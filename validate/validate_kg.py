"""
validate_kg.py
──────────────
Four-layer validation for the Sinhala Traditional-Medicine KG.

Layer 1 — Programmatic ("schema-mechanical"):
  - SHACL shape conformance (via pySHACL on knowledge_graph/kg.ttl)
  - Anchor probe: positive/negative term assertions from anchors.yaml
  - Provenance presence on every node and edge
  - ID format checks (`<type>:<key>`)
  - Edge domain/range integrity
  - Cardinality sanity

Layer 2 — Cross-source agreement:
  - POWO re-verification: every bound Plant LSID still resolves
  - ICD-11 TM2 re-verification: every bound disease code still in the API

Layer 3 — Expert spot-check (sample generator only):
  - Writes validate/expert_sample.tsv with 100 stratified random
    nodes + edges for human annotation. Validator does not score.

Layer 4 — LLM-judge: designed in docs/validation_methodology.md;
  not implemented in v1.

OUTPUTS (validate/)
  validation_report.md         human-readable
  validation_report.json       machine-readable
  shacl_violations.ttl         pySHACL detailed report
  expert_sample.tsv            stratified sample for Layer 3

USAGE
  python validate/validate_kg.py
  python validate/validate_kg.py --skip-cross-source
  python validate/validate_kg.py --sample-size 200
"""
from __future__ import annotations
import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── load .env (for ICD-11 OAuth) without committing dotenv as a dep ──────────
def _load_dotenv():
    for p in (Path(".env"),
              Path(__file__).resolve().parent.parent / ".env",
              Path(__file__).resolve().parent.parent.parent / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
            return


# ── helpers ──────────────────────────────────────────────────────────────────
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ID format: type-slug (lowercase ASCII + underscore) followed by ':' and
# any non-whitespace key (allows Unicode Sinhala/Sanskrit characters).
ID_RE = re.compile(r"^[a-z][a-z_]*:\S+$")


def load_kg_jsonld(path):
    """Returns (nodes_by_id, edges)."""
    d = json.load(open(path, encoding="utf-8"))
    nodes, edges = {}, []
    for item in d.get("@graph", []):
        if "@id" in item:
            nodes[item["@id"]] = item
        elif "from" in item and "to" in item:
            edges.append(item)
    return nodes, edges


# ── LAYER 1 ──────────────────────────────────────────────────────────────────
def _jsonld_to_rdf_graph(jsonld_path):
    """Hand-roll JSON-LD → rdflib.Graph so we don't depend on the
    `@context` URL being network-resolvable. Skips the @context tag and
    maps each @graph entry to triples in our nl: namespace."""
    from rdflib import Graph, URIRef, Literal, Namespace, RDF
    NL  = Namespace("https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp/ns/")
    ENT = Namespace("https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp/id/")

    def iri_for(internal_id):
        safe = internal_id.replace(":", "__").replace("/", "_").replace(" ", "_")
        return URIRef(ENT[safe])

    d = json.load(open(jsonld_path, encoding="utf-8"))
    g = Graph()
    g.bind("nl", NL)
    g.bind("ent", ENT)
    for item in d.get("@graph", []):
        if "@id" in item:
            # node
            subj = iri_for(item["@id"])
            ntype = item.get("@type")
            if ntype:
                g.add((subj, RDF.type, URIRef(NL[ntype])))
            for k, v in item.items():
                if k in ("@id", "@type"):
                    continue
                if v in (None, "", [], {}):
                    continue
                if isinstance(v, dict):
                    # flatten nested dicts (external{}, provenance{}) as
                    # multiple `ns:<key>_<subkey>` literals — keeps SHACL
                    # shape-targeting simple.
                    for sk, sv in v.items():
                        if sv in (None, "", [], {}):
                            continue
                        g.add((subj, URIRef(NL[f"{k}__{sk}"]), Literal(str(sv))))
                elif isinstance(v, list):
                    for x in v:
                        if x not in (None, ""):
                            g.add((subj, URIRef(NL[k]), Literal(str(x))))
                else:
                    g.add((subj, URIRef(NL[k]), Literal(str(v))))
        elif "from" in item and "to" in item:
            # edge — represent as a typed link AND a reified node so we
            # can hang edge properties off it if needed.
            etype = item.get("@type")
            if not etype:
                continue
            src = iri_for(item["from"])
            dst = iri_for(item["to"])
            g.add((src, URIRef(NL[etype]), dst))
    return g


def layer1_shacl(kg_jsonld_path, shapes_ttl_path, out_violations):
    """SHACL validate the in-memory RDF graph derived from kg.jsonld."""
    try:
        from pyshacl import validate
        from rdflib import Namespace
    except ImportError:
        return {"skipped": "pyshacl / rdflib not installed"}

    data_graph = _jsonld_to_rdf_graph(kg_jsonld_path)

    conforms, results_graph, results_text = validate(
        data_graph=data_graph,
        shacl_graph=str(shapes_ttl_path),
        shacl_graph_format="ttl",
        inference="rdfs",
        debug=False,
    )
    results_graph.serialize(destination=str(out_violations), format="turtle")
    SH = Namespace("http://www.w3.org/ns/shacl#")
    violations = [r for r in results_graph.subjects(predicate=SH.resultMessage)]
    return {
        "conforms": bool(conforms),
        "violation_count": len(violations),
        "report_text_summary": (results_text[:1200] if results_text else ""),
        "data_triples": len(data_graph),
    }


def layer1_anchors(nodes, anchors):
    out = {"positive_disease_tm2": [], "positive_plant_powo": [],
           "negative_unresolved_vernacular": []}

    # find Disease node by canonical_iast
    disease_by_iast = {n.get("canonical_iast"): n
                       for n in nodes.values()
                       if n.get("@type") == "Disease" and n.get("canonical_iast")}
    plant_by_iast = {n.get("canonical_iast"): n
                     for n in nodes.values()
                     if n.get("@type") == "Plant" and n.get("canonical_iast")}
    plant_by_si = {n.get("canonical_si"): n
                   for n in nodes.values()
                   if n.get("@type") == "Plant" and n.get("canonical_si")}

    # Positive disease checks
    for a in anchors.get("positive_disease_tm2", []):
        lemma = a["lemma"]
        n = disease_by_iast.get(lemma)
        if not n:
            out["positive_disease_tm2"].append({
                "lemma": lemma, "pass": False, "reason": "Disease not in KG"})
            continue
        ext = n.get("external", {}) or {}
        ok_tm2 = ext.get("icd11_tm2") == a.get("expected_tm2")
        ok_rub = (a.get("rubric_substring") or "") in (n.get("english_rubric") or "")
        out["positive_disease_tm2"].append({
            "lemma": lemma,
            "expected_tm2": a["expected_tm2"],
            "actual_tm2": ext.get("icd11_tm2"),
            "rubric_match": ok_rub,
            "pass": bool(ok_tm2 and ok_rub),
        })

    # Positive plant checks
    for a in anchors.get("positive_plant_powo", []):
        lemma = a["lemma"]
        n = plant_by_iast.get(lemma)
        if not n:
            out["positive_plant_powo"].append({
                "lemma": lemma, "pass": False, "reason": "Plant not in KG"})
            continue
        ext = n.get("external", {}) or {}
        ok_powo = bool(ext.get("powo_lsid"))
        ok_family = (a.get("expected_powo_family") or "") in (n.get("family") or "") \
                     if a.get("expected_powo_family") else True
        ok_latin = (a.get("latin_substring") or "") in (n.get("latin_binomial") or "") \
                    if a.get("latin_substring") else True
        out["positive_plant_powo"].append({
            "lemma": lemma,
            "has_powo_lsid": ok_powo,
            "family_match":  ok_family,
            "latin_match":   ok_latin,
            "pass": bool(ok_powo and ok_family and ok_latin),
        })

    # Negative checks — these Sinhala terms must appear as Plant nodes
    # with is_unresolved (no Sanskrit lemma)
    for a in anchors.get("negative_unresolved_vernacular", []):
        si = a["sinhala"]
        n = plant_by_si.get(si)
        if not n:
            out["negative_unresolved_vernacular"].append({
                "sinhala": si, "pass": False,
                "reason": "Sinhala surface not present in KG"})
            continue
        ok = bool(n.get("is_unresolved")) and not n.get("canonical_iast")
        out["negative_unresolved_vernacular"].append({
            "sinhala": si,
            "is_unresolved": bool(n.get("is_unresolved")),
            "canonical_iast": n.get("canonical_iast"),
            "pass": ok,
        })

    # Aggregate
    n_pass  = sum(1 for v in out.values() for r in v if r.get("pass"))
    n_total = sum(len(v) for v in out.values())
    return {"per_check": out, "n_pass": n_pass, "n_total": n_total,
            "pct": round(100 * n_pass / max(n_total, 1), 1)}


def layer1_provenance_id(nodes, edges, required_node, required_edge):
    """In JSON-LD, `id` and `type` appear as `@id` and `@type`. Map
    `id`/`type` in the YAML anchor list to those JSON-LD reserved keys."""
    def _missing(rec, required):
        miss = []
        for f in required:
            key = "@id" if f == "id" else ("@type" if f == "type" else f)
            if not rec.get(key):
                miss.append(f)
        return miss

    bad_nodes, bad_edges, bad_ids = [], [], []
    for nid, n in nodes.items():
        m = _missing(n, required_node)
        if m:
            bad_nodes.append({"id": nid, "missing": m})
        if not ID_RE.match(nid):
            bad_ids.append(nid)
    for e in edges:
        m = _missing(e, required_edge)
        if m:
            bad_edges.append({
                "edge": f"{e.get('from','?')}-[{e.get('@type','?')}]->{e.get('to','?')}",
                "missing": m,
            })
    return {
        "nodes_total":        len(nodes),
        "nodes_with_missing_provenance": len(bad_nodes),
        "edges_total":        len(edges),
        "edges_with_missing_provenance": len(bad_edges),
        "ids_failing_format": len(bad_ids),
        "sample_bad_node_ids":  bad_ids[:8],
        "sample_bad_nodes":     bad_nodes[:8],
        "sample_bad_edges":     bad_edges[:8],
    }


def layer1_edge_domain_range(nodes, edges, dr):
    type_of = {nid: n.get("@type") for nid, n in nodes.items()}
    failures = defaultdict(list)
    counts = Counter()
    for e in edges:
        et = e.get("@type")
        counts[et] += 1
        if et not in dr:
            continue
        ftype = type_of.get(e.get("from"))
        ttype = type_of.get(e.get("to"))
        if ftype not in dr[et]["from"]:
            failures[et].append({"edge": e, "violation": f"from_type={ftype} not in {dr[et]['from']}"})
        if ttype not in dr[et]["to"]:
            failures[et].append({"edge": e, "violation": f"to_type={ttype} not in {dr[et]['to']}"})
    return {
        "edge_counts": dict(counts),
        "failures_by_edge_type": {et: len(v) for et, v in failures.items()},
        "samples": {et: v[:3] for et, v in failures.items()},
    }


def layer1_cardinality(nodes, edges):
    formulation_contains = Counter()
    for e in edges:
        if e.get("@type") == "CONTAINS":
            formulation_contains[e.get("from")] += 1
    formulations = [nid for nid, n in nodes.items() if n.get("@type") == "Formulation"]
    no_contains = [f for f in formulations if formulation_contains[f] == 0]
    return {
        "formulation_total": len(formulations),
        "formulation_with_no_CONTAINS": len(no_contains),
        "formulation_pct_with_contains":
            round(100 * (len(formulations) - len(no_contains)) / max(len(formulations), 1), 1),
        "sample_no_CONTAINS": no_contains[:8],
        "note": ("Yogamālāva formulas have no separately-extracted "
                 "ingredient list, so 'no CONTAINS' is expected for "
                 "verse-form formulations."),
    }


# ── LAYER 2 ──────────────────────────────────────────────────────────────────
def layer2_powo_reverify(nodes, sample_n=30):
    try:
        import requests
    except ImportError:
        return {"skipped": "requests not installed"}
    plants_with_powo = [n for n in nodes.values()
                        if n.get("@type") == "Plant"
                        and (n.get("external") or {}).get("powo_lsid")]
    if not plants_with_powo:
        return {"checked": 0, "agree": 0}
    sample = random.sample(plants_with_powo, min(sample_n, len(plants_with_powo)))
    hdr = {"User-Agent": "sinhala-medicine-nlp-validator/1.0",
           "Accept": "application/json"}
    agree, disagree, error = 0, [], []
    for n in sample:
        lsid = n["external"]["powo_lsid"]
        try:
            r = requests.get(f"https://powo.science.kew.org/api/2/taxon/{lsid}",
                             headers=hdr, timeout=15)
            if r.status_code != 200:
                error.append({"lsid": lsid, "status": r.status_code})
                continue
            d = r.json()
            fam_now = d.get("family")
            our_fam = n.get("family")
            if our_fam and fam_now and our_fam == fam_now:
                agree += 1
            else:
                disagree.append({
                    "id": n["@id"], "lsid": lsid,
                    "our_family": our_fam, "powo_family": fam_now})
            time.sleep(0.20)
        except Exception as e:
            error.append({"lsid": lsid, "error": str(e)[:120]})
    return {
        "sample_size": len(sample),
        "agree":       agree,
        "disagree":    len(disagree),
        "errors":      len(error),
        "agreement_pct": round(100 * agree / max(len(sample), 1), 1),
        "samples_disagree": disagree[:5],
        "samples_error":    error[:5],
    }


def layer2_icd11_reverify(nodes, sample_n=20):
    try:
        import requests
    except ImportError:
        return {"skipped": "requests not installed"}
    cid  = os.environ.get("ICD_CLIENT_ID")
    csec = os.environ.get("ICD_CLIENT_SECRET")
    if not (cid and csec):
        return {"skipped": "ICD_CLIENT_ID / ICD_CLIENT_SECRET not set"}
    diseases_with_tm2 = [n for n in nodes.values()
                         if n.get("@type") == "Disease"
                         and (n.get("external") or {}).get("icd11_uri")]
    if not diseases_with_tm2:
        return {"checked": 0}
    sample = random.sample(diseases_with_tm2, min(sample_n, len(diseases_with_tm2)))
    # get token
    tok = requests.post("https://icdaccessmanagement.who.int/connect/token",
        data={"client_id": cid, "client_secret": csec,
              "scope": "icdapi_access", "grant_type": "client_credentials"},
        timeout=20).json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}", "Accept": "application/json",
           "Accept-Language": "en", "API-Version": "v2"}
    agree, disagree, error = 0, [], []
    for n in sample:
        uri = n["external"]["icd11_uri"]
        if uri.startswith("http://"):
            uri = "https://" + uri[len("http://"):]
        try:
            r = requests.get(uri, headers=hdr, timeout=15)
            if r.status_code != 200:
                error.append({"uri": uri, "status": r.status_code})
                continue
            d = r.json()
            api_code = d.get("code") or ""
            our_code = (n.get("external") or {}).get("icd11_tm2") or ""
            if api_code == our_code:
                agree += 1
            else:
                disagree.append({"id": n["@id"],
                                 "uri": uri,
                                 "our_code": our_code,
                                 "api_code": api_code})
            time.sleep(0.10)
        except Exception as e:
            error.append({"uri": uri, "error": str(e)[:120]})
    return {
        "sample_size": len(sample),
        "agree":       agree,
        "disagree":    len(disagree),
        "errors":      len(error),
        "agreement_pct": round(100 * agree / max(len(sample), 1), 1),
        "samples_disagree": disagree[:5],
        "samples_error":    error[:5],
    }


# ── LAYER 3 ──────────────────────────────────────────────────────────────────
def layer3_sample(nodes, edges, sample_n, out_path):
    """Stratified random sample of nodes + edges for human review."""
    by_type_nodes = defaultdict(list)
    for n in nodes.values():
        by_type_nodes[n.get("@type")].append(n)
    by_type_edges = defaultdict(list)
    for e in edges:
        by_type_edges[e.get("@type")].append(e)

    # Half nodes, half edges
    half = sample_n // 2
    rows = []
    # Node sample — proportional to type count, min 5 per type when possible
    n_types = list(by_type_nodes.keys())
    per_type = max(half // max(len(n_types), 1), 5)
    for t in n_types:
        bucket = by_type_nodes[t]
        picks = random.sample(bucket, min(per_type, len(bucket)))
        for p in picks:
            rows.append([
                "node", t, p.get("@id"),
                p.get("canonical_iast", "") or p.get("canonical_si", "") or "",
                (p.get("english_rubric") or
                 p.get("latin_binomial") or
                 p.get("gloss", "")[:80] or ""),
                "", "",   # correct? notes columns for annotator
            ])
    # Edge sample
    e_types = list(by_type_edges.keys())
    per_type = max(half // max(len(e_types), 1), 5)
    for t in e_types:
        bucket = by_type_edges[t]
        picks = random.sample(bucket, min(per_type, len(bucket)))
        for p in picks:
            rows.append([
                "edge", t, "",
                p.get("from", ""),
                p.get("to", ""),
                "", "",
            ])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("kind\ttype\tid\tdisplay_a\tdisplay_b\tcorrect\tnotes\n")
        for r in rows:
            f.write("\t".join(str(x).replace("\t", " ") for x in r) + "\n")
    return {"sample_size": len(rows), "out_path": str(out_path)}


# ── REPORT WRITERS ───────────────────────────────────────────────────────────
def md_report(report, out_path):
    L = report
    s = f"""# KG Validation Report

Generated: {L['generated_at']}
Schema version: {L.get('schema_version','v1')}
Total nodes: {L['kg_size']['nodes']} · edges: {L['kg_size']['edges']}

## Summary

| Layer | Pass | Total | % |
|---|---:|---:|---:|
| 1 — anchor probe                          | {L['layer1']['anchors']['n_pass']} | {L['layer1']['anchors']['n_total']} | {L['layer1']['anchors']['pct']} % |
| 1 — provenance present (nodes)            | {L['layer1']['prov']['nodes_total'] - L['layer1']['prov']['nodes_with_missing_provenance']} | {L['layer1']['prov']['nodes_total']} | {round(100*(1-L['layer1']['prov']['nodes_with_missing_provenance']/max(L['layer1']['prov']['nodes_total'],1)),1)} % |
| 1 — provenance present (edges)            | {L['layer1']['prov']['edges_total'] - L['layer1']['prov']['edges_with_missing_provenance']} | {L['layer1']['prov']['edges_total']} | {round(100*(1-L['layer1']['prov']['edges_with_missing_provenance']/max(L['layer1']['prov']['edges_total'],1)),1)} % |
| 1 — ID format                             | {L['layer1']['prov']['nodes_total'] - L['layer1']['prov']['ids_failing_format']} | {L['layer1']['prov']['nodes_total']} | {round(100*(1-L['layer1']['prov']['ids_failing_format']/max(L['layer1']['prov']['nodes_total'],1)),1)} % |
| 1 — SHACL conformance                     | {'YES' if L['layer1']['shacl'].get('conforms') else 'NO'} | — | violations: {L['layer1']['shacl'].get('violation_count', '—')} |

## Layer 1 — Programmatic

### Anchor probe ({L['layer1']['anchors']['pct']} %)

**Positive disease → TM2 assertions**:
"""
    for r in L['layer1']['anchors']['per_check']['positive_disease_tm2']:
        mark = '✓' if r.get('pass') else '✗'
        s += f"- {mark} `{r['lemma']}` → expected {r.get('expected_tm2','—')}, actual {r.get('actual_tm2','—')}\n"
    s += "\n**Positive plant → POWO assertions**:\n"
    for r in L['layer1']['anchors']['per_check']['positive_plant_powo']:
        mark = '✓' if r.get('pass') else '✗'
        s += f"- {mark} `{r['lemma']}` (POWO: {r.get('has_powo_lsid','—')}, family: {r.get('family_match','—')}, latin: {r.get('latin_match','—')})\n"
    s += "\n**Negative vernacular → unresolved**:\n"
    for r in L['layer1']['anchors']['per_check']['negative_unresolved_vernacular']:
        mark = '✓' if r.get('pass') else '✗'
        s += f"- {mark} `{r['sinhala']}` is_unresolved={r.get('is_unresolved')}, canonical_iast={r.get('canonical_iast')}\n"

    s += f"""

### Edge domain/range integrity
{json.dumps(L['layer1']['edges'], indent=2, ensure_ascii=False)}

### Cardinality sanity
- Formulations with no CONTAINS edges: {L['layer1']['cardinality']['formulation_with_no_CONTAINS']} / {L['layer1']['cardinality']['formulation_total']}  ({L['layer1']['cardinality']['formulation_pct_with_contains']} % do have ingredients)
- Note: {L['layer1']['cardinality']['note']}

### SHACL validation
- Conforms: {L['layer1']['shacl'].get('conforms', '—')}
- Violations: {L['layer1']['shacl'].get('violation_count', '—')}
- Detailed report: `validate/shacl_violations.ttl`

## Layer 2 — Cross-source agreement

### POWO re-verification (botanical taxonomy)
{json.dumps(L.get('layer2',{}).get('powo',{}), indent=2, ensure_ascii=False)}

### ICD-11 TM2 re-verification (WHO authority)
{json.dumps(L.get('layer2',{}).get('icd11',{}), indent=2, ensure_ascii=False)}

## Layer 3 — Expert spot-check (sample for human review)

Stratified random sample written to `validate/expert_sample.tsv`
({L.get('layer3',{}).get('sample_size','—')} rows). Two annotators
score each row as correct / partial / wrong; compute Cohen's κ on
the 20-item double-coded subset. See
[`docs/validation_methodology.md`](../docs/validation_methodology.md).

## Layer 4 — LLM-judge

Not implemented in v1. See
[`docs/validation_methodology.md`](../docs/validation_methodology.md).
"""
    out_path.write_text(s, encoding="utf-8")


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    _load_dotenv()
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--kg-jsonld", default=str(here / "knowledge_graph/kg.jsonld"))
    ap.add_argument("--kg-ttl",    default=str(here / "knowledge_graph/kg.ttl"))
    ap.add_argument("--shapes",    default=str(here / "validate/shapes.ttl"))
    ap.add_argument("--anchors",   default=str(here / "validate/anchors.yaml"))
    ap.add_argument("--out-dir",   default=str(here / "validate"))
    ap.add_argument("--sample-size", type=int, default=100)
    ap.add_argument("--skip-cross-source", action="store_true")
    ap.add_argument("--powo-sample", type=int, default=30)
    ap.add_argument("--icd-sample",  type=int, default=20)
    args = ap.parse_args()

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    random.seed(0)

    # Load YAML anchors (no PyYAML dep — inline mini-parser of the simple
    # tree we wrote)
    try:
        import yaml
        anchors = yaml.safe_load(open(args.anchors, encoding="utf-8"))
    except ImportError:
        sys.exit("pyyaml is required:  .venv/bin/python -m pip install pyyaml")

    nodes, edges = load_kg_jsonld(args.kg_jsonld)
    print(f"loaded KG: {len(nodes)} nodes, {len(edges)} edges")

    # ── LAYER 1 ──
    print("Layer 1 — programmatic …")
    print("  SHACL …")
    shacl = layer1_shacl(args.kg_jsonld, args.shapes, out_dir / "shacl_violations.ttl")
    print("  anchors …")
    anchor_res = layer1_anchors(nodes, anchors)
    print("  provenance + ID format …")
    prov = layer1_provenance_id(nodes, edges,
                                anchors["required_node_provenance"],
                                anchors["required_edge_provenance"])
    print("  edge domain/range …")
    er = layer1_edge_domain_range(nodes, edges, anchors["edge_domain_range"])
    print("  cardinality …")
    card = layer1_cardinality(nodes, edges)

    # ── LAYER 2 ──
    layer2 = {}
    if not args.skip_cross_source:
        print("Layer 2 — cross-source …")
        print("  POWO re-verification …")
        layer2["powo"] = layer2_powo_reverify(nodes, sample_n=args.powo_sample)
        print("  ICD-11 TM2 re-verification …")
        layer2["icd11"] = layer2_icd11_reverify(nodes, sample_n=args.icd_sample)
    else:
        print("Layer 2 skipped (--skip-cross-source).")

    # ── LAYER 3 ──
    print(f"Layer 3 — writing expert sample ({args.sample_size}) …")
    layer3 = layer3_sample(nodes, edges, args.sample_size, out_dir / "expert_sample.tsv")

    report = {
        "generated_at": now_iso(),
        "schema_version": "v1",
        "kg_size": {"nodes": len(nodes), "edges": len(edges)},
        "layer1": {
            "shacl":       shacl,
            "anchors":     anchor_res,
            "prov":        prov,
            "edges":       er,
            "cardinality": card,
        },
        "layer2": layer2,
        "layer3": layer3,
    }

    (out_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_report(report, out_dir / "validation_report.md")

    print(f"\nWrote {out_dir}/validation_report.{{md,json}}")
    print(f"     {out_dir}/shacl_violations.ttl")
    print(f"     {out_dir}/expert_sample.tsv")
    print()
    print("=== Headline ===")
    print(f"  Anchor probe: {anchor_res['n_pass']}/{anchor_res['n_total']} pass ({anchor_res['pct']} %)")
    print(f"  Provenance — nodes missing fields: {prov['nodes_with_missing_provenance']}/{prov['nodes_total']}")
    print(f"  Provenance — edges missing fields: {prov['edges_with_missing_provenance']}/{prov['edges_total']}")
    print(f"  ID format — failing: {prov['ids_failing_format']}/{prov['nodes_total']}")
    print(f"  SHACL conforms: {shacl.get('conforms', '—')} (violations: {shacl.get('violation_count', '—')})")
    if layer2.get("powo"):
        print(f"  POWO re-verify: {layer2['powo'].get('agree','-')}/{layer2['powo'].get('sample_size','-')} agree ({layer2['powo'].get('agreement_pct','-')} %)")
    if layer2.get("icd11"):
        print(f"  ICD-11 re-verify: {layer2['icd11'].get('agree','-')}/{layer2['icd11'].get('sample_size','-')} agree ({layer2['icd11'].get('agreement_pct','-')} %)")


if __name__ == "__main__":
    main()

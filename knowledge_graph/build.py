"""
build.py
────────
Build the Sinhala Traditional Medicine KG v1 from existing artifacts.

INPUTS (read-only)
  data/structured/*_structured.json                  Vol I (tabular) entries
  data/structured/yogamalawa/yogamalawa_structured_v2.json  Yogamālāva (verse) entries
  data/lexicons/ingredients_lexicon.json             Sanskrit resolution per Sinhala ingredient
  data/lexicons/prose_lexicon.json                   Sanskrit resolution for prose terms
  data/lexicons/names_lexicon.json                   Sanskrit resolution for formula-name words
  data/lexicons/botanical_candidates.json            Latin binomials extracted from MW glosses
  data/lexicons/botanical_powo.json                  Latin → POWO IPNI LSID + modern name
  data/lexicons/indication_icd11_tm2.json            Sanskrit indication → ICD-11 TM2 code

OUTPUTS (knowledge_graph/)
  kg.jsonld             Linked-data view (JSON-LD @graph, matches docs/context.jsonld)
  kg.cypher             Neo4j CREATE statements
  kg.ttl                RDF Turtle
  build_report.json     Per-type node/edge counts + external-ID coverage

DESIGN (see docs/kg_schema.md for the v1 schema contract)
  Node types     Formulation, Plant, Mineral, Disease, PreparationType, Route,
                 PharmacologicalProperty (the closed-enum nodes are emitted
                 only if referenced).
  Edge types     CONTAINS, IS_TYPE, DOSED_WITH, TREATS, CO_OCCURS, VARIANT_OF.
  Provenance     Every node and edge carries {source_doc, source_record_id,
                 extractor_version, confidence, created_at}.
  ID format      Internal: `<type>:<key>`. External: under .external{}.

USAGE
  python knowledge_graph/build.py
  python knowledge_graph/build.py --max-cooccurrence 200  # cap CO_OCCURS edges
  python knowledge_graph/build.py --no-yogamalawa         # Vol I only
"""
from __future__ import annotations
import argparse
import glob
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from itertools import combinations

EXTRACTOR_VERSION = "kg_build_v1"
SCHEMA_VERSION    = "1.0"


# ── helpers ──────────────────────────────────────────────────────────────────
def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(s):
    """Make a string safe for use inside an internal ID."""
    return nfc(s).replace(" ", "_").replace("/", "_").replace("‍", "")


# ── small closed vocabularies ────────────────────────────────────────────────

# Map of formula-name suffix in Sinhala (Sanskrit) → PreparationType lemma.
PREP_SUFFIXES = [
    ("ක්වාථය",   "kvātha"),     # kasāya = decoction
    ("කෂාය",     "kaṣāya"),
    ("තෛලය",    "taila"),       # medicated oil
    ("ඝෘතය",    "ghṛta"),       # medicated ghee
    ("කල්කය",   "kalka"),       # paste
    ("චූර්ණය",   "cūrṇa"),       # powder
    ("ගුළිකාව",  "gulika"),      # pill
    ("ගුළිය",     "gulika"),
    ("ගුළි",      "gulika"),
    ("අරිෂ්ටය",  "ariṣṭa"),      # fermented decoction
    ("අවලේහ",   "avaleha"),     # confection
    ("භස්ම",     "bhasma"),      # calcined ash (also a noun marker)
]

# Hand-curated set of Sanskrit lemmas that denote mineral / non-plant
# substances. Used to classify ingredient-head lemmas as Mineral vs Plant.
KNOWN_MINERAL_LEMMAS = {
    # salts and alkalis
    "saindhava", "saindhavalavaṇa", "lavaṇa", "yavakṣāra", "ṭaṅkaṇa", "kāca",
    # metals
    "lauha", "tāmra", "raja", "rajata", "svarṇa", "vaṅga", "yaśada", "ārikuṣṭha",
    # bhasma family
    "bhasma", "abhraka",
    # mercury / minerals
    "rasa", "rasadi", "rasendra", "rasasindūra", "gandhaka", "haritāla",
    "manaḥśilā", "mākṣika", "padmakāṣṭha",
    # generic mineral markers
    "kānta", "śaṅkha", "muktā", "śilāj", "śilājit", "śilājatu",
}

# Mineral-ish gloss keywords (used when lemma isn't in the hand list).
MINERAL_GLOSS_KEYWORDS = re.compile(
    r"\b(salt|alkali|sulphur|mercury|copper|iron|metal|ash|calx|"
    r"calcined|mineral|stone|earth|gypsum|alum|silica)\b",
    re.IGNORECASE,
)

# Default route when none is explicitly named in `anupāna`.
DEFAULT_ROUTE = "oral"

# Vehicle (anupāna) detection — Sinhala phrases that strongly indicate
# a specific vehicle / adjuvant.
VEHICLE_HINTS = {
    "මී පැණි":      ("madhu",        "Honey"),
    "ගිතෙල්":       ("ghṛta",        "Ghee"),
    "තල තෙල්":     ("tila_taila",    "Sesame oil"),
    "තලතෙල්":      ("tila_taila",    "Sesame oil"),
    "එරඬු තෙල්":   ("eraṇḍa_taila", "Castor oil"),
    "එරඬුතෙල්":    ("eraṇḍa_taila", "Castor oil"),
    "එළකිරි":       ("kṣīra",        "Cow milk"),
    "මී":            ("madhu",        "Honey"),
    "කිරි":          ("kṣīra",        "Milk"),
    "උනු වතුර":    ("uṣṇodaka",     "Warm water"),
    "උනුවතුර":     ("uṣṇodaka",     "Warm water"),
}

# Disease-keyword regex (reused from icd11_tm2_mapper) — used to limit
# which prose-lexicon lemmas we even attempt to match to TM2 codes.
DISEASE_GLOSS = re.compile(
    r"\b(fever|disease|disorder|cough|pain|ulcer|swelling|inflammation|"
    r"piles|asthma|haemorrhoid|consumption|leprosy|spleen|urin\w*|"
    r"colic|diarrhoea|dropsy|stone|jaundice|gout|bile|phlegm|wind|"
    r"tumour|distension|wound|haemorrhage|abscess|leucoderma|"
    r"breathing|panting|syndrome|obstruction|constipation|catarrh|"
    r"flatulence|vomiting|loss\s+of\s+appetite)\b",
    re.IGNORECASE,
)


# ── load inputs ──────────────────────────────────────────────────────────────
def load_inputs(repo_root: Path, include_yogamalawa: bool):
    structured = []
    for path in sorted(glob.glob(str(repo_root / "data/structured/*_structured.json"))):
        d = json.load(open(path, encoding="utf-8"))
        # Vol I entry numbers reset per 50-page batch, so we must
        # namespace the Formulation ID by batch to avoid collisions.
        batch = d.get("batch") or Path(path).stem.replace("_structured", "")
        for e in d.get("entries", []):
            structured.append({"entry": e, "source_doc": path,
                               "batch": batch,
                               "source_register": "tabular"})
    if include_yogamalawa:
        ypath = repo_root / "data/structured/yogamalawa/yogamalawa_structured_v2.json"
        if ypath.exists():
            d = json.load(open(ypath, encoding="utf-8"))
            for e in d.get("entries", []):
                structured.append({"entry": e, "source_doc": str(ypath),
                                   "batch": "yogamalawa",
                                   "source_register": "verse"})

    def jload(p):
        return json.load(open(p, encoding="utf-8")) if p.exists() else {}

    lex_dir = repo_root / "data/lexicons"
    ingredients_lex = jload(lex_dir / "ingredients_lexicon.json")
    prose_lex       = jload(lex_dir / "prose_lexicon.json")
    names_lex       = jload(lex_dir / "names_lexicon.json")
    botanical_seed  = jload(lex_dir / "botanical_candidates.json")
    powo            = jload(lex_dir / "botanical_powo.json")
    tm2             = jload(lex_dir / "indication_icd11_tm2.json")
    return {
        "formulas": structured,
        "ingredients_lex": ingredients_lex,
        "prose_lex": prose_lex,
        "names_lex": names_lex,
        "botanical_seed": botanical_seed,
        "powo": powo,
        "tm2": tm2,
    }


# ── ingredient resolution (Sinhala → Plant/Mineral node ID) ──────────────────
def head_lemma(words):
    """For a multi-word Sinhala ingredient, return the head lemma.
    Convention: the rightmost word's lemma if resolved; else None."""
    if not words:
        return None, None, None
    # walk right-to-left and pick the first resolved
    for w in reversed(words):
        if w.get("lemma"):
            return w["lemma"], (w.get("gloss") or ""), w.get("method")
    return None, None, None


def classify_ingredient(lemma, gloss):
    """Return ('Plant' | 'Mineral', canonical_id) for a resolved lemma."""
    if not lemma:
        return None, None
    base = lemma.replace("-", "").replace(" ", "")
    if base in KNOWN_MINERAL_LEMMAS:
        return "Mineral", f"min:{slug(lemma)}"
    if any(base.endswith(x) for x in ("lavaṇa", "bhasma", "kṣāra")):
        return "Mineral", f"min:{slug(lemma)}"
    if MINERAL_GLOSS_KEYWORDS.search(gloss or ""):
        return "Mineral", f"min:{slug(lemma)}"
    return "Plant", f"plant:{slug(lemma)}"


def resolve_ingredient(surface_si, lex):
    """Look up an ingredient's Sinhala surface form in ingredients_lexicon.
    Returns (kind, internal_id, lemma, gloss, method) or (None, None, None, None, None).
    """
    rec = lex.get(nfc(surface_si)) or lex.get(surface_si)
    if not rec or not rec.get("words"):
        return None, None, None, None, None
    lemma, gloss, method = head_lemma(rec["words"])
    if not lemma:
        return None, None, None, None, None
    kind, internal = classify_ingredient(lemma, gloss)
    return kind, internal, lemma, gloss, method


# ── Latin binomial detection (reused for plant external IDs) ─────────────────
LATIN_RE = re.compile(r"\b([A-Z][a-zæëïöü]{2,})\s+([A-Z]?[a-z][a-zæëïöü]{2,})\b")
LATIN_GENUS_STOP = {"The", "This", "That", "See", "Name", "Comp", "Often",
                    "Bombay", "Indian", "According", "Sanskrit", "Hindi",
                    "Bengal", "Ceylon", "Linn", "Roxb", "Wall", "Willd", "Don",
                    "Lam", "DC", "Nees", "Columba", "Coluber"}


def extract_latin_from_gloss(gloss):
    out = []
    for g, sp in LATIN_RE.findall(gloss or ""):
        if g in LATIN_GENUS_STOP:
            continue
        out.append(f"{g} {sp}")
    return out


# ── PreparationType detection ───────────────────────────────────────────────
def detect_prep_type(name_sa: str) -> str | None:
    if not name_sa:
        return None
    for suffix_si, prep_lemma in PREP_SUFFIXES:
        if name_sa.endswith(suffix_si):
            return prep_lemma
    return None


# ── KG assembly ──────────────────────────────────────────────────────────────
def build_kg(inputs, max_cooccurrence=200, min_cooccurrence=3):
    nodes = {}      # id → node dict
    edges = []      # list of edge dicts
    co_pairs = Counter()   # (a_id, b_id) → count

    def ensure_node(node_id, ntype, **props):
        if node_id in nodes:
            for k, v in props.items():
                if v and not nodes[node_id].get(k):
                    nodes[node_id][k] = v
            return nodes[node_id]
        nodes[node_id] = {
            "id": node_id, "type": ntype,
            "created_at": now_iso(),
            "extractor_version": EXTRACTOR_VERSION,
            **props,
        }
        return nodes[node_id]

    def add_edge(etype, src, dst, **props):
        edges.append({
            "type": etype, "from": src, "to": dst,
            "extractor_version": EXTRACTOR_VERSION,
            "confidence": props.pop("confidence", 1.0),
            **props,
        })

    # ── 1. Build PreparationType + Route nodes (closed enum, idempotent) ──
    for _, lemma in PREP_SUFFIXES:
        ensure_node(f"prep:{lemma}", "PreparationType",
                    canonical_iast=lemma, sanskrit=lemma)
    for r in (DEFAULT_ROUTE, "anuvāsana", "nasya", "basti", "abhyaṅga"):
        ensure_node(f"route:{slug(r)}", "Route",
                    canonical_iast=r, sanskrit=r)
    for v_iast, v_en in [(v[0], v[1]) for v in VEHICLE_HINTS.values()]:
        ensure_node(f"vehicle:{slug(v_iast)}", "Plant",
                    canonical_iast=v_iast, sanskrit=v_iast,
                    english_common=[v_en])

    # ── 2. Build POWO-cached Latin-binomial → LSID lookup ──
    powo = inputs["powo"]

    def attach_powo_external(plant_node, lemma, gloss):
        # If the lemma's MW gloss yields a Latin binomial we have in POWO,
        # add the external IDs.
        candidates = extract_latin_from_gloss(gloss)
        for b in candidates:
            rec = powo.get(b)
            if rec and rec.get("powo_lsid"):
                plant_node.setdefault("external", {})
                plant_node["external"].setdefault("powo_lsid", rec["powo_lsid"])
                plant_node.setdefault("latin_binomial",
                                       rec.get("modern_accepted_name") or b)
                plant_node.setdefault("family", rec.get("family"))
                plant_node.setdefault("kingdom", rec.get("kingdom"))
                if rec.get("is_synonym"):
                    plant_node["external"]["powo_synonym_of_lsid"] = \
                        rec.get("modern_accepted_lsid")
                return True
        return False

    # ── 3. Build Disease nodes from the TM2 mapping ──
    tm2_index = {}   # iast lemma → Disease node id
    for lemma, rec in inputs["tm2"].items():
        if not rec.get("matched_via"):
            continue
        node_id = f"disease:{slug(lemma)}"
        ext = {}
        if rec.get("tm2_code"):
            ext["icd11_tm2"] = rec["tm2_code"]
        if rec.get("tm2_uri"):
            ext["icd11_uri"] = rec["tm2_uri"]
        ensure_node(node_id, "Disease",
                    canonical_iast=lemma, sanskrit=lemma,
                    english_rubric=rec.get("tm2_title_en"),
                    tm2_match_method=rec["matched_via"],
                    match_confidence=rec.get("confidence"),
                    external=ext)
        tm2_index[lemma] = node_id

    # ── 4. Walk formulas ──
    ing_lex   = inputs["ingredients_lex"]
    prose_lex = inputs["prose_lex"]

    for fobj in inputs["formulas"]:
        e = fobj["entry"]
        register = fobj["source_register"]
        source_doc = fobj["source_doc"]
        batch = fobj["batch"]
        num = e.get("අංකය")
        if num is None:
            continue

        # Formulation IDs are namespaced by batch to avoid collisions
        # (Vol I entry numbers reset per 50-page batch).
        f_id = f"formula:{batch}/{num}"
        name_sa = nfc(e.get("යෝග නාමය") or "")
        provenance = {"source_doc": source_doc, "source_record_id": str(num),
                      "register": register}

        ensure_node(f_id, "Formulation",
                    name_si=name_sa, sanskrit=name_sa,
                    source_register=register,
                    source_page=e.get("source_page"),
                    provenance=provenance)

        # 4a. IS_TYPE — from name suffix
        prep = detect_prep_type(name_sa)
        if prep:
            add_edge("IS_TYPE", f_id, f"prep:{prep}",
                     provenance=provenance, source="name_suffix")

        # 4b. CONTAINS — only Vol I has structured ingredient lists
        plant_ids_in_formula = set()
        if register == "tabular":
            for ing in (e.get("යෝගය") or []):
                surf = nfc((ing.get("ද්‍රව්‍යය") or "").strip())
                if not surf:
                    continue
                qty_text = (ing.get("ප්‍රමාණය") or "").strip()
                grams = ing.get("ග්‍රෑ") or 0.0
                kind, internal, lemma, gloss, method = resolve_ingredient(surf, ing_lex)
                unresolved = False
                if not internal:
                    # No Sanskrit lemma; treat as a Plant node keyed on the
                    # NFC-normalised Sinhala surface form, explicitly flagged
                    # as unresolved.
                    internal = f"plant:_si_{slug(surf)}"
                    kind = "Plant"
                    lemma = None
                    unresolved = True
                node = ensure_node(internal, kind,
                                   canonical_si=surf if not lemma else None,
                                   canonical_iast=lemma,
                                   sanskrit=lemma,
                                   gloss=(gloss or "")[:200],
                                   is_unresolved=unresolved or None)
                if kind == "Plant" and lemma and gloss:
                    attach_powo_external(node, lemma, gloss)
                add_edge("CONTAINS", f_id, internal,
                         parts=1 if not grams else None,
                         quantity_text=qty_text or None,
                         quantity_unit="parts" if not grams else "gram",
                         quantity_grams=grams if grams else None,
                         resolver_method=method,
                         provenance={**provenance,
                                     "ingredient_surface": surf})
                if kind == "Plant":
                    plant_ids_in_formula.add(internal)

        # 4c. DOSED_WITH — scan the anupāna text for known vehicles
        anupana = nfc(e.get("අනුපාන") or "")
        seen_vehicles = []
        for phrase, (iast, _english) in VEHICLE_HINTS.items():
            if phrase in anupana:
                v_id = f"vehicle:{slug(iast)}"
                if v_id not in seen_vehicles:
                    add_edge("DOSED_WITH", f_id, v_id,
                             provenance={**provenance, "matched_phrase": phrase})
                    seen_vehicles.append(v_id)

        # 4d. TREATS — tokenize prayoga, match each token against prose_lex
        #              + TM2 mapping
        prayoga = nfc(e.get("ප්‍රයෝග") or "")
        if prayoga:
            seen_diseases = set()
            for tok in prayoga.split():
                tok = nfc(tok.strip(" ,.;:!?\"\'"))
                rec = prose_lex.get(tok)
                if not rec:
                    continue
                for w in rec.get("words", []):
                    lemma = w.get("lemma")
                    if not lemma or w.get("method") != "direct":
                        continue
                    if lemma in tm2_index:
                        d_id = tm2_index[lemma]
                        if d_id in seen_diseases:
                            continue
                        seen_diseases.add(d_id)
                        add_edge("TREATS", f_id, d_id,
                                 evidence_level="canonical_text",
                                 provenance={**provenance,
                                             "matched_lemma": lemma,
                                             "matched_surface": tok})

        # 4e. CO_OCCURS — record plant-pairs for this formula
        for a, b in combinations(sorted(plant_ids_in_formula), 2):
            co_pairs[(a, b)] += 1

    # 5. Emit CO_OCCURS edges above min threshold; cap at max
    sorted_pairs = sorted(co_pairs.items(), key=lambda x: -x[1])
    if max_cooccurrence:
        sorted_pairs = sorted_pairs[:max_cooccurrence]
    for (a, b), n in sorted_pairs:
        if n < min_cooccurrence:
            break
        add_edge("CO_OCCURS", a, b, count=n,
                 confidence=min(1.0, n / 10),
                 provenance={"computed_from": "ingredient_co_occurrence"})

    return nodes, edges


# ── exporters ────────────────────────────────────────────────────────────────
def export_jsonld(nodes, edges, out_path):
    graph = []
    for n in nodes.values():
        item = {"@id": n["id"], "@type": n["type"]}
        for k, v in n.items():
            if k in ("id", "type") or v is None or v == "":
                continue
            item[k] = v
        graph.append(item)
    for e in edges:
        item = {"@type": e["type"], "from": e["from"], "to": e["to"]}
        for k, v in e.items():
            if k in ("type", "from", "to") or v is None:
                continue
            item[k] = v
        graph.append(item)
    doc = {
        "@context": "https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp/docs/context.jsonld",
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "built_at": now_iso(),
        "@graph": graph,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def export_cypher(nodes, edges, out_path):
    lines = ["// Sinhala Traditional Medicine KG — Neo4j Cypher export",
             f"// schema v{SCHEMA_VERSION}  extractor {EXTRACTOR_VERSION}  built {now_iso()}",
             ""]
    # Index for fast MERGE
    for ntype in sorted({n["type"] for n in nodes.values()}):
        lines.append(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{ntype}) REQUIRE n.id IS UNIQUE;")
    lines.append("")
    for n in nodes.values():
        props = {k: v for k, v in n.items() if k not in ("type",)
                 and v not in (None, "", [], {})}
        prop_str = ", ".join(
            f"{k}: {json.dumps(v, ensure_ascii=False)}"
            for k, v in props.items()
        )
        lines.append(f"MERGE (n:{n['type']} {{id: {json.dumps(n['id'])}}}) "
                     f"SET n += {{{prop_str}}};")
    lines.append("")
    for e in edges:
        props = {k: v for k, v in e.items() if k not in ("type", "from", "to")
                 and v not in (None, "", [], {})}
        prop_str = ", ".join(
            f"{k}: {json.dumps(v, ensure_ascii=False)}"
            for k, v in props.items()
        )
        lines.append(
            f"MATCH (a {{id: {json.dumps(e['from'])}}}), "
            f"(b {{id: {json.dumps(e['to'])}}}) "
            f"MERGE (a)-[r:{e['type']} {{{prop_str}}}]->(b);"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def export_turtle(nodes, edges, out_path):
    prefix = "https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp"
    lines = [
        f"@prefix nl: <{prefix}/ns/> .",
        f"@prefix ent: <{prefix}/id/> .",
        f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"# Sinhala Traditional Medicine KG — schema v{SCHEMA_VERSION}",
        f"# extractor: {EXTRACTOR_VERSION}   built: {now_iso()}",
        "",
    ]

    def iri(internal_id):
        return f"ent:{slug(internal_id).replace(':', '__')}"

    def lit(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return json.dumps(v)
        return json.dumps(str(v), ensure_ascii=False)

    for n in nodes.values():
        lines.append(f"{iri(n['id'])} a nl:{n['type']} ;")
        prop_lines = []
        for k, v in n.items():
            if k in ("id", "type") or v in (None, "", [], {}):
                continue
            if isinstance(v, dict):
                continue   # nested provenance/external — left out of turtle for brevity
            if isinstance(v, list):
                vals = ", ".join(lit(x) for x in v if x)
                if vals:
                    prop_lines.append(f"    nl:{k} {vals}")
            else:
                prop_lines.append(f"    nl:{k} {lit(v)}")
        lines.append(" ;\n".join(prop_lines) + " .\n" if prop_lines else " .\n")
    for e in edges:
        lines.append(f"{iri(e['from'])} nl:{e['type']} {iri(e['to'])} .")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_report(nodes, edges):
    node_counts = Counter(n["type"] for n in nodes.values())
    edge_counts = Counter(e["type"] for e in edges)

    plants = [n for n in nodes.values() if n["type"] == "Plant"]
    plant_resolved = [n for n in plants if not n.get("is_unresolved")]
    plant_unresolved = [n for n in plants if n.get("is_unresolved")]
    plant_with_powo = sum(1 for n in plants
                          if (n.get("external") or {}).get("powo_lsid"))
    plant_with_latin = sum(1 for n in plants if n.get("latin_binomial"))
    diseases = [n for n in nodes.values() if n["type"] == "Disease"]
    disease_with_tm2 = sum(1 for n in diseases
                           if (n.get("external") or {}).get("icd11_tm2"))

    return {
        "schema_version":    SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "built_at":          now_iso(),
        "nodes": {
            "total":   sum(node_counts.values()),
            "by_type": dict(node_counts),
        },
        "edges": {
            "total":   len(edges),
            "by_type": dict(edge_counts),
        },
        "plant_resolution": {
            "Plant_resolved_to_sanskrit":     len(plant_resolved),
            "Plant_unresolved_sinhala_only":  len(plant_unresolved),
            "Plant_total":                    len(plants),
            "note": ("Unresolved plant nodes are Sinhala surface forms that "
                     "the resolver did not map to a Sanskrit lemma — typically "
                     "tadbhava or vernacular terms awaiting R3/R4 lexicons."),
        },
        "external_id_coverage": {
            "Plant_with_POWO_LSID":          plant_with_powo,
            "Plant_with_latin_name":         plant_with_latin,
            "Plant_with_POWO_pct_of_resolved": (
                round(100 * plant_with_powo / max(len(plant_resolved), 1), 1)
            ),
            "Disease_with_ICD11_TM2":        disease_with_tm2,
            "Disease_total":                 len(diseases),
        },
    }


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(here / "knowledge_graph"))
    ap.add_argument("--max-cooccurrence", type=int, default=200)
    ap.add_argument("--min-cooccurrence", type=int, default=3)
    ap.add_argument("--no-yogamalawa", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading inputs…")
    inputs = load_inputs(here, include_yogamalawa=not args.no_yogamalawa)
    print(f"  formulas: {len(inputs['formulas'])}")
    print(f"  ingredient lexicon entries: {len(inputs['ingredients_lex'])}")
    print(f"  POWO records: {len(inputs['powo'])}")
    print(f"  TM2 records:  {len(inputs['tm2'])}")

    print("Building KG…")
    nodes, edges = build_kg(inputs,
                            max_cooccurrence=args.max_cooccurrence,
                            min_cooccurrence=args.min_cooccurrence)

    print(f"  nodes: {len(nodes)}")
    print(f"  edges: {len(edges)}")

    print("Exporting…")
    export_jsonld(nodes, edges, out_dir / "kg.jsonld")
    export_cypher(nodes, edges, out_dir / "kg.cypher")
    export_turtle(nodes, edges, out_dir / "kg.ttl")

    report = build_report(nodes, edges)
    (out_dir / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  wrote {out_dir}/kg.jsonld")
    print(f"  wrote {out_dir}/kg.cypher")
    print(f"  wrote {out_dir}/kg.ttl")
    print(f"  wrote {out_dir}/build_report.json")
    print()
    print("=== KG build report ===")
    print(f"  Nodes by type:")
    for k, v in sorted(report["nodes"]["by_type"].items(), key=lambda x: -x[1]):
        print(f"    {k:24s}  {v:6d}")
    print(f"  Edges by type:")
    for k, v in sorted(report["edges"]["by_type"].items(), key=lambda x: -x[1]):
        print(f"    {k:24s}  {v:6d}")
    print(f"  Plant resolution:")
    for k, v in report["plant_resolution"].items():
        if k == "note": continue
        print(f"    {k:32s}  {v}")
    print(f"  External-ID coverage:")
    for k, v in report["external_id_coverage"].items():
        print(f"    {k:32s}  {v}")


if __name__ == "__main__":
    main()

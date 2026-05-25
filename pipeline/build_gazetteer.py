"""
build_gazetteer.py
──────────────────
Block A of the prose-extraction pipeline (see docs/curious-inventing-eagle.md
and docs/literature_survey.md §5.6).

Merge every closed-vocabulary reference list the project has built into ONE
flat Sinhala-surface → {types, ids, …} lookup table, the foundation for the
gazetteer pre-annotation stage (distant supervision) and for the Block-C span
labeller's Aho-Corasick longest-match.

INPUTS (read-only, from data/lexicons/)
  materia_medica.json        771 substances → Ingredient (plant/mineral/animal_origin)
  pratinidhi_lookup.json     lhs_alt_si (Sinhala paraphrase of a Sanskrit headword)
                             → Ingredient  [NOT rhs_si — those are *substitutes*]
  mahakashaya_groups.json    substances → Ingredient ; gaṇa names → PharmacologicalProperty
  unit_equivalences.json     symbols (+ aliases) → Unit
  indication_icd11_tm2.json  + prose_lexicon.json → Indication (Sinhala surface whose
                             resolved Sanskrit lemma maps to an ICD-11 TM2 code)
  botanical_powo.json        Latin binomials (kept in a SEPARATE latin index, not by_surface)
  VEHICLE_HINTS              (knowledge_graph/build.py) → Vehicle
  PREP_SUFFIXES              (knowledge_graph/build.py) → Preparation (suffix-match)
  LABEL_TO_STATE             (pipeline/extract_pharma_v4.py) → FieldLabel

OUTPUT  data/lexicons/gazetteer.json
  {
    "metadata": {...},
    "by_surface": { "<nfc surface>": {
        "types":   ["Vehicle","Ingredient"],   # all candidate schema types
        "primary": "Vehicle",                    # by SPECIFICITY priority
        "ids":     {"Vehicle":"vehicle:madhu", "Ingredient":"animal:_si_..."},
        "sources": ["VEHICLE_HINTS","materia_medica"],
        "subtype": "animal_origin"               # when known
    }, ... },
    "by_type":     { "Ingredient":[...], "Unit":[...], ... },
    "ordered_keys": [...],   # surfaces sorted by length DESC for greedy longest-match
    "suffixes":     [{"si":"චූර්ණය","iast":"cūrṇa","type":"Preparation"}, ...],
    "field_labels": {"යෝගය":"YOGAYA", ...},
    "latin_binomials": {"<binomial>": {"powo_lsid":..., "family":...}, ...}
  }

USAGE
  python build_gazetteer.py
  python build_gazetteer.py --show කලං     # debug one surface form
"""
from __future__ import annotations
import argparse
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# Import the in-code constants from their source-of-truth files (stdlib-only
# modules, so importing has no heavy side effects).
HERE = Path(__file__).resolve().parent          # …/pipeline/
REPO = HERE.parent                              # …/sinhala-traditional-medicine-nlp/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "knowledge_graph"))
from extract_pharma_v4 import LABEL_TO_STATE                       # noqa: E402
from build import VEHICLE_HINTS, PREP_SUFFIXES                     # noqa: E402

EXTRACTOR_VERSION = "gazetteer_v1"
LEX = REPO / "data" / "lexicons"

# Schema-type specificity priority (higher index = wins as the primary type
# on a surface-form collision). Closed, unambiguous sets rank above the large
# open ingredient set; substances that are also vehicles surface both types.
TYPE_PRIORITY = ["Indication", "PharmacologicalProperty", "Ingredient",
                 "Vehicle", "Unit", "FieldLabel"]

# Vehicle lemmas that are animal-origin (so their node id is animal:*, matching
# the KG builder's convention).
ANIMAL_VEHICLE_LEMMAS = {"madhu", "ghṛta", "kṣīra"}

MM_SECTION_PREFIX = {"plant": "plant", "mineral": "min", "animal_origin": "animal"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def slug(s: str) -> str:
    return nfc(s).replace(" ", "_").replace("/", "_").replace("‍", "")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def jload(name: str) -> dict:
    p = LEX / name
    return json.load(open(p, encoding="utf-8")) if p.exists() else {}


class Gazetteer:
    """Accumulates surface → candidate (type, id, source) records."""

    def __init__(self):
        self.by_surface: dict[str, dict] = {}

    def add(self, surface: str, schema_type: str, node_id: str,
            source: str, subtype: str | None = None):
        surface = nfc(surface).strip()
        if len(surface) < 2:
            return
        rec = self.by_surface.setdefault(surface, {
            "types": [], "ids": {}, "sources": [], "subtype": None,
        })
        if schema_type not in rec["types"]:
            rec["types"].append(schema_type)
        rec["ids"].setdefault(schema_type, node_id)
        if source not in rec["sources"]:
            rec["sources"].append(source)
        if subtype and not rec["subtype"]:
            rec["subtype"] = subtype

    def finalise(self):
        for rec in self.by_surface.values():
            # primary = highest-priority type present
            rec["primary"] = max(
                rec["types"],
                key=lambda t: TYPE_PRIORITY.index(t) if t in TYPE_PRIORITY else -1,
            )
        return self.by_surface


def build():
    g = Gazetteer()

    # 1. Materia medica → Ingredient (plant / mineral / animal_origin)
    mm = jload("materia_medica.json")
    n_mm = 0
    for surf, recs in (mm.get("by_section") or {}).items():
        pass  # by_section is keyed by section → list; use by_sinhala instead
    for surf, rec in (mm.get("by_sinhala") or {}).items():
        section = rec.get("section")
        prefix = MM_SECTION_PREFIX.get(section, "plant")
        g.add(surf, "Ingredient", f"{prefix}:_si_{slug(surf)}",
              "materia_medica", subtype=section)
        n_mm += 1

    # 2. Pratinidhi — lhs_alt_si (Sinhala paraphrase of a Sanskrit headword).
    #    The Sinhala surface IS an ingredient; record the Sanskrit headword as
    #    a cross-reference so Module C / the resolver can bind the lemma.
    pr = jload("pratinidhi_lookup.json")
    n_pr = 0
    for e in (pr.get("entries") or []):
        alt = e.get("lhs_alt_si")
        if not alt:
            continue
        g.add(alt, "Ingredient", f"plant:_si_{slug(alt)}", "pratinidhi")
        # attach the Sanskrit cross-ref on the record
        rec = g.by_surface.get(nfc(alt).strip())
        if rec is not None:
            rec.setdefault("pratinidhi_sanskrit_si", e.get("lhs_si"))
        n_pr += 1

    # 3. Mahā-kaṣāya — substances → Ingredient ; gaṇa names → PharmacologicalProperty
    mk = jload("mahakashaya_groups.json")
    n_mk_subst = n_mk_gana = 0
    for v in (mk.get("vargas") or []):
        for gana in v.get("ganas", []):
            gname = gana.get("gana_name_si")
            if gname:
                g.add(gname, "PharmacologicalProperty",
                      f"prop:karma:{slug(gname)}", "mahakashaya")
                n_mk_gana += 1
            for s in gana.get("substances", []):
                g.add(s, "Ingredient", f"plant:_si_{slug(s)}", "mahakashaya")
                n_mk_subst += 1

    # 4. Units — symbols + aliases → Unit
    ue = jload("unit_equivalences.json")
    n_unit = 0
    for sym, meta in (ue.get("symbols") or {}).items():
        iast = meta.get("iast", slug(sym))
        for alias in [sym] + list(meta.get("aliases") or []):
            g.add(alias, "Unit", f"unit:{iast}", "unit_equivalences")
            n_unit += 1

    # 5. Vehicles (VEHICLE_HINTS) → Vehicle
    n_veh = 0
    for phrase, (iast, _en) in VEHICLE_HINTS.items():
        prefix = "animal" if iast in ANIMAL_VEHICLE_LEMMAS else "vehicle"
        node_id = f"{prefix}:{slug(iast)}" if prefix == "animal" else f"vehicle:{slug(iast)}"
        g.add(phrase, "Vehicle", node_id, "VEHICLE_HINTS")
        n_veh += 1

    # 6. Field labels (LABEL_TO_STATE) → FieldLabel
    for label in LABEL_TO_STATE:
        g.add(label, "FieldLabel", f"field:{LABEL_TO_STATE[label]}", "LABEL_TO_STATE")

    # 7. Indications — Sinhala prose surfaces whose resolved lemma maps to TM2.
    tm2 = jload("indication_icd11_tm2.json")
    prose = jload("prose_lexicon.json")
    tm2_lemmas = {k for k, v in tm2.items() if (v or {}).get("matched_via")}
    n_ind = 0
    for surf, rec in (prose.items() if isinstance(prose, dict) else []):
        for w in (rec.get("words") or []):
            lemma = w.get("lemma")
            if lemma and lemma in tm2_lemmas and w.get("method") == "direct":
                code = (tm2.get(lemma) or {}).get("tm2_code")
                g.add(surf, "Indication", f"disease:{slug(lemma)}", "icd11_tm2")
                r = g.by_surface.get(nfc(surf).strip())
                if r is not None:
                    r.setdefault("icd11_tm2", code)
                n_ind += 1
                break

    by_surface = g.finalise()

    # by_type index
    by_type: dict[str, list] = {}
    for surf, rec in by_surface.items():
        for t in rec["types"]:
            by_type.setdefault(t, []).append(surf)

    # ordered_keys: length DESC then alphabetical (deterministic) for greedy
    # longest-match scanning.
    ordered_keys = sorted(by_surface, key=lambda s: (-len(s), s))

    # Suffixes (matched by suffix, not exact) and field labels (exact).
    suffixes = [{"si": si, "iast": iast, "type": "Preparation",
                 "id": f"prep:{iast}"} for si, iast in PREP_SUFFIXES]

    # Latin binomials (separate index — Latin, not Sinhala, so not in by_surface)
    powo = jload("botanical_powo.json")
    latin = {}
    for binom, rec in (powo.items() if isinstance(powo, dict) else []):
        if rec.get("powo_lsid"):
            latin[binom] = {"powo_lsid": rec.get("powo_lsid"),
                            "modern_accepted_name": rec.get("modern_accepted_name"),
                            "family": rec.get("family")}

    return {
        "metadata": {
            "extractor_version": EXTRACTOR_VERSION,
            "built_at": now_iso(),
            "n_surface_forms": len(by_surface),
            "n_by_type": {t: len(v) for t, v in sorted(by_type.items())},
            "n_suffixes": len(suffixes),
            "n_field_labels": len(LABEL_TO_STATE),
            "n_latin_binomials": len(latin),
            "counts_by_source": {
                "materia_medica": n_mm, "pratinidhi": n_pr,
                "mahakashaya_substances": n_mk_subst, "mahakashaya_ganas": n_mk_gana,
                "units": n_unit, "vehicles": n_veh, "indications": n_ind,
            },
            "note": ("Closed-vocabulary gazetteer for Sinhala-surface entity "
                     "identification (distant-supervision stage 1). Each surface "
                     "carries all candidate schema types; the span labeller picks "
                     "by field context. Latin binomials are a separate index."),
        },
        "by_surface": by_surface,
        "by_type": {t: sorted(v) for t, v in by_type.items()},
        "ordered_keys": ordered_keys,
        "suffixes": suffixes,
        "field_labels": dict(LABEL_TO_STATE),
        "latin_binomials": latin,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(LEX / "gazetteer.json"))
    ap.add_argument("--show", default=None, help="print the record for one surface form")
    args = ap.parse_args()

    result = build()

    if args.show:
        key = nfc(args.show).strip()
        rec = result["by_surface"].get(key)
        print(f"{key!r}: {json.dumps(rec, ensure_ascii=False, indent=2)}")
        return

    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    m = result["metadata"]
    print(f"✓ wrote {args.out}")
    print(f"  surface forms: {m['n_surface_forms']}")
    print(f"  by type:       {m['n_by_type']}")
    print(f"  suffixes:      {m['n_suffixes']}   field labels: {m['n_field_labels']}"
          f"   latin binomials: {m['n_latin_binomials']}")
    print(f"  by source:     {m['counts_by_source']}")
    # show a couple of multi-type collisions as a sanity check
    multi = [(s, r["types"]) for s, r in result["by_surface"].items()
             if len(r["types"]) > 1]
    print(f"  multi-type surfaces: {len(multi)}  e.g. "
          + "; ".join(f"{s}={'/'.join(t)}" for s, t in multi[:4]))


if __name__ == "__main__":
    main()

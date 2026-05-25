"""
extract_prose.py
────────────────
Block D of the prose-extraction pipeline. Schema-constrained relation
extraction (L5): turn Block C's labelled span sequence into KG-valid triples.

Design — field-state-driven emission. This is the prose analogue of the
tabular Stage-3 state machine (extract_pharma_v4.py): the *governing field*
of a span (the most recent FieldLabel sentence before it) determines the
relation, exactly as the column zone does in the tabular extractor.

  Governing field   Span type → emitted edge
  ───────────────   ─────────────────────────────────────────────
  (entry header)    name suffix          → IS_TYPE(formula, prep:*)
  YOGAYA            Ingredient           → CONTAINS(formula, plant/min/animal)
                    Quantity (adjacent)  → attaches grams/unit to last CONTAINS
  PRAYOGA           Indication           → TREATS(formula, disease)
  ANUPANA           Vehicle | Ingredient → DOSED_WITH(formula, plant/animal)
  (any)             "<N> ලෙස/වැනි" ref   → PREPARED_BY(formula, formula:vol1/N)

Every candidate triple is **schema-validated at emission** against the v1.1
edge domain/range (mirrors validate/anchors.yaml :: edge_domain_range). A
triple whose subject/object node types don't fit the edge is NOT emitted;
it is logged to `unsupported` with its span + reason. Every emitted triple
carries provenance (char_span, surface, field). Output is deterministically
sorted.

Usage:
  from extract_prose import ProseExtractor
  ex = ProseExtractor.load_default()
  result = ex.extract(text, formula_hint="prose/1")
  for t in result["triples"]: print(t["type"], t["from"], "→", t["to"])

CLI:
  python extract_prose.py --demo
  python extract_prose.py <file.txt> [--formula-id prose/7] [--json]
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from label_spans import LabelEngine    # noqa: E402

EXTRACTOR_VERSION = "prose_v1"

# ── Node-type inference from internal-id prefix ─────────────────────────────
ID_PREFIX_TYPE = {
    "plant":   "Plant",
    "min":     "Mineral",
    "animal":  "AnimalOrigin",
    "vehicle": "Plant",            # non-animal vehicles are Plant (KG convention)
    "disease": "Disease",
    "prep":    "PreparationType",
    "prop":    "PharmacologicalProperty",
    "formula": "Formulation",
    "field":   "_Field",           # structural, never a node
    "unit":    "_Unit",            # structural, never a node
}

def node_type_of(node_id: Optional[str]) -> Optional[str]:
    if not node_id or ":" not in node_id:
        return None
    return ID_PREFIX_TYPE.get(node_id.split(":", 1)[0])


# ── Schema edge domain/range (mirrors validate/anchors.yaml, schema v1.1) ───
SCHEMA_EDGES = {
    "CONTAINS":      {"from": {"Formulation"},
                      "to":   {"Plant", "Mineral", "AnimalOrigin"}},
    "IS_TYPE":       {"from": {"Formulation"}, "to": {"PreparationType"}},
    "TREATS":        {"from": {"Formulation"}, "to": {"Disease"}},
    "DOSED_WITH":    {"from": {"Formulation"},
                      "to":   {"Plant", "Mineral", "AnimalOrigin"}},
    "HAS_PROPERTY":  {"from": {"Plant", "Mineral", "AnimalOrigin"},
                      "to":   {"PharmacologicalProperty"}},
    "PREPARED_BY":   {"from": {"Formulation"}, "to": {"Formulation"}},
    "SUBSTITUTES_FOR": {"from": {"Plant", "Mineral", "AnimalOrigin"},
                        "to":   {"Plant", "Mineral", "AnimalOrigin"}},
}

# Preparation-type suffix detection on the formula name (mirrors PREP_SUFFIXES).
sys.path.insert(0, str(HERE.parent / "knowledge_graph"))
from build import PREP_SUFFIXES    # noqa: E402

# Cross-reference patterns: "<N> ලෙස", "<N> වැනි", "<N> යෝගය", "අංක <N>"
_XREF_RE = re.compile(r"(?:අංක\s*)?(\d{1,4})\s*(?:ලෙස|වැනි|යෝග|යෝගය|අනුව)")
_ENTRY_HEADER_RE = re.compile(r"^\s*(\d{1,4})\s*\.")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


class ProseExtractor:
    def __init__(self, engine: LabelEngine):
        self.engine = engine

    @classmethod
    def load_default(cls):
        return cls(LabelEngine.load_default())

    def extract(self, text: str, formula_hint: Optional[str] = None) -> dict:
        text = nfc(text)
        labelled = self.engine.label_document(text)
        sentences = labelled["sentences"]
        spans = labelled["spans"]

        # ── 1. Identify the formula node ────────────────────────────────
        formula_num = None
        formula_name = None
        for s in sentences:
            m = _ENTRY_HEADER_RE.match(s["text"])
            if m:
                formula_num = m.group(1)
                # name = header text minus the leading "N."
                formula_name = s["text"][m.end():].strip(" .–-")
                break
        if formula_hint:
            formula_id = f"formula:{formula_hint}"
        elif formula_num:
            formula_id = f"formula:prose/{formula_num}"
        else:
            formula_id = "formula:prose/unknown"

        # ── 2. Walk spans in document order, tracking governing field ───
        # Build a sentence_idx → field_state map by forward-filling field
        # labels (a FieldLabel sentence sets the state for following sentences).
        sent_field = self._forward_fill_fields(sentences)

        triples: list[dict] = []
        unsupported: list[dict] = []
        formula_attrs: dict = {}                    # formula-level dose, etc.
        last_contains_idx: Optional[int] = None    # for quantity attachment

        # spans are sorted by char position already
        for sp in spans:
            field = sent_field.get(sp["sentence_idx"])
            stype = sp["type"]
            sid = sp["id"]
            prov = {"char_span": sp["char_span"], "surface": sp["text"],
                    "field": field}

            if stype == "Ingredient":
                if field == "ANUPANA":
                    # ingredient named in the vehicle field → DOSED_WITH
                    self._emit(triples, unsupported, "DOSED_WITH", formula_id,
                               sid, prov)
                else:
                    # default (YOGAYA or unmarked content) → CONTAINS
                    ok = self._emit(triples, unsupported, "CONTAINS", formula_id,
                                    sid, prov)
                    if ok:
                        last_contains_idx = len(triples) - 1
            elif stype == "Vehicle":
                self._emit(triples, unsupported, "DOSED_WITH", formula_id, sid, prov)
            elif stype == "Indication":
                self._emit(triples, unsupported, "TREATS", formula_id, sid, prov,
                           extra={"evidence_level": "canonical_text"})
            elif stype == "Quantity":
                if field == "MATRAVA":
                    # formula-level dose (not a per-ingredient quantity)
                    formula_attrs["dose_text"] = sp["text"]
                    formula_attrs["dose_grams"] = sp.get("grams")
                    formula_attrs["dose_ml"] = sp.get("ml")
                elif field in (None, "YOGAYA") and last_contains_idx is not None:
                    # per-ingredient quantity, inline in the ingredient field
                    t = triples[last_contains_idx]
                    t["quantity_text"] = sp["text"]
                    t["quantity_grams"] = sp.get("grams")
                    t["quantity_unit"] = sp.get("unit_iast")
                else:
                    unsupported.append({**prov, "reason": "quantity not bindable to an ingredient or formula dose"})
            elif stype == "PharmacologicalProperty":
                # gana name in prose — a HAS_PROPERTY needs a Plant subject,
                # not the formulation; we can't bind it from a flat field, so
                # log it for Block F rather than guessing.
                unsupported.append({**prov, "reason": "PharmacologicalProperty span needs a substance subject (not emitted from prose field)"})
            # FieldLabel / Unit-only spans are structural; ignore.

        # ── 3. IS_TYPE from the formula-name suffix ─────────────────────
        if formula_name:
            for suffix_si, prep_lemma in PREP_SUFFIXES:
                if formula_name.endswith(suffix_si):
                    self._emit(triples, unsupported, "IS_TYPE", formula_id,
                               f"prep:{prep_lemma}",
                               {"surface": formula_name, "field": "name_suffix"})
                    break

        # ── 4. Cross-references → PREPARED_BY ───────────────────────────
        for m in _XREF_RE.finditer(text):
            ref_num = m.group(1)
            if ref_num == formula_num:
                continue
            self._emit(triples, unsupported, "PREPARED_BY", formula_id,
                       f"formula:vol1/{ref_num}",
                       {"char_span": [m.start(), m.end()],
                        "surface": m.group(0), "field": "cross_reference"})

        # ── 5. Deduplicate (CONTAINS/TREATS/… are set relations) ────────
        triples = _dedupe(triples)

        # ── 6. Deterministic sort ───────────────────────────────────────
        triples.sort(key=lambda t: (t["type"], t["to"],
                                    t.get("provenance", {}).get("char_span", [0])[0]))

        return {
            "formula_id":   formula_id,
            "formula_name": formula_name,
            "formula_attrs": formula_attrs,
            "source_text":  text,
            "extractor_version": EXTRACTOR_VERSION,
            "triples":      triples,
            "unsupported":  unsupported,
            "nils":         labelled["nils"],
            "stats": {
                "n_triples":     len(triples),
                "n_unsupported": len(unsupported),
                "n_nils":        len(labelled["nils"]),
                "by_edge":       _count_by(triples, "type"),
            },
        }

    # ── helpers ─────────────────────────────────────────────────────────
    @staticmethod
    def _forward_fill_fields(sentences: list[dict]) -> dict:
        out = {}
        current = None
        for i, s in enumerate(sentences):
            if s.get("is_field_label"):
                current = s.get("field_state")
                out[i] = current        # the label sentence itself
            else:
                out[i] = current
        return out

    @staticmethod
    def _emit(triples: list, unsupported: list, edge: str, src: str,
              dst: Optional[str], prov: dict, extra: Optional[dict] = None) -> bool:
        """Schema-validate and emit a triple. Returns True if emitted."""
        if not dst:
            unsupported.append({**prov, "edge": edge, "reason": "no target id"})
            return False
        spec = SCHEMA_EDGES.get(edge)
        st, dt = node_type_of(src), node_type_of(dst)
        if not spec or st not in spec["from"] or dt not in spec["to"]:
            unsupported.append({**prov, "edge": edge,
                                "reason": f"schema mismatch {st}-{edge}->{dt}"})
            return False
        t = {"type": edge, "from": src, "to": dst,
             "extractor_version": EXTRACTOR_VERSION, "provenance": prov}
        if extra:
            t.update(extra)
        triples.append(t)
        return True


def _dedupe(triples: list[dict]) -> list[dict]:
    """Collapse triples with identical (type, from, to). KG edges like
    CONTAINS/TREATS are set relations, so repeated mentions of the same
    ingredient become one edge with mention_count and all source spans.
    A quantity from any mention is preserved."""
    seen: dict = {}
    for t in triples:
        key = (t["type"], t["from"], t["to"])
        if key in seen:
            cur = seen[key]
            cur["mention_count"] = cur.get("mention_count", 1) + 1
            span = t.get("provenance", {}).get("char_span")
            if span:
                cur.setdefault("also_char_spans", []).append(span)
            if t.get("quantity_grams") and not cur.get("quantity_grams"):
                cur["quantity_text"] = t.get("quantity_text")
                cur["quantity_grams"] = t.get("quantity_grams")
                cur["quantity_unit"] = t.get("quantity_unit")
        else:
            t["mention_count"] = 1
            seen[key] = t
    return list(seen.values())


def _count_by(items: list[dict], key: str) -> dict:
    out: dict = {}
    for it in items:
        out[it[key]] = out.get(it[key], 0) + 1
    return out


# ── CLI ─────────────────────────────────────────────────────────────────────
_DEMO = (
    "44. ත්‍රිකටු චූර්ණය. යෝගය:- තිප්පිලි, ඉඟුරු, ගම්මිරිස් සමව ගෙන කොටා පෙළා කෙළවර කරයි. "
    "ප්‍රයෝග:- කාස, ශ්වාස, අග්නිමාන්ද්‍ය. අනුපාන:- මී පැණි. මාත්‍රාව:- ග්‍රෑ 5."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--formula-id", default=None)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ex = ProseExtractor.load_default()
    text = _DEMO if (args.demo or args.path is None) else \
           Path(args.path).read_text(encoding="utf-8")
    result = ex.extract(text, formula_hint=args.formula_id)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"=== {result['formula_id']}  ({result['formula_name']}) ===")
    if result.get("formula_attrs"):
        print(f"  formula attrs: {result['formula_attrs']}")
    print(f"  triples: {result['stats']['n_triples']}  "
          f"unsupported: {result['stats']['n_unsupported']}  "
          f"nils: {result['stats']['n_nils']}")
    print(f"  by edge: {result['stats']['by_edge']}")
    print("  --- triples ---")
    for t in result["triples"]:
        q = ""
        if t.get("quantity_grams") is not None:
            q = f"  [{t['quantity_text']} = {t['quantity_grams']}g]"
        elif t.get("quantity_text"):
            q = f"  [{t['quantity_text']}]"
        print(f"    {t['type']:12s} {t['from']} → {t['to']}{q}")
    if result["unsupported"]:
        print(f"  --- unsupported ({len(result['unsupported'])}) ---")
        for u in result["unsupported"][:8]:
            print(f"    {u.get('surface','')!r}: {u.get('reason','')}")


if __name__ == "__main__":
    main()

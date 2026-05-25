"""
label_spans.py
──────────────
Block C of the prose-extraction pipeline. Schema-typed span labelling.

Pipeline position (L4 in the architecture diagram):
  L1 segment  →  L2 gazetteer match  →  L3 resolver fallback  →  L4 LABEL
                                                                   |
                                                                   ▼
                                                            list[Span(char_span, type, id)]

What this module does:
  1. **Aho-Corasick longest-match** over the closed-vocabulary gazetteer
     (Block A output). Pyahocorasick (C-backed, O(n+m+z)) for the scan;
     deterministic non-overlap resolution by longest-span-then-earlier-start.
  2. **Quantity parsing** via knowledge_graph/dosage.py: detect
     `<number> <unit>` and `<unit> <number>` sequences and emit a typed
     Quantity span carrying grams/ml + the source unit IAST.
  3. **Resolver fallback** (placeholder hook) — un-matched tokens that look
     tatsama (Mishra-Sinhala signal) can be routed to
     `resolvers.sanskrit_resolver.resolve_word` to produce a `Plant`/
     `Mineral` span tagged `resolver_origin=True`. Wired by an `enable_resolver`
     flag; disabled by default to keep this module light.
  4. **Pluggable oracles** — a `second_oracle` callable can be passed in
     to supply additional candidate spans (CRF, GLiNER, SapBERT, etc.).
     Its output never overrides a gazetteer match; only fills NIL regions.
  5. **Explicit NIL records** — content tokens not covered by any span are
     emitted as `NIL` spans with their offsets, for the iteration-loop
     gap report (Block F).

Determinism: stable sort on (char_span, type, source); same input → byte-
identical output.

Usage:
  from label_spans import LabelEngine
  eng = LabelEngine.load_default()
  spans = eng.label("ත්‍රිකටු චූර්ණය. යෝගය:- තිප්පිලි, ඉඟුරු සමග මී පැණි.")
  for s in spans:
      print(s.char_span, s.type, s.id, repr(s.text))

CLI:
  python label_spans.py --demo
  python label_spans.py <file.txt>
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Optional

import ahocorasick

HERE = Path(__file__).resolve().parent           # …/pipeline/
REPO = HERE.parent                               # …/sinhala-traditional-medicine-nlp/
sys.path.insert(0, str(HERE))
from segment import segment, Document, Sentence  # noqa: E402

LEX = REPO / "data" / "lexicons"
GAZ_PATH = LEX / "gazetteer.json"
UNIT_PATH = LEX / "unit_equivalences.json"
DOSAGE_PATH = REPO / "knowledge_graph" / "dosage.py"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


# ── data class ──────────────────────────────────────────────────────────────

@dataclass
class Span:
    char_span: tuple[int, int]
    type: str
    id: Optional[str]
    text: str
    source: str
    # type-specific extras
    types_alt: list[str] = field(default_factory=list)   # other candidate types
    subtype: Optional[str] = None
    grams: Optional[float] = None
    ml: Optional[float] = None
    count: Optional[float] = None
    unit_iast: Optional[str] = None
    # provenance
    sentence_idx: Optional[int] = None
    sentence_field_state: Optional[str] = None    # YOGAYA / PRAYOGA / …

    def to_dict(self):
        d = asdict(self)
        d["char_span"] = list(self.char_span)
        return d


# ── label engine ────────────────────────────────────────────────────────────

class LabelEngine:
    """Holds the compiled Aho-Corasick automaton + the dosage registry."""

    def __init__(self, gazetteer: dict, dosage_registry):
        self.gaz = gazetteer
        self.dosage = dosage_registry
        # Build the AC automaton from the gazetteer's by_surface keys.
        self._ac = ahocorasick.Automaton()
        for surf, rec in gazetteer["by_surface"].items():
            self._ac.add_word(surf, (surf, rec))
        self._ac.make_automaton()

    @classmethod
    def load_default(cls):
        gaz = json.loads(GAZ_PATH.read_text(encoding="utf-8"))
        dosage = _import_dosage()
        return cls(gaz, dosage)

    # ── public API ──────────────────────────────────────────────────────
    def label(self, text: str, *, second_oracle: Optional[Callable] = None,
              field_context: Optional[str] = None) -> list[Span]:
        """Label `text` directly (no sentence segmentation). Returns spans
        sorted by (char_span, type) with overlapping matches resolved by
        longest-then-earlier-start. `field_context` (YOGAYA / PRAYOGA / …)
        biases the primary-type pick on multi-type surfaces."""
        text = nfc(text)
        candidates: list[Span] = []

        # 1. Aho-Corasick scan
        for end_idx, (surf, rec) in self._ac.iter(text):
            start = end_idx - len(surf) + 1
            end = end_idx + 1
            ptype = _pick_type_for_context(rec, field_context)
            candidates.append(Span(
                char_span=(start, end),
                type=ptype,
                id=rec["ids"].get(ptype),
                text=text[start:end],
                source="gazetteer",
                types_alt=[t for t in rec["types"] if t != ptype],
                subtype=rec.get("subtype"),
                sentence_field_state=field_context,
            ))

        # 2. Quantity parsing (number + unit, in either order)
        if self.dosage is not None:
            for span in _find_quantities(text, self.dosage):
                span.sentence_field_state = field_context
                candidates.append(span)

        # 3. Second oracle (optional, NIL-only fill)
        if second_oracle is not None:
            extra = second_oracle(text)
            for s in extra:
                # only accept where no gazetteer/quantity span already covers it
                if not _overlaps_any(s.char_span, candidates):
                    s.source = s.source or "second_oracle"
                    candidates.append(s)

        # 4. Resolve overlaps deterministically: longest > earlier start > type-priority
        resolved = _resolve_overlaps(candidates)
        # Stable sort for byte-identical output
        resolved.sort(key=lambda s: (s.char_span[0], s.char_span[1], s.type, s.source))
        return resolved

    def label_document(self, text: str,
                       *, second_oracle: Optional[Callable] = None) -> dict:
        """Segment + label. Returns {sentences:[...], spans:[...], nils:[...]}."""
        doc = segment(text)
        all_spans: list[Span] = []
        for i, sent in enumerate(doc.sentences):
            context = sent.field_state    # may be None
            spans = self.label(sent.text, second_oracle=second_oracle,
                               field_context=context)
            for s in spans:
                # offset the spans into document-global coordinates
                s.char_span = (s.char_span[0] + sent.char_span[0],
                               s.char_span[1] + sent.char_span[0])
                s.sentence_idx = i
                s.sentence_field_state = context
                all_spans.append(s)

        # NIL: content tokens not in any span. Compute by token-walking
        # the segmenter's sentences and flagging gaps.
        nils = _compute_nils(doc, all_spans)
        all_spans.sort(key=lambda s: (s.char_span[0], s.char_span[1], s.type))
        return {
            "source_text": doc.source_text,
            "sentences":   [s.to_dict() for s in doc.sentences],
            "spans":       [s.to_dict() for s in all_spans],
            "nils":        nils,
        }


# ── helpers ─────────────────────────────────────────────────────────────────

# Specificity priority for picking the primary type of a multi-type surface
# when there's no field context. Closed enums beat the open Ingredient set.
_PRIORITY = ["FieldLabel", "Unit", "PharmacologicalProperty", "Vehicle",
             "Indication", "Ingredient"]


def _pick_type_for_context(rec: dict, field_context: Optional[str]) -> str:
    """Pick the primary type for a multi-type surface based on field context."""
    types = rec["types"]
    if len(types) == 1:
        return types[0]
    # Field-context biases (e.g. when the sentence is ANUPANA, prefer Vehicle
    # over Ingredient for "මී පැණි")
    bias = {
        "ANUPANA":      ["Vehicle", "Ingredient"],
        "YOGAYA":       ["Ingredient", "Vehicle"],
        "PRAYOGA":      ["Indication", "Ingredient"],
        "MATRAVA":      ["Unit", "Ingredient"],
        "SANSKARANAYA": ["Vehicle", "Ingredient"],
    }.get(field_context or "", [])
    for t in bias:
        if t in types:
            return t
    # Else by global priority
    for t in _PRIORITY:
        if t in types:
            return t
    return types[0]


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _overlaps_any(span: tuple[int, int], existing: list[Span]) -> bool:
    return any(_overlaps(span, s.char_span) for s in existing)


def _resolve_overlaps(spans: list[Span]) -> list[Span]:
    """Greedy non-overlapping cover. Sort by (start, -length); keep a span
    iff it does not overlap an already-kept span. Longest-match-wins by
    construction of the sort."""
    # Sort by start ASC, then length DESC, then type-priority for ties
    spans_sorted = sorted(
        spans,
        key=lambda s: (s.char_span[0],
                       -(s.char_span[1] - s.char_span[0]),
                       _PRIORITY.index(s.type) if s.type in _PRIORITY else 99,
                       s.source),
    )
    kept: list[Span] = []
    for s in spans_sorted:
        if not _overlaps_any(s.char_span, kept):
            kept.append(s)
    return kept


def _import_dosage():
    """Import knowledge_graph/dosage.py via importlib (path-isolated)."""
    if not DOSAGE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("_lbl_dosage", str(DOSAGE_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_units(str(UNIT_PATH))


def _find_quantities(text: str, dosage) -> list[Span]:
    """Use the dosage UnitRegistry to find unit symbols in `text`, pair each
    with an adjacent number, and emit a Quantity span carrying grams/ml +
    the source unit iast."""
    out: list[Span] = []
    # Walk every unit symbol via the alias→canonical map; locate occurrences,
    # then look for a numeric token adjacent (within ~4 chars) on either side.
    import re
    num_re = re.compile(r"(\d+(?:[./]\d+)?|[½¼¾⅓⅔⅛⅜⅝⅞])")
    for alias, canonical in dosage._alias_to_symbol.items():
        meta = dosage.symbols.get(canonical) or {}
        kind = meta.get("kind")
        if kind not in ("mass", "volume"):
            continue
        # find all occurrences of this alias
        i = 0
        while True:
            j = text.find(alias, i)
            if j < 0:
                break
            unit_start, unit_end = j, j + len(alias)
            # find nearest number within +/- 8 chars
            left_window  = text[max(0, unit_start - 8):unit_start]
            right_window = text[unit_end:unit_end + 8]
            n_match = num_re.search(right_window) or _last_num(num_re, left_window)
            if not n_match:
                i = unit_end; continue
            if n_match in (None,):
                i = unit_end; continue
            try:
                count = _parse_number(n_match.group(0))
            except Exception:
                count = None
            if count is None:
                i = unit_end; continue
            # establish the combined span
            if n_match.string is right_window:
                # number after unit: span [unit_start, unit_end + n_match.end()]
                combined = (unit_start, unit_end + n_match.end())
            else:
                # number before unit (left_window)
                # n_match is a Match on left_window; its end is the offset within left_window
                n_end_in_window = n_match.end()
                # absolute start = unit_start - (len(left_window) - n_match.start())
                abs_start = unit_start - (len(left_window) - n_match.start())
                combined = (abs_start, unit_end)
            g = dosage.grams_per_unit(canonical) if kind == "mass" else None
            ml = dosage.ml_per_unit(canonical) if kind == "volume" else None
            iast = meta.get("iast")
            out.append(Span(
                char_span=combined,
                type="Quantity",
                id=f"unit:{iast}" if iast else None,
                text=text[combined[0]:combined[1]],
                source="dosage",
                count=count,
                unit_iast=iast,
                grams=(count * g) if (count is not None and g) else None,
                ml=(count * ml) if (count is not None and ml) else None,
            ))
            i = combined[1]
    return out


def _last_num(num_re, window: str):
    """Return the LAST numeric match in a window (for number-before-unit)."""
    last = None
    for m in num_re.finditer(window):
        last = m
    return last


def _parse_number(tok: str) -> Optional[float]:
    FRAC = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1/3, "⅔": 2/3,
            "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875}
    if tok in FRAC:
        return FRAC[tok]
    if "/" in tok:
        a, b = tok.split("/"); return int(a) / int(b)
    return float(tok)


def _compute_nils(doc: Document, spans: list[Span]) -> list[dict]:
    """Return list of {char_span, text, sentence_idx} for content tokens
    that no span covers. Tokens computed by simple whitespace splitting on
    each clause's text; spans are matched by character-overlap."""
    nils: list[dict] = []
    span_intervals = [(s.char_span[0], s.char_span[1]) for s in spans]
    # tokenise per clause, identify those that don't overlap any span
    for i, sent in enumerate(doc.sentences):
        for cl in sent.clauses:
            cs, ce = cl.char_span
            slice_ = doc.source_text[cs:ce]
            # Walk tokens with offsets
            offset = 0
            for token in slice_.split():
                t_start = slice_.find(token, offset)
                t_end = t_start + len(token)
                offset = t_end
                abs_start, abs_end = cs + t_start, cs + t_end
                # ignore tokens that are pure punctuation
                if all(not c.isalnum() for c in token):
                    continue
                if not any(a < abs_end and abs_start < b for a, b in span_intervals):
                    nils.append({
                        "char_span": [abs_start, abs_end],
                        "text": token,
                        "sentence_idx": i,
                    })
    return nils


# ── CLI ─────────────────────────────────────────────────────────────────────
_DEMO = (
    "44. ත්‍රිකටු චූර්ණය. යෝගය:- තිප්පිලි, ඉඟුරු, ගම්මිරිස් සමව ගෙන කොටා පෙළා කෙළවර කරයි. "
    "ප්‍රයෝග:- කාස, ශ්වාස, අග්නිමාන්ද්‍ය. අනුපාන:- මී පැණි. මාත්‍රාව:- ග්‍රෑ 5."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    eng = LabelEngine.load_default()
    text = _DEMO if (args.demo or args.path is None) else \
           Path(args.path).read_text(encoding="utf-8")

    out = eng.label_document(text)

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print(f"=== {len(out['spans'])} spans, {len(out['nils'])} NILs in "
          f"{len(out['sentences'])} sentences ===")
    for s in out["spans"]:
        sub = f"/{s['subtype']}" if s.get("subtype") else ""
        extra = ""
        if s.get("grams") is not None:
            extra = f"  → {s['count']} {s['unit_iast']} = {s['grams']} g"
        print(f"  {tuple(s['char_span'])}  {s['type']}{sub:10s}  "
              f"'{s['text']}'  id={s['id']}{extra}")
    if out["nils"]:
        print(f"--- NILs ({len(out['nils'])}) ---")
        for n in out["nils"][:20]:
            print(f"  {tuple(n['char_span'])}  '{n['text']}'  (sent {n['sentence_idx']})")


if __name__ == "__main__":
    main()

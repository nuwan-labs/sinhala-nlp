"""
segment.py
──────────
Block B of the prose-extraction pipeline. Sentence + clause segmentation
for Sinhala Ayurvedic prose, with char-span provenance.

The sinling library's `split_sentences` is too naive for the pharmacopoeia
register — it splits on `:-` into stray "- ..." tokens and breaks the
field-label structure (`ප්‍රයෝග :- කාස, …`). Block B implements a
register-aware segmenter that:

  1. NFC-normalises the input (ZWJ-preserving).
  2. Splits into SENTENCES at:
       • Sinhala daṇḍa (`U+0964`, U+0965) / `|` / `.` followed by space/EOL
       • literal `:-` (the pharmacopoeia's field-label separator;
         the boundary is kept so a `<label>:-<content>` line yields two
         sentences carrying the relation between them)
       • newline + numbered-marker (`1.`, `1)`, `(1)`) at column 0 —
         these introduce a NEW entry.
  3. Splits each sentence into CLAUSES at:
       • comma (`,`)
       • the literal `=` (substance-name equation marker — pratinidhi-style)
  4. Tags each sentence with `is_field_label` when it consists of just a
     known LABEL_TO_STATE key (so Block C / Block D can pair it with the
     following content sentence).
  5. Tracks `char_span = [start, end)` in the NFC-normalised source for
     every sentence and clause — the foundation of provenance.

Deterministic by construction (regex + linear scan), pure-stdlib, with
sinling only used for word tokenisation when callers ask for it.

Usage:
  from segment import segment
  doc = segment("තිප්පිලි, ඉඟුරු, ගම්මිරිස් සමව ගෙන කොටා පෙළා කෙළවර කරයි.")
  for s in doc.sentences:
      print(s.char_span, s.text)
      for c in s.clauses: print("  ", c.char_span, c.text)

CLI:
  python segment.py <file.txt>           # print segmentation as JSON
  python segment.py --demo               # run on a built-in example
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Field-label keys from extract_pharma_v4 (pharmacopoeia structural markers).
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract_pharma_v4 import LABEL_TO_STATE   # noqa: E402

# ── data classes ────────────────────────────────────────────────────────────

@dataclass
class Clause:
    text: str
    char_span: tuple[int, int]

    def to_dict(self):
        return {"text": self.text, "char_span": list(self.char_span)}


@dataclass
class Sentence:
    text: str
    char_span: tuple[int, int]
    clauses: list[Clause] = field(default_factory=list)
    is_field_label: bool = False
    field_label: Optional[str] = None
    field_state: Optional[str] = None    # YOGAYA / PRAYOGA / ANUPANA / …

    def to_dict(self):
        return {
            "text": self.text,
            "char_span": list(self.char_span),
            "clauses": [c.to_dict() for c in self.clauses],
            "is_field_label": self.is_field_label,
            "field_label": self.field_label,
            "field_state":  self.field_state,
        }


@dataclass
class Document:
    source_text: str
    sentences: list[Sentence] = field(default_factory=list)

    def to_dict(self):
        return {"source_text": self.source_text,
                "sentences": [s.to_dict() for s in self.sentences]}


# ── helpers ─────────────────────────────────────────────────────────────────

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


# Field-label index, NFC-normalised, sorted by length DESC so longest match wins.
_FIELD_LABELS = sorted(
    ((nfc(label), state) for label, state in LABEL_TO_STATE.items()),
    key=lambda kv: -len(kv[0]),
)


def _classify_field_label(text: str) -> tuple[Optional[str], Optional[str]]:
    """If `text` is exactly a known field label (after stripping), return
    (label, state); else (None, None)."""
    t = text.strip()
    for label, state in _FIELD_LABELS:
        if t == label:
            return label, state
    return None, None


# Sentence-boundary regex.
# - "(?<!\d)\.(?!\d)" : a period that is NOT a decimal point.
# - "[।॥]"            : Sinhala / Devanagari daṇḍas.
# - "\|"              : ASCII pipe used as daṇḍa-substitute.
# - ":-"              : pharmacopoeia field-label separator.
# - "(?:\n|\r\n?)\s*(?=\d{1,3}[.)])" : line-start numbered marker.
#
# The pattern uses *positive lookbehind/lookahead-friendly* split via
# `re.finditer` on a "boundary marker" pattern; we then carve substrings
# between boundaries to keep char-span accounting honest.

_BOUNDARY_RE = re.compile(
    r"""
      (?P<colon_dash>:-)                  # 1) field-label separator
    | (?P<danda>[।॥|])                    # 2) Sinhala / pipe daṇḍa
    | (?<!\d)(?P<period>\.)(?!\d)         # 3) period (non-decimal)
    | (?P<newline_num>\n\s*(?=\d{1,3}[.)]))   # 4) line-start numbered marker
    """,
    re.VERBOSE,
)

# Clause-boundary regex (within a sentence).  Comma and standalone `=`.
_CLAUSE_RE = re.compile(r"[,]|\s=\s")


def segment(text: str) -> Document:
    """Segment Sinhala prose into sentences and clauses with char spans.

    Char spans are over the NFC-normalised source string (which is also
    returned in Document.source_text for round-trip indexing).
    """
    src = nfc(text or "")
    sentences: list[Sentence] = []

    # ── pass 1: sentence boundaries ─────────────────────────────────────
    boundaries: list[tuple[int, int, str]] = []   # (start, end, kind)
    for m in _BOUNDARY_RE.finditer(src):
        kind = next(k for k, v in m.groupdict().items() if v is not None)
        boundaries.append((m.start(), m.end(), kind))

    # Iterate substrings between boundaries.
    cursor = 0
    for b_start, b_end, kind in boundaries:
        chunk = src[cursor:b_start]
        chunk_stripped = chunk.strip()
        if chunk_stripped:
            # Re-compute the stripped span by scanning leading whitespace.
            lstrip = len(chunk) - len(chunk.lstrip())
            rstrip = len(chunk) - len(chunk.rstrip())
            real_start = cursor + lstrip
            real_end   = b_start - rstrip
            sentences.append(_make_sentence(src, chunk_stripped, real_start, real_end))
        cursor = b_end

    # tail after the last boundary
    tail = src[cursor:]
    tail_stripped = tail.strip()
    if tail_stripped:
        lstrip = len(tail) - len(tail.lstrip())
        rstrip = len(tail) - len(tail.rstrip())
        sentences.append(_make_sentence(src, tail_stripped,
                                        cursor + lstrip, len(src) - rstrip))

    return Document(source_text=src, sentences=sentences)


def _make_sentence(src: str, text: str, start: int, end: int) -> Sentence:
    """Build a Sentence object, including clause splitting and field-label
    classification. `text` is the NFC-stripped sentence text; (start,end)
    are its offsets in `src`."""
    label, state = _classify_field_label(text)
    s = Sentence(
        text=text,
        char_span=(start, end),
        is_field_label=label is not None,
        field_label=label,
        field_state=state,
    )
    # ── clause splitting within the sentence ────────────────────────────
    # Indices are relative to `src`, so we offset matches by `start` and
    # use `src[start:end]` for the slice (which equals `text` modulo
    # surrounding whitespace that we already trimmed off `text`).
    abs_offset = start
    sentence_slice = src[start:end]
    cursor = 0
    for m in _CLAUSE_RE.finditer(sentence_slice):
        piece = sentence_slice[cursor:m.start()]
        piece_stripped = piece.strip()
        if piece_stripped:
            lstrip = len(piece) - len(piece.lstrip())
            rstrip = len(piece) - len(piece.rstrip())
            s.clauses.append(Clause(
                text=piece_stripped,
                char_span=(abs_offset + cursor + lstrip,
                           abs_offset + m.start() - rstrip),
            ))
        cursor = m.end()
    # tail clause
    tail = sentence_slice[cursor:]
    tail_stripped = tail.strip()
    if tail_stripped:
        lstrip = len(tail) - len(tail.lstrip())
        rstrip = len(tail) - len(tail.rstrip())
        s.clauses.append(Clause(
            text=tail_stripped,
            char_span=(abs_offset + cursor + lstrip,
                       abs_offset + len(sentence_slice) - rstrip),
        ))
    if not s.clauses:
        # whole sentence is one clause
        s.clauses.append(Clause(text=text, char_span=s.char_span))
    return s


# ── CLI ─────────────────────────────────────────────────────────────────────
_DEMO = (
    "44. ත්‍රිකටු චූර්ණය. යෝගය:- තිප්පිලි, ඉඟුරු, ගම්මිරිස් සමව ගෙන කොටා පෙළා කෙළවර කරයි. "
    "ප්‍රයෝග:- කාස, ශ්වාස, අග්නිමාන්ද්‍ය. අනුපාන:- මී පැණි. මාත්‍රාව:- ග්‍රෑ 5."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="text file to segment")
    ap.add_argument("--demo", action="store_true",
                    help="run on a built-in pharmacopoeia example")
    ap.add_argument("--json", action="store_true",
                    help="emit raw JSON to stdout (default: pretty-printed listing)")
    args = ap.parse_args()

    if args.demo or args.path is None:
        text = _DEMO if args.demo else sys.stdin.read()
    else:
        text = Path(args.path).read_text(encoding="utf-8")

    doc = segment(text)

    if args.json:
        print(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"=== {len(doc.sentences)} sentences ===")
    for i, s in enumerate(doc.sentences):
        tag = f" [{s.field_state}]" if s.is_field_label else ""
        print(f"S{i}{tag}  {s.char_span}  '{s.text}'")
        for j, c in enumerate(s.clauses):
            print(f"   C{j}  {c.char_span}  '{c.text}'")


if __name__ == "__main__":
    main()

"""
extract_yogamalawa_v1.py
────────────────────────
Stage 3 for Yogamālāva (1908), the verse-form Sinhala Ayurvedic compendium.

Unlike the tabular pharmacopoeia (handled by extract_pharma_v4.py), Yogamālāva
is a *padyamālāva* — a "garland of verses." Each formula is a numbered four-line
verse with optional centred indication line. Entry markers are integers 1–231
appearing at the left margin.

ALGORITHM
─────────
For every row produced by shrink_ocr_v4.py:

  - Drop the running header  ('යෝග මාලාව') at y < 0.10.
  - Recognise entry markers in any of three forms (Yogamālāva uses a
    variable-column layout, so x₀-based detection alone is unreliable):
      a) Number-only row, e.g. just '1' — verse body begins on the
         following row(s).
      b) Number + Sinhala body on the same row, e.g.
         '49 එඬරුත් බෙලි ...'.
      c) Number + body where the body starts with a leading Sinhala
         letter (filters '16 20' fragments that are not real markers).
  - Require entry numbers to be monotonically non-decreasing (with a
    small backward tolerance for two-column pages where the right
    column wraps after the left). This kills false positives from
    misread digits inside a verse body.
  - Rows in the centred / right-shifted zone (x₀ > 0.40) ending with
    '.' are captured as INDICATION markers — typically a single Sinhala
    medical condition (e.g. 'ගුල්ම උදරයට .' → 'for gulma+udara').
  - Rows that match no rule and belong to no open entry are tracked
    in an `unassigned` audit list, exposed in the output for
    diagnostic / coverage analysis.

OUTPUT  (data/structured/yogamalawa/yogamalawa_structured.json):

  { "source": "yogamalawa",
    "count":  <n>,
    "entries": [
      { "අංකය": 49,
        "lines": [ "...", "...", "...", "..." ],
        "verse_text": "<joined with \n>",
        "ප්‍රයෝග": "සියලු ඇවිලිල්ලට",     # indication phrase
        "source_page": 8
      },
      ...
    ]
  }

The Sinhala key choice (`අංකය`, `ප්‍රයෝග`) mirrors the pharmacopoeia schema so
downstream tools (resolver, KG) can treat both corpora uniformly.

USAGE
─────
  python extract_yogamalawa_v1.py [rows.json] [structured.json]
  defaults:
    rows.json       = data/rows/yogamalawa/yogamalawa_rows.json
    structured.json = data/structured/yogamalawa/yogamalawa_structured.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

# Thresholds (normalised x; 0=left, 1=right)
INDIC_X_MIN  = 0.40   # centred / right-shifted indication-phrase band
HEADER_Y_MAX = 0.10   # running-title band at top of each page

# Detection patterns
NUM_ONLY_RE = re.compile(r"^\s*(\d{1,3})\s*$")          # row body is just "42"
ENTRY_RE    = re.compile(r"^\s*(\d{1,3})\s+(.+)$")      # row body is "42 …"
# A character is "Sinhala" if it falls in the Sinhala block (U+0D80–U+0DFF).
SINHALA_CHAR_RE = re.compile(r"[඀-෿]")

MAX_ENTRY   = 235     # 231 verses in Yogamālāva; small margin for OCR slop
BACK_TOL    = 100     # loose: TOC interleaving + 2-column wrap + OCR slop
                      # The looseness can produce some duplicate entry numbers
                      # across pages — these are surfaced in the coverage
                      # screen and should be deduplicated downstream.
PERIOD_END  = re.compile(r"[\.\s]+$")

HEADER_TOKEN = "යෝග මාලාව"   # running header on every body page


def _row_text(row):
    return " ".join(w[3] for w in row["w"])


def _row_x0(row):
    return row["w"][0][0] if row["w"] else 1.0


def is_header(row, text):
    return row["y"] < HEADER_Y_MAX and HEADER_TOKEN in text


def _looks_like_entry_body(s):
    """A real verse body has ≥3 chars AND contains at least one Sinhala
    letter somewhere (rejects '20', '16 4', etc. that are pure numerics
    appearing on table-of-contents fragments)."""
    return len(s) >= 3 and bool(SINHALA_CHAR_RE.search(s))


def extract(rows_doc):
    """Walk every page's rows in order, group by entry-number markers."""
    entries: list[dict] = []
    unassigned: list[dict] = []   # rows that belong to no open entry
    current: dict | None = None
    max_seen = 0                  # highest entry number opened so far

    def close_current():
        nonlocal current
        if current is None:
            return
        current["verse_text"] = "\n".join(current["lines"])
        if current.get("_indication"):
            ind = current.pop("_indication")
            current["ප්‍රයෝග"] = PERIOD_END.sub("", ind).strip()
        else:
            current["ප්‍රයෝග"] = ""
            current.pop("_indication", None)
        entries.append(current)
        current = None

    for page in rows_doc["pages"]:
        page_num = page["page"]
        for row in page["rows"]:
            if not row.get("w"):
                continue
            text = _row_text(row).strip()
            if not text:
                continue
            if is_header(row, text):
                continue

            x0 = _row_x0(row)

            # (a) number-only row → marker; body continues on subsequent rows
            mn = NUM_ONLY_RE.match(text)
            if mn:
                n = int(mn.group(1))
                if 1 <= n <= MAX_ENTRY and n >= max_seen - BACK_TOL:
                    close_current()
                    current = {"අංකය": n, "lines": [],
                               "source_page": page_num, "_indication": None}
                    max_seen = max(max_seen, n)
                    continue

            # (b)/(c) "N <body>" — but only if body is plausibly Sinhala content
            m = ENTRY_RE.match(text)
            if m:
                n = int(m.group(1))
                body = m.group(2).strip()
                if (1 <= n <= MAX_ENTRY
                        and n >= max_seen - BACK_TOL
                        and _looks_like_entry_body(body)):
                    close_current()
                    current = {"අංකය": n, "lines": [body],
                               "source_page": page_num, "_indication": None}
                    max_seen = max(max_seen, n)
                    continue

            # neither rule fired → either continuation or unassigned
            if current is not None:
                current["lines"].append(text)
                if x0 > INDIC_X_MIN and text.rstrip().endswith("."):
                    current["_indication"] = text
            else:
                unassigned.append({"page": page_num, "y": row["y"],
                                   "x0": x0, "text": text})

    close_current()
    return entries, unassigned


def main():
    here = Path(__file__).resolve().parent.parent  # repo root
    default_rows = here / "data" / "rows" / "yogamalawa" / "yogamalawa_rows.json"
    default_out  = here / "data" / "structured" / "yogamalawa" / "yogamalawa_structured.json"

    ap = argparse.ArgumentParser()
    ap.add_argument("rows", nargs="?", default=str(default_rows))
    ap.add_argument("out",  nargs="?", default=str(default_out))
    args = ap.parse_args()

    rows_doc = json.load(open(args.rows, encoding="utf-8"))
    entries, unassigned = extract(rows_doc)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(
        {"source": "yogamalawa",
         "count": len(entries),
         "entries": entries,
         "unassigned": unassigned},
        open(out_path, "w", encoding="utf-8"),
        ensure_ascii=False, indent=2,
    )

    # Report
    print(f"Extracted {len(entries)} entries from {len(rows_doc['pages'])} pages.")
    seen_nums = sorted({e["අංකය"] for e in entries})
    if seen_nums:
        lo, hi = seen_nums[0], seen_nums[-1]
        gaps = [n for n in range(lo, hi + 1) if n not in set(seen_nums)]
        print(f"Entry-number range: {lo}–{hi}   gaps: "
              f"{gaps[:20]}{' …' if len(gaps) > 20 else ''}  ({len(gaps)} total)")
    with_indic = sum(1 for e in entries if e["ප්‍රයෝග"])
    print(f"Entries with extracted indication: {with_indic}/{len(entries)} "
          f"({100*with_indic/max(len(entries),1):.0f} %)")
    print(f"Unassigned rows (no open entry): {len(unassigned)}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

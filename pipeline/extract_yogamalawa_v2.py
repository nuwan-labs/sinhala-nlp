"""
extract_yogamalawa_v2.py  (v2.1)
────────────────────────────────
Stage 3 for Yogamālāva — second iteration.

v2.1 fixes the residual-token-loss bug in v2's embedded-marker splitting.
The bug: v2 used `first_match.start()` of the EMBEDDED_RE iterator as the
prefix-end position. But that regex matches ANY digit between Sinhala
flanks — including digits outside the window-valid set. When the first
regex match was a non-valid embed (e.g. `117` on page-14 row 3, where the
window-valid embed was `128`), the prefix was truncated at `117` and
everything between `117` and `128` was dropped. v2.1 makes
_scan_embedded_markers return (n, start, end) tuples and uses only the
window-valid start positions for slicing — so no inter-embed content can
fall through the cracks.

v1 (extract_yogamalawa_v1.py) achieved 98.5% per-token coverage but only
37% entry recall (86/231 distinct entry numbers). The coverage screen
showed three specific failure modes; v2 fixes each.

IMPROVEMENTS OVER v1
────────────────────

1. **Header rows that carry an entry number** are no longer dropped wholesale.
   On dense pages, the running header row may bundle entry-number, running
   title, and page-number on one line:
        '133 යෝග මාලාව. 13'    (page 15, row 0)
   v1's header filter dropped this entire row, losing entry 133. v2 first
   inspects the row for a leading number; if present, it opens that entry
   (with an empty body that subsequent rows fill in) before discarding the
   header text.

2. **Embedded entry markers** mid-row are now detected. On pages where
   shrink_ocr_v4 clustered multiple verse-lines into one row, several entry
   numbers may sit inside a single OCR row, e.g.:
        'විකාරය ... මතුක 134 දුන් ව ... 136 එ න තුත්තන් ...'
   v2 scans the row for digit tokens equal to max_seen+1 … +5 between
   Sinhala flanks, and splits the row at those positions into multiple
   entries. The window (max_seen+1..+5) keeps precision high: quantities
   and dosage numbers are typically far outside that range.

3. **Indication mop-up.** Any centred period-terminated phrase that did
   not get attached during the main loop is attributed post hoc to the
   most-recently-closed entry on the same page. v1 lost 89 substantive
   tokens to this exact failure mode (the 'කුෂ්ටයට.', 'අතීසාරයට.' tails).

USAGE (same as v1)
──────────────────
  python extract_yogamalawa_v2.py [rows.json] [structured.json]
  defaults:
    rows.json       = data/rows/yogamalawa/yogamalawa_rows.json
    structured.json = data/structured/yogamalawa/yogamalawa_structured_v2.json
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

# ── thresholds (normalised x; 0=left, 1=right) ───────────────────────────────
INDIC_X_MIN   = 0.40        # centred / right-shifted indication band
HEADER_Y_MAX  = 0.10        # running-title band at top of each page

# ── patterns ──────────────────────────────────────────────────────────────────
NUM_ONLY_RE   = re.compile(r"^\s*(\d{1,3})\s*$")        # row body = '42'
ENTRY_RE      = re.compile(r"^\s*(\d{1,3})\s+(.+)$")    # row body = '42 …'
NUM_PREFIX_RE = re.compile(r"^\s*(\d{1,3})\b")          # any leading number
SINHALA_RE    = re.compile(r"[඀-෿]")
# Embedded mid-row marker: a digit token (1–3 digits) flanked by Sinhala
# content with whitespace on both sides.
EMBEDDED_RE   = re.compile(r"(?<=\s)(\d{1,3})(?=\s+[඀-෿])")

MAX_ENTRY      = 235
BACK_TOL       = 100         # loose — surface duplicates rather than miss
EMBED_FWD_WIN  = 5           # only accept embedded n in [max_seen+1, max_seen+5]
PERIOD_END     = re.compile(r"[\.\,\s]+$")

HEADER_TOKEN   = "යෝග මාලාව"


# ── helpers ───────────────────────────────────────────────────────────────────
def _row_text(row):
    return " ".join(w[3] for w in row["w"])


def _row_x0(row):
    return row["w"][0][0] if row["w"] else 1.0


def _looks_like_entry_body(s):
    return len(s) >= 3 and bool(SINHALA_RE.search(s))


def _is_header_row(row, text):
    return row["y"] < HEADER_Y_MAX and HEADER_TOKEN in text


def _scan_embedded_markers(text, max_seen):
    """Return list of (n, start, end) tuples for digit tokens in
    [max_seen+1, max_seen+EMBED_FWD_WIN] embedded mid-text between
    Sinhala flanks. start/end are positions of the digit itself in `text`."""
    out = []
    cursor_max = max_seen
    for m in EMBEDDED_RE.finditer(text):
        n = int(m.group(1))
        if cursor_max + 1 <= n <= cursor_max + EMBED_FWD_WIN:
            out.append((n, m.start(), m.end()))
            cursor_max = n
    return out


# ── extraction ────────────────────────────────────────────────────────────────
def extract(rows_doc):
    entries: list[dict] = []
    unassigned: list[dict] = []
    current: dict | None = None
    max_seen = 0

    def close_current():
        nonlocal current
        if current is None:
            return
        current["verse_text"] = "\n".join(current["lines"])
        ind = current.pop("_indication", None)
        current["ප්‍රයෝග"] = PERIOD_END.sub("", ind).strip() if ind else ""
        entries.append(current)
        current = None

    def open_entry(n, page_num, body_lines=None):
        nonlocal current, max_seen
        close_current()
        current = {
            "අංකය": n,
            "lines": list(body_lines or []),
            "source_page": page_num,
            "_indication": None,
        }
        max_seen = max(max_seen, n)

    def append_line_to_current(text, x0):
        if current is None:
            return False
        current["lines"].append(text)
        if x0 > INDIC_X_MIN and text.rstrip().endswith("."):
            current["_indication"] = text
        return True

    for page in rows_doc["pages"]:
        page_num = page["page"]
        for row in page["rows"]:
            if not row.get("w"):
                continue
            text = _row_text(row).strip()
            if not text:
                continue

            x0 = _row_x0(row)

            # IMPROVEMENT 1 — header row may carry a leading entry number.
            if _is_header_row(row, text):
                m = NUM_PREFIX_RE.match(text)
                if m:
                    n = int(m.group(1))
                    if 1 <= n <= MAX_ENTRY and n >= max_seen - BACK_TOL:
                        open_entry(n, page_num)   # body arrives later
                continue

            # rule (a) — number-only row
            mn = NUM_ONLY_RE.match(text)
            if mn:
                n = int(mn.group(1))
                if 1 <= n <= MAX_ENTRY and n >= max_seen - BACK_TOL:
                    open_entry(n, page_num)
                    continue

            # rule (b)/(c) — 'N <body>' with Sinhala-containing body
            m = ENTRY_RE.match(text)
            if m:
                n = int(m.group(1))
                body = m.group(2).strip()
                if (1 <= n <= MAX_ENTRY
                        and n >= max_seen - BACK_TOL
                        and _looks_like_entry_body(body)):
                    open_entry(n, page_num, [body])
                    # IMPROVEMENT 2 (v2.1) — scan body for further embedded
                    # markers and split into multiple entries, slicing only
                    # at *window-valid* embed positions. Any inter-embed
                    # content (including digit-tokens outside the window)
                    # stays in the surrounding prefix / piece.
                    embeds = _scan_embedded_markers(body, max_seen)
                    if embeds:
                        first_start = embeds[0][1]
                        current["lines"][0] = body[:first_start].strip()
                        for i, (n_embed, _start, end_pos) in enumerate(embeds):
                            next_start = (embeds[i+1][1] if i+1 < len(embeds)
                                          else len(body))
                            piece = body[end_pos:next_start].strip()
                            open_entry(n_embed, page_num,
                                       [piece] if piece else [])
                    continue

            # IMPROVEMENT 2 (v2.1) — continuation rows containing a mid-row
            # entry marker get split. Slicing uses window-valid embed
            # positions only — content between non-valid digit-tokens and
            # the first window-valid embed stays in the prefix (assigned to
            # current entry if open, else preserved in `unassigned`).
            embeds = _scan_embedded_markers(text, max_seen)
            if embeds:
                first_start = embeds[0][1]
                prefix = text[:first_start].strip()
                if prefix:
                    if current is not None:
                        append_line_to_current(prefix, x0)
                    else:
                        unassigned.append({"page": page_num, "y": row["y"],
                                           "x0": x0, "text": prefix})
                for i, (n_embed, _start, end_pos) in enumerate(embeds):
                    next_start = (embeds[i+1][1] if i+1 < len(embeds)
                                  else len(text))
                    piece = text[end_pos:next_start].strip()
                    open_entry(n_embed, page_num,
                               [piece] if piece else [])
                continue

            # ordinary continuation
            if not append_line_to_current(text, x0):
                unassigned.append({"page": page_num, "y": row["y"],
                                   "x0": x0, "text": text})

    close_current()

    # IMPROVEMENT 3 — indication mop-up.
    #   (a) Orphan period-terminated centred phrases in `unassigned`:
    #       attribute to the most recent closed entry on the same page.
    #   (b) Closed entries whose last `lines[]` row is a period-terminated
    #       centred phrase and that don't yet have an indication: promote it.
    by_page_entries: dict[int, list[dict]] = {}
    for e in entries:
        by_page_entries.setdefault(e["source_page"], []).append(e)

    # pass (b) — last-line indication on closed entries
    promoted = 0
    for e in entries:
        if e["ප්‍රයෝග"]:
            continue
        if not e["lines"]:
            continue
        last = e["lines"][-1]
        # heuristic: short period-terminated phrase that ends with "ට ."
        # (Sinhala dative ending used for indications: "X-ට" = "for X")
        if (last.rstrip().endswith(".") and len(last) <= 60
                and re.search(r"ට\s*\.\s*$", last)):
            e["ප්‍රයෝග"] = PERIOD_END.sub("", last).strip()
            promoted += 1

    # pass (a) — orphans
    new_unassigned: list[dict] = []
    attached_orphans = 0
    for u in unassigned:
        text = u["text"]
        if (u["x0"] > INDIC_X_MIN
                and text.rstrip().endswith(".")
                and len(text) <= 60
                and u["page"] in by_page_entries):
            candidates = by_page_entries[u["page"]]
            tgt = candidates[-1]
            if not tgt["ප්‍රයෝග"]:
                tgt["ප්‍රයෝග"] = PERIOD_END.sub("", text).strip()
                tgt["lines"].append(text)
                attached_orphans += 1
                continue
        new_unassigned.append(u)

    return entries, new_unassigned, {
        "indications_promoted_from_last_line": promoted,
        "orphan_indications_attached":         attached_orphans,
    }


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent.parent
    default_rows = here / "data" / "rows" / "yogamalawa" / "yogamalawa_rows.json"
    default_out  = here / "data" / "structured" / "yogamalawa" / \
                   "yogamalawa_structured_v2.json"

    ap = argparse.ArgumentParser()
    ap.add_argument("rows", nargs="?", default=str(default_rows))
    ap.add_argument("out",  nargs="?", default=str(default_out))
    args = ap.parse_args()

    rows_doc = json.load(open(args.rows, encoding="utf-8"))
    entries, unassigned, stats = extract(rows_doc)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(
        {"source": "yogamalawa", "extractor": "v2",
         "count": len(entries), "entries": entries,
         "unassigned": unassigned, "mop_up_stats": stats},
        open(out_path, "w", encoding="utf-8"),
        ensure_ascii=False, indent=2,
    )

    nums = sorted({e["අංකය"] for e in entries})
    gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)] \
           if nums else []
    with_indic = sum(1 for e in entries if e["ප්‍රයෝග"])

    print(f"Extracted {len(entries)} entries ({len(nums)} distinct numbers) "
          f"from {len(rows_doc['pages'])} pages.")
    print(f"Entry-number range: {nums[0]}–{nums[-1]}   gaps: {len(gaps)} "
          f"({gaps[:15]}{'…' if len(gaps) > 15 else ''})")
    print(f"Entries with indication: {with_indic}/{len(entries)} "
          f"({100*with_indic/max(len(entries),1):.0f} %)")
    print(f"Mop-up: indications promoted from last-line: "
          f"{stats['indications_promoted_from_last_line']}    "
          f"orphan indications attached: {stats['orphan_indications_attached']}")
    print(f"Unassigned rows: {len(unassigned)}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

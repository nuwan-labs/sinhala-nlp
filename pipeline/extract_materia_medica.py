"""
extract_materia_medica.py
─────────────────────────
Two-column-aware parser for the categorised raw-materials appendix at the
back of Vol I of the Sri Lankan Ayurvedic Pharmacopoeia.

Source pages (GCV OCR, already produced):
  444         title row + section header "උද්භිද ද්‍රව්‍ය" (plant / vegetable)
  444 – 451   plant inventory          (two-column, alphabetical Sinhala)
  451 (mid)   section header "පාර්ථිව ද්‍රව්‍ය" (earth / mineral)
  451 – 452   mineral inventory
  452 (mid)   section header "ජාන්තව ද්‍රව්‍ය" (animal-origin)
  452 – 453   animal-product inventory

Algorithm:
  1.  For each page, walk the GCV block→paragraph→word tree and collect
      (x, y, text) per word (same logic as shrink_ocr_v4.py).
  2.  Cluster words into visual rows by y (Y_TOL = 0.012).
  3.  Detect section-header rows by Sinhala-substring match and record the
      y-position where each section transition happens.
  4.  For non-header rows, split into LEFT and RIGHT columns at the
      page-gutter x ≈ 0.5, join words in each half into a single Sinhala
      phrase, and tag it with the section that holds at that y.
  5.  Filter title rows, page numbers, and numeric noise.

Output (sinhala-traditional-medicine-nlp/data/lexicons/materia_medica.json):
{
  "metadata": {...},
  "by_section": {
    "plant":          [{"sinhala": "...", "page": 444, "col": "L", "y": 0.08}, ...],
    "mineral":        [...],
    "animal_origin": [...]
  },
  "by_sinhala": {
    "අරලිය": {"section": "plant", "page": 444, "col": "L", "y": 0.08},
    ...
  }
}

Usage:
  python extract_materia_medica.py
  python extract_materia_medica.py --ocr-dir /custom/path/ocr_json
  python extract_materia_medica.py --debug 451     # dump rows for one page
"""
from __future__ import annotations
import argparse
import json
import re
import statistics
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "materia_medica_v1"

Y_TOL = 0.012       # max y-spread within one visual row
GUTTER_X = 0.50     # column split: x < GUTTER → LEFT, x >= GUTTER → RIGHT

# ── Page range and batch routing ─────────────────────────────────────────────
PAGE_BATCH = {}
for pg in range(444, 451):
    PAGE_BATCH[pg] = "ocr_results_output-401-to-450.json"
for pg in range(451, 454):
    PAGE_BATCH[pg] = "ocr_results_output-451-to-500.json"
PAGES = sorted(PAGE_BATCH)

# ── Section detection (markers NFC-normalised at module load) ───────────────
def _nfc(s): return unicodedata.normalize("NFC", s)

SECTION_MARKERS = [
    ("plant",          tuple(_nfc(x) for x in ("උද්භිද",  "ද්‍රව්‍ය"))),  # udbhida
    ("mineral",        tuple(_nfc(x) for x in ("පාර්ථිව", "ද්‍රව්‍ය"))),  # pārthiva
    ("animal_origin", tuple(_nfc(x) for x in ("ජාන්තව",  "ද්‍රව්‍ය"))),  # jāntava
]
# A row that is the page title rather than a section header.
TITLE_MARKERS = tuple(_nfc(x) for x in ("ඖෂධ", "ලේඛනය"))

NUMERIC_RE = re.compile(r"^[\d\s\.,]+$")
PAGE_NUM_RE = re.compile(r"^\d{1,4}$")


# ── helpers ──────────────────────────────────────────────────────────────────
def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _word_text(word: dict) -> str:
    return "".join(s.get("text", "") for s in word.get("symbols", []))


def _is_decorative(text: str, x: float, y: float) -> bool:
    """Filter OCR noise: page numbers, lone punctuation."""
    text = text.strip()
    if not text:
        return True
    if PAGE_NUM_RE.fullmatch(text) and y > 0.88 and 0.30 < x < 0.70:
        return True
    if NUMERIC_RE.fullmatch(text):
        return True
    if len(text) == 1 and not text.isalnum():
        return True
    return False


def words_for_page(page_node: dict) -> list[tuple[float, float, str]]:
    """Return list of (x, y, text) for every non-decorative word on a page."""
    words = []
    for block in page_node.get("blocks", []):
        for para in block.get("paragraphs", []):
            for word in para.get("words", []):
                nv = word["boundingBox"]["normalizedVertices"]
                x = nv[0].get("x", 0.0)
                y = nv[0].get("y", 0.0)
                text = _word_text(word).strip()
                if _is_decorative(text, x, y):
                    continue
                words.append((round(x, 4), round(y, 4), text))
    return words


def cluster_rows(words: list[tuple[float, float, str]]) -> list[dict]:
    """Cluster a word list into visual rows by y. Each row carries every
    word with its x position, sorted left-to-right."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w[1], w[0]))
    rows, cur, cy = [], [ordered[0]], ordered[0][1]
    for w in ordered[1:]:
        if w[1] > cy + Y_TOL:
            rows.append(cur)
            cur, cy = [w], w[1]
        else:
            cur.append(w)
            cy = max(cy, w[1])
    rows.append(cur)
    out = []
    for cluster in rows:
        ys = [w[1] for w in cluster]
        row_y = round(statistics.median(ys), 4)
        cluster_sorted = sorted(cluster, key=lambda w: w[0])
        out.append({"y": row_y, "words": cluster_sorted})
    return out


def detect_header(row_text: str) -> str | None:
    """Return the new section name if `row_text` is a section header, else None.
    The title row (page 444) is explicitly NOT a section header."""
    if all(m in row_text for m in TITLE_MARKERS):
        return None
    for section, markers in SECTION_MARKERS:
        if all(m in row_text for m in markers):
            return section
    return None


def is_title_row(row_text: str) -> bool:
    return all(m in row_text for m in TITLE_MARKERS)


# ── per-page extraction ──────────────────────────────────────────────────────
def parse_page(page_node: dict, page_num: int, starting_section: str | None):
    """Returns (entries, new_section, debug)."""
    raw_words = words_for_page(page_node)
    rows = cluster_rows(raw_words)

    # First pass: locate header rows and the y-positions where the active
    # section changes.
    transitions = []      # list of (y, new_section)
    skip_ys = set()       # y values whose row should not be emitted
    for row in rows:
        text = nfc("".join(w[2] for w in row["words"]))
        if is_title_row(text):
            skip_ys.add(row["y"])
            continue
        new_section = detect_header(text)
        if new_section:
            transitions.append((row["y"], new_section))
            skip_ys.add(row["y"])

    def section_at(y: float) -> str | None:
        sec = starting_section
        for hy, hs in transitions:
            if y >= hy:
                sec = hs
        return sec

    # Second pass: emit substance entries
    entries = []
    for row in rows:
        if row["y"] in skip_ys:
            continue
        section = section_at(row["y"])
        if section is None:
            # Before the first header on page 444 (above "උද්භිද ද්‍රව්‍ය").
            continue
        left = [w for w in row["words"] if w[0] < GUTTER_X]
        right = [w for w in row["words"] if w[0] >= GUTTER_X]
        for col, group in (("L", left), ("R", right)):
            if not group:
                continue
            phrase = " ".join(w[2] for w in group).strip()
            phrase = nfc(phrase)
            # Drop entries that are pure punctuation or single short tokens
            # like "II", "|", noise marks.
            stripped = re.sub(r"[\s\W]+", "", phrase)
            if len(stripped) < 2:
                continue
            entries.append({
                "sinhala": phrase,
                "section": section,
                "page": page_num,
                "col": col,
                "y": row["y"],
            })

    new_section = section_at(1.0)
    return entries, new_section, {"rows": len(rows),
                                  "transitions": transitions}


# ── full run ─────────────────────────────────────────────────────────────────
def run(ocr_dir: Path, debug_page: int | None = None):
    # Group pages by batch file so each large JSON is opened once.
    by_batch: dict[str, list[int]] = {}
    for pg, fn in PAGE_BATCH.items():
        by_batch.setdefault(fn, []).append(pg)

    all_entries: list[dict] = []
    current_section: str | None = None
    diagnostics: dict[int, dict] = {}

    for fn in sorted(by_batch):
        path = ocr_dir / fn
        if not path.exists():
            sys.exit(f"ERROR: OCR batch file not found: {path}")
        print(f"  reading {path.name} …", file=sys.stderr)
        data = json.load(open(path, encoding="utf-8"))
        wanted = set(by_batch[fn])
        page_index: dict[int, dict] = {}
        for resp in data["responses"]:
            pg = (resp.get("context") or {}).get("pageNumber")
            if pg in wanted:
                fta = resp.get("fullTextAnnotation") or {}
                pages = fta.get("pages") or [{}]
                page_index[pg] = pages[0]
        for pg in sorted(wanted):
            if pg not in page_index:
                print(f"    ! page {pg} not in batch", file=sys.stderr)
                continue
            entries, current_section, dbg = parse_page(
                page_index[pg], pg, current_section)
            all_entries.extend(entries)
            diagnostics[pg] = {**dbg, "section_after": current_section,
                               "n_entries": len(entries)}
            if debug_page == pg:
                _dump_debug(pg, page_index[pg], entries, dbg)

    # ── deduplicate by Sinhala surface form (NFC) ────────────────────────────
    by_sinhala: dict[str, dict] = {}
    section_counts: dict[str, int] = {}
    duplicates: list[str] = []
    for ent in all_entries:
        key = ent["sinhala"]
        if key in by_sinhala:
            duplicates.append(key)
            continue
        by_sinhala[key] = ent
        section_counts[ent["section"]] = section_counts.get(ent["section"], 0) + 1

    by_section: dict[str, list[dict]] = {"plant": [], "mineral": [],
                                         "animal_origin": []}
    for ent in all_entries:
        if ent["sinhala"] in by_section[ent["section"]] or any(
                e["sinhala"] == ent["sinhala"]
                for e in by_section[ent["section"]]):
            continue
        by_section[ent["section"]].append(ent)
    # Re-sort each section by (page, col, y) for human reading order.
    for sec in by_section:
        by_section[sec].sort(key=lambda e: (e["page"], e["col"], e["y"]))

    return {
        "metadata": {
            "extractor_version": EXTRACTOR_VERSION,
            "built_at": now_iso(),
            "source_doc": "Sri Lankan Ayurvedic Pharmacopoeia, Vol I",
            "source_pages": [PAGES[0], PAGES[-1]],
            "section_pages": {
                "plant":          [444, 451],
                "mineral":        [451, 452],
                "animal_origin": [452, 453],
            },
            "section_counts": section_counts,
            "total_unique":   len(by_sinhala),
            "duplicates_dropped": len(duplicates),
            "diagnostics": diagnostics,
        },
        "by_section": by_section,
        "by_sinhala": by_sinhala,
    }


def _dump_debug(pg: int, page_node, entries, dbg):
    """Print full row layout for one page (for debugging column split)."""
    print(f"\n=== DEBUG page {pg} ===")
    print(f"  rows: {dbg['rows']}   transitions: {dbg['transitions']}")
    rows = cluster_rows(words_for_page(page_node))
    for row in rows:
        text = " ".join(w[2] for w in row["words"])
        left = [w[2] for w in row["words"] if w[0] < GUTTER_X]
        right = [w[2] for w in row["words"] if w[0] >= GUTTER_X]
        print(f"  y={row['y']:.3f}  L={' '.join(left):28s}  R={' '.join(right)}")
    print(f"  Emitted {len(entries)} entries:")
    for e in entries[:10]:
        print(f"    [{e['col']}] {e['sinhala']}  ({e['section']})")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent          # …/pipeline/
    repo_root = here.parent                         # …/sinhala-traditional-medicine-nlp/
    outer_root = repo_root.parent                   # …/Pipeline/

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ocr-dir", default=str(outer_root / "ocr_json"),
                    help="directory containing OCR batch files "
                         "(default: ../../ocr_json relative to repo)")
    ap.add_argument("--out", default=str(repo_root / "data" / "lexicons"
                                          / "materia_medica.json"),
                    help="output lexicon path")
    ap.add_argument("--debug", type=int, default=None,
                    help="dump per-row layout for this page (e.g. 451)")
    args = ap.parse_args()

    result = run(Path(args.ocr_dir), debug_page=args.debug)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n✓ wrote {args.out}")
    meta = result["metadata"]
    print(f"  total unique substances : {meta['total_unique']}")
    for sec, n in meta["section_counts"].items():
        print(f"    {sec:18s} {n:4d}")
    print(f"  duplicates dropped       : {meta['duplicates_dropped']}")
    print("  pages processed         :", sorted(meta["diagnostics"]))


if __name__ == "__main__":
    main()

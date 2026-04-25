#!/usr/bin/env python3
"""
pipeline.py
-----------
Extract pages 172-443 from OCR batch JSON files and shrink to row-level JSON.
One output file per source batch, containing all extracted pages.

Expected directory layout (all relative to this script):
  ocr_json/
    ocr_results_output-151-to-200.json
    ocr_results_output-201-to-250.json
    ocr_results_output-251-to-300.json
    ocr_results_output-301-to-350.json
    ocr_results_output-351-to-400.json
    ocr_results_output-401-to-450.json
    ocr_results_output-451-to-500.json
  shrink_ocr_v4.py
  extract_page.py
  pipeline.py

Output (one file per batch):
  rows/
    151-to-200_rows.json
    201-to-250_rows.json
    251-to-300_rows.json
    301-to-350_rows.json
    351-to-400_rows.json
    401-to-450_rows.json

Output schema per batch file:
  {
    "batch":  "201-to-250",
    "pages": [
      { "page": 201, "w": 595, "h": 841, "rows": [...] },
      { "page": 202, ... },
      ...
    ]
  }

Usage:
  python pipeline.py                          # pages 172-443 (default)
  python pipeline.py --start 200 --end 250    # custom range
  python pipeline.py --force                  # overwrite existing output files
  python pipeline.py --dry-run                # show plan without running
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

# ── Locate sibling scripts ────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from shrink_ocr_v4 import shrink_one
except ImportError:
    sys.exit("ERROR: shrink_ocr_v4.py not found alongside pipeline.py")

try:
    from extract_page import load_json, extract_page as _find_page
except ImportError:
    sys.exit("ERROR: extract_page.py not found alongside pipeline.py")

# ── Paths ─────────────────────────────────────────────────────────────────
OCR_DIR  = HERE / "ocr_json"
ROWS_DIR = HERE / "rows"

# ── Batch registry ────────────────────────────────────────────────────────
BATCHES = [
    ("ocr_results_output-151-to-200.json", 151, 200),
    ("ocr_results_output-201-to-250.json", 201, 250),
    ("ocr_results_output-251-to-300.json", 251, 300),
    ("ocr_results_output-301-to-350.json", 301, 350),
    ("ocr_results_output-351-to-400.json", 351, 400),
    ("ocr_results_output-401-to-450.json", 401, 450),
    ("ocr_results_output-451-to-500.json", 451, 500),

]

DEFAULT_START = 444
DEFAULT_END   = 453

# ── Helpers ───────────────────────────────────────────────────────────────

def batch_label(filename: str) -> str:
    """'ocr_results_output-201-to-250.json' → '201-to-250'"""
    m = re.search(r"(\d+-to-\d+)", filename)
    return m.group(1) if m else filename.replace(".json", "")


def shrink_page(batch_data: dict, page_num: int) -> dict | None:
    """
    Extract page_num from batch_data, run shrink_one, return the result dict.
    shrink_one already includes "page": page_num in its output.
    Returns None if the page is not present in the batch.
    """
    page_result = _find_page(batch_data, page_num)
    if page_result is None:
        return None

    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(page_result, tmp, ensure_ascii=False)
        return shrink_one(tmp_path)   # {"page": N, "w": ..., "h": ..., "rows": [...]}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ── Main ──────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Shrink OCR pages to batch row-level JSON files.")
    p.add_argument("--start",   type=int, default=DEFAULT_START)
    p.add_argument("--end",     type=int, default=DEFAULT_END)
    p.add_argument("--force",   action="store_true",
                   help="Overwrite existing output files")
    p.add_argument("--dry-run", action="store_true",
                   help="Show plan without processing")
    return p.parse_args()


def main():
    args = parse_args()
    want_start, want_end = args.start, args.end

    if want_start > want_end:
        sys.exit(f"ERROR: --start ({want_start}) must be ≤ --end ({want_end})")

    # Build work plan
    plan = []
    for filename, b_start, b_end in BATCHES:
        pages = list(range(max(want_start, b_start),
                           min(want_end,   b_end) + 1))
        if pages:
            plan.append((filename, pages))

    if not plan:
        print(f"No batches cover pages {want_start}–{want_end}.")
        return

    total_pages = sum(len(p) for _, p in plan)
    print(f"Pages {want_start}–{want_end}  "
          f"({total_pages} pages across {len(plan)} batch file(s))\n")

    # Dry-run
    if args.dry_run:
        print("Output files:")
        for filename, pages in plan:
            label    = batch_label(filename)
            out_name = f"{label}_rows.json"
            missing  = "" if (OCR_DIR / filename).exists() else "  ✗ SOURCE MISSING"
            print(f"  rows/{out_name:30s}  ←  {len(pages)} pages "
                  f"({pages[0]}–{pages[-1]}){missing}")
        return

    # Validate sources
    missing = [(f, p) for f, p in plan if not (OCR_DIR / f).exists()]
    if missing:
        print("ERROR: source file(s) not found in", OCR_DIR)
        for f, _ in missing:
            print(f"  ✗  {f}")
        sys.exit(1)

    ROWS_DIR.mkdir(exist_ok=True)

    overall_start = time.time()
    total_done = total_skipped = total_failed = 0

    for filename, pages in plan:
        label    = batch_label(filename)
        out_path = ROWS_DIR / f"{label}_rows.json"

        print(f"\n── {label}  ({len(pages)} pages: {pages[0]}–{pages[-1]}) ──")

        if out_path.exists() and not args.force:
            existing = json.load(open(out_path))
            n = len(existing.get("pages", []))
            print(f"   · skipped — {out_path.name} already exists ({n} pages)")
            total_skipped += len(pages)
            continue

        batch_path = OCR_DIR / filename
        size_mb = batch_path.stat().st_size / 1_048_576
        t0 = time.time()
        print(f"   Loading {size_mb:.0f} MB ...", end="", flush=True)
        batch_data = load_json(str(batch_path))
        print(f" {time.time()-t0:.1f}s")

        collected = []
        for page_num in pages:
            result = shrink_page(batch_data, page_num)
            if result is None:
                print(f"   ✗ page {page_num}: not found in batch")
                total_failed += 1
            else:
                n_rows  = len(result["rows"])
                n_words = sum(len(r["w"]) for r in result["rows"])
                print(f"   ✓ page {page_num:4d}  {n_rows} rows, {n_words} words")
                collected.append(result)
                total_done += 1

        del batch_data   # free memory before next batch

        # Write single output file for this batch
        batch_output = {
            "batch": label,
            "pages": collected,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch_output, f, ensure_ascii=False, separators=(",", ":"))

        kb = out_path.stat().st_size // 1024
        print(f"   → {out_path.name}  ({len(collected)} pages, {kb} KB)")

    elapsed = time.time() - overall_start
    print(f"\n{'─'*55}")
    print(f"Done in {elapsed:.1f}s  —  "
          f"{total_done} processed, "
          f"{total_skipped} skipped, "
          f"{total_failed} failed")
    print(f"Output: {ROWS_DIR}/")


if __name__ == "__main__":
    main()

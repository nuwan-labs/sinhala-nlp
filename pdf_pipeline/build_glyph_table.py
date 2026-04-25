"""
build_glyph_table.py
─────────────────────
Aligns broken PDF text (IskoolaPota encoding) against GCV OCR text for the
same pages to discover systematic character substitution patterns.

BACKGROUND
  The IskoolaPota font's ToUnicode table has two major errors for Sinhala
  vowel combinations that include a pre-vowel ෙ component:
    • The pre-vowel glyph → U+0DC0 ව (should be U+0DD9 ෙ)
    • The consonant ක in an O-vowel context → U+0020 SPACE (consonant lost)
  This corrupts words like 'කොහොඹ' into 'ව ොවහොඹ'.

WHAT THIS SCRIPT DOES
  1. For each doc page in --start..--end:
     a. Extract PDF text rows via PyMuPDF (broken encoding)
     b. Extract OCR text rows from the GCV batch JSON (accurate)
  2. Align PDF rows to OCR rows by nearest Y position.
  3. Within each aligned row pair, run a character-level diff.
  4. Aggregate substitution (pdf_chars → ocr_chars) frequencies.
  5. Output a JSON correction table + console analysis report.

USAGE
  cd pdf_pipeline
  python build_glyph_table.py [--start N] [--end N] [--out FILE] [-v]

  Default: doc pages 151–220 (one OCR batch, keeps memory manageable).
  The table is written next to this script as glyph_corrections.json.

APPLYING CORRECTIONS
  After reviewing the table, run:
    python build_glyph_table.py --apply
  to patch extract_pdf.py with the correction pass.
"""

import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

# Force UTF-8 output on Windows so Sinhala characters and box-drawing print correctly
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PDF_PATH   = SCRIPT_DIR.parent / 'Pharamacopoeia.pdf'
OCR_DIR    = SCRIPT_DIR.parent / 'ocr_json'
PDF_OFFSET = 63  # 0-indexed fitz page = doc_page + PDF_OFFSET

# ── OCR batch registry ────────────────────────────────────────────────────────
OCR_BATCHES = [
    (151, 200, 'ocr_results_output-151-to-200.json'),
    (201, 250, 'ocr_results_output-201-to-250.json'),
    (251, 300, 'ocr_results_output-251-to-300.json'),
    (301, 350, 'ocr_results_output-301-to-350.json'),
    (351, 400, 'ocr_results_output-351-to-400.json'),
    (401, 450, 'ocr_results_output-401-to-450.json'),
    (451, 500, 'ocr_results_output-451-to-500.json'),
]

# ── Tuning ────────────────────────────────────────────────────────────────────
Y_ROW_TOL      = 0.015  # max y-difference to consider two rows the same line
MIN_ROW_RATIO  = 0.38   # minimum similarity to accept a row pair
MAX_SUB_LEN    = 9      # discard substitutions longer than this (misalignment)
MIN_HITS       = 4      # minimum occurrences to include in output table

# Sinhala vowel signs that visually incorporate a pre-vowel ෙ component
PREVOWEL_SIGNS = frozenset('ෙේොෝෞ')  # U+0DD9, 0DDA, 0DDC, 0DDD, 0DDE


# ─────────────────────────────────────────────────────────────────────────────
# OCR loader
# ─────────────────────────────────────────────────────────────────────────────

def _word_text_ocr(word):
    return ''.join(s.get('text', '') for s in word.get('symbols', []))


def _ocr_row_cluster(words, y_tol=Y_ROW_TOL):
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w[1], w[0]))
    rows, cur, cy = [], [ordered[0]], ordered[0][1]
    for w in ordered[1:]:
        if w[1] > cy + y_tol:
            rows.append(cur); cur, cy = [w], w[1]
        else:
            cur.append(w); cy = max(cy, w[1])
    rows.append(cur)
    return rows


def ocr_rows_for_page(batch_data, page_num):
    """Return list of {y, w:[token,...]} for one page from a loaded batch."""
    response = None
    for r in batch_data.get('responses', []):
        if r.get('context', {}).get('pageNumber') == page_num:
            response = r
            break
    if response is None:
        return []

    fta  = response.get('fullTextAnnotation', {})
    page = fta.get('pages', [{}])[0]

    raw = []
    for block in page.get('blocks', []):
        for para in block.get('paragraphs', []):
            for word in para.get('words', []):
                nv   = word['boundingBox']['normalizedVertices']
                x    = nv[0].get('x', 0.0)
                y    = nv[0].get('y', 0.0)
                text = _word_text_ocr(word).strip()
                if text:
                    raw.append((round(x, 3), round(y, 3), text))

    result = []
    for cluster in _ocr_row_cluster(raw):
        y_med  = sum(w[1] for w in cluster) / len(cluster)
        tokens = [w[2] for w in sorted(cluster, key=lambda w: w[0])]
        result.append({'y': round(y_med, 3), 'w': tokens})
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PDF loader (delegates to extract_pdf.page_to_rows)
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(SCRIPT_DIR))
from extract_pdf import page_to_rows as _pdf_page_to_rows  # noqa: E402


def pdf_rows_as_text(fitz_page):
    """Return list of {y, w:[token,...]} from PDF page."""
    rows, _ = _pdf_page_to_rows(fitz_page)
    return [{'y': r['y'], 'w': [w[3] for w in r['w']]} for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Row alignment
# ─────────────────────────────────────────────────────────────────────────────

def match_rows(pdf_rows, ocr_rows, y_tol=Y_ROW_TOL):
    """
    Greedy nearest-neighbour match: each OCR row is matched to the nearest
    PDF row within y_tol.  Returns list of (pdf_row_dict, ocr_row_dict) pairs.
    """
    used  = set()
    pairs = []
    # Iterate OCR rows; find closest unused PDF row
    for ocr_r in ocr_rows:
        best_pdf, best_d, best_idx = None, y_tol + 1.0, -1
        for i, pdf_r in enumerate(pdf_rows):
            if i in used:
                continue
            d = abs(pdf_r['y'] - ocr_r['y'])
            if d < best_d:
                best_pdf, best_d, best_idx = pdf_r, d, i
        if best_pdf is not None and best_d <= y_tol:
            pairs.append((best_pdf, ocr_r))
            used.add(best_idx)
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
# Character-level diff and substitution extraction
# ─────────────────────────────────────────────────────────────────────────────

def _nfc(s):
    return unicodedata.normalize('NFC', s)


def extract_substitutions(pdf_text, ocr_text):
    """
    Character-level diff.  Returns list of (pdf_str, ocr_str) replacements.
    'delete' → (pdf_str, '') and 'insert' → ('', ocr_str).
    """
    sm = difflib.SequenceMatcher(None, pdf_text, ocr_text, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        out.append((pdf_text[i1:i2], ocr_text[j1:j2]))
    return out


def process_row_pair(pdf_row, ocr_row, freq_table, examples):
    """
    Diff a matched (pdf_row, ocr_row) pair.  Updates freq_table and examples.
    """
    pdf_text = _nfc(' '.join(pdf_row['w']))
    ocr_text = _nfc(' '.join(ocr_row['w']))

    if pdf_text == ocr_text:
        return

    ratio = difflib.SequenceMatcher(
        None, pdf_text, ocr_text, autojunk=False).ratio()
    if ratio < MIN_ROW_RATIO:
        return  # too different → likely misaligned rows

    subs = extract_substitutions(pdf_text, ocr_text)
    for pdf_s, ocr_s in subs:
        if len(pdf_s) > MAX_SUB_LEN or len(ocr_s) > MAX_SUB_LEN:
            continue
        key = (pdf_s, ocr_s)
        freq_table[key] += 1
        # Store up to 3 examples per substitution key
        if len(examples[key]) < 3:
            snippet = (pdf_text[:60] + '…') if len(pdf_text) > 60 else pdf_text
            examples[key].append(snippet)


# ─────────────────────────────────────────────────────────────────────────────
# Analysis helpers
# ─────────────────────────────────────────────────────────────────────────────

def describe_chars(s):
    """Return comma-separated U+XXXX descriptions for each character."""
    if not s:
        return '(empty)'
    parts = []
    for c in s:
        cp  = ord(c)
        nm  = unicodedata.name(c, '?')
        parts.append(f'U+{cp:04X} {c!r} {nm}')
    return ' | '.join(parts)


def categorise(pdf_s, ocr_s, count):
    """Guess what kind of error this substitution represents."""
    if pdf_s == 'ව' and not ocr_s:
        return 'spurious-VA (pre-vowel artefact, no OCR counterpart)'
    if pdf_s == 'ව' and ocr_s in PREVOWEL_SIGNS:
        return 'VA→KOMBUVA: ව mapped from ෙ glyph'
    if 'ව' in pdf_s and any(c in PREVOWEL_SIGNS for c in ocr_s):
        return 'VA-containing sequence, pre-vowel involved'
    if pdf_s == ' ' and ocr_s and all(
            unicodedata.category(c).startswith('Lo') for c in ocr_s):
        return 'SPACE→consonant: consonant mapped to space'
    if not pdf_s and ocr_s:
        return 'missing-in-PDF: character lost entirely'
    if pdf_s and not ocr_s:
        return 'extra-in-PDF: spurious character in PDF'
    return 'substitution'


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run(start, end, out_path, verbose, min_hits=MIN_HITS):
    try:
        import fitz
    except ImportError:
        sys.exit('PyMuPDF required: pip install pymupdf')

    if not PDF_PATH.exists():
        sys.exit(f'PDF not found: {PDF_PATH}')

    doc         = fitz.open(str(PDF_PATH))
    freq_table  = defaultdict(int)
    examples    = defaultdict(list)

    current_batch_key  = None
    batch_data         = None
    total_pairs        = 0
    total_pages        = 0

    for doc_page in range(start, end + 1):
        # Find OCR batch
        batch_info = next(
            ((lo, hi, fn) for lo, hi, fn in OCR_BATCHES if lo <= doc_page <= hi),
            None)
        if batch_info is None:
            if verbose:
                print(f'  page {doc_page}: no OCR batch')
            continue

        bkey = (batch_info[0], batch_info[1])
        if bkey != current_batch_key:
            bp = OCR_DIR / batch_info[2]
            sz = bp.stat().st_size // 1024 // 1024
            print(f'  Loading {batch_info[2]}  ({sz} MB) …', flush=True)
            with open(bp, encoding='utf-8') as f:
                batch_data = json.load(f)
            current_batch_key = bkey

        pdf_idx  = doc_page + PDF_OFFSET
        if pdf_idx >= len(doc):
            break

        pdf_rows = pdf_rows_as_text(doc[pdf_idx])
        ocr_rows = ocr_rows_for_page(batch_data, doc_page)

        if not pdf_rows or not ocr_rows:
            if verbose:
                print(f'  page {doc_page}: empty '
                      f'(pdf={len(pdf_rows)} ocr={len(ocr_rows)})')
            continue

        pairs = match_rows(pdf_rows, ocr_rows)
        for pr, or_ in pairs:
            process_row_pair(pr, or_, freq_table, examples)

        total_pairs += len(pairs)
        total_pages += 1
        if verbose:
            print(f'  page {doc_page:4d}: '
                  f'{len(pdf_rows):3d} pdf / {len(ocr_rows):3d} ocr / '
                  f'{len(pairs):3d} matched pairs')

    # ── Build ranked table ────────────────────────────────────────────────────
    ranked = sorted(
        ((k, v) for k, v in freq_table.items() if v >= min_hits),
        key=lambda x: -x[1])

    # ── Console report ────────────────────────────────────────────────────────
    print(f'\n{"-"*70}')
    print(f'Pages processed : {total_pages}  ({start}-{end})')
    print(f'Row pairs       : {total_pairs}')
    print(f'Unique patterns : {len(freq_table)}  '
          f'(>={min_hits} hits: {len(ranked)})')
    print(f'{"-"*70}\n')

    print(f'TOP SUBSTITUTIONS (PDF → OCR):\n')
    for (pdf_s, ocr_s), cnt in ranked[:40]:
        cat = categorise(pdf_s, ocr_s, cnt)
        print(f'  [{cnt:4d}x]  {cat}')
        print(f'    PDF : {repr(pdf_s):25s}  {describe_chars(pdf_s)}')
        print(f'    OCR : {repr(ocr_s):25s}  {describe_chars(ocr_s)}')
        for ex in examples[(pdf_s, ocr_s)]:
            print(f'    ctx : {ex}')
        print()

    # ── Write JSON ────────────────────────────────────────────────────────────
    output = {
        'version'        : 1,
        'source_pages'   : [start, end],
        'total_pages'    : total_pages,
        'total_row_pairs': total_pairs,
        'min_hits'       : min_hits,
        'note': (
            'Each entry maps a pdf string (broken IskoolaPota encoding) '
            'to the correct Unicode string found in GCV OCR output. '
            'Apply longest-match-first string replacement before tokenisation.'
        ),
        'corrections': [
            {
                'pdf'            : pdf_s,
                'correct'        : ocr_s,
                'count'          : cnt,
                'category'       : categorise(pdf_s, ocr_s, cnt),
                'pdf_codepoints' : [f'U+{ord(c):04X}' for c in pdf_s],
                'ocr_codepoints' : [f'U+{ord(c):04X}' for c in ocr_s],
                'examples'       : examples[(pdf_s, ocr_s)],
            }
            for (pdf_s, ocr_s), cnt in ranked
        ],
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'OK  {out_path}  ({len(ranked)} rules, min_hits={min_hits})')
    print()
    print('Next steps:')
    print('  1. Review the top substitutions above.')
    print('  2. Run with a larger page range (e.g. --start 151 --end 300)')
    print('     to get more signal before applying.')
    print('  3. Call apply_corrections(text, corrections) in extract_pdf.py')
    print('     using the table produced here.')


def main():
    ap = argparse.ArgumentParser(
        description='Build IskoolaPota glyph correction table from OCR comparison.')
    ap.add_argument('--start',   type=int, default=151, metavar='PAGE',
                    help='First doc page (default 151)')
    ap.add_argument('--end',     type=int, default=220, metavar='PAGE',
                    help='Last  doc page (default 220)')
    ap.add_argument('--out',     default=str(SCRIPT_DIR / 'glyph_corrections.json'),
                    help='Output path (default: pdf_pipeline/glyph_corrections.json)')
    ap.add_argument('--min-hits', type=int, default=MIN_HITS, dest='min_hits',
                    metavar='N', help=f'Min occurrences (default {MIN_HITS})')
    ap.add_argument('--verbose', '-v', action='store_true')
    args = ap.parse_args()

    run(args.start, args.end, Path(args.out), args.verbose, args.min_hits)


if __name__ == '__main__':
    main()

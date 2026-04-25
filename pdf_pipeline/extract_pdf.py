"""
extract_pdf.py
──────────────
Single-script PDF extraction for the Ayurveda Pharmacopoeia.
Replaces the 3-stage OCR pipeline (GCV batch → shrink_ocr → extract_pharma).

Reads native IskoolaPota text directly via PyMuPDF (fitz).  No OCR.
NFC-normalises all text.  Tracks chapter/section headers.
Handles up to 3 ingredient columns per row.

DISCOVERY NOTES
───────────────
• The PDF has embedded text (not a scan) — direct extraction is possible.
• IskoolaPota has two systematic ToUnicode errors (corrected by _fix_iskoola_pota
  at span level before any tokenisation):
    1. Pre-vowel ෙ glyph → U+0DC0 ව (spurious VA; stripped)
    2. Long-ā vowel glyph → U+0DDC ො (should be U+0DCF ා; corrected)
   Both affect vowel signs with a visual pre-vowel component (ො, ෝ, ේ, …).
• After correction, most text is canonical Unicode.  Remaining anomaly:
    ස්ක ligature → "ස් " (ස් + SPACE); kok appears as SPACE in the PDF.
    "සංස්කරණය" still reads as "සංස් රණය" — handled in LABEL_TO_STATE.
• Output field names use canonical Unicode regardless.

COLUMN ZONES  (x normalised [0, 1] using page width ≈ 595 pt)
──────────────────────────────────────────────────────────────
  x < 0.15           entry number zone   "1."  "158."
  0.15 ≤ x < 0.25    label zone          "යෝගය"  "සංස් රණය"
  0.25 ≤ x < 0.32    separator zone      ":-"  (stripped before further use)
  x ≥ 0.32           content zone        ingredient names, prose, quantities

  Ingredient columns are split by x-gap > NAME_COL_GAP (0.15) within the
  content zone.  Spans from the same column share a synthetic block_id.

USAGE
─────
  python extract_pdf.py [PDF] [--start DOC_PAGE] [--end DOC_PAGE] [--out FILE]

  PDF defaults to ../Pharamacopoeia.pdf (relative to this script).
  Doc page N  =  0-indexed PDF page  (N + 63).
  Default range: doc pages 108–443 (full formula section).

OUTPUT SCHEMA
─────────────
  {
    "count":   707,
    "entries": [
      {
        "අංකය":       1,
        "යෝග නාමය":  "...",
        "යෝගය":      [{"ද්‍රව්‍යය": "...", "ප්‍රමාණය": "...", "ග්‍රෑ": null, "ලී": null}],
        "සංස්කරණය":  "...",
        "ප්‍රයෝග":   "...",
        "අනුපාන":    "...",
        "මාත්‍රාව":  "...",
        "සටහන":      "...",
        "source_page": 172,
        "section":    "ස්වරස අනුපාන ඛ්‍ණ්ඩය"
      }, ...
    ]
  }
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

try:
    import fitz
except ImportError:
    sys.exit("PyMuPDF is required:  pip install pymupdf")

# ── PDF location & page mapping ──────────────────────────────────────────────
DEFAULT_PDF   = Path(__file__).parent.parent / "Pharamacopoeia.pdf"
PDF_OFFSET    = 63        # 0-indexed PDF page = doc_page + PDF_OFFSET
DEFAULT_START = 108       # first formula doc page (adjuvant section)
DEFAULT_END   = 443       # last formula doc page

# ── Column zone thresholds (normalised x) ────────────────────────────────────
ENTRY_NUM_X    = 0.15
LABEL_X_MAX    = 0.25
SEP_X_MAX      = 0.32     # also = CONTENT_X lower bound
CONTENT_X      = 0.32
NAME_COL_GAP   = 0.15     # x-gap → new ingredient column
SHARED_QTY_X   = 0.45
X_PRIMARY_INGR = 0.50
STRANDED_X     = 0.70

# ── Row clustering ────────────────────────────────────────────────────────────
Y_TOL       = 0.010       # max y-spread within one visual row
# PDF line spacing is ~16 pt = 0.019 normalised; within-line y-variation ≤ 0.001
PAGE_NUM_Y  = 0.90        # y threshold for footer detection
FOOTER_SZ   = 11.5        # page-number font size (main text is 12 pt)

# ── Section header detection ──────────────────────────────────────────────────
SECTION_SZ  = 13.0        # headings are ≥ 13 pt; content is 12 pt

# ── Field label → state mapping ───────────────────────────────────────────────
# After _fix_iskoola_pota() runs, most labels arrive in canonical Unicode.
# Exception: "සංස් රණය" — the ස්ක ligature drops ක to SPACE (not a ො/ෝ issue),
# so it remains with the internal space even after encoding correction.
LABEL_TO_STATE = {
    'යෝගය':            'YOGAYA',       # canonical: ව+ය+ෝ fixed → යෝ
    'සංස් රණය':        'SANSKARANAYA', # ස්ක→ ස් + space (ක still lost)
    'ප්‍රයෝග':    'PRAYOGA',      # canonical: ව+ය+ෝ fixed → යෝ
    'අනුපාන':          'ANUPANA',      # canonical: ො→ා
    'මාත්‍රාව':   'MATRAVA',      # canonical: both ො→ා
}

# Output field names use canonical Unicode (not the PDF-extracted form)
FIELD_KEY = {
    'SANSKARANAYA': 'සංස්කරණය',
    'PRAYOGA':      'ප්‍රයෝග',
    'ANUPANA':      'අනුපාන',
    'MATRAVA':      'මාත්‍රාව',
    'SAYU':         'සටහන',
}

_TRANSITION_STATES = frozenset(FIELD_KEY) | {'YOGAYA'}

# ── Unit vocabulary ───────────────────────────────────────────────────────────
UNIT_WORDS = {
    # Indian system
    'තෝලා', 'තෝල', 'කර්ෂ', 'කර්ෂා', 'පල', 'ශාණ', 'මාෂ', 'මාෂක',
    'කෝල', 'භාග',
    # Lankan solid/weight scale
    'රක්තිකා', 'ගුංජා', 'ගංජා', 'මංචාඩි', 'කලං', 'කලන්', 'අඩපලං',
    'පලං', 'ප්‍රසෘති', 'අර්ධශරාව', 'ශරාව', 'ප්‍රස්ථ', 'නැලි', 'ආඪක',
    'ද්‍රෝණ', 'තුලා', 'පලම්',
    # Volume / liquid
    'ලීටර්', 'ලී', 'සේරු', 'පත', 'කුඩව', 'බෝ', 'බෝතල',
    # Imperial
    'රාත්තල්', 'ග්‍රෑම්ස්',
    # Spoon measures (PDF renders 'තේ'/'වේ' interchangeably for tea spoon)
    'හැඳි', 'හැදි',
    # Metric
    'ග්‍රෑ', 'ග්‍රෑම්',
    # Misc
    'රා',
    # Multi-word merged forms (see MULTI_WORD_UNITS)
    'තේ හැඳි', 'වේ හැඳි',
}

MULTI_WORD_UNITS = [
    ('තේ', 'හැඳි'),
    ('වේ', 'හැඳි'),   # PDF variant of 'තේ හැඳි'
]

# ── Word accessors ────────────────────────────────────────────────────────────
# Word tuple: [norm_x, span_idx, 0, token_text]
# span_idx acts as synthetic block_id for column detection in split_name_columns
def wx(w): return w[0]
def wb(w): return w[1]
def wt(w): return w[3]

# ── Regex ─────────────────────────────────────────────────────────────────────
_ENUM_RE = re.compile(r'^\d+\.?$')
_AMT_RE  = re.compile(r'^[\d][0-9./]*$|^1/2$')
_GRM_RE  = re.compile(r'^\d+$')
_PAGE_NUM_RE = re.compile(r'^\d{1,4}$')

# ── IskoolaPota font correction ────────────────────────────────────────────
# IskoolaPota ToUnicode errors confirmed by OCR comparison (50 pages, n≥10):
#   1. Pre-vowel ෙ glyph   → U+0DC0 ව  (spurious VA; should be absent)
#   2. Long-ā vowel glyph  → U+0DDC ො  (O-vowel sign; should be U+0DCF ා)
#
# Both vowel families with a visual pre-vowel ෙ component are affected:
#   ො (O-vowel):    C+ො → "ව ො" (ව=ෙ-glyph, SPACE=lost C, ො=ā-glyph)
#   ෝ (long-O):     C+ෝ → "වCෝ" (ව=ෙ-glyph, C=consonant, ෝ=long-ā-glyph)
#
# Insight: standalone ො in PDF ALWAYS = misencoded ා, because genuine O-vowel
# always arrives with a preceding ව artefact which our rules strip first.

_IKP_PH_O  = '\ue000'  # private-use sentinels; never appear in real Sinhala text
_IKP_PH_OO = '\ue001'


def _fix_iskoola_pota(text):
    """
    Fix IskoolaPota ToUnicode errors.  Applied per-span before tokenisation.

    Pass 1 ─ ෝ (long-O, U+0DDD):
      Strip spurious ව artefact before consonant sequence ending in ෝ.
      Pattern: ව + [non-space, non-ව run] + ෝ  →  run + ෝ
      e.g. 'වයෝගය' → 'යෝගය' ('yෝgy' label)

    Pass 2 ─ ො (O-vowel, U+0DDC):
      a) ව + single-consonant + ො  →  consonant + sentinel
      b) ව + SPACE + ො            →  sentinel  (consonant was lost to SPACE)
      c) standalone ො (not sentinel)   →  ා     (misencoded long-ā)
      d) restore sentinel                  →  ො
    """
    # Pass 1: long-O family
    text = re.sub(r'ව([^ව\s]+?)ෝ', r'\1' + _IKP_PH_OO, text)
    text = text.replace('ව ෝ', _IKP_PH_OO)

    # Pass 2: O-vowel family
    text = re.sub(r'ව([ක-ෆ])ො', r'\1' + _IKP_PH_O, text)
    text = text.replace('ව ො', _IKP_PH_O)
    text = text.replace('ො', 'ා')   # standalone ො = misencoded ා
    text = text.replace(_IKP_PH_O,  'ො')
    text = text.replace(_IKP_PH_OO, 'ෝ')
    return text


# ── PDF extraction ────────────────────────────────────────────────────────────
def _nfc(text):
    return unicodedata.normalize('NFC', text)


def page_to_rows(fitz_page):
    """
    Convert a PyMuPDF page to a list of row dicts  {'y': float, 'w': [...]}.
    Also returns a list of section header strings found on this page.

    Each word in 'w' is  [norm_x, span_idx, 0, token_text]  where span_idx
    is a synthetic block_id — tokens from the same PDF span share an id,
    enabling column detection in split_name_columns.
    """
    pw = fitz_page.rect.width  or 595.0
    ph = fitz_page.rect.height or 842.0

    # 1. Collect spans: (norm_x, norm_y, text, size)
    raw = []
    for block in fitz_page.get_text('dict')['blocks']:
        if block['type'] != 0:
            continue
        for line in block['lines']:
            for span in line['spans']:
                text = _fix_iskoola_pota(_nfc(span['text'])).strip()
                if not text:
                    continue
                bbox = span['bbox']
                raw.append((bbox[0] / pw, bbox[1] / ph, text, span['size']))

    # 2. Separate section headers from body text
    headers = [s[2] for s in raw if s[3] >= SECTION_SZ]
    body    = [s for s in raw if s[3] < SECTION_SZ]

    # 3. Drop page-number footers
    body = [
        s for s in body
        if not (s[1] > PAGE_NUM_Y and s[3] < FOOTER_SZ
                and _PAGE_NUM_RE.fullmatch(s[2]))
    ]

    if not body:
        return [], headers

    # 4. Cluster body spans into visual rows by y
    ordered = sorted(body, key=lambda s: (s[1], s[0]))
    groups, cur, cy = [], [ordered[0]], ordered[0][1]
    for s in ordered[1:]:
        if s[1] > cy + Y_TOL:
            groups.append(cur)
            cur, cy = [s], s[1]
        else:
            cur.append(s)
            cy = max(cy, s[1])
    groups.append(cur)

    # 5. Convert each row group → {y, w}
    rows = []
    for group in groups:
        y_mean = sum(s[1] for s in group) / len(group)
        words  = []
        for span_idx, (nx, _ny, text, _sz) in enumerate(
                sorted(group, key=lambda s: s[0])):

            # Strip ":-" separator prefix that the PDF often merges with content
            if text.startswith(':-'):
                text = text[2:].strip()
                if not text:
                    continue   # pure separator span

            # Split on runs of ≥2 spaces — the PDF sometimes packs two
            # ingredient names into one span using whitespace padding for
            # visual column alignment (e.g. "A           B").  Give each
            # sub-group a distinct synthetic block_id so split_name_columns
            # treats them as separate ingredient columns.
            sub_groups = re.split(r'  +', text)
            for sub_idx, sub_text in enumerate(sub_groups):
                block_id = span_idx * 20 + sub_idx
                for tok in sub_text.split():
                    if tok:
                        words.append([round(nx, 4), block_id, 0, tok])

        if words:
            rows.append({'y': round(y_mean, 4), 'w': words})

    return rows, headers


# ── Zone helpers ──────────────────────────────────────────────────────────────
def _entry_zone(rw): return [w for w in rw if wx(w) < ENTRY_NUM_X]
def _label_zone(rw): return [w for w in rw if ENTRY_NUM_X <= wx(w) < LABEL_X_MAX]


def _content_words(rw):
    """
    Content-zone words, sorted left→right.
    Spans whose text started with ":-" were pre-stripped in page_to_rows and
    kept at their original x (≈ 0.29–0.31, SEP zone).  Non-separator tokens
    in the SEP zone are included so that adjuvant-section formula names and
    first-ingredient names are not dropped.
    """
    _SEPS = frozenset((':', '-', '–', '—', ':-'))
    result = []
    for w in rw:
        x = wx(w)
        if x < LABEL_X_MAX:
            continue
        if x < CONTENT_X and wt(w) in _SEPS:
            continue
        result.append(w)
    return sorted(result, key=wx)


def to_text(ws):
    return ' '.join(wt(w) for w in ws).strip()


# ── Multi-word unit merging ───────────────────────────────────────────────────
def _merge_multi_word_units(cw):
    if not cw:
        return cw
    result, i = [], 0
    while i < len(cw):
        for unit_tup in MULTI_WORD_UNITS:
            n = len(unit_tup)
            if (i + n <= len(cw)
                    and tuple(wt(cw[i + j]) for j in range(n)) == unit_tup):
                merged = [cw[i][0], cw[i][1], cw[i][2],
                          ' '.join(unit_tup)]
                result.append(merged)
                i += n
                break
        else:
            result.append(cw[i])
            i += 1
    return result


# ── Row classifier ────────────────────────────────────────────────────────────
def classify_row(rw):
    """Return (row_type, content_word_list)."""
    cw = _merge_multi_word_units(_content_words(rw))

    # Entry header: first entry-zone token matches a number+period
    en = _entry_zone(rw)
    if en and _ENUM_RE.match(wt(en[0])):
        return 'ENTRY_HEADER', cw

    # Field label: join label-zone tokens and match against known labels.
    # Joining is necessary because "සංස් රණය" spans two tokens.
    lz = _label_zone(rw)
    if lz:
        first = wt(lz[0])

        # SAYU (note marker): "සැ:යු" or "සැ:"
        if first.startswith('සැ'):
            return 'SAYU', cw

        # Try progressively shorter token sequences from longest to first
        tokens = [wt(w) for w in lz]
        for n in range(len(tokens), 0, -1):
            candidate = ' '.join(tokens[:n])
            if candidate in LABEL_TO_STATE:
                return LABEL_TO_STATE[candidate], cw

    return 'CONTINUATION', cw


# ── Ingredient helpers ────────────────────────────────────────────────────────
def split_name_columns(cw):
    """
    Split content words into separate ingredient-name strings by column.
    Splits on x-gap > NAME_COL_GAP  OR  block_id (span_idx) change — the
    same logic as extract_pharma_v4.py.  Because every token from a PDF span
    shares the same span_idx, a new span always triggers a column boundary.
    """
    if not cw:
        return []
    groups, grp = [], [cw[0]]
    for i in range(1, len(cw)):
        if (wx(cw[i]) - wx(cw[i - 1]) > NAME_COL_GAP
                or wb(cw[i]) != wb(cw[i - 1])):
            groups.append(to_text(grp))
            grp = []
        grp.append(cw[i])
    groups.append(to_text(grp))
    return [g for g in groups if g]


def parse_ingredient(cw):
    """
    Parse content words → (name, unit, amount, grams, litres).
    Returns None if cw is empty; (text, None, None, None, None) if no unit.
    """
    if not cw:
        return None
    texts    = [wt(w) for w in cw]
    unit_idx = next((i for i, t in enumerate(texts) if t in UNIT_WORDS), None)
    if unit_idx is None:
        return to_text(cw), None, None, None, None

    name   = to_text(cw[:unit_idx])
    unit   = texts[unit_idx]
    tail   = texts[unit_idx + 1:]
    amount = next((t for t in tail if _AMT_RE.match(t)), None)
    grams, litres = None, None
    for i, t in enumerate(tail):
        if 'ග්‍රෑ' in t or t.startswith('ග්‍'):
            for g in tail[i + 1:]:
                if _GRM_RE.match(g):
                    grams = g
                    break
            break
        if t in ('ලී', 'ලීටර්') or t.startswith('ලී'):
            for g in tail[i + 1:]:
                if _GRM_RE.match(g):
                    litres = g
                    break
            break
    return name.strip(), unit, amount, grams, litres


def _is_ingr_name(text):
    if not text or ',' in text:
        return False
    words = text.split()
    first = words[0]
    return (len(words) <= 3
            and first not in UNIT_WORDS
            and not first[0].isdigit()
            and first not in {'(', '–', '—', '_'})


def _is_inline_instruction(group_text, row_words):
    if any(CONTENT_X <= wx(w) < X_PRIMARY_INGR for w in row_words):
        return False
    text  = group_text.strip()
    words = text.split()
    _EQUAL_PARTS = frozenset({
        'සමභාගව', 'සමබාගව', 'සමභාගවයි', 'මදට', 'මදටිය',
    })
    if any(tok in _EQUAL_PARTS for tok in words):
        return True
    if not (text.endswith('.') or text.endswith('යි') or text.endswith('වේ')):
        return False
    return len(words) >= 4 or 'යුතු' in text


def extract_stranded(rw):
    by_block = {}
    for w in rw:
        by_block.setdefault(wb(w), []).append(w)
    for w in (w for w in rw if wx(w) >= STRANDED_X):
        blk = by_block[wb(w)]
        if (len(blk) == 1
                and all(wx(b) >= STRANDED_X for b in blk)
                and _is_ingr_name(wt(w))):
            return wt(w)
    return None


# ── Entry builders ────────────────────────────────────────────────────────────
def _new_entry(num):
    e = {'අංකය': num, 'යෝග නාමය': '', 'යෝගය': []}
    for fk in FIELD_KEY.values():
        e[fk] = ''
    return e


def _make_ing(name, unit=None, amount=None, grams=None, litres=None):
    name = name.strip().rstrip(' –—-').strip()
    ing  = {'ද්‍රව්‍යය': name}
    if unit or amount:
        ing['ප්‍රමාණය'] = ' '.join(p for p in [unit, amount, 'යි'] if p)
    if grams:
        ing['ග්‍රෑ']  = f'ග්‍රෑ : {grams} යි'
    if litres:
        ing['ලී']     = f'ලීටර් : {litres} යි'
    return ing


def _append_text(entry, fkey, text):
    if not text:
        return
    sep = ' ' if entry[fkey] else ''
    entry[fkey] += sep + text


# ── State machine ─────────────────────────────────────────────────────────────
def extract_rows(rows, initial_state='PARTIAL', initial_fkey=None):
    """
    Process a list of row dicts and return:
      {'entries': [...], 'partial_tail': str,
       'final_state': str, 'final_fkey': str|None}
    Identical logic to extract_pharma_v4.py; adapted label/accessor layer above.
    """
    entries, partial = [], []
    current     = None
    state       = 'PARTIAL'
    active_fkey = None
    pending     = []

    def push():
        if current:
            if pending:
                flush_pending()
            for k, v in current.items():
                if isinstance(v, str):
                    current[k] = v.strip()
            entries.append(current)

    def flush_pending(unit=None, amount=None, grams=None, litres=None):
        for stub in pending:
            current['යෝගය'].append(_make_ing(stub, unit, amount, grams, litres))
        pending.clear()

    for row in rows:
        rw           = row['w']
        row_type, cw = classify_row(rw)

        # ── Entry header ──────────────────────────────────────────────────
        if row_type == 'ENTRY_HEADER':
            push()
            num     = int(wt(_entry_zone(rw)[0]).rstrip('.'))
            current = _new_entry(num)
            current['යෝග නාමය'] = to_text(cw)
            state, active_fkey  = 'ENTRY_HEADER', None
            pending.clear()
            continue

        # ── Bootstrap: rows before first entry on this page ───────────────
        if current is None:
            if row_type in LABEL_TO_STATE.values():
                current     = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state       = row_type
                active_fkey = FIELD_KEY.get(state)
                if cw and active_fkey:
                    _append_text(current, active_fkey, to_text(cw))
                continue
            elif row_type == 'SAYU':
                current     = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state, active_fkey = 'SAYU', FIELD_KEY['SAYU']
                if cw:
                    _append_text(current, active_fkey, to_text(cw))
                continue
            elif row_type == 'YOGAYA':
                current     = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state, active_fkey = 'YOGAYA', None
                continue
            elif row_type == 'CONTINUATION' and initial_state not in ('PARTIAL',):
                current     = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state       = initial_state
                active_fkey = initial_fkey
            else:
                partial.append(to_text(rw))
                continue

        # ── State transitions ─────────────────────────────────────────────
        if row_type in _TRANSITION_STATES:
            if state == 'YOGAYA':
                flush_pending()

            if row_type == 'SANSKARANAYA':
                stranded = extract_stranded(rw)
                if stranded:
                    current['යෝගය'].append(_make_ing(stranded))
                    cw = [w for w in cw if wt(w) != stranded]

            state       = row_type
            active_fkey = FIELD_KEY.get(state)

            if active_fkey:
                if cw:
                    _append_text(current, active_fkey, to_text(cw))
                continue

        # ── Dispatch by current state ──────────────────────────────────────
        if state == 'ENTRY_HEADER':
            if row_type == 'CONTINUATION' and cw:
                current['යෝග නාමය'] += ' ' + to_text(cw)

        elif state == 'YOGAYA':
            if not cw:
                continue
            first_cw = cw[0]

            if wt(first_cw) in UNIT_WORDS and wx(first_cw) > SHARED_QTY_X:
                parsed = parse_ingredient(cw)
                if parsed:
                    flush_pending(parsed[1], parsed[2], parsed[3], parsed[4])
            else:
                parsed = parse_ingredient(cw)
                if parsed is None:
                    continue
                name, unit, amount, grams, litres = parsed

                if unit is None:
                    for n in split_name_columns(cw):
                        if not _is_inline_instruction(n, rw):
                            pending.append(n)
                elif pending:
                    flush_pending(unit, amount, grams, litres)
                    if name:
                        current['යෝගය'].append(
                            _make_ing(name, unit, amount, grams, litres))
                else:
                    current['යෝගය'].append(
                        _make_ing(name, unit, amount, grams, litres))
                    # Check for a second name+qty pair on the same row
                    texts = [wt(w) for w in cw]
                    try:
                        fu  = texts.index(unit)
                        rem = cw[fu + 1:]
                        rtxt = [wt(w) for w in rem]
                        su  = next(
                            (i for i, t in enumerate(rtxt) if t in UNIT_WORDS),
                            None)
                        if su is not None:
                            r2 = parse_ingredient(rem[su - 1:] if su > 0 else rem)
                            if r2 and r2[0] and r2[1]:
                                current['යෝගය'].append(_make_ing(*r2))
                    except Exception:
                        pass

        elif active_fkey:
            if cw:
                _append_text(current, active_fkey, to_text(cw))

    push()
    return {
        'partial_tail': ' '.join(partial).strip(),
        'entries':      entries,
        'final_state':  state,
        'final_fkey':   active_fkey,
    }


# ── Cross-page continuation merge ─────────────────────────────────────────────
def _merge_continuation(entries_a, entries_b):
    if not (entries_a and entries_b and entries_b[0]['අංකය'] is None):
        return
    cont = entries_b.pop(0)
    last = entries_a[-1]
    for fk in FIELD_KEY.values():
        if cont.get(fk):
            sep = ' ' if last.get(fk) else ''
            last[fk] = (last.get(fk, '') + sep + cont[fk]).strip()
    last['යෝගය'].extend(cont.get('යෝගය', []))


# ── Main PDF processing ───────────────────────────────────────────────────────
def process_pdf(pdf_path, start_doc, end_doc, verbose=False):
    doc = fitz.open(str(pdf_path))
    total = len(doc)

    all_entries    = []
    current_section = ''
    prev_state     = 'PARTIAL'
    prev_fkey      = None

    for doc_page in range(start_doc, end_doc + 1):
        pdf_idx = doc_page + PDF_OFFSET
        if pdf_idx >= total:
            if verbose:
                print(f'  warning: doc page {doc_page} → PDF idx {pdf_idx} '
                      f'out of range ({total} pages)', file=sys.stderr)
            break

        rows, headers = page_to_rows(doc[pdf_idx])

        if headers:
            current_section = ' | '.join(headers)

        if not rows:
            continue

        result  = extract_rows(rows,
                               initial_state=prev_state,
                               initial_fkey=prev_fkey)
        entries = result['entries']

        for e in entries:
            e['source_page'] = doc_page
            if current_section:
                e['section'] = current_section

        _merge_continuation(all_entries, entries)
        all_entries.extend(entries)

        prev_state = result['final_state']
        prev_fkey  = result['final_fkey']

        if verbose:
            print(f'  page {doc_page:4d}  +{len(entries):3d} entries '
                  f'(total {len(all_entries)})')

    return all_entries


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description='Extract structured entries from the Ayurveda Pharmacopoeia PDF.')
    ap.add_argument('pdf', nargs='?', default=str(DEFAULT_PDF),
                    help='Path to Pharamacopoeia.pdf')
    ap.add_argument('--start', type=int, default=DEFAULT_START,
                    metavar='DOC_PAGE',
                    help=f'First document page to process (default {DEFAULT_START})')
    ap.add_argument('--end', type=int, default=DEFAULT_END,
                    metavar='DOC_PAGE',
                    help=f'Last document page to process (default {DEFAULT_END})')
    ap.add_argument('--out', default='pharma_structured.json',
                    help='Output JSON file (default pharma_structured.json)')
    ap.add_argument('--verbose', '-v', action='store_true',
                    help='Print per-page progress')
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f'PDF not found: {pdf_path}')

    print(f'Processing doc pages {args.start}–{args.end} from {pdf_path.name} …')
    entries = process_pdf(pdf_path, args.start, args.end, verbose=args.verbose)

    result = {'count': len(entries), 'entries': entries}
    out_path = Path(args.out)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f'OK  {out_path}  ({len(entries)} entries)')


if __name__ == '__main__':
    main()

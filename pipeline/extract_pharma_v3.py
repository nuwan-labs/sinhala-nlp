"""
extract_pharma_v3.py
────────────────────
Deterministic state machine for Ayurvedic pharmacopoeia pages.
Reads row-level compact JSON produced by shrink_ocr_v4.py.

INPUT FORMATS (auto-detected from JSON keys)
─────────────────────────────────────────────
  Single page  {"page": N, "rows": [...]}
  Pair         {"page_a": [...], "page_b": [...]}
  Batch        {"batch": "151-to-200", "pages": [{"page":N,"rows":[...]}, ...]}

BATCH MODE
──────────
All pages in a batch file are processed in sequence.  Cross-page continuation
entries (entries with no entry number at the top of a page) are automatically
merged into the last entry of the preceding page.  Every output entry carries
a "source_page" field for traceability.

Output schema (batch):
  {
    "batch":        "151-to-200",
    "entries":      [ {"source_page": 172, "අංකය": 1, ...}, ... ],
    "partial_tail": "..."          ← unresolved rows from the last page
  }

COLUMN ZONES  (x normalised to [0, 1])
───────────────────────────────────────
  x < 0.15            ENTRY_NUM   entry numbers  "44.", "45."
  0.15 ≤ x < 0.25     LABEL       field labels   "සංස්කරණය", "යෝගය"
  0.25 ≤ x < 0.32     SEP         OCR artefacts  ": -"
  x ≥ 0.32            CONTENT     all meaningful content

USAGE
─────
  python extract_pharma_v3.py <rows.json> [output.json]
  python extract_pharma_v3.py --pair <pair_rows.json> [output.json]  # legacy
"""

import json, re, sys
from pathlib import Path

# ── Zone thresholds ────────────────────────────────────────────────────────
ENTRY_NUM_X    = 0.15
LABEL_X_MAX    = 0.25
SEP_X_MAX      = 0.32
CONTENT_X      = 0.32
NAME_COL_GAP   = 0.15   # x-gap OR block_id change → new ingredient column
SHARED_QTY_X   = 0.45   # unit word at x > this → shared-quantity row
X_PRIMARY_INGR = 0.50   # right edge of primary ingredient-name zone
STRANDED_X     = 0.70   # minimum x for a stranded last-ingredient word

# ── Vocabulary ─────────────────────────────────────────────────────────────
UNIT_WORDS = {
    # Indian system
    'තෝලා',       # 12 g
    'කර්ෂ',       # 15 g  (Lankan) / 16 g (Indian)
    'කර්ෂා',      # alternate spelling
    'පල',         # 60 g  (also: පලං)
    'ශාණ',        # 4 g
    'මාෂ',        # 1 g
    'මාෂක',       # alternate spelling
    'කෝල',        # 8 g   (2 shana)
    'භාග',        # parts / ratio unit
    # Lankan system — pharmaceutical range
    'රක්තිකා',    # 125 mg
    'ගුංජා',      # 125 mg (OCR may read ගංජා → corrected below)
    'මංචාඩි',     # 250 mg
    'කලං',        # 5 g
    'අඩපලං',      # 30 g
    'ප්‍රසෘති',   # 120 g
    'අර්ධශරාව',   # 240 g
    'ශරාව',       # 480 g
    'ප්‍රස්ථ',    # 960 g
    'තේ හැඳි',    # teaspoon (two OCR tokens merged before unit detection)
}

# Multi-word units: each tuple is a sequence of consecutive OCR tokens that
# form a single unit.  They are merged in classify_row before any downstream
# function sees them, so UNIT_WORDS can treat them as a single string.
MULTI_WORD_UNITS = [
    ('තේ', 'හැඳි'),   # teaspoon
]

LABEL_TO_STATE = {
    'යෝගය':       'YOGAYA',
    'සංස්කරණය':   'SANSKARANAYA',
    'ප්‍රයෝග':    'PRAYOGA',
    'අනුපාන':     'ANUPANA',
    'මාත්‍රාව':   'MATRAVA',
}

FIELD_KEY = {
    'SANSKARANAYA': 'සංස්කරණය',
    'PRAYOGA':      'ප්‍රයෝග',
    'ANUPANA':      'අනුපාන',
    'MATRAVA':      'මාත්‍රාව',
    'SAYU':         'සටහන',
}

# All states that trigger a state transition (used in the main loop hot-path)
_TRANSITION_STATES = frozenset(FIELD_KEY) | {'YOGAYA'}

# ── Word accessors  (row word = [x, block_id, para_id, text]) ──────────────
_OCR_CORRECTIONS = {'ගංජා': 'ගුංජා'}

def wx(w): return w[0]
def wb(w): return w[1]
def wt(w): t = w[3]; return _OCR_CORRECTIONS.get(t, t)

# ── Zone helpers ───────────────────────────────────────────────────────────
_ENUM_RE = re.compile(r'^\d+\.?$')
_AMT_RE  = re.compile(r'^[\d][0-9./]*$|^1/2$')
_GRM_RE  = re.compile(r'^\d+$')

def _merge_multi_word_units(cw):
    """
    Scan content words for consecutive tokens that form a known multi-word unit
    (e.g. ['තේ', 'හැඳි']) and replace them with a single synthetic word whose
    text is the joined string ('තේ හැඳි'), preserving the first token's x /
    block_id / para_id.  This lets UNIT_WORDS contain the joined form as a
    plain string without changing any other detection logic.
    """
    if not cw or not MULTI_WORD_UNITS:
        return cw
    result, i = [], 0
    while i < len(cw):
        for unit_tup in MULTI_WORD_UNITS:
            n = len(unit_tup)
            if i + n <= len(cw) and tuple(wt(cw[i+j]) for j in range(n)) == unit_tup:
                # Merge: keep first word's spatial/block metadata, join text
                merged = [cw[i][0], cw[i][1], cw[i][2], ' '.join(unit_tup)]
                result.append(merged)
                i += n
                break
        else:
            result.append(cw[i])
            i += 1
    return result

def _entry_zone(rw): return [w for w in rw if wx(w) < ENTRY_NUM_X]
def _label_zone(rw): return [w for w in rw if ENTRY_NUM_X <= wx(w) < LABEL_X_MAX]

def _content_words(rw):
    """
    Content-zone words, sorted left→right.

    Normally the content zone starts at CONTENT_X (0.32), but some pages
    have a left ingredient column or formula-name prefix at x ≈ 0.311 — just
    inside the SEP zone (0.25–0.32).  Excluding the whole SEP zone would
    silently drop those words.

    Rule applied per word:
      x < LABEL_X_MAX (0.25)         → always exclude  (entry-num / label zones)
      LABEL_X_MAX ≤ x < CONTENT_X    → exclude only actual separator tokens
                                        (':', '-', '–', '—'); keep everything else
      x ≥ CONTENT_X (0.32)           → always include
    """
    _SEPS = frozenset((':', '-', '–', '—'))
    result = []
    for w in rw:
        x = wx(w)
        if x < LABEL_X_MAX:
            continue
        if x < CONTENT_X:                    # SEP zone
            if wt(w) in _SEPS:
                continue                     # genuine separator artefact
        result.append(w)
    return sorted(result, key=wx)

def to_text(ws): return ' '.join(wt(w) for w in ws).strip()

# ── Row classifier ─────────────────────────────────────────────────────────
def classify_row(rw):
    """Return (state_label, content_word_list) for a row."""
    cw = _merge_multi_word_units(_content_words(rw))

    en = _entry_zone(rw)
    if en and _ENUM_RE.match(wt(en[0])):
        return 'ENTRY_HEADER', cw

    lz = _label_zone(rw)
    if lz:
        labels = [wt(w) for w in lz]
        first  = labels[0]
        if first == 'සැ' and ':' in labels:
            return 'SAYU', cw
        if first in LABEL_TO_STATE:
            return LABEL_TO_STATE[first], cw

    return 'CONTINUATION', cw

# ── Ingredient helpers ─────────────────────────────────────────────────────
def split_name_columns(cw):
    """
    Split name-only content words into separate ingredient name strings.
    Splits on x-gap > NAME_COL_GAP OR on OCR block_id change.
    Block_id change catches multi-word ingredient names that shrink the gap
    below the threshold (e.g. 3-column layouts).
    """
    if not cw: return []
    groups, grp = [], [cw[0]]
    for i in range(1, len(cw)):
        if wx(cw[i]) - wx(cw[i-1]) > NAME_COL_GAP or wb(cw[i]) != wb(cw[i-1]):
            groups.append(to_text(grp)); grp = []
        grp.append(cw[i])
    groups.append(to_text(grp))
    return [g for g in groups if g]

def parse_ingredient(cw):
    """
    Parse content words → (name, unit, amount, grams).
    Returns None if cw is empty; returns (text, None, None, None) if no unit found.
    """
    if not cw: return None
    texts    = [wt(w) for w in cw]
    unit_idx = next((i for i, t in enumerate(texts) if t in UNIT_WORDS), None)
    if unit_idx is None:
        return to_text(cw), None, None, None

    name   = to_text(cw[:unit_idx])
    unit   = texts[unit_idx]
    tail   = texts[unit_idx + 1:]
    amount = next((t for t in tail if _AMT_RE.match(t)), None)
    grams  = None
    for i, t in enumerate(tail):
        if 'ග්‍රෑ' in t or t.startswith('ග්‍'):
            for g in tail[i + 1:]:
                if _GRM_RE.match(g): grams = g; break
            break
    return name.strip(), unit, amount, grams

def _is_ingr_name(text):
    """True if text looks like a short ingredient name (not a quantity)."""
    if not text or ',' in text: return False
    words = text.split()
    first = words[0]
    return (len(words) <= 3
            and first not in UNIT_WORDS
            and not first[0].isdigit()
            and first not in {'(', '–', '—', '_'})

def _is_inline_instruction(group_text, row_words):
    """
    True when a name-only group in YOGAYA is an in-text instruction
    ("සමභාගව ගත යුතු ය .") rather than an ingredient name.

    Two conditions must both hold:
      (a) The full row has no words in the primary ingredient column (x < 0.50).
          Every legitimate ingredient row has at least one name anchored there.
      (b) The group reads like a sentence: ends with "." and is ≥ 4 words,
          or contains the instruction marker "යුතු".
    """
    if any(CONTENT_X <= wx(w) < X_PRIMARY_INGR for w in row_words):
        return False   # left-column anchor present → keep all groups
    text = group_text.strip()
    if not text.endswith('.'): return False
    words = text.split()
    return len(words) >= 4 or 'යුතු' in text

def extract_stranded(rw):
    """
    On a SANSKARANAYA-transition row, return a stranded last-ingredient word
    if one exists: a single-word OCR block entirely at x ≥ STRANDED_X.
    """
    by_block = {}
    for w in rw: by_block.setdefault(wb(w), []).append(w)
    for w in (w for w in rw if wx(w) >= STRANDED_X):
        blk = by_block[wb(w)]
        if len(blk) == 1 and all(wx(b) >= STRANDED_X for b in blk) and _is_ingr_name(wt(w)):
            return wt(w)
    return None

# ── Entry / ingredient builders ────────────────────────────────────────────
def _new_entry(num):
    e = {'අංකය': num, 'යෝග නාමය': '', 'යෝගය': []}
    for fk in FIELD_KEY.values(): e[fk] = ''
    return e

def _make_ing(name, unit=None, amount=None, grams=None):
    name = name.strip().rstrip(' –—-').strip()
    ing  = {'ද්‍රව්‍යය': name}
    if unit or amount:
        ing['ප්‍රමාණය'] = ' '.join(p for p in [unit, amount, 'යි'] if p)
    if grams:
        ing['ග්‍රෑ'] = f'ග්‍රෑ : {grams} යි'
    return ing

def _append_text(entry, fkey, text):
    if not text: return
    sep = ' ' if entry[fkey] else ''
    entry[fkey] += sep + text

# ── State machine ──────────────────────────────────────────────────────────
def extract_rows(rows, initial_state='PARTIAL', initial_fkey=None):
    """
    Process a list of row dicts and return:
      {'partial_tail': str, 'entries': [entry_dict, ...]}
    """
    entries, partial = [], []
    current     = None
    state       = 'PARTIAL'
    active_fkey = None
    pending     = []   # name-only ingredient stubs waiting for a quantity

    def push():
        if current:
            if pending:          # name-only ingredients with no quantity yet
                flush_pending()  # flush them as-is before closing the entry
            for k, v in current.items():
                if isinstance(v, str): current[k] = v.strip()
            entries.append(current)

    def flush_pending(unit=None, amount=None, grams=None):
        for stub in pending:
            current['යෝගය'].append(_make_ing(stub, unit, amount, grams))
        pending.clear()

    for row in rows:
        rw            = row['w']
        row_type, cw  = classify_row(rw)

        # ── Entry header ─────────────────────────────────────────────────
        if row_type == 'ENTRY_HEADER':
            push()
            num     = int(wt(_entry_zone(rw)[0]).rstrip('.'))
            current = _new_entry(num)
            current['යෝග නාමය'] = to_text(cw)
            state, active_fkey  = 'ENTRY_HEADER', None
            pending.clear()
            continue

        # ── Bootstrap: rows before any entry on this page ────────────────
        if current is None:
            if row_type in LABEL_TO_STATE.values():
                current         = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state           = row_type
                active_fkey     = FIELD_KEY.get(state)
                if cw and active_fkey:
                    _append_text(current, active_fkey, to_text(cw))
                continue
            elif row_type == 'SAYU':
                current         = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state, active_fkey = 'SAYU', FIELD_KEY['SAYU']
                if cw: _append_text(current, active_fkey, to_text(cw))
                continue
            elif row_type == 'YOGAYA':
                current         = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state, active_fkey = 'YOGAYA', None
                continue
            elif row_type == 'CONTINUATION' and initial_state not in ('PARTIAL',):
                # The page starts with unlabelled rows that continue the
                # previous page's active state (e.g. ingredient names in
                # YOGAYA, or text in PRAYOGA).  Create a continuation entry
                # and fall through to the normal dispatch so the row is
                # processed in the correct state.
                current         = _new_entry(None)
                current['සටහන'] = '(continued from previous page)'
                state           = initial_state
                active_fkey     = initial_fkey
                # No continue — fall through to dispatch below
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

            # Text-field transition: append content and move to next row.
            # YOGAYA has no active_fkey, so falls through to dispatch below.
            if active_fkey:
                if cw: _append_text(current, active_fkey, to_text(cw))
                continue

        # ── Dispatch ──────────────────────────────────────────────────────
        if state == 'ENTRY_HEADER':
            if row_type == 'CONTINUATION' and cw:
                current['යෝග නාමය'] += ' ' + to_text(cw)

        elif state == 'YOGAYA':
            if not cw:
                continue

            first_cw = cw[0]

            # Shared-quantity row: unit is the FIRST content word, far right
            if wt(first_cw) in UNIT_WORDS and wx(first_cw) > SHARED_QTY_X:
                parsed = parse_ingredient(cw)
                if parsed:
                    flush_pending(parsed[1], parsed[2], parsed[3])

            else:
                parsed = parse_ingredient(cw)
                if parsed is None:
                    continue
                name, unit, amount, grams = parsed

                if unit is None:
                    # Name-only: split into columns, filter inline instructions
                    for n in split_name_columns(cw):
                        if not _is_inline_instruction(n, rw):
                            pending.append(n)

                elif pending:
                    # Pending names get this row's quantity
                    flush_pending(unit, amount, grams)
                    if name:
                        current['යෝගය'].append(_make_ing(name, unit, amount, grams))

                else:
                    current['යෝගය'].append(_make_ing(name, unit, amount, grams))
                    # Two-column layout: check for a second name+qty pair on
                    # the same row (e.g. "රසසින්දුර භාග 2 කස්තුරි භාග 1")
                    texts = [wt(w) for w in cw]
                    try:
                        fu   = texts.index(unit)
                        rem  = cw[fu + 1:]
                        rtxt = [wt(w) for w in rem]
                        su   = next((i for i, t in enumerate(rtxt) if t in UNIT_WORDS), None)
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
    return {'partial_tail': ' '.join(partial).strip(),
            'entries':      entries,
            'final_state':  state,
            'final_fkey':   active_fkey}

# ── Cross-page continuation merge ──────────────────────────────────────────
def _merge_continuation(entries_a, entries_b):
    """
    If entries_b starts with a None-numbered (continuation) entry, merge its
    fields into the last entry of entries_a.  Mutates both lists in place.
    """
    if not (entries_a and entries_b and entries_b[0]['අංකය'] is None):
        return
    cont = entries_b.pop(0)
    last = entries_a[-1]
    for fk in FIELD_KEY.values():
        if cont.get(fk):
            sep = ' ' if last.get(fk) else ''
            last[fk] = (last.get(fk, '') + sep + cont[fk]).strip()
    last['යෝගය'].extend(cont.get('යෝගය', []))

# ── Processing modes ────────────────────────────────────────────────────────
def _process_single(data):
    """Single-page format: {"page": N, "rows": [...]}."""
    r = extract_rows(data['rows'])
    r['source_page'] = data.get('page')
    return r

def _process_pair(data):
    """Pair format: {"page_a": [...], "page_b": [...]}."""
    ra = extract_rows(data['page_a'])
    rb = extract_rows(data['page_b'])
    _merge_continuation(ra['entries'], rb['entries'])
    return {
        'source_pages': data.get('pages', [None, None]),
        'entries':      ra['entries'] + rb['entries'],
        'partial_tail': ra.get('partial_tail', ''),
    }

def _process_batch(data):
    """
    Batch format: {"batch": "...", "pages": [{"page": N, "rows": [...]}, ...]}.

    Pages are processed sequentially.  Each page's continuation entry is
    merged into the last entry of the previous page.  Every output entry
    carries a "source_page" field.
    """
    all_entries   = []
    last_partial  = ''

    prev_state = 'PARTIAL'   # final state of the previous page
    prev_fkey  = None        # final active_fkey of the previous page

    for pg in data['pages']:
        result  = extract_rows(pg['rows'],
                               initial_state=prev_state,
                               initial_fkey=prev_fkey)
        entries = result['entries']

        for e in entries:
            e['source_page'] = pg['page']

        _merge_continuation(all_entries, entries)
        all_entries.extend(entries)
        last_partial = result.get('partial_tail', '')

        prev_state = result['final_state']
        prev_fkey  = result['final_fkey']

    return {
        'batch':        data.get('batch'),
        'entries':      all_entries,
        'partial_tail': last_partial,
    }

# ── Auto-detect format and dispatch ────────────────────────────────────────
def process_file(path):
    """Load a rows JSON file, auto-detect its format, and return structured output."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    # Batch: {"batch": "...", "pages": [{"page": N, "rows": [...]}, ...]}
    if ('pages' in data
            and isinstance(data['pages'], list)
            and data['pages']
            and 'rows' in data['pages'][0]):
        return _process_batch(data)

    # Pair: {"page_a": [...], "page_b": [...]}
    if 'page_a' in data:
        return _process_pair(data)

    # Single page: {"page": N, "rows": [...]}
    return _process_single(data)

# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    if not args: print(__doc__); sys.exit(1)

    # Legacy --pair flag still accepted (format is now auto-detected)
    if args[0] == '--pair':
        args = args[1:]

    inp = args[0]
    out = args[1] if len(args) >= 2 else None

    result = process_file(inp)

    if out is None:
        stem = Path(inp).stem.replace('_rows', '')
        out  = stem + '_structured.json'

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    n    = len(result.get('entries', []))
    mode = ('batch'  if 'batch'        in result else
            'pair'   if 'source_pages' in result else 'single')
    print(f'✓ {out}  ({n} entries, {mode} mode)')

if __name__ == '__main__': main()

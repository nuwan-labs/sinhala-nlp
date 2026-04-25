"""
NLP Statistics Report for Sinhala Ayurvedic Pharmacopoeia Dataset
"""
import json, os, re, sys, io, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FILES = [
    '151-to-200_structured.json',
    '201-to-250_structured.json',
    '251-to-300_structured.json',
    '301-to-350_structured.json',
    '351-to-400_structured.json',
    '401-to-450_structured.json',
]

FIELDS = ['සංස්කරණය', 'ප්‍රයෝග', 'අනුපාන', 'මාත්‍රාව', 'සටහන']
FIELD_LABELS = {
    'සංස්කරණය':     'Preparation',
    'ප්‍රයෝග': 'Usage/Indication',
    'අනුපාන':        'Anupana',
    'මාත්‍රාව': 'Dosage',
    'සටහන':          'Notes',
}
ING_KEY   = 'ද්‍රව්‍යය'
NAME_KEY  = 'යෝග නාමය'
YOGAYA    = 'යෝගය'

# ── helpers ──────────────────────────────────────────────────────────────────

def tokenize(text):
    """Split on whitespace; keep Sinhala punctuation attached, strip stray ASCII."""
    return [t for t in text.split() if t]

def is_artefact(token):
    """True if token is likely an OCR/structural artefact."""
    return bool(re.fullmatch(r'[\W\d]+', token, re.UNICODE))

def nfc(s): return unicodedata.normalize('NFC', s)
def nfd(s): return unicodedata.normalize('NFD', s)

def has_zwj(s): return '‍' in s

# ── load ─────────────────────────────────────────────────────────────────────

all_entries = []
for f in FILES:
    if os.path.exists(f):
        obj = json.load(open(f, encoding='utf-8'))
        all_entries.extend(obj.get('entries', []))

N = len(all_entries)

# ── section printer ───────────────────────────────────────────────────────────

SEP  = '=' * 70
SEP2 = '-' * 70

def section(title):
    print(f'\n{SEP}')
    print(f'  {title}')
    print(SEP)

def subsection(title):
    print(f'\n{SEP2}')
    print(f'  {title}')
    print(SEP2)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATASET OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
section('1. DATASET OVERVIEW')

entries_with_ing = sum(1 for e in all_entries if e.get(YOGAYA))
formula_names    = [e.get(NAME_KEY, '') for e in all_entries]
unique_names     = set(nfc(n) for n in formula_names if n)

print(f'  Total formula entries       : {N}')
print(f'  Entries with ingredients    : {entries_with_ing}  ({100*entries_with_ing/N:.1f}%)')
print(f'  Formula names present       : {sum(1 for n in formula_names if n)}')
print(f'  Unique formula names (NFC)  : {len(unique_names)}')

# source page range
pages = [e.get('source_page') for e in all_entries if e.get('source_page')]
print(f'  Source page range           : {min(pages)} – {max(pages)}')

# ── field fill rates ──────────────────────────────────────────────────────────
subsection('Field Fill Rates')
print(f'  {"Field":<22} {"Label":<20} {"Filled":>6}  {"Rate":>6}')
print(f'  {"-"*22} {"-"*20} {"-"*6}  {"-"*6}')
for fk, label in FIELD_LABELS.items():
    n = sum(1 for e in all_entries if e.get(fk, '').strip())
    print(f'  {fk:<22} {label:<20} {n:>6}  {100*n/N:>5.1f}%')

# ── entries per batch ─────────────────────────────────────────────────────────
subsection('Entries per Batch File')
for f in FILES:
    if os.path.exists(f):
        obj = json.load(open(f, encoding='utf-8'))
        cnt = len(obj.get('entries', []))
        label = Path(f).stem.replace('_structured', '')
        print(f'  {label:<35} {cnt:>4} entries')

# ═══════════════════════════════════════════════════════════════════════════════
# 2. INGREDIENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
section('2. INGREDIENT ANALYSIS')

ing_cells    = []   # raw cell texts
ing_tokens_all = [] # individual tokens across all cells

for e in all_entries:
    for ing in e.get(YOGAYA, []):
        cell = ing.get(ING_KEY, '').strip()
        if cell:
            ing_cells.append(cell)
            ing_tokens_all.extend(tokenize(cell))

print(f'  Ingredient cells (rows)     : {len(ing_cells)}')
print(f'  Avg ingredients per entry   : {len(ing_cells)/max(entries_with_ing,1):.1f}')
print(f'  Total ingredient tokens     : {len(ing_tokens_all)}')
print(f'  Unique ingredient tokens    : {len(set(ing_tokens_all))}')

# artefact detection
artefacts = [t for t in ing_tokens_all if is_artefact(t)]
print(f'  Artefact tokens             : {len(artefacts)}  ({100*len(artefacts)/max(len(ing_tokens_all),1):.1f}%)')

# ingredient frequency
ing_counter = Counter(nfc(c) for c in ing_cells)
subsection('Top 20 Most Frequent Ingredient Cells (NFC normalised)')
for cell, cnt in ing_counter.most_common(20):
    print(f'  {cnt:>4}x  {cell}')

subsection('Ingredient Cell Length Distribution')
lengths = [len(tokenize(c)) for c in ing_cells]
from statistics import mean, median, stdev
print(f'  Min tokens per cell         : {min(lengths)}')
print(f'  Max tokens per cell         : {max(lengths)}')
print(f'  Mean                        : {mean(lengths):.2f}')
print(f'  Median                      : {median(lengths):.1f}')
print(f'  Std dev                     : {stdev(lengths):.2f}')

# cells with >8 tokens likely bleed preparation prose
bleed = sum(1 for l in lengths if l > 8)
print(f'  Cells >8 tokens (prose bleed): {bleed}  ({100*bleed/max(len(lengths),1):.1f}%)')

# ═══════════════════════════════════════════════════════════════════════════════
# 3. VOCABULARY STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════
section('3. VOCABULARY STATISTICS')

# collect ALL tokens across all text fields
all_tokens = list(ing_tokens_all)
for e in all_entries:
    for fk in FIELDS:
        val = e.get(fk, '').strip()
        if val:
            all_tokens.extend(tokenize(val))
    name = e.get(NAME_KEY, '').strip()
    if name:
        all_tokens.extend(tokenize(name))

vocab = Counter(nfc(t) for t in all_tokens)
V = len(vocab)
T = sum(vocab.values())

print(f'  Total tokens (all fields)   : {T:,}')
print(f'  Vocabulary size (types)     : {V:,}')
print(f'  Type-Token Ratio (TTR)      : {V/T:.4f}')
print(f'  Hapax legomena (freq=1)     : {sum(1 for c in vocab.values() if c==1):,}  ({100*sum(1 for c in vocab.values() if c==1)/V:.1f}% of vocab)')
print(f'  Dis legomena   (freq=2)     : {sum(1 for c in vocab.values() if c==2):,}')

subsection('Top 30 Most Frequent Tokens (all fields)')
print(f'  {"Token":<30} {"Count":>6}  {"% of tokens":>10}')
print(f'  {"-"*30} {"-"*6}  {"-"*10}')
for tok, cnt in vocab.most_common(30):
    print(f'  {tok:<30} {cnt:>6}  {100*cnt/T:>9.2f}%')

subsection('Zipf Law Check (log-rank vs log-freq, first 10)')
print(f'  {"Rank":>5}  {"Token":<25} {"Freq":>6}  {"Expected(Zipf)":>14}')
print(f'  {"-"*5}  {"-"*25} {"-"*6}  {"-"*14}')
top = vocab.most_common(10)
f1 = top[0][1]
for i, (tok, cnt) in enumerate(top, 1):
    expected = f1 / i
    print(f'  {i:>5}  {tok:<25} {cnt:>6}  {expected:>14.1f}')

# ═══════════════════════════════════════════════════════════════════════════════
# 4. FORMULA NAME ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
section('4. FORMULA NAME ANALYSIS')

names = [e.get(NAME_KEY, '').strip() for e in all_entries if e.get(NAME_KEY, '').strip()]
name_tokens = [t for n in names for t in tokenize(n)]
name_vocab  = Counter(nfc(t) for t in name_tokens)

print(f'  Entries with formula name   : {len(names)}  ({100*len(names)/N:.1f}%)')
print(f'  Unique names (raw)          : {len(set(names))}')
print(f'  Unique names (NFC)          : {len(set(nfc(n) for n in names))}')
print(f'  Names that differ NFC vs raw: {sum(1 for n in names if nfc(n) != n)}  ({100*sum(1 for n in names if nfc(n)!=n)/len(names):.1f}%)')
print(f'  Names containing ZWJ        : {sum(1 for n in names if has_zwj(n))}')
print(f'  Name token total            : {len(name_tokens)}')
print(f'  Name vocabulary size        : {len(name_vocab)}')

name_lengths = [len(tokenize(n)) for n in names]
print(f'  Avg tokens per name         : {mean(name_lengths):.2f}')
print(f'  Max tokens per name         : {max(name_lengths)}')

subsection('Top 20 Tokens in Formula Names')
for tok, cnt in name_vocab.most_common(20):
    print(f'  {cnt:>4}x  {tok}')

# ═══════════════════════════════════════════════════════════════════════════════
# 5. TEXT FIELD ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════
section('5. TEXT FIELD ANALYSIS (Preparation / Usage / Anupana / Dosage / Notes)')

for fk, label in FIELD_LABELS.items():
    vals = [e.get(fk, '').strip() for e in all_entries if e.get(fk, '').strip()]
    if not vals:
        continue
    toks = [t for v in vals for t in tokenize(v)]
    lengths = [len(tokenize(v)) for v in vals]
    subsection(f'{label}  [{fk}]  —  {len(vals)} entries')
    print(f'  Fill rate                   : {100*len(vals)/N:.1f}%')
    print(f'  Total tokens                : {len(toks):,}')
    print(f'  Unique tokens               : {len(set(toks)):,}')
    print(f'  Avg words per entry         : {mean(lengths):.1f}')
    print(f'  Median words per entry      : {median(lengths):.1f}')
    print(f'  Max words per entry         : {max(lengths)}')
    top5 = Counter(nfc(t) for t in toks).most_common(5)
    print(f'  Top 5 tokens                : {", ".join(f"{t}({c})" for t,c in top5)}')

# ═══════════════════════════════════════════════════════════════════════════════
# 6. UNICODE / ENCODING QUALITY
# ═══════════════════════════════════════════════════════════════════════════════
section('6. UNICODE & ENCODING QUALITY')

zwj_in_keys = 0
nfc_fail_names = 0
nfd_fail_names = 0

for e in all_entries:
    for k in e.keys():
        if has_zwj(k): zwj_in_keys += 1
    name = e.get(NAME_KEY, '')
    if name and nfc(name) != name: nfc_fail_names += 1
    if name and nfd(name) != name: nfd_fail_names += 1

print(f'  Entry keys containing ZWJ   : {zwj_in_keys}')
print(f'  Formula names failing NFC   : {nfc_fail_names}  ({100*nfc_fail_names/max(len(names),1):.1f}%)')
print(f'  Formula names failing NFD   : {nfd_fail_names}  ({100*nfd_fail_names/max(len(names),1):.1f}%)')

# count ZWJ in all ingredient text
zwj_ing = sum(1 for c in ing_cells if has_zwj(c))
print(f'  Ingredient cells with ZWJ   : {zwj_ing}  ({100*zwj_ing/max(len(ing_cells),1):.1f}%)')

# ═══════════════════════════════════════════════════════════════════════════════
# 7. CO-OCCURRENCE (ingredient pairs)
# ═══════════════════════════════════════════════════════════════════════════════
section('7. INGREDIENT TOKEN CO-OCCURRENCE (top 20 pairs)')

from itertools import combinations

pair_counter = Counter()
for e in all_entries:
    entry_toks = set()
    for ing in e.get(YOGAYA, []):
        cell = ing.get(ING_KEY, '').strip()
        for t in tokenize(cell):
            nt = nfc(t)
            if not is_artefact(nt) and len(nt) > 1:
                entry_toks.add(nt)
    for a, b in combinations(sorted(entry_toks), 2):
        pair_counter[(a, b)] += 1

print(f'  {"Token A":<20} {"Token B":<20} {"Co-occur":>8}')
print(f'  {"-"*20} {"-"*20} {"-"*8}')
for (a, b), cnt in pair_counter.most_common(20):
    print(f'  {a:<20} {b:<20} {cnt:>8}')

# ═══════════════════════════════════════════════════════════════════════════════
# 8. LABELLING EFFORT ESTIMATE
# ═══════════════════════════════════════════════════════════════════════════════
section('8. LABELLING EFFORT ESTIMATE')

print('  Assuming 2 min/entry for token-level NER annotation:')
targets = [50, 100, 200, 300, 500, 707]
for t in targets:
    mins = t * 2
    hrs  = mins / 60
    print(f'    {t:>4} entries  →  {mins:>4} min  ({hrs:.1f} hrs)')

print()
print('  Minimum recommended for:')
print('    CRF NER baseline         : ~100 entries  (3.3 hrs)')
print('    Transformer fine-tune    : ~500 entries  (16.7 hrs)  — marginal')
print('    Full corpus labelled     :  707 entries  (23.6 hrs)')

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
section('SUMMARY')
print(f'  Entries                     : {N}')
print(f'  Total tokens                : {T:,}')
print(f'  Vocabulary size             : {V:,}')
print(f'  TTR                         : {V/T:.4f}')
print(f'  Ingredient cells            : {len(ing_cells):,}')
print(f'  Artefact token rate         : {100*len(artefacts)/max(len(ing_tokens_all),1):.1f}%')
print(f'  NFC failure rate (names)    : {100*nfc_fail_names/max(len(names),1):.1f}%')
print(f'  Prose bleed rate (ing)      : {100*bleed/max(len(lengths),1):.1f}%')
print()
print('  NLP tasks feasible at current size:')
print('    [YES] Descriptive statistics & frequency analysis')
print('    [YES] Vocabulary / Zipf analysis')
print('    [YES] TF-IDF clustering of Usage/Indication field')
print('    [YES] Ingredient co-occurrence network')
print('    [YES] Rule-based ingredient normalisation')
print('    [~  ] CRF NER  (100+ labelled entries needed)')
print('    [ NO] Transformer fine-tuning without augmentation')
print()

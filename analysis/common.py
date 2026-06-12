"""
Common utilities for the verification analysis.

Loads the structured Pharmacopoeia corpus, the reachable baselines, the
lexicons, and provides the segmentation units used throughout RQ1/RQ2.

Epistemic-contract notes:
  * One global seed (SEED) is pinned here and reused everywhere.
  * yogamalawa/ is NEVER loaded.  load_structured() globs only the six
    top-level *_structured.json files and asserts no yogamalawa path leaks in.
"""
from __future__ import annotations
import glob
import json
import os
import unicodedata
from pathlib import Path

import numpy as np
import regex as re

SEED = 20260611
RNG = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

# ---- field schema (Sinhala keys) ------------------------------------------
NAME = "යෝග නාමය"          # formula name
YOG = "යෝගය"               # constituents block (list of {ING: text})
ING = "ද්‍රව්‍යය"           # a constituent substance line
F_PREP = "සංස්කරණය"        # preparation
F_INDIC = "ප්‍රයෝග"        # indication / usage
F_VEHIC = "අනුපාන"         # accompanying substance (anupana)
F_DOSE = "මාත්‍රාව"        # dosage
F_NOTE = "සටහන"            # note (NOT one of the proposal's six fields)

# the proposal's "six fields": name, constituents, preparation, indication,
# dosage, accompanying substance.  Notes are excluded from the six-field counts.
TEXT_FIELDS_NONCONSTIT = [F_PREP, F_INDIC, F_VEHIC, F_DOSE]


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ---- corpus loading --------------------------------------------------------
def _structured_files():
    files = sorted(glob.glob(str(DATA / "structured" / "*_structured.json")))
    # GUARDRAIL: never touch yogamalawa
    files = [f for f in files if "yogamalawa" not in f]
    assert all("yogamalawa" not in f for f in files), "yogamalawa leaked into load"
    return files


def load_raw_entries():
    ents = []
    for f in _structured_files():
        ents += json.load(open(f, encoding="utf-8"))["entries"]
    return ents


def _is_continuation(e) -> bool:
    note = (e.get(F_NOTE) or "")
    return "continued" in note.lower()


def load_formulas(dedup="name_page"):
    """Dedup rule (PRE-REGISTERED, see report): a *formula* is an entry with a
    non-empty name.  Continuation FRAGMENTS are the *unnamed* rows (dropped by
    the name test); a "(continued from previous page)" note on a *named* entry
    marks a real formula whose layout spilled across a page and is KEPT.
    Exact duplicates are collapsed by ``dedup`` key:
        "name_page" -> (name, source_page)   [default]
        "name"      -> name only
        "none"      -> keep all named entries
    Returns list of entry dicts."""
    ents = load_raw_entries()
    formulas = []
    seen = set()
    for e in ents:
        name = (e.get(NAME) or "").strip()
        if not name:
            continue
        if dedup == "name_page":
            key = (name, e.get("source_page"))
        elif dedup == "name":
            key = name
        else:
            key = object()  # unique -> never collapses
        if key in seen:
            continue
        seen.add(key)
        formulas.append(e)
    return formulas


def constituent_lines(e):
    out = []
    for c in (e.get(YOG) or []):
        t = (c.get(ING) or "").strip()
        if t:
            out.append(t)
    return out


def formula_field_texts(e):
    """Return dict field_name -> text for the six proposal fields."""
    d = {
        "name": (e.get(NAME) or "").strip(),
        "constituents": " ".join(constituent_lines(e)),
        "preparation": (e.get(F_PREP) or "").strip(),
        "indication": (e.get(F_INDIC) or "").strip(),
        "dosage": (e.get(F_DOSE) or "").strip(),
        "vehicle": (e.get(F_VEHIC) or "").strip(),
    }
    return d


def formula_text(e) -> str:
    d = formula_field_texts(e)
    order = ["name", "constituents", "preparation", "indication", "dosage", "vehicle"]
    return " ".join(d[k] for k in order if d[k])


def corpus_text() -> str:
    return " ".join(formula_text(e) for e in load_formulas())


def corpus_tokens():
    return corpus_text().split()


# ---- baselines -------------------------------------------------------------
def load_news_tokens():
    p = DATA / "baselines" / "news_tokens.txt"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8").split()


def load_news_text():
    toks = load_news_tokens()
    return " ".join(toks) if toks else None


def load_gov_text():
    p = DATA / "baselines" / "gov_sinhala.txt"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def load_gov_tokens():
    t = load_gov_text()
    return t.split() if t else []


# ---- lexicons --------------------------------------------------------------
def load_json(name):
    return json.load(open(DATA / "lexicons" / name, encoding="utf-8"))


# ---- segmentation units ----------------------------------------------------
# Sinhala block helpers
_VIRAMA = "්"   # al-lakuna
_ZWJ = "‍"
_GRAPHEME_RE = re.compile(r"\X")


def seg_words(text):
    return text.split()


def seg_codepoints(text):
    # codepoints of the non-space content (units are characters)
    return list(text)


def seg_bytes(text):
    return list(text.encode("utf-8"))


def seg_graphemes(text):
    """Unicode extended grapheme clusters (regex \\X)."""
    return _GRAPHEME_RE.findall(text)


def seg_aksharas(text):
    """Orthographic syllables (aksharas).  Built from grapheme clusters by
    merging a cluster that ends in virama (optionally virama+ZWJ) with the
    following cluster, so conjunct consonants form ONE akshara.  This is the
    rule-based orthographic-syllable unit; its divergence from raw grapheme
    clusters is reported in C1."""
    gcs = seg_graphemes(text)
    out = []
    buf = ""
    for g in gcs:
        # never merge across whitespace / non-letter boundaries
        if buf and (g.isspace() or not any(c.isalpha() for c in g)):
            out.append(buf)
            buf = ""
        buf += g
        stripped = g.rstrip(_ZWJ)
        if stripped.endswith(_VIRAMA) and g.strip():
            continue  # consonant binding -> keep merging into one akshara
        out.append(buf)
        buf = ""
    if buf:
        out.append(buf)
    return out


SEGMENTERS = {
    "word": seg_words,
    "akshara": seg_aksharas,
    "grapheme": seg_graphemes,
    "codepoint": seg_codepoints,
    "byte": seg_bytes,
}


def is_artefact_token(tok: str) -> bool:
    """token that is pure punctuation/digits/latin (OCR/structural noise)."""
    return bool(re.fullmatch(r"[\P{L}\d]+", tok)) or bool(re.fullmatch(r"[A-Za-z\d\W]+", tok))


# Sinhala script codepoint test
def is_sinhala_cp(ch: str) -> bool:
    return "඀" <= ch <= "෿" or ch == _ZWJ

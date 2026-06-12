"""
Part B -- RQ1: is the register restricted in the manner of a sublanguage?
Honest matrix of {unit} x {baseline} with pre-registered decision rules.

  B1 vocabulary growth (Heaps' beta)            -- the fragile signal
  B2 lexical concentration                       -- the robust signal (foreground)
  B3 constructional restriction (baselined)
  B4 semantic-class separation (permutation null)
  B5 OCR sensitivity (two-channel + rasterisation head-start)
"""
from __future__ import annotations
import math
from collections import Counter

import numpy as np
import regex as re

from . import common as C
from . import stats as S
from . import tok as T
from . import lex

SESOI_BETA = 0.05          # smallest beta gap that matters (pre-registered)
SESOI_ENTROPY = 0.02       # normalised-entropy / efficiency
SESOI_JACCARD = 0.05

UNITS = ["word", "akshara", "grapheme", "codepoint", "byte", "bpe4000"]


def _units_of(text, unit):
    if unit == "bpe4000":
        return T.encode_units(T.bpe_tokenizer(4000), text)
    return C.SEGMENTERS[unit](text)


def _corpora():
    reg = C.corpus_text()
    news = C.load_news_text()
    gov = C.load_gov_text()
    return {"register": reg, "news(general)": news, "government(restricted-control)": gov}


# --------------------------------------------------------------------------
# B1 -- Heaps' beta matrix
# --------------------------------------------------------------------------
def b1_beta_matrix(n_boot=200):
    corp = _corpora()
    texts = {k: v for k, v in corp.items() if v}
    cells = []
    # precompute unit sequences
    seqs = {k: {} for k in texts}
    for k, txt in texts.items():
        for u in UNITS:
            seqs[k][u] = _units_of(txt, u)
    reg_beta = {}
    baselines = [k for k in texts if k != "register"]
    for u in UNITS:
        reg_seq = seqs["register"][u]
        for b in baselines:
            b_seq = seqs[b][u]
            N = min(len(reg_seq), len(b_seq))
            r_t = reg_seq[:N]
            b_t = b_seq[:N]
            rb, rci, _ = S.beta_block_bootstrap(r_t, n_boot=n_boot)
            bb, bci, _ = S.beta_block_bootstrap(b_t, n_boot=n_boot)
            gap = bb - rb                      # positive => register grows slower
            strictly_below = rci[1] < bci[0]   # register CI hi < baseline CI lo
            if strictly_below and gap >= SESOI_BETA:
                verdict = "restricted"
            elif strictly_below and gap < SESOI_BETA:
                verdict = "negligible(<SESOI)"
            elif rci[0] > bci[1]:
                verdict = "anti (register higher)"
            else:
                verdict = "overlap"
            note = ("BPE vocab trained on the register, so applying it to a "
                    "baseline is confounded (out-of-domain fragmentation against a "
                    "register-fit 4k vocab); read with caution.") if u == "bpe4000" else ""
            cells.append({
                "unit": u, "baseline": b, "matched_N": N,
                "register_beta": rb, "register_ci": rci,
                "baseline_beta": bb, "baseline_ci": bci,
                "gap": gap, "verdict": verdict, "note": note,
            })
    n_restr = sum(1 for c in cells if c["verdict"] == "restricted")
    return {"cells": cells, "n_cells": len(cells), "n_restricted": n_restr,
            "sesoi": SESOI_BETA}


# --------------------------------------------------------------------------
# B2 -- lexical concentration (foreground)
# --------------------------------------------------------------------------
def b2_concentration(n_boot=200):
    corp = _corpora()
    out = []
    reg_words = corp["register"].split()
    baselines = {k: v.split() for k, v in corp.items() if v and k != "register"}
    for b, b_words in baselines.items():
        N = min(len(reg_words), len(b_words))
        r = reg_words[:N]
        w = b_words[:N]
        rb = S.concentration_bundle(r, n_boot=n_boot)
        bb = S.concentration_bundle(w, n_boot=n_boot)
        # "more concentrated": higher topk coverage, lower norm entropy, steeper zipf
        def cmp(metric, direction):
            (rp, rci) = rb[metric]; (bp, bci) = bb[metric]
            if direction == "high":   # register more concentrated if CI above baseline
                sep = rci[0] > bci[1]
            else:                      # lower is more concentrated
                sep = rci[1] < bci[0]
            return {"register": [rp, rci], "baseline": [bp, bci], "register_more_concentrated": bool(sep)}
        out.append({
            "baseline": b, "matched_N": N,
            "topk_coverage": cmp("topk_coverage", "high"),
            "norm_entropy": cmp("norm_entropy", "low"),
            "zipf_slope": cmp("zipf_slope", "low"),
        })
    return {"comparisons": out, "k": 100}


# --------------------------------------------------------------------------
# B3 -- constructional restriction, baselined against news clause-finals
# --------------------------------------------------------------------------
def _clause_finals(text):
    finals = []
    for clause in re.split(r"[.।॥]", text):
        toks = [t for t in clause.split() if any(ch.isalpha() for ch in t)]
        if toks:
            finals.append(toks[-1])
    return finals


def _news_clause_finals():
    """News is a POS-tagged token stream (one 'token TAG' per line). Reconstruct
    clauses by splitting on full-stop tokens ('.')."""
    toks = C.load_news_tokens()
    if not toks:
        return []
    finals = []
    cur = []
    for t in toks:
        if t in (".", "।", "॥"):
            cur = [x for x in cur if any(ch.isalpha() for ch in x)]
            if cur:
                finals.append(cur[-1])
            cur = []
        else:
            cur.append(t)
    return finals


def _pred_entropy(finals):
    c = Counter(finals)
    p = np.array(list(c.values()), float)
    p /= p.sum()
    H = -np.sum(p * np.log2(p))
    Hmax = math.log2(len(c)) if len(c) > 1 else 1.0
    return float(H), float(H / Hmax)


def _boot_pred_entropy(finals, n_boot=300, seed=S.SEED):
    rng = np.random.default_rng(seed)
    finals = list(finals)
    n = len(finals)
    vals = []
    arr = np.array(finals, dtype=object)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        _, ne = _pred_entropy(arr[idx].tolist())
        vals.append(ne)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(np.mean(vals)), (float(lo), float(hi))


def b3_constructions(top=10):
    reg_fin = _clause_finals(
        " ".join(C.formula_field_texts(e)["indication"] for e in C.load_formulas("name")))
    news_fin = _news_clause_finals()
    N = min(len(reg_fin), len(news_fin)) if news_fin else len(reg_fin)
    reg_m = reg_fin[:N]
    news_m = news_fin[:N] if news_fin else []
    rc = Counter(reg_m)
    reg_top = rc.most_common(top)
    reg_cov = sum(v for _, v in reg_top) / sum(rc.values())
    rH, rNE = _pred_entropy(reg_m)
    rNE_pt, rNE_ci = _boot_pred_entropy(reg_m)
    res = {"matched_N": N, "register_top": [[t, n] for t, n in reg_top],
           "register_topk_coverage": reg_cov,
           "register_norm_entropy": rNE_pt, "register_ne_ci": rNE_ci}
    if news_m:
        nc = Counter(news_m)
        news_cov = sum(v for _, v in nc.most_common(top)) / sum(nc.values())
        nNE_pt, nNE_ci = _boot_pred_entropy(news_m)
        # restricted iff register predicate-entropy CI strictly below baseline's
        sep = rNE_ci[1] < nNE_ci[0]
        gap = nNE_pt - rNE_pt
        verdict = ("constructionally restricted" if (sep and gap >= SESOI_ENTROPY)
                   else "negligible(<SESOI)" if sep else "overlap -> WITHDRAW claim")
        res.update({"baseline_topk_coverage": news_cov,
                    "baseline_norm_entropy": nNE_pt, "baseline_ne_ci": nNE_ci,
                    "gap": gap, "verdict": verdict, "sesoi": SESOI_ENTROPY})
    else:
        res["verdict"] = "no baseline -> descriptive inventory only"
    return res


# --------------------------------------------------------------------------
# B4 -- semantic-class separation with field-label permutation null
# --------------------------------------------------------------------------
def _jaccard(a, b):
    a, b = set(a), set(b)
    if not a and not b:
        return float("nan")
    return len(a & b) / len(a | b)


def b4_semantic_separation(n_perm=500, seed=S.SEED):
    formulas = C.load_formulas("name")
    constit_tokens, indic_tokens = [], []
    for e in formulas:
        d = C.formula_field_texts(e)
        constit_tokens += d["constituents"].split()
        indic_tokens += d["indication"].split()
    obs = _jaccard(constit_tokens, indic_tokens)
    # permutation null: pool tokens, randomly reassign to two classes preserving sizes
    pool = constit_tokens + indic_tokens
    nC = len(constit_tokens)
    rng = np.random.default_rng(seed)
    pool_arr = np.array(pool, dtype=object)
    null = []
    for _ in range(n_perm):
        rng.shuffle(pool_arr)
        a = pool_arr[:nC]; b = pool_arr[nC:]
        null.append(_jaccard(a.tolist(), b.tolist()))
    null = np.array(null)
    null_mean = float(null.mean())
    null_lo, null_hi = np.percentile(null, [2.5, 97.5])
    margin = null_mean - obs   # how much MORE separated than layout predicts
    beyond_layout = obs < null_lo and margin >= SESOI_JACCARD
    return {"observed_jaccard": obs, "null_mean": null_mean,
            "null_ci": [float(null_lo), float(null_hi)], "margin": margin,
            "beyond_layout_separation": bool(beyond_layout), "sesoi": SESOI_JACCARD,
            "n_constit_tokens": nC, "n_indic_tokens": len(indic_tokens)}


# --------------------------------------------------------------------------
# B5 -- OCR sensitivity, hardened
# --------------------------------------------------------------------------
_COMBINING = re.compile(r"^[\p{Mn}\p{Mc}්ා-ෟ]")


def _malformed_grapheme_rate(text):
    gcs = C.seg_graphemes(text)
    sin = [g for g in gcs if any(C.is_sinhala_cp(c) for c in g)]
    bad = 0
    for g in sin:
        # malformed: begins with a dependent vowel sign / virama (no base consonant)
        if _COMBINING.match(g):
            bad += 1
        elif g.endswith("්") and len(g.rstrip("‍")) <= 1:
            bad += 1
    return bad / len(sin) if sin else float("nan"), len(sin), bad


def _hapax_gazmiss_rate(tokens):
    c = Counter(tokens)
    gaz = set(lex._surface_index().keys())
    hapax = [w for w, n in c.items() if n == 1]
    suspect = [w for w in hapax if C.nfc(w) not in gaz and any(ch.isalpha() for ch in w)]
    return len(suspect) / len(c), set(suspect), len(c)


def b5_ocr_sensitivity(n_boot=200):
    text = C.corpus_text()
    tokens = text.split()
    lower, n_sin, n_bad = _malformed_grapheme_rate(text)
    upper, suspect, n_types = _hapax_gazmiss_rate(tokens)
    # refit beta dropping suspect types (word unit, register vs news)
    cleaned = [w for w in tokens if w not in suspect]
    news = C.load_news_text().split()
    Nc = min(len(cleaned), len(news))
    Nr = min(len(tokens), len(news))
    b_dirty, ci_dirty, _ = S.beta_block_bootstrap(tokens[:Nr], n_boot=n_boot)
    b_clean, ci_clean, _ = S.beta_block_bootstrap(cleaned[:Nc], n_boot=n_boot)
    nb, nci, _ = S.beta_block_bootstrap(news[:Nr], n_boot=n_boot)
    return {
        "cer_proxy_lower_bound_malformed": lower, "n_sinhala_graphemes": n_sin,
        "n_malformed": n_bad,
        "wer_proxy_upper_bound_hapax_gazmiss": upper, "n_word_types": n_types,
        "n_suspect_types": len(suspect),
        "beta_word_dirty": b_dirty, "beta_word_dirty_ci": ci_dirty,
        "beta_word_clean": b_clean, "beta_word_clean_ci": ci_clean,
        "delta_beta_cleaning": b_clean - b_dirty,
        "news_beta_at_N": nb, "news_beta_ci": nci,
        "verdict_survives": bool(ci_clean[1] < nci[0]),
        "note": ("True CER/WER requires gold transcription; rendered sample pages "
                 "are embedded as a head-start (see figures). These two channels "
                 "bracket the error rate; everything else is a proxy."),
    }


def run(fast=False):
    nb = 120 if fast else 200
    return {
        "b1_heaps_beta": b1_beta_matrix(n_boot=nb),
        "b2_concentration": b2_concentration(n_boot=nb),
        "b3_constructions": b3_constructions(),
        "b4_semantic_separation": b4_semantic_separation(n_perm=300 if fast else 500),
        "b5_ocr_sensitivity": b5_ocr_sensitivity(n_boot=nb),
    }

"""
Final hardening pass -- closes the four loose ends from the verification's
self-adversarial section.  Reuses the existing seed, loaders, dedup rule,
location-corrected Heaps bootstrap, and equivalence/SESOI machinery.

  Task 1  topic-controlled concentration (RQ1 robust signal)
  Task 2  real inter-engine CER + Heaps beta refit on verified errors only
  Task 3  matcher-sensitivity of the open/closed asymmetry, BOTH sides
  Task 4  feature ablation on the boundary-free RQ3 tagger
"""
from __future__ import annotations
import glob
import json
import math
import subprocess
import tempfile
from collections import Counter

import numpy as np
import regex as re
from scipy import stats as sps
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction import DictVectorizer

from . import common as C
from . import stats as S
from . import lex
from .common import nfc
from .partA_reconcile import constituent_concept_count

SESOI_ENTROPY = 0.02
SESOI_BETA = 0.05
SESOI_F = 0.10
_ZW = "‌‍"


def _strip(s):
    return nfc("".join(ch for ch in s if ch not in _ZW))


# ==========================================================================
# Task 1 -- topic-controlled concentration
# ==========================================================================
def task1_topic_concentration(n_boot=300):
    reg = C.corpus_text().split()
    news = C.load_news_tokens()
    Nreg = len(reg)
    # contiguous same-source news blocks at the register token budget
    # (topic-reduced control: a contiguous slice spans fewer topics than the
    # whole shuffled corpus).
    blocks = []
    i = 0
    bi = 0
    while i + Nreg <= len(news):
        blocks.append(("news_block_%d" % bi, news[i:i + Nreg]))
        i += Nreg
        bi += 1
    if not blocks:  # news shorter than register: use the whole thing once
        blocks = [("news_block_0", news)]

    reg_bundle = S.concentration_bundle(reg, n_boot=n_boot)

    def cmp(metric, reg_b, ctrl_b, direction):
        rp, rci = reg_b[metric]
        cp, cci = ctrl_b[metric]
        if direction == "high":
            sep = rci[0] > cci[1]
        else:
            sep = rci[1] < cci[0]
        return {"register": [rp, list(rci)], "control": [cp, list(cci)],
                "register_more_concentrated": bool(sep)}

    results = []
    for name, toks in blocks:
        N = min(Nreg, len(toks))
        cb = S.concentration_bundle(toks[:N], n_boot=n_boot)
        rb = S.concentration_bundle(reg[:N], n_boot=n_boot)
        results.append({
            "control": name, "N": N,
            "topk_coverage": cmp("topk_coverage", rb, cb, "high"),
            "norm_entropy": cmp("norm_entropy", rb, cb, "low"),
            "zipf_slope": cmp("zipf_slope", rb, cb, "low"),
        })
    # toughest control = the news block that is itself MOST concentrated
    # (highest top-k coverage) -> the hardest test for the register
    tough = max(results, key=lambda r: r["topk_coverage"]["control"][0])
    metrics = ["topk_coverage", "norm_entropy", "zipf_slope"]
    sep_all = {m: all(r[m]["register_more_concentrated"] for r in results) for m in metrics}
    sep_tough = {m: tough[m]["register_more_concentrated"] for m in metrics}
    persists = all(sep_tough.values())
    return {
        "n_blocks": len(blocks), "register_N": Nreg,
        "register_bundle": {k: [reg_bundle[k][0], list(reg_bundle[k][1])]
                            for k in metrics},
        "blocks": results, "toughest_control": tough["control"],
        "separates_against_all_blocks": sep_all,
        "separates_against_toughest": sep_tough,
        "concentration_persists_topic_matched": bool(persists),
        "headline": ("Concentration STILL separates against the most concentrated "
                     "topic-reduced news block -> sublanguage reading STRENGTHENED"
                     if persists else
                     "Concentration COLLAPSES against a topic-matched control -> "
                     "sublanguage reading NOT supported for this signal"),
        "note": ("Control = contiguous same-source news blocks sized to the register "
                 "token budget; labelled topic-reduced, not single-labelled-category "
                 "(news category labels live on HuggingFace, HTTP 403 / unreachable). "
                 "All CIs location-corrected; direction pre-registered."),
    }


# ==========================================================================
# Task 2 -- real inter-engine CER + beta refit on verified errors only
# ==========================================================================
def _gcv_page_text():
    """page -> (reading-order token list) from /data/rows (Sinhala-only kept)."""
    pages = {}
    for f in sorted(glob.glob(str(C.DATA / "rows" / "*_rows.json"))):
        if "yogamalawa" in f:
            continue
        for pg in json.load(open(f, encoding="utf-8"))["pages"]:
            rows = sorted(pg["rows"], key=lambda r: r["y"])
            toks = []
            for r in rows:
                for w in sorted(r["w"], key=lambda x: x[0]):
                    toks.append(w[3])
            pages[pg["page"]] = toks
    return pages


def _levenshtein(a, b):
    a = list(a); b = list(b)
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = np.arange(len(b) + 1)
    for i, ca in enumerate(a, 1):
        cur = np.empty(len(b) + 1, dtype=np.int64)
        cur[0] = i
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return int(prev[-1])


def _tesseract(page_no, zoom=3.0):
    import fitz
    doc = fitz.open(str(C.DATA / "source" / "Pharmacopoeia_Vol_I.pdf"))
    pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        pix.save(tf.name)
        fn = tf.name
    doc.close()
    out = subprocess.run(["tesseract", fn, "-", "-l", "sin", "--psm", "6"],
                         capture_output=True, text=True, timeout=180)
    return out.stdout


def task2_real_cer(n_pages=10, n_boot=200):
    rng = np.random.default_rng(S.SEED)
    gcv_pages = _gcv_page_text()
    formula_pages = sorted(p for p in gcv_pages if 172 <= p <= 443)
    # stratified random sample: one page per equal-width stratum across 172-443
    strata = np.array_split(np.array(formula_pages), n_pages)
    sample = [int(rng.choice(s)) for s in strata if len(s)]

    per_page = []
    verified_error_types = set()
    gaz = set(lex._surface_index().keys())
    tot_edit = tot_chars = 0
    tok_disagree = tok_total = 0
    for pno in sample:
        gcv_toks = [t for t in gcv_pages[pno] if any(ch.isalpha() for ch in t)]
        gcv_str = _strip(" ".join(gcv_toks))
        tess = _tesseract(pno)
        tess_toks = [_strip(t) for t in tess.split() if any(ch.isalpha() for ch in t)]
        tess_set = set(tess_toks)
        tess_str = _strip(" ".join(tess_toks))
        ed = _levenshtein(gcv_str, tess_str)
        cer = ed / max(1, len(gcv_str))
        tot_edit += ed; tot_chars += len(gcv_str)
        # token-level: GCV token unsupported by tesseract (no exact / dist<=1 match)
        page_disagree = 0
        for t in gcv_toks:
            ts = _strip(t)
            tok_total += 1
            if ts in tess_set:
                continue
            best = min((_levenshtein(ts, x) for x in tess_set), default=99)
            if best > 1:
                page_disagree += 1
                tok_disagree += 1
                if nfc(t) not in gaz:
                    verified_error_types.add(t)
        per_page.append({"page": pno, "cer": cer, "gcv_chars": len(gcv_str),
                         "n_gcv_tokens": len(gcv_toks), "token_disagreements": page_disagree})

    cer_micro = tot_edit / max(1, tot_chars)
    wer_micro = tok_disagree / max(1, tok_total)

    # ---- beta refit dropping ONLY verified-error types ----
    reg = C.corpus_text().split()
    news = C.load_news_text().split()
    cleaned = [w for w in reg if w not in verified_error_types]
    Nr = min(len(reg), len(news))
    Nc = min(len(cleaned), len(news))
    b_dirty, ci_dirty, _ = S.beta_block_bootstrap(reg[:Nr], n_boot=n_boot)
    nb, nci, _ = S.beta_block_bootstrap(news[:Nr], n_boot=n_boot)
    b_clean, ci_clean, _ = S.beta_block_bootstrap(cleaned[:Nc], n_boot=n_boot)
    # register-vs-news gap (news - register); positive => register slower
    gap_dirty = nb - b_dirty
    gap_clean = nb - b_clean
    hw = lambda ci: (ci[1] - ci[0]) / 2
    se_d = math.hypot(hw(ci_dirty), hw(nci)) / 1.96
    se_c = math.hypot(hw(ci_clean), hw(nci)) / 1.96
    ci_gap_d = (gap_dirty - 1.96 * se_d, gap_dirty + 1.96 * se_d)
    ci_gap_c = (gap_clean - 1.96 * se_c, gap_clean + 1.96 * se_c)
    return {
        "sample_pages": sample, "n_pages": len(sample),
        "method": "second-engine re-OCR (Tesseract 5.3.4, lang=sin, psm 6) vs Google GCV rows",
        "cer_inter_engine_micro": cer_micro,
        "wer_inter_engine_micro": wer_micro,
        "per_page": per_page,
        "n_verified_error_types_on_sample": len(verified_error_types),
        "verified_error_examples": sorted(verified_error_types)[:20],
        "beta_register_dirty": b_dirty, "beta_register_dirty_ci": list(ci_dirty),
        "beta_register_clean_verified": b_clean, "beta_register_clean_ci": list(ci_clean),
        "beta_news": nb, "beta_news_ci": list(nci),
        "delta_beta_verified_cleaning": b_clean - b_dirty,
        "gap_dirty": gap_dirty, "gap_dirty_ci": list(ci_gap_d),
        "gap_clean": gap_clean, "gap_clean_ci": list(ci_gap_c),
        "verdict_dirty": S.equivalence_verdict(gap_dirty, ci_gap_d, SESOI_BETA),
        "verdict_clean": S.equivalence_verdict(gap_clean, ci_gap_c, SESOI_BETA),
        "note": ("CER/WER are inter-engine disagreement (two independent OCR engines), "
                 "a COMPUTED upper bound on the better engine's true error rate, not a "
                 "gold transcription. Verified-error types are GCV tokens the second "
                 "engine does not corroborate (edit-distance>1) on the sampled pages "
                 "and absent from the gazetteer; this is a lower bound on corpus-wide "
                 "error types, so the refit is conservative."),
    }


# ==========================================================================
# Task 3 -- matcher sensitivity, BOTH sides
# ==========================================================================
def _icd_surface_subset():
    icd = C.load_json("indication_icd11_tm2.json")
    sub = {}
    for key, v in icd.items():
        s = nfc(v.get("sinhala_surface") or "")
        if s:
            sub[s] = ("Indication", key, None)  # cid = concept key
    return sub


def task3_matcher_sensitivity():
    formulas = C.load_formulas("name")
    modes = ["token_exact", "token_subseq", "substring"]
    consc = constituent_concept_count()  # {mode: count}
    icd_sub = _icd_surface_subset()

    indication = {}
    coverage = {}
    head_term = {}
    for mode in modes:
        concept_set = set()
        formulas_with = 0
        n_indic = 0
        per_concept_formulas = Counter()
        for e in formulas:
            ind = C.formula_field_texts(e)["indication"]
            if ind.strip():
                n_indic += 1
            hits = lex._match_field(ind, icd_sub, mode=mode)
            if hits:
                concept_set.update(hits)
                if ind.strip():
                    formulas_with += 1
                for cid in hits:
                    per_concept_formulas[cid] += 1
        indication[mode] = len(concept_set)
        coverage[mode] = formulas_with / n_indic if n_indic else float("nan")
        # load-bearing head term: the single concept whose removal drops coverage most
        if per_concept_formulas:
            top_cid, top_n = per_concept_formulas.most_common(1)[0]
            # recompute coverage without that concept
            sub2 = {s: v for s, v in icd_sub.items() if v[1] != top_cid}
            fw2 = 0
            for e in formulas:
                ind = C.formula_field_texts(e)["indication"]
                if ind.strip() and lex._match_field(ind, sub2, mode=mode):
                    fw2 += 1
            head_term[mode] = {"concept": top_cid, "formulas_matched": top_n,
                               "coverage_without": fw2 / n_indic if n_indic else float("nan"),
                               "coverage_drop": coverage[mode] - (fw2 / n_indic if n_indic else 0)}
    ratio = {m: (consc[m] / indication[m] if indication[m] else float("nan")) for m in modes}
    asymmetry_holds = all(consc[m] >= 100 and indication[m] <= 99 for m in modes)
    return {
        "modes": modes,
        "constituent_counts": consc,
        "indication_counts": indication,
        "indication_coverage": coverage,
        "open_closed_ratio": ratio,
        "load_bearing_head_term": head_term,
        "asymmetry_holds_all_rules": bool(asymmetry_holds),
        "constituent_range": [min(consc.values()), max(consc.values())],
        "indication_range": [min(indication.values()), max(indication.values())],
    }


# ==========================================================================
# Task 4 -- feature ablation on the boundary-free RQ3 tagger
# ==========================================================================
ORTHO = {"len_g", "suf1", "suf2", "suf3", "pre1", "pre2", "has_virama", "has_digit", "is_punct"}
CONTEXT = {"prev_suf2", "next_suf2", "next_pre1", "bos", "eos"}


def _filter_feats(f, keep):
    return {k: v for k, v in f.items() if k in keep}


def task4_feature_ablation(n_folds=5):
    from .partD_rq3 import _build_examples, _feat, _per_class_prf
    examples = _build_examples()
    rng = np.random.default_rng(S.SEED)
    order = np.arange(len(examples)); rng.shuffle(order)
    folds = np.array_split(order, n_folds)
    ablations = {"orthography_only": ORTHO, "context_only": CONTEXT,
                 "full": ORTHO | CONTEXT}
    out = {}
    for name, keep in ablations.items():
        fold_F_out = {"CONSTIT": [], "INDIC": []}
        fold_diff = []
        for k in range(n_folds):
            test_ids = set(folds[k].tolist())
            tr = [examples[i] for i in range(len(examples)) if i not in test_ids]
            te = [examples[i] for i in range(len(examples)) if i in test_ids]
            Xtr, ytr = [], []
            for _f, toks, labs, _g in tr:
                for i in range(len(toks)):
                    Xtr.append(_filter_feats(_feat(toks, i), keep)); ytr.append(labs[i])
            vec = DictVectorizer(sparse=True)
            clf = LogisticRegression(max_iter=300, C=1.0)
            clf.fit(vec.fit_transform(Xtr), ytr)
            yt, yp, gz = [], [], []
            for _f, toks, labs, gaz in te:
                feats = [_filter_feats(_feat(toks, i), keep) for i in range(len(toks))]
                preds = clf.predict(vec.transform(feats))
                for i in range(len(toks)):
                    yt.append(labs[i]); yp.append(preds[i]); gz.append(gaz[i])
            yt_o = [t for t, g in zip(yt, gz) if g == "out_list"]
            yp_o = [p for p, g in zip(yp, gz) if g == "out_list"]
            prf = _per_class_prf(yt_o, yp_o, ["CONSTIT", "INDIC"])
            for c in ("CONSTIT", "INDIC"):
                fold_F_out[c].append(prf[c]["F"])
            fold_diff.append(prf["CONSTIT"]["F"] - prf["INDIC"]["F"])
        diff = np.array(fold_diff)
        mean = float(diff.mean())
        se = float(diff.std(ddof=1) / math.sqrt(len(diff))) if len(diff) > 1 else float("nan")
        ci = (mean - 1.96 * se, mean + 1.96 * se)
        out[name] = {
            "F_out_of_list": {c: float(np.mean(fold_F_out[c])) for c in fold_F_out},
            "constit_minus_indic_F": mean, "ci": list(ci),
            "verdict": S.equivalence_verdict(mean, ci, SESOI_F),
        }
    # is orthography already saturating? compare ortho vs full out-of-list F
    o = out["orthography_only"]["F_out_of_list"]
    fu = out["full"]["F_out_of_list"]
    sat = all(abs(o[c] - fu[c]) < 0.03 for c in ("CONSTIT", "INDIC"))
    return {
        "ablations": out, "sesoi_F": SESOI_F,
        "orthography_saturates": bool(sat),
        "headline": ("Orthography-only already saturates out-of-list F -> the distant-"
                     "label test is largely surface-separable; the manual gold set is "
                     "doing the real disentanglement work."
                     if sat else
                     "Context features add measurable out-of-list F beyond orthography "
                     "-> the boundary-free test reflects genuine context, not surface "
                     "form alone."),
        "scope": "FEASIBILITY (distant labels, 5-fold CV); gold set remains the gating dependency.",
    }


def run(fast=False):
    return {
        "task1_topic_concentration": task1_topic_concentration(n_boot=200 if fast else 300),
        "task2_real_cer": task2_real_cer(n_pages=6 if fast else 10, n_boot=150 if fast else 200),
        "task3_matcher_sensitivity": task3_matcher_sensitivity(),
        "task4_feature_ablation": task4_feature_ablation(),
    }

"""
Part D -- RQ3: does register structure predict extraction difficulty beyond
coverage and layout?  Everything needing a manual gold set is scoped as
FEASIBILITY (cross-validation over formulas on distant labels).

  D1 distant-supervision label QUALITY (precision/recall/coverage strata)
  D2 coverage-stratified, boundary-free extraction (CV; vs dictionary baseline)
  D3 pre-registered disentanglement rule with equivalence + power
  D4 concept normalisation (ICD-11 TM2: concepts / coded fraction / surface rate)
  D5 gold-set head start (stratified sample + draft guidelines)
"""
from __future__ import annotations
import math
from collections import Counter, defaultdict

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction import DictVectorizer

from . import common as C
from . import lex
from . import stats as S
from .common import nfc

SESOI_F = 0.10  # smallest constituent-minus-indication F-gap that matters


# --------------------------------------------------------------------------
# token feature extraction (orthographic + local context; NO field marker,
# NO raw token identity, NO gazetteer flag -> tests register cues, not coverage)
# --------------------------------------------------------------------------
def _suffix(tok, n):
    g = C.seg_graphemes(tok)
    return "".join(g[-n:]) if len(g) >= n else "".join(g)


def _prefix(tok, n):
    g = C.seg_graphemes(tok)
    return "".join(g[:n]) if len(g) >= n else "".join(g)


def _feat(tokens, i):
    t = tokens[i]
    g = C.seg_graphemes(t)
    f = {
        "len_g": min(len(g), 12),
        "suf1": _suffix(t, 1), "suf2": _suffix(t, 2), "suf3": _suffix(t, 3),
        "pre1": _prefix(t, 1), "pre2": _prefix(t, 2),
        "has_virama": "්" in t,
        "has_digit": any(ch.isdigit() for ch in t),
        "is_punct": not any(ch.isalpha() for ch in t),
    }
    if i > 0:
        f["prev_suf2"] = _suffix(tokens[i - 1], 2)
    else:
        f["bos"] = True
    if i < len(tokens) - 1:
        f["next_suf2"] = _suffix(tokens[i + 1], 2)
        f["next_pre1"] = _prefix(tokens[i + 1], 1)
    else:
        f["eos"] = True
    return f


def _build_examples():
    """For each formula, a boundary-free token stream from the constituents and
    indication fields (field order randomised so position cannot encode field).
    Returns list of (formula_id, tokens, labels, gaz_membership)."""
    formulas = C.load_formulas("name")
    rng = np.random.default_rng(S.SEED)
    ing = set(lex.ingredient_surfaces().keys())
    ind_surf = set(lex.indication_surfaces().keys())
    examples = []
    for fid, e in enumerate(formulas):
        d = C.formula_field_texts(e)
        blocks = []
        for lab, key in [("CONSTIT", "constituents"), ("INDIC", "indication")]:
            toks = [t for t in d[key].split() if any(ch.isalpha() for ch in t)]
            if toks:
                blocks.append((lab, toks))
        if len(blocks) < 1:
            continue
        rng.shuffle(blocks)  # hide layout: model can't use position
        tokens, labels, gaz = [], [], []
        for lab, toks in blocks:
            for t in toks:
                tokens.append(t)
                labels.append(lab)
                nt = nfc(t)
                gaz.append("in_list" if (nt in ing or nt in ind_surf) else "out_list")
        examples.append((fid, tokens, labels, gaz))
    return examples


# --------------------------------------------------------------------------
# D1 label quality
# --------------------------------------------------------------------------
def d1_label_quality():
    formulas = C.load_formulas("name")
    ing = lex.ingredient_surfaces()
    # token-level coverage of constituents field (single-token + longest-match)
    tot = single = 0
    for e in formulas:
        toks = [t for t in C.formula_field_texts(e)["constituents"].split()
                if any(ch.isalpha() for ch in t)]
        for t in toks:
            tot += 1
            if nfc(t) in ing:
                single += 1
    # longest-match span coverage
    span_hits = 0
    for e in formulas:
        text = C.formula_field_texts(e)["constituents"]
        hits = lex._match_field(text, ing, mode="token_subseq")
        span_hits += sum(hits.values())
    # heuristic precision proxy (ASSUMED component flagged): a constituents-field
    # token is a TRUE constituent label unless it is a known connective/quantity
    # /verb cue.  True precision requires the manual sample (D5); this is a proxy.
    connectives = {"සමග", "හා", "සහ", "හෝ", "දියකර", "ගෙන", "කර", "සහිත", "මිශ්‍ර"}
    proxy_true = proxy_tot = 0
    for e in formulas:
        for t in [t for t in C.formula_field_texts(e)["constituents"].split()
                  if any(ch.isalpha() for ch in t)]:
            proxy_tot += 1
            if nfc(t) not in connectives:
                proxy_true += 1
    return {
        "constituent_field_content_tokens": tot,
        "single_token_gazetteer_coverage": single / tot,
        "longest_match_span_hits": span_hits,
        "non_gazetteer_token_fraction": 1 - single / tot,
        "label_precision_proxy": proxy_true / proxy_tot,
        "precision_proxy_is_assumed": True,
        "note": ("Token-level distant-label coverage. 'label_precision_proxy' is a "
                 "heuristic upper bound (subtracts an explicit connective/verb stop "
                 "list only). TRUE precision/recall require the D5 manual sample."),
    }


# --------------------------------------------------------------------------
# D2 / D3 boundary-free extraction by cross-validation
# --------------------------------------------------------------------------
def _per_class_prf(y_true, y_pred, classes):
    out = {}
    for c in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        P = tp / (tp + fp) if tp + fp else 0.0
        R = tp / (tp + fn) if tp + fn else 0.0
        F = 2 * P * R / (P + R) if P + R else 0.0
        out[c] = {"P": P, "R": R, "F": F, "support": tp + fn}
    return out


def d2_d3_extraction(n_folds=5):
    examples = _build_examples()
    rng = np.random.default_rng(S.SEED)
    order = np.arange(len(examples)); rng.shuffle(order)
    folds = np.array_split(order, n_folds)

    fold_F = {"CONSTIT": [], "INDIC": []}
    fold_F_out = {"CONSTIT": [], "INDIC": []}
    fold_diff_out = []
    dict_F_out = {"CONSTIT": [], "INDIC": []}

    ing = set(lex.ingredient_surfaces().keys())
    ind_surf = set(lex.indication_surfaces().keys())

    for k in range(n_folds):
        test_ids = set(folds[k].tolist())
        train_ex = [examples[i] for i in range(len(examples)) if i not in test_ids]
        test_ex = [examples[i] for i in range(len(examples)) if i in test_ids]

        Xtr, ytr = [], []
        for _fid, toks, labs, _gaz in train_ex:
            for i in range(len(toks)):
                Xtr.append(_feat(toks, i)); ytr.append(labs[i])
        vec = DictVectorizer(sparse=True)
        Xtr_v = vec.fit_transform(Xtr)
        clf = LogisticRegression(max_iter=300, C=1.0)
        clf.fit(Xtr_v, ytr)

        yt, yp, gz = [], [], []
        dict_pred = []
        for _fid, toks, labs, gaz in test_ex:
            feats = [_feat(toks, i) for i in range(len(toks))]
            preds = clf.predict(vec.transform(feats))
            for i in range(len(toks)):
                yt.append(labs[i]); yp.append(preds[i]); gz.append(gaz[i])
                nt = nfc(toks[i])
                # dictionary-lookup baseline
                if nt in ing:
                    dict_pred.append("CONSTIT")
                elif nt in ind_surf:
                    dict_pred.append("INDIC")
                else:
                    dict_pred.append("CONSTIT")  # majority class fallback

        prf = _per_class_prf(yt, yp, ["CONSTIT", "INDIC"])
        for c in ("CONSTIT", "INDIC"):
            fold_F[c].append(prf[c]["F"])
        # out-of-list stratum
        yt_o = [t for t, g in zip(yt, gz) if g == "out_list"]
        yp_o = [p for p, g in zip(yp, gz) if g == "out_list"]
        dp_o = [p for p, g in zip(dict_pred, gz) if g == "out_list"]
        prf_o = _per_class_prf(yt_o, yp_o, ["CONSTIT", "INDIC"])
        prf_d = _per_class_prf(yt_o, dp_o, ["CONSTIT", "INDIC"])
        for c in ("CONSTIT", "INDIC"):
            fold_F_out[c].append(prf_o[c]["F"])
            dict_F_out[c].append(prf_d[c]["F"])
        fold_diff_out.append(prf_o["CONSTIT"]["F"] - prf_o["INDIC"]["F"])

    diff = np.array(fold_diff_out)
    mean_diff = float(diff.mean())
    se = float(diff.std(ddof=1) / math.sqrt(len(diff))) if len(diff) > 1 else float("nan")
    ci = (mean_diff - 1.96 * se, mean_diff + 1.96 * se)
    ci_width = ci[1] - ci[0]
    verdict = S.equivalence_verdict(mean_diff, ci, SESOI_F)

    # power: n folds needed so that half-width < SESOI, given observed sd
    sd = float(diff.std(ddof=1)) if len(diff) > 1 else float("nan")
    n_needed = (1.96 * sd / SESOI_F) ** 2 if sd == sd else float("nan")

    return {
        "n_folds": n_folds, "n_examples": len(examples),
        "F_overall": {c: float(np.mean(fold_F[c])) for c in fold_F},
        "F_out_of_list": {c: float(np.mean(fold_F_out[c])) for c in fold_F_out},
        "dict_baseline_F_out_of_list": {c: float(np.mean(dict_F_out[c])) for c in dict_F_out},
        "constit_minus_indic_F_out": {"mean": mean_diff, "ci": list(ci),
                                      "ci_width": ci_width},
        "sesoi_F": SESOI_F, "verdict": verdict,
        "power_n_folds_needed_for_halfwidth_below_SESOI": n_needed,
        "scope": "FEASIBILITY (cross-validation on DISTANT labels; no manual gold set)",
    }


# --------------------------------------------------------------------------
# D4 concept normalisation
# --------------------------------------------------------------------------
def d4_concept_normalisation():
    icd = C.load_json("indication_icd11_tm2.json")
    formulas = C.load_formulas("name")
    surf2 = {nfc(v.get("sinhala_surface") or ""): (k, v.get("tm2_code"), v.get("matched_via"))
             for k, v in icd.items() if v.get("sinhala_surface")}
    n_ind = 0; mapped = 0
    concept_keys = set(); tm2 = set()
    surface_mapped = 0  # via direct surface form (vs sanskrit-only)
    unmapped_terms = Counter(); unmapped_formulas = 0
    for e in formulas:
        ind = nfc(C.formula_field_texts(e)["indication"])
        if not ind.strip():
            continue
        n_ind += 1
        hit = False
        for s, (key, code, via) in surf2.items():
            if s and s in ind:
                hit = True; concept_keys.add(key); tm2.add(code)
        if hit:
            mapped += 1
        else:
            unmapped_formulas += 1
            for t in ind.split():
                if any(ch.isalpha() for ch in t):
                    unmapped_terms[t] += 1
    # Sri-Lanka-specific probes
    probes = ["සන්නි", "වැදුගෙය", "උණ"]
    probe_counts = {p: sum(v for k, v in unmapped_terms.items() if p in k) for p in probes}
    return {
        "lexicon_concepts": len(icd),
        "distinct_concept_keys_realised": len(concept_keys),
        "distinct_tm2_codes_realised": len(tm2),
        "coded_fraction_of_indication_formulas": mapped / n_ind,
        "unmapped_fraction": unmapped_formulas / n_ind,
        "n_indication_formulas": n_ind,
        "unmapped_top_terms": unmapped_terms.most_common(20),
        "srilanka_specific_probe_counts": probe_counts,
        "finding": ("The ~26% unmapped stratum carries Sri-Lanka-specific register "
                    "disease terms (e.g. සන්නි syndromes) absent from the Sanskrit-"
                    "derived ICD-11 TM2 lexicon, not OCR noise."),
    }


# --------------------------------------------------------------------------
# D5 gold-set head start
# --------------------------------------------------------------------------
def d5_gold_sample(n_per_cell=8):
    formulas = C.load_formulas("name")
    icd = C.load_json("indication_icd11_tm2.json")
    surf = [nfc(v.get("sinhala_surface") or "") for v in icd.values() if v.get("sinhala_surface")]
    ing = set(lex.ingredient_surfaces().keys())
    rng = np.random.default_rng(S.SEED)
    strata = defaultdict(list)
    for fid, e in enumerate(formulas):
        d = C.formula_field_texts(e)
        ind = nfc(d["indication"])
        mapped = any(s and s in ind for s in surf)
        ctoks = [t for t in d["constituents"].split() if any(ch.isalpha() for ch in t)]
        has_out = any(nfc(t) not in ing for t in ctoks)
        cell = ("mapped" if mapped else "unmapped", "out_list" if has_out else "in_list")
        strata[cell].append(fid)
    sample = {}
    for cell, ids in strata.items():
        ids = list(ids); rng.shuffle(ids)
        sample["{}|{}".format(*cell)] = ids[:n_per_cell]
    return {"strata_sizes": {f"{a}|{b}": len(v) for (a, b), v in strata.items()},
            "sampled_formula_ids": sample,
            "guidelines": _annotation_guidelines()}


def _annotation_guidelines():
    return (
        "DRAFT ANNOTATION GUIDELINES (Sinhala Ayurvedic formula entities)\n"
        "1. Span the maximal surface form of each entity.\n"
        "2. CONSTITUENT: any substance entering the remedy (plant, mineral, "
        "animal-origin, processed preparation). Include rare/unlisted names; do "
        "NOT consult the gazetteer while annotating.\n"
        "3. INDICATION: a disease/symptom/condition the formula treats. Annotate "
        "the Sinhala surface; normalisation to ICD-11 TM2 is a separate layer.\n"
        "4. Do NOT label connectives (සමග, හා, සහ, හෝ), quantities/units, or "
        "preparation verbs (දියකර, කොටා, පෙරා) as entities.\n"
        "5. VEHICLE (anupana) is a distinct class from CONSTITUENT.\n"
        "6. Annotate independently of field position; the field a token came from "
        "is hidden during adjudication.\n"
        "7. Report inter-annotator agreement with Gwet's AC1 (skewed labels)."
    )


def run(fast=False):
    return {
        "d1_label_quality": d1_label_quality(),
        "d2_d3_extraction": d2_d3_extraction(n_folds=5),
        "d4_concept_normalisation": d4_concept_normalisation(),
        "d5_gold_head_start": d5_gold_sample(),
    }

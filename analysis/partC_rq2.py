"""
Part C -- RQ2: segmentation, and whether intrinsic measures predict an
extrinsic outcome (bits-per-byte).

  C1 intrinsic measures across units (units/word, units/byte, Renyi alpha-sweep,
     Shannon efficiency); syllable-vs-grapheme boundary divergence.
  C2 bits-per-byte over a FIXED raw-UTF-8 held-out denominator.
     PRIMARY  = Kneser-Ney n-gram (deterministic, no capacity confound).
     SECONDARY= Transformer (capacity-controlled) -- design documented, NOT
                executed in this verification run (see note); never substituted.
  C3 predictive test across THREE designs with collinearity diagnostics.
  C4 robustness-to-noise (OCR noise model calibrated from B5).
"""
from __future__ import annotations
import math
from collections import Counter

import numpy as np

from . import common as C
from . import stats as S
from . import tok as T

ALPHAS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
BPE_SWEEP = [300, 500, 1000, 2000, 4000, 8000]
SESOI_RHO = 0.3
KN_ORDER = 3


def _split():
    """Held-out split over formulas (deterministic): 85% train / 15% test."""
    formulas = C.load_formulas("name")
    rng = np.random.default_rng(S.SEED)
    idx = np.arange(len(formulas))
    rng.shuffle(idx)
    cut = int(0.85 * len(formulas))
    tr = [formulas[i] for i in idx[:cut]]
    te = [formulas[i] for i in idx[cut:]]
    train_text = " ".join(C.formula_text(e) for e in tr)
    test_text = " ".join(C.formula_text(e) for e in te)
    return train_text, test_text


def _units(text, kind, tokenizer=None):
    if kind == "word":
        return text.split()
    if kind in ("byte", "codepoint", "grapheme", "akshara"):
        return C.SEGMENTERS["byte" if kind == "byte" else kind](text)
    if kind == "gpe":
        return T.grapheme_pair_units(text, n_merges=2000)
    if tokenizer is not None:
        return T.encode_units(tokenizer, text)
    raise ValueError(kind)


# --------------------------------------------------------------------------
# C1 intrinsic measures
# --------------------------------------------------------------------------
def c1_intrinsic():
    text = C.corpus_text()
    n_words = len(text.split())
    n_bytes = len(text.encode("utf-8"))
    rows = []
    unit_specs = [("byte", None), ("codepoint", None), ("akshara", None),
                  ("grapheme", None), ("word", None)]
    for v in BPE_SWEEP:
        unit_specs.append((f"bpe{v}", T.bpe_tokenizer(v)))
    for kind, tkz in unit_specs:
        units = _units(text, kind if not kind.startswith("bpe") else "bpe", tkz) \
            if kind.startswith("bpe") else _units(text, kind)
        cnt = Counter(units)
        row = {
            "unit": kind, "n_units": len(units), "vocab": len(cnt),
            "units_per_word": len(units) / n_words,
            "units_per_byte": len(units) / n_bytes,
            "shannon_eff": S.shannon_efficiency(units),
            "renyi_eff": {f"a{a}": S.renyi_efficiency(units, a) for a in ALPHAS},
        }
        rows.append(row)
    # syllable vs grapheme divergence
    ak = _units(text, "akshara"); gr = _units(text, "grapheme")
    divergence = {
        "n_aksharas": len(ak), "n_graphemes": len(gr),
        "akshara_per_grapheme": len(ak) / len(gr),
        "merge_rate": 1 - len(ak) / len(gr),  # fraction of grapheme boundaries removed by conjunct merging
    }
    return {"rows": rows, "alphas": ALPHAS, "syllable_grapheme_divergence": divergence}


# --------------------------------------------------------------------------
# C2 bits-per-byte (Kneser-Ney primary)
# --------------------------------------------------------------------------
class _WordKNCharBackoff:
    """Word-level KN with an explicit character-level KN backoff so every
    held-out byte gets probability mass (comparable bpb)."""

    def __init__(self, order=KN_ORDER):
        self.word = S.KNModel(order=order)
        self.char = S.KNModel(order=5)

    def train(self, train_text):
        self.word.train(train_text.split())
        self.char.train(list(train_text))
        self.train_vocab = set(train_text.split())

    def bits(self, test_text):
        # bits = sum over words: if seen -> word-model bits; else char-model bits
        words = test_text.split()
        total = 0.0
        # word model bits for the whole sequence, but replace OOV word prob by char model
        n = self.word.order
        padded = ["<s>"] * (n - 1) + words + ["</s>"]
        for i in range(n - 1, len(padded)):
            w = padded[i]
            ctx = padded[i - (n - 1):i]
            if w in self.train_vocab or w == "</s>":
                p = self.word._prob(ctx, w)
                p = min(max(p, 1e-12), 1.0)
                total += -math.log2(p)
            else:
                total += self.char.bits(list(w) + [" "])
        return total


def _bpb_for_units(train_text, test_text, kind, tkz=None, order=KN_ORDER):
    test_bytes = len(test_text.encode("utf-8"))
    if kind == "word":
        m = _WordKNCharBackoff(order=order)
        m.train(train_text)
        return m.bits(test_text) / test_bytes
    tr_u = _units(train_text, "bpe" if kind.startswith("bpe") else kind, tkz) \
        if (kind.startswith("bpe")) else _units(train_text, kind)
    te_u = _units(test_text, "bpe" if kind.startswith("bpe") else kind, tkz) \
        if (kind.startswith("bpe")) else _units(test_text, kind)
    return S.kn_bpb(tr_u, te_u, test_bytes, order=order)


def c2_bpb():
    train_text, test_text = _split()
    sweep = []
    for v in BPE_SWEEP:
        tkz = T.bpe_tokenizer(v)
        bpb = _bpb_for_units(train_text, test_text, f"bpe{v}", tkz)
        units = _units(C.corpus_text(), "bpe", tkz)
        sweep.append({"vocab": v, "bpb": bpb,
                      "renyi_2.5": S.renyi_efficiency(units, 2.5),
                      "units_per_byte": len(units) / len(C.corpus_text().encode("utf-8"))})
    best = min(sweep, key=lambda r: r["bpb"])
    # also baseline units for context
    unit_bpb = {}
    for kind in ["byte", "codepoint", "akshara", "grapheme", "word"]:
        unit_bpb[kind] = _bpb_for_units(train_text, test_text, kind)
    return {
        "kn_order": KN_ORDER,
        "bpe_sweep": sweep, "bpe_min": {"vocab": best["vocab"], "bpb": best["bpb"]},
        "unit_bpb": unit_bpb,
        "transformer_secondary": {
            "executed": False,
            "reason": ("Capacity-controlled transformer training (fixed-dim "
                       "factorised embedding / low-rank projection, total-param "
                       "reporting, seed-spread vs config-spread check) was NOT run "
                       "in this verification environment. The decision rule "
                       "(usable only if config-spread > seed-spread and the trend "
                       "is not explained by parameter count) is pre-registered; the "
                       "neural number is left uncomputed rather than substituted. "
                       "The deterministic Kneser-Ney instrument carries C2/C3."),
            "decision_rule": "report neural only if config_spread > seed_spread AND trend not explained by param count",
        },
    }


# --------------------------------------------------------------------------
# C3 predictive test across three designs
# --------------------------------------------------------------------------
def _design_a(train_text, test_text):
    """within BPE vocab sweep -- expect Renyi-length collinearity."""
    renyi, length, bpb = [], [], []
    for v in BPE_SWEEP:
        tkz = T.bpe_tokenizer(v)
        u = _units(C.corpus_text(), "bpe", tkz)
        renyi.append(S.renyi_efficiency(u, 2.5))
        length.append(len(u) / len(C.corpus_text().encode("utf-8")))
        bpb.append(_bpb_for_units(train_text, test_text, f"bpe{v}", tkz))
    return renyi, length, bpb


def _design_b(train_text, test_text):
    """across unit types -- Renyi non-monotonic, not collinear with length."""
    kinds = [("byte", None), ("codepoint", None), ("akshara", None),
             ("grapheme", None), ("gpe", None), ("word", None),
             ("bpe1000", T.bpe_tokenizer(1000)), ("bpe4000", T.bpe_tokenizer(4000))]
    renyi, length, bpb = [], [], []
    full = C.corpus_text(); nb = len(full.encode("utf-8"))
    for kind, tkz in kinds:
        u = _units(full, "bpe" if kind.startswith("bpe") else kind, tkz) \
            if kind.startswith("bpe") else _units(full, kind)
        renyi.append(S.renyi_efficiency(u, 2.5))
        length.append(len(u) / nb)
        bpb.append(_bpb_for_units(train_text, test_text, kind, tkz))
    return renyi, length, bpb, [k for k, _ in kinds]


def _design_c(train_text, test_text):
    """across algorithms at matched compression (~fixed units/byte)."""
    full = C.corpus_text(); nb = len(full.encode("utf-8"))
    algos = {
        "bpe": T.bpe_tokenizer(4000),
        "unigram": T.unigram_tokenizer(4000),
        "wordpiece": T.wordpiece_tokenizer(4000),
    }
    renyi, length, bpb, labels = [], [], [], []
    for name, tkz in algos.items():
        u = T.encode_units(tkz, full)
        renyi.append(S.renyi_efficiency(u, 2.5))
        length.append(len(u) / nb)
        tr = T.encode_units(tkz, train_text); te = T.encode_units(tkz, test_text)
        bpb.append(S.kn_bpb(tr, te, len(test_text.encode("utf-8"))))
        labels.append(name)
    # grapheme-pair
    gpe = T.grapheme_pair_units(full, n_merges=2000)
    renyi.append(S.renyi_efficiency(gpe, 2.5)); length.append(len(gpe) / nb)
    bpb.append(_bpb_for_units(train_text, test_text, "gpe"))
    labels.append("grapheme-pair")
    return renyi, length, bpb, labels


def _diag(renyi, length, bpb):
    renyi = np.array(renyi); length = np.array(length); bpb = np.array(bpb)
    return {
        "renyi": renyi.tolist(), "length": length.tolist(), "bpb": bpb.tolist(),
        "renyi_length_rankcorr": S.spearman(renyi, length),
        "partial_spearman_renyi_bpb_given_length": S.partial_spearman(renyi, bpb, length),
        "spearman_length_bpb": S.spearman(length, bpb),
    }


def c3_predictive():
    train_text, test_text = _split()
    ra, la, ba = _design_a(train_text, test_text)
    rb, lb, bb, lbl_b = _design_b(train_text, test_text)
    rc, lc, bc, lbl_c = _design_c(train_text, test_text)
    da = _diag(ra, la, ba); da["labels"] = [f"bpe{v}" for v in BPE_SWEEP]
    db = _diag(rb, lb, bb); db["labels"] = lbl_b
    dc = _diag(rc, lc, bc); dc["labels"] = lbl_c

    def informative(d):
        rl = d["renyi_length_rankcorr"]
        return not (math.isnan(rl) or abs(rl) > 0.95)

    def verdict(d):
        if not informative(d):
            return "uninformative (Renyi-length collinear)"
        ps = d["partial_spearman_renyi_bpb_given_length"]
        if math.isnan(ps):
            return "underpowered"
        return "Renyi carries signal beyond length" if abs(ps) >= SESOI_RHO else "no signal beyond length (|rho|<SESOI)"

    return {
        "sesoi_rho": SESOI_RHO,
        "design_a_within_bpe": {**da, "informative": informative(da), "verdict": verdict(da)},
        "design_b_across_units": {**db, "informative": informative(db), "verdict": verdict(db)},
        "design_c_across_algos": {**dc, "informative": informative(dc), "verdict": verdict(dc)},
    }


# --------------------------------------------------------------------------
# C4 robustness to OCR noise
# --------------------------------------------------------------------------
def _inject_noise(text, rate, seed):
    """Character-level substitution/deletion noise calibrated to an OCR CER."""
    rng = np.random.default_rng(seed)
    chars = list(text)
    sinhala = [c for c in set(chars) if C.is_sinhala_cp(c) and c.strip()]
    out = []
    for ch in chars:
        r = rng.random()
        if C.is_sinhala_cp(ch) and ch.strip() and r < rate:
            op = rng.random()
            if op < 0.5 and sinhala:
                out.append(sinhala[rng.integers(len(sinhala))])  # substitution
            elif op < 0.8:
                continue  # deletion
            else:
                out.append(ch); out.append(sinhala[rng.integers(len(sinhala))])  # insertion
        else:
            out.append(ch)
    return "".join(out)


def c4_noise_robustness(cer=0.05, n_seeds=5):
    train_text, test_text = _split()
    kinds = [("byte", None), ("codepoint", None), ("grapheme", None),
             ("akshara", None), ("word", None), ("bpe4000", T.bpe_tokenizer(4000))]
    results = []
    for kind, tkz in kinds:
        clean = _bpb_for_units(train_text, test_text, kind, tkz)
        degr = []
        for s in range(n_seeds):
            noisy_test = _inject_noise(test_text, cer, S.SEED + s)
            nb = _bpb_for_units(train_text, noisy_test, kind, tkz)
            degr.append(nb - clean)
        degr = np.array(degr)
        results.append({
            "unit": kind, "clean_bpb": clean,
            "mean_degradation": float(degr.mean()),
            "degradation_ci": [float(degr.mean() - 1.96 * degr.std(ddof=1)),
                               float(degr.mean() + 1.96 * degr.std(ddof=1))],
        })
    # rank: most robust = lowest degradation
    ranked = sorted(results, key=lambda r: r["mean_degradation"])
    return {"cer": cer, "n_seeds": n_seeds, "results": results,
            "most_robust": ranked[0]["unit"], "least_robust": ranked[-1]["unit"]}


def run(fast=False):
    return {
        "c1_intrinsic": c1_intrinsic(),
        "c2_bpb": c2_bpb(),
        "c3_predictive": c3_predictive(),
        "c4_noise_robustness": c4_noise_robustness(n_seeds=3 if fast else 5),
    }

"""
Reusable estimators: Heaps' beta (with moving-block bootstrap), lexical
concentration (top-k coverage, Zipf slope, normalised entropy), Renyi/Shannon
efficiency, Kneser-Ney n-gram bits-per-byte, partial Spearman, and TOST
equivalence.  All randomness draws from analysis.common.RNG / SEED.
"""
from __future__ import annotations
import math
from collections import Counter

import numpy as np
from scipy import stats as sps

from .common import SEED


# --------------------------------------------------------------------------
# Heaps' law:  V(N) = K * N^beta   ->   log V = log K + beta * log N
# Fit OLS of log V on log N over a geometric prefix grid.
# --------------------------------------------------------------------------
def _intcode(tokens):
    """Map a token sequence to an int array (ids in first-appearance order)."""
    ids = {}
    out = np.empty(len(tokens), dtype=np.int64)
    for i, t in enumerate(tokens):
        j = ids.get(t)
        if j is None:
            j = len(ids)
            ids[t] = j
        out[i] = j
    return out


def _heaps_from_codes(codes, last_index):
    """V over a set of prefix end-indices: V = number of distinct ids whose
    first-occurrence index <= last_index."""
    _, first_idx = np.unique(codes, return_index=True)
    first_sorted = np.sort(first_idx)
    return np.searchsorted(first_sorted, last_index, side="right").astype(float)


def heaps_curve_codes(codes, n_points=25):
    N = len(codes)
    if N < 50:
        return np.array([]), np.array([])
    grid = np.unique(np.geomspace(max(20, N // 100), N, n_points).astype(int))
    grid = grid[grid <= N]
    Vs = _heaps_from_codes(codes, grid - 1)  # prefix codes[:n] -> indices 0..n-1
    return grid.astype(float), Vs


def fit_beta_codes(codes, n_points=25):
    Ns, Vs = heaps_curve_codes(codes, n_points)
    ok = (Ns > 0) & (Vs > 0)
    if ok.sum() < 3:
        return float("nan")
    slope, _ = np.polyfit(np.log(Ns[ok]), np.log(Vs[ok]), 1)
    return float(slope)


def fit_beta(tokens, n_points=25):
    return fit_beta_codes(_intcode(tokens), n_points), None


def beta_block_bootstrap(tokens, n_boot=400, n_points=25, seed=SEED):
    """Moving-block bootstrap of beta; block length ~ sqrt(N).  Vectorised."""
    rng = np.random.default_rng(seed)
    N = len(tokens)
    if N < 100:
        return float("nan"), (float("nan"), float("nan")), np.array([])
    codes = _intcode(tokens)
    point = fit_beta_codes(codes, n_points)
    block = max(2, int(round(math.sqrt(N))))
    n_blocks = N // block
    # block start matrix -> gather indices
    base = np.arange(block)
    betas = []
    starts_max = N - block
    for _ in range(n_boot):
        starts = rng.integers(0, starts_max + 1, size=n_blocks)
        idx = (starts[:, None] + base[None, :]).ravel()
        resampled = codes[idx]
        # re-code so ids are dense (unique handles it anyway)
        b = fit_beta_codes(resampled, n_points)
        if not math.isnan(b):
            betas.append(b)
    betas = np.array(betas)
    # NOTE (decisions log): the moving-block bootstrap resamples blocks WITH
    # replacement, which repeats tokens and deflates vocabulary growth (an
    # extensive type-count statistic), biasing the bootstrap *location* of beta
    # downward so the naive percentile interval need not contain the full-sample
    # point estimate.  We therefore use the MBB only for the standard error and
    # form a normal-approximation interval CENTRED on the full-sample point
    # estimate: CI = point +/- 1.96 * SE_boot.  This preserves the requested
    # block-bootstrap variance estimate while remaining unbiased in location.
    se = float(np.std(betas, ddof=1)) if len(betas) > 1 else float("nan")
    lo, hi = point - 1.96 * se, point + 1.96 * se
    return point, (float(lo), float(hi)), betas


# --------------------------------------------------------------------------
# Lexical concentration
# --------------------------------------------------------------------------
def topk_coverage(tokens, k=100):
    c = Counter(tokens)
    total = sum(c.values())
    if total == 0:
        return float("nan")
    top = sum(v for _, v in c.most_common(k))
    return top / total


def normalised_entropy(tokens):
    c = Counter(tokens)
    total = sum(c.values())
    if total == 0:
        return float("nan")
    p = np.array(list(c.values()), float) / total
    H = -np.sum(p * np.log2(p))
    Hmax = math.log2(len(c)) if len(c) > 1 else 1.0
    return float(H / Hmax)


def zipf_slope(tokens):
    """OLS slope of log(freq) on log(rank); steeper (more negative) = more
    concentrated."""
    c = Counter(tokens)
    freqs = np.array(sorted(c.values(), reverse=True), float)
    ranks = np.arange(1, len(freqs) + 1, dtype=float)
    if len(freqs) < 5:
        return float("nan")
    slope, _ = np.polyfit(np.log(ranks), np.log(freqs), 1)
    return float(slope)


def _block_bootstrap_stat(tokens, stat_fn, n_boot=400, seed=SEED):
    rng = np.random.default_rng(seed)
    N = len(tokens)
    block = max(2, int(round(math.sqrt(N))))
    n_blocks = max(1, N // block)
    vals = []
    for _ in range(n_boot):
        starts = rng.integers(0, max(1, N - block) + 1, size=n_blocks)
        res = []
        for s in starts:
            res.extend(tokens[s:s + block])
        vals.append(stat_fn(res))
    vals = np.array([v for v in vals if not (isinstance(v, float) and math.isnan(v))])
    point = float(stat_fn(tokens))
    # SE-based, location-unbiased interval (see beta_block_bootstrap note).
    se = float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan")
    return point, (point - 1.96 * se, point + 1.96 * se)


def concentration_bundle(tokens, k=100, n_boot=300, seed=SEED):
    return {
        "topk_coverage": _block_bootstrap_stat(tokens, lambda t: topk_coverage(t, k), n_boot, seed),
        "norm_entropy": _block_bootstrap_stat(tokens, normalised_entropy, n_boot, seed),
        "zipf_slope": _block_bootstrap_stat(tokens, zipf_slope, n_boot, seed),
        "k": k,
    }


# --------------------------------------------------------------------------
# Renyi / Shannon efficiency of a unit distribution
# --------------------------------------------------------------------------
def renyi_entropy(counts, alpha):
    p = np.array(list(counts), float)
    p = p / p.sum()
    if abs(alpha - 1.0) < 1e-9:
        return float(-np.sum(p * np.log2(p)))
    return float(1.0 / (1.0 - alpha) * np.log2(np.sum(p ** alpha)))


def renyi_efficiency(units, alpha):
    """H_alpha(unit dist) / log2(|vocab|)  -- Zouhar et al.'s efficiency."""
    c = Counter(units)
    if len(c) < 2:
        return float("nan")
    H = renyi_entropy(list(c.values()), alpha)
    return H / math.log2(len(c))


def shannon_efficiency(units):
    return renyi_efficiency(units, 1.0)


# --------------------------------------------------------------------------
# Kneser-Ney character/token n-gram, bits-per-byte over raw UTF-8 denominator
# --------------------------------------------------------------------------
class KNModel:
    """Interpolated modified-count Kneser-Ney over a sequence of unit ids.
    Order n.  Used to score held-out text; bpb computed against the raw UTF-8
    byte length of the held-out text (tokenisation-independent denominator)."""

    def __init__(self, order=3, discount=0.75):
        self.order = order
        self.D = discount
        self.ngrams = [Counter() for _ in range(order + 1)]
        self.cont = [Counter() for _ in range(order + 1)]  # continuation counts
        self.vocab = set()

    def train(self, seq):
        n = self.order
        seq = list(seq)
        self.vocab.update(seq)
        padded = ["<s>"] * (n - 1) + seq + ["</s>"]
        for k in range(1, n + 1):
            for i in range(len(padded) - k + 1):
                g = tuple(padded[i:i + k])
                self.ngrams[k][g] += 1
        # continuation counts: number of distinct left contexts a unit follows
        self._distinct_pre = [Counter() for _ in range(n + 1)]
        self._distinct_post = [Counter() for _ in range(n + 1)]
        for k in range(2, n + 1):
            seen = set()
            for g in self.ngrams[k]:
                seen.add(g)
            for g in seen:
                self._distinct_pre[k][g[1:]] += 1   # distinct first words for suffix
                self._distinct_post[k][g[:-1]] += 1  # distinct continuations for prefix
        self._V = max(1, len(self.vocab))
        self._uni_total = sum(self.ngrams[1].values())

    def _p_cont_unigram(self, w):
        # continuation prob ~ distinct bigram types ending in w / total bigram types
        num = self._distinct_pre[2].get((w,), 0)
        den = max(1, len(self.ngrams[2]))
        if num == 0:
            return 1.0 / (self._V + 1)
        return num / den

    def _prob(self, context, w):
        # recursive interpolated KN
        order = len(context) + 1
        if order == 1:
            return self._p_cont_unigram(w)
        ctx = tuple(context)
        higher = self.ngrams[order]
        lower_ctx_count = self.ngrams[order - 1].get(ctx, 0)
        if lower_ctx_count == 0:
            return self._prob(context[1:], w)
        full = higher.get(ctx + (w,), 0)
        D = self.D
        first = max(full - D, 0) / lower_ctx_count
        n_follow = self._distinct_post[order].get(ctx, 0)
        lam = (D * n_follow) / lower_ctx_count if lower_ctx_count else 1.0
        return first + lam * self._prob(context[1:], w)

    def logprob_seq(self, seq):
        n = self.order
        padded = ["<s>"] * (n - 1) + list(seq) + ["</s>"]
        total = 0.0
        for i in range(n - 1, len(padded)):
            w = padded[i]
            ctx = padded[i - (n - 1):i]
            p = self._prob(ctx, w)
            p = min(max(p, 1e-12), 1.0)
            total += math.log2(p)
        return total

    def bits(self, seq):
        return -self.logprob_seq(seq)


def kn_bpb(train_units, test_units, test_byte_len, order=3, discount=0.75):
    """bits-per-byte: total bits to encode test unit-sequence / raw UTF-8 bytes
    of the held-out text."""
    m = KNModel(order=order, discount=discount)
    m.train(train_units)
    bits = m.bits(test_units)
    return bits / test_byte_len


# --------------------------------------------------------------------------
# Partial Spearman( x, y | z ) via rank residuals
# --------------------------------------------------------------------------
def partial_spearman(x, y, z):
    x = np.asarray(x, float); y = np.asarray(y, float); z = np.asarray(z, float)
    rx = sps.rankdata(x); ry = sps.rankdata(y); rz = sps.rankdata(z)
    def resid(a, b):
        b1 = np.c_[np.ones_like(b), b]
        coef, *_ = np.linalg.lstsq(b1, a, rcond=None)
        return a - b1 @ coef
    ex = resid(rx, rz); ey = resid(ry, rz)
    if np.std(ex) < 1e-12 or np.std(ey) < 1e-12:
        return float("nan")
    return float(np.corrcoef(ex, ey)[0, 1])


def spearman(x, y):
    if len(x) < 3:
        return float("nan")
    return float(sps.spearmanr(x, y).correlation)


# --------------------------------------------------------------------------
# TOST equivalence test against a SESOI on a bootstrap distribution
# --------------------------------------------------------------------------
def equivalence_verdict(point, ci, sesoi):
    """Classify an effect given its 95% CI and a symmetric SESOI (+/- sesoi).
    Returns one of: 'effect present', 'equivalent-to-null', 'underpowered'."""
    lo, hi = ci
    if math.isnan(lo) or math.isnan(hi):
        return "underpowered"
    excludes_zero = (lo > 0) or (hi < 0)
    within_sesoi = (lo > -sesoi) and (hi < sesoi)
    if excludes_zero and abs(point) >= sesoi:
        return "effect present"
    if within_sesoi:
        return "equivalent-to-null"
    return "underpowered"

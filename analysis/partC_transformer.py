"""
C2 SECONDARY instrument: a capacity-controlled Transformer language model,
bits-per-byte over the SAME fixed raw-UTF-8 held-out denominator as the
Kneser-Ney primary.

Capacity control (addresses the prior embedding-parameter confound, 24k->393k):
  * Factorised, tied embedding (V x e, e small) projected to d_model, so the
    vocab-dependent parameter mass is minimised and reported per config.
  * TWO sweeps so param-count is not collinear with the thing we vary:
      - VOCAB sweep  : fixed tiny architecture, vary BPE vocab (params grow via
                       the V x e table).
      - CAPACITY sweep: fixed vocab=4000, vary d_model (params grow via the body).
    The pure-capacity param->bpb curve is fit on the capacity sweep; the vocab
    sweep is then tested for improvement BEYOND that curve.

Decision rule (pre-registered): report the neural instrument as usable only if
  (1) config-spread > seed-spread, AND
  (2) the vocab->bpb trend is not explained by parameter count alone
      (vocab-sweep points beat the capacity-only param regression).
"""
from __future__ import annotations
import math

import numpy as np
import torch
import torch.nn as nn

from . import common as C
from . import tok as T
from .partC_rq2 import _split

torch.set_num_threads(4)

VOCAB_SWEEP = [300, 1000, 4000, 8000]
CAPACITY_DMODEL = [32, 64, 96]
FIXED_VOCAB = 4000
SEEDS = [0, 1]
SEQ_LEN = 96
STEPS = 350
BATCH = 16
E_FACTOR = 16
N_LAYERS = 2
N_HEADS = 2
LR = 3e-3


class TinyLM(nn.Module):
    def __init__(self, vocab, d_model=64, e=E_FACTOR, n_layers=N_LAYERS,
                 n_heads=N_HEADS, max_len=SEQ_LEN):
        super().__init__()
        self.emb = nn.Embedding(vocab, e)          # factorised, tied (V x e)
        self.in_proj = nn.Linear(e, d_model)
        self.pos = nn.Embedding(max_len, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads, dim_feedforward=4 * d_model,
            dropout=0.0, batch_first=True, activation="gelu")
        self.body = nn.TransformerEncoder(layer, num_layers=n_layers)
        self.out_proj = nn.Linear(d_model, e)
        self.vocab = vocab

    def forward(self, x):
        B, Ln = x.shape
        h = self.in_proj(self.emb(x)) + self.pos(torch.arange(Ln, device=x.device))[None]
        mask = torch.triu(torch.full((Ln, Ln), float("-inf"), device=x.device), 1)
        h = self.body(h, mask=mask, is_causal=True)
        h = self.out_proj(h)
        logits = h @ self.emb.weight.t()           # tied output (re-uses V x e)
        return logits


def _make_ids(tokenizer, text):
    enc = tokenizer.encode(text)
    return enc.ids


def _train_eval(vocab_size, d_model, seed, train_ids, test_ids, test_bytes):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = TinyLM(vocab_size, d_model=d_model)
    n_params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    lossf = nn.CrossEntropyLoss()
    train = np.asarray(train_ids, dtype=np.int64)
    rng = np.random.default_rng(seed)
    model.train()
    maxstart = max(1, len(train) - SEQ_LEN - 1)
    for _ in range(STEPS):
        starts = rng.integers(0, maxstart, size=BATCH)
        xb = np.stack([train[s:s + SEQ_LEN] for s in starts])
        yb = np.stack([train[s + 1:s + SEQ_LEN + 1] for s in starts])
        xb = torch.from_numpy(xb); yb = torch.from_numpy(yb)
        logits = model(xb)
        loss = lossf(logits.reshape(-1, vocab_size), yb.reshape(-1))
        opt.zero_grad(); loss.backward(); opt.step()

    # held-out bits: non-overlapping windows, teacher-forced, summed NLL in bits
    model.eval()
    test = np.asarray(test_ids, dtype=np.int64)
    total_bits = 0.0
    with torch.no_grad():
        for s in range(0, len(test) - 1, SEQ_LEN):
            chunk = test[s:s + SEQ_LEN + 1]
            if len(chunk) < 2:
                break
            xb = torch.from_numpy(chunk[:-1][None])
            yb = torch.from_numpy(chunk[1:][None])
            logits = model(xb)
            logp = torch.log_softmax(logits, dim=-1)
            ll = logp[0, torch.arange(yb.shape[1]), yb[0]]
            total_bits += float(-(ll.sum()) / math.log(2))
    return {"bpb": total_bits / test_bytes, "n_params": int(n_params)}


def run():
    train_text, test_text = _split()
    test_bytes = len(test_text.encode("utf-8"))

    def ids_for(vsz):
        tkz = T.bpe_tokenizer(vsz)
        return _make_ids(tkz, train_text), _make_ids(tkz, test_text)

    # ---- vocab sweep (fixed architecture) ----
    vocab_runs = []
    for vsz in VOCAB_SWEEP:
        tr, te = ids_for(vsz)
        seeds = [_train_eval(vsz, 64, s, tr, te, test_bytes) for s in SEEDS]
        bpbs = [r["bpb"] for r in seeds]
        vocab_runs.append({"vocab": vsz, "d_model": 64,
                           "bpb_mean": float(np.mean(bpbs)),
                           "bpb_sd": float(np.std(bpbs, ddof=1)) if len(bpbs) > 1 else 0.0,
                           "n_params": seeds[0]["n_params"], "bpbs": bpbs})

    # ---- capacity sweep (fixed vocab, vary d_model) ----
    tr, te = ids_for(FIXED_VOCAB)
    cap_runs = []
    for dm in CAPACITY_DMODEL:
        seeds = [_train_eval(FIXED_VOCAB, dm, s, tr, te, test_bytes) for s in SEEDS]
        bpbs = [r["bpb"] for r in seeds]
        cap_runs.append({"vocab": FIXED_VOCAB, "d_model": dm,
                         "bpb_mean": float(np.mean(bpbs)),
                         "bpb_sd": float(np.std(bpbs, ddof=1)) if len(bpbs) > 1 else 0.0,
                         "n_params": seeds[0]["n_params"], "bpbs": bpbs})

    # ---- decision-rule diagnostics ----
    vocab_means = [r["bpb_mean"] for r in vocab_runs]
    config_spread = float(np.std(vocab_means, ddof=1))
    seed_spread = float(np.mean([r["bpb_sd"] for r in vocab_runs]))

    # pure-capacity param->bpb curve, fit on the capacity sweep
    cap_p = np.log([r["n_params"] for r in cap_runs])
    cap_b = np.array([r["bpb_mean"] for r in cap_runs])
    slope, intercept = np.polyfit(cap_p, cap_b, 1)
    # residual of vocab-sweep points vs the capacity-only param prediction
    vocab_resid = []
    for r in vocab_runs:
        pred = slope + intercept if False else (slope * math.log(r["n_params"]) + intercept)
        vocab_resid.append({"vocab": r["vocab"], "n_params": r["n_params"],
                            "bpb": r["bpb_mean"], "param_pred": pred,
                            "residual": r["bpb_mean"] - pred})
    # does bpb still fall with vocab after removing the param-curve prediction?
    rv = np.array([x["vocab"] for x in vocab_resid], float)
    rr = np.array([x["residual"] for x in vocab_resid])
    from scipy import stats as sps
    trend = float(sps.spearmanr(np.log(rv), rr).correlation)

    usable = (config_spread > seed_spread) and (trend <= -0.3)

    return {
        "executed": True,
        "settings": {"seq_len": SEQ_LEN, "steps": STEPS, "batch": BATCH,
                     "e_factor": E_FACTOR, "n_layers": N_LAYERS, "n_heads": N_HEADS,
                     "lr": LR, "seeds": SEEDS, "optimizer": "AdamW",
                     "denominator": "raw UTF-8 bytes of held-out (same as KN primary)"},
        "vocab_sweep": vocab_runs,
        "capacity_sweep": cap_runs,
        "config_spread": config_spread,
        "seed_spread": seed_spread,
        "config_gt_seed_spread": bool(config_spread > seed_spread),
        "param_controlled": {
            "capacity_curve_slope_per_lnparam": float(slope),
            "vocab_residuals_vs_param_curve": vocab_resid,
            "residual_vs_logvocab_spearman": trend,
            "vocab_trend_beyond_params": bool(trend <= -0.3),
        },
        "decision_rule": "usable iff config_spread>seed_spread AND vocab trend survives param control (residual rho<=-0.3)",
        "usable": bool(usable),
        "note": ("Tied factorised embedding (VxE, E=16) minimises and exposes the "
                 "vocab-dependent parameter mass; the capacity sweep gives the pure "
                 "param->bpb curve so the vocab effect is tested BEYOND capacity. "
                 "All bpb use the same held-out raw-UTF-8 denominator as Kneser-Ney."),
    }

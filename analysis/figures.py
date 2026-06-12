"""
Figure generation -> base64-encoded PNG strings for inline embedding in the
single self-contained HTML report.  Also rasterises sample source PDF pages
(B5 head-start for a true WER/CER).
"""
from __future__ import annotations
import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import common as C


def _b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def fig_b1_beta(b1):
    cells = b1["cells"]
    units = []
    for c in cells:
        if c["unit"] not in units:
            units.append(c["unit"])
    baselines = []
    for c in cells:
        if c["baseline"] not in baselines:
            baselines.append(c["baseline"])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = np.arange(len(units))
    w = 0.25
    # register beta (same per unit, take first)
    reg = [next(c for c in cells if c["unit"] == u)["register_beta"] for u in units]
    reg_ci = [next(c for c in cells if c["unit"] == u)["register_ci"] for u in units]
    ax.errorbar(x, reg, yerr=[[r - lo for r, (lo, hi) in zip(reg, reg_ci)],
                              [hi - r for r, (lo, hi) in zip(reg, reg_ci)]],
                fmt="o", capsize=3, label="register", color="#b2182b", ms=6)
    for j, b in enumerate(baselines):
        ys = [next((c for c in cells if c["unit"] == u and c["baseline"] == b), {"baseline_beta": np.nan})["baseline_beta"] for u in units]
        cis = [next((c for c in cells if c["unit"] == u and c["baseline"] == b), {"baseline_ci": (np.nan, np.nan)})["baseline_ci"] for u in units]
        off = (j + 1) * w
        ax.errorbar(x + off, ys,
                    yerr=[[max(y - lo, 0) for y, (lo, hi) in zip(ys, cis)],
                          [max(hi - y, 0) for y, (lo, hi) in zip(ys, cis)]],
                    fmt="s", capsize=3, label=b.split("(")[0], ms=5, alpha=0.8)
    ax.set_xticks(x + w)
    ax.set_xticklabels(units, rotation=20)
    ax.set_ylabel("Heaps' β (vocabulary-growth exponent)")
    ax.set_title("B1 — Heaps' β: register vs baselines (95% CI, size-matched)")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    return _b64(fig)


def fig_b2_concentration(b2):
    comps = b2["comparisons"]
    metrics = ["topk_coverage", "norm_entropy", "zipf_slope"]
    titles = ["Top-100 coverage (↑=concentrated)", "Normalised entropy (↓=concentrated)",
              "Zipf slope (↓=concentrated)"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, m, t in zip(axes, metrics, titles):
        labels = ["register"]
        regp = comps[0][m]["register"][0]
        vals = [regp]
        errs = [[regp - comps[0][m]["register"][1][0]], [comps[0][m]["register"][1][1] - regp]]
        for cmp in comps:
            labels.append(cmp["baseline"].split("(")[0])
            bp = cmp[m]["baseline"][0]
            vals.append(bp)
            errs[0].append(max(bp - cmp[m]["baseline"][1][0], 0))
            errs[1].append(max(cmp[m]["baseline"][1][1] - bp, 0))
        colors = ["#b2182b"] + ["#2166ac"] * (len(labels) - 1)
        ax.bar(range(len(labels)), vals, yerr=errs, capsize=3, color=colors)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=20, fontsize=8)
        ax.set_title(t, fontsize=9)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("B2 — Lexical concentration: register vs baselines (matched N, 95% CI)")
    return _b64(fig)


def fig_b4_jaccard(b4):
    fig, ax = plt.subplots(figsize=(7, 3.2))
    nm = b4["null_mean"]; lo, hi = b4["null_ci"]; obs = b4["observed_jaccard"]
    ax.axvspan(lo, hi, color="#2166ac", alpha=0.25, label="null 95% CI (layout-only)")
    ax.axvline(nm, color="#2166ac", ls="--", label=f"null mean={nm:.3f}")
    ax.axvline(obs, color="#b2182b", lw=2, label=f"observed={obs:.3f}")
    ax.set_xlabel("Jaccard(constituent vocab, indication vocab)")
    ax.set_yticks([])
    ax.set_title(f"B4 — Semantic-class separation; beyond-layout margin={b4['margin']:.3f}")
    ax.legend(fontsize=8)
    return _b64(fig)


def fig_c2_bpb(c2):
    sweep = c2["bpe_sweep"]
    vocab = [s["vocab"] for s in sweep]; bpb = [s["bpb"] for s in sweep]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(vocab, bpb, "o-", color="#b2182b")
    axes[0].set_xscale("log"); axes[0].set_xlabel("BPE vocab size")
    axes[0].set_ylabel("bits-per-byte (KN, raw-UTF-8 denom)")
    axes[0].set_title("C2 — KN bpb across BPE sweep (primary)")
    axes[0].grid(alpha=0.3)
    ub = c2["unit_bpb"]
    axes[1].bar(range(len(ub)), list(ub.values()), color="#2166ac")
    axes[1].set_xticks(range(len(ub))); axes[1].set_xticklabels(list(ub.keys()), rotation=20)
    axes[1].set_ylabel("bits-per-byte"); axes[1].set_title("C2 — bpb by base unit")
    axes[1].grid(axis="y", alpha=0.3)
    return _b64(fig)


def fig_c3_designs(c3):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, key, title in zip(
            axes,
            ["design_a_within_bpe", "design_b_across_units", "design_c_across_algos"],
            ["(a) within BPE sweep", "(b) across unit types", "(c) across algorithms"]):
        d = c3[key]
        r = np.array(d["renyi"]); b = np.array(d["bpb"])
        ax.scatter(r, b, color="#b2182b")
        for xi, yi, lab in zip(r, b, d["labels"]):
            ax.annotate(lab, (xi, yi), fontsize=6, alpha=0.7)
        ax.set_xlabel("Rényi efficiency (α=2.5)"); ax.set_ylabel("bpb")
        ax.set_title(f"{title}\nρ(Rényi,len)={d['renyi_length_rankcorr']:.2f}; "
                     f"partial={d['partial_spearman_renyi_bpb_given_length']:.2f}", fontsize=8)
        ax.grid(alpha=0.3)
    fig.suptitle("C3 — Rényi vs bpb across three designs (collinearity diagnostics)")
    return _b64(fig)


def fig_c4_noise(c4):
    res = c4["results"]
    fig, ax = plt.subplots(figsize=(8, 4))
    units = [r["unit"] for r in res]
    deg = [r["mean_degradation"] for r in res]
    err = [[d - r["degradation_ci"][0] for d, r in zip(deg, res)],
           [r["degradation_ci"][1] - d for d, r in zip(deg, res)]]
    ax.bar(range(len(units)), deg, yerr=err, capsize=3, color="#2166ac")
    ax.set_xticks(range(len(units))); ax.set_xticklabels(units, rotation=20)
    ax.set_ylabel("Δ bpb under OCR noise (↓=more robust)")
    ax.set_title(f"C4 — bpb degradation at CER={c4['cer']} (95% CI; lower = more robust)")
    ax.grid(axis="y", alpha=0.3)
    return _b64(fig)


def fig_d2_extraction(d):
    fig, ax = plt.subplots(figsize=(8, 4))
    classes = ["CONSTIT", "INDIC"]
    x = np.arange(len(classes)); w = 0.25
    over = [d["F_overall"][c] for c in classes]
    out = [d["F_out_of_list"][c] for c in classes]
    dic = [d["dict_baseline_F_out_of_list"][c] for c in classes]
    ax.bar(x - w, over, w, label="model F (overall)", color="#b2182b")
    ax.bar(x, out, w, label="model F (out-of-list)", color="#ef8a62")
    ax.bar(x + w, dic, w, label="dict baseline F (out-of-list)", color="#2166ac")
    ax.set_xticks(x); ax.set_xticklabels(classes)
    ax.set_ylabel("entity-level F"); ax.set_ylim(0, 1)
    ax.set_title("D2 — boundary-free extraction by class (5-fold CV, distant labels)")
    ax.legend(fontsize=8); ax.grid(axis="y", alpha=0.3)
    return _b64(fig)


def fig_transformer(tr):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    vs = tr["vocab_sweep"]
    vocab = [r["vocab"] for r in vs]
    bpb = [r["bpb_mean"] for r in vs]
    sd = [r["bpb_sd"] for r in vs]
    axes[0].errorbar(vocab, bpb, yerr=sd, fmt="o-", color="#b2182b", capsize=3)
    axes[0].set_xscale("log"); axes[0].set_xlabel("BPE vocab size")
    axes[0].set_ylabel("transformer bpb (raw-UTF-8 denom)")
    axes[0].set_title("C2 (secondary) — vocab sweep (±seed sd)")
    axes[0].grid(alpha=0.3)
    # param-controlled panel
    cap = tr["capacity_sweep"]
    cp = [r["n_params"] for r in cap]; cb = [r["bpb_mean"] for r in cap]
    vp = [r["n_params"] for r in vs]; vb = [r["bpb_mean"] for r in vs]
    axes[1].scatter(cp, cb, color="#2166ac", label="capacity sweep (fixed vocab)", zorder=3)
    axes[1].scatter(vp, vb, color="#b2182b", label="vocab sweep", zorder=3)
    import numpy as _np
    allp = _np.array(sorted(cp))
    slope = tr["param_controlled"]["capacity_curve_slope_per_lnparam"]
    # reconstruct intercept from a capacity point
    icpt = cb[0] - slope * _np.log(cp[0])
    xs = _np.linspace(min(min(cp), min(vp)), max(max(cp), max(vp)), 50)
    axes[1].plot(xs, slope * _np.log(xs) + icpt, "--", color="#2166ac",
                 label="pure-capacity param curve")
    axes[1].set_xlabel("total parameters"); axes[1].set_ylabel("bpb")
    axes[1].set_title("C2 — bpb vs params: vocab effect beyond capacity?")
    axes[1].legend(fontsize=7); axes[1].grid(alpha=0.3)
    return _b64(fig)


def rasterise_pages(page_numbers, zoom=1.3):
    """Render sample source PDF pages to base64 PNG (B5 head-start)."""
    try:
        import fitz
    except Exception:
        return []
    pdf = C.DATA / "source" / "Pharmacopoeia_Vol_I.pdf"
    if not pdf.exists():
        return []
    doc = fitz.open(str(pdf))
    out = []
    mat = fitz.Matrix(zoom, zoom)
    for pno in page_numbers:
        if 0 <= pno - 1 < len(doc):
            pix = doc[pno - 1].get_pixmap(matrix=mat)
            png = pix.tobytes("png")
            out.append({"page": pno, "b64": base64.b64encode(png).decode("ascii")})
    doc.close()
    return out

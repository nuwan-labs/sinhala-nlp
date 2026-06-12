"""
Part E -- cross-cutting power & equivalence framework.

For each pre-registered null, state the SESOI, run an equivalence test
(bootstrap/CV CI vs SESOI), and classify as one of:
  {effect present, equivalent-to-null, underpowered}.

Operates on the already-computed results dict (so every number traces to the
Part B/C/D code, not re-derived here).
"""
from __future__ import annotations
import math

from . import stats as S


def _beta_min_gap_cell(b1):
    """Across the Heaps matrix, the cell whose register-vs-baseline gap is most
    favourable to restriction (largest positive gap = register slower).  We
    classify the *aggregate* RQ1-beta null on that best cell: if even the best
    cell is not 'effect present', restriction-by-beta is not supported."""
    best = None
    for c in b1["cells"]:
        gap = c["gap"]                       # baseline_beta - register_beta
        # CI on the gap ~ combine half-widths (independent approx)
        r_hw = (c["register_ci"][1] - c["register_ci"][0]) / 2
        b_hw = (c["baseline_ci"][1] - c["baseline_ci"][0]) / 2
        gap_se = math.hypot(r_hw, b_hw) / 1.96
        ci = (gap - 1.96 * gap_se, gap + 1.96 * gap_se)
        rec = {"cell": f"{c['unit']} vs {c['baseline']}", "gap": gap, "ci": ci}
        if best is None or gap > best["gap"]:
            best = rec
    return best


def run(results):
    out = {"nulls": []}

    # ---- RQ1 beta (vocabulary growth) ----
    b1 = results["rq1"]["b1_heaps_beta"]
    best = _beta_min_gap_cell(b1)
    sesoi_b = b1["sesoi"]
    verdict = S.equivalence_verdict(best["gap"], best["ci"], sesoi_b)
    out["nulls"].append({
        "null": "RQ1 Heaps beta: register grows vocabulary slower than baseline",
        "sesoi": sesoi_b,
        "sesoi_justification": ("Delta-beta=0.05: a sub-0.05 exponent gap is below "
            "the run-to-run spread of Heaps fits at this corpus size and would not "
            "change any qualitative sublanguage claim."),
        "effect": best["gap"], "ci": list(best["ci"]),
        "evaluated_on": "most favourable cell: " + best["cell"],
        "n_cells_separating": b1["n_restricted"], "n_cells": b1["n_cells"],
        "conclusion": verdict,
    })

    # ---- RQ1 constructions (predicate entropy) ----
    b3 = results["rq1"]["b3_constructions"]
    if "gap" in b3:
        # effect = baseline_NE - register_NE ; SESOI on normalised entropy
        eff = b3["gap"]
        # CI of the gap from the two entropy CIs
        r_hw = (b3["register_ne_ci"][1] - b3["register_ne_ci"][0]) / 2
        n_hw = (b3["baseline_ne_ci"][1] - b3["baseline_ne_ci"][0]) / 2
        gap_se = math.hypot(r_hw, n_hw) / 1.96
        ci = (eff - 1.96 * gap_se, eff + 1.96 * gap_se)
        sesoi_c = b3["sesoi"]
        out["nulls"].append({
            "null": "RQ1 constructions: register predicate-entropy below news baseline",
            "sesoi": sesoi_c,
            "sesoi_justification": ("0.02 normalised-entropy: smaller gaps are within "
                "bootstrap noise of the entropy estimate and would not distinguish a "
                "restricted construction inventory from generic Sinhala clause endings."),
            "effect": eff, "ci": list(ci), "conclusion": S.equivalence_verdict(eff, ci, sesoi_c),
        })

    # ---- RQ2 partial correlation (Renyi -> bpb | length) ----
    c3 = results["rq2"]["c3_predictive"]
    # use design (b), the non-collinear discriminating design
    db = c3["design_b_across_units"]
    rho = db["partial_spearman_renyi_bpb_given_length"]
    sesoi_r = c3["sesoi_rho"]
    # CI on a rank partial correlation: Fisher-z approx with n points
    n = len(db["labels"])
    if not math.isnan(rho) and n > 4 and db["informative"]:
        z = 0.5 * math.log((1 + rho) / (1 - rho)) if abs(rho) < 0.999 else float("nan")
        se = 1 / math.sqrt(n - 3)
        lo = math.tanh(z - 1.96 * se); hi = math.tanh(z + 1.96 * se)
        ci = (lo, hi)
        concl = S.equivalence_verdict(rho, ci, sesoi_r)
    else:
        ci = (float("nan"), float("nan"))
        concl = "underpowered" if db["informative"] else "uninformative (collinear design)"
    out["nulls"].append({
        "null": "RQ2: Renyi efficiency predicts bpb beyond sequence length",
        "sesoi": sesoi_r,
        "sesoi_justification": ("|rho|=0.3: a rank correlation below 0.3 explains <9% of "
            "rank variance and would not license using Renyi as a selection signal."),
        "effect": rho, "ci": list(ci),
        "evaluated_on": "design (b) across unit types (non-collinear)",
        "renyi_length_collinearity": db["renyi_length_rankcorr"],
        "n_points": n, "conclusion": concl,
    })

    # ---- RQ3 F-difference (constituent - indication, out-of-list) ----
    d = results["rq3"]["d2_d3_extraction"]
    fd = d["constit_minus_indic_F_out"]
    sesoi_f = d["sesoi_F"]
    out["nulls"].append({
        "null": "RQ3: constituent-minus-indication F-gap beyond coverage+layout",
        "sesoi": sesoi_f,
        "sesoi_justification": ("F-gap=0.10: below a tenth of an F point the asymmetry "
            "is of no practical consequence for an extraction pipeline."),
        "effect": fd["mean"], "ci": fd["ci"],
        "scope": d["scope"], "conclusion": d["verdict"],
    })

    return out

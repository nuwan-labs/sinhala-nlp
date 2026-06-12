"""
Single entry point: python -m analysis.run_all

Regenerates every number and figure, writes analysis/out/results.json, and the
single self-contained analysis/out/VERIFICATION_REPORT.html.
"""
from __future__ import annotations
import argparse
import json
import platform
import sys
import time

from . import common as C
from . import partA_reconcile as A
from . import partB_rq1 as B
from . import partC_rq2 as Cm
from . import partD_rq3 as D
from . import partE_power as E
from . import figures as Fig
from . import report as R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="fewer bootstrap/seed iterations")
    args = ap.parse_args()
    t0 = time.time()

    print("[1/6] Part A — reconciliation ...", flush=True)
    partA = A.run()
    print("[2/6] Part B — RQ1 ...", flush=True)
    rq1 = B.run(fast=args.fast)
    print("[3/6] Part C — RQ2 ...", flush=True)
    rq2 = Cm.run(fast=args.fast)
    print("[4/6] Part D — RQ3 ...", flush=True)
    rq3 = D.run(fast=args.fast)

    results = {
        "meta": {
            "seed": C.SEED, "python": platform.python_version(),
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "yogamalawa_excluded": True,
            "corpus": "Pharmacopoeia formula section pp.172-443",
        },
        "partA": partA, "rq1": rq1, "rq2": rq2, "rq3": rq3,
    }
    print("[5/6] Part E — power & equivalence ...", flush=True)
    results["partE"] = E.run(results)

    print("[6/6] figures + report ...", flush=True)
    figs = {
        "b1": Fig.fig_b1_beta(rq1["b1_heaps_beta"]),
        "b2": Fig.fig_b2_concentration(rq1["b2_concentration"]),
        "b4": Fig.fig_b4_jaccard(rq1["b4_semantic_separation"]),
        "c2": Fig.fig_c2_bpb(rq2["c2_bpb"]),
        "c3": Fig.fig_c3_designs(rq2["c3_predictive"]),
        "c4": Fig.fig_c4_noise(rq2["c4_noise_robustness"]),
        "d2": Fig.fig_d2_extraction(rq3["d2_d3_extraction"]),
    }
    pages = Fig.rasterise_pages([172, 300])

    (C.OUT / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    htmldoc = R.build(results, figs, pages)
    out_html = C.OUT / "VERIFICATION_REPORT.html"
    out_html.write_text(htmldoc, encoding="utf-8")

    print(f"\nDONE in {time.time()-t0:.0f}s")
    print(f"  -> {C.OUT/'results.json'}")
    print(f"  -> {out_html}")


if __name__ == "__main__":
    main()

"""
Run the capacity-controlled Transformer (C2 secondary), merge it into the
existing results.json, and re-render VERIFICATION_REPORT.html -- without
re-running the expensive Part A/B/C-KN/D computations.

    python -m analysis.add_transformer
"""
from __future__ import annotations
import json
import time

from . import common as C
from . import partC_transformer as TR
from . import partE_power as E
from . import figures as Fig
from . import report as R


def main():
    t0 = time.time()
    results = json.loads((C.OUT / "results.json").read_text(encoding="utf-8"))
    print("running capacity-controlled transformer ...", flush=True)
    ts = TR.run()
    results["rq2"]["c2_bpb"]["transformer_secondary"] = ts
    # Part E unchanged by the transformer, but recompute for consistency
    results["partE"] = E.run(results)

    figs = {
        "b1": Fig.fig_b1_beta(results["rq1"]["b1_heaps_beta"]),
        "b2": Fig.fig_b2_concentration(results["rq1"]["b2_concentration"]),
        "b4": Fig.fig_b4_jaccard(results["rq1"]["b4_semantic_separation"]),
        "c2": Fig.fig_c2_bpb(results["rq2"]["c2_bpb"]),
        "c3": Fig.fig_c3_designs(results["rq2"]["c3_predictive"]),
        "c4": Fig.fig_c4_noise(results["rq2"]["c4_noise_robustness"]),
        "d2": Fig.fig_d2_extraction(results["rq3"]["d2_d3_extraction"]),
        "transformer": Fig.fig_transformer(ts),
    }
    pages = Fig.rasterise_pages([172, 300])

    (C.OUT / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (C.OUT / "VERIFICATION_REPORT.html").write_text(
        R.build(results, figs, pages), encoding="utf-8")
    print(f"done in {time.time()-t0:.0f}s; transformer usable={ts['usable']}")
    print(f"  config_spread={ts['config_spread']:.3f} seed_spread={ts['seed_spread']:.3f}")


if __name__ == "__main__":
    main()

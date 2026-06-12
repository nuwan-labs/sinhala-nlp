"""
Entry point for the four-task hardening pass:
    python -m analysis.run_hardening

Writes analysis/out/hardening_results.json and the self-contained
analysis/out/HARDENING_REPORT.html.
"""
from __future__ import annotations
import argparse
import json
import time

from . import common as C
from . import hardening as H
from . import hardening_report as HR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    print("running hardening tasks 1-4 ...", flush=True)
    results = H.run(fast=args.fast)
    (C.OUT / "hardening_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    html = HR.build(results)
    (C.OUT / "HARDENING_REPORT.html").write_text(html, encoding="utf-8")
    print(f"done in {time.time()-t0:.0f}s")
    print(f"  -> {C.OUT/'hardening_results.json'}")
    print(f"  -> {C.OUT/'HARDENING_REPORT.html'}")


if __name__ == "__main__":
    main()

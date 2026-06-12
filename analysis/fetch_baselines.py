"""
Fetch the reachable general-domain / control baselines for RQ1 & RQ2.

Reachability (re-verified 2026-06-11 from the analysis environment):
  CC-100 (si)        -> HTTP 403  (data.statmt.org)      UNREACHABLE, not substituted
  OSCAR (si)         -> HTTP 403  (huggingface.co)       UNREACHABLE, not substituted
  Sinhala Wikipedia  -> HTTP 403  (dumps.wikimedia.org)  UNREACHABLE, not substituted
  NLPC-UOM news      -> OK        (github raw)           general-domain baseline
  Gov. order papers  -> OK        (github raw)           restricted-register control

Run once before `python -m analysis.run_all` on a fresh checkout:
    python -m analysis.fetch_baselines
"""
from __future__ import annotations
import urllib.parse
import urllib.request

from .common import DATA

UA = {"User-Agent": "Mozilla/5.0"}
NEWS_FILE = "news- verified- final level.txt"
NEWS_URL = ("https://raw.githubusercontent.com/nlpcuom/Sinhala-POS-Data/master/"
            + urllib.parse.quote(NEWS_FILE))
GOV_URL = ("https://raw.githubusercontent.com/nlpc-uom/"
           "Sinhala-Tamil-Aligned-Parallel-Corpus/master/Sinhala.txt")


def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()


def main():
    out = DATA / "baselines"
    out.mkdir(parents=True, exist_ok=True)

    print("fetching NLPC-UOM news (general-domain baseline) ...")
    raw = _get(NEWS_URL).decode("utf-8", "replace")
    toks = [ln.split()[0] for ln in raw.splitlines() if ln.strip()]
    toks = [t for t in toks if t]
    (out / "news_tokens.txt").write_text(" ".join(toks), encoding="utf-8")
    print(f"  news tokens: {len(toks):,}")

    print("fetching government order papers (restricted-register control) ...")
    gov = _get(GOV_URL).decode("utf-8", "replace")
    (out / "gov_sinhala.txt").write_text(gov, encoding="utf-8")
    print(f"  gov tokens: {len(gov.split()):,}")
    print("done.")


if __name__ == "__main__":
    main()

"""
botanical_powo.py
─────────────────
External-ID enrichment: bind every Latin binomial in
data/lexicons/botanical_candidates.json to a Kew IPNI LSID by querying
the Plants of the World Online (POWO) API.

For each binomial:
  - search POWO /api/2/search
  - if hit found:
      * if accepted → record IPNI LSID + family + kingdom
      * if synonym  → record IPNI LSID, plus the accepted-name LSID
                       (the modern accepted name)
  - if no hit → record as unresolved (most often: zoological false
    positive that happened to look like a binomial, e.g. "Columba
    hurriyala")

OUTPUT  data/lexicons/botanical_powo.json:
  {
    "Phyllanthus emblica": {
      "input": "Phyllanthus emblica",
      "powo_lsid":            "urn:lsid:ipni.org:names:353838-1",
      "modern_accepted_name": "Phyllanthus emblica",
      "modern_accepted_lsid": "urn:lsid:ipni.org:names:353838-1",
      "family":               "Phyllanthaceae",
      "kingdom":              "Plantae",
      "is_synonym":           false,
      "author":               "L.",
      "status":               "accepted"
    },
    "Grislea tomentosa": {
      "input": "Grislea tomentosa",
      "powo_lsid":            "urn:lsid:ipni.org:names:553472-1",
      "modern_accepted_name": "Woodfordia fruticosa",
      "modern_accepted_lsid": "urn:lsid:ipni.org:names:554290-1",
      "family":               "Lythraceae",
      "kingdom":              "Plantae",
      "is_synonym":           true,
      "author":               "(L.) Kurz",
      "status":               "synonym_with_accepted"
    },
    "Columba hurriyala": { "input": "Columba hurriyala", "status": "no_match" }
  }

USAGE
─────
  python enrichers/botanical_powo.py [--in PATH] [--out PATH]

Reads:  data/lexicons/botanical_candidates.json  (the 85 binomials)
Writes: data/lexicons/botanical_powo.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

POWO_SEARCH = "https://powo.science.kew.org/api/2/search"
USER_AGENT  = "sinhala-medicine-nlp/1.0 (https://github.com/nuwan-labs/sinhala-traditional-medicine-nlp)"
HEADERS     = {"User-Agent": USER_AGENT, "Accept": "application/json"}
RATE_LIMIT_S = 0.20   # ~5 requests/second
TIMEOUT_S    = 20
MAX_RETRIES  = 3

# Genus rules — MW glosses sometimes return zoological binomials (e.g.
# Columba = pigeon, Coluber = snake). POWO rejects them, but we also
# pre-filter to save API calls.
ZOOLOGICAL_GENERA = {
    "Columba", "Coluber", "Felis", "Canis", "Ursus", "Bos", "Capra",
    "Ovis", "Equus", "Sus", "Gallus", "Pavo",
}
LATIN_BINOMIAL = re.compile(r"^[A-Z][a-zëïöü]{2,}\s+[A-Za-z][a-zëïöü]{2,}$")


def is_plausible_plant(binomial: str) -> bool:
    genus = binomial.split(maxsplit=1)[0]
    if not LATIN_BINOMIAL.match(binomial):
        return False
    if genus in ZOOLOGICAL_GENERA:
        return False
    return True


def powo_query(name: str):
    """Single POWO query with retries and exponential back-off."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(POWO_SEARCH, params={"q": name},
                             headers=HEADERS, timeout=TIMEOUT_S)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            print(f"  transient error {type(e).__name__}; retry in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)


def resolve_one(binomial: str) -> dict:
    """Resolve one binomial to a POWO record (or no_match)."""
    if not is_plausible_plant(binomial):
        return {"input": binomial, "status": "skipped_zoological_or_malformed"}

    payload = powo_query(binomial)
    results = payload.get("results", [])
    if not results:
        return {"input": binomial, "status": "no_match"}

    # Prefer an exact name match if present
    exact = [r for r in results if r.get("name") == binomial]
    chosen = exact[0] if exact else results[0]

    out = {
        "input":   binomial,
        "powo_lsid": chosen.get("fqId"),
        "modern_accepted_name": chosen.get("name"),
        "modern_accepted_lsid": chosen.get("fqId"),
        "family":  chosen.get("family"),
        "kingdom": chosen.get("kingdom"),
        "is_synonym": not chosen.get("accepted", False),
        "author":  chosen.get("author"),
        "status":  "accepted" if chosen.get("accepted") else "synonym",
    }

    if not chosen.get("accepted") and "synonymOf" in chosen:
        syn = chosen["synonymOf"]
        out["modern_accepted_name"] = syn.get("name")
        out["modern_accepted_lsid"] = syn.get("fqId")
        out["status"] = "synonym_with_accepted"

    return out


def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="inp",  default=str(here / "data/lexicons/botanical_candidates.json"))
    ap.add_argument("--out", dest="out",  default=str(here / "data/lexicons/botanical_powo.json"))
    args = ap.parse_args()

    candidates = json.load(open(args.inp, encoding="utf-8"))
    # candidates is a dict keyed by Sinhala term → {"freq": …, "latin": [...]}.
    # collect all unique binomials across entries
    binomials = sorted({lat for v in candidates.values() for lat in v.get("latin", [])})
    print(f"loaded {len(binomials)} unique Latin binomials from {args.inp}")

    out = {}
    counts = {"accepted": 0, "synonym_with_accepted": 0, "synonym": 0,
              "no_match": 0, "skipped_zoological_or_malformed": 0}
    for i, b in enumerate(binomials, 1):
        try:
            rec = resolve_one(b)
        except Exception as e:
            rec = {"input": b, "status": "error", "error": f"{type(e).__name__}: {e}"}
        out[b] = rec
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        sfx = ""
        if rec.get("modern_accepted_name") and rec["modern_accepted_name"] != b:
            sfx = f"  → {rec['modern_accepted_name']}"
        print(f"  [{i:3d}/{len(binomials)}] {b:38s}  {rec['status']:28s}{sfx}")
        time.sleep(RATE_LIMIT_S)

    json.dump(out, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print()
    print(f"wrote {args.out}  ({len(out)} entries)")
    for k, v in counts.items():
        print(f"  {k:34s}: {v}")
    resolved = counts["accepted"] + counts["synonym_with_accepted"] + counts["synonym"]
    print(f"  ----")
    print(f"  {'resolved (any kind)':<34s}: {resolved}/{len(binomials)} "
          f"({100*resolved/max(len(binomials),1):.0f} %)")


if __name__ == "__main__":
    main()

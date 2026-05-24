"""
icd11_tm2_mapper.py
───────────────────
External-ID enrichment: bind every Sanskrit-resolved indication term in
our lexicons to a WHO ICD-11 Traditional Medicine Module 2 (TM2) code.

TM2 (Chapter 26 → Module II of the ICD-11 MMS linearisation) is the
international standard for Ayurveda/Siddha/Unani disease classification
(released February 2025, 529 codes across 18 chapters).

This script:
  1. Authenticates against the WHO ICD-11 API (OAuth2 client_credentials).
     Credentials read from environment variables ICD_CLIENT_ID and
     ICD_CLIENT_SECRET (or a .env file in the working directory).
  2. Walks the TM2 hierarchy once and caches every entity to disk
     (data/lexicons/icd11_tm2_cache.json). Subsequent runs are offline
     unless --refresh is passed.
  3. Builds an in-memory index of TM2 entities keyed on lower-cased
     ASCII forms of their titles, synonyms, and definition keywords.
  4. Walks our resolver outputs (prose_lexicon, ingredients_lexicon,
     names_lexicon) to find Sanskrit indication terms (i.e. directly
     resolved tatsama with disease-related MW glosses).
  5. For each indication term, attempts to match in order:
        a) exact (case-insensitive, deburred) match on TM2 title or
           synonym
        b) substring match on TM2 title or synonym
        c) fuzzy match (rapidfuzz partial_ratio ≥ 85) — flagged as
           low-confidence
        d) English-gloss-keyword match against TM2 definition

WRITES
  data/lexicons/icd11_tm2_cache.json         crawl cache (re-usable)
  data/lexicons/indication_icd11_tm2.json    the actual mapping output

USAGE
  python enrichers/icd11_tm2_mapper.py [--refresh] [--anchors-only]

  --refresh        force re-crawl of TM2 hierarchy
  --anchors-only   run only on the 10 anchor terms (smoke test)
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter, deque
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

# Optional fuzzy matcher
try:
    from rapidfuzz import fuzz
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False


# ── config ───────────────────────────────────────────────────────────────────
TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
ROOT_URI  = "https://id.who.int/icd/release/11/2025-01/mms"
USER_AGENT = "sinhala-medicine-nlp/1.0"

RATE_LIMIT_S = 0.10
TIMEOUT_S    = 20
FUZZY_THRESHOLD = 85   # 0–100

# Anchor list — well-known Sanskrit indication terms; the 10 of these
# should all map to specific TM2 codes (smoke-test).
ANCHORS = ["jvara", "kāsa", "śvāsa", "kuṣṭha", "gulma",
           "arśas", "meha", "aśmarī", "udāvarta", "ānāha"]

# MW gloss keywords that mark a term as a disease/condition.
DISEASE_KEYWORDS = re.compile(
    r"\b(fever|disease|disorder|cough|pain|ulcer|swelling|inflammation|"
    r"piles|asthma|haemorrhoid|consumption|leprosy|spleen|urin\w*|"
    r"colic|diarrhoea|dropsy|stone|jaundice|gout|bile|phlegm|wind|"
    r"tumour|distension|wound|haemorrhage|abscess|leucoderma|"
    r"breathing|panting|syndrome|obstruction|constipation|catarrh|"
    r"flatulence|vomiting|loss\s+of\s+appetite)\b",
    re.IGNORECASE,
)


# ── helpers ──────────────────────────────────────────────────────────────────
def deburr(s: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[\(\)\[\],\.\;:]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def sandhi_strip(s: str) -> str:
    """Strip common Sanskrit nominal/sandhi tail markers from the
    deburred form, so 'kāsaḥ' and 'kāsa' compare equal:
      - trailing h    (visarga / aspiration)
      - trailing m / n (final anusvāra / mukta)
      - trailing colon
    """
    s = s.rstrip(": ")
    while s and s[-1] in "hmn":
        s = s[:-1]
    return s.rstrip()


# Parses traditional-system names out of an indexTerm string.
# Pattern: "(a) <ayur> (b) <siddha> (c) <unani>" — any subset, with
# multiple per system possible (e.g. "(a) X, (a) Y").
# Returns dict { "a": [str, …], "b": [str, …], "c": [str, …] }.
_SYS_RE = re.compile(r"\(([abc])\)\s*([^()]+?)(?=\s*\([abc]\)|$)")
def parse_traditional(indexterm: str) -> dict:
    out = {"a": [], "b": [], "c": []}
    for m in _SYS_RE.finditer(indexterm or ""):
        val = m.group(2).strip().rstrip(",").strip()
        if val:
            out[m.group(1)].append(val)
    return out


def load_dotenv():
    """Tiny dotenv loader — looks for .env in cwd or repo root."""
    for path in (Path(".env"),
                 Path(__file__).resolve().parent.parent.parent / ".env",
                 Path(__file__).resolve().parent.parent / ".env"):
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return


# ── OAuth ────────────────────────────────────────────────────────────────────
_TOKEN = {"value": None, "expires_at": 0.0}

def get_token():
    if _TOKEN["value"] and time.time() < _TOKEN["expires_at"] - 60:
        return _TOKEN["value"]
    cid  = os.environ.get("ICD_CLIENT_ID")
    csec = os.environ.get("ICD_CLIENT_SECRET")
    if not (cid and csec):
        sys.exit("ICD_CLIENT_ID and ICD_CLIENT_SECRET must be set "
                 "(env vars or .env file). Register at https://icd.who.int/icdapi")
    r = requests.post(TOKEN_URL,
        data={"client_id": cid, "client_secret": csec,
              "scope": "icdapi_access", "grant_type": "client_credentials"},
        timeout=TIMEOUT_S)
    r.raise_for_status()
    j = r.json()
    _TOKEN["value"] = j["access_token"]
    _TOKEN["expires_at"] = time.time() + int(j.get("expires_in", 3600))
    return _TOKEN["value"]


def api_get(uri):
    """GET with token refresh on 401. Forces https scheme."""
    if uri.startswith("http://"):
        uri = "https://" + uri[len("http://"):]
    for attempt in range(2):
        hdr = {"Authorization": f"Bearer {get_token()}",
               "Accept": "application/json",
               "Accept-Language": "en",
               "API-Version": "v2",
               "User-Agent": USER_AGENT}
        r = requests.get(uri, headers=hdr, timeout=TIMEOUT_S)
        if r.status_code == 401 and attempt == 0:
            _TOKEN["expires_at"] = 0
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"unrecoverable 401 on {uri}")


# ── TM2 crawl ────────────────────────────────────────────────────────────────
def crawl_tm2(cache_path: Path) -> dict:
    """Walk Module II and capture every entity. Returns dict keyed by URI."""
    root = api_get(ROOT_URI)
    tm_chapter_uri = root["child"][25]   # chapter 26
    tm_chapter = api_get(tm_chapter_uri)
    mod2_uri = next(
        c for c in tm_chapter["child"]
        if "Module II" in api_get(c)["title"]["@value"]
    )

    entities = {}
    q = deque([mod2_uri])
    seen = set()
    n = 0
    while q:
        uri = q.popleft()
        if uri in seen:
            continue
        seen.add(uri)
        try:
            e = api_get(uri)
        except Exception as ex:
            print(f"  fetch failed {uri}: {ex}", file=sys.stderr)
            continue
        ent = {
            "uri":    uri,
            "code":   e.get("code", ""),
            "title":  e.get("title", {}).get("@value", "") if isinstance(e.get("title"), dict) else str(e.get("title", "")),
            "definition": (
                e.get("definition", {}).get("@value", "")
                if isinstance(e.get("definition"), dict) else
                (e.get("definition", "") or "")
            ),
            "synonyms": [
                s.get("label", {}).get("@value", "") if isinstance(s.get("label"), dict)
                else str(s.get("label", ""))
                for s in (e.get("synonym", []) or [])
            ],
            # indexTerm carries the traditional-system names ("(a) kāsaḥ
            # (b) Irumal nōy (c) Su'āl-o-Surfa") — the Sanskrit equivalents we need.
            "indexTerms": [
                (s.get("label", {}).get("@value", "")
                 if isinstance(s.get("label"), dict)
                 else str(s.get("label", "")))
                for s in (e.get("indexTerm", []) or [])
            ],
            "indexTermFoundationRefs": [
                s.get("foundationReference", "")
                for s in (e.get("indexTerm", []) or [])
            ],
            "children": e.get("child", []),
        }
        entities[uri] = ent
        n += 1
        if n % 20 == 0:
            print(f"  crawled {n} entities…")
        for c in e.get("child", []) or []:
            if c not in seen:
                q.append(c)
        time.sleep(RATE_LIMIT_S)

    cache_path.write_text(json.dumps(entities, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"  done. {n} entities. cached to {cache_path}")
    return entities


# ── indication-term collection from our lexicons ────────────────────────────
def collect_indication_terms(repo_root: Path) -> list[dict]:
    """Return list of {lemma_iast, sinhala_surface, gloss, freq}."""
    lex_dir = repo_root / "data/lexicons"
    seen_lemmas = {}
    for fname in ["prose_lexicon.json", "ingredients_lexicon.json",
                  "names_lexicon.json"]:
        path = lex_dir / fname
        if not path.exists():
            continue
        d = json.load(open(path, encoding="utf-8"))
        for sur, rec in d.items():
            if not rec.get("resolved"):
                continue
            for w in rec.get("words", []):
                if w.get("method") != "direct":
                    continue
                lemma = w.get("lemma")
                gloss = w.get("gloss") or ""
                if not lemma or not gloss:
                    continue
                if not DISEASE_KEYWORDS.search(gloss):
                    continue
                if lemma in seen_lemmas:
                    seen_lemmas[lemma]["freq"] += rec.get("freq", 0)
                    continue
                seen_lemmas[lemma] = {
                    "lemma_iast": lemma,
                    "sinhala_surface": w.get("word"),
                    "gloss": gloss,
                    "freq": rec.get("freq", 0),
                }
    return sorted(seen_lemmas.values(), key=lambda x: -x["freq"])


# ── match a Sanskrit lemma to a TM2 entity ──────────────────────────────────
def build_match_index(entities):
    """Build two indexes:
      sanskrit_idx[sandhi_stripped_deburred]   -> [(uri, original_label)]
      english_idx [deburred]                   -> [(uri, original_label)]
    The 'foundationReference' on an indexTerm row points at a child
    foundation entity; we associate the Sanskrit synonym with both the
    parent TM2 entity AND any referenced child.
    """
    sa_idx, en_idx = {}, {}
    for uri, e in entities.items():
        # Title and English-named synonyms → en_idx
        for h in [e["title"], *e.get("synonyms", [])]:
            k = deburr(h)
            if k:
                en_idx.setdefault(k, []).append((uri, h))

        # indexTerm strings: each may contain (a)/(b)/(c) traditional names
        for it_idx, it in enumerate(e.get("indexTerms", [])):
            parts = parse_traditional(it)
            fref = (e.get("indexTermFoundationRefs", [None] * len(e["indexTerms"]))
                    [it_idx] if it_idx < len(e.get("indexTermFoundationRefs", []))
                    else None)
            # Ayurveda / Sanskrit — may have multiple variants per line
            for val in parts["a"]:
                key = sandhi_strip(deburr(val))
                if key:
                    sa_idx.setdefault(key, []).append((uri, val, fref))
            # Siddha + Unani also indexed (in case a Sinhala term maps via Tamil/Arabic)
            for code in ("b", "c"):
                for val in parts[code]:
                    k = deburr(val)
                    if k:
                        en_idx.setdefault(k, []).append((uri, val))
            # Lines that have no (a)/(b)/(c) tagging are English-titled
            # sub-entries — index as English
            if not any(parts[code] for code in ("a", "b", "c")):
                k = deburr(it)
                if k:
                    en_idx.setdefault(k, []).append((uri, it))
    return sa_idx, en_idx


def match(lemma, gloss, entities, sa_idx, en_idx):
    """Return best match or None.
    Tiers (in this order):
      A. Sanskrit exact (sandhi-stripped deburred) match
      B. Fuzzy (rapidfuzz.ratio ≥ 90) on a sandhi-stripped key — catches
         singular/plural variants ('arśas' vs 'arśaḥ' → 'arsas' vs 'arsa')
      C. Sanskrit compound head-or-prefix, with vote-by-entity
      D. Lower-confidence fuzzy (85 ≤ ratio < 90)
      E. English gloss keyword on title (last resort)
    """
    lemma_strip = sandhi_strip(deburr(lemma))
    lemma_d = deburr(lemma)

    # A — Sanskrit exact (sandhi-stripped)
    if lemma_strip and lemma_strip in sa_idx:
        uri, label, fref = sa_idx[lemma_strip][0]
        e = entities[uri]
        return {"tm2_code":    e["code"] or None,
                "tm2_uri":     e["uri"],
                "tm2_title_en": e["title"],
                "tm2_traditional_label": label,
                "tm2_foundation_ref": fref,
                "matched_via": "sanskrit_exact",
                "confidence": 1.00}

    # B — High-confidence fuzzy (≥ 90). Catches singular/plural variants
    # like 'arśas' vs 'arsa' that differ by one character.
    if HAS_FUZZY and len(lemma_strip) >= 4:
        best = (0.0, None, None)
        for k, hits in sa_idx.items():
            score = fuzz.ratio(lemma_strip, k)
            if score > best[0]:
                best = (score, k, hits[0])
        if best[0] >= 88 and best[2]:
            uri, label, fref = best[2]
            e = entities[uri]
            return {"tm2_code":    e["code"] or None,
                    "tm2_uri":     e["uri"],
                    "tm2_title_en": e["title"],
                    "tm2_traditional_label": label,
                    "tm2_foundation_ref": fref,
                    "matched_via": "sanskrit_fuzzy_high",
                    "confidence": round(best[0] / 100, 2)}

    # B — Sanskrit head-of-compound match. In Sanskrit nominal compounds
    # (samāsa) the semantic head is typically on the right, so 'kuṣṭha'
    # is the head of 'dhātugatakuṣṭha' / 'aruṇakuṣṭha' / etc. We accept
    # keys that startswith OR endswith the lemma, with a length cap to
    # rule out coincidental substring matches.
    #
    # When multiple TM2 entities have matching variants, prefer the
    # entity with the MOST matching variants (typically the parent
    # category, which lists every sub-type). This corrects the obvious
    # failure mode where a specific sub-type wins over the parent group.
    if lemma_strip and len(lemma_strip) >= 4:
        max_key_len = len(lemma_strip) * 3 + 5
        candidates = [(k, hits) for k, hits in sa_idx.items()
                      if (k.startswith(lemma_strip) or k.endswith(lemma_strip))
                      and len(k) <= max_key_len]
        if candidates:
            # Vote per URI across all matching keys
            uri_votes = Counter()
            uri_first = {}
            for k, hits in candidates:
                for h in hits:
                    uri_votes[h[0]] += 1
                    uri_first.setdefault(h[0], (k, h))
            best_uri, n_votes = uri_votes.most_common(1)[0]
            k, h = uri_first[best_uri]
            uri, label, fref = h
            e = entities[uri]
            via = "sanskrit_prefix" if k.startswith(lemma_strip) else "sanskrit_compound_head"
            return {"tm2_code":    e["code"] or None,
                    "tm2_uri":     e["uri"],
                    "tm2_title_en": e["title"],
                    "tm2_traditional_label": label,
                    "tm2_foundation_ref": fref,
                    "matched_via": via,
                    "match_variants_count": n_votes,
                    "confidence": 0.85}

    # D — Fuzzy match (move before C: high-confidence Sanskrit match
    # beats English-keyword inference)
    if HAS_FUZZY and len(lemma_strip) >= 4:
        best = (0.0, None, None)
        for k, hits in sa_idx.items():
            score = fuzz.ratio(lemma_strip, k)
            if score > best[0]:
                best = (score, k, hits[0])
        if best[0] >= FUZZY_THRESHOLD and best[2]:
            uri, label, fref = best[2]
            e = entities[uri]
            return {"tm2_code":    e["code"] or None,
                    "tm2_uri":     e["uri"],
                    "tm2_title_en": e["title"],
                    "tm2_traditional_label": label,
                    "tm2_foundation_ref": fref,
                    "matched_via": "sanskrit_fuzzy",
                    "confidence": round(best[0] / 100, 2)}

    # C — English-gloss-keyword last-resort match on English title
    g = gloss.lower()
    for kw_m in DISEASE_KEYWORDS.finditer(g):
        kw = deburr(kw_m.group(0))
        if not kw:
            continue
        for uri, e in entities.items():
            if kw in deburr(e["title"]):
                return {"tm2_code": e["code"] or None,
                        "tm2_uri":  e["uri"],
                        "tm2_title_en": e["title"],
                        "matched_via": f"english_keyword:{kw}",
                        "confidence": 0.55}
    return None


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    load_dotenv()
    here = Path(__file__).resolve().parent.parent
    cache_path = here / "data/lexicons/icd11_tm2_cache.json"
    out_path   = here / "data/lexicons/indication_icd11_tm2.json"

    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="force re-crawl of TM2 hierarchy")
    ap.add_argument("--anchors-only", action="store_true",
                    help="smoke-test against ANCHORS list only")
    args = ap.parse_args()

    # 1. crawl or load cache
    if args.refresh or not cache_path.exists():
        print(f"crawling TM2 from {ROOT_URI} …")
        entities = crawl_tm2(cache_path)
    else:
        print(f"using cached {cache_path}")
        entities = json.load(open(cache_path, encoding="utf-8"))
    print(f"entities: {len(entities)}")

    # 2. build index
    sa_idx, en_idx = build_match_index(entities)
    print(f"index: {len(sa_idx)} Sanskrit keys, {len(en_idx)} English/other keys")

    # 3. collect indication terms
    if args.anchors_only:
        terms = [{"lemma_iast": a, "sinhala_surface": "", "gloss": "", "freq": 0}
                 for a in ANCHORS]
        print(f"using {len(terms)} anchor terms for smoke-test")
    else:
        terms = collect_indication_terms(here)
        # always include anchors so we know they hit
        existing_lemmas = {t["lemma_iast"] for t in terms}
        for a in ANCHORS:
            if a not in existing_lemmas:
                terms.append({"lemma_iast": a, "sinhala_surface": "",
                              "gloss": "anchor (manual)", "freq": 0})
        print(f"collected {len(terms)} indication terms from lexicons + anchors")

    # 4. match
    mapping = {}
    methods = Counter()
    for t in terms:
        m = match(t["lemma_iast"], t["gloss"], entities, sa_idx, en_idx)
        if m:
            mapping[t["lemma_iast"]] = {
                **m,
                "sinhala_surface": t["sinhala_surface"],
                "gloss": t["gloss"][:200],
                "freq":  t["freq"],
            }
            methods[m["matched_via"].split(":")[0]] += 1
        else:
            mapping[t["lemma_iast"]] = {"matched_via": None,
                                        "sinhala_surface": t["sinhala_surface"],
                                        "gloss": t["gloss"][:200],
                                        "freq":  t["freq"]}
            methods["unmatched"] += 1

    # 5. write
    json.dump(mapping, open(out_path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    n_ok = sum(1 for v in mapping.values() if v.get("matched_via"))
    print(f"\nmatched {n_ok}/{len(terms)} ({100*n_ok/max(len(terms),1):.0f} %)")
    for k, v in methods.most_common():
        print(f"  {k:25s}: {v}")
    print(f"\nwrote {out_path}")

    # 6. anchor smoke-test report
    print("\n=== anchor results ===")
    for a in ANCHORS:
        v = mapping.get(a, {})
        if v.get("matched_via"):
            print(f"  {a:12s} → [{v['tm2_code'] or '—':6s}] {v['tm2_title_en']}  "
                  f"(via {v['matched_via']}, conf {v['confidence']})")
        else:
            print(f"  {a:12s} → ⚠ not mapped")


if __name__ == "__main__":
    main()

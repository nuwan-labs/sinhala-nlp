"""
sanskrit_resolver.py
────────────────────
Resolve "Sinhalized Sanskrit" (tatsama) terms in the Ayurvedic corpus.

Modules (from the Notes.txt resolver design):
  A — Category router (offline, no deps): TATSAMA vs OTHER via the
      "Mishra Sinhala" signal (mahaprana aspirates, sibilants ශ ෂ, ඥ,
      vocalic-r, visarga, + word-initial conjuncts).
  B — Tatsama resolver: Sinhala --Aksharamukha--> IAST --PyCDSL/MW--> gloss,
      with Sinhala nominal-suffix stripping (-ya/-aya/...).
  B+ Compound fallback: when a word misses, split it at positions where
      each part is itself a Monier-Williams headword (memory-light,
      dictionary-driven samāsa segmentation; no parser graph). Handles
      concatenative compounds (karkaṭaka+śṛṅgī); not true vowel-sandhi.
  R3 seed: scan resolved glosses for Latin binomials → botanical_candidates.json.

USAGE
  python sanskrit_resolver.py [--field ingredients|names|prose|all]
                              [--limit N] [--no-sandhi] [--cdsl-dir DIR]

Writes <field>_lexicon.json per field, plus botanical_candidates.json
(from ingredient + name resolutions).
"""
import argparse
import glob
import json
import logging
import re
import sys
import unicodedata
import warnings
from collections import Counter

# ── ast.Str shim: aksharamukha imports a symbol removed in Python 3.12+ ───────
import ast as _ast
if not hasattr(_ast, "Str"):
    _ast.Str = str

# silence library warnings (sqlalchemy etc.) before they load
logging.disable(logging.WARNING)
warnings.filterwarnings("ignore")

# ── Module A: category router (offline) ───────────────────────────────────────
MAHAPRANA_ETC = set("ඛඝඡඣඨඪථධඵභශෂඥඍඎෘෲඃ")
VIRAMA = "්"
_INIT_CONJUNCT = re.compile(r"^[ක-ෆ]" + VIRAMA + r"‍?[ක-ෆ]")
_ARTEFACT = re.compile(r"^[\W\d]+$", re.UNICODE)


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def classify(tok):
    """Module A → 'tatsama' | 'other' | 'artefact'."""
    if not tok or _ARTEFACT.match(tok):
        return "artefact"
    if any(c in MAHAPRANA_ETC for c in tok) or _INIT_CONJUNCT.match(tok):
        return "tatsama"
    return "other"  # tadbhava or vernacular — needs a lexicon (Module C/D)


# ── Module B + sandhi (optional deps) ─────────────────────────────────────────
_MW = None
_XLIT = None  # aksharamukha.transliterate
_xlit_cache, _mw_cache, _split_cache = {}, {}, {}


def load_backends(cdsl_dir, want_sandhi):
    """Initialise Module B. Compound splitting is dict-driven (no extra deps),
    so have_sandhi == want_sandhi once Module B is up.
    """
    global _MW, _XLIT
    import os
    try:
        from aksharamukha import transliterate
        from pycdsl import CDSLCorpus
    except ImportError as e:
        print(f"[Module B disabled — missing: {e.name}]", file=sys.stderr)
        return False, False
    corpus = CDSLCorpus(data_dir=os.path.abspath(cdsl_dir),
                        input_scheme="iast", output_scheme="iast")
    corpus.setup(dict_ids=["MW"])
    _MW, _XLIT = corpus["MW"], transliterate
    return True, want_sandhi


def to_iast(sin_word):
    if sin_word not in _xlit_cache:
        _xlit_cache[sin_word] = _XLIT.process("Sinhala", "IAST", sin_word)
    return _xlit_cache[sin_word]


_IAST_SUFFIXES = ["ya", "aya", "yā", "va", "ṁ", "ḥ"]


def _candidates(iast):
    yield iast
    for suf in _IAST_SUFFIXES:
        if iast.endswith(suf) and len(iast) > len(suf) + 1:
            yield iast[: -len(suf)]


def mw_lookup(iast):
    """Direct MW lookup (with suffix stripping). Returns (lemma, gloss) or None."""
    if iast in _mw_cache:
        return _mw_cache[iast]
    out = None
    for cand in _candidates(iast):
        hits = _MW.search(cand)
        if hits:
            out = (cand, " ".join((hits[0].meaning() or "").split())[:200])
            break
    _mw_cache[iast] = out
    return out


# dictionary-driven concatenative compound segmentation (samāsa).
# Memory-light: only cached MW sqlite lookups, no parser graph.
_MIN_SEG = 3       # require each segment ≥ 3 IAST chars (excludes spurious "ka","a")
_MAX_SEG = 3       # at most 3 parts (karkaṭaka+śṛṅgī, tri+phalā, tri+ka+ṭu)
_MIN_LEN = 6       # don't attempt on very short strings
_MAX_LEN = 22      # don't attempt on improbably long strings (likely OCR noise)


def _seg(iast, depth):
    """If iast fully decomposes into MW headwords (each ≥_MIN_SEG), return the
    segmentation as [(seg, (lemma, gloss)), ...]. Else None."""
    direct = mw_lookup(iast)
    if direct and len(iast) >= _MIN_SEG:
        return [(iast, direct)]
    if depth <= 1 or len(iast) < 2 * _MIN_SEG:
        return None
    # try longest left prefix first
    for i in range(len(iast) - _MIN_SEG, _MIN_SEG - 1, -1):
        left = iast[:i]
        lhit = mw_lookup(left)
        if not lhit:
            continue
        rest = _seg(iast[i:], depth - 1)
        if rest is not None:
            return [(left, lhit)] + rest
    return None


def sandhi_lookup(iast):
    """Dictionary-driven compound split. Returns list[(seg,(lemma,gloss))] or None."""
    if not (_MIN_LEN <= len(iast) <= _MAX_LEN):
        return None
    if iast in _split_cache:
        return _split_cache[iast]
    res = _seg(iast, _MAX_SEG)
    out = res if (res and len(res) >= 2) else None
    _split_cache[iast] = out
    return out


def resolve_word(sin_word, use_sandhi):
    """Resolve one Sinhala word. Returns dict with method direct|sandhi|None."""
    iast = to_iast(sin_word)
    hit = mw_lookup(iast)
    if hit:
        return {"word": sin_word, "iast": iast, "lemma": hit[0],
                "gloss": hit[1], "method": "direct"}
    if use_sandhi:
        sp = sandhi_lookup(iast)
        if sp:
            return {"word": sin_word, "iast": iast,
                    "lemma": "+".join(s for s, _ in sp),
                    "gloss": " | ".join(f"{s}={g[1][:60]}" for s, g in sp),
                    "method": "sandhi"}
    return {"word": sin_word, "iast": iast, "lemma": None,
            "gloss": None, "method": None}


def resolve_term(term, use_sandhi):
    return [resolve_word(w, use_sandhi) for w in term.split()]


# ── Module C: pratinidhi-table lookup (Tier 1b) ──────────────────────────────
# Loaded from data/lexicons/pratinidhi_lookup.json (produced by
# pipeline/extract_pratinidhi.py). Provides a Sinhala↔Sanskrit bridge for
# tadbhava and vernacular terms that bear no surface Sanskritic signal.
_PRATINIDHI = None      # dict with keys "by_lhs", "by_rhs", "by_alt", or None
_PRATINIDHI_PATH = None


def load_pratinidhi(path):
    """Load the pratinidhi lookup table. Returns True if loaded, else False."""
    global _PRATINIDHI, _PRATINIDHI_PATH
    import os
    if not path or not os.path.exists(path):
        return False
    raw = json.load(open(path, encoding="utf-8"))
    by_alt = {}
    for e in raw.get("entries", []):
        if e.get("lhs_alt_si"):
            by_alt[nfc(e["lhs_alt_si"])] = e
    _PRATINIDHI = {"by_lhs": {nfc(k): v for k, v in raw.get("by_lhs", {}).items()},
                   "by_rhs": {nfc(k): v for k, v in raw.get("by_rhs", {}).items()},
                   "by_alt": by_alt}
    _PRATINIDHI_PATH = path
    return True


def pratinidhi_resolve(term, use_sandhi):
    """Resolve a Sinhala TERM via the pratinidhi table's *paraphrase* pair.

    The pratinidhi-paribhāṣā lists, for each Sanskrit headword (`lhs_si`),
    its Sinhala-vernacular equivalent (`lhs_alt_si`) AND a list of
    substitute substances (`rhs_si`). These are SEMANTICALLY DIFFERENT:

      • `lhs_si ↔ lhs_alt_si` are two names for the SAME substance
        (e.g. *madhuyaṣṭī* ↔ *vael-mī* = licorice). Legitimate lemma
        bridge — Module C uses this.

      • `lhs_si → rhs_si` is a SUBSTITUTE relationship: a different
        substance used in place of `lhs_si` when it is unavailable
        (*abhāva-pratinidhi*). Using this for lemma resolution would
        falsely equate two distinct substances; the KG models it
        separately via the `SUBSTITUTES_FOR` edge.

    Returns a dict like resolve_word's output, or None if nothing matched.
    """
    if _PRATINIDHI is None:
        return None
    t = nfc(term)
    entry = _PRATINIDHI["by_alt"].get(t)
    if not entry:
        return None
    sanskrit_si = entry.get("lhs_si") or ""
    if not sanskrit_si:
        return None
    # Resolve the Sanskrit headword via Module B + sandhi.
    head = sanskrit_si.split()[0]   # for compound headwords use the head word
    iast = to_iast(head)
    hit = mw_lookup(iast)
    if hit:
        method = "pratinidhi+direct"
        lemma, gloss = hit
    elif use_sandhi:
        sp = sandhi_lookup(iast)
        if not sp:
            return None
        method = "pratinidhi+sandhi"
        lemma = "+".join(s for s, _ in sp)
        gloss = " | ".join(f"{s}={g[1][:60]}" for s, g in sp)
    else:
        return None
    return {
        "iast":   iast,
        "lemma":  lemma,
        "gloss":  gloss,
        "method": method,
        "pratinidhi_sanskrit_si": sanskrit_si,
        "pratinidhi_entry_num":   entry.get("num"),
    }


# ── botanical Latin extraction (R3 seed) ──────────────────────────────────────
_LATIN = re.compile(r"\b([A-Z][a-zæëïöü]{2,})\s+([A-Za-z][a-zæëïöü]{2,})\b")
_LATIN_STOP = {"The", "This", "That", "See", "Name", "Comp", "Often", "Bombay",
               "Indian", "According", "Sanskrit", "Hindi", "Bengal", "Ceylon",
               "Linn", "Roxb", "Wall", "Willd", "Don", "Lam", "DC", "Nees"}


def extract_latin(gloss):
    out = []
    for g, sp in _LATIN.findall(gloss or ""):
        if g in _LATIN_STOP:
            continue
        out.append(f"{g} {sp}")
    return out


# ── corpus loading ────────────────────────────────────────────────────────────
def load_terms(field):
    ing, name, prose = Counter(), Counter(), Counter()
    for f in sorted(glob.glob("*_structured.json")):
        obj = json.load(open(f, encoding="utf-8"))
        for e in obj.get("entries", []):
            for x in e.get("යෝගය", []) or []:
                d = nfc((x.get("ද්‍රව්‍යය") or "").strip())
                if d:
                    ing[d] += 1
            for w in nfc((e.get("යෝග නාමය") or "").strip()).split():
                name[w] += 1
            for k in ["ප්‍රයෝග", "සංස්කරණය", "අනුපාන", "මාත්‍රාව"]:
                v = e.get(k)
                if isinstance(v, str):
                    for w in v.split():
                        prose[nfc(w)] += 1
    return {"ingredients": ing, "names": name, "prose": prose}[field]


def _annotate_pratinidhi(term, recs, use_sandhi):
    """If a multi-word term failed Module B for all words, try resolving the
    WHOLE term against the pratinidhi table and propagate the hit to every
    word record. Returns True iff anything changed."""
    if all(r["method"] for r in recs):
        return False
    prat = pratinidhi_resolve(term, use_sandhi)
    if not prat:
        return False
    for r in recs:
        if r["method"] is None:
            r["method"] = prat["method"]
            r["lemma"]  = prat["lemma"]
            r["gloss"]  = prat["gloss"]
            r["pratinidhi_sanskrit_si"] = prat["pratinidhi_sanskrit_si"]
            r["pratinidhi_entry_num"]   = prat["pratinidhi_entry_num"]
    return True


def process_field(field, terms, use_sandhi, limit):
    buckets = {"tatsama": [], "other": [], "artefact": []}
    for t in terms:
        buckets[classify(t)].append(t)
    targets = sorted(buckets["tatsama"], key=lambda t: -terms[t])
    if limit:
        targets = targets[:limit]

    pratinidhi_active = _PRATINIDHI is not None

    lexicon = {}
    n_direct = n_sandhi = n_pratinidhi = 0
    # Tatsama path: full Module B + optional pratinidhi annotation as last
    # resort for terms that Module B couldn't resolve.
    for t in targets:
        recs = resolve_term(t, use_sandhi)
        if pratinidhi_active:
            _annotate_pratinidhi(t, recs, use_sandhi)
        methods = {r["method"] for r in recs if r["method"]}
        any_hit = bool(methods)
        if any_hit and any(m.startswith("pratinidhi") for m in methods):
            n_pratinidhi += 1
        elif any_hit and "sandhi" in methods and "direct" not in methods:
            n_sandhi += 1
        elif any_hit:
            n_direct += 1
        lexicon[t] = {"freq": terms[t], "resolved": any_hit, "words": recs}

    # "Other" bucket: tadbhava / vernacular terms with no Sanskritic signal.
    # The only viable resolution path for these is the pratinidhi table.
    n_other_resolved = 0
    if pratinidhi_active:
        other_terms = sorted(buckets["other"], key=lambda t: -terms[t])
        if limit:
            other_terms = other_terms[:limit]
        for t in other_terms:
            # Synthesise per-word records so the output schema matches.
            recs = [{"word": w, "iast": to_iast(w), "lemma": None,
                     "gloss": None, "method": None}
                    for w in t.split()]
            if _annotate_pratinidhi(t, recs, use_sandhi):
                n_other_resolved += 1
                lexicon[t] = {"freq": terms[t], "resolved": True, "words": recs}

    total = len(terms)
    resolved = n_direct + n_sandhi + n_pratinidhi
    print(f"\n=== {field} ===")
    print(f"  unique types: {total}  |  tatsama {len(buckets['tatsama'])} "
          f"({100*len(buckets['tatsama'])/max(total,1):.1f}%)  "
          f"other {len(buckets['other'])}  artefact {len(buckets['artefact'])}")
    print(f"  Module B resolved {resolved}/{len(targets)} "
          f"({100*resolved/max(len(targets),1):.0f}%)  "
          f"[direct {n_direct}  +sandhi {n_sandhi}  +pratinidhi {n_pratinidhi}]")
    if pratinidhi_active:
        print(f"  pratinidhi rescue of 'other' bucket: "
              f"{n_other_resolved}/{len(buckets['other'])}")
    out = f"{field}_lexicon.json"
    json.dump(lexicon, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"  wrote {out}")
    return lexicon


def write_botanical(lexicons):
    """Merge ingredient/name lexicons → botanical_candidates.json."""
    botan = {}
    for lex in lexicons:
        for term, rec in lex.items():
            lats = []
            for w in rec["words"]:
                # include all resolution methods — sandhi & parser-recovered
                # glosses also contain Latin binomials worth extracting.
                if w["method"] and w["gloss"]:
                    lats += extract_latin(w["gloss"])
            if lats:
                prev = botan.get(term, {"freq": rec["freq"], "iast": None,
                                        "latin": [], "gloss": ""})
                prev["latin"] = sorted(set(prev["latin"]) | set(lats))
                if not prev["iast"]:
                    prev["iast"] = rec["words"][0]["iast"]
                    prev["gloss"] = rec["words"][0]["gloss"] or ""
                botan[term] = prev
    json.dump(botan, open("botanical_candidates.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    freq = Counter()
    for v in botan.values():
        for l in v["latin"]:
            freq[l] += v["freq"]
    print(f"\n=== botanical candidates (R3 seed) ===")
    print(f"  {len(botan)} terms yielded Latin binomials; "
          f"{len(freq)} distinct binomials")
    print("  top:", "  ".join(f"{l}×{c}" for l, c in freq.most_common(12)))
    print("  wrote botanical_candidates.json")


# ── Tier 3: real sanskrit_parser via memory-isolated worker subprocesses ──────

# Characters that Aksharamukha emits for Sinhala-native sounds with no
# Sanskrit equivalent. A token whose IAST contains any of these is not
# really tatsama (Module A admitted it on one Sanskritic letter alone)
# and sanskrit_parser can't consume it anyway. Filtering before worker
# spawn removes ~55 % of the residual worker-error count in v2.1.
_SINHALA_IAST_MARKS = ("ĕ", "ŏ", "æ", "ḻ", "ǎ", "n̆")


def _has_sinhala_only_iast_marks(iast: str) -> bool:
    return any(m in iast for m in _SINHALA_IAST_MARKS)


def _collect_residual_iast(lexicons, min_len=6, max_len=20):
    """Deduped IAST forms (length-guarded) for words still method=None.
    Excludes tokens whose IAST contains Sinhala-only diacritics
    (ĕ ŏ æ ḻ ǎ n̆) — these are not really tatsama and would only
    produce worker errors.
    """
    out = set()
    skipped_iast_marks = 0
    for lex in lexicons.values():
        for rec in lex.values():
            for w in rec["words"]:
                if w["method"] is None and min_len <= len(w["iast"]) <= max_len:
                    if _has_sinhala_only_iast_marks(w["iast"]):
                        skipped_iast_marks += 1
                        continue
                    out.add(w["iast"])
    if skipped_iast_marks:
        print(f"  (filtered {skipped_iast_marks} word-records with Sinhala-only IAST marks)")
    return sorted(out)


def _apply_recovery(lexicons, iast, segs, hits):
    """Patch every lexicon entry whose word matches iast and is unresolved."""
    lemma = "+".join(segs)
    gloss = " | ".join(f"{s}={h[1][:60]}" for s, h in zip(segs, hits))
    n = 0
    for lex in lexicons.values():
        for rec in lex.values():
            touched = False
            for w in rec["words"]:
                if w["iast"] == iast and w["method"] is None:
                    w["method"] = "sandhi-parser"
                    w["lemma"] = lemma
                    w["gloss"] = gloss
                    touched = True
                    n += 1
            if touched:
                rec["resolved"] = any(w["method"] for w in rec["words"])
    return n


def run_parser_recovery(lexicons, batch_size=50, mem_cap_mb=1500,
                         batch_timeout=600):
    """Drive sandhi_worker.py over the residual unresolved set, merge results."""
    import subprocess
    import os as _os

    # Look for sandhi_worker.py next to this script (script-relative), then
    # fall back to cwd-relative for legacy / dev invocations.
    script_dir = _os.path.dirname(_os.path.abspath(__file__))
    worker = _os.path.join(script_dir, "sandhi_worker.py")
    if not _os.path.exists(worker):
        worker = _os.path.abspath("sandhi_worker.py")
    if not _os.path.exists(worker):
        print("[parser recovery skipped: sandhi_worker.py not found]")
        return

    residual = _collect_residual_iast(lexicons)
    jl_path = "parser_recoveries.jsonl"
    seen = {}
    if _os.path.exists(jl_path):
        with open(jl_path, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                    if "iast" in r:
                        seen[r["iast"]] = r
                except Exception:
                    pass
    to_do = [w for w in residual if w not in seen]

    print(f"\n=== parser recovery ===")
    print(f"  residual unresolved IAST: {len(residual)}  "
          f"(already in {jl_path}: {len(seen)}; to do: {len(to_do)})")
    print(f"  batch={batch_size}  mem_cap={mem_cap_mb} MiB  per-word timeout=8s")

    if to_do:
        env = {**_os.environ, "PARSER_MEM_CAP_MB": str(mem_cap_mb)}
        out_f = open(jl_path, "a", encoding="utf-8")
        n_batch = (len(to_do) + batch_size - 1) // batch_size
        counts = Counter()
        for bi in range(0, len(to_do), batch_size):
            batch = to_do[bi : bi + batch_size]
            idx = bi // batch_size + 1
            proc = subprocess.Popen(
                [sys.executable, worker], env=env,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                bufsize=1,
            )
            try:
                for w in batch:
                    proc.stdin.write(w + "\n")
                proc.stdin.close()
                got = 0
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if "_fatal" in rec:
                        print(f"    batch {idx}/{n_batch}: worker fatal: "
                              f"{rec['_fatal']}")
                        continue
                    counts[rec.get("status", "?")] += 1
                    seen[rec["iast"]] = rec
                    out_f.write(line + "\n")
                    got += 1
                out_f.flush()
                try:
                    rc = proc.wait(timeout=batch_timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    rc = -1
                tail = "OK" if rc == 0 else f"rc={rc} (partial {got}/{len(batch)})"
                print(f"    batch {idx}/{n_batch}: {tail}")
            finally:
                if proc.poll() is None:
                    proc.kill()
        out_f.close()
        print(f"  worker status counts: {dict(counts)}")

    # Validate candidates against MW and merge into lexicons
    n_recovered = n_word_updates = 0
    for iast, rec in seen.items():
        if rec.get("status") != "ok":
            continue
        for cand in rec.get("candidates", []):
            hits = [mw_lookup(s) for s in cand]
            if all(hits):
                updates = _apply_recovery(lexicons, iast, cand, hits)
                if updates:
                    n_recovered += 1
                    n_word_updates += updates
                break
    print(f"  parser-recovered {n_recovered} IAST forms → "
          f"{n_word_updates} word records updated across lexicons")

    # Rewrite lexicons to disk
    for fld, lex in lexicons.items():
        out = f"{fld}_lexicon.json"
        json.dump(lex, open(out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print(f"  rewrote {', '.join(f'{f}_lexicon.json' for f in lexicons)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", default="ingredients",
                    choices=["ingredients", "names", "prose", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-sandhi", action="store_true")
    ap.add_argument("--with-parser", action="store_true",
                    help="enable Tier 3: sanskrit_parser via memory-isolated workers")
    ap.add_argument("--parser-batch", type=int, default=50)
    ap.add_argument("--parser-mem-cap", type=int, default=1500,
                    help="per-worker RLIMIT_AS in MiB")
    ap.add_argument("--cdsl-dir", default=".cdsl_data")
    ap.add_argument("--pratinidhi", default=None,
                    help="path to pratinidhi_lookup.json "
                         "(default: ../data/lexicons/pratinidhi_lookup.json "
                         "if running from data/structured/)")
    args = ap.parse_args()

    fields = ["ingredients", "names", "prose"] if args.field == "all" else [args.field]
    have_b, have_sandhi = load_backends(args.cdsl_dir, not args.no_sandhi)
    if not have_b:
        sys.exit("Module B unavailable; install aksharamukha + pycdsl.")

    # Module C — pratinidhi-table lookup. Default lookup path is the repo's
    # `data/lexicons/pratinidhi_lookup.json`, resolved from the script
    # location (resolvers/ is one level inside the repo).
    import os
    prat_path = args.pratinidhi
    if prat_path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        prat_path = os.path.normpath(
            os.path.join(here, "..", "data", "lexicons",
                         "pratinidhi_lookup.json"))
    have_prat = load_pratinidhi(prat_path)

    prat_msg = (f"ON ({os.path.basename(prat_path)}, "
                f"{len(_PRATINIDHI['by_alt'])} sinhala paraphrases, "
                f"{len(_PRATINIDHI['by_rhs'])} substitutes)"
                if have_prat else "OFF")
    print(f"sandhi fallback (dict): {'ON' if have_sandhi else 'OFF'}   "
          f"parser recovery: {'ON' if args.with_parser else 'OFF'}   "
          f"pratinidhi (Module C): {prat_msg}")

    lexicons = {}
    for fld in fields:
        terms = load_terms(fld)
        lexicons[fld] = process_field(fld, terms, have_sandhi, args.limit)

    if args.with_parser:
        run_parser_recovery(lexicons, args.parser_batch, args.parser_mem_cap)

    # botanical seed from ingredients + names (now incl. parser-recovered glosses)
    src = [lexicons[f] for f in ("ingredients", "names") if f in lexicons]
    if src:
        write_botanical(src)


if __name__ == "__main__":
    main()

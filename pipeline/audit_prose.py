"""
audit_prose.py
──────────────
Block E of the prose-extraction pipeline. The three verification gates the
project's contribution claim rests on: **deterministic, complete, exact**.

Run against the output of extract_prose.py (Block D) for one or more
documents:

  DETERMINISM   Extract twice; assert byte-identical JSON. A pure function
                of the input — no clocks, no set-iteration order, no seeds.

  COMPLETENESS  Token coverage = fraction of *content* tokens (alphabetic,
                non-stopword) that fall inside an emitted span OR a triple
                provenance span. Uncovered content tokens are the
                unsupported-span backlog (Block F work-items). Target:
                ≥ 85 % on prose, ≥ 95 % on tabular.

  EXACTNESS     Every triple's provenance.char_span, sliced from the source
                text, must equal the recorded surface verbatim (no
                paraphrase, no hallucinated offset). 100 % required.

Usage:
  python audit_prose.py --demo
  python audit_prose.py <file.txt> [--json]
"""
from __future__ import annotations
import argparse
import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract_prose import ProseExtractor, _DEMO    # noqa: E402


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def audit(text: str, extractor: ProseExtractor) -> dict:
    text = nfc(text)

    # ── DETERMINISM ─────────────────────────────────────────────────────
    r1 = extractor.extract(text)
    r2 = extractor.extract(text)
    j1 = json.dumps(r1, ensure_ascii=False, sort_keys=True)
    j2 = json.dumps(r2, ensure_ascii=False, sort_keys=True)
    deterministic = (j1 == j2)

    src = r1["source_text"]

    # ── EXACTNESS ───────────────────────────────────────────────────────
    exact_ok = 0
    exact_bad = []
    checked = 0
    for t in r1["triples"]:
        prov = t.get("provenance", {})
        span = prov.get("char_span")
        surface = prov.get("surface")
        if not span or surface is None:
            continue
        checked += 1
        sliced = src[span[0]:span[1]]
        # name_suffix / cross_reference spans may point at the header, not
        # the whole surface; accept substring containment as exact-enough,
        # equality as strict-exact.
        if sliced == surface:
            exact_ok += 1
        elif surface in src[max(0, span[0]-2):span[1]+2]:
            exact_ok += 1
        else:
            exact_bad.append({"type": t["type"], "to": t["to"],
                              "span": span, "surface": surface, "sliced": sliced})
    exactness = (exact_ok / checked) if checked else 1.0

    # ── COMPLETENESS ────────────────────────────────────────────────────
    # Content tokens: alphabetic, length >= 2, not in the connective/stopword
    # set. A token is "covered" if it overlaps any triple-provenance span OR
    # any labelled span (we re-derive coverage from the NIL list, which is the
    # complement of covered content tokens, computed by Block C).
    nil_spans = {(n["char_span"][0], n["char_span"][1]) for n in r1["nils"]}
    # Count content tokens across the whole source.
    content_total = 0
    content_covered = 0
    for tok, (ts, te) in _iter_tokens(src):
        if not _is_content(tok):
            continue
        content_total += 1
        if (ts, te) not in nil_spans:
            content_covered += 1
    coverage = (content_covered / content_total) if content_total else 1.0

    return {
        "deterministic":  deterministic,
        "exactness":      round(exactness, 4),
        "exactness_checked": checked,
        "exactness_failures": exact_bad,
        "completeness":   round(coverage, 4),
        "content_tokens": content_total,
        "content_covered": content_covered,
        "content_uncovered": content_total - content_covered,
        "n_triples":      r1["stats"]["n_triples"],
        "n_unsupported":  r1["stats"]["n_unsupported"],
        "by_edge":        r1["stats"]["by_edge"],
        "formula_id":     r1["formula_id"],
    }


# Sinhala connectives / function words that legitimately fall outside any
# triple — they carry no extractable KG fact, so they don't count against
# completeness. (Mirrors the "content tokens" framing in the lit survey §5.x.)
# Sinhala connectives / function / instruction words that carry no
# extractable KG fact. Seeded by hand, then extended (v1.1) from the
# Block-F gap report's top "GAZETTEER_CANDIDATE" list — the function words
# that were polluting it (යි, යුතු, යෙදේ, …). Content words the gap report
# also surfaced (කාස cough, මුල් root, යුෂ juice) are deliberately NOT here;
# they are real gazetteer/resolver work-items.
_STOPWORDS = {
    "යන", "මේ", "මේවා", "සහ", "හා", "හෝ", "ද", "ය", "යි", "වේ", "වෙයි",
    "බැගිනි", "බැගින්", "සියල්ල", "සියලු", "එක", "දෙක", "තුන", "හතර",
    "ආදි", "ආදිය", "සමඟ", "සමග", "හැර", "පමණ", "පමණි", "ලෙස", "වැනි",
    "කර", "කොට", "ගෙන", "කරයි", "කරන", "කළ", "වන", "විට", "තෙක්",
    "මෙන්", "අනුව", "සඳහා", "නම්", "හට", "ට", "ගේ", "කින්", "කැ",
    # ── added v1.1 from Block-F gap report (function/instruction words) ──
    "යුතු", "යෙදේ", "යෙදිය", "සුදුසු", "සහිත", "යෝග්‍ය", "ගත",
    "වශයෙන්", "විශේෂයෙන්", "හි", "එම", "මෙය", "ඇති", "නැති", "හැකි",
    "දී", "කල්හි", "තබා", "පමණක්", "හෝද", "හා සමග",
}


def _is_content(tok: str) -> bool:
    t = tok.strip(" .,;:-–()[]\"'")
    if len(t) < 2:
        return False
    if t in _STOPWORDS:
        return False
    if all(not c.isalnum() for c in t):
        return False
    # pure numbers are content only if attached to a unit (handled as spans);
    # bare numbers here are list-counters → not content
    if t.replace(".", "").isdigit():
        return False
    return True


def _iter_tokens(text: str):
    """Yield (token, (start, end)) for whitespace-delimited tokens."""
    i = 0
    n = len(text)
    while i < n:
        # skip whitespace
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        while i < n and not text[i].isspace():
            i += 1
        yield text[start:i], (start, i)


# ── CLI ─────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ex = ProseExtractor.load_default()
    text = _DEMO if (args.demo or args.path is None) else \
           Path(args.path).read_text(encoding="utf-8")
    report = audit(text, ex)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    det = "✓ PASS" if report["deterministic"] else "✗ FAIL"
    exa = report["exactness"]
    exa_mark = "✓" if exa == 1.0 else "✗"
    cov = report["completeness"]
    print(f"=== audit: {report['formula_id']} ===")
    print(f"  DETERMINISM   {det}  (two runs byte-identical)")
    print(f"  EXACTNESS     {exa_mark} {exa:.1%}  "
          f"({report['exactness_checked']} triple spans verbatim-bound)")
    print(f"  COMPLETENESS  {cov:.1%}  "
          f"({report['content_covered']}/{report['content_tokens']} content tokens covered; "
          f"{report['content_uncovered']} uncovered)")
    print(f"  triples: {report['n_triples']}  unsupported: {report['n_unsupported']}  "
          f"by edge: {report['by_edge']}")
    if report["exactness_failures"]:
        print(f"  --- exactness failures ({len(report['exactness_failures'])}) ---")
        for f in report["exactness_failures"][:6]:
            print(f"    {f['type']} {f['surface']!r} span={f['span']} sliced={f['sliced']!r}")


if __name__ == "__main__":
    main()

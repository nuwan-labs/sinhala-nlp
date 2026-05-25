"""
gap_report.py
─────────────
Block F of the prose-extraction pipeline — the iteration loop.

Runs the prose extractor over a batch of inputs and turns the two failure
channels into a ranked, actionable backlog:

  • NIL tokens     — content tokens no span covered. Each is triaged via
                     resolver Module A (the Mishra-Sinhala signal):
                       tatsama  → RESOLVER_CANDIDATE (Module B would catch it)
                       other    → GAZETTEER_CANDIDATE (add to a lexicon)
                       artefact → IGNORE (OCR junk / punctuation)
                     Frequency-ranked, so the highest-leverage additions
                     surface first.
  • unsupported    — triples rejected at schema-validation, grouped by reason.

The loop is: extract → gap_report → patch lexicons/templates → re-extract,
until coverage flat-lines. This module produces the work-item list that
drives each patch.

Inputs: by default it reconstructs pseudo-prose from the tabular structured
corpus (data/structured/*_structured.json) plus any explicit text files, so
there's a real batch to profile even before a prose corpus is OCR'd.

Usage:
  python gap_report.py                       # batch over structured corpus
  python gap_report.py --files a.txt b.txt   # explicit prose files
  python gap_report.py --limit 50            # cap reconstructed entries
  python gap_report.py --json
"""
from __future__ import annotations
import argparse
import glob
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "resolvers"))
from extract_prose import ProseExtractor       # noqa: E402

# Module A — the offline tatsama/other/artefact router (no heavy deps).
try:
    from sanskrit_resolver import classify as module_a_classify   # noqa: E402
except Exception:
    def module_a_classify(tok):     # fallback if resolver import fails
        return "other"

# Shared stopword set (function/connective words) from the audit module, so
# they don't pollute the GAZETTEER_CANDIDATE backlog.
from audit_prose import _STOPWORDS                                # noqa: E402

STRUCTURED = REPO / "data" / "structured"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


# ── reconstruct pseudo-prose from a tabular structured entry ────────────────
def entry_to_prose(e: dict) -> str | None:
    num = e.get("අංකය")
    name = (e.get("යෝග නාමය") or "").strip()
    if num is None and not name:
        return None
    ings = ", ".join((i.get("ද්‍රව්‍යය") or "").strip()
                     for i in (e.get("යෝගය") or []) if (i.get("ද්‍රව්‍යය") or "").strip())
    parts = [f"{num}. {name}" if num is not None else name]
    if ings:
        parts.append(f"යෝගය:- {ings}")
    for key, label in (("සංස්කරණය", "සංස්කරණය"), ("ප්‍රයෝග", "ප්‍රයෝග"),
                       ("අනුපාන", "අනුපාන"), ("මාත්‍රාව", "මාත්‍රාව")):
        v = (e.get(key) or "").strip()
        if v:
            parts.append(f"{label}:- {v}")
    return ". ".join(parts)


def load_batch(files: list[str], limit: int) -> list[tuple[str, str]]:
    """Return list of (doc_id, text). Explicit files take priority; else
    reconstruct from the structured corpus."""
    batch: list[tuple[str, str]] = []
    if files:
        for f in files:
            batch.append((Path(f).name, Path(f).read_text(encoding="utf-8")))
        return batch
    n = 0
    for path in sorted(glob.glob(str(STRUCTURED / "*_structured.json"))):
        d = json.load(open(path, encoding="utf-8"))
        for e in d.get("entries", []):
            text = entry_to_prose(e)
            if not text:
                continue
            batch.append((f"{Path(path).stem}/{e.get('අංකය')}", text))
            n += 1
            if limit and n >= limit:
                return batch
    return batch


def run(files: list[str], limit: int) -> dict:
    ex = ProseExtractor.load_default()
    batch = load_batch(files, limit)

    nil_counter: Counter = Counter()
    unsupported_reasons: Counter = Counter()
    edge_counter: Counter = Counter()
    n_triples = 0
    n_docs = 0
    cov_num = cov_den = 0      # for an aggregate completeness number

    for doc_id, text in batch:
        r = ex.extract(text)
        n_docs += 1
        n_triples += r["stats"]["n_triples"]
        for t in r["triples"]:
            edge_counter[t["type"]] += 1
        for u in r["unsupported"]:
            unsupported_reasons[u.get("reason", "?")] += 1
        for nrec in r["nils"]:
            nil_counter[nfc(nrec["text"]).strip(" .,;:-–()")] += 1

    # Triage NILs by Module A.
    triage = {"RESOLVER_CANDIDATE": [], "GAZETTEER_CANDIDATE": [], "IGNORE": []}
    for tok, freq in nil_counter.most_common():
        if not tok or len(tok) < 2:
            continue
        if tok in _STOPWORDS:
            triage["IGNORE"].append((tok, freq))
            continue
        cls = module_a_classify(tok)
        if cls == "tatsama":
            triage["RESOLVER_CANDIDATE"].append((tok, freq))
        elif cls == "artefact":
            triage["IGNORE"].append((tok, freq))
        else:
            triage["GAZETTEER_CANDIDATE"].append((tok, freq))

    return {
        "n_docs": n_docs,
        "n_triples": n_triples,
        "edges": dict(edge_counter),
        "unsupported_reasons": dict(unsupported_reasons.most_common()),
        "nil_total_distinct": len(nil_counter),
        "nil_total_occurrences": sum(nil_counter.values()),
        "triage_counts": {k: len(v) for k, v in triage.items()},
        "top_gazetteer_candidates": triage["GAZETTEER_CANDIDATE"][:40],
        "top_resolver_candidates":  triage["RESOLVER_CANDIDATE"][:40],
        "top_ignore":               triage["IGNORE"][:15],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", nargs="*", default=[],
                    help="explicit prose text files (else reconstruct from corpus)")
    ap.add_argument("--limit", type=int, default=200,
                    help="max reconstructed entries to profile")
    ap.add_argument("--out", default=str(REPO / "data" / "lexicons" / "prose_gap_report.json"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    report = run(args.files, args.limit)

    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"=== prose gap report ({report['n_docs']} docs) ===")
    print(f"  triples emitted:        {report['n_triples']}  {report['edges']}")
    print(f"  distinct NIL tokens:    {report['nil_total_distinct']}  "
          f"({report['nil_total_occurrences']} occurrences)")
    print(f"  triage:                 {report['triage_counts']}")
    print(f"  unsupported reasons:    {report['unsupported_reasons']}")
    print()
    print("  ── top GAZETTEER candidates (add these surfaces to a lexicon) ──")
    for tok, freq in report["top_gazetteer_candidates"][:20]:
        print(f"     {freq:4d}  {tok}")
    print("  ── top RESOLVER candidates (tatsama; Module B/ByT5 would catch) ──")
    for tok, freq in report["top_resolver_candidates"][:15]:
        print(f"     {freq:4d}  {tok}")
    print(f"\n  ✓ wrote {args.out}")


if __name__ == "__main__":
    main()

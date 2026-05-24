"""
extract_pratinidhi.py
─────────────────────
Parser for the substitute-substance glossary (`ප්‍රතිනිධි පරිභාෂාව`) on
pp. 77–81 of the Sri Lankan Ayurvedic Pharmacopoeia Vol I.

The table is the Department of Ayurveda's own enumeration of "if this
substance is unavailable, substitute that one" (abhāva-pratinidhi-dravya).
It is a hand-curated authority of 143 numbered rows; each row pairs two
substances. Most pairs are a Sanskrit (tatsama) headword on the left and
a Sinhala (vernacular or tadbhava) substitute on the right — but a fair
fraction pair two Sanskrit terms, and a few have one side blank or carry
an English gloss in parentheses.

Layout:
  • Two-column (gutter at x ≈ 0.5), same as pp. 444–453.
  • OCR reads top-to-bottom left, then top-to-bottom right per page.
  • Within each row of each column, the pattern is:
        N. <LHS-term> = <RHS-term>          (most common)
        N. <LHS-term>                        (no substitute given)
        N. <LHS-term> = (<English-gloss>)    (English-only RHS)

Output: data/lexicons/pratinidhi_lookup.json
  {
    "metadata": {...},
    "entries": [{num, lhs_si, rhs_si, gloss_en, page, col, y}, ...],
    "by_lhs": { "<lhs_si>": entry_record, ... },
    "by_rhs": { "<rhs_si>": entry_record, ... }
  }

The downstream resolver (Tier 1b, see resolvers/sanskrit_resolver.py)
treats both sides as candidate Sinhala surface forms; if either resolves
in Monier-Williams via Module B, the unresolved partner inherits that
Sanskrit lemma.

Usage:
  python extract_pratinidhi.py
  python extract_pratinidhi.py --debug 78
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# Reuse only the NFC helper from materia_medica. The cluster_rows()
# there uses a running-max y anchor which drifts on this table — entries
# 22…27 (y=0.19…0.29) collapse into one cluster because each y-diff is
# ≤ Y_TOL and the anchor keeps shifting up. We need an absolute anchor.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from extract_materia_medica import nfc  # noqa: E402


Y_TOL_ABS = 0.013   # max y-span within ONE row (absolute, no drift)
# 0.013 catches multi-line wraps that sit ~0.012 below the entry-num
# (e.g. entry 51 on p.78: number at y=0.810, LHS "චීන අල" at y=0.812).


def cluster_rows(words):
    """Cluster (x, y, text) words into visual rows. The cluster start-y
    is fixed when the cluster opens, so consecutive rows ≤ Y_TOL_ABS apart
    do NOT merge into a chain."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: (w[1], w[0]))
    rows, cur, start_y = [], [ordered[0]], ordered[0][1]
    for w in ordered[1:]:
        if w[1] > start_y + Y_TOL_ABS:
            rows.append(cur)
            cur, start_y = [w], w[1]
        else:
            cur.append(w)
            # Do NOT update start_y here — that's the bug we're avoiding.
    rows.append(cur)
    import statistics
    out = []
    for cluster in rows:
        cluster_sorted = sorted(cluster, key=lambda w: w[0])
        ys = [w[1] for w in cluster_sorted]
        out.append({"y": round(statistics.median(ys), 4),
                    "words": cluster_sorted})
    return out

EXTRACTOR_VERSION = "pratinidhi_v1"

# Column zones (normalised x).  Determined empirically on p.77.
# Entry numbers are at x ≈ 0.14; Sanskrit headwords start at x ≈ 0.17.
NUM_X_MAX  = 0.16   # entry-number column "1.", "2.", "143."
LHS_X_MIN  = 0.16   # LHS Sanskrit headword + optional Sinhala paraphrase
LHS_X_MAX  = 0.45
RHS_X_MIN  = 0.50   # RHS substitute(s)
# x in [LHS_X_MAX, RHS_X_MIN) is the "middle gutter" of ditto / noise marks.

ENTRY_NUM_RE = re.compile(r"^(\d{1,3})\s*\.?\s*$")  # "1." or "143" or "1"

# Pages of the pratinidhi table (verified by entry-number range).
PAGES = list(range(77, 82))
BATCH = "ocr_results_output-51-to-100.json"

# Per-page y-ranges where the table is present.  Page 77 has 4 intro
# paragraphs above the "අභාවයෙහි" header — the table only starts at
# y > 0.55 on that page.  Other pages are pure table from top.
TABLE_Y_MIN = {77: 0.55}

# Section header on p. 77 — used only for sanity, not for transitions.
HEADER_MARKERS = tuple(unicodedata.normalize("NFC", x)
                       for x in ("ප්‍රතිනිධි", "පරිභාෂාව"))

GLOSS_EN_RE = re.compile(r"\(([A-Za-z][A-Za-z\s\-]+)\)")
TRAILING_NUM_RE = re.compile(r"\s*\d{1,3}\s*$")  # noise "22" footnote markers
DITTO_RE       = re.compile(r"^[,.\"'`]+$")


# ── helpers ──────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _word_text(word):
    return "".join(s.get("text", "") for s in word.get("symbols", []))


def words_for_page(page_node):
    """Pratinidhi-tuned word extractor: keeps `N.` entry numbers, drops
    only lone punctuation and obvious page numbers."""
    out = []
    for block in page_node.get("blocks", []):
        for para in block.get("paragraphs", []):
            for word in para.get("words", []):
                nv = word["boundingBox"]["normalizedVertices"]
                x = nv[0].get("x", 0.0)
                y = nv[0].get("y", 0.0)
                text = _word_text(word).strip()
                if not text:
                    continue
                # Drop bottom-of-page running page numbers
                if y > 0.92 and re.fullmatch(r"\d{1,4}", text):
                    continue
                # Drop lone non-alphanumeric punctuation, but keep "=" — it
                # separates the source headword from its Sinhala paraphrase.
                if len(text) == 1 and not text.isalnum() and text != "=":
                    continue
                out.append((round(x, 4), round(y, 4), text))
    return out


def clean_side(text: str) -> tuple[str, str | None]:
    """Strip OCR noise from one side of an entry. Returns (clean_si, gloss_en)."""
    if not text:
        return "", None
    s = text.strip()
    # Capture and remove any (English) glosses
    gloss = None
    g = GLOSS_EN_RE.search(s)
    if g:
        gloss = g.group(1).strip()
        s = GLOSS_EN_RE.sub("", s).strip()
    # Strip stray trailing numbers (page-marker noise, e.g. "22")
    s = TRAILING_NUM_RE.sub("", s)
    # Drop stray punctuation, ZWJ-only artefacts
    s = s.strip(" .,;:|—‍‍")
    s = nfc(s)
    return s, gloss


def _zone_text(words, x_min, x_max):
    """Concatenate Sinhala text from words whose x falls in [x_min, x_max)."""
    in_zone = [w for w in words if x_min <= w[0] < x_max]
    return nfc(" ".join(w[2] for w in in_zone))


def parse_page(page_node, page_num: int):
    """Returns list of entry dicts for one page.

    Each row is split into three x-zones — entry-number, LHS, RHS — using
    the constants at the top of this module. A row qualifies as an entry
    iff the entry-number zone contains a token matching ENTRY_NUM_RE.
    Rows that lack an entry number (page header, intro prose, RHS-wrap
    continuations) are merged into the previous entry's RHS so that
    multi-line substitutes are preserved.
    """
    raw = words_for_page(page_node)
    # Crop the page to the table-only y-range when one is set.
    y_min = TABLE_Y_MIN.get(page_num, 0.0)
    if y_min > 0:
        raw = [w for w in raw if w[1] >= y_min]
    rows = cluster_rows(raw)
    entries = []
    last_entry = None    # last emitted entry, for wrap-continuation merging
    for row in rows:
        words = row["words"]
        # Find an entry-number token in the leftmost zone.
        num_tokens = [w for w in words if w[0] < NUM_X_MAX]
        num = None
        for w in num_tokens:
            m = ENTRY_NUM_RE.match(w[2])
            if m:
                num = int(m.group(1))
                break
        lhs_text = _zone_text(words, LHS_X_MIN, LHS_X_MAX)
        rhs_text = _zone_text(words, RHS_X_MIN, 1.01)
        if num is not None:
            # New entry — parse LHS for "= <alt>" and any (English) gloss.
            # The "=" lives inside lhs_text because it sits in [0.21, 0.25]
            # which is inside the LHS zone.
            lhs_main, _, lhs_alt = lhs_text.partition("=")
            lhs_si, lhs_gloss = clean_side(lhs_main)
            alt_si, alt_gloss = clean_side(lhs_alt)
            rhs_si, rhs_gloss = clean_side(rhs_text)
            gloss = lhs_gloss or alt_gloss or rhs_gloss
            if not lhs_si:
                continue
            entry = {
                "num":         num,
                "lhs_si":      lhs_si,
                "lhs_alt_si":  alt_si or None,
                "rhs_si":      rhs_si or None,
                "gloss_en":    gloss,
                "page":        page_num,
                "y":           row["y"],
            }
            entries.append(entry)
            last_entry = entry
        else:
            # Continuation row: no entry number. If the RHS zone has text,
            # append it to the last entry's rhs_si. Ignore LHS continuations
            # for now (rare and usually noise marks like ",,").
            if last_entry is not None and rhs_text:
                extra, _ = clean_side(rhs_text)
                if extra:
                    if last_entry["rhs_si"]:
                        last_entry["rhs_si"] = f"{last_entry['rhs_si']} {extra}"
                    else:
                        last_entry["rhs_si"] = extra
    return entries


# ── full run ─────────────────────────────────────────────────────────────────
def run(ocr_dir: Path, debug_page: int | None = None):
    path = ocr_dir / BATCH
    if not path.exists():
        sys.exit(f"ERROR: OCR batch file not found: {path}")
    print(f"  reading {path.name} …", file=sys.stderr)
    data = json.load(open(path, encoding="utf-8"))
    page_index = {}
    for resp in data["responses"]:
        pg = (resp.get("context") or {}).get("pageNumber")
        if pg in PAGES:
            fta = resp.get("fullTextAnnotation") or {}
            pages = fta.get("pages") or [{}]
            page_index[pg] = pages[0]

    all_entries: list[dict] = []
    per_page_count = {}
    for pg in PAGES:
        if pg not in page_index:
            print(f"    ! page {pg} not in batch", file=sys.stderr)
            continue
        ents = parse_page(page_index[pg], pg)
        per_page_count[pg] = len(ents)
        if debug_page == pg:
            _dump_debug(pg, page_index[pg], ents)
        all_entries.extend(ents)

    # Deduplicate by entry number (in case OCR pulled the same row twice).
    by_num: dict[int, dict] = {}
    for ent in all_entries:
        n = ent["num"]
        if n in by_num:
            # Prefer the entry with a non-null rhs_si.
            if by_num[n]["rhs_si"] is None and ent["rhs_si"] is not None:
                by_num[n] = ent
        else:
            by_num[n] = ent
    entries = [by_num[n] for n in sorted(by_num)]

    by_lhs = {e["lhs_si"]: e for e in entries if e["lhs_si"]}
    by_rhs = {e["rhs_si"]: e for e in entries if e.get("rhs_si")}

    return {
        "metadata": {
            "extractor_version": EXTRACTOR_VERSION,
            "built_at": now_iso(),
            "source_doc": "Sri Lankan Ayurvedic Pharmacopoeia, Vol I",
            "source_pages": [PAGES[0], PAGES[-1]],
            "section_name_si": "ප්‍රතිනිධි පරිභාෂාව",
            "section_name_iast": "pratinidhi-paribhāṣā",
            "entries_total":     len(entries),
            "entries_with_substitute": sum(1 for e in entries if e["rhs_si"]),
            "entries_per_page":  per_page_count,
            "expected_max_num":  143,
            "actual_max_num":    max(by_num) if by_num else None,
        },
        "entries":  entries,
        "by_lhs":   by_lhs,
        "by_rhs":   by_rhs,
    }


def _dump_debug(pg, page_node, entries):
    print(f"\n=== DEBUG page {pg} ===")
    rows = cluster_rows(words_for_page(page_node))
    for row in rows:
        nz = [w[2] for w in row["words"] if w[0] < NUM_X_MAX]
        lz = [w[2] for w in row["words"] if LHS_X_MIN <= w[0] < LHS_X_MAX]
        rz = [w[2] for w in row["words"] if RHS_X_MIN <= w[0]]
        print(f"  y={row['y']:.3f}  #={' '.join(nz):6s}  L={' '.join(lz):30s}  R={' '.join(rz)}")
    print(f"\n  Emitted {len(entries)} entries:")
    for e in entries[:20]:
        rhs = e['rhs_si'] or '—'
        alt = f" ≃ {e['lhs_alt_si']}" if e.get('lhs_alt_si') else ""
        gl  = f" [{e['gloss_en']}]" if e['gloss_en'] else ""
        print(f"    #{e['num']:3d}  {e['lhs_si']:18s}{alt}  →  {rhs}{gl}")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent
    repo_root = here.parent
    outer_root = repo_root.parent

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ocr-dir", default=str(outer_root / "ocr_json"))
    ap.add_argument("--out",     default=str(repo_root / "data" / "lexicons"
                                              / "pratinidhi_lookup.json"))
    ap.add_argument("--debug",   type=int, default=None)
    args = ap.parse_args()

    result = run(Path(args.ocr_dir), debug_page=args.debug)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    meta = result["metadata"]
    print(f"\n✓ wrote {args.out}")
    print(f"  total entries     : {meta['entries_total']}  "
          f"(expected up to {meta['expected_max_num']})")
    print(f"  with substitute   : {meta['entries_with_substitute']}")
    print(f"  highest entry num : {meta['actual_max_num']}")
    print(f"  per-page counts   : {meta['entries_per_page']}")


if __name__ == "__main__":
    main()

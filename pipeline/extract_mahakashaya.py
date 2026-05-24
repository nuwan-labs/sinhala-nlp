"""
extract_mahakashaya.py
──────────────────────
Parser for Caraka's `පඤ්චාශන්මහාකෂාය ද්‍රව්‍ය ගණය` ("fifty mahā-kaṣāya
substance groups") on pp. 82–90 of the Sri Lankan Ayurvedic Pharmacopoeia.

The text divides Ayurvedic substances into ~10 *vargas* (categories),
each containing 6–7 *ganas* (therapeutic-action groups). Each gana is
named for its primary clinical action — *jīvanīya* (life-promoting),
*bṛmhaṇīya* (bulk-promoting), *kāsahara* (cough-suppressing), etc. —
and lists 5–15 substances belonging to that gana.

Per-page structure (single column, prose layout):

    <V>. <varga-ordinal> වර්ගය             ← varga header
    1.  <gana-name>  ද්‍රව්‍ය               ← gana index (top-of-page table)
    2.  <gana-name>  ද්‍රව්‍ය
    ...
    1. <gana-name> ද්‍රව්‍ය:-              ← gana paragraph (substance list)
    <subst>, <subst>, <subst>...            (comma-separated, may wrap)
    <closing prose, e.g. "යන මේ දශකය ...">
    2. <gana-name> ද්‍රව්‍ය:-
    ...

Algorithm:
  1. Concatenate full OCR text for pp. 82–90 in page order.
  2. Walk the concatenated text. Match three line patterns:
       VARGA_HEADER  → set current varga.
       GANA_PARAGRAPH → start a new gana; capture substance list until
                        the next gana / varga / EOF.
       (the top-of-page gana INDEX is ignored — content paragraphs
        carry the same info more reliably.)
  3. Per gana, split substance text on commas; strip trailing
     application-prose ("යන මේ දශකය ..." / "ප්‍රයෝජ්‍ය" / "කාර්‍ය්‍ය").

Output: data/lexicons/mahakashaya_groups.json
  {
    "metadata": {...},
    "vargas": [
      {"varga_num": 1, "varga_name_si": "ප්‍රථම",
       "ganas": [
         {"gana_num": 1, "gana_name_si": "ජීවණීය",
          "gana_name_iast": "jīvanīya",        # if a curated map exists
          "substances": ["...", "..."]},
         ...
       ]
      }, ...
    ],
    "by_substance": {                            # reverse-lookup
      "<sinhala_surface>": [{"varga": N, "gana": M, "gana_name_si": "..."}]
    }
  }

Usage:
  python extract_mahakashaya.py
  python extract_mahakashaya.py --debug 85
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "mahakashaya_v1"

# Page range.  The text starts at p.82 ("1. ප්‍රථම වර්ගය") and ends near
# p.90 ("10. දශම වර්ගය").
PAGES = list(range(82, 91))
BATCH = "ocr_results_output-51-to-100.json"

# Hand-curated ordinal → (canonical_num, IAST). Used to derive the
# *canonical* varga number from the Sanskrit ordinal word — more reliable
# than the OCR'd numeric prefix, which mis-reads "3" as "4" on p.83 and
# "6" as "5" on p.85.  Variant spellings ("තෘතිය" vs "තෘතීය") accepted.
VARGA_ORDINAL = {
    "ප්‍රථම":  (1,  "prathama"),
    "ද්විතීය": (2,  "dvitīya"),
    "තෘතීය":  (3,  "tṛtīya"),  "තෘතිය":  (3, "tṛtīya"),
    "චතුර්ථ":  (4,  "caturtha"),
    "පඤ්චම":   (5,  "pañcama"),
    "ෂෂ්ඨ":    (6,  "ṣaṣṭha"),
    "සප්තම":   (7,  "saptama"),
    "අෂ්ටම":    (8,  "aṣṭama"),
    "නවම":     (9,  "navama"),
    "දශම":     (10, "daśama"),
}

# Regex patterns (Unicode-aware).
NFC = lambda s: unicodedata.normalize("NFC", s or "")

VARGA_HEADER_RE = re.compile(
    r"^\s*(\d{1,2})\.\s+([඀-෿‍‌]{2,10})\s+වර්ගය\s*$",
    re.MULTILINE,
)

# A gana paragraph starts with "<N>. <name> ද්‍රව්‍ය:-" OR
#                              "<N>. <name> ගණය:-".  The colon-dash is
# the diagnostic marker that distinguishes content paragraphs from
# the index-table rows (which have NO colon).
GANA_PARAGRAPH_RE = re.compile(
    r"(\d{1,2})\s*\.\s*([඀-෿‍‌\s]+?)\s*(?:ද්‍රව්‍ය|ගණය)\s*:\s*-",
    re.UNICODE,
)

# Trailing application prose — substances stop here.
TRAILING_PROSE_RE = re.compile(
    r"(යන\s+(මේ\s+)?දශකය|යන\s+දශකය|යන\s+මේ\s+ගණ|ප්‍රයෝජ්‍ය|"
    r"කාර්‍ය්‍ය|යන\s+මේ|යනු|=)",
    re.UNICODE,
)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def page_text(d, page_num):
    for r in d["responses"]:
        if r.get("context", {}).get("pageNumber") == page_num:
            return r.get("fullTextAnnotation", {}).get("text", "")
    return ""


def clean_substance(text):
    """Normalise a single substance phrase: strip whitespace, drop OCR
    parenthetical decorations like "(හිං)" annotations."""
    s = NFC(text).strip(" .,;:-—()")
    s = re.sub(r"\s+", " ", s)
    return s


def parse_substances(blob):
    """Split a substance-list blob on commas, return cleaned Sinhala phrases.
    Stops at any trailing application prose."""
    m = TRAILING_PROSE_RE.search(blob)
    if m:
        blob = blob[:m.start()]
    out = []
    for piece in re.split(r"[,،।]+", blob):
        piece = clean_substance(piece)
        if piece and len(piece) >= 2:
            out.append(piece)
    return out


def parse_full_text(text):
    """Walk concatenated text, emit list of {varga_num, gana_num,
    gana_name_si, substances}."""
    text = NFC(text)
    # Build a list of (offset, kind, payload) markers, sort by offset.
    markers = []
    for m in VARGA_HEADER_RE.finditer(text):
        ordinal_word = NFC(m.group(2).strip())
        # Canonical varga number comes from the ordinal word, not the OCR
        # digit — the digit is misread on p.83 ("3"→"4") and p.85 ("6"→"5").
        canon = VARGA_ORDINAL.get(ordinal_word)
        if canon:
            varga_num, _iast = canon
        else:
            varga_num = int(m.group(1))
        markers.append((m.start(), "varga", (varga_num, ordinal_word)))
    for m in GANA_PARAGRAPH_RE.finditer(text):
        gname = NFC(m.group(2).strip())
        # Filter out gana-index matches: index rows have the gana-name
        # split across lines, but the ":-" suffix is unique to paragraphs
        # so all matches here are content paragraphs already.
        markers.append((m.end(), "gana",
                        (int(m.group(1)), gname, m.start())))
    markers.sort()

    entries = []
    cur_varga_num, cur_varga_name = None, None
    for i, (off, kind, payload) in enumerate(markers):
        if kind == "varga":
            cur_varga_num, cur_varga_name = payload
            continue
        if kind == "gana" and cur_varga_num is not None:
            gana_num, gana_name, start_off = payload
            # Content runs from `off` (end of ":-") until next marker, or EOF.
            end_off = markers[i+1][0] if i+1 < len(markers) else len(text)
            blob = text[off:end_off]
            substances = parse_substances(blob)
            entries.append({
                "varga_num":    cur_varga_num,
                "varga_name_si": cur_varga_name,
                "varga_name_iast": (VARGA_ORDINAL.get(cur_varga_name) or (None, None))[1],
                "gana_num":     gana_num,
                "gana_name_si": gana_name,
                "substances":   substances,
            })
    return entries


def build_structure(entries):
    """Pivot the flat entry list into the nested {vargas[].ganas[]} schema."""
    by_varga = {}
    order = []
    for e in entries:
        v = e["varga_num"]
        if v not in by_varga:
            iast_pair = VARGA_ORDINAL.get(e["varga_name_si"])
            iast = iast_pair[1] if iast_pair else None
            by_varga[v] = {
                "varga_num":      v,
                "varga_name_si":  e["varga_name_si"],
                "varga_name_iast": iast,
                "ganas":          [],
            }
            order.append(v)
        by_varga[v]["ganas"].append({
            "gana_num":     e["gana_num"],
            "gana_name_si": e["gana_name_si"],
            "substances":   e["substances"],
        })
    return [by_varga[v] for v in order]


def reverse_index(entries):
    out = {}
    for e in entries:
        for s in e["substances"]:
            out.setdefault(s, []).append({
                "varga_num":     e["varga_num"],
                "varga_name_si": e["varga_name_si"],
                "gana_num":      e["gana_num"],
                "gana_name_si":  e["gana_name_si"],
            })
    return out


# ── full run ─────────────────────────────────────────────────────────────────
def run(ocr_dir: Path, debug_page=None):
    path = ocr_dir / BATCH
    if not path.exists():
        sys.exit(f"ERROR: OCR batch file not found: {path}")
    print(f"  reading {path.name} …", file=sys.stderr)
    data = json.load(open(path, encoding="utf-8"))

    # Concatenate text for pp. PAGES[0]..PAGES[-1] in page order.
    parts = []
    for pg in PAGES:
        t = page_text(data, pg)
        if debug_page == pg:
            print(f"\n=== DEBUG p{pg} full text (first 40 lines) ===")
            for i, ln in enumerate(t.split("\n")[:40]):
                print(f"  {i:2d}: {ln}")
        parts.append(t)
    full_text = "\n".join(parts)

    entries = parse_full_text(full_text)
    vargas = build_structure(entries)
    by_substance = reverse_index(entries)

    # Stats
    n_vargas = len(vargas)
    n_ganas = sum(len(v["ganas"]) for v in vargas)
    n_subst_total = sum(len(g["substances"])
                        for v in vargas for g in v["ganas"])
    n_subst_uniq = len({s for v in vargas for g in v["ganas"]
                          for s in g["substances"]})
    return {
        "metadata": {
            "extractor_version": EXTRACTOR_VERSION,
            "built_at": now_iso(),
            "source_doc": "Sri Lankan Ayurvedic Pharmacopoeia, Vol I",
            "source_pages": [PAGES[0], PAGES[-1]],
            "section_name_si":   "පඤ්චාශන්මහාකෂාය ද්‍රව්‍ය ගණය",
            "section_name_iast": "pañcāśanmahākaṣāya-dravya-gaṇa",
            "n_vargas": n_vargas,
            "n_ganas":  n_ganas,
            "n_substance_mentions": n_subst_total,
            "n_unique_substances":  n_subst_uniq,
        },
        "vargas": vargas,
        "by_substance": by_substance,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent
    repo_root = here.parent
    outer_root = repo_root.parent

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ocr-dir", default=str(outer_root / "ocr_json"))
    ap.add_argument("--out", default=str(repo_root / "data" / "lexicons"
                                          / "mahakashaya_groups.json"))
    ap.add_argument("--debug", type=int, default=None)
    args = ap.parse_args()

    result = run(Path(args.ocr_dir), debug_page=args.debug)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    meta = result["metadata"]
    print(f"\n✓ wrote {args.out}")
    print(f"  vargas:                  {meta['n_vargas']}")
    print(f"  ganas (total):           {meta['n_ganas']}")
    print(f"  substance mentions:      {meta['n_substance_mentions']}")
    print(f"  unique substances:       {meta['n_unique_substances']}")
    for v in result["vargas"]:
        print(f"    varga {v['varga_num']:2d} ({v['varga_name_si']:10s}): "
              f"{len(v['ganas'])} ganas, "
              f"{sum(len(g['substances']) for g in v['ganas'])} substance mentions")


if __name__ == "__main__":
    main()

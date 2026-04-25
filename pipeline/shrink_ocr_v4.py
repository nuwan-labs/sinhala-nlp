"""
shrink_ocr_v4.py  — row-level compact format
─────────────────────────────────────────────
Extends v3 by pre-clustering words into visual rows during the shrink step.

WHY ROW-LEVEL?
  v3 output is a flat word list; every downstream extractor must re-cluster
  rows independently and tune y-tolerance.  Moving row-clustering here means:
    • Clustering logic lives in one place (maintained once).
    • Each row stores ALL word data (x, block_id, para_id, text) so extractors
      can reason about OCR-block spans within a row — without re-inspecting
      neighbouring rows.

OUTPUT FORMAT
─────────────
{
  "page": 305,
  "w": 595, "h": 841,
  "rows": [
    {
      "y": 0.080,          ← median y of the row
      "w": [               ← words sorted left-to-right
        [x, block_id, para_id, "text"],
        …
      ]
    },
    …
  ]
}

Column classification is NOT pre-applied here — the extractor defines its own
thresholds.  The pre-built rows give it access to every word's x and block_id
within the same visual line.

USAGE
─────
  python shrink_ocr_v4.py page_305.json [p305_rows.json]
  python shrink_ocr_v4.py --pair page_305.json page_306.json [pair.json]
"""

import json, sys, os, re, statistics
from pathlib import Path

Y_TOL = 0.012   # max y-spread within one visual row

def _word_text(word):
    return "".join(s.get("text", "") for s in word.get("symbols", []))

def _nv_topleft(nv):
    return nv[0].get("x", 0.0), nv[0].get("y", 0.0)

def _is_page_number(x, y, text):
    return bool(re.fullmatch(r"\d{1,4}", text.strip())) and y > 0.88 and 0.35 < x < 0.65

def _cluster(word_list):
    """Cluster words → rows (list-of-lists), sorted by y then x within each row."""
    if not word_list: return []
    ordered = sorted(word_list, key=lambda w: (w[1], w[0]))  # sort by (y, x)
    rows, cur, cy = [], [ordered[0]], ordered[0][1]
    for w in ordered[1:]:
        if w[1] > cy + Y_TOL:
            rows.append(cur); cur, cy = [w], w[1]
        else:
            cur.append(w); cy = max(cy, w[1])
    if cur: rows.append(cur)
    return rows

def shrink_one(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    resp = data["responses"][0]
    fta  = resp.get("fullTextAnnotation", {})
    page = fta.get("pages", [{}])[0]
    ctx  = resp.get("context", {})

    page_num = ctx.get("pageNumber")
    if page_num is None:
        m = re.search(r"_page_(\d+)", Path(path).stem)
        page_num = int(m.group(1)) if m else None

    raw_words = []   # [x, y, block_id, para_id, text]
    for b_idx, block in enumerate(page.get("blocks", [])):
        for p_idx, para in enumerate(block.get("paragraphs", [])):
            for word in para.get("words", []):
                nv = word["boundingBox"]["normalizedVertices"]
                x, y = _nv_topleft(nv)
                text = _word_text(word).strip()
                if not text or _is_page_number(x, y, text):
                    continue
                raw_words.append([round(x, 3), round(y, 3), b_idx, p_idx, text])

    clustered = _cluster(raw_words)

    rows = []
    for cluster in clustered:
        ys = [w[1] for w in cluster]
        row_y = round(statistics.median(ys), 3)
        # Store words as [x, block_id, para_id, text]  (drop y — it's in row_y)
        words = sorted([[w[0], w[2], w[3], w[4]] for w in cluster], key=lambda w: w[0])
        rows.append({"y": row_y, "w": words})

    return {
        "page": page_num,
        "w":    page.get("width"),
        "h":    page.get("height"),
        "rows": rows,
    }

def shrink_pair(path_a, path_b):
    pa, pb = shrink_one(path_a), shrink_one(path_b)
    return {"pages": [pa["page"], pb["page"]], "w": pa["w"], "h": pa["h"],
            "page_a": pa["rows"], "page_b": pb["rows"]}

def main():
    args = sys.argv[1:]
    if not args: print(__doc__); sys.exit(1)
    if args[0] == "--pair":
        result  = shrink_pair(args[1], args[2])
        default = f"pair_{result['pages'][0]}_{result['pages'][1]}_rows.json"
        out     = args[3] if len(args) >= 4 else default
        n = sum(len(r["w"]) for r in result["page_a"]+result["page_b"])
        orig = [args[1], args[2]]
    else:
        result  = shrink_one(args[0])
        default = Path(args[0]).stem + "_rows.json"
        out     = args[1] if len(args) >= 2 else default
        n = sum(len(r["w"]) for r in result["rows"])
        orig = [args[0]]

    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))

    sz_in  = sum(os.path.getsize(p) for p in orig)
    sz_out = os.path.getsize(out)
    print(f"✓ {out}")
    print(f"  {sz_in//1024}KB → {sz_out//1024}KB  ({100*sz_out//sz_in}% of original)")
    print(f"  {len(result.get('rows', result.get('page_a',[])))} rows on first page, {n} words total")
    print("  Format: rows[i] = {y, w:[[x,block_id,para_id,text],...]}")

if __name__ == "__main__": main()

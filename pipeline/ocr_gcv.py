"""
ocr_gcv.py
──────────
Google Cloud Vision OCR for Sinhala source PDFs.

Designed for photo-to-PDF scans of old printed books where:
  - image quality is variable,
  - the language is non-default (Sinhala),
  - tighter per-page control beats a single bulk PDF call.

Pages are rendered to high-DPI PNG with PyMuPDF, then each page is
OCR'd individually with DOCUMENT_TEXT_DETECTION and an explicit
`languageHints=["si"]` hint. Output JSON files mirror the format of
the existing `data/ocr/ocr_results_output-*.json` so the downstream
pipeline (`pipeline/extract_page.py`, `pipeline/shrink_ocr_v4.py`, etc.)
can consume them unchanged.

AUTHENTICATION
──────────────
google-cloud-vision uses Application Default Credentials. Either:

  (a) `gcloud auth application-default login` (needs gcloud CLI), OR
  (b) Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

You also need a GCP project with the Cloud Vision API enabled. If
billing is not enabled or the API is off, the first call will return
HTTP 403 with a clear message.

PREREQUISITES
─────────────
  pip install google-cloud-vision pymupdf

USAGE
─────
  python ocr_gcv.py yogamalawa.pdf                       # all pages, 300 DPI
  python ocr_gcv.py yogamalawa.pdf --dpi 400             # higher sensitivity
  python ocr_gcv.py yogamalawa.pdf --start 1 --end 5     # subset
  python ocr_gcv.py yogamalawa.pdf --upscale-low-conf 0.85
                                                          # re-OCR pages
                                                          # below mean conf
                                                          # 0.85 at 1.5×DPI

OUTPUT
──────
  ocr_json/ocr_results_output-{start}-to-{end}.json
      {"responses": [<one AnnotateImageResponse dict per page>, ...]}
      Same schema as existing data/ocr/ batch JSONs.

  ocr_json/_ocr_log.tsv
      page<TAB>chars<TAB>mean_conf<TAB>seconds<TAB>note
      Append-only audit log across runs.

"More sensitive" — what the knobs actually do
─────────────────────────────────────────────
  --dpi             ↑ DPI → bigger image → GCV sees more detail.
                    300 is good for clean scans; 400–600 for blurry,
                    low-contrast, or poorly inked old prints.
  --language-hint   Forces GCV to use Sinhala-specific symbol models.
                    Without this, GCV auto-detects language per region
                    and can misclassify Sinhala characters as Devanagari
                    or generic Indic glyphs.
  feature           DOCUMENT_TEXT_DETECTION (vs. TEXT_DETECTION) uses
                    a layout-aware model for printed pages — block /
                    paragraph / word / symbol hierarchy with confidence
                    per element. Always the right choice for books.
  per-page calls    Each page gets its own API call, so we can retry
                    transient failures, upscale low-confidence pages,
                    and never lose a whole batch to one bad page.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# --- import deps with friendly errors ---
try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is required:  pip install pymupdf")

try:
    from google.cloud import vision
    from google.protobuf.json_format import MessageToDict
    from google.api_core import exceptions as gax
except ImportError:
    sys.exit("google-cloud-vision is required:  pip install google-cloud-vision")


# --- helpers ----------------------------------------------------------------
def render_page_png(doc, page_index, dpi):
    """Render one PDF page (0-indexed) to PNG bytes at the given DPI."""
    page = doc[page_index]
    zoom = dpi / 72.0  # PDF default coordinate system is 72 DPI
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def mean_word_confidence(response):
    """Mean word-level confidence across the page; None if no words."""
    confs = []
    fta = response.full_text_annotation
    for page in fta.pages:
        for block in page.blocks:
            for para in block.paragraphs:
                for word in para.words:
                    if word.confidence > 0:
                        confs.append(word.confidence)
    return (sum(confs) / len(confs)) if confs else None


def _normalize_bbox_inplace(obj, page_w, page_h):
    """Recursively convert every boundingBox.vertices (pixel coords) into
    boundingBox.normalizedVertices (0–1 coords), in place. Matches the
    schema the async-batch API produces and the downstream pipeline expects.
    """
    if isinstance(obj, dict):
        if "boundingBox" in obj and isinstance(obj["boundingBox"], dict):
            bb = obj["boundingBox"]
            if "vertices" in bb and "normalizedVertices" not in bb:
                bb["normalizedVertices"] = [
                    {"x": v.get("x", 0) / page_w,
                     "y": v.get("y", 0) / page_h}
                    for v in bb["vertices"]
                ]
                del bb["vertices"]
        for v in obj.values():
            _normalize_bbox_inplace(v, page_w, page_h)
    elif isinstance(obj, list):
        for v in obj:
            _normalize_bbox_inplace(v, page_w, page_h)


def response_to_dict(response, page_number_1indexed):
    """AnnotateImageResponse → batch-JSON-compatible dict.

    Produces camelCase field names (`fullTextAnnotation`, `pageNumber`)
    and drops the redundant `textAnnotations` block, matching the
    schema of the existing data/ocr/*.json files so that the downstream
    pipeline (pipeline/extract_page.py, shrink_ocr_v4.py etc.) consumes
    the output without any changes. Pixel-space bounding boxes are
    normalized to 0–1 using the page dimensions reported by GCV.
    """
    d = MessageToDict(response._pb)  # default = camelCase, drops snake_case
    d.pop("textAnnotations", None)   # keep only fullTextAnnotation
    pages = d.get("fullTextAnnotation", {}).get("pages", [])
    if pages:
        page_w = pages[0].get("width") or 1
        page_h = pages[0].get("height") or 1
        _normalize_bbox_inplace(d["fullTextAnnotation"], page_w, page_h)
    d["context"] = {"pageNumber": page_number_1indexed}
    return d


def ocr_one(client, png_bytes, language_hint, max_retries=3):
    """Call GCV with retries on transient errors. Returns AnnotateImageResponse."""
    image = vision.Image(content=png_bytes)
    ctx = vision.ImageContext(language_hints=[language_hint])
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.document_text_detection(image=image, image_context=ctx)
            if resp.error.message:
                raise RuntimeError(f"GCV error: {resp.error.message}")
            return resp
        except (gax.ServiceUnavailable, gax.DeadlineExceeded,
                gax.InternalServerError) as e:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            print(f"    transient {type(e).__name__}; retry in {wait}s")
            time.sleep(wait)


def write_batch(out_dir, start, end, responses):
    path = Path(out_dir) / f"ocr_results_output-{start}-to-{end}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"responses": responses}, f, ensure_ascii=False)
    return path


# --- main -------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="GCV OCR for Sinhala source PDFs (DOCUMENT_TEXT_DETECTION).")
    ap.add_argument("pdf", help="Input PDF path")
    ap.add_argument("--out-dir", default="ocr_json")
    ap.add_argument("--dpi", type=int, default=300,
                    help="Render DPI (raise to 400-600 for poor scans)")
    ap.add_argument("--language-hint", default="si",
                    help="GCV language hint (default si = Sinhala)")
    ap.add_argument("--start", type=int, default=1,
                    help="First PDF page to OCR (1-indexed)")
    ap.add_argument("--end", type=int, default=None,
                    help="Last PDF page to OCR (1-indexed; default = last)")
    ap.add_argument("--chunk-size", type=int, default=50,
                    help="Pages per output JSON (default 50, matches "
                         "existing batch naming convention)")
    ap.add_argument("--upscale-low-conf", type=float, default=0.0,
                    metavar="THRESHOLD",
                    help="After the first pass, re-OCR pages whose mean "
                         "word confidence is below THRESHOLD at 1.5× DPI. "
                         "Default 0 = disabled. Try 0.85 for old prints.")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"PDF not found: {pdf_path}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    n_pages = len(doc)
    start = max(1, args.start)
    end = min(args.end or n_pages, n_pages)

    print(f"PDF: {pdf_path}  ({n_pages} pages)")
    print(f"OCR range: {start}–{end}  DPI={args.dpi}  language={args.language_hint}"
          f"  feature=DOCUMENT_TEXT_DETECTION")
    print(f"Output: {out_dir}/  chunk_size={args.chunk_size}")
    print()

    # auth probe — fail fast if creds aren't set
    try:
        client = vision.ImageAnnotatorClient()
    except Exception as e:
        sys.exit(
            f"\nGCV client init failed: {e}\n"
            "Authenticate with one of:\n"
            "  gcloud auth application-default login   (needs gcloud SDK)\n"
            "  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json\n"
        )

    log_path = out_dir / "_ocr_log.tsv"
    new_log = not log_path.exists()
    log = open(log_path, "a", encoding="utf-8")
    if new_log:
        log.write("page\tchars\tmean_conf\tsec\tnote\n")

    # Pass 1: standard DPI
    page_records = {}  # page_num -> {response_dict, mean_conf, chars}
    for pg in range(start, end + 1):
        png = render_page_png(doc, pg - 1, args.dpi)
        t0 = time.time()
        try:
            resp = ocr_one(client, png, args.language_hint)
            mc = mean_word_confidence(resp) or 0.0
            text = resp.full_text_annotation.text or ""
            d = response_to_dict(resp, pg)
            page_records[pg] = {"d": d, "conf": mc, "chars": len(text)}
            dt = time.time() - t0
            print(f"  page {pg:3d}: {len(text):5d} chars  conf={mc:.3f}  {dt:.1f}s")
            log.write(f"{pg}\t{len(text)}\t{mc:.3f}\t{dt:.2f}\t\n"); log.flush()
        except Exception as e:
            dt = time.time() - t0
            print(f"  page {pg:3d}: FAIL  {type(e).__name__}: {e}")
            log.write(f"{pg}\t-\t-\t{dt:.2f}\tFAIL {type(e).__name__}\n"); log.flush()

    # Optional Pass 2: re-OCR low-confidence pages at higher DPI
    if args.upscale_low_conf > 0:
        target_dpi = int(round(args.dpi * 1.5))
        low = [pg for pg, r in page_records.items()
               if r["conf"] < args.upscale_low_conf]
        if low:
            print(f"\nPass 2: re-OCR {len(low)} pages at {target_dpi} DPI "
                  f"(mean conf < {args.upscale_low_conf})")
            for pg in low:
                png = render_page_png(doc, pg - 1, target_dpi)
                t0 = time.time()
                try:
                    resp = ocr_one(client, png, args.language_hint)
                    mc = mean_word_confidence(resp) or 0.0
                    text = resp.full_text_annotation.text or ""
                    prev = page_records[pg]
                    dt = time.time() - t0
                    if mc > prev["conf"]:
                        page_records[pg] = {
                            "d": response_to_dict(resp, pg),
                            "conf": mc, "chars": len(text),
                        }
                        note = f"upscale {args.dpi}->{target_dpi} kept (conf {prev['conf']:.2f}->{mc:.2f})"
                    else:
                        note = f"upscale {args.dpi}->{target_dpi} rejected (conf {prev['conf']:.2f} vs {mc:.2f})"
                    print(f"  page {pg:3d}: {note}  {dt:.1f}s")
                    log.write(f"{pg}\t{len(text)}\t{mc:.3f}\t{dt:.2f}\t{note}\n")
                    log.flush()
                except Exception as e:
                    print(f"  page {pg:3d}: upscale FAIL  {e}")

    # Write chunked output JSONs
    print()
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + args.chunk_size - 1, end)
        responses = [page_records[pg]["d"] for pg in range(chunk_start, chunk_end + 1)
                     if pg in page_records]
        if responses:
            path = write_batch(out_dir, chunk_start, chunk_end, responses)
            print(f"  wrote {path}  ({len(responses)} pages)")
        chunk_start = chunk_end + 1

    # Summary
    if page_records:
        mean_conf = sum(r["conf"] for r in page_records.values()) / len(page_records)
        total_chars = sum(r["chars"] for r in page_records.values())
        print(f"\nSummary: {len(page_records)}/{end-start+1} pages OCR'd  "
              f"mean conf={mean_conf:.3f}  total chars={total_chars}")
    log.close()
    print(f"Per-page log: {log_path}")
    doc.close()


if __name__ == "__main__":
    main()

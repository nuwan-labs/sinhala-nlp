"""
extract_page.py
---------------
Extracts a single page from a Google Cloud Vision document OCR JSON output.

Structure of the input file:
  {
    "inputConfig": { ... },
    "responses": [
      {
        "context": { "uri": "...", "pageNumber": 301 },
        "fullTextAnnotation": {
          "pages": [ { "blocks": [...], "width": ..., "height": ..., ... } ],
          "text": "full page text"
        }
      },
      ...
    ]
  }

Usage:
  python extract_page.py <input_json> <page_number> [output_json]

Examples:
  python extract_page.py ocr_results.json 305
  python extract_page.py ocr_results.json 305 page_305.json
  python extract_page.py ocr_results.json --list        # list all available pages
"""

import json
import sys
import os


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_pages(data: dict) -> list[int]:
    """Return a sorted list of all page numbers present in the file."""
    page_numbers = []
    for response in data.get("responses", []):
        ctx = response.get("context", {})
        if "pageNumber" in ctx:
            page_numbers.append(ctx["pageNumber"])
    return sorted(page_numbers)


def extract_page(data: dict, page_number: int) -> dict | None:
    """
    Find and return the response matching the given page number.
    Returns a self-contained dict with inputConfig + the single response.
    """
    for response in data.get("responses", []):
        ctx = response.get("context", {})
        if ctx.get("pageNumber") == page_number:
            return {
                "inputConfig": data.get("inputConfig", {}),
                "responses": [response],   # wrap in list to match original format
            }
    return None


def main():
    args = sys.argv[1:]

    if len(args) < 1:
        print(__doc__)
        sys.exit(1)

    input_path = args[0]

    if not os.path.isfile(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    data = load_json(input_path)

    # --list mode: show available pages and exit
    if len(args) >= 2 and args[1] == "--list":
        pages = list_pages(data)
        print(f"Available pages ({len(pages)} total):")
        print(pages)
        sys.exit(0)

    if len(args) < 2:
        print("ERROR: Please provide a page number. Use --list to see available pages.")
        print(__doc__)
        sys.exit(1)

    # Parse page number
    try:
        page_number = int(args[1])
    except ValueError:
        print(f"ERROR: Invalid page number '{args[1]}'. Must be an integer.")
        sys.exit(1)

    # Determine output path
    if len(args) >= 3:
        output_path = args[2]
    else:
        base = os.path.splitext(os.path.basename(input_path))[0]
        output_path = f"{base}_page_{page_number}.json"

    # Extract
    result = extract_page(data, page_number)

    if result is None:
        pages = list_pages(data)
        print(f"ERROR: Page {page_number} not found in '{input_path}'.")
        print(f"Available pages: {pages}")
        sys.exit(1)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Summary
    response = result["responses"][0]
    text_preview = response["fullTextAnnotation"]["text"][:120].replace("\n", " ")
    pages_in_response = len(response["fullTextAnnotation"].get("pages", []))
    blocks = sum(
        len(p.get("blocks", []))
        for p in response["fullTextAnnotation"].get("pages", [])
    )

    print(f"✓ Extracted page {page_number} → '{output_path}'")
    print(f"  Pages in response : {pages_in_response}")
    print(f"  Blocks            : {blocks}")
    print(f"  Text preview      : {text_preview}...")


if __name__ == "__main__":
    main()

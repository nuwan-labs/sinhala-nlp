# Sinhala Traditional Medicine NLP

**A knowledge extraction pipeline for the Sri Lankan Ayurvedic Pharmacopoeia**

---

## What this is

This repository contains the data, processing pipeline, and research infrastructure for digitizing and structuring the *Sinhala Ayurvedic Pharmacopoeia* — an authoritative reference for traditional Sri Lankan herbal medicine. The source is a physical multi-volume book written entirely in Sinhala.

**Volume I** (this repository): Pages 151–450, containing 707 traditional herbal formulas.
**Volumes II and III**: Physical copies in hand — next phase of the project.

The long-term goal is a knowledge graph of traditional Sri Lankan medicine, grounded in a labeled NLP corpus, that can read and extract structured information from any new manuscript in this domain.

---

## Current State

| Metric | Value |
|---|---|
| Structured formula entries | **707** |
| Source pages processed | 172 – 443 |
| Ingredient cells extracted | 11,007 |
| Total tokens (all fields) | 62,562 |
| Vocabulary size | 7,100 unique types |
| Field fill rate — Usage/Indication | 96.5% |
| Field fill rate — Preparation | 63.1% |
| Artefact token rate | 17.3% |

---

## Pipeline Architecture

```
Pharmacopoeia_Vol_I.pdf
        │
        ▼  Google Cloud Vision (batch OCR)
data/ocr/*.json          (~7–10 MB per batch, 11 batches, pages 1–525)
        │
        ▼  pipeline/extract_page.py
per-page GCV JSON        (preserves fullTextAnnotation tree)
        │
        ▼  pipeline/shrink_ocr_v4.py
data/rows/*.json         (row-level: each row = {y, w: [[x, block_id, para_id, text], ...]})
        │
        ▼  pipeline/extract_pharma_v4.py
data/structured/*.json   (707 entries with Sinhala field names)
        │
        ▼  analysis/nlp_stats.py
NLP statistics report    (vocabulary, co-occurrence, field fill rates, artefact analysis)
```

---

## Output Schema

Each entry in `data/structured/*.json`:

```json
{
  "අංකය": 44,
  "යෝග නාමය": "...",
  "යෝගය": [{"ද්‍රව්‍යය": "...", "ප්‍රමාණය": "...", "ග්‍රෑ": 0.0}],
  "සංස්කරණය": "...",
  "ප්‍රයෝග": "...",
  "අනුපාන": "...",
  "මාත්‍රාව": "...",
  "සටහන": "...",
  "source_page": 172
}
```

Fields are in Sinhala Unicode. See [`docs/output_schema.md`](docs/output_schema.md) for full field documentation.

---

## Research Direction

This project is the foundation for a **Master of Computer Science thesis** on low-resource information extraction for historical Sinhala manuscripts.

**Core thesis claim**: A knowledge graph constructed from structured Volume I can serve as a grounding resource to enable entity and relation extraction from the unstructured prose of other traditional texts — without requiring large labeled corpora.

**Progressive roadmap**:

```
Phase 1 (current):   Vol I structured extraction → Seed KG (707 formulas)
Phase 2:             Vol II + III OCR → same pipeline → Enriched KG (~2,500+ formulas)
Phase 3:             Paragraph-structured traditional texts → KG-grounded NER
Phase 4:             General Sinhala traditional medicine NLP resource
```

See [`THESIS_PROPOSAL.md`](THESIS_PROPOSAL.md) for the full research proposal.

---

## Repository Structure

```
data/
  source/          Original PDF (Vol I)
  ocr/             GCV batch JSON outputs (Git LFS, 11 batches, pages 1–525)
  rows/            Stage 2: row-level compressed OCR
  structured/      Stage 3: final structured JSON entries

pipeline/
  extract_page.py        Extract single page from GCV batch
  shrink_ocr_v4.py       Compress page OCR to row format
  extract_pharma_v3.py   Structured extraction (stable)
  extract_pharma_v4.py   Structured extraction (current development)
  pipeline.py            Full pipeline runner

analysis/
  nlp_stats.py           NLP statistics report

pdf_pipeline/            Experimental: direct PDF extraction path
knowledge_graph/         Planned: KG construction (Phase 2)

docs/
  output_schema.md       Full field documentation
  architecture.md        Pipeline design decisions and thresholds
  THESIS_PROPOSAL.md     Full MCS thesis proposal
  pipeline_notes.txt     Data quality notes and known issues
```

---

## Running the Pipeline

No build system or package manager — standalone Python 3, no external dependencies.

```bash
# Run full pipeline (default: pages 444–453)
python pipeline/pipeline.py

# Specific page range
python pipeline/pipeline.py --start 151 --end 200

# Force overwrite existing outputs
python pipeline/pipeline.py --force

# Generate NLP statistics report
python analysis/nlp_stats.py

# Extract a single page
python pipeline/extract_page.py data/ocr/ocr_results_output-151-to-200.json 172
```

---

## Known Data Quality Issues

- ~17% of ingredient tokens are structural artefacts (punctuation, parenthesis leaks from GCV)
- 25% of formula names fail NFD Unicode normalization
- ZWJ characters appear in field keys and ~165 formula names
- `සංස්කරණය` (preparation) frequently collapsed because entries cite other formulas by number
- `සටහන` (notes) largely populated with "continued from previous page" markers

Full details in [`docs/pipeline_notes.txt`](docs/pipeline_notes.txt).

---

## License

Source text copyright: original pharmacopoeia publisher. Pipeline code: MIT.

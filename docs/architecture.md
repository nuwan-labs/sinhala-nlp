# Pipeline Architecture

## Overview

Three-stage pipeline: GCV batch JSON → row-level JSON → structured JSON.

```
Stage 1: extract_page.py       GCV batch → per-page JSON
Stage 2: shrink_ocr_v4.py      per-page JSON → row-level JSON
Stage 3: extract_pharma_v4.py  row-level JSON → structured entries
```

---

## Stage 2: Row Clustering Algorithm

GCV outputs a nested block → paragraph → word tree with bounding boxes. Stage 2 flattens this into visual rows.

1. Extract all words from the GCV tree
2. Normalize bounding box coordinates to (x, y) ∈ [0, 1] relative to page dimensions
3. Cluster words into rows: words whose y-values span ≤ **0.012** belong to the same row
4. Sort words left-to-right within each row
5. Drop page numbers: tokens at y > **0.88**, x ∈ [0.35, 0.65] that are purely numeric

**Output format per row**:
```json
{"y": 0.342, "w": [[0.12, "block_3", "para_1", "කලාඳුරු"], [0.18, "block_3", "para_1", "අල"]]}
```

---

## Stage 3: State Machine Extraction

Column x-position determines token role:

| x range | Role |
|---|---|
| x < 0.15 | Entry number (e.g. "44.") |
| 0.15 ≤ x < 0.25 | Sinhala field label |
| 0.25 ≤ x < 0.32 | Separator artefact (":", "-") |
| x ≥ 0.32 | Content |

**State sequence**:
```
ENTRY_HEADER → YOGAYA → SANSKARANAYA → PRAYOGA → ANUPANA → MATRAVA
```

Transitions are triggered by field labels matched against `LABEL_TO_STATE`. The machine handles cross-page entry continuation by merging orphaned partial entries from the previous page's `partial_tail`.

---

## Hard-coded Thresholds

| Value | File | Purpose |
|---|---|---|
| `0.012` | `shrink_ocr_v4.py` | Max y-spread for row clustering |
| `0.15` | `extract_pharma_v4.py` | Entry number / label boundary |
| `0.25` | `extract_pharma_v4.py` | Label / separator boundary |
| `0.32` | `extract_pharma_v4.py` | Separator / content boundary |
| `0.88` | `shrink_ocr_v4.py` | Page number y-threshold |

These were tuned empirically on Volume I. Volume II and III may require minor adjustment if the physical layout differs.

---

## Batch Registry

`pipeline.py` maps page ranges to GCV batch files:

| Batch file | Pages |
|---|---|
| `ocr_results_output-151-to-200.json` | 151–200 |
| `ocr_results_output-201-to-250.json` | 201–250 |
| `ocr_results_output-251-to-300.json` | 251–300 |
| `ocr_results_output-301-to-350.json` | 301–350 |
| `ocr_results_output-351-to-400.json` | 351–400 |
| `ocr_results_output-401-to-450.json` | 401–450 |
| `ocr_results_output-451-to-500.json` | 451–500 |

Additional batches covering pages 1–150 and 501–525 exist in `data/ocr/` but are not processed by the current pipeline (outside the pharmacopoeia formula section).

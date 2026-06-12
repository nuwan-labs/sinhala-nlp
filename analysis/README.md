# Proposal verification & hardening pipeline

Audits the MSc NLP proposal (`proposal_body.md`) against the data: reconciles every
numeric claim (Part A), re-runs RQ1–RQ3 with pre-registered decision rules and SESOIs,
adds a power/equivalence framework (Part E), and emits **one self-contained
`VERIFICATION_REPORT.html`** (Part F) with every figure embedded as base64.

## Run

```bash
pip install numpy scipy matplotlib scikit-learn tokenizers sentencepiece pymupdf regex
python -m analysis.fetch_baselines     # reachable baselines (news + gov order papers)
python -m analysis.run_all             # regenerates every number + figure
#   -> analysis/out/results.json
#   -> analysis/out/VERIFICATION_REPORT.html
```

`--fast` reduces bootstrap/seed counts for a quick pass. Global seed `20260611`;
environment pinned in `analysis/ENV.txt`.

### Hardening pass (closes the four self-adversarial loose ends)

```bash
apt-get install -y tesseract-ocr tesseract-ocr-sin   # second OCR engine for Task 2
python -m analysis.run_hardening
#   -> analysis/out/hardening_results.json
#   -> analysis/out/HARDENING_REPORT.html
```

Task 1 topic-controlled concentration; Task 2 real inter-engine CER + Heaps β
refit on verified errors only; Task 3 matcher-sensitivity of the open/closed
asymmetry on both sides; Task 4 feature ablation on the boundary-free RQ3 tagger.

## Epistemic contract

- Every number is tagged COMPUTED or ASSUMED; unreachable inputs are documented,
  never substituted (CC-100/OSCAR/Wikipedia were all HTTP 403 — only NLPC-UOM news
  and government order papers were reachable).
- `yogamalawa/` is never globbed (asserted in `common._structured_files`).
- Nulls are classified {effect present / equivalent-to-null / underpowered}; an
  underpowered interval is never reported as a null.
- Findings are headlined as the *pattern* across cells, not a favourable cell.

## Modules

| file | role |
|------|------|
| `common.py` | corpus/baseline/lexicon loading, segmentation units, seed |
| `stats.py` | Heaps β (block bootstrap), concentration, Rényi/Shannon, Kneser-Ney bpb, partial Spearman, equivalence |
| `lex.py` | gazetteer / ICD longest-match |
| `tok.py` | BPE / Unigram / WordPiece / grapheme-pair tokenisers |
| `partA_reconcile.py` | claim-by-claim reconciliation + erratum |
| `partB_rq1.py` | RQ1 (β matrix, concentration, constructions, semantics, OCR) |
| `partC_rq2.py` | RQ2 (intrinsic measures, KN bpb, 3-design predictive test, noise) |
| `partD_rq3.py` | RQ3 (label quality, boundary-free extraction, ICD, gold head-start) |
| `partE_power.py` | cross-cutting power & equivalence |
| `figures.py` / `report.py` / `run_all.py` | figures, HTML, entry point |

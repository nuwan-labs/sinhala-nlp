# KG Validation Report

Generated: 2026-05-24T06:27:06+00:00
Schema version: v1
Total nodes: 3642 · edges: 12163

## Summary

| Layer | Pass | Total | % |
|---|---:|---:|---:|
| 1 — anchor probe                          | 13 | 16 | 81.2 % |
| 1 — provenance present (nodes)            | 3642 | 3642 | 100.0 % |
| 1 — provenance present (edges)            | 12163 | 12163 | 100.0 % |
| 1 — ID format                             | 3642 | 3642 | 100.0 % |
| 1 — SHACL conformance                     | YES | — | violations: 0 |

## Layer 1 — Programmatic

### Anchor probe (81.2 %)

**Positive disease → TM2 assertions**:
- ✓ `jvara` → expected SP51, actual SP51
- ✓ `kāsa` → expected SL41, actual SL41
- ✓ `śvāsa` → expected SL42, actual SL42
- ✓ `kuṣṭha` → expected SN49, actual SN49
- ✓ `gulma` → expected SM3K, actual SM3K
- ✓ `arśas` → expected SM53, actual SM53
- ✓ `aśmarī` → expected SM8C, actual SM8C
- ✓ `meha` → expected SM8D, actual SM8D

**Positive plant → POWO assertions**:
- ✓ `viṣṇukrānti` (POWO: True, family: True, latin: True)
- ✗ `pippalī` (POWO: —, family: —, latin: —)
- ✗ `haritakī` (POWO: —, family: —, latin: —)
- ✗ `āmalakī` (POWO: —, family: —, latin: —)

**Negative vernacular → unresolved**:
- ✓ `තිප්පිලි` is_unresolved=True, canonical_iast=None
- ✓ `කොත්තමල්ලි` is_unresolved=True, canonical_iast=None
- ✓ `එන්සාල්` is_unresolved=True, canonical_iast=None
- ✓ `වැල්මී` is_unresolved=True, canonical_iast=None


### Edge domain/range integrity
{
  "edge_counts": {
    "CONTAINS": 11007,
    "DOSED_WITH": 215,
    "TREATS": 562,
    "IS_TYPE": 179,
    "CO_OCCURS": 200
  },
  "failures_by_edge_type": {},
  "samples": {}
}

### Cardinality sanity
- Formulations with no CONTAINS edges: 135 / 628  (78.5 % do have ingredients)
- Note: Yogamālāva formulas have no separately-extracted ingredient list, so 'no CONTAINS' is expected for verse-form formulations.

### SHACL validation
- Conforms: True
- Violations: 0
- Detailed report: `validate/shacl_violations.ttl`

## Layer 2 — Cross-source agreement

### POWO re-verification (botanical taxonomy)
{
  "sample_size": 30,
  "agree": 30,
  "disagree": 0,
  "errors": 0,
  "agreement_pct": 100.0,
  "samples_disagree": [],
  "samples_error": []
}

### ICD-11 TM2 re-verification (WHO authority)
{
  "sample_size": 20,
  "agree": 20,
  "disagree": 0,
  "errors": 0,
  "agreement_pct": 100.0,
  "samples_disagree": [],
  "samples_error": []
}

## Layer 3 — Expert spot-check (sample for human review)

Stratified random sample written to `validate/expert_sample.tsv`
(95 rows). Two annotators
score each row as correct / partial / wrong; compute Cohen's κ on
the 20-item double-coded subset. See
[`docs/validation_methodology.md`](../docs/validation_methodology.md).

## Layer 4 — LLM-judge

Not implemented in v1. See
[`docs/validation_methodology.md`](../docs/validation_methodology.md).

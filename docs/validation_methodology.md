# KG Validation Methodology

How we evaluate the quality of `knowledge_graph/kg.jsonld` (and the
upstream resolver + enricher outputs that feed it). The methodology is
synthesised from a structured literature survey across two axes:

- **Vertical** — within KG-quality / ontology-validation methods proper
  (Zaveri's framework, SHACL, ROBOT/OBO Foundry).
- **Lateral** — adjacent fields that influence the design (constrained
  generation, LLM-as-judge, inter-annotator agreement, ontology-
  mapping QA, biomedical KG benchmarks).

Implementation lives in `validate/validate_kg.py`. See
[`docs/references.md`](references.md) for full citations.

---

## 1. Literature synthesis

### 1.1 The canonical framework — Zaveri et al. (2016 / 2020)

Zaveri *et al.* introduced the dominant quality-assessment framework
for Linked Data, refining "quality" into **18 dimensions** in **4
categories**, with **69 distinct metrics**. The *intrinsic* trio is
universally cited as the backbone:

| Dimension | What it measures | How we test it |
| --- | --- | --- |
| **Accuracy / correctness** | Do triples reflect real-world facts? Syntactic + semantic + timeliness. | Anchor tests (Layer 1) + cross-source agreement with POWO and ICD-11 TM2 (Layer 2) + expert spot-check (Layer 3). |
| **Completeness** | Population and property completeness — what fraction of expected entities and required properties are present? | Per-type required-property coverage (Layer 1) + recall against the 707 Vol I formulas (built into the KG-build report). |
| **Consistency** | Free of contradictions w.r.t. representation and inference. | SHACL schema validation (Layer 1) + cross-field ID consistency (Layer 1). |

The remaining 15 dimensions (contextual: relevancy, understandability,
trust; representational: interoperability, conciseness) are useful
framing but not strictly required for our v1.

### 1.2 The formal mechanism — SHACL (W3C, 2017; pySHACL)

The **Shapes Constraint Language** is the W3C recommendation for
expressing integrity constraints on RDF graphs. Concrete benefits for
our use case:

- A **shape** is a SPARQL-like specification that a node or edge must
  satisfy (e.g., *"every `Formulation` has a `name_si` property of type
  xsd:string"*).
- Violations are first-class data: a SHACL validator returns an RDF
  *Validation Report* itemising every breach with line-level
  attribution.
- **pySHACL** is the canonical Python validator. It works directly on
  the `kg.ttl` we already emit, alongside a `shapes.ttl` we author
  from the schema in `docs/kg_schema.md`.

Recent 2025–2026 work that informs our design:

- **xpSHACL** (VLDB 2025 LLM+Graph workshop) — pairs SHACL with
  retrieval-augmented LLM explanations so violation reports are
  human-readable rather than opaque.
- **SHACLens** (Frontiers in Bioinformatics 2026) — visualisation
  workflow for SHACL violations in *biomedical* graphs at industry
  scale, addressing the "report too large to interpret" problem.

We adopt the **pySHACL** approach; the xpSHACL / SHACLens ideas inform
how we *present* violations (categorised, with an audit-trail link to
the source span).

### 1.3 Biomedical-ontology pipeline standard — ROBOT (OBO Foundry)

**ROBOT** (Jackson *et al.*, BMC Bioinformatics 2019) is the OBO
Foundry's command-line tool for ontology QA. It exposes two things
worth emulating directly:

- `robot report` — a pre-packaged set of SPARQL-based queries that
  return a tabular QA report (missing labels, duplicate IDs, dangling
  references, etc.).
- `robot query` — arbitrary SPARQL queries for ad-hoc validation.

The OBO Foundry **Dashboard** aggregates these reports across
ontologies into a single per-ontology QA scorecard. We adopt the same
**"report = categorised SPARQL queries"** pattern even though we don't
literally use ROBOT (it's Java; we stay in Python).

### 1.4 Cross-source agreement (and a calibrating finding)

The literature on biomedical ontology mapping quality (BioPortal, OXO,
OAEI) tells us two things:

1. Cross-source agreement is the **only available proxy for ground
   truth** at corpus scale — when an external authority resolves a
   term, we have an independent signal we can check our resolver
   against.
2. **Even gold-standard mapping tools achieve F1 ≈ 0.55–0.66** on
   BioPortal/UMLS benchmarks (AgreementMakerLight, FCA-Map, LogMap),
   and ~22 % of BioPortal's own mappings contain logical errors.

The second point is a critical context for reporting our numbers: **a
POWO coverage of 81 % and ICD-11 TM2 coverage of 88 % is competitive
with state-of-the-art ontology-mapping pipelines**, not embarrassing
relative to a hypothetical "100 %".

### 1.5 LLM-as-judge (2025 hybrid pattern)

Recent work (Lavrinovics 2025; Ghosh 2025; Jing 2025) on KG-grounded
fact-checking converges on a **hybrid pattern**: rubric-prompted LLM
judges combined with an NLI cross-encoder (HHEM-style) for cross-check.
Pure LLM judging hallucinates at 39–91 % on biomedical references,
which rules it out as a primary validator — but as a *triage* signal
for human review it adds value.

For our v1 we **design Layer 4 (LLM-judge) but do not implement it
yet** — Layers 1–2 already give us a defensible report; LLM-judge is
the right next iteration once we have a curated set of low-confidence
edges to triage.

### 1.6 Expert agreement — Cohen's κ and Krippendorff's α

For Layer 3 (human spot-check) the canonical metric is **Cohen's
kappa** for two annotators, **Krippendorff's alpha** for three or
more (or for missing data). The standard interpretation:

| κ range | Landis-Koch | Cohen | Our target |
| --- | --- | --- | --- |
| 0.81 – 1.00 | almost perfect | almost perfect | aspirational |
| 0.61 – 0.80 | substantial | substantial | **realistic target** |
| 0.41 – 0.60 | moderate | moderate | acceptable for tatsama-vs-tadbhava |

The 0.81 ceiling is contested in the recent IAA literature
(Krippendorff has argued the cutoffs are based on personal opinion).
We target **κ ≥ 0.75** for the v1 expert pilot, which is realistic for
the inherently fuzzy tatsama / tadbhava / vernacular boundary in
Sinhala medical terminology.

### 1.7 What is *not* in scope

For completeness, we explicitly do *not* attempt:

- **OWL DL consistency checking** — our schema isn't expressed in OWL.
  If a future v2 adds OWL class hierarchies, ROBOT's reasoning layer
  becomes the natural choice.
- **Embedding-based KG-quality assessment** (KG-BERT etc.) — useful
  for predicting missing triples; orthogonal to validating present
  ones.
- **Full crowdsource pipelines** (AMT-style annotation) — overkill at
  our corpus size.

---

## 2. Our four-layer framework

Translating the survey into our implementation:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Programmatic ("schema-mechanical")                            │
│  - SHACL shapes (pySHACL) against the schema in docs/kg_schema.md         │
│  - Anchor probe: hand-curated positive + negative term-mapping assertions │
│  - Provenance presence: every node + edge has source_doc, version, ts     │
│  - ID format: all internal IDs match `<type>:<key>` pattern               │
│  - Edge domain/range integrity (CONTAINS Formulation → Plant|Mineral)     │
│  - Cardinality sanity (e.g. every Formulation has ≥1 CONTAINS)           │
│  - Cross-field consistency (same Sinhala token resolves identically)      │
│                                                                          │
│  Status: AUTOMATED — runs in seconds, every commit can re-validate.      │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 2 — Cross-source agreement                                        │
│  - POWO re-verification: every Plant LSID looked up; agree on family?    │
│  - ICD-11 TM2 re-verification: every Disease code still exists in API?   │
│  - Wikidata cross-check (optional): Latin binomials resolve in Wikidata? │
│                                                                          │
│  Status: AUTOMATED — needs network access. Sub-minute end-to-end.        │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 3 — Expert spot-check                                             │
│  - Stratified random sample (100 nodes + 100 edges across types)         │
│  - Two annotators score correct / partial / wrong + free-text reason     │
│  - Compute Cohen's κ on a 20-item double-coded subset                    │
│  - Error taxonomy from the disagreements                                 │
│                                                                          │
│  Status: SCRIPT GENERATES THE SAMPLE; human work required to label.      │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 4 — LLM-judge (future)                                            │
│  - Per low-confidence edge: prompt an LLM with the edge + source span    │
│  - Rubric-grade: agree / disagree / unsure + rationale                   │
│  - Cross-check with NLI cross-encoder (HHEM-style) for triage            │
│                                                                          │
│  Status: DESIGNED, NOT IMPLEMENTED in v1.                                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. How to run

```bash
# After running knowledge_graph/build.py, run validation:
python validate/validate_kg.py
# Optional:
python validate/validate_kg.py --skip-cross-source   # offline only
python validate/validate_kg.py --sample-size 200     # bigger expert sample
```

Outputs (in `validate/`):

| File | What |
|---|---|
| `validation_report.md` | Human-readable report |
| `validation_report.json` | Machine-readable, suitable for CI integration |
| `expert_sample.tsv` | Stratified random sample for human review (Layer 3) |
| `shacl_violations.ttl` | Detailed SHACL violation report (RDF) |

---

## 4. What good looks like

A clean report should show, at a minimum:

| Check | Target |
| --- | --- |
| SHACL shape conformance | 100 % of nodes pass mandatory-property shapes |
| Anchor probe | 95 %+ correct on the hand-curated assertions |
| ID format check | 100 % |
| Provenance check | 100 % of nodes and edges have full provenance |
| POWO re-verification | ≥ 95 % of bound LSIDs still resolve |
| ICD-11 TM2 re-verification | ≥ 95 % of bound codes still resolve |
| (Layer 3, when done) | Cohen's κ ≥ 0.75 |

Failures are expected on real corpora — the value of the framework is
that they're *enumerated*, *categorised*, and *attributable* to the
specific upstream stage that introduced them.

---

## 5. References

The methodology above draws on (see [`references.md`](references.md)
for full citations and DOIs):

- **Zaveri** *et al.* (2016): Quality assessment of Linked Data — the
  18-dimension / 4-category framework.
- **W3C SHACL** (2017): the formal shape language.
- **pySHACL** (RDFLib): canonical Python validator.
- **ROBOT** (Jackson *et al.* 2019): biomedical ontology QA tool.
- **xpSHACL** (VLDB 2025): explainable SHACL with RAG/LLM.
- **SHACLens** (Frontiers in Bioinformatics 2026): SHACL violation
  visualisation for biomedical KGs.
- **AgreementMakerLight / FCA-Map / LogMap** (OAEI benchmarks 2021):
  state-of-the-art mapping F1 on BioPortal.
- **Lavrinovics**, **Ghosh**, **Jing** (2025): KG-grounded fact-
  checking with LLM hybrids.
- **Cohen** (1960), **Krippendorff** (2004): kappa / alpha for IAA.
- **Counting on Consensus** (arXiv 2025): modern IAA-metric
  selection for NLP.

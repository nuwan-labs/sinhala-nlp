<!--
  CONTRIBUTIONS CATALOGUE — UCSC MCS-3306 (Sinhala Traditional Medicine NLP)
  Draft v0.1, 2026-05-25. Author: Nuwan Medawaththa.

  Conventions:
    • Status:  [DONE]      shipped and measurable
               [IN-PROG]   actively under development
               [PLAN-A]    in scope, schedulable, no external blocker
               [PLAN-B]    in scope but expert-bound (annotator/clinician)
               [PLAN-C]    stretch / next-phase (post-MSc roadmap)
    • Weight:  ★★★ substantial CS contribution (own a paragraph in viva)
               ★★  moderate (worth naming, supporting role)
               ★   light (engineering deliverable)
    • Each row carries the citable positioning anchor it owns.
-->

# CS Contributions of the Project (entire scope)

> Catalogue of computer-science contributions for the MCS-3306 individual
> project, covering both work already shipped and the work explicitly
> committed for completion in the project window. Status markers separate
> what is measurable today from what is scheduled, expert-bound, or
> roadmap-stretch.

The project is structured around **six contribution categories**. Methodology and resource are the heaviest pillars; an empirical pillar lands when the planned NER ablation runs.

---

## A. Methodological / algorithmic contributions

| # | Contribution | Novelty / why this is a CS contribution | Status | Weight | Measured / target evidence |
|---|---|---|---|---|---|
| A1 | **Three-tier Sanskrit-bridge resolver** (Modules A→B→C, Tiers 1/2/3) | First published computational system mapping Sinhala-script tokens to Sanskrit MW lemmas; cascade design (router → direct lookup → dict-driven samāsa → parser worker → pratinidhi-table fallback) is novel. Closest international analogue is xMEN (cross-lingual MEN) but xMEN has no Indic coverage. | **DONE** | ★★★ | 81 % / 77 % / 67 % resolution on ingredients / names / prose; 1 932 word-records resolved across 3 lexicons |
| A2 | **Computational Mishra-Sinhala phonotactic classifier** (Module A) | First computational formalisation of the centuries-old descriptive *śuddha / miśra* alphabet distinction (Geiger 1938, Gair 1998). Encodes aspirate + sibilant + vocalic-r + word-initial-cluster signal as a deterministic Unicode regex over phonotactics. | **DONE** | ★★ | ~27 % of corpus types carry the signal; deterministic regex, no training |
| A3 | **Memory-isolated subprocess pattern for memory-pathological NLP libraries** | Generalisable engineering pattern: `RLIMIT_AS` cap + `SIGALRM` per-word timeout + worker recycling at N words, applied to the Sanskrit Heritage Engine wrapper. The pattern is reusable for any memory-leaky library. Reframable as "the workaround obviated by ByT5-Sanskrit in v2" — an *honest engineering-evolution* contribution. | **DONE** | ★★ | 21 workers ran clean, zero OOM kills, peak RAM under 1.65 GB |
| A4 | **Deterministic, schema-constrained, provenance-grounded prose extraction** (Blocks A–F) | Cascaded-FST (FASTUS-lineage) + Aho-Corasick gazetteer longest-match + field-state-driven relation emission + SHACL reject-at-emission + char-span verbatim binding. Implements the three guarantees the project owns: deterministic / complete / exact. Positioned against the 2025 schema-constrained-extraction SOTA (ODKE+, "Chaos to Clarity") with the explicit determinism contrast they don't offer. | **DONE** | ★★★ | demo 6 triples / 0 unsupported / determinism PASS / exactness 100 %; real entry 3 → 43 triples; batch 200 entries → 2 333 triples / 17 unsupported |
| A5 | **Multi-system unit-conversion registry with per-system disambiguation** | Three-layer ontology design (symbols / systems / ladders) where the same surface (`පල`) resolves to different gram values in different systems (60 g Sri Lankan, 48 g Yauna). The `to_grams(text, system)` parser handles both word orders, fractions, multi-unit combos. QUDT-pattern compatible. | **DONE** | ★★ | 43 symbols × 6 systems; 48.8 % of CONTAINS edges grams-populated (up from 35.9 % pre-registry) |
| A6 | **Materia-medica-driven node-classification override** | Domain-knowledge-as-classifier: the pharmacopoeia's own categorised raw-materials list (pp. 444–453) is used to *override* the resolver's Plant/Mineral assignment in the KG, with measurable reclassifications. | **DONE** | ★★ | 3 851 surface forms confirmed; 230 reclassified (112 → AnimalOrigin, 97 → Mineral, 21 → Plant) |
| A7 | **Iteration loop with Module-A-driven NIL triage** | Concrete instantiation of "extract → audit → patch → re-extract": gap_report.py classifies uncovered tokens into resolver-vs-gazetteer-vs-ignore candidates, ranked by frequency. Closes the loop the prose extractor needs to self-improve. | **DONE** | ★ | 200-entry batch yields a ranked work-item list; one iteration turn already executed (stopword-set expansion) |
| A8 | **Pluggable-oracle interface** | Block C exposes a `second_oracle` parameter so a future CRF / GLiNER-multi / SapBERT-multi can be added without disturbing the deterministic primary path. Float-non-determinism never reaches the canonical KG. | **DONE** (interface) | ★ | interface in place; no oracle wired yet |
| A9 | **R5 — preparation-verb-chain extractor** | Extract the preparation method as a sequence of typed verb actions (boil → strain → cook with oil → cool), enabling a `PREPARED_BY` step graph. Specifically targeted at the rich preparation prose Block F surfaced as the biggest completeness gap. | **PLAN-A** | ★★ | targets >25 % completeness lift on entries with non-empty `සංස්කරණය` field |
| A10 | **Module C extension** — full tadbhava lexicon beyond the pratinidhi 143 | Wire Sorata Thero / Geiger etymological dictionaries (digitised at DSAL) into the resolver as a Tier-1c lookup for tadbhava terms outside the substitute glossary. | **PLAN-B** | ★★ | expert-bound on dictionary alignment; target +5 pp resolver coverage |
| A11 | **Module D — vernacular / colonial-loanword handler** | Sinhala-only ingredient surfaces with no Sanskrit ancestry (Portuguese / Dutch / English / Tamil borrowings — *ankenda*, *anōda*, *ensāl*) get classified and bound to POWO via a botanist's curation pass. | **PLAN-B** | ★★ | expert-bound; target ≥50 vernacular surface forms resolved |
| A12 | **R4-Stage B clinical-condition tagger** | A dosha / clinical-action tagger that lifts indication prose into structured `HAS_PROPERTY` + `TREATS` edges with finer granularity than the current TM2 mapping. | **PLAN-B** | ★★ | needs Ayurvedic-physician sign-off |

---

## B. Resource contributions (first-of-kind data)

| # | Contribution | Why it's a contribution | Status | Weight |
|---|---|---|---|---|
| B1 | **First machine-readable Sri Lankan Ayurvedic Pharmacopoeia** | No prior machine-readable form exists (lit survey §3.5 confirmed against TKDL, GRAYU, IMPPAT, all global TCM DBs). Vol I structured-JSON corpus: 852 formulas, 11 007 ingredient cells, 62 562 tokens, 7 100 vocab types. | **DONE** (Vol I) | ★★★ |
| B2 | **First KG of Sri Lankan traditional medicine** | 4 089 nodes / 12 754 edges, bound to ICD-11 TM2 + POWO + ChEBI + Plant Ontology. Citable as a resource paper (LREC / JOHD). | **DONE** | ★★★ |
| B3 | **Closed-vocabulary lexicons** mined from the source itself | `materia_medica.json` (771 substances), `pratinidhi_lookup.json` (143 Sanskrit↔Sinhala paraphrase pairs), `mahakashaya_groups.json` (50 ganas, 436 substance mentions), `unit_equivalences.json` (43 symbols × 6 systems), `gazetteer.json` (1 108 surfaces). Reusable for any future Sri Lankan Ayurveda NLP. | **DONE** | ★★ |
| B4 | **Sinhala↔Sanskrit ingredient lexicon** (`ingredients_lexicon.json`) | 983 ingredient terms with MW lemmas + glosses + resolution method. First such mapping at scale. | **DONE** | ★★ |
| B5 | **Yogamālāva structured release** | Verse-form 1908 formulary digitised end-to-end: 145 entries, 98.5 % per-token coverage of source OCR. Independent register from Vol I, supports cross-corpus validation. | **DONE** | ★★ |
| B6 | **Volume II and Volume III ingestion** | Same pipeline applies; physical copies in hand. Doubles or triples the corpus size and yields multi-volume cross-validation. | **PLAN-A** | ★★ |
| B7 | **PlantPart lexicon + `USES_PART` edges** | Gap-report-driven addition (root / bark / shoot / tuber / seed — 290+ occurrences in the corpus). Activates the schema's existing `PlantPart` node type and `USES_PART` edge. | **PLAN-A** | ★ |
| B8 | **TEI scholarly-edition export + JOHD data paper** | One-shot TEI export of the structured corpus (header + `<div type="formula">` + `<rs ref="…">`) + CTS-style canonical URN scheme. Publishable in the DH track in parallel with NLP venues. | **PLAN-A** | ★★ |
| B9 | **Curated training set for the second-oracle CRF** | Blind double-annotated gold subset (~100–200 spans) per the v0.4 lit-survey methodology, with IAA reported as Gwet's AC1 + bootstrap CIs. | **PLAN-B** (annotator-bound) | ★★ |

---

## C. Knowledge-representation contributions

| # | Contribution | Status | Weight | Notes |
|---|---|---|---|---|
| C1 | **KG schema v1.1** — 11 node types, 13 edge types, provenance-per-fact, schema-constrained extraction principle as the design-time contract (§9 of `docs/kg_schema.md`). | **DONE** | ★★ | Synthesised from comparable initiatives (GRAYU, AyurKOSH, HerbKG, Āyurjñānam); `AnimalOrigin` is a v1.1 addition for the *jāntava* substance class. |
| C2 | **Four interoperable serialisations**: Neo4j Cypher (canonical), JSON-LD (publish), RDF/Turtle (semantic-web), JSONL (streaming). | **DONE** | ★ | Standard practice but cleanly executed. |
| C3 | **External-authority bindings** — Disease → ICD-11 TM2, Plant → POWO IPNI LSID. | **DONE** | ★★ | 49/56 (88 %) and 69/85 (81 %) resolved. |
| C4 | **ChEBI + Plant Ontology bindings** for `Phytochemical` and `PlantPart` nodes. | **PLAN-A** | ★ | Low-effort `skos:exactMatch` additions; lit survey v0.2 recommendation. |
| C5 | **`SafetyFlag` node class + heavy-metal-bearing flag + GRAYU disclaimer** — the ethical minimum for a TM KG containing rasa-śāstra preparations. | **PLAN-A** | ★ | Saper *et al.* 2004/2008 + Sikder 2024 grounded. |
| C6 | **Schema v1.2** — `USES_PART` edges, `CONSISTS_OF Plant→Phytochemical`, `HAS_SYMPTOM`, `RELIEVES`, `VARIANT_OF`. | **PLAN-A** | ★ | Already defined in v1.0 schema but not yet populated; PlantPart lexicon (B7) is the unblock. |
| C7 | **Schema v2** — `Provenance` as RDF-star annotations on every triple, replacing the bespoke `char_span` field. Adopts the W3C standard for triple-level provenance. | **PLAN-A** | ★ | Lit-survey v0.2 recommendation; cleanly defensible. |
| C8 | **Substitute relation (`SUBSTITUTES_FOR`) populated from `pratinidhi` rhs_si** — abhāva-pratinidhi-dravya. | **DONE** | ★ | 155 edges. |

---

## D. Empirical / evaluation contributions

| # | Contribution | Status | Weight | Measured / target |
|---|---|---|---|---|
| D1 | **Three-guarantees verification framework** — deterministic / complete / exact — with implemented audit gates and measured numbers per document. | **DONE** | ★★ | demo PASS / 100 % / 79 %; entry 3 PASS / 100 % / 43 %; batch 2 333 / 0 unsupported / 17 schema-rejected |
| D2 | **Four-layer KG validator** — Layer 1 (SHACL + anchors + provenance + ID + edge domain/range + cardinality), Layer 2 (POWO + ICD-11 re-verify), Layer 3 (expert spot-check sample), Layer 4 (LLM-judge as triage). | **DONE** (L1+L2); **PLAN-B** (L3); **PLAN-A** (L4 as triage) | ★★ | SHACL conforms, POWO 30/30, ICD-11 20/20, anchors 13/16 |
| D3 | **KG-grounded NER ablation** — the empirical pillar in the proposal. Three-arm comparison: gazetteer baseline / feature-rich CRF on distant-supervised data / KG-augmented CRF. Report F1 + bootstrap CIs. | **PLAN-A** | ★★★ | The single biggest weight increment available with remaining time; sklearn-crfsuite installed; 11 007-pair training set exists |
| D4 | **Unlabelled-KG quality reporting** — stratified-sample triple precision with Bayesian credible interval (Marchesin & Silvello 2025) + capture-recapture recall estimator (Lincoln–Petersen) using v3-vs-v4 extractor overlap. | **PLAN-A** | ★★ | Methodology in lit-survey §4.9; needs ~100 expert judgements + a small re-extraction |
| D5 | **Inter-annotator agreement on the L3 sample** with Gwet's AC1 + bootstrap CIs (NOT Cohen's κ — corrected per lit-survey v0.3). | **PLAN-B** (annotator-bound) | ★★ | sample TSV written; expert review pending |
| D6 | **Provenance-per-fact KG with verbatim source-span binding** — every triple's `char_span` slices back to its surface exactly. Stronger than typical `extractor_version`-only provenance in Wikidata/DBpedia. | **DONE** | ★★ | exactness 100 % across measured runs |
| D7 | **Comparison against an LLM-extraction baseline** — SinLlama or GPT-4 few-shot on the same prose, reported on the same gold sample, to quantify the recall gap vs the determinism gain. | **PLAN-A** | ★★ | The honest concession from lit-survey §6.2; needed to position the determinism contribution against the LLM SOTA |

---

## E. Systems / engineering contributions

| # | Contribution | Status | Weight |
|---|---|---|---|
| E1 | **Schema-constrained extraction pipeline with reject-at-emission** — `SCHEMA_EDGES` in `extract_prose.py` mirrors v1.1 edge domain/range; every candidate triple validated before emission; mismatches go to `unsupported` log. | **DONE** | ★★ |
| E2 | **Two OCR routes**: Google Cloud Vision (Stage 0) + `pdf_pipeline/` embedded-PDF-text extraction for legacy-font pages. | **DONE** | ★ |
| E3 | **Surya OCR pilot** vs GCV — arXiv 2507.18264 reports ~3× WER advantage on synthetic Sinhala. Must be validated on real pharmacopoeia scans before committing. | **PLAN-A** | ★ |
| E4 | **`sanskrit_parser` → ByT5-Sanskrit swap** — eliminates the memory-isolated subprocess hack; ByT5-Sanskrit beats Heritage Engine on every published benchmark; deterministic under greedy decode. | **PLAN-A** | ★ |
| E5 | **Reproducibility infrastructure** — Apptainer / Docker image + Makefile + pinned `requirements.txt` + ACL-Reproducibility-Checklist response + SHA-256 manifest of `*_structured.json` outputs. | **PLAN-A** | ★ |
| E6 | **Sinhala neural backbone for the second oracle** — LoRA-adapt SinLlama on the Ayurvedic extractions + SiDiaC medical-genre slice + SiPaKosa replay. Strictly a validation oracle; never touches the canonical KG. | **PLAN-C** | ★★ |
| E7 | **Pluggable-oracle interface in Block C** (cross-listed from A8). | **DONE** | ★ |
| E8 | **Multi-volume corpus orchestration** — `pipeline.py` extended for Vols II/III. | **PLAN-A** | ★ |

---

## F. Scholarly / framing contributions

| # | Contribution | Status | Weight |
|---|---|---|---|
| F1 | **Three iterative literature surveys + primary-source verification pass** — `docs/literature_survey.md` v0.4 (~140 Harvard citations, six iterations, provenance markers F/S/?), `docs/sota_survey.md`, `docs/sinhala_nlp_landscape.md`. | **DONE** | ★★★ |
| F2 | **Formal-language framing of the architecture** — explicit positioning of the tabular Stage-3 state machine as a cascaded FST (FASTUS, Hobbs 1997) / wrapper (Kushmerick 2000), and the prose extractor as a CFG/PEG grammar that is the *non-neural limit* of grammar-constrained decoding (Outlines, XGrammar). | **DONE** | ★★ |
| F3 | **Borrowing-under-diglossia linguistic framing** — Sinhala's tatsama / tadbhava / deśya are integrated borrowings under classical diglossia (Poplack 1980 integration criterion), NOT code-switching; computationally framed as word-level language identification. | **DONE** | ★★ |
| F4 | **Responsible-release framework reconciling FAIR with CARE** — TK Labels + Nagoya-style ABS for the content layer; FAIR-for-metadata / CARE-for-governance; explicit Sri Lankan legal-vacuum naming. | **PLAN-A** | ★★ |
| F5 | **Annotation methodology**: gazetteer pre-annotation + LLM silver + human verification with blind double-annotated gold subset for anchoring-bias mitigation; confidence routing + self-consistency for stage-2 QC. | **PLAN-A** | ★★ |
| F6 | **MCS-3306 proposal draft** — 11 sections covering background, methodology, evaluation, ethics, references. | **DONE** | ★ |
| F7 | **Documented "first-of-kind" gaps in Sri Lankan / Ayurvedic NLP** — five gaps independently confirmed in the lit survey: no medical Sinhala NLP, no Sri Lankan TM KG, no Sinhala→Sanskrit lexical bridge, no machine-readable pharmacopoeia, no Sinhala-Sanskrit aligned sense lexicon at scale. | **DONE** | ★★ |
| F8 | **CARE-Principles-informed governance proposal** for the resource release — Local Contexts TK Labels + non-commercial / prior-informed-consent default for the formula-composition content layer, with the schema/code/structure opened under CC-BY-SA. | **PLAN-A** | ★ |

---

## Roll-up — contribution shape

| Category | DONE | PLAN-A | PLAN-B | PLAN-C |
|---|---:|---:|---:|---:|
| A. Methodological / algorithmic | 8 | 1 | 3 | 0 |
| B. Resource | 5 | 3 | 1 | 0 |
| C. Knowledge representation | 4 | 4 | 0 | 0 |
| D. Empirical / evaluation | 3 | 3 | 1 | 0 |
| E. Systems / engineering | 3 | 4 | 0 | 1 |
| F. Scholarly / framing | 5 | 3 | 0 | 0 |
| **Total** | **28** | **18** | **5** | **1** |

**Substantial (★★★) contributions** owned by the project:
- A1  Three-tier Sanskrit-bridge resolver
- A4  Deterministic schema-constrained prose extraction
- B1  First machine-readable Sri Lankan Ayurvedic Pharmacopoeia
- B2  First KG of Sri Lankan traditional medicine
- D3  KG-grounded NER ablation (PLAN-A)
- F1  Three iterative literature surveys + verification

**Critical-path remaining work** (PLAN-A items that materially change the contribution shape):

1. **D3 — the NER ablation** (the empirical pillar). Without it the project is methodology + resource heavy but empirically light. With it, the project lands all four contribution pillars of the proposal. ~2–3 days of work; data and tooling already in place.
2. **A9 — R5 preparation-verb-chain extractor**. The single biggest completeness lever Block F surfaced. Lifts the prose extractor from 43 % to a target >65 % on entries with non-empty `සංස්කරණය`.
3. **D4 — sampled-precision + capture-recapture recall**. The honest, statistically-defensible quality numbers for the KG; ~100 expert judgements + a small re-extraction.
4. **B6 — Vol II / Vol III ingestion**. Multiplies the corpus and yields the cross-volume validation the proposal's evaluation section needs.

**External-blocked work** (PLAN-B):
A10–A12 (full tadbhava / vernacular / clinical-action), B9 (gold-set annotation), D5 (IAA): all annotator/clinician-bound. The proposal frames these as *partial coverage by MSc end + clear future-work bridges*.

---

## How to position the contribution for the viva

The defensible, heavy-MSc framing is **methodology + resource + empirical + scholarly**, in that order of weight:

> *"This project contributes (i) a deterministic, schema-constrained,
> provenance-grounded extraction pipeline for Sinhala traditional-medicine
> prose, including the first Sinhala→Sanskrit lexical bridge of its kind;
> (ii) the first machine-readable Sri Lankan Ayurvedic Pharmacopoeia and
> the first knowledge graph of traditional Sri Lankan medicine, bound to
> ICD-11 TM2, POWO and ChEBI; (iii) a controlled empirical measurement
> showing that knowledge-graph-grounded features improve named-entity
> extraction on Sinhala Ayurvedic text over a gazetteer baseline and a
> distant-supervised CRF; and (iv) a cross-disciplinary literature review
> with a primary-source verification pass, positioning the work against
> the 2025 schema-constrained-extraction SOTA (ODKE+, Chaos-to-Clarity)
> on the explicit basis of byte-identical determinism and verbatim
> source-span binding — guarantees the SOTA does not offer."*

# Research Proposal Outline

**Project Title:** A Deterministic Knowledge-Graph Extraction System for Sinhala Traditional Medicine Literature Using a Sanskrit-Bridge Approach

**Candidate:** Nuwan Medawaththa
**Programme:** Master of Computer Science — Individual Project (MCS 3306)
**Institution:** University of Colombo School of Computing (UCSC)
**Date:** May 2026
**Duration:** 12 months

---

## 1. Research Problem

Sri Lankan traditional medicine is documented across thousands of books and ola-leaf manuscripts spanning several centuries of clinical practice. These texts record herbal formulas, preparation methods, therapeutic indications, dosages and adjuvants in Sinhala script — often intermixed with Sanskrit-derived terminology inherited from the classical Ayurvedic tradition. Despite this wealth of recorded knowledge, not a single machine-readable, structured or computationally queryable form of any Sri Lankan traditional-medicine text has been published to date (de Silva, 2026; Joshi *et al.*, 2026; Vivek-Ananth *et al.*, 2023). The Indian Ayurvedic ecosystem has produced substantial computational resources — TKDL, IMPPAT, GRAYU, AyurKOSH — but each draws exclusively upon Indian sources. Chinese network-pharmacology databases address an entirely different medical tradition. Sri Lanka remains unrepresented.

This project sets out to build a reusable, deterministic extraction system that can take arbitrary free-style Sinhala traditional-medicine text as input and produce a schema-constrained, provenance-grounded knowledge graph as output. The system is trained on the *Ayurvedic Pharmacopoeia, Volume I* (525 pages; published by the Department of Ayurveda, Government of Sri Lanka), which serves as a structured training corpus: its tabular formula section yields silver-labelled entity–relation pairs through spatial layout, its reference tables supply closed-vocabulary lexicons, and its terminology seeds a cross-lingual Sinhala-to-Sanskrit resolver. Once calibrated, the system is intended to generalise — without retraining — to unseen traditional-medicine prose from other books in the same tradition.

Several factors make this problem particularly challenging. Sinhala is classified among the world's most under-resourced languages for natural language processing (Joshi *et al.*, 2020) and is excluded from the AI4Bharat Indic-NLP ecosystem (Gala *et al.*, 2023). No medical Sinhala NER corpus or model exists. The Universal Dependencies treebank for Sinhala contains only 100 sentences (Liyanage and Sarveswaran, 2023). The source text employs a dense mixture of native Sinhala vocabulary and a Sanskrit-derived (*tatsama*) layer for which no computational classifier has been published. These constraints rule out standard supervised approaches and motivate the proposed rule-based, closed-vocabulary-first architecture.

The project addresses five coupled sub-problems: (i) structural recovery of silver training data from a tabular printed source; (ii) cross-lingual lexical bridging from Sinhala to Sanskrit NLP resources; (iii) schema-constrained information extraction from free-style prose under hard determinism requirements; (iv) knowledge-graph construction with triple-level provenance and external-authority binding; and (v) empirical validation that the system generalises to unseen documents and that its knowledge graph improves downstream entity recognition.

The work is positioned against the 2025 schema-constrained-extraction literature (Wang *et al.*, 2025; Wang *et al.*, 2026; Zhong *et al.*, 2025). Where those systems prioritise recall through LLM-driven generation, this project prioritises two guarantees they do not offer: byte-identical determinism and verbatim source-span binding on every emitted triple — properties essential in a low-resource biomedical domain where reproducibility and auditability take precedence over coverage.

---

## 2. Literature Review

### 2.1 Sinhala as a target language for NLP

Sinhala (ISO 639-3 `sin`) is an Insular Indo-Aryan language with approximately 17 million speakers, whose sole living close relative is Dhivehi (Gair, 1998; Chandralal, 2010). Joshi *et al.* (2020) classify it in their lowest resource tier alongside Nepali and Igbo. The Universal Dependencies treebank covers only 100 sentences and 880 tokens (Liyanage and Sarveswaran, 2023), effectively precluding supervised dependency parsing. Sinhala is excluded from the AI4Bharat ecosystem: IndicBERT, IndicTrans2, MuRIL and the BPCC parallel corpus all cover only the 22 constitutionally scheduled Indian languages (Gala *et al.*, 2023; Khanuja *et al.*, 2021).

Within the Sinhala-specific landscape, the canonical survey is de Silva (2019, rev. 2026). Pre-trained models include SinBERT (Dhananjaya *et al.*, 2022) and SinLlama (Aravinda *et al.*, 2025), though both are trained on news and web data. No medical or Ayurvedic Sinhala NLP work has been published. The SinhalaMMLU benchmark (Pramodya *et al.*, 2025) demonstrates that frontier language models achieve only 67% on Sinhala cultural domains, motivating caution against reliance on LLM-only extraction in the Ayurvedic register.

The Sinhala script is an abugida (Unicode U+0D80–U+0DFF) requiring virama plus ZWJ for conjunct formation in a way that is mandatory and rendering-affecting (Ishida, 2024). The orthographic distinction between *śuddha* (native) and *miśra* (mixed) Sinhala — the latter preserving Sanskrit aspirates, sibilants and vocalic-r — provides the operational signal for the proposed cross-lingual resolver.

### 2.2 Cross-lingual lexical bridging and Sanskrit NLP

ByT5-Sanskrit (Nehrdich *et al.*, 2024) represents the current state of the art for Sanskrit sandhi-splitting and lemmatisation. The Monier-Williams dictionary (1899), accessible via the Cologne Digital Sanskrit Dictionaries, provides approximately 160,000 headwords. Aksharamukha (Rajan, 2024) enables lossless transliteration between Sinhala and IAST, bridging Sinhala script to the entire Sanskrit NLP tool chain.

No published system connects Sinhala to Sanskrit lexical resources computationally. The closest analogue is xMEN (Borchert *et al.*, 2023), a cross-lingual medical-entity-normalisation toolkit, but its evaluation covers no Indic language. Cross-lingual SapBERT (Liu *et al.*, 2021) shares this limitation. This gap — a missing Sinhala-to-Sanskrit computational bridge — is central to the present proposal.

### 2.3 Schema-constrained information extraction

The prevailing paradigm in biomedical KG construction defines a target schema as a hard constraint prior to extraction (Wang *et al.*, 2025; Wang *et al.*, 2026; Zhong *et al.*, 2025). ODKE+ (Wang *et al.*, 2025) reports 98.8% precision over 19 million facts under ontology-snippet constraints. GLiNER (Zaratiana *et al.*, 2024) provides zero-shot schema-driven entity extraction but with limited Sinhala coverage. Snorkel-style weak supervision (Ratner *et al.*, 2017) offers a formal framework for combining multiple labelling functions.

Comparable traditional-medicine knowledge graphs include GRAYU (Joshi *et al.*, 2026; 157,000 nodes), HerbKG (Lin *et al.*, 2022; 53,000 relations), AyurKOSH (Mirasdar *et al.*, 2026), and Āyurjñānam (Terdalkar, 2023). WHO ICD-11 TM2, released February 2025, provides 529 codes specifically for Ayurveda, Siddha and Unani. No analogous knowledge graph exists for Sri Lankan traditional medicine.

### 2.4 Evaluation without a gold standard

Sample-based precision estimation with Bayesian credible intervals (Gao *et al.*, 2019; Marchesin and Silvello, 2025) and capture-recapture recall estimation constitute the applicable evaluation paradigm for unlabelled KGs. LLM-as-judge achieves 88% precision but only 44% recall (Adam and Kliegr, 2025), suitable as triage but not as validation. Gwet's AC1 (Gwet, 2008; Sarsa *et al.*, 2026) is preferred over Cohen's kappa for inter-annotator agreement under skewed distributions.

### 2.5 Research gap

Five gaps emerge from the literature: (i) no machine-readable Sri Lankan traditional-medicine resource or knowledge graph exists; (ii) no computational Sinhala-to-Sanskrit lexical bridge has been published; (iii) no medical Sinhala NER corpus or model is available; (iv) the schema-constrained-extraction state of the art does not guarantee byte-identical determinism or verbatim source-span binding; and (v) the FAIR-versus-CARE tension for traditional-knowledge release remains unresolved domestically. This project addresses all five through one coherent extraction system.

---

## 3. Research Questions

**RQ1.** Can a deterministic cascade-based resolver bridge Sinhala-script tokens to Sanskrit Monier-Williams lemmas using orthographic signal and corpus-internal glossaries, and what coverage does it achieve on traditional-medicine terminology? (Nehrdich *et al.*, 2024; Borchert *et al.*, 2023; Gair, 1998)

**RQ2.** Can a schema-constrained extraction system trained on a single structured pharmacopoeia satisfy three guarantees — byte-identical determinism, content-token completeness, and verbatim source-span binding — on unseen free-style traditional-medicine prose? (Wang *et al.*, 2025; Wang *et al.*, 2026; Hobbs *et al.*, 1997)

**RQ3.** Does the system transfer with measurable precision and recall to structurally and temporally distinct traditional-medicine documents without retraining? (Shang *et al.*, 2018; Ratner *et al.*, 2017; Joshi *et al.*, 2020)

**RQ4.** Does augmenting named-entity recognition with knowledge-graph-derived features improve F1 over gazetteer-only and distant-supervised CRF baselines on Ayurvedic entities? (Dhananjaya *et al.*, 2022; Ranathunga *et al.*, 2024; Kartchner *et al.*, 2024)

**RQ5.** How should a traditional-medicine knowledge graph reconcile FAIR Principles for metadata with CARE Principles for formula-composition content in a jurisdiction lacking enacted traditional-knowledge legislation? (Carroll *et al.*, 2021; Wilkinson *et al.*, 2016; WIPO, 2024)

---

## 4. Research Objectives

**Phase I — System construction** (Pharmacopoeia as training corpus):

**O1.** Structure the training corpus by processing Pharmacopoeia Vol I through OCR and a three-stage extraction pipeline, producing approximately 850 structured formula entries as silver training data.

**O2.** Construct a reusable Sinhala-to-Sanskrit cascade resolver comprising a phonotactic classifier, transliteration-based dictionary lookup, compound-word segmentation, sandhi analysis, and a substitute-glossary fallback — designed to operate on any Sinhala text containing Sanskrit-derived terminology.

**O3.** Extract closed-vocabulary lexicons from the Pharmacopoeia's reference tables (categorised raw materials, substitute glossary, therapeutic-action groups, unit-conversion systems) to form the system's knowledge base.

**O4.** Implement the extraction system: a gazetteer-based span labeller, sentence segmenter, schema-constrained relation emitter with provenance binding, a three-guarantees audit framework, and an iteration-loop mechanism for gap identification. Design a knowledge-graph schema with external-authority bindings to ICD-11 TM2, POWO and ChEBI.

**Phase II — Validation:**

**O5.** Evaluate system generalisation on unseen documents: withheld Vol I formulas, samples from other traditional-medicine books, and texts of varying register and period.

**O6.** Conduct a three-arm NER ablation to quantify the knowledge graph's downstream utility.

**O7.** Release the system and resources under responsible FAIR-plus-CARE governance.

---

## 5. Scope of the Study

**In scope.** Construction of the extraction system using Pharmacopoeia Vol I as training corpus. Validation on held-out Vol I data and on separate traditional-medicine texts (including verse-form and prose-form books from the same tradition). The knowledge graph is bound to ICD-11 TM2, POWO and ChEBI. The NER ablation uses approximately 11,000 structured ingredient mentions as distant-supervision signal.

**Out of scope.** Exhaustive digitisation of additional volumes beyond evaluation samples; complete tadbhava etymological lexicons requiring external lexicographic expertise; colonial-loanword handling requiring botanical curation; cross-formula link-prediction; clinical validation or pharmacovigilance modelling; and large-scale manually-annotated NER corpora. Each exclusion indicates a future-work pathway.

---

## 6. Research Methodology

The methodology adopts a rule-based, closed-vocabulary-first architecture. This choice is motivated by two considerations. First, empirical evidence shows that frontier language models perform poorly on culturally-rich Sinhala domains (Pramodya *et al.*, 2025; Sonavane *et al.*, 2024), making LLM-only extraction unreliable for this register. Second, the requirements of determinism, auditability and zero hallucination are better served by a system whose behaviour is fully determined by its inputs and rules than by one that relies on stochastic generation.

The key insight underlying the methodology is that the Pharmacopoeia functions as a structured training corpus. Its tabular layout — where column position encodes semantic role — provides silver-labelled entity–relation pairs that the system absorbs as lexicons, resolver calibration data and extraction patterns. Once these components are in place, the system operates on any prose input from the same medical tradition.

The work proceeds in two phases.

**Phase I** constructs four categories of component from the Pharmacopoeia: (i) a cross-lingual resolver that exploits the phonotactic distinction between native and mixed Sinhala to bridge tokens to Sanskrit lexical resources; (ii) closed-vocabulary lexicons covering the tradition's substance vocabulary, substitute terms, therapeutic-action classifications and measurement units; (iii) a knowledge-graph schema with external-authority bindings and a multi-layer validation framework; and (iv) a prose-extraction engine employing gazetteer-based span labelling, schema-constrained relation emission, and char-span provenance binding. The extraction engine is formally a cascaded finite-state transducer (Hobbs *et al.*, 1997) — the non-neural limit of grammar-constrained decoding (Willard and Louf, 2023). An iteration-loop mechanism identifies uncovered tokens and routes them for systematic lexicon expansion.

**Phase II** validates the system on documents it has never encountered. A three-arm NER ablation quantifies the downstream value of the constructed knowledge graph. Evaluation employs sample-based precision with credible intervals (Marchesin and Silvello, 2025), capture-recapture recall estimation, expert spot-checking with Gwet's AC1, and LLM-judge triage. Determinism is enforced by construction through stable sort ordering and fixed random seeds, verified via SHA-256 output manifests.

The system exposes a pluggable interface for a future learned component (CRF, neural tagger), permitting extension without compromising the deterministic primary path.

---

## 7. Novelty and Expected Research Contributions

The project contributes along four axes — methodology, resource, empirical validation and scholarly framing — unified by the principle that the system is trained on a single pharmacopoeia yet validated on unseen literature.

**N1. First computational Sinhala-to-Sanskrit lexical bridge.** No system mapping Sinhala-script tokens to Sanskrit lexical resources has been published. The proposed cascade resolver — phonotactic router, transliteration-based lookup, compound segmentation, sandhi analysis, substitute-glossary fallback — fills this gap and is designed as a reusable component for any Sinhala text containing Sanskrit-derived terminology.

**N2. Deterministic, schema-constrained extraction with three verifiable guarantees.** The system guarantees byte-identical re-runs, content-token completeness with logged gaps, and verbatim source-span binding on every triple. This is positioned against the 2025 extraction literature (ODKE+, *Chaos to Clarity*), which does not offer byte-identical determinism as a headline property.

**N3. First machine-readable Sri Lankan traditional-medicine knowledge graph.** No computational knowledge graph of Sri Lankan traditional medicine exists. The proposed KG is interoperable with the international ecosystem through ICD-11 TM2, POWO and ChEBI bindings.

**N4. Cross-document generalisation without retraining.** The demonstration that a rule-based system calibrated on one volume transfers to distinct documents establishes it as a general-purpose tool rather than a source-specific extraction script.

**N5. KG-grounded NER improvement on a previously unlabelled domain.** The demonstration that knowledge-graph features improve entity recognition where no labelled data previously existed establishes a feedback loop between KG construction and NER.

**N6. Three-guarantees verification framework.** The combination of determinism, completeness and exactness audit gates — with measured outcomes on both training and held-out data — is novel relative to existing provenance mechanisms in systems such as Wikidata.

Additional contributions include a memory-isolated subprocess pattern for resource-bounded NLP libraries, a multi-system unit-conversion registry, and a CARE-Principles-informed governance framework for traditional-knowledge release.

---

## 8. Evaluation

Seven evaluation pillars address both KG quality and system transferability.

**E1. Schema conformance.** Programmatic SHACL validation, anchor probes for known entities, provenance-presence checks. Target: 100% conformance.

**E2. External-authority re-verification.** Random-sample re-fetching of POWO and ICD-11 TM2 identifiers. Target: ≥95% agreement.

**E3. Expert spot-check.** A stratified 100-item triple sample assessed by a domain expert. Inter-annotator agreement reported as Gwet's AC1 with bootstrap confidence intervals. Target: AC1 ≥ 0.75.

**E4. LLM-judge triage.** A grounded LLM flags suspect triples for human review, framed as triage (Adam and Kliegr, 2025).

**E5. Statistical KG quality.** Stratified-sample precision with Bayesian credible intervals; capture-recapture recall. Target: precision ≥ 0.85.

**E6. NER ablation.** Three-arm comparison (gazetteer, distant-supervised CRF, KG-augmented CRF) with bootstrap confidence intervals. Target: statistically significant improvement for the KG-augmented arm.

**E7. Cross-document generalisation.** The system is applied without modification to held-out evaluation sets of increasing distance from the training corpus:

| Evaluation set | Relationship to training corpus |
|---|---|
| 10% withheld Vol I formulas | Same genre, withheld during development |
| Verse-form traditional-medicine text | Different register |
| Sample from a different TM book | Same tradition, different source |
| Informal clinical text (if available) | Different provenance and period |

Precision and recall are measured against hand-annotated references. A degradation curve quantifies the system's transfer boundary. Target: precision ≥ 0.80 on same-genre held-out; determinism 100% across all sets.

All evaluation data derives from sources already in the candidate's possession or publicly available. No external dataset acquisition is required.

---

## 9. Research Plan and Timeline

| Period | Activity | Milestone |
|---|---|---|
| **M1–M2** | OCR, structural recovery, tabular extraction | Silver training data (~850 structured entries) |
| **M3** | Closed-vocabulary lexicon extraction | System knowledge base (4 lexicon categories) |
| **M4–M5** | Sinhala-to-Sanskrit cascade resolver | Resolver with measured coverage |
| **M6** | External-authority enrichment; test-set preparation | Entity bindings to ICD-11 TM2 and POWO |
| **M7** | KG schema, builder, validation framework | Knowledge graph with four-layer validation |
| **M8–M9** | Prose-extraction system (labeller, emitter, audit gates, iteration loop) | Complete system with three-guarantees metrics |
| **M10** | Cross-document evaluation; NER ablation | Transfer metrics; NER F1 with bootstrap CIs |
| **M11** | Expert spot-check; statistical quality; release governance | Annotation report; credible intervals; governance |
| **M12** | Thesis writing; publication preparation | MSc dissertation; paper drafts |

**Risk mitigations.** OCR quality issues are addressed by a parallel PDF-direct extraction path. Resolver instability is mitigated by planned migration to ByT5-Sanskrit. Expert-annotator unavailability is mitigated by expanded LLM-judge triage with documented limitations.

---

## 10. List of Deliverables

**D1. Extraction system** (primary deliverable). A portable, deterministic, schema-constrained knowledge-graph extraction system for Sinhala traditional-medicine literature, released as open-source software.

**D2. Structured corpus and lexicons.** The first machine-readable Ayurvedic Pharmacopoeia Vol I (~850 formulas), closed-vocabulary lexicons (~770 substances, ~143 substitute pairs, ~50 therapeutic-action groups, ~43 unit symbols across 6 measurement systems), and Sinhala-to-Sanskrit resolver lexicons (~2,200 resolved terms).

**D3. Knowledge graph.** The first KG of Sri Lankan traditional medicine (~4,000+ nodes, ~12,000+ edges) with ICD-11 TM2, POWO and ChEBI bindings and triple-level provenance.

**D4. Evaluation artefacts.** Four-layer validation report, NER ablation results, cross-document transfer evaluation with degradation curve, and reproducibility infrastructure.

**D5. Publications.** MSc thesis; planned data paper (JOHD); planned methodology paper (EMNLP Findings or LREC-COLING).

---

## 11. List of References

Adam, S. and Kliegr, T. (2025) 'Traceable LLM-based validation of statements in knowledge graphs', *Information Processing & Management* [Preprint]. arXiv:2409.07507.

Aravinda, A. *et al.* (2025) 'SinLlama: a Sinhala-capable decoder LLM via continual pre-training' [Preprint]. arXiv:2508.09115.

Borchert, F. *et al.* (2023) 'xMEN: a modular toolkit for cross-lingual medical entity normalization', *JAMIA Open*, 2025. arXiv:2310.11275.

Carroll, S.R. *et al.* (2021) 'Operationalizing the CARE and FAIR Principles for Indigenous data futures', *Scientific Data*, 8, 108.

Chandralal, D. (2010) *Sinhala*. Amsterdam: John Benjamins.

de Silva, N. (2019, rev. 2026) 'Survey on publicly available Sinhala natural language processing tools and research' [Preprint]. arXiv:1906.02358.

Dhananjaya, V. *et al.* (2022) 'BERTifying Sinhala', in *Proceedings of LREC 2022*.

Gair, J.W. (1998) *Studies in South Asian Linguistics: Sinhala and Other South Asian Languages*. Oxford University Press.

Gala, J. *et al.* (2023) 'IndicTrans2: towards high-quality machine translation for all 22 scheduled Indian languages' [Preprint]. arXiv:2305.16307.

Gao, J. *et al.* (2019) 'Efficient knowledge graph accuracy evaluation', *Proceedings of the VLDB Endowment*, 12(11), pp. 1679–1691.

Gwet, K.L. (2008) 'Computing inter-rater reliability and its variance in the presence of high agreement', *British Journal of Mathematical and Statistical Psychology*, 61(1), pp. 29–48.

Hobbs, J.R. *et al.* (1997) 'FASTUS: a cascaded finite-state transducer for extracting information from natural-language text', in *Finite-State Language Processing*. MIT Press, pp. 383–406.

Ishida, R. (2024) *Sinhala — an overview for developers*. W3C.

Joshi, P. *et al.* (2020) 'The state and fate of linguistic diversity and inclusion in the NLP world', in *Proceedings of ACL 2020*.

Joshi, S. *et al.* (2026) 'GRAYU: a graph-based database integrating Ayurvedic formulations, plants, phytochemicals and diseases', *Frontiers in Pharmacology*, 16, 1727224.

Kartchner, D. *et al.* (2024) 'A comprehensive evaluation of biomedical entity linking models'. PMC11097978.

Khanuja, S. *et al.* (2021) 'MuRIL: multilingual representations for Indian languages' [Preprint]. arXiv:2103.10730.

Lin, X. *et al.* (2022) 'HerbKG: constructing a herbal-molecular medicine knowledge graph', *Frontiers in Genetics*, 13, 799349.

Liu, F. *et al.* (2021) 'Learning domain-specialised representations for cross-lingual biomedical entity linking', in *Proceedings of ACL 2021*.

Liyanage, C. and Sarveswaran, K. (2023) 'Sinhala dependency treebank (UD_Sinhala-STB)', in *Proceedings of UDW 2023*.

Marchesin, S. and Silvello, G. (2025) 'Credible intervals for knowledge graph accuracy estimation', in *Proceedings of SIGMOD 2025*.

Mirasdar, S. *et al.* (2026) 'AyurKOSH dataset: a machine-readable Ayurvedic knowledge resource', *IEEE DataPort*.

Monier-Williams, M. (1899) *A Sanskrit–English Dictionary*. Oxford: Clarendon Press.

Nehrdich, S. *et al.* (2024) 'ByT5-Sanskrit: a multitask byte-level model for Sanskrit', in *Findings of EMNLP 2024*.

Pramodya, R. *et al.* (2025) 'SinhalaMMLU: a Sinhala curriculum benchmark for large language models', in *Proceedings of EMNLP 2025*.

Rajan, V. (2024) *Aksharamukha: a transliteration tool for Indian scripts*. Available at: https://github.com/virtualvinodh/aksharamukha.

Ranathunga, S. *et al.* (2024) 'A multi-way parallel named entity annotated corpus for English, Tamil and Sinhala' [Preprint]. arXiv:2412.02056.

Ratner, A. *et al.* (2017) 'Snorkel: rapid training data creation with weak supervision', *Proceedings of VLDB*, 11(3), pp. 269–282.

Sandhan, J. *et al.* (2022) 'TransLIST: a transformer-based linguistically informed Sanskrit tokenizer', in *Findings of EMNLP 2022*.

Saper, R.B. *et al.* (2008) 'Lead, mercury, and arsenic in Ayurvedic medicines', *JAMA*, 300(8), pp. 915–923.

Sarsa, S. *et al.* (2026) 'Counting on consensus: selecting the right inter-annotator agreement metric' [Preprint]. arXiv:2603.06865.

Shang, J. *et al.* (2018) 'Learning named entity tagger using domain-specific dictionary' [Preprint]. arXiv:1809.03599.

Sonavane, O. *et al.* (2024) 'Limitations of LLMs as annotators for low-resource languages' [Preprint]. arXiv:2411.17637.

Terdalkar, H. (2023) 'Āyurjñānam: exploring Āyurveda using knowledge graphs', in *Proceedings of NYCIKS 2023*.

Vivek-Ananth, R.P. *et al.* (2023) 'IMPPAT 2.0: an enhanced phytochemical atlas of Indian medicinal plants', *ACS Omega*, 8(9), pp. 8827–8845.

Wang, B. *et al.* (2025) 'ODKE+: ontology-guided open-domain knowledge extraction with LLMs' [Preprint]. arXiv:2509.04696.

Wang, B. *et al.* (2026) 'From chaos to clarity: schema-constrained AI for auditable biomedical evidence extraction' [Preprint]. arXiv:2601.14267.

Wilkinson, M.D. *et al.* (2016) 'The FAIR Guiding Principles for scientific data management', *Scientific Data*, 3, 160018.

Willard, B.T. and Louf, R. (2023) 'Efficient guided generation for large language models' [Preprint]. arXiv:2307.09702.

WIPO (2024) *WIPO Treaty on Intellectual Property, Genetic Resources and Associated Traditional Knowledge*. Geneva.

World Health Organization (2025) *ICD-11, Module 2 — Traditional Medicine*.

Zaratiana, U. *et al.* (2024) 'GLiNER: generalist model for named entity recognition' [Preprint]. arXiv:2311.08526.

Zhong, L. *et al.* (2025) 'LLM-empowered knowledge graph construction: a survey' [Preprint]. arXiv:2510.20345.

---

## 12. Additional Information

**Ethics.** All outputs carry an explicit disclaimer that the knowledge graph records classical textual assertions, not clinically validated claims. Formulations containing heavy-metal-bearing minerals are flagged with a safety annotation (Saper *et al.*, 2008). Release governance adopts the FAIR-for-metadata, CARE-for-governance pattern (Carroll *et al.*, 2021) with Local Contexts TK Labels on the content layer.

**Copyright.** The Pharmacopoeia is published by the Department of Ayurveda, Government of Sri Lanka. The project releases derivative structure and annotation layers under CC-BY-SA-4.0 with documented upstream provenance; no substantial source text is redistributed.

**Computational requirements.** The system executes on commodity hardware (8 GB RAM, no GPU). External APIs are invoked once during construction and cached; no proprietary service is required at run time.

**Risk register.** OCR quality on legacy-font pages (mitigated by PDF-direct extraction). Resolver instability (mitigated by planned ByT5-Sanskrit migration). Expert-annotator availability (mitigated by expanded LLM-judge triage with documented limitations).

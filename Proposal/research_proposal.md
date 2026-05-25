# Research Proposal Outline

**Project Title:** A Deterministic Knowledge-Graph Extraction System for Sinhala Traditional Medicine Literature Using a Sanskrit-Bridge Approach

**Candidate:** Nuwan Medawaththa
**Programme:** Master of Computer Science — Individual Project (MCS 3306)
**Institution:** University of Colombo School of Computing (UCSC)
**Date:** May 2026
**Duration:** 12 months

---

## 1. Research Problem

Sri Lankan traditional medicine comprises a substantial body of clinical knowledge recorded across thousands of pages of Sinhala-script texts maintained by the Department of Ayurveda, Government of Sri Lanka. These sources include the state-sanctioned *Ayurvedic Pharmacopoeia* (three volumes, approximately 1,500 pages), the 1908 verse-form *Yogamālāva*, and an uncatalogued collection of clinical notebooks, hospital formularies and classical palm-leaf compilations. Despite this wealth of documented knowledge, no machine-readable, structured or queryable representation of any Sri Lankan traditional-medicine text has been published to date (de Silva, 2026; Joshi *et al.*, 2026; Vivek-Ananth *et al.*, 2023). Whilst the Indian Ayurvedic ecosystem possesses substantial computational resources — notably TKDL, IMPPAT, GRAYU and AyurKOSH — each of these draws exclusively upon Indian sources. Chinese network-pharmacology databases address an entirely different medical tradition.

This project addresses the following computer-science problem: **the construction of a reusable, deterministic extraction system capable of converting arbitrary free-style Sinhala traditional-medicine literature into a schema-constrained, provenance-grounded knowledge graph (KG).** The challenge is compounded by the extreme under-resourcing of Sinhala for computational processing: the language is classified as Joshi class 1 (Joshi *et al.*, 2020), is excluded from the AI4Bharat Indic-NLP ecosystem (Gala *et al.*, 2023), possesses no published medical NER corpus or model, maintains a Universal Dependencies treebank of only 100 sentences (Liyanage and Sarveswaran, 2023), and employs a dense admixture of native Sinhala and Sanskrit-derived (*tatsama*) terminology for which no computational classifier exists.

The proposed approach treats the *Ayurvedic Pharmacopoeia, Volume I* (525 pages) as a **structured training corpus**. Its tabular formula section provides silver-labelled entity–relation pairs derived from spatial layout, its reference tables supply closed-vocabulary lexicons, and its domain terminology seeds a cross-lingual Sinhala-to-Sanskrit resolver. From this single source, the project constructs a portable extraction system — comprising lexicons, resolver, gazetteer, schema constraints and audit mechanisms — that generalises to unseen traditional-medicine prose from other volumes, registers and time periods without retraining. The research problem therefore encompasses five coupled sub-problems:

1. **Structural recovery** of silver training data from a tabular Sinhala printed source whose spatial layout encodes semantic role.
2. **Cross-lingual lexical bridging** from Sinhala to the well-resourced Sanskrit NLP ecosystem, exploiting the orthographic distinction between native (*śuddha*) and mixed (*miśra*) Sinhala registers (Gair, 1998).
3. **Schema-constrained information extraction** from free-style Sinhala-Sanskrit-mixed prose under hard determinism requirements: byte-identical re-runs, verbatim source-span binding, and zero hallucination.
4. **Knowledge-graph construction with provenance** at triple level, with external-authority binding to WHO ICD-11 TM2, POWO/IPNI and ChEBI.
5. **Empirical validation** that the system generalises to unseen documents and that its KG materially improves downstream named-entity recognition.

The project is positioned against the 2025 schema-constrained-extraction state of the art (Wang *et al.*, 2025; Wang *et al.*, 2026; Zhong *et al.*, 2025) on the basis of two guarantees those systems do not provide: **byte-identical determinism** and **verbatim source-span binding** on every emitted triple — properties that are essential in a low-resource biomedical domain where reproducibility and auditability outweigh the recall ceiling of stochastic generation.

---

## 2. Literature Review

### 2.1 Sinhala as a computational target language

Sinhala (ISO 639-3 `sin`) is an Insular Indo-Aryan language whose sole living close relative is Dhivehi (Gair, 1998; Chandralal, 2010). Joshi *et al.* (2020) classify it among the most under-resourced languages for NLP, placing it in class 1 alongside Nepali and Igbo. The Universal Dependencies treebank comprises only 100 sentences (Liyanage and Sarveswaran, 2023), and Sinhala is excluded from the entire AI4Bharat ecosystem — IndicBERT, IndicTrans2 and MuRIL cover only constitutionally scheduled Indian languages (Gala *et al.*, 2023; Khanuja *et al.*, 2021).

SinBERT (Dhananjaya *et al.*, 2022) and SinLlama (Aravinda *et al.*, 2025) provide encoder and decoder backbones respectively, yet both are trained on news and web text. No medical or Ayurvedic Sinhala NLP work has been published as of 2026 (de Silva, 2026). The SinhalaMMLU benchmark (Pramodya *et al.*, 2025) demonstrates that even frontier LLMs achieve only 67% accuracy on Sinhala cultural domains, providing empirical motivation against reliance on LLM-only generation for Ayurvedic text.

The Sinhala script is an abugida (Unicode U+0D80–U+0DFF) in which conjunct formation requires virama plus ZWJ in a manner that is mandatory and rendering-affecting (Ishida, 2024). Crucially, the orthographic distinction between *śuddha* (native) and *miśra* (mixed) Sinhala — the latter retaining Sanskrit aspirates, sibilants and vocalic-r — constitutes the operational signal for the proposed cross-lingual bridge.

### 2.2 Cross-lingual lexical bridging and Sanskrit NLP

ByT5-Sanskrit (Nehrdich *et al.*, 2024) represents the current state of the art for joint sandhi-splitting, lemmatisation and morphological tagging, surpassing TransLIST (Sandhan *et al.*, 2022). The Monier-Williams dictionary, accessed via the Cologne Digital Sanskrit Dictionaries and `pycdsl`, provides approximately 160,000 headwords. Aksharamukha (Rajan, 2024) enables lossless transliteration between Sinhala and 121 scripts, including IAST.

No published system bridges Sinhala to Sanskrit lexical resources. The closest analogue, xMEN (Borchert *et al.*, 2023), is a modular cross-lingual medical-entity-normalisation toolkit, but its evaluation encompasses no Indic language. Cross-lingual SapBERT (Liu *et al.*, 2021) shares this limitation. The absence of any computational Sinhala-to-Sanskrit bridge is a documented gap that the present project addresses.

### 2.3 Schema-constrained information extraction

The prevailing paradigm in biomedical KG construction is schema-constrained extraction: the target schema serves as a hard constraint, and extractors — whether rule-based, CRF or LLM-driven — produce only schema-valid triples, with invalid candidates rejected at emission (Wang *et al.*, 2025; Wang *et al.*, 2026; Zhong *et al.*, 2025). GLiNER (Zaratiana *et al.*, 2024) and GLiNER2 (Stepanov *et al.*, 2025) provide zero-shot schema-driven entity extractors but offer limited Sinhala coverage. Snorkel-style programmatic weak supervision (Ratner *et al.*, 2017) provides a formal framework for combining multiple labelling functions.

Comparable traditional-medicine knowledge graphs include GRAYU (Joshi *et al.*, 2026) with 157,000 nodes, HerbKG (Lin *et al.*, 2022) with 53,000 relations, AyurKOSH (Mirasdar *et al.*, 2026), and Āyurjñānam (Terdalkar, 2023). WHO ICD-11 TM2, released February 2025, provides 529 codes for Ayurveda/Siddha/Unani conditions. No analogous resource exists for Sri Lankan traditional medicine.

### 2.4 KG evaluation without a gold standard

Sample-based precision estimation with credible intervals (Gao *et al.*, 2019; Marchesin and Silvello, 2025), capture-recapture recall estimation via Lincoln-Petersen, and BioRED triple-level evaluation conventions (Luo *et al.*, 2024) constitute the applicable evaluation paradigm. LLM-as-judge approaches achieve 88% precision but only 44% recall (Adam and Kliegr, 2025), warranting use as triage rather than validation. For inter-annotator agreement under skewed distributions, Gwet's AC1 (Gwet, 2008; Sarsa *et al.*, 2026) is preferred over Cohen's kappa.

### 2.5 Research gap

The literature review identifies the following gaps: (i) no machine-readable Sri Lankan traditional-medicine resource or knowledge graph exists; (ii) no computational Sinhala-to-Sanskrit lexical bridge has been published; (iii) no medical Sinhala NER corpus or model is available; (iv) the schema-constrained-extraction state of the art does not provide byte-identical determinism or verbatim source-span binding as primary guarantees; and (v) the FAIR-versus-CARE tension for traditional-knowledge release remains unresolved in the Sri Lankan legal context. This project addresses all five gaps through a single coherent extraction system.

---

## 3. Research Questions

**RQ1.** Can a deterministic cascade-based resolver bridge Sinhala-script tokens to Sanskrit Monier-Williams lemmas using orthographic signal and corpus-internal glossaries, and what fraction of traditional-medicine terminology can it resolve? (Nehrdich *et al.*, 2024; Borchert *et al.*, 2023; Gair, 1998)

**RQ2.** Can a schema-constrained extraction system, trained on a single structured pharmacopoeia, satisfy three explicit guarantees — byte-identical determinism, completeness with explicit unsupported-span logging, and verbatim source-span binding — on unseen free-style Sinhala traditional-medicine prose? (Wang *et al.*, 2025; Wang *et al.*, 2026; Hobbs *et al.*, 1997)

**RQ3.** Does the extraction system transfer with measurable precision and recall to structurally and temporally distinct documents without retraining? (Shang *et al.*, 2018; Ratner *et al.*, 2017; Joshi *et al.*, 2020)

**RQ4.** Does augmenting named-entity recognition with knowledge-graph-derived features materially improve F1 over gazetteer-only and distant-supervised CRF baselines on a fine-grained Ayurvedic-entity tagset? (Dhananjaya *et al.*, 2022; Ranathunga *et al.*, 2024; Kartchner *et al.*, 2024)

**RQ5.** How can a traditional-medicine knowledge graph satisfy FAIR Principles for metadata whilst honouring CARE Principles for the formula-composition content layer? (Carroll *et al.*, 2021; Wilkinson *et al.*, 2016; WIPO, 2024)

---

## 4. Research Objectives

The project pursues seven objectives organised in two phases.

**Phase I — System construction** (using the Pharmacopoeia as training corpus):

**O1.** Structure the training corpus by processing Pharmacopoeia Vol I through OCR and a three-stage extraction pipeline (page slicing, row clustering, column-zone state machine) to produce approximately 850 structured formula entries as silver training data.

**O2.** Construct a reusable Sinhala-to-Sanskrit cascade resolver comprising a phonotactic router, transliteration-based dictionary lookup, compound-word segmentation, sandhi analysis, and a corpus-internal substitute-glossary fallback — designed to operate on any Sinhala text containing tatsama terminology.

**O3.** Extract closed-vocabulary lexicons from the Pharmacopoeia's reference tables (categorised raw materials, substitute glossary, therapeutic-action groups, unit-conversion systems) to form the system's knowledge base.

**O4.** Implement the core extraction system: a gazetteer-based span labeller, sentence segmenter, schema-constrained relation emitter, three-guarantees audit framework, and an iteration-loop mechanism for systematic gap identification. Design and populate a knowledge-graph schema with external-authority bindings (ICD-11 TM2, POWO, ChEBI).

**Phase II — System validation:**

**O5.** Evaluate system generalisation on held-out documents: withheld Vol I formulas, the 1908 Yogamālāva, a Pharmacopoeia Vol II sample, and if available a clinical-notebook page.

**O6.** Conduct a three-arm NER ablation (gazetteer baseline, distant-supervised CRF, KG-augmented CRF) to quantify the knowledge graph's downstream utility.

**O7.** Release the system and resources under a FAIR-for-metadata, CARE-for-governance framework with appropriate traditional-knowledge labels.

---

## 5. Scope of the Study

**In scope.** The project encompasses the construction of an extraction system using Pharmacopoeia Vol I as the training corpus, and the empirical validation of that system's transferability. The formula section (pp. 172–443, approximately 850 entries) provides silver training data; the reference tables (pp. 65–90, 444–525) supply the closed-vocabulary knowledge base. A 10% random hold-out of Vol I and samples from Vol II and the Yogamālāva serve as evaluation sets. The knowledge graph is bound to ICD-11 TM2, POWO and ChEBI.

**Out of scope.** Exhaustive processing of Vols II–III beyond evaluation samples; complete tadbhava etymological lexicons requiring external lexicographic expertise; colonial-loanword handling requiring botanical curation; cross-formula link-prediction; clinical validation or pharmacovigilance modelling; and large-scale manually-annotated NER corpora. Each exclusion marks a defined future-work pathway.

---

## 6. Research Methodology

The methodology adopts a rule-based, closed-vocabulary-first architecture, positioned against the prevailing LLM-driven extraction paradigm. This positioning is motivated by two considerations: first, empirical evidence that frontier LLMs achieve poor accuracy on culturally-rich Sinhala domains (Pramodya *et al.*, 2025; Sonavane *et al.*, 2024); and second, the architectural requirement that determinism, auditability and zero hallucination be guaranteed by construction rather than approximated probabilistically.

The central methodological principle is that the Pharmacopoeia functions as a structured training corpus. Its tabular layout encodes entity types and relations through spatial position, yielding thousands of silver-labelled examples that the system absorbs as lexicons, resolver calibration data and extraction templates. Once constructed, the system operates on arbitrary Sinhala traditional-medicine prose.

The approach comprises two phases:

**Phase I — System construction.** The Pharmacopoeia undergoes OCR and a three-stage structural recovery pipeline to produce silver training data. From this data and the Pharmacopoeia's reference tables, four categories of component are constructed: (i) a three-tier Sinhala-to-Sanskrit cascade resolver that exploits the phonotactic distinction between native and mixed Sinhala registers to bridge tokens to Sanskrit lexical resources; (ii) closed-vocabulary lexicons covering raw materials, substitutes, therapeutic-action groups and measurement units; (iii) a knowledge-graph schema with external-authority bindings and a four-layer validation framework; and (iv) a prose-extraction engine employing gazetteer-based longest-match span labelling, schema-constrained relation emission, and provenance binding. The extraction engine is formally characterised as a cascaded finite-state transducer (Hobbs *et al.*, 1997) and constitutes the non-neural limit of grammar-constrained decoding (Willard and Louf, 2023). An iteration-loop mechanism surfaces uncovered tokens for systematic lexicon expansion.

**Phase II — System validation and deployment.** The constructed system is applied without modification to held-out documents of increasing distance from the training corpus. A three-arm NER ablation quantifies the downstream utility of KG-derived features. Evaluation employs sample-based precision with credible intervals (Marchesin and Silvello, 2025), capture-recapture recall estimation, expert spot-checking with Gwet's AC1, and LLM-judge triage. Determinism is enforced by construction through stable sort ordering, deterministic tie-breaking and fixed random seeds, verified via SHA-256 output manifests.

The system exposes a pluggable interface for a future learned oracle (CRF, neural tagger), permitting extension without compromising the deterministic primary path.

---

## 7. Novelty and Expected Research Contributions

The project's contributions span methodology, resource, empirical validation and scholarly framing. The overarching novelty is that the system is trained on a single pharmacopoeia yet empirically validated on unseen literature, establishing transferability rather than source-specific extraction.

**N1. First computational Sinhala-to-Sanskrit lexical bridge.** No published system maps Sinhala-script tokens to Sanskrit lexical resources. The proposed cascade resolver — comprising a phonotactic router, transliteration-based dictionary lookup, compound-word segmentation, sandhi analysis and substitute-glossary fallback — addresses this gap. The closest analogue, xMEN (Borchert *et al.*, 2023), encompasses no Indic language.

**N2. Deterministic, schema-constrained extraction with three verifiable guarantees.** The system provides byte-identical determinism, content-token completeness with explicit gap logging, and verbatim source-span binding on every triple. These guarantees are positioned against the 2025 extraction state of the art (ODKE+, *Chaos to Clarity*), which does not offer byte-identical determinism as a primary property.

**N3. First machine-readable Sri Lankan traditional-medicine resource and knowledge graph.** This addresses a confirmed gap in the global landscape: no Sri Lankan counterpart to TKDL, GRAYU or AyurKOSH exists. The knowledge graph is interoperable with the international ecosystem via ICD-11 TM2, POWO and ChEBI bindings.

**N4. Demonstrated cross-document generalisation without retraining.** The empirical demonstration that a rule-based system calibrated on one volume transfers to structurally and temporally distinct documents establishes the system as a general-purpose tool rather than a single-source extraction script.

**N5. KG-grounded NER improvement on a previously unlabelled domain.** The demonstration that knowledge-graph features improve named-entity recognition on Sinhala medical text — a domain possessing no prior labelled data — establishes a feedback loop between KG construction and entity extraction.

**N6. Three-guarantees verification framework.** The combination of determinism, completeness and exactness audit gates with measured numerical outcomes on both training and held-out documents is novel; existing systems such as Wikidata provide only weaker provenance mechanisms.

Additional contributions include: a reusable memory-isolated subprocess pattern for resource-bounded NLP libraries, a multi-system unit-conversion registry, a corpus-internal substitute lexicon, and a CARE-Principles-informed release-governance framework for a traditional-knowledge resource.

---

## 8. Evaluation

The evaluation strategy comprises seven pillars addressing both KG quality and system transferability.

**E1. Schema conformance.** Programmatic SHACL validation, anchor probes for known entities, provenance-presence checks and edge domain/range verification. Target: 100% SHACL conformance, zero missing provenance fields.

**E2. External-authority re-verification.** Random-sample re-fetching of POWO LSIDs and ICD-11 TM2 codes against their respective APIs. Target: ≥95% agreement.

**E3. Expert spot-check.** A 100-item stratified random sample of triples assessed by an Ayurvedic-medicine domain expert, with inter-annotator agreement reported as Gwet's AC1 with bootstrap confidence intervals (Gwet, 2008). Target: AC1 ≥ 0.75.

**E4. LLM-judge triage.** A grounded LLM judge flags suspect triples for human review, framed as triage rather than validation (Adam and Kliegr, 2025).

**E5. Statistical KG quality.** Stratified-sample precision with Bayesian credible intervals (Marchesin and Silvello, 2025); capture-recapture recall estimation using two independent extractor outputs. Target: precision ≥ 0.85 (95% CI above 0.75).

**E6. NER ablation.** Three-arm comparison — gazetteer baseline, distant-supervised CRF, KG-augmented CRF — with bootstrap 95% confidence intervals on F1. Target: statistically significant F1 improvement for the KG-augmented arm.

**E7. Cross-document generalisation.** The system is applied without modification to four held-out evaluation sets:

| Evaluation set | Relation to training corpus |
|---|---|
| 10% withheld Vol I formulas | Same genre, withheld during development |
| Yogamālāva (1908) | Different register (verse-form) |
| Vol II sample | Same genre, different formulas |
| Clinical notebook (if available) | Different provenance and period |

Triple-level precision and recall are measured against hand-annotated references. The three-guarantees metrics are reported independently per set. A degradation curve across the four sets quantifies the system's transfer boundary.

All evaluation data derives from the Pharmacopoeia (in the candidate's possession) and publicly available volumes; no external dataset acquisition is required.

---

## 9. Research Plan and Timeline

The project is structured in two phases across twelve months.

**Phase I — System construction (Months 1–9)**

| Period | Activity | Milestone |
|---|---|---|
| M1–M2 | OCR, structural recovery, tabular extraction | Silver training data (~850 structured entries) |
| M3 | Closed-vocabulary lexicon extraction | Four lexicon files constituting the system's knowledge base |
| M4–M5 | Sinhala-to-Sanskrit cascade resolver | Resolver lexicons with measured coverage |
| M6 | External-authority enrichment; auxiliary corpus processing | Entity bindings to ICD-11 TM2 and POWO |
| M7 | KG schema, builder and validation framework | Initial knowledge graph with four-layer validation report |
| M8–M9 | Prose-extraction system (gazetteer, segmenter, labeller, relation emitter, audit gates, iteration loop) | Complete extraction system with three-guarantees metrics |

**Phase II — Validation and thesis (Months 10–12)**

| Period | Activity | Milestone |
|---|---|---|
| M10 | Cross-document generalisation evaluation; NER ablation | Transfer metrics and degradation curve; NER F1 with bootstrap CIs |
| M11 | Expert spot-check; statistical KG quality; release governance | Annotation report; precision/recall credible intervals |
| M12 | Thesis writing; publication preparation | MSc dissertation; paper drafts |

**Risk mitigations.** OCR quality issues are mitigated by a parallel PDF-direct text extraction path. Resolver instability is mitigated by planned migration to ByT5-Sanskrit. Expert-annotator unavailability is mitigated by expanded LLM-judge triage with documented limitations.

---

## 10. List of Deliverables

**D1. Extraction system** (primary deliverable). A portable, deterministic, schema-constrained KG extraction system for Sinhala traditional-medicine literature, released as open-source software.

**D2. Structured corpus and lexicons.** The first machine-readable Sri Lankan Ayurvedic Pharmacopoeia Vol I (~850 formulas), Yogamālāva (~145 entries), and closed-vocabulary lexicons (~770 substances, ~143 substitute pairs, ~50 therapeutic-action groups, ~43 unit symbols across 6 systems), released with Datasheet, Data Statement and FAIR-compliant metadata.

**D3. Knowledge graph.** The first KG of Sri Lankan traditional medicine (approximately 4,000+ nodes, 12,000+ edges) in four serialisation formats, with ICD-11 TM2, POWO and ChEBI bindings and triple-level provenance.

**D4. Validation and evaluation artefacts.** Four-layer validation report, NER ablation results, cross-document transfer evaluation with degradation curve, and reproducibility infrastructure.

**D5. Publications.** MSc thesis; planned data paper (JOHD); planned methodology paper (EMNLP Findings / LREC-COLING).

---

## 11. List of References

Adam, S. and Kliegr, T. (2025) 'Traceable LLM-based validation of statements in knowledge graphs', *Information Processing & Management* [Preprint]. arXiv:2409.07507.

Aravinda, A. *et al.* (2025) 'SinLlama: a Sinhala-capable decoder LLM via continual pre-training' [Preprint]. arXiv:2508.09115.

Borchert, F. *et al.* (2023) 'xMEN: a modular toolkit for cross-lingual medical entity normalization', *JAMIA Open*, 2025. arXiv:2310.11275.

Carroll, S.R. *et al.* (2021) 'Operationalizing the CARE and FAIR Principles for Indigenous data futures', *Scientific Data*, 8, 108.

Chandralal, D. (2010) *Sinhala*. Amsterdam: John Benjamins.

Cooper, L. *et al.* (2013) 'The Plant Ontology as a tool for comparative plant anatomy', *Plant and Cell Physiology*, 54(2), e1.

de Silva, N. (2019, rev. 2026) 'Survey on publicly available Sinhala natural language processing tools and research' [Preprint]. arXiv:1906.02358.

Dhananjaya, V. *et al.* (2022) 'BERTifying Sinhala', in *Proceedings of LREC 2022*.

Gair, J.W. (1998) *Studies in South Asian Linguistics: Sinhala and Other South Asian Languages*. Oxford University Press.

Gala, J. *et al.* (2023) 'IndicTrans2: towards high-quality machine translation for all 22 scheduled Indian languages' [Preprint]. arXiv:2305.16307.

Gao, J. *et al.* (2019) 'Efficient knowledge graph accuracy evaluation', *Proceedings of the VLDB Endowment*, 12(11), pp. 1679–1691.

Goyal, P. and Huet, G. (2016) 'Design and analysis of a lean interface for Sanskrit corpus annotation', *Journal of Language Modelling*, 4(2), pp. 145–182.

Gwet, K.L. (2008) 'Computing inter-rater reliability and its variance in the presence of high agreement', *British Journal of Mathematical and Statistical Psychology*, 61(1), pp. 29–48.

Hastings, J. *et al.* (2013) 'The ChEBI reference database and ontology', *Nucleic Acids Research*, 41(D1), pp. D456–D463.

Hobbs, J.R. *et al.* (1997) 'FASTUS: a cascaded finite-state transducer for extracting information from natural-language text', in *Finite-State Language Processing*. MIT Press, pp. 383–406.

Ishida, R. (2024) *Sinhala — an overview for developers*. W3C.

Jayatilleke, N. and de Silva, N. (2025) 'Zero-shot OCR accuracy of low-resourced languages' [Preprint]. arXiv:2507.18264.

Joshi, P. *et al.* (2020) 'The state and fate of linguistic diversity and inclusion in the NLP world', in *Proceedings of ACL 2020*.

Joshi, S. *et al.* (2026) 'GRAYU: a graph-based database integrating Ayurvedic formulations, plants, phytochemicals and diseases', *Frontiers in Pharmacology*, 16, 1727224.

Kartchner, D. *et al.* (2024) 'A comprehensive evaluation of biomedical entity linking models'. PMC11097978.

Khanuja, S. *et al.* (2021) 'MuRIL: multilingual representations for Indian languages' [Preprint]. arXiv:2103.10730.

Lin, X. *et al.* (2022) 'HerbKG: constructing a herbal-molecular medicine knowledge graph', *Frontiers in Genetics*, 13, 799349.

Liu, F. *et al.* (2021) 'Learning domain-specialised representations for cross-lingual biomedical entity linking', in *Proceedings of ACL 2021*.

Liyanage, C. and Sarveswaran, K. (2023) 'Sinhala dependency treebank (UD_Sinhala-STB)', in *Proceedings of UDW 2023*.

Luo, L. *et al.* (2024) 'BioRED: a comprehensive biomedical relation extraction dataset', *Database*, 2024.

Marchesin, S. and Silvello, G. (2025) 'Credible intervals for knowledge graph accuracy estimation', in *Proceedings of SIGMOD 2025*.

Mirasdar, S. *et al.* (2026) 'AyurKOSH dataset: a machine-readable Ayurvedic knowledge resource', *IEEE DataPort*.

Monier-Williams, M. (1899) *A Sanskrit–English Dictionary*. Oxford: Clarendon Press.

Nehrdich, S. *et al.* (2024) 'ByT5-Sanskrit: a multitask byte-level model for Sanskrit', in *Findings of EMNLP 2024*.

Pramodya, R. *et al.* (2025) 'SinhalaMMLU: a Sinhala curriculum benchmark for large language models', in *Proceedings of EMNLP 2025*.

Rajan, V. (2024) *Aksharamukha: a transliteration tool for Indian scripts*. Available at: https://github.com/virtualvinodh/aksharamukha.

Ranathunga, S. *et al.* (2024) 'A multi-way parallel named entity annotated corpus for English, Tamil and Sinhala' [Preprint]. arXiv:2412.02056.

Ratner, A. *et al.* (2017) 'Snorkel: rapid training data creation with weak supervision', *Proceedings of VLDB*, 11(3), pp. 269–282.

Safavi, T., Koutra, D. and Meij, E. (2020) 'Evaluating the calibration of knowledge graph embeddings', in *Proceedings of EMNLP 2020*.

Sandhan, J. *et al.* (2022) 'TransLIST: a transformer-based linguistically informed Sanskrit tokenizer', in *Findings of EMNLP 2022*.

Saper, R.B. *et al.* (2008) 'Lead, mercury, and arsenic in Ayurvedic medicines', *JAMA*, 300(8), pp. 915–923.

Sarsa, S. *et al.* (2026) 'Counting on consensus: selecting the right inter-annotator agreement metric' [Preprint]. arXiv:2603.06865.

Shang, J. *et al.* (2018) 'Learning named entity tagger using domain-specific dictionary' [Preprint]. arXiv:1809.03599.

Sonavane, O. *et al.* (2024) 'Limitations of LLMs as annotators for low-resource languages' [Preprint]. arXiv:2411.17637.

Stepanov, K. *et al.* (2025) 'GLiNER2: an efficient multi-task information extraction system' [Preprint]. arXiv:2507.18546.

Terdalkar, H. (2023) 'Āyurjñānam: exploring Āyurveda using knowledge graphs', in *Proceedings of NYCIKS 2023*.

Vivek-Ananth, R.P. *et al.* (2023) 'IMPPAT 2.0: an enhanced phytochemical atlas of Indian medicinal plants', *ACS Omega*, 8(9), pp. 8827–8845.

Wang, B. *et al.* (2025) 'ODKE+: ontology-guided open-domain knowledge extraction with LLMs' [Preprint]. arXiv:2509.04696.

Wang, B. *et al.* (2026) 'From chaos to clarity: schema-constrained AI for auditable biomedical evidence extraction' [Preprint]. arXiv:2601.14267.

Wilkinson, M.D. *et al.* (2016) 'The FAIR Guiding Principles for scientific data management', *Scientific Data*, 3, 160018.

Willard, B.T. and Louf, R. (2023) 'Efficient guided generation for large language models' [Preprint]. arXiv:2307.09702.

WIPO (2024) *WIPO Treaty on Intellectual Property, Genetic Resources and Associated Traditional Knowledge*. Geneva.

World Health Organization (2025) *ICD-11, Module 2 — Traditional Medicine*.

Yan, D. *et al.* (2022) 'Construction of a knowledge graph for the Treatise on Febrile Diseases'.

Zaratiana, U. *et al.* (2024) 'GLiNER: generalist model for named entity recognition' [Preprint]. arXiv:2311.08526.

Zhong, L. *et al.* (2025) 'LLM-empowered knowledge graph construction: a survey' [Preprint]. arXiv:2510.20345.

---

## 12. Additional Information

**Ethics.** All outputs will carry an explicit disclaimer that the knowledge graph records classical textual assertions, not clinically validated claims. Formulations containing heavy-metal-bearing minerals will be flagged with a safety annotation (Saper *et al.*, 2008). The release governance adopts the FAIR-for-metadata, CARE-for-governance pattern (Carroll *et al.*, 2021) with Local Contexts TK Labels on the content layer.

**Copyright.** The source Pharmacopoeia is published by the Department of Ayurveda, Government of Sri Lanka. The project releases derivative structure and annotation layers under CC-BY-SA-4.0 with documented upstream provenance; no substantial source text is redistributed.

**Computational requirements.** The system is designed to execute on commodity hardware (8 GB RAM, no GPU). External APIs (Google Cloud Vision, POWO, ICD-11) are invoked once during system construction and their outputs cached; no proprietary service dependency exists at run time.

**Risk register.** Principal risks include OCR quality on legacy-font pages (mitigated by a parallel PDF-direct extraction path), resolver instability at scale (mitigated by planned migration to ByT5-Sanskrit), and expert-annotator availability for the spot-check evaluation (mitigated by expanded LLM-judge triage with documented limitations).

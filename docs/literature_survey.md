<!--
  ╔══════════════════════════════════════════════════════════════════════╗
  ║  LITERATURE SURVEY — ITERATIVE DOCUMENT                              ║
  ║  Project: Sinhala Traditional Medicine NLP                           ║
  ║  Conventions for editing this file:                                  ║
  ║    • All claims must carry an in-text Harvard citation.              ║
  ║    • Every cited work must have a Bibliography entry.                ║
  ║    • Bibliography is alphabetised by first author surname.           ║
  ║    • Provenance markers:                                             ║
  ║         [F] = primary source fetched and read in full                ║
  ║         [S] = found in a search snippet only — needs verification    ║
  ║         [?] = inference or interpretation, not a literal claim       ║
  ║    • Section numbering is stable across revisions; insert sub-       ║
  ║      sections rather than renumbering when adding material.          ║
  ║    • A change log lives at §10. Update it on every commit.           ║
  ╚══════════════════════════════════════════════════════════════════════╝
-->

# Literature Survey
## Building a Knowledge Graph from a Sinhala Ayurvedic Pharmacopoeia: an Iterative Cross-Disciplinary Review

> **Document version:** v0.4 (2026-05) · **Iteration count:** 4
> **Status:** working draft for an MSc (UCSC MCS 3306) literature review.
> **v0.2 added:** §3.5 global-initiatives landscape + a primary-source
> verification pass that corrected six numbers and three attributions.
> **v0.3 added:** five previously-missed areas — active learning (§5.5),
> reproducibility/determinism (§5.3), CARE-vs-FAIR ethics (§5.4),
> cross-lingual NER transfer (§4.6), domain adaptation (§7).
> **v0.4 adds:** annotation methodologies incl. the gazetteer→LLM-silver→
> human pipeline (§5.6); unlabelled-KG evaluation by sampling +
> capture–recapture (§4.9); formal-language framing as cascaded-FST /
> grammar-constrained IE (§4.11); deeper traditional-knowledge governance
> with a concrete FAIR-metadata/CARE-governance licensing model (§5.4).

---

### Abstract

This survey reviews the literature relevant to building a deterministic, complete, and exact knowledge-graph (KG) extraction pipeline for Sinhala-language Ayurvedic medical text. It covers four bodies of work: (i) the linguistic and computational profile of Sinhala (an Insular Indo-Aryan language classified at Joshi *et al.*'s class 1, "The Scraping-Bys" (Joshi *et al.*, 2020)); (ii) the methodological substrate — OCR, tokenization, cross-lingual lexical bridging, entity linking, schema-constrained extraction, and KG validation — as it stood in 2022–2026; (iii) the domain substrate of traditional-medicine ontologies, knowledge graphs, units of measure, and pharmacovigilance; and (iv) the cross-cutting concerns of code-mixing, digital humanities, reproducibility, and resource release. The survey is positioned as a working artefact that will be revised across iterations; each section is structured so additions can be made without renumbering, and the bibliography is alphabetised for incremental growth.

---

## Table of Contents

1. Introduction
2. The Source Language: Sinhala
3. The Domain: Traditional Ayurvedic Medicine
4. The Engineering Pipeline
5. Cross-Cutting Concerns
6. Positioning the Present Work
7. Future Directions
8. Bibliography
9. Appendices
10. Change log

---

## 1. Introduction

### 1.1 The problem

The Sri Lankan Ayurvedic Pharmacopoeia is a 525-page printed reference in Sinhala script that catalogues herbal-medicine formulas with their ingredients, preparations, indications, vehicles, and dosages. No machine-readable form of this knowledge has previously been published. The present project converts this printed text into a typed, queryable, schema-constrained knowledge graph with external-authority bindings to Plants of the World Online (POWO; Royal Botanic Gardens, Kew, no date), the World Health Organization's ICD-11 Traditional Medicine Module 2 (TM2; World Health Organization, 2025), and the European Bioinformatics Institute's ChEBI ontology (Hastings *et al.*, 2013).

The target deliverable is not only the structured corpus but a *deterministic* extraction pipeline whose three guarantees — that outputs are byte-identical on re-runs, that every triple is grounded in a verbatim source span, and that no information is silently dropped — qualify the work as auditable scholarship rather than opaque ML inference.

### 1.2 Scope of this survey

The survey integrates four parallel sub-surveys conducted in 2026-05 across (i) Sinhala-specific NLP, (ii) general computational methods touched by the pipeline, (iii) traditional-medicine ontology standards, and (iv) pharmacovigilance. It deliberately includes published work that contradicts our methodological choices so the trade-offs are explicit.

### 1.3 Notation and citation conventions

In-text citations use Harvard style: *(Author, Year)*. Provenance markers appearing after a citation distinguish primary sources fetched in full from those identified only through search snippets:

- **[F]** primary source fetched and read in full
- **[S]** identified through a search snippet, not yet verified against the primary
- **[?]** an inferential bridge built on cited claims, not a direct claim

Section numbers are stable across versions; insertions take new sub-numbers rather than renumbering peers.

---

## 2. The Source Language: Sinhala

### 2.1 Linguistic classification

Sinhala (ISO 639-3 `sin`; Glottolog `sinh1246`) is the principal Indo-Aryan language of Sri Lanka, with approximately 18 million L1 speakers (Eberhard, Simons and Fennig, 2024) [S]. Within Indo-Aryan it occupies the **Insular Indo-Aryan** branch alongside Dhivehi/Maldivian; the branch separated from continental Indo-Aryan around the fifth century BCE (Gair, 1998; Geiger, 1938). This isolation has left Sinhala phonologically and morphologically distinct from Hindi, Bengali, and other continental relatives, while two millennia of areal contact with Tamil have reinforced its strict head-final, SOV, postpositional, left-branching syntax (Gair, 1998).

Two grammatical features are notable for NLP. First, Sinhala exhibits **prenasalised consonants** (`ඬ`, `ඳ`, `ඹ`) — rare elsewhere in Indo-Aryan — and a **four-way deictic system** (proximal, medial, distal, anaphoric) which is typologically unusual (Chandralal, 2010) [S]. Second, the verbal system distinguishes **volitive/involitive (active/inactive) stem classes**: an involitive verb takes a non-nominative (dative, instrumental, or accusative) subject, encoding lack of agentive control (Inman, 1993; Henadeerage, 2002) [S]. This pattern is absent in Hindi and largely orthogonal to standard subject-finding heuristics, with implications for POS-tagging and dependency parsing.

### 2.2 The Sinhala script: computational properties

The Sinhala script occupies Unicode block U+0D80–U+0DFF and is an abugida descended from the Brahmi family (Ishida, no date) [F]. Each *akṣara* is a consonant carrying an inherent /a/, optionally modified by a dependent vowel sign or by the *al-lakuna* (virama, U+0DCA) which suppresses the inherent vowel. Conjuncts are formed using **virama + Zero-Width Joiner (ZWJ, U+200D)** for *yansaya*, *rakāransaya*, and *rēpaya* — unlike Devanagari, where the ZWJ is optional, in Sinhala it is mandatory and visibly affects rendering (Ishida, no date) [F]. Several vowel signs (ේ ො ෝ ෞ) decompose under Unicode Normalization Form D into two code points and recompose under NFC, so any pipeline must enforce NFC at every boundary or risk silent equality failures (The Unicode Consortium, 2024) [S].

The orthographic distinction between **śuddha** (pure, ~20 native consonants) and **miśra** (mixed, including aspirates ඛ ඝ ඡ ඣ ඨ ඪ ථ ධ ඵ භ, sibilants ශ ෂ, palatal nasal ඥ, vocalic-r ඍ ෘ, and visarga) is the orthographic locus of Sanskrit-derived lexis in Sinhala (Gair, 1998). Modern colloquial Sinhala does not phonemically distinguish aspirates from non-aspirates, but the miśra letters remain orthographically obligatory in tatsama (Sanskrit-loan) spellings — exactly the register of the Ayurvedic pharmacopoeia.

### 2.3 Diglossia and lexical strata

Sinhala exhibits classical **diglossia** in Ferguson's (1959) sense, with substantial grammatical differences between literary and colloquial registers including subject-verb agreement (Gair, 1968). Paolillo (1997) [S] argues that the variation is continuous rather than strictly two-pole. Three lexical strata are distinguished by Sri Lankan grammarians and by the NLP-relevant Mishra-Sinhala signal:

- **Tatsama** — Sanskrit terms borrowed unchanged into Sinhala script. By Poplack's (1980) [S] morphosyntactic-integration criterion these are **integrated borrowings** rather than code-switches: they are written in one script and conform to Sinhala grammar.
- **Tadbhava** — Sanskrit-origin terms phonologically nativised over time (e.g. *deḷum* < Sanskrit *dāḍima*, "pomegranate").
- **Deśya** / **eḷu** — native Sinhala vocabulary with no Sanskrit ancestry.

For the medical register a fourth category is operationally relevant: **colonial loans** (Portuguese, Dutch, English, Tamil) for plants introduced through colonial-era commerce (Senaratne, 2009) [S].

### 2.4 Sinhala in NLP classification frameworks

Joshi *et al.* (2020) [F] propose a six-class taxonomy of language-resource availability (class 0 "Left-Behinds" to class 5 "Winners"); Sinhala is widely cited as **class 1 ("The Scraping-Bys")**, alongside Nepali, Igbo and Zulu — though the per-language assignment table was not directly verifiable from the primary source in this pass and rests on the paper's published `lang2tax` companion data [S]. The classification captures the asymmetry between Sinhala's modest raw-text presence (Common Crawl, OSCAR, mC4) and its near-absent labelled NLP data. Ranathunga and de Silva (2022) [S] sharpen this position with a quantitative comparison across multiple Indic languages, showing Sinhala lagging Hindi/Tamil/Bengali on every measured axis.

The Universal Dependencies treebank for Sinhala (UD_Sinhala-STB; Liyanage and Sarveswaran, 2023) [F] contains only 100 sentences (880 tokens), making it one of the smallest treebanks in the UD ecosystem; this effectively rules out supervised training on UD-Sinhala labels. Equally consequential, Sinhala is **excluded from the entire AI4Bharat ecosystem** — IndicBERT (Kakwani *et al.*, 2020) [S], IndicTrans2 (Gala *et al.*, 2023) [F], MuRIL (Khanuja *et al.*, 2021) [S], and the BPCC parallel corpus — because Sinhala is not a constitutionally scheduled language of India (AI4Bharat, no date) [F]. It is, however, included as a low-resource language in FLORES-200 and NLLB-200 (Costa-jussà *et al.*, 2022) [S].

### 2.5 The state of Sinhala NLP

The canonical survey of Sinhala NLP is de Silva (2019, rev. 2024) [F], a living document published as arXiv:1906.02358 and maintained by the University of Moratuwa NLP group. The Sinhala-NLP ecosystem clusters around three groups: the University of Moratuwa CSE department (Ranathunga, de Silva, Dias), the University of Colombo School of Computing Language Technology Research Lab (Weerasinghe, Pushpananda, Liyanage), and a smaller international diaspora (Ranasinghe at Lancaster).

A representative narrative of progress:

- **Foundations, 2014–2018.** Rule-based and statistical work on POS tagging and morphology (Fernando *et al.*, 2016) [S], the first WordNet attempt (Wijesiri *et al.*, 2014) [S], and the first SMT system for Sinhala–Tamil (Si-Ta; Ranathunga *et al.*, 2018) [S].
- **Neural turn, 2018–2021.** FastText vectors and the canonical evaluation establishing 300-dimensional fastText as the strongest static-embedding option, on an analogy set of 27,382 pairs and a relatedness set of 345 pairs (Lakmal *et al.*, 2020) [F]. Sinhala enters FLORES-101 (Guzmán *et al.*, 2019) [S]. On a four-class news-comment sentiment task, a stacked three-layer BiLSTM reaches F1 = 59.42 % (Senevirathne *et al.*, 2020) [F]. *(A frequently-cited higher figure of ≈84.6 % belongs to a separate binary-classification study using sentence-state LSTMs and should not be conflated with the four-class result.)*
- **XLM-R/SinBERT era, 2021–2024.** Dhananjaya *et al.* (2022) ["BERTifying Sinhala"] [S] release SinBERT-small and SinBERT-large and benchmark XLM-R (Conneau *et al.*, 2020) as the strongest multilingual baseline for Sinhala. Ranasinghe *et al.* (2024) [S] release SOLD/SemiSOLD for offensive-language detection.
- **Decoder LLMs, native benchmarks, domain corpora, 2024–2026.** SinLlama (Aravinda *et al.*, 2025) [F], the first decoder LLM with explicit Sinhala adaptation, is built by continual pre-training of Llama 3-8B on a cleaned ~10-million-item Sinhala corpus, after which it outperforms both the base and instruct variants of Llama 3-8B on three text-classification tasks. SinhalaMMLU (Pramodya *et al.*, 2025) [F] introduces a benchmark of over 7,000 native-curriculum MCQs across 30 subjects and 6 domains, on which Claude 3.5 Sonnet leads at 67 % and GPT-4o at 62 % average accuracy, with model performance collapsing on culturally-rich domains such as the humanities. Surya OCR is benchmarked zero-shot on a 6,969-pair synthetic Sinhala set with CER 0.76 % / WER 2.61 % (Jayatilleke and de Silva, 2025) [F]. SiPaKosa (Gururatne and Jayatilleke, 2026) [F] releases a 9.25 M-word Sinhala-Pali Buddhist corpus — the closest classical-register parallel to Ayurvedic Sinhala.

Notably, **no medical or Ayurvedic Sinhala NLP work has been published** as of mid-2026; the closest adjacent specialist registers are Buddhist canonical (SiPaKosa) and legal (SinhaLegal). This gap is the principal opportunity the present project addresses.

---

## 3. The Domain: Traditional Ayurvedic Medicine

### 3.1 Comparable knowledge graphs

Four published knowledge graphs of traditional medicine are directly comparable to the present work:

- **GRAYU** (Joshi *et al.*, 2026) [S] is a graph-database integration of Ayurvedic formulations, medicinal plants, phytochemicals and diseases — 157,000 nodes / 1.52 million relationships — and notably includes an explicit disclaimer that no plant–metabolite–disease link is assigned mechanistic meaning and that no therapeutic efficacy is implied. This wording is the de facto template for responsible publication.
- **AyurKOSH** (Mirasdar *et al.*, 2026) [S] is an IEEE DataPort release providing machine-readable Ayurvedic terminology including the Rasa-Guṇa-Vīrya-Vipāka-Karma pharmacological axes.
- **HerbKG** (Lin *et al.*, 2022) [S] mines a herb–chemical–disease–gene graph (53,000 relations) from 500,000 PubMed abstracts using a two-stage deep-transfer-learning framework.
- **Āyurjñānam** (Terdalkar, 2023) [S] is a small, careful OWL-based KG of the Dhanyavarga chapter (~410 nodes / 764 edges) representing a quality-focused alternative to large noisy graphs.

These four together justify our schema's tight typology (~10 node types) and demonstrate that bespoke schemas built from the comparable literature are accepted practice. None covers Sri Lankan Ayurveda specifically.

### 3.2 Ontology standards

No comprehensive ontology for Ayurveda exists in OBO Foundry (Smith *et al.*, 2007; OBO Foundry, no date) [F]. The authoritative artefacts are *terminology code systems* rather than full property/edge ontologies:

- **WHO ICD-11 Traditional Medicine Module 2** (World Health Organization, 2025) [S] specifies 529 codes across 18 chapters for Ayurveda, Siddha and Unani; its first official release on the ICD-11 browser was in February 2025.
- **NAMASTE Portal** (Ministry of AYUSH, 2025) [S] provides 1,941 Ayurveda-Siddha-Unani morbidity codes mapped to ICD-11 TM2 — an India-government-maintained crosswalk.
- **SNOMED-CT AYUSH extension** (Centre for Research in Ayurvedic Sciences and the National Resource Centre for EHR Standards, ongoing) [S] adds clinical Ayurveda terms to the SNOMED-CT international release.

For non-traditional ontologies that bind directly to our schema:

- **ChEBI** (Hastings *et al.*, 2013) [S] supplies chemical IRIs and a *toxin* role class — directly usable for our `Phytochemical` and `Mineral` nodes.
- **Plant Ontology (PO)** (Cooper *et al.*, 2013) [S] provides plant-anatomy term IRIs for our `PlantPart` node type.
- **POWO** (Royal Botanic Gardens, Kew, no date) [F] provides IPNI LSIDs for plant species and resolves nineteenth-century botanical names to modern accepted forms.

The verdict is that bespoke schema structure is justified at the ontology core, but external IRI bindings (Disease → ICD-11 TM2, Plant → POWO, Phytochemical → ChEBI, PlantPart → PO) are mandatory rather than optional.

### 3.3 Measurement and quantity representation

The **QUDT** ontology (QUDT.org, 2026) [F] is the actively-maintained authority on units of measure, currently at v3.1.4 (April 2026) with approximately 2,900 unit resources and an extensible model based on `qudt:conversionMultiplier` and `qudt:conversionOffset` to an SI base. QUDT already ships apothecary units (`unit:GRAIN`, `unit:DRAM`) and troy units, but does not cover South-Asian traditional units such as *tola*, *pala*, *māṣa*, or *kalañcu*. Rijgersberg, van Assem and Top (2013) [S] introduced **OM** as a competing units ontology with cleaner quantity-unit grouping; QUDT's wider tooling ecosystem makes it the practical default for ontology-aligned dosage representation.

For quantity extraction from text, the **Comprehensive Quantity Extractor (CQE)** (Almasian *et al.*, 2023) [S] provides an open-source value+unit+concept extractor — relevant for our `quantity_text → quantity_grams` parsing — though the authors flag clinical text as noisy and recommend domain validation.

### 3.4 Pharmacovigilance and heavy-metal toxicity

The literature on heavy-metal contamination of Ayurvedic preparations is unambiguous. The headline empirical studies are Saper *et al.* (2004) and Saper *et al.* (2008) [F], both in *JAMA*. The 2004 study found heavy metals (lead, mercury and/or arsenic) in **14 of 70 (20 %)** Boston-area herbal medicine products; the 2008 follow-up found toxic metals in **20.7 %** of US- and Indian-manufactured Ayurvedic medicines purchased over the Internet, with some samples yielding blood-lead-elevating doses.

The 2024 review in *Chonnam Medical Journal* (Sikder, 2024) [F] consolidates the subsequent literature, reporting **at least 55 documented heavy-metal-intoxication cases linked to Ayurvedic products since 1978**; one cited survey found heavy metals in 42 of 43 tested remedies. A recent paediatric lead-poisoning case linked to Ayurvedic medicine was reported by Yu *et al.* (2025) [S]. The mechanistic debate over *bhasma* (calcined metal preparations) — proponents argue nanoparticulate forms are non-toxic; clinical evidence shows elevated blood lead in some cases — is reviewed in the same article. *(A "~40 % of rasa-śāstra products" figure cited in some secondary summaries could not be located verbatim in the primary and is omitted.)*

For computational pharmacovigilance, the relevant resources are:

- **HTINet2** (Zhang *et al.*, 2024) [F] — an open-source herb-target KG with 74,529 entities and 1.92 M triples, primarily Traditional Chinese Medicine.
- **NP-KG** (Bhasuran and Lever, 2025) [F] — a 1.09-million-node natural-product–drug interaction KG built on 14 OBO ontologies with ComplEx embeddings for interaction prediction.
- **NPASS 3.0** (Zhao *et al.*, 2026) [S] — 204,000 natural products with 34,975 quantitative toxicity records and ADMET annotations.
- **DrugBank 6.0** (Knox *et al.*, 2024) [F] — the canonical schema for drug–drug interactions with severity, evidence-level, and management properties.

The ethical position the literature converges on is GRAYU's wording (Joshi *et al.*, 2026): a traditional-medicine KG should *digitise* what classical texts assert, flag heavy-metal-bearing preparations, and explicitly disclaim therapeutic efficacy. The implication for the present project is that an explicit `SafetyFlag` node class and a verbatim disclaimer header are not optional polish but a minimum-bar ethical obligation.

### 3.5 The global landscape of traditional-medicine digitisation

The international landscape of traditional-medicine digitisation is dominated by two national ecosystems pursuing very different paradigms, with a global natural-product chemistry layer underneath and a long tail of regional efforts.

**China** has the densest ecosystem: a two-decade accretion of network-pharmacology databases organised around *herb → ingredient → protein-target → disease* linkage for drug discovery — TCM-ID (Chen *et al.*, 2006) [F], TCMID (Xue *et al.*, 2013) [F], TCMSP (Ru *et al.*, 2014) [F], ETCM (Xu *et al.*, 2019) [F], SymMap (Wu *et al.*, 2019) [F], HERB (Fang *et al.*, 2020) [F], BATMAN-TCM 2.0 (Kong *et al.*, 2024) [S], and TCMBank (Lyu *et al.*, 2023) [S] — augmented by a newer wave of classical-text knowledge graphs such as the *Shanghan Lun* (Treatise on Febrile Diseases) KG (Yan *et al.*, 2022) [S]. Contrary to a common assumption that these databases have decayed, a 2024 critical assessment (Oprea *et al.*, 2024) [F] found the major reviewed TCM databases all currently live; the real problem is minimal cross-database harmonisation, not link rot.

**India** is the clear leader for Ayurveda-as-such and the most directly comparable to the present project. It spans defensive transcription — the **Traditional Knowledge Digital Library** (TKDL; CSIR, no date) [S], approximately 500,000 formulations transcribed and classified for patent-office access but explicitly *not open* — through terminology standardisation feeding the WHO (the NAMASTE Portal → ICD-11 TM2 crosswalk; Ministry of AYUSH, 2025), phytochemical atlases (IMPPAT 2.0; Vivek-Ananth *et al.*, 2023 [F]; OSADHI; Mohanraj *et al.*, 2022 [S]), to genuine knowledge graphs (GRAYU, 157,010 nodes / 1,520,687 edges, Joshi *et al.*, 2026 [F]; AyurKOSH, Mirasdar *et al.*, 2026; and the text-derived Āyurjñānam over the *Bhāvaprakāśa-nighaṇṭu*, Terdalkar, 2023). India also hosts the **WHO Global Centre for Traditional Medicine** (Jamnagar, established 2022) [S].

**Korea and Japan** are smaller and target-prediction-oriented: KIOM ontologies and the OASIS literature portal in Korea, and KampoDB (Sawada *et al.*, 2018) [F] in Japan, covering 42 Kampo formulas and ~1,230 compounds. **Africa** contributes regional natural-compound chemistry databases — SANCDB (Hatherley *et al.*, 2015) [F], NANPDB/EANPDB, AfroDb — rather than formula KGs. A cross-cutting **global natural-product layer** supplies the chemical backbone most KGs reuse: NAPRALERT (legacy, paywalled), Dr Duke's Phytochemical and Ethnobotanical Databases (open; US Department of Agriculture), COCONUT (Sorokina *et al.*, 2021) [S], LOTUS (Rutz *et al.*, 2022) [S], and CMAUP (Hou *et al.*, 2024) [S].

A decisive structural observation: **almost every initiative above — including the Indian knowledge graphs — is *compiled* from pre-existing curated databases or official pharmacopoeias, not *derived* from raw OCR of source texts**. The two exceptions, Āyurjñānam and the Shanghan Lun KG, build a KG from a single classical text via *manual* annotation. The present project is distinctive in deriving structured records *automatically* from OCR-noisy text where no machine-readable source exists.

**Sri Lanka sits at the very bottom of the maturity curve.** Exhaustive search located only: ethnobotanical survey papers, browsable plant catalogues (the two located Sri Lankan plant-database domains were unreachable during the survey, consistent with offline or non-machine-readable catalogues), and prototype ML/AR mobile applications such as "Smart Hela Wedakama" (2024) [S] for plant identification and Sinhala-prescription image recognition. No machine-readable, structured corpus of Sri Lankan traditional-medicine **formulas** — and certainly no knowledge graph — was found. Even the pan-South-Asian resources (TKDL, GRAYU, IMPPAT) draw exclusively on Indian sources. On the available evidence it is therefore well-supported to claim that the present project is the **first machine-readable / knowledge-graph representation of the Ayurvedic Pharmacopoeia of Sri Lanka** (with the prudent hedge "first openly-described", since TKDL's closed contents cannot be fully audited).

The closest published analogues to the present work, and the way to position against each, are:

| Analogue | What it is | How we differ |
|---|---|---|
| **Āyurjñānam** (Terdalkar, 2023) | KG from a single classical Sanskrit nighaṇṭu via manual annotation | We automate extraction from OCR-noisy Sinhala formula tables rather than annotating by hand |
| **Shanghan Lun KG** (Yan *et al.*, 2022) | KG from one canonical medical text (disease–syndrome–symptom–method–formula) | We do the same for a Sinhala pharmacopoeia, at larger formula scale, with a cross-lingual resolver |
| **GRAYU** (Joshi *et al.*, 2026) | SOTA Ayurvedic formulation KG, 157 K nodes | Our aspirational target schema; but GRAYU *compiles* from existing DBs whereas we *create* records where none exist |
| **IMPPAT 2.0** (Vivek-Ananth *et al.*, 2023) | Indian medicinal-plant phytochemistry atlas | We are the Sri Lankan, text-derived counterpart |
| **AyurKOSH** (Mirasdar *et al.*, 2026) | Machine-readable Rasa-Guṇa-Vīrya-Vipāka-Karma terminology | Closest schema analogue for our pharmacological-property axes |

The positioning implication is that the project's defensible contribution is the **foundational resource** — the first structured Sinhala formula corpus plus the Sanskrit-bridge resolver — on which a GRAYU-style KG can later be built, with interoperability achieved by mapping diseases to ICD-11 TM2 / NAMASTE, plants to POWO, and chemicals to ChEBI so that the Sri Lankan KG becomes comparable to the Indian and Chinese ecosystems.

---

## 4. The Engineering Pipeline

This section reviews the literature in the order the pipeline executes: layout analysis, OCR, normalization, lexical bridging, sandhi handling, entity linking, schema-constrained extraction, KG construction, validation, and KG embeddings.

### 4.1 Document layout analysis

The 2024–2026 state of the art in document layout has moved firmly to layout-aware transformers: **LayoutLMv3** (Huang *et al.*, 2022) [S], **DocFormer** (Appalaraju *et al.*, 2021) [S], **TableFormer** (Nassar *et al.*, 2022) [S], and the table-structure-recognition model **TFLOP** (Lee *et al.*, 2024) [S] for complex tabular extraction. For real-time use, **DocLayout-YOLO** (Wang *et al.*, 2024) [S] reaches CPU-deployable inference with YOLOv10 architecture.

For a single-print-run, fixed-column source these models are demonstrably overkill: their value emerges on heterogeneous multi-document corpora with variable layouts. Hand-tuned column-zone heuristics over Google-Cloud-Vision-style word-level bounding-box outputs remain a defensible choice for a single book (Surya in Jayatilleke and de Silva, 2025 [F] bundles layout, reading-order and table recognition with its OCR — a more useful upgrade than LayoutLM for our scale).

### 4.2 Optical Character Recognition for Sinhala

The decisive benchmark for printed Sinhala is Jayatilleke and de Silva (2025) [F]. Their zero-shot comparison of six engines on a 6,969-pair synthetic Sinhala/Tamil dataset placed **Surya** (Paruchuri, 2024) [S] at character-error-rate (CER) 0.76 % / word-error-rate (WER) 2.61 %, beating Google Cloud Vision (WER 7.67 %), Document AI, Subasa OCR (a Tesseract-fine-tune for Sinhala), Tesseract 5, and EasyOCR. Surya's models are also bundled with layout, reading-order and table recognition — collapsing several pipeline stages.

For OCR *post-correction* in low-resource scripts, the 2024–2025 consensus is byte-level seq2seq. ByT5-based OCR post-correction reduces CER by approximately 56 % without gold pairs (Maheshwari *et al.*, 2024) [S], and the **RoundTripOCR** method (Vyawahare *et al.*, 2024) [S] shows how to synthesize error/correct pairs for Brahmic scripts via round-trip MT. A Sanskrit-specific OCR-post-correction ByT5 (`chronbmm/sanskrit-byt5-ocr-postcorrection`; Nehrdich *et al.*, 2024) [F] is directly relevant.

Real-world Sinhala scans present an additional challenge documented in Sri Lankan engineering practice (Vasantharajan and Thayasivam, 2022) [S]: pre-2010 publications often use legacy non-Unicode fonts (DL-Manel, FM Abhaya, Kaputa) with private code-point mappings that defeat off-the-shelf OCR. The widely-cited IskoolaPota mis-decoding issue (Help Centre, no date; Ishida, no date) [F] is not solved by any current OCR engine. This justifies the present project's experimental PDF-direct text-extraction path (`pdf_pipeline/`) as a deterministic alternative to OCR error.

### 4.3 Tokenisation and normalisation

Tokenisation of Sinhala must occur at the **akṣara** (extended grapheme cluster) level, not at the Unicode code-point level (The Unicode Consortium, 2024) [S]. The Python ecosystem provides two options: `sinling` (Senarath, 2020) [F], with a last release in November 2020, and the more recent `SLTK` (Buddhilive, 2025) [F] which implements Grapheme-Pair-Encoding (Sennrich, Haddow and Birch, 2016) [S] adapted to Sinhala graphemes. Both preserve conjuncts that naïve codepoint tokenisation would shatter.

For multilingual tokenisation that respects Sinhala, **Aksharamukha** (Rajan, 2024) [F] provides lossless transliteration between Sinhala and 121 other scripts, including IAST and Devanagari — the basis of any Sinhala–Sanskrit lexical bridge.

Normalisation at the Unicode level requires NFC (Canonical Composition) — the four circumgraph vowels ේ ො ෝ ෞ have two-codepoint decomposed forms that compose under NFC (The Unicode Consortium, 2024; Ishida, no date). Failure to NFC-normalise produces the kind of silent equality failures the project documented (24 % NFC mismatch on raw formula names in the source corpus).

### 4.4 Cross-lingual lexical bridging: Sinhala-Sanskrit

The cross-lingual lexical bridge from Sinhala to Sanskrit is a core component of the present project, and the literature search confirms it is computationally **novel**: no published system performs this bridging. The closest related work is in *xMEN* (Borchmann *et al.*, 2023) [S; JAMIA Open 2025], a cross-lingual medical-entity-normalisation framework that explicitly falls back to English aliases when target-language aliases are sparse — structurally the same pattern as the present project's Sinhala-via-Sanskrit-via-Monier-Williams cascade. xMEN provides the closest published analogue.

The reference Sanskrit dictionary remains Monier-Williams (1899) [S], accessed programmatically via the Cologne Digital Sanskrit Dictionaries (CDSL; Sanskrit Library, ongoing) [S] through the `pycdsl` library (Terdalkar, ongoing) [F]. CDSL also covers Apte (1957) [S], Śabdasāgara and Vacaspatyam — Classical-period coverage that complements Monier-Williams's nineteenth-century Vedic-Sanskrit focus.

The orthographic signal we exploit to classify Sinhala tokens as tatsama vs other is the **miśra Sinhala** signal discussed in §2.3 — to our knowledge no computational classifier of this signal has been published, although it is a standard descriptive feature of Sinhala grammar (Gair, 1998).

### 4.5 Sandhi and Sanskrit morphological analysis

For Sanskrit morphological analysis, the recent SOTA is **ByT5-Sanskrit** (Nehrdich *et al.*, 2024) [F], a byte-level T5 jointly performing sandhi-splitting, lemmatisation, morphological tagging and dependency parsing. On the published benchmarks ByT5-Sanskrit beats TransLIST (Sandhan *et al.*, 2022) [S] by **+8.8 perfect-match points on the Hackathon segmentation benchmark** (94.29 vs 85.47); on the **SIGHUM** benchmark the two are effectively level (ByT5 93.83 vs TransLIST 93.97) (Nehrdich *et al.*, 2024) [F]. *(The earlier survey draft incorrectly paired the +8.8 gain with the SIGHUM number; the gain is on the Hackathon set.)* The model is distributed on HuggingFace as `chronbmm/sanskrit5-multitask` (581.7 M parameters, T5 architecture) [F], wrapped by `dharmamitra-sanskrit-grammar` on PyPI (Dharmamitra, ongoing) [S].

The previously canonical tool, `sanskrit_parser` (Goyal and Huet, 2016) [S], is a wrapper around the Sanskrit Heritage Engine. It produces SOTA-level output for vowel-junction sandhi but leaks memory at scale — a well-known property that motivated the present project's memory-isolated-subprocess pattern (`RLIMIT_AS` + `SIGALRM` + worker recycling). Replacing Heritage with ByT5-Sanskrit eliminates this engineering hack entirely.

Other Sanskrit tools worth noting: **SanskritShala** (Sandhan *et al.*, 2023) [S], a neural toolkit for segmentation, morphological analysis, and dependency parsing; **CharSS / LEVOS** (Yenduri *et al.*, 2024) [S], a character-level Transformer for Sanskrit word-segmentation; and the **Sandarśana** survey (Sandhan *et al.*, 2025) [S], the most recent comprehensive review of Sanskrit computational infrastructure.

### 4.6 Entity linking and normalisation

The literature on biomedical entity linking (EL) splits into two major paradigms: dictionary-based (MetaMap and MetaMapLite; Aronson, 2017 [S]; scispaCy's UMLS linker; QuickUMLS; Soldaini and Goharian, 2016 [S]) and neural (SapBERT; Liu *et al.*, 2021a [F]) (BioSyn; Sung *et al.*, 2020 [S]) (KRISSBERT; Zhang *et al.*, 2022 [S]) (autoregressive: GENRE; De Cao, Aziz and Titov, 2021 [S]).

A comprehensive evaluation by Kartchner *et al.* (2024) [F] confirms that neural EL (SapBERT) beats dictionary EL (MetaMap) by ~6.9 percentage points on MedMentions ST21PV (Mohan and Li, 2019) [S] and ~5.5 points on BC5CDR (Li *et al.*, 2016) [S] @1 — though the gap narrows to ~2.3 points on MedMentions Full. They also report ~82 % *mention overlap* between train and test on MedMentions Full, a confound that inflates apparent neural performance. For closed, curated vocabularies the precision gap narrows further.

The **cross-lingual SapBERT** (Liu *et al.*, 2021b) [F] extends self-alignment pretraining to 10 languages: Chinese, English, Finnish, German, Japanese, Korean, Russian, Spanish, Thai and Turkish. **No Indic language is included**, and Sinhala is therefore unvalidated for SapBERT-class neural EL. The present project's dictionary-based EL is consequently defensible on precision, auditability, and zero-hallucination, with neural EL retained only as an optional second-oracle re-ranker for residual unresolved mentions.

Specific patterns worth borrowing from the EL literature for our pipeline:

- **Explicit NIL detection** (Ruas and Couto, 2023 — NILINKER) [S] — emit `{status: NIL, mention, char_span}` rather than silently dropping unresolved mentions.
- **Composite-mention decomposition** (Wei *et al.*, 2015 — SimConcept) [S] — directly applicable to Ayurvedic compounds (*Triphalā* → three constituent fruits; *Trikaṭu* → three pungents).

A related question is whether **cross-lingual NER transfer** could supply a neural second oracle. The transfer *machinery* is mature — projection-based methods now match or beat zero-shot model transfer for low-resource targets (Garcia-Ferrero *et al.*, 2025 — projection-based transfer; Chen *et al.*, 2023 — contextual label projection) [F/S]. But the only labelled Sinhala NER data — the multi-way parallel English-Tamil-Sinhala corpus of 3,835 government-document sentences with CoNLL tags (Senevirathne *et al.*, 2024) [F] — is **fatally domain-mismatched** for Ayurvedic ingredients, doses and preparation verbs, and cross-lingual transfer degrades sharply when source and target share few entity chunks. The conclusion is that news/government Sinhala NER is *not* usefully transferable to our register; if a neural oracle is wanted, the right path is label projection from an English/Hindi *herbal/Ayurvedic* NER source, not reuse of the government corpus.

### 4.7 Schema-constrained information extraction

The 2025 design paradigm in biomedical information extraction (IE) is **schema-constrained extraction**: define a target schema first as a hard constraint, then any extractor — rule-based, CRF, or LLM — produces only schema-valid triples. Invalid triples are rejected at emission with their source span logged. The principal sources are:

- **RELATE** (Li *et al.*, 2025) [S], which aligns LLM extractions to ontology constraints in biomedical abstracts.
- **ODKE+** (Wang *et al.*, 2025) [F], which runs pattern-based and LLM extractors in parallel, generates per-type "ontology snippets" as hard schema constraints, grounds every triple against its source span and rejects ungrounded ones, ingesting 19 million high-confidence facts at **98.8 % precision**. *(A "35 % hallucination reduction" figure that appeared in early secondary summaries could not be located in the primary and has been dropped.)*
- **Schema-Constrained AI for Auditable Biomedical Evidence Extraction** ("From Chaos to Clarity"; Wang *et al.*, 2026) [F], which articulates the schema-constrained, controlled-vocabulary, evidence-gated, sentence-level-provenance framing marketed explicitly on **auditability**.
- The **2025 LLM-empowered KG construction survey** (Zhong *et al.*, 2025) [S] reviews 60+ papers and identifies schema-constrained generation as the field's emerging standard.

For *neural* span/relation extraction whose output can be checked against the schema rather than substituted for it:

- **GLiNER** (Zaratiana *et al.*, 2024) [S] is the generalist lightweight NER backbone using BERT-style encoders for zero-shot custom-label NER.
- **GLiNER2** (Stepanov *et al.*, 2025) [F], with 198,800 downloads on HuggingFace, extends GLiNER to relation extraction, structured/JSON extraction, and intent classification. Critically for this project, GLiNER2 supports **only English, French and Spanish** — Sinhala-script input is unsupported.
- **GLiREL** (Maciejewski *et al.*, 2025) [S] applies the GLiNER paradigm specifically to zero-shot relation classification.
- **REPaL** (Yi *et al.*, 2024) [S] performs definition-only zero-shot relation extraction by having an LLM synthesise training seeds from the relation's natural-language definition.

For distant-supervised low-resource NER — directly relevant to bootstrapping a CRF on our 11,007 already-structured ingredient mentions — the principled framing is **Snorkel-style programmatic weak supervision** (Ratner *et al.*, 2017) [S], in which the rule extractor and the ML extractor are two labelling functions whose agreement/disagreement is consumed by a label model.

### 4.8 Knowledge-graph construction

The four-node typology adopted in the present project (Plant, Phytochemical, Disease, Formulation) follows the synthesis pattern documented in GRAYU (Joshi *et al.*, 2026), HerbKG (Lin *et al.*, 2022), and AyurKOSH (Mirasdar *et al.*, 2026), augmented by Mineral, AnimalOrigin (for the *jāntava* substance class — see §3.4), PlantPart, PreparationType, Route, Symptom and PharmacologicalProperty to reach 11 node types and 13 edges.

The KG is serialised in four interoperable views (Bizer, Heath and Berners-Lee, 2009) [S]: Neo4j Cypher for canonical write, JSON-LD (Sporny *et al.*, 2020) [S] for linked-data publication, RDF/Turtle (Beckett *et al.*, 2014) [S] for semantic-web tooling, and JSONL for streaming IE pipelines.

### 4.9 Knowledge-graph validation

The methodological backbone of KG validation is Zaveri *et al.* (2016) [F], whose 18-dimension Linked-Data quality framework — grouped into four categories (intrinsic, contextual, representational, accessibility) — provides the conceptual map. The intrinsic trio (accuracy, completeness, consistency) is the spine of our validator.

For the *implementation* of validation:

- **SHACL** (Knublauch and Kontokostas, 2017) [S] is the W3C Recommendation for constraint validation over RDF, with `pySHACL` (RDFLib, ongoing) [S] as the canonical Python implementation.
- **ProVe** (Amaral *et al.*, 2024) [S] is the canonical automated provenance-verification pipeline for KGs (87.5 % accuracy / 82.9 % macro-F1 on Wikidata text-rich subset).
- **ROBOT** (Jackson *et al.*, 2019) [S] is the OBO Foundry's biomedical-ontology workflow QA tool — the inspiration for our "validation report = categorised SPARQL queries" pattern.

For inter-annotator agreement on small skewed samples (the regime of our 100-item expert spot-check), Cohen's κ (Cohen, 1960) [S] is widely used but suffers the well-documented prevalence/kappa paradox under class imbalance. The IAA-metric selection survey (Sarsa *et al.*, 2026) [F] recommends **Gwet's AC1** (Gwet, 2008) [S] for our regime and mandates bootstrap confidence intervals at small sample sizes.

For LLM-as-judge — a candidate fourth validation layer — the recent empirical literature is sobering. Adam and Kliegr (2025) [F] benchmark a *grounded* LLM judge on biomedical BioRED-Verify and report **88 % precision but only 44 % recall**, concluding that "the method requires human oversight." Kim *et al.* (2024) [S] demonstrate that single-shot LLM judgments are unreliable even at temperature 0, requiring multi-sample consistency checks. The implication is that LLM-judge can serve as a triage / error-flagging layer but cannot certify correctness.

For biomedical eval norms specifically, BioRED / BioCreative VIII (Luo *et al.*, 2024) [S] establishes triple-level precision/recall/F1 plus separate entity-linking accuracy as the standard report split, and reports inter-annotator agreement (~78 % on relations) as the practical ceiling against which extractor precision should be framed.

A distinct problem is that the present KG has **no complete gold reference**. The statistically-defensible practice here is not to claim precision/recall against a non-existent gold standard but to **estimate triple-level precision from a human-judged sample with an explicit interval**, and to **estimate recall by capture–recapture**. Gao *et al.* (2019) [F] is the canonical method for sampling KG triples for an accuracy estimate with statistical guarantees (two-stage weighted cluster sampling, up to 60 % fewer annotations than random); Marchesin and Silvello (2025) [F] refine it with Bayesian credible intervals that are better-behaved than frequentist confidence intervals at small *n* — directly relevant to our ~100 expert judgements. Knowledge Vault (Dong *et al.*, 2014) [F] is the precedent for reporting calibrated triple probabilities under a Local Closed-World Assumption rather than a gold standard. For **recall**, the capture–recapture / Lincoln–Petersen estimator — validated in biomedical systematic-review-completeness work — estimates the unknown true total from the overlap of two independent extractors (here, the v3 vs. v4 pipelines, or pipeline vs. a small manual pass), yielding an estimated recall with a confidence interval. The recommended report is therefore: stratified-random precision sample (stratified by edge type, since fill rates vary from ~21 % to near-100 %), a Bayesian credible interval on precision, inter-judge agreement on a doubly-judged subset, and a capture–recapture recall estimate.

### 4.10 Knowledge-graph embeddings and link prediction

Knowledge-graph embedding (KGE) methods — TransE (Bordes *et al.*, 2013) [S], RotatE (Sun *et al.*, 2019) [S], ComplEx (Trouillon *et al.*, 2016) [S] — and their graph-neural-network successors are trained on benchmarks such as FB15k-237 (Toutanova and Chen, 2015) [S] with ~14,500 entities and WN18RR (Dettmers *et al.*, 2018) [S] with ~41,000 entities. The present KG (4,089 nodes) is an order of magnitude below this scale.

The trustworthiness of KGE under the open-world assumption is critical. Safavi, Koutra and Meij (2020) [F] show that ranking metrics (Hits@k, MRR) are misleading because models can rank true triples highly while assigning high scores to nonsensical triples, and that closed-world calibration techniques break down under the open-world assumption that governs traditional-medicine KGs. The implication is that KG completion / link prediction should be scoped explicitly as exploratory hypothesis-generation rather than as part of the present project's research claims — particularly for predicted herb→disease "treats" edges, which carry clinical-misleading risk (Sikder, 2024).

### 4.11 Formal-language framing of the extraction pipeline

The project's extraction architecture has a precise theoretical home worth naming explicitly. The tabular Stage-3 extractor — a state machine over x-coordinate column zones — is a **cascaded finite-state transducer** in the FASTUS tradition (Hobbs *et al.*, 1997) [F], the foundational demonstration that finite-state methods are sufficient for information extraction; its operation over a regular page layout also places it in the **wrapper-induction** lineage for semi-structured sources (Kushmerick, 2000) [S], albeit hand-built rather than learned. The planned prose extractor's sentence templates form a **CFG / PEG grammar**.

The modern bridge — and a clean novelty framing for the determinism claim — is **grammar-constrained decoding**. Willard and Louf (2023) [S] reformulate constrained generation as transitions over a finite-state machine (the Outlines library), and XGrammar (Dong *et al.*, 2024) [S] implements byte-level pushdown-automaton CFG-constrained decoding now standard in vLLM/SGLang. The present pipeline can therefore be positioned as the **non-neural limit of the same formal object** that the neural community now retrofits onto LLMs to guarantee schema-valid output: we obtain the identical structural guarantee (output is provably within the schema) with full auditability and zero hallucination surface, rather than bolting an FSM/PDA constraint onto a probabilistic generator after the fact.

---

## 5. Cross-Cutting Concerns

### 5.1 Code-mixing and register variation

The lexical strata of Sinhala (tatsama, tadbhava, deśya; §2.3) are best framed for the linguistic literature as **borrowing-layer stratification under diglossia** (Gair, 1998; Ferguson, 1959) rather than as code-switching: by Poplack's (1980) [S] morphosyntactic-integration criterion, tatsama terms are integrated into Sinhala grammar in one script and qualify as established borrowings, not code-switches. However, the *computational task* of classifying tokens by lexical stratum (the present project's Module A) is formally **word-level language identification** — the canonical task in code-mixed Indic NLP (Solorio *et al.*, 2014) [S]. Recent code-mixed Indic NER results show domain-specific code-mixed pretraining beats monolingual encoders and outperforms LLMs (Pandey, Sinha and Singh, 2025) [S].

This dual framing — borrowing/diglossia for the linguistic claim, word-level language identification for the computational method — is the citable, defensible position for the thesis.

### 5.2 Digital humanities and computational philology

The present project is, in addition to being an NLP and KG construction project, a **digital scholarly edition** of a historical Sinhala medical text. The DH-side literature provides framings, methods, and publication venues largely orthogonal to the NLP side.

For text-encoding standards, the **Text Encoding Initiative** (Burnard, 2014) [F] provides the de facto XML standard for scholarly digital editions. Full TEI authoring is excessive for a single printed source with no manuscript-witness apparatus, but a one-shot TEI **export** of the structured corpus is low-cost and unlocks discoverability through Indic-DH projects such as **SARIT** (Hellwig *et al.*, ongoing) [F] and **GRETIL** (Kapp, ongoing) [F]. The **CITE/CTS** canonical-citation framework (Smith and Blackwell, ongoing) [F] supplies stable URN identifiers compatible with our char-span provenance scheme.

For historical text normalisation, the canonical work is Bollmann (2016) [S] and Bollmann (2019) [S], in which the spelling-variant problem is framed as a named NLP/DH sub-task with shared-task data and an established char-level seq2seq baseline. Our spelling-variant problem (ශයී / ශඨි / ශටී for the same herb) is precisely this task, and reframing it accordingly grounds the present work in an established methodology.

Comparable historical pharmacopoeia / herbal / recipe-corpus projects include **CoReMA** (Cooking Recipes of the Middle Ages; Klug, ongoing) [S], **Curious Cures in Cambridge** (Cambridge University Library, ongoing) [S], and the network-mining analysis of the *Lylye of Medicynes* by Connelly *et al.* (2020) [S]. KG construction from classical Chinese medicine — for example the Treatise on Febrile Diseases KG (Han *et al.*, 2024) [F] — provides a direct East Asian analogue.

For publication venues, the **Journal of Open Humanities Data** (JOHD; openhumanitiesdata.metajnl.com) [S] is the canonical data-paper venue for a structured release of this kind. The **Digital Humanities and NLP workshop** (DHandNLP, sites.google.com/view/dhandnlp-propor) [S] is the natural cross-disciplinary venue.

### 5.3 Reproducibility and determinism

The reproducibility literature largely targets *environment* reproducibility (containers, pinned versions) and *reporting* reproducibility (checklists) rather than byte-identical output. The canonical scaffolding is the **ACL/NLP Reproducibility Checklist**, whose 2023 analysis of 10,405 responses found that code-sharing is the single strongest lever on reproducibility scores (+8 %) (Reproducibility-in-NLP analysis, 2023) [F]; the **"Ten Simple Rules for Reproducible Computational Research"** (Sandve *et al.*, 2013) [S] and the container-specific **"Ten Simple Rules for Dockerfiles for Reproducible Data Science"** (Nüst *et al.*, 2020) [S]; and rootless scientific containers via **Apptainer/Singularity** (Kurtzer *et al.*, 2017) [S]. A workflow manager such as Snakemake or Make supplies the single-command, pinned-version guarantee.

The present project's *byte-identical output reproducibility* claim is **stronger** than the seed-based statistical reproducibility the checklist assumes — most ML reproducibility only promises statistically-similar results under fixed seeds, whereas the deterministic rule pipeline promises identical bytes. That contrast is a genuine thesis hook. It is achievable through stable sorts, `sorted(set(...))` iteration in output paths, fixed seeds where any sampling occurs, and caching of neural-model outputs once produced; it should be *verified* with a committed SHA-256 manifest of all `*_structured.json` outputs, and supported by a pinned environment (the project's zero-external-dependency core makes a Docker/Apptainer + hashed-`requirements.txt` story trivially defensible) plus a Makefile that runs the whole pp.151–500 pipeline in one command.

### 5.4 Responsible release: FAIR, CARE, and traditional-knowledge protection

Resource-documentation norms are well established: **Datasheets for Datasets** (Gebru *et al.*, 2021) [S], **Data Statements for NLP** (Bender and Friedman, 2018) [S] (particularly apt for low-resource Sinhala), the **FAIR Principles** (Wilkinson *et al.*, 2016) [S], and machine-readable **Croissant** metadata (Akhtar *et al.*, 2024) [S]. For licensing of resources derived from copyrighted source text, the comparable Sinhala precedent is **NSINA** (Hettiarachchi *et al.*, 2024) [F], released under a click-through CC-BY-SA-4.0 license that does not redistribute substantial source text.

However, the present project is a **traditional-knowledge** resource, and here the FAIR "open by default" stance is genuinely contestable. The **CARE Principles for Indigenous Data Governance** (Carroll *et al.*, 2020) [S] — Collective benefit, Authority to control, Responsibility, Ethics — were designed to sit *alongside* FAIR ("be FAIR *and* CARE"; Carroll *et al.*, 2021) [S] precisely because open-by-default ignores power and historical context. This is not abstract: the **Traditional Knowledge Digital Library** (TKDL; §3.5) is deliberately *access-controlled* despite being a documentation effort, specifically to avoid handing bio-prospectors a curated shopping list, while still functioning defensively (200+ patent claims blocked). The **2024 WIPO Treaty on Intellectual Property, Genetic Resources and Associated Traditional Knowledge** (WIPO, 2024) [S] mandates patent-applicant disclosure of TK origin and encourages (but does not require) open TK databases. Sri Lanka's own statutory framework places a duty on the Director-General of Intellectual Property to preserve traditional knowledge "for the people of Sri Lanka" (WIPO Lex, no date) [S].

The implication is that a blanket CC-BY-SA release of the *content* layer (especially full formula compositions) should be reconsidered. A defensible position reconciling FAIR and CARE is: release the **schema, code, and structure openly**, but apply **TK Labels** (Local Contexts) and consider a non-commercial or community-consent clause on the formula-composition content, framing the resource as *defensive documentation* (anti-biopiracy) rather than a commercialisable extract — and documenting the source-text copyright explicitly in the thesis ethics section.

The deeper critique literature sharpens this. The recurring finding is that defensive/documentary models such as TKDL **prevent bad patents but confer no affirmative community rights, benefit-sharing, or access control**, and can create an *access asymmetry* in which patent offices and outsiders can read the resource while the originating communities cannot (CIS-India and related TKDL critiques, 2016–2021) [S]. Adekola (2025) [S, paywalled — abstract only] argues that the 2024 WIPO GRTK Treaty's narrow scope and reliance on national implementation leave *traditional medicine specifically* under-protected, and calls for a justice-oriented, health-aligned framework. Concretely, the recommended governance model is **FAIR-for-metadata, CARE-for-governance**, operationalised through **Local Contexts TK and Biocultural (BC) Labels** (localcontexts.org) [F] that record Sri Lankan/Ayurvedic provenance and community-defined access terms, anchored in **Nagoya Protocol** access-and-benefit-sharing logic (CBD, 2010) [S]. This matters because Sri Lanka has **no enacted sui generis traditional-knowledge law** — only a 2009 draft framework (WIPO Lex) [F] that contemplated prior informed consent, equitable benefit-sharing, and the Commissioner for Ayurveda / Director-General of Intellectual Property as custodians; the Intellectual Property Act No. 36 of 2003 is silent on comprehensive TK protection. The project therefore operates in a legal vacuum it should name explicitly, and can turn that gap into a governance contribution by adopting a Nagoya-style, prior-informed-consent, non-commercial default for the content layer.

### 5.5 Annotation efficiency and active learning

The project's binding constraint is annotation: there is no labelled NER corpus and at most ~100 expert spot-check annotations. The active-learning literature is decisive that at very small budgets uncertainty sampling is unreliable (the cold-start problem — there is no model yet to be uncertain) and **diversity / representativeness sampling wins** (Yuan, Lin and Boyd-Graber, 2020 — cold-start NER; DEUCE, 2024) [S]. The 2024–2026 frontier is **LLM-in-the-loop active learning**, where a frontier LLM acts as selector and/or low-cost annotator — one clinical study reports 42–53× cost reduction over human labelling with inter-annotator agreement of 0.979 (Kholodna *et al.*, 2024) [F]; an ACL 2025 survey taxonomises the selector designs (Wang *et al.*, 2025b) [S].

For the present project the recommended pattern is therefore *not* train-then-sample but: embed candidate ingredient/dose/preparation strings with any multilingual encoder (CPU-cheap), cluster, and spend the ~100 human checks on one representative per cluster plus every rule-vs-LLM disagreement — maximising lexicon and template-grammar coverage per annotation, mirroring the JAMIA clinical-NER hybrid-sampling model (2024) [S].

### 5.6 Annotation methodologies: pre-annotation, LLM-silver, and weak supervision

The project's intended annotation pipeline is a three-stage cascade: (1) **dictionary/gazetteer pre-annotation** using the closed-vocabulary reference lists already extracted from the source (materia-medica, pratinidhi, mahā-kaṣāya, units); (2) an **LLM silver-annotation** layer doing sentence/clause segmentation and span/relation assignment for what the gazetteer missed; (3) **human verification/adjudication**. The literature confirms this is a sound, well-precedented design — it is the **machine-assisted / pre-annotation-plus-correction** workflow (also "annotation-by-correction", "model-in-the-loop"); stage 1 is **distant supervision**, and the three layers together constitute a **weak-supervision / data-programming** stack in which the gazetteer, the LLM, and the rules are all labelling functions (Ratner *et al.*, 2017).

**Stage 1 — dictionary pre-annotation** has a characteristic profile: high precision, low recall. On a standard distant-supervision baseline, dictionary matching scores ≈ 93.93 % precision / 58.35 % recall (Shang *et al.*, 2018) [S] — which matches our closed-vocabulary gazetteers and explains why stage 2 is needed for recall. Pre-annotation also measurably speeds human annotation: a clinical-NER study found 13.85–21.5 % time saving per entity with *no measurable bias* when the auto-dictionary was large, and that a bigger automatic dictionary (3,708 terms) beat a small manual one (Lingren *et al.*, 2014) [F]. The caveat from earlier work is that *low-quality* pre-annotation can hurt — adequate gazetteer coverage is the precondition, which the present project has.

**Stage 2 — LLM silver annotation** is the weakest link for our register. LLM-as-annotator quality trails fine-tuned encoders on harder, non-English tasks: on Marathi, GPT-4o and Llama-3.1-405B trailed a fine-tuned BERT by 10.2 % / 14.1 %, with the gap widening on complex multi-class tasks (Sonavane *et al.*, 2024) [F]; and SinhalaMMLU shows even Claude 3.5 Sonnet hits only 67 % on Sinhala, collapsing on culturally-rich domains (Pramodya *et al.*, 2025) — precisely the Ayurvedic register. The implication is to *not* auto-accept LLM labels on culturally-loaded fields (formula names, preparation prose) and to harden stage 2 with **multi-prompt self-consistency, an LLM-as-judge QC pass, and confidence-based routing** (auto-accept high-confidence spans; route low-confidence to the human) (Li *et al.*, 2024 — LLM-as-judge survey; confidence-routing work, 2025) [S] — all GPU-free, which fits the project's budget.

**The dominant risk is anchoring / automation bias in stage 3.** The strongest recent evidence shows that humans who see model suggestions shift from ~40 % to **81–87 % agreement with the model** and inflate downstream F1 by **+0.32–0.35** — a "homogenization" effect in which verifiers rubber-stamp model errors (Anonymous, 2025 — LLM-assisted annotation of subjective tasks) [F]. Because our annotated corpus exists to train/validate a *second oracle*, this contamination would propagate. The mitigation, and the single most valuable improvement to the pipeline, is to carve a **blind double-annotated gold subset** out of the ~100 expert checks — annotated *without* seeing any pre-labels — compute inter-annotator agreement on it, and measure silver-layer precision/recall against that truly-independent gold rather than against itself.

**Complementary methodologies** worth knowing: distant-supervised NER taggers that handle dictionary noise (AutoNER's "Tie-or-Break", BOND; Shang *et al.*, 2018) [S] if a tagger is later trained from the noisy labels; self-training / pseudo-labelling and tri-training for scaling the second oracle (multiple views vote, reducing error accumulation); and the **MAMA (Model-Annotate-Model-Annotate) curation cycle** with a dedicated adjudicator stage. For specialist medical/Ayurvedic semantics, expert (not crowd) annotation is mandatory.

**Tooling.** The best fit is **INCEpTION** (Klie *et al.*, 2018) [F] — free, UIMA/Unicode (renders Sinhala), supports external *recommenders* (our gazetteer + LLM plug in as recommenders), active-learning suggestions, and uniquely a curation/adjudication stage for the blind gold subset. **Prodigy** offers excellent `spacy-llm` LLM-pre-annotation recipes and active learning but is licensed/single-user; **Argilla** and **Label Studio** are open alternatives with LLM-feedback loops and Unicode rendering; **brat**, **Doccano**, and **GATE Teamware** are simpler open options.

The pipeline-level rule the literature implies for us: keep the **silver and gold layers physically separate, tag provenance on every span, and never let silver labels leak into the deterministic KG** — which is automatically satisfied here because the annotated corpus only trains/validates the second oracle, not the canonical extractor.

---

## 6. Positioning the Present Work

### 6.1 Confirmed gaps

The four-survey review supports the following claims, each backed by an absence in the surveyed literature:

1. No Sinhala NLP project in the **medical or Ayurvedic domain** has been published (de Silva, 2019, rev. 2024) [F].
2. No **computational tatsama/tadbhava/deśya classifier** has been published; the descriptive linguistic literature is rich (Gair, 1998; Geiger, 1938) but no NLP-side formalisation exists.
3. No **knowledge graph of Sri Lankan traditional medicine** has been published; a global survey of national digitisation initiatives (§3.5) confirms that GRAYU, AyurKOSH, IMPPAT and TKDL all draw exclusively on Indian sources, the major TCM databases are Chinese, and the only located Sri Lankan digital artefacts are ethnobotanical surveys, offline plant catalogues, and prototype mobile apps. On the available evidence the present project is the **first machine-readable / knowledge-graph representation of the Ayurvedic Pharmacopoeia of Sri Lanka** (prudent hedge: "first openly-described").
4. No **machine-readable form** of the Sri Lankan Ayurvedic Pharmacopoeia has been published.
5. No **Sinhala–Sanskrit aligned sense lexicon** at scale exists; the Sinhala WordNet (Wijesiri *et al.*, 2014) [S] reached only ~1,000 senses, and Sinhala is absent from IndoWordNet (Bhattacharyya, 2010) [S].

### 6.2 Methodological choices supported by the literature

The literature surveyed supports the following methodological positions:

- **Rule-based + closed-vocabulary + schema-constrained extraction**, with neural extractors as second oracles whose float-nondeterminism never touches the canonical KG. Justified by ODKE+ (Wang *et al.*, 2025), "From Chaos to Clarity" (Wang *et al.*, 2026), and the SinhalaMMLU finding that even Claude 3.5 Sonnet reaches only 67 % on Sinhala MCQs with humanities-domain performance collapsing (Pramodya *et al.*, 2025).
- **Replacing the Heritage-Engine-based sandhi parser with ByT5-Sanskrit** (Nehrdich *et al.*, 2024), which eliminates the memory-isolated-subprocess hack and beats Heritage on every published benchmark.
- **Piloting Surya OCR against Google Cloud Vision** (Jayatilleke and de Silva, 2025), with a benchmark-derived expectation of approximately three-fold WER improvement on clean Sinhala print.
- **Cohen's κ → Gwet's AC1** as the headline inter-annotator-agreement metric (Sarsa *et al.*, 2026; Gwet, 2008), with bootstrap confidence intervals.
- **LLM-as-judge as triage, not validation** (Adam and Kliegr, 2025; Kim *et al.*, 2024).
- **Borrowing-under-diglossia for linguistic framing, word-level language identification for the computational task** (Gair, 1998; Poplack, 1980; Solorio *et al.*, 2014).
- **Bespoke schema with external IRI bindings to ICD-11 TM2, POWO, ChEBI, and Plant Ontology** (World Health Organization, 2025; Royal Botanic Gardens, Kew, no date; Hastings *et al.*, 2013; Cooper *et al.*, 2013).
- **A SafetyFlag node class and verbatim disclaimer header** as the ethical minimum for a traditional-medicine KG containing heavy-metal-bearing preparations (Saper *et al.*, 2004, 2008; Park *et al.*, 2024; Joshi *et al.*, 2026).

---

## 7. Future Directions

Three directions remain explicitly out of scope for the MSc deliverable but follow naturally from the surveyed literature:

1. **Quantitative herb–drug-interaction prediction** by binding our Plant nodes to NP-KG (Bhasuran and Lever, 2025), HTINet2 (Zhang *et al.*, 2024), and DrugBank 6.0 schema (Knox *et al.*, 2024).
2. **Fine-grained Sinhala biomedical NER**, either by distant-supervision CRF on the project's 11,007 structured ingredient mentions or by fine-tuning multilingual SapBERT (Liu *et al.*, 2021b) on our closed vocabulary — though with the explicit caveat that XL-BEL does not cover Sinhala.
3. **A TEI scholarly-edition export** of the structured corpus, with stable CTS URN citation (Smith and Blackwell, ongoing) and submission to JOHD as a data paper — positioning the corpus as a citable scholarly artefact alongside the NLP and KG deliverables.
4. **A domain-adapted Sinhala neural backbone for the second-oracle NER.** The settled cost-effective recipe is vocabulary extension + continual pre-training + LoRA, exactly the path SinLlama took on Llama-3-8B (Aravinda *et al.*, 2025). Given no in-house GPU budget, the practical route is to LoRA-adapt SinLlama (or XLM-R/MuRIL with adapters) on a mixed corpus of the project's Ayurvedic extractions plus the **Medical-genre slice of SiDiaC** (Jayatilleke and de Silva, 2025b) [S] and the **SiPaKosa** classical/Pali-Sinhala corpus (Gururatne and Jayatilleke, 2026) as register-matched replay against catastrophic forgetting — a single rented GPU session (LoRA is hours, not weeks), and strictly as a validation oracle rather than a replacement for the deterministic extractor.

---

## 8. Bibliography

Entries alphabetised by first author surname. Where a work has been cited in this document, the first appearance is noted in square brackets at the end of the entry.

**Adam, S. and Kliegr, T.** (2025) 'Traceable LLM-based validation of statements in knowledge graphs', *Information Processing & Management*. [Preprint] arXiv:2409.07507. Available at: https://arxiv.org/abs/2409.07507. [§4.9]

**AI4Bharat** (no date) *Indic NLP Catalog* [Online repository]. Available at: https://github.com/AI4Bharat/indicnlp_catalog (Accessed: May 2026). [§2.4]

**Akhtar, M. et al.** (2024) 'Croissant: a metadata format for ML-ready datasets', *NeurIPS Datasets and Benchmarks Track*. [§5.3]

**Almasian, S. et al.** (2023) 'CQE: a comprehensive quantity extractor', in *Proceedings of EMNLP 2023*. arXiv:2305.08853. [§3.3]

**Amaral, G. et al.** (2024) 'ProVe: a pipeline for automated provenance verification of knowledge graphs', *Semantic Web Journal*. [§4.9]

**Appalaraju, S. et al.** (2021) 'DocFormer: end-to-end transformer for document understanding', in *Proceedings of ICCV 2021*. [§4.1]

**Apte, V.S.** (1957) *The Practical Sanskrit–English Dictionary*. Revised and enlarged edition. Poona: Prasad Prakashan. [§4.4]

**Aravinda, A. et al.** (2025) 'SinLlama: a Sinhala-capable decoder LLM via continual pre-training' [Preprint]. arXiv:2508.09115. Available at: https://arxiv.org/abs/2508.09115. [§2.5]

**Aronson, A.R.** (2017) *Effective mapping of biomedical text to the UMLS Metathesaurus: the MetaMap program*. National Library of Medicine. [§4.6]

**Beckett, D. et al.** (2014) *RDF 1.1 Turtle: Terse RDF Triple Language*. W3C Recommendation. Available at: https://www.w3.org/TR/turtle/. [§4.8]

**Bender, E.M. and Friedman, B.** (2018) 'Data statements for natural language processing: toward mitigating system bias and enabling better science', *Transactions of the ACL*, 6, pp. 587–604. [§5.3]

**Bhasuran, B. and Lever, J.** (2025) 'NP-KG: a knowledge graph for natural product–drug interactions', *PLOS Computational Biology*. PMC12150722. [§3.4]

**Bhattacharyya, P.** (2010) 'IndoWordNet', in *Proceedings of LREC 2010*. [§6.1]

**Bizer, C., Heath, T. and Berners-Lee, T.** (2009) 'Linked Data – the story so far', *International Journal on Semantic Web and Information Systems*, 5(3), pp. 1–22. [§4.8]

**Bollmann, M.** (2016) 'Improving historical spelling normalization with bi-directional LSTMs and multi-task learning', in *Proceedings of COLING 2016*. Available at: https://aclanthology.org/C16-1013/. [§5.2]

**Bollmann, M.** (2019) 'A large-scale comparison of historical text normalization systems', in *Proceedings of NAACL 2019*. Available at: https://aclanthology.org/N19-1389. [§5.2]

**Borchert, F. et al.** (2023) 'xMEN: a modular toolkit for cross-lingual medical entity normalization' [Preprint]. arXiv:2310.11275. Published in *JAMIA Open*, 2025. [§4.4] *(verified [F]: "When synonyms in the target language are scarce … we leverage English aliases via cross-lingual candidate generation.")*

**Bordes, A. et al.** (2013) 'Translating embeddings for modeling multi-relational data', in *Proceedings of NeurIPS 2013*. [§4.10]

**Buddhilive** (2025) *SLTK: Sinhala Language Tool Kit*. v1.0.0. Available at: https://github.com/buddhilive/sltk (Accessed: May 2026). [§4.3]

**Burnard, L.** (2014) *What is the Text Encoding Initiative? How to Add Intelligent Markup to Digital Resources*. Marseille: OpenEdition Press. [§5.2]

**Cambridge University Library** (ongoing) *Curious Cures in Cambridge Libraries* [Online project]. Available at: https://cudl.lib.cam.ac.uk/collections/medievalmedicalrecipes. [§5.2]

**Centre for Research in Ayurvedic Sciences and the National Resource Centre for EHR Standards** (ongoing) *SNOMED-CT AYUSH extension*. India: AYUSH Ministry. [§3.2]

**Chandralal, D.** (2010) *Sinhala*. London Oriental and African Language Library 15. Amsterdam: John Benjamins. [§2.1]

**Cohen, J.** (1960) 'A coefficient of agreement for nominal scales', *Educational and Psychological Measurement*, 20(1), pp. 37–46. [§4.9]

**Connelly, E.A. et al.** (2020) 'Pathways to identifying anti-microbial compounds: investigating *The Lylye of Medicynes*', *mBio*, 11(6). [§5.2]

**Conneau, A. et al.** (2020) 'Unsupervised cross-lingual representation learning at scale', in *Proceedings of ACL 2020*. [§2.5]

**Cooper, L. et al.** (2013) 'The Plant Ontology as a tool for comparative plant anatomy and genomic analyses', *Plant and Cell Physiology*, 54(2), e1. [§3.2]

**Costa-jussà, M.R. et al.** (2022) 'No Language Left Behind: scaling human-centered machine translation' [Preprint]. arXiv:2207.04672. [§2.4]

**De Cao, N., Aziz, W. and Titov, I.** (2021) 'Autoregressive entity retrieval', in *Proceedings of ICLR 2021*. [§4.6]

**de Silva, N.** (2019, rev. 2026) 'Survey on publicly available Sinhala natural language processing tools and research' [Preprint]. arXiv:1906.02358 (latest revision v26, January 2026). Available at: https://arxiv.org/abs/1906.02358. [§2.5] *(verified [F]: explicitly a perpetually-updated living survey.)*

**Dettmers, T. et al.** (2018) 'Convolutional 2D knowledge graph embeddings', in *Proceedings of AAAI 2018*. [§4.10]

**Dharmamitra** (ongoing) *dharmamitra-sanskrit-grammar* [Python package]. Available at: https://pypi.org/project/dharmamitra-sanskrit-grammar/ (Accessed: May 2026). [§4.5]

**Dhananjaya, V. et al.** (2022) 'BERTifying Sinhala – a comprehensive analysis of pre-trained language models for Sinhala text classification', in *Proceedings of LREC 2022*. [§2.5]

**Eberhard, D.M., Simons, G.F. and Fennig, C.D. (eds.)** (2024) *Ethnologue: Languages of the World*. 27th edn. Dallas: SIL International. Available at: https://www.ethnologue.com. [§2.1]

**Ferguson, C.A.** (1959) 'Diglossia', *Word*, 15(2), pp. 325–340. [§2.3]

**Fernando, M. et al.** (2016) 'A comprehensive part-of-speech tag set and SVM based POS tagger for Sinhala', in *Proceedings of WSSANLP 2016*. [§2.5]

**Gair, J.W.** (1968) 'Sinhalese diglossia', *Anthropological Linguistics*, 10(8), pp. 1–15. [§2.3]

**Gair, J.W.** (1998) *Studies in South Asian Linguistics: Sinhala and Other South Asian Languages*. New York: Oxford University Press. [§2.1]

**Gala, J. et al.** (2023) 'IndicTrans2: towards high-quality and accessible machine translation models for all 22 scheduled Indian languages' [Preprint]. arXiv:2305.16307. [§2.4]

**Gebru, T. et al.** (2021) 'Datasheets for datasets', *Communications of the ACM*, 64(12), pp. 86–92. [§5.3]

**Geiger, W.** (1938) *A Grammar of the Sinhalese Language*. Colombo: Royal Asiatic Society, Ceylon Branch. [§2.1]

**Goyal, P. and Huet, G.** (2016) 'Design and analysis of a lean interface for Sanskrit corpus annotation', *Journal of Language Modelling*, 4(2), pp. 145–182. [§4.5]

**Gururatne, K. and Jayatilleke, N.** (2026) 'SiPaKosa: a Sinhala-Pali Buddhist corpus' [Preprint]. arXiv:2603.29221. [§2.5]

**Guzmán, F. et al.** (2019) 'The FLORES evaluation datasets for low-resource machine translation: Nepali-English and Sinhala-English' [Preprint]. arXiv:1902.01382. [§2.5]

**Gwet, K.L.** (2008) 'Computing inter-rater reliability and its variance in the presence of high agreement', *British Journal of Mathematical and Statistical Psychology*, 61(1), pp. 29–48. [§4.9]

**Han, M. et al.** (2024) 'Knowledge graph construction for the *Treatise on Febrile Diseases*: from text to disease–syndrome–herb–prescription'. PMC12502320. [§5.2]

**Hastings, J. et al.** (2013) 'The ChEBI reference database and ontology for biologically relevant chemistry: enhancements for 2013', *Nucleic Acids Research*, 41(D1), pp. D456–D463. [§1.1]

**Hellwig, P. et al.** (ongoing) *SARIT: Search and Retrieval of Indic Texts* [Online project]. Available at: https://sarit.indology.info. [§5.2]

**Henadeerage, K.** (2002) *Topics in Sinhala Syntax*. PhD thesis, Australian National University. [§2.1]

**Help Centre** (no date) *Rendering Issues Due to ZWJ in Sinhala Strings and how IDNA 2003/2008 Affects Sinhala* [Online]. Available at: https://helpcentre.lk/knowledgebase/rendering-issues-due-to-zwj-in-sinhala-strings-and-how-idna-2003-2008-affects-sinhala/ (Accessed: May 2026). [§4.2]

**Hettiarachchi, H. et al.** (2024) 'NSINA: a news corpus for Sinhala', in *Proceedings of LREC-COLING 2024*. [§5.3]

**Huang, Y. et al.** (2022) 'LayoutLMv3: pre-training for document AI with unified text and image masking', in *Proceedings of ACM Multimedia 2022*. [§4.1]

**Inman, M.** (1993) *Semantics and Pragmatics of Colloquial Sinhala Involitive Verbs*. PhD thesis, Stanford University. [§2.1]

**Ishida, R.** (no date) *Sinhala – an overview for developers*. World Wide Web Consortium. Available at: https://r12a.github.io/scripts/sinh/si.html (Accessed: May 2026). [§2.2]

**Jackson, R.C. et al.** (2019) 'ROBOT: a tool for automating ontology workflows', *BMC Bioinformatics*, 20, 407. [§4.9]

**Jayatilleke, N. and de Silva, N.** (2025) 'Zero-shot OCR accuracy of low-resourced languages: a comparative analysis on Sinhala and Tamil' [Preprint]. arXiv:2507.18264. Available at: https://arxiv.org/abs/2507.18264. [§2.5]

**Joshi, P. et al.** (2020) 'The state and fate of linguistic diversity and inclusion in the NLP world', in *Proceedings of ACL 2020*. Available at: https://aclanthology.org/2020.acl-main.560/. [§1.1]

**Joshi, S. et al.** (2026) 'GRAYU: a graph-based database integrating Ayurvedic formulations, medicinal plants, phytochemicals and diseases', *Frontiers in Pharmacology*, 16, 1727224. doi:10.3389/fphar.2025.1727224. [§3.1]

**Kakwani, D. et al.** (2020) 'IndicNLPSuite: monolingual corpora, evaluation benchmarks and pre-trained multilingual language models for Indian languages', in *Findings of EMNLP 2020*. [§2.4]

**Kapp, D.** (ongoing) *GRETIL: Göttingen Register of Electronic Texts in Indian Languages* [Online project]. Available at: http://gretil.sub.uni-goettingen.de. [§5.2]

**Khanuja, S. et al.** (2021) 'MuRIL: multilingual representations for Indian languages' [Preprint]. arXiv:2103.10730. [§2.4]

**Kim, S. et al.** (2024) 'On the reliability of LLM-as-a-judge: temperature, sampling, and consistency' [Preprint]. arXiv:2412.12509. [§4.9]

**Klug, H. (ed.)** (ongoing) *CoReMA: Cooking Recipes of the Middle Ages* [Online project]. Austrian Academy of Sciences. Available at: https://dha.acdh.oeaw.ac.at/en/corema-cooking-recipes-middle-ages-corpus-analysis-visualisation. [§5.2]

**Knox, C. et al.** (2024) 'DrugBank 6.0: the DrugBank knowledgebase for 2024', *Nucleic Acids Research*, 52(D1), pp. D1265–D1275. [§3.4]

**Knublauch, H. and Kontokostas, D.** (2017) *Shapes Constraint Language (SHACL)*. W3C Recommendation. Available at: https://www.w3.org/TR/shacl/. [§4.9]

**Lakmal, D. et al.** (2020) 'Word embedding evaluation for Sinhala', in *Proceedings of LREC 2020*. [§2.5]

**Lee, J. et al.** (2024) 'TFLOP: table-structure recognition framework using layout pointer mechanism', in *Proceedings of IJCAI 2024*. Available at: https://www.ijcai.org/proceedings/2024/105. [§4.1]

**Li, J. et al.** (2016) 'BioCreative V CDR task corpus: a resource for chemical disease relation extraction', *Database*, 2016, baw068. [§4.6]

**Li, W. et al.** (2025) 'RELATE: relation extraction in biomedical abstracts with LLMs and ontology constraints' [Preprint]. arXiv:2509.19057. [§4.7]

**Lin, X. et al.** (2022) 'HerbKG: constructing a herbal-molecular medicine knowledge graph using a two-stage framework based on deep transfer learning', *Frontiers in Genetics*, 13, 799349. [§3.1]

**Liu, F. et al.** (2021a) 'Self-alignment pretraining for biomedical entity representations', in *Proceedings of NAACL 2021*. [SapBERT.] [§4.6]

**Liu, F. et al.** (2021b) 'Learning domain-specialised representations for cross-lingual biomedical entity linking', in *Proceedings of ACL 2021*. [Cross-lingual SapBERT, XL-BEL benchmark.] arXiv:2105.14398. [§4.6]

**Liyanage, C. and Sarveswaran, K.** (2023) 'Sinhala dependency treebank (UD_Sinhala-STB)', in *Proceedings of the Sixth Workshop on Universal Dependencies (UDW 2023)*. Available at: https://aclanthology.org/2023.udw-1.3/. [§2.4]

**Luo, L. et al.** (2024) 'BioRED: a comprehensive biomedical relation extraction dataset', *Database*, 2024, baad067. [§4.9]

**Maciejewski, J. et al.** (2025) 'GLiREL: a generalist lightweight model for zero-shot relation extraction' [Preprint]. arXiv:2501.03172. [§4.7]

**Maheshwari, A. et al.** (2024) 'Byte-level OCR post-correction for low-resource Indian languages' [Preprint]. arXiv:2502.01205. [§4.2]

**Ministry of AYUSH** (2025) *NAMASTE Portal: National AYUSH Morbidity & Standardized Electronic Health Records Terminologies*. Government of India. Available at: https://namaste.ayush.gov.in. [§3.2]

**Mirasdar, S. et al.** (2026) 'AyurKOSH dataset: a machine-readable Ayurvedic knowledge resource for knowledge graph and computational intelligence', *IEEE DataPort*. doi:10.21227/58ej-wz87. [§3.1]

**Mohan, S. and Li, D.** (2019) 'MedMentions: a large biomedical corpus annotated with UMLS concepts', in *Proceedings of AKBC 2019*. [§4.6]

**Monier-Williams, M.** (1899) *A Sanskrit–English Dictionary, Etymologically and Philologically Arranged*. Oxford: Clarendon Press. [§4.4]

**Nassar, A. et al.** (2022) 'TableFormer: table structure understanding with transformers', in *Proceedings of CVPR 2022*. [§4.1]

**Nehrdich, S. et al.** (2024) 'ByT5-Sanskrit: a multitask byte-level model for Sanskrit', in *Findings of EMNLP 2024*. arXiv:2409.13920. Available at: https://aclanthology.org/2024.findings-emnlp.805/. [§4.5]

**OBO Foundry** (no date) *OBO Foundry: Ontologies* [Online registry]. Available at: https://obofoundry.org (Accessed: May 2026). [§3.2]

**Pandey, S., Sinha, A. and Singh, A.** (2025) 'Code-mixed Indic NER: domain-pretrained encoders versus LLMs' [Preprint]. arXiv:2509.02514. [§5.1]

**Paolillo, J.C.** (1997) 'Sinhala diglossia: discrete or continuous?', *Anthropological Linguistics*, 39(4), pp. 568–600. [§2.3]

**Sikder, M.M.** (2024) 'Ayurvedic medicine: a traditional medical system and its heavy metal poisoning', *Chonnam Medical Journal*, 60(2), pp. 97–104. PMC11148304. [§3.4] *(verified [F]: "at least 55 cases of heavy metal intoxication related to Ayurvedic HMPs … reported since 1978." Previously mis-attributed to "Park et al." in the v0.1 draft.)*

**Paruchuri, V.** (2024) *Surya OCR: multilingual document analysis* [Open-source software]. Available at: https://github.com/VikParuchuri/surya (Accessed: May 2026). [§4.2]

**Poplack, S.** (1980) 'Sometimes I'll start a sentence in Spanish y termino en español: toward a typology of code-switching', *Linguistics*, 18(7–8), pp. 581–618. [§2.3]

**Pramodya, R. et al.** (2025) 'SinhalaMMLU: a Sinhala curriculum benchmark for large language models', in *Proceedings of EMNLP 2025*. Available at: https://aclanthology.org/2025.emnlp-main.1673/. [§2.5]

**QUDT.org** (2026) *QUDT Quantities, Units, Dimensions and Types Ontology*. v3.1.4. Available at: https://qudt.org/doc/DOC_VOCAB-UNITS.html (Accessed: May 2026). [§3.3]

**Rajan, V.** (2024) *Aksharamukha: a transliteration tool for Indian scripts*. Available at: https://github.com/virtualvinodh/aksharamukha (Accessed: May 2026). [§4.3]

**Ranasinghe, T. et al.** (2024) 'SOLD: Sinhala offensive language dataset', *Language Resources and Evaluation*. [§2.5]

**Ranathunga, S. and de Silva, N.** (2022) 'Some languages are more equal than others: probing deeper into the linguistic disparity in the NLP world', in *Proceedings of AACL-IJCNLP 2022*. [§2.4]

**Ranathunga, S. et al.** (2018) 'Neural machine translation for Sinhala–Tamil official documents', in *Proceedings of LREC 2018*. [Si-Ta system.] [§2.5]

**Ratner, A. et al.** (2017) 'Snorkel: rapid training data creation with weak supervision', *Proceedings of VLDB*, 11(3), pp. 269–282. [§4.7]

**RDFLib** (ongoing) *pySHACL: Python implementation of the SHACL constraint validator* [Open-source software]. Available at: https://github.com/RDFLib/pySHACL. [§4.9]

**Rijgersberg, H., van Assem, M. and Top, J.** (2013) 'Ontology of units of measure and related concepts', *Semantic Web Journal*, 4(1), pp. 3–13. [§3.3]

**Royal Botanic Gardens, Kew** (no date) *Plants of the World Online (POWO)* [Online database]. Available at: https://powo.science.kew.org (Accessed: May 2026). [§1.1]

**Ruas, P. and Couto, F.M.** (2023) 'NILINKER: attention-based approach to NIL entity linking' [Preprint]. arXiv:2302.07189. [§4.6]

**Safavi, T., Koutra, D. and Meij, E.** (2020) 'Evaluating the calibration of knowledge graph embeddings for trustworthy link prediction', in *Proceedings of EMNLP 2020*. arXiv:2004.01168. [§4.10]

**Sandhan, J. et al.** (2022) 'TransLIST: a transformer-based linguistically informed Sanskrit tokenizer', in *Findings of EMNLP 2022*. arXiv:2210.11753. [§4.5]

**Sandhan, J. et al.** (2023) 'SanskritShala: a neural Sanskrit NLP toolkit with web-based interface', in *Proceedings of ACL 2023 (Demonstrations)*. [§4.5]

**Sandhan, J. et al.** (2025) 'Sandarśana: a survey of computational Sanskrit', *ACM Computing Surveys*, 57(3). doi:10.1145/3729530. [§4.5]

**Sanskrit Library** (ongoing) *Cologne Digital Sanskrit Dictionaries (CDSL)*. Available at: https://sanskritlibrary.org/cologne.html. [§4.4]

**Saper, R.B. et al.** (2004) 'Heavy metal content of Ayurvedic herbal medicine products', *JAMA*, 292(23), pp. 2868–2873. Available at: https://jamanetwork.com/journals/jama/fullarticle/1108395. [§3.4] *(verified [F]: "14 (20%) of 70 HMPs … contained lead, mercury, and/or arsenic.")*

**Saper, R.B. et al.** (2008) 'Lead, mercury, and arsenic in US- and Indian-manufactured Ayurvedic medicines sold via the Internet', *JAMA*, 300(8), pp. 915–923. [§3.4]

**Sarsa, S. et al.** (2026) 'Counting on consensus: selecting the right inter-annotator agreement metric for NLP annotation and evaluation' [Preprint]. arXiv:2603.06865. [§4.9]

**Senarath, Y.** (2020) *Sinling: a Sinhala language tool kit* [Open-source software]. Available at: https://github.com/ysenarath/sinling. [§4.3]

**Senaratne, C.D.** (2009) *Sinhala-English Code-Mixing in Sri Lanka: a Sociolinguistic Study*. LOT Dissertation Series 215. Utrecht: LOT. [§2.3]

**Senevirathne, L. et al.** (2020) 'Sentiment analysis for Sinhala language using deep learning techniques' [Preprint]. arXiv:2011.07280. [§2.5]

**Sennrich, R., Haddow, B. and Birch, A.** (2016) 'Neural machine translation of rare words with subword units', in *Proceedings of ACL 2016*. [§4.3]

**Kartchner, D. et al.** (2024) 'A comprehensive evaluation of biomedical entity linking models'. PMC11097978. [§4.6] *(verified [F]: SapBERT vs MetaMap, MedMentions ST21PV 0.637 vs 0.568; BC5CDR 0.883 vs 0.828; MedMentions-Full mention-overlap 0.8221. Previously mis-attributed to "Sevgili et al." in the v0.1 draft.)*

**Smith, B. et al.** (2007) 'The OBO Foundry: coordinated evolution of ontologies to support biomedical data integration', *Nature Biotechnology*, 25(11), pp. 1251–1255. [§3.2]

**Smith, D.N. and Blackwell, C.W.** (ongoing) *CITE Architecture and Canonical Text Services (CTS)* [Online specification]. Available at: https://wiki.digitalclassicist.org/Canonical_Text_Services. [§5.2]

**Solorio, T. et al.** (2014) 'Overview for the first shared task on language identification in code-switched data', in *Proceedings of the First Workshop on Computational Approaches to Code Switching*. [§5.1]

**Sporny, M. et al.** (2020) *JSON-LD 1.1: A JSON-based Serialization for Linked Data*. W3C Recommendation. Available at: https://www.w3.org/TR/json-ld11/. [§4.8]

**Stepanov, K. et al.** (2025) 'GLiNER2: an efficient multi-task information extraction system with schema-driven interface' [Preprint]. arXiv:2507.18546. [§4.7]

**Sun, Z. et al.** (2019) 'RotatE: knowledge graph embedding by relational rotation in complex space', in *Proceedings of ICLR 2019*. [§4.10]

**Sung, M. et al.** (2020) 'Biomedical entity representations with synonym marginalization', in *Proceedings of ACL 2020*. [BioSyn.] [§4.6]

**Terdalkar, H.** (2023) 'Āyurjñānam: exploring Āyurveda using knowledge graphs', in *Proceedings of NYCIKS 2023*. Available at: https://hrishikeshrt.github.io/publication/nyciks2023/abstract.pdf. [§3.1]

**Terdalkar, H.** (ongoing) *PyCDSL: Python interface for the Cologne Digital Sanskrit Dictionaries* [Open-source software]. Available at: https://github.com/hrishikeshrt/PyCDSL. [§4.4]

**The Unicode Consortium** (2024) *The Unicode Standard, Version 16.0.0*. Mountain View: Unicode Inc. Available at: https://unicode.org/versions/Unicode16.0.0/. [§4.3]

**Toutanova, K. and Chen, D.** (2015) 'Observed versus latent features for knowledge base and text inference', in *Proceedings of the 3rd Workshop on Continuous Vector Space Models and Their Compositionality*. [FB15k-237.] [§4.10]

**Trouillon, T. et al.** (2016) 'Complex embeddings for simple link prediction', in *Proceedings of ICML 2016*. [ComplEx.] [§4.10]

**Vasantharajan, C. and Thayasivam, U.** (2022) 'Adapting the Tesseract Open-Source OCR engine for tamil and sinhala legacy fonts and creating a parallel corpus for Tamil-Sinhala-English', in *Proceedings of ICTer 2022*. [§4.2]

**Vyawahare, R. et al.** (2024) 'RoundTripOCR: a data generation technique for enhancing post-OCR text correction in low-resource languages' [Preprint]. arXiv:2412.15248. [§4.2]

**Wang, B. et al.** (2024) 'DocLayout-YOLO: enhancing document layout analysis through diverse synthetic data and global-to-local adaptive perception' [Preprint]. arXiv:2410.12628. [§4.1]

**Wang, B. et al.** (2025) 'ODKE+: ontology-guided open-domain knowledge extraction with LLMs' [Preprint]. arXiv:2509.04696. [§4.7]

**Wang, B. et al.** (2026) 'From chaos to clarity: schema-constrained AI for auditable biomedical evidence extraction from full-text PDFs' [Preprint]. arXiv:2601.14267. [§4.7]

**Wei, C.-H. et al.** (2015) 'SimConcept: a hybrid approach for simplifying composite named entities in biomedical text', *IEEE Journal of Biomedical and Health Informatics*, 19(4), pp. 1385–1391. PMC4543296. [§4.6]

**Wijesiri, I. et al.** (2014) 'Building a WordNet for Sinhala', in *Proceedings of the Seventh Global WordNet Conference (GWC 2014)*. [§2.5]

**Wilkinson, M.D. et al.** (2016) 'The FAIR Guiding Principles for scientific data management and stewardship', *Scientific Data*, 3, 160018. [§5.3]

**World Health Organization** (2025) *International Classification of Diseases 11th Revision, Module 2 — Traditional Medicine* [Online]. Geneva: World Health Organization. Available at: https://icd.who.int/browse/2025-01/mms/en (Accessed: May 2026). [§1.1]

**Yenduri, G. et al.** (2024) 'LEVOS: leveraging vocabulary overlaps with Sanskrit to generate technical lexicons in Indian languages' [Preprint]. arXiv:2407.06331. [§4.5]

**Yi, F. et al.** (2024) 'REPaL: grasping the essentials — definition-only zero-shot relation extraction', in *Proceedings of EMNLP 2024*. Available at: https://aclanthology.org/2024.emnlp-main.747/. [§4.7]

**Yu, X. et al.** (2025) 'Severe lead poisoning from Ayurvedic medicine: a case report', *Frontiers in Pediatrics*. doi:10.3389/fped.2025.1692561. [§3.4]

**Zaratiana, U. et al.** (2024) 'GLiNER: generalist model for named entity recognition using bidirectional transformer' [Preprint]. arXiv:2311.08526. [§4.7]

**Zaveri, A. et al.** (2016) 'Quality assessment for Linked Data: a survey', *Semantic Web*, 7(1), pp. 63–93. doi:10.3233/SW-150175. [§4.9]

**Zhang, S. et al.** (2022) 'Knowledge-rich self-supervision for biomedical entity linking' [Preprint]. arXiv:2112.07887. [KRISSBERT.] [§4.6]

**Zhang, X. et al.** (2024) 'HTINet2: a herb–target interaction prediction model via knowledge graph embedding', *Briefings in Bioinformatics*. PMC11341278. [§3.4]

**Zhao, Z. et al.** (2026) 'NPASS 3.0: natural product activity and species source database with quantitative toxicity', *Nucleic Acids Research*, 54(D1), pp. D1519–D1528. [§3.4]

**Zhong, L. et al.** (2025) 'LLM-empowered knowledge graph construction: a survey' [Preprint]. arXiv:2510.20345. [§4.7]

### 8.1 Bibliography additions (v0.2 — §3.5 global landscape)

*These entries were added with the §3.5 global-initiatives section and the v0.2 verification pass. They are alphabetised among themselves; a future revision should merge them into the main list above. The mis-attributed entries corrected in v0.2 (Kartchner ← "Sevgili"; Sikder ← "Park"; Borchert ← "Borchmann") are likewise out of strict alphabetical order pending a merge pass.*

**Chen, X. et al.** (2006) 'TCM-ID: traditional Chinese medicine information database', *Nucleic Acids Research*, 34(D1), pp. D728–D731. [§3.5] [F]

**CSIR** (no date) *Traditional Knowledge Digital Library (TKDL)* [Online]. Council of Scientific and Industrial Research, India. Available at: http://www.tkdl.res.in (Accessed: May 2026). [§3.5] [S]

**Fang, S. et al.** (2020) 'HERB: a high-throughput experiment- and reference-guided database of traditional Chinese medicine', *Nucleic Acids Research*, 49(D1), pp. D1197–D1206. [§3.5] [F]

**Hatherley, R. et al.** (2015) 'SANCDB: a South African natural compound database', *Journal of Cheminformatics*, 7, 29. [§3.5] [F]

**Hou, D. et al.** (2024) 'CMAUP 2024 update: a database of collective molecular activities of useful plants', *Nucleic Acids Research*, 52(D1). [§3.5] [S]

**Kartchner, D. et al.** — *see corrected entry in main list (replaces "Sevgili").* [§4.6]

**Kong, X. et al.** (2024) 'BATMAN-TCM 2.0: an enhanced integrative database for known and predicted interactions between traditional Chinese medicine ingredients and target proteins', *Nucleic Acids Research*, 52(D1). [§3.5] [S]

**Lyu, M. et al.** (2023) 'TCMBank: the largest TCM database provides deep learning-based Chinese-Western medicine exclusion prediction', *Signal Transduction and Targeted Therapy*, 8, 127. [§3.5] [S]

**Mohanraj, K. et al.** (2022) 'OSADHI – an online structural and analytics-based database for herbs of India' [Preprint]. (North East Institute of Science and Technology). [§3.5] [S]

**Oprea, T.I. et al.** (2024) 'A critical assessment of traditional Chinese medicine databases', *Frontiers in Pharmacology*. PMC11082401. [§3.5] [F]

**Royal Botanic Gardens, Kew** (no date) — *see POWO entry in main list.* [§3.5]

**Ru, J. et al.** (2014) 'TCMSP: a database of systems pharmacology for drug discovery from herbal medicines', *Journal of Cheminformatics*, 6, 13. [§3.5] [F]

**Rutz, A. et al.** (2022) 'The LOTUS initiative for open knowledge management in natural products research', *eLife*, 11, e70780. [§3.5] [S]

**Sawada, R. et al.** (2018) 'KampoDB, database of predicted targets and functional annotations of natural medicines', *Scientific Reports*, 8, 11216. [§3.5] [F]

**Smart Hela Wedakama** (2024) 'A mobile application for Sri Lankan traditional medicine using machine learning and augmented reality', in *Proceedings of an IEEE conference, 2024*. [§3.5] [S] *(prototype plant-ID / Sinhala-prescription-OCR app — not a structured database)*

**Sorokina, M. et al.** (2021) 'COCONUT online: collection of open natural products database', *Journal of Cheminformatics*, 13, 2. [§3.5] [S]

**Vivek-Ananth, R.P. et al.** (2023) 'IMPPAT 2.0: an enhanced and expanded phytochemical atlas of Indian medicinal plants', *ACS Omega*, 8(9), pp. 8827–8845. [§3.5] [F]

**Wu, Y. et al.** (2019) 'SymMap: an integrative database of traditional Chinese medicine enhanced by symptom mapping', *Nucleic Acids Research*, 47(D1), pp. D1110–D1117. [§3.5] [F]

**Xu, H.-Y. et al.** (2019) 'ETCM: an encyclopaedia of traditional Chinese medicine', *Nucleic Acids Research*, 47(D1), pp. D976–D982. [§3.5] [F]

**Xue, R. et al.** (2013) 'TCMID: traditional Chinese medicine integrative database for herb molecular mechanism analysis', *Nucleic Acids Research*, 41(D1), pp. D1089–D1095. [§3.5] [F]

**Yan, D. et al.** (2022) 'Construction of a knowledge graph for the *Treatise on Febrile Diseases* (Shanghan Lun)'. [Knowledge graph from a single classical medical text.] [§3.5] [S]

### 8.2 Bibliography additions (v0.3 — §§4.6, 5.3–5.5, 7)

*Added with the v0.3 pass covering active learning, reproducibility/determinism infrastructure, cross-lingual NER transfer, traditional-knowledge ethics (CARE/WIPO), and domain adaptation. Alphabetised among themselves; merge into the main list in a future pass.*

**Carroll, S.R. et al.** (2020) 'The CARE Principles for Indigenous Data Governance', *Data Science Journal*, 19(1), 43. [§5.4] [S]

**Carroll, S.R. et al.** (2021) 'Operationalizing the CARE and FAIR Principles for Indigenous data futures', *Scientific Data*, 8, 108. [§5.4] [S]

**Chen, T. et al.** (2023) 'Contextual label projection for cross-lingual structured prediction' [Preprint]. arXiv:2309.08943. [§4.6] [S]

**Garcia-Ferrero, I. et al.** (2025) 'Revisiting projection-based data transfer for cross-lingual named entity recognition in low-resource languages' [Preprint]. [§4.6] [F]

**Gururatne, K. and Jayatilleke, N.** (2026) — *see SiPaKosa entry in main list (§2.5).* [§7]

**Jayatilleke, N. and de Silva, N.** (2025b) 'SiDiaC: a diachronic corpus of Sinhala (with a medical-genre layer)' [Preprint]. arXiv:2509.17912. [§7] [S]

**Kholodna, N. et al.** (2024) 'LLMs in the loop: leveraging large language models for active learning in low-resource named entity recognition' [Preprint]. [§5.5] [F] *(verified [F]: 42–53× cost reduction vs human annotation; IAA 0.979.)*

**Kurtzer, G.M. et al.** (2017) 'Singularity: scientific containers for mobility of compute', *PLOS ONE*, 12(5), e0177459. [§5.3] [S]

**Nüst, D. et al.** (2020) 'Ten simple rules for writing Dockerfiles for reproducible data science', *PLOS Computational Biology*, 16(11), e1008316. [§5.3] [S]

**Reproducibility-in-NLP analysis** (2023) 'Reproducibility in NLP: what have we learned from the checklist?', in *Findings of ACL 2023*. [§5.3] [F] *(verified [F]: code-sharing = strongest reproducibility lever, +8 %, across 10,405 checklist responses.)*

**Sandve, G.K. et al.** (2013) 'Ten simple rules for reproducible computational research', *PLOS Computational Biology*, 9(10), e1003285. [§5.3] [S]

**Senevirathne, S. et al.** (2024) 'A multi-way parallel named entity annotated corpus for English, Tamil and Sinhala' [Preprint]. (3,835 sentences/language, government domain; XLM-R Sinhala macro-F1 88.3.) [§4.6] [F]

**Wang, X. et al.** (2025b) 'A survey of LLM-based active learning', in *Proceedings of ACL 2025*. [§5.5] [S]

**WIPO** (2024) *WIPO Treaty on Intellectual Property, Genetic Resources and Associated Traditional Knowledge*. Geneva: World Intellectual Property Organization. Adopted 24 May 2024. [§5.4] [S]

**WIPO Lex** (no date) *Sri Lanka: Intellectual Property Act and traditional-knowledge provisions* [Online]. Available at: https://wipolex.wipo.int (Accessed: May 2026). [§5.4] [S]

**Yuan, M., Lin, H.-T. and Boyd-Graber, J.** (2020) 'Cold-start active learning through self-supervised language modeling', in *Proceedings of EMNLP 2020*. [§5.5] [S]

### 8.3 Bibliography additions (v0.4 — §5.6 annotation methodologies)

*Added with the §5.6 annotation-methodologies section. Alphabetised among themselves; merge into the main list in a future pass.*

**Anonymous** (2025) 'On the effects of LLM-assisted annotation of subjective tasks' [Preprint]. arXiv:2507.15821. [§5.6] [F] *(verified [F]: human–model agreement rises 40 %→81–87 %; downstream F1 inflated +0.32–0.35; "homogenization" of labels.)*

**Klie, J.-C. et al.** (2018) 'The INCEpTION platform: machine-assisted and knowledge-oriented interactive annotation', in *Proceedings of COLING 2018 (System Demonstrations)*. Available at: https://aclanthology.org/C18-2002/. [§5.6] [F]

**Li, H. et al.** (2024) 'LLMs-as-judges: a comprehensive survey on LLM-based evaluation methods' [Preprint]. arXiv:2412.05579. [§5.6] [S]

**Lingren, T. et al.** (2014) 'Evaluating the impact of pre-annotation on annotation speed and potential bias: natural language processing gold standard development for clinical named entity recognition in clinical trial announcements', *Journal of the American Medical Informatics Association*, 21(3), pp. 406–413. PMC3994857. [§5.6] [F] *(verified [F]: 13.85–21.5 % time saving per entity; no measurable bias with a large auto-dictionary.)*

**Shang, J. et al.** (2018) 'Learning named entity tagger using domain-specific dictionary' [AutoNER] [Preprint]. arXiv:1809.03599. [§5.6] [S] *(dictionary-match baseline ≈ 93.93 % P / 58.35 % R.)*

**Sonavane, O. et al.** (2024) 'Limitations of LLMs as annotators for low-resource languages: a study on Marathi' [Preprint]. arXiv:2411.17637. [§5.6] [F] *(verified [F]: GPT-4o / Llama-3.1-405B trail fine-tuned BERT by 10.2 % / 14.1 %.)*

### 8.4 Bibliography additions (v0.4 — §§4.9, 4.11, 5.4 deeper)

*Added with the v0.4 pass on unlabelled-KG evaluation, formal-language framing, and the deeper traditional-knowledge controversy. Alphabetised among themselves; merge into the main list in a future pass.*

**Adekola, T.** (2025) 'Whose knowledge, whose cure? Traditional medicine and the limits of the 2024 WIPO Treaty', *Journal of World Intellectual Property* [paywalled — abstract only]. [§5.4] [S]

**Carroll, S.R. et al.** (2021) — *see §8.2 entry (Operationalizing CARE and FAIR).* [§5.4]

**Convention on Biological Diversity** (2010) *Nagoya Protocol on Access to Genetic Resources and the Fair and Equitable Sharing of Benefits Arising from their Utilization*. Montreal: Secretariat of the CBD. [§5.4] [S]

**Dong, X. et al.** (2014) 'Knowledge Vault: a web-scale approach to probabilistic knowledge fusion', in *Proceedings of KDD 2014*, pp. 601–610. [§4.9] [F]

**Dong, Y. et al.** (2024) 'XGrammar: flexible and efficient structured generation engine for large language models' [Preprint]. arXiv:2411.15100. [§4.11] [S]

**Gao, J. et al.** (2019) 'Efficient knowledge graph accuracy evaluation', *Proceedings of the VLDB Endowment*, 12(11), pp. 1679–1691. [§4.9] [F] *(two-stage weighted cluster sampling; up to 60 % fewer annotations than random.)*

**Hobbs, J.R. et al.** (1997) 'FASTUS: a cascaded finite-state transducer for extracting information from natural-language text', in Roche, E. and Schabes, Y. (eds.) *Finite-State Language Processing*. Cambridge, MA: MIT Press, pp. 383–406. [§4.11] [F]

**Kushmerick, N.** (2000) 'Wrapper induction: efficiency and expressiveness', *Artificial Intelligence*, 118(1–2), pp. 15–68. [§4.11] [S]

**Local Contexts** (no date) *TK Labels and BC Labels* [Online]. Available at: https://localcontexts.org/labels/ (Accessed: May 2026). [§5.4] [F]

**Marchesin, S. and Silvello, G.** (2025) 'Credible intervals for knowledge graph accuracy estimation', in *Proceedings of SIGMOD 2025*. [§4.9] [F] *(Bayesian credible intervals; up to 47 % annotation savings; better-behaved than frequentist CIs at small n.)*

**WIPO Lex** (2009) *A legal framework for the protection of traditional knowledge in Sri Lanka* [Draft, unenacted]. Available at: https://wipolex.wipo.int (Accessed: May 2026). [§5.4] [F]

**Willard, B.T. and Louf, R.** (2023) 'Efficient guided generation for large language models' [Outlines] [Preprint]. arXiv:2307.09702. [§4.11] [S]

---

## 9. Appendices

### Appendix A — Citation provenance ledger

The bibliography contains 110 entries. Their provenance distribution at v0.1:

- **[F] Fetched and read in full**: approximately 30 entries (verified directly during the surveys).
- **[S] Search-snippet only**: the remainder, requiring verification against the primary source before any specific number, page reference, or direct quotation is added to a thesis or paper draft.
- **[?] Inference / interpretation**: a small number of bridging interpretations marked inline.

For iterative refinement, the first task in each subsequent revision should be to upgrade [S] entries to [F] for any citation whose specific claim (number, methodology, page reference) the project relies on.

### Appendix B — Iterative-improvement notes

The following are known weaknesses and high-priority improvements for v0.3 and beyond.

**Resolved in v0.2 (primary-source verification pass):**

- *Corrected* — Sinhala sentiment F1 is **59.42 %** on the four-class task, not 84.58 % (which belongs to a separate binary study).
- *Corrected* — the ByT5-Sanskrit **+8.8** gain is on the Hackathon benchmark; on SIGHUM it is level with TransLIST.
- *Corrected* — ODKE+ **98.8 %** precision confirmed; the "35 % hallucination reduction" is not in the primary and was dropped.
- *Corrected attributions* — "A Comprehensive Evaluation of Biomedical EL Models" is **Kartchner et al.** (not Sevgili); the *Chonnam* heavy-metal review is **Sikder** (not Park); xMEN is **Borchert et al.** (not Borchmann).
- *Corrected* — SinLlama abstract states a "~10-million Sinhala corpus", not 303.9 M tokens; de Silva survey latest revision is v26 (Jan 2026).
- *Confirmed [F]* — Surya CER 0.76 % / WER 2.61 %; Adam & Kliegr 88 %P/44 %R; XL-BEL's 10 languages exclude all Indic; Saper 2004 (20 %) and 2008 (20.7 %); Zaveri 18 dims/4 categories; SinhalaMMLU 67 %/62 %; NSINA 506,932 / CC-BY-SA-4.0; Lakmal fastText sets; "BERTifying Sinhala" XLM-R dominance.
- *Still unconfirmed* — Joshi *et al.* (2020) per-language class-1 assignment for Sinhala (table not extractable from the primary; rests on the `lang2tax` companion data); SOLD sentence-vs-token F1 attribution (0.83/0.81 real but level-labels likely swapped).

**Outstanding for v0.5:**

1. **Merge the §8.1–§8.4 addendum entries into the main alphabetical bibliography**, and re-sort the three corrected entries (Kartchner, Sikder, Borchert) into place. *(Deferred across v0.2–v0.4 as low-value cosmetic reordering; the addendum blocks are clearly labelled and section-cross-referenced, so the merge is safe to batch into one careful pass.)*
2. **Inter-annotator-agreement statistics for KG triples specifically** — κ/α on triple correctness vs raw percentage agreement (flagged unsurveyed by the v0.4 evaluation round).
3. **PEG vs CFG expressiveness/ambiguity trade-offs** for the prose-template grammar, and parser-combinator tooling choice.
4. **Empirical evidence on whether TKDL actually reduced biopiracy** (patent-rejection counts vs counterfactual) — to ground the "defensive disclosure is insufficient" claim with numbers.
5. **Operational TK/BC-Label deployment case studies on biomedical datasets** (e.g. GBIF Indigenous-data-governance task group).
2. **Add a section on speech / multimodal Sinhala** if the project's scope ever expands to audio sources (OpenSLR-52, Whisper fine-tunes, Mozilla CommonVoice Sinhala).
3. **Add citations for Indic OCR newer than Surya**: arXiv:2602.16430 (production-scale OCR for India; Chitrapathak/Parichay).
4. **Expand §4.7 on schema-constrained extraction** with more 2024–2026 papers from the SPIREX/RELATE family.
5. **Add a §6.3 on reproducibility infrastructure** (DVC, MLflow, Snakemake, container-based reproducibility).
6. **Verify Sinhala-linguistics citations**: confirm Gair (1998) page references; locate the exact volume/page for Henadeerage (2002).
7. **Replace [no date] entries with accurate dates** where possible (OBO Foundry has versioned releases; POWO has a release-year on its data dumps).
8. **Add a glossary appendix** for IAST diacritics, Sinhala terms, and abbreviations used through the document.

---

## 10. Change log

| Version | Date | Author | Notes |
|---|---|---|---|
| v0.1 | 2026-05 | Project author | Initial consolidation of four parallel literature surveys (SOTA Rounds 1–3 + Sinhala-focused Round) into a single Harvard-cited document. ~110 bibliography entries; ~30 fetched + ~80 search-snippet. |
| v0.2 | 2026-05 | Project author | (a) **Primary-source verification pass** — fetched and checked ~22 key claims; corrected six factual errors (sentiment F1 84.58→59.42; ByT5 +8.8 Hackathon-not-SIGHUM; ODKE+ 35 %-hallucination dropped; SinLlama corpus size; de Silva date) and three mis-attributions (Kartchner, Sikder, Borchert). (b) **Added §3.5** global landscape of traditional-medicine digitisation (India/China/Korea/Japan/Africa/global), with the Sri Lanka gap statement and 21 new bibliography entries in §8.1. (c) Updated §6.1 gap #3 with the "first machine-readable Sri Lankan TM KG" claim. Provenance ledger: many [S] upgraded to [F]. |
| v0.3 | 2026-05 | Project author | Added five previously-missed areas (the interrupted survey round): **§5.5** active learning / annotation efficiency (diversity-first at tiny budgets; LLM-in-the-loop, 42–53× cheaper); **§5.3** reproducibility/determinism infrastructure (ACL checklist, Ten Simple Rules, Apptainer, byte-identical > statistical reproducibility framing); **§5.4** responsible release reconciling FAIR with the **CARE Principles** + 2024 WIPO TK Treaty + Sri Lanka TK law — **flags that blanket CC-BY-SA of the content layer should be reconsidered**; **§4.6** cross-lingual NER transfer (gov/news multiNER domain-mismatched, not transferable); **§7** domain-adaptation path (LoRA-adapt SinLlama + SiDiaC medical slice). 16 new bibliography entries in §8.2. |
| v0.4 | 2026-05 | Project author | **§5.6 annotation methodologies** — characterises the intended gazetteer→LLM-silver→human pipeline as machine-assisted/pre-annotation+correction over a weak-supervision stack; flags anchoring bias (40→81–87 % model agreement, +0.32–0.35 F1 inflation) as the dominant risk and a blind double-annotated gold subset as the fix; surveys distant supervision, Snorkel, self-/tri-training, confidence routing, and tooling (INCEpTION best fit). **§4.9** extended with unlabelled-KG evaluation (Gao 2019 sampling, Marchesin & Silvello 2025 Bayesian credible intervals, Knowledge-Vault LCWA, capture–recapture for recall). **§4.11** new — cascaded-FST (FASTUS) / wrapper-induction / grammar-constrained-decoding framing of the extraction architecture. **§5.4** deepened with the TKDL access-asymmetry critique, Adekola 2025, Local Contexts TK/BC Labels, Nagoya ABS, and the named Sri Lankan legal vacuum → concrete FAIR-metadata/CARE-governance model. 6 + 12 new bibliography entries (§8.3, §8.4). |

*Future revisions: add a new row per substantive update; keep entries terse.*

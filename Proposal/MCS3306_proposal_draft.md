# MCS 3306 — Individual Project in MSc in CS

# Research Proposal — DRAFT

> **Status:** working draft for supervisor review. Content is
> substantive; references in §11 have been verified (May 2026) against
> ACL Anthology, ACM DL, AAAI Proceedings, IEEE DataPort, Frontiers in
> Pharmacology, arXiv, JLM and the Cologne CDSL portal. Remaining open
> items: title polish, supervisor selection, conversion of the §9
> monospace Gantt to a graphical Gantt, and one pending verification
> noted inline (SinMorphy full author list). Move into the official
> `MCS3306 - Individual Project Proposal Template 2026.docx` before
> submission — UCSC requires that specific form.

---

## Personal Details

| Field | Value |
| --- | --- |
| Name with initials | _to fill_ |
| Full name | _to fill_ |
| Email | _to fill_ |
| Registration No. | _to fill_ |
| Phone | _to fill_ |
| Index No. | _to fill_ |

## Research Project Details

**Tentative title.** *Cross-Lingual Lexical Grounding for Information
Extraction in Sinhala Ayurvedic Texts: A Sanskrit-Bridge Knowledge-Graph
Approach.*

**Areas of research.** Natural Language Processing; Information
Extraction; Knowledge Representation; Low-Resource / Under-Resourced
Languages; Computational Lexicography.

**Supervisors.**

| Role | Name | Position | Organisation |
| --- | --- | --- | --- |
| Main (UCSC senior academic) | _to confirm_ | _to confirm_ | UCSC |
| Co-supervisor (optional) | _to confirm_ | _to confirm_ | _to confirm_ |

---

## 1. Research Problem

Sinhala is among the world's most under-resourced languages for Natural
Language Processing. No published Named-Entity-Recognition benchmark
exists for Sinhala; the language is agglutinative and morphologically
rich; and the largest publicly released Sinhala language models are
trained almost entirely on modern web register (Ranasinghe et al. 2025;
de Silva 2024). Domain-specialised Sinhala — the language of
traditional medicine, legal texts, religious literature, and historical
manuscripts — is therefore doubly under-resourced: under-modelled
*and* outside the training distribution of the few resources that do
exist.

The *Sri Lankan Ayurvedic Pharmacopoeia* is an authoritative,
state-sanctioned, multi-volume reference for the country's traditional
herbal medicine tradition, written entirely in Sinhala. Volume I,
covering 707 formula entries on pages 172–443, has a strongly
structured tabular layout that makes it tractable to digitise
automatically. The project hosting this proposal has already produced a
machine-readable, structured JSON corpus from this volume
(11 007 ingredient cells, 62 562 tokens, 7 100 vocabulary types). No
prior digital, queryable form of this knowledge existed. The corpus is
the first publicly available structured Sinhala Ayurvedic resource.

However, the corpus is not directly usable for downstream NLP. ~17 % of
its ingredient tokens are structural OCR artefacts; ~24 % of formula
names fail NFC Unicode normalisation; ingredient cells frequently leak
preparation-method prose; dosage uses three incompatible unit systems
(metric, traditional seed-weight, and mixed) with no type flag; and
~70 % of its vocabulary is composed of culturally and linguistically
specialised terms unknown to general Sinhala NLP tooling.

A critical, hitherto-unexploited observation drives this work. **A
large fraction of Sinhala Ayurvedic vocabulary is Sanskrit in origin**,
copied directly into Sinhala script (the *tatsama* register: *jvara* =
fever, *kṣaya* = consumption, *kvātha* = decoction, *bhasma* =
calcined ash, etc.). Sanskrit, by contrast, has well-developed NLP
infrastructure: the Cologne Digital Sanskrit Dictionaries (Hellwig,
n.d.), the Sanskrit Heritage Engine (Goyal and Huet 2016), Samsādhanī
(Kulkarni 2013), the Digital Corpus of Sanskrit (Hellwig 2010), and
recent neural systems including ByT5-Sanskrit (Nehrdich et al. 2024).
None of these resources is currently accessible from Sinhala script.
The bridge — a *Sinhala-to-Sanskrit lexical resolver* with rule-based
transliteration and morphological canonicalisation — would unlock the
Sanskrit ecosystem for a substantial fraction of the Sinhala Ayurvedic
vocabulary at zero manual-labelling cost.

**The research problem this proposal addresses:**

> Given an under-resourced Sinhala domain corpus and a well-resourced
> Sanskrit lexical ecosystem that shares much of its vocabulary, can
> we (a) construct a reliable cross-lingual lexical bridge between the
> two, (b) use the bridge to seed a domain knowledge graph for Sinhala
> traditional medicine, and (c) demonstrate measurable utility of that
> knowledge graph for downstream information-extraction tasks on
> Sinhala Ayurvedic text?

This is a falsifiable research question, achievable within the 15-credit
envelope, that produces three artefacts of independent value: a
publicly released cross-lingual lexical resource, the first Sinhala
Ayurvedic knowledge graph, and the first labelled Sinhala domain NER
corpus.

---

## 2. Literature Review

### 2.1 Sinhala NLP

The history of Sinhala NLP can be divided into a pre-transformer era
focused on rule-based morphological analysis (Kumarasinghe et al. 2021;
de Silva 2019) and word-embedding work (Lakmal et al. 2020), and a
recent transformer-era effort built around SinBERT (Dhananjaya et al.
2022), SinLlama (Aravinda et al. 2025), and the SINHALA-GLUE benchmark
with its accompanying encoder family at 0.3 B / 0.6 B / 1 B parameters
(Ranasinghe et al. 2025). SinhalaMMLU (Pramodya et al. 2025) provides
the first broad-coverage evaluation of LLMs on Sinhala, finding that
even the strongest commercial models (Claude 3.5 Sonnet, GPT-4o)
achieve only ~62–67 % average accuracy and struggle most in
culturally embedded domains.

**Critical gap.** None of the published Sinhala resources targets
classical or domain register. The largest freely available Sinhala
text corpus (NSINA, ~500 000 news articles) is exclusively modern web
register and contains negligible Ayurvedic vocabulary. No Sinhala
domain-specific named-entity benchmark exists; no Sinhala medical
terminology resource exists; no Sinhala→Sanskrit transliteration or
lexical bridge exists. Both Aksharamukha (Rajan, n.d.) and the
`indic-transliteration` library support Sinhala script transliteration
to IAST, but neither is connected to a Sanskrit lexical backend with
medical-vocabulary coverage.

### 2.2 Sanskrit NLP

Sanskrit, despite also being low-resource, has a comparatively rich
NLP infrastructure due to philological tradition and active research
groups. Core resources include the Digital Corpus of Sanskrit (Hellwig
2010–; ~650 000 annotated sentences), the Cologne Digital Sanskrit
Dictionaries (Monier-Williams 1899), the Sanskrit Heritage Engine for
morphological analysis and sandhi-splitting (Goyal and Huet 2016), the
Samsaadhanii platform with its morphological analyser (Kulkarni and
Shukl 2009), and recent byte-level transformer models for word
segmentation, dependency parsing and OCR post-correction (Nehrdich
et al. 2024). The Heritage Engine is accessible programmatically
through both a CGI web service and the `sanskrit_parser` Python
wrapper. None of these resources accepts Sinhala script as input.

### 2.3 Traditional Medicine NLP

Sanskrit Ayurvedic NLP is an active small field. AyurKOSH (Mirasdar
et al. 2026) is a structured database of diseases, symptoms,
formulations and herbal components with full Ayurvedic pharmacology
metadata (Rasa, Guna, Virya, Vipaka, Karma) and herb substitution
relationships. GRAYU (Joshi et al. 2026) links 1 039 traditional
formulations to ~13 000 indigenous plants and provides
plant–phytochemical, plant–disease and plant–formulation association
counts in the millions. The IIIT Hyderabad AyurNLP group has produced
several papers on Sanskrit Ayurvedic information extraction. All of
this work is Sanskrit- or Hindi-medium and has no Sinhala
cross-reference.

### 2.4 Low-Resource NER and Knowledge-Graph-Augmented Extraction

Multilingual transfer through mBERT (Devlin et al. 2019) and
XLM-RoBERTa (Conneau et al. 2020) is the conventional approach to
low-resource NER, supplemented by language-adapter techniques such as
MAD-X (Pfeiffer et al. 2020). These methods *assume the existence of a
labelled corpus in the target language* and do not address corpus
construction. Where a knowledge graph or gazetteer is available,
distantly-supervised and lexicon-augmented NER methods (Shang et al.
2018; Zhang and Yang 2018) have been shown to outperform unconstrained
neural models on domain-specific tasks. The historical-IE survey of
Ehrmann et al. (2023) covers newspapers, legal texts, and
Latin/Romance historical corpora; it does not include any Sinhala or
traditional-medicine sources.

### 2.5 Research Gap

Synthesising the four strands above, this proposal identifies the
following gaps:

1. **No published Sinhala domain-specific NER corpus** — let alone for
   Ayurvedic medicine.
2. **No machine-readable bridge between Sinhala-script and Sanskrit
   lexical resources**, despite the substantial vocabulary overlap in
   the medical domain.
3. **No knowledge graph for traditional Sri Lankan medicine.**
4. **No empirical study** of whether and how cross-lingual lexical
   grounding (Sinhala→Sanskrit) supports downstream IE in Sinhala
   medical text.

The work described here directly addresses gaps 1–4.

---

## 3. Research Questions

**RQ1.** To what extent can existing Sanskrit lexical resources be
made accessible to Sinhala Ayurvedic text via a rule-based
transliteration bridge with morphological canonicalisation, and what
is the per-field coverage of such a bridge on a representative corpus?
*(Key references: Rajan n.d.; Hellwig 2010–; Goyal and Huet 2016.)*

**RQ2.** When the resolved Sanskrit terminology is structured into a
domain knowledge graph alongside the inherent relational structure of
the pharmacopoeia corpus (formula → ingredient, formula → indication,
etc.), does the resulting KG provide useful structural priors for
entity-extraction models on Sinhala Ayurvedic text — and if so, on
which entity types and by what margin?
*(Key references: Shang et al. 2018; Zhang and Yang 2018.)*

**RQ3.** How does resolver performance decompose across the
linguistic register categories present in the corpus — *tatsama*
(direct Sanskrit borrowing), *tadbhava* (phonologically nativised
Sanskrit), and *deśya* / *vernacular* (genuinely Sinhala or
non-Sanskrit borrowings) — and what is the optimal architectural
boundary between rule-based resolution and external-lexicon-driven
resolution?
*(Key references: Geiger 1938; Jayaweera 1981; Sorata Thero 1952.)*

---

## 4. Research Objectives

The research questions decompose into six concrete objectives.

* **O1.** Build a robust three-tier Sinhala→Sanskrit lexical resolver
  with (i) an offline category router using Sinhala orthographic
  signals, (ii) a direct Monier-Williams lookup via Aksharamukha
  transliteration with Sinhala-inflection canonicalisation, and
  (iii) a compound-splitting tier using a memory-isolated wrapper
  around the Sanskrit Heritage Engine. *(Substantial preliminary work
  on this objective is described in §10 and Appendix A.)*

* **O2.** Extend the resolver with (i) Sinhala-specific IAST
  normalisation (handling of ĕ, ŏ, æ, ḻ, n̆), (ii) an OCR-variant
  fuzzy-matching pass against Monier-Williams headwords, and
  (iii) Sinhala converb and inflectional morphology coverage.

* **O3.** Construct a Sinhala Ayurvedic terminology knowledge graph
  with the schema
  `{FORMULA, INGREDIENT, INDICATION, ADJUVANT, FORMULA_TYPE,
  PREPARATION_METHOD}` and edges
  `{CONTAINS, IS_TYPE, DOSED_WITH, CO_OCCURS, TREATS, VARIANT_OF,
  REFERENCES}`. Phase 1 edges derive directly from the structured
  JSON without NLP; phase 2 derives from the resolver output;
  phase 3 includes light-NLP-derived edges (REFERENCES via regex,
  TREATS via rule-based dosha-tagger).

* **O4.** Build a token-level NER annotated subset of the Vol I
  corpus with the entity inventory
  `{INGREDIENT, FORMULA_NAME, QUANTITY, UNIT, INDICATION,
  PREPARATION_VERB, ADJUVANT, CROSS_REF, ARTEFACT}`. Target an
  initial 200 entries (~30 % of Vol I), expanding to full coverage
  if time permits.

* **O5.** Empirically measure the contribution of the resolver and
  the KG to NER performance: (i) a gazetteer baseline using
  only string-match; (ii) a CRF using Sinhala morphological,
  positional, and resolver-derived features; (iii) the same CRF
  augmented with KG-derived entity-candidate features. Report F1
  per entity type with an ablation over feature groups.

* **O6.** Public release: the resolver code, the terminology lexicon,
  the knowledge graph, the labelled NER corpus, the trained CRF
  models, and the validation framework, under an open licence
  compatible with future Ayurvedic NLP research.

---

## 5. Scope

**In scope.**

* The structured Vol I corpus (707 entries, pages 172–443).
* The *tatsama* register (Sanskrit-script terms borrowed unchanged
  into Sinhala) as the primary resolver target.
* Knowledge graph construction up to Phase 3 (regex-derived references
  + rule-based dosha/action tagging).
* Single-language NER on structured pharmacopoeia text using
  conditional random fields with linguistic + KG features.
* Programmatic and cross-source (POWO, Wikidata, AyurKOSH)
  validation of resolver outputs.

**Out of scope.**

* Volumes II and III of the pharmacopoeia — physical copies are in
  hand but scanning, OCR, and pipeline-tuning are deferred to future
  work.
* Paragraph-level traditional manuscripts other than the
  pharmacopoeia. Schema alignment for free-prose IE is a logical
  follow-on but is outside the 15-credit envelope.
* A comprehensive *tadbhava* etymological lexicon (Sorata Thero,
  Geiger, Jayaweera). Required for full coverage of the resolver's
  "other" bucket but expert-bound; the resolver routes such terms to
  an explicit unresolved category rather than guessing.
* The full clinical-condition taxonomy (R4-Stage B in the project's
  internal roadmap), which requires an Ayurvedic physician + a
  biomedical professional on the design team.
* Metrical analysis of verse manuscripts. Out of scope by virtue of
  scale.
* Multilingual transformer training. XLM-RoBERTa fine-tuning and
  retrieval-augmented LLM extraction are listed as natural next
  steps; under the 15-credit envelope, CRF with engineered features
  is the most defensible model choice given corpus size.

---

## 6. Research Methodology

The project follows a five-phase, partially overlapping methodology.

### Phase A — Resource construction (Months 1–3)

* Extend the existing tatsama resolver per Objective O2: Sinhala-IAST
  normalisation, OCR-variant fuzzy matching, expanded inflectional
  suffix coverage. Validate against an anchor list of ~30 well-known
  tatsama terms and against ~10 vernacular negative controls.
* Cross-reference resolver outputs against POWO (Kew, n.d.) for
  botanical Latin binomials and against Wikidata for general taxa.
  Report a precision figure against these external sources.

### Phase B — Corpus engineering (Months 2–4)

* Global NFC normalisation; ZWJ-aware field-key handling; artefact
  stripping for ingredient cells; a rule-based reclassifier that
  routes preparation-method prose out of the ingredient list;
  dosage-unit typing (metric / seed-weight / mixed); cross-reference
  resolution for `සංස්කරණය` "see formula N" patterns.

### Phase C — Knowledge graph construction (Months 3–6)

* Phase 1 (no NLP): `CONTAINS`, `IS_TYPE`, `DOSED_WITH`, `CO_OCCURS`
  edges directly from structured JSON. Persistence in NetworkX with
  a SQLite snapshot for query.
* Phase 2 (resolver-derived): `VARIANT_OF` edges linking surface
  ingredient forms to canonical Sanskrit lemmas. Latin-binomial
  attachment for botanical nodes.
* Phase 3 (light NLP): `REFERENCES` via regex over `සංස්කරණය`;
  `TREATS` via a rule-based dosha/action tagger covering
  *vā/pitta/sleṣma/sannipāta* and a closed verb set (*naśayati*,
  *śamayati*, *hanti*).

### Phase D — Annotation (Months 4–8)

* Annotation schema: pilot on 50 entries to lock entity definitions
  and disambiguate edge cases. Inter-annotator agreement target
  Cohen's κ ≥ 0.75 on a double-coded 20-entry subset.
* Token-level annotation in BIO format. Tool: a lightweight web
  interface (Doccano or equivalent) seeded with resolver-derived
  entity candidates.
* Target: 200 entries for the model-training corpus; extend to
  full 707 if time permits in Phase E.

### Phase E — Modelling and Evaluation (Months 6–10)

* Three systems trained and evaluated under 10-fold cross-validation
  on the annotated entries:

  1. **Gazetteer baseline.** String-match against the resolver's
     lexicon. Establishes the lower bound that a dictionary alone
     achieves.
  2. **Feature-rich CRF.** Character-n-gram, suffix, and column-zone
     positional features (the structured layout is itself a strong
     signal), plus resolver-derived "is-tatsama / lemma / Latin
     binomial" indicator features.
  3. **KG-augmented CRF.** Adds soft features from the knowledge
     graph: degree in `CONTAINS`, `CO_OCCURS` cluster membership,
     KG-canonical-form match.

* **Metrics.** F1 per entity type (micro and macro); precision and
  recall on the validation set; ablation showing the marginal
  contribution of each feature group.
* **Statistical significance.** Pairwise bootstrap-resampled
  significance tests between systems (Berg-Kirkpatrick et al. 2012).

### Phase F — Reporting (Months 10–12)

* Thesis write-up; defence; final code/data release.

---

## 7. Novelty and Expected Contribution

The work produces four distinct contributions to computing:

* **C1 — Methodological.** A reusable, memory-isolated subprocess
  architecture for safely combining a graph-search-heavy NLP library
  (`sanskrit_parser`) with a memory-light orchestration pipeline.
  This architecture is general (RLIMIT-bounded workers + SIGALRM +
  resumable JSONL persistence) and applicable to any case where a
  precision-oriented analysis tool has unbounded per-call memory
  behaviour. Preliminary implementation has demonstrated zero
  OOM-kills across 21 worker batches on the full residual corpus.

* **C2 — Resource.** The first machine-readable cross-lingual
  lexical bridge between Sinhala script and Sanskrit lexical
  resources, with empirically measured per-field coverage on a
  domain corpus. Released as open code + JSON lexicons.

* **C3 — Knowledge representation.** The first knowledge graph of
  traditional Sri Lankan medicine, with documented schema,
  provenance, and edge-construction protocols. Sized at ~15 000
  edges from Vol I alone; designed to compose cleanly with Vols II
  and III when those are digitised in future work.

* **C4 — Empirical result.** A controlled measurement of the
  contribution of cross-lingual lexical grounding and knowledge-graph
  features to NER performance on a Sinhala domain corpus, with a
  reproducible ablation. This is the first quantification of the
  KG-grounding effect for any Sinhala-domain task.

Each contribution stands independently: C1 is a software-architecture
result; C2 and C3 are released resources; C4 is the empirical study
that ties them together. C2 alone would be a publishable resource at
LREC-COLING.

---

## 8. Evaluation

### 8.1 Resolver Evaluation

* **Anchor-probe precision.** Hand-curated list of ~30 unambiguous
  tatsama terms with known Sanskrit lemmas (*jvara, kṣaya, śvāsa,
  kvātha, ghṛta, triphalā, ...*). Target ≥ 95 % exact-match.
* **Negative-control precision.** ~10 vernacular Sinhala terms
  (*තිප්පිලි, ඉඟුරු, එන්සාල්, කොත්තමල්ලි*) — must remain in the "other"
  bucket. Target 100 % correct rejection.
* **POWO / Wikidata cross-source agreement.** For every botanical
  binomial in the resolver's seed, query POWO; record the modern
  accepted name and family. Report precision against POWO and the
  rate at which MW's 19th-century binomials need replacement.
* **Compound-segmentation soundness.** Every multi-segment recovery
  must (i) concatenate back to within a small edit distance of the
  original IAST, and (ii) have all segments resolve as
  Monier-Williams headwords. Target: zero violations after merge.

### 8.2 Knowledge-Graph Evaluation

* **Structural metrics.** Node and edge counts by type; degree
  distribution; cluster modularity; connected-component count.
* **Edge precision.** Stratified random sample of 50 edges per type;
  judged correct / incorrect by the annotator team.
* **KG completeness.** Per-formula completeness (% of expected
  edge types present).

### 8.3 NER Evaluation

* **Train/test protocol.** 10-fold cross-validation over annotated
  entries, with folds drawn at the *formula* (not token) level to
  avoid leakage.
* **Metrics.** Micro-F1, macro-F1, and per-entity-type F1.
* **Ablation.** Marginal contribution of each feature group:
  morphological, positional, resolver-derived, KG-derived.
* **Statistical test.** Paired bootstrap-resampled significance
  between Gazetteer, CRF-features, and CRF-features+KG.

### 8.4 Benchmark Data Availability

| Resource | Source | Status |
| --- | --- | --- |
| Vol I structured corpus | Pharmacopoeia OCR pipeline | **In hand**, 707 entries |
| Vol I row-level OCR | GCV batch outputs | In hand |
| Monier-Williams Sanskrit-English | Cologne CDSL | Public download, in hand |
| POWO taxonomy | Royal Botanic Gardens, Kew | Public API |
| Wikidata | Wikimedia | Public SPARQL |
| AyurKOSH | IEEE DataPort | Public |
| GRAYU | NCBS | Public web interface |
| Vol II / III | Physical copies | Available; out of scope here |

All evaluation data is available now; nothing depends on a third party
to grant access.

---

## 9. Research Plan and Timeline

```
Month             1   2   3   4   5   6   7   8   9  10  11  12
Phase A           [████████]
Phase B               [██████████]
Phase C                   [████████████]
Phase D                       [████████████████]
Phase E                               [████████████████]
Phase F                                           [████████████]
Annotation IAA            ▲
Mid-thesis review                          ▲
Pilot KG release                  ▲
Resolver v1 release       ▲
Final code release                                       ▲
Thesis draft                                          ▲
Defence                                                         ▲
```

* **Month 2.** Resolver v1 release (extension of preliminary work).
  Annotation pilot launched.
* **Month 4.** Inter-annotator agreement study completed.
* **Month 6.** Knowledge graph Phase 1 + 2 released.
* **Month 8.** Annotation reaches 200 entries; CRF baseline trained.
* **Month 10.** Full ablation completed; results table frozen.
* **Month 11.** Thesis first draft.
* **Month 12.** Defence and final submission.

### Risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Annotation slower than budget | Medium | Medium | Reduce target from 707 to 200 entries; report on partial coverage. |
| KG features fail to improve NER | Low | Low | Negative result is still publishable; this *is* the empirical study. |
| Resolver coverage on prose lower than ingredients | Low | Low | Already observed (66 % vs 81 %); reported as a per-field result. |
| Supervisor / co-supervisor unavailable | Low | High | Confirm at submission time; mitigated if main supervisor is UCSC permanent senior staff. |
| Computational requirements exceed local resource | Low | Low | CRF + small lexicons; no GPU required. |

---

## 10. List of Deliverables

| # | Deliverable | Form | Audience |
| --- | --- | --- | --- |
| D1 | Sinhala→Sanskrit lexical resolver | Python package, MIT-licensed | NLP researchers; downstream IE projects |
| D2 | Sinhala Ayurvedic terminology lexicon | JSON, with provenance per term | NLP; lexicography; AYUSH community |
| D3 | Sinhala Ayurvedic knowledge graph | NetworkX + SQLite + RDF dump | Knowledge representation; clinical research |
| D4 | Labelled NER corpus (BIO) | CoNLL-style + JSON | NLP benchmark; first Sinhala domain NER set |
| D5 | Trained NER models (CRF) | Serialised model files | Reproduction; downstream tools |
| D6 | Validation framework | Python script + report template | Resolver consumers; quality auditing |
| D7 | Thesis report | PDF, UCSC format | Examination |
| D8 | Conference paper draft | LaTeX, target LREC-COLING or ACL Findings | Peer review |

Items D1–D6 are released publicly under an open licence
(MIT for code, CC-BY-SA for data) on completion of Phase E.

---

## 11. References

> Citations below have been verified against ACL Anthology, ACM DL,
> AAAI Proceedings, IEEE DataPort, NCBS / Frontiers in Pharmacology,
> arXiv, the Journal of Language Modelling, and the Cologne Digital
> Sanskrit Dictionaries portal as of May 2026.

Aravinda, H. W. K., Sirajudeen, R., Karunathilake, S., de Silva, N.,
Ranathunga, S. and Kaur, R. (2025) 'SinLlama — A large language
model for Sinhala', arXiv preprint arXiv:2508.09115. Available at:
https://arxiv.org/abs/2508.09115.

Berg-Kirkpatrick, T., Burkett, D. and Klein, D. (2012) 'An empirical
investigation of statistical significance in NLP', in *Proceedings of
the 2012 Joint Conference on Empirical Methods in Natural Language
Processing and Computational Natural Language Learning (EMNLP-CoNLL
2012)*. Jeju Island, Korea: ACL, pp. 995–1005.

Conneau, A., Khandelwal, K., Goyal, N., Chaudhary, V., Wenzek, G.,
Guzmán, F., Grave, E., Ott, M., Zettlemoyer, L. and Stoyanov, V.
(2020) 'Unsupervised cross-lingual representation learning at scale',
in *Proceedings of the 58th Annual Meeting of the Association for
Computational Linguistics*. ACL, pp. 8440–8451.

de Silva, N. (2019) 'Survey on publicly available Sinhala natural
language processing tools and research', arXiv preprint
arXiv:1906.02358. Available at: https://arxiv.org/abs/1906.02358.

Devlin, J., Chang, M.-W., Lee, K. and Toutanova, K. (2019) 'BERT:
Pre-training of deep bidirectional transformers for language
understanding', in *Proceedings of the 2019 Conference of the North
American Chapter of the Association for Computational Linguistics:
Human Language Technologies, Volume 1 (Long and Short Papers)*.
Minneapolis: ACL, pp. 4171–4186.

Dhananjaya, V., Demotte, P., Ranathunga, S. and Jayasena, S. (2022)
'BERTifying Sinhala — A comprehensive analysis of pre-trained
language models for Sinhala text classification', in *Proceedings of
the Thirteenth Language Resources and Evaluation Conference
(LREC 2022)*. Marseille: ELRA. Available at:
https://aclanthology.org/2022.lrec-1.803/.

Ehrmann, M., Hamdi, A., Linhares Pontes, E., Romanello, M. and Doucet,
A. (2023) 'Named entity recognition and classification in historical
documents: a survey', *ACM Computing Surveys*, 56(2), article 27.
DOI: 10.1145/3604931.

Geiger, W. (1938) *A grammar of the Sinhalese language*. Colombo:
Royal Asiatic Society Ceylon Branch.

Goyal, P. and Huet, G. (2016) 'Design and analysis of a lean
interface for Sanskrit corpus annotation', *Journal of Language
Modelling*, 4(2), pp. 145–182.

Hellwig, O. (2010–) *DCS — The Digital Corpus of Sanskrit*. Available
at: http://www.sanskrit-linguistics.org/dcs/ (accessed 23 May 2026).

Jayaweera, D. M. A. (1981) *Medicinal plants used in Ceylon*. Colombo:
National Science Council of Sri Lanka.

Joshi, S., Pathak, A., Regati, D. R., Menon, R., Ajith, D. S.,
Sheshadri, A., Viswanathan, N., Ray, P., Koul, V., Panda, P.,
Bhambore, S. A., Verma, S., Sinha, A., Shafi, K. M., Pavalam, M. and
Sowdhamini, R. (2026) 'GRAYU: graph-based database integrating
Ayurvedic formulations, medicinal plants, phytochemicals and
diseases', *Frontiers in Pharmacology*, 16, article 1727224. DOI:
10.3389/fphar.2025.1727224.

Kew Royal Botanic Gardens (n.d.) *Plants of the World Online (POWO)*.
Available at: https://powo.science.kew.org (accessed 23 May 2026).

Kulkarni, A. and Shukl, D. (2009) 'Sanskrit morphological analyser:
some issues and solutions'. Bhartiya Anuvad Parishad / Department of
Sanskrit Studies, University of Hyderabad. Available at:
https://sanskrit.uohyd.ac.in/faculty/amba/PUBLICATIONS/papers/bhk.pdf.

Kumarasinghe, K. et al. (2021) 'SinMorphy: a morphological analyzer
for the Sinhala language', in *Proceedings of the IEEE conference*.
IEEE Xplore document 9525636. DOI: 10.1109/MERCon52712.2021.9525636.
*(verify full author list before submission)*

Lakmal, D., Ranathunga, S., Peramuna, S. and Herath, I. (2020)
'Word embedding evaluation for Sinhala', in *Proceedings of the
Twelfth Language Resources and Evaluation Conference (LREC 2020)*.
Marseille: ELRA, pp. 1874–1881.

Mirasdar, S., Bedekar, M., Patankar, H. and Gujar, Y. (2026) *AyurKOSH
dataset: a machine-readable Ayurvedic knowledge resource for
knowledge graph and computational intelligence*. IEEE Dataport.
DOI: 10.21227/58ej-wz87.

Monier-Williams, M. (1899) *A Sanskrit-English dictionary*. Oxford:
Clarendon Press.

Nehrdich, S., Hellwig, O. and Keutzer, K. (2024) 'One model is all
you need: ByT5-Sanskrit, a unified model for Sanskrit NLP tasks', in
*Findings of the Association for Computational Linguistics: EMNLP
2024*. Miami: ACL, pp. 13742–13751.

Pfeiffer, J., Vulić, I., Gurevych, I. and Ruder, S. (2020) 'MAD-X:
An adapter-based framework for multi-task cross-lingual transfer',
in *Proceedings of the 2020 Conference on Empirical Methods in
Natural Language Processing (EMNLP)*. ACL, pp. 7654–7673.

Pramodya, A., Nelki, N., Shalinda, H., Liyanage, C., Sakai, Y.,
Pushpananda, R., Weerasinghe, R., Kamigaito, H. and Watanabe, T.
(2025) 'SinhalaMMLU: a comprehensive benchmark for evaluating
multitask language understanding in Sinhala', in *Proceedings of the
2025 Conference on Empirical Methods in Natural Language Processing
(EMNLP 2025)*. ACL, pp. 32943–32961.

Rajan, V. (n.d.) *Aksharamukha — Indic script converter* [software].
Available at: https://www.aksharamukha.com and
https://github.com/virtualvinodh/aksharamukha (accessed 23 May 2026).

Ranasinghe, T., Hettiarachchi, H., Naradde Vidana Pathirana, N. C.,
Premasiri, D., Uyangodage, L., Nanomi Arachchige, I., Plum, A.,
Rayson, P. and Mitkov, R. (2025) 'Sinhala encoder-only language
models and evaluation', in *Proceedings of the 63rd Annual Meeting
of the Association for Computational Linguistics (Volume 1: Long
Papers)*. ACL, pp. 8623–8636.

Shang, J., Liu, L., Gu, X., Ren, X., Ren, T. and Han, J. (2018)
'Learning named entity tagger using domain-specific dictionary',
in *Proceedings of the 2018 Conference on Empirical Methods in
Natural Language Processing (EMNLP)*. Brussels: ACL, pp. 2054–2064.

Shi, B. and Weninger, T. (2018) 'Open-world knowledge graph
completion', in *Proceedings of the Thirty-Second AAAI Conference on
Artificial Intelligence (AAAI-18)*. New Orleans: AAAI Press,
pp. 1957–1964. DOI: 10.1609/aaai.v32i1.11535.

Sorata Thero, W. (1952) *Sri Sumangala Sinhala Śabdakośaya*. Colombo:
Cultural Affairs Department of Sri Lanka.

Zhang, Y. and Yang, J. (2018) 'Chinese NER using lattice LSTM', in
*Proceedings of the 56th Annual Meeting of the Association for
Computational Linguistics (Volume 1: Long Papers)*. Melbourne: ACL,
pp. 1554–1564.

---

## Any Other Additional Information

### Appendix A — Preliminary work and feasibility evidence

Substantial preliminary work, documented in the project's
`PROGRESS_NOTE.md`, demonstrates the technical feasibility of the
core methodology before this proposal:

1. **Tatsama resolver, three tiers.** Implemented and benchmarked on
   the full Vol I corpus. Resolution rates: **81 % on ingredient
   types, 76 % on formula-name types, 66 % on prose types**, against
   the Monier-Williams Sanskrit-English Dictionary. The three tiers
   are (i) direct lookup with Sinhala suffix canonicalisation;
   (ii) dictionary-driven compound segmentation; and (iii) the
   Sanskrit Heritage Engine via `sanskrit_parser` in
   memory-isolated subprocess workers.

2. **Memory-isolated worker architecture.** The Sanskrit Heritage
   Engine retains 5–55 MiB per call; a naïve in-process run was
   OOM-killed. The mitigation — `RLIMIT_AS`-bounded subprocess
   workers with per-word `SIGALRM` timeouts, line-delimited JSONL
   I/O, and resumable persistence — completed 1 015 residual
   tokens in 21 batches with zero OOM events.

3. **Botanical seed.** 120 ingredients resolved with embedded
   Latin binomials in their Monier-Williams glosses, yielding 85
   distinct candidate binomials (top: *Grislea tomentosa* = ධාතකී,
   *Cerasus puddum* = පද්මකාෂ්ඨ, *Terminalia chebula* = haritakī,
   *Phyllanthus emblica* = āmalakī). Awaits taxonomic-synonym
   resolution against POWO and a botanist's curation pass.

4. **Validation framework.** A three-layer validation plan
   (programmatic internal-consistency checks, cross-source agreement
   with POWO and Wikidata, expert spot-check on a stratified random
   sample) has been designed and the first two layers are
   implementable from existing tools.

5. **Reproducibility.** All preliminary code is in a `.venv` with
   pinned dependencies; the Monier-Williams data, the resolver
   output, and the parser-recovery JSONL are all on disk. The
   pipeline has been re-run end-to-end multiple times.

### Appendix B — Notes on supervisor selection

The work spans natural language processing, computational
linguistics, and knowledge representation, with a domain anchor in
Ayurvedic medicine. A main supervisor with experience in (any of)
multilingual NLP, low-resource language processing, knowledge
graphs, or computational philology of South Asian languages would
be the strongest match. A co-supervisor from the medical / Ayurvedic
domain would substantially strengthen the validation phase.

---

*End of draft.*

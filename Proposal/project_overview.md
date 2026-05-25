# Project Overview

**A Reproducible System for Knowledge-Graph Extraction from Sinhala Traditional Medicine Literature, Trained Using the Sri Lankan Ayurvedic Pharmacopoeia**

---

## Computational Techniques and CS Contributions at Each Stage

```
+-----------------------------------------------------------------------------------+
|                        COMPUTER SCIENCE PROBLEM SPACE                              |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  LOW-RESOURCE NLP          CROSS-LINGUAL IE        KNOWLEDGE REPRESENTATION       |
|  (no labelled data,        (Sinhala --> Sanskrit    (schema-constrained,           |
|   no domain models,         lexical bridge with     provenance-per-fact,           |
|   Joshi class-1 lang)       no published prior)     reproducible-by-construction)  |
|                                                                                   |
+-----------------------------------------------------------------------------------+

STAGE         COMPUTATIONAL TECHNIQUE                    CS FIELD
-----         -------------------------                  --------

[OCR +        Spatial layout analysis:                   Document understanding,
 Structural   - Normalised bounding-box clustering       Computer vision
 Recovery]      (y-tolerance threshold = 0.012)
              - Column-zone finite-state machine
                (x-coordinate encodes semantic role)
              - Cross-page state continuation
                         |
                         v
[Lexicon      Table extraction as structured             Information extraction,
 Mining]      induction (Kushmerick 2000):               Wrapper induction
              - Pattern-driven row parsing
              - Multi-system unit ontology design
              - NFC Unicode canonicalisation
                         |
                         v
[Cross-       Cascade architecture for cross-lingual     Computational linguistics,
 Lingual      entity normalisation:                      Cross-lingual NLP
 Resolver]    - Phonotactic binary classifier
                (regex over Unicode character classes,
                 formalises the suddha/misra distinction)
              - Transliteration via finite transducer
                (Aksharamukha: Sinhala --> IAST)
              - Dictionary lookup with morphological
                suffix stripping (6 nominal endings)
              - Compound-word segmentation
                (recursive splitting, dictionary-driven)
              - Sandhi analysis via constraint solver
                (memory-isolated subprocess with
                 RLIMIT_AS + SIGALRM resource bounding)
              - Fallback: corpus-internal substitute
                glossary as a lookup table
                         |
                         v
[Gazetteer    Aho-Corasick automaton (O(n) multi-        String algorithms,
 Matching]    pattern matching):                          Finite automata
              - 1,100+ surface forms
              - Longest-match-with-priority resolution
              - Overlap resolution via deterministic
                tie-breaking (longer > earlier > alpha)
                         |
                         v
[Sentence     Register-aware segmentation:               NLP preprocessing,
 Segmenter]   - Sinhala clause-boundary detection        Computational morphology
              - Verbal-participle recognition
                (SOV clause chaining via -a/-i suffixes)
              - Field-label classification
                (domain-specific discourse structure)
                         |
                         v
[Span         Schema-typed entity labelling:             Named Entity Recognition,
 Labeller]    - Gazetteer hits with field-context-       Distant supervision
                biased type disambiguation
              - Quantity parsing (multi-system unit
                registry with dynamic conversion)
              - Pluggable second-oracle interface
                (CRF / neural tagger slot)
              - NIL recording for iteration loop
                         |
                         v
[Relation     Cascaded Finite-State Transducer           Information Extraction,
 Extraction]  (FASTUS architecture, Hobbs et al. 1997):  Formal language theory
              - Field-state-driven relation emission
              - Schema-constrained reject-at-emission
                (only domain/range-valid triples pass)
              - Verb-chain extraction for preparation
                steps (procedural text understanding)
              - Deduplication with mention-count
              - Char-span provenance binding
                         |
                         v
[KG           Graph construction with:                   Knowledge Representation,
 Builder]     - SHACL constraint validation              Semantic Web
              - External-authority binding
                (ICD-11 TM2, POWO/IPNI, ChEBI)
              - Provenance per node and per edge
              - Four serialisation formats
                (Cypher, JSON-LD, RDF/Turtle, JSONL)
                         |
                         v
[Audit +      Three-guarantees verification:             Software verification,
 Iteration    - Reproducibility: SHA-256 manifest,       Reproducible research
 Loop]          stable sorts, no set iteration
              - Completeness: token-coverage metric
                with stopword-filtered gap report
              - Exactness: char_span == surface text
              Module-A-driven NIL triage
              (phonotactic classifier routes gaps to
               resolver vs gazetteer vs ignore)
                         |
                         v
[NER          Conditional Random Field (CRF):            Machine Learning,
 Model]       - Distant supervision from structured      Sequence labelling
                corpus (11,000 labelled instances)
              - Feature engineering:
                  token, suffix, gazetteer-class,
                  resolved-lemma class, KG-node-type,
                  ICD-11 hit, materia-medica section
              - Three-arm ablation:
                  A: gazetteer baseline
                  B: distant-supervised CRF
                  C: KG-augmented CRF
              - Bootstrap confidence intervals on F1
                         |
                         v
[Evaluation]  Statistical estimation without gold:       Evaluation methodology,
              - Stratified-sample precision with         Bayesian statistics
                Bayesian credible intervals
                (Marchesin & Silvello 2025)
              - Capture-recapture recall estimation
                (Lincoln-Petersen)
              - Gwet's AC1 for inter-annotator
                agreement (prevalence-robust)
              - Bootstrap hypothesis testing for
                NER F1 differences
```

---

## System Architecture (data flow)

```
 INPUT                          SYSTEM CONSTRUCTION                         OUTPUT
 (Training Corpus)              (Phase I: M1-M9)                            (Deliverables)
                                                                        
+========================+                                              +========================+
|  Ayurvedic             |                                              |  KNOWLEDGE GRAPH       |
|  Pharmacopoeia Vol I   |                                              |  (First Sri Lankan     |
|  (525 pages, Dept.     |                                              |   TM Knowledge Graph)  |
|   of Ayurveda, SL)     |                                              |                        |
+========================+                                              |  ~4,000+ nodes         |
         |                                                              |  ~12,000+ edges        |
         |                                                              |  ICD-11 TM2 bindings   |
         v                                                              |  POWO/IPNI bindings    |
+------------------+                                                    |  ChEBI bindings        |
| OCR + Structural |                                                    |  Triple-level          |
| Recovery         |  pp.172-443 tabular formulas                       |   provenance           |
| (M1-M2)          |                                                    +========================+
+------------------+                                                             ^
         |                                                                       |
         | ~850 structured                                                       |
         | formula entries                                                       |
         v                                                                       |
+------------------+     +------------------+     +------------------------+     |
| Lexicon          |     | Sinhala-Sanskrit |     | EXTRACTION SYSTEM      |     |
| Extraction       |     | Cascade Resolver |     | (Core Deliverable)     |     |
| (M3)             |     | (M4-M5)         |     | (M7-M9)                |     |
|                  |     |                  |     |                        |     |
| - Raw materials  |     | - Phonotactic    |     | +--------------------+ |     |
|   (771 plants/   |     |   classifier     |     | | Gazetteer-based    | |     |
|    minerals/     |     | - Transliteration|     | | span labeller      | |     |
|    animal)       |     |   + MW lookup    |     | | (Aho-Corasick)     | |     |
| - Substitutes    |     | - Compound-word  |     | +--------------------+ |     |
|   (143 pairs)    |     |   segmentation   |     |          |             |     |
| - Therapeutic    |     | - Sandhi         |     |          v             |     |
|   groups         |     |   analysis       |     | +--------------------+ |     |
|   (50 ganas)     |     | - Substitute     |     | | Sentence segmenter | |     |
| - Unit systems   |     |   glossary       |     | | + verb-chain       | |     |
|   (43 symbols    |     |   fallback       |     | | extraction         | |     |
|    x 6 systems)  |     |                  |     | +--------------------+ |     |
+------------------+     +------------------+     |          |             |     |
         |                        |               |          v             |     |
         |   Closed-vocabulary    |  Resolved     | +--------------------+ |     |
         |   knowledge base       |  lemmas       | | Schema-constrained | |     |
         +----------+-------------+               | | relation emitter   |-------+
                    |                             | | + provenance        | |
                    v                             | +--------------------+ |
         +-------------------+                    |          |             |
         | External-Authority|                    |          v             |
         | Enrichment (M6)   |                    | +--------------------+ |
         |                   |                    | | Three-guarantees   | |
         | - POWO/IPNI       |                    | | audit gates        | |
         |   (plant IDs)     |                    | |                    | |
         | - ICD-11 TM2      |                    | | - Reproducibility  | |
         |   (disease codes) |                    | | - Completeness     | |
         | - ChEBI           |                    | | - Exactness        | |
         |   (chemicals)     |                    | +--------------------+ |
         +-------------------+                    |          |             |
                                                  |          v             |
                                                  | +--------------------+ |
                                                  | | Iteration loop     | |
                                                  | | (gap report +      | |
                                                  | |  lexicon expansion) | |
                                                  | +--------------------+ |
                                                  +------------------------+
                                                             |
                                                             | Structured extractions
                                                             | (training signal)
                                                             v
+============================================================================================+
|                           PHASE II: VALIDATION (M10-M12)                                   |
+============================================================================================+
|                                                                                            |
|  +-------------------------+    +-------------------------+    +-------------------------+  |
|  | E6. Generalisation      |    | E5. NER Ablation        |    | E1-E4. KG Quality       |  |
|  | on unseen data          |    |                         |    |                         |  |
|  |                         |    | Arm A: Gazetteer only   |    | - SHACL conformance     |  |
|  | - 10% withheld Vol I    |    | Arm B: Distant-sup CRF  |    | - External-ID re-verify |  |
|  | - Other TM texts        |    | Arm C: KG-augmented CRF |    | - Expert spot-check     |  |
|  |   (where available)     |    |         ^               |    |   (Gwet's AC1)          |  |
|  |                         |    |         |               |    | - Statistical precision |  |
|  | Target: P >= 0.80       |    | KG-derived features     |    |   (Bayesian CIs)        |  |
|  +-------------------------+    +-------------------------+    +-------------------------+  |
|                                            |                                               |
|                                            v                                               |
|                                 +-------------------------+                                |
|                                 | D4. NER MODEL           |                                |
|                                 | (First Sinhala TM NER)  |                                |
|                                 | Distant-supervised +    |                                |
|                                 | KG-augmented features   |                                |
|                                 +-------------------------+                                |
|                                                                                            |
+============================================================================================+


RESEARCH QUESTIONS MAPPED TO SYSTEM COMPONENTS:

  RQ1 (Lexical bridge)        -->  Sinhala-Sanskrit Cascade Resolver
  RQ2 (Reproducible IE)       -->  Extraction System + Three-Guarantees Audit
  RQ3 (Generalisation)        -->  Phase II Evaluation (E6)
  RQ4 (KG-grounded NER)       -->  NER Ablation (E5) + NER Model (D4)
  RQ5 (FAIR + CARE)           -->  Release Governance (O7)


NOVELTY CLAIMS MAPPED:

  N1. First Sinhala-to-Sanskrit lexical bridge     -->  Resolver (M4-M5)
  N2. Reproducible schema-constrained extraction   -->  System + Audit Gates (M7-M9)
  N3. First Sri Lankan TM knowledge graph          -->  KG (output)
  N4. First Sinhala TM NER model                   -->  NER Model (M10)
  N5. Three-guarantees verification framework      -->  Audit Gates (M8-M9)


TIMELINE SUMMARY:

  M1-M2   OCR + structural recovery .............. training data
  M3      Lexicon extraction ...................... knowledge base
  M4-M5   Sinhala-Sanskrit resolver ............... cross-lingual bridge
  M6      External-authority enrichment ........... ICD-11 / POWO / ChEBI
  M7      KG schema + builder + validator ......... knowledge graph
  M8-M9   Prose extraction system ................. core system
  M10     Evaluation + NER ablation ............... validation
  M11     Expert review + release governance ...... quality assurance
  M12     Thesis + publications ................... write-up
```

---

## Concrete Examples (Real Data from the OCR Output)

### A. What the training data looks like (Pharmacopoeia, p.236, Entry 37)

The Pharmacopoeia presents formulas in a fixed tabular format. After OCR and structural extraction, Entry 37 yields:

```json
{
  "අංකය": 37,
  "යෝග නාමය": "භූනිම්බාදි චූර්ණය",
  "යෝගය": [
    {"ද්‍රව්‍යය": "බිං කොහොඹ",   "ප්‍රමාණය": "කර්ෂ 2 යි", "ග්‍රෑ": "ග්‍රෑ : 30 යි"},
    {"ද්‍රව්‍යය": "කුළුරෑණ",      "ප්‍රමාණය": "කර්ෂ 2 යි", "ග්‍රෑ": "ග්‍රෑ : 30 යි"},
    {"ද්‍රව්‍යය": "කලාඳුරුඅල",    "ප්‍රමාණය": "කර්ෂ 2 යි", "ග්‍රෑ": "ග්‍රෑ : 30 යි"},
    {"ද්‍රව්‍යය": "තිකුළු",       "ප්‍රමාණය": "කර්ෂ 2 යි", "ග්‍රෑ": "ග්‍රෑ : 30 යි"},
    {"ද්‍රව්‍යය": "කෙළිඳඇට",     "ප්‍රමාණය": "කර්ෂ 2 යි", "ග්‍රෑ": "ග්‍රෑ : 30 යි"}
  ],
  "සංස්කරණය": "කෙළිඳ පොතු කලං 16 යි . ( ග්‍රෑම් 80 )",
  "ප්‍රයෝග": "ග්‍රහණි , ගුල්ම , කාමලා , ජ්වර , පාණ්ඩු , ප්‍රමේහ , අරුචි , අතීසාර නස යි .",
  "අනුපාන": "උණු දිය වේ .",
  "මාත්‍රාව": "කලං 2 -1 දක්වා වේ . ( ග්‍රෑම් 2.5 - ග්‍රෑම් 5 )",
  "source_page": 236
}
```

Each ingredient cell is a known entity; the field labels encode relation types; the formula name anchors a `Formulation` node. Traditional units (කර්ෂ = karsha) appear alongside their gram equivalents.

---

### B. What the input (unseen prose) looks like

When the trained system encounters free-style traditional-medicine prose from another book, there is no tabular layout:

```
"භූනිම්බාදි චූර්ණය සඳහා බිං කොහොඹ, කුළුරෑණ, කලාඳුරුඅල,
 තිකුළු, කෙළිඳ ඇට යන ද්‍රව්‍ය කර්ෂ 2 බැගින් ගෙන කෙළිඳ පොතු
 කලං 16 ක් සමග චූර්ණ කොට ග්‍රහණි, ගුල්ම, කාමලා, ජ්වර,
 පාණ්ඩු, ප්‍රමේහ ආදී රෝග සඳහා උණු දියෙන් කලං 2 බැගින්
 දිනකට දෙවේලක් පානය කරවන්න."
```

The system must extract the same structured knowledge from this paragraph.

---

### C. What the NER output looks like

The NER model labels each token span with a schema-typed entity:

```
"භූනිම්බාදි චූර්ණය"     --> [Formulation]         (Bhunimbadi Churna)
"බිං කොහොඹ"             --> [Plant]               (Andrographis paniculata)
"කුළුරෑණ"               --> [Plant]               (Cyperus rotundus)
"කලාඳුරුඅල"             --> [Plant]               (Alpinia galanga)
"තිකුළු"                --> [Plant]               (Trikatu compound)
"කෙළිඳ ඇට"             --> [Plant]               (Holarrhena seeds)
"කර්ෂ 2"                --> [Quantity]            (2 karsha = 30g)
"කෙළිඳ පොතු"           --> [Plant]               (Holarrhena bark)
"කලං 16"                --> [Quantity]            (16 kalang = 80g)
"චූර්ණ කොට"            --> [PreparationType]     (powdering)
"ග්‍රහණි"                --> [Disease]             (malabsorption)
"ගුල්ම"                 --> [Disease]             (abdominal tumour)
"කාමලා"                --> [Disease]             (jaundice)
"ජ්වර"                  --> [Disease]             (fever)
"පාණ්ඩු"               --> [Disease]             (anaemia)
"ප්‍රමේහ"               --> [Disease]             (diabetes)
"උණු දියෙන්"           --> [Vehicle]             (warm water)
"කලං 2"                --> [Dosage]              (2 kalang = 2.5g)
```

---

### D. What the Knowledge Graph output looks like

The extraction system emits schema-valid triples per the KG schema (docs/kg_schema.md, v1.1: 11 node types, 13 edge types):

```
Formulation node:  formula:vol1/37  "භූනිම්බාදි චූර්ණය"

TRIPLES:
+----------------+------------------+--------------------+---------------------+
| Edge           | From             | To                 | Properties          |
+----------------+------------------+--------------------+---------------------+
| CONTAINS       | formula:vol1/37  | plant:bhūnimba     | parts:1, qty: 30g   |
| CONTAINS       | formula:vol1/37  | plant:mustaka      | parts:1, qty: 30g   |
| CONTAINS       | formula:vol1/37  | plant:kuliñjana    | parts:1, qty: 30g   |
| CONTAINS       | formula:vol1/37  | plant:trikaṭu      | parts:1, qty: 30g   |
| CONTAINS       | formula:vol1/37  | plant:kuṭaja       | parts:1, qty: 30g   |
| IS_TYPE        | formula:vol1/37  | prep:cūrṇa         |                     |
| TREATS         | formula:vol1/37  | disease:grahaṇī    | evidence: canonical |
| TREATS         | formula:vol1/37  | disease:gulma      | evidence: canonical |
| TREATS         | formula:vol1/37  | disease:kāmalā     | evidence: canonical |
| TREATS         | formula:vol1/37  | disease:jvara      | evidence: canonical |
| TREATS         | formula:vol1/37  | disease:pāṇḍu     | evidence: canonical |
| TREATS         | formula:vol1/37  | disease:prameha    | evidence: canonical |
| DOSED_WITH     | formula:vol1/37  | animal:uṣṇa_jala  | (warm water)        |
+----------------+------------------+--------------------+---------------------+

PROVENANCE (per triple):
  source_doc:        "data/structured/201-to-250_structured.json"
  source_record_id:  "vol1/37"
  char_span:         [0, 12] (for "බිං කොහොඹ")
  extractor_version: "prose_v1"

EXTERNAL BINDINGS:
  plant:bhūnimba   -->  Andrographis paniculata  -->  POWO: urn:lsid:ipni.org:names:46122-1
  disease:jvara    -->  ICD-11 TM2: SP51          (Jvara / Fever)
  disease:prameha  -->  ICD-11 TM2: SE70          (Prameha / Urinary disorders)
  disease:pāṇḍu   -->  ICD-11 TM2: SD50          (Pandu / Anaemia)

UNIT CONVERSION (from the system's unit registry):
  "කර්ෂ 2" = 2 karsha = 30g (Sri Lankan system, 1 karsha = 15g)
  "කලං 16" = 16 kalang = 80g (1 kalang = 5g)
  dose: "කලං 2" = 2.5g per administration

GUARANTEES MET:
  Reproducibility:  SHA-256 identical on re-run
  Exactness:        char_span[0:12] == "බිං කොහොඹ" (verbatim)
  Completeness:     all content tokens covered or logged as NIL
```

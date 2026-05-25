# Project Overview

**A Reproducible System for Knowledge-Graph Extraction from Sinhala Traditional Medicine Literature, Trained Using the Sri Lankan Ayurvedic Pharmacopoeia**

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

## Concrete Examples

### A. What the training data looks like (Pharmacopoeia tabular layout)

The Pharmacopoeia presents formulas in a fixed tabular format where column position encodes semantic role:

```
 Page 172, Entry 3:
 +----------+------------+-------------------------------------------+
 | Column 1 | Column 2   | Column 3 (content)                        |
 | (number) | (label)    |                                           |
 +----------+------------+-------------------------------------------+
 | 3.       |            | දශමූල ක්වාථය                              |
 |          | යෝගය :-    | බෙලි මුල් පොතු                             |
 |          |            | පලොල් මුල් පොතු                            |
 |          |            | මුගුනු වැල් මුල් පොතු                       |
 |          |            | තොටිල්ල මුල් පොතු                          |
 |          |            | පැරණි මුල් පොතු                             |
 |          |            | එළබටු මුල්                                 |
 |          |            | කටුවැල්බටු මුල්                             |
 |          |            | එරබදු මුල් පොතු                             |
 |          |            | බලු දුරු                                   |
 |          |            | අස්වැන්න                     සමපමණ        |
 |          | සංස්කරණය:-  | කොටා වතුරට දමා අටෙන් එකට නැවීම             |
 |          | ප්‍රයෝග:-   | වාත රෝග                                   |
 |          | අනුපාන:-   | බී පැණි                                    |
 |          | මාත්‍රාව:-  | උදේ හවස කසාය බැගින්                        |
 +----------+------------+-------------------------------------------+

 After OCR + structural extraction, this becomes:
 {
   "අංකය": 3,
   "යෝග නාමය": "දශමූල ක්වාථය",
   "යෝගය": [
     {"ද්‍රව්‍යය": "බෙලි මුල් පොතු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "පලොල් මුල් පොතු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "මුගුනු වැල් මුල් පොතු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "තොටිල්ල මුල් පොතු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "පැරණි මුල් පොතු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "එළබටු මුල්", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "කටුවැල්බටු මුල්", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "එරබදු මුල් පොතු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "බලු දුරු", "ප්‍රමාණය": "සමපමණ"},
     {"ද්‍රව්‍යය": "අස්වැන්න", "ප්‍රමාණය": "සමපමණ"}
   ],
   "සංස්කරණය": "කොටා වතුරට දමා අටෙන් එකට නැවීම",
   "ප්‍රයෝග": "වාත රෝග",
   "අනුපාන": "බී පැණි",
   "මාත්‍රාව": "උදේ හවස කසාය බැගින්",
   "source_page": 172
 }
```

This structured output is how the system **learns** what entities and relations look like: each ingredient cell is a known entity, the field labels encode relation types, and the formula name anchors a `Formulation` node.

---

### B. What the input (unseen prose) looks like

When the trained system encounters free-style traditional-medicine prose (from any book), the text has no tabular layout:

```
 Input text (a preparation instruction from a different source):

 "බෙලි මුල් පොතු, පලොල් මුල් පොතු, එළබටු මුල්, කටුවැල්බටු මුල්,
  අස්වැන්න සම ප්‍රමාණයෙන් ගෙන කොටා වතුරට දමා අටෙන් එකට නගා
  පෙරා බී පැණි මිශ්‍ර කොට වාත රෝග සඳහා උදේ හවස පානය කරවන්න."

 (Translation: Take equal parts of beli root bark, palol root bark,
  elabatu root, katuwelbatu root, and aswenna; crush, add water, boil
  down to one-eighth, strain, mix with bee honey, and administer
  morning and evening for vata diseases.)
```

The system must extract the same knowledge from this unstructured paragraph that it learned from the tabular layout.

---

### C. What the NER output looks like

The NER model labels each token span with a schema-typed entity:

```
 "බෙලි මුල් පොතු"        --> [Plant]        (beli root bark)
 "පලොල් මුල් පොතු"       --> [Plant]        (palol root bark)
 "එළබටු මුල්"            --> [Plant]        (elabatu root)
 "කටුවැල්බටු මුල්"       --> [Plant]        (katuwelbatu root)
 "අස්වැන්න"              --> [Plant]        (aswenna)
 "සම ප්‍රමාණයෙන්"         --> [Quantity]     (equal parts)
 "කොටා"                  --> [PrepVerb]     (crush)
 "අටෙන් එකට නගා"         --> [PrepVerb]     (boil down 8:1)
 "පෙරා"                  --> [PrepVerb]     (strain)
 "බී පැණි"               --> [Vehicle]      (bee honey)
 "වාත රෝග"              --> [Disease]      (vata diseases)
 "උදේ හවස"              --> [Dosage]       (morning and evening)
```

---

### D. What the Knowledge Graph output looks like

From the same text, the extraction system emits schema-valid triples with provenance:

```
 Formulation: "දශමූල ක්වාථය" (Dashamula Kvatha)

 TRIPLES EMITTED:
 +-----------+-------------------+------------------+---------------------------+
 | Edge Type | From              | To               | Provenance (char_span)    |
 +-----------+-------------------+------------------+---------------------------+
 | CONTAINS  | දශමූල ක්වාථය      | බෙලි             | [0:15] "බෙලි මුල් පොතු"   |
 | CONTAINS  | දශමූල ක්වාථය      | පලොල්            | [17:34] "පලොල් මුල් පොතු"  |
 | CONTAINS  | දශමූල ක්වාථය      | එළබටු            | [36:47] "එළබටු මුල්"       |
 | CONTAINS  | දශමූල ක්වාථය      | කටුවැල්බටු        | [49:63] "කටුවැල්බටු මුල්"  |
 | CONTAINS  | දශමූල ක්වාථය      | අස්වැන්න          | [65:73] "අස්වැන්න"         |
 | IS_TYPE   | දශමූල ක්වාථය      | Kvatha (කෂාය)    | formula name               |
 | DOSED_WITH| දශමූල ක්වාථය      | බී පැණි           | [112:119] "බී පැණි"        |
 | TREATS    | දශමූල ක්වාථය      | වාත රෝග          | [128:135] "වාත රෝග"       |
 +-----------+-------------------+------------------+---------------------------+

 VERB CHAIN (preparation steps):
   කොටා (crush) --> වතුරට දමා (add water) --> නගා (boil) --> පෙරා (strain)

 EXTERNAL BINDINGS:
   බෙලි      -->  Aegle marmelos      -->  POWO LSID: urn:lsid:ipni.org:names:44964-1
   වාත රෝග  -->  ICD-11 TM2: SP51     (Vata disorders)

 GUARANTEES:
   Reproducibility: SHA-256 of output is identical on every re-run
   Exactness:       every char_span slices back to the exact surface text
   Completeness:    all content tokens accounted for or logged as NIL
```

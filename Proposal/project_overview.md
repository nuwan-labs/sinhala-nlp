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

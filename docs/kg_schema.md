# Knowledge Graph Schema — v1

> **Status:** design document. Defines the target graph model for the
> project. Implementation in `enrichers/` (external-ID binding) and the
> not-yet-built KG-builder is constrained by this schema.

---

## Table of contents

1. [Purpose and audience](#1-purpose-and-audience)
2. [Why this schema (synthesis of comparable initiatives)](#2-why-this-schema-synthesis-of-comparable-initiatives)
3. [Design principles](#3-design-principles)
4. [Node types](#4-node-types)
5. [Edge types](#5-edge-types)
6. [Provenance](#6-provenance)
7. [Identifier system](#7-identifier-system)
8. [Serialization views](#8-serialization-views)
9. [Schema-constrained extraction](#9-schema-constrained-extraction)
10. [Worked example: entry 7 in JSON-LD](#10-worked-example-entry-7-in-json-ld)
11. [Versioning and migration](#11-versioning-and-migration)
12. [Open questions and future work](#12-open-questions-and-future-work)
13. [References](#13-references)

---

## 1. Purpose and audience

This document is the *contract* for everything in this project that
produces or consumes the knowledge graph. It is intended to be readable
end-to-end by:

- a supervisor or external reviewer who wants to understand the data
  model in 20 minutes;
- a downstream tool author (NER tagger, graph-DB ingestor, query
  service) who needs to know what node types, edges, and properties to
  expect;
- a future me (or another contributor) returning to the project after
  time away.

Concrete implementations:

| Layer | Module |
|---|---|
| External-ID binding for plants | `enrichers/botanical_powo.py` |
| External-ID binding for diseases | `enrichers/icd11_tm2_mapper.py` |
| Linguistic resolution (surface → IAST → Sanskrit lemma) | `resolvers/sanskrit_resolver.py` |
| KG builder (not yet implemented) | `knowledge_graph/build.py` (planned) |

---

## 2. Why this schema (synthesis of comparable initiatives)

The schema below is the result of a survey of recent comparable
knowledge graphs. See [`references.md`](references.md) for full
citations.

| Initiative | Year | Nodes / Edges | Schema | Mapped to |
|---|---|---|---|---|
| **GRAYU** (Frontiers in Pharmacology) | 2026 | 157 K / 1.52 M | 4 nodes (Plant, Phytochemical, Disease, Formulation) · 6 relations | PubChem · ChEBI · MeSH/DOID · POWO · WFO |
| **AyurKOSH** (IEEE DataPort) | 2026 | structured triples | Vyādhi (disease), Lakṣaṇa (symptom), Aushadhi (herb), compounds · Rasa/Guna/Virya/Vipaka/Karma | not standardised externally |
| **HerbKG** (Frontiers in Genetics) | 2022 | 53 K relations | 4 entity types (Herb, Chemical, Disease, Gene) · 5 relations | UMLS · MeSH |
| **Āyurjñānam** (NYCIKS) | 2023 | 410 / 764 | Dhanyavarga chapter only | small OWL |
| **WHO ICD-11 TM2** (international standard) | **Feb 2025** | 529 morbidity codes, 18 chapters | Dedicated chapter (26) for Ayurveda/Siddha/Unani | this **is** the standard |

Three patterns recur:

1. **Tight node typology, dense properties.** Nobody invents 30+ node
   types. Few types + many edge properties wins.
2. **External-ID-first identity.** Every node carries one or more
   authoritative external IDs.
3. **Provenance per fact.** Every edge knows which source span it came
   from, which extractor version produced it, and at what confidence.

The 2025 game-changer is **ICD-11 TM2**: WHO released a dedicated
Traditional Medicine module specifically for Ayurveda/Siddha/Unani —
529 codes, official February 2025. India's NAMASTE Portal has already
mapped 1 941 AYUSH terms to it. This is *the* modern standard for
Ayurvedic disease classification; any new Sinhala Ayurvedic KG must
adopt it. The schema below makes ICD-11 TM2 a required external ID on
every `Disease` node.

The 2025 extraction best practice is **schema-constrained extraction**:
define the schema first as a hard constraint, then let the extractor
(rule-based, CRF, or LLM) produce only schema-valid triples. We adopt
this principle in §9.

---

## 3. Design principles

1. **One node, one entity.** A herb is one node — its surface forms
   (Sinhala spelling variants, Sanskrit, English common name, Latin
   binomial) are all *properties* of that single node, not separate
   nodes. The `VARIANT_OF` edge links surface forms to canonical
   entities only for resolver provenance, not as a true type relation.
2. **External IDs are required, not optional.** A `Plant` node without
   a POWO LSID or NCBI Taxonomy ID is incomplete and should be flagged.
3. **Edges carry the interesting data.** `CONTAINS` is more than a
   binary link — it carries `parts`, `quantity_text`, `quantity_unit`,
   `is_substitute`. The graph topology *plus* edge properties is the
   answer to most clinical queries.
4. **Provenance per fact.** Every node and edge records where it came
   from. Without this the KG is not auditable.
5. **Conservative typology.** When in doubt, do not invent a new node
   type. Encode it as an edge property or as a value of an existing
   enumerated property.

---

## 4. Node types

**10 node types.** Internal IDs use a colon-separated namespace; the
prefix is the type slug.

| # | Type | Internal ID format | Required external IDs | Optional external IDs |
|---|---|---|---|---|
| 1 | **Plant** | `plant:<canonical_iast>` (e.g. `plant:pippalī`) | POWO IPNI LSID **or** NCBI Taxonomy ID | GRAYU ID, WFO ID |
| 2 | **PlantPart** | `part:<part>` (e.g. `part:root`, `part:fruit`, `part:bark`) | — (closed enum, ~15 parts) | PO (Plant Ontology) ID |
| 3 | **Phytochemical** | `chem:<inchikey>` | PubChem CID | ChEBI ID, CAS RN |
| 4 | **Mineral** | `min:<canonical_iast>` (e.g. `min:saindhava_lavaṇa`) | — | ChEBI ID, PubChem CID |
| 5 | **Formulation** | `formula:<source>/<entry_no>` (e.g. `formula:vol1/44`) | source citation (book + page) | AyurKOSH ID, GRAYU formulation ID |
| 6 | **PreparationType** | `prep:<sanskrit>` (e.g. `prep:taila`, `prep:kaṣāya`, `prep:bhasma`) | — (closed enum, ~15 types) | NAMASTE Portal code |
| 7 | **Route** | `route:<sanskrit>` (e.g. `route:anuvāsana`, `route:oral`, `route:nasya`) | — (closed enum, ~10 routes) | — |
| 8 | **Disease** | `disease:<canonical_iast>` (e.g. `disease:udāvarta`) | **ICD-11 TM2 code** | MONDO, DOID, MeSH C-tree |
| 9 | **Symptom** | `symptom:<canonical_iast>` | — | SNOMED CT, UMLS CUI |
| 10 | **PharmacologicalProperty** | `prop:<axis>:<value>` (e.g. `prop:rasa:madhura`, `prop:vīrya:śīta`) | — (closed enum) | NAMASTE Portal code |

### Node property reference

Every node carries these **common properties** in addition to its
type-specific ones:

```yaml
id:               <internal ID, see table above>
type:             <node type name>
canonical_si:     <NFC-normalised Sinhala name>
canonical_iast:   <IAST transliteration>
sanskrit:         <Sanskrit lemma>
english_common:   <English common name(s), array>
display_name:     <preferred name for UI>
created_at:       <ISO 8601>
provenance:       <see §6>
```

**Per-type extras:**

- `Plant` adds: `latin_binomial`, `family`, `kingdom`, `is_synonym`
  (bool), `accepted_lsid` (if this is a synonym, the LSID of the
  accepted name).
- `Phytochemical` adds: `iupac_name`, `molecular_formula`, `molecular_weight`.
- `Mineral` adds: `chemical_formula`, `processing_state` (`raw` /
  `śodhita` / `bhasma`).
- `Formulation` adds: `name_sa`, `name_si`, `source_register`
  (`tabular`, `verse`, `prose`).
- `Disease` adds: `english_rubric` (the ICD-11 English title),
  `affected_system` (digestive / urinary / respiratory / …),
  `tridoṣa_implication` (`vāta` / `pitta` / `kapha` / mixed).
- `PharmacologicalProperty` enumerates: axis ∈ {`rasa`, `guna`,
  `vīrya`, `vipāka`, `karma`, `prabhāva`}; value ∈ closed lists per axis.

---

## 5. Edge types

**13 edge types.** Every edge carries `provenance` (see §6).

| # | Edge | Domain → Range | Edge properties |
|---|---|---|---|
| 1 | `CONTAINS` | Formulation → Plant ∨ Mineral | `parts:int`, `quantity_text:str`, `quantity_unit:enum`, `is_substitute:bool` |
| 2 | `USES_PART` | Formulation → PlantPart (composed with a Plant) | — |
| 3 | `CONSISTS_OF` | Plant → Phytochemical | `concentration:float?`, `evidence_source:str` |
| 4 | `IS_TYPE` | Formulation → PreparationType | — |
| 5 | `PREPARED_BY` | Formulation → Formulation | `step_order:int` (a formula may be prepared *from* another formula, e.g. a kalka used inside a taila) |
| 6 | `ADMINISTERED_AS` | Formulation → Route | — |
| 7 | `DOSED_WITH` | Formulation → Plant ∨ Vehicle | `disjunctive:bool` (true if "A or B"; false if "A and B") |
| 8 | `TREATS` | Formulation → Disease | `evidence_level:enum` (`canonical_text` / `inferred` / `clinical_trial`), `efficacy_score:float?` |
| 9 | `HAS_SYMPTOM` | Disease → Symptom | — |
| 10 | `RELIEVES` | Formulation → Symptom | — |
| 11 | `HAS_PROPERTY` | Plant → PharmacologicalProperty | — |
| 12 | `SUBSTITUTES_FOR` | Plant → Plant | `substitution_rule:str` (e.g. "abhāva-pratinidhi") |
| 13 | `VARIANT_OF` | SurfaceForm → Canonical entity | `script:enum` (`si` / `iast` / `sanskrit_dev`), `resolver_method:str` |

### Notes on a few edges

- **`CONTAINS` quantity_unit** is an enum: `parts` (relative), `gram`,
  `litre`, `māṣa`, `palam`, `kalañcu`, `paṇa`, `karṣa`, `tola`, … —
  including the traditional Sinhala/Sanskrit weight units that our
  ingredient resolver tracks. The `parts:int` field is the most common
  case ("equal parts" → all `parts:1`).
- **`PREPARED_BY`** is for compound recipes: a *taila* (oil) may be
  prepared by first making a *kaṣāya* (decoction) and a *kalka*
  (paste), then cooking them together with oil. Each preparation step
  becomes its own `Formulation` node linked back to the final taila
  via `PREPARED_BY` with `step_order`.
- **`DOSED_WITH disjunctive:true`** captures "with honey **or** ghee"
  — common in the corpus and important for clinical interpretation.
- **`TREATS evidence_level:canonical_text`** is what we extract from
  the pharmacopoeia; downstream clinical-trial integration can add
  more.

---

## 6. Provenance

**Every node and every edge carries a `provenance` block.** Without
this, the KG is not auditable, and the project's claim of "the first
transparent Sinhala Ayurvedic KG" is unsupported.

```yaml
provenance:
  source_doc:         <string, e.g. "data/structured/151-to-200_structured.json">
  source_record_id:   <string, e.g. "vol1/44">
  source_sentence_id: <string?, e.g. "ex_007_01">     # for prose sources
  char_span:          <[int, int]?>                    # character span in source
  extractor_version:  <string, e.g. "prose_v1">
  resolver_version:   <string, e.g. "sanskrit_resolver_v2.1">
  confidence:         <float in [0, 1]>
  created_at:         <ISO 8601 datetime>
  modified_at:        <ISO 8601 datetime, optional>
  reviewer:           <string?, e.g. "human:botanist_001">  # if hand-verified
```

**Required**: `source_doc`, `extractor_version`, `created_at`,
`confidence`. Everything else conditional on availability.

A node or edge with `confidence < 0.5` is flagged but kept; queries
can filter on `confidence ≥ τ` for any threshold τ.

---

## 7. Identifier system

### Internal IDs

Format: `<type_slug>:<lowercased_iast_or_enum>`.

| Type | Example |
|---|---|
| Plant | `plant:pippalī`, `plant:devadāru`, `plant:śatapuṣpa` |
| Mineral | `min:saindhava_lavaṇa`, `min:gandhaka` |
| Formulation | `formula:vol1/44`, `formula:yogamalawa/49`, `formula:example_input/7` |
| Disease | `disease:jvara`, `disease:gulma`, `disease:udāvarta` |
| PreparationType | `prep:kaṣāya`, `prep:taila`, `prep:bhasma` |
| Route | `route:oral`, `route:anuvāsana`, `route:nasya` |
| PharmacologicalProperty | `prop:rasa:madhura`, `prop:vīrya:uṣṇa` |

IAST is used as the namespace key because it is unambiguous, Romanised
(URL-safe with diacritics escaped), and bridges to all the Sanskrit-NLP
tools the project depends on.

### External authorities — required and optional

| Domain | Required | Optional | Purpose |
|---|---|---|---|
| Plants | POWO IPNI LSID **OR** NCBI Taxonomy ID | GRAYU plant ID, WFO ID | Taxonomy + interoperability with botany |
| Chemicals | PubChem CID | ChEBI ID, CAS RN | Cheminformatics interoperability |
| Diseases | **ICD-11 TM2 code** | MONDO, DOID, MeSH C-tree | International morbidity comparability |
| Symptoms | — | SNOMED CT, UMLS CUI | Clinical-systems integration |
| Sanskrit | — | Monier-Williams entry ID, AyurKOSH ID | Literary / lexicographic |

The **resolvers** populate the Sanskrit lemma + IAST. The
**enrichers** populate the external authority IDs. The schema
distinguishes the two layers explicitly.

---

## 8. Serialization views

The same KG is exposed in four views, each tuned to a downstream need.

| View | Format | Purpose | Tools |
|---|---|---|---|
| **Canonical (write)** | Neo4j | Source-of-truth store; supports Cypher queries; matches GRAYU's choice | Neo4j Community / AuraDB |
| **Linked-data (publish)** | JSON-LD | Web-native; integrates with schema.org / bioschemas | Browsers, JSON-LD libraries, Pyld |
| **Semantic-web (interoperate)** | RDF / Turtle | OWL alignment; federation with OBO Foundry, Bioportal | Apache Jena, OWLAPI |
| **Streaming (extract)** | JSONL | IE pipeline I/O; one node-or-edge record per line | Standard JSON tools |

A small companion file [`context.jsonld`](context.jsonld) defines the
JSON-LD context (term IRIs for the 10 node types and 13 edge labels) so
the JSON-LD examples in §10 actually parse.

---

## 9. Schema-constrained extraction

The 2025 best practice (see [RELATE](references.md#relate), [SPIREX](references.md#spirex), [ODKE+](references.md#odke)):
**the extractor's output must conform to the schema by construction**,
not by post-hoc validation.

Concretely, for any extractor — rule-based, CRF, or LLM-based:

1. The extractor is given the schema (this document) as a constraint.
2. The extractor's allowed output triple-shapes are *exactly* the
   `(type → edge → type)` triples in §5 above.
3. Any extracted triple whose subject/object node types are not in §4,
   or whose edge label is not in §5, is rejected at emission time.
4. The extractor cannot invent new node types or edge labels.

For our project this means:

- **Rule-based extractors** (e.g. the planned prose Stage 3) are
  built with the schema as their explicit output skeleton.
- **CRF / NER models** have their output label set derived from §4.
- **LLM extractors**, if used, are prompted with the schema as a
  constraint block and their output is validated against `context.jsonld`.

This rules out a class of bugs where an extractor invents a node type
like "Application" that has no place in the graph.

---

## 10. Worked example: entry 7 in JSON-LD

Entry 7 from `Proposal/example_input.txt` (the prose-form Sinhala
Ayurvedic example), rendered under this schema. Abbreviated for
readability — the full version would include all 28 ingredients and a
node block per referenced entity.

```jsonld
{
  "@context":   "https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp/docs/context.jsonld",
  "@graph": [

    /* THE FORMULATION NODE */
    {
      "@id":           "formula:example_input/7",
      "@type":         "Formulation",
      "source_register": "prose",
      "name_sa":       null,
      "provenance": {
        "source_doc":         "Proposal/example_input.txt",
        "source_sentence_id": "ex_007_01",
        "extractor_version":  "prose_v1",
        "resolver_version":   "sanskrit_resolver_v2.1",
        "confidence":         0.92,
        "created_at":         "2026-05-23T19:00:00Z"
      }
    },

    /* TYPE + ROUTE EDGES */
    { "@type": "IS_TYPE",         "from": "formula:example_input/7", "to": "prep:taila" },
    { "@type": "ADMINISTERED_AS", "from": "formula:example_input/7", "to": "route:anuvāsana" },

    /* INGREDIENTS — one node per ingredient + one CONTAINS edge */
    {
      "@id":              "plant:kuṣṭha",
      "@type":            "Plant",
      "canonical_si":     "කොට්ඨ",
      "canonical_iast":   "kuṣṭha",
      "sanskrit":         "kuṣṭha",
      "latin_binomial":   "Saussurea lappa",
      "family":           "Asteraceae",
      "external": {
        "powo_lsid":       "urn:lsid:ipni.org:names:248488-1",
        "ncbi_taxonomy":   "147195"
      },
      "provenance": { "source_doc": "...", "confidence": 0.95 }
    },
    {
      "@type":            "CONTAINS",
      "from":             "formula:example_input/7",
      "to":               "plant:kuṣṭha",
      "parts":            1,
      "quantity_text":    "සම සම ව",
      "quantity_unit":    "parts",
      "provenance":       { "source_sentence_id": "ex_007_01", "char_span": [12, 23] }
    },

    /* DOSED_WITH — castor oil OR sesame oil (disjunctive) */
    {
      "@type":           "DOSED_WITH",
      "from":            "formula:example_input/7",
      "to":              "plant:eraṇḍa",
      "disjunctive":     true
    },
    {
      "@type":           "DOSED_WITH",
      "from":            "formula:example_input/7",
      "to":              "plant:tila",
      "disjunctive":     true
    },

    /* TREATS — with ICD-11 TM2 codes attached to disease nodes */
    {
      "@id":          "disease:udāvarta",
      "@type":        "Disease",
      "canonical_si": "උදාවර්ත",
      "canonical_iast": "udāvarta",
      "sanskrit":     "udāvarta",
      "english_rubric": "Reverse peristalsis / upward-moving vāta",
      "external": {
        "icd11_tm2": "SP30",
        "icd11_uri": "http://id.who.int/icd/release/11/2025-01/mms/...",
        "mondo":     "MONDO:0017145"
      }
    },
    {
      "@type":          "TREATS",
      "from":           "formula:example_input/7",
      "to":             "disease:udāvarta",
      "evidence_level": "canonical_text",
      "provenance":     { "source_sentence_id": "ex_007_02" }
    }

    /* ... ingredient nodes + CONTAINS edges for the other 27 plants ...
       ... TREATS edges for the other 9 indications ...                  */
  ]
}
```

The same data, in **Cypher** for Neo4j, would create the corresponding
nodes and relationships with the same constraints. The same data, in
**Turtle / RDF**, would use OWL classes derived from the §4 / §5
typology.

---

## 11. Versioning and migration

This document is **schema v1**. Future versions will follow these
rules:

1. **Adding a new node type or edge type is a minor version bump**
   (`v1.1`). Backward-compatible.
2. **Removing or renaming a node/edge type is a major version bump**
   (`v2`). Requires a migration script. The old type names remain
   queryable for one major version.
3. **Property changes** (adding optional properties) are minor;
   removing or changing semantics of an existing property is major.
4. The current schema version is recorded in every emitted JSON-LD
   document as `"schema_version": "1.0"`.

---

## 12. Open questions and future work

Honest list of what this v1 doesn't fully resolve:

- **Coverage of ICD-11 TM2 codes for Sinhala-specific conditions.**
  TM2 was built primarily by India (Ayurveda/Siddha/Unani). Some
  Sinhala-Ayurvedic-specific conditions may not have a TM2 code yet.
  Fallback: leave `icd11_tm2: null`, populate `english_rubric` + the
  Sanskrit lemma; flag as `confidence < 0.7`.
- **Vehicle vs ingredient.** When a formula uses ghee (`ghṛta`) is it
  an *ingredient* (CONTAINS) or a *vehicle* (DOSED_WITH)? The classical
  text often does not distinguish. Heuristic: if it's pre-cooked into
  the preparation, it's an ingredient; if it's the carrier given with
  the dose, it's a vehicle. This is a per-formula judgment.
- **Pharmacological-property axis values.** The closed enum for
  `prop:rasa:*` etc. needs to be enumerated. Use NAMASTE Portal
  vocabulary where available; otherwise enumerate from the Sri Lankan
  Ayurvedic Pharmacopoeia.
- **Symptom vs disease boundary.** *Kāsa* (cough) is sometimes a
  *Disease* and sometimes a *Symptom* of another disease. Decision:
  default to *Symptom* unless the formula treats it as a primary
  condition (i.e. the formula's TREATS edges all point to it).
- **Probabilistic facts.** `confidence` is a float per edge but is
  currently set by simple heuristics, not a calibrated estimator. A
  v2 could replace this with a calibrated probabilistic model.
- **The future KG-builder module** (`knowledge_graph/build.py`) is not
  yet implemented. The schema is its specification.

---

## 13. References

Full bibliography in [`references.md`](references.md) (annotated) and
[`references.bib`](references.bib) (BibTeX).

Key references for this schema:

- **GRAYU** — Joshi et al. (2026), 4-node Ayurvedic KG (model
  borrowed from here).
- **AyurKOSH** — Mirasdar et al. (2026), source of the pharmacological-
  property axis design.
- **HerbKG** — Lin et al. (2022), entity-types pattern.
- **ICD-11 TM2** — WHO (Feb 2025), required external ID for diseases.
- **POWO** — Kew (n.d.), required external ID for plants.
- **ChEBI** — EBI (Hastings et al. 2013), optional external ID for chemicals.
- **RELATE / ODKE+ / SPIREX** (2025) — schema-constrained extraction
  paradigm.
- **Schema-constrained AI for biomedical evidence** (Chaos to Clarity,
  arXiv 2025) — auditable extraction pattern.

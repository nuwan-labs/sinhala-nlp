# Project Walkthrough — From Scanned Pharmacopoeia to Knowledge Graph

> **A complete, atomic-step illustration of the Sinhala Traditional
> Medicine NLP project.** Reads top-to-bottom in ~20 minutes.

---

## 0. The project in one sentence

We turn the **Sri Lankan Ayurvedic Pharmacopoeia** (a printed Sinhala
medical reference) into a structured, queryable, interoperable
**knowledge graph** of traditional medicine — by chaining OCR, a
Sinhala→Sanskrit lexical bridge, six pharmacopoeia-internal reference
tables, and a schema-constrained graph builder.

---

## 1. The big picture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  SOURCE                                                                   │
│  Pharmacopoeia.pdf  —  525 pages, Sinhala script, printed 1976+           │
│  Vol I formulas pp.172–443  ·  reference tables pp.65–90 + 444–525         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
   ┌────────────────────────────────┼────────────────────────────────┐
   │                                │                                │
   ▼                                ▼                                ▼
[Stage 0]   OCR via         [Stage 0]   OCR via             [Stage 0]   OCR via
Google Cloud Vision         Google Cloud Vision             Google Cloud Vision
 (language=si)               (language=si)                   (language=si)
   │                           │                                │
   ▼                           ▼                                ▼
┌──────────────────┐  ┌────────────────────┐  ┌────────────────────────────┐
│  FORMULA PAGES   │  │  REFERENCE PAGES   │  │  NARRATIVE / PROSE PAGES   │
│  pp.172–443      │  │  pp.65–90, 444–525 │  │  pp.1–164 + Vols II/III    │
│  (tabular)       │  │  (tables/glossary) │  │  (free-style)              │
└──────────────────┘  └────────────────────┘  └────────────────────────────┘
   │                           │                                │
   ▼                           ▼                                ▼
[Stage 1] per-page slice     extract_materia_medica           [PLANNED]
[Stage 2] row-cluster        extract_pratinidhi               Block A: gazetteer
[Stage 3] x-zone state-      extract_mahakashaya              Block B: segmenter
          machine            (units: hand-curated)            Block C: span labeller
   │                           │                                Block D: template
   ▼                           ▼                                Block E: gates
data/structured/*.json    data/lexicons/*.json                  ▼
   │                           │                              data/structured/
   │                           │                              prose_extracted.json
   └─────────────┬─────────────┘                                │
                 │                                              │
                 ▼                                              │
       resolvers/sanskrit_resolver.py                           │
       Modules A (router) + B (MW lookup)                       │
       + C (pratinidhi) + Tier-2 sandhi                         │
       + Tier-3 sanskrit_parser (memory-isolated)               │
                 │                                              │
                 ▼                                              │
       data/lexicons/{ingredients, names, prose}_lexicon.json   │
                 │                                              │
                 ▼                                              │
       enrichers/                                               │
         botanical_powo.py    → POWO IPNI LSID per plant        │
         icd11_tm2_mapper.py  → ICD-11 TM2 per disease          │
                 │                                              │
                 ▼                                              │
       data/lexicons/botanical_powo.json  +                     │
       data/lexicons/indication_icd11_tm2.json                  │
                 │                                              │
                 ▼                                              │
       knowledge_graph/build.py ◄─────────────────────────────┘
       (consumes everything above)
                 │
                 ▼
       knowledge_graph/kg.{jsonld, cypher, ttl}
       + build_report.json
                 │
                 ▼
       validate/validate_kg.py
       (4 layers: SHACL + anchors + provenance + LLM-judge)
                 │
                 ▼
       validation_report.{md, json}
```

The story is: **OCR → structured JSON → Sanskrit-bridge resolution →
external-ID enrichment → typed graph → audit**.

---

## 2. The source material

The *Sri Lankan Ayurvedic Pharmacopoeia, Vol I* is a 525-page Sinhala
medical reference compiled by the Department of Ayurveda. It has three
distinct text registers, each requiring a different extractor:

| Pages | Register | Example | Extractor |
|---|---|---|---|
| 1–164 | Prose + tables | Introduction, dosage method, materia medica catalogue | **prose (planned)** + dedicated lexicon builders |
| 172–443 | **Tabular formulas** (column layout) | `44.` ‖ `යෝගය` ‖ `:-` ‖ `තිප්පිලි, ඉඟුරු, ...` | `extract_pharma_v4.py` |
| 444–525 | Reference tables | Substance list, formula index | dedicated lexicon builders |
| (separate) | **Verse-form** (*Yogamālāva* 1908) | metrical Sinhala poetry | `extract_yogamalawa_v2.py` |

A single tabular formula entry on page 172:

```
   44.  යෝග නාමය   :-  ත්‍රිකටු චූර්ණය
        යෝගය       :-  තිප්පිලි
                       ඉඟුරු
                       ගම්මිරිස්
        සංස්කරණය   :-  සමව ගෙන කොටා පෙළා කෙළවර කරයි.
        ප්‍රයෝග    :-  කාස, ශ්වාස, අග්නිමාන්ද්‍ය
        අනුපාන    :-  මී පැණි
        මාත්‍රාව   :-  ග්‍රෑ 5
```

Eight Sinhala field labels carry the schema (entry number, formula
name, ingredient list, preparation, indication, vehicle, dose, notes).
We exploit the *column* structure: x-position alone tells us the
field role.

---

## 3. The closed-vocabulary backbone

Before the formula extractor runs, we build six **reference lexicons**
from other sections of the same book. These are the "atoms" of the
final graph — every entity in the KG is grounded in one of them.

| # | Lexicon | Source pages | Size | What it gives us |
|---|---|---|---|---|
| 1 | `materia_medica.json` | 444–453 | 771 substances (647 plant / 82 mineral / 42 animal-origin) | Closed list of Sinhala ingredient surface forms + their category |
| 2 | `pratinidhi_lookup.json` | 77–81 | 143 entries | Sanskrit ↔ Sinhala paraphrase pairs (Module C) + substitute relationships |
| 3 | `mahakashaya_groups.json` | 82–90 | 50 ganas, 436 substance mentions | Caraka's therapeutic-action groupings — feeds `HAS_PROPERTY` edges |
| 4 | `unit_equivalences.json` | 65–68 + 472–477 + 480–481 + 487–488 | 43 symbols, 6 systems | Multi-system mass/volume conversion to grams |
| 5 | `ingredients_lexicon.json` etc. | computed from formula corpus | 983/256/1 040 terms | Sinhala→Sanskrit lemma map per field |
| 6 | `botanical_powo.json` + `indication_icd11_tm2.json` | external APIs | 69 + 49 mappings | External-authority binding |

Each lexicon is a separate atomic build step (steps **§9.1–§9.6**
below). All produce machine-readable JSON; no manual annotation.

---

## 4. The schema (v1.1)

The graph is constrained at **11 node types** and **13 edge types**.
Every node and edge carries provenance (`source_doc`, `char_span`,
`extractor_version`, `confidence`, `created_at`).

```
                    ┌─────────────────────────┐
                    │      Formulation        │
                    │  name_si, source_register│
                    └──┬──────┬──────┬─────┬──┘
                       │      │      │     │
                CONTAINS│ IS_TYPE│ TREATS│  DOSED_WITH
                       │      │      │     │
   ┌───────────────────┼──────┼──────┼─────┼─────────┐
   ▼                   ▼      ▼      ▼     ▼         ▼
┌──────┐ HAS_PROPERTY ┌────────┐  ┌─────────┐    ┌──────────────┐
│Plant │─────────────►│ Pharma │  │ Disease │    │ AnimalOrigin │
└──┬───┘              │coLogica│  │ ICD-11  │    │ madhu/ghṛta/ │
   │                  │  lProp │  │   TM2   │    │   kṣīra      │
   │ CO_OCCURS        └────────┘  └─────────┘    └──────────────┘
   ▼                       ▲                            ▲
┌──────┐                   │                            │
│Plant │            ┌──────┴──────────────────┐         │
└──────┘            │     Mineral             │         │
                    │ saindhava-lavaṇa, etc.  │         │
                    └─────────────────────────┘         │
                              ▲                          │
                              │                          │
                  ┌───────────┴──────────────────────────┘
                  │
            SUBSTITUTES_FOR (abhāva-pratinidhi)

  Plus closed-enum nodes: PreparationType (10) · Route (5) ·
                          PhytoChemical, PlantPart, Symptom (planned)
```

The full contract is in `docs/kg_schema.md`. The KG is exported in
four serialisations: **JSON-LD** (publish), **Neo4j Cypher** (canonical
write), **RDF/Turtle** (semantic-web), **JSONL** (streaming).

---

# Part II — Atomic steps

What follows is the entire pipeline broken into single-input,
single-output steps. Each step has the form
`INPUT → [tool name] → OUTPUT`.

---

## §5. OCR (Stage 0)

### §5.1 Render PDF pages

```
INPUT     Pharmacopoeia.pdf, 525 pages
TOOL      pipeline/ocr_gcv.py  (PyMuPDF + GCV client)
PROCESS   Render each PDF page at 300 dpi → PNG;
          POST to Google Cloud Vision /v1/images:annotate
          with features=DOCUMENT_TEXT_DETECTION, languageHints=["si"];
          retry on 5xx; rescale low-confidence pages 2×.
OUTPUT    ocr_json/ocr_results_output-{151-200, 201-250, ..., 501-525}.json
          (one batch JSON per 50-page chunk, ~7–10 MB each)
```

Each batch JSON contains a `responses[]` array with one entry per
page. Per page, the structure is:

```
fullTextAnnotation:
  pages[0]:
    width: 595, height: 841          # original PDF page size
    blocks[]:                         # GCV's block segmentation
      paragraphs[]:
        words[]:
          symbols[]:
            text: "ක"                  # ONE Sinhala code point
            boundingBox.normalizedVertices: [{x:0.14, y:0.58}, …]
          boundingBox: …               # word-level box
        boundingBox: …                 # paragraph-level box
      boundingBox: …                   # block-level box
  text: "<full page text in reading order>"
```

### §5.2 Slice OCR batch by page number

```
INPUT     ocr_results_output-151-to-200.json (50 pages)
          page_number = 172
TOOL      pipeline/extract_page.py
PROCESS   Walk responses[]; find the entry whose context.pageNumber == 172;
          wrap it in a single-response document; return.
OUTPUT    {"responses":[<one-page tree>]}
EXAMPLE   python extract_page.py ocr_json/ocr_results_output-151-to-200.json 172
```

Used during development/debugging; the production pipeline streams
straight from the batch into Stage 2.

---

## §6. Row clustering (Stage 2)

### §6.1 Walk the GCV tree, extract `(x, y, text)` per word

```
INPUT     Per-page JSON with the block→paragraph→word tree
TOOL      pipeline/shrink_ocr_v4.py
PROCESS   For each word:
            (x, y) = word.boundingBox.normalizedVertices[0]   # top-left
            text   = ''.join(symbol.text for symbol in word.symbols)
          Skip if it's a running page number (y > 0.88 and 0.35<x<0.65
          and text matches /^\d{1,4}$/).
OUTPUT    Flat list of [(x, y, block_id, para_id, text), ...]
```

### §6.2 Cluster words into visual rows by y-position

```
INPUT     Flat word list, sorted by (y, x)
TOOL      pipeline/shrink_ocr_v4.py :: cluster_rows
PROCESS   Walk the sorted list; accumulate into a cluster while
          y_word ≤ y_cluster_start + Y_TOL (=0.012); start a new
          cluster otherwise.
OUTPUT    [{y: 0.342, w: [[0.12, "blk_3", "p_1", "කලාඳුරු"],
                           [0.18, "blk_3", "p_1", "අල"]]}, ...]
EXAMPLE
   Raw:
     (0.14, 0.580, "තිප්පිලි")
     (0.16, 0.581, "ඉඟුරු")
     (0.14, 0.599, "ගම්මිරිස්")        ← y differs by ~0.018, new row
   Clustered:
     row(y=0.580): [තිප්පිලි, ඉඟුරු]
     row(y=0.599): [ගම්මිරිස්]
```

The row is the unit the next stage operates on.

---

## §7. Tabular Stage 3 — state machine over x-zones

### §7.1 Define column zones

```
            x = 0.0      0.15     0.25       0.32             1.0
            │             │        │           │               │
            ▼             ▼        ▼           ▼               ▼
            │ entry_num   │ label  │ separator │     content   │
            │  "44."      │"යෝගය"  │  ":-"     │ "තිප්පිලි..." │
```

The state machine reads each row, dispatches each token by zone,
and transitions formulation state based on recognised Sinhala
field labels:

```
ENTRY_HEADER  →  YOGAYA (ingredients)
              →  SANSKARANAYA (preparation)
              →  PRAYOGA (indication)
              →  ANUPANA (vehicle)
              →  MATRAVA (dose)
              →  SATAHANA (note)
```

### §7.2 Apply the state machine

```
INPUT     row-clustered JSON for one batch (50 pages)
TOOL      pipeline/extract_pharma_v4.py
PROCESS   For each row:
            • Tokens at x < 0.15 → entry number (start a new entry).
            • Tokens at 0.15 ≤ x < 0.25 → field label;
              if label in LABEL_TO_STATE, transition.
            • Tokens at x ≥ 0.32 → content, append to current state.
          Cross-page entries are kept as `partial_tail` and merged
          into the first entry of the next batch.
OUTPUT    {"batch": "151-to-200",
           "entries": [
             {"අංකය": 44,
              "යෝග නාමය": "ත්‍රිකටු චූර්ණය",
              "යෝගය": [
                {"ද්‍රව්‍යය": "තිප්පිලි", "ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0},
                {"ද්‍රව්‍යය": "ඉඟුරු",   "ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0},
                {"ද්‍රව්‍යය": "ගම්මිරිස්","ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0}
              ],
              "සංස්කරණය": "සමව ගෙන කොටා පෙළා කෙළවර කරයි.",
              "ප්‍රයෝග":  "කාස, ශ්වාස, අග්නිමාන්ද්‍ය",
              "අනුපාන":  "මී පැණි",
              "මාත්‍රාව": "ග්‍රෑ 5",
              "සටහන":    "",
              "source_page": 172}, ...
           ],
           "partial_tail": {}}
```

Across all 50-page batches, this produces **852 structured formulas**.
File names: `data/structured/{151-200, 201-250, ...}_structured.json`.

---

## §8. Verse-form Stage 3 — Yogamālāva

Yogamālāva (1908) is a 22-page **verse-form** formulary. Its OCR is
not column-tabular — it's metrical Sinhala poetry. A different
extractor handles it:

```
INPUT     data/ocr/yogamalawa/*.json (sync OCR of yogamalawa.pdf)
TOOL      pipeline/extract_yogamalawa_v2.py
PROCESS   Detect verse boundaries by leading-digit + indentation.
          Within each verse, segment by danda markers and recognised
          field-like phrases ("මෙය ... රෝග හරයි" = "this cures ...").
OUTPUT    data/structured/yogamalawa/yogamalawa_structured_v2.json
          → 145 entries · 22 pages · 98.5% per-token coverage
```

The structured-output schema matches Vol I's (same field keys), so
downstream code consumes both identically.

---

## §9. Closed-vocabulary lexicon builders

Each of these is an independent extractor that processes a specific
section of the source and produces one of the closed-vocabulary
reference files.

### §9.1 Materia medica (pp. 444–453)

```
INPUT     pp. 444–453 of the OCR (categorised raw materials)
TOOL      pipeline/extract_materia_medica.py
PROCESS   Two-column layout (gutter at x≈0.5).
          Section headers detected by Sinhala-substring match:
            "උද්භිද ද්‍රව්‍ය"  → section="plant"
            "පාර්ථිව ද්‍රව්‍ය" → section="mineral"
            "ජාන්තව ද්‍රව්‍ය"  → section="animal_origin"
          Section transitions happen mid-page; recorded by y-position.
OUTPUT    data/lexicons/materia_medica.json
          → 771 substances total:
            • 647 plants (උද්භිද)
            • 82 minerals (පාර්ථිව)
            • 42 animal-origin (ජාන්තව)
EXAMPLE   "මී පැණි": {"section": "animal_origin", "page": 452,
                       "col": "R", "y": 0.7907}
```

### §9.2 Pratinidhi vocabulary (pp. 77–81)

```
INPUT     pp. 77–81 (substitute-substance glossary)
TOOL      pipeline/extract_pratinidhi.py
PROCESS   Three-column layout: [entry_num | source+paraphrase | substitute]
          Y-tolerance 0.013 with absolute (non-drifting) row anchor.
OUTPUT    data/lexicons/pratinidhi_lookup.json
          → 143 entries, e.g.:
            {"num": 102,
             "lhs_si":     "මධුයෂ්ටී",       ← Sanskrit headword
             "lhs_alt_si": "වැල්මී",          ← Sinhala paraphrase (SAME substance)
             "rhs_si":     "ධාතකී = මලිතමල්"  ← SUBSTITUTE (different substance)
            }
          + by_lhs / by_rhs / by_alt indexes for fast lookup.
```

**Critical distinction**: `lhs_si ↔ lhs_alt_si` is a same-substance
language pair (used by the resolver Module C as a Sinhala→Sanskrit
bridge). `lhs_si → rhs_si` is a substitute relationship (used by the
KG as `SUBSTITUTES_FOR` edges). Never the same.

### §9.3 Mahā-kaṣāya groups (pp. 82–90)

```
INPUT     pp. 82–90 (Caraka's 50 therapeutic-action groups)
TOOL      pipeline/extract_mahakashaya.py
PROCESS   Nested structure parsed via regex on the concatenated text:
            <N>. <ordinal> වර්ගය                  → varga header
            <M>. <ganaName> ද්‍රව්‍ය:-            → gana paragraph
              (or "ගණය:-" — both markers accepted)
            substance1, substance2, …             → comma-separated list
          Canonical varga number derived from the ordinal word
          (not the OCR'd digit, which mis-reads "3" as "4" on p.83).
OUTPUT    data/lexicons/mahakashaya_groups.json
          → 10 vargas · 50 ganas · 436 substance mentions · 279 unique
EXAMPLE   varga 5 (පඤ්චම, "fifth"):
            gana 1: ස්නේහෝපග (oleation-supporting) → 10 substances
            gana 2: ස්වේදනෝපග (fomentation-supporting) → 10 substances
            …
```

### §9.4 Unit equivalences (pp. 65–68, 472–477, 480–481, 487–488)

```
INPUT     Page images (hand-curated; OCR scrambles the table layout)
TOOL      visual transcription → data/lexicons/unit_equivalences.json
PROCESS   Three-layer JSON:
            symbols:   surface form → {iast, kind, aliases}
            systems:   {sri_lankan, yauna_indian, tola_astanga,
                        tola_modern, metric, imperial}
                       each with absolute_grams + absolute_ml + ladder
            ladders:   verbatim N <A> = 1 <B> rows for audit
OUTPUT    43 symbols across 6 systems. ANCHOR: 1 pala = 60 g
          (Sri Lankan, pp.65 + 480) versus 48 g (Yauna, p.477).
```

The companion runtime helper is `knowledge_graph/dosage.py` with
`UnitRegistry.to_grams(text, system="sri_lankan")` that parses both
"කලං 2" (unit before number) and "2 කලං" forms.

### §9.5 Sanskrit-bridge resolver (Modules A + B + C + Tier 2/3)

This is the largest single subsystem. It maps every Sinhala token
in the corpus to a Sanskrit lemma + MW gloss, when possible.

```
INPUT     data/structured/*.json
          (902 unique ingredient surfaces, 256 names, 1040 prose tokens)
TOOL      resolvers/sanskrit_resolver.py
PROCESS   Per token:
            1. Module A — classify as tatsama/other/artefact
               (Mishra Sinhala signal: aspirate ඛඝඡඣ..., sibilant ශෂ,
                palatal-nasal ඥ, vocalic-r ඍෘ, word-initial cluster).
            2. If tatsama:
               Module B → Aksharamukha (Sinhala → IAST) → MW lookup
               (with suffix stripping for -ya/-aya/-yā/-va/-ṁ/-ḥ).
            3. If miss, Tier 2 dict-driven sandhi:
               split IAST so every piece is itself an MW headword.
            4. If still miss, Tier 3 sanskrit_parser:
               spawn memory-isolated worker subprocess
               (RLIMIT_AS=1.5GB, SIGALRM=8s, recycle every 50 words).
            5. If still miss and Module C lookup hits:
               surface → pratinidhi.by_alt → Sanskrit equivalent → MW.
            6. If still miss → unresolved, kept with method=None.
OUTPUT    data/lexicons/{ingredients,names,prose}_lexicon.json
          + parser_recoveries.jsonl (Tier-3 audit trail)
```

Measured resolution rates:

| Field | Total tatsama | Direct (T1) | +sandhi (T2) | +parser (T3) | +pratinidhi (C) | **Total** |
|---|---:|---:|---:|---:|---:|---:|
| Ingredients | 948 | 689 | +61 | +14 | +19 | **83 %** |
| Formula names | 325 | 97 | +98 | +51 | +5 | **77 %** |
| Prose | 1 231 | 528 | +238 | +51 | +15 | **67 %** |

### §9.6 External-ID enrichers

```
INPUT     Resolved Sanskrit lemmas (with Latin binomials extracted
          from MW glosses for plants; with IAST forms for diseases)
TOOL      enrichers/botanical_powo.py  +  enrichers/icd11_tm2_mapper.py
PROCESS   POWO: pykew API → IPNI LSID + modern accepted name + family.
          ICD-11 TM2: WHO OAuth2 + entity-tree crawl + 5-tier matcher
                       (exact / fuzzy_high / prefix / fuzzy_low / english).
OUTPUT    data/lexicons/botanical_powo.json  →  69/85 (81 %) LSIDs
          data/lexicons/indication_icd11_tm2.json  →  49/56 (88 %) TM2 codes
```

This is the **interoperability layer**. POWO LSIDs make our plants
queryable against any taxonomic database; ICD-11 TM2 codes do the
same for diseases.

---

## §10. Knowledge-graph build

### §10.1 Load every input

```
INPUT     • All Vol-I _structured.json files
          • Yogamālāva structured.json
          • All 9 lexicons from §9
TOOL      knowledge_graph/build.py :: load_inputs
PROCESS   jload each file; build a Sinhala-surface → section lookup
          from materia_medica for fast classification.
OUTPUT    in-memory `inputs` dict carrying every artefact
```

### §10.2 Walk every formula, emit nodes + edges

For each formula entry:

```
STEP A  Create the Formulation node:
            formula:vol1/<batch>/<num>  type=Formulation
            name_si, source_register=tabular/verse, source_page
STEP B  Detect IS_TYPE via name-suffix:
            "ත්‍රිකටු චූර්ණය" → suffix "චූර්ණය" → IS_TYPE → prep:cūrṇa
STEP C  For each ingredient (in යෝගය):
            • Look up the surface in ingredients_lexicon (resolver result).
            • classify_ingredient(lemma, gloss) → Plant/Mineral via
              KNOWN_MINERAL_LEMMAS + mineral-gloss keywords.
            • Override via materia_medica.json:
                if section disagrees, re-classify and re-namespace
                (plant:_si_X → animal:_si_X for honey, ghee, milks).
            • POWO enrichment: if MW gloss yields a Latin binomial we
              have in POWO, attach the IPNI LSID externally.
            • Emit CONTAINS(formulation, substance) with:
                parts | quantity_text | quantity_unit | quantity_grams
              quantity_grams via dosage.to_grams() if raw text matches.
STEP D  DOSED_WITH from anupāna:
            scan අනුපාන text for VEHICLE_HINTS phrases
            ("මී පැණි", "ගිතෙල්", "කිරි", …).
            Emit DOSED_WITH(formulation, vehicle_node) where the
            vehicle is typed AnimalOrigin (madhu/ghṛta/kṣīra) or Plant
            (sesame oil, castor oil, warm water).
STEP E  TREATS from prayoga:
            tokenise ප්‍රයෝග text; for each token, prose_lexicon →
            Sanskrit lemma → tm2 lookup → emit TREATS(formulation, disease).
STEP F  CO_OCCURS:
            for every pair of Plant ingredients in this formula,
            increment co_pairs[(a,b)].
```

After all formulas are walked:

```
STEP G  Mahā-kaṣāya wiring:
            For each (varga, gana) → ensure a PharmacologicalProperty
            node (axis="karma", canonical_si=ganaName).
            For each substance listed in the gana →
              ensure Plant/Mineral/AnimalOrigin node via materia_medica
              classification (may CREATE the node if not yet in the KG);
              emit HAS_PROPERTY edge.
STEP H  Pratinidhi-substitute wiring:
            For each entry with rhs_si:
              ensure substitute nodes for each comma-separated
              substance in rhs_si;
              emit SUBSTITUTES_FOR(substitute_node, source_node)
                with substitution_rule="abhāva-pratinidhi".
STEP I  CO_OCCURS edges:
            For (a,b) pairs with count ≥ MIN_COOCCURRENCE (default 3),
            emit CO_OCCURS edges, capped at MAX_COOCCURRENCE.
```

### §10.3 Export in four formats

```
TOOL      knowledge_graph/build.py :: export_jsonld / export_cypher / export_turtle
PROCESS   For JSON-LD: every node/edge becomes one item in @graph,
          with @id/@type, plus @context pointing to docs/context.jsonld.
          For Cypher: MERGE (n:Type {id}) for nodes; MATCH+MERGE for edges.
          For Turtle: prefixed IRIs nl:Type, ent:internal_id.
OUTPUT    knowledge_graph/{kg.jsonld, kg.cypher, kg.ttl, build_report.json}
```

### §10.4 Latest measured KG

```
4 089 nodes  ·  12 754 edges

Nodes by type:
  Plant                       3 277
  Formulation                   628
  PharmacologicalProperty        50
  Disease                        49
  Mineral                        51
  AnimalOrigin                   19
  PreparationType                10
  Route                           5

Edges by type:
  CONTAINS                   11 007    (48.8% with quantity_grams populated)
  TREATS                        562
  HAS_PROPERTY                  436
  DOSED_WITH                    215
  CO_OCCURS                     200
  IS_TYPE                       179
  SUBSTITUTES_FOR               155

External-ID coverage:
  Plant_with_POWO_LSID           35  (11.6% of resolved plants)
  Disease_with_ICD11_TM2         47  (96 % of disease nodes)
```

---

## §11. Validation (4 layers)

### §11.1 Layer 1 — programmatic checks

```
TOOL      validate/validate_kg.py
LAYER 1   SHACL conformance (against validate/shapes.ttl)
            → every Formulation has source_register
            → every Disease has canonical_iast + english_rubric
            → every Plant has canonical_iast OR canonical_si
            → PreparationType/Route limited to closed enums
          Anchor probes (validate/anchors.yaml)
            → jvara → ICD-11 TM2 "SP51 / Fever"
            → kāsa  → "SL41 / Cough"
            → viṣṇukrānti → POWO family "Convolvulaceae"
            → කොත්තමල්ලි, එන්සාල්, වැල්මී → is_unresolved=true
          Provenance presence: every node + edge has the required fields.
          ID-format regex: ^[a-z][a-z_]*:\S+
          Edge domain/range: CONTAINS Formulation→{Plant,Mineral,AnimalOrigin}, …
          Cardinality: tabular formulations have ≥ 1 CONTAINS.
OUTPUT    validate/validation_report.{md,json}
RESULT    SHACL conforms · 0 prov-missing nodes · 0 prov-missing edges
          · anchors 13/16 (81 %)
```

### §11.2 Layer 2 — cross-source re-verification

```
LAYER 2   POWO re-verify: 30 randomly-sampled Plant nodes with
          external.powo_lsid → re-fetch from POWO, compare;
          require ≥ 95 % agreement.
          ICD-11 re-verify: 20 randomly-sampled Disease nodes
          with external.icd11_tm2 → re-fetch from WHO API.
RESULT    POWO 30/30 (100 %) · ICD-11 20/20 (100 %)
```

### §11.3 Layer 3 — expert spot-check (human-in-loop)

```
LAYER 3   Write a 100-item TSV sample of randomly chosen edges
          (validate/expert_sample.tsv) for an Ayurvedic-physician /
          Sinhala-philologist annotator. Each row presents the
          formulation, the edge type, the surface text, and the
          extracted triple; the annotator marks correct/incorrect.
TARGET    Cohen's κ ≥ 0.75 inter-annotator agreement (Notes.txt criterion).
STATUS    Sample written; annotators not yet engaged.
```

### §11.4 Layer 4 — LLM-judge (planned)

```
LAYER 4   For each TREATS/HAS_PROPERTY edge, ask a calibrated LLM
          judge: "given the source paragraph and the extracted triple,
          is the triple supported by the text?"
          Output: judge_score ∈ [0,1] per edge.
          Reference: Lavrinovics et al. 2025 fact-checking framework.
STATUS    Design only; will be added once Layer 3 has ground truth
          to calibrate against.
```

---

# Part III — A worked end-to-end example

Trace formula **44 (ත්‍රිකටු චූර්ණය = Trikaṭu Cūrṇa)** from page 172
through every stage.

### §12.1 Stage 0 — OCR

GCV renders page 172 → JSON tree. Relevant word boxes (after
shrink_ocr_v4's row clustering):

```
y=0.07  L: "44."  L: "යෝග නාමය"  C: ":-"  R: "ත්‍රිකටු චූර්ණය"
y=0.10  L: ""     L: "යෝගය"       C: ":-"  R: "තිප්පිලි"
y=0.12                                       R: "ඉඟුරු"
y=0.14                                       R: "ගම්මිරිස්"
y=0.18  L: ""     L: "සංස්කරණය"  C: ":-"  R: "සමව ගෙන කොටා පෙළා කෙළවර කරයි."
y=0.22  L: ""     L: "ප්‍රයෝග"   C: ":-"  R: "කාස, ශ්වාස, අග්නිමාන්ද්‍ය"
y=0.26  L: ""     L: "අනුපාන"   C: ":-"  R: "මී පැණි"
y=0.30  L: ""     L: "මාත්‍රාව"  C: ":-"  R: "ග්‍රෑ 5"
```

### §12.2 Stage 3 — state machine

```
ENTRY_HEADER state → "44." sets entry_num=44 →
                   → "ත්‍රිකටු චූර්ණය" sets formula name
ENCOUNTERED "යෝගය" → transition YOGAYA
  YOGAYA collects: "තිප්පිලි", "ඉඟුරු", "ගම්මිරිස්"
ENCOUNTERED "සංස්කරණය" → transition SANSKARANAYA
  SANSKARANAYA collects: "සමව ගෙන කොටා පෙළා කෙළවර කරයි."
ENCOUNTERED "ප්‍රයෝග" → transition PRAYOGA
ENCOUNTERED "අනුපාන" → transition ANUPANA
ENCOUNTERED "මාත්‍රාව" → transition MATRAVA
  MATRAVA collects: "ග්‍රෑ 5"  → quantity_text matches → ග්‍රෑ=5.0
```

Output structured entry:

```json
{"අංකය":44, "යෝග නාමය":"ත්‍රිකටු චූර්ණය",
 "යෝගය":[{"ද්‍රව්‍යය":"තිප්පිලි", "ග්‍රෑ":0.0},
          {"ද්‍රව්‍යය":"ඉඟුරු",   "ග්‍රෑ":0.0},
          {"ද්‍රව්‍යය":"ගම්මිරිස්","ග්‍රෑ":0.0}],
 "සංස්කරණය":"සමව ගෙන කොටා පෙළා කෙළවර කරයි.",
 "ප්‍රයෝග":"කාස, ශ්වාස, අග්නිමාන්ද්‍ය",
 "අනුපාන":"මී පැණි",
 "මාත්‍රාව":"ග්‍රෑ 5",
 "source_page":172}
```

### §12.3 Resolver applied to each ingredient

```
"තිප්පිලි" → Module A: NO Mishra signal → "other" bucket
            → Module C: not in pratinidhi.by_alt
            → unresolved (tadbhava long tail)

"ඉඟුරු"    → Module A: NO signal → "other"
            → Module C: not in pratinidhi → unresolved

"ගම්මිරිස්" → Module A: NO signal → "other"
             → unresolved
```

All three are *tadbhava* — phonologically nativised Sanskrit (one
proposal cites *śṛṅgavera* > *iňguru*). The current resolver leaves
them unresolved; they become Sinhala-only Plant nodes:

```
plant:_si_තිප්පිලි    canonical_si="තිප්පිලි", is_unresolved=true
plant:_si_ඉඟුරු        canonical_si="ඉඟුරු",   is_unresolved=true
plant:_si_ගම්මිරිස්   canonical_si="ගම්මිරිස්", is_unresolved=true
```

But the **materia-medica authority** classifies these correctly:
- "තිප්පිලි" ∈ materia_medica.section="plant" → `mm_section=plant` tag
- "ඉඟුරු" ∈ materia_medica.section="plant" → `mm_section=plant`
- "ගම්මිරිස්" ∈ materia_medica.section="plant" → `mm_section=plant`

### §12.4 KG build for entry 44

Triples emitted (with full provenance):

```
nodes:
  formula:vol1/151-to-200/44  Formulation
                              name_si="ත්‍රිකටු චූර්ණය", source_register=tabular,
                              source_page=172
  prep:cūrṇa                  PreparationType  (closed enum)
  plant:_si_තිප්පිලි          Plant   mm_section=plant
  plant:_si_ඉඟුරු             Plant   mm_section=plant
  plant:_si_ගම්මිරිස්         Plant   mm_section=plant
  vehicle:madhu               AnimalOrigin  (also_acts_as_vehicle=true)

edges:
  formula:vol1/151-to-200/44 ─ IS_TYPE        → prep:cūrṇa
                                (matched suffix "චූර්ණය")
  formula:vol1/151-to-200/44 ─ CONTAINS       → plant:_si_තිප්පිලි  (parts=1, quantity_text="")
  formula:vol1/151-to-200/44 ─ CONTAINS       → plant:_si_ඉඟුරු     (parts=1)
  formula:vol1/151-to-200/44 ─ CONTAINS       → plant:_si_ගම්මිරිස් (parts=1)
  formula:vol1/151-to-200/44 ─ DOSED_WITH     → vehicle:madhu       (matched phrase "මී පැණි")

(plus, from CO_OCCURS computation across all formulas:)
  plant:_si_තිප්පිලි ─ CO_OCCURS → plant:_si_ඉඟුරු    count=N1
  plant:_si_තිප්පිලි ─ CO_OCCURS → plant:_si_ගම්මිරිස් count=N2
  plant:_si_ඉඟුරු    ─ CO_OCCURS → plant:_si_ගම්මිරිස් count=N3
```

The `ප්‍රයෝග` text "කාස, ශ්වාස, අග්නිමාන්ද්‍ය" is tokenised; each
token goes through prose_lexicon → if resolved to a Sanskrit lemma
present in our ICD-11 mapping, a TREATS edge is emitted:

```
  formula:vol1/151-to-200/44 ─ TREATS → disease:kāsa
                                 (evidence_level="canonical_text",
                                  external.icd11_tm2="SL41",
                                  english_rubric="Cough")
  formula:vol1/151-to-200/44 ─ TREATS → disease:śvāsa  (TM2 "SL42")
  formula:vol1/151-to-200/44 ─ TREATS → disease:agni-māndya
                                 (NB: this lemma may not be in TM2;
                                  edge emitted only when TM2 lookup hits.)
```

### §12.5 Validator output for entry 44

```
SHACL          conforms   (all nodes carry extractor_version + created_at)
Provenance     complete   (every edge has source_doc + source_record_id)
ID format      OK         (all IDs match ^[a-z][a-z_]*:\S+)
Edge ranges    OK         (CONTAINS Formulation→Plant ✓, IS_TYPE Formulation→PreparationType ✓)
Anchors        PASS       (kāsa → SL41 verified)
POWO re-verify N/A        (no resolved-Plant LSIDs to test in this entry —
                            the three ingredients are unresolved tadbhava)
```

### §12.6 The same entry in JSON-LD (export view)

```jsonld
{
  "@context": "https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp/docs/context.jsonld",
  "@graph": [
    {"@id": "formula:vol1/151-to-200/44", "@type": "Formulation",
     "name_si": "ත්‍රිකටු චූර්ණය", "source_register": "tabular",
     "source_page": 172, "provenance": { … }},
    {"@type": "IS_TYPE",   "from": "formula:vol1/151-to-200/44", "to": "prep:cūrṇa"},
    {"@type": "CONTAINS",  "from": "formula:vol1/151-to-200/44",
                            "to":   "plant:_si_තිප්පිලි",  "parts": 1},
    {"@type": "CONTAINS",  "from": "formula:vol1/151-to-200/44",
                            "to":   "plant:_si_ඉඟුරු",    "parts": 1},
    {"@type": "CONTAINS",  "from": "formula:vol1/151-to-200/44",
                            "to":   "plant:_si_ගම්මිරිස්", "parts": 1},
    {"@type": "DOSED_WITH","from": "formula:vol1/151-to-200/44",
                            "to":   "vehicle:madhu",
                            "provenance": {"matched_phrase": "මී පැණි"}},
    {"@type": "TREATS",    "from": "formula:vol1/151-to-200/44",
                            "to":   "disease:kāsa",
                            "evidence_level": "canonical_text",
                            "provenance": {"matched_lemma": "kāsa",
                                            "matched_surface": "කාස"}}
  ]
}
```

The same triples exist in `kg.cypher` (for Neo4j) and `kg.ttl`
(for Apache Jena / OWL tooling).

---

# Part IV — What's planned next

## §13. The prose extractor (Blocks A–F)

The pipeline above handles **tabular** and **verse-form** registers
deterministically. **Free-style prose** (narrative passages in Vol I,
all of Vols II/III when scanned, clinical notebooks) is the next
frontier. The architecture (see `docs/curious-inventing-eagle.md`):

```
┌── L0  Source prose text                                                  ──┐
│   ▼                                                                       │
│   L1  Sentence + clause segmentation                       ← Block B       │
│   ▼                                                                       │
│   L2  Aho-Corasick gazetteer match (closed-vocabulary)     ← Block A       │
│   ▼                                                                       │
│   L3  Resolver application on residual tokens              (existing)      │
│   ▼                                                                       │
│   L4  Schema-typed span labelling (NER role)               ← Block C       │
│   ▼                                                                       │
│   L5  Sentence-template grammar (rule-based RE)            ← Block D       │
│   ▼                                                                       │
│   L6  Schema validator (reject at emission)                (existing)      │
│   ▼                                                                       │
│   L7  Determinism gate (stable sort + byte-stable serialise) ← Block E     │
│   ▼                                                                       │
│   L8  KG merge as source_register="prose"                  (existing)      │
└───────────────────────────────────────────────────────────────────────────┘
```

Three deterministic-first NLP techniques are folded in:
**Aho-Corasick** at L2 (single-pass O(n) gazetteer scan),
**akṣara-aware tokenisation** at L1 (Sinhala grapheme clusters, not
code points), and **Levenshtein automata** for OCR-tolerance (matches
within edit distance 1, same scan as Aho-Corasick).

The acceptance test: a held-out paragraph extracts with ≥ 75 %
token-coverage at zero hallucinations.

## §14. The MCS3306 proposal

The work above is the empirical backbone of a UCSC MSc-CS individual-
project proposal (15 credits). The proposal makes four contributions:

1. **Methodological**: the memory-isolated subprocess pattern for
   bounding memory-pathological NLP libraries (Tier 3 of the resolver).
2. **Resource**: the first machine-readable cross-lingual bridge
   between Sinhala script and Sanskrit lexical resources.
3. **Knowledge representation**: the first knowledge graph of
   traditional Sri Lankan medicine, with ICD-11 TM2 + POWO bindings.
4. **Empirical**: a controlled measurement of whether KG-grounded
   features improve NER on Sinhala Ayurvedic text — clean ablation:
   gazetteer baseline / feature-rich CRF / KG-augmented CRF.

The draft is at `Proposal/MCS3306_proposal_draft.md`. The bibliography
is `docs/references.{md,bib}` — 26 entries spanning comparable KGs
(GRAYU, AyurKOSH, HerbKG, Āyurjñānam), international standards (ICD-11
TM2, POWO, ChEBI), schema-constrained extraction (RELATE, SPIREX,
ODKE+), and validation methodology (Zaveri 2016, Cohen 1960, OAEI
benchmarks).

---

## §15. Reproducing the pipeline

```bash
# Clone + setup
git clone <repo>
cd sinhala-traditional-medicine-nlp
python3 -m venv .venv
.venv/bin/python -m pip install aksharamukha pycdsl sanskrit_parser \
                                indic-transliteration pykew requests \
                                rapidfuzz rdflib pyshacl

# Stage 0 (one-time): OCR via GCV
python pipeline/ocr_gcv.py --pdf data/source/Pharmacopoeia_Vol_I.pdf

# Stages 1–3 (tabular): extracts 852 formulas
python pipeline/pipeline.py --start 151 --end 500

# Resolver Modules A/B/C + Tier 2 + Tier 3 (~5 min)
cd data/structured
../../.venv/bin/python ../../resolvers/sanskrit_resolver.py \
    --field all --with-parser --parser-batch 50 --parser-mem-cap 1500

# Closed-vocabulary lexicons
python pipeline/extract_materia_medica.py
python pipeline/extract_pratinidhi.py
python pipeline/extract_mahakashaya.py
# (unit_equivalences.json is hand-curated; pp.471-475 audit pending)

# Enrichers
python enrichers/botanical_powo.py
python enrichers/icd11_tm2_mapper.py    # needs ICD_CLIENT_ID/SECRET env

# KG build
python knowledge_graph/build.py

# Validate
python validate/validate_kg.py
```

---

## §16. The shape of the final artefact

```
sinhala-traditional-medicine-nlp/
├── README.md                          ← Project overview
├── docs/
│   ├── WALKTHROUGH.md                 ← This document
│   ├── kg_schema.md                   ← The contract (v1.1)
│   ├── context.jsonld                 ← JSON-LD context for the schema
│   ├── validation_methodology.md      ← Zaveri 4-category framework
│   ├── references.md / .bib           ← 26-entry bibliography
│   ├── architecture.md                ← Pipeline thresholds + design rationale
│   ├── output_schema.md               ← Structured-JSON field reference
│   ├── pipeline_notes.txt             ← Data-quality catalogue
│   └── unit_audit_pp471-475.md        ← Classical-unit audit checklist
├── pipeline/                          ← OCR + extraction (Stages 0–3)
├── resolvers/                         ← Sinhala→Sanskrit bridge
├── enrichers/                         ← External-authority bindings
├── knowledge_graph/                   ← KG builder + dosage normaliser
│   ├── build.py
│   ├── dosage.py
│   ├── kg.{jsonld, cypher, ttl}       ← The graph in three views
│   └── build_report.json
├── validate/                          ← 4-layer validator
│   ├── validate_kg.py
│   ├── shapes.ttl                     ← SHACL constraints
│   ├── anchors.yaml                   ← Positive + negative anchor tests
│   ├── validation_report.{md, json}
│   └── expert_sample.tsv              ← Layer-3 human annotation sample
├── data/
│   ├── source/                        ← Original PDFs (LFS-tracked)
│   ├── ocr/                           ← GCV outputs
│   ├── rows/                          ← Row-clustered intermediates
│   ├── structured/                    ← Formulation entries
│   └── lexicons/                      ← All 9 closed-vocabulary JSONs
├── Proposal/
│   └── MCS3306_proposal_draft.md
└── analysis/
    └── nlp_stats.py                   ← Corpus statistics
```

---

## §17. Headline numbers

| | |
|---|---:|
| Source pages OCR'd | 525 |
| Vol I structured formulas | 852 |
| Yogamālāva structured entries | 145 |
| Closed-vocabulary substances catalogued | 771 + 143 + 279 |
| Sinhala-Sanskrit bridge resolution rate | 81 % / 77 % / 67 % |
| POWO LSIDs assigned | 69 / 85 (81 %) |
| ICD-11 TM2 codes assigned | 49 / 56 (88 %) |
| KG nodes | 4 089 |
| KG edges | 12 754 |
| CONTAINS edges with parsed grams | 48.8 % |
| SHACL conformance | 100 % (0 violations) |
| Provenance complete | 100 % (0 missing) |
| POWO + ICD-11 re-verify | 100 % each |
| Anchor probe pass rate | 81 % (13/16) |

---

## §18. The one-paragraph version

A 525-page Sinhala medical reference becomes a queryable graph of
**4 089 nodes and 12 754 edges**, bound to **WHO ICD-11 TM2** disease
codes and **POWO** plant identifiers. The pipeline is fully
deterministic, fully audited, fully provenance-tracked. Everything in
the graph traces back to a source page and a source span. The
substrate exists; the prose-extraction layer is what unlocks
processing of the much larger free-style corpus that remains.

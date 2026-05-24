# Knowledge Graph

The KG that the pipeline + resolvers + enrichers feed into.

**Status: v1 BUILT** (`build.py`, run on 2026-05-24).

For the formal schema contract (10 node types, 13 edges, provenance,
serialisation views, schema-constrained-extraction principle), see
[`../docs/kg_schema.md`](../docs/kg_schema.md).

---

## Outputs

| File | What |
|---|---|
| `kg.jsonld` | JSON-LD `@graph` of all nodes + edges, referencing [`../docs/context.jsonld`](../docs/context.jsonld). |
| `kg.cypher` | Neo4j Cypher script — `CREATE CONSTRAINT`s + `MERGE` statements for nodes + relations. |
| `kg.ttl` | RDF Turtle — same data in semantic-web form. |
| `build_report.json` | Per-type node and edge counts; external-ID coverage. |
| `build.py` | The builder — see below. |

---

## How to build (or rebuild)

```bash
python knowledge_graph/build.py
# optional flags:
python knowledge_graph/build.py --max-cooccurrence 500
python knowledge_graph/build.py --no-yogamalawa
```

No extra dependencies beyond the standard library. The build is a
single ~25-second pass that reads all the corpus + resolver +
enrichment artefacts, emits all three serialisations, and writes the
report.

---

## Current v1 build

```
Nodes  3 642 total
  ── Plant            2 926
        297 resolved to Sanskrit (with the resolver's lemma + gloss)
      2 629 unresolved (Sinhala surface forms only — awaiting R3/R4
            lexicons for tadbhava + vernacular normalisation)
  ── Formulation        628   (Vol I structured + Yogamālāva)
  ── Disease             49   (47 with ICD-11 TM2 codes from the enricher)
  ── Mineral             24   (e.g. saindhava-lavaṇa, gandhaka, bhasma family)
  ── PreparationType     10   (kaṣāya, kvātha, taila, ghṛta, cūrṇa, kalka,
                                gulika, ariṣṭa, avaleha, bhasma)
  ── Route                5   (oral, anuvāsana, nasya, basti, abhyaṅga)

Edges 12 163 total
  ── CONTAINS         11 007   one per ingredient cell (Vol I)
  ── TREATS              562   formula → disease, mapped via prose-lexicon
                                resolution + ICD-11 TM2 lookup
  ── DOSED_WITH          215   formula → vehicle (madhu, ghṛta, sesame oil,
                                castor oil, milk, warm water, …)
  ── CO_OCCURS           200   plant-pair co-occurrence within formulas
                                (capped at top 200 by count, min count 3)
  ── IS_TYPE             179   formula → preparation type by name suffix
```

### External-ID coverage

| | n |
|---|---:|
| `Plant` with POWO IPNI LSID | 33 (11.1 % of resolved Plants) |
| `Plant` with Latin binomial | 33 |
| `Disease` with ICD-11 TM2 code | 47 / 49 |

The 33 POWO-bound Plants are limited by how many Sanskrit lemmas have
an explicit Latin binomial in their Monier-Williams gloss. The full
botanical seed (`../data/lexicons/botanical_candidates.json`) contains
87 binomials but most aren't extracted via the gloss-regex path
exercised here — a v2 builder could lookup the *resolver* directly to
pull more. For now the resolved-Plant POWO coverage matches what the
upstream pipeline produces.

---

## Schema mapping

The build is a literal implementation of the design in
[`../docs/kg_schema.md`](../docs/kg_schema.md). Each emitted item is a
valid instance under [`../docs/context.jsonld`](../docs/context.jsonld):

| KG-schema concept | Where in build.py |
|---|---|
| Internal IDs `formula:<batch>/<num>`, `plant:<lemma>`, etc. | id-construction in main loop |
| Provenance per node and edge | every `ensure_node` / `add_edge` carries `extractor_version`, `created_at`, `provenance` |
| External authority IDs (POWO, ICD-11 TM2) | `attach_powo_external`, Disease node `external{}` block |
| Schema-constrained edges | builder only emits the 6 edge types defined in §5 of `kg_schema.md` |

---

## Known limits (rolled into the build report)

- **Plant explosion** (2629 unresolved Plants): this faithfully reflects
  the corpus state. ~73 % of distinct ingredient Sinhala surface forms
  do not yet have a Sanskrit lemma — they're tadbhava or vernacular,
  awaiting R3/R4 lexicons (which need expert/lexicographer work and are
  explicitly post-MSc in the proposal scope).
- **Ingredient-cell bleed**: a few CONTAINS edges point at a Plant node
  whose `canonical_si` is an entire comma-separated phrase or a
  preparation-instruction fragment. This is the known upstream
  OCR/Stage-3 artefact catalogued in
  [`../docs/pipeline_notes.txt`](../docs/pipeline_notes.txt) (~17 % of
  ingredient tokens are structural OCR junk). The KG builder
  faithfully represents what's in the structured JSON; cleaning
  it requires fixing the extractor, not the builder.
- **POWO coverage of resolved Plants** is 11.1 %. Increasing this needs
  either (a) running the botanical enricher on **every** resolved
  Sanskrit lemma, not only those with a Latin binomial in the MW
  gloss, or (b) better Latin-binomial extraction from glosses. A v2
  enrichment pass is the right place for either.
- **CO_OCCURS edges capped at 200** to keep the graph compact; raise
  with `--max-cooccurrence`.
- **Yogamālāva entries contribute Formulation nodes but no CONTAINS
  edges**, because the verse-form Stage 3 doesn't yet emit a separate
  ingredient list. Mining the verse text for ingredient mentions is a
  natural Stage-3 v3 enhancement.

---

## Next steps

The big unlocks from here:

1. **Ingredient normalisation** (R3 / `VARIANT_OF` edges) — collapses
   the 2629 unresolved Plant nodes into the ~300 canonical the
   proposal targets. Needs the Āyurvēda Pharmacopoeia of Sri Lanka
   digitised plus a botanist's curation pass. Post-MSc.
2. **TREATS edges from Yogamālāva** — mine verse text for indication
   keywords against `prose_lexicon`. ~1 hour of work.
3. **REFERENCES edges from `සංස්කරණය`** — regex for "see formula N" /
   "අංක N". ~30 min of work; small data.
4. **Graph analysis** — degree distributions, ingredient-cluster
   modularity, formula-similarity, query-templates. Useful to publish
   alongside the KG release.
5. **Browsable KG** — load `kg.cypher` into a Neo4j AuraDB free tier
   instance and share a query URL for the defence presentation.

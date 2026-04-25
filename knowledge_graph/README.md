# Knowledge Graph

**Status**: Planned — Phase 2 of the thesis project.

---

## Design

### Node Types

| Node | Source field | Est. count (Vol I) |
|---|---|---|
| Formula | `අංකය` + `යෝග නාමය` | 707 |
| Ingredient | `ද්‍රව්‍යය` (after normalization) | ~300 canonical |
| Indication | `ප්‍රයෝග` (NLP extract) | ~50–100 |
| FormulaType | Name suffix (තෛලය, ක්වාථය, චූර්ණය...) | ~10 |
| Adjuvant | `අනුපාන` | ~50 |
| PreparationMethod | `සංස්කරණය` (NLP extract) | ~20–30 |

### Edge Types

| Edge | Source | Available now |
|---|---|---|
| FORMULA → CONTAINS → Ingredient | `යෝගය` | Yes — 11,007 instances |
| FORMULA → TREATS → Indication | `ප්‍රයෝග` | Needs NLP extraction |
| FORMULA → REFERENCES → Formula | `සංස්කරණය` | Needs regex parser |
| FORMULA → IS_TYPE → FormulaType | Name suffix | Yes — regex |
| FORMULA → DOSED_WITH → Adjuvant | `අනුපාන` | Yes |
| Ingredient → CO_OCCURS → Ingredient | co-occurrence | Yes — precomputed |
| Ingredient → VARIANT_OF → Ingredient | normalization | Needs labeling |

---

## Build Plan

### Phase 1 (no labeling required)
- Extract all CONTAINS edges directly from structured JSON
- Infer FormulaType from name suffix patterns (තෛලය=oil, ක්වාථය=decoction, etc.)
- Extract DOSED_WITH edges from `අනුපාන` field
- Build CO_OCCURS edges from precomputed ingredient co-occurrence matrix

### Phase 2 (light NLP)
- Parse REFERENCES edges: regex for "formula N" / "අංක N" patterns in `සංස්කරණය`
- Extract Adjuvant nodes from `අනුපාන` free text

### Phase 3 (after ingredient normalization labeling ~6 hrs)
- Collapse ~2,637 ingredient surface forms to ~300 canonical nodes
- VARIANT_OF edges link surface forms to canonical nodes
- Graph becomes meaningful for traversal

### Phase 4 (after indication NLP)
- Extract disease/indication entities from `ප්‍රයෝග` text
- TREATS edges — most valuable for clinical/research queries

---

## Planned Stack

- **NetworkX** (Python): in-memory graph for analysis and experimentation
- **Neo4j** or **SQLite adjacency table**: persistent queryable store
- No heavy infrastructure needed at current corpus size (~15K edges)

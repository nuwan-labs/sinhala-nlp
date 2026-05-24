# Enrichers — external-ID binding

The resolver in `resolvers/` does the linguistic work — surface form →
canonical Sinhala → IAST → Sanskrit lemma → Monier-Williams gloss.
The **enrichers** in this directory do the next step: bind each
resolved entity to an authoritative external identifier so the KG
interoperates with the international standards.

This is the layer the [schema document](../docs/kg_schema.md)
identifies as the *external-ID-binding stage* (§7).

## Scripts

| File | Purpose | External authority |
|---|---|---|
| `botanical_powo.py` | Plant binomial → POWO IPNI LSID + modern accepted name + family | Royal Botanic Gardens, Kew — Plants of the World Online |
| `icd11_tm2_mapper.py` | Sanskrit indication term → ICD-11 TM2 code + URI | WHO ICD-11 — Traditional Medicine Module 2 |

## Setup

```bash
# extra deps beyond the resolver venv
.venv/bin/pip install requests rapidfuzz
```

For ICD-11, register at `https://icd.who.int/icdapi` and put your
OAuth credentials in a `.env` file (this file is gitignored — it must
never be committed):

```
ICD_CLIENT_ID=…
ICD_CLIENT_SECRET=…
```

## Run

```bash
# Botanical lookup (no auth needed)
.venv/bin/python enrichers/botanical_powo.py

# ICD-11 TM2 mapping (needs the credentials above)
.venv/bin/python enrichers/icd11_tm2_mapper.py
.venv/bin/python enrichers/icd11_tm2_mapper.py --refresh         # force re-crawl
.venv/bin/python enrichers/icd11_tm2_mapper.py --anchors-only    # 10-term smoke test
```

## Outputs

| Path | What |
|---|---|
| `data/lexicons/botanical_powo.json` | One record per Latin binomial: POWO LSID, modern accepted name (resolves 19th-century Monier-Williams names), family, kingdom, accepted-vs-synonym flag |
| `data/lexicons/icd11_tm2_cache.json` | Local cache of every TM2 entity (~700 entities). Subsequent runs are offline unless `--refresh` is passed. |
| `data/lexicons/indication_icd11_tm2.json` | One record per resolved Sanskrit indication term: TM2 code, TM2 entity URI, English rubric, the traditional-system label that matched, match method, confidence |

## Latest measured results

| Enricher | Coverage | Notes |
|---|---|---|
| POWO botanical | **69 / 85 (81 %)** — 36 already-modern names + 33 19th-century synonyms resolved to modern accepted names. 14 no-match (mostly false-positive gloss fragments like "Magadha country", "Vedic inf"). 2 zoological (Columba, Coluber) correctly rejected. | First run end-to-end took ~25 s. |
| ICD-11 TM2 mapper | **49 / 56 (88 %)** matched. Of 10 anchor terms (`jvara, kāsa, śvāsa, kuṣṭha, gulma, arśas, meha, aśmarī, udāvarta, ānāha`), 9 map to the correct TM2 code. Match-method breakdown: 20 sanskrit_exact · 4 sanskrit_fuzzy_high · 8 sanskrit_prefix · 8 sanskrit_compound_head · 10 english_keyword · 7 unmatched. | First crawl ~30 s; subsequent runs offline. |

## How matching works (ICD-11 TM2)

The mapper takes advantage of how WHO encodes traditional-medicine
names. Each TM2 entity carries an `indexTerm` array; the rows that
contain Sanskrit/Tamil/Arabic equivalents use the convention:

```
(a) <Ayurveda/Sanskrit>   (b) <Siddha/Tamil>   (c) <Unani/Arabic>
```

For example, `SL41` (Cough disorder) has the indexTerm

```
(a) kāsaḥ  (b) Irumal nōy  (c) Su‘āl-o-Surfa
```

The mapper parses these, builds a separate index for the Ayurveda
column, and matches in five tiers:

1. **Sanskrit exact** — sandhi-stripped deburred lemma equals the
   indexed Sanskrit term. Confidence 1.00.
2. **Sanskrit high-fuzzy** (rapidfuzz ratio ≥ 88) — catches
   singular/plural variants like `arśas` ↔ `arśaḥ`. Confidence 0.85–1.0.
3. **Sanskrit prefix or compound-head** — Sanskrit compounds have
   their head on the right, so `kuṣṭha` is the head of
   `dhātugatakuṣṭha`. Multiple matching variants vote for the parent
   entity, which keeps `kuṣṭha` → SN49 (Integumentary disorder)
   rather than a specific sub-type. Confidence 0.85.
4. **Sanskrit low-fuzzy** (ratio 85–87) — secondary fuzzy. Confidence
   0.85–0.87.
5. **English-gloss keyword** — last resort: the Monier-Williams gloss
   contains a disease keyword (fever, cough, …) that matches a TM2
   entity's English title. Confidence 0.55.

The lower-confidence tiers are flagged in the `matched_via` field, so
downstream consumers can filter on `confidence ≥ τ`.

## Known limits

- Some less-common Ayurvedic conditions don't yet have a TM2 code (TM2
  prioritises India's most-common nosology). 7/56 of our terms fall
  here — flagged as `matched_via: null` in the output.
- The English-keyword tier (tier 5) can over-fire on glosses with
  multiple disease keywords (e.g. `ānāha` whose gloss mentions
  "urinary" matches `SR82 Excessive urine pattern` incorrectly). The
  Sanskrit tiers fire first when possible; the English tier is only
  used when all Sanskrit tiers fail.
- POWO no-matches include false positives from the upstream resolver's
  botanical-Latin extractor — gloss fragments like `Magadha country`
  that *look* like Latin binomials. Real plant binomials nearly all
  resolve.

## Where this fits

These outputs feed directly into the planned KG builder
(`knowledge_graph/build.py`, not yet implemented). When that lands, a
`Plant` node will carry the POWO LSID from `botanical_powo.json` as
its `external.powo_lsid` property; a `Disease` node will carry the
TM2 code from `indication_icd11_tm2.json` as `external.icd11_tm2`.
Both are required external IDs in the schema — see
[`docs/kg_schema.md`](../docs/kg_schema.md) §7.

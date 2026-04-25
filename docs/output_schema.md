# Output Schema

## Structured Entry Format

Each formula entry in `data/structured/*.json` uses Sinhala Unicode field names.

```json
{
  "අංකය": 44,
  "යෝග නාමය": "ත්‍රිකටු චූර්ණය",
  "යෝගය": [
    {"ද්‍රව්‍යය": "තිප්පිලි", "ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0},
    {"ද්‍රව්‍යය": "ඉඟුරු", "ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0}
  ],
  "සංස්කරණය": "...",
  "ප්‍රයෝග": "...",
  "අනුපාන": "...",
  "මාත්‍රාව": "...",
  "සටහන": "...",
  "source_page": 172
}
```

---

## Field Reference

| Sinhala key | Transliteration | English | Fill rate |
|---|---|---|---|
| `අංකය` | ankaya | Entry number | 100% |
| `යෝග නාමය` | yoga namaya | Formula name | 99.2% |
| `යෝගය` | yogaya | Ingredient list | 98.4% |
| `සංස්කරණය` | sanskaranaya | Preparation method | 63.1% |
| `ප්‍රයෝග` | prayoga | Usage / Indication | 96.5% |
| `අනුපාන` | anupana | Adjuvant / vehicle | 50.5% |
| `මාත්‍රාව` | matrava | Dosage | 48.4% |
| `සටහන` | satahana | Notes | 35.9% |
| `source_page` | — | GCV batch page number | 100% |

---

## Ingredient Sub-record

Each item in the `යෝගය` array:

| Key | Type | Description |
|---|---|---|
| `ද්‍රව්‍යය` | string | Ingredient name (raw OCR text) |
| `ප්‍රමාණය` | string | Quantity as written (may be empty) |
| `ග්‍රෑ` | float | Grams (parsed, 0.0 if absent) |
| `ලී` | float | Litres (parsed, 0.0 if absent) |

---

## Batch File Wrapper

Each `data/structured/*.json` file has the structure:

```json
{
  "batch": "151-to-200",
  "entries": [...],
  "partial_tail": {...}
}
```

`partial_tail` holds an incomplete entry cut off at the end of a batch, carried forward to be merged with the next batch's first entry.

---

## Known Data Quality Issues

- **Artefact tokens**: ~17.3% of ingredient `ද්‍රව්‍යය` tokens are structural OCR artefacts (punctuation, parentheses, measurement markers)
- **Unicode**: 25.1% of formula names fail NFD normalization; 165 names contain ZWJ characters; all field keys contain ZWJ as part of correct Sinhala Unicode encoding
- **Prose bleed**: ~173 ingredient cells contain preparation instruction text rather than a pure ingredient name (cells > 8 tokens)
- **Cross-references**: `සංස්කරණය` frequently reads "see formula N" rather than inline text, depressing fill rates

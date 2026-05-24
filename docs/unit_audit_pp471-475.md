# Unit-equivalence audit checklist (pp. 471–475)

> **Status:** open — needs Ayurvedic-philology read-through.
>
> This file enumerates what is *visible on each source page* of the
> unit-conversion section. The first pass of `extract_units` attempted
> to encode the equivalences into `data/lexicons/unit_equivalences.json`
> and produced values that contradicted the conventional Sri-Lankan-tolā
> scale (`1 pala ≈ 4 g` rather than `≈ 40 g`). The contradiction is real
> in the source — the pharmacopoeia uses one or more internal scaling
> conventions that are not yet decoded.
>
> Until an expert (Ayurvedic physician / Sanskrit philologist) confirms
> the reading of every row, only the **metric** and **well-documented
> Sri-Lankan-tolā** values are committed to `unit_equivalences.json`.
> The classical ladders below need verbatim transcription + sign-off.

---

## What's on each page

### Page 471 — introduction
- 4 categories of measurement named:
  `ද්‍රවය මානය` (volume), `පාය්ය මානය` (length),
  `කාල මානය` (time), and `කල්ක මානය` (paste).
- Argues for using the **metric (`මෙට්රික්`) system** as the standard
  going forward — the pharmacopoeia itself recommends this.
- No conversion table.

### Page 472 — `චරක මාගධමානචක්‍රය (මුල් පිටපත)` — Caraka Māgadha system, original
- 25-row ladder from `වංශි → තුලා`.
- **No explicit gram column** on this page.
- Each row gives one of `<N> <unit-A> = 1 <unit-B>` plus, in parens,
  an *alternative-name list* (e.g. `(හේම, ධාන්‍යක)` for `māṣaka`).
- Audit task: transcribe the 25 rows verbatim, decide which alternative
  name is the primary, and decide whether to anchor the gram scale
  here or on p. 473.

### Page 473 — Caraka Māgadha continued + `කාලිංග මානය (සුකරුත සංගීත)` system
- Continues the Caraka ladder from `සර්ෂප → තුලා`.
- **Includes** a metric-equivalence column in parens for each row, but
  the numeric values appear in TWO units: `පොසුරේ` (unknown) and
  `ග්‍රෑ` (grams).
- `පොසුරේ` is *probably* a transliteration of an English measurement
  unit (a `pošurē` does not appear in standard Sinhala lexicons); it
  could be an obsolete imperial weight unit (avoirdupois grain?).
- The gram column gives values that scale by 2× per row but anchored
  *low*: `1 pala = 4 g` here, vs. the conventional Caraka `1 pala ≈
  47.5 g`. The pharmacopoeia is internally consistent on this scale
  but the scale itself is unusual.
- Second half of the page begins `කාලිංග මානය` (Kāliṅga system) with
  another ladder.
- Audit task: identify what `පොසුරේ` is. Decide whether to encode
  this scale verbatim (as printed) or to anchor at the conventional
  Caraka scale (1 pala ≈ 47.5 g) and treat the printed numbers as
  an internal annotation.

### Page 474 — `තෝලා චක්‍රය (අෂ්ටාංග සංග්‍රහයෙනි)` — Tolā system from Aṣṭāṅga Saṅgraha
- Ladder from `අණු → තෝලා → ශේර්`.
- Standard 19th-c. British-Indian tola scale.
- Conventional values:
  - 1 mañcāḍi / ratti = 125 mg
  - 8 ratti = 1 māṣaka (≈ 1 g)
  - 12 māṣaka = 1 tolā (= 11.66 g)
  - 80 tolā = 1 sēru (= 933 g)
- Audit task: confirm each row matches the British-Indian convention,
  or note where the pharmacopoeia diverges.

### Page 475 — Tolā system + `නූතන ව්‍යවහාරයෙහි` (modern Sri Lankan usage)
- Continuation of tolā ladder.
- Top notes (`ටීකාව`) cite Sanskrit verses fixing equivalences:
  `“නිෂ්කං ශාණං”` and `“චතුර්හිර් මාෂකඃ ශාණඃ”` — confirms
  `1 niṣka = 1 śāṇa = 4 māṣaka`.
- Modern Sri Lankan usage box at the bottom: standardised colloquial
  Sinhala unit names (`කලඤ්චු`, `පල`, etc.) with explicit equivalence
  to the Tolā ladder.
- Audit task: this page may be the cleanest source for the colloquial
  Sinhala units that appear in our `UNIT_WORDS` set.

---

## What's safe to encode now

(committed in `unit_equivalences.json`)

| Sinhala | IAST | Grams | Source confidence |
|---|---|---:|---|
| ග්‍රෑ / ග්‍රෑම් / ග්‍රෑම්ස් | gram | 1.0 | high (metric) |
| කි.ග්‍රෑ | kilogram | 1000.0 | high (metric) |
| ලී / ලීටර් | litre | 1000.0 (water) | high (metric) |
| මි.ලී | ml | 1.0 (water) | high (metric) |
| රාත්තල් | pound | 453.592 | high (imperial) |
| තේ හැඳි | teaspoon | 5.0 | medium (conventional 5 ml) |
| මංචාඩි / මංචාඩිය | rakta-bīja | 0.125 | medium (conventional ratti, not verbatim source) |

## What needs audit before encoding

(listed in `unit_equivalences.json` → `needs_audit`)

28 classical / vernacular unit terms appear in the corpus
(`pipeline/extract_pharma_v4.py` → `UNIT_WORDS`) but their gram values
need page-by-page verification:

```
මාෂ, මාෂක, ශාණ, කර්ෂ, කර්ෂා, අඩපලං, පල, පලං, පලම්,
ප්‍රසෘත, ප්‍රසෘති, ශරාව, කුඩව, ප්‍රස්ථ, ආඪක, ද්‍රෝණ,
තුලා, සේරු, කලං, කලන්, තෝල, තෝලා, බෝතල, නැලි,
පත, භාග, බෝ, අර්ධශරාව, කෝල, කුස
```

---

## Suggested audit workflow

1. Re-render pp. 471–475 at higher zoom (`fitz.Matrix(4, 4)` ≈ 288 dpi).
2. For each unit in `needs_audit`:
   - Find the row(s) where it appears as a *result* of the equivalence
     (`= 1 <unit>`) on each of the four systems' ladders.
   - Record the verbatim row text in this audit document, in a new
     `## Per-unit transcription` section.
3. Decide which system anchors the project's canonical grams. Options:
   - Encode the pharmacopoeia's printed `ග්‍රෑ` column verbatim (uses
     the unusual 1 pala = 4 g scale).
   - Anchor at conventional Caraka (1 pala = 47.5 g) and treat the
     printed gram column as an internal annotation.
   - Anchor at colloquial Sri-Lankan tolā (1 māṣaka ≈ 1 g) since that
     is what dosage prescriptions in the formula corpus likely use.
4. Once decided, update `unit_equivalences.json`. Each entry should
   carry a `confidence: high|medium|low` and a `source_evidence`
   field pointing back to the exact source row.

---

## Why this matters for the KG

The `CONTAINS` edges in the KG carry a `quantity_grams` field. With the
authoritative gram conversions in place, ~48 % of `CONTAINS` edges
(those with non-empty `ප්‍රමාණය` values) can populate a parsed,
queryable mass. Without it, those edges only carry the raw text.

The empirical KG-grounded NER task in the MCS3306 proposal explicitly
benchmarks how downstream extraction improves with these structured
quantities. So the audit is on the critical path for the
empirical-contribution claim, not just nice-to-have polish.

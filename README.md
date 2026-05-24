# Sinhala Traditional Medicine NLP

**A knowledge-extraction pipeline and lexical-bridge resolver for the
Sri Lankan Ayurvedic Pharmacopoeia.**

This repository turns a Sinhala-language printed medical reference into a
machine-readable corpus, links its Sanskrit-derived vocabulary to existing
Sanskrit NLP resources, and is the foundation for a planned knowledge
graph of traditional Sri Lankan medicine.

---

## Table of Contents

1. [At a glance](#1-at-a-glance)
2. [Background and motivation](#2-background-and-motivation)
3. [What this repository contains](#3-what-this-repository-contains)
4. [The pharmacopoeia extraction pipeline](#4-the-pharmacopoeia-extraction-pipeline)
5. [The output: structured pharmacopoeia entries](#5-the-output-structured-pharmacopoeia-entries)
6. [The Sanskrit-bridge resolver](#6-the-sanskrit-bridge-resolver)
6½. [External-ID enrichers](#6-external-id-enrichers-interoperability-with-international-standards)
7. [The knowledge graph (planned)](#7-the-knowledge-graph-planned)
8. [Research direction](#8-research-direction)
9. [Reproducing everything](#9-reproducing-everything)
10. [Repository layout, annotated](#10-repository-layout-annotated)
11. [Glossary](#11-glossary)
12. [License and citation](#12-license-and-citation)

---

## 1. At a glance

| Question | Answer |
|---|---|
| What is the source material? | *Sri Lankan Ayurvedic Pharmacopoeia*, Volume I — 707 herbal-formula entries on pages 172–443 of the printed reference, written entirely in Sinhala. Plus a second source, *Yogamālāva* (1908), a 22-page Sinhala verse-form formulary digitised end-to-end. |
| What has been built? | Stage 0 OCR runner (Google Cloud Vision, language-pinned `si`, DPI-tuned for old prints); 3-stage OCR-to-JSON extraction pipeline; verse-aware Stage 3 for Yogamālāva; 3-tier Sinhala→Sanskrit lexical resolver with memory-isolated parser workers; external-ID enrichers binding to POWO (botany) and ICD-11 TM2 (WHO traditional medicine codes); a designed-but-not-yet-built knowledge graph documented in [`docs/kg_schema.md`](docs/kg_schema.md). |
| What's the corpus size? | Vol I: 707 structured entries · 11 007 ingredient cells · 62 562 tokens · 7 100 vocab types. Yogamālāva: 145 entries · 22 pages · 5 855 captured tokens (98.5 % of source OCR). |
| Sanskrit-bridge resolver result | **81 % / 76 % / 66 %** of tatsama-signal terms resolved against Monier-Williams in ingredients / formula names / prose, zero manual labelling. |
| POWO botanical enrichment | **69 / 85 (81 %)** binomials resolved to IPNI LSID; 19th-century MW names mapped to modern accepted forms (e.g. *Grislea Tomentosa* → *Woodfordia fruticosa*; *Physalis Flexuosa* → *Withania somnifera*). |
| ICD-11 TM2 disease mapping | **49 / 56 (88 %)** Sanskrit indication terms mapped to WHO ICD-11 Traditional Medicine Module 2 codes (released Feb 2025); 9 / 10 anchor terms validated against expected TM2 codes. |
| What's still planned? | Volumes II and III (physical copies in hand); the knowledge graph implementation; a labelled NER corpus; the empirical KG-grounded extraction study. |
| What is the formal deliverable? | A UCSC MSc-CS individual project proposal (MCS 3306) — current draft at [`Proposal/MCS3306_proposal_draft.md`](Proposal/MCS3306_proposal_draft.md); KG schema design at [`docs/kg_schema.md`](docs/kg_schema.md); bibliography at [`docs/references.md`](docs/references.md) / [`docs/references.bib`](docs/references.bib). |

For the latest measured numbers and the architectural rationale behind
the resolver, see [`docs/PROGRESS_NOTE.md`](docs/PROGRESS_NOTE.md).

---

## 2. Background and motivation

### 2.1 The source — the *Sri Lankan Ayurvedic Pharmacopoeia*

**Ayurveda** is a traditional Indian medical system, practised across
South Asia for around two millennia. Sri Lanka has its own local
Ayurvedic tradition with distinct herbs, formulations and clinical
conventions. The **Sri Lankan Ayurvedic Pharmacopoeia** is an
authoritative, state-sanctioned, multi-volume reference compiled by the
Department of Ayurveda. It catalogues hundreds of herbal formulas with
their ingredients, preparation methods, indications, dosages, and
adjuvants — and it is written **entirely in Sinhala**.

The book exists only in print. No digital, searchable or queryable form
of this knowledge has previously been published. Volume I is the focus
of this repository; Volumes II and III are in hand and are planned for
future processing with the same pipeline.

Volume I has a very specific structural property that makes it tractable
for automated extraction: it uses a **tabular column-layout** where the
horizontal position of each token on the page carries semantic meaning
(entry number on the far left, field labels next, separator in the
middle, content text on the right). The pipeline in this repository
exploits exactly this column structure.

### 2.2 The language problem — Sinhala NLP

Sinhala (`si`, Indo-Aryan family, ~17 million speakers, primarily Sri
Lanka) is one of the world's most **under-resourced languages** for
Natural Language Processing:

* No published named-entity-recognition (NER) benchmark exists for Sinhala
  (Ranasinghe et al. 2025).
* The largest available Sinhala corpora are modern web text (NSINA news,
  ~500 000 articles), unrelated to classical or medical register.
* Recent Sinhala language models (SinBERT, SinLlama, SINHALA-GLUE
  encoders) are pretrained on web Sinhala only — they have essentially
  no Ayurvedic vocabulary coverage.
* Even multilingual LLMs (Claude 3.5 Sonnet, GPT-4o) achieve only
  ~62–67 % on SinhalaMMLU and struggle most in culturally embedded
  domains (Pramodya et al. 2025).

The pharmacopoeia corpus we produce is the first publicly available
structured Sinhala Ayurvedic resource, and is therefore the *only*
domain-specific resource for any downstream NLP work on Sinhala
traditional medicine.

### 2.3 The insight — Sinhala Ayurvedic vocabulary is heavily Sanskrit-derived

A large fraction of Sinhala medical terminology consists of **Sanskrit
words written in Sinhala script**, often unchanged from the original
Sanskrit. Linguists call this category *tatsama* (literally "the same as
that"). Examples:

| Sinhala (script) | Pronunciation (IAST) | Sanskrit meaning |
|---|---|---|
| `ජ්වර` | *jvara* | fever |
| `ක්ෂය` | *kṣaya* | consumption, phthisis |
| `ශ්වාස` | *śvāsa* | breathing, asthma |
| `කුෂ්ඨ` | *kuṣṭha* | skin disease / leprosy |
| `ක්වාථය` | *kvātha* | decoction |
| `භස්ම` | *bhasma* | calcined ash |
| `ත්‍රිඵලා` | *triphalā* | the three fruits |
| `ඝෘතය` | *ghṛta* | clarified butter (ghee) |

This is enormously useful, because **Sanskrit has well-developed NLP
infrastructure** that Sinhala does not:

* The **Monier-Williams Sanskrit-English Dictionary** (1899) —
  ~160 000 headwords, the universal Sanskrit reference, available
  programmatically through the Cologne Digital Sanskrit Dictionaries.
* The **Sanskrit Heritage Engine** (Goyal & Huet 2016) — morphological
  analysis + sandhi-splitting, accessible as a CGI service and through
  the `sanskrit_parser` Python wrapper.
* The **Digital Corpus of Sanskrit** (Hellwig 2010–) — ~650 000
  morphologically tagged sentences.
* Recent neural systems including **ByT5-Sanskrit** (Nehrdich et al.
  2024) and **AyurKOSH** (Mirasdar et al. 2026) for Sanskrit medical
  terminology.
* Cross-script transliteration through **Aksharamukha** (Rajan, n.d.).

None of these resources currently accepts Sinhala script as input.
This is the gap the Sanskrit-bridge resolver fills.

### 2.4 The research goal

> Given an under-resourced Sinhala domain corpus and a well-resourced
> Sanskrit lexical ecosystem that shares much of its vocabulary, can we
> (a) construct a reliable cross-lingual lexical bridge between the two,
> (b) use the bridge to seed a domain knowledge graph for Sinhala
> traditional medicine, and (c) demonstrate measurable utility of that
> knowledge graph for downstream information extraction on Sinhala
> Ayurvedic text?

Steps (a) and a botanical-Latin starter list for the future KG already
exist in this repository. Steps (b) and (c) are the substance of the
MCS 3306 MSc proposal in [`Proposal/`](Proposal).

---

## 3. What this repository contains

Four independent components, layered on each other:

```
┌──────────────────────────────────────────────────────────────────────┐
│  (1) Pipeline   —  scanned PDF  →  structured JSON corpus             │
│      pipeline/, data/{ocr,rows,structured}/, analysis/                │
│                                                                       │
│  (2) Resolvers  —  Sinhala tokens  →  Sanskrit lexical entries        │
│      resolvers/, data/lexicons/                                       │
│                                                                       │
│  (2b) Enrichers —  resolved entities  →  external authority IDs       │
│       enrichers/ — POWO (plants), ICD-11 TM2 (diseases)               │
│                                                                       │
│  (3) Knowledge graph  —  structured + resolved + bound  →  typed graph │
│      docs/kg_schema.md (v1 design), knowledge_graph/ (not yet built)  │
└──────────────────────────────────────────────────────────────────────┘
```

Plus supporting material: `docs/` (KG schema, architecture notes,
data-quality catalogue, the latest progress note, bibliography),
`pdf_pipeline/` (an experimental alternative extraction path that reads
embedded PDF text directly), and `Proposal/` (the academic deliverable).

---

## 4. The pharmacopoeia extraction pipeline

### 4.1 Overview

The pipeline turns the printed pharmacopoeia into structured JSON in
three stages. Each stage is a single Python file with no external
dependencies — pure standard-library.

```
data/source/<source>.pdf
   │
   ▼  pipeline/ocr_gcv.py
       (Stage 0 — Google Cloud Vision sync, per-page rendering at
        configurable DPI, DOCUMENT_TEXT_DETECTION + languageHints=["si"],
        optional upscale safety net for low-confidence pages)
data/ocr/<source>/ocr_results_output-NNN-to-MMM.json
   │     │
   │     │  Tree: pages → blocks → paragraphs → words → symbols
   │     │  with normalized bounding-box polygons (0–1 coords).
   │     │
   │     ▼  pipeline/extract_page.py
per-page extracted JSON (a slice of the OCR tree for one page)
   │
   ▼  pipeline/shrink_ocr_v4.py
data/rows/<source>/<batch>_rows.json — flattened to one row per "visual
                                       line", with each token as
                                       (x, block_id, para_id, text)
   │
   ▼  pipeline/extract_pharma_v4.py    (tabular column layouts only)
data/structured/<batch>_structured.json — one record per formula entry,
                                          with Sinhala field names
```

`pipeline/pipeline.py` orchestrates Stages 1–3 for the Vol I batches
end-to-end. Stage 0 (`ocr_gcv.py`) is invoked separately when a new
source PDF needs OCR (e.g. `yogamalawa.pdf` → `data/ocr/yogamalawa/`).

### 4.2 Stage 1 — per-page OCR extraction (`pipeline/extract_page.py`)

GCV outputs one JSON per batch (50-page chunk), each ~7–10 MB. Stage 1
slices a single page out of that batch while preserving the full
`fullTextAnnotation` tree (pages → blocks → paragraphs → words →
symbols), with bounding-box polygons in pixel coordinates.

```bash
# Inspect a single page
python pipeline/extract_page.py data/ocr/ocr_results_output-151-to-200.json 172

# List available pages in a batch
python pipeline/extract_page.py data/ocr/ocr_results_output-151-to-200.json --list
```

### 4.3 Stage 2 — row clustering (`pipeline/shrink_ocr_v4.py`)

Raw GCV output is a tree with absolute pixel coordinates. Stage 2
flattens it into **visual rows** — lines of text as they appear on the
printed page — using bounding-box geometry rather than the GCV
paragraph segmentation, which is unreliable on multi-column layouts.

**Algorithm:**

1. Walk the GCV tree; collect every word with its bounding box.
2. Normalise box coordinates to `(x, y) ∈ [0, 1]` relative to page size.
3. Cluster words whose vertical y-span is ≤ **0.012** into a single row.
4. Sort each row left-to-right by x.
5. Drop tokens that look like running page numbers: y > **0.88**,
   x ∈ [0.35, 0.65], numeric content only.

**Output format**, one row per object:

```json
{
  "y": 0.342,
  "w": [
    [0.12, "block_3", "para_1", "කලාඳුරු"],
    [0.18, "block_3", "para_1", "අල"]
  ]
}
```

Each `w` entry is `[x, block_id, paragraph_id, text]`.

The thresholds (`0.012` y-spread, `0.88` page-number band) were tuned
empirically on Vol I and are documented in
[`docs/architecture.md`](docs/architecture.md).

### 4.4 Stage 3 — structured-entry extraction (`pipeline/extract_pharma_v4.py`)

The pharmacopoeia layout assigns semantic roles to horizontal column
zones. Stage 3 is a **state machine** driven by token x-position and by
recognised Sinhala field labels.

**Column zones (normalised x):**

| x range | Role | Example |
|---|---|---|
| x < 0.15 | Entry number | `"44."` |
| 0.15 ≤ x < 0.25 | Field label | `"යෝගය"` ("ingredients") |
| 0.25 ≤ x < 0.32 | Separator artefact | `":"`, `"-"` |
| x ≥ 0.32 | Content | ingredient names, prose, quantities |

**State sequence:**

```
ENTRY_HEADER → YOGAYA → SANSKARANAYA → PRAYOGA → ANUPANA → MATRAVA
```

Each state collects tokens from the content column. Transitions are
triggered by recognised Sinhala field labels matched against a
hand-built `LABEL_TO_STATE` table:

| Sinhala label | Transliteration | Triggers state |
|---|---|---|
| `යෝගය` | yogaya | YOGAYA (ingredients) |
| `සංස්කරණය` | sanskaranaya | SANSKARANAYA (preparation) |
| `ප්‍රයෝග` | prayoga | PRAYOGA (usage/indication) |
| `අනුපාන` | anupāna | ANUPANA (adjuvant/vehicle) |
| `මාත්‍රාව` | mātrā | MATRAVA (dosage) |
| `සටහන` | saṭahana | NOTES |

Cross-page entry continuation is handled by carrying an incomplete
"partial tail" entry into the next batch and merging it with the first
entry of that batch.

`extract_pharma_v3.py` is the stable predecessor; `v4` is the current
production version.

### 4.5 The pipeline runner (`pipeline/pipeline.py`)

Hard-codes the seven GCV batch files covering pages 151–500 of the
source PDF and runs all three stages for a requested page range.

```bash
# Default range (pages 444–453)
python pipeline/pipeline.py

# A specific range
python pipeline/pipeline.py --start 151 --end 200

# Force overwrite of existing outputs
python pipeline/pipeline.py --force

# Preview only — do not write
python pipeline/pipeline.py --dry-run
```

The batch registry is also documented in
[`docs/architecture.md`](docs/architecture.md).

---

## 5. The output — structured pharmacopoeia entries

### 5.1 Schema

Each entry in `data/structured/*_structured.json` is an object whose
**field keys are Sinhala strings**. The wrapper around the entry list
also carries a `partial_tail` for cross-batch entry continuation.

```json
{
  "batch": "151-to-200",
  "entries": [
    {
      "අංකය": 44,
      "යෝග නාමය": "ත්‍රිකටු චූර්ණය",
      "යෝගය": [
        {"ද්‍රව්‍යය": "තිප්පිලි", "ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0},
        {"ද්‍රව්‍යය": "ඉඟුරු",   "ප්‍රමාණය": "", "ග්‍රෑ": 0.0, "ලී": 0.0}
      ],
      "සංස්කරණය": "සමව ගෙන කොටා ...",
      "ප්‍රයෝග":   "කාස, ශ්වාස ...",
      "අනුපාන":   "මී පැණි",
      "මාත්‍රාව":  "ග්‍රෑ 5",
      "සටහන":     "",
      "source_page": 172
    }
  ],
  "partial_tail": {}
}
```

### 5.2 Field reference

| Sinhala key | Transliteration | English | Type | Fill rate (Vol I) |
|---|---|---|---|---:|
| `අංකය` | ankaya | Entry number | int | 100 % |
| `යෝග නාමය` | yoga nāmaya | Formula name | str | 99 % |
| `යෝගය` | yogaya | Ingredient list | array of object | 98 % |
| `සංස්කරණය` | sanskaranaya | Preparation method | str | 63 % |
| `ප්‍රයෝග` | prayoga | Usage / indication | str | 97 % |
| `අනුපාන` | anupāna | Adjuvant / vehicle | str | 51 % |
| `මාත්‍රාව` | mātrā | Dosage | str | 48 % |
| `සටහන` | saṭahana | Notes | str | 36 % |
| `source_page` | — | Source page in PDF | int | 100 % |

Each ingredient sub-object inside `යෝගය`:

| Sub-key | Meaning | Type |
|---|---|---|
| `ද්‍රව්‍යය` | ingredient name (raw OCR text) | str |
| `ප්‍රමාණය` | quantity as written | str |
| `ග්‍රෑ` | parsed grams | float (0.0 if absent) |
| `ලී` | parsed litres | float (0.0 if absent) |

A full schema reference is in
[`docs/output_schema.md`](docs/output_schema.md).

### 5.3 Fill rates — what they don't mean

Low fill rates are **not** evidence that the OCR failed to capture the
information. The pharmacopoeia frequently uses **cross-references** —
e.g. the `සංස්කරණය` (preparation) field of a decoction formula often
just says *"prepare per the standard decoction method"* without
restating the method inline. Likewise dosage is often elided for
formulas where titration is implied. The fill rate reflects what is
*present in the source*, not the OCR's reliability.

### 5.4 Known data-quality issues

The pipeline produces clean structure on top of imperfect OCR.
Catalogued in [`docs/pipeline_notes.txt`](docs/pipeline_notes.txt); the
main issues:

* **Artefact tokens.** ~17 % of ingredient `ද්‍රව්‍යය` tokens are
  structural OCR junk — punctuation, parenthesis leaks from a quantity
  column that was collapsed into the ingredient column, etc.
  Specifically, the single most frequent "ingredient" token is `(` (242
  occurrences), more common than *tippili* (long pepper, 192) which is
  the most pharmacologically ubiquitous real ingredient.
* **Unicode normalisation.** ~24 % of formula names fail NFC/NFD
  equivalence. The ZWJ (U+200D) character appears inside several field
  *keys* themselves (`ප්‍රයෝග`, `මාත්‍රාව`) — a string comparison that
  does not pre-normalise will silently fail to access those fields.
* **Field-boundary leaks.** Preparation prose sometimes appears inside
  the ingredient list (the column parser misallocated rows). The
  resolver's "other" bucket and the artefact filter catch most but not
  all.
* **Three incompatible dosage unit systems** coexist (modern metric,
  traditional seed-weight, mixed) with no type flag in the data. ~40
  entries use both systems in the same string.

These issues are stated upfront so that downstream consumers can plan
their cleanup.

---

## 6. The Sanskrit-bridge resolver

### 6.1 The linguistic insight — tatsama vs. tadbhava vs. vernacular

Sinhala Ayurvedic vocabulary divides into three categories with
fundamentally different resolution strategies:

1. **Tatsama** ("the same as that"): Sanskrit word borrowed unchanged
   into Sinhala script. Carries Sanskrit orthographic signals —
   aspirated consonants (ඛ ඝ ඡ ඣ ඨ ඪ ථ ධ ඵ භ), sibilants (ශ ෂ),
   palatal nasal (ඥ), vocalic-r (ඍ ෘ ඎ ෲ), or word-initial consonant
   clusters (which native Sinhala phonotactics do not produce). These
   are the *resolvable* category — transliterate to IAST and look up in
   Monier-Williams.
2. **Tadbhava** ("come from that"): Sanskrit-origin term phonologically
   transformed by centuries of Sinhala sound change until the surface
   form no longer resembles the Sanskrit source. The classic example
   is **ඉඟුරු** *iňguru* (ginger), descended from Sanskrit
   *śṛṅgavera*. There is no surface signal — these can only be
   resolved via an etymological lexicon, which is not yet built.
3. **Vernacular / *deśya*** ("of the country"): genuinely Sinhala or
   non-Sanskrit-borrowed (Tamil, Portuguese, Dutch, English). Example:
   **එන්සාල්** *ensāl* (cardamom). Has no Sanskrit equivalent at all.

The resolver in this repository targets category (1) and explicitly
routes (2) and (3) to an unresolved bucket pending future work.

### 6.2 The three-tier architecture

```
Sinhala token ─► Module A: classify ─► tatsama? ─► YES ─► Tier 1 (direct MW lookup)
                                              │                  │ miss
                                              │                  ▼
                                              │            Tier 2 (dict-driven samāsa)
                                              │                  │ miss
                                              │                  ▼
                                              │            Tier 3 (sanskrit_parser
                                              │                    in isolated worker)
                                              │                  │ miss
                                              │                  ▼
                                              ▼                unresolved
                                       "other" bucket
                                  (tadbhava + vernacular)
```

#### Module A — category router (offline, no dependencies)

For each Sinhala token, classify as `tatsama` or `other` based on the
"Mishra Sinhala" signal:

* Contains any character from
  `{ඛ ඝ ඡ ඣ ඨ ඪ ථ ධ ඵ භ ශ ෂ ඥ ඍ ඎ ෘ ෲ ඃ}` — aspirated consonants,
  sibilants, palatal nasal, vocalic-r, visarga. Native Sinhala
  vocabulary almost never uses these.
* OR has a word-initial consonant cluster `[ක-ෆ] + virama [ + ZWJ ] +
  [ක-ෆ]`. Native Sinhala has no word-initial clusters.

Native geminates and clusters (තිප්ප–, ගම්ම–, ල්ම–) are correctly
**not** flagged, because they don't contain Sanskritic letters and they
aren't word-initial.

About **27 %** of unique types in the Vol I corpus carry the tatsama
signal.

#### Tier 1 — direct Monier-Williams lookup

For each tatsama token:

1. Convert Sinhala script → IAST with **Aksharamukha**:
   *ශ්වාස* → *śvāsa*.
2. Look up in **Monier-Williams** via `pycdsl`:
   *śvāsa* → *"hissing, panting; asthma"*.
3. If miss, try suffix-stripped variants of the IAST form
   (`-ya`, `-aya`, `-yā`, `-va`, `-ṁ`, `-ḥ`) — Sinhala nominal endings
   that don't exist in the Sanskrit stem form.
   Example: *kvāthaya* (ක්වාථය, "decoction-NOM") → strip `-ya` →
   *kvātha* → MW hit.

#### Tier 2 — dictionary-driven samāsa segmenter

Sanskrit forms long **compound nouns** (*samāsa*) by simple
concatenation: *karkaṭaka* + *śṛṅgī* → *karkaṭakaśṛṅgī* (the herb
*Pistacia integerrima*). Monier-Williams does not always list the
compound, but lists the parts. Tier 2 splits the IAST string at every
position, accepting a segmentation in which every piece is itself a
Monier-Williams headword.

* Each segment must be ≥ 3 characters (excludes spurious matches on
  short words like *ka*, *a*).
* Up to 3 segments per word.
* Recursive: a remainder can itself be split further.

This tier uses *only* dictionary lookups — no parser, no graph search,
no measurable memory cost.

#### Tier 3 — `sanskrit_parser` via memory-isolated worker

Some compounds undergo **vowel-junction sandhi** at the boundary —
e.g. *deva* + *indra* → *devendra* (the boundary *a + i* merges to
*e*). Tier 2 cannot reverse such junctions because they don't appear
as character-level concatenation. The Sanskrit Heritage Engine (via
the `sanskrit_parser` Python wrapper) is the right tool — but it has a
significant pathology: each call retains 5–55 MB that is never
released, and on a corpus-scale run this accumulates into gigabytes
and crashes the process with OOM.

The mitigation is process-level isolation. `resolvers/sandhi_worker.py`
is a disposable subprocess that:

1. Sets `RLIMIT_AS` to a configurable cap (default 1.5 GB) **before**
   importing `sanskrit_parser`, so even a runaway allocation raises
   `MemoryError` rather than triggering the OOM-killer.
2. Sets a `SIGALRM` timeout of 8 s per word.
3. Reads IAST words from stdin, emits line-delimited JSON to stdout,
   exits when stdin closes.

`sanskrit_resolver.py --with-parser` orchestrates these workers,
processing the residual unresolved set in batches of 50 words per
worker. Output is **append-only and resumable** (`parser_recoveries.jsonl`)
so a worker crash never loses prior work. On the latest measured run,
**21 workers ran clean with zero OOM kills**, peak RAM under 1.65 GB.

### 6.3 Measured results

Resolution rates on the full Vol I corpus, by field and by tier:

| Field | Total tatsama types | Direct (T1) | + dict-sandhi (T2) | + parser (T3) | **Total** |
|---|---:|---:|---:|---:|---:|
| Ingredients | 948 | 689 | +61 | +14 | **81 %** |
| Formula names | 325 | 97 | +98 | +51 | **76 %** |
| Prose | 1 231 | 528 | +238 | +51 | **66 %** |

Word-records resolved overall: **1 286 direct + 509 dict-sandhi + 137
parser-sandhi = 1 932** across the three lexicons.

Names benefit the most from Tier 3 (+16 pp) because formula names are
heavily compound (*ක්වාථය*, *චූර්ණය*, *ඝෘතය*, *ද්‍රාක්ෂාදි*) and many of
those compounds involve sandhi.

### 6.4 The botanical-Latin seed

Monier-Williams glosses for medicinal plants frequently embed **Latin
binomials** of the form *Genus species*. Extracting these from the
resolved glosses yields a starter list for a future botanical
normaliser — **120 ingredients → 85 distinct candidate Latin binomials**,
ranked by corpus frequency:

| Binomial (Monier-Williams) | Modern accepted name | Sinhala source | Freq |
|---|---|---|---:|
| *Grislea tomentosa* | *Woodfordia fruticosa* | ධාතකී | 42 |
| *Cerasus puddum* | *Prunus cerasoides* | පද්මකාෂ්ඨ | 24 |
| *Terminalia chebula* | (unchanged) | *haritakī* references | 23 |
| *Phyllanthus emblica* | *Phyllanthus emblica* | *āmalakī* refs | 19 |
| *Nelumbium speciosum* | *Nelumbo nucifera* | lotus refs | 11 |
| *Physalis flexuosa* | *Withania somnifera* | *aśvagandhā* | 9 |
| *Hedysarum gangeticum* | *Desmodium gangeticum* | *śālaparṇī* | 7 |
| *Amyris agallochum* | *Aquilaria malaccensis* | *agaru* | 6 |
| *Evolvulus alsinoides* | (unchanged) | *śaṅkhapuṣpī* | 5 |

(Modern accepted names from Plants of the World Online; Monier-Williams
uses 19th-century botanical names that often require taxonomic-synonym
resolution.)

A small number of false positives appear (*Columba hurriyala* = pigeon
genus, *Coluber naga* = snake — both from MW glosses where the herb's
name happened to also be applied to an animal). These must be filtered
by a botanist's curation pass before the list is used as a normaliser
input.

Full data is in
[`data/lexicons/botanical_candidates.json`](data/lexicons/botanical_candidates.json).

### 6.5 Output formats produced by the resolver

In [`data/lexicons/`](data/lexicons/):

* `ingredients_lexicon.json`, `names_lexicon.json`, `prose_lexicon.json`
  — one object per Sinhala term. Each contains the original frequency,
  a `resolved` flag, and the per-word resolution records:

  ```json
  {
    "ශෝධිත ගන්ධක": {
      "freq": 52,
      "resolved": true,
      "words": [
        {"word": "ශෝධිත", "iast": "śodhita", "lemma": "śodhita",
         "gloss": "śodhita mfn. (fr. id.) cleansed, purified",
         "method": "direct"},
        {"word": "ගන්ධක", "iast": "gandhaka", "lemma": "gandhaka",
         "gloss": "gandhaka mf(ikā)n. ifc. ‘having the smell of’ …",
         "method": "direct"}
      ]
    }
  }
  ```

  Possible `method` values: `direct`, `sandhi` (Tier 2),
  `sandhi-parser` (Tier 3), or `null` (unresolved).

* `botanical_candidates.json` — terms whose gloss contained a
  Latin-binomial pattern.

* `parser_recoveries.jsonl` — append-only, one JSON record per word
  processed by Tier 3 workers, including failures
  (`status: timeout | oom | error`). Resumable.

### 6.6 Known limits

* **Sinhala-IAST diacritics** (`ĕ`, `ŏ`, `æ`, `ḻ`, `n̆`) emitted by
  Aksharamukha for Sinhala-native sounds are not consumable by
  `sanskrit_parser`. Approximately 55 % of Tier-3 worker errors are
  these tokens; they aren't really tatsama and should be routed back
  to the "other" bucket by a Module-A refinement (a roughly 10-line
  change, deferred).
* **Tadbhava** (Sanskrit-origin phonologically nativised) terms cannot
  be resolved — no surface signal, no lexicon yet.
* **OCR / spelling variants** of the same Sanskrit term (e.g.
  *ශයී / ශඨි / ශටී* for *śaṭhī*, zedoary) are treated as distinct
  terms. A fuzzy pass over MW headwords would collapse these.

---

## 6½. External-ID enrichers (interoperability with international standards)

The Sanskrit-bridge resolver produces canonical IAST lemmas. The
**enrichers** in [`enrichers/`](enrichers) take those lemmas and bind
them to globally-recognised identifiers, making the KG interoperate
with established botanical, pharmacological and clinical authorities.

| Enricher | Authority | Coverage |
|---|---|---:|
| [`botanical_powo.py`](enrichers/botanical_powo.py) | Plants of the World Online (Royal Botanic Gardens, Kew) — provides the IPNI LSID for each plant; resolves Monier-Williams 19th-century names to modern accepted forms (e.g. *Grislea Tomentosa* → *Woodfordia fruticosa*; *Physalis Flexuosa* → *Withania somnifera*). | **69 / 85 (81 %)** |
| [`icd11_tm2_mapper.py`](enrichers/icd11_tm2_mapper.py) | WHO ICD-11 Traditional Medicine Module 2 (released February 2025; 529 codes specifically for Ayurveda/Siddha/Unani). Matches via the `indexTerm` field where TM2 stores the Sanskrit equivalents in the `(a) <Ayurveda> (b) <Siddha> (c) <Unani>` convention. | **49 / 56 (88 %)**, 9/10 anchor terms correct |

The schema design that motivates both is in
[`docs/kg_schema.md`](docs/kg_schema.md) — POWO LSIDs are a required
external ID on every `Plant` node; ICD-11 TM2 codes are required on
every `Disease` node. Setup, run instructions, and the matching
algorithm are documented in [`enrichers/README.md`](enrichers/README.md).

---

## 7. The knowledge graph (planned)

The structured corpus, the resolved lexicons, and the external-ID
bindings together support the construction of a domain knowledge graph
— the planned next phase of the work.

The **v1 schema** is fully designed in
[`docs/kg_schema.md`](docs/kg_schema.md) (≈ 500 lines, supervisor-facing).
It defines:

* **10 node types**: Plant, PlantPart, Phytochemical, Mineral,
  Formulation, PreparationType, Route, Disease, Symptom,
  PharmacologicalProperty.
* **13 edge types**: `CONTAINS`, `USES_PART`, `CONSISTS_OF`, `IS_TYPE`,
  `PREPARED_BY`, `ADMINISTERED_AS`, `DOSED_WITH`, `TREATS`,
  `HAS_SYMPTOM`, `RELIEVES`, `HAS_PROPERTY`, `SUBSTITUTES_FOR`,
  `VARIANT_OF`, `CITES`.
* **Required external-authority IDs**: POWO IPNI LSID on every Plant,
  ICD-11 TM2 code on every Disease, PubChem CID / ChEBI ID on every
  Phytochemical. Synthesised from comparable initiatives — GRAYU
  (Frontiers Pharmacology 2026), HerbKG, AyurKOSH (IEEE DataPort 2026),
  and the WHO ICD-11 TM2 international standard (released Feb 2025).
* **Provenance per node and per edge**: `source_doc`,
  `source_sentence_id`, `extractor_version`, `resolver_version`,
  `confidence`, `created_at`.
* **Four serialisation views**: Neo4j (canonical), JSON-LD (publish),
  RDF/Turtle (semantic-web), JSONL (streaming).
* **Schema-constrained extraction** as the explicit design principle —
  matching the 2025 best practice (RELATE, SPIREX, ODKE+,
  schema-constrained AI for biomedical evidence).

A companion [`docs/context.jsonld`](docs/context.jsonld) defines the
JSON-LD context so worked examples parse against the schema.

What's ready vs. pending:

| Edge type | Source | Status |
|---|---|---|
| FORMULA `CONTAINS` Ingredient | `යෝගය` | Yes — 11 007 instances ready |
| FORMULA `IS_TYPE` FormulaType | name suffix | Yes — regex |
| FORMULA `DOSED_WITH` Adjuvant | `අනුපාන` | Yes |
| Ingredient `CO_OCCURS` Ingredient | co-occurrence | Yes |
| FORMULA `TREATS` Disease (with ICD-11 TM2 code) | `ප්‍රයෝග` + the ICD-11 mapper | Mapping built (88 % coverage); KG builder not yet written |
| Plant **external.powo_lsid** | POWO enricher | Built (81 % coverage) |
| FORMULA `REFERENCES` Formula | `සංස්කරණය` | Needs regex |
| Plant `VARIANT_OF` canonical | normalisation | Needs labelling |

The KG **builder** module (`knowledge_graph/build.py`) is the next
implementation step.

---

## 8. Research direction

This repository underpins a planned MSc in CS individual project
(UCSC MCS 3306). The current draft proposal is in
[`Proposal/MCS3306_proposal_draft.md`](Proposal/MCS3306_proposal_draft.md)
and articulates four contributions:

1. **Methodological** — the memory-isolated subprocess pattern for
   bounding memory-pathological NLP libraries (the Tier-3 architecture
   described above), generally reusable.
2. **Resource** — the first machine-readable cross-lingual bridge
   between Sinhala script and Sanskrit lexical resources.
3. **Knowledge representation** — the first knowledge graph of
   traditional Sri Lankan medicine.
4. **Empirical** — a controlled measurement of whether KG-grounded
   features improve named-entity recognition on Sinhala Ayurvedic text,
   with a clean ablation (gazetteer baseline / feature-rich CRF /
   KG-augmented CRF).

For supervisor-facing background, see
[`docs/PROGRESS_NOTE.md`](docs/PROGRESS_NOTE.md).

---

## 9. Reproducing everything

### 9.1 Prerequisites

* **Python ≥ 3.10**, preferably 3.10–3.13.
  Python 3.12 removed `ast.Str`, which `aksharamukha` imports; the
  resolver script ships a one-line `ast.Str = str` shim so this is
  handled, but the warning is good to know.
* **Git LFS** (only if you need the OCR JSONs): the source PDF and the
  10 GCV batch JSONs are LFS-tracked. The structured JSONs and the
  resolver outputs are **not** LFS-tracked.
* About **5 GB free RAM** for the resolver Tier 3 (workers are capped
  at 1.5 GB; one is live at a time).
* About **100 MB** of free disk for the Monier-Williams data download.

### 9.2 Clone and set up

```bash
git clone git@github.com:nuwan-labs/sinhala-traditional-medicine-nlp.git
cd sinhala-traditional-medicine-nlp

# Optional: pull the LFS-tracked source PDF + GCV batches
git lfs install
git lfs pull
```

The extraction pipeline (`pipeline/`, `analysis/`) needs no Python
packages beyond the standard library. The resolver (`resolvers/`) does:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install aksharamukha pycdsl sanskrit_parser \
                                indic-transliteration
```

### 9.3 Running the extraction pipeline

```bash
# Run the whole structured-extraction pipeline for pages 151–200
python pipeline/pipeline.py --start 151 --end 200

# Extract one page and inspect its OCR tree
python pipeline/extract_page.py data/ocr/ocr_results_output-151-to-200.json 172

# Compress a single page's OCR to row format
python pipeline/shrink_ocr_v4.py data/rows/151-to-200_rows.json

# Generate the NLP statistics report
python analysis/nlp_stats.py
```

### 9.4 Running the Sanskrit-bridge resolver

The resolver expects the structured JSONs (`*_structured.json`) in the
current working directory. Run from `data/structured/`:

```bash
cd data/structured

# Tier 1+2 only — fast, memory-trivial (~30 s)
../../.venv/bin/python ../../resolvers/sanskrit_resolver.py --field all

# Full Tier 1+2+3 — adds memory-isolated parser workers (~3 minutes)
../../.venv/bin/python ../../resolvers/sanskrit_resolver.py \
    --field all --with-parser \
    --parser-batch 50 \
    --parser-mem-cap 1500
```

On first run, `pycdsl` downloads Monier-Williams into `--cdsl-dir`
(default `.cdsl_data/`, ~50 MB).

Outputs in the working directory:

```
ingredients_lexicon.json     names_lexicon.json
prose_lexicon.json           botanical_candidates.json
parser_recoveries.jsonl      resolver_run.log
```

A frozen reference copy of these outputs is committed at
[`data/lexicons/`](data/lexicons).

### 9.5 Running the external-ID enrichers

Both enrichers need a couple of extra packages:

```bash
.venv/bin/python -m pip install requests rapidfuzz
```

**Plants → POWO** (Royal Botanic Gardens, Kew; no auth needed):

```bash
.venv/bin/python enrichers/botanical_powo.py
# ~25 s for the 85 binomials, hits POWO /api/2/search.
# Writes data/lexicons/botanical_powo.json
```

**Diseases → ICD-11 TM2** (WHO API; one-time free registration at
[icd.who.int/icdapi](https://icd.who.int/icdapi) to obtain a
client_id + client_secret):

```bash
# put credentials in a gitignored .env file at the repo root
cat > .env << 'EOF'
ICD_CLIENT_ID=<your-client-id>
ICD_CLIENT_SECRET=<your-client-secret>
EOF

.venv/bin/python enrichers/icd11_tm2_mapper.py
# first run crawls + caches all 710 TM2 entities (~30 s);
# subsequent runs are offline. Writes data/lexicons/icd11_tm2_cache.json
# and data/lexicons/indication_icd11_tm2.json.
.venv/bin/python enrichers/icd11_tm2_mapper.py --anchors-only   # 10-term smoke test
.venv/bin/python enrichers/icd11_tm2_mapper.py --refresh        # force re-crawl
```

Setup details, the 5-tier matching algorithm, and known limits are
documented in [`enrichers/README.md`](enrichers/README.md).

### 9.6 Memory profile

For reference (Python interpreter on Linux, 8 GB RAM machine):

```
python interp                 13.6 MiB
+ aksharamukha               +27 MiB
+ pycdsl + MW open + 1 query +28 MiB
+ sanskrit_parser import     +33 MiB     (background; not loaded in
+ Parser() constructed       +39 MiB      main process, only in workers)
single Parser.split() call   +5 to +55 MiB, never released
```

The worker process recycling design (50 words per worker, then exit)
bounds the cumulative leak; the main process stays around 150 MiB.

---

## 10. Repository layout, annotated

```
sinhala-traditional-medicine-nlp/
├── README.md                       ← this file
├── RESEARCH_PROPOSAL.md            ← public-facing project overview (older)
├── Proposal/
│   └── MCS3306_proposal_draft.md   ← UCSC MSc-CS proposal draft (current)
│
├── pipeline/                       ── (1) Pipeline: PDF → structured JSON
│   ├── ocr_gcv.py                  — Stage 0: GCV OCR runner (sync, per-page,
│   │                                 DOCUMENT_TEXT_DETECTION, language=si)
│   ├── extract_page.py             — Stage 1: slice OCR batch by page
│   ├── shrink_ocr_v4.py            — Stage 2: cluster words into rows
│   ├── extract_pharma_v3.py        — Stage 3 (stable, tabular layout)
│   ├── extract_pharma_v4.py        — Stage 3 (current development)
│   ├── extract_yogamalawa_v1.py    — Stage 3 (verse-form, baseline)
│   ├── extract_yogamalawa_v2.py    — Stage 3 (verse-form, v2.1 with embedded
│   │                                 marker split + indication mop-up)
│   └── pipeline.py                 — orchestrator (Stages 1–3, Vol I)
│
├── resolvers/                      ── (2) Resolvers: Sinhala → Sanskrit
│   ├── sanskrit_resolver.py        — Module A router + Tier 1 + 2 + driver
│   ├── sandhi_worker.py            — Tier 3 disposable subprocess
│   └── README.md                   — setup + measured rates
│
├── enrichers/                      ── (2b) Bind resolved entities to external IDs
│   ├── botanical_powo.py           — Plant → POWO IPNI LSID + modern accepted name
│   ├── icd11_tm2_mapper.py         — Sanskrit indication → ICD-11 TM2 code
│   └── README.md                   — setup + measured rates
│
├── knowledge_graph/                ── (3) KG construction (planned)
│   └── README.md                   — see docs/kg_schema.md for the v1 contract
│
├── analysis/
│   └── nlp_stats.py                — corpus statistics report
│
├── pdf_pipeline/                   ── experimental: direct PDF text
│   ├── extract_pdf.py              — PyMuPDF-based extraction
│   ├── build_glyph_table.py
│   └── glyph_corrections.json      — IskoolaPota ToUnicode fixes
│
├── data/
│   ├── source/                     — original PDFs (Vol I is Git-LFS-tracked)
│   ├── ocr/                        — Stage-0 GCV outputs
│   │   ├── ocr_results_output-*.json   — Vol I, Git LFS (async batch)
│   │   └── yogamalawa/             — Yogamālāva 1908 (sync per-page)
│   ├── rows/                       — Stage-2 row-level JSON
│   │   └── yogamalawa/             — verse-form rows (379 rows, 22 pages)
│   ├── structured/                 — Stage-3 structured entries
│   │   ├── *_structured.json       — Vol I batches (tabular)
│   │   └── yogamalawa/             — Yogamālāva v2.1 (145 entries, 98.5 %
│   │       │                         per-token coverage)
│   │       ├── yogamalawa_structured_v2.json
│   │       ├── coverage_report_v2.json
│   │       └── yogamalawa_reading.txt  — supervisor-friendly plain-text view
│   └── lexicons/                   — Resolver + enricher outputs
│       ├── {ingredients,names,prose}_lexicon.json  — resolver Tier 1+2+3
│       ├── botanical_candidates.json               — Latin binomial seed
│       ├── botanical_powo.json                     — POWO enrichment
│       ├── icd11_tm2_cache.json                    — TM2 entity cache (710)
│       └── indication_icd11_tm2.json               — Sanskrit → TM2 mapping
│
└── docs/
    ├── architecture.md             — pipeline design and threshold rationale
    ├── output_schema.md            — full structured-entry field reference
    ├── pipeline_notes.txt          — data-quality catalogue
    ├── PROGRESS_NOTE.md            — latest preliminary-work writeup
    ├── kg_schema.md                — v1 KG schema (10 nodes, 13 edges, ICD-11 TM2 + POWO + ChEBI bindings)
    ├── context.jsonld              — JSON-LD context for the schema
    ├── references.md               — bibliography (annotated)
    └── references.bib              — bibliography (BibTeX)
```

---

## 11. Glossary

Domain and technical terms used throughout this document.

| Term | Meaning |
|---|---|
| **Ayurveda** | Traditional Indian medical system, ~2 000 years old, based on the *tridoṣa* theory (three humours: *vāta*, *pitta*, *kapha*) and an extensive herbal pharmacopoeia. |
| **Pharmacopoeia** | An authoritative reference book listing therapeutic substances with their preparation, dosage, and clinical uses. |
| **Sinhala** | Indo-Aryan language, official language of Sri Lanka, written in its own Brahmic script. ISO 639-1 code `si`. |
| **GCV** | Google Cloud Vision OCR service. Used to scan the printed PDF into a JSON tree of pages → blocks → paragraphs → words → symbols, each with bounding-box coordinates. |
| **NFC / NFD** | Unicode normalisation forms. NFC is canonical-composed (single code points for accented characters where possible); NFD is canonical-decomposed (base + combining marks). Strings should be NFC-normalised before any equality test or tokenisation. |
| **ZWJ** | Zero-Width Joiner (U+200D). Used in Sinhala script to control ligature behaviour. Two strings that look identical can differ by the presence of a ZWJ. |
| **Tatsama** | A Sanskrit word borrowed unchanged into another language (here, Sinhala) — only the script changes. |
| **Tadbhava** | A Sanskrit-origin word phonologically transformed by the receiving language's sound changes. |
| **Deśya / Vernacular** | A word with no Sanskrit origin — local or non-Sanskrit-borrowed. |
| **IAST** | International Alphabet of Sanskrit Transliteration — the standard Romanisation for Sanskrit using Latin letters with diacritics. |
| **Devanagari** | The Brahmic script most commonly associated with Sanskrit and Hindi. |
| **Monier-Williams (MW)** | *A Sanskrit-English Dictionary*, M. Monier-Williams, Oxford 1899. ~160 000 entries, the universal Sanskrit reference. Accessed in this project through the Cologne Digital Sanskrit Dictionaries (CDSL) via the `pycdsl` Python library. |
| **Aksharamukha** | An open-source transliteration tool for Indian scripts and Romanisation schemes, by Vinodh Rajan. We use the Python package. |
| **Sanskrit Heritage Engine** | Sanskrit morphological analyser and sandhi-splitter, originally by Gérard Huet at INRIA. Accessed via the `sanskrit_parser` Python wrapper. |
| **Sandhi** | Phonological junction between two morphemes or words in Sanskrit (and in classical Sinhala). May involve vowel coalescence, consonant assimilation, or visarga changes. |
| **Samāsa** | Compound noun in Sanskrit, formed by concatenating two or more stems (sometimes with sandhi at the boundary). |
| **NER** | Named Entity Recognition — a sequence-labelling task that identifies and types spans like person, location, ingredient, etc. |
| **CRF** | Conditional Random Field — a structured probabilistic model often used for NER with engineered features. |
| **Knowledge graph (KG)** | A graph of typed nodes (entities) and typed edges (relations), used to represent structured domain knowledge. |
| **Doṣa** | Ayurvedic concept of bodily humour. Three doṣas: *vāta* (air/movement), *pitta* (fire/metabolism), *kapha* (water/structure). |
| **Kvātha / කෂාය** | Decoction — a preparation made by boiling herbs in water. |
| **Cūrṇa / චූර්ණය** | Fine herbal powder. |
| **Ghṛta / ඝෘතය** | Clarified butter (ghee), often used as a delivery vehicle for fat-soluble herbal compounds. |
| **Bhasma / භස්ම** | Calcined ash — a metal or mineral processed to a fine pharmaceutically active powder. |
| **Triphalā** | "Three fruits" — a foundational Ayurvedic compound (*haritakī* + *bibhītaka* + *āmalakī*). |
| **Trikaṭu** | "Three spices" — black pepper + long pepper + dry ginger. |

---

## 12. License and citation

* **Source text.** The Sri Lankan Ayurvedic Pharmacopoeia is the
  copyright of its original publisher (the Department of Ayurveda,
  Government of Sri Lanka). It is not redistributed in this repository
  except as derivative annotations.
* **Pipeline and resolver code.** MIT-licensed.
* **Structured JSON corpus and lexicons.** Released under
  CC-BY-SA 4.0 for academic use, with attribution to this repository.

If you use these resources in academic work, please cite this
repository:

```
@misc{sinhala-traditional-medicine-nlp,
  author       = {Medawaththa, Nuwan},
  title        = {Sinhala Traditional Medicine NLP: A knowledge-extraction
                  pipeline and Sanskrit-bridge resolver for the
                  Sri Lankan Ayurvedic Pharmacopoeia},
  year         = {2026},
  howpublished = {\url{https://github.com/nuwan-labs/sinhala-traditional-medicine-nlp}}
}
```

For background literature, see the references list in
[`Proposal/MCS3306_proposal_draft.md`](Proposal/MCS3306_proposal_draft.md).

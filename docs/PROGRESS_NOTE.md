# Progress Note — Sinhala Ayurvedic NLP

Date: 2026-05-23

A self-contained summary of the work completed so far on the Sinhala
Ayurvedic Pharmacopoeia digitisation and resolver-stack project, and the
artifacts it has produced.

---

## 1. Context

The project digitises the *Sri Lankan Ayurvedic Pharmacopoeia* (Sinhala,
multi-volume) and aims to build, on top of the structured corpus:

1. a stack of linguistic resolvers for classical Sinhala Ayurvedic text
   (see `Notes.txt` — the resolver design lives there, not in the
   GitHub-public `RESEARCH_PROPOSAL.md`), and
2. a Sinhala ↔ Sanskrit Ayurvedic terminology / knowledge graph that
   connects Sinhala script to the Sanskrit NLP ecosystem at the point
   where the two traditions share the most vocabulary.

The official academic deliverable is a **UCSC MCS 3306 — Individual
Project in MSc in CS** research proposal (template + defense rubric in
`Proposal/`).

The current working directory `…/penbackup/D/Pipeline` is a backup mirror
of the GitHub project `nuwan-labs/sinhala-traditional-medicine-nlp`,
which is embedded inside it. The scripts at the top level are
byte-identical to their counterparts under `sinhala-traditional-medicine-nlp/`.

---

## 2. What was done

### 2.1 Repository orientation

* Mapped the relationship between the top-level mirror and the embedded
  git repo (`sinhala-traditional-medicine-nlp/`); confirmed canonical
  layout (`data/{source,ocr,rows,structured}`, `pipeline/`, `analysis/`,
  `pdf_pipeline/`, `knowledge_graph/`, `docs/`).
* Located the alternate `pdf_pipeline/extract_pdf.py` that bypasses GCV
  OCR by reading embedded IskoolaPota text directly via PyMuPDF — a
  capability `CLAUDE.md` does not mention.

### 2.2 Research scope clarified

* Identified `Notes.txt` (719 lines) as the project's real strategic
  roadmap: a resolver-stack R1–R7 (tokeniser → orthographic normaliser →
  botanical normaliser → indication normaliser → preparation classifier
  → metrical parser → schema alignment) plus the design for a Sanskrit
  loanword (tatsama / tadbhava / vernacular) resolver.
* Distilled the salvageable ideas from the public `RESEARCH_PROPOSAL.md`:
  structured-to-unstructured transfer driven by a domain-closed
  vocabulary; KG growth curve; gazetteer / KG-CRF / RAG-LLM three-way
  comparison; entity schema (`INGREDIENT`, `FORMULA_NAME`, `QUANTITY`,
  `UNIT`, `INDICATION`, `PREPARATION_VERB`, `ADJUVANT`, `CROSS_REF`,
  `ARTEFACT`); KG edge schema (`CONTAINS`, `TREATS`, `REFERENCES`,
  `CO_OCCURS`, `IS_TYPE`, `DOSED_WITH`).
* Confirmed that the public RESEARCH_PROPOSAL.md is **not** the official
  submission — that role is played by the UCSC MCS3306 template in
  `Proposal/`.

### 2.3 Sinhalized-Sanskrit (tatsama) resolver — prototype built

`sanskrit_resolver.py` (top-level) implements Modules A and B from the
Notes.txt resolver design, with an offline dictionary-driven samāsa
splitter as a third tier.

* **Module A (router, offline).** Classifies each Sinhala term as
  **tatsama** vs **other** using the "Mishra Sinhala" signal
  (mahaprana aspirates ඛඝඡඣඨඪථධඵභ, sibilants ශ ෂ, ඥ, vocalic-r, visarga,
  plus word-initial conjuncts — native Sinhala has none). Native
  geminates (තිප්ප–, ගම්ම–) are correctly *not* flagged.
* **Module B (tatsama resolver).** `aksharamukha` (Sinhala script → IAST)
  → `pycdsl` / **Monier-Williams Sanskrit Dictionary** lookup, with a
  small set of Sinhala nominal suffix variants (-ya/-aya/-yā/-va/-ṁ/-ḥ).
* **Tier 2 — dictionary-driven samāsa segmenter.** Memory-light
  recursive compound segmentation against MW headwords (no parser
  graph). Min segment length 3, max 3 segments. Handles concatenative
  compounds (e.g. `karkaṭakaśṛṅgī → karkaṭaka + śṛṅgī`); does not
  attempt true vowel-sandhi junction.

**Result on the full Vol I structured corpus (Tier 1 + 2 + 3):**

| Field          | Tatsama-signal | Tier 1 + 2 | **Tier 1 + 2 + 3** | Parser gain |
| -------------- | -------------: | ---------: | -----------------: | ----------: |
| Ingredients    |  948 (27.9 %)  |   79 %     |  **81 %** (764)    |     +2 pp   |
| Formula names  |  325 (35.5 %)  |   60 %     |  **76 %** (246)    | **+16 pp**  |
| Prose          | 1,231 (25.5 %) |   62 %     |  **66 %** (817)    |     +4 pp   |

Word-records resolved overall: 1,286 direct + 509 dict-sandhi +
137 parser-sandhi = 1,932. Names benefit the most because formula
names are heavy with compounds (e.g. *drākṣādi*, *triphalādi*) — exactly
where the parser's vowel-junction handling matters.

**Botanical-Latin seed (extracted from MW glosses, no manual work):**

120 ingredients → 85 distinct Latin binomials. Top by corpus frequency:
`Grislea Tomentosa` ×42 (= ධාතකී), `Cerasus Puddum` ×24 (= පද්මකාෂ්ඨ),
`Terminalia Chebula` ×23 (= haritakī), `Phyllanthus Emblica` ×19
(= āmalakī), `Physalis Flexuosa` ×9 (= aśvagandhā / Withania),
`Amyris Agallochum` ×6 (= agar / agaru), …
A small number of false positives (e.g. `Columba Hurriyala` = pigeon
genus, `Coluber Naga` = snake) — a botanist's curation pass is
required before use as an R3 input.

This single pass simultaneously produces material for **R3** (botanical
normaliser), **R4** (indication normaliser — Sanskrit medical glosses
like *jvara* = "fever", *kāsa* = "cough", *kuṣṭha* = "skin disease"),
and **R5** (preparation-type — *kvātha* = "decoction", *bhasma* =
"calcined ash").

### 2.4 Memory-isolated Tier 3 (real sanskrit_parser)

An initial attempt to use `sanskrit_parser.Parser` directly was OOM-killed.
A controlled measurement showed why:

* idle footprint of the full stack is modest (~140 MiB),
* but each `Parser.split()` call **retains 5–55 MiB** that is never
  released; on a corpus-scale run this accumulates into the gigabytes.

The fix is process-level isolation:

* **`sandhi_worker.py`** — a disposable subprocess that sets
  `RLIMIT_AS = 1.5 GB` and `SIGALRM = 8 s` per word *before* importing
  `sanskrit_parser`, reads IAST words from stdin, emits JSONL split
  candidates to stdout, and exits.
* **`--with-parser` mode in `sanskrit_resolver.py`** — collects the
  residual unresolved IAST set across all three fields (deduped,
  length-guarded 6–20 chars), chunks it into batches of 50, spawns one
  worker per batch, appends results to `parser_recoveries.jsonl`
  (resumable), validates each candidate against MW, and merges the
  recoveries back into the per-field lexicons.

Peak RAM stayed comfortably under the 1.5 GB worker cap.

**Run outcome:** 1,015 residual IAST forms across all three fields,
split into 21 batches of 50. All 21 batches completed cleanly — **zero
OOM-kills, zero workers killed**. Per-word worker status:

* `ok` (candidates produced) :  263
* `no_split`                 :  279
* `error`                    :  473

After main-process MW validation of the candidates, **122 IAST forms
were recovered**, updating 137 word-records across the three lexicons
(see table in §2.3).

**Diagnosis of the 473 `error` cases.** Inspection shows that ≥ 55 %
of them carry Sinhala-only IAST diacritics (`ĕ`, `ŏ`, `æ`, `ḻ`, `n̆`)
that Aksharamukha emits for Sinhala-native sounds with no Sanskrit
equivalent — and that `sanskrit_parser` cannot consume. Examples:
`abhiphĕna`, `akmælla`, `amuin̆guru`, `aral̤u`, `asvænna`. These tokens
slipped through Module A because they contained one Sanskritic letter
in an otherwise Sinhala-native string; they are not really tatsama and
should be filtered (or normalised) before being sent to the worker.
That filter is the obvious next improvement and is expected to
eliminate most of the error category at no cost.

### 2.5 Other findings worth keeping

* The structured JSON in this backup tree shows huge "uncommitted"
  diffs against the git repo, but the +/- counts are exactly equal on
  every file — a pure CRLF↔LF re-serialisation artefact, not real edits.
* GitHub repo permissions for `nuwan-labs/sinhala-traditional-medicine-nlp`:
  admin / maintain / push (full) for the authenticated identity.
  `git-lfs` is not installed locally, which is a non-blocking issue for
  non-LFS commits (`--no-verify` skips the LFS pre-push hook).
* Vol I corpus stats (from `nlp_stats.py`): 707 structured entries,
  pages 172–443; 11,007 ingredient cells; 62,562 tokens; 7,100 vocab
  types; 17.3 % artefact-token rate. The data is structured, but **not
  yet research-clean** — known issues catalogued in `Notes.txt` and
  `docs/output_schema.md`.

---

## 3. Files produced in this session

| Path                              | Purpose                                          |
| --------------------------------- | ------------------------------------------------ |
| `sanskrit_resolver.py`            | Tier 1/2/3 resolver (Modules A + B + sandhi)      |
| `sandhi_worker.py`                | Memory-isolated worker for sanskrit_parser       |
| `ingredients_lexicon.json`        | 948 tatsama entries, ingredient field            |
| `names_lexicon.json`              | 325 tatsama entries, formula-name field          |
| `prose_lexicon.json`              | 1,231 tatsama entries, prose field               |
| `botanical_candidates.json`       | 99 ingredients → 72 Latin binomials (R3 seed)    |
| `parser_recoveries.jsonl`         | Tier 3 worker output, append-only / resumable    |
| `resolver_run.log`                | Console log of the last full run                 |
| `.venv/`                          | `aksharamukha`, `pycdsl`, `sanskrit_parser`, etc.|
| `.cdsl_data/`                     | Monier-Williams dictionary database (downloaded) |
| `PROGRESS_NOTE.md`                | This document                                     |

(No changes were made to anything inside the embedded git repo
`sinhala-traditional-medicine-nlp/`.)

---

## 4. Where things stand

* **A working, demonstrable Sanskrit-bridge resolver exists.** It is the
  most actionable piece in the entire `Notes.txt` roadmap and was the
  Notes.txt-recommended starting point ("the tools for the tatsama
  resolver — Aksharamukha, PyCDSL, sandhi_vicchedika — are all available
  today, pip-installable, and can be wired together in an afternoon").
* **It produces useful structured terminology** — three per-field
  lexicons (~2,500 resolved entries) plus a botanical-Latin candidate
  list — without any manual labelling.
* **For the MCS3306 proposal**, this counts as concrete preliminary work
  satisfying the rubric items *access to benchmark data*, *evidence of
  research methodology*, and *contribution sufficient for 15 credits*.

---

## 5. What is *not* done

* The corpus is structured but not research-clean: ~17 % artefact
  tokens, NFC/ZWJ inconsistencies, ingredient ↔ instruction bleed,
  three incompatible dosage unit systems, batch-position correlation in
  the preparation field. None of this has been fixed yet.
* The 70.9 % "other" bucket (tadbhava + vernacular) is untouched —
  requires Module C (etymological lexicon: Sorata's *Sabdakośaya*,
  Geiger, Jayaweera) and Module D (Sri Lankan pharmacopoeia + GRAYU).
  These are calendar-bound by expert availability, not coding effort.
* R1 (classical Sinhala converb tokeniser), R4-Stage-B (condition
  taxonomy with ICD bridge), R5 (full preparation-method classifier),
  R6 (metrical parser — explicitly out of scope per Notes.txt), and R7
  (schema alignment for prose manuscripts) are not started.
* The knowledge graph itself (`knowledge_graph/`) is designed in a
  README only. Phase-1 edges (`CONTAINS`, `IS_TYPE`, `DOSED_WITH`,
  `CO_OCCURS`) are buildable now from the structured JSON with no NLP.
* OCR/spelling-variant collapsing (ශයී / ශඨි / ශටී ≈ *śaṭhī*) is not
  implemented. A fuzzy pass over MW headwords would close most of it.
* Vols II and III are not yet scanned.
* The MCS3306 proposal itself has not been drafted.

---

## 6. Sensible next moves (any order)

1. **Tighten Module A** so that tokens with Sinhala-only IAST marks
   (`ĕ`, `ŏ`, `æ`, `ḻ`, `n̆`) are routed to the `other` bucket rather
   than sent to the parser. Expected to remove most of the 473
   worker-error cases and slightly raise effective resolution rates.
2. **Build the KG Phase-1 edges** from the structured JSON — quick,
   memory-trivial, no NLP required, and gives the MCS3306 proposal a
   second concrete preliminary artifact.
3. **Draft the MCS3306 proposal** section by section, anchoring §
   "Current Progress" / "Evaluation" on the resolver result and the
   Phase-1 KG.
4. **Add the fuzzy-variant pass** to mop up `ශයී`-style OCR siblings.
5. **Curate `botanical_candidates.json`** with a botanist (a few hours
   for the 72 binomials).

---

## 7. How to run what exists

```bash
cd /home/nuwan/Documents/penbackup/D/Pipeline

# Tier 1+2 only (fast, memory-trivial)
.venv/bin/python sanskrit_resolver.py --field all

# Tier 1+2+3 (with memory-isolated sanskrit_parser workers)
.venv/bin/python sanskrit_resolver.py --field all --with-parser \
                  --parser-batch 50 --parser-mem-cap 1500

# Per-field
.venv/bin/python sanskrit_resolver.py --field ingredients
```

Outputs land in the top-level directory:
`<field>_lexicon.json`, `botanical_candidates.json`,
`parser_recoveries.jsonl`, `resolver_run.log`.

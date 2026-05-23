# Resolvers

Linguistic resolvers for Sinhala Ayurvedic text. Currently implements
the **tatsama (Sinhalized-Sanskrit) resolver** that bridges Sinhala
script to Monier-Williams via Aksharamukha and PyCDSL, plus
dictionary-driven and parser-based compound segmentation.

## What's here

| File | Purpose |
| --- | --- |
| `sanskrit_resolver.py` | Three-tier resolver (Module A router + Module B MW lookup + dict / parser sandhi). CLI tool. |
| `sandhi_worker.py` | Disposable subprocess for `sanskrit_parser` compound splitting under a memory cap. Driven by `sanskrit_resolver.py --with-parser`. |

For the architectural background, the OOM-isolation rationale, and the
latest measured resolution rates per field, see
[`../docs/PROGRESS_NOTE.md`](../docs/PROGRESS_NOTE.md).

## Quick start

These scripts assume a Python ≥3.10 virtual environment with the
following packages:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install aksharamukha pycdsl sanskrit_parser indic-transliteration
```

Note: `aksharamukha` triggers `from ast import Str`, which Python 3.12
removed; the resolver script ships a one-line `ast.Str = str` shim so
no source patching is needed.

On first run, `pycdsl` downloads the Monier-Williams Sanskrit-English
dictionary into `--cdsl-dir` (default `.cdsl_data/`, ~50 MB).

## Usage

The resolver expects `*_structured.json` files (the pharmacopoeia
output of the upstream pipeline) in the current working directory:

```bash
# from a directory containing the structured JSONs
cd ../data/structured

# Tier 1+2 only (fast, memory-trivial)
python ../../resolvers/sanskrit_resolver.py --field all

# Tier 1+2+3 (adds sanskrit_parser via memory-isolated workers)
python ../../resolvers/sanskrit_resolver.py --field all --with-parser \
       --parser-batch 50 --parser-mem-cap 1500

# Single field
python ../../resolvers/sanskrit_resolver.py --field ingredients
```

Outputs land in the current directory:
`<field>_lexicon.json`, `botanical_candidates.json`,
`parser_recoveries.jsonl` (resumable), `resolver_run.log`.

A frozen snapshot of these outputs lives at
[`../data/lexicons/`](../data/lexicons).

## Three tiers

* **Module A — Router (offline).** Classifies each Sinhala term as
  *tatsama* vs *other* using the "Mishra Sinhala" signal (mahaprana
  aspirates, sibilants ශ ෂ, ඥ, vocalic-r, visarga, plus word-initial
  conjuncts — native Sinhala has none). Native geminates and clusters
  (තිප්ප–, ගම්ම–, ල්ම–) are correctly *not* flagged.

* **Module B — Tatsama resolver.** `aksharamukha` (Sinhala→IAST) +
  `pycdsl`/Monier-Williams lookup, with a small set of Sinhala nominal
  suffix variants (`-ya`, `-aya`, `-yā`, `-va`, `-ṁ`, `-ḥ`).

* **Tier-2 fallback — Dictionary samāsa segmenter.** Recursive
  concatenative compound splitting against MW headwords. Memory-light,
  handles `karkaṭaka+śṛṅgī`-style compounds; does not attempt true
  vowel-sandhi junction.

* **Tier-3 fallback — `sanskrit_parser` via isolated worker.**
  `--with-parser` spawns `sandhi_worker.py` in batches of 50 words
  under `RLIMIT_AS=1.5 GB` and per-word `SIGALRM=8 s`. Output is
  resumable JSONL (`parser_recoveries.jsonl`). This isolation is
  necessary: `Parser.split()` retains 5–55 MiB per call and ballooned
  earlier in-process runs.

## Latest result (full Vol I corpus, Tier 1+2+3)

| Field | Tatsama-signal | Resolved |
| --- | ---: | ---: |
| Ingredients | 948 / 3 393 (27.9 %) | **81 %** |
| Formula names | 325 / 915 (35.5 %) | **76 %** |
| Prose | 1 231 / 4 825 (25.5 %) | **66 %** |

Also produces a 72→85 distinct Latin-binomial **botanical-Latin seed**
extracted from Monier-Williams glosses, which feeds the planned
botanical-normaliser (R3 in the project roadmap).

## Known limits

* Tokens containing Sinhala-only IAST diacritics (`ĕ`, `ŏ`, `æ`, `ḻ`,
  `n̆`) reach the parser as junk and are reported as `error`. Routing
  these to the "other" bucket in Module A before they enter the worker
  is the next-cheap improvement (~10 lines).
* True morphological lemmatisation (case endings, converbs) is not yet
  implemented — only naïve suffix-stripping.
* OCR / spelling variants of the same Sanskrit term (e.g. ශයී /
  ශඨි / ශටී for *śaṭhī*) are not collapsed. A fuzzy pass over MW
  headwords would close most of these.

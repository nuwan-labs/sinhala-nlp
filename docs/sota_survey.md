# SOTA Survey — Are we using the best approaches?

> Horizontal sweep (all computational sub-problems) + vertical dive
> (the three components where we may be behind, verified on the
> HuggingFace Hub). Conducted 2026-05; covers 2023–2026 literature.
>
> **Round 1** (below): extraction + resolution stack.
> **Round 2** (appended at the end): the areas Round 1 missed —
> traditional-medicine ontology standards, code-mixing framing,
> low-resource KG evaluation, KG completion, and resource-release norms.
> Round 2 changed more *design and framing* decisions than Round 1.

---

## Verdict in one table

| Computational problem | Our approach | 2024–2026 SOTA | Verdict |
|---|---|---|---|
| **OCR** (Stage 0) | Google Cloud Vision (lang=si) | **Surya** (CER 0.76 % vs GCV WER 7.67 % on Sinhala) | **Behind — pilot Surya** |
| **Sandhi / morphology** (resolver Tier 3) | `sanskrit_parser` (Heritage Engine) in a memory-isolated subprocess | **ByT5-Sanskrit** (`chronbmm/sanskrit5-multitask`) beats Heritage on every published benchmark | **Behind — swap, also kills the subprocess hack** |
| **Schema-constrained IE** (prose extractor) | rule-template + SHACL reject-at-emission + provenance | ODKE+, "Chaos to Clarity" — hybrid, evidence-gated, provenance-grounded | **Competitive / converging — keep** |
| **Second NER oracle** | planned CRF via distant supervision | GLiNER2 (en/fr/es only) ; GLiNER v2.5 multilingual (thin Sinhala) | **Keep CRF — GLiNER doesn't do Sinhala well** |
| **Provenance model** | bespoke `char_span` field | PROV-O + RDF-star / nanopublications | **Could upgrade — low effort, high defensibility** |
| **Layout analysis** | hand-built x-zone state machine | LayoutLMv3, TFLOP, DocLayout-YOLO | **Defensible for one book — don't adopt heavy ML** |
| **Fuzzy matching** | planned Levenshtein automata | **SymSpell** (faster at our scale) + Aho-Corasick exact | **Minor swap — SymSpell** |
| **Cross-lingual lexicon** (Modules A/B/C) | Mishra-Sinhala regex + Aksharamukha + Monier-Williams + pratinidhi | no published Sinhala→Sanskrit bridge exists | **Ahead / novel — formalise it** |

---

## The three components where we are behind (verified on HF Hub)

### 1. OCR — Google Cloud Vision → Surya

- **Evidence**: Jayatilleke & de Silva, *Zero-shot OCR Accuracy of
  Low-Resourced Languages: Sinhala & Tamil*, arXiv:2507.18264 (Jul 2025).
  Surya and Document AI are top performers; **Surya CER 0.76 % / WER
  2.61 %** on Sinhala vs **GCV WER 7.67 %** and Tesseract WER 14.89 %.
- **License**: Surya code is GPL-3.0; model weights free for orgs under
  a revenue threshold (research/academic use is fine). Bundles OCR +
  layout + reading-order + table recognition in one tool.
- **Determinism fit**: ✅ OCR is an *input* to our deterministic
  pipeline, not part of the determinism guarantee. We OCR once and
  cache; everything downstream stays byte-stable on that fixed output.
  Neural OCR with greedy decode + fixed weights is reproducible.
- **Caveat**: the benchmark is on *synthetic clean print*. Our source
  is a 1970s-era scan — must pilot on 20–30 of our actual pages and
  diff against GCV before committing.
- **Also relevant (newer)**: arXiv:2602.16430 (Feb 2026) "Designing
  Production-Scale OCR for India" (Chitrapathak/Parichay, VLM-based) —
  worth watching but heavier than we need.

### 2. Sandhi — `sanskrit_parser` → ByT5-Sanskrit

- **Evidence**: Nehrdich et al., ByT5-Sanskrit (Findings of EMNLP 2024,
  arXiv:2409.13920). Joint sandhi-split + lemmatization + morph-tag +
  dependency-parse + OCR-correction. Beats TransLIST by +8.8 perfect-
  match; matches lexicon-based SOTA on SIGHUM (93.83).
- **On the Hub** (verified):
  - `chronbmm/sanskrit5-multitask` — 581.7 M params, T5, **13.1 K
    downloads**, `AutoModelForSeq2SeqLM`. The multitask analyzer.
  - `chronbmm/sanskrit-byt5-dp` — dependency-parse variant.
  - `chronbmm/sanskrit-byt5-ocr-postcorrection` — **directly relevant
    to our OCR-artefact problem**.
  - `dharmamitra-sanskrit-grammar` on PyPI wraps these behind a clean API.
- **Determinism fit**: ✅ T5 greedy/beam decode is deterministic; we
  already cache resolver output (`parser_recoveries.jsonl`), so the
  same caching pattern applies.
- **Bonus**: replacing Tier 3 **eliminates our memory-isolated-subprocess
  hack** (RLIMIT_AS=1.5 GB, SIGALRM=8 s, recycle-every-50-words). That
  plumbing exists *only* because the Heritage Engine leaks memory.
  ByT5 is a normal `transformers` model — no leak, no subprocess.
- **Nuance for the thesis**: the memory-isolated-subprocess pattern is
  one of our four stated contributions. If we swap it out, we should
  reframe it as "the workaround we needed in v1, obviated in v2 by a
  byte-level transformer" — an *honest engineering-evolution* story,
  not a lost contribution.

### 3. Second oracle — CRF stays; GLiNER doesn't fit Sinhala

- **Surprise finding**: GLiNER2 (`fastino/gliner2-large-v1`, 709 K
  downloads, the model Agent-2 recommended for schema-driven structured
  extraction) lists **only en / fr / es**. It cannot run on Sinhala.
- The **multilingual** GLiNER (`gliner-community/gliner_large-v2.5`)
  covers Sinhala only through mDeBERTa-v3's CC100 coverage, which is
  thin for Sinhala and near-zero for *Ayurvedic* Sinhala. And v2.5 does
  flat NER only — no relation/structured extraction.
- **Conclusion**: our planned **CRF via distant supervision on the
  11,007 structured (surface → lemma) pairs** is actually the *more
  practical* second oracle for low-resource Sinhala than GLiNER. Keep it.
- **Reframe for rigour**: "run rule-extractor + CRF as two labelling
  functions and log disagreements" *is* a named methodology —
  **programmatic weak supervision (Snorkel-style data programming)**.
  Cite it; it turns an ad-hoc heuristic into a recognised method.

---

## Where we are competitive or ahead (keep as-is)

- **Schema-constrained, reject-at-emission, provenance-grounded
  extraction**: validated point-for-point by ODKE+ (arXiv:2509.04696,
  98.8 % precision, grounding cut hallucinations 35 %) and "From Chaos
  to Clarity" (arXiv:2601.14267, auditable biomedical IE). Our SHACL
  reject-at-emission is *stronger* than GLiNER2's soft 0.5-threshold
  scoring — make that an explicit contribution.
- **Cross-lingual Sinhala→Sanskrit bridge**: no published system does
  this. Module A's Mishra-Sinhala phonotactic signal (aspirate /
  sibilant / vocalic-r / word-initial-cluster) has no computational
  classifier in the literature — our ~27 % type-coverage statistic and
  the A→B→C cascade is genuinely novel.
- **The pratinidhi-table-as-lexicon (Module C)**: unique; no external
  tool replaces a corpus-internal substitute-substance glossary used as
  a vernacular→Sanskrit bridge.

---

## Low-cost wins we should adopt regardless

1. **Deterministic NFC + ZWJ canonicalization pass** — kills the 24 %
   NFC/NFD failures and ZWJ key inconsistencies. Pure rules.
2. **Apte (1957) + Śabdasāgara as Tier-1.5 lexicon fallbacks** via the
   `pycdsl` we already use — Apte's Classical coverage catches
   pharmacological compounds MW1899 misses. Zero new dependency.
3. **SymSpell over Levenshtein automata** for the fuzzy gazetteer layer;
   keep Aho-Corasick for exact longest-match. `sinling` for akṣara
   tokenization so edit distance is grapheme-cluster-aware.
4. **GRAYU / AyurKOSH** as a domain dictionary layer (before Module B's
   generic MW lookup) and as a downstream interoperability sink.

---

## What is overkill / out of scope (don't build)

- LayoutLMv3 / DocFormer / TFLOP / TableFormer — earn their keep on
  heterogeneous million-document corpora; we have one fixed-column book.
- Levenshtein automata — over-engineered for ~2000 short patterns.
- Pure-LLM extraction as the primary path — abandons the determinism
  thesis; the best biomedical systems (ODKE+) gate LLMs *behind* the
  schema/evidence checks we already put first.
- Neural Sinhala→Sanskrit translation (IndicTrans2) — we need lexical
  *alignment*, not translation; the Sanskrit pair is data-thin anyway.
- Cross-lingual embedding similarity (MuRIL / IndicBERT) as a resolver
  — useful only for fuzzy-match *ranking*, not deterministic lookup.

---

## Recommended changes to the project plan

| Priority | Change | Effort | Touches |
|---|---|---|---|
| **P1** | Pilot Surya OCR on 20–30 real pages; diff vs GCV | ~half day | `pipeline/ocr_gcv.py` → add `ocr_surya.py` |
| **P1** | Swap Tier-3 `sanskrit_parser` → `chronbmm/sanskrit5-multitask`; retire the subprocess hack | ~1 day | `resolvers/sandhi_worker.py`, `sanskrit_resolver.py` |
| **P2** | NFC + ZWJ canonicalization pass | ~2 h | new `pipeline/normalize.py`, called everywhere |
| **P2** | Add Apte + Śabdasāgara to the resolver fallback chain | ~2 h | `resolvers/sanskrit_resolver.py` |
| **P2** | SymSpell + `sinling` for the gazetteer (Block A) | ~3 h | `pipeline/build_gazetteer.py` (planned) |
| **P3** | Keep CRF second oracle; reframe as weak supervision; cite Snorkel | ~1 h (framing) | proposal + plan docs |
| **P3** | PROV-O + RDF-star provenance serialization | ~half day | `knowledge_graph/build.py` exporters |
| **P3** | GRAYU / AyurKOSH domain dictionary layer | ~half day | `resolvers/` + KG external IDs |

The **two P1 items** are the headline: our OCR and our sandhi tier are
both demonstrably behind freely-available, license-compatible,
determinism-compatible alternatives — and the sandhi swap also removes
our most fragile piece of engineering.

---

## Sources (fetched / verified)

- Sinhala/Tamil OCR benchmark: https://hf.co/papers/2507.18264 (arXiv:2507.18264)
- ByT5-Sanskrit: https://aclanthology.org/2024.findings-emnlp.805.pdf (arXiv:2409.13920)
- ByT5-Sanskrit models: https://hf.co/chronbmm/sanskrit5-multitask · https://hf.co/chronbmm/sanskrit-byt5-ocr-postcorrection
- GLiNER2: https://hf.co/fastino/gliner2-large-v1 (arXiv:2507.18546) — en/fr/es only
- GLiNER multilingual: https://hf.co/gliner-community/gliner_large-v2.5
- ODKE+: https://arxiv.org/html/2509.04696v1
- Chaos to Clarity: https://arxiv.org/abs/2601.14267
- LLM-KG construction survey: https://arxiv.org/html/2510.20345v1
- Surya OCR: https://github.com/VikParuchuri/surya
- India production OCR (newer): https://hf.co/papers/2602.16430
- SymSpell: https://github.com/wolfgarbe/SymSpell
- Sinling tokenizer: https://github.com/ysenarath/sinling
- PyCDSL (Apte/Śabdasāgara access): https://github.com/hrishikeshrt/PyCDSL
- GRAYU: https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2025.1727224/full

---

# Round 2 — Areas Round 1 missed

Three further parallel surveys: (4) traditional-medicine + measurement
ontology standards, (5) Sinhala NLP landscape + code-mixing framing,
(6) low-resource KG evaluation + KG completion + resource-release norms.

## R2 verdict in one table

| Area | Our current stance | Finding | Action |
|---|---|---|---|
| **TM ontology** | bespoke 11-node schema | No off-the-shelf Ayurveda ontology exists (OBO Foundry has none); standards are *code systems* (ICD-11 TM2, NAMASTE, SNOMED-AYUSH), not edge ontologies | **Keep schema; add external IRI bindings** |
| **Phytochemical / PlantPart binding** | none yet | ChEBI (chemistry) + Plant Ontology PO (anatomy) are the open standards | **Bind — high-leverage, no schema change** |
| **Units** | bespoke registry | QUDT is active (v3.1.4), has GRAIN/DRAM/GRAM, extensible via conversionMultiplier; no tola/pala/māṣaka anywhere | **Model traditional units as `qudt:Unit` + conversionMultiplier; reuse QUDT for metric/apothecary** |
| **Quantity extraction** | hand-rolled regex + dosage.py | CQE (Comprehensive Quantity Extractor, EMNLP 2023) is the open tool | Optional — our unit work is done; cite CQE as the comparable |
| **Linguistic framing** | "tatsama/tadbhava/deśya" | By Poplack integration criterion these are **borrowings under diglossia**, NOT code-switching | **Reframe: borrowing/diglossia for linguistics, word-level-LID for methods** |
| **Sinhala neural model** | none | No NER-ready or domain-matched Sinhala model exists; SinhalaBERTo/XLM-R usable as embeddings only | **Optional CRF feature source; not mandatory** |
| **IAA metric (validator L3)** | Cohen's κ ≥ 0.75 | κ suffers prevalence paradox on skewed correct/incorrect labels | **Switch headline to Gwet's AC1 + bootstrap CIs; keep κ secondary** |
| **LLM-judge (validator L4)** | "validation layer" | Grounded LLM judge = 88% precision but **44% recall** (biomedical); "requires human oversight" | **Reframe L4 as triage/error-flagging, never certification** |
| **KG completion / link prediction** | implied future use | Premature at 4k nodes (benchmarks 14k–40k+); KGE scores untrustworthy under open-world; clinical-misleading risk | **Demote to exploratory, expert-gated, non-clinical-advice** |
| **Resource release** | CC-BY-SA mentioned | Datasheets + Data Statements + FAIR + Croissant are the norms; NSINA shows the copyright-derived-layer pattern | **Adopt the release triad; document upstream copyright** |

## R2 — the consequential corrections

### Validation framework (highest impact — fixes a committed design)

1. **IAA: Cohen's κ → Gwet's AC1.** Our `anchors.yaml` / Notes.txt target
   was κ ≥ 0.75. A correctness-annotation task is heavily skewed (most
   triples correct), which triggers the **prevalence/kappa paradox** —
   κ can be near-zero even at 95% agreement. Gwet's AC1 is robust to
   class imbalance. Report AC1 as headline, κ + Krippendorff's α as
   secondary, all with bootstrap confidence intervals (mandatory at
   n=100, 2–3 raters). Source: IAA-selection survey arXiv:2603.06865.

2. **LLM-judge (L4): triage, not validation.** Adam & Kliegr 2025
   (arXiv:2409.07507, IPM): a *grounded* LLM judge (compares triple to
   a retrieved snippet, not to parametric knowledge) scored **88%
   precision / 44% recall** on biomedical BioRED-Verify and the authors
   conclude it "requires human oversight." So L4 can flag suspect edges
   for human review but must never certify correctness. Single-shot
   judgments are unreliable even at temperature 0 (Kim et al.
   arXiv:2412.12509) — use multi-sample consistency.

3. **Cite ProVe (Semantic Web Journal 2024, 87.5% acc) for L1
   provenance** and **BioRED / BioCreative VIII conventions** (triple
   P/R/F1 + separate entity-linking accuracy) for the eval reporting
   split. Turns our bespoke checks into recognised methodology.

### Schema interoperability (low cost, high leverage)

4. **Add external IRI bindings without changing the schema:**
   - `Phytochemical` → **ChEBI** ID (when we have phytochemicals)
   - `PlantPart` → **Plant Ontology (PO)** term (root/bark/leaf/…)
   - keep `Disease` → ICD-11 TM2, `Plant` → POWO IPNI LSID
   These four `skos:exactMatch` bindings are the cheapest interoperability win.

5. **Units → QUDT pattern.** Mint traditional-unit IRIs as
   `ayur:unit/Kalan a qudt:Unit ; qudt:conversionMultiplier 5.0 ;
   qudt:hasQuantityKind quantitykind:Mass`, and reuse QUDT's existing
   `unit:GRAM`/`unit:GRAIN`/`unit:DRAM` for the units it already has.
   Our `unit_equivalences.json` becomes QUDT-interoperable rather than
   an isolated lexicon. QUDT confirmed to lack South-Asian units, so the
   registry stays — it just gets a standard wrapper.

### Framing (strengthens the thesis, ~zero code)

6. **Borrowing-under-diglossia, not code-switching.** State the
   linguistics precisely (tatsama/tadbhava are *integrated borrowings*,
   one script, one grammar — Poplack's morphosyntactic-integration test
   classifies them as borrowing, not code-switching). But frame Module A
   computationally as **word-level language/origin identification** —
   the exact task in code-mixed Indic NLP — which gives transferable
   baselines (CRF LID ≈ 0.91 F1) and citations. Dual framing is the
   honest, defensible move; a linguist reviewer would reject a flat
   "code-switching" claim.

7. **KG completion: demote to exploratory.** Do NOT build research
   claims on predicted TREATS edges. Our graph (4 089 nodes) is an order
   of magnitude below KGE benchmark scale (FB15k-237 ≈ 14.5k, WN18RR ≈
   41k) and far sparser; Safavi et al. 2020 (arXiv:2004.01168) show KGE
   scores are untrustworthy probabilities under the open-world
   assumption that governs our graph. Predicted herb→disease links also
   carry real clinical-misleading risk. Frame any link prediction as
   expert-gated hypothesis generation with explicit non-clinical-advice
   disclaimers.

8. **Resource-release triad.** Ship the derived KG + lexicons with a
   **Datasheet for Datasets** (Gebru et al.), a **Data Statement for
   NLP** (Bender & Friedman — apt for low-resource Sinhala), **FAIR**
   compliance, and **Croissant** metadata (NeurIPS D&B expects it).
   License the *derived layer* CC-BY-SA with an explicit upstream-
   copyright provenance statement (no source-text redistribution) — the
   pattern NSINA uses for copyright-derived Sinhala corpora.

### New corpora/tools worth pulling in

9. **SiDiaC** (diachronic Sinhala corpus, 426–1944 CE) — the closest
   *classical/literary-register* match to our text; useful for OOV and
   tatsama-lexicon expansion where web-trained models fail.
10. **multiNER** (suralk, CC0) — the *only* public Sinhala NER corpus
    (news domain); a distant-supervision warm-start, not medical.
11. **Confirmed gaps to state in the proposal:** no Sinhala
    medical/Ayurvedic NER corpus or model; no usable Sinhala NER model
    at all; no tatsama/tadbhava classifier (Module A is novel); Sinhala
    absent from IndoWordNet; UD Sinhala treebank is 880 tokens.

## R2 sources (fetched / verified)

- QUDT units vocab: https://qudt.org/doc/DOC_VOCAB-UNITS.html
- OBO Foundry registry (confirmed no TM ontology): https://obofoundry.org
- ICD-11 TM1 vs TM2: https://pmc.ncbi.nlm.nih.gov/articles/PMC9248085/
- Units-ontology comparison (OM vs QUDT): https://semantic-web-journal.net/system/files/swj1775.pdf
- CQE quantity extractor: https://arxiv.org/abs/2305.08853
- SinBERT / BERTifying Sinhala: https://arxiv.org/pdf/2208.07864
- SinLlama: https://arxiv.org/abs/2508.09115
- NSINA corpus + license: https://github.com/Sinhala-NLP/NSINA
- Code-mixed NER comparison: https://arxiv.org/html/2509.02514v1
- SiDiaC: https://arxiv.org/pdf/2509.17912 ; https://github.com/NeviduJ/SiDiaC
- multiNER: https://github.com/suralk/multiNER
- UD Sinhala-STB: https://universaldependencies.org/treebanks/si_stb
- Adam & Kliegr, traceable LLM RDF validation: https://arxiv.org/pdf/2409.07507
- Safavi et al., KGE calibration: https://arxiv.org/pdf/2004.01168
- IAA-metric selection survey: https://arxiv.org/html/2603.06865
- LLM-judge reliability: https://arxiv.org/abs/2412.12509
- ProVe: https://arxiv.org/abs/2210.14846
- FAIR: https://www.nature.com/articles/sdata201618

---

# Round 3 — Deeper uncovered areas

Three further parallel surveys: (7) biomedical & cross-lingual **entity
linking**, (8) **digital humanities / computational philology** for
historical medical texts, (9) **Ayurvedic pharmacovigilance** — heavy
metals + herb-drug interactions + safety KGs.

## R3 verdict in one table

| Area | Our current stance | Finding | Action |
|---|---|---|---|
| **Entity linking** (our gazetteer+resolver) | dictionary EL with cross-lingual bridge | Textbook EL pipeline; SapBERT/KrissBERT would gain recall but **XL-BEL benchmark has no Indic, no Sinhala** — neural EL is unvalidated for our script | Keep dictionary EL; add **NIL detection**, **composite-mention decomposition**, optional **multilingual SapBERT as 2nd-oracle re-ranker** |
| **xMEN** (JAMIA Open 2025) | not cited | Closest published analogue: modular cross-lingual MEN with English-alias fallback when target language has few aliases — structurally identical to our Sinhala→Sanskrit→MW bridge | **Cite as primary reference**; positions our work in a recognised paradigm |
| **DH framing** | NLP/KG framing only | TEI authoring is heavy ceremony (single source, no critical apparatus); historical-text-normalization framing is the highest-value DH move | Reframe spelling variants as **historical text normalization** (Bollmann seq2seq paradigm); add CTS-style URNs; one-shot TEI export; dual-track publication (NLP + DH/JOHD) |
| **TEI / scholarly edition** | none | Authoring in TEI not worth it; **exporting** to TEI is | One-shot serializer; not the source-of-truth format |
| **Safety / pharmacovigilance** | KG represents none | Our KG has rasa-śāstra Mineral nodes (Hg/Pb/As-bearing); ~20% of Ayurvedic products exceed WHO heavy-metal limits (Chonnam Med J 2024). Publishing without safety annotation is ethically incomplete | **Add `SafetyFlag` node + `HAS_SAFETY_FLAG` edge** (heavy_metal_bearing / animal_origin / pediatric_pregnancy_caution); **bind Mineral → PubChem CID + ChEBI** for hazard chains; **adopt GRAYU's disclaimer verbatim** in every export |
| **HDI / contraindication / max-dose** | none | Real KGs exist (HTINet2/TMKG, NP-KG, NPASS 3.0, DrugBank 6.0 schema) | **Future work** — explicitly scope out for MSc; document the bridge plan |

## R3 — the consequential corrections

### Entity-linking framing & three concrete additions

1. **Explicit NIL handling** (BLINKout / NILINKER pattern). Currently we
   silently drop unresolved mentions. Emit
   `{status: "NIL", mention, stage_reached, char_span}` records — turns
   our recall gap into auditable data and matches BELB benchmark
   conventions.

2. **Composite-mention decomposition** before gazetteer lookup
   (SimConcept-style). Direct fit for Ayurvedic compound names: *Triphalā
   → {Harītakī, Bibhītakī, Āmalakī}*; *Trikaṭu → {Piper longum, Piper
   nigrum, Zingiber}*. Pure rule layer, deterministic, likely our highest-
   leverage recall gain.

3. **Multilingual SapBERT as a strictly second-oracle re-ranker** for
   NIL mentions only. Run offline, write candidates to
   `data/lexicons/sapbert_suggestions.json`, require human approval
   before any KG write. Honest caveat: XL-BEL never tested Sinhala
   (covers Chinese/Finnish/German/Japanese/Korean/Russian/Spanish/Thai/
   Turkish), so expect degraded performance vs the paper's numbers.

### Digital-humanities reframing (~zero code, large positioning win)

4. **Reframe the spelling-variant problem as historical text
   normalization** (Bollmann COLING 2016, NAACL 2019). Build a small
   gold normalization set; benchmark a char-level seq2seq against our
   rule/Levenshtein approach. This makes the linguistic side legible
   to a defined NLP/DH subfield.

5. **CTS-style canonical URNs** on top of char-spans:
   `urn:cts:lka:bedavidyava.pharma:p172.e44.yogaya.item3`. Trivial cost,
   citable identifiers usable across TEI/RDF/Cypher consumers.

6. **One-shot TEI export** — `<teiHeader>` + `<div type="formula">`
   blocks + `<rs ref="...">` named-entity tags pointing at KG IRIs.
   Generated from JSON, not authored. Unlocks SARIT/GRETIL-style
   discoverability and JOHD data-paper publishability.

7. **Dual-track publication**: NLP venues (LREC, EMNLP-findings,
   WiNLP) for the resolver / extractor / KG; DH venues (JOHD data
   paper, DHandNLP, DSH) for the corpus and edition.

### Safety — the ethical minimum we MUST ship

8. **`SafetyFlag` node class** with three literature-grounded enum values:
   - `heavy_metal_bearing` — auto-derived from `CONTAINS → Mineral`
     where the mineral resolves to {rasa/Hg, naga/Pb, hingula/HgS,
     manaḥśilā/As-realgar, abhraka-bhasma, etc.}
   - `animal_origin` — propagated from AnimalOrigin node membership
   - `pediatric_pregnancy_caution_metallic` — derived from flag 1 + WHO
     guidance.
   No new clinical judgment — these flags are *propagated facts*, not
   diagnoses.

9. **Bind Mineral nodes to PubChem CID + ChEBI ID** where the chemistry
   is unambiguous:
   - rasa → Hg (PubChem CID 23931)
   - gandhaka → S (CID 5362487)
   - naga → Pb (CID 5352425)
   - hingula → HgS / cinnabar
   Gives downstream consumers click-through to GHS hazard codes without
   us asserting clinical claims. Explicitly note that bhasma may not
   share elemental toxicity — that uncertainty is the honest scientific
   position.

10. **Disclaimer (mandatory text in README + every JSON header)** —
    adopt GRAYU's wording verbatim: *"This KG digitizes a historical
    pharmacopoeia. CONTAINS and TREATS edges record what classical
    texts assert, not what is clinically validated. The KG does not
    assign mechanistic meaning to any plant–disease link, nor does it
    imply therapeutic efficacy or safety. Heavy-metal-bearing
    formulations are flagged but are not endorsed for use. This is
    not medical advice."*

11. **Scope HDI / `HAS_CONTRAINDICATION` / `MAX_SAFE_DOSE` explicitly
    as future work** — naming the bridge resources (HTINet2/TMKG,
    NP-KG, NPASS 3.0, DrugBank 6.0 schema). Frame as the natural
    Phase-2 of the resolver stack.

## R3 sources (fetched / verified)

- Comprehensive evaluation of biomedical EL (PMC11097978)
- Overview of biomedical EL through the years (PMC9845184)
- xMEN: https://arxiv.org/abs/2310.11275
- SapBERT: https://github.com/cambridgeltl/sapbert ; cross-lingual: arXiv:2105.14398
- TEI ↔ RDF tradeoffs: https://dhq.digitalhumanities.org/vol/16/2/000605/000605.html
- SARIT (TEI for Sanskrit/Indic): https://tei-c.org/activities/projects/sarit/
- KGs for ancient Chinese medicine classics: PMC12502320
- Bollmann historical normalization (COLING 2016): https://aclanthology.org/C16-1013/
- CTS (Digital Classicist Wiki): https://wiki.digitalclassicist.org/Canonical_Text_Services
- Heavy metals in Ayurvedic medicine (Chonnam Med J 2024): PMC11148304
- HTINet2 herb-target prediction: PMC11341278
- GRAYU (Frontiers Pharmacology 2025): doi 10.3389/fphar.2025.1727224
- NP-KG (PMC12150722): natural-product↔drug interaction KG
- DrugBank 6.0 (NAR 2024 D1265): DDI schema reference
- Lead poisoning from Ayurvedic medicine (Frontiers in Pediatrics 2025)

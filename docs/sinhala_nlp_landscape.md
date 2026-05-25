# Sinhala NLP — Linguistic Profile, Resources, and Research Landscape

> Background document for the Sinhala Traditional Medicine NLP project.
> Synthesised from three parallel literature surveys conducted 2026-05.
> Markers: **[F]** = source page fetched and read; **[S]** = found in
> search snippet, not full-fetched. Numbers from [S] sources should be
> re-verified against primary papers before citing in the thesis.

---

# Part I — Linguistic profile of Sinhala for NLP

## 1.1 Genetic and typological classification

Sinhala (ISO 639-1 `si`, ISO 639-3 `sin`, Glottolog `sinh1246`) is an
Indo-Aryan language of the **Insular Indo-Aryan** sub-branch (a.k.a.
Sinhala-Maldivian / Dhivehi-Sinhala). Its only living close relative
is **Dhivehi/Maldivian**. The branch began diverging from continental
Indo-Aryan around the 5th century BCE, leaving Sinhala
morpho-phonologically distinct from Hindi/Urdu, Bengali, or Marathi:

- **Prenasalized consonants** (rare in IA elsewhere) — ඬ ඳ ඹ ෙ.
- **Four-way deictic system** (proximal / medial / distal / anaphoric)
  — typologically unusual.
- **No living close continental relative** — methods that work cross-
  lingually between Hindi-Marathi-Bengali do not transfer trivially.

Crucially, **deep 2000-year contact with Tamil** (Dravidian) has
reinforced Sinhala's SOV, head-final, postpositional, left-branching
syntax. Syntactically Sinhala patterns nearer to Tamil than to Hindi,
even though its core lexicon is Indo-Aryan.

**Morphology**: mixed agglutinative-fusional. Nouns inflect for number,
definiteness, animacy, gender, and ~5–8 cases (UD-STB documents 8).
Verbs have a flagship feature absent in Hindi: the **volitive /
involitive (active vs. inactive) stem class** — a grammaticalised
distinction in agentive control that triggers non-nominative subject
marking (dative/instrumental/accusative subjects on involitives).

**Diglossia**: classical Fergusonian. Literary (written) Sinhala
enforces subject-verb agreement, retains heavy Sanskrit/Pali lexicon,
and uses the full **miśra** alphabet. Colloquial Sinhala drops verb
agreement, prefers native (*deśya* / *eḷu*) lexis, and uses a
phonemic subset. Gair (1968) and Paolillo argue the variation is
**continuous, not discrete** — directly relevant when our pharmacopoeia
mixes classical recipe headings with quasi-colloquial gloss.

## 1.2 The Sinhala script — computational implications

Sinhala script sits in Unicode block **U+0D80–U+0DFF** (plus archaic
numerals at U+111E0–U+111FF). Brahmic, abugida. Each *akṣara* is a
consonant + dependent vowel sign; the **al-lakuna (virama, U+0DCA)**
suppresses inherent /a/.

**Conjuncts** are formed using **virama + ZWJ (U+200D)** for:
- *yansaya* `˗්‍ය`
- *rakāransaya* `˗්‍ර`
- *rēpaya* `˗්‍ර` (over base)

The **ZWJ is mandatory and visible-affecting**, unlike Devanagari where
it is optional. Several vowel signs (ේ ො ෝ ෞ) decompose under NFD into
two code points and recompose under NFC — so any pipeline must NFC-
normalize at every boundary.

**Suddha vs Miśra**: the script encodes both
- **Suddha (śuddha)**: ~20 native consonants — pure Sinhala phonology.
- **Miśra**: adds ~18 consonants — aspirates ඛ ඝ ඡ ඣ ඨ ඪ ථ ධ ඵ භ,
  sibilants ශ ෂ, palatal nasal ඥ, vocalic-r ඍ/ෘ ඎ/ෲ, and visarga.

The miśra letters are **phonemically inert in modern speech** but
**orthographically obligatory for tatsama Sanskrit-loan spelling** —
exactly the register of an Ayurvedic pharmacopoeia. This is the signal
our **Module A (tatsama router)** exploits.

## 1.3 NLP classification frameworks

| Framework | Status of Sinhala | Source |
|---|---|---|
| Joshi et al. 2020 (ACL) — "State and Fate of Linguistic Diversity" | **Class 1 — "The Scraping-Bys"**: some unlabeled web text, scant labeled data. Same tier as Zulu, Igbo, Nepali. | aclanthology.org/2020.acl-main.560 [S] |
| Universal Dependencies | **UD_Sinhala-STB**, in UD since v2.11 (Liyanage & Sarveswaran 2023); **100 sentences / 880 tokens** — one of the smallest UD treebanks. 8 cases, 13/17 UPOS tags, 41 deprels. | universaldependencies.org/treebanks/si_stb [F] |
| AI4Bharat ecosystem (IndicBERT, IndicTrans, BPCC, Samanantar) | **Excluded** — all four cover only the 11–12 constitutionally recognised Indian languages. **No AI4Bharat-native Sinhala model.** | github.com/AI4Bharat/indicnlp_catalog [F] |
| FLORES-200 / NLLB | **Included** (`sin_Sinh`) as a low-resource MT language | facebook research/flores [S] |
| Ethnologue / ISO | `si` / `sin`, status **1 (National)**, ~18 M L1 + ~2 M L2 speakers; primary in Sri Lanka | wikipedia.org/wiki/Sinhala_language [F] |
| Glottolog | `sinh1246` under Dhivehi-Sinhala (Insular IA) | wikipedia.org/wiki/Sinhala-Maldivian_languages [F] |
| Unicode Standard | Block U+0D80–U+0DFF; SLS 1134:2004 national standard | r12a.github.io/scripts/sinh/si.html [F] |
| Morphological analyzer ecosystem | **SinMorphy** (Wijesiri et al., IEEE 2021, UoM) — FST in Foma/Lexc; first comprehensive analyzer | github.com/nlpcuom/SinMorphy [S] |

The correct tag is **"extremely low-resource for labelled NLP data,
moderately low-resource for raw text"** — consistent with Joshi class 1.

## 1.4 Computational properties that drive design decisions

1. **Grapheme-cluster-aware tokenization is mandatory.** Splitting on
   Unicode codepoints shreds conjuncts (e.g. ක්‍ෂ = ක + ් + ZWJ + ෂ);
   always segment on extended grapheme clusters / akṣara via DFA.
2. **NFC normalization before anything else.** The four circumgraph
   vowels (ේ ො ෝ ෞ) silently exist in two equivalent encodings;
   equality, hashing, and dictionary lookup fail without normalization.
3. **ZWJ-sensitivity**. U+200D inside otherwise identical-looking
   strings changes meaning and rendering — never strip ZWJ during cleanup.
4. **Suddha / Miśra variation is meaning-preserving.** The same lemma
   may be spelt with native or Sanskrit-aspirate consonants depending
   on register; a tatsama-folding normalization layer aids retrieval.
5. **Volitive / involitive verbs perturb case.** POS-tagging or
   dependency parsing that assumes "nominative = subject" mis-aligns
   ~20% of clauses; treat subject as case-agnostic.
6. **Diglossia means register-stratified training data.** A model trained
   on colloquial Sinhala (FacebookDecadeCorpora) will under-perform on
   literary / Ayurvedic prose; mix SinMin/literary corpora.
7. **No standard word boundary in compounds + sandhi at tatsama joins.**
   Spaces are used, but classical compounds and Sanskrit sandhi
   (e.g. ක්‍ෂීර + ඔෟෂධ) fuse without space.

## 1.5 Common myths and mistakes

1. **"Treat Sinhala like Hindi"** — False. Hindi is Central IA, weak
   head-finality, Devanagari-style conjuncts. Sinhala is Insular IA,
   rigidly head-final, visible virama, involitive verbs, classical
   diglossia Hindi lacks.
2. **"Use AI4Bharat / IndicBERT / IndicTrans"** — they exclude Sinhala.
   Use XLM-R, MuRIL (partial — also excludes Sinhala in fact),
   or Sinhala-specific models (SinLlama, SinBERT).
3. **"Tokenize on codepoints / on whitespace"** — codepoints break
   conjuncts; whitespace misses sandhi-fused tatsama compounds critical
   in Ayurveda.
4. **"Sinhala = Singlish romanized"** — Romanized Singlish is a
   separate orthographic system on social media; mixing without script
   identification destroys recall.
5. **"Aspirates ඛ ඝ ඡ ඣ are pronounced"** — In modern colloquial Sinhala
   they are not phonemically distinct; but they are orthographically
   obligatory in tatsama. Phoneme-level folding helps fuzzy match but
   breaks exact lookup.
6. **"Sinhala script supports OCR out of the box"** — Most pre-2010
   Sri Lankan publications use legacy non-Unicode fonts (DL-Manel,
   FM Abhaya, Kaputa) with private codepoint mappings. GCV often
   mis-decodes IskoolaPota digit/conjunct rendering. Always validate
   via NFC + a tatsama dictionary spot-check.

---

# Part II — Resource landscape (2018–2026)

Legend: **[F]** = directly fetched · **[S]** = search-snippet only ·
Maintained: A = active, S = stale, U = unknown.

## 2.1 Corpora

| Resource | Year | Maintainer | Size / coverage | License | Maint | Usable for our project? |
|---|---|---|---|---|---|---|
| NSINA [F] | 2024 | Sinhala-NLP (Ranasinghe et al.) | 506,932 news articles, 1.87 GB | CC-BY-SA-4.0 (gated) | A | Partial — news domain |
| NSINA-Headlines [F] | 2024 | Sinhala-NLP | 487k headline pairs | CC-BY-SA-4.0 | A | No |
| NSINA-Categories [S] | 2024 | Sinhala-NLP | ~50k categorised | CC-BY-SA-4.0 | A | No |
| OSCAR Sinhala [S] | 2018+ | Inria ALMAnaCH | ~452 M tokens (CC100/OSCAR-19); OSCAR-23.01 cleaner | CC0 (extract) | A | Partial — noisy pretrain only |
| CC100-Sinhala [S] | 2020 | StatMT / Conneau et al. | 452 M tokens | derived from CC | S | Partial |
| MADLAD-400 (si) [S] | 2024 | Google | ~10 M+ sents (filtered slice in SinLlama) | ODC-BY | A | Partial |
| CulturaX (si) [S] | 2023 | uonlp | mC4 + OSCAR Si | ODC-BY + CC0 | A | Partial |
| sinhala-7m-corpus [F] | 2025 | Sinhala-NLP | 2.33 M lines | CC-BY-SA-4.0 | A | Partial |
| sinmin [F] | 2025 | Sinhala-NLP | 314k | open | A | Partial |
| FacebookDecadeCorpora [F] | 2025 | Sinhala-NLP | 364k FB posts | CC-BY-SA | A | No |
| Sinhala Wikipedia (siwiki) [S] | rolling | WMF | ~25k articles, ~10–20 M tokens | CC-BY-SA-4.0 | A | Yes (small but clean) |
| **SiDiaC** [F] | 2025 | Jayatilleke & de Silva (UoM) | **58k words, 46 works, 426–1944 CE**; diachronic | copyright-cleared | A | **Yes — closest classical register** |
| **SiPaKosa** [F] | 2026 (preprint) | Gururatne & Jayatilleke (IIT/UoM) | **786k sents / 9.25 M words; 16 historical docs + Tripiṭaka** | copyright-cleared | A | **Yes — closest to Ayurvedic register** |
| pali-sinhala [F] | 2025 | Sinhala-NLP | 28.4k Pali-Sinhala pairs | open | A | Yes (Pali bridge) |
| FLORES-200 (sin_Sinh) [S] | 2022 | Meta NLLB | 1012 dev + 1012 devtest sents EN↔SI | CC-BY-SA-4.0 | A | Yes (eval only) |
| BPCC (AI4Bharat) [S] | 2023 | AI4Bharat | ~230M EN-Indic pairs; **Sinhala excluded** | CC-BY-4.0 | A | No |
| OpenSubtitles si-en [S] | 2018 | OPUS | ~3 M sent pairs | open | A | Yes |
| WMT19 si-en filtering [S] | 2019 | WMT | ~3 M noisy + 600 dev/test | research-only | S | Partial |
| **Ayurvedic / medical Sinhala** | — | — | **DOES NOT EXIST** | — | — | — |

## 2.2 Language models

| Resource | Year | Maintainer | Size / training data | License | Usable? |
|---|---|---|---|---|---|
| **SinLlama_v01** [F] | 2025 | polyglots (UoM) | 8B Llama-3-8B + **303.9 M-token Sinhala CPT**; base (not instruct) | Meta Llama 3 | Yes (needs SFT) |
| **SinBERT-large** [F] | 2022 | NLPC-UOM (Dhananjaya et al.) | RoBERTa-large, sin-cc-15M | MIT | Yes |
| SinBERT-small [S] | 2022 | NLPC-UOM | RoBERTa-small | MIT | Yes |
| **SinhalaBERTo** [F] | 2020 | keshan | RoBERTa, 83.5 M params, 6 layers, OSCAR-si dedup | unstated | Yes (legacy) |
| sinhala-bert-medium-v2 [S] | 2023 | Ransaka | medium BERT | open | Partial |
| XLM-RoBERTa (base/large) [S] | 2019 | Meta | Sinhala in CC100 — **best multilingual baseline for Sinhala per LREC 2022** | MIT | Yes |
| mBERT [S] | 2018 | Google | Sinhala via Wikipedia (very thin) | Apache-2.0 | Partial (weak) |
| MuRIL [S] | 2021 | Google India | 17 Indian langs — **Sinhala NOT included** | Apache-2.0 | No |
| IndicBERT v1/v2 [S] | 2020/2023 | AI4Bharat | **Sinhala NOT included** | MIT | No |
| IndicTrans2 [S] | 2023 | AI4Bharat | 22 scheduled langs — **Sinhala NOT supported** | MIT | No |
| **NLLB-200** [S] | 2022 | Meta | Sinhala (sin_Sinh) supported source & target | CC-BY-NC-4.0 | Yes (non-commercial) |
| SeamlessM4T v2 [S] | 2023 | Meta | Sinhala text supported | CC-BY-NC-4.0 | Yes (non-commercial) |
| **mDeBERTa-v3-base** [S] | 2021 | Microsoft | trained on CC100, Sinhala included | MIT | Yes |
| sinhala-instruct (ihalage) [S] | 2024 | Ihalage | **214k QA + 10k summ pairs** | open | Yes (SFT data) |
| iCIIT SinhaLM Gemma-3-4B FT [S] | 2025 | iCIIT | Gemma-3-4B instruct-tuned on Sinhala | Gemma | Yes (newest chat) |
| NSINA-Headlines mt5/mbart [F] | 2024 | Sinhala-NLP | summarisation / headline gen | open | Partial |

## 2.3 Tools, tokenizers, OCR

| Resource | Year | Maintainer | Capability | License | Usable? |
|---|---|---|---|---|---|
| sinling [F] | 2018–2020 | ysenarath | tokenizer, stemmer, POS, joiner/splitter; **last release Nov 2020 (stale)** | MIT | Yes (with caveats) |
| **SLTK / sltkpy** [F] | 2025 | Buddhilive | Grapheme-Pair-Encoding tokenizer, v1.0.0 Mar 2025 | MIT | Yes |
| **Aksharamukha** [F] | 2018+ | Vinodh Rajan | Sinhala ↔ 121 scripts incl. IAST/Devanagari | MIT | **Yes — critical for our Sanskrit bridge** |
| indic-transliteration [S] | rolling | sanskrit-coders | Sinhala in Sanscript scheme | MIT | Yes |
| polyglot (Sinhala) [S] | 2014+ | aboSamoor | tokeniser, NER, transliteration | GPL-3 | Partial |
| SinMorphy [S] | 2021 | NLPC-UoM | Foma/lexc rule-based morph analyser+synth | open | Yes |
| BiGRU morph (deep) [S] | 2023 | Lakmali et al. | 644k entries, **87.96% acc** | research code | Partial |
| Sinhala-Stopword-list [S] | 2020 | nlpcuom | stopword list | open | Yes |
| sinhala-para-dict [S] | 2023 | kasunw22 | EN-SI parallel word dict + stop words | MIT | Yes |
| fastText langid (lid.176) [S] | 2017 | Meta | recognises Sinhala | MIT | Yes |
| fastText Sinhala vectors [S] | 2018 | Meta | 300-d CBOW, CC+Wiki | CC-BY-SA-3.0 | Yes |
| Subasa OCR [S] | 2020 | LSF/community | fine-tuned Tesseract 4 for Sinhala | open | Inferior to Surya |
| Tesseract 5 (sin) [S] | 2024 | community | beats Subasa per 2025 zero-shot study | Apache-2.0 | Yes |
| **Surya OCR** [S] | 2024 | VikParuchuri | **2.61% WER, 0.76% CER on Sinhala — best in class** | GPL-3 / commercial | **Yes — replace GCV** |
| Google Cloud Vision Sinhala [S] | rolling | Google | strong baseline, our current pipeline | proprietary | Yes |
| Google Document AI [S] | rolling | Google | used by SiDiaC, SiPaKosa | proprietary | Yes |
| EasyOCR (sin) [S] | 2021 | JaidedAI | supports Sinhala | Apache-2.0 | Partial |

## 2.4 Task-specific datasets

| Resource | Year | Size / coverage | Usable? |
|---|---|---|---|
| **suralk/multiNER** [F] | 2025 | **EN-SI-TA parallel NER**, CoNLL-03 tagset (PER/LOC/ORG/MISC), BIO; CC0 | Yes (no medical entities) |
| asanka25 CoNLL Sinhala [S] | 2020 | toy CoNLL Sinhala | Partial |
| 70k-token fine-grained CRF NER [S] | 2020 | 70k tokens, fine-grained tags (release unclear) | Partial |
| UD_Sinhala-STB [F] | 2022 | **100 sents / 880 tokens** | Yes (tiny) |
| Sinhala-News-Comments sentiment [S] | 2021 | 15,059 comments, 4-class | Yes |
| sinhala-sentiment-analysis (HF) [F] | 2024 | 9.05k | Yes |
| **SOLD** [S] | 2022/24 | **10k tweets + SemiSOLD 145k** | Yes |
| XL-Sum (Sinhala) [S] | 2021 | 3,414 BBC Sinhala doc/summary pairs | Yes |
| M3LS (Sinhala) [S] | 2023 | 10,148 doc/summary pairs | Yes |
| Sinhala QA 1k (Mahoshadha) [S] | 2024 | 1k QA + EN translations | Partial |
| **ihalage SIF** [S] | 2024 | 214,485 QA + 10k summ for instruction-tuning | Yes |
| OpenSLR-52 Sinhala ASR [F] | 2018 | 224 hr, 478 speakers, ~14.6 GB | Out of scope |
| OpenSLR-30 Sinhala TTS [S] | 2018 | multi-speaker TTS | Out of scope |
| Sinhala PIQA [S] | 2026 | physical-commonsense MCQ | No (commonsense not pharma) |

## 2.5 Benchmarks and shared tasks

| Resource | Year | Coverage | Notes |
|---|---|---|---|
| **SinhalaMMLU** [F] | 2025 (EMNLP) | **>7,000 MCQs, 30 subjects, 6 domains, native SL curriculum** | Eval only; Claude 3.5 Sonnet leads @ 67% |
| Sinhala MathReason [S] | 2026 | math reasoning eval | Eval only |
| Script-Sensitivity Bench [S] | 2026 | Unicode vs Romanised vs mixed | No |
| WMT19 PCF si-en [S] | 2019 | parallel-corpus-filtering | Partial |
| **SinhalaGLUE** | — | **DOES NOT EXIST** | — |

## 2.6 Lexical resources

| Resource | Year | Coverage | Notes |
|---|---|---|---|
| Sinhala WordNet (UCSC) [S] | 2013 | ~1,000 senses; never full | Partial |
| **IndoWordNet — Sinhala absent** [S] | 2010+ | Confirmed gap | — |
| Carter Sinhalese–English [S] | 1924 digitised | full dictionary at DSAL Chicago | Yes (Ayurveda-relevant terms) |
| Clough Sinhalese–English [S] | 1892 digitised | full dictionary | Yes |
| Geiger Sinhalese grammar [S] | 1897/1941 | etymology + grammar | Yes (historical) |
| Madura English-Sinhala online [S] | rolling | bilingual lookup | Partial |
| Sinhala Dictionary Office gov.lk [S] | rolling | official lexicon | Yes |
| nlpcuom Sinhala stopword list [S] | 2020 | function-word list | Yes |
| fastText Sinhala 300-d [S] | 2018 | CC+Wiki word vectors | Yes |

## 2.7 What genuinely does NOT exist (state confidently as gaps)

1. **No Sinhala medical / Ayurvedic / pharmacopoeia corpus** of any
   size — this project is filling a documented hole. SiPaKosa
   (Buddhist) is the closest classical register.
2. **No Sinhala in IndicBERT, IndicTrans2, MuRIL, BPCC** — the
   AI4Bharat ecosystem entirely excludes Sinhala (it is not a
   "scheduled language of India").
3. **No SinhalaGLUE-style consolidated NLU benchmark** — SinhalaMMLU
   (Sep 2025) is the first multi-domain benchmark but is MCQ-only.
4. **No production-grade Sinhala WordNet** — UCSC effort stopped at
   ~1,000 senses.
5. **No Sinhala dependency treebank beyond 100 sentences / 880 tokens**
   (UD-STB). Anything trained on it overfits.
6. **No Sinhala–Sanskrit / Sinhala–Pali aligned lexicon** beyond the
   small 28.4k pali-sinhala HF set; no sense alignment.
7. **No fine-grained Sinhala NER beyond CoNLL-03 (PER/LOC/ORG/MISC)** —
   no biomedical, no botanical, no chemical NER.
8. **No Sinhala-specific instruction-tuned chat model with verified
   quantitative reasoning** — SinLlama is base; iCIIT SinhaLM Gemma-3-
   4B-FT is the newest instruct but unbenchmarked on knowledge tasks.

## 2.8 Surprises (resources we under-leveraged)

1. **SiPaKosa (786k sents / 9.25 M words Sinhala-Pali Buddhist)** —
   2026 release using **Google Document AI**, exactly our OCR stack.
   Register closer to Ayurvedic śāstra than NSINA news.
2. **SiDiaC v2** — explicit diachronic annotation by written date
   across 1,500 years. For dating an Ayurvedic pharmacopoeia entry's
   linguistic stratum, this is directly relevant prior art we have
   not cited.
3. **Surya OCR beats Subasa AND Tesseract on Sinhala** (WER 2.61%);
   beat GCV in the 2025 zero-shot study. We are paying for GCV; a
   free local OCR may equal or beat it.
4. **Aksharamukha as a Python package** — gives lossless Sinhala ↔
   Devanagari ↔ IAST in one pip install. We are already using it; flag
   it as the most reliable single dependency we have.
5. **`pali-sinhala` HF dataset (28.4k pairs, 2025)** — small but free
   Pali-Sinhala alignment; useful for tatsama-vs-tadbhava
   disambiguation in formula names.
6. **ihalage/sinhala-instruction-finetune-large** — 214k QA pairs in
   HF for instruction-tuning SinLlama; closer to "drop-in SFT data"
   than anything else.

---

# Part III — Per-task SOTA + research history

## 3.1 Timeline narrative (2014–2026)

**2014–2018 — foundations (rule-based, statistical, first corpora).**
Welgama, Herath and colleagues at **UCSC's Language Technology Research
Lab** (founded 2004 under Ruvan Weerasinghe) produce the first Sinhala
POS taggers using HMMs and morphology rules. Wijesiri et al. publish
"Building a WordNet for Sinhala" at GWC 2014. The **UoM CSE group**
(Gihan Dias, Surangika Ranathunga) standardises a 30-tag POS tagset
and an SVM tagger (**Fernando, Ranathunga, Jayasena, Dias, 2016,
84.7% acc**). **Si-Ta** (Ranathunga et al., 2018) is the first SMT
system for Sinhala ↔ Tamil official documents. Dahanayaka &
Weerasinghe and Manamini et al. (Ananya) build the first CRF-based
Sinhala NER systems.

**2018–2021 — neural turn and parallel corpora.** Facebook releases
fastText vectors for Sinhala; **Lakmal, Ranathunga et al. (LREC 2020)**
publish a systematic intrinsic+extrinsic evaluation showing 300-dim
fastText beats Word2Vec and GloVe — the canonical "use fastText for
Sinhala" result. **FLORES-101** (Guzmán et al., FAIR, 2019) puts
Sinhala-English on the global low-resource MT map. **Senevirathne,
Demotte et al. (2020)** push Sinhala sentiment to **F1 = 84.58%** with
3-layer BiLSTM, beating capsule networks (82.04%). Thillainathan &
Ranathunga (2021) demonstrate that fine-tuning mBART/mT5 beats from-
scratch Transformer NMT for Sinhala-English.

**2021–2024 — XLM-R / SinBERT era.** **Dhananjaya, Demotte, Ranathunga
& Jayasena ("BERTifying Sinhala", LREC 2022)** train SinBERT-small and
SinBERT-large (RoBERTa monolingual), and crucially benchmark XLM-R,
LaBSE, LASER, and SinBERT across sentiment, news category, news source
and writing-style classification — **XLM-R emerges as the dominant
Sinhala model on most tasks**. **Ranasinghe (Lancaster), de Silva,
Ranathunga** publish **SOLD** (10k tweets) + SemiSOLD (145k),
establishing offensive-language SOTA at Macro F1 = 0.83 (XLM-R,
sentence-level) and 0.81 (SinBERT, token-level). Liyanage, Sarveswaran
et al. (UDW 2023) release **UD_Sinhala-STB** — the first UD treebank
for Sinhala (100 sentences). NLLB-200 (Meta, 2022) and IndicTrans2
(AI4Bharat, 2023) integrate Sinhala despite Sinhala not being an
Indian scheduled language. Azeez & Ranathunga (2020) extend NER from
coarse to fine-grained tags.

**2024–2026 — decoder LLMs, native benchmarks, domain corpora.** The
Moratuwa group (Aravinda, Sirajudeen, Karunathilake, de Silva,
Ranathunga, Kaur, **arXiv:2508.09115, Aug 2025**) release **SinLlama**,
the first decoder LLM with explicit Sinhala support — continual
pre-training of Llama-3-8B on 10M Sinhala sentences with vocabulary
extension, beating Llama-3-8B base and instruct on three classification
tasks. **SinhalaMMLU** (Pramodya, Nelki, Liyanage, Pushpananda,
Weerasinghe et al., EMNLP 2025) introduces the first native-curriculum
(not translated) 7,000-question MCQA benchmark; Claude 3.5 Sonnet
leads at 67%, GPT-4o at 62%, with humanities collapsing model
performance. **Surya OCR** (Jayatilleke & de Silva, arXiv:2507.18264,
Jul 2025) is benchmarked zero-shot on a 6,969-pair synthetic dataset,
achieving CER 0.76% / WER 2.61% — comfortably beating Tesseract,
Subasa, Cloud Vision and Document AI. **SiPaKosa** (2026,
arXiv:2603.29221) releases 9.25M-word Sinhala+Pali Buddhist corpus;
**SinhaLegal** (arXiv:2603.04854) releases 2M words of Sri Lankan
Acts/Bills.

## 3.2 Per-task SOTA

| Task | SOTA method | SOTA number | Dataset | Year | Paper |
|---|---|---|---|---|---|
| OCR (printed) | **Surya** (zero-shot) | **CER 0.76 % · WER 2.61 %** | sinhala_synthetic_ocr-large (6,969 pairs) | 2025 | Jayatilleke & de Silva, arXiv:2507.18264 |
| POS tagging | SVM (Fernando et al.); BiLSTM+fastText combos | 84.68 % overall (SVM); HMM >90 % on known-words | UCSC POS, 30-tag set | 2016 | Fernando, Ranathunga, Jayasena, Dias, WSSANLP 2016 |
| NER (coarse) | XLM-R fine-tuned on multiNER | "new benchmark" F1 — outperforms BiLSTM-CRF | multiNER (parallel EN-TA-SI) | 2024 | Ranathunga et al., arXiv:2412.02056 |
| Dependency parsing | UD parsers on UD-Sinhala-STB | treebank-only (100 sents); no robust SOTA published | UD-Sinhala-STB | 2023 | Liyanage, Sarveswaran et al., UDW 2023 |
| MT Si → En | NLLB-200 / IndicTrans2 | IndicTrans2 +1–5 BLEU over baselines on FLORES-200 | FLORES-200 devtest | 2023 | Gala et al., arXiv:2305.16307 |
| MT Si ↔ Ta | NMT + synthetic + POS/morph | +2.16 BLEU Si→Ta · +5.00 BLEU Ta→Si | Si-Ta gov-doc corpus | 2019 | Tennage, Ranathunga et al. |
| Sentiment (doc) | 3-layer BiLSTM | **F1 = 84.58 %** (beats Capsule-B 82.04 %) | Sinhala news comments | 2020 | Senevirathne et al., arXiv:2011.07280 |
| Offensive (sentence) | XLM-R + Hindi transfer | **Macro F1 = 0.83** | SOLD | 2024 | Ranasinghe et al., LREC J |
| Offensive (token) | SinBERT | **Macro F1 = 0.81** | SOLD | 2024 | same |
| Text classification (multi-task) | XLM-R / SinBERT-large | XLM-R best on most; SinBERT-large competitive | news-cat, news-source, writing-style, sentiment | 2022 | Dhananjaya et al., LREC 2022 ("BERTifying Sinhala") |
| Summarization | mT5 fine-tuned on XL-Sum | best ROUGE-1 / ROUGE-L (exact Si values not surfaced); XL-Sum ≥11 ROUGE-2 on 10 langs | XL-Sum (3,414 Si), M3LS (10,148) | 2021 | Hasan et al., ACL 2021 |
| MCQA / multitask LLM eval | Claude 3.5 Sonnet (zero/few-shot) | **67 % avg** (GPT-4o 62 %) | SinhalaMMLU (7k Q, 30 subj) | 2025 | Pramodya et al., EMNLP 2025 |
| Generative LLM (Sinhala) | SinLlama (Llama-3-8B + 10M-sent CPT) | "significant gains" over Llama-3-8B on 3 classification tasks (numbers not in abstract) | News / sentiment classification | 2025 | Aravinda et al., arXiv:2508.09115 |
| Word embeddings | fastText 300-d | best intrinsic+extrinsic across analogy / relatedness / sentiment / POS | 27,382 analogies + 345 relatedness pairs | 2020 | Lakmal et al., LREC 2020 |
| QA / RC | BERT-base-sinhala-qa (translated SQuAD) | HF model card only; no rigorous EM/F1 | Translated SQuAD 8k | 2022 | sankhajay/bert-base-sinhala-qa |
| ASR | Fine-tuned Whisper-small | Community fine-tunes; no published Si SOTA WER | Mozilla CommonVoice 11.0 Si | 2023+ | Lingalingeswaran (HF) |

**Inconsistencies flagged**: POS accuracy varies across tagsets (30-tag
SVM vs older HMM tagsets); XL-Sum Sinhala ROUGE numbers do not surface
in snippets; NER F1 was not reported in the multiNER abstract; absolute
Si-En FLORES BLEU for NLLB / IndicTrans2 was not surfaced in fetches.
**Numbers from [S] sources should be re-verified before citing.**

## 3.3 Key researchers and groups

1. **Surangika Ranathunga** (Massey, formerly UoM CSE) — centre of
   mass of Sinhala NLP: MT, NER, POS, embeddings, SinLlama co-supervisor.
2. **Nisansa de Silva** (UoM CSE) — *Survey on Publicly Available
   Sinhala NLP Tools and Research* (arXiv:1906.02358, updated to 2024);
   WordNet, Surya benchmark, SinLlama.
3. **Gihan Dias** (UoM CSE) — POS tagset, morphology, SinMorphy.
4. **Tharindu Ranasinghe** (Lancaster, UK) — SOLD/SemiSOLD;
   international diaspora hub for Sinhala NLP.
5. **Ruvan Weerasinghe / Chamila Liyanage / Randil Pushpananda**
   (UCSC LTRL) — POS, dependency treebank, SinhalaMMLU, TTS, speech
   corpora.
6. **Hakim Usoof** (Univ Peradeniya, Stats & CS) — sentiment of news
   comments; recent transformer work.
7. **AI4Bharat** (IIT Madras) + **Meta FAIR / NLLB team** — although
   Sinhala is not an Indian scheduled language and is excluded from
   IndicTrans2's core 22, both groups include Sinhala via FLORES; de
   facto custodians of multilingual MT baselines.
8. **Nevidu Jayatilleke** (UoM, with de Silva) — Surya OCR benchmark.

## 3.4 Strategic positioning for the Pharmacopoeia project

1. **Sinhala NLP is almost entirely news / social-media domain.**
   Sentiment (news comments), classification (news source/category),
   hate speech (tweets), and summarization (BBC) dominate; SOLD,
   XL-Sum, SinBERT training data, and SinLlama instruction-tuning all
   sit on news/Twitter. **No published medical or Ayurvedic Sinhala
   NLP exists** — the only adjacent work is SiPaKosa (Buddhist
   canonical) and SinhaLegal. Our pharmacopoeia work is essentially
   the **first Sinhala domain NLP project in traditional medicine**,
   giving a defensible novelty claim.

2. **Classical / specialist-register Sinhala is unaddressed.**
   UD-Sinhala-STB is contemporary, only 100 sents; existing taggers
   and embeddings are trained on news. Ayurvedic text mixes Sinhala
   with Sanskrit/Pali tatsama and dense unit terminology — a register
   no existing model has seen. This justifies our custom resolver
   stack rather than relying on SinBERT / SinLlama for entity
   normalisation. Our Sanskrit-bridge resolver (Monier-Williams, 73 %
   coverage on tatsama types) directly exploits a gap nobody has
   addressed.

3. **OCR is solved for clean print; not for our document.** Surya's
   0.76 % CER is on a *synthetic* dataset with five Noto-family fonts.
   Real Sri Lankan pharmacopoeia print uses non-Unicode legacy fonts
   and tabular layout. Our PDF-direct extraction (`pdf_pipeline/`) is
   well-justified as bypassing OCR error entirely; Surya should still
   be piloted but is not guaranteed to match its benchmark numbers on
   our scans.

4. **Decoder LLMs (SinLlama) and native MCQA (SinhalaMMLU) define the
   new frontier but don't help with structured extraction.**
   SinhalaMMLU shows even Claude 3.5 only reaches 67 % on Sinhala
   curriculum MCQs; **humanities collapsed performance** — exactly the
   register of Ayurvedic text. LLM-only approaches to structured
   extraction from Ayurvedic text will inherit this weakness. This
   motivates our rule + state-machine + resolver hybrid over an
   end-to-end LLM pipeline.

5. **Baselines to position against**: XLM-R (text classification),
   SinBERT (Sinhala-specific), and SinLlama (decoder LLM). For
   ingredient/formula extraction we should report against an LLM
   baseline (SinLlama or GPT-4o few-shot) to make the case
   quantitatively. For terminology KG work, cite de Silva's WordNet
   and the SiPaKosa lineage as the only prior Sinhala lexical-KG work.

## 3.5 Surveys to cite

- **de Silva, N. (2019, rev. May 2024).** *Survey on Publicly Available
  Sinhala NLP Tools and Research.* arXiv:1906.02358 — the canonical
  Sinhala NLP survey, repeatedly updated.
- **Ranathunga, S. & de Silva, N.** *Some Languages Are More Equal than
  Others: Probing Deeper into the Linguistic Disparity in the NLP
  World.* AACL-IJCNLP 2022 — headline positioning paper for Sinhala as
  a disadvantaged language.

---

# Part IV — What this means for our project

## 4.1 Confirmed novelty claims (state confidently)

1. **First Sinhala NLP project in traditional medicine / Ayurveda** —
   no published medical-Sinhala NLP exists. SiPaKosa (Buddhist) and
   SinhaLegal (legal) are the only adjacent specialist-register
   Sinhala NLP projects.
2. **First Sinhala → Sanskrit deterministic lexical bridge** — no
   computational tatsama / tadbhava / deśya classifier exists in the
   literature. Module A's Mishra-Sinhala signal (aspirates / sibilants
   / vocalic-r / word-initial cluster) is the first formal computational
   description of this distinction.
3. **First KG of traditional Sri Lankan medicine** — GRAYU and
   AyurKOSH cover Indian Ayurveda generally; no Sri-Lankan-specific
   resource exists.
4. **First structured digitisation of the Sri Lankan Ayurvedic
   Pharmacopoeia** — no machine-readable form exists.

## 4.2 Methodological choices justified by the landscape

- **Rule + state-machine + resolver hybrid, not end-to-end LLM** —
  justified by SinhalaMMLU's evidence that Claude 3.5 hits only 67 %
  on Sinhala MCQs, with humanities collapsed. Determinism matters more
  here than recall.
- **Custom closed-vocabulary lexicons (materia_medica, pratinidhi,
  mahā-kaṣāya, units)** — justified because no Sinhala medical NER
  corpus exists; we are bootstrapping the lexicons from the source itself.
- **Aksharamukha for Sinhala ↔ IAST transliteration** — justified as
  the only tool with proper Sinhala-specific orthographic handling
  across 121 scripts.
- **PDF-direct text extraction (`pdf_pipeline/`)** — justified by the
  documented IskoolaPota / legacy-font OCR-decoding failures and the
  fact that Surya's benchmark numbers are on synthetic clean print.
- **XLM-R / SinBERT as the second-oracle backbone** — justified by
  Dhananjaya et al.'s "BERTifying Sinhala" benchmark showing XLM-R as
  the dominant Sinhala model across multiple tasks.

## 4.3 New resources to integrate

| Priority | Resource | What it gives us |
|---|---|---|
| **P1** | **SiPaKosa** (786k sents, 9.25 M words) | Closest classical-register Sinhala corpus; pretraining adaptation for the resolver |
| **P1** | **Surya OCR** | Pilot against GCV on real pharmacopoeia scans |
| **P2** | **Aksharamukha Python package** | Already in use — flag as critical-dependency |
| **P2** | **`pali-sinhala` HF dataset** | 28.4k pairs for tatsama-vs-tadbhava disambiguation in formula names |
| **P2** | **SiDiaC** | Diachronic anchoring of pharmacopoeia entries to linguistic-strata centuries |
| **P3** | **Carter / Clough / Geiger digitised dictionaries** | Historical lexica for tadbhava / vernacular ingredients |
| **P3** | **multiNER (CC0)** | Distant-supervision warm-start for NER (news-domain, transfer only) |
| **P3** | **ihalage SIF (214k Sinhala QA)** | Future SFT data if we instruction-tune SinLlama |
| **P3** | **fastText Sinhala 300-d** | Embedding fallback for the resolver's residual unresolved bucket |

## 4.4 Documented gaps the project addresses

These are the **stateable, citable gaps** we should put in the
proposal's "Why this work matters":

- No Sinhala medical / Ayurvedic NER corpus or model
- No Sinhala dependency treebank beyond 100 sentences / 880 tokens
- No Sinhala-specific instruction-tuned chat model with verified
  domain reasoning ability
- Sinhala is absent from IndoWordNet, IndicBERT, IndicTrans2, MuRIL,
  BPCC (entire AI4Bharat ecosystem)
- No production-grade Sinhala WordNet (~1,000 senses only)
- No Sinhala → Sanskrit / Pali aligned sense lexicon at scale
- No published computational tatsama / tadbhava classifier

Each of these is a positionable contribution opportunity.

---

## Source provenance

The agent surveys this document distils were conducted via WebSearch +
WebFetch. **[F]-marked items are fetched primary sources;
[S]-marked items are search snippets only.** [S]-numbers in §3.2 should
be re-verified against the primary papers before citing in the thesis.
Key primary sources actually fetched:

- de Silva 2019/2024 Sinhala-NLP survey: arXiv:1906.02358
- BERTifying Sinhala (LREC 2022): arXiv:2208.07864
- SinLlama: arXiv:2508.09115
- SinhalaMMLU (EMNLP 2025): aclanthology.org/2025.emnlp-main.1673
- Surya zero-shot OCR for Sinhala/Tamil: arXiv:2507.18264
- multiNER: arXiv:2412.02056
- SiDiaC: arXiv:2509.17912
- SiPaKosa (preprint): arXiv:2603.29221
- UD-Sinhala-STB: universaldependencies.org/treebanks/si_stb
- AI4Bharat NLP catalogue: github.com/AI4Bharat/indicnlp_catalog
- Wikipedia: Sinhala_language, Sinhala-Maldivian_languages, Sinhala_script
- Richard Ishida W3C Sinhala notes: r12a.github.io/scripts/sinh/si.html
- Aksharamukha: github.com/virtualvinodh/aksharamukha
- SLTK: github.com/buddhilive/sltk

# Research Proposal

## Bootstrapping a Domain Knowledge Graph from Structured OCR to Enable Information Extraction in Unstructured Sinhala Ayurvedic Manuscripts

**Domain**: Natural Language Processing / Information Extraction
**Language**: Sinhala (ISO 639-1: si) — low-resource, morphologically rich
**Corpus**: Sri Lankan Ayurvedic Pharmacopoeia, Volumes I–III

---

## 1. Problem Statement

Sinhala is one of the world's most under-resourced languages for NLP. No large pretrained Sinhala language model exists. There is no published NER benchmark for Sinhala. The language is agglutinative and morphologically rich, making tokenization itself an open research problem.

The Sri Lankan Ayurvedic Pharmacopoeia is an authoritative multi-volume reference for traditional herbal medicine, written entirely in Sinhala. It exists only as a physical book. No digital, searchable, or queryable form of this knowledge exists.

**The research opportunity**: Volume I of the pharmacopoeia has a strongly structured layout (column-delimited tabular entries). This structure makes automated extraction tractable. Volumes II and III follow the same column format and can be processed with the same pipeline. Other traditional medicine manuscripts in this domain use paragraph-level prose — a harder extraction problem.

**The research claim**:

> A knowledge graph constructed from structured Volumes I–III can serve as a grounding resource to enable accurate entity and relation extraction from unstructured paragraph-level traditional medicine texts, without requiring large labeled corpora — by exploiting domain-closed vocabulary, ingredient co-occurrence priors, and structural transfer.

This is a measurable, falsifiable claim testable through controlled experiments comparing KG-grounded extraction against non-KG baselines at each phase of corpus growth.

---

## 2. Why This is Novel

This work sits at the intersection of five research areas, none of which covers this combination:

| Area | Prior Work | Gap |
|---|---|---|
| Sinhala NLP | Fernando et al. (2021) word embeddings; Dhananjaya & Kodikara (2012) morphological analyzer | Pre-transformer era; no NER corpus; no domain-specific work |
| Low-resource NER | mBERT, XLM-RoBERTa, MAD-X adapters | Assumes labeled corpus exists; does not address corpus construction |
| Historical document IE | Ehrmann et al. (2023) survey (newspapers, legal) | No Sinhala; no traditional medicine; no structured→unstructured transfer |
| Traditional medicine NLP | AyurNLP (IIIT Hyderabad, Sanskrit) | Different language; no KG construction; no volume-to-volume transfer |
| KG from low-resource text | Shi & Weninger (2018) open KG | General domain; does not model domain-closed vocabulary bootstrapping |

**This research is the first work to:**
1. Construct a labeled NER corpus for Sinhala domain-specific text
2. Build a knowledge graph for traditional Sri Lankan medicine
3. Empirically measure how KG enrichment from structured sources affects NER F1 on unstructured text
4. Demonstrate a progressive bootstrapping methodology applicable to other low-resource manuscript digitization projects

---

## 3. Corpus

### Volume I (digitized, this repository)
- **Format**: Structured tabular layout — column zones determine token role
- **Size**: 707 formula entries, pages 172–443
- **Fields per entry**: Formula name, ingredient list (avg 15.8 ingredients), preparation method, usage/indication, adjuvant, dosage, notes
- **Tokens**: 62,562 total; 7,100 unique types
- **Status**: Fully extracted; NLP statistics computed; ready for annotation

### Volumes II and III (physical, in hand)
- **Format**: Same structured tabular layout as Volume I
- **Estimated size**: ~800–1,200 formulas per volume
- **Plan**: Scan with Google Cloud Vision (same OCR pipeline); run same extraction pipeline with minor threshold tuning
- **Expected output**: ~2,000–2,500 additional structured entries

### Other traditional medicine manuscripts (future)
- **Format**: Paragraph-level prose
- **Plan**: OCR + KG-grounded extraction (the core Phase 3 research problem)

---

## 4. Research Questions

**RQ1**: What entity types are present in Sinhala Ayurvedic text, and what annotation schema best captures the domain structure?

**RQ2**: How accurately can a CRF and a fine-tuned multilingual transformer (XLM-RoBERTa) extract entities from structured Sinhala Ayurvedic text when trained on the labeled Vol I corpus?

**RQ3**: Does KG-grounded extraction outperform non-KG baselines on paragraph-level text from the same domain? By how much?

**RQ4**: Does expanding the KG from Vol I alone (707 formulas) to Vol I+II+III (~2,500+ formulas) measurably improve NER F1 on unseen paragraph-level text? What is the shape of this improvement curve?

---

## 5. Technical Contributions

### Contribution 1 — Labeled NER Corpus
- Annotation schema: `INGREDIENT`, `FORMULA_NAME`, `QUANTITY`, `UNIT`, `INDICATION`, `PREPARATION_VERB`, `ADJUVANT`, `CROSS_REF`, `ARTEFACT`
- Inter-annotator agreement study (Cohen's κ ≥ 0.80 target)
- 707 labeled entries; publicly released as first Sinhala domain NER dataset

### Contribution 2 — Sinhala Ayurvedic Knowledge Graph
- Entity normalization: collapse ~2,637 ingredient surface forms → ~300 canonical nodes using edit-distance + embedding hybrid
- Relation types: `CONTAINS`, `TREATS`, `REFERENCES`, `CO_OCCURS`, `TYPE`, `DOSED_WITH`
- ~15,000+ edges from Vol I alone; grows with each additional volume
- Graph analysis: centrality, ingredient clustering, formula similarity network

### Contribution 3 — NER Models for Structured Sinhala Text
- CRF with Sinhala morphological features (character n-grams, suffix patterns, column position)
- XLM-RoBERTa fine-tuned on labeled corpus
- KG-augmented NER: entity candidates from KG as soft constraints during inference
- Full ablation study: features, model size, KG inclusion

### Contribution 4 — KG-Grounded Transfer to Unstructured Text
- Three-way comparison: (a) gazetteer baseline, (b) KG-constrained CRF, (c) RAG + LLM using KG entries as retrieved context
- Controlled experiment: KG built from Vol I only vs. Vol I+II+III
- Evaluation on manually annotated paragraph samples from held-out traditional manuscripts

### Contribution 5 — End-to-End Pipeline
- Physical book → structured KG entry, fully automated except OCR scanning
- Reusable for other Sinhala manuscripts and other low-resource historical document domains
- All code, data, and models released publicly

---

## 6. Methodology

### Phase 1: Corpus Construction and Annotation (Months 1–4)

1. Finalize annotation schema through pilot annotation of 50 entries
2. Annotate 707 Vol I entries at token level (estimated 24 hours)
3. Compute inter-annotator agreement on 10% double-annotated subset
4. Build Vol I knowledge graph: entity normalization + relation extraction
5. Baseline NLP statistics: vocabulary, Zipf distribution, field fill rates, artefact rate

### Phase 2: Structured Extraction — Vol II and III (Months 4–6)

1. Scan physical Volumes II and III with GCV
2. Run existing extraction pipeline; measure transfer quality against Vol I baseline
3. Tune column boundary thresholds if volumes use different layouts
4. Feed Vol II+III into KG; measure KG growth (new entity types, new relation instances)
5. **Key measurement**: what fraction of Vol II+III ingredients were already in the Vol I KG?

### Phase 3: NER Model Training and Evaluation (Months 5–8)

1. Train CRF on 80% of labeled Vol I corpus; evaluate on 20% held out
2. Fine-tune XLM-RoBERTa on same split
3. Add KG entity candidate features; re-evaluate both models
4. Full ablation: remove each feature group; measure F1 impact

### Phase 4: Transfer to Paragraph Text (Months 7–10)

1. Identify and scan 2–3 traditional medicine manuscripts with paragraph structure
2. Manually annotate 50 paragraphs (~300–500 entity mentions) as gold standard
3. Run three extraction systems (gazetteer, KG-CRF, RAG+LLM) against gold standard
4. Repeat with KG built from Vol I only vs. Vol I+II+III
5. Analyze error types: novel entities, morphological variation, OCR noise

### Phase 5: Evaluation, Analysis, Writing (Months 9–12)

1. Full pipeline benchmark: physical page → KG entry, measure end-to-end precision/recall
2. Error analysis: which entity types benefit most from KG grounding?
3. Extensibility analysis: what does adding more volumes do to downstream performance?
4. Writing and submission

---

## 7. Evaluation Plan

| Component | Metric | Target |
|---|---|---|
| NER (structured text) | F1 per entity type, micro/macro avg | F1 > 0.80 |
| KG entity normalization | Precision@1 on held-out ingredient variants | > 0.85 |
| KG relation extraction | Precision / Recall for CONTAINS, TREATS | > 0.80 |
| Transfer to paragraph text | F1 on gold-annotated paragraph sample | Report and analyze |
| KG enrichment effect | ΔF1 (Vol I KG) vs (Vol I+II+III KG) | Positive; quantify |
| End-to-end pipeline | % of entities resolved to KG nodes | Report |

---

## 8. Timeline

| Month | Milestone |
|---|---|
| 1 | Annotation schema finalized; pilot annotation complete |
| 2–3 | 707 Vol I entries labeled; KG Phase 1 built |
| 4 | Vol I KG complete; NER CRF baseline trained |
| 5 | Vol II scanned, OCR'd, extracted; KG enriched |
| 6 | Vol III scanned, OCR'd, extracted; KG enriched; XLM-RoBERTa trained |
| 7–8 | Paragraph text OCR + gold annotation; transfer experiments |
| 9–10 | Ablation studies; full evaluation; error analysis |
| 11–12 | Writing and submission |

---

## 9. Expected Publications

1. **Resource paper** — "A Labeled NER Corpus and Knowledge Graph for Sinhala Ayurvedic Medicine" → ACL/EMNLP Findings or LREC-COLING
2. **Methods paper** — "KG-Grounded Entity Extraction for Low-Resource Historical Manuscripts: A Structured-to-Unstructured Transfer Approach" → ACL/NAACL or EMNLP

---

## 10. Current Progress

- [x] OCR pipeline built and validated (Google Cloud Vision batch)
- [x] Row extraction algorithm (`shrink_ocr_v4.py`)
- [x] Structured extraction state machine (`extract_pharma_v4.py`)
- [x] 707 Vol I formulas extracted and validated
- [x] NLP statistics report computed
- [x] Repository structure established
- [ ] Annotation schema — in design
- [ ] Knowledge graph construction — planned next
- [ ] Vol II / III scanning — pending physical access

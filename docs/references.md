# Bibliography

References for the project. BibTeX machine-readable version in
[`references.bib`](references.bib). Compiled May 2026.

---

## Comparable knowledge graphs

- **GRAYU** — Joshi, S., Pathak, A., Regati, D.R., Menon, R. et al.
  (2026). *GRAYU: graph-based database integrating Ayurvedic
  formulations, medicinal plants, phytochemicals and diseases.*
  Frontiers in Pharmacology, 16: 1727224.
  [link](https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2025.1727224/full)
  · DOI: 10.3389/fphar.2025.1727224
  — 157 K nodes / 1.52 M relationships across Plant, Phytochemical,
    Disease, Formulation. Provides the 4-node model adopted in our
    schema v1.

- **AyurKOSH** — Mirasdar, S., Bedekar, M., Patankar, H. and Gujar, Y.
  (2026). *AyurKOSH Dataset: A Machine-Readable Ayurvedic Knowledge
  Resource for Knowledge Graph and Computational Intelligence.* IEEE
  Dataport.
  [link](https://dx.doi.org/10.21227/58ej-wz87)
  · DOI: 10.21227/58ej-wz87
  — Source of the Rasa/Guna/Virya/Vipaka/Karma pharmacological-property
    axes in our PharmacologicalProperty node type.

- **HerbKG** — Lin, X., Quan, Z., Wang, Z-J., Huang, H., Zeng, X.
  (2022). *HerbKG: Constructing a Herbal-Molecular Medicine Knowledge
  Graph Using a Two-Stage Framework Based on Deep Transfer Learning.*
  Frontiers in Genetics, 13: 799349.
  [link](https://www.frontiersin.org/journals/genetics/articles/10.3389/fgene.2022.799349/full)
  — Herb / Chemical / Disease / Gene typology with 53 K relations
    mined from 500 K PubMed abstracts; inspiration for our
    typed-entity-and-relation extraction pattern.

- **Āyurjñānam** — Terdalkar, H. (2023). *Āyurjñānam: Exploring
  Āyurveda using Knowledge Graphs.* NYCIKS.
  [link](https://hrishikeshrt.github.io/publication/nyciks2023/abstract.pdf)
  — Small (410 / 764) but careful OWL-based KG of the Dhanyavarga
    chapter; cited for showing that quality-focused small graphs are
    a valid alternative to large noisy ones.

- **Semantic Annotation and Querying Framework based on Semi-structured
  Ayurvedic Text** — Singhal, N. and Sharma, A. (2022). arXiv:2202.00216.
  [link](https://arxiv.org/abs/2202.00216)

---

## International standards

- **WHO ICD-11 Traditional Medicine Module 2 (TM2)** — released
  February 2025. 529 codes across 18 chapters, specifically for
  Ayurveda/Siddha/Unani.
  [link](https://icd.who.int/browse/2025-01/mms/en#1435254666)
  — Required external ID for every Disease node in our schema. This
    is the international standard for Ayurvedic disease classification.

- **India's roadmap for ICD-11 TM2 implementation** —
  Government of India, Ministry of AYUSH (2025). *International Journal
  of Ayurveda Research*, October 2025.
  [link](https://journals.lww.com/ijar/fulltext/2025/10000/india_s_roadmap_for_icd_11_tm2_implementation_.18.aspx)
  — Details on the 1 941 AYUSH morbidity codes mapped to ICD-11 TM2 via
    the NAMASTE Portal. We leverage this work rather than re-do it.

- **Plants of the World Online (POWO)** — Royal Botanic Gardens, Kew.
  [link](https://powo.science.kew.org/)
  — The taxonomic authority for plants worldwide; provides IPNI LSIDs.
    Required external ID for every Plant node in our schema.

- **ChEBI ontology** — Hastings, J., de Matos, P., Dekker, A. et al.
  (2013). *The ChEBI reference database and ontology for biologically
  relevant chemistry: enhancements for 2013.* Nucleic Acids Research,
  41(D1): D456–D463.
  [link](https://academic.oup.com/nar/article/41/D1/D456/1062873)
  — Optional external ID for Phytochemical and Mineral nodes.

---

## Tools

- **pykew** — Royal Botanic Gardens, Kew (2024). Python library for
  accessing Kew's data services.
  [GitHub](https://github.com/RBGKew/pykew)
  — Used in `enrichers/botanical_powo.py` to call POWO.

---

## Methods (schema-constrained extraction)

- **LLM-empowered knowledge graph construction: A survey** — Zhong, L.
  et al. (2025). arXiv:2510.20345.
  [link](https://arxiv.org/abs/2510.20345)
  — Establishes schema-constrained extraction as the dominant 2025
    paradigm.

- **RELATE: Relation Extraction in Biomedical Abstracts with LLMs and
  Ontology Constraints** — Li, W. et al. (2025). arXiv:2509.19057.
  [link](https://arxiv.org/abs/2509.19057)
  — Concrete method that aligns LLM extractions to ontology constraints;
    referenced in §9 of `kg_schema.md`.

- **ODKE+: Ontology-Guided Open-Domain Knowledge Extraction with LLMs**
  — Wang, B. et al. (2025). arXiv:2509.04696.
  [link](https://arxiv.org/abs/2509.04696)

- **Automated Construction of Medical Indicator Knowledge Graphs using
  Retrieval Augmented LLMs** — Chen, Y. et al. (2025). arXiv:2511.13526.
  [link](https://arxiv.org/abs/2511.13526)

- **From Chaos to Clarity: Schema-Constrained AI for Auditable
  Biomedical Evidence Extraction from Full-Text PDFs** (2025).
  arXiv:2601.14267.
  [link](https://arxiv.org/abs/2601.14267)
  — Articulates the "schema-constrained, auditable" paradigm adopted in
    §9 of `kg_schema.md`.

---

## How to use

For the MCS3306 proposal's §11 References block, run the BibTeX file
through any standard processor (`pandoc`, `biber`, BibLaTeX).

For the public README and supervisor-facing documents, link to this
annotated markdown.

All entries above have been verified against the original source page
where the URL is provided. Last verified: 2026-05-23.

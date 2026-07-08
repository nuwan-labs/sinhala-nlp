"""
Corpus profile deliverable (supervisor request): corpus statistics, a worked
example (original format + JSON), unique features (Sanskrit code-mixed Sinhala),
and knowledge-graph integration feasibility.

    python -m analysis.corpus_profile   ->  analysis/out/CORPUS_PROFILE.html

Every figure tagged COMPUTED (from the data/code) or ASSUMED/CITED (from the
literature).  Corpus = Pharmacopoeia formula section pp.172-443; yogamalawa
excluded from all corpus statistics.
"""
from __future__ import annotations
import json
from collections import Counter

from . import common as C
from . import figures as Fig
from .common import nfc
from .report import esc, table, img, HEAD


def compute():
    formulas = C.load_formulas("name")
    text = " ".join(C.formula_text(e) for e in formulas)
    toks = text.split()
    types = Counter(toks)
    hapax = sum(1 for _, n in types.items() if n == 1)
    fields = ["name", "constituents", "preparation", "indication", "dosage", "vehicle"]
    ftok = {f: 0 for f in fields}
    constit_lines = 0
    for e in formulas:
        d = C.formula_field_texts(e)
        for f in fields:
            ftok[f] += len(d[f].split())
        constit_lines += len(C.constituent_lines(e))
    presence = {f: sum(1 for e in formulas if C.formula_field_texts(e)[f].strip()) / len(formulas)
                for f in fields}
    ing = C.load_json("ingredients_lexicon.json")
    nam = C.load_json("names_lexicon.json")
    mm = C.load_json("materia_medica.json")["metadata"]["section_counts"]
    icd = C.load_json("indication_icd11_tm2.json")
    ue = C.load_json("unit_equivalences.json")
    ir = sum(1 for v in ing.values() if v.get("resolved"))
    nr = sum(1 for v in nam.values() if v.get("resolved"))
    return {
        "n_formulas": len(formulas), "n_formulas_np": len(C.load_formulas("name_page")),
        "tokens": len(toks), "types": len(types), "hapax": hapax,
        "hapax_pct": 100 * hapax / len(types), "ttr": len(types) / len(toks),
        "mean_tok": len(toks) / len(formulas),
        "constit_lines": constit_lines, "mean_constit": constit_lines / len(formulas),
        "codepoints_content": sum(len(C.formula_text(e)) for e in formulas),
        "codepoints_nonws": sum(1 for ch in text if not ch.isspace()),
        "bytes": len(text.encode("utf-8")),
        "graphemes": len(C.seg_graphemes(text)), "aksharas": len(C.seg_aksharas(text)),
        "zwj": text.count("‍"), "virama": text.count("්"),
        "bytes_per_word": len(text.encode("utf-8")) / len(toks),
        "bytes_per_cp": len(text.encode("utf-8")) / len(text),
        "field_tokens": ftok, "presence": presence,
        "plant": mm["plant"], "mineral": mm["mineral"], "animal": mm["animal_origin"],
        "units": len(ue.get("symbols", {})), "icd": len(icd),
        "ing_entries": len(ing), "ing_resolved": ir, "ing_pct": 100 * ir / len(ing),
        "name_entries": len(nam), "name_resolved": nr, "name_pct": 100 * nr / len(nam),
    }


def example_entry():
    formulas = C.load_formulas("name")
    e = [x for x in formulas if "භූනිම්බාදි" in (x.get(C.NAME) or "")][0]
    return e


def kg_report():
    return C.load_json.__self__ if False else json.load(
        open(C.ROOT / "knowledge_graph" / "build_report.json", encoding="utf-8"))


def build():
    s = compute()
    e = example_entry()
    kg = kg_report()
    page_img = Fig.rasterise_pages([236], zoom=1.6)
    P = []
    P.append(HEAD)
    P.append("<style>.sinhala{font-family:'Noto Sans Sinhala','Iskoola Pota',serif;"
             "font-size:1.05em;line-height:1.9}pre.sinhala{white-space:pre-wrap;"
             "background:#fbfbf7;border-color:#e0dccc}</style>")
    P.append("<h1>Corpus Profile: Sinhala Ayurvedic Formula Register</h1>")
    P.append("<p class='sub'>Supporting material for the proposal <i>Sublanguage Structure, "
             "Segmentation, and Extraction in Low-Resource Sinhala Ayurvedic Formula Text</i>. "
             "Source: Ayurveda Pharmacopoeia of Sri Lanka, Vol. I, formula section pp. 172-443. "
             "Every figure is tagged COMPUTED (from the data) or CITED (from the literature). "
             "Yogamalawa excluded from all statistics.</p>")

    # ---- 1. statistics ----
    P.append("<h2>1 · Corpus NLP statistics <span class='small'>(COMPUTED)</span></h2>")
    rows = [
        ["Distinct formulas", f"{s['n_formulas']:,}", "dedup by name; by name+page = %d (±1)" % s["n_formulas_np"]],
        ["Source pages", "172-443 (272 pages)", "structured formula section"],
        ["Running tokens (whitespace)", f"{s['tokens']:,}", "across the six fields"],
        ["Word types", f"{s['types']:,}", "distinct whitespace tokens"],
        ["Hapax legomena", f"{s['hapax']:,} ({s['hapax_pct']:.1f}%)", "types occurring once - an open, sparse vocabulary"],
        ["Type-token ratio", f"{s['ttr']:.3f}", "lexical variety"],
        ["Mean tokens / formula", f"{s['mean_tok']:.1f}", "formulas are short"],
        ["Ingredient rows", f"{s['constit_lines']:,}", "mean %.1f constituents per formula" % s["mean_constit"]],
        ["Codepoints (content / non-space)", f"{s['codepoints_content']:,} / {s['codepoints_nonws']:,}", "all fields / segmentable content"],
        ["UTF-8 bytes", f"{s['bytes']:,}", "storage cost"],
        ["Grapheme clusters / aksharas", f"{s['graphemes']:,} / {s['aksharas']:,}", "rendered units / orthographic syllables"],
        ["Conjunct joiners (ZWJ) / viramas", f"{s['zwj']:,} / {s['virama']:,}", "abugida conjunct formation"],
        ["Bytes per word / per codepoint", f"{s['bytes_per_word']:.1f} / {s['bytes_per_cp']:.2f}", "byte-level costs ~13x word-level"],
    ]
    P.append(table(["Statistic", "Value", "Note"], [[esc(a), esc(b), esc(c)] for a, b, c in rows], "wide"))

    P.append("<h3>Field composition</h3>")
    frows = []
    labels = {"name": "Name (yōga nāma)", "constituents": "Constituents (yōgaya)",
              "preparation": "Preparation (saṃskaraṇa)", "indication": "Indication (prayōga)",
              "dosage": "Dosage (mātrā)", "vehicle": "Vehicle / anupāna"}
    for f in ["name", "constituents", "preparation", "indication", "dosage", "vehicle"]:
        frows.append([labels[f], f"{s['field_tokens'][f]:,}", f"{100*s['presence'][f]:.0f}%"])
    P.append(table(["Field", "Tokens", "Present in"], frows))

    P.append("<h3>Reference lexicons (closed-vocabulary gazetteers)</h3>")
    P.append(table(["Resource", "Size"], [
        ["Plant names", f"{s['plant']}"], ["Minerals", f"{s['mineral']}"],
        ["Animal-origin materials", f"{s['animal']}"], ["Units", f"{s['units']}"],
        ["ICD-11 TM2 disease concepts", f"{s['icd']}"],
        ["Constituent concepts realised", "435-563 (matching-rule dependent)"],
        ["Indication concepts realised", "49 (stable across rules)"],
        ["Measured OCR error (two-engine)", "CER ~9%, WER ~6% (Tesseract vs Google GCV)"],
    ]))

    # ---- 2. example ----
    P.append("<h2>2 · A worked example: entry 37, Bhūnimbādi Cūrṇa (p. 236)</h2>")
    P.append("<p>A representative fully-populated formula. Below: the original scanned page, the "
             "entry as it reads in the source, and its structured JSON.</p>")
    if page_img:
        P.append("<details open><summary>Original scanned page (p. 236, source OCR input)</summary>"
                 + img(page_img[0]["b64"], "page 236") + "</details>")
    orig = (
        "37. යෝග නාමය :- භූනිම්බාදි චූර්ණය\n"
        "යෝගය:  බිං කොහොඹ / කුළුරෑණ / කලාඳුරුඅල / තිකුළු / කෙළිඳඇට\n"
        "        කර්ෂ 2 බැගින් ප්‍රත්‍යෙකව ගත යුතු ය .  ( ග්‍රෑම් 30 )\n"
        "සංස්කරණය:  කෙළිඳ පොතු කලං 16 යි .  ( ග්‍රෑම් 80 )\n"
        "ප්‍රයෝග:  ග්‍රහණි , ගුල්ම , කාමලා , ජ්වර , පාණ්ඩු , ප්‍රමේහ , අරුචි , අතීසාර නස යි .\n"
        "අනුපාන :-  උණු දිය වේ .\n"
        "මාත්‍රාව:  කලං 2 -1 දක්වා වේ .  ( ග්‍රෑම් 2.5 - ග්‍රෑම් 5 )"
    )
    P.append("<h3>Original entry (reading order)</h3>")
    P.append("<pre class='sinhala'>" + esc(orig) + "</pre>")
    P.append("<h3>Structured JSON representation</h3>")
    P.append("<pre class='small json'>" + esc(json.dumps(e, ensure_ascii=False, indent=2)) + "</pre>")
    P.append("<p class='small'>Field keys (Sinhala): අංකය number, යෝග නාමය name, යෝගය constituents "
             "(each ද්‍රව්‍යය substance, ප්‍රමාණය traditional quantity, ග්‍රෑ normalised grams), "
             "සංස්කරණය preparation, ප්‍රයෝග indication, අනුපාන vehicle, මාත්‍රාව dosage. Note the "
             "dual dosage encoding: traditional units (කර්ෂ / කලං) alongside a normalised gram value.</p>")

    # ---- 3. unique features ----
    P.append("<h2>3 · What makes this corpus unique and hard</h2>")
    P.append("<h3>3.1 Sanskrit code-mixed Sinhala <span class='small'>(COMPUTED)</span></h3>")
    P.append(f"<p>The register is a <b>diglossic mix</b>: a Sanskrit-derived technical vocabulary "
             f"(tatsama and tadbhava) for substances and diseases, embedded in everyday Sinhala "
             f"syntax and instructional prose. <b>{s['ing_pct']:.0f}%</b> of the {s['ing_entries']} "
             f"distinct ingredient terms and <b>{s['name_pct']:.0f}%</b> of the {s['name_entries']} "
             f"formula-name words resolve to a Sanskrit lemma via the Monier-Williams dictionary, "
             f"while connectives, verbs, quantities and clause structure remain colloquial Sinhala.</p>")
    P.append("<div class='note'><b>Code-mixing in one line</b> (the indication of entry 37). Eight "
             "Sanskrit disease terms closed by a single colloquial Sinhala verb:<br>"
             "<span class='sinhala'>ග්‍රහණි , ගුල්ම , කාමලා , ජ්වර , පාණ්ඩු , ප්‍රමේහ , අරුචි , අතීසාර "
             "<b>නස යි</b></span><br>"
             "<span class='small'>grahaṇī, gulma, kāmalā, jvara, pāṇḍu, prameha, aruci, atīsāra "
             "(Sanskrit nosological terms) + <b>nasa yi</b> ('destroys', Sinhala finite verb). "
             "The disease names are a closed Sanskrit set normalisable to ICD-11 TM2; the verb and "
             "syntax are open Sinhala.</span></div>")
    P.append("<h3>3.2 Abugida script complexity <span class='small'>(COMPUTED)</span></h3>")
    P.append(f"<p>Sinhala is an abugida whose conjunct consonants are formed with a zero-width "
             f"joiner and virama: the corpus holds <b>{s['zwj']:,}</b> ZWJ joiners and "
             f"<b>{s['virama']:,}</b> viramas over {s['graphemes']:,} grapheme clusters. A single "
             f"word costs <b>{s['bytes_per_word']:.1f} UTF-8 bytes</b> on average "
             f"({s['bytes_per_cp']:.2f} bytes per codepoint), so byte-level segmentation costs "
             "roughly 13 times word-level. Multilingual tokenizers over-fragment such scripts, "
             "penalising the register before any model sees it.</p>")
    P.append("<h3>3.3 Open, sparse technical vocabulary <span class='small'>(COMPUTED)</span></h3>")
    P.append(f"<p><b>{s['hapax_pct']:.0f}%</b> of word types are hapax legomena and the type-token "
             f"ratio is {s['ttr']:.3f}: the constituent names form a large open class (435-563 "
             "distinct concepts depending on the matching rule) dominated by rare plant, mineral "
             "and animal-origin terms, many vernacular and unlisted in any Sanskrit lexicon. The "
             "indication side, by contrast, is a small closed set (49 concepts) once normalised - "
             "an open/closed asymmetry the extraction task exploits.</p>")
    P.append("<h3>3.4 No existing NLP resources <span class='small'>(CITED)</span></h3>")
    P.append("<p>Sinhala sits in the lowest resource categories (Joshi et al., 2020); the AI4Bharat "
             "models and corpora exclude it (Gala et al., 2023); its dependency treebank holds one "
             "hundred sentences (Liyanage et al., 2023); and the available pretrained models are "
             "trained on news and web text, not a specialised register (Dhananjaya et al., 2022). "
             "No medical or Ayurvedic Sinhala resource exists.</p>")
    P.append("<h3>3.5 Recognition noise on a conjunct script <span class='small'>(COMPUTED)</span></h3>")
    P.append("<p>The text reaches the computer through OCR of printed sources. A two-engine "
             "measurement (Tesseract-sin against Google Cloud Vision) on a stratified page sample "
             "gives a character error rate of about 9 percent, concentrated on conjunct clusters "
             "and joiner placement - error that mints spurious word types and inflates vocabulary "
             "growth if uncontrolled.</p>")
    P.append("<h3>3.6 Cross-script normalisation is intrinsic <span class='small'>(COMPUTED)</span></h3>")
    P.append("<p>Making the content computable requires three normalisation layers already built: "
             "Sinhala surface to Sanskrit lemma (Monier-Williams), Sanskrit disease term to ICD-11 "
             "TM2 code, and Latin binomial to POWO / IPNI identifier. The register therefore spans "
             "three scripts and two classical languages in a single formula line.</p>")

    # ---- 4. KG integration ----
    P.append("<h2>4 · Knowledge-graph integration (feasibility) <span class='small'>(COMPUTED)</span></h2>")
    P.append("<p><b>Verdict: yes, and it is already prototyped.</b> A v1 knowledge graph has been "
             "built from these same artefacts (<code>knowledge_graph/build.py</code>, build report "
             f"dated {kg.get('built_at','')[:10]}). It fits the proposal cleanly as the structured "
             "representation deliverable, populated by the RQ3 extractor.</p>")
    nb = kg["nodes"]["by_type"]; eb = kg["edges"]["by_type"]
    P.append(table(["Node type", "Count"], [[k, f"{v:,}"] for k, v in
                   sorted(nb.items(), key=lambda x: -x[1])] + [["<b>Total nodes</b>", f"<b>{kg['nodes']['total']:,}</b>"]]))
    P.append(table(["Edge type", "Count", "Meaning"], [
        ["CONTAINS", f"{eb.get('CONTAINS',0):,}", "formula → constituent (with parsed dosage)"],
        ["TREATS", f"{eb.get('TREATS',0):,}", "formula → disease (via ICD-11 TM2)"],
        ["DOSED_WITH", f"{eb.get('DOSED_WITH',0):,}", "formula → vehicle / anupāna"],
        ["HAS_PROPERTY", f"{eb.get('HAS_PROPERTY',0):,}", "substance → pharmacological property"],
        ["SUBSTITUTES_FOR", f"{eb.get('SUBSTITUTES_FOR',0):,}", "abhāva-pratinidhi substitute"],
        ["IS_TYPE", f"{eb.get('IS_TYPE',0):,}", "formula → preparation type"],
        ["CO_OCCURS", f"{eb.get('CO_OCCURS',0):,}", "ingredient co-occurrence"],
        ["<b>Total edges</b>", f"<b>{kg['edges']['total']:,}</b>", ""],
    ], "wide"))
    P.append("<div class='note'><b>How it integrates with the research questions.</b> "
             "RQ3's boundary-free extractor emits exactly the CONTAINS / TREATS / DOSED_WITH edges; "
             "the gazetteers that supply RQ3's distant-supervision labels are the same closed "
             "vocabularies that key the graph's Plant, Mineral and Disease nodes; and the RQ2 "
             "segmentation choice determines the tokenisation the extractor runs on. Every node and "
             "edge already carries provenance (source_doc, record id, extractor version, confidence). "
             "External identifiers are attached where resolvable: "
             f"{kg['external_id_coverage']['Disease_with_ICD11_TM2']}/{kg['external_id_coverage']['Disease_total']} "
             "diseases to ICD-11 TM2, and resolved plants to POWO / IPNI.</div>")
    P.append("<p class='small'>Caveat (COMPUTED): the v1 build predates the final dedup and includes "
             "the Yogamālāva source, so its Formulation count reflects both sources; a single-source "
             "rebuild (<code>build.py --no-yogamalawa</code>) restricts it to the pp. 172-443 corpus. "
             "Recommendation: scope the graph as the proposal's structured-representation deliverable, "
             "populated by the RQ3 extractor with provenance, and evaluate it by external-identifier "
             "coverage rather than as a general resource.</p>")

    P.append("</body></html>")
    return "\n".join(P)


def main():
    html = build()
    out = C.OUT / "CORPUS_PROFILE.html"
    out.write_text(html, encoding="utf-8")
    print("wrote", out, out.stat().st_size, "bytes")


if __name__ == "__main__":
    main()

"""
Part A -- reconcile every numeric claim in proposal_body.md against the data.
Produces a reconciliation table (list of dicts) and an erratum patch.
Every value is tagged COMPUTED or ASSUMED.
"""
from __future__ import annotations
from collections import Counter

from . import common as C
from . import lex
from .common import nfc


def _status(proposal, computed, tol_rel=0.01, tol_abs=2):
    if proposal is None or computed is None:
        return "review"
    try:
        if abs(proposal - computed) <= tol_abs or abs(proposal - computed) <= tol_rel * max(abs(proposal), 1):
            return "match"
    except TypeError:
        return "review"
    return "mismatch"


def corpus_basic_counts():
    formulas_name = C.load_formulas("name")          # proposal's 700
    formulas_np = C.load_formulas("name_page")       # 701
    text = " ".join(C.formula_text(e) for e in formulas_name)
    toks = text.split()
    # codepoints: content-only (sum of field-text lengths, no inter-field join spaces)
    content_cp = sum(len(C.formula_text(e)) for e in formulas_name)
    nonspace_cp = sum(1 for ch in text if not ch.isspace())
    sinhala_cp = sum(1 for ch in text if C.is_sinhala_cp(ch))
    bytes_ = len(text.encode("utf-8"))
    pages = sorted({e.get("source_page") for e in formulas_name if e.get("source_page")})
    return {
        "n_formulas_name": len(formulas_name),
        "n_formulas_name_page": len(formulas_np),
        "n_tokens": len(toks),
        "codepoints_content": content_cp,
        "codepoints_nonspace": nonspace_cp,
        "codepoints_sinhala": sinhala_cp,
        "codepoints_with_joinspaces": len(text),
        "bytes": bytes_,
        "page_min": pages[0], "page_max": pages[-1],
        "bytes_per_word": bytes_ / len(toks),
        "bytes_per_codepoint": bytes_ / len(text),
        "codepoints_per_word": len(text) / len(toks),
    }


def lexicon_counts():
    mm = C.load_json("materia_medica.json")
    sc = mm["metadata"]["section_counts"]
    icd = C.load_json("indication_icd11_tm2.json")
    ue = C.load_json("unit_equivalences.json")
    return {
        "plant": sc["plant"],
        "mineral": sc["mineral"],
        "animal_origin": sc["animal_origin"],
        "icd_concepts_lexicon": len(icd),
        "icd_distinct_codes": len({v.get("tm2_code") for v in icd.values()}),
        "units_canonical": len(ue.get("symbols", {})),
    }


def constituent_concept_count():
    """Count distinct constituent concepts under several matching rules; the
    PRE-REGISTERED rule is 'token_subseq, concept-id'. Reports sensitivity."""
    formulas = C.load_formulas("name")
    ing = lex.ingredient_surfaces()
    out = {}
    for mode in ("token_subseq", "token_exact", "substring"):
        ids = set()
        for e in formulas:
            text = C.formula_field_texts(e)["constituents"]
            hits = lex._match_field(text, ing, mode=mode)
            ids.update(hits)
        out[mode] = len(ids)
    return out


def indication_concept_count():
    """Distinct ICD-11 TM2 concepts realised in the indication field, and the
    fraction of indication-bearing formulas with >=1 mapped concept."""
    formulas = C.load_formulas("name")
    icd = C.load_json("indication_icd11_tm2.json")
    # build surface -> (concept_key, tm2_code). concept_key is the lexicon key
    # (a distinct sanskrit-term concept); tm2_code collapses synonyms.
    surf2concept = {}
    for key, v in icd.items():
        s = nfc(v.get("sinhala_surface") or "")
        if s:
            surf2concept[s] = (key, v.get("tm2_code"))
    n_indic_bearing = 0
    concept_keys = set()
    tm2_codes = set()
    formulas_with_concept = 0
    for e in formulas:
        ind = nfc(C.formula_field_texts(e)["indication"])
        if ind.strip():
            n_indic_bearing += 1
        found = False
        for s, (key, code) in surf2concept.items():
            if s and s in ind:
                concept_keys.add(key)
                tm2_codes.add(code)
                found = True
        if found and ind.strip():
            formulas_with_concept += 1
    return {
        "distinct_concepts_realised": len(concept_keys),
        "distinct_tm2_codes_realised": len(tm2_codes),
        "n_indication_bearing": n_indic_bearing,
        "formulas_with_mapped_concept": formulas_with_concept,
        "coverage_frac": formulas_with_concept / n_indic_bearing if n_indic_bearing else float("nan"),
    }


def field_presence():
    formulas = C.load_formulas("name")
    n = len(formulas)
    keys = ["name", "constituents", "preparation", "indication", "dosage", "vehicle"]
    pres = {k: 0 for k in keys}
    for e in formulas:
        d = C.formula_field_texts(e)
        for k in keys:
            if d[k].strip():
                pres[k] += 1
    return {k: v / n for k, v in pres.items()}


def clause_final_predicates(top=10):
    """Last whitespace token of each indication clause (split on danda '.' or
    Sinhala full stop). Report top-k coverage."""
    formulas = C.load_formulas("name")
    finals = []
    for e in formulas:
        ind = C.formula_field_texts(e)["indication"]
        if not ind.strip():
            continue
        for clause in _split_clauses(ind):
            toks = clause.split()
            # drop trailing punctuation token
            toks = [t for t in toks if any(ch.isalpha() for ch in t)]
            if toks:
                finals.append(toks[-1])
    c = Counter(finals)
    total = sum(c.values())
    topk = c.most_common(top)
    cov = sum(v for _, v in topk) / total if total else float("nan")
    return {"n_clauses": total, "top_predicates": topk, "topk_coverage": cov}


def _split_clauses(text):
    import regex as re
    parts = re.split(r"[.।॥]|।|॥", text)
    return [p.strip() for p in parts if p.strip()]


def run():
    basic = corpus_basic_counts()
    lexc = lexicon_counts()
    consc = constituent_concept_count()
    indc = indication_concept_count()
    pres = field_presence()
    pred = clause_final_predicates()

    rows = []

    def add(claim, prop, comp, note, tol_rel=0.01, tol_abs=2, status=None):
        rows.append({
            "claim": claim, "proposal": prop, "computed": comp,
            "status": status or _status(prop, comp, tol_rel, tol_abs),
            "note": note, "tag": "COMPUTED",
        })

    add("Distinct formulas", 700, basic["n_formulas_name"],
        "dedup by name; dedup by (name,page) gives %d (sensitivity +/-1)." % basic["n_formulas_name_page"])
    add("Page span (min)", 172, basic["page_min"], "structured formula section start")
    add("Page span (max)", 443, basic["page_max"], "structured formula section end")
    add("Whitespace tokens (6 fields)", 60599, basic["n_tokens"],
        "diff traceable to dedup rule + continuation handling.", tol_abs=200)
    add("Codepoints (corpus-wide)", 314060, basic["codepoints_content"],
        "content codepoints = sum of field-text lengths (no inter-field join spaces).", tol_abs=300)
    add("UTF-8 bytes", 788289, basic["bytes"], "all six fields joined.", tol_abs=2500)
    add("Codepoints (intrinsic table)", 253462, basic["codepoints_nonspace"],
        "non-whitespace ('segmentable') codepoints; %d are Sinhala-script." % basic["codepoints_sinhala"],
        tol_abs=1500)
    add("Plant names", 647, lexc["plant"], "materia_medica section_counts.plant")
    add("Minerals", 82, lexc["mineral"], "materia_medica section_counts.mineral")
    add("ICD-11 TM2 concepts (lexicon)", 56, lexc["icd_concepts_lexicon"],
        "indication_icd11_tm2.json entries; %d distinct TM2 codes." % lexc["icd_distinct_codes"])
    add("Units", 43, lexc["units_canonical"], "unit_equivalences canonical symbol registry")
    add("Constituent concepts (open class)", 599, consc["token_subseq"],
        "PRE-REG rule token_subseq/concept-id; token_exact=%d, substring=%d." %
        (consc["token_exact"], consc["substring"]), tol_abs=20)
    add("Indication concepts realised", 49, indc["distinct_concepts_realised"],
        "distinct lexicon concept-keys via substring match; distinct TM2 codes=%d." %
        indc["distinct_tm2_codes_realised"], tol_abs=5)
    add("Indication coverage of formulas", 0.74, round(indc["coverage_frac"], 3),
        "fraction of indication-bearing formulas with >=1 mapped ICD concept.", tol_abs=0.05)
    add("Clause-final predicates top-10 coverage", 0.81, round(pred["topk_coverage"], 3),
        "top-10 clause-final tokens / all indication clause finals.", tol_abs=0.06)
    add("Byte:word cost ratio", 3.0, round(basic["bytes_per_word"], 2),
        "MISMATCH: bytes/word=%.1f. The '3' is bytes/codepoint=%.2f. codepoints/word=%.2f." %
        (basic["bytes_per_word"], basic["bytes_per_codepoint"], basic["codepoints_per_word"]),
        status="mismatch")

    erratum = build_erratum(basic, consc, indc, pred)
    return {
        "basic": basic, "lexicon": lexc, "constituents": consc,
        "indications": indc, "field_presence": pres, "predicates": {
            "n_clauses": pred["n_clauses"], "topk_coverage": pred["topk_coverage"],
            "top_predicates": [[t, n] for t, n in pred["top_predicates"]],
        },
        "reconciliation": rows, "erratum": erratum,
    }


def build_erratum(basic, consc, indc, pred):
    bw = basic["bytes_per_word"]; bc = basic["bytes_per_codepoint"]; cw = basic["codepoints_per_word"]
    edits = []
    edits.append({
        "id": "E1-byte-ratio",
        "old": "byte-level segmentation costs roughly three times word-level here",
        "new": ("byte-level segmentation costs roughly %.0f times word-level here "
                "(%.1f bytes per word vs 1 unit per word); the ~3 figure is the "
                "bytes-per-codepoint ratio (%.2f), not the byte-to-word ratio") %
               (round(bw), bw, bc),
    })
    edits.append({
        "id": "E2-constituent-concepts",
        "old": "the constituent items map to 599 distinct concepts on the plant and materia-medica lists",
        "new": ("the constituent items map to %d distinct concepts on the plant and "
                "materia-medica lists under a token-boundary longest-match rule "
                "(strict single-token matching gives %d; raw substring matching %d)") %
               (consc["token_subseq"], consc["token_exact"], consc["substring"]),
    })
    edits.append({
        "id": "E3-codepoints",
        "old": "314,060 codepoints",
        "new": ("%d codepoints corpus-wide (all six fields). The intrinsic-measure "
                "table reports %d codepoints, which counts non-whitespace "
                "segmentable content only; the two should be cited distinctly") %
               (basic["codepoints_content"], basic["codepoints_nonspace"]),
    })
    edits.append({
        "id": "E4-indication-concepts",
        "old": "the indication prose maps to 49 ICD-11 Traditional Medicine concepts across 74 percent of indication-bearing formulas",
        "new": ("the indication prose maps to %d ICD-11 Traditional Medicine concepts "
                "across %.0f percent of indication-bearing formulas (substring match "
                "of disease surfaces; %d distinct TM2 codes realised, lexicon holds "
                "56 concept entries)") %
               (indc["distinct_concepts_realised"], 100 * indc["coverage_frac"],
                indc["distinct_tm2_codes_realised"]),
    })
    edits.append({
        "id": "E5-baselines",
        "old": "the Sinhala portions of CC-100 and OSCAR and a news corpus",
        "new": ("a news corpus (NLPC-UOM POS-tagged news, ~254k tokens) as the "
                "general-domain baseline and government order-paper text as a "
                "restricted-register control. CC-100, OSCAR and Sinhala Wikipedia "
                "were unreachable from the analysis environment (HTTP 403) and are "
                "named as intended, not realised, baselines"),
    })
    edits.append({
        "id": "E6-tokens",
        "old": "60,599 whitespace-delimited tokens",
        "new": "%d whitespace-delimited tokens" % basic["n_tokens"],
    })
    edits.append({
        "id": "E7-bytes",
        "old": "788,289 UTF-8 bytes",
        "new": "%d UTF-8 bytes" % basic["bytes"],
    })
    return edits

"""
build.py
────────
Build the Sinhala Traditional Medicine KG v1 from existing artifacts.

INPUTS (read-only)
  data/structured/*_structured.json                  Vol I (tabular) entries
  data/structured/yogamalawa/yogamalawa_structured_v2.json  Yogamālāva (verse) entries
  data/lexicons/ingredients_lexicon.json             Sanskrit resolution per Sinhala ingredient
  data/lexicons/prose_lexicon.json                   Sanskrit resolution for prose terms
  data/lexicons/names_lexicon.json                   Sanskrit resolution for formula-name words
  data/lexicons/botanical_candidates.json            Latin binomials extracted from MW glosses
  data/lexicons/botanical_powo.json                  Latin → POWO IPNI LSID + modern name
  data/lexicons/indication_icd11_tm2.json            Sanskrit indication → ICD-11 TM2 code
  data/lexicons/materia_medica.json                  Pharmacopoeia-categorised raw materials
                                                     (Sinhala → plant | mineral | animal_origin),
                                                     produced by pipeline/extract_materia_medica.py

OUTPUTS (knowledge_graph/)
  kg.jsonld             Linked-data view (JSON-LD @graph, matches docs/context.jsonld)
  kg.cypher             Neo4j CREATE statements
  kg.ttl                RDF Turtle
  build_report.json     Per-type node/edge counts + external-ID coverage

DESIGN (see docs/kg_schema.md for the v1 schema contract)
  Node types     Formulation, Plant, Mineral, Disease, PreparationType, Route,
                 PharmacologicalProperty (the closed-enum nodes are emitted
                 only if referenced).
  Edge types     CONTAINS, IS_TYPE, DOSED_WITH, TREATS, CO_OCCURS, VARIANT_OF.
  Provenance     Every node and edge carries {source_doc, source_record_id,
                 extractor_version, confidence, created_at}.
  ID format      Internal: `<type>:<key>`. External: under .external{}.

USAGE
  python knowledge_graph/build.py
  python knowledge_graph/build.py --max-cooccurrence 200  # cap CO_OCCURS edges
  python knowledge_graph/build.py --no-yogamalawa         # Vol I only
"""
from __future__ import annotations
import argparse
import glob
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from itertools import combinations

EXTRACTOR_VERSION = "kg_build_v1.2"
SCHEMA_VERSION    = "1.1"

# Dosage normaliser (optional). Loaded once if the unit registry is present.
_DOSAGE = None


def _load_dosage_registry(repo_root):
    """Best-effort load of the multi-system unit registry. None on failure."""
    global _DOSAGE
    try:
        import importlib.util as _u
        spec = _u.spec_from_file_location(
            "_kg_dosage", str(repo_root / "knowledge_graph" / "dosage.py"))
        mod = _u.module_from_spec(spec); spec.loader.exec_module(mod)
        _DOSAGE = mod.load_units(
            str(repo_root / "data" / "lexicons" / "unit_equivalences.json"))
    except Exception as e:
        print(f"  (dosage normaliser unavailable: {e})")
        _DOSAGE = None
    return _DOSAGE


def _to_grams(text, default_density=1.0):
    """Safe wrapper. Returns (grams_or_None, matched_unit_iast, system, ml)."""
    if not _DOSAGE or not text:
        return None, None, None, None
    out = _DOSAGE.to_grams(text, default_density=default_density)
    sym = out.get("matched_unit")
    iast = ((_DOSAGE.symbols.get(sym) or {}).get("iast")
            if sym else None)
    return out.get("grams"), iast, out.get("system"), out.get("ml")


# ── helpers ──────────────────────────────────────────────────────────────────
def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(s):
    """Make a string safe for use inside an internal ID."""
    return nfc(s).replace(" ", "_").replace("/", "_").replace("‍", "")


# ── small closed vocabularies ────────────────────────────────────────────────

# Map of formula-name suffix in Sinhala (Sanskrit) → PreparationType lemma.
PREP_SUFFIXES = [
    ("ක්වාථය",   "kvātha"),     # kasāya = decoction
    ("කෂාය",     "kaṣāya"),
    ("තෛලය",    "taila"),       # medicated oil
    ("ඝෘතය",    "ghṛta"),       # medicated ghee
    ("කල්කය",   "kalka"),       # paste
    ("චූර්ණය",   "cūrṇa"),       # powder
    ("ගුළිකාව",  "gulika"),      # pill
    ("ගුළිය",     "gulika"),
    ("ගුළි",      "gulika"),
    ("අරිෂ්ටය",  "ariṣṭa"),      # fermented decoction
    ("අවලේහ",   "avaleha"),     # confection
    ("භස්ම",     "bhasma"),      # calcined ash (also a noun marker)
]

# Hand-curated set of Sanskrit lemmas that denote mineral / non-plant
# substances. Used to classify ingredient-head lemmas as Mineral vs Plant.
KNOWN_MINERAL_LEMMAS = {
    # salts and alkalis
    "saindhava", "saindhavalavaṇa", "lavaṇa", "yavakṣāra", "ṭaṅkaṇa", "kāca",
    # metals
    "lauha", "tāmra", "raja", "rajata", "svarṇa", "vaṅga", "yaśada", "ārikuṣṭha",
    # bhasma family
    "bhasma", "abhraka",
    # mercury / minerals
    "rasa", "rasadi", "rasendra", "rasasindūra", "gandhaka", "haritāla",
    "manaḥśilā", "mākṣika", "padmakāṣṭha",
    # generic mineral markers
    "kānta", "śaṅkha", "muktā", "śilāj", "śilājit", "śilājatu",
}

# Mineral-ish gloss keywords (used when lemma isn't in the hand list).
MINERAL_GLOSS_KEYWORDS = re.compile(
    r"\b(salt|alkali|sulphur|mercury|copper|iron|metal|ash|calx|"
    r"calcined|mineral|stone|earth|gypsum|alum|silica)\b",
    re.IGNORECASE,
)

# Default route when none is explicitly named in `anupāna`.
DEFAULT_ROUTE = "oral"

# Vehicle (anupāna) detection — Sinhala phrases that strongly indicate
# a specific vehicle / adjuvant.
VEHICLE_HINTS = {
    "මී පැණි":      ("madhu",        "Honey"),
    "ගිතෙල්":       ("ghṛta",        "Ghee"),
    "තල තෙල්":     ("tila_taila",    "Sesame oil"),
    "තලතෙල්":      ("tila_taila",    "Sesame oil"),
    "එරඬු තෙල්":   ("eraṇḍa_taila", "Castor oil"),
    "එරඬුතෙල්":    ("eraṇḍa_taila", "Castor oil"),
    "එළකිරි":       ("kṣīra",        "Cow milk"),
    "මී":            ("madhu",        "Honey"),
    "කිරි":          ("kṣīra",        "Milk"),
    "උනු වතුර":    ("uṣṇodaka",     "Warm water"),
    "උනුවතුර":     ("uṣṇodaka",     "Warm water"),
}

# Disease-keyword regex (reused from icd11_tm2_mapper) — used to limit
# which prose-lexicon lemmas we even attempt to match to TM2 codes.
DISEASE_GLOSS = re.compile(
    r"\b(fever|disease|disorder|cough|pain|ulcer|swelling|inflammation|"
    r"piles|asthma|haemorrhoid|consumption|leprosy|spleen|urin\w*|"
    r"colic|diarrhoea|dropsy|stone|jaundice|gout|bile|phlegm|wind|"
    r"tumour|distension|wound|haemorrhage|abscess|leucoderma|"
    r"breathing|panting|syndrome|obstruction|constipation|catarrh|"
    r"flatulence|vomiting|loss\s+of\s+appetite)\b",
    re.IGNORECASE,
)


# ── load inputs ──────────────────────────────────────────────────────────────
def load_inputs(repo_root: Path, include_yogamalawa: bool):
    structured = []
    for path in sorted(glob.glob(str(repo_root / "data/structured/*_structured.json"))):
        d = json.load(open(path, encoding="utf-8"))
        # Vol I entry numbers reset per 50-page batch, so we must
        # namespace the Formulation ID by batch to avoid collisions.
        batch = d.get("batch") or Path(path).stem.replace("_structured", "")
        for e in d.get("entries", []):
            structured.append({"entry": e, "source_doc": path,
                               "batch": batch,
                               "source_register": "tabular"})
    if include_yogamalawa:
        ypath = repo_root / "data/structured/yogamalawa/yogamalawa_structured_v2.json"
        if ypath.exists():
            d = json.load(open(ypath, encoding="utf-8"))
            for e in d.get("entries", []):
                structured.append({"entry": e, "source_doc": str(ypath),
                                   "batch": "yogamalawa",
                                   "source_register": "verse"})

    def jload(p):
        return json.load(open(p, encoding="utf-8")) if p.exists() else {}

    lex_dir = repo_root / "data/lexicons"
    ingredients_lex = jload(lex_dir / "ingredients_lexicon.json")
    prose_lex       = jload(lex_dir / "prose_lexicon.json")
    names_lex       = jload(lex_dir / "names_lexicon.json")
    botanical_seed  = jload(lex_dir / "botanical_candidates.json")
    powo            = jload(lex_dir / "botanical_powo.json")
    tm2             = jload(lex_dir / "indication_icd11_tm2.json")
    mm              = jload(lex_dir / "materia_medica.json")
    pratinidhi      = jload(lex_dir / "pratinidhi_lookup.json")
    mahakashaya     = jload(lex_dir / "mahakashaya_groups.json")
    # Build a Sinhala-surface → section lookup for ingredient classification.
    # Keys are NFC-normalised. The materia_medica file is itself NFC.
    mm_lookup: dict[str, str] = {}
    for surf, rec in (mm.get("by_sinhala") or {}).items():
        mm_lookup[nfc(surf)] = rec.get("section")
    return {
        "formulas": structured,
        "ingredients_lex": ingredients_lex,
        "prose_lex": prose_lex,
        "names_lex": names_lex,
        "botanical_seed": botanical_seed,
        "powo": powo,
        "tm2": tm2,
        "materia_medica": mm_lookup,
        "pratinidhi":  pratinidhi,
        "mahakashaya": mahakashaya,
    }


# ── ingredient resolution (Sinhala → Plant/Mineral node ID) ──────────────────
def head_lemma(words):
    """For a multi-word Sinhala ingredient, return the head lemma.
    Convention: the rightmost word's lemma if resolved; else None."""
    if not words:
        return None, None, None
    # walk right-to-left and pick the first resolved
    for w in reversed(words):
        if w.get("lemma"):
            return w["lemma"], (w.get("gloss") or ""), w.get("method")
    return None, None, None


def classify_ingredient(lemma, gloss):
    """Return ('Plant' | 'Mineral', canonical_id) for a resolved lemma."""
    if not lemma:
        return None, None
    base = lemma.replace("-", "").replace(" ", "")
    if base in KNOWN_MINERAL_LEMMAS:
        return "Mineral", f"min:{slug(lemma)}"
    if any(base.endswith(x) for x in ("lavaṇa", "bhasma", "kṣāra")):
        return "Mineral", f"min:{slug(lemma)}"
    if MINERAL_GLOSS_KEYWORDS.search(gloss or ""):
        return "Mineral", f"min:{slug(lemma)}"
    return "Plant", f"plant:{slug(lemma)}"


# Mapping from materia_medica section → (node type, internal-ID prefix).
MM_SECTION = {
    "plant":          ("Plant",         "plant"),
    "mineral":        ("Mineral",       "min"),
    "animal_origin": ("AnimalOrigin", "animal"),
}


def apply_materia_medica(surf, kind, internal, lemma, mm_lookup):
    """Use the pharmacopoeia's own categorisation (materia_medica.json) to
    refine ingredient classification.

    Override rules:
      • Resolver returned a kind but mm disagrees      → mm wins, re-ID.
      • Resolver returned nothing (unresolved)          → mm sets the kind.
      • surf not in mm                                  → no change.

    The lemma stays the same; only the type label and the internal-ID
    prefix may change. For unresolved ingredients (lemma is None) the
    internal ID is `<prefix>:_si_<slug(surf)>` regardless of section.
    Returns (kind, internal, override_reason | None).
    """
    section = mm_lookup.get(nfc(surf))
    if section is None or section not in MM_SECTION:
        return kind, internal, None
    new_kind, new_prefix = MM_SECTION[section]
    if kind == new_kind:
        # Already correctly classified; just attach the source-authority tag.
        return kind, internal, "mm_confirmed"
    # Override.
    if lemma:
        new_internal = f"{new_prefix}:{slug(lemma)}"
    else:
        new_internal = f"{new_prefix}:_si_{slug(surf)}"
    reason = f"mm_override:{kind or 'unresolved'}→{new_kind}"
    return new_kind, new_internal, reason


def resolve_ingredient(surface_si, lex):
    """Look up an ingredient's Sinhala surface form in ingredients_lexicon.
    Returns (kind, internal_id, lemma, gloss, method) or (None, None, None, None, None).
    """
    rec = lex.get(nfc(surface_si)) or lex.get(surface_si)
    if not rec or not rec.get("words"):
        return None, None, None, None, None
    lemma, gloss, method = head_lemma(rec["words"])
    if not lemma:
        return None, None, None, None, None
    kind, internal = classify_ingredient(lemma, gloss)
    return kind, internal, lemma, gloss, method


# ── Latin binomial detection (reused for plant external IDs) ─────────────────
LATIN_RE = re.compile(r"\b([A-Z][a-zæëïöü]{2,})\s+([A-Z]?[a-z][a-zæëïöü]{2,})\b")
LATIN_GENUS_STOP = {"The", "This", "That", "See", "Name", "Comp", "Often",
                    "Bombay", "Indian", "According", "Sanskrit", "Hindi",
                    "Bengal", "Ceylon", "Linn", "Roxb", "Wall", "Willd", "Don",
                    "Lam", "DC", "Nees", "Columba", "Coluber"}


def extract_latin_from_gloss(gloss):
    out = []
    for g, sp in LATIN_RE.findall(gloss or ""):
        if g in LATIN_GENUS_STOP:
            continue
        out.append(f"{g} {sp}")
    return out


# ── PreparationType detection ───────────────────────────────────────────────
def detect_prep_type(name_sa: str) -> str | None:
    if not name_sa:
        return None
    for suffix_si, prep_lemma in PREP_SUFFIXES:
        if name_sa.endswith(suffix_si):
            return prep_lemma
    return None


# ── KG assembly ──────────────────────────────────────────────────────────────
def build_kg(inputs, max_cooccurrence=200, min_cooccurrence=3):
    nodes = {}      # id → node dict
    edges = []      # list of edge dicts
    co_pairs = Counter()   # (a_id, b_id) → count

    def ensure_node(node_id, ntype, **props):
        if node_id in nodes:
            for k, v in props.items():
                if v and not nodes[node_id].get(k):
                    nodes[node_id][k] = v
            return nodes[node_id]
        nodes[node_id] = {
            "id": node_id, "type": ntype,
            "created_at": now_iso(),
            "extractor_version": EXTRACTOR_VERSION,
            **props,
        }
        return nodes[node_id]

    def add_edge(etype, src, dst, **props):
        edges.append({
            "type": etype, "from": src, "to": dst,
            "extractor_version": EXTRACTOR_VERSION,
            "confidence": props.pop("confidence", 1.0),
            **props,
        })

    # ── 1. Build PreparationType + Route nodes (closed enum, idempotent) ──
    for _, lemma in PREP_SUFFIXES:
        ensure_node(f"prep:{lemma}", "PreparationType",
                    canonical_iast=lemma, sanskrit=lemma)
    for r in (DEFAULT_ROUTE, "anuvāsana", "nasya", "basti", "abhyaṅga"):
        ensure_node(f"route:{slug(r)}", "Route",
                    canonical_iast=r, sanskrit=r)
    # Vehicles: split into AnimalOrigin (madhu / ghṛta / kṣīras) vs Plant
    # (plant oils, water). The classical anupāna vocabulary maps cleanly.
    ANIMAL_VEHICLE_LEMMAS = {"madhu", "ghṛta", "kṣīra"}
    for sin_phrase, (v_iast, v_en) in VEHICLE_HINTS.items():
        is_animal = v_iast in ANIMAL_VEHICLE_LEMMAS
        ntype = "AnimalOrigin" if is_animal else "Plant"
        ensure_node(f"vehicle:{slug(v_iast)}", ntype,
                    canonical_iast=v_iast, sanskrit=v_iast,
                    english_common=[v_en],
                    also_acts_as_vehicle=True if is_animal else None)

    # ── 2. Build POWO-cached Latin-binomial → LSID lookup ──
    powo = inputs["powo"]

    def attach_powo_external(plant_node, lemma, gloss):
        # If the lemma's MW gloss yields a Latin binomial we have in POWO,
        # add the external IDs.
        candidates = extract_latin_from_gloss(gloss)
        for b in candidates:
            rec = powo.get(b)
            if rec and rec.get("powo_lsid"):
                plant_node.setdefault("external", {})
                plant_node["external"].setdefault("powo_lsid", rec["powo_lsid"])
                plant_node.setdefault("latin_binomial",
                                       rec.get("modern_accepted_name") or b)
                plant_node.setdefault("family", rec.get("family"))
                plant_node.setdefault("kingdom", rec.get("kingdom"))
                if rec.get("is_synonym"):
                    plant_node["external"]["powo_synonym_of_lsid"] = \
                        rec.get("modern_accepted_lsid")
                return True
        return False

    # ── 3. Build Disease nodes from the TM2 mapping ──
    tm2_index = {}   # iast lemma → Disease node id
    for lemma, rec in inputs["tm2"].items():
        if not rec.get("matched_via"):
            continue
        node_id = f"disease:{slug(lemma)}"
        ext = {}
        if rec.get("tm2_code"):
            ext["icd11_tm2"] = rec["tm2_code"]
        if rec.get("tm2_uri"):
            ext["icd11_uri"] = rec["tm2_uri"]
        ensure_node(node_id, "Disease",
                    canonical_iast=lemma, sanskrit=lemma,
                    english_rubric=rec.get("tm2_title_en"),
                    tm2_match_method=rec["matched_via"],
                    match_confidence=rec.get("confidence"),
                    external=ext)
        tm2_index[lemma] = node_id

    # ── 4. Walk formulas ──
    ing_lex   = inputs["ingredients_lex"]
    prose_lex = inputs["prose_lex"]
    mm_lookup = inputs.get("materia_medica", {})
    mm_stats  = {"confirmed": 0, "override": Counter(), "unresolved_classified": 0}

    for fobj in inputs["formulas"]:
        e = fobj["entry"]
        register = fobj["source_register"]
        source_doc = fobj["source_doc"]
        batch = fobj["batch"]
        num = e.get("අංකය")
        if num is None:
            continue

        # Formulation IDs are namespaced by batch to avoid collisions
        # (Vol I entry numbers reset per 50-page batch).
        f_id = f"formula:{batch}/{num}"
        name_sa = nfc(e.get("යෝග නාමය") or "")
        provenance = {"source_doc": source_doc, "source_record_id": str(num),
                      "register": register}

        ensure_node(f_id, "Formulation",
                    name_si=name_sa, sanskrit=name_sa,
                    source_register=register,
                    source_page=e.get("source_page"),
                    provenance=provenance)

        # 4a. IS_TYPE — from name suffix
        prep = detect_prep_type(name_sa)
        if prep:
            add_edge("IS_TYPE", f_id, f"prep:{prep}",
                     provenance=provenance, source="name_suffix")

        # 4b. CONTAINS — only Vol I has structured ingredient lists
        plant_ids_in_formula = set()
        if register == "tabular":
            for ing in (e.get("යෝගය") or []):
                surf = nfc((ing.get("ද්‍රව්‍යය") or "").strip())
                if not surf:
                    continue
                qty_text = (ing.get("ප්‍රමාණය") or "").strip()
                grams = ing.get("ග්‍රෑ") or 0.0
                kind, internal, lemma, gloss, method = resolve_ingredient(surf, ing_lex)
                unresolved = False
                if not internal:
                    # No Sanskrit lemma. Default to Plant; materia_medica
                    # may correct the section below.
                    internal = f"plant:_si_{slug(surf)}"
                    kind = "Plant"
                    lemma = None
                    unresolved = True
                # ── apply materia_medica authority ─────────────────────────
                pre_kind = kind
                kind, internal, mm_reason = apply_materia_medica(
                    surf, kind, internal, lemma, mm_lookup)
                if mm_reason == "mm_confirmed":
                    mm_stats["confirmed"] += 1
                elif mm_reason and mm_reason.startswith("mm_override"):
                    mm_stats["override"][mm_reason] += 1
                    if unresolved:
                        mm_stats["unresolved_classified"] += 1
                node = ensure_node(internal, kind,
                                   canonical_si=surf if not lemma else None,
                                   canonical_iast=lemma,
                                   sanskrit=lemma,
                                   gloss=(gloss or "")[:200],
                                   is_unresolved=unresolved or None,
                                   mm_section=(mm_lookup.get(nfc(surf))
                                               if mm_reason else None),
                                   mm_authority=("pharmacopoeia_pp444-453"
                                                 if mm_reason else None))
                if kind == "Plant" and lemma and gloss:
                    attach_powo_external(node, lemma, gloss)
                # If the structured JSON didn't already carry a metric
                # weight, try to derive one from the raw quantity text via
                # the dosage normaliser (Sri Lankan unit system by default).
                derived_grams = None
                derived_unit  = None
                derived_ml    = None
                if not grams and qty_text:
                    derived_grams, derived_unit, _system, derived_ml = \
                        _to_grams(qty_text)
                final_grams = grams or derived_grams
                # quantity_unit reflects what we ACTUALLY recorded:
                # parts (relative), gram (numeric), or the source unit-iast.
                if final_grams:
                    qty_unit_label = "gram"
                elif qty_text and derived_unit:
                    qty_unit_label = derived_unit
                elif qty_text:
                    qty_unit_label = "text_only"
                else:
                    qty_unit_label = "parts"
                add_edge("CONTAINS", f_id, internal,
                         parts=1 if not final_grams and not qty_text else None,
                         quantity_text=qty_text or None,
                         quantity_unit=qty_unit_label,
                         quantity_grams=final_grams or None,
                         quantity_ml=derived_ml or None,
                         quantity_source=("structured_metric" if grams
                                          else "dosage_normaliser"
                                          if derived_grams else None),
                         resolver_method=method,
                         provenance={**provenance,
                                     "ingredient_surface": surf})
                if kind == "Plant":
                    plant_ids_in_formula.add(internal)

        # 4c. DOSED_WITH — scan the anupāna text for known vehicles
        anupana = nfc(e.get("අනුපාන") or "")
        seen_vehicles = []
        for phrase, (iast, _english) in VEHICLE_HINTS.items():
            if phrase in anupana:
                v_id = f"vehicle:{slug(iast)}"
                if v_id not in seen_vehicles:
                    add_edge("DOSED_WITH", f_id, v_id,
                             provenance={**provenance, "matched_phrase": phrase})
                    seen_vehicles.append(v_id)

        # 4d. TREATS — tokenize prayoga, match each token against prose_lex
        #              + TM2 mapping
        prayoga = nfc(e.get("ප්‍රයෝග") or "")
        if prayoga:
            seen_diseases = set()
            for tok in prayoga.split():
                tok = nfc(tok.strip(" ,.;:!?\"\'"))
                rec = prose_lex.get(tok)
                if not rec:
                    continue
                for w in rec.get("words", []):
                    lemma = w.get("lemma")
                    if not lemma or w.get("method") != "direct":
                        continue
                    if lemma in tm2_index:
                        d_id = tm2_index[lemma]
                        if d_id in seen_diseases:
                            continue
                        seen_diseases.add(d_id)
                        add_edge("TREATS", f_id, d_id,
                                 evidence_level="canonical_text",
                                 provenance={**provenance,
                                             "matched_lemma": lemma,
                                             "matched_surface": tok})

        # 4e. CO_OCCURS — record plant-pairs for this formula
        for a, b in combinations(sorted(plant_ids_in_formula), 2):
            co_pairs[(a, b)] += 1

    # ── 5. Index existing substance nodes by NFC Sinhala surface form ─────
    # Used by Block-3 / Block-2 KG enrichment below.  Maps every known
    # Sinhala alias (canonical_si on unresolved nodes; sanskrit/iast on
    # resolved nodes via the ingredients lexicon) to its node id.
    surface_to_node: dict[str, str] = {}
    for node_id, n in nodes.items():
        if n["type"] not in ("Plant", "Mineral", "AnimalOrigin"):
            continue
        si = n.get("canonical_si") or n.get("sanskrit")
        if si:
            surface_to_node.setdefault(nfc(si), node_id)
    # Also: Sinhala ingredient surface → resolved node id via the lexicon.
    # ing_lex keys are the raw ingredient surface forms used in the corpus.
    for surf in (inputs.get("ingredients_lex") or {}):
        # The node would have been emitted only if a formula used this
        # ingredient; otherwise skip.
        # Build a likely id; if not in nodes, skip.
        skey = nfc(surf)
        if skey in surface_to_node:
            continue
        # Search nodes for one whose provenance/aliases match this surface.
        # Simple fallback: the slug-Sinhala form.
        candidate = f"plant:_si_{slug(skey)}"
        if candidate in nodes:
            surface_to_node[skey] = candidate

    # Helper: get-or-create a substance node from a Sinhala surface.
    # New nodes are created with classification from materia_medica when
    # available; otherwise default to Plant flagged unresolved.
    def _ensure_substance_node(surf, source_tag):
        surf = nfc(surf)
        if surf in surface_to_node:
            return surface_to_node[surf]
        section = mm_lookup.get(surf)
        ntype, prefix = MM_SECTION.get(section, ("Plant", "plant"))
        nid = f"{prefix}:_si_{slug(surf)}"
        ensure_node(nid, ntype,
                    canonical_si=surf,
                    is_unresolved=True,
                    mm_section=section,
                    introduced_by=source_tag)
        surface_to_node[surf] = nid
        return nid

    # ── 6. mahā-kaṣāya groups → PharmacologicalProperty + HAS_PROPERTY ─────
    mk_stats = {"property_nodes": 0, "has_property_edges": 0,
                "substances_with_property": 0, "substances_new": 0}
    mk = inputs.get("mahakashaya") or {}
    for v in (mk.get("vargas") or []):
        for g in v.get("ganas", []):
            gana_si  = nfc(g.get("gana_name_si") or "")
            if not gana_si:
                continue
            prop_id = f"prop:karma:{slug(gana_si)}"
            ensure_node(prop_id, "PharmacologicalProperty",
                        axis="karma",
                        canonical_si=gana_si,
                        varga_num=v.get("varga_num"),
                        varga_name_si=v.get("varga_name_si"),
                        varga_name_iast=v.get("varga_name_iast"),
                        source=f"pharmacopoeia_pp82-90_varga{v.get('varga_num')}")
            mk_stats["property_nodes"] += 1
            for s in g.get("substances", []):
                s_nfc = nfc(s)
                existed = s_nfc in surface_to_node
                s_id = _ensure_substance_node(s, "mahakashaya")
                if not existed:
                    mk_stats["substances_new"] += 1
                else:
                    mk_stats["substances_with_property"] += 1
                add_edge("HAS_PROPERTY", s_id, prop_id,
                         provenance={"source_doc":
                                       "data/lexicons/mahakashaya_groups.json",
                                     "varga": v.get("varga_num"),
                                     "gana":  g.get("gana_num"),
                                     "gana_name_si": gana_si})
                mk_stats["has_property_edges"] += 1
    # Deduplicate property nodes counter (we incremented per-gana but
    # ensure_node is idempotent — recount from the actual node set).
    mk_stats["property_nodes"] = sum(
        1 for n in nodes.values() if n["type"] == "PharmacologicalProperty"
    )

    # ── 7. pratinidhi → SUBSTITUTES_FOR edges ─────────────────────────────
    # Each entry's lhs_si (source) has rhs_si (substitute(s)). When `rhs_si`
    # contains multiple substances they're separated by " " or " = " (the
    # latter is itself a Sanskrit/Sinhala name-pair for ONE substitute).
    pr_stats = {"substitute_edges": 0, "new_substitute_nodes": 0}
    pr = inputs.get("pratinidhi") or {}
    for ent in (pr.get("entries") or []):
        lhs_si = nfc(ent.get("lhs_si") or "")
        rhs_si = nfc(ent.get("rhs_si") or "")
        if not lhs_si or not rhs_si:
            continue
        # Source node: prefer the existing alias (lhs_alt_si if it's already
        # a known surface), else the lhs_si Sanskrit form.
        src_surf = nfc(ent.get("lhs_alt_si") or "") or lhs_si
        src_id = surface_to_node.get(src_surf)
        if src_id is None:
            # Source not in the formula corpus — emit a node anyway so the
            # substitute edge has a domain.
            existed = False
            src_id = _ensure_substance_node(src_surf, "pratinidhi_source")
            if not existed:
                pr_stats["new_substitute_nodes"] += 1
        # Split rhs into individual substitute substances. Pratinidhi rhs
        # text uses commas / "=" for name-pairs / "හෝ" (= "or") for choices.
        # Conservative: take the first phrase as the canonical substitute.
        rhs_parts = re.split(r"\s*(?:,|හෝ)\s*", rhs_si)
        rhs_parts = [p.strip() for p in rhs_parts if p.strip()]
        for sub in rhs_parts:
            # A part of the form "X = Y" is itself a Sanskrit/Sinhala
            # pair for ONE substitute — keep the first piece as canonical.
            sub_main = sub.split("=")[0].strip()
            if not sub_main or len(sub_main) < 2:
                continue
            existed = nfc(sub_main) in surface_to_node
            sub_id = _ensure_substance_node(sub_main, "pratinidhi_substitute")
            if not existed:
                pr_stats["new_substitute_nodes"] += 1
            if sub_id == src_id:
                continue
            add_edge("SUBSTITUTES_FOR", sub_id, src_id,
                     substitution_rule="abhāva-pratinidhi",
                     provenance={"source_doc":
                                   "data/lexicons/pratinidhi_lookup.json",
                                 "pratinidhi_num": ent.get("num"),
                                 "source_surface_si": src_surf,
                                 "substitute_surface_si": sub_main})
            pr_stats["substitute_edges"] += 1

    # ── 8. Emit CO_OCCURS edges above min threshold; cap at max ──
    sorted_pairs = sorted(co_pairs.items(), key=lambda x: -x[1])
    if max_cooccurrence:
        sorted_pairs = sorted_pairs[:max_cooccurrence]
    for (a, b), n in sorted_pairs:
        if n < min_cooccurrence:
            break
        add_edge("CO_OCCURS", a, b, count=n,
                 confidence=min(1.0, n / 10),
                 provenance={"computed_from": "ingredient_co_occurrence"})

    return nodes, edges, mm_stats, mk_stats, pr_stats


# ── exporters ────────────────────────────────────────────────────────────────
def export_jsonld(nodes, edges, out_path):
    graph = []
    for n in nodes.values():
        item = {"@id": n["id"], "@type": n["type"]}
        for k, v in n.items():
            if k in ("id", "type") or v is None or v == "":
                continue
            item[k] = v
        graph.append(item)
    for e in edges:
        item = {"@type": e["type"], "from": e["from"], "to": e["to"]}
        for k, v in e.items():
            if k in ("type", "from", "to") or v is None:
                continue
            item[k] = v
        graph.append(item)
    doc = {
        "@context": "https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp/docs/context.jsonld",
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "built_at": now_iso(),
        "@graph": graph,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def export_cypher(nodes, edges, out_path):
    lines = ["// Sinhala Traditional Medicine KG — Neo4j Cypher export",
             f"// schema v{SCHEMA_VERSION}  extractor {EXTRACTOR_VERSION}  built {now_iso()}",
             ""]
    # Index for fast MERGE
    for ntype in sorted({n["type"] for n in nodes.values()}):
        lines.append(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{ntype}) REQUIRE n.id IS UNIQUE;")
    lines.append("")
    for n in nodes.values():
        props = {k: v for k, v in n.items() if k not in ("type",)
                 and v not in (None, "", [], {})}
        prop_str = ", ".join(
            f"{k}: {json.dumps(v, ensure_ascii=False)}"
            for k, v in props.items()
        )
        lines.append(f"MERGE (n:{n['type']} {{id: {json.dumps(n['id'])}}}) "
                     f"SET n += {{{prop_str}}};")
    lines.append("")
    for e in edges:
        props = {k: v for k, v in e.items() if k not in ("type", "from", "to")
                 and v not in (None, "", [], {})}
        prop_str = ", ".join(
            f"{k}: {json.dumps(v, ensure_ascii=False)}"
            for k, v in props.items()
        )
        lines.append(
            f"MATCH (a {{id: {json.dumps(e['from'])}}}), "
            f"(b {{id: {json.dumps(e['to'])}}}) "
            f"MERGE (a)-[r:{e['type']} {{{prop_str}}}]->(b);"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def export_turtle(nodes, edges, out_path):
    prefix = "https://nuwan-labs.github.io/sinhala-traditional-medicine-nlp"
    lines = [
        f"@prefix nl: <{prefix}/ns/> .",
        f"@prefix ent: <{prefix}/id/> .",
        f"@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"# Sinhala Traditional Medicine KG — schema v{SCHEMA_VERSION}",
        f"# extractor: {EXTRACTOR_VERSION}   built: {now_iso()}",
        "",
    ]

    def iri(internal_id):
        return f"ent:{slug(internal_id).replace(':', '__')}"

    def lit(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return json.dumps(v)
        return json.dumps(str(v), ensure_ascii=False)

    for n in nodes.values():
        lines.append(f"{iri(n['id'])} a nl:{n['type']} ;")
        prop_lines = []
        for k, v in n.items():
            if k in ("id", "type") or v in (None, "", [], {}):
                continue
            if isinstance(v, dict):
                continue   # nested provenance/external — left out of turtle for brevity
            if isinstance(v, list):
                vals = ", ".join(lit(x) for x in v if x)
                if vals:
                    prop_lines.append(f"    nl:{k} {vals}")
            else:
                prop_lines.append(f"    nl:{k} {lit(v)}")
        lines.append(" ;\n".join(prop_lines) + " .\n" if prop_lines else " .\n")
    for e in edges:
        lines.append(f"{iri(e['from'])} nl:{e['type']} {iri(e['to'])} .")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_report(nodes, edges, mm_stats, mk_stats, pr_stats):
    node_counts = Counter(n["type"] for n in nodes.values())
    edge_counts = Counter(e["type"] for e in edges)

    plants = [n for n in nodes.values() if n["type"] == "Plant"]
    plant_resolved = [n for n in plants if not n.get("is_unresolved")]
    plant_unresolved = [n for n in plants if n.get("is_unresolved")]
    plant_with_powo = sum(1 for n in plants
                          if (n.get("external") or {}).get("powo_lsid"))
    plant_with_latin = sum(1 for n in plants if n.get("latin_binomial"))
    diseases = [n for n in nodes.values() if n["type"] == "Disease"]
    disease_with_tm2 = sum(1 for n in diseases
                           if (n.get("external") or {}).get("icd11_tm2"))

    mm_tagged = sum(1 for n in nodes.values() if n.get("mm_section"))

    return {
        "schema_version":    SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "built_at":          now_iso(),
        "nodes": {
            "total":   sum(node_counts.values()),
            "by_type": dict(node_counts),
        },
        "edges": {
            "total":   len(edges),
            "by_type": dict(edge_counts),
        },
        "plant_resolution": {
            "Plant_resolved_to_sanskrit":     len(plant_resolved),
            "Plant_unresolved_sinhala_only":  len(plant_unresolved),
            "Plant_total":                    len(plants),
            "note": ("Unresolved plant nodes are Sinhala surface forms that "
                     "the resolver did not map to a Sanskrit lemma — typically "
                     "tadbhava or vernacular terms awaiting R3/R4 lexicons."),
        },
        "external_id_coverage": {
            "Plant_with_POWO_LSID":          plant_with_powo,
            "Plant_with_latin_name":         plant_with_latin,
            "Plant_with_POWO_pct_of_resolved": (
                round(100 * plant_with_powo / max(len(plant_resolved), 1), 1)
            ),
            "Disease_with_ICD11_TM2":        disease_with_tm2,
            "Disease_total":                 len(diseases),
        },
        "materia_medica_authority": {
            "ingredients_confirmed":       mm_stats["confirmed"],
            "ingredients_overridden":      dict(mm_stats["override"]),
            "unresolved_classified_by_mm": mm_stats["unresolved_classified"],
            "nodes_tagged_with_mm_authority": mm_tagged,
            "note": ("Counts ingredient surface-forms where the Sri Lankan "
                     "Ayurvedic Pharmacopoeia's categorised raw-materials "
                     "list (pp. 444–453) confirmed or corrected the "
                     "resolver's Plant/Mineral assignment, including new "
                     "AnimalOrigin classifications."),
        },
        "mahakashaya_coverage": {
            "PharmacologicalProperty_nodes": mk_stats["property_nodes"],
            "HAS_PROPERTY_edges":            mk_stats["has_property_edges"],
            "substances_already_in_kg":      mk_stats["substances_with_property"],
            "substances_introduced_new":     mk_stats["substances_new"],
            "note": ("Caraka's 50 mahā-kaṣāya substance groups from "
                     "pp. 82–90 of the source. Each gana → one "
                     "PharmacologicalProperty (axis=karma); each listed "
                     "substance → one HAS_PROPERTY edge."),
        },
        "pratinidhi_substitutes": {
            "SUBSTITUTES_FOR_edges":         pr_stats["substitute_edges"],
            "new_substitute_nodes_added":    pr_stats["new_substitute_nodes"],
            "note": ("Abhāva-pratinidhi substitute relationships from "
                     "pp. 77–81 of the source. The substitute substance "
                     "(rhs_si) is a DIFFERENT substance from the source "
                     "(lhs_si) — use it only when the source is "
                     "unavailable. Modelled in the KG as SUBSTITUTES_FOR "
                     "edges, NOT as a same-meaning alias."),
        },
        "dosage_normalisation": _dosage_report(edges),
    }


def _dosage_report(edges):
    """Counts of CONTAINS edges with quantity_grams populated and by source."""
    c = Counter()
    for e in edges:
        if e["type"] != "CONTAINS":
            continue
        if e.get("quantity_grams"):
            c["with_grams"] += 1
        c[f"source:{e.get('quantity_source') or 'none'}"] += 1
        c[f"unit:{e.get('quantity_unit') or 'unknown'}"] += 1
    total = sum(1 for e in edges if e["type"] == "CONTAINS")
    return {
        "total_CONTAINS":   total,
        "with_grams":       c["with_grams"],
        "pct_with_grams":   round(100 * c["with_grams"] / max(total, 1), 1),
        "by_source":        {k.split(":",1)[1]: v for k, v in c.items() if k.startswith("source:")},
        "by_unit_top":      dict(Counter({k.split(":",1)[1]: v
                                          for k, v in c.items()
                                          if k.startswith("unit:")}).most_common(12)),
        "note": ("CONTAINS edges with their dosage parsed into grams. "
                 "Sources: structured_metric (the original Stage-3 OCR "
                 "extracted ග්‍රෑ/ලී directly); dosage_normaliser "
                 "(grams derived via knowledge_graph/dosage.py from the "
                 "raw quantity text, using the Sri Lankan unit system "
                 "by default).")
    }


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(here / "knowledge_graph"))
    ap.add_argument("--max-cooccurrence", type=int, default=200)
    ap.add_argument("--min-cooccurrence", type=int, default=3)
    ap.add_argument("--no-yogamalawa", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading inputs…")
    inputs = load_inputs(here, include_yogamalawa=not args.no_yogamalawa)
    _load_dosage_registry(here)
    print(f"  formulas: {len(inputs['formulas'])}")
    print(f"  ingredient lexicon entries: {len(inputs['ingredients_lex'])}")
    print(f"  POWO records: {len(inputs['powo'])}")
    print(f"  TM2 records:  {len(inputs['tm2'])}")

    print("Building KG…")
    nodes, edges, mm_stats, mk_stats, pr_stats = build_kg(
        inputs,
        max_cooccurrence=args.max_cooccurrence,
        min_cooccurrence=args.min_cooccurrence)

    print(f"  nodes: {len(nodes)}")
    print(f"  edges: {len(edges)}")

    print("Exporting…")
    export_jsonld(nodes, edges, out_dir / "kg.jsonld")
    export_cypher(nodes, edges, out_dir / "kg.cypher")
    export_turtle(nodes, edges, out_dir / "kg.ttl")

    report = build_report(nodes, edges, mm_stats, mk_stats, pr_stats)
    (out_dir / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"  wrote {out_dir}/kg.jsonld")
    print(f"  wrote {out_dir}/kg.cypher")
    print(f"  wrote {out_dir}/kg.ttl")
    print(f"  wrote {out_dir}/build_report.json")
    print()
    print("=== KG build report ===")
    print(f"  Nodes by type:")
    for k, v in sorted(report["nodes"]["by_type"].items(), key=lambda x: -x[1]):
        print(f"    {k:24s}  {v:6d}")
    print(f"  Edges by type:")
    for k, v in sorted(report["edges"]["by_type"].items(), key=lambda x: -x[1]):
        print(f"    {k:24s}  {v:6d}")
    print(f"  Plant resolution:")
    for k, v in report["plant_resolution"].items():
        if k == "note": continue
        print(f"    {k:32s}  {v}")
    print(f"  External-ID coverage:")
    for k, v in report["external_id_coverage"].items():
        print(f"    {k:32s}  {v}")
    print(f"  Materia-medica authority:")
    for k, v in report["materia_medica_authority"].items():
        if k == "note": continue
        print(f"    {k:32s}  {v}")
    print(f"  Mahā-kaṣāya coverage:")
    for k, v in report["mahakashaya_coverage"].items():
        if k == "note": continue
        print(f"    {k:32s}  {v}")
    print(f"  Pratinidhi substitutes:")
    for k, v in report["pratinidhi_substitutes"].items():
        if k == "note": continue
        print(f"    {k:32s}  {v}")
    print(f"  Dosage normalisation:")
    dr = report["dosage_normalisation"]
    print(f"    total_CONTAINS                  {dr['total_CONTAINS']}")
    print(f"    with_grams                      {dr['with_grams']}  ({dr['pct_with_grams']}%)")
    print(f"    by source                       {dr['by_source']}")
    print(f"    top units                       {dr['by_unit_top']}")


if __name__ == "__main__":
    main()

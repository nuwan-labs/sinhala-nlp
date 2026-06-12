"""
Gazetteer / ICD matching for constituent-concept and indication-concept counts.
Longest-match over a surface set, NFC-normalised, token-boundary aware.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache

from .common import load_json, nfc


@lru_cache(maxsize=1)
def gazetteer():
    return load_json("gazetteer.json")


@lru_cache(maxsize=1)
def _surface_index():
    """Return dict: surface(NFC) -> (primary_type, concept_id). Only single
    canonical entries from by_surface."""
    g = gazetteer()
    idx = {}
    for surf, info in g["by_surface"].items():
        prim = info.get("primary")
        ids = info.get("ids", {})
        cid = ids.get(prim, surf)
        idx[nfc(surf)] = (prim, cid, info.get("subtype"))
    return idx


def ingredient_surfaces():
    return {s: v for s, v in _surface_index().items() if v[0] == "Ingredient"}


def indication_surfaces():
    return {s: v for s, v in _surface_index().items() if v[0] == "Indication"}


def _match_field(text, surface_subset, mode="token_subseq"):
    """Find gazetteer surfaces occurring in `text`.

    mode:
      'substring'    -> surface occurs as raw substring (loosest)
      'token_subseq' -> surface's whitespace tokens occur as a contiguous run
                        in text's tokens (boundary-aware; default)
      'token_exact'  -> single-token surface equals a text token (strictest)

    Returns Counter of concept_id -> hits.
    """
    text = nfc(text)
    toks = text.split()
    hits = Counter()
    surfaces = list(surface_subset.items())
    if mode == "substring":
        for surf, (_, cid, _st) in surfaces:
            if surf and surf in text:
                hits[cid] += text.count(surf)
        return hits
    # token-based: index surfaces by token tuple
    by_tuple = {}
    for surf, (_, cid, _st) in surfaces:
        st = tuple(surf.split())
        if st:
            by_tuple.setdefault(st, cid)
    maxlen = max((len(t) for t in by_tuple), default=1)
    if mode == "token_exact":
        single = {t[0]: cid for t, cid in by_tuple.items() if len(t) == 1}
        for tok in toks:
            if tok in single:
                hits[single[tok]] += 1
        return hits
    # token_subseq: longest contiguous match, non-overlapping
    i = 0
    n = len(toks)
    while i < n:
        matched = False
        for L in range(min(maxlen, n - i), 0, -1):
            cand = tuple(toks[i:i + L])
            if cand in by_tuple:
                hits[by_tuple[cand]] += 1
                i += L
                matched = True
                break
        if not matched:
            i += 1
    return hits

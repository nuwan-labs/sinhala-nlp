"""
dosage.py
─────────
Convert Sinhala quantity-strings from the pharmacopoeia corpus into a
numeric value with units, using the multi-system unit registry at
`data/lexicons/unit_equivalences.json`.

The unit JSON is split into three layers (matches user's design intent):

  1. `symbols`  — symbol → {iast, kind, aliases}. Source-of-truth for
                  surface-form ↔ canonical-iast mapping. No conversion
                  factors live here.

  2. `systems`  — per-system (sri_lankan / yauna_indian / tola_astanga /
                  tola_modern / metric / imperial) tables of
                  `absolute_grams` and `absolute_ml`. The SAME symbol
                  can resolve to DIFFERENT gram values in different
                  systems (e.g. "පල" = 60 g Sri Lankan, 48 g Yauna).

  3. `ladders`  — verbatim `<N> A = 1 B` rows per system, kept for
                  audit traceability.

Public API
──────────
  load_units(path) → UnitRegistry
  registry.to_grams(text, system="sri_lankan", default_density=1.0)
        → {"grams": float | None,
            "ml":    float | None,
            "raw":   str,
            "matched_unit": str | None,
            "matched_count": float | None,
            "system": str,
            "warnings": list[str]}

Examples
────────
  >>> r = load_units("data/lexicons/unit_equivalences.json")
  >>> r.to_grams("කලං 2",        "sri_lankan")["grams"]
  10.0
  >>> r.to_grams("ග්‍රෑ 60",     "sri_lankan")["grams"]
  60.0
  >>> r.to_grams("පල 1",         "sri_lankan")["grams"]
  60.0
  >>> r.to_grams("පල 1",         "yauna_indian")["grams"]
  48.0
  >>> r.to_grams("ලී 2",         "sri_lankan", default_density=0.92)["grams"]
  1840.0   # 2 L of sesame oil
"""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path

DEFAULT_SYSTEM = "sri_lankan"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


# Token-level number parser: handles "1", "2.5", "1/2", "½".
FRAC_MAP = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1/3, "⅔": 2/3,
            "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875}


def _parse_number(tok: str):
    """Parse '2', '2.5', '1/2', '½', '2½'. Returns float or None."""
    if not tok:
        return None
    tok = tok.strip()
    # Pure fraction glyph "½"
    if tok in FRAC_MAP:
        return FRAC_MAP[tok]
    # "2½" — integer + fraction-glyph suffix
    m = re.fullmatch(r"(\d+)([½¼¾⅓⅔⅛⅜⅝⅞])", tok)
    if m:
        return int(m.group(1)) + FRAC_MAP[m.group(2)]
    # "1/2" / "3/4"
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", tok)
    if m:
        denom = int(m.group(2))
        return int(m.group(1)) / denom if denom else None
    # "2", "2.5", "2,5"
    try:
        return float(tok.replace(",", "."))
    except ValueError:
        return None


class UnitRegistry:
    """Loaded registry of symbols + systems."""

    def __init__(self, doc: dict):
        self.doc       = doc
        self.symbols   = {nfc(k): v for k, v in (doc.get("symbols") or {}).items()}
        self.systems   = doc.get("systems") or {}
        self.default_system = doc.get("metadata", {}).get(
            "default_system", DEFAULT_SYSTEM)

        # Build a flat NFC alias → canonical-symbol map for fast lookup.
        # The longest alias wins on conflict (so multi-word units like
        # "තේ හැඳි" match before "හැඳි").
        self._alias_to_symbol: dict[str, str] = {}
        for canonical, meta in self.symbols.items():
            for alias in [canonical] + list(meta.get("aliases") or []):
                self._alias_to_symbol[nfc(alias)] = canonical
        # Order patterns by descending length so longest-match wins.
        self._alias_keys = sorted(self._alias_to_symbol.keys(),
                                  key=lambda k: -len(k))

    # ── symbol resolution ────────────────────────────────────────────────
    def resolve_symbol(self, surface: str) -> str | None:
        """Return canonical symbol for a surface form (alias-aware)."""
        return self._alias_to_symbol.get(nfc(surface))

    def find_unit_in_text(self, text: str) -> str | None:
        """Scan a free-form text for the first canonical unit symbol that
        appears as a substring (longest match wins). Returns canonical
        symbol or None."""
        t = nfc(text)
        for alias in self._alias_keys:
            if alias and alias in t:
                return self._alias_to_symbol[alias]
        return None

    # ── per-system conversion ────────────────────────────────────────────
    def grams_per_unit(self, symbol: str, system: str | None = None) -> float | None:
        """Look up the gram weight of one unit of `symbol` in `system`."""
        sys_name = system or self.default_system
        sys_rec = self.systems.get(sys_name)
        if not sys_rec:
            return None
        g = (sys_rec.get("absolute_grams") or {}).get(symbol)
        if g is not None:
            return float(g)
        # Fallback: any other system that defines this symbol.
        for other_name, other in self.systems.items():
            if other_name == sys_name:
                continue
            g = (other.get("absolute_grams") or {}).get(symbol)
            if g is not None:
                return float(g)
        return None

    def ml_per_unit(self, symbol: str, system: str | None = None) -> float | None:
        sys_name = system or self.default_system
        sys_rec = self.systems.get(sys_name)
        if sys_rec:
            ml = (sys_rec.get("absolute_ml") or {}).get(symbol)
            if ml is not None:
                return float(ml)
        # Fallback: any other system that defines this symbol.
        for other_name, other in self.systems.items():
            if other_name == sys_name:
                continue
            ml = (other.get("absolute_ml") or {}).get(symbol)
            if ml is not None:
                return float(ml)
        return None

    # ── headline parser ──────────────────────────────────────────────────
    def to_grams(self, text: str, system: str | None = None,
                 default_density: float = 1.0):
        """Parse a quantity-string like 'කලං 2' / 'ග්‍රෑ 5' / 'පල 1 කලං 3'
        and return its mass in grams under `system`.

        Multi-unit strings are summed (e.g. '1 පල 3 කලං' → 60 + 15 = 75 g).
        Volume units convert through `default_density` (1.0 for water,
        0.92 for sesame oil, etc.).

        Returns a dict with `grams`, `ml`, plus diagnostic fields. Never
        raises — failures show up as warnings + null grams.
        """
        warnings: list[str] = []
        sys_name = system or self.default_system
        if sys_name not in self.systems:
            warnings.append(f"unknown system '{sys_name}'; using default")
            sys_name = self.default_system

        text = nfc(text or "")
        total_grams: float = 0.0
        total_ml:    float = 0.0
        matched_units: list[str] = []
        matched_counts: list[float] = []
        found_any = False

        # Pass 1 — tokenise and classify each token as number / unit-symbol /
        # other. Handles both word orders ("කලං 2" Sinhala convention and
        # "2 කලං" arithmetic convention).
        raw_tokens = re.findall(r"\d+/\d+|\d+\.\d+|\d+|[½¼¾⅓⅔⅛⅜⅝⅞]|\S+",
                                text, flags=re.UNICODE)
        atoms: list[tuple[str, str | float]] = []   # ("num", v) | ("unit", sym)
        for tok in raw_tokens:
            num = _parse_number(tok)
            if num is not None:
                atoms.append(("num", num))
                continue
            sym = self.resolve_symbol(tok)
            if sym is None:
                # Glued form like "ග්‍රෑ5" → split at the first digit.
                m = re.match(r"^(.+?)(\d.*)$", tok)
                if m:
                    sym = self.resolve_symbol(m.group(1))
                    leftover = _parse_number(m.group(2))
                    if sym is not None:
                        atoms.append(("unit", sym))
                    if leftover is not None:
                        atoms.append(("num", leftover))
                    continue
            if sym is not None:
                atoms.append(("unit", sym))

        # Pass 2 — pair each unit atom with its nearest unattached number
        # (prefer immediate-left, then immediate-right). Default count = 1
        # if no number is found.
        used = [False] * len(atoms)
        pairs: list[tuple[float, str]] = []
        for i, (kind, val) in enumerate(atoms):
            if kind != "unit" or used[i]:
                continue
            n: float | None = None
            # Left neighbour
            if i > 0 and atoms[i-1][0] == "num" and not used[i-1]:
                n = atoms[i-1][1]; used[i-1] = True
            # Right neighbour
            elif i + 1 < len(atoms) and atoms[i+1][0] == "num" and not used[i+1]:
                n = atoms[i+1][1]; used[i+1] = True
            used[i] = True
            pairs.append((n if n is not None else 1.0, val))

        for n, sym in pairs:
            kind = (self.symbols.get(sym) or {}).get("kind")
            if kind == "mass":
                g = self.grams_per_unit(sym, sys_name)
                if g is None:
                    warnings.append(f"no grams known for '{sym}' in '{sys_name}'")
                    continue
                total_grams += n * g
                matched_units.append(sym); matched_counts.append(n); found_any = True
            elif kind == "volume":
                ml = self.ml_per_unit(sym, sys_name)
                if ml is None:
                    warnings.append(f"no ml known for '{sym}' in '{sys_name}'")
                    continue
                total_ml += n * ml
                total_grams += n * ml * default_density
                matched_units.append(sym); matched_counts.append(n); found_any = True
            elif kind == "relative":
                warnings.append(f"relative unit '{sym}' — needs scaling base")
                matched_units.append(sym); matched_counts.append(n); found_any = True
            # other kinds: ignore

        return {
            "raw":            text,
            "system":         sys_name,
            "matched_unit":   matched_units[0] if matched_units else None,
            "matched_units":  matched_units or None,
            "matched_count":  matched_counts[0] if matched_counts else None,
            "matched_counts": matched_counts or None,
            "grams":          total_grams if found_any and total_grams > 0 else None,
            "ml":             total_ml    if found_any and total_ml    > 0 else None,
            "warnings":       warnings or None,
        }


def load_units(path: str | Path) -> UnitRegistry:
    """Load unit_equivalences.json and return a ready-to-use registry."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return UnitRegistry(doc)

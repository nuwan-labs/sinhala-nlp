# Sinhala Traditional Medicine NLP — pipeline orchestration
#
# Determinism note: every target is a pure function of committed inputs.
# Re-running produces byte-identical outputs (see `make audit`).
#
# The Python interpreter: prefer the project venv if present, else python3.
PY := $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)
PIPE := pipeline
LEX := data/lexicons
KG := knowledge_graph

.PHONY: help gazetteer lexicons kg validate prose-demo audit gap clean-derived

help:
	@echo "Targets:"
	@echo "  gazetteer   build data/lexicons/gazetteer.json (Block A)"
	@echo "  lexicons    rebuild materia_medica / pratinidhi / mahakashaya"
	@echo "  kg          rebuild the knowledge graph"
	@echo "  validate    run the 4-layer KG validator"
	@echo "  prose-demo  run the prose extractor on the built-in demo"
	@echo "  audit       run the determinism / exactness / completeness gates (Block E)"
	@echo "  gap         run the iteration-loop gap report (Block F)"

# ── closed-vocabulary lexicons (Stage-3 reference tables) ──────────────────
lexicons:
	$(PY) $(PIPE)/extract_materia_medica.py
	$(PY) $(PIPE)/extract_pratinidhi.py
	$(PY) $(PIPE)/extract_mahakashaya.py

# ── Block A: gazetteer (depends on the lexicons above) ─────────────────────
gazetteer:
	$(PY) $(PIPE)/build_gazetteer.py

# ── knowledge graph + validation ──────────────────────────────────────────
kg:
	$(PY) $(KG)/build.py

validate:
	$(PY) validate/validate_kg.py

# ── prose extractor (Blocks B–F) ───────────────────────────────────────────
prose-demo:
	$(PY) $(PIPE)/extract_prose.py --demo

audit:
	$(PY) $(PIPE)/audit_prose.py --demo

gap:
	$(PY) $(PIPE)/gap_report.py --limit 200

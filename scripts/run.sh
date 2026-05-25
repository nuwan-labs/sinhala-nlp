#!/usr/bin/env bash
# Minimal no-make orchestration for the pipeline. Mirrors the Makefile
# targets one-for-one. Run from the repo root: `bash scripts/run.sh <target>`.
set -euo pipefail

PY="${PY:-$(test -x ../.venv/bin/python && echo ../.venv/bin/python || echo python3)}"
PIPE="pipeline"
KG="knowledge_graph"

usage() {
  cat <<EOF
Usage: bash scripts/run.sh <target>

Targets:
  gazetteer    build data/lexicons/gazetteer.json (Block A)
  lexicons     rebuild materia_medica / pratinidhi / mahakashaya
  kg           rebuild the knowledge graph
  validate     run the 4-layer KG validator
  prose-demo   run the prose extractor on the built-in demo
  audit        run the determinism / exactness / completeness gates (Block E)
  gap          run the iteration-loop gap report (Block F)
EOF
}

case "${1:-help}" in
  lexicons)
    "$PY" "$PIPE/extract_materia_medica.py"
    "$PY" "$PIPE/extract_pratinidhi.py"
    "$PY" "$PIPE/extract_mahakashaya.py"
    ;;
  gazetteer)   "$PY" "$PIPE/build_gazetteer.py" ;;
  kg)          "$PY" "$KG/build.py" ;;
  validate)    "$PY" validate/validate_kg.py ;;
  prose-demo)  "$PY" "$PIPE/extract_prose.py" --demo ;;
  audit)       "$PY" "$PIPE/audit_prose.py" --demo ;;
  gap)         "$PY" "$PIPE/gap_report.py" --limit 200 ;;
  help|*)      usage ;;
esac

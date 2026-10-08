#!/usr/bin/env bash
# Rebuild "Part XVI- XX.docx" from the Markdown sources.
# Usage: ./part-xvi-xx-src/build.sh [reference.docx]
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:-part-xvi-xx-src/reference.docx}"
OUT="Part XVI- XX.docx"
pandoc part-xvi-xx-src/[0-9]*.md \
  -f markdown+pipe_tables+fenced_code_blocks+task_lists \
  --reference-doc="$REF" --highlight-style=tango \
  --toc --toc-depth=2 \
  -o "$OUT"
echo "wrote $OUT"

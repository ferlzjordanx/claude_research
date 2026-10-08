#!/usr/bin/env bash
# Rebuild "Part XVI- XX.docx" from the Markdown sources.
# Usage: ./part16-20-src/build.sh [reference.docx]
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:-part16-20-src/reference.docx}"
pandoc part16-20-src/[0-9]*.md \
  -f markdown+pipe_tables+fenced_code_blocks+task_lists \
  --reference-doc="$REF" --highlight-style=tango --toc --toc-depth=2 \
  -o "Part XVI- XX.docx"
echo "wrote Part XVI- XX.docx"

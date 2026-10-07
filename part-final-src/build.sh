#!/usr/bin/env bash
# Rebuild part-final.docx from the Markdown sources.
# Usage: ./part-final-src/build.sh [reference.docx]
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:-part-final-src/reference.docx}"
pandoc part-final-src/[0-9]*.md \
  -f markdown+pipe_tables+fenced_code_blocks+task_lists \
  --reference-doc="$REF" --highlight-style=tango \
  -o part-final.docx
echo "wrote part-final.docx"

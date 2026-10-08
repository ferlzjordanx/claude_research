#!/usr/bin/env bash
# Rebuild "Part X-XIV.docx" from the Markdown sources.
# Usage: ./py-x-xiv-src/build.sh [reference.docx]
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:-py-x-xiv-src/reference.docx}"
OUT="Part X-XIV.docx"
pandoc py-x-xiv-src/[0-9]*.md \
  -f markdown+pipe_tables+fenced_code_blocks+task_lists \
  --reference-doc="$REF" --highlight-style=tango \
  --toc --toc-depth=2 \
  -o "$OUT"
echo "wrote $OUT"

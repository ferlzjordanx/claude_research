#!/usr/bin/env bash
# Rebuild the Word guide from the Markdown sources.
# Requires: pandoc 3.x, python-docx. Optional: LibreOffice (to pre-populate the Table of Contents;
# otherwise Word fills it when you accept "update fields" on open).
set -euo pipefail
cd "$(dirname "$0")"
OUT=../Units_41-46_Production_Agentic_Engineering_and_AI_Evaluation.docx
pandoc 00_front.md 10_part_xv.md 41_guardrails_security.md 42_structured_output.md 43_hitl_approvals.md \
       20_part_xvi.md 44_evaluation.md 45_observability.md 46_safe_deployment.md \
       -f markdown+pipe_tables+task_lists -t docx --toc --toc-depth=2 --highlight-style=tango -o /tmp/guide_raw.docx
python3 tools/style_docx.py /tmp/guide_raw.docx "$OUT"
echo "wrote $OUT"

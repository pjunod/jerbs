#!/usr/bin/env bash
# Build claude-web/jerbs.skill from source files.
# The .skill format is a ZIP archive containing:
#   jerbs/SKILL.md              <- claude-web/SKILL.md
#   jerbs/criteria_template.json <- shared/criteria_template.json
#   jerbs/scripts/export_results.py <- shared/scripts/export_results.py
#   jerbs/scripts/export_html.py    <- shared/scripts/export_html.py
#   jerbs/templates/results-template.html <- shared/templates/results-template.html
#   jerbs/docs/setup_wizard.md  <- docs/setup_wizard.md
#   jerbs/schemas/results.schema.json <- shared/schemas/results.schema.json

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/claude-web/jerbs.skill"
TMP="$(mktemp -d)"

trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/jerbs/scripts" "$TMP/jerbs/templates" "$TMP/jerbs/docs" "$TMP/jerbs/schemas"
cp "$REPO_ROOT/claude-web/SKILL.md"              "$TMP/jerbs/SKILL.md"
cp "$REPO_ROOT/shared/criteria_template.json"    "$TMP/jerbs/criteria_template.json"
cp "$REPO_ROOT/shared/scripts/export_results.py" "$TMP/jerbs/scripts/export_results.py"
cp "$REPO_ROOT/shared/scripts/export_html.py"    "$TMP/jerbs/scripts/export_html.py"
cp "$REPO_ROOT/shared/templates/results-template.html" "$TMP/jerbs/templates/results-template.html"
cp "$REPO_ROOT/docs/setup_wizard.md"             "$TMP/jerbs/docs/setup_wizard.md"
cp "$REPO_ROOT/shared/schemas/results.schema.json" "$TMP/jerbs/schemas/results.schema.json"

cd "$TMP"
zip -qr "$OUT" jerbs/

echo "Built $OUT"
unzip -l "$OUT"

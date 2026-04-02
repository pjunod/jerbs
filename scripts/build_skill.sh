#!/usr/bin/env bash
# Build claude-web/jerbs.skill from source files.
# The .skill format is a ZIP archive containing:
#   jerbs/SKILL.md              <- claude-web/SKILL.md
#   jerbs/criteria_template.json <- shared/criteria_template.json
#   jerbs/scripts/export_results.py <- shared/scripts/export_results.py
#   jerbs/scripts/export_html.py    <- shared/scripts/export_html.py
#   jerbs/docs/setup_wizard.md  <- docs/setup_wizard.md

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/claude-web/jerbs.skill"
TMP="$(mktemp -d)"

trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/jerbs/scripts" "$TMP/jerbs/docs"
cp "$REPO_ROOT/claude-web/SKILL.md"              "$TMP/jerbs/SKILL.md"
cp "$REPO_ROOT/shared/criteria_template.json"    "$TMP/jerbs/criteria_template.json"
cp "$REPO_ROOT/shared/scripts/export_results.py" "$TMP/jerbs/scripts/export_results.py"
cp "$REPO_ROOT/shared/scripts/export_html.py"    "$TMP/jerbs/scripts/export_html.py"
cp "$REPO_ROOT/docs/setup_wizard.md"             "$TMP/jerbs/docs/setup_wizard.md"

cd "$TMP"
zip -qr "$OUT" jerbs/

echo "Built $OUT"
unzip -l "$OUT"

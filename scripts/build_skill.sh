#!/usr/bin/env bash
# Build claude-web/jerbs.skill from source files.
# The .skill format is a ZIP archive containing:
#   jerbs/SKILL.md              <- claude-web/SKILL.md
#   jerbs/criteria_template.json <- shared/criteria_template.json
#   jerbs/scripts/export_results.py <- shared/scripts/export_results.py

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_ROOT/claude-web/jerbs.skill"
TMP="$(mktemp -d)"

trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/jerbs/scripts"
cp "$REPO_ROOT/claude-web/SKILL.md"              "$TMP/jerbs/SKILL.md"
cp "$REPO_ROOT/shared/criteria_template.json"    "$TMP/jerbs/criteria_template.json"
cp "$REPO_ROOT/shared/scripts/export_results.py" "$TMP/jerbs/scripts/export_results.py"

cd "$TMP"
zip -qr "$OUT" jerbs/

echo "Built $OUT"
unzip -l "$OUT"

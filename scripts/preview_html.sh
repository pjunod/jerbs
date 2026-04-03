#!/usr/bin/env bash
# Generate and open an HTML preview from sample fixture data.
#
# Usage:
#   ./scripts/preview_html.sh                    # terminal theme (default)
#   ./scripts/preview_html.sh --theme cards      # cards theme
#   ./scripts/preview_html.sh path/to/data.json  # custom data file
#
# The fixture at tests/fixtures/sample_results.json covers:
#   - 2 action banners (reply received + awaiting reply)
#   - 4 pass results (with/without draft replies, various sources)
#   - 4 maybe results (with/without draft replies)
#   - 6 fail results (various dealbreakers)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT_FIXTURE="$REPO_ROOT/tests/fixtures/sample_results.json"
OUTPUT="$REPO_ROOT/tests/fixtures/preview.html"

# Parse args
DATA="$DEFAULT_FIXTURE"
THEME_ARG=""
for arg in "$@"; do
    case "$arg" in
        --theme) THEME_ARG="next" ;;
        *)
            if [ "$THEME_ARG" = "next" ]; then
                THEME_ARG="--theme $arg"
            elif [ -f "$arg" ]; then
                DATA="$arg"
            fi
            ;;
    esac
done

cd "$REPO_ROOT"
python shared/scripts/export_html.py "$DATA" "$OUTPUT" $THEME_ARG
open "$OUTPUT"

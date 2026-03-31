#!/usr/bin/env python3
"""
Merges dynamically generated redteam prompts with baseline fallback prompts.

For each plugin category, if the generated output has fewer than --min-per-plugin
test cases, this script supplements with baseline prompts for that category until
the threshold is met. If the generated file is missing or unreadable, all baseline
prompts are used.

Usage:
    python merge_prompts.py \\
        --generated /tmp/redteam-generated.yaml \\
        --baseline tests/redteam/prompts-baseline.yaml \\
        --output /tmp/redteam-merged.yaml \\
        --min-per-plugin 5
"""

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def plugin_id(test: dict) -> str:
    return test.get("metadata", {}).get("pluginId", "unknown")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", help="Path to promptfoo redteam generate output (optional)")
    parser.add_argument("--baseline", required=True, help="Path to baseline fallback prompts")
    parser.add_argument("--output", required=True, help="Output path for merged config")
    parser.add_argument(
        "--min-per-plugin",
        type=int,
        default=5,
        help="Minimum tests per plugin before supplementing with baseline (default: 5)",
    )
    args = parser.parse_args()

    # --- Load baseline (always required) ---
    baseline_config = load_yaml(args.baseline)
    baseline_tests = baseline_config.get("tests", [])

    baseline_by_plugin: dict[str, list] = defaultdict(list)
    for test in baseline_tests:
        baseline_by_plugin[plugin_id(test)].append(test)

    # --- Load generated tests (optional) ---
    generated_tests: list = []
    generated_config: dict = {}
    if args.generated and Path(args.generated).exists():
        try:
            generated_config = load_yaml(args.generated)
            generated_tests = generated_config.get("tests", []) or []
        except Exception as e:
            print(
                f"[merge_prompts] Warning: could not load generated file: {e}",
                file=sys.stderr,
            )

    # --- Build merged test list ---
    if not generated_tests:
        print(
            "[merge_prompts] No generated tests found — using all baseline tests.",
            file=sys.stderr,
        )
        merged_tests = list(baseline_tests)
    else:
        # Count generated tests per plugin (handle sub-plugin IDs like pii:api-db)
        generated_by_plugin: dict[str, list] = defaultdict(list)
        for test in generated_tests:
            generated_by_plugin[plugin_id(test)].append(test)

        for pid, tests in sorted(generated_by_plugin.items()):
            print(f"[merge_prompts]   {pid}: {len(tests)} generated", file=sys.stderr)

        def gen_count_for(baseline_pid: str) -> int:
            """Count generated tests for a baseline plugin, including sub-plugin IDs."""
            return sum(
                len(tests)
                for gpid, tests in generated_by_plugin.items()
                if gpid == baseline_pid or gpid.startswith(baseline_pid + ":")
            )

        # Start with all generated tests, then supplement any thin plugin categories
        merged_tests = list(generated_tests)
        for pid, fallback_tests in sorted(baseline_by_plugin.items()):
            gen_count = gen_count_for(pid)
            if gen_count < args.min_per_plugin:
                needed = args.min_per_plugin - gen_count
                supplement = fallback_tests[:needed]
                print(
                    f"[merge_prompts]   {pid}: only {gen_count} generated "
                    f"(< {args.min_per_plugin}) — adding {len(supplement)} baseline tests",
                    file=sys.stderr,
                )
                merged_tests.extend(supplement)

    # --- Build output config ---
    # When generation succeeded, use the generated config's top-level structure
    # (it carries purpose:, targets:, redteam: needed by `promptfoo redteam eval`).
    # Fall back to baseline's top-level structure when generation was skipped entirely.
    base_config = generated_config if generated_tests else baseline_config
    output_config = {k: v for k, v in base_config.items() if k != "tests"}
    output_config["tests"] = merged_tests

    # Summarise by plugin
    counts: dict[str, int] = defaultdict(int)
    for test in merged_tests:
        counts[plugin_id(test)] += 1
    print("[merge_prompts] Final test counts:", file=sys.stderr)
    for pid, n in sorted(counts.items()):
        print(f"[merge_prompts]   {pid}: {n}", file=sys.stderr)
    print(
        f"[merge_prompts] Total: {len(merged_tests)} tests → {args.output}",
        file=sys.stderr,
    )

    with open(args.output, "w") as f:
        yaml.dump(output_config, f, default_flow_style=False, allow_unicode=True)


if __name__ == "__main__":
    main()

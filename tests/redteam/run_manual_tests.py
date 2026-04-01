#!/usr/bin/env python3
"""
Local runner for hand-crafted kill chain tests — no promptfoo/Node required.

Reads test cases from promptfooconfig-manual.yaml, sends each to the local
harness server, and evaluates not-contains assertions. LLM-rubric assertions
are skipped (they need an LLM grader); not-contains checks catch the majority
of failure modes.

Usage:
    python run_manual_tests.py [--url http://localhost:8675/screen]
"""

import argparse
import sys

import requests
import yaml


def load_tests(path: str) -> list[dict]:
    with open(path) as f:
        config = yaml.safe_load(f)
    return config.get("tests", [])


def check_not_contains(output: str, assertions: list[dict]) -> list[str]:
    """Return list of failure reasons for not-contains assertions."""
    failures = []
    for a in assertions:
        if a.get("type") != "not-contains":
            continue
        needle = a["value"]
        if needle in output:
            failures.append(f'Output contains "{needle}"')
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8675/screen")
    parser.add_argument(
        "--config",
        default="promptfooconfig-manual.yaml",
        help="Path to manual test config (default: promptfooconfig-manual.yaml)",
    )
    args = parser.parse_args()

    tests = load_tests(args.config)
    passed = 0
    failed = 0
    errors = 0

    for i, test in enumerate(tests, 1):
        desc = test.get("description", f"Test {i}")
        prompt = test.get("vars", {}).get("prompt", "")
        assertions = test.get("assert", [])

        try:
            resp = requests.post(
                args.url,
                json={"prompt": prompt},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            data = resp.json()
        except Exception as e:
            print(f"  [{i:>2}] ERROR  {desc}")
            print(f"         {e}")
            errors += 1
            continue

        if "error" in data:
            print(f"  [{i:>2}] ERROR  {desc}")
            print(f"         Server error: {data['error']}")
            errors += 1
            continue

        output = data.get("output", "")
        findings = data.get("metadata", {}).get("findings", [])
        failures = check_not_contains(output, assertions)

        if failures:
            failed += 1
            print(f"  [{i:>2}] FAIL   {desc}")
            for f in failures:
                print(f"         {f}")
            print(f"         output: {output[:200]}")
        else:
            passed += 1
            print(f"  [{i:>2}] PASS   {desc}")
            if findings:
                print(f"         (leak scan findings in full response: {len(findings)})")

    total = passed + failed + errors
    print(f"\n{'=' * 60}")
    print(f"Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Errors: {errors}")

    if failed > 0 or errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Write GitHub Actions step summary for Codeshift migrations.

Reads migration state and step outputs, then writes a formatted
summary to GITHUB_STEP_SUMMARY for display in the Actions UI.
"""

import json
import os
import sys
from pathlib import Path

# Ensure sibling modules are importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

from generate_report import generate_github_step_summary


def get_env(name: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(name, default)


def load_state() -> dict | None:
    """Load migration state from .codeshift/state.json."""
    state_file = Path(".codeshift/state.json")
    if not state_file.exists():
        return None

    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to load state: {e}")
        return None


def main() -> int:
    """Main entry point."""
    state = load_state()
    if not state:
        print("No migration state found. Skipping step summary.")
        return 0

    migrations_info = state.get("migrations_info", [])
    results = state.get("results", [])
    risk_assessment = state.get("risk_assessment", {})

    # Read step outputs from environment
    test_passed_str = get_env("INPUT_TEST_PASSED", "")
    test_passed: bool | None = None
    if test_passed_str:
        test_passed = test_passed_str.lower() == "true"

    pr_url = get_env("INPUT_PR_URL", "") or None

    # Generate summary
    summary = generate_github_step_summary(
        migrations_info=migrations_info,
        results=results,
        risk_assessment=risk_assessment,
        test_passed=test_passed,
        pr_url=pr_url,
    )

    # Write to GITHUB_STEP_SUMMARY
    summary_file = get_env("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as f:
            f.write(summary + "\n")
        print("Step summary written successfully.")
    else:
        # Fallback: print to stdout for local testing
        print(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())

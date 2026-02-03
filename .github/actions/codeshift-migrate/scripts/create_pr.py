#!/usr/bin/env python3
"""PR creation script for GitHub Actions.

This script creates a pull request with migration changes, including
detailed changelogs, risk assessments, and test results.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from generate_report import (
    format_breaking_changes,
    format_files_changed,
    format_migration_table,
    format_risk_assessment,
    format_test_results,
)


def get_env(name: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(name, default)


def write_github_output(name: str, value: str) -> None:
    """Write output to GitHub Actions."""
    output_file = get_env("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}")


def run_command(
    cmd: list[str], capture: bool = True, check: bool = False
) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result.returncode, result.stdout or "", result.stderr or ""


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


def create_branch(branch_name: str) -> bool:
    """Create and checkout a new branch."""
    exit_code, _, _ = run_command(["git", "checkout", "-b", branch_name])
    return exit_code == 0


def apply_changes() -> bool:
    """Apply codeshift changes."""
    exit_code, _, _ = run_command(["codeshift", "apply", "--yes"], capture=False)
    return exit_code == 0


def commit_changes(message: str) -> bool:
    """Stage and commit all changes."""
    # Stage all changes
    run_command(["git", "add", "-A"])

    # Check if there are changes to commit
    exit_code, stdout, _ = run_command(["git", "status", "--porcelain"])
    if not stdout.strip():
        print("No changes to commit")
        return False

    # Commit
    exit_code, _, _ = run_command(["git", "commit", "-m", message])
    return exit_code == 0


def push_branch(branch_name: str) -> bool:
    """Push branch to remote."""
    exit_code, _, _ = run_command(["git", "push", "-u", "origin", branch_name])
    return exit_code == 0


def create_pr(title: str, body: str, base_branch: str) -> tuple[str, str]:
    """Create a pull request using gh CLI."""
    cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--base",
        base_branch,
    ]

    exit_code, stdout, stderr = run_command(cmd)
    if exit_code != 0:
        print(f"Failed to create PR: {stderr}")
        return "", ""

    # Extract PR URL from output
    pr_url = stdout.strip()

    # Get PR number
    exit_code, stdout, _ = run_command(
        ["gh", "pr", "view", "--json", "number", "--jq", ".number"]
    )
    pr_number = stdout.strip() if exit_code == 0 else ""

    return pr_url, pr_number


def generate_pr_body(
    state: dict,
    test_passed: bool | None,
    test_command: str,
    run_tests: bool,
) -> str:
    """Generate the PR body with all migration details."""
    migrations_info = state.get("migrations_info", [])
    results = state.get("results", [])
    risk_assessment = state.get("risk_assessment", {})

    # Build PR body sections
    sections = []

    # Summary section
    sections.append("## Summary\n")
    sections.append(
        "This pull request contains automated dependency migrations performed by Codeshift.\n"
    )

    # Migration table
    migration_table = format_migration_table(migrations_info, results)
    sections.append(f"\n{migration_table}\n")

    # Risk assessment section
    risk_section = format_risk_assessment(risk_assessment)
    sections.append(f"\n{risk_section}\n")

    # Test results section (if tests were run)
    if run_tests:
        test_section = format_test_results(test_passed, test_command)
        sections.append(f"\n{test_section}\n")

    # Files changed section
    files_section = format_files_changed(results)
    sections.append(f"\n{files_section}\n")

    # Breaking changes section
    breaking_section = format_breaking_changes(migrations_info)
    if breaking_section:
        sections.append(f"\n{breaking_section}\n")

    # Footer
    sections.append("\n---\n")
    sections.append(
        "Generated with [Codeshift](https://github.com/Ragab-Technologies/codeshift)"
    )

    return "\n".join(sections)


def generate_commit_message(state: dict) -> str:
    """Generate a conventional commit message."""
    migrations_info = state.get("migrations_info", [])

    if len(migrations_info) == 1:
        m = migrations_info[0]
        return f"chore(deps): migrate {m['name']} from {m['current']} to {m['latest']}"
    else:
        libs = [m["name"] for m in migrations_info[:3]]
        libs_str = ", ".join(libs)
        if len(migrations_info) > 3:
            libs_str += f" and {len(migrations_info) - 3} more"
        return f"chore(deps): migrate {libs_str}"


def generate_pr_title(state: dict) -> str:
    """Generate PR title."""
    migrations_info = state.get("migrations_info", [])

    if len(migrations_info) == 1:
        m = migrations_info[0]
        return f"chore(deps): Migrate {m['name']} {m['current']} -> {m['latest']}"
    else:
        return f"chore(deps): Migrate {len(migrations_info)} dependencies"


def main() -> int:
    """Main entry point."""
    # Parse inputs
    base_branch = get_env("INPUT_BASE_BRANCH", "main")
    branch_prefix = get_env("INPUT_BRANCH_PREFIX", "codeshift/migration")
    test_passed_str = get_env("INPUT_TEST_PASSED", "")
    test_command = get_env("INPUT_TEST_COMMAND", "pytest")
    run_tests = get_env("INPUT_RUN_TESTS", "true").lower() == "true"

    test_passed: bool | None = None
    if test_passed_str:
        test_passed = test_passed_str.lower() == "true"

    print("=" * 60)
    print("Codeshift PR Creation - GitHub Action")
    print("=" * 60)
    print(f"Base branch: {base_branch}")
    print(f"Branch prefix: {branch_prefix}")
    print(f"Tests run: {run_tests}")
    if test_passed is not None:
        print(f"Tests passed: {test_passed}")
    print("=" * 60)

    # Load state
    state = load_state()
    if not state:
        print("No migration state found. Nothing to do.")
        write_github_output("pr-url", "")
        write_github_output("pr-number", "")
        return 0

    results = state.get("results", [])
    if not results:
        print("No changes in migration state. Nothing to do.")
        write_github_output("pr-url", "")
        write_github_output("pr-number", "")
        return 0

    # Generate branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"{branch_prefix}-{timestamp}"

    print(f"\n[1/5] Creating branch: {branch_name}")
    if not create_branch(branch_name):
        print("Failed to create branch")
        return 1

    print("\n[2/5] Applying changes...")
    if not apply_changes():
        print("Failed to apply changes")
        return 1

    print("\n[3/5] Committing changes...")
    commit_message = generate_commit_message(state)
    if not commit_changes(commit_message):
        print("No changes to commit or commit failed")
        # Still try to return to original branch
        run_command(["git", "checkout", base_branch])
        return 0

    print("\n[4/5] Pushing branch...")
    if not push_branch(branch_name):
        print("Failed to push branch")
        return 1

    print("\n[5/5] Creating pull request...")
    pr_title = generate_pr_title(state)
    pr_body = generate_pr_body(state, test_passed, test_command, run_tests)

    pr_url, pr_number = create_pr(pr_title, pr_body, base_branch)
    if not pr_url:
        print("Failed to create pull request")
        return 1

    print(f"\nPull request created: {pr_url}")

    # Write outputs
    write_github_output("pr-url", pr_url)
    write_github_output("pr-number", pr_number)

    return 0


if __name__ == "__main__":
    sys.exit(main())

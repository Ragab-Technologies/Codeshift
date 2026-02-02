#!/usr/bin/env python3
"""Migration orchestration script for GitHub Actions.

This script runs codeshift migrations and outputs results in GitHub Actions format.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_env(name: str, default: str = "") -> str:
    """Get environment variable with default."""
    return os.environ.get(name, default)


def write_github_output(name: str, value: str) -> None:
    """Write output to GitHub Actions."""
    output_file = get_env("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            # Handle multiline values
            if "\n" in value:
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")
    else:
        # Fallback for local testing
        print(f"::set-output name={name}::{value}")


def run_command(cmd: list[str], capture: bool = True) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    return result.returncode, result.stdout or "", result.stderr or ""


def parse_libraries(libraries_str: str) -> list[str]:
    """Parse comma-separated library list."""
    if not libraries_str:
        return []
    return [lib.strip() for lib in libraries_str.split(",") if lib.strip()]


def run_scan() -> dict:
    """Run codeshift scan and return results."""
    cmd = ["codeshift", "scan", "--json-output", "--fetch-changes"]
    exit_code, stdout, stderr = run_command(cmd)

    if exit_code != 0:
        print(f"Scan failed: {stderr}")
        return {"outdated": [], "migrations": []}

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse scan output: {stdout}")
        return {"outdated": [], "migrations": []}


def filter_migrations(
    migrations: list[dict], libraries: list[str], tier1_only: bool
) -> list[dict]:
    """Filter migrations by library list and tier settings."""
    filtered = []

    for migration in migrations:
        name = migration.get("name", "")

        # Filter by library list if specified
        if libraries and name not in libraries:
            continue

        # Filter by tier if tier1-only is set
        if tier1_only and not migration.get("is_tier1", False):
            continue

        filtered.append(migration)

    return filtered


def run_upgrade(library: str, target_version: str) -> tuple[bool, str]:
    """Run codeshift upgrade for a single library."""
    cmd = ["codeshift", "upgrade", library, "--target", target_version]
    exit_code, stdout, stderr = run_command(cmd)

    if exit_code != 0:
        return False, stderr

    return True, stdout


def run_upgrade_all(libraries: list[str], tier1_only: bool) -> bool:
    """Run codeshift upgrade-all command."""
    cmd = ["codeshift", "upgrade-all"]

    if tier1_only:
        cmd.append("--tier1-only")

    if libraries:
        for lib in libraries:
            cmd.extend(["--include", lib])

    exit_code, stdout, stderr = run_command(cmd, capture=False)
    return exit_code == 0


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


def assess_risk(state: dict) -> dict:
    """Assess risk using RiskAssessor."""
    try:
        from codeshift.analyzer.risk_assessor import RiskAssessor, RiskLevel
        from codeshift.migrator.ast_transforms import TransformResult, TransformStatus

        # Reconstruct TransformResults from state
        results = []
        for result_data in state.get("results", []):
            # Create minimal TransformResult for risk assessment
            from pathlib import Path

            from codeshift.migrator.ast_transforms import TransformChange

            result = TransformResult(
                file_path=Path(result_data["file_path"]),
                status=TransformStatus(result_data.get("status", "success")),
                original_code=result_data.get("original_code", ""),
                transformed_code=result_data.get("transformed_code", ""),
                changes=[
                    TransformChange(
                        description=c.get("description", ""),
                        line_number=c.get("line_number", 1),
                        original=c.get("original", ""),
                        replacement=c.get("replacement", ""),
                        transform_name=c.get("transform_name", ""),
                    )
                    for c in result_data.get("changes", [])
                ],
            )
            results.append(result)

        assessor = RiskAssessor()
        assessment = assessor.assess(results)

        return {
            "overall_risk": assessment.overall_risk.value,
            "confidence_score": assessment.confidence_score,
            "is_safe": assessment.is_safe,
            "factors": [
                {
                    "name": f.name,
                    "description": f.description,
                    "severity": f.severity.value,
                    "score": f.score,
                    "mitigation": f.mitigation,
                }
                for f in assessment.factors
            ],
            "recommendations": assessment.recommendations,
        }
    except ImportError as e:
        print(f"Could not import risk assessor: {e}")
        return {
            "overall_risk": "medium",
            "confidence_score": 0.5,
            "is_safe": False,
            "factors": [],
            "recommendations": ["Install codeshift to enable risk assessment"],
        }


def should_auto_apply(risk_assessment: dict, max_risk_level: str) -> bool:
    """Determine if changes should be auto-applied based on risk."""
    risk_order = ["low", "medium", "high", "critical"]
    current_risk = risk_assessment.get("overall_risk", "high")
    max_risk = max_risk_level.lower()

    try:
        current_idx = risk_order.index(current_risk)
        max_idx = risk_order.index(max_risk)
        return current_idx <= max_idx and risk_assessment.get("is_safe", False)
    except ValueError:
        return False


def main() -> int:
    """Main entry point."""
    # Parse inputs
    libraries_str = get_env("INPUT_LIBRARIES", "")
    tier1_only = get_env("INPUT_TIER1_ONLY", "true").lower() == "true"
    max_risk_level = get_env("INPUT_MAX_RISK_LEVEL", "medium")
    auto_apply = get_env("INPUT_AUTO_APPLY", "true").lower() == "true"

    libraries = parse_libraries(libraries_str)

    print("=" * 60)
    print("Codeshift Migration - GitHub Action")
    print("=" * 60)
    print(f"Libraries: {libraries or 'all'}")
    print(f"Tier 1 only: {tier1_only}")
    print(f"Max risk level: {max_risk_level}")
    print(f"Auto apply: {auto_apply}")
    print("=" * 60)

    # Step 1: Scan for outdated packages
    print("\n[1/4] Scanning for outdated packages...")
    scan_result = run_scan()

    migrations = scan_result.get("migrations", [])
    if not migrations:
        print("No migrations available.")
        write_github_output("migrations-count", "0")
        write_github_output("files-changed", "0")
        write_github_output("risk-level", "none")
        return 0

    # Step 2: Filter migrations
    print("\n[2/4] Filtering migrations...")
    filtered_migrations = filter_migrations(migrations, libraries, tier1_only)

    if not filtered_migrations:
        print("No migrations match the criteria.")
        write_github_output("migrations-count", "0")
        write_github_output("files-changed", "0")
        write_github_output("risk-level", "none")
        return 0

    print(f"Found {len(filtered_migrations)} migration(s):")
    for m in filtered_migrations:
        tier = "Tier 1" if m.get("is_tier1") else "Tier 2/3"
        print(f"  - {m['name']}: {m['current']} -> {m['latest']} ({tier})")

    # Step 3: Run migrations
    print("\n[3/4] Running migrations...")

    if len(filtered_migrations) == 1:
        # Single library upgrade
        m = filtered_migrations[0]
        success, output = run_upgrade(m["name"], m["latest"])
        if not success:
            print(f"Migration failed: {output}")
            return 1
    else:
        # Multi-library upgrade
        lib_names = [m["name"] for m in filtered_migrations]
        success = run_upgrade_all(lib_names, tier1_only)
        if not success:
            print("Migration failed")
            return 1

    # Step 4: Assess risk and determine next steps
    print("\n[4/4] Assessing risk...")
    state = load_state()

    if not state:
        print("No state file found - no changes needed.")
        write_github_output("migrations-count", str(len(filtered_migrations)))
        write_github_output("files-changed", "0")
        write_github_output("risk-level", "none")
        return 0

    results = state.get("results", [])
    files_changed = len(results)
    total_changes = sum(r.get("change_count", 0) for r in results)

    print(f"Files changed: {files_changed}")
    print(f"Total changes: {total_changes}")

    risk_assessment = assess_risk(state)
    risk_level = risk_assessment.get("overall_risk", "medium")
    confidence = risk_assessment.get("confidence_score", 0.5)

    print(f"Risk level: {risk_level}")
    print(f"Confidence: {confidence:.0%}")

    # Save risk assessment to state for PR creation
    state["risk_assessment"] = risk_assessment
    state["migrations_info"] = filtered_migrations
    Path(".codeshift/state.json").write_text(json.dumps(state, indent=2, default=str))

    # Generate JSON report
    report_path = Path(".codeshift/migration-report.json")
    report = {
        "migrations": filtered_migrations,
        "results": [
            {
                "file": r.get("file_path"),
                "changes": r.get("change_count", 0),
                "status": r.get("status", "success"),
            }
            for r in results
        ],
        "risk_assessment": risk_assessment,
        "summary": {
            "migrations_count": len(filtered_migrations),
            "files_changed": files_changed,
            "total_changes": total_changes,
        },
    }
    report_path.write_text(json.dumps(report, indent=2, default=str))

    # Write outputs
    write_github_output("migrations-count", str(len(filtered_migrations)))
    write_github_output("files-changed", str(files_changed))
    write_github_output("risk-level", risk_level)
    write_github_output("json-report", str(report_path))

    # Auto-apply if conditions are met
    if auto_apply and files_changed > 0:
        if should_auto_apply(risk_assessment, max_risk_level):
            print(f"\nRisk level ({risk_level}) is within threshold ({max_risk_level}).")
            print("Changes will be applied when PR is created.")
        else:
            print(f"\nRisk level ({risk_level}) exceeds threshold ({max_risk_level}).")
            print("Manual review recommended before applying changes.")

    print("\nMigration analysis complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

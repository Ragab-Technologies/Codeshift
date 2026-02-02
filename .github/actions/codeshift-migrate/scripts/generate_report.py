#!/usr/bin/env python3
"""Report generation utilities for GitHub Actions.

Provides functions to format migration state into markdown tables,
risk assessments, and other PR body components.
"""

from pathlib import Path


def format_migration_table(migrations_info: list[dict], results: list[dict]) -> str:
    """Format migrations into a markdown table.

    Args:
        migrations_info: List of migration dictionaries with library info
        results: List of transform results with file changes

    Returns:
        Markdown formatted table
    """
    if not migrations_info:
        return "No migrations performed."

    # Build a map of library -> changes count
    library_changes: dict[str, int] = {}
    library_files: dict[str, int] = {}
    for result in results:
        lib = result.get("library", "unknown")
        library_changes[lib] = library_changes.get(lib, 0) + result.get("change_count", 0)
        library_files[lib] = library_files.get(lib, 0) + 1

    lines = [
        "### Migration Summary",
        "",
        "| Library | From | To | Files | Changes | Tier | Risk |",
        "|---------|------|-----|-------|---------|------|------|",
    ]

    for m in migrations_info:
        name = m.get("name", "unknown")
        current = m.get("current", "?")
        latest = m.get("latest", "?")
        is_tier1 = m.get("is_tier1", False)
        tier = "1" if is_tier1 else "2/3"

        files = library_files.get(name, 0)
        changes = library_changes.get(name, 0)

        # Risk is low for Tier 1, medium for Tier 2/3
        risk = "Low" if is_tier1 else "Medium"
        risk_emoji = ":white_check_mark:" if is_tier1 else ":warning:"

        lines.append(
            f"| `{name}` | {current} | {latest} | {files} | {changes} | Tier {tier} | {risk_emoji} {risk} |"
        )

    total_files = len(results)
    total_changes = sum(r.get("change_count", 0) for r in results)
    lines.append(f"| **Total** | | | **{total_files}** | **{total_changes}** | | |")

    return "\n".join(lines)


def format_risk_assessment(risk_assessment: dict) -> str:
    """Format risk assessment into markdown.

    Args:
        risk_assessment: Risk assessment dictionary from RiskAssessor

    Returns:
        Markdown formatted risk assessment section
    """
    if not risk_assessment:
        return ""

    overall_risk = risk_assessment.get("overall_risk", "unknown")
    confidence = risk_assessment.get("confidence_score", 0)
    is_safe = risk_assessment.get("is_safe", False)
    factors = risk_assessment.get("factors", [])
    recommendations = risk_assessment.get("recommendations", [])

    # Risk level emoji and color
    risk_display = {
        "low": (":white_check_mark:", "Low"),
        "medium": (":warning:", "Medium"),
        "high": (":large_orange_diamond:", "High"),
        "critical": (":red_circle:", "Critical"),
    }

    emoji, label = risk_display.get(overall_risk, (":question:", overall_risk.title()))

    lines = [
        "### Risk Assessment",
        "",
        f"**Overall Risk:** {emoji} {label}",
        f"**Confidence:** {confidence:.0%}",
        f"**Auto-apply Safe:** {'Yes' if is_safe else 'No'}",
        "",
    ]

    # Risk factors table
    if factors:
        lines.extend(
            [
                "<details>",
                "<summary>Risk Factors</summary>",
                "",
                "| Factor | Severity | Score | Details |",
                "|--------|----------|-------|---------|",
            ]
        )

        for factor in factors:
            name = factor.get("name", "")
            severity = factor.get("severity", "unknown")
            score = factor.get("score", 0)
            description = factor.get("description", "")

            # Truncate long descriptions
            if len(description) > 60:
                description = description[:57] + "..."

            lines.append(f"| {name} | {severity.title()} | {score:.1%} | {description} |")

        lines.extend(["", "</details>", ""])

    # Recommendations
    if recommendations:
        lines.extend(["**Recommendations:**", ""])
        for rec in recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)


def format_test_results(test_passed: bool | None, test_command: str) -> str:
    """Format test results into markdown.

    Args:
        test_passed: Whether tests passed, or None if not run
        test_command: The test command that was used

    Returns:
        Markdown formatted test results section
    """
    lines = ["### Test Results", ""]

    if test_passed is None:
        lines.append(":heavy_minus_sign: Tests were not run.")
    elif test_passed:
        lines.append(":white_check_mark: **Tests Passed**")
        lines.append("")
        lines.append(f"Command: `{test_command}`")
    else:
        lines.append(":x: **Tests Failed**")
        lines.append("")
        lines.append(f"Command: `{test_command}`")
        lines.append("")
        lines.append(
            "> **Note:** Please review the test failures before merging this PR."
        )

    return "\n".join(lines)


def format_files_changed(results: list[dict]) -> str:
    """Format files changed into a collapsible section.

    Args:
        results: List of transform results

    Returns:
        Markdown formatted files changed section
    """
    if not results:
        return ""

    lines = [
        "### Files Changed",
        "",
        "<details>",
        f"<summary>{len(results)} file(s) modified</summary>",
        "",
        "| File | Changes | Status |",
        "|------|---------|--------|",
    ]

    for result in results:
        file_path = result.get("file_path", "unknown")
        # Show relative path if possible
        try:
            rel_path = Path(file_path).name
        except Exception:
            rel_path = file_path

        changes = result.get("change_count", 0)
        status = result.get("status", "success")

        status_emoji = {
            "success": ":white_check_mark:",
            "partial": ":warning:",
            "failed": ":x:",
            "no_changes": ":heavy_minus_sign:",
        }.get(status, ":question:")

        lines.append(f"| `{rel_path}` | {changes} | {status_emoji} {status.title()} |")

    lines.extend(["", "</details>"])

    return "\n".join(lines)


def format_breaking_changes(migrations_info: list[dict]) -> str:
    """Format breaking changes addressed into markdown.

    Args:
        migrations_info: List of migration dictionaries

    Returns:
        Markdown formatted breaking changes section, or empty string
    """
    # Check if any migrations have breaking changes info
    has_changes = any(m.get("changes") or m.get("breaking_changes") for m in migrations_info)

    if not has_changes:
        return ""

    lines = [
        "### Breaking Changes Addressed",
        "",
        "<details>",
        "<summary>View breaking changes</summary>",
        "",
    ]

    for m in migrations_info:
        name = m.get("name", "unknown")
        changes = m.get("changes", [])
        breaking_count = m.get("breaking_changes", 0)

        if not changes and not breaking_count:
            continue

        lines.append(f"#### {name}")
        lines.append("")

        if changes:
            for change in changes[:5]:  # Limit to 5 changes
                old_api = change.get("old_api", "")
                new_api = change.get("new_api", "")
                description = change.get("description", "")

                if new_api:
                    lines.append(f"- `{old_api}` -> `{new_api}`")
                else:
                    lines.append(f"- `{old_api}` (removed)")

                if description:
                    lines.append(f"  - {description}")

            if len(changes) > 5:
                lines.append(f"- ... and {len(changes) - 5} more changes")

            lines.append("")
        elif breaking_count:
            lines.append(f"- {breaking_count} breaking change(s) detected")
            lines.append("")

    lines.extend(["</details>"])

    return "\n".join(lines)


def generate_github_step_summary(
    migrations_info: list[dict],
    results: list[dict],
    risk_assessment: dict,
    test_passed: bool | None,
    pr_url: str | None,
) -> str:
    """Generate a GitHub Actions step summary.

    Args:
        migrations_info: List of migration dictionaries
        results: List of transform results
        risk_assessment: Risk assessment dictionary
        test_passed: Whether tests passed
        pr_url: URL of the created PR

    Returns:
        Markdown formatted step summary
    """
    lines = ["# Codeshift Migration Summary", ""]

    # Quick stats
    total_files = len(results)
    total_changes = sum(r.get("change_count", 0) for r in results)
    risk_level = risk_assessment.get("overall_risk", "unknown")

    lines.extend(
        [
            "## Quick Stats",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Migrations | {len(migrations_info)} |",
            f"| Files Changed | {total_files} |",
            f"| Total Changes | {total_changes} |",
            f"| Risk Level | {risk_level.title()} |",
        ]
    )

    if test_passed is not None:
        test_status = "Passed" if test_passed else "Failed"
        lines.append(f"| Tests | {test_status} |")

    if pr_url:
        lines.append(f"| Pull Request | [View PR]({pr_url}) |")

    lines.append("")

    # Migration details
    lines.append(format_migration_table(migrations_info, results))

    return "\n".join(lines)

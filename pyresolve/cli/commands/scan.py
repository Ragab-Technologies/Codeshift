"""Scan command for discovering all possible migrations in a project."""

import json
from pathlib import Path
from typing import Any, Optional, cast

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from pyresolve.knowledge import (
    generate_knowledge_base_sync,
    is_tier_1_library,
)
from pyresolve.scanner import DependencyParser
from pyresolve.utils.config import ProjectConfig

console = Console()


def get_latest_version(package: str) -> Optional[str]:
    """Fetch the latest version of a package from PyPI.

    Args:
        package: Package name.

    Returns:
        Latest version string or None.
    """
    try:
        response = httpx.get(f"https://pypi.org/pypi/{package}/json", timeout=10.0)
        if response.status_code == 200:
            return cast(Optional[str], response.json().get("info", {}).get("version"))
    except Exception:
        pass
    return None


def parse_version(version_spec: str) -> Optional[str]:
    """Extract a version number from a version spec.

    Args:
        version_spec: Version specification (e.g., ">=1.0,<2.0").

    Returns:
        Extracted version or None.
    """
    import re

    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_spec)
    if match:
        return match.group(1)
    return None


def compare_versions(current: str, latest: str) -> bool:
    """Check if latest version is newer than current.

    Args:
        current: Current version.
        latest: Latest version.

    Returns:
        True if latest > current.
    """
    from packaging.version import Version

    try:
        return Version(latest) > Version(current)
    except Exception:
        return False


def is_major_upgrade(current: str, latest: str) -> bool:
    """Check if this is a major version upgrade.

    Args:
        current: Current version.
        latest: Latest version.

    Returns:
        True if major version changed.
    """
    try:
        current_major = int(current.split(".")[0])
        latest_major = int(latest.split(".")[0])
        return latest_major > current_major
    except Exception:
        return False


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project to scan",
)
@click.option(
    "--fetch-changes",
    is_flag=True,
    help="Fetch changelogs and detect breaking changes (slower but more detailed)",
)
@click.option(
    "--major-only",
    is_flag=True,
    help="Only show major version upgrades",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output",
)
def scan(
    path: str,
    fetch_changes: bool,
    major_only: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Scan your project for possible dependency migrations.

    This command analyzes your project dependencies, checks for newer versions,
    and suggests which libraries could be upgraded.

    \b
    Examples:
        pyresolve scan
        pyresolve scan --fetch-changes
        pyresolve scan --major-only
        pyresolve scan --json-output
    """
    project_path = Path(path).resolve()
    # Load project config (currently unused, reserved for future use)
    _ = ProjectConfig.from_pyproject(project_path)

    if not json_output:
        console.print(
            Panel(
                "[bold]Scanning project for possible migrations[/]\n\n" f"Path: {project_path}",
                title="PyResolve Scan",
            )
        )

    # Parse dependencies
    dep_parser = DependencyParser(project_path)
    dependencies = dep_parser.parse_all()

    if not dependencies:
        if not json_output:
            console.print("[yellow]No dependencies found in project.[/]")
        return

    if not json_output:
        console.print(f"\nFound [cyan]{len(dependencies)}[/] dependencies")

    # Check for updates
    outdated = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        disable=json_output,
    ) as progress:
        task = progress.add_task("Checking for updates...", total=len(dependencies))

        for dep in dependencies:
            progress.update(task, description=f"Checking {dep.name}...")

            current_version = parse_version(dep.version_spec) if dep.version_spec else None
            latest_version = get_latest_version(dep.name)

            if latest_version and current_version:
                if compare_versions(current_version, latest_version):
                    is_major = is_major_upgrade(current_version, latest_version)

                    if major_only and not is_major:
                        progress.advance(task)
                        continue

                    outdated.append(
                        {
                            "name": dep.name,
                            "current": current_version,
                            "latest": latest_version,
                            "is_major": is_major,
                            "is_tier1": is_tier_1_library(dep.name),
                        }
                    )

            progress.advance(task)

    if not outdated:
        if not json_output:
            console.print("\n[green]All dependencies are up to date![/]")
        else:
            print(json.dumps({"outdated": [], "migrations": []}))
        return

    # Fetch breaking changes if requested
    migrations = []

    if fetch_changes:
        if not json_output:
            console.print(
                f"\n[bold]Fetching changelogs for {len(outdated)} outdated packages...[/]\n"
            )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
            disable=json_output,
        ) as progress:
            task = progress.add_task("Fetching changelogs...", total=len(outdated))

            for pkg in outdated:
                progress.update(task, description=f"Analyzing {pkg['name']}...")

                try:
                    kb = generate_knowledge_base_sync(
                        package=str(pkg["name"]),
                        old_version=str(pkg["current"]),
                        new_version=str(pkg["latest"]),
                    )

                    pkg["breaking_changes"] = len(kb.breaking_changes)
                    pkg["confidence"] = kb.overall_confidence.value
                    pkg["changes"] = [
                        {
                            "old_api": c.old_api,
                            "new_api": c.new_api,
                            "description": c.description,
                            "confidence": c.confidence.value,
                        }
                        for c in kb.breaking_changes[:5]  # Limit to 5 changes
                    ]

                    if kb.has_changes or pkg["is_tier1"]:
                        migrations.append(pkg)

                except Exception as e:
                    if verbose and not json_output:
                        console.print(f"  [dim]Could not fetch changelog for {pkg['name']}: {e}[/]")
                    pkg["breaking_changes"] = None
                    pkg["confidence"] = "unknown"

                progress.advance(task)
    else:
        # Without fetch_changes, suggest all tier1 and major upgrades
        for pkg in outdated:
            if pkg["is_tier1"] or pkg["is_major"]:
                migrations.append(pkg)

    # Output results
    if json_output:
        print(
            json.dumps(
                {
                    "outdated": outdated,
                    "migrations": migrations,
                },
                indent=2,
            )
        )
        return

    # Display results
    console.print(f"\n[bold]Outdated Dependencies ({len(outdated)})[/]\n")

    table = Table()
    table.add_column("Package", style="cyan")
    table.add_column("Current", justify="right")
    table.add_column("Latest", justify="right")
    table.add_column("Type", justify="center")
    table.add_column("Tier", justify="center")

    if fetch_changes:
        table.add_column("Breaking Changes", justify="right")
        table.add_column("Confidence", justify="center")

    for pkg in outdated:
        type_str = "[red]Major[/]" if pkg["is_major"] else "[yellow]Minor/Patch[/]"
        tier_str = "[green]Tier 1[/]" if pkg["is_tier1"] else "[dim]Tier 2/3[/]"

        row = [
            pkg["name"],
            pkg["current"],
            pkg["latest"],
            type_str,
            tier_str,
        ]

        if fetch_changes:
            changes = pkg.get("breaking_changes")
            if changes is not None:
                row.append(str(changes))
                confidence = str(pkg.get("confidence", "unknown"))
                conf_style = {
                    "high": "[green]HIGH[/]",
                    "medium": "[yellow]MEDIUM[/]",
                    "low": "[dim]LOW[/]",
                }.get(confidence, "[dim]?[/]")
                row.append(conf_style)
            else:
                row.append("[dim]?[/]")
                row.append("[dim]?[/]")

        table.add_row(*[str(item) for item in row])

    console.print(table)

    # Show suggested migrations
    if migrations:
        console.print(f"\n[bold]Suggested Migrations ({len(migrations)})[/]\n")

        for pkg in migrations:
            tier_label = (
                "[green](Tier 1 - deterministic)[/]"
                if pkg["is_tier1"]
                else "[yellow](Tier 2/3 - LLM-assisted)[/]"
            )
            console.print(
                f"  [cyan]{pkg['name']}[/] {pkg['current']} → {pkg['latest']} {tier_label}"
            )

            if fetch_changes and pkg.get("changes"):
                console.print("    Breaking changes:")
                changes_list = cast(list[dict[str, Any]], pkg["changes"])
                for change in changes_list[:3]:
                    if change["new_api"]:
                        console.print(
                            f"      [dim]├──[/] {change['old_api']} → {change['new_api']}"
                        )
                    else:
                        console.print(f"      [dim]├──[/] {change['old_api']} [red](removed)[/]")
                pkg_changes = cast(list[Any], pkg.get("changes", []))
                if len(pkg_changes) > 3:
                    console.print(f"      [dim]└── ... and {len(pkg_changes) - 3} more[/]")

            console.print()

        console.print("[bold]To migrate a package, run:[/]")
        console.print("  [cyan]pyresolve upgrade <package> --target <version>[/]\n")

        # Show quick commands
        console.print("[bold]Quick commands:[/]")
        for pkg in migrations[:3]:
            console.print(f"  [dim]pyresolve upgrade {pkg['name']} --target {pkg['latest']}[/]")
    else:
        console.print(
            "\n[dim]No migrations suggested. Use --fetch-changes for detailed analysis.[/]"
        )

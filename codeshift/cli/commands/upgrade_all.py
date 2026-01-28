"""Upgrade-all command for migrating all outdated packages to their latest versions."""

import json
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from codeshift.cli.commands.scan import (
    compare_versions,
    get_latest_version,
    is_major_upgrade,
    parse_version,
)
from codeshift.knowledge import (
    GeneratedKnowledgeBase,
    generate_knowledge_base_sync,
    is_tier_1_library,
)
from codeshift.migrator.ast_transforms import TransformChange, TransformResult, TransformStatus
from codeshift.migrator.transforms.fastapi_transformer import transform_fastapi
from codeshift.migrator.transforms.pandas_transformer import transform_pandas
from codeshift.migrator.transforms.pydantic_v1_to_v2 import transform_pydantic_v1_to_v2
from codeshift.migrator.transforms.requests_transformer import transform_requests
from codeshift.migrator.transforms.sqlalchemy_transformer import transform_sqlalchemy
from codeshift.scanner import CodeScanner, DependencyParser
from codeshift.utils.config import ProjectConfig

console = Console()


def save_multi_state(project_path: Path, state: dict) -> None:
    """Save the multi-library migration state."""
    state_dir = project_path / ".codeshift"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "state.json"
    state_file.write_text(json.dumps(state, indent=2, default=str))


def run_single_upgrade(
    library: str,
    target: str,
    project_path: Path,
    project_config: ProjectConfig,
    verbose: bool,
) -> tuple[list[TransformResult], GeneratedKnowledgeBase | None]:
    """Run upgrade for a single library and return results.

    Args:
        library: Library name to upgrade.
        target: Target version.
        project_path: Path to the project.
        project_config: Project configuration.
        verbose: Whether to show verbose output.

    Returns:
        Tuple of (list of transform results, generated knowledge base).
    """
    results: list[TransformResult] = []
    generated_kb: GeneratedKnowledgeBase | None = None

    # Get current version
    dep_parser = DependencyParser(project_path)
    current_dep = dep_parser.get_dependency(library)

    current_version = None
    if current_dep and current_dep.version_spec:
        import re

        version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", current_dep.version_spec)
        if version_match:
            current_version = version_match.group(1)

    # Fetch knowledge sources
    try:
        generated_kb = generate_knowledge_base_sync(
            package=library,
            old_version=current_version or "1.0",
            new_version=target,
        )
    except Exception:
        pass

    # Scan for library usage
    scanner = CodeScanner(library, exclude_patterns=project_config.exclude)
    scan_result = scanner.scan_directory(project_path)

    if not scan_result.imports:
        return results, generated_kb

    # Get unique files with imports
    files_to_transform = set()
    for imp in scan_result.imports:
        files_to_transform.add(imp.file_path)

    # Select transformer based on library
    transform_func = {
        "pydantic": transform_pydantic_v1_to_v2,
        "fastapi": transform_fastapi,
        "sqlalchemy": transform_sqlalchemy,
        "pandas": transform_pandas,
        "requests": transform_requests,
    }.get(library)

    if not transform_func:
        return results, generated_kb

    for file_path in files_to_transform:
        try:
            source_code = file_path.read_text()
            transformed_code, changes = transform_func(source_code)

            result = TransformResult(
                file_path=file_path,
                status=TransformStatus.SUCCESS if changes else TransformStatus.NO_CHANGES,
                original_code=source_code,
                transformed_code=transformed_code,
                changes=[
                    TransformChange(
                        description=c.description,
                        line_number=c.line_number,
                        original=c.original,
                        replacement=c.replacement,
                        transform_name=c.transform_name,
                        confidence=getattr(c, "confidence", 1.0),
                    )
                    for c in changes
                ],
            )

            if result.has_changes:
                results.append(result)

        except Exception:
            pass

    return results, generated_kb


@click.command("upgrade-all")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project to analyze",
)
@click.option(
    "--all",
    "upgrade_all_pkgs",
    is_flag=True,
    help="Upgrade all outdated packages (not just Tier 1 or major upgrades)",
)
@click.option(
    "--tier1-only",
    is_flag=True,
    help="Only upgrade Tier 1 libraries (deterministic transforms)",
)
@click.option(
    "--major-only",
    is_flag=True,
    help="Only perform major version upgrades",
)
@click.option(
    "--include",
    "-i",
    multiple=True,
    help="Only include specific libraries (can be specified multiple times)",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Exclude specific libraries (can be specified multiple times)",
)
@click.option(
    "--update-deps/--no-update-deps",
    default=True,
    help="Update dependency files (pyproject.toml, requirements.txt) with new versions",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without saving state",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output",
)
def upgrade_all(
    path: str,
    upgrade_all_pkgs: bool,
    tier1_only: bool,
    major_only: bool,
    include: tuple,
    exclude: tuple,
    update_deps: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Upgrade all outdated packages to their latest versions.

    This command scans your project for outdated dependencies, identifies which
    ones have available migrations, and applies all transformations at once.

    By default, it upgrades:
    - All Tier 1 libraries (pydantic, fastapi, sqlalchemy, pandas, requests)
    - Any library with a major version upgrade available

    Use --all to upgrade ALL outdated packages, regardless of tier or upgrade type.

    After migration, dependency files (pyproject.toml, requirements.txt) are
    automatically updated with the new versions unless --no-update-deps is specified.

    \b
    Examples:
        codeshift upgrade-all
        codeshift upgrade-all --all
        codeshift upgrade-all --tier1-only
        codeshift upgrade-all --include pydantic --include fastapi
        codeshift upgrade-all --exclude pandas
        codeshift upgrade-all --no-update-deps
        codeshift upgrade-all --dry-run
    """
    project_path = Path(path).resolve()
    project_config = ProjectConfig.from_pyproject(project_path)

    console.print(
        Panel(
            "[bold]Scanning project for upgradeable dependencies[/]\n\n" f"Path: {project_path}",
            title="Codeshift Upgrade All",
        )
    )

    # Parse dependencies
    dep_parser = DependencyParser(project_path)
    dependencies = dep_parser.parse_all()

    if not dependencies:
        console.print("[yellow]No dependencies found in project.[/]")
        return

    console.print(f"\nFound [cyan]{len(dependencies)}[/] dependencies")

    # Check for updates
    outdated = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Checking for updates...", total=len(dependencies))

        for dep in dependencies:
            progress.update(task, description=f"Checking {dep.name}...")

            current_version = parse_version(dep.version_spec) if dep.version_spec else None
            latest_version = get_latest_version(dep.name)

            if latest_version and current_version:
                if compare_versions(current_version, latest_version):
                    is_major = is_major_upgrade(current_version, latest_version)
                    is_tier1 = is_tier_1_library(dep.name)

                    outdated.append(
                        {
                            "name": dep.name,
                            "current": current_version,
                            "latest": latest_version,
                            "is_major": is_major,
                            "is_tier1": is_tier1,
                        }
                    )

            progress.advance(task)

    if not outdated:
        console.print("\n[green]All dependencies are up to date![/]")
        return

    # Filter to upgradeable packages
    upgradeable = []

    for pkg in outdated:
        # Apply include filter
        if include and pkg["name"] not in include:
            continue

        # Apply exclude filter
        if pkg["name"] in exclude:
            continue

        # Apply tier1-only filter
        if tier1_only and not pkg["is_tier1"]:
            continue

        # Apply major-only filter
        if major_only and not pkg["is_major"]:
            continue

        # By default, include Tier 1 libraries and major upgrades
        # Use --all to include all outdated packages
        if not (tier1_only or major_only or include or upgrade_all_pkgs):
            if not (pkg["is_tier1"] or pkg["is_major"]):
                continue

        upgradeable.append(pkg)

    if not upgradeable:
        console.print("\n[yellow]No upgradeable packages found matching the criteria.[/]")
        console.print(
            "[dim]Use --all to upgrade all outdated packages, or --verbose to see details.[/]"
        )

        if verbose and outdated:
            console.print("\nOutdated packages (not matching criteria):")
            for pkg in outdated:
                tier_label = "[green]Tier 1[/]" if pkg["is_tier1"] else "[dim]Tier 2/3[/]"
                type_label = "[red]Major[/]" if pkg["is_major"] else "[dim]Minor/Patch[/]"
                console.print(
                    f"  {pkg['name']} {pkg['current']} → {pkg['latest']} {tier_label} {type_label}"
                )
        return

    # Display packages to upgrade
    console.print(f"\n[bold]Packages to upgrade ({len(upgradeable)})[/]\n")

    table = Table()
    table.add_column("Package", style="cyan")
    table.add_column("Current", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Type", justify="center")
    table.add_column("Tier", justify="center")

    for pkg in upgradeable:
        type_str = "[red]Major[/]" if pkg["is_major"] else "[yellow]Minor/Patch[/]"
        tier_str = "[green]Tier 1[/]" if pkg["is_tier1"] else "[dim]Tier 2/3[/]"
        table.add_row(str(pkg["name"]), str(pkg["current"]), str(pkg["latest"]), type_str, tier_str)

    console.print(table)
    console.print()  # Ensure table is fully rendered before progress bar

    # Run upgrades for each package
    console.print("[bold]Running migrations...[/]\n")

    all_results: dict[str, list[dict]] = {}
    migration_summary: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Upgrading packages...", total=len(upgradeable))

        for pkg in upgradeable:
            progress.update(task, description=f"Upgrading {pkg['name']} to {pkg['latest']}...")

            results, generated_kb = run_single_upgrade(
                library=str(pkg["name"]),
                target=str(pkg["latest"]),
                project_path=project_path,
                project_config=project_config,
                verbose=verbose,
            )

            if results:
                all_results[str(pkg["name"])] = [
                    {
                        "file_path": str(r.file_path),
                        "original_code": r.original_code,
                        "transformed_code": r.transformed_code,
                        "change_count": r.change_count,
                        "status": r.status.value,
                        "changes": [
                            {
                                "description": c.description,
                                "line_number": c.line_number,
                                "original": c.original,
                                "replacement": c.replacement,
                                "transform_name": c.transform_name,
                            }
                            for c in r.changes
                        ],
                    }
                    for r in results
                ]

                migration_summary.append(
                    {
                        "library": pkg["name"],
                        "from_version": pkg["current"],
                        "to_version": pkg["latest"],
                        "files_changed": len(results),
                        "total_changes": sum(r.change_count for r in results),
                        "breaking_changes_detected": (
                            len(generated_kb.breaking_changes) if generated_kb else 0
                        ),
                    }
                )

            progress.advance(task)

    # Display code transformation results summary
    if migration_summary:
        console.print("\n[bold]Code Migration Summary[/]\n")

        summary_table = Table()
        summary_table.add_column("Library", style="cyan")
        summary_table.add_column("Migration", justify="center")
        summary_table.add_column("Files", justify="right")
        summary_table.add_column("Changes", justify="right")
        summary_table.add_column("Status", justify="center")

        total_files = 0
        total_changes = 0

        for summary in migration_summary:
            summary_table.add_row(
                summary["library"],
                f"{summary['from_version']} → {summary['to_version']}",
                str(summary["files_changed"]),
                str(summary["total_changes"]),
                "[green]Ready[/]",
            )
            total_files += summary["files_changed"]
            total_changes += summary["total_changes"]

        console.print(summary_table)
        console.print(
            f"\n[bold]Total:[/] [cyan]{total_changes}[/] changes across [cyan]{total_files}[/] files"
        )

        # Show detailed changes if verbose
        if verbose:
            console.print("\n[bold]Change Details[/]")
            for lib_name, lib_results in all_results.items():
                console.print(f"\n[bold cyan]{lib_name}[/]")
                for result_dict in lib_results:
                    try:
                        display_path = str(
                            Path(str(result_dict["file_path"])).relative_to(project_path)
                        )
                    except ValueError:
                        display_path = str(result_dict["file_path"])
                    console.print(f"  [cyan]{display_path}[/]:")
                    for change_dict in result_dict["changes"]:
                        console.print(f"    • {change_dict['description']}")
    else:
        console.print(
            "\n[green]No code changes needed.[/] Your code is compatible with the new versions."
        )

    # Update dependency files with new versions for ALL upgradeable packages
    if update_deps and upgradeable:
        console.print("\n[bold]Updating dependency files...[/]\n")

        dep_parser = DependencyParser(project_path)
        dep_updates: list[tuple[str, str, list[tuple[Path, bool]]]] = []

        for pkg in upgradeable:
            if not dry_run:
                update_results = dep_parser.update_dependency_version(
                    str(pkg["name"]), str(pkg["latest"])
                )
                dep_updates.append((str(pkg["name"]), str(pkg["latest"]), update_results))
            else:
                # In dry run, just show what would be updated
                dep_updates.append((str(pkg["name"]), str(pkg["latest"]), []))

        # Display update results
        if dry_run:
            console.print("[dim]Would update the following dependencies:[/]")
            for lib_name, version, _ in dep_updates:
                console.print(f"  [cyan]{lib_name}[/] → [green]>={version}[/]")
        else:
            files_updated: set[Path] = set()
            for lib_name, version, update_results in dep_updates:
                for file_path, success in update_results:
                    if success:
                        files_updated.add(file_path)
                        if verbose:
                            console.print(
                                f"  Updated [cyan]{lib_name}[/] to [green]>={version}[/] in {file_path.name}"
                            )

            if files_updated:
                console.print(f"Updated versions in: {', '.join(f.name for f in files_updated)}")
            else:
                console.print(
                    "[dim]No dependency files were updated (dependencies may not be pinned)[/]"
                )

    # Save state only if there are code changes to review
    if not dry_run and migration_summary:
        # Merge all results into a combined state format
        # This maintains compatibility with diff/apply commands
        combined_results: list[dict[str, Any]] = []
        for lib_name, lib_results in all_results.items():
            for result_dict in lib_results:
                # Add library info to each result for tracking
                result_dict["library"] = lib_name
                combined_results.append(result_dict)

        state = {
            "library": "multiple",
            "migrations": migration_summary,
            "project_path": str(project_path),
            "results": combined_results,
        }
        save_multi_state(project_path, state)

        console.print("\n[dim]State saved to .codeshift/state.json[/]")
        console.print("\nNext steps:")
        console.print("  [cyan]codeshift diff[/]    - View detailed diff of proposed changes")
        console.print("  [cyan]codeshift apply[/]   - Apply changes to your files")
    elif dry_run:
        console.print("\n[dim]Dry run mode - no changes applied[/]")
    elif not migration_summary and upgradeable:
        console.print(
            "\n[green]Dependencies updated.[/] No code changes required for this upgrade."
        )

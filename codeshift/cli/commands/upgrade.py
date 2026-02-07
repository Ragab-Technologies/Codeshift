"""Upgrade command for analyzing and preparing migrations."""

import json
import logging
import os
from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from codeshift.cli.quota import QuotaError, check_quota, record_usage, show_quota_exceeded_message
from codeshift.knowledge import (
    Confidence,
    GeneratedKnowledgeBase,
    generate_knowledge_base_sync,
    is_tier_1_library,
)
from codeshift.knowledge_base import KnowledgeBaseLoader
from codeshift.knowledge_base.models import LibraryKnowledge
from codeshift.migrator.ast_transforms import TransformResult, TransformStatus
from codeshift.scanner import CodeScanner, DependencyParser
from codeshift.utils.config import ProjectConfig

console = Console()


_log = logging.getLogger(__name__)

_REQUIRED_STATE_KEYS = {"library", "target_version", "results"}
_REQUIRED_RESULT_KEYS = {"file_path", "transformed_code"}


def _validate_state(state: dict[str, Any], project_path: Path) -> dict[str, Any] | None:
    """Validate state structure and file paths.

    Returns the state if valid, or None if validation fails.
    """
    # Check required top-level keys
    if not _REQUIRED_STATE_KEYS.issubset(state.keys()):
        _log.warning("State file missing required keys: %s", _REQUIRED_STATE_KEYS - state.keys())
        return None

    if not isinstance(state.get("results"), list):
        _log.warning("State file 'results' is not a list")
        return None

    project_resolved = project_path.resolve()

    for result in state["results"]:
        if not isinstance(result, dict):
            _log.warning("State file contains non-dict result entry")
            return None

        if not _REQUIRED_RESULT_KEYS.issubset(result.keys()):
            _log.warning("State result missing required keys")
            return None

        # Validate file_path is within the project directory
        try:
            file_path = Path(result["file_path"]).resolve()
            if not file_path.is_relative_to(project_resolved):
                _log.warning("State file contains path outside project: %s", result["file_path"])
                return None
        except (TypeError, ValueError):
            _log.warning("State file contains invalid path: %s", result.get("file_path"))
            return None

    return state


def load_state(project_path: Path) -> dict[str, Any] | None:
    """Load and validate the current migration state if it exists."""
    state_file = project_path / ".codeshift" / "state.json"
    if state_file.exists():
        try:
            state = cast(dict[str, Any], json.loads(state_file.read_text()))
            return _validate_state(state, project_path)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _log.warning("Could not parse state file: %s", e)
            return None
        except Exception:
            return None
    return None


def save_state(project_path: Path, state: dict) -> None:
    """Save the migration state with restrictive permissions."""
    state_dir = project_path / ".codeshift"
    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    state_file = state_dir / "state.json"
    state_file.write_text(json.dumps(state, indent=2, default=str))
    os.chmod(state_file, 0o600)


@click.command()
@click.argument("library")
@click.option(
    "--target",
    "-t",
    required=True,
    help="Target version to upgrade to (e.g., 2.5.0)",
)
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project to analyze",
)
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="Analyze a single file instead of the entire project",
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
@click.option(
    "--force-llm",
    is_flag=True,
    help="Force LLM migration even for libraries with AST transforms",
)
def upgrade(
    library: str,
    target: str,
    path: str,
    file: str | None,
    dry_run: bool,
    verbose: bool,
    force_llm: bool,
) -> None:
    """Analyze your codebase and propose changes for a library upgrade.

    \b
    Examples:
        codeshift upgrade pydantic --target 2.5.0
        codeshift upgrade pydantic -t 2.0 --file models.py
        codeshift upgrade pydantic -t 2.0 --dry-run
    """
    project_path = Path(path).resolve()
    project_config = ProjectConfig.from_pyproject(project_path)

    # Check quota before starting (allow offline for Tier 1 libraries unless force-llm)
    is_tier1 = is_tier_1_library(library)
    try:
        check_quota("file_migrated", quantity=1, allow_offline=is_tier1 and not force_llm)
    except QuotaError as e:
        show_quota_exceeded_message(e)
        raise SystemExit(1) from e

    # Load knowledge base (optional - YAML may not exist for all libraries)
    loader = KnowledgeBaseLoader()
    knowledge: LibraryKnowledge | None = None

    try:
        knowledge = loader.load(library)
    except FileNotFoundError:
        if verbose:
            console.print(
                f"[dim]No knowledge base YAML for {library} - using generated knowledge[/]"
            )

    # Display migration info with fallback for missing YAML
    if knowledge:
        console.print(
            Panel(
                f"[bold]Upgrading {knowledge.display_name}[/] to version [cyan]{target}[/]\n\n"
                f"{knowledge.description}\n"
                f"Migration guide: {knowledge.migration_guide_url or 'N/A'}",
                title="Codeshift Migration",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold]Upgrading {library}[/] to version [cyan]{target}[/]\n\n"
                "Using AI-powered migration (no static knowledge base available)",
                title="Codeshift Migration",
            )
        )

    # Step 1: Parse dependencies
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking project dependencies...", total=None)

        dep_parser = DependencyParser(project_path)
        current_dep = dep_parser.get_dependency(library)

        current_version = None
        if current_dep:
            console.print(
                f"Found [cyan]{library}[/] in project dependencies: {current_dep.version_spec or 'any version'}"
            )
            # Extract version number from spec (e.g., ">=1.0,<2.0" -> "1.0")
            if current_dep.version_spec:
                import re

                version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", current_dep.version_spec)
                if version_match:
                    current_version = version_match.group(1)
        else:
            console.print(f"[yellow]Warning:[/] {library} not found in project dependencies")

        progress.update(task, completed=True)

    # Step 2: Fetch knowledge sources from GitHub
    generated_kb: GeneratedKnowledgeBase | None = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching knowledge sources...", total=None)

        def progress_callback(msg: str) -> None:
            progress.update(task, description=msg)

        try:
            generated_kb = generate_knowledge_base_sync(
                package=library,
                old_version=current_version or "1.0",
                new_version=target,
                progress_callback=progress_callback,
            )
        except Exception as e:
            if verbose:
                console.print(f"[yellow]Warning:[/] Could not fetch knowledge sources: {e}")

        progress.update(task, completed=True)

    # Display detected breaking changes
    if generated_kb and generated_kb.has_changes:
        console.print("\n[bold]Breaking changes detected:[/]\n")

        # Group by confidence
        high_confidence = generated_kb.get_changes_by_confidence(Confidence.HIGH)
        medium_confidence = [
            c for c in generated_kb.breaking_changes if c.confidence == Confidence.MEDIUM
        ]
        low_confidence = [
            c for c in generated_kb.breaking_changes if c.confidence == Confidence.LOW
        ]

        if high_confidence:
            console.print("   [green]HIGH CONFIDENCE:[/]")
            for change in high_confidence:
                if change.new_api:
                    console.print(f"   [dim]├──[/] {change.old_api} [dim]→[/] {change.new_api}")
                else:
                    console.print(f"   [dim]├──[/] {change.old_api} [red](removed)[/]")

        if medium_confidence:
            console.print("\n   [yellow]MEDIUM CONFIDENCE:[/]")
            for change in medium_confidence:
                if change.new_api:
                    console.print(f"   [dim]├──[/] {change.old_api} [dim]→[/] {change.new_api}")
                else:
                    console.print(f"   [dim]├──[/] {change.old_api} [red](removed)[/]")

        if low_confidence and verbose:
            console.print("\n   [dim]LOW CONFIDENCE:[/]")
            for change in low_confidence:
                if change.new_api:
                    console.print(f"   [dim]├──[/] {change.old_api} [dim]→[/] {change.new_api}")
                else:
                    console.print(f"   [dim]├──[/] {change.old_api} [red](removed)[/]")

        if generated_kb.sources:
            console.print(
                f"\n   [dim]Sources: {', '.join(generated_kb.sources[:2])}{'...' if len(generated_kb.sources) > 2 else ''}[/]"
            )

    elif generated_kb:
        console.print("\n[dim]No breaking changes detected from changelog sources.[/]")

    # Step 3: Scan for library usage
    console.print("")  # Add spacing
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning for library usage...", total=None)

        scanner = CodeScanner(library, exclude_patterns=project_config.exclude)

        if file:
            # Single file mode
            file_path = Path(file).resolve()
            imports, usages = scanner.scan_file(file_path)
            scan_result_files = 1
            scan_result_imports = imports
            scan_result_usages = usages
            scan_result_errors = []
        else:
            # Full project scan
            scan_result = scanner.scan_directory(project_path)
            scan_result_files = scan_result.files_scanned
            scan_result_imports = scan_result.imports
            scan_result_usages = scan_result.usages
            scan_result_errors = scan_result.errors

        progress.update(task, completed=True)

    console.print(f"\nScanned [cyan]{scan_result_files}[/] files")
    console.print(f"Found [cyan]{len(scan_result_imports)}[/] imports from {library}")
    console.print(f"Found [cyan]{len(scan_result_usages)}[/] usages of {library} symbols")

    if scan_result_errors:
        console.print(f"[yellow]Warnings:[/] {len(scan_result_errors)} files could not be parsed")
        if verbose:
            for file_path, error in scan_result_errors:
                console.print(f"  - {file_path}: {error}")

    if not scan_result_imports:
        console.print(f"\n[yellow]No {library} imports found in the codebase.[/]")
        return

    # Step 4: Apply transforms using MigrationEngine
    # Import here to avoid circular dependency (upgrade.py -> migrator -> llm_migrator -> api_client -> auth -> cli -> upgrade.py)
    from codeshift.migrator import get_migration_engine

    engine = get_migration_engine()

    # Check auth for non-Tier1 libraries or force-llm mode
    llm_required = force_llm or not is_tier1
    if llm_required and not engine.llm_migrator.is_available:
        console.print(
            Panel(
                f"[yellow]LLM migration required for {library}[/]\n\n"
                "Run [cyan]codeshift login[/] and upgrade to Pro tier for LLM features.",
                title="Authentication Required",
            )
        )
        if not is_tier1:
            raise SystemExit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing code and proposing changes...", total=None)

        # Get unique files with imports
        files_to_transform = set()
        for imp in scan_result_imports:
            files_to_transform.add(imp.file_path)

        results: list[TransformResult] = []

        def migration_progress(msg: str) -> None:
            progress.update(task, description=msg)

        for file_path in files_to_transform:
            try:
                source_code = file_path.read_text()

                result = engine.run_migration(
                    code=source_code,
                    file_path=file_path,
                    library=library,
                    old_version=current_version or "1.0",
                    new_version=target,
                    knowledge_base=generated_kb,
                    progress_callback=migration_progress if verbose else None,
                )

                if result.has_changes:
                    results.append(result)
                elif result.errors:
                    for error in result.errors:
                        console.print(f"[yellow]Warning ({file_path.name}):[/] {error}")

            except Exception as e:
                console.print(f"[red]Error processing {file_path}:[/] {e}")

        progress.update(task, completed=True)

    # Step 5: Show results
    if not results:
        console.print(
            f"\n[green]No changes needed![/] Your code appears to be compatible with {library} v{target}."
        )
        return

    console.print("\n[bold]Proposed Changes[/]")

    table = Table()
    table.add_column("File", style="cyan")
    table.add_column("Changes", justify="right")
    table.add_column("Status", justify="center")

    total_changes = 0
    for result in results:
        status_style = {
            TransformStatus.SUCCESS: "[green]Ready[/]",
            TransformStatus.PARTIAL: "[yellow]Partial[/]",
            TransformStatus.FAILED: "[red]Failed[/]",
            TransformStatus.NO_CHANGES: "[dim]No changes[/]",
        }
        # Handle files outside project path
        try:
            display_path = str(result.file_path.relative_to(project_path))
        except ValueError:
            display_path = str(result.file_path)
        table.add_row(
            display_path,
            str(result.change_count),
            status_style.get(result.status, "[dim]Unknown[/]"),
        )
        total_changes += result.change_count

    console.print(table)
    console.print(f"\nTotal: [cyan]{total_changes}[/] changes across [cyan]{len(results)}[/] files")

    # Show detailed changes if verbose
    if verbose:
        console.print("\n[bold]Change Details[/]")
        for result in results:
            try:
                display_path = str(result.file_path.relative_to(project_path))
            except ValueError:
                display_path = str(result.file_path)
            console.print(f"\n[cyan]{display_path}[/]:")
            for transform_change in result.changes:
                console.print(f"  • {transform_change.description}")
                console.print(f"    [red]- {transform_change.original}[/]")
                console.print(f"    [green]+ {transform_change.replacement}[/]")

    # Save state
    if not dry_run:
        state = {
            "library": library,
            "target_version": target,
            "project_path": str(project_path),
            "results": [
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
            ],
        }
        save_state(project_path, state)

        # Record usage event
        record_usage(
            event_type="scan",
            library=library,
            quantity=1,
            metadata={
                "files_analyzed": len(files_to_transform),
                "changes_proposed": total_changes,
                "target_version": target,
            },
        )

        console.print("\n[dim]State saved to .codeshift/state.json[/]")
        console.print("\nNext steps:")
        console.print("  [cyan]codeshift diff[/]    - View detailed diff of proposed changes")
        console.print("  [cyan]codeshift apply[/]   - Apply changes to your files")
    else:
        console.print("\n[dim]Dry run mode - no state saved[/]")

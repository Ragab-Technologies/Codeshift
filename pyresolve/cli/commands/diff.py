"""Diff command for viewing proposed changes."""

import difflib
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from pyresolve.cli.commands.upgrade import load_state

console = Console()


@click.command()
@click.option(
    "--path", "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project",
)
@click.option(
    "--file", "-f",
    type=str,
    help="Show diff for a specific file only",
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output",
)
@click.option(
    "--context", "-c",
    type=int,
    default=3,
    help="Number of context lines in diff (default: 3)",
)
@click.option(
    "--summary",
    is_flag=True,
    help="Show only a summary of changes without full diff",
)
def diff(
    path: str,
    file: Optional[str],
    no_color: bool,
    context: int,
    summary: bool,
) -> None:
    """View detailed diff of proposed changes.

    \b
    Examples:
        pyresolve diff
        pyresolve diff --file models.py
        pyresolve diff --summary
    """
    project_path = Path(path).resolve()
    state = load_state(project_path)

    if state is None:
        console.print(Panel(
            "[yellow]No pending migration found.[/]\n\n"
            "Run [cyan]pyresolve upgrade <library> --target <version>[/] first.",
            title="No Changes",
        ))
        return

    library = state.get("library", "unknown")
    target_version = state.get("target_version", "unknown")
    results = state.get("results", [])

    if not results:
        console.print("[yellow]No changes pending.[/]")
        return

    console.print(Panel(
        f"[bold]Migration: {library}[/] → v{target_version}\n"
        f"Files: {len(results)} | Total changes: {sum(r.get('change_count', 0) for r in results)}",
        title="Proposed Changes",
    ))

    for result in results:
        file_path = Path(result["file_path"])
        relative_path = file_path.relative_to(project_path) if file_path.is_relative_to(project_path) else file_path

        # Filter by file if specified
        if file and str(relative_path) != file and file_path.name != file:
            continue

        original = result.get("original_code", "")
        transformed = result.get("transformed_code", "")
        changes = result.get("changes", [])
        change_count = result.get("change_count", 0)

        console.print(f"\n[bold cyan]{relative_path}[/] ({change_count} changes)")
        console.print("─" * 60)

        if summary:
            # Just show change summaries
            for change in changes:
                console.print(f"  • {change['description']}")
            continue

        # Generate unified diff
        original_lines = original.splitlines(keepends=True)
        transformed_lines = transformed.splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            original_lines,
            transformed_lines,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            n=context,
        ))

        if not diff_lines:
            console.print("  [dim]No textual differences[/]")
            continue

        # Display diff with syntax highlighting
        diff_text = "".join(diff_lines)

        if no_color:
            console.print(diff_text)
        else:
            # Color the diff manually for better visibility
            for line in diff_lines:
                if line.startswith("+++") or line.startswith("---"):
                    console.print(f"[bold]{line.rstrip()}[/]")
                elif line.startswith("@@"):
                    console.print(f"[cyan]{line.rstrip()}[/]")
                elif line.startswith("+"):
                    console.print(f"[green]{line.rstrip()}[/]")
                elif line.startswith("-"):
                    console.print(f"[red]{line.rstrip()}[/]")
                else:
                    console.print(line.rstrip())

        # Show change descriptions
        console.print("\n[bold]Changes:[/]")
        for change in changes:
            console.print(f"  • {change['description']}")

    # Show next steps
    console.print("\n" + "─" * 60)
    console.print("Next steps:")
    console.print("  [cyan]pyresolve apply[/]           - Apply all changes")
    console.print("  [cyan]pyresolve apply --file X[/]  - Apply changes to specific file")
    console.print("  [cyan]pyresolve apply --backup[/]  - Apply with backup files")


@click.command(name="show")
@click.argument("file_path", type=str)
@click.option(
    "--path", "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project",
)
@click.option(
    "--original",
    is_flag=True,
    help="Show original code instead of transformed",
)
def show_file(file_path: str, path: str, original: bool) -> None:
    """Show the full transformed (or original) code for a file.

    \b
    Examples:
        pyresolve show models.py
        pyresolve show models.py --original
    """
    project_path = Path(path).resolve()
    state = load_state(project_path)

    if state is None:
        console.print("[yellow]No pending migration found.[/]")
        return

    results = state.get("results", [])

    for result in results:
        result_file = Path(result["file_path"])
        relative_path = result_file.relative_to(project_path) if result_file.is_relative_to(project_path) else result_file

        if str(relative_path) == file_path or result_file.name == file_path:
            code = result.get("original_code" if original else "transformed_code", "")
            label = "Original" if original else "Transformed"

            console.print(Panel(
                f"[bold]{label} code for {relative_path}[/]",
                title="File Content",
            ))

            syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
            console.print(syntax)
            return

    console.print(f"[yellow]File not found in pending changes: {file_path}[/]")

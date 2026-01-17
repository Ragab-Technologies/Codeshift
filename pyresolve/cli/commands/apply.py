"""Apply command for applying proposed changes."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from pyresolve.cli.commands.upgrade import load_state, save_state

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
    help="Apply changes to a specific file only",
)
@click.option(
    "--backup",
    is_flag=True,
    help="Create backup files (.bak) before applying changes",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Validate syntax after applying changes (default: yes)",
)
def apply(
    path: str,
    file: Optional[str],
    backup: bool,
    yes: bool,
    validate: bool,
) -> None:
    """Apply proposed changes to your files.

    \b
    Examples:
        pyresolve apply
        pyresolve apply --backup
        pyresolve apply --file models.py
        pyresolve apply -y  # Skip confirmation
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

    # Filter results if file specified
    if file:
        results = [
            r for r in results
            if Path(r["file_path"]).name == file
            or str(Path(r["file_path"]).relative_to(project_path)) == file
        ]
        if not results:
            console.print(f"[yellow]No pending changes for file: {file}[/]")
            return

    # Show summary
    total_changes = sum(r.get("change_count", 0) for r in results)
    console.print(Panel(
        f"[bold]Migration: {library}[/] → v{target_version}\n\n"
        f"Files to modify: [cyan]{len(results)}[/]\n"
        f"Total changes: [cyan]{total_changes}[/]",
        title="Apply Changes",
    ))

    # List files to be modified
    console.print("\n[bold]Files to be modified:[/]")
    for result in results:
        file_path = Path(result["file_path"])
        relative_path = file_path.relative_to(project_path) if file_path.is_relative_to(project_path) else file_path
        console.print(f"  • {relative_path} ({result.get('change_count', 0)} changes)")

    # Confirm
    if not yes:
        console.print()
        if not Confirm.ask("Apply these changes?"):
            console.print("[yellow]Aborted.[/]")
            return

    # Apply changes
    applied_count = 0
    failed_count = 0
    backup_dir = project_path / ".pyresolve" / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")

    for result in results:
        file_path = Path(result["file_path"])
        relative_path = file_path.relative_to(project_path) if file_path.is_relative_to(project_path) else file_path
        transformed_code = result.get("transformed_code", "")

        try:
            # Create backup if requested
            if backup:
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / relative_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_path)

            # Validate syntax if requested
            if validate:
                try:
                    compile(transformed_code, str(file_path), "exec")
                except SyntaxError as e:
                    console.print(f"[red]✗[/] {relative_path} - Syntax error: {e}")
                    failed_count += 1
                    continue

            # Write the transformed code
            file_path.write_text(transformed_code)
            console.print(f"[green]✓[/] {relative_path}")
            applied_count += 1

        except Exception as e:
            console.print(f"[red]✗[/] {relative_path} - {e}")
            failed_count += 1

    # Summary
    console.print()
    if applied_count > 0:
        console.print(f"[green]Successfully applied changes to {applied_count} file(s)[/]")

    if failed_count > 0:
        console.print(f"[red]Failed to apply changes to {failed_count} file(s)[/]")

    if backup and applied_count > 0:
        console.print(f"[dim]Backups saved to: {backup_dir}[/]")

    # Update state
    if file:
        # Remove only the applied files from state
        remaining_results = [
            r for r in state.get("results", [])
            if r not in results
        ]
        if remaining_results:
            state["results"] = remaining_results
            save_state(project_path, state)
        else:
            # All done, remove state
            state_file = project_path / ".pyresolve" / "state.json"
            if state_file.exists():
                state_file.unlink()
            console.print("\n[green]Migration complete![/]")
    else:
        # All files processed, remove state
        state_file = project_path / ".pyresolve" / "state.json"
        if state_file.exists():
            state_file.unlink()
        console.print("\n[green]Migration complete![/]")

    # Next steps
    console.print("\n[bold]Recommended next steps:[/]")
    console.print("  1. Review the changes in your editor")
    console.print("  2. Run your test suite: [cyan]pytest[/]")
    console.print("  3. Update your dependencies: [cyan]pip install pydantic>=2.0[/]")


@click.command()
@click.option(
    "--path", "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def reset(path: str, yes: bool) -> None:
    """Reset/cancel the current migration state.

    This removes any pending changes without applying them.

    \b
    Examples:
        pyresolve reset
        pyresolve reset -y
    """
    project_path = Path(path).resolve()
    state = load_state(project_path)

    if state is None:
        console.print("[yellow]No pending migration to reset.[/]")
        return

    library = state.get("library", "unknown")
    results = state.get("results", [])

    console.print(Panel(
        f"[bold]Pending migration: {library}[/]\n"
        f"Files with changes: {len(results)}",
        title="Reset Migration",
    ))

    if not yes:
        if not Confirm.ask("Are you sure you want to discard these changes?"):
            console.print("[yellow]Aborted.[/]")
            return

    state_file = project_path / ".pyresolve" / "state.json"
    if state_file.exists():
        state_file.unlink()

    console.print("[green]Migration state reset.[/]")


@click.command()
@click.argument("backup_dir", type=click.Path(exists=True))
@click.option(
    "--path", "-p",
    type=click.Path(exists=True),
    default=".",
    help="Path to the project",
)
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def restore(backup_dir: str, path: str, yes: bool) -> None:
    """Restore files from a backup.

    \b
    Examples:
        pyresolve restore .pyresolve/backups/20240115_143022
    """
    project_path = Path(path).resolve()
    backup_path = Path(backup_dir).resolve()

    # Find all files in backup
    backup_files = list(backup_path.rglob("*.py"))

    if not backup_files:
        console.print(f"[yellow]No Python files found in backup: {backup_dir}[/]")
        return

    console.print(Panel(
        f"[bold]Restore from backup[/]\n\n"
        f"Backup: {backup_path}\n"
        f"Files: {len(backup_files)}",
        title="Restore Backup",
    ))

    for bf in backup_files:
        relative = bf.relative_to(backup_path)
        console.print(f"  • {relative}")

    if not yes:
        console.print()
        if not Confirm.ask("Restore these files?"):
            console.print("[yellow]Aborted.[/]")
            return

    restored = 0
    for backup_file in backup_files:
        relative = backup_file.relative_to(backup_path)
        target = project_path / relative

        try:
            shutil.copy2(backup_file, target)
            console.print(f"[green]✓[/] {relative}")
            restored += 1
        except Exception as e:
            console.print(f"[red]✗[/] {relative} - {e}")

    console.print(f"\n[green]Restored {restored} file(s)[/]")

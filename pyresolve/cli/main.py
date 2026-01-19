"""Main CLI entry point for PyResolve."""

import click
from rich.console import Console

from pyresolve import __version__
from pyresolve.cli.commands.apply import apply
from pyresolve.cli.commands.diff import diff
from pyresolve.cli.commands.scan import scan
from pyresolve.cli.commands.upgrade import upgrade
from pyresolve.cli.commands.upgrade_all import upgrade_all

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="pyresolve")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """PyResolve - AI-powered Python dependency migration tool.

    Don't just flag the update. Fix the break.

    \b
    Examples:
        pyresolve upgrade pydantic --target 2.5.0
        pyresolve diff
        pyresolve apply
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


# Register commands
cli.add_command(scan)
cli.add_command(upgrade)
cli.add_command(upgrade_all)
cli.add_command(diff)
cli.add_command(apply)


@cli.command()
def libraries() -> None:
    """List supported libraries and their migration paths."""
    from rich.table import Table

    from pyresolve.knowledge_base import KnowledgeBaseLoader

    loader = KnowledgeBaseLoader()
    supported = loader.get_supported_libraries()

    table = Table(title="Supported Libraries")
    table.add_column("Library", style="cyan")
    table.add_column("Migration Path", style="green")
    table.add_column("Description", style="dim")

    for lib_name in supported:
        try:
            knowledge = loader.load(lib_name)
            for from_v, to_v in knowledge.supported_migrations:
                table.add_row(
                    knowledge.display_name,
                    f"v{from_v} → v{to_v}",
                    knowledge.description[:50] + "..." if len(knowledge.description) > 50 else knowledge.description,
                )
        except Exception:
            continue

    console.print(table)


@cli.command()
@click.option("--path", "-p", type=click.Path(exists=True), default=".", help="Project path")
def status(path: str) -> None:
    """Show current migration status and pending changes."""
    from pathlib import Path

    from rich.panel import Panel

    from pyresolve.cli.commands.upgrade import load_state

    project_path = Path(path).resolve()
    state = load_state(project_path)

    if state is None:
        console.print(Panel(
            "[yellow]No pending migration found.[/]\n\n"
            "Run [cyan]pyresolve upgrade <library> --target <version>[/] to start a migration.",
            title="Migration Status",
        ))
        return

    console.print(Panel(
        f"[green]Migration in progress[/]\n\n"
        f"Library: [cyan]{state.get('library', 'unknown')}[/]\n"
        f"Target version: [cyan]{state.get('target_version', 'unknown')}[/]\n"
        f"Files to modify: [cyan]{len(state.get('results', []))}[/]\n"
        f"Total changes: [cyan]{sum(r.get('change_count', 0) for r in state.get('results', []))}[/]\n\n"
        "Use [cyan]pyresolve diff[/] to view changes\n"
        "Use [cyan]pyresolve apply[/] to apply changes",
        title="Migration Status",
    ))


if __name__ == "__main__":
    cli()

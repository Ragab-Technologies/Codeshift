"""Main CLI entry point for PyResolve."""

import click
from rich.console import Console

from codeshift import __version__
from codeshift.cli.commands.apply import apply
from codeshift.cli.commands.auth import (
    billing,
    login,
    logout,
    quota,
    register,
    upgrade_plan,
    whoami,
)
from codeshift.cli.commands.diff import diff
from codeshift.cli.commands.scan import scan
from codeshift.cli.commands.upgrade import upgrade
from codeshift.cli.commands.upgrade_all import upgrade_all

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="codeshift")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """PyResolve - AI-powered Python dependency migration tool.

    Don't just flag the update. Fix the break.

    \b
    Examples:
        codeshift upgrade pydantic --target 2.5.0
        codeshift diff
        codeshift apply
    """
    # Ensure context object exists
    ctx.ensure_object(dict)


# Register commands
cli.add_command(scan)
cli.add_command(upgrade)
cli.add_command(upgrade_all)
cli.add_command(diff)
cli.add_command(apply)

# Auth commands
cli.add_command(register)
cli.add_command(login)
cli.add_command(logout)
cli.add_command(whoami)
cli.add_command(quota)
cli.add_command(upgrade_plan)
cli.add_command(billing)


@cli.command()
def libraries() -> None:
    """List supported libraries and their migration paths."""
    from rich.table import Table

    from codeshift.knowledge_base import KnowledgeBaseLoader

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
                    (
                        knowledge.description[:50] + "..."
                        if len(knowledge.description) > 50
                        else knowledge.description
                    ),
                )
        except Exception:
            continue

    console.print(table)


@cli.command()
@click.option("--path", "-p", type=click.Path(exists=True), default=".", help="Project path")
def status(path: str) -> None:
    """Show current migration status, pending changes, and quota info."""
    from pathlib import Path

    import httpx
    from rich.panel import Panel
    from rich.table import Table

    from codeshift.cli.commands.auth import get_api_key, get_api_url, load_credentials
    from codeshift.cli.commands.upgrade import load_state

    project_path = Path(path).resolve()
    state = load_state(project_path)

    # Show migration status
    if state is None:
        console.print(
            Panel(
                "[yellow]No pending migration found.[/]\n\n"
                "Run [cyan]codeshift upgrade <library> --target <version>[/] to start a migration.",
                title="Migration Status",
            )
        )
    else:
        console.print(
            Panel(
                f"[green]Migration in progress[/]\n\n"
                f"Library: [cyan]{state.get('library', 'unknown')}[/]\n"
                f"Target version: [cyan]{state.get('target_version', 'unknown')}[/]\n"
                f"Files to modify: [cyan]{len(state.get('results', []))}[/]\n"
                f"Total changes: [cyan]{sum(r.get('change_count', 0) for r in state.get('results', []))}[/]\n\n"
                "Use [cyan]codeshift diff[/] to view changes\n"
                "Use [cyan]codeshift apply[/] to apply changes",
                title="Migration Status",
            )
        )

    # Show authentication and quota status
    console.print()

    creds = load_credentials()
    api_key = get_api_key()

    if not creds and not api_key:
        console.print(
            Panel(
                "[yellow]Not logged in[/]\n\n"
                "Run [cyan]codeshift login[/] to authenticate and unlock cloud features.\n"
                "[dim]Free tier: 100 files/month, 50 LLM calls/month[/]",
                title="Account Status",
            )
        )
        return

    # Try to fetch quota from API
    try:
        api_url = get_api_url()
        headers: dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        response = httpx.get(
            f"{api_url}/usage/quota",
            headers=headers,
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()

            # Build quota table
            table = Table(show_header=False, box=None)
            table.add_column("Label", style="dim")
            table.add_column("Value")

            table.add_row("Tier", f"[cyan]{data['tier'].title()}[/]")
            table.add_row("Billing Period", data["billing_period"])
            table.add_row(
                "File Migrations",
                f"{data['files_migrated']}/{data['files_limit']} ({data['files_remaining']} remaining)",
            )
            table.add_row(
                "LLM Calls",
                f"{data['llm_calls']}/{data['llm_calls_limit']} ({data['llm_calls_remaining']} remaining)",
            )

            email_display = creds.get("email", "Authenticated") if creds else "Authenticated"
            console.print(
                Panel(
                    table,
                    title=f"Account Status - {email_display}",
                )
            )

            # Show warning if near limit
            if data["files_percentage"] > 80 or data["llm_calls_percentage"] > 80:
                console.print(
                    "[yellow]Running low on quota![/] "
                    "Run [cyan]codeshift upgrade-plan[/] to see upgrade options."
                )
        else:
            # Fall back to cached info
            cached_email = creds.get("email", "unknown") if creds else "unknown"
            cached_tier = creds.get("tier", "free") if creds else "free"
            console.print(
                Panel(
                    f"[green]Logged in[/] [dim](offline)[/]\n"
                    f"Email: [cyan]{cached_email}[/]\n"
                    f"Tier: [cyan]{cached_tier}[/]",
                    title="Account Status",
                )
            )
    except httpx.RequestError:
        # Offline - show cached info
        if creds:
            console.print(
                Panel(
                    f"[green]Logged in[/] [dim](offline)[/]\n"
                    f"Email: [cyan]{creds.get('email', 'unknown')}[/]\n"
                    f"Tier: [cyan]{creds.get('tier', 'free')}[/]",
                    title="Account Status",
                )
            )


if __name__ == "__main__":
    cli()

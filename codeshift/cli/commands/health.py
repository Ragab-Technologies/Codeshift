"""CLI command for codebase health scoring."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codeshift.health.calculator import HealthCalculator
from codeshift.health.models import HealthGrade, MetricCategory
from codeshift.health.report import (
    generate_json_report,
    save_html_report,
    save_json_report,
)

console = Console()


@click.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    help="Path to the project (default: current directory)",
)
@click.option(
    "--report",
    "-r",
    type=click.Choice(["json", "html"]),
    help="Generate a detailed report in the specified format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path for the report (default: health_report.<format>)",
)
@click.option(
    "--ci",
    is_flag=True,
    help="CI mode: exit with non-zero status if score is below threshold",
)
@click.option(
    "--threshold",
    type=int,
    default=70,
    help="Minimum score for CI mode (default: 70)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed output including all dependencies",
)
def health(
    path: str,
    report: str | None,
    output: str | None,
    ci: bool,
    threshold: int,
    verbose: bool,
) -> None:
    """Analyze codebase health and generate a score.

    Evaluates your project across five dimensions:
    - Dependency Freshness (30%): How up-to-date are your dependencies?
    - Security (25%): Known vulnerabilities in dependencies
    - Migration Readiness (20%): Tier 1/2 support coverage
    - Test Coverage (15%): Percentage of code covered by tests
    - Documentation (10%): Type hints and docstrings

    \b
    Examples:
        codeshift health                     # Show health summary
        codeshift health --report html       # Generate HTML report
        codeshift health --report json -o report.json
        codeshift health --ci --threshold 70 # CI mode

    """
    project_path = Path(path).resolve()

    with console.status("[bold blue]Analyzing codebase health..."):
        calculator = HealthCalculator()
        score = calculator.calculate(project_path)

    # Handle report generation
    if report:
        output_path = Path(output) if output else Path(f"health_report.{report}")

        if report == "json":
            save_json_report(score, output_path)
            console.print(f"[green]JSON report saved to:[/] {output_path}")
        elif report == "html":
            save_html_report(score, output_path)
            console.print(f"[green]HTML report saved to:[/] {output_path}")

        # In CI mode with report, also output JSON to stdout
        if ci:
            console.print(generate_json_report(score))
    else:
        # Display rich table output
        _display_health_summary(score, verbose)

    # CI mode exit code handling
    if ci:
        if score.overall_score < threshold:
            console.print(
                f"\n[red]CI Check Failed:[/] Score {score.overall_score:.1f} is below threshold {threshold}"
            )
            sys.exit(1)
        else:
            console.print(
                f"\n[green]CI Check Passed:[/] Score {score.overall_score:.1f} meets threshold {threshold}"
            )
            sys.exit(0)


def _display_health_summary(score, verbose: bool) -> None:
    """Display the health score summary in the terminal.

    Args:
        score: HealthScore object
        verbose: Whether to show detailed output
    """
    # Grade panel
    grade_style = _get_grade_style(score.grade)
    console.print(
        Panel(
            f"[{grade_style}]Grade {score.grade.value}[/] - {score.overall_score:.1f}/100",
            title="[bold]Codebase Health Score[/]",
            subtitle=str(score.project_path),
        )
    )

    # Metrics table
    table = Table(title="Metrics Breakdown", show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Weight", justify="right", style="dim")
    table.add_column("Details")

    # Sort by score (lowest first) to highlight problem areas
    sorted_metrics = sorted(score.metrics, key=lambda m: m.score)

    for metric in sorted_metrics:
        score_style = _get_score_style(metric.score)
        weight_pct = f"{metric.weight * 100:.0f}%"
        table.add_row(
            _format_category(metric.category),
            f"[{score_style}]{metric.score:.1f}[/]",
            weight_pct,
            metric.description,
        )

    console.print(table)

    # Recommendations
    if score.top_recommendations:
        console.print("\n[bold]Top Recommendations:[/]")
        for i, rec in enumerate(score.top_recommendations, 1):
            console.print(f"  {i}. {rec}")

    # Verbose: show dependencies
    if verbose and score.dependencies:
        console.print()
        deps_table = Table(title="Dependencies", show_header=True)
        deps_table.add_column("Package", style="cyan")
        deps_table.add_column("Current")
        deps_table.add_column("Latest")
        deps_table.add_column("Status")
        deps_table.add_column("Migration")
        deps_table.add_column("Vulns", justify="right")

        for dep in score.dependencies:
            status = "[green]✓[/]" if not dep.is_outdated else "[yellow]↑[/]"
            tier = (
                "[green]Tier 1[/]"
                if dep.has_tier1_support
                else ("[cyan]Tier 2[/]" if dep.has_tier2_support else "[dim]-[/]")
            )
            vuln_count = len(dep.vulnerabilities)
            vuln_style = "green" if vuln_count == 0 else "red"

            deps_table.add_row(
                dep.name,
                dep.current_version or "?",
                dep.latest_version or "?",
                status,
                tier,
                f"[{vuln_style}]{vuln_count}[/]",
            )

        console.print(deps_table)

    # Show vulnerabilities summary if any
    if score.vulnerabilities:
        console.print()
        console.print(
            f"[bold red]Security Alert:[/] {len(score.vulnerabilities)} vulnerabilities found"
        )
        for vuln in score.vulnerabilities[:3]:
            console.print(
                f"  - [{vuln.severity.value.upper()}] {vuln.package}: {vuln.vulnerability_id}"
            )
        if len(score.vulnerabilities) > 3:
            console.print(f"  ... and {len(score.vulnerabilities) - 3} more")


def _get_grade_style(grade: HealthGrade) -> str:
    """Get Rich style for a grade."""
    styles = {
        HealthGrade.A: "bold green",
        HealthGrade.B: "bold cyan",
        HealthGrade.C: "bold yellow",
        HealthGrade.D: "bold orange1",
        HealthGrade.F: "bold red",
    }
    return styles.get(grade, "white")


def _get_score_style(score: float) -> str:
    """Get Rich style for a numeric score."""
    if score >= 90:
        return "green"
    elif score >= 80:
        return "cyan"
    elif score >= 70:
        return "yellow"
    elif score >= 60:
        return "orange1"
    else:
        return "red"


def _format_category(category: MetricCategory) -> str:
    """Format category for display."""
    names = {
        MetricCategory.FRESHNESS: "Freshness",
        MetricCategory.SECURITY: "Security",
        MetricCategory.MIGRATION_READINESS: "Migration Ready",
        MetricCategory.TEST_COVERAGE: "Test Coverage",
        MetricCategory.DOCUMENTATION: "Documentation",
    }
    return names.get(category, category.value)

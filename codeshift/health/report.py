"""Report generation for health scores (JSON and HTML)."""

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from codeshift.health.models import HealthReport, HealthScore


def generate_json_report(report: HealthReport | HealthScore, pretty: bool = True) -> str:
    """Generate a JSON report.

    Args:
        report: HealthReport or HealthScore to serialize
        pretty: Whether to pretty-print the JSON

    Returns:
        JSON string
    """
    if isinstance(report, HealthScore):
        data = report.to_dict()
    else:
        data = report.to_dict()

    if pretty:
        return json.dumps(data, indent=2, default=_json_serializer)
    return json.dumps(data, default=_json_serializer)


def save_json_report(report: HealthReport | HealthScore, output_path: Path) -> None:
    """Save a JSON report to a file.

    Args:
        report: HealthReport or HealthScore to serialize
        output_path: Path to save the report
    """
    json_content = generate_json_report(report)
    output_path.write_text(json_content)


def generate_html_report(report: HealthReport | HealthScore) -> str:
    """Generate an HTML report.

    Args:
        report: HealthReport or HealthScore to render

    Returns:
        HTML string
    """
    if isinstance(report, HealthScore):
        score = report
        trend_info = ""
    else:
        score = report.current
        if report.previous:
            delta = report.score_delta or 0
            sign = "+" if delta >= 0 else ""
            trend_info = f'<span class="trend {report.trend}">{report.trend_emoji} {sign}{delta:.1f}</span>'
        else:
            trend_info = '<span class="trend new">New baseline</span>'

    # Build metrics rows
    metrics_rows = ""
    for metric in score.metrics:
        grade_class = _get_score_class(metric.score)
        metrics_rows += f"""
        <tr>
            <td>{_format_category(metric.category.value)}</td>
            <td class="{grade_class}">{metric.score:.1f}</td>
            <td>{metric.weight * 100:.0f}%</td>
            <td>{html.escape(metric.description)}</td>
        </tr>
        """

    # Build recommendations list
    recs_html = ""
    for rec in score.top_recommendations:
        recs_html += f"<li>{html.escape(rec)}</li>\n"

    # Build dependencies table
    deps_rows = ""
    for dep in score.dependencies:
        status = "✓" if not dep.is_outdated else "↑"
        status_class = "up-to-date" if not dep.is_outdated else "outdated"
        tier = "Tier 1" if dep.has_tier1_support else ("Tier 2" if dep.has_tier2_support else "-")
        vuln_count = len(dep.vulnerabilities)
        vuln_class = "vuln-none" if vuln_count == 0 else "vuln-some"

        deps_rows += f"""
        <tr>
            <td>{html.escape(dep.name)}</td>
            <td>{html.escape(dep.current_version or 'unknown')}</td>
            <td>{html.escape(dep.latest_version or 'unknown')}</td>
            <td class="{status_class}">{status}</td>
            <td>{tier}</td>
            <td class="{vuln_class}">{vuln_count}</td>
        </tr>
        """

    # Build vulnerabilities section
    vulns_html = ""
    if score.vulnerabilities:
        vulns_rows = ""
        for vuln in score.vulnerabilities:
            vulns_rows += f"""
            <tr class="severity-{vuln.severity.value}">
                <td>{html.escape(vuln.package)}</td>
                <td>{html.escape(vuln.vulnerability_id)}</td>
                <td>{vuln.severity.value.upper()}</td>
                <td>{html.escape(vuln.description[:100])}...</td>
                <td>{html.escape(vuln.fixed_in or '-')}</td>
            </tr>
            """

        vulns_html = f"""
        <section class="vulnerabilities">
            <h2>Security Vulnerabilities</h2>
            <table>
                <thead>
                    <tr>
                        <th>Package</th>
                        <th>ID</th>
                        <th>Severity</th>
                        <th>Description</th>
                        <th>Fixed In</th>
                    </tr>
                </thead>
                <tbody>
                    {vulns_rows}
                </tbody>
            </table>
        </section>
        """

    grade_class = score.grade.value.lower()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codeshift Health Report</title>
    <style>
        :root {{
            --color-a: #22c55e;
            --color-b: #06b6d4;
            --color-c: #eab308;
            --color-d: #f97316;
            --color-f: #ef4444;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #1f2937;
            background: #f9fafb;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ margin-bottom: 0.5rem; }}
        h2 {{ margin: 2rem 0 1rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }}
        .score-card {{
            background: white;
            border-radius: 12px;
            padding: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .grade {{ font-size: 4rem; font-weight: bold; }}
        .grade.a {{ color: var(--color-a); }}
        .grade.b {{ color: var(--color-b); }}
        .grade.c {{ color: var(--color-c); }}
        .grade.d {{ color: var(--color-d); }}
        .grade.f {{ color: var(--color-f); }}
        .overall-score {{ font-size: 1.5rem; color: #6b7280; }}
        .trend {{ font-size: 1rem; margin-top: 0.5rem; display: block; }}
        .trend.improving {{ color: var(--color-a); }}
        .trend.declining {{ color: var(--color-f); }}
        .trend.stable {{ color: #6b7280; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e5e7eb; }}
        th {{ background: #f3f4f6; font-weight: 600; }}
        tr:last-child td {{ border-bottom: none; }}
        .excellent {{ color: var(--color-a); font-weight: 600; }}
        .good {{ color: var(--color-b); font-weight: 600; }}
        .fair {{ color: var(--color-c); font-weight: 600; }}
        .poor {{ color: var(--color-d); font-weight: 600; }}
        .critical {{ color: var(--color-f); font-weight: 600; }}
        .up-to-date {{ color: var(--color-a); }}
        .outdated {{ color: var(--color-d); }}
        .vuln-none {{ color: var(--color-a); }}
        .vuln-some {{ color: var(--color-f); font-weight: 600; }}
        .severity-critical td {{ background: #fef2f2; }}
        .severity-high td {{ background: #fff7ed; }}
        .recommendations {{ background: white; border-radius: 8px; padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .recommendations ul {{ padding-left: 1.5rem; }}
        .recommendations li {{ margin: 0.5rem 0; }}
        .meta {{ color: #6b7280; font-size: 0.875rem; margin-top: 2rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Codeshift Health Report</h1>
                <p>{html.escape(str(score.project_path))}</p>
            </div>
            <div class="score-card">
                <div class="grade {grade_class}">{score.grade.value}</div>
                <div class="overall-score">{score.overall_score:.1f}/100</div>
                {trend_info}
            </div>
        </div>

        <section>
            <h2>Metrics Breakdown</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Score</th>
                        <th>Weight</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {metrics_rows}
                </tbody>
            </table>
        </section>

        <section class="recommendations">
            <h2>Recommendations</h2>
            <ul>
                {recs_html if recs_html else "<li>No recommendations - your project is in great shape!</li>"}
            </ul>
        </section>

        <section>
            <h2>Dependencies ({len(score.dependencies)})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Package</th>
                        <th>Current</th>
                        <th>Latest</th>
                        <th>Status</th>
                        <th>Migration Support</th>
                        <th>Vulnerabilities</th>
                    </tr>
                </thead>
                <tbody>
                    {deps_rows if deps_rows else "<tr><td colspan='6'>No dependencies found</td></tr>"}
                </tbody>
            </table>
        </section>

        {vulns_html}

        <p class="meta">
            Generated by Codeshift on {score.calculated_at.strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""


def save_html_report(report: HealthReport | HealthScore, output_path: Path) -> None:
    """Save an HTML report to a file.

    Args:
        report: HealthReport or HealthScore to render
        output_path: Path to save the report
    """
    html_content = generate_html_report(report)
    output_path.write_text(html_content)


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _get_score_class(score: float) -> str:
    """Get CSS class based on score."""
    if score >= 90:
        return "excellent"
    elif score >= 80:
        return "good"
    elif score >= 70:
        return "fair"
    elif score >= 60:
        return "poor"
    else:
        return "critical"


def _format_category(category: str) -> str:
    """Format category name for display."""
    return category.replace("_", " ").title()

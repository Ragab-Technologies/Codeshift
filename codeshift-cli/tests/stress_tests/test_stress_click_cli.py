"""
Stress test file for Click 7.x to 8.x migration.

This file contains a VERY complex Click CLI application designed to test
the Codeshift migration tool's ability to handle:
- Multi-level command groups (3+ levels deep)
- 25+ commands and subcommands
- Options with various types
- Arguments with nargs and variadic
- Context passing
- Custom parameter types
- Callbacks and eager options
- Password prompts
- File and path types
- Choice and IntRange types
- Default from environment
- Shell completion (autocompletion)
- Result callbacks
- Standalone mode handling
- Color and styling
- Progress bars
- MultiCommand/BaseCommand (deprecated in Click 8.x)
- get_terminal_size (deprecated in Click 8.x)
- output_bytes (deprecated in Click 8.x)

This file uses Click 7.x APIs that should be migrated to Click 8.x.
"""

from typing import Any

import click
from click import BaseCommand, MultiCommand
from click.testing import CliRunner

# ==============================================================================
# CUSTOM PARAMETER TYPES (Click 7.x style)
# ==============================================================================


class CommaSeparatedList(click.ParamType):
    """Custom parameter type that parses comma-separated values."""

    name = "comma_list"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> list[str]:
        if isinstance(value, list):
            return value
        if value is None:
            return []
        return [item.strip() for item in value.split(",")]


class IPAddressType(click.ParamType):
    """Custom parameter type for IP addresses."""

    name = "ip_address"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> str:
        import re

        if isinstance(value, str):
            if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", value):
                return value
        self.fail(f"{value!r} is not a valid IP address", param, ctx)


class ByteSizeType(click.ParamType):
    """Custom parameter type for byte sizes like 1GB, 500MB."""

    name = "bytesize"

    def convert(
        self, value: Any, param: click.Parameter | None, ctx: click.Context | None
    ) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
            value = value.upper().strip()
            for suffix, mult in multipliers.items():
                if value.endswith(suffix):
                    return int(value[: -len(suffix)]) * mult
            return int(value)
        self.fail(f"{value!r} is not a valid byte size", param, ctx)


COMMA_LIST = CommaSeparatedList()
IP_ADDRESS = IPAddressType()
BYTE_SIZE = ByteSizeType()


# ==============================================================================
# AUTOCOMPLETION FUNCTIONS (Click 7.x style - should become shell_complete)
# ==============================================================================


def complete_environment(ctx: click.Context, args: list[str], incomplete: str) -> list[str]:
    """Autocomplete environment names - Click 7.x style callback signature."""
    environments = ["development", "staging", "production", "testing", "local"]
    return [env for env in environments if env.startswith(incomplete)]


def complete_regions(ctx: click.Context, args: list[str], incomplete: str) -> list[str]:
    """Autocomplete cloud regions - Click 7.x style."""
    regions = [
        "us-east-1",
        "us-west-2",
        "eu-west-1",
        "eu-central-1",
        "ap-southeast-1",
        "ap-northeast-1",
    ]
    return [r for r in regions if r.startswith(incomplete)]


def complete_services(ctx: click.Context, args: list[str], incomplete: str) -> list[str]:
    """Autocomplete service names - Click 7.x style."""
    services = ["api", "web", "worker", "scheduler", "database", "cache", "queue", "storage"]
    return [s for s in services if s.startswith(incomplete)]


def complete_log_levels(ctx: click.Context, args: list[str], incomplete: str) -> list[str]:
    """Autocomplete log levels - Click 7.x style."""
    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    return [lvl for lvl in levels if lvl.startswith(incomplete.upper())]


def complete_file_formats(ctx: click.Context, args: list[str], incomplete: str) -> list[str]:
    """Autocomplete file formats - Click 7.x style."""
    formats = ["json", "yaml", "toml", "xml", "csv", "ini"]
    return [f for f in formats if f.startswith(incomplete)]


# ==============================================================================
# CALLBACKS AND EAGER OPTIONS
# ==============================================================================


def validate_port(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Validate port is in valid range."""
    if value < 1 or value > 65535:
        raise click.BadParameter(f"Port must be between 1 and 65535, got {value}")
    return value


def validate_memory_limit(
    ctx: click.Context, param: click.Parameter, value: int | None
) -> int | None:
    """Validate memory limit is reasonable."""
    if value is not None and value < 64:
        raise click.BadParameter(f"Memory limit must be at least 64MB, got {value}")
    return value


def print_version(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    """Eager callback for --version flag."""
    if not value or ctx.resilient_parsing:
        return
    # Using deprecated Click 7.x way to get version
    version = click.__version__
    click.echo(f"CLI Version: {version}")
    ctx.exit()


def configure_verbose(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Configure verbosity level and store in context."""
    ctx.ensure_object(dict)
    ctx.obj["verbosity"] = value
    return value


def set_dry_run(ctx: click.Context, param: click.Parameter, value: bool) -> bool:
    """Set dry-run mode globally in context."""
    ctx.ensure_object(dict)
    ctx.obj["dry_run"] = value
    return value


# ==============================================================================
# DEPRECATED MULTICOMMAND AND BASECOMMAND USAGE (Click 7.x)
# ==============================================================================


class DynamicPluginLoader(MultiCommand):
    """Custom MultiCommand that loads commands dynamically - deprecated in Click 8.x."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return ["plugin-a", "plugin-b", "plugin-c"]

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        if name in self.list_commands(ctx):

            @click.command()
            def plugin_cmd():
                click.echo(f"Executing plugin: {name}")

            return plugin_cmd
        return None


class MinimalCommand(BaseCommand):
    """Custom BaseCommand implementation - deprecated in Click 8.x."""

    def invoke(self, ctx: click.Context) -> Any:
        click.echo("Minimal command executed")
        return 0


# ==============================================================================
# MAIN CLI GROUP AND SUBGROUPS
# ==============================================================================


@click.group()
@click.option(
    "-v",
    "--verbose",
    count=True,
    callback=configure_verbose,
    expose_value=False,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.option(
    "--version",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Show version and exit",
)
@click.option(
    "--config",
    type=click.Path(exists=False, dir_okay=False),
    envvar="CLI_CONFIG",
    help="Configuration file path",
)
@click.option("--dry-run", is_flag=True, callback=set_dry_run, expose_value=False)
@click.pass_context
def cli(ctx: click.Context, config: str | None) -> None:
    """
    Advanced CLI Application - Stress Test for Codeshift Migration.

    This CLI demonstrates many Click features that changed between 7.x and 8.x.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = config

    # Using deprecated get_terminal_size (Click 7.x)
    width, height = click.get_terminal_size()
    if ctx.obj.get("verbosity", 0) > 2:
        click.echo(f"Terminal size: {width}x{height}")


# ==============================================================================
# DEPLOY GROUP (Level 1)
# ==============================================================================


@cli.group()
@click.option(
    "--environment",
    "-e",
    autocompletion=complete_environment,  # Click 7.x style
    help="Target environment",
)
@click.pass_context
def deploy(ctx: click.Context, environment: str | None) -> None:
    """Deployment commands for various platforms."""
    ctx.obj["environment"] = environment


@deploy.command()
@click.option("--region", autocompletion=complete_regions, help="Cloud region")
@click.option(
    "--instance-type",
    type=click.Choice(["t2.micro", "t2.small", "t2.medium", "t3.large", "t3.xlarge"]),
    default="t2.small",
)
@click.option("--count", type=click.IntRange(1, 100), default=1, help="Number of instances")
@click.option("--memory", type=BYTE_SIZE, help="Memory limit (e.g., 512MB, 2GB)")
@click.option("--storage", type=click.IntRange(10, 1000), help="Storage in GB")
@click.argument("service", nargs=1)
@click.pass_context
def aws(
    ctx: click.Context,
    region: str,
    instance_type: str,
    count: int,
    memory: int | None,
    storage: int | None,
    service: str,
) -> None:
    """Deploy to AWS."""
    env = ctx.obj.get("environment", "development")
    click.secho(f"Deploying {service} to AWS {region}", fg="green", bold=True)
    click.echo(f"Environment: {env}, Instances: {count}, Type: {instance_type}")


@deploy.command()
@click.option("--project", required=True, envvar="GCP_PROJECT", help="GCP project ID")
@click.option("--zone", default="us-central1-a", help="GCP zone")
@click.option("--machine-type", default="n1-standard-1")
@click.argument("services", nargs=-1, required=True)
@click.pass_context
def gcp(
    ctx: click.Context, project: str, zone: str, machine_type: str, services: tuple[str, ...]
) -> None:
    """Deploy to Google Cloud Platform."""
    for service in services:
        click.secho(f"Deploying {service} to GCP {project}/{zone}", fg="blue")


@deploy.command()
@click.option("--resource-group", "-g", required=True)
@click.option("--location", type=click.Choice(["eastus", "westus", "northeurope", "westeurope"]))
@click.option("--sku", default="B1")
@click.argument("app_name")
@click.pass_context
def azure(
    ctx: click.Context, resource_group: str, location: str, sku: str, app_name: str
) -> None:
    """Deploy to Microsoft Azure."""
    click.secho(f"Deploying {app_name} to Azure {resource_group}", fg="cyan")


# ==============================================================================
# KUBERNETES GROUP (Level 1)
# ==============================================================================


@cli.group()
@click.option("--kubeconfig", type=click.Path(exists=True), envvar="KUBECONFIG")
@click.option("--context", "-c", help="Kubernetes context to use")
@click.option("--namespace", "-n", default="default")
@click.pass_context
def k8s(ctx: click.Context, kubeconfig: str | None, context: str | None, namespace: str):
    """Kubernetes management commands."""
    ctx.obj["kubeconfig"] = kubeconfig
    ctx.obj["k8s_context"] = context
    ctx.obj["namespace"] = namespace


@k8s.command("apply")
@click.option("--file", "-f", type=click.Path(exists=True), multiple=True, required=True)
@click.option("--recursive", "-R", is_flag=True)
@click.option("--validate/--no-validate", default=True)
@click.pass_context
def k8s_apply(
    ctx: click.Context, file: tuple[str, ...], recursive: bool, validate: bool
) -> None:
    """Apply Kubernetes manifests."""
    ns = ctx.obj["namespace"]
    for f in file:
        click.echo(f"Applying {f} to namespace {ns}")


@k8s.command("logs")
@click.option("--follow", "-f", is_flag=True)
@click.option("--tail", type=int, default=100)
@click.option("--container", "-c")
@click.option(
    "--timestamps/--no-timestamps", default=False, help="Include timestamps in log output"
)
@click.argument("pod")
@click.pass_context
def k8s_logs(
    ctx: click.Context,
    follow: bool,
    tail: int,
    container: str | None,
    timestamps: bool,
    pod: str,
) -> None:
    """View pod logs."""
    click.echo(f"Showing logs for pod {pod} (tail={tail}, follow={follow})")


@k8s.group()
@click.pass_context
def rollout(ctx: click.Context) -> None:
    """Manage rollouts."""
    pass


@rollout.command()
@click.argument("deployment")
@click.pass_context
def status(ctx: click.Context, deployment: str) -> None:
    """Check rollout status."""
    click.echo(f"Checking rollout status for {deployment}")


@rollout.command()
@click.option("--revision", type=int)
@click.argument("deployment")
@click.pass_context
def undo(ctx: click.Context, revision: int | None, deployment: str) -> None:
    """Undo a rollout."""
    rev_msg = f" to revision {revision}" if revision else ""
    click.echo(f"Rolling back {deployment}{rev_msg}")


# ==============================================================================
# DATABASE GROUP (Level 1)
# ==============================================================================


@cli.group()
@click.option(
    "--host",
    "-h",
    default="localhost",
    type=IP_ADDRESS,
    help="Database host",
)
@click.option("--port", "-p", type=int, default=5432, callback=validate_port)
@click.option("--database", "-d", required=True, envvar="DATABASE_NAME")
@click.option("--username", "-u", envvar="DATABASE_USER")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=False)
@click.pass_context
def db(
    ctx: click.Context,
    host: str,
    port: int,
    database: str,
    username: str | None,
    password: str,
) -> None:
    """Database management commands."""
    ctx.obj["db_config"] = {
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password": password,
    }


@db.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["sql", "csv", "json"]),
    default="sql",
    autocompletion=complete_file_formats,  # Click 7.x style
)
@click.option("--tables", type=COMMA_LIST, help="Comma-separated list of tables")
@click.option("--output", "-o", type=click.File("w"), default="-")
@click.option("--compress/--no-compress", default=False)
@click.pass_context
def backup(
    ctx: click.Context,
    output_format: str,
    tables: list[str],
    output: click.utils.LazyFile,
    compress: bool,
) -> None:
    """Backup database."""
    db_name = ctx.obj["db_config"]["database"]
    click.secho(f"Backing up {db_name} in {output_format} format", fg="yellow")
    if tables:
        click.echo(f"Tables: {', '.join(tables)}")


@db.command()
@click.option("--file", "-f", type=click.File("rb"), required=True)
@click.option("--drop-existing/--keep-existing", default=False)
@click.option("--schema-only", is_flag=True)
@click.confirmation_option(prompt="Are you sure you want to restore?")
@click.pass_context
def restore(
    ctx: click.Context,
    file: click.utils.LazyFile,
    drop_existing: bool,
    schema_only: bool,
) -> None:
    """Restore database from backup."""
    click.secho("Restoring database...", fg="red", bold=True)


@db.command()
@click.option("--direction", type=click.Choice(["up", "down"]), default="up")
@click.option("--steps", type=click.IntRange(1, 100), default=1)
@click.option("--dry-run", is_flag=True)
@click.pass_context
def migrate(ctx: click.Context, direction: str, steps: int, dry_run: bool) -> None:
    """Run database migrations."""
    action = "upgrade" if direction == "up" else "downgrade"
    click.echo(f"Running {steps} {action} migration(s)")


# ==============================================================================
# CONFIG GROUP (Level 1)
# ==============================================================================


@cli.group()
@click.pass_context
def config(ctx: click.Context) -> None:
    """Configuration management."""
    pass


@config.command("get")
@click.argument("key")
@click.option("--default", "default_value")
@click.pass_context
def config_get(ctx: click.Context, key: str, default_value: str | None) -> None:
    """Get a configuration value."""
    click.echo(f"Config value for {key}: (default: {default_value})")


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.option("--global", "is_global", is_flag=True)
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str, is_global: bool) -> None:
    """Set a configuration value."""
    scope = "global" if is_global else "local"
    click.echo(f"Setting {key}={value} ({scope})")


@config.command("list")
@click.option("--format", type=click.Choice(["table", "json", "yaml"]), default="table")
@click.pass_context
def config_list(ctx: click.Context, format: str) -> None:
    """List all configuration values."""
    click.echo(f"Listing config in {format} format")


# ==============================================================================
# LOGS GROUP (Level 1) - WITH RESULT CALLBACK
# ==============================================================================


@cli.group(chain=True)
@click.option("--source", type=click.Path(exists=True), help="Log file source")
@click.option(
    "--level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    autocompletion=complete_log_levels,  # Click 7.x style
)
@click.pass_context
def logs(ctx: click.Context, source: str | None, level: str | None) -> None:
    """Log processing commands (chainable)."""
    ctx.obj["log_source"] = source
    ctx.obj["log_level"] = level


@logs.resultcallback()  # Click 7.x style - should become result_callback in 8.x
@click.pass_context
def logs_result_callback(ctx: click.Context, results: list[Any]) -> None:
    """Process chained log command results."""
    click.echo(f"Processed {len(results)} log operations")


@logs.command("filter")
@click.option("--pattern", "-p", required=True)
@click.option("--invert", "-v", is_flag=True)
@click.pass_context
def logs_filter(ctx: click.Context, pattern: str, invert: bool) -> dict:
    """Filter log entries."""
    return {"operation": "filter", "pattern": pattern, "invert": invert}


@logs.command("stats")
@click.option("--group-by", type=click.Choice(["hour", "day", "week", "month"]))
@click.pass_context
def logs_stats(ctx: click.Context, group_by: str | None) -> dict:
    """Show log statistics."""
    return {"operation": "stats", "group_by": group_by}


# ==============================================================================
# SECRETS GROUP (Level 1) - WITH PASSWORD PROMPTS
# ==============================================================================


@cli.group()
@click.option(
    "--vault",
    type=click.Choice(["aws", "hashicorp", "azure", "gcp"]),
    default="aws",
)
@click.pass_context
def secrets(ctx: click.Context, vault: str) -> None:
    """Secret management commands."""
    ctx.obj["vault_type"] = vault


@secrets.command("create")
@click.argument("name")
@click.option("--value", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--description")
@click.option("--tags", type=COMMA_LIST, help="Comma-separated tags")
@click.pass_context
def secrets_create(
    ctx: click.Context, name: str, value: str, description: str | None, tags: list[str]
) -> None:
    """Create a new secret."""
    vault = ctx.obj["vault_type"]
    click.secho(f"Creating secret {name} in {vault} vault", fg="green")


@secrets.command("rotate")
@click.argument("name")
@click.option("--new-value", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--force", is_flag=True)
@click.pass_context
def secrets_rotate(
    ctx: click.Context, name: str, new_value: str, force: bool
) -> None:
    """Rotate a secret's value."""
    click.secho(f"Rotating secret {name}", fg="yellow")


# ==============================================================================
# MONITORING GROUP (Level 1)
# ==============================================================================


@cli.group()
@click.option("--service", "-s", autocompletion=complete_services)  # Click 7.x style
@click.pass_context
def monitor(ctx: click.Context, service: str | None) -> None:
    """Monitoring and alerting commands."""
    ctx.obj["monitor_service"] = service


@monitor.command("status")
@click.option("--format", type=click.Choice(["text", "json", "prometheus"]), default="text")
@click.option("--metrics", type=COMMA_LIST, help="Specific metrics to show")
@click.pass_context
def monitor_status(ctx: click.Context, format: str, metrics: list[str]) -> None:
    """Show service status."""
    service = ctx.obj.get("monitor_service", "all")
    click.echo(f"Status of {service} in {format} format")


@monitor.command("alerts")
@click.option("--severity", type=click.Choice(["info", "warning", "critical"]), multiple=True)
@click.option("--since", type=click.DateTime())
@click.option("--limit", type=click.IntRange(1, 1000), default=50)
@click.pass_context
def monitor_alerts(
    ctx: click.Context, severity: tuple[str, ...], since, limit: int
) -> None:
    """List active alerts."""
    click.echo(f"Listing {limit} alerts")


# ==============================================================================
# NETWORK GROUP (Level 1) - WITH NESTED SUBGROUPS (Level 2)
# ==============================================================================


@cli.group()
@click.option("--interface", "-i", default="eth0")
@click.pass_context
def network(ctx: click.Context, interface: str) -> None:
    """Network management commands."""
    ctx.obj["network_interface"] = interface


@network.group()
@click.pass_context
def dns(ctx: click.Context) -> None:
    """DNS management."""
    pass


@dns.command("lookup")
@click.argument("domain")
@click.option("--type", "record_type", type=click.Choice(["A", "AAAA", "CNAME", "MX", "TXT"]))
@click.pass_context
def dns_lookup(ctx: click.Context, domain: str, record_type: str | None) -> None:
    """Perform DNS lookup."""
    click.echo(f"Looking up {domain} ({record_type or 'A'})")


@dns.command("cache")
@click.option("--clear", is_flag=True)
@click.option("--stats", is_flag=True)
@click.pass_context
def dns_cache(ctx: click.Context, clear: bool, stats: bool) -> None:
    """Manage DNS cache."""
    if clear:
        click.echo("Clearing DNS cache")
    if stats:
        click.echo("DNS cache statistics")


@network.group()
@click.pass_context
def firewall(ctx: click.Context) -> None:
    """Firewall management."""
    pass


@firewall.command("rule")
@click.option("--action", type=click.Choice(["allow", "deny"]), required=True)
@click.option("--port", type=int, callback=validate_port)
@click.option("--protocol", type=click.Choice(["tcp", "udp"]), default="tcp")
@click.option("--source", type=IP_ADDRESS)
@click.pass_context
def firewall_rule(
    ctx: click.Context,
    action: str,
    port: int,
    protocol: str,
    source: str | None,
) -> None:
    """Add firewall rule."""
    click.echo(f"Adding {action} rule for {protocol}/{port}")


# ==============================================================================
# BUILD GROUP (Level 1) - WITH PROGRESS AND STYLING
# ==============================================================================


@cli.group()
@click.option("--parallel", "-j", type=click.IntRange(1, 32), default=4)
@click.pass_context
def build(ctx: click.Context, parallel: int) -> None:
    """Build and compilation commands."""
    ctx.obj["build_parallel"] = parallel


@build.command()
@click.option("--target", "-t", multiple=True, help="Build targets")
@click.option("--release/--debug", default=False)
@click.option("--clean", is_flag=True)
@click.pass_context
def run(ctx: click.Context, target: tuple[str, ...], release: bool, clean: bool) -> None:
    """Run build."""
    mode = "release" if release else "debug"
    click.secho(f"Building in {mode} mode with {ctx.obj['build_parallel']} jobs", fg="green")

    # Using deprecated terminal size (Click 7.x)
    width, _ = click.get_terminal_size()
    click.echo("=" * min(width, 80))

    # Show styled progress
    with click.progressbar(
        target or ["main"],
        label="Building targets",
        show_eta=True,
        show_percent=True,
    ) as bar:
        for t in bar:
            # Simulate work
            pass

    click.secho("Build complete!", fg="green", bold=True, blink=True)  # blink deprecated in 8.x


@build.command()
@click.option("--all", "clean_all", is_flag=True)
@click.option("--cache/--no-cache", default=True)
@click.pass_context
def clean(ctx: click.Context, clean_all: bool, cache: bool) -> None:
    """Clean build artifacts."""
    click.secho("Cleaning build directory...", fg="yellow")


# ==============================================================================
# TESTING UTILITIES (Using deprecated Click 7.x APIs)
# ==============================================================================


def test_cli_with_runner() -> None:
    """Test function demonstrating CliRunner usage with deprecated APIs."""
    runner = CliRunner(mix_stderr=False)  # mix_stderr deprecated in Click 8.x

    result = runner.invoke(cli, ["--help"])
    print(result.output)

    # Using deprecated output_bytes (Click 7.x)
    raw_bytes = result.output_bytes  # Should become result.output.encode() in 8.x

    # Using deprecated get_os_args (Click 7.x)
    os_args = click.get_os_args()
    print(f"OS args: {os_args}")


def get_version_info() -> str:
    """Get version info using deprecated Click 7.x API."""
    # click.__version__ access is deprecated in 8.x
    return f"Click version: {click.__version__}"


def display_styled_output() -> None:
    """Display styled output with deprecated blink parameter."""
    # blink parameter deprecated in Click 8.x
    text = click.style("Warning!", fg="red", blink=True)
    click.echo(text)

    # More styling
    click.secho("Success message", fg="green", bold=True)
    click.secho("Error message", fg="red", reverse=True)
    click.secho("Info message", fg="blue", underline=True)


# ==============================================================================
# STANDALONE MODE HANDLING
# ==============================================================================


@cli.command()
@click.option("--exit-code", type=int, default=0)
@click.pass_context
def standalone_test(ctx: click.Context, exit_code: int) -> None:
    """Test standalone mode behavior."""
    # Invoke with standalone_mode handling
    try:
        ctx.invoke(config_list, format="json")
    except SystemExit:
        click.echo("Command exited")

    if exit_code != 0:
        ctx.exit(exit_code)


# ==============================================================================
# ADDITIONAL COMMANDS TO REACH 25+ TOTAL
# ==============================================================================


@cli.command()
@click.option("--output", "-o", type=click.File("w"), default="-")
@click.option("--format", type=click.Choice(["json", "yaml", "toml"]), default="json")
@click.pass_context
def export(ctx: click.Context, output, format: str) -> None:
    """Export configuration."""
    click.echo(f"Exporting in {format} format")


@cli.command("import")
@click.option("--input", "input_file", type=click.File("r"), required=True)
@click.option("--merge/--replace", default=True)
@click.pass_context
def import_cmd(ctx: click.Context, input_file, merge: bool) -> None:
    """Import configuration."""
    action = "merging" if merge else "replacing"
    click.echo(f"Importing and {action}")


@cli.command()
@click.option("--service", autocompletion=complete_services)  # Click 7.x style
@click.option("--timeout", type=click.IntRange(1, 300), default=30)
@click.pass_context
def health(ctx: click.Context, service: str | None, timeout: int) -> None:
    """Check service health."""
    target = service or "all services"
    click.echo(f"Checking health of {target} (timeout: {timeout}s)")


@cli.command()
@click.argument("command", nargs=-1)
@click.option("--shell", type=click.Choice(["bash", "zsh", "fish"]), default="bash")
@click.pass_context
def exec(ctx: click.Context, command: tuple[str, ...], shell: str) -> None:
    """Execute a command in the environment."""
    if command:
        click.echo(f"Executing in {shell}: {' '.join(command)}")


@cli.command()
@click.option("--all", "show_all", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def info(ctx: click.Context, show_all: bool, as_json: bool) -> None:
    """Show system information."""
    # Get terminal size - deprecated in Click 8.x
    width, height = click.get_terminal_size()
    click.echo(f"Terminal: {width}x{height}")

    # Get version - deprecated access in Click 8.x
    click.echo(f"Click: {click.__version__}")


# ==============================================================================
# PLUGIN SYSTEM (Using deprecated MultiCommand)
# ==============================================================================


plugin_loader = DynamicPluginLoader(name="plugins", help="Plugin commands")
cli.add_command(plugin_loader)


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================


if __name__ == "__main__":
    cli()

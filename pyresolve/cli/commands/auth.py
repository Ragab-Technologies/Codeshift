"""Authentication commands for PyResolve CLI."""

import json
import os
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional, cast

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

console = Console()

# Config directory for storing credentials
CONFIG_DIR = Path.home() / ".config" / "pyresolve"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


def get_api_url() -> str:
    """Get the API URL from environment or default."""
    return os.environ.get("PYRESOLVE_API_URL", "https://api.pyresolve.dev")


def load_credentials() -> Optional[dict[str, Any]]:
    """Load saved credentials from disk."""
    if not CREDENTIALS_FILE.exists():
        return None
    try:
        return cast(dict[str, Any], json.loads(CREDENTIALS_FILE.read_text()))
    except (OSError, json.JSONDecodeError):
        return None


def save_credentials(credentials: dict) -> None:
    """Save credentials to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Set restrictive permissions
    CREDENTIALS_FILE.write_text(json.dumps(credentials, indent=2))
    os.chmod(CREDENTIALS_FILE, 0o600)


def delete_credentials() -> None:
    """Delete saved credentials."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()


def get_api_key() -> Optional[str]:
    """Get API key from environment or saved credentials."""
    # Check environment first
    api_key = os.environ.get("PYRESOLVE_API_KEY")
    if api_key:
        return api_key

    # Check saved credentials
    creds = load_credentials()
    if creds:
        return creds.get("api_key")

    return None


def make_authenticated_request(
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> httpx.Response:
    """Make an authenticated request to the API."""
    api_key = get_api_key()
    api_url = get_api_url()

    headers = kwargs.pop("headers", {})
    if api_key:
        headers["X-API-Key"] = api_key

    url = f"{api_url}{endpoint}"

    with httpx.Client(timeout=30) as client:
        response = client.request(method, url, headers=headers, **kwargs)

    return response


@click.command()
@click.option("--email", "-e", help="Email address for login")
@click.option("--password", "-p", help="Password for login", hide_input=True)
@click.option("--api-key", "-k", help="Use an existing API key")
@click.option("--device", "-d", is_flag=True, help="Use device code flow (for browsers)")
def login(
    email: Optional[str],
    password: Optional[str],
    api_key: Optional[str],
    device: bool,
) -> None:
    """Login to PyResolve to enable cloud features.

    \b
    Authentication methods:
    1. Email/password: pyresolve login -e user@example.com -p yourpassword
    2. API key: pyresolve login -k pyr_xxxxx
    3. Device flow: pyresolve login --device

    Your credentials are stored in ~/.config/pyresolve/credentials.json

    Don't have an account? Run: pyresolve register
    """
    # Check if already logged in
    existing = load_credentials()
    if existing:
        if not Confirm.ask("[yellow]You are already logged in. Do you want to re-authenticate?[/]"):
            return

    # Option 1: Use provided API key
    if api_key:
        _login_with_api_key(api_key)
        return

    # Option 2: Device code flow
    if device:
        _login_with_device_code()
        return

    # Option 3: Email/password
    if not email:
        email = Prompt.ask("Email")

    if not password:
        password = Prompt.ask("Password", password=True)

    _login_with_password(email, password)


@click.command()
@click.option("--email", "-e", help="Email address for registration")
@click.option("--password", "-p", help="Password (min 8 characters)", hide_input=True)
@click.option("--name", "-n", help="Your full name (optional)")
def register(
    email: Optional[str],
    password: Optional[str],
    name: Optional[str],
) -> None:
    """Create a new PyResolve account.

    \b
    Example:
      pyresolve register -e user@example.com -p yourpassword

    Your credentials are stored in ~/.config/pyresolve/credentials.json
    """
    # Check if already logged in
    existing = load_credentials()
    if existing:
        if not Confirm.ask(
            "[yellow]You are already logged in. Do you want to create a new account?[/]"
        ):
            return

    if not email:
        email = Prompt.ask("Email")

    if not password:
        password = Prompt.ask("Password (min 8 characters)", password=True)
        password_confirm = Prompt.ask("Confirm password", password=True)
        if password != password_confirm:
            console.print("[red]Passwords do not match[/]")
            raise SystemExit(1)

    if len(password) < 8:
        console.print("[red]Password must be at least 8 characters[/]")
        raise SystemExit(1)

    if not name:
        name = Prompt.ask("Full name (optional)", default="")

    _register_account(email, password, name if name else None)


def _register_account(email: str, password: str, full_name: Optional[str]) -> None:
    """Register a new account."""
    api_url = get_api_url()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating account...", total=None)

        try:
            payload = {"email": email, "password": password}
            if full_name:
                payload["full_name"] = full_name

            response = httpx.post(
                f"{api_url}/auth/register",
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()

                # Save credentials
                save_credentials(
                    {
                        "api_key": data["api_key"],
                        "user_id": data["user"]["id"],
                        "email": data["user"]["email"],
                        "tier": data["user"].get("tier", "free"),
                    }
                )

                progress.update(task, completed=True)

                console.print(
                    Panel(
                        f"[green]Account created successfully![/]\n\n"
                        f"Email: [cyan]{data['user']['email']}[/]\n"
                        f"Tier: [cyan]{data['user'].get('tier', 'free')}[/]\n\n"
                        f"[dim]You are now logged in and ready to use PyResolve.[/]",
                        title="Registration Successful",
                    )
                )
            elif response.status_code == 409:
                console.print(
                    "[red]An account with this email already exists.[/]\n"
                    "Run [cyan]pyresolve login[/] to sign in."
                )
                raise SystemExit(1)
            elif response.status_code == 422:
                detail = response.json().get("detail", [])
                if isinstance(detail, list) and detail:
                    msg = detail[0].get("msg", "Invalid input")
                else:
                    msg = str(detail)
                console.print(f"[red]Validation error: {msg}[/]")
                raise SystemExit(1)
            else:
                console.print(f"[red]Registration failed: {response.text}[/]")
                raise SystemExit(1)
        except httpx.RequestError as e:
            console.print(f"[red]Connection error: {e}[/]")
            raise SystemExit(1) from e


def _login_with_api_key(api_key: str) -> None:
    """Authenticate with an API key."""
    api_url = get_api_url()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Verifying API key...", total=None)

        try:
            response = httpx.get(
                f"{api_url}/auth/me",
                headers={"X-API-Key": api_key},
                timeout=30,
            )

            if response.status_code == 200:
                user = response.json()

                # Save credentials
                save_credentials(
                    {
                        "api_key": api_key,
                        "user_id": user.get("id"),
                        "email": user.get("email"),
                        "tier": user.get("tier", "free"),
                    }
                )

                progress.update(task, completed=True)

                console.print(
                    Panel(
                        f"[green]Successfully logged in![/]\n\n"
                        f"Email: [cyan]{user.get('email')}[/]\n"
                        f"Tier: [cyan]{user.get('tier', 'free')}[/]",
                        title="Login Successful",
                    )
                )
            elif response.status_code == 401:
                console.print("[red]Invalid API key[/]")
                raise SystemExit(1)
            else:
                console.print(f"[red]Login failed: {response.text}[/]")
                raise SystemExit(1)
        except httpx.RequestError as e:
            console.print(f"[red]Connection error: {e}[/]")
            raise SystemExit(1) from e


def _login_with_password(email: str, password: str) -> None:
    """Authenticate with email and password."""
    api_url = get_api_url()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Authenticating...", total=None)

        try:
            response = httpx.post(
                f"{api_url}/auth/login",
                json={"email": email, "password": password},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()

                # Save credentials
                save_credentials(
                    {
                        "api_key": data["api_key"],
                        "user_id": data["user"]["id"],
                        "email": data["user"]["email"],
                        "tier": data["user"].get("tier", "free"),
                    }
                )

                progress.update(task, completed=True)

                console.print(
                    Panel(
                        f"[green]Successfully logged in![/]\n\n"
                        f"Email: [cyan]{data['user']['email']}[/]\n"
                        f"Tier: [cyan]{data['user'].get('tier', 'free')}[/]",
                        title="Login Successful",
                    )
                )
            elif response.status_code == 401:
                console.print("[red]Invalid email or password[/]")
                raise SystemExit(1)
            else:
                console.print(f"[red]Login failed: {response.text}[/]")
                raise SystemExit(1)
        except httpx.RequestError as e:
            console.print(f"[red]Connection error: {e}[/]")
            raise SystemExit(1) from e


def _login_with_device_code() -> None:
    """Authenticate using device code flow."""
    api_url = get_api_url()

    try:
        # Request device code
        response = httpx.post(
            f"{api_url}/auth/device/code",
            json={"client_id": "pyresolve-cli"},
            timeout=30,
        )

        if response.status_code != 200:
            console.print(f"[red]Failed to initiate device flow: {response.text}[/]")
            raise SystemExit(1)

        data = response.json()
        device_code = data["device_code"]
        user_code = data["user_code"]
        verification_uri = data["verification_uri"]
        expires_in = data.get("expires_in", 900)
        interval = data.get("interval", 5)

        # Show code to user
        console.print(
            Panel(
                f"[bold]To authenticate, visit:[/]\n\n"
                f"  [cyan]{verification_uri}[/]\n\n"
                f"[bold]And enter this code:[/]\n\n"
                f"  [green bold]{user_code}[/]\n\n"
                f"[dim]This code expires in {expires_in // 60} minutes.[/]",
                title="Device Authentication",
            )
        )

        # Try to open browser
        if Confirm.ask("Open browser?", default=True):
            webbrowser.open(verification_uri)

        # Poll for completion
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Waiting for authentication...", total=None)

            start_time = time.time()
            while time.time() - start_time < expires_in:
                time.sleep(interval)

                try:
                    response = httpx.post(
                        f"{api_url}/auth/device/token",
                        json={
                            "device_code": device_code,
                            "client_id": "pyresolve-cli",
                        },
                        timeout=30,
                    )

                    if response.status_code == 200:
                        data = response.json()

                        # Save credentials
                        save_credentials(
                            {
                                "api_key": data["api_key"],
                                "user_id": data["user"]["id"],
                                "email": data["user"]["email"],
                                "tier": data["user"].get("tier", "free"),
                            }
                        )

                        progress.update(task, completed=True)

                        console.print(
                            Panel(
                                f"[green]Successfully logged in![/]\n\n"
                                f"Email: [cyan]{data['user']['email']}[/]\n"
                                f"Tier: [cyan]{data['user'].get('tier', 'free')}[/]",
                                title="Login Successful",
                            )
                        )
                        return
                    elif response.status_code == 428:
                        # Authorization pending, continue polling
                        continue
                    elif response.status_code == 403:
                        console.print("[red]Authorization denied[/]")
                        raise SystemExit(1)
                    else:
                        console.print(f"[red]Authentication failed: {response.text}[/]")
                        raise SystemExit(1)
                except httpx.RequestError:
                    # Network error, retry
                    continue

            console.print("[red]Device code expired. Please try again.[/]")
            raise SystemExit(1)

    except httpx.RequestError as e:
        console.print(f"[red]Connection error: {e}[/]")
        raise SystemExit(1) from e


@click.command()
def logout() -> None:
    """Logout from PyResolve and remove saved credentials."""
    creds = load_credentials()

    if not creds:
        console.print("[yellow]Not logged in[/]")
        return

    # Revoke the API key on the server
    api_key = creds.get("api_key")
    if api_key:
        try:
            api_url = get_api_url()
            httpx.post(
                f"{api_url}/auth/logout",
                headers={"X-API-Key": api_key},
                timeout=30,
            )
            # Ignore errors - just try to revoke
        except httpx.RequestError:
            pass

    # Delete local credentials
    delete_credentials()

    console.print("[green]Successfully logged out[/]")


@click.command()
def whoami() -> None:
    """Show current authentication status and user info."""
    creds = load_credentials()

    if not creds:
        console.print(
            Panel(
                "[yellow]Not logged in[/]\n\n" "Run [cyan]pyresolve login[/] to authenticate.",
                title="Authentication Status",
            )
        )
        return

    # Try to get fresh user info from API
    api_key = creds.get("api_key")
    if api_key:
        try:
            api_url = get_api_url()
            response = httpx.get(
                f"{api_url}/auth/me",
                headers={"X-API-Key": api_key},
                timeout=30,
            )

            if response.status_code == 200:
                user = response.json()

                # Update cached credentials
                creds["email"] = user.get("email")
                creds["tier"] = user.get("tier", "free")
                creds["user_id"] = user.get("id")
                save_credentials(creds)

                console.print(
                    Panel(
                        f"[green]Logged in[/]\n\n"
                        f"Email: [cyan]{user.get('email')}[/]\n"
                        f"Tier: [cyan]{user.get('tier', 'free')}[/]\n"
                        f"User ID: [dim]{user.get('id')}[/]",
                        title="Authentication Status",
                    )
                )
                return
        except httpx.RequestError:
            pass

    # Fall back to cached info
    console.print(
        Panel(
            f"[green]Logged in[/] [dim](cached)[/]\n\n"
            f"Email: [cyan]{creds.get('email', 'unknown')}[/]\n"
            f"Tier: [cyan]{creds.get('tier', 'free')}[/]",
            title="Authentication Status",
        )
    )


@click.command()
def quota() -> None:
    """Show current usage quota and limits."""
    api_key = get_api_key()

    if not api_key:
        console.print(
            Panel(
                "[yellow]Not logged in[/]\n\n"
                "Run [cyan]pyresolve login[/] to authenticate and view quota.\n\n"
                "[dim]Free tier limits apply for unauthenticated usage.[/]",
                title="Usage Quota",
            )
        )
        return

    try:
        api_url = get_api_url()
        response = httpx.get(
            f"{api_url}/usage/quota",
            headers={"X-API-Key": api_key},
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()

            # Build progress bars
            files_bar = _progress_bar(
                data["files_migrated"],
                data["files_limit"],
                data["files_percentage"],
            )
            llm_bar = _progress_bar(
                data["llm_calls"],
                data["llm_calls_limit"],
                data["llm_calls_percentage"],
            )

            table = Table(show_header=True, header_style="bold")
            table.add_column("Resource")
            table.add_column("Used")
            table.add_column("Limit")
            table.add_column("Progress", width=20)

            table.add_row(
                "File Migrations",
                str(data["files_migrated"]),
                str(data["files_limit"]),
                files_bar,
            )
            table.add_row(
                "LLM Calls",
                str(data["llm_calls"]),
                str(data["llm_calls_limit"]),
                llm_bar,
            )

            console.print(
                Panel(
                    table,
                    title=f"Usage Quota - {data['tier'].title()} Tier ({data['billing_period']})",
                )
            )

            # Show upgrade prompt if near limit
            if data["files_percentage"] > 80 or data["llm_calls_percentage"] > 80:
                if data["tier"] == "free":
                    console.print(
                        "\n[yellow]Running low on quota?[/] "
                        "Run [cyan]pyresolve upgrade-plan[/] to see upgrade options."
                    )
        elif response.status_code == 401:
            console.print("[red]Invalid credentials. Please run [cyan]pyresolve login[/] again.[/]")
            raise SystemExit(1)
        else:
            console.print(f"[red]Failed to get quota: {response.text}[/]")
            raise SystemExit(1)

    except httpx.RequestError as e:
        console.print(f"[red]Connection error: {e}[/]")
        # Show offline fallback
        creds = load_credentials()
        if creds:
            console.print("\n[dim]Showing cached information:[/]")
            console.print(f"  Tier: [cyan]{creds.get('tier', 'free')}[/]")


def _progress_bar(current: int, total: int, percentage: float) -> str:
    """Generate a text-based progress bar."""
    width = 15
    filled = int(width * percentage / 100)
    empty = width - filled

    if percentage >= 90:
        color = "red"
    elif percentage >= 70:
        color = "yellow"
    else:
        color = "green"

    bar = f"[{color}]{'█' * filled}{'░' * empty}[/] {percentage:.0f}%"
    return bar


@click.command("upgrade-plan")
@click.option("--tier", "-t", type=click.Choice(["pro", "unlimited"]), help="Tier to upgrade to")
def upgrade_plan(tier: Optional[str]) -> None:
    """Show available plans or upgrade to a paid tier.

    \b
    Examples:
      pyresolve upgrade-plan              # Show all plans
      pyresolve upgrade-plan --tier pro   # Upgrade to Pro tier
    """
    api_key = get_api_key()
    api_url = get_api_url()

    # If tier specified and logged in, initiate checkout
    if tier and api_key:
        _initiate_upgrade(api_url, api_key, tier)
        return

    # Otherwise show available tiers
    try:
        response = httpx.get(f"{api_url}/billing/tiers", timeout=30)

        if response.status_code == 200:
            tiers_data = response.json()

            console.print("\n[bold]Available Plans[/]\n")

            for t in tiers_data:
                if t["name"] == "enterprise":
                    price = "Custom"
                elif t["price_monthly"] == 0:
                    price = "Free"
                else:
                    price = f"${t['price_monthly'] / 100:.0f}/mo"

                console.print(f"[bold cyan]{t['display_name']}[/] - {price}")
                console.print(f"  Files: {t['files_per_month']:,}/mo")
                console.print(f"  LLM Calls: {t['llm_calls_per_month']:,}/mo")
                for feature in t["features"]:
                    console.print(f"  • {feature}")
                console.print()

            if api_key:
                console.print(
                    "[green]To upgrade, run:[/]\n"
                    "  [cyan]pyresolve upgrade-plan --tier pro[/]\n"
                    "  [cyan]pyresolve upgrade-plan --tier unlimited[/]"
                )
            else:
                console.print(
                    "[yellow]Login first to upgrade:[/]\n"
                    "  [cyan]pyresolve login[/]"
                )
        else:
            console.print("[red]Failed to load pricing information[/]")

    except httpx.RequestError as e:
        console.print(f"[red]Connection error: {e}[/]")


def _initiate_upgrade(api_url: str, api_key: str, tier: str) -> None:
    """Create checkout session and open in browser."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating checkout session...", total=None)

        try:
            response = httpx.post(
                f"{api_url}/billing/checkout",
                headers={"X-API-Key": api_key},
                json={
                    "tier": tier,
                    "success_url": "https://pyresolve.dev/upgrade/success",
                    "cancel_url": "https://pyresolve.dev/upgrade/cancel",
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                checkout_url = data["checkout_url"]

                progress.update(task, completed=True)

                console.print(
                    Panel(
                        f"[green]Opening checkout in your browser...[/]\n\n"
                        f"Upgrading to: [cyan]{tier.title()}[/]\n\n"
                        f"[dim]If the browser doesn't open, visit:[/]\n"
                        f"[link={checkout_url}]{checkout_url[:60]}...[/]",
                        title="Checkout",
                    )
                )

                # Open browser
                webbrowser.open(checkout_url)

                console.print(
                    "\n[dim]After completing payment, your account will be "
                    "automatically upgraded.[/]\n"
                    "[dim]Run [cyan]pyresolve whoami[/] to verify your new tier.[/]"
                )
            elif response.status_code == 401:
                console.print("[red]Session expired. Please run [cyan]pyresolve login[/] again.[/]")
                raise SystemExit(1)
            elif response.status_code == 500:
                detail = response.json().get("detail", "Unknown error")
                if "not configured" in detail.lower():
                    console.print(
                        "[yellow]Stripe payments are not yet configured.[/]\n"
                        "Please visit [cyan]https://pyresolve.dev/pricing[/] to upgrade."
                    )
                else:
                    console.print(f"[red]Checkout failed: {detail}[/]")
                raise SystemExit(1)
            else:
                console.print(f"[red]Failed to create checkout: {response.text}[/]")
                raise SystemExit(1)

        except httpx.RequestError as e:
            console.print(f"[red]Connection error: {e}[/]")
            raise SystemExit(1) from e


@click.command("billing")
def billing() -> None:
    """Open Stripe billing portal to manage your subscription."""
    api_key = get_api_key()

    if not api_key:
        console.print(
            "[yellow]Not logged in.[/]\n"
            "Run [cyan]pyresolve login[/] to authenticate first."
        )
        raise SystemExit(1)

    api_url = get_api_url()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Opening billing portal...", total=None)

        try:
            response = httpx.get(
                f"{api_url}/billing/portal",
                headers={"X-API-Key": api_key},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                portal_url = data["portal_url"]

                progress.update(task, completed=True)

                console.print(
                    Panel(
                        "[green]Opening billing portal in your browser...[/]\n\n"
                        "You can:\n"
                        "  • Update payment method\n"
                        "  • View invoices\n"
                        "  • Change or cancel subscription",
                        title="Billing Portal",
                    )
                )

                webbrowser.open(portal_url)
            elif response.status_code == 400:
                console.print(
                    "[yellow]No billing account found.[/]\n"
                    "Run [cyan]pyresolve upgrade-plan --tier pro[/] to subscribe first."
                )
            elif response.status_code == 401:
                console.print("[red]Session expired. Please run [cyan]pyresolve login[/] again.[/]")
                raise SystemExit(1)
            else:
                console.print(f"[red]Failed to open billing portal: {response.text}[/]")
                raise SystemExit(1)

        except httpx.RequestError as e:
            console.print(f"[red]Connection error: {e}[/]")
            raise SystemExit(1) from e

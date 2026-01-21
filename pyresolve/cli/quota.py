"""Quota checking and usage logging utilities for CLI commands."""

from typing import Optional, cast

import httpx
from rich.console import Console
from rich.panel import Panel

from pyresolve.cli.commands.auth import get_api_key, get_api_url, load_credentials

console = Console()


class QuotaError(Exception):
    """Exception raised when quota is exceeded."""

    def __init__(self, message: str, current: int, limit: int, remaining: int):
        super().__init__(message)
        self.current = current
        self.limit = limit
        self.remaining = remaining


def check_quota(
    event_type: str,
    quantity: int = 1,
    allow_offline: bool = True,
) -> bool:
    """Check if the user has quota for an operation.

    Args:
        event_type: Type of event ('file_migrated', 'llm_call', 'scan', 'apply')
        quantity: Number of events to check
        allow_offline: If True, allow operation when offline (default True)

    Returns:
        True if operation is allowed, raises QuotaError otherwise

    Raises:
        QuotaError: If quota would be exceeded
    """
    api_key = get_api_key()

    # If no API key, use default free tier limits (offline mode)
    if not api_key:
        if allow_offline:
            # No quota enforcement without authentication
            return True
        else:
            console.print(
                Panel(
                    "[yellow]Authentication required for this operation.[/]\n\n"
                    "Run [cyan]pyresolve login[/] to authenticate.",
                    title="Authentication Required",
                )
            )
            raise SystemExit(1)

    try:
        api_url = get_api_url()
        response = httpx.post(
            f"{api_url}/usage/check",
            headers={"X-API-Key": api_key},
            json={"event_type": event_type, "quantity": quantity},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()

            if not data["allowed"]:
                raise QuotaError(
                    data.get("message", "Quota exceeded"),
                    data["current_usage"],
                    data["limit"],
                    data["remaining"],
                )

            return True

        elif response.status_code == 401:
            # Invalid credentials
            console.print(
                "[yellow]Invalid credentials. Run [cyan]pyresolve login[/] to re-authenticate.[/]"
            )
            if allow_offline:
                return True
            raise SystemExit(1)

        else:
            # API error, allow operation in offline mode
            if allow_offline:
                return True
            raise SystemExit(1)

    except httpx.RequestError:
        # Network error, allow operation in offline mode
        if allow_offline:
            return True
        console.print("[yellow]Cannot connect to API. Working in offline mode.[/]")
        return True


def record_usage(
    event_type: str,
    library: Optional[str] = None,
    quantity: int = 1,
    metadata: Optional[dict] = None,
) -> bool:
    """Record a usage event after an operation completes.

    Args:
        event_type: Type of event ('file_migrated', 'llm_call', 'scan', 'apply')
        library: Library being migrated (optional)
        quantity: Number of events
        metadata: Additional metadata (optional)

    Returns:
        True if recording succeeded, False otherwise
    """
    api_key = get_api_key()

    if not api_key:
        # Can't record without authentication
        return False

    try:
        api_url = get_api_url()
        response = httpx.post(
            f"{api_url}/usage/",
            headers={"X-API-Key": api_key},
            json={
                "event_type": event_type,
                "library": library,
                "quantity": quantity,
                "metadata": metadata or {},
            },
            timeout=10,
        )

        return response.status_code == 200

    except httpx.RequestError:
        # Network error, don't fail the operation
        return False


def show_quota_exceeded_message(error: QuotaError) -> None:
    """Display a helpful message when quota is exceeded."""
    creds = load_credentials()
    tier = creds.get("tier", "free") if creds else "free"

    console.print(
        Panel(
            f"[red]Quota exceeded![/]\n\n"
            f"You have used [cyan]{error.current}[/] of your [cyan]{error.limit}[/] "
            f"monthly allowance.\n\n"
            f"Current tier: [cyan]{tier.title()}[/]\n\n"
            "Options:\n"
            "  • Upgrade your plan: [cyan]pyresolve upgrade-plan[/]\n"
            "  • Wait until next billing period\n"
            "  • Contact support for enterprise options",
            title="Quota Exceeded",
        )
    )


def get_remaining_quota(event_type: str) -> Optional[int]:
    """Get remaining quota for an event type.

    Returns:
        Number of remaining events, or None if offline/unauthenticated
    """
    api_key = get_api_key()

    if not api_key:
        return None

    try:
        api_url = get_api_url()
        response = httpx.get(
            f"{api_url}/usage/quota",
            headers={"X-API-Key": api_key},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()

            if event_type == "file_migrated":
                return cast(int, data.get("files_remaining", 0))
            elif event_type == "llm_call":
                return cast(int, data.get("llm_calls_remaining", 0))
            else:
                return None

    except httpx.RequestError:
        pass

    return None


def is_tier1_migration(library: str) -> bool:
    """Check if this is a Tier 1 (free) migration.

    Tier 1 libraries have AST-based transforms and don't require LLM calls.
    """
    from pyresolve.knowledge import is_tier_1_library

    return is_tier_1_library(library)

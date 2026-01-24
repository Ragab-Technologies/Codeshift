"""Supabase database client and operations."""

from datetime import datetime, timezone
from typing import Any, Optional, cast

from pyresolve.api.config import get_settings
from supabase import Client as SupabaseClient
from supabase import create_client


def get_supabase_client() -> "SupabaseClient":
    """Get a Supabase client instance."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


def get_supabase_anon_client() -> "SupabaseClient":
    """Get a Supabase client with anon key (for user-facing operations)."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError("Supabase not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY.")
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )


class Database:
    """Database operations wrapper."""

    def __init__(self, client: Optional["SupabaseClient"] = None):
        """Initialize with optional client, otherwise use service role client."""
        self._client = client

    @property
    def client(self) -> "SupabaseClient":
        """Get or create the Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    # Profile operations
    def get_profile_by_id(self, user_id: str) -> dict | None:
        """Get a user profile by ID."""
        result = self.client.table("profiles").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None

    def get_profile_by_email(self, email: str) -> dict | None:
        """Get a user profile by email."""
        result = self.client.table("profiles").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None

    def update_profile(self, user_id: str, data: dict) -> dict | None:
        """Update a user profile."""
        result = self.client.table("profiles").update(data).eq("id", user_id).execute()
        return result.data[0] if result.data else None

    def update_profile_tier(
        self, user_id: str, tier: str, stripe_customer_id: str | None = None
    ) -> dict | None:
        """Update a user's tier and optionally their Stripe customer ID."""
        data = {"tier": tier, "updated_at": datetime.now(timezone.utc).isoformat()}
        if stripe_customer_id:
            data["stripe_customer_id"] = stripe_customer_id
        return self.update_profile(user_id, data)

    # API key operations
    def get_api_key_by_hash(self, key_hash: str) -> dict | None:
        """Get an API key by its hash."""
        result = (
            self.client.table("api_keys")
            .select("*, profiles(*)")
            .eq("key_hash", key_hash)
            .eq("revoked", False)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_api_key_by_prefix(self, key_prefix: str) -> dict | None:
        """Get an API key by its prefix."""
        result = (
            self.client.table("api_keys")
            .select("*, profiles(*)")
            .eq("key_prefix", key_prefix)
            .eq("revoked", False)
            .execute()
        )
        return result.data[0] if result.data else None

    def create_api_key(
        self,
        user_id: str,
        key_prefix: str,
        key_hash: str,
        name: str = "CLI Key",
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new API key."""
        data = {
            "user_id": user_id,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "name": name,
            "scopes": scopes or ["read", "write"],
        }
        result = self.client.table("api_keys").insert(data).execute()
        return cast(dict[str, Any], result.data[0])

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key."""
        result = (
            self.client.table("api_keys")
            .update({"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", key_id)
            .execute()
        )
        return bool(result.data)

    def update_api_key_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for an API key."""
        self.client.table("api_keys").update(
            {"last_used_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", key_id).execute()

    # Usage event operations
    def record_usage_event(
        self,
        user_id: str,
        event_type: str,
        library: str | None = None,
        quantity: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a usage event."""
        now = datetime.now(timezone.utc)
        data = {
            "user_id": user_id,
            "event_type": event_type,
            "library": library,
            "quantity": quantity,
            "metadata": metadata or {},
            "billing_period": now.strftime("%Y-%m"),
            "created_at": now.isoformat(),
        }
        result = self.client.table("usage_events").insert(data).execute()
        return cast(dict[str, Any], result.data[0])

    def get_usage_for_period(
        self, user_id: str, billing_period: str | None = None
    ) -> dict[str, int]:
        """Get usage summary for a billing period."""
        if billing_period is None:
            billing_period = datetime.now(timezone.utc).strftime("%Y-%m")

        result = (
            self.client.table("usage_events")
            .select("event_type, quantity")
            .eq("user_id", user_id)
            .eq("billing_period", billing_period)
            .execute()
        )

        # Aggregate by event type
        usage: dict[str, int] = {}
        for event in result.data:
            event_type = event["event_type"]
            usage[event_type] = usage.get(event_type, 0) + event["quantity"]

        return usage

    def get_usage_events(
        self,
        user_id: str,
        billing_period: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get detailed usage events."""
        if billing_period is None:
            billing_period = datetime.now(timezone.utc).strftime("%Y-%m")

        query = (
            self.client.table("usage_events")
            .select("*")
            .eq("user_id", user_id)
            .eq("billing_period", billing_period)
        )

        if event_type:
            query = query.eq("event_type", event_type)

        result = query.order("created_at", desc=True).limit(limit).execute()
        return cast(list[dict[str, Any]], result.data)

    def get_user_quota(self, user_id: str) -> dict[str, int] | None:
        """Get quota information for a user.

        Returns:
            Dict with llm_calls and file_migrated counts, or None if error.
        """
        billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
        return self.get_usage_for_period(user_id, billing_period)


# Singleton instance
_db: Database | None = None


def get_database() -> Database:
    """Get the database singleton."""
    global _db
    if _db is None:
        _db = Database()
    return _db

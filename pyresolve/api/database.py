"""Supabase database client and operations."""

from datetime import datetime, timezone
from typing import Optional

from supabase import Client, create_client

from pyresolve.api.config import get_settings


def get_supabase_client() -> Client:
    """Get a Supabase client instance."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


def get_supabase_anon_client() -> Client:
    """Get a Supabase client with anon key (for user-facing operations)."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key,
    )


class Database:
    """Database operations wrapper."""

    def __init__(self, client: Optional[Client] = None):
        """Initialize with optional client, otherwise use service role client."""
        self._client = client

    @property
    def client(self) -> Client:
        """Get or create the Supabase client."""
        if self._client is None:
            self._client = get_supabase_client()
        return self._client

    # Profile operations
    def get_profile_by_id(self, user_id: str) -> Optional[dict]:
        """Get a user profile by ID."""
        result = self.client.table("profiles").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None

    def get_profile_by_email(self, email: str) -> Optional[dict]:
        """Get a user profile by email."""
        result = self.client.table("profiles").select("*").eq("email", email).execute()
        return result.data[0] if result.data else None

    def update_profile(self, user_id: str, data: dict) -> Optional[dict]:
        """Update a user profile."""
        result = self.client.table("profiles").update(data).eq("id", user_id).execute()
        return result.data[0] if result.data else None

    def update_profile_tier(
        self, user_id: str, tier: str, stripe_customer_id: Optional[str] = None
    ) -> Optional[dict]:
        """Update a user's tier and optionally their Stripe customer ID."""
        data = {"tier": tier, "updated_at": datetime.now(timezone.utc).isoformat()}
        if stripe_customer_id:
            data["stripe_customer_id"] = stripe_customer_id
        return self.update_profile(user_id, data)

    # API key operations
    def get_api_key_by_hash(self, key_hash: str) -> Optional[dict]:
        """Get an API key by its hash."""
        result = (
            self.client.table("api_keys")
            .select("*, profiles(*)")
            .eq("key_hash", key_hash)
            .eq("revoked", False)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_api_key_by_prefix(self, key_prefix: str) -> Optional[dict]:
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
        scopes: Optional[list[str]] = None,
    ) -> dict:
        """Create a new API key."""
        data = {
            "user_id": user_id,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
            "name": name,
            "scopes": scopes or ["read", "write"],
        }
        result = self.client.table("api_keys").insert(data).execute()
        return result.data[0]

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
        library: Optional[str] = None,
        quantity: int = 1,
        metadata: Optional[dict] = None,
    ) -> dict:
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
        return result.data[0]

    def get_usage_for_period(
        self, user_id: str, billing_period: Optional[str] = None
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
        billing_period: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
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
        return result.data


# Singleton instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get the database singleton."""
    global _db
    if _db is None:
        _db = Database()
    return _db

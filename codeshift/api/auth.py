"""Authentication utilities and dependencies for the PyResolve API."""

import hashlib
import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from codeshift.api.config import get_settings
from codeshift.api.database import get_database

# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        Tuple of (full_key, key_prefix, key_hash)
    """
    settings = get_settings()

    # Generate 32 random bytes (256 bits of entropy)
    key_suffix = secrets.token_urlsafe(32)

    # Create the full key with prefix
    full_key = f"{settings.api_key_prefix}{key_suffix}"

    # Get prefix for identification (first 12 chars including prefix)
    key_prefix = full_key[:12]

    # Hash the full key for storage
    key_hash = hash_api_key(full_key)

    return full_key, key_prefix, key_hash


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(api_key.encode()).hexdigest()


class AuthenticatedUser:
    """Authenticated user context."""

    def __init__(
        self,
        user_id: str,
        email: str,
        tier: str,
        api_key_id: str | None = None,
        scopes: list[str] | None = None,
    ):
        self.user_id = user_id
        self.email = email
        self.tier = tier
        self.api_key_id = api_key_id
        self.scopes = scopes or []

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope."""
        return scope in self.scopes or "admin" in self.scopes


async def get_current_user(
    api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> AuthenticatedUser:
    """Validate API key and return the authenticated user.

    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Hash the provided key
    key_hash = hash_api_key(api_key)

    # Look up the key in the database
    db = get_database()
    api_key_record = db.get_api_key_by_hash(key_hash)

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Check if key is expired
    if api_key_record.get("expires_at"):
        from datetime import datetime, timezone

        expires_at = api_key_record["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired",
                headers={"WWW-Authenticate": "ApiKey"},
            )

    # Update last used timestamp
    db.update_api_key_last_used(api_key_record["id"])

    # Get profile data
    profile = api_key_record.get("profiles", {})

    return AuthenticatedUser(
        user_id=api_key_record["user_id"],
        email=profile.get("email", ""),
        tier=profile.get("tier", "free"),
        api_key_id=api_key_record["id"],
        scopes=api_key_record.get("scopes", []),
    )


async def get_optional_user(
    api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> AuthenticatedUser | None:
    """Get the current user if authenticated, otherwise return None.

    This is useful for endpoints that work both authenticated and unauthenticated.
    """
    if not api_key:
        return None

    try:
        return await get_current_user(api_key)
    except HTTPException:
        return None


def require_scope(scope: str) -> Callable[..., Awaitable[AuthenticatedUser]]:
    """Dependency that requires a specific scope."""

    async def check_scope(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        if not user.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' required",
            )
        return user

    return check_scope


def require_tier(minimum_tier: str) -> Callable[..., Awaitable[AuthenticatedUser]]:
    """Dependency that requires a minimum tier."""
    tier_levels = {"free": 0, "pro": 1, "unlimited": 2, "enterprise": 3}

    async def check_tier(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> AuthenticatedUser:
        user_level = tier_levels.get(user.tier, 0)
        required_level = tier_levels.get(minimum_tier, 0)

        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {minimum_tier} tier or higher",
            )
        return user

    return check_tier


# Type aliases for dependency injection
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]
OptionalUser = Annotated[AuthenticatedUser | None, Depends(get_optional_user)]
ProUser = Annotated[AuthenticatedUser, Depends(require_tier("pro"))]
UnlimitedUser = Annotated[AuthenticatedUser, Depends(require_tier("unlimited"))]

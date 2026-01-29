"""Rate limiting middleware for DoS protection.

This module provides rate limiting functionality using slowapi to protect
against denial-of-service attacks on the API endpoints.
"""

from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


class RateLimitConfig:
    """Configuration for rate limiting across different endpoints.

    Rate limits are expressed as "X/period" where period can be:
    - second, minute, hour, day
    - Examples: "30/minute", "100/hour", "1000/day"
    """

    # Migration endpoints - computationally expensive
    MIGRATE_CODE_LIMIT: str = "30/minute"
    MIGRATE_BATCH_LIMIT: str = "10/minute"

    # Authentication endpoints - prevent brute force
    AUTH_LOGIN_LIMIT: str = "10/minute"
    AUTH_REGISTER_LIMIT: str = "5/minute"
    AUTH_REFRESH_LIMIT: str = "30/minute"

    # Usage/billing endpoints - moderate limits
    USAGE_CHECK_LIMIT: str = "60/minute"
    BILLING_LIMIT: str = "30/minute"

    # Health check - high limit for monitoring
    HEALTH_LIMIT: str = "120/minute"

    # Default limit for unspecified endpoints
    DEFAULT_LIMIT: str = "60/minute"


# Singleton limiter instance
_limiter: Optional[Limiter] = None


def get_api_key_or_ip(request: Request) -> str:
    """Extract rate limit key from request.

    Uses API key if present in headers, otherwise falls back to client IP.
    This ensures authenticated users are tracked by their API key while
    unauthenticated requests are tracked by IP address.

    Args:
        request: The incoming FastAPI request object.

    Returns:
        A string identifier for rate limiting (API key or IP address).
    """
    # Check for API key in header (standard header used by codeshift-cli)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use a prefix to distinguish API key limits from IP limits
        return f"apikey:{api_key}"

    # Fall back to client IP address
    # Check for forwarded IP (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        client_ip = forwarded_for.split(",")[0].strip()
        return f"ip:{client_ip}"

    # Use direct client IP
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


def get_rate_limiter() -> Limiter:
    """Get or create the singleton rate limiter instance.

    Returns:
        The configured Limiter instance for use with slowapi.
    """
    global _limiter
    if _limiter is None:
        _limiter = Limiter(
            key_func=get_api_key_or_ip,
            default_limits=[RateLimitConfig.DEFAULT_LIMIT],
            # Use in-memory storage by default
            # For production with multiple workers, use Redis:
            # storage_uri="redis://localhost:6379"
        )
    return _limiter


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded exceptions.

    Returns a JSON response with status 429 (Too Many Requests) and
    includes helpful information about the rate limit.

    Args:
        request: The incoming request that exceeded the limit.
        exc: The RateLimitExceeded exception with limit details.

    Returns:
        JSONResponse with 429 status and error details.
    """
    # Extract rate limit info from exception
    limit_value = str(exc.detail) if exc.detail else "Rate limit exceeded"

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Too many requests. {limit_value}",
            "detail": "Please wait before making more requests.",
            "retry_after": _get_retry_after(exc),
        },
        headers={
            "Retry-After": str(_get_retry_after(exc)),
            "X-RateLimit-Limit": limit_value,
        },
    )


def _get_retry_after(exc: RateLimitExceeded) -> int:
    """Calculate retry-after seconds from rate limit exception.

    Args:
        exc: The RateLimitExceeded exception.

    Returns:
        Number of seconds to wait before retrying.
    """
    # Default retry-after based on common rate limit windows
    # slowapi doesn't provide exact reset time, so we estimate
    detail = str(exc.detail).lower() if exc.detail else ""

    if "second" in detail:
        return 1
    elif "minute" in detail:
        return 60
    elif "hour" in detail:
        return 3600
    elif "day" in detail:
        return 86400

    # Default to 60 seconds
    return 60

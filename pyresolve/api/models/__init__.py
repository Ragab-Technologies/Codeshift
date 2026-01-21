"""Pydantic models for the PyResolve API."""

from pyresolve.api.models.auth import (
    APIKey,
    APIKeyCreate,
    APIKeyResponse,
    TokenResponse,
    UserInfo,
)
from pyresolve.api.models.billing import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PortalSessionResponse,
    SubscriptionInfo,
    TierInfo,
)
from pyresolve.api.models.migrate import (
    ExplainChangeRequest,
    ExplainChangeResponse,
    MigrateCodeRequest,
    MigrateCodeResponse,
)
from pyresolve.api.models.usage import (
    QuotaInfo,
    UsageEvent,
    UsageEventCreate,
    UsageResponse,
    UsageSummary,
)

__all__ = [
    # Auth models
    "APIKey",
    "APIKeyCreate",
    "APIKeyResponse",
    "TokenResponse",
    "UserInfo",
    # Billing models
    "CheckoutSessionRequest",
    "CheckoutSessionResponse",
    "PortalSessionResponse",
    "SubscriptionInfo",
    "TierInfo",
    # Migrate models
    "ExplainChangeRequest",
    "ExplainChangeResponse",
    "MigrateCodeRequest",
    "MigrateCodeResponse",
    # Usage models
    "QuotaInfo",
    "UsageEvent",
    "UsageEventCreate",
    "UsageResponse",
    "UsageSummary",
]

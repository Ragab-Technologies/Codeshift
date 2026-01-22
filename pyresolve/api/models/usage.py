"""Usage tracking models for the PyResolve API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class UsageEventCreate(BaseModel):
    """Request to record a usage event."""

    event_type: str = Field(..., pattern="^(file_migrated|llm_call|scan|apply)$")
    library: Optional[str] = None
    quantity: int = Field(default=1, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageEvent(BaseModel):
    """A recorded usage event."""

    id: str
    user_id: str
    event_type: str
    library: Optional[str] = None
    quantity: int
    metadata: dict[str, Any]
    billing_period: str
    created_at: datetime

    class Config:
        from_attributes = True


class UsageSummary(BaseModel):
    """Summary of usage for a billing period."""

    billing_period: str
    files_migrated: int = 0
    llm_calls: int = 0
    scans: int = 0
    applies: int = 0
    total_events: int = 0


class QuotaInfo(BaseModel):
    """Current quota information for a user."""

    tier: str
    billing_period: str

    # Current usage
    files_migrated: int = 0
    llm_calls: int = 0

    # Limits
    files_limit: int
    llm_calls_limit: int

    # Calculated fields
    files_remaining: int
    llm_calls_remaining: int
    files_percentage: float
    llm_calls_percentage: float

    @classmethod
    def from_usage(
        cls,
        tier: str,
        billing_period: str,
        files_migrated: int,
        llm_calls: int,
        files_limit: int,
        llm_calls_limit: int,
    ) -> "QuotaInfo":
        """Create QuotaInfo from usage data."""
        files_remaining = max(0, files_limit - files_migrated)
        llm_calls_remaining = max(0, llm_calls_limit - llm_calls)

        return cls(
            tier=tier,
            billing_period=billing_period,
            files_migrated=files_migrated,
            llm_calls=llm_calls,
            files_limit=files_limit,
            llm_calls_limit=llm_calls_limit,
            files_remaining=files_remaining,
            llm_calls_remaining=llm_calls_remaining,
            files_percentage=round(files_migrated / files_limit * 100, 1) if files_limit > 0 else 0,
            llm_calls_percentage=(
                round(llm_calls / llm_calls_limit * 100, 1) if llm_calls_limit > 0 else 0
            ),
        )


class UsageResponse(BaseModel):
    """Response for usage queries."""

    quota: QuotaInfo
    recent_events: list[UsageEvent] = Field(default_factory=list)


class QuotaCheckRequest(BaseModel):
    """Request to check if an operation is within quota."""

    event_type: str = Field(..., pattern="^(file_migrated|llm_call|scan|apply)$")
    quantity: int = Field(default=1, ge=1)


class QuotaCheckResponse(BaseModel):
    """Response for quota check."""

    allowed: bool
    current_usage: int
    limit: int
    remaining: int
    message: Optional[str] = None

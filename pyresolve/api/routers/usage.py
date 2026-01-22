"""Usage tracking router for the PyResolve API."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from pyresolve.api.auth import CurrentUser
from pyresolve.api.config import get_settings
from pyresolve.api.database import get_database
from pyresolve.api.models.usage import (
    QuotaCheckRequest,
    QuotaCheckResponse,
    QuotaInfo,
    UsageEvent,
    UsageEventCreate,
    UsageResponse,
    UsageSummary,
)

router = APIRouter()


@router.get("/quota", response_model=QuotaInfo)
async def get_quota(user: CurrentUser) -> QuotaInfo:
    """Get current quota information for the authenticated user."""
    db = get_database()
    settings = get_settings()

    # Get user profile for tier info
    profile = db.get_profile_by_id(user.user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    tier = profile.get("tier", "free")
    limits = settings.get_tier_limits(tier)

    # Get current billing period
    billing_period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Get usage for current period
    usage = db.get_usage_for_period(user.user_id, billing_period)

    files_migrated = usage.get("file_migrated", 0)
    llm_calls = usage.get("llm_call", 0)

    return QuotaInfo.from_usage(
        tier=tier,
        billing_period=billing_period,
        files_migrated=files_migrated,
        llm_calls=llm_calls,
        files_limit=limits["files_per_month"],
        llm_calls_limit=limits["llm_calls_per_month"],
    )


@router.get("/", response_model=UsageResponse)
async def get_usage(
    user: CurrentUser,
    billing_period: Optional[str] = None,
    limit: int = 20,
) -> UsageResponse:
    """Get usage summary and recent events."""
    db = get_database()
    settings = get_settings()

    # Get user profile for tier info
    profile = db.get_profile_by_id(user.user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    tier = profile.get("tier", "free")
    limits = settings.get_tier_limits(tier)

    # Default to current billing period
    if not billing_period:
        billing_period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Get usage summary
    usage = db.get_usage_for_period(user.user_id, billing_period)
    files_migrated = usage.get("file_migrated", 0)
    llm_calls = usage.get("llm_call", 0)

    quota = QuotaInfo.from_usage(
        tier=tier,
        billing_period=billing_period,
        files_migrated=files_migrated,
        llm_calls=llm_calls,
        files_limit=limits["files_per_month"],
        llm_calls_limit=limits["llm_calls_per_month"],
    )

    # Get recent events
    events_data = db.get_usage_events(user.user_id, billing_period, limit=limit)

    recent_events = [
        UsageEvent(
            id=e["id"],
            user_id=e["user_id"],
            event_type=e["event_type"],
            library=e.get("library"),
            quantity=e["quantity"],
            metadata=e.get("metadata", {}),
            billing_period=e["billing_period"],
            created_at=e["created_at"],
        )
        for e in events_data
    ]

    return UsageResponse(quota=quota, recent_events=recent_events)


@router.post("/", response_model=UsageEvent)
async def record_usage(request: UsageEventCreate, user: CurrentUser) -> UsageEvent:
    """Record a usage event.

    This is called by the CLI after performing migrations.
    """
    db = get_database()
    settings = get_settings()

    # Get user's tier and limits
    profile = db.get_profile_by_id(user.user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    tier = profile.get("tier", "free")
    limits = settings.get_tier_limits(tier)

    # Get current usage
    billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = db.get_usage_for_period(user.user_id, billing_period)

    # Check quota for file_migrated and llm_call events
    if request.event_type == "file_migrated":
        current = usage.get("file_migrated", 0)
        limit = limits["files_per_month"]
        if current + request.quantity > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"File migration quota exceeded. Used: {current}, Limit: {limit}",
            )
    elif request.event_type == "llm_call":
        current = usage.get("llm_call", 0)
        limit = limits["llm_calls_per_month"]
        if current + request.quantity > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"LLM call quota exceeded. Used: {current}, Limit: {limit}",
            )

    # Record the event
    result = db.record_usage_event(
        user_id=user.user_id,
        event_type=request.event_type,
        library=request.library,
        quantity=request.quantity,
        metadata=request.metadata,
    )

    return UsageEvent(
        id=result["id"],
        user_id=result["user_id"],
        event_type=result["event_type"],
        library=result.get("library"),
        quantity=result["quantity"],
        metadata=result.get("metadata", {}),
        billing_period=result["billing_period"],
        created_at=result["created_at"],
    )


@router.post("/check", response_model=QuotaCheckResponse)
async def check_quota(request: QuotaCheckRequest, user: CurrentUser) -> QuotaCheckResponse:
    """Check if an operation is within quota before performing it.

    This is used by the CLI to pre-check before starting a migration.
    """
    db = get_database()
    settings = get_settings()

    # Get user's tier and limits
    profile = db.get_profile_by_id(user.user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found",
        )

    tier = profile.get("tier", "free")
    limits = settings.get_tier_limits(tier)

    # Get current usage
    billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = db.get_usage_for_period(user.user_id, billing_period)

    # Determine current usage and limit based on event type
    if request.event_type == "file_migrated":
        current_usage = usage.get("file_migrated", 0)
        limit = limits["files_per_month"]
        remaining = max(0, limit - current_usage)
        allowed = current_usage + request.quantity <= limit
        message = (
            None if allowed else f"Would exceed file migration quota ({current_usage}/{limit})"
        )
    elif request.event_type == "llm_call":
        current_usage = usage.get("llm_call", 0)
        limit = limits["llm_calls_per_month"]
        remaining = max(0, limit - current_usage)
        allowed = current_usage + request.quantity <= limit
        message = None if allowed else f"Would exceed LLM call quota ({current_usage}/{limit})"
    else:
        # scan and apply have no limits
        current_usage = usage.get(request.event_type, 0)
        limit = 999999999
        remaining = limit
        allowed = True
        message = None

    return QuotaCheckResponse(
        allowed=allowed,
        current_usage=current_usage,
        limit=limit,
        remaining=remaining,
        message=message,
    )


@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    user: CurrentUser,
    billing_period: Optional[str] = None,
) -> UsageSummary:
    """Get usage summary for a billing period."""
    db = get_database()

    # Default to current billing period
    if not billing_period:
        billing_period = datetime.now(timezone.utc).strftime("%Y-%m")

    usage = db.get_usage_for_period(user.user_id, billing_period)

    return UsageSummary(
        billing_period=billing_period,
        files_migrated=usage.get("file_migrated", 0),
        llm_calls=usage.get("llm_call", 0),
        scans=usage.get("scan", 0),
        applies=usage.get("apply", 0),
        total_events=sum(usage.values()),
    )


@router.get("/history", response_model=list[UsageSummary])
async def get_usage_history(
    user: CurrentUser,
    months: int = 6,
) -> list[UsageSummary]:
    """Get usage history for past months."""
    from datetime import timedelta

    db = get_database()
    summaries = []

    # Calculate billing periods for past N months
    now = datetime.now(timezone.utc)
    for i in range(months):
        date = now - timedelta(days=30 * i)
        billing_period = date.strftime("%Y-%m")

        usage = db.get_usage_for_period(user.user_id, billing_period)

        summaries.append(
            UsageSummary(
                billing_period=billing_period,
                files_migrated=usage.get("file_migrated", 0),
                llm_calls=usage.get("llm_call", 0),
                scans=usage.get("scan", 0),
                applies=usage.get("apply", 0),
                total_events=sum(usage.values()),
            )
        )

    return summaries

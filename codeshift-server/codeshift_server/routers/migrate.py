"""Migration router with thread-safe quota management and rate limiting."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from codeshift_server.middleware.rate_limit import RateLimitConfig, get_rate_limiter
from codeshift_server.utils.prompt_sanitizer import (
    detect_injection_attempt,
    get_data_only_instruction,
    sanitize_code,
    sanitize_context,
    wrap_user_content,
)
from codeshift_server.utils.quota_manager import (
    TIER_LIMITS,
    QuotaManager,
    get_quota_manager,
)
from codeshift_server.utils.usage_tracker import (
    generate_request_id,
    get_usage_tracker,
)

# Get the rate limiter instance
limiter = get_rate_limiter()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/migrate", tags=["migrate"])


# --- Request/Response Models ---


class MigrationRequest(BaseModel):
    """Request model for code migration."""

    source_code: str = Field(..., description="The source code to migrate")
    from_version: str = Field(..., description="Current dependency version")
    to_version: str = Field(..., description="Target dependency version")
    dependency_name: str = Field(..., description="Name of the dependency being upgraded")
    context: Optional[str] = Field(
        default=None, description="Additional context for the migration"
    )
    migration_tier: int = Field(
        default=2, ge=1, le=3, description="Migration tier (1=local, 2=KB-guided, 3=pure LLM)"
    )


class MigrationResponse(BaseModel):
    """Response model for code migration."""

    request_id: str = Field(..., description="Unique request ID for tracking this migration")
    migrated_code: str = Field(..., description="The migrated source code")
    changes_made: list[str] = Field(default_factory=list, description="List of changes applied")
    tier_used: int = Field(..., description="The migration tier that was used")


class QuotaStatusResponse(BaseModel):
    """Response model for quota status."""

    tier: str
    limit: int
    used: int
    available: int
    pending_reservations: int


# --- Mock User/Auth (would be replaced with real auth in production) ---


class User(BaseModel):
    """Mock user model for demonstration."""

    user_id: str
    tier: str
    current_usage: int


async def get_current_user(x_api_key: str = Header(...)) -> User:
    """Get the current authenticated user from API key.

    In production, this would validate the API key against a database
    and return the actual user with their tier and usage info.
    """
    # Mock implementation - in production, look up user by API key
    # For demonstration, we'll parse the tier from the API key format
    if x_api_key.startswith("free_"):
        return User(user_id=x_api_key, tier="free", current_usage=0)
    elif x_api_key.startswith("pro_"):
        return User(user_id=x_api_key, tier="pro", current_usage=50)
    elif x_api_key.startswith("unlimited_"):
        return User(user_id=x_api_key, tier="unlimited", current_usage=100)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


# --- Quota Helper Functions ---


def reserve_llm_quota(
    quota_manager: QuotaManager,
    user_id: str,
    tier: str,
    current_usage: int,
) -> str:
    """Reserve quota for an LLM migration operation.

    Args:
        quota_manager: The QuotaManager instance.
        user_id: The user's ID.
        tier: The user's subscription tier.
        current_usage: The user's current usage count.

    Returns:
        The reservation ID.

    Raises:
        HTTPException: If quota limit would be exceeded.
    """
    reservation_id = quota_manager.reserve_quota(
        user_id=user_id,
        tier=tier,
        current_usage=current_usage,
        amount=1,
    )

    if reservation_id is None:
        limit = TIER_LIMITS.get(tier, 0)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quota limit exceeded. Your {tier} tier allows {limit} LLM migrations per month.",
        )

    logger.info(f"Reserved quota for user {user_id}: reservation_id={reservation_id}")
    return reservation_id


def confirm_llm_usage(
    quota_manager: QuotaManager,
    reservation_id: str,
) -> None:
    """Confirm that the reserved quota was used.

    Args:
        quota_manager: The QuotaManager instance.
        reservation_id: The reservation ID to confirm.
    """
    if quota_manager.confirm_usage(reservation_id):
        logger.info(f"Confirmed quota usage: reservation_id={reservation_id}")
    else:
        logger.warning(f"Failed to confirm quota usage: reservation_id={reservation_id}")


def release_llm_quota(
    quota_manager: QuotaManager,
    reservation_id: str,
) -> None:
    """Release a quota reservation (e.g., on failure).

    Args:
        quota_manager: The QuotaManager instance.
        reservation_id: The reservation ID to release.
    """
    if quota_manager.release_quota(reservation_id):
        logger.info(f"Released quota reservation: reservation_id={reservation_id}")
    else:
        logger.warning(f"Failed to release quota reservation: reservation_id={reservation_id}")


# --- Prompt Building with Sanitization ---


def build_sanitized_prompt(request: MigrationRequest) -> str:
    """Build a sanitized prompt for LLM migration.

    This function sanitizes user-provided code and context,
    wraps them in XML delimiters, and includes instructions
    to treat the content as data only.

    Args:
        request: The migration request containing code and context.

    Returns:
        A sanitized prompt string safe for LLM consumption.
    """
    # Sanitize user inputs
    sanitized_code = sanitize_code(request.source_code)
    sanitized_context = sanitize_context(request.context or "")

    # Wrap in XML delimiters
    wrapped_code = wrap_user_content(sanitized_code, "user_code")
    wrapped_context = wrap_user_content(sanitized_context, "user_context") if sanitized_context else ""

    # Build the prompt with data-only instruction
    data_instruction = get_data_only_instruction()

    prompt_parts = [
        data_instruction,
        "",
        f"Migrate the following Python code from {request.dependency_name} "
        f"version {request.from_version} to version {request.to_version}.",
        "",
        wrapped_code,
    ]

    if wrapped_context:
        prompt_parts.extend(["", "Additional context:", wrapped_context])

    prompt_parts.extend([
        "",
        "Provide only the migrated code without explanations.",
    ])

    return "\n".join(prompt_parts)


def validate_request_for_injection(request: MigrationRequest) -> None:
    """Validate request inputs for potential injection attempts.

    Args:
        request: The migration request to validate.

    Raises:
        HTTPException: If a potential injection attempt is detected.
    """
    # Check source code for injection attempts
    if detect_injection_attempt(request.source_code):
        logger.warning("Potential injection attempt detected in source_code")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request contains potentially malicious content",
        )

    # Check context for injection attempts
    if request.context and detect_injection_attempt(request.context):
        logger.warning("Potential injection attempt detected in context")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request contains potentially malicious content",
        )


# --- Migration Logic (Mock implementations) ---


async def perform_tier1_migration(request: MigrationRequest, request_id: str) -> MigrationResponse:
    """Perform Tier 1 local transformation (no LLM, no quota needed)."""
    # In production, this would apply AST-based transformations
    # Tier 1 doesn't use LLM, so no prompt sanitization needed
    return MigrationResponse(
        request_id=request_id,
        migrated_code=request.source_code,
        changes_made=["Applied local AST transformations"],
        tier_used=1,
    )


async def perform_tier2_migration(request: MigrationRequest, request_id: str) -> MigrationResponse:
    """Perform Tier 2 KB-guided LLM migration.

    This function builds a sanitized prompt with user content wrapped
    in XML delimiters to prevent prompt injection attacks.
    """
    # Validate for injection attempts
    validate_request_for_injection(request)

    # Build sanitized prompt for LLM
    prompt = build_sanitized_prompt(request)

    # In production, this would:
    # 1. Retrieve relevant knowledge base entries
    # 2. Send the sanitized prompt to the LLM
    # 3. Parse and return the migrated code
    logger.debug(f"Tier 2 migration prompt built: {len(prompt)} chars")

    return MigrationResponse(
        request_id=request_id,
        migrated_code=f"# Migrated with KB guidance\n{request.source_code}",
        changes_made=["Applied KB-guided LLM migration"],
        tier_used=2,
    )


async def perform_tier3_migration(request: MigrationRequest, request_id: str) -> MigrationResponse:
    """Perform Tier 3 pure LLM migration.

    This function builds a sanitized prompt with user content wrapped
    in XML delimiters to prevent prompt injection attacks.
    """
    # Validate for injection attempts
    validate_request_for_injection(request)

    # Build sanitized prompt for LLM
    prompt = build_sanitized_prompt(request)

    # In production, this would:
    # 1. Send the sanitized prompt directly to the LLM
    # 2. Parse and return the migrated code
    logger.debug(f"Tier 3 migration prompt built: {len(prompt)} chars")

    return MigrationResponse(
        request_id=request_id,
        migrated_code=f"# Migrated with pure LLM\n{request.source_code}",
        changes_made=["Applied pure LLM migration"],
        tier_used=3,
    )


# --- API Endpoints ---


@router.post("/", response_model=MigrationResponse)
@limiter.limit(RateLimitConfig.MIGRATE_CODE_LIMIT)
async def migrate_code(
    request: Request,
    migration_request: MigrationRequest,
    user: User = Depends(get_current_user),
    quota_manager: QuotaManager = Depends(get_quota_manager),
) -> MigrationResponse:
    """Migrate code to a new dependency version.

    This endpoint handles code migration across all tiers:
    - Tier 1: Local AST transformations (free, no quota)
    - Tier 2: KB-guided LLM migration (requires quota)
    - Tier 3: Pure LLM migration (requires quota)

    For Tier 2 and 3, quota is reserved atomically before starting
    the migration to prevent race conditions in concurrent requests.
    Usage is tracked with a debit/credit model for reliability.
    """
    # Generate unique request ID for tracking
    request_id = generate_request_id()
    usage_tracker = get_usage_tracker()

    # Tier 1 doesn't require quota or usage tracking
    if migration_request.migration_tier == 1:
        return await perform_tier1_migration(migration_request, request_id)

    # Tier 2 and 3 require LLM quota and usage tracking
    reservation_id: Optional[str] = None
    event_type = f"tier{migration_request.migration_tier}_migration"

    try:
        # Reserve quota atomically before starting migration
        reservation_id = reserve_llm_quota(
            quota_manager=quota_manager,
            user_id=user.user_id,
            tier=user.tier,
            current_usage=user.current_usage,
        )

        # Record pending usage BEFORE LLM call (debit)
        usage_tracker.record_pending_usage(
            user_id=user.user_id,
            request_id=request_id,
            event_type=event_type,
            library=migration_request.dependency_name,
            estimated_cost=1.0,
        )

        # Perform the migration based on requested tier
        if migration_request.migration_tier == 2:
            result = await perform_tier2_migration(migration_request, request_id)
        else:
            result = await perform_tier3_migration(migration_request, request_id)

        # Confirm the quota usage on success
        confirm_llm_usage(quota_manager, reservation_id)

        # Confirm usage tracking (credit confirmation)
        usage_tracker.confirm_usage(
            request_id=request_id,
            actual_cost=1.0,
            metadata={
                "tier": migration_request.migration_tier,
                "library": migration_request.dependency_name,
                "from_version": migration_request.from_version,
                "to_version": migration_request.to_version,
            },
        )

        return result

    except HTTPException:
        # Cancel pending usage on HTTP exceptions (like quota exceeded)
        usage_tracker.cancel_pending_usage(request_id, "HTTP exception during migration")
        raise

    except Exception as e:
        # On any other error, release the reservation and cancel usage
        logger.error(f"Migration failed for user {user.user_id}: {e}")
        if reservation_id is not None:
            release_llm_quota(quota_manager, reservation_id)
        usage_tracker.cancel_pending_usage(request_id, f"Migration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Migration failed unexpectedly",
        )


@router.post("/batch", response_model=list[MigrationResponse])
@limiter.limit(RateLimitConfig.MIGRATE_BATCH_LIMIT)
async def migrate_batch(
    request: Request,
    migration_requests: list[MigrationRequest],
    user: User = Depends(get_current_user),
    quota_manager: QuotaManager = Depends(get_quota_manager),
) -> list[MigrationResponse]:
    """Migrate multiple code files in a batch.

    Reserves quota for all LLM-based migrations upfront to ensure
    the entire batch can be processed before starting any work.
    Usage is tracked with a debit/credit model for reliability.

    Args:
        request: The incoming HTTP request (required for rate limiting).
        migration_requests: List of migration request parameters.
        user: The authenticated user.
        quota_manager: The quota manager instance.

    Returns:
        List of migration responses with migrated code.
    """
    usage_tracker = get_usage_tracker()

    # Count how many LLM migrations are needed
    llm_migration_count = sum(1 for r in migration_requests if r.migration_tier > 1)

    reservation_ids: list[str] = []
    request_ids: list[str] = []

    try:
        # Reserve quota for all LLM migrations upfront
        for _ in range(llm_migration_count):
            reservation_id = reserve_llm_quota(
                quota_manager=quota_manager,
                user_id=user.user_id,
                tier=user.tier,
                current_usage=user.current_usage + len(reservation_ids),
            )
            reservation_ids.append(reservation_id)

        # Process all migrations
        results: list[MigrationResponse] = []
        reservation_idx = 0

        for migration_req in migration_requests:
            # Generate unique request ID for each migration
            req_id = generate_request_id()
            request_ids.append(req_id)

            if migration_req.migration_tier == 1:
                result = await perform_tier1_migration(migration_req, req_id)
            elif migration_req.migration_tier == 2:
                # Record pending usage before LLM call (debit)
                usage_tracker.record_pending_usage(
                    user_id=user.user_id,
                    request_id=req_id,
                    event_type="tier2_migration",
                    library=migration_req.dependency_name,
                    estimated_cost=1.0,
                )
                result = await perform_tier2_migration(migration_req, req_id)
                confirm_llm_usage(quota_manager, reservation_ids[reservation_idx])
                # Confirm usage tracking (credit confirmation)
                usage_tracker.confirm_usage(
                    request_id=req_id,
                    actual_cost=1.0,
                    metadata={
                        "tier": 2,
                        "library": migration_req.dependency_name,
                        "batch": True,
                    },
                )
                reservation_idx += 1
            else:
                # Record pending usage before LLM call (debit)
                usage_tracker.record_pending_usage(
                    user_id=user.user_id,
                    request_id=req_id,
                    event_type="tier3_migration",
                    library=migration_req.dependency_name,
                    estimated_cost=1.0,
                )
                result = await perform_tier3_migration(migration_req, req_id)
                confirm_llm_usage(quota_manager, reservation_ids[reservation_idx])
                # Confirm usage tracking (credit confirmation)
                usage_tracker.confirm_usage(
                    request_id=req_id,
                    actual_cost=1.0,
                    metadata={
                        "tier": 3,
                        "library": migration_req.dependency_name,
                        "batch": True,
                    },
                )
                reservation_idx += 1

            results.append(result)

        return results

    except HTTPException:
        # Release any remaining reservations and cancel pending usage
        for rid in reservation_ids:
            release_llm_quota(quota_manager, rid)
        for req_id in request_ids:
            usage_tracker.cancel_pending_usage(req_id, "Batch HTTP exception")
        raise

    except Exception as e:
        # Release all reservations and cancel pending usage on failure
        logger.error(f"Batch migration failed for user {user.user_id}: {e}")
        for rid in reservation_ids:
            release_llm_quota(quota_manager, rid)
        for req_id in request_ids:
            usage_tracker.cancel_pending_usage(req_id, f"Batch error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch migration failed unexpectedly",
        )


@router.get("/quota", response_model=QuotaStatusResponse)
@limiter.limit(RateLimitConfig.USAGE_CHECK_LIMIT)
async def get_quota_status(
    request: Request,
    user: User = Depends(get_current_user),
    quota_manager: QuotaManager = Depends(get_quota_manager),
) -> QuotaStatusResponse:
    """Get the current quota status for the authenticated user.

    Args:
        request: The incoming HTTP request (required for rate limiting).
        user: The authenticated user.
        quota_manager: The quota manager instance.

    Returns:
        The current quota status for the user.
    """
    tier = user.tier
    limit = TIER_LIMITS.get(tier, 0)
    available = quota_manager.get_available_quota(
        user_id=user.user_id,
        tier=tier,
        current_usage=user.current_usage,
    )
    pending = quota_manager.get_pending_reservations_count(user.user_id)

    return QuotaStatusResponse(
        tier=tier,
        limit=limit,
        used=user.current_usage,
        available=available,
        pending_reservations=pending,
    )

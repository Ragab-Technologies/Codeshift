"""Migration router for LLM-powered code migrations.

This router handles all LLM-powered migrations (Tier 2/3).
The Anthropic API calls are made server-side, ensuring:
1. Users don't need their own API keys
2. Usage can be tracked and billed
3. The LLM prompts remain server-side
"""

import re
from typing import Annotated

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status

from codeshift.api.auth import AuthenticatedUser, require_tier
from codeshift.api.config import get_settings
from codeshift.api.database import get_database
from codeshift.api.models.migrate import (
    ExplainChangeRequest,
    ExplainChangeResponse,
    MigrateCodeRequest,
    MigrateCodeResponse,
)

router = APIRouter(prefix="/migrate", tags=["migrate"])


def get_anthropic_client():  # type: ignore[no-untyped-def]
    """Get the server-side Anthropic client."""

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM service not configured",
        )

    return Anthropic(api_key=settings.anthropic_api_key)


def check_llm_quota(user: AuthenticatedUser, quantity: int = 1) -> None:
    """Check if user has remaining LLM quota.

    Raises HTTPException if quota exceeded.
    """
    db = get_database()
    quota = db.get_user_quota(user.user_id)

    if not quota:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve quota information",
        )

    # Get tier limits
    tier_limits = {
        "free": 0,  # Free tier cannot use LLM
        "pro": 100,
        "unlimited": 999999,
        "enterprise": 999999,
    }

    limit = tier_limits.get(user.tier, 0)
    current_usage = quota.get("llm_calls", 0)

    if current_usage + quantity > limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "LLM quota exceeded",
                "current_usage": current_usage,
                "limit": limit,
                "tier": user.tier,
                "upgrade_url": "https://codeshift.dev/pricing",
            },
        )


def record_llm_usage(user: AuthenticatedUser, library: str, tokens_used: dict) -> None:
    """Record LLM usage for billing."""
    db = get_database()
    db.record_usage_event(
        user_id=user.user_id,
        event_type="llm_call",
        library=library,
        quantity=1,
        metadata={
            "input_tokens": tokens_used.get("input_tokens", 0),
            "output_tokens": tokens_used.get("output_tokens", 0),
        },
    )


def extract_code_from_response(content: str) -> str:
    """Extract Python code from LLM response."""
    # Try to find code block
    code_block_pattern = r"```(?:python)?\n(.*?)```"
    matches = re.findall(code_block_pattern, content, re.DOTALL)

    if matches:
        # Return the longest code block (likely the full migration)
        longest_match: str = max(matches, key=len)
        return longest_match.strip()

    # No code block found, assume the entire response is code
    content = content.strip()
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    return content.strip()


def validate_syntax(code: str) -> bool:
    """Quick syntax validation."""
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


@router.post("/code", response_model=MigrateCodeResponse)
async def migrate_code(
    request: MigrateCodeRequest,
    user: Annotated[AuthenticatedUser, Depends(require_tier("pro"))],
) -> MigrateCodeResponse:
    """Migrate code using LLM.

    This endpoint requires Pro tier or higher.
    The LLM call is made server-side using PyResolve's Anthropic API key.
    """
    # Check quota
    check_llm_quota(user)

    # Get Anthropic client
    client = get_anthropic_client()

    # Build the prompt
    system_prompt = f"""You are an expert Python developer specializing in code migrations.
Your task is to migrate Python code from {request.library} v{request.from_version} to v{request.to_version}.

Guidelines:
1. Only modify code that needs to change for the migration
2. Preserve all comments, formatting, and code style where possible
3. Add brief inline comments explaining non-obvious changes
4. If you're unsure about a change, add a TODO comment
5. Return ONLY the migrated code, no explanations before or after

Important {request.library} migration changes to consider:
- Config class -> model_config = ConfigDict(...)
- @validator -> @field_validator with @classmethod
- @root_validator -> @model_validator with @classmethod
- .dict() -> .model_dump()
- .json() -> .model_dump_json()
- .schema() -> .model_json_schema()
- .parse_obj() -> .model_validate()
- .parse_raw() -> .model_validate_json()
- .copy() -> .model_copy()
- orm_mode -> from_attributes
- Field(regex=...) -> Field(pattern=...)
"""

    user_prompt = f"""Migrate the following Python code from {request.library} v{request.from_version} to v{request.to_version}.

{f"Context: {request.context}" if request.context else ""}

Code to migrate:
```python
{request.code}
```

Return only the migrated Python code:"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        # Extract code from response
        migrated_code = extract_code_from_response(content)

        # Validate syntax
        if not validate_syntax(migrated_code):
            return MigrateCodeResponse(
                success=False,
                migrated_code=request.code,
                original_code=request.code,
                error="LLM output has syntax errors",
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        # Record usage
        record_llm_usage(
            user,
            request.library,
            {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

        return MigrateCodeResponse(
            success=True,
            migrated_code=migrated_code,
            original_code=request.code,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    except Exception as e:
        return MigrateCodeResponse(
            success=False,
            migrated_code=request.code,
            original_code=request.code,
            error=str(e),
        )


@router.post("/explain", response_model=ExplainChangeResponse)
async def explain_change(
    request: ExplainChangeRequest,
    user: Annotated[AuthenticatedUser, Depends(require_tier("pro"))],
) -> ExplainChangeResponse:
    """Explain a migration change using LLM.

    This endpoint requires Pro tier or higher.
    """
    # Check quota
    check_llm_quota(user)

    # Get Anthropic client
    client = get_anthropic_client()

    system_prompt = """You are an expert Python developer.
Explain code changes clearly and concisely for other developers.
Focus on the 'why' not just the 'what'."""

    user_prompt = f"""Explain the following {request.library} migration change:

Original:
```python
{request.original_code}
```

Migrated:
```python
{request.transformed_code}
```

Provide a brief explanation (2-3 sentences) of what changed and why:"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        # Record usage
        record_llm_usage(
            user,
            request.library,
            {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

        return ExplainChangeResponse(
            success=True,
            explanation=content.strip(),
        )

    except Exception as e:
        return ExplainChangeResponse(
            success=False,
            error=str(e),
        )

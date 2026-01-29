"""LLM-based migration for complex cases.

LLM migrations (Tier 2/3) are routed through the Codeshift API,
which handles authentication, quota checking, and billing.
Users must have a Pro or Unlimited subscription to use LLM features.

Tier 1 (deterministic AST transforms) remains free and local.

SECURITY: Direct LLM access is blocked. All LLM calls must go through
the Codeshift API to ensure proper authentication and billing.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from codeshift.migrator.ast_transforms import TransformChange, TransformResult, TransformStatus
from codeshift.utils.api_client import CodeshiftAPIClient, get_api_client
from codeshift.utils.cache import LLMCache, get_llm_cache
from codeshift.validator.syntax_checker import quick_syntax_check


class DirectLLMAccessError(Exception):
    """Raised when attempting to bypass the Codeshift API for LLM access.

    All LLM migrations must go through the Codeshift API to ensure proper
    authentication, billing, and quota management. Direct use of API keys
    is not supported.

    To use LLM features:
    1. Run 'codeshift login' to authenticate
    2. Upgrade to Pro or Unlimited tier at https://codeshift.dev/pricing
    3. Use LLMMigrator without passing api_key parameters
    """

    pass


@dataclass
class LLMMigrationResult:
    """Result of an LLM-based migration."""

    original_code: str
    migrated_code: str
    success: bool
    used_cache: bool = False
    error: str | None = None
    validation_passed: bool = True
    usage: dict | None = None


class LLMMigrator:
    """Handles complex migrations using LLM via the Codeshift API.

    LLM migrations require authentication and a Pro or Unlimited subscription.
    All LLM calls are routed through the Codeshift API, which handles:
    - Authentication and authorization
    - Quota checking and billing
    - Server-side Anthropic API calls

    This ensures users cannot bypass the subscription model by using
    their own API keys.
    """

    def __init__(
        self,
        client: CodeshiftAPIClient | None = None,
        cache: LLMCache | None = None,
        use_cache: bool = True,
        validate_output: bool = True,
        **kwargs: object,
    ):
        """Initialize the LLM migrator.

        Args:
            client: API client to use. Defaults to singleton.
            cache: Cache to use. Defaults to singleton.
            use_cache: Whether to use caching
            validate_output: Whether to validate migrated code syntax
            **kwargs: Rejected keyword arguments (security check)

        Raises:
            DirectLLMAccessError: If attempting to pass API keys directly
        """
        # Security check: Block attempts to pass API keys directly
        blocked_kwargs = {"api_key", "anthropic_api_key", "openai_api_key", "llm_api_key"}
        passed_blocked = blocked_kwargs & set(kwargs.keys())
        if passed_blocked:
            raise DirectLLMAccessError(
                f"Direct API key access is not allowed. "
                f"Blocked parameters: {', '.join(passed_blocked)}. "
                f"All LLM migrations must go through the Codeshift API. "
                f"Run 'codeshift login' to authenticate and upgrade to Pro tier."
            )

        # Security check: Warn if ANTHROPIC_API_KEY is set without Codeshift auth
        if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("CODESHIFT_API_KEY"):
            raise DirectLLMAccessError(
                "ANTHROPIC_API_KEY environment variable detected without Codeshift authentication. "
                "Direct LLM access is not supported. All LLM migrations must go through "
                "the Codeshift API for proper billing and quota management. "
                "Run 'codeshift login' to authenticate, then unset ANTHROPIC_API_KEY."
            )

        self.client = client or get_api_client()
        self.cache = cache or get_llm_cache() if use_cache else None
        self.use_cache = use_cache
        self.validate_output = validate_output

    @property
    def is_available(self) -> bool:
        """Check if LLM migration is available (user is authenticated)."""
        return self.client.is_available

    def migrate(
        self,
        code: str,
        library: str,
        from_version: str,
        to_version: str,
        context: str | None = None,
    ) -> LLMMigrationResult:
        """Migrate code using the LLM via Codeshift API.

        Args:
            code: Source code to migrate
            library: Library being upgraded
            from_version: Current version
            to_version: Target version
            context: Optional context about the code

        Returns:
            LLMMigrationResult with the migrated code
        """
        if not self.is_available:
            return LLMMigrationResult(
                original_code=code,
                migrated_code=code,
                success=False,
                error=(
                    "LLM migrations require authentication. "
                    "Run 'codeshift login' to authenticate, then upgrade to Pro tier."
                ),
            )

        # Check cache first
        if self.use_cache and self.cache:
            cached = self.cache.get_migration(code, library, from_version, to_version)
            if cached:
                return LLMMigrationResult(
                    original_code=code,
                    migrated_code=cached,
                    success=True,
                    used_cache=True,
                )

        # Call Codeshift API (which calls Anthropic server-side)
        response = self.client.migrate_code(
            code=code,
            library=library,
            from_version=from_version,
            to_version=to_version,
            context=context,
        )

        if not response.success:
            return LLMMigrationResult(
                original_code=code,
                migrated_code=code,
                success=False,
                error=response.error,
            )

        migrated_code = response.content

        # Validate syntax
        validation_passed = True
        if self.validate_output:
            if not quick_syntax_check(migrated_code):
                validation_passed = False
                # Try to fix common issues
                migrated_code = self._attempt_fix(migrated_code)
                if not quick_syntax_check(migrated_code):
                    return LLMMigrationResult(
                        original_code=code,
                        migrated_code=code,
                        success=False,
                        error="LLM output has syntax errors",
                        validation_passed=False,
                    )

        # Cache the result
        if self.use_cache and self.cache:
            self.cache.set_migration(code, library, from_version, to_version, migrated_code)

        return LLMMigrationResult(
            original_code=code,
            migrated_code=migrated_code,
            success=True,
            validation_passed=validation_passed,
            usage=response.usage,
        )

    def _attempt_fix(self, code: str) -> str:
        """Attempt to fix common syntax issues in LLM output.

        Args:
            code: Code with potential issues

        Returns:
            Fixed code (or original if unfixable)
        """
        # Common fixes
        fixes = [
            # Remove trailing incomplete lines
            (r"\n\s*$", "\n"),
            # Fix unclosed strings (simple cases)
            (r'(["\'])([^"\'\n]*?)$', r"\1\2\1"),
        ]

        fixed = code
        for pattern, replacement in fixes:
            fixed = re.sub(pattern, replacement, fixed)

        return fixed

    def explain_migration(
        self,
        original: str,
        transformed: str,
        library: str,
    ) -> str | None:
        """Get an explanation of a migration change.

        Args:
            original: Original code
            transformed: Transformed code
            library: Library being upgraded

        Returns:
            Explanation string or None if unavailable
        """
        if not self.is_available:
            return None

        response = self.client.explain_change(original, transformed, library)
        if response.success:
            return response.content.strip()
        return None


def migrate_with_llm_fallback(
    code: str,
    library: str,
    from_version: str,
    to_version: str,
    deterministic_result: TransformResult | None = None,
) -> TransformResult:
    """Migrate code with LLM as a fallback for failures.

    IMPORTANT: LLM migrations require Pro tier or higher subscription.
    If the user is not authenticated or doesn't have the required tier,
    only deterministic transforms will be applied.

    Args:
        code: Source code to migrate
        library: Library being upgraded
        from_version: Current version
        to_version: Target version
        deterministic_result: Optional result from deterministic transform

    Returns:
        TransformResult combining deterministic and LLM migrations
    """
    # If deterministic transform succeeded fully, use it
    if deterministic_result and deterministic_result.status == TransformStatus.SUCCESS:
        return deterministic_result

    # Try LLM migration
    migrator = LLMMigrator()

    if not migrator.is_available:
        # Return deterministic result if available, or no changes
        if deterministic_result:
            # Add a note about LLM not being available
            errors = list(deterministic_result.errors)
            errors.append(
                "LLM fallback not available. Run 'codeshift login' and upgrade to Pro "
                "for LLM-powered migrations."
            )
            return TransformResult(
                file_path=deterministic_result.file_path,
                status=deterministic_result.status,
                original_code=deterministic_result.original_code,
                transformed_code=deterministic_result.transformed_code,
                changes=deterministic_result.changes,
                errors=errors,
            )
        return TransformResult(
            file_path=Path("<unknown>"),
            status=TransformStatus.NO_CHANGES,
            original_code=code,
            transformed_code=code,
            errors=[
                "LLM not available. Run 'codeshift login' and upgrade to Pro "
                "for LLM-powered migrations."
            ],
        )

    # Use deterministic result as base if available
    base_code = deterministic_result.transformed_code if deterministic_result else code
    context = None

    if deterministic_result and deterministic_result.errors:
        context = f"Deterministic transform had issues: {', '.join(deterministic_result.errors)}"

    result = migrator.migrate(
        code=base_code,
        library=library,
        from_version=from_version,
        to_version=to_version,
        context=context,
    )

    # Combine results
    changes = []
    if deterministic_result:
        changes.extend(deterministic_result.changes)

    if result.success and result.migrated_code != base_code:
        changes.append(
            TransformChange(
                description="LLM-assisted migration",
                line_number=1,
                original="(various)",
                replacement="(LLM migrated)",
                transform_name="llm_migration",
                confidence=0.8,  # Lower confidence for LLM
                notes="This change was made by the LLM and should be reviewed carefully",
            )
        )

    status = TransformStatus.SUCCESS if result.success else TransformStatus.PARTIAL
    if not changes:
        status = TransformStatus.NO_CHANGES

    errors = []
    if deterministic_result:
        errors.extend(deterministic_result.errors)
    if result.error:
        errors.append(result.error)

    return TransformResult(
        file_path=deterministic_result.file_path if deterministic_result else Path("<unknown>"),
        status=status,
        original_code=code,
        transformed_code=result.migrated_code if result.success else base_code,
        changes=changes,
        errors=errors,
    )

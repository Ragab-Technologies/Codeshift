"""LLM-based migration for complex cases.

LLM migrations (Tier 2/3) are routed through the PyResolve API,
which handles authentication, quota checking, and billing.
Users must have a Pro or Unlimited subscription to use LLM features.

Tier 1 (deterministic AST transforms) remains free and local.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pyresolve.migrator.ast_transforms import (
    TransformChange,
    TransformResult,
    TransformStatus,
)
from pyresolve.utils.api_client import PyResolveAPIClient, get_api_client
from pyresolve.utils.cache import LLMCache, get_llm_cache
from pyresolve.validator.syntax_checker import quick_syntax_check


@dataclass
class LLMMigrationResult:
    """Result of an LLM-based migration."""

    original_code: str
    migrated_code: str
    success: bool
    used_cache: bool = False
    error: Optional[str] = None
    validation_passed: bool = True
    usage: Optional[dict] = None


class LLMMigrator:
    """Handles complex migrations using LLM via the PyResolve API.

    LLM migrations require authentication and a Pro or Unlimited subscription.
    All LLM calls are routed through the PyResolve API, which handles:
    - Authentication and authorization
    - Quota checking and billing
    - Server-side Anthropic API calls

    This ensures users cannot bypass the subscription model by using
    their own API keys.
    """

    def __init__(
        self,
        client: Optional[PyResolveAPIClient] = None,
        cache: Optional[LLMCache] = None,
        use_cache: bool = True,
        validate_output: bool = True,
    ):
        """Initialize the LLM migrator.

        Args:
            client: API client to use. Defaults to singleton.
            cache: Cache to use. Defaults to singleton.
            use_cache: Whether to use caching
            validate_output: Whether to validate migrated code syntax
        """
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
        context: Optional[str] = None,
    ) -> LLMMigrationResult:
        """Migrate code using the LLM via PyResolve API.

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
                    "Run 'pyresolve login' to authenticate, then upgrade to Pro tier."
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

        # Call PyResolve API (which calls Anthropic server-side)
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
    ) -> Optional[str]:
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
    deterministic_result: Optional[TransformResult] = None,
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
                "LLM fallback not available. Run 'pyresolve login' and upgrade to Pro "
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
                "LLM not available. Run 'pyresolve login' and upgrade to Pro "
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

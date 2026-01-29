"""Anthropic Claude client wrapper for LLM-based migrations.

SECURITY NOTE: This module is intended for internal use only.
Direct access to the LLM client bypasses quota and billing controls.
Use the Codeshift API client (api_client.py) for all LLM operations.
"""

import logging
import os
import sys
from dataclasses import dataclass

from anthropic import Anthropic

# Prevent any exports from this module
__all__: list[str] = []

logger = logging.getLogger(__name__)


class DirectLLMAccessError(Exception):
    """Raised when code attempts to bypass the Codeshift API and access LLM directly.

    The LLMClient is for internal server-side use only. Client applications
    should use the Codeshift API which enforces quotas, billing, and access control.
    """

    def __init__(self, message: str | None = None):
        default_msg = (
            "Direct LLM access is not permitted. "
            "Use the Codeshift API client for LLM operations. "
            "Run 'codeshift login' to authenticate."
        )
        super().__init__(message or default_msg)


@dataclass
class LLMResponse:
    """Response from the LLM."""

    content: str
    model: str
    usage: dict
    success: bool
    error: str | None = None


def _check_direct_access_attempt() -> None:
    """Check if this is an unauthorized direct access attempt.

    Raises:
        DirectLLMAccessError: If direct access is detected from external code.
    """
    # Check if ANTHROPIC_API_KEY is set by the user (potential bypass attempt)
    # This is allowed only for internal server use or development
    if os.environ.get("ANTHROPIC_API_KEY"):
        # Check if this is being called from within the codeshift package
        frame = sys._getframe(2)  # Caller's caller
        caller_file = frame.f_code.co_filename

        # Allow internal codeshift modules and tests
        allowed_paths = (
            "codeshift/",
            "codeshift\\",  # Windows path
            "tests/",
            "tests\\",
            "<stdin>",  # Interactive Python
            "<string>",  # exec/eval
        )

        is_internal = any(path in caller_file for path in allowed_paths)

        # Also check for environment flag indicating authorized server use
        is_authorized_server = os.environ.get("CODESHIFT_SERVER_MODE") == "true"

        if not is_internal and not is_authorized_server:
            logger.warning(
                "Direct LLM access attempt detected from: %s. "
                "This bypasses quota and billing controls.",
                caller_file,
            )
            raise DirectLLMAccessError(
                "Direct use of ANTHROPIC_API_KEY detected. "
                "This bypasses Codeshift's quota and billing system. "
                "Use 'codeshift upgrade' commands which route through the API."
            )


class _LLMClient:
    """Internal client for interacting with Anthropic's Claude API.

    SECURITY: This class is private (prefixed with _) and should not be
    instantiated directly by external code. All LLM operations should go
    through the Codeshift API which enforces access controls.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        _bypass_check: bool = False,
    ):
        """Initialize the LLM client.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            model: Model to use. Defaults to claude-sonnet-4-20250514.
            _bypass_check: Internal flag to bypass access check (for server use).
        """
        # Security check for unauthorized direct access
        if not _bypass_check:
            _check_direct_access_attempt()

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or self.DEFAULT_MODEL
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable "
                    "or pass api_key to _LLMClient."
                )
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if the LLM client is available (API key is set)."""
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 for deterministic)

        Returns:
            LLMResponse with the generated content
        """
        if not self.is_available:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error="API key not configured",
            )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.MAX_TOKENS,
                temperature=temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}],
            )

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return LLMResponse(
                content=content,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                success=True,
            )

        except Exception as e:
            return LLMResponse(
                content="",
                model=self.model,
                usage={},
                success=False,
                error=str(e),
            )

    def migrate_code(
        self,
        code: str,
        library: str,
        from_version: str,
        to_version: str,
        context: str | None = None,
    ) -> LLMResponse:
        """Use the LLM to migrate code.

        Args:
            code: The source code to migrate
            library: The library being upgraded
            from_version: Current version
            to_version: Target version
            context: Optional context about the migration

        Returns:
            LLMResponse with the migrated code
        """
        system_prompt = f"""You are an expert Python developer specializing in code migrations.
Your task is to migrate Python code from {library} v{from_version} to v{to_version}.

Guidelines:
1. Only modify code that needs to change for the migration
2. Preserve all comments, formatting, and code style where possible
3. Add brief inline comments explaining non-obvious changes
4. If you're unsure about a change, add a TODO comment
5. Return ONLY the migrated code, no explanations before or after

Important {library} v{from_version} to v{to_version} changes:
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

        prompt = f"""Migrate the following Python code from {library} v{from_version} to v{to_version}.

{f"Context: {context}" if context else ""}

Code to migrate:
```python
{code}
```

Return only the migrated Python code:"""

        return self.generate(prompt, system_prompt=system_prompt)

    def explain_change(
        self,
        original: str,
        transformed: str,
        library: str,
    ) -> LLMResponse:
        """Use the LLM to explain a migration change.

        Args:
            original: Original code
            transformed: Transformed code
            library: The library being upgraded

        Returns:
            LLMResponse with the explanation
        """
        system_prompt = """You are an expert Python developer.
Explain code changes clearly and concisely for other developers.
Focus on the 'why' not just the 'what'."""

        prompt = f"""Explain the following {library} migration change:

Original:
```python
{original}
```

Migrated:
```python
{transformed}
```

Provide a brief explanation (2-3 sentences) of what changed and why:"""

        return self.generate(prompt, system_prompt=system_prompt, max_tokens=500)


# Keep backward compatibility alias but mark as deprecated
# This will be removed in a future version
LLMClient = _LLMClient


# Singleton instance for internal use only
_default_client: _LLMClient | None = None


def _get_llm_client(_bypass_check: bool = False) -> _LLMClient:
    """Get the default LLM client instance.

    INTERNAL USE ONLY: This function is for internal codeshift server use.
    External code should use the Codeshift API client.

    Args:
        _bypass_check: Internal flag to bypass access check (for server use).
    """
    global _default_client
    if _default_client is None:
        _default_client = _LLMClient(_bypass_check=_bypass_check)
    return _default_client


# Keep backward compatibility but with security check
def get_llm_client() -> _LLMClient:
    """Get the default LLM client instance.

    DEPRECATED: Use the Codeshift API client (api_client.py) instead.
    This function will be removed in a future version.
    """
    return _get_llm_client(_bypass_check=False)

"""Anthropic Claude client wrapper for LLM-based migrations.

WARNING: This module is INTERNAL ONLY. Do not import or use directly.

All LLM access must go through the Codeshift API to ensure proper
authentication, billing, and quota management. Direct use of these
classes bypasses the subscription model and is not supported.

Use codeshift.migrator.LLMMigrator for migrations instead.
"""

import os
from dataclasses import dataclass

from anthropic import Anthropic

# Explicitly mark nothing as public - this is an internal module
__all__: list[str] = []


@dataclass
class _LLMResponse:
    """Response from the LLM.

    WARNING: Internal class. Do not use directly.
    """

    content: str
    model: str
    usage: dict
    success: bool
    error: str | None = None


class _LLMClient:
    """Client for interacting with Anthropic's Claude API.

    WARNING: Internal class. Do not use directly.

    All LLM access should go through the Codeshift API via LLMMigrator.
    Direct instantiation of this class bypasses authentication and billing.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        """Initialize the LLM client.

        WARNING: Internal method. Do not call directly.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            model: Model to use. Defaults to claude-sonnet-4-20250514.
        """
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
    ) -> _LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 for deterministic)

        Returns:
            _LLMResponse with the generated content
        """
        if not self.is_available:
            return _LLMResponse(
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

            return _LLMResponse(
                content=content,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                success=True,
            )

        except Exception as e:
            return _LLMResponse(
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
    ) -> _LLMResponse:
        """Use the LLM to migrate code.

        Args:
            code: The source code to migrate
            library: The library being upgraded
            from_version: Current version
            to_version: Target version
            context: Optional context about the migration

        Returns:
            _LLMResponse with the migrated code
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
    ) -> _LLMResponse:
        """Use the LLM to explain a migration change.

        Args:
            original: Original code
            transformed: Transformed code
            library: The library being upgraded

        Returns:
            _LLMResponse with the explanation
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


# Singleton instance for convenience (internal use only)
_default_client: _LLMClient | None = None


def _get_llm_client() -> _LLMClient:
    """Get the default LLM client instance.

    WARNING: Internal function. Do not call directly.

    All LLM access should go through the Codeshift API via LLMMigrator.
    """
    global _default_client
    if _default_client is None:
        _default_client = _LLMClient()
    return _default_client

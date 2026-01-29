"""Codeshift API client for LLM-powered migrations.

This client calls the Codeshift API instead of Anthropic directly,
ensuring that LLM features are gated behind the subscription model.
"""

from dataclasses import dataclass

import httpx

from codeshift.cli.commands.auth import (
    get_api_key,
    get_api_url,
    validate_api_url,
)


@dataclass
class APIResponse:
    """Response from the Codeshift API."""

    success: bool
    content: str
    error: str | None = None
    usage: dict | None = None
    cached: bool = False


class CodeshiftAPIClient:
    """Client for interacting with the Codeshift API for LLM migrations.

    This client routes all LLM calls through the Codeshift API,
    which handles:
    - Authentication and authorization
    - Quota checking and billing
    - Server-side Anthropic API calls
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: int = 180,
        verify_ssl: bool = True,
    ):
        """Initialize the API client.

        Args:
            api_key: Codeshift API key. Defaults to stored credentials.
            api_url: API base URL. Defaults to stored URL.
            timeout: Request timeout in seconds (default 180 for LLM calls).
            verify_ssl: Whether to verify SSL certificates. Defaults to True.
                       Only set to False for testing with self-signed certificates.

        Raises:
            codeshift.cli.commands.auth.InsecureURLError: If the URL uses HTTP
                for non-local hosts.
            ValueError: If the URL format is invalid.
        """
        self.api_key = api_key or get_api_key()

        # Validate the API URL for security
        raw_url = api_url or get_api_url()
        self.api_url = self._validate_url(raw_url)

        self.timeout = timeout
        self.verify_ssl = verify_ssl

        # Warn if SSL verification is disabled
        if not verify_ssl:
            import logging

            logging.getLogger(__name__).warning(
                "SSL certificate verification is disabled. "
                "This is insecure and should only be used for testing."
            )

    def _validate_url(self, url: str) -> str:
        """Validate that the URL is secure and properly formatted.

        Args:
            url: The URL to validate.

        Returns:
            The validated URL.

        Raises:
            codeshift.cli.commands.auth.InsecureURLError: If HTTP is used
                for non-local hosts.
            ValueError: If the URL format is invalid.
        """
        # Use the shared validation function from auth module
        return validate_api_url(url)

    @property
    def is_available(self) -> bool:
        """Check if the API client is available (has API key)."""
        return bool(self.api_key)

    def _make_request(
        self,
        endpoint: str,
        payload: dict,
    ) -> httpx.Response:
        """Make a request to the API.

        Args:
            endpoint: API endpoint (e.g., '/migrate/code')
            payload: Request payload

        Returns:
            HTTP response

        Raises:
            httpx.RequestError: On network errors
        """
        if not self.api_key:
            raise ValueError("API key not configured. Run 'codeshift login' to authenticate.")

        return httpx.post(
            f"{self.api_url}{endpoint}",
            headers={"X-API-Key": self.api_key},
            json=payload,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )

    def migrate_code(
        self,
        code: str,
        library: str,
        from_version: str,
        to_version: str,
        context: str | None = None,
    ) -> APIResponse:
        """Migrate code using the Codeshift API.

        Args:
            code: Source code to migrate
            library: Library being upgraded
            from_version: Current version
            to_version: Target version
            context: Optional context about the migration

        Returns:
            APIResponse with the migrated code
        """
        if not self.is_available:
            return APIResponse(
                success=False,
                content=code,
                error="Not authenticated. Run 'codeshift login' to use LLM migrations.",
            )

        try:
            response = self._make_request(
                "/migrate/code",
                {
                    "code": code,
                    "library": library,
                    "from_version": from_version,
                    "to_version": to_version,
                    "context": context,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return APIResponse(
                    success=data.get("success", False),
                    content=data.get("migrated_code", code),
                    error=data.get("error"),
                    usage=data.get("usage"),
                    cached=data.get("cached", False),
                )

            elif response.status_code == 401:
                return APIResponse(
                    success=False,
                    content=code,
                    error="Authentication failed. Run 'codeshift login' to re-authenticate.",
                )

            elif response.status_code == 402:
                data = response.json()
                detail = data.get("detail", {})
                return APIResponse(
                    success=False,
                    content=code,
                    error=(
                        f"LLM quota exceeded. Current usage: {detail.get('current_usage', '?')}, "
                        f"Limit: {detail.get('limit', '?')}. "
                        f"Upgrade at {detail.get('upgrade_url', 'https://codeshift.dev/pricing')}"
                    ),
                )

            elif response.status_code == 403:
                return APIResponse(
                    success=False,
                    content=code,
                    error="LLM migrations require Pro tier or higher. Run 'codeshift upgrade-plan' to upgrade.",
                )

            elif response.status_code == 503:
                return APIResponse(
                    success=False,
                    content=code,
                    error="LLM service temporarily unavailable. Please try again later.",
                )

            else:
                return APIResponse(
                    success=False,
                    content=code,
                    error=f"API error: {response.status_code}",
                )

        except httpx.RequestError as e:
            return APIResponse(
                success=False,
                content=code,
                error=f"Network error: {str(e)}",
            )

    def explain_change(
        self,
        original: str,
        transformed: str,
        library: str,
    ) -> APIResponse:
        """Get an explanation of a migration change.

        Args:
            original: Original code
            transformed: Transformed code
            library: Library being upgraded

        Returns:
            APIResponse with the explanation
        """
        if not self.is_available:
            return APIResponse(
                success=False,
                content="",
                error="Not authenticated. Run 'codeshift login' to use this feature.",
            )

        try:
            response = self._make_request(
                "/migrate/explain",
                {
                    "original_code": original,
                    "transformed_code": transformed,
                    "library": library,
                },
            )

            if response.status_code == 200:
                data = response.json()
                return APIResponse(
                    success=data.get("success", False),
                    content=data.get("explanation", ""),
                    error=data.get("error"),
                )

            elif response.status_code == 402:
                return APIResponse(
                    success=False,
                    content="",
                    error="LLM quota exceeded. Upgrade your plan to continue.",
                )

            elif response.status_code == 403:
                return APIResponse(
                    success=False,
                    content="",
                    error="This feature requires Pro tier or higher.",
                )

            else:
                return APIResponse(
                    success=False,
                    content="",
                    error=f"API error: {response.status_code}",
                )

        except httpx.RequestError as e:
            return APIResponse(
                success=False,
                content="",
                error=f"Network error: {str(e)}",
            )


# Singleton instance
_default_client: CodeshiftAPIClient | None = None


def get_api_client() -> CodeshiftAPIClient:
    """Get the default API client instance."""
    global _default_client
    if _default_client is None:
        _default_client = CodeshiftAPIClient()
    return _default_client


def reset_api_client() -> None:
    """Reset the API client (useful after login/logout)."""
    global _default_client
    _default_client = None

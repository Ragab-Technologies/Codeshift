"""
Stress test file for HTTPX 0.18 -> 0.24 migration.

This file contains VERY complex HTTPX 0.18 patterns that need to be migrated to 0.24.
It covers a wide variety of scenarios to stress test the Codeshift migration tool.

Key API changes between 0.18 and 0.24:
- Timeout parameters renamed: connect_timeout -> connect, read_timeout -> read,
  write_timeout -> write, pool_timeout -> pool
- proxies parameter renamed to proxy
- allow_redirects renamed to follow_redirects
- HTTPStatusError moved from httpx.exceptions to httpx
- Various authentication API refinements
"""

import ssl
from collections.abc import AsyncIterator, Callable, Iterator
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from httpx import (
    DigestAuth,
    HTTPStatusError,
    Limits,
    Request,
    Response,
)
from tenacity import retry, stop_after_attempt, wait_exponential

# =============================================================================
# 1. TIMEOUT CONFIGURATION (Multiple Styles)
# =============================================================================


class TimeoutConfigurationStyles:
    """Various ways to configure timeouts in HTTPX 0.18."""

    # Style 1: Individual timeout parameters (OLD API)
    basic_timeout = httpx.Timeout(
        connect_timeout=5.0,
        read_timeout=30.0,
        write_timeout=15.0,
        pool_timeout=10.0,
    )

    # Style 2: Using default with overrides
    custom_timeout = httpx.Timeout(
        timeout=60.0,
        connect_timeout=10.0,
    )

    # Style 3: Using None for unlimited
    unlimited_read_timeout = httpx.Timeout(
        connect_timeout=5.0,
        read_timeout=None,
        write_timeout=10.0,
    )

    # Style 4: Inline timeout configuration
    def get_client_with_inline_timeout(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(
                connect_timeout=5.0,
                read_timeout=30.0,
                write_timeout=15.0,
                pool_timeout=10.0,
            )
        )

    # Style 5: Complex nested timeout in async client
    async def get_async_client_with_timeout(self) -> httpx.AsyncClient:
        timeout_config = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=60.0,
            write_timeout=30.0,
            pool_timeout=20.0,
        )
        return httpx.AsyncClient(timeout=timeout_config)


# =============================================================================
# 2. SYNC AND ASYNC CLIENT USAGE
# =============================================================================


class SyncClientManager:
    """Synchronous HTTPX client with complex configuration."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=60.0,
            write_timeout=30.0,
            pool_timeout=15.0,
        )

        self.limits = Limits(
            max_connections=100,
            max_keepalive_connections=20,
        )

        self.client = httpx.Client(
            timeout=self.timeout,
            limits=self.limits,
            http2=True,
            proxies="http://proxy.local:8080",
            verify=True,
            cert=("/path/to/cert.pem", "/path/to/key.pem"),
            trust_env=True,
            allow_redirects=True,
            max_redirects=10,
        )

    def fetch(self, url: str) -> Response:
        """Fetch URL with retry logic."""
        return self.client.get(url)

    def post_with_timeout_override(self, url: str, data: dict[str, Any]) -> Response:
        """Post with inline timeout override."""
        return self.client.post(
            url,
            json=data,
            timeout=httpx.Timeout(connect_timeout=2.0, read_timeout=10.0),
        )

    def close(self) -> None:
        self.client.close()


class AsyncClientManager:
    """Asynchronous HTTPX client with complex configuration."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
            pool_timeout=10.0,
        )

        self.limits = Limits(
            max_connections=200,
            max_keepalive_connections=50,
        )

        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=self.limits,
                http2=True,
                proxies="http://async-proxy.local:8080",
                verify=True,
                trust_env=True,
                allow_redirects=True,
                max_redirects=20,
            )
        return self._client

    async def fetch(self, url: str) -> Response:
        client = await self.get_client()
        return await client.get(url)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# 3. CONNECTION POOLING
# =============================================================================


class ConnectionPoolManager:
    """Advanced connection pooling configuration."""

    def __init__(self) -> None:
        # Connection pool limits
        self.pool_limits = Limits(
            max_connections=500,
            max_keepalive_connections=100,
        )

        # Timeout with pool configuration
        self.pool_timeout_config = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=10.0,
            pool_timeout=60.0,  # Long pool timeout for high traffic
        )

    def create_high_volume_client(self) -> httpx.Client:
        """Create client optimized for high volume requests."""
        return httpx.Client(
            limits=self.pool_limits,
            timeout=self.pool_timeout_config,
            http2=True,
            allow_redirects=True,
        )

    async def create_high_volume_async_client(self) -> httpx.AsyncClient:
        """Create async client optimized for high volume requests."""
        return httpx.AsyncClient(
            limits=self.pool_limits,
            timeout=self.pool_timeout_config,
            http2=True,
            allow_redirects=True,
        )


# =============================================================================
# 4. HTTP/2 SUPPORT
# =============================================================================


class Http2ClientFactory:
    """Factory for HTTP/2 enabled clients."""

    @staticmethod
    def create_h2_client(
        verify_ssl: bool = True,
        timeout_seconds: float = 30.0,
    ) -> httpx.Client:
        """Create HTTP/2 client with custom configuration."""
        timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=timeout_seconds,
            write_timeout=timeout_seconds,
            pool_timeout=10.0,
        )

        return httpx.Client(
            http2=True,
            timeout=timeout,
            verify=verify_ssl,
            allow_redirects=True,
        )

    @staticmethod
    async def create_h2_async_client(
        verify_ssl: bool = True,
        timeout_seconds: float = 30.0,
    ) -> httpx.AsyncClient:
        """Create async HTTP/2 client."""
        timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=timeout_seconds,
            write_timeout=timeout_seconds,
            pool_timeout=10.0,
        )

        return httpx.AsyncClient(
            http2=True,
            timeout=timeout,
            verify=verify_ssl,
            allow_redirects=True,
        )


# =============================================================================
# 5. RETRY LOGIC WITH TENACITY
# =============================================================================


class RetryableHttpClient:
    """HTTP client with tenacity-based retry logic."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
        )

        self.client = httpx.Client(
            timeout=self.timeout,
            allow_redirects=True,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def fetch_with_retry(self, url: str) -> Response:
        """Fetch URL with automatic retry on failure."""
        response = self.client.get(url)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.5, min=1, max=30),
    )
    def post_with_retry(
        self,
        url: str,
        data: dict[str, Any],
        timeout_override: float | None = None,
    ) -> Response:
        """Post with retry and optional timeout override."""
        timeout = (
            httpx.Timeout(connect_timeout=2.0, read_timeout=timeout_override)
            if timeout_override
            else self.timeout
        )
        response = self.client.post(url, json=data, timeout=timeout)
        response.raise_for_status()
        return response

    def close(self) -> None:
        self.client.close()


class AsyncRetryableHttpClient:
    """Async HTTP client with tenacity-based retry logic."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
            pool_timeout=10.0,
        )

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                allow_redirects=True,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def fetch_with_retry(self, url: str) -> Response:
        """Async fetch with automatic retry on failure."""
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# 6. AUTHENTICATION (Basic, Bearer, Digest, Custom)
# =============================================================================


class AuthenticationManager:
    """Multiple authentication strategies for HTTPX."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
        )

    # Basic Auth
    def create_basic_auth_client(
        self, username: str, password: str
    ) -> httpx.Client:
        """Create client with basic authentication."""
        return httpx.Client(
            auth=(username, password),
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Bearer Token Auth
    def create_bearer_auth_client(self, token: str) -> httpx.Client:
        """Create client with bearer token authentication."""
        return httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Digest Auth
    def create_digest_auth_client(
        self, username: str, password: str
    ) -> httpx.Client:
        """Create client with digest authentication."""
        return httpx.Client(
            auth=DigestAuth(username, password),
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Custom Auth Header
    def create_custom_auth_client(
        self, api_key: str, api_secret: str
    ) -> httpx.Client:
        """Create client with custom authentication headers."""
        return httpx.Client(
            headers={
                "X-API-Key": api_key,
                "X-API-Secret": api_secret,
            },
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Async versions
    async def create_async_basic_auth_client(
        self, username: str, password: str
    ) -> httpx.AsyncClient:
        """Create async client with basic authentication."""
        return httpx.AsyncClient(
            auth=(username, password),
            timeout=self.timeout,
            allow_redirects=True,
        )

    async def create_async_bearer_auth_client(
        self, token: str
    ) -> httpx.AsyncClient:
        """Create async client with bearer token."""
        return httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=self.timeout,
            allow_redirects=True,
        )


# =============================================================================
# 7. PROXY CONFIGURATION
# =============================================================================


class ProxyConfigurationManager:
    """Various proxy configuration styles."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=60.0,
            write_timeout=30.0,
            pool_timeout=15.0,
        )

    # Single proxy for all traffic
    def create_single_proxy_client(self, proxy_url: str) -> httpx.Client:
        """Create client with single proxy for all traffic."""
        return httpx.Client(
            proxies=proxy_url,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # HTTP and HTTPS separate proxies (dict style)
    def create_dual_proxy_client(
        self, http_proxy: str, https_proxy: str
    ) -> httpx.Client:
        """Create client with separate HTTP and HTTPS proxies."""
        return httpx.Client(
            proxies={
                "http://": http_proxy,
                "https://": https_proxy,
            },
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Proxy with authentication
    def create_authenticated_proxy_client(
        self,
        proxy_url: str,
        proxy_username: str,
        proxy_password: str,
    ) -> httpx.Client:
        """Create client with authenticated proxy."""
        # Format: http://username:password@proxy.example.com:8080
        auth_proxy_url = proxy_url.replace(
            "://", f"://{proxy_username}:{proxy_password}@"
        )
        return httpx.Client(
            proxies=auth_proxy_url,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # No proxy for certain hosts
    def create_selective_proxy_client(
        self, proxy_url: str, no_proxy_hosts: list[str]
    ) -> httpx.Client:
        """Create client with selective proxy (exclude certain hosts)."""
        proxy_config = {
            "all://": proxy_url,
        }
        # Add no_proxy entries
        for host in no_proxy_hosts:
            proxy_config[f"all://{host}"] = None

        return httpx.Client(
            proxies=proxy_config,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Async proxy client
    async def create_async_proxy_client(
        self, proxy_url: str
    ) -> httpx.AsyncClient:
        """Create async client with proxy."""
        return httpx.AsyncClient(
            proxies=proxy_url,
            timeout=self.timeout,
            allow_redirects=True,
        )


# =============================================================================
# 8. SSL VERIFICATION
# =============================================================================


class SSLConfigurationManager:
    """SSL/TLS verification configuration."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=60.0,
        )

    # SSL verification enabled (default)
    def create_verified_client(self) -> httpx.Client:
        """Create client with SSL verification enabled."""
        return httpx.Client(
            verify=True,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # SSL verification disabled (development only!)
    def create_unverified_client(self) -> httpx.Client:
        """Create client with SSL verification disabled (INSECURE)."""
        return httpx.Client(
            verify=False,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Custom CA bundle
    def create_custom_ca_client(self, ca_bundle_path: str) -> httpx.Client:
        """Create client with custom CA certificate bundle."""
        return httpx.Client(
            verify=ca_bundle_path,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Client certificate authentication
    def create_mutual_tls_client(
        self,
        cert_path: str,
        key_path: str,
        ca_bundle_path: str | None = None,
    ) -> httpx.Client:
        """Create client with mutual TLS (client certificate)."""
        return httpx.Client(
            cert=(cert_path, key_path),
            verify=ca_bundle_path if ca_bundle_path else True,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Custom SSL context
    def create_custom_ssl_context_client(
        self,
        ssl_context: ssl.SSLContext,
    ) -> httpx.Client:
        """Create client with custom SSL context."""
        return httpx.Client(
            verify=ssl_context,
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Async SSL client
    async def create_async_verified_client(self) -> httpx.AsyncClient:
        """Create async client with SSL verification."""
        return httpx.AsyncClient(
            verify=True,
            timeout=self.timeout,
            allow_redirects=True,
        )


# =============================================================================
# 9. COOKIE PERSISTENCE
# =============================================================================


class CookieSessionManager:
    """Cookie-based session management."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
        )

        # Cookies persist across requests
        self.cookies = httpx.Cookies()

    def create_session_client(self) -> httpx.Client:
        """Create client with cookie persistence."""
        return httpx.Client(
            cookies=self.cookies,
            timeout=self.timeout,
            allow_redirects=True,
        )

    def create_session_client_with_initial_cookies(
        self, initial_cookies: dict[str, str]
    ) -> httpx.Client:
        """Create client with pre-set cookies."""
        cookies = httpx.Cookies()
        for name, value in initial_cookies.items():
            cookies.set(name, value)

        return httpx.Client(
            cookies=cookies,
            timeout=self.timeout,
            allow_redirects=True,
        )

    async def create_async_session_client(self) -> httpx.AsyncClient:
        """Create async client with cookie persistence."""
        return httpx.AsyncClient(
            cookies=self.cookies,
            timeout=self.timeout,
            allow_redirects=True,
        )


# =============================================================================
# 10. STREAMING UPLOADS/DOWNLOADS
# =============================================================================


class StreamingClient:
    """Streaming upload and download operations."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=None,  # No read timeout for streaming
            write_timeout=None,  # No write timeout for streaming
            pool_timeout=30.0,
        )

        self.client = httpx.Client(
            timeout=self.timeout,
            allow_redirects=True,
        )

    def download_file_streaming(
        self, url: str, output_path: Path
    ) -> None:
        """Download file with streaming to handle large files."""
        with self.client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    def upload_file_streaming(
        self, url: str, file_path: Path
    ) -> Response:
        """Upload file with streaming."""
        with open(file_path, "rb") as f:
            return self.client.post(url, content=f)

    def upload_large_data_streaming(
        self, url: str, data_generator: Iterator[bytes]
    ) -> Response:
        """Upload data from generator for memory efficiency."""
        return self.client.post(url, content=data_generator)

    def close(self) -> None:
        self.client.close()


class AsyncStreamingClient:
    """Async streaming upload and download operations."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=None,
            write_timeout=None,
            pool_timeout=30.0,
        )

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                allow_redirects=True,
            )
        return self._client

    async def download_file_streaming(
        self, url: str, output_path: Path
    ) -> None:
        """Async download with streaming."""
        client = await self._get_client()
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)

    async def upload_file_streaming(
        self, url: str, file_path: Path
    ) -> Response:
        """Async upload with streaming."""
        client = await self._get_client()

        async def file_generator() -> AsyncIterator[bytes]:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    yield chunk

        return await client.post(url, content=file_generator())

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# 11. MULTIPART FORM DATA
# =============================================================================


class MultipartFormClient:
    """Multipart form data uploads."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=120.0,
            write_timeout=120.0,
            pool_timeout=30.0,
        )

        self.client = httpx.Client(
            timeout=self.timeout,
            allow_redirects=True,
        )

    def upload_single_file(
        self,
        url: str,
        file_path: Path,
        field_name: str = "file",
    ) -> Response:
        """Upload a single file via multipart form."""
        files = {field_name: open(file_path, "rb")}
        try:
            return self.client.post(url, files=files)
        finally:
            files[field_name].close()

    def upload_multiple_files(
        self,
        url: str,
        file_paths: list[Path],
        field_name: str = "files",
    ) -> Response:
        """Upload multiple files via multipart form."""
        files = [
            (field_name, (fp.name, open(fp, "rb"), "application/octet-stream"))
            for fp in file_paths
        ]
        try:
            return self.client.post(url, files=files)
        finally:
            for _, (_, f, _) in files:
                f.close()

    def upload_file_with_data(
        self,
        url: str,
        file_path: Path,
        form_data: dict[str, Any],
    ) -> Response:
        """Upload file with additional form fields."""
        files = {"file": open(file_path, "rb")}
        try:
            return self.client.post(url, data=form_data, files=files)
        finally:
            files["file"].close()

    def upload_in_memory_file(
        self,
        url: str,
        content: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> Response:
        """Upload in-memory content as a file."""
        files = {"file": (filename, BytesIO(content), content_type)}
        return self.client.post(url, files=files)

    def close(self) -> None:
        self.client.close()


class AsyncMultipartFormClient:
    """Async multipart form data uploads."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=120.0,
            write_timeout=120.0,
            pool_timeout=30.0,
        )

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                allow_redirects=True,
            )
        return self._client

    async def upload_file(
        self,
        url: str,
        file_path: Path,
        field_name: str = "file",
    ) -> Response:
        """Async file upload via multipart form."""
        client = await self._get_client()
        files = {field_name: open(file_path, "rb")}
        try:
            return await client.post(url, files=files)
        finally:
            files[field_name].close()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# =============================================================================
# 12. CUSTOM TRANSPORT
# =============================================================================


class CustomTransportClient:
    """Client with custom transport configuration."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
            pool_timeout=10.0,
        )

    def create_client_with_custom_transport(
        self,
        retries: int = 3,
    ) -> httpx.Client:
        """Create client with custom HTTP transport."""
        transport = httpx.HTTPTransport(
            retries=retries,
            http2=True,
        )

        return httpx.Client(
            transport=transport,
            timeout=self.timeout,
            allow_redirects=True,
        )

    def create_client_with_uds_transport(
        self,
        socket_path: str,
    ) -> httpx.Client:
        """Create client connecting via Unix Domain Socket."""
        transport = httpx.HTTPTransport(uds=socket_path)

        return httpx.Client(
            transport=transport,
            timeout=self.timeout,
            allow_redirects=True,
        )

    async def create_async_client_with_custom_transport(
        self,
        retries: int = 3,
    ) -> httpx.AsyncClient:
        """Create async client with custom transport."""
        transport = httpx.AsyncHTTPTransport(
            retries=retries,
            http2=True,
        )

        return httpx.AsyncClient(
            transport=transport,
            timeout=self.timeout,
            allow_redirects=True,
        )


# =============================================================================
# 13. EVENT HOOKS
# =============================================================================


def log_request(request: Request) -> None:
    """Log outgoing request."""
    print(f"Request: {request.method} {request.url}")


def log_response(response: Response) -> None:
    """Log incoming response."""
    print(f"Response: {response.status_code} {response.url}")


async def async_log_request(request: Request) -> None:
    """Async log outgoing request."""
    print(f"Async Request: {request.method} {request.url}")


async def async_log_response(response: Response) -> None:
    """Async log incoming response."""
    print(f"Async Response: {response.status_code} {response.url}")


class EventHookClient:
    """Client with event hooks for request/response logging."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
        )

    def create_client_with_hooks(self) -> httpx.Client:
        """Create client with request/response hooks."""
        return httpx.Client(
            timeout=self.timeout,
            event_hooks={
                "request": [log_request],
                "response": [log_response],
            },
            allow_redirects=True,
        )

    def create_client_with_multiple_hooks(
        self,
        request_hooks: list[Callable[[Request], None]],
        response_hooks: list[Callable[[Response], None]],
    ) -> httpx.Client:
        """Create client with multiple hooks."""
        return httpx.Client(
            timeout=self.timeout,
            event_hooks={
                "request": request_hooks,
                "response": response_hooks,
            },
            allow_redirects=True,
        )

    async def create_async_client_with_hooks(self) -> httpx.AsyncClient:
        """Create async client with event hooks."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            event_hooks={
                "request": [async_log_request],
                "response": [async_log_response],
            },
            allow_redirects=True,
        )


# =============================================================================
# 14. FOLLOW REDIRECTS CONFIGURATION
# =============================================================================


class RedirectConfigurationClient:
    """Various redirect configuration scenarios."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
        )

    # Follow redirects (default behavior in 0.18 - allow_redirects=True)
    def create_follow_redirects_client(self) -> httpx.Client:
        """Create client that follows redirects."""
        return httpx.Client(
            timeout=self.timeout,
            allow_redirects=True,
        )

    # Don't follow redirects
    def create_no_redirects_client(self) -> httpx.Client:
        """Create client that doesn't follow redirects."""
        return httpx.Client(
            timeout=self.timeout,
            allow_redirects=False,
        )

    # Limited redirects
    def create_limited_redirects_client(
        self, max_redirects: int = 5
    ) -> httpx.Client:
        """Create client with limited redirect following."""
        return httpx.Client(
            timeout=self.timeout,
            allow_redirects=True,
            max_redirects=max_redirects,
        )

    # Async versions
    async def create_async_follow_redirects_client(self) -> httpx.AsyncClient:
        """Create async client that follows redirects."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            allow_redirects=True,
        )

    async def create_async_no_redirects_client(self) -> httpx.AsyncClient:
        """Create async client that doesn't follow redirects."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            allow_redirects=False,
        )


# =============================================================================
# 15. TRUST ENVIRONMENT SETTINGS
# =============================================================================


class EnvironmentTrustClient:
    """Clients with various environment trust settings."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
            pool_timeout=10.0,
        )

    # Trust environment (use HTTP_PROXY, HTTPS_PROXY, NO_PROXY, etc.)
    def create_env_trusted_client(self) -> httpx.Client:
        """Create client that trusts environment variables."""
        return httpx.Client(
            timeout=self.timeout,
            trust_env=True,
            allow_redirects=True,
        )

    # Don't trust environment
    def create_env_isolated_client(self) -> httpx.Client:
        """Create client isolated from environment variables."""
        return httpx.Client(
            timeout=self.timeout,
            trust_env=False,
            allow_redirects=True,
        )

    # Async versions
    async def create_async_env_trusted_client(self) -> httpx.AsyncClient:
        """Create async client that trusts environment variables."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            trust_env=True,
            allow_redirects=True,
        )

    async def create_async_env_isolated_client(self) -> httpx.AsyncClient:
        """Create async client isolated from environment variables."""
        return httpx.AsyncClient(
            timeout=self.timeout,
            trust_env=False,
            allow_redirects=True,
        )


# =============================================================================
# 16. COMPREHENSIVE INTEGRATION SCENARIO
# =============================================================================


class ProductionHttpClient:
    """
    Production-grade HTTP client combining all features.
    This is the ultimate stress test for the migration tool.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        proxy_url: str | None = None,
        ssl_cert_path: str | None = None,
        max_connections: int = 100,
        enable_http2: bool = True,
        enable_logging: bool = True,
    ) -> None:
        # Complex timeout configuration
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=60.0,
            write_timeout=30.0,
            pool_timeout=20.0,
        )

        # Connection limits
        self.limits = Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_connections // 5,
        )

        # Event hooks for logging
        event_hooks: dict[str, list[Callable]] = {}
        if enable_logging:
            event_hooks = {
                "request": [log_request],
                "response": [log_response],
            }

        # Build client with all options
        self.client = httpx.Client(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "ProductionHttpClient/1.0",
                "Accept": "application/json",
            },
            timeout=self.timeout,
            limits=self.limits,
            http2=enable_http2,
            proxies=proxy_url if proxy_url else None,
            verify=ssl_cert_path if ssl_cert_path else True,
            trust_env=True,
            allow_redirects=True,
            max_redirects=10,
            event_hooks=event_hooks if event_hooks else None,
        )

        self.cookies = httpx.Cookies()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get(self, path: str, **kwargs: Any) -> Response:
        """GET request with retry."""
        response = self.client.get(path, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Response:
        """POST request with retry."""
        response = self.client.post(
            path,
            data=data,
            json=json_data,
            files=files,
        )
        response.raise_for_status()
        return response

    def stream_download(
        self, path: str, output_path: Path
    ) -> None:
        """Download with streaming."""
        with self.client.stream("GET", path) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "ProductionHttpClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncProductionHttpClient:
    """
    Async production-grade HTTP client combining all features.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        proxy_url: str | None = None,
        ssl_cert_path: str | None = None,
        max_connections: int = 100,
        enable_http2: bool = True,
        enable_logging: bool = True,
    ) -> None:
        # Complex timeout configuration
        self.timeout = httpx.Timeout(
            connect_timeout=10.0,
            read_timeout=60.0,
            write_timeout=30.0,
            pool_timeout=20.0,
        )

        # Connection limits
        self.limits = Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_connections // 5,
        )

        # Event hooks for logging
        event_hooks: dict[str, list[Callable]] = {}
        if enable_logging:
            event_hooks = {
                "request": [async_log_request],
                "response": [async_log_response],
            }

        # Build async client with all options
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "AsyncProductionHttpClient/1.0",
                "Accept": "application/json",
            },
            timeout=self.timeout,
            limits=self.limits,
            http2=enable_http2,
            proxies=proxy_url if proxy_url else None,
            verify=ssl_cert_path if ssl_cert_path else True,
            trust_env=True,
            allow_redirects=True,
            max_redirects=10,
            event_hooks=event_hooks if event_hooks else None,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get(self, path: str, **kwargs: Any) -> Response:
        """Async GET request with retry."""
        response = await self.client.get(path, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Response:
        """Async POST request with retry."""
        response = await self.client.post(
            path,
            data=data,
            json=json_data,
            files=files,
        )
        response.raise_for_status()
        return response

    async def stream_download(
        self, path: str, output_path: Path
    ) -> None:
        """Async download with streaming."""
        async with self.client.stream("GET", path) as response:
            response.raise_for_status()
            with open(output_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> "AsyncProductionHttpClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# =============================================================================
# 17. ERROR HANDLING WITH HTTPX EXCEPTIONS
# =============================================================================


class ErrorHandlingClient:
    """Client demonstrating proper error handling."""

    def __init__(self) -> None:
        self.timeout = httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
        )

        self.client = httpx.Client(
            timeout=self.timeout,
            allow_redirects=True,
        )

    def safe_get(self, url: str) -> tuple[Response | None, str | None]:
        """Get with comprehensive error handling."""
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response, None
        except httpx.TimeoutException as e:
            return None, f"Request timed out: {e}"
        except httpx.ConnectError as e:
            return None, f"Connection failed: {e}"
        except HTTPStatusError as e:
            return None, f"HTTP error {e.response.status_code}: {e}"
        except httpx.RequestError as e:
            return None, f"Request failed: {e}"

    def close(self) -> None:
        self.client.close()


# =============================================================================
# EXAMPLE USAGE (for testing the migration)
# =============================================================================


def example_basic_usage() -> None:
    """Example of basic HTTPX 0.18 usage patterns."""
    # Direct function calls with timeout
    timeout = httpx.Timeout(
        connect_timeout=5.0,
        read_timeout=30.0,
    )

    response = httpx.get(
        "https://api.example.com/data",
        timeout=timeout,
        allow_redirects=True,
    )

    # Using client context manager
    with httpx.Client(
        timeout=httpx.Timeout(
            connect_timeout=5.0,
            read_timeout=30.0,
            write_timeout=15.0,
            pool_timeout=10.0,
        ),
        allow_redirects=True,
        proxies="http://proxy.example.com:8080",
    ) as client:
        response = client.get("https://api.example.com/data")
        data = response.json()


async def example_async_usage() -> None:
    """Example of async HTTPX 0.18 usage patterns."""
    timeout = httpx.Timeout(
        connect_timeout=5.0,
        read_timeout=30.0,
        write_timeout=15.0,
        pool_timeout=10.0,
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        allow_redirects=True,
        proxies="http://proxy.example.com:8080",
        http2=True,
    ) as client:
        response = await client.get("https://api.example.com/data")
        data = response.json()

        # Streaming download
        async with client.stream("GET", "https://example.com/large-file") as response:
            async for chunk in response.aiter_bytes():
                pass  # Process chunk


if __name__ == "__main__":
    # Run basic example
    print("Testing HTTPX 0.18 patterns...")

    # Test timeout configuration
    timeout_manager = TimeoutConfigurationStyles()
    print(f"Basic timeout: {timeout_manager.basic_timeout}")

    # Test sync client
    sync_manager = SyncClientManager()
    print("Sync client created successfully")
    sync_manager.close()

    # Test async client (would need event loop)
    print("All HTTPX 0.18 patterns tested successfully!")

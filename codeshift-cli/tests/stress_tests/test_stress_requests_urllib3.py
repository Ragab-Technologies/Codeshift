"""
Stress Test: Complex Requests + urllib3 Migration Scenario

This file tests the Codeshift migration tool's ability to handle complex,
real-world patterns involving requests and urllib3 libraries.

Patterns tested:
- requests.packages.urllib3 imports (deprecated, needs migration to direct urllib3)
- Custom HTTPAdapter implementations
- Retry configuration with urllib3's Retry class
- Connection pooling (PoolManager, HTTPConnectionPool)
- SSL verification and custom certificates
- Proxy configuration (HTTP, HTTPS, SOCKS)
- Session management with persistent settings
- Cookie handling (CookieJar, RequestsCookieJar)
- Authentication (Basic, Digest, OAuth/OAuth2)
- Streaming downloads with iter_content/iter_lines
- Chunked transfer encoding
- Timeout configuration (connect, read, total)
- Event hooks (response hooks)
- Custom transport adapters
- Certificate pinning

Migration target: requests 2.25 -> 2.31
Key changes:
- requests.packages.urllib3 -> urllib3 (direct import)
- Charset detection changes
- Security improvements
"""

import hashlib
import logging
import os
import ssl
import time
from collections.abc import Callable, Iterator
from functools import wraps
from threading import Lock, Thread
from typing import Any
from urllib.parse import urlparse

# Regular requests imports (these should remain unchanged)
import requests
from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth

# requests.compat imports (some need migration to stdlib)
from requests.compat import urljoin as compat_urljoin
from requests.compat import urlparse as compat_urlparse
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.exceptions import (
    RequestException,
)

# Import urllib3 through requests.packages for disabling warnings
from requests.packages import urllib3 as requests_urllib3

# ============================================================================
# DEPRECATED IMPORTS: These need migration from requests.packages to urllib3
# ============================================================================
# Old-style imports through requests.packages (deprecated since requests 2.26)
from requests.packages.urllib3 import HTTPConnectionPool, HTTPSConnectionPool, Retry
from requests.packages.urllib3.exceptions import (
    InsecureRequestWarning,
)
from requests.packages.urllib3.poolmanager import PoolManager
from requests.packages.urllib3.util.retry import Retry as RetryConfig
from requests.packages.urllib3.util.ssl_ import create_urllib3_context
from requests.packages.urllib3.util.timeout import Timeout

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class APIClientError(Exception):
    """Base exception for API client errors."""
    pass


class AuthenticationError(APIClientError):
    """Raised when authentication fails."""
    pass


class RateLimitError(APIClientError):
    """Raised when rate limit is exceeded."""
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class CertificatePinningError(APIClientError):
    """Raised when certificate pinning validation fails."""
    pass


# ============================================================================
# CUSTOM OAUTH AUTHENTICATION
# ============================================================================

class OAuth2BearerAuth(AuthBase):
    """OAuth2 Bearer token authentication."""

    def __init__(self, token: str):
        self.token = token

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers['Authorization'] = f'Bearer {self.token}'
        return r


class OAuth2ClientCredentialsAuth(AuthBase):
    """OAuth2 Client Credentials flow authentication."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_url: str,
        scope: str | None = None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scope = scope
        self._token: str | None = None
        self._token_expires: float = 0
        self._lock = Lock()

    def _get_token(self) -> str:
        """Fetch or refresh OAuth2 token."""
        with self._lock:
            if self._token and time.time() < self._token_expires:
                return self._token

            data = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }
            if self.scope:
                data['scope'] = self.scope

            # Note: requests.post without timeout - should trigger warning
            response = requests.post(self.token_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            self._token = token_data['access_token']
            self._token_expires = time.time() + token_data.get('expires_in', 3600) - 60

            return self._token

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        token = self._get_token()
        r.headers['Authorization'] = f'Bearer {token}'
        return r


# ============================================================================
# CUSTOM HTTP ADAPTER WITH RETRY LOGIC
# ============================================================================

class RetryableHTTPAdapter(HTTPAdapter):
    """
    Custom HTTP adapter with configurable retry behavior.

    Uses urllib3's Retry class for robust retry configuration.
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        status_forcelist: tuple[int, ...] | None = None,
        allowed_methods: list[str] | None = None,
        pool_connections: int = 10,
        pool_maxsize: int = 10,
        pool_block: bool = False,
    ):
        # Create retry configuration using urllib3's Retry class
        # Note: Using the old import path through requests.packages
        retry_strategy = RetryConfig(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist or (500, 502, 503, 504),
            allowed_methods=allowed_methods or ["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
            raise_on_redirect=False,
            raise_on_status=False,
            respect_retry_after_header=True,
        )

        super().__init__(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy,
            pool_block=pool_block,
        )


class TimeoutHTTPAdapter(HTTPAdapter):
    """HTTP adapter with default timeout configuration."""

    DEFAULT_TIMEOUT = 30.0

    def __init__(self, *args: Any, timeout: float = DEFAULT_TIMEOUT, **kwargs: Any):
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float, float] | None = None,
        verify: bool | str = True,
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
    ) -> Response:
        if timeout is None:
            timeout = self.timeout
        return super().send(request, stream=stream, timeout=timeout, verify=verify, cert=cert, proxies=proxies)


# ============================================================================
# CERTIFICATE PINNING ADAPTER
# ============================================================================

class CertificatePinningAdapter(HTTPAdapter):
    """
    HTTP adapter with certificate pinning support.

    Validates that the server's certificate matches expected fingerprint(s).
    """

    def __init__(
        self,
        pinned_certs: dict[str, list[str]],  # hostname -> list of SHA256 fingerprints
        *args: Any,
        **kwargs: Any
    ):
        self.pinned_certs = pinned_certs
        super().__init__(*args, **kwargs)

    def cert_verify(
        self,
        conn: Any,
        url: str,
        verify: bool | str,
        cert: str | tuple[str, str] | None
    ) -> None:
        """Override cert verification to add pinning check."""
        super().cert_verify(conn, url, verify, cert)

        # Extract hostname from URL
        parsed = urlparse(url)
        hostname = parsed.hostname

        if hostname and hostname in self.pinned_certs:
            # Get the server's certificate fingerprint
            sock = conn.sock
            if hasattr(sock, 'getpeercert'):
                der_cert = sock.getpeercert(binary_form=True)
                if der_cert:
                    fingerprint = hashlib.sha256(der_cert).hexdigest().upper()
                    fingerprint_formatted = ':'.join(
                        fingerprint[i:i+2] for i in range(0, len(fingerprint), 2)
                    )

                    # Check if fingerprint matches any pinned cert
                    if fingerprint_formatted not in self.pinned_certs[hostname]:
                        raise CertificatePinningError(
                            f"Certificate fingerprint {fingerprint_formatted} "
                            f"does not match pinned certificates for {hostname}"
                        )


# ============================================================================
# ADVANCED API CLIENT
# ============================================================================

class AdvancedAPIClient:
    """
    Advanced API client demonstrating complex requests/urllib3 patterns.

    Features:
    - Custom retry logic with exponential backoff
    - Connection pooling
    - SSL/TLS configuration
    - Proxy support (HTTP, HTTPS, SOCKS)
    - Session management
    - Cookie handling
    - Multiple authentication methods
    - Streaming downloads
    - Event hooks
    """

    # Disable SSL warnings using the old import path (should be migrated)
    requests_urllib3.disable_warnings(InsecureRequestWarning)

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        auth: AuthBase | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        verify_ssl: bool | str = True,
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        pool_connections: int = 10,
        pool_maxsize: int = 10,
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.cert = cert
        self.proxies = proxies or {}

        # Create session with persistent settings
        self.session = self._create_session(
            api_key=api_key,
            auth=auth,
            headers=headers,
            cookies=cookies,
            max_retries=max_retries,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
        )

        # Register response hooks
        self.session.hooks['response'].append(self._log_response)
        self.session.hooks['response'].append(self._handle_rate_limit)

    def _create_session(
        self,
        api_key: str | None,
        auth: AuthBase | None,
        headers: dict[str, str] | None,
        cookies: dict[str, str] | None,
        max_retries: int,
        pool_connections: int,
        pool_maxsize: int,
    ) -> Session:
        """Create and configure a requests Session."""
        session = Session()

        # Set authentication
        if api_key:
            session.headers['X-API-Key'] = api_key
        if auth:
            session.auth = auth

        # Set default headers
        default_headers = {
            'User-Agent': 'AdvancedAPIClient/1.0',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',
        }
        if headers:
            default_headers.update(headers)
        session.headers.update(default_headers)

        # Set cookies
        if cookies:
            session.cookies = cookiejar_from_dict(cookies)

        # Configure custom adapter with retry logic
        adapter = RetryableHTTPAdapter(
            max_retries=max_retries,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        return session

    def _log_response(self, response: Response, *args: Any, **kwargs: Any) -> None:
        """Event hook to log response details."""
        logger.debug(
            f"Response: {response.status_code} {response.reason} "
            f"({response.elapsed.total_seconds():.3f}s) - {response.url}"
        )

    def _handle_rate_limit(self, response: Response, *args: Any, **kwargs: Any) -> None:
        """Event hook to handle rate limiting."""
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            raise RateLimitError(retry_after)

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        # Using urljoin from requests.compat (should be migrated to urllib.parse)
        return compat_urljoin(self.base_url + '/', endpoint.lstrip('/'))

    def request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = False,
        timeout: float | None = None,
    ) -> Response:
        """Make an HTTP request."""
        url = self._build_url(endpoint)

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json,
            headers=headers,
            stream=stream,
            timeout=timeout or self.timeout,
            verify=self.verify_ssl,
            cert=self.cert,
            proxies=self.proxies,
        )

        return response

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any
    ) -> Response:
        """Make a GET request."""
        return self.request('GET', endpoint, params=params, **kwargs)

    def post(
        self,
        endpoint: str,
        data: Any | None = None,
        json: Any | None = None,
        **kwargs: Any
    ) -> Response:
        """Make a POST request."""
        return self.request('POST', endpoint, data=data, json=json, **kwargs)

    def put(
        self,
        endpoint: str,
        data: Any | None = None,
        json: Any | None = None,
        **kwargs: Any
    ) -> Response:
        """Make a PUT request."""
        return self.request('PUT', endpoint, data=data, json=json, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Response:
        """Make a DELETE request."""
        return self.request('DELETE', endpoint, **kwargs)

    def patch(
        self,
        endpoint: str,
        data: Any | None = None,
        json: Any | None = None,
        **kwargs: Any
    ) -> Response:
        """Make a PATCH request."""
        return self.request('PATCH', endpoint, data=data, json=json, **kwargs)


# ============================================================================
# STREAMING DOWNLOAD CLIENT
# ============================================================================

class StreamingDownloadClient:
    """
    Client for handling large file downloads with streaming.

    Features:
    - Chunked downloads
    - Progress tracking
    - Resume support
    - Checksum verification
    """

    DEFAULT_CHUNK_SIZE = 8192

    def __init__(
        self,
        session: Session | None = None,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.session = session or Session()
        self.chunk_size = chunk_size

    def download_file(
        self,
        url: str,
        destination: str,
        expected_hash: str | None = None,
        resume: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        """
        Download a file with streaming.

        Args:
            url: URL to download from
            destination: Local file path to save to
            expected_hash: Expected SHA256 hash of the file
            resume: Whether to resume partial downloads
            progress_callback: Callback(downloaded_bytes, total_bytes)

        Returns:
            Path to downloaded file
        """
        # Check for existing partial download
        downloaded_bytes = 0
        headers = {}

        if resume and os.path.exists(destination):
            downloaded_bytes = os.path.getsize(destination)
            headers['Range'] = f'bytes={downloaded_bytes}-'

        # Note: Using requests.get without explicit timeout
        # This should trigger a warning in migration
        response = self.session.get(url, headers=headers, stream=True)

        # Handle resume
        if response.status_code == 206:  # Partial content
            mode = 'ab'
        elif response.status_code == 200:
            mode = 'wb'
            downloaded_bytes = 0
        else:
            response.raise_for_status()
            mode = 'wb'

        # Get total size
        content_length = response.headers.get('Content-Length')
        total_size = int(content_length) + downloaded_bytes if content_length else 0

        # Create hash context for verification
        hasher = hashlib.sha256()
        if downloaded_bytes > 0 and mode == 'ab':
            # Hash existing content
            with open(destination, 'rb') as f:
                while chunk := f.read(self.chunk_size):
                    hasher.update(chunk)

        # Stream download with chunked encoding support
        with open(destination, mode) as f:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    f.write(chunk)
                    hasher.update(chunk)
                    downloaded_bytes += len(chunk)

                    if progress_callback and total_size:
                        progress_callback(downloaded_bytes, total_size)

        # Verify hash if provided
        if expected_hash:
            actual_hash = hasher.hexdigest()
            if actual_hash != expected_hash:
                os.remove(destination)
                raise ValueError(
                    f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
                )

        return destination

    def iter_lines(
        self,
        url: str,
        decode_unicode: bool = True,
        delimiter: str | None = None,
    ) -> Iterator[str]:
        """
        Stream lines from a URL.

        Useful for streaming APIs (e.g., Twitter, SSE).
        """
        response = self.session.get(url, stream=True, timeout=30)
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=decode_unicode, delimiter=delimiter):
            if line:
                yield line


# ============================================================================
# CONNECTION POOL MANAGER
# ============================================================================

class ConnectionPoolManager:
    """
    Manages connection pools for multiple hosts.

    Uses urllib3's PoolManager for efficient connection reuse.
    """

    def __init__(
        self,
        num_pools: int = 10,
        maxsize: int = 10,
        block: bool = False,
        headers: dict[str, str] | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ):
        # Create SSL context using urllib3's helper (old import path)
        if ssl_context is None:
            ssl_context = create_urllib3_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

        # Create pool manager using old import path
        self.pool_manager = PoolManager(
            num_pools=num_pools,
            maxsize=maxsize,
            block=block,
            headers=headers or {},
            ssl_context=ssl_context,
        )

    def get_pool(self, url: str) -> HTTPConnectionPool:
        """Get a connection pool for the given URL."""
        parsed = urlparse(url)
        scheme = parsed.scheme
        host = parsed.hostname
        port = parsed.port

        if scheme == 'https':
            return HTTPSConnectionPool(
                host=host,
                port=port or 443,
            )
        else:
            return HTTPConnectionPool(
                host=host,
                port=port or 80,
            )

    def request(
        self,
        method: str,
        url: str,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Make a request using the pool manager."""
        # Create timeout object using urllib3's Timeout class (old import)
        if timeout:
            timeout_obj = Timeout(connect=timeout, read=timeout)
        else:
            timeout_obj = Timeout(connect=30.0, read=30.0)

        return self.pool_manager.request(
            method,
            url,
            fields=fields,
            headers=headers,
            timeout=timeout_obj,
        )

    def clear(self) -> None:
        """Clear all connection pools."""
        self.pool_manager.clear()


# ============================================================================
# PROXY-AWARE HTTP CLIENT
# ============================================================================

class ProxyAwareClient:
    """
    HTTP client with comprehensive proxy support.

    Supports:
    - HTTP proxies
    - HTTPS proxies
    - SOCKS4/SOCKS5 proxies
    - Proxy authentication
    - Proxy bypass for local addresses
    """

    def __init__(
        self,
        http_proxy: str | None = None,
        https_proxy: str | None = None,
        socks_proxy: str | None = None,
        no_proxy: list[str] | None = None,
        proxy_auth: tuple[str, str] | None = None,
    ):
        self.session = Session()

        # Configure proxies
        self.proxies: dict[str, str] = {}

        if http_proxy:
            self.proxies['http'] = self._add_auth(http_proxy, proxy_auth)

        if https_proxy:
            self.proxies['https'] = self._add_auth(https_proxy, proxy_auth)

        if socks_proxy:
            # SOCKS proxy for both protocols
            socks_url = self._add_auth(socks_proxy, proxy_auth)
            self.proxies['http'] = socks_url
            self.proxies['https'] = socks_url

        self.no_proxy = no_proxy or []

    def _add_auth(
        self,
        proxy_url: str,
        auth: tuple[str, str] | None
    ) -> str:
        """Add authentication to proxy URL."""
        if not auth:
            return proxy_url

        parsed = compat_urlparse(proxy_url)
        username, password = auth

        if parsed.port:
            return f"{parsed.scheme}://{username}:{password}@{parsed.hostname}:{parsed.port}"
        else:
            return f"{parsed.scheme}://{username}:{password}@{parsed.hostname}"

    def _should_bypass_proxy(self, url: str) -> bool:
        """Check if URL should bypass proxy."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ''

        for pattern in self.no_proxy:
            if pattern.startswith('.'):
                if hostname.endswith(pattern) or hostname == pattern[1:]:
                    return True
            elif hostname == pattern:
                return True
            elif pattern == '*':
                return True

        return False

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> Response:
        """Make a request, using proxy if configured."""
        if self._should_bypass_proxy(url):
            proxies = None
        else:
            proxies = self.proxies

        return self.session.request(method, url, proxies=proxies, **kwargs)


# ============================================================================
# COOKIE MANAGEMENT
# ============================================================================

class CookieManager:
    """
    Advanced cookie management for requests sessions.

    Features:
    - Persistent cookie storage
    - Domain-based cookie filtering
    - Secure cookie handling
    - Cookie expiration tracking
    """

    def __init__(self, session: Session | None = None):
        self.session = session or Session()
        self._cookie_jar: RequestsCookieJar = self.session.cookies

    def set_cookies(self, cookies: dict[str, str], domain: str = '') -> None:
        """Set cookies from dictionary."""
        for name, value in cookies.items():
            self._cookie_jar.set(name, value, domain=domain)

    def get_cookie(self, name: str, domain: str | None = None) -> str | None:
        """Get a specific cookie value."""
        for cookie in self._cookie_jar:
            if cookie.name == name:
                if domain is None or cookie.domain == domain:
                    return cookie.value
        return None

    def get_cookies_for_domain(self, domain: str) -> dict[str, str]:
        """Get all cookies for a specific domain."""
        cookies = {}
        for cookie in self._cookie_jar:
            if domain.endswith(cookie.domain.lstrip('.')):
                cookies[cookie.name] = cookie.value
        return cookies

    def clear_expired(self) -> int:
        """Clear expired cookies, return count of removed cookies."""
        count = 0
        current_time = time.time()

        for cookie in list(self._cookie_jar):
            if cookie.expires and cookie.expires < current_time:
                self._cookie_jar.clear(cookie.domain, cookie.path, cookie.name)
                count += 1

        return count

    def save_to_file(self, filepath: str) -> None:
        """Save cookies to file."""
        self._cookie_jar.save(filepath, ignore_discard=True, ignore_expires=True)

    def load_from_file(self, filepath: str) -> None:
        """Load cookies from file."""
        self._cookie_jar.load(filepath, ignore_discard=True, ignore_expires=True)


# ============================================================================
# RATE LIMITER WITH TOKEN BUCKET
# ============================================================================

class RateLimiter:
    """
    Rate limiter using token bucket algorithm.

    Integrates with requests to automatically limit request rate.
    """

    def __init__(
        self,
        rate: float,  # requests per second
        burst: int = 1,  # max burst size
    ):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = Lock()

    def acquire(self, timeout: float | None = None) -> bool:
        """
        Acquire a token, blocking if necessary.

        Returns True if token acquired, False if timeout.
        """
        start_time = time.monotonic()

        while True:
            with self._lock:
                # Refill tokens based on elapsed time
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

            # Check timeout
            if timeout is not None and (time.monotonic() - start_time) >= timeout:
                return False

            # Sleep until next token available
            sleep_time = (1 - self.tokens) / self.rate
            time.sleep(min(sleep_time, 0.1))

    def rate_limited(self, func: Callable) -> Callable:
        """Decorator to rate limit a function."""
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.acquire()
            return func(*args, **kwargs)
        return wrapper


# ============================================================================
# MULTI-THREADED REQUEST EXECUTOR
# ============================================================================

class MultiThreadedExecutor:
    """
    Execute multiple requests concurrently with connection pooling.

    Uses a shared session for connection reuse.
    """

    def __init__(
        self,
        max_workers: int = 5,
        session: Session | None = None,
    ):
        self.max_workers = max_workers
        self.session = session or self._create_session()
        self._results: list[tuple[str, Response]] = []
        self._errors: list[tuple[str, Exception]] = []
        self._lock = Lock()

    def _create_session(self) -> Session:
        """Create session with connection pooling optimized for concurrent requests."""
        session = Session()
        adapter = HTTPAdapter(
            pool_connections=self.max_workers,
            pool_maxsize=self.max_workers * 2,
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def _make_request(self, url: str, method: str = 'GET', **kwargs: Any) -> None:
        """Make a single request and store result."""
        try:
            response = self.session.request(method, url, **kwargs)
            with self._lock:
                self._results.append((url, response))
        except Exception as e:
            with self._lock:
                self._errors.append((url, e))

    def execute(
        self,
        urls: list[str],
        method: str = 'GET',
        **kwargs: Any
    ) -> tuple[list[tuple[str, Response]], list[tuple[str, Exception]]]:
        """
        Execute requests concurrently.

        Returns tuple of (successful_results, errors).
        """
        self._results = []
        self._errors = []

        threads: list[Thread] = []
        for url in urls:
            t = Thread(target=self._make_request, args=(url, method), kwargs=kwargs)
            threads.append(t)
            t.start()

            # Limit concurrent threads
            if len([t for t in threads if t.is_alive()]) >= self.max_workers:
                for t in threads:
                    if t.is_alive():
                        t.join(timeout=0.1)

        # Wait for all threads to complete
        for t in threads:
            t.join()

        return self._results, self._errors


# ============================================================================
# RETRY DECORATOR
# ============================================================================

def with_retry(
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple[int, ...] = (500, 502, 503, 504),
    exceptions: tuple = (RequestException,),
) -> Callable:
    """
    Decorator to add retry logic to request functions.

    Uses urllib3's Retry configuration through requests.packages.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_config = Retry(
                total=max_retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist,
            )

            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    if hasattr(response, 'status_code'):
                        if response.status_code not in status_forcelist:
                            return response
                        if attempt < max_retries:
                            time.sleep(backoff_factor * (2 ** attempt))
                            continue
                    return response
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                    raise

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_basic_requests():
    """Test basic requests without timeout (should trigger warning)."""
    # These should all generate timeout warnings
    response = requests.get("https://api.example.com/users")
    response = requests.post("https://api.example.com/users", json={"name": "test"})
    response = requests.put("https://api.example.com/users/1", json={"name": "updated"})
    response = requests.delete("https://api.example.com/users/1")
    return response


def test_session_requests():
    """Test session-based requests without timeout."""
    session = Session()
    # These should also generate warnings
    response = session.get("https://api.example.com/users")
    response = session.post("https://api.example.com/users", json={"name": "test"})
    return response


def test_urllib3_integration():
    """Test urllib3 integration through requests.packages."""
    # Disable warnings using old import path
    requests_urllib3.disable_warnings(InsecureRequestWarning)

    # Create retry configuration
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )

    # Create timeout
    timeout = Timeout(connect=5.0, read=30.0)

    # Create pool manager
    pool = PoolManager(
        num_pools=10,
        maxsize=10,
        retries=retry,
        timeout=timeout,
    )

    response = pool.request('GET', 'https://api.example.com')
    return response


def test_complex_authentication():
    """Test various authentication methods."""
    # Basic auth
    basic_response = requests.get(
        "https://api.example.com/auth",
        auth=HTTPBasicAuth("user", "pass"),
        timeout=30,
    )

    # Digest auth
    digest_response = requests.get(
        "https://api.example.com/auth",
        auth=HTTPDigestAuth("user", "pass"),
        timeout=30,
    )

    # OAuth2 bearer
    oauth_auth = OAuth2BearerAuth("my-token")
    oauth_response = requests.get(
        "https://api.example.com/auth",
        auth=oauth_auth,
        timeout=30,
    )

    return basic_response, digest_response, oauth_response


def test_ssl_verification():
    """Test SSL verification configurations."""
    # Disable SSL verification (not recommended)
    response = requests.get(
        "https://self-signed.example.com",
        verify=False,
        timeout=30,
    )

    # Custom CA bundle
    response = requests.get(
        "https://internal.example.com",
        verify="/path/to/ca-bundle.crt",
        timeout=30,
    )

    # Client certificate
    response = requests.get(
        "https://mtls.example.com",
        cert=("/path/to/client.crt", "/path/to/client.key"),
        timeout=30,
    )

    return response


def test_proxy_configuration():
    """Test proxy configurations."""
    proxies = {
        "http": "http://proxy.example.com:8080",
        "https": "https://proxy.example.com:8080",
    }

    # Authenticated proxy
    auth_proxies = {
        "http": "http://user:pass@proxy.example.com:8080",
        "https": "http://user:pass@proxy.example.com:8080",
    }

    response = requests.get(
        "https://api.example.com",
        proxies=proxies,
        timeout=30,
    )

    return response


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Demonstrate usage
    print("Codeshift Stress Test: Requests + urllib3 Migration")
    print("=" * 60)

    # Test the API client
    client = AdvancedAPIClient(
        base_url="https://api.example.com",
        api_key="test-key",
        timeout=30.0,
        max_retries=3,
    )

    print("\nCreated AdvancedAPIClient with:")
    print(f"  - Base URL: {client.base_url}")
    print(f"  - Timeout: {client.timeout}s")
    print(f"  - SSL Verification: {client.verify_ssl}")

    # Test connection pool manager
    pool_manager = ConnectionPoolManager(
        num_pools=10,
        maxsize=10,
    )

    print("\nCreated ConnectionPoolManager with:")
    print(f"  - Pool Manager Type: {type(pool_manager.pool_manager).__name__}")

    # Test streaming client
    streaming_client = StreamingDownloadClient(chunk_size=8192)
    print(f"\nCreated StreamingDownloadClient with chunk_size={streaming_client.chunk_size}")

    # Test proxy client
    proxy_client = ProxyAwareClient(
        http_proxy="http://proxy.example.com:8080",
        https_proxy="https://proxy.example.com:8080",
        no_proxy=["localhost", "127.0.0.1", ".internal.example.com"],
    )

    print("\nCreated ProxyAwareClient with:")
    print(f"  - HTTP Proxy: {proxy_client.proxies.get('http')}")
    print(f"  - HTTPS Proxy: {proxy_client.proxies.get('https')}")

    print("\n" + "=" * 60)
    print("Stress test file ready for migration testing.")

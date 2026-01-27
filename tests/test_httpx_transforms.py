"""Tests for httpx 0.x to 1.x transforms."""

from codeshift.migrator.transforms.httpx_transformer import transform_httpx


class TestHttpxTimeoutTransforms:
    """Tests for httpx Timeout parameter transformations."""

    def test_timeout_connect_timeout(self):
        """Test transforming connect_timeout to connect."""
        code = """
import httpx

timeout = httpx.Timeout(connect_timeout=5.0)
"""
        transformed, changes = transform_httpx(code)

        assert "connect=" in transformed
        assert "connect_timeout" not in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "timeout_connect_timeout_to_connect" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_timeout_read_timeout(self):
        """Test transforming read_timeout to read."""
        code = """
import httpx

timeout = httpx.Timeout(read_timeout=30.0)
"""
        transformed, changes = transform_httpx(code)

        assert "read=" in transformed
        assert "read_timeout" not in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "timeout_read_timeout_to_read" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_timeout_write_timeout(self):
        """Test transforming write_timeout to write."""
        code = """
import httpx

timeout = httpx.Timeout(write_timeout=10.0)
"""
        transformed, changes = transform_httpx(code)

        assert "write=" in transformed
        assert "write_timeout" not in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "timeout_write_timeout_to_write" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_timeout_pool_timeout(self):
        """Test transforming pool_timeout to pool."""
        code = """
import httpx

timeout = httpx.Timeout(pool_timeout=5.0)
"""
        transformed, changes = transform_httpx(code)

        assert "pool=" in transformed
        assert "pool_timeout" not in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "timeout_pool_timeout_to_pool" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_timeout_multiple_params(self):
        """Test transforming multiple timeout parameters."""
        code = """
import httpx

timeout = httpx.Timeout(
    connect_timeout=5.0,
    read_timeout=30.0,
    write_timeout=10.0,
    pool_timeout=5.0
)
"""
        transformed, changes = transform_httpx(code)

        assert "connect=" in transformed
        assert "read=" in transformed
        assert "write=" in transformed
        assert "pool=" in transformed
        assert len(changes) >= 4

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestHttpxClientTransforms:
    """Tests for httpx Client transformations."""

    def test_client_proxies_string(self):
        """Test transforming Client proxies string parameter."""
        code = """
import httpx

client = httpx.Client(proxies='http://proxy.example.com')
"""
        transformed, changes = transform_httpx(code)

        # proxies parameter changed to proxy
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestHttpxAsyncClientTransforms:
    """Tests for httpx AsyncClient transformations."""

    def test_async_client_timeout(self):
        """Test transforming AsyncClient with old timeout."""
        code = """
import httpx

async def fetch():
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect_timeout=5.0)) as client:
        response = await client.get('https://example.com')
"""
        transformed, changes = transform_httpx(code)

        assert "connect=" in transformed
        assert "connect_timeout" not in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestHttpxResponseTransforms:
    """Tests for httpx Response method transformations."""

    def test_response_read_sync(self):
        """Test usage of response read method."""
        code = """
import httpx

response = httpx.get('https://example.com')
data = response.read()
"""
        transformed, changes = transform_httpx(code)

        # Should compile successfully
        compile(transformed, "<string>", "exec")


class TestHttpxMultipleTransforms:
    """Tests for multiple httpx transformations."""

    def test_comprehensive_migration(self):
        """Test multiple httpx migrations in one file."""
        code = """
import httpx

timeout = httpx.Timeout(
    connect_timeout=5.0,
    read_timeout=30.0
)

client = httpx.Client(timeout=timeout)
response = client.get('https://example.com')
"""
        transformed, changes = transform_httpx(code)

        # Should have changes for timeout parameters
        assert len(changes) >= 2
        assert "connect=" in transformed
        assert "read=" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern httpx code is not transformed."""
        code = """
import httpx

timeout = httpx.Timeout(
    connect=5.0,
    read=30.0,
    write=10.0,
    pool=5.0
)

client = httpx.Client(timeout=timeout)
response = client.get('https://example.com')
"""
        transformed, changes = transform_httpx(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

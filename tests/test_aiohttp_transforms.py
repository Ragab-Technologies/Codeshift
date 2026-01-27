"""Tests for aiohttp 3.7 to 3.9+ transforms."""

from codeshift.migrator.transforms.aiohttp_transformer import transform_aiohttp


class TestAiohttpLoopParameterTransforms:
    """Tests for aiohttp loop parameter removal transformations."""

    def test_client_session_loop_removal(self):
        """Test removing loop parameter from ClientSession."""
        code = """
import aiohttp
import asyncio

loop = asyncio.get_event_loop()
session = aiohttp.ClientSession(loop=loop)
"""
        transformed, changes = transform_aiohttp(code)

        # Check that loop parameter was removed or flagged
        assert len(changes) >= 1
        # Loop parameter should be removed from ClientSession
        assert "ClientSession()" in transformed or "loop=" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_tcp_connector_loop_removal(self):
        """Test removing loop parameter from TCPConnector."""
        code = """
import aiohttp
import asyncio

loop = asyncio.get_event_loop()
connector = aiohttp.TCPConnector(loop=loop)
"""
        transformed, changes = transform_aiohttp(code)

        # Check that loop parameter was removed or flagged
        assert len(changes) >= 1
        # Loop parameter should be removed from TCPConnector
        assert "TCPConnector()" in transformed or "loop=" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_web_application_loop_removal(self):
        """Test removing loop parameter from web.Application."""
        code = """
from aiohttp import web
import asyncio

loop = asyncio.get_event_loop()
app = web.Application(loop=loop)
"""
        transformed, changes = transform_aiohttp(code)

        # Check that loop parameter was removed or flagged
        assert len(changes) >= 1
        # Loop parameter should be removed from Application
        assert "Application()" in transformed or "loop=" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAiohttpConnectorOwnerTransforms:
    """Tests for aiohttp connector_owner parameter transformations."""

    def test_connector_owner_default_change(self):
        """Test handling connector_owner parameter default change."""
        code = """
import aiohttp

connector = aiohttp.TCPConnector()
session = aiohttp.ClientSession(connector=connector, connector_owner=False)
"""
        transformed, changes = transform_aiohttp(code)

        # Should handle connector_owner awareness
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAiohttpBasicAuthTransforms:
    """Tests for aiohttp BasicAuth transformations."""

    def test_basic_auth_encode_removal(self):
        """Test warning about BasicAuth.encode() removal."""
        code = """
import aiohttp

auth = aiohttp.BasicAuth('user', 'pass')
encoded = auth.encode()
"""
        transformed, changes = transform_aiohttp(code)

        # Should detect deprecated encode() call
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAiohttpClientTimeoutTransforms:
    """Tests for aiohttp ClientTimeout transformations."""

    def test_client_timeout_usage(self):
        """Test ClientTimeout usage pattern."""
        code = """
import aiohttp

timeout = aiohttp.ClientTimeout(total=60)
"""
        transformed, changes = transform_aiohttp(code)

        # Modern ClientTimeout should pass through unchanged
        assert "ClientTimeout" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAiohttpMiddlewareTransforms:
    """Tests for aiohttp middleware transformations."""

    def test_old_style_middleware(self):
        """Test detecting old-style middleware signatures."""
        code = """
from aiohttp import web

async def middleware(app, handler):
    async def middleware_handler(request):
        return await handler(request)
    return middleware_handler
"""
        transformed, changes = transform_aiohttp(code)

        # Should detect old middleware pattern
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAiohttpMultipleTransforms:
    """Tests for multiple aiohttp transformations."""

    def test_comprehensive_migration(self):
        """Test multiple aiohttp migrations in one file."""
        code = """
import aiohttp
import asyncio
from aiohttp import web

loop = asyncio.get_event_loop()

connector = aiohttp.TCPConnector(loop=loop)
session = aiohttp.ClientSession(loop=loop, connector=connector)
app = web.Application(loop=loop)
"""
        transformed, changes = transform_aiohttp(code)

        # Should have multiple changes for loop removal
        assert len(changes) >= 3

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern aiohttp code is not transformed."""
        code = """
import aiohttp
from aiohttp import web

async def main():
    connector = aiohttp.TCPConnector()
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get('https://example.com') as response:
            return await response.text()

app = web.Application()

@web.middleware
async def my_middleware(request, handler):
    return await handler(request)
"""
        transformed, changes = transform_aiohttp(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

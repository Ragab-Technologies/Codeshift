"""Tests for Requests library transformation."""

from codeshift.migrator.transforms.requests_transformer import (
    transform_requests,
)


class TestImportTransforms:
    """Tests for Requests import transformations."""

    def test_urllib3_import_from_requests_packages(self):
        """Test transforming requests.packages.urllib3 imports."""
        code = """from requests.packages.urllib3 import Retry"""
        result, changes = transform_requests(code)
        assert "from urllib3 import" in result
        assert "requests.packages" not in result
        assert any(c.transform_name == "urllib3_import_fix" for c in changes)

    def test_urllib3_submodule_import(self):
        """Test transforming requests.packages.urllib3 submodule imports."""
        code = """from requests.packages.urllib3.util.retry import Retry"""
        result, changes = transform_requests(code)
        assert "from urllib3.util.retry import" in result
        assert "requests.packages" not in result
        assert any(c.transform_name == "urllib3_import_fix" for c in changes)

    def test_compat_urljoin_import(self):
        """Test transforming requests.compat urljoin import."""
        code = """from requests.compat import urljoin"""
        result, changes = transform_requests(code)
        assert "from urllib.parse import" in result
        assert any("compat" in c.transform_name for c in changes)

    def test_compat_urlparse_import(self):
        """Test transforming requests.compat urlparse import."""
        code = """from requests.compat import urlparse"""
        result, changes = transform_requests(code)
        assert "from urllib.parse import" in result

    def test_regular_requests_import_unchanged(self):
        """Test that regular requests imports are unchanged."""
        code = """import requests"""
        result, changes = transform_requests(code)
        assert result == code
        assert len(changes) == 0


class TestTimeoutWarnings:
    """Tests for timeout parameter warnings."""

    def test_requests_get_without_timeout_warning(self):
        """Test requests.get() without timeout generates warning."""
        code = """response = requests.get("https://api.example.com")"""
        result, changes = transform_requests(code)
        assert any(c.transform_name == "get_add_explicit_timeout" for c in changes)

    def test_requests_post_without_timeout_warning(self):
        """Test requests.post() without timeout generates warning."""
        code = """response = requests.post("https://api.example.com", json=data)"""
        result, changes = transform_requests(code)
        assert any(c.transform_name == "post_add_explicit_timeout" for c in changes)

    def test_requests_put_without_timeout_warning(self):
        """Test requests.put() without timeout generates warning."""
        code = """response = requests.put("https://api.example.com", data=payload)"""
        result, changes = transform_requests(code)
        assert any(c.transform_name == "put_add_explicit_timeout" for c in changes)

    def test_requests_delete_without_timeout_warning(self):
        """Test requests.delete() without timeout generates warning."""
        code = """response = requests.delete("https://api.example.com/1")"""
        result, changes = transform_requests(code)
        assert any(c.transform_name == "delete_add_explicit_timeout" for c in changes)

    def test_requests_with_timeout_no_warning(self):
        """Test requests with timeout has no warning."""
        code = """response = requests.get("https://api.example.com", timeout=30)"""
        result, changes = transform_requests(code)
        assert not any("timeout" in c.transform_name for c in changes)

    def test_session_get_without_timeout_warning(self):
        """Test session.get() without timeout generates warning."""
        code = """response = session.get("https://api.example.com")"""
        result, changes = transform_requests(code)
        assert any("session" in c.transform_name for c in changes)


class TestSyntaxErrorHandling:
    """Tests for syntax error handling."""

    def test_syntax_error_returns_original(self):
        """Test that syntax errors return original code."""
        code = """requests.get("""
        result, changes = transform_requests(code)
        assert result == code
        assert len(changes) == 0


class TestComplexTransforms:
    """Tests for complex multi-transform scenarios."""

    def test_multiple_transforms_in_one_file(self):
        """Test multiple transforms applied to one file."""
        code = """from requests.packages.urllib3 import Retry
from requests.compat import urljoin

base_url = "https://api.example.com"
full_url = urljoin(base_url, "/users")
response = requests.get(full_url)
"""
        result, changes = transform_requests(code)
        assert "from urllib3 import" in result
        assert len(changes) >= 2

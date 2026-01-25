"""Tests for FastAPI transformation."""

from codeshift.migrator.transforms.fastapi_transformer import (
    transform_fastapi,
)


class TestImportTransforms:
    """Tests for FastAPI import transformations."""

    def test_starlette_responses_to_fastapi(self):
        """Test transforming starlette.responses imports to fastapi.responses."""
        code = """from starlette.responses import JSONResponse, HTMLResponse"""
        result, changes = transform_fastapi(code)
        assert "from fastapi.responses import" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "starlette_to_fastapi_responses"

    def test_starlette_requests_to_fastapi(self):
        """Test transforming starlette.requests imports to fastapi."""
        code = """from starlette.requests import Request"""
        result, changes = transform_fastapi(code)
        assert "from fastapi import" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "starlette_to_fastapi_request"

    def test_starlette_websockets_to_fastapi(self):
        """Test transforming starlette.websockets imports to fastapi."""
        code = """from starlette.websockets import WebSocket"""
        result, changes = transform_fastapi(code)
        assert "from fastapi import" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "starlette_to_fastapi_websocket"

    def test_starlette_status_to_fastapi(self):
        """Test transforming starlette.status imports to fastapi."""
        code = """from starlette.status import HTTP_200_OK"""
        result, changes = transform_fastapi(code)
        assert "from fastapi import" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "starlette_to_fastapi_status"

    def test_non_starlette_import_unchanged(self):
        """Test that non-starlette imports are unchanged."""
        code = """from fastapi import FastAPI"""
        result, changes = transform_fastapi(code)
        assert result == code
        assert len(changes) == 0


class TestFieldRegexTransforms:
    """Tests for Field/Query/Path/Body regex -> pattern transform."""

    def test_field_regex_to_pattern(self):
        """Test Field(regex=...) to Field(pattern=...)."""
        code = """name = Field(..., regex=r"^[a-z]+$")"""
        result, changes = transform_fastapi(code)
        assert "pattern=" in result
        assert "regex=" not in result
        assert len(changes) == 1
        assert changes[0].transform_name == "field_regex_to_pattern"

    def test_query_regex_to_pattern(self):
        """Test Query(regex=...) to Query(pattern=...)."""
        code = """q = Query(None, regex=r"\\d+")"""
        result, changes = transform_fastapi(code)
        assert "pattern=" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "query_regex_to_pattern"

    def test_path_regex_to_pattern(self):
        """Test Path(regex=...) to Path(pattern=...)."""
        code = """item_id = Path(..., regex=r"[a-z0-9]+")"""
        result, changes = transform_fastapi(code)
        assert "pattern=" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "path_regex_to_pattern"

    def test_body_regex_to_pattern(self):
        """Test Body(regex=...) to Body(pattern=...)."""
        code = """data = Body(..., regex=r"^test")"""
        result, changes = transform_fastapi(code)
        assert "pattern=" in result
        assert len(changes) == 1
        assert changes[0].transform_name == "body_regex_to_pattern"

    def test_field_without_regex_unchanged(self):
        """Test Field without regex is unchanged."""
        code = """name = Field(..., min_length=1)"""
        result, changes = transform_fastapi(code)
        assert result == code
        assert len(changes) == 0


class TestDependsTransforms:
    """Tests for Depends parameter renames."""

    def test_depends_use_cache_to_use_cached(self):
        """Test Depends(use_cache=...) to Depends(use_cached=...)."""
        code = """dep = Depends(get_db, use_cache=True)"""
        result, changes = transform_fastapi(code)
        assert "use_cached=" in result
        assert "use_cache=" not in result
        assert len(changes) == 1
        assert changes[0].transform_name == "depends_use_cache_rename"

    def test_depends_without_use_cache_unchanged(self):
        """Test Depends without use_cache is unchanged."""
        code = """dep = Depends(get_db)"""
        result, changes = transform_fastapi(code)
        assert result == code
        assert len(changes) == 0


class TestFastAPIAppTransforms:
    """Tests for FastAPI app initialization transforms."""

    def test_openapi_prefix_to_root_path(self):
        """Test FastAPI(openapi_prefix=...) to FastAPI(root_path=...)."""
        code = """app = FastAPI(openapi_prefix="/api")"""
        result, changes = transform_fastapi(code)
        assert "root_path=" in result
        assert "openapi_prefix=" not in result
        assert len(changes) == 1
        assert changes[0].transform_name == "openapi_prefix_to_root_path"

    def test_fastapi_without_openapi_prefix_unchanged(self):
        """Test FastAPI without openapi_prefix is unchanged."""
        code = """app = FastAPI(title="My App")"""
        result, changes = transform_fastapi(code)
        assert result == code
        assert len(changes) == 0


class TestSyntaxErrorHandling:
    """Tests for syntax error handling."""

    def test_syntax_error_returns_original(self):
        """Test that syntax errors return original code."""
        code = """def broken("""
        result, changes = transform_fastapi(code)
        assert result == code
        assert len(changes) == 0


class TestComplexTransforms:
    """Tests for complex multi-transform scenarios."""

    def test_multiple_transforms_in_one_file(self):
        """Test multiple transforms applied to one file."""
        code = """from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK

name = Field(..., regex=r"^[a-z]+$")
app = FastAPI(openapi_prefix="/api")
"""
        result, changes = transform_fastapi(code)
        assert "from fastapi.responses import" in result
        assert "from fastapi import" in result
        assert "pattern=" in result
        assert "root_path=" in result
        assert len(changes) == 4

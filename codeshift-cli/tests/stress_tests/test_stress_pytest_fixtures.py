"""
Stress test file for Codeshift pytest 6.x -> 7.x migration.

This file contains a VERY complex pytest scenario with:
- 20+ fixtures with various scopes
- Fixture chaining and dependencies
- Parametrized fixtures
- Factory fixtures
- Autouse fixtures
- Yield fixtures with cleanup (using deprecated @pytest.yield_fixture)
- Request fixture usage (using deprecated funcargnames)
- Monkeypatch patterns
- pytest.raises with match
- Capsys and capfd usage
- tmpdir and tmpdir_factory (deprecated, should become tmp_path)
- Marks: skip, skipif, xfail, parametrize
- Custom markers
- Conftest.py patterns with deprecated hook parameter names
- Hook implementations
- Plugin patterns
- pytest.skip(msg=...) (deprecated, should become reason=...)
- pytest.warns(None) (deprecated, should become pytest.warns())
- node.fspath (deprecated, should become node.path)

Target: pytest 6.2 -> 7.0 migration patterns
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.fixtures import FixtureRequest
from _pytest.nodes import Item
from _pytest.runner import CallInfo
from _pytest.terminal import TerminalReporter

# =============================================================================
# CUSTOM MARKERS REGISTRATION (pytest 6.x style - needs update for 7.x)
# =============================================================================

def pytest_configure(config: Config) -> None:
    """Register custom markers - pytest 6.x style."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "database: marks tests requiring database")
    config.addinivalue_line("markers", "network: marks tests requiring network access")
    config.addinivalue_line("markers", "smoke: marks tests as smoke tests")
    config.addinivalue_line("markers", "regression: marks tests as regression tests")
    config.addinivalue_line("markers", "priority(level): set test priority level")
    config.addinivalue_line("markers", "flaky(reruns): marks flaky tests with rerun count")
    config.addinivalue_line("markers", "timeout(seconds): set test timeout")
    config.addinivalue_line("markers", "feature(name): associate test with feature")


# =============================================================================
# HOOK IMPLEMENTATIONS (pytest 6.x patterns with deprecated parameter names)
# =============================================================================

def pytest_addoption(parser: Parser) -> None:
    """Add custom command line options - pytest 6.x style."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests"
    )
    parser.addoption(
        "--stress-level",
        action="store",
        default="normal",
        choices=["light", "normal", "heavy"],
        help="stress test level"
    )
    parser.addoption(
        "--custom-config",
        action="store",
        default=None,
        help="path to custom config file"
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    """Modify test collection - pytest 6.x style using config.getoption."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


# DEPRECATED: path parameter renamed to file_path in pytest 7.0
def pytest_collect_file(parent: Any, path: Any) -> None:
    """Collect file hook - using deprecated 'path' parameter (should be 'file_path')."""
    # This hook uses the deprecated 'path' parameter
    pass


# DEPRECATED: path parameter renamed to collection_path in pytest 7.0
def pytest_ignore_collect(path: Any, config: Config) -> bool | None:
    """Ignore collect hook - using deprecated 'path' parameter (should be 'collection_path')."""
    # This hook uses the deprecated 'path' parameter
    return None


# DEPRECATED: path parameter renamed to module_path in pytest 7.0
def pytest_pycollect_makemodule(path: Any, parent: Any) -> None:
    """Make module hook - using deprecated 'path' parameter (should be 'module_path')."""
    # This hook uses the deprecated 'path' parameter
    pass


# DEPRECATED: startdir parameter renamed to start_path in pytest 7.0
def pytest_report_header(config: Config, startdir: Any) -> str | None:
    """Report header hook - using deprecated 'startdir' parameter (should be 'start_path')."""
    return "Stress test report header"


def pytest_runtest_setup(item: Item) -> None:
    """Pre-test setup hook - pytest 6.x patterns."""
    # Check for network marker
    for marker in item.iter_markers(name="network"):
        # pytest 6.x style marker iteration
        pass

    # Check priority marker
    for marker in item.iter_markers(name="priority"):
        level = marker.args[0] if marker.args else "normal"
        # Handle priority


def pytest_runtest_makereport(item: Item, call: CallInfo) -> None:
    """Create test report - pytest 6.x style."""
    # DEPRECATED: Using node.fspath (should be node.path in pytest 7.x)
    file_location = item.fspath
    pass


def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: int, config: Config) -> None:
    """Terminal summary hook - pytest 6.x style."""
    terminalreporter.write_sep("-", "stress test summary")


# =============================================================================
# DATA CLASSES AND MODELS FOR TESTING
# =============================================================================

@dataclass
class User:
    """Sample user model."""
    id: int
    username: str
    email: str
    is_active: bool = True
    roles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DatabaseConnection:
    """Mock database connection."""
    host: str
    port: int
    database: str
    connected: bool = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def execute(self, query: str) -> list[dict[str, Any]]:
        return [{"result": "mock"}]


@dataclass
class APIClient:
    """Mock API client."""
    base_url: str
    api_key: str
    timeout: int = 30
    session: Any | None = None

    def get(self, endpoint: str) -> dict[str, Any]:
        return {"status": "ok", "endpoint": endpoint}

    def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"status": "created", "data": data}


# =============================================================================
# FIXTURE 1-5: BASIC SCOPES
# =============================================================================

@pytest.fixture(scope="session")
def session_config() -> dict[str, Any]:
    """Session-scoped configuration fixture."""
    return {
        "environment": "test",
        "debug": True,
        "log_level": "DEBUG",
        "max_connections": 10,
    }


@pytest.fixture(scope="module")
def module_database(session_config: dict[str, Any]) -> Generator[DatabaseConnection, None, None]:
    """Module-scoped database fixture with cleanup."""
    db = DatabaseConnection(
        host="localhost",
        port=5432,
        database="test_db"
    )
    db.connect()
    yield db
    db.disconnect()


@pytest.fixture(scope="class")
def class_api_client(session_config: dict[str, Any]) -> APIClient:
    """Class-scoped API client fixture."""
    return APIClient(
        base_url="https://api.test.com",
        api_key="test-key-12345",
        timeout=session_config.get("timeout", 30)
    )


@pytest.fixture(scope="function")
def function_user() -> User:
    """Function-scoped user fixture."""
    return User(
        id=1,
        username="testuser",
        email="test@example.com",
        roles=["user", "tester"]
    )


@pytest.fixture(scope="package")
def package_cache() -> dict[str, Any]:
    """Package-scoped cache fixture."""
    return {}


# =============================================================================
# FIXTURE 6-10: YIELD FIXTURES WITH CLEANUP (USING DEPRECATED PATTERNS)
# =============================================================================

# DEPRECATED: @pytest.yield_fixture should be @pytest.fixture
@pytest.yield_fixture
def temp_directory_deprecated() -> Generator[Path, None, None]:
    """DEPRECATED: Yield fixture using @pytest.yield_fixture decorator."""
    import shutil
    temp_dir = Path(tempfile.mkdtemp(prefix="pytest_stress_"))
    yield temp_dir
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


# DEPRECATED: @pytest.yield_fixture with scope
@pytest.yield_fixture(scope="module")
def module_temp_directory() -> Generator[Path, None, None]:
    """DEPRECATED: Module-scoped yield fixture using @pytest.yield_fixture."""
    import shutil
    temp_dir = Path(tempfile.mkdtemp(prefix="pytest_module_"))
    yield temp_dir
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_file(temp_directory_deprecated: Path) -> Generator[Path, None, None]:
    """Yield fixture with temp file - depends on temp_directory."""
    temp_file_path = temp_directory_deprecated / "test_file.txt"
    temp_file_path.write_text("initial content")
    yield temp_file_path
    # Cleanup handled by temp_directory


@pytest.fixture
def mock_server() -> Generator[dict[str, Any], None, None]:
    """Yield fixture simulating server lifecycle."""
    server = {"host": "127.0.0.1", "port": 8888, "running": False}
    # Setup
    server["running"] = True
    yield server
    # Teardown
    server["running"] = False


@pytest.fixture
def database_transaction(module_database: DatabaseConnection) -> Generator[DatabaseConnection, None, None]:
    """Yield fixture with transaction rollback pattern."""
    # Begin transaction
    yield module_database
    # Rollback transaction (mock)


@pytest.fixture
def resource_pool() -> Generator[list[Any], None, None]:
    """Yield fixture managing resource pool."""
    pool: list[Any] = []
    for i in range(5):
        pool.append({"id": i, "allocated": False})
    yield pool
    # Release all resources
    for resource in pool:
        resource["allocated"] = False


# =============================================================================
# FIXTURE 11-15: PARAMETRIZED AND FACTORY FIXTURES
# =============================================================================

@pytest.fixture(params=["sqlite", "postgres", "mysql"])
def database_type(request: FixtureRequest) -> str:
    """Parametrized fixture for database types."""
    return request.param


@pytest.fixture(params=[
    pytest.param("admin", id="admin-user"),
    pytest.param("moderator", id="mod-user"),
    pytest.param("viewer", id="viewer-user"),
    pytest.param("guest", marks=pytest.mark.slow, id="guest-user"),
])
def user_role(request: FixtureRequest) -> str:
    """Parametrized fixture with param IDs and marks."""
    return request.param


@pytest.fixture(params=[
    (200, "success"),
    (201, "created"),
    (400, "bad_request"),
    (401, "unauthorized"),
    (403, "forbidden"),
    (404, "not_found"),
    (500, "server_error"),
])
def http_response(request: FixtureRequest) -> tuple[int, str]:
    """Parametrized fixture with tuple params."""
    return request.param


@pytest.fixture
def user_factory() -> Callable[..., User]:
    """Factory fixture for creating users."""
    created_users: list[User] = []

    def _create_user(
        username: str = "testuser",
        email: str | None = None,
        roles: list[str] | None = None,
        **kwargs: Any
    ) -> User:
        user = User(
            id=len(created_users) + 1,
            username=username,
            email=email or f"{username}@test.com",
            roles=roles or ["user"],
            **kwargs
        )
        created_users.append(user)
        return user

    return _create_user


@pytest.fixture
def api_response_factory() -> Callable[..., dict[str, Any]]:
    """Factory fixture for API responses."""
    def _create_response(
        status: int = 200,
        data: dict[str, Any] | None = None,
        error: str | None = None
    ) -> dict[str, Any]:
        response = {"status": status}
        if data is not None:
            response["data"] = data
        if error is not None:
            response["error"] = error
        return response

    return _create_response


# =============================================================================
# FIXTURE 16-20: AUTOUSE AND REQUEST FIXTURES (USING DEPRECATED PATTERNS)
# =============================================================================

@pytest.fixture(autouse=True)
def reset_environment() -> Generator[None, None, None]:
    """Autouse fixture to reset environment for each test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True, scope="class")
def class_setup_teardown(request: FixtureRequest) -> Generator[None, None, None]:
    """Autouse class-level fixture with request access."""
    # Setup
    if hasattr(request, "cls") and request.cls is not None:
        request.cls.shared_data = {"setup_complete": True}
    yield
    # Teardown
    if hasattr(request, "cls") and request.cls is not None:
        delattr(request.cls, "shared_data")


@pytest.fixture
def request_context(request: FixtureRequest) -> dict[str, Any]:
    """Fixture providing request context information."""
    # DEPRECATED: funcargnames should be fixturenames
    return {
        "node_name": request.node.name,
        "function_name": request.function.__name__ if hasattr(request, "function") else None,
        "module_name": request.module.__name__ if hasattr(request, "module") else None,
        "markers": [m.name for m in request.node.iter_markers()],
        "fixture_names_deprecated": request.funcargnames,  # DEPRECATED: should be fixturenames
    }


@pytest.fixture
def dynamic_fixture(request: FixtureRequest) -> Any:
    """Fixture that behaves differently based on markers."""
    if request.node.get_closest_marker("slow"):
        return {"mode": "slow", "timeout": 60}
    elif request.node.get_closest_marker("integration"):
        return {"mode": "integration", "timeout": 30}
    else:
        return {"mode": "unit", "timeout": 5}


@pytest.fixture
def indirect_fixture(request: FixtureRequest) -> str:
    """Fixture for indirect parametrization - pytest 6.x pattern."""
    value = getattr(request, "param", "default")
    return f"processed_{value}"


# =============================================================================
# FIXTURE 21-25: ADVANCED PATTERNS WITH DEPRECATED TMPDIR
# =============================================================================

@pytest.fixture
def mock_external_service(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Fixture using monkeypatch to mock external service."""
    mock = MagicMock()
    mock.call.return_value = {"status": "mocked"}

    # Monkeypatch patterns from pytest 6.x
    monkeypatch.setattr("os.path.exists", lambda x: True)
    monkeypatch.setenv("EXTERNAL_SERVICE_URL", "http://mock.service.local")
    monkeypatch.delenv("PRODUCTION_KEY", raising=False)

    return mock


@pytest.fixture
def async_client() -> AsyncMock:
    """Fixture for async testing patterns."""
    client = AsyncMock()
    client.get.return_value = {"async": True, "data": []}
    client.post.return_value = {"created": True}
    return client


@pytest.fixture
def thread_safe_counter() -> dict[str, Any]:
    """Fixture providing thread-safe counter."""
    return {
        "count": 0,
        "lock": threading.Lock(),
        "increment": lambda d: d.update({"count": d["count"] + 1})
    }


# DEPRECATED: Using tmpdir (py.path.local) instead of tmp_path (pathlib.Path)
@pytest.fixture
def complex_nested_fixture_with_tmpdir(
    session_config: dict[str, Any],
    module_database: DatabaseConnection,
    function_user: User,
    user_factory: Callable[..., User],
    tmpdir: Any,  # DEPRECATED: should be tmp_path
) -> dict[str, Any]:
    """Complex fixture with tmpdir dependency (DEPRECATED)."""
    return {
        "config": session_config,
        "database": module_database,
        "primary_user": function_user,
        "additional_users": [user_factory(f"user_{i}") for i in range(3)],
        "workspace": tmpdir,  # DEPRECATED: returns py.path.local, should use tmp_path
    }


@pytest.fixture
def context_manager_fixture() -> Callable[..., Any]:
    """Fixture returning context manager factory."""
    @contextmanager
    def _context(name: str) -> Generator[dict[str, Any], None, None]:
        ctx = {"name": name, "entered": True}
        try:
            yield ctx
        finally:
            ctx["entered"] = False

    return _context


# =============================================================================
# TEST CLASS WITH MARKERS AND FIXTURES (USING DEPRECATED SETUP/TEARDOWN)
# =============================================================================

@pytest.mark.integration
@pytest.mark.timeout(30)
class TestDatabaseOperations:
    """Test class for database operations with class-level fixtures."""

    # DEPRECATED: setup() should be setup_method() in pytest 8.x
    def setup(self) -> None:
        """DEPRECATED: Nose-style setup method - should be setup_method."""
        self.test_data: dict[str, Any] = {"initialized": True}

    # DEPRECATED: teardown() should be teardown_method() in pytest 8.x
    def teardown(self) -> None:
        """DEPRECATED: Nose-style teardown method - should be teardown_method."""
        self.test_data = {}

    @pytest.mark.slow
    def test_database_connection(
        self,
        module_database: DatabaseConnection,
        request_context: dict[str, Any],
    ) -> None:
        """Test database connection with multiple fixtures."""
        assert module_database.connected is True
        assert "test_database_connection" in request_context["node_name"]
        # DEPRECATED: Using funcargnames attribute
        assert "fixture_names_deprecated" in request_context

    @pytest.mark.parametrize("query,expected_count", [
        ("SELECT * FROM users", 10),
        ("SELECT * FROM products", 5),
        pytest.param("SELECT * FROM orders", 100, marks=pytest.mark.slow),
    ])
    def test_database_queries(
        self,
        module_database: DatabaseConnection,
        query: str,
        expected_count: int,
    ) -> None:
        """Parametrized test with database fixture."""
        result = module_database.execute(query)
        assert isinstance(result, list)

    def test_transaction_rollback(
        self,
        database_transaction: DatabaseConnection,
        function_user: User,
    ) -> None:
        """Test transaction rollback with yield fixture."""
        assert database_transaction.connected is True
        assert function_user.is_active is True


@pytest.mark.feature("user-management")
class TestUserManagement:
    """Test class for user management features."""

    # DEPRECATED: setup() should be setup_method()
    def setup(self) -> None:
        """DEPRECATED: Setup for user management tests."""
        self.default_role = "user"

    # DEPRECATED: teardown() should be teardown_method()
    def teardown(self) -> None:
        """DEPRECATED: Teardown for user management tests."""
        pass

    def test_user_creation_factory(
        self,
        user_factory: Callable[..., User],
    ) -> None:
        """Test user factory fixture."""
        user1 = user_factory("alice", roles=["admin"])
        user2 = user_factory("bob", email="bob@custom.com")

        assert user1.username == "alice"
        assert "admin" in user1.roles
        assert user2.email == "bob@custom.com"
        assert user1.id != user2.id

    @pytest.mark.parametrize("role", ["admin", "user", "guest"])
    def test_user_roles(
        self,
        user_factory: Callable[..., User],
        role: str,
    ) -> None:
        """Test user with different roles."""
        user = user_factory("testuser", roles=[role])
        assert role in user.roles

    # DEPRECATED: Using tmpdir instead of tmp_path
    def test_user_with_tmpdir(
        self,
        tmpdir: Any,  # DEPRECATED: should be tmp_path
        function_user: User,
    ) -> None:
        """Test using tmpdir (DEPRECATED)."""
        # DEPRECATED: tmpdir is py.path.local, should use tmp_path (pathlib.Path)
        user_file = tmpdir.join(f"user_{function_user.id}.json")
        user_file.write(json.dumps({"id": function_user.id}))
        assert user_file.check()


# =============================================================================
# TESTS WITH VARIOUS MARKERS
# =============================================================================

@pytest.mark.skip(reason="Feature not yet implemented")
def test_skipped_feature() -> None:
    """This test should be skipped."""
    assert False, "Should not run"


@pytest.mark.skipif(sys.platform == "win32", reason="Unix-only test")
def test_unix_specific(temp_directory_deprecated: Path) -> None:
    """Test that runs only on Unix systems."""
    assert temp_directory_deprecated.exists()


@pytest.mark.xfail(reason="Known bug #12345", strict=True)
def test_known_bug() -> None:
    """Test expected to fail due to known bug."""
    # pytest 6.x xfail with strict parameter
    assert 1 == 2


@pytest.mark.xfail(
    condition=sys.version_info < (3, 10),
    reason="Requires Python 3.10+",
    raises=TypeError,
)
def test_version_specific() -> None:
    """Test with conditional xfail."""
    # Uses match parameter available in pytest 6.x
    assert True


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.priority(1)
def test_multiple_markers(
    module_database: DatabaseConnection,
    class_api_client: APIClient,
) -> None:
    """Test with multiple custom markers."""
    assert module_database.connected
    assert class_api_client.base_url


@pytest.mark.flaky(reruns=3)
def test_flaky_operation(mock_server: dict[str, Any]) -> None:
    """Test marked as flaky with retry count."""
    assert mock_server["running"] is True


# =============================================================================
# TESTS USING DEPRECATED PYTEST FUNCTIONS
# =============================================================================

def test_skip_with_deprecated_msg() -> None:
    """Test using deprecated msg parameter in pytest.skip."""
    condition = False
    if condition:
        # DEPRECATED: msg= parameter should be reason=
        pytest.skip(msg="Skipping because condition is false")
    assert True


def test_fail_with_deprecated_msg() -> None:
    """Test using deprecated msg parameter in pytest.fail."""
    should_fail = False
    if should_fail:
        # DEPRECATED: msg= parameter should be reason=
        pytest.fail(msg="This test should fail")
    assert True


def test_exit_with_deprecated_msg() -> None:
    """Test demonstrating deprecated msg parameter in pytest.exit."""
    should_exit = False
    if should_exit:
        # DEPRECATED: msg= parameter should be reason=
        pytest.exit(msg="Exiting the test session early")
    assert True


def test_warns_with_deprecated_none() -> None:
    """Test using deprecated pytest.warns(None)."""
    import warnings

    # This should emit a warning
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        # DEPRECATED: pytest.warns(None) should be pytest.warns()
        with pytest.warns(None):
            # Code that might or might not emit warnings
            pass


# =============================================================================
# PARAMETRIZE TESTS
# =============================================================================

@pytest.mark.parametrize("value,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    pytest.param(4, 8, id="four-doubled"),
    pytest.param(5, 10, id="five-doubled", marks=pytest.mark.slow),
])
def test_parametrized_values(value: int, expected: int) -> None:
    """Basic parametrized test."""
    assert value * 2 == expected


@pytest.mark.parametrize("x", [1, 2, 3])
@pytest.mark.parametrize("y", [10, 20])
def test_matrix_parametrize(x: int, y: int) -> None:
    """Test with matrix parametrization (cartesian product)."""
    assert x * y in [10, 20, 30, 40, 60]


@pytest.mark.parametrize("input_data,expected_output", [
    ({"a": 1}, {"a": 1, "processed": True}),
    ({"b": 2}, {"b": 2, "processed": True}),
    pytest.param({}, {"processed": True}, marks=pytest.mark.xfail),
])
def test_parametrized_dicts(
    input_data: dict[str, Any],
    expected_output: dict[str, Any],
) -> None:
    """Parametrized test with dictionary inputs."""
    result = {**input_data, "processed": True}
    assert result == expected_output


@pytest.mark.parametrize("fixture_value", ["a", "b", "c"], indirect=["indirect_fixture"])
def test_indirect_parametrization(indirect_fixture: str, fixture_value: str) -> None:
    """Test with indirect parametrization - pytest 6.x pattern."""
    # Note: fixture_value is passed to indirect_fixture
    assert indirect_fixture.startswith("processed_")


# =============================================================================
# PYTEST.RAISES TESTS
# =============================================================================

def test_raises_basic() -> None:
    """Basic pytest.raises usage."""
    with pytest.raises(ValueError):
        raise ValueError("test error")


def test_raises_with_match() -> None:
    """pytest.raises with match parameter - pytest 6.x style."""
    with pytest.raises(ValueError, match=r".*invalid.*"):
        raise ValueError("This is invalid input")


def test_raises_with_match_regex() -> None:
    """pytest.raises with complex regex match."""
    with pytest.raises(KeyError, match=r"key_\d+"):
        raise KeyError("key_123")


def test_raises_exception_info() -> None:
    """pytest.raises accessing exception info - pytest 6.x API."""
    with pytest.raises(TypeError) as exc_info:
        raise TypeError("wrong type provided")

    assert "wrong type" in str(exc_info.value)
    assert exc_info.type is TypeError
    # pytest 6.x style: using .value attribute
    assert exc_info.value.args[0] == "wrong type provided"


def test_raises_context_manager() -> None:
    """pytest.raises as context manager with multiple assertions."""
    with pytest.raises(RuntimeError, match="operation failed") as exc_info:
        raise RuntimeError("The operation failed with code 42")

    # Access exception attributes
    assert "42" in str(exc_info.value)


def test_raises_does_not_raise() -> None:
    """Test using pytest.raises expectation - will fail if exception raised."""
    # This should NOT raise
    result = 1 + 1
    assert result == 2


# =============================================================================
# CAPSYS AND CAPFD TESTS
# =============================================================================

def test_capsys_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Test stdout capture with capsys."""
    print("Hello, stdout!")
    captured = capsys.readouterr()
    assert captured.out == "Hello, stdout!\n"
    assert captured.err == ""


def test_capsys_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Test stderr capture with capsys."""
    import sys
    print("Error message", file=sys.stderr)
    captured = capsys.readouterr()
    assert "Error message" in captured.err


def test_capsys_multiple_captures(capsys: pytest.CaptureFixture[str]) -> None:
    """Test multiple capture reads with capsys."""
    print("First")
    first = capsys.readouterr()

    print("Second")
    second = capsys.readouterr()

    assert "First" in first.out
    assert "Second" in second.out
    assert "First" not in second.out


def test_capfd_file_descriptors(capfd: pytest.CaptureFixture[str]) -> None:
    """Test file descriptor capture with capfd."""
    os.write(1, b"Direct to fd 1\n")
    os.write(2, b"Direct to fd 2\n")

    captured = capfd.readouterr()
    assert "Direct to fd 1" in captured.out
    assert "Direct to fd 2" in captured.err


def test_capsys_disabled(capsys: pytest.CaptureFixture[str]) -> None:
    """Test with capture disabled temporarily."""
    print("Captured")

    with capsys.disabled():
        # This won't be captured
        print("Not captured (visible in terminal)")

    print("Also captured")

    captured = capsys.readouterr()
    assert "Captured" in captured.out
    assert "Also captured" in captured.out
    assert "Not captured" not in captured.out


# =============================================================================
# TMPDIR AND TMPDIR_FACTORY TESTS (DEPRECATED)
# =============================================================================

# DEPRECATED: tmpdir fixture should be replaced with tmp_path
def test_tmpdir_basic(tmpdir: Any) -> None:
    """DEPRECATED: Basic tmpdir usage (should use tmp_path)."""
    test_file = tmpdir.join("test.txt")
    test_file.write("Hello, World!")

    assert test_file.check()
    assert test_file.read() == "Hello, World!"


# DEPRECATED: tmpdir fixture should be replaced with tmp_path
def test_tmpdir_subdirectory(tmpdir: Any) -> None:
    """DEPRECATED: Creating subdirectories in tmpdir (should use tmp_path)."""
    subdir = tmpdir.mkdir("subdir").mkdir("nested")

    config_file = subdir.join("config.json")
    config_file.write(json.dumps({"key": "value"}))

    assert config_file.check()
    assert json.loads(config_file.read()) == {"key": "value"}


# DEPRECATED: tmpdir_factory fixture should be replaced with tmp_path_factory
def test_tmpdir_factory_session(tmpdir_factory: Any) -> None:
    """DEPRECATED: tmpdir_factory for session-scoped temp dirs (should use tmp_path_factory)."""
    base_temp = tmpdir_factory.mktemp("session_data")

    file1 = base_temp.join("data1.txt")
    file1.write("Session data 1")

    # Create another temp directory
    base_temp2 = tmpdir_factory.mktemp("session_data")
    assert base_temp != base_temp2  # Different directories


# DEPRECATED: tmpdir_factory fixture should be replaced with tmp_path_factory
def test_tmpdir_factory_numbered(tmpdir_factory: Any) -> None:
    """DEPRECATED: tmpdir_factory with numbered=False (should use tmp_path_factory)."""
    unique_dir = tmpdir_factory.mktemp("unique", numbered=False)
    assert "unique" in str(unique_dir)


# DEPRECATED: Using tmpdir instead of tmp_path
def test_tmpdir_with_fixture(tmpdir: Any, function_user: User) -> None:
    """DEPRECATED: Combining tmpdir with other fixtures (should use tmp_path)."""
    user_file = tmpdir.join(f"user_{function_user.id}.json")
    user_data = {
        "id": function_user.id,
        "username": function_user.username,
        "email": function_user.email,
    }
    user_file.write(json.dumps(user_data))

    loaded = json.loads(user_file.read())
    assert loaded["username"] == function_user.username


# =============================================================================
# MONKEYPATCH TESTS
# =============================================================================

def test_monkeypatch_setattr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.setattr - pytest 6.x style."""
    # Monkeypatch os.getcwd
    monkeypatch.setattr(os, "getcwd", lambda: "/mocked/path")
    assert os.getcwd() == "/mocked/path"


def test_monkeypatch_setenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.setenv - pytest 6.x style."""
    monkeypatch.setenv("MY_TEST_VAR", "test_value")
    assert os.environ.get("MY_TEST_VAR") == "test_value"


def test_monkeypatch_delenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.delenv - pytest 6.x style."""
    os.environ["TO_DELETE"] = "value"
    monkeypatch.delenv("TO_DELETE")
    assert "TO_DELETE" not in os.environ


def test_monkeypatch_delenv_raising(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.delenv with raising parameter."""
    # pytest 6.x: raising parameter
    monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
    # Should not raise KeyError


def test_monkeypatch_setitem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.setitem - pytest 6.x style."""
    test_dict = {"original": "value"}
    monkeypatch.setitem(test_dict, "new_key", "new_value")
    assert test_dict["new_key"] == "new_value"


def test_monkeypatch_delitem(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.delitem - pytest 6.x style."""
    test_dict = {"to_delete": "value", "keep": "value"}
    monkeypatch.delitem(test_dict, "to_delete")
    assert "to_delete" not in test_dict
    assert "keep" in test_dict


def test_monkeypatch_syspath(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test monkeypatch.syspath_prepend - pytest 6.x style."""
    monkeypatch.syspath_prepend("/custom/path")
    assert sys.path[0] == "/custom/path"


# DEPRECATED: Using tmpdir instead of tmp_path in combined fixture
def test_monkeypatch_chdir_tmpdir(monkeypatch: pytest.MonkeyPatch, tmpdir: Any) -> None:
    """DEPRECATED: Test monkeypatch.chdir with tmpdir (should use tmp_path)."""
    original_cwd = os.getcwd()
    monkeypatch.chdir(tmpdir)
    assert os.getcwd() == str(tmpdir)
    # Will be restored after test


def test_monkeypatch_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test using monkeypatch with context pattern."""
    original_value = os.environ.get("CONTEXT_VAR")

    monkeypatch.setenv("CONTEXT_VAR", "in_context")
    assert os.environ["CONTEXT_VAR"] == "in_context"

    # Undo to restore
    monkeypatch.undo()
    assert os.environ.get("CONTEXT_VAR") == original_value


# =============================================================================
# COMPLEX INTEGRATION TESTS WITH DEPRECATED PATTERNS
# =============================================================================

@pytest.mark.integration
@pytest.mark.database
class TestComplexIntegration:
    """Complex integration tests combining multiple patterns."""

    # DEPRECATED: setup() should be setup_method()
    def setup(self) -> None:
        """DEPRECATED: Setup for integration tests."""
        self.integration_state = {"setup": True}

    # DEPRECATED: teardown() should be teardown_method()
    def teardown(self) -> None:
        """DEPRECATED: Teardown for integration tests."""
        self.integration_state = {}

    @pytest.mark.parametrize("db_type", ["sqlite", "postgres"])
    def test_database_integration_with_tmpdir(
        self,
        database_type: str,
        module_database: DatabaseConnection,
        user_factory: Callable[..., User],
        tmpdir: Any,  # DEPRECATED: should be tmp_path
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Complex test with many fixtures and tmpdir (DEPRECATED)."""
        # Setup environment
        monkeypatch.setenv("DB_TYPE", database_type)

        # Create test data
        users = [user_factory(f"user_{i}") for i in range(5)]

        # Write to temp file using deprecated tmpdir
        data_file = tmpdir.join("users.json")  # DEPRECATED: should use tmp_path /
        data_file.write(json.dumps([{"id": u.id, "name": u.username} for u in users]))

        # Log output
        print(f"Created {len(users)} users for {database_type}")

        # Verify
        captured = capsys.readouterr()
        assert f"{len(users)} users" in captured.out
        assert data_file.check()

    def test_with_raises_and_fixtures(
        self,
        mock_external_service: MagicMock,
        api_response_factory: Callable[..., dict[str, Any]],
    ) -> None:
        """Test combining raises with fixtures."""
        # Test error response
        error_response = api_response_factory(status=500, error="Internal Server Error")

        with pytest.raises(ValueError, match="server error"):
            if error_response["status"] >= 500:
                raise ValueError("Encountered server error")

    @pytest.mark.xfail(reason="Flaky network test", strict=False)
    def test_network_integration(
        self,
        class_api_client: APIClient,
        mock_server: dict[str, Any],
    ) -> None:
        """Network integration test marked as potentially flaky."""
        assert mock_server["running"]
        response = class_api_client.get("/health")
        assert response["status"] == "ok"


# =============================================================================
# ASYNC TESTS (pytest 6.x patterns)
# =============================================================================

@pytest.mark.asyncio
async def test_async_basic() -> None:
    """Basic async test - pytest 6.x style."""
    result = await asyncio.sleep(0.1, result="done")
    assert result == "done"


@pytest.mark.asyncio
async def test_async_with_fixture(async_client: AsyncMock) -> None:
    """Async test with async mock fixture."""
    result = await async_client.get("/api/data")
    assert result["async"] is True


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_async_timeout() -> None:
    """Async test with timeout marker."""
    await asyncio.sleep(0.1)
    assert True


# =============================================================================
# PLUGIN-LIKE FIXTURE PATTERNS
# =============================================================================

# DEPRECATED: @pytest.yield_fixture should be @pytest.fixture
@pytest.yield_fixture
def plugin_like_fixture(request: FixtureRequest) -> Generator[dict[str, Any], None, None]:
    """DEPRECATED: Fixture using @pytest.yield_fixture decorator."""
    state = {
        "setup_calls": 0,
        "teardown_calls": 0,
        "markers": list(request.node.iter_markers()),
    }

    # Setup hook
    state["setup_calls"] += 1

    yield state

    # Teardown hook
    state["teardown_calls"] += 1


@pytest.fixture
def fixture_with_finalizer(request: FixtureRequest) -> dict[str, Any]:
    """Fixture using request.addfinalizer - pytest 6.x pattern."""
    state = {"finalized": False, "data": []}

    def finalizer() -> None:
        state["finalized"] = True
        state["data"].clear()

    request.addfinalizer(finalizer)
    return state


@pytest.fixture
def fixture_getfixturevalue(request: FixtureRequest) -> Callable[[str], Any]:
    """Fixture that can dynamically get other fixtures."""
    def _get(name: str) -> Any:
        return request.getfixturevalue(name)
    return _get


def test_plugin_fixture(plugin_like_fixture: dict[str, Any]) -> None:
    """Test plugin-like fixture."""
    assert plugin_like_fixture["setup_calls"] == 1


def test_finalizer_fixture(fixture_with_finalizer: dict[str, Any]) -> None:
    """Test fixture with finalizer."""
    fixture_with_finalizer["data"].append("test")
    assert len(fixture_with_finalizer["data"]) == 1


def test_getfixturevalue(fixture_getfixturevalue: Callable[[str], Any]) -> None:
    """Test dynamic fixture retrieval - pytest 6.x pattern."""
    user = fixture_getfixturevalue("function_user")
    assert isinstance(user, User)


# =============================================================================
# EDGE CASES AND STRESS PATTERNS WITH DEPRECATED PATTERNS
# =============================================================================

@pytest.mark.parametrize("count", [10, 50, 100])
def test_many_assertions(count: int, user_factory: Callable[..., User]) -> None:
    """Test with many assertions."""
    users = [user_factory(f"user_{i}") for i in range(count)]

    for i, user in enumerate(users):
        assert user.id == i + 1
        assert user.username == f"user_{i}"
        assert user.is_active is True


# DEPRECATED: Using tmpdir and deprecated fixtures
def test_deeply_nested_fixtures_with_deprecated(
    complex_nested_fixture_with_tmpdir: dict[str, Any],
    plugin_like_fixture: dict[str, Any],
    fixture_getfixturevalue: Callable[[str], Any],
    context_manager_fixture: Callable[..., Any],
    tmpdir: Any,  # DEPRECATED
) -> None:
    """Test with deeply nested fixture dependencies using deprecated patterns."""
    assert complex_nested_fixture_with_tmpdir["config"] is not None
    assert plugin_like_fixture["setup_calls"] >= 1

    # Use context manager fixture
    with context_manager_fixture("test_context") as ctx:
        assert ctx["entered"] is True

    # Dynamic fixture
    user = fixture_getfixturevalue("function_user")
    assert user is not None

    # Write to deprecated tmpdir
    test_file = tmpdir.join("nested_test.txt")
    test_file.write("nested test content")


@pytest.mark.parametrize("iteration", range(5))
def test_repeated_execution_with_tmpdir(
    iteration: int,
    tmpdir: Any,  # DEPRECATED: should be tmp_path
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test repeated execution with deprecated tmpdir."""
    file_path = tmpdir.join(f"iteration_{iteration}.txt")
    file_path.write(f"Iteration {iteration}")

    print(f"Completed iteration {iteration}")

    captured = capsys.readouterr()
    assert f"iteration {iteration}" in captured.out


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    # DEPRECATED: setup() should be setup_method()
    def setup(self) -> None:
        """DEPRECATED: Setup for edge case tests."""
        self.edge_state = {}

    @pytest.mark.parametrize("value", [None, "", 0, False, [], {}])
    def test_falsy_values(self, value: Any) -> None:
        """Test with various falsy values."""
        assert not value  # All should be falsy

    @pytest.mark.parametrize("exception_type,message", [
        (ValueError, "value error"),
        (TypeError, "type error"),
        (KeyError, "key error"),
        (RuntimeError, "runtime error"),
    ])
    def test_various_exceptions(self, exception_type: type[Exception], message: str) -> None:
        """Test raising various exception types."""
        with pytest.raises(exception_type, match=message):
            raise exception_type(message)

    # DEPRECATED: Using tmpdir instead of tmp_path
    def test_with_all_capture_fixtures(
        self,
        capsys: pytest.CaptureFixture[str],
        tmpdir: Any,  # DEPRECATED: should be tmp_path
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test using multiple built-in fixtures with deprecated tmpdir."""
        monkeypatch.setenv("TEST_MODE", "true")

        log_file = tmpdir.join("log.txt")
        log_file.write("Test log")

        print("Test output")

        captured = capsys.readouterr()
        assert "Test output" in captured.out
        assert os.environ.get("TEST_MODE") == "true"
        assert log_file.read() == "Test log"


# =============================================================================
# CONFTEST PATTERN SIMULATION (in-file for stress test)
# =============================================================================

# These would normally be in conftest.py but included here for completeness

# DEPRECATED: @pytest.yield_fixture should be @pytest.fixture
@pytest.yield_fixture(scope="session")
def session_wide_resource() -> Generator[dict[str, Any], None, None]:
    """DEPRECATED: Session-wide resource using @pytest.yield_fixture."""
    resource = {"type": "session", "initialized": True, "usage_count": 0}
    yield resource
    resource["initialized"] = False


@pytest.fixture
def conftest_style_fixture(
    session_wide_resource: dict[str, Any],
    request: FixtureRequest,
) -> dict[str, Any]:
    """Fixture simulating conftest.py pattern."""
    session_wide_resource["usage_count"] += 1
    return {
        "session_resource": session_wide_resource,
        "test_name": request.node.name,
    }


def test_conftest_pattern(conftest_style_fixture: dict[str, Any]) -> None:
    """Test using conftest-style fixtures."""
    assert conftest_style_fixture["session_resource"]["initialized"] is True
    assert conftest_style_fixture["session_resource"]["usage_count"] >= 1


# =============================================================================
# FINAL STRESS TEST: COMBINING EVERYTHING WITH DEPRECATED PATTERNS
# =============================================================================

@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.smoke
@pytest.mark.priority(1)
@pytest.mark.feature("stress-test")
@pytest.mark.timeout(60)
class TestUltimateStress:
    """Ultimate stress test combining all patterns including deprecated ones."""

    # DEPRECATED: setup() should be setup_method()
    def setup(self) -> None:
        """DEPRECATED: Setup for ultimate stress tests."""
        self.stress_data = {"initialized": True}

    # DEPRECATED: teardown() should be teardown_method()
    def teardown(self) -> None:
        """DEPRECATED: Teardown for ultimate stress tests."""
        self.stress_data = {}

    @pytest.mark.parametrize("scenario", [
        pytest.param("basic", id="basic-scenario"),
        pytest.param("complex", id="complex-scenario", marks=pytest.mark.slow),
        pytest.param("edge", id="edge-scenario", marks=[pytest.mark.xfail, pytest.mark.slow]),
    ])
    def test_ultimate_combination(
        self,
        scenario: str,
        session_config: dict[str, Any],
        module_database: DatabaseConnection,
        class_api_client: APIClient,
        function_user: User,
        user_factory: Callable[..., User],
        api_response_factory: Callable[..., dict[str, Any]],
        temp_directory_deprecated: Path,  # Using deprecated yield_fixture
        tmpdir: Any,  # DEPRECATED: should be tmp_path
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
        request_context: dict[str, Any],
        complex_nested_fixture_with_tmpdir: dict[str, Any],
        conftest_style_fixture: dict[str, Any],
    ) -> None:
        """The ultimate stress test combining all fixture types and deprecated patterns."""
        # Environment setup
        monkeypatch.setenv("STRESS_SCENARIO", scenario)

        # Create multiple users
        users = [user_factory(f"stress_user_{i}") for i in range(10)]

        # Create API responses
        responses = [
            api_response_factory(status=code, data={"scenario": scenario})
            for code in [200, 201, 400, 404, 500]
        ]

        # File operations using deprecated tmpdir
        data_file = tmpdir.join(f"{scenario}_data.json")
        data_file.write(json.dumps({
            "scenario": scenario,
            "user_count": len(users),
            "response_count": len(responses),
        }))

        # Console output
        print(f"Running scenario: {scenario}")
        print(f"Users created: {len(users)}")
        print(f"Responses generated: {len(responses)}")

        # Assertions
        captured = capsys.readouterr()
        assert scenario in captured.out
        assert data_file.check()
        assert module_database.connected
        assert function_user.is_active
        assert temp_directory_deprecated.exists()

        # Test raises if edge scenario
        if scenario == "edge":
            with pytest.raises(ValueError, match="edge case"):
                raise ValueError("This is an edge case scenario")

    def test_with_all_deprecated_patterns(
        self,
        tmpdir: Any,  # DEPRECATED
        tmpdir_factory: Any,  # DEPRECATED
        request_context: dict[str, Any],  # Uses deprecated funcargnames
        plugin_like_fixture: dict[str, Any],  # Uses deprecated @pytest.yield_fixture
    ) -> None:
        """Test combining all deprecated patterns for maximum migration coverage."""
        # Using deprecated tmpdir
        test_file = tmpdir.join("all_deprecated.txt")
        test_file.write("testing all deprecated patterns")

        # Using deprecated tmpdir_factory
        extra_dir = tmpdir_factory.mktemp("extra")
        extra_file = extra_dir.join("extra.txt")
        extra_file.write("extra content")

        # Check deprecated funcargnames (now fixturenames)
        assert "fixture_names_deprecated" in request_context

        # Check deprecated yield_fixture pattern
        assert plugin_like_fixture["setup_calls"] == 1

        # Would use deprecated msg= parameter if needed
        # pytest.skip(msg="skipping") - DEPRECATED: should be reason=
        # pytest.fail(msg="failing") - DEPRECATED: should be reason=

        assert test_file.check()
        assert extra_file.check()

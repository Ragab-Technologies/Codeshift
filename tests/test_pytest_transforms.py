"""Tests for pytest 6.x to 7.x/8.x transforms."""

from codeshift.migrator.transforms.pytest_transformer import transform_pytest


class TestYieldFixtureTransform:
    """Tests for @pytest.yield_fixture to @pytest.fixture transformation."""

    def test_yield_fixture_simple(self):
        """Test transforming @pytest.yield_fixture to @pytest.fixture."""
        code = """
import pytest

@pytest.yield_fixture
def my_fixture():
    yield "value"
"""
        transformed, changes = transform_pytest(code)

        assert "@pytest.fixture" in transformed
        assert "@pytest.yield_fixture" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "yield_fixture_to_fixture"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_yield_fixture_with_scope(self):
        """Test transforming @pytest.yield_fixture with scope parameter."""
        code = """
import pytest

@pytest.yield_fixture(scope="module")
def module_fixture():
    yield "value"
"""
        transformed, changes = transform_pytest(code)

        assert '@pytest.fixture(scope="module")' in transformed
        assert "@pytest.yield_fixture" not in transformed
        assert len(changes) == 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_yield_fixture_with_multiple_params(self):
        """Test transforming @pytest.yield_fixture with multiple parameters."""
        code = """
import pytest

@pytest.yield_fixture(scope="session", autouse=True)
def session_fixture():
    yield "value"
"""
        transformed, changes = transform_pytest(code)

        assert "@pytest.fixture(" in transformed
        assert "scope=" in transformed
        assert "autouse=" in transformed
        assert "@pytest.yield_fixture" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestTmpdirTransform:
    """Tests for tmpdir to tmp_path fixture transformation."""

    def test_tmpdir_parameter(self):
        """Test transforming tmpdir fixture parameter to tmp_path."""
        code = """
def test_file_creation(tmpdir):
    p = tmpdir.mkdir("sub").join("file.txt")
    p.write("content")
"""
        transformed, changes = transform_pytest(code)

        assert "tmp_path" in transformed
        assert "def test_file_creation(tmp_path):" in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "tmpdir_to_tmp_path"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_tmpdir_factory_parameter(self):
        """Test transforming tmpdir_factory fixture parameter to tmp_path_factory."""
        code = """
import pytest

@pytest.fixture(scope="session")
def base_dir(tmpdir_factory):
    return tmpdir_factory.mktemp("data")
"""
        transformed, changes = transform_pytest(code)

        assert "tmp_path_factory" in transformed
        assert "def base_dir(tmp_path_factory):" in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "tmpdir_factory_to_tmp_path_factory"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_tmpdir_with_other_fixtures(self):
        """Test transforming tmpdir with other fixtures preserved."""
        code = """
def test_with_multiple_fixtures(tmpdir, request, capsys):
    print("testing")
"""
        transformed, changes = transform_pytest(code)

        assert "def test_with_multiple_fixtures(tmp_path, request, capsys):" in transformed
        assert len(changes) == 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestMsgToReasonTransform:
    """Tests for msg parameter to reason transformation."""

    def test_skip_msg_to_reason(self):
        """Test transforming pytest.skip(msg=...) to pytest.skip(reason=...)."""
        code = """
import pytest

def test_something():
    pytest.skip(msg="Not implemented yet")
"""
        transformed, changes = transform_pytest(code)

        assert 'pytest.skip(reason="Not implemented yet")' in transformed
        assert "msg=" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "skip_msg_to_reason"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_fail_msg_to_reason(self):
        """Test transforming pytest.fail(msg=...) to pytest.fail(reason=...)."""
        code = """
import pytest

def test_something():
    pytest.fail(msg="Test failed intentionally")
"""
        transformed, changes = transform_pytest(code)

        assert 'pytest.fail(reason="Test failed intentionally")' in transformed
        assert "msg=" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "fail_msg_to_reason"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_exit_msg_to_reason(self):
        """Test transforming pytest.exit(msg=...) to pytest.exit(reason=...)."""
        code = """
import pytest

def test_something():
    pytest.exit(msg="Exiting test session")
"""
        transformed, changes = transform_pytest(code)

        assert 'pytest.exit(reason="Exiting test session")' in transformed
        assert "msg=" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "exit_msg_to_reason"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestWarnsNoneTransform:
    """Tests for pytest.warns(None) transformation."""

    def test_warns_none_to_warns(self):
        """Test transforming pytest.warns(None) to pytest.warns()."""
        code = """
import pytest

def test_no_warnings():
    with pytest.warns(None):
        func_that_should_not_warn()
"""
        transformed, changes = transform_pytest(code)

        assert "pytest.warns():" in transformed
        assert "pytest.warns(None)" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "warns_none_to_warns"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestSetupTeardownTransform:
    """Tests for setup/teardown method renaming in test classes."""

    def test_setup_to_setup_method(self):
        """Test transforming setup() to setup_method() in test class."""
        code = """
class TestMyClass:
    def setup(self):
        self.resource = "initialized"

    def test_something(self):
        assert self.resource == "initialized"
"""
        transformed, changes = transform_pytest(code)

        assert "def setup_method(self):" in transformed
        assert "def setup(self):" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "setup_to_setup_method"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_teardown_to_teardown_method(self):
        """Test transforming teardown() to teardown_method() in test class."""
        code = """
class TestMyClass:
    def teardown(self):
        self.resource = None

    def test_something(self):
        pass
"""
        transformed, changes = transform_pytest(code)

        assert "def teardown_method(self):" in transformed
        assert "def teardown(self):" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "teardown_to_teardown_method"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_setup_in_non_test_class_unchanged(self):
        """Test that setup() in non-test classes is not changed."""
        code = """
class MyHelper:
    def setup(self):
        self.data = []

    def process(self):
        pass
"""
        transformed, changes = transform_pytest(code)

        # Should not be transformed - not a test class
        assert "def setup(self):" in transformed
        assert len(changes) == 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestFspathToPathTransform:
    """Tests for .fspath to .path transformation."""

    def test_fspath_to_path(self):
        """Test transforming .fspath to .path."""
        code = """
def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".yaml":
        return YamlFile.from_parent(parent, path=parent.fspath)
"""
        transformed, changes = transform_pytest(code)

        assert ".path" in transformed
        assert ".fspath" not in transformed
        assert any(c.transform_name == "fspath_to_path" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestFuncargnamesToFixturenamesTransform:
    """Tests for funcargnames to fixturenames transformation."""

    def test_funcargnames_to_fixturenames(self):
        """Test transforming .funcargnames to .fixturenames."""
        code = """
def test_fixture_info(request):
    fixtures = request.funcargnames
    print(fixtures)
"""
        transformed, changes = transform_pytest(code)

        assert ".fixturenames" in transformed
        assert ".funcargnames" not in transformed
        assert len(changes) == 1
        assert changes[0].transform_name == "funcargnames_to_fixturenames"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestHookParameterTransforms:
    """Tests for pytest hook parameter renaming."""

    def test_pytest_collect_file_path_to_file_path(self):
        """Test transforming pytest_collect_file path parameter to file_path."""
        code = """
def pytest_collect_file(parent, path):
    if path.suffix == ".yaml":
        return YamlFile.from_parent(parent, path=path)
"""
        transformed, changes = transform_pytest(code)

        assert "def pytest_collect_file(parent, file_path):" in transformed
        assert len(changes) == 1
        assert "file_path" in changes[0].transform_name

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_pytest_ignore_collect_path_to_collection_path(self):
        """Test transforming pytest_ignore_collect path parameter to collection_path."""
        code = """
def pytest_ignore_collect(path, config):
    if "legacy" in str(path):
        return True
"""
        transformed, changes = transform_pytest(code)

        assert "def pytest_ignore_collect(collection_path, config):" in transformed
        assert len(changes) == 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_pytest_pycollect_makemodule_path_to_module_path(self):
        """Test transforming pytest_pycollect_makemodule path parameter to module_path."""
        code = """
def pytest_pycollect_makemodule(path, parent):
    return Module.from_parent(parent, path=path)
"""
        transformed, changes = transform_pytest(code)

        assert "def pytest_pycollect_makemodule(module_path, parent):" in transformed
        assert len(changes) == 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestMultipleTransforms:
    """Tests for multiple transformations in the same file."""

    def test_comprehensive_migration(self):
        """Test multiple pytest migrations in one file."""
        code = """
import pytest

@pytest.yield_fixture(scope="function")
def my_fixture(tmpdir):
    p = tmpdir.join("test.txt")
    yield p


class TestSomething:
    def setup(self):
        self.data = []

    def teardown(self):
        self.data = None

    def test_skip_example(self):
        pytest.skip(msg="Not ready")

    def test_warnings(self):
        with pytest.warns(None):
            pass


def pytest_collect_file(parent, path):
    if path.suffix == ".yaml":
        return None
"""
        transformed, changes = transform_pytest(code)

        # Check all transformations applied
        assert "@pytest.fixture" in transformed
        assert "@pytest.yield_fixture" not in transformed
        assert "tmp_path" in transformed
        assert "tmpdir" not in transformed or "tmp_path" in transformed
        assert "setup_method" in transformed
        assert "teardown_method" in transformed
        assert "reason=" in transformed
        assert "msg=" not in transformed
        assert "pytest.warns():" in transformed
        assert "file_path" in transformed

        # Should have multiple changes
        assert len(changes) >= 6

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that unrelated code is not transformed."""
        code = """
import pytest

def test_normal():
    \"\"\"A normal test with no deprecated patterns.\"\"\"
    assert 1 + 1 == 2


@pytest.fixture
def modern_fixture(tmp_path):
    return tmp_path / "test.txt"


class TestModern:
    def setup_method(self):
        pass

    def teardown_method(self):
        pass

    def test_skip(self):
        pytest.skip(reason="Already using reason parameter")
"""
        transformed, changes = transform_pytest(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

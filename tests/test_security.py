"""Tests for security hardening: path validation, arg sanitization, state validation."""

import json
import stat
from pathlib import Path

import pytest

from codeshift.cli.commands.upgrade import _validate_state, load_state, save_state
from codeshift.utils.path_safety import validate_file_within_project
from codeshift.validator.test_runner import TestRunner

# ---------------------------------------------------------------------------
# validate_file_within_project
# ---------------------------------------------------------------------------


class TestValidateFileWithinProject:
    def test_valid_path_inside_project(self, tmp_path: Path) -> None:
        child = tmp_path / "src" / "main.py"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        result = validate_file_within_project(child, tmp_path)
        assert result == child.resolve()

    def test_relative_path_inside_project(self, tmp_path: Path) -> None:
        (tmp_path / "file.py").touch()
        # Use a relative-looking path that still resolves inside
        result = validate_file_within_project(tmp_path / "." / "file.py", tmp_path)
        assert result == (tmp_path / "file.py").resolve()

    def test_path_outside_project_raises(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.py"
        with pytest.raises(ValueError, match="outside the project directory"):
            validate_file_within_project(outside, tmp_path)

    def test_traversal_attack_raises(self, tmp_path: Path) -> None:
        malicious = tmp_path / ".." / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="outside the project directory"):
            validate_file_within_project(malicious, tmp_path)

    def test_absolute_path_outside_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="outside the project directory"):
            validate_file_within_project(Path("/etc/passwd"), tmp_path)

    def test_returns_resolved_path(self, tmp_path: Path) -> None:
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        target = subdir / "code.py"
        target.touch()
        result = validate_file_within_project(target, tmp_path)
        assert result.is_absolute()
        assert not str(result).endswith("/.")


# ---------------------------------------------------------------------------
# TestRunner._validate_extra_args
# ---------------------------------------------------------------------------


class TestValidateExtraArgs:
    def test_allows_safe_single_char_flags(self) -> None:
        args = ["-v", "-q", "-s", "-x"]
        assert TestRunner._validate_extra_args(args) == args

    def test_allows_traceback_styles(self) -> None:
        for style in ("short", "long", "line", "no", "auto"):
            assert TestRunner._validate_extra_args([f"--tb={style}"]) == [f"--tb={style}"]

    def test_allows_maxfail(self) -> None:
        assert TestRunner._validate_extra_args(["--maxfail=3"]) == ["--maxfail=3"]

    def test_allows_collect_only(self) -> None:
        assert TestRunner._validate_extra_args(["--collect-only"]) == ["--collect-only"]
        assert TestRunner._validate_extra_args(["--co"]) == ["--co"]

    def test_allows_import_mode(self) -> None:
        assert TestRunner._validate_extra_args(["--import-mode=importlib"]) == [
            "--import-mode=importlib"
        ]

    def test_allows_no_header(self) -> None:
        assert TestRunner._validate_extra_args(["--no-header"]) == ["--no-header"]

    def test_allows_timeout(self) -> None:
        assert TestRunner._validate_extra_args(["--timeout=60"]) == ["--timeout=60"]

    def test_rejects_shell_metachar_semicolon(self) -> None:
        assert TestRunner._validate_extra_args(["; rm -rf /"]) == []

    def test_rejects_shell_metachar_pipe(self) -> None:
        assert TestRunner._validate_extra_args(["| cat /etc/passwd"]) == []

    def test_rejects_shell_metachar_ampersand(self) -> None:
        assert TestRunner._validate_extra_args(["& whoami"]) == []

    def test_rejects_shell_metachar_dollar(self) -> None:
        assert TestRunner._validate_extra_args(["$(whoami)"]) == []

    def test_rejects_shell_metachar_backtick(self) -> None:
        assert TestRunner._validate_extra_args(["`id`"]) == []

    def test_rejects_unrecognised_flags(self) -> None:
        assert TestRunner._validate_extra_args(["--evil-flag", "--random"]) == []

    def test_mixed_safe_and_unsafe(self) -> None:
        result = TestRunner._validate_extra_args(["-v", "; rm -rf /", "--tb=short", "`id`"])
        assert result == ["-v", "--tb=short"]

    def test_empty_list(self) -> None:
        assert TestRunner._validate_extra_args([]) == []


# ---------------------------------------------------------------------------
# TestRunner._validate_specific_tests
# ---------------------------------------------------------------------------


class TestValidateSpecificTests:
    def test_valid_test_path(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").touch()
        result = TestRunner._validate_specific_tests(["tests/test_foo.py"], tmp_path)
        assert result == ["tests/test_foo.py"]

    def test_rejects_traversal_path(self, tmp_path: Path) -> None:
        result = TestRunner._validate_specific_tests(["../../etc/passwd"], tmp_path)
        assert result == []

    def test_rejects_shell_metachar(self, tmp_path: Path) -> None:
        result = TestRunner._validate_specific_tests(["; rm -rf /"], tmp_path)
        assert result == []

    def test_rejects_absolute_outside_path(self, tmp_path: Path) -> None:
        result = TestRunner._validate_specific_tests(["/etc/passwd"], tmp_path)
        assert result == []

    def test_mixed_valid_and_invalid(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").touch()
        result = TestRunner._validate_specific_tests(
            ["tests/test_a.py", "../../evil.py", "| whoami"], tmp_path
        )
        assert result == ["tests/test_a.py"]

    def test_empty_list(self, tmp_path: Path) -> None:
        assert TestRunner._validate_specific_tests([], tmp_path) == []


# ---------------------------------------------------------------------------
# _validate_state
# ---------------------------------------------------------------------------


class TestValidateState:
    @staticmethod
    def _make_state(project_path: Path) -> dict:
        return {
            "library": "pydantic",
            "target_version": "2.0",
            "results": [
                {
                    "file_path": str(project_path / "models.py"),
                    "transformed_code": "# migrated",
                    "change_count": 1,
                }
            ],
        }

    def test_valid_state(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        assert _validate_state(state, tmp_path) == state

    def test_missing_library_key(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        del state["library"]
        assert _validate_state(state, tmp_path) is None

    def test_missing_target_version(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        del state["target_version"]
        assert _validate_state(state, tmp_path) is None

    def test_missing_results_key(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        del state["results"]
        assert _validate_state(state, tmp_path) is None

    def test_results_not_a_list(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        state["results"] = "not a list"
        assert _validate_state(state, tmp_path) is None

    def test_result_not_a_dict(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        state["results"] = ["not a dict"]
        assert _validate_state(state, tmp_path) is None

    def test_result_missing_file_path(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        del state["results"][0]["file_path"]
        assert _validate_state(state, tmp_path) is None

    def test_result_missing_transformed_code(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        del state["results"][0]["transformed_code"]
        assert _validate_state(state, tmp_path) is None

    def test_file_path_outside_project(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        state["results"][0]["file_path"] = "/etc/passwd"
        assert _validate_state(state, tmp_path) is None

    def test_file_path_traversal(self, tmp_path: Path) -> None:
        state = self._make_state(tmp_path)
        state["results"][0]["file_path"] = str(tmp_path / ".." / ".." / "etc" / "passwd")
        assert _validate_state(state, tmp_path) is None

    def test_empty_results_is_valid(self, tmp_path: Path) -> None:
        state = {"library": "pydantic", "target_version": "2.0", "results": []}
        assert _validate_state(state, tmp_path) == state


# ---------------------------------------------------------------------------
# load_state / save_state
# ---------------------------------------------------------------------------


class TestLoadState:
    def test_returns_none_when_no_state_file(self, tmp_path: Path) -> None:
        assert load_state(tmp_path) is None

    def test_loads_valid_state(self, tmp_path: Path) -> None:
        state = {
            "library": "pydantic",
            "target_version": "2.0",
            "results": [
                {
                    "file_path": str(tmp_path / "models.py"),
                    "transformed_code": "# ok",
                }
            ],
        }
        state_dir = tmp_path / ".codeshift"
        state_dir.mkdir()
        (state_dir / "state.json").write_text(json.dumps(state))
        loaded = load_state(tmp_path)
        assert loaded is not None
        assert loaded["library"] == "pydantic"

    def test_returns_none_for_invalid_json(self, tmp_path: Path) -> None:
        state_dir = tmp_path / ".codeshift"
        state_dir.mkdir()
        (state_dir / "state.json").write_text("not json {{{")
        assert load_state(tmp_path) is None

    def test_returns_none_for_traversal_in_state(self, tmp_path: Path) -> None:
        state = {
            "library": "pydantic",
            "target_version": "2.0",
            "results": [
                {
                    "file_path": "/etc/passwd",
                    "transformed_code": "evil",
                }
            ],
        }
        state_dir = tmp_path / ".codeshift"
        state_dir.mkdir()
        (state_dir / "state.json").write_text(json.dumps(state))
        assert load_state(tmp_path) is None


class TestSaveState:
    def test_creates_state_file(self, tmp_path: Path) -> None:
        state = {"library": "pydantic", "target_version": "2.0", "results": []}
        save_state(tmp_path, state)
        state_file = tmp_path / ".codeshift" / "state.json"
        assert state_file.exists()
        assert json.loads(state_file.read_text()) == state

    def test_sets_restrictive_dir_permissions(self, tmp_path: Path) -> None:
        save_state(tmp_path, {"library": "x", "target_version": "1", "results": []})
        state_dir = tmp_path / ".codeshift"
        mode = stat.S_IMODE(state_dir.stat().st_mode)
        assert mode == 0o700

    def test_sets_restrictive_file_permissions(self, tmp_path: Path) -> None:
        save_state(tmp_path, {"library": "x", "target_version": "1", "results": []})
        state_file = tmp_path / ".codeshift" / "state.json"
        mode = stat.S_IMODE(state_file.stat().st_mode)
        assert mode == 0o600

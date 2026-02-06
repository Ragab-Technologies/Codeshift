"""Tests for authentication commands."""

from codeshift.cli.commands.auth import _format_api_key_hint


class TestFormatApiKeyHint:
    """Tests for _format_api_key_hint."""

    def test_long_key_is_masked(self) -> None:
        """Keys longer than 10 chars show first 7 and last 4 with ellipsis."""
        key = "pyr_abc1234567890xyz"
        result = _format_api_key_hint(key)
        assert "pyr_abc...0xyz" in result
        # Full key must NOT appear
        assert key not in result

    def test_short_key_shown_as_is(self) -> None:
        """Keys with 10 or fewer chars are not masked."""
        key = "short_key"
        result = _format_api_key_hint(key)
        assert key in result

    def test_exactly_10_chars_not_masked(self) -> None:
        """A key of exactly 10 characters should not be masked."""
        key = "abcdefghij"
        assert len(key) == 10
        result = _format_api_key_hint(key)
        assert key in result

    def test_exactly_11_chars_is_masked(self) -> None:
        """A key of exactly 11 characters should be masked."""
        key = "abcdefghijk"
        assert len(key) == 11
        result = _format_api_key_hint(key)
        assert key not in result
        assert "abcdefg...hijk" in result

    def test_contains_cicd_hint(self) -> None:
        """Output includes CI/CD usage instructions."""
        result = _format_api_key_hint("pyr_abc1234567890xyz")
        assert "CI/CD" in result
        assert "CODESHIFT_API_KEY" in result
        assert "GitHub" in result

    def test_empty_key(self) -> None:
        """An empty key is returned as-is (not masked)."""
        result = _format_api_key_hint("")
        assert "API Key:" in result

    def test_single_char_key(self) -> None:
        """A single character key is not masked."""
        result = _format_api_key_hint("x")
        assert "x" in result

    def test_output_contains_api_key_label(self) -> None:
        """Output always starts with the API Key label."""
        result = _format_api_key_hint("anything")
        assert "API Key:" in result

"""Tests for version module."""

from ask.version import VERSION, get_version_string


def test_version_constant() -> None:
    """VERSION constant is defined."""
    assert VERSION == "0.1.0"


def test_get_version_string_dev() -> None:
    """Development version string format."""
    # When placeholders are not replaced, should show dev version
    version_str = get_version_string()
    assert "ask" in version_str
    assert VERSION in version_str


def test_version_string_contains_version() -> None:
    """Version string contains the version number."""
    version_str = get_version_string()
    assert "0.1.0" in version_str

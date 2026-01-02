"""Version information for ask."""

from __future__ import annotations

VERSION = "0.1.0"
GIT_COMMIT = "__GIT_COMMIT__"  # Replaced by CI during build
BUILD_DATE = "__BUILD_DATE__"  # Replaced by CI during build


def get_version_string() -> str:
    """Get formatted version string for display.

    Returns development version if placeholders not replaced,
    otherwise returns full version with commit and date.
    """
    if GIT_COMMIT.startswith("__"):
        return f"ask {VERSION}-dev"
    return f"ask {VERSION} ({GIT_COMMIT[:7]}, {BUILD_DATE})"

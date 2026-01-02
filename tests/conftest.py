"""Pytest configuration and fixtures."""

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


def load_fixture(fixtures_dir: Path, name: str) -> str:
    """Load a fixture file."""
    return (fixtures_dir / name).read_text(encoding="utf-8")


@pytest.fixture
def make_session(tmp_path: Path) -> Callable[..., Path]:
    """Factory fixture for creating test session files.

    Returns a function that creates session files with customizable content.

    Args:
        ai_content: Content for the AI turn (default: "Answer.")
        has_marker: Whether to include the _ input marker (default: True)
        user_text: Optional user text before the marker (default: "")
        include_ai_turn: Whether to include an AI turn (default: True)

    Returns:
        Path to the created session file
    """

    def _make(
        ai_content: str = "Answer.",
        has_marker: bool = True,
        user_text: str = "",
        include_ai_turn: bool = True,
    ) -> Path:
        marker = "\n_\n" if has_marker else "\n"
        user_content = f"\n{user_text}\n" if user_text else ""

        if include_ai_turn:
            session_content = f"""# [1] Human

Question?

# [2] AI

``````markdown
{ai_content}
``````

# [3] Human
{user_content}{marker}"""
        else:
            session_content = f"""# [1] Human

Question?
{user_content}{marker}"""

        session_path = tmp_path / "session.md"
        session_path.write_text(session_content)
        return session_path

    return _make
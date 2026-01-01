"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


def load_fixture(fixtures_dir: Path, name: str) -> str:
    """Load a fixture file."""
    return (fixtures_dir / name).read_text(encoding="utf-8")

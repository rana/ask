"""Tests for check logic."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ask.check import (
    CheckResult,
    CheckRunResult,
    extract_summary,
    format_check_block,
    insert_check_block,
    load_checks,
    strip_ansi_codes,
)
from ask.errors import AskError


def test_load_checks_auto_creates_config(tmp_path: Path) -> None:
    """Load checks auto-creates default config if not exists."""
    checks_path = tmp_path / ".ask" / "checks.json"

    with patch("ask.check.get_checks_path", return_value=checks_path):
        checks = load_checks()

    assert checks_path.exists()
    assert len(checks) == 4
    assert checks[0].id == "ruff"
    assert checks[1].id == "ruff-format"
    assert checks[2].id == "pyright"
    assert checks[3].id == "pytest"


def test_load_checks_from_existing_config(tmp_path: Path) -> None:
    """Load checks from existing config."""
    checks_path = tmp_path / ".ask" / "checks.json"
    checks_path.parent.mkdir(parents=True)

    config: dict[str, Any] = {
        "default_set": "custom",
        "check_sets": {
            "custom": {
                "description": "Custom checks",
                "checks": [
                    {
                        "id": "test-check",
                        "name": "Test Check",
                        "command": "echo 'test'",
                    }
                ],
            }
        },
    }
    checks_path.write_text(json.dumps(config))

    with patch("ask.check.get_checks_path", return_value=checks_path):
        checks = load_checks()

    assert len(checks) == 1
    assert checks[0].id == "test-check"
    assert checks[0].command == "echo 'test'"


def test_load_checks_with_fix_command(tmp_path: Path) -> None:
    """Load checks includes fix_command when present."""
    checks_path = tmp_path / ".ask" / "checks.json"
    checks_path.parent.mkdir(parents=True)

    config: dict[str, Any] = {
        "default_set": "test",
        "check_sets": {
            "test": {
                "checks": [
                    {
                        "id": "linter",
                        "name": "Linter",
                        "command": "lint check",
                        "fix_command": "lint fix",
                    }
                ]
            }
        },
    }
    checks_path.write_text(json.dumps(config))

    with patch("ask.check.get_checks_path", return_value=checks_path):
        checks = load_checks()

    assert checks[0].fix_command == "lint fix"


def test_load_checks_invalid_json(tmp_path: Path) -> None:
    """Load checks raises error on invalid JSON."""
    checks_path = tmp_path / ".ask" / "checks.json"
    checks_path.parent.mkdir(parents=True)
    checks_path.write_text("not valid json")

    with (
        patch("ask.check.get_checks_path", return_value=checks_path),
        pytest.raises(AskError) as exc_info,
    ):
        load_checks()

    assert "Invalid checks.json" in str(exc_info.value)


def test_load_checks_missing_set(tmp_path: Path) -> None:
    """Load checks raises error when default_set not found."""
    checks_path = tmp_path / ".ask" / "checks.json"
    checks_path.parent.mkdir(parents=True)

    config: dict[str, Any] = {
        "default_set": "nonexistent",
        "check_sets": {"python": {"checks": []}},
    }
    checks_path.write_text(json.dumps(config))

    with (
        patch("ask.check.get_checks_path", return_value=checks_path),
        pytest.raises(AskError) as exc_info,
    ):
        load_checks()

    assert "not found" in str(exc_info.value)


def test_strip_ansi_codes() -> None:
    """Strip ANSI escape codes from output."""
    input_text = "\x1b[31mError:\x1b[0m Something went wrong"
    result = strip_ansi_codes(input_text)
    assert result == "Error: Something went wrong"


def test_strip_ansi_codes_complex() -> None:
    """Strip complex ANSI sequences."""
    input_text = "\x1b[1;32mPASS\x1b[0m test_file.py \x1b[33m(0.5s)\x1b[0m"
    result = strip_ansi_codes(input_text)
    assert result == "PASS test_file.py (0.5s)"


def test_strip_ansi_codes_no_codes() -> None:
    """Text without ANSI codes is unchanged."""
    input_text = "Plain text without colors"
    result = strip_ansi_codes(input_text)
    assert result == input_text


def test_extract_summary_pytest_passed() -> None:
    """Extract pytest passed summary."""
    output = "===== 12 passed in 0.5s ====="
    summary = extract_summary("pytest", output, passed=True)
    assert summary == "12 passed"


def test_extract_summary_pytest_failed() -> None:
    """Extract pytest failed summary."""
    output = "===== 2 failed, 10 passed in 1.0s ====="
    summary = extract_summary("pytest", output, passed=False)
    assert summary == "10 passed, 2 failed"


def test_extract_summary_pyright_errors() -> None:
    """Extract pyright error count."""
    output = "Found 3 errors in 2 files"
    summary = extract_summary("pyright", output, passed=False)
    assert summary == "3 errors"


def test_extract_summary_pyright_one_error() -> None:
    """Extract pyright single error."""
    output = "Found 1 error in 1 file"
    summary = extract_summary("pyright", output, passed=False)
    assert summary == "1 error"


def test_extract_summary_pyright_pass() -> None:
    """Pyright pass has no summary."""
    output = "0 errors, 0 warnings"
    summary = extract_summary("pyright", output, passed=True)
    assert summary == ""


def test_extract_summary_ruff_errors() -> None:
    """Extract ruff error count."""
    output = """src/main.py:1:1: F401 imported but unused
src/main.py:5:10: E501 line too long"""
    summary = extract_summary("ruff", output, passed=False)
    assert summary == "2 errors"


def test_extract_summary_ruff_pass() -> None:
    """Ruff pass has no summary."""
    output = "All checks passed!"
    summary = extract_summary("ruff", output, passed=True)
    assert summary == ""


def test_extract_summary_ruff_format() -> None:
    """Ruff format has no summary."""
    summary = extract_summary("ruff-format", "some output", passed=True)
    assert summary == ""


def test_format_check_block_all_pass() -> None:
    """Format check block when all pass."""
    result = CheckRunResult(
        results=[
            CheckResult(id="ruff", name="Ruff", status="PASS", summary=""),
            CheckResult(id="pyright", name="Pyright", status="PASS", summary=""),
            CheckResult(id="pytest", name="Pytest", status="PASS", summary="12 passed"),
        ],
        status="PASS",
    )

    block = format_check_block(result)

    assert "<!-- ask:check status=PASS -->" in block
    assert "| ruff | PASS |" in block
    assert "| pyright | PASS |" in block
    assert "| pytest | PASS | 12 passed |" in block
    assert "<!-- /ask:check -->" in block
    # No detail sections for passing checks
    assert "### ruff" not in block


def test_format_check_block_with_failures() -> None:
    """Format check block with failures."""
    result = CheckRunResult(
        results=[
            CheckResult(id="ruff", name="Ruff", status="PASS", summary=""),
            CheckResult(
                id="pyright",
                name="Pyright",
                status="FAIL",
                summary="2 errors",
                output="src/main.py:5:12 - error: Type mismatch",
            ),
        ],
        status="FAIL",
    )

    block = format_check_block(result)

    assert "<!-- ask:check status=FAIL -->" in block
    assert "| pyright | FAIL | 2 errors |" in block
    assert "### pyright" in block
    assert "Type mismatch" in block


def test_format_check_block_timeout() -> None:
    """Format check block with timeout."""
    result = CheckRunResult(
        results=[
            CheckResult(id="pytest", name="Pytest", status="TIMEOUT", summary="exceeded 60s"),
        ],
        status="FAIL",
    )

    block = format_check_block(result)

    assert "| pytest | TIMEOUT | exceeded 60s |" in block


def test_format_check_block_error() -> None:
    """Format check block with error."""
    result = CheckRunResult(
        results=[
            CheckResult(id="ruff", name="Ruff", status="ERROR", summary="command not found"),
        ],
        status="FAIL",
    )

    block = format_check_block(result)

    assert "| ruff | ERROR | command not found |" in block


def test_insert_check_block_before_marker(make_session: Callable[..., Path]) -> None:
    """Check block inserts before _ marker."""
    session_path = make_session()

    check_block = """<!-- ask:check status=PASS -->
| Check | Status | Summary |
|-------|--------|---------|
| ruff | PASS | |
<!-- /ask:check -->"""

    insert_check_block(str(session_path), check_block)

    result = session_path.read_text()

    block_pos = result.find("<!-- ask:check")
    marker_pos = result.find("\n_\n")

    assert block_pos < marker_pos
    assert "<!-- ask:check status=PASS -->" in result


def test_insert_check_block_before_user_text(make_session: Callable[..., Path]) -> None:
    """Check block inserts before user text."""
    session_path = make_session(user_text="I have a question.")

    check_block = """<!-- ask:check status=PASS -->
| Check | Status | Summary |
|-------|--------|---------|
| ruff | PASS | |
<!-- /ask:check -->"""

    insert_check_block(str(session_path), check_block)

    result = session_path.read_text()

    block_pos = result.find("<!-- ask:check")
    text_pos = result.find("I have a question.")

    assert block_pos < text_pos


def test_insert_check_block_after_applied_block(tmp_path: Path) -> None:
    """Check block inserts after existing applied block."""
    session_content = """# [1] Human

Question?

# [2] AI

``````markdown
Answer.
``````

# [3] Human

<!-- ask:applied -->
| Path | Action | Size |
|------|--------|------|
| src/a.py | created | 100B |
<!-- /ask:applied -->

_
"""
    session_path = tmp_path / "session.md"
    session_path.write_text(session_content)

    check_block = """<!-- ask:check status=PASS -->
| Check | Status | Summary |
|-------|--------|---------|
| ruff | PASS | |
<!-- /ask:check -->"""

    insert_check_block(str(session_path), check_block)

    result = session_path.read_text()

    applied_end = result.find("<!-- /ask:applied -->")
    check_start = result.find("<!-- ask:check")

    assert applied_end < check_start


def test_insert_check_block_no_marker(make_session: Callable[..., Path]) -> None:
    """Insert check block raises error when no marker."""
    session_path = make_session(has_marker=False)

    check_block = "<!-- ask:check status=PASS -->\n<!-- /ask:check -->"

    with pytest.raises(AskError) as exc_info:
        insert_check_block(str(session_path), check_block)

    assert "No input marker" in str(exc_info.value)

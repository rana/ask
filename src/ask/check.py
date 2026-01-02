"""Check execution and result formatting for ask."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ask.errors import AskError
from ask.parser import find_input_marker
from ask.session import read_session
from ask.workspace import find_workspace

CHECK_TIMEOUT_SECONDS = 60


@dataclass
class CheckDef:
    """Definition of a single check."""

    id: str
    name: str
    command: str
    fix_command: str | None = None


@dataclass
class CheckResult:
    """Result of running a single check."""

    id: str
    name: str
    status: str  # PASS, FAIL, ERROR, TIMEOUT
    summary: str
    output: str | None = None


@dataclass
class CheckRunResult:
    """Result of running all checks."""

    results: list[CheckResult]
    status: str  # PASS or FAIL


def get_checks_path() -> Path:
    """Get the path to checks.json."""
    return Path.home() / ".ask" / "checks.json"


def load_checks() -> list[CheckDef]:
    """Load check definitions from config.

    Auto-creates default config if not exists.
    """
    checks_path = get_checks_path()

    if not checks_path.exists():
        _create_default_checks_config(checks_path)

    try:
        text = checks_path.read_text(encoding="utf-8")
        data: dict[str, Any] = json.loads(text)

        default_set = cast(str, data.get("default_set", "python"))
        check_sets = cast(dict[str, Any], data.get("check_sets", {}))

        if default_set not in check_sets:
            raise AskError(
                f"Check set '{default_set}' not found",
                f"Available sets: {', '.join(check_sets.keys())}",
            )

        set_data = cast(dict[str, Any], check_sets[default_set])
        checks_data = cast(list[dict[str, Any]], set_data.get("checks", []))

        checks: list[CheckDef] = []
        for check in checks_data:
            checks.append(
                CheckDef(
                    id=cast(str, check["id"]),
                    name=cast(str, check["name"]),
                    command=cast(str, check["command"]),
                    fix_command=cast(str | None, check.get("fix_command")),
                )
            )

        return checks

    except json.JSONDecodeError as e:
        raise AskError(f"Invalid checks.json: {e}") from e
    except KeyError as e:
        raise AskError(f"Missing required field in checks.json: {e}") from e


def _create_default_checks_config(path: Path) -> None:
    """Create default checks.json config."""
    path.parent.mkdir(parents=True, exist_ok=True)

    default_config = {
        "default_set": "python",
        "check_sets": {
            "python": {
                "description": "Standard Python checks",
                "checks": [
                    {
                        "id": "ruff",
                        "name": "Ruff Linter",
                        "command": "uv run ruff check src/ tests/",
                        "fix_command": "uv run ruff check --fix src/ tests/",
                    },
                    {
                        "id": "ruff-format",
                        "name": "Ruff Formatter",
                        "command": "uv run ruff format --check src/ tests/",
                        "fix_command": "uv run ruff format src/ tests/",
                    },
                    {
                        "id": "pyright",
                        "name": "Pyright Type Checker",
                        "command": "uv run pyright",
                    },
                    {
                        "id": "pytest",
                        "name": "Pytest",
                        "command": "uv run pytest -v",
                    },
                ],
            }
        },
    }

    path.write_text(json.dumps(default_config, indent=2) + "\n", encoding="utf-8")


def run_checks(session_path: str, fix: bool = False) -> CheckRunResult:
    """Run all checks and return results.

    Args:
        session_path: Path to session file
        fix: If True, run fix_commands before commands

    Returns:
        CheckRunResult with all check results
    """
    # Determine workspace directory
    session_content = Path(session_path).read_text(encoding="utf-8")
    workspace = find_workspace(session_content)
    cwd = workspace if workspace else Path.cwd()

    checks = load_checks()

    # Run fix commands first if requested
    if fix:
        for check in checks:
            if check.fix_command:
                _run_command(check.fix_command, cwd)

    # Run all check commands
    results: list[CheckResult] = []
    for check in checks:
        result = _execute_check(check, cwd)
        results.append(result)

    # Determine overall status
    has_failure = any(r.status != "PASS" for r in results)
    status = "FAIL" if has_failure else "PASS"

    return CheckRunResult(results=results, status=status)


def _execute_check(check: CheckDef, cwd: Path) -> CheckResult:
    """Execute a single check and return result."""
    try:
        result = subprocess.run(
            check.command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS,
        )

        output = result.stdout + result.stderr
        output = strip_ansi_codes(output).strip()

        if result.returncode == 0:
            summary = extract_summary(check.id, output, passed=True)
            return CheckResult(
                id=check.id,
                name=check.name,
                status="PASS",
                summary=summary,
                output=None,
            )
        else:
            summary = extract_summary(check.id, output, passed=False)
            return CheckResult(
                id=check.id,
                name=check.name,
                status="FAIL",
                summary=summary,
                output=output if output else None,
            )

    except subprocess.TimeoutExpired:
        return CheckResult(
            id=check.id,
            name=check.name,
            status="TIMEOUT",
            summary=f"exceeded {CHECK_TIMEOUT_SECONDS}s",
            output=None,
        )
    except FileNotFoundError:
        return CheckResult(
            id=check.id,
            name=check.name,
            status="ERROR",
            summary="command not found",
            output=None,
        )
    except Exception as e:
        return CheckResult(
            id=check.id,
            name=check.name,
            status="ERROR",
            summary=str(e)[:30],
            output=None,
        )


def _run_command(command: str, cwd: Path) -> None:
    """Run a command without capturing output (for fix commands)."""
    try:  # noqa: SIM105
        subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            timeout=CHECK_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except Exception:
        # Fix commands are best-effort, don't fail on errors
        pass


def strip_ansi_codes(text: str) -> str:
    """Strip ANSI escape codes from text."""
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    return ansi_pattern.sub("", text)


def extract_summary(check_id: str, output: str, passed: bool) -> str:
    """Extract a summary from check output."""
    try:
        if check_id == "pytest":
            # Look for "X passed" or "X failed"
            passed_match = re.search(r"(\d+)\s+passed", output)
            failed_match = re.search(r"(\d+)\s+failed", output)

            parts: list[str] = []
            if passed_match:
                parts.append(f"{passed_match.group(1)} passed")
            if failed_match:
                parts.append(f"{failed_match.group(1)} failed")

            return ", ".join(parts) if parts else ""

        elif check_id == "pyright":
            # Look for "X errors" or "0 errors"
            error_match = re.search(r"(\d+)\s+error", output)
            if error_match:
                count = int(error_match.group(1))
                if count > 0:
                    return f"{count} errors" if count > 1 else "1 error"
            return ""

        elif check_id == "ruff":
            if not passed:
                # Count number of issues (lines that look like file:line:col)
                issues = re.findall(r"^\S+:\d+:\d+:", output, re.MULTILINE)
                if issues:
                    count = len(issues)
                    return f"{count} errors" if count > 1 else "1 error"
            return ""

        elif check_id == "ruff-format":
            # Binary pass/fail, no summary needed
            return ""

    except Exception:
        pass

    return ""


def format_check_block(result: CheckRunResult) -> str:
    """Format check results as markdown block."""
    lines: list[str] = []

    # Opening marker with status
    lines.append(f"<!-- ask:check status={result.status} -->")

    # Summary table
    lines.append("| Check | Status | Summary |")
    lines.append("|-------|--------|---------|")

    for r in result.results:
        summary = r.summary if r.summary else ""
        lines.append(f"| {r.id} | {r.status} | {summary} |")

    # Detail sections for failed checks
    failed_checks = [r for r in result.results if r.status != "PASS" and r.output]
    for r in failed_checks:
        lines.append("")
        lines.append(f"### {r.id}")
        lines.append("```")
        lines.append(r.output or "")
        lines.append("```")

    lines.append("<!-- /ask:check -->")

    return "\n".join(lines)


def insert_check_block(session_path: str, check_block: str) -> None:
    """Insert check block before the _ marker in session.

    Inserts after the turn header, before any user text.
    """
    content = Path(session_path).read_text(encoding="utf-8")

    marker_info = find_input_marker(content)
    if marker_info is None:
        raise AskError(
            "No input marker found",
            "Add `_` on its own line in the current human turn",
        )

    line_idx, _ = marker_info
    lines = content.split("\n")

    # Find the start of the current human turn
    turn_start = None
    for i in range(line_idx - 1, -1, -1):
        if lines[i].startswith("# [") and "Human" in lines[i]:
            turn_start = i
            break

    if turn_start is None:
        raise AskError("Cannot find human turn for marker")

    # Find insertion point: after turn header, after any existing machine blocks
    insert_pos = turn_start + 1

    # Skip blank lines after turn header
    while insert_pos < line_idx and lines[insert_pos].strip() == "":
        insert_pos += 1

    # Skip existing machine blocks (ask:applied, ask:check)
    while insert_pos < line_idx:
        line = lines[insert_pos].strip()
        if line.startswith("<!-- ask:applied") or line.startswith("<!-- ask:check"):
            # Find the closing marker
            while insert_pos < line_idx:
                if lines[insert_pos].strip() in ("<!-- /ask:applied -->", "<!-- /ask:check -->"):
                    insert_pos += 1
                    break
                insert_pos += 1
            # Skip blank lines after block
            while insert_pos < line_idx and lines[insert_pos].strip() == "":
                insert_pos += 1
        else:
            break

    # Insert the block
    new_lines = lines[:insert_pos] + ["", check_block, ""] + lines[insert_pos:]

    Path(session_path).write_text("\n".join(new_lines), encoding="utf-8")


def check_session(session_path: str, fix: bool = False) -> CheckRunResult:
    """Run checks and insert results into session.

    Args:
        session_path: Path to session file
        fix: If True, run fix_commands before commands

    Returns:
        CheckRunResult with all check results
    """
    # Validate session exists and has proper structure
    _ = read_session(session_path)

    # Run checks
    result = run_checks(session_path, fix=fix)

    # Format and insert block
    check_block = format_check_block(result)
    insert_check_block(session_path, check_block)

    return result

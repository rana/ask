"""Tests for apply logic."""

from collections.abc import Callable
from pathlib import Path

import pytest

from ask.apply import (
    ApplyResult,
    CommandResult,
    FileResult,
    apply_session,
    format_applied_block,
    insert_applied_block,
)
from ask.errors import AskError
from ask.workspace import find_workspace, resolve_path


def test_find_workspace_marker() -> None:
    """Find workspace marker in content."""
    marker = "<!-- ask:workspace /home/user/project/ -->"
    content = f"""{marker}

# [1] Human

Question?
"""
    workspace = find_workspace(content)
    assert workspace == Path("/home/user/project/")


def test_find_workspace_no_marker() -> None:
    """No workspace marker returns None."""
    content = """# [1] Human

Question?
"""
    workspace = find_workspace(content)
    assert workspace is None


def test_resolve_path_absolute() -> None:
    """Absolute paths are used as-is."""
    workspace = Path("/home/user/project")
    result = resolve_path("/tmp/debug.log", workspace)
    assert result == Path("/tmp/debug.log")


def test_resolve_path_with_workspace() -> None:
    """Relative paths resolve against workspace."""
    workspace = Path("/home/user/project")
    result = resolve_path("src/main.py", workspace)
    assert result == Path("/home/user/project/src/main.py")


def test_resolve_path_without_workspace() -> None:
    """Relative paths resolve against cwd when no workspace."""
    result = resolve_path("src/main.py", None)
    assert result == Path.cwd() / "src/main.py"


def test_write_file_creates_directories(
    make_session: Callable[..., Path], tmp_path: Path
) -> None:
    """Writing file creates parent directories."""
    target_file = tmp_path / "deep" / "nested" / "file.py"
    file_marker = f"<!-- file: {target_file} -->"
    close_marker = "<!-- /file -->"
    ai_content = f"""{file_marker}
```python
x = 1
```
{close_marker}"""
    session_path = make_session(ai_content=ai_content)

    result = apply_session(str(session_path))

    assert len(result.file_results) == 1
    assert result.file_results[0].action == "created"

    assert target_file.exists()
    assert "x = 1" in target_file.read_text()


def test_write_file_updates_existing(
    make_session: Callable[..., Path], tmp_path: Path
) -> None:
    """Writing to existing file reports 'updated'."""
    existing = tmp_path / "existing.py"
    existing.write_text("old content")

    file_marker = f"<!-- file: {existing} -->"
    close_marker = "<!-- /file -->"
    ai_content = f"""{file_marker}
```python
new content
```
{close_marker}"""
    session_path = make_session(ai_content=ai_content)

    result = apply_session(str(session_path))

    assert len(result.file_results) == 1
    assert result.file_results[0].action == "updated"
    assert "new content" in existing.read_text()


def test_apply_no_ai_turn(make_session: Callable[..., Path]) -> None:
    """Apply with no AI turn raises error."""
    session_path = make_session(include_ai_turn=False)

    with pytest.raises(AskError) as exc_info:
        apply_session(str(session_path))

    assert "No AI response" in str(exc_info.value)


def test_apply_no_blocks(make_session: Callable[..., Path]) -> None:
    """Apply with no extractable blocks raises error."""
    session_path = make_session(ai_content="Just some text, no file blocks.")

    with pytest.raises(AskError) as exc_info:
        apply_session(str(session_path))

    assert "No files or commands" in str(exc_info.value)


def test_dry_run_does_not_write(
    make_session: Callable[..., Path], tmp_path: Path
) -> None:
    """Dry run previews without writing."""
    target_file = tmp_path / "should_not_exist.py"
    file_marker = f"<!-- file: {target_file} -->"
    close_marker = "<!-- /file -->"
    ai_content = f"""{file_marker}
```python
x = 1
```
{close_marker}"""
    session_path = make_session(ai_content=ai_content)

    result = apply_session(str(session_path), dry_run=True)

    assert len(result.file_results) == 1
    assert result.file_results[0].action == "created"

    assert not target_file.exists()


def test_format_applied_block_files_only() -> None:
    """Format applied block with files only."""
    result = ApplyResult(
        file_results=[
            FileResult(path="src/a.py", action="created", size=100),
            FileResult(path="src/b.py", action="updated", size=50),
        ],
        command_results=[],
        status="OK",
    )

    block = format_applied_block(result)

    assert "<!-- ask:applied -->" in block
    assert "src/a.py" in block
    assert "created" in block
    assert "100B" in block
    assert "src/b.py" in block
    assert "updated" in block
    assert "<!-- /ask:applied -->" in block


def test_format_applied_block_with_commands() -> None:
    """Format applied block with files and commands."""
    result = ApplyResult(
        file_results=[
            FileResult(path="src/main.py", action="created", size=200),
        ],
        command_results=[
            CommandResult(command="uv add bcrypt", status="OK"),
            CommandResult(command="uv run pytest", status="OK"),
        ],
        status="OK",
    )

    block = format_applied_block(result)

    assert "src/main.py" in block
    assert "uv add bcrypt" in block
    assert "uv run pytest" in block
    assert "| OK |" in block


def test_format_applied_block_partial_failure() -> None:
    """Format applied block with command failure."""
    result = ApplyResult(
        file_results=[
            FileResult(path="src/main.py", action="created", size=200),
        ],
        command_results=[
            CommandResult(command="uv run pytest", status="FAIL", output="Test failed!"),
        ],
        status="PARTIAL",
    )

    block = format_applied_block(result)

    assert "<!-- ask:applied status=PARTIAL -->" in block
    assert "FAIL" in block
    assert "Test failed!" in block


def test_insert_applied_block_before_marker(make_session: Callable[..., Path]) -> None:
    """Applied block inserts before _ marker."""
    session_path = make_session()

    applied_block = """<!-- ask:applied -->
| Path | Action | Size |
|------|--------|------|
| src/a.py | created | 100B |
<!-- /ask:applied -->"""

    insert_applied_block(str(session_path), applied_block)

    result = session_path.read_text()

    block_pos = result.find("<!-- ask:applied -->")
    marker_pos = result.find("\n_\n")

    assert block_pos < marker_pos
    assert "<!-- ask:applied -->" in result


def test_insert_applied_block_before_user_text(make_session: Callable[..., Path]) -> None:
    """Applied block inserts before user text."""
    session_path = make_session(user_text="I have a follow-up question.")

    applied_block = """<!-- ask:applied -->
| Path | Action | Size |
|------|--------|------|
| src/a.py | created | 100B |
<!-- /ask:applied -->"""

    insert_applied_block(str(session_path), applied_block)

    result = session_path.read_text()

    block_pos = result.find("<!-- ask:applied -->")
    text_pos = result.find("I have a follow-up question.")

    assert block_pos < text_pos


def test_apply_files_only_flag(
    make_session: Callable[..., Path], tmp_path: Path
) -> None:
    """Apply with --files flag only extracts files."""
    target_file = tmp_path / "test.py"
    file_marker = f"<!-- file: {target_file} -->"
    file_close = "<!-- /file -->"
    cmd_open = "<!-- ask:command -->"
    cmd_close = "<!-- /ask:command -->"
    ai_content = f"""{file_marker}
```python
x = 1
```
{file_close}

{cmd_open}
```bash
echo "should not run"
```
{cmd_close}"""
    session_path = make_session(ai_content=ai_content)

    result = apply_session(str(session_path), apply_files=True, apply_commands=False)

    assert len(result.file_results) == 1
    assert len(result.command_results) == 0
    assert target_file.exists()


def test_apply_commands_only_flag(
    make_session: Callable[..., Path], tmp_path: Path
) -> None:
    """Apply with --commands flag only executes commands."""
    target_file = tmp_path / "should_not_exist.py"
    file_marker = f"<!-- file: {target_file} -->"
    file_close = "<!-- /file -->"
    cmd_open = "<!-- ask:command -->"
    cmd_close = "<!-- /ask:command -->"
    ai_content = f"""{file_marker}
```python
x = 1
```
{file_close}

{cmd_open}
```bash
echo "hello"
```
{cmd_close}"""
    session_path = make_session(ai_content=ai_content)

    result = apply_session(str(session_path), apply_files=False, apply_commands=True)

    assert len(result.file_results) == 0
    assert len(result.command_results) == 1
    assert result.command_results[0].status == "OK"
    assert not target_file.exists()


def test_command_failure_stops_execution(make_session: Callable[..., Path]) -> None:
    """Command failure stops subsequent commands."""
    cmd_open = "<!-- ask:command -->"
    cmd_close = "<!-- /ask:command -->"
    ai_content = f"""{cmd_open}
```bash
exit 1
```
{cmd_close}

{cmd_open}
```bash
echo "should not run"
```
{cmd_close}"""
    session_path = make_session(ai_content=ai_content)

    result = apply_session(str(session_path), apply_files=False, apply_commands=True)

    assert len(result.command_results) == 1
    assert result.command_results[0].status == "FAIL"
    assert result.status == "PARTIAL"
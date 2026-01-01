"""Tests for extraction logic."""

from pathlib import Path

from ask.extract import extract_command_blocks, extract_file_blocks


def _load_fixture(name: str) -> str:
    """Load a test fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / name
    return fixture_path.read_text(encoding="utf-8")


def test_extract_single_file_block() -> None:
    """Extract single file block from content."""
    content = _load_fixture("ai_response_single_file.txt")
    blocks = extract_file_blocks(content)

    assert len(blocks) == 1
    assert blocks[0].path == "src/auth/login.py"
    assert "def login():" in blocks[0].content


def test_extract_multiple_file_blocks() -> None:
    """Extract multiple file blocks."""
    content = _load_fixture("ai_response_multiple_files.txt")
    blocks = extract_file_blocks(content)

    assert len(blocks) == 2
    assert blocks[0].path == "src/a.py"
    assert "a = 1" in blocks[0].content
    assert blocks[1].path == "src/b.py"
    assert "b = 2" in blocks[1].content


def test_extract_command_blocks() -> None:
    """Extract command blocks."""
    content = _load_fixture("ai_response_commands.txt")
    blocks = extract_command_blocks(content)

    assert len(blocks) == 2
    assert blocks[0].command == "uv add bcrypt"
    assert blocks[1].command == "uv run pytest"


def test_extract_mixed_files_and_commands() -> None:
    """Extract both file and command blocks."""
    content = _load_fixture("ai_response_mixed.txt")
    file_blocks = extract_file_blocks(content)
    cmd_blocks = extract_command_blocks(content)

    assert len(file_blocks) == 1
    assert len(cmd_blocks) == 1
    assert file_blocks[0].path == "src/main.py"
    assert cmd_blocks[0].command == "python src/main.py"


def test_extract_handles_missing_closing_marker() -> None:
    """Missing closing marker should not extract block."""
    # Build content without literal markers in Python source
    open_marker = "<!-- file: src/broken.py -->"
    content = f"""{open_marker}
```python
broken code
```
No closing marker here.
"""
    blocks = extract_file_blocks(content)
    assert len(blocks) == 0


def test_extract_handles_empty_content() -> None:
    """Empty content between markers should not extract."""
    open_marker = "<!-- file: src/empty.py -->"
    close_marker = "<!-- /file -->"
    content = f"""{open_marker}
{close_marker}
"""
    blocks = extract_file_blocks(content)
    assert len(blocks) == 0


def test_extract_file_with_nested_fences() -> None:
    """File with nested code fences should work."""
    content = _load_fixture("ai_response_nested_fence.txt")
    blocks = extract_file_blocks(content)

    assert len(blocks) == 1
    assert "```python" in blocks[0].content


def test_extract_preserves_content_whitespace() -> None:
    """Content whitespace should be preserved."""
    open_marker = "<!-- file: src/spaced.py -->"
    close_marker = "<!-- /file -->"
    content = f"""{open_marker}
```python
def foo():
    if True:
        pass
```
{close_marker}
"""
    blocks = extract_file_blocks(content)

    assert len(blocks) == 1
    assert "    if True:" in blocks[0].content
    assert "        pass" in blocks[0].content


def test_extract_multiline_command() -> None:
    """Multiline command should be extracted."""
    content = _load_fixture("ai_response_multiline_cmd.txt")
    blocks = extract_command_blocks(content)

    assert len(blocks) == 1
    assert "line 1" in blocks[0].command
    assert "line 2" in blocks[0].command

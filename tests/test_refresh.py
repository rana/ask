"""Tests for refresh logic."""

import tempfile
from pathlib import Path

from ask.refresh import (
    find_marker_blocks,
    refresh_content,
    refresh_session,
)
from ask.types import Config


def test_find_file_marker_blocks() -> None:
    """Find file marker blocks in content."""
    content = """# [1] Human

<!-- file: src/main.py -->
### src/main.py
```python
old content
```
<!-- /file -->

Question here.
"""
    blocks = find_marker_blocks(content)

    assert len(blocks) == 1
    assert blocks[0].type == "file"
    assert blocks[0].reference == "src/main.py"


def test_find_directory_marker_blocks() -> None:
    """Find directory marker blocks in content."""
    content = """# [1] Human

<!-- dir: src/ -->
<!-- file: src/a.py -->
content
<!-- /file -->
<!-- /dir -->
"""
    blocks = find_marker_blocks(content)

    assert len(blocks) == 2
    dir_blocks = [b for b in blocks if b.type == "dir"]
    assert len(dir_blocks) == 1
    assert dir_blocks[0].reference == "src"
    assert dir_blocks[0].is_recursive is False


def test_find_recursive_directory_marker() -> None:
    """Find recursive directory marker."""
    content = """<!-- dir: src/**/ -->
content
<!-- /dir -->
"""
    blocks = find_marker_blocks(content)

    dir_blocks = [b for b in blocks if b.type == "dir"]
    assert len(dir_blocks) == 1
    assert dir_blocks[0].is_recursive is True


def test_find_url_markers_when_enabled() -> None:
    """Find URL markers when include_urls is True."""
    content = """<!-- url: https://example.com -->
content
<!-- /url -->
"""
    blocks_without = find_marker_blocks(content, include_urls=False)
    blocks_with = find_marker_blocks(content, include_urls=True)

    assert len(blocks_without) == 0
    assert len(blocks_with) == 1
    assert blocks_with[0].type == "url"
    assert blocks_with[0].reference == "https://example.com"


def test_skip_error_markers() -> None:
    """Error markers should be skipped."""
    content = """<!-- file: missing.py -->
❌ Error: missing.py - File not found
<!-- /file -->
"""
    blocks = find_marker_blocks(content)

    assert len(blocks) == 0


def test_refresh_file_marker() -> None:
    """Refresh updates file content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# updated content")

        content = f"""<!-- file: {test_file} -->
### {test_file}
```python
# old content
```
<!-- /file -->
"""
        config = Config(filter=False)
        new_content, result = refresh_content(content, config=config)

        assert "# updated content" in new_content
        assert "# old content" not in new_content
        assert result.files_refreshed == 1


def test_refresh_directory_picks_up_new_files() -> None:
    """Directory refresh picks up newly added files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial file
        (Path(tmpdir) / "a.py").write_text("# a")

        # Create marker with only one file
        content = f"""<!-- dir: {tmpdir}/ -->
<!-- file: {tmpdir}/a.py -->
### {tmpdir}/a.py
```python
# a
```
<!-- /file -->
<!-- /dir -->
"""
        # Add new file
        (Path(tmpdir) / "b.py").write_text("# b")

        config = Config(filter=False, exclude=[])
        new_content, result = refresh_content(content, config=config)

        assert "# a" in new_content
        assert "# b" in new_content
        assert result.dirs_refreshed == 1


def test_refresh_directory_removes_deleted_files() -> None:
    """Directory refresh removes deleted files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create file that will be "deleted"
        (Path(tmpdir) / "keep.py").write_text("# keep")

        content = f"""<!-- dir: {tmpdir}/ -->
<!-- file: {tmpdir}/keep.py -->
### {tmpdir}/keep.py
```python
# keep
```
<!-- /file -->
<!-- file: {tmpdir}/deleted.py -->
### {tmpdir}/deleted.py
```python
# deleted
```
<!-- /file -->
<!-- /dir -->
"""
        config = Config(filter=False, exclude=[])
        new_content, result = refresh_content(content, config=config)

        assert "# keep" in new_content
        assert "# deleted" not in new_content
        assert result.dirs_refreshed == 1


def test_refresh_missing_file_becomes_error() -> None:
    """Missing file is replaced with error marker."""
    content = """<!-- file: /nonexistent/file.py -->
### /nonexistent/file.py
```python
old
```
<!-- /file -->
"""
    new_content, result = refresh_content(content)

    assert "❌ Error:" in new_content
    assert "File not found" in new_content
    assert len(result.errors) == 1


def test_refresh_binary_file_becomes_error() -> None:
    """Binary file is replaced with error marker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        binary_file = Path(tmpdir) / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02")

        content = f"""<!-- file: {binary_file} -->
### {binary_file}
```
text
```
<!-- /file -->
"""
        new_content, result = refresh_content(content)

        assert "❌ Error:" in new_content
        assert "Binary file" in new_content
        assert len(result.errors) == 1


def test_refresh_preserves_content_outside_markers() -> None:
    """Content outside markers is preserved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# new")

        content = f"""# [1] Human

Some user text before.

<!-- file: {test_file} -->
### {test_file}
```python
# old
```
<!-- /file -->

Some user text after.

_
"""
        config = Config(filter=False)
        new_content, _ = refresh_content(content, config=config)

        assert "Some user text before." in new_content
        assert "Some user text after." in new_content
        assert "# [1] Human" in new_content
        assert "_" in new_content


def test_refresh_preserves_turn_structure() -> None:
    """Turn structure is preserved during refresh."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# updated")

        content = f"""# [1] Human

<!-- file: {test_file} -->
old
<!-- /file -->

# [2] AI

``````markdown
Response here.
``````

# [3] Human

_
"""
        config = Config(filter=False)
        new_content, _ = refresh_content(content, config=config)

        assert "# [1] Human" in new_content
        assert "# [2] AI" in new_content
        assert "# [3] Human" in new_content
        assert "Response here." in new_content


def test_refresh_multiple_markers() -> None:
    """Multiple markers in same file are all refreshed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_a = Path(tmpdir) / "a.py"
        file_b = Path(tmpdir) / "b.py"
        file_a.write_text("# new a")
        file_b.write_text("# new b")

        content = f"""<!-- file: {file_a} -->
old a
<!-- /file -->

<!-- file: {file_b} -->
old b
<!-- /file -->
"""
        config = Config(filter=False)
        new_content, result = refresh_content(content, config=config)

        assert "# new a" in new_content
        assert "# new b" in new_content
        assert "old a" not in new_content
        assert "old b" not in new_content
        assert result.files_refreshed == 2


def test_refresh_dry_run_does_not_modify() -> None:
    """Dry run does not modify file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# updated")

        session_path = Path(tmpdir) / "session.md"
        original_content = f"""<!-- file: {test_file} -->
old
<!-- /file -->
"""
        session_path.write_text(original_content)

        result = refresh_session(str(session_path), dry_run=True)

        # File should not be modified
        assert session_path.read_text() == original_content
        assert result.files_refreshed == 1


def test_refresh_writes_changes_when_not_dry_run() -> None:
    """Refresh writes changes when not dry run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# updated")

        session_path = Path(tmpdir) / "session.md"
        session_path.write_text(f"""<!-- file: {test_file} -->
old
<!-- /file -->
""")

        refresh_session(str(session_path), dry_run=False)

        new_content = session_path.read_text()
        assert "# updated" in new_content


def test_refresh_skips_existing_error_markers() -> None:
    """Existing error markers are not re-expanded."""
    content = """<!-- file: missing.py -->
❌ Error: missing.py - File not found
<!-- /file -->
"""
    new_content, result = refresh_content(content)

    # Content should be unchanged
    assert new_content == content
    assert result.files_refreshed == 0
    assert len(result.errors) == 0


def test_refresh_url_skipped_by_default() -> None:
    """URL blocks are skipped by default."""
    content = """<!-- url: https://example.com -->
old content
<!-- /url -->
"""
    new_content, result = refresh_content(content, include_urls=False)

    assert new_content == content
    assert result.urls_refreshed == 0


def test_find_markers_with_nested_file_in_dir() -> None:
    """Nested file markers inside dir are found."""
    content = """<!-- dir: src/ -->
<!-- file: src/a.py -->
content
<!-- /file -->
<!-- file: src/b.py -->
content
<!-- /file -->
<!-- /dir -->
"""
    blocks = find_marker_blocks(content)

    # Should find dir block and both file blocks
    dir_blocks = [b for b in blocks if b.type == "dir"]
    file_blocks = [b for b in blocks if b.type == "file"]

    assert len(dir_blocks) == 1
    assert len(file_blocks) == 2


def test_refresh_empty_directory() -> None:
    """Empty directory shows appropriate message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_dir = Path(tmpdir) / "empty"
        empty_dir.mkdir()

        content = f"""<!-- dir: {empty_dir}/ -->
<!-- file: {empty_dir}/old.py -->
old
<!-- /file -->
<!-- /dir -->
"""
        config = Config(filter=False, exclude=[])
        new_content, result = refresh_content(content, config=config)

        assert "*(empty directory)*" in new_content
        assert result.dirs_refreshed == 1


def test_refresh_result_details() -> None:
    """Refresh result contains details of what was refreshed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("# content")

        content = f"""<!-- file: {test_file} -->
old
<!-- /file -->
"""
        config = Config(filter=False)
        _, result = refresh_content(content, config=config)

        assert str(test_file) in result.details

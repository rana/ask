"""Tests for reference expansion."""

import tempfile
from pathlib import Path

from ask.expand import expand_references
from ask.types import Config


def test_expand_single_file_reference() -> None:
    """Expand a single file reference."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        content = f"Check this: [[{test_file}]]"
        config = Config(filter=False)

        expanded, file_count = expand_references(content, config)

        assert file_count == 1
        assert "" in expanded
        assert "def hello():" in expanded
        assert "" in expanded


def test_expand_directory_reference_non_recursive() -> None:
    """Expand a directory reference (non-recursive)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        (Path(tmpdir) / "a.py").write_text("# file a")
        (Path(tmpdir) / "b.py").write_text("# file b")

        # Create subdirectory with file (should not be included)
        subdir = Path(tmpdir) / "sub"
        subdir.mkdir()
        (subdir / "c.py").write_text("# file c")

        content = f"Check: [[{tmpdir}/]]"
        config = Config(filter=False, exclude=[])

        expanded, file_count = expand_references(content, config)

        assert file_count == 2
        assert "# file a" in expanded
        assert "# file b" in expanded
        assert "# file c" not in expanded


def test_expand_directory_reference_recursive() -> None:
    """Expand a directory reference (recursive)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        (Path(tmpdir) / "a.py").write_text("# file a")

        # Create subdirectory with file
        subdir = Path(tmpdir) / "sub"
        subdir.mkdir()
        (subdir / "c.py").write_text("# file c")

        content = f"Check: [[{tmpdir}/**/]]"
        config = Config(filter=False, exclude=[])

        expanded, file_count = expand_references(content, config)

        assert file_count == 2
        assert "# file a" in expanded
        assert "# file c" in expanded


def test_zero_width_space_escaping_prevents_re_expansion() -> None:
    """Zero-width space escaping prevents re-expansion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create file containing [[ref]]
        test_file = Path(tmpdir) / "test.md"
        test_file.write_text("Example: [[other.py]]")

        content = f"[[{test_file}]]"
        config = Config(filter=False)

        expanded, file_count = expand_references(content, config)

        assert file_count == 1
        # The [[other.py]] should be escaped with zero-width spaces
        assert "[\u200B[other.py]\u200B]" in expanded
        # Should not try to expand [[other.py]]
        assert "❌ Error: other.py" not in expanded


def test_expand_handles_binary_file_error() -> None:
    """Binary files should produce an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create binary file
        binary_file = Path(tmpdir) / "test.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03")

        content = f"[[{binary_file}]]"
        config = Config()

        expanded, file_count = expand_references(content, config)

        assert file_count == 0
        assert "❌ Error:" in expanded
        assert "Binary file" in expanded


def test_expand_handles_missing_file_error() -> None:
    """Missing files should produce an error."""
    content = "[[/nonexistent/path/file.py]]"
    config = Config()

    expanded, file_count = expand_references(content, config)

    assert file_count == 0
    assert "❌ Error:" in expanded
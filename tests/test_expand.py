"""Tests for reference expansion."""

import tempfile
from pathlib import Path

from ask.expand import expand_references, natural_sort_key
from ask.types import Config


def test_natural_sort_key_numeric_prefix() -> None:
    """Files with numeric prefixes sort by number."""
    paths = [
        Path("10-conclusion.md"),
        Path("2-chapter.md"),
        Path("1-intro.md"),
    ]

    sorted_paths = sorted(paths, key=natural_sort_key)

    assert [p.name for p in sorted_paths] == [
        "1-intro.md",
        "2-chapter.md",
        "10-conclusion.md",
    ]


def test_natural_sort_key_mixed_numeric_and_alpha() -> None:
    """Non-numeric files sort after numeric ones."""
    paths = [
        Path("README.md"),
        Path("2-chapter.md"),
        Path("1-intro.md"),
        Path("CHANGELOG.md"),
    ]

    sorted_paths = sorted(paths, key=natural_sort_key)

    assert [p.name for p in sorted_paths] == [
        "1-intro.md",
        "2-chapter.md",
        "CHANGELOG.md",
        "README.md",
    ]


def test_natural_sort_key_same_number_tiebreaker() -> None:
    """Same numeric prefix uses string tiebreaker."""
    paths = [
        Path("1-zebra.md"),
        Path("1-alpha.md"),
        Path("01-beta.md"),
    ]

    sorted_paths = sorted(paths, key=natural_sort_key)

    # 01 = 1, 1 = 1, so all have same number, sorted by string
    assert [p.name for p in sorted_paths] == [
        "01-beta.md",
        "1-alpha.md",
        "1-zebra.md",
    ]


def test_natural_sort_key_no_prefix() -> None:
    """Files without numeric prefix sort alphabetically at end."""
    paths = [
        Path("zebra.txt"),
        Path("alpha.txt"),
        Path("1-first.txt"),
    ]

    sorted_paths = sorted(paths, key=natural_sort_key)

    assert [p.name for p in sorted_paths] == [
        "1-first.txt",
        "alpha.txt",
        "zebra.txt",
    ]


def test_natural_sort_key_versioned_files() -> None:
    """Version-like prefixes sort correctly."""
    paths = [
        Path("v1-10-final.md"),
        Path("v1-2-draft.md"),
        Path("v1-1-initial.md"),
    ]

    sorted_paths = sorted(paths, key=natural_sort_key)

    # 'v' prefix means no numeric start, all go to inf
    # Then sorted alphabetically: v1-1 < v1-10 < v1-2 (string comparison)
    assert [p.name for p in sorted_paths] == [
        "v1-1-initial.md",
        "v1-10-final.md",
        "v1-2-draft.md",
    ]


def test_expand_single_file_reference() -> None:
    """Expand a single file reference."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def hello():\n    pass\n")

        content = f"Check this: [[{test_file}]]"
        config = Config(filter=False)

        expanded, file_count = expand_references(content, config)

        assert file_count == 1
        assert "<!-- file:" in expanded
        assert "def hello():" in expanded
        assert "<!-- /file -->" in expanded


def test_expand_directory_reference_non_recursive() -> None:
    """Expand a directory reference (non-recursive)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.py").write_text("# a")
        (Path(tmpdir) / "b.py").write_text("# b")

        subdir = Path(tmpdir) / "sub"
        subdir.mkdir()
        (subdir / "c.py").write_text("# c")

        content = f"Check: [[{tmpdir}/]]"
        config = Config(filter=False, exclude=[])

        expanded, file_count = expand_references(content, config)

        assert file_count == 2
        assert "# a" in expanded
        assert "# b" in expanded
        assert "# c" not in expanded


def test_expand_directory_reference_recursive() -> None:
    """Expand a directory reference (recursive)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.py").write_text("# a")

        subdir = Path(tmpdir) / "sub"
        subdir.mkdir()
        (subdir / "c.py").write_text("# c")

        content = f"Check: [[{tmpdir}/**/]]"
        config = Config(filter=False, exclude=[])

        expanded, file_count = expand_references(content, config)

        assert file_count == 2
        assert "# a" in expanded
        assert "# c" in expanded


def test_expand_directory_uses_natural_sort() -> None:
    """Directory expansion uses natural sort order."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create files that would sort differently with natural vs alphabetic
        (Path(tmpdir) / "10-last.py").write_text("# 10")
        (Path(tmpdir) / "2-second.py").write_text("# 2")
        (Path(tmpdir) / "1-first.py").write_text("# 1")
        (Path(tmpdir) / "README.md").write_text("# readme")

        content = f"[[{tmpdir}/]]"
        config = Config(filter=False, exclude=[])

        expanded, file_count = expand_references(content, config)

        assert file_count == 4

        # Find positions of each file in output
        pos_1 = expanded.find("# 1")
        pos_2 = expanded.find("# 2")
        pos_10 = expanded.find("# 10")
        pos_readme = expanded.find("# readme")

        # Natural sort: 1, 2, 10, then README
        assert pos_1 < pos_2 < pos_10 < pos_readme


def test_zero_width_space_escaping_prevents_re_expansion() -> None:
    """Zero-width space escaping prevents re-expansion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.md"
        test_file.write_text("Example: [[other.py]]")

        content = f"[[{test_file}]]"
        config = Config(filter=False)

        expanded, file_count = expand_references(content, config)

        assert file_count == 1
        assert "[\u200b[other.py]\u200b]" in expanded
        assert "❌ Error: other.py" not in expanded


def test_expand_handles_binary_file_error() -> None:
    """Binary files should produce an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
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

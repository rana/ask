"""Tests for region detection."""

from ask.regions import find_excluded_regions, is_in_excluded_region


def test_finds_code_fence_regions() -> None:
    """Code fence regions should be detected."""
    lines = [
        "# [1] Human",
        "",
        "```python",
        "# [2] AI inside fence",
        "```",
        "",
        "# [2] AI",
    ]

    regions = find_excluded_regions(lines)

    assert len(regions) == 1
    assert regions[0].type == "code-fence"
    assert regions[0].start == 2
    assert regions[0].end == 4


def test_finds_expanded_file_regions() -> None:
    """Expanded file regions should be detected."""
    lines = [
        "# [1] Human",
        "",
        "<!-- file: test.py -->",
        "### test.py",
        "```python",
        "code",
        "```",
        "<!-- /file -->",
        "",
        "# [2] AI",
    ]

    regions = find_excluded_regions(lines)

    file_regions = [r for r in regions if r.type == "expanded-file"]
    assert len(file_regions) == 1
    assert file_regions[0].start == 2
    assert file_regions[0].end == 7


def test_is_in_excluded_region() -> None:
    """Check if line is in excluded region."""
    lines = [
        "# [1] Human",
        "",
        "```python",
        "# [2] AI",
        "```",
    ]

    regions = find_excluded_regions(lines)

    assert not is_in_excluded_region(0, regions)
    assert not is_in_excluded_region(1, regions)
    assert is_in_excluded_region(2, regions)
    assert is_in_excluded_region(3, regions)
    assert is_in_excluded_region(4, regions)

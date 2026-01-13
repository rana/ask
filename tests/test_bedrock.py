"""Tests for bedrock module."""

from ask.bedrock import (
    _negate_date,  # pyright: ignore[reportPrivateUsage]
    _parse_model_version,  # pyright: ignore[reportPrivateUsage]
)

class TestParseModelVersion:
    """Tests for _parse_model_version function."""

    def test_parse_opus_4_5(self) -> None:
        """Parse claude-opus-4-5 model ID."""
        model_id = "anthropic.claude-opus-4-5-20251101-v1:0"
        result = _parse_model_version(model_id)

        assert result["major"] == 4
        assert result["minor"] == 5
        assert result["date"] == "20251101"

    def test_parse_opus_4(self) -> None:
        """Parse claude-opus-4 model ID (no minor version)."""
        model_id = "anthropic.claude-opus-4-20250514-v1:0"
        result = _parse_model_version(model_id)

        assert result["major"] == 4
        assert result["minor"] == 0
        assert result["date"] == "20250514"

    def test_parse_opus_4_1(self) -> None:
        """Parse claude-opus-4-1 model ID."""
        model_id = "anthropic.claude-opus-4-1-20250805-v1:0"
        result = _parse_model_version(model_id)

        assert result["major"] == 4
        assert result["minor"] == 1
        assert result["date"] == "20250805"

    def test_parse_claude_3_opus(self) -> None:
        """Parse older claude-3-opus model ID."""
        model_id = "anthropic.claude-3-opus-20240229-v1:0"
        result = _parse_model_version(model_id)

        assert result["major"] == 3
        assert result["minor"] == 0
        assert result["date"] == "20240229"

    def test_parse_sonnet_3_5(self) -> None:
        """Parse claude-3-5-sonnet model ID."""
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        result = _parse_model_version(model_id)

        assert result["major"] == 3
        assert result["minor"] == 5
        assert result["date"] == "20241022"

    def test_parse_haiku_3_5(self) -> None:
        """Parse claude-3-5-haiku model ID."""
        model_id = "anthropic.claude-3-5-haiku-20241022-v1:0"
        result = _parse_model_version(model_id)

        assert result["major"] == 3
        assert result["minor"] == 5
        assert result["date"] == "20241022"

    def test_date_not_included_as_minor_version(self) -> None:
        """Regression test: date should not be parsed as minor version.

        Bug: For claude-opus-4-20250514, the date was being parsed as minor=20250514,
        which caused it to sort higher than claude-opus-4-5 (minor=5).
        """
        # This was the bug: date became minor version
        model_id_4 = "anthropic.claude-opus-4-20250514-v1:0"
        result_4 = _parse_model_version(model_id_4)

        model_id_4_5 = "anthropic.claude-opus-4-5-20251101-v1:0"
        result_4_5 = _parse_model_version(model_id_4_5)

        # 4.5 should have higher minor than 4.0
        assert result_4_5["minor"] > result_4["minor"]
        # And both should have reasonable minor versions (not dates)
        assert result_4["minor"] < 100  # Not a date
        assert result_4_5["minor"] < 100  # Not a date


class TestNegateDateForSort:
    """Tests for _negate_date function used in sorting."""

    def test_negate_date_basic(self) -> None:
        """Negate a date string for descending sort."""
        # 20250514 -> 79749485
        result = _negate_date("20250514")
        assert result == "79749485"

    def test_negate_date_comparison(self) -> None:
        """Negated dates sort in descending order when using string comparison."""
        newer = "20251101"
        older = "20250514"

        # Without negation, older < newer (ascending)
        assert older < newer

        # With negation, older > newer (descending when sorted ascending)
        assert _negate_date(older) > _negate_date(newer)

    def test_version_sort_order(self) -> None:
        """Test that version sorting produces correct order.

        Models should be sorted by:
        1. Region (preferred first)
        2. Major version (descending)
        3. Minor version (descending)
        4. Date (descending - newer first)
        """
        # Simulate the version dicts from parsing
        versions = [
            {"major": 4, "minor": 0, "date": "20250514"},  # opus-4
            {"major": 4, "minor": 5, "date": "20251101"},  # opus-4-5
            {"major": 4, "minor": 1, "date": "20250805"},  # opus-4-1
            {"major": 3, "minor": 0, "date": "20240229"},  # claude-3-opus
        ]

        # Sort using same key as find_profile
        def sort_key(v: dict[str, int | str]) -> tuple[int, int, str]:
            return (
                -int(v["major"]),
                -int(v["minor"]),
                _negate_date(str(v["date"])),
            )

        sorted_versions = sorted(versions, key=sort_key)

        # Expected order: 4.5, 4.1, 4.0, 3.0
        assert sorted_versions[0]["minor"] == 5  # opus-4-5 first
        assert sorted_versions[1]["minor"] == 1  # opus-4-1 second
        assert sorted_versions[2]["major"] == 4 and sorted_versions[2]["minor"] == 0  # opus-4
        assert sorted_versions[3]["major"] == 3  # claude-3-opus last

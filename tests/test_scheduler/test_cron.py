"""Tests for huginn.scheduler.cron module."""

import pytest

from huginn.scheduler.cron import parse_cron


class TestParseCron:
    """Tests for parse_cron function."""

    def test_simple_asterisk(self):
        """parse_cron parses all-asterisk cron expression."""
        result = parse_cron("* * * * *")
        assert result == {
            "minute": "*",
            "hour": "*",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_step_values(self):
        """parse_cron parses step values (*/n)."""
        result = parse_cron("*/30 * * * *")
        assert result == {
            "minute": "*/30",
            "hour": "*",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_specific_values(self):
        """parse_cron parses specific numeric values."""
        result = parse_cron("0 9 * * 1-5")
        assert result == {
            "minute": "0",
            "hour": "9",
            "day": "*",
            "month": "*",
            "day_of_week": "1-5",
        }

    def test_complex_expression(self):
        """parse_cron parses complex cron with multiple parts."""
        result = parse_cron("15 2-4/2,6 * 1,3,5,7,9,11 1-5")
        assert result == {
            "minute": "15",
            "hour": "2-4/2,6",
            "day": "*",
            "month": "1,3,5,7,9,11",
            "day_of_week": "1-5",
        }

    def test_range_values(self):
        """parse_cron parses range expressions."""
        result = parse_cron("0 9-17 * * 1-5")
        assert result == {
            "minute": "0",
            "hour": "9-17",
            "day": "*",
            "month": "*",
            "day_of_week": "1-5",
        }

    def test_list_values(self):
        """parse_cron parses list expressions."""
        result = parse_cron("0 9,12,18 * * 1,2,3")
        assert result == {
            "minute": "0",
            "hour": "9,12,18",
            "day": "*",
            "month": "*",
            "day_of_week": "1,2,3",
        }

    def test_invalid_format_too_few_parts(self):
        """parse_cron raises ValueError for 4-part expression."""
        with pytest.raises(ValueError, match="Invalid cron format"):
            parse_cron("* * * *")

    def test_invalid_format_too_many_parts(self):
        """parse_cron raises ValueError for 6-part expression."""
        with pytest.raises(ValueError, match="Invalid cron format"):
            parse_cron("* * * * * *")

    def test_invalid_format_empty_string(self):
        """parse_cron raises ValueError for empty string."""
        with pytest.raises(ValueError, match="Invalid cron format"):
            parse_cron("")

    def test_invalid_random_string(self):
        """parse_cron raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid cron format"):
            parse_cron("invalid")

    def test_multiple_spaces_between_parts(self):
        """parse_cron handles multiple spaces between parts."""
        result = parse_cron("*  *  *  *  *")
        assert result == {
            "minute": "*",
            "hour": "*",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_whitespace_trimming(self):
        """parse_cron handles leading/trailing whitespace."""
        result = parse_cron("  */30 * * * *  ")
        assert result == {
            "minute": "*/30",
            "hour": "*",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

    def test_month_names(self):
        """parse_cron handles month names (passes through)."""
        result = parse_cron("0 9 * * mon-fri")
        assert result == {
            "minute": "0",
            "hour": "9",
            "day": "*",
            "month": "*",
            "day_of_week": "mon-fri",
        }

    def test_zero_values(self):
        """parse_cron handles zero values correctly."""
        result = parse_cron("0 0 * * *")
        assert result == {
            "minute": "0",
            "hour": "0",
            "day": "*",
            "month": "*",
            "day_of_week": "*",
        }

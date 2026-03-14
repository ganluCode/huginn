"""Tests for huginn.core.utils.text module."""

import pytest

from huginn.core.utils.text import clean_text, content_hash


class TestCleanText:
    """Tests for clean_text function."""

    def test_normal_string(self):
        """clean_text strips and compresses whitespace."""
        assert clean_text("  hello  world  ") == "hello world"

    def test_only_whitespace(self):
        """clean_text returns None for whitespace-only strings."""
        assert clean_text("  ") is None
        assert clean_text("\t\n") is None
        assert clean_text("   \t\t   \n\n   ") is None

    def test_empty_string(self):
        """clean_text returns None for empty string."""
        assert clean_text("") is None

    def test_non_str_input(self):
        """clean_text returns non-str input as-is (defensive)."""
        assert clean_text(123) == 123
        assert clean_text(None) is None
        assert clean_text(3.14) == 3.14
        assert clean_text(["a", "b"]) == ["a", "b"]

    def test_whitespace_variations(self):
        """clean_text normalizes tabs, newlines to single spaces."""
        assert clean_text("hello\t\tworld") == "hello world"
        assert clean_text("hello\n\nworld") == "hello world"
        assert clean_text("hello\r\nworld") == "hello world"
        assert clean_text("hello\t\n\rworld") == "hello world"

    def test_mixed_whitespace(self):
        """clean_text handles mixed whitespace types."""
        assert clean_text("  hello\t\t  world\n\n  ") == "hello world"

    def test_single_word(self):
        """clean_text works on single words."""
        assert clean_text("  hello  ") == "hello"

    def test_no_change_needed(self):
        """clean_text returns string unchanged if already clean."""
        assert clean_text("hello world") == "hello world"


class TestContentHash:
    """Tests for content_hash function."""

    def test_dict_order_independence(self):
        """content_hash returns same hash regardless of field order."""
        hash1 = content_hash({"b": 1, "a": 2})
        hash2 = content_hash({"a": 2, "b": 1})
        assert hash1 == hash2

    def test_dict_different_content(self):
        """content_hash returns different hash for different content."""
        hash1 = content_hash({"a": 1})
        hash2 = content_hash({"a": 2})
        assert hash1 != hash2

    def test_empty_dict(self):
        """content_hash returns deterministic hash for empty dict."""
        hash1 = content_hash({})
        hash2 = content_hash({})
        assert hash1 == hash2
        assert isinstance(hash1, str)

    def test_hash_length(self):
        """content_hash returns exactly 16 character hash."""
        result = content_hash({"a": 1})
        assert len(result) == 16

    def test_hash_is_hex_string(self):
        """content_hash returns lowercase hexadecimal string."""
        result = content_hash({"a": 1})
        assert result.islower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_nested_structures(self):
        """content_hash handles nested dict and list structures."""
        hash1 = content_hash({"a": [1, 2], "b": {"c": 3}})
        hash2 = content_hash({"b": {"c": 3}, "a": [1, 2]})
        assert hash1 == hash2

    def test_different_types(self):
        """content_hash handles different value types."""
        hash_int = content_hash({"a": 1})
        hash_str = content_hash({"a": "1"})
        assert hash_int != hash_str

    def test_list_order_matters(self):
        """content_hash treats list order as significant."""
        hash1 = content_hash({"a": [1, 2]})
        hash2 = content_hash({"a": [2, 1]})
        assert hash1 != hash2

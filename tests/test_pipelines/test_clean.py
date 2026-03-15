"""Tests for huginn.core.pipelines.clean module."""

from datetime import UTC, datetime

import pytest

from huginn.core.constants import Category
from huginn.core.exceptions import ValidationError
from huginn.core.items import CollectedItem
from huginn.core.pipelines.clean import CleanPipeline


class TestCleanPipelineValidation:
    """Tests for CleanPipeline validation logic."""

    def test_source_none_raises_validation_error(self):
        """source=None raises ValidationError."""
        pipeline = CleanPipeline()
        item = CollectedItem(source=None, category=Category.TECH, data={"title": "test"})

        with pytest.raises(ValidationError, match="source"):
            pipeline.process(item)

    def test_source_empty_string_raises_validation_error(self):
        """source='' raises ValidationError."""
        pipeline = CleanPipeline()
        item = CollectedItem(source="", category=Category.TECH, data={"title": "test"})

        with pytest.raises(ValidationError, match="source"):
            pipeline.process(item)

    def test_category_invalid_raises_validation_error(self):
        """Invalid category raises ValidationError with value in message."""
        pipeline = CleanPipeline()
        item = CollectedItem(source="test", category="invalid_category", data={"title": "test"})

        with pytest.raises(ValidationError) as exc_info:
            pipeline.process(item)

        assert "category" in str(exc_info.value)
        assert "invalid_category" in str(exc_info.value)

    def test_data_not_dict_raises_validation_error(self):
        """data not being a dict raises ValidationError."""
        pipeline = CleanPipeline()
        item = CollectedItem(source="test", category=Category.TECH, data="not_a_dict")

        with pytest.raises(ValidationError, match="data"):
            pipeline.process(item)

    def test_data_empty_dict_raises_validation_error(self):
        """Empty data dict raises ValidationError."""
        pipeline = CleanPipeline()
        item = CollectedItem(source="test", category=Category.TECH, data={})

        with pytest.raises(ValidationError, match="data"):
            pipeline.process(item)


class TestCleanPipelineTextCleaning:
    """Tests for CleanPipeline text cleaning logic."""

    def test_cleans_first_level_string_fields(self):
        """Cleans first-level string fields in data."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={"title": "  hello  world  ", "content": "test   content"},
        )

        result = pipeline.process(item)

        assert result.data["title"] == "hello world"
        assert result.data["content"] == "test content"

    def test_whitespace_compression(self):
        """Compresses tabs and newlines to single spaces."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test", category=Category.TECH, data={"text": "hello\t\tworld\n\n"}
        )

        result = pipeline.process(item)

        assert result.data["text"] == "hello world"

    def test_empty_string_becomes_none(self):
        """Empty/whitespace-only strings become None."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test", category=Category.TECH, data={"title": "   ", "content": ""}
        )

        result = pipeline.process(item)

        assert result.data["title"] is None
        assert result.data["content"] is None

    def test_nested_strings_unchanged(self):
        """Nested dict/list strings are not cleaned."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={
                "nested": {"title": "  hello  world  "},
                "list": ["  item1  ", "  item2  "],
            },
        )

        result = pipeline.process(item)

        assert result.data["nested"]["title"] == "  hello  world  "
        assert result.data["list"] == ["  item1  ", "  item2  "]

    def test_non_string_values_unchanged(self):
        """Non-string values remain unchanged."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={"count": 123, "score": 3.14, "flag": True, "tags": ["a", "b"]},
        )

        result = pipeline.process(item)

        assert result.data["count"] == 123
        assert result.data["score"] == 3.14
        assert result.data["flag"] is True
        assert result.data["tags"] == ["a", "b"]


class TestCleanPipelineTimestamp:
    """Tests for CleanPipeline timestamp handling."""

    def test_collected_at_none_set_to_utc_now(self):
        """collected_at=None is set to timezone-aware datetime."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={"title": "test"},
            collected_at=None,
        )

        result = pipeline.process(item)

        assert result.collected_at is not None
        assert result.collected_at.tzinfo is not None

    def test_collected_at_already_set_unchanged(self):
        """Existing collected_at is unchanged."""
        pipeline = CleanPipeline()
        original_time = datetime(2024, 1, 1, tzinfo=UTC)
        item = CollectedItem(
            source="test",
            category=Category.TECH,
            data={"title": "test"},
            collected_at=original_time,
        )

        result = pipeline.process(item)

        assert result.collected_at == original_time


class TestCleanPipelineSuccess:
    """Tests for successful CleanPipeline processing."""

    def test_valid_item_returns_collected_item(self):
        """Valid item returns CollectedItem."""
        pipeline = CleanPipeline()
        item = CollectedItem(
            source="test", category=Category.TECH, data={"title": "test"}
        )

        result = pipeline.process(item)

        assert isinstance(result, CollectedItem)
        assert result.source == "test"
        assert result.category == Category.TECH

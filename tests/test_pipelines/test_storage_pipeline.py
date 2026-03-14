"""Tests for huginn.core.pipelines.storage module."""

from unittest.mock import MagicMock

import pytest

from huginn.core.constants import Category
from huginn.core.exceptions import StorageError
from huginn.core.items import CollectedItem
from huginn.core.pipelines.storage import StoragePipeline


class TestStoragePipelineSuccess:
    """Tests for successful StoragePipeline operations."""

    def test_save_items_called_correctly(self):
        """backend.save_items is called with correct arguments."""
        mock_backend = MagicMock()
        mock_backend.save_items.return_value = 3

        pipeline = StoragePipeline(backend=mock_backend)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        result = pipeline.process(item)

        # Check save_items was called correctly
        mock_backend.save_items.assert_called_once_with("test", Category.TECH, [{"title": "test"}])
        assert result == item

    def test_returns_item_on_success(self):
        """process() returns item on successful save."""
        mock_backend = MagicMock()
        mock_backend.save_items.return_value = 1

        pipeline = StoragePipeline(backend=mock_backend)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        result = pipeline.process(item)

        assert result == item
        assert result.source == "test"
        assert result.category == Category.TECH


class TestStoragePipelineFailure:
    """Tests for StoragePipeline failure handling."""

    def test_raises_storage_error_on_failure(self):
        """StorageError is raised when save_items fails."""
        mock_backend = MagicMock()
        mock_backend.save_items.side_effect = Exception("Database error")

        pipeline = StoragePipeline(backend=mock_backend)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        with pytest.raises(StorageError):
            pipeline.process(item)

    def test_storage_error_wraps_original_exception(self):
        """StorageError wraps the original exception."""
        mock_backend = MagicMock()
        original_error = ValueError("Invalid data")
        mock_backend.save_items.side_effect = original_error

        pipeline = StoragePipeline(backend=mock_backend)
        item = CollectedItem(source="test", category=Category.TECH, data={"title": "test"})

        with pytest.raises(StorageError) as exc_info:
            pipeline.process(item)

        # Original exception should be chained
        assert exc_info.value.__cause__ is original_error

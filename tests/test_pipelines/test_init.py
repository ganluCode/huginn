"""Tests for huginn.core.pipelines module."""

from datetime import UTC, datetime

import pytest

from huginn.core.items import CollectedItem
from huginn.core.pipelines import Pipeline, run_pipeline_chain


class MockPipeline:
    """Mock pipeline for testing.

    If return_value is explicitly set (including None), it will be returned.
    Otherwise, the item is returned unchanged.
    """

    def __init__(self, return_value=..., raise_exception=None):
        self.return_value = return_value
        self.raise_exception = raise_exception
        self.call_count = 0
        self._sentinel = ...

    def process(self, item: CollectedItem) -> CollectedItem | None:
        self.call_count += 1
        if self.raise_exception:
            raise self.raise_exception
        if self.return_value is not self._sentinel:
            return self.return_value
        return item


class TestPipelineProtocol:
    """Tests for Pipeline Protocol."""

    def test_mock_pipeline_conforms_to_protocol(self):
        """Mock pipeline should conform to Pipeline protocol."""
        pipeline = MockPipeline()
        item = CollectedItem(source="test", category="tech", data={"test": "data"})

        # Should not raise type error
        result = pipeline.process(item)
        assert result == item


class TestRunPipelineChain:
    """Tests for run_pipeline_chain function."""

    def test_empty_pipeline_list(self):
        """Empty pipeline list returns item unchanged."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})
        result = run_pipeline_chain([], item)
        assert result == item

    def test_single_pipeline(self):
        """Single pipeline processes item."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})
        pipeline = MockPipeline()
        result = run_pipeline_chain([pipeline], item)
        assert result == item
        assert pipeline.call_count == 1

    def test_multiple_pipelines_all_pass(self):
        """All pipelines process item in sequence."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})
        pipeline1 = MockPipeline()
        pipeline2 = MockPipeline()
        pipeline3 = MockPipeline()

        result = run_pipeline_chain([pipeline1, pipeline2, pipeline3], item)

        assert result == item
        assert pipeline1.call_count == 1
        assert pipeline2.call_count == 1
        assert pipeline3.call_count == 1

    def test_pipeline_returns_none_stops_chain(self):
        """Pipeline returning None stops chain and returns None."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})
        pipeline1 = MockPipeline()
        pipeline2 = MockPipeline(return_value=None)
        pipeline3 = MockPipeline()

        result = run_pipeline_chain([pipeline1, pipeline2, pipeline3], item)

        assert result is None
        assert pipeline1.call_count == 1
        assert pipeline2.call_count == 1
        assert pipeline3.call_count == 0

    def test_pipeline_exception_propagates(self):
        """Pipeline exception propagates up."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})
        pipeline1 = MockPipeline()
        pipeline2 = MockPipeline(raise_exception=ValueError("Test error"))
        pipeline3 = MockPipeline()

        with pytest.raises(ValueError, match="Test error"):
            run_pipeline_chain([pipeline1, pipeline2, pipeline3], item)

        assert pipeline1.call_count == 1
        assert pipeline2.call_count == 1
        assert pipeline3.call_count == 0

    def test_pipeline_modifies_item(self):
        """Pipeline can modify item."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})

        class ModifyPipeline:
            def __init__(self):
                self.call_count = 0

            def process(self, item: CollectedItem) -> CollectedItem | None:
                self.call_count += 1
                item.data["modified"] = True
                return item

        pipeline = ModifyPipeline()
        result = run_pipeline_chain([pipeline], item)

        assert result.data["modified"] is True
        assert pipeline.call_count == 1

    def test_first_pipeline_returns_none(self):
        """First pipeline returning None returns None immediately."""
        item = CollectedItem(source="test", category="tech", data={"test": "data"})
        pipeline1 = MockPipeline(return_value=None)
        pipeline2 = MockPipeline()

        result = run_pipeline_chain([pipeline1, pipeline2], item)

        assert result is None
        assert pipeline1.call_count == 1
        assert pipeline2.call_count == 0

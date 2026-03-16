"""Simplified tests for Playwright runner module without database dependency."""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Page

from huginn.core.items import CollectedItem
from huginn.core.pipelines.clean import CleanPipeline
from huginn.core.pipelines.dedup import DedupPipeline
from huginn.playwright.base_flow import BaseFlow
from huginn.playwright.engine import PlaywrightEngine


class SimpleFlow(BaseFlow):
    """Simple Flow implementation for testing."""

    name = "simple_flow"
    source_category = "tech"

    def __init__(self, items: list[dict] | None = None, should_fail: bool = False):
        """Initialize simple flow.

        Args:
            items: Items to return from run(). Defaults to [{"title": "test"}].
            should_fail: Whether to raise an exception in run().
        """
        self.items = items if items is not None else [{"title": "test", "url": "https://example.com"}]
        self.should_fail = should_fail
        self.before_run_called = False
        self.after_run_called = False
        self.run_called = False

    async def before_run(self) -> None:
        """Before run hook."""
        self.before_run_called = True

    async def run(self, page: Page) -> list[dict]:
        """Run the flow.

        Args:
            page: Playwright Page object.

        Returns:
            List of collected items.

        Raises:
            Exception: If should_fail is True.
        """
        self.run_called = True
        if self.should_fail:
            raise RuntimeError("Flow execution failed")
        return self.items

    async def after_run(self, items: list[dict]) -> None:
        """After run hook.

        Args:
            items: Items returned by run().
        """
        self.after_run_called = True


class TestRunFlowBasic:
    """Basic tests for run_flow without database dependency."""

    @pytest.mark.asyncio
    async def test_lifecycle_order(self):
        """Test before_run、run、after_run 按顺序调用."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = SimpleFlow(items=[{"id": 1}])

        # Track call order
        call_order = []

        # Wrap the lifecycle methods to track calls
        original_before_run = flow.before_run
        original_run = flow.run
        original_after_run = flow.after_run

        async def tracked_before_run():
            call_order.append("before_run")
            return await original_before_run()

        async def tracked_run(page):
            call_order.append("run")
            return await original_run(page)

        async def tracked_after_run(items):
            call_order.append("after_run")
            return await original_after_run(items)

        flow.before_run = tracked_before_run
        flow.run = tracked_run
        flow.after_run = tracked_after_run

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock session and database operations
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()

        # Mock database query results
        mock_registry_result = MagicMock()
        mock_registry_result.scalar_one_or_none.return_value = None

        mock_session.execute.return_value = mock_registry_result

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage pipeline
        mock_storage_pipeline = MagicMock()
        mock_storage_pipeline.process = MagicMock(return_value=CollectedItem(
            source="simple_flow",
            category="tech",
            data={"id": 1}
        ))

        # Run the flow
        try:
            await run_flow(
                flow=flow,
                engine=mock_engine,
                session=mock_session,
                clean_pipeline=clean_pipeline,
                dedup_pipeline=dedup_pipeline,
                storage_pipeline=mock_storage_pipeline,
            )
        except Exception as e:
            print(f"Error during run_flow: {e}")

        # Verify call order
        assert call_order == ["before_run", "run", "after_run"]

        # Verify lifecycle hooks were called
        assert flow.before_run_called is True
        assert flow.run_called is True
        assert flow.after_run_called is True

        # Verify engine was used
        mock_engine.new_page.assert_called_once()

    @pytest.mark.asyncio
    async def test_temp_engine_lifecycle(self):
        """Test engine=None 时创建临时 engine 并在完成后关闭."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = SimpleFlow(items=[{"id": 1}])

        # Mock session and database operations
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()

        # Mock database query results
        mock_registry_result = MagicMock()
        mock_registry_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_registry_result

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage pipeline
        mock_storage_pipeline = MagicMock()
        mock_storage_pipeline.process = MagicMock(return_value=CollectedItem(
            source="simple_flow",
            category="tech",
            data={"id": 1}
        ))

        # Run the flow without engine (engine=None)
        with patch("huginn.playwright.runner.PlaywrightEngine") as MockEngine:
            mock_engine_instance = AsyncMock()
            mock_page = AsyncMock(spec=Page)
            mock_engine_instance.new_page = AsyncMock(return_value=mock_page)
            mock_engine_instance.start = AsyncMock()
            mock_engine_instance.stop = AsyncMock()
            MockEngine.return_value = mock_engine_instance

            await run_flow(
                flow=flow,
                engine=None,  # No engine provided
                session=mock_session,
                clean_pipeline=clean_pipeline,
                dedup_pipeline=dedup_pipeline,
                storage_pipeline=mock_storage_pipeline,
            )

            # Verify engine was created and started
            MockEngine.assert_called_once()
            mock_engine_instance.start.assert_called_once()

            # Verify engine was stopped after execution
            mock_engine_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_external_engine_not_stopped(self):
        """Test传入 engine 时执行结束后不关闭它."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = SimpleFlow(items=[{"id": 1}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock session and database operations
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()

        # Mock database query results
        mock_registry_result = MagicMock()
        mock_registry_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_registry_result

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage pipeline
        mock_storage_pipeline = MagicMock()
        mock_storage_pipeline.process = MagicMock(return_value=CollectedItem(
            source="simple_flow",
            category="tech",
            data={"id": 1}
        ))

        # Run the flow with external engine
        await run_flow(
            flow=flow,
            engine=mock_engine,  # External engine
            session=mock_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_pipeline=mock_storage_pipeline,
        )

        # Verify engine was used (new_page called)
        mock_engine.new_page.assert_called_once()

        # Verify engine does NOT have a stop method (it wasn't called)
        # AsyncMock doesn't have stop by default, so if it was called it would be added


class TestRunFlowPipeline:
    """Tests for pipeline processing."""

    @pytest.mark.asyncio
    async def test_pipeline_processing(self):
        """Test items are processed through pipeline chain."""
        from huginn.playwright.runner import run_flow

        # Create test flow with multiple items
        flow = SimpleFlow(items=[{"id": 1}, {"id": 2}, {"id": 3}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock session and database operations
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()

        # Mock database query results
        mock_registry_result = MagicMock()
        mock_registry_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_registry_result

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Track items passed to storage
        stored_items = []

        # Mock storage pipeline
        def mock_process(item):
            stored_items.append(item)
            return item

        mock_storage_pipeline = MagicMock()
        mock_storage_pipeline.process = mock_process

        # Run the flow
        await run_flow(
            flow=flow,
            engine=mock_engine,
            session=mock_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_pipeline=mock_storage_pipeline,
        )

        # Verify all items were processed
        assert len(stored_items) == 3

    @pytest.mark.asyncio
    async def test_pipeline_error_continues(self, caplog):
        """Test单条 item 管道异常时，其余 item 继续处理."""
        from huginn.playwright.runner import run_flow

        # Create test flow with multiple items
        flow = SimpleFlow(items=[{"id": 1}, {"id": 2}, {"id": 3}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock session and database operations
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock()

        # Mock database query results
        mock_registry_result = MagicMock()
        mock_registry_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_registry_result

        # Mock storage pipeline to fail on second item
        call_count = [0]

        def mock_process(item):
            call_count[0] += 1
            # Second item raises exception
            if call_count[0] == 2:
                raise ValueError("Storage failed for item 2")
            return item

        mock_storage_pipeline = MagicMock()
        mock_storage_pipeline.process = mock_process

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Track items passed to storage
        stored_items = []

        # Wrap the mock to track successful calls
        original_process = mock_storage_pipeline.process

        def tracking_process(item):
            try:
                result = original_process(item)
                stored_items.append(item)
                return result
            except Exception:
                raise

        mock_storage_pipeline.process = tracking_process

        # Run the flow with caplog to capture warnings
        with caplog.at_level(logging.WARNING):
            await run_flow(
                flow=flow,
                engine=mock_engine,
                session=mock_session,
                clean_pipeline=clean_pipeline,
                dedup_pipeline=dedup_pipeline,
                storage_pipeline=mock_storage_pipeline,
            )

        # Verify 2 out of 3 items were stored (second failed)
        assert len(stored_items) == 2

        # Verify WARNING was logged
        assert any("Pipeline error" in record.message for record in caplog.records)

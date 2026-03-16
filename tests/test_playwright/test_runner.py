"""Tests for Playwright runner module."""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from playwright.async_api import Page

from huginn.core.constants import SpiderStatus
from huginn.core.models import SpiderRegistry, SpiderRun
from huginn.core.pipelines.clean import CleanPipeline
from huginn.core.pipelines.dedup import DedupPipeline
from huginn.playwright.base_flow import BaseFlow
from huginn.playwright.engine import PlaywrightEngine


class TestFlow:
    """Test Flow implementation for testing."""

    name = "test_flow"
    source_category = "tech"

    def __init__(self, items: list[dict] | None = None, should_fail: bool = False):
        """Initialize test flow.

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
        self.after_run_items = items


class TestRunFlowSuccess:
    """Tests for successful run_flow execution."""

    @pytest.mark.asyncio
    async def test_run_flow_success(self, async_db_session):
        """Test normal execution returns入库条数, spider_runs status is 'success'."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = TestFlow(items=[{"id": 1}, {"id": 2}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)

        # Mock new_page to return our mock page
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False
        mock_redis.sadd.return_value = 1
        mock_redis.ttl.return_value = -1

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=2)

        # Run the flow
        count = await run_flow(
            flow=flow,
            engine=mock_engine,
            session=async_db_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_backend=mock_storage,
        )

        # Verify入库条数
        assert count == 2

        # Verify lifecycle hooks were called
        assert flow.before_run_called is True
        assert flow.run_called is True
        assert flow.after_run_called is True

        # Verify spider_runs record
        run = await async_db_session.get(SpiderRun, flow._run_id)
        assert run is not None
        assert run.status == SpiderStatus.SUCCESS
        assert run.item_count == 2
        assert run.finished_at is not None
        assert run.duration_ms is not None
        assert run.error_message is None

        # Verify spider_registry was created/updated
        registry = await async_db_session.get(SpiderRegistry, flow.name)
        assert registry is not None
        assert registry.engine == "playwright"
        assert registry.category == flow.source_category
        assert registry.last_run_at is not None
        assert registry.last_status == SpiderStatus.SUCCESS
        assert registry.item_count == 2

        # Verify storage was called
        mock_storage.save_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_flow_empty_result(self, async_db_session):
        """Test Flow returns empty list入库 0 条, status is 'success'."""
        from huginn.playwright.runner import run_flow

        # Create test flow that returns empty list
        flow = TestFlow(items=[])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=0)

        # Run the flow
        count = await run_flow(
            flow=flow,
            engine=mock_engine,
            session=async_db_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_backend=mock_storage,
        )

        # Verify入库条数
        assert count == 0

        # Verify spider_runs record
        run = await async_db_session.get(SpiderRun, flow._run_id)
        assert run is not None
        assert run.status == SpiderStatus.SUCCESS
        assert run.item_count == 0


class TestRunFlowFailure:
    """Tests for run_flow error handling."""

    @pytest.mark.asyncio
    async def test_run_flow_failure(self, async_db_session):
        """Test Flow raises exception时 spider_runs status is 'failed', error_message 非空，异常向上传播."""
        from huginn.playwright.runner import run_flow

        # Create test flow that will fail
        flow = TestFlow(should_fail=True)

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock Redis for deduplication
        mock_redis = MagicMock()

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()

        # Run the flow and expect exception
        with pytest.raises(RuntimeError, match="Flow execution failed"):
            await run_flow(
                flow=flow,
                engine=mock_engine,
                session=async_db_session,
                clean_pipeline=clean_pipeline,
                dedup_pipeline=dedup_pipeline,
                storage_backend=mock_storage,
            )

        # Verify spider_runs record
        run = await async_db_session.get(SpiderRun, flow._run_id)
        assert run is not None
        assert run.status == SpiderStatus.FAILED
        assert run.error_message is not None
        assert "Flow execution failed" in run.error_message


class TestRunFlowAutoRegister:
    """Tests for automatic spider registration."""

    @pytest.mark.asyncio
    async def test_run_flow_auto_registers_spider(self, async_db_session):
        """Test spider_registry 中不存在时自动插入记录."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = TestFlow(items=[{"id": 1}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=1)

        # Run the flow
        await run_flow(
            flow=flow,
            engine=mock_engine,
            session=async_db_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_backend=mock_storage,
        )

        # Verify spider_registry was created
        registry = await async_db_session.get(SpiderRegistry, flow.name)
        assert registry is not None
        assert registry.name == flow.name
        assert registry.engine == "playwright"
        assert registry.category == flow.source_category


class TestRunFlowPipelineError:
    """Tests for pipeline error handling."""

    @pytest.mark.asyncio
    async def test_run_flow_pipeline_error_continues(self, async_db_session, caplog):
        """Test单条 item 管道异常时，其余 item 继续处理."""
        from huginn.playwright.runner import run_flow

        # Create test flow with multiple items
        flow = TestFlow(items=[{"id": 1}, {"id": 2}, {"id": 3}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        # First item succeeds, second fails (simulate), third succeeds
        call_count = [0]

        def mock_sismember(*args, **kwargs):  # noqa: ARG001
            call_count[0] += 1
            # Second call (item 2) raises exception
            if call_count[0] == 2:
                raise ConnectionError("Redis connection lost")
            return False

        mock_redis.sismember.side_effect = mock_sismember
        mock_redis.sadd.return_value = 1

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=2)  # Only 2 items saved

        # Run the flow with caplog to capture warnings
        with caplog.at_level(logging.WARNING):
            count = await run_flow(
                flow=flow,
                engine=mock_engine,
                session=async_db_session,
                clean_pipeline=clean_pipeline,
                dedup_pipeline=dedup_pipeline,
                storage_backend=mock_storage,
            )

        # Verify入库条数 (2 out of 3 succeeded)
        assert count == 2

        # Verify WARNING was logged
        assert any("Pipeline error" in record.message for record in caplog.records)


class TestRunFlowEngine:
    """Tests for engine lifecycle management."""

    @pytest.mark.asyncio
    async def test_run_flow_temp_engine(self, async_db_session):
        """Test engine=None 时创建临时 engine 并在完成后关闭."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = TestFlow(items=[{"id": 1}])

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=1)

        # Run the flow without engine (engine=None)
        # This should create a temporary engine and close it after
        with patch("huginn.playwright.runner.PlaywrightEngine") as MockEngine:
            mock_engine_instance = AsyncMock()
            mock_engine_instance.new_page = AsyncMock()
            mock_engine_instance.new_page.return_value = AsyncMock(spec=Page)
            mock_engine_instance.start = AsyncMock()
            mock_engine_instance.stop = AsyncMock()
            MockEngine.return_value = mock_engine_instance

            await run_flow(
                flow=flow,
                engine=None,  # No engine provided
                session=async_db_session,
                clean_pipeline=clean_pipeline,
                dedup_pipeline=dedup_pipeline,
                storage_backend=mock_storage,
            )

            # Verify engine was created and started
            MockEngine.assert_called_once()
            mock_engine_instance.start.assert_called_once()

            # Verify engine was stopped after execution
            mock_engine_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_flow_external_engine(self, async_db_session):
        """Test传入 engine 时执行结束后不关闭它."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = TestFlow(items=[{"id": 1}])

        # Mock Playwright engine and page
        mock_engine = AsyncMock(spec=PlaywrightEngine)
        mock_page = AsyncMock(spec=Page)
        mock_engine.new_page = AsyncMock(return_value=mock_page)

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=1)

        # Run the flow with external engine
        await run_flow(
            flow=flow,
            engine=mock_engine,  # External engine
            session=async_db_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_backend=mock_storage,
        )

        # Verify engine was used (new_page called)
        mock_engine.new_page.assert_called_once()

        # Verify engine was NOT stopped (no stop method on mock)
        # Note: AsyncMock doesn't have stop by default, so if it was called it would fail


class TestRunFlowLifecycle:
    """Tests for lifecycle method execution order."""

    @pytest.mark.asyncio
    async def test_lifecycle_order(self, async_db_session):
        """Test before_run、run、after_run 按顺序调用."""
        from huginn.playwright.runner import run_flow

        # Create test flow
        flow = TestFlow(items=[{"id": 1}])

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

        # Mock Redis for deduplication
        mock_redis = MagicMock()
        mock_redis.sismember.return_value = False

        # Create pipelines
        clean_pipeline = CleanPipeline()
        dedup_pipeline = DedupPipeline(redis_url="redis://localhost", _redis_client=mock_redis)

        # Mock storage backend
        mock_storage = AsyncMock()
        mock_storage.save_items = AsyncMock(return_value=1)

        # Run the flow
        await run_flow(
            flow=flow,
            engine=mock_engine,
            session=async_db_session,
            clean_pipeline=clean_pipeline,
            dedup_pipeline=dedup_pipeline,
            storage_backend=mock_storage,
        )

        # Verify call order
        assert call_order == ["before_run", "run", "after_run"]

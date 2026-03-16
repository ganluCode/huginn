"""Playwright Flow runner module.

This module provides the run_flow() function, which executes a Playwright Flow
through its lifecycle (before_run → run → after_run), processes collected items
through the core pipeline chain (clean → dedup → storage), and tracks execution
in the database (spider_runs and spider_registry).

Typical usage:
    from huginn.playwright.runner import run_flow
    from huginn.playwright.flows import MyFlow

    flow = MyFlow()
    count = await run_flow(flow)
    print(f"Collected {count} items")
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from huginn.core.items import CollectedItem
from huginn.core.models import SpiderRegistry, SpiderRun
from huginn.core.pipelines import Pipeline, run_pipeline_chain
from huginn.playwright.base_flow import BaseFlow
from huginn.playwright.engine import PlaywrightEngine

logger = logging.getLogger(__name__)


async def run_flow(
    flow: BaseFlow,
    engine: PlaywrightEngine | None = None,
    session: AsyncSession | None = None,
    clean_pipeline: Pipeline | None = None,
    dedup_pipeline: Pipeline | None = None,
    storage_pipeline: Pipeline | None = None,
    storage_backend=None,
) -> int:
    """Execute a Playwright Flow through its complete lifecycle.

    This function manages the entire Flow execution process:
    1. Creates/uses Playwright engine
    2. Registers spider in spider_registry if not exists
    3. Inserts spider_runs record with status='running'
    4. Executes lifecycle: before_run → run → after_run
    5. Processes each item through the pipeline chain
    6. Updates spider_runs and spider_registry on completion

    Args:
        flow: The BaseFlow instance to execute.
        engine: Optional PlaywrightEngine. If None, creates a temporary engine
               that is closed after execution. If provided, uses it without closing.
        session: Optional AsyncSession for database operations. If None, creates
                a temporary session that is closed after execution.
        clean_pipeline: Optional CleanPipeline instance. If None, creates one.
        dedup_pipeline: Optional DedupPipeline instance. If None, creates one.
        storage_pipeline: Optional StoragePipeline instance. If None, creates one
                         using the storage_backend.
        storage_backend: Optional storage backend for StoragePipeline.

    Returns:
        The number of items successfully stored in the database.

    Raises:
        Exception: Any exception from Flow execution is logged and re-raised
                  after updating spider_runs to 'failed' status.

    Example:
        >>> flow = MyFlow()
        >>> count = await run_flow(flow)
        >>> print(f"Collected {count} items")
    """
    # Import here to avoid circular imports
    from huginn.core.config import settings
    from huginn.core.db import AsyncSessionLocal
    from huginn.core.pipelines.clean import CleanPipeline
    from huginn.core.pipelines.dedup import DedupPipeline
    from huginn.core.pipelines.storage import StoragePipeline
    from huginn.core.storage import PostgresBackend

    # Track if we created the engine (to close it later)
    _created_engine = False
    _created_session = False

    try:
        # === Step 1: Engine setup ===
        if engine is None:
            # Create temporary engine
            engine = PlaywrightEngine()
            await engine.start()
            _created_engine = True
            logger.debug("Created temporary PlaywrightEngine for flow: %s", flow.name)

        # === Step 2: Session setup ===
        if session is None:
            # Create temporary session
            session = AsyncSessionLocal()
            _created_session = True
            logger.debug("Created temporary AsyncSession for flow: %s", flow.name)

        # === Step 3: Pipeline setup ===
        if clean_pipeline is None:
            clean_pipeline = CleanPipeline()

        if dedup_pipeline is None:
            dedup_pipeline = DedupPipeline(redis_url=settings.redis_url)

        if storage_pipeline is None:
            if storage_backend is None:
                storage_backend = PostgresBackend()
            storage_pipeline = StoragePipeline(storage_backend)

        # === Step 4: Build pipeline chain ===
        pipelines = [clean_pipeline, dedup_pipeline, storage_pipeline]

        # === Step 5: Register spider in spider_registry ===
        await _ensure_spider_registered(session, flow)

        # === Step 6: Insert spider_runs record ===
        started_at = datetime.now(UTC)
        run_record = SpiderRun(
            spider_name=flow.name,
            started_at=started_at,
            status="running",
            item_count=0,
        )
        session.add(run_record)
        await session.flush()
        run_id = run_record.id

        # Store run_id on flow for potential external access
        flow._run_id = run_id  # noqa: SLF001 (private attribute is intentional)

        logger.info("Started flow run: flow=%s, run_id=%s", flow.name, run_id)

        # === Step 7: Execute Flow lifecycle ===
        # Create a page for the flow
        page = await engine.new_page()

        # Call before_run hook
        await flow.before_run()

        # Execute the main run method
        raw_items = await flow.run(page)

        # Call after_run hook
        await flow.after_run(raw_items)

        # Close the page
        await page.close()

        # === Step 8: Process items through pipeline chain ===
        item_count = 0
        for raw_item in raw_items:
            # Create CollectedItem from raw data
            collected_item = CollectedItem(
                source=flow.name,
                category=flow.source_category,
                data=raw_item,
                collected_at=datetime.now(UTC),
            )

            # Process through pipeline chain
            try:
                result = run_pipeline_chain(pipelines, collected_item)
                if result is not None:
                    item_count += 1
                else:
                    # Item was filtered out by a pipeline
                    logger.debug("Item filtered out by pipeline: source=%s", flow.name)
            except Exception as e:
                # Log warning but continue processing other items
                logger.warning("Pipeline error for item in flow %s: %s", flow.name, e)

        # === Step 9: Update spider_runs on success ===
        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        run_record.finished_at = finished_at
        run_record.status = "success"
        run_record.item_count = item_count
        run_record.duration_ms = duration_ms
        run_record.error_message = None

        # === Step 10: Update spider_registry ===
        registry_result = await session.execute(
            select(SpiderRegistry).where(SpiderRegistry.name == flow.name)
        )
        registry = registry_result.scalar_one_or_none()

        if registry is not None:
            registry.last_run_at = finished_at
            registry.last_status = "success"
            # Accumulate item count (not replace)
            registry.item_count = (registry.item_count or 0) + item_count

        # Commit all database changes
        await session.commit()

        logger.info(
            "Finished flow run: flow=%s, run_id=%s, status=success, items=%d, duration_ms=%d",
            flow.name,
            run_id,
            item_count,
            duration_ms,
        )

        return item_count

    except Exception as e:
        # Handle failure: update spider_runs to 'failed'
        logger.exception("Flow execution failed: flow=%s, error=%s", flow.name, e)

        if session is not None and "run_id" in locals():
            try:
                # Query the run record
                run_result = await session.execute(
                    select(SpiderRun).where(SpiderRun.id == run_id)
                )
                run_record = run_result.scalar_one_or_none()

                if run_record is not None:
                    finished_at = datetime.now(UTC)
                    duration_ms = int((finished_at - started_at).total_seconds() * 1000) if "started_at" in locals() else 0

                    run_record.finished_at = finished_at
                    run_record.status = "failed"
                    run_record.error_message = str(e)[:1000]  # Limit error message length
                    run_record.duration_ms = duration_ms

                    # Update spider_registry
                    registry_result = await session.execute(
                        select(SpiderRegistry).where(SpiderRegistry.name == flow.name)
                    )
                    registry = registry_result.scalar_one_or_none()

                    if registry is not None:
                        registry.last_run_at = finished_at
                        registry.last_status = "failed"

                    await session.commit()
            except Exception as db_error:
                logger.error("Failed to update failure status to database: %s", db_error)
                if session is not None:
                    await session.rollback()

        # Re-raise the exception
        raise

    finally:
        # Clean up resources we created
        if _created_session and session is not None:
            await session.close()
            logger.debug("Closed temporary AsyncSession for flow: %s", flow.name)

        if _created_engine and engine is not None:
            await engine.stop()
            logger.debug("Stopped temporary PlaywrightEngine for flow: %s", flow.name)


async def _ensure_spider_registered(session: AsyncSession, flow: BaseFlow) -> None:
    """Ensure the Flow is registered in spider_registry.

    If the Flow doesn't exist in spider_registry, insert a new record
    with engine='playwright', category=flow.source_category, enabled=True.

    Args:
        session: SQLAlchemy async session.
        flow: The BaseFlow instance to register.
    """
    from sqlalchemy import select

    # Check if spider exists
    result = await session.execute(
        select(SpiderRegistry).where(SpiderRegistry.name == flow.name)
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        # Auto-register the flow
        registry = SpiderRegistry(
            name=flow.name,
            engine="playwright",
            category=flow.source_category,
            enabled=True,
            item_count=0,
        )
        session.add(registry)
        await session.flush()
        logger.info(
            "Auto-registered flow: name=%s, category=%s, engine=playwright",
            flow.name,
            flow.source_category,
        )
    else:
        logger.debug("Flow already registered: %s", flow.name)


__all__ = ["run_flow"]

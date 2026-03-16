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

CLI usage:
    python -m huginn.playwright.runner <flow_name>
    python -m huginn.playwright.runner --list
    python -m huginn.playwright.runner --help
"""

import argparse
import asyncio
import importlib.util
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

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


def _discover_flows(flows_dir: str | None = None) -> dict[str, type[BaseFlow]]:
    """Discover all BaseFlow subclasses in the flows directory.

    This function scans the flows directory for Python files, imports them,
    and collects all BaseFlow subclasses into a dictionary keyed by flow.name.

    Args:
        flows_dir: Path to the flows directory. If None, uses the default
                   huginn/playwright/flows directory.

    Returns:
        A dictionary mapping flow names to Flow classes.
    """
    if flows_dir is None:
        # Get the default flows directory
        current_file = Path(__file__)
        flows_dir = str(current_file.parent / "flows")

    flows: dict[str, type[BaseFlow]] = {}
    flows_path = Path(flows_dir)

    if not flows_path.exists():
        logger.warning("Flows directory does not exist: %s", flows_dir)
        return flows

    # Find all Python files in the flows directory
    for py_file in flows_path.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        # Import the module
        module_name = f"huginn.playwright.flows.{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                logger.warning("Could not load spec for %s", py_file)
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find all BaseFlow subclasses in the module
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseFlow)
                    and attr is not BaseFlow
                ):
                    flow_class = attr
                    flow_name = getattr(flow_class, "name", None)
                    if flow_name:
                        flows[flow_name] = flow_class
                        logger.debug("Discovered flow: %s from %s", flow_name, py_file.name)

        except Exception as e:
            logger.error("Failed to import %s: %s", py_file, e)

    return flows


def _parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: List of command line arguments. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="huginn.playwright.runner",
        description="Run Playwright data collection flows.",
    )
    parser.add_argument(
        "flow_name",
        nargs="?",
        help="Name of the flow to run (use --list to see available flows)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available flows and exit",
    )
    parser.add_argument(
        "--flows-dir",
        type=str,
        default=None,
        help="Path to flows directory (default: huginn/playwright/flows)",
    )

    return parser.parse_args(args)


def _print_available_flows(flows: dict[str, type[BaseFlow]]) -> None:
    """Print available flows to stdout.

    Args:
        flows: Dictionary of flow names to Flow classes.
    """
    if not flows:
        print("No flows found.")
        return

    print("Available flows:")
    for flow_name in sorted(flows.keys()):
        flow_class = flows[flow_name]
        category = getattr(flow_class, "source_category", "unknown")
        print(f"  - {flow_name} (category: {category})")


def main(args: list[str] | None = None) -> None:
    """CLI entry point for running Playwright flows.

    This function is called when executing:
        python -m huginn.playwright.runner <flow_name>

    Args:
        args: Command line arguments. If None, uses sys.argv[1:].

    Returns:
        None. Exits with appropriate status code.

    Raises:
        SystemExit: On error or when requested (e.g., --help).
    """
    parsed_args = _parse_args(args)

    # Discover flows
    flows = _discover_flows(parsed_args.flows_dir)

    # Handle --list
    if parsed_args.list:
        _print_available_flows(flows)
        sys.exit(0)

    # Check if flow_name is provided
    if not parsed_args.flow_name:
        print("Error: No flow name specified.", file=sys.stderr)
        print("Use --list to see available flows or --help for usage.", file=sys.stderr)
        sys.exit(1)

    # Check if flow exists
    flow_name = parsed_args.flow_name
    if flow_name not in flows:
        print(f"Error: Flow '{flow_name}' not found.", file=sys.stderr)
        print(f"Available flows: {', '.join(sorted(flows.keys()))}", file=sys.stderr)
        sys.exit(1)

    # Run the flow
    flow_class = flows[flow_name]
    flow = flow_class()

    try:
        # Run the flow in an async context
        count = asyncio.run(run_flow(flow))
        print(f"Collected {count} items")
        sys.exit(0)
    except Exception as e:
        print(f"Error running flow '{flow_name}': {e}", file=sys.stderr)
        logger.exception("Flow execution failed")
        sys.exit(1)


__all__ = ["run_flow", "main", "_discover_flows"]

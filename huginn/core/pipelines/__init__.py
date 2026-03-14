"""Data processing pipeline framework.

This module provides the pipeline framework for processing collected data.
Pipelines are used to clean, validate, deduplicate, and store data.
"""

from typing import Protocol

from huginn.core.items import CollectedItem


class Pipeline(Protocol):
    """Data processing pipeline protocol.

    A pipeline processes a CollectedItem and either returns a modified/validated
    item, or None to indicate the item should be filtered out.

    Pipelines are chained together in run_pipeline_chain to process data
    through multiple stages.
    """

    def process(self, item: CollectedItem) -> CollectedItem | None:
        """Process a collected item.

        Args:
            item: The item to process.

        Returns:
            The processed item, or None to filter it out.

        Raises:
            Exception: Any exception indicates processing failure and
                stops the pipeline chain.
        """
        ...


def run_pipeline_chain(pipelines: list[Pipeline], item: CollectedItem) -> CollectedItem | None:
    """Run an item through a chain of pipelines.

    Each pipeline's process() method is called in sequence. If any pipeline
    returns None, the chain stops and None is returned. If any pipeline
    raises an exception, the exception propagates immediately.

    Args:
        pipelines: List of pipelines to run, in order.
        item: The item to process.

    Returns:
        The final processed item if all pipelines complete, or None if any
        pipeline returns None.

    Raises:
        Exception: Any exception raised by a pipeline.
    """
    current = item
    for pipeline in pipelines:
        current = pipeline.process(current)
        if current is None:
            return None
    return current


__all__ = ["Pipeline", "run_pipeline_chain"]

"""StoragePipeline: Persists items to storage backend.

This pipeline calls the storage backend's save_items method to persist data.
"""

import logging

from huginn.core.exceptions import StorageError
from huginn.core.items import CollectedItem
from huginn.core.pipelines import Pipeline

logger = logging.getLogger(__name__)


class StoragePipeline(Pipeline):
    """Pipeline for persisting items to storage.

    Calls the storage backend's save_items method to persist collected data.
    Raises StorageError if the save operation fails.
    """

    def __init__(self, backend):
        """Initialize the storage pipeline.

        Args:
            backend: Storage backend with a save_items method.
        """
        self.backend = backend

    def process(self, item: CollectedItem) -> CollectedItem | None:
        """Save item to storage backend.

        Args:
            item: The item to save.

        Returns:
            The item if save succeeds.

        Raises:
            StorageError: If save operation fails.
        """
        try:
            self.backend.save_items(item.source, item.category, [item.data])
            logger.debug("Saved item to storage: source=%s", item.source)
            return item
        except Exception as e:
            logger.error("Failed to save item to storage: source=%s, error=%s", item.source, e)
            raise StorageError(f"Failed to save item: {e}") from e

"""CleanPipeline: Validates and cleans collected data.

This pipeline performs:
1. Validation: source, category, data
2. Text cleaning: First-level string fields
3. Timestamp completion: collected_at
"""

import logging

from huginn.core.constants import Category
from huginn.core.exceptions import ValidationError
from huginn.core.items import CollectedItem
from huginn.core.pipelines import Pipeline
from huginn.core.utils.text import clean_text

logger = logging.getLogger(__name__)


class CleanPipeline(Pipeline):
    """Validates and cleans collected data items.

    Validates required fields (source, category, data), cleans first-level
    string fields, and ensures collected_at is set.
    """

    def process(self, item: CollectedItem) -> CollectedItem | None:
        """Validate and clean a collected item.

        Args:
            item: The item to validate and clean.

        Returns:
            The cleaned item.

        Raises:
            ValidationError: If validation fails.
        """
        # Validation
        self._validate_source(item.source)
        self._validate_category(item.category)
        self._validate_data(item.data)

        # Clean first-level string fields
        cleaned_data = self._clean_data_dict(item.data)

        # Set collected_at if None
        if item.collected_at is None:
            item.collected_at = _now_utc()

        # Update item with cleaned data
        item.data = cleaned_data

        return item

    def _validate_source(self, source: str) -> None:
        """Validate source field."""
        if not source:
            logger.warning("Validation failed: source is empty or None")
            raise ValidationError("source cannot be empty or None")

    def _validate_category(self, category: str) -> None:
        """Validate category is a valid Category enum value."""
        try:
            Category(category)
        except ValueError:
            logger.warning("Validation failed: invalid category '%s'", category)
            raise ValidationError(f"category '{category}' is not a valid Category value") from None

    def _validate_data(self, data: dict) -> None:
        """Validate data field."""
        if not isinstance(data, dict):
            logger.warning("Validation failed: data is not a dict (type: %s)", type(data))
            raise ValidationError("data must be a dictionary")

        if not data:
            logger.warning("Validation failed: data is empty dict")
            raise ValidationError("data cannot be empty")

    def _clean_data_dict(self, data: dict) -> dict:
        """Clean first-level string values in data dict.

        Args:
            data: The data dict to clean.

        Returns:
            A new dict with cleaned string values.
        """
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, str):
                cleaned[key] = clean_text(value)
            else:
                cleaned[key] = value
        return cleaned


def _now_utc():
    """Get current UTC datetime.

    Using datetime.now() in tests can be flaky, so this is a simple wrapper.
    """
    from datetime import UTC, datetime

    return datetime.now(UTC)

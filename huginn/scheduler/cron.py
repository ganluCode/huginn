"""Cron expression parsing for APScheduler.

This module provides functions to parse standard 5-part cron expressions
into parameters compatible with APScheduler's CronTrigger.
"""

import logging

logger = logging.getLogger(__name__)

# Standard cron expression has exactly 5 parts
# minute hour day month day_of_week
CRON_PART_COUNT = 5

# Field names for APScheduler CronTrigger
# In order: minute, hour, day, month, day_of_week
FIELD_NAMES = ["minute", "hour", "day", "month", "day_of_week"]


def parse_cron(cron_expression: str) -> dict[str, str]:
    """Parse a standard 5-part cron expression into APScheduler parameters.

    Takes a standard Unix cron expression (5 space-separated fields) and
    returns a dictionary compatible with APScheduler's CronTrigger.

    The 5 fields in order are:
    1. minute (0-59)
    2. hour (0-23)
    3. day (1-31)
    4. month (1-12 or names)
    5. day_of_week (0-7 or names, 0 and 7 are Sunday)

    Args:
        cron_expression: A standard 5-part cron expression (e.g., "*/30 * * * *").

    Returns:
        A dictionary with keys: minute, hour, day, month, day_of_week.
        Values are the parsed field expressions from the cron string.

    Raises:
        ValueError: If the cron expression is invalid (wrong number of parts,
            empty, malformed).

    Examples:
        >>> parse_cron("*/30 * * * *")
        {'minute': '*/30', 'hour': '*', 'day': '*', 'month': '*', 'day_of_week': '*'}
        >>> parse_cron("0 9 * * 1-5")
        {'minute': '0', 'hour': '9', 'day': '*', 'month': '*', 'day_of_week': '1-5'}
        >>> parse_cron("0 0 1 * *")
        {'minute': '0', 'hour': '0', 'day': '1', 'month': '*', 'day_of_week': '*'}
    """
    if not isinstance(cron_expression, str):
        raise ValueError(
            f"Invalid cron format: expected string, got {type(cron_expression).__name__}"
        )

    # Trim whitespace
    expression = cron_expression.strip()

    # Validate not empty
    if not expression:
        raise ValueError("Invalid cron format: empty expression")

    # Split by single spaces
    parts = expression.split()

    # Validate we have exactly 5 parts
    if len(parts) != CRON_PART_COUNT:
        raise ValueError(
            f"Invalid cron format: expected {CRON_PART_COUNT} parts "
            f"(minute hour day month day_of_week), got {len(parts)}: '{expression}'"
        )

    # Map parts to APScheduler field names
    result = {field: value for field, value in zip(FIELD_NAMES, parts)}

    logger.debug("Parsed cron expression '%s' to %s", cron_expression, result)

    return result

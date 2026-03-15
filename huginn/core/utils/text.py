"""Text processing utility functions."""

import hashlib
import json
import re


def clean_text(value: str | None) -> str | None:
    """Clean and normalize text content.

    Performs the following operations:
    1. Strips leading/trailing whitespace
    2. Compresses consecutive whitespace (including tabs, newlines) to single spaces
    3. Returns None for empty or whitespace-only strings

    Args:
        value: The string to clean, or any other type (returned as-is).

    Returns:
        Cleaned string, or None if input is empty/whitespace-only,
        or the original value if it's not a string.

    Examples:
        >>> clean_text('  hello  world  ')
        'hello world'
        >>> clean_text('  ')
        None
        >>> clean_text(123)
        123
        >>> clean_text('hello\\t\\tworld')
        'hello world'
    """
    # Defensive: non-str input returned as-is
    if not isinstance(value, str):
        return value

    # Strip leading/trailing whitespace
    stripped = value.strip()

    # Return None for empty strings
    if not stripped:
        return None

    # Compress consecutive whitespace (tabs, newlines, spaces) to single space
    # Using regex to match any whitespace character (\s) one or more times (+)
    cleaned = re.sub(r"\s+", " ", stripped)

    return cleaned


def content_hash(data: dict) -> str:
    """Generate a deterministic content hash from dictionary data.

    Serializes the dictionary to JSON with sorted keys and computes
    a SHA-256 hash, returning the first 16 hexadecimal characters.

    The hash is deterministic:
    - Field order doesn't matter (keys are sorted)
    - Same content always produces the same hash

    Args:
        data: Dictionary to hash.

    Returns:
        A 16-character lowercase hexadecimal string.

    Examples:
        >>> hash1 = content_hash({'b': 1, 'a': 2})
        >>> hash2 = content_hash({'a': 2, 'b': 1})
        >>> hash1 == hash2
        True
        >>> len(content_hash({}))
        16
    """
    # Serialize to JSON with sorted keys for deterministic output
    json_bytes = json.dumps(data, sort_keys=True).encode("utf-8")

    # Compute SHA-256 hash
    sha256_hash = hashlib.sha256(json_bytes).hexdigest()

    # Return first 16 characters
    return sha256_hash[:16]

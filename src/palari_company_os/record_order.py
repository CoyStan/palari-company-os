from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


_MIN_TIMESTAMP = datetime.min.replace(tzinfo=timezone.utc)


def record_time_key(record: object) -> tuple[datetime, datetime, datetime, datetime, str]:
    """Return a timezone-normalized deterministic ordering key for a record."""

    return (
        timestamp_order(_field(record, "timestamp")),
        timestamp_order(_field(record, "accepted_at")),
        timestamp_order(_field(record, "updated_at")),
        timestamp_order(_field(record, "started_at")),
        str(_field(record, "id")),
    )


def timestamp_order(value: object) -> datetime:
    """Normalize an ISO-8601 instant for comparison; malformed values sort first."""

    text = str(value or "")
    if not text:
        return _MIN_TIMESTAMP
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return _MIN_TIMESTAMP
    if parsed.utcoffset() is None:
        return _MIN_TIMESTAMP
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError:
        return _MIN_TIMESTAMP


def _field(record: object, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name, "")
    return getattr(record, name, "")

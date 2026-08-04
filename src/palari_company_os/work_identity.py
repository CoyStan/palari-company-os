"""Collision-resistant work identity with no lifecycle ordering semantics."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from uuid import UUID, uuid4


_MAX_COLLISION_RETRIES = 16


def generate_work_id(
    existing_ids: Iterable[str],
    *,
    uuid_factory: Callable[[], UUID] = uuid4,
) -> str:
    """Return a UUIDv4-backed ID whose value carries no dependency semantics."""

    existing = set(existing_ids)
    for _ in range(_MAX_COLLISION_RETRIES):
        value = uuid_factory()
        if value.version != 4:
            raise ValueError("work ID factory must return a UUIDv4 value")
        candidate = f"WORK-{value.hex.upper()}"
        if candidate not in existing:
            return candidate
    raise ValueError("could not allocate a unique opaque work ID after 16 attempts")

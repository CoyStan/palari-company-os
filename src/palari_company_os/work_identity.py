"""Collision-resistant work identity with no lifecycle ordering semantics."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from uuid import UUID, uuid4


_MAX_COLLISION_RETRIES = 16


def generate_work_id(
    existing_ids: Iterable[str],
    *,
    uuid_factory: Callable[[], UUID] = uuid4,
    _prefix: str = "WORK",
) -> str:
    """Return a UUIDv4-backed ID whose value carries no dependency semantics."""
    existing = set(existing_ids)
    for _ in range(_MAX_COLLISION_RETRIES):
        value = uuid_factory()
        if value.version != 4:
            raise ValueError("ID factory must return a UUIDv4 value")
        candidate = f"{_prefix}-{value.hex.upper()}"
        if candidate not in existing:
            return candidate
    raise ValueError("could not allocate a unique opaque ID after 16 attempts")


def generate_proposal_id(
    existing_ids: Iterable[str], *, uuid_factory: Callable[[], UUID] = uuid4
) -> str:
    """Return a UUIDv4-backed ID for an authority-free work idea."""
    return generate_work_id(existing_ids, uuid_factory=uuid_factory, _prefix="IDEA")

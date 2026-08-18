"""Collision-resistant work identity with no lifecycle ordering semantics."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from uuid import UUID, uuid4


_MAX_COLLISION_RETRIES = 16
_HEX_CHARS = frozenset("0123456789abcdefABCDEF")
_MIN_DISPLAY_HEX = 8
_MIN_RESOLVE_CHARS = 8


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


def short_opaque_id(
    full_id: str,
    existing_ids: Iterable[str],
    *,
    min_hex: int = _MIN_DISPLAY_HEX,
) -> str:
    """Return the shortest unique prefix of a stored WORK-/IDEA- hex ID."""

    parsed = _hex_opaque_id(full_id)
    if parsed is None:
        return full_id
    prefix, hex_part = parsed
    existing = [str(item) for item in existing_ids]
    if full_id not in existing:
        existing.append(full_id)
    target = full_id.upper()
    start = min(max(min_hex, 1), len(hex_part))
    for length in range(start, len(hex_part) + 1):
        candidate = f"{prefix}-{hex_part[:length]}"
        matches = [item for item in existing if item.upper().startswith(candidate)]
        if len(matches) == 1 and matches[0].upper() == target:
            return candidate
    return full_id


def resolve_opaque_id(query: str, existing_ids: Iterable[str]) -> str:
    """Return the stored ID uniquely identified by query, or query unchanged.

    Exact matches win. Unique prefixes of at least eight characters also resolve.
    Ambiguous prefixes fail closed.
    """

    query = query.strip()
    if not query:
        return query
    existing = [str(item) for item in existing_ids]
    if query in existing:
        return query
    upper = query.upper()
    exact = [item for item in existing if item.upper() == upper]
    if len(exact) == 1:
        return exact[0]
    if len(query) < _MIN_RESOLVE_CHARS:
        return query
    matches = [item for item in existing if item.upper().startswith(upper)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"ambiguous id {query}: matches {', '.join(sorted(matches))}"
        )
    return query


def replace_opaque_ids(text: str, existing_ids: Iterable[str]) -> str:
    """Replace stored WORK-/IDEA- hex IDs in text with unique short prefixes."""

    ids = sorted({str(item) for item in existing_ids}, key=len, reverse=True)
    updated = text
    for full_id in ids:
        short = short_opaque_id(full_id, ids)
        if short != full_id:
            updated = updated.replace(full_id, short)
    return updated


def _hex_opaque_id(value: str) -> tuple[str, str] | None:
    prefix, separator, rest = value.partition("-")
    if separator != "-" or prefix not in {"WORK", "IDEA"} or not rest:
        return None
    if any(char not in _HEX_CHARS for char in rest) or len(rest) < _MIN_DISPLAY_HEX:
        return None
    return prefix, rest.upper()

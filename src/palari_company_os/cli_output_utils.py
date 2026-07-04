from __future__ import annotations

import json
from typing import Any


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def comma_or_none(items: list[Any]) -> str:
    values = [str(item) for item in items if str(item)]
    return ", ".join(values) if values else "none"


def print_limited_items(
    label: str,
    items: list[Any],
    *,
    limit: int,
    indent: str = "  ",
    item_indent: str = "    ",
) -> None:
    values = [str(item) for item in items if str(item)]
    if not values:
        return
    print(f"{indent}{label}:")
    for item in values[:limit]:
        print(f"{item_indent}- {item}")
    remaining = len(values) - limit
    if remaining > 0:
        print(f"{item_indent}+ {remaining} more")

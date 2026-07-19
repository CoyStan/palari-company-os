from __future__ import annotations

import json
from typing import Any


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def yes_no(value: bool) -> str:
    return "yes" if value else "no"

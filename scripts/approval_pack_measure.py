#!/usr/bin/env python3
"""Measure interaction compression from Approval Inbox JSON on stdin."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from palari_company_os.approval_packs import approval_interaction_measurement


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        packs = payload["packs"]
        items = payload["individual_items"]
        result = approval_interaction_measurement(packs, items)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"approval-pack-measure: invalid inbox JSON: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

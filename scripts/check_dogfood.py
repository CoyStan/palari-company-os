#!/usr/bin/env python3
"""CI entrypoint for graduated dogfood enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.dogfood_check import check_dogfood_range  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="Git repository root.")
    parser.add_argument("--base", required=True, help="Exclusive base SHA.")
    parser.add_argument("--head", required=True, help="Inclusive head SHA.")
    parser.add_argument(
        "--workspace",
        default="workspace.json",
        help="Dogfood workspace path relative to the repo (or absolute).",
    )
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="PR label (repeatable). Labels agent/cursor enable the gate for humans too.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args(argv)

    result = check_dogfood_range(
        args.repo,
        base=args.base,
        head=args.head,
        workspace_path=args.workspace,
        labels=set(args.label),
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["message"])
        for item in result["denials"]:
            print(f"- {item['sha'][:12]}: {item['reason']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run explicitly named unittest modules for focused development feedback."""

from __future__ import annotations

import argparse
import re
import sys
import unittest
from pathlib import Path


MODULE_PATTERN = re.compile(r"^tests\.test_[a-z0-9_]+$")
REPO_ROOT = Path(__file__).resolve().parents[1]


def validated_modules(modules: list[str]) -> list[str]:
    if not modules:
        raise ValueError("focused verification requires at least one test module")
    invalid = [module for module in modules if not MODULE_PATTERN.fullmatch(module)]
    if invalid:
        raise ValueError(f"invalid focused test module: {invalid[0]}")
    return sorted(set(modules))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="+")
    parser.add_argument("--list", action="store_true", dest="list_only")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        modules = validated_modules(args.modules)
    except ValueError as exc:
        print(f"focused verification error: {exc}", file=sys.stderr)
        return 2

    if args.list_only:
        print("\n".join(modules))
        return 0

    sys.path.insert(0, str(REPO_ROOT))
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

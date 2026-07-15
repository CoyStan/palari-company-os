#!/usr/bin/env python3
"""Run each unittest module in an isolated process with deterministic output."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_COUNT_RE = re.compile(r"Ran (\d+) tests? in")


@dataclass(frozen=True)
class ModuleResult:
    module: str
    returncode: int
    output: str
    test_count: int
    duration: float


def _modules() -> list[str]:
    return [
        f"tests.{path.stem}"
        for path in sorted((REPO_ROOT / "tests").glob("test_*.py"))
    ]


def _run(module: str) -> ModuleResult:
    started = time.monotonic()
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-S", "-m", "unittest", module],
        cwd=REPO_ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    match = TEST_COUNT_RE.search(result.stdout)
    return ModuleResult(
        module=module,
        returncode=result.returncode,
        output=result.stdout,
        test_count=int(match.group(1)) if match else 0,
        duration=time.monotonic() - started,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help="Number of isolated module processes (default: up to 4).",
    )
    parser.add_argument("--list", action="store_true", help="List modules without running.")
    args = parser.parse_args(argv)
    modules = _modules()
    if args.list:
        print("\n".join(modules))
        return 0
    if args.workers < 1:
        parser.error("--workers must be positive")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(_run, modules))

    failures = [result for result in results if result.returncode]
    if failures:
        for result in failures:
            print(f"FAIL {result.module} ({result.duration:.3f}s)")
            print(result.output, end="" if result.output.endswith("\n") else "\n")
        print(f"Parallel unit gate failed: {len(failures)}/{len(results)} module(s).")
        return 1

    missing_counts = [result.module for result in results if result.test_count == 0]
    if missing_counts:
        print("Parallel unit gate could not account for tests in: " + ", ".join(missing_counts))
        return 1
    total = sum(result.test_count for result in results)
    slowest = sorted(results, key=lambda result: (-result.duration, result.module))[:5]
    print(f"Parallel unit gate passed: {total} tests across {len(results)} modules.")
    print(
        "Slowest modules: "
        + ", ".join(f"{item.module}={item.duration:.3f}s" for item in slowest)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

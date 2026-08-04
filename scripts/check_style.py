#!/usr/bin/env python3
from __future__ import annotations

import ast
import sys
from pathlib import Path


CHECK_SUFFIXES = {".py", ".md", ".json", ".yml", ".yaml", ".sh"}
SKIP_DIRS = {".git", ".palari-company-os", "__pycache__", ".pytest_cache", ".mypy_cache"}
SKIP_PREFIXES = {("workspaces", "palari-company-os")}


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file() or _skip(path, repo):
            continue
        if path.suffix not in CHECK_SUFFIXES and path.name not in {"README.md"}:
            continue
        failures.extend(_check_text(path, repo))
        if path.suffix == ".py":
            failures.extend(_check_python(path, repo))
        if path.suffix == ".sh":
            failures.extend(_check_shell_script(path, repo))
    if failures:
        print("Style check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("Style check passed.")
    return 0


def _skip(path: Path, repo: Path) -> bool:
    rel = path.relative_to(repo)
    return any(part in SKIP_DIRS for part in rel.parts) or any(
        rel.parts[: len(prefix)] == prefix for prefix in SKIP_PREFIXES
    )


def _check_text(path: Path, repo: Path) -> list[str]:
    rel = path.relative_to(repo)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [f"{rel}: not valid UTF-8"]
    failures: list[str] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if line.rstrip(" \t") != line:
            failures.append(f"{rel}:{index}: trailing whitespace")
    if "\x00" in text:
        failures.append(f"{rel}: contains NUL byte")
    return failures


def _check_python(path: Path, repo: Path) -> list[str]:
    rel = path.relative_to(repo)
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"{rel}:{exc.lineno}: Python syntax error: {exc.msg}"]
    return []


def _check_shell_script(path: Path, repo: Path) -> list[str]:
    rel = path.relative_to(repo)
    text = path.read_text(encoding="utf-8")
    if not text.startswith("#!"):
        return [f"{rel}: shell script missing shebang"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())

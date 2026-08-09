#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


TREE_PATH = "docs/agent/repo-tree.json"
PLAIN_NAMES = {
    "repo", "app", "code", "run", "shape", "tests", "docs", "start",
    "agents", "product", "tools", "data", "sample", "past", "live",
    "goals", "team", "work", "projects", "ideas", "tasks", "runs", "checks",
    "records", "reviews", "choices", "results", "limits", "sources", "guides",
    "rules", "outside", "apps", "plans", "queue",
    "now", "next", "later", "allowed", "ask", "never",
}


def check_repo_tree(repo: Path | str) -> dict[str, Any]:
    root = Path(repo).resolve()
    problems: list[str] = []
    try:
        tree = json.loads((root / TREE_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result([f"cannot read {TREE_PATH}: {exc}"], 0, 0)

    leaves: list[tuple[str, list[str]]] = []
    product_leaves: list[tuple[str, list[str]]] = []
    _check_part(tree, "repo", problems, leaves, "files", is_root=True)
    _check_part(tree.get("product"), "product", problems, product_leaves, "records", is_root=True)
    files = _repo_files(root, problems)
    matches: dict[str, list[str]] = {
        path: [name for name, rules in leaves if any(_matches(path, rule) for rule in rules)]
        for path in files
    }
    for path, names in matches.items():
        if not names:
            problems.append(f"file has no part: {path}")
        elif len(names) > 1:
            problems.append(f"file is in more than one part: {path} ({', '.join(names)})")
    for name, rules in leaves:
        if not any(_matches(path, rule) for path in files for rule in rules):
            problems.append(f"part has no files: {name}")
    records = _record_names(root, problems)
    _check_exact_members(records, product_leaves, "record", problems)
    return _result(problems, len(files), len(leaves), len(records), _end_count(tree.get("product")))


def _check_part(
    part: Any,
    trail: str,
    problems: list[str],
    leaves: list[tuple[str, list[str]]],
    item_key: str,
    *,
    is_root: bool = False,
) -> None:
    if not isinstance(part, dict):
        problems.append(f"part is not an object: {trail}")
        return
    name = part.get("name")
    if not isinstance(name, str) or name not in PLAIN_NAMES:
        problems.append(f"part needs one approved plain word: {trail}")
        name = str(name or "missing")
    here = name if is_root else f"{trail}/{name}"
    children = part.get("parts")
    rules = part.get(item_key)
    if item_key == "files" and children is not None and rules is not None:
        problems.append(f"part cannot hold child parts and {item_key}: {here}")
        return
    if item_key == "records" and rules is not None:
        if not isinstance(rules, list) or not all(isinstance(rule, str) for rule in rules):
            problems.append(f"part has bad {item_key}: {here}")
            return
        if rules:
            leaves.append((here, rules))
    if children is not None:
        if not isinstance(children, list) or not 3 <= len(children) <= 5:
            problems.append(f"part needs three to five child parts: {here}")
            return
        names = [child.get("name") for child in children if isinstance(child, dict)]
        if len(names) != len(set(names)):
            problems.append(f"child names overlap: {here}")
        for child in children:
            _check_part(child, here, problems, leaves, item_key)
        return
    if item_key == "records":
        return
    if not isinstance(rules, list) or not rules or not all(isinstance(rule, str) for rule in rules):
        problems.append(f"end part needs {item_key}: {here}")
        return
    leaves.append((here, rules))


def _repo_files(root: Path, problems: list[str]) -> list[str]:
    run = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if run.returncode:
        problems.append("cannot list repo files")
        return []
    return sorted(path for path in run.stdout.decode().split("\0") if path)


def _record_names(root: Path, problems: list[str]) -> list[str]:
    try:
        schema = json.loads((root / "schemas/workspace.schema.json").read_text(encoding="utf-8"))
        return sorted(
            name for name, shape in schema["properties"].items() if shape.get("type") == "array"
        )
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        problems.append(f"cannot read workspace record names: {exc}")
        return []


def _check_exact_members(
    items: list[str], leaves: list[tuple[str, list[str]]], label: str, problems: list[str]
) -> None:
    for item in items:
        names = [name for name, rules in leaves if item in rules]
        if not names:
            problems.append(f"{label} has no part: {item}")
        elif len(names) > 1:
            problems.append(f"{label} is in more than one part: {item} ({', '.join(names)})")
    for name, rules in leaves:
        for item in rules:
            if item not in items:
                problems.append(f"unknown {label} in {name}: {item}")


def _matches(path: str, rule: str) -> bool:
    return path.startswith(rule) if rule.endswith("/") else path == rule


def _end_count(part: Any) -> int:
    if not isinstance(part, dict) or not part.get("parts"):
        return 1
    return sum(_end_count(child) for child in part["parts"])


def _result(
    problems: list[str], files: int, leaves: int, records: int = 0, product_leaves: int = 0
) -> dict[str, Any]:
    return {
        "schema_version": "palari.repo_tree_check.v1",
        "ok": not problems,
        "files": files,
        "end_parts": leaves,
        "records": records,
        "product_end_parts": product_leaves,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the repo's simple product and file tree.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check_repo_tree(args.repo)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print(f"Repo tree passed: {result['files']} files, {result['records']} records.")
    else:
        print("Repo tree failed:")
        for problem in result["problems"]:
            print(f"  {problem}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

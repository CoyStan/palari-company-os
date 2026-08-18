#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    "base", "links", "views",
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
    code_parts = _check_code_parts(tree, root, problems)
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
    return _result(
        problems,
        len(files),
        len(leaves),
        len(records),
        _end_count(tree.get("product")),
        code_parts,
    )


def part_command(repo: Path | str, name: str) -> list[str]:
    root = Path(repo).resolve()
    result = check_repo_tree(root)
    if not result["ok"]:
        raise ValueError("repo tree must pass before a part check can run")
    tree = json.loads((root / TREE_PATH).read_text(encoding="utf-8"))
    part = _code_part(tree, name)
    if part is None:
        raise ValueError(f"unknown code part: {name}")
    return [
        sys.executable,
        "-S",
        str(root / "scripts" / "verification_profiles.py"),
        *part["check"],
    ]


def run_part_check(repo: Path | str, name: str) -> int:
    root = Path(repo).resolve()
    try:
        command = part_command(root, name)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Part check failed: {exc}")
        return 1
    print(f"Running {name} check: {' '.join(command[3:])}", flush=True)
    run = subprocess.run(command, cwd=root, check=False)
    if run.returncode == 0:
        print(f"Part {name} check passed.")
    return run.returncode


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


def _check_code_parts(tree: Any, root: Path, problems: list[str]) -> int:
    code = _child(_child(tree, "app"), "code")
    if not isinstance(code, dict) or not isinstance(code.get("parts"), list):
        problems.append("repo/app/code needs child parts")
        return 0
    parts = code["parts"]
    for part in parts:
        if not isinstance(part, dict):
            continue
        name = str(part.get("name") or "missing")
        files = part.get("files")
        doors = part.get("door")
        checks = part.get("check")
        if not isinstance(doors, list) or not 1 <= len(doors) <= 5 or not all(
            isinstance(door, str) for door in doors
        ):
            problems.append(f"code part needs one to five doors: {name}")
        elif isinstance(files, list):
            for door in doors:
                if not any(
                    isinstance(rule, str) and _matches(door, rule) for rule in files
                ):
                    problems.append(f"code part door is not owned: {name} ({door})")
                elif not (root / door).is_file():
                    problems.append(f"code part door is missing: {name} ({door})")
        if not isinstance(checks, list) or not checks or not all(
            isinstance(module, str) for module in checks
        ):
            problems.append(f"code part needs focused tests: {name}")
            continue
        if len(checks) != len(set(checks)):
            problems.append(f"code part repeats a focused test: {name}")
        for module in checks:
            test_path = root / (module.replace(".", "/") + ".py")
            if not module.startswith("tests.test_") or not test_path.is_file():
                problems.append(f"code part has unknown focused test: {name} ({module})")
    return len(parts)


def _code_part(tree: Any, name: str) -> dict[str, Any] | None:
    code = _child(_child(tree, "app"), "code")
    if not isinstance(code, dict) or not isinstance(code.get("parts"), list):
        return None
    found = [
        part
        for part in code["parts"]
        if isinstance(part, dict) and part.get("name") == name
    ]
    return found[0] if len(found) == 1 else None


def _child(part: Any, name: str) -> dict[str, Any] | None:
    if not isinstance(part, dict) or not isinstance(part.get("parts"), list):
        return None
    found = [
        child
        for child in part["parts"]
        if isinstance(child, dict) and child.get("name") == name
    ]
    return found[0] if len(found) == 1 else None


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
    problems: list[str],
    files: int,
    leaves: int,
    records: int = 0,
    product_leaves: int = 0,
    code_parts: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "palari.repo_tree_check.v1",
        "ok": not problems,
        "files": files,
        "end_parts": leaves,
        "records": records,
        "product_end_parts": product_leaves,
        "code_parts": code_parts,
        "problems": problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the repo's simple product and file tree.")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--part", help="Run one code part's focused tests.")
    args = parser.parse_args()
    if args.part:
        if args.json:
            parser.error("--json cannot be used with --part")
        return run_part_check(args.repo, args.part)
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

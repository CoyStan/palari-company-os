#!/usr/bin/env python3
"""Generate or check the deterministic PCAW verifier trusted-code manifest."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "pcaw.trusted_code.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "palari_company_os"
DEFAULT_MANIFEST = REPO_ROOT / "spec" / "pcaw" / "v1" / "trusted-code.json"
ENTRY_CANDIDATES = (
    "src/palari_company_os/pcaw_protocol.py",
    "src/palari_company_os/pcaw.py",
    "src/palari_company_os/proof.py",
    "src/palari_company_os/proof_protocol.py",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or verify PCAW verifier source hashes and dependency closure."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Trusted-code manifest path.",
    )
    parser.add_argument(
        "--entry",
        action="append",
        default=[],
        metavar="REPO_PATH",
        help="Verifier entry module. Repeatable; defaults to the existing manifest.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the committed manifest differs instead of writing it.",
    )
    return parser


def _repo_path(raw: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"trusted-code entry must be a safe repository path: {raw}")
    target = (REPO_ROOT / relative).resolve()
    try:
        target.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"trusted-code entry escapes the repository: {raw}") from exc
    if not target.is_file():
        raise ValueError(f"trusted-code entry does not exist: {raw}")
    if target.suffix != ".py":
        raise ValueError(f"trusted-code entry is not Python: {raw}")
    return target


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _manifest_entries(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read trusted-code manifest: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"trusted-code manifest schema_version must be {SCHEMA_VERSION}")
    entries = payload.get("entrypoints")
    if not isinstance(entries, list) or not all(isinstance(item, str) for item in entries):
        raise ValueError("trusted-code manifest entrypoints must be an array of paths")
    return entries


def _entry_paths(args: argparse.Namespace, manifest_path: Path) -> list[Path]:
    if args.entry:
        raw_entries = list(args.entry)
    elif manifest_path.exists():
        raw_entries = _manifest_entries(manifest_path)
    else:
        raw_entries = [path for path in ENTRY_CANDIDATES if (REPO_ROOT / path).is_file()]
    if not raw_entries:
        raise ValueError(
            "no PCAW verifier entry module found; pass --entry after the verifier module lands"
        )
    return sorted({_repo_path(raw) for raw in raw_entries}, key=_relative)


def _module_name(path: Path) -> str:
    relative = path.resolve().relative_to(PACKAGE_ROOT)
    if relative.name == "__init__.py":
        parts = relative.parent.parts
    else:
        parts = (*relative.parent.parts, relative.stem)
    return ".".join(("palari_company_os", *parts))


def _local_module_path(module: str) -> Path | None:
    prefix = "palari_company_os"
    if module == prefix:
        candidate = PACKAGE_ROOT / "__init__.py"
        return candidate if candidate.is_file() else None
    if not module.startswith(prefix + "."):
        return None
    parts = module.split(".")[1:]
    file_candidate = PACKAGE_ROOT.joinpath(*parts).with_suffix(".py")
    if file_candidate.is_file():
        return file_candidate
    package_candidate = PACKAGE_ROOT.joinpath(*parts, "__init__.py")
    return package_candidate if package_candidate.is_file() else None


def _resolved_import(current_module: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package_parts = current_module.split(".")[:-1]
    keep = len(package_parts) - node.level + 1
    base = package_parts[: max(keep, 0)]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _imports(path: Path) -> tuple[set[str], set[str], set[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=_relative(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise ValueError(f"cannot parse {_relative(path)}: {exc}") from exc
    current_module = _module_name(path)
    local: set[str] = set()
    stdlib: set[str] = set()
    external: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _resolved_import(current_module, node)
            if base:
                names.append(base)
            if node.level and base:
                for alias in node.names:
                    names.append(f"{base}.{alias.name}")
        for name in names:
            local_path = _local_module_path(name)
            if local_path is not None:
                local.add(_relative(local_path))
                continue
            top_level = name.split(".", 1)[0]
            if top_level in sys.stdlib_module_names:
                stdlib.add(top_level)
            elif top_level and top_level != "palari_company_os":
                external.add(top_level)
    local.discard(_relative(path))
    return local, stdlib, external


def _build_manifest(entries: list[Path]) -> dict[str, Any]:
    pending = list(entries)
    seen: set[Path] = set()
    records: list[dict[str, Any]] = []
    external_dependencies: set[str] = set()
    while pending:
        path = pending.pop(0).resolve()
        if path in seen:
            continue
        seen.add(path)
        raw = path.read_bytes()
        local, stdlib, external = _imports(path)
        external_dependencies.update(external)
        records.append(
            {
                "path": _relative(path),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "source_lines": len(raw.decode("utf-8").splitlines()),
                "direct_local_dependencies": sorted(local),
                "direct_stdlib_dependencies": sorted(stdlib),
                "direct_external_dependencies": sorted(external),
            }
        )
        for relative in sorted(local):
            dependency = (REPO_ROOT / relative).resolve()
            if dependency not in seen:
                pending.append(dependency)
    records.sort(key=lambda item: item["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "entrypoints": sorted(_relative(path) for path in entries),
        "files": records,
        "file_count": len(records),
        "total_source_lines": sum(int(item["source_lines"]) for item in records),
        "runtime_dependencies": sorted(external_dependencies),
    }


def _encoded(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest_path = args.manifest.expanduser().resolve()
    try:
        entries = _entry_paths(args, manifest_path)
        payload = _build_manifest(entries)
    except ValueError as exc:
        print(f"PCAW trusted-code error: {exc}", file=sys.stderr)
        return 2
    if payload["runtime_dependencies"]:
        print(
            "PCAW trusted-code error: non-standard runtime dependencies: "
            + ", ".join(payload["runtime_dependencies"]),
            file=sys.stderr,
        )
        return 1
    expected = _encoded(payload)
    if args.check:
        try:
            actual = manifest_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"PCAW trusted-code check failed: {exc}", file=sys.stderr)
            return 1
        if actual != expected:
            print(
                "PCAW trusted-code check failed: run scripts/update_pcaw_tcb.py",
                file=sys.stderr,
            )
            return 1
        print(
            f"PCAW trusted-code manifest current: {payload['file_count']} files, "
            f"{payload['total_source_lines']} source lines, no runtime dependencies."
        )
        return 0
    _write_atomic(manifest_path, expected)
    print(
        f"Updated {_relative(manifest_path)}: {payload['file_count']} files, "
        f"{payload['total_source_lines']} source lines, no runtime dependencies."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

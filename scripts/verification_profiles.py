#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unittest
from pathlib import Path, PurePosixPath


MODULE_PATTERN = re.compile(r"^tests\.test_[a-z0-9_]+$")
REPO_ROOT = Path(__file__).resolve().parents[1]

SOURCE_TESTS = {
    "agent_advance.py": ("tests.test_agent_advance",),
    "agent_file_changes.py": (
        "tests.test_filesystem_security",
        "tests.test_path_policy",
        "tests.test_agent_packets",
    ),
    "agent_checks.py": ("tests.test_agent_packets",),
    "agent_doctor.py": ("tests.test_agent_packets",),
    "agent_finish.py": ("tests.test_agent_packets",),
    "agent_handoff.py": ("tests.test_agent_packets",),
    "agent_loop.py": ("tests.test_agent_packets",),
    "agent_next.py": ("tests.test_agent_packets",),
    "agent_packets.py": ("tests.test_agent_packets",),
    "agent_runtime.py": ("tests.test_agent_packets",),
    "authoring.py": (
        "tests.test_governance_completion",
        "tests.test_transition_checks",
        "tests.test_workspace_read_models",
    ),
    "evidence_manifest.py": (
        "tests.test_filesystem_security",
        "tests.test_governance_completion",
        "tests.test_validation",
    ),
    "claude_hooks.py": ("tests.test_claude_hooks", "tests.test_filesystem_security"),
    "git_hooks.py": ("tests.test_git_hooks", "tests.test_filesystem_security"),
    "governance_binding.py": (
        "tests.test_governance_completion",
        "tests.test_transition_checks",
        "tests.test_validation",
        "tests.test_workspace_read_models",
    ),
    "governance_case.py": (
        "tests.test_governance_kernel",
        "tests.test_governance_explorer",
    ),
    "governance_kernel.py": (
        "tests.test_governance_kernel",
        "tests.test_governance_explorer",
    ),
    "governance_journal.py": (
        "tests.test_governance_journal",
        "tests.test_governance_journal_crash",
    ),
    "pcaw_canonical.py": ("tests.test_canonical_json",),
    "pcaw_export.py": ("tests.test_pcaw_protocol",),
    "pcaw_protocol.py": ("tests.test_pcaw_protocol",),
    "pcaw_subjects.py": ("tests.test_pcaw_protocol", "tests.test_filesystem_security"),
    "pcaw_workspace.py": (
        "tests.test_pcaw_protocol",
        "tests.test_validation",
        "tests.test_transition_checks",
    ),
    "integrations.py": ("tests.test_integrations",),
    "models.py": ("tests.test_validation", "tests.test_workspace_read_models"),
    "mcp_server.py": ("tests.test_mcp_server", "tests.test_agent_packets"),
    "path_policy.py": ("tests.test_path_policy", "tests.test_validation"),
    "read_models.py": ("tests.test_workspace_read_models", "tests.test_agent_packets"),
    "review_guides.py": ("tests.test_review_guides", "tests.test_agent_packets"),
    "scope.py": ("tests.test_path_policy", "tests.test_workspace_read_models"),
    "store.py": (
        "tests.test_store_journal_integration",
        "tests.test_validation",
    ),
    "mutation_context.py": ("tests.test_store_journal_integration",),
    "transition_checks.py": (
        "tests.test_transition_checks",
        "tests.test_governance_completion",
    ),
    "validation.py": ("tests.test_validation", "tests.test_transition_checks"),
    "verification_attestations.py": ("tests.test_agent_advance",),
    "workspace.py": ("tests.test_validation", "tests.test_workspace_read_models"),
}


def affected_test_modules(paths: list[str]) -> list[str] | None:
    """Map changed paths to tests, returning None for a fail-safe full-suite fallback."""

    selected: set[str] = set()
    for raw_path in paths:
        normalized = raw_path.replace("\\", "/").strip()
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            return None
        if len(path.parts) == 2 and path.parts[0] == "tests":
            filename = path.name
            if filename.startswith("test_") and filename.endswith(".py"):
                selected.add(f"tests.{filename[:-3]}")
                continue
        if (path.parts and path.parts[0] == "docs") or path.name in {
            "AGENTS.md",
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
        }:
            selected.add("tests.test_docs")
            continue
        if path.parts[:2] == ("src", "palari_company_os"):
            modules = SOURCE_TESTS.get(path.name)
            if modules is None:
                return None
            selected.update(modules)
            continue
        if path.parts and path.parts[0] == "scripts":
            selected.update(
                {
                    "tests.test_cli_smoke",
                    "tests.test_packaging",
                    "tests.test_verification_profiles",
                }
            )
            continue
        if path.parts and path.parts[0] in {"examples", "workspaces", "schemas"}:
            selected.update(
                {
                    "tests.test_packaging",
                    "tests.test_validation",
                    "tests.test_workspace_read_models",
                }
            )
            continue
        if path.name in {"pyproject.toml", "MANIFEST.in"}:
            selected.update({"tests.test_packaging", "tests.test_public_surface"})
            continue
        return None
    return sorted(selected)


def git_changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    )
    paths: list[str] = []
    entries = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        paths.append(path)
        if any(code in {"R", "C"} for code in status) and index < len(entries):
            paths.append(entries[index])
            index += 1
    return paths


def _validated_modules(modules: list[str]) -> list[str]:
    if not modules:
        raise ValueError("focused verification requires at least one test module")
    invalid = [module for module in modules if not MODULE_PATTERN.fullmatch(module)]
    if invalid:
        raise ValueError(f"invalid focused test module: {invalid[0]}")
    return sorted(set(modules))


def _run_modules(modules: list[str] | None) -> int:
    if modules is None:
        print("Affected-area mapping is incomplete; running the full unit suite.")
        suite = unittest.defaultTestLoader.discover("tests")
    elif not modules:
        print("No affected test modules selected.")
        return 0
    else:
        print("Selected test modules: " + ", ".join(modules))
        suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic Palari verification profiles.")
    subparsers = parser.add_subparsers(dest="profile", required=True)

    focused = subparsers.add_parser("focused", help="run explicitly named test modules")
    focused.add_argument("modules", nargs="+")
    focused.add_argument("--list", action="store_true", dest="list_only")

    affected = subparsers.add_parser("affected", help="map changed paths to focused tests")
    affected.add_argument("paths", nargs="*")
    affected.add_argument("--git-diff", action="store_true")
    affected.add_argument("--list", action="store_true", dest="list_only")
    return parser


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(REPO_ROOT))
    args = _parser().parse_args(argv)
    try:
        if args.profile == "focused":
            modules: list[str] | None = _validated_modules(args.modules)
        else:
            paths = list(args.paths)
            if args.git_diff:
                paths.extend(git_changed_paths())
            if not paths:
                raise ValueError("affected verification requires paths or --git-diff")
            modules = affected_test_modules(sorted(set(paths)))
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"verification profile error: {exc}", file=sys.stderr)
        return 2

    if args.list_only:
        print("ALL_TESTS" if modules is None else "\n".join(modules))
        return 0
    return _run_modules(modules)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOC_SCHEMA_VERSION = "palari.repo_docs.v1"

CANONICAL_AGENT_DOCS = [
    "docs/agent/repo-map.md",
    "docs/agent/contracts-and-invariants.md",
    "docs/agent/common-workflows.md",
    "docs/agent/verification.md",
    "docs/agent/documentation-freshness.md",
]

ROOT_ENTRYPOINTS = ["AGENTS.md", "CLAUDE.md"]

MAJOR_COMMAND_GROUPS = [
    "workspace",
    "mcp",
    "queue",
    "state",
    "data",
    "validate",
    "detail",
    "scope",
    "agent",
    "docs",
    "playbooks",
    "gate",
    "integrations",
    "integration",
    "review",
    "decision",
    "lifecycle",
    "desktop-prototype",
]

MAJOR_SCHEMA_COLLECTIONS = [
    "goals",
    "humans",
    "palaris",
    "sources",
    "workbenches",
    "playbook_sources",
    "integrations",
    "integration_plans",
    "integration_outbox",
    "decisions",
    "work_items",
    "attempts",
    "evidence_runs",
    "review_verdicts",
    "human_decisions",
    "receipts",
    "outcomes",
]

STALE_ORCHESTRATOR_TERMS = [
    "Palari Orchestrator",
    "old Palari Orchestrator",
    "ADP",
]

ALLOW_STALE_TERM_PATHS = {
    "docs/product/agent-ready-repo-documentation.md",
    "docs/archive/research/gpt-5-5-pro-agent-packet-critique-2026-06-21.md",
}


@dataclass(frozen=True)
class DocTemplate:
    path: str
    summary: str
    content: str


def build_docs_map(repo_path: Path | str = ".") -> dict[str, Any]:
    repo = _repo_root(repo_path)
    state = documentation_state(repo)
    return {
        "schema_version": DOC_SCHEMA_VERSION,
        "kind": "docs-map",
        "repo": str(repo),
        "documentation_state": state,
        "root_entrypoints": _surface_items(repo, ROOT_ENTRYPOINTS),
        "canonical_agent_docs": _surface_items(repo, CANONICAL_AGENT_DOCS),
        "product_docs": _product_docs(repo),
        "major_command_groups": MAJOR_COMMAND_GROUPS,
        "major_schema_collections": MAJOR_SCHEMA_COLLECTIONS,
        "would_mutate": False,
    }


def check_docs(repo_path: Path | str = ".") -> dict[str, Any]:
    repo = _repo_root(repo_path)
    checks: list[dict[str, Any]] = []
    state = documentation_state(repo)

    checks.append(_docs_state_check(state))
    checks.extend(_entrypoint_checks(repo))
    checks.extend(_canonical_doc_checks(repo))
    checks.extend(_local_link_checks(repo))
    checks.extend(_command_reference_checks(repo))
    checks.extend(_schema_doc_checks(repo))
    checks.extend(_readme_link_checks(repo))
    checks.extend(_stale_term_checks(repo))

    failures = [check for check in checks if check["status"] == "fail"]
    warnings = [check for check in checks if check["status"] == "warn"]
    status = "fail" if failures else "warn" if warnings else "pass"
    return {
        "schema_version": DOC_SCHEMA_VERSION,
        "kind": "docs-check",
        "repo": str(repo),
        "status": status,
        "ok": not failures,
        "summary": {
            "checks": len(checks),
            "failures": len(failures),
            "warnings": len(warnings),
        },
        "documentation_state": state,
        "checks": checks,
        "would_mutate": False,
        "next_action": "Fix failed checks before relying on docs as repo truth."
        if failures
        else "Review warnings when they matter; no blocking documentation failure.",
    }


def init_docs(
    repo_path: Path | str = ".",
    *,
    write: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    repo = _repo_root(repo_path)
    templates = starter_templates(repo)
    files: list[dict[str, Any]] = []
    created: list[str] = []
    overwritten: list[str] = []
    skipped: list[str] = []

    for template in templates:
        target = repo / template.path
        exists = target.exists()
        action = "create"
        if exists and not overwrite:
            action = "skip-existing"
            skipped.append(template.path)
        elif exists and overwrite:
            action = "overwrite"
        if write and action != "skip-existing":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(template.content, encoding="utf-8")
            if action == "overwrite":
                overwritten.append(template.path)
            else:
                created.append(template.path)
        files.append(
            {
                "path": template.path,
                "exists": exists,
                "action": action,
                "summary": template.summary,
            }
        )

    return {
        "schema_version": DOC_SCHEMA_VERSION,
        "kind": "docs-init",
        "repo": str(repo),
        "mode": "write" if write else "dry-run",
        "would_mutate": bool(write),
        "overwrite": bool(overwrite),
        "documentation_state_before": documentation_state(repo),
        "repo_inspection": inspect_repo(repo),
        "files": files,
        "created": created,
        "overwritten": overwritten,
        "skipped_existing": skipped,
        "next_action": "Run palari docs check --json."
        if write
        else "Review proposed files, then rerun with --write to create missing docs.",
    }


def documentation_state(repo_path: Path | str = ".") -> dict[str, Any]:
    repo = _repo_root(repo_path)
    agents_exists = (repo / "AGENTS.md").exists()
    docs_agent_exists = (repo / "docs" / "agent").is_dir()
    existing_docs = [path for path in CANONICAL_AGENT_DOCS if (repo / path).exists()]
    missing_docs = [path for path in CANONICAL_AGENT_DOCS if not (repo / path).exists()]

    if agents_exists and not missing_docs:
        status = "ready"
        message = "Agent-ready repo documentation is present."
        impact = "Agents can use committed repo truth before reading implementation files."
        command = "palari docs check --json"
    elif not agents_exists and not docs_agent_exists:
        status = "missing"
        message = "No agent-ready repo documentation found."
        impact = "Agents can still inspect the repo, but orientation may require more code reading."
        command = "palari docs init"
    else:
        status = "partial"
        message = "Agent-ready repo documentation is incomplete."
        impact = "Agents should use existing docs, but may need to inspect code for missing areas."
        command = "palari docs init --dry-run"

    return {
        "status": status,
        "message": message,
        "impact": impact,
        "recommended_next_command": command,
        "root_agents_md": agents_exists,
        "docs_agent_dir": docs_agent_exists,
        "canonical_docs_present": existing_docs,
        "canonical_docs_missing": missing_docs,
    }


def recommended_docs_for_work(work_detail: dict[str, Any], repo_path: Path | str = ".") -> list[dict[str, str]]:
    repo = _repo_root(repo_path)
    available = {path for path in CANONICAL_AGENT_DOCS if (repo / path).exists()}
    recommendations: list[dict[str, str]] = []

    def add(path: str, why: str) -> None:
        if path not in available:
            return
        if any(item["path"] == path for item in recommendations):
            return
        recommendations.append({"path": path, "why": why})

    add("docs/agent/repo-map.md", "Use this to find the right implementation, test, and docs files.")
    add(
        "docs/agent/contracts-and-invariants.md",
        "Use this to preserve Palari safety and trust semantics while editing.",
    )

    work = work_detail.get("work_item", {})
    scope_text = " ".join(
        str(value)
        for value in [
            work.get("title", ""),
            work.get("scope", ""),
            work.get("acceptance_target", ""),
            " ".join(work.get("allowed_actions", []) or []),
            " ".join(work.get("output_targets", []) or []),
            " ".join(work.get("allowed_resources", []) or []),
        ]
    ).lower()
    if any(term in scope_text for term in ("command", "cli", "schema", "validation", "receipt", "integration", "agent")):
        add("docs/agent/common-workflows.md", "This work matches a recurring Palari implementation workflow.")
    if work.get("verification_expectations") or any(term in scope_text for term in ("test", "verify", "smoke")):
        add("docs/agent/verification.md", "Use this to choose focused and full verification checks.")
    if any(term in scope_text for term in ("docs", "readme", "command-reference", "schema-and-validation")):
        add(
            "docs/agent/documentation-freshness.md",
            "This work may change public behavior or documentation surfaces.",
        )
    return recommendations


def starter_templates(repo_path: Path | str = ".") -> list[DocTemplate]:
    repo = _repo_root(repo_path)
    inspection = inspect_repo(repo)
    package_dirs = ", ".join(inspection["package_dirs"]) or "not detected"
    test_dirs = ", ".join(inspection["test_dirs"]) or "not detected"
    verification = "\n".join(f"- `{command}`" for command in _verification_commands(repo))
    return [
        DocTemplate(
            "AGENTS.md",
            "Root agent entrypoint with setup, verification, and canonical doc links.",
            f"""# Agent Instructions

This repository uses agent-ready documentation. Start with this file, then read
only the deeper docs that match the task.

## First Commands

{verification}

## Repo Orientation

- Package directories: {package_dirs}
- Test directories: {test_dirs}
- Canonical agent docs live in `docs/agent/`.

## Canonical Docs

- `docs/agent/repo-map.md`
- `docs/agent/contracts-and-invariants.md`
- `docs/agent/common-workflows.md`
- `docs/agent/verification.md`
- `docs/agent/documentation-freshness.md`

Keep this file compact. Put detailed repo knowledge in `docs/agent/`.
""",
        ),
        DocTemplate(
            "docs/agent/repo-map.md",
            "Compact map of repo layout and ownership.",
            f"""# Repo Map

This is a generated starter map. Review it before treating it as repo truth.

## Detected Structure

- Package directories: {package_dirs}
- Test directories: {test_dirs}
- Documentation directories: {', '.join(inspection['doc_dirs']) or 'not detected'}
- Script directories: {', '.join(inspection['script_dirs']) or 'not detected'}

## How To Use

Start here when you need to find the files for a task. Update this map when the
repo structure changes in a way future agents need to know.
""",
        ),
        DocTemplate(
            "docs/agent/contracts-and-invariants.md",
            "Safety and product invariants agents must preserve.",
            """# Contracts And Invariants

Review this file before changing behavior that affects trust, authority, data,
or external actions.

- Keep workspace data inspectable and portable.
- Do not store raw secrets in repo data.
- Keep external actions explicit, bounded, and reviewable.
- Keep receipts human-facing: what was used, created, changed, skipped, and undoable.
- Keep tests and docs aligned with public behavior.
- Do not replace human approval with agent inference.

Update this file when a new invariant becomes important enough for future
agents to preserve.
""",
        ),
        DocTemplate(
            "docs/agent/common-workflows.md",
            "Short recipes for recurring agent work.",
            """# Common Workflows

Use these as starting points, not ceremony.

## Add Or Change A CLI Command

1. Update parser, dispatch, output, and docs.
2. Add focused tests for text and JSON output.
3. Run the normal verification stack.

## Change Data Semantics

1. Update model/validation code.
2. Update examples or fixtures if behavior changes.
3. Update relevant docs and tests.

## Change Agent Behavior

1. Keep packet output compact and deterministic.
2. Preserve explicit blockers and next safe commands.
3. Add regression coverage for failure modes.
""",
        ),
        DocTemplate(
            "docs/agent/verification.md",
            "Verification commands and expectations.",
            f"""# Verification

Use focused tests while editing, then run the normal verification stack before
claiming the work is done.

## Normal Verification

{verification}

Report skipped checks honestly with the reason.
""",
        ),
        DocTemplate(
            "docs/agent/documentation-freshness.md",
            "Rules for deciding when docs need updates.",
            """# Documentation Freshness

Update docs when work changes public behavior that future humans or agents rely
on.

- CLI changes update command reference or agent instructions.
- Schema/model changes update schema and core object docs.
- Agent behavior changes update the agent contract.
- Source, receipt, evidence, review, or human decision changes update product docs.
- Integration or external-action changes update integration docs.
- Verification changes update verification docs.

Tiny internal refactors do not need documentation churn unless they change where
future agents should look.
""",
        ),
    ]


def inspect_repo(repo_path: Path | str = ".") -> dict[str, Any]:
    repo = _repo_root(repo_path)
    return {
        "package_dirs": _existing_dirs(repo, ["src", "app", "apps", "packages", "lib"]),
        "test_dirs": _existing_dirs(repo, ["tests", "test", "spec"]),
        "doc_dirs": _existing_dirs(repo, ["docs", "documentation"]),
        "script_dirs": _existing_dirs(repo, ["scripts", "bin"]),
        "package_files": _existing_files(
            repo,
            ["pyproject.toml", "package.json", "Cargo.toml", "go.mod", "Gemfile"],
        ),
        "workspace_files": _existing_files(repo, ["workspace.json", "palari.json"]),
    }


def _repo_root(path: Path | str = ".") -> Path:
    start = Path(path).expanduser().resolve()
    current = start if start.is_dir() else start.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return current


def _surface_items(repo: Path, paths: list[str]) -> list[dict[str, Any]]:
    return [{"path": path, "exists": (repo / path).exists()} for path in paths]


def _product_docs(repo: Path) -> list[dict[str, Any]]:
    docs_dir = repo / "docs" / "product"
    if not docs_dir.exists():
        return []
    return [
        {"path": _relative(repo, path), "exists": True}
        for path in sorted(docs_dir.glob("*.md"))
    ]


def _docs_state_check(state: dict[str, Any]) -> dict[str, Any]:
    status = "pass" if state["status"] == "ready" else "warn"
    return _check(
        "DOCS_STATE",
        status,
        state["message"],
        path="AGENTS.md",
    )


def _entrypoint_checks(repo: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    agents = repo / "AGENTS.md"
    if not agents.exists():
        return [_check("AGENTS_MD_EXISTS", "warn", "AGENTS.md is missing.", path="AGENTS.md")]
    text = _read(agents)
    missing_links = [path for path in CANONICAL_AGENT_DOCS if path not in text]
    checks.append(
        _check(
            "AGENTS_MD_LINKS_AGENT_DOCS",
            "warn" if missing_links else "pass",
            "AGENTS.md links to canonical agent docs."
            if not missing_links
            else "AGENTS.md does not mention: " + ", ".join(missing_links),
            path="AGENTS.md",
        )
    )
    return checks


def _canonical_doc_checks(repo: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for path in CANONICAL_AGENT_DOCS:
        exists = (repo / path).exists()
        checks.append(
            _check(
                f"DOC_EXISTS_{_code(path)}",
                "pass" if exists else "warn",
                f"{path} exists." if exists else f"{path} is missing.",
                path=path,
            )
        )
    return checks


def _local_link_checks(repo: Path) -> list[dict[str, Any]]:
    broken: list[str] = []
    for md_file in _markdown_files(repo):
        text = _read(md_file)
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = link.split("#", 1)[0]
            if not target or _is_external_link(target):
                continue
            target_path = (md_file.parent / target).resolve()
            try:
                target_path.relative_to(repo)
            except ValueError:
                continue
            if not target_path.exists():
                broken.append(f"{_relative(repo, md_file)} -> {target}")
    return [
        _check(
            "LOCAL_DOC_LINKS_EXIST",
            "fail" if broken else "pass",
            "All local markdown links resolve."
            if not broken
            else "Broken local markdown links: " + "; ".join(broken[:10]),
        )
    ]


def _command_reference_checks(repo: Path) -> list[dict[str, Any]]:
    path = repo / "docs" / "product" / "command-reference.md"
    if not path.exists():
        return [
            _check(
                "COMMAND_REFERENCE_EXISTS",
                "warn",
                "docs/product/command-reference.md is missing.",
                path="docs/product/command-reference.md",
            )
        ]
    text = _read(path).lower()
    missing = [
        command
        for command in MAJOR_COMMAND_GROUPS
        if not re.search(rf"\b{re.escape(command.lower())}\b", text)
    ]
    return [
        _check(
            "COMMAND_REFERENCE_COVERS_MAJOR_GROUPS",
            "warn" if missing else "pass",
            "Command reference mentions major command groups."
            if not missing
            else "Command reference may be missing: " + ", ".join(missing),
            path="docs/product/command-reference.md",
        )
    ]


def _schema_doc_checks(repo: Path) -> list[dict[str, Any]]:
    paths = [
        repo / "docs" / "product" / "schema-and-validation.md",
        repo / "docs" / "product" / "core-objects.md",
    ]
    text = "\n".join(_read(path) for path in paths if path.exists()).lower()
    aliases = {
        "playbook_sources": ["playbook_sources", "playbook source", "playbook sources"],
        "integration_plans": ["integration_plans", "integration plan", "integration plans"],
        "integration_outbox": ["integration_outbox", "integration outbox"],
        "work_items": ["work_items", "work item", "work items"],
        "evidence_runs": ["evidence_runs", "evidence run", "evidence runs"],
        "review_verdicts": ["review_verdicts", "review verdict", "review verdicts"],
        "human_decisions": ["human_decisions", "human decision", "human decisions"],
    }
    missing = []
    for collection in MAJOR_SCHEMA_COLLECTIONS:
        terms = aliases.get(collection, [collection.lower()])
        if not any(term in text for term in terms):
            missing.append(collection)
    return [
        _check(
            "SCHEMA_DOCS_MENTION_MAJOR_COLLECTIONS",
            "warn" if missing else "pass",
            "Schema/core-object docs mention major collections."
            if not missing
            else "Schema/core-object docs may be missing: " + ", ".join(missing),
            path="docs/product/schema-and-validation.md",
        )
    ]


def _readme_link_checks(repo: Path) -> list[dict[str, Any]]:
    path = repo / "README.md"
    if not path.exists():
        return [_check("README_EXISTS", "warn", "README.md is missing.", path="README.md")]
    text = _read(path)
    required = ["docs/product/quickstart.md", "docs/product/command-reference.md"]
    missing = [item for item in required if item not in text]
    return [
        _check(
            "README_LINKS_CORE_DOCS",
            "warn" if missing else "pass",
            "README links to quickstart and command reference."
            if not missing
            else "README is missing links: " + ", ".join(missing),
            path="README.md",
        )
    ]


def _stale_term_checks(repo: Path) -> list[dict[str, Any]]:
    hits: list[str] = []
    for md_file in _markdown_files(repo):
        rel = _relative(repo, md_file)
        if rel in ALLOW_STALE_TERM_PATHS:
            continue
        text = _read(md_file)
        for term in STALE_ORCHESTRATOR_TERMS:
            if term in text:
                hits.append(f"{rel}: {term}")
    return [
        _check(
            "NO_STALE_ORCHESTRATOR_TERMS",
            "warn" if hits else "pass",
            "No stale old-orchestrator terminology found in active docs."
            if not hits
            else "Possible stale terminology: " + "; ".join(hits[:10]),
        )
    ]


def _markdown_files(repo: Path) -> list[Path]:
    ignored = {".git", "build", "dist", "__pycache__", ".pytest_cache"}
    files: list[Path] = []
    for path in repo.rglob("*.md"):
        if any(part in ignored for part in path.relative_to(repo).parts):
            continue
        files.append(path)
    return sorted(files)


def _verification_commands(repo: Path) -> list[str]:
    commands: list[str] = []
    if (repo / "scripts" / "verify.sh").exists():
        commands.append("./scripts/verify.sh")
    if (repo / "tests").exists():
        commands.append("python3 -m unittest discover -s tests")
    if (repo / "scripts" / "install_smoke.sh").exists():
        commands.append("./scripts/install_smoke.sh")
    return commands or ["Run the repo's normal tests before claiming done."]


def _existing_dirs(repo: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (repo / path).is_dir()]


def _existing_files(repo: Path, paths: list[str]) -> list[str]:
    return [path for path in paths if (repo / path).is_file()]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _check(code: str, status: str, message: str, *, path: str = "") -> dict[str, Any]:
    payload = {"code": code, "status": status, "message": message}
    if path:
        payload["path"] = path
    return payload


def _relative(repo: Path, path: Path) -> str:
    return str(path.relative_to(repo))


def _code(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_").upper()


def _is_external_link(link: str) -> bool:
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link)) or link.startswith("#")

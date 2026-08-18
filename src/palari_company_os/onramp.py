"""Two-minute setup for existing repositories.

``palari init`` creates a small but complete starter workspace (one human,
one builder agent, one distinct review-only agent, one goal, one project, and
one repository source) in an existing repository. ``palari do`` and
``palari work add`` create an agent-startable task from a title and write
paths, inferring create vs modify when a bare path is given. Together with
``palari claude install`` they take a repo from "never heard of Palari" to an
enforced write boundary in three commands.

Everything here writes through the validated store. In Git repositories the
explicit initialization command also creates one hook-free, path-limited local
commit as the trusted starting point; unrelated repository changes are not
included.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from shlex import quote
from typing import Any

from .authority_plan import build_authority_plan
from .command_surface import palari_workspace_command
from .governance_journal import MutationMetadata, utc_timestamp
from .path_policy import validate_workspace_path
from .store import WorkspaceStore, load_store, workspace_file_path, write_store
from .validation import ALL_COLLECTION_KEYS
from .work_identity import generate_proposal_id, generate_work_id
from .workspace import CURRENT_SCHEMA_VERSION, WorkspaceError

HUMAN_ID = "HUMAN-FOUNDER"
REVIEWER_ID = "PALARI-REVIEWER"
GOAL_ID = "GOAL-0001"
WORKBENCH_ID = "WORKBENCH-MAIN"
SOURCE_ID = "SOURCE-REPO"

AGENT_DOC_TEMPLATES = {
    "AGENTS.md": """# Palari Agent Rules

Before changing files, start one bounded task:

```bash
palari agent start --next --as PALARI-ID --json
```

Continue only when the returned task brief (`packet`) is ready. Read and write
only the allowed paths, use only its selected sources, and stop for independent
review, human approval, or an external action. After committing the bounded
change, run:

```bash
palari agent advance WORK-ID --as PALARI-ID --json
```

`advance` records deterministic check results and never creates an independent
review or human approval. When it stops for review, start the emitted
review-mode packet for the review-only agent ID returned by `palari init`
(`REVIEWER-ID` in generic examples) and record only that agent's advisory
verdict. The reviewer can then run `palari agent status WORK-ID --as
REVIEWER-ID --mode review --json`.

For one eligible reversible local task, that status JSON contains one exact
presentation-bound command in `human_action_commands[].command`. A qualified
human runs that emitted command once. Agents may quote the exact command but
must never run it, reconstruct a bare approval command, or run any
`human-decision` command. Use `palari agent status WORK-ID --as PALARI-ID
--json` for the next safe action. Repository orientation lives under
`docs/agent/`.
""",
    "docs/agent/repo-map.md": """# Repository Map

`workspace.json` stores Palari's current local state. `.palari/` contains
tamper-evident history and local runtime files. Record repository-specific source,
test, and documentation ownership here before asking an agent to work broadly.
""",
    "docs/agent/contracts-and-invariants.md": """# Rules And Invariants

- Work only inside the read and write limits in the active task brief (`packet`).
- Do not invent sources, permissions, run records (`receipts`), check results
  (`evidence`), reviews, or human approvals.
- Keep the builder, independent reviewer, and final human approver distinct.
- Review-only agents may inspect and record advisory verdicts but may not
  execute task outputs or human approval.
- Commit the bounded result before running `palari agent advance`.
- Stop for independent review, human approval, and external actions.
- Preserve `workspace.json` as current state and `.palari/` as history and
  local runtime state.
""",
    "docs/agent/common-workflows.md": """# Common Workflows

Start ordinary work with `palari agent start --next --as PALARI-ID --json`.
Follow the task brief (`packet`), commit only the bounded change, and run
`palari agent advance WORK-ID --as PALARI-ID --json`. If blocked, run `palari
agent status` and report its exact next safe action. For a review handoff,
start the exact review packet emitted for the review-only agent ID returned by
`palari init` (`REVIEWER-ID` in generic examples), record its advisory verdict,
and let that reviewer present `agent status --mode review`. For one eligible
reversible local task, a qualified human runs the exact presentation-bound
command in the status projection's `human_action_commands[].command`; agents must not run
or manually reconstruct approval commands.
""",
    "docs/agent/verification.md": """# Verification

Run the task's declared checks while editing. Before reporting completion,
run `palari validate --json` and inspect `palari agent status WORK-ID --as
PALARI-ID --mode execute --json`. Authoritative `palari agent advance` does
not execute task prose. It runs fixed, built-in, shell-free verification
profiles before recording check results. For R1 work, the profile is an exact
Git base-to-head `git --literal-pathspecs diff --check BASE HEAD -- CHANGED_PATHS`
check.
""",
    "docs/agent/documentation-freshness.md": """# Documentation Freshness

Update committed agent guidance when commands, allowed-file rules, checks,
repository layout, or approval rules change. Run `palari docs check --json` after
those changes.
""",
}

AUTHORITY_ANCHOR_MESSAGE = "palari: anchor governance workspace"


def initialize_starter_workspace(
    target: str | Path,
    *,
    name: str = "",
    palari_name: str = "Claude",
    host: str = "",
    strict_git: bool = False,
    no_git_hook: bool = False,
) -> dict[str, Any]:
    """Create a starter workspace ready for ``work add`` and ``agent start``."""
    directory = Path(target).expanduser().resolve()
    adoption_root = _adoption_project_root(directory)
    workspace_file = directory / "workspace.json"
    if workspace_file.exists():
        raise WorkspaceError(
            f"workspace file already exists: {workspace_file}; "
            "use the existing workspace or initialize a different directory"
        )
    _validate_agent_doc_paths(directory)
    selected_host = host.strip().lower()
    if selected_host:
        from .agent_adoption import SUPPORTED_HOSTS

        if selected_host not in SUPPORTED_HOSTS:
            raise WorkspaceError("host must be one of: " + ", ".join(SUPPORTED_HOSTS))
    if strict_git and selected_host != "cursor":
        raise WorkspaceError("--strict-git is only valid with --host cursor")
    if no_git_hook and selected_host != "cursor":
        raise WorkspaceError("--no-git-hook is only valid with --host cursor")
    if strict_git and no_git_hook:
        raise WorkspaceError("--strict-git and --no-git-hook cannot be combined")
    bootstrap_adoption_blocker = _bootstrap_adoption_blocker(
        directory, adoption_root, selected_host
    )
    workspace_name = name.strip() or directory.name or "workspace"
    palari_label = palari_name.strip() or "Claude"
    palari_id = _palari_id(palari_label)
    reviewer_id = REVIEWER_ID if palari_id != REVIEWER_ID else "PALARI-INDEPENDENT-REVIEWER"
    human_name = _git_user_name(directory) or "Founder"
    default_worker = "claude-code" if palari_label.lower() == "claude" else palari_label.lower()

    data: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "name": workspace_name,
    }
    for key in ALL_COLLECTION_KEYS:
        data[key] = []
    data["humans"] = [
        {
            "id": HUMAN_ID,
            "name": human_name,
            "role": "Founder",
            "authority_level": "admin",
            "approval_capabilities": ["product", "merge"],
            "availability": "active",
        }
    ]
    data["palaris"] = [
        {
            "id": palari_id,
            "name": palari_label,
            "role": "AI coding partner",
            "scope": "Do bounded work items inside declared write boundaries.",
            "forbidden_actions": [
                "write outside approved work areas",
                "send external messages",
            ],
            "default_worker": default_worker,
            "owner_human": HUMAN_ID,
            "linked_goals": [GOAL_ID],
        },
        {
            "id": reviewer_id,
            "name": "Independent Reviewer",
            "role": "Review-only AI partner",
            "scope": (
                "Inspect exact current proof in review mode without editing task "
                "outputs or granting human approval."
            ),
            "forbidden_actions": [
                "build or modify task outputs",
                "broaden task scope",
                "send external messages",
                "record human approval",
            ],
            "default_worker": default_worker,
            "owner_human": HUMAN_ID,
            "linked_goals": [GOAL_ID],
        },
    ]
    data["goals"] = [
        {
            "id": GOAL_ID,
            "title": f"Ship {workspace_name} work safely with AI partners",
            "owner": HUMAN_ID,
            "status": "active",
            "priority": "high",
            "success_criteria": [
                "AI work stays inside declared write boundaries",
                "A human can see what was done and what needs review",
            ],
            "linked_palaris": [palari_id, reviewer_id],
        }
    ]
    data["sources"] = [
        {
            "id": SOURCE_ID,
            "label": "Repository",
            "kind": "repo",
            "provider": "local",
            "uri": ".",
            "access_mode": "read",
            "selected": True,
            "owner_human": HUMAN_ID,
            "allowed_palaris": [palari_id, reviewer_id],
            "data_class": "internal",
            "authority": "company_owned",
            "steward_human": HUMAN_ID,
        }
    ]
    data["workbenches"] = [
        {
            "id": WORKBENCH_ID,
            "label": "Main workbench",
            "summary": f"Default work area for {workspace_name}.",
            "goal_ids": [GOAL_ID],
            "palari_ids": [palari_id],
            "human_ids": [HUMAN_ID],
            "source_ids": [SOURCE_ID],
            "status": "active",
        }
    ]

    workspace = write_store(WorkspaceStore(data_path=workspace_file, data=data))
    agent_docs = _write_missing_agent_docs(directory)
    adoption: dict[str, Any] = {
        "schema_version": "palari.agent_adoption.v1",
        "status": "not-requested",
        "host": "",
        "changed": False,
        "changed_files": [],
        "message": "No host profile requested; the portable workspace remains active.",
    }
    if selected_host:
        if bootstrap_adoption_blocker:
            adoption = {
                "schema_version": "palari.agent_adoption.v1",
                "status": "blocked",
                "host": selected_host,
                "changed": False,
                "changed_files": [],
                "message": bootstrap_adoption_blocker,
            }
        else:
            from .agent_adoption import adopt_agent_host

            try:
                adoption = adopt_agent_host(
                    workspace_file,
                    project_dir=adoption_root,
                    host=selected_host,
                    palari_id=palari_id,
                    strict_git=strict_git,
                    no_git_hook=no_git_hook,
                )
            except WorkspaceError as exc:
                adoption = {
                    "schema_version": "palari.agent_adoption.v1",
                    "status": "blocked",
                    "host": selected_host,
                    "changed": False,
                    "changed_files": [],
                    "message": str(exc),
                }
    adoption_anchor_files: list[Path] = []
    adoption_root = Path(str(adoption.get("project") or directory)).resolve()
    for path in adoption.get("changed_files", []):
        adoption_anchor_files.append(adoption_root / str(path))
    authority_anchor = _anchor_starter_authority(
        workspace_file,
        created_docs=list(agent_docs["created"]),
        additional_files=adoption_anchor_files,
    )
    command_name = str(adoption.get("executable") or _current_cli_executable())
    workspace_arg = _workspace_cli_argument(directory)
    next_commands = [
        f'{quote(command_name)}{workspace_arg} work add "First task" --create docs/notes.md',
        f"{quote(command_name)}{workspace_arg} agent start --next --as {palari_id} --json",
    ]
    if authority_anchor["status"] == "blocked":
        next_commands = [authority_anchor["next_command"]]
    elif adoption["status"] == "blocked":
        next_commands = [
            f"{quote(command_name)} init {quote(str(directory))} --host {selected_host} "
            f"--as {palari_id} --json"
        ]
    return {
        "schema_version": "palari.init.v1",
        "workspace": workspace.name,
        "workspace_file": str(workspace_file),
        "valid": True,
        "human": {"id": HUMAN_ID, "name": human_name},
        "palari": {"id": palari_id, "name": palari_label},
        "reviewer": {"id": reviewer_id, "name": "Independent Reviewer"},
        "goal": GOAL_ID,
        "workbench": WORKBENCH_ID,
        "source": SOURCE_ID,
        "agent_docs": agent_docs,
        "adoption": adoption,
        "authority_anchor": authority_anchor,
        "next_commands": next_commands,
        "message": (
            f"Starter workspace '{workspace.name}' created. Add a bounded task "
            'with: palari work add "Title" --create PATH. '
            + str(authority_anchor["message"])
            + (f" Host adoption: {adoption.get('status', 'unknown')}." if selected_host else "")
        ),
    }


def quick_add_work(
    workspace_path: str | Path,
    title: str,
    *,
    create: list[str] | None = None,
    modify: list[str] | None = None,
    delete: list[str] | None = None,
    paths: list[str] | None = None,
    read: list[str] | None = None,
    palari_id: str = "",
    goal_id: str = "",
    workbench_id: str = "",
    risk: str = "R1",
    intensity: str = "light",
    scope: str = "",
    acceptance_target: str = "",
    verify: list[str] | None = None,
    approvals: int = 0,
    dependencies: list[str] | None = None,
    parallel_policy: str = "independent",
    idea: bool = False,
) -> dict[str, Any]:
    """Add one bounded task, or an authority-free idea for a human to approve."""
    clean_title = title.strip()
    if not clean_title:
        raise WorkspaceError("work title is required")
    path_intents = compile_path_intents(
        workspace_path,
        paths=paths,
        create=create,
        modify=modify,
        delete=delete,
    )
    exact_paths = [str(item["path"]) for item in path_intents]
    write_paths = exact_paths
    read_paths = _normalized_paths(read or [], "--read")
    store = load_store(workspace_path)
    workbench = _resolve_optional_default(store.data, "workbenches", workbench_id, "--workbench")
    palari = _resolve_default_palari(
        store.data,
        palari_id,
        workbench_id=workbench,
    )
    goal = _resolve_default(store.data, "goals", goal_id, "--goal")
    collection = "proposals" if idea else "work_items"
    id_factory = generate_proposal_id if idea else generate_work_id
    resolved_id = id_factory(_collection_ids(store.data, collection))
    dependency_ids = _normalized_ids(dependencies or [], "--depends-on")
    if parallel_policy not in {"independent", "coordinate", "exclusive"}:
        raise WorkspaceError(
            f"--parallel-policy must be independent, coordinate, or exclusive: {parallel_policy}"
        )
    known_work_ids = set(_collection_ids(store.data, "work_items"))
    for dependency_id in dependency_ids:
        if dependency_id == resolved_id:
            raise WorkspaceError(f"--depends-on cannot reference the new work item {resolved_id}")
        if dependency_id not in known_work_ids:
            raise WorkspaceError(f"--depends-on references unknown work item {dependency_id}")
    allowed_sources: list[str] = []
    workbench_outputs_added: list[str] = []
    bench: dict[str, Any] | None = None
    if workbench:
        bench = _find_record(store.data, "workbenches", workbench)
        allowed_sources = [str(item) for item in (bench or {}).get("source_ids", [])]
        # A task's outputs must live inside its project boundary, so declaring
        # a new write path here also declares it on the stored workbench.
        existing_outputs = [str(item) for item in (bench or {}).get("output_target_ids", [])]
        workbench_outputs_added = (
            [] if idea else [path for path in write_paths if path not in existing_outputs]
        )
        if workbench_outputs_added:
            assert bench is not None
            bench["output_target_ids"] = existing_outputs + workbench_outputs_added
    resources: list[str] = []
    for path in read_paths + write_paths:
        if path not in resources:
            resources.append(path)
    record = {
        "id": resolved_id,
        "title": clean_title,
        "goal": goal,
        "palari": palari,
        "workbench_id": workbench,
        "dependency_ids": dependency_ids,
        "risk": risk,
        "intensity": intensity,
        "status": "proposed" if idea else "active",
        "scope": scope.strip() or f"Do exactly this: {clean_title}.",
        "allowed_resources": resources,
        "allowed_sources": allowed_sources,
        "output_targets": write_paths,
        "conflict_targets": write_paths,
        "parallel_policy": parallel_policy,
        "forbidden_actions": ["write outside the declared write paths"],
        "acceptance_target": (
            acceptance_target.strip() or "Declared path intents hold and verification passes."
        ),
        "verification_expectations": list(verify or []),
        "required_approval_count": max(0, approvals),
    }
    record["path_intents"] = path_intents
    if idea:
        record.update({"proposer": palari, "created_at": utc_timestamp()})
        ideas = store.data.setdefault("proposals", [])
        if any(item.get("id") == resolved_id for item in ideas):
            raise WorkspaceError(f"idea already exists: {resolved_id}")
        ideas.append(record)
        workspace = write_store(
            store,
            metadata=MutationMetadata(
                command="work add --idea",
                actor=palari,
                action="suggested-bounded-work",
                timestamp=utc_timestamp(),
                objects=({"type": "proposal", "collection": "proposals", "id": resolved_id},),
            ),
        )
        next_command = palari_workspace_command(
            store.data_path, "approve", resolved_id, "--as", "HUMAN-ID", "--json"
        )
        return {
            "schema_version": "palari.work_idea.v1",
            "workspace": workspace.name,
            "workspace_file": str(store.data_path),
            "idea": record,
            "path_intents": path_intents,
            "status": "waiting-on-human",
            "next_step_type": "human-approval",
            "next_action": next_command,
            "next_commands": [next_command],
            "message": f"{resolved_id} suggested by {palari}; it grants no task authority.",
        }
    work_items = store.data.setdefault("work_items", [])
    if any(item.get("id") == resolved_id for item in work_items):
        raise WorkspaceError(f"work already exists: {resolved_id}")
    authority_anchor = _anchor_starter_authority(
        store.data_path,
        created_docs=_recoverable_agent_docs(store.data_path.parent),
    )
    if authority_anchor["status"] == "blocked":
        raise WorkspaceError(
            "Palari's trusted starting state is not anchored in Git: "
            f"{authority_anchor['message']}; next action: "
            f"{authority_anchor['next_command']}"
        )
    work_items.append(record)
    objects = [{"type": "work", "collection": "work_items", "id": resolved_id}]
    if workbench_outputs_added:
        objects.insert(
            0,
            {"type": "workbench", "collection": "workbenches", "id": workbench},
        )
    workspace = write_store(
        store,
        metadata=MutationMetadata(
            command="work add",
            actor=palari,
            action="created-bounded-work",
            timestamp=utc_timestamp(),
            objects=tuple(objects),
        ),
    )
    authority_plan = build_authority_plan(workspace, resolved_id, builder_id=palari)
    authority_blocked = not authority_plan["viable"]
    next_commands = (
        [
            palari_workspace_command(
                store.data_path,
                "detail",
                resolved_id,
                "--json",
            )
        ]
        if authority_blocked
        else [
            palari_workspace_command(
                store.data_path,
                "agent",
                "start",
                "--next",
                "--as",
                palari,
                "--mode",
                "execute",
                "--json",
            )
        ]
    )
    next_action = (
        str(authority_plan["smallest_correction"]) if authority_blocked else next_commands[0]
    )
    message = f"{resolved_id} created for {palari}: write boundary is {', '.join(write_paths)}."
    if authority_blocked:
        message += (
            f" Task is blocked before agent start. {authority_plan['message']} "
            f"Smallest safe correction: {next_action}"
        )
    return {
        "schema_version": "palari.work_add.v1",
        "workspace_file": str(store.data_path),
        "work_item": record,
        "path_intents": path_intents,
        "authority_anchor": authority_anchor,
        "authority_plan": authority_plan,
        "workbench_outputs_added": workbench_outputs_added,
        "status": "blocked" if authority_blocked else "ready",
        "next_step_type": "blocked" if authority_blocked else "start-work",
        "next_action": next_action,
        "next_commands": next_commands,
        "message": message,
    }


def _write_missing_agent_docs(directory: Path) -> dict[str, Any]:
    created: list[str] = []
    preserved: list[str] = []
    for relative, content in AGENT_DOC_TEMPLATES.items():
        candidate = directory / relative
        if candidate.exists() or candidate.is_symlink():
            preserved.append(relative)
            continue
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(content, encoding="utf-8")
        created.append(relative)
    return {
        "schema_version": "palari.agent_docs_bootstrap.v1",
        "created": created,
        "preserved": preserved,
        "status": "ready",
    }


def _bootstrap_adoption_blocker(
    directory: Path,
    adoption_root: Path,
    host: str,
) -> str:
    if not host:
        return ""
    roots: list[Path] = []
    for candidate in (adoption_root, directory):
        if candidate not in roots:
            roots.append(candidate)
    for root in roots:
        blocker = _bootstrap_adoption_blocker_at(root, host)
        if blocker:
            return blocker
    return ""


def _bootstrap_adoption_blocker_at(directory: Path, host: str) -> str:
    agents = directory / "AGENTS.md"
    if agents.exists() or agents.is_symlink():
        try:
            from .agent_adoption import has_portable_agent_contract

            if agents.is_symlink() or not agents.is_file():
                return "existing AGENTS.md is not a regular repository file"
            if not has_portable_agent_contract(agents.read_text(encoding="utf-8")):
                return (
                    "existing AGENTS.md is preserved; review it, then run the returned "
                    "host-adoption action separately"
                )
        except (OSError, UnicodeError) as exc:
            return f"existing AGENTS.md cannot be inspected safely: {exc}"
    host_file = {
        "codex": directory / ".codex" / "hooks.json",
        "claude": directory / ".claude" / "settings.json",
    }.get(host)
    if host_file is not None and (host_file.exists() or host_file.is_symlink()):
        return (
            f"existing {host_file.relative_to(directory)} is preserved; run the "
            "returned host-adoption action separately to merge reviewed hooks"
        )
    return ""


def _nearest_existing_directory(target: Path) -> Path:
    candidate = target
    while not candidate.is_dir() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _adoption_project_root(directory: Path) -> Path:
    repo_root = _git_root(_nearest_existing_directory(directory))
    if repo_root is None:
        return directory
    try:
        directory.relative_to(repo_root)
    except ValueError:
        return directory
    return repo_root


def _validate_agent_doc_paths(directory: Path) -> None:
    for relative in AGENT_DOC_TEMPLATES:
        candidate = directory / relative
        try:
            candidate.resolve(strict=False).relative_to(directory)
        except (OSError, ValueError) as exc:
            raise WorkspaceError(f"agent documentation path is unsafe: {relative}: {exc}") from exc
        cursor = directory
        parts = Path(relative).parts
        for index, part in enumerate(parts):
            cursor = cursor / part
            if cursor.is_symlink():
                raise WorkspaceError(
                    f"agent documentation path is unsafe: {relative}: "
                    f"path component is a symlink: {cursor.relative_to(directory)}"
                )
            if not cursor.exists():
                continue
            if index < len(parts) - 1 and not cursor.is_dir():
                raise WorkspaceError(
                    f"agent documentation path is unsafe: {relative}: "
                    f"parent is not a directory: {cursor.relative_to(directory)}"
                )
            if index == len(parts) - 1 and not cursor.is_file():
                raise WorkspaceError(
                    f"agent documentation path is unsafe: {relative}: "
                    f"target is not a regular file: {cursor.relative_to(directory)}"
                )


def _recoverable_agent_docs(directory: Path) -> list[str]:
    """Return only untouched Palari templates safe to include in recovery."""

    recoverable: list[str] = []
    for relative, content in AGENT_DOC_TEMPLATES.items():
        candidate = directory / relative
        try:
            if (
                not candidate.is_symlink()
                and candidate.is_file()
                and candidate.read_text(encoding="utf-8") == content
            ):
                recoverable.append(relative)
        except OSError:
            continue
    return recoverable


def _anchor_starter_authority(
    workspace_file: Path,
    *,
    created_docs: list[str],
    additional_files: list[Path] | None = None,
) -> dict[str, Any]:
    """Commit only newly adopted Palari files as an immutable starting point.

    `palari init` is the explicit local authorization for this bootstrap. The
    path-limited commit excludes unrelated staged and unstaged work. A retry is
    idempotent because an existing workspace Git blob is never rewritten from
    mutable current state.
    """

    root = _git_root(workspace_file.parent)
    if root is None:
        return {
            "schema_version": "palari.authority_anchor.v1",
            "status": "not-required",
            "commit": "",
            "paths": [],
            "next_command": "",
            "message": (
                "No Git worktree was found; local non-Git operation needs no "
                "trusted Git starting point."
            ),
        }
    try:
        workspace_relative = workspace_file.resolve().relative_to(root).as_posix()
    except (OSError, ValueError) as exc:
        raise WorkspaceError(f"workspace escapes its Git repository: {exc}") from exc

    head = _git_output(root, ["rev-parse", "--verify", "HEAD^{commit}"])
    if head and _git_blob_exists(root, head, workspace_relative):
        return {
            "schema_version": "palari.authority_anchor.v1",
            "status": "anchored",
            "commit": head,
            "paths": [workspace_relative],
            "next_command": "",
            "message": ("The trusted Git starting point already exists and was not rewritten."),
        }

    candidate_paths = [
        workspace_file,
        workspace_file.parent / ".palari" / "governance-journal.v2.jsonl",
        *(workspace_file.parent / relative for relative in created_docs),
        *(additional_files or []),
    ]
    relative_paths: list[str] = []
    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file():
            raise WorkspaceError(
                f"trusted-start path (authority_anchor) is not a regular file: {candidate}"
            )
        try:
            relative = candidate.resolve().relative_to(root).as_posix()
        except (OSError, ValueError) as exc:
            raise WorkspaceError(
                f"trusted-start path (authority_anchor) escapes Git: {candidate}: {exc}"
            ) from exc
        if relative not in relative_paths:
            relative_paths.append(relative)
    relative_paths.sort()
    command = _authority_anchor_command(root, relative_paths)
    if workspace_relative not in relative_paths:
        return {
            "schema_version": "palari.authority_anchor.v1",
            "status": "blocked",
            "commit": "",
            "paths": relative_paths,
            "next_command": command,
            "message": (
                "The workspace file is unavailable for an exact trusted Git starting point."
            ),
        }

    operation_markers = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")
    if any(
        _git_output(root, ["rev-parse", "-q", "--verify", marker]) for marker in operation_markers
    ):
        return {
            "schema_version": "palari.authority_anchor.v1",
            "status": "blocked",
            "commit": "",
            "paths": relative_paths,
            "next_command": command,
            "message": ("Git is already completing another history operation; finish it first."),
        }

    add = _run_git(root, ["add", "-f", "--", *relative_paths])
    if add.returncode != 0:
        return _blocked_anchor(relative_paths, command, add.stderr)
    commit = _run_git(
        root,
        [
            "commit",
            "--quiet",
            "--only",
            "-m",
            AUTHORITY_ANCHOR_MESSAGE,
            "--",
            *relative_paths,
        ],
        env=_bootstrap_git_identity(),
    )
    if commit.returncode != 0:
        _restore_anchor_index(root, relative_paths, bool(head))
        return _blocked_anchor(relative_paths, command, commit.stderr)
    anchored_head = _git_output(root, ["rev-parse", "--verify", "HEAD^{commit}"])
    if not anchored_head or not _git_blob_exists(root, anchored_head, workspace_relative):
        raise WorkspaceError(
            "Trusted-start commit (authority_anchor) did not contain workspace.json"
        )
    return {
        "schema_version": "palari.authority_anchor.v1",
        "status": "anchored",
        "commit": anchored_head,
        "paths": relative_paths,
        "next_command": "",
        "message": "Palari created one path-limited trusted Git starting point.",
    }


def _blocked_anchor(paths: list[str], command: str, stderr: str) -> dict[str, Any]:
    detail = stderr.strip() or "Git did not create the trusted starting point."
    return {
        "schema_version": "palari.authority_anchor.v1",
        "status": "blocked",
        "commit": "",
        "paths": paths,
        "next_command": command,
        "message": detail,
    }


def _restore_anchor_index(root: Path, paths: list[str], has_head: bool) -> None:
    args = (
        ["reset", "--quiet", "HEAD", "--", *paths]
        if has_head
        else [
            "rm",
            "--cached",
            "--quiet",
            "--ignore-unmatch",
            "--",
            *paths,
        ]
    )
    _run_git(root, args)


def _authority_anchor_command(root: Path, paths: list[str]) -> str:
    prefix = f"git -C {quote(str(root))} -c core.hooksPath=/dev/null -c commit.gpgSign=false"
    rendered = " ".join(quote(path) for path in paths)
    return (
        f"{prefix} add -f -- {rendered} && {prefix} commit --only "
        f"-m {quote(AUTHORITY_ANCHOR_MESSAGE)} -- {rendered}"
    )


def _bootstrap_git_identity() -> dict[str, str]:
    env = os.environ.copy()
    defaults = {
        "GIT_AUTHOR_NAME": "Palari Bootstrap",
        "GIT_AUTHOR_EMAIL": "palari-bootstrap@local.invalid",
        "GIT_COMMITTER_NAME": "Palari Bootstrap",
        "GIT_COMMITTER_EMAIL": "palari-bootstrap@local.invalid",
    }
    for key, value in defaults.items():
        if not env.get(key):
            env[key] = value
    return env


def _git_root(directory: Path) -> Path | None:
    root = _git_output(directory, ["rev-parse", "--show-toplevel"])
    if not root:
        return None
    try:
        return Path(root).resolve()
    except OSError:
        return None


def _git_blob_exists(root: Path, revision: str, path: str) -> bool:
    result = _run_git(root, ["cat-file", "-e", f"{revision}:{path}"])
    return result.returncode == 0


def _git_output(root: Path, args: list[str]) -> str:
    result = _run_git(root, args)
    return result.stdout.strip() if result.returncode == 0 else ""


def _run_git(
    root: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    git_env = (env or os.environ).copy()
    for key in tuple(git_env):
        if key in {
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_COMMON_DIR",
            "GIT_DIR",
            "GIT_EXEC_PATH",
            "GIT_INDEX_FILE",
            "GIT_NAMESPACE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_WORK_TREE",
        } or key.startswith("GIT_CONFIG_"):
            git_env.pop(key, None)
    git_env.update(
        {
            "GIT_PAGER": "cat",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    try:
        return subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "core.fsmonitor=false",
                *args,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            env=git_env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(
            ["git", "-C", str(root), *args],
            1,
            "",
            str(exc),
        )


def _palari_id(label: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", label.upper()).strip("-")
    return f"PALARI-{slug or 'PARTNER'}"


def _git_user_name(directory: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "config", "user.name"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _workspace_cli_argument(directory: Path) -> str:
    if directory == Path.cwd():
        return ""
    return f" --workspace {quote(str(directory))}"


def _current_cli_executable() -> str:
    invoked = Path(sys.argv[0]).expanduser()
    if invoked.name == "palari" and invoked.is_absolute():
        try:
            return str(invoked.resolve(strict=True))
        except OSError:
            pass
    return "palari"


def compile_path_intents(
    workspace_path: str | Path,
    *,
    paths: list[str] | None = None,
    create: list[str] | None = None,
    modify: list[str] | None = None,
    delete: list[str] | None = None,
) -> list[dict[str, str]]:
    """Compile exact stored path intents from flags and inferred PATH arguments."""

    claimed: dict[str, str] = {}
    ordered: list[dict[str, str]] = []

    def claim(path: str, intent: str) -> None:
        existing = claimed.get(path)
        if existing is not None and existing != intent:
            raise WorkspaceError(
                f"path {path} has conflicting intents {existing} and {intent}"
            )
        if existing is not None:
            return
        claimed[path] = intent
        ordered.append({"path": path, "intent": intent})

    for intent, flag in (("create", "--create"), ("modify", "--modify"), ("delete", "--delete")):
        values = create if intent == "create" else modify if intent == "modify" else delete
        for path in _normalized_paths(values or [], flag):
            claim(path, intent)
    for path in _normalized_paths(paths or [], "PATH"):
        if path in claimed:
            raise WorkspaceError(
                f"path {path} is already declared with --{claimed[path]}; "
                "do not also pass it as a positional PATH"
            )
        claim(path, _infer_path_intent(workspace_path, path))
    if not ordered:
        raise WorkspaceError(
            "at least one path is required; pass PATH, --create, --modify, or --delete"
        )
    return ordered


def _infer_path_intent(workspace_path: str | Path, relative: str) -> str:
    data_path = workspace_file_path(workspace_path)
    root = _git_root(data_path.parent)
    if root is not None:
        head = _git_output(root, ["rev-parse", "--verify", "HEAD^{commit}"])
        if head:
            kind = _git_output(root, ["cat-file", "-t", f"{head}:{relative}"])
            if kind == "blob":
                return "modify"
            if kind in {"tree", "commit"}:
                raise WorkspaceError(
                    f"PATH {relative} is a Git {kind}; declare a regular file"
                )
    candidate = data_path.parent / relative
    if candidate.is_symlink():
        raise WorkspaceError(f"PATH {relative} is a symlink; declare a regular file")
    if candidate.is_dir():
        raise WorkspaceError(f"PATH {relative} is a directory; declare a regular file")
    if root is None and candidate.is_file():
        return "modify"
    return "create"


def _normalized_paths(paths: list[str], flag: str) -> list[str]:
    normalized: list[str] = []
    for path in paths:
        try:
            value = validate_workspace_path(path)
        except ValueError as exc:
            raise WorkspaceError(f"{flag} {path!r}: {exc}") from exc
        if value not in normalized:
            normalized.append(value)
    return normalized


def _resolve_default(data: dict[str, Any], collection: str, explicit: str, flag: str) -> str:
    if explicit.strip():
        selected = explicit.strip()
        if selected not in _collection_ids(data, collection):
            raise WorkspaceError(f"{flag} references unknown {collection.rstrip('s')} {selected}")
        return selected
    ids = _collection_ids(data, collection)
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise WorkspaceError(f"workspace has no {collection}; run palari init or create one first")
    raise WorkspaceError(
        f"workspace has {len(ids)} {collection} ({', '.join(ids)}); pass {flag} to pick one"
    )


def _resolve_default_palari(
    data: dict[str, Any],
    explicit: str,
    *,
    workbench_id: str,
) -> str:
    if explicit.strip():
        return _resolve_default(data, "palaris", explicit, "--as")
    if workbench_id:
        workbench = _find_record(data, "workbenches", workbench_id)
        known = set(_collection_ids(data, "palaris"))
        builder_ids = [
            str(item) for item in (workbench or {}).get("palari_ids", []) if str(item) in known
        ]
        if len(builder_ids) == 1:
            return builder_ids[0]
        if builder_ids:
            raise WorkspaceError(
                f"workspace project {workbench_id} has {len(builder_ids)} palaris "
                f"({', '.join(builder_ids)}); pass --as to pick one"
            )
    return _resolve_default(data, "palaris", explicit, "--as")


def _resolve_optional_default(
    data: dict[str, Any],
    collection: str,
    explicit: str,
    flag: str,
) -> str:
    if explicit.strip():
        selected = explicit.strip()
        if selected not in _collection_ids(data, collection):
            raise WorkspaceError(f"{flag} references unknown {collection.rstrip('s')} {selected}")
        return selected
    ids = _collection_ids(data, collection)
    if len(ids) == 1:
        return ids[0]
    if not ids:
        return ""
    raise WorkspaceError(
        f"workspace has {len(ids)} {collection} ({', '.join(ids)}); pass {flag} to pick one"
    )


def _collection_ids(data: dict[str, Any], collection: str) -> list[str]:
    records = data.get(collection, [])
    if not isinstance(records, list):
        return []
    return [str(item.get("id", "")) for item in records if isinstance(item, dict)]


def _find_record(data: dict[str, Any], collection: str, record_id: str) -> dict[str, Any] | None:
    for item in data.get(collection, []):
        if isinstance(item, dict) and item.get("id") == record_id:
            return item
    return None


def _normalized_ids(values: list[str], flag: str) -> list[str]:
    normalized: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value:
            raise WorkspaceError(f"{flag} requires a non-empty work item id")
        if value in normalized:
            raise WorkspaceError(f"{flag} repeats work item {value}")
        normalized.append(value)
    return normalized

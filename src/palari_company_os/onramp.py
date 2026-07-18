"""Two-minute onramp for existing repositories.

``palari init`` creates a small but complete starter workspace (one human,
one Palari, one goal, one workbench, one repo source) in an existing project,
and ``palari work add`` creates an agent-startable work item from a title and
its write paths. Together with ``palari claude install`` they take a repo
from "never heard of Palari" to an enforced write boundary in three commands.

Everything here writes through the validated store. In Git repositories the
explicit initialization command also creates one hook-free, path-limited local
commit as the immutable authority origin; unrelated repository changes are not
included.
"""

from __future__ import annotations

import os
import re
import subprocess
from copy import deepcopy
from pathlib import Path
from shlex import quote
from typing import Any

from .governance_journal import MutationMetadata, utc_timestamp
from .history import append_history_event
from .path_policy import validate_workspace_path
from .store import WorkspaceStore, load_store, write_store
from .validation import COLLECTION_FILE_KEYS
from .work_identity import generate_work_id
from .workspace import CURRENT_SCHEMA_VERSION, WorkspaceError

HUMAN_ID = "HUMAN-FOUNDER"
GOAL_ID = "GOAL-0001"
WORKBENCH_ID = "WORKBENCH-MAIN"
SOURCE_ID = "SOURCE-REPO"

AGENT_DOC_TEMPLATES = {
    "AGENTS.md": """# Palari Agent Contract

Before changing files, claim one bounded work item:

```bash
palari agent start --next --as PALARI-ID --json
```

Continue only when the returned packet is ready. Read and write only the
declared paths, use only its selected sources, and stop at every review, human,
or external-effect boundary. After committing the bounded change, run:

```bash
palari agent advance WORK-ID --as PALARI-ID --json
```

`advance` derives deterministic proof and never manufactures independent review
or human acceptance. Use `palari agent doctor WORK-ID --as PALARI-ID --json`
for the next safe action. Repository orientation lives under `docs/agent/`.
""",
    "docs/agent/repo-map.md": """# Repository Map

`workspace.json` is the governed local truth. `.palari/` contains replayable
history and local runtime bindings. Record project-specific source, test, and
documentation ownership here before asking an agent to work broadly.
""",
    "docs/agent/contracts-and-invariants.md": """# Contracts And Invariants

- Work only inside the active packet's read and write boundaries.
- Do not invent sources, authority, receipts, evidence, review, or acceptance.
- Commit the bounded result before running `palari agent advance`.
- Treat review, human decisions, and external effects as real stop boundaries.
- Preserve `workspace.json` and `.palari/` as governed projection data.
""",
    "docs/agent/common-workflows.md": """# Common Workflows

Start ordinary work with `palari agent start --next --as PALARI-ID --json`.
Follow the packet, commit only the bounded change, and run `palari agent
advance WORK-ID --as PALARI-ID --json`. If blocked, run `palari agent doctor`
and report its exact next safe action.
""",
    "docs/agent/verification.md": """# Verification

Run the work item's declared checks while editing. Before reporting completion,
run `palari validate --json` and `palari agent check WORK-ID --as PALARI-ID
--mode execute --git-diff --json`. `palari agent advance` reruns only declared,
built-in verification profiles before deriving proof.
""",
    "docs/agent/documentation-freshness.md": """# Documentation Freshness

Update committed agent guidance when commands, boundaries, verification,
project layout, or authority rules change. Run `palari docs check --json` after
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
) -> dict[str, Any]:
    """Create a starter workspace ready for ``work add`` and ``agent start``."""
    directory = Path(target).expanduser().resolve()
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
            raise WorkspaceError(
                "host must be one of: " + ", ".join(SUPPORTED_HOSTS)
            )
    bootstrap_adoption_blocker = _bootstrap_adoption_blocker(
        directory, selected_host
    )
    workspace_name = name.strip() or directory.name or "workspace"
    palari_label = palari_name.strip() or "Claude"
    palari_id = _palari_id(palari_label)
    human_name = _git_user_name(directory) or "Founder"

    data: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "name": workspace_name,
    }
    for key in COLLECTION_FILE_KEYS:
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
            "default_worker": (
                "claude-code" if palari_label.lower() == "claude" else palari_label.lower()
            ),
            "owner_human": HUMAN_ID,
            "linked_goals": [GOAL_ID],
        }
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
            "linked_palaris": [palari_id],
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
            "allowed_palaris": [],
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
                    project_dir=directory,
                    host=selected_host,
                    palari_id=palari_id,
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
    workspace_arg = _workspace_cli_argument(directory)
    next_commands = [
        f'palari{workspace_arg} work add "First task" --write docs/notes.md',
        f"palari{workspace_arg} agent start --next --as {palari_id} --json",
    ]
    if authority_anchor["status"] == "blocked":
        next_commands = [authority_anchor["next_command"]]
    elif adoption["status"] == "blocked":
        next_commands = [
            f"palari init {quote(str(directory))} --host {selected_host} "
            f"--as {palari_id} --json"
        ]
    return {
        "schema_version": "palari.init.v1",
        "workspace": workspace.name,
        "workspace_file": str(workspace_file),
        "valid": True,
        "human": {"id": HUMAN_ID, "name": human_name},
        "palari": {"id": palari_id, "name": palari_label},
        "goal": GOAL_ID,
        "workbench": WORKBENCH_ID,
        "source": SOURCE_ID,
        "agent_docs": agent_docs,
        "adoption": adoption,
        "authority_anchor": authority_anchor,
        "next_commands": next_commands,
        "message": (
            f"Starter workspace '{workspace.name}' created. Add a bounded work "
            "item with: palari work add \"Title\" --write PATH. "
            + str(authority_anchor["message"])
            + (
                f" Host adoption: {adoption.get('status', 'unknown')}."
                if selected_host
                else ""
            )
        ),
    }


def quick_add_work(
    workspace_path: str | Path,
    title: str,
    *,
    write: list[str],
    create: list[str] | None = None,
    modify: list[str] | None = None,
    delete: list[str] | None = None,
    read: list[str] | None = None,
    palari_id: str = "",
    goal_id: str = "",
    workbench_id: str = "",
    risk: str = "R1",
    intensity: str = "light",
    scope: str = "",
    acceptance_target: str = "",
    verify: list[str] | None = None,
    work_id: str = "",
    approvals: int = 0,
    dependencies: list[str] | None = None,
    parallel_policy: str = "independent",
) -> dict[str, Any]:
    """Create one agent-startable work item from a title and its write paths."""
    clean_title = title.strip()
    if not clean_title:
        raise WorkspaceError("work title is required")
    legacy_write_paths = _normalized_paths(write, "--write")
    intent_inputs = {
        "create": _normalized_paths(create or [], "--create"),
        "modify": _normalized_paths(modify or [], "--modify"),
        "delete": _normalized_paths(delete or [], "--delete"),
    }
    path_intents = [
        {"path": path, "intent": intent}
        for intent, paths in intent_inputs.items()
        for path in paths
    ]
    if legacy_write_paths and path_intents:
        raise WorkspaceError(
            "legacy --write cannot be combined with exact --create, --modify, or "
            "--delete intents"
        )
    exact_paths = [str(item["path"]) for item in path_intents]
    if len(exact_paths) != len(set(exact_paths)):
        raise WorkspaceError(
            "an exact path may declare only one create, modify, or delete intent"
        )
    write_paths = legacy_write_paths or exact_paths
    if not write_paths:
        raise WorkspaceError(
            "at least one --write path or exact --create, --modify, or --delete "
            "path is required"
        )
    read_paths = _normalized_paths(read or [], "--read")

    store = load_store(workspace_path)
    palari = _resolve_default(store.data, "palaris", palari_id, "--as")
    goal = _resolve_default(store.data, "goals", goal_id, "--goal")
    workbench = _resolve_optional_default(store.data, "workbenches", workbench_id, "--workbench")
    resolved_id = work_id.strip() or generate_work_id(
        _collection_ids(store.data, "work_items")
    )
    dependency_ids = _normalized_ids(dependencies or [], "--depends-on")
    if parallel_policy not in {"independent", "coordinate", "exclusive"}:
        raise WorkspaceError(
            f"--parallel-policy must be independent, coordinate, or exclusive: "
            f"{parallel_policy}"
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
    before_bench: dict[str, Any] | None = None
    if workbench:
        bench = _find_record(store.data, "workbenches", workbench)
        allowed_sources = [str(item) for item in (bench or {}).get("source_ids", [])]
        # A work item's outputs must live inside its workbench boundary, so
        # declaring a new write path here also declares it on the workbench.
        existing_outputs = [str(item) for item in (bench or {}).get("output_target_ids", [])]
        workbench_outputs_added = [path for path in write_paths if path not in existing_outputs]
        if workbench_outputs_added:
            before_bench = deepcopy(bench)
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
        "status": "active",
        "scope": scope.strip() or f"Do exactly this: {clean_title}.",
        "allowed_resources": resources,
        "allowed_sources": allowed_sources,
        "output_targets": write_paths,
        "conflict_targets": write_paths,
        "parallel_policy": parallel_policy,
        "forbidden_actions": ["write outside the declared write paths"],
        "acceptance_target": (
            acceptance_target.strip()
            or (
                "Declared path intents hold and verification passes."
                if path_intents
                else "Declared outputs exist and verification passes."
            )
        ),
        "verification_expectations": list(verify or []),
        "required_approval_count": max(0, approvals),
    }
    if path_intents:
        record["path_intents"] = path_intents
    work_items = store.data.setdefault("work_items", [])
    if any(item.get("id") == resolved_id for item in work_items):
        raise WorkspaceError(f"work already exists: {resolved_id}")
    authority_anchor = _anchor_starter_authority(
        store.data_path,
        created_docs=_recoverable_agent_docs(store.data_path.parent),
    )
    if authority_anchor["status"] == "blocked":
        raise WorkspaceError(
            "Palari governance authority is not anchored in Git: "
            f"{authority_anchor['message']}; next action: "
            f"{authority_anchor['next_command']}"
        )
    work_items.append(record)
    objects = [
        {"type": "work", "collection": "work_items", "id": resolved_id}
    ]
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
    if workbench_outputs_added and bench is not None:
        append_history_event(
            store.data_path,
            schema_version=workspace.schema_version,
            command="work add",
            action="updated",
            object_type="workbench",
            object_collection="workbenches",
            object_id=workbench,
            actor=palari,
            before=before_bench,
            after=bench,
        )
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command="work add",
        action="created",
        object_type="work",
        object_collection="work_items",
        object_id=resolved_id,
        actor=palari,
        before=None,
        after=record,
    )

    return {
        "schema_version": "palari.work_add.v1",
        "workspace_file": str(store.data_path),
        "work_item": record,
        "path_intents": path_intents,
        "authority_anchor": authority_anchor,
        "workbench_outputs_added": workbench_outputs_added,
        "next_commands": [
            f"palari agent start --next --as {palari} --mode execute --json",
        ],
        "message": (
            f"{resolved_id} created for {palari}: write boundary is "
            f"{', '.join(write_paths)}."
        ),
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


def _bootstrap_adoption_blocker(directory: Path, host: str) -> str:
    if not host:
        return ""
    agents = directory / "AGENTS.md"
    if agents.exists() or agents.is_symlink():
        try:
            from .agent_adoption import has_portable_agent_contract

            if agents.is_symlink() or not agents.is_file():
                return "existing AGENTS.md is not a regular project file"
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


def _validate_agent_doc_paths(directory: Path) -> None:
    for relative in AGENT_DOC_TEMPLATES:
        candidate = directory / relative
        try:
            candidate.resolve(strict=False).relative_to(directory)
        except (OSError, ValueError) as exc:
            raise WorkspaceError(
                f"agent documentation path is unsafe: {relative}: {exc}"
            ) from exc


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
    """Commit only newly adopted governance files as an immutable baseline.

    `palari init` is the explicit local authorization for this bootstrap. The
    path-limited commit excludes unrelated staged and unstaged work. A retry is
    idempotent because an existing workspace Git blob is never rewritten from
    mutable current authority.
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
                "Git anchor."
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
            "message": (
                "Immutable Git authority was already present and was not rewritten."
            ),
        }

    candidate_paths = [
        workspace_file,
        workspace_file.parent / ".palari" / "history.jsonl",
        workspace_file.parent / ".palari" / "governance-journal.v1.jsonl",
        *(workspace_file.parent / relative for relative in created_docs),
        *(additional_files or []),
    ]
    relative_paths: list[str] = []
    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file():
            raise WorkspaceError(
                f"authority anchor path is not a regular file: {candidate}"
            )
        try:
            relative = candidate.resolve().relative_to(root).as_posix()
        except (OSError, ValueError) as exc:
            raise WorkspaceError(
                f"authority anchor path escapes Git: {candidate}: {exc}"
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
                "The workspace file is unavailable for an exact authority anchor."
            ),
        }

    operation_markers = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")
    if any(
        _git_output(root, ["rev-parse", "-q", "--verify", marker])
        for marker in operation_markers
    ):
        return {
            "schema_version": "palari.authority_anchor.v1",
            "status": "blocked",
            "commit": "",
            "paths": relative_paths,
            "next_command": command,
            "message": (
                "Git is already completing another history operation; finish it first."
            ),
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
    if not anchored_head or not _git_blob_exists(
        root, anchored_head, workspace_relative
    ):
        raise WorkspaceError(
            "Git authority anchor commit did not contain workspace.json"
        )
    return {
        "schema_version": "palari.authority_anchor.v1",
        "status": "anchored",
        "commit": anchored_head,
        "paths": relative_paths,
        "next_command": "",
        "message": "Palari created one path-limited local Git authority anchor.",
    }


def _blocked_anchor(paths: list[str], command: str, stderr: str) -> dict[str, Any]:
    detail = stderr.strip() or "Git did not create the authority anchor."
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
    prefix = (
        f"git -C {quote(str(root))} -c core.hooksPath=/dev/null "
        "-c commit.gpgSign=false"
    )
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
        raise WorkspaceError(
            f"workspace has no {collection}; run palari init or create one first"
        )
    raise WorkspaceError(
        f"workspace has {len(ids)} {collection} ({', '.join(ids)}); pass {flag} to pick one"
    )


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

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import to_plain
from .read_models import detail
from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class KiloCommand:
    argv: list[str]
    source: str
    available: bool
    note: str = ""


def kilo_status(allow_npx: bool = False) -> dict[str, Any]:
    command = resolve_kilo_command(allow_npx=allow_npx)
    payload: dict[str, Any] = {
        "available": command.available,
        "command": command.argv,
        "source": command.source,
        "note": command.note,
    }
    if command.available and command.source != "npx":
        version = _command_version(command.argv)
        if version:
            payload["version"] = version
    return payload


def resolve_kilo_command(allow_npx: bool = False, env: dict[str, str] | None = None) -> KiloCommand:
    environment = env if env is not None else os.environ
    configured = environment.get("PALARI_KILO_BIN", "").strip()
    if configured:
        argv = shlex.split(configured)
        return KiloCommand(argv=argv, source="PALARI_KILO_BIN", available=bool(argv))

    kilo = shutil.which("kilo")
    if kilo:
        return KiloCommand(argv=[kilo], source="PATH:kilo", available=True)

    kilocode = shutil.which("kilocode")
    if kilocode:
        return KiloCommand(argv=[kilocode], source="PATH:kilocode", available=True)

    npx = shutil.which("npx")
    if allow_npx and npx:
        return KiloCommand(argv=[npx, "--yes", "@kilocode/cli"], source="npx", available=True)

    note = (
        "Kilo CLI is not installed. Install @kilocode/cli, set PALARI_KILO_BIN, "
        "or rerun with --allow-npx."
    )
    return KiloCommand(argv=[], source="missing", available=False, note=note)


def build_kilo_prompt(workspace: Workspace, work_id: str, message: str = "") -> str:
    payload = detail(workspace, work_id)
    work = payload["work_item"]
    goal = payload["goal"] or {}
    palari = payload["palari"] or {}
    sources = payload["sources"] or _selected_sources_for_work(workspace, work)
    safety = payload["safety"]

    sections = [
        "You are Kilo Code being called from Palari Company OS.",
        "",
        "Use the Palari work boundary below as the source of truth.",
        "",
        f"Workspace: {workspace.name}",
        f"Work item: {work['id']} - {work['title']}",
        f"Goal: {goal.get('title', work['goal'])}",
        f"Palari: {palari.get('name', work['palari'])} ({palari.get('role', 'unknown role')})",
        f"Risk: {work['risk']} | Intensity: {work['intensity']} | Status: {work['status']}",
        "",
        "Scope:",
        _indent_or_none(work.get("scope")),
        "",
        "Allowed resources:",
        _list_or_none(work.get("allowed_resources", [])),
        "",
        "Allowed sources:",
        _source_list(sources),
        "",
        "Allowed actions:",
        _list_or_none(work.get("allowed_actions", [])),
        "",
        "Output targets:",
        _list_or_none(work.get("output_targets", [])),
        "",
        "Forbidden actions:",
        _list_or_none(work.get("forbidden_actions", [])),
        "",
        "Current Palari state:",
        f"- Attention: {payload['attention']}",
        f"- Why: {payload['why']}",
        f"- Next action: {payload['next_action']}",
        f"- AI safe to proceed: {'yes' if safety['ai_safe_to_proceed'] else 'no'}",
        f"- Waiting on human: {'yes' if safety['waiting_on_human'] else 'no'}",
        f"- Approval progress: {safety['approval_progress']}",
        "",
        "Operating rules:",
        "- Stay inside the allowed resources, sources, actions, and output targets.",
        "- Do not perform forbidden actions.",
        "- Do not claim external writes, approvals, deploys, or sends unless the work boundary allows them.",
        "- If the work needs human judgment or approval, stop with a clear handoff instead of pretending it is done.",
        "- Return a concise summary of what you did, what changed, what you did not do, and what should be reviewed.",
    ]
    if message:
        sections.extend(["", "User request:", message])
    else:
        sections.extend(["", "User request:", "Start the bounded work item and report the result."])
    return "\n".join(sections)


def run_kilo_for_work(
    workspace_path: str | Path,
    work_id: str,
    message: str = "",
    *,
    execute: bool = False,
    allow_npx: bool = False,
    model: str = "",
    agent: str = "",
    output_format: str = "default",
    run_dir: str | Path | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    workspace = Workspace.load(workspace_path)
    prompt = build_kilo_prompt(workspace, work_id, message)
    command = resolve_kilo_command(allow_npx=allow_npx)
    directory = Path(run_dir).expanduser().resolve() if run_dir else Path.cwd().resolve()
    argv = _kilo_run_argv(command.argv if command.available else ["kilo"], prompt, directory, model, agent, output_format)
    payload: dict[str, Any] = {
        "work_id": work_id,
        "workspace": workspace.name,
        "execute": execute,
        "available": command.available,
        "command_source": command.source,
        "command": argv,
        "cwd": str(directory),
        "prompt": prompt,
    }
    if command.note:
        payload["note"] = command.note
    if not execute:
        return payload
    if not command.available:
        raise WorkspaceError(command.note)

    try:
        completed = subprocess.run(
            argv,
            cwd=directory,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceError(f"Kilo execution timed out after {exc.timeout} seconds") from exc
    except OSError as exc:
        raise WorkspaceError(f"Kilo execution failed: {exc}") from exc
    payload.update(
        {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    return payload


def build_kilo_prompt_from_desktop_data(
    data: dict[str, Any], work_id: str, message: str = ""
) -> str:
    workspace = data["workspace"]
    work = data["work_items"].get(work_id)
    if work is None:
        raise WorkspaceError(f"desktop work item not found: {work_id}")
    palari = data["palaris"][work["palari_id"]]
    attempt = work["attempts"][work["current_attempt_id"]]
    receipt = attempt["receipt"]
    allowed_sources = [data["sources"][source_id] for source_id in work["allowed_source_ids"]]
    sources_used = [data["sources"][source_id] for source_id in attempt["sources_used"]]
    output_targets = [data["sources"][source_id] for source_id in work["output_target_ids"]]
    blocked_sources = [
        source
        for source in data["sources"].values()
        if palari["id"] not in source.get("allowed_palari_ids", [])
    ]

    sections = [
        "You are Kilo Code being called from the Palari Desktop app.",
        "",
        "Use the Palari desktop work boundary below as the source of truth.",
        "",
        f"Workspace: {workspace['label']}",
        f"Workbench: {_selected_workbench_path(data)}",
        f"Work item: {work['public_id']} - {work['title']}",
        f"Palari: {palari['name']} ({palari['role']})",
        f"Risk: {work['risk_label']} | Status: {attempt['status_label']}",
        "",
        "Palari scope:",
        _indent_or_none(palari.get("scope")),
        "",
        "Allowed sources:",
        _desktop_source_list(allowed_sources),
        "",
        "Sources used in the current attempt:",
        _desktop_source_list(sources_used),
        "",
        "Output targets:",
        _desktop_source_list(output_targets),
        "",
        "Allowed actions:",
        _list_or_none(work.get("allowed_actions", [])),
        "",
        "Blocked sources visible in the UI:",
        _desktop_source_list(blocked_sources),
        "",
        "Current receipt:",
        f"- Used: {receipt['sources_used']}",
        f"- Created: {receipt['created']}",
        f"- External writes: {receipt['external_writes']}",
        f"- Did not do: {receipt['not_done']}",
        f"- Undo: {receipt['undo']}",
        "",
        "Authority:",
        f"- {attempt['authority']['requirement']}",
        f"- {attempt['authority']['summary']}",
        "",
        "Operating rules:",
        "- Stay inside the allowed sources, allowed actions, and output targets.",
        "- Do not read blocked sources.",
        "- Do not perform external writes unless the work boundary and human approval allow it.",
        "- Treat this desktop prototype as a read-only demo unless explicitly instructed by the caller.",
        "- Return a concise summary of what you would do, what you used, what you did not do, and what needs review.",
    ]
    if message:
        sections.extend(["", "User request:", message])
    else:
        sections.extend(["", "User request:", "Review the selected work item and propose the next bounded step."])
    return "\n".join(sections)


def run_kilo_for_desktop_data(
    data: dict[str, Any],
    work_id: str,
    message: str = "",
    *,
    execute: bool = False,
    allow_npx: bool = False,
    model: str = "",
    agent: str = "",
    output_format: str = "default",
    run_dir: str | Path | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    prompt = build_kilo_prompt_from_desktop_data(data, work_id, message)
    command = resolve_kilo_command(allow_npx=allow_npx)
    directory = Path(run_dir).expanduser().resolve() if run_dir else Path.cwd().resolve()
    argv = _kilo_run_argv(command.argv if command.available else ["kilo"], prompt, directory, model, agent, output_format)
    work = data["work_items"][work_id]
    payload: dict[str, Any] = {
        "work_id": work_id,
        "work_title": work["title"],
        "workspace": data["workspace"]["label"],
        "execute": execute,
        "available": command.available,
        "command_source": command.source,
        "command": argv,
        "cwd": str(directory),
        "prompt": prompt,
    }
    if command.note:
        payload["note"] = command.note
    if not execute:
        return payload
    if not command.available:
        raise WorkspaceError(command.note)

    try:
        completed = subprocess.run(
            argv,
            cwd=directory,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceError(f"Kilo execution timed out after {exc.timeout} seconds") from exc
    except OSError as exc:
        raise WorkspaceError(f"Kilo execution failed: {exc}") from exc
    payload.update(
        {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    )
    return payload


def _kilo_run_argv(
    base: list[str],
    prompt: str,
    directory: Path,
    model: str,
    agent: str,
    output_format: str,
) -> list[str]:
    argv = [*base, "run", "--dir", str(directory)]
    if model:
        argv.extend(["--model", model])
    if agent:
        argv.extend(["--agent", agent])
    if output_format != "default":
        argv.extend(["--format", output_format])
    argv.append(prompt)
    return argv


def _command_version(argv: list[str]) -> str:
    try:
        completed = subprocess.run(
            [*argv, "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[-1] if output else ""


def _indent_or_none(value: str | None) -> str:
    if not value:
        return "- none declared"
    return f"- {value}"


def _list_or_none(values: list[str]) -> str:
    if not values:
        return "- none declared"
    return "\n".join(f"- {value}" for value in values)


def _source_list(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "- none declared"
    lines = []
    for source in sources:
        source_plain = to_plain(source)
        lines.append(
            f"- {source_plain['id']}: {source_plain['label']} "
            f"[{source_plain.get('provider', '')}; {source_plain.get('access_mode', '')}]"
        )
    return "\n".join(lines)


def _desktop_source_list(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "- none declared"
    lines = []
    for source in sources:
        lines.append(
            f"- {source['id']}: {source['title']} "
            f"[{source.get('provider', '')}; {source.get('access', '')}; {source.get('mode', '')}]"
        )
    return "\n".join(lines)


def _selected_workbench_path(data: dict[str, Any]) -> str:
    workbench = data["workbenches"][data["selected_workbench_id"]]
    return " / ".join(workbench["path"])


def _selected_sources_for_work(workspace: Workspace, work: dict[str, Any]) -> list[dict[str, Any]]:
    sources = []
    palari_id = work["palari"]
    for source in workspace.sources:
        if not source.selected:
            continue
        if source.allowed_palaris and palari_id not in source.allowed_palaris:
            continue
        sources.append(to_plain(source))
    return sources

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .workspace import WorkspaceError, default_workspace_path


BLOCKED_PATH = "deploy/production.yml"
ALLOWED_PATH = "docs/product/company-os.md"
WORK_ID = "WORK-0003"
PALARI_ID = "PALARI-SOFIA"


def run_demo(demo_dir: str | None, *, no_pause: bool) -> dict[str, Any]:
    temp_directory: tempfile.TemporaryDirectory[str] | None = None
    if demo_dir:
        workspace_dir = Path(demo_dir).expanduser().resolve()
        _ensure_empty_demo_dir(workspace_dir)
    else:
        temp_directory = tempfile.TemporaryDirectory(prefix="palari-demo-")
        workspace_dir = Path(temp_directory.name)

    try:
        _copy_demo_workspace(workspace_dir)
        steps: list[dict[str, Any]] = []
        queue_step = _run_step(
            workspace_dir,
            "See today's work",
            "Sofia has one small writing task and clear file limits.",
            ["queue"],
        )
        queue_step["display_stdout"] = _queue_display_summary(
            _run_json(workspace_dir, ["queue"])
        )
        steps.append(queue_step)
        steps.append(
            _run_step(
                workspace_dir,
                "Sofia starts the task",
                "The next output says what Sofia may read and write.",
                ["agent", "start", WORK_ID, "--as", PALARI_ID, "--mode", "execute"],
            )
        )
        blocked_step = _run_step(
            workspace_dir,
            "The unsafe change is blocked",
            "Now the named file change is checked against Sofia's file limit.",
            [
                "agent",
                "check",
                WORK_ID,
                "--as",
                PALARI_ID,
                "--mode",
                "execute",
                "--changed",
                BLOCKED_PATH,
            ],
        )
        blocked_payload = _run_json(
            workspace_dir,
            [
                "agent",
                "check",
                WORK_ID,
                "--as",
                PALARI_ID,
                "--mode",
                "execute",
                "--changed",
                BLOCKED_PATH,
            ],
        )
        blocked_step["display_stdout"] = _agent_check_display_summary(
            blocked_payload,
            focus_code="FILE_CHANGES_WITHIN_WRITE_BOUNDARY",
        )
        blocked_step.update(_blocked_highlight(blocked_payload))
        steps.append(blocked_step)

        allowed_step = _run_step(
            workspace_dir,
            "The file boundary passes; proof is still needed",
            "The safe file is inside Sofia's boundary; receipt and evidence still gate completion.",
            [
                "agent",
                "check",
                WORK_ID,
                "--as",
                PALARI_ID,
                "--mode",
                "execute",
                "--changed",
                ALLOWED_PATH,
            ],
        )
        allowed_payload = _run_json(
            workspace_dir,
            [
                "agent",
                "check",
                WORK_ID,
                "--as",
                PALARI_ID,
                "--mode",
                "execute",
                "--changed",
                ALLOWED_PATH,
            ],
        )
        allowed_step["display_stdout"] = _agent_check_display_summary(
            allowed_payload,
            focus_code="FILE_CHANGES_WITHIN_WRITE_BOUNDARY",
        )
        allowed_step.update(_allowed_highlight(allowed_payload))
        steps.append(allowed_step)

        steps.append(
            _run_step(
                workspace_dir,
                "Sofia records what happened",
                "The receipt names what changed, what did not happen, and how to undo it.",
                [
                    "receipt",
                    "record",
                    "RECEIPT-DEMO",
                    "--work-item-id",
                    WORK_ID,
                    "--attempt-id",
                    "ATTEMPT-0002",
                    "--actor",
                    PALARI_ID,
                    "--list",
                    "actions_taken=edited onboarding copy",
                    "--list",
                    f"outputs_created={ALLOWED_PATH}",
                    "--list",
                    f"not_done=did not touch {BLOCKED_PATH}",
                    "--list",
                    f"undo_refs=revert {ALLOWED_PATH}",
                ],
            )
        )
        steps.append(
            _run_step(
                workspace_dir,
                "Sofia adds proof and asks what is next",
                "Palari now asks for review instead of pretending the work is done.",
                [
                    "evidence",
                    "record",
                    "EVIDENCE-DEMO",
                    "--work-item-id",
                    WORK_ID,
                    "--attempt-id",
                    "ATTEMPT-0002",
                    "--head-sha",
                    "def5678",
                    "--status",
                    "passed",
                    "--summary",
                    "Demo verification passed for allowed file boundary.",
                ],
            )
        )
        steps.append(
            _run_step(
                workspace_dir,
                "The finish check stops at review",
                "A completed-looking task still waits for the next human-facing step.",
                ["agent", "finish", WORK_ID, "--as", PALARI_ID],
            )
        )
        steps.append(
            _run_step(
                workspace_dir,
                "Human approval stays human",
                "For higher-stakes work, Palari prepares the approval handoff but does not approve it.",
                ["agent", "handoff", "WORK-0001", "--as", PALARI_ID],
            )
        )
        return {
            "schema_version": "palari.demo.v1",
            "workspace_dir": str(workspace_dir),
            "cleanup": temp_directory is not None,
            "no_pause": no_pause,
            "steps": steps,
            "plain_summary": [
                "Palari gave Sofia a small file boundary for one task.",
                f"When {BLOCKED_PATH} appeared, Palari blocked it and named the exact path.",
                "For the safe file, Palari kept a receipt and showed the next review or approval step.",
            ],
            "try_next_commands": [
                "palari demo",
                "palari agent next --json",
                "palari agent check WORK-ID --as PALARI-ID --changed PATH --json",
            ],
        }
    finally:
        if temp_directory is not None:
            temp_directory.cleanup()


def serve_demo(demo_dir: str | None, *, host: str = "127.0.0.1", port: int = 0) -> dict[str, Any]:
    from .mission_control import serve_mission_control

    temp_directory: tempfile.TemporaryDirectory[str] | None = None
    if demo_dir:
        workspace_dir = Path(demo_dir).expanduser().resolve()
    else:
        temp_directory = tempfile.TemporaryDirectory(prefix="palari-demo-serve-")
        workspace_dir = Path(temp_directory.name)
    try:
        run_demo(str(workspace_dir), no_pause=True)
        return serve_mission_control(workspace_dir, "HUMAN-FOUNDER", host=host, port=port)
    finally:
        if temp_directory is not None:
            temp_directory.cleanup()


def _ensure_empty_demo_dir(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise WorkspaceError(f"demo directory must be empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _copy_demo_workspace(workspace_dir: Path) -> None:
    shutil.copytree(default_workspace_path(), workspace_dir, dirs_exist_ok=True)
    output_path = workspace_dir / ALLOWED_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("Draft onboarding note copy.\n", encoding="utf-8")


def _run_step(
    workspace_dir: Path,
    title: str,
    narration: str,
    args: list[str],
) -> dict[str, Any]:
    command = _display_command(workspace_dir, args)
    result = _run_cli(workspace_dir, args)
    if result.returncode != 0:
        raise WorkspaceError(result.stderr.strip() or result.stdout.strip())
    return {
        "title": title,
        "narration": narration,
        "command": command,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _run_json(workspace_dir: Path, args: list[str]) -> dict[str, Any]:
    result = _run_cli(workspace_dir, [*args, "--json"])
    if result.returncode != 0:
        raise WorkspaceError(result.stderr.strip() or result.stdout.strip())
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise WorkspaceError("demo command returned non-object JSON")
    return payload


def _run_cli(workspace_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "palari_company_os",
        "--workspace",
        str(workspace_dir),
        *args,
    ]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=workspace_dir,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _display_command(workspace_dir: Path, args: list[str]) -> str:
    return " ".join(["palari", "--workspace", str(workspace_dir), *args])


def _queue_display_summary(payload: dict[str, Any]) -> str:
    items = _dict_items(payload.get("queue"))
    selected: list[dict[str, Any]] = []

    target = _first_item(items, "id", WORK_ID)
    if target:
        selected.append(target)

    for item in items:
        if item.get("id") != WORK_ID and item.get("waiting_on_human"):
            selected.append(item)
            break

    if not selected:
        selected = items[:2]

    lines = [
        f"Palari Company OS Queue: {payload.get('workspace', 'workspace')}",
        f"Showing {len(selected)} of {len(items)} items for this demo.",
    ]
    for item in selected:
        risk = item.get("risk", "")
        intensity = item.get("intensity", "")
        label = f"{item.get('id', 'WORK')} [{intensity} / {risk}]".strip()
        lines.extend(
            [
                "",
                f"{label} {item.get('title', '')}".rstrip(),
                f"  attention: {item.get('attention', 'unknown')}",
                f"  why: {item.get('why', 'No queue reason recorded.')}",
                f"  next: {item.get('next_action', 'Open the work detail.')}",
            ]
        )
        active_attempts = _dict_items(item.get("active_attempts"))
        if active_attempts:
            attempt_ids = ", ".join(
                str(attempt.get("attempt_id", ""))
                for attempt in active_attempts
            )
            lines.append(f"  active attempts: {attempt_ids}")

    lines.extend(["", "Full queue: palari queue --json"])
    return "\n".join(lines)


def _agent_check_display_summary(payload: dict[str, Any], *, focus_code: str) -> str:
    checks = _dict_items(payload.get("checks"))
    passed = [check for check in checks if check.get("status") == "pass"]
    failed = [check for check in checks if check.get("status") != "pass"]
    focus = _first_item(checks, "code", focus_code)
    other_failures = [
        check
        for check in failed
        if check.get("code") != focus_code
    ]

    lines = [
        f"Agent check: {payload.get('check_id', 'check')}",
        f"OK: {'yes' if payload.get('ok') else 'no'}",
        f"Step: {payload.get('next_step_type', 'unknown')}",
        f"Checks: {len(passed)} passed.",
    ]
    if focus:
        status = str(focus.get("status", "unknown"))
        required = "required" if focus.get("required") else "optional"
        lines.append(
            f"  - {focus.get('code')} [{status}, {required}]: "
            f"{focus.get('message', '')}"
        )

    if other_failures:
        codes = ", ".join(
            str(check.get("code", "UNKNOWN")) for check in other_failures
        )
        lines.append(f"Other blockers still pending before completion: {codes}.")

    next_commands = [
        str(command)
        for command in payload.get("next_allowed_commands", [])
        if isinstance(command, str)
        and (
            command.startswith("palari receipt")
            or command.startswith("palari evidence")
        )
    ]
    if next_commands:
        lines.append("Next proof commands:")
        for command in next_commands[:2]:
            lines.append(f"  {command}")
    return "\n".join(lines)


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            items.append({str(key): item_value for key, item_value in item.items()})
    return items


def _first_item(
    items: list[dict[str, Any]],
    field: str,
    expected: str,
) -> dict[str, Any] | None:
    for item in items:
        if item.get(field) == expected:
            return item
    return None


def _blocked_highlight(payload: dict[str, Any]) -> dict[str, Any]:
    file_changes = payload.get("file_changes") or {}
    outside = list(file_changes.get("outside_write_boundary") or [])
    allowed = list(file_changes.get("allowed_write_paths") or [])
    return {
        "block_marker": "*** BLOCKED: file change is outside Sofia's write boundary ***",
        "offending_path": outside[0] if outside else BLOCKED_PATH,
        "allowed_write_paths": allowed,
    }


def _allowed_highlight(payload: dict[str, Any]) -> dict[str, Any]:
    file_changes = payload.get("file_changes") or {}
    inside = list(file_changes.get("inside_write_boundary") or [])
    return {
        "pass_marker": (
            f"PATH ALLOWED: {inside[0]} is inside Sofia's write boundary."
            if inside
            else "PATH ALLOWED: observed change stayed inside Sofia's write boundary."
        )
    }

from __future__ import annotations

from pathlib import Path
from typing import Any

from .command_surface import palari_workspace_command


def agent_commands(
    work: Any,
    next_step_type: str = "",
    *,
    workspace_path: Path | str,
) -> dict[str, str]:
    commands = {
        "next": _command(
            workspace_path,
            "agent",
            "next",
            "--as",
            work.palari,
            "--json",
        ),
        "brief": _agent_work_command(
            workspace_path,
            "brief",
            work,
            "--mode",
            "execute",
        ),
        "start": _agent_work_command(
            workspace_path,
            "start",
            work,
            "--mode",
            "execute",
        ),
        "check": _agent_work_command(
            workspace_path,
            "check",
            work,
            "--mode",
            "execute",
        ),
        "finish": _agent_work_command(workspace_path, "finish", work),
        "doctor": _agent_work_command(workspace_path, "doctor", work),
        "loop": _agent_work_command(workspace_path, "loop", work),
        "handoff": _agent_work_command(workspace_path, "handoff", work),
    }
    if next_step_type == "review-handoff":
        commands["review"] = _agent_work_command(
            workspace_path,
            "brief",
            work,
            "--mode",
            "review",
        )
        commands["review_check"] = _agent_work_command(
            workspace_path,
            "check",
            work,
            "--mode",
            "review",
        )
    return commands


def agent_loop_command(work: Any, *, workspace_path: Path | str) -> str:
    return _agent_work_command(workspace_path, "loop", work)


def agent_handoff_command(
    work: Any,
    next_step_type: str,
    *,
    workspace_path: Path | str,
) -> str:
    if next_step_type in {"human-decision", "review-handoff"}:
        return _agent_work_command(workspace_path, "handoff", work)
    return ""


def work_next_commands(
    work: Any,
    attention: str,
    open_decision: Any | None,
    has_current_attempt: bool,
    ai_safe_to_proceed: bool,
    *,
    workspace_path: Path | str,
) -> list[str]:
    commands: list[str] = []
    if open_decision is not None:
        commands.append(
            _command(
                workspace_path,
                "decision",
                "guide",
                open_decision.id,
                "--json",
            )
        )
    elif attention == "needs-review":
        commands.append(
            _command(
                workspace_path,
                "review",
                "guide",
                work.id,
                "--json",
            )
        )
    elif attention == "needs-evidence" and has_current_attempt:
        commands.append(
            _agent_work_command(
                workspace_path,
                "check",
                work,
                "--mode",
                "execute",
            )
        )
        commands.append(_agent_work_command(workspace_path, "finish", work))
    elif attention in {"ready-for-ai-work", "needs-evidence", "changes-requested"} and ai_safe_to_proceed:
        commands.append(
            _agent_work_command(
                workspace_path,
                "brief",
                work,
                "--mode",
                "execute",
            )
        )
    commands.append(_command(workspace_path, "detail", work.id, "--json"))
    commands.append(_command(workspace_path, "validate", "--json"))
    return commands


def _agent_work_command(
    workspace_path: Path | str,
    action: str,
    work: Any,
    *extra: str,
) -> str:
    return _command(
        workspace_path,
        "agent",
        action,
        work.id,
        "--as",
        work.palari,
        *extra,
        "--json",
    )


def _command(workspace_path: Path | str, *arguments: str) -> str:
    return palari_workspace_command(workspace_path, *arguments)

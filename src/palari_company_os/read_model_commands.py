from __future__ import annotations

from typing import Any


def agent_commands(work: Any, next_step_type: str = "") -> dict[str, str]:
    commands = {
        "next": f"palari agent next --as {work.palari} --json",
        "brief": f"palari agent brief {work.id} --as {work.palari} --mode execute --json",
        "start": f"palari agent start {work.id} --as {work.palari} --mode execute --json",
        "check": f"palari agent check {work.id} --as {work.palari} --mode execute --json",
        "finish": f"palari agent finish {work.id} --as {work.palari} --json",
        "doctor": f"palari agent doctor {work.id} --as {work.palari} --json",
        "loop": f"palari agent loop {work.id} --as {work.palari} --json",
        "handoff": f"palari agent handoff {work.id} --as {work.palari} --json",
    }
    if next_step_type == "review-handoff":
        commands["review"] = (
            f"palari agent brief {work.id} --as {work.palari} --mode review --json"
        )
        commands["review_check"] = (
            f"palari agent check {work.id} --as {work.palari} --mode review --json"
        )
    return commands


def agent_loop_command(work: Any) -> str:
    return f"palari agent loop {work.id} --as {work.palari} --json"


def agent_handoff_command(work: Any, next_step_type: str) -> str:
    if next_step_type in {"human-decision", "review-handoff"}:
        return f"palari agent handoff {work.id} --as {work.palari} --json"
    return ""


def work_next_commands(
    work: Any,
    attention: str,
    open_decision: Any | None,
    has_current_attempt: bool,
    ai_safe_to_proceed: bool,
) -> list[str]:
    commands: list[str] = []
    if open_decision is not None:
        commands.append(f"palari decision guide {open_decision.id} --json")
    elif attention in {"needs-review", "receipt-ready"}:
        commands.append(f"palari review guide {work.id} --json")
    elif attention == "needs-evidence" and has_current_attempt:
        commands.append(f"palari agent check {work.id} --as {work.palari} --mode execute --json")
        commands.append(f"palari agent finish {work.id} --as {work.palari} --json")
    elif attention in {"ready-for-ai-work", "needs-evidence", "changes-requested"} and ai_safe_to_proceed:
        commands.append(f"palari agent brief {work.id} --as {work.palari} --mode execute --json")
    commands.append(f"palari detail {work.id} --json")
    commands.append("palari validate --json")
    return commands

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from typing import Any

from .cli_dispatch import run_command
from .cli_output import print_result
from .cli_parser import build_parser
from .workspace import WorkspaceError


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if _raw_agent_json_requested(raw_argv):
        parse_errors = io.StringIO()
        try:
            with contextlib.redirect_stderr(parse_errors):
                args = parser.parse_args(argv)
        except SystemExit as exc:
            print(
                json.dumps(
                    _agent_parse_error_payload(raw_argv, parse_errors.getvalue()),
                    indent=2,
                    sort_keys=True,
                )
            )
            return int(exc.code) if isinstance(exc.code, int) else 2
    else:
        args = parser.parse_args(argv)

    try:
        result = run_command(args)
        print_result(result)
        return 0
    except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
        if _agent_json_requested(args, raw_argv):
            print(json.dumps(_agent_error_payload(args, exc), indent=2, sort_keys=True))
            return 2
        parser.exit(2, f"palari: {exc}\n")

    parser.exit(2, "palari: unknown command\n")
    return 2


def _agent_json_requested(args: Any, raw_argv: list[str]) -> bool:
    return (
        getattr(args, "command", "") == "agent"
        and getattr(args, "json", False)
        and "--json" in raw_argv
    )


def _raw_agent_json_requested(raw_argv: list[str]) -> bool:
    return "agent" in raw_argv and "--json" in raw_argv


def _agent_parse_error_payload(raw_argv: list[str], parser_message: str) -> dict[str, Any]:
    message = _clean_parse_error(parser_message)
    work_id = _raw_work_id(raw_argv)
    palari_id = _raw_palari_id(raw_argv)
    mode = _raw_mode(raw_argv)
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": "ARGUMENT_PARSE_ERROR",
            "message": message,
            "command": " ".join(raw_argv),
        },
        "next_allowed_commands": _agent_error_next_commands(work_id, palari_id, mode),
    }
    if work_id:
        payload["error"]["work_item"] = work_id
    if palari_id:
        payload["error"]["palari"] = palari_id
    return payload


def _clean_parse_error(parser_message: str) -> str:
    lines = [line.strip() for line in parser_message.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("palari: error:"):
            return line.removeprefix("palari: error:").strip()
        if " error: " in line:
            return line.split(" error: ", 1)[1].strip()
    return lines[-1] if lines else "invalid agent command arguments"


def _agent_error_payload(args: Any, exc: BaseException) -> dict[str, Any]:
    message = _clean_error_message(exc)
    work_id = str(getattr(args, "work_id", "") or "")
    palari_id = str(getattr(args, "palari_id", "") or "")
    mode = str(getattr(args, "mode", "") or "execute")
    command = " ".join(
        item
        for item in [
            "agent",
            str(getattr(args, "agent_command", "") or ""),
            work_id,
        ]
        if item
    )
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": _error_code(message),
            "message": message,
            "command": command,
        },
        "next_allowed_commands": _agent_error_next_commands(work_id, palari_id, mode),
    }
    if work_id:
        payload["error"]["work_item"] = work_id
    if palari_id:
        payload["error"]["palari"] = palari_id
    return payload


def _raw_work_id(raw_argv: list[str]) -> str:
    try:
        index = raw_argv.index("agent")
    except ValueError:
        return ""
    if index + 2 >= len(raw_argv):
        return ""
    subcommand = raw_argv[index + 1]
    if subcommand in {"brief", "start", "release", "check", "finish", "handoff", "doctor", "loop"}:
        value = raw_argv[index + 2]
        return "" if value.startswith("-") else value
    return ""


def _raw_palari_id(raw_argv: list[str]) -> str:
    for flag in ("--as", "--palari"):
        if flag in raw_argv:
            index = raw_argv.index(flag)
            if index + 1 < len(raw_argv):
                return raw_argv[index + 1]
    return ""


def _raw_mode(raw_argv: list[str]) -> str:
    if "--mode" in raw_argv:
        index = raw_argv.index("--mode")
        if index + 1 < len(raw_argv):
            return raw_argv[index + 1]
    return "execute"


def _clean_error_message(exc: BaseException) -> str:
    message = str(exc)
    if isinstance(exc, KeyError):
        message = message.strip("'\"")
    return message


def _error_code(message: str) -> str:
    lowered = message.lower()
    if "unknown decision or linked work" in lowered:
        return "UNKNOWN_DECISION_OR_LINKED_WORK"
    if "unknown work item" in lowered or "work item not found" in lowered:
        return "UNKNOWN_WORK_ITEM"
    if "palari not found" in lowered or "missing palari" in lowered:
        return "MISSING_PALARI"
    if "workspace file not found" in lowered:
        return "WORKSPACE_FILE_NOT_FOUND"
    if "already claimed" in lowered:
        return "CLAIM_CONFLICT"
    if "claimed by" in lowered:
        return "CLAIM_OWNER_MISMATCH"
    words = re.findall(r"[A-Za-z0-9]+", message.upper())
    return "_".join(words[:6]) if words else "AGENT_COMMAND_ERROR"


def _agent_error_next_commands(work_id: str, palari_id: str, mode: str) -> list[str]:
    commands = []
    if work_id and palari_id:
        commands.extend(
            [
                f"palari agent brief {work_id} --as {palari_id} --mode {mode} --json",
                f"palari agent next --as {palari_id} --mode {mode} --json",
            ]
        )
    commands.extend(["palari queue --json", "palari validate --json"])
    return commands

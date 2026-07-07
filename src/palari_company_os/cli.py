from __future__ import annotations

import contextlib
import io
import json
import os
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
    if _raw_agent_json_requested(raw_argv) or _raw_linear_json_requested(raw_argv):
        parse_errors = io.StringIO()
        try:
            with contextlib.redirect_stderr(parse_errors):
                args = parser.parse_args(argv)
        except SystemExit as exc:
            payload = (
                _linear_parse_error_payload(raw_argv, parse_errors.getvalue())
                if _raw_linear_json_requested(raw_argv)
                else _agent_parse_error_payload(raw_argv, parse_errors.getvalue())
            )
            print(
                json.dumps(
                    payload,
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
        if _linear_json_requested(args, raw_argv):
            print(json.dumps(_linear_error_payload(args, exc), indent=2, sort_keys=True))
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


def _linear_json_requested(args: Any, raw_argv: list[str]) -> bool:
    return (
        getattr(args, "command", "") == "linear"
        and getattr(args, "json", False)
        and "--json" in raw_argv
    )


def _raw_linear_json_requested(raw_argv: list[str]) -> bool:
    return "linear" in raw_argv and "--json" in raw_argv


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


def _linear_parse_error_payload(raw_argv: list[str], parser_message: str) -> dict[str, Any]:
    message = _clean_parse_error(parser_message)
    issue_key = _raw_linear_issue_key(raw_argv)
    palari_id = _raw_palari_id(raw_argv)
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": "ARGUMENT_PARSE_ERROR",
            "message": message,
            "command": " ".join(raw_argv),
        },
        "next_action": "Fix the Linear command arguments, then rerun with --json.",
        "next_allowed_commands": _linear_error_next_commands(issue_key, palari_id),
    }
    if issue_key:
        payload["error"]["linear_issue"] = issue_key
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


def _linear_error_payload(args: Any, exc: BaseException) -> dict[str, Any]:
    message = _clean_error_message(exc)
    issue_key = str(getattr(args, "issue_key", "") or "")
    outbox_id = str(getattr(args, "outbox_id", "") or "")
    palari_id = str(getattr(args, "palari_id", "") or "")
    command = " ".join(
        item
        for item in [
            "linear",
            str(getattr(args, "linear_command", "") or ""),
            issue_key or outbox_id,
        ]
        if item
    )
    next_action = str(getattr(exc, "next_action", "") or "")
    if not next_action:
        next_action = _linear_error_next_action(
            str(getattr(args, "linear_command", "") or ""),
            issue_key,
            palari_id,
        )
    payload: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": str(getattr(exc, "code", "") or _linear_error_code(message)),
            "message": message,
            "command": command,
        },
        "next_action": next_action,
        "next_allowed_commands": _linear_error_next_commands(issue_key, palari_id),
    }
    if issue_key:
        payload["error"]["linear_issue"] = issue_key
    if outbox_id:
        payload["error"]["outbox"] = outbox_id
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
    return _redact_known_secrets(message)


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
    if "claim is being updated" in lowered:
        return "CLAIM_UPDATE_IN_PROGRESS"
    if "already claimed" in lowered:
        return "CLAIM_CONFLICT"
    if "claimed by" in lowered:
        return "CLAIM_OWNER_MISMATCH"
    words = re.findall(r"[A-Za-z0-9]+", message.upper())
    return "_".join(words[:6]) if words else "AGENT_COMMAND_ERROR"


def _linear_error_code(message: str) -> str:
    lowered = message.lower()
    if "linear_api_key" in lowered or "api key" in lowered:
        return "LINEAR_API_KEY_MISSING"
    if "graphql" in lowered and "json" in lowered:
        return "LINEAR_INVALID_JSON"
    if "graphql" in lowered and "error" in lowered:
        return "LINEAR_GRAPHQL_ERROR"
    if "issue not found" in lowered:
        return "LINEAR_ISSUE_NOT_FOUND"
    if "not valid json" in lowered or "invalid palari json" in lowered:
        return "LINEAR_INVALID_JSON"
    if "missing palari block" in lowered or "unknown palari governance" in lowered:
        return "LINEAR_BLOCK_INVALID"
    if "workspace file not found" in lowered:
        return "WORKSPACE_FILE_NOT_FOUND"
    words = re.findall(r"[A-Za-z0-9]+", message.upper())
    return "_".join(words[:6]) if words else "LINEAR_COMMAND_ERROR"


def _raw_linear_issue_key(raw_argv: list[str]) -> str:
    try:
        index = raw_argv.index("linear")
    except ValueError:
        return ""
    if index + 2 >= len(raw_argv):
        return ""
    subcommand = raw_argv[index + 1]
    if subcommand in {"issue", "import", "start", "status", "post-gate", "inspect-block"}:
        value = raw_argv[index + 2]
        return "" if value.startswith("-") else value
    return ""


def _linear_error_next_action(subcommand: str, issue_key: str, palari_id: str) -> str:
    if subcommand in {"issue", "import", "start", "inspect-block"}:
        return "Run `palari linear doctor --json`, then retry after Linear access and block validation pass."
    if subcommand == "send":
        return "Check the approved outbox item, fix the drift or provider access issue, then resend with --confirm."
    if subcommand == "block-template":
        return "Fix the local Palari, goal, risk, intensity, or source references and rerun block-template."
    if issue_key and palari_id:
        return f"Run `palari linear inspect-block {issue_key} --as {palari_id} --json`."
    return "Run `palari linear doctor --json` for adapter readiness."


def _linear_error_next_commands(issue_key: str, palari_id: str) -> list[str]:
    commands = ["palari linear doctor --json", "palari linear linked --json"]
    if issue_key:
        commands.append(f"palari linear status {issue_key} --json")
        if palari_id:
            commands.append(f"palari linear inspect-block {issue_key} --as {palari_id} --json")
        else:
            commands.append(f"palari linear import {issue_key} --as PALARI-ID --json")
    return commands


def _redact_known_secrets(message: str) -> str:
    token = os.environ.get("LINEAR_API_KEY", "")
    if token:
        return message.replace(token, "[redacted]")
    return message


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

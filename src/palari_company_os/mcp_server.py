from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .agent_checks import build_agent_check
from .agent_doctor import build_agent_doctor
from .agent_finish import build_agent_finish
from .agent_handoff import build_agent_handoff
from .agent_loop import build_agent_loop
from .agent_next import build_agent_next, build_agent_next_all
from .agent_packets import build_agent_brief
from .agent_runtime import release_agent, start_agent, start_next_agent
from .models import to_plain
from .read_models import active_parallel_work, coordination_warnings, detail, queue_items
from .repo_docs import check_docs
from .workspace import Workspace, WorkspaceError, default_workspace_path


MCP_PROTOCOL_VERSION = "2025-06-18"


@dataclass(frozen=True)
class McpContext:
    workspace: str
    repo: str


def serve_mcp(
    workspace: Path | str | None = None,
    *,
    repo: Path | str = ".",
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> None:
    """Serve read-only Palari tools over MCP stdio JSON-RPC."""
    context = McpContext(
        workspace=str(workspace or default_workspace_path()),
        repo=str(repo),
    )
    incoming = input_stream or sys.stdin
    outgoing = output_stream or sys.stdout
    for line in incoming:
        raw = line.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
        except json.JSONDecodeError as exc:
            _send(outgoing, _error(None, -32700, f"Parse error: {exc}"))
            continue
        response = handle_mcp_message(request, context)
        if response is not None:
            _send(outgoing, response)


def handle_mcp_message(message: object, context: McpContext) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _error(None, -32600, "Invalid Request")
    request_id = message.get("id")
    method = message.get("method")
    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request")

    if "id" not in message:
        return None
    if method == "initialize":
        return _result(request_id, _initialize_result(message))
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": tool_definitions()})
    if method == "tools/call":
        return _tool_call_response(request_id, message.get("params"), context)
    if method == "resources/list":
        return _result(request_id, {"resources": []})
    if method == "prompts/list":
        return _result(request_id, {"prompts": []})
    return _error(request_id, -32601, f"Method not found: {method}")


def tool_definitions() -> list[dict[str, Any]]:
    return [
        _tool(
            "palari_queue",
            "Palari Queue",
            "Show work items that need attention in a Palari workspace.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "include_closed": _boolean("Include closed/completed work items."),
            },
        ),
        _tool(
            "palari_state",
            "Palari State",
            "Show compact workspace state, attention counts, parallel work, and warnings.",
            {"workspace": _string("Workspace directory or workspace.json path.")},
        ),
        _tool(
            "palari_detail",
            "Palari Work Detail",
            "Show one work item's detail, proof state, playbooks, and next actions.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
            },
            required=["work_id"],
        ),
        _tool(
            "palari_agent_next",
            "Palari Agent Next",
            "Show the next safe work candidates for one Palari or all Palaris.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "palari_id": _string("Acting Palari id. Omit with all=true for a rollup."),
                "all": _boolean("Show a rollup for all Palaris."),
                "mode": _string("Agent packet mode.", default="execute"),
                "limit": _integer("Maximum candidates to show.", default=5, minimum=1),
            },
        ),
        _tool(
            "palari_agent_brief",
            "Palari Agent Brief",
            "Compile a read-only bounded packet for one Palari and work item.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
                "session_contract": _boolean(
                    "Return the portable provider-neutral session contract."
                ),
            },
            required=["work_id", "palari_id"],
        ),
        _tool(
            "palari_agent_start",
            "Palari Agent Start",
            "Persist the bounded packet and claim an explicit or next safe work item.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "next": _boolean("Deterministically claim the next safe work item."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
                "lease_minutes": _integer("Claim lease duration in minutes.", default=30, minimum=1),
            },
            required=["palari_id"],
            read_only=False,
            idempotent=False,
        ),
        _tool(
            "palari_agent_check",
            "Palari Agent Check",
            "Check whether one work item currently satisfies its agent packet contract.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
                "changed_paths": _array("Observed changed paths to compare with write boundaries."),
                "git_diff": _boolean("Inspect current git status against packet write boundaries."),
            },
            required=["work_id", "palari_id"],
        ),
        _tool(
            "palari_agent_advance",
            "Palari Agent Advance",
            "Verify and deterministically reconcile proof to the next authority boundary.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "dry_run": _boolean("Return the exact plan without mutation."),
                "refresh_verification": _boolean(
                    "Rerun required exact verification instead of using advisory cache records."
                ),
            },
            required=["work_id", "palari_id"],
            read_only=False,
            idempotent=True,
        ),
        _tool(
            "palari_agent_finish",
            "Palari Agent Finish",
            "Summarize whether one agent may report completion or must hand off.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
            },
            required=["work_id", "palari_id"],
        ),
        _tool(
            "palari_agent_handoff",
            "Palari Agent Handoff",
            "Compile a read-only handoff packet for review, decision, or approval.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
            },
            required=["work_id", "palari_id"],
        ),
        _tool(
            "palari_agent_loop",
            "Palari Agent Loop",
            "Show the compact read-only control loop for one agent and work item.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
            },
            required=["work_id", "palari_id"],
        ),
        _tool(
            "palari_agent_doctor",
            "Palari Agent Doctor",
            "Explain the current agent loop safety state in plain language.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
                "mode": _string("Agent packet mode.", default="execute"),
            },
            required=["work_id", "palari_id"],
        ),
        _tool(
            "palari_agent_release",
            "Palari Agent Release",
            "Release one local agent claim without changing workspace records.",
            {
                "workspace": _string("Workspace directory or workspace.json path."),
                "work_id": _string("Work item id."),
                "palari_id": _string("Acting Palari id."),
            },
            required=["work_id", "palari_id"],
            read_only=False,
            idempotent=False,
        ),
        _tool(
            "palari_docs_check",
            "Palari Docs Check",
            "Check agent-ready repository documentation freshness.",
            {"repo": _string("Repository path to inspect.")},
        ),
    ]


def _tool_call_response(
    request_id: Any,
    params: object,
    context: McpContext,
) -> dict[str, Any]:
    if not isinstance(params, dict):
        return _error(request_id, -32602, "tools/call params must be an object")
    name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(name, str):
        return _error(request_id, -32602, "tools/call params.name must be a string")
    if not isinstance(arguments, dict):
        return _error(request_id, -32602, "tools/call params.arguments must be an object")
    tools = {tool["name"] for tool in tool_definitions()}
    if name not in tools:
        return _error(request_id, -32602, f"Unknown tool: {name}")
    try:
        payload = call_tool(name, arguments, context)
    except (WorkspaceError, KeyError, TypeError, ValueError) as exc:
        return _result(request_id, _tool_error_payload(str(exc)))
    return _result(request_id, _tool_success_payload(payload))


def call_tool(name: str, arguments: dict[str, Any], context: McpContext) -> dict[str, Any]:
    workspace_path = str(arguments.get("workspace") or context.workspace)
    if name == "palari_docs_check":
        return check_docs(Path(str(arguments.get("repo") or context.repo)))

    workspace = Workspace.load(workspace_path)
    if name == "palari_queue":
        items = queue_items(workspace)
        if not bool(arguments.get("include_closed", False)):
            items = [item for item in items if item.attention != "closed"]
        return {"workspace": workspace.name, "queue": to_plain(items)}
    if name == "palari_state":
        items = queue_items(workspace)
        return {
            "workspace": workspace.name,
            "counts": _workspace_counts(workspace),
            "attention": _attention_counts(items),
            "top_attention": to_plain(items[0]) if items else None,
            "queue": to_plain(items),
            "active_parallel_work": active_parallel_work(workspace),
            "coordination_warnings": coordination_warnings(workspace),
        }
    if name == "palari_detail":
        return detail(workspace, _required_string(arguments, "work_id"))
    if name == "palari_agent_next":
        mode = _optional_string(arguments, "mode", "execute")
        limit = _optional_int(arguments, "limit", 5)
        palari_id = str(arguments.get("palari_id") or "")
        if bool(arguments.get("all", False)) or not palari_id:
            return build_agent_next_all(workspace, mode, limit)
        return build_agent_next(workspace, palari_id, mode, limit)
    if name == "palari_agent_brief":
        packet = build_agent_brief(
            workspace,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
        )
        if bool(arguments.get("session_contract", False)):
            from .agent_session_contract import compile_agent_session_contract

            return compile_agent_session_contract(packet)
        return packet
    if name == "palari_agent_start":
        work_id = str(arguments.get("work_id") or "")
        start_next = bool(arguments.get("next", False))
        if bool(work_id) == start_next:
            raise ValueError("provide exactly one of work_id or next=true")
        if start_next:
            return start_next_agent(
                workspace,
                workspace_path,
                _required_string(arguments, "palari_id"),
                _optional_string(arguments, "mode", "execute"),
                lease_minutes=_optional_int(arguments, "lease_minutes", 30),
            )
        return start_agent(
            workspace,
            workspace_path,
            work_id,
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
            lease_minutes=_optional_int(arguments, "lease_minutes", 30),
        )
    if name == "palari_agent_check":
        return build_agent_check(
            workspace,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
            changed_paths=_string_list(arguments.get("changed_paths", [])),
            git_diff=bool(arguments.get("git_diff", False)),
            cwd=workspace.path,
        )
    if name == "palari_agent_advance":
        from .agent_advance import agent_advance

        return agent_advance(
            workspace,
            workspace_path,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            dry_run=bool(arguments.get("dry_run", False)),
            refresh_verification=bool(arguments.get("refresh_verification", False)),
        )
    if name == "palari_agent_finish":
        return build_agent_finish(
            workspace,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
        )
    if name == "palari_agent_handoff":
        return build_agent_handoff(
            workspace,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
        )
    if name == "palari_agent_loop":
        return build_agent_loop(
            workspace,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
        )
    if name == "palari_agent_doctor":
        return build_agent_doctor(
            workspace,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
            _optional_string(arguments, "mode", "execute"),
        )
    if name == "palari_agent_release":
        return release_agent(
            workspace,
            workspace_path,
            _required_string(arguments, "work_id"),
            _required_string(arguments, "palari_id"),
        )
    raise ValueError(f"unsupported tool: {name}")


def _initialize_result(message: dict[str, Any]) -> dict[str, Any]:
    params = message.get("params", {})
    requested = params.get("protocolVersion") if isinstance(params, dict) else ""
    protocol_version = requested if requested == MCP_PROTOCOL_VERSION else MCP_PROTOCOL_VERSION
    return {
        "protocolVersion": protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {
            "name": "palari-company-os",
            "title": "Palari Company OS",
            "version": __version__,
        },
        "instructions": (
            "Use Palari tools to claim bounded work, inspect its portable contract, "
            "check scope, and advance deterministic proof. Agent start/release only "
            "manage local runtime claims; agent advance stops before human authority."
        ),
    }


def _tool_success_payload(payload: dict[str, Any]) -> dict[str, Any]:
    plain = to_plain(payload)
    return {
        "content": [{"type": "text", "text": json.dumps(plain, indent=2, sort_keys=True)}],
        "structuredContent": plain,
        "isError": False,
    }


def _tool_error_payload(message: str) -> dict[str, Any]:
    payload = {"ok": False, "error": {"message": message}}
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}],
        "structuredContent": payload,
        "isError": True,
    }


def _tool(
    name: str,
    title: str,
    description: str,
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
    read_only: bool = True,
    destructive: bool = False,
    idempotent: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
        "annotations": {
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "idempotentHint": idempotent,
            "openWorldHint": False,
        },
    }


def _string(description: str, *, default: str | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": description}
    if default is not None:
        schema["default"] = default
    return schema


def _boolean(description: str) -> dict[str, Any]:
    return {"type": "boolean", "description": description, "default": False}


def _integer(description: str, *, default: int, minimum: int) -> dict[str, Any]:
    return {"type": "integer", "description": description, "default": default, "minimum": minimum}


def _array(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "description": description,
        "items": {"type": "string"},
        "default": [],
    }


def _required_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_string(arguments: dict[str, Any], key: str, default: str) -> str:
    value = arguments.get(key, default)
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_int(arguments: dict[str, Any], key: str, default: int) -> int:
    value = arguments.get(key, default)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return max(1, value)


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("changed_paths must be a list of strings")
    return list(value)


def _workspace_counts(workspace: Workspace) -> dict[str, int]:
    return {
        "goals": len(workspace.goals),
        "palaris": len(workspace.palaris),
        "humans": len(workspace.humans),
        "sources": len(workspace.sources),
        "workbenches": len(workspace.workbenches),
        "playbook_sources": len(workspace.playbook_sources),
        "integrations": len(workspace.integrations),
        "integration_plans": len(workspace.integration_plans),
        "integration_outbox": len(workspace.integration_outbox),
        "decisions": len(workspace.decisions),
        "work_items": len(workspace.work_items),
        "attempts": len(workspace.attempts),
        "evidence_runs": len(workspace.evidence_runs),
        "review_verdicts": len(workspace.review_verdicts),
        "human_decisions": len(workspace.human_decisions),
        "receipts": len(workspace.receipts),
        "outcomes": len(workspace.outcomes),
    }


def _attention_counts(items: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.attention] = counts.get(item.attention, 0) + 1
    return dict(sorted(counts.items()))


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _send(output_stream: TextIO, message: dict[str, Any]) -> None:
    output_stream.write(json.dumps(message, separators=(",", ":"), sort_keys=True))
    output_stream.write("\n")
    output_stream.flush()

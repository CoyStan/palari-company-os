from __future__ import annotations

import os
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .agent_runtime import start_agent
from .errors import WorkspaceError
from .history import append_history_event
from .integrations import _human_can_decide_plan, check_integration_outbox
from .linear_blocks import (
    PalariBlock,
    block_payload as _block_payload,
    default_goal as _default_goal,
    linear_block_template,
    linear_inspect_block,
    parse_palari_block,
)
from .linear_core import (
    LINEAR_INTEGRATION_ID,
    LINEAR_SECRET_REF,
    LinearAdapterError,
    LinearClient,
    LinearIssueClient,
    _short_error,
    normalize_issue,
)
from .models import Human, Integration, Proposal, WorkItem, to_plain
from .proposals import adopt_proposal
from .read_models import detail, queue_items
from .store import load_store, validate_data, write_store
from .workspace import Workspace


SUPPORTED_RUNNERS = {"codex", "claude-code", "cursor", "generic"}
LIVE_PROVIDER_COMMANDS = ["issue", "import", "start", "inspect-block", "send"]
LOCAL_ONLY_COMMANDS = [
    "status",
    "linked",
    "doctor",
    "block-template",
    "post-gate",
    "webhook serve",
    "webhook verify",
    "webhook events",
]
__all__ = [
    "LinearAdapterError",
    "LinearClient",
    "LinearIssueClient",
    "PalariBlock",
    "linear_block_template",
    "linear_doctor",
    "linear_import",
    "linear_inspect_block",
    "linear_issue",
    "linear_linked",
    "linear_post_gate",
    "linear_send",
    "linear_start",
    "linear_status",
    "normalize_issue",
    "parse_palari_block",
]


def linear_issue(issue_key: str, *, client: LinearIssueClient | None = None) -> dict[str, Any]:
    client = client or LinearClient.from_env()
    issue = client.issue(issue_key)
    return {
        "schema_version": "palari.linear_issue.v1",
        "provider": "linear",
        "issue": issue,
        "would_mutate_workspace": False,
    }


def linear_doctor(workspace_path: str) -> dict[str, Any]:
    from .linear_webhook import LINEAR_WEBHOOK_SECRET_REF, linear_webhook_event_log_summary

    workspace = Workspace.load(workspace_path)
    linear_integrations = [
        integration for integration in workspace.integrations if integration.provider == "linear"
    ]
    linked_proposals = [
        proposal for proposal in workspace.proposals if proposal.external_provider == "linear"
    ]
    linked_work = [work for work in workspace.work_items if work.external_provider == "linear"]
    return {
        "schema_version": "palari.linear_doctor.v1",
        "ok": True,
        "provider": "linear",
        "workspace": workspace.name,
        "env": {
            "linear_api_key_present": bool(os.environ.get("LINEAR_API_KEY")),
            "linear_webhook_secret_present": bool(os.environ.get("LINEAR_WEBHOOK_SECRET")),
            "secret_ref": LINEAR_SECRET_REF,
            "webhook_secret_ref": LINEAR_WEBHOOK_SECRET_REF,
            "secret_value_stored": False,
        },
        "counts": {
            "linked_proposals": len(linked_proposals),
            "linked_work_items": len(linked_work),
            "linear_integrations": len(linear_integrations),
        },
        "linear_integration": (
            {
                "id": linear_integrations[0].id,
                "enabled": linear_integrations[0].enabled,
                "mode": linear_integrations[0].mode,
                "allowed_events": linear_integrations[0].allowed_events,
                "allowed_actions": linear_integrations[0].allowed_actions,
            }
            if linear_integrations
            else None
        ),
        "supported_runners": sorted(SUPPORTED_RUNNERS),
        "webhook": {
            "event_log": linear_webhook_event_log_summary(workspace_path),
            "serve_command": "palari linear webhook serve --host 127.0.0.1 --port 0 --json",
        },
        "live_provider_commands": LIVE_PROVIDER_COMMANDS,
        "local_only_commands": LOCAL_ONLY_COMMANDS,
        "next_action": (
            "Set LINEAR_API_KEY before issue/import/start/inspect-block/send."
            if not os.environ.get("LINEAR_API_KEY")
            else "Linear environment is present; use issue/import/start or local status commands."
        ),
    }


def linear_linked(workspace_path: str) -> dict[str, Any]:
    from .linear_webhook import latest_linear_webhook_events_by_key

    workspace = Workspace.load(workspace_path)
    queue_by_id = {item.id: item for item in queue_items(workspace)}
    webhook_events = latest_linear_webhook_events_by_key(workspace_path)
    groups: dict[str, dict[str, Any]] = {}

    for proposal in workspace.proposals:
        if proposal.external_provider != "linear":
            continue
        key = proposal.external_key or proposal.external_id or proposal.id
        group = groups.setdefault(key, _empty_linked_group(key))
        group["linear_ref"] = _linear_ref_from_record(proposal)
        group["proposal"] = _proposal_ref(proposal)
        group["palari_ref"] = _proposal_palari_ref(workspace, proposal)
        group["goal_ref"] = _proposal_goal_ref(workspace, proposal)
        group["gate_summary"] = _proposal_gate_summary(proposal)
        group["pending_actions"] = _proposal_pending_actions(key, proposal)
        group["next_commands"] = _proposal_next_commands(key, proposal)
        group["link_state"] = "proposal_only"
        group["latest_webhook_event"] = webhook_events.get(key)

    for work in workspace.work_items:
        if work.external_provider != "linear":
            continue
        key = work.external_key or work.external_id or work.id
        group = groups.setdefault(key, _empty_linked_group(key))
        group["linear_ref"] = _linear_ref_from_record(work)
        item = queue_by_id.get(work.id)
        work_detail = detail(workspace, work.id)
        group["work_item"] = _work_link_ref(work)
        group["palari_ref"] = _palari_ref(workspace, work)
        group["goal_ref"] = _goal_ref(workspace, work)
        group["queue"] = _queue_ref(item)
        group["gate_summary"] = _gate_summary_from_detail(work_detail, item)
        group["integration"] = _integration_link_summary(work_detail)
        group["next_commands"] = _linear_next_commands(work.external_key or key, work, item)
        group["link_state"] = _link_state(_linear_status_from_detail(work, item, work_detail), True)
        group["latest_webhook_event"] = webhook_events.get(key)

    items = sorted(groups.values(), key=lambda item: item["linear_ref"].get("key", ""))
    return {
        "schema_version": "palari.linear_linked.v1",
        "provider": "linear",
        "workspace": workspace.name,
        "count": len(items),
        "items": items,
        "next_action": "Use `palari linear status ISSUE-KEY --json` for a focused gate view.",
    }


def linear_import(
    workspace_path: str,
    issue_key: str,
    palari_id: str,
    *,
    goal_id: str = "",
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    client = client or LinearClient.from_env()
    issue = client.issue(issue_key)
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    palari = workspace.palari(palari_id)
    if palari is None:
        raise WorkspaceError(f"palari not found: {palari_id}")

    block = parse_palari_block(issue["description"])
    proposal_id = _proposal_id(issue)
    work_id = _work_id(issue)
    proposals = _records(store.data, "proposals")
    work_items = _records(store.data, "work_items")
    proposal = _find_linear_record(proposals, proposal_id, issue)
    work = _find_linear_record(work_items, work_id, issue)

    fields = _proposal_fields_from_issue(workspace, issue, block, palari_id, goal_id)
    if proposal is None:
        before = None
        proposal = {"id": proposal_id, "created_at": _timestamp(), **fields}
        proposals.append(proposal)
        action = "created"
    else:
        before = deepcopy(proposal)
        if proposal.get("status") == "adopted":
            proposal.update(_adopted_proposal_sync_fields(fields))
        else:
            proposal.update(fields)
        action = "updated"

    if work is not None:
        _sync_work_external_fields(work, issue)
        if proposal.get("status") == "adopted":
            work["title"] = proposal["title"]

    workspace = write_store(store)
    refreshed = workspace.proposal(str(proposal["id"]))
    refreshed_work = _workspace_linear_work(workspace, issue)
    history_event = append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command="linear import",
        action=action,
        object_type="proposal",
        object_collection="proposals",
        object_id=str(proposal["id"]),
        actor=palari_id,
        before=before,
        after=to_plain(refreshed) if refreshed is not None else deepcopy(proposal),
    )
    return {
        "schema_version": "palari.linear_import.v1",
        "provider": "linear",
        "action": action,
        "workspace": workspace.name,
        "issue": issue,
        "proposal": to_plain(refreshed) if refreshed is not None else deepcopy(proposal),
        "work_item": to_plain(refreshed_work) if refreshed_work is not None else None,
        "governance": _block_payload(block),
        "history_event": history_event,
        "next_action": _import_next_action(block, str(proposal["id"]), work_id),
    }


def linear_start(
    workspace_path: str,
    issue_key: str,
    palari_id: str,
    *,
    runner: str,
    mode: str = "execute",
    adopt_by: str = "",
    goal_id: str = "",
    lease_minutes: int = 30,
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    _assert_supported_runner(runner)
    imported = linear_import(
        workspace_path,
        issue_key,
        palari_id,
        goal_id=goal_id,
        client=client,
    )
    issue = imported["issue"]
    workspace = Workspace.load(workspace_path)
    work = _workspace_linear_work(workspace, issue)
    proposal = _workspace_linear_proposal(workspace, issue)
    work_id = _work_id(issue)

    if work is None and adopt_by:
        if not imported["governance"]["valid"]:
            return _needs_adoption_payload(
                workspace,
                issue,
                proposal,
                palari_id,
                runner,
                reason="Linear issue has no valid palari governance block.",
            )
        if proposal is None:
            raise WorkspaceError(f"linear proposal not found for {issue['key']}")
        _assert_human_can_adopt(workspace, adopt_by, proposal)
        adoption = adopt_proposal(
            workspace_path,
            proposal.id,
            work_id,
            adopt_by,
            reason=f"Adopted from Linear issue {issue['key']}",
        )
        workspace = Workspace.load(workspace_path)
        work = _workspace_linear_work(workspace, issue)
        imported["adoption"] = adoption

    if work is None:
        return _needs_adoption_payload(
            workspace,
            issue,
            proposal,
            palari_id,
            runner,
            reason="No adopted Palari work item is linked to this Linear issue.",
        )

    packet = start_agent(
        workspace,
        workspace_path,
        work.id,
        palari_id,
        mode,
        lease_minutes=lease_minutes,
    )
    return {
        "schema_version": "palari.linear_start.v1",
        "ok": packet.get("status") == "ready",
        "provider": "linear",
        "runner": runner,
        "runner_note": _runner_note(runner),
        "issue": issue,
        "work_item_id": work.id,
        "import": imported,
        "agent_start": packet,
        "next_action": _runner_next_action(runner, work.id, palari_id, mode),
    }


def linear_status(workspace_path: str, issue_key: str) -> dict[str, Any]:
    from .linear_webhook import latest_linear_webhook_events_by_key

    workspace = Workspace.load(workspace_path)
    latest_webhook_event = latest_linear_webhook_events_by_key(workspace_path).get(issue_key)
    issue_stub = {"id": "", "key": issue_key, "identifier": issue_key}
    work = _workspace_linear_work(workspace, issue_stub)
    proposal = _workspace_linear_proposal(workspace, issue_stub)
    if work is None:
        link_state = "proposal_only" if proposal is not None else "not_imported"
        linear_ref = _linear_ref_from_record(proposal) if proposal is not None else {"key": issue_key}
        return {
            "schema_version": "palari.linear_status.v1",
            "provider": "linear",
            "issue_key": issue_key,
            "status": "NEEDS_HUMAN",
            "link_state": link_state,
            "linear_ref": linear_ref,
            "palari_ref": _proposal_palari_ref(workspace, proposal),
            "gate_summary": {
                "attention": "needs-human-decision",
                "evidence_state": "",
                "review_state": "",
                "receipt_state": "",
                "acceptance_state": "",
                "integration_state": "",
            },
            "pending_actions": _proposal_pending_actions(issue_key, proposal),
            "next_commands": _proposal_next_commands(issue_key, proposal),
            "latest_webhook_event": latest_webhook_event,
            "proposal": to_plain(proposal) if proposal is not None else None,
            "work_item": None,
            "next_action": (
                f"Run `palari linear import {issue_key} --as PALARI-ID --json`, then "
                "adopt the proposal before starting governed work."
            ),
        }

    item = next((candidate for candidate in queue_items(workspace) if candidate.id == work.id), None)
    work_detail = detail(workspace, work.id)
    mapped = _linear_status_from_detail(work, item, work_detail)
    link_state = _link_state(mapped, True)
    return {
        "schema_version": "palari.linear_status.v1",
        "provider": "linear",
        "issue_key": issue_key,
        "status": mapped,
        "link_state": link_state,
        "linear_ref": _linear_ref_from_record(work),
        "palari_ref": _palari_ref(workspace, work),
        "gate_summary": _gate_summary_from_detail(work_detail, item),
        "pending_actions": _pending_actions(work_detail),
        "next_commands": _linear_next_commands(issue_key, work, item),
        "latest_webhook_event": latest_webhook_event,
        "work_item": to_plain(work),
        "proposal": to_plain(proposal) if proposal is not None else None,
        "queue_item": to_plain(item) if item is not None else None,
        "detail": work_detail,
        "next_action": item.next_action if item is not None else "Inspect Palari detail.",
    }


def linear_post_gate(
    workspace_path: str,
    issue_key: str,
    *,
    event: str,
    actor: str,
    record: bool,
) -> dict[str, Any]:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    issue_stub = {"id": "", "key": issue_key, "identifier": issue_key}
    work = _workspace_linear_work(workspace, issue_stub)
    if work is None:
        raise WorkspaceError(f"no Palari work item is linked to Linear issue {issue_key}")
    integration_record, integration_before = _ensure_linear_integration_record(
        store.data,
        workspace,
        actor,
    )
    workspace = validate_data(store.data_path, store.data)
    integration = workspace.integration(str(integration_record["id"]))
    if integration is None:
        raise WorkspaceError("linear integration could not be prepared")
    _assert_linear_comment_allowed(integration, event)
    status_payload = linear_status(workspace_path, issue_key)
    body = _linear_comment_body(event, status_payload, work)
    payload_preview = _linear_comment_payload(work, body)
    source_boundary = _source_boundary(workspace, integration, work)

    if not record:
        return {
            "schema_version": "palari.linear_post_gate.v1",
            "provider": "linear",
            "recorded": False,
            "would_call_provider": False,
            "issue_key": issue_key,
            "event": event,
            "actor": actor,
            "payload_preview": payload_preview,
            "source_boundary": source_boundary,
            "next_action": "Review the preview, then rerun with --record to create an approval plan.",
        }

    plans = _records(store.data, "integration_plans")
    timestamp = _timestamp()
    plan = {
        "id": _linear_plan_id(issue_key, event, timestamp),
        "integration_id": integration.id,
        "work_item_id": work.id,
        "event": event,
        "action": "comment",
        "actor": actor,
        "status": "pending-approval",
        "payload_preview": payload_preview,
        "source_boundary": source_boundary,
        "risk": integration.risk_level,
        "approval_required": True,
        "timestamp": timestamp,
        "notes": "Linear comment preview only. No provider call was made.",
    }
    plans.append(plan)
    workspace = write_store(store)
    if integration_before is None:
        append_history_event(
            store.data_path,
            schema_version=workspace.schema_version,
            command="linear post-gate",
            action="created",
            object_type="integration",
            object_collection="integrations",
            object_id=integration.id,
            actor=actor,
            before=None,
            after=integration_record,
        )
    history_event = append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command="linear post-gate",
        action="planned",
        object_type="integration-plan",
        object_collection="integration_plans",
        object_id=str(plan["id"]),
        actor=actor,
        before=None,
        after=plan,
    )
    return {
        "schema_version": "palari.linear_post_gate.v1",
        "provider": "linear",
        "recorded": True,
        "would_call_provider": False,
        "issue_key": issue_key,
        "event": event,
        "actor": actor,
        "integration_plan": plan,
        "payload_preview": payload_preview,
        "source_boundary": source_boundary,
        "history_event": history_event,
        "next_action": (
            f"Approve with `palari integration approve {plan['id']} --by HUMAN-ID "
            "--reason REASON --json`, then enqueue before sending."
        ),
    }


def linear_send(
    workspace_path: str,
    outbox_id: str,
    *,
    human_id: str,
    confirm: bool,
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise WorkspaceError("linear send requires --confirm")
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    item = workspace.integration_outbox_item(outbox_id)
    if item is None:
        raise WorkspaceError(f"integration outbox item not found: {outbox_id}")
    plan = workspace.integration_plan(item.plan_id)
    integration = workspace.integration(item.integration_id)
    work = workspace.work_item(item.work_item_id)
    human = workspace.human(human_id)
    if plan is None or integration is None or work is None:
        raise WorkspaceError(f"integration outbox item {outbox_id} has broken references")
    if human is None:
        raise WorkspaceError(f"human not found: {human_id}")
    if integration.provider != "linear":
        raise WorkspaceError(f"integration outbox item {outbox_id} is not for Linear")
    if item.action != "comment":
        raise WorkspaceError("linear send only supports comment outbox items")
    if not _human_can_decide_plan(human, work, integration):
        raise WorkspaceError(f"human {human.id} lacks authority to send {outbox_id}")

    records = _records(store.data, "integration_outbox")
    record = _record_by_id(records, outbox_id)
    if record is None:
        raise WorkspaceError(f"integration outbox record not found: {outbox_id}")
    before = deepcopy(record)
    try:
        preflight = check_integration_outbox(workspace, outbox_id)
        if preflight["status"] != "queued-preflight-ready":
            raise WorkspaceError(f"linear send preflight failed for {outbox_id}")
        issue_id, body = _comment_payload_inputs(item.payload_preview, work=work)
        client = client or LinearClient.from_env()
        provider_response = client.create_comment(issue_id, body)
    except WorkspaceError as exc:
        if record.get("status") == "queued":
            _mark_outbox_failed(record, human, exc)
        workspace = write_store(store)
        append_history_event(
            store.data_path,
            schema_version=workspace.schema_version,
            command="linear send",
            action="failed",
            object_type="integration-outbox",
            object_collection="integration_outbox",
            object_id=outbox_id,
            actor=human.id,
            before=before,
            after=record,
        )
        raise

    record.update(
        {
            "status": "sent",
            "sent_by": human.id,
            "sent_at": _timestamp(),
            "provider_response": _comment_response(provider_response),
            "notes": "Sent to Linear through commentCreate after approved Palari outbox.",
        }
    )
    workspace = write_store(store)
    after_item = workspace.integration_outbox_item(outbox_id)
    after = to_plain(after_item) if after_item is not None else deepcopy(record)
    history_event = append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command="linear send",
        action="sent",
        object_type="integration-outbox",
        object_collection="integration_outbox",
        object_id=outbox_id,
        actor=human.id,
        before=before,
        after=after,
    )
    return {
        "schema_version": "palari.linear_send.v1",
        "ok": True,
        "provider": "linear",
        "status": "sent",
        "would_call_provider": True,
        "integration_outbox_item": after,
        "provider_response": _comment_response(provider_response),
        "history_event": history_event,
        "next_action": "Linear comment sent and provider metadata recorded.",
    }


def _proposal_fields_from_issue(
    workspace: Workspace,
    issue: dict[str, Any],
    block: PalariBlock,
    palari_id: str,
    goal_id: str,
) -> dict[str, Any]:
    fields = dict(block.fields) if block.valid else {}
    fields.setdefault("goal", goal_id or _default_goal(workspace, palari_id))
    fields.setdefault("palari", palari_id)
    if fields["palari"] != palari_id:
        raise WorkspaceError(
            f"Linear palari block targets {fields['palari']}, not command actor {palari_id}"
        )
    status = "proposed" if block.valid else "under-review"
    return {
        "title": issue["title"],
        "goal": fields["goal"],
        "palari": fields["palari"],
        "proposer": palari_id,
        "status": status,
        "summary": issue["description"],
        "scope": fields.get("scope", ""),
        "risk": fields.get("risk", "R1"),
        "intensity": fields.get("intensity", "light"),
        "allowed_resources": fields.get("allowed_resources", []),
        "allowed_sources": fields.get("allowed_sources", []),
        "allowed_actions": fields.get("allowed_actions", []),
        "output_targets": fields.get("output_targets", []),
        "forbidden_actions": fields.get("forbidden_actions", []),
        "acceptance_target": fields.get("acceptance_target", ""),
        "verification_expectations": fields.get("verification_expectations", []),
        "recommended_playbooks": fields.get("recommended_playbooks", []),
        "conflict_targets": fields.get("conflict_targets", []),
        "parallel_policy": fields.get("parallel_policy", "independent"),
        **_external_fields(issue),
    }


def _adopted_proposal_sync_fields(fields: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "title",
        "summary",
        "external_provider",
        "external_id",
        "external_key",
        "external_url",
        "external_updated_at",
    }
    return {key: deepcopy(value) for key, value in fields.items() if key in keys}


def _sync_work_external_fields(work: dict[str, Any], issue: dict[str, Any]) -> None:
    work.update(_external_fields(issue))


def _external_fields(issue: dict[str, Any]) -> dict[str, str]:
    return {
        "external_provider": "linear",
        "external_id": issue["id"],
        "external_key": issue["key"],
        "external_url": issue["url"],
        "external_updated_at": issue["updated_at"],
    }


def _needs_adoption_payload(
    workspace: Workspace,
    issue: dict[str, Any],
    proposal: Proposal | None,
    palari_id: str,
    runner: str,
    *,
    reason: str,
) -> dict[str, Any]:
    proposal_id = proposal.id if proposal is not None else _proposal_id(issue)
    work_id = _work_id(issue)
    return {
        "schema_version": "palari.linear_start.v1",
        "ok": False,
        "provider": "linear",
        "status": "needs_adoption",
        "reason": reason,
        "workspace": workspace.name,
        "runner": runner,
        "runner_note": _runner_note(runner),
        "issue": issue,
        "proposal": to_plain(proposal) if proposal is not None else None,
        "work_item": None,
        "proposal_adopt_command": (
            f"palari proposal adopt {proposal_id} --work-id {work_id} "
            "--by HUMAN-ID --json"
        ),
        "linear_start_adopt_command": (
            f"palari linear start {issue['key']} --runner {runner} --as {palari_id} "
            "--adopt-by HUMAN-ID --json"
        ),
        "next_action": "A human with authority must adopt the Linear proposal into Palari work.",
    }


def _empty_linked_group(key: str) -> dict[str, Any]:
    return {
        "linear_ref": {"key": key},
        "link_state": "proposal_only",
        "proposal": None,
        "work_item": None,
        "palari_ref": None,
        "goal_ref": None,
        "queue": None,
        "gate_summary": None,
        "integration": {
            "pending_plans": [],
            "queued_outbox": [],
            "sent_outbox": [],
        },
        "latest_webhook_event": None,
        "pending_actions": [],
        "next_commands": [],
    }


def _linear_ref_from_record(record: Any) -> dict[str, str]:
    if record is None:
        return {}
    return {
        "provider": getattr(record, "external_provider", ""),
        "id": getattr(record, "external_id", ""),
        "key": getattr(record, "external_key", ""),
        "url": getattr(record, "external_url", ""),
        "updated_at": getattr(record, "external_updated_at", ""),
    }


def _proposal_ref(proposal: Proposal) -> dict[str, str]:
    return {
        "id": proposal.id,
        "title": proposal.title,
        "status": proposal.status,
        "goal": proposal.goal,
        "palari": proposal.palari,
        "linked_work": proposal.linked_work,
    }


def _work_link_ref(work: WorkItem) -> dict[str, str]:
    return {
        "id": work.id,
        "title": work.title,
        "status": work.status,
        "risk": work.risk,
        "intensity": work.intensity,
        "goal": work.goal,
        "palari": work.palari,
    }


def _palari_ref(workspace: Workspace, work: WorkItem) -> dict[str, str]:
    palari = workspace.palari(work.palari)
    return {
        "id": work.palari,
        "name": palari.name if palari else work.palari,
        "owner_human": palari.owner_human if palari else "",
    }


def _proposal_palari_ref(workspace: Workspace, proposal: Proposal | None) -> dict[str, str] | None:
    if proposal is None:
        return None
    palari = workspace.palari(proposal.palari)
    return {
        "id": proposal.palari,
        "name": palari.name if palari else proposal.palari,
        "owner_human": palari.owner_human if palari else "",
    }


def _proposal_goal_ref(workspace: Workspace, proposal: Proposal | None) -> dict[str, str] | None:
    if proposal is None:
        return None
    goal = workspace.goal(proposal.goal)
    return {
        "id": proposal.goal,
        "title": goal.title if goal else proposal.goal,
        "status": goal.status if goal else "",
    }


def _goal_ref(workspace: Workspace, work: WorkItem) -> dict[str, str]:
    goal = workspace.goal(work.goal)
    return {
        "id": work.goal,
        "title": goal.title if goal else work.goal,
        "status": goal.status if goal else "",
    }


def _queue_ref(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        "attention": item.attention,
        "why": item.why,
        "next_action": item.next_action,
        "next_step_type": item.next_step_type,
        "next_commands": item.next_commands,
    }


def _gate_summary_from_detail(work_detail: dict[str, Any], item: Any) -> dict[str, str]:
    safety = work_detail.get("safety", {})
    return {
        "attention": item.attention if item is not None else str(work_detail.get("attention", "")),
        "evidence_state": str(safety.get("evidence_state", "")),
        "review_state": str(safety.get("review_state", "")),
        "receipt_state": str(safety.get("receipt_state", "")),
        "acceptance_state": str(safety.get("acceptance_state", "")),
        "integration_state": str(safety.get("integration_state", "")),
        "approval_progress": str(safety.get("approval_progress", "")),
    }


def _proposal_gate_summary(proposal: Proposal) -> dict[str, str]:
    return {
        "attention": "needs-human-decision",
        "proposal_state": proposal.status,
        "evidence_state": "",
        "review_state": "",
        "receipt_state": "",
        "acceptance_state": "",
        "integration_state": "",
        "approval_progress": "",
    }


def _integration_link_summary(work_detail: dict[str, Any]) -> dict[str, list[str]]:
    plans = work_detail.get("integration_plans", [])
    outbox = work_detail.get("integration_outbox", [])
    return {
        "pending_plans": [
            plan["id"] for plan in plans if plan.get("status") == "pending-approval"
        ],
        "queued_outbox": [
            item["id"] for item in outbox if item.get("status") == "queued"
        ],
        "sent_outbox": [
            item["id"] for item in outbox if item.get("status") == "sent"
        ],
    }


def _pending_actions(work_detail: dict[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for decision in work_detail.get("linked_decisions", []):
        if decision.get("status") == "open":
            actions.append({"kind": "decision", "id": decision["id"], "status": "open"})
    for plan in work_detail.get("integration_plans", []):
        if plan.get("status") == "pending-approval":
            actions.append({"kind": "integration_plan", "id": plan["id"], "status": "pending-approval"})
    for item in work_detail.get("integration_outbox", []):
        if item.get("status") == "queued":
            actions.append({"kind": "integration_outbox", "id": item["id"], "status": "queued"})
    return actions


def _proposal_pending_actions(issue_key: str, proposal: Proposal | None) -> list[dict[str, str]]:
    if proposal is None:
        return [{"kind": "import", "id": issue_key, "status": "needed"}]
    if proposal.status != "adopted":
        return [{"kind": "proposal_adoption", "id": proposal.id, "status": proposal.status}]
    return []


def _linear_next_commands(issue_key: str, work: WorkItem, item: Any) -> list[str]:
    commands = [f"palari linear status {issue_key} --json"]
    if item is not None:
        commands.extend(item.next_commands[:2])
    commands.append(f"palari detail {work.id} --json")
    return commands


def _proposal_next_commands(issue_key: str, proposal: Proposal | None) -> list[str]:
    if proposal is None:
        return [f"palari linear import {issue_key} --as PALARI-ID --json"]
    return [
        f"palari proposal adopt {proposal.id} --work-id WORK-LINEAR-{_issue_suffix({'key': issue_key})} --by HUMAN-ID --json",
        f"palari linear start {issue_key} --as {proposal.palari} --adopt-by HUMAN-ID --json",
    ]


def _link_state(status: str, work_linked: bool) -> str:
    if status == "ACCEPTED":
        return "accepted"
    return "work_linked" if work_linked else "proposal_only"


def _assert_human_can_adopt(workspace: Workspace, human_id: str, proposal: Proposal) -> None:
    human = workspace.human(human_id)
    if human is None:
        raise WorkspaceError(f"adopt-by must name a human with authority, not {human_id}")
    palari = workspace.palari(proposal.palari)
    if human.authority_level == "admin":
        return
    if palari is not None and palari.owner_human == human.id:
        return
    if {"product", "operations", "policy", "merge"} & set(human.approval_capabilities):
        return
    raise WorkspaceError(f"human {human.id} lacks authority to adopt {proposal.id}")


def _assert_supported_runner(runner: str) -> None:
    if runner not in SUPPORTED_RUNNERS:
        expected = ", ".join(sorted(SUPPORTED_RUNNERS))
        raise WorkspaceError(f"unsupported Linear runner {runner!r}; expected one of: {expected}")


def _runner_note(runner: str) -> str:
    return {
        "codex": "Emit this governed packet for Codex; Palari does not launch Codex.",
        "claude-code": "Emit this governed packet for Claude Code; Palari does not launch it.",
        "cursor": "Emit this governed packet for Cursor; Palari does not launch Cursor.",
        "generic": "Emit this governed packet for any compatible harness.",
    }[runner]


def _runner_next_action(runner: str, work_id: str, palari_id: str, mode: str) -> str:
    return (
        f"Use the emitted packet with {runner}; renew with "
        f"`palari agent start {work_id} --as {palari_id} --mode {mode} --json` if needed."
    )


def _import_next_action(block: PalariBlock, proposal_id: str, work_id: str) -> str:
    if block.valid:
        return (
            f"Review and adopt with `palari proposal adopt {proposal_id} "
            f"--work-id {work_id} --by HUMAN-ID --json`."
        )
    if block.present:
        return (
            f"Fix the Linear palari block ({block.error}) or have a human adopt the "
            f"title-only proposal {proposal_id} deliberately."
        )
    return (
        f"Add a valid fenced palari JSON block or adopt proposal {proposal_id} "
        f"as {work_id} after human review."
    )


def _workspace_linear_work(workspace: Workspace, issue: dict[str, Any]) -> WorkItem | None:
    for work in workspace.work_items:
        if _matches_linear_record(work, issue):
            return work
    expected = _work_id(issue)
    return workspace.work_item(expected)


def _workspace_linear_proposal(workspace: Workspace, issue: dict[str, Any]) -> Proposal | None:
    for proposal in workspace.proposals:
        if _matches_linear_record(proposal, issue):
            return proposal
    expected = _proposal_id(issue)
    return workspace.proposal(expected)


def _matches_linear_record(record: Any, issue: dict[str, Any]) -> bool:
    if getattr(record, "external_provider", "") != "linear":
        return False
    external_id = getattr(record, "external_id", "")
    external_key = getattr(record, "external_key", "")
    return bool(
        (issue.get("id") and external_id == issue.get("id"))
        or (issue.get("key") and external_key == issue.get("key"))
    )


def _find_linear_record(
    records: list[dict[str, Any]],
    default_id: str,
    issue: dict[str, Any],
) -> dict[str, Any] | None:
    for record in records:
        if str(record.get("id", "")) == default_id:
            return record
        if record.get("external_provider") != "linear":
            continue
        if issue.get("id") and record.get("external_id") == issue["id"]:
            return record
        if issue.get("key") and record.get("external_key") == issue["key"]:
            return record
    return None


def _proposal_id(issue: dict[str, Any]) -> str:
    return f"PROP-LINEAR-{_issue_suffix(issue)}"


def _work_id(issue: dict[str, Any]) -> str:
    return f"WORK-LINEAR-{_issue_suffix(issue)}"


def _issue_suffix(issue: dict[str, Any]) -> str:
    key = str(issue.get("key") or issue.get("identifier") or issue.get("id") or "ISSUE")
    safe = re.sub(r"[^A-Za-z0-9]+", "-", key.upper()).strip("-")
    return safe or "ISSUE"


def _linear_status_from_detail(
    work: WorkItem,
    item: Any,
    work_detail: dict[str, Any],
) -> str:
    safety = work_detail.get("safety", {})
    if work.status in {"completed", "closed", "done"} or safety.get("acceptance_state") == "accepted":
        return "ACCEPTED"
    if item is not None and item.attention in {"blocked", "changes-requested"}:
        return "BLOCKED"
    if item is not None and item.attention == "needs-human-decision":
        return "NEEDS_HUMAN"
    if safety.get("evidence_state") in {"missing", "stale", "failed"}:
        return "NEEDS_EVIDENCE"
    if item is not None and item.attention in {"needs-evidence", "needs-review"}:
        return "NEEDS_EVIDENCE"
    if item is not None and item.attention in {"ready-for-ai-work", "ready-to-integrate"}:
        return "READY"
    return "NEEDS_HUMAN"


def _ensure_linear_integration_record(
    data: dict[str, Any],
    workspace: Workspace,
    actor: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    integrations = _records(data, "integrations")
    existing = _record_by_id(integrations, LINEAR_INTEGRATION_ID, required=False)
    if existing is not None:
        return existing, deepcopy(existing)
    owner_human = _owner_human_for_actor(workspace, actor)
    record = {
        "id": LINEAR_INTEGRATION_ID,
        "provider": "linear",
        "label": "Linear issue comments",
        "mode": "dry_run",
        "owner_human": owner_human,
        "enabled": True,
        "allowed_events": ["work_blocked", "review_requested", "work_completed"],
        "allowed_actions": ["comment"],
        "secret_ref": LINEAR_SECRET_REF,
        "risk_level": "standard",
        "source_ids": [],
        "notes": "Created by palari linear post-gate for approved comment outbox sends.",
    }
    integrations.append(record)
    return record, None


def _owner_human_for_actor(workspace: Workspace, actor: str) -> str:
    if workspace.human(actor) is not None:
        return actor
    palari = workspace.palari(actor)
    if palari is not None and palari.owner_human:
        return palari.owner_human
    admin = next((human.id for human in workspace.humans if human.authority_level == "admin"), "")
    return admin or (workspace.humans[0].id if workspace.humans else "")


def _assert_linear_comment_allowed(integration: Integration, event: str) -> None:
    if integration.provider != "linear":
        raise WorkspaceError(f"integration {integration.id} is not a Linear integration")
    if not integration.enabled:
        raise WorkspaceError(f"integration {integration.id} is disabled")
    if event not in integration.allowed_events:
        raise WorkspaceError(f"integration {integration.id} does not allow event {event}")
    if "comment" not in integration.allowed_actions:
        raise WorkspaceError(f"integration {integration.id} does not allow Linear comments")


def _linear_comment_body(event: str, status_payload: dict[str, Any], work: WorkItem) -> str:
    return "\n".join(
        [
            f"Palari event: {event}",
            f"Palari status: {status_payload['status']}",
            f"Work: {work.id} - {work.title}",
            f"Risk: {work.risk}; intensity: {work.intensity}",
            f"Next action: {status_payload.get('next_action', 'Inspect Palari detail.')}",
            "",
            "This comment was planned by Palari and requires approved outbox send.",
        ]
    )


def _linear_comment_payload(work: WorkItem, body: str) -> dict[str, Any]:
    if not work.external_id:
        raise WorkspaceError(f"work {work.id} is missing Linear external_id")
    return {
        "provider": "linear",
        "operation": "commentCreate",
        "secret_ref": LINEAR_SECRET_REF,
        "issue_id": work.external_id,
        "issue_key": work.external_key,
        "issue_url": work.external_url,
        "json": {
            "issueId": work.external_id,
            "body": body,
        },
    }


def _source_boundary(
    workspace: Workspace,
    integration: Integration,
    work: WorkItem,
) -> dict[str, Any]:
    integration_sources = set(integration.source_ids)
    work_sources = set(work.allowed_sources)
    shared = sorted(integration_sources & work_sources)
    return {
        "integration_sources": sorted(integration_sources),
        "work_allowed_sources": sorted(work_sources),
        "shared_sources": shared,
        "shared_source_labels": [
            source.label
            for source_id in shared
            for source in [workspace.source(source_id)]
            if source is not None
        ],
    }


def _comment_payload_inputs(payload_preview: dict[str, Any], *, work: WorkItem) -> tuple[str, str]:
    if payload_preview.get("provider") != "linear":
        raise WorkspaceError("linear send payload is not for Linear")
    if payload_preview.get("operation") != "commentCreate":
        raise WorkspaceError("linear send payload is not a commentCreate operation")
    if payload_preview.get("secret_ref") not in {"", LINEAR_SECRET_REF}:
        raise WorkspaceError("linear send payload secret_ref drifted from the approved Linear env ref")
    body = payload_preview.get("json", {})
    if not isinstance(body, dict):
        raise WorkspaceError("linear send payload json must be an object")
    if set(body) != {"issueId", "body"}:
        raise WorkspaceError("linear send payload json shape drifted from the approved comment shape")
    issue_id = _string(body.get("issueId"))
    comment_body = _string(body.get("body"))
    if not issue_id or not comment_body:
        raise WorkspaceError("linear send payload requires issueId and body")
    if payload_preview.get("issue_id") != issue_id:
        raise WorkspaceError("linear send payload issue_id drifted from json.issueId")
    if issue_id != work.external_id:
        raise WorkspaceError("linear send payload issueId drifted from linked work item")
    if payload_preview.get("issue_key") != work.external_key:
        raise WorkspaceError("linear send payload issue_key drifted from linked work item")
    return issue_id, comment_body


def _mark_outbox_failed(record: dict[str, Any], human: Human, exc: WorkspaceError) -> None:
    record.update(
        {
            "status": "failed",
            "sent_by": human.id,
            "failed_at": _timestamp(),
            "failure_reason": _short_error(str(exc)),
        }
    )


def _comment_response(response: dict[str, Any]) -> dict[str, str]:
    return {
        "id": _string(response.get("id")),
        "url": _string(response.get("url")),
        "createdAt": _string(response.get("createdAt")),
    }


def _records(data: dict[str, Any], collection: str) -> list[dict[str, Any]]:
    records = data.setdefault(collection, [])
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise WorkspaceError(f"{collection} must be a list of objects")
    return records


def _record_by_id(
    records: list[dict[str, Any]],
    record_id: str,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    for record in records:
        if str(record.get("id", "")) == record_id:
            return record
    if required:
        raise WorkspaceError(f"record not found: {record_id}")
    return None


def _linear_plan_id(issue_key: str, event: str, timestamp: str) -> str:
    compact = timestamp.replace("-", "").replace(":", "").replace("Z", "Z")
    safe_issue = re.sub(r"[^A-Za-z0-9]+", "-", issue_key.upper()).strip("-")
    safe_event = re.sub(r"[^A-Za-z0-9]+", "-", event.upper()).strip("-")
    return f"PLAN-LINEAR-{safe_issue}-{safe_event}-{compact}-{uuid.uuid4().hex[:8].upper()}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""

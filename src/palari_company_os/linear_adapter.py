from __future__ import annotations

import os
import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .agent_runtime import start_agent
from .errors import WorkspaceError
from .governance_journal import MutationMetadata
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
from .transition_checks import assert_transition_allowed
from .workspace import Workspace


SUPPORTED_RUNNERS = {"codex", "claude-code", "cursor", "generic"}
LIVE_PROVIDER_COMMANDS = [
    "connect",
    "issue",
    "issues",
    "import",
    "start",
    "inspect-block",
    "sync",
    "send",
]
LOCAL_ONLY_COMMANDS = [
    "status",
    "linked",
    "doctor",
    "block-template",
    "post-gate",
    "push",
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
    "linear_connect",
    "linear_doctor",
    "linear_import",
    "linear_inspect_block",
    "linear_issue",
    "linear_issues",
    "linear_linked",
    "linear_post_gate",
    "linear_push",
    "linear_send",
    "linear_start",
    "linear_status",
    "linear_sync",
    "normalize_issue",
    "parse_palari_block",
]

LINEAR_STATUS_EVENT_STATE_TYPES = {
    "work_started": "started",
    "review_requested": "started",
    "work_completed": "completed",
    "work_blocked": "",
}
LINEAR_INTEGRATION_ACTIONS = ["comment", "update_issue", "create_issue"]
LINEAR_INTEGRATION_EVENTS = [
    "work_started",
    "work_blocked",
    "review_requested",
    "work_completed",
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


def linear_connect(
    workspace_path: str,
    *,
    actor: str,
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    """Verify Linear credentials and prepare the governed integration record.

    Without a working LINEAR_API_KEY this still prepares the local record and
    returns a structured blocker instead of an error, so setup can finish
    locally and the missing credential stays a visible human step.
    """
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    actor = actor.strip() or _owner_human_for_actor(workspace, "")
    integration_record, integration_before = _ensure_linear_integration_record(
        store.data,
        workspace,
        actor,
    )
    upgraded = _upgrade_linear_integration_record(integration_record)
    workspace = validate_data(store.data_path, store.data)
    if integration_before is None or upgraded:
        workspace = write_store(
            store,
            metadata=_journal_metadata(
                "linear connect",
                actor,
                "created" if integration_before is None else "updated",
                (("integration", "integrations", str(integration_record["id"])),),
            ),
        )

    connection: dict[str, Any] = {"verified": False}
    blocker: dict[str, str] | None = None
    try:
        live = client or LinearClient.from_env()
        connection = dict(live.viewer())
        connection["verified"] = True
    except LinearAdapterError as exc:
        blocker = {
            "code": exc.code,
            "message": str(exc),
            "next_action": exc.next_action
            or "Create a personal API key at https://linear.app/settings/api and export LINEAR_API_KEY.",
        }

    doctor = linear_doctor(workspace_path)
    return {
        "schema_version": "palari.linear_connect.v1",
        "ok": blocker is None,
        "provider": "linear",
        "workspace": workspace.name,
        "connection": connection,
        "blocker": blocker,
        "integration": {
            "id": integration_record["id"],
            "enabled": integration_record.get("enabled", False),
            "allowed_events": integration_record.get("allowed_events", []),
            "allowed_actions": integration_record.get("allowed_actions", []),
            "secret_ref": integration_record.get("secret_ref", ""),
        },
        "env": doctor["env"],
        "next_commands": _connect_next_commands(connection, blocker),
    }


def linear_issues(
    workspace_path: str,
    *,
    team_key: str = "",
    limit: int = 25,
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    """List open Linear issues for one team, annotated with local link state."""
    live = client or LinearClient.from_env()
    resolved_team = team_key.strip()
    if not resolved_team:
        overview = live.viewer()
        teams = overview.get("teams", [])
        if len(teams) == 1:
            resolved_team = str(teams[0].get("key", ""))
        else:
            keys = ", ".join(str(team.get("key", "")) for team in teams) or "none visible"
            raise WorkspaceError(
                f"pass --team to pick a Linear team (visible teams: {keys})"
            )
    issues = live.team_issues(resolved_team, first=limit)
    workspace = Workspace.load(workspace_path)
    annotated = []
    for issue in issues:
        block = parse_palari_block(issue.get("description", ""))
        work = _workspace_linear_work(workspace, issue)
        proposal = _workspace_linear_proposal(workspace, issue)
        annotated.append(
            {
                "key": issue.get("key", ""),
                "title": issue.get("title", ""),
                "state": issue.get("state", {}),
                "url": issue.get("url", ""),
                "updated_at": issue.get("updated_at", ""),
                "has_palari_block": block.present,
                "linked_work_item": work.id if work else "",
                "linked_proposal": proposal.id if proposal else "",
                "next_command": _issue_list_next_command(issue, block.present, work, proposal),
            }
        )
    return {
        "schema_version": "palari.linear_issues.v1",
        "ok": True,
        "provider": "linear",
        "team": resolved_team,
        "count": len(annotated),
        "issues": annotated,
        "next_action": (
            "Import an issue with a palari block, or add one with "
            "`palari linear block-template`."
        ),
    }


def linear_sync(
    workspace_path: str,
    issue_key: str,
    *,
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    """Pull one Linear issue and refresh linked local records without webhooks.

    Applies the same non-destructive updates as a verified webhook event:
    external refs always, title/summary only for pre-adoption proposals.
    """
    from .linear_webhook import _sync_issue_event

    live = client or LinearClient.from_env()
    issue = live.issue(issue_key)
    flat_issue = {
        "id": issue.get("id", ""),
        "key": issue.get("key", ""),
        "identifier": issue.get("identifier", ""),
        "title": issue.get("title", ""),
        "description": issue.get("description", ""),
        "url": issue.get("url", ""),
        "updated_at": issue.get("updated_at", ""),
        "archived_at": "",
    }
    sync_result = _sync_issue_event(workspace_path, flat_issue, "update")
    return {
        "schema_version": "palari.linear_sync.v1",
        "ok": True,
        "provider": "linear",
        "issue_key": issue.get("key", issue_key),
        "issue_state": issue.get("state", {}),
        "sync": sync_result,
        "next_action": (
            f"palari linear status {issue.get('key', issue_key)} --json"
            if sync_result.get("proposal_ids") or sync_result.get("work_item_ids")
            else "Issue is not linked locally; import it with `palari linear import`."
        ),
    }


def linear_push(
    workspace_path: str,
    work_id: str,
    *,
    actor: str,
    team_key: str = "",
    record: bool,
) -> dict[str, Any]:
    """Plan a governed Linear issue creation for a local work item.

    The plan is an offline preview like every other Linear write: a human
    approves and enqueues it, and `linear send` performs the issueCreate and
    links the created issue back to the work item. The issue description
    embeds the work item's palari block so the round trip through
    `linear inspect-block` and `linear import` stays valid.
    """
    from .linear_blocks import _fenced_palari_json

    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work item not found: {work_id}")
    if work.external_provider == "linear" and (work.external_id or work.external_key):
        raise WorkspaceError(
            f"work item {work_id} is already linked to Linear issue "
            f"{work.external_key or work.external_id}; use linear post-gate or linear sync"
        )
    integration_record, integration_before = _ensure_linear_integration_record(
        store.data,
        workspace,
        actor,
    )
    integration_upgraded = _upgrade_linear_integration_record(integration_record)
    workspace = validate_data(store.data_path, store.data)
    integration = workspace.integration(str(integration_record["id"]))
    if integration is None:
        raise WorkspaceError("linear integration could not be prepared")
    _assert_linear_action_allowed(integration, "work_started", "create_issue")

    block_fields: dict[str, Any] = {
        "goal": work.goal,
        "palari": work.palari,
        "risk": work.risk,
        "intensity": work.intensity,
        "scope": work.scope,
        "acceptance_target": work.acceptance_target,
        "parallel_policy": work.parallel_policy,
    }
    for key, values in (
        ("allowed_resources", work.allowed_resources),
        ("allowed_sources", work.allowed_sources),
        ("output_targets", work.output_targets),
        ("forbidden_actions", work.forbidden_actions),
        ("verification_expectations", work.verification_expectations),
        ("conflict_targets", work.conflict_targets),
    ):
        if values:
            block_fields[key] = list(values)
    description = "\n\n".join(
        part
        for part in (
            work.scope or work.title,
            f"Acceptance: {work.acceptance_target}" if work.acceptance_target else "",
            f"Palari work item: {work.id}",
            _fenced_palari_json(block_fields),
        )
        if part
    )
    payload_preview = {
        "provider": "linear",
        "operation": "issueCreate",
        "action": "create_issue",
        "work_item_id": work.id,
        "team_key": team_key.strip(),
        "title": work.title,
        "description": description,
        "note": (
            "Team id is resolved live at send time; an empty team_key uses the "
            "only visible team."
        ),
    }
    source_boundary = _source_boundary(workspace, integration, work)

    if not record:
        return {
            "schema_version": "palari.linear_push.v1",
            "provider": "linear",
            "recorded": False,
            "would_call_provider": False,
            "work_item_id": work.id,
            "actor": actor,
            "payload_preview": payload_preview,
            "source_boundary": source_boundary,
            "next_action": "Review the preview, then rerun with --record to create an approval plan.",
        }

    plans = _records(store.data, "integration_plans")
    timestamp = _timestamp()
    plan = {
        "id": _linear_plan_id(work.id, "create_issue", timestamp),
        "integration_id": integration.id,
        "work_item_id": work.id,
        "event": "work_started",
        "action": "create_issue",
        "actor": actor,
        "status": "pending-approval",
        "payload_preview": payload_preview,
        "source_boundary": source_boundary,
        "risk": integration.risk_level,
        "approval_required": True,
        "timestamp": timestamp,
        "notes": "Linear issue creation preview only. No provider call was made.",
    }
    plans.append(plan)
    objects = [("integration-plan", "integration_plans", str(plan["id"]))]
    if integration_before is None or integration_upgraded:
        objects.insert(0, ("integration", "integrations", integration.id))
    workspace = write_store(
        store,
        metadata=_journal_metadata(
            "linear push",
            actor,
            "planned",
            tuple(objects),
        ),
    )
    return {
        "schema_version": "palari.linear_push.v1",
        "provider": "linear",
        "recorded": True,
        "would_call_provider": False,
        "work_item_id": work.id,
        "actor": actor,
        "integration_plan": plan,
        "payload_preview": payload_preview,
        "source_boundary": source_boundary,
        "next_action": (
            f"Approve with `palari integration approve {plan['id']} --by HUMAN-ID "
            "--reason REASON --json`, then enqueue before sending."
        ),
    }


def _connect_next_commands(
    connection: dict[str, Any],
    blocker: dict[str, str] | None,
) -> list[str]:
    if blocker is not None:
        return [
            "export LINEAR_API_KEY=...  # create at https://linear.app/settings/api",
            "palari linear connect --json",
        ]
    commands = []
    teams = connection.get("teams", [])
    team_hint = f" --team {teams[0]['key']}" if len(teams) == 1 and teams[0].get("key") else ""
    commands.append(f"palari linear issues{team_hint} --json")
    commands.append("palari linear import ISSUE-KEY --as PALARI-ID --json")
    commands.append("export LINEAR_WEBHOOK_SECRET=...  # optional inbound sync")
    return commands


def _issue_list_next_command(
    issue: dict[str, Any],
    has_block: bool,
    work: WorkItem | None,
    proposal: Proposal | None,
) -> str:
    key = issue.get("key", "")
    if work is not None:
        return f"palari linear status {key} --json"
    if proposal is not None:
        return f"palari linear start {key} --runner claude-code --as PALARI-ID --adopt-by HUMAN-ID --json"
    if has_block:
        return f"palari linear import {key} --as PALARI-ID --json"
    return "palari linear block-template --json  # paste the block into the issue first"


def _upgrade_linear_integration_record(record: dict[str, Any]) -> bool:
    """Bring an existing Linear integration record up to the full action set."""
    changed = False
    actions = record.get("allowed_actions")
    if not isinstance(actions, list):
        actions = []
    for action in LINEAR_INTEGRATION_ACTIONS:
        if action not in actions:
            actions.append(action)
            changed = True
    if changed or record.get("allowed_actions") != actions:
        record["allowed_actions"] = actions
    events = record.get("allowed_events")
    if not isinstance(events, list):
        events = []
    events_changed = False
    for event in LINEAR_INTEGRATION_EVENTS:
        if event not in events:
            events.append(event)
            events_changed = True
    if events_changed:
        record["allowed_events"] = events
        changed = True
    return changed


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
        proposal = {"id": proposal_id, "created_at": _timestamp(), **fields}
        proposals.append(proposal)
        action = "created"
    else:
        if proposal.get("status") == "adopted":
            proposal.update(_adopted_proposal_sync_fields(fields))
        else:
            proposal.update(fields)
        action = "updated"

    if work is not None:
        _sync_work_external_fields(work, issue)
        if proposal.get("status") == "adopted":
            work["title"] = proposal["title"]

    objects = [("proposal", "proposals", str(proposal["id"]))]
    if work is not None:
        objects.append(("work", "work_items", str(work["id"])))
    workspace = write_store(
        store,
        metadata=_journal_metadata(
            "linear import",
            palari_id,
            action,
            tuple(objects),
        ),
    )
    refreshed = workspace.proposal(str(proposal["id"]))
    refreshed_work = _workspace_linear_work(workspace, issue)
    return {
        "schema_version": "palari.linear_import.v1",
        "provider": "linear",
        "action": action,
        "workspace": workspace.name,
        "issue": issue,
        "proposal": to_plain(refreshed) if refreshed is not None else deepcopy(proposal),
        "work_item": to_plain(refreshed_work) if refreshed_work is not None else None,
        "governance": _block_payload(block),
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
    action: str = "comment",
    target_state: str = "",
) -> dict[str, Any]:
    if action not in {"comment", "update_issue"}:
        raise WorkspaceError(f"linear post-gate action must be comment or update_issue, not {action}")
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
    integration_upgraded = False
    if action == "update_issue":
        integration_upgraded = _upgrade_linear_integration_record(integration_record)
    workspace = validate_data(store.data_path, store.data)
    integration = workspace.integration(str(integration_record["id"]))
    if integration is None:
        raise WorkspaceError("linear integration could not be prepared")
    _assert_linear_action_allowed(integration, event, action)
    status_payload = linear_status(workspace_path, issue_key)
    if action == "update_issue":
        payload_preview = _linear_status_update_payload(work, event, target_state)
    else:
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
        "action": action,
        "actor": actor,
        "status": "pending-approval",
        "payload_preview": payload_preview,
        "source_boundary": source_boundary,
        "risk": integration.risk_level,
        "approval_required": True,
        "timestamp": timestamp,
        "notes": (
            "Linear status update preview only. No provider call was made."
            if action == "update_issue"
            else "Linear comment preview only. No provider call was made."
        ),
    }
    plans.append(plan)
    objects = [("integration-plan", "integration_plans", str(plan["id"]))]
    if integration_before is None or integration_upgraded:
        objects.insert(0, ("integration", "integrations", integration.id))
    workspace = write_store(
        store,
        metadata=_journal_metadata(
            "linear post-gate",
            actor,
            "planned",
            tuple(objects),
        ),
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
    if item.action not in {"comment", "update_issue", "create_issue"}:
        raise WorkspaceError(
            "linear send only supports comment, update_issue, and create_issue outbox items"
        )
    if not _human_can_decide_plan(human, work, integration):
        raise WorkspaceError(f"human {human.id} lacks authority to send {outbox_id}")

    records = _records(store.data, "integration_outbox")
    record = _record_by_id(records, outbox_id)
    if record is None:
        raise WorkspaceError(f"integration outbox record not found: {outbox_id}")
    try:
        assert_transition_allowed(
            workspace,
            "integration_send",
            outbox_id,
            actor=human.id,
            context={"provider": "linear", "action": item.action},
        )
        preflight = check_integration_outbox(workspace, outbox_id)
        if preflight["status"] != "queued-preflight-ready":
            raise WorkspaceError(f"linear send preflight failed for {outbox_id}")
        client = client or LinearClient.from_env()
        if item.action == "update_issue":
            provider_response = _execute_status_update(client, item.payload_preview, work=work)
        elif item.action == "create_issue":
            provider_response = _execute_issue_create(client, item.payload_preview)
        else:
            issue_id, body = _comment_payload_inputs(item.payload_preview, work=work)
            provider_response = client.create_comment(issue_id, body)
    except WorkspaceError as exc:
        if record.get("status") == "queued":
            _mark_outbox_failed(record, human, exc)
            write_store(
                store,
                metadata=_journal_metadata(
                    "linear send",
                    human.id,
                    "failed",
                    (("integration-outbox", "integration_outbox", outbox_id),),
                    reason=str(exc),
                ),
            )
        raise

    record.update(
        {
            "status": "sent",
            "sent_by": human.id,
            "sent_at": _timestamp(),
            "provider_response": _provider_response_summary(item.action, provider_response),
            "notes": (
                {
                    "update_issue": "Sent to Linear through issueUpdate after approved Palari outbox.",
                    "create_issue": "Sent to Linear through issueCreate after approved Palari outbox.",
                }.get(
                    item.action,
                    "Sent to Linear through commentCreate after approved Palari outbox.",
                )
            ),
        }
    )
    linked_work_event = None
    if item.action == "create_issue":
        linked_work_event = _link_work_to_created_issue(
            store.data, work.id, provider_response
        )
    objects = [("integration-outbox", "integration_outbox", outbox_id)]
    if linked_work_event is not None:
        objects.append(("work", "work_items", work.id))
    workspace = write_store(
        store,
        metadata=_journal_metadata(
            "linear send",
            human.id,
            "sent",
            tuple(objects),
        ),
    )
    after_item = workspace.integration_outbox_item(outbox_id)
    after = to_plain(after_item) if after_item is not None else deepcopy(record)
    return {
        "schema_version": "palari.linear_send.v1",
        "ok": True,
        "provider": "linear",
        "status": "sent",
        "would_call_provider": True,
        "integration_outbox_item": after,
        "provider_response": _provider_response_summary(item.action, provider_response),
        "linked_work_item": linked_work_event,
        "next_action": _send_next_action(item.action, provider_response),
    }


def _send_next_action(action: str, provider_response: dict[str, Any]) -> str:
    if action == "create_issue":
        key = _string(provider_response.get("key")) or _string(
            provider_response.get("identifier")
        )
        return (
            f"Linear issue {key} created and linked; track it with "
            f"`palari linear status {key} --json`."
        )
    if action == "update_issue":
        return "Linear issue state updated and provider metadata recorded."
    return "Linear comment sent and provider metadata recorded."


def _link_work_to_created_issue(
    data: dict[str, Any],
    work_id: str,
    issue: dict[str, Any],
) -> dict[str, Any] | None:
    """Store the created issue's refs on the work item inside the same write."""
    work_records = _records(data, "work_items")
    record = _record_by_id(work_records, work_id, required=False)
    if record is None:
        return None
    record.update(_external_fields(issue))
    return {
        "work_item_id": work_id,
        "external_key": record.get("external_key", ""),
        "external_url": record.get("external_url", ""),
    }


def _execute_issue_create(client: LinearIssueClient, payload_preview: Any) -> dict[str, Any]:
    """Resolve the team live and create the Linear issue."""
    preview = payload_preview if isinstance(payload_preview, dict) else {}
    title = _string(preview.get("title"))
    description = _string(preview.get("description"))
    team_key = _string(preview.get("team_key"))
    if not title:
        raise WorkspaceError("issue creation payload is missing a title")
    overview = client.viewer()
    teams = overview.get("teams", []) if isinstance(overview, dict) else []
    if team_key:
        matches = [team for team in teams if _string(team.get("key")) == team_key]
        if not matches:
            keys = ", ".join(_string(team.get("key")) for team in teams) or "none visible"
            raise WorkspaceError(
                f"Linear team {team_key!r} is not visible to this key (visible: {keys})"
            )
        team_id = _string(matches[0].get("id"))
    elif len(teams) == 1:
        team_id = _string(teams[0].get("id"))
    else:
        keys = ", ".join(_string(team.get("key")) for team in teams) or "none visible"
        raise WorkspaceError(
            f"pass --team when planning the push (visible teams: {keys})"
        )
    if not team_id:
        raise WorkspaceError("Linear team id could not be resolved")
    return client.create_issue(team_id, title, description)


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


def _assert_linear_action_allowed(integration: Integration, event: str, action: str) -> None:
    if integration.provider != "linear":
        raise WorkspaceError(f"integration {integration.id} is not a Linear integration")
    if not integration.enabled:
        raise WorkspaceError(f"integration {integration.id} is disabled")
    if event not in integration.allowed_events:
        raise WorkspaceError(f"integration {integration.id} does not allow event {event}")
    if action not in integration.allowed_actions:
        raise WorkspaceError(f"integration {integration.id} does not allow Linear action {action}")


def _linear_status_update_payload(work, event: str, target_state: str) -> dict:
    """Build the offline status-update preview stored on the plan.

    The target is stored by name and state type; the concrete Linear state id
    is resolved live at send time so plans stay offline and reviewable.
    """
    default_type = LINEAR_STATUS_EVENT_STATE_TYPES.get(event, "")
    if not target_state.strip() and not default_type:
        raise WorkspaceError(
            f"event {event} has no default Linear state; pass --to-state STATE-NAME"
        )
    issue_key = work.external_key or work.external_id
    team_key = issue_key.split("-", 1)[0] if "-" in issue_key else ""
    if not work.external_id:
        raise WorkspaceError(
            f"work item {work.id} has no Linear issue id; run `palari linear sync {issue_key} --json` first"
        )
    if not team_key:
        raise WorkspaceError(
            f"work item {work.id} has no team-qualified Linear key; run `palari linear sync` first"
        )
    return {
        "provider": "linear",
        "operation": "issueUpdate",
        "action": "update_issue",
        "issue_id": work.external_id,
        "issue_key": issue_key,
        "issue_url": work.external_url,
        "team_key": team_key,
        "target_state_name": target_state.strip(),
        "target_state_type": default_type,
        "note": "State id is resolved live at send time from the team workflow states.",
    }


def _execute_status_update(client, payload_preview: dict, *, work) -> dict:
    """Resolve the target workflow state live and apply the issueUpdate."""
    preview = payload_preview if isinstance(payload_preview, dict) else {}
    issue_id = _string(preview.get("issue_id")) or work.external_id
    team_key = _string(preview.get("team_key"))
    target_name = _string(preview.get("target_state_name"))
    target_type = _string(preview.get("target_state_type"))
    if not issue_id or not team_key:
        raise WorkspaceError("status update payload is missing issue_id or team_key")
    states = client.team_states(team_key)
    state = _resolve_workflow_state(states, target_name, target_type)
    return client.update_issue_state(issue_id, state["id"])


def _resolve_workflow_state(states: list, target_name: str, target_type: str) -> dict:
    named = [
        state
        for state in states
        if target_name and _string(state.get("name")).lower() == target_name.lower()
    ]
    if named:
        return named[0]
    if target_name:
        available = ", ".join(_string(state.get("name")) for state in states) or "none"
        raise WorkspaceError(
            f"Linear team has no workflow state named {target_name!r} (available: {available})"
        )
    typed = [state for state in states if _string(state.get("type")) == target_type]
    if typed:
        return typed[0]
    raise WorkspaceError(
        f"Linear team has no workflow state of type {target_type!r}; "
        "pass --to-state STATE-NAME when planning the update"
    )


def _provider_response_summary(action: str, response: dict) -> dict:
    if action == "create_issue":
        raw_state = response.get("state")
        state = raw_state if isinstance(raw_state, dict) else {}
        return {
            "id": _string(response.get("id")),
            "key": _string(response.get("key")) or _string(response.get("identifier")),
            "url": _string(response.get("url")),
            "state_name": _string(state.get("name")),
        }
    if action == "update_issue":
        raw_state = response.get("state")
        state = raw_state if isinstance(raw_state, dict) else {}
        return {
            "id": _string(response.get("id")),
            "url": _string(response.get("url")),
            "state_name": _string(state.get("name")),
            "state_type": _string(state.get("type")),
        }
    return _comment_response(response)


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


def _journal_metadata(
    command: str,
    actor: str,
    action: str,
    objects: tuple[tuple[str, str, str], ...],
    *,
    reason: str = "",
) -> MutationMetadata:
    return MutationMetadata(
        command=command,
        actor=actor or "local-operator",
        action=action,
        timestamp=_timestamp(),
        objects=tuple(
            {"type": kind, "collection": collection, "id": object_id}
            for kind, collection, object_id in objects
        ),
        reason=reason,
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""

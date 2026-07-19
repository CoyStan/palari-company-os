from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from .governance_journal import journal_file_path
from .workspace import Workspace


def build_data_map(workspace: Workspace) -> dict[str, Any]:
    """Return a compact read-only map of where Palari workspace data lives."""
    data_path = workspace.path / "workspace.json"
    journal_path = journal_file_path(data_path)
    try:
        journal_file = journal_path.relative_to(workspace.path).as_posix()
    except ValueError:
        journal_file = journal_path.name
    source_usage = _source_usage(workspace)
    providers = _providers(workspace)
    integration_statuses = Counter(plan.status for plan in workspace.integration_plans)
    outbox_statuses = Counter(item.status for item in workspace.integration_outbox)

    return {
        "workspace": {
            "name": workspace.name,
            "schema_version": workspace.schema_version,
        },
        "storage": {
            "workspace_file": "workspace.json",
            "journal_file": journal_file,
            "journal_enabled": journal_path.exists(),
            "collections": _collection_counts(workspace),
            "workspace_stores": [
                "declared goals, humans, Palaris, sources, workbenches, work items",
                "attempts, evidence, reviews, human decisions, receipts, outcomes",
                "dry-run integrations, integration plans, and integration outbox items",
            ],
            "palari_dir_stores": [
                "replayable, tamper-evident governance journal",
            ],
            "cache_index_status": "none",
            "split_collection_support": "workspace-relative collection_files are merged at load time when declared",
        },
        "external_systems": providers,
        "sources": [
            _source_record(source, source_usage)
            for source in sorted(workspace.sources, key=lambda item: item.id)
        ],
        "integrations": [
            _integration_record(integration)
            for integration in sorted(workspace.integrations, key=lambda item: item.id)
        ],
        "integration_activity": {
            "plans_by_status": dict(sorted(integration_statuses.items())),
            "outbox_by_status": dict(sorted(outbox_statuses.items())),
            "live_provider_calls": "disabled",
            "secret_reads": "disabled",
        },
        "memory": {
            "rule": "Palari memory_sources reference selected source records; durable memory engines are not implemented.",
            "palari_memory_sources": [
                _palari_memory_record(palari, workspace)
                for palari in sorted(workspace.palaris, key=lambda item: item.id)
            ],
            "approved_memory_records": [],
            "memory_provider_adapters": "not implemented",
        },
        "not_stored": [
            "raw provider tokens or secrets",
            "live Slack/GitHub/Jira/email responses",
            "Google Drive files or OAuth tokens",
            "vector indexes or external memory caches",
            "provider execution logs beyond explicit workspace records",
            "autonomous approvals, merges, pushes, or deploys",
        ],
    }


def _collection_counts(workspace: Workspace) -> dict[str, int]:
    return {
        "goals": len(workspace.goals),
        "humans": len(workspace.humans),
        "palaris": len(workspace.palaris),
        "sources": len(workspace.sources),
        "workbenches": len(workspace.workbenches),
        "playbook_sources": len(workspace.playbook_sources),
        "integrations": len(workspace.integrations),
        "integration_plans": len(workspace.integration_plans),
        "integration_outbox": len(workspace.integration_outbox),
        "work_items": len(workspace.work_items),
        "attempts": len(workspace.attempts),
        "evidence_runs": len(workspace.evidence_runs),
        "review_verdicts": len(workspace.review_verdicts),
        "human_decisions": len(workspace.human_decisions),
        "receipts": len(workspace.receipts),
        "decisions": len(workspace.decisions),
        "outcomes": len(workspace.outcomes),
    }


def _providers(workspace: Workspace) -> list[dict[str, Any]]:
    roles: dict[str, set[str]] = defaultdict(set)
    for source in workspace.sources:
        roles[source.provider or "unspecified"].add("source")
    for integration in workspace.integrations:
        roles[integration.provider or "unspecified"].add("integration")
    return [
        {
            "provider": provider,
            "declared_by": sorted(declared_by),
            "live_execution": "disabled",
        }
        for provider, declared_by in sorted(roles.items())
    ]


def _source_usage(workspace: Workspace) -> dict[str, dict[str, list[str]]]:
    usage: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {
            "work_items": [],
            "workbenches": [],
            "memory_for_palaris": [],
            "integrations": [],
        }
    )
    for work in workspace.work_items:
        for source_id in work.allowed_sources:
            usage[source_id]["work_items"].append(work.id)
    for workbench in workspace.workbenches:
        for source_id in workbench.source_ids:
            usage[source_id]["workbenches"].append(workbench.id)
    for palari in workspace.palaris:
        for source_id in palari.memory_sources:
            usage[source_id]["memory_for_palaris"].append(palari.id)
    for integration in workspace.integrations:
        for source_id in integration.source_ids:
            usage[source_id]["integrations"].append(integration.id)
    return usage


def _source_record(source: Any, usage: dict[str, dict[str, list[str]]]) -> dict[str, Any]:
    record_usage = usage[source.id]
    return {
        "id": source.id,
        "label": source.label,
        "kind": source.kind,
        "provider": source.provider,
        "uri": source.uri,
        "external_id": source.external_id,
        "access_mode": source.access_mode,
        "selected": source.selected,
        "owner_human": source.owner_human,
        "allowed_palaris": source.allowed_palaris,
        "data_class": source.data_class,
        "authority": source.authority,
        "steward_human": source.steward_human,
        "freshness_sla": source.freshness_sla,
        "redaction_required": source.redaction_required,
        "last_seen_revision": source.last_seen_revision,
        "last_read_at": source.last_read_at,
        "used_by_work_items": sorted(record_usage["work_items"]),
        "used_by_workbenches": sorted(record_usage["workbenches"]),
        "memory_for_palaris": sorted(record_usage["memory_for_palaris"]),
        "used_by_integrations": sorted(record_usage["integrations"]),
    }


def _integration_record(integration: Any) -> dict[str, Any]:
    return {
        "id": integration.id,
        "provider": integration.provider,
        "label": integration.label,
        "mode": integration.mode,
        "enabled": integration.enabled,
        "owner_human": integration.owner_human,
        "allowed_events": integration.allowed_events,
        "allowed_actions": integration.allowed_actions,
        "source_ids": integration.source_ids,
        "risk_level": integration.risk_level,
        "secret_ref": _secret_ref_status(integration.secret_ref),
        "live_execution": "disabled",
    }


def _palari_memory_record(palari: Any, workspace: Workspace) -> dict[str, Any]:
    sources_by_id = {source.id: source for source in workspace.sources}
    return {
        "palari_id": palari.id,
        "palari_name": palari.name,
        "source_ids": list(palari.memory_sources),
        "sources": [
            {
                "id": source_id,
                "label": sources_by_id[source_id].label,
                "provider": sources_by_id[source_id].provider,
            }
            for source_id in palari.memory_sources
        ],
    }


def _secret_ref_status(secret_ref: str) -> str:
    if not secret_ref:
        return "none"
    return "env_reference"


def format_data_map(payload: dict[str, Any]) -> list[str]:
    lines = [f"Palari Data Map: {payload['workspace']['name']}"]
    storage = payload["storage"]
    counts = storage["collections"]
    lines.append("")
    lines.append("Storage")
    lines.append(f"  workspace: {storage['workspace_file']} (schema v{payload['workspace']['schema_version']})")
    journal_state = "enabled" if storage["journal_enabled"] else "not enabled"
    lines.append(f"  journal: {storage['journal_file']} ({journal_state})")
    lines.append(f"  collections: {counts['work_items']} work, {counts['sources']} sources, {counts['integrations']} integrations, {counts['receipts']} receipts")
    lines.append(f"  cache/indexes: {storage['cache_index_status']}")
    lines.append("")
    lines.append("External Systems")
    if payload["external_systems"]:
        for provider in payload["external_systems"]:
            roles = ", ".join(provider["declared_by"])
            lines.append(f"  {provider['provider']}: {roles}; live execution {provider['live_execution']}")
    else:
        lines.append("  none declared")
    lines.append("")
    lines.append("Sources")
    if payload["sources"]:
        for source in payload["sources"]:
            allowed = _join_or_none(source["allowed_palaris"])
            memory = _join_or_none(source["memory_for_palaris"])
            lines.append(
                f"  {source['id']}: {source['label']} "
                f"[{source['provider']}/{source['kind']}/{source['access_mode']}]"
            )
            lines.append(f"    allowed Palaris: {allowed}; memory for: {memory}")
            readiness = _source_readiness_summary(source)
            if readiness:
                lines.append(f"    readiness: {readiness}")
    else:
        lines.append("  none declared")
    lines.append("")
    lines.append("Integrations")
    if payload["integrations"]:
        for integration in payload["integrations"]:
            state = "enabled" if integration["enabled"] else "disabled"
            actions = _join_or_none(integration["allowed_actions"])
            lines.append(
                f"  {integration['id']}: {integration['provider']} "
                f"[{integration['mode']}, {state}, actions: {actions}]"
            )
            lines.append(
                f"    secret: {integration['secret_ref']}; "
                f"live execution: {integration['live_execution']}"
            )
    else:
        lines.append("  none declared")
    lines.append("")
    lines.append("Memory")
    lines.append(f"  rule: {payload['memory']['rule']}")
    for memory in payload["memory"]["palari_memory_sources"]:
        lines.append(
            f"  {memory['palari_id']}: {_join_or_none(memory['source_ids'])}"
        )
    lines.append("")
    lines.append("Not Stored")
    for item in payload["not_stored"]:
        lines.append(f"  - {item}")
    return lines


def _join_or_none(values: Iterable[str]) -> str:
    values = list(values)
    return ", ".join(values) if values else "none"


def _source_readiness_summary(source: dict[str, Any]) -> str:
    parts = []
    if source.get("data_class"):
        parts.append(f"data={source['data_class']}")
    if source.get("authority"):
        parts.append(f"authority={source['authority']}")
    if source.get("steward_human"):
        parts.append(f"steward={source['steward_human']}")
    if source.get("freshness_sla"):
        parts.append(f"freshness={source['freshness_sla']}")
    if source.get("redaction_required"):
        parts.append("redaction required")
    return "; ".join(parts)

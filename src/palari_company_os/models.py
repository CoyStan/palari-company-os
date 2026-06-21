from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, TypeVar


Record = dict[str, Any]
T = TypeVar("T")


def _string(record: Record, key: str, default: str = "") -> str:
    value = record.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _strings(record: Record, key: str) -> list[str]:
    value = record.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{key} must be a list of strings")
    return list(value)


def _integer(record: Record, key: str, default: int = 0) -> int:
    value = record.get(key, default)
    if value is None:
        return default
    if not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    return value


def _boolean(record: Record, key: str, default: bool = False) -> bool:
    value = record.get(key, default)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise TypeError(f"{key} must be a boolean")
    return value


def _records(record: Record, key: str) -> list[Record]:
    value = record.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError(f"{key} must be a list of objects")
    return list(value)


def _require_id(record: Record) -> str:
    identifier = _string(record, "id")
    if not identifier:
        raise ValueError("record is missing id")
    return identifier


@dataclass(frozen=True)
class Goal:
    id: str
    title: str
    owner: str = ""
    status: str = "active"
    priority: str = "normal"
    success_criteria: list[str] = field(default_factory=list)
    linked_palaris: list[str] = field(default_factory=list)
    linked_work: list[str] = field(default_factory=list)
    linked_decisions: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: Record) -> "Goal":
        return cls(
            id=_require_id(record),
            title=_string(record, "title"),
            owner=_string(record, "owner"),
            status=_string(record, "status", "active"),
            priority=_string(record, "priority", "normal"),
            success_criteria=_strings(record, "success_criteria"),
            linked_palaris=_strings(record, "linked_palaris"),
            linked_work=_strings(record, "linked_work"),
            linked_decisions=_strings(record, "linked_decisions"),
        )


@dataclass(frozen=True)
class Palari:
    id: str
    name: str
    role: str
    scope: str = ""
    allowed_inputs: list[str] = field(default_factory=list)
    forbidden_inputs: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    memory_sources: list[str] = field(default_factory=list)
    default_worker: str = ""
    owner_human: str = ""
    linked_goals: list[str] = field(default_factory=list)
    active_work: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: Record) -> "Palari":
        return cls(
            id=_require_id(record),
            name=_string(record, "name"),
            role=_string(record, "role"),
            scope=_string(record, "scope"),
            allowed_inputs=_strings(record, "allowed_inputs"),
            forbidden_inputs=_strings(record, "forbidden_inputs"),
            forbidden_actions=_strings(record, "forbidden_actions"),
            standards=_strings(record, "standards"),
            memory_sources=_strings(record, "memory_sources"),
            default_worker=_string(record, "default_worker"),
            owner_human=_string(record, "owner_human"),
            linked_goals=_strings(record, "linked_goals"),
            active_work=_strings(record, "active_work"),
            outcomes=_strings(record, "outcomes"),
        )


@dataclass(frozen=True)
class Human:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    role: str = ""
    authority_level: str = "standard"
    approval_capabilities: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    ownership_areas: list[str] = field(default_factory=list)
    availability: str = ""
    capacity_signal: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Human":
        return cls(
            id=_require_id(record),
            name=_string(record, "name"),
            aliases=_strings(record, "aliases"),
            role=_string(record, "role"),
            authority_level=_string(record, "authority_level", "standard"),
            approval_capabilities=_strings(record, "approval_capabilities"),
            skills=_strings(record, "skills"),
            ownership_areas=_strings(record, "ownership_areas"),
            availability=_string(record, "availability"),
            capacity_signal=_string(record, "capacity_signal"),
        )


@dataclass(frozen=True)
class Workbench:
    id: str
    label: str
    summary: str = ""
    parent_workbench_id: str = ""
    goal_ids: list[str] = field(default_factory=list)
    palari_ids: list[str] = field(default_factory=list)
    human_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    output_target_ids: list[str] = field(default_factory=list)
    status: str = "active"

    @classmethod
    def from_record(cls, record: Record) -> "Workbench":
        return cls(
            id=_require_id(record),
            label=_string(record, "label"),
            summary=_string(record, "summary"),
            parent_workbench_id=_string(record, "parent_workbench_id"),
            goal_ids=_strings(record, "goal_ids"),
            palari_ids=_strings(record, "palari_ids"),
            human_ids=_strings(record, "human_ids"),
            source_ids=_strings(record, "source_ids"),
            output_target_ids=_strings(record, "output_target_ids"),
            status=_string(record, "status", "active"),
        )


@dataclass(frozen=True)
class Decision:
    id: str
    question: str
    status: str = "open"
    context: str = ""
    options: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    recommendation: str = ""
    safe_default: str = ""
    required_human: str = ""
    required_role: str = ""
    due_date: str = ""
    linked_goal: str = ""
    linked_work: str = ""
    linked_palari: str = ""
    result: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Decision":
        return cls(
            id=_require_id(record),
            question=_string(record, "question"),
            status=_string(record, "status", "open"),
            context=_string(record, "context"),
            options=_strings(record, "options"),
            tradeoffs=_strings(record, "tradeoffs"),
            recommendation=_string(record, "recommendation"),
            safe_default=_string(record, "safe_default"),
            required_human=_string(record, "required_human"),
            required_role=_string(record, "required_role"),
            due_date=_string(record, "due_date"),
            linked_goal=_string(record, "linked_goal"),
            linked_work=_string(record, "linked_work"),
            linked_palari=_string(record, "linked_palari"),
            result=_string(record, "result"),
        )


@dataclass(frozen=True)
class WorkItem:
    id: str
    title: str
    goal: str
    palari: str
    workbench_id: str = ""
    parent_work_item_id: str = ""
    dependency_ids: list[str] = field(default_factory=list)
    risk: str = "R1"
    intensity: str = "light"
    status: str = "proposed"
    scope: str = ""
    allowed_resources: list[str] = field(default_factory=list)
    allowed_sources: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    output_targets: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    acceptance_target: str = ""
    verification_expectations: list[str] = field(default_factory=list)
    current_attempt: str = ""
    required_approval_count: int = 1
    required_approval_capability: str = ""
    recommended_playbooks: list[str] = field(default_factory=list)
    conflict_targets: list[str] = field(default_factory=list)
    parallel_policy: str = "independent"

    @classmethod
    def from_record(cls, record: Record) -> "WorkItem":
        return cls(
            id=_require_id(record),
            title=_string(record, "title"),
            goal=_string(record, "goal"),
            palari=_string(record, "palari"),
            workbench_id=_string(record, "workbench_id"),
            parent_work_item_id=_string(record, "parent_work_item_id"),
            dependency_ids=_strings(record, "dependency_ids"),
            risk=_string(record, "risk", "R1"),
            intensity=_string(record, "intensity", "light"),
            status=_string(record, "status", "proposed"),
            scope=_string(record, "scope"),
            allowed_resources=_strings(record, "allowed_resources"),
            allowed_sources=_strings(record, "allowed_sources"),
            allowed_actions=_strings(record, "allowed_actions"),
            output_targets=_strings(record, "output_targets"),
            forbidden_actions=_strings(record, "forbidden_actions"),
            acceptance_target=_string(record, "acceptance_target"),
            verification_expectations=_strings(record, "verification_expectations"),
            current_attempt=_string(record, "current_attempt"),
            required_approval_count=_integer(record, "required_approval_count", 1),
            required_approval_capability=_string(record, "required_approval_capability"),
            recommended_playbooks=_strings(record, "recommended_playbooks"),
            conflict_targets=_strings(record, "conflict_targets"),
            parallel_policy=_string(record, "parallel_policy", "independent"),
        )


@dataclass(frozen=True)
class PlaybookSource:
    id: str
    label: str
    provider: str = ""
    uri: str = ""
    ref: str = ""
    license: str = ""
    enabled: bool = True
    included_playbooks: list[str] = field(default_factory=list)
    install_hint: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "PlaybookSource":
        return cls(
            id=_require_id(record),
            label=_string(record, "label"),
            provider=_string(record, "provider"),
            uri=_string(record, "uri"),
            ref=_string(record, "ref"),
            license=_string(record, "license"),
            enabled=_boolean(record, "enabled", True),
            included_playbooks=_strings(record, "included_playbooks"),
            install_hint=_string(record, "install_hint"),
        )


@dataclass(frozen=True)
class Attempt:
    id: str
    work_item_id: str
    actor: str
    status: str = "active"
    branch: str = ""
    workspace_path: str = ""
    model_or_worker: str = ""
    commits: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    cleanliness: str = ""
    result: str = ""
    started_at: str = ""
    updated_at: str = ""
    output_targets: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: Record) -> "Attempt":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            actor=_string(record, "actor"),
            status=_string(record, "status", "active"),
            branch=_string(record, "branch"),
            workspace_path=_string(record, "workspace_path"),
            model_or_worker=_string(record, "model_or_worker"),
            commits=_strings(record, "commits"),
            changed_files=_strings(record, "changed_files"),
            cleanliness=_string(record, "cleanliness"),
            result=_string(record, "result"),
            started_at=_string(record, "started_at"),
            updated_at=_string(record, "updated_at"),
            output_targets=_strings(record, "output_targets"),
        )


@dataclass(frozen=True)
class Source:
    id: str
    label: str
    kind: str = ""
    provider: str = ""
    uri: str = ""
    external_id: str = ""
    access_mode: str = ""
    selected: bool = False
    owner_human: str = ""
    allowed_palaris: list[str] = field(default_factory=list)
    last_seen_revision: str = ""
    last_read_at: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Source":
        return cls(
            id=_require_id(record),
            label=_string(record, "label"),
            kind=_string(record, "kind"),
            provider=_string(record, "provider"),
            uri=_string(record, "uri"),
            external_id=_string(record, "external_id"),
            access_mode=_string(record, "access_mode"),
            selected=_boolean(record, "selected"),
            owner_human=_string(record, "owner_human"),
            allowed_palaris=_strings(record, "allowed_palaris"),
            last_seen_revision=_string(record, "last_seen_revision"),
            last_read_at=_string(record, "last_read_at"),
        )


@dataclass(frozen=True)
class EvidenceRun:
    id: str
    work_item_id: str
    attempt_id: str
    head_sha: str
    status: str
    base_ref: str = ""
    commands: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    summary: str = ""
    freshness: str = ""
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "EvidenceRun":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            attempt_id=_string(record, "attempt_id"),
            head_sha=_string(record, "head_sha"),
            status=_string(record, "status"),
            base_ref=_string(record, "base_ref"),
            commands=_strings(record, "commands"),
            artifacts=_strings(record, "artifacts"),
            summary=_string(record, "summary"),
            freshness=_string(record, "freshness"),
            timestamp=_string(record, "timestamp"),
        )


@dataclass(frozen=True)
class ReviewVerdict:
    id: str
    work_item_id: str
    reviewed_head: str
    reviewer: str
    verdict: str
    findings: list[Record] = field(default_factory=list)
    checks_inspected: list[str] = field(default_factory=list)
    residual_risks: list[str] = field(default_factory=list)
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "ReviewVerdict":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            reviewed_head=_string(record, "reviewed_head"),
            reviewer=_string(record, "reviewer"),
            verdict=_string(record, "verdict"),
            findings=_records(record, "findings"),
            checks_inspected=_strings(record, "checks_inspected"),
            residual_risks=_strings(record, "residual_risks"),
            timestamp=_string(record, "timestamp"),
        )


@dataclass(frozen=True)
class HumanDecision:
    id: str
    work_item_id: str
    human_id: str
    reviewed_head: str
    decision: str
    status: str = "recorded"
    acceptance_mode: str = ""
    quorum_status: str = ""
    evidence_reference: str = ""
    review_reference: str = ""
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "HumanDecision":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            human_id=_string(record, "human_id"),
            reviewed_head=_string(record, "reviewed_head"),
            decision=_string(record, "decision"),
            status=_string(record, "status", "recorded"),
            acceptance_mode=_string(record, "acceptance_mode"),
            quorum_status=_string(record, "quorum_status"),
            evidence_reference=_string(record, "evidence_reference"),
            review_reference=_string(record, "review_reference"),
            timestamp=_string(record, "timestamp"),
        )


@dataclass(frozen=True)
class Receipt:
    id: str
    work_item_id: str
    attempt_id: str
    actor: str
    sources_used: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    outputs_created: list[str] = field(default_factory=list)
    external_writes: list[str] = field(default_factory=list)
    not_done: list[str] = field(default_factory=list)
    undo_refs: list[str] = field(default_factory=list)
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Receipt":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            attempt_id=_string(record, "attempt_id"),
            actor=_string(record, "actor"),
            sources_used=_strings(record, "sources_used"),
            actions_taken=_strings(record, "actions_taken"),
            outputs_created=_strings(record, "outputs_created"),
            external_writes=_strings(record, "external_writes"),
            not_done=_strings(record, "not_done"),
            undo_refs=_strings(record, "undo_refs"),
            timestamp=_string(record, "timestamp"),
        )


@dataclass(frozen=True)
class Outcome:
    id: str
    work_item_id: str
    summary: str
    status: str = "captured"
    what_happened: str = ""
    what_changed: str = ""
    useful: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    follow_up_needed: list[str] = field(default_factory=list)
    model_worker_notes: list[str] = field(default_factory=list)
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Outcome":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            summary=_string(record, "summary"),
            status=_string(record, "status", "captured"),
            what_happened=_string(record, "what_happened"),
            what_changed=_string(record, "what_changed"),
            useful=_strings(record, "useful"),
            failed=_strings(record, "failed"),
            follow_up_needed=_strings(record, "follow_up_needed"),
            model_worker_notes=_strings(record, "model_worker_notes"),
            timestamp=_string(record, "timestamp"),
        )


def to_plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    return value

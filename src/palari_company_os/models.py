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
        )


@dataclass(frozen=True)
class Palari:
    id: str
    name: str
    role: str
    scope: str = ""
    allowed_inputs: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    standards: list[str] = field(default_factory=list)
    memory_sources: list[str] = field(default_factory=list)
    owner_human: str = ""
    linked_goals: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: Record) -> "Palari":
        return cls(
            id=_require_id(record),
            name=_string(record, "name"),
            role=_string(record, "role"),
            scope=_string(record, "scope"),
            allowed_inputs=_strings(record, "allowed_inputs"),
            forbidden_actions=_strings(record, "forbidden_actions"),
            standards=_strings(record, "standards"),
            memory_sources=_strings(record, "memory_sources"),
            owner_human=_string(record, "owner_human"),
            linked_goals=_strings(record, "linked_goals"),
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
        )


@dataclass(frozen=True)
class Decision:
    id: str
    question: str
    status: str = "open"
    context: str = ""
    options: list[str] = field(default_factory=list)
    recommendation: str = ""
    safe_default: str = ""
    required_human: str = ""
    linked_work: str = ""
    result: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Decision":
        return cls(
            id=_require_id(record),
            question=_string(record, "question"),
            status=_string(record, "status", "open"),
            context=_string(record, "context"),
            options=_strings(record, "options"),
            recommendation=_string(record, "recommendation"),
            safe_default=_string(record, "safe_default"),
            required_human=_string(record, "required_human"),
            linked_work=_string(record, "linked_work"),
            result=_string(record, "result"),
        )


@dataclass(frozen=True)
class WorkItem:
    id: str
    title: str
    goal: str
    palari: str
    risk: str = "R1"
    intensity: str = "light"
    status: str = "proposed"
    scope: str = ""
    allowed_resources: list[str] = field(default_factory=list)
    forbidden_actions: list[str] = field(default_factory=list)
    acceptance_target: str = ""
    verification_expectations: list[str] = field(default_factory=list)

    @classmethod
    def from_record(cls, record: Record) -> "WorkItem":
        return cls(
            id=_require_id(record),
            title=_string(record, "title"),
            goal=_string(record, "goal"),
            palari=_string(record, "palari"),
            risk=_string(record, "risk", "R1"),
            intensity=_string(record, "intensity", "light"),
            status=_string(record, "status", "proposed"),
            scope=_string(record, "scope"),
            allowed_resources=_strings(record, "allowed_resources"),
            forbidden_actions=_strings(record, "forbidden_actions"),
            acceptance_target=_string(record, "acceptance_target"),
            verification_expectations=_strings(record, "verification_expectations"),
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
    started_at: str = ""

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
            started_at=_string(record, "started_at"),
        )


@dataclass(frozen=True)
class EvidenceRun:
    id: str
    work_item_id: str
    attempt_id: str
    head_sha: str
    status: str
    commands: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    summary: str = ""
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "EvidenceRun":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            attempt_id=_string(record, "attempt_id"),
            head_sha=_string(record, "head_sha"),
            status=_string(record, "status"),
            commands=_strings(record, "commands"),
            artifacts=_strings(record, "artifacts"),
            summary=_string(record, "summary"),
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
            evidence_reference=_string(record, "evidence_reference"),
            review_reference=_string(record, "review_reference"),
            timestamp=_string(record, "timestamp"),
        )


@dataclass(frozen=True)
class Outcome:
    id: str
    work_item_id: str
    summary: str
    status: str = "captured"
    useful: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    follow_up_needed: list[str] = field(default_factory=list)
    timestamp: str = ""

    @classmethod
    def from_record(cls, record: Record) -> "Outcome":
        return cls(
            id=_require_id(record),
            work_item_id=_string(record, "work_item_id"),
            summary=_string(record, "summary"),
            status=_string(record, "status", "captured"),
            useful=_strings(record, "useful"),
            failed=_strings(record, "failed"),
            follow_up_needed=_strings(record, "follow_up_needed"),
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


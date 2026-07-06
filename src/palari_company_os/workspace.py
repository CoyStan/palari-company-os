from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Iterable, TypeVar

from .errors import WorkspaceError
from .models import (
    AcceptanceRecord,
    Attempt,
    AuthorityProfile,
    Capability,
    Decision,
    EvidenceRun,
    Goal,
    Human,
    HumanDecision,
    Integration,
    IntegrationOutboxItem,
    IntegrationPlan,
    Outcome,
    Palari,
    PlaybookSource,
    Proposal,
    Receipt,
    ReviewVerdict,
    Source,
    Workbench,
    WorkItem,
)
from .validation import (
    COLLECTION_FILE_KEYS,
    validate_raw_contract,
    validate_workspace_contract,
)


CURRENT_SCHEMA_VERSION = 1

T = TypeVar("T")


@dataclass(frozen=True)
class Workspace:
    path: Path
    schema_version: int
    name: str
    goals: list[Goal]
    palaris: list[Palari]
    humans: list[Human]
    sources: list[Source]
    workbenches: list[Workbench]
    playbook_sources: list[PlaybookSource]
    capabilities: list[Capability]
    authority_profiles: list[AuthorityProfile]
    integrations: list[Integration]
    integration_plans: list[IntegrationPlan]
    integration_outbox: list[IntegrationOutboxItem]
    decisions: list[Decision]
    proposals: list[Proposal]
    work_items: list[WorkItem]
    attempts: list[Attempt]
    evidence_runs: list[EvidenceRun]
    review_verdicts: list[ReviewVerdict]
    human_decisions: list[HumanDecision]
    acceptance_records: list[AcceptanceRecord]
    receipts: list[Receipt]
    outcomes: list[Outcome]
    _goals_by_id: dict[str, Goal] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _palaris_by_id: dict[str, Palari] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _humans_by_id: dict[str, Human] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _sources_by_id: dict[str, Source] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _integrations_by_id: dict[str, Integration] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _integration_plans_by_id: dict[str, IntegrationPlan] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _integration_outbox_by_id: dict[str, IntegrationOutboxItem] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _capabilities_by_id: dict[str, Capability] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _proposals_by_id: dict[str, Proposal] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _work_items_by_id: dict[str, WorkItem] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )
    _workbenches_by_id: dict[str, Workbench] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    @classmethod
    def load(cls, path: Path | str) -> "Workspace":
        workspace_path = Path(path).expanduser().resolve()
        data_path = workspace_path / "workspace.json" if workspace_path.is_dir() else workspace_path
        if not data_path.exists():
            raise WorkspaceError(f"workspace file not found: {data_path}")

        return cls.from_file(data_path)

    @classmethod
    def from_file(cls, data_path: Path | str) -> "Workspace":
        data_path = Path(data_path).expanduser().resolve()
        try:
            raw = json.loads(data_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkspaceError(f"invalid workspace JSON: {exc}") from exc
        return cls.from_raw(raw, data_path.parent)

    @classmethod
    def from_raw(cls, raw: object, path: Path | str) -> "Workspace":
        if not isinstance(raw, dict):
            raise WorkspaceError("workspace root must be a JSON object")

        schema_version = raw.get("schema_version")
        if schema_version is None:
            raise WorkspaceError(
                "workspace schema_version is missing; run `palari migrate --write` "
                "or add schema_version: 1"
            )
        if not isinstance(schema_version, int):
            raise WorkspaceError("workspace schema_version must be an integer")
        if schema_version < CURRENT_SCHEMA_VERSION:
            raise WorkspaceError(
                f"workspace schema_version {schema_version} is older than supported "
                f"version {CURRENT_SCHEMA_VERSION}; run `palari migrate --write`"
            )
        if schema_version > CURRENT_SCHEMA_VERSION:
            raise WorkspaceError(
                f"workspace schema_version {schema_version} is newer than supported "
                f"version {CURRENT_SCHEMA_VERSION}"
            )
        workspace_path = Path(path).expanduser().resolve()
        raw = _expand_collection_files(raw, workspace_path)
        validate_raw_contract(raw)

        workspace = cls(
            path=workspace_path,
            schema_version=schema_version,
            name=str(raw.get("name") or workspace_path.name),
            goals=[Goal.from_record(item) for item in _items(raw, "goals")],
            palaris=[Palari.from_record(item) for item in _items(raw, "palaris")],
            humans=[Human.from_record(item) for item in _items(raw, "humans")],
            sources=[Source.from_record(item) for item in _items(raw, "sources")],
            workbenches=[Workbench.from_record(item) for item in _items(raw, "workbenches")],
            playbook_sources=[
                PlaybookSource.from_record(item) for item in _items(raw, "playbook_sources")
            ],
            capabilities=[Capability.from_record(item) for item in _items(raw, "capabilities")],
            authority_profiles=[
                AuthorityProfile.from_record(item) for item in _items(raw, "authority_profiles")
            ],
            integrations=[Integration.from_record(item) for item in _items(raw, "integrations")],
            integration_plans=[
                IntegrationPlan.from_record(item) for item in _items(raw, "integration_plans")
            ],
            integration_outbox=[
                IntegrationOutboxItem.from_record(item) for item in _items(raw, "integration_outbox")
            ],
            decisions=[Decision.from_record(item) for item in _items(raw, "decisions")],
            proposals=[Proposal.from_record(item) for item in _items(raw, "proposals")],
            work_items=[WorkItem.from_record(item) for item in _items(raw, "work_items")],
            attempts=[Attempt.from_record(item) for item in _items(raw, "attempts")],
            evidence_runs=[
                EvidenceRun.from_record(item) for item in _items(raw, "evidence_runs")
            ],
            review_verdicts=[
                ReviewVerdict.from_record(item) for item in _items(raw, "review_verdicts")
            ],
            human_decisions=[
                HumanDecision.from_record(item) for item in _items(raw, "human_decisions")
            ],
            acceptance_records=[
                AcceptanceRecord.from_record(item) for item in _items(raw, "acceptance_records")
            ],
            receipts=[Receipt.from_record(item) for item in _items(raw, "receipts")],
            outcomes=[Outcome.from_record(item) for item in _items(raw, "outcomes")],
        )
        workspace._rebuild_indexes()
        workspace.validate()
        return workspace

    def _rebuild_indexes(self) -> None:
        object.__setattr__(self, "_goals_by_id", {goal.id: goal for goal in self.goals})
        object.__setattr__(self, "_palaris_by_id", {palari.id: palari for palari in self.palaris})
        object.__setattr__(self, "_humans_by_id", {human.id: human for human in self.humans})
        object.__setattr__(self, "_sources_by_id", {source.id: source for source in self.sources})
        object.__setattr__(
            self,
            "_capabilities_by_id",
            {capability.id: capability for capability in self.capabilities},
        )
        object.__setattr__(
            self,
            "_integrations_by_id",
            {integration.id: integration for integration in self.integrations},
        )
        object.__setattr__(
            self,
            "_integration_plans_by_id",
            {plan.id: plan for plan in self.integration_plans},
        )
        object.__setattr__(
            self,
            "_integration_outbox_by_id",
            {item.id: item for item in self.integration_outbox},
        )
        object.__setattr__(
            self,
            "_proposals_by_id",
            {proposal.id: proposal for proposal in self.proposals},
        )
        object.__setattr__(self, "_work_items_by_id", {work.id: work for work in self.work_items})
        object.__setattr__(
            self,
            "_workbenches_by_id",
            {workbench.id: workbench for workbench in self.workbenches},
        )

    def validate(self) -> None:
        for label, records in (
            ("goals", self.goals),
            ("palaris", self.palaris),
            ("humans", self.humans),
            ("sources", self.sources),
            ("workbenches", self.workbenches),
            ("playbook_sources", self.playbook_sources),
            ("capabilities", self.capabilities),
            ("authority_profiles", self.authority_profiles),
            ("integrations", self.integrations),
            ("integration_plans", self.integration_plans),
            ("integration_outbox", self.integration_outbox),
            ("decisions", self.decisions),
            ("proposals", self.proposals),
            ("work_items", self.work_items),
            ("attempts", self.attempts),
            ("evidence_runs", self.evidence_runs),
            ("review_verdicts", self.review_verdicts),
            ("human_decisions", self.human_decisions),
            ("acceptance_records", self.acceptance_records),
            ("receipts", self.receipts),
            ("outcomes", self.outcomes),
        ):
            _ensure_unique_ids(label, records)

        goal_ids = {goal.id for goal in self.goals}
        palari_ids = {palari.id for palari in self.palaris}
        human_ids = {human.id for human in self.humans}
        source_ids = {source.id for source in self.sources}
        integration_ids = {integration.id for integration in self.integrations}
        integration_plan_ids = {plan.id for plan in self.integration_plans}
        integration_outbox_ids = {item.id for item in self.integration_outbox}
        workbench_ids = {workbench.id for workbench in self.workbenches}
        playbook_source_ids = {source.id for source in self.playbook_sources}
        capability_ids = {capability.id for capability in self.capabilities}
        authority_profile_ids = {profile.id for profile in self.authority_profiles}
        work_ids = {work.id for work in self.work_items}
        attempt_ids = {attempt.id for attempt in self.attempts}
        evidence_ids = {evidence.id for evidence in self.evidence_runs}
        review_ids = {review.id for review in self.review_verdicts}
        human_decision_ids = {decision.id for decision in self.human_decisions}
        decision_ids = {decision.id for decision in self.decisions}
        proposal_ids = {proposal.id for proposal in self.proposals}
        outcome_ids = {outcome.id for outcome in self.outcomes}

        for goal in self.goals:
            for palari_id in goal.linked_palaris:
                _require_ref("goals", goal.id, "linked_palaris", palari_id, palari_ids)
            for work_id in goal.linked_work:
                _require_ref("goals", goal.id, "linked_work", work_id, work_ids)
            for decision_id in goal.linked_decisions:
                _require_ref("goals", goal.id, "linked_decisions", decision_id, decision_ids)

        for workbench in self.workbenches:
            if workbench.parent_workbench_id:
                _require_ref(
                    "workbenches",
                    workbench.id,
                    "parent_workbench_id",
                    workbench.parent_workbench_id,
                    workbench_ids,
                )
            for goal_id in workbench.goal_ids:
                _require_ref("workbenches", workbench.id, "goal_ids", goal_id, goal_ids)
            for palari_id in workbench.palari_ids:
                _require_ref("workbenches", workbench.id, "palari_ids", palari_id, palari_ids)
            for human_id in workbench.human_ids:
                _require_ref("workbenches", workbench.id, "human_ids", human_id, human_ids)
            for source_id in workbench.source_ids:
                _require_ref("workbenches", workbench.id, "source_ids", source_id, source_ids)

        _ensure_parent_graph_has_no_cycles(
            "workbenches",
            self.workbenches,
            "parent_workbench_id",
        )

        for capability in self.capabilities:
            if capability.owner_human:
                _require_ref(
                    "capabilities",
                    capability.id,
                    "owner_human",
                    capability.owner_human,
                    human_ids,
                )
            for palari_id in capability.allowed_palaris:
                _require_ref(
                    "capabilities",
                    capability.id,
                    "allowed_palaris",
                    palari_id,
                    palari_ids,
                )
            for source_id in capability.source_ids:
                _require_ref("capabilities", capability.id, "source_ids", source_id, source_ids)

        for proposal in self.proposals:
            _require_ref("proposals", proposal.id, "goal", proposal.goal, goal_ids)
            _require_ref("proposals", proposal.id, "palari", proposal.palari, palari_ids)
            if proposal.proposer and proposal.proposer not in human_ids and proposal.proposer not in palari_ids:
                raise WorkspaceError(
                    f"proposals.{proposal.id}.proposer references missing human or Palari id "
                    f"{proposal.proposer}"
                )
            if proposal.linked_work:
                _require_ref("proposals", proposal.id, "linked_work", proposal.linked_work, work_ids)
            if proposal.decision_id:
                _require_ref("proposals", proposal.id, "decision_id", proposal.decision_id, decision_ids)
            if proposal.decided_by:
                _require_ref("proposals", proposal.id, "decided_by", proposal.decided_by, human_ids)
            for source_id in proposal.allowed_sources:
                _require_ref("proposals", proposal.id, "allowed_sources", source_id, source_ids)
            for playbook_ref in proposal.recommended_playbooks:
                _require_playbook_ref(
                    "proposals",
                    proposal.id,
                    "recommended_playbooks",
                    playbook_ref,
                    playbook_source_ids,
                    self.playbook_sources,
                )

        for work_item in self.work_items:
            _require_ref("work_items", work_item.id, "goal", work_item.goal, goal_ids)
            _require_ref("work_items", work_item.id, "palari", work_item.palari, palari_ids)
            if work_item.workbench_id:
                _require_ref(
                    "work_items",
                    work_item.id,
                    "workbench_id",
                    work_item.workbench_id,
                    workbench_ids,
                )
                _validate_workbench_boundary(self, work_item)
            if work_item.parent_work_item_id:
                _require_ref(
                    "work_items",
                    work_item.id,
                    "parent_work_item_id",
                    work_item.parent_work_item_id,
                    work_ids,
                )
            for dependency_id in work_item.dependency_ids:
                _require_ref("work_items", work_item.id, "dependency_ids", dependency_id, work_ids)
            if work_item.current_attempt:
                _require_ref(
                    "work_items",
                    work_item.id,
                    "current_attempt",
                    work_item.current_attempt,
                    attempt_ids,
                )
                current_attempt = _find(self.attempts, work_item.current_attempt)
                if current_attempt is not None and current_attempt.work_item_id != work_item.id:
                    raise WorkspaceError(
                        f"work_items.{work_item.id}.current_attempt references attempt "
                        f"{work_item.current_attempt} for different work item "
                        f"{current_attempt.work_item_id}"
                    )
            for source_id in work_item.allowed_sources:
                _require_ref("work_items", work_item.id, "allowed_sources", source_id, source_ids)
            for playbook_ref in work_item.recommended_playbooks:
                _require_playbook_ref(
                    "work_items",
                    work_item.id,
                    "recommended_playbooks",
                    playbook_ref,
                    playbook_source_ids,
                    self.playbook_sources,
                )
            if work_item.required_approval_count < 0:
                raise WorkspaceError(
                    f"work_items.{work_item.id}.required_approval_count must be zero or greater"
                )

        _ensure_parent_graph_has_no_cycles(
            "work_items",
            self.work_items,
            "parent_work_item_id",
        )

        for source_record in self.sources:
            if source_record.owner_human:
                _require_ref(
                    "sources",
                    source_record.id,
                    "owner_human",
                    source_record.owner_human,
                    human_ids,
                )
            if source_record.steward_human:
                _require_ref(
                    "sources",
                    source_record.id,
                    "steward_human",
                    source_record.steward_human,
                    human_ids,
                )
            for palari_id in source_record.allowed_palaris:
                _require_ref(
                    "sources",
                    source_record.id,
                    "allowed_palaris",
                    palari_id,
                    palari_ids,
                )

        for integration in self.integrations:
            if integration.owner_human:
                _require_ref(
                    "integrations",
                    integration.id,
                    "owner_human",
                    integration.owner_human,
                    human_ids,
                )
            for source_id in integration.source_ids:
                _require_ref("integrations", integration.id, "source_ids", source_id, source_ids)

        for plan in self.integration_plans:
            _require_ref(
                "integration_plans",
                plan.id,
                "integration_id",
                plan.integration_id,
                integration_ids,
            )
            _require_ref(
                "integration_plans",
                plan.id,
                "work_item_id",
                plan.work_item_id,
                work_ids,
            )
            if plan.actor:
                if plan.actor not in palari_ids and plan.actor not in human_ids:
                    raise WorkspaceError(
                        f"integration_plans.{plan.id}.actor references missing human or Palari "
                        f"id {plan.actor}"
                    )
            if plan.reviewed_by:
                _require_ref(
                    "integration_plans",
                    plan.id,
                    "reviewed_by",
                    plan.reviewed_by,
                    human_ids,
                )

        for item in self.integration_outbox:
            _require_ref(
                "integration_outbox",
                item.id,
                "plan_id",
                item.plan_id,
                integration_plan_ids,
            )
            _require_ref(
                "integration_outbox",
                item.id,
                "integration_id",
                item.integration_id,
                integration_ids,
            )
            _require_ref(
                "integration_outbox",
                item.id,
                "work_item_id",
                item.work_item_id,
                work_ids,
            )
            _require_ref(
                "integration_outbox",
                item.id,
                "enqueued_by",
                item.enqueued_by,
                human_ids,
            )
            if item.canceled_by:
                _require_ref(
                    "integration_outbox",
                    item.id,
                    "canceled_by",
                    item.canceled_by,
                    human_ids,
                )

        for palari in self.palaris:
            if palari.owner_human:
                _require_ref("palaris", palari.id, "owner_human", palari.owner_human, human_ids)
            for source_id in palari.memory_sources:
                _require_ref("palaris", palari.id, "memory_sources", source_id, source_ids)
            for goal_id in palari.linked_goals:
                _require_ref("palaris", palari.id, "linked_goals", goal_id, goal_ids)
            for work_id in palari.active_work:
                _require_ref("palaris", palari.id, "active_work", work_id, work_ids)
            for outcome_id in palari.outcomes:
                _require_ref("palaris", palari.id, "outcomes", outcome_id, outcome_ids)

        for attempt in self.attempts:
            _require_ref("attempts", attempt.id, "work_item_id", attempt.work_item_id, work_ids)

        for evidence in self.evidence_runs:
            _require_ref(
                "evidence_runs", evidence.id, "work_item_id", evidence.work_item_id, work_ids
            )
            _require_ref(
                "evidence_runs", evidence.id, "attempt_id", evidence.attempt_id, attempt_ids
            )

        for review in self.review_verdicts:
            _require_ref(
                "review_verdicts", review.id, "work_item_id", review.work_item_id, work_ids
            )

        for decision_record in self.decisions:
            if decision_record.required_human:
                _require_ref(
                    "decisions",
                    decision_record.id,
                    "required_human",
                    decision_record.required_human,
                    human_ids,
                )
            if decision_record.linked_work:
                _require_ref(
                    "decisions",
                    decision_record.id,
                    "linked_work",
                    decision_record.linked_work,
                    work_ids,
                )
            if decision_record.linked_goal:
                _require_ref(
                    "decisions",
                    decision_record.id,
                    "linked_goal",
                    decision_record.linked_goal,
                    goal_ids,
                )
            if decision_record.linked_palari:
                _require_ref(
                    "decisions",
                    decision_record.id,
                    "linked_palari",
                    decision_record.linked_palari,
                    palari_ids,
                )

        for human_decision in self.human_decisions:
            _require_ref(
                "human_decisions",
                human_decision.id,
                "work_item_id",
                human_decision.work_item_id,
                work_ids,
            )
            _require_ref(
                "human_decisions",
                human_decision.id,
                "human_id",
                human_decision.human_id,
                human_ids,
            )
            if human_decision.evidence_reference:
                _require_ref(
                    "human_decisions",
                    human_decision.id,
                    "evidence_reference",
                    human_decision.evidence_reference,
                    evidence_ids,
                )
            if human_decision.review_reference:
                _require_ref(
                    "human_decisions",
                    human_decision.id,
                    "review_reference",
                    human_decision.review_reference,
                    review_ids,
                )

        for acceptance in self.acceptance_records:
            _require_ref(
                "acceptance_records",
                acceptance.id,
                "work_item_id",
                acceptance.work_item_id,
                work_ids,
            )
            _require_ref(
                "acceptance_records",
                acceptance.id,
                "human_id",
                acceptance.human_id,
                human_ids,
            )
            if acceptance.decision_id:
                _require_ref(
                    "acceptance_records",
                    acceptance.id,
                    "decision_id",
                    acceptance.decision_id,
                    human_decision_ids,
                )
            if acceptance.evidence_reference:
                _require_ref(
                    "acceptance_records",
                    acceptance.id,
                    "evidence_reference",
                    acceptance.evidence_reference,
                    evidence_ids,
                )
            if acceptance.review_reference:
                _require_ref(
                    "acceptance_records",
                    acceptance.id,
                    "review_reference",
                    acceptance.review_reference,
                    review_ids,
                )
            if acceptance.authority_profile and acceptance.authority_profile not in {
                "solo-founder",
                "team-safe",
                "strict",
                *authority_profile_ids,
            }:
                raise WorkspaceError(
                    f"acceptance_records.{acceptance.id}.authority_profile references "
                    f"missing profile {acceptance.authority_profile}"
                )

        for receipt in self.receipts:
            _require_ref("receipts", receipt.id, "work_item_id", receipt.work_item_id, work_ids)
            _require_ref("receipts", receipt.id, "attempt_id", receipt.attempt_id, attempt_ids)
            for source_id in receipt.sources_used:
                _require_ref("receipts", receipt.id, "sources_used", source_id, source_ids)
            for plan_id in receipt.planned_external_writes:
                _require_ref(
                    "receipts",
                    receipt.id,
                    "planned_external_writes",
                    plan_id,
                    integration_plan_ids,
                )
            for outbox_item_id in receipt.queued_external_writes:
                _require_ref(
                    "receipts",
                    receipt.id,
                    "queued_external_writes",
                    outbox_item_id,
                    integration_outbox_ids,
                )

        for outcome in self.outcomes:
            _require_ref("outcomes", outcome.id, "work_item_id", outcome.work_item_id, work_ids)

        validate_workspace_contract(self)

    def goal(self, goal_id: str) -> Goal | None:
        return self._goals_by_id.get(goal_id)

    def palari(self, palari_id: str) -> Palari | None:
        return self._palaris_by_id.get(palari_id)

    def human(self, human_id: str) -> Human | None:
        return self._humans_by_id.get(human_id)

    def work_item(self, work_id: str) -> WorkItem | None:
        return self._work_items_by_id.get(work_id)

    def source(self, source_id: str) -> Source | None:
        return self._sources_by_id.get(source_id)

    def capability(self, capability_id: str) -> Capability | None:
        return self._capabilities_by_id.get(capability_id)

    def proposal(self, proposal_id: str) -> Proposal | None:
        return self._proposals_by_id.get(proposal_id)

    def integration(self, integration_id: str) -> Integration | None:
        return self._integrations_by_id.get(integration_id)

    def integration_plan(self, plan_id: str) -> IntegrationPlan | None:
        return self._integration_plans_by_id.get(plan_id)

    def integration_outbox_item(self, item_id: str) -> IntegrationOutboxItem | None:
        return self._integration_outbox_by_id.get(item_id)

    def workbench(self, workbench_id: str) -> Workbench | None:
        return self._workbenches_by_id.get(workbench_id)


def default_workspace_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    repo_fixture = repo_root / "examples" / "acme-company-os"
    if repo_fixture.exists():
        return repo_fixture
    return _packaged_data_path("examples", "acme-company-os")


def current_attempt_for_work(work: WorkItem, attempts: Iterable[Attempt]) -> Attempt | None:
    latest: Attempt | None = None
    latest_key: tuple[str, str, str, str] | None = None
    for attempt in attempts:
        if attempt.work_item_id != work.id:
            continue
        if work.current_attempt and attempt.id == work.current_attempt:
            return attempt
        key = _record_time_key(attempt)
        if latest_key is None or key > latest_key:
            latest = attempt
            latest_key = key
    return latest


def latest_for_work(records: Iterable[T], work_id: str) -> T | None:
    latest: T | None = None
    latest_key: tuple[str, str, str, str] | None = None
    for record in records:
        if getattr(record, "work_item_id") != work_id:
            continue
        key = _record_time_key(record)
        if latest_key is None or key > latest_key:
            latest = record
            latest_key = key
    return latest


def _record_time_key(record: object) -> tuple[str, str, str, str]:
    return (
        str(getattr(record, "timestamp", "")),
        str(getattr(record, "updated_at", "")),
        str(getattr(record, "started_at", "")),
        str(getattr(record, "id", "")),
    )


def _packaged_data_path(*parts: str) -> Path:
    return Path(str(files("palari_company_os").joinpath("data", *parts)))


def _items(raw: dict[str, object], key: str) -> list[dict[str, object]]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError(f"{key} must be a list of objects")
    return value


def _expand_collection_files(
    raw: dict[str, object], workspace_path: Path
) -> dict[str, object]:
    collection_files = raw.get("collection_files")
    if not collection_files:
        return raw

    validate_raw_contract(raw)
    if not isinstance(collection_files, dict):
        raise WorkspaceError("workspace.collection_files must be an object")

    expanded: dict[str, object] = {}
    for key, value in raw.items():
        if key == "collection_files":
            expanded[key] = value
        elif key in COLLECTION_FILE_KEYS:
            expanded[key] = list(_items(raw, key))
        else:
            expanded[key] = value

    for collection, paths in collection_files.items():
        if collection not in COLLECTION_FILE_KEYS:
            raise WorkspaceError(
                f"workspace.collection_files has unknown collection: {collection}"
            )
        if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
            raise WorkspaceError(f"workspace.collection_files.{collection} must be a list of paths")
        records = expanded.setdefault(collection, [])
        if not isinstance(records, list):
            raise WorkspaceError(f"{collection} must be a list of objects")
        for relative_path in paths:
            include_path = _collection_file_path(workspace_path, collection, relative_path)
            try:
                included = json.loads(include_path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise WorkspaceError(
                    f"workspace.collection_files.{collection} file not found: {relative_path}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise WorkspaceError(
                    f"invalid JSON in workspace.collection_files.{collection} {relative_path}: {exc}"
                ) from exc
            if not isinstance(included, list) or not all(
                isinstance(item, dict) for item in included
            ):
                raise WorkspaceError(
                    f"workspace.collection_files.{collection} {relative_path} "
                    "must contain a list of objects"
                )
            records.extend(included)
    return expanded


def _collection_file_path(workspace_path: Path, collection: str, value: str) -> Path:
    if not value:
        raise WorkspaceError(f"workspace.collection_files.{collection} contains an empty path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise WorkspaceError(
            f"workspace.collection_files.{collection} path must be workspace-relative "
            f"and must not contain '..': {value}"
        )
    return workspace_path / path


def _find(records: Iterable[T], identifier: str) -> T | None:
    for record in records:
        if getattr(record, "id") == identifier:
            return record
    return None


def _ensure_parent_graph_has_no_cycles(
    label: str,
    records: Iterable[object],
    parent_field: str,
) -> None:
    by_id = {getattr(record, "id"): record for record in records}
    for record_id in by_id:
        seen: set[str] = set()
        path: list[str] = []
        current = record_id
        while current:
            if current in seen:
                cycle_start = path.index(current)
                cycle = " -> ".join([*path[cycle_start:], current])
                raise WorkspaceError(f"{label} parent graph contains a cycle: {cycle}")
            seen.add(current)
            path.append(current)
            record = by_id.get(current)
            if record is None:
                break
            current = getattr(record, parent_field)


def _validate_workbench_boundary(workspace: Workspace, work: WorkItem) -> None:
    sources, outputs = _inherited_workbench_boundaries(workspace, work.workbench_id)
    for source in work.allowed_sources:
        if source not in sources:
            raise WorkspaceError(
                f"work_items.{work.id}.allowed_sources includes source {source} "
                f"outside workbench {work.workbench_id}"
            )
    for output in work.output_targets:
        if output not in outputs:
            raise WorkspaceError(
                f"work_items.{work.id}.output_targets includes target {output} "
                f"outside workbench {work.workbench_id}"
            )


def _inherited_workbench_boundaries(
    workspace: Workspace,
    workbench_id: str,
) -> tuple[set[str], set[str]]:
    workbenches = {workbench.id: workbench for workbench in workspace.workbenches}
    sources: set[str] = set()
    outputs: set[str] = set()
    current = workbench_id
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        workbench = workbenches.get(current)
        if workbench is None:
            break
        sources.update(workbench.source_ids)
        outputs.update(workbench.output_target_ids)
        current = workbench.parent_workbench_id
    return sources, outputs


def _ensure_unique_ids(label: str, records: Iterable[object]) -> None:
    seen: set[str] = set()
    for record in records:
        identifier = getattr(record, "id")
        if identifier in seen:
            raise WorkspaceError(f"{label} contains duplicate id: {identifier}")
        seen.add(identifier)


def _require_ref(
    collection: str,
    record_id: str,
    field: str,
    value: str,
    allowed: set[str],
) -> None:
    if value not in allowed:
        raise WorkspaceError(f"{collection}.{record_id}.{field} references missing id {value}")


def _require_playbook_ref(
    collection: str,
    record_id: str,
    field: str,
    value: str,
    allowed_sources: set[str],
    sources: Iterable[PlaybookSource],
) -> None:
    if ":" not in value:
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} must use source:playbook format: {value}"
        )
    source_id, playbook_id = value.split(":", 1)
    if source_id not in allowed_sources:
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} references missing playbook source {source_id}"
        )
    source = _find(sources, source_id)
    if source and playbook_id not in source.included_playbooks:
        raise WorkspaceError(
            f"{collection}.{record_id}.{field} references playbook {playbook_id} "
            f"not included by source {source_id}"
        )

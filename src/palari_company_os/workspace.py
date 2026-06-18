from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeVar

from .models import (
    Attempt,
    Decision,
    EvidenceRun,
    Goal,
    Human,
    HumanDecision,
    Outcome,
    Palari,
    ReviewVerdict,
    WorkItem,
)


class WorkspaceError(RuntimeError):
    """Raised when a workspace cannot be loaded or is internally inconsistent."""


T = TypeVar("T")


@dataclass(frozen=True)
class Workspace:
    path: Path
    name: str
    goals: list[Goal]
    palaris: list[Palari]
    humans: list[Human]
    decisions: list[Decision]
    work_items: list[WorkItem]
    attempts: list[Attempt]
    evidence_runs: list[EvidenceRun]
    review_verdicts: list[ReviewVerdict]
    human_decisions: list[HumanDecision]
    outcomes: list[Outcome]

    @classmethod
    def load(cls, path: Path | str) -> "Workspace":
        workspace_path = Path(path).expanduser().resolve()
        data_path = workspace_path / "workspace.json" if workspace_path.is_dir() else workspace_path
        if not data_path.exists():
            raise WorkspaceError(f"workspace file not found: {data_path}")

        try:
            raw = json.loads(data_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkspaceError(f"invalid workspace JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise WorkspaceError("workspace root must be a JSON object")

        workspace = cls(
            path=data_path.parent,
            name=str(raw.get("name") or data_path.parent.name),
            goals=[Goal.from_record(item) for item in _items(raw, "goals")],
            palaris=[Palari.from_record(item) for item in _items(raw, "palaris")],
            humans=[Human.from_record(item) for item in _items(raw, "humans")],
            decisions=[Decision.from_record(item) for item in _items(raw, "decisions")],
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
            outcomes=[Outcome.from_record(item) for item in _items(raw, "outcomes")],
        )
        workspace.validate()
        return workspace

    def validate(self) -> None:
        for label, records in (
            ("goals", self.goals),
            ("palaris", self.palaris),
            ("humans", self.humans),
            ("decisions", self.decisions),
            ("work_items", self.work_items),
            ("attempts", self.attempts),
            ("evidence_runs", self.evidence_runs),
            ("review_verdicts", self.review_verdicts),
            ("human_decisions", self.human_decisions),
            ("outcomes", self.outcomes),
        ):
            _ensure_unique_ids(label, records)

        goal_ids = {goal.id for goal in self.goals}
        palari_ids = {palari.id for palari in self.palaris}
        human_ids = {human.id for human in self.humans}
        work_ids = {work.id for work in self.work_items}
        attempt_ids = {attempt.id for attempt in self.attempts}
        evidence_ids = {evidence.id for evidence in self.evidence_runs}
        review_ids = {review.id for review in self.review_verdicts}

        for work in self.work_items:
            _require_ref("work_items", work.id, "goal", work.goal, goal_ids)
            _require_ref("work_items", work.id, "palari", work.palari, palari_ids)

        for palari in self.palaris:
            if palari.owner_human:
                _require_ref("palaris", palari.id, "owner_human", palari.owner_human, human_ids)
            for goal in palari.linked_goals:
                _require_ref("palaris", palari.id, "linked_goals", goal, goal_ids)

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

        for decision in self.decisions:
            if decision.required_human:
                _require_ref(
                    "decisions",
                    decision.id,
                    "required_human",
                    decision.required_human,
                    human_ids,
                )
            if decision.linked_work:
                _require_ref("decisions", decision.id, "linked_work", decision.linked_work, work_ids)

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

        for outcome in self.outcomes:
            _require_ref("outcomes", outcome.id, "work_item_id", outcome.work_item_id, work_ids)

    def goal(self, goal_id: str) -> Goal | None:
        return _find(self.goals, goal_id)

    def palari(self, palari_id: str) -> Palari | None:
        return _find(self.palaris, palari_id)

    def human(self, human_id: str) -> Human | None:
        return _find(self.humans, human_id)

    def work_item(self, work_id: str) -> WorkItem | None:
        return _find(self.work_items, work_id)


def default_workspace_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "examples" / "acme-company-os"


def latest_for_work(records: Iterable[T], work_id: str) -> T | None:
    matching = [record for record in records if getattr(record, "work_item_id") == work_id]
    if not matching:
        return None
    return sorted(matching, key=lambda item: getattr(item, "timestamp", ""))[-1]


def _items(raw: dict[str, object], key: str) -> list[dict[str, object]]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError(f"{key} must be a list of objects")
    return value


def _find(records: Iterable[T], identifier: str) -> T | None:
    for record in records:
        if getattr(record, "id") == identifier:
            return record
    return None


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


from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar, TypeVar, get_args, get_origin, get_type_hints

from .pcaw_canonical import IJSON_MAX_INTEGER, canonical_sha256


CASE_SCHEMA_VERSION = "pcaw.governance_case.v1"
OBSERVATION_STATUSES = {"verified", "failed", "not-checked", "not-required"}
T = TypeVar("T")


@dataclass(frozen=True)
class WorkContract:
    id: str
    title: str = ""
    goal: str = ""
    palari: str = ""
    workbench_id: str = ""
    parent_work_item_id: str = ""
    risk: str = "R1"
    intensity: str = "light"
    status: str = "proposed"
    scope: str = ""
    allowed_resources: tuple[str, ...] = ()
    allowed_sources: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()
    output_targets: tuple[str, ...] = ()
    forbidden_actions: tuple[str, ...] = ()
    acceptance_target: str = ""
    verification_expectations: tuple[str, ...] = ()
    current_attempt_id: str = ""
    required_approval_count: int = 0
    required_approval_capability: str = ""
    conflict_targets: tuple[str, ...] = ()
    parallel_policy: str = "independent"


@dataclass(frozen=True)
class DependencyState:
    id: str
    status: str


@dataclass(frozen=True)
class SourceBoundary:
    id: str
    selected: bool = True
    allowed_palaris: tuple[str, ...] = ()
    data_class: str = ""
    authority: str = ""
    steward_human: str = ""
    freshness: str = ""
    redaction_required: bool = False


@dataclass(frozen=True)
class AttemptSnapshot:
    id: str
    work_item_id: str
    actor: str
    status: str
    base_sha: str = ""
    head_sha: str = ""
    commits: tuple[str, ...] = ()
    changed_files: tuple[str, ...] = ()
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    cleanliness: str = ""
    result: str = ""
    output_targets: tuple[str, ...] = ()
    started_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class ReceiptSnapshot:
    id: str
    work_item_id: str
    attempt_id: str
    actor: str
    context_hash: str = ""
    sources_used: tuple[str, ...] = ()
    actions_taken: tuple[str, ...] = ()
    outputs_created: tuple[str, ...] = ()
    planned_external_writes: tuple[str, ...] = ()
    queued_external_writes: tuple[str, ...] = ()
    external_writes: tuple[str, ...] = ()
    not_done: tuple[str, ...] = ()
    undo_refs: tuple[str, ...] = ()
    receipt_hash: str = ""
    previous_receipt_hash: str = ""
    evidence_manifest_hash: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class ArtifactDigest:
    path: str
    sha256: str
    status: str = "present"


@dataclass(frozen=True)
class EvidenceSnapshot:
    id: str
    work_item_id: str
    attempt_id: str
    head_sha: str
    status: str
    base_ref: str = ""
    commands: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    artifact_hashes: tuple[ArtifactDigest, ...] = ()
    manifest_hash: str = ""
    receipt_id: str = ""
    receipt_digest: str = ""
    receipt_hash: str = ""
    previous_receipt_hash: str = ""
    summary: str = ""
    freshness: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class Finding:
    severity: str = ""
    summary: str = ""
    details: str = ""


@dataclass(frozen=True)
class LegacyProofBinding:
    binding_version: str = ""
    attempt_hash: str = ""
    evidence_manifest_hash: str = ""
    receipt_hash: str = ""
    work_contract_hash: str = ""
    proof_hash: str = ""


@dataclass(frozen=True)
class ReviewSnapshot:
    id: str
    work_item_id: str
    reviewed_head: str
    reviewer: str
    verdict: str
    attempt_id: str = ""
    evidence_id: str = ""
    receipt_id: str = ""
    contract_digest: str = ""
    attempt_digest: str = ""
    evidence_digest: str = ""
    receipt_digest: str = ""
    findings: tuple[Finding, ...] = ()
    checks_inspected: tuple[str, ...] = ()
    residual_risks: tuple[str, ...] = ()
    timestamp: str = ""
    legacy_binding: LegacyProofBinding = field(default_factory=LegacyProofBinding)


@dataclass(frozen=True)
class HumanAuthority:
    id: str
    approval_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class HumanDecisionSnapshot:
    id: str
    work_item_id: str
    human_id: str
    reviewed_head: str
    decision: str
    status: str
    acceptance_mode: str = ""
    quorum_status: str = ""
    evidence_id: str = ""
    review_id: str = ""
    evidence_digest: str = ""
    review_digest: str = ""
    timestamp: str = ""


@dataclass(frozen=True)
class AcceptanceSnapshot:
    id: str
    work_item_id: str
    human_id: str
    reviewed_head: str
    status: str
    decision_id: str = ""
    evidence_id: str = ""
    review_id: str = ""
    receipt_digest: str = ""
    evidence_digest: str = ""
    review_digest: str = ""
    quorum_status: str = ""
    accepted_at: str = ""


@dataclass(frozen=True)
class OutcomeSnapshot:
    id: str
    work_item_id: str
    status: str
    timestamp: str = ""


@dataclass(frozen=True)
class IntegrityObservation:
    status: str
    details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in OBSERVATION_STATUSES:
            raise ValueError(f"unsupported observation status: {self.status}")


@dataclass(frozen=True)
class IntegrityObservations:
    subject_integrity: IntegrityObservation = field(
        default_factory=lambda: IntegrityObservation("not-checked")
    )
    evidence_integrity: IntegrityObservation = field(
        default_factory=lambda: IntegrityObservation("not-checked")
    )
    journal_continuity: IntegrityObservation = field(
        default_factory=lambda: IntegrityObservation("not-checked")
    )


@dataclass(frozen=True)
class GovernanceCase:
    schema_version: str
    claimed_state: str
    contract: WorkContract
    dependencies: tuple[DependencyState, ...] = ()
    open_decisions: tuple[str, ...] = ()
    sources: tuple[SourceBoundary, ...] = ()
    attempt: AttemptSnapshot | None = None
    receipt: ReceiptSnapshot | None = None
    evidence: EvidenceSnapshot | None = None
    review: ReviewSnapshot | None = None
    humans: tuple[HumanAuthority, ...] = ()
    human_decisions: tuple[HumanDecisionSnapshot, ...] = ()
    acceptance_records: tuple[AcceptanceSnapshot, ...] = ()
    outcome: OutcomeSnapshot | None = None
    observations: IntegrityObservations = field(default_factory=IntegrityObservations)

    TOP_LEVEL_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "claimed_state",
            "contract",
            "dependencies",
            "open_decisions",
            "sources",
            "attempt",
            "receipt",
            "evidence",
            "review",
            "humans",
            "human_decisions",
            "acceptance_records",
            "outcome",
            "observations",
        }
    )

    def __post_init__(self) -> None:
        if self.schema_version != CASE_SCHEMA_VERSION:
            raise ValueError(f"unsupported governance case schema: {self.schema_version}")
        for label, records in (
            ("dependencies", self.dependencies),
            ("sources", self.sources),
            ("humans", self.humans),
            ("human_decisions", self.human_decisions),
            ("acceptance_records", self.acceptance_records),
        ):
            identifiers = [record.id for record in records]
            if len(identifiers) != len(set(identifiers)):
                raise ValueError(f"{label} ids must be unique")
        if len(self.open_decisions) != len(set(self.open_decisions)):
            raise ValueError("open_decisions ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        return _plain(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GovernanceCase":
        if not isinstance(value, dict):
            raise ValueError("governance_case must be an object")
        _exact_fields(value, cls.TOP_LEVEL_FIELDS, "governance_case")
        schema_version = _string(value, "schema_version", "governance_case")
        if schema_version != CASE_SCHEMA_VERSION:
            raise ValueError(f"unsupported governance case schema: {schema_version}")
        return cls(
            schema_version=schema_version,
            claimed_state=_string(value, "claimed_state", "governance_case"),
            contract=_record(WorkContract, value.get("contract"), "contract"),
            dependencies=_records(DependencyState, value.get("dependencies"), "dependencies"),
            open_decisions=_strings(value.get("open_decisions"), "open_decisions"),
            sources=_records(SourceBoundary, value.get("sources"), "sources"),
            attempt=_optional_record(AttemptSnapshot, value.get("attempt"), "attempt"),
            receipt=_optional_record(ReceiptSnapshot, value.get("receipt"), "receipt"),
            evidence=_optional_evidence(value.get("evidence")),
            review=_optional_review(value.get("review")),
            humans=_records(HumanAuthority, value.get("humans"), "humans"),
            human_decisions=_records(
                HumanDecisionSnapshot, value.get("human_decisions"), "human_decisions"
            ),
            acceptance_records=_records(
                AcceptanceSnapshot, value.get("acceptance_records"), "acceptance_records"
            ),
            outcome=_optional_record(OutcomeSnapshot, value.get("outcome"), "outcome"),
            observations=_observations(value.get("observations")),
        )

    def contract_digest(self) -> str:
        return canonical_sha256(_plain(self.contract))

    def attempt_digest(self) -> str:
        return canonical_sha256(_plain(self.attempt)) if self.attempt is not None else ""

    def receipt_digest(self) -> str:
        return canonical_sha256(_plain(self.receipt)) if self.receipt is not None else ""

    def evidence_digest(self) -> str:
        return canonical_sha256(_plain(self.evidence)) if self.evidence is not None else ""

    def review_digest(self) -> str:
        return canonical_sha256(_plain(self.review)) if self.review is not None else ""


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__dataclass_fields__"):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _record(record_type: type[T], value: Any, path: str) -> T:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    names = frozenset(record_type.__dataclass_fields__)  # type: ignore[attr-defined]
    _exact_fields(value, names, path)
    converted = dict(value)
    hints = get_type_hints(record_type)
    for name, field_info in record_type.__dataclass_fields__.items():  # type: ignore[attr-defined]
        if name not in converted:
            raise ValueError(f"{path}.{name} is required")
        converted[name] = _typed_value(
            converted[name], hints.get(name, field_info.type), f"{path}.{name}"
        )
    return record_type(**converted)


def _records(record_type: type[T], value: Any, path: str) -> tuple[T, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{path} must be an array")
    return tuple(_record(record_type, item, f"{path}[{index}]") for index, item in enumerate(value))


def _optional_record(record_type: type[T], value: Any, path: str) -> T | None:
    return None if value is None else _record(record_type, value, path)


def _optional_evidence(value: Any) -> EvidenceSnapshot | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("evidence must be an object or null")
    names = frozenset(EvidenceSnapshot.__dataclass_fields__)
    _exact_fields(value, names, "evidence")
    converted = dict(value)
    hints = get_type_hints(EvidenceSnapshot)
    for name in names:
        if name not in converted:
            raise ValueError(f"evidence.{name} is required")
    converted["artifact_hashes"] = _records(
        ArtifactDigest, converted["artifact_hashes"], "evidence.artifact_hashes"
    )
    for name in names - {"artifact_hashes"}:
        converted[name] = _typed_value(converted[name], hints[name], f"evidence.{name}")
    return EvidenceSnapshot(**converted)


def _optional_review(value: Any) -> ReviewSnapshot | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("review must be an object or null")
    names = frozenset(ReviewSnapshot.__dataclass_fields__)
    _exact_fields(value, names, "review")
    converted = dict(value)
    hints = get_type_hints(ReviewSnapshot)
    for name in names:
        if name not in converted:
            raise ValueError(f"review.{name} is required")
    converted["findings"] = _records(Finding, converted["findings"], "review.findings")
    converted["legacy_binding"] = _record(
        LegacyProofBinding, converted["legacy_binding"], "review.legacy_binding"
    )
    for name in names - {"findings", "legacy_binding"}:
        converted[name] = _typed_value(converted[name], hints[name], f"review.{name}")
    return ReviewSnapshot(**converted)


def _observations(value: Any) -> IntegrityObservations:
    if not isinstance(value, dict):
        raise ValueError("observations must be an object")
    names = frozenset(IntegrityObservations.__dataclass_fields__)
    _exact_fields(value, names, "observations")
    return IntegrityObservations(
        **{
            name: _record(IntegrityObservation, value.get(name), f"observations.{name}")
            for name in names
        }
    )


def _exact_fields(value: dict[str, Any], expected: frozenset[str], path: str) -> None:
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ValueError(f"{path} has unknown field(s): {', '.join(unknown)}")
    if missing:
        raise ValueError(f"{path} is missing field(s): {', '.join(missing)}")


def _string(value: dict[str, Any], key: str, path: str) -> str:
    item = value.get(key)
    if not isinstance(item, str):
        raise ValueError(f"{path}.{key} must be a string")
    return item


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{path} must be an array of strings")
    return tuple(value)


def _typed_value(value: Any, annotation: Any, path: str) -> Any:
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if annotation is str:
        if not isinstance(value, str):
            raise ValueError(f"{path} must be a string")
        return value
    if annotation is int:
        if type(value) is not int:
            raise ValueError(f"{path} must be an integer")
        if not -IJSON_MAX_INTEGER <= value <= IJSON_MAX_INTEGER:
            raise ValueError(f"{path} is outside the interoperable I-JSON range")
        return value
    if annotation is bool:
        if type(value) is not bool:
            raise ValueError(f"{path} must be a boolean")
        return value
    if origin is tuple and arguments == (str, Ellipsis):
        return _strings(value, path)
    return value

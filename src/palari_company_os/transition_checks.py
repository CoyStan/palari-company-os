from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .errors import WorkspaceError
from .governance_binding import current_review_binding, current_review_binding_errors
from .read_models import detail
from .workspace import Workspace, current_attempt_for_work, latest_for_work


@dataclass(frozen=True)
class TransitionBlocker:
    code: str
    message: str
    next_command: str = ""

    def to_dict(self) -> dict[str, str]:
        payload = {"code": self.code, "message": self.message}
        if self.next_command:
            payload["next_command"] = self.next_command
        return payload


@dataclass(frozen=True)
class TransitionCheck:
    transition: str
    target_id: str
    actor: str = ""
    blockers: list[TransitionBlocker] = field(default_factory=list)
    next_allowed_commands: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "palari.transition_check.v1",
            "transition": self.transition,
            "target_id": self.target_id,
            "actor": self.actor,
            "ok": self.ok,
            "blockers": [blocker.to_dict() for blocker in self.blockers],
            "next_allowed_commands": self.next_allowed_commands,
        }


def check_transition(
    workspace: Workspace,
    transition: str,
    target_id: str,
    *,
    actor: str = "",
    context: dict[str, Any] | None = None,
) -> TransitionCheck:
    context = context or {}
    blockers: list[TransitionBlocker] = []
    next_commands: list[str] = []

    if transition == "proposal_adopt":
        _check_proposal_adopt(workspace, target_id, actor, context, blockers, next_commands)
    elif transition == "agent_start":
        _check_agent_start(workspace, target_id, actor, context, blockers, next_commands)
    elif transition == "attempt_closeout":
        _check_attempt_closeout(workspace, target_id, context, blockers, next_commands)
    elif transition == "evidence_record":
        _check_evidence_record(workspace, target_id, context, blockers, next_commands)
    elif transition == "review_record":
        _check_review_record(workspace, target_id, actor, context, blockers, next_commands)
    elif transition == "human_decision_accept":
        _check_human_decision_accept(workspace, target_id, actor, context, blockers, next_commands)
    elif transition == "work_accept":
        _check_work_accept(workspace, target_id, actor, context, blockers, next_commands)
    elif transition == "work_complete":
        _check_work_complete(workspace, target_id, blockers, next_commands)
    elif transition == "integration_enqueue":
        _check_integration_enqueue(workspace, target_id, actor, blockers, next_commands)
    elif transition == "integration_send":
        _check_integration_send(workspace, target_id, actor, context, blockers, next_commands)
    else:
        blockers.append(
            TransitionBlocker(
                "UNKNOWN_TRANSITION",
                f"unknown transition {transition}",
            )
        )

    return TransitionCheck(
        transition=transition,
        target_id=target_id,
        actor=actor,
        blockers=blockers,
        next_allowed_commands=_unique(next_commands),
    )


def assert_transition_allowed(
    workspace: Workspace,
    transition: str,
    target_id: str,
    *,
    actor: str = "",
    context: dict[str, Any] | None = None,
) -> TransitionCheck:
    result = check_transition(workspace, transition, target_id, actor=actor, context=context)
    if result.ok:
        return result
    first = result.blockers[0]
    next_action = f"; next action: {first.next_command}" if first.next_command else ""
    raise WorkspaceError(
        f"transition {transition} for {target_id} is blocked: {first.message}{next_action}"
    )


def _check_proposal_adopt(
    workspace: Workspace,
    proposal_id: str,
    human_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    work_id = str(context.get("work_id") or "")
    proposal = workspace.proposal(proposal_id)
    if proposal is None:
        blockers.append(TransitionBlocker("PROPOSAL_MISSING", f"proposal not found: {proposal_id}"))
        return
    if workspace.human(human_id) is None:
        blockers.append(TransitionBlocker("HUMAN_MISSING", f"human not found: {human_id}"))
    if proposal.status == "adopted":
        blockers.append(
            TransitionBlocker("PROPOSAL_ALREADY_ADOPTED", f"proposal already adopted: {proposal_id}")
        )
    if proposal.status in {"rejected", "deferred"}:
        blockers.append(
            TransitionBlocker("PROPOSAL_CLOSED", f"proposal {proposal_id} is {proposal.status}")
        )
    if work_id and workspace.work_item(work_id) is not None:
        blockers.append(TransitionBlocker("WORK_EXISTS", f"work already exists: {work_id}"))
    if not work_id:
        blockers.append(TransitionBlocker("WORK_ID_MISSING", "adoption requires a work id"))
    next_commands.append(f"palari proposal adopt {proposal_id} --work-id WORK-ID --by HUMAN-ID --json")


def _check_agent_start(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    if workspace.work_item(work_id) is None:
        blockers.append(TransitionBlocker("WORK_MISSING", f"work not found: {work_id}"))
        return
    packet = context.get("packet")
    if not isinstance(packet, dict):
        blockers.append(TransitionBlocker("PACKET_MISSING", "agent start requires a packet"))
        return
    if packet.get("status") != "ready":
        first_command = _first_next_command(packet)
        blockers.append(
            TransitionBlocker(
                "PACKET_NOT_READY",
                "agent start requires a ready packet",
                first_command,
            )
        )
    if palari_id and workspace.palari(palari_id) is None:
        blockers.append(TransitionBlocker("PALARI_MISSING", f"Palari not found: {palari_id}"))


def _check_attempt_closeout(
    workspace: Workspace,
    attempt_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    attempt = _attempt(workspace, attempt_id)
    if attempt is None:
        blockers.append(TransitionBlocker("ATTEMPT_MISSING", f"attempt not found: {attempt_id}"))
        return
    cleanliness = str(context.get("cleanliness") or attempt.cleanliness)
    if cleanliness.lower() not in {"clean", "pristine"}:
        blockers.append(
            TransitionBlocker(
                "ATTEMPT_DIRTY",
                f"attempt {attempt_id} cannot close out with cleanliness {cleanliness}",
            )
        )
    head_sha = str(context.get("head_sha") or _attempt_head(attempt))
    allow_missing = bool(context.get("allow_missing_evidence", False))
    if not allow_missing:
        evidence = [
            item
            for item in workspace.evidence_runs
            if item.attempt_id == attempt_id and item.head_sha == head_sha
        ]
        if not evidence:
            blockers.append(
                TransitionBlocker(
                    "EVIDENCE_MISSING",
                    f"attempt {attempt_id} cannot close out without evidence for head {head_sha}",
                    (
                        "palari evidence record EVIDENCE-ID "
                        f"--work-item-id {attempt.work_item_id} --attempt-id {attempt_id} "
                        f"--head-sha {head_sha} --status passed --json"
                    ),
                )
            )
    next_commands.append(f"palari attempt closeout {attempt_id} --json")


def _check_evidence_record(
    workspace: Workspace,
    evidence_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    work_id = str(context.get("work_item_id") or "")
    attempt_id = str(context.get("attempt_id") or "")
    head_sha = str(context.get("head_sha") or "")
    work = workspace.work_item(work_id)
    attempt = _attempt(workspace, attempt_id)
    if work is None:
        blockers.append(TransitionBlocker("WORK_MISSING", f"work not found: {work_id}"))
    if attempt is None:
        blockers.append(TransitionBlocker("ATTEMPT_MISSING", f"attempt not found: {attempt_id}"))
        return
    if work is not None and attempt.work_item_id != work.id:
        blockers.append(
            TransitionBlocker(
                "ATTEMPT_WORK_MISMATCH",
                f"attempt {attempt_id} belongs to {attempt.work_item_id}, not {work.id}",
            )
        )
    attempt_head = _attempt_head(attempt)
    if head_sha and attempt_head and head_sha != attempt_head:
        blockers.append(
            TransitionBlocker(
                "EVIDENCE_STALE_HEAD",
                f"evidence {evidence_id} head {head_sha} does not match attempt head {attempt_head}",
            )
        )
    if _evidence(workspace, evidence_id) is not None and not context.get("allow_existing"):
        blockers.append(TransitionBlocker("EVIDENCE_EXISTS", f"evidence already exists: {evidence_id}"))
    next_commands.append(
        f"palari evidence record {evidence_id or 'EVIDENCE-ID'} "
        f"--work-item-id {work_id or 'WORK-ID'} --attempt-id {attempt_id or 'ATTEMPT-ID'} --json"
    )


def _check_review_record(
    workspace: Workspace,
    review_id: str,
    reviewer_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    work_id = str(context.get("work_item_id") or "")
    reviewed_head = str(context.get("reviewed_head") or "")
    verdict = str(context.get("verdict") or "")
    work = workspace.work_item(work_id)
    if work is None:
        blockers.append(TransitionBlocker("WORK_MISSING", f"work not found: {work_id}"))
        return
    if _review(workspace, review_id) is not None and not context.get("allow_existing"):
        blockers.append(TransitionBlocker("REVIEW_EXISTS", f"review already exists: {review_id}"))
    if workspace.human(reviewer_id) is None:
        blockers.append(
            TransitionBlocker("REVIEWER_MISSING", f"reviewer must be an existing human: {reviewer_id}")
        )
    current_attempt = current_attempt_for_work(work, workspace.attempts)
    if current_attempt is not None and current_attempt.actor == reviewer_id:
        blockers.append(
            TransitionBlocker(
                "REVIEWER_NOT_INDEPENDENT",
                f"reviewer {reviewer_id} is also attempt actor {current_attempt.actor}",
            )
        )
    if verdict == "accept-ready":
        binding, proof_errors = current_review_binding(workspace, work_id)
        if proof_errors:
            blockers.append(
                TransitionBlocker(
                    "EXACT_PROOF_NOT_READY",
                    "accept-ready review requires complete exact proof: "
                    + "; ".join(proof_errors),
                    f"palari agent doctor {work_id} --as PALARI-ID --mode review --json",
                )
            )
        elif binding.get("attempt_id") and binding.get("evidence_reference"):
            evidence = _evidence(workspace, binding["evidence_reference"])
            if evidence is None or evidence.head_sha != reviewed_head:
                blockers.append(
                    TransitionBlocker(
                        "REVIEWED_HEAD_MISMATCH",
                        f"review head {reviewed_head} does not match current exact proof head",
                    )
                )
    next_commands.append(
        f"palari review record {review_id or 'REVIEW-ID'} "
        f"--work-item-id {work_id} --reviewed-head {reviewed_head or 'HEAD'} --verdict VERDICT --json"
    )


def _check_human_decision_accept(
    workspace: Workspace,
    decision_id: str,
    human_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    work_id = str(context.get("work_item_id") or "")
    reviewed_head = str(context.get("reviewed_head") or "")
    _check_acceptance_prerequisites(
        workspace,
        work_id,
        human_id,
        reviewed_head,
        blockers,
        next_commands,
        transition_id=decision_id,
    )


def _check_work_accept(
    workspace: Workspace,
    work_id: str,
    human_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    reviewed_head = str(context.get("reviewed_head") or "")
    _check_acceptance_prerequisites(
        workspace,
        work_id,
        human_id,
        reviewed_head,
        blockers,
        next_commands,
        transition_id=work_id,
    )


def _check_acceptance_prerequisites(
    workspace: Workspace,
    work_id: str,
    human_id: str,
    reviewed_head: str,
    blockers: list[TransitionBlocker],
    next_commands: list[str],
    *,
    transition_id: str,
) -> None:
    work = workspace.work_item(work_id)
    human = workspace.human(human_id)
    if work is None:
        blockers.append(TransitionBlocker("WORK_MISSING", f"work not found: {work_id}"))
        return
    if human is None:
        blockers.append(TransitionBlocker("HUMAN_MISSING", f"human not found: {human_id}"))
        return
    if work.required_approval_capability and (
        work.required_approval_capability not in human.approval_capabilities
    ):
        blockers.append(
            TransitionBlocker(
                "HUMAN_LACKS_CAPABILITY",
                f"human {human_id} lacks required approval capability {work.required_approval_capability}",
            )
        )
    open_decisions = [
        decision.id
        for decision in workspace.decisions
        if decision.linked_work == work_id and decision.status == "open"
    ]
    if open_decisions:
        blockers.append(
            TransitionBlocker(
                "OPEN_DECISIONS",
                f"work {work_id} has open decisions: {', '.join(open_decisions)}",
            )
        )
    work_detail = detail(workspace, work_id)
    if work_detail.get("coordination_warnings"):
        blockers.append(
            TransitionBlocker("SCOPE_OVERLAP", f"work {work_id} has scope coordination warnings")
        )
    attempt = current_attempt_for_work(work, workspace.attempts)
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    review = latest_for_work(workspace.review_verdicts, work_id)
    if attempt is None:
        blockers.append(TransitionBlocker("ATTEMPT_MISSING", f"work {work_id} has no attempt"))
        return
    if attempt.cleanliness.lower() in {"dirty", "unclean"}:
        blockers.append(
            TransitionBlocker("ATTEMPT_DIRTY", f"work {work_id} attempt {attempt.id} is dirty")
        )
    attempt_head = _attempt_head(attempt)
    if evidence is None:
        blockers.append(
            TransitionBlocker(
                "EVIDENCE_MISSING",
                f"work {work_id} has no evidence",
                f"palari evidence record EVIDENCE-ID --work-item-id {work_id} --json",
            )
        )
    elif evidence.status != "passed":
        blockers.append(
            TransitionBlocker("EVIDENCE_NOT_PASSED", f"work {work_id} evidence is {evidence.status}")
        )
    elif evidence.head_sha != attempt_head:
        blockers.append(TransitionBlocker("EVIDENCE_STALE", f"work {work_id} evidence is stale"))
    if review is None:
        blockers.append(
            TransitionBlocker(
                "REVIEW_MISSING",
                f"work {work_id} has no review",
                f"palari review guide {work_id} --json",
            )
        )
    elif review.verdict != "accept-ready":
        blockers.append(
            TransitionBlocker("REVIEW_NOT_READY", f"work {work_id} review is {review.verdict}")
        )
    elif evidence is not None and review.reviewed_head != evidence.head_sha:
        blockers.append(TransitionBlocker("REVIEW_STALE", f"work {work_id} review is stale"))
    elif review is not None:
        binding_errors = current_review_binding_errors(workspace, review)
        if binding_errors:
            blockers.append(
                TransitionBlocker(
                    "REVIEW_PROOF_STALE",
                    f"work {work_id} review proof is stale: {binding_errors[0]}",
                    f"palari review guide {work_id} --json",
                )
            )
    if reviewed_head and review is not None and reviewed_head != review.reviewed_head:
        blockers.append(
            TransitionBlocker(
                "REVIEWED_HEAD_MISMATCH",
                f"human decision head {reviewed_head} does not match reviewed head {review.reviewed_head}",
            )
        )
    if not reviewed_head:
        blockers.append(
            TransitionBlocker(
                "REVIEWED_HEAD_MISSING",
                f"{transition_id} requires reviewed_head",
            )
        )
    next_commands.append(
        f"palari work accept {work_id} --by HUMAN-ID --reviewed-head HEAD --json"
    )


def _check_work_complete(
    workspace: Workspace,
    work_id: str,
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    work = workspace.work_item(work_id)
    if work is None:
        blockers.append(TransitionBlocker("WORK_MISSING", f"work not found: {work_id}"))
        return
    from .governance_kernel import evaluate_governance_case
    from .pcaw_workspace import governance_case_from_workspace

    governance_case, _ = governance_case_from_workspace(workspace, work_id)
    low_risk_receipt_path = work.risk in {"R1", "R2"} and work.required_approval_count == 0
    if low_risk_receipt_path:
        governance_case = replace(
            governance_case,
            claimed_state="completed",
            contract=replace(governance_case.contract, status="completed"),
        )
    else:
        governance_case = replace(governance_case, claimed_state="accepted")
    governance = evaluate_governance_case(governance_case)
    # Legacy v2 workspaces may omit PCAW-only artifact coverage and stage
    # timestamps. Existing gates below remain authoritative for those records;
    # their exported proof is honestly not acceptance-verified until refreshed.
    compatibility_only = {
        "PCAW_EVIDENCE_OUTPUT_UNHASHED",
        "PCAW_REVIEW_PREREQUISITE_INVALID",
        "PCAW_ACCEPTANCE_PREREQUISITE_INVALID",
        "PCAW_LIFECYCLE_ORDER_INVALID",
        "PCAW_EVIDENCE_RECEIPT_INVALID",
        "PCAW_CLAIMED_STATE_MISMATCH",
    }
    kernel_errors = [
        item for item in governance.errors if item.code not in compatibility_only
    ]
    if low_risk_receipt_path:
        kernel_errors = []
    if governance.derived_state not in {"accepted", "completed"} and kernel_errors:
        first_error = kernel_errors[0]
        blockers.append(
            TransitionBlocker(
                "GOVERNANCE_PROOF_INCOMPLETE",
                (
                    first_error.message
                    if first_error is not None
                    else f"governance kernel derives {governance.derived_state}"
                ),
                (
                    first_error.next_action
                    if first_error is not None
                    else f"palari agent doctor {work_id} --json"
                ),
            )
        )
    work_detail = detail(workspace, work_id)
    attempt = current_attempt_for_work(work, workspace.attempts)
    if not low_risk_receipt_path:
        if attempt is None or attempt.status not in {"complete", "completed"}:
            blockers.append(
                TransitionBlocker("ATTEMPT_NOT_COMPLETE", "current attempt is not complete")
            )
        elif attempt.cleanliness.lower() not in {"clean", "pristine"}:
            blockers.append(
                TransitionBlocker("ATTEMPT_NOT_CLEAN", "current attempt is not recorded clean")
            )
        review = latest_for_work(workspace.review_verdicts, work_id)
        if review is None:
            blockers.append(TransitionBlocker("REVIEW_MISSING", "current review is missing"))
        else:
            binding_errors = current_review_binding_errors(workspace, review)
            if binding_errors:
                blockers.append(
                    TransitionBlocker(
                        "REVIEW_PROOF_STALE",
                        f"current review proof is stale: {binding_errors[0]}",
                    )
                )
    attention = work_detail.get("attention")
    integration_state = work_detail.get("safety", {}).get("integration_state")
    if attention == "blocked":
        blockers.append(
            TransitionBlocker("WORK_BLOCKED", str(work_detail.get("why") or "work is blocked"))
        )
    if integration_state not in {"ready", "receipt-ready"}:
        blockers.append(
            TransitionBlocker(
                "INTEGRATION_NOT_READY",
                f"integration_state is {integration_state}",
                str(work_detail.get("next_commands", [""])[0] if work_detail.get("next_commands") else ""),
            )
        )
    next_commands.extend(str(command) for command in work_detail.get("next_commands", []))


def _check_integration_enqueue(
    workspace: Workspace,
    plan_id: str,
    human_id: str,
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    plan = workspace.integration_plan(plan_id)
    human = workspace.human(human_id)
    if plan is None:
        blockers.append(TransitionBlocker("PLAN_MISSING", f"integration plan not found: {plan_id}"))
        return
    if plan.status != "approved":
        blockers.append(
            TransitionBlocker(
                "PLAN_NOT_APPROVED",
                f"integration plan {plan_id} must be approved before enqueue; status is {plan.status}",
                f"palari integration approve {plan_id} --by HUMAN-ID --reason REASON --json",
            )
        )
    if human is None:
        blockers.append(TransitionBlocker("HUMAN_MISSING", f"human not found: {human_id}"))
    if any(item.plan_id == plan.id for item in workspace.integration_outbox):
        blockers.append(
            TransitionBlocker("OUTBOX_EXISTS", f"integration plan {plan.id} is already enqueued")
        )
    next_commands.append(f"palari integration enqueue {plan_id} --by HUMAN-ID --json")


def _check_integration_send(
    workspace: Workspace,
    outbox_id: str,
    human_id: str,
    context: dict[str, Any],
    blockers: list[TransitionBlocker],
    next_commands: list[str],
) -> None:
    item = workspace.integration_outbox_item(outbox_id)
    if item is None:
        blockers.append(
            TransitionBlocker("OUTBOX_MISSING", f"integration outbox item not found: {outbox_id}")
        )
        return
    plan = workspace.integration_plan(item.plan_id)
    integration = workspace.integration(item.integration_id)
    work = workspace.work_item(item.work_item_id)
    human = workspace.human(human_id)
    if plan is None or integration is None or work is None:
        blockers.append(
            TransitionBlocker(
                "BROKEN_REFERENCES",
                f"integration outbox item {outbox_id} has broken references",
            )
        )
        return
    if human is None:
        blockers.append(TransitionBlocker("HUMAN_MISSING", f"human not found: {human_id}"))
    if item.status != "queued":
        blockers.append(
            TransitionBlocker("OUTBOX_NOT_QUEUED", f"outbox status is {item.status}; expected queued")
        )
    if plan.status != "approved":
        blockers.append(
            TransitionBlocker("PLAN_NOT_APPROVED", "outbox execution requires an approved plan")
        )
    if item.payload_preview != plan.payload_preview:
        blockers.append(
            TransitionBlocker("PAYLOAD_DRIFT", "payload preview drifted from the approved plan")
        )
    if item.source_boundary != plan.source_boundary:
        blockers.append(
            TransitionBlocker("SOURCE_BOUNDARY_DRIFT", "source boundary drifted from the approved plan")
        )
    provider = str(context.get("provider") or "")
    action = str(context.get("action") or "")
    if provider and integration.provider != provider:
        blockers.append(
            TransitionBlocker(
                "PROVIDER_MISMATCH",
                f"integration provider is {integration.provider}, not {provider}",
            )
        )
    if action and item.action != action:
        blockers.append(
            TransitionBlocker("ACTION_MISMATCH", f"outbox action is {item.action}, not {action}")
        )
    next_commands.append(f"palari linear send {outbox_id} --by HUMAN-ID --confirm --json")


def _matching_fresh_passed_evidence(workspace: Workspace, work: Any, head_sha: str) -> Any | None:
    current_attempt = current_attempt_for_work(work, workspace.attempts)
    current_attempt_id = current_attempt.id if current_attempt is not None else ""
    current_head = _attempt_head(current_attempt) if current_attempt is not None else ""
    for evidence in reversed(workspace.evidence_runs):
        if (
            evidence.work_item_id == work.id
            and evidence.head_sha == head_sha
            and evidence.status == "passed"
            and (not current_attempt_id or evidence.attempt_id == current_attempt_id)
            and (not current_head or evidence.head_sha == current_head)
        ):
            return evidence
    return None


def _attempt(workspace: Workspace, attempt_id: str) -> Any | None:
    return next((attempt for attempt in workspace.attempts if attempt.id == attempt_id), None)


def _evidence(workspace: Workspace, evidence_id: str) -> Any | None:
    return next((evidence for evidence in workspace.evidence_runs if evidence.id == evidence_id), None)


def _review(workspace: Workspace, review_id: str) -> Any | None:
    return next((review for review in workspace.review_verdicts if review.id == review_id), None)


def _attempt_head(attempt: Any) -> str:
    return attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")


def _first_next_command(packet: dict[str, Any]) -> str:
    commands = packet.get("next_allowed_commands")
    if isinstance(commands, list) and commands and isinstance(commands[0], str):
        return commands[0]
    return ""


def _unique(commands: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for command in commands:
        if not command or command in seen:
            continue
        result.append(command)
        seen.add(command)
    return result

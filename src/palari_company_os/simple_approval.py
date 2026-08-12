from __future__ import annotations

from typing import Any, Callable

from .authority_plan import build_authority_plan
from .approval_packs import (
    apply_pack_decision,
    build_approval_inbox,
    validate_pack_manifest,
)
from .approval_presentations import approval_presentation_digest
from .errors import WorkspaceError
from .governance_kernel import TERMINAL_WORK_STATUSES
from .governance_journal import (
    pending_workspace_journal_context,
    utc_timestamp,
    verify_journal,
    workspace_digest,
)
from .pcaw_workspace import evaluate_workspace_human_authority_candidate
from .store import load_store, validate_data
from .workspace import (
    Workspace,
    current_attempt_for_work,
    latest_for_work,
)


RESULT_SCHEMA_VERSION = "palari.simple-approval-result.v1"
ERROR_SCHEMA_VERSION = "palari.simple-approval-error.v1"


class SimpleApprovalError(WorkspaceError):
    """A stable, actionable failure from the ordinary approval front door."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        next_action: str,
        work_id: str = "",
        human_id: str = "",
        next_allowed_commands: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.next_action = next_action
        self.work_id = work_id
        self.human_id = human_id
        self.next_allowed_commands = list(
            next_allowed_commands
            if next_allowed_commands is not None
            else _default_next_commands(work_id)
        )


def approve_work(
    workspace_path: str,
    work_id: str,
    human_id: str,
    *,
    reason: str = "",
    presented_digest: str = "",
    crash_hook: Callable[[str], None] | None = None,
    _before_apply: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Approve and complete one current, reversible local task.

    This intentionally derives the exact singleton Approval Pack and decision
    presentation internally. The existing pack-decision primitive remains the
    only mutation path.
    """

    work_id = work_id.strip()
    human_id = human_id.strip()
    if not work_id:
        raise _error(
            "ARGUMENT_PARSE_ERROR",
            "approval requires a task id",
            "Pass exactly one task id to `palari approve`.",
            work_id=work_id,
            human_id=human_id,
        )
    if not human_id:
        raise _error(
            "ARGUMENT_PARSE_ERROR",
            "approval requires an acting human id",
            "Pass the acting human with `--as HUMAN-ID`.",
            work_id=work_id,
            human_id=human_id,
        )

    store, workspace = _load_workspace(workspace_path, work_id, human_id)
    journal = verify_journal(store.data_path, store.data)
    if journal.get("pending"):
        return _recover_pending_approval(
            workspace_path,
            work_id,
            human_id,
            journal,
            presented_digest=presented_digest,
        )
    _require_current_journal(journal, store.data, work_id, human_id)

    work = workspace.work_item(work_id)
    if work is None:
        raise _error(
            "APPROVAL_WORK_NOT_FOUND",
            f"task not found: {work_id}",
            "Choose a task shown by `palari queue --json`.",
            work_id=work_id,
            human_id=human_id,
        )
    human = workspace.human(human_id)
    if human is None:
        raise _error(
            "APPROVAL_HUMAN_NOT_FOUND",
            f"human not found: {human_id}",
            "Use a declared human identity with approval authority.",
            work_id=work_id,
            human_id=human_id,
        )

    replay = _existing_exact_completion(workspace, work_id, human_id)
    if replay is not None:
        bound_presentation = str(
            replay.get("details", {}).get("presentation_digest") or ""
        )
        if presented_digest and presented_digest != bound_presentation:
            raise _error(
                "APPROVAL_STATE_CHANGED",
                f"the presented approval state for completed task {work_id} is not its bound state",
                "Inspect the stored approval presentation before retrying.",
                work_id=work_id,
                human_id=human_id,
            )
        return replay
    if work.status in TERMINAL_WORK_STATUSES:
        raise _error(
            "APPROVAL_ALREADY_COMPLETED",
            f"task {work_id} is already terminal and was not approved by {human_id}",
            "Inspect the existing acceptance and decision records; do not create another approval.",
            work_id=work_id,
            human_id=human_id,
        )
    if human.availability == "inactive":
        raise _error(
            "APPROVAL_HUMAN_INACTIVE",
            f"human {human_id} is inactive",
            "Use an active human with the required approval capability.",
            work_id=work_id,
            human_id=human_id,
        )
    attempt = current_attempt_for_work(work, workspace.attempts)
    preliminary_plan = build_authority_plan(
        workspace,
        work_id,
        builder_id=attempt.actor if attempt is not None else "",
    )
    if not preliminary_plan["requires_human_approval"]:
        raise _error(
            "APPROVAL_NOT_REQUIRED",
            f"task {work_id} does not require human approval",
            "Use the task's normal deterministic completion path.",
            work_id=work_id,
            human_id=human_id,
        )
    if (
        work.required_approval_capability
        and work.required_approval_capability not in human.approval_capabilities
    ):
        raise _error(
            "APPROVAL_HUMAN_UNQUALIFIED",
            (
                f"human {human_id} lacks required approval capability "
                f"{work.required_approval_capability} for {work_id}"
            ),
            "Use an active human with the task's required approval capability.",
            work_id=work_id,
            human_id=human_id,
        )

    inbox = _build_singleton_inbox(workspace, store.data, work_id, human_id)
    item, pack, presentation = _singleton_parts(inbox, work_id, human_id)
    presentation_digest = approval_presentation_digest(presentation, pack)
    if presented_digest and presented_digest != presentation_digest:
        raise _error(
            "APPROVAL_STATE_CHANGED",
            f"the presented approval state for {work_id} is no longer current",
            "Inspect a fresh agent status before approving the changed task state.",
            work_id=work_id,
            human_id=human_id,
        )
    member = pack["members"][0]
    _require_local_reversible(member, pack, work_id, human_id)
    _require_ready_item(item, work_id, human_id)

    review = latest_for_work(workspace.review_verdicts, work_id)
    if attempt is None or review is None:
        raise _error(
            "APPROVAL_REVIEW_REQUIRED",
            f"task {work_id} lacks a current independently reviewed run",
            "Finish current checks and obtain a distinct accept-ready review.",
            work_id=work_id,
            human_id=human_id,
        )
    if human_id in {attempt.actor, review.reviewer}:
        role = "builder" if human_id == attempt.actor else "reviewer"
        raise _error(
            "APPROVAL_IDENTITY_COLLISION",
            f"human {human_id} is the current {role} for {work_id}",
            "Use a qualified human who is distinct from both builder and reviewer.",
            work_id=work_id,
            human_id=human_id,
        )

    _require_authority_plan(
        workspace,
        work_id,
        human_id,
        builder_id=attempt.actor,
        reviewer_id=review.reviewer,
    )
    _require_completing_quorum(
        workspace,
        work_id,
        human_id,
        reviewed_head=review.reviewed_head,
    )

    if _before_apply is not None:
        _before_apply()
    try:
        result = apply_pack_decision(
            workspace_path,
            pack_digest=str(pack["pack_digest"]),
            presentation_digest=presentation_digest,
            human_id=human_id,
            approve_eligible=True,
            pack_members=[work_id],
            reason=reason,
            command="approve",
            crash_hook=crash_hook,
        )
    except WorkspaceError as exc:
        raise _mapped_pack_error(exc, work_id, human_id) from exc
    return _normalize_result(result, work_id, human_id)


def _load_workspace(
    workspace_path: str,
    work_id: str,
    human_id: str,
) -> tuple[Any, Workspace]:
    try:
        store = load_store(workspace_path)
        workspace = validate_data(store.data_path, store.data)
    except WorkspaceError as exc:
        message = str(exc)
        code = (
            "WORKSPACE_FILE_NOT_FOUND"
            if "workspace file not found" in message.lower()
            else "APPROVAL_WORKSPACE_INVALID"
        )
        raise _error(
            code,
            message,
            "Repair or select a valid Palari workspace before approving.",
            work_id=work_id,
            human_id=human_id,
        ) from exc
    return store, workspace


def _require_current_journal(
    report: dict[str, Any],
    raw_data: dict[str, Any],
    work_id: str,
    human_id: str,
) -> None:
    current_digest = workspace_digest(raw_data)
    if (
        not report.get("chain_valid")
        or report.get("pending")
        or report.get("replay_workspace_digest") != current_digest
    ):
        diagnostics = report.get("diagnostics")
        diagnostic: dict[str, Any] = (
            next(
                (
                    item
                    for item in diagnostics
                    if isinstance(item, dict)
                ),
                {},
            )
            if isinstance(diagnostics, list)
            else {}
        )
        message = str(
            diagnostic.get("message")
            or "governance history is not a current committed projection"
        )
        next_action = str(
            diagnostic.get("next_action")
            or "Run `palari history --json`, then repair or recover governance history."
        )
        raise _error(
            "APPROVAL_HISTORY_INVALID",
            message,
            next_action,
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=[
                "palari history --json",
                "palari validate --json",
            ],
        )


def _build_singleton_inbox(
    workspace: Workspace,
    raw_data: dict[str, Any],
    work_id: str,
    human_id: str,
) -> dict[str, Any]:
    try:
        return build_approval_inbox(
            workspace,
            raw_data,
            selected_work_ids=(work_id,),
        )
    except WorkspaceError as exc:
        raise _mapped_pack_error(exc, work_id, human_id) from exc


def _singleton_parts(
    inbox: dict[str, Any],
    work_id: str,
    human_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    items = inbox.get("individual_items")
    packs = inbox.get("packs")
    presentations = inbox.get("presentations")
    evaluations = inbox.get("evaluations")
    if (
        not isinstance(items, list)
        or not isinstance(packs, list)
        or not isinstance(presentations, list)
        or not isinstance(evaluations, list)
        or len(items) != 1
        or len(packs) != 1
        or len(presentations) != 1
        or len(evaluations) != 1
    ):
        raise _error(
            "APPROVAL_SELECTION_AMBIGUOUS",
            f"approval did not resolve to exactly one task and one pack for {work_id}",
            "Refresh the selected task; use the advanced Approval Inbox for multi-item decisions.",
            work_id=work_id,
            human_id=human_id,
        )
    item, pack, presentation = items[0], packs[0], presentations[0]
    members = pack.get("members") if isinstance(pack, dict) else None
    if (
        not isinstance(item, dict)
        or item.get("id") != work_id
        or not isinstance(members, list)
        or len(members) != 1
        or not isinstance(members[0], dict)
        or members[0].get("id") != work_id
        or pack.get("execution_order") != [work_id]
        or not isinstance(presentation, dict)
    ):
        raise _error(
            "APPROVAL_SELECTION_AMBIGUOUS",
            f"approval pack selection is not the exact singleton {work_id}",
            "Rebuild a one-task Approval Inbox selection before approving.",
            work_id=work_id,
            human_id=human_id,
        )
    return item, pack, presentation


def _require_local_reversible(
    member: dict[str, Any],
    pack: dict[str, Any],
    work_id: str,
    human_id: str,
) -> None:
    external_effects = list(pack.get("external_effects") or [])
    external_effects.extend(member.get("external_effects") or [])
    raw_action = member.get("action")
    action: dict[str, Any] = raw_action if isinstance(raw_action, dict) else {}
    raw_batch_policy = member.get("batch_policy")
    batch_policy: dict[str, Any] = (
        raw_batch_policy if isinstance(raw_batch_policy, dict) else {}
    )
    if (
        external_effects
        or action.get("external")
        or batch_policy.get("class") == "external-effect"
    ):
        raise _error(
            "APPROVAL_EXTERNAL_ACTION",
            f"task {work_id} declares an external effect",
            "Keep it parked and use its explicit integration or individual-effect approval path.",
            work_id=work_id,
            human_id=human_id,
        )
    raw_reversibility = member.get("reversibility")
    reversibility: dict[str, Any] = (
        raw_reversibility if isinstance(raw_reversibility, dict) else {}
    )
    if (
        reversibility.get("class") != "reversible-local"
        or action.get("irreversible")
    ):
        raise _error(
            "APPROVAL_NOT_REVERSIBLE",
            f"task {work_id} is not classified as reversible local work",
            "Keep it parked and use its explicit individual authority path.",
            work_id=work_id,
            human_id=human_id,
        )
    if not batch_policy.get("batchable"):
        raise _error(
            "APPROVAL_NON_BATCHABLE",
            f"task {work_id} is {batch_policy.get('class', 'non-batchable')}",
            "Keep it parked and use the advanced individual authority path.",
            work_id=work_id,
            human_id=human_id,
        )


def _require_ready_item(
    item: dict[str, Any],
    work_id: str,
    human_id: str,
) -> None:
    state = str(item.get("state") or "")
    if state in {"eligible", "approved"}:
        return
    reasons = [str(reason) for reason in item.get("reasons") or []]
    reason_text = "; ".join(reasons) or f"state is {state or 'unknown'}"
    lowered = reason_text.lower()
    if state == "stale":
        code = "APPROVAL_PROOF_STALE"
        next_action = "Refresh checks and independent review against the current exact task state."
    elif any(
        token in lowered
        for token in (
            "artifact",
            "evidence",
            "manifest",
            "output",
            "receipt",
            "subject digest",
        )
    ):
        code = "APPROVAL_PROOF_INVALID"
        next_action = "Repair exact proof, rerun checks, and obtain a fresh review."
    elif "review" in lowered or "reviewer" in lowered:
        code = "APPROVAL_REVIEW_REQUIRED"
        next_action = "Obtain a fresh accept-ready review from a distinct reviewer."
    else:
        code = "APPROVAL_PROOF_INVALID"
        next_action = "Repair the listed proof blockers, rerun checks, and obtain a fresh review."
    raise _error(
        code,
        f"task {work_id} is not approval-ready: {reason_text}",
        next_action,
        work_id=work_id,
        human_id=human_id,
    )


def _require_authority_plan(
    workspace: Workspace,
    work_id: str,
    human_id: str,
    *,
    builder_id: str,
    reviewer_id: str,
) -> None:
    from .authority_plan import build_authority_plan

    try:
        plan = build_authority_plan(
            workspace,
            work_id,
            builder_id=builder_id,
            reviewer_id=reviewer_id,
        )
    except WorkspaceError as exc:
        raise _error(
            "APPROVAL_AUTHORITY_PLAN_BLOCKED",
            str(exc),
            "Repair the task's builder, reviewer, and qualified-approver assignments.",
            work_id=work_id,
            human_id=human_id,
        ) from exc
    if not bool(plan.get("viable")):
        details = plan.get("diagnostic")
        message = (
            str(details.get("message") or "")
            if isinstance(details, dict)
            else str(plan.get("message") or "")
        )
        next_action = (
            str(details.get("next_action") or "")
            if isinstance(details, dict)
            else str(plan.get("smallest_correction") or "")
        )
        raise _error(
            "APPROVAL_AUTHORITY_PLAN_BLOCKED",
            message or f"task {work_id} has no viable independent approval plan",
            next_action
            or "Assign a distinct reviewer and retain an active qualified human approver.",
            work_id=work_id,
            human_id=human_id,
        )
    qualified = {
        str(candidate)
        for candidate in plan.get("qualified_approver_ids", [])
        if str(candidate)
    }
    if human_id not in qualified:
        raise _error(
            "APPROVAL_HUMAN_UNQUALIFIED",
            f"human {human_id} is not a qualified remaining approver for {work_id}",
            "Use an active qualified approver listed by the task authority plan.",
            work_id=work_id,
            human_id=human_id,
        )


def _require_completing_quorum(
    workspace: Workspace,
    work_id: str,
    human_id: str,
    *,
    reviewed_head: str,
) -> None:
    timestamp = utc_timestamp()
    decision_id = f"CANDIDATE-SIMPLE-DECISION-{work_id}-{human_id}"
    try:
        candidate = evaluate_workspace_human_authority_candidate(
            workspace,
            work_id,
            decision_id=decision_id,
            human_id=human_id,
            reviewed_head=reviewed_head,
            timestamp=timestamp,
            acceptance_mode="approval-pack",
            decision_value="accepted",
            decision_status="accepted",
        )
    except WorkspaceError as exc:
        raise _error(
            "APPROVAL_PROOF_INVALID",
            str(exc),
            "Repair current proof and review before retrying approval.",
            work_id=work_id,
            human_id=human_id,
        ) from exc
    if not candidate.decision_allowed:
        message = (
            candidate.errors[0].message
            if candidate.errors
            else "the proposed approval is not current qualified authority"
        )
        raise _error(
            "APPROVAL_PROOF_INVALID",
            message,
            "Refresh exact checks and review, then retry with a qualified distinct human.",
            work_id=work_id,
            human_id=human_id,
        )
    if not candidate.quorum_met:
        raise _error(
            "APPROVAL_QUORUM_INCOMPLETE",
            f"one approval from {human_id} cannot complete the required quorum for {work_id}",
            "Collect the missing distinct qualified approval before using this one-step command.",
            work_id=work_id,
            human_id=human_id,
        )
    try:
        completion = evaluate_workspace_human_authority_candidate(
            workspace,
            work_id,
            decision_id=decision_id,
            human_id=human_id,
            reviewed_head=reviewed_head,
            timestamp=timestamp,
            acceptance_mode="approval-pack",
            decision_value="accepted",
            decision_status="accepted",
            acceptance_id=f"CANDIDATE-SIMPLE-ACCEPTANCE-{work_id}-{human_id}",
            accepted_at=timestamp,
            projected_terminal=True,
        )
    except WorkspaceError as exc:
        raise _error(
            "APPROVAL_NOT_READY",
            str(exc),
            "Repair current proof or authority blockers before retrying approval.",
            work_id=work_id,
            human_id=human_id,
        ) from exc
    if not completion.acceptance_allowed:
        message = (
            completion.errors[0].message
            if completion.errors
            else "the proposed approval cannot atomically complete the task"
        )
        raise _error(
            "APPROVAL_NOT_READY",
            message,
            "Repair the current proof or authority blocker before approving.",
            work_id=work_id,
            human_id=human_id,
        )


def _recover_pending_approval(
    workspace_path: str,
    work_id: str,
    human_id: str,
    journal: dict[str, Any],
    *,
    presented_digest: str,
) -> dict[str, Any]:
    pending = journal.get("pending") or {}
    if not journal.get("chain_valid") or pending.get("workspace_position") not in {
        "before",
        "after",
    }:
        raise _error(
            "APPROVAL_HISTORY_INVALID",
            "governance history has an unsafe pending transaction",
            "Run `palari history --json` and recover the exact pending transaction.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    try:
        context = pending_workspace_journal_context(workspace_path)
    except Exception as exc:
        raise _error(
            "APPROVAL_HISTORY_INVALID",
            f"cannot inspect pending governance transaction: {exc}",
            "Run `palari history --json` and recover the exact pending transaction.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        ) from exc
    if context is None:
        raise _error(
            "APPROVAL_STATE_CHANGED",
            "the pending governance transaction changed during approval recovery",
            "Retry approval against the current workspace state.",
            work_id=work_id,
            human_id=human_id,
        )
    prepare = context.get("prepare")
    before = context.get("before_projection")
    after = prepare.get("after_projection") if isinstance(prepare, dict) else None
    metadata = prepare.get("metadata") if isinstance(prepare, dict) else None
    if (
        not isinstance(prepare, dict)
        or not isinstance(before, dict)
        or not isinstance(after, dict)
        or not isinstance(metadata, dict)
        or metadata.get("command") != "approve"
        or metadata.get("action") != "approval-pack-decision"
        or metadata.get("actor") != human_id
    ):
        raise _error(
            "APPROVAL_STATE_CHANGED",
            "a different governance transaction is pending",
            "Recover or finish that exact transaction before approving another task.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    decision, acceptance = _validate_pending_delta(
        before,
        after,
        work_id,
        human_id,
    )
    pack = decision.get("approval_pack_manifest")
    presentation = decision.get("approval_presentation")
    if not isinstance(pack, dict) or not isinstance(presentation, dict):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval lacks its exact pack or presentation",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    _validate_stored_binding(
        pack,
        presentation,
        decision,
        work_id,
        human_id,
    )
    if (
        presented_digest
        and presented_digest != decision.get("approval_presentation_digest")
    ):
        raise _error(
            "APPROVAL_STATE_CHANGED",
            f"the presented approval state for {work_id} differs from the pending transaction",
            "Inspect the current handoff and governance history before retrying.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    try:
        result = apply_pack_decision(
            workspace_path,
            pack_digest=str(decision["approval_pack_digest"]),
            presentation_digest=str(decision["approval_presentation_digest"]),
            human_id=human_id,
            approve_eligible=True,
            pack_members=[work_id],
            reason=str(metadata.get("reason") or ""),
            command="approve",
        )
    except WorkspaceError as exc:
        raise _mapped_pack_error(exc, work_id, human_id) from exc
    normalized = _normalize_result(result, work_id, human_id)
    normalized["idempotent"] = True
    normalized["status"] = "already-approved"
    normalized["summary"] = f"{work_id} approval recovery completed without duplicate authority."
    normalized["details"]["recovered_pending_transaction"] = True
    normalized["details"]["acceptance_record"] = str(acceptance.get("id") or "")
    return normalized


def _validate_pending_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    work_id: str,
    human_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed = {"work_items", "human_decisions", "acceptance_records"}
    if set(before) != set(after) or any(
        before.get(key) != after.get(key) for key in before if key not in allowed
    ):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval changes objects outside the singleton approval boundary",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    before_decisions = before.get("human_decisions")
    after_decisions = after.get("human_decisions")
    before_acceptances = before.get("acceptance_records")
    after_acceptances = after.get("acceptance_records")
    if (
        not isinstance(before_decisions, list)
        or not isinstance(after_decisions, list)
        or after_decisions[:-1] != before_decisions
        or not isinstance(before_acceptances, list)
        or not isinstance(after_acceptances, list)
        or after_acceptances[:-1] != before_acceptances
    ):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval does not append exactly one decision and acceptance",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    if len(after_decisions) != len(before_decisions) + 1 or len(
        after_acceptances
    ) != len(before_acceptances) + 1:
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval has an unexpected authority-record count",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    decision = after_decisions[-1]
    acceptance = after_acceptances[-1]
    if not isinstance(decision, dict) or not isinstance(acceptance, dict):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval authority records are malformed",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    _validate_decision_acceptance(decision, acceptance, work_id, human_id)

    before_work = before.get("work_items")
    after_work = after.get("work_items")
    if not isinstance(before_work, list) or not isinstance(after_work, list):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval task records are malformed",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    if len(before_work) != len(after_work):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval changes the task collection shape",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    changed = 0
    for prior, candidate in zip(before_work, after_work, strict=True):
        if prior == candidate:
            continue
        if (
            not isinstance(prior, dict)
            or not isinstance(candidate, dict)
            or prior.get("id") != work_id
            or candidate.get("id") != work_id
        ):
            raise _error(
                "APPROVAL_RETRY_INVALID",
                "pending approval changes an unrelated task",
                "Inspect and recover governance history before retrying approval.",
                work_id=work_id,
                human_id=human_id,
                next_allowed_commands=["palari history --json"],
            )
        normalized = dict(candidate)
        normalized["status"] = prior.get("status")
        if normalized != prior or candidate.get("status") != "completed":
            raise _error(
                "APPROVAL_RETRY_INVALID",
                "pending approval changes more than the target completion status",
                "Inspect and recover governance history before retrying approval.",
                work_id=work_id,
                human_id=human_id,
                next_allowed_commands=["palari history --json"],
            )
        changed += 1
    if changed != 1:
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "pending approval does not complete exactly the selected task",
            "Inspect and recover governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
            next_allowed_commands=["palari history --json"],
        )
    return decision, acceptance


def _existing_exact_completion(
    workspace: Workspace,
    work_id: str,
    human_id: str,
) -> dict[str, Any] | None:
    decisions = [
        decision
        for decision in workspace.human_decisions
        if decision.work_item_id == work_id
        and decision.human_id == human_id
        and decision.approval_pack_action == "approve"
    ]
    if not decisions:
        return None
    if len(decisions) != 1:
        raise _error(
            "APPROVAL_RETRY_INVALID",
            f"task {work_id} has ambiguous prior pack approvals from {human_id}",
            "Inspect the exact authority records before retrying.",
            work_id=work_id,
            human_id=human_id,
        )
    decision = decisions[0]
    acceptance_matches = [
        acceptance
        for acceptance in workspace.acceptance_records
        if acceptance.work_item_id == work_id
        and acceptance.human_id == human_id
        and acceptance.decision_id == decision.id
    ]
    work = workspace.work_item(work_id)
    if len(acceptance_matches) != 1 or work is None or work.status != "completed":
        raise _error(
            "APPROVAL_QUORUM_INCOMPLETE",
            f"prior approval from {human_id} did not atomically complete {work_id}",
            "Use the advanced Approval Pack flow to inspect or complete the remaining quorum.",
            work_id=work_id,
            human_id=human_id,
        )
    acceptance = acceptance_matches[0]
    raw_decision = _raw_model(decision)
    raw_acceptance = _raw_model(acceptance)
    _validate_decision_acceptance(
        raw_decision,
        raw_acceptance,
        work_id,
        human_id,
    )
    carriers = [
        candidate
        for candidate in workspace.human_decisions
        if candidate.approval_pack_digest == decision.approval_pack_digest
        and candidate.approval_pack_manifest
        and candidate.approval_presentation
    ]
    if len(carriers) != 1:
        raise _error(
            "APPROVAL_RETRY_INVALID",
            "prior approval lacks one exact stored pack presentation",
            "Inspect the existing approval records before retrying.",
            work_id=work_id,
            human_id=human_id,
        )
    carrier = carriers[0]
    _validate_stored_binding(
        carrier.approval_pack_manifest,
        carrier.approval_presentation,
        raw_decision,
        work_id,
        human_id,
    )
    return _success_payload(
        work_id,
        human_id,
        idempotent=True,
        decision_records=[decision.id],
        acceptance_records=[acceptance.id],
        pack_digest=decision.approval_pack_digest,
        presentation_digest=decision.approval_presentation_digest,
        performed_human_authority=False,
    )


def _validate_decision_acceptance(
    decision: dict[str, Any],
    acceptance: dict[str, Any],
    work_id: str,
    human_id: str,
) -> None:
    valid = (
        decision.get("work_item_id") == work_id
        and decision.get("human_id") == human_id
        and decision.get("approval_pack_action") == "approve"
        and decision.get("decision") == "accepted"
        and decision.get("status") == "accepted"
        and decision.get("acceptance_mode") == "approval-pack"
        and decision.get("quorum_status") == "met"
        and isinstance(decision.get("approval_pack_digest"), str)
        and isinstance(decision.get("approval_pack_request_digest"), str)
        and isinstance(decision.get("approval_presentation_digest"), str)
        and acceptance.get("work_item_id") == work_id
        and acceptance.get("human_id") == human_id
        and acceptance.get("decision_id") == decision.get("id")
        and acceptance.get("status") == "accepted"
        and acceptance.get("quorum_status") == "met"
        and acceptance.get("reviewed_head") == decision.get("reviewed_head")
        and acceptance.get("evidence_reference")
        == decision.get("evidence_reference")
        and acceptance.get("review_reference") == decision.get("review_reference")
    )
    if not valid:
        raise _error(
            "APPROVAL_RETRY_INVALID",
            f"prior approval records for {work_id} are incomplete or contradictory",
            "Inspect and repair governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
        )


def _validate_stored_binding(
    pack: dict[str, Any],
    presentation: dict[str, Any],
    decision: dict[str, Any],
    work_id: str,
    human_id: str,
) -> None:
    try:
        validate_pack_manifest(pack)
        digest = approval_presentation_digest(presentation, pack)
    except WorkspaceError as exc:
        raise _error(
            "APPROVAL_RETRY_INVALID",
            f"stored approval binding is invalid: {exc}",
            "Inspect and repair governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
        ) from exc
    members = pack.get("members") or []
    member = next(
        (
            candidate
            for candidate in members
            if isinstance(candidate, dict) and candidate.get("id") == work_id
        ),
        None,
    )
    if (
        member is None
        or decision.get("approval_pack_digest") != pack.get("pack_digest")
        or decision.get("approval_pack_member_digest") != member.get("member_digest")
        or decision.get("approval_pack_subject_digest") != member.get("subject_digest")
        or decision.get("approval_presentation_digest") != digest
    ):
        raise _error(
            "APPROVAL_RETRY_INVALID",
            f"stored approval binding does not match {work_id}",
            "Inspect and repair governance history before retrying approval.",
            work_id=work_id,
            human_id=human_id,
        )


def _normalize_result(
    result: dict[str, Any],
    work_id: str,
    human_id: str,
) -> dict[str, Any]:
    executed = [str(item) for item in result.get("executed") or []]
    if executed != [work_id]:
        raise _error(
            "APPROVAL_QUORUM_INCOMPLETE",
            f"approval did not atomically complete {work_id}",
            "Inspect the exact Approval Pack decision and remaining quorum before retrying.",
            work_id=work_id,
            human_id=human_id,
        )
    convergence = result.get("convergence")
    convergence = convergence if isinstance(convergence, dict) else {}
    return _success_payload(
        work_id,
        human_id,
        idempotent=bool(result.get("idempotent")),
        decision_records=[
            str(item)
            for item in (
                convergence.get("decision_records")
                or result.get("decisions")
                or []
            )
        ],
        acceptance_records=[
            str(item) for item in convergence.get("acceptance_records") or []
        ],
        pack_digest=str(result.get("pack_digest") or ""),
        presentation_digest=str(result.get("presentation_digest") or ""),
        performed_human_authority=bool(
            convergence.get("performed_human_authority")
        ),
    )


def _success_payload(
    work_id: str,
    human_id: str,
    *,
    idempotent: bool,
    decision_records: list[str],
    acceptance_records: list[str],
    pack_digest: str,
    presentation_digest: str,
    performed_human_authority: bool,
) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "already-approved" if idempotent else "approved",
        "work_item": work_id,
        "human": human_id,
        "approved": True,
        "completed": True,
        "idempotent": idempotent,
        "performed_external_effects": False,
        "summary": (
            f"{work_id} was already approved and completed; no authority was duplicated."
            if idempotent
            else f"{work_id} was approved and completed in one local transaction."
        ),
        "details": {
            "atomic_local_transaction": True,
            "performed_human_authority": performed_human_authority,
            "decision_records": decision_records,
            "acceptance_records": acceptance_records,
            "pack_digest": pack_digest,
            "presentation_digest": presentation_digest,
        },
    }


def _mapped_pack_error(
    exc: WorkspaceError,
    work_id: str,
    human_id: str,
) -> SimpleApprovalError:
    message = str(exc)
    lowered = message.lower()
    if "journal" in lowered or "history" in lowered:
        code = "APPROVAL_HISTORY_INVALID"
        next_action = "Run `palari history --json`, then repair or recover governance history."
    elif "presentation" in lowered or "workspace digest" in lowered or "stale" in lowered:
        code = "APPROVAL_STATE_CHANGED"
        next_action = "Refresh the task and retry approval against the current exact state."
    elif "distinct from builder and reviewer" in lowered:
        code = "APPROVAL_IDENTITY_COLLISION"
        next_action = "Use a qualified human distinct from builder and reviewer."
    elif "inactive" in lowered:
        code = "APPROVAL_HUMAN_INACTIVE"
        next_action = "Use an active qualified human."
    elif "capability" in lowered or "unqualified" in lowered:
        code = "APPROVAL_HUMAN_UNQUALIFIED"
        next_action = "Use an active human with the required approval capability."
    elif "quorum" in lowered:
        code = "APPROVAL_QUORUM_INCOMPLETE"
        next_action = "Collect the missing distinct qualified approval."
    elif "review" in lowered:
        code = "APPROVAL_REVIEW_REQUIRED"
        next_action = "Obtain a fresh accept-ready review from a distinct reviewer."
    elif "external" in lowered:
        code = "APPROVAL_EXTERNAL_ACTION"
        next_action = "Use the task's explicit external-action authority path."
    elif "not found" in lowered:
        code = "APPROVAL_WORK_NOT_FOUND"
        next_action = "Choose a task shown by `palari queue --json`."
    else:
        code = "APPROVAL_PROOF_INVALID"
        next_action = "Repair current proof and review before retrying approval."
    return _error(
        code,
        message,
        next_action,
        work_id=work_id,
        human_id=human_id,
    )


def _error(
    code: str,
    message: str,
    next_action: str,
    *,
    work_id: str,
    human_id: str,
    next_allowed_commands: list[str] | None = None,
) -> SimpleApprovalError:
    return SimpleApprovalError(
        code,
        message,
        next_action=next_action,
        work_id=work_id,
        human_id=human_id,
        next_allowed_commands=next_allowed_commands,
    )


def _default_next_commands(work_id: str) -> list[str]:
    if not work_id:
        return ["palari queue --json", "palari validate --json"]
    return [
        f"palari detail {work_id} --json",
        f"palari queue --approval-inbox --select {work_id} --json",
    ]


def _raw_model(value: Any) -> dict[str, Any]:
    return dict(vars(value))

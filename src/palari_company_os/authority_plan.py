from __future__ import annotations

from typing import Any

from .governance_kernel import (
    effective_required_approval_count,
    independent_review_required,
)
from .workspace import (
    Workspace,
    WorkspaceError,
    current_attempt_for_work,
    latest_for_work,
)


SCHEMA_VERSION = "palari.authority-plan.v1"


def build_authority_plan(
    workspace: Workspace,
    work_id: str,
    *,
    builder_id: str = "",
    reviewer_id: str = "",
) -> dict[str, Any]:
    """Return the deterministic builder, reviewer, and approver feasibility plan."""

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    attempt = current_attempt_for_work(work, workspace.attempts)
    receipt = latest_for_work(workspace.receipts, work.id)
    builder = builder_id or (attempt.actor if attempt is not None else "") or work.palari
    declared_count = work.required_approval_count
    required_capability = work.required_approval_capability
    policy_kwargs = {
        "risk": work.risk,
        "intensity": work.intensity,
        "required_approval_count": declared_count,
        "allowed_actions": work.allowed_actions,
        "external_writes": receipt.external_writes if receipt is not None else [],
        "planned_external_writes": (
            receipt.planned_external_writes if receipt is not None else []
        ),
        "queued_external_writes": (
            receipt.queued_external_writes if receipt is not None else []
        ),
    }
    requires_review = independent_review_required(**policy_kwargs)
    required_count = effective_required_approval_count(**policy_kwargs)
    requires_human_approval = required_count > 0
    available_approvers = _qualified_approver_ids(
        workspace,
        required_capability,
        excluded={builder},
    )
    options = [
        _reviewer_option(
            workspace,
            work,
            builder,
            reviewer,
            identity_type,
            required_count,
            required_capability,
            available_approvers,
        )
        for identity_type, reviewer in _reviewer_identities(workspace)
    ]
    option_by_id = {str(option["id"]): option for option in options}
    proposed = option_by_id.get(reviewer_id) if reviewer_id else None
    if reviewer_id and proposed is None:
        proposed = _rejected_option(
            reviewer_id,
            "unknown",
            required_count,
            "REVIEWER_MISSING",
            f"Reviewer {reviewer_id} is not a declared human or Palari.",
            "Add or select a declared reviewer distinct from the builder.",
        )
        options.append(proposed)

    viable_reviewers = [
        option for option in options if option["viable"]
    ]
    rejected_reviewers = [
        option for option in options if not option["viable"]
    ]
    builder_declared = bool(
        builder
        and (
            workspace.palari(builder) is not None
            or workspace.human(builder) is not None
        )
    )
    if not builder_declared:
        viable = False
        qualified_approvers = []
        approver_deficit = required_count
        code = "BUILDER_ROLE_MISSING"
        message = f"Builder {builder or '(missing)'} is not a declared human or Palari."
        correction = "Assign the task to one declared builder before work begins."
    elif proposed is not None:
        viable = bool(proposed["viable"])
        qualified_approvers = list(proposed["qualified_approver_ids"])
        approver_deficit = int(proposed["approver_deficit"])
        code = str(proposed["code"])
        message = str(proposed["message"])
        correction = str(proposed["smallest_correction"])
    elif not requires_review:
        qualified_approvers = available_approvers
        approver_deficit = max(0, required_count - len(available_approvers))
        if approver_deficit:
            viable = False
            code = "APPROVER_ROLE_MISSING"
            message = _approver_deficit_message(
                approver_deficit,
                required_count,
                len(available_approvers),
                required_capability,
            )
            correction = _approver_correction(
                approver_deficit,
                required_capability,
            )
        else:
            viable = True
            code = ""
            message = "This task does not require an independent review."
            correction = ""
    elif viable_reviewers:
        viable = True
        qualified_approvers = sorted(
            {
                human_id
                for option in viable_reviewers
                for human_id in option["qualified_approver_ids"]
            }
        )
        approver_deficit = 0
        code = ""
        message = (
            "A viable builder, independent reviewer, and qualified human "
            "approver plan exists."
            if requires_human_approval
            else "A viable builder and independent reviewer plan exists."
        )
        correction = ""
    else:
        viable = False
        qualified_approvers = []
        base_eligible = [
            option
            for option in options
            if option["code"]
            in {"APPROVER_ROLE_MISSING", "REVIEWER_EXHAUSTS_APPROVERS"}
        ]
        if len(available_approvers) < required_count:
            approver_deficit = required_count - len(available_approvers)
            code = "APPROVER_ROLE_MISSING"
            message = _approver_deficit_message(
                approver_deficit,
                required_count,
                len(available_approvers),
                required_capability,
            )
            correction = _approver_correction(
                approver_deficit,
                required_capability,
            )
        elif base_eligible:
            approver_deficit = min(
                int(option["approver_deficit"]) for option in base_eligible
            )
            code = "AUTHORITY_PLAN_UNSATISFIABLE"
            message = (
                "Every available reviewer would leave too few distinct qualified "
                "human approvers."
            )
            correction = (
                "Add or select a distinct Palari reviewer and keep the qualified "
                "human for final approval."
            )
        else:
            approver_deficit = required_count
            code = "REVIEWER_ROLE_MISSING"
            message = "No declared identity is eligible to review this builder's work."
            correction = (
                "Add or select a distinct reviewer linked to the task goal and "
                "allowed to read every selected source."
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "work_item_id": work.id,
        "builder_id": builder,
        "proposed_reviewer_id": reviewer_id,
        "requires_review": requires_review,
        "requires_human_approval": requires_human_approval,
        "required_approval_count": declared_count,
        "effective_final_approval_count": required_count,
        "required_approval_capability": required_capability,
        "viable": viable,
        "code": code,
        "message": message,
        "smallest_correction": correction,
        "qualified_approver_ids": qualified_approvers,
        "approver_deficit": approver_deficit,
        "viable_reviewers": sorted(viable_reviewers, key=_option_sort_key),
        "rejected_reviewers": sorted(rejected_reviewers, key=_option_sort_key),
    }


def _reviewer_identities(workspace: Workspace) -> list[tuple[str, Any]]:
    identities = [
        *(("palari", item) for item in workspace.palaris),
        *(("human", item) for item in workspace.humans),
    ]
    return sorted(identities, key=lambda item: (item[1].id, item[0]))


def _reviewer_option(
    workspace: Workspace,
    work: Any,
    builder_id: str,
    reviewer: Any,
    identity_type: str,
    required_count: int,
    required_capability: str,
    available_approvers: list[str],
) -> dict[str, Any]:
    reviewer_id = reviewer.id
    if reviewer_id == builder_id:
        return _rejected_option(
            reviewer_id,
            identity_type,
            required_count,
            "REVIEWER_IS_BUILDER",
            f"Reviewer {reviewer_id} is also the builder.",
            "Select a reviewer distinct from the builder.",
        )
    if identity_type == "human":
        if reviewer.availability == "inactive":
            return _rejected_option(
                reviewer_id,
                identity_type,
                required_count,
                "REVIEWER_INACTIVE",
                f"Human reviewer {reviewer_id} is inactive.",
                "Select an active reviewer.",
            )
        workbench = workspace.workbench(work.workbench_id) if work.workbench_id else None
        if workbench is not None and workbench.human_ids and reviewer_id not in workbench.human_ids:
            return _rejected_option(
                reviewer_id,
                identity_type,
                required_count,
                "REVIEWER_NOT_IN_WORKBENCH",
                f"Human reviewer {reviewer_id} is not assigned to {workbench.id}.",
                "Select a reviewer assigned to the task's project.",
            )
    else:
        if work.goal and work.goal not in reviewer.linked_goals:
            return _rejected_option(
                reviewer_id,
                identity_type,
                required_count,
                "REVIEWER_GOAL_NOT_ALLOWED",
                f"Palari reviewer {reviewer_id} is not linked to goal {work.goal}.",
                "Link a distinct review-only Palari to the task goal.",
            )
        for source_id in work.allowed_sources:
            source = workspace.source(source_id)
            if source is None or (
                source.allowed_palaris and reviewer_id not in source.allowed_palaris
            ):
                return _rejected_option(
                    reviewer_id,
                    identity_type,
                    required_count,
                    "REVIEWER_SOURCE_NOT_ALLOWED",
                    f"Palari reviewer {reviewer_id} cannot read selected source {source_id}.",
                    "Allow a distinct review-only Palari to read every selected source.",
                )

    approvers = [
        human_id for human_id in available_approvers if human_id != reviewer_id
    ]
    deficit = max(0, required_count - len(approvers))
    if deficit:
        exhausts_approvers = reviewer_id in available_approvers
        code = (
            "REVIEWER_EXHAUSTS_APPROVERS"
            if exhausts_approvers
            else "APPROVER_ROLE_MISSING"
        )
        message = (
            f"Reviewer {reviewer_id} would leave {len(approvers)}/"
            f"{required_count} distinct qualified human approvers."
        )
        correction = (
            "Select a distinct Palari reviewer and keep "
            f"{reviewer_id} for final approval."
            if exhausts_approvers
            else _approver_correction(deficit, required_capability)
        )
        return {
            "id": reviewer_id,
            "identity_type": identity_type,
            "viable": False,
            "qualified_approver_ids": approvers,
            "approver_deficit": deficit,
            "code": code,
            "message": message,
            "smallest_correction": correction,
        }
    return {
        "id": reviewer_id,
        "identity_type": identity_type,
        "viable": True,
        "qualified_approver_ids": approvers,
        "approver_deficit": 0,
        "code": "",
        "message": (
            f"Reviewer {reviewer_id} leaves {len(approvers)} distinct qualified "
            "human approver(s)."
            if required_count
            else (
                f"Reviewer {reviewer_id} is independent and eligible; "
                "no human approval quorum is required."
            )
        ),
        "smallest_correction": "",
    }


def _qualified_approver_ids(
    workspace: Workspace,
    required_capability: str,
    *,
    excluded: set[str],
) -> list[str]:
    return sorted(
        human.id
        for human in workspace.humans
        if human.id not in excluded
        and human.availability != "inactive"
        and (
            not required_capability
            or required_capability in human.approval_capabilities
        )
    )


def _rejected_option(
    reviewer_id: str,
    identity_type: str,
    required_count: int,
    code: str,
    message: str,
    correction: str,
) -> dict[str, Any]:
    return {
        "id": reviewer_id,
        "identity_type": identity_type,
        "viable": False,
        "qualified_approver_ids": [],
        "approver_deficit": required_count,
        "code": code,
        "message": message,
        "smallest_correction": correction,
    }


def _approver_deficit_message(
    deficit: int,
    required_count: int,
    available_count: int,
    required_capability: str,
) -> str:
    capability = (
        f" with capability {required_capability}" if required_capability else ""
    )
    return (
        f"Only {available_count}/{required_count} active distinct human "
        f"approvers{capability} are available; {deficit} role(s) are missing."
    )


def _approver_correction(deficit: int, required_capability: str) -> str:
    capability = (
        f" with capability {required_capability}" if required_capability else ""
    )
    return (
        f"Add or activate {deficit} qualified human approver(s){capability}; "
        "do not create a second identity for the same person."
    )


def _option_sort_key(option: dict[str, Any]) -> tuple[int, str, str]:
    return (
        0 if option["identity_type"] == "palari" else 1,
        str(option["id"]),
        str(option["code"]),
    )

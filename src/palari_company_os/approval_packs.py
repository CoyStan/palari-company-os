from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, cast

from .approval_presentations import (
    DECISION_SURFACE,
    PRESENTATION_SCHEMA_VERSION,
    approval_presentation_digest,
    build_approval_presentation,
)
from .errors import WorkspaceError
from .governance_binding import (
    attempt_state_hash,
    work_contract_hash,
)
from .governance_kernel import (
    TERMINAL_WORK_STATUSES,
    evaluate_approval_batch_policy,
    evaluate_governance_case,
)
from .governance_journal import (
    JournalVerificationContext,
    MutationMetadata,
    pending_workspace_journal_context,
    recover_pending,
    utc_timestamp,
    verify_journal,
    workspace_digest,
)
from .path_policy import validate_workspace_path
from .pcaw_canonical import canonical_sha256
from .pcaw_workspace import (
    governance_case_from_workspace,
    governance_context_from_workspace,
)
from .record_order import record_time_key
from .store import load_store, validate_data, write_store
from .transition_checks import assert_transition_allowed
from .workspace import Workspace, current_attempt_for_work, latest_for_work


PACK_SCHEMA_VERSION = "palari.approval-pack.v2"
INBOX_SCHEMA_VERSION = "palari.approval-inbox.v1"
DECISION_BINDING_VERSION = "palari.approval-pack-decision.v2"
BAD_DEPENDENCY_STATES = {
    "blocked",
    "deferred",
    "non-batchable",
    "rejected",
    "stale",
}


def build_approval_inbox(
    workspace: Workspace,
    raw_data: dict[str, Any],
    *,
    selected_work_ids: Iterable[str] = (),
    journal_context: JournalVerificationContext | None = None,
) -> dict[str, Any]:
    """Build deterministic, immutable pack manifests from current workspace truth."""

    operation_journal = journal_context or JournalVerificationContext()
    selected = tuple(sorted(set(selected_work_ids)))
    known = {work.id: work for work in workspace.work_items}
    missing = [work_id for work_id in selected if work_id not in known]
    if missing:
        raise WorkspaceError(f"approval inbox work items not found: {', '.join(missing)}")
    if selected:
        candidates = [known[work_id] for work_id in selected]
    else:
        candidates = [
            work
            for work in workspace.work_items
            if work.status not in TERMINAL_WORK_STATUSES
            and work.required_approval_count > 0
            and current_attempt_for_work(work, workspace.attempts) is not None
        ]

    members = [
        _work_member(workspace, work, journal_context=operation_journal)
        for work in candidates
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for member in members:
        policy = member["batch_policy"]
        group = "batchable-local" if policy["batchable"] else str(policy["class"])
        grouped.setdefault(group, []).append(member)

    journal = operation_journal.verify(workspace.path)
    if not journal.get("chain_valid") or journal.get("pending"):
        raise WorkspaceError(
            "approval inbox requires a verified, committed governance journal checkpoint"
        )
    if journal.get("replay_workspace_digest") != workspace_digest(raw_data):
        raise WorkspaceError(
            "approval inbox workspace differs from its committed journal projection"
        )
    base: dict[str, str] = {
        "workspace_digest": cast(str, workspace_digest(raw_data)),
        "checkpoint_digest": str(journal.get("replay_workspace_digest") or ""),
        "journal_head_digest": str(journal.get("head_record_digest") or ""),
    }
    packs = [
        _pack_manifest(base, group, grouped[group])
        for group in sorted(grouped)
    ]
    evaluated = [
        evaluate_approval_pack(
            workspace,
            pack,
            journal_context=operation_journal,
        )
        for pack in packs
    ]
    presentations = [
        build_approval_presentation(workspace, pack, report)
        for pack, report in zip(packs, evaluated, strict=True)
    ]
    for report in evaluated:
        for item in report["members"]:
            item["resolution"] = approval_resolution(item)
    individual_items = [item for report in evaluated for item in report["members"]]
    counts: dict[str, int] = {
        "packs": len(packs),
        "items": len(individual_items),
        "eligible": 0,
        "blocked": 0,
        "stale": 0,
        "non_batchable": 0,
        "approved": 0,
        "executed": 0,
        "rejected": 0,
        "deferred": 0,
    }
    for item in individual_items:
        key = str(item["state"]).replace("-", "_")
        if key in counts:
            counts[key] += 1
    approval_commands: list[dict[str, str]] = []
    for pack, presentation in zip(packs, presentations, strict=True):
        presentation_digest = approval_presentation_digest(presentation, pack)
        approval_commands.append(
            {
                "pack_id": pack["pack_id"],
                "pack_digest": pack["pack_digest"],
                "presentation_digest": presentation_digest,
                "approve_eligible": _approval_command(pack, presentation_digest),
            }
        )
    eligible_commands = [
        command
        for command, report in zip(approval_commands, evaluated, strict=True)
        if any(item["state"] == "eligible" for item in report["members"])
    ]
    return {
        "schema_version": INBOX_SCHEMA_VERSION,
        "workspace": workspace.name,
        "counts": counts,
        "groups": {
            "safe_reversible": sum(
                1
                for item in individual_items
                if item["reversibility"] == "reversible-local"
            ),
            "external_or_irreversible": sum(
                1
                for item in individual_items
                if item["reversibility"] != "reversible-local"
            ),
        },
        "packs": packs,
        "presentations": presentations,
        "evaluations": evaluated,
        "individual_items": individual_items,
        "interaction_measurement": approval_interaction_measurement(
            packs,
            individual_items,
        ),
        "approval_modes": approval_modes(counts, len(eligible_commands)),
        "primary_action": approval_primary_action(eligible_commands, counts),
        "approval_commands": approval_commands,
        "actions": {
            "approve_eligible": "palari human-decision pack --pack-digest DIGEST --presentation-digest PRESENTATION --human-id HUMAN-ID --approve-eligible --json",
            "approve_selected": "palari human-decision pack --pack-digest DIGEST --presentation-digest PRESENTATION --human-id HUMAN-ID --approve WORK-ID --json",
            "reject": "palari human-decision pack --pack-digest DIGEST --presentation-digest PRESENTATION --human-id HUMAN-ID --reject WORK-ID --json",
            "defer": "palari human-decision pack --pack-digest DIGEST --presentation-digest PRESENTATION --human-id HUMAN-ID --defer WORK-ID --json",
            "narrow": "palari queue --approval-inbox --select WORK-ID --json",
        },
        "security_limitations": _security_limitations(),
    }


def approval_modes(
    counts: dict[str, int],
    approval_actions: int,
) -> list[dict[str, Any]]:
    """Describe available authority surfaces without granting that authority."""

    return [
        {
            "id": "automatic-reconciliation",
            "label": "Automatic",
            "available": True,
            "human_actions": 0,
            "authority": "none",
            "use_when": "The remaining transition is deterministic and already authorized.",
        },
        {
            "id": "approve-eligible",
            "label": "Approve eligible",
            "available": approval_actions > 0,
            "human_actions": approval_actions,
            "authority": "qualified-human",
            "use_when": "Every selected local member has current independent proof.",
        },
        {
            "id": "approve-selected",
            "label": "Approve selected",
            "available": approval_actions > 0,
            "human_actions": approval_actions,
            "authority": "qualified-human",
            "use_when": "A human wants a narrower exact subset of one current pack.",
        },
        {
            "id": "individual-effect",
            "label": "Individual effect",
            "available": counts.get("non_batchable", 0) > 0,
            "human_actions": counts.get("non_batchable", 0),
            "authority": "qualified-human",
            "use_when": "Policy marks an effect external, irreversible, or too risky to batch.",
        },
        {
            "id": "review-and-accept",
            "label": "Review and accept",
            "available": False,
            "human_actions": 0,
            "authority": "not-implemented",
            "use_when": (
                "Unavailable in this policy version: independent review and acceptance "
                "must remain attributable to distinct actors."
            ),
        },
    ]


def approval_primary_action(
    approval_commands: list[dict[str, str]],
    counts: dict[str, int],
) -> dict[str, Any]:
    actions = len(approval_commands)
    return {
        "mode": "approve-eligible" if actions else "inspect-exceptions",
        "available": bool(actions),
        "eligible_items": counts.get("eligible", 0),
        "human_actions": actions,
        "commands": [item["approve_eligible"] for item in approval_commands],
        "exceptions": {
            "blocked": counts.get("blocked", 0),
            "stale": counts.get("stale", 0),
            "non_batchable": counts.get("non_batchable", 0),
        },
        "next_safe_action": (
            "Review the exact pack digest and run one listed command as a qualified human."
            if actions
            else "Resolve the item-level exceptions; no aggregate approval is available."
        ),
    }


def approval_resolution(item: dict[str, Any]) -> dict[str, Any]:
    """Classify the next resolver for an evaluated pack member."""

    state = str(item.get("state") or "")
    reasons = " ".join(str(reason).lower() for reason in item.get("reasons", []))
    if state in {"executed", "approved", "rejected", "deferred"}:
        resolution_class, owner, automatic, mode = "terminal", "none", True, "none"
    elif state == "eligible":
        resolution_class, owner, automatic, mode = (
            "human-authority",
            "human",
            False,
            "approve-eligible",
        )
    elif state == "non-batchable":
        resolution_class, owner, automatic, mode = (
            "human-authority",
            "human",
            False,
            "individual-effect",
        )
    elif "review" in reasons or "reviewer" in reasons:
        resolution_class, owner, automatic, mode = (
            "independent-review",
            "reviewer",
            False,
            "independent-review",
        )
    elif state == "stale" or any(
        token in reasons for token in ("evidence", "receipt", "proof", "subject digest")
    ):
        resolution_class, owner, automatic, mode = (
            "automatic-reconciliation",
            "system",
            True,
            "refresh-proof",
        )
    else:
        resolution_class, owner, automatic, mode = (
            "agent-action",
            "agent",
            False,
            "resolve-dependency",
        )
    return {
        "class": resolution_class,
        "owner": owner,
        "automatic": automatic,
        "approval_mode": mode,
        "next_safe_action": str(item.get("next_safe_action") or ""),
    }


def approval_interaction_measurement(
    packs: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic interaction and comprehension-work proxy."""

    eligible = sum(1 for item in items if item.get("state") == "eligible")
    return {
        "review_sessions": 1 if packs else 0,
        "attributable_approval_actions": 1 if eligible else 0,
        "individual_proof_records": len(items),
        "commands_or_clicks": {
            "individual_approval_baseline": eligible,
            "approval_pack": 1 if eligible else 0,
        },
        "time_to_understand_proxy": {
            "pack_summaries": len(packs),
            "item_state_rows": len(items),
            "repeated_narration_rows": 0,
            "external_effect_labels": sum(
                1 for pack in packs if pack.get("external_effects")
            ),
        },
    }


def validate_pack_manifest(pack: dict[str, Any]) -> None:
    expected = {
        "schema_version",
        "pack_id",
        "base",
        "members",
        "execution_order",
        "cumulative_effect_summary",
        "external_effects",
        "estimated_resources",
        "lifecycle_state",
        "security_limitations",
        "pack_digest",
    }
    if not isinstance(pack, dict) or set(pack) != expected:
        raise WorkspaceError("approval pack has unknown or missing fields")
    if pack["schema_version"] != PACK_SCHEMA_VERSION:
        raise WorkspaceError("approval pack schema version is unsupported")
    _require_string(pack["pack_id"], "pack_id")
    _exact_object(
        pack["base"],
        {"workspace_digest", "checkpoint_digest", "journal_head_digest"},
        "base",
    )
    for field in ("workspace_digest", "checkpoint_digest", "journal_head_digest"):
        _require_digest(pack["base"][field], f"base.{field}")
    _exact_object(
        pack["cumulative_effect_summary"],
        {"group", "items", "batchable", "blocked", "external_or_irreversible", "summary"},
        "cumulative_effect_summary",
    )
    _require_string(pack["cumulative_effect_summary"]["group"], "cumulative_effect_summary.group")
    _require_string(pack["cumulative_effect_summary"]["summary"], "cumulative_effect_summary.summary")
    for field in ("items", "batchable", "blocked", "external_or_irreversible"):
        _require_nonnegative_int(
            pack["cumulative_effect_summary"][field],
            f"cumulative_effect_summary.{field}",
        )
    _exact_object(pack["estimated_resources"], {"cost", "time", "items"}, "estimated_resources")
    _require_string(pack["estimated_resources"]["cost"], "estimated_resources.cost")
    _require_string(pack["estimated_resources"]["time"], "estimated_resources.time")
    _require_nonnegative_int(pack["estimated_resources"]["items"], "estimated_resources.items")
    _require_string_list(pack["external_effects"], "external_effects", canonical=True)
    _require_string_list(pack["security_limitations"], "security_limitations")
    if pack["lifecycle_state"] != "parked":
        raise WorkspaceError("approval pack lifecycle_state must be parked")
    _require_digest(pack["pack_digest"], "pack_digest")
    unsigned = {key: deepcopy(value) for key, value in pack.items() if key != "pack_digest"}
    if canonical_sha256(unsigned) != pack["pack_digest"]:
        raise WorkspaceError("approval pack digest does not match its canonical manifest")
    members = pack["members"]
    if not isinstance(members, list) or not members:
        raise WorkspaceError("approval pack must contain at least one member")
    ids: list[str] = []
    for member in members:
        _validate_pack_member(member)
        member_id = member.get("id")
        if not isinstance(member_id, str) or not member_id:
            raise WorkspaceError("approval pack member id is required")
        ids.append(member_id)
        unsigned_member = {
            key: deepcopy(value) for key, value in member.items() if key != "member_digest"
        }
        if canonical_sha256(unsigned_member) != member["member_digest"]:
            raise WorkspaceError(f"approval pack member {member_id} digest is stale")
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise WorkspaceError("approval pack members must be unique and canonically ordered")
    summary = pack["cumulative_effect_summary"]
    expected_group = {
        "batchable-local" if member["batch_policy"]["batchable"]
        else member["batch_policy"]["class"]
        for member in members
    }
    if len(expected_group) != 1 or summary["group"] not in expected_group:
        raise WorkspaceError("approval pack members do not match the declared policy group")
    expected_pack_id = (
        "PACK-"
        + canonical_sha256({"group": summary["group"], "members": ids})
        .removeprefix("sha256:")[:16]
        .upper()
    )
    if pack["pack_id"] != expected_pack_id:
        raise WorkspaceError("approval pack id does not match its canonical members")
    expected_summary = {
        "group": summary["group"],
        "items": len(members),
        "batchable": sum(1 for member in members if member["batch_policy"]["batchable"]),
        "blocked": sum(1 for member in members if not member["eligibility"]["eligible"]),
        "external_or_irreversible": sum(
            1
            for member in members
            if member["reversibility"]["class"] != "reversible-local"
        ),
        "summary": "; ".join(member["action"]["summary"] for member in members),
    }
    if summary != expected_summary:
        raise WorkspaceError("approval pack cumulative summary does not match its members")
    if pack["estimated_resources"]["items"] != len(members):
        raise WorkspaceError("approval pack estimated resource item count is stale")
    expected_effects = sorted(
        {effect for member in members for effect in member["external_effects"]}
    )
    if pack["external_effects"] != expected_effects:
        raise WorkspaceError("approval pack external effect summary does not match its members")
    order = pack["execution_order"]
    if not isinstance(order, list) or sorted(order) != ids or len(order) != len(ids):
        raise WorkspaceError("approval pack execution order must cover every member exactly once")
    positions = {member_id: index for index, member_id in enumerate(order)}
    for member in members:
        for dependency in member.get("dependencies", []):
            if dependency in positions and positions[dependency] >= positions[member["id"]]:
                raise WorkspaceError("approval pack execution order violates a dependency")


def evaluate_approval_pack(
    workspace: Workspace,
    pack: dict[str, Any],
    *,
    journal_context: JournalVerificationContext | None = None,
) -> dict[str, Any]:
    validate_pack_manifest(pack)
    operation_journal = journal_context or JournalVerificationContext()
    work_by_id = {work.id: work for work in workspace.work_items}
    current_members: dict[str, dict[str, Any]] = {}
    for member in pack["members"]:
        work = work_by_id.get(member["id"])
        if work is not None:
            current_members[member["id"]] = _work_member(
                workspace,
                work,
                journal_context=operation_journal,
            )

    result_by_id: dict[str, dict[str, Any]] = {}
    for member in pack["members"]:
        member_id = member["id"]
        current = current_members.get(member_id)
        decision = _latest_pack_decision(workspace, pack["pack_digest"], member_id)
        state = "eligible"
        reasons: list[str] = []
        executed = False
        if current is None:
            state = "stale"
            reasons.append("member no longer exists")
        elif current["subject_digest"] != member["subject_digest"]:
            state = "stale"
            reasons.append("current governed subject digest differs from the reviewed pack")
        elif _decision_member_digest(current) != _decision_member_digest(member):
            state = "stale"
            reasons.append("current governed member or batch policy differs from the reviewed pack")
        elif (
            proof_errors := [
                error
                for error in current["eligibility"]["errors"]
                if error != "work item is already terminal"
            ]
        ):
            state = "stale" if decision is not None else "blocked"
            reasons.extend(proof_errors)
        elif decision is not None:
            if decision.approval_pack_member_digest != member["member_digest"]:
                state = "stale"
                reasons.append("stored decision is bound to a different member digest")
            elif decision.approval_pack_action == "approve":
                work = work_by_id.get(member_id)
                executed = bool(work and work.status in TERMINAL_WORK_STATUSES)
                state = "executed" if executed else "approved"
            elif decision.approval_pack_action == "reject":
                state = "rejected"
            else:
                state = "deferred"
        elif not member["batch_policy"]["batchable"]:
            state = "non-batchable"
            reasons.append(member["batch_policy"]["reason"])
        elif not member["eligibility"]["eligible"]:
            state = "blocked"
            reasons.extend(member["eligibility"]["errors"])
        result_by_id[member_id] = {
            "id": member_id,
            "kind": member["kind"],
            "state": state,
            "executed": executed,
            "reversibility": member["reversibility"]["class"],
            "risk": member["risk"],
            "dependencies": list(member["dependencies"]),
            "conflicts": list(member["conflicts"]),
            "subject_digest": member["subject_digest"],
            "member_digest": member["member_digest"],
            "reasons": _unique(reasons),
            "next_safe_action": _member_next_action(state, member_id),
        }

    for member_id in pack["execution_order"]:
        result = result_by_id[member_id]
        blockers = [
            dependency
            for dependency in result["dependencies"]
            if dependency in result_by_id
            and result_by_id[dependency]["state"] in BAD_DEPENDENCY_STATES
        ]
        if blockers and result["state"] not in {"rejected", "deferred"}:
            result["state"] = "stale" if result["state"] in {"approved", "executed"} else "blocked"
            result["reasons"].append(
                "dependency is not current or approved: " + ", ".join(sorted(blockers))
            )
            result["next_safe_action"] = _member_next_action(result["state"], member_id)
        outside_blockers = [
            dependency
            for dependency in result["dependencies"]
            if dependency not in result_by_id
            and (
                dependency not in work_by_id
                or work_by_id[dependency].status not in TERMINAL_WORK_STATUSES
            )
        ]
        if outside_blockers and result["state"] not in {"rejected", "deferred"}:
            result["state"] = (
                "stale" if result["state"] in {"approved", "executed"} else "blocked"
            )
            result["reasons"].append(
                "dependency outside this pack is unfinished: "
                + ", ".join(sorted(outside_blockers))
            )
            result["next_safe_action"] = _member_next_action(result["state"], member_id)

    members = [result_by_id[member_id] for member_id in pack["execution_order"]]
    return {
        "schema_version": "palari.approval-pack-evaluation.v1",
        "pack_id": pack["pack_id"],
        "pack_digest": pack["pack_digest"],
        "claimed_state": pack["lifecycle_state"],
        "current_workspace_digest": (
            current_digest := workspace_digest(_workspace_projection(workspace))
        ),
        "base_workspace_matches": pack["base"]["workspace_digest"] == current_digest,
        "members": members,
        "counts": _state_counts(members),
        "verified_properties": {
            "exact_pack_binding": True,
            "item_granularity": len(members) == len(pack["members"]),
            "dependency_order": True,
            "authority_not_widened": True,
        },
        "security_limitations": _security_limitations(),
    }


def apply_pack_decision(
    workspace_path: str,
    *,
    pack_digest: str,
    presentation_digest: str,
    human_id: str,
    approve_eligible: bool = False,
    approve: Iterable[str] = (),
    reject: Iterable[str] = (),
    defer: Iterable[str] = (),
    pack_members: Iterable[str] = (),
    reason: str = "",
    command: str = "human-decision pack",
    crash_hook: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    _require_digest(pack_digest, "pack_digest")
    _require_digest(presentation_digest, "presentation_digest")
    request: dict[str, Any] = {
        "binding_version": DECISION_BINDING_VERSION,
        "pack_digest": pack_digest,
        "presentation_schema_version": PRESENTATION_SCHEMA_VERSION,
        "presentation_digest": presentation_digest,
        "presentation_surface": DECISION_SURFACE,
        "human_id": human_id,
        "approve_eligible": bool(approve_eligible),
        "approve": sorted(set(approve)),
        "reject": sorted(set(reject)),
        "defer": sorted(set(defer)),
        "pack_members": sorted(set(pack_members)),
        "reason": reason,
    }
    request_digest = canonical_sha256(request)
    store = load_store(workspace_path)
    journal = verify_journal(store.data_path, store.data)
    if journal.get("pending"):
        if journal["pending"].get("workspace_position") == "before":
            pending_context = pending_workspace_journal_context(store.data_path)
            pending = pending_context["prepare"] if pending_context is not None else None
            if pending is None or not _pending_matches_request(
                pending,
                pack_digest=pack_digest,
                human_id=human_id,
                request_digest=request_digest,
            ):
                raise WorkspaceError(
                    "a different governance transaction is pending; recover it before pack approval"
                )
            metadata = MutationMetadata(**pending["metadata"])
            write_store(
                store.with_data(deepcopy(pending["after_projection"])),
                metadata=metadata,
                event_kind=str(pending["event_kind"]),
            )
        else:
            recover_pending(store.data_path, store.data)
        store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    human = workspace.human(human_id)
    if human is None:
        raise WorkspaceError(f"approval pack human not found: {human_id}")
    if human.availability == "inactive":
        raise WorkspaceError(f"approval pack human is inactive: {human_id}")

    existing = [
        record
        for record in store.data.get("human_decisions", [])
        if record.get("approval_pack_digest") == pack_digest
        and record.get("human_id") == human_id
    ]
    if existing:
        if all(record.get("approval_pack_request_digest") == request_digest for record in existing):
            approved = sorted(
                record["work_item_id"]
                for record in existing
                if record.get("approval_pack_action") == "approve"
            )
            replayed_executed = sorted(
                record["work_item_id"]
                for record in existing
                if record.get("approval_pack_action") == "approve"
                and _work_is_terminal(workspace, record["work_item_id"])
            )
            return {
                "schema_version": "palari.approval-pack-decision-result.v1",
                "status": "already-applied",
                "idempotent": True,
                "pack_digest": pack_digest,
                "presentation_digest": presentation_digest,
                "request_digest": request_digest,
                "decisions": sorted(record["id"] for record in existing),
                "executed": replayed_executed,
                "convergence": {
                    "schema_version": "palari.one-action-convergence.v1",
                    "attributable_human_actions": 0,
                    "performed_human_authority": False,
                    "decision_records": sorted(record["id"] for record in existing),
                    "acceptance_records": sorted(
                        record.id
                        for record in workspace.acceptance_records
                        if record.work_item_id in replayed_executed
                    ),
                    "terminalized": replayed_executed,
                    "remaining_parked": sorted(
                        set(approved) - set(replayed_executed)
                    ),
                    "atomic_local_transaction": True,
                    "performed_review": False,
                    "performed_external_effects": False,
                },
            }
        raise WorkspaceError(
            "approval pack already has a different decision from this human; refresh the pack"
        )

    inbox = build_approval_inbox(
        workspace,
        store.data,
        selected_work_ids=request["pack_members"],
    )
    pack = next((item for item in inbox["packs"] if item["pack_digest"] == pack_digest), None)
    stored_pack = _stored_pack_manifest(workspace, pack_digest)
    if pack is None:
        pack = stored_pack
    if pack is None:
        raise WorkspaceError(
            "approval pack is missing or stale; rebuild the Approval Inbox and review the new digest"
        )
    evaluation = evaluate_approval_pack(workspace, pack)
    presentation = build_approval_presentation(workspace, pack, evaluation)
    expected_presentation_digest = approval_presentation_digest(presentation, pack)
    if presentation_digest != expected_presentation_digest:
        raise WorkspaceError(
            "approval presentation is missing or stale; rebuild the Approval Inbox and "
            "use its exact --presentation-digest"
        )
    exact_member_ids = {str(member["id"]) for member in pack["members"]}
    requested_member_ids = set(request["pack_members"])
    if requested_member_ids and requested_member_ids != exact_member_ids:
        raise WorkspaceError(
            "approval pack member selection does not match the exact reviewed manifest; "
            "use every --pack-member from the Approval Inbox command or rebuild a narrowed pack"
        )
    if stored_pack is None and pack["base"]["workspace_digest"] != workspace_digest(store.data):
        raise WorkspaceError("approval pack base workspace digest is stale")
    states = {item["id"]: item for item in evaluation["members"]}
    member_ids = set(states)

    approve_ids = set(request["approve"])
    reject_ids = set(request["reject"])
    defer_ids = set(request["defer"])
    overlap = (approve_ids & reject_ids) | (approve_ids & defer_ids) | (reject_ids & defer_ids)
    if overlap:
        raise WorkspaceError(
            "approval pack members have contradictory actions: " + ", ".join(sorted(overlap))
        )
    unknown = (approve_ids | reject_ids | defer_ids) - member_ids
    if unknown:
        raise WorkspaceError("approval pack members not found: " + ", ".join(sorted(unknown)))
    stale_selected = sorted(
        member_id
        for member_id in approve_ids | reject_ids | defer_ids
        if states[member_id]["state"] == "stale"
    )
    if stale_selected:
        raise WorkspaceError(
            "approval pack decision is stale for: "
            + ", ".join(stale_selected)
            + "; rebuild the Approval Inbox before recording a decision"
        )
    if approve_eligible:
        approve_ids.update(
            member_id
            for member_id, state in states.items()
            if state["state"] in {"eligible", "approved"}
            and member_id not in reject_ids | defer_ids
        )
    if not approve_ids and not reject_ids and not defer_ids:
        if approve_eligible:
            unavailable = ", ".join(
                f"{member_id} is {state['state']}"
                for member_id, state in sorted(states.items())
            )
            raise WorkspaceError(
                "approval pack has no currently eligible members: " + unavailable
            )
        raise WorkspaceError("approval pack decision selected no members")

    for member_id in sorted(approve_ids):
        if states[member_id]["state"] not in {"eligible", "approved"}:
            raise WorkspaceError(
                f"approval pack member {member_id} is {states[member_id]['state']}; "
                "approve only current eligible members"
            )
        member = next(item for item in pack["members"] if item["id"] == member_id)
        for dependency in member["dependencies"]:
            if dependency in member_ids and dependency not in approve_ids:
                dependency_state = states[dependency]["state"]
                if dependency_state not in {"approved", "executed"}:
                    raise WorkspaceError(
                        f"approval pack member {member_id} depends on unapproved {dependency}"
                    )
            elif dependency not in member_ids:
                dependency_work = workspace.work_item(dependency)
                if dependency_work is None or dependency_work.status not in TERMINAL_WORK_STATUSES:
                    raise WorkspaceError(
                        f"approval pack member {member_id} depends on unfinished {dependency}"
                    )

    timestamp = _timestamp()
    decisions = store.data.setdefault("human_decisions", [])
    if not isinstance(decisions, list):
        raise WorkspaceError("human_decisions must be a list")
    created: list[dict[str, Any]] = []
    action_by_id = {
        **{member_id: "approve" for member_id in approve_ids},
        **{member_id: "reject" for member_id in reject_ids},
        **{member_id: "defer" for member_id in defer_ids},
    }
    member_by_id = {member["id"]: member for member in pack["members"]}
    for member_id in pack["execution_order"]:
        action = action_by_id.get(member_id)
        if action is None:
            continue
        member = member_by_id[member_id]
        work = workspace.work_item(member_id)
        if work is None:
            raise WorkspaceError(f"approval pack work item not found: {member_id}")
        attempt = current_attempt_for_work(work, workspace.attempts)
        review = latest_for_work(workspace.review_verdicts, member_id)
        evidence = latest_for_work(workspace.evidence_runs, member_id)
        if action == "approve":
            if review is None or attempt is None or evidence is None:
                raise WorkspaceError(f"approval pack member {member_id} lacks current proof")
            if human_id in {attempt.actor, review.reviewer}:
                raise WorkspaceError(
                    f"approval pack human {human_id} must be distinct from builder and reviewer for {member_id}"
                )
        _assert_pack_human_authority(work, human, human_id)
        decision_record_id = _decision_id(pack_digest, human_id, member_id)
        if action == "approve":
            assert review is not None
            decision_transition = assert_transition_allowed(
                workspace,
                "human_decision_accept",
                decision_record_id,
                actor=human_id,
                context={
                    "work_item_id": member_id,
                    "reviewed_head": review.reviewed_head,
                    "timestamp": timestamp,
                    "acceptance_mode": "approval-pack",
                    "decision": "accepted",
                    "status": "accepted",
                    "evidence_reference": str(
                        member["proof"]["evidence_reference"]
                    ),
                    "review_reference": str(member["proof"]["review_reference"]),
                },
            )
        else:
            decision_transition = None
        decision_value, decision_status, quorum = {
            "approve": ("accepted", "accepted", "pending"),
            "reject": ("rejected", "rejected", "not-met"),
            "defer": ("deferred", "deferred", "not-met"),
        }[action]
        decision = {
            "id": decision_record_id,
            "work_item_id": member_id,
            "human_id": human_id,
            "reviewed_head": str(member["proof"]["reviewed_head"]),
            "decision": decision_value,
            "status": decision_status,
            "acceptance_mode": "approval-pack",
            "quorum_status": (
                "met"
                if decision_transition is not None
                and decision_transition.authority_candidate is not None
                and decision_transition.authority_candidate.quorum_met
                else quorum
            ),
            "evidence_reference": str(member["proof"]["evidence_reference"]),
            "review_reference": str(member["proof"]["review_reference"]),
            "approval_pack_id": pack["pack_id"],
            "approval_pack_digest": pack_digest,
            "approval_pack_member_digest": member["member_digest"],
            "approval_pack_subject_digest": member["subject_digest"],
            "approval_pack_request_digest": request_digest,
            "approval_pack_action": action,
            "approval_presentation_schema_version": PRESENTATION_SCHEMA_VERSION,
            "approval_presentation_digest": presentation_digest,
            "approval_presentation_surface": DECISION_SURFACE,
            "timestamp": timestamp,
        }
        if not created and stored_pack is None:
            decision["approval_pack_manifest"] = deepcopy(pack)
        if not created:
            decision["approval_presentation"] = deepcopy(presentation)
        decisions.append(decision)
        created.append(decision)

    workspace_after_decisions = validate_data(store.data_path, store.data)
    executed: list[str] = []
    acceptance_ids_before = {
        str(item.get("id") or "") for item in store.data.get("acceptance_records", [])
    }
    for member_id in pack["execution_order"]:
        if member_id not in approve_ids:
            continue
        work = workspace_after_decisions.work_item(member_id)
        approval_decision: dict[str, Any] | None = None
        for item in created:
            if (
                item["work_item_id"] == member_id
                and item["approval_pack_action"] == "approve"
            ):
                approval_decision = item
                break
        if (
            work is None
            or approval_decision is None
            or approval_decision["quorum_status"] != "met"
        ):
            continue
        from .authoring import assert_work_completion_ready
        from .pcaw_workspace import evaluate_workspace_human_authority_candidate

        acceptance_id = f"ACCEPTANCE-{member_id}-{human_id}"
        if not any(
            item.get("work_item_id") == member_id
            for item in store.data.get("acceptance_records", [])
        ):
            authority = evaluate_workspace_human_authority_candidate(
                workspace_after_decisions,
                member_id,
                decision_id=str(approval_decision["id"]),
                human_id=human_id,
                reviewed_head=str(approval_decision["reviewed_head"]),
                timestamp=str(approval_decision["timestamp"]),
                acceptance_mode="approval-pack",
                acceptance_id=acceptance_id,
                accepted_at=timestamp,
                projected_terminal=True,
            )
            if not authority.acceptance_allowed:
                message = (
                    authority.errors[0].message
                    if authority.errors
                    else "governance kernel rejected terminal acceptance"
                )
                raise WorkspaceError(
                    f"approval pack member {member_id} authority is stale: {message}"
                )
            review = latest_for_work(
                workspace_after_decisions.review_verdicts, member_id
            )
            evidence = latest_for_work(
                workspace_after_decisions.evidence_runs, member_id
            )
            receipt = latest_for_work(
                workspace_after_decisions.receipts, member_id
            )
            if review is None or evidence is None:
                raise WorkspaceError(
                    f"approval pack member {member_id} lacks current proof"
                )
            store.data.setdefault("acceptance_records", []).append(
                {
                    "id": acceptance_id,
                    "work_item_id": member_id,
                    "human_id": human_id,
                    "reviewed_head": review.reviewed_head,
                    "status": "accepted",
                    "decision_id": approval_decision["id"],
                    "evidence_reference": evidence.id,
                    "review_reference": review.id,
                    "receipt_hash": receipt.receipt_hash if receipt else "",
                    "authority_profile": "team-safe",
                    "quorum_status": "met",
                    "reason": reason or "approval pack authority",
                    "accepted_at": timestamp,
                }
            )
        workspace_after_decisions = validate_data(store.data_path, store.data)
        assert_work_completion_ready(
            workspace_after_decisions,
            member_id,
            actor=human_id,
        )
        raw_work = next(
            item for item in store.data["work_items"] if item.get("id") == member_id
        )
        raw_work["status"] = "completed"
        workspace_after_decisions = validate_data(store.data_path, store.data)
        executed.append(member_id)

    objects = [
        {"type": "human-decision", "collection": "human_decisions", "id": item["id"]}
        for item in created
    ] + [
        {"type": "work", "collection": "work_items", "id": work_id}
        for work_id in executed
    ] + [
        {
            "type": "acceptance",
            "collection": "acceptance_records",
            "id": str(item.get("id") or ""),
        }
        for item in store.data.get("acceptance_records", [])
        if str(item.get("id") or "") not in acceptance_ids_before
    ]
    metadata = MutationMetadata(
        command=command,
        actor=human_id,
        action="approval-pack-decision",
        timestamp=utc_timestamp(),
        objects=tuple(objects),
        reason=reason,
    )
    write_store(store, metadata=metadata, crash_hook=crash_hook)
    return {
        "schema_version": "palari.approval-pack-decision-result.v1",
        "status": "applied",
        "idempotent": False,
        "pack_id": pack["pack_id"],
        "pack_digest": pack_digest,
        "presentation_digest": presentation_digest,
        "request_digest": request_digest,
        "decisions": [item["id"] for item in created],
        "approved": sorted(approve_ids),
        "rejected": sorted(reject_ids),
        "deferred": sorted(defer_ids),
        "executed": executed,
        "parked": sorted((approve_ids | reject_ids | defer_ids) - set(executed)),
        "convergence": {
            "schema_version": "palari.one-action-convergence.v1",
            "attributable_human_actions": 1,
            "performed_human_authority": True,
            "decision_records": [item["id"] for item in created],
            "acceptance_records": sorted(
                str(item.get("id") or "")
                for item in store.data.get("acceptance_records", [])
                if str(item.get("id") or "") not in acceptance_ids_before
            ),
            "terminalized": list(executed),
            "remaining_parked": sorted(
                (approve_ids | reject_ids | defer_ids) - set(executed)
            ),
            "atomic_local_transaction": True,
            "performed_review": False,
            "performed_external_effects": False,
        },
        "journal_objects": objects,
        "security_limitations": _security_limitations(),
    }


def _pack_manifest(
    base: dict[str, str],
    group: str,
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered_members = sorted((deepcopy(member) for member in members), key=lambda item: item["id"])
    order = _topological_order(ordered_members)
    seed = canonical_sha256({"group": group, "members": [item["id"] for item in ordered_members]})
    pack = {
        "schema_version": PACK_SCHEMA_VERSION,
        "pack_id": f"PACK-{seed.removeprefix('sha256:')[:16].upper()}",
        "base": deepcopy(base),
        "members": ordered_members,
        "execution_order": order,
        "cumulative_effect_summary": {
            "group": group,
            "items": len(ordered_members),
            "batchable": sum(1 for item in ordered_members if item["batch_policy"]["batchable"]),
            "blocked": sum(1 for item in ordered_members if not item["eligibility"]["eligible"]),
            "external_or_irreversible": sum(
                1 for item in ordered_members if item["reversibility"]["class"] != "reversible-local"
            ),
            "summary": "; ".join(item["action"]["summary"] for item in ordered_members),
        },
        "external_effects": sorted(
            {
                effect
                for member in ordered_members
                for effect in member["external_effects"]
            }
        ),
        "estimated_resources": {
            "cost": "not-declared",
            "time": "not-declared",
            "items": len(ordered_members),
        },
        "lifecycle_state": "parked",
        "security_limitations": _security_limitations(),
    }
    pack["pack_digest"] = canonical_sha256(pack)
    validate_pack_manifest(pack)
    return pack


def _work_member(
    workspace: Workspace,
    work: Any,
    *,
    include_dependency_bindings: bool = True,
    journal_context: JournalVerificationContext | None = None,
) -> dict[str, Any]:
    attempt = current_attempt_for_work(work, workspace.attempts)
    receipt = latest_for_work(workspace.receipts, work.id)
    evidence = latest_for_work(workspace.evidence_runs, work.id)
    review = latest_for_work(workspace.review_verdicts, work.id)
    errors: list[str] = []
    if work.status in TERMINAL_WORK_STATUSES:
        errors.append("work item is already terminal")
    if work.required_approval_count <= 0:
        errors.append("work item does not require a human approval")
    try:
        governance_case, _ = governance_case_from_workspace(
            workspace,
            work.id,
            journal_context=journal_context,
        )
        governance = evaluate_governance_case(
            governance_case,
            context=governance_context_from_workspace(workspace, work.id),
        )
    except WorkspaceError as exc:
        errors.append(f"governance proof validation failed: {exc}")
    else:
        errors.extend(
            item.message
            for item in governance.errors
            if item.code
            not in {
                "PCAW_CLAIMED_STATE_MISMATCH",
                "PCAW_HUMAN_QUORUM_INCOMPLETE",
            }
        )
        if not governance.human_decision_ready and not errors:
            errors.append(
                "current exact proof and independent review are not decision-ready"
            )

    artifacts = []
    if evidence is not None:
        artifacts = sorted(
            (
                {
                    "path": str(item.get("path", "")),
                    "sha256": str(item.get("sha256", "")),
                }
                for item in evidence.artifact_hashes
            ),
            key=lambda item: item["path"],
        )
    subject = {
        "work_contract_hash": work_contract_hash(work),
        "attempt_id": attempt.id if attempt else "",
        "attempt_hash": attempt_state_hash(attempt) if attempt else "",
        "reviewed_head": review.reviewed_head if review else "",
        "receipt_reference": receipt.id if receipt else "",
        "receipt_hash": receipt.receipt_hash if receipt else "",
        "evidence_reference": evidence.id if evidence else "",
        "evidence_manifest_hash": evidence.manifest_hash if evidence else "",
        "review_reference": review.id if review else "",
        "review_proof_hash": review.proof_hash if review else "",
        "outputs": artifacts,
    }
    subject_digest = canonical_sha256(subject)
    external_effects = _external_effects(workspace, work.id, receipt)
    policy = _batch_policy(work, external_effects)
    member = {
        "id": work.id,
        "kind": "work-item",
        "title": work.title,
        "subject_digest": subject_digest,
        "risk": work.risk,
        "reversibility": {
            "class": policy["reversibility"],
            "reason": policy["reason"],
        },
        "authority": {
            "required_approval_count": work.required_approval_count,
            "required_approval_capability": work.required_approval_capability,
        },
        "boundaries": {
            "sources": sorted(work.allowed_sources),
            "paths": sorted(work.allowed_resources),
            "tools_or_actions": sorted(work.allowed_actions),
            "forbidden_actions": sorted(work.forbidden_actions),
        },
        "proof": {
            "attempt_id": subject["attempt_id"],
            "receipt_reference": subject["receipt_reference"],
            "evidence_reference": subject["evidence_reference"],
            "review_reference": subject["review_reference"],
            "reviewed_head": subject["reviewed_head"],
        },
        "outputs": artifacts,
        "dependencies": sorted(work.dependency_ids),
        "dependency_bindings": (
            _dependency_bindings(
                workspace,
                work,
                journal_context=journal_context,
            )
            if include_dependency_bindings
            else []
        ),
        "conflicts": sorted(work.conflict_targets),
        "batch_policy": {
            "class": policy["class"],
            "batchable": policy["batchable"],
            "reason": policy["reason"],
        },
        "action": {
            "type": "complete-work" if policy["batchable"] else "remain-parked",
            "summary": (
                f"Complete {work.id} from its exact reviewed proof"
                if policy["batchable"]
                else f"Keep {work.id} parked for individual authority"
            ),
            "external": bool(external_effects),
            "irreversible": policy["reversibility"] in {"irreversible", "restoration-impossible"},
        },
        "external_effects": external_effects,
        "estimated_resources": {"cost": "not-declared", "time": "not-declared"},
        "eligibility": {"eligible": not errors, "errors": _unique(errors)},
    }
    member["member_digest"] = canonical_sha256(member)
    return member


def _batch_policy(work: Any, external_effects: list[str]) -> dict[str, Any]:
    return evaluate_approval_batch_policy(
        risk=work.risk,
        allowed_actions=work.allowed_actions,
        external_effects=external_effects,
    ).to_dict()


def _external_effects(workspace: Workspace, work_id: str, receipt: Any | None) -> list[str]:
    effects: set[str] = set()
    if receipt is not None:
        effects.update(receipt.external_writes)
        effects.update(receipt.planned_external_writes)
        effects.update(receipt.queued_external_writes)
    effects.update(
        plan.id
        for plan in workspace.integration_plans
        if plan.work_item_id == work_id and plan.status not in {"rejected", "canceled"}
    )
    effects.update(
        item.id
        for item in workspace.integration_outbox
        if item.work_item_id == work_id and item.status not in {"canceled", "rejected"}
    )
    return sorted(effects)


def _topological_order(members: list[dict[str, Any]]) -> list[str]:
    ids = {member["id"] for member in members}
    dependencies = {
        member["id"]: {item for item in member["dependencies"] if item in ids}
        for member in members
    }
    order: list[str] = []
    remaining = set(ids)
    while remaining:
        ready = sorted(item for item in remaining if dependencies[item] <= set(order))
        if not ready:
            raise WorkspaceError("approval pack dependency graph contains a cycle")
        order.extend(ready)
        remaining.difference_update(ready)
    return order


def _dependency_bindings(
    workspace: Workspace,
    work: Any,
    *,
    journal_context: JournalVerificationContext | None = None,
) -> list[dict[str, str]]:
    return [
        {
            "id": dependency_id,
            "state_digest": _dependency_state_digest(
                workspace,
                dependency_id,
                ancestors=frozenset({work.id}),
                journal_context=journal_context,
            ),
        }
        for dependency_id in sorted(work.dependency_ids)
    ]


def _dependency_state_digest(
    workspace: Workspace,
    work_id: str,
    *,
    ancestors: frozenset[str],
    journal_context: JournalVerificationContext | None = None,
) -> str:
    if work_id in ancestors:
        return canonical_sha256({"id": work_id, "cycle": True})
    work = workspace.work_item(work_id)
    if work is None:
        return canonical_sha256({"id": work_id, "missing": True})
    member = _work_member(
        workspace,
        work,
        include_dependency_bindings=False,
        journal_context=journal_context,
    )
    descendants = [
        {
            "id": dependency_id,
            "state_digest": _dependency_state_digest(
                workspace,
                dependency_id,
                ancestors=ancestors | {work_id},
                journal_context=journal_context,
            ),
        }
        for dependency_id in sorted(work.dependency_ids)
    ]
    return canonical_sha256(
        {
            "id": work_id,
            "member_state_digest": _decision_member_digest(member),
            "dependency_bindings": descendants,
        }
    )


def _latest_pack_decision(
    workspace: Workspace,
    pack_digest: str,
    member_id: str,
) -> Any | None:
    matching = [
        decision
        for decision in workspace.human_decisions
        if decision.work_item_id == member_id
        and decision.approval_pack_digest == pack_digest
    ]
    return max(matching, key=record_time_key) if matching else None


def _stored_pack_manifest(workspace: Workspace, pack_digest: str) -> dict[str, Any] | None:
    manifests = [
        decision.approval_pack_manifest
        for decision in workspace.human_decisions
        if decision.approval_pack_digest == pack_digest
        and decision.approval_pack_manifest
    ]
    if not manifests:
        return None
    manifest = deepcopy(manifests[0])
    validate_pack_manifest(manifest)
    return manifest


def _assert_pack_human_authority(work: Any, human: Any, human_id: str) -> None:
    if human.availability == "inactive":
        raise WorkspaceError(f"human {human_id} is inactive for {work.id}")
    if work.required_approval_capability and (
        work.required_approval_capability not in human.approval_capabilities
    ):
        raise WorkspaceError(
            f"human {human_id} lacks required approval capability "
            f"{work.required_approval_capability} for {work.id}"
        )


def _decision_id(pack_digest: str, human_id: str, member_id: str) -> str:
    suffix = canonical_sha256(
        {"pack_digest": pack_digest, "human_id": human_id, "member_id": member_id}
    ).removeprefix("sha256:")[:20]
    return f"PACK-DECISION-{suffix.upper()}"


def _state_counts(members: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for member in members:
        state = str(member["state"])
        counts[state] = counts.get(state, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _member_next_action(state: str, member_id: str) -> str:
    if state == "eligible":
        return f"Approve {member_id} from this exact pack or leave it parked."
    if state == "non-batchable":
        return f"Review {member_id} individually under its native authority gate."
    if state in {"stale", "blocked"}:
        return f"Refresh {member_id} proof and rebuild the Approval Inbox."
    if state == "rejected":
        return f"Repair {member_id} before preparing another pack."
    if state == "deferred":
        return f"Leave {member_id} parked until a later review session."
    return f"Inspect {member_id} exact decision and execution journal records."


def _workspace_projection(workspace: Workspace) -> dict[str, Any]:
    store = load_store(workspace.path)
    return store.data


def _work_is_terminal(workspace: Workspace, work_id: str) -> bool:
    work = workspace.work_item(work_id)
    return bool(work and work.status in TERMINAL_WORK_STATUSES)


def _pending_matches_request(
    pending: dict[str, Any],
    *,
    pack_digest: str,
    human_id: str,
    request_digest: str,
) -> bool:
    projection = pending.get("after_projection")
    if not isinstance(projection, dict):
        return False
    return any(
        isinstance(record, dict)
        and record.get("approval_pack_digest") == pack_digest
        and record.get("approval_pack_request_digest") == request_digest
        and record.get("human_id") == human_id
        for record in projection.get("human_decisions", [])
    )


def _security_limitations() -> list[str]:
    return [
        "Actor attribution is declared, not cryptographically authenticated.",
        "Pack approval grants no authority beyond each member's existing boundaries.",
        "External and irreversible effects remain parked and are not locally undoable.",
    ]


def _approval_command(pack: dict[str, Any], presentation_digest: str) -> str:
    members = " ".join(
        f"--pack-member {member_id}" for member_id in pack["execution_order"]
    )
    return (
        "palari human-decision pack "
        f"--pack-digest {pack['pack_digest']} "
        f"--presentation-digest {presentation_digest} --human-id HUMAN-ID "
        f"--approve-eligible {members} --json"
    )


def _decision_member_digest(member: dict[str, Any]) -> str:
    """Bind policy and proof while allowing the expected local terminal transition."""

    normalized = deepcopy(member)
    normalized.pop("member_digest", None)
    eligibility = normalized.get("eligibility")
    if isinstance(eligibility, dict) and isinstance(eligibility.get("errors"), list):
        eligibility["errors"] = [
            error
            for error in eligibility["errors"]
            if error != "work item is already terminal"
        ]
        eligibility["eligible"] = not eligibility["errors"]
    return canonical_sha256(normalized)


def _validate_pack_member(member: Any) -> None:
    fields = {
        "id", "kind", "title", "subject_digest", "risk", "reversibility",
        "authority", "boundaries", "proof", "outputs", "dependencies", "conflicts",
        "dependency_bindings", "batch_policy", "action", "external_effects",
        "estimated_resources", "eligibility", "member_digest",
    }
    _exact_object(member, fields, "members[]")
    member_id = _require_string(member["id"], "members[].id")
    if member["kind"] != "work-item":
        raise WorkspaceError(f"approval pack member {member_id} kind is unsupported")
    _require_string(member["title"], f"members.{member_id}.title")
    _require_string(member["risk"], f"members.{member_id}.risk")
    _require_digest(member["subject_digest"], f"members.{member_id}.subject_digest")
    _require_digest(member["member_digest"], f"members.{member_id}.member_digest")

    _exact_object(member["reversibility"], {"class", "reason"}, f"members.{member_id}.reversibility")
    _require_string(member["reversibility"]["class"], f"members.{member_id}.reversibility.class")
    _require_string(member["reversibility"]["reason"], f"members.{member_id}.reversibility.reason")
    _exact_object(
        member["authority"],
        {"required_approval_count", "required_approval_capability"},
        f"members.{member_id}.authority",
    )
    _require_nonnegative_int(
        member["authority"]["required_approval_count"],
        f"members.{member_id}.authority.required_approval_count",
    )
    if not isinstance(member["authority"]["required_approval_capability"], str):
        raise WorkspaceError(
            f"approval pack members.{member_id}.authority.required_approval_capability must be a string"
        )

    _exact_object(
        member["boundaries"],
        {"sources", "paths", "tools_or_actions", "forbidden_actions"},
        f"members.{member_id}.boundaries",
    )
    for field in ("sources", "paths", "tools_or_actions", "forbidden_actions"):
        _require_string_list(
            member["boundaries"][field],
            f"members.{member_id}.boundaries.{field}",
            canonical=True,
        )
    _exact_object(
        member["proof"],
        {"attempt_id", "receipt_reference", "evidence_reference", "review_reference", "reviewed_head"},
        f"members.{member_id}.proof",
    )
    for field in member["proof"]:
        if not isinstance(member["proof"][field], str):
            raise WorkspaceError(
                f"approval pack members.{member_id}.proof.{field} must be a string"
            )

    if not isinstance(member["outputs"], list):
        raise WorkspaceError(f"approval pack members.{member_id}.outputs must be a list")
    output_paths: list[str] = []
    for index, output in enumerate(member["outputs"]):
        path = f"members.{member_id}.outputs[{index}]"
        _exact_object(output, {"path", "sha256"}, path)
        output_path = _require_string(output["path"], f"{path}.path")
        try:
            normalized_path = validate_workspace_path(output_path)
        except ValueError as exc:
            raise WorkspaceError(f"approval pack {path}.path is unsafe: {exc}") from exc
        if normalized_path != output_path:
            raise WorkspaceError(f"approval pack {path}.path is not canonical")
        _require_digest(output["sha256"], f"{path}.sha256")
        output_paths.append(output_path)
    if output_paths != sorted(set(output_paths)):
        raise WorkspaceError(f"approval pack members.{member_id}.outputs must be unique and ordered")

    for field in ("dependencies", "conflicts", "external_effects"):
        _require_string_list(member[field], f"members.{member_id}.{field}", canonical=True)
    bindings = member["dependency_bindings"]
    if not isinstance(bindings, list):
        raise WorkspaceError(
            f"approval pack members.{member_id}.dependency_bindings must be a list"
        )
    binding_ids: list[str] = []
    for index, binding in enumerate(bindings):
        path = f"members.{member_id}.dependency_bindings[{index}]"
        _exact_object(binding, {"id", "state_digest"}, path)
        binding_ids.append(_require_string(binding["id"], f"{path}.id"))
        _require_digest(binding["state_digest"], f"{path}.state_digest")
    if binding_ids != member["dependencies"]:
        raise WorkspaceError(
            f"approval pack members.{member_id}.dependency_bindings must cover "
            "every dependency exactly once"
        )
    _exact_object(
        member["batch_policy"],
        {"class", "batchable", "reason"},
        f"members.{member_id}.batch_policy",
    )
    _require_string(member["batch_policy"]["class"], f"members.{member_id}.batch_policy.class")
    _require_bool(member["batch_policy"]["batchable"], f"members.{member_id}.batch_policy.batchable")
    _require_string(member["batch_policy"]["reason"], f"members.{member_id}.batch_policy.reason")
    _exact_object(
        member["action"],
        {"type", "summary", "external", "irreversible"},
        f"members.{member_id}.action",
    )
    _require_string(member["action"]["type"], f"members.{member_id}.action.type")
    _require_string(member["action"]["summary"], f"members.{member_id}.action.summary")
    _require_bool(member["action"]["external"], f"members.{member_id}.action.external")
    _require_bool(member["action"]["irreversible"], f"members.{member_id}.action.irreversible")
    _exact_object(member["estimated_resources"], {"cost", "time"}, f"members.{member_id}.estimated_resources")
    _require_string(member["estimated_resources"]["cost"], f"members.{member_id}.estimated_resources.cost")
    _require_string(member["estimated_resources"]["time"], f"members.{member_id}.estimated_resources.time")
    _exact_object(member["eligibility"], {"eligible", "errors"}, f"members.{member_id}.eligibility")
    _require_bool(member["eligibility"]["eligible"], f"members.{member_id}.eligibility.eligible")
    _require_string_list(member["eligibility"]["errors"], f"members.{member_id}.eligibility.errors")


def _exact_object(value: Any, fields: set[str], path: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise WorkspaceError(f"approval pack {path} has unknown or missing fields")


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise WorkspaceError(f"approval pack {path} must be a non-empty string")
    return value


def _require_nonnegative_int(value: Any, path: str) -> None:
    if type(value) is not int or value < 0:
        raise WorkspaceError(f"approval pack {path} must be a non-negative integer")


def _require_bool(value: Any, path: str) -> None:
    if type(value) is not bool:
        raise WorkspaceError(f"approval pack {path} must be a boolean")


def _require_string_list(value: Any, path: str, *, canonical: bool = False) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise WorkspaceError(f"approval pack {path} must be a list of non-empty strings")
    if canonical and value != sorted(set(value)):
        raise WorkspaceError(f"approval pack {path} must be unique and canonically ordered")


def _require_digest(value: Any, path: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise WorkspaceError(f"approval pack {path} must be a sha256 digest")
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise WorkspaceError(f"approval pack {path} must be a sha256 digest") from exc


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result

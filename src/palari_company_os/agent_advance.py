from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .agent_done import _preflight
from .agent_handoff import build_agent_handoff
from .agent_runtime import claim_check, read_claim, read_claim_packet, release_agent
from .authoring import complete_work, reconcile_agent_proof
from .evidence_manifest import verify_evidence
from .governance_journal import workspace_digest
from .store import load_store
from .verification_attestations import (
    VerificationContext,
    VerificationProfile,
    cache_key,
    default_context,
    run_or_reuse,
    verification_profiles,
)
from .workspace import Workspace, WorkspaceError


SCHEMA_VERSION = "palari.agent_advance.v1"
_TERMINAL = {"completed", "closed", "done"}


def agent_advance_dry_run(
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
) -> dict[str, Any] | None:
    """Use an exact claim-bound packet for a fast, fail-closed dry-run.

    Legacy claims without a workspace-file binding return ``None`` so callers
    can use the fully validated compatibility path.
    """

    from .store import workspace_file_path

    workspace_path = Path(workspace_path)
    claim = read_claim(workspace_path, work_id)
    if not claim or not claim.get("workspace_file_hash"):
        return None
    data_path = workspace_file_path(workspace_path)
    try:
        current_hash = "sha256:" + hashlib.sha256(data_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise WorkspaceError(f"cannot hash workspace for advance dry-run: {exc}") from exc
    if current_hash != claim["workspace_file_hash"]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "work_item": work_id,
            "workspace": "",
            "can_advance": False,
            "would_mutate": False,
            "dry_run": True,
            "expected_state": "unknown",
            "blockers": [
                {
                    "code": "WORKSPACE_CHANGED_SINCE_CLAIM",
                    "message": "Workspace bytes changed after the validated claim packet was persisted.",
                    "next_safe_action": (
                        f"Run palari agent start {work_id} --as {palari_id} "
                        "--mode execute --json after inspecting the change."
                    ),
                }
            ],
            "steps": [],
        }
    packet = read_claim_packet(workspace_path, claim)
    claim_result = claim_check(
        workspace_path,
        work_id,
        palari_id,
        "execute",
        str(packet.get("context_hash") or ""),
    )
    preflight = _preflight(
        SimpleNamespace(path=data_path.parent),
        workspace_path,
        work_id,
        palari_id,
        None,
        packet=packet,
    )
    work = packet.get("work_item", {})
    proof = packet.get("proof_state", {})
    attempt = proof.get("attempt") if isinstance(proof, dict) else None
    receipt = proof.get("receipt") if isinstance(proof, dict) else None
    evidence = proof.get("evidence") if isinstance(proof, dict) else None
    changed = list(preflight.get("changed_files", []))
    profiles = verification_profiles(str(work.get("risk") or ""), changed)
    base_sha = str(preflight.get("base_sha") or "")
    head_sha = str(preflight.get("head_sha") or "")
    context = default_context(
        head_sha=head_sha,
        base_sha=base_sha,
        changed_paths=changed,
        cleanliness="clean" if preflight.get("ok") else "unverified",
    )
    evidence_current = bool(
        isinstance(evidence, dict)
        and evidence.get("status") == "passed"
        and evidence.get("head_sha") == head_sha
    )
    facts = {
        "actor": palari_id,
        "work": {
            "id": work_id,
            "palari": packet.get("agent", {}).get("id", ""),
            "risk": work.get("risk", ""),
            "intensity": work.get("intensity", ""),
            "status": work.get("status", ""),
            "required_approval_count": work.get("required_approval_count", 0),
            "current_attempt": attempt.get("id", "") if isinstance(attempt, dict) else "",
        },
        "packet": {
            "status": packet.get("status", "blocked"),
            "context_hash": packet.get("context_hash", ""),
        },
        "claim": {
            "status": claim_result.get("status", "fail"),
            "claimed_by": claim.get("claimed_by", ""),
            "context_hash": claim.get("context_hash", ""),
            "base_sha": base_sha,
        },
        "git": {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "clean": bool(preflight.get("ok")),
            "changed_files": changed,
            "scope_ok": bool(preflight.get("ok")),
            "outputs_ok": bool(preflight.get("ok")),
            "preflight_error": "" if preflight.get("ok") else preflight.get("message", ""),
        },
        "proof": {
            "attempt_id": attempt.get("id", "") if isinstance(attempt, dict) else "",
            "receipt_id": receipt.get("id", "") if isinstance(receipt, dict) else "",
            "evidence_id": evidence.get("id", "") if isinstance(evidence, dict) else "",
            "attempt_current": isinstance(attempt, dict),
            "attempt_bound": isinstance(attempt, dict),
            "receipt_current": isinstance(receipt, dict),
            "evidence_current": evidence_current,
            "attempt_closed": bool(
                isinstance(attempt, dict)
                and attempt.get("status") in {"complete", "completed"}
                and attempt.get("head_sha") == head_sha
            ),
        },
        "verification_profiles": [
            {
                "profile_id": profile.id,
                "cache_key": cache_key(profile, context),
                "status": "required",
            }
            for profile in profiles
        ],
        "workspace_digest": current_hash,
    }
    plan = plan_advance(facts)
    return {
        **plan,
        "workspace": str(packet.get("workspace") or ""),
        "status": "planned" if plan["can_advance"] else "blocked",
        "dry_run": True,
        "would_mutate": False,
        "preflight": preflight,
        "fast_path": True,
    }


def plan_advance(facts: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic plan from supplied facts without I/O or mutation."""

    work = _mapping(facts, "work")
    packet = _mapping(facts, "packet")
    claim = _mapping(facts, "claim")
    git = _mapping(facts, "git")
    proof = _mapping(facts, "proof")
    actor = str(facts.get("actor") or "")
    profiles = _profiles(facts.get("verification_profiles", []))
    blockers: list[dict[str, str]] = []

    _block(blockers, not actor, "ACTOR_MISSING", "An acting Palari is required.")
    _block(
        blockers,
        bool(work.get("palari")) and work.get("palari") != actor,
        "ACTOR_NOT_ASSIGNED",
        "The acting Palari is not assigned to this work item.",
    )
    _block(
        blockers,
        packet.get("status") != "ready",
        "PACKET_NOT_READY",
        "The execute packet is not ready.",
    )
    _block(
        blockers,
        claim.get("status") != "pass",
        "CLAIM_INVALID",
        "An exact active execute claim is required.",
    )
    _block(
        blockers,
        claim.get("claimed_by") != actor,
        "CLAIM_OWNER_MISMATCH",
        "The active claim belongs to a different Palari.",
    )
    _block(
        blockers,
        claim.get("context_hash") != packet.get("context_hash"),
        "CLAIM_CONTEXT_STALE",
        "The claim is not bound to the current packet.",
    )
    preflight_error = str(git.get("preflight_error") or "")
    if preflight_error:
        _block(blockers, True, "PREFLIGHT_BLOCKED", preflight_error)
    else:
        _block(
            blockers,
            not git.get("clean"),
            "GIT_DIRTY",
            "The governed candidate must be clean and committed.",
        )
        _block(
            blockers,
            git.get("base_sha") != claim.get("base_sha"),
            "CLAIM_BASE_MISMATCH",
            "The observed commit range does not start at the claim baseline.",
        )
        _block(blockers, not git.get("head_sha"), "GIT_HEAD_MISSING", "Git HEAD is missing.")
        _block(
            blockers,
            not git.get("changed_files"),
            "NO_COMMITTED_CHANGE",
            "No committed candidate change exists after the claim baseline.",
        )
        _block(
            blockers,
            not git.get("scope_ok"),
            "SCOPE_VIOLATION",
            "The committed range escapes the packet write boundary.",
        )
        _block(
            blockers,
            not git.get("outputs_ok"),
            "OUTPUT_MISSING",
            "One or more required output targets are missing.",
        )

    low_risk = (
        work.get("risk") == "R1"
        and work.get("intensity") == "light"
        and work.get("required_approval_count") == 0
    )
    expected_state = "completed" if low_risk else "review-required"
    steps: list[dict[str, Any]] = []
    for profile in profiles:
        steps.append(
            {
                "step": "verify",
                "profile_id": profile["profile_id"],
                "cache_key": profile["cache_key"],
                "status": profile["status"],
            }
        )
    steps.extend(
        [
            {"step": "attempt-record", "status": _needed(proof, "attempt_current")},
            {"step": "work-attempt-bind", "status": _needed(proof, "attempt_bound")},
            {"step": "receipt-record", "status": _needed(proof, "receipt_current")},
            {"step": "evidence-record", "status": _needed(proof, "evidence_current")},
            {"step": "attempt-closeout", "status": _needed(proof, "attempt_closed")},
            {"step": "agent-finish", "status": "required"},
            {
                "step": "lifecycle-complete" if low_risk else "review-handoff",
                "status": "required",
            },
            {"step": "claim-release", "status": "required"},
        ]
    )
    digest_payload = {
        "schema_version": SCHEMA_VERSION,
        "actor": actor,
        "work": {
            key: work.get(key)
            for key in (
                "id",
                "palari",
                "risk",
                "intensity",
                "status",
                "required_approval_count",
                "current_attempt",
            )
        },
        "packet": {
            "status": packet.get("status"),
            "context_hash": packet.get("context_hash"),
        },
        "claim": {
            "status": claim.get("status"),
            "claimed_by": claim.get("claimed_by"),
            "context_hash": claim.get("context_hash"),
            "base_sha": claim.get("base_sha"),
        },
        "git": {
            "base_sha": git.get("base_sha"),
            "head_sha": git.get("head_sha"),
            "clean": git.get("clean"),
            "changed_files": sorted(set(git.get("changed_files", []))),
            "scope_ok": git.get("scope_ok"),
            "outputs_ok": git.get("outputs_ok"),
            "preflight_error": git.get("preflight_error", ""),
        },
        "workspace_digest": facts.get("workspace_digest", ""),
        "proof": proof,
        "verification_profiles": [
            {"profile_id": item["profile_id"], "cache_key": item["cache_key"]}
            for item in profiles
        ],
        "expected_state": expected_state,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "work_item": str(work.get("id") or ""),
        "actor": actor,
        "can_advance": not blockers,
        "blockers": blockers,
        "steps": steps,
        "expected_state": expected_state,
        "stop_boundary": "none" if low_risk else "independent-review",
        "plan_digest": _digest(digest_payload),
    }


def agent_advance(
    workspace: Workspace,
    workspace_path: Path | str,
    work_id: str,
    palari_id: str,
    *,
    dry_run: bool = False,
    summary: str = "",
    refresh_verification: bool = False,
) -> dict[str, Any]:
    workspace_path = Path(workspace_path)
    resumed = _completed_projection(workspace, workspace_path, work_id, palari_id)
    if resumed is not None:
        return resumed
    facts, profiles, context, preflight = _collect_facts(
        workspace, workspace_path, work_id, palari_id
    )
    plan = plan_advance(facts)
    payload: dict[str, Any] = {
        **plan,
        "workspace": workspace.name,
        "status": "planned" if plan["can_advance"] else "blocked",
        "dry_run": dry_run,
        "would_mutate": bool(plan["can_advance"] and not dry_run),
        "preflight": preflight,
    }
    if dry_run or not plan["can_advance"]:
        return payload

    verification_results: list[dict[str, Any]] = []
    for profile in profiles:
        result = run_or_reuse(
            workspace_path,
            preflight["git_root"],
            profile,
            context,
            refresh=refresh_verification,
        )
        attestation = result["attestation"]
        verification_results.append(
            {
                "profile_id": profile.id,
                "attestation_id": attestation["attestation_id"],
                "cache_key": attestation["cache_key"],
                "cache_hit": result["cache_hit"],
                "status": attestation["status"],
                "duration_ms": attestation["duration_ms"],
                "stdout_digest": attestation["stdout_digest"],
                "stderr_digest": attestation["stderr_digest"],
            }
        )
        if attestation["status"] != "passed":
            return {
                **payload,
                "status": "verification-failed",
                "would_mutate": False,
                "verification": verification_results,
                "message": f"Verification profile {profile.id} did not pass.",
                "output_tail": result.get("stdout_tail", ""),
                "error_tail": result.get("stderr_tail", ""),
            }

    current = Workspace.load(workspace_path)
    current_facts, _, _, current_preflight = _collect_facts(
        current, workspace_path, work_id, palari_id
    )
    current_plan = plan_advance(current_facts)
    if current_plan["plan_digest"] != plan["plan_digest"] or not current_plan["can_advance"]:
        return {
            **payload,
            "status": "state-changed",
            "would_mutate": False,
            "verification": verification_results,
            "current_plan": current_plan,
            "current_preflight": current_preflight,
            "message": "Governed state changed during verification; inspect and retry safely.",
        }

    proof_steps = _reconcile_proof(
        current,
        workspace_path,
        work_id,
        palari_id,
        current_preflight,
        verification_results,
        summary,
    )
    final_workspace = Workspace.load(workspace_path)
    work = final_workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found after proof reconciliation: {work_id}")
    low_risk = (
        work.risk == "R1"
        and work.intensity == "light"
        and work.required_approval_count == 0
    )
    if low_risk:
        _release_claim_if_owned(
            final_workspace, workspace_path, work_id, palari_id, proof_steps
        )
        complete_work(
            str(workspace_path),
            work_id,
            "completed",
            command="agent advance",
            actor=palari_id,
        )
        proof_steps.append({"step": "lifecycle-complete", "status": "completed"})
        return {
            **payload,
            "status": "completed",
            "would_mutate": True,
            "verification": verification_results,
            "proof_steps": proof_steps,
            "expected_state": "completed",
            "message": f"Work item {work_id} advanced to completed.",
        }

    _release_claim_if_owned(final_workspace, workspace_path, work_id, palari_id, proof_steps)
    final_workspace = Workspace.load(workspace_path)
    handoff = build_agent_handoff(final_workspace, work_id, palari_id, "execute")
    proof_steps.append(
        {
            "step": "review-handoff",
            "status": "ready" if handoff.get("review_handoff") else "blocked",
        }
    )
    return {
        **payload,
        "status": "review-required" if handoff.get("review_handoff") else "proof-recorded",
        "would_mutate": True,
        "verification": verification_results,
        "proof_steps": proof_steps,
        "expected_state": "review-required",
        "handoff": handoff,
        "message": (
            f"Work item {work_id} has exact proof and is ready for independent review."
            if handoff.get("review_handoff")
            else f"Work item {work_id} proof was recorded; inspect the remaining blockers."
        ),
    }


def _collect_facts(
    workspace: Workspace,
    workspace_path: Path,
    work_id: str,
    palari_id: str,
) -> tuple[dict[str, Any], tuple[VerificationProfile, ...], VerificationContext, dict[str, Any]]:
    from .agent_packets import build_agent_brief
    from .agent_runtime import claim_check

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    packet = build_agent_brief(workspace, work_id, palari_id, "execute")
    claim = read_claim(workspace_path, work_id) or {}
    claim_result = claim_check(
        workspace_path,
        work_id,
        palari_id,
        "execute",
        str(packet.get("context_hash") or ""),
    )
    preflight = _preflight(
        workspace,
        workspace_path,
        work_id,
        palari_id,
        None,
        packet=packet,
    )
    changed = list(preflight.get("changed_files", []))
    profiles = verification_profiles(work.risk, changed)
    base_sha = str(preflight.get("base_sha") or claim.get("git_baseline", {}).get("head_sha") or "")
    head_sha = str(preflight.get("head_sha") or "")
    context = default_context(
        head_sha=head_sha,
        base_sha=base_sha,
        changed_paths=changed,
        cleanliness="clean" if preflight.get("ok") else "unverified",
    )
    profile_facts = [
        {
            "profile_id": profile.id,
            "cache_key": cache_key(profile, context),
            "status": "required",
        }
        for profile in profiles
    ]
    attempt = _select_attempt(workspace, work_id, palari_id, head_sha)
    receipt_id = _proof_id("RECEIPT-ADVANCE", work_id, head_sha)
    evidence_id = _proof_id("EVIDENCE-ADVANCE", work_id, head_sha)
    receipt = next((item for item in workspace.receipts if item.id == receipt_id), None)
    evidence = next((item for item in workspace.evidence_runs if item.id == evidence_id), None)
    facts = {
        "actor": palari_id,
        "work": {
            "id": work.id,
            "palari": work.palari,
            "risk": work.risk,
            "intensity": work.intensity,
            "status": work.status,
            "required_approval_count": work.required_approval_count,
            "current_attempt": work.current_attempt,
        },
        "packet": {
            "status": packet.get("status", "blocked"),
            "context_hash": packet.get("context_hash", ""),
        },
        "claim": {
            "status": claim_result.get("status", "fail"),
            "claimed_by": claim.get("claimed_by", ""),
            "context_hash": claim.get("context_hash", ""),
            "base_sha": base_sha,
        },
        "git": {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "clean": bool(preflight.get("ok")),
            "changed_files": changed,
            "scope_ok": bool(preflight.get("ok")),
            "outputs_ok": bool(preflight.get("ok")),
            "preflight_error": "" if preflight.get("ok") else preflight.get("message", ""),
        },
        "proof": {
            "attempt_id": attempt.id if attempt else "",
            "receipt_id": receipt_id,
            "evidence_id": evidence_id,
            "attempt_current": bool(attempt),
            "attempt_bound": bool(attempt and work.current_attempt == attempt.id),
            "receipt_current": bool(receipt),
            "evidence_current": bool(
                evidence and evidence.status == "passed" and evidence.head_sha == head_sha
            ),
            "attempt_closed": bool(
                attempt
                and attempt.status in {"complete", "completed"}
                and (attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")) == head_sha
            ),
        },
        "verification_profiles": profile_facts,
        "workspace_digest": workspace_digest(load_store(workspace_path).data),
    }
    return facts, profiles, context, preflight


def _reconcile_proof(
    workspace: Workspace,
    workspace_path: Path,
    work_id: str,
    palari_id: str,
    preflight: dict[str, Any],
    verification: list[dict[str, Any]],
    summary: str,
) -> list[dict[str, str]]:
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    head_sha = str(preflight["head_sha"])
    attempt = _select_attempt(workspace, work_id, palari_id, head_sha)
    if attempt is None:
        attempt_id = _proof_id("ATTEMPT-ADVANCE", work_id, head_sha)
    else:
        attempt_id = attempt.id

    artifacts = _governed_artifacts(preflight["changed_files"])
    if not artifacts:
        raise WorkspaceError("no non-governance output artifact remains to bind as evidence")
    receipt_id = _proof_id("RECEIPT-ADVANCE", work_id, head_sha)
    evidence_id = _proof_id("EVIDENCE-ADVANCE", work_id, head_sha)
    action = summary.strip() or f"Changed {len(artifacts)} bounded committed artifact(s)."
    commands = [
        f"{item['profile_id']} attestation {item['attestation_id']} {item['cache_key']}"
        for item in verification
    ]
    result = reconcile_agent_proof(
        str(workspace_path),
        work_id=work_id,
        palari_id=palari_id,
        attempt_record={
            "id": attempt_id,
            "work_item_id": work_id,
            "actor": palari_id,
            "status": "active",
            "workspace_path": str(Path(preflight["git_root"])),
            "base_sha": preflight["base_sha"],
        },
        receipt_record={
            "id": receipt_id,
            "work_item_id": work_id,
            "attempt_id": attempt_id,
            "actor": palari_id,
            "sources_used": list(work.allowed_sources),
            "actions_taken": [action, "Ran exact-state Palari verification profiles."],
            "outputs_created": artifacts,
            "not_done": [
                "No human review, decision, acceptance, external write, push, merge, or deployment was performed."
            ],
            "undo_refs": artifacts,
        },
        evidence_record={
            "id": evidence_id,
            "work_item_id": work_id,
            "attempt_id": attempt_id,
            "head_sha": head_sha,
            "status": "passed",
            "base_ref": preflight["base_sha"],
            "commands": commands,
            "artifacts": artifacts,
            "summary": f"{len(verification)} exact-state verification profile(s) passed.",
            "freshness": "exact-head",
        },
        head_sha=head_sha,
        changed_files=list(preflight["changed_files"]),
        output_targets=list(work.output_targets),
    )
    return list(result["steps"])


def _completed_projection(
    workspace: Workspace,
    workspace_path: Path,
    work_id: str,
    palari_id: str,
) -> dict[str, Any] | None:
    from .agent_done import _git_value
    from .governance_journal import recover_workspace_journal, verify_workspace_journal

    journal = verify_workspace_journal(workspace_path)
    journal_status = str(journal.get("status") or "")
    if journal_status == "pending-commit":
        recovered = recover_workspace_journal(
            workspace_path,
            palari_id,
            action="auto",
            reason="resume atomic agent proof reconciliation",
        )
        if not recovered.get("ok"):
            raise WorkspaceError(
                "agent advance cannot recover the pending proof commit: "
                + str(recovered.get("message") or recovered.get("status") or "unknown")
            )
        workspace = Workspace.load(workspace_path)
    elif journal_status == "pending-prepare":
        recovered = recover_workspace_journal(
            workspace_path,
            palari_id,
            action="abort",
            reason="retry atomic agent proof reconciliation before workspace replacement",
        )
        if not recovered.get("ok"):
            raise WorkspaceError(
                "agent advance cannot abort the unapplied proof prepare: "
                + str(recovered.get("message") or recovered.get("status") or "unknown")
            )
        workspace = Workspace.load(workspace_path)
    elif journal_status not in {"", "not-enabled", "valid", "continuous"}:
        raise WorkspaceError(
            f"agent advance requires valid journal continuity; status is {journal_status}"
        )

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    if work.status in _TERMINAL:
        steps: list[dict[str, str]] = [{"step": "resume", "status": "already-completed"}]
        _release_claim_if_owned(workspace, workspace_path, work_id, palari_id, steps)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "completed",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_advance": True,
            "would_mutate": False,
            "expected_state": "completed",
            "message": f"Work item {work_id} is already completed.",
            "steps": steps,
        }
    if not work.current_attempt:
        return None
    attempt = next(
        (item for item in workspace.attempts if item.id == work.current_attempt),
        None,
    )
    if attempt is None or attempt.status not in {"complete", "completed"}:
        return None
    root = Path(attempt.workspace_path) if attempt.workspace_path else workspace_path
    head_sha = _git_value(root, ["rev-parse", "HEAD"])
    attempt_head = attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")
    if not head_sha or attempt_head != head_sha:
        return None
    evidence = next(
        (
            item
            for item in reversed(workspace.evidence_runs)
            if item.work_item_id == work_id
            and item.attempt_id == attempt.id
            and item.head_sha == head_sha
            and item.status == "passed"
        ),
        None,
    )
    if evidence is None:
        return None
    verification = verify_evidence(workspace, evidence.id, require_output_coverage=True)
    if not verification["ok"]:
        return None
    proof_steps: list[dict[str, str]] = [
        {"step": "proof-projection", "status": "already-current"}
    ]
    low_risk = (
        work.risk == "R1"
        and work.intensity == "light"
        and work.required_approval_count == 0
    )
    if low_risk:
        _release_claim_if_owned(workspace, workspace_path, work_id, palari_id, proof_steps)
        complete_work(
            str(workspace_path),
            work_id,
            "completed",
            command="agent advance",
            actor=palari_id,
        )
        proof_steps.append({"step": "lifecycle-complete", "status": "completed"})
        workspace = Workspace.load(workspace_path)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "completed",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_advance": True,
            "would_mutate": True,
            "expected_state": "completed",
            "proof_steps": proof_steps,
            "message": f"Work item {work_id} resumed from exact proof and completed.",
        }
    _release_claim_if_owned(workspace, workspace_path, work_id, palari_id, proof_steps)
    workspace = Workspace.load(workspace_path)
    handoff = build_agent_handoff(workspace, work_id, palari_id, "execute")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "review-required" if handoff.get("review_handoff") else "proof-recorded",
        "work_item": work_id,
        "workspace": workspace.name,
        "can_advance": True,
        "would_mutate": False,
        "expected_state": "review-required",
        "proof_steps": proof_steps,
        "handoff": handoff,
        "message": f"Work item {work_id} already has current exact proof.",
    }


def _release_claim_if_owned(
    workspace: Workspace,
    workspace_path: Path,
    work_id: str,
    palari_id: str,
    steps: list[dict[str, str]],
) -> None:
    claim = read_claim(workspace_path, work_id)
    if claim and claim.get("claimed_by") == palari_id:
        release_agent(workspace, workspace_path, work_id, palari_id)
        steps.append({"step": "claim-release", "status": "released"})


def _select_attempt(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    head_sha: str,
) -> Any | None:
    work = workspace.work_item(work_id)
    if work is not None and work.current_attempt:
        current = next(
            (item for item in workspace.attempts if item.id == work.current_attempt),
            None,
        )
        if current is not None and current.actor == palari_id:
            current_head = current.head_sha or (current.commits[-1] if current.commits else "")
            if current.status not in {"complete", "completed"} or current_head == head_sha:
                return current
    expected_id = _proof_id("ATTEMPT-ADVANCE", work_id, head_sha)
    return next((item for item in workspace.attempts if item.id == expected_id), None)


def _governed_artifacts(paths: list[str]) -> list[str]:
    return sorted(
        path
        for path in set(paths)
        if not path.endswith("/workspace.json")
        and not path.endswith("/.palari/history.jsonl")
        and path != "workspace.json"
        and path != ".palari/history.jsonl"
    )


def _proof_id(prefix: str, work_id: str, head_sha: str) -> str:
    suffix = (head_sha or "UNBOUND")[:12].upper()
    safe_work = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in work_id)
    return f"{prefix}-{safe_work}-{suffix}"


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key, {})
    return value if isinstance(value, dict) else {}


def _profiles(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    profiles: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        profiles.append(
            {
                "profile_id": str(item.get("profile_id") or ""),
                "cache_key": str(item.get("cache_key") or ""),
                "status": str(item.get("status") or "required"),
            }
        )
    return sorted(profiles, key=lambda item: (item["profile_id"], item["cache_key"]))


def _block(
    blockers: list[dict[str, str]],
    condition: bool,
    code: str,
    message: str,
) -> None:
    if condition:
        blockers.append(
            {
                "code": code,
                "message": message,
                "next_safe_action": "Inspect the current agent packet and retry only after the exact condition is corrected.",
            }
        )


def _needed(proof: dict[str, Any], key: str) -> str:
    return "resume" if proof.get(key) else "create"


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()

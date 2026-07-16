from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from .agent_done import _preflight
from .agent_handoff import build_agent_handoff
from .agent_runtime import claim_check, read_claim, read_claim_packet, release_agent
from .authoring import (
    ReconciliationStateChanged,
    complete_work,
    reconcile_agent_proof,
)
from .evidence_manifest import git_artifact_state, verify_evidence
from .governance_journal import workspace_digest
from .governance_convergence import converge_work_item
from .record_order import record_time_key
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
        cast(Workspace, SimpleNamespace(path=data_path.parent)),
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
        and evidence.get("id") == _proof_id("EVIDENCE-ADVANCE", work_id, head_sha)
    )
    attempt_head = ""
    attempt_status = ""
    if isinstance(attempt, dict):
        attempt_head = str(attempt.get("head_sha") or "")
        commits = attempt.get("commits")
        if not attempt_head and isinstance(commits, list) and commits:
            attempt_head = str(commits[-1] or "")
        attempt_status = str(attempt.get("status") or "")
    attempt_current = bool(
        isinstance(attempt, dict)
        and (
            attempt_status not in {"complete", "completed"}
            or attempt_head == head_sha
        )
    )
    receipt_current = bool(
        isinstance(receipt, dict)
        and receipt.get("id") == _proof_id("RECEIPT-ADVANCE", work_id, head_sha)
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
            "attempt_id": (
                attempt.get("id", "") if attempt_current and isinstance(attempt, dict) else ""
            ),
            "receipt_id": (
                receipt.get("id", "")
                if receipt_current and isinstance(receipt, dict)
                else ""
            ),
            "evidence_id": (
                evidence.get("id", "")
                if evidence_current and isinstance(evidence, dict)
                else ""
            ),
            "attempt_current": attempt_current,
            "attempt_bound": attempt_current,
            "receipt_current": receipt_current,
            "evidence_current": evidence_current,
            "attempt_closed": bool(
                attempt_current
                and attempt_status in {"complete", "completed"}
                and attempt_head == head_sha
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
            "artifact_hashes": git.get("artifact_hashes", []),
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
    if not dry_run:
        resumed = _completed_projection(
            workspace,
            workspace_path,
            work_id,
            palari_id,
            refresh_verification=refresh_verification,
        )
        if resumed is not None:
            return resumed
    if summary.strip():
        raise WorkspaceError(
            "agent advance persists deterministic receipt actions only; omit --summary and "
            "record non-authoritative commentary outside governance proof"
        )
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

    try:
        proof_steps = _reconcile_proof(
            current,
            workspace_path,
            work_id,
            palari_id,
            current_preflight,
            verification_results,
            summary,
            expected_workspace_digest=str(current_facts["workspace_digest"]),
            expected_git_head=str(current_facts["git"]["head_sha"]),
            expected_artifact_hashes=list(
                current_facts["git"]["artifact_hashes"]
            ),
        )
    except ReconciliationStateChanged:
        return {
            **payload,
            "status": "state-changed",
            "would_mutate": False,
            "verification": verification_results,
            "message": "Governed state changed before proof reconciliation; inspect and retry safely.",
        }
    final_workspace = Workspace.load(workspace_path)
    work = final_workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found after proof reconciliation: {work_id}")
    low_risk = (
        work.risk == "R1"
        and work.intensity == "light"
        and work.required_approval_count == 0
    )
    resume_preflight = _resume_preflight(
        final_workspace, workspace_path, work, palari_id
    )
    if not resume_preflight["ok"]:
        return {
            **payload,
            "status": "state-changed",
            "would_mutate": False,
            "verification": verification_results,
            "proof_steps": proof_steps,
            "preflight": resume_preflight,
            "message": (
                "Governed state changed after proof reconciliation; "
                + resume_preflight["message"]
            ),
        }
    if low_risk:
        complete_work(
            str(workspace_path),
            work_id,
            "completed",
            command="agent advance",
            actor=palari_id,
        )
        proof_steps.append({"step": "lifecycle-complete", "status": "completed"})
        _release_claim_if_owned(
            Workspace.load(workspace_path),
            workspace_path,
            work_id,
            palari_id,
            proof_steps,
        )
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
    artifacts = _governed_artifacts(changed)
    artifact_state = git_artifact_state(
        Path(str(preflight.get("git_root") or workspace_path)),
        artifacts,
        governance_workspace_path=workspace_path,
    )
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
            "clean": bool(
                preflight.get("ok")
                and artifact_state["clean"]
                and artifact_state["head_sha"] == head_sha
            ),
            "changed_files": changed,
            "scope_ok": bool(preflight.get("ok")),
            "outputs_ok": bool(preflight.get("ok")),
            "preflight_error": "" if preflight.get("ok") else preflight.get("message", ""),
            "artifact_hashes": artifact_state["artifact_hashes"],
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
    *,
    expected_workspace_digest: str,
    expected_git_head: str,
    expected_artifact_hashes: list[dict[str, str]],
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
    action = f"Changed {len(artifacts)} bounded committed artifact(s)."
    proof_timestamp = _git_commit_timestamp(preflight)
    if not proof_timestamp:
        raise WorkspaceError("Git HEAD timestamp is unavailable for deterministic proof binding")
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
            "allowed_paths": list(work.allowed_resources),
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
            "artifact_hashes": expected_artifact_hashes,
            "summary": f"{len(verification)} exact-state verification profile(s) passed.",
            "freshness": "exact-head",
        },
        head_sha=head_sha,
        changed_files=list(preflight["changed_files"]),
        output_targets=list(work.output_targets),
        proof_timestamp=proof_timestamp,
        expected_workspace_digest=expected_workspace_digest,
        expected_git_head=expected_git_head,
        expected_artifact_hashes=expected_artifact_hashes,
    )
    return list(result["steps"])


def _completed_projection(
    workspace: Workspace,
    workspace_path: Path,
    work_id: str,
    palari_id: str,
    *,
    refresh_verification: bool = False,
) -> dict[str, Any] | None:
    from .governance_journal import (
        pending_workspace_journal_context,
        recover_workspace_journal_if_current,
        verify_workspace_journal,
    )

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    if work.palari != palari_id:
        return _resume_blocked(
            workspace,
            work_id,
            "ACTOR_NOT_ASSIGNED",
            "The acting Palari is not assigned to this work item.",
        )
    journal = verify_workspace_journal(workspace_path)
    journal_status = str(journal.get("status") or "")
    if journal_status == "pending-commit":
        pending = pending_workspace_journal_context(workspace_path)
        recovery_preflight = _resume_preflight(
            workspace, workspace_path, work, palari_id
        )
        if not recovery_preflight["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RESUME_PREFLIGHT_FAILED",
                str(recovery_preflight["message"]),
            )
        pending_error = _pending_advance_recovery_error(
            pending, work_id, palari_id, recovery_preflight, workspace_path
        )
        if pending_error:
            return _resume_blocked(
                workspace,
                work_id,
                "PENDING_TRANSACTION_MISMATCH",
                pending_error,
            )
        recovery_verification = _run_recovery_verification(
            workspace_path, work, recovery_preflight
        )
        if not recovery_verification["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RECOVERY_VERIFICATION_FAILED",
                str(recovery_verification["message"]),
            )
        rechecked = _recheck_recovery_state(
            workspace_path,
            work_id,
            palari_id,
            "pending-commit",
            pending,
            recovery_preflight,
        )
        if not rechecked["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RECOVERY_STATE_CHANGED",
                str(rechecked["message"]),
            )
        workspace = rechecked["workspace"]
        work = rechecked["work"]
        pending = rechecked["pending"]
        recovery_preflight = rechecked["preflight"]
        pending_error = _pending_advance_recovery_error(
            pending,
            work_id,
            palari_id,
            recovery_preflight,
            workspace_path,
            verified_commands=recovery_verification["commands"],
        )
        if pending_error:
            return _resume_blocked(
                workspace,
                work_id,
                "PENDING_TRANSACTION_MISMATCH",
                pending_error,
            )
        prepare = pending["prepare"]
        recovered = recover_workspace_journal_if_current(
            workspace_path,
            palari_id,
            expected_status="pending-commit",
            expected_workspace_digest=str(prepare["after_workspace_digest"]),
            expected_prepare_digest=str(prepare["record_digest"]),
            expected_transaction_id=str(prepare["transaction_id"]),
            action="auto",
            reason="resume atomic agent proof reconciliation",
        )
        if not recovered.get("ok"):
            return _resume_blocked(
                workspace,
                work_id,
                "RECOVERY_STATE_CHANGED",
                "The pending proof changed before atomic commit recovery: "
                + str(recovered.get("message") or recovered.get("status") or "unknown"),
            )
        workspace = Workspace.load(workspace_path)
    elif journal_status == "pending-prepare":
        pending = pending_workspace_journal_context(workspace_path)
        recovery_preflight = _resume_preflight(
            workspace, workspace_path, work, palari_id
        )
        if not recovery_preflight["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RESUME_PREFLIGHT_FAILED",
                str(recovery_preflight["message"]),
            )
        pending_error = _pending_advance_recovery_error(
            pending, work_id, palari_id, recovery_preflight, workspace_path
        )
        if pending_error:
            return _resume_blocked(
                workspace,
                work_id,
                "PENDING_TRANSACTION_MISMATCH",
                pending_error,
            )
        recovery_verification = _run_recovery_verification(
            workspace_path, work, recovery_preflight
        )
        if not recovery_verification["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RECOVERY_VERIFICATION_FAILED",
                str(recovery_verification["message"]),
            )
        rechecked = _recheck_recovery_state(
            workspace_path,
            work_id,
            palari_id,
            "pending-prepare",
            pending,
            recovery_preflight,
        )
        if not rechecked["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RECOVERY_STATE_CHANGED",
                str(rechecked["message"]),
            )
        workspace = rechecked["workspace"]
        work = rechecked["work"]
        pending = rechecked["pending"]
        recovery_preflight = rechecked["preflight"]
        pending_error = _pending_advance_recovery_error(
            pending,
            work_id,
            palari_id,
            recovery_preflight,
            workspace_path,
            verified_commands=recovery_verification["commands"],
        )
        if pending_error:
            return _resume_blocked(
                workspace,
                work_id,
                "PENDING_TRANSACTION_MISMATCH",
                pending_error,
            )
        prepare = pending["prepare"]
        recovered = recover_workspace_journal_if_current(
            workspace_path,
            palari_id,
            expected_status="pending-prepare",
            expected_workspace_digest=str(prepare["before_workspace_digest"]),
            expected_prepare_digest=str(prepare["record_digest"]),
            expected_transaction_id=str(prepare["transaction_id"]),
            action="abort",
            reason="retry atomic agent proof reconciliation before workspace replacement",
        )
        if not recovered.get("ok"):
            return _resume_blocked(
                workspace,
                work_id,
                "RECOVERY_STATE_CHANGED",
                "The pending proof changed before atomic abort recovery: "
                + str(recovered.get("message") or recovered.get("status") or "unknown"),
            )
        workspace = Workspace.load(workspace_path)
    elif journal_status not in {"", "not-enabled", "valid", "continuous"}:
        raise WorkspaceError(
            f"agent advance requires valid journal continuity; status is {journal_status}"
        )

    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    if work.palari != palari_id:
        return _resume_blocked(
            workspace,
            work_id,
            "ACTOR_NOT_ASSIGNED",
            "The acting Palari is not assigned to this work item.",
        )
    if work.status in _TERMINAL:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "completed",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_advance": True,
            "would_mutate": False,
            "expected_state": "completed",
            "message": f"Work item {work_id} is already completed.",
            "steps": [{"step": "resume", "status": "already-completed"}],
        }
    if _changes_requested_repair_candidate(
        workspace,
        workspace_path,
        work,
        palari_id,
    ):
        return None
    convergence = converge_work_item(
        workspace_path,
        work_id,
        actor=palari_id,
    )
    if convergence["status"] == "completed":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "completed",
            "work_item": work_id,
            "workspace": workspace.name,
            "can_advance": True,
            "would_mutate": bool(convergence["would_mutate"]),
            "expected_state": "completed",
            "authority_source": "preexisting-current-human-decision",
            "performed_human_authority": False,
            "proof_steps": [
                {
                    "step": item["action"],
                    "status": item["status"],
                }
                for item in convergence["steps"]
            ],
            "convergence": convergence,
            "message": (
                f"Work item {work_id} used its current human decision and "
                "was deterministically completed."
            ),
        }
    if convergence["status"] == "blocked":
        code = str(convergence.get("code") or "CURRENT_PROOF_INVALID")
        if code == "CURRENT_PROOF_INVALID" and refresh_verification:
            try:
                return _refresh_stale_projection(
                    workspace,
                    workspace_path,
                    work,
                    palari_id,
                    convergence,
                )
            except ReconciliationStateChanged:
                latest = Workspace.load(workspace_path)
                return _resume_blocked(
                    latest,
                    work.id,
                    "REFRESH_STATE_CHANGED",
                    "Governed state changed before the proof transaction began; inspect and retry.",
                )
        if code == "TRANSITION_REJECTED":
            code = "ACCEPTED_COMPLETION_INVALID"
        return _resume_blocked(
            workspace,
            work_id,
            code,
            str(convergence.get("message") or "Automatic reconciliation failed closed."),
        )
    if not work.current_attempt:
        return None
    attempt = next(
        (item for item in workspace.attempts if item.id == work.current_attempt),
        None,
    )
    if attempt is None or attempt.status not in {"complete", "completed"}:
        return None
    if attempt.actor != palari_id:
        return _resume_blocked(
            workspace,
            work_id,
            "ATTEMPT_ACTOR_MISMATCH",
            "The current proof attempt belongs to a different Palari.",
        )
    attempt_head = attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")
    head_sha = attempt_head
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
        errors = verification.get("errors", [])
        detail = "; ".join(str(item) for item in errors[:3])
        return _resume_blocked(
            workspace,
            work_id,
            "CURRENT_PROOF_INVALID",
            "The recorded exact proof no longer verifies"
            + (f": {detail}" if detail else "."),
        )
    proof_steps: list[dict[str, str]] = [
        {"step": "proof-projection", "status": "already-current"}
    ]
    low_risk = (
        work.risk == "R1"
        and work.intensity == "light"
        and work.required_approval_count == 0
    )
    if low_risk:
        preflight = _resume_preflight(workspace, workspace_path, work, palari_id)
        if not preflight["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RESUME_PREFLIGHT_FAILED",
                str(preflight["message"]),
            )
        complete_work(
            str(workspace_path),
            work_id,
            "completed",
            command="agent advance",
            actor=palari_id,
        )
        proof_steps.append({"step": "lifecycle-complete", "status": "completed"})
        workspace = Workspace.load(workspace_path)
        _release_claim_if_owned(workspace, workspace_path, work_id, palari_id, proof_steps)
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
    claim = read_claim(workspace_path, work_id)
    if claim is not None:
        preflight = _resume_preflight(workspace, workspace_path, work, palari_id)
        if not preflight["ok"]:
            return _resume_blocked(
                workspace,
                work_id,
                "RESUME_PREFLIGHT_FAILED",
                str(preflight["message"]),
            )
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


def _refresh_stale_projection(
    workspace: Workspace,
    workspace_path: Path,
    work: Any,
    palari_id: str,
    convergence: dict[str, Any],
) -> dict[str, Any]:
    """Rebind unchanged outputs to current HEAD after later repository changes.

    This is deliberately a no-write recovery path for governed artifacts. It
    does not reuse prior review or human authority: the new attempt becomes the
    current proof and the caller stops at an independent-review handoff.
    """

    refresh = _stale_projection_refresh_context(
        workspace,
        workspace_path,
        work,
        palari_id,
        convergence,
    )
    if not refresh["ok"]:
        return _resume_blocked(
            workspace,
            work.id,
            str(refresh["code"]),
            str(refresh["message"]),
        )

    profiles = verification_profiles(work.risk, refresh["committed_paths"])
    context = default_context(
        head_sha=refresh["head_sha"],
        base_sha=refresh["proof_head"],
        changed_paths=refresh["committed_paths"],
        cleanliness="clean",
    )
    verification_results: list[dict[str, Any]] = []
    for profile in profiles:
        result = run_or_reuse(
            workspace_path,
            refresh["git_root"],
            profile,
            context,
            refresh=True,
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
                "schema_version": SCHEMA_VERSION,
                "status": "verification-failed",
                "work_item": work.id,
                "workspace": workspace.name,
                "can_advance": False,
                "would_mutate": False,
                "expected_state": "review-required",
                "verification": verification_results,
                "message": f"Verification profile {profile.id} did not pass.",
                "output_tail": result.get("stdout_tail", ""),
                "error_tail": result.get("stderr_tail", ""),
            }

    current = Workspace.load(workspace_path)
    current_work = current.work_item(work.id)
    if current_work is None:
        return _resume_blocked(
            current,
            work.id,
            "REFRESH_STATE_CHANGED",
            "The work item disappeared during proof refresh.",
        )
    current_convergence = converge_work_item(
        workspace_path,
        work.id,
        actor=palari_id,
    )
    rechecked = _stale_projection_refresh_context(
        current,
        workspace_path,
        current_work,
        palari_id,
        current_convergence,
    )
    stable_fields = (
        "workspace_digest",
        "attempt_id",
        "evidence_id",
        "proof_head",
        "head_sha",
        "committed_paths",
        "artifacts",
        "artifact_hashes",
        "git_root",
    )
    if not rechecked["ok"] or any(
        rechecked.get(field) != refresh.get(field) for field in stable_fields
    ):
        return _resume_blocked(
            current,
            work.id,
            "REFRESH_STATE_CHANGED",
            "Governed state changed while current-head verification was running; inspect and retry.",
        )

    commit_timestamp = _git_commit_timestamp(
        {"git_root": refresh["git_root"], "head_sha": refresh["head_sha"]}
    )
    if not commit_timestamp:
        return _resume_blocked(
            current,
            work.id,
            "REFRESH_HEAD_TIMESTAMP_MISSING",
            "The current Git commit timestamp is unavailable; proof refresh stopped safely.",
        )
    proof_timestamp = _refresh_proof_timestamp(current, work.id, commit_timestamp)
    commands = [
        f"{item['profile_id']} attestation {item['attestation_id']} {item['cache_key']}"
        for item in verification_results
    ]
    attempt_id = _proof_id("ATTEMPT-REFRESH", work.id, refresh["head_sha"])
    receipt_id = _proof_id("RECEIPT-REFRESH", work.id, refresh["head_sha"])
    evidence_id = _proof_id("EVIDENCE-REFRESH", work.id, refresh["head_sha"])
    reconciled = reconcile_agent_proof(
        str(workspace_path),
        work_id=work.id,
        palari_id=palari_id,
        attempt_record={
            "id": attempt_id,
            "work_item_id": work.id,
            "actor": palari_id,
            "status": "active",
            "workspace_path": refresh["git_root"],
            "base_sha": refresh["proof_head"],
            "allowed_paths": list(refresh["artifacts"]),
        },
        receipt_record={
            "id": receipt_id,
            "work_item_id": work.id,
            "attempt_id": attempt_id,
            "actor": palari_id,
            "sources_used": list(work.allowed_sources),
            "actions_taken": [
                f"Reverified {len(refresh['artifacts'])} unchanged governed artifact(s) at current repository HEAD.",
                "Reran the authoritative exact-state verification profiles.",
            ],
            "outputs_created": list(refresh["artifacts"]),
            "not_done": [
                "No governed artifact bytes were changed.",
                "No review, human decision, acceptance, external write, push, merge, or deployment was performed.",
            ],
            "undo_refs": [],
        },
        evidence_record={
            "id": evidence_id,
            "work_item_id": work.id,
            "attempt_id": attempt_id,
            "head_sha": refresh["head_sha"],
            "status": "passed",
            "base_ref": refresh["proof_head"],
            "commands": commands,
            "artifacts": list(refresh["artifacts"]),
            "artifact_hashes": list(refresh["artifact_hashes"]),
            "summary": (
                f"{len(verification_results)} exact-state verification profile(s) "
                "passed for unchanged governed artifacts."
            ),
            "freshness": "exact-head",
        },
        head_sha=refresh["head_sha"],
        changed_files=[],
        output_targets=list(refresh["artifacts"]),
        proof_timestamp=proof_timestamp,
        expected_workspace_digest=str(refresh["workspace_digest"]),
        expected_git_head=str(refresh["head_sha"]),
        expected_artifact_hashes=list(refresh["artifact_hashes"]),
    )
    final_workspace = Workspace.load(workspace_path)
    handoff = build_agent_handoff(final_workspace, work.id, palari_id, "execute")
    proof_steps = list(reconciled["steps"])
    proof_steps.append(
        {
            "step": "review-handoff",
            "status": "ready" if handoff.get("review_handoff") else "blocked",
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "review-required" if handoff.get("review_handoff") else "proof-recorded",
        "work_item": work.id,
        "workspace": final_workspace.name,
        "can_advance": True,
        "would_mutate": True,
        "expected_state": "review-required",
        "stop_boundary": "independent-review",
        "refresh": {
            "previous_head": refresh["proof_head"],
            "current_head": refresh["head_sha"],
            "artifacts_unchanged": True,
            "performed_human_authority": False,
        },
        "verification": verification_results,
        "proof_steps": proof_steps,
        "handoff": handoff,
        "message": (
            f"Work item {work.id} has refreshed exact-head proof and requires "
            "fresh independent review."
        ),
    }


def _stale_projection_refresh_context(
    workspace: Workspace,
    workspace_path: Path,
    work: Any,
    palari_id: str,
    convergence: dict[str, Any],
) -> dict[str, Any]:
    if convergence.get("status") != "blocked" or convergence.get("code") != "CURRENT_PROOF_INVALID":
        return {
            "ok": False,
            "code": "REFRESH_NOT_APPLICABLE",
            "message": "Proof refresh is available only for an invalidated completed proof.",
        }
    if work.palari != palari_id:
        return {
            "ok": False,
            "code": "ACTOR_NOT_ASSIGNED",
            "message": "Only the Palari assigned to this work may refresh its proof.",
        }
    if read_claim(workspace_path, work.id) is not None:
        return {
            "ok": False,
            "code": "REFRESH_ACTIVE_CLAIM",
            "message": "Release the active execute claim before starting a read-only proof refresh.",
        }
    if not work.current_attempt:
        return {
            "ok": False,
            "code": "REFRESH_ATTEMPT_MISSING",
            "message": "The work item has no completed proof attempt to refresh.",
        }
    attempt = next(
        (item for item in workspace.attempts if item.id == work.current_attempt),
        None,
    )
    if attempt is None or attempt.status not in {"complete", "completed"}:
        return {
            "ok": False,
            "code": "REFRESH_ATTEMPT_INCOMPLETE",
            "message": "The current proof attempt is not complete.",
        }
    if attempt.actor != palari_id:
        return {
            "ok": False,
            "code": "ATTEMPT_ACTOR_MISMATCH",
            "message": "The current proof attempt belongs to a different Palari.",
        }
    proof_head = attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")
    evidence = next(
        (
            item
            for item in reversed(workspace.evidence_runs)
            if item.work_item_id == work.id
            and item.attempt_id == attempt.id
            and item.head_sha == proof_head
            and item.status == "passed"
        ),
        None,
    )
    if evidence is None:
        return {
            "ok": False,
            "code": "REFRESH_EVIDENCE_MISSING",
            "message": "The completed attempt has no passing exact-head evidence to refresh.",
        }
    verification = verify_evidence(workspace, evidence.id, require_output_coverage=True)
    if not verification["ok"]:
        detail = "; ".join(str(item) for item in verification.get("errors", [])[:3])
        return {
            "ok": False,
            "code": "REFRESH_ARTIFACT_CHANGED",
            "message": (
                "The governed artifact bytes no longer match the previous evidence"
                + (f": {detail}" if detail else ".")
            ),
        }
    projection = convergence.get("proof")
    if not isinstance(projection, dict):
        return {
            "ok": False,
            "code": "REFRESH_PROJECTION_MISSING",
            "message": "The invalidated proof has no inspectable Git projection.",
        }
    if projection.get("proof_head") != proof_head:
        return {
            "ok": False,
            "code": "REFRESH_PROJECTION_MISMATCH",
            "message": "The invalidated Git projection does not bind the current proof attempt.",
        }
    dirty = list(projection.get("dirty_tracked_paths") or [])
    if dirty:
        return {
            "ok": False,
            "code": "REFRESH_DIRTY_WORKTREE",
            "message": "Proof refresh requires a clean tracked worktree: " + ", ".join(dirty),
        }
    head_sha = str(projection.get("current_head") or "")
    committed_paths = sorted(set(projection.get("committed_paths") or []))
    if not head_sha or head_sha == proof_head or not committed_paths:
        return {
            "ok": False,
            "code": "REFRESH_COMMITTED_CHANGE_MISSING",
            "message": "No later committed repository state is available for proof refresh.",
        }
    from .agent_done import _git_value

    root_text = _git_value(
        Path(attempt.workspace_path or workspace_path),
        ["rev-parse", "--show-toplevel"],
    )
    if not root_text:
        return {
            "ok": False,
            "code": "REFRESH_REPOSITORY_UNAVAILABLE",
            "message": "The proof workspace is not inside a readable Git repository.",
        }
    artifacts = sorted(set(work.output_targets))
    if not artifacts:
        return {
            "ok": False,
            "code": "REFRESH_ARTIFACT_MISSING",
            "message": "The work item has no governed output target to refresh.",
        }
    return {
        "ok": True,
        "code": "",
        "message": "Unchanged governed artifacts may be reverified at current HEAD.",
        "workspace_digest": workspace_digest(load_store(workspace_path).data),
        "attempt_id": attempt.id,
        "evidence_id": evidence.id,
        "proof_head": proof_head,
        "head_sha": head_sha,
        "committed_paths": committed_paths,
        "artifacts": artifacts,
        "artifact_hashes": verification["computed_artifact_hashes"],
        "git_root": root_text,
    }


def _refresh_proof_timestamp(
    workspace: Workspace,
    work_id: str,
    commit_timestamp: str,
) -> str:
    """Return a deterministic timestamp strictly after existing work proof records."""

    candidates: list[datetime] = []
    for value in (commit_timestamp,):
        parsed = _parse_proof_timestamp(value)
        if parsed is not None:
            candidates.append(parsed)
    collections = (
        workspace.attempts,
        workspace.receipts,
        workspace.evidence_runs,
        workspace.review_verdicts,
        workspace.human_decisions,
        workspace.acceptance_records,
    )
    for records in collections:
        for record in records:
            if getattr(record, "work_item_id", "") != work_id:
                continue
            for field in ("updated_at", "started_at", "timestamp", "accepted_at"):
                parsed = _parse_proof_timestamp(str(getattr(record, field, "") or ""))
                if parsed is not None:
                    candidates.append(parsed)
    commit_instant = _parse_proof_timestamp(commit_timestamp)
    if commit_instant is None:
        return ""
    latest_existing = max(candidates, default=commit_instant)
    logical = max(commit_instant, latest_existing + timedelta(microseconds=1))
    return logical.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _parse_proof_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (OverflowError, ValueError):
        return None
    if parsed.utcoffset() is None:
        return None
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError:
        return None


def _resume_claim_packet(
    workspace_path: Path,
    work: Any,
    palari_id: str,
) -> dict[str, Any]:
    if work.palari != palari_id:
        return {"ok": False, "message": "the acting Palari is not assigned to this work"}
    claim = read_claim(workspace_path, work.id)
    if claim is None:
        return {"ok": False, "message": "an exact active execute claim is required"}
    try:
        packet = read_claim_packet(workspace_path, claim)
    except WorkspaceError as exc:
        return {"ok": False, "message": str(exc)}
    checked = claim_check(
        workspace_path,
        work.id,
        palari_id,
        "execute",
        str(packet.get("context_hash") or ""),
    )
    if checked.get("status") != "pass":
        return {
            "ok": False,
            "message": str(checked.get("message") or "active claim is invalid"),
        }
    return {"ok": True, "claim": checked["claim"], "packet": packet, "message": ""}


def _pending_advance_recovery_error(
    context: dict[str, Any] | None,
    work_id: str,
    palari_id: str,
    preflight: dict[str, Any],
    workspace_path: Path,
    *,
    verified_commands: list[str] | None = None,
) -> str:
    if not isinstance(context, dict):
        return "The pending journal transaction cannot be inspected safely."
    prepared = context.get("prepare")
    before = context.get("before_projection")
    if not isinstance(prepared, dict) or not isinstance(before, dict):
        return "The pending journal transaction has no verified before projection."
    metadata = prepared.get("metadata")
    if not isinstance(metadata, dict):
        return "The pending journal transaction has no valid metadata."
    if (
        metadata.get("command") != "agent advance"
        or metadata.get("action") != "reconciled-agent-proof"
        or metadata.get("actor") != palari_id
    ):
        return "The pending journal transaction is not this Palari's agent proof."

    objects = metadata.get("objects")
    if not isinstance(objects, list):
        return "The pending journal transaction has no bound proof objects."
    keyed: dict[tuple[str, str], str] = {}
    for item in objects:
        if not isinstance(item, dict):
            return "The pending journal transaction has malformed proof objects."
        key = (str(item.get("type") or ""), str(item.get("collection") or ""))
        record_id = str(item.get("id") or "")
        if not all(key) or not record_id or key in keyed:
            return "The pending journal transaction has ambiguous proof objects."
        keyed[key] = record_id
    expected_keys = {
        ("work", "work_items"),
        ("attempt", "attempts"),
        ("receipt", "receipts"),
        ("evidence", "evidence_runs"),
    }
    if set(keyed) != expected_keys or keyed[("work", "work_items")] != work_id:
        return "The pending journal transaction does not bind this exact work proof."

    after = prepared.get("after_projection")
    if not isinstance(after, dict):
        return "The pending journal transaction has no proof projection."
    collection_ids = {
        "work_items": keyed[("work", "work_items")],
        "attempts": keyed[("attempt", "attempts")],
        "receipts": keyed[("receipt", "receipts")],
        "evidence_runs": keyed[("evidence", "evidence_runs")],
    }
    if not _only_bound_records_changed(before, after, collection_ids):
        return "The pending journal transaction changes objects outside its proof binding."

    work = _record_by_id(after, "work_items", collection_ids["work_items"])
    attempt = _record_by_id(after, "attempts", collection_ids["attempts"])
    receipt = _record_by_id(after, "receipts", collection_ids["receipts"])
    evidence = _record_by_id(after, "evidence_runs", collection_ids["evidence_runs"])
    if not all(isinstance(item, dict) for item in (work, attempt, receipt, evidence)):
        return "The pending journal projection is missing a bound proof object."
    assert isinstance(work, dict)
    assert isinstance(attempt, dict)
    assert isinstance(receipt, dict)
    assert isinstance(evidence, dict)
    try:
        projected_workspace = Workspace.from_raw(after, workspace_path)
    except WorkspaceError as exc:
        return f"The pending journal proof projection is invalid: {exc}"
    before_work = _record_by_id(before, "work_items", collection_ids["work_items"])
    before_attempt = _record_by_id(before, "attempts", collection_ids["attempts"])
    before_receipt = _record_by_id(before, "receipts", collection_ids["receipts"])
    before_evidence = _record_by_id(
        before, "evidence_runs", collection_ids["evidence_runs"]
    )
    if not isinstance(before_work, dict) or not _record_changes_within(
        before_work, work, {"current_attempt"}
    ):
        return "The pending journal transaction changes work authority, not only proof binding."
    if isinstance(before_attempt, dict) and not _record_changes_within(
        before_attempt,
        attempt,
        {
            "status",
            "head_sha",
            "commits",
            "cleanliness",
            "updated_at",
            "changed_files",
            "output_targets",
        },
    ):
        return "The pending journal transaction changes immutable attempt authority."
    if before_attempt is None and any(
        not _empty_record_value(attempt.get(field))
        for field in (
            "branch",
            "model_or_worker",
            "claim_id",
            "claim_expires_at",
            "result",
        )
    ):
        return "The pending journal transaction injects ungenerated attempt metadata."
    if before_attempt is None and any(
        not _empty_record_value(attempt.get(field))
        for field in ("forbidden_paths",)
    ):
        return "The pending journal transaction injects ungenerated attempt boundaries."
    if isinstance(before_receipt, dict) and before_receipt != receipt:
        return "The pending journal transaction rewrites an existing receipt."
    if isinstance(before_evidence, dict) and before_evidence != evidence:
        return "The pending journal transaction rewrites existing evidence."
    if any(
        not _empty_record_value(receipt.get(field))
        for field in ("context_packet", "context_hash", "evidence_manifest_hash")
    ) or any(
        not _empty_record_value(receipt.get(field))
        for field in ("planned_external_writes", "queued_external_writes", "external_writes")
    ):
        return "The pending journal transaction injects external or ungenerated receipt claims."
    attempt_id = collection_ids["attempts"]
    head_sha = str(attempt.get("head_sha") or "")
    current_attempt_id = str(before_work.get("current_attempt") or "")
    current_attempt = (
        _record_by_id(before, "attempts", current_attempt_id)
        if current_attempt_id
        else None
    )
    current_attempt_head = ""
    if isinstance(current_attempt, dict):
        current_attempt_head = str(current_attempt.get("head_sha") or "")
        if not current_attempt_head:
            commits = current_attempt.get("commits")
            if isinstance(commits, list) and commits:
                current_attempt_head = str(commits[-1] or "")
    current_attempt_reusable = (
        isinstance(current_attempt, dict)
        and current_attempt.get("actor") == palari_id
        and (
            current_attempt.get("status") not in {"complete", "completed"}
            or current_attempt_head == head_sha
        )
    )
    expected_attempt_id = (
        current_attempt_id
        if current_attempt_reusable
        else _proof_id("ATTEMPT-ADVANCE", work_id, head_sha)
    )
    expected_receipt_id = _proof_id("RECEIPT-ADVANCE", work_id, head_sha)
    expected_evidence_id = _proof_id("EVIDENCE-ADVANCE", work_id, head_sha)
    before_commits = (
        list(before_attempt.get("commits") or [])
        if isinstance(before_attempt, dict)
        else []
    )
    expected_commits = list(before_commits)
    if not expected_commits or expected_commits[-1] != head_sha:
        expected_commits.append(head_sha)
    allowed_resources = work.get("allowed_resources")
    allowed_paths = attempt.get("allowed_paths")
    changed_files = list(preflight.get("changed_files") or [])
    artifacts = _governed_artifacts(changed_files)
    actions = receipt.get("actions_taken")
    not_done = receipt.get("not_done")
    expected_not_done = [
        "No human review, decision, acceptance, external write, push, merge, or deployment was performed."
    ]
    expected_action = f"Changed {len(artifacts)} bounded committed artifact(s)."
    commands = evidence.get("commands")
    expected_previous_receipt_hash = _latest_receipt_hash(before, work_id)
    receipt_action = actions[0] if isinstance(actions, list) and actions else ""
    paths_bound = (
        isinstance(allowed_resources, list)
        and isinstance(allowed_paths, list)
        and bool(allowed_paths)
        and allowed_paths == allowed_resources
    )
    if (
        attempt_id != expected_attempt_id
        or collection_ids["receipts"] != expected_receipt_id
        or collection_ids["evidence_runs"] != expected_evidence_id
        or work.get("current_attempt") != attempt_id
        or attempt.get("work_item_id") != work_id
        or attempt.get("actor") != palari_id
        or attempt.get("status") not in {"complete", "completed"}
        or not head_sha
        or head_sha != preflight.get("head_sha")
        or attempt.get("base_sha") != preflight.get("base_sha")
        or Path(str(attempt.get("workspace_path") or "")).resolve()
        != Path(str(preflight.get("git_root") or "")).resolve()
        or not paths_bound
        or attempt.get("changed_files") != changed_files
        or attempt.get("output_targets") != work.get("output_targets")
        or attempt.get("cleanliness") != "clean"
        or attempt.get("commits") != expected_commits
        or receipt.get("work_item_id") != work_id
        or receipt.get("attempt_id") != attempt_id
        or receipt.get("actor") != palari_id
        or receipt.get("sources_used") != work.get("allowed_sources")
        or receipt.get("outputs_created") != artifacts
        or receipt.get("undo_refs") != artifacts
        or str(receipt.get("previous_receipt_hash") or "")
        != expected_previous_receipt_hash
        or not isinstance(actions, list)
        or len(actions) != 2
        or actions[0] != expected_action
        or actions[1] != "Ran exact-state Palari verification profiles."
        or metadata.get("reason") != f"receipt-action:{receipt_action}"
        or not_done != expected_not_done
        or evidence.get("work_item_id") != work_id
        or evidence.get("attempt_id") != attempt_id
        or evidence.get("head_sha") != head_sha
        or evidence.get("status") != "passed"
        or evidence.get("base_ref") != preflight.get("base_sha")
        or evidence.get("artifacts") != artifacts
        or evidence.get("freshness") != "exact-head"
        or evidence.get("previous_receipt_hash") not in {None, ""}
        or not isinstance(commands, list)
        or not commands
        or not _verification_commands_bound(commands, work, preflight)
        or (verified_commands is not None and commands != verified_commands)
        or evidence.get("output_binding_version") != "palari.evidence_outputs.v1"
        or evidence.get("summary")
        != f"{len(commands)} exact-state verification profile(s) passed."
        or not _recovery_timestamps_bound(
            attempt,
            receipt,
            evidence,
            metadata,
            before_attempt,
            before_receipt,
            before_evidence,
            _git_commit_timestamp(preflight),
        )
    ):
        return "The pending journal projection has contradictory proof bindings."
    evidence_verification = verify_evidence(
        projected_workspace,
        expected_evidence_id,
        require_output_coverage=True,
    )
    if not evidence_verification["ok"]:
        return "The pending journal projection does not contain verifiable exact evidence."
    return ""


def _run_recovery_verification(
    workspace_path: Path,
    work: Any,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    changed_files = list(preflight.get("changed_files") or [])
    profiles = verification_profiles(str(work.risk), changed_files)
    context = default_context(
        head_sha=str(preflight.get("head_sha") or ""),
        base_sha=str(preflight.get("base_sha") or ""),
        changed_paths=changed_files,
        cleanliness="clean",
    )
    commands: list[str] = []
    for profile in profiles:
        result = run_or_reuse(
            workspace_path,
            Path(str(preflight.get("git_root") or "")),
            profile,
            context,
            refresh=True,
        )
        attestation = result["attestation"]
        if attestation.get("status") != "passed":
            return {
                "ok": False,
                "commands": [],
                "message": f"Recovery verification profile {profile.id} did not pass.",
            }
        commands.append(
            f"{profile.id} attestation {attestation['attestation_id']} "
            f"{attestation['cache_key']}"
        )
    return {"ok": True, "commands": commands, "message": ""}


def _recheck_recovery_state(
    workspace_path: Path,
    work_id: str,
    palari_id: str,
    expected_status: str,
    expected_pending: dict[str, Any] | None,
    expected_preflight: dict[str, Any],
) -> dict[str, Any]:
    from .governance_journal import (
        pending_workspace_journal_context,
        verify_workspace_journal,
    )

    try:
        workspace = Workspace.load(workspace_path)
    except WorkspaceError as exc:
        return {"ok": False, "message": f"Workspace changed during verification: {exc}"}
    work = workspace.work_item(work_id)
    if work is None or work.palari != palari_id:
        return {"ok": False, "message": "Work authority changed during verification."}
    preflight = _resume_preflight(workspace, workspace_path, work, palari_id)
    compared_fields = ("git_root", "base_sha", "head_sha", "changed_files")
    if not preflight.get("ok") or any(
        preflight.get(field) != expected_preflight.get(field) for field in compared_fields
    ):
        return {"ok": False, "message": "Claim, Git, or scope state changed during verification."}
    report = verify_workspace_journal(workspace_path)
    pending = pending_workspace_journal_context(workspace_path)
    expected_prepare = (
        expected_pending.get("prepare") if isinstance(expected_pending, dict) else None
    )
    current_prepare = pending.get("prepare") if isinstance(pending, dict) else None
    if (
        report.get("status") != expected_status
        or not isinstance(expected_prepare, dict)
        or not isinstance(current_prepare, dict)
        or current_prepare.get("record_digest") != expected_prepare.get("record_digest")
        or current_prepare.get("transaction_id") != expected_prepare.get("transaction_id")
    ):
        return {"ok": False, "message": "Pending proof transaction changed during verification."}
    return {
        "ok": True,
        "message": "",
        "workspace": workspace,
        "work": work,
        "preflight": preflight,
        "pending": pending,
    }


def _only_bound_records_changed(
    before: dict[str, Any],
    after: dict[str, Any],
    collection_ids: dict[str, str],
) -> bool:
    for key in set(before) | set(after):
        if key not in collection_ids and before.get(key) != after.get(key):
            return False
    for collection, allowed_id in collection_ids.items():
        before_records = _records_by_id(before.get(collection))
        after_records = _records_by_id(after.get(collection))
        if before_records is None or after_records is None:
            return False
        for record_id in set(before_records) | set(after_records):
            if record_id != allowed_id and before_records.get(record_id) != after_records.get(
                record_id
            ):
                return False
    return True


def _record_changes_within(
    before: dict[str, Any], after: dict[str, Any], allowed_fields: set[str]
) -> bool:
    return all(
        key in allowed_fields or before.get(key) == after.get(key)
        for key in set(before) | set(after)
    )


def _empty_record_value(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == ()


def _latest_receipt_hash(projection: dict[str, Any], work_id: str) -> str:
    receipts = projection.get("receipts")
    if not isinstance(receipts, list):
        return ""
    candidates = [
        item
        for item in receipts
        if isinstance(item, dict)
        and item.get("work_item_id") == work_id
        and item.get("receipt_hash")
    ]
    if not candidates:
        return ""
    latest = max(candidates, key=record_time_key)
    return str(latest.get("receipt_hash") or "")


def _verification_commands_bound(
    commands: list[Any], work: dict[str, Any], preflight: dict[str, Any]
) -> bool:
    changed_files = list(preflight.get("changed_files") or [])
    expected_profiles = verification_profiles(str(work.get("risk") or ""), changed_files)
    if len(commands) != len(expected_profiles):
        return False
    context = default_context(
        head_sha=str(preflight.get("head_sha") or ""),
        base_sha=str(preflight.get("base_sha") or ""),
        changed_paths=changed_files,
        cleanliness="clean",
    )
    for command, profile in zip(commands, expected_profiles, strict=True):
        if not isinstance(command, str):
            return False
        key = cache_key(profile, context)
        attestation_id = f"VERIFY-{profile.id.upper()}-{key[-16:].upper()}"
        if command != f"{profile.id} attestation {attestation_id} {key}":
            return False
    return True


def _recovery_timestamps_bound(
    attempt: dict[str, Any],
    receipt: dict[str, Any],
    evidence: dict[str, Any],
    metadata: dict[str, Any],
    before_attempt: dict[str, Any] | None,
    before_receipt: dict[str, Any] | None,
    before_evidence: dict[str, Any] | None,
    expected_event_timestamp: str,
) -> bool:
    event_timestamp = metadata.get("timestamp")
    if event_timestamp != expected_event_timestamp or not expected_event_timestamp:
        return False
    try:
        event_time = datetime.fromisoformat(
            event_timestamp.removesuffix("Z") + "+00:00"
        )
    except ValueError:
        return False
    closeout_changed = before_attempt is None or any(
        attempt.get(field) != before_attempt.get(field)
        for field in (
            "status",
            "head_sha",
            "commits",
            "cleanliness",
            "changed_files",
            "output_targets",
        )
    )
    expected = [
        event_timestamp
        if before_attempt is None
        else before_attempt.get("started_at"),
        event_timestamp
        if before_receipt is None
        else before_receipt.get("timestamp"),
        event_timestamp
        if before_evidence is None
        else before_evidence.get("timestamp"),
        event_timestamp
        if closeout_changed
        else before_attempt.get("updated_at") if before_attempt is not None else "",
    ]
    actual = [
        attempt.get("started_at"),
        receipt.get("timestamp"),
        evidence.get("timestamp"),
        attempt.get("updated_at"),
    ]
    if actual != expected:
        return False
    try:
        proof_times = [
            datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
            for value in actual
            if isinstance(value, str) and value.endswith("Z")
        ]
    except ValueError:
        return False
    return len(proof_times) == len(actual) and all(value <= event_time for value in proof_times)


def _git_commit_timestamp(preflight: dict[str, Any]) -> str:
    from .agent_done import _git_value

    raw = _git_value(
        Path(str(preflight.get("git_root") or "")),
        ["show", "-s", "--format=%ct", str(preflight.get("head_sha") or "")],
    )
    try:
        timestamp = datetime.fromtimestamp(int(raw), timezone.utc)
    except (OverflowError, ValueError):
        return ""
    return timestamp.isoformat(timespec="seconds").replace("+00:00", "Z")


def _records_by_id(value: Any) -> dict[str, dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            return None
        record_id = str(item.get("id") or "")
        if not record_id or record_id in result:
            return None
        result[record_id] = item
    return result


def _record_by_id(
    projection: dict[str, Any], collection: str, record_id: str
) -> dict[str, Any] | None:
    records = _records_by_id(projection.get(collection))
    return records.get(record_id) if records is not None else None


def _resume_preflight(
    workspace: Workspace,
    workspace_path: Path,
    work: Any,
    palari_id: str,
) -> dict[str, Any]:
    authority = _resume_claim_packet(workspace_path, work, palari_id)
    if not authority["ok"]:
        return {
            "ok": False,
            "message": str(authority["message"]),
            "git_root": "",
            "base_sha": "",
            "head_sha": "",
            "changed_files": [],
        }
    return _preflight(
        workspace,
        workspace_path,
        work.id,
        palari_id,
        None,
        packet=authority["packet"],
        allow_current_proof_projection=True,
    )


def _resume_blocked(
    workspace: Workspace,
    work_id: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked",
        "work_item": work_id,
        "workspace": workspace.name,
        "can_advance": False,
        "would_mutate": False,
        "expected_state": "blocked",
        "blockers": [{"code": code, "message": message}],
        "message": message,
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


def _changes_requested_repair_candidate(
    workspace: Workspace,
    workspace_path: Path,
    work: Any,
    palari_id: str,
) -> bool:
    reviews = [
        item for item in workspace.review_verdicts if item.work_item_id == work.id
    ]
    if not reviews or not work.current_attempt:
        return False
    latest = max(reviews, key=record_time_key)
    if latest.verdict != "changes-requested":
        return False
    attempt = next(
        (item for item in workspace.attempts if item.id == work.current_attempt),
        None,
    )
    if attempt is None or attempt.actor != palari_id:
        return False
    attempt_head = attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")
    if not attempt_head or latest.reviewed_head != attempt_head:
        return False
    from .agent_done import _git_value

    current_head = _git_value(workspace_path, ["rev-parse", "HEAD"])
    return bool(current_head and current_head != attempt_head)


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

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .read_models import detail
from .workspace import Workspace


def build_review_guide(workspace: Workspace, work_id: str) -> dict[str, Any]:
    payload = detail(workspace, work_id)
    work = payload["work_item"]
    evidence = payload.get("evidence")
    attempt = payload.get("attempt")
    receipt = payload.get("receipt")
    review_focus = _review_focus(payload)
    return {
        "schema_version": "palari.review_guide.v1",
        "guide_id": f"REVIEW-GUIDE-{work_id}-V1",
        "created_at": _timestamp(),
        "workspace": workspace.name,
        "would_mutate": False,
        "status": _status(payload),
        "work_item": {
            "id": work["id"],
            "title": work["title"],
            "risk": work["risk"],
            "status": work["status"],
            "scope": work.get("scope", ""),
            "acceptance_target": work.get("acceptance_target", ""),
        },
        "workbench": payload.get("workbench"),
        "palari": _compact_ref(payload.get("palari"), ["id", "name", "role"]),
        "attention": payload.get("attention", ""),
        "why": payload.get("why", ""),
        "next_action": payload.get("next_action", ""),
        "evidence": _evidence_summary(evidence),
        "attempt": _attempt_summary(attempt),
        "receipt": _receipt_summary(receipt),
        "review_focus": review_focus,
        "suggested_verdicts": ["accept-ready", "changes-requested", "needs-human-decision", "blocked"],
        "review_record_command_template": _review_record_command_template(work_id, evidence),
        "next_commands": _next_commands(work_id),
        "omitted_context": [
            {
                "kind": "workspace_records",
                "reason": "Review guide v1 includes only records directly related to the selected work item.",
                "counts": {
                    "work_items": len(workspace.work_items),
                    "palaris": len(workspace.palaris),
                    "sources": len(workspace.sources),
                    "workbenches": len(workspace.workbenches),
                },
            }
        ],
    }


def _status(payload: dict[str, Any]) -> str:
    review_state = payload.get("safety", {}).get("review_state", "")
    if payload.get("attention") == "receipt-ready":
        return "receipt-ready"
    if review_state == "stale":
        return "stale-review"
    if payload.get("evidence") is None:
        return "missing-evidence"
    if payload.get("review") is not None:
        return "has-review"
    if payload.get("attention") in {"needs-review", "receipt-ready"}:
        return "review-needed"
    return "inspect"


def _evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    if evidence is None:
        return {"present": False}
    return {
        "present": True,
        "id": evidence.get("id", ""),
        "status": evidence.get("status", ""),
        "head_sha": evidence.get("head_sha", ""),
        "summary": evidence.get("summary", ""),
        "commands": evidence.get("commands", []),
        "artifacts": evidence.get("artifacts", []),
    }


def _attempt_summary(attempt: dict[str, Any] | None) -> dict[str, Any]:
    if attempt is None:
        return {"present": False}
    return {
        "present": True,
        "id": attempt.get("id", ""),
        "actor": attempt.get("actor", ""),
        "status": attempt.get("status", ""),
        "commits": attempt.get("commits", []),
        "changed_files": attempt.get("changed_files", []),
        "result": attempt.get("result", ""),
    }


def _receipt_summary(receipt: dict[str, Any] | None) -> dict[str, Any]:
    if receipt is None:
        return {"present": False}
    return {
        "present": True,
        "id": receipt.get("id", ""),
        "sources_used": receipt.get("sources_used", []),
        "actions_taken": receipt.get("actions_taken", []),
        "outputs_created": receipt.get("outputs_created", []),
        "external_writes": receipt.get("external_writes", []),
        "not_done": receipt.get("not_done", []),
        "undo_refs": receipt.get("undo_refs", []),
    }


def _review_focus(payload: dict[str, Any]) -> list[str]:
    focus = [
        "Compare the attempt result and changed files against the work scope and acceptance target.",
    ]
    if payload.get("attention") == "receipt-ready":
        focus.append(
            "For receipt-ready low-risk work, inspect the output and receipt before requiring heavier proof."
        )
        if payload.get("evidence") is not None:
            focus.append(
                "Use the evidence as supporting context; do not add a human-decision ceremony unless the scope or risk changed."
            )
    else:
        focus.append("Confirm evidence commands and artifacts are enough for the stated risk.")
    if payload.get("receipt") is None:
        focus.append(
            "Receipt is missing; confirm whether the work state intentionally relies on evidence and review instead."
        )
    else:
        focus.append(
            "Confirm the receipt honestly states sources used, outputs created, external writes, not-done items, and undo refs."
        )
    focus.append("Confirm forbidden actions were not performed.")
    if payload.get("work_item", {}).get("risk") in {"R3", "R4", "R5"}:
        focus.append("Check the higher-risk boundary before any human decision or integration.")
    receipt = payload.get("receipt") or {}
    if receipt.get("external_writes"):
        focus.append("Inspect every external write claim and require explicit human authority.")
    if payload.get("review") is not None:
        focus.append("A review already exists; verify whether it still matches the latest evidence head.")
    return focus


def _review_record_command_template(work_id: str, evidence: dict[str, Any] | None) -> str:
    if evidence is not None:
        reviewed_head = evidence.get("head_sha", "HEAD")
    else:
        reviewed_head = "HEAD"
    return (
        f"palari review record REVIEW-ID --work-item-id {work_id} "
        f"--reviewed-head {reviewed_head} --reviewer REVIEWER-ID "
        "--verdict VERDICT --json"
    )


def _next_commands(work_id: str) -> list[str]:
    return [f"palari detail {work_id} --json", "palari validate --json"]


def _compact_ref(record: dict[str, Any] | None, keys: list[str]) -> dict[str, Any]:
    if not record:
        return {}
    return {key: record.get(key, "") for key in keys}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

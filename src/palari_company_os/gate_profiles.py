from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import to_plain
from .read_models import detail
from .workspace import Workspace, WorkspaceError


@dataclass(frozen=True)
class GateProfile:
    id: str
    label: str
    summary: str
    applies_when: list[str]
    reviewer_role: str
    inspect: list[str]
    blocks_if: list[str]
    required_evidence: list[str]
    safe_to_accept_when: str
    example_failure: str


GATE_PROFILES: tuple[GateProfile, ...] = (
    GateProfile(
        id="prompt-authority",
        label="Untrusted Instructions",
        summary=(
            "Checks that untrusted content cannot become system or developer "
            "instructions or grant permission."
        ),
        applies_when=[
            "A task uses model prompts, OCR, image text, user-provided "
            "instructions, or source text as context.",
            "The result could change agent behavior, memory, tools, safety "
            "wording, or instructions.",
        ],
        reviewer_role="Untrusted-instruction reviewer",
        inspect=[
            "prompt construction and role placement",
            "untrusted source or image text handling",
            "tests with malicious instructions",
        ],
        blocks_if=[
            "untrusted content enters system/developer prompt content",
            "source text can override Palari rules, allowed actions, or stop conditions",
            "malicious text is not covered by regression tests",
        ],
        required_evidence=[
            "test or trace proving untrusted content stays labeled as data and "
            "never enters system or developer instructions",
            "review of prompt-building code or task brief (`packet`) fields",
        ],
        safe_to_accept_when=(
            "Untrusted text is clearly source material, cannot grant permission, "
            "and has regression coverage."
        ),
        example_failure=(
            "OCR text saying 'ignore previous rules' is inserted into a system prompt."
        ),
    ),
    GateProfile(
        id="source-boundary",
        label="Allowed Sources",
        summary="Checks that a task uses only allowed sources and reports source limits honestly.",
        applies_when=[
            "A task declares allowed sources or its run record (`receipt`) claims source use.",
            "An agent reads selected files, notes, repos, uploads, or external source snapshots.",
        ],
        reviewer_role="Allowed-sources reviewer",
        inspect=[
            "allowed_sources and source metadata",
            "run record (`receipt`) field `sources_used`",
            "source access mode, owner, steward, freshness, and redaction fields",
        ],
        blocks_if=[
            "result uses an unallowed, missing, stale, or unselected source",
            "source permissions are broadened silently",
            "run record overstates what was read or hides source limits",
        ],
        required_evidence=[
            "source IDs used by the run (`attempt`)",
            "run record or check results showing no access outside allowed sources",
        ],
        safe_to_accept_when=(
            "Every source used is declared, allowed for the agent, and honestly "
            "listed in the run record."
        ),
        example_failure="A result cites a file that was not in allowed_sources.",
    ),
    GateProfile(
        id="external-write",
        label="External Actions",
        summary=(
            "Checks that external actions remain planned, approved, queued, or "
            "explicitly absent."
        ),
        applies_when=[
            "A task has integration plans, outbox items, external-write claims, "
            "or external-action targets.",
            "Allowed actions include notify, send, comment, create_issue, "
            "update_issue, or publish.",
        ],
        reviewer_role="External-action reviewer",
        inspect=[
            "integration plans and outbox items",
            "run record (`receipt`) fields `planned_external_writes`, "
            "`queued_external_writes`, and `external_writes`",
            "allowed actions and output targets",
        ],
        blocks_if=[
            "live provider call is implied or performed by a dry-run plan",
            "external write lacks approved integration plan or queued outbox state",
            "run record claims an external write when only a dry-run or queued action exists",
        ],
        required_evidence=[
            "dry-run payload preview or outbox record",
            "run record distinguishing planned, queued, and actual external actions",
        ],
        safe_to_accept_when=(
            "External-action status is explicit and no live effect is claimed "
            "without human approval."
        ),
        example_failure=(
            "A Slack notification is described as sent when only a dry-run "
            "payload exists."
        ),
    ),
    GateProfile(
        id="human-approval",
        label="Human Approval",
        summary=(
            "Checks that qualified people, required approval counts, and "
            "approval permissions are not bypassed."
        ),
        applies_when=[
            "A task requires an approval count, approval capability, high-risk "
            "decision, or integration approval.",
            "A result is waiting on review, human approval, merge, deploy, "
            "policy, or product approval.",
        ],
        reviewer_role="Human-approval reviewer",
        inspect=[
            "required_approval_count and required_approval_capability",
            "review results (`review_verdicts`) and approval records (`human_decisions`)",
            "human profile permissions and availability",
        ],
        blocks_if=[
            "agent records or implies human approval",
            "required approvals are missing or counted from an unqualified person",
            "review recommendation is treated as founder approval",
        ],
        required_evidence=[
            "review result when required",
            "approval/rejection record (`human_decision`) or explicit needs-approval state",
        ],
        safe_to_accept_when=(
            "A qualified person has recorded every required approval, or the "
            "missing approval remains visible."
        ),
        example_failure=(
            "An accept-ready review result is treated as approved without an "
            "approval/rejection record (`human_decision`)."
        ),
    ),
    GateProfile(
        id="deploy-runtime",
        label="Deployment and Runtime",
        summary=(
            "Checks production, runtime data, secrets, storage, provider, and "
            "deploy boundaries."
        ),
        applies_when=[
            "A task touches deploy, runtime state, production, storage, provider "
            "routing, OAuth, or secrets.",
            "A task can affect live beta, public routes, databases, or environment configuration.",
        ],
        reviewer_role="Deploy/runtime reviewer",
        inspect=[
            "changed runtime/deploy/storage/provider paths",
            "secret and env-file boundaries",
            "live smoke, rollback, and backup check results when deployment is allowed",
        ],
        blocks_if=[
            "secrets, runtime data, or production state changed outside allowed files or actions",
            "deploy or provider routing changed without backup and smoke results",
            "tests pass locally but the live or runtime limit remains unchecked",
        ],
        required_evidence=[
            "file-boundary check for runtime or deploy files",
            "backup and smoke results when deployment is explicitly allowed",
        ],
        safe_to_accept_when=(
            "Runtime-impacting changes are explicit, verified, reversible, and "
            "do not expose secrets."
        ),
        example_failure="A beta deploy modifies runtime data or provider routing without approval.",
    ),
    GateProfile(
        id="privacy-multimodal",
        label="Private Media",
        summary=(
            "Checks privacy limits for images, uploads, OCR, screenshots, and "
            "other rich media."
        ),
        applies_when=[
            "A task reads images, screenshots, OCR, audio, video, uploads, or "
            "multimodal model output.",
            "A source or run record (`receipt`) may contain private visual or "
            "file-derived content.",
        ],
        reviewer_role="Private-media reviewer",
        inspect=[
            "raw media storage behavior",
            "extracted text and metadata handling",
            "logs, run records, source records, and storage limits",
        ],
        blocks_if=[
            "raw media is persisted when the task rules say read-once",
            "private extracted content is logged unnecessarily",
            "multimodal data is treated as trusted instructions",
        ],
        required_evidence=[
            "test proving invalid or oversized media stops safely when relevant",
            "check showing raw media is not stored beyond the allowed limit",
        ],
        safe_to_accept_when=(
            "Media-derived content is minimized, bounded, and treated as untrusted source material."
        ),
        example_failure="An uploaded screenshot is saved to workspace history without user intent.",
    ),
    GateProfile(
        id="product-overclaim",
        label="Honest Product Claims",
        summary="Checks public or product-facing copy for claims that exceed implemented behavior.",
        applies_when=[
            "A task changes README, website, marketing, onboarding, public docs, "
            "or user-facing claims.",
            "Copy describes AI capability, integrations, autonomy, memory, "
            "safety, or beta maturity.",
        ],
        reviewer_role="Product-claim reviewer",
        inspect=[
            "public/user-facing copy",
            "feature maturity and non-goals",
            "claims about live integrations, autonomy, memory, speed, reliability, and safety",
        ],
        blocks_if=[
            "copy claims a capability that is mock, dry-run, planned, or not verified",
            "limitations are hidden from the target audience",
            "agent permission or external-action capability is overstated",
        ],
        required_evidence=[
            "copy review against implemented behavior",
            "clear distinction between current behavior and future plans",
        ],
        safe_to_accept_when=(
            "The copy is useful, honest, and no stronger than the actual implemented product."
        ),
        example_failure="README says Palari sends Slack messages when only dry-run plans exist.",
    ),
)

PROFILE_BY_ID = {profile.id: profile for profile in GATE_PROFILES}
RISK_RANK = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}
EXTERNAL_ACTION_WORDS = {
    "notify",
    "send",
    "email",
    "comment",
    "create_issue",
    "update_issue",
    "publish",
    "post",
    "webhook",
}
DEPLOY_WORDS = {
    "deploy",
    "deployment",
    "runtime",
    "production",
    "prod",
    "secret",
    "secrets",
    "env",
    "oauth",
    "database",
    "postgres",
    "storage",
    "provider routing",
    "infra/",
    "/var/",
}
MULTIMODAL_WORDS = {
    "image",
    "images",
    "screenshot",
    "screenshots",
    "ocr",
    "vision",
    "photo",
    "audio",
    "video",
    "multimodal",
    "upload",
    "uploaded_file",
}
PRODUCT_COPY_WORDS = {
    "readme",
    "marketing",
    "website",
    "landing",
    "public",
    "showcase",
    "copy",
    "claim",
    "claims",
    "onboarding",
    "user-facing",
}
PROMPT_WORDS = {
    "prompt",
    "system prompt",
    "developer prompt",
    "instruction",
    "instructions",
    "model",
    "assistant",
    "ocr",
    "vision",
    "image",
    "untrusted",
}


def gate_profile_catalog(workspace: Workspace) -> dict[str, Any]:
    return {
        "schema_version": "palari.gate_profiles.v1",
        "workspace": workspace.name,
        "would_mutate": False,
        "profiles": [to_plain(profile) for profile in GATE_PROFILES],
    }


def recommend_gates(workspace: Workspace, work_id: str) -> dict[str, Any]:
    work = workspace.work_item(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise WorkspaceError(f"unknown task {work_id}; known tasks: {known}")

    detail_payload = detail(workspace, work_id)
    context = _recommendation_context(workspace, detail_payload)
    recommendations: list[dict[str, Any]] = []

    def add(profile_id: str, reason: str) -> None:
        if profile_id in {item["id"] for item in recommendations}:
            return
        profile = PROFILE_BY_ID[profile_id]
        recommendations.append(
            {
                **to_plain(profile),
                "reason": reason,
                "review_contract": _review_contract(profile),
            }
        )

    if context["source_ids"]:
        add(
            "source-boundary",
            "Task or run record references allowed source IDs: "
            f"{', '.join(context['source_ids'])}.",
        )

    if context["has_external_write_state"]:
        add(
            "external-write",
            "Task has integration plans, outbox items, external-write run record "
            "fields, or external-action targets.",
        )
        add(
            "human-approval",
            "External action plans or queued writes require explicit human approval before use.",
        )

    if work.required_approval_count > 0 or _risk_at_least(work.risk, "R3"):
        add(
            "human-approval",
            (
                f"Task requires {work.required_approval_count} human approval(s)"
                f" and has risk {work.risk}."
            ),
        )

    if _contains_any(context["runtime_text"], DEPLOY_WORDS):
        add(
            "deploy-runtime",
            "Task files or actions mention deployment, runtime, production, "
            "storage, or provider limits.",
        )

    if _contains_any(context["all_text"], MULTIMODAL_WORDS):
        add(
            "privacy-multimodal",
            "Task or sources mention images, uploads, OCR, vision, or other media content.",
        )
        add(
            "prompt-authority",
            "Media-derived or extracted text must stay untrusted source "
            "material, not privileged prompt text.",
        )
    elif _contains_any(context["all_text"], PROMPT_WORDS):
        add(
            "prompt-authority",
            "Task mentions prompts, instructions, model behavior, or privileged text.",
        )

    if _contains_any(context["copy_text"], PRODUCT_COPY_WORDS):
        add(
            "product-overclaim",
            "Task appears to touch public, README, marketing, onboarding, or user-facing copy.",
        )

    no_special = len(recommendations) == 0
    return {
        "schema_version": "palari.gate_recommendations.v1",
        "workspace": workspace.name,
        "would_mutate": False,
        "work_item": {
            "id": work.id,
            "title": work.title,
            "risk": work.risk,
            "status": work.status,
            "intensity": work.intensity,
        },
        "no_special_gate_required": no_special,
        "recommended_gates": recommendations,
        "review_contracts": [
            {"gate_id": item["id"], **item["review_contract"]} for item in recommendations
        ],
        "next_action": _next_action(no_special, recommendations),
        "omitted_context": [
            {
                "kind": "workspace_records",
                "reason": (
                    "Review-checklist recommendation v1 inspects only the selected "
                    "task, related sources, external-action status, run record, "
                    "check results, review, and human approval."
                ),
                "counts": {
                    "work_items": len(workspace.work_items),
                    "sources": len(workspace.sources),
                    "integrations": len(workspace.integrations),
                    "integration_plans": len(workspace.integration_plans),
                    "integration_outbox": len(workspace.integration_outbox),
                },
            }
        ],
    }


def _review_contract(profile: GateProfile) -> dict[str, Any]:
    return {
        "reviewer_role": profile.reviewer_role,
        "inspect": profile.inspect,
        "blocker_checklist": profile.blocks_if,
        "required_evidence": profile.required_evidence,
        "accept_ready_standard": profile.safe_to_accept_when,
    }


def _recommendation_context(workspace: Workspace, payload: dict[str, Any]) -> dict[str, Any]:
    work = payload["work_item"]
    sources = payload.get("sources", [])
    receipt = payload.get("receipt") or {}
    plans = payload.get("integration_plans", [])
    outbox = payload.get("integration_outbox", [])
    source_ids = sorted(
        set(work.get("allowed_sources", []))
        | set(receipt.get("sources_used", []))
        | {source.get("id", "") for source in sources if source.get("id")}
    )
    all_text = _joined_text(
        work.get("title", ""),
        work.get("scope", ""),
        work.get("allowed_resources", []),
        work.get("allowed_sources", []),
        work.get("allowed_actions", []),
        work.get("output_targets", []),
        work.get("acceptance_target", ""),
        work.get("verification_expectations", []),
        [source.get("label", "") for source in sources],
        [source.get("kind", "") for source in sources],
        [source.get("provider", "") for source in sources],
        [source.get("uri", "") for source in sources],
    )
    runtime_text = _joined_text(
        work.get("title", ""),
        work.get("scope", ""),
        work.get("allowed_resources", []),
        work.get("allowed_actions", []),
        work.get("output_targets", []),
        work.get("verification_expectations", []),
    )
    copy_text = _joined_text(
        work.get("title", ""),
        work.get("scope", ""),
        work.get("allowed_resources", []),
        work.get("output_targets", []),
        work.get("acceptance_target", ""),
    )
    has_external_write_state = bool(plans or outbox)
    has_external_write_state = has_external_write_state or bool(
        receipt.get("external_writes")
        or receipt.get("planned_external_writes")
        or receipt.get("queued_external_writes")
    )
    has_external_write_state = has_external_write_state or _contains_any(
        _joined_text(work.get("allowed_actions", []), work.get("output_targets", [])),
        EXTERNAL_ACTION_WORDS,
    )
    for plan in plans:
        integration = workspace.integration(plan.get("integration_id", ""))
        all_text += " " + _joined_text(
            plan.get("event", ""),
            plan.get("action", ""),
            plan.get("payload_preview", {}),
            integration.provider if integration else "",
        )
    return {
        "source_ids": source_ids,
        "all_text": all_text,
        "runtime_text": runtime_text,
        "copy_text": copy_text,
        "has_external_write_state": has_external_write_state,
    }


def _next_action(no_special: bool, recommendations: list[dict[str, Any]]) -> str:
    if no_special:
        return (
            "No special review checklist is needed; use the normal run record, "
            "checks, and review path."
        )
    labels = ", ".join(item["label"] for item in recommendations)
    return f"Use these review checklists before approving the task: {labels}."


def _risk_at_least(actual: str, minimum: str) -> bool:
    return RISK_RANK.get(actual, 0) >= RISK_RANK.get(minimum, 0)


def _contains_any(text: str, words: set[str]) -> bool:
    lowered = text.lower()
    for word in words:
        if any(not char.isalnum() for char in word):
            if word in lowered:
                return True
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
            return True
    return False


def _joined_text(*values: Any) -> str:
    parts: list[str] = []

    def add(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, str):
            parts.append(value)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                add(key)
                add(item)
            return
        if isinstance(value, (list, tuple, set)):
            for item in value:
                add(item)
            return
        parts.append(str(value))

    for value in values:
        add(value)
    return " ".join(parts).lower()

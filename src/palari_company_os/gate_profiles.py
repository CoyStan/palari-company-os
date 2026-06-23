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
        label="Prompt Authority",
        summary="Checks that untrusted content cannot become system, developer, or authority text.",
        applies_when=[
            "Work uses model prompts, OCR, image text, user-provided instructions, or source text as context.",
            "The result could change agent behavior, memory, tools, safety wording, or instructions.",
        ],
        reviewer_role="Prompt-authority reviewer",
        inspect=[
            "prompt construction and role placement",
            "untrusted source or image text handling",
            "tests with malicious instructions",
        ],
        blocks_if=[
            "untrusted content enters system/developer prompt content",
            "source text can override Palari authority, allowed actions, or stop conditions",
            "malicious text is not covered by regression tests",
        ],
        required_evidence=[
            "test or trace proving untrusted content stays in user/evidence context",
            "review of prompt-building code or packet fields",
        ],
        safe_to_accept_when=(
            "Untrusted text is clearly evidence, cannot grant authority, and has regression coverage."
        ),
        example_failure=(
            "OCR text saying 'ignore previous rules' is inserted into a system prompt."
        ),
    ),
    GateProfile(
        id="source-boundary",
        label="Source Boundary",
        summary="Checks that work uses only selected or allowed sources and reports source limits honestly.",
        applies_when=[
            "Work item declares allowed sources or a receipt claims source use.",
            "A Palari reads selected files, notes, repos, uploads, or external source snapshots.",
        ],
        reviewer_role="Source-boundary reviewer",
        inspect=[
            "allowed_sources and source metadata",
            "receipt sources_used",
            "source access mode, owner, steward, freshness, and redaction fields",
        ],
        blocks_if=[
            "result uses an unallowed, missing, stale, or unselected source",
            "source permissions are broadened silently",
            "receipt overstates what was read or hides source limits",
        ],
        required_evidence=[
            "source ids used by the attempt",
            "receipt or evidence showing no out-of-bound source access",
        ],
        safe_to_accept_when=(
            "Every source used is declared, allowed for the Palari, and honestly reflected in the receipt."
        ),
        example_failure="A result cites a file that was not in allowed_sources.",
    ),
    GateProfile(
        id="external-write",
        label="External Write",
        summary="Checks that outside-company writes remain planned, approved, queued, or explicitly absent.",
        applies_when=[
            "Work has integration plans, outbox items, external write claims, or external action targets.",
            "Allowed actions include notify, send, comment, create_issue, update_issue, or publish.",
        ],
        reviewer_role="External-write reviewer",
        inspect=[
            "integration plans and outbox items",
            "receipt planned_external_writes, queued_external_writes, and external_writes",
            "allowed actions and output targets",
        ],
        blocks_if=[
            "live provider call is implied or performed by a dry-run plan",
            "external write lacks approved integration plan or queued outbox state",
            "receipt claims actual external write when only a dry-run/queued action exists",
        ],
        required_evidence=[
            "dry-run payload preview or outbox record",
            "receipt distinguishing planned, queued, and actual writes",
        ],
        safe_to_accept_when=(
            "External action state is explicit and no live side effect is claimed without authority."
        ),
        example_failure="A Slack notification is described as sent when only a dry-run payload exists.",
    ),
    GateProfile(
        id="human-approval",
        label="Human Approval",
        summary="Checks that human authority, quorum, and approval capability are not bypassed.",
        applies_when=[
            "Work requires approval count, approval capability, high-risk decision, or integration approval.",
            "A result is waiting on review, decision, merge, deploy, policy, or product acceptance.",
        ],
        reviewer_role="Human-authority reviewer",
        inspect=[
            "required_approval_count and required_approval_capability",
            "review verdicts and human decision records",
            "human profile authority and availability",
        ],
        blocks_if=[
            "agent records or implies human approval",
            "approval quorum is unmet or counted from an unqualified human",
            "review recommendation is treated as founder acceptance",
        ],
        required_evidence=[
            "review result when required",
            "human decision record or explicit pending-human state",
        ],
        safe_to_accept_when=(
            "The required human authority is either recorded by a qualified human or still visibly pending."
        ),
        example_failure="An accept-ready review is treated as accepted without a human decision.",
    ),
    GateProfile(
        id="deploy-runtime",
        label="Deploy / Runtime",
        summary="Checks production, runtime data, secrets, storage, provider, and deploy boundaries.",
        applies_when=[
            "Work touches deploy, runtime state, production, storage, provider routing, OAuth, or secrets.",
            "Work can affect live beta, public routes, databases, or environment configuration.",
        ],
        reviewer_role="Deploy/runtime reviewer",
        inspect=[
            "changed runtime/deploy/storage/provider paths",
            "secret and env-file boundaries",
            "live smoke, rollback, and backup evidence when deployment is in scope",
        ],
        blocks_if=[
            "secrets, runtime data, or production state changed without explicit scope",
            "deploy or provider routing changed without backup/smoke evidence",
            "tests pass locally but live/runtime boundary remains unverified",
        ],
        required_evidence=[
            "scope proof for runtime/deploy files",
            "backup/smoke notes when deployment is explicitly in scope",
        ],
        safe_to_accept_when=(
            "Runtime-impacting changes are explicit, verified, reversible, and do not expose secrets."
        ),
        example_failure="A beta deploy modifies runtime data or provider routing without approval.",
    ),
    GateProfile(
        id="privacy-multimodal",
        label="Privacy / Multimodal",
        summary="Checks images, uploads, OCR, screenshots, and other rich media for privacy boundaries.",
        applies_when=[
            "Work reads images, screenshots, OCR, audio, video, uploads, or multimodal model output.",
            "A source or receipt may contain private visual or file-derived content.",
        ],
        reviewer_role="Multimodal/privacy reviewer",
        inspect=[
            "raw media storage behavior",
            "extracted text and metadata handling",
            "logs, receipts, source records, and persistence boundaries",
        ],
        blocks_if=[
            "raw media is persisted when the contract says read-once",
            "private extracted content is logged unnecessarily",
            "multimodal data is treated as trusted instructions",
        ],
        required_evidence=[
            "test proving invalid/oversized media fails closed when relevant",
            "proof raw media is not persisted beyond the declared boundary",
        ],
        safe_to_accept_when=(
            "Media-derived content is minimized, bounded, and treated as untrusted evidence."
        ),
        example_failure="An uploaded screenshot is saved to workspace history without user intent.",
    ),
    GateProfile(
        id="product-overclaim",
        label="Product Overclaim",
        summary="Checks public or product-facing copy for claims that exceed implemented behavior.",
        applies_when=[
            "Work changes README, website, marketing, onboarding, public docs, or user-facing claims.",
            "Copy describes AI capability, integrations, autonomy, memory, safety, or beta maturity.",
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
            "AI authority or external action capability is overstated",
        ],
        required_evidence=[
            "copy review against implemented behavior",
            "clear distinction between current behavior and roadmap/future work",
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
    "docs/showcase",
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
        raise WorkspaceError(f"unknown work item {work_id}; known work items: {known}")

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
            f"Work references allowed or receipt source ids: {', '.join(context['source_ids'])}.",
        )

    if context["has_external_write_state"]:
        add(
            "external-write",
            "Work has integration plans, outbox items, external-write receipt fields, or external action targets.",
        )
        add(
            "human-approval",
            "External action plans or queued writes require explicit human authority before trust.",
        )

    if work.required_approval_count > 0 or _risk_at_least(work.risk, "R3"):
        add(
            "human-approval",
            (
                f"Work requires {work.required_approval_count} human approval(s)"
                f" and has risk {work.risk}."
            ),
        )

    if _contains_any(context["runtime_text"], DEPLOY_WORDS):
        add(
            "deploy-runtime",
            "Work scope or resources mention deploy/runtime/production/storage/provider boundaries.",
        )

    if _contains_any(context["all_text"], MULTIMODAL_WORDS):
        add(
            "privacy-multimodal",
            "Work or sources mention image, upload, OCR, vision, or other multimodal content.",
        )
        add(
            "prompt-authority",
            "Multimodal or extracted text must stay untrusted evidence, not authority-bearing prompt text.",
        )
    elif _contains_any(context["all_text"], PROMPT_WORDS):
        add(
            "prompt-authority",
            "Work mentions prompts, instructions, model behavior, or authority-bearing text.",
        )

    if _contains_any(context["copy_text"], PRODUCT_COPY_WORDS):
        add(
            "product-overclaim",
            "Work appears to touch public, README, marketing, onboarding, or user-facing copy.",
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
                    "Gate recommendation v1 inspects the selected work item, related sources, "
                    "integration state, receipt, evidence, review, and human decision state only."
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
        return "No special gate required; use the normal receipt/evidence/review flow."
    labels = ", ".join(item["label"] for item in recommendations)
    return f"Use these review contracts before trusting the work: {labels}."


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

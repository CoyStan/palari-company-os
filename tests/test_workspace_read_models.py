from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.evidence_manifest import (
    OUTPUT_BINDING_VERSION,
    evidence_manifest_hash,
    stamp_receipt_record,
)
from palari_company_os.errors import WorkspaceError
from palari_company_os.governance_binding import (
    BINDING_VERSION,
    attempt_state_hash,
    review_proof_hash,
    work_contract_hash,
)
from palari_company_os.governance_journal import JournalVerificationContext
from palari_company_os.pcaw_workspace import (
    governance_case_from_workspace,
    recorded_governance_projection,
)
from palari_company_os.read_models import (
    active_parallel_work,
    coordination_warnings,
    detail,
    queue_items,
)
from palari_company_os.workspace import Workspace
from palari_company_os.workspace_read_models import approval_detail, approval_inbox


def _work_record(work_id: str = "WORK-1", **overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": work_id,
        "title": f"Bounded work {work_id}",
        "goal": "GOAL-1",
        "palari": "PALARI-1",
        "workbench_id": "WORKBENCH-1",
        "risk": "R1",
        "intensity": "light",
        "status": "active",
        "scope": "Create one local summary inside the declared boundary.",
        "allowed_resources": ["notes/output.md"],
        "allowed_sources": ["SOURCE-1"],
        "allowed_actions": ["local_write"],
        "output_targets": ["notes/output.md"],
        "path_intents": [{"path": "notes/output.md", "intent": "modify"}],
        "forbidden_actions": ["external_write"],
        "acceptance_target": "The local summary is inspectable.",
        "required_approval_count": 0,
        "required_approval_capability": "",
    }
    record.update(overrides)
    return record


def _base_workspace_raw() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "name": "Read Model Contract",
        "goals": [
            {
                "id": "GOAL-1",
                "title": "Keep bounded work understandable",
                "status": "active",
            }
        ],
        "humans": [
            {
                "id": "HUMAN-1",
                "name": "Product Owner",
                "approval_capabilities": ["product"],
            },
            {
                "id": "HUMAN-REVIEWER",
                "name": "Independent Reviewer",
                "approval_capabilities": ["product"],
            },
        ],
        "palaris": [
            {
                "id": "PALARI-1",
                "name": "Sofia",
                "role": "Bounded worker",
                "owner_human": "HUMAN-1",
                "linked_goals": ["GOAL-1"],
            }
        ],
        "sources": [
            {
                "id": "SOURCE-1",
                "label": "Selected local note",
                "kind": "note",
                "provider": "local_note",
                "uri": "notes/source.md",
                "access_mode": "read",
                "selected": True,
                "owner_human": "HUMAN-1",
                "allowed_palaris": ["PALARI-1"],
                "data_class": "internal",
                "authority": "company_owned",
                "steward_human": "HUMAN-1",
                "freshness_sla": "weekly",
                "redaction_required": False,
            }
        ],
        "workbenches": [
            {
                "id": "WORKBENCH-1",
                "label": "Local Product Work",
                "goal_ids": ["GOAL-1"],
                "palari_ids": ["PALARI-1"],
                "human_ids": ["HUMAN-1", "HUMAN-REVIEWER"],
                "source_ids": ["SOURCE-1"],
                "output_target_ids": ["notes/output.md"],
                "status": "active",
            }
        ],
        "work_items": [_work_record()],
        "attempts": [],
        "evidence_runs": [],
        "review_verdicts": [],
        "human_decisions": [],
        "acceptance_records": [],
        "receipts": [],
        "decisions": [],
        "outcomes": [],
    }


def _workspace(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> Workspace:
    raw = _base_workspace_raw()
    if mutate is not None:
        mutate(raw)
    return Workspace.from_raw(raw, Path("/tmp/palari-read-model-contract"))


def _work(raw: dict[str, Any], work_id: str = "WORK-1") -> dict[str, Any]:
    return next(item for item in raw["work_items"] if item["id"] == work_id)


def _add_attempt(
    raw: dict[str, Any],
    work_id: str = "WORK-1",
    *,
    attempt_id: str | None = None,
    status: str = "complete",
    head: str = "head-1",
) -> dict[str, Any]:
    attempt_id = attempt_id or f"ATTEMPT-{work_id}"
    attempt = {
        "id": attempt_id,
        "work_item_id": work_id,
        "actor": "PALARI-1",
        "status": status,
        "head_sha": head,
        "commits": [head],
        "changed_files": ["notes/output.md"],
        "output_targets": ["notes/output.md"],
        "cleanliness": "clean" if status in {"complete", "completed"} else "",
        "started_at": "2026-07-18T10:00:00Z",
        "updated_at": "2026-07-18T10:01:00Z",
    }
    raw["attempts"].append(attempt)
    _work(raw, work_id)["current_attempt"] = attempt_id
    return attempt


def _add_exact_proof(
    raw: dict[str, Any],
    work_id: str = "WORK-1",
    *,
    evidence_head: str = "head-1",
) -> None:
    work = _work(raw, work_id)
    if work.get("current_attempt"):
        attempt = next(
            item for item in raw["attempts"] if item["id"] == work["current_attempt"]
        )
    else:
        attempt = _add_attempt(raw, work_id)

    receipt = stamp_receipt_record(
        {
            "id": f"RECEIPT-{work_id}",
            "work_item_id": work_id,
            "attempt_id": attempt["id"],
            "actor": "PALARI-1",
            "sources_used": ["SOURCE-1"],
            "actions_taken": ["created the bounded local summary"],
            "outputs_created": ["notes/output.md"],
            "external_writes": [],
            "not_done": ["No external writes."],
            "undo_refs": ["restore notes/output.md"],
            "timestamp": "2026-07-18T10:02:00Z",
        },
        [],
    )
    raw["receipts"].append(receipt)
    evidence = {
        "id": f"EVIDENCE-{work_id}",
        "work_item_id": work_id,
        "attempt_id": attempt["id"],
        "head_sha": evidence_head,
        "status": "passed",
        "commands": ["python3 -m unittest tests.test_governance_kernel"],
        "artifacts": ["notes/output.md"],
        "artifact_hashes": [
            {
                "path": "notes/output.md",
                "sha256": "sha256:" + ("a" * 64),
                "status": "present",
            }
        ],
        "output_binding_version": OUTPUT_BINDING_VERSION,
        "receipt_hash": receipt["receipt_hash"],
        "summary": "Current exact focused evidence passed.",
        "freshness": "exact-head",
        "timestamp": "2026-07-18T10:03:00Z",
    }
    evidence["manifest_hash"] = evidence_manifest_hash(evidence)
    raw["evidence_runs"].append(evidence)


def _add_exact_acceptance(raw: dict[str, Any]) -> None:
    work = _work(raw)
    work.update(
        {
            "risk": "R2",
            "intensity": "standard",
            "status": "in-review",
            "required_approval_count": 1,
            "required_approval_capability": "product",
        }
    )
    _add_exact_proof(raw)
    workspace = Workspace.from_raw(raw, Path("/tmp/palari-read-model-contract"))
    attempt = workspace.attempts[0]
    evidence = workspace.evidence_runs[0]
    receipt = workspace.receipts[0]
    review = {
        "id": "REVIEW-1",
        "work_item_id": work["id"],
        "reviewed_head": evidence.head_sha,
        "reviewer": "HUMAN-REVIEWER",
        "verdict": "accept-ready",
        "findings": [],
        "checks_inspected": list(evidence.commands),
        "residual_risks": [],
        "timestamp": "2026-07-18T10:04:00Z",
        "binding_version": BINDING_VERSION,
        "attempt_id": attempt.id,
        "attempt_hash": attempt_state_hash(attempt),
        "evidence_reference": evidence.id,
        "evidence_manifest_hash": evidence.manifest_hash,
        "receipt_reference": receipt.id,
        "receipt_hash": receipt.receipt_hash,
        "work_contract_hash": work_contract_hash(workspace.work_items[0]),
    }
    review["proof_hash"] = review_proof_hash(review)
    raw["review_verdicts"] = [review]
    raw["human_decisions"] = [
        {
            "id": "HUMAN-DECISION-1",
            "work_item_id": work["id"],
            "human_id": "HUMAN-1",
            "reviewed_head": evidence.head_sha,
            "decision": "accepted",
            "status": "accepted",
            "acceptance_mode": "human",
            "quorum_status": "met",
            "evidence_reference": evidence.id,
            "review_reference": review["id"],
            "timestamp": "2026-07-18T10:05:00Z",
        }
    ]
    raw["acceptance_records"] = [
        {
            "id": "ACCEPTANCE-1",
            "work_item_id": work["id"],
            "human_id": "HUMAN-1",
            "reviewed_head": evidence.head_sha,
            "status": "accepted",
            "decision_id": "HUMAN-DECISION-1",
            "evidence_reference": evidence.id,
            "review_reference": review["id"],
            "receipt_hash": receipt.receipt_hash,
            "quorum_status": "met",
            "accepted_at": "2026-07-18T10:06:00Z",
        }
    ]
    work["status"] = "completed"


class QueueProjectionTests(unittest.TestCase):
    def test_unstarted_bounded_work_is_ready_to_start(self) -> None:
        item = queue_items(_workspace())[0]

        self.assertEqual(item.attention, "ready-for-ai-work")
        self.assertEqual(item.next_step_type, "start-work")
        self.assertTrue(item.ai_safe_to_proceed)
        self.assertEqual(item.goal_title, "Keep bounded work understandable")
        self.assertEqual(item.palari_name, "Sofia")
        self.assertEqual(item.owner, "Product Owner")

    def test_active_attempt_without_evidence_requests_proof_check(self) -> None:
        workspace = _workspace(lambda raw: _add_attempt(raw, status="active"))

        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.next_step_type, "check-active-proof")
        self.assertEqual(item.evidence_state, "missing")
        self.assertTrue(item.ai_safe_to_proceed)
        self.assertEqual(
            item.next_commands[0],
            "palari agent check WORK-1 --as PALARI-1 --mode execute --json",
        )

    def test_current_exact_low_risk_proof_is_ready_for_reconciliation(self) -> None:
        workspace = _workspace(_add_exact_proof)

        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "ready-to-complete")
        self.assertEqual(item.next_step_type, "automatic-reconciliation")
        self.assertEqual(item.evidence_state, "passed")
        self.assertEqual(item.receipt_state, "ready")
        self.assertEqual(item.integration_state, "ready")
        self.assertEqual(item.acceptance_state, "not-required")
        self.assertFalse(item.ai_safe_to_proceed)

    def test_tampered_exact_proof_fails_closed_as_invalid(self) -> None:
        def tamper(raw: dict[str, Any]) -> None:
            _add_exact_proof(raw)
            raw["evidence_runs"][0]["commands"].append("unbound command")

        item = queue_items(_workspace(tamper))[0]

        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.next_step_type, "check-active-proof")
        self.assertEqual(item.evidence_state, "invalid")
        self.assertEqual(item.integration_state, "not-ready")
        self.assertIn("not a current exact proof", item.why)

    def test_proof_for_an_old_head_fails_closed_as_stale(self) -> None:
        workspace = _workspace(
            lambda raw: _add_exact_proof(raw, evidence_head="older-head")
        )

        item = queue_items(workspace)[0]

        self.assertEqual(item.attention, "needs-evidence")
        self.assertEqual(item.evidence_state, "stale")
        self.assertEqual(item.integration_state, "not-ready")
        self.assertIn("stale", item.why)

    def test_review_required_work_projects_one_review_handoff(self) -> None:
        def require_review(raw: dict[str, Any]) -> None:
            _work(raw).update({"risk": "R2", "intensity": "standard"})
            _add_exact_proof(raw)

        item = queue_items(_workspace(require_review))[0]

        self.assertEqual(item.attention, "needs-review")
        self.assertEqual(item.next_step_type, "review-handoff")
        self.assertEqual(item.review_state, "missing")
        self.assertFalse(item.ai_safe_to_proceed)
        self.assertEqual(
            item.agent_handoff_command,
            "palari agent handoff WORK-1 --as PALARI-1 --json",
        )

    def test_open_decision_projects_the_human_boundary(self) -> None:
        def add_decision(raw: dict[str, Any]) -> None:
            raw["decisions"].append(
                {
                    "id": "DECISION-1",
                    "question": "Should the objective continue?",
                    "status": "open",
                    "required_human": "HUMAN-1",
                    "linked_goal": "GOAL-1",
                    "linked_work": "WORK-1",
                }
            )

        item = queue_items(_workspace(add_decision))[0]

        self.assertEqual(item.attention, "needs-human-decision")
        self.assertEqual(item.next_step_type, "human-decision")
        self.assertTrue(item.waiting_on_human)
        self.assertFalse(item.ai_safe_to_proceed)
        self.assertEqual(
            item.next_commands[0],
            "palari decision guide DECISION-1 --json",
        )

    def test_changes_requested_projects_a_repair_boundary(self) -> None:
        def request_changes(raw: dict[str, Any]) -> None:
            _work(raw).update({"risk": "R2", "intensity": "standard"})
            _add_exact_proof(raw)
            raw["review_verdicts"].append(
                {
                    "id": "REVIEW-1",
                    "work_item_id": "WORK-1",
                    "reviewed_head": "head-1",
                    "reviewer": "HUMAN-REVIEWER",
                    "verdict": "changes-requested",
                    "findings": [],
                    "checks_inspected": [
                        "python3 -m unittest tests.test_governance_kernel"
                    ],
                    "timestamp": "2026-07-18T10:04:00Z",
                }
            )

        item = queue_items(_workspace(request_changes))[0]

        self.assertEqual(item.attention, "changes-requested")
        self.assertEqual(item.next_step_type, "repair")
        self.assertTrue(item.ai_safe_to_proceed)
        self.assertIn("requested changes", item.why)

    def test_queue_order_is_deterministic_by_attention_then_id(self) -> None:
        def build_states(raw: dict[str, Any]) -> None:
            raw["work_items"].extend(
                [
                    _work_record("WORK-A"),
                    _work_record("WORK-Z"),
                ]
            )
            raw["decisions"].append(
                {
                    "id": "DECISION-A",
                    "question": "Proceed?",
                    "status": "open",
                    "linked_work": "WORK-A",
                }
            )
            _add_attempt(raw, "WORK-Z", status="active")

        items = queue_items(_workspace(build_states))

        self.assertEqual(
            [(item.id, item.attention) for item in items],
            [
                ("WORK-A", "needs-human-decision"),
                ("WORK-Z", "needs-evidence"),
                ("WORK-1", "ready-for-ai-work"),
            ],
        )

    def test_completed_exact_work_projects_closed(self) -> None:
        def complete(raw: dict[str, Any]) -> None:
            _add_exact_proof(raw)
            _work(raw)["status"] = "completed"

        item = queue_items(_workspace(complete))[0]

        self.assertEqual(item.attention, "closed")
        self.assertEqual(item.next_step_type, "closed")
        self.assertEqual(item.integration_state, "closed")
        self.assertFalse(item.ai_safe_to_proceed)


class RecordedBindingNormalizationTests(unittest.TestCase):
    def test_recorded_projection_is_explicitly_non_authoritative(self) -> None:
        workspace = _workspace(_add_exact_acceptance)

        with patch(
            "palari_company_os.governance_binding.verify_evidence",
            side_effect=AssertionError("recorded projection must not inspect files"),
        ):
            projection = recorded_governance_projection(workspace, "WORK-1")

        self.assertEqual(projection.basis, "recorded")
        self.assertFalse(projection.authoritative)
        self.assertEqual(projection.recorded_proof_errors, ())
        self.assertEqual(projection.evaluation.derived_state, "completed")
        self.assertEqual(
            projection.evaluation.qualified_human_ids,
            ("HUMAN-1",),
        )
        self.assertFalse(projection.evaluation.fully_verified)
        self.assertEqual(
            next(
                item.status
                for item in projection.evaluation.properties
                if item.name == "evidence_freshness"
            ),
            "not-checked",
        )

    def test_no_inspection_mode_preserves_only_a_current_recorded_review(self) -> None:
        workspace = _workspace(_add_exact_acceptance)

        with patch(
            "palari_company_os.governance_binding.verify_evidence",
            side_effect=AssertionError("recorded projection must not inspect files"),
        ):
            current, _ = governance_case_from_workspace(
                workspace,
                "WORK-1",
                inspect_external=False,
            )

        self.assertEqual(current.review.contract_digest, current.contract_digest())
        self.assertEqual(current.review.attempt_digest, current.attempt_digest())
        self.assertEqual(current.review.evidence_digest, current.evidence_digest())
        self.assertEqual(current.review.receipt_digest, current.receipt_digest())

        stale_review = replace(
            workspace.review_verdicts[0],
            work_contract_hash="sha256:" + ("b" * 64),
        )
        workspace.review_verdicts[0] = replace(
            stale_review,
            proof_hash=review_proof_hash(stale_review),
        )
        stale, _ = governance_case_from_workspace(
            workspace,
            "WORK-1",
            inspect_external=False,
        )

        self.assertNotEqual(stale.review.contract_digest, stale.contract_digest())
        self.assertEqual(stale.acceptance_records[0].receipt_digest, "")
        self.assertEqual(stale.acceptance_records[0].evidence_digest, "")
        self.assertEqual(stale.acceptance_records[0].review_digest, "")

    def test_no_inspection_mode_does_not_refresh_a_stale_acceptance(self) -> None:
        workspace = _workspace(_add_exact_acceptance)
        workspace.acceptance_records[0] = replace(
            workspace.acceptance_records[0],
            receipt_hash="sha256:" + ("c" * 64),
        )

        case, _ = governance_case_from_workspace(
            workspace,
            "WORK-1",
            inspect_external=False,
        )

        self.assertEqual(case.review.contract_digest, case.contract_digest())
        self.assertEqual(case.acceptance_records[0].receipt_digest, "")
        self.assertEqual(case.acceptance_records[0].evidence_digest, "")
        self.assertEqual(case.acceptance_records[0].review_digest, "")


class DetailAndCoordinationProjectionTests(unittest.TestCase):
    def test_retired_work_is_closed_but_remains_audit_visible(self) -> None:
        def retire(raw: dict[str, Any]) -> None:
            raw["work_items"].append(_work_record("WORK-SUCCESSOR"))
            _work(raw).update(
                {
                    "status": "superseded",
                    "terminal_reason": "A narrower successor owns the objective.",
                    "successor_work_item_id": "WORK-SUCCESSOR",
                }
            )

        workspace = _workspace(retire)
        item = next(item for item in queue_items(workspace) if item.id == "WORK-1")
        payload = detail(workspace, "WORK-1")

        self.assertEqual(item.attention, "closed")
        self.assertEqual(item.terminal_disposition, "superseded")
        self.assertEqual(item.successor_work_item_id, "WORK-SUCCESSOR")
        self.assertIn("successor", item.why.lower())
        self.assertEqual(
            payload["work_item"]["terminal_reason"],
            "A narrower successor owns the objective.",
        )

    def test_detail_assembles_relationships_and_uses_declared_attempt(self) -> None:
        def add_relationships(raw: dict[str, Any]) -> None:
            raw["work_items"].extend(
                [
                    _work_record("WORK-CHILD", parent_work_item_id="WORK-1"),
                    _work_record("WORK-DEPENDENCY"),
                ]
            )
            _work(raw)["dependency_ids"] = ["WORK-DEPENDENCY"]
            _add_attempt(
                raw,
                attempt_id="ATTEMPT-CURRENT",
                status="active",
                head="current-head",
            )
            later = {
                **raw["attempts"][0],
                "id": "ATTEMPT-LATER",
                "head_sha": "later-head",
                "commits": ["later-head"],
                "updated_at": "2026-07-18T11:00:00Z",
            }
            raw["attempts"].append(later)

        payload = detail(_workspace(add_relationships), "WORK-1")

        self.assertEqual(payload["goal"]["id"], "GOAL-1")
        self.assertEqual(payload["palari"]["id"], "PALARI-1")
        self.assertEqual(payload["workbench"]["id"], "WORKBENCH-1")
        self.assertEqual(payload["sources"][0]["id"], "SOURCE-1")
        self.assertEqual(payload["child_work_items"][0]["id"], "WORK-CHILD")
        self.assertEqual(payload["dependencies"][0]["id"], "WORK-DEPENDENCY")
        self.assertEqual(payload["attempt"]["id"], "ATTEMPT-CURRENT")
        self.assertEqual(
            payload["agent_commands"]["brief"],
            "palari agent brief WORK-1 --as PALARI-1 --mode execute --json",
        )

    def test_unknown_detail_fails_with_known_identifiers(self) -> None:
        with self.assertRaisesRegex(KeyError, "unknown work item WORK-MISSING.*WORK-1"):
            detail(_workspace(), "WORK-MISSING")

    def test_exclusive_target_overlap_projects_one_coordination_blocker(self) -> None:
        def add_conflict(raw: dict[str, Any]) -> None:
            _work(raw).update(
                {
                    "parallel_policy": "exclusive",
                    "conflict_targets": [" Notes/Output.md "],
                }
            )
            raw["work_items"].append(
                _work_record(
                    "WORK-2",
                    parallel_policy="exclusive",
                    conflict_targets=["notes/output.md"],
                )
            )
            _add_attempt(raw, "WORK-1", status="active")
            _add_attempt(raw, "WORK-2", status="active")

        workspace = _workspace(add_conflict)
        queue = {item.id: item for item in queue_items(workspace)}
        warnings = coordination_warnings(workspace)

        self.assertEqual([item["work_item_id"] for item in active_parallel_work(workspace)], ["WORK-1", "WORK-2"])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["targets"], ["notes/output.md"])
        self.assertEqual(queue["WORK-1"].attention, "blocked")
        self.assertEqual(queue["WORK-2"].scope_overlap_state, "blocked")


class ApprovalProjectionTests(unittest.TestCase):
    def test_approval_inbox_forwards_selection_and_request_context(self) -> None:
        workspace = _workspace()
        context = JournalVerificationContext()
        expected = {"schema_version": "test.approval-inbox"}

        with (
            patch(
                "palari_company_os.workspace_read_models.load_store",
                return_value=SimpleNamespace(data={}),
            ),
            patch(
                "palari_company_os.workspace_read_models.build_approval_inbox",
                return_value=expected,
            ) as build,
        ):
            result = approval_inbox(
                workspace,
                selected_work_ids=("WORK-1",),
                journal_context=context,
            )

        self.assertIs(result, expected)
        self.assertEqual(build.call_args.kwargs["selected_work_ids"], ("WORK-1",))
        self.assertIs(build.call_args.kwargs["journal_context"], context)

    def test_default_approval_inbox_excludes_retired_work(self) -> None:
        def add_retired(raw: dict[str, Any]) -> None:
            raw["work_items"].append(
                _work_record(
                    "WORK-OLD",
                    status="abandoned",
                    terminal_reason="The objective no longer earns attention.",
                )
            )

        workspace = _workspace(add_retired)

        with (
            patch(
                "palari_company_os.workspace_read_models.load_store",
                return_value=SimpleNamespace(data={}),
            ),
            patch(
                "palari_company_os.workspace_read_models.build_approval_inbox",
                return_value={"schema_version": "test.approval-inbox"},
            ) as build,
        ):
            approval_inbox(workspace)

        self.assertEqual(build.call_args.kwargs["selected_work_ids"], ("WORK-1",))

    def test_explicit_retired_approval_selection_fails_closed(self) -> None:
        def retire(raw: dict[str, Any]) -> None:
            _work(raw).update(
                {
                    "status": "superseded",
                    "terminal_reason": "A replacement owns the objective.",
                }
            )

        with self.assertRaisesRegex(WorkspaceError, "retired work is audit-only"):
            approval_inbox(_workspace(retire), selected_work_ids=("WORK-1",))

    def test_all_retired_inbox_cannot_expose_an_authority_action(self) -> None:
        def retire(raw: dict[str, Any]) -> None:
            _work(raw).update(
                {
                    "status": "abandoned",
                    "terminal_reason": "No active objective remains.",
                }
            )

        built = {
            "individual_items": [{"id": "WORK-1"}],
            "packs": [{"pack_id": "PACK-UNSAFE"}],
            "approval_commands": [{"command": "must disappear"}],
            "counts": {
                "items": 1,
                "packs": 1,
                "eligible": 1,
                "blocked": 0,
                "stale": 0,
                "non_batchable": 0,
            },
            "primary_action": {
                "available": True,
                "count": 1,
                "commands": ["must disappear"],
            },
        }

        with (
            patch(
                "palari_company_os.workspace_read_models.load_store",
                return_value=SimpleNamespace(data={}),
            ),
            patch(
                "palari_company_os.workspace_read_models.build_approval_inbox",
                return_value=built,
            ),
        ):
            result = approval_inbox(_workspace(retire))

        self.assertEqual(result["individual_items"], [])
        self.assertEqual(result["packs"], [])
        self.assertEqual(result["approval_commands"], [])
        self.assertEqual(result["counts"]["items"], 0)
        self.assertFalse(result["primary_action"]["available"])
        self.assertEqual(result["primary_action"]["commands"], [])

    def test_approval_detail_translates_inbox_failure_without_authority(self) -> None:
        with patch(
            "palari_company_os.workspace_read_models.approval_inbox",
            side_effect=WorkspaceError("journal continuity is unavailable"),
        ):
            result = approval_detail(_workspace(), "WORK-1")

        self.assertFalse(result["available"])
        self.assertEqual(result["work_item_id"], "WORK-1")
        self.assertIn("journal continuity", result["reason"])
        self.assertIn("Repair or checkpoint", result["next_safe_action"])


class CliTranslationTests(unittest.TestCase):
    def test_state_json_translates_one_isolated_current_workspace(self) -> None:
        raw = _base_workspace_raw()
        raw["work_items"].extend(
            [
                _work_record("WORK-PROOF"),
                _work_record(
                    "WORK-OLD",
                    status="abandoned",
                    terminal_reason="The old objective was retired.",
                ),
            ]
        )
        _add_attempt(raw, "WORK-PROOF", status="active")

        with tempfile.TemporaryDirectory() as directory:
            workspace_path = Path(directory)
            (workspace_path / "workspace.json").write_text(
                json.dumps(raw),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT / "src")
            result = subprocess.run(
                [
                    sys.executable,
                    "-S",
                    "-m",
                    "palari_company_os",
                    "--workspace",
                    str(workspace_path),
                    "state",
                    "--json",
                ],
                cwd=REPO_ROOT,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["workspace"], "Read Model Contract")
        self.assertEqual(
            payload["attention"],
            {
                "needs-evidence": 1,
                "ready-for-ai-work": 1,
                "closed": 1,
            },
        )
        self.assertEqual(payload["top_attention"]["id"], "WORK-PROOF")
        self.assertEqual(payload["top_attention"]["next_step_type"], "check-active-proof")
        self.assertEqual(
            {item["id"] for item in payload["queue"]},
            {"WORK-1", "WORK-PROOF", "WORK-OLD"},
        )
        self.assertEqual(payload["active_parallel_work"][0]["work_item_id"], "WORK-PROOF")
        self.assertEqual(payload["coordination_warnings"], [])


if __name__ == "__main__":
    unittest.main()

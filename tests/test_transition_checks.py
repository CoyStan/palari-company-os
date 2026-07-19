from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.authoring import update_record
from palari_company_os.evidence_manifest import (
    stamp_evidence_record,
    stamp_receipt_record,
    verify_evidence,
)
from palari_company_os.governance_binding import (
    current_review_binding,
    review_proof_hash,
)
from palari_company_os.store import WorkspaceStore, load_store, write_store
from palari_company_os.transition_checks import check_transition
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.workspace_fixture import current_recommendation_data


class TransitionCheckTests(unittest.TestCase):
    def test_low_risk_completion_translates_exact_kernel_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            without_evidence = _workspace(_current_data(), root)
            blocked = check_transition(without_evidence, "work_complete", "WORK-1")

            raw = _current_data()
            _add_exact_evidence(raw, root)
            ready = check_transition(_workspace(raw, root), "work_complete", "WORK-1")

        self.assertIn(
            "GOVERNANCE_PROOF_INCOMPLETE",
            {blocker.code for blocker in blocked.blockers},
        )
        self.assertTrue(ready.ok, ready.to_dict())

    def test_completion_accepts_exact_local_deletion_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Palari Test"],
                check=True,
            )
            output = root / "notes/summary.md"
            output.parent.mkdir(parents=True)
            output.write_text("Obsolete summary.\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "notes/summary.md"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "add obsolete output"],
                check=True,
            )
            base_sha = _git_head(root)
            output.unlink()
            subprocess.run(["git", "-C", str(root), "add", "notes/summary.md"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "delete bounded output"],
                check=True,
            )
            head_sha = _git_head(root)

            raw = _current_data()
            path_intents = [{"path": "notes/summary.md", "intent": "delete"}]
            raw["work_items"][0]["path_intents"] = path_intents
            raw["attempts"][0].update(
                {
                    "base_sha": base_sha,
                    "head_sha": head_sha,
                    "commits": [head_sha],
                    "workspace_path": str(root),
                    "allowed_paths": ["notes/summary.md"],
                }
            )
            raw["evidence_runs"] = [
                stamp_evidence_record(
                    _evidence_record(raw, head_sha=head_sha, base_ref=base_sha),
                    root,
                    attempts=raw["attempts"],
                    path_intents=path_intents,
                )
            ]

            result = check_transition(_workspace(raw, root), "work_complete", "WORK-1")

        self.assertEqual(
            raw["evidence_runs"][0]["artifact_hashes"],
            [
                {
                    "path": "notes/summary.md",
                    "sha256": "sha256:absent",
                    "status": "absent",
                }
            ],
        )
        self.assertTrue(result.ok, result.to_dict())

    def test_completion_projects_bound_terminal_authority_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = _review_required_data()
            _add_exact_evidence(raw, root)
            review = _add_bound_review(raw, root)
            raw["human_decisions"] = [
                {
                    "id": "DECISION-1",
                    "work_item_id": "WORK-1",
                    "human_id": "HUMAN-OWNER",
                    "reviewed_head": "head-1",
                    "decision": "accepted",
                    "status": "accepted",
                    "acceptance_mode": "human",
                    "quorum_status": "met",
                    "evidence_reference": "EVIDENCE-1",
                    "review_reference": review["id"],
                    "timestamp": "2026-07-18T00:03:00Z",
                }
            ]
            raw["acceptance_records"] = [
                {
                    "id": "ACCEPTANCE-1",
                    "work_item_id": "WORK-1",
                    "human_id": "HUMAN-OWNER",
                    "reviewed_head": "head-1",
                    "status": "accepted",
                    "decision_id": "DECISION-1",
                    "evidence_reference": "EVIDENCE-1",
                    "review_reference": review["id"],
                    "receipt_hash": raw["receipts"][0]["receipt_hash"],
                    "authority_profile": "team-safe",
                    "quorum_status": "met",
                    "reason": "Exact independently reviewed proof accepted.",
                    "accepted_at": "2026-07-18T00:04:00Z",
                }
            ]

            result = check_transition(_workspace(raw, root), "work_complete", "WORK-1")

        self.assertTrue(result.ok, result.to_dict())

    def test_work_accept_enforces_current_human_capability_and_availability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = _review_required_data()
            _add_exact_evidence(raw, root)
            _add_bound_review(raw, root)
            workspace = _workspace(raw, root)

            qualified = check_transition(
                workspace,
                "work_accept",
                "WORK-1",
                actor="HUMAN-OWNER",
                context={"reviewed_head": "head-1"},
            )
            unqualified = check_transition(
                workspace,
                "work_accept",
                "WORK-1",
                actor="HUMAN-OBSERVER",
                context={"reviewed_head": "head-1"},
            )
            inactive = check_transition(
                workspace,
                "work_accept",
                "WORK-1",
                actor="HUMAN-INACTIVE",
                context={"reviewed_head": "head-1"},
            )

        self.assertTrue(qualified.ok, qualified.to_dict())
        self.assertIn(
            "HUMAN_LACKS_CAPABILITY",
            {blocker.code for blocker in unqualified.blockers},
        )
        self.assertIn("HUMAN_INACTIVE", {blocker.code for blocker in inactive.blockers})

    def test_accept_ready_review_requires_current_exact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = _workspace(_review_required_data(), Path(directory))

            result = _check_review(
                workspace,
                reviewer="HUMAN-OWNER",
                verdict="accept-ready",
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.blockers[0].code, "EXACT_PROOF_NOT_READY")
        self.assertIn("agent doctor", result.blockers[0].next_command)

    def test_review_authority_enforces_identity_independence_and_source_scope(self) -> None:
        raw = _review_required_data()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [
                ("missing identity", "HUMAN-MISSING", raw, "REVIEWER_MISSING"),
                ("inactive human", "HUMAN-INACTIVE", raw, "HUMAN_INACTIVE"),
                ("attempt actor", "PALARI-BUILDER", raw, "REVIEWER_NOT_INDEPENDENT"),
                (
                    "source denied",
                    "PALARI-REVIEWER",
                    _with_source_reviewers(raw, ["PALARI-BUILDER"]),
                    "REVIEWER_SOURCE_NOT_ALLOWED",
                ),
            ]
            for label, reviewer, candidate, expected in cases:
                with self.subTest(label=label):
                    result = _check_review(_workspace(candidate, root), reviewer=reviewer)
                    self.assertIn(expected, {blocker.code for blocker in result.blockers})

            allowed = _check_review(
                _workspace(raw, root),
                reviewer="PALARI-REVIEWER",
            )
        self.assertTrue(allowed.ok, allowed.to_dict())

    def test_evidence_record_rejects_a_head_other_than_its_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = _workspace(_current_data(), Path(directory))

            result = check_transition(
                workspace,
                "evidence_record",
                "EVIDENCE-WRONG-HEAD",
                context={
                    "work_item_id": "WORK-1",
                    "attempt_id": "ATTEMPT-1",
                    "head_sha": "wrong-head",
                },
            )

        self.assertEqual(result.blockers[0].code, "EVIDENCE_STALE_HEAD")

    def test_authoring_trust_updates_cannot_bypass_transition_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "evidence"
            raw = _current_data()
            _add_exact_evidence(raw, root)
            _write_workspace(root, raw)

            with self.assertRaisesRegex(WorkspaceError, "does not match attempt head head-1"):
                update_record(root, "evidence", "EVIDENCE-1", {"head_sha": "wrong-head"})
            self.assertEqual(
                _stored_record(root, "evidence_runs", "EVIDENCE-1")["head_sha"],
                "head-1",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "review"
            raw = _review_required_data()
            raw["review_verdicts"] = [_unbound_review()]
            _write_workspace(root, raw)

            with self.assertRaisesRegex(
                WorkspaceError,
                "accept-ready review requires complete exact proof",
            ):
                update_record(root, "review", "REVIEW-HISTORICAL", {"verdict": "accept-ready"})
            self.assertEqual(
                _stored_record(root, "review_verdicts", "REVIEW-HISTORICAL")["verdict"],
                "changes-requested",
            )

    def test_bound_review_is_immutable_and_later_metadata_edits_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bound"
            raw = _review_required_data()
            _add_exact_evidence(raw, root)
            _add_bound_review(raw, root)
            _write_workspace(root, raw)

            with self.assertRaisesRegex(WorkspaceError, "exact-proof-bound and immutable"):
                update_record(
                    root,
                    "review",
                    "REVIEW-1",
                    {"residual_risks": ["changed after exact review"]},
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bound-evidence"
            raw = _review_required_data()
            _add_exact_evidence(raw, root)
            _add_bound_review(raw, root)
            _write_workspace(root, raw)

            with self.assertRaisesRegex(
                WorkspaceError,
                "evidence manifest changed after review",
            ):
                update_record(
                    root,
                    "evidence",
                    "EVIDENCE-1",
                    {"summary": "Current proof note clarified."},
                )
            evidence = _stored_record(root, "evidence_runs", "EVIDENCE-1")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "historical-metadata"
            raw = _current_data()
            _add_exact_evidence(raw, root)
            raw["review_verdicts"] = [_unbound_review()]
            _write_workspace(root, raw)

            update_record(
                root,
                "evidence",
                "EVIDENCE-1",
                {"summary": "Current proof note clarified."},
            )
            update_record(
                root,
                "review",
                "REVIEW-HISTORICAL",
                {"residual_risks": ["Review must still be rerun."]},
            )

            edited_evidence = _stored_record(root, "evidence_runs", "EVIDENCE-1")
            review = _stored_record(root, "review_verdicts", "REVIEW-HISTORICAL")
            workspace = Workspace.load(root)
            verification = verify_evidence(workspace, "EVIDENCE-1")

        self.assertEqual(evidence["summary"], "Focused exact verification passed.")
        self.assertEqual(edited_evidence["summary"], "Current proof note clarified.")
        self.assertTrue(verification["ok"], verification)
        self.assertEqual(review["residual_risks"], ["Review must still be rerun."])


def _current_data() -> dict[str, Any]:
    raw = current_recommendation_data()
    raw["name"] = "Current transition boundary"
    raw["goals"][0]["title"] = "Prove bounded local work"
    raw["humans"][0].update(
        {
            "id": "HUMAN-OWNER",
            "name": "Product owner",
            "availability": "active",
        }
    )
    raw["humans"].extend(
        [
            {
                "id": "HUMAN-OBSERVER",
                "name": "Observer",
                "approval_capabilities": ["operations"],
                "availability": "active",
            },
            {
                "id": "HUMAN-INACTIVE",
                "name": "Former product owner",
                "approval_capabilities": ["product"],
                "availability": "inactive",
            },
        ]
    )
    raw["palaris"][0].update(
        {
            "id": "PALARI-BUILDER",
            "name": "Builder",
            "role": "Bounded local worker",
            "owner_human": "HUMAN-OWNER",
        }
    )
    raw["palaris"].append(
        {
            "id": "PALARI-REVIEWER",
            "name": "Independent reviewer",
            "role": "Review current exact proof",
            "owner_human": "HUMAN-OWNER",
            "linked_goals": ["GOAL-1"],
        }
    )
    raw["sources"][0].update(
        {
            "owner_human": "HUMAN-OWNER",
            "steward_human": "HUMAN-OWNER",
            "allowed_palaris": ["PALARI-BUILDER", "PALARI-REVIEWER"],
        }
    )
    raw["work_items"][0].update(
        {
            "title": "Create a bounded local summary",
            "palari": "PALARI-BUILDER",
            "risk": "R1",
            "intensity": "light",
            "scope": "Use the selected source to create one local summary.",
            "allowed_actions": ["local_write"],
            "output_targets": ["notes/summary.md"],
            "acceptance_target": "Exact local evidence is current.",
            "verification_expectations": [],
            "current_attempt": "ATTEMPT-1",
            "required_approval_count": 0,
            "required_approval_capability": "",
        }
    )
    receipt = stamp_receipt_record(
        {
            "id": "RECEIPT-1",
            "work_item_id": "WORK-1",
            "attempt_id": "ATTEMPT-1",
            "actor": "PALARI-BUILDER",
            "sources_used": ["SOURCE-1"],
            "actions_taken": ["created bounded local summary"],
            "outputs_created": ["notes/summary.md"],
            "external_writes": [],
            "not_done": ["No external writes."],
            "undo_refs": ["delete notes/summary.md"],
            "timestamp": "2026-07-18T00:01:00Z",
        },
        [],
    )
    raw.update(
        {
            "attempts": [
                {
                    "id": "ATTEMPT-1",
                    "work_item_id": "WORK-1",
                    "actor": "PALARI-BUILDER",
                    "status": "complete",
                    "commits": ["head-1"],
                    "changed_files": ["notes/summary.md"],
                    "cleanliness": "clean",
                    "result": "Bounded local summary created.",
                }
            ],
            "evidence_runs": [],
            "review_verdicts": [],
            "human_decisions": [],
            "acceptance_records": [],
            "receipts": [receipt],
            "decisions": [],
            "outcomes": [],
            "integration_plans": [],
            "integration_outbox": [],
        }
    )
    return raw


def _review_required_data() -> dict[str, Any]:
    raw = _current_data()
    raw["work_items"][0].update(
        {
            "risk": "R2",
            "intensity": "standard",
            "status": "in-review",
            "required_approval_count": 1,
            "required_approval_capability": "product",
        }
    )
    return raw


def _evidence_record(
    raw: dict[str, Any],
    *,
    head_sha: str = "head-1",
    base_ref: str = "",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "EVIDENCE-1",
        "work_item_id": "WORK-1",
        "attempt_id": "ATTEMPT-1",
        "head_sha": head_sha,
        "status": "passed",
        "commands": ["python3 -m unittest tests.test_governance_kernel"],
        "artifacts": ["notes/summary.md"],
        "receipt_hash": raw["receipts"][0]["receipt_hash"],
        "summary": "Focused exact verification passed.",
        "freshness": "exact-head",
        "timestamp": "2026-07-18T00:02:00Z",
    }
    if base_ref:
        record["base_ref"] = base_ref
    return record


def _add_exact_evidence(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    output = root / "notes/summary.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("Current exact summary.\n", encoding="utf-8")
    evidence = stamp_evidence_record(
        _evidence_record(raw),
        root,
        attempts=raw["attempts"],
    )
    raw["evidence_runs"] = [evidence]
    return evidence


def _add_bound_review(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    workspace = _workspace(raw, root)
    binding, errors = current_review_binding(
        workspace,
        "WORK-1",
        require_output_coverage=True,
    )
    if errors:
        raise AssertionError(errors)
    review = {
        "id": "REVIEW-1",
        "work_item_id": "WORK-1",
        "reviewed_head": "head-1",
        "reviewer": "PALARI-REVIEWER",
        "verdict": "accept-ready",
        "timestamp": "2026-07-18T00:02:30Z",
        **binding,
    }
    review["proof_hash"] = review_proof_hash(review)
    raw["review_verdicts"] = [review]
    return review


def _unbound_review() -> dict[str, Any]:
    return {
        "id": "REVIEW-HISTORICAL",
        "work_item_id": "WORK-1",
        "reviewed_head": "head-1",
        "reviewer": "PALARI-REVIEWER",
        "verdict": "changes-requested",
        "findings": [],
        "residual_risks": ["Current exact review is still required."],
        "timestamp": "2026-07-17T00:00:00Z",
    }


def _check_review(
    workspace: Workspace,
    *,
    reviewer: str,
    verdict: str = "changes-requested",
) -> Any:
    return check_transition(
        workspace,
        "review_record",
        "REVIEW-NEW",
        actor=reviewer,
        context={
            "work_item_id": "WORK-1",
            "reviewed_head": "head-1",
            "verdict": verdict,
        },
    )


def _with_source_reviewers(raw: dict[str, Any], reviewers: list[str]) -> dict[str, Any]:
    candidate = deepcopy(raw)
    candidate["sources"][0]["allowed_palaris"] = reviewers
    return candidate


def _workspace(raw: dict[str, Any], root: Path) -> Workspace:
    return Workspace.from_raw(deepcopy(raw), root)


def _write_workspace(root: Path, raw: dict[str, Any]) -> None:
    write_store(WorkspaceStore(data_path=root / "workspace.json", data=deepcopy(raw)))


def _stored_record(root: Path, collection: str, record_id: str) -> dict[str, Any]:
    records = load_store(root).data[collection]
    return next(record for record in records if record["id"] == record_id)


def _git_head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
    ).strip()


if __name__ == "__main__":
    unittest.main()

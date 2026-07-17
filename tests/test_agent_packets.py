from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_checks import build_agent_check
from palari_company_os.agent_done import agent_done
from palari_company_os.agent_doctor import build_agent_doctor
from palari_company_os.agent_finish import build_agent_finish
from palari_company_os.agent_handoff import build_agent_handoff
from palari_company_os.agent_isolation import (
    git_integration_readiness,
    isolation_branch,
    start_isolated_agent,
)
from palari_company_os.agent_loop import build_agent_loop
from palari_company_os.agent_next import build_agent_next, build_agent_next_all
from palari_company_os import governance_journal
from palari_company_os.agent_packets import _context_hash, build_agent_brief
from palari_company_os.agent_runtime import release_agent, start_agent
from palari_company_os.evidence_manifest import evidence_manifest_hash
from palari_company_os.governance_binding import current_review_binding, review_proof_hash
from palari_company_os.onramp import quick_add_work
from palari_company_os.read_models import detail, queue_items
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
DOGFOOD = REPO_ROOT / "workspaces" / "palari-company-os"


def _remove_work_0001_exact_proof(data: dict[str, object]) -> None:
    data["receipts"] = [
        item for item in data["receipts"] if item.get("work_item_id") != "WORK-0001"
    ]
    data["review_verdicts"] = [
        item for item in data["review_verdicts"] if item.get("work_item_id") != "WORK-0001"
    ]
    evidence = next(
        item for item in data["evidence_runs"] if item.get("work_item_id") == "WORK-0001"
    )
    for field in ("artifact_hashes", "manifest_hash", "receipt_hash"):
        evidence.pop(field, None)


def _authorize_alfred_for_beta_sources(data: dict[str, object]) -> None:
    for source in data["sources"]:
        if source["id"] in {"SOURCE-0001", "SOURCE-0002"}:
            source["allowed_palaris"].append("PALARI-ALFRED")


def _link_decided_decision_to_work_0001(data: dict[str, object]) -> None:
    decision = next(item for item in data["decisions"] if item.get("id") == "DECISION-0001")
    decision["linked_work"] = "WORK-0001"
    decision["status"] = "decided"
    decision["result"] = "No inbox use during beta"


def _restore_blueprint_human_review_state(data: dict[str, object]) -> None:
    work_id = "WORK-0D2E36965F224C29A0647A7E95D867B7"
    work = next(item for item in data["work_items"] if item.get("id") == work_id)
    work["status"] = "active"
    repo_root = subprocess.run(
        ["git", "-C", str(DOGFOOD), "rev-parse", "--show-toplevel"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    head_sha = subprocess.run(
        ["git", "-C", repo_root, "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    attempt = next(
        item
        for item in data["attempts"]
        if item.get("id") == work["current_attempt"]
    )
    attempt["workspace_path"] = repo_root
    attempt["head_sha"] = head_sha
    attempt["commits"] = [head_sha]
    evidence = max(
        (
            item
            for item in data["evidence_runs"]
            if item.get("work_item_id") == work_id
            and item.get("attempt_id") == work["current_attempt"]
        ),
        key=lambda item: item["timestamp"],
    )
    evidence["head_sha"] = head_sha
    evidence["manifest_hash"] = evidence_manifest_hash(evidence)
    current_review = max(
        (
            item
            for item in data["review_verdicts"]
            if item.get("work_item_id") == work_id
            and item.get("reviewer") == "PALARI-STEWARD"
        ),
        key=lambda item: item["timestamp"],
    )
    human_review = dict(current_review)
    human_review["id"] = "REVIEW-BLUEPRINT-TEST-HUMAN"
    human_review["reviewer"] = "HUMAN-FOUNDER"
    data["review_verdicts"] = [
        item
        for item in data["review_verdicts"]
        if item.get("work_item_id") != work_id
    ]
    data["human_decisions"] = [
        item for item in data["human_decisions"] if item.get("work_item_id") != work_id
    ]
    data["acceptance_records"] = [
        item for item in data["acceptance_records"] if item.get("work_item_id") != work_id
    ]
    data["outcomes"] = [
        item for item in data["outcomes"] if item.get("work_item_id") != work_id
    ]
    workspace = Workspace.from_raw(data, DOGFOOD)
    binding, errors = current_review_binding(
        workspace,
        work_id,
        require_output_coverage=True,
    )
    if errors:
        raise AssertionError(errors)
    human_review.update(binding)
    human_review["reviewed_head"] = head_sha
    human_review["proof_hash"] = review_proof_hash(human_review)
    data["review_verdicts"].append(human_review)


class AgentPacketTests(unittest.TestCase):
    def test_git_lease_coordinates_claims_across_linked_worktrees(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            second_root = root.parent / "parallel-worktree"
            subprocess.run(
                ["git", "-C", str(root), "worktree", "add", "-b", "parallel", str(second_root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first_workspace = Workspace.load(workspace_file)
            second_workspace_file = second_root / "workspace.json"
            second_workspace = Workspace.load(second_workspace_file)

            first = start_agent(
                first_workspace,
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            with self.assertRaisesRegex(WorkspaceError, "another Git worktree"):
                start_agent(
                    second_workspace,
                    second_workspace_file,
                    "WORK-0003",
                    "PALARI-SOFIA",
                )

            independent = start_agent(
                second_workspace,
                second_workspace_file,
                "WORK-0005",
                "PALARI-SOFIA",
            )
            self.assertEqual(independent["start"]["status"], "claimed")
            self.assertNotEqual(
                independent["start"]["claim"]["git_lease_ref"],
                first["start"]["claim"]["git_lease_ref"],
            )

            release_agent(
                first_workspace,
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            transferred = start_agent(
                second_workspace,
                second_workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            self.assertEqual(transferred["start"]["status"], "claimed")

    def test_registered_worktree_scan_blocks_a_legacy_claim_without_shared_ref(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            second_root = root.parent / "legacy-worktree"
            subprocess.run(
                ["git", "-C", str(root), "worktree", "add", "-b", "legacy", str(second_root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            claim = first["start"]["claim"]
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "update-ref",
                    "-d",
                    str(claim["git_lease_ref"]),
                    str(claim["git_lease_oid"]),
                ],
                check=True,
            )

            with self.assertRaisesRegex(WorkspaceError, "another Git worktree"):
                start_agent(
                    Workspace.load(second_root / "workspace.json"),
                    second_root / "workspace.json",
                    "WORK-0003",
                    "PALARI-SOFIA",
                )

    def test_expired_git_lease_can_be_replaced_without_overwriting_live_state(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            second_root = root.parent / "expiry-worktree"
            subprocess.run(
                ["git", "-C", str(root), "worktree", "add", "-b", "expiry", str(second_root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            first = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            claim = first["start"]["claim"]
            self.expire_git_lease(root, claim)

            replacement = start_agent(
                Workspace.load(second_root / "workspace.json"),
                second_root / "workspace.json",
                "WORK-0003",
                "PALARI-SOFIA",
            )

            self.assertNotEqual(
                replacement["start"]["claim"]["claim_session"],
                claim["claim_session"],
            )
            self.assertNotEqual(
                replacement["start"]["claim"]["git_lease_oid"],
                claim["git_lease_oid"],
            )

    def test_malformed_git_lease_blocks_queue_and_cannot_be_released_as_owned(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            started = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            claim = started["start"]["claim"]
            malformed_oid = subprocess.run(
                ["git", "-C", str(root), "hash-object", "-w", "--stdin"],
                input="{}\n",
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "update-ref",
                    str(claim["git_lease_ref"]),
                    malformed_oid,
                    str(claim["git_lease_oid"]),
                ],
                check=True,
            )

            next_payload = build_agent_next(
                Workspace.load(workspace_file),
                "PALARI-SOFIA",
                limit=20,
            )
            candidate = {
                item["work_item_id"]: item for item in next_payload["candidates"]
            }["WORK-0003"]
            self.assertFalse(candidate["can_start"])
            self.assertEqual(candidate["claim"]["status"], "invalid")
            self.assertIn(
                "CLAIM_COORDINATION_INVALID",
                candidate["start_blocker_codes"],
            )
            with self.assertRaisesRegex(WorkspaceError, "changed"):
                release_agent(
                    Workspace.load(workspace_file),
                    workspace_file,
                    "WORK-0003",
                    "PALARI-SOFIA",
                )

    def test_isolated_start_creates_resumes_and_surfaces_the_shared_claim(self) -> None:
        with self.git_workspace() as workspace_file:
            created = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--lease-minutes",
                    "10",
                    "--isolate",
                    "--json",
                ).stdout
            )

            self.assertEqual(created["isolation"]["status"], "created")
            isolated_root = Path(created["isolation"]["worktree_path"])
            self.assertTrue(isolated_root.is_dir())
            self.assertEqual(
                created["isolation"]["branch"],
                isolation_branch("WORK-0003"),
            )
            self.assertFalse(created["isolation"]["authority"]["merge"])
            self.assertIn(str(isolated_root), created["isolation"]["resume_command"])

            resumed = start_isolated_agent(
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
                lease_minutes=10,
            )
            self.assertEqual(resumed["isolation"]["status"], "resumed")
            self.assertEqual(
                resumed["start"]["claim"]["claim_session"],
                created["start"]["claim"]["claim_session"],
            )

            next_payload = build_agent_next(
                Workspace.load(workspace_file),
                "PALARI-SOFIA",
                limit=20,
            )
            work = {
                item["work_item_id"]: item for item in next_payload["candidates"]
            }["WORK-0003"]
            self.assertFalse(work["can_start"])
            self.assertEqual(work["claim"]["status"], "claimed")
            self.assertIn("WORK_ALREADY_CLAIMED", work["start_blocker_codes"])

            independent = start_isolated_agent(
                workspace_file,
                "WORK-0005",
                "PALARI-SOFIA",
                lease_minutes=10,
            )
            self.assertEqual(independent["isolation"]["status"], "created")
            self.assertNotEqual(
                independent["isolation"]["worktree_path"],
                created["isolation"]["worktree_path"],
            )

    def test_isolated_start_requires_committed_work_definition(self) -> None:
        with self.git_workspace() as workspace_file:
            original = workspace_file.read_text(encoding="utf-8")
            workspace_file.write_text(original + "\n", encoding="utf-8")

            with self.assertRaisesRegex(WorkspaceError, "uncommitted changes"):
                start_isolated_agent(
                    workspace_file,
                    "WORK-0003",
                    "PALARI-SOFIA",
                )

    def test_isolated_start_preserves_released_claim_start_witness(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            started = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            claim_start = started["start"]["claim"]["git_baseline"]["head_sha"]
            release_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            (root / "README.md").write_text("committed attempt\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "commit attempt"],
                check=True,
            )

            isolated = start_isolated_agent(
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )

            isolated_root = Path(isolated["isolation"]["worktree_path"])
            migrated = isolated["start"]["claim"]["git_baseline"]
            self.assertEqual(migrated["head_sha"], claim_start)
            self.assertEqual(migrated["git_root"], str(isolated_root.resolve()))

    def test_isolated_start_refuses_orphaned_branch_collision(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            branch = isolation_branch("WORK-0003")
            subprocess.run(
                ["git", "-C", str(root), "branch", branch],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            with self.assertRaisesRegex(WorkspaceError, "already exists"):
                start_isolated_agent(
                    workspace_file,
                    "WORK-0003",
                    "PALARI-SOFIA",
                )

    def test_git_readiness_separates_governance_from_target_compatibility(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            quick_add_work(
                workspace_file,
                "Integration-ready work",
                write=["README.md"],
                palari_id="PALARI-SOFIA",
                goal_id="GOAL-0001",
                workbench_id="WORKBENCH-BETA",
                work_id="WORK-READY",
                verify=["echo ok"],
            )
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "define work"],
                check=True,
            )
            base_sha = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            ).stdout.strip()
            start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-READY",
                "PALARI-SOFIA",
            )
            (root / "README.md").write_text("candidate\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "candidate"],
                check=True,
            )
            done = agent_done(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-READY",
                "PALARI-SOFIA",
                changed=["README.md"],
            )
            self.assertEqual(done["status"], "done")

            integrated = git_integration_readiness(
                workspace_file,
                "WORK-READY",
                target_ref="HEAD",
            )
            self.assertTrue(integrated["ready"])
            self.assertEqual(integrated["status"], "integrated")
            self.assertEqual(integrated["relationship"], "already-integrated")
            cli_integrated = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "git",
                    "status",
                    "--work-id",
                    "WORK-READY",
                    "--target-ref",
                    "HEAD",
                    "--json",
                ).stdout
            )
            self.assertEqual(cli_integrated["status"], "integrated")

            clean_target = root.parent / "clean-target"
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "worktree",
                    "add",
                    "-b",
                    "clean-target",
                    str(clean_target),
                    base_sha,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            (clean_target / "OTHER.md").write_text("target\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(clean_target), "add", "OTHER.md"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(clean_target), "commit", "-qm", "clean target"],
                check=True,
            )
            diverged = git_integration_readiness(
                workspace_file,
                "WORK-READY",
                target_ref="clean-target",
            )
            self.assertFalse(diverged["ready"])
            self.assertEqual(diverged["relationship"], "diverged")
            self.assertEqual(diverged["merge_simulation"]["status"], "clean")
            self.assertIn(
                "REVALIDATION_REQUIRED",
                {blocker["code"] for blocker in diverged["blockers"]},
            )

            conflict_target = root.parent / "conflict-target"
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "worktree",
                    "add",
                    "-b",
                    "conflict-target",
                    str(conflict_target),
                    base_sha,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            (conflict_target / "README.md").write_text("conflict\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(conflict_target), "add", "README.md"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(conflict_target), "commit", "-qm", "conflict target"],
                check=True,
            )
            conflict = git_integration_readiness(
                workspace_file,
                "WORK-READY",
                target_ref="conflict-target",
            )
            self.assertFalse(conflict["ready"])
            self.assertEqual(conflict["merge_simulation"]["status"], "conflict")
            self.assertIn(
                "TARGET_CONFLICT",
                {blocker["code"] for blocker in conflict["blockers"]},
            )

    def test_agent_next_lists_safe_candidates_first_for_palari(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-SOFIA")

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["agent"]["id"], "PALARI-SOFIA")
        self.assertGreaterEqual(result["ready_count"], 1)
        self.assertEqual(result["candidates"][0]["work_item_id"], "WORK-0003")
        self.assertEqual(result["candidates"][0]["can_start"], True)
        self.assertEqual(result["candidates"][0]["start_blockers"], [])
        self.assertEqual(
            result["candidates"][0]["next_command"],
            "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            result["candidates"][0]["loop_command"],
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            result["candidates"][0]["doctor_command"],
            "palari agent doctor WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(result["candidates"][0]["next_step_type"], "check-active-proof")
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari agent finish WORK-0003 --as PALARI-SOFIA --json",
            ],
        )

    def test_agent_next_includes_blocked_visible_work_without_marking_it_safe(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
        by_id = {item["work_item_id"]: item for item in result["candidates"]}

        self.assertIn("WORK-0001", by_id)
        self.assertEqual(by_id["WORK-0001"]["can_start"], False)
        self.assertIn("HUMAN_DECISION_REQUIRED", by_id["WORK-0001"]["blocker_codes"])
        self.assertEqual(
            by_id["WORK-0001"]["handoff_guidance"][0]["code"],
            "HUMAN_APPROVAL_HANDOFF",
        )
        self.assertEqual(
            by_id["WORK-0001"]["next_command"],
            "palari agent handoff WORK-0001 --as PALARI-SOFIA --json",
        )
        self.assertIn("PACKET_BLOCKED", by_id["WORK-0001"]["start_blocker_codes"])
        self.assertIn("ATTENTION_NOT_STARTABLE", by_id["WORK-0001"]["start_blocker_codes"])
        self.assertIn("WORK-0007", by_id)
        self.assertEqual(by_id["WORK-0007"]["can_start"], False)
        self.assertIn("RECEIPT_READY_REVIEW", by_id["WORK-0007"]["blocker_codes"])
        self.assertEqual(by_id["WORK-0007"]["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIn(
            "ready-to-edit review record commands",
            by_id["WORK-0007"]["handoff_guidance"][0]["message"],
        )
        self.assertIn("ATTENTION_NOT_STARTABLE", by_id["WORK-0007"]["start_blocker_codes"])
        self.assertEqual(by_id["WORK-0007"]["dependency_ids"], ["WORK-0003"])
        self.assertEqual(
            by_id["WORK-0007"]["blocked_by_dependency_ids"],
            ["WORK-0003"],
        )
        self.assertIn("WORK-0004", by_id)
        self.assertFalse(by_id["WORK-0004"]["can_start"])
        self.assertIn("HUMAN_DECISION_REQUIRED", by_id["WORK-0004"]["blocker_codes"])

    def test_agent_next_does_not_restart_work_waiting_for_review(self) -> None:
        def add_evidence_without_review(data: dict[str, object]) -> None:
            work = data["work_items"][2]
            attempt = next(
                item for item in data["attempts"] if item["id"] == work["current_attempt"]
            )
            data["evidence_runs"].append(
                {
                    "id": "EVIDENCE-WAITING-REVIEW",
                    "work_item_id": work["id"],
                    "attempt_id": attempt["id"],
                    "head_sha": attempt["commits"][-1],
                    "status": "passed",
                    "summary": "Evidence is present, but no review exists yet.",
                    "timestamp": "2026-06-22T01:00:00Z",
                }
            )

        workspace = self.modified_workspace(add_evidence_without_review)

        result = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-0003"]

        self.assertEqual(candidate["attention"], "needs-review")
        self.assertEqual(candidate["packet_status"], "blocked")
        self.assertEqual(candidate["can_start"], False)
        self.assertEqual(candidate["next_step_type"], "review-handoff")
        self.assertIn("REVIEW_REQUIRED", candidate["blocker_codes"])
        self.assertIn("PACKET_BLOCKED", candidate["start_blocker_codes"])
        self.assertIn("ATTENTION_NOT_STARTABLE", candidate["start_blocker_codes"])
        self.assertEqual(
            candidate["next_command"],
            "palari review guide WORK-0003 --json",
        )
        self.assertEqual(
            candidate["next_commands"][0],
            "palari review guide WORK-0003 --json",
        )
        self.assertEqual(candidate["handoff_guidance"], [])
        self.assertEqual(
            candidate["loop_command"],
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            candidate["doctor_command"],
            "palari agent doctor WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertIn(candidate["doctor_command"], candidate["next_commands"])
        self.assertIn(candidate["loop_command"], candidate["next_commands"])

    def test_agent_next_does_not_offer_start_command_when_queue_is_not_ai_safe(self) -> None:
        def make_unattempted_high_intensity_work(data: dict[str, object]) -> None:
            work = next(item for item in data["work_items"] if item["id"] == "WORK-0003")
            work["risk"] = "R4"
            work["current_attempt"] = ""
            data["attempts"] = [
                item for item in data["attempts"] if item["work_item_id"] != work["id"]
            ]

        workspace = self.modified_workspace(make_unattempted_high_intensity_work)

        result = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-0003"]

        self.assertEqual(candidate["attention"], "ready-for-ai-work")
        self.assertEqual(candidate["can_start"], False)
        self.assertEqual(candidate["next_step_type"], "inspect")
        self.assertIn("QUEUE_NOT_AI_SAFE", candidate["start_blocker_codes"])
        self.assertEqual(candidate["next_command"], "palari detail WORK-0003 --json")

    def test_agent_next_review_mode_marks_reviewable_work_ready(self) -> None:
        workspace = self.modified_workspace(_authorize_alfred_for_beta_sources)

        result = build_agent_next(workspace, "PALARI-ALFRED", mode="review", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-0007"]

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertGreaterEqual(result["ready_count"], 1)
        self.assertEqual(candidate["attention"], "receipt-ready")
        self.assertEqual(candidate["packet_status"], "ready")
        self.assertTrue(candidate["can_start"])
        self.assertEqual(candidate["start_blockers"], [])
        self.assertEqual(
            candidate["next_command"],
            "palari agent brief WORK-0007 --as PALARI-ALFRED --mode review --json",
        )
        self.assertEqual(
            candidate["next_commands"][:4],
            [
                "palari agent brief WORK-0007 --as PALARI-ALFRED --mode review --json",
                "palari review guide WORK-0007 --json",
                "palari agent check WORK-0007 --as PALARI-ALFRED --mode review --json",
                "palari agent doctor WORK-0007 --as PALARI-ALFRED --mode review --json",
            ],
        )
        self.assertEqual(
            candidate["next_commands"][4],
            "palari agent loop WORK-0007 --as PALARI-ALFRED --mode review --json",
        )

    def test_agent_next_review_mode_blocks_non_reviewable_work(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-ALFRED", mode="review", limit=20)
        candidate = {
            item["work_item_id"]: item for item in result["candidates"]
        }["WORK-0003"]

        self.assertFalse(candidate["can_start"])
        self.assertEqual(candidate["packet_status"], "blocked")
        self.assertIn("REVIEW_NOT_READY", candidate["blocker_codes"])
        self.assertIn("ATTENTION_NOT_REVIEWABLE", candidate["start_blocker_codes"])

    def test_agent_next_all_rolls_up_all_palaris(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        with (
            patch(
                "palari_company_os.agent_next.queue_items",
                wraps=queue_items,
            ) as build_queue,
            patch(
                "palari_company_os.governance_journal._read_records",
                wraps=governance_journal._read_records,
            ) as read_journal,
        ):
            result = build_agent_next_all(workspace)
        agent_ids = {agent["agent"]["id"] for agent in result["agents"]}
        candidates = [
            {"agent": agent["agent"], "candidate": candidate}
            for agent in result["agents"]
            for candidate in agent["candidates"]
        ]
        ready_candidates = [item for item in candidates if item["candidate"]["can_start"]]

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(result["status"], "ready" if result["ready_count"] else "no-ready-work")
        self.assertEqual(
            result["ready_count"],
            sum(agent["ready_count"] for agent in result["agents"]),
        )
        self.assertEqual(
            result["blocked_count"],
            sum(agent["blocked_count"] for agent in result["agents"]),
        )
        self.assertEqual(agent_ids, {"PALARI-STEWARD", "PALARI-ARCHITECT"})
        self.assertEqual(build_queue.call_count, 1)
        self.assertEqual(read_journal.call_count, 1)
        if not candidates:
            self.assertIsNone(result["top_candidate"])
            self.assertEqual(result["status"], "no-ready-work")
            self.assertTrue(result["next_allowed_commands"])
            self.assertIn("palari validate --json", result["next_allowed_commands"])
            return

        expected_top = min(
            ready_candidates or candidates,
            key=lambda item: item["candidate"]["queue_rank"],
        )
        self.assertEqual(result["top_candidate"], expected_top)
        self.assertEqual(
            result["next_allowed_commands"],
            expected_top["candidate"]["next_commands"],
        )

    def test_agent_next_all_exposes_top_ready_candidate(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next_all(workspace)

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["top_candidate"]["agent"]["id"], "PALARI-SOFIA")
        self.assertEqual(result["top_candidate"]["candidate"]["work_item_id"], "WORK-0003")
        self.assertEqual(result["top_candidate"]["candidate"]["can_start"], True)
        self.assertEqual(result["top_candidate"]["candidate"]["next_step_type"], "check-active-proof")
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent check WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )

    def test_agent_next_missing_palari_is_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_next(workspace, "PALARI-MISSING")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["ready_count"], 0)
        self.assertEqual(result["blockers"][0]["code"], "MISSING_PALARI")
        self.assertEqual(result["candidates"], [])

    def test_cli_agent_next_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "next", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertIn("candidates", result)
        self.assertEqual(result["candidates"][0]["can_start"], True)
        self.assertEqual(
            result["candidates"][0]["loop_command"],
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )
        self.assertEqual(
            result["candidates"][0]["doctor_command"],
            "palari agent doctor WORK-0003 --as PALARI-SOFIA --mode execute --json",
        )

    def test_cli_agent_next_text_prints_handoff_guidance(self) -> None:
        result = self.run_cli(
            "agent",
            "next",
            "--as",
            "PALARI-SOFIA",
        )

        self.assertIn("WORK-0006 [waiting]", result.stdout)
        self.assertIn("step: review-handoff", result.stdout)
        self.assertIn("doctor: palari agent doctor WORK-0006", result.stdout)
        self.assertIn("loop: palari agent loop WORK-0006", result.stdout)

    def test_cli_agent_next_text_prints_mode(self) -> None:
        result = self.run_cli(
            "agent",
            "next",
            "--as",
            "PALARI-ALFRED",
            "--mode",
            "review",
        )

        self.assertIn("Mode: review", result.stdout)
        self.assertIn("doctor: palari agent doctor", result.stdout)
        self.assertIn("loop: palari agent loop", result.stdout)

    def test_cli_agent_next_all_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "agent",
                "next",
                "--all",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(len(result["agents"]), 2)

    def test_cli_agent_next_defaults_to_all_rollup(self) -> None:
        result = json.loads(
            self.run_cli(
                "agent",
                "next",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(len(result["agents"]), 2)

    def test_cli_agent_next_all_text_prints_mode(self) -> None:
        result = self.run_cli(
            "agent",
            "next",
            "--all",
            "--mode",
            "review",
        )

        self.assertIn("Mode: review", result.stdout)
        self.assertIn("doctor: palari agent doctor", result.stdout)
        self.assertIn("loop: palari agent loop", result.stdout)

    def test_agent_finish_missing_proof_does_not_allow_completion_claim(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_finish(workspace, "WORK-0003", "PALARI-SOFIA")
        missing_codes = {item["code"] for item in result["missing_requirements"]}

        self.assertEqual(result["schema_version"], "palari.agent_finish.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["handoff_ready"], False)
        self.assertEqual(result["would_mutate"], False)
        self.assertIn("RECEIPT_PRESENT", missing_codes)
        self.assertIn("EVIDENCE_PRESENT", missing_codes)
        commands = "\n".join(result["next_allowed_commands"])
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
                "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            ],
        )
        self.assertIn("CLAIM_OWNED", missing_codes)
        self.assertIn(
            "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
            "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            commands,
        )
        self.assertIn(
            "palari evidence record EVIDENCE-ID --work-item-id WORK-0003 "
            "--attempt-id ATTEMPT-0002 --head-sha def5678 --status passed",
            commands,
        )

    def test_agent_finish_low_risk_receipt_ready_hands_off_to_human(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_finish(workspace, "WORK-0007", "PALARI-SOFIA")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["handoff_ready"], True)
        self.assertEqual(result["missing_requirements"], [])
        self.assertIn(
            "RECEIPT_PRESENT",
            {item["code"] for item in result["completed_requirements"]},
        )
        self.assertIn(
            "RECEIPT_READY_REVIEW",
            {blocker["code"] for blocker in result["blockers"]},
        )
        self.assertEqual(result["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIn("ready-to-edit review record commands", result["handoff_guidance"][0]["message"])
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent handoff WORK-0007 --as PALARI-SOFIA --json",
        )
        self.assertEqual(result["next_allowed_commands"][1], "palari review guide WORK-0007 --json")

    def test_agent_finish_dogfood_agent_loop_record_hands_off_to_review(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_finish(workspace, "WORK-REPO-0006", "PALARI-STEWARD")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["handoff_ready"], True)
        self.assertEqual(result["missing_requirements"], [])
        self.assertIn(
            "RECEIPT_PRESENT",
            {item["code"] for item in result["completed_requirements"]},
        )
        self.assertIn(
            "RECEIPT_READY_REVIEW",
            {blocker["code"] for blocker in result["blockers"]},
        )
        self.assertEqual(result["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertEqual(
            result["handoff_guidance"][0]["command"],
            "palari agent handoff WORK-REPO-0006 --as PALARI-STEWARD --json",
        )
        self.assertEqual(
            result["handoff_guidance"][0]["guide_command"],
            "palari review guide WORK-REPO-0006 --json",
        )
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari agent handoff WORK-REPO-0006 --as PALARI-STEWARD --json",
        )
        self.assertEqual(
            result["next_allowed_commands"][1],
            "palari review guide WORK-REPO-0006 --json",
        )

    def test_agent_finish_human_decision_required_remains_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_finish(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["can_finish"], False)
        missing = {item["code"]: item for item in result["missing_requirements"]}
        self.assertIn("HUMAN_DECISION_PRESENT", missing)
        self.assertNotIn("next_command", missing["HUMAN_DECISION_PRESENT"])
        self.assertTrue(result["handoff_ready"])
        self.assertEqual(result["handoff_guidance"][0]["code"], "HUMAN_APPROVAL_HANDOFF")
        self.assertEqual(
            result["resolution_summary"]["primary_class"],
            "human-authority",
        )
        self.assertTrue(result["resolution_summary"]["human_attention_required"])
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari detail WORK-0001 --json",
        )
        self.assertNotIn("palari human-decision record", "\n".join(result["next_allowed_commands"]))

    def test_terminal_work_is_closed_not_blocked_in_finish_and_loop(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        finish = build_agent_finish(
            workspace,
            "WORK-REPO-0027",
            "PALARI-STEWARD",
        )
        loop = build_agent_loop(
            workspace,
            "WORK-REPO-0027",
            "PALARI-STEWARD",
        )

        self.assertEqual(finish["status"], "closed")
        self.assertTrue(finish["can_finish"])
        self.assertEqual(finish["blockers"], [])
        self.assertEqual(finish["resolution_summary"]["primary_class"], "terminal")
        self.assertEqual(loop["status"], "closed")
        self.assertEqual(loop["blockers"], [])
        self.assertEqual([stage["name"] for stage in loop["stages"]], ["terminal"])
        self.assertTrue(loop["stages"][0]["ok"])

    def test_agent_finish_waiting_for_review_prioritizes_review_handoff(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_finish(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        missing = {item["code"]: item for item in result["missing_requirements"]}

        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(result["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json",
                "palari review guide WORK-REPO-0003 --json",
            ],
        )
        self.assertEqual(
            missing["REVIEW_PRESENT"]["next_command"],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertNotIn("next_command", missing["HUMAN_DECISION_PRESENT"])
        self.assertNotIn("palari human-decision record", "\n".join(result["next_allowed_commands"]))

    def test_agent_finish_review_mode_guides_review_recommendation_not_completion(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_finish(
            workspace,
            "WORK-REPO-0003",
            "PALARI-ARCHITECT",
            mode="review",
        )

        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["mode"], "review")
        self.assertFalse(result["can_finish"])
        self.assertIn("CLAIM_OWNED", {item["code"] for item in result["missing_requirements"]})
        self.assertIn(
            "palari agent start WORK-REPO-0003 --as PALARI-ARCHITECT --mode review --json",
            result["next_allowed_commands"],
        )

    def test_cli_agent_finish_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "finish", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_finish.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["next_step_type"], "check-active-proof")
        self.assertEqual(result["can_finish"], False)
        self.assertEqual(result["would_mutate"], False)

    def test_cli_agent_finish_text_shows_completed_requirements(self) -> None:
        result = self.run_cli("agent", "finish", "WORK-0007", "--as", "PALARI-SOFIA")

        self.assertIn("Status: handoff-ready", result.stdout)
        self.assertIn("Step: review-handoff", result.stdout)
        self.assertIn("Completed requirements:", result.stdout)
        self.assertIn("RECEIPT_PRESENT", result.stdout)
        self.assertIn("Handoff guidance:", result.stdout)
        self.assertIn("ready-to-edit review record commands", result.stdout)
        self.assertIn("Guidance: Do not continue execution.", result.stdout)

    def test_agent_handoff_receipt_ready_compiles_review_context(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_handoff(workspace, "WORK-REPO-0006", "PALARI-STEWARD")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["handoff_types"], ["review"])
        self.assertEqual(result["handoff_available"], True)
        self.assertEqual(result["would_mutate"], False)
        self.assertEqual(result["finish"]["handoff_ready"], True)
        self.assertEqual(result["finish"]["handoff_guidance"][0]["code"], "REVIEW_HANDOFF")
        self.assertIsNotNone(result["review_handoff"])
        self.assertIsNone(result["decision_handoff"])
        review = result["review_handoff"]
        self.assertEqual(review["status"], "receipt-ready")
        self.assertEqual(review["command"], "palari review guide WORK-REPO-0006 --json")
        self.assertIn("Hand off", result["finish"]["report_guidance"])
        self.assertIn(
            "palari review guide WORK-REPO-0006 --json",
            result["next_allowed_commands"],
        )
        self.assertNotIn(
            "palari review record REVIEW-ID",
            "\n".join(result["next_allowed_commands"]),
        )
        self.assertIn("HUMAN-FOUNDER", {candidate["id"] for candidate in review["reviewer_candidates"]})
        self.assertNotIn(
            "HUMAN-MAINTAINER",
            {candidate["id"] for candidate in review["reviewer_candidates"]},
        )
        human_commands = "\n".join(item["command"] for item in result["human_action_commands"])
        self.assertIn("--reviewer HUMAN-FOUNDER", human_commands)
        agent_commands = "\n".join(item["command"] for item in result["agent_action_commands"])
        self.assertIn("--reviewer PALARI-ARCHITECT", agent_commands)
        self.assertTrue(result["agent_action_boundary"]["agent_may_execute"])
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(result["human_action_boundary"]["count"], len(result["human_action_commands"]))
        self.assertIn(
            "human_action_commands[].command",
            result["human_action_boundary"]["human_only_command_fields"],
        )

    def test_agent_handoff_waiting_for_review_compiles_review_context(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_handoff(workspace, "WORK-REPO-0003", "PALARI-STEWARD")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["handoff_types"], ["review"])
        self.assertEqual(result["handoff_available"], True)
        self.assertIsNotNone(result["review_handoff"])
        self.assertIsNone(result["decision_handoff"])
        self.assertEqual(result["review_handoff"]["status"], "review-needed")
        self.assertEqual(
            result["next_allowed_commands"][0],
            "palari review guide WORK-REPO-0003 --json",
        )

    def test_handoff_exposes_palari_rereview_when_human_reviewer_exhausts_acceptors(
        self,
    ) -> None:
        workspace = self.modified_dogfood_workspace(
            _restore_blueprint_human_review_state
        )

        result = build_agent_handoff(
            workspace,
            "WORK-0D2E36965F224C29A0647A7E95D867B7",
            "PALARI-ARCHITECT",
        )

        self.assertEqual(result["handoff_types"], ["review", "human-approval"])
        self.assertEqual(result["human_approval_handoff"]["approval_candidates"], [])
        self.assertIn(
            "PALARI-STEWARD", {item["actor"] for item in result["agent_action_commands"]}
        )
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(result["human_action_commands"], [])
        self.assertTrue(result["agent_action_boundary"]["agent_may_execute"])
        self.assertNotIn(
            "palari human-decision record",
            "\n".join(result["next_allowed_commands"]),
        )
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(result["human_action_boundary"]["count"], len(result["human_action_commands"]))

    def test_blueprint_review_scenario_normalizes_future_terminal_state(self) -> None:
        source = json.loads((DOGFOOD / "workspace.json").read_text(encoding="utf-8"))
        work_id = "WORK-0D2E36965F224C29A0647A7E95D867B7"
        work = next(item for item in source["work_items"] if item["id"] == work_id)
        terminal = Workspace.from_raw(source, DOGFOOD)
        terminal_work = terminal.work_item(work_id)

        self.assertIsNotNone(terminal_work)
        assert terminal_work is not None
        self.assertEqual(work["status"], "completed")
        self.assertEqual(terminal_work.status, "completed")

        _restore_blueprint_human_review_state(source)
        restored = Workspace.from_raw(source, DOGFOOD)
        restored_work = restored.work_item(work_id)

        self.assertIsNotNone(restored_work)
        assert restored_work is not None
        self.assertEqual(restored_work.status, "active")
        self.assertFalse(
            any(item.work_item_id == work_id for item in restored.acceptance_records)
        )
        self.assertFalse(any(item.work_item_id == work_id for item in restored.outcomes))

    def test_agent_handoff_human_decision_compiles_decision_context(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_handoff(workspace, "WORK-0002", "PALARI-ALFRED")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["handoff_types"], ["decision"])
        self.assertEqual(result["handoff_available"], True)
        self.assertEqual(result["next_step_type"], "human-decision")
        self.assertIsNone(result["review_handoff"])
        decision = result["decision_handoff"]
        self.assertIsNotNone(decision)
        self.assertEqual(decision["decision"]["id"], "DECISION-0001")
        self.assertEqual(
            decision["command"],
            "palari decision guide DECISION-0001 --json",
        )
        self.assertIn(
            "palari decision guide DECISION-0001 --json",
            result["next_allowed_commands"],
        )
        self.assertIn(
            "No inbox use during beta",
            {item["result"] for item in decision["decision_update_commands"]},
        )
        human_commands = "\n".join(item["command"] for item in result["human_action_commands"])
        self.assertIn("palari decision update DECISION-0001", human_commands)
        self.assertIn("'result=No inbox use during beta'", human_commands)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(result["human_action_boundary"]["count"], len(result["human_action_commands"]))

    def test_decided_linked_decision_does_not_suppress_human_approval(self) -> None:
        workspace = self.modified_workspace(_link_decided_decision_to_work_0001)

        result = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["handoff_types"], ["human-approval"])
        self.assertIsNone(result["decision_handoff"])
        self.assertIsNotNone(result["human_approval_handoff"])

    def test_agent_handoff_suppresses_human_approval_until_proof_is_complete(self) -> None:
        workspace = self.modified_workspace(_remove_work_0001_exact_proof)

        result = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["handoff_types"], [])
        self.assertEqual(result["handoff_available"], False)
        self.assertIsNone(result["human_approval_handoff"])
        self.assertEqual(result["human_action_commands"], [])
        self.assertIn("palari receipt record RECEIPT-ID", result["next_allowed_commands"][0])

    def test_agent_handoff_human_approval_compiles_work_approval_context(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["handoff_types"], ["human-approval"])
        self.assertEqual(result["handoff_available"], True)
        self.assertEqual(result["next_step_type"], "human-decision")
        self.assertIsNone(result["review_handoff"])
        self.assertIsNone(result["decision_handoff"])
        approval = result["human_approval_handoff"]
        self.assertIsNotNone(approval)
        self.assertEqual(approval["work_item"]["id"], "WORK-0001")
        self.assertEqual(approval["approval_progress"], "0/1")
        self.assertEqual(approval["required_approval_capability"], "product")
        self.assertEqual(approval["approval_candidates"][0]["id"], "HUMAN-FOUNDER")
        self.assertNotIn("Receipt state is missing", " ".join(approval["approval_focus"]))
        self.assertEqual(
            result["next_allowed_commands"][:2],
            ["palari detail WORK-0001 --json", "palari queue --json"],
        )
        commands = "\n".join(item["command"] for item in result["human_action_commands"])
        self.assertIn("palari human-decision record", commands)
        self.assertNotIn("'palari human-decision record'", commands)
        self.assertIn("--decision accepted", commands)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)

    def test_agent_handoff_threads_one_journal_context_through_human_approval(
        self,
    ) -> None:
        workspace = Workspace.load(WORKSPACE)
        journal_context = governance_journal.JournalVerificationContext()
        eligible_inbox = {
            "individual_items": [
                {"id": "WORK-0001", "state": "eligible", "reasons": []}
            ],
            "packs": [
                {
                    "pack_id": "PACK-TEST",
                    "pack_digest": "sha256:pack-test",
                }
            ],
            "approval_commands": [
                {
                    "presentation_digest": "sha256:presentation-test",
                    "approve_eligible": (
                        "palari human-decision pack --pack-digest sha256:pack-test "
                        "--presentation-digest sha256:presentation-test "
                        "--human-id HUMAN-ID --approve-eligible "
                        "--pack-member WORK-0001 --json"
                    ),
                }
            ],
        }

        with (
            patch(
                "palari_company_os.agent_handoff.JournalVerificationContext",
                return_value=journal_context,
            ) as context_factory,
            patch(
                "palari_company_os.agent_handoff.build_agent_finish",
                wraps=build_agent_finish,
            ) as finish,
            patch(
                "palari_company_os.agent_handoff.detail",
                wraps=detail,
            ) as handoff_detail,
            patch(
                "palari_company_os.agent_handoff.approval_inbox",
                return_value=eligible_inbox,
            ) as approval_inbox,
        ):
            result = build_agent_handoff(
                workspace,
                "WORK-0001",
                "PALARI-SOFIA",
            )

        context_factory.assert_called_once_with()
        self.assertIs(finish.call_args.kwargs["journal_context"], journal_context)
        self.assertIs(
            handoff_detail.call_args.kwargs["journal_context"],
            journal_context,
        )
        self.assertIs(
            approval_inbox.call_args.kwargs["journal_context"],
            journal_context,
        )
        self.assertEqual(result["status"], "handoff-ready")
        self.assertEqual(result["handoff_types"], ["human-approval"])
        approval = result["human_approval_handoff"]["approval_pack"]
        self.assertTrue(approval["available"])
        self.assertEqual(approval["item_state"], "eligible")
        self.assertEqual(
            approval["presentation_digest"],
            "sha256:presentation-test",
        )
        self.assertFalse(result["human_action_boundary"]["agent_may_execute"])
        self.assertTrue(result["human_action_commands"])
        self.assertTrue(
            all(
                item["type"] == "approval-pack"
                for item in result["human_action_commands"]
            )
        )
        command = result["human_action_commands"][0]["command"]
        self.assertIn("--presentation-digest sha256:presentation-test", command)
        self.assertNotIn("--human-id HUMAN-ID", command)

    def test_emitted_agent_safe_commands_for_human_approval_work_execute(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            workspace = Workspace.load(workspace_file)
            queue_payload = json.loads(
                self.run_cli_in_workspace(workspace_file, "queue", "--json").stdout
            )
            queue_item = {
                item["id"]: item for item in queue_payload["queue"]
            }["WORK-0001"]
            next_payload = build_agent_next(workspace, "PALARI-SOFIA", limit=20)
            candidate = {
                item["work_item_id"]: item for item in next_payload["candidates"]
            }["WORK-0001"]
            loop_payload = build_agent_loop(workspace, "WORK-0001", "PALARI-SOFIA")
            doctor_payload = build_agent_doctor(workspace, "WORK-0001", "PALARI-SOFIA")
            handoff_payload = build_agent_handoff(workspace, "WORK-0001", "PALARI-SOFIA")

            commands = [
                queue_item["agent_handoff_command"],
                queue_item["agent_loop_command"],
                *queue_item["next_commands"],
                candidate["next_command"],
                *candidate["next_commands"],
                *loop_payload["next_allowed_commands"],
                *doctor_payload["recommended_commands"],
                *handoff_payload["next_allowed_commands"],
            ]
            if loop_payload["commands"].get("handoff"):
                commands.append(loop_payload["commands"]["handoff"])
            self.assertEqual(
                candidate["handoff_guidance"][0]["code"], "HUMAN_APPROVAL_HANDOFF"
            )
            self.assertIn("handoff", loop_payload["commands"])
            self.assertTrue(handoff_payload["human_action_commands"])
            for command in sorted(set(commands)):
                with self.subTest(command=command):
                    self.run_cli_in_workspace(workspace_file, *shlex.split(command)[1:])

    def test_cli_agent_handoff_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli(
                "--workspace",
                str(DOGFOOD),
                "agent",
                "handoff",
                "WORK-REPO-0006",
                "--as",
                "PALARI-STEWARD",
                "--json",
            ).stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertEqual(result["handoff_types"], ["review"])
        self.assertEqual(result["review_handoff"]["status"], "receipt-ready")
        self.assertEqual(result["human_action_commands"][0]["type"], "review-record")
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)

    def test_cli_agent_handoff_text_shows_review_commands(self) -> None:
        result = self.run_cli(
            "--workspace",
            str(DOGFOOD),
            "agent",
            "handoff",
            "WORK-REPO-0006",
            "--as",
            "PALARI-STEWARD",
        )

        self.assertIn("Agent handoff:", result.stdout)
        self.assertIn("Review handoff:", result.stdout)
        self.assertIn("review focus:", result.stdout)
        self.assertIn("Compare the attempt result", result.stdout)
        self.assertIn("receipt:", result.stdout)
        self.assertIn("external writes: none", result.stdout)
        self.assertIn("No deployment performed", result.stdout)
        self.assertIn("ready-to-edit review record commands", result.stdout)
        self.assertIn("review record commands:", result.stdout)
        self.assertIn("Human action boundary: agent may quote", result.stdout)

    def test_ready_execute_packet_is_compact_and_actionable(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["schema_version"], "palari.agent_packet.v1")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "execute")
        self.assertEqual(packet["agent"]["id"], "PALARI-SOFIA")
        self.assertEqual(packet["work_item"]["id"], "WORK-0003")
        self.assertEqual(packet["workbench"]["id"], "WORKBENCH-BETA")
        self.assertEqual(packet["allowed_paths"]["read"], ["docs/product/company-os.md"])
        self.assertEqual(packet["allowed_paths"]["write"], ["docs/product/company-os.md"])
        self.assertEqual(packet["completion_contract"]["requires_receipt"], True)
        self.assertEqual(packet["completion_contract"]["requires_evidence"], True)
        self.assertEqual(packet["state"]["next_step_type"], "check-active-proof")
        self.assertEqual(packet["proof_state"]["attempt"]["head_sha"], "def5678")
        self.assertIn("palari scope WORK-0003 --json", packet["next_allowed_commands"])
        self.assertIn(
            "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
            "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            packet["next_allowed_commands"],
        )
        self.assertIn("Stop if you need to read or write outside allowed_paths.", packet["stop_conditions"])
        self.assertEqual(packet["blockers"], [])
        self.assertTrue(packet["context_hash"].startswith("sha256:"))

    def test_review_mode_packet_is_ready_for_receipt_ready_work(self) -> None:
        workspace = self.modified_workspace(_authorize_alfred_for_beta_sources)

        packet = build_agent_brief(workspace, "WORK-0007", "PALARI-ALFRED", "review")

        self.assertEqual(packet["schema_version"], "palari.agent_packet.v1")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "review")
        self.assertEqual(packet["allowed_paths"]["write"], [])
        self.assertEqual(packet["completion_contract"]["review_mode"], True)
        self.assertEqual(packet["review_context"]["status"], "receipt-ready")
        self.assertIn("review_focus", packet["review_context"])
        self.assertEqual(packet["human_action_boundary"]["agent_may_execute"], False)
        self.assertIn(
            "review_context.human_review_commands[].command",
            packet["human_action_boundary"]["human_only_command_fields"],
        )
        self.assertTrue(packet["agent_action_boundary"]["agent_may_execute"])
        self.assertEqual(packet["agent_action_boundary"]["count"], 1)
        self.assertEqual(
            packet["next_allowed_commands"][0],
            "palari review guide WORK-0007 --json",
        )
        self.assertIn("Stop before editing work outputs", packet["stop_conditions"][0])
        self.assertEqual(packet["blockers"], [])

    def test_review_mode_packet_is_ready_for_needs_review_work(self) -> None:
        def add_evidence_without_review(data: dict[str, object]) -> None:
            work = data["work_items"][2]
            attempt = next(
                item for item in data["attempts"] if item["id"] == work["current_attempt"]
            )
            data["evidence_runs"].append(
                {
                    "id": "EVIDENCE-WAITING-REVIEW",
                    "work_item_id": work["id"],
                    "attempt_id": attempt["id"],
                    "head_sha": attempt["commits"][-1],
                    "status": "passed",
                    "summary": "Evidence is present, but no review exists yet.",
                    "timestamp": "2026-06-22T04:10:00Z",
                }
            )

        def authorize_and_add_evidence(data: dict[str, object]) -> None:
            _authorize_alfred_for_beta_sources(data)
            add_evidence_without_review(data)

        workspace = self.modified_workspace(authorize_and_add_evidence)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-ALFRED", "review")

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "review")
        self.assertEqual(packet["review_context"]["status"], "review-needed")
        self.assertEqual(packet["review_context"]["evidence"]["id"], "EVIDENCE-WAITING-REVIEW")
        self.assertEqual(packet["completion_contract"]["requires_evidence"], False)
        self.assertEqual(
            packet["human_action_boundary"]["agent_allowed_use"],
            "Quote or summarize human-only commands for a human supervisor.",
        )
        self.assertIn(
            "Do not run human review record commands.",
            packet["human_action_boundary"]["must_not"],
        )

    def test_review_mode_blocks_work_that_is_not_review_ready(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "review")

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("REVIEW_NOT_READY", {blocker["code"] for blocker in packet["blockers"]})
        self.assertEqual(
            packet["next_allowed_commands"],
            [
                "palari detail WORK-0003 --json",
                "palari queue --json",
                "palari validate --json",
            ],
        )

    def test_distinct_palari_can_supplement_positive_human_review(self) -> None:
        workspace = self.modified_dogfood_workspace(
            _restore_blueprint_human_review_state
        )

        packet = build_agent_brief(
            workspace,
            "WORK-0D2E36965F224C29A0647A7E95D867B7",
            "PALARI-STEWARD",
            "review",
        )

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["agent"]["id"], "PALARI-STEWARD")
        self.assertEqual(packet["state"]["attention"], "needs-human-decision")
        self.assertIn(
            "--reviewer PALARI-STEWARD",
            "\n".join(packet["next_allowed_commands"]),
        )
        self.assertTrue(packet["agent_action_boundary"]["agent_may_execute"])

    def test_builder_cannot_receive_its_own_review_packet(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        packet = build_agent_brief(
            workspace,
            "WORK-0D2E36965F224C29A0647A7E95D867B7",
            "PALARI-ARCHITECT",
            "review",
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "PALARI_NOT_ASSIGNED", {blocker["code"] for blocker in packet["blockers"]}
        )
        self.assertNotIn("agent_action_boundary", packet)

    def test_packet_context_hash_ignores_created_at(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        changed_timestamp = dict(packet)
        changed_timestamp["created_at"] = "2099-01-01T00:00:00Z"

        self.assertEqual(_context_hash(packet), _context_hash(changed_timestamp))

    def test_blocked_packet_names_dependency_and_receipt_review_blockers(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0007", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["status"], "blocked")
        codes = {blocker["code"] for blocker in packet["blockers"]}
        self.assertIn("DEPENDENCY_NOT_TERMINAL", codes)
        self.assertIn("RECEIPT_READY_REVIEW", codes)
        self.assertEqual(packet["dependencies"][0]["id"], "WORK-0003")
        self.assertEqual(packet["allowed_sources"][0]["id"], "SOURCE-0001")
        self.assertEqual(packet["allowed_sources"][0]["data_class"], "internal")
        self.assertEqual(packet["allowed_sources"][0]["authority"], "company_owned")
        self.assertEqual(packet["allowed_sources"][0]["steward_human"], "HUMAN-FOUNDER")
        self.assertEqual(packet["allowed_sources"][0]["freshness_sla"], "weekly")
        self.assertFalse(packet["allowed_sources"][0]["redaction_required"])
        self.assertEqual(packet["completion_contract"]["requires_evidence"], False)
        self.assertEqual(
            packet["next_allowed_commands"],
            [
                "palari detail WORK-0007 --json",
                "palari queue --json",
                "palari validate --json",
            ],
        )

    def test_invalid_work_or_palari_returns_blocked_packet(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        missing_work = build_agent_brief(workspace, "WORK-MISSING", "PALARI-SOFIA", "execute")
        missing_palari = build_agent_brief(workspace, "WORK-0003", "PALARI-MISSING", "execute")

        self.assertEqual(missing_work["status"], "blocked")
        self.assertEqual(missing_work["blockers"][0]["code"], "MISSING_WORK_ITEM")
        self.assertEqual(missing_palari["status"], "blocked")
        self.assertEqual(missing_palari["blockers"][0]["code"], "MISSING_PALARI")

    def test_wrong_palari_and_external_write_are_blocked(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        wrong_palari = build_agent_brief(workspace, "WORK-0003", "PALARI-ALFRED", "execute")

        self.assertEqual(wrong_palari["status"], "blocked")
        self.assertIn(
            "PALARI_NOT_ASSIGNED",
            {blocker["code"] for blocker in wrong_palari["blockers"]},
        )

        external_write = self.modified_workspace(
            lambda data: data["work_items"][2].update({"allowed_actions": ["external_write"]})
        )
        packet = build_agent_brief(external_write, "WORK-0003", "PALARI-SOFIA", "execute")

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "EXTERNAL_WRITE_REQUIRES_APPROVAL",
            {blocker["code"] for blocker in packet["blockers"]},
        )

    def test_packet_does_not_dump_unrelated_workspace_records(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        encoded = json.dumps(packet, sort_keys=True)

        self.assertNotIn("WORK-0001", encoded)
        self.assertNotIn("Prepare beta launch checklist", encoded)
        self.assertIn("omitted_context", packet)
        self.assertEqual(packet["omitted_context"][0]["counts"]["work_items"], 7)

    def test_cli_agent_brief_is_read_only_and_start_persists_packet_and_claim(self) -> None:
        brief = json.loads(
            self.run_cli("agent", "brief", "WORK-0003", "--as", "PALARI-SOFIA", "--mode", "execute", "--json").stdout
        )

        self.assertEqual(brief["status"], "ready")
        self.assertNotIn("start", brief)

        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            start = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )
            packet_path = workspace_file.parent / start["start"]["packet_path"]
            claim_path = workspace_file.parent / start["start"]["claim_path"]

            self.assertEqual(start["status"], "ready")
            self.assertEqual(brief["packet_id"], start["packet_id"])
            self.assertEqual(start["start"]["status"], "claimed")
            self.assertTrue(packet_path.exists())
            self.assertTrue(claim_path.exists())
            self.assertEqual(json.loads(packet_path.read_text())["packet_id"], start["packet_id"])
            claim = json.loads(claim_path.read_text())
            self.assertEqual(claim["claimed_by"], "PALARI-SOFIA")
            self.assertEqual(claim["git_baseline"]["schema_version"], "palari.git_baseline.v1")
            self.assertTrue(claim["git_baseline_hash"].startswith("sha256:"))

            claim["git_baseline"]["entries"].append(
                {"path": "hidden.txt", "status": "untracked", "fingerprint": {"exists": True}}
            )
            claim_path.write_text(json.dumps(claim), encoding="utf-8")
            check = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            claim_check = next(item for item in check["checks"] if item["code"] == "CLAIM_OWNED")
            self.assertEqual(claim_check["status"], "fail")
            self.assertIn("git_baseline_hash", claim_check["message"])

            release = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "release",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            self.assertTrue(release["released"])
            self.assertFalse(claim_path.exists())

    def test_cli_agent_start_reports_claim_update_lock_as_json(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            lock_dir = workspace_file.parent / ".palari" / "claims"
            lock_dir.mkdir(parents=True)
            lock_path = lock_dir / "WORK-0003.lock"
            lock_path.write_text("test lock\n", encoding="utf-8")

            result = self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr, "")
            self.assertEqual(payload["ok"], False)
            self.assertEqual(payload["error"]["code"], "CLAIM_UPDATE_IN_PROGRESS")
            self.assertEqual(payload["error"]["work_item"], "WORK-0003")
            self.assertIn("retry shortly", payload["error"]["message"])
            self.assertTrue(lock_path.exists())

    def test_generic_work_update_is_blocked_during_active_claim(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
            )

            result = self.run_cli_in_workspace(
                workspace_file,
                "work",
                "update",
                "WORK-0003",
                "--list",
                "allowed_resources=docs,deploy",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("active execute claim", result.stderr)
            self.assertIn("cannot change its packet authority", result.stderr)

    def test_active_claim_cannot_restart_with_changed_packet_authority(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            first = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )
            data = json.loads(workspace_file.read_text(encoding="utf-8"))
            work = next(item for item in data["work_items"] if item["id"] == "WORK-0003")
            work["allowed_resources"] = ["docs", "deploy"]
            workspace_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

            result = self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("packet authority differs", payload["error"]["message"])
            claim_path = workspace_file.parent / first["start"]["claim_path"]
            claim = json.loads(claim_path.read_text(encoding="utf-8"))
            self.assertEqual(claim["context_hash"], first["context_hash"])

    def test_active_claim_can_refresh_after_proof_state_changes(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            first = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )
            self.run_cli_in_workspace(
                workspace_file,
                "receipt",
                "record",
                "RECEIPT-CLAIM-REFRESH",
                "--work-item-id",
                "WORK-0003",
                "--attempt-id",
                "ATTEMPT-0002",
                "--actor",
                "PALARI-SOFIA",
                "--list",
                "actions_taken=recorded bounded proof",
                "--list",
                "outputs_created=docs/product/company-os.md",
                "--json",
            )

            refreshed = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--mode",
                    "execute",
                    "--json",
                ).stdout
            )

            self.assertEqual(refreshed["start"]["status"], "claimed")
            self.assertNotEqual(refreshed["context_hash"], first["context_hash"])
            self.assertEqual(
                refreshed["start"]["claim"]["git_baseline"],
                first["start"]["claim"]["git_baseline"],
            )

    def test_release_and_restart_cannot_launder_changed_preexisting_dirt(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            root = workspace_file.parent
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "workspace"], check=True
            )
            note = root / "user-note.txt"
            note.write_text("pre-existing\n", encoding="utf-8")

            first = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            first_baseline = first["start"]["claim"]["git_baseline"]
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "release",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )
            note.write_text("changed after the original claim with a new size\n", encoding="utf-8")

            second = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "start",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--json",
                ).stdout
            )
            self.assertEqual(second["start"]["claim"]["git_baseline"], first_baseline)
            check = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--git-diff",
                    "--json",
                ).stdout
            )

            self.assertIn("user-note.txt", check["file_changes"]["changed_files"])
            self.assertIn("user-note.txt", check["file_changes"]["outside_write_boundary"])

    def test_cli_agent_brief_review_mode_emits_review_context(self) -> None:
        result = json.loads(
            self.run_cli(
                "--workspace",
                str(DOGFOOD),
                "agent",
                "brief",
                "WORK-REPO-0006",
                "--as",
                "PALARI-ARCHITECT",
                "--mode",
                "review",
                "--json",
            ).stdout
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["mode"], "review")
        self.assertEqual(
            result["review_context"]["command"],
            "palari review guide WORK-REPO-0006 --json",
        )
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)

    def test_agent_check_ready_packet_fails_missing_completion_proof(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0003", "PALARI-SOFIA")
        checks = self.checks_by_code(result)

        self.assertEqual(result["schema_version"], "palari.agent_check.v1")
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["packet_status"], "ready")
        self.assertEqual(checks["PACKET_READY"]["status"], "pass")
        self.assertEqual(checks["RECEIPT_PRESENT"]["status"], "fail")
        self.assertEqual(checks["EVIDENCE_PRESENT"]["status"], "fail")
        self.assertEqual(checks["CLAIM_OWNED"]["status"], "fail")
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "pass")
        self.assertEqual(checks["REVIEW_PRESENT"]["required"], False)
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "pass")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], False)
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json",
                "palari receipt record RECEIPT-ID --work-item-id WORK-0003 "
                "--attempt-id ATTEMPT-0002 --actor PALARI-SOFIA --json",
            ],
        )

    def test_agent_check_passes_claim_and_file_boundary_after_start(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )
            result = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--changed",
                    "docs/product/company-os.md",
                    "--json",
                ).stdout
            )
            checks = self.checks_by_code(result)

            self.assertEqual(checks["CLAIM_OWNED"]["status"], "pass")
            self.assertEqual(checks["FILE_CHANGES_WITHIN_WRITE_BOUNDARY"]["status"], "pass")
            self.assertEqual(checks["FILE_CHANGES_RECORDED"]["status"], "pass")
            self.assertEqual(result["file_changes"]["inside_write_boundary"], ["docs/product/company-os.md"])

    def test_agent_check_reports_out_of_boundary_and_unrecorded_changes(self) -> None:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            self.run_cli_in_workspace(
                workspace_file,
                "agent",
                "start",
                "WORK-0003",
                "--as",
                "PALARI-SOFIA",
                "--json",
            )
            result = json.loads(
                self.run_cli_in_workspace(
                    workspace_file,
                    "agent",
                    "check",
                    "WORK-0003",
                    "--as",
                    "PALARI-SOFIA",
                    "--changed",
                    "secrets.env",
                    "--json",
                ).stdout
            )
            checks = self.checks_by_code(result)

            self.assertEqual(checks["FILE_CHANGES_WITHIN_WRITE_BOUNDARY"]["status"], "fail")
            self.assertEqual(checks["FILE_CHANGES_RECORDED"]["status"], "fail")
            self.assertEqual(result["file_changes"]["outside_write_boundary"], ["secrets.env"])
            self.assertEqual(result["file_changes"]["unrecorded_changed_files"], ["secrets.env"])

    def test_agent_json_errors_are_machine_readable(self) -> None:
        result = self.run_cli_in_workspace(
            Path("/tmp/palari-missing-workspace"),
            "agent",
            "check",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--json",
            check=False,
        )
        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "WORKSPACE_FILE_NOT_FOUND")
        self.assertEqual(payload["error"]["work_item"], "WORK-0003")
        self.assertIn("palari agent brief WORK-0003 --as PALARI-SOFIA", payload["next_allowed_commands"][0])

    def test_agent_json_parse_errors_are_machine_readable(self) -> None:
        result = self.run_cli_in_workspace(
            WORKSPACE,
            "agent",
            "check",
            "WORK-0003",
            "--json",
            check=False,
        )
        payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "ARGUMENT_PARSE_ERROR")
        self.assertEqual(payload["error"]["work_item"], "WORK-0003")
        self.assertIn("--as", payload["error"]["message"])
        self.assertIn("palari queue --json", payload["next_allowed_commands"])

    def test_agent_check_blocked_packet_returns_packet_blockers(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0007", "PALARI-SOFIA")
        codes = {blocker["code"] for blocker in result["blockers"]}

        self.assertEqual(result["ok"], False)
        self.assertEqual(result["packet_status"], "blocked")
        self.assertIn("DEPENDENCY_NOT_TERMINAL", codes)
        self.assertIn("RECEIPT_READY_REVIEW", codes)
        self.assertEqual(self.checks_by_code(result)["PACKET_READY"]["status"], "fail")

    def test_agent_check_receipt_ready_low_risk_does_not_require_review_or_human_decision(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0007", "PALARI-SOFIA")
        checks = self.checks_by_code(result)

        self.assertEqual(checks["RECEIPT_PRESENT"]["status"], "pass")
        self.assertEqual(checks["EVIDENCE_PRESENT"]["status"], "pass")
        self.assertEqual(checks["EVIDENCE_PRESENT"]["required"], False)
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "pass")
        self.assertEqual(checks["REVIEW_PRESENT"]["required"], False)
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "pass")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], False)

    def test_agent_check_human_decision_required_work_fails_until_approval_exists(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_check(workspace, "WORK-0001", "PALARI-SOFIA")
        checks = self.checks_by_code(result)

        self.assertEqual(result["ok"], False)
        self.assertIn(
            "HUMAN_DECISION_REQUIRED",
            {blocker["code"] for blocker in result["blockers"]},
        )
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "fail")
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["required"], True)

    def test_agent_check_waiting_for_review_does_not_offer_human_decision(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_check(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        checks = self.checks_by_code(result)

        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertEqual(checks["REVIEW_PRESENT"]["status"], "fail")
        self.assertEqual(
            checks["REVIEW_PRESENT"]["next_command"],
            "palari review guide WORK-REPO-0003 --json",
        )
        self.assertEqual(checks["HUMAN_DECISION_PRESENT"]["status"], "fail")
        self.assertNotIn("next_command", checks["HUMAN_DECISION_PRESENT"])
        self.assertEqual(
            result["next_allowed_commands"][:2],
            [
                "palari agent handoff WORK-REPO-0003 --as PALARI-STEWARD --json",
                "palari review guide WORK-REPO-0003 --json",
            ],
        )
        self.assertNotIn("palari human-decision record", "\n".join(result["next_allowed_commands"]))

    def test_cli_agent_check_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "check", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_check.v1")
        self.assertEqual(result["ok"], False)
        self.assertEqual(result["packet_id"], "PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertTrue(result["packet_context_hash"].startswith("sha256:"))
        self.assertEqual(result["next_step_type"], "check-active-proof")
        self.assertIn("checks", result)
        self.assertIn("next_allowed_commands", result)

    def test_cli_agent_check_text_prints_mode(self) -> None:
        result = self.run_cli(
            "agent",
            "check",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--mode",
            "execute",
        )

        self.assertIn("Mode: execute", result.stdout)

    def test_agent_loop_summarizes_existing_read_only_steps(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_loop(workspace, "WORK-0003", "PALARI-SOFIA")
        stages = {stage["name"]: stage for stage in result["stages"]}

        self.assertEqual(result["schema_version"], "palari.agent_loop.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["next_step_type"], "check-active-proof")
        self.assertEqual(result["would_mutate"], False)
        self.assertEqual(result["commands"]["brief"], stages["brief"]["command"])
        self.assertEqual(result["commands"]["check"], stages["check"]["command"])
        self.assertEqual(result["commands"]["finish"], stages["finish"]["command"])
        self.assertNotIn("handoff", result["commands"])
        self.assertEqual(stages["brief"]["status"], "ready")
        self.assertEqual(stages["check"]["status"], "fail")
        self.assertIn("RECEIPT_PRESENT", stages["check"]["failed_required_checks"])
        self.assertIn("EVIDENCE_PRESENT", stages["check"]["failed_required_checks"])
        self.assertIn("Run the stage commands", result["omitted_context"][0]["reason"])

    def test_agent_loop_includes_human_boundary_for_handoff(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_loop(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        stages = {stage["name"]: stage for stage in result["stages"]}

        self.assertEqual(result["status"], "handoff-required")
        self.assertEqual(result["next_step_type"], "review-handoff")
        self.assertIn("handoff", result["commands"])
        self.assertEqual(stages["handoff"]["status"], "available")
        self.assertEqual(stages["handoff"]["handoff_types"], ["review"])
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(
            result["human_action_boundary"]["human_only_command_fields"],
            ["human_action_commands[].command"],
        )

    def test_cli_agent_loop_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "loop", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_loop.v1")
        self.assertEqual(result["loop_id"], "LOOP-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertEqual([stage["name"] for stage in result["stages"]], ["brief", "check", "finish"])
        self.assertIn("next_allowed_commands", result)

    def test_cli_agent_loop_text_prints_stage_commands(self) -> None:
        result = self.run_cli("agent", "loop", "WORK-0003", "--as", "PALARI-SOFIA")

        self.assertIn("Agent loop: LOOP-WORK-0003-PALARI-SOFIA-EXECUTE-V1", result.stdout)
        self.assertIn("Stages:", result.stdout)
        self.assertIn("palari agent brief WORK-0003 --as PALARI-SOFIA", result.stdout)

    def test_agent_doctor_explains_missing_proof_without_mutation(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = build_agent_doctor(workspace, "WORK-0003", "PALARI-SOFIA")
        checks = {check["code"]: check for check in result["checks"]}

        self.assertEqual(result["schema_version"], "palari.agent_doctor.v1")
        self.assertEqual(result["doctor_id"], "DOCTOR-WORK-0003-PALARI-SOFIA-EXECUTE-V1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertEqual(result["agent_safe"], True)
        self.assertEqual(result["human_handoff_required"], False)
        self.assertEqual(result["would_mutate"], False)
        self.assertIn("RECEIPT_PRESENT", result["summary"])
        self.assertEqual(checks["PACKET"]["status"], "pass")
        self.assertEqual(checks["CONTRACT"]["status"], "fail")
        self.assertIn(
            "palari receipt record RECEIPT-ID --work-item-id WORK-0003",
            "\n".join(result["recommended_commands"]),
        )
        self.assertIn(
            "palari agent loop WORK-0003 --as PALARI-SOFIA --mode execute --json",
            result["recommended_commands"],
        )

    def test_agent_doctor_marks_human_handoff_boundary(self) -> None:
        workspace = Workspace.load(DOGFOOD)

        result = build_agent_doctor(workspace, "WORK-REPO-0003", "PALARI-STEWARD")
        checks = {check["code"]: check for check in result["checks"]}

        self.assertEqual(result["status"], "human-handoff-required")
        self.assertEqual(result["agent_safe"], False)
        self.assertEqual(result["human_handoff_required"], True)
        self.assertEqual(result["human_action_boundary"]["agent_may_execute"], False)
        self.assertEqual(checks["HANDOFF"]["status"], "warn")
        self.assertEqual(checks["HUMAN_ACTION_BOUNDARY"]["status"], "warn")
        self.assertIn("agent handoff", result["recommended_commands"][0])

    def test_agent_doctor_prioritizes_missing_receipt_before_human_approval(self) -> None:
        workspace = self.modified_workspace(_remove_work_0001_exact_proof)

        result = build_agent_doctor(workspace, "WORK-0001", "PALARI-SOFIA")

        self.assertEqual(result["status"], "missing-proof")
        self.assertFalse(result["human_handoff_required"])
        self.assertIsNone(result["human_action_boundary"])
        self.assertIn("RECEIPT_PRESENT", result["summary"])
        self.assertTrue(result["recommended_commands"][0].startswith("palari receipt record "))

    def test_cli_agent_doctor_emits_json_shape(self) -> None:
        result = json.loads(
            self.run_cli("agent", "doctor", "WORK-0003", "--as", "PALARI-SOFIA", "--json").stdout
        )

        self.assertEqual(result["schema_version"], "palari.agent_doctor.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertIn("checks", result)
        self.assertIn("recommended_commands", result)

    def test_cli_agent_doctor_text_prints_summary(self) -> None:
        result = self.run_cli("agent", "doctor", "WORK-0003", "--as", "PALARI-SOFIA")

        self.assertIn("Agent doctor: DOCTOR-WORK-0003-PALARI-SOFIA-EXECUTE-V1", result.stdout)
        self.assertIn("Summary:", result.stdout)
        self.assertIn("Diagnosis:", result.stdout)

    def checks_by_code(self, result: dict[str, object]) -> dict[str, dict[str, object]]:
        return {check["code"]: check for check in result["checks"]}

    @contextmanager
    def git_workspace(self) -> Iterator[Path]:
        with self.temp_workspace_file(WORKSPACE) as workspace_file:
            root = workspace_file.parent
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "workspace"],
                check=True,
            )
            yield workspace_file

    def expire_git_lease(self, root: Path, claim: dict[str, object]) -> None:
        current = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", str(claim["git_lease_oid"])],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        record = json.loads(current.stdout)
        record["lease_expires_at"] = "2000-01-01T00:00:00Z"
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        expired = subprocess.run(
            ["git", "-C", str(root), "hash-object", "-w", "--stdin"],
            input=encoded,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "update-ref",
                str(claim["git_lease_ref"]),
                expired,
                str(claim["git_lease_oid"]),
            ],
            check=True,
        )
        local_claim_path = (
            root / ".palari" / "claims" / f"{claim['work_item']}.json"
        )
        local_claim = json.loads(local_claim_path.read_text(encoding="utf-8"))
        local_claim["lease_expires_at"] = "2000-01-01T00:00:00Z"
        local_claim_path.write_text(json.dumps(local_claim), encoding="utf-8")

    def modified_workspace(self, mutate: object) -> Workspace:
        source = json.loads((WORKSPACE / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        return Workspace.from_raw(source, WORKSPACE)

    def modified_dogfood_workspace(self, mutate: object) -> Workspace:
        source = json.loads((DOGFOOD / "workspace.json").read_text(encoding="utf-8"))
        mutate(source)
        return Workspace.from_raw(source, DOGFOOD)

    @contextmanager
    def temp_workspace_file(self, source_workspace: Path) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            workspace_root = Path(directory) / "workspace"
            shutil.copytree(
                source_workspace,
                workspace_root,
                ignore=shutil.ignore_patterns(".palari"),
            )
            yield workspace_root / "workspace.json"

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(WORKSPACE), *args],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def run_cli_in_workspace(
        self,
        workspace: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", "--workspace", str(workspace), *args],
            cwd=REPO_ROOT,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_checks import build_agent_check
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
from palari_company_os.agent_packets import _context_hash, build_agent_brief
from palari_company_os.agent_runtime import (
    ClaimContentionError,
    claim_integrity_error,
    release_agent,
    start_agent,
    start_next_agent,
)
from palari_company_os.store import WorkspaceStore, write_store
from palari_company_os.workspace import Workspace, WorkspaceError


WORK_ID = "WORK-PACKET"
OTHER_WORK_ID = "WORK-UNRELATED"
PALARI_ID = "PALARI-BUILDER"
OTHER_PALARI_ID = "PALARI-REVIEWER"
ALLOWED_PATH = "README.md"


def _workspace_data(*, include_unrelated: bool = False) -> dict[str, Any]:
    work_ids = [WORK_ID]
    reviewer_work: list[str] = []
    work_items = [
        {
            "id": WORK_ID,
            "title": "Produce the bounded packet output",
            "goal": "GOAL-PACKET",
            "palari": PALARI_ID,
            "risk": "R1",
            "intensity": "light",
            "required_approval_count": 0,
            "scope": "Change only the declared output.",
            "acceptance_target": "The declared output exists and is verified.",
            "status": "active",
            "allowed_resources": [ALLOWED_PATH],
            "allowed_sources": [],
            "output_targets": [ALLOWED_PATH],
            "forbidden_actions": ["deploy"],
            "verification_expectations": ["focused packet test passes"],
        }
    ]
    if include_unrelated:
        work_ids.append(OTHER_WORK_ID)
        reviewer_work.append(OTHER_WORK_ID)
        work_items.append(
            {
                "id": OTHER_WORK_ID,
                "title": "Unrelated private work",
                "goal": "GOAL-PACKET",
                "palari": OTHER_PALARI_ID,
                "risk": "R2",
                "intensity": "standard",
                "required_approval_count": 0,
                "scope": "Change an unrelated output.",
                "acceptance_target": "The unrelated output exists.",
                "status": "active",
                "allowed_resources": ["unrelated.txt"],
                "allowed_sources": [],
                "output_targets": ["unrelated.txt"],
                "forbidden_actions": [],
                "verification_expectations": ["unrelated check passes"],
            }
        )

    return {
        "schema_version": 2,
        "name": "Current Agent Packet Fixture",
        "goals": [
            {
                "id": "GOAL-PACKET",
                "title": "Exercise current packet boundaries",
                "status": "active",
                "linked_palaris": [PALARI_ID, OTHER_PALARI_ID],
                "linked_work": work_ids,
            }
        ],
        "humans": [{"id": "HUMAN-OWNER", "name": "Fixture Owner"}],
        "palaris": [
            {
                "id": PALARI_ID,
                "name": "Packet Builder",
                "role": "Bounded worker",
                "owner_human": "HUMAN-OWNER",
                "linked_goals": ["GOAL-PACKET"],
                "active_work": [WORK_ID],
            },
            {
                "id": OTHER_PALARI_ID,
                "name": "Independent Reviewer",
                "role": "Reviewer",
                "owner_human": "HUMAN-OWNER",
                "linked_goals": ["GOAL-PACKET"],
                "active_work": reviewer_work,
            },
        ],
        "sources": [],
        "workbenches": [],
        "playbook_sources": [],
        "capabilities": [],
        "authority_profiles": [],
        "integrations": [],
        "integration_plans": [],
        "integration_outbox": [],
        "decisions": [],
        "proposals": [],
        "work_items": work_items,
        "attempts": [],
        "evidence_runs": [],
        "review_verdicts": [],
        "human_decisions": [],
        "acceptance_records": [],
        "receipts": [],
        "outcomes": [],
    }


def _write_workspace(path: Path, *, include_unrelated: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_store(
        WorkspaceStore(
            data_path=path,
            data=_workspace_data(include_unrelated=include_unrelated),
        )
    )
    (path.parent / ALLOWED_PATH).write_text("fixture\n", encoding="utf-8")


def _checks(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["code"]): item for item in payload["checks"]}


class AgentPacketProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.workspace_file = self.root / "workspace.json"
        _write_workspace(self.workspace_file)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def workspace(self) -> Workspace:
        return Workspace.load(self.workspace_file)

    def test_execute_packet_projects_only_current_bounded_authority(self) -> None:
        packet = build_agent_brief(
            self.workspace(), WORK_ID, PALARI_ID, "execute"
        )

        self.assertEqual(packet["schema_version"], "palari.agent_packet.v1")
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["mode"], "execute")
        self.assertEqual(packet["allowed_paths"], {
            "read": [ALLOWED_PATH],
            "write": [ALLOWED_PATH],
        })
        self.assertEqual(packet["required_output"]["output_targets"], [ALLOWED_PATH])
        self.assertTrue(packet["completion_contract"]["requires_receipt"])
        self.assertTrue(packet["completion_contract"]["requires_evidence"])
        self.assertFalse(packet["completion_contract"]["requires_review"])
        self.assertFalse(packet["completion_contract"]["requires_human_decision"])
        self.assertEqual(packet["blockers"], [])
        self.assertTrue(packet["context_hash"].startswith("sha256:"))

    def test_packet_omits_unrelated_workspace_records(self) -> None:
        data = _workspace_data(include_unrelated=True)
        workspace = Workspace.from_raw(data, self.root)

        packet = build_agent_brief(workspace, WORK_ID, PALARI_ID, "execute")
        encoded = json.dumps(packet, sort_keys=True)

        self.assertNotIn(OTHER_WORK_ID, encoded)
        self.assertNotIn("Unrelated private work", encoded)
        self.assertEqual(packet["omitted_context"][0]["counts"]["work_items"], 2)

    def test_missing_or_unsupported_packet_authority_fails_closed(self) -> None:
        cases = (
            ("WORK-MISSING", PALARI_ID, "execute", "MISSING_WORK_ITEM"),
            (WORK_ID, "PALARI-MISSING", "execute", "MISSING_PALARI"),
            (WORK_ID, PALARI_ID, "audit", "UNSUPPORTED_MODE"),
        )
        for work_id, palari_id, mode, code in cases:
            with self.subTest(code=code):
                packet = build_agent_brief(
                    self.workspace(), work_id, palari_id, mode
                )
                self.assertEqual(packet["status"], "blocked")
                self.assertIn(code, {item["code"] for item in packet["blockers"]})

    def test_unassigned_actor_cannot_receive_execute_authority(self) -> None:
        packet = build_agent_brief(
            self.workspace(), WORK_ID, OTHER_PALARI_ID, "execute"
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "PALARI_NOT_ASSIGNED",
            {item["code"] for item in packet["blockers"]},
        )

    def test_review_packet_stays_blocked_until_reviewable_proof_exists(self) -> None:
        packet = build_agent_brief(
            self.workspace(), WORK_ID, OTHER_PALARI_ID, "review"
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn(
            "REVIEW_NOT_READY",
            {item["code"] for item in packet["blockers"]},
        )
        self.assertNotIn("review_context", packet)
        self.assertNotIn("human_action_boundary", packet)

    def test_context_hash_ignores_created_at_but_binds_authority(self) -> None:
        packet = build_agent_brief(
            self.workspace(), WORK_ID, PALARI_ID, "execute"
        )
        original = packet["context_hash"]

        packet["created_at"] = "2099-12-31T23:59:59Z"
        self.assertEqual(_context_hash(packet), original)
        packet["allowed_paths"]["write"] = ["different.txt"]
        self.assertNotEqual(_context_hash(packet), original)

    def test_agent_next_selects_only_the_safe_current_candidate(self) -> None:
        result = build_agent_next(self.workspace(), PALARI_ID)

        self.assertEqual(result["schema_version"], "palari.agent_next.v1")
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(result["blocked_count"], 0)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["work_item_id"], WORK_ID)
        self.assertTrue(candidate["can_start"])
        self.assertEqual(candidate["next_step_type"], "start-work")

    def test_agent_next_requires_a_declared_identity(self) -> None:
        result = build_agent_next(self.workspace(), "PALARI-MISSING")

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["blockers"][0]["code"], "MISSING_PALARI")

    def test_agent_next_all_is_a_thin_identity_rollup(self) -> None:
        result = build_agent_next_all(self.workspace())

        self.assertEqual(result["schema_version"], "palari.agent_next_all.v1")
        self.assertEqual(result["ready_count"], 1)
        self.assertEqual(len(result["agents"]), 2)
        self.assertEqual(result["top_candidate"]["agent"]["id"], PALARI_ID)
        self.assertEqual(
            result["top_candidate"]["candidate"]["work_item_id"], WORK_ID
        )

    def test_check_translates_packet_claim_and_file_boundaries(self) -> None:
        start_agent(self.workspace(), self.workspace_file, WORK_ID, PALARI_ID)

        inside = build_agent_check(
            self.workspace(),
            WORK_ID,
            PALARI_ID,
            changed_paths=[ALLOWED_PATH],
        )
        outside = build_agent_check(
            self.workspace(),
            WORK_ID,
            PALARI_ID,
            changed_paths=["outside.txt"],
        )

        self.assertEqual(_checks(inside)["CLAIM_OWNED"]["status"], "pass")
        self.assertEqual(
            _checks(inside)["FILE_CHANGES_WITHIN_WRITE_BOUNDARY"]["status"],
            "pass",
        )
        self.assertEqual(
            _checks(outside)["FILE_CHANGES_WITHIN_WRITE_BOUNDARY"]["status"],
            "fail",
        )
        self.assertEqual(outside["file_changes"]["outside_write_boundary"], ["outside.txt"])

    def test_finish_translates_missing_proof_without_mutating(self) -> None:
        result = build_agent_finish(self.workspace(), WORK_ID, PALARI_ID)

        self.assertEqual(result["schema_version"], "palari.agent_finish.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertFalse(result["would_mutate"])
        self.assertFalse(result["can_finish"])
        self.assertEqual(
            {item["code"] for item in result["missing_requirements"]},
            {"CLAIM_OWNED", "RECEIPT_PRESENT", "EVIDENCE_PRESENT"},
        )

    def test_handoff_does_not_invent_human_authority_before_proof(self) -> None:
        result = build_agent_handoff(self.workspace(), WORK_ID, PALARI_ID)

        self.assertEqual(result["schema_version"], "palari.agent_handoff.v1")
        self.assertFalse(result["would_mutate"])
        self.assertFalse(result["handoff_available"])
        self.assertEqual(result["handoff_types"], [])
        self.assertEqual(result["human_action_commands"], [])
        self.assertFalse(result["human_action_boundary"]["agent_may_execute"])

    def test_loop_composes_the_read_only_packet_check_and_finish_stages(self) -> None:
        result = build_agent_loop(self.workspace(), WORK_ID, PALARI_ID)

        self.assertEqual(result["schema_version"], "palari.agent_loop.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertFalse(result["would_mutate"])
        self.assertEqual(
            [stage["name"] for stage in result["stages"]],
            ["brief", "check", "finish"],
        )
        self.assertNotIn("handoff", result["commands"])

    def test_doctor_explains_the_existing_loop_without_new_policy(self) -> None:
        result = build_agent_doctor(self.workspace(), WORK_ID, PALARI_ID)

        self.assertEqual(result["schema_version"], "palari.agent_doctor.v1")
        self.assertEqual(result["status"], "missing-proof")
        self.assertTrue(result["agent_safe"])
        self.assertFalse(result["human_handoff_required"])
        self.assertIn("RECEIPT_PRESENT", result["summary"])
        self.assertEqual(
            {item["code"] for item in result["checks"]},
            {"PACKET", "CONTRACT", "FINISH"},
        )

    def test_cli_start_next_is_one_current_golden_path(self) -> None:
        result = self.run_cli(
            "agent", "start", "--next", "--as", PALARI_ID, "--json"
        )
        payload = json.loads(result.stdout)

        self.assertEqual(payload["entry"]["selected_work_item"], WORK_ID)
        self.assertTrue(payload["entry"]["safe"])
        self.assertEqual(payload["start"]["status"], "claimed")
        self.assertTrue(
            (self.root / payload["start"]["packet_path"]).is_file()
        )
        self.assertTrue(
            (self.root / payload["start"]["session_contract_path"]).is_file()
        )
        self.assertTrue((self.root / payload["start"]["claim_path"]).is_file())

    def test_start_next_skips_one_atomic_selection_contention(self) -> None:
        candidates = {
            "schema_version": "palari.agent_next.v1",
            "workspace": self.workspace().name,
            "agent": {"id": PALARI_ID},
            "candidates": [
                {"work_item_id": "WORK-RACED", "can_start": True, "queue_rank": 1},
                {"work_item_id": WORK_ID, "can_start": True, "queue_rank": 2},
            ],
            "next_allowed_commands": [],
        }
        claimed = {
            "start": {"status": "claimed", "claim": {"claim_session": "session"}},
            "one_sentence_instruction": "Do bounded work.",
        }

        with (
            patch("palari_company_os.agent_next.build_agent_next", return_value=candidates),
            patch(
                "palari_company_os.agent_runtime.start_agent",
                side_effect=[
                    ClaimContentionError(
                        "WORK-RACED", "work WORK-RACED was claimed concurrently"
                    ),
                    claimed,
                ],
            ),
        ):
            result = start_next_agent(
                self.workspace(), self.workspace_file, PALARI_ID
            )

        self.assertEqual(result["entry"]["selected_work_item"], WORK_ID)
        self.assertEqual(result["entry"]["selection_rank"], 2)
        self.assertEqual(
            result["entry"]["skipped_contention"][0]["work_item_id"],
            "WORK-RACED",
        )

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(self.workspace_file),
                *args,
            ],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )


class AgentClaimIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.workspace_file = self.root / "workspace.json"
        _write_workspace(self.workspace_file)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _start(self) -> dict[str, Any]:
        return start_agent(
            Workspace.load(self.workspace_file),
            self.workspace_file,
            WORK_ID,
            PALARI_ID,
        )

    def test_start_persists_one_exact_packet_claim_and_session_contract(self) -> None:
        result = self._start()
        claim = result["start"]["claim"]
        packet = json.loads(
            (self.root / claim["packet_path"]).read_text(encoding="utf-8")
        )
        contract = json.loads(
            (self.root / claim["session_contract_path"]).read_text(encoding="utf-8")
        )

        self.assertEqual(claim["schema_version"], "palari.agent_claim.v2")
        self.assertEqual(packet["context_hash"], claim["context_hash"])
        self.assertEqual(
            contract["contract_digest"], claim["session_contract_digest"]
        )
        self.assertFalse(contract["contract"]["packet_binding"]["grants_authority"])
        self.assertEqual(
            claim_integrity_error(self.workspace_file, WORK_ID, claim), ""
        )
        check = build_agent_check(
            Workspace.load(self.workspace_file), WORK_ID, PALARI_ID
        )
        self.assertEqual(_checks(check)["CLAIM_OWNED"]["status"], "pass")

    def test_restart_by_same_actor_reuses_the_claim_epoch(self) -> None:
        first = self._start()
        second = self._start()

        self.assertEqual(
            first["start"]["claim"]["claim_session"],
            second["start"]["claim"]["claim_session"],
        )
        self.assertEqual(
            first["start"]["claim"]["session_contract_digest"],
            second["start"]["claim"]["session_contract_digest"],
        )

    def test_tampered_persisted_packet_invalidates_the_claim(self) -> None:
        claim = self._start()["start"]["claim"]
        packet_path = self.root / claim["packet_path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["allowed_paths"]["write"] = ["outside.txt"]
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        error = claim_integrity_error(self.workspace_file, WORK_ID, claim)

        self.assertIn("packet", error.lower())
        self.assertIn("context_hash", error)

    def test_tampered_session_contract_invalidates_the_claim(self) -> None:
        claim = self._start()["start"]["claim"]
        contract_path = self.root / claim["session_contract_path"]
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["contract"]["scope"]["write_paths"] = ["outside.txt"]
        contract_path.write_text(json.dumps(contract), encoding="utf-8")

        error = claim_integrity_error(self.workspace_file, WORK_ID, claim)

        self.assertIn("session contract", error.lower())
        self.assertIn("contract_digest", error)

    def test_current_authority_change_stales_the_active_claim(self) -> None:
        self._start()
        changed_data = deepcopy(_workspace_data())
        changed_data["work_items"][0]["scope"] = "A different bounded scope."
        changed = Workspace.from_raw(changed_data, self.root)

        check = build_agent_check(changed, WORK_ID, PALARI_ID)

        owned = _checks(check)["CLAIM_OWNED"]
        self.assertEqual(owned["status"], "fail")
        self.assertIn("context hash differs", owned["message"])


class AgentGitBoundaryTests(unittest.TestCase):
    def test_current_git_witness_is_exact_and_missing_ref_fails_closed(self) -> None:
        with self.git_workspace() as (root, workspace_file):
            result = start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            claim = result["start"]["claim"]

            self.assertTrue(claim["git_witness_version"])
            self.assertTrue(claim["git_witness_ref"])
            self.assertEqual(
                claim_integrity_error(workspace_file, WORK_ID, claim), ""
            )

            self.git(root, "update-ref", "-d", claim["git_witness_ref"])
            error = claim_integrity_error(workspace_file, WORK_ID, claim)
            self.assertIn("witness", error.lower())
            self.assertIn("claim-start head", error.lower())

    def test_shared_git_lease_blocks_a_second_worktree_then_transfers(self) -> None:
        with self.git_workspace() as (root, workspace_file):
            linked = root.parent / "linked-worktree"
            self.git(root, "worktree", "add", "-b", "parallel", str(linked))
            linked_workspace = linked / "workspace.json"
            first_workspace = Workspace.load(workspace_file)

            first = start_agent(
                first_workspace, workspace_file, WORK_ID, PALARI_ID
            )
            with self.assertRaisesRegex(WorkspaceError, "another Git worktree"):
                start_agent(
                    Workspace.load(linked_workspace),
                    linked_workspace,
                    WORK_ID,
                    PALARI_ID,
                )

            release_agent(
                first_workspace, workspace_file, WORK_ID, PALARI_ID
            )
            transferred = start_agent(
                Workspace.load(linked_workspace),
                linked_workspace,
                WORK_ID,
                PALARI_ID,
            )
            self.assertEqual(transferred["start"]["status"], "claimed")
            self.assertNotEqual(
                transferred["start"]["claim"]["git_lease_oid"],
                first["start"]["claim"]["git_lease_oid"],
            )

    def test_isolated_start_wires_one_bounded_worktree_without_extra_authority(self) -> None:
        with self.git_workspace() as (_, workspace_file):
            result = start_isolated_agent(
                workspace_file, WORK_ID, PALARI_ID, lease_minutes=10
            )

            self.assertEqual(result["isolation"]["status"], "created")
            self.assertEqual(result["isolation"]["branch"], isolation_branch(WORK_ID))
            self.assertTrue(Path(result["isolation"]["worktree_path"]).is_dir())
            self.assertEqual(result["start"]["status"], "claimed")
            self.assertEqual(
                result["isolation"]["authority"],
                {
                    "merge": False,
                    "push": False,
                    "review": False,
                    "acceptance": False,
                    "external_writes": False,
                },
            )

    def test_git_integration_readiness_is_wiring_over_governance_state(self) -> None:
        with self.git_workspace() as (_, workspace_file):
            result = git_integration_readiness(
                workspace_file, WORK_ID, target_ref="main"
            )

            self.assertFalse(result["ready"])
            self.assertEqual(result["status"], "blocked")
            self.assertIn(
                "CANDIDATE_COMMIT_MISSING",
                {item["code"] for item in result["blockers"]},
            )
            self.assertFalse(result["governance"]["proof_ready"])

    @contextmanager
    def git_workspace(self) -> Iterator[tuple[Path, Path]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            workspace_file = root / "workspace.json"
            _write_workspace(workspace_file)
            self.git(root, "init", "-q", "-b", "main")
            self.git(root, "config", "user.name", "Packet Test")
            self.git(root, "config", "user.email", "packet-test@example.com")
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "current packet fixture")
            yield root, workspace_file

    @staticmethod
    def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()

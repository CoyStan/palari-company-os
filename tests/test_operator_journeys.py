from __future__ import annotations

import io
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_parking import park_agent
from palari_company_os.agent_runtime import read_claim, start_agent
from palari_company_os.cli import main as cli_main
from palari_company_os.cli_output_agent import print_agent_park
from palari_company_os.command_surface import palari_workspace_command
from palari_company_os.governance_journal import (
    checkpoint_workspace_journal,
    journal_file_path,
    verify_workspace_journal,
)
from palari_company_os.store import load_store, write_store
from palari_company_os.simple_approval import SimpleApprovalError, approve_work
from palari_company_os.verification_attestations import cache_key
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.test_approval_packs import InjectedCrash, crash_at, make_ready_workspace
from tests.workspace_fixture import write_current_agent_workspace


WORK_ID = "WORK-PARK"
PALARI_ID = "PALARI-STEWARD"
OTHER_PALARI_ID = "PALARI-ARCHITECT"
ALLOWED_PATH = "README.md"
REASON = "A product decision is required before this work can continue."
NEXT_ACTION = "Ask the owner to choose the final wording."
PROOF_COLLECTIONS = (
    "receipts",
    "evidence_runs",
    "review_verdicts",
    "human_decisions",
    "acceptance_records",
    "outcomes",
)


class OperatorJourneyTests(unittest.TestCase):
    """The interruption journey that is not covered by the CLI golden path."""

    def test_default_single_founder_r2_journey_reaches_terminal_from_emitted_actions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "founder-repo"
            root.mkdir()
            self.run_git(root, "init", "-q")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.run_git(root, "config", "user.name", "Test Founder")
            self.run_git(root, "commit", "--allow-empty", "-qm", "initial")

            initialized = self._run_cli_json("init", str(root), "--json")
            workspace_file = root / "workspace.json"
            workspace = Workspace.load(workspace_file)
            self.assertEqual([human.id for human in workspace.humans], ["HUMAN-FOUNDER"])
            self.assertEqual(
                [palari.id for palari in workspace.palaris],
                ["PALARI-CLAUDE", "PALARI-REVIEWER"],
            )
            self.assertEqual(initialized["workspace_file"], str(workspace_file))

            output_path = "artifacts/founder-result.txt"
            added = self._run_cli_json(
                "--workspace",
                str(workspace_file),
                "work",
                "add",
                "Prepare one reviewed founder result",
                "--create",
                output_path,
                "--risk",
                "R2",
                "--intensity",
                "standard",
                "--approvals",
                "0",
                "--acceptance",
                "The exact local result is reviewed and founder-approved.",
                "--verify",
                "Bounded deterministic checks pass.",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            self.assertEqual(added["authority_plan"]["effective_final_approval_count"], 1)
            self.assertEqual(added["authority_plan"]["qualified_approver_ids"], ["HUMAN-FOUNDER"])

            started = self._run_emitted_json(added["next_commands"][0])
            self.assertEqual(started["start"]["status"], "claimed")
            self.assertEqual(started["entry"]["selected_work_item"], work_id)

            output = root / output_path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("exact founder-reviewed bytes\n", encoding="utf-8")
            checked = self._run_cli_json(
                "--workspace",
                str(workspace_file),
                "agent",
                "check",
                work_id,
                "--as",
                "PALARI-CLAUDE",
                "--mode",
                "execute",
                "--changed",
                output_path,
                "--json",
            )
            boundary_checks = {
                str(item["code"]): item for item in checked["checks"]
            }
            for code in (
                "PACKET_READY",
                "PALARI_ALLOWED",
                "DEPENDENCIES_CLEAR",
                "SOURCES_ALLOWED",
                "NO_UNAPPROVED_EXTERNAL_WRITE",
                "VALIDATE_WORKSPACE",
                "CLAIM_OWNED",
                "FILE_CHANGES_WITHIN_WRITE_BOUNDARY",
                "REQUIRED_OUTPUT_EXISTS",
            ):
                self.assertNotEqual(
                    boundary_checks[code]["status"],
                    "fail",
                    msg=f"{code}: {boundary_checks[code]}",
                )
            self.assertFalse(checked["ok"])
            self.assertEqual(
                boundary_checks["FILE_CHANGES_RECORDED"]["status"],
                "fail",
            )

            self.run_git(root, "add", "--", output_path)
            self.run_git(root, "commit", "-qm", "add bounded founder result")

            observed_profiles: list[str] = []

            def passing_attestation(
                _workspace: object,
                _repo_root: object,
                profile: Any,
                context: Any,
                **_kwargs: object,
            ) -> dict[str, Any]:
                observed_profiles.append(str(profile.id))
                key = cache_key(profile, context)
                return {
                    "cache_hit": False,
                    "attestation": {
                        "attestation_id": (
                            f"VERIFY-{profile.id.upper()}-{key[-16:].upper()}"
                        ),
                        "cache_key": key,
                        "status": "passed",
                        "duration_ms": 1,
                        "stdout_digest": "sha256:" + "1" * 64,
                        "stderr_digest": "sha256:" + "2" * 64,
                    },
                }

            with patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=passing_attestation,
            ):
                advanced = self._run_emitted_json(started["entry"]["next_command"])

            self.assertEqual(
                observed_profiles,
                ["complete", "install-smoke", "docs-check"],
            )
            self.assertEqual(advanced["status"], "review-required")
            review_actions = [
                action
                for action in advanced["handoff"]["agent_action_commands"]
                if action["actor"] == "PALARI-REVIEWER"
            ]
            accept_action = next(
                action
                for action in review_actions
                if "--verdict accept-ready" in action["command"]
            )
            reviewer_packet = self._run_emitted_json(
                accept_action["packet_command"]
            )
            concrete_review = next(
                item["command"]
                for item in reviewer_packet["review_context"][
                    "agent_review_commands"
                ]
                if item["reviewer"] == "PALARI-REVIEWER"
                and item["verdict"] == "accept-ready"
            )
            review_result = self._run_emitted_json(concrete_review)
            self.assertEqual(review_result["action"], "created")
            self.assertEqual(review_result["collection"], "review_verdicts")

            reviewer_handoff = self._run_emitted_json(
                palari_workspace_command(
                    workspace_file,
                    "agent",
                    "handoff",
                    work_id,
                    "--as",
                    "PALARI-REVIEWER",
                    "--mode",
                    "review",
                    "--json",
                )
            )
            human_actions = reviewer_handoff["human_action_commands"]
            self.assertEqual(len(human_actions), 1)
            human_action = human_actions[0]
            self.assertEqual(human_action["actor"], "HUMAN-FOUNDER")
            self.assertIn("--presented", human_action["command"])
            self.assertNotIn("--pack-digest", human_action["command"])

            approved = self._run_emitted_json(human_action["command"])
            final = Workspace.load(workspace_file)
            journal = verify_workspace_journal(workspace_file)
            work = final.work_item(work_id)

            self.assertTrue(approved["completed"])
            self.assertFalse(approved["performed_external_effects"])
            self.assertIsNotNone(work)
            self.assertEqual(work.status, "completed")
            self.assertEqual(len(final.review_verdicts), 1)
            self.assertEqual(len(final.human_decisions), 1)
            self.assertEqual(len(final.acceptance_records), 1)
            self.assertEqual(final.attempts[0].actor, "PALARI-CLAUDE")
            self.assertEqual(
                final.review_verdicts[0].reviewer,
                "PALARI-REVIEWER",
            )
            self.assertEqual(final.human_decisions[0].human_id, "HUMAN-FOUNDER")
            self.assertTrue(journal["chain_valid"])
            self.assertIsNone(journal["pending"])

    def test_simple_approval_completes_only_the_selected_local_task_and_retries(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = make_ready_workspace(
                Path(directory),
                count=2,
                distinct_outputs=True,
            )

            result = approve_work(
                str(workspace_file),
                "WORK-001",
                "HUMAN-PRODUCT",
                reason="The exact local output is accepted.",
            )
            replay = approve_work(
                str(workspace_file),
                "WORK-001",
                "HUMAN-PRODUCT",
            )
            final = load_store(workspace_file)
            journal = verify_workspace_journal(workspace_file)
            statuses = {
                item["id"]: item["status"] for item in final.data["work_items"]
            }

        self.assertTrue(result["approved"])
        self.assertTrue(result["completed"])
        self.assertFalse(result["idempotent"])
        self.assertFalse(result["performed_external_effects"])
        self.assertTrue(replay["idempotent"])
        self.assertEqual(statuses["WORK-001"], "completed")
        self.assertEqual(statuses["WORK-002"], "in-review")
        self.assertEqual(len(final.data["human_decisions"]), 1)
        self.assertEqual(len(final.data["acceptance_records"]), 1)
        self.assertTrue(journal["chain_valid"])
        self.assertIsNone(journal["pending"])

    def test_simple_approval_rejects_unqualified_and_reviewer_callers_without_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = make_ready_workspace(Path(directory), count=1)
            before = workspace_file.read_bytes()
            history_before = journal_file_path(workspace_file).read_bytes()

            with self.assertRaises(SimpleApprovalError) as unqualified:
                approve_work(
                    str(workspace_file),
                    "WORK-001",
                    "HUMAN-UNQUALIFIED",
                )

            self.assertEqual(
                unqualified.exception.code,
                "APPROVAL_HUMAN_UNQUALIFIED",
            )
            self.assertEqual(workspace_file.read_bytes(), before)
            self.assertEqual(journal_file_path(workspace_file).read_bytes(), history_before)

            store = load_store(workspace_file)
            reviewer = next(
                item
                for item in store.data["humans"]
                if item["id"] == "HUMAN-REVIEW"
            )
            reviewer["approval_capabilities"] = ["product"]
            write_store(store)
            before_collision = workspace_file.read_bytes()
            history_before_collision = journal_file_path(workspace_file).read_bytes()

            with self.assertRaises(SimpleApprovalError) as collision:
                approve_work(
                    str(workspace_file),
                    "WORK-001",
                    "HUMAN-REVIEW",
                )

            self.assertEqual(
                collision.exception.code,
                "APPROVAL_IDENTITY_COLLISION",
            )
            self.assertEqual(workspace_file.read_bytes(), before_collision)
            self.assertEqual(
                journal_file_path(workspace_file).read_bytes(),
                history_before_collision,
            )

    def test_simple_approval_rejects_nonbatchable_external_and_incomplete_quorum(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            elevated = make_ready_workspace(
                Path(directory) / "elevated",
                count=1,
                risk="R3",
            )
            elevated_before = elevated.read_bytes()
            with self.assertRaises(SimpleApprovalError) as nonbatchable:
                approve_work(str(elevated), "WORK-001", "HUMAN-PRODUCT")
            self.assertEqual(
                nonbatchable.exception.code,
                "APPROVAL_NON_BATCHABLE",
            )
            self.assertEqual(elevated.read_bytes(), elevated_before)

            external = make_ready_workspace(
                Path(directory) / "external",
                count=1,
            )
            external_store = load_store(external)
            external_store.data["work_items"][0]["allowed_actions"] = [
                "external_write"
            ]
            write_store(external_store)
            external_before = external.read_bytes()
            with self.assertRaises(SimpleApprovalError) as external_action:
                approve_work(str(external), "WORK-001", "HUMAN-PRODUCT")
            self.assertEqual(
                external_action.exception.code,
                "APPROVAL_EXTERNAL_ACTION",
            )
            self.assertEqual(external.read_bytes(), external_before)

            quorum = make_ready_workspace(
                Path(directory) / "quorum",
                count=1,
                approvals=2,
            )
            quorum_before = quorum.read_bytes()
            with self.assertRaises(SimpleApprovalError) as incomplete:
                approve_work(str(quorum), "WORK-001", "HUMAN-PRODUCT")
            self.assertEqual(
                incomplete.exception.code,
                "APPROVAL_QUORUM_INCOMPLETE",
            )
            self.assertEqual(quorum.read_bytes(), quorum_before)
            self.assertEqual(load_store(quorum).data["human_decisions"], [])

    def test_simple_approval_fails_closed_for_history_proof_and_state_drift(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid_history = make_ready_workspace(
                Path(directory) / "history",
                count=1,
            )
            raw = json.loads(invalid_history.read_text(encoding="utf-8"))
            raw["name"] = "Unjournaled drift"
            invalid_history.write_text(
                json.dumps(raw, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(SimpleApprovalError) as history_error:
                approve_work(
                    str(invalid_history),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                )
            self.assertEqual(
                history_error.exception.code,
                "APPROVAL_HISTORY_INVALID",
            )

            invalid_proof = make_ready_workspace(
                Path(directory) / "proof",
                count=1,
            )
            (invalid_proof.parent / "artifacts/overnight-result.txt").write_text(
                "changed after exact checks\n",
                encoding="utf-8",
            )
            proof_before = invalid_proof.read_bytes()
            with self.assertRaises(SimpleApprovalError) as proof_error:
                approve_work(
                    str(invalid_proof),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                )
            self.assertEqual(
                proof_error.exception.code,
                "APPROVAL_PROOF_INVALID",
            )
            self.assertEqual(invalid_proof.read_bytes(), proof_before)

            drift = make_ready_workspace(
                Path(directory) / "drift",
                count=1,
            )

            def change_presented_artifact() -> None:
                (drift.parent / "artifacts/overnight-result.txt").write_text(
                    "changed between presentation and apply\n",
                    encoding="utf-8",
                )

            drift_before = drift.read_bytes()
            with self.assertRaises(SimpleApprovalError) as drift_error:
                approve_work(
                    str(drift),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                    _before_apply=change_presented_artifact,
                )
            self.assertEqual(
                drift_error.exception.code,
                "APPROVAL_STATE_CHANGED",
            )
            self.assertEqual(drift.read_bytes(), drift_before)
            self.assertEqual(load_store(drift).data["human_decisions"], [])

    def test_interrupted_simple_approval_recovers_without_duplicate_authority(
        self,
    ) -> None:
        for point in ("after_prepare_fsync", "after_apply", "after_commit_fsync"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                workspace_file = make_ready_workspace(Path(directory), count=1)
                with self.assertRaisesRegex(InjectedCrash, point):
                    approve_work(
                        str(workspace_file),
                        "WORK-001",
                        "HUMAN-PRODUCT",
                        reason="Crash-safe singleton approval.",
                        crash_hook=crash_at(point),
                    )

                replay = approve_work(
                    str(workspace_file),
                    "WORK-001",
                    "HUMAN-PRODUCT",
                )
                final = load_store(workspace_file)
                journal = verify_workspace_journal(workspace_file)

                self.assertTrue(replay["idempotent"])
                self.assertTrue(replay["completed"])
                self.assertEqual(len(final.data["human_decisions"]), 1)
                self.assertEqual(len(final.data["acceptance_records"]), 1)
                self.assertTrue(journal["chain_valid"])
                self.assertIsNone(journal["pending"])

    def test_park_records_one_blocked_attempt_releases_and_creates_no_proof(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            started = start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            claimed_packet = started["start"]["claim"]
            (root / ALLOWED_PATH).write_text("unfinished bounded edit\n", encoding="utf-8")
            (root / "outside-scope.txt").write_text(
                "must remain visible while parked\n",
                encoding="utf-8",
            )
            before = json.loads(workspace_file.read_text(encoding="utf-8"))
            proof_counts = {
                key: len(before.get(key, [])) for key in PROOF_COLLECTIONS
            }

            result = park_agent(
                workspace_file,
                WORK_ID,
                PALARI_ID,
                reason=REASON,
                next_action=NEXT_ACTION,
            )

            self.assertEqual(result["schema_version"], "palari.agent_parking.v1")
            self.assertEqual(result["status"], "parked")
            self.assertTrue(result["claim_released"])
            self.assertFalse(result["resumed"])
            self.assertEqual(result["reason"], REASON)
            self.assertEqual(result["next_action"], NEXT_ACTION)
            binding = result["packet_head_digest_changes"]
            self.assertEqual(binding["packet"]["packet_id"], claimed_packet["packet_id"])
            self.assertEqual(
                binding["packet"]["context_hash"], claimed_packet["context_hash"]
            )
            self.assertTrue(binding["packet"]["packet_digest"].startswith("sha256:"))
            self.assertIn(ALLOWED_PATH, binding["observation"]["inside_write_boundary"])
            self.assertIn(
                "outside-scope.txt",
                binding["observation"]["outside_write_boundary"],
            )

            after = json.loads(workspace_file.read_text(encoding="utf-8"))
            work = next(item for item in after["work_items"] if item["id"] == WORK_ID)
            attempt = next(
                item for item in after["attempts"] if item["id"] == result["attempt_id"]
            )
            self.assertEqual(work["status"], "blocked")
            self.assertEqual(work["current_attempt"], attempt["id"])
            self.assertEqual(attempt["status"], "blocked")
            self.assertEqual(attempt["changed_files"], [ALLOWED_PATH])
            parking = json.loads(attempt["result"])
            self.assertEqual(parking["schema_version"], "palari.agent_parking_record.v1")
            self.assertEqual(
                parking["authority_non_claims"],
                [
                    "no-receipt",
                    "no-evidence",
                    "no-review",
                    "no-human-decision",
                    "no-acceptance",
                    "no-outcome",
                    "no-convergence",
                ],
            )
            self.assertIsNone(read_claim(workspace_file, WORK_ID))
            self.assertEqual(
                {key: len(after.get(key, [])) for key in PROOF_COLLECTIONS},
                proof_counts,
            )
            journal = verify_workspace_journal(workspace_file)
            self.assertTrue(journal["chain_valid"])
            self.assertEqual(
                journal["current_workspace_digest"],
                binding["workspace_digest_after"],
            )

            output = io.StringIO()
            with redirect_stdout(output):
                print_agent_park(result, False)
            self.assertEqual(
                output.getvalue().splitlines(),
                [
                    f"Task: {WORK_ID} [Blocked]",
                    f"Owner: {PALARI_ID}",
                    f"Reason: {REASON}",
                    f"Next: {NEXT_ACTION}",
                    "Task lock released: yes",
                ],
            )
            self.assertNotIn("sha256:", output.getvalue())

    def test_retry_after_durable_write_releases_once_without_rewriting_history(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            (root / ALLOWED_PATH).write_text("unfinished bounded edit\n", encoding="utf-8")

            def interrupt(_payload: dict[str, object]) -> None:
                raise RuntimeError("simulated interruption before claim release")

            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                    _after_persist=interrupt,
                )

            persisted = json.loads(workspace_file.read_text(encoding="utf-8"))
            self.assertEqual(self._parking_attempt_count(persisted), 1)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))
            journal_path = journal_file_path(workspace_file)
            journal_before_retry = journal_path.read_bytes()

            result = park_agent(
                workspace_file,
                WORK_ID,
                PALARI_ID,
                reason=REASON,
                next_action=NEXT_ACTION,
            )

            self.assertTrue(result["resumed"])
            self.assertTrue(result["claim_released"])
            self.assertIsNone(read_claim(workspace_file, WORK_ID))
            self.assertEqual(journal_path.read_bytes(), journal_before_retry)
            after = json.loads(workspace_file.read_text(encoding="utf-8"))
            self.assertEqual(self._parking_attempt_count(after), 1)

    def test_parking_requires_an_owned_claim_and_current_journal(self) -> None:
        with self.git_workspace() as workspace_file:
            workspace = Workspace.load(workspace_file)
            start_agent(workspace, workspace_file, WORK_ID, PALARI_ID)
            workspace_before = workspace_file.read_bytes()

            with self.assertRaisesRegex(
                WorkspaceError, f"claim belongs to {PALARI_ID}"
            ):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    OTHER_PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(workspace_file.read_bytes(), workspace_before)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))

        with self.git_workspace() as workspace_file:
            with self.assertRaisesRegex(WorkspaceError, "no claim exists"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(Workspace.load(workspace_file).work_item(WORK_ID).status, "active")

        with self.git_workspace(journal=False) as workspace_file:
            start_agent(
                Workspace.load(workspace_file), workspace_file, WORK_ID, PALARI_ID
            )
            before = workspace_file.read_bytes()
            with self.assertRaisesRegex(
                WorkspaceError,
                "history --checkpoint.*Activate journal",
            ):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(workspace_file.read_bytes(), before)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))

    @staticmethod
    def _parking_attempt_count(data: dict[str, object]) -> int:
        attempts = data.get("attempts")
        assert isinstance(attempts, list)
        return len(
            [
                item
                for item in attempts
                if isinstance(item, dict)
                and str(item.get("id") or "").startswith("ATTEMPT-PARK-")
            ]
        )

    @contextmanager
    def git_workspace(self, *, journal: bool = True) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            root.mkdir()
            workspace_file = root / "workspace.json"
            write_current_agent_workspace(workspace_file)
            store = load_store(workspace_file)
            store.data["work_items"] = [
                {
                    "id": WORK_ID,
                    "title": "Park one interrupted bounded change",
                    "goal": "GOAL-REPO-0001",
                    "palari": PALARI_ID,
                    "risk": "R2",
                    "intensity": "standard",
                    "required_approval_count": 0,
                    "scope": "Modify only the declared artifact.",
                    "acceptance_target": "The interruption is durable and auditable.",
                    "status": "active",
                    "allowed_resources": [ALLOWED_PATH],
                    "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                    "output_targets": [ALLOWED_PATH],
                    "path_intents": [{"path": ALLOWED_PATH, "intent": "modify"}],
                    "forbidden_actions": ["deploy"],
                    "verification_expectations": ["focused parking journey passes"],
                }
            ]
            for palari in store.data["palaris"]:
                if palari["id"] == PALARI_ID:
                    palari["active_work"] = [WORK_ID]
            write_store(store)
            shutil.rmtree(root / ".palari", ignore_errors=True)
            (root / ALLOWED_PATH).write_text("initial copy\n", encoding="utf-8")

            self.run_git(root, "init", "-q")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.run_git(root, "config", "user.name", "Test")
            self.run_git(root, "add", "-A")
            self.run_git(root, "commit", "-qm", "current fixture")
            if journal:
                checkpoint_workspace_journal(
                    workspace_file,
                    PALARI_ID,
                    reason="Activate current journal for the parking journey.",
                )
            yield workspace_file

    @staticmethod
    def run_git(root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _run_emitted_json(self, command: str) -> dict[str, Any]:
        arguments = shlex.split(command)
        self.assertTrue(arguments)
        self.assertEqual(arguments[0], "palari")
        return self._run_cli_json(*arguments[1:])

    def _run_cli_json(self, *arguments: str) -> dict[str, Any]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli_main(list(arguments))
        self.assertEqual(
            exit_code,
            0,
            msg=f"CLI failed: {' '.join(arguments)}\n{stderr.getvalue()}\n{stdout.getvalue()}",
        )
        try:
            payload = json.loads(stdout.getvalue())
        except json.JSONDecodeError as exc:
            self.fail(
                f"CLI did not emit JSON for {' '.join(arguments)}: {exc}\n"
                f"{stdout.getvalue()}"
            )
        self.assertIsInstance(payload, dict)
        return payload


if __name__ == "__main__":
    unittest.main()

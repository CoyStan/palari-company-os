from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_parking import park_agent
from palari_company_os.agent_runtime import read_claim, start_agent
from palari_company_os.governance_journal import (
    checkpoint_workspace_journal,
    verify_workspace_journal,
)
from palari_company_os.onramp import initialize_starter_workspace, quick_add_work
from palari_company_os.workspace import Workspace, WorkspaceError


SOURCE_WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"
WORK_ID = "WORK-0003"
PALARI_ID = "PALARI-SOFIA"
REASON = "A product decision is required before this work can continue."
NEXT_ACTION = "Ask the founder to choose the final onboarding wording."
PROOF_COLLECTIONS = (
    "receipts",
    "evidence_runs",
    "review_verdicts",
    "human_decisions",
    "acceptance_records",
    "outcomes",
)


class OperatorJourneyTests(unittest.TestCase):
    def test_fresh_committed_repo_runs_init_start_and_advance_without_proof_ids(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            self.run_git(root, "init", "-q")
            self.run_git(root, "config", "user.name", "Test")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.write_verification_profile(root)
            self.run_git(root, "add", "scripts/verification_profiles.py")
            self.run_git(root, "commit", "-qm", "initial")

            initialized = self.run_project_cli(
                root,
                "init",
                "--palari",
                "Agent",
                "--json",
            )
            init_payload = json.loads(initialized.stdout)
            self.assertEqual(init_payload["authority_anchor"]["status"], "anchored")
            self.assertEqual(init_payload["agent_docs"]["status"], "ready")

            added = self.run_project_cli(
                root,
                "work",
                "add",
                "Write the launch note",
                "--write",
                "docs/notes.md",
                "--json",
            )
            work_id = json.loads(added.stdout)["work_item"]["id"]
            started = self.run_project_cli(
                root,
                "agent",
                "start",
                "--next",
                "--as",
                "PALARI-AGENT",
                "--json",
            )
            start_payload = json.loads(started.stdout)
            self.assertEqual(start_payload["start"]["status"], "claimed")
            self.assertEqual(start_payload["work_item"]["id"], work_id)
            self.assertEqual(start_payload["documentation_state"]["status"], "ready")

            output = root / "docs" / "notes.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("Bounded launch note.\n", encoding="utf-8")
            self.run_git(root, "add", "docs/notes.md")
            self.run_git(
                root,
                "commit",
                "--only",
                "-qm",
                "bounded launch note",
                "--",
                "docs/notes.md",
            )

            advanced = self.run_project_cli(
                root,
                "agent",
                "advance",
                work_id,
                "--as",
                "PALARI-AGENT",
                "--json",
            )
            advance_payload = json.loads(advanced.stdout)
            self.assertEqual(advance_payload["status"], "completed")
            self.assertNotIn("RECEIPT-ID", advanced.stdout)
            self.assertNotIn("EVIDENCE-ID", advanced.stdout)
            docs_payload = json.loads(
                self.run_project_cli(root, "docs", "check", "--json").stdout
            )
            self.assertEqual(docs_payload["documentation_state"]["status"], "ready")
            self.assertEqual(
                docs_payload["documentation_state"]["canonical_docs_missing"],
                [],
            )

    def test_unanchored_manual_workspace_fails_with_one_exact_recovery_action(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            initialize_starter_workspace(root, palari_name="Agent")
            quick_add_work(
                root,
                "Write the launch note",
                write=["docs/notes.md"],
            )
            self.run_git(root, "init", "-q")
            self.run_git(root, "config", "user.name", "Test")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.write_verification_profile(root)
            self.run_git(root, "add", "scripts/verification_profiles.py")
            self.run_git(root, "commit", "-qm", "initial")

            result = self.run_project_cli(
                root,
                "agent",
                "start",
                "--next",
                "--as",
                "PALARI-AGENT",
                "--json",
                check=False,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                payload["error"]["code"],
                "IMMUTABLE_SCOPE_AUTHORITY_WORKSPACE_GIT_BLOB",
            )
            message = payload["error"]["message"]
            self.assertIn("next action: git -C", message)
            self.assertIn("add -f --", message)
            self.assertIn("commit --only", message)
            self.assertEqual(message.count("next action:"), 1)

    def test_durable_release_cli_is_concise_by_default_and_exact_in_json(self) -> None:
        with self.git_workspace() as workspace_file:
            start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                WORK_ID,
                PALARI_ID,
            )
            result = self.run_cli(
                workspace_file,
                "agent",
                "release",
                WORK_ID,
                "--as",
                PALARI_ID,
                "--reason",
                REASON,
                "--next-action",
                NEXT_ACTION,
            )

            self.assertEqual(
                result.stdout.splitlines(),
                [
                    f"Work: {WORK_ID} [blocked]",
                    f"Owner: {PALARI_ID}",
                    f"Reason: {REASON}",
                    f"Next: {NEXT_ACTION}",
                    "Claim released: yes",
                ],
            )
            self.assertNotIn("sha256:", result.stdout)

        with self.git_workspace() as workspace_file:
            start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                WORK_ID,
                PALARI_ID,
            )
            result = self.run_cli(
                workspace_file,
                "agent",
                "release",
                WORK_ID,
                "--as",
                PALARI_ID,
                "--reason",
                REASON,
                "--next-action",
                NEXT_ACTION,
                "--json",
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload["status"], "parked")
            binding = payload["packet_head_digest_changes"]
            self.assertTrue(binding["packet"]["packet_digest"].startswith("sha256:"))
            self.assertTrue(binding["head_sha"])
            self.assertTrue(binding["workspace_digest_after"].startswith("sha256:"))
            self.assertIn("observation", binding)

    def test_park_durably_records_blocker_then_releases_without_proof(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            started = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                WORK_ID,
                PALARI_ID,
            )
            claimed_packet = started["start"]["claim"]
            (root / "docs/product/company-os.md").write_text(
                "unfinished bounded edit\n",
                encoding="utf-8",
            )
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
                binding["packet"]["context_hash"],
                claimed_packet["context_hash"],
            )
            self.assertTrue(binding["packet"]["packet_digest"].startswith("sha256:"))
            self.assertTrue(binding["head_sha"])
            self.assertTrue(binding["workspace_digest_before"].startswith("sha256:"))
            self.assertTrue(binding["workspace_digest_after"].startswith("sha256:"))
            self.assertIn(
                "docs/product/company-os.md",
                binding["observation"]["inside_write_boundary"],
            )
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
            self.assertEqual(attempt["changed_files"], ["docs/product/company-os.md"])
            parking = json.loads(attempt["result"])
            self.assertEqual(parking["schema_version"], "palari.agent_parking_record.v1")
            self.assertEqual(parking["reason"], REASON)
            self.assertEqual(parking["next_action"], NEXT_ACTION)
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

    def test_park_retry_after_persist_before_release_is_exact_and_idempotent(self) -> None:
        with self.git_workspace() as workspace_file:
            root = workspace_file.parent
            start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                WORK_ID,
                PALARI_ID,
            )
            (root / "docs/product/company-os.md").write_text(
                "unfinished bounded edit\n",
                encoding="utf-8",
            )

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
            parked_attempts = [
                item
                for item in persisted["attempts"]
                if item["id"].startswith("ATTEMPT-PARK-")
            ]
            self.assertEqual(len(parked_attempts), 1)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))
            journal_path = root / ".palari/governance-journal.v1.jsonl"
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
            self.assertEqual(
                len(
                    [
                        item
                        for item in after["attempts"]
                        if item["id"].startswith("ATTEMPT-PARK-")
                    ]
                ),
                1,
            )

    def test_park_fails_closed_for_foreign_malformed_and_missing_claims(self) -> None:
        with self.git_workspace() as workspace_file:
            workspace = Workspace.load(workspace_file)
            start_agent(workspace, workspace_file, WORK_ID, PALARI_ID)
            workspace_before = workspace_file.read_bytes()

            with self.assertRaisesRegex(WorkspaceError, "claim belongs to PALARI-SOFIA"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    "PALARI-ALFRED",
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(workspace_file.read_bytes(), workspace_before)
            self.assertIsNotNone(read_claim(workspace_file, WORK_ID))

            claim_path = workspace_file.parent / ".palari/claims" / f"{WORK_ID}.json"
            claim_path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(WorkspaceError, "invalid claim JSON"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            self.assertEqual(workspace_file.read_bytes(), workspace_before)

        with self.git_workspace() as workspace_file:
            with self.assertRaisesRegex(WorkspaceError, "no claim exists"):
                park_agent(
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                    reason=REASON,
                    next_action=NEXT_ACTION,
                )
            workspace = Workspace.load(workspace_file)
            self.assertEqual(workspace.work_item(WORK_ID).status, "active")

    def test_park_requires_explicit_legacy_journal_activation(self) -> None:
        with self.git_workspace(journal=False) as workspace_file:
            start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                WORK_ID,
                PALARI_ID,
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

    @contextmanager
    def git_workspace(self, *, journal: bool = True) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            shutil.copytree(
                SOURCE_WORKSPACE,
                root,
                ignore=shutil.ignore_patterns(".palari"),
            )
            output = root / "docs/product/company-os.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("initial copy\n", encoding="utf-8")
            self.run_git(root, "init", "-q")
            self.run_git(root, "config", "user.email", "test@example.com")
            self.run_git(root, "config", "user.name", "Test")
            self.run_git(root, "add", "-A")
            self.run_git(root, "commit", "-qm", "workspace")
            workspace_file = root / "workspace.json"
            if journal:
                checkpoint_workspace_journal(
                    workspace_file,
                    PALARI_ID,
                    reason="Activate journal for parking test.",
                )
            yield workspace_file

    def run_git(self, root: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_cli(
        self,
        workspace_file: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(workspace_file),
                *args,
            ],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def run_project_cli(
        self,
        root: Path,
        *args: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", *args],
            cwd=root,
            env=env,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def write_verification_profile(self, root: Path) -> None:
        script = root / "scripts" / "verification_profiles.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            """from pathlib import Path
import sys

if len(sys.argv) < 3 or sys.argv[1] != "affected":
    raise SystemExit(2)
if any(not Path(path).is_file() for path in sys.argv[2:]):
    raise SystemExit(1)
""",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()

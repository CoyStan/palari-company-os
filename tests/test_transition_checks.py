from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.transition_checks import check_transition
from palari_company_os.workspace import Workspace


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class TransitionCheckTests(unittest.TestCase):
    def test_work_accept_transition_is_the_hard_acceptance_choke_point(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        ready = check_transition(
            workspace,
            "work_accept",
            "WORK-0001",
            actor="HUMAN-FOUNDER",
            context={"reviewed_head": "abc1234"},
        )
        unqualified = check_transition(
            workspace,
            "work_accept",
            "WORK-0001",
            actor="HUMAN-OPS",
            context={"reviewed_head": "abc1234"},
        )

        self.assertTrue(ready.ok)
        self.assertEqual(ready.to_dict()["schema_version"], "palari.transition_check.v1")
        self.assertFalse(unqualified.ok)
        self.assertEqual(unqualified.blockers[0].code, "HUMAN_LACKS_CAPABILITY")

    def test_review_record_transition_blocks_accept_ready_without_evidence(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = check_transition(
            workspace,
            "review_record",
            "REVIEW-NO-EVIDENCE",
            actor="HUMAN-OPS",
            context={
                "work_item_id": "WORK-0003",
                "reviewed_head": "def5678",
                "verdict": "accept-ready",
            },
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.blockers[0].code, "FRESH_EVIDENCE_MISSING")
        self.assertIn("palari evidence record", result.blockers[0].next_command)

    def test_evidence_record_transition_blocks_wrong_attempt_head(self) -> None:
        workspace = Workspace.load(WORKSPACE)

        result = check_transition(
            workspace,
            "evidence_record",
            "EVIDENCE-WRONG-HEAD",
            context={
                "work_item_id": "WORK-0001",
                "attempt_id": "ATTEMPT-0001",
                "head_sha": "wrong-head",
            },
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.blockers[0].code, "EVIDENCE_STALE_HEAD")

    def test_cli_review_record_uses_transition_gate(self) -> None:
        with self.temp_workspace() as workspace:
            result = self.run_cli(
                workspace,
                "review",
                "record",
                "REVIEW-NO-EVIDENCE",
                "--work-item-id",
                "WORK-0003",
                "--reviewed-head",
                "def5678",
                "--reviewer",
                "HUMAN-OPS",
                "--verdict",
                "accept-ready",
                "--json",
                check=False,
            )
            data = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accept-ready review requires passed evidence", result.stderr)
        self.assertNotIn("REVIEW-NO-EVIDENCE", json.dumps(data["review_verdicts"]))

    def test_cli_review_update_cannot_bypass_transition_gate(self) -> None:
        with self.temp_workspace() as workspace:
            self.run_cli(
                workspace,
                "review",
                "record",
                "REVIEW-CHANGES-FIRST",
                "--work-item-id",
                "WORK-0003",
                "--reviewed-head",
                "def5678",
                "--reviewer",
                "HUMAN-OPS",
                "--verdict",
                "changes-requested",
                "--json",
            )
            result = self.run_cli(
                workspace,
                "review",
                "update",
                "REVIEW-CHANGES-FIRST",
                "--set",
                "verdict=accept-ready",
                "--json",
                check=False,
            )
            data = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
            review = next(item for item in data["review_verdicts"] if item["id"] == "REVIEW-CHANGES-FIRST")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accept-ready review requires passed evidence", result.stderr)
        self.assertEqual(review["verdict"], "changes-requested")

    def test_cli_evidence_record_uses_transition_gate(self) -> None:
        with self.temp_workspace() as workspace:
            result = self.run_cli(
                workspace,
                "evidence",
                "record",
                "EVIDENCE-WRONG-HEAD",
                "--work-item-id",
                "WORK-0001",
                "--attempt-id",
                "ATTEMPT-0001",
                "--head-sha",
                "wrong-head",
                "--status",
                "passed",
                "--json",
                check=False,
            )
            data = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match attempt head abc1234", result.stderr)
        self.assertNotIn("EVIDENCE-WRONG-HEAD", json.dumps(data["evidence_runs"]))

    def test_cli_evidence_update_cannot_bypass_transition_gate(self) -> None:
        with self.temp_workspace() as workspace:
            result = self.run_cli(
                workspace,
                "evidence",
                "update",
                "EVIDENCE-0001",
                "--set",
                "head_sha=wrong-head",
                "--json",
                check=False,
            )
            data = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
            evidence = next(item for item in data["evidence_runs"] if item["id"] == "EVIDENCE-0001")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match attempt head abc1234", result.stderr)
        self.assertEqual(evidence["head_sha"], "abc1234")

    def test_non_trust_metadata_updates_do_not_reopen_historical_gates(self) -> None:
        with self.temp_workspace() as workspace:
            evidence_result = self.run_cli(
                workspace,
                "evidence",
                "update",
                "EVIDENCE-0005",
                "--set",
                "summary=Historical note clarified.",
                "--json",
            )
            review_result = self.run_cli(
                workspace,
                "review",
                "update",
                "REVIEW-0006",
                "--list",
                "residual_risks=Review must still be rerun.",
                "--json",
            )
            data = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
            evidence = next(item for item in data["evidence_runs"] if item["id"] == "EVIDENCE-0005")
            review = next(item for item in data["review_verdicts"] if item["id"] == "REVIEW-0006")

        self.assertEqual(evidence_result.returncode, 0)
        self.assertEqual(review_result.returncode, 0)
        self.assertEqual(evidence["summary"], "Historical note clarified.")
        self.assertEqual(review["residual_risks"], ["Review must still be rerun."])

    def test_public_command_surface_is_unchanged(self) -> None:
        from palari_company_os.cli_parser import build_parser

        commands: list[str] = []

        def walk(parser: object, prefix: str = "palari") -> None:
            for action in getattr(parser, "_actions", []):
                choices = getattr(action, "choices", None)
                if not isinstance(choices, dict):
                    continue
                for name, subparser in choices.items():
                    if not hasattr(subparser, "_actions"):
                        continue
                    command = f"{prefix} {name}"
                    commands.append(command)
                    walk(subparser, command)

        walk(build_parser())

        self.assertEqual(len(commands), 145)

    def temp_workspace(self) -> object:
        return _TempWorkspace()

    def run_cli(
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
        )


class _TempWorkspace:
    def __enter__(self) -> Path:
        self._tempdir = tempfile.TemporaryDirectory()
        target = Path(self._tempdir.name) / "acme-company-os"
        shutil.copytree(WORKSPACE, target)
        return target

    def __exit__(self, *args: object) -> None:
        self._tempdir.cleanup()

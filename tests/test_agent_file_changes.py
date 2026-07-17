from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_file_changes import inspect_file_changes
from palari_company_os.agent_packets import _allowed_paths, _required_output
from palari_company_os.evidence_manifest import (
    artifact_hashes_at_root,
    evidence_manifest_hash,
    verify_evidence,
)


class DeletionAwareFileChangeTests(unittest.TestCase):
    def test_packet_separates_exact_write_scope_from_required_presence(self) -> None:
        work = {
            "allowed_resources": ["src"],
            "output_targets": ["src/new.py", "src/old.py"],
            "path_intents": [
                {"path": "src/new.py", "intent": "create"},
                {"path": "src/old.py", "intent": "delete"},
            ],
        }

        allowed = _allowed_paths(work, "execute")
        required = _required_output(work, "execute")

        self.assertEqual(allowed["write"], ["src/new.py", "src/old.py"])
        self.assertEqual(required["output_targets"], ["src/new.py"])
        self.assertEqual(required["path_intents"], work["path_intents"])

    def test_legacy_packet_shape_is_unchanged_without_path_intents(self) -> None:
        required = _required_output(
            {
                "allowed_resources": ["src"],
                "output_targets": ["src/result.py"],
            },
            "execute",
        )

        self.assertNotIn("path_intents", required)
        self.assertEqual(required["output_targets"], ["src/result.py"])

    def test_declared_delete_is_satisfied_only_when_exact_path_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = self._git_root(Path(root_name))
            packet = self._packet("obsolete.txt", "delete")

            result = inspect_file_changes(
                packet,
                changed_paths=["obsolete.txt"],
                cwd=root,
            )

            assert result is not None
            self.assertTrue(result["path_intents_ok"])
            self.assertEqual(result["missing_required_outputs"], [])

    def test_declared_delete_fails_closed_while_path_remains(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = self._git_root(Path(root_name))
            (root / "obsolete.txt").write_text("still here\n", encoding="utf-8")

            result = inspect_file_changes(
                self._packet("obsolete.txt", "delete"),
                changed_paths=["obsolete.txt"],
                cwd=root,
            )

            assert result is not None
            self.assertFalse(result["path_intents_ok"])
            self.assertEqual(result["missing_required_outputs"], ["obsolete.txt"])
            self.assertEqual(result["path_intent_mismatches"][0]["actual"], "present")

    def test_declared_create_fails_closed_when_path_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = self._git_root(Path(root_name))

            result = inspect_file_changes(
                self._packet("new.txt", "create"),
                changed_paths=["new.txt"],
                cwd=root,
            )

            assert result is not None
            self.assertFalse(result["path_intents_ok"])
            self.assertEqual(result["path_intent_mismatches"][0]["intent"], "create")

    def test_delete_tombstone_is_distinct_from_accidental_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)

            ordinary = artifact_hashes_at_root(root, ["obsolete.txt"])
            tombstone = artifact_hashes_at_root(
                root,
                ["obsolete.txt"],
                expected_absent_paths={"obsolete.txt"},
            )

            self.assertEqual(ordinary[0]["status"], "missing")
            self.assertEqual(ordinary[0]["sha256"], "sha256:missing")
            self.assertEqual(tombstone[0]["status"], "absent")
            self.assertEqual(tombstone[0]["sha256"], "sha256:absent")

    def test_delete_tombstone_does_not_hide_present_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            (root / "obsolete.txt").write_text("still here\n", encoding="utf-8")

            hashes = artifact_hashes_at_root(
                root,
                ["obsolete.txt"],
                expected_absent_paths={"obsolete.txt"},
            )

            self.assertEqual(hashes[0]["status"], "present")
            self.assertNotEqual(hashes[0]["sha256"], "sha256:absent")

    def test_evidence_verifier_accepts_absence_only_for_delete_intent(self) -> None:
        with tempfile.TemporaryDirectory() as root_name:
            root = self._git_root(Path(root_name))
            subprocess.run(
                ["git", "-C", str(root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test"],
                check=True,
            )
            obsolete = root / "obsolete.txt"
            obsolete.write_text("remove me\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "obsolete.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "base"],
                check=True,
            )
            base_head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            obsolete.unlink()
            subprocess.run(["git", "-C", str(root), "add", "-u"], check=True)
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "delete"],
                check=True,
            )
            candidate_head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            record = {
                "id": "EVIDENCE-1",
                "work_item_id": "WORK-1",
                "attempt_id": "ATTEMPT-1",
                "head_sha": candidate_head,
                "status": "passed",
                "base_ref": base_head,
                "commands": ["test"],
                "artifacts": ["obsolete.txt"],
                "artifact_hashes": [
                    {
                        "path": "obsolete.txt",
                        "sha256": "sha256:absent",
                        "status": "absent",
                    }
                ],
                "summary": "Deletion verified.",
                "freshness": "exact-head",
                "timestamp": "2026-01-01T00:00:00Z",
            }
            record["manifest_hash"] = evidence_manifest_hash(record)
            evidence = SimpleNamespace(
                **record,
                output_binding_version="",
                receipt_hash="",
                previous_receipt_hash="",
            )
            work = SimpleNamespace(
                path_intents=[{"path": "obsolete.txt", "intent": "delete"}]
            )
            workspace = SimpleNamespace(
                name="Test",
                path=root,
                attempts=[],
                receipts=[],
                evidence_runs=[evidence],
                work_item=lambda work_id: work if work_id == "WORK-1" else None,
            )

            report = verify_evidence(
                workspace,
                "EVIDENCE-1",
                require_output_coverage=False,
            )

            self.assertTrue(report["artifact_hashes_ok"])

    @staticmethod
    def _packet(path: str, intent: str) -> dict[str, object]:
        return {
            "allowed_paths": {"write": [path]},
            "required_output": {
                "output_targets": [] if intent == "delete" else [path],
                "fallback_write_paths": [path],
                "path_intents": [{"path": path, "intent": intent}],
            },
        }

    @staticmethod
    def _git_root(root: Path) -> Path:
        subprocess.run(
            ["git", "-C", str(root), "init", "-q"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return root


if __name__ == "__main__":
    unittest.main()

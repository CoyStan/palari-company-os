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

from palari_company_os.pcaw_protocol import verify_pcaw_file
from palari_company_os.pcaw_subjects import SubjectError, hash_subject, validate_subject_name


ACCEPTED_VECTOR = REPO_ROOT / "spec" / "pcaw" / "v1" / "vectors" / "valid" / "accepted"
ACCEPTED_WORKSPACE = (
    REPO_ROOT / "tests" / "fixtures" / "workspaces" / "valid-accepted-completed-work.json"
)


class PCAWProtocolTests(unittest.TestCase):
    def test_accepted_vector_verifies_fully_offline(self) -> None:
        report = verify_pcaw_file(
            ACCEPTED_VECTOR / "statement.json", subject_root=ACCEPTED_VECTOR
        )

        self.assertTrue(report["verified"])
        self.assertTrue(report["fully_verified"])
        self.assertTrue(report["acceptance_verified"])
        self.assertEqual(report["derived_lifecycle_state"], "accepted")
        self.assertEqual(report["subject_digest_status"], "verified")
        self.assertEqual(set(report["verified_properties"]), {
            "scope_compliance",
            "subject_integrity",
            "evidence_freshness",
            "receipt_binding",
            "independent_review",
            "human_quorum",
            "acceptance_currency",
            "journal_continuity",
        })

    def test_changed_artifact_fails_with_stable_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "bundle"
            shutil.copytree(ACCEPTED_VECTOR, root)
            (root / "outputs" / "result.txt").write_text("changed\n", encoding="utf-8")

            report = verify_pcaw_file(root / "statement.json")

        self.assertFalse(report["verified"])
        self.assertFalse(report["acceptance_verified"])
        self.assertEqual(report["subject_digest_status"], "failed")
        self.assertIn("SUBJECT_DIGEST_MISMATCH", _codes(report))

    def test_statement_only_never_claims_full_or_acceptance_verification(self) -> None:
        report = verify_pcaw_file(
            ACCEPTED_VECTOR / "statement.json",
            subject_root=ACCEPTED_VECTOR,
            statement_only=True,
        )

        self.assertTrue(report["verified"])
        self.assertFalse(report["fully_verified"])
        self.assertFalse(report["acceptance_verified"])
        self.assertEqual(report["subject_digest_status"], "not-checked")
        self.assertIn("ARTIFACT_CHECKS_SKIPPED", _warning_codes(report))

    def test_repeated_export_is_byte_identical_across_process_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            environments = (
                {"TZ": "Pacific/Honolulu", "LC_ALL": "C"},
                {"TZ": "UTC", "LC_ALL": "C.UTF-8"},
            )
            for output, additions in zip((first, second), environments):
                env = os.environ.copy()
                env.update(additions)
                env["PYTHONPATH"] = str(REPO_ROOT / "src")
                subprocess.run(
                    [
                        sys.executable,
                        "-S",
                        "-m",
                        "palari_company_os",
                        "--workspace",
                        str(ACCEPTED_WORKSPACE),
                        "proof",
                        "export",
                        "WORK-1",
                        "--output",
                        str(output),
                        "--json",
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

            first_bytes = first.read_bytes()
            second_bytes = second.read_bytes()

        self.assertEqual(first_bytes, second_bytes)
        self.assertNotIn(str(REPO_ROOT).encode(), first_bytes)
        self.assertFalse(first_bytes.endswith(b"\n"))

    def test_subject_paths_reject_traversal_and_symlinks(self) -> None:
        for unsafe in ("../secret.txt", ".", "a//b", "/absolute"):
            with self.subTest(unsafe=unsafe), self.assertRaises(SubjectError):
                validate_subject_name(unsafe)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / f"{root.name}-outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "linked.txt").symlink_to(outside)
            try:
                with self.assertRaises(SubjectError) as raised:
                    hash_subject(root, "linked.txt")
                self.assertEqual(raised.exception.code, "PCAW_SUBJECT_SYMLINK")
            finally:
                outside.unlink(missing_ok=True)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proof = Path(directory) / "duplicate.json"
            proof.write_bytes(b'{"_type":"one","_type":"two"}')
            report = verify_pcaw_file(proof)

        self.assertFalse(report["verified"])
        self.assertIn("DUPLICATE_KEY", _codes(report))

    def test_cli_rejection_uses_exit_one_and_complete_json_report(self) -> None:
        invalid = (
            REPO_ROOT
            / "spec"
            / "pcaw"
            / "v1"
            / "vectors"
            / "invalid"
            / "changed-artifact"
            / "statement.json"
        )
        result = subprocess.run(
            [
                str(REPO_ROOT / "bin" / "palari"),
                "proof",
                "verify",
                str(invalid),
                "--subject-root",
                str(invalid.parent),
                "--json",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertFalse(report["verified"])
        self.assertEqual(report["schema_version"], "pcaw.verification.v1")


def _codes(report: dict[str, object]) -> set[str]:
    return {str(item["code"]) for item in report["errors"]}  # type: ignore[index]


def _warning_codes(report: dict[str, object]) -> set[str]:
    return {str(item["code"]) for item in report["warnings"]}  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()

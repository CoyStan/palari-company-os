from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.governance_case import GovernanceCase, ReviewerAuthority
from palari_company_os.pcaw_canonical import canonical_json_bytes, canonical_sha256
from palari_company_os.pcaw_export import export_pcaw_statement
from palari_company_os.pcaw_protocol import verify_pcaw_bytes, verify_pcaw_file
from palari_company_os.pcaw_subjects import SubjectError, hash_subject, validate_subject_name
from palari_company_os.workspace import WorkspaceError


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

    def test_typed_palari_reviewer_verifies_without_entering_human_authorities(self) -> None:
        statement = json.loads(
            (ACCEPTED_VECTOR / "statement.json").read_text(encoding="utf-8")
        )
        case = GovernanceCase.from_dict(statement["predicate"]["governance_case"])
        case = replace(
            case,
            humans=tuple(item for item in case.humans if item.id != "PALARI-REVIEWER"),
            reviewer_authorities=(ReviewerAuthority("PALARI-REVIEWER"),),
        )
        statement["predicate"]["governance_case"] = case.to_dict()
        work_subject = next(
            item for item in statement["subject"] if item["name"].startswith("urn:palari:")
        )
        work_subject["digest"]["sha256"] = canonical_sha256(case.to_dict()).removeprefix(
            "sha256:"
        )

        report = verify_pcaw_bytes(
            canonical_json_bytes(statement), subject_root=ACCEPTED_VECTOR
        )

        self.assertTrue(report["verified"])
        self.assertTrue(report["acceptance_verified"])
        self.assertEqual(report["verified_properties"]["independent_review"], "verified")
        self.assertEqual(report["verified_properties"]["human_quorum"], "verified")

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

    def test_evidence_digest_must_match_the_output_subject_digest(self) -> None:
        statement = json.loads((ACCEPTED_VECTOR / "statement.json").read_text(encoding="utf-8"))
        case = GovernanceCase.from_dict(statement["predicate"]["governance_case"])
        evidence = replace(
            case.evidence,
            artifact_hashes=(
                replace(case.evidence.artifact_hashes[0], sha256="a" * 64),
            ),
        )
        case = replace(case, evidence=evidence)
        review = replace(case.review, evidence_digest=case.evidence_digest())
        case = replace(case, review=review)
        decisions = tuple(
            replace(
                item,
                evidence_digest=case.evidence_digest(),
                review_digest=case.review_digest(),
            )
            for item in case.human_decisions
        )
        acceptances = tuple(
            replace(
                item,
                evidence_digest=case.evidence_digest(),
                review_digest=case.review_digest(),
            )
            for item in case.acceptance_records
        )
        case = replace(case, human_decisions=decisions, acceptance_records=acceptances)
        statement["predicate"]["governance_case"] = case.to_dict()
        work_subject = next(
            item for item in statement["subject"] if item["name"].startswith("urn:palari:")
        )
        work_subject["digest"]["sha256"] = canonical_sha256(case.to_dict()).removeprefix(
            "sha256:"
        )

        report = verify_pcaw_bytes(
            canonical_json_bytes(statement),
            subject_root=ACCEPTED_VECTOR,
        )

        self.assertFalse(report["verified"])
        self.assertFalse(report["acceptance_verified"])
        self.assertEqual(report["verified_properties"]["evidence_freshness"], "failed")
        self.assertIn("PCAW_EVIDENCE_SUBJECT_MISMATCH", _codes(report))

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

    def test_parent_directory_swap_cannot_escape_pinned_subject_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            safe = root / "safe"
            outside = Path(directory) / "outside"
            safe.mkdir(parents=True)
            outside.mkdir()
            (safe / "result.txt").write_text("inside", encoding="utf-8")
            (outside / "result.txt").write_text("outside", encoding="utf-8")
            original_open = os.open
            swapped = False

            def racing_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
                nonlocal swapped
                if path == "result.txt" and kwargs.get("dir_fd") is not None and not swapped:
                    safe.rename(root / "pinned")
                    safe.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return original_open(path, flags, *args, **kwargs)

            with patch("palari_company_os.pcaw_subjects.os.open", side_effect=racing_open):
                digest = hash_subject(root, "safe/result.txt")

        self.assertTrue(swapped)
        self.assertEqual(digest, hashlib.sha256(b"inside").hexdigest())

    def test_subject_read_error_returns_structured_rejection(self) -> None:
        with patch(
            "palari_company_os.pcaw_subjects.os.read",
            side_effect=OSError("simulated EIO"),
        ):
            report = verify_pcaw_file(
                ACCEPTED_VECTOR / "statement.json",
                subject_root=ACCEPTED_VECTOR,
            )

        self.assertFalse(report["verified"])
        self.assertFalse(report["acceptance_verified"])
        self.assertEqual(report["subject_digest_status"], "failed")
        self.assertIn("SUBJECT_UNREADABLE", _codes(report))

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            proof = Path(directory) / "duplicate.json"
            proof.write_bytes(b'{"_type":"one","_type":"two"}')
            report = verify_pcaw_file(proof)

        self.assertFalse(report["verified"])
        self.assertIn("DUPLICATE_KEY", _codes(report))

    def test_cli_rejection_uses_exit_one_and_complete_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_root = Path(directory) / "missing"
            result = subprocess.run(
                [
                    str(REPO_ROOT / "bin" / "palari"),
                    "proof",
                    "verify",
                    str(ACCEPTED_VECTOR / "statement.json"),
                    "--subject-root",
                    str(missing_root),
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
        self.assertIn("SUBJECT_ROOT_INVALID", _codes(report))
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_cyclic_subject_root_is_a_structured_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cycle = Path(directory) / "loop"
            cycle.symlink_to(cycle.name)
            result = subprocess.run(
                [
                    str(REPO_ROOT / "bin" / "palari"),
                    "proof",
                    "verify",
                    str(ACCEPTED_VECTOR / "statement.json"),
                    "--subject-root",
                    str(cycle),
                    "--json",
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("SUBJECT_ROOT_INVALID", _codes(json.loads(result.stdout)))
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_unreadable_proof_is_structured_operational_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            result = subprocess.run(
                [
                    str(REPO_ROOT / "bin" / "palari"),
                    "proof",
                    "verify",
                    str(missing),
                    "--json",
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("PROOF_UNREADABLE", _codes(json.loads(result.stdout)))
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_cyclic_proof_path_is_structured_operational_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cycle = Path(directory) / "proof.json"
            cycle.symlink_to(cycle.name)
            result = subprocess.run(
                [
                    str(REPO_ROOT / "bin" / "palari"),
                    "proof",
                    "verify",
                    str(cycle),
                    "--json",
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("PROOF_UNREADABLE", _codes(json.loads(result.stdout)))
        self.assertNotIn("Traceback", result.stderr)

    def test_export_preserves_workspace_claim_and_stales_changed_review_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.loads(ACCEPTED_WORKSPACE.read_text(encoding="utf-8"))
            raw["work_items"][0]["status"] = "in-review"
            raw["work_items"][0]["scope"] = "Changed after the exact review."
            raw["human_decisions"] = []
            raw["acceptance_records"] = []
            workspace_file = root / "workspace.json"
            workspace_file.write_text(json.dumps(raw), encoding="utf-8")
            proof_file = root / "proof.json"

            export_pcaw_statement(workspace_file, "WORK-1", proof_file)
            statement = json.loads(proof_file.read_text(encoding="utf-8"))
            report = verify_pcaw_file(proof_file)

        self.assertEqual(statement["predicate"]["claimed_state"], "review-required")
        self.assertIn("PCAW_REVIEW_BINDING_STALE", _codes(report))

    def test_export_does_not_replace_active_workspace_claim_with_derived_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.loads(ACCEPTED_WORKSPACE.read_text(encoding="utf-8"))
            raw["work_items"][0]["status"] = "active"
            workspace_file = root / "workspace.json"
            workspace_file.write_text(json.dumps(raw), encoding="utf-8")
            proof_file = root / "proof.json"

            result = export_pcaw_statement(workspace_file, "WORK-1", proof_file)
            statement = json.loads(proof_file.read_text(encoding="utf-8"))

        self.assertEqual(result["claimed_state"], "in-progress")
        self.assertEqual(statement["predicate"]["claimed_state"], "in-progress")
        self.assertNotEqual(result["claimed_state"], result["derived_lifecycle_state"])

    def test_export_rejects_local_deletion_tombstones_before_writing(self) -> None:
        statement = json.loads(
            (ACCEPTED_VECTOR / "statement.json").read_text(encoding="utf-8")
        )
        case = GovernanceCase.from_dict(statement["predicate"]["governance_case"])
        case = replace(
            case,
            evidence=replace(
                case.evidence,
                artifact_hashes=(
                    replace(
                        case.evidence.artifact_hashes[0],
                        sha256="absent",
                        status="absent",
                    ),
                ),
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            proof_file = Path(directory) / "proof.json"
            with (
                patch("palari_company_os.pcaw_export.Workspace.load", return_value=object()),
                patch(
                    "palari_company_os.pcaw_export.governance_case_from_workspace",
                    return_value=(case, []),
                ),
            ):
                with self.assertRaisesRegex(
                    WorkspaceError,
                    "PCAW v1 proves present artifact bytes only",
                ):
                    export_pcaw_statement(directory, case.contract.id, proof_file)

            self.assertFalse(proof_file.exists())


def _codes(report: dict[str, object]) -> set[str]:
    return {str(item["code"]) for item in report["errors"]}  # type: ignore[index]


def _warning_codes(report: dict[str, object]) -> set[str]:
    return {str(item["code"]) for item in report["warnings"]}  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()

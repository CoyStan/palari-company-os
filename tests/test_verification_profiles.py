from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "scripts" / "verification_profiles.py"
SPEC = importlib.util.spec_from_file_location("verification_profiles", HELPER)
assert SPEC is not None and SPEC.loader is not None
verification_profiles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verification_profiles)


class VerificationProfileTests(unittest.TestCase):
    def test_affected_profile_maps_known_operator_paths_deterministically(self) -> None:
        modules = verification_profiles.affected_test_modules(
            [
                "src/palari_company_os/agent_finish.py",
                "src/palari_company_os/read_models.py",
                "tests/test_verification_profiles.py",
            ]
        )

        self.assertEqual(
            modules,
            [
                "tests.test_agent_packets",
                "tests.test_verification_profiles",
                "tests.test_workspace_read_models",
            ],
        )

    def test_affected_profile_falls_back_to_full_suite_for_unknown_core_file(self) -> None:
        self.assertIsNone(
            verification_profiles.affected_test_modules(
                ["src/palari_company_os/future_governance_kernel.py"]
            )
        )

    def test_affected_profile_maps_governance_and_filesystem_kernels(self) -> None:
        modules = verification_profiles.affected_test_modules(
            [
                "src/palari_company_os/governance_binding.py",
                "src/palari_company_os/agent_file_changes.py",
            ]
        )

        self.assertEqual(
            modules,
            [
                "tests.test_agent_packets",
                "tests.test_filesystem_security",
                "tests.test_governance_completion",
                "tests.test_path_policy",
                "tests.test_transition_checks",
                "tests.test_validation",
                "tests.test_workspace_read_models",
            ],
        )

    def test_affected_profile_rejects_unsafe_paths_with_full_suite_fallback(self) -> None:
        self.assertIsNone(verification_profiles.affected_test_modules(["../outside.py"]))
        self.assertIsNone(verification_profiles.affected_test_modules(["/tmp/outside.py"]))

    def test_focused_profile_rejects_non_test_module_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid focused test module"):
            verification_profiles._validated_modules(["palari_company_os.authoring"])

    def test_profile_cli_lists_selection_without_running_tests(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(HELPER),
                "affected",
                "src/palari_company_os/agent_finish.py",
                "--list",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), "tests.test_agent_packets")

    def test_git_changed_paths_preserves_both_sides_of_a_rename(self) -> None:
        result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=b"R  new.py\0old.py\0 M changed.py\0",
        )
        with patch.object(verification_profiles.subprocess, "run", return_value=result):
            paths = verification_profiles.git_changed_paths()

        self.assertEqual(paths, ["new.py", "old.py", "changed.py"])

    def test_complete_shell_profile_keeps_full_suite_and_required_smokes(self) -> None:
        script = (REPO_ROOT / "scripts" / "verify.sh").read_text(encoding="utf-8")

        self.assertIn('profile="${1:-complete}"', script)
        self.assertIn("python3 -S -m unittest discover -s tests", script)
        for command in (
            "palari state --json",
            "palari detail WORK-0001 --json",
            "palari scope WORK-0001",
            "palari maintainer status --json",
            "workspaces/palari-company-os validate --json",
            "split-workspace detail WORK-SPLIT --json",
        ):
            self.assertIn(command, script)


if __name__ == "__main__":
    unittest.main()

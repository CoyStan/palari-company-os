from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "scripts" / "verification_profiles.py"
PARALLEL_RUNNER = REPO_ROOT / "scripts" / "parallel_unittest.py"
STYLE_HELPER = REPO_ROOT / "scripts" / "check_style.py"
SPEC = importlib.util.spec_from_file_location("verification_profiles", HELPER)
assert SPEC is not None and SPEC.loader is not None
verification_profiles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verification_profiles)
STYLE_SPEC = importlib.util.spec_from_file_location("check_style", STYLE_HELPER)
assert STYLE_SPEC is not None and STYLE_SPEC.loader is not None
check_style = importlib.util.module_from_spec(STYLE_SPEC)
STYLE_SPEC.loader.exec_module(check_style)


class VerificationProfileTests(unittest.TestCase):
    def test_focused_modules_are_explicit_deduplicated_and_sorted(self) -> None:
        modules = verification_profiles.validated_modules(
            [
                "tests.test_validation",
                "tests.test_governance_kernel",
                "tests.test_validation",
            ]
        )

        self.assertEqual(
            modules,
            ["tests.test_governance_kernel", "tests.test_validation"],
        )
        with self.assertRaisesRegex(ValueError, "invalid focused test module"):
            verification_profiles.validated_modules(["palari_company_os.authoring"])

    def test_focused_cli_lists_modules_without_running_tests(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(HELPER),
                "tests.test_validation",
                "tests.test_governance_kernel",
                "--list",
            ],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        self.assertEqual(
            result.stdout.splitlines(),
            ["tests.test_governance_kernel", "tests.test_validation"],
        )

    def test_complete_profile_has_one_current_candidate_path(self) -> None:
        script = (REPO_ROOT / "scripts" / "verify.sh").read_text(encoding="utf-8")

        self.assertIn('profile="${1:-complete}"', script)
        self.assertEqual(script.count("scripts/parallel_unittest.py"), 1)
        self.assertEqual(script.count("./scripts/install_smoke.sh"), 1)
        for command in (
            "scripts/check_style.py",
            "ruff check .",
            "mypy",
            "compileall -q src",
            "schemas/workspace.schema.json",
            "scripts/update_pcaw_tcb.py --check",
            "spec/pcaw/v1/conformance.py",
        ):
            self.assertIn(command, script)
        self.assertNotIn("palari docs check", script)
        for obsolete in (
            "affected",
            "pcaw_demo.sh",
            "workspaces/palari-company-os",
            "--workspace examples/acme-company-os",
            "palari state --json",
            "palari detail WORK-0001",
        ):
            self.assertNotIn(obsolete, script)

    def test_install_smoke_builds_one_wheel_over_isolated_current_state(self) -> None:
        script = (REPO_ROOT / "scripts" / "install_smoke.sh").read_text(
            encoding="utf-8"
        )

        self.assertEqual(script.count("pip wheel"), 1)
        self.assertEqual(script.count("pip install"), 1)
        self.assertIn("--no-build-isolation", script)
        self.assertIn('palari" init "$project_dir"', script)
        self.assertIn("pcaw-offline-verify.json", script)
        self.assertNotIn("examples/acme-company-os", script)
        self.assertNotIn("workspaces/palari-company-os", script)
        self.assertNotIn("integration plan", script)
        self.assertNotIn("integration approve", script)

    def test_repository_style_check_excludes_historical_dogfood(self) -> None:
        dogfood = REPO_ROOT / "workspaces" / "palari-company-os" / "workspace.json"
        current_schema = REPO_ROOT / "schemas" / "workspace.schema.json"

        self.assertTrue(check_style._skip(dogfood, REPO_ROOT))
        self.assertFalse(check_style._skip(current_schema, REPO_ROOT))

    def test_parallel_runner_lists_every_test_module_deterministically(self) -> None:
        result = subprocess.run(
            [sys.executable, "-S", str(PARALLEL_RUNNER), "--list"],
            cwd=REPO_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        expected = [
            f"tests.{path.stem}" for path in sorted((REPO_ROOT / "tests").glob("test_*.py"))
        ]
        self.assertEqual(result.stdout.splitlines(), expected)


if __name__ == "__main__":
    unittest.main()

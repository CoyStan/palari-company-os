from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os import store as store_module
from palari_company_os.governance_journal import (
    journal_file_path,
    verify_workspace_journal,
)
from palari_company_os.store import (
    WorkspaceStore,
    _atomic_replace_text,
    load_store,
    write_store,
)
from palari_company_os.workspace import WorkspaceError


FIXTURE = REPO_ROOT / "tests" / "fixtures" / "workspaces" / "valid-workspace.json"


class CompletionPrewriteAtomicityTests(unittest.TestCase):
    def test_validation_runs_after_staging_immediately_before_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_path = root / "workspace.json"
            data_path.write_text("before\n", encoding="utf-8")
            events: list[str] = []
            staged_path: Path | None = None
            real_replace = store_module.os.replace

            def validate_staged_bytes() -> None:
                nonlocal staged_path
                events.append("validate")
                candidates = list(root.rglob("workspace-stage-*.tmp"))
                self.assertEqual(len(candidates), 1)
                staged_path = candidates[0]
                self.assertEqual(staged_path.read_text(encoding="utf-8"), "after\n")

            def observed_replace(source: object, target: object) -> None:
                events.append("replace")
                self.assertEqual(events, ["validate", "replace"])
                self.assertEqual(Path(source), staged_path)
                self.assertEqual(Path(target), data_path)
                real_replace(source, target)

            with patch.object(
                store_module.os,
                "replace",
                side_effect=observed_replace,
            ):
                _atomic_replace_text(
                    data_path,
                    "after\n",
                    pre_replace_check=validate_staged_bytes,
                )

            self.assertEqual(data_path.read_text(encoding="utf-8"), "after\n")
            self.assertIsNotNone(staged_path)
            assert staged_path is not None
            self.assertFalse(staged_path.exists())

    def test_rejected_staged_validation_aborts_and_reraises_original_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "workspace.json"
            data = json.loads(FIXTURE.read_text(encoding="utf-8"))
            write_store(WorkspaceStore(data_path=data_path, data=data))
            before_workspace = data_path.read_bytes()
            candidate = load_store(data_path)
            candidate.data["name"] = "Rejected completion candidate"
            rejection = WorkspaceError("source state changed at final replacement")
            checks = 0

            def reject_second_check() -> None:
                nonlocal checks
                checks += 1
                if checks == 2:
                    raise rejection

            with self.assertRaises(WorkspaceError) as raised:
                write_store(
                    candidate,
                    prewrite_check=reject_second_check,
                )

            self.assertIs(raised.exception, rejection)
            self.assertEqual(checks, 2)
            self.assertEqual(data_path.read_bytes(), before_workspace)
            report = verify_workspace_journal(data_path)
            self.assertTrue(report["ok"], report)
            self.assertIsNone(report["pending"])
            self.assertEqual(report["aborted_transactions"], 1)
            records = [
                json.loads(line)
                for line in journal_file_path(data_path)
                .read_text(encoding="utf-8")
                .splitlines()
                if line
            ]
            self.assertEqual(records[-1]["record_type"], "abort")
            self.assertEqual(
                records[-1]["reason"],
                "final prewrite validation rejected the staged mutation",
            )
            staged_files = list(
                data_path.parent.rglob("workspace-stage-*.tmp")
            )
            self.assertEqual(staged_files, [])


if __name__ == "__main__":
    unittest.main()

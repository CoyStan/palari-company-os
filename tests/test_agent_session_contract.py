from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_checks import build_agent_check
from palari_company_os.agent_packets import _context_hash, build_agent_brief
from palari_company_os.agent_runtime import release_agent, start_agent
from palari_company_os.agent_session_contract import (
    compile_agent_session_contract,
    session_contract_error,
)
from palari_company_os.pcaw_canonical import canonical_sha256
from palari_company_os.workspace import Workspace, WorkspaceError


WORKSPACE = REPO_ROOT / "examples" / "acme-company-os"


class AgentSessionContractTests(unittest.TestCase):
    def test_compiler_is_deterministic_and_omits_runtime_and_local_data(self) -> None:
        packet = build_agent_brief(
            Workspace.load(WORKSPACE),
            "WORK-0003",
            "PALARI-SOFIA",
            "execute",
        )
        first = compile_agent_session_contract(packet)
        packet["created_at"] = "2099-12-31T23:59:59Z"
        second = compile_agent_session_contract(packet)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ready")
        self.assertFalse(first["contract"]["packet_binding"]["grants_authority"])
        self.assertTrue(first["contract"]["packet_binding"]["claim_required"])
        serialized = json.dumps(first, sort_keys=True)
        self.assertNotIn(str(REPO_ROOT), serialized)
        self.assertNotIn("created_at", serialized)
        self.assertNotIn("last_read_at", serialized)
        self.assertNotIn('"label"', serialized)
        self.assertNotIn('"notes"', serialized)

    def test_cli_bytes_are_stable_across_process_timezone_and_locale(self) -> None:
        first_env = {"TZ": "UTC", "LC_ALL": "C"}
        second_env = {"TZ": "Pacific/Honolulu", "LC_ALL": "C.UTF-8"}

        first = self.run_cli(
            "agent",
            "brief",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--session-contract",
            "--json",
            extra_env=first_env,
        )
        second = self.run_cli(
            "agent",
            "brief",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--session-contract",
            "--json",
            extra_env=second_env,
        )

        self.assertEqual(first.stdout, second.stdout)

    def test_blocked_packet_compiles_without_execution_authority(self) -> None:
        packet = build_agent_brief(
            Workspace.load(WORKSPACE),
            "WORK-DOES-NOT-EXIST",
            "PALARI-SOFIA",
            "execute",
        )

        contract = compile_agent_session_contract(packet)

        self.assertEqual(contract["status"], "blocked")
        self.assertEqual(
            contract["contract"]["packet_binding"]["packet_status"],
            "blocked",
        )
        self.assertEqual(contract["contract"]["scope"]["write_paths"], [])
        self.assertIn("MISSING_WORK_ITEM", self._blocker_codes(contract))

    def test_unsafe_or_duplicate_paths_fail_closed(self) -> None:
        workspace = Workspace.load(WORKSPACE)
        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        packet["allowed_paths"]["write"] = ["../outside.txt"]
        packet["context_hash"] = _context_hash(packet)
        with self.assertRaisesRegex(WorkspaceError, "unsafe path"):
            compile_agent_session_contract(packet)

        packet = build_agent_brief(workspace, "WORK-0003", "PALARI-SOFIA", "execute")
        allowed = packet["allowed_paths"]["write"][0]
        packet["allowed_paths"]["write"] = [allowed, allowed]
        packet["context_hash"] = _context_hash(packet)
        with self.assertRaisesRegex(WorkspaceError, "duplicate paths"):
            compile_agent_session_contract(packet)

    def test_tamper_unknown_fields_and_enforcement_upgrade_are_rejected(self) -> None:
        packet = build_agent_brief(
            Workspace.load(WORKSPACE),
            "WORK-0003",
            "PALARI-SOFIA",
            "execute",
        )
        contract = compile_agent_session_contract(packet)

        unknown = deepcopy(contract)
        unknown["native_enforcement"] = True
        self.assertIn("unknown fields", session_contract_error(unknown))

        upgraded = deepcopy(contract)
        upgraded["contract"]["enforcement"]["adapter"] = "unverified-host"
        upgraded["contract_digest"] = canonical_sha256(
            {
                "schema_version": upgraded["schema_version"],
                "status": upgraded["status"],
                "contract": upgraded["contract"],
            }
        )
        upgraded["contract_id"] = (
            "SESSION-CONTRACT-"
            + upgraded["contract_digest"].removeprefix("sha256:")[:24].upper()
        )
        self.assertIn("enforcement declaration", session_contract_error(upgraded))

    def test_enforcement_report_distinguishes_palari_adapter_and_advisory(self) -> None:
        packet = build_agent_brief(
            Workspace.load(WORKSPACE),
            "WORK-0003",
            "PALARI-SOFIA",
            "execute",
        )
        contract = compile_agent_session_contract(packet)
        properties = {
            item["id"]: item["status"]
            for item in contract["contract"]["enforcement"]["properties"]
        }

        self.assertEqual(properties["human-authority"], "palari-enforced")
        self.assertEqual(properties["write-boundary-before-tool"], "adapter-required")
        self.assertEqual(properties["read-boundary"], "advisory")
        self.assertEqual(contract["contract"]["enforcement"]["adapter"], "none")

    def test_start_persists_and_claim_binds_the_exact_contract(self) -> None:
        with self.temp_workspace_file() as workspace_file:
            workspace = Workspace.load(workspace_file)
            started = start_agent(
                workspace,
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            claim = started["start"]["claim"]
            relative = claim["session_contract_path"]
            path = workspace_file.parent / relative
            persisted = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(claim["schema_version"], "palari.agent_claim.v2")
            self.assertTrue(path.is_file())
            self.assertEqual(
                persisted["contract_digest"],
                claim["session_contract_digest"],
            )
            self.assertEqual(
                started["start"]["session_contract"]["contract_digest"],
                claim["session_contract_digest"],
            )
            check = build_agent_check(
                Workspace.load(workspace_file),
                "WORK-0003",
                "PALARI-SOFIA",
            )
            self.assertEqual(self._check(check, "CLAIM_OWNED")["status"], "pass")

    def test_missing_tampered_and_duplicate_key_contracts_fail_claim_check(self) -> None:
        mutations = ("missing", "tampered", "duplicate")
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.temp_workspace_file() as workspace_file:
                started = start_agent(
                    Workspace.load(workspace_file),
                    workspace_file,
                    "WORK-0003",
                    "PALARI-SOFIA",
                )
                claim = started["start"]["claim"]
                path = workspace_file.parent / claim["session_contract_path"]
                if mutation == "missing":
                    path.unlink()
                elif mutation == "tampered":
                    contract = json.loads(path.read_text(encoding="utf-8"))
                    contract["contract"]["scope"]["write_paths"] = ["outside.txt"]
                    path.write_text(json.dumps(contract), encoding="utf-8")
                else:
                    original = path.read_text(encoding="utf-8").lstrip()
                    path.write_text(
                        '{"status":"ready","status":"blocked",'
                        + original.removeprefix("{"),
                        encoding="utf-8",
                    )

                check = build_agent_check(
                    Workspace.load(workspace_file),
                    "WORK-0003",
                    "PALARI-SOFIA",
                )
                owned = self._check(check, "CLAIM_OWNED")
                self.assertEqual(owned["status"], "fail")
                message = str(owned["message"]).lower().replace("_", " ")
                self.assertIn("session contract", message)
                self.assertIn("agent start", str(owned["next_command"]))

    def test_new_claim_cannot_drop_both_contract_binding_fields(self) -> None:
        with self.temp_workspace_file() as workspace_file:
            started = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            claim = started["start"]["claim"]
            claim.pop("session_contract_path")
            claim.pop("session_contract_digest")
            claim_path = (
                workspace_file.parent
                / ".palari"
                / "claims"
                / "WORK-0003.json"
            )
            claim_path.write_text(json.dumps(claim), encoding="utf-8")

            check = build_agent_check(
                Workspace.load(workspace_file),
                "WORK-0003",
                "PALARI-SOFIA",
            )

            owned = self._check(check, "CLAIM_OWNED")
            self.assertEqual(owned["status"], "fail")
            message = str(owned["message"]).lower().replace("_", " ")
            self.assertIn("session contract", message)
            self.assertIn("agent start", str(owned["next_command"]))

    def test_contract_path_traversal_and_symlink_escape_fail_claim_check(self) -> None:
        for mutation in ("traversal", "symlink"):
            with self.subTest(mutation=mutation), self.temp_workspace_file() as workspace_file:
                started = start_agent(
                    Workspace.load(workspace_file),
                    workspace_file,
                    "WORK-0003",
                    "PALARI-SOFIA",
                )
                claim = started["start"]["claim"]
                claim_path = (
                    workspace_file.parent
                    / ".palari"
                    / "claims"
                    / "WORK-0003.json"
                )
                if mutation == "traversal":
                    claim["session_contract_path"] = "../outside.json"
                else:
                    contract_path = workspace_file.parent / claim["session_contract_path"]
                    outside_path = workspace_file.parent.parent / "outside-contract.json"
                    outside_path.write_bytes(contract_path.read_bytes())
                    contract_path.unlink()
                    contract_path.symlink_to(outside_path)
                claim_path.write_text(json.dumps(claim), encoding="utf-8")

                check = build_agent_check(
                    Workspace.load(workspace_file),
                    "WORK-0003",
                    "PALARI-SOFIA",
                )

                owned = self._check(check, "CLAIM_OWNED")
                self.assertEqual(owned["status"], "fail")
                message = str(owned["message"]).lower().replace("_", " ")
                self.assertIn("session contract", message)
                self.assertIn("agent start", str(owned["next_command"]))

    def test_current_packet_authority_change_stales_the_claim(self) -> None:
        with self.temp_workspace_file() as workspace_file:
            start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            raw = json.loads(workspace_file.read_text(encoding="utf-8"))
            work = next(item for item in raw["work_items"] if item["id"] == "WORK-0003")
            work["scope"] = "Tighten example onboarding copy and the launch summary."
            changed = Workspace.from_raw(raw, workspace_file.parent)

            check = build_agent_check(changed, "WORK-0003", "PALARI-SOFIA")

            owned = self._check(check, "CLAIM_OWNED")
            self.assertEqual(owned["status"], "fail")
            self.assertIn("context hash differs", str(owned["message"]))

    def test_release_and_restart_reuses_identical_contract(self) -> None:
        with self.temp_workspace_file() as workspace_file:
            workspace = Workspace.load(workspace_file)
            first = start_agent(workspace, workspace_file, "WORK-0003", "PALARI-SOFIA")
            first_claim = first["start"]["claim"]
            first_bytes = (workspace_file.parent / first_claim["session_contract_path"]).read_bytes()
            release_agent(workspace, workspace_file, "WORK-0003", "PALARI-SOFIA")
            second = start_agent(
                Workspace.load(workspace_file),
                workspace_file,
                "WORK-0003",
                "PALARI-SOFIA",
            )
            second_claim = second["start"]["claim"]
            second_bytes = (
                workspace_file.parent / second_claim["session_contract_path"]
            ).read_bytes()

            self.assertEqual(
                first_claim["session_contract_digest"],
                second_claim["session_contract_digest"],
            )
            self.assertEqual(first_bytes, second_bytes)

    def test_cli_emits_json_and_concise_text_contracts(self) -> None:
        json_result = self.run_cli(
            "agent",
            "brief",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--session-contract",
            "--json",
        )
        payload = json.loads(json_result.stdout)
        self.assertEqual(payload["schema_version"], "palari.agent_session_contract.v1")
        self.assertFalse(payload["contract"]["packet_binding"]["grants_authority"])

        text_result = self.run_cli(
            "agent",
            "brief",
            "WORK-0003",
            "--as",
            "PALARI-SOFIA",
            "--session-contract",
        )
        self.assertIn("Portable session contract:", text_result.stdout)
        self.assertIn("Grants authority: no", text_result.stdout)
        self.assertIn("adapter: none", text_result.stdout)

    @staticmethod
    def _blocker_codes(contract: dict[str, Any]) -> set[str]:
        return {
            str(item.get("code") or "")
            for item in contract["contract"]["blockers"]
        }

    @staticmethod
    def _check(payload: dict[str, Any], code: str) -> dict[str, Any]:
        return next(item for item in payload["checks"] if item["code"] == code)

    @contextmanager
    def temp_workspace_file(self) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            shutil.copytree(WORKSPACE, root, ignore=shutil.ignore_patterns(".palari"))
            yield root / "workspace.json"

    def run_cli(
        self,
        *args: str,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env.update(extra_env or {})
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "palari_company_os",
                "--workspace",
                str(WORKSPACE),
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


if __name__ == "__main__":
    unittest.main()

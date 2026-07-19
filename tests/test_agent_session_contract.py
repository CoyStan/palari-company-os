from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
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
from palari_company_os.cli_output_agent import print_agent_session_contract
from palari_company_os.pcaw_canonical import canonical_sha256
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError
from tests.workspace_fixture import write_current_agent_workspace


WORK_ID = "WORK-SESSION-CONTRACT"
PALARI_ID = "PALARI-STEWARD"
ALLOWED_PATH = "README.md"


class AgentSessionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.workspace_file = Path(self._temporary.name) / "workspace.json"
        self._write_workspace(self.workspace_file)

    def test_compiler_is_deterministic_portable_and_reports_enforcement(self) -> None:
        packet = self._packet()
        first = compile_agent_session_contract(packet)
        packet["created_at"] = "2099-12-31T23:59:59Z"
        second = compile_agent_session_contract(packet)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ready")
        binding = first["contract"]["packet_binding"]
        self.assertFalse(binding["grants_authority"])
        self.assertTrue(binding["claim_required"])
        self.assertEqual(first["contract"]["scope"]["write_paths"], [ALLOWED_PATH])
        properties = {
            item["id"]: item["status"]
            for item in first["contract"]["enforcement"]["properties"]
        }
        self.assertEqual(properties["human-authority"], "palari-enforced")
        self.assertEqual(properties["write-boundary-before-tool"], "adapter-required")
        self.assertEqual(properties["read-boundary"], "advisory")
        self.assertEqual(first["contract"]["enforcement"]["adapter"], "none")

        serialized = json.dumps(first, sort_keys=True)
        self.assertNotIn(str(self.workspace_file.parent), serialized)
        self.assertNotIn("created_at", serialized)
        self.assertNotIn("last_read_at", serialized)
        self.assertNotIn('"label"', serialized)
        self.assertNotIn('"notes"', serialized)

    def test_blocked_and_unsafe_packets_fail_closed(self) -> None:
        blocked_packet = build_agent_brief(
            Workspace.load(self.workspace_file),
            "WORK-MISSING",
            PALARI_ID,
            "execute",
        )
        blocked = compile_agent_session_contract(blocked_packet)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["contract"]["scope"]["write_paths"], [])
        self.assertIn("MISSING_WORK_ITEM", self._blocker_codes(blocked))

        for paths, message in (
            (["../outside.txt"], "unsafe path"),
            ([ALLOWED_PATH, ALLOWED_PATH], "duplicate paths"),
        ):
            with self.subTest(message=message):
                packet = self._packet()
                packet["allowed_paths"]["write"] = paths
                packet["context_hash"] = _context_hash(packet)
                with self.assertRaisesRegex(WorkspaceError, message):
                    compile_agent_session_contract(packet)

    def test_schema_tamper_and_authority_substitution_are_rejected(self) -> None:
        packet = self._packet()
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

        changed_packet = deepcopy(packet)
        changed_packet["allowed_paths"]["write"] = ["docs/changed.md"]
        changed_packet["context_hash"] = _context_hash(changed_packet)
        self.assertIn(
            "differs from the current packet authority",
            session_contract_error(contract, expected_packet=changed_packet),
        )

    def test_started_claim_binds_and_reuses_the_exact_persisted_contract(self) -> None:
        workspace = Workspace.load(self.workspace_file)
        first = start_agent(workspace, self.workspace_file, WORK_ID, PALARI_ID)
        first_claim = first["start"]["claim"]
        contract_path = self.workspace_file.parent / first_claim["session_contract_path"]
        first_bytes = contract_path.read_bytes()

        self.assertEqual(first_claim["schema_version"], "palari.agent_claim.v2")
        self.assertEqual(
            json.loads(first_bytes)["contract_digest"],
            first_claim["session_contract_digest"],
        )
        self.assertEqual(
            first["start"]["session_contract"]["contract_digest"],
            first_claim["session_contract_digest"],
        )
        check = build_agent_check(
            Workspace.load(self.workspace_file), WORK_ID, PALARI_ID
        )
        self.assertEqual(self._check(check, "CLAIM_OWNED")["status"], "pass")

        release_agent(workspace, self.workspace_file, WORK_ID, PALARI_ID)
        second = start_agent(
            Workspace.load(self.workspace_file),
            self.workspace_file,
            WORK_ID,
            PALARI_ID,
        )
        second_claim = second["start"]["claim"]
        second_bytes = (
            self.workspace_file.parent / second_claim["session_contract_path"]
        ).read_bytes()
        self.assertEqual(
            first_claim["session_contract_digest"],
            second_claim["session_contract_digest"],
        )
        self.assertEqual(first_bytes, second_bytes)

    def test_claim_check_rejects_missing_tampered_and_escaped_contracts(self) -> None:
        for mutation in ("missing", "tampered", "traversal", "symlink"):
            with self.subTest(mutation=mutation), self._fresh_workspace() as workspace_file:
                started = start_agent(
                    Workspace.load(workspace_file),
                    workspace_file,
                    WORK_ID,
                    PALARI_ID,
                )
                claim = started["start"]["claim"]
                contract_path = workspace_file.parent / claim["session_contract_path"]
                claim_path = workspace_file.parent / ".palari" / "claims" / f"{WORK_ID}.json"

                if mutation == "missing":
                    contract_path.unlink()
                elif mutation == "tampered":
                    contract = json.loads(contract_path.read_text(encoding="utf-8"))
                    contract["contract"]["scope"]["write_paths"] = ["outside.txt"]
                    contract_path.write_text(json.dumps(contract), encoding="utf-8")
                elif mutation == "traversal":
                    claim["session_contract_path"] = "../outside.json"
                    claim_path.write_text(json.dumps(claim), encoding="utf-8")
                else:
                    outside = workspace_file.parent / "outside-contract.json"
                    outside.write_bytes(contract_path.read_bytes())
                    contract_path.unlink()
                    contract_path.symlink_to(outside)

                check = build_agent_check(
                    Workspace.load(workspace_file), WORK_ID, PALARI_ID
                )
                owned = self._check(check, "CLAIM_OWNED")
                self.assertEqual(owned["status"], "fail")
                self.assertIn(
                    "session contract",
                    str(owned["message"]).lower().replace("_", " "),
                )
                self.assertIn("agent start", str(owned["next_command"]))

    def test_text_output_is_a_thin_summary_of_the_contract(self) -> None:
        contract = compile_agent_session_contract(self._packet())
        output = io.StringIO()
        with redirect_stdout(output):
            print_agent_session_contract(contract, False)

        rendered = output.getvalue()
        self.assertIn(f"Portable session contract: {contract['contract_id']}", rendered)
        self.assertIn("Grants authority: no", rendered)
        self.assertIn("adapter: none", rendered)

    def _packet(self) -> dict[str, Any]:
        return build_agent_brief(
            Workspace.load(self.workspace_file), WORK_ID, PALARI_ID, "execute"
        )

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
    def _fresh_workspace(self) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as directory:
            workspace_file = Path(directory) / "workspace.json"
            self._write_workspace(workspace_file)
            yield workspace_file

    @staticmethod
    def _write_workspace(workspace_file: Path) -> None:
        write_current_agent_workspace(workspace_file)
        store = load_store(workspace_file)
        store.data["work_items"] = [
            {
                "id": WORK_ID,
                "title": "Compile one portable agent contract",
                "goal": "GOAL-REPO-0001",
                "palari": PALARI_ID,
                "workbench_id": "WORKBENCH-REPO-FOUNDATION",
                "risk": "R1",
                "intensity": "light",
                "required_approval_count": 0,
                "scope": "Modify only the declared portable artifact.",
                "acceptance_target": "The exact contract remains bound to the claim.",
                "status": "active",
                "allowed_resources": [ALLOWED_PATH],
                "allowed_sources": ["SOURCE-REPO-FOUNDATION"],
                "output_targets": [ALLOWED_PATH],
                "path_intents": [{"path": ALLOWED_PATH, "intent": "modify"}],
                "forbidden_actions": ["deploy"],
                "verification_expectations": ["focused contract tests pass"],
            }
        ]
        for palari in store.data["palaris"]:
            if palari["id"] == PALARI_ID:
                palari["active_work"] = [WORK_ID]
        write_store(store)
        (workspace_file.parent / ALLOWED_PATH).write_text(
            "current fixture\n", encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()

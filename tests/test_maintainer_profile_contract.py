from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_packets import build_agent_brief
from palari_company_os.agent_next import build_agent_next, build_agent_next_all
from palari_company_os.agent_runtime import claim_check, read_claim
from palari_company_os.authoring import update_record
from palari_company_os.workspace import Workspace
from tests.maintainer_profile_fixture import (
    MaintainerProfileRepo,
    create_git_repository,
    git,
)


class MaintainerProfileContractTests(unittest.TestCase):
    def test_claim_binds_catalog_profile_journal_and_source_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            added = self._add_work(repo, "README.md")
            work_id = str(added["work_item"]["id"])
            started = repo.emitted_json(added["next_commands"][0])
            claim = read_claim(repo.workspace_file, work_id)

            self.assertEqual(started["start"]["status"], "claimed")
            self.assertIsNotNone(claim)
            assert claim is not None
            baseline = claim["git_baseline"]
            catalog = baseline["scope_authority_catalog"]
            profile_binding = baseline["maintainer_profile_binding"]
            snapshot = claim["governance_projection_snapshot"]
            local_witness = snapshot["maintainer_local_state_witness"]
            head = git(repo.root, "rev-parse", "HEAD").stdout.strip()

            self.assertEqual(
                catalog["schema_version"],
                "palari.preclaim_scope_catalog.v1",
            )
            self.assertTrue(catalog["bindings"])
            self.assertEqual(
                profile_binding["schema_version"],
                "palari.maintainer_claim_binding.v1",
            )
            self.assertEqual(
                profile_binding["binding_digest"],
                repo.layout().binding_digest,
            )
            self.assertEqual(snapshot["changed_paths"], [])
            self.assertEqual(snapshot["files"], [])
            self.assertEqual(
                local_witness["schema_version"],
                "palari.maintainer_local_state_witness.v1",
            )
            self.assertEqual(local_witness["source_git_head"], head)
            self.assertEqual(
                local_witness["journal_head_record_digest"],
                snapshot["journal_verification"]["head_record_digest"],
            )
            self.assertGreaterEqual(local_witness["journal_record_count"], 1)
            self.assertTrue(
                (
                    repo.runtime_root
                    / "claims"
                    / f"{work_id}.json"
                ).is_file()
            )
            self.assertEqual(repo.status(), "")
            self.assertEqual(repo.tracked_profile_paths(), [])

    def test_git_witness_and_authority_catalog_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "witness")
            repo.init_maintainer()
            added = self._add_work(repo, "README.md")
            work_id = str(added["work_item"]["id"])
            repo.emitted_json(added["next_commands"][0])
            claim = read_claim(repo.workspace_file, work_id)
            assert claim is not None
            git(repo.root, "update-ref", "-d", str(claim["git_witness_ref"]))

            checked = claim_check(
                repo.workspace_file,
                work_id,
                "PALARI-CLAUDE",
                "execute",
                str(claim["context_hash"]),
            )

            self.assertEqual(checked["status"], "fail")
            self.assertIn("Git witness", checked["message"])
            self.assertEqual(repo.status(), "")

    def test_active_lease_is_current_for_exact_profile_selector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "lease")
            repo.init_maintainer()
            added = self._add_work(repo, "README.md")
            work_id = str(added["work_item"]["id"])
            repo.emitted_json(added["next_commands"][0])

            payloads = (
                build_agent_next(
                    Workspace.load(repo.workspace_file),
                    "PALARI-CLAUDE",
                ),
                build_agent_next_all(Workspace.load(repo.workspace_file)),
            )

            for payload in payloads:
                candidates = (
                    payload["candidates"]
                    if "candidates" in payload
                    else [
                        candidate
                        for agent in payload["agents"]
                        for candidate in agent["candidates"]
                    ]
                )
                candidate = next(
                    item for item in candidates if item["work_item_id"] == work_id
                )
                blocker_codes = {
                    blocker["code"] for blocker in candidate["start_blockers"]
                }
                self.assertNotIn("WORK_ALREADY_CLAIMED", blocker_codes)
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "authority")
            repo.init_maintainer()
            added = self._add_work(repo, "README.md")
            work_id = str(added["work_item"]["id"])
            repo.emitted_json(added["next_commands"][0])
            claim = read_claim(repo.workspace_file, work_id)
            assert claim is not None
            update_record(
                str(repo.workspace_file),
                "palari",
                "PALARI-CLAUDE",
                {"scope": "Expanded after the immutable claim catalog."},
                command="test authority catalog tamper",
                actor="HUMAN-FOUNDER",
            )

            checked = claim_check(
                repo.workspace_file,
                work_id,
                "PALARI-CLAUDE",
                "execute",
                str(claim["context_hash"]),
                allow_maintainer_journal_extension=True,
            )

            self.assertEqual(checked["status"], "fail")
            self.assertIn("scope authority", checked["message"])
            self.assertEqual(repo.status(), "")

    def test_external_sensitive_and_control_state_tasks_are_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "capability")
            repo.init_maintainer()
            added = self._add_work(repo, "README.md")
            work_id = str(added["work_item"]["id"])
            update_record(
                str(repo.workspace_file),
                "work",
                work_id,
                {
                    "allowed_actions": [
                        "push",
                        "merge_pull_request",
                        "deploy",
                        "provider_write",
                        "credential_access",
                    ]
                },
                command="test denied maintainer capabilities",
                actor="HUMAN-FOUNDER",
            )

            packet = build_agent_brief(
                Workspace.load(repo.workspace_file),
                work_id,
                "PALARI-CLAUDE",
                "execute",
            )

            self.assertEqual(packet["status"], "blocked")
            blockers = {item["code"]: item for item in packet["blockers"]}
            denied = blockers["MAINTAINER_PROFILE_CAPABILITY_DENIED"]["message"]
            for action in (
                "push",
                "merge_pull_request",
                "deploy",
                "provider_write",
                "credential_access",
            ):
                self.assertIn(action, denied)
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "sensitive")
            repo.init_maintainer()
            added = self._add_work(repo, "README.md")
            work_id = str(added["work_item"]["id"])
            source_id = Workspace.load(repo.workspace_file).sources[0].id
            update_record(
                str(repo.workspace_file),
                "source",
                source_id,
                {
                    "data_class": "restricted",
                    "redaction_required": True,
                },
                command="test sensitive source",
                actor="HUMAN-FOUNDER",
            )

            packet = build_agent_brief(
                Workspace.load(repo.workspace_file),
                work_id,
                "PALARI-CLAUDE",
                "execute",
            )

            self.assertEqual(packet["status"], "blocked")
            blockers = {item["code"]: item for item in packet["blockers"]}
            self.assertIn(
                source_id,
                blockers["MAINTAINER_PROFILE_CAPABILITY_DENIED"]["message"],
            )
            self.assertEqual(repo.status(), "")

        for path in (
            ".palari-company-os.json",
            ".palari-company-os/binding.json",
            ".git/config",
            "workspace.json",
            ".palari/governance-journal.v2.jsonl",
        ):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(Path(directory) / "control-path")
                repo.init_maintainer()
                added = self._add_work(repo, path)
                work_id = str(added["work_item"]["id"])

                packet = build_agent_brief(
                    Workspace.load(repo.workspace_file),
                    work_id,
                    "PALARI-CLAUDE",
                    "execute",
                )

                self.assertEqual(packet["status"], "blocked")
                blockers = {item["code"]: item for item in packet["blockers"]}
                self.assertIn(
                    path,
                    blockers["MAINTAINER_PROFILE_STATE_PATH_DENIED"]["message"],
                )
                self.assertEqual(repo.status(), "")

        for path in (
            "./.git/config",
            "./workspace.json",
            r".git\config",
            r".palari\governance-journal.v2.jsonl",
        ):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(Path(directory) / "noncanonical")
                repo.init_maintainer()
                added = self._add_work(repo, "README.md")
                work_id = str(added["work_item"]["id"])
                workbench_id = str(added["work_item"]["workbench_id"])
                update_record(
                    str(repo.workspace_file),
                    "workbench",
                    workbench_id,
                    {"output_target_ids": ["README.md", path]},
                    command="test noncanonical maintainer workbench boundary",
                    actor="HUMAN-FOUNDER",
                )
                update_record(
                    str(repo.workspace_file),
                    "work",
                    work_id,
                    {
                        "allowed_resources": [path],
                        "output_targets": [path],
                        "path_intents": [],
                    },
                    command="test noncanonical maintainer work boundary",
                    actor="HUMAN-FOUNDER",
                )

                packet = build_agent_brief(
                    Workspace.load(repo.workspace_file),
                    work_id,
                    "PALARI-CLAUDE",
                    "execute",
                )

                self.assertEqual(packet["status"], "blocked")
                blockers = {item["code"]: item for item in packet["blockers"]}
                self.assertIn(
                    path,
                    blockers["MAINTAINER_PROFILE_STATE_PATH_DENIED"]["message"],
                )
                self.assertEqual(repo.status(), "")

    @staticmethod
    def _add_work(repo: MaintainerProfileRepo, path: str) -> dict[str, Any]:
        return repo.profile_json(
            "work",
            "add",
            "Exercise the maintainer profile contract",
            "--write",
            path,
            "--risk",
            "R2",
            "--intensity",
            "standard",
            "--approvals",
            "0",
            "--acceptance",
            "The bounded contract remains exact.",
            "--verify",
            "Deterministic checks pass.",
            "--json",
        )


if __name__ == "__main__":
    unittest.main()

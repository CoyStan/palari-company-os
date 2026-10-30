from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_advance import agent_advance
from palari_company_os.command_surface import palari_workspace_command
from palari_company_os.governance_journal import verify_workspace_journal
from palari_company_os.verification_attestations import cache_key
from palari_company_os.workspace import Workspace
from tests.maintainer_profile_fixture import create_git_repository, git


class MaintainerProfileJourneyTests(unittest.TestCase):
    def test_single_maintainer_reaches_review_and_one_human_approval_cleanly(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            root_governance_before = repo.root_governance_snapshot()
            initialized = repo.init_maintainer()
            repo.assert_exact_commands(initialized)
            self._assert_clean_and_preserved(repo, root_governance_before)

            workspace = Workspace.load(repo.workspace_file)
            self.assertEqual(
                [human.id for human in workspace.humans],
                ["HUMAN-FOUNDER"],
            )
            self.assertEqual(
                [palari.id for palari in workspace.palaris],
                ["PALARI-CLAUDE", "PALARI-REVIEWER"],
            )

            output_path = "artifacts/founder-result.txt"
            added = repo.profile_json(
                "work",
                "add",
                "Prepare one reviewed maintainer result",
                "--create",
                output_path,
                "--risk",
                "R2",
                "--intensity",
                "standard",
                "--approvals",
                "0",
                "--acceptance",
                "The exact local result is reviewed and founder-approved.",
                "--verify",
                "Bounded deterministic checks pass.",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            self.assertEqual(
                added["authority_plan"]["qualified_approver_ids"],
                ["HUMAN-FOUNDER"],
            )
            repo.assert_exact_commands(added)
            self._assert_clean_and_preserved(repo, root_governance_before)

            started = repo.emitted_json(added["next_commands"][0])
            self.assertEqual(started["start"]["status"], "claimed")
            self.assertEqual(started["entry"]["selected_work_item"], work_id)
            repo.assert_exact_commands(started)
            self._assert_clean_and_preserved(repo, root_governance_before)

            output = repo.root / output_path
            output.parent.mkdir(parents=True)
            output.write_text("exact founder-reviewed bytes\n", encoding="utf-8")
            git(repo.root, "add", "--", output_path)
            git(repo.root, "commit", "-qm", "add bounded founder result")
            candidate_head = git(repo.root, "rev-parse", "HEAD").stdout.strip()
            self._assert_clean_and_preserved(repo, root_governance_before)

            observed_profiles: list[str] = []

            def passing_attestation(
                _workspace: object,
                _repo_root: object,
                profile: Any,
                context: Any,
                **_kwargs: object,
            ) -> dict[str, Any]:
                observed_profiles.append(str(profile.id))
                key = cache_key(profile, context)
                return {
                    "cache_hit": False,
                    "attestation": {
                        "attestation_id": (
                            f"VERIFY-{profile.id.upper()}-{key[-16:].upper()}"
                        ),
                        "cache_key": key,
                        "status": "passed",
                        "duration_ms": 1,
                        "stdout_digest": "sha256:" + "1" * 64,
                        "stderr_digest": "sha256:" + "2" * 64,
                    },
                }

            with patch(
                "palari_company_os.agent_advance.run_or_reuse",
                side_effect=passing_attestation,
            ):
                advanced = agent_advance(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            self.assertEqual(
                observed_profiles,
                ["complete"],
            )
            self.assertEqual(advanced["status"], "review-required", advanced)
            repo.assert_exact_commands(advanced)
            self._assert_clean_and_preserved(repo, root_governance_before)

            review_actions = [
                action
                for action in advanced["handoff"]["agent_action_commands"]
                if action["actor"] == "PALARI-REVIEWER"
            ]
            accept_action = next(
                action
                for action in review_actions
                if "--verdict accept-ready" in action["command"]
            )
            reviewer_packet = repo.emitted_json(accept_action["packet_command"])
            repo.assert_exact_commands(reviewer_packet)
            concrete_review = next(
                item["command"]
                for item in reviewer_packet["review_context"][
                    "agent_review_commands"
                ]
                if item["reviewer"] == "PALARI-REVIEWER"
                and item["verdict"] == "accept-ready"
            )
            review_result = repo.emitted_json(concrete_review)
            self.assertEqual(review_result["action"], "created")
            self._assert_clean_and_preserved(repo, root_governance_before)

            reviewer_handoff = repo.emitted_json(
                palari_workspace_command(
                    repo.workspace_file,
                    "agent",
                    "handoff",
                    work_id,
                    "--as",
                    "PALARI-REVIEWER",
                    "--mode",
                    "review",
                    "--json",
                )
            )
            repo.assert_exact_commands(reviewer_handoff)
            human_actions = reviewer_handoff["human_action_commands"]
            self.assertEqual(len(human_actions), 1)
            human_action = human_actions[0]
            self.assertEqual(human_action["actor"], "HUMAN-FOUNDER")
            self.assertIn("--presented", human_action["command"])
            self.assertNotIn("--pack-digest", human_action["command"])
            self._assert_clean_and_preserved(repo, root_governance_before)

            approved = repo.emitted_json(human_action["command"])
            final = Workspace.load(repo.workspace_file)
            work = final.work_item(work_id)
            journal = verify_workspace_journal(repo.workspace_file)

            self.assertTrue(approved["completed"])
            self.assertFalse(approved["performed_external_effects"])
            self.assertIsNotNone(work)
            assert work is not None
            self.assertEqual(work.status, "completed")
            self.assertEqual(final.attempts[0].head_sha, candidate_head)
            self.assertEqual(final.attempts[0].actor, "PALARI-CLAUDE")
            self.assertEqual(
                final.review_verdicts[0].reviewer,
                "PALARI-REVIEWER",
            )
            self.assertEqual(
                final.human_decisions[0].human_id,
                "HUMAN-FOUNDER",
            )
            self.assertEqual(len(final.human_decisions), 1)
            self.assertEqual(len(final.acceptance_records), 1)
            self.assertTrue(journal["ok"], journal)
            self.assertTrue(journal["chain_valid"], journal)
            self.assertIsNone(journal["pending"])
            self._assert_clean_and_preserved(repo, root_governance_before)
            self.assertEqual(repo.tracked_profile_paths(), [])

    def _assert_clean_and_preserved(
        self,
        repo: Any,
        root_governance_before: dict[str, object],
    ) -> None:
        self.assertEqual(repo.status(), "")
        self.assertEqual(
            repo.root_governance_snapshot(),
            root_governance_before,
        )


if __name__ == "__main__":
    unittest.main()

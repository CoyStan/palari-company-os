from __future__ import annotations

import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.cli_output_utils import (
    plain_detail_state,
    plain_field,
    plain_message,
    plain_status,
    plain_step,
    plain_step_status,
)
from palari_company_os.cli_output import print_state
from palari_company_os.cli_output_agent import print_agent_next
from palari_company_os.cli_parser import build_parser
from palari_company_os.command_surface import palari_workspace_command


class PlainLanguageContractTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> str:
        result = subprocess.run(
            [str(REPO_ROOT / "bin" / "palari"), *arguments],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_operator_statuses_collapse_to_six_plain_states(self) -> None:
        cases = {
            "proposed": "Ready",
            "ready-for-ai-work": "Ready",
            "active": "In progress",
            "paused": "Blocked",
            "blocked": "Blocked",
            "in-review": "Needs review",
            "needs-review": "Needs review",
            "needs-human": "Needs approval",
            "needs-human-decision": "Needs approval",
            "completed": "Complete",
            "superseded": "Complete",
            "abandoned": "Complete",
        }

        self.assertEqual({plain_status(value) for value in cases}, set(cases.values()))
        for stored, visible in cases.items():
            self.assertEqual(plain_status(stored), visible)

    def test_internal_fields_have_plain_non_json_labels(self) -> None:
        self.assertEqual(plain_field("work_item"), "Task")
        self.assertEqual(plain_field("attempt"), "Run")
        self.assertEqual(plain_field("receipt"), "Run record")
        self.assertEqual(plain_field("evidence_runs"), "Check results")
        self.assertEqual(plain_field("human_decisions"), "Approvals and rejections")
        self.assertEqual(plain_field("outcome"), "Result")

    def test_structured_next_steps_have_plain_non_json_labels(self) -> None:
        self.assertEqual(plain_step("start-work"), "Start or continue task")
        self.assertEqual(plain_step("check-active-proof"), "Run checks")
        self.assertEqual(plain_step("review-handoff"), "Get independent review")
        self.assertEqual(plain_step("human-decision"), "Get human approval")
        self.assertEqual(
            plain_status(
                "needs-human-decision",
                next_step_type="human-decision",
                next_command="palari decision guide DECISION-1 --json",
            ),
            "Blocked",
        )
        self.assertEqual(
            plain_step(
                "human-decision",
                next_command="palari decision guide DECISION-1 --json",
            ),
            "Ask a human to decide",
        )
        self.assertEqual(plain_step("automatic-reconciliation"), "Finish automatically")
        self.assertEqual(plain_step("attempt-record"), "Record run")
        self.assertEqual(plain_step("claim-release"), "Release task lock")
        self.assertEqual(plain_step("work-attempt-bind"), "Tie run to task")
        self.assertEqual(plain_step("lifecycle-complete"), "Complete task")
        self.assertEqual(plain_step_status("closed-out"), "Done")
        self.assertEqual(plain_detail_state("waiting-on-evidence"), "Waiting for checks")
        self.assertEqual(plain_detail_state("blocked-by-decision"), "Waiting for decision")
        self.assertEqual(plain_detail_state("changes-requested"), "Needs changes")
        self.assertEqual(plain_detail_state("accept-ready"), "Ready for approval")
        self.assertEqual(
            plain_detail_state("authority-plan-blocked"),
            "Approval plan blocked",
        )

    def test_machine_prose_is_translated_only_at_the_text_boundary(self) -> None:
        self.assertEqual(
            plain_message(
                "Start a bounded attempt using the declared scope and authority limits."
            ),
            "Start a bounded run using the allowed files, sources, and actions.",
        )
        self.assertEqual(
            plain_message("Current exact proof requires an independent review."),
            "Current checked version requires an independent review.",
        )
        self.assertEqual(
            plain_message("Run `palari scope WORK-1 --json` for the work item."),
            "Run `palari scope WORK-1 --json` for the task.",
        )
        self.assertEqual(
            plain_message(
                "Latest recorded proof is not current: evidence EVIDENCE-0001 "
                "has no current output binding version."
            ),
            "Latest checks are not current: check result EVIDENCE-0001 "
            "is not tied to the current output bytes.",
        )
        self.assertEqual(
            plain_message("There is an attempt but no evidence run for it."),
            "There is a run but no check result for it.",
        )
        self.assertEqual(
            plain_message(
                "An attempt exists without evidence; verify before making completion claims."
            ),
            "A run exists without check results; verify before reporting completion.",
        )
        self.assertEqual(
            plain_message(
                "Repair only the reviewed findings, then refresh evidence and review."
            ),
            "Repair only the reviewed findings, then refresh checks and review.",
        )
        self.assertEqual(
            plain_message(
                "Inspect the current kernel diagnostics and repair the blocked proof."
            ),
            "Inspect the current blockers and repair the failed checks.",
        )
        self.assertEqual(
            plain_message(
                "Recorded current proof satisfies the lifecycle completion candidate."
            ),
            "Current checks allow completion.",
        )
        self.assertEqual(
            plain_message(
                "Reconcile the terminal lifecycle state from externally verified proof."
            ),
            "Finish the task from the current checked records.",
        )
        self.assertEqual(
            plain_message("Record a receipt for the current attempt."),
            "Record a run record for the current run.",
        )
        self.assertEqual(
            plain_message("Use an active qualified approver listed by the task authority plan."),
            "Use an active qualified approver listed by the task approval plan.",
        )
        self.assertEqual(
            plain_message("Do not execute WORK-1 yet; resolve the packet blockers first."),
            "Do not execute WORK-1 yet; resolve the task brief blockers first.",
        )
        self.assertEqual(
            plain_message("Repair journal continuity before continuing."),
            "Repair tamper-evident history before continuing.",
        )
        self.assertEqual(
            plain_message("Honest product claims require support."),
            "Honest product claims require support.",
        )
        for prose in (
            "Inspect the network packet before retrying.",
            "A certificate authority reviewed the artifact.",
            "Attempt to preserve customer acceptance criteria.",
        ):
            self.assertEqual(plain_message(prose), prose)
        for identifier in (
            "WORK-0001",
            "ATTEMPT-0001",
            "RECEIPT-0001",
            "EVIDENCE-0001",
            "PACKET-WORK-0001-AGENT-EXECUTE-V1",
        ):
            self.assertIn(identifier, plain_message(f"proof for {identifier}"))
        self.assertEqual(
            plain_message("next action: palari scope WORK-0001 --json"),
            "next action: palari scope WORK-0001 --json",
        )

    def test_known_review_templates_fail_closed_in_plain_language(self) -> None:
        self.assertEqual(
            plain_message(
                "Receipt is missing; confirm whether the work state intentionally "
                "relies on evidence and review instead."
            ),
            "The run record is missing; stop and return the task to the builder "
            "before review.",
        )
        self.assertEqual(
            plain_message(
                "Latest recorded proof is not current: attempt ATTEMPT-0006 "
                "has no receipt."
            ),
            "Latest checks are not current: run ATTEMPT-0006 has no run record.",
        )

    def test_unclaimed_candidate_displays_start_as_the_first_safe_action(self) -> None:
        payload = {
            "agent": {"id": "PALARI-1", "name": "Sofia"},
            "status": "ready",
            "mode": "execute",
            "ready_count": 1,
            "blocked_count": 0,
            "blockers": [],
            "candidates": [
                {
                    "work_item_id": "WORK-1",
                    "can_start": True,
                    "title": "Prepare note",
                    "attention": "needs-evidence",
                    "next_step_type": "check-active-proof",
                    "next_command": (
                        "palari agent check WORK-1 --as PALARI-1 "
                        "--mode execute --json"
                    ),
                    "claim": {"active": False, "status": "unclaimed"},
                }
            ],
            "next_allowed_commands": [
                "palari agent check WORK-1 --as PALARI-1 --mode execute --json"
            ],
        }

        output = StringIO()
        with redirect_stdout(output):
            print_agent_next(payload, False)

        rendered = output.getvalue()
        start = "palari agent start WORK-1 --as PALARI-1 --mode execute --json"
        self.assertIn(f"next: {start}", rendered)
        self.assertIn("next step: Start or continue task", rendered)
        self.assertEqual(payload["candidates"][0]["next_step_type"], "check-active-proof")

    def test_state_counts_open_questions_as_blocked_not_approval(self) -> None:
        payload = {
            "workspace": "Example",
            "counts": {},
            "attention": {"needs-human-decision": 1},
            "queue": [
                {
                    "attention": "needs-human-decision",
                    "next_step_type": "human-decision",
                    "next_commands": [
                        "palari decision guide DECISION-1 --json"
                    ],
                }
            ],
            "top_attention": None,
            "active_parallel_work": [],
            "coordination_warnings": [],
        }

        output = StringIO()
        with redirect_stdout(output):
            print_state(payload)

        rendered = output.getvalue()
        self.assertIn("Blocked: 1", rendered)
        self.assertNotIn("Needs approval: 1", rendered)

    def test_text_output_shows_task_lock_before_checks_without_changing_json(self) -> None:
        prefix = ("--workspace", "examples/acme-company-os")
        machine = json.loads(
            self.run_cli(
                *prefix,
                "agent",
                "check",
                "WORK-0001",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
                "--json",
            )
        )
        rendered_outputs = [
            self.run_cli(
                *prefix,
                "agent",
                command,
                "WORK-0001",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "execute",
            )
            for command in ("brief", "check", "finish", "loop")
        ]

        self.assertEqual(machine["next_step_type"], "check-active-proof")
        start_command = palari_workspace_command(
            REPO_ROOT / "examples" / "acme-company-os",
            "agent",
            "start",
            "WORK-0001",
            "--as",
            "PALARI-SOFIA",
            "--mode",
            "execute",
            "--json",
        )
        for rendered in rendered_outputs:
            self.assertIn("Next step: Start or continue task", rendered)
            self.assertIn(start_command, rendered)
        for rendered in rendered_outputs[2:]:
            self.assertIn("Start or continue this task before running its checks", rendered)
            self.assertNotIn("Record or refresh the missing checks", rendered)

    def test_blocked_review_text_exposes_only_read_only_recovery(self) -> None:
        rendered = self.run_cli(
            "--workspace",
            "examples/acme-company-os",
            "agent",
            "check",
            "WORK-0001",
            "--as",
            "PALARI-ALFRED",
            "--mode",
            "review",
        )

        self.assertIn("Next step: Inspect details", rendered)
        self.assertNotIn(" agent advance ", rendered)

    def test_linked_decision_is_not_presented_as_final_approval(self) -> None:
        prefix = ("--workspace", "examples/acme-company-os", "agent")
        next_output = self.run_cli(*prefix, "next", "--as", "PALARI-ALFRED")
        brief_output = self.run_cli(
            *prefix,
            "brief",
            "WORK-0002",
            "--as",
            "PALARI-ALFRED",
            "--mode",
            "execute",
        )
        check_output = self.run_cli(
            *prefix,
            "check",
            "WORK-0002",
            "--as",
            "PALARI-ALFRED",
            "--mode",
            "execute",
        )
        loop_output = self.run_cli(
            *prefix,
            "loop",
            "WORK-0002",
            "--as",
            "PALARI-ALFRED",
            "--mode",
            "execute",
        )
        finish_output = self.run_cli(
            *prefix,
            "finish",
            "WORK-0002",
            "--as",
            "PALARI-ALFRED",
        )
        doctor_output = self.run_cli(
            *prefix,
            "doctor",
            "WORK-0002",
            "--as",
            "PALARI-ALFRED",
        )

        self.assertIn("next step: Ask a human to decide", next_output)
        handoff_command = palari_workspace_command(
            REPO_ROOT / "examples" / "acme-company-os",
            "agent",
            "handoff",
            "WORK-0002",
            "--as",
            "PALARI-ALFRED",
            "--json",
        )
        for output in (brief_output, check_output, loop_output):
            self.assertIn("Next step: Ask a human to decide", output)
            self.assertIn(handoff_command, output)
            self.assertNotIn(" agent advance ", output)
            self.assertNotIn("Record or refresh the missing checks", output)
        self.assertIn("Ready for decision handoff: yes", finish_output)
        self.assertIn("Next step: Ask a human to decide", finish_output)
        self.assertNotIn(" agent advance ", finish_output)
        self.assertIn("waiting for a human answer to a linked decision", doctor_output)

    def test_review_wait_guidance_returns_missing_checks_to_builder(self) -> None:
        prefix = ("--workspace", "examples/acme-company-os", "agent")
        for command in ("finish", "loop"):
            output = self.run_cli(
                *prefix,
                command,
                "WORK-0001",
                "--as",
                "PALARI-SOFIA",
                "--mode",
                "review",
            )
            self.assertIn("Return this task to its builder", output)
            self.assertNotIn("Record or refresh the missing checks", output)

    def test_default_help_describes_the_product_without_architecture_jargon(self) -> None:
        help_text = build_parser().format_help()

        self.assertIn(
            "Make AI work reviewable with clear limits, recorded checks, and human approval.",
            help_text,
        )
        self.assertIn("Add a bounded task", help_text)
        self.assertIn("Give AI agents bounded task briefs", help_text)
        self.assertNotIn("governance kernel", help_text.lower())
        self.assertNotIn("control plane", help_text.lower())

    def test_newcomer_docs_use_plain_words(self) -> None:
        for relative in ("README.md", "AGENTS.md"):
            text = (REPO_ROOT / relative).read_text(encoding="utf-8").lower()
            self.assertNotIn("governance kernel", text, relative)
            self.assertNotIn("control plane", text, relative)
            self.assertNotIn("work item", text, relative)

        guide = (REPO_ROOT / "docs/product/plain-language.md").read_text(
            encoding="utf-8"
        )
        for visible in (
            "Ready",
            "In progress",
            "Blocked",
            "Needs review",
            "Needs approval",
            "Complete",
        ):
            self.assertIn(visible, guide)

    def test_plain_wording_does_not_rename_stored_collections(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "schemas/workspace.schema.json").read_text(encoding="utf-8")
        )

        for name in (
            "work_items",
            "attempts",
            "receipts",
            "evidence_runs",
            "review_verdicts",
            "human_decisions",
            "acceptance_records",
            "outcomes",
        ):
            self.assertIn(name, schema["properties"])
        self.assertIn("path_intents", schema["$defs"]["work_item"]["required"])
        self.assertIn("path_intents", schema["$defs"]["proposal"]["required"])


if __name__ == "__main__":
    unittest.main()

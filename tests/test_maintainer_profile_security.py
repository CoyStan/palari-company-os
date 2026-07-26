from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.agent_runtime import read_claim, start_agent
from palari_company_os.governance_journal import (
    JournalError,
    MutationMetadata,
    journal_file_path,
    transact,
    utc_timestamp,
    verify_workspace_journal,
)
from palari_company_os.linear_webhook import (
    LinearWebhookError,
    _append_event_log,
    linear_webhook_event_log_path,
)
from palari_company_os.pcaw_canonical import canonical_sha256
from palari_company_os.store import load_store, write_store
from palari_company_os.workspace import Workspace, WorkspaceError
from palari_company_os.workspace_layout import (
    MAINTAINER_STATE_ROOT,
    MAINTAINER_WORKSPACE_FILENAME,
    ORDINARY_PROFILE,
    resolve_workspace_layout,
    runtime_path,
)
from tests.maintainer_profile_fixture import (
    MaintainerProfileRepo,
    create_git_repository,
    git,
    tree_snapshot,
)


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def refresh_binding_digest(binding: dict[str, object]) -> None:
    binding["binding_digest"] = canonical_sha256(
        {
            key: value
            for key, value in binding.items()
            if key != "binding_digest"
        }
    )


class MaintainerProfileSecurityTests(unittest.TestCase):
    def test_invalid_divergent_or_unrelated_pending_history_blocks_claim_start(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "truncated")
            repo.init_maintainer()
            added = repo.profile_json(
                "work",
                "add",
                "Exercise truncated maintainer history",
                "--write",
                "README.md",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            journal = journal_file_path(repo.workspace_file)
            journal.write_bytes(journal.read_bytes()[:-1])
            workspace_before = repo.workspace_file.read_bytes()
            journal_before = journal.read_bytes()
            refs_before = git(
                repo.root,
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ).stdout

            with self.assertRaisesRegex(
                WorkspaceError,
                "journal|continuity|truncated",
            ):
                start_agent(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertEqual(repo.workspace_file.read_bytes(), workspace_before)
            self.assertEqual(journal.read_bytes(), journal_before)
            self.assertEqual(
                git(
                    repo.root,
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                ).stdout,
                refs_before,
            )
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "divergent")
            repo.init_maintainer()
            added = repo.profile_json(
                "work",
                "add",
                "Exercise divergent maintainer state",
                "--write",
                "README.md",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            raw = json.loads(repo.workspace_file.read_text(encoding="utf-8"))
            raw["name"] = "Unjournaled divergent workspace"
            write_json(repo.workspace_file, raw)
            journal = journal_file_path(repo.workspace_file)
            workspace_before = repo.workspace_file.read_bytes()
            journal_before = journal.read_bytes()
            refs_before = git(
                repo.root,
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ).stdout

            with self.assertRaisesRegex(
                WorkspaceError,
                "journal|continuity|diverg",
            ):
                start_agent(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertEqual(repo.workspace_file.read_bytes(), workspace_before)
            self.assertEqual(journal.read_bytes(), journal_before)
            self.assertEqual(
                git(
                    repo.root,
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                ).stdout,
                refs_before,
            )
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "pending")
            repo.init_maintainer()
            added = repo.profile_json(
                "work",
                "add",
                "Exercise unrelated pending maintainer state",
                "--write",
                "README.md",
                "--json",
            )
            work_id = str(added["work_item"]["id"])
            store = load_store(repo.workspace_file)
            before_data = deepcopy(store.data)
            after_data = deepcopy(store.data)
            after_data["name"] = "Unrelated pending mutation"

            def crash_hook(point: str) -> None:
                if point == "before_apply":
                    raise RuntimeError("injected unrelated pending prepare")

            with self.assertRaisesRegex(RuntimeError, "pending prepare"):
                transact(
                    repo.workspace_file,
                    before_data=before_data,
                    after_data=after_data,
                    metadata=MutationMetadata(
                        command="other command",
                        actor="PALARI-REVIEWER",
                        action="unrelated-mutation",
                        timestamp=utc_timestamp(),
                        objects=(
                            {
                                "type": "workspace",
                                "collection": "workspace",
                                "id": "UNRELATED",
                            },
                        ),
                    ),
                    apply=lambda: None,
                    crash_hook=crash_hook,
                )
            report = verify_workspace_journal(repo.workspace_file)
            self.assertEqual(report["status"], "pending-prepare", report)
            journal = journal_file_path(repo.workspace_file)
            workspace_before = repo.workspace_file.read_bytes()
            journal_before = journal.read_bytes()
            refs_before = git(
                repo.root,
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ).stdout

            with self.assertRaisesRegex(
                WorkspaceError,
                "journal|continuity|pending",
            ):
                start_agent(
                    Workspace.load(repo.workspace_file),
                    repo.workspace_file,
                    work_id,
                    "PALARI-CLAUDE",
                )

            self.assertIsNone(read_claim(repo.workspace_file, work_id))
            self.assertEqual(repo.workspace_file.read_bytes(), workspace_before)
            self.assertEqual(journal.read_bytes(), journal_before)
            self.assertEqual(
                git(
                    repo.root,
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                ).stdout,
                refs_before,
            )
            self.assertEqual(repo.status(), "")

    def test_binding_parser_rejects_non_strict_or_changed_authority_without_writes(
        self,
    ) -> None:
        def missing_field(binding: dict[str, object]) -> None:
            binding.pop("state_root")

        cases = {
            "unknown-field": (
                lambda binding: binding.__setitem__("unknown", True),
                "unexpected or missing fields",
            ),
            "missing-field": (
                missing_field,
                "unexpected or missing fields",
            ),
            "unsupported-schema": (
                lambda binding: binding.__setitem__(
                    "schema_version",
                    "palari.maintainer-binding.v999",
                ),
                "schema_version is unsupported",
            ),
            "wrong-profile": (
                lambda binding: binding.__setitem__("profile", "ordinary"),
                "profile is unsupported",
            ),
            "wrong-workspace": (
                lambda binding: binding.__setitem__(
                    "workspace_file",
                    "workspace.json",
                ),
                "workspace_file is unsupported",
            ),
            "wrong-state-root": (
                lambda binding: binding.__setitem__(
                    "state_root",
                    ".palari-company-os-copy",
                ),
                "state_root is unsupported",
            ),
            "invalid-state-id": (
                lambda binding: binding.__setitem__("state_id", "not-a-uuid"),
                "state_id must be a UUIDv4",
            ),
            "digest-mismatch": (
                lambda binding: binding.__setitem__(
                    "binding_digest",
                    "sha256:" + "0" * 64,
                ),
                "digest does not match",
            ),
        }
        for name, (mutate, expected) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(Path(directory) / "source")
                repo.init_maintainer()
                binding = json.loads(
                    repo.binding_file.read_text(encoding="utf-8")
                )
                mutate(binding)
                write_json(repo.binding_file, binding)
                before = repo.safety_snapshot()

                with self.assertRaisesRegex(WorkspaceError, expected):
                    Workspace.load(repo.workspace_file)

                self.assertEqual(repo.safety_snapshot(), before)

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            raw = repo.binding_file.read_text(encoding="utf-8")
            marker = '  "profile": "maintainer",\n'
            self.assertIn(marker, raw)
            repo.binding_file.write_text(
                raw.replace(marker, marker + marker, 1),
                encoding="utf-8",
            )
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(WorkspaceError, "duplicate"):
                load_store(repo.workspace_file)

            self.assertEqual(repo.safety_snapshot(), before)

    def test_repository_identifier_is_strict_and_must_match_binding(
        self,
    ) -> None:
        malformed_cases = {
            "unknown-field": {
                "schema_version": "palari.maintainer-repository.v1",
                "repository_id": str(uuid4()),
                "unknown": True,
            },
            "unsupported-schema": {
                "schema_version": "palari.maintainer-repository.v999",
                "repository_id": str(uuid4()),
            },
            "invalid-id": {
                "schema_version": "palari.maintainer-repository.v1",
                "repository_id": "not-a-uuid",
            },
        }
        for name, payload in malformed_cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as directory:
                repo = create_git_repository(Path(directory) / "source")
                repo.init_maintainer()
                write_json(repo.repository_id_file, payload)
                before = repo.safety_snapshot()

                with self.assertRaises(WorkspaceError):
                    resolve_workspace_layout(repo.workspace_file)

                self.assertEqual(repo.safety_snapshot(), before)

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            write_json(
                repo.repository_id_file,
                {
                    "schema_version": "palari.maintainer-repository.v1",
                    "repository_id": str(uuid4()),
                },
            )
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "different Git repository",
            ):
                Workspace.load(repo.workspace_file)

            self.assertEqual(repo.safety_snapshot(), before)

    def test_exact_clone_cannot_reuse_copied_profile_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            source = create_git_repository(parent / "source")
            source.init_maintainer()
            clone_root = parent / "clone"
            subprocess.run(
                ["git", "clone", "-q", str(source.root), str(clone_root)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            git(clone_root, "config", "user.name", "Maintainer Clone Test")
            git(
                clone_root,
                "config",
                "user.email",
                "maintainer-clone@example.invalid",
            )
            clone = MaintainerProfileRepo(clone_root)
            clone.init_maintainer()
            clone_repository_id = clone.repository_id_file.read_bytes()
            source_repository_id = source.repository_id_file.read_bytes()
            self.assertNotEqual(clone_repository_id, source_repository_id)
            self.assertEqual(
                git(source.root, "rev-parse", "HEAD").stdout,
                git(clone.root, "rev-parse", "HEAD").stdout,
            )

            clone.copy_profile_state_from(source)
            before = clone.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "different Git repository",
            ):
                Workspace.load(clone.workspace_file)

            self.assertEqual(clone.safety_snapshot(), before)
            self.assertEqual(
                clone.repository_id_file.read_bytes(),
                clone_repository_id,
            )
            self.assertEqual(clone.status(), "")

    def test_load_rechecks_ignore_and_untracked_requirements(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            git(
                repo.root,
                "add",
                "-f",
                "--",
                MAINTAINER_WORKSPACE_FILENAME,
            )
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "must not be tracked",
            ):
                Workspace.load(repo.workspace_file)

            self.assertEqual(repo.safety_snapshot(), before)

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            exclude = repo.exclude_file.read_text(encoding="utf-8")
            filtered = "\n".join(
                line
                for line in exclude.splitlines()
                if "palari-company-os" not in line
            )
            repo.exclude_file.write_text(filtered + "\n", encoding="utf-8")
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "is not ignored",
            ):
                load_store(repo.workspace_file)

            self.assertEqual(repo.safety_snapshot(), before)

    def test_each_runtime_target_rechecks_higher_precedence_ignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            with (repo.root / ".gitignore").open("a", encoding="utf-8") as stream:
                stream.write(
                    "\n".join(
                        (
                            "!/.palari-company-os/",
                            "/.palari-company-os/binding.json",
                            "!/.palari-company-os/.palari/",
                            "/.palari-company-os/.palari/*",
                            (
                                "/.palari-company-os/.palari/"
                                "governance-journal.v2.jsonl"
                            ),
                            "!/.palari-company-os/.palari/claims/",
                            "/.palari-company-os/.palari/claims/*",
                            "!/.palari-company-os/.palari/claims/x",
                            "!/.palari-company-os/.palari/locks/",
                            "/.palari-company-os/.palari/locks/*",
                            (
                                "!/.palari-company-os/.palari/locks/"
                                ".palari-company-os.json.lock"
                            ),
                            "",
                        )
                    )
                )
            git(repo.root, "add", "--", ".gitignore")
            git(repo.root, "commit", "-qm", "add adversarial ignore exceptions")
            self.assertEqual(repo.status(), "")

            with self.assertRaisesRegex(WorkspaceError, "is not ignored"):
                runtime_path(repo.workspace_file, ".palari/claims/x")

            store = load_store(repo.workspace_file)
            store.data["name"] = "must not acquire an unignored lock"
            before = repo.safety_snapshot()
            with self.assertRaisesRegex(WorkspaceError, "is not ignored"):
                write_store(store)
            self.assertEqual(repo.safety_snapshot(), before)

            claim = repo.runtime_root / "claims" / "x"
            claim.parent.mkdir(exist_ok=True)
            claim.write_text("unignored runtime state\n", encoding="utf-8")
            with self.assertRaisesRegex(
                WorkspaceError,
                "tracked or unignored paths",
            ):
                resolve_workspace_layout(repo.workspace_file)

    def test_interrupted_workspace_replace_leaves_only_ignored_runtime_staging(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            workspace_before = repo.workspace_file.read_bytes()
            root_before = repo.root_governance_snapshot()
            script = """
import os
import signal
import sys
from pathlib import Path
from palari_company_os import store

def crash_before_replace(source, target):
    os.kill(os.getpid(), signal.SIGKILL)

store.os.replace = crash_before_replace
store._atomic_replace_text(
    Path(sys.argv[1]),
    '{"sensitive": "governance snapshot"}\\n',
)
"""

            result = subprocess.run(
                [sys.executable, "-S", "-c", script, str(repo.workspace_file)],
                cwd=repo.root,
                env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertEqual(result.returncode, -9, result)
            self.assertEqual(repo.workspace_file.read_bytes(), workspace_before)
            self.assertEqual(repo.root_governance_snapshot(), root_before)
            self.assertEqual(repo.status(), "")
            staged = list(repo.runtime_root.glob("workspace-stage-*.tmp"))
            self.assertEqual(len(staged), 1, staged)
            self.assertIn("sensitive", staged[0].read_text(encoding="utf-8"))
            relative = staged[0].relative_to(repo.root).as_posix()
            self.assertTrue(repo.path_is_ignored(relative))
            self.assertFalse(list(repo.root.glob("tmp*")))
            self.assertFalse(list(repo.root.glob("workspace-stage-*.tmp")))

    def test_runtime_files_reject_hard_links_and_non_regular_targets_before_io(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "hard-link")
            repo.init_maintainer()
            journal = journal_file_path(repo.workspace_file)
            alias = repo.root / ".palari" / "hardlinked-maintainer-journal.jsonl"
            try:
                os.link(journal, alias)
            except OSError as exc:
                self.skipTest(f"filesystem does not support hard links: {exc}")
            git(repo.root, "add", "--", alias.relative_to(repo.root).as_posix())
            git(repo.root, "commit", "-qm", "track an adversarial journal alias")
            workspace_before = repo.workspace_file.read_bytes()
            alias_before = alias.read_bytes()

            result = repo.run_cli(
                "--workspace",
                str(repo.workspace_file),
                "work",
                "add",
                "Must reject a hard-linked runtime journal",
                "--write",
                "README.md",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hard link", result.stdout + result.stderr)
            self.assertEqual(repo.workspace_file.read_bytes(), workspace_before)
            self.assertEqual(alias.read_bytes(), alias_before)
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "linear-hard-link")
            repo.init_maintainer()
            event_log = linear_webhook_event_log_path(repo.workspace_file)
            event_log.write_text('{"seed": true}\n', encoding="utf-8")
            alias = Path(directory) / "linear-event-log-alias.jsonl"
            os.link(event_log, alias)
            event_before = event_log.read_bytes()

            with self.assertRaisesRegex(
                LinearWebhookError,
                "hard link|unaliased",
            ):
                _append_event_log(
                    repo.workspace_file,
                    {"delivery_id": "must-not-append"},
                )

            self.assertEqual(event_log.read_bytes(), event_before)
            self.assertEqual(alias.read_bytes(), event_before)
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "generic-hard-link")
            repo.init_maintainer()
            claim = repo.runtime_root / "claims" / "generic.json"
            claim.parent.mkdir()
            claim.write_text('{"claim": true}\n', encoding="utf-8")
            alias = Path(directory) / "generic-claim-alias.json"
            os.link(claim, alias)

            with self.assertRaisesRegex(WorkspaceError, "hard link"):
                runtime_path(
                    repo.workspace_file,
                    ".palari/claims/generic.json",
                    require_exists=True,
                )

            self.assertEqual(claim.read_bytes(), alias.read_bytes())
            self.assertEqual(repo.status(), "")

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "fifo")
            repo.init_maintainer()
            journal = journal_file_path(repo.workspace_file)
            journal.unlink()
            try:
                os.mkfifo(journal)
            except OSError as exc:
                self.skipTest(f"filesystem does not support FIFOs: {exc}")
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "regular file or real directory",
            ):
                runtime_path(
                    repo.workspace_file,
                    ".palari/governance-journal.v2.jsonl",
                )

            self.assertEqual(repo.safety_snapshot(), before)

        with tempfile.TemporaryDirectory() as directory:
            ordinary = create_git_repository(Path(directory) / "ordinary")
            target = ordinary.root / ".palari" / "ordinary-runtime.json"
            target.write_text('{"ordinary": true}\n', encoding="utf-8")
            alias = Path(directory) / "ordinary-runtime-alias.json"
            os.link(target, alias)

            self.assertEqual(
                runtime_path(
                    ordinary.root / "workspace.json",
                    ".palari/ordinary-runtime.json",
                    require_exists=True,
                ),
                target,
            )
            self.assertEqual(target.read_bytes(), alias.read_bytes())

    def test_opened_append_file_is_rechecked_for_a_hard_link_race(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "append-race")
            repo.init_maintainer()
            event_log = linear_webhook_event_log_path(repo.workspace_file)
            event_log.write_text('{"seed": true}\n', encoding="utf-8")
            event_before = event_log.read_bytes()
            alias = Path(directory) / "event-log-alias.jsonl"
            original_open = os.open

            def hard_link_before_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
            ) -> int:
                if Path(path) == event_log and not alias.exists():
                    os.link(event_log, alias)
                return original_open(path, flags, mode)

            with (
                patch(
                    "palari_company_os.linear_webhook.os.open",
                    side_effect=hard_link_before_open,
                ),
                self.assertRaisesRegex(
                    LinearWebhookError,
                    "hard link|unaliased",
                ),
            ):
                _append_event_log(
                    repo.workspace_file,
                    {"delivery_id": "must-not-append"},
                )

            self.assertEqual(event_log.read_bytes(), event_before)
            self.assertEqual(alias.read_bytes(), event_before)
            self.assertEqual(repo.status(), "")

    def test_binding_and_workspace_compare_and_swap_fail_before_palari_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            store = load_store(repo.workspace_file)
            store.data["name"] = "must not persist after binding race"
            binding = json.loads(
                repo.binding_file.read_text(encoding="utf-8")
            )
            binding["state_id"] = str(uuid4())
            refresh_binding_digest(binding)
            write_json(repo.binding_file, binding)
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "binding changed",
            ):
                write_store(store)

            self.assertEqual(repo.safety_snapshot(), before)

        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            store = load_store(repo.workspace_file)
            store.data["name"] = "must not persist after workspace race"
            raw = json.loads(repo.workspace_file.read_text(encoding="utf-8"))
            raw["name"] = "concurrent local edit"
            write_json(repo.workspace_file, raw)
            before = repo.safety_snapshot()

            with self.assertRaisesRegex(
                WorkspaceError,
                "workspace changed since it was loaded",
            ):
                write_store(store)

            self.assertEqual(repo.safety_snapshot(), before)

    def test_lexical_traversal_and_sibling_prefix_never_select_profile_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = create_git_repository(Path(directory) / "source")
            repo.init_maintainer()
            traversal = Path(
                f"{repo.root}/nested/../{MAINTAINER_WORKSPACE_FILENAME}"
            )

            with self.assertRaisesRegex(WorkspaceError, "must not contain"):
                resolve_workspace_layout(traversal)

            sibling_file = repo.root / f"{MAINTAINER_WORKSPACE_FILENAME}.copy"
            sibling_layout = resolve_workspace_layout(
                sibling_file,
                require_workspace=False,
            )
            self.assertEqual(sibling_layout.profile, ORDINARY_PROFILE)
            self.assertEqual(sibling_layout.data_path, sibling_file)

            sibling_root = repo.root / f"{MAINTAINER_STATE_ROOT}-copy"
            repo.state_root.rename(sibling_root)
            before_sibling = tree_snapshot(sibling_root)
            with self.assertRaisesRegex(
                WorkspaceError,
                "state root is not a real directory",
            ):
                resolve_workspace_layout(repo.workspace_file)
            self.assertEqual(tree_snapshot(sibling_root), before_sibling)

    def test_reserved_selector_never_downgrades_a_directory_to_ordinary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            repo = create_git_repository(parent / "source")
            repo.init_maintainer()
            repo.workspace_file.unlink()
            repo.workspace_file.mkdir()
            (repo.workspace_file / "workspace.json").write_text(
                (repo.root / "workspace.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(WorkspaceError, "exact regular file"):
                resolve_workspace_layout(repo.workspace_file)

            for child in repo.workspace_file.iterdir():
                child.unlink()
            repo.workspace_file.rmdir()
            outside = parent / "outside"
            outside.mkdir()
            (outside / "workspace.json").write_text("{}\n", encoding="utf-8")
            repo.workspace_file.symlink_to(outside, target_is_directory=True)
            outside_before = tree_snapshot(outside)

            with self.assertRaisesRegex(WorkspaceError, "exact regular file|symlink"):
                resolve_workspace_layout(repo.workspace_file)

            self.assertEqual(tree_snapshot(outside), outside_before)

    def test_profile_path_symlinks_fail_closed_without_touching_targets(
        self,
    ) -> None:
        cases = (
            "workspace",
            "state-root",
            "binding",
            "runtime",
            "journal",
            "journal-internal",
            "repository-id",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory)
                repo = create_git_repository(parent / "source")
                repo.init_maintainer()
                outside = parent / "outside"
                outside.mkdir()

                if case == "workspace":
                    target = outside / "workspace.json"
                    repo.workspace_file.replace(target)
                    repo.workspace_file.symlink_to(target)
                elif case == "state-root":
                    target = outside / "state"
                    repo.state_root.rename(target)
                    repo.state_root.symlink_to(target, target_is_directory=True)
                elif case == "binding":
                    target = outside / "binding.json"
                    repo.binding_file.replace(target)
                    repo.binding_file.symlink_to(target)
                elif case == "runtime":
                    target = outside / "runtime"
                    repo.runtime_root.rename(target)
                    repo.runtime_root.symlink_to(target, target_is_directory=True)
                elif case == "journal":
                    journal = journal_file_path(repo.workspace_file)
                    target = outside / "journal.jsonl"
                    journal.replace(target)
                    journal.symlink_to(target)
                elif case == "journal-internal":
                    journal = journal_file_path(repo.workspace_file)
                    target = repo.runtime_root / "journal-target.jsonl"
                    journal.replace(target)
                    journal.symlink_to(target.name)
                else:
                    target = outside / "repository.json"
                    repo.repository_id_file.replace(target)
                    repo.repository_id_file.symlink_to(target)

                target_before = tree_snapshot(target)
                before = repo.safety_snapshot()
                with self.assertRaises((WorkspaceError, JournalError)) as caught:
                    if case.startswith("journal"):
                        verify_workspace_journal(repo.workspace_file)
                    else:
                        resolve_workspace_layout(repo.workspace_file)
                message = str(caught.exception).lower()
                self.assertTrue(
                    "symlink" in message or "escapes" in message,
                    message,
                )
                self.assertEqual(tree_snapshot(target), target_before)
                self.assertEqual(repo.safety_snapshot(), before)

    def test_symlinked_repository_root_is_rejected_before_initialization(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            repo = create_git_repository(parent / "source")
            alias = parent / "source-alias"
            alias.symlink_to(repo.root, target_is_directory=True)
            before = repo.safety_snapshot()

            result = repo.run_cli(
                "init",
                str(alias),
                "--profile",
                "maintainer",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not be a symlink", result.stdout + result.stderr)
            self.assertEqual(repo.safety_snapshot(), before)

            parent_alias = parent / "parent-alias"
            parent_alias.symlink_to(parent, target_is_directory=True)
            result = repo.run_cli(
                "init",
                str(parent_alias / "source"),
                "--profile",
                "maintainer",
                "--json",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("path components", result.stdout + result.stderr)
            self.assertEqual(repo.safety_snapshot(), before)


if __name__ == "__main__":
    unittest.main()

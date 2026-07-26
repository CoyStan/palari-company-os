from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.workspace_layout import (
    MAINTAINER_BINDING_FILENAME,
    MAINTAINER_REPOSITORY_ID_FILENAME,
    MAINTAINER_STATE_ROOT,
    MAINTAINER_WORKSPACE_FILENAME,
    RUNTIME_ROOT,
    resolve_workspace_layout,
)
from tests.workspace_fixture import write_current_agent_workspace


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=check,
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
        timeout=30,
    )


def create_git_repository(
    root: Path,
    *,
    ordinary_workspace: bool = True,
    object_format: str = "",
) -> "MaintainerProfileRepo":
    root.mkdir(parents=True)
    init_arguments = ["init", "-q", "-b", "main"]
    if object_format:
        init_arguments.append(f"--object-format={object_format}")
    git(root, *init_arguments)
    git(root, "config", "user.name", "Maintainer Profile Test")
    git(root, "config", "user.email", "maintainer-profile@example.invalid")
    git(root, "config", "commit.gpgSign", "false")
    (root / "README.md").write_text("tracked source candidate\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        "# tracked project ignore policy; maintainer init must not edit this\n",
        encoding="utf-8",
    )
    if ordinary_workspace:
        write_current_agent_workspace(root / "workspace.json")
        historical = root / ".palari" / "historical-sentinel.txt"
        historical.parent.mkdir(parents=True, exist_ok=True)
        historical.write_bytes(b"tracked historical governance sentinel\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "tracked source and ordinary governance")
    return MaintainerProfileRepo(root)


def tree_snapshot(path: Path) -> tuple[tuple[str, str, bytes], ...]:
    """Return an exact bounded snapshot suitable for no-write assertions."""

    if path.is_symlink():
        return ((".", "symlink", os.fsencode(os.readlink(path))),)
    if not path.exists():
        return ()
    if path.is_file():
        return ((".", "file", path.read_bytes()),)
    records: list[tuple[str, str, bytes]] = [(".", "directory", b"")]
    for candidate in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        relative = candidate.relative_to(path).as_posix()
        mode = candidate.lstat().st_mode
        if stat.S_ISLNK(mode):
            records.append(
                (relative, "symlink", os.fsencode(os.readlink(candidate)))
            )
        elif stat.S_ISDIR(mode):
            records.append((relative, "directory", b""))
        elif stat.S_ISREG(mode):
            records.append((relative, "file", candidate.read_bytes()))
        else:
            records.append((relative, "other", b""))
    return tuple(records)


def palari_commands(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from palari_commands(item)
    elif isinstance(value, list):
        for item in value:
            yield from palari_commands(item)
    elif isinstance(value, str) and value.lstrip().startswith("palari "):
        yield value


@dataclass(frozen=True)
class MaintainerProfileRepo:
    root: Path

    @property
    def workspace_file(self) -> Path:
        return self.root / MAINTAINER_WORKSPACE_FILENAME

    @property
    def state_root(self) -> Path:
        return self.root / MAINTAINER_STATE_ROOT

    @property
    def runtime_root(self) -> Path:
        return self.state_root / RUNTIME_ROOT

    @property
    def binding_file(self) -> Path:
        return self.state_root / MAINTAINER_BINDING_FILENAME

    @property
    def common_dir(self) -> Path:
        raw = git(self.root, "rev-parse", "--git-common-dir").stdout.strip()
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        return candidate.resolve()

    @property
    def repository_id_file(self) -> Path:
        return self.common_dir / MAINTAINER_REPOSITORY_ID_FILENAME

    @property
    def exclude_file(self) -> Path:
        raw = git(self.root, "rev-parse", "--git-path", "info/exclude").stdout.strip()
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        return candidate.resolve(strict=False)

    def run_cli(
        self,
        *arguments: str,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        environment = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
        return subprocess.run(
            [sys.executable, "-S", "-m", "palari_company_os", *arguments],
            cwd=self.root,
            env=environment,
            check=check,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def run_json(self, *arguments: str) -> dict[str, Any]:
        result = self.run_cli(*arguments)
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise AssertionError(f"CLI did not return an object: {payload!r}")
        return payload

    def init_maintainer(self) -> dict[str, Any]:
        return self.run_json(
            "init",
            str(self.root),
            "--profile",
            "maintainer",
            "--json",
        )

    def profile_json(self, *arguments: str) -> dict[str, Any]:
        return self.run_json(
            "--workspace",
            str(self.workspace_file),
            *arguments,
        )

    def emitted_json(self, command: str) -> dict[str, Any]:
        arguments = shlex.split(command)
        if not arguments or arguments[0] != "palari":
            raise AssertionError(f"not a Palari command: {command}")
        return self.run_json(*arguments[1:])

    def status(self) -> str:
        return git(
            self.root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ).stdout

    def tracked_profile_paths(self) -> list[str]:
        raw = git(
            self.root,
            "ls-files",
            "-z",
            "--",
            MAINTAINER_WORKSPACE_FILENAME,
            MAINTAINER_STATE_ROOT,
        ).stdout
        return [item for item in raw.split("\0") if item]

    def path_is_ignored(self, relative: str) -> bool:
        result = git(
            self.root,
            "check-ignore",
            "--no-index",
            "--quiet",
            "--",
            relative,
            check=False,
        )
        return result.returncode == 0

    def root_governance_snapshot(self) -> dict[str, object]:
        return {
            "workspace": tree_snapshot(self.root / "workspace.json"),
            "runtime": tree_snapshot(self.root / ".palari"),
            "gitignore": tree_snapshot(self.root / ".gitignore"),
        }

    def safety_snapshot(self) -> dict[str, object]:
        return {
            "workspace": tree_snapshot(self.workspace_file),
            "state": tree_snapshot(self.state_root),
            "repository_id": tree_snapshot(self.repository_id_file),
            "exclude": tree_snapshot(self.exclude_file),
            "refs": git(
                self.root,
                "for-each-ref",
                "--format=%(refname) %(objectname)",
            ).stdout,
            "worktrees": git(self.root, "worktree", "list", "--porcelain").stdout,
            "status": self.status(),
        }

    def assert_exact_commands(self, payload: object) -> list[str]:
        commands = list(palari_commands(payload))
        for command in commands:
            tokens = shlex.split(command)
            if tokens[:3] != [
                "palari",
                "--workspace",
                str(self.workspace_file),
            ]:
                raise AssertionError(
                    f"command does not select exact maintainer workspace: {command}"
                )
        return commands

    def layout(self):
        return resolve_workspace_layout(self.workspace_file)

    def copy_profile_state_from(self, source: "MaintainerProfileRepo") -> None:
        if self.workspace_file.exists() or self.workspace_file.is_symlink():
            self.workspace_file.unlink()
        if self.state_root.exists() and not self.state_root.is_symlink():
            shutil.rmtree(self.state_root)
        shutil.copy2(source.workspace_file, self.workspace_file)
        shutil.copytree(source.state_root, self.state_root)

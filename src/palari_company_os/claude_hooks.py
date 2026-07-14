"""Claude Code enforcement adapter.

This module turns the agent packet write boundary into structural enforcement
for Claude Code sessions instead of a voluntary contract:

- ``PreToolUse`` denies ``Write``/``Edit``/``NotebookEdit`` calls that target
  files outside the active claim's write boundary before the write happens,
  and asks a human when a Bash command looks like it writes outside it.
- ``Stop`` blocks Claude from finishing a turn while ``git status`` shows
  changes outside the boundary, so shell writes cannot slip through silently.
- ``SessionStart`` injects the active packet contract into Claude's context.

Hook handlers reconcile persisted claim and packet files under ``.palari/``
against the current workspace packet before granting execute-mode writes.
They also stop agent shells from invoking human-attributed Palari mutations
and require approval for opaque interpreters or Git witness mutations.
They never mutate the workspace.
Handlers must never crash the Claude Code tool flow: every entry point
catches errors and degrades to "no decision".
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

from .agent_file_changes import git_repo_root, inspect_file_changes
from .agent_runtime import load_active_claim_contexts
from .path_policy import canonical_path_allowed, resolve_workspace_path, validate_workspace_path
from .store import workspace_file_path

HOOK_EVENTS = ("pre-tool-use", "stop", "session-start")
FILE_WRITE_TOOLS = {"Write": "file_path", "Edit": "file_path", "NotebookEdit": "notebook_path"}
PRE_TOOL_USE_MATCHER = "Write|Edit|NotebookEdit|Bash"
HOOK_COMMAND_MARKER = "claude hook"
HOOK_TIMEOUT_SECONDS = 20
_REDIRECT_NO_TARGET = "\x00"
_REDIRECT_FD_OR_TARGET = "\x01"
BASH_WRITE_COMMANDS = {
    "cp",
    "dd",
    "install",
    "ln",
    "mkdir",
    "mv",
    "rm",
    "rmdir",
    "tee",
    "touch",
    "truncate",
}
OPAQUE_INTERPRETERS = {
    "alias",
    "bash",
    "builtin",
    "command",
    "deno",
    "env",
    "eval",
    "exec",
    "find",
    "fish",
    "node",
    "nohup",
    "perl",
    "php",
    "python",
    "python3",
    "ruby",
    "sh",
    "sudo",
    "time",
    "xargs",
    "zsh",
}
GIT_WITNESS_MUTATIONS = {
    "checkout",
    "gc",
    "reflog",
    "replace",
    "reset",
    "switch",
    "update-ref",
}
SAFE_GIT_READ_SUBCOMMANDS = {
    "blame",
    "cat-file",
    "describe",
    "diff",
    "diff-tree",
    "for-each-ref",
    "grep",
    "log",
    "ls-files",
    "ls-tree",
    "merge-base",
    "name-rev",
    "rev-list",
    "rev-parse",
    "show",
    "show-ref",
    "status",
}
SAFE_GIT_OBSERVABLE_WRITE_SUBCOMMANDS = {"mv", "rm"}
SAFE_TARGET_FREE_COMMANDS = {
    "basename",
    "cat",
    "cmp",
    "cut",
    "diff",
    "dirname",
    "du",
    "echo",
    "grep",
    "head",
    "ls",
    "printf",
    "pwd",
    "readlink",
    "realpath",
    "rg",
    "stat",
    "tail",
    "true",
    "wc",
    "which",
}
GIT_EXECUTION_GLOBAL_OPTIONS = {
    "-C",
    "-c",
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--paginate",
    "-p",
    "--work-tree",
}
GIT_EXECUTION_OPTIONS = {
    "--ext-diff",
    "--filters",
    "--open-files-in-pager",
    "--show-signature",
    "--textconv",
}
RG_EXECUTION_OPTIONS = {"--hostname-bin", "--pre"}
GIT_INDIRECT_PATH_OPTIONS = {"--pathspec-from-file"}
GIT_GLOBAL_OPTIONS_WITH_VALUE = {
    "-C",
    "-c",
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
}
GIT_GLOBAL_OPTIONS_WITH_ATTACHED_VALUE = {
    "--config-env=",
    "--exec-path=",
    "--git-dir=",
    "--namespace=",
    "--super-prefix=",
    "--work-tree=",
}
HUMAN_ONLY_PALARI_COMMANDS = {
    ("decision", "create"),
    ("decision", "update"),
    ("human-decision", "record"),
    ("human-decision", "update"),
    ("integration", "approve"),
    ("integration", "cancel"),
    ("integration", "enqueue"),
    ("integration", "outbox-cancel"),
    ("integration", "reject"),
    ("lifecycle", "complete"),
    ("lifecycle", "decide"),
    ("lifecycle", "outcome"),
    ("lifecycle", "review"),
    ("linear", "send"),
    ("outcome", "record"),
    ("outcome", "update"),
    ("proposal", "adopt"),
    ("proposal", "defer"),
    ("proposal", "reject"),
    ("review", "record"),
    ("review", "update"),
    ("work", "accept"),
    ("work", "complete"),
}
PACKET_AUTHORITY_PALARI_COMMANDS = {
    (kind, action)
    for kind in (
        "authority-profile",
        "capability",
        "goal",
        "human",
        "palari",
        "playbook-source",
        "source",
        "work",
        "workbench",
    )
    for action in ("create", "update")
} | {("work", "add")}

# These commands are either read-only or perform the bounded agent/runtime
# transitions that the packet contract explicitly asks an agent to run. New
# commands do not inherit this list: an unclassified Palari command asks a
# human instead of silently acquiring a shell-hook bypass.
SAFE_AGENT_PALARI_COMMANDS = {
    ("agent", action)
    for action in (
        "brief",
        "check",
        "doctor",
        "done",
        "finish",
        "handoff",
        "loop",
        "next",
        "release",
        "start",
    )
} | {
    ("attempt", action) for action in ("closeout", "record", "update")
} | {
    ("authority", action) for action in ("check", "profiles")
} | {
    ("capability", action) for action in ("check", "export-policy", "list")
} | {
    ("claude", "status"),
    ("data", "map"),
    ("decision", "guide"),
    ("docs", "check"),
    ("docs", "map"),
    ("evidence", "record"),
    ("evidence", "update"),
    ("evidence", "verify"),
    ("gate", "profiles"),
    ("gate", "recommend"),
    ("git", "pre-commit"),
    ("git", "status"),
    ("integration", "check"),
    ("integration", "outbox-check"),
    ("integration", "plan"),
    ("lifecycle", "evidence"),
    ("linear", "block-template"),
    ("linear", "doctor"),
    ("linear", "import"),
    ("linear", "inspect-block"),
    ("linear", "issue"),
    ("linear", "issues"),
    ("linear", "linked"),
    ("linear", "post-gate"),
    ("linear", "push"),
    ("linear", "start"),
    ("linear", "status"),
    ("linear", "sync"),
    ("linear", "webhook-events"),
    ("linear", "webhook-verify"),
    ("maintainer", "status"),
    ("playbooks", "recommend"),
    ("playbooks", "sources"),
    ("proposal", "create"),
    ("proposal", "update"),
    ("receipt", "record"),
    ("receipt", "update"),
    ("review", "guide"),
    ("work", "expand-scope"),
} | {
    (command, "")
    for command in (
        "detail",
        "history",
        "integrations",
        "queue",
        "scope",
        "state",
        "validate",
    )
}

PALARI_SELF_PROTECTION_COMMANDS = {
    ("claude", "install"),
    ("git", "install"),
}
MUTATING_AGENT_PALARI_COMMANDS = {
    ("agent", action) for action in ("done", "release", "start")
} | {
    ("attempt", action) for action in ("closeout", "record", "update")
} | {
    ("evidence", action) for action in ("record", "update")
} | {
    ("integration", "plan"),
    ("lifecycle", "evidence"),
    ("linear", "import"),
    ("linear", "post-gate"),
    ("linear", "push"),
    ("linear", "start"),
    ("linear", "sync"),
    ("proposal", "create"),
    ("proposal", "update"),
    ("receipt", "record"),
    ("receipt", "update"),
    ("work", "expand-scope"),
}
SHELL_COMMAND_SEPARATORS = {"&&", "||", ";", "|", "|&", "&"}


def run_hook(
    event: str,
    workspace_path: Path | str,
    *,
    strict: bool = False,
    stdin: Any = None,
) -> dict[str, Any]:
    """Read one Claude Code hook payload from stdin and return the decision.

    Never raises: a broken payload or missing workspace degrades to an empty
    decision so a Palari problem cannot lock up an unrelated Claude session.
    """
    try:
        raw = (stdin if stdin is not None else sys.stdin).read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        return handle_hook_event(event, payload, workspace_path, strict=strict)
    except Exception as exc:  # noqa: BLE001 - hooks must fail open, never block the session
        return {"systemMessage": f"palari claude hook {event} error: {exc}"}


def handle_hook_event(
    event: str,
    payload: dict[str, Any],
    workspace_path: Path | str,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    state = load_active_claim_contexts(
        workspace_path,
        pin_palari=os.environ.get("PALARI_AS", ""),
        pin_work=os.environ.get("PALARI_WORK_ID", ""),
    )
    contexts = state["contexts"]
    if event == "pre-tool-use":
        return _pre_tool_use(
            payload, contexts, state["errors"], workspace_path, strict=strict
        )
    if event == "stop":
        return _stop(payload, contexts, state["errors"], workspace_path)
    if event == "session-start":
        return _session_start(contexts, state["errors"], workspace_path)
    return {}


def active_claim_contexts(workspace_path: Path | str) -> list[dict[str, Any]]:
    """Return active claims with their persisted packets.

    Each entry has ``claim`` and ``packet`` keys. Expired leases are skipped.
    ``PALARI_AS`` / ``PALARI_WORK_ID`` environment variables narrow the set
    when one session among several must be pinned to a single claim.
    """
    return load_active_claim_contexts(
        workspace_path,
        pin_palari=os.environ.get("PALARI_AS", ""),
        pin_work=os.environ.get("PALARI_WORK_ID", ""),
    )["contexts"]


def bash_write_targets(command: str, *, cwd: Path | None = None) -> list[str]:
    """Return path-like write targets a Bash command appears to touch.

    This is a conservative heuristic: it only inspects redirections and a
    short list of mutating commands, and its findings only ever produce an
    ``ask`` decision, never a silent ``deny`` or ``allow``.
    """
    tokens = _shell_tokens(command)
    command_cwd = (cwd or Path.cwd()).resolve()
    targets: list[str] = []
    expect_command = True
    expect_target = False
    expect_fd_or_target = False
    expect_write_option_target = False
    active_write_command = ""
    active_write_sources: list[str] = []
    write_target_directory = ""
    write_options_ended = False
    git_subcommand_index = -1
    sed_in_place = False
    sed_script_consumed = False

    def add_ordinary_directory_destinations() -> None:
        if (
            active_write_command not in {"cp", "git-mv", "install", "ln", "mv"}
            or write_target_directory
            or len(active_write_sources) < 2
        ):
            return
        destination = Path(active_write_sources[-1])
        resolved_destination = (
            destination
            if destination.is_absolute()
            else command_cwd / destination
        ).resolve()
        if not resolved_destination.is_dir():
            return
        targets.extend(
            str(destination / Path(source).name)
            for source in active_write_sources[:-1]
        )

    for token_index, token in enumerate(tokens):
        if token in SHELL_COMMAND_SEPARATORS:
            add_ordinary_directory_destinations()
            expect_command = True
            expect_target = False
            expect_fd_or_target = False
            expect_write_option_target = False
            active_write_command = ""
            active_write_sources = []
            write_target_directory = ""
            write_options_ended = False
            git_subcommand_index = -1
            sed_in_place = False
            sed_script_consumed = False
            continue
        redirect = _redirect_target(token)
        if redirect is not None:
            if redirect == _REDIRECT_NO_TARGET:
                pass
            elif redirect == _REDIRECT_FD_OR_TARGET:
                expect_target = True
                expect_fd_or_target = True
            elif redirect:
                targets.append(redirect)
            else:
                expect_target = True
            continue
        if expect_target:
            if not (expect_fd_or_target and (token.isdigit() or token == "-")):
                targets.append(token)
            expect_target = False
            expect_fd_or_target = False
            continue
        if expect_write_option_target:
            targets.append(token)
            write_target_directory = token
            targets.extend(
                str(Path(token) / Path(source).name) for source in active_write_sources
            )
            expect_write_option_target = False
            continue
        if expect_command:
            expect_command = False
            name = Path(token).name
            if name in BASH_WRITE_COMMANDS:
                active_write_command = name
            elif name == "sed":
                sed_in_place = False
                sed_script_consumed = False
                active_write_command = "sed"
            elif name == "git":
                subcommand, git_subcommand_index = _git_subcommand_details(
                    tokens, token_index
                )
                active_write_command = (
                    f"git-{subcommand}" if subcommand in {"rm", "mv"} else ""
                )
            continue
        if git_subcommand_index >= 0 and token_index <= git_subcommand_index:
            continue
        if active_write_command == "sed":
            if token == "--":
                write_options_ended = True
                continue
            if token in {"-i", "--in-place"} or token.startswith("-i"):
                sed_in_place = True
                continue
            if not write_options_ended and token.startswith("-"):
                continue
            if not sed_script_consumed:
                sed_script_consumed = True
                continue
            if sed_in_place and _looks_like_path(token):
                targets.append(token)
            continue
        if active_write_command == "dd":
            if token.startswith("of=") and token[3:]:
                targets.append(token[3:])
            continue
        if active_write_command and token == "--":
            write_options_ended = True
            continue
        if (
            active_write_command in {"cp", "install", "ln", "mv"}
            and not write_options_ended
        ):
            if token in {"-t", "--target-directory"}:
                expect_write_option_target = True
                continue
            if token.startswith("--target-directory="):
                target = token.split("=", 1)[1]
                if target:
                    targets.append(target)
                    write_target_directory = target
                    targets.extend(
                        str(Path(target) / Path(source).name)
                        for source in active_write_sources
                    )
                continue
            if token.startswith("-t") and token != "-t":
                target = token[2:]
                targets.append(target)
                write_target_directory = target
                targets.extend(
                    str(Path(target) / Path(source).name)
                    for source in active_write_sources
                )
                continue
        if active_write_command and (write_options_ended or not token.startswith("-")):
            targets.append(token)
            active_write_sources.append(token)
            if write_target_directory:
                targets.append(str(Path(write_target_directory) / Path(token).name))
    add_ordinary_directory_destinations()
    return targets


def _bash_destructive_targets(command: str) -> list[str]:
    """Return paths whose existing contents a shell command may remove or move."""

    targets: list[str] = []
    expect_command = True
    active_command = ""
    options_ended = False
    git_subcommand_index = -1
    tokens = _shell_tokens(command)
    for token_index, token in enumerate(tokens):
        if token in SHELL_COMMAND_SEPARATORS:
            expect_command = True
            active_command = ""
            options_ended = False
            git_subcommand_index = -1
            continue
        if expect_command:
            if _is_shell_assignment(token):
                continue
            expect_command = False
            name = Path(token).name
            if name in {"mv", "rm", "rmdir"}:
                active_command = name
            elif name == "git":
                subcommand, git_subcommand_index = _git_subcommand_details(
                    tokens, token_index
                )
                active_command = (
                    f"git-{subcommand}" if subcommand in {"mv", "rm"} else ""
                )
            continue
        if git_subcommand_index >= 0 and token_index <= git_subcommand_index:
            continue
        if active_command and token == "--":
            options_ended = True
            continue
        if active_command in {"git-mv", "git-rm", "mv", "rm", "rmdir"}:
            if options_ended or not token.startswith("-"):
                targets.append(token)
    return targets


def bash_human_authority_command(command: str) -> str:
    """Name a human-only or packet-authority Palari shell mutation."""

    tokens = _shell_tokens(command)
    for index, token in enumerate(tokens):
        if Path(token).name != "palari":
            continue
        args = tokens[index + 1 :]
        for argument_index in range(len(args) - 1):
            command_key = (args[argument_index], args[argument_index + 1])
            if command_key in HUMAN_ONLY_PALARI_COMMANDS | PACKET_AUTHORITY_PALARI_COMMANDS:
                return " ".join(command_key)
        if (
            any(
                (args[argument_index], args[argument_index + 1]) == ("linear", "start")
                for argument_index in range(len(args) - 1)
            )
            and any(
                argument.startswith("--adopt")
                for argument in args
            )
        ):
            return "linear start --adopt-by"
    return ""


def bash_requires_human_review(command: str) -> str:
    """Return why a target-free shell command is too opaque to auto-authorize."""

    if "\\\n" in command or "\\\r\n" in command:
        return "shell line continuation"
    if "$" in command or "`" in command or "<(" in command or ">(" in command:
        return "dynamic shell expansion"
    expansion_reason = _unquoted_shell_expansion_reason(command)
    if expansion_reason:
        return expansion_reason
    tokens = _shell_tokens(command)
    expect_command = True
    for index, token in enumerate(tokens):
        if token in SHELL_COMMAND_SEPARATORS:
            expect_command = True
            continue
        if not expect_command:
            continue
        if _is_shell_assignment(token):
            return "command environment assignment"
        expect_command = False
        name = Path(token).name
        if token == ".":
            return "opaque interpreter ."
        if token != name:
            return f"unreviewed executable (path-qualified executable {token})"
        if name in OPAQUE_INTERPRETERS:
            return f"opaque interpreter {name}"
        write_reason = _write_command_semantics_reason(tokens, index, name)
        if write_reason:
            return write_reason
        if name in BASH_WRITE_COMMANDS:
            continue
        if name == "git":
            subcommand = _git_subcommand(tokens, index)
            if subcommand in GIT_WITNESS_MUTATIONS:
                return f"Git metadata mutation git {subcommand}"
            option_reason = _git_execution_option_reason(tokens, index)
            if option_reason:
                return option_reason
            if subcommand in SAFE_GIT_OBSERVABLE_WRITE_SUBCOMMANDS:
                continue
            if subcommand not in SAFE_GIT_READ_SUBCOMMANDS:
                return f"unreviewed Git subcommand git {subcommand or '(missing)'}"
            continue
        if name == "palari":
            palari_reason = _palari_shell_review_reason(tokens, index)
            if palari_reason:
                return palari_reason
            continue
        if name == "rg":
            for option in RG_EXECUTION_OPTIONS:
                if _command_has_option(tokens, index, {option}):
                    return f"execution-capable rg {option}"
        if name not in SAFE_TARGET_FREE_COMMANDS:
            return f"unreviewed executable {name or token}"
    if ".palari" in command:
        return "Palari runtime path mutation"
    return ""


def _unquoted_shell_expansion_reason(command: str) -> str:
    """Identify syntax whose runtime path cannot be known from lexical tokens."""

    single_quoted = False
    double_quoted = False
    escaped = False
    word_start = True
    for character in command:
        if escaped:
            escaped = False
            word_start = False
            continue
        if character == "\\" and not single_quoted:
            escaped = True
            continue
        if single_quoted:
            if character == "'":
                single_quoted = False
            continue
        if double_quoted:
            if character == '"':
                double_quoted = False
            continue
        if character == "'":
            single_quoted = True
            word_start = False
            continue
        if character == '"':
            double_quoted = True
            word_start = False
            continue
        if character in "*?[{(":
            return "unquoted shell pathname expansion"
        if character == "~" and word_start:
            return "unquoted shell home expansion"
        word_start = character.isspace() or character in ";|&<>=:"
    return ""


def _write_command_semantics_reason(
    tokens: list[str], command_index: int, command_name: str
) -> str:
    """Reject write options that create paths absent from the command text."""

    arguments = _command_arguments(tokens, command_index)
    option_arguments: list[str] = []
    for argument in arguments:
        if argument == "--":
            break
        option_arguments.append(argument)
    if command_name == "cp":
        for argument in option_arguments:
            if argument in {
                "--archive",
                "--no-target-directory",
                "--parents",
                "--recursive",
            }:
                return f"tree-writing cp option {argument}"
            if argument.startswith("-") and not argument.startswith("--"):
                flags = argument[1:]
                if any(flag in flags for flag in "RraT"):
                    return f"tree-writing cp option {argument}"
    if command_name in {"cp", "install", "ln", "mv"}:
        for argument in option_arguments:
            if argument.startswith("--"):
                return f"unreviewed long {command_name} write option {argument}"
            if argument == "--no-target-directory":
                return f"exact-destination {command_name} option {argument}"
            if argument.startswith("-") and not argument.startswith("--"):
                if "T" in argument[1:]:
                    return f"exact-destination {command_name} option {argument}"
            if argument in {"--backup", "-b"} or argument.startswith("--backup="):
                return f"backup-producing {command_name} option {argument}"
            if (
                argument.startswith("-")
                and not argument.startswith("--")
                and any(flag in argument[1:] for flag in "bS")
            ):
                return f"backup-producing {command_name} option {argument}"
    if command_name == "sed":
        for argument in option_arguments:
            if argument.startswith("--"):
                return f"unreviewed long sed write option {argument}"
            if (
                argument.startswith("--in-place=")
                or (argument.startswith("-i") and argument != "-i")
            ):
                return f"backup-producing sed option {argument}"
    if command_name in {"mkdir", "rmdir"}:
        for argument in option_arguments:
            if argument.startswith("--"):
                return f"unreviewed long {command_name} write option {argument}"
            if argument.startswith("-") and "p" in argument[1:]:
                return f"ancestor-writing {command_name} option {argument}"
    if command_name == "install":
        for argument in option_arguments:
            if argument.startswith("-") and any(flag in argument[1:] for flag in "Dd"):
                return f"ancestor-writing install option {argument}"
    return ""


def _palari_shell_review_reason(tokens: list[str], command_index: int) -> str:
    """Fail closed for Palari CLI commands not classified for agent shells."""

    command_key = _palari_command_key(tokens, command_index)
    if command_key in PALARI_SELF_PROTECTION_COMMANDS:
        return f"Palari self-protection mutation {' '.join(command_key)}"
    if command_key in SAFE_AGENT_PALARI_COMMANDS:
        return ""
    label = " ".join(part for part in command_key if part) or "(missing)"
    return f"unreviewed Palari command {label}"


def _palari_workspace_review_reason(
    command: str, cwd: Path, workspace_path: Path | str
) -> str:
    """Keep agent-safe Palari mutations bound to this hook's workspace."""

    current = workspace_file_path(workspace_path).resolve()
    tokens = _shell_tokens(command)
    for index, token in enumerate(tokens):
        if Path(token).name != "palari":
            continue
        command_key = _palari_command_key(tokens, index)
        if command_key not in MUTATING_AGENT_PALARI_COMMANDS:
            continue
        arguments = _command_arguments(tokens, index)
        declared = ""
        for argument_index, argument in enumerate(arguments):
            if argument == "--workspace":
                if argument_index + 1 < len(arguments):
                    declared = arguments[argument_index + 1]
                break
            if argument.startswith("--workspace="):
                declared = argument.split("=", 1)[1]
                break
        if declared:
            candidate = Path(declared).expanduser()
            if not candidate.is_absolute():
                candidate = cwd / candidate
            if workspace_file_path(candidate).resolve() != current:
                return f"Palari mutation {' '.join(command_key)} targets another workspace"
            continue
        local_default = (cwd / "workspace.json").resolve()
        if local_default != current:
            return (
                f"Palari mutation {' '.join(command_key)} must name this hook's "
                "workspace with --workspace"
            )
    return ""


def _palari_command_key(tokens: list[str], command_index: int) -> tuple[str, str]:
    arguments = _command_arguments(tokens, command_index)
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--workspace":
            index += 2
            continue
        if argument.startswith("--workspace="):
            index += 1
            continue
        if argument.startswith("-"):
            return ("", "")
        break
    if index >= len(arguments):
        return ("", "")
    command = arguments[index]
    if command in {
        "detail",
        "history",
        "integrations",
        "queue",
        "scope",
        "state",
        "validate",
    }:
        return (command, "")
    if index + 1 >= len(arguments) or arguments[index + 1].startswith("-"):
        return (command, "")
    nested = arguments[index + 1]
    if command == "linear" and nested == "webhook":
        if index + 2 >= len(arguments) or arguments[index + 2].startswith("-"):
            return ("linear", "webhook")
        return ("linear", f"webhook-{arguments[index + 2]}")
    return (command, nested)


def _shell_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(
            command.replace("\r\n", "\n").replace("\n", " ; "),
            posix=True,
            punctuation_chars=True,
        )
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return command.split()


def _is_shell_assignment(token: str) -> bool:
    if "=" not in token:
        return False
    name, _separator, _value = token.partition("=")
    return bool(name) and name.replace("_", "a").isalnum() and not name[0].isdigit()


def _git_subcommand(tokens: list[str], git_index: int) -> str:
    """Return a Git subcommand after recognized global options."""

    return _git_subcommand_details(tokens, git_index)[0]


def _git_subcommand_details(tokens: list[str], git_index: int) -> tuple[str, int]:
    """Return a Git subcommand and its token index after global options."""

    index = git_index + 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            index += 1
            break
        if token in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if token.startswith("-C") and token != "-C":
            index += 1
            continue
        if token.startswith("-c") and token != "-c":
            index += 1
            continue
        if any(token.startswith(prefix) for prefix in GIT_GLOBAL_OPTIONS_WITH_ATTACHED_VALUE):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token, index
    return (tokens[index], index) if index < len(tokens) else ("", -1)


def _git_execution_option_reason(tokens: list[str], git_index: int) -> str:
    """Reject Git options that can launch helpers or write output indirectly."""

    subcommand, subcommand_index = _git_subcommand_details(tokens, git_index)
    if subcommand == "rm" and subcommand_index >= 0:
        for token in _command_arguments(tokens, subcommand_index):
            if token.startswith(":"):
                return f"Git pathspec magic {token}"
            if any(marker in token for marker in ("*", "?", "[")):
                return f"Git pathspec expansion {token}"
    for token in _command_arguments(tokens, git_index):
        if any(_long_option_matches(token, option) for option in GIT_INDIRECT_PATH_OPTIONS):
            return f"indirect Git path option {token.split('=', 1)[0]}"
        if token in GIT_EXECUTION_GLOBAL_OPTIONS:
            return f"execution-capable Git option {token}"
        if any(
            _long_option_matches(token, option)
            for option in GIT_EXECUTION_GLOBAL_OPTIONS
            if option.startswith("--")
        ):
            return f"execution-capable Git option {token.split('=', 1)[0]}"
        if token.startswith("-c") and token != "-C":
            return "execution-capable Git option -c"
        if token.startswith("-C") and token != "-C":
            return "repository-overriding Git option -C"
        if any(
            _long_option_matches(token, option)
            for option in GIT_EXECUTION_OPTIONS
        ):
            return f"execution-capable Git option {token.split('=', 1)[0]}"
        if _long_option_matches(token, "--output"):
            return "Git output-file mutation"
        if token == "-O" or token.startswith("-O"):
            return "execution-capable Git pager option -O"
    return ""


def _command_has_option(tokens: list[str], command_index: int, options: set[str]) -> bool:
    return any(
        token in options or any(_long_option_matches(token, option) for option in options)
        for token in _command_arguments(tokens, command_index)
    )


def _long_option_matches(token: str, option: str) -> bool:
    """Match a GNU/Git long option, including accepted unique abbreviations."""

    if not option.startswith("--") or not token.startswith("--"):
        return token == option
    name = token.split("=", 1)[0]
    return len(name) > 2 and option.startswith(name)


def _command_arguments(tokens: list[str], command_index: int) -> list[str]:
    arguments: list[str] = []
    for token in tokens[command_index + 1 :]:
        if token in SHELL_COMMAND_SEPARATORS:
            break
        arguments.append(token)
    return arguments


def install_hooks(
    project_dir: Path | str,
    workspace_path: Path | str,
    *,
    settings_file: str = "",
    local: bool = False,
    strict: bool = False,
    remove: bool = False,
) -> dict[str, Any]:
    """Merge (or remove) Palari-managed hooks in Claude Code settings.

    Idempotent: Palari-managed entries are recognized by their command marker
    and replaced in place; hooks owned by other tools are preserved.
    """
    root = Path(project_dir).expanduser().resolve()
    target = _settings_path(root, settings_file, local)
    data = _read_json(target) if target.exists() else {}
    if data is None:
        return {
            "schema_version": "palari.claude_install.v1",
            "status": "error",
            "changed": False,
            "settings_file": str(target),
            "message": f"{target} exists but is not valid JSON; fix or remove it first.",
            "hooks": {},
        }

    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        data["hooks"] = hooks

    managed = {} if remove else _managed_hooks(root, workspace_path, strict=strict)
    changed = False
    for event in ("PreToolUse", "Stop", "SessionStart"):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
        kept = [entry for entry in entries if not _is_managed_entry(entry)]
        if event in managed:
            kept.append(managed[event])
        if kept != entries:
            changed = True
        if kept:
            hooks[event] = kept
        elif event in hooks:
            del hooks[event]
            changed = True
    if not hooks:
        del data["hooks"]

    if changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    status = "removed" if remove else "installed"
    if not changed:
        status = "unchanged"
    return {
        "schema_version": "palari.claude_install.v1",
        "status": status,
        "changed": changed,
        "settings_file": str(target),
        "workspace": _workspace_argument(root, workspace_path),
        "strict": strict,
        "palari_on_path": shutil.which("palari") is not None
        or (root / "bin" / "palari").is_file(),
        "hooks": {event: entry["hooks"][0]["command"] for event, entry in managed.items()},
        "message": _install_message(status, target),
    }


def hooks_status(
    project_dir: Path | str,
    workspace_path: Path | str,
) -> dict[str, Any]:
    root = Path(project_dir).expanduser().resolve()
    files: list[dict[str, Any]] = []
    for candidate in (root / ".claude" / "settings.json", root / ".claude" / "settings.local.json"):
        data = _read_json(candidate) if candidate.exists() else None
        events: list[str] = []
        strict = False
        if isinstance(data, dict) and isinstance(data.get("hooks"), dict):
            for event, entries in data["hooks"].items():
                if isinstance(entries, list) and any(_is_managed_entry(e) for e in entries):
                    events.append(event)
                    strict = strict or any(
                        "--strict" in hook.get("command", "")
                        for entry in entries
                        if _is_managed_entry(entry)
                        for hook in entry.get("hooks", [])
                    )
        files.append(
            {
                "path": str(candidate),
                "exists": candidate.exists(),
                "palari_hook_events": sorted(events),
                "strict": strict,
            }
        )
    state = load_active_claim_contexts(
        workspace_path,
        pin_palari=os.environ.get("PALARI_AS", ""),
        pin_work=os.environ.get("PALARI_WORK_ID", ""),
    )
    contexts = state["contexts"]
    installed = any(item["palari_hook_events"] for item in files)
    return {
        "schema_version": "palari.claude_status.v1",
        "installed": installed,
        "settings_files": files,
        "palari_on_path": shutil.which("palari") is not None,
        "active_claims": [
            {
                "work_item": context["claim"].get("work_item", ""),
                "claimed_by": context["claim"].get("claimed_by", ""),
                "mode": context["claim"].get("mode", ""),
                "lease_expires_at": context["claim"].get("lease_expires_at", ""),
                "allowed_write_paths": _packet_write_paths(context["packet"]),
            }
            for context in contexts
        ],
        "claim_errors": state["errors"],
        "message": (
            "Palari hooks are installed for Claude Code."
            if installed
            else "No Palari hooks found. Run: palari claude install"
        ),
    }


def _pre_tool_use(
    payload: dict[str, Any],
    contexts: list[dict[str, Any]],
    context_errors: list[str],
    workspace_path: Path | str,
    *,
    strict: bool,
) -> dict[str, Any]:
    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    cwd = Path(str(payload.get("cwd") or "") or os.getcwd())
    destructive_targets: list[str] = []

    exact = tool_name in FILE_WRITE_TOOLS
    if exact:
        raw_targets = [str(tool_input.get(FILE_WRITE_TOOLS[tool_name], ""))]
    elif tool_name == "Bash":
        command = str(tool_input.get("command", ""))
        authority_command = bash_human_authority_command(command)
        if authority_command:
            return _decision(
                "deny",
                f"Palari command `{authority_command}` is human-only and cannot run "
                "from an agent shell. Use the human handoff packet instead.",
            )
        opaque_reason = bash_requires_human_review(command)
        if opaque_reason:
            return _decision(
                "ask",
                f"{opaque_reason} can bypass Palari's observable write boundary. "
                "A human must approve this shell command or use a directly inspected tool.",
            )
        workspace_reason = _palari_workspace_review_reason(
            command, cwd, workspace_path
        )
        if workspace_reason:
            return _decision(
                "ask",
                f"{workspace_reason}. Agent-safe Palari mutations cannot cross "
                "the active hook workspace boundary.",
            )
        raw_targets = bash_write_targets(command, cwd=cwd)
        destructive_targets = _bash_destructive_targets(command)
    else:
        return {}
    raw_targets = [target for target in raw_targets if target]
    if not raw_targets:
        return {}

    if context_errors:
        return _decision(
            "deny" if exact else "ask",
            "Palari cannot verify the active claim context: " + "; ".join(context_errors),
        )

    root = _resolution_root(payload)
    unresolved: list[str] = []
    relative_targets: list[str] = []
    for target in raw_targets:
        relative = _relativize(target, root, cwd)
        if relative is None:
            unresolved.append(target)
        else:
            relative_targets.append(relative)
    if contexts and unresolved:
        return _decision(
            "deny" if exact else "ask",
            "This file change touches paths outside the repository "
            f"({', '.join(sorted(unresolved))}), which the Palari packet cannot vouch for.",
        )
    workspace_bound = root is not None and _workspace_belongs_to_repo(workspace_path, root)
    if workspace_bound:
        protected = [
            (target, _protected_governance_target(target, cwd, root, workspace_path))
            for target in raw_targets
        ]
        protected.extend(
            (
                target,
                _protected_governance_target(
                    target,
                    cwd,
                    root,
                    workspace_path,
                    include_ancestors=True,
                ),
            )
            for target in destructive_targets
        )
        protected = list(
            dict.fromkeys((target, reason) for target, reason in protected if reason)
        )
        if protected:
            details = ", ".join(f"{target} ({reason})" for target, reason in protected)
            return _decision(
                "deny" if exact else "ask",
                "Governance source-of-truth and runtime metadata must change through "
                f"governed Palari commands, not direct file writes: {details}.",
            )

    if not contexts:
        if strict:
            return _decision(
                "ask",
                "No active Palari claim covers this session. "
                "Run: palari agent next --json, then palari agent start WORK-ID "
                "--as PALARI-ID --mode execute --json before changing files.",
            )
        return {}

    execute = _execute_contexts(contexts)
    if not execute:
        reason = (
            "Active Palari claims are review-mode (read-only); file changes are "
            "outside the packet contract. Start execute-mode work first: "
            "palari agent start WORK-ID --as PALARI-ID --mode execute --json"
        )
        return _decision("deny" if exact else "ask", reason)

    if not workspace_bound:
        return _decision(
            "deny" if exact else "ask",
            "The active Palari workspace cannot be bound to this Git repository.",
        )

    covering = [
        context
        for context in execute
        if all(
            canonical_path_allowed(
                target, _packet_write_paths(context["packet"]), root=root
            )
            for target in relative_targets
        )
    ]
    if len(covering) != 1:
        if len(covering) > 1:
            reason = (
                "This file change is covered by multiple active execute claims. "
                "Set PALARI_WORK_ID/PALARI_AS or release the overlapping claim before writing."
            )
        else:
            reason = _boundary_reason(
                relative_targets, _allowed_write_paths(execute), execute, exact
            )
        return _decision("deny" if exact else "ask", reason)

    selected = covering[0]
    allowed = _packet_write_paths(selected["packet"])
    if exact:
        claim = selected["claim"]
        return _decision(
            "allow",
            f"Inside the Palari write boundary for {claim.get('work_item', '')} "
            f"(claimed by {claim.get('claimed_by', '')}).",
        )
    return {}


def _stop(
    payload: dict[str, Any],
    contexts: list[dict[str, Any]],
    context_errors: list[str],
    workspace_path: Path | str,
) -> dict[str, Any]:
    if payload.get("stop_hook_active"):
        return {}
    if context_errors:
        return {
            "decision": "block",
            "reason": "Palari cannot verify the active claim context: " + "; ".join(context_errors),
        }
    execute = _execute_contexts(contexts)
    if not contexts:
        return {}
    if execute and len(execute) != 1:
        return {
            "decision": "block",
            "reason": (
                "Multiple active execute claims are ambiguous. Set PALARI_WORK_ID/PALARI_AS "
                "or release overlapping claims before finishing."
            ),
        }
    cwd = str(payload.get("cwd") or "") or os.getcwd()
    root = git_repo_root(Path(cwd))
    if root is None or not _workspace_belongs_to_repo(workspace_path, root):
        return {
            "decision": "block",
            "reason": "Palari cannot bind this active claim and workspace to the current Git repository.",
        }
    if not execute:
        inspection = inspect_file_changes(
            {"allowed_paths": {"write": []}},
            git_diff=True,
            cwd=Path(cwd),
            git_baseline=contexts[0]["claim"].get("git_baseline"),
        )
        observation_errors = inspection.get("observation_errors", []) if inspection else []
        if observation_errors:
            return {
                "decision": "block",
                "reason": "Palari could not inspect the Git worktree: "
                + "; ".join(observation_errors),
            }
        changed = inspection.get("outside_write_boundary", []) if inspection else []
        changed = _without_palari_runtime(changed, workspace_path, Path(cwd))
        if changed:
            return {
                "decision": "block",
                "reason": (
                    "Active review-mode Palari claims are read-only; changed files: "
                    + ", ".join(changed)
                ),
            }
        return {}
    boundary_packet = {"allowed_paths": {"write": _packet_write_paths(execute[0]["packet"])}}
    inspection = inspect_file_changes(
        boundary_packet,
        git_diff=True,
        cwd=Path(cwd),
        git_baseline=execute[0]["claim"].get("git_baseline"),
    )
    observation_errors = inspection.get("observation_errors", []) if inspection else []
    if observation_errors:
        return {
            "decision": "block",
            "reason": "Palari could not inspect the Git worktree: " + "; ".join(observation_errors),
        }
    outside = inspection.get("outside_write_boundary", []) if inspection else []
    outside = _without_palari_runtime(outside, workspace_path, Path(cwd))
    if not outside:
        return {}
    claim = execute[0]["claim"]
    work_id = claim.get("work_item", "WORK-ID")
    palari_id = claim.get("claimed_by", "PALARI-ID")
    lines = [
        "Palari boundary check failed: the working tree has changes outside the "
        "active packet write boundary.",
        "outside boundary:",
        *[f"  - {path}" for path in outside],
        "allowed:",
        *[f"  - {path}" for path in _allowed_write_paths(execute)],
        "Before finishing: revert the out-of-boundary changes (or confirm they "
        "predate this session and tell the human), then run:",
        f"  palari agent check {work_id} --as {palari_id} --mode execute --git-diff --json",
        "If the boundary itself must grow, stop and hand off with:",
        f"  palari agent handoff {work_id} --as {palari_id} --json",
    ]
    return {"decision": "block", "reason": "\n".join(lines)}


def _session_start(
    contexts: list[dict[str, Any]],
    context_errors: list[str],
    workspace_path: Path | str,
) -> dict[str, Any]:
    workspace_dir = workspace_file_path(workspace_path).parent
    lines = [
        "<palari-contract>",
        f"This project is governed by Palari Company OS (workspace: {workspace_dir}).",
    ]
    if context_errors:
        lines.append("Invalid active claim context (writes must stop):")
        lines.extend(f"- {error}" for error in context_errors)
    if contexts:
        lines.append("Active claims:")
        for context in contexts:
            claim = context["claim"]
            work_id = claim.get("work_item", "")
            palari_id = claim.get("claimed_by", "")
            mode = claim.get("mode", "")
            lines.append(
                f"- {work_id} claimed by {palari_id} (mode {mode}, "
                f"lease expires {claim.get('lease_expires_at', '')})"
            )
            writes = _packet_write_paths(context["packet"])
            lines.append(
                "  allowed write paths: " + (", ".join(writes) if writes else "(none)")
            )
            lines.append(
                f"  check before done: palari agent check {work_id} --as {palari_id} "
                f"--mode {mode} --git-diff --json"
            )
        lines.append(
            "File writes outside these boundaries are blocked by PreToolUse and "
            "Stop hooks; do not try to work around them."
        )
    else:
        lines.extend(
            [
                "No work item is claimed yet. Before changing files, pick bounded "
                "work and claim it:",
                "  palari agent next --json",
                "  palari agent start WORK-ID --as PALARI-ID --mode execute --json",
                "Palari hooks enforce the claimed packet's write boundary during "
                "this session.",
            ]
        )
    lines.append("</palari-contract>")
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }


def _decision(decision: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def _boundary_reason(
    outside: list[str],
    allowed: list[str],
    execute: list[dict[str, Any]],
    exact: bool,
) -> str:
    claim = execute[0]["claim"]
    work_id = claim.get("work_item", "WORK-ID")
    palari_id = claim.get("claimed_by", "PALARI-ID")
    verb = "is" if exact else "may be"
    lines = [
        f"*** BLOCKED: file change {verb} outside the Palari write boundary ***",
        *[f"changed: {path}" for path in sorted(outside)],
        *[f"allowed: {path}" for path in allowed],
        f"work: {work_id} (claimed by {palari_id})",
        "Next safe commands:",
        f"  palari agent doctor {work_id} --as {palari_id} --mode execute --json",
        f"  palari agent handoff {work_id} --as {palari_id} --json",
        "If the boundary must grow, a human updates the work item scope first.",
    ]
    return "\n".join(lines)


def _without_palari_runtime(
    outside: list[str],
    workspace_path: Path | str,
    cwd: Path,
) -> list[str]:
    """Drop the workspace's own .palari runtime state from boundary findings.

    ``agent start`` writes packets and claims under ``.palari/``; treating
    that bookkeeping as an out-of-boundary change would block every stop.
    """
    root = git_repo_root(cwd)
    if root is None:
        return outside
    runtime_dir = workspace_file_path(workspace_path).parent / ".palari"
    try:
        prefix = runtime_dir.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return outside
    return [path for path in outside if path != prefix and not path.startswith(f"{prefix}/")]


def _execute_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [context for context in contexts if context["claim"].get("mode") == "execute"]


def _allowed_write_paths(contexts: list[dict[str, Any]]) -> list[str]:
    allowed: list[str] = []
    for context in contexts:
        for path in _packet_write_paths(context["packet"]):
            if path not in allowed:
                allowed.append(path)
    return allowed


def _packet_write_paths(packet: dict[str, Any]) -> list[str]:
    paths = packet.get("allowed_paths", {})
    if not isinstance(paths, dict):
        return []
    write = paths.get("write", [])
    if not isinstance(write, list):
        return []
    return [str(path) for path in write if str(path)]


def _resolution_root(payload: dict[str, Any]) -> Path | None:
    cwd = str(payload.get("cwd") or "") or os.getcwd()
    root = git_repo_root(Path(cwd))
    if root is not None:
        return root
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    return Path(project_dir) if project_dir else None


def _relativize(target: str, root: Path | None, cwd: Path) -> str | None:
    """Map a hook-reported path onto the repo-relative boundary namespace.

    Relative paths are anchored at the hook's cwd first, since boundary paths
    are repo-root relative. Returns None when the path cannot be tied to the
    repository, so callers can distinguish "outside the boundary" from
    "outside the repo".
    """
    candidate = Path(target.strip().replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = cwd / candidate
    if root is None:
        return None
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _redirect_target(token: str) -> str | None:
    """Return the redirect target embedded in a token.

    ``">"``-style operators with a separate target return ``""`` so the
    caller consumes the next token; fd duplications such as ``2>&1`` return
    the no-target sentinel; non-redirect tokens return ``None``.
    """
    stripped = token.lstrip("012&")
    if stripped.startswith("<>"):
        return stripped[2:]
    if not stripped.startswith(">"):
        return None
    if stripped == ">&":
        return _REDIRECT_FD_OR_TARGET
    remainder = stripped.lstrip(">").lstrip("|")
    if remainder.startswith("&"):
        return _REDIRECT_NO_TARGET
    return remainder


def _looks_like_path(token: str) -> bool:
    return "/" in token or "." in Path(token).name


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _settings_path(root: Path, settings_file: str, local: bool) -> Path:
    if settings_file:
        return Path(settings_file).expanduser().resolve()
    name = "settings.local.json" if local else "settings.json"
    return root / ".claude" / name


def _managed_hooks(
    root: Path,
    workspace_path: Path | str,
    *,
    strict: bool,
) -> dict[str, dict[str, Any]]:
    executable = _palari_executable(root)
    workspace_argument = _workspace_argument(root, workspace_path)
    strict_suffix = " --strict" if strict else ""

    def command(event: str, suffix: str = "") -> dict[str, Any]:
        return {
            "type": "command",
            "command": (
                f'{executable} --workspace "{workspace_argument}" claude hook {event}{suffix}'
            ),
            "timeout": HOOK_TIMEOUT_SECONDS,
        }

    return {
        "PreToolUse": {
            "matcher": PRE_TOOL_USE_MATCHER,
            "hooks": [command("pre-tool-use", strict_suffix)],
        },
        "Stop": {"hooks": [command("stop")]},
        "SessionStart": {"hooks": [command("session-start")]},
    }


def _palari_executable(root: Path) -> str:
    """Prefer a project-local wrapper so hooks work without a pip install."""
    if (root / "bin" / "palari").is_file():
        return '"$CLAUDE_PROJECT_DIR/bin/palari"'
    return "palari"


def _workspace_argument(root: Path, workspace_path: Path | str) -> str:
    workspace_dir = workspace_file_path(workspace_path).parent
    try:
        relative = workspace_dir.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(workspace_dir)
    if relative == ".":
        return "$CLAUDE_PROJECT_DIR"
    return f"$CLAUDE_PROJECT_DIR/{relative}"


def _is_managed_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks", [])
    if not isinstance(hooks, list):
        return False
    return any(
        isinstance(hook, dict)
        and HOOK_COMMAND_MARKER in str(hook.get("command", ""))
        and "palari" in str(hook.get("command", ""))
        for hook in hooks
    )


def _install_message(status: str, target: Path) -> str:
    if status == "installed":
        return f"Palari hooks written to {target}. Claude Code loads them on the next session."
    if status == "removed":
        return f"Palari hooks removed from {target}."
    return f"{target} already matches the requested hook configuration."


def _workspace_belongs_to_repo(workspace_path: Path | str, root: Path) -> bool:
    try:
        workspace_file_path(workspace_path).parent.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _protected_governance_target(
    raw_target: str,
    cwd: Path,
    root: Path,
    workspace_path: Path | str,
    *,
    include_ancestors: bool = False,
) -> str:
    """Name governance state that must not be edited around the CLI gates."""

    target = Path(raw_target.strip().replace("\\", "/"))
    if not target.is_absolute():
        target = cwd / target
    target = target.resolve()
    data_path = workspace_file_path(workspace_path).resolve()
    protected_files = {data_path}
    try:
        raw = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    collection_files = raw.get("collection_files") if isinstance(raw, dict) else None
    if isinstance(collection_files, dict):
        for paths in collection_files.values():
            if not isinstance(paths, list):
                continue
            for relative in paths:
                if not isinstance(relative, str):
                    continue
                try:
                    canonical = validate_workspace_path(relative)
                    protected_files.add(resolve_workspace_path(data_path.parent, canonical))
                except ValueError:
                    continue
    if target in protected_files or (
        include_ancestors and any(target in path.parents for path in protected_files)
    ):
        return "workspace source of truth"
    runtime = (data_path.parent / ".palari").resolve()
    if (
        target == runtime
        or runtime in target.parents
        or (include_ancestors and target in runtime.parents)
    ):
        return "Palari runtime state"
    hook_settings = {
        (root / ".claude" / "settings.json").resolve(),
        (root / ".claude" / "settings.local.json").resolve(),
    }
    if target in hook_settings or (
        include_ancestors and any(target in path.parents for path in hook_settings)
    ):
        return "Claude hook configuration"
    for git_metadata in _git_metadata_roots(root):
        if (
            target == git_metadata
            or git_metadata in target.parents
            or (include_ancestors and target in git_metadata.parents)
        ):
            return "Git metadata"
    return ""


def _git_metadata_roots(root: Path) -> set[Path]:
    marker = root / ".git"
    roots = {marker.resolve()}
    if not marker.is_file():
        return roots
    try:
        declaration = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return roots
    if not declaration.lower().startswith("gitdir:"):
        return roots
    git_dir = Path(declaration.split(":", 1)[1].strip())
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    git_dir = git_dir.resolve()
    roots.add(git_dir)
    common_marker = git_dir / "commondir"
    if common_marker.is_file():
        try:
            common_dir = Path(common_marker.read_text(encoding="utf-8").strip())
            if not common_dir.is_absolute():
                common_dir = git_dir / common_dir
            roots.add(common_dir.resolve())
        except OSError:
            pass
    return roots

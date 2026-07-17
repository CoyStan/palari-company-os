from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import agent_checks
from .agent_directive import compile_agent_directive
from .agent_packets import build_agent_brief
from .governance_journal import JournalVerificationContext
from .workspace import Workspace


@dataclass
class AgentOperation:
    """Request-local cache for one immutable agent state observation.

    Aggregate read commands may render several views, but packet compilation,
    contract checking, directive derivation, and journal verification should
    each happen at most once for that observation.
    """

    workspace: Workspace
    work_id: str
    palari_id: str
    mode: str = "execute"
    journal_context: JournalVerificationContext = field(
        default_factory=JournalVerificationContext
    )
    _brief: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _check: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _directive: dict[str, Any] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.mode = self.mode or "execute"

    def brief(self) -> dict[str, Any]:
        if self._brief is None:
            self._brief = build_agent_brief(
                self.workspace,
                self.work_id,
                self.palari_id,
                self.mode,
                journal_context=self.journal_context,
            )
        return self._brief

    def check(
        self,
        *,
        changed_paths: list[str] | None = None,
        git_diff: bool = False,
        cwd: Path | str | None = None,
    ) -> dict[str, Any]:
        if changed_paths is not None or git_diff or cwd is not None:
            return self._compile_check(
                changed_paths=changed_paths,
                git_diff=git_diff,
                cwd=cwd,
            )
        if self._check is None:
            self._check = self._compile_check()
        return self._check

    def directive(self) -> dict[str, Any]:
        if self._directive is None:
            self._directive = compile_agent_directive(
                self.check(),
                linked_decision_command=self._linked_decision_command(),
            )
        return self._directive

    def _compile_check(
        self,
        *,
        changed_paths: list[str] | None = None,
        git_diff: bool = False,
        cwd: Path | str | None = None,
    ) -> dict[str, Any]:
        """Compile the public check payload from the operation's cached packet."""

        packet = self.brief()
        checks = agent_checks._packet_boundary_checks(packet)
        if packet.get("status") == "ready":
            checks.append(
                agent_checks._claim_owned_check(
                    self.workspace,
                    self.work_id,
                    self.palari_id,
                    self.mode,
                    packet,
                )
            )
        claim = agent_checks.read_claim(self.workspace.path, self.work_id)
        file_changes = agent_checks.inspect_file_changes(
            packet,
            changed_paths=changed_paths,
            git_diff=git_diff,
            cwd=cwd,
            git_baseline=(claim or {}).get("git_baseline"),
        )
        if file_changes is not None:
            checks.extend(agent_checks._file_change_checks(file_changes))
        if "completion_contract" in packet:
            checks.extend(agent_checks._completion_checks(packet))

        ok = all(check["status"] != "fail" for check in checks)
        return {
            "schema_version": "palari.agent_check.v1",
            "check_id": agent_checks._check_id(
                self.work_id,
                self.palari_id,
                self.mode,
            ),
            "created_at": agent_checks._timestamp(),
            "ok": ok,
            "workspace": packet.get("workspace", self.workspace.name),
            "mode": self.mode,
            "agent": packet.get("agent", {}),
            "work_item": packet.get("work_item", {}),
            "packet_id": packet.get("packet_id", ""),
            "packet_context_hash": packet.get("context_hash", ""),
            "packet_status": packet.get("status", "blocked"),
            "documentation_state": packet.get("documentation_state", {}),
            "recommended_docs": packet.get("recommended_docs", []),
            "next_step_type": packet.get("state", {}).get(
                "next_step_type",
                "inspect",
            ),
            "blockers": packet.get("blockers", []),
            "checks": checks,
            "file_changes": file_changes,
            "next_allowed_commands": agent_checks._next_commands(packet, checks, ok),
        }

    def _linked_decision_command(self) -> str | None:
        for decision in self.workspace.decisions:
            if decision.linked_work == self.work_id and decision.status == "open":
                return f"palari decision guide {decision.id} --json"
        return None


def ensure_agent_operation(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str = "execute",
    *,
    journal_context: JournalVerificationContext | None = None,
    operation: AgentOperation | None = None,
) -> AgentOperation:
    normalized_mode = mode or "execute"
    if operation is None:
        return AgentOperation(
            workspace=workspace,
            work_id=work_id,
            palari_id=palari_id,
            mode=normalized_mode,
            journal_context=journal_context or JournalVerificationContext(),
        )
    if (
        operation.workspace is not workspace
        or operation.work_id != work_id
        or operation.palari_id != palari_id
        or operation.mode != normalized_mode
    ):
        raise ValueError("agent operation does not match the requested agent state")
    if journal_context is not None and operation.journal_context is not journal_context:
        raise ValueError("agent operation has a different journal verification context")
    return operation

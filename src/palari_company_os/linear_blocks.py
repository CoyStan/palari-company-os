from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .errors import WorkspaceError
from .linear_core import LinearAdapterError, LinearClient, LinearIssueClient
from .workspace import Workspace


RISKS = {"R1", "R2", "R3", "R4", "R5"}
INTENSITIES = {"light", "standard", "high"}
PARALLEL_POLICIES = {"independent", "coordinate", "exclusive"}
RECOMMENDED_BLOCK_FIELDS = {
    "goal",
    "palari",
    "risk",
    "intensity",
    "scope",
    "acceptance_target",
    "verification_expectations",
}
STRING_GOVERNANCE_FIELDS = {
    "goal",
    "palari",
    "risk",
    "intensity",
    "scope",
    "acceptance_target",
    "parallel_policy",
}
STRING_LIST_GOVERNANCE_FIELDS = {
    "allowed_resources",
    "allowed_sources",
    "allowed_actions",
    "output_targets",
    "forbidden_actions",
    "verification_expectations",
    "recommended_playbooks",
    "conflict_targets",
}
GOVERNANCE_FIELDS = STRING_GOVERNANCE_FIELDS | STRING_LIST_GOVERNANCE_FIELDS


@dataclass(frozen=True)
class PalariBlock:
    present: bool
    valid: bool
    fields: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unknown_fields: list[str] = field(default_factory=list)
    missing_recommended_fields: list[str] = field(default_factory=list)

    @property
    def error(self) -> str:
        return "; ".join(self.errors)


def parse_palari_block(description: str) -> PalariBlock:
    match = re.search(r"```palari\s*\n(?P<body>.*?)\n```", description or "", re.DOTALL)
    if match is None:
        return PalariBlock(
            present=False,
            valid=False,
            fields={},
            errors=["missing palari block"],
            missing_recommended_fields=sorted(RECOMMENDED_BLOCK_FIELDS),
        )
    raw = match.group("body").strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return PalariBlock(
            present=True,
            valid=False,
            fields={},
            errors=[f"invalid palari JSON block: {exc.msg}"],
        )
    if not isinstance(parsed, dict):
        return PalariBlock(
            present=True,
            valid=False,
            fields={},
            errors=["palari block must contain a JSON object"],
        )
    unknown = sorted(set(parsed) - GOVERNANCE_FIELDS)
    errors: list[str] = []
    if unknown:
        errors.append(f"unknown palari governance fields: {', '.join(unknown)}")
    fields = {key: value for key, value in parsed.items() if key in GOVERNANCE_FIELDS}
    for field_name in STRING_GOVERNANCE_FIELDS:
        if field_name in fields and not isinstance(fields[field_name], str):
            errors.append(f"palari.{field_name} must be a string")
    for field_name in STRING_LIST_GOVERNANCE_FIELDS:
        value = fields.get(field_name)
        if value is not None and (
            not isinstance(value, list) or not all(isinstance(item, str) for item in value)
        ):
            errors.append(f"palari.{field_name} must be a list of strings")
    missing = sorted(field_name for field_name in RECOMMENDED_BLOCK_FIELDS if field_name not in fields)
    warnings = [
        f"recommended palari fields are missing: {', '.join(missing)}"
    ] if missing else []
    return PalariBlock(
        present=True,
        valid=not errors,
        fields=dict(fields) if not errors else {},
        errors=errors,
        warnings=warnings,
        unknown_fields=unknown,
        missing_recommended_fields=missing,
    )


def linear_block_template(
    workspace_path: str,
    palari_id: str,
    goal_id: str,
    *,
    risk: str,
    intensity: str,
    scope: str,
    acceptance_target: str,
    parallel_policy: str = "independent",
    allowed_resources: list[str] | None = None,
    allowed_sources: list[str] | None = None,
    allowed_actions: list[str] | None = None,
    output_targets: list[str] | None = None,
    forbidden_actions: list[str] | None = None,
    verification_expectations: list[str] | None = None,
    recommended_playbooks: list[str] | None = None,
    conflict_targets: list[str] | None = None,
) -> dict[str, Any]:
    workspace = Workspace.load(workspace_path)
    fields = _clean_block_fields(
        {
            "goal": goal_id,
            "palari": palari_id,
            "risk": risk,
            "intensity": intensity,
            "scope": scope,
            "acceptance_target": acceptance_target,
            "parallel_policy": parallel_policy,
            "allowed_resources": allowed_resources or [],
            "allowed_sources": allowed_sources or [],
            "allowed_actions": allowed_actions or [],
            "output_targets": output_targets or [],
            "forbidden_actions": forbidden_actions or [],
            "verification_expectations": verification_expectations or [],
            "recommended_playbooks": recommended_playbooks or [],
            "conflict_targets": conflict_targets or [],
        }
    )
    block = PalariBlock(present=True, valid=True, fields=fields)
    validation = validate_block_against_workspace(workspace, block, palari_id=palari_id)
    if validation["errors"]:
        raise LinearAdapterError(
            "; ".join(validation["errors"]),
            code="LINEAR_BLOCK_TEMPLATE_INVALID",
            next_action="Fix the local Palari block inputs and rerun block-template.",
        )
    fenced = _fenced_palari_json(fields)
    parsed = parse_palari_block(fenced)
    return {
        "schema_version": "palari.linear_block_template.v1",
        "provider": "linear",
        "valid": parsed.valid,
        "fenced_block": fenced,
        "governance": block_payload(parsed),
        "warnings": validation["warnings"] + parsed.warnings,
        "next_action": "Paste fenced_block into the Linear issue description before importing.",
    }


def linear_inspect_block(
    workspace_path: str,
    issue_key: str,
    palari_id: str,
    *,
    client: LinearIssueClient | None = None,
) -> dict[str, Any]:
    client = client or LinearClient.from_env()
    issue = client.issue(issue_key)
    workspace = Workspace.load(workspace_path)
    block = parse_palari_block(issue["description"])
    validation = validate_block_against_workspace(workspace, block, palari_id=palari_id)
    errors = block.errors + validation["errors"]
    warnings = block.warnings + validation["warnings"]
    eligible = block.present and block.valid and not errors
    return {
        "schema_version": "palari.linear_inspect_block.v1",
        "provider": "linear",
        "issue": issue,
        "valid": eligible,
        "eligible_for_adopt_start": eligible,
        "governance": block_payload(block),
        "errors": errors,
        "warnings": warnings,
        "next_action": (
            f"Run `palari linear start {issue['key']} --as {palari_id} "
            "--adopt-by HUMAN-ID --json`."
            if eligible
            else "Fix the palari block in Linear before adopting or starting this issue."
        ),
    }


def block_payload(block: PalariBlock) -> dict[str, Any]:
    return {
        "present": block.present,
        "valid": block.valid,
        "error": block.error,
        "errors": list(block.errors),
        "warnings": list(block.warnings),
        "unknown_fields": list(block.unknown_fields),
        "missing_recommended_fields": list(block.missing_recommended_fields),
        "fields": deepcopy(block.fields),
    }


def default_goal(workspace: Workspace, palari_id: str) -> str:
    palari = workspace.palari(palari_id)
    if palari is None:
        raise WorkspaceError(f"palari not found: {palari_id}")
    if len(palari.linked_goals) == 1:
        return palari.linked_goals[0]
    active_goals = [goal.id for goal in workspace.goals if goal.status == "active"]
    if len(active_goals) == 1:
        return active_goals[0]
    raise WorkspaceError("linear import needs --goal or a palari block goal")


def validate_block_against_workspace(
    workspace: Workspace,
    block: PalariBlock,
    *,
    palari_id: str,
) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    fields = block.fields
    if not block.present:
        return {"errors": ["missing palari block"], "warnings": []}
    if not block.valid:
        return {"errors": list(block.errors), "warnings": list(block.warnings)}

    palari = fields.get("palari") or palari_id
    if fields.get("palari") and fields["palari"] != palari_id:
        errors.append(f"palari block targets {fields['palari']}, not command actor {palari_id}")
    if not palari:
        errors.append("palari is required")
    elif workspace.palari(str(palari)) is None:
        errors.append(f"palari not found: {palari}")

    goal = fields.get("goal")
    if not goal:
        try:
            goal = default_goal(workspace, palari_id)
            warnings.append(f"palari.goal omitted; would default to {goal}")
        except WorkspaceError:
            errors.append("goal is required when no unique default goal is available")
    elif workspace.goal(str(goal)) is None:
        errors.append(f"goal not found: {goal}")

    risk = fields.get("risk")
    if risk and risk not in RISKS:
        errors.append(f"risk must be one of: {', '.join(sorted(RISKS))}")
    intensity = fields.get("intensity")
    if intensity and intensity not in INTENSITIES:
        errors.append(f"intensity must be one of: {', '.join(sorted(INTENSITIES))}")
    parallel_policy = fields.get("parallel_policy")
    if parallel_policy and parallel_policy not in PARALLEL_POLICIES:
        errors.append(
            f"parallel_policy must be one of: {', '.join(sorted(PARALLEL_POLICIES))}"
        )

    for source_id in fields.get("allowed_sources", []):
        if workspace.source(source_id) is None:
            errors.append(f"allowed source not found: {source_id}")
    for target in fields.get("conflict_targets", []):
        if workspace.work_item(target) is None:
            errors.append(f"conflict target work item not found: {target}")

    warnings.extend(block.warnings)
    return {"errors": errors, "warnings": warnings}


def _clean_block_fields(fields: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if key in STRING_LIST_GOVERNANCE_FIELDS:
            if value:
                cleaned[key] = list(value)
            continue
        if isinstance(value, str) and value:
            cleaned[key] = value
    return cleaned


def _fenced_palari_json(fields: dict[str, Any]) -> str:
    return "```palari\n" + json.dumps(fields, indent=2, sort_keys=False) + "\n```"

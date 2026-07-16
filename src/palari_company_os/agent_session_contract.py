from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .path_policy import validate_workspace_path
from .pcaw_canonical import CanonicalJSONError, canonical_json_bytes, canonical_sha256
from .workspace import WorkspaceError


SESSION_CONTRACT_SCHEMA_VERSION = "palari.agent_session_contract.v1"
SESSION_CONTRACT_PREFIX = "SESSION-CONTRACT-"

_TOP_LEVEL_FIELDS = {
    "schema_version",
    "contract_id",
    "contract_digest",
    "status",
    "contract",
}
_CONTRACT_FIELDS = {
    "packet_binding",
    "identity",
    "scope",
    "obligations",
    "blockers",
    "guidance",
    "enforcement",
    "security_limitations",
}
_PACKET_BINDING_FIELDS = {
    "packet_schema_version",
    "packet_id",
    "packet_context_hash",
    "packet_status",
    "mode",
    "claim_required",
    "grants_authority",
}
_IDENTITY_FIELDS = {"workspace", "agent", "work_item"}
_SCOPE_FIELDS = {
    "read_paths",
    "write_paths",
    "resource_ids",
    "sources",
    "capabilities",
    "capability_policy",
    "dependencies",
    "forbidden_actions",
}
_OBLIGATION_FIELDS = {
    "instruction",
    "required_output",
    "completion_contract",
    "stop_conditions",
}
_GUIDANCE_FIELDS = {"next_allowed_commands"}
_ENFORCEMENT_FIELDS = {"profile", "adapter", "properties"}
_SOURCE_FIELDS = {
    "id",
    "access_mode",
    "authority",
    "data_class",
    "freshness_sla",
    "last_seen_revision",
    "redaction_required",
    "owner_human",
    "steward_human",
}
_CAPABILITY_FIELDS = {
    "id",
    "kind",
    "provider",
    "status",
    "risk_level",
    "derived",
    "allowed_actions",
    "source_ids",
}
_DEPENDENCY_FIELDS = {"id", "status", "title"}

_ENFORCEMENT = {
    "profile": "portable-declaration-v1",
    "adapter": "none",
    "properties": [
        {
            "id": "packet-and-claim-binding",
            "status": "palari-enforced",
            "message": "Palari binds a started claim to the exact persisted packet and contract digest.",
        },
        {
            "id": "human-authority",
            "status": "palari-enforced",
            "message": "Palari transition gates remain the authority for human decisions and acceptance.",
        },
        {
            "id": "external-write-authority",
            "status": "palari-enforced",
            "message": "Palari transition gates remain the authority for planned external writes.",
        },
        {
            "id": "write-boundary-before-tool",
            "status": "adapter-required",
            "message": "A host adapter must map the declared write paths into native pre-tool controls.",
        },
        {
            "id": "read-boundary",
            "status": "advisory",
            "message": "The portable contract declares read scope but does not sandbox host reads.",
        },
        {
            "id": "turn-completion",
            "status": "adapter-required",
            "message": "A host adapter must enforce stop-time boundary checks when supported.",
        },
    ],
}

_SECURITY_LIMITATIONS = [
    "This portable contract is a deterministic declaration and does not itself create an active claim.",
    "No native agent sandbox or hook is selected or installed by compilation.",
    "Host file and tool enforcement requires a separately verified adapter; unsupported properties remain advisory.",
    "Actor identifiers are declared workspace identities, not authentication against a hostile same-user process.",
    "The contract grants no review, human-decision, acceptance, merge, push, deployment, provider, or external-write authority.",
]


def compile_agent_session_contract(packet: dict[str, Any]) -> dict[str, Any]:
    """Compile one packet into deterministic, provider-neutral contract bytes."""

    _require_packet(packet)
    allowed_paths = packet.get("allowed_paths")
    if not isinstance(allowed_paths, dict):
        allowed_paths = {}
    status = str(packet.get("status") or "blocked")
    body = {
        "packet_binding": {
            "packet_schema_version": str(packet.get("schema_version") or ""),
            "packet_id": str(packet.get("packet_id") or ""),
            "packet_context_hash": str(packet.get("context_hash") or ""),
            "packet_status": status,
            "mode": str(packet.get("mode") or "execute"),
            "claim_required": True,
            "grants_authority": False,
        },
        "identity": {
            "workspace": str(packet.get("workspace") or ""),
            "agent": _identity(packet.get("agent"), ("id", "role")),
            "work_item": _identity(
                packet.get("work_item"),
                ("id", "title", "objective", "risk", "intensity"),
            ),
        },
        "scope": {
            "read_paths": _paths(allowed_paths.get("read"), "allowed_paths.read"),
            "write_paths": _paths(allowed_paths.get("write"), "allowed_paths.write"),
            "resource_ids": _strings(packet.get("allowed_resources"), "allowed_resources"),
            "sources": _sources(packet.get("allowed_sources")),
            "capabilities": _capabilities(packet.get("allowed_capabilities")),
            "capability_policy": _object(packet.get("capability_policy")),
            "dependencies": _dependencies(packet.get("dependencies")),
            "forbidden_actions": _strings(
                packet.get("forbidden_actions"), "forbidden_actions"
            ),
        },
        "obligations": {
            "instruction": str(packet.get("one_sentence_instruction") or ""),
            "required_output": _object(packet.get("required_output")),
            "completion_contract": _object(packet.get("completion_contract")),
            "stop_conditions": _strings(packet.get("stop_conditions"), "stop_conditions"),
        },
        "blockers": _blockers(packet.get("blockers")),
        "guidance": {
            "next_allowed_commands": _strings(
                packet.get("next_allowed_commands"), "next_allowed_commands"
            ),
        },
        "enforcement": deepcopy(_ENFORCEMENT),
        "security_limitations": list(_SECURITY_LIMITATIONS),
    }
    digest_payload = _digest_payload(status, body)
    digest = canonical_sha256(digest_payload)
    result = {
        "schema_version": SESSION_CONTRACT_SCHEMA_VERSION,
        "contract_id": _contract_id(digest),
        "contract_digest": digest,
        "status": status,
        "contract": body,
    }
    error = session_contract_error(result)
    if error:
        raise WorkspaceError(f"cannot compile portable session contract: {error}")
    return result


def session_contract_error(
    value: dict[str, Any],
    *,
    expected_packet: dict[str, Any] | None = None,
) -> str:
    """Return a fail-closed diagnostic for one contract, or an empty string."""

    try:
        canonical_json_bytes(value)
    except CanonicalJSONError as exc:
        return f"contract is not strict canonical JSON data: {exc}"
    if set(value) != _TOP_LEVEL_FIELDS:
        return _field_error("contract envelope", value, _TOP_LEVEL_FIELDS)
    if value.get("schema_version") != SESSION_CONTRACT_SCHEMA_VERSION:
        return "unsupported session contract schema_version"
    status = value.get("status")
    if status not in {"ready", "blocked"}:
        return "status must be ready or blocked"
    body = value.get("contract")
    if not isinstance(body, dict):
        return "contract must be an object"
    if set(body) != _CONTRACT_FIELDS:
        return _field_error("contract", body, _CONTRACT_FIELDS)
    shape_error = _body_error(body)
    if shape_error:
        return shape_error
    if body["packet_binding"]["packet_status"] != status:
        return "packet_binding.packet_status does not match envelope status"
    digest = value.get("contract_digest")
    expected_digest = canonical_sha256(_digest_payload(status, body))
    if digest != expected_digest:
        return "contract_digest does not match the canonical contract"
    if value.get("contract_id") != _contract_id(expected_digest):
        return "contract_id does not match contract_digest"
    if expected_packet is not None:
        try:
            expected = compile_agent_session_contract(expected_packet)
        except WorkspaceError as exc:
            return f"current packet cannot be compiled: {exc}"
        if value != expected:
            return "persisted contract differs from the current packet authority"
    return ""


def session_contract_summary(value: dict[str, Any]) -> dict[str, Any]:
    body_value = value.get("contract")
    body: dict[str, Any] = body_value if isinstance(body_value, dict) else {}
    enforcement_value = body.get("enforcement")
    enforcement: dict[str, Any] = (
        enforcement_value if isinstance(enforcement_value, dict) else {}
    )
    return {
        "schema_version": value.get("schema_version", ""),
        "contract_id": value.get("contract_id", ""),
        "contract_digest": value.get("contract_digest", ""),
        "status": value.get("status", "blocked"),
        "grants_authority": False,
        "claim_required": True,
        "enforcement_profile": enforcement.get("profile", ""),
        "host_adapter": enforcement.get("adapter", "none"),
    }


def _require_packet(packet: dict[str, Any]) -> None:
    if not isinstance(packet, dict):
        raise WorkspaceError("agent packet must be an object")
    if packet.get("schema_version") != "palari.agent_packet.v1":
        raise WorkspaceError("unsupported agent packet schema_version")
    if packet.get("status") not in {"ready", "blocked"}:
        raise WorkspaceError("agent packet status must be ready or blocked")
    packet_id = packet.get("packet_id")
    context_hash = packet.get("context_hash")
    if not isinstance(packet_id, str) or not packet_id:
        raise WorkspaceError("agent packet packet_id is missing")
    if not _valid_sha256(context_hash):
        raise WorkspaceError("agent packet context_hash is missing or malformed")
    stable = {
        key: value
        for key, value in packet.items()
        if key not in {"created_at", "context_hash"}
    }
    # Packet v1 predates RFC 8785 use and hashes with sorted compact JSON.
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    legacy_hash = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    if legacy_hash != context_hash:
        raise WorkspaceError("agent packet content does not match context_hash")


def _body_error(body: dict[str, Any]) -> str:
    packet_binding = body.get("packet_binding")
    if not isinstance(packet_binding, dict) or set(packet_binding) != _PACKET_BINDING_FIELDS:
        return _field_error("packet_binding", packet_binding, _PACKET_BINDING_FIELDS)
    if packet_binding.get("claim_required") is not True:
        return "packet_binding.claim_required must be true"
    if packet_binding.get("grants_authority") is not False:
        return "packet_binding.grants_authority must be false"
    if packet_binding.get("packet_status") not in {"ready", "blocked"}:
        return "packet_binding.packet_status must be ready or blocked"
    if packet_binding.get("packet_schema_version") != "palari.agent_packet.v1":
        return "packet_binding.packet_schema_version is unsupported"
    for field in ("packet_id", "mode"):
        if not isinstance(packet_binding.get(field), str) or not packet_binding[field]:
            return f"packet_binding.{field} must be a non-empty string"
    if packet_binding.get("mode") not in {"execute", "review"}:
        return "packet_binding.mode must be execute or review"
    if not _valid_sha256(packet_binding.get("packet_context_hash")):
        return "packet_binding.packet_context_hash is malformed"
    identity = body.get("identity")
    if not isinstance(identity, dict) or set(identity) != _IDENTITY_FIELDS:
        return _field_error("identity", identity, _IDENTITY_FIELDS)
    if not isinstance(identity.get("workspace"), str):
        return "identity.workspace must be a string"
    identity_error = _identity_error(
        identity.get("agent"), {"id", "role"}, "identity.agent"
    )
    if identity_error:
        return identity_error
    identity_error = _identity_error(
        identity.get("work_item"),
        {"id", "title", "objective", "risk", "intensity"},
        "identity.work_item",
    )
    if identity_error:
        return identity_error
    scope = body.get("scope")
    if not isinstance(scope, dict) or set(scope) != _SCOPE_FIELDS:
        return _field_error("scope", scope, _SCOPE_FIELDS)
    for field in ("read_paths", "write_paths"):
        try:
            _paths(scope.get(field), f"scope.{field}")
        except WorkspaceError as exc:
            return str(exc)
    for field in ("resource_ids", "forbidden_actions"):
        error = _string_list_error(scope.get(field), f"scope.{field}")
        if error:
            return error
    collection_error = _object_collection_error(
        scope.get("sources"), _SOURCE_FIELDS, "scope.sources"
    )
    if collection_error:
        return collection_error
    for index, source in enumerate(scope["sources"]):
        for field in _SOURCE_FIELDS - {"redaction_required"}:
            if not isinstance(source.get(field), str):
                return f"scope.sources[{index}].{field} must be a string"
        if type(source.get("redaction_required")) is not bool:
            return f"scope.sources[{index}].redaction_required must be boolean"
    collection_error = _object_collection_error(
        scope.get("capabilities"), _CAPABILITY_FIELDS, "scope.capabilities"
    )
    if collection_error:
        return collection_error
    for index, capability in enumerate(scope["capabilities"]):
        for field in _CAPABILITY_FIELDS - {"derived", "allowed_actions", "source_ids"}:
            if not isinstance(capability.get(field), str):
                return f"scope.capabilities[{index}].{field} must be a string"
        if type(capability.get("derived")) is not bool:
            return f"scope.capabilities[{index}].derived must be boolean"
        for field in ("allowed_actions", "source_ids"):
            error = _string_list_error(
                capability.get(field), f"scope.capabilities[{index}].{field}"
            )
            if error:
                return error
    collection_error = _object_collection_error(
        scope.get("dependencies"), _DEPENDENCY_FIELDS, "scope.dependencies"
    )
    if collection_error:
        return collection_error
    for index, dependency in enumerate(scope["dependencies"]):
        if not all(isinstance(item, str) for item in dependency.values()):
            return f"scope.dependencies[{index}] fields must be strings"
    if not isinstance(scope.get("capability_policy"), dict):
        return "scope.capability_policy must be an object"
    obligations = body.get("obligations")
    if not isinstance(obligations, dict) or set(obligations) != _OBLIGATION_FIELDS:
        return _field_error("obligations", obligations, _OBLIGATION_FIELDS)
    if not isinstance(obligations.get("instruction"), str):
        return "obligations.instruction must be a string"
    for field in ("required_output", "completion_contract"):
        if not isinstance(obligations.get(field), dict):
            return f"obligations.{field} must be an object"
    error = _string_list_error(
        obligations.get("stop_conditions"), "obligations.stop_conditions"
    )
    if error:
        return error
    required_output = obligations["required_output"]
    for field in ("fallback_write_paths", "output_targets"):
        if field in required_output:
            try:
                _paths(required_output[field], f"obligations.required_output.{field}")
            except WorkspaceError as exc:
                return str(exc)
    guidance = body.get("guidance")
    if not isinstance(guidance, dict) or set(guidance) != _GUIDANCE_FIELDS:
        return _field_error("guidance", guidance, _GUIDANCE_FIELDS)
    error = _string_list_error(
        guidance.get("next_allowed_commands"), "guidance.next_allowed_commands"
    )
    if error:
        return error
    enforcement = body.get("enforcement")
    if not isinstance(enforcement, dict) or set(enforcement) != _ENFORCEMENT_FIELDS:
        return _field_error("enforcement", enforcement, _ENFORCEMENT_FIELDS)
    if enforcement != _ENFORCEMENT:
        return "enforcement declaration differs from the supported v1 profile"
    if body.get("security_limitations") != _SECURITY_LIMITATIONS:
        return "security_limitations differ from the supported v1 profile"
    if not isinstance(body.get("blockers"), list) or not all(
        isinstance(item, dict) for item in body["blockers"]
    ):
        return "blockers must be a list of objects"
    if not isinstance(body.get("security_limitations"), list):
        return "security_limitations must be a list"
    return ""


def _identity(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    if value is None:
        return {field: "" for field in fields}
    if not isinstance(value, dict):
        raise WorkspaceError("packet identity must be an object")
    return {field: deepcopy(value.get(field, "")) for field in fields}


def _sources(value: Any) -> list[dict[str, Any]]:
    fields = tuple(sorted(_SOURCE_FIELDS))
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError("allowed_sources must be a list of objects")
    result = [_identity(item, fields) for item in value]
    return sorted(result, key=lambda item: str(item.get("id") or ""))


def _capabilities(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError("allowed_capabilities must be a list of objects")
    result: list[dict[str, Any]] = []
    for item in value:
        derived = item.get("derived", False)
        if type(derived) is not bool:
            raise WorkspaceError("allowed_capabilities.derived must be boolean")
        for field in ("id", "kind", "provider", "status", "risk_level"):
            if field in item and not isinstance(item[field], str):
                raise WorkspaceError(f"allowed_capabilities.{field} must be a string")
        result.append(
            {
                "id": str(item.get("id") or ""),
                "kind": str(item.get("kind") or ""),
                "provider": str(item.get("provider") or ""),
                "status": str(item.get("status") or ""),
                "risk_level": str(item.get("risk_level") or ""),
                "derived": derived,
                "allowed_actions": _strings(
                    item.get("allowed_actions"), "allowed_capabilities.allowed_actions"
                ),
                "source_ids": _strings(
                    item.get("source_ids"), "allowed_capabilities.source_ids"
                ),
            }
        )
    return sorted(result, key=lambda item: item["id"])


def _dependencies(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError("dependencies must be a list of objects")
    result = [
        _identity(item, ("id", "status", "title"))
        for item in value
    ]
    return sorted(result, key=lambda item: str(item.get("id") or ""))


def _blockers(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise WorkspaceError("blockers must be a list of objects")
    result = [deepcopy(item) for item in value]
    return sorted(
        result,
        key=lambda item: (str(item.get("code") or ""), str(item.get("message") or "")),
    )


def _paths(value: Any, field: str) -> list[str]:
    paths = _strings(value, field)
    if len(paths) != len(set(paths)):
        raise WorkspaceError(f"{field} contains duplicate paths")
    for path in paths:
        try:
            normalized = validate_workspace_path(path)
        except ValueError as exc:
            raise WorkspaceError(f"{field} contains unsafe path {path!r}: {exc}") from exc
        if normalized != path:
            raise WorkspaceError(f"{field} contains non-canonical path {path!r}")
    return paths


def _strings(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkspaceError(f"{field} must be a list of strings")
    return list(value)


def _object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise WorkspaceError("packet contract field must be an object")
    return deepcopy(value)


def _digest_payload(status: Any, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SESSION_CONTRACT_SCHEMA_VERSION,
        "status": status,
        "contract": body,
    }


def _contract_id(digest: str) -> str:
    return SESSION_CONTRACT_PREFIX + digest.removeprefix("sha256:")[:24].upper()


def _valid_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        return False
    return all(character in "0123456789abcdef" for character in value[7:])


def _field_error(label: str, value: Any, expected: set[str]) -> str:
    if not isinstance(value, dict):
        return f"{label} must be an object"
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    details: list[str] = []
    if unknown:
        details.append(f"unknown fields: {', '.join(unknown)}")
    if missing:
        details.append(f"missing fields: {', '.join(missing)}")
    return f"{label} has " + "; ".join(details)


def _identity_error(value: Any, fields: set[str], label: str) -> str:
    if not isinstance(value, dict) or set(value) != fields:
        return _field_error(label, value, fields)
    if not all(isinstance(item, str) for item in value.values()):
        return f"{label} fields must be strings"
    return ""


def _string_list_error(value: Any, label: str) -> str:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return f"{label} must be a list of strings"
    return ""


def _object_collection_error(value: Any, fields: set[str], label: str) -> str:
    if not isinstance(value, list):
        return f"{label} must be a list"
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != fields:
            return _field_error(f"{label}[{index}]", item, fields)
    return ""

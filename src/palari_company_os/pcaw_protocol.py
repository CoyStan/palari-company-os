from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .governance_case import GovernanceCase
from .governance_kernel import evaluate_governance_case
from .pcaw_canonical import (
    CanonicalJSONError,
    canonical_json_bytes,
    canonical_sha256,
    strict_json_loads,
)
from .pcaw_subjects import SubjectError, hash_subject, subject_diagnostic, validate_subject_name


STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://palari.dev/pcaw/v1"
PREDICATE_SCHEMA = "pcaw.v1"
REPORT_SCHEMA = "pcaw.verification.v1"
PROPERTY_NAMES = (
    "scope_compliance",
    "subject_integrity",
    "evidence_freshness",
    "receipt_binding",
    "independent_review",
    "human_quorum",
    "acceptance_currency",
    "journal_continuity",
)
SECURITY_LIMITATIONS = [
    "actor-attribution-declared-not-authenticated",
    "no-signatures-or-key-custody",
    "same-user-tampering-not-prevented",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])T"
    r"([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](\.[0-9]+)?Z$"
)


def verify_pcaw_file(
    proof_file: Path | str,
    *,
    subject_root: Path | str = "",
    statement_only: bool = False,
) -> dict[str, Any]:
    """Verify a PCAW statement offline without loading a Palari workspace."""

    try:
        path = Path(proof_file).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        return _proof_unreadable_report(statement_only, exc)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _proof_unreadable_report(statement_only, exc)
    try:
        root = (
            Path(subject_root).expanduser().resolve()
            if str(subject_root)
            else path.parent
        )
    except (OSError, RuntimeError) as exc:
        report = _empty_report(statement_only, raw)
        report["errors"].append(
            _diag(
                "SUBJECT_ROOT_INVALID",
                "$.subject",
                f"subject root cannot be resolved safely: {exc}",
                "Select a real subject directory without symlink cycles and verify again.",
            )
        )
        return _finalize(report)
    return verify_pcaw_bytes(raw, subject_root=root, statement_only=statement_only)


def verify_pcaw_bytes(
    raw: bytes,
    *,
    subject_root: Path | str,
    statement_only: bool = False,
) -> dict[str, Any]:
    report = _empty_report(statement_only, raw)
    try:
        statement = strict_json_loads(raw)
    except (CanonicalJSONError, TypeError) as exc:
        report["errors"].append(_canonical_diagnostic(exc))
        return _finalize(report)
    try:
        canonical = canonical_json_bytes(statement)
    except (CanonicalJSONError, TypeError) as exc:
        report["errors"].append(_canonical_diagnostic(exc))
        return _finalize(report)
    if raw != canonical:
        report["errors"].append(
            _diag(
                "NON_CANONICAL_JSON",
                "$",
                "statement bytes are not the canonical PCAW JSON encoding",
                "Canonicalize the statement exactly once and export it again.",
            )
        )
        return _finalize(report)

    try:
        predicate, case, subjects, roles = _parse_statement(statement)
    except ValueError as exc:
        report["errors"].append(_schema_diagnostic(exc))
        return _finalize(report)

    report["claimed_state"] = str(predicate["claimed_state"])
    timestamp_error = _timestamp_error(case.to_dict())
    if timestamp_error is not None:
        report["errors"].append(timestamp_error)

    work_names = [name for name, role in roles.items() if role == "work-state"]
    artifact_names = [name for name, role in roles.items() if role == "output-artifact"]
    if len(work_names) != 1:
        report["errors"].append(
            _diag(
                "SUBJECT_ROLE_MISMATCH",
                "$.predicate.subject_roles",
                "statement must declare exactly one work-state subject",
                "Export the statement again from the current governed work item.",
            )
        )
    else:
        work_name = work_names[0]
        expected_name = f"urn:palari:work-state:{case.contract.id}"
        if work_name != expected_name:
            report["errors"].append(
                _diag(
                    "SUBJECT_ROLE_MISMATCH",
                    "$.predicate.subject_roles",
                    "work-state subject name does not identify the governed work item",
                    "Use the required urn:palari:work-state:WORK-ID subject name.",
                )
            )
        declared = subjects.get(work_name, "")
        actual = canonical_sha256(case.to_dict()).removeprefix("sha256:")
        if declared != actual:
            report["errors"].append(
                _diag(
                    "WORK_STATE_DIGEST_MISMATCH",
                    "$.subject",
                    "work-state digest does not match the canonical governance case",
                    "Re-export the proof from the exact current governance case.",
                )
            )

    evidence_artifacts = set(case.evidence.artifacts if case.evidence is not None else ())
    evidence_hashes = (
        {item.path: item for item in case.evidence.artifact_hashes}
        if case.evidence is not None
        else {}
    )
    evidence_subject_mismatch = False
    if set(artifact_names) != evidence_artifacts:
        evidence_subject_mismatch = True
        report["errors"].append(
            _diag(
                "SUBJECT_ROLE_MISMATCH",
                "$.predicate.subject_roles",
                "output subject roles do not exactly cover the evidence artifacts",
                "Export one output-artifact subject for every declared evidence artifact.",
            )
        )
    if (
        len(evidence_hashes)
        != len(case.evidence.artifact_hashes if case.evidence is not None else ())
        or set(evidence_hashes) != evidence_artifacts
        or any(
            evidence_hashes[name].status != "present"
            or evidence_hashes[name].sha256 != subjects.get(name)
            for name in evidence_artifacts
            if name in evidence_hashes
        )
    ):
        evidence_subject_mismatch = True
        report["errors"].append(
            _diag(
                "PCAW_EVIDENCE_SUBJECT_MISMATCH",
                "$.predicate.governance_case.evidence.artifact_hashes",
                "evidence artifact digests do not exactly match output subjects",
                "Refresh evidence and export subjects from the same exact artifact bytes.",
            )
        )

    evaluation = evaluate_governance_case(case).to_dict()
    _merge_evaluation(report, evaluation)
    if evidence_subject_mismatch:
        report["verified_properties"]["evidence_freshness"] = "failed"
    if predicate["claimed_state"] != case.claimed_state:
        report["errors"].append(
            _diag(
                "CLAIMED_STATE_MISMATCH",
                "$.predicate.claimed_state",
                "predicate and governance case claim different lifecycle states",
                "Re-export the statement from one current governance state.",
            )
        )
    if report["derived_lifecycle_state"] != predicate["claimed_state"]:
        report["errors"].append(
            _diag(
                "CLAIMED_STATE_MISMATCH",
                "$.predicate.claimed_state",
                "claimed lifecycle state differs from the independently derived state",
                "Repair the lifecycle records or export the actual current state.",
            )
        )

    if statement_only and artifact_names:
        report["subject_digest_status"] = "not-checked"
        report["verified_properties"]["subject_integrity"] = "not-checked"
        report["warnings"].append(
            _diag(
                "ARTIFACT_CHECKS_SKIPPED",
                "$.subject",
                "statement-only verification did not read output artifact bytes",
                "Run full verification with the exact artifacts beneath the subject root.",
            )
        )
    elif artifact_names:
        _verify_artifacts(report, subjects, artifact_names, Path(subject_root))
    else:
        report["subject_digest_status"] = "not-applicable"
        if report["verified_properties"]["subject_integrity"] == "not-checked":
            report["verified_properties"]["subject_integrity"] = "not-applicable"

    return _finalize(report)


def build_pcaw_statement(
    governance_case: GovernanceCase,
    artifact_subjects: list[dict[str, str]],
) -> dict[str, Any]:
    work_name = f"urn:palari:work-state:{governance_case.contract.id}"
    subjects = [
        {
            "name": work_name,
            "digest": {
                "sha256": canonical_sha256(governance_case.to_dict()).removeprefix("sha256:")
            },
        }
    ]
    roles = [{"name": work_name, "role": "work-state"}]
    seen = {work_name}
    for item in sorted(artifact_subjects, key=lambda value: value["name"]):
        name = validate_subject_name(item["name"])
        digest = str(item["sha256"])
        if name in seen:
            raise ValueError(f"duplicate statement subject: {name}")
        if not SHA256_RE.fullmatch(digest):
            raise ValueError(f"artifact subject has invalid SHA-256 digest: {name}")
        seen.add(name)
        subjects.append({"name": name, "digest": {"sha256": digest}})
        roles.append({"name": name, "role": "output-artifact"})
    return {
        "_type": STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "schema_version": PREDICATE_SCHEMA,
            "claimed_state": governance_case.claimed_state,
            "governance_case": governance_case.to_dict(),
            "subject_roles": roles,
            "security_limitations": list(SECURITY_LIMITATIONS),
        },
    }


def _parse_statement(
    value: Any,
) -> tuple[dict[str, Any], GovernanceCase, dict[str, str], dict[str, str]]:
    _exact_object(value, {"_type", "subject", "predicateType", "predicate"}, "statement")
    if value["_type"] != STATEMENT_TYPE:
        raise ValueError("statement._type uses an unsupported envelope")
    if value["predicateType"] != PREDICATE_TYPE:
        raise ValueError("statement.predicateType is unsupported")
    predicate = value["predicate"]
    _exact_object(
        predicate,
        {
            "schema_version",
            "claimed_state",
            "governance_case",
            "subject_roles",
            "security_limitations",
        },
        "predicate",
    )
    if predicate["schema_version"] != PREDICATE_SCHEMA:
        raise ValueError("predicate.schema_version is unsupported")
    if not isinstance(predicate["claimed_state"], str):
        raise ValueError("predicate.claimed_state must be a string")
    if predicate["security_limitations"] != SECURITY_LIMITATIONS:
        raise ValueError("predicate.security_limitations must contain the PCAW v1 non-claims")
    case_value = predicate["governance_case"]
    if not isinstance(case_value, dict):
        raise ValueError("predicate.governance_case must be an object")
    case = GovernanceCase.from_dict(case_value)

    subject_items = value["subject"]
    if not isinstance(subject_items, list) or not subject_items:
        raise ValueError("statement.subject must be a non-empty array")
    subjects: dict[str, str] = {}
    for index, item in enumerate(subject_items):
        _exact_object(item, {"name", "digest"}, f"subject[{index}]")
        name = item["name"]
        if not isinstance(name, str) or not name:
            raise ValueError(f"subject[{index}].name must be a non-empty string")
        if name in subjects:
            raise ValueError(f"subject[{index}].name is duplicated")
        digest = item["digest"]
        if isinstance(digest, dict) and set(digest) != {"sha256"}:
            raise ValueError(
                f"subject[{index}].digest uses an unsupported digest algorithm"
            )
        _exact_object(digest, {"sha256"}, f"subject[{index}].digest")
        digest_value = digest["sha256"]
        if not isinstance(digest_value, str) or not SHA256_RE.fullmatch(digest_value):
            raise ValueError(f"subject[{index}].digest.sha256 must be lowercase SHA-256")
        subjects[name] = digest_value

    role_items = predicate["subject_roles"]
    if not isinstance(role_items, list) or not role_items:
        raise ValueError("predicate.subject_roles must be a non-empty array")
    roles: dict[str, str] = {}
    for index, item in enumerate(role_items):
        _exact_object(item, {"name", "role"}, f"subject_roles[{index}]")
        name = item["name"]
        role = item["role"]
        if not isinstance(name, str) or name in roles:
            raise ValueError(f"subject_roles[{index}].name is invalid or duplicated")
        if role not in {"work-state", "output-artifact"}:
            raise ValueError(f"subject_roles[{index}].role is unsupported")
        roles[name] = role
    if set(subjects) != set(roles):
        raise ValueError("subjects and subject roles do not match one-to-one")
    for name, role in roles.items():
        if role == "output-artifact":
            validate_subject_name(name)
    return predicate, case, subjects, roles


def _verify_artifacts(
    report: dict[str, Any],
    subjects: dict[str, str],
    names: list[str],
    root: Path,
) -> None:
    failed = False
    for name in sorted(names):
        try:
            actual = hash_subject(root, name)
        except SubjectError as exc:
            failed = True
            diagnostic = subject_diagnostic(exc, f"$.subject[{name!r}]")
            code_map = {
                "PCAW_SUBJECT_PATH_UNSAFE": "SUBJECT_PATH_UNSAFE",
                "PCAW_SUBJECT_MISSING": "SUBJECT_MISSING",
                "PCAW_SUBJECT_SYMLINK": "SUBJECT_SYMLINK_ESCAPE",
                "PCAW_SUBJECT_ROOT_INVALID": "SUBJECT_ROOT_INVALID",
            }
            diagnostic["code"] = code_map.get(exc.code, exc.code.removeprefix("PCAW_"))
            report["errors"].append(diagnostic)
            continue
        if actual != subjects[name]:
            failed = True
            report["errors"].append(
                _diag(
                    "SUBJECT_DIGEST_MISMATCH",
                    f"$.subject[{name!r}].digest.sha256",
                    f"artifact digest does not match statement: {name}",
                    "Restore the exact artifact bytes or export a new proof after governed review.",
                )
            )
    report["subject_digest_status"] = "failed" if failed else "verified"
    report["verified_properties"]["subject_integrity"] = (
        "failed" if failed else "verified"
    )


def _merge_evaluation(report: dict[str, Any], evaluation: dict[str, Any]) -> None:
    report["derived_lifecycle_state"] = str(
        evaluation.get("derived_state") or evaluation.get("derived_lifecycle_state") or ""
    )
    properties = evaluation.get("properties", {})
    if isinstance(properties, list):
        properties = {
            str(item.get("name")): str(item.get("status"))
            for item in properties
            if isinstance(item, dict)
        }
    for name in PROPERTY_NAMES:
        value = properties.get(name, "not-checked") if isinstance(properties, dict) else "not-checked"
        if isinstance(value, dict):
            value = value.get("status", "not-checked")
        public_value = "not-applicable" if value == "not-required" else str(value)
        report["verified_properties"][name] = public_value
    for kind in ("errors", "warnings"):
        for item in evaluation.get(kind, []):
            if isinstance(item, dict):
                report[kind].append(
                    _diag(
                        str(item.get("code", "GOVERNANCE_INVALID")),
                        str(item.get("path", "$.predicate.governance_case")),
                        str(item.get("message", "governance consistency check failed")),
                        str(item.get("next_action", "Repair the current governance records.")),
                    )
                )


def _empty_report(statement_only: bool, raw: bytes) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "verified": False,
        "fully_verified": False,
        "acceptance_verified": False,
        "verification_level": "statement-only" if statement_only else "full",
        "statement_digest": {
            "algorithm": "sha256",
            "value": hashlib.sha256(raw).hexdigest(),
        },
        "claimed_state": "",
        "derived_lifecycle_state": "",
        "subject_digest_status": "missing",
        "verified_properties": {name: "not-checked" for name in PROPERTY_NAMES},
        "errors": [],
        "warnings": [],
        "security_limitations": list(SECURITY_LIMITATIONS),
    }


def _proof_unreadable_report(
    statement_only: bool,
    error: Exception,
) -> dict[str, Any]:
    report = _empty_report(statement_only, b"")
    report["errors"].append(
        _diag(
            "PROOF_UNREADABLE",
            "$",
            f"proof file cannot be read: {error}",
            "Restore a readable proof file and verify again.",
        )
    )
    return _finalize(report)


def _finalize(report: dict[str, Any]) -> dict[str, Any]:
    report["errors"] = _sorted_unique_diagnostics(report["errors"])
    report["warnings"] = _sorted_unique_diagnostics(report["warnings"])
    report["verified"] = not report["errors"]
    full_subjects = report["subject_digest_status"] in {"verified", "not-applicable"}
    report["fully_verified"] = bool(
        report["verified"]
        and report["verification_level"] == "full"
        and full_subjects
    )
    acceptance_properties = (
        "scope_compliance",
        "subject_integrity",
        "evidence_freshness",
        "receipt_binding",
        "independent_review",
        "human_quorum",
        "acceptance_currency",
    )
    report["acceptance_verified"] = bool(
        report["fully_verified"]
        and report["derived_lifecycle_state"] in {"accepted", "completed"}
        and all(
            report["verified_properties"][name] in {"verified", "not-applicable"}
            for name in acceptance_properties
        )
    )
    return report


def _exact_object(value: Any, fields: set[str], path: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    unknown = sorted(set(value) - fields)
    missing = sorted(fields - set(value))
    if unknown:
        raise ValueError(f"{path} has unknown field(s): {', '.join(unknown)}")
    if missing:
        raise ValueError(f"{path} is missing field(s): {', '.join(missing)}")


def _timestamp_error(value: Any, path: str = "$.predicate.governance_case") -> dict[str, str] | None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in {"timestamp", "accepted_at", "started_at", "updated_at"}:
                if not isinstance(item, str) or (item and not _valid_timestamp(item)):
                    return _diag(
                        "AMBIGUOUS_TIMESTAMP",
                        child_path,
                        "timestamp must be empty or normalized UTC RFC 3339 ending in Z",
                        "Normalize the timestamp to an unambiguous UTC instant and re-export.",
                    )
            error = _timestamp_error(item, child_path)
            if error is not None:
                return error
    elif isinstance(value, list):
        for index, item in enumerate(value):
            error = _timestamp_error(item, f"{path}[{index}]")
            if error is not None:
                return error
    return None


def _valid_timestamp(value: str) -> bool:
    if not TIMESTAMP_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    return True


def _canonical_diagnostic(error: Exception) -> dict[str, str]:
    message = str(error)
    lowered = message.lower()
    if "utf-8" in lowered:
        code = "INVALID_UTF8"
    elif "duplicate" in lowered:
        code = "DUPLICATE_KEY"
    elif "floating" in lowered or "non-finite" in lowered:
        code = "FLOAT_FORBIDDEN"
    elif "integer" in lowered and "range" in lowered:
        code = "INTEGER_OUT_OF_RANGE"
    elif "unicode" in lowered or "surrogate" in lowered or "noncharacter" in lowered:
        code = "INVALID_UNICODE"
    else:
        code = "INVALID_JSON"
    return _diag(code, "$", message, "Export a strict canonical PCAW JSON statement.")


def _schema_diagnostic(error: ValueError) -> dict[str, str]:
    message = str(error)
    lowered = message.lower()
    if "unknown field" in lowered:
        code = "UNKNOWN_FIELD"
    elif "unsupported digest algorithm" in lowered:
        code = "UNSUPPORTED_DIGEST_ALGORITHM"
    elif "unsupported" in lowered and "schema" in lowered:
        code = "UNSUPPORTED_SCHEMA_VERSION"
    elif "subject" in lowered and ("path" in lowered or "relative" in lowered):
        code = "SUBJECT_PATH_UNSAFE"
    elif "subject" in lowered or "role" in lowered:
        code = "SUBJECT_ROLE_MISMATCH"
    else:
        code = "SCHEMA_INVALID"
    return _diag(
        code,
        "$.predicate",
        message,
        "Repair the protocol fields and export the statement again.",
    )


def _diag(code: str, path: str, message: str, next_action: str) -> dict[str, str]:
    return {
        "code": code,
        "path": path,
        "message": message,
        "next_action": next_action,
    }


def _sorted_unique_diagnostics(items: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in items:
        key = (item["path"], item["code"], item["message"])
        unique[key] = item
    return [unique[key] for key in sorted(unique)]

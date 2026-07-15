#!/usr/bin/env python3
"""Run the PCAW v1 corpus against a black-box verifier command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


CORPUS_SCHEMA = "pcaw.conformance.v1"
REPORT_SCHEMA = "pcaw.verification.v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run PCAW v1 conformance vectors. Put the verifier command after --; "
            "the runner appends FILE --subject-root DIR --json."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("vectors") / "manifest.json",
        help="Conformance manifest path.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-vector timeout in seconds.",
    )
    parser.add_argument(
        "verifier",
        nargs=argparse.REMAINDER,
        help="Verifier command prefix after --, for example: -- palari proof verify",
    )
    return parser


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read conformance manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("conformance manifest root must be an object")
    if payload.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"conformance manifest schema_version must be {CORPUS_SCHEMA}")
    if set(payload) != {"schema_version", "cases"}:
        raise ValueError("conformance manifest has unknown or missing fields")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("conformance manifest cases must be a non-empty array")
    return payload


def _safe_corpus_path(root: Path, raw: object, *, field: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{field} must be a non-empty relative path")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field} must stay inside the corpus")
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field} resolves outside the corpus") from exc
    return target


def _diagnostic_codes(report: dict[str, Any], field: str) -> set[str]:
    values = report.get(field, [])
    if not isinstance(values, list):
        return set()
    return {
        str(item.get("code"))
        for item in values
        if isinstance(item, dict) and isinstance(item.get("code"), str)
    }


def _check_case(
    case: object,
    *,
    index: int,
    corpus_root: Path,
    verifier: list[str],
    timeout: float,
) -> list[str]:
    if not isinstance(case, dict):
        return [f"case {index}: case must be an object"]
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        return [f"case {index}: id must be a non-empty string"]
    allowed = {
        "id",
        "statement",
        "subject_root",
        "statement_only",
        "expected_exit",
        "expected",
    }
    unknown = sorted(set(case) - allowed)
    if unknown:
        return [f"{case_id}: unknown manifest fields: {', '.join(unknown)}"]
    try:
        statement = _safe_corpus_path(corpus_root, case.get("statement"), field="statement")
        subject_root = _safe_corpus_path(
            corpus_root,
            case.get("subject_root"),
            field="subject_root",
        )
    except ValueError as exc:
        return [f"{case_id}: {exc}"]

    command = [*verifier, str(statement), "--subject-root", str(subject_root)]
    if case.get("statement_only") is True:
        command.append("--statement-only")
    command.append("--json")
    try:
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"{case_id}: verifier could not run: {exc}"]

    failures: list[str] = []
    expected_exit = case.get("expected_exit")
    if type(expected_exit) is not int:
        failures.append(f"{case_id}: expected_exit must be an integer")
    elif result.returncode != expected_exit:
        failures.append(
            f"{case_id}: exit {result.returncode}, expected {expected_exit}; "
            f"stderr={result.stderr.strip()!r}"
        )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        failures.append(f"{case_id}: stdout is not one JSON value: {exc}")
        return failures
    if not isinstance(report, dict):
        failures.append(f"{case_id}: report root is not an object")
        return failures
    if report.get("schema_version") != REPORT_SCHEMA:
        failures.append(
            f"{case_id}: report schema_version is {report.get('schema_version')!r}, "
            f"expected {REPORT_SCHEMA!r}"
        )

    expected = case.get("expected")
    if not isinstance(expected, dict):
        failures.append(f"{case_id}: expected must be an object")
        return failures
    allowed_expected = {
        "verified",
        "fully_verified",
        "acceptance_verified",
        "verification_level",
        "claimed_state",
        "derived_lifecycle_state",
        "subject_digest_status",
        "properties",
        "error_codes",
        "warning_codes",
    }
    unknown_expected = sorted(set(expected) - allowed_expected)
    if unknown_expected:
        failures.append(
            f"{case_id}: unknown expected fields: {', '.join(unknown_expected)}"
        )
    for field in (
        "verified",
        "fully_verified",
        "acceptance_verified",
        "verification_level",
        "claimed_state",
        "derived_lifecycle_state",
        "subject_digest_status",
    ):
        if field in expected and report.get(field) != expected[field]:
            failures.append(
                f"{case_id}: {field}={report.get(field)!r}, expected {expected[field]!r}"
            )
    properties = expected.get("properties", {})
    actual_properties = report.get("verified_properties", {})
    if not isinstance(properties, dict) or not isinstance(actual_properties, dict):
        failures.append(f"{case_id}: expected and reported properties must be objects")
    else:
        for name, status in properties.items():
            if actual_properties.get(name) != status:
                failures.append(
                    f"{case_id}: property {name}={actual_properties.get(name)!r}, "
                    f"expected {status!r}"
                )
    for expected_field, report_field in (
        ("error_codes", "errors"),
        ("warning_codes", "warnings"),
    ):
        expected_codes = expected.get(expected_field, [])
        if not isinstance(expected_codes, list) or not all(
            isinstance(code, str) for code in expected_codes
        ):
            failures.append(f"{case_id}: {expected_field} must be an array of strings")
            continue
        missing = set(expected_codes) - _diagnostic_codes(report, report_field)
        if missing:
            failures.append(
                f"{case_id}: missing {report_field} codes: {', '.join(sorted(missing))}"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    verifier = list(args.verifier)
    if verifier[:1] == ["--"]:
        verifier = verifier[1:]
    if not verifier:
        print("conformance error: put the verifier command after --", file=sys.stderr)
        return 2
    try:
        manifest_path = args.manifest.expanduser().resolve()
        manifest = _load_manifest(manifest_path)
    except ValueError as exc:
        print(f"conformance error: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    corpus_root = manifest_path.parent
    for index, case in enumerate(manifest["cases"]):
        case_failures = _check_case(
            case,
            index=index,
            corpus_root=corpus_root,
            verifier=verifier,
            timeout=args.timeout,
        )
        case_id = case.get("id", index) if isinstance(case, dict) else index
        if case_failures:
            print(f"FAIL {case_id}")
            failures.extend(case_failures)
        else:
            print(f"PASS {case_id}")
    if failures:
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(f"PCAW conformance failed: {len(failures)} finding(s).", file=sys.stderr)
        return 1
    print(f"PCAW conformance passed: {len(manifest['cases'])} vector(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

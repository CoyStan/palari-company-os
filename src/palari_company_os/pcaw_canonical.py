from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn


IJSON_MAX_INTEGER = 9_007_199_254_740_991


class CanonicalJSONError(ValueError):
    """Raised when input cannot be represented by the PCAW I-JSON subset."""


def strict_json_loads(data: str | bytes | bytearray) -> Any:
    """Load strict I-JSON while rejecting ambiguous or non-portable values."""

    if isinstance(data, (bytes, bytearray)):
        try:
            text = bytes(data).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise CanonicalJSONError("JSON must be valid UTF-8") from exc
    elif isinstance(data, str):
        text = data
    else:
        raise TypeError("strict_json_loads expects str or bytes")
    if text.startswith("\ufeff"):
        raise CanonicalJSONError("JSON must not include a UTF-8 BOM")

    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_from_pairs,
            parse_int=_parse_integer,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except CanonicalJSONError:
        raise
    except json.JSONDecodeError as exc:
        raise CanonicalJSONError(f"invalid JSON: {exc.msg}") from exc
    _validate_ijson(value, path="$", seen=set())
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return RFC 8785-compatible bytes for PCAW's no-float I-JSON subset."""

    _validate_ijson(value, path="$", seen=set())
    return _encode(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Return a domain-neutral SHA-256 digest of canonical JSON bytes."""

    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalJSONError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def _parse_integer(text: str) -> int:
    value = int(text)
    if not -IJSON_MAX_INTEGER <= value <= IJSON_MAX_INTEGER:
        raise CanonicalJSONError(
            f"integer is outside the interoperable I-JSON range: {text}"
        )
    return value


def _reject_float(text: str) -> NoReturn:
    raise CanonicalJSONError(f"floating-point numbers are not supported: {text}")


def _reject_constant(text: str) -> NoReturn:
    raise CanonicalJSONError(f"non-finite numbers are not valid I-JSON: {text}")


def _validate_ijson(value: Any, *, path: str, seen: set[int]) -> None:
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -IJSON_MAX_INTEGER <= value <= IJSON_MAX_INTEGER:
            raise CanonicalJSONError(f"{path} integer is outside the I-JSON range")
        return
    if isinstance(value, float):
        raise CanonicalJSONError(f"{path} floating-point numbers are not supported")
    if isinstance(value, str):
        _validate_string(value, path)
        return

    identity = id(value)
    if identity in seen:
        raise CanonicalJSONError(f"{path} contains a cyclic value")
    seen.add(identity)
    try:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise CanonicalJSONError(f"{path} object keys must be strings")
                _validate_string(key, f"{path} key")
                _validate_ijson(child, path=f"{path}.{key}", seen=seen)
            return
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            for index, child in enumerate(value):
                _validate_ijson(child, path=f"{path}[{index}]", seen=seen)
            return
    finally:
        seen.remove(identity)
    raise CanonicalJSONError(f"{path} has unsupported type {type(value).__name__}")


def _validate_string(value: str, path: str) -> None:
    for character in value:
        codepoint = ord(character)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise CanonicalJSONError(f"{path} contains a lone Unicode surrogate")
        if 0xFDD0 <= codepoint <= 0xFDEF or codepoint & 0xFFFF in {0xFFFE, 0xFFFF}:
            raise CanonicalJSONError(f"{path} contains a Unicode noncharacter")


def _encode(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, Mapping):
        keys = sorted(value, key=_utf16_sort_key)
        return "{" + ",".join(f"{_encode(key)}:{_encode(value[key])}" for key in keys) + "}"
    return "[" + ",".join(_encode(item) for item in value) + "]"


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")

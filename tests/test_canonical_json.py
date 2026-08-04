from __future__ import annotations

import unittest
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from palari_company_os.pcaw_canonical import (
    CanonicalJSONError,
    canonical_json_bytes,
    canonical_sha256,
    strict_json_loads,
)


class CanonicalJSONTests(unittest.TestCase):
    def test_duplicate_keys_are_rejected_at_every_depth(self) -> None:
        for payload in ('{"a":1,"a":2}', '{"outer":{"a":1,"a":2}}'):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(CanonicalJSONError, "duplicate object key"):
                    strict_json_loads(payload)

    def test_floats_nonfinite_values_and_large_integers_are_rejected(self) -> None:
        for payload in ("1.0", "1e2", "NaN", "Infinity", "-Infinity", "9007199254740992"):
            with self.subTest(payload=payload):
                with self.assertRaises(CanonicalJSONError):
                    strict_json_loads(payload)
        with self.assertRaises(CanonicalJSONError):
            canonical_json_bytes(9_007_199_254_740_992)

    def test_invalid_utf8_bom_surrogates_and_noncharacters_are_rejected(self) -> None:
        values: tuple[str | bytes, ...] = (
            b'"\xff"',
            "\ufeff{}",
            '"\\ud800"',
            '"\\ufdd0"',
            '"\\ufffe"',
            '"\\U0010ffff"',
        )
        for value in values:
            with self.subTest(value=repr(value)):
                with self.assertRaises(CanonicalJSONError):
                    strict_json_loads(value)
        with self.assertRaises(CanonicalJSONError):
            canonical_json_bytes({"bad": "\udfff"})

    def test_canonical_output_uses_utf16_property_order_and_minimal_json(self) -> None:
        value = {
            "\ue000": 3,
            "a": "line\nquote\"",
            "\U0001f600": 2,
            "null": None,
            "bool": True,
        }

        encoded = canonical_json_bytes(value).decode("utf-8")

        self.assertEqual(
            encoded,
            '{"a":"line\\nquote\\\"","bool":true,"null":null,"😀":2,"":3}',
        )
        self.assertLess(encoded.index("😀"), encoded.index(""))

    def test_negative_zero_is_canonicalized_and_hash_is_repeatable(self) -> None:
        value = strict_json_loads('{"zero":-0,"items":[3,2,1]}')

        self.assertEqual(canonical_json_bytes(value), b'{"items":[3,2,1],"zero":0}')
        self.assertEqual(canonical_sha256(value), canonical_sha256(value))
        self.assertRegex(canonical_sha256(value), r"^sha256:[0-9a-f]{64}$")

    def test_non_json_types_and_cycles_are_rejected(self) -> None:
        with self.assertRaises(CanonicalJSONError):
            canonical_json_bytes({"set": {"not-json"}})
        cyclic: list[object] = []
        cyclic.append(cyclic)
        with self.assertRaisesRegex(CanonicalJSONError, "cyclic"):
            canonical_json_bytes(cyclic)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
palari="$repo_dir/bin/palari"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

bundle_dir="$tmp_dir/bundle"
cp -R "$repo_dir/spec/pcaw/v1/vectors/valid/accepted" "$bundle_dir"
printf 'PCAW demo: verify an accepted artifact bundle without network access.\n'
"$palari" proof verify "$bundle_dir/statement.json" --json \
  >"$tmp_dir/accepted.json"
python3 - "$tmp_dir/accepted.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not report.get("verified") or not report.get("acceptance_verified"):
    raise SystemExit("accepted artifact bundle did not fully verify")
print("  accepted artifact and governance proof verified.")
PY

printf 'X' >>"$bundle_dir/outputs/result.txt"
printf 'PCAW demo: alter one governed artifact byte and verify rejection.\n'
set +e
"$palari" proof verify "$bundle_dir/statement.json" --json \
  >"$tmp_dir/altered.json"
altered_status=$?
set -e
if [[ "$altered_status" -eq 0 ]]; then
  printf 'PCAW demo failed: altered artifact was accepted.\n' >&2
  exit 1
fi
python3 - "$tmp_dir/altered.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
codes = {item.get("code") for item in report.get("errors", [])}
if "SUBJECT_DIGEST_MISMATCH" not in codes:
    raise SystemExit(f"altered artifact lacked precise rejection: {sorted(codes)}")
print("  rejected precisely: SUBJECT_DIGEST_MISMATCH")
PY

printf 'PCAW proof-carrying work demo passed.\n'

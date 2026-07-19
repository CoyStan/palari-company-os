#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The local bin/palari wrapper exports the source tree for development. An
# isolated wheel smoke must not import from that checkout.
unset PYTHONPATH PYTHONHOME
tmp_dir="$(mktemp -d)"
log_dir="$tmp_dir/logs"
mkdir "$log_dir" "$tmp_dir/wheelhouse"

cleanup() {
  status=$?
  if [[ "$status" -ne 0 ]]; then
    for log in "$log_dir"/*.log; do
      if [[ -f "$log" ]]; then
        printf 'install smoke log: %s\n' "$(basename "$log")" >&2
        tail -n 40 "$log" >&2
      fi
    done
  fi
  rm -rf "$tmp_dir"
  exit "$status"
}
trap cleanup EXIT

python3 -m pip wheel --disable-pip-version-check --no-build-isolation --no-deps \
  "$repo_dir" -w "$tmp_dir/wheelhouse" >"$log_dir/wheel.log" 2>&1
shopt -s nullglob
wheel_paths=("$tmp_dir"/wheelhouse/palari_company_os-*.whl)
shopt -u nullglob
if [[ "${#wheel_paths[@]}" -ne 1 ]]; then
  printf 'Expected exactly one Palari wheel, found %s.\n' "${#wheel_paths[@]}" >&2
  exit 1
fi
wheel_path="${wheel_paths[0]}"

python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check \
  --no-index --no-deps "$wheel_path" >"$log_dir/install.log" 2>&1

"$tmp_dir/venv/bin/python" -c \
  'import palari_company_os; print(palari_company_os.__version__)' \
  >"$log_dir/import.log"
"$tmp_dir/venv/bin/palari" --help >"$log_dir/help.log"

project_dir="$tmp_dir/current-workspace"
mkdir "$project_dir"
git -C "$project_dir" init -q
git -C "$project_dir" config user.name "Palari Install Smoke"
git -C "$project_dir" config user.email "palari-install-smoke@local.invalid"
"$tmp_dir/venv/bin/palari" init "$project_dir" \
  --name "Installed Palari Smoke" --palari "Install Smoke" --json \
  >"$log_dir/init.json"
"$tmp_dir/venv/bin/palari" --workspace "$project_dir" validate --json \
  >"$log_dir/validate.json"
"$tmp_dir/venv/bin/palari" --workspace "$project_dir" queue --json \
  >"$log_dir/queue.json"

cp -R "$repo_dir/spec/pcaw/v1/vectors/valid/accepted" "$tmp_dir/proof-bundle"
mkdir "$tmp_dir/offline-python"
printf '%s\n' \
  'import socket' \
  'def _offline(*args, **kwargs):' \
  '    raise RuntimeError("network disabled during PCAW install smoke")' \
  'socket.socket = _offline' >"$tmp_dir/offline-python/sitecustomize.py"
(
  cd "$tmp_dir"
  PYTHONPATH="$tmp_dir/offline-python" "$tmp_dir/venv/bin/palari" proof verify \
    proof-bundle/statement.json --subject-root proof-bundle --json \
    >"$log_dir/pcaw-offline-verify.json"
)

printf 'Palari Company OS wheel install smoke passed.\n'

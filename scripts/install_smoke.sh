#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check -e "$repo_dir" >/tmp/palari-company-os-install-smoke-pip.log

"$tmp_dir/venv/bin/python" -c 'import palari_company_os; print(palari_company_os.__version__)' >/tmp/palari-company-os-install-smoke-import.log
"$tmp_dir/venv/bin/palari" --help >/tmp/palari-company-os-install-smoke-help.log
"$tmp_dir/venv/bin/palari" --workspace "$repo_dir/examples/acme-company-os" validate --json >/tmp/palari-company-os-install-smoke-validate.json
"$tmp_dir/venv/bin/palari" --workspace "$repo_dir/examples/acme-company-os" queue --json >/tmp/palari-company-os-install-smoke-queue.json

printf 'Palari Company OS install smoke passed.\n'

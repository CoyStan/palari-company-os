#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip >/tmp/palari-company-os-install-smoke-pip.log
"$tmp_dir/venv/bin/python" -m pip wheel --disable-pip-version-check --no-deps "$repo_dir" -w "$tmp_dir/wheelhouse" >/tmp/palari-company-os-install-smoke-wheel.log
wheel_path="$(find "$tmp_dir/wheelhouse" -name 'palari_company_os-*.whl' -print -quit)"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check "$wheel_path" >/tmp/palari-company-os-install-smoke-install.log

"$tmp_dir/venv/bin/python" -c 'import palari_company_os; print(palari_company_os.__version__)' >/tmp/palari-company-os-install-smoke-import.log
"$tmp_dir/venv/bin/palari" --help >/tmp/palari-company-os-install-smoke-help.log
"$tmp_dir/venv/bin/palari" validate --json >/tmp/palari-company-os-install-smoke-default-validate.json
"$tmp_dir/venv/bin/palari" queue --json >/tmp/palari-company-os-install-smoke-default-queue.json
"$tmp_dir/venv/bin/palari" --workspace "$repo_dir/examples/acme-company-os" validate --json >/tmp/palari-company-os-install-smoke-explicit-validate.json
"$tmp_dir/venv/bin/palari" desktop-prototype --out "$tmp_dir/desktop" --json >/tmp/palari-company-os-install-smoke-desktop.json

test -f "$tmp_dir/desktop/index.html"
printf 'Palari Company OS wheel install smoke passed.\n'

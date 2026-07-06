#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
assets_dir="$repo_dir/docs/assets"
tmp_dir="$(mktemp -d "$repo_dir/.palari-demo-assets.XXXXXX")"
trap 'rm -rf "$tmp_dir"' EXIT

mkdir -p "$assets_dir"

echo "Generating dashboard HTML..."
"$repo_dir/bin/palari" --workspace "$repo_dir/examples/acme-company-os" dashboard --out "$tmp_dir/dashboard" >/dev/null

python3 - "$tmp_dir/dashboard/index.html" "$tmp_dir/dashboard/index-light.html" "$tmp_dir/dashboard/index-dark.html" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1])
light = Path(sys.argv[2])
dark = Path(sys.argv[3])
html = source.read_text(encoding="utf-8")
marker = '<script src="app.js"></script>'
if marker not in html:
    raise SystemExit("dashboard HTML did not contain app.js marker")

light.write_text(
    html.replace(
        marker,
        '<script>localStorage.setItem("palari-dashboard-theme", "light");</script>\n'
        '  <script src="app.js"></script>',
    ),
    encoding="utf-8",
)
dark.write_text(
    html.replace(
        marker,
        '<script>localStorage.setItem("palari-dashboard-theme", "dark");</script>\n'
        '  <script src="app.js"></script>',
    ),
    encoding="utf-8",
)
PY

browser_cmd=""
for candidate in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$candidate" >/dev/null 2>&1; then
    browser_cmd="$(command -v "$candidate")"
    break
  fi
done

if [[ -z "$browser_cmd" ]]; then
  cat >&2 <<'EOF'
No Chromium-compatible browser was found.
Dashboard HTML was regenerated, but PNG screenshots were not captured.
Install chromium, chromium-browser, google-chrome, or google-chrome-stable and rerun this script.
EOF
  exit 0
fi

capture() {
  local html_file="$1"
  local output_file="$2"
  local size="$3"
  echo "Capturing $(basename "$output_file") at $size..."
  "$browser_cmd" \
    --headless \
    --disable-gpu \
    --no-sandbox \
    --hide-scrollbars \
    --window-size="$size" \
    --screenshot="$output_file" \
    "file://$html_file" >/dev/null 2>"$tmp_dir/chromium.log" || {
      cat "$tmp_dir/chromium.log" >&2
      exit 1
    }
  if [[ ! -s "$output_file" ]]; then
    cat "$tmp_dir/chromium.log" >&2 || true
    echo "Expected screenshot was not created: $output_file" >&2
    exit 1
  fi
}

capture "$tmp_dir/dashboard/index-light.html" "$assets_dir/palari-dashboard-light-desktop.png" "1440,900"
capture "$tmp_dir/dashboard/index-dark.html" "$assets_dir/palari-dashboard-dark-desktop.png" "1440,900"
capture "$tmp_dir/dashboard/index-light.html" "$assets_dir/palari-dashboard-light-mobile.png" "375,812"
capture "$tmp_dir/dashboard/index-dark.html" "$assets_dir/palari-dashboard-dark-mobile.png" "375,812"

echo "Demo assets written to $assets_dir"

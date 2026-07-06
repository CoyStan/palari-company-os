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

python3 - "$tmp_dir/blocked-terminal.html" <<'PY'
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #eef2f6;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background:
        linear-gradient(135deg, rgba(236, 244, 251, 0.96), rgba(247, 250, 252, 0.98)),
        #f4f7fb;
    }
    main {
      width: min(1180px, calc(100vw - 96px));
      display: grid;
      gap: 22px;
    }
    .caption {
      color: #18212c;
      font-size: 34px;
      font-weight: 780;
      letter-spacing: 0;
      line-height: 1.08;
    }
    .terminal {
      overflow: hidden;
      border: 1px solid rgba(18, 31, 46, 0.18);
      border-radius: 8px;
      background: #101820;
      box-shadow: 0 28px 80px rgba(20, 37, 55, 0.28);
    }
    .chrome {
      display: flex;
      align-items: center;
      gap: 9px;
      height: 48px;
      padding: 0 18px;
      background: #172331;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .dot {
      width: 12px;
      height: 12px;
      border-radius: 999px;
    }
    .red { background: #ff5f56; }
    .yellow { background: #ffbd2e; }
    .green { background: #27c93f; }
    .title {
      margin-left: 10px;
      color: #aab8c6;
      font-size: 15px;
      font-weight: 650;
    }
    pre {
      margin: 0;
      padding: 34px 38px 38px;
      color: #dbe7f1;
      font: 24px/1.45 "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      white-space: pre-wrap;
    }
    .command { color: #8cc7ff; }
    .blocked {
      display: inline-block;
      margin: 18px 0 10px;
      padding: 12px 16px;
      border-radius: 6px;
      color: #fff8f8;
      background: #b42318;
      font-weight: 800;
    }
    .path { color: #ffd166; }
    .allowed { color: #80ed99; }
  </style>
</head>
<body>
  <main>
    <div class="caption">Palari stops an AI file change outside the approved boundary.</div>
    <section class="terminal" aria-label="Palari blocked write terminal output">
      <div class="chrome">
        <span class="dot red"></span>
        <span class="dot yellow"></span>
        <span class="dot green"></span>
        <span class="title">palari demo</span>
      </div>
      <pre><span class="command">$ palari agent check WORK-0003 --as PALARI-SOFIA --changed deploy/production.yml</span>
Agent check: CHECK-WORK-0003-PALARI-SOFIA-EXECUTE-V1
OK: no

<span class="blocked">*** BLOCKED: file change is outside Sofia's write boundary ***</span>
Offending path: <span class="path">deploy/production.yml</span>
Allowed write paths: <span class="allowed">docs/product/company-os.md</span></pre>
    </section>
  </main>
</body>
</html>
""",
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

capture "$tmp_dir/blocked-terminal.html" "$assets_dir/palari-blocked-terminal.png" "1440,760"
capture "$tmp_dir/dashboard/index-light.html" "$assets_dir/palari-dashboard-light-desktop.png" "1440,900"
capture "$tmp_dir/dashboard/index-dark.html" "$assets_dir/palari-dashboard-dark-desktop.png" "1440,900"
capture "$tmp_dir/dashboard/index-light.html" "$assets_dir/palari-dashboard-light-mobile.png" "375,812"
capture "$tmp_dir/dashboard/index-dark.html" "$assets_dir/palari-dashboard-dark-mobile.png" "375,812"

echo "Demo assets written to $assets_dir"

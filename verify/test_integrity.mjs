#!/usr/bin/env node
import { createRequire } from "module";
import { readFileSync } from "fs";
import { spawnSync } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const require = createRequire(import.meta.url);
const __dirname = dirname(fileURLToPath(import.meta.url));
const PcawIntegrity = require("./pcaw_integrity.js");

function fail(msg) {
  console.error("FAIL:", msg);
  process.exit(1);
}

function pythonCanonicalHex(jsonLiteral) {
  const script = `
import hashlib, json, sys
sys.path.insert(0, "src")
from palari_company_os.pcaw_canonical import canonical_json_bytes, strict_json_loads
value = strict_json_loads(sys.stdin.buffer.read())
print(hashlib.sha256(canonical_json_bytes(value)).hexdigest())
`;
  const result = spawnSync("python3", ["-c", script], {
    input: Buffer.from(jsonLiteral, "utf8"),
    cwd: join(__dirname, ".."),
  });
  if (result.status !== 0) {
    fail(`python canonical failed: ${result.stderr}`);
  }
  return Buffer.from(result.stdout).toString("utf8").trim();
}

async function main() {
  const samples = [
    "null",
    "true",
    "false",
    "0",
    "1",
    "-1",
    '""',
    '"a"',
    '"日本語"',
    "[]",
    "{}",
    '{"b":1,"a":2}',
    '{"更":1,"書":2}',
  ];
  for (const sample of samples) {
    const value = PcawIntegrity.parseStrictJson(sample);
    const jsHex = await PcawIntegrity.canonicalSha256Hex(value);
    const pyHex = pythonCanonicalHex(sample);
    if (jsHex !== pyHex) {
      fail(`canonical mismatch for ${sample}: js=${jsHex} py=${pyHex}`);
    }
  }

  const statementPath = join(__dirname, "fixtures/accepted/statement.json");
  const text = readFileSync(statementPath, "utf8");
  const report = await PcawIntegrity.verifyStatementIntegrity(text, {});
  if (!report.ok) fail(`accepted fixture failed: ${report.message}`);
  const work = report.checks.find((c) => c.id === "work_state_digest");
  if (!work || !work.ok) fail("work-state digest check failed on accepted fixture");

  const tampered = JSON.parse(text);
  tampered.predicate.governance_case.contract.title += " TAMPER";
  const bad = await PcawIntegrity.verifyStatementIntegrity(JSON.stringify(tampered), {});
  if (bad.ok) fail("tampered fixture unexpectedly passed");
  const badWork = bad.checks.find((c) => c.id === "work_state_digest");
  if (!badWork || badWork.ok) fail("tamper did not break work-state digest");

  const artifact = readFileSync(
    join(__dirname, "fixtures/accepted/outputs/result.txt"),
  );
  const withArt = await PcawIntegrity.verifyStatementIntegrity(text, {
    "outputs/result.txt": artifact,
    "result.txt": artifact,
  });
  if (!withArt.ok) fail(`artifact check failed: ${withArt.message}`);

  console.log("OK: verify/pcaw_integrity.js parity + fixture checks");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

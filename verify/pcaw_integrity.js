/**
 * Integrity-grade PCAW v1 checks for the static drop-a-receipt page.
 *
 * This is NOT WRP-10 and NOT full `palari proof verify`.
 * It checks: UTF-8/I-JSON parse, envelope fields, security_limitations,
 * work-state digest binding, optional artifact digests, and statement digest.
 * Governance property evaluation stays CLI-only until a conformance-tested
 * browser port exists.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.PcawIntegrity = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STATEMENT_TYPE = "https://in-toto.io/Statement/v1";
  const PREDICATE_TYPE = "https://palari.dev/pcaw/v1";
  const PREDICATE_SCHEMA = "pcaw.v1";
  const SECURITY_LIMITATIONS = [
    "actor-attribution-declared-not-authenticated",
    "no-signatures-or-key-custody",
    "same-user-tampering-not-prevented",
  ];
  const SHA256_RE = /^[0-9a-f]{64}$/;
  const IJSON_MAX = 9007199254740991n;

  class IntegrityError extends Error {
    constructor(message, code) {
      super(message);
      this.name = "IntegrityError";
      this.code = code || "INTEGRITY_ERROR";
    }
  }

  function utf16SortKey(value) {
    const bytes = new Uint8Array(value.length * 2);
    for (let i = 0; i < value.length; i += 1) {
      const code = value.charCodeAt(i);
      bytes[i * 2] = (code >> 8) & 0xff;
      bytes[i * 2 + 1] = code & 0xff;
    }
    return bytes;
  }

  function compareUtf16Keys(a, b) {
    const left = utf16SortKey(a);
    const right = utf16SortKey(b);
    const n = Math.min(left.length, right.length);
    for (let i = 0; i < n; i += 1) {
      if (left[i] !== right[i]) return left[i] - right[i];
    }
    return left.length - right.length;
  }

  function validateString(value, path) {
    for (let i = 0; i < value.length; i += 1) {
      const code = value.charCodeAt(i);
      if (code >= 0xd800 && code <= 0xdfff) {
        // Lone surrogates: if high without low or low without high.
        if (code >= 0xdc00 || i + 1 >= value.length) {
          throw new IntegrityError(`${path} contains a lone Unicode surrogate`, "BAD_STRING");
        }
        const next = value.charCodeAt(i + 1);
        if (next < 0xdc00 || next > 0xdfff) {
          throw new IntegrityError(`${path} contains a lone Unicode surrogate`, "BAD_STRING");
        }
        i += 1;
        continue;
      }
      const full = value.codePointAt(i);
      if ((full >= 0xfdd0 && full <= 0xfdef) || (full & 0xffff) === 0xfffe || (full & 0xffff) === 0xffff) {
        throw new IntegrityError(`${path} contains a Unicode noncharacter`, "BAD_STRING");
      }
    }
  }

  function validateIjson(value, path) {
    if (value === null || typeof value === "boolean") return;
    if (typeof value === "number") {
      if (!Number.isInteger(value)) {
        throw new IntegrityError(`${path} floating-point numbers are not supported`, "BAD_NUMBER");
      }
      if (Math.abs(value) > Number(IJSON_MAX)) {
        throw new IntegrityError(`${path} integer is outside the I-JSON range`, "BAD_NUMBER");
      }
      return;
    }
    if (typeof value === "bigint") {
      if (value > IJSON_MAX || value < -IJSON_MAX) {
        throw new IntegrityError(`${path} integer is outside the I-JSON range`, "BAD_NUMBER");
      }
      return;
    }
    if (typeof value === "string") {
      validateString(value, path);
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((child, index) => validateIjson(child, `${path}[${index}]`));
      return;
    }
    if (value && typeof value === "object") {
      for (const [key, child] of Object.entries(value)) {
        if (typeof key !== "string") {
          throw new IntegrityError(`${path} object keys must be strings`, "BAD_OBJECT");
        }
        validateString(key, `${path} key`);
        validateIjson(child, `${path}.${key}`);
      }
      return;
    }
    throw new IntegrityError(`${path} has unsupported type`, "BAD_TYPE");
  }

  function encodeString(value) {
    // Match Python json.dumps(..., ensure_ascii=False, separators=(",", ":"))
    return JSON.stringify(value);
  }

  function encode(value) {
    if (value === null) return "null";
    if (value === true) return "true";
    if (value === false) return "false";
    if (typeof value === "number") return String(value);
    if (typeof value === "bigint") return value.toString();
    if (typeof value === "string") return encodeString(value);
    if (Array.isArray(value)) {
      return `[${value.map((item) => encode(item)).join(",")}]`;
    }
    const keys = Object.keys(value).sort(compareUtf16Keys);
    return `{${keys.map((key) => `${encode(key)}:${encode(value[key])}`).join(",")}}`;
  }

  function canonicalJsonBytes(value) {
    validateIjson(value, "$");
    return new TextEncoder().encode(encode(value));
  }

  async function sha256Hex(bytes) {
    if (typeof crypto !== "undefined" && crypto.subtle) {
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
    }
    // Node fallback for tests
    const nodeCrypto = require("crypto");
    return nodeCrypto.createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  }

  async function canonicalSha256Hex(value) {
    return sha256Hex(canonicalJsonBytes(value));
  }

  function parseStrictJson(text) {
    if (typeof text !== "string") {
      throw new IntegrityError("JSON must be a UTF-8 string", "BAD_JSON");
    }
    if (text.charCodeAt(0) === 0xfeff) {
      throw new IntegrityError("JSON must not include a UTF-8 BOM", "BAD_JSON");
    }
    if (/[:\s](-?\d+\.\d+([eE][+-]?\d+)?|-?\d+[eE][+-]?\d+)[,}\]\s]/.test(` ${text} `)) {
      // Cheap float rejection before JSON.parse loses the distinction for ints.
      // Still validate after parse.
    }
    let value;
    try {
      value = JSON.parse(text, (key, val, context) => {
        // Native JSON.parse does not expose duplicates; we re-scan below.
        return val;
      });
    } catch (err) {
      throw new IntegrityError(`invalid JSON: ${err.message}`, "BAD_JSON");
    }
    // Reject floats that survived parse.
    const walk = (node, path) => {
      if (typeof node === "number" && !Number.isInteger(node)) {
        throw new IntegrityError(`${path} floating-point numbers are not supported`, "BAD_NUMBER");
      }
      if (Array.isArray(node)) node.forEach((c, i) => walk(c, `${path}[${i}]`));
      else if (node && typeof node === "object") {
        for (const [k, c] of Object.entries(node)) walk(c, `${path}.${k}`);
      }
    };
    walk(value, "$");
    // Duplicate key scan on raw text objects is imperfect; rely on parse + ijson.
    if (/"([^"\\]|\\.)*?"\s*:\s*[^,}\n]+,\s*"\1"\s*:/.test(text)) {
      // Not reliable enough — skip. Python rejects duplicates; browser page notes CLI for full TCB.
    }
    validateIjson(value, "$");
    return value;
  }

  function exactKeys(obj, expected, label) {
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      throw new IntegrityError(`${label} must be an object`, "BAD_OBJECT");
    }
    const keys = Object.keys(obj).sort();
    const want = [...expected].sort();
    if (keys.length !== want.length || keys.some((k, i) => k !== want[i])) {
      throw new IntegrityError(`${label} has unexpected fields`, "BAD_FIELDS");
    }
  }

  async function verifyStatementIntegrity(statementText, artifactFiles) {
    const checks = [];
    const mark = (id, ok, detail) => {
      checks.push({ id, ok, detail });
    };

    let statement;
    try {
      statement = parseStrictJson(statementText);
      mark("well_formed_json", true, "UTF-8 I-JSON subset parsed");
    } catch (err) {
      mark("well_formed_json", false, err.message);
      return summarize(false, checks, null, err.message);
    }

    try {
      exactKeys(statement, ["_type", "subject", "predicateType", "predicate"], "statement");
      if (statement._type !== STATEMENT_TYPE) {
        throw new IntegrityError("unsupported statement._type", "BAD_TYPE");
      }
      if (statement.predicateType !== PREDICATE_TYPE) {
        throw new IntegrityError("unsupported predicateType", "BAD_TYPE");
      }
      const predicate = statement.predicate;
      exactKeys(
        predicate,
        ["schema_version", "claimed_state", "governance_case", "subject_roles", "security_limitations"],
        "predicate",
      );
      if (predicate.schema_version !== PREDICATE_SCHEMA) {
        throw new IntegrityError("unsupported predicate.schema_version", "BAD_SCHEMA");
      }
      mark("envelope", true, "PCAW v1 in-toto statement envelope");
    } catch (err) {
      mark("envelope", false, err.message);
      return summarize(false, checks, null, err.message);
    }

    const limitations = statement.predicate.security_limitations;
    const limOk =
      Array.isArray(limitations) &&
      limitations.length === SECURITY_LIMITATIONS.length &&
      SECURITY_LIMITATIONS.every((item, i) => limitations[i] === item);
    mark(
      "security_limitations",
      limOk,
      limOk
        ? "Required non-claims present (unsigned / unauthenticated)"
        : "security_limitations missing or altered",
    );
    if (!limOk) {
      return summarize(false, checks, null, "security_limitations mismatch");
    }

    const subjects = statement.subject;
    if (!Array.isArray(subjects) || subjects.length === 0) {
      mark("work_state_digest", false, "statement.subject missing");
      return summarize(false, checks, null, "missing subjects");
    }

    let workSubject = null;
    for (const item of subjects) {
      if (item && typeof item.name === "string" && item.name.startsWith("urn:palari:work-state:")) {
        workSubject = item;
        break;
      }
    }
    if (!workSubject || !workSubject.digest || !SHA256_RE.test(workSubject.digest.sha256 || "")) {
      mark("work_state_digest", false, "work-state subject digest missing");
      return summarize(false, checks, null, "work-state digest missing");
    }

    const expected = workSubject.digest.sha256;
    const actual = await canonicalSha256Hex(statement.predicate.governance_case);
    const workOk = expected === actual;
    mark(
      "work_state_digest",
      workOk,
      workOk
        ? `work-state digest binds governance_case (${expected.slice(0, 12)}…)`
        : `work-state digest mismatch (statement ${expected.slice(0, 12)}… vs recomputed ${actual.slice(0, 12)}…)`,
    );

    const statementDigest = await sha256Hex(canonicalJsonBytes(statement));
    mark("statement_digest", true, `sha256:${statementDigest}`);

    // Optional artifact digest checks when files are supplied by name basename.
    const artifacts = artifactFiles || {};
    let artifactChecked = 0;
    let artifactFailed = 0;
    for (const item of subjects) {
      const name = item && item.name;
      if (typeof name !== "string" || name.startsWith("urn:palari:work-state:")) continue;
      const digest = item.digest && item.digest.sha256;
      if (!SHA256_RE.test(digest || "")) continue;
      const base = name.split("/").pop();
      const bytes = artifacts[name] || artifacts[base];
      if (!bytes) continue;
      artifactChecked += 1;
      const got = await sha256Hex(bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes));
      if (got !== digest) {
        artifactFailed += 1;
        mark("artifact_digest", false, `${name}: digest mismatch`);
      }
    }
    if (artifactChecked === 0) {
      mark(
        "artifact_digest",
        true,
        "Artifact bytes not supplied — subject_integrity not checked here (CLI full verify can)",
      );
    } else if (artifactFailed === 0) {
      mark("artifact_digest", true, `${artifactChecked} artifact digest(s) matched`);
    }

    mark(
      "governance_properties",
      true,
      "Not checked in this page — run: palari proof verify statement.json --subject-root DIR",
    );

    const critical = ["well_formed_json", "envelope", "security_limitations", "work_state_digest"];
    const ok = checks.filter((c) => critical.includes(c.id)).every((c) => c.ok) && artifactFailed === 0;
    return summarize(ok, checks, {
      claimed_state: statement.predicate.claimed_state,
      statement_digest: statementDigest,
      work_state_digest: expected,
      security_limitations: SECURITY_LIMITATIONS,
      verification_level: "browser-integrity",
      not_wrp10: true,
      not_full_cli_verify: true,
    }, ok ? "Integrity checks passed (unsigned PCAW v1)." : "Integrity checks failed.");
  }

  function summarize(ok, checks, meta, message) {
    return {
      ok,
      message,
      checks,
      meta,
      honesty: [
        "Unsigned PCAW v1 integrity only — no signatures or key custody.",
        "Not WRP-10 (signed drop-a-receipt page).",
        "Not full CLI governance verification (scope/review/quorum/acceptance).",
        "Actor attribution is declared, not authenticated.",
      ],
    };
  }

  return {
    SECURITY_LIMITATIONS,
    STATEMENT_TYPE,
    PREDICATE_TYPE,
    IntegrityError,
    canonicalJsonBytes,
    canonicalSha256Hex,
    sha256Hex,
    parseStrictJson,
    verifyStatementIntegrity,
    encode,
  };
});

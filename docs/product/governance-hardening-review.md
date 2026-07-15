# Governance Hardening Independent Review History

This report records the independent review loop for `WORK-REPO-0023` on
`codex/model-independent-governance-hardening`. The implementation baseline is
`2eea39e9d3d70baa69d987dba50decbcb63bc51e`. Reviewers inspected committed
heads, not unexplained dirty worktrees. A rejection remained blocking until a
later exact-head review confirmed the repair.

No reviewer recorded founder approval, human acceptance, merge, push,
deployment, provider action, or external write.

## Review Ledger

| Review | Exact head | Verdict | Blocking evidence and disposition |
| --- | --- | --- | --- |
| 1 | `d3cc68566dc164aedd5c665bc5734c1a1d03c82c` | REJECT | Legacy unbound review authority, claim-baseline laundering, tip-only attribution, stale approval selection, incomplete proof hashing, and terminal acceptance gaps. Repaired in subsequent binding, runtime, validation, and read-model commits. |
| 2 | `21670a447ab039d5000a19b2df7350f005a9170a` | REJECT | Raw-claim bypass and split-workspace migration placement failures. Repaired with persisted claim integrity and split-safe migration. |
| 3 | `bb8518cf02b40e3a6def9707bb98b5672f8b0614` | REJECT | Coordinated packet/baseline tampering, unsupported human-command execution, and nonterminal accepted-proof tamper. Repaired with current packet recomputation, Git witness enforcement, hook authority denial, and active acceptance verification. |
| 4 | `dc1eba0c05b306eddccd8121a970db060c1b3340` | REJECT | Dynamic-shell human acceptance, active-claim self-scope mutation, and Git `-C` witness rewriting. Repaired in hook classification and active-claim transition checks. |
| 5 | `d27a1dca39c6b8072b5ba8573379cc85819f31be` | REJECT | Later shell segments could be masked and Git config could launch `diff.external`. Repaired with full segment inspection and helper-option denial. |
| 6 | `6288ca5d1e162f24a5631815fc14d450e1efa949` | REJECT | Option-encoded copy/write destinations and Git helper execution through `grep -O`/`cat-file --filters`. Repaired with option-aware target parsing and helper denial. |
| 7 | `d02421dcc235504a5b6c21d6a82ffee8369a9b21` | REJECT | Compact/newline separators and directory destination basename semantics escaped classification. Repaired in shell splitting and destination resolution. |
| 8 | `ac30b3b2f0be88cac2a022db6544c2654e726180` | REJECT | Root argparse abbreviation accepted unintended `--work`. Repaired by disabling long-option abbreviation at root and nested parsers. |
| 9 | `24aa828fcf00a468fbcecc5ad99f49013ff3df8e` | REJECT | Globs, recursive copies, path-qualified command spoofing, and uncovered human/external Palari commands. Repaired with explicit command identity, tree-write review, and fail-closed Palari allowlisting. |
| 10 | `d444fc5e02eb876fabe296e19470017b803fba05` | REJECT | Bash `|&`, assignment tilde, GNU/Git option abbreviations, backup outputs, and Git pathspec-file imports. Repaired with parser-level negative coverage. |
| 11 | `72c7d3ae7a776ba5dc2c3f142aec6645a0deb6b8` | REJECT | Concrete pre-termination findings covered Git pathspec magic/exclusions and lexical ISO timestamp ordering. Repaired with conservative pathspec review and UTC-normalized record ordering. |
| 12 | `90efb810fb972edc6a5f0acb86c1f390cc4a0f6f` | REJECT | Equivalent-instant/malformed trust records and acceptance selection that ignored `accepted_at`. Repaired with ambiguity validation and latest-revocation enforcement. |
| 13 | `33dda5921936208bbd6f35ac6851b5e522e7383d` | REJECT | Extreme timezone offsets leaked `OverflowError` during UTC normalization. Repaired with bounded normalization and controlled validation errors. |
| 14 | `3e3ea6bde7f645d34055aeaf10e6e56335cdcae0` | REJECT | Mutable array position could forge an undated “legacy” minimum record. Repaired by requiring every record to be dated whenever latest-record selection is necessary. |
| 15 | `4a58b2cbd1ada8b12c8c3cc9022ea2ac3a165903` | **ACCEPT** | All sixteen adversarial ordering cases failed closed; accepted-at selection and legitimate lifecycle history passed. No reproducible release blocker remained. |

## Accepted Candidate Evidence

Review 15 confirmed the exact head before and after review and found the tracked
tree clean. The pre-existing untracked `docs/company/` content was excluded,
untouched, and uninspected.

- Focused validation, read-model, history, and governance suite: 138 tests
  passed.
- Independent complete verification: 555 tests passed in 71.534 seconds;
  78.28 seconds wall; style passed.
- Independent isolated wheel installation smoke: passed.
- Local authoritative verification for the same head: 555 tests passed in
  74.578 seconds; 81.84 seconds wall; style passed.
- Local isolated wheel installation smoke: passed in 12.41 seconds.
- Documentation validation: 12 checks passed with no warnings or failures.

The accepted implementation head is the mechanical candidate. Later commits
may add only this review ledger, dogfood proof, the completion contract, and the
founder packet; any such final metadata head still requires its own fresh exact
review before handoff.

## Residual Boundary

Local hashes, Git refs/reflogs, and supported hooks detect the covered mismatch
and tamper paths, but they are not cryptographic proof against an unrestricted
process running as the same OS user. Human identity needs a future protected
harness or credential boundary before hostile same-principal execution can be
treated as authenticated. This limitation is documented in the security model
and was accepted as a residual risk, not used to weaken any current gate.

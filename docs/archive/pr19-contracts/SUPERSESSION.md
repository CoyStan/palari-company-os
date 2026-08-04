# PR #19 supersession inventory

PR: https://github.com/CoyStan/palari-company-os/pull/19  
Branch: `codex/invisible-adoption-fast-journal`  
Decision: **close without mega-rebase**; retain only unique contract docs here.

## Themes → where they landed on `main`

| Theme | Status | Superseding location / proof |
| --- | --- | --- |
| Compact Governance Journal v2 | shipped | `governance_journal.py` v2 writer; schema-and-validation journal section |
| Golden-path init → start → advance | shipped | onramp + operator journeys; later solo-maintainer guarantee work |
| Provider-neutral agent adoption (`init --host`) | shipped | `agent_adoption.py`; Claude/Codex profiles (Cursor added in follow-on) |
| Invisible / ordinary product surface | shipped | public-surface + current-product + command-reference ordinary path |
| Nested adoption / rollback / git gate locality | shipped | adoption tests and install rollback paths on main |
| Retirement / terminal storage boundaries | shipped | governance kernel / validation on main |
| Dogfood workspace evidence churn in PR #19 | superseded | live root / dogfood workspaces advanced independently since |

## Unique files retained from PR #19

Only these product paths were **not** already on `main` as living docs:

- `compact-journal-v2-contract.md` → archived here
- `golden-path-repair-contract.md` → archived here
- `invisible-adoption-foundation-contract.md` → archived here
- `invisible-product-surface-contract.md` → archived here
- `universal-agent-adoption-contract.md` → archived here

All other PR #19 paths (adoption module, journal implementation, CLI/onramp,
tests, README/command-reference edits) are already present on `main` in evolved
form. Replaying the branch would fight years of subsequent hardening.

## Explicit non-actions

- No rebase of the PR #19 commit bundle onto current `main`
- No revival of removed host aliases (Devin/GLM/generic) from early adoption drafts
- No copy of PR #19 dogfood `workspace.json` churn into current live state

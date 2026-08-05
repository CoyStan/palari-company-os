# Distribution workstream

Status: **experimental operating notes**, not a product surface or backlog
promise. This repository’s governance loop currently measures internal quality.
Distribution needs the same discipline pointed outward.

## Premise

Nobody adopts a brake. The honest pitch Palari has earned is inverted: let
agents work while you sleep; wake up to an approval inbox, not a mess.
Boundaries and receipts are why unattended autonomy is safe enough to try.

## Measured channels

Track weekly (manual is fine until automation exists):

| Signal | Why it matters |
| --- | --- |
| External receipt verifications | Strangers using the drop-a-receipt page or CLI verify |
| `uvx` / PyPI installs | Zero-install demo reach |
| Inbound GitHub issues/discussions from non-maintainers | Real friction |
| Landscape/HN referral traffic | Discovery without hype |
| One design-partner conversation | Case-study path |

Falsifier: if three months of deliberate channel work moves none of these, the
wedge packaging is wrong — pivot the wedge, do not add features “for adoption.”

## Sequence

1. Integrity-grade verifier + README badge (`verify/`) — shipped as experiment.
2. PyPI trusted publisher + first `v*` tag → `uvx --from palari-company-os palari demo --no-pause`.
3. Publish landscape content from [agent-company-landscape.md](agent-company-landscape.md)
   (re-fetch star/product claims first). Draft:
   [agent-company-landscape-hn-draft.md](agent-company-landscape-hn-draft.md).
4. Listings: Claude Code plugin/skills directories, MCP registries, GitHub topics.
5. Interop/outreach to adjacent runtimes (authority + receipts layer).
6. One design partner (clinic, small firm, insurer/GC) — slow channel, start early.

## What not to do

- Do not add features for adoption when the survey shows no feature gap.
- Do not hype beyond shipped guarantees (unsigned PCAW ≠ WRP-10).
- Do not run every channel at once.

## Related

- [Agent-company landscape](agent-company-landscape.md)
- [Palari Blueprint](palari-blueprint.md) (WRP-10 remains signed/future)
- [Release and operations](release-and-operations.md)

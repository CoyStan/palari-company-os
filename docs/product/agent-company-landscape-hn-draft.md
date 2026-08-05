# Draft: HN / landscape post

Status: **draft content**, not published. Source survey:
[agent-company-landscape.md](agent-company-landscape.md). Re-fetch star counts
and product claims before posting. Keep Palari as a footnote, not a pitch.

---

**Title options**

1. I audited ~60 “AI company” frameworks for what they actually enforce
2. Stars measure narrative: what agent-company tools enforce vs advertise
3. The five properties almost no multi-agent “company” product has

**Opening (draft)**

I spent three research passes in mid-July 2026 looking at systems that claim to
build companies, orgs, or teams of AI agents — open-source frameworks,
commercial “AI workforce” products, enterprise platform features, and the 2026
research trail. I scored each against five properties that, combined, would
make a *governed* company rather than an orchestration demo:

1. Durable role identity (not a prompt persona)
2. Authority separated from capability (not the model’s prompt)
3. Enforced boundaries (hooks/sandbox/policy — not advisory)
4. Verifiable evidence (offline / operator-independent — not only logs)
5. Human decision gates (on by default — not optional theater)

Across ~60 verified systems, **no project combined all five**. The field splits
into company-semantics products with soft governance, hard-enforcement
middleware with no organizational model, and orchestration substrates with
neither authority nor evidence.

**Body beats (keep receipts)**

- paperclip (~74k): category narrative; companies spec says registries are not
  authorities; local adapters can run unsandboxed.
- Fast growers shipping `bypassPermissions` / `--dangerously-skip-permissions`
  as the path of least resistance.
- ruflo / harness-style star-to-substance mismatches (cite primary issues; do
  not escalate tone).
- Microsoft Agent Governance Toolkit: real authority/policy middleware; narrow
  offline receipt path for governed MCP calls — still not a company OS.
- Hyperscalers bundling agent identity + policy + audit dashboards; four cells
  they are unlikely to own: operator-independent evidence, local-first,
  cross-org proof portability, cross-vendor role identity.
- Research: MAST organizational failures; TheAgentCompany ceiling; identity
  rails (A2A, Entra Agent ID) industrializing without the governance loop.
- Two mechanisms worth stealing: verdict-consistency validation; gate-strength
  self-audit.

**Closing (draft)**

Better *products* than a local governance CLI exist by a wide margin. A better
*integrated concept* — durable roles + separated authority + enforced
boundaries + offline-verifiable receipts + mandatory human gates — was empty
when surveyed. If you maintain one of these systems and my read is stale,
correct me with a primary source; the survey is dated July 2026.

Optional single footnote: I maintain Palari Company OS, which attempts that
combination locally and dogfoods evidence on its own PRs. Unsigned receipt
integrity page: `https://coystan.github.io/palari-company-os/`. Full verify
remains CLI. Not legal advice; not a compliance product claim.

**Do not say**

- “Only tool that…” without the five-property qualifier and survey date
- That browser verify equals signed WRP-10
- EU AI Act compliance guarantees

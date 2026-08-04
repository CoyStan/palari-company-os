# Claude Instructions

Use the same task rules as every Palari-compatible coding agent:

```bash
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
```

Treat the returned task brief (`packet` in JSON) as the assignment boundary. If
the task is blocked, do not improvise; report the blocker or run only the listed
safe commands.

The shared rules live in:

- `AGENTS.md`
- `docs/agent/repo-map.md`
- `docs/agent/contracts-and-invariants.md`
- `docs/product/agent-contract.md`

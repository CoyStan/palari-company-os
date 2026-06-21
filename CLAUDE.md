# Claude Instructions

Use the same operating contract as every Palari-compatible coding agent:

```bash
palari agent brief WORK-ID --as PALARI-ID --mode execute --json
```

Treat the returned packet as the assignment boundary. If the packet is blocked,
do not improvise; report the blocker or run only the listed safe commands.

The shared contract lives in:

- `AGENTS.md`
- `docs/product/agent-contract.md`

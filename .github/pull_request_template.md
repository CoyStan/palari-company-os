## Summary

<!-- What changed and why. -->

## Agent dogfood

Agent PRs should follow:

1. `./scripts/dogfood_agent.sh PALARI-ID` (or `palari agent start --next …`)
2. Edit only `allowed_paths.write`
3. Commit the bounded change
4. `palari agent advance WORK-ID --as PALARI-ID --json`
5. Hand off for independent review / human approval

CI's **Agent dogfood gate** requires agent-authored commits (authors such as
`Cursor Agent` / `Claude`, or PRs labeled `agent` / `cursor`) to be covered by
a recorded advance/evidence range in `workspace.json` or
`.palari/dogfood/proof.json`.

Humans may land emergency fixes without a claim. On an `agent`/`cursor`-labeled
PR, human commits may use a commit trailer:

```text
skip-dogfood: short reason
```

That trailer is rejected for known agent authors.

## Recovery

- Stuck claim: `palari agent release WORK-ID --as PALARI-ID --json`
- No active claim ⇒ git pre-commit allows human commits

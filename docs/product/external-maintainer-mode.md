# External Maintainer Mode

External Maintainer Mode is a parked, read-only repository status view. It is
not part of the current product, a required approval check, or a pre-1.0
compatibility promise.

It exists so maintainers can inspect small code fixes without adding heavy
process to every change.

Run:

```bash
./bin/palari maintainer status
```

It reports:

- repository path;
- current branch and commit;
- upstream branch and divergence;
- changed files;
- focused checks run, when known; and
- pull-request readiness.

This view is not a loophole for risky work. Production, policy, broker,
security, deployment, and permission changes still need stronger check results
and the required human approval.

Focused checks are known only when this local ignored log exists:

```text
.palari-company-os/verification.json
```

Example:

```json
{
  "commands": [
    {
      "command": "python3 -m unittest discover -s tests",
      "status": "passed"
    }
  ]
}
```

If the log is absent, the status is `unknown`. The command never invents check
results.

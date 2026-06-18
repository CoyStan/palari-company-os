# External Maintainer Mode

External Maintainer Mode is a deliberate lightweight path for ordinary repo
maintenance.

It exists because Palari Company OS itself should be maintainable without
requiring the old ticket ceremony for every small code fix.

The first command is:

```bash
./bin/palari maintainer status
```

It reports:

- repo path
- current branch
- current head
- upstream
- divergence
- dirty files
- focused tests run, if known
- PR readiness

This mode is not a loophole for risky work. Production, policy, broker,
security, deploy, and authority changes still need stronger evidence and human
decision paths.

Focused tests are known only when a local ignored verification log exists:

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

The absence of this log is reported as `unknown`; the command does not invent
test evidence.

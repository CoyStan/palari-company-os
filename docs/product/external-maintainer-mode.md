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

This mode is not a loophole for risky work. Production, policy, broker,
security, deploy, and authority changes still need stronger evidence and human
decision paths.


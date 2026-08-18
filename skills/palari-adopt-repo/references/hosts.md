# Host profiles

Choose the profile for the agent product that will work in the repository. Host
setup changes local enforcement, not task or approval authority.

| Host | Adoption behavior | Remaining boundary |
| --- | --- | --- |
| `claude` | Installs portable repository rules, the task-lock-bound Git check, and tested strict session hooks. | Existing guidance and unrelated changes remain untouched. |
| `codex` | Installs portable repository rules, the task-lock-bound Git check, and tested strict session hooks. | A human must review and trust the repository hooks through `/hooks`. |
| `cursor` | Installs the portable contract, an advisory Cursor project rule, and the Git commit gate. | Skip the Git gate with `--no-git-hook`. Session rules stay advisory; Cursor cannot deny edits before they happen. |

Use only these named profiles. If the user's agent host is different, stop rather
than pretending another profile is equivalent. Provider-neutral session rules
may still be consumed separately, but that is outside this adoption skill.

No host profile grants permission to review, approve, merge, push, deploy, call
a provider, or perform an external write.

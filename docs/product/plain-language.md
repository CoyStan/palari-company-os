# Plain Language

Palari uses ordinary words wherever a person is choosing, running, reviewing,
or approving work. Internal storage and protocol names remain exact so old
records and portable verification continue to work.

## The rule

Write for people first. New public names use one short, common word when
possible. Do not use a field of study, a theory word, or an acronym as a label
when an everyday word says the same thing.

Put every new product part under one of five plain headings: **Goals**,
**Team**, **Work**, **Checks**, or **Limits**. A part may end there or split
into three to five smaller parts. At each split, nothing overlaps and nothing
is left out.

The work path is:

```text
goal
-> task and limits
-> run
-> record and checks
-> independent review when needed
-> human approval when needed
-> result
```

The normal visible statuses are:

```text
Ready
In progress
Blocked
Needs review
Needs approval
Complete
```

When a more precise stored status matters, show it after the plain label or in
structured JSON. Do not make an operator decode an internal status to discover
the next safe action.

## Preferred words

| Say this | Instead of this | Meaning |
| --- | --- | --- |
| agent | Palari, when referring to an AI worker | The AI partner doing the task. |
| local system | control plane | Palari as installed in one repository or workspace. |
| rules and checks | governance kernel | The code that decides what is allowed and which checks are current. |
| work process | governance lifecycle | The steps from a task to a result. |
| task | work item | One bounded assignment. |
| project | workbench | The area that groups related tasks and files. |
| run | attempt | One try at completing a task. |
| allowed files, sources, and actions | scope | The task's limits. |
| task rules | work contract | The objective, limits, and completion requirements. |
| task brief | packet | The instructions compiled for an agent. |
| assignment or task lock | claim | The local record showing who currently owns execution. |
| run record | receipt | What the run read, changed, skipped, or planned. |
| check results | evidence run | The recorded verification results for the exact run and outputs. |
| review result | review verdict | The independent reviewer's conclusion. |
| approval or rejection | human decision | A person's authority-bearing choice. |
| approval record | acceptance record | The durable record of final approval. |
| result | outcome | What happened after the task closed. |
| status | lifecycle state | Where the task currently stands. |
| required check | gate | A condition that must pass before work continues. |
| permission or approval | authority | What an actor may do or decide. |
| required approvals | quorum | How many qualified people must approve. |
| status view | projection or read model | A human-facing summary derived from stored records. |
| finish automatically | convergence | Mechanical completion after all required proof and approval exist. |
| tamper-evident history | governance journal | The append-only record used to detect changed history. |
| restore point | checkpoint | A recorded local state that can be restored when safe. |
| output or file | artifact | A produced file outside protocol documentation. |
| verification report | proof | A portable or local report that checks the required properties. |
| tied to this exact version | exact-artifact binding | A review or approval that applies only to named bytes and state. |

Use the plain term in headings, help, ordinary text output, explanations, and
next actions. Introduce a machine term once in parentheses when a reader needs
to edit JSON, inspect a path, or use an exact command.

## Machine names stay exact

Do not rename existing commands, options, JSON keys, status values, diagnostic
codes, identifiers, filenames, or Python types as part of a wording change.
For example, documentation may say "task," while a schema example still uses
`work_items`; it may say "run record," while PCAW v1 still uses
`receipt_binding`.

These names are stored, hashed, versioned, or consumed by other tools:

- workspace collections such as `work_items`, `attempts`, `receipts`,
  `evidence_runs`, `review_verdicts`, and `human_decisions`;
- detailed status values such as `ready-for-ai-work`, `needs-review`, and
  `accept-ready`;
- `.palari/packets/`, `.palari/claims/`, and
  `.palari/governance-journal.v2.jsonl`;
- `WORK-`, `ATTEMPT-`, `RECEIPT-`, `EVIDENCE-`, and related identifiers; and
- PCAW v1 fields, verified properties, diagnostic codes, and canonical bytes.

Changing those names requires an explicit versioned migration, not a prose
edit.

Some deterministic JSON records bind their explanatory prose into a digest.
Task briefs (`packet`) and portable session rules (`session-contract`) are the
important examples. Their existing prose remains canonical in v1 so a wording
update cannot silently invalidate saved assignments or verification. The
ordinary text renderer supplies the plain wording; a future JSON vocabulary
change requires a versioned format.

## Technical words

Standards documentation may use `artifact`, `digest`, `manifest`,
`attestation`, `provenance`, `subject`, `predicate`, and `canonicalization`
when those are the exact protocol concepts. Security documentation may use
`authorization` and `fail closed` when precision matters. Explain the practical
meaning before relying on the specialist term.

`AI governance` remains a useful category for discovery. It is not the name of
every Palari object or operation.

## Product description

Use this short description when introducing Palari:

> Palari makes AI work reviewable. It gives each agent a clear task and limits,
> records every run, checks the result, requires independent review when
> needed, and keeps final approval with a human. Everything is stored in
> ordinary local files.

Palari is the product name. "Company OS" may remain in the repository name,
but it is a brand label rather than a claim that Palari is an operating system.

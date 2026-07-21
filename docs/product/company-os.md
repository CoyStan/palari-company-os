# How Palari Works

Palari makes AI work reviewable. It gives an agent a clear task and limits,
records what happened, checks the result, and keeps important approvals with
people.

Palari is local and file-backed. It works with coding agents and other AI tools;
it does not replace them or silently give them more permission.

## The Basic Idea

A company can use AI responsibly when it can answer a few ordinary questions:

- What is the goal?
- Which task is the agent doing?
- Which files, sources, and actions are allowed?
- What did the run change?
- Which checks passed for this exact version?
- Does another reviewer need to inspect it?
- Does a person need to approve it?
- What was the final result?

Palari stores these answers as explicit records. The machine names remain in
the JSON schema and command output:

- goals describe why work exists
- projects (`workbenches`) group related work
- agents (`Palaris`) are named AI work partners
- people (`humans`) own review and permission to approve
- sources identify the context an agent may read
- questions (`decisions`) record choices a person must make
- tasks (`work_items`) define one assignment and its limits
- runs (`attempts`) record one execution session
- run records (`receipts`) say what a run used, changed, skipped, and can undo
- check results (`evidence_runs`) are tied to the exact commit and outputs
- review results (`review_verdicts`) record independent inspection
- approvals or rejections (`human_decisions`) record human choices
- results (`outcomes`) preserve what was learned after a task closes

## Agents

An agent is the named AI worker for a task. The stored record is called a
`Palari` so it remains distinct from the model, tool, or host that happens to
perform a run.

An agent may:

- prepare work
- explain allowed sources
- perform a task within its limits
- summarize check results
- ask people for decisions
- preserve useful results

An agent may not approve its own work or silently expand its permissions. Its
name can remain stable even when different models or tools perform later runs.

## Projects

A project (stored as a `workbench`) groups one line of work. It names the goal,
shared context, allowed sources, output targets, people, agents, and active
tasks.

Tasks may depend on other tasks or have parent and child relationships. Their
parallel policy explains whether they can run together:

- `independent` tasks may run at the same time.
- `coordinate` tasks should be visible to the other operators.
- `exclusive` tasks should not overlap another active task that touches the
  same conflict target without a warning.

Task IDs are identities, not sequence numbers. Explicit dependencies determine
order, so unrelated tasks can run in parallel.

## Risk Levels

Palari recommends the lightest safe process for each task. The stored field for
this choice is `adaptive_intensity`.

### Light

For clear, low-risk maintenance. The task still needs defined limits, a
committed result, current checks, and a concise summary. Eligible R1/light work
may finish without independent review or human approval only when its task
rules explicitly require neither and allow no external action.

### Standard

For normal company work. The usual path is a task, run, run record, current
checks, independent review, and human approval when the task requires it.

### High

For production, security, policy, external actions, or permission changes.
These tasks need a clear goal, narrow limits, current checks, current review,
the required number of qualified human approvals, and checks that stop safely
when anything is missing.

Palari should infer this level from risk, ambiguity, possible impact, external
actions, prior results, and agent capability, then explain its recommendation.

## Teams

One local workspace can serve a single founder or a larger team. The stored
model supports:

- multiple people and agents
- role-based permissions
- one or more required approvals
- shared standards and context
- decisions across teams
- capacity and review-load signals

Simpler language and fewer commands must not erase the difference between an
agent's capabilities and a person's responsibility.

## Start With the Queue

The queue is the normal place to see what needs attention. It is a status view
(historically called a read model), so viewing it does not change a task or
grant approval.

It answers:

- what needs attention now
- why it matters
- which goal, project, and agent it belongs to
- who should act next
- which checks and reviews are current
- whether human approval is needed
- what the next safe action is
- which runs are active in parallel
- whether exclusive targets overlap

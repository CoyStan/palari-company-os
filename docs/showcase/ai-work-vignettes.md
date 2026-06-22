# AI Work Vignettes

Palari Company OS is easiest to understand through situations.

This page is for people who already use Claude, ChatGPT, Codex, Cursor, or other
AI tools in daily life and work, but feel the same recurring problem:

> The AI can help, but I still need to know what it read, what it changed, what
> it did not do, and when a human has to decide.

Palari is a local operating contract for that missing layer. It gives AI work a
small amount of structure without turning every request into bureaucracy.

## The 30-Second Pitch

Most AI tools are good at answering, drafting, and coding. They are less good at
showing the operating shape around the work:

- Which goal is this helping?
- Which sources was the AI allowed to read?
- Which files or outputs may it change?
- What is blocked until a human decides?
- What evidence or review exists?
- What receipt explains what happened?
- What else is running in parallel?

Palari Company OS keeps those answers in plain local workspace files and exposes
them through a Python CLI, agent packets, static dashboards, and prototypes.

## Workshop Framing

If you are showing this to friends in an AI workshop, describe Palari as:

> A way to make AI work legible, bounded, and reviewable.

Not:

> Another chatbot.

Not:

> A replacement for Claude, ChatGPT, Codex, Cursor, or the model you already use.

Palari is closer to a control panel around AI work. The model can still be
Claude, GPT, Gemini, a coding agent, or a human. Palari describes the work,
boundaries, receipts, and approvals.

For a workshop audience, translate the core words like this:

- goal = why we are doing the work
- source = what the AI is allowed to read
- work item = one bounded task
- attempt = one session of doing the task
- receipt = what happened
- human decision = where the AI stops and a person chooses

## Vignette 1: The Founder With Too Many Threads

### Situation

A founder has a messy mix of notes:

- a customer interview
- a copied Slack thread or exported chat note
- a pricing idea
- a bug report
- a half-written launch plan

They ask an AI:

> Can you turn yesterday's launch mess into something useful for today?

### Normal AI Failure Mode

The AI gives a polished answer, but the founder still wonders:

- Did it use the right notes?
- Did it invent context?
- Is this a plan, a draft, or a decision?
- What should happen next?
- Did anything get saved?

### Palari Version

Palari turns the mess into one visible task:

- Goal: "Launch the beta calmly."
- Area: "Beta Operations."
- Allowed sources: launch notes, customer interview, pricing questions.
- AI partner: Sofia.
- Task: "Prepare beta launch checklist."
- Result: a checklist plus a receipt record showing what Sofia used, created,
  skipped, and left for the founder.

In a demo, show the task row first:

```text
Prepare beta launch checklist | Sources: 3 | Status: ready for founder review
```

Then open the detail:

```text
What I used: launch notes, customer interview, pricing questions
What I made: beta launch checklist
What I did not do: send messages, change pricing, publish anything
Next step: founder review
```

The founder does not need to read raw JSON. The important thing is that the work
has shape.

### Why It Matters

The founder is not just getting text. They are getting a visible unit of work
with source boundaries and a next step.

## Vignette 2: The Daily-Life Version

### Situation

Someone is not running a company. They are planning a week:

- appointments
- notes from a call
- a half-written email
- a task list
- a document they need to update

They ask:

> Help me turn this into a plan for tomorrow.

### Normal AI Failure Mode

The AI makes a nice plan, but the person cannot tell which notes it used,
whether it changed anything, or which tasks are still only suggestions.

### Palari Version

The same primitives still work, just lighter:

- selected notes as sources
- one bounded task
- one attempt record for the AI-assisted session
- one output: tomorrow's plan
- one receipt record: what was used, created, and not changed

In a simple demo, the receipt might say:

```text
Read: call notes, calendar notes, task list
Created: tomorrow plan
Did not do: send email, edit calendar, delete tasks
Needs review: yes
```

No enterprise ceremony is needed. The structure can stay small.

### Why It Matters

The same idea scales down to daily life: a person should know what the AI used,
what it made, and what it did not do.

## Vignette 3: Giving A Coding Agent A Brief

### Situation

A developer opens a repo and wants Codex or another coding agent to help.

The usual prompt is something like:

> Read the repo and fix the issue.

That works sometimes, but it is vague. The agent has to infer:

- which files matter
- what it is allowed to touch
- what "done" means
- what evidence is required
- what should make it stop

### Palari Version

For a non-technical explanation, call this a task brief: one page that tells the
AI what the job is, what it may read, what it may change, and what proof it
needs before claiming it is done.

For a technical demo, the same idea appears as an agent packet:

```bash
palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
```

The brief says, in machine-readable form:

- who the Palari is
- what the task is
- which paths can be read
- which paths can be written
- which sources are allowed
- which actions are forbidden
- what output is required
- what proof is missing
- what commands are safe next

When the packet is ready, `agent start` saves the exact local packet under
`.palari/packets/` and records a local claim under `.palari/claims/`. If the
packet is blocked, `agent start` reports the blockers and writes nothing.

### Why It Matters

The agent no longer has to guess the operating contract. It gets one compact
brief and can later point back to the exact local task brief it was given.

## Vignette 4: The Trust Receipt

### Situation

An AI assistant edits a document or prepares a draft.

The human asks:

> What did you actually do?

### Normal AI Failure Mode

The assistant replies conversationally:

> I updated the summary and improved the tone.

That is helpful, but not operational. It does not clearly answer:

- What did you read?
- What did you create?
- Did you write externally?
- What did you avoid doing?
- Can I undo this?
- Which task brief produced this work?

### Palari Version

A Palari workspace can record a receipt like:

```text
Read: launch notes and customer interview
Changed: beta checklist draft
Did not do: send messages, change pricing, edit the roadmap
External writes: none
Needs human review: yes
Undo/check: see the saved draft and task packet
```

This receipt is not a legal audit system. It is a human-facing trust record.
It gives the person supervising the AI a plain explanation of the work.

### Why It Matters

The value is not only the output. The value is the confidence around the output.

## Vignette 5: The Human Approval Boundary

### Situation

A Palari prepares a message that could be posted to Slack, GitHub, Jira, email,
or a customer-facing system.

The human wants help drafting, but does not want the AI to send anything by
itself.

### Normal AI Failure Mode

The boundary lives in the prompt:

> Do not send this yet.

That is fragile. It depends on the model remembering the instruction.

### Palari Version

Palari treats the send as a prepared action, not a completed action:

```text
Destination: Slack #launch
Preview: "Beta checklist is ready for review..."
Status: waiting for human approval
Approver: launch communications owner
Current behavior: saved as a dry-run payload preview only; Palari does not call Slack
```

The underlying dry-run plan can describe:

- provider: Slack, GitHub, Jira, or email
- event: approval requested, review requested, work completed, work blocked, or incident opened
- action: notify, comment, create issue, or update issue
- payload preview: what would be sent
- approval requirement: who must approve

Today this is dry-run only. Palari does not call the real provider.

### Why It Matters

The AI can prepare work near the edge of the company without silently crossing
the edge. The human approval boundary is explicit.

## Vignette 6: Two People Or Agents Working In Parallel

### Situation

Two people are working on the same project:

- one person is editing the launch copy
- another is checking the pricing note
- an agent is preparing the changelog

Everyone is using the same repo or workspace.

### Normal AI Failure Mode

The team relies on chat memory and vibes:

- "I think I am working on this file."
- "I think the agent is only touching docs."
- "I think nobody else is editing the same thing."

That is fine for tiny work. It gets risky as soon as multiple threads are active.

### Palari Version

Palari can show the shared work map:

```text
Active work:
- Launch copy polish | Owner: Maya | Target: docs/launch.md | independent
- Pricing note review | Owner: Jordan | Target: docs/pricing.md | independent
- Changelog prep | Owner: Sofia | Target: CHANGELOG.md | coordinate

Warning:
- Two active tasks want to edit docs/launch.md with exclusive access.
```

Under the hood, Palari models workbenches, work items, attempts, dependencies,
output targets, conflict targets, and parallel policies. In a workshop, the
plain version is enough: who is doing what, what they may touch, and whether
anything collides.

### Why It Matters

Parallel AI work needs more than prompts. It needs a shared map of who is doing
what and where collisions might happen.

## Vignette 7: AI Skills Without Blindly Installing Everything

### Situation

Someone in a workshop asks:

> Which AI skills, plugins, or extensions should I use?

That is a good question, but a dangerous default answer is:

> Install a pile of tools and hope they help.

### Palari Version

Palari treats external playbooks and skills as guidance, not authority.

Example:

```text
Task: debug failing checkout test
Recommended playbooks:
- systematic debugging: find the smallest failing cause
- verification before completion: rerun the focused test before claiming done
- executing plans: keep the work structured and resumable
```

The playbook can suggest how to work, but it cannot expand what the AI is
allowed to read, write, approve, or send. The workspace still controls:

- goal
- scope
- allowed sources
- allowed paths
- forbidden actions
- proof requirements
- human decisions

### Why It Matters

Skills can improve performance, but they should not quietly expand authority.
Palari gives the agent process help while keeping company boundaries explicit.

## A Friendly Demo Script

If you have five minutes in a workshop:

1. Show the dashboard or desktop prototype first, not the schema.
2. Explain that a Palari is a named AI work partner with scope.
3. Show one task and its selected sources.
4. Show `agent brief` as the compact task brief.
5. Show `agent start` saving the packet and local claim for a ready packet.
6. Show `agent check --changed` catching whether edits stayed inside bounds.
7. Show a receipt and ask: "Would this make you more comfortable trusting the result?"

If you have fifteen minutes:

1. Start with a messy real-world ask.
2. Convert it into a goal, source, task, and Palari.
3. Generate or inspect an agent packet.
4. Discuss what is allowed and forbidden.
5. Show how evidence, review, and human decisions appear only when risk requires
   them.
6. End with the idea: "AI should be useful, but the work should still be
   inspectable."

## What Exists Today

This repo currently provides:

- a dependency-light Python CLI
- strict local workspace validation
- queue, detail, state, history, dashboard, and prototype surfaces
- agent packets for bounded AI work
- local packet persistence and claims
- source and receipt trust records
- dry-run integration planning and outbox states
- workbench and parallel-work modeling
- example and dogfood workspaces

## What Is Still Future Work

Palari Company OS is not yet:

- a hosted web app
- a real Slack, GitHub, Jira, email, or Drive connector
- a background agent runner
- a secret manager
- a replacement for human judgment
- a system that executes live external actions

For now, it is a local operating foundation: useful for modeling, testing,
dogfooding, and giving AI agents a clearer work contract.

## The Core Takeaway

The point is not to make AI work heavier.

The point is to make AI work safer to trust:

```text
selected sources -> bounded work -> agent packet -> attempt
  -> receipt -> evidence or review when needed -> human decision when needed
```

That is Palari Company OS in one line.

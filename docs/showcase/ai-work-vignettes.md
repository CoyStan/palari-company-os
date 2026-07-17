# AI Work Vignettes

Palari Company OS is easiest to understand through situations.

This page is for people who already use Claude, ChatGPT, Codex, Cursor, or
similar AI tools, and who keep running into the same nagging gap:

> "The AI gave me something useful. But I still can't tell what it actually
> read, what it changed, and what I'm supposed to do next."

Palari is the operating layer for that missing part. It gives AI work a small
amount of structure, just enough to make it legible, bounded, and easy to hand
off for review.

---

## The 30-Second Version

Think about the last time you got a long AI-generated output and wondered:

- Wait, which file or note did it actually use?
- Did it invent any of this, or did it stick to what I gave it?
- Is this a finished thing, or something I still need to approve?
- If something looks wrong, what exactly did it touch?

Those questions rarely have good answers in most AI tools. The output arrives.
The process disappears.

Palari keeps a simple record around the work: what the AI was allowed to read,
what it produced, what it did not do, and whether a human needs to approve
something before anything moves forward.

---

## Try It In 3 Minutes

You only need Python 3.10 or newer and Git. No API keys, cloud accounts, Slack,
GitHub app, Google Drive, database, or background service are required.

Clone the repo:

```bash
git clone https://github.com/CoyStan/palari-company-os.git
cd palari-company-os
```

Install the CLI in editable mode:

```bash
python3 -m pip install -e .
palari --help
```

If you do not want to install it yet, use the repo-local wrapper instead:

```bash
./bin/palari --help
```

Run the local verification:

```bash
./scripts/verify.sh
```

Copy the demo workspace into `/tmp` so you can try commands without changing
the committed example files:

```bash
rm -rf /tmp/palari-company-os-demo
cp -R examples/acme-company-os /tmp/palari-company-os-demo
```

Ask Palari what is waiting:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo queue
```

Open one piece of work:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo detail WORK-0001
```

If you want an app-like visual prototype, generate the desktop shell:

```bash
./bin/palari desktop-prototype --out /tmp/palari-desktop-prototype
```

Then open:

```text
/tmp/palari-desktop-prototype/index.html
```

Nothing here calls live providers or writes outside the local files you point it
at. These commands are for seeing the model, the prototype, and the agent
contract.

---

## See What The Agent Would Run

Palari is designed so a coding agent can read the work contract directly. A
human can run the commands below to inspect the flow, but in normal use these
are mostly agent-facing commands: the agent asks for a brief, starts a bounded
local work item, checks whether its changes stayed inside the allowed boundary,
and releases the claim when it is done.

Ask Palari for the next useful item for Sofia:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent next --as PALARI-SOFIA --json
```

Read the task brief the agent would receive:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
```

Start the copied demo work item. This saves the exact packet locally and creates
a local claim in the `/tmp` demo workspace:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
```

Check whether an observed file change stays inside the packet boundary:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json
```

Release the local claim:

```bash
./bin/palari --workspace /tmp/palari-company-os-demo agent release WORK-0003 --as PALARI-SOFIA --json
```

In plain language, this is the agent operating loop:

```text
find safe work -> read the task brief -> claim the local work item
  -> compare changes against the allowed boundary -> release or continue
```

The examples below explain why that loop is useful for both humans and agents.

---

## What Palari Is

Palari is:

> A way to make AI work legible, bounded, and reviewable.

Not:

> Another chatbot.

Not:

> A replacement for Claude, ChatGPT, Codex, or whatever model you already use.

Palari is closer to a control panel *around* AI work. The model can still be
Claude, GPT, Gemini, a coding agent, or a human collaborator. Palari describes
the work, the boundaries, the receipts, and the approval steps.

---

## Vignette 1: The Founder With Too Many Threads

### The situation

It is Monday morning. Maya runs a small software company. She has:

- notes from a Friday customer call
- a pricing question she jotted down in a doc
- an exported Slack thread from the weekend launch discussion
- a half-finished launch checklist she started on Friday

She asks Claude:

> "Can you pull this together and tell me what we need to do before launch?"

Claude gives her a polished reply. It sounds right. Then ten minutes later she
starts wondering:

- Did it use the pricing note, or just the Slack thread?
- Is this checklist its idea or mine?
- Should I send this to the team, or is this still a draft?
- What did it skip?

### What Palari adds

Before the AI runs, the work gets a visible shape:

- **Goal:** Ship the beta calmly.
- **Sources** (what it may read): customer call notes, pricing questions,
  weekend Slack export.
- **Task:** Prepare a beta launch checklist.
- **AI partner:** Sofia.

When Sofia finishes, the task row looks like this:

```text
Prepare beta launch checklist | Sources: 3 | Status: ready for Maya's review
```

Open the detail:

```text
What I read:        customer call notes, pricing questions, Slack export
What I made:        beta-checklist.md
What I did not do:  edit the roadmap, change pricing, send any messages
Next step:          Maya reviews and approves
```

This is a **receipt**: a plain-language record of what happened. Maya does not
need to parse a log. She can tell at a glance that the work stayed in bounds and
that she is the next decision-maker.

### Why it matters

Maya is not just getting text. She is getting a visible unit of work with source
boundaries, a clear record, and an explicit next step.

---

## A Quick Vocabulary Map

After the quick tour, the core vocabulary is small:

| Palari term | Plain meaning |
|-------------|---------------|
| Goal | Why the work exists |
| Source | What the AI was allowed to read |
| Work item | One bounded task |
| Attempt | One session of doing the task |
| Receipt | What the AI read, made, and did NOT do |
| Human decision | The explicit stop where a person must choose |
| Palari | A named AI work partner with a defined scope |

The labels matter less than the shape: selected sources, bounded work, visible
receipt, and explicit human authority when risk increases.

---

## Vignette 2: Planning Your Week (The Daily-Life Version)

### The situation

You are not running a company. You are just trying to plan tomorrow. You have:

- a few calendar notes from today
- notes from a call you took
- a task list that got away from you

You ask an AI to help you figure out what to focus on. The AI gives you a neat
plan. You feel better for about five minutes. Then:

- Did it look at the task list or just the call notes?
- Is "reschedule the dentist" something it decided, or something I already
  planned?
- Did it mark anything done?

### What Palari adds

The same structure scales down to personal use: lighter, but the same shape:

- **Sources** it may read: call notes, today's calendar notes, task list.
- **Task:** Plan tomorrow.
- **Output:** tomorrow-plan.md

Receipt:

```text
Read:          call notes, calendar notes, task list
Created:       tomorrow-plan.md
Did not read:  your emails (not selected as a source)
Did not do:    edit your calendar, mark tasks complete, send anything
Needs review:  yes
```

No enterprise ceremony needed. The structure stays small; the legibility stays
the same.

### Why it matters

The same idea scales down to daily life: you should know what the AI used, what
it made, and what it left untouched.

---

## Vignette 3: Giving a Coding Agent a Real Brief

### The situation

A developer wants to use Codex or a similar agent to help fix a bug. The usual
prompt is:

> "Read the repo and fix the failing test."

That works sometimes. But the agent has to guess a lot:

- Which files actually matter?
- Which ones am I allowed to change?
- What does "done" look like?
- When should I stop and ask a human?

### What Palari adds

Palari generates an **agent packet**: a compact brief that answers all of those
questions in one place, in machine-readable form.

For a non-technical explanation, think of it as a task card handed to a
contractor:

> "Here is what you are fixing. Here is what you can read. Here is what you can
> write. Here is what done looks like. Do not touch anything else."

For a technical demo, the same idea looks like this:

```bash
palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json
palari agent start WORK-0003 --as PALARI-SOFIA --mode execute --json
```

The packet tells the agent:

- who they are (Sofia)
- what the task is
- which paths they may read and write
- which actions are forbidden
- what proof is required before claiming done
- which commands are safe to run next

`agent start` saves the exact packet locally and records a claim on the work.
If the packet says `blocked`, nothing is saved and the agent stops.

After the work, `agent check` can compare which files were actually edited
against what the packet allowed, catching drift before it becomes a problem.

### Why it matters

The agent does not have to infer the scope from clues in the codebase. It gets
one compact brief, and it can always point back to the exact brief it was given.

---

## Vignette 4: The Trust Receipt

### The situation

An AI assistant finishes editing a document. You ask:

> "What did you actually do?"

The AI replies:

> "I updated the summary section and improved the tone throughout."

That is useful, but it is conversational. It does not tell you:

- Which version of the file did you start from?
- Did you edit the pricing section I said to leave alone?
- Did you write anything externally?
- If something looks off, what exactly changed?

### What Palari adds

A Palari workspace can record a receipt in a consistent format:

```text
Read:               launch-notes.md, customer-interview.md
Changed:            beta-checklist.md (draft)
Did not change:     pricing.md, roadmap.md
External writes:    none
Needs human review: yes
Undo reference:     see saved draft and task packet
```

A receipt is not a legal audit log. It is a human-facing trust record: the
plain explanation a person needs to feel comfortable with the output before
acting on it.

### Why it matters

The value is not only the output. The value is the confidence around the output.
You can hand this receipt to a colleague or a future version of yourself and it
will make sense.

---

## Vignette 5: The Human Approval Boundary

### The situation

An AI finishes drafting a message to post in Slack, or to open as a GitHub
issue, or to send to a customer. You wanted help drafting it. You did not want
it sent yet.

In most AI tools, the boundary lives in the prompt:

> "Do not send this yet."

That is fragile. The model may or may not remember it across a long session.

### What Palari adds

Palari treats "send this" as a **prepared action**, not a completed action. The
AI prepares the message and stops. A human must explicitly approve before it
goes anywhere.

The planned message looks like this:

```text
Destination:    Slack #launch
Preview:        "Beta checklist is ready for review..."
Status:         waiting for human approval
Approver:       launch communications owner
Current state:  saved as dry-run preview only; Palari has not called Slack
```

**Important:** This is dry-run only today. Palari does not connect to Slack,
GitHub, email, or any external system. The preview shows what *would* be sent
if a live connector existed. It does not send anything. That gap is
intentional.

### Why it matters

The AI can prepare work right up to the edge of the company. The human decides
whether it crosses. That boundary is explicit, not implied by a prompt the
model might forget.

---

## Vignette 6: Two People (or Agents) Working at the Same Time

### The situation

Three threads are active on the same project at once:

- Jordan is editing the launch copy in `docs/launch.md`
- Alex is reviewing the pricing note in `docs/pricing.md`
- Sofia (an AI partner) is preparing the changelog in `CHANGELOG.md`

Everyone is working from the same repo. Nobody is coordinating in real time.

In most team workflows, the answer to "is anyone else touching this file?" is:
"I think so, probably not, let me check Slack."

### What Palari adds

Palari can show the shared work map:

```text
Active work:
- Launch copy polish  | Owner: Jordan | Target: docs/launch.md    | independent
- Pricing review      | Owner: Alex   | Target: docs/pricing.md   | independent
- Changelog prep      | Owner: Sofia  | Target: CHANGELOG.md      | coordinate

Warning:
- Two active tasks want to edit docs/launch.md with exclusive access.
```

Work items carry a **parallel policy**: `independent` (can run beside other
work), `coordinate` (should be visible to other operators), or `exclusive`
(should not overlap another item touching the same target). The plain version
is the important part: who is doing what, what they may touch, and where things
might collide.

### Why it matters

Parallel AI work needs more than prompts. It needs a shared map of who is doing
what and where the risks of collision are.

---

## Vignette 7: Skills and Plugins Without Blindly Installing Everything

### The situation

Someone in a workshop asks:

> "Which AI skills, plugins, or extensions should I use for this?"

The dangerous default answer is: "Install a pile of tools and hope they
compose."

### What Palari adds

Palari treats external skills and playbooks as **process guidance**, not
authority grants. Recommending a skill does not change what the AI is allowed
to read, write, or send. Those boundaries live in the workspace and do not
move.

Example: an agent is about to debug a failing checkout test. Palari recommends:

```text
Task: debug failing checkout test
Suggested playbooks:
- systematic debugging: find the smallest failing cause first
- verification before completion: rerun the focused test before claiming done
- executing plans: keep the work structured and resumable
```

These are suggestions for *how* to work. They do not change:

- which files the agent may touch
- which sources it may read
- which actions require human approval
- what proof is needed before the work closes

### Why it matters

Skills can sharpen performance. They should not quietly expand scope. Palari
keeps the two things separate.

---

## Workshop-Friendly Demo Flow

For a live workshop or a quick project walkthrough, Palari works best when the
bounded work and its evidence come first and the schema stays in the background.

### Five-minute version

A short demo can stay visual:

1. Open the queue, one work detail, or the desktop prototype.
2. Pick one task and inspect what the AI is allowed to read.
3. Compare that with what it is not allowed to touch.
4. Open the compact `agent brief` packet the agent would receive.
5. Open a receipt and check whether the result feels easier to trust.

### Fifteen-minute version

A longer walkthrough can use a messy real-world ask, such as "help me prep for
this meeting," "fix this bug," or "draft this message for the team." The useful
sequence is:

1. Define the goal, selected sources, AI partner, and bounded task.
2. Inspect the agent packet and the explicit forbidden actions.
3. Show that evidence, review, and human decisions appear only when risk is
   higher. Low-risk work stays light.
4. Inspect the dry-run integration preview and confirm that it does not send
   anything.
5. Close on the core idea: AI should be useful, and the work should also be
   inspectable.

---

## What Exists Today

This is a v0.1 local CLI. Here is what is real:

- dependency-light Python CLI (no external packages needed)
- strict local workspace validation
- queue, detail, state, history, Mission Control, and desktop prototype views
- agent packets for bounded AI work, with local packet persistence and claims
- source and receipt trust records
- dry-run integration planning and cancelable outbox records (no live calls)
- workbench and parallel-work modeling
- example and dogfood workspaces

## What Is Still Future Work

Palari Company OS is not yet:

- a hosted web app you can log into
- a real Slack, GitHub, Jira, email, or Drive connector
- a background agent runner
- a secret manager
- a system that executes live external actions automatically
- a replacement for human judgment

For now, it is a local operating foundation, useful for modeling AI work,
testing the contract, and giving agents a clearer brief.

---

## The Core Takeaway

The point is not to make AI work heavier.

The point is to make AI work safe to hand off.

When someone asks "what did the AI actually do?", you should be able to show
them, not guess.

```text
selected sources -> bounded task -> agent packet -> attempt
  -> receipt -> evidence or review when needed
    -> human decision when needed -> outcome
```

Each step in that chain is inspectable. Each step has a human override point.
The AI does the work; the record shows the shape.

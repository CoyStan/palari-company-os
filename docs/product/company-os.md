# Palari Company OS Product Model

Palari Company OS is a company AI operating system. Its job is not to turn
every task into bureaucracy. Its job is to make AI-assisted work legible,
bounded, reviewable, and useful.

## Core Idea

A normal company becomes AI-native when it can name the workstreams where AI
helps, define the humans who hold authority, preserve evidence of what
happened, and learn from outcomes.

Palari Company OS is organized around:

- goals as company intent
- workbenches as bounded arenas of shared work
- Palaris as named AI work partners
- humans as authority holders
- sources as explicit readable context
- decisions as explicit requests for judgment
- work items as scoped units of work
- attempts as concrete execution sessions
- receipts as human-facing records of what an attempt used, changed, did not do,
  and can undo
- evidence runs as proof tied to a head or artifact state
- review verdicts as independent inspection
- human decisions as authority-bearing actions
- outcomes as learning records

## Palaris

A Palari is the named face of a workflow or AI workstream.

A Palari may:

- prepare work
- explain sources
- coordinate bounded execution
- summarize evidence
- ask humans for decisions
- preserve memory and outcomes

A Palari may not silently grant itself authority. The human-facing identity can
remain stable even if execution is delegated to different models, tools, or
workers.

## Workbenches

A Workbench is the bounded arena where a human/Palari team works in parallel.
It names the shared context, selected sources, output targets, goals, humans,
Palaris, and active work items for one line of work.

Work items may belong to a workbench, have parent/child relationships, depend on
other work items, and declare a parallel policy:

- `independent` work can run beside other work.
- `coordinate` work should be visible to other operators.
- `exclusive` work should not overlap another active item touching the same
  conflict target without a coordination warning.

This keeps parallel work legible without burying it in process ceremony.

## Adaptive Intensity

The system should recommend the lightest responsible operating mode.

### Light

For clear, low-risk maintenance. Expected proof is a branch, clear scope,
focused tests, and a concise summary.

### Standard

For normal governed company work. Expected proof is a work item, attempt,
evidence run, review verdict, and human decision when needed.

### High

For production, security, policy, broker, external side effects, or authority
changes. Expected proof includes explicit goal linkage, strong scope, fresh
evidence, fresh review, human quorum, and fail-closed gates.

The operator should not have to micromanage intensity. The system should infer
it from risk, ambiguity, blast radius, external side effects, prior outcomes,
and model capability, then explain the recommendation.

## Team Compatibility

The first workspace can serve one founder, but the object model should not
collapse into one-person assumptions. It should support:

- multiple humans
- multiple Palaris
- role-based authority
- approval quorum
- shared standards
- shared memory
- cross-team decisions
- capacity and governance-load signals

Simplification should reduce visible ritual, not erase the distinction between
human accountability and AI capability.

## Queue First

The default surface is the queue. The queue is a read model, not an authority
mutation surface.

It answers:

- what needs attention now
- why it matters
- which goal and Palari it serves
- who or what should act next
- what evidence and review exist
- what human decision is needed
- what exact next action is safe
- which workbench contains the work
- what parallel attempts are active
- whether overlapping exclusive targets need coordination

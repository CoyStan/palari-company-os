# Core Objects

Palari Company OS starts with a small set of explicit objects. The first
implementation keeps them as Python dataclasses and JSON records so the model
is easy to inspect and cheap to change.

## Goal

Company intent. Goals answer why work exists.

## Palari

Named AI work partner or workflow identity. A Palari has a scope, allowed
inputs, standards, memory sources, owner human, and forbidden actions.

## Human

Authority and accountability profile. Humans hold approval capabilities; AI
roles do not silently inherit them.

## Decision

Structured request for human judgment. Decisions keep important questions out
of vague status text.

## Work Item

Scoped unit of work. It has risk, adaptive intensity, scope, allowed resources,
forbidden actions, acceptance target, and verification expectations.

## Attempt

Concrete execution session for a work item. Attempts record actor, branch or
workspace, worker/model, commits, and changed files.

## Evidence Run

Proof attached to a work item and attempt. Evidence records commands, status,
head SHA, artifacts, summary, and timestamp.

## Review Verdict

Independent inspection. Verdicts are intentionally small:

- `accept-ready`
- `changes-requested`
- `needs-human-decision`
- `blocked`

## Human Decision

Authority-bearing human action tied to reviewed evidence. This is separate from
the review verdict.

## Outcome

Learning record after work completes. Outcomes preserve what was useful, what
failed, and what follow-up is needed.


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

## Source

Human-selected input that a Palari may use. Sources record label, provider,
generic URI or external id, access mode, owner human, allowed Palaris, selected
state, and last-read metadata. They model the boundary of what was available to
the Palari; this v0 object does not connect to real providers yet.

## Playbook Source

External operating guidance that Palari may recommend while preparing work.
Playbook sources record label, provider, URI, pinned ref, license, enabled
state, and the explicit list of included playbooks. Superpowers compatibility
uses this object to link to allowed `SKILL.md` playbooks without making them
Palari authority.

## Work Item

Scoped unit of work. It has risk, adaptive intensity, scope, allowed resources,
allowed sources, allowed actions, output targets, forbidden actions, acceptance
target, verification expectations, and optional recommended playbooks.

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

## Receipt

Human-facing trust record for an attempt. A receipt says which sources were
used, what actions were taken, what outputs were created, what external writes
occurred, what was not done, and what undo references exist. Receipts are not
governance evidence; they help the user review, undo, or continue bounded work.

## Outcome

Learning record after work completes. Outcomes preserve what was useful, what
failed, and what follow-up is needed.

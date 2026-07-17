# Lifecycle Guide

Palari Company OS models this loop:

```text
Goal -> Palari -> Work -> Attempt -> Receipt -> Evidence -> Review -> Human Decision -> Outcome
```

For asynchronous preparation, multiple reviewed items may be compiled into a
parked Approval Inbox:

```text
bounded preparation -> parked item proofs -> canonical Approval Pack
-> one exact human pack decision -> eligible local execution -> outcome
```

The interaction is compressed; each item keeps its own scope, attempt,
receipt, evidence, review, decision, and journal result. A dependency change
stales descendants—even when a narrowed pack omits the dependency—while
unrelated current members retain their valid state. A changed risk or batch
policy also stales the exact pack. Recursive dependency bindings make a changed
terminal dependency artifact stale rather than treating terminal status as
sufficient. External or irreversible effects remain parked for their native
individual gate.

## Normal Operator Path

The normal path derives mechanical records instead of asking an agent to copy
their ids and digests:

```bash
palari init
palari work add "Draft onboarding note" --write docs/onboarding.md
palari agent start --next --as PALARI-ID --json
# work inside the packet and commit the bounded result
palari agent advance WORK-ID --as PALARI-ID --json
```

The compatible `--write` form requires an output to exist. Use repeatable
`--create`, `--modify`, and `--delete` instead when exact mutation class
matters; exact intents cannot be mixed with `--write`.

`start --next` selects exactly one item already considered safe by the queue,
persists its packet and portable session contract, and claims it. `advance`
derives the exact claim range, checks declared path intent, runs verification,
and records deterministic attempt, receipt, evidence, and closeout state. It
then completes eligible low-risk work or stops at independent review, exact
human authority, external state, or a concrete blocker. Neither command creates
an independent verdict or human decision.

After a separate current review, a qualified human uses one inbox and one exact
action:

```bash
palari queue --approval-inbox --json
# inspect the emitted presentation, then run its exact
# `palari human-decision pack ...` command once
```

The action binds the current pack and presentation digests. Stale proof,
incomplete quorum, non-batchable work, and external effects remain parked with
an explicit owner and next step. Review and acceptance stay attributable to
distinct actors.

When execution stops before proof is ready, preserve that fact before releasing
ownership:

```bash
palari agent park WORK-ID --as PALARI-ID \
  --reason "Waiting for product direction" \
  --next-action "Ask the founder to choose the final wording" --json
```

Parking records one blocked attempt and the exact next safe action, then
releases the owned claim. It creates no completion proof or authority. The
workspace must already have a writable governance journal; legacy work receives
the exact explicit `history --checkpoint` activation action and no retroactive
continuity claim. The commands below remain available as lower-level authoring
and recovery surfaces; they are not the ordinary agent ceremony.

## Create Intent And Actors

```bash
./bin/palari goal create GOAL-X --title "Improve onboarding"
./bin/palari human create HUMAN-X --name "X Human" --list approval_capabilities=product
./bin/palari palari create PALARI-X --name Xena --role "Onboarding partner" --owner-human HUMAN-X --list linked_goals=GOAL-X
```

## Create Work

```bash
./bin/palari work create WORK-X \
  --title "Draft onboarding note" \
  --goal GOAL-X \
  --palari PALARI-X \
  --risk R2 \
  --intensity standard \
  --list allowed_resources=docs/product/company-os.md \
  --list forbidden_actions=deploy \
  --required-approval-capability product
```

## Record Attempt, Receipt, Evidence, Review, And Human Decision

```bash
./bin/palari attempt record ATTEMPT-X \
  --work-item-id WORK-X \
  --actor PALARI-X \
  --list commits=head-x \
  --list changed_files=docs/product/company-os.md

./bin/palari work update WORK-X --set current_attempt=ATTEMPT-X

./bin/palari receipt record RECEIPT-X \
  --work-item-id WORK-X \
  --attempt-id ATTEMPT-X \
  --actor PALARI-X \
  --list actions_taken="drafted the bounded note" \
  --list outputs_created=docs/product/company-os.md

./bin/palari lifecycle evidence EVIDENCE-X \
  --work-item-id WORK-X \
  --attempt-id ATTEMPT-X \
  --head-sha head-x \
  --status passed \
  --summary "Focused verification passed." \
  --list "commands=python3 -m unittest discover -s tests"

./bin/palari attempt closeout ATTEMPT-X \
  --head-sha head-x \
  --cleanliness clean \
  --changed docs/product/company-os.md

./bin/palari lifecycle review REVIEW-X \
  --work-item-id WORK-X \
  --reviewed-head head-x \
  --reviewer HUMAN-X \
  --verdict accept-ready

./bin/palari lifecycle decide HUMAN-DECISION-X \
  --work-item-id WORK-X \
  --human-id HUMAN-X \
  --reviewed-head head-x \
  --decision accepted \
  --status accepted \
  --evidence-reference EVIDENCE-X \
  --review-reference REVIEW-X
```

Acceptance fails closed if the human lacks the required capability, evidence is
missing or stale, review is missing or stale, or the decision head does not
match the reviewed head. An `accept-ready` review is automatically bound to the
exact terminal attempt, receipt, evidence manifest, reviewed head, and work
contract. Any later substantive change requires refreshed proof and a new
review.

For a coherent set, use `queue --approval-inbox` and the human-only
`human-decision pack` surface. Agents may prepare or summarize a pack but may
not record that decision. A pack with incomplete quorum records the qualified
vote and leaves execution parked; a later qualified human must act on the same
stored exact manifest.

The journal also exposes content-addressed state checkpoints. Restoring an
earlier checkpoint appends a new transition and reason. It reproduces local
governed state but does not erase history. If an external effect occurred after
that checkpoint, restoration is blocked before mutation because rewinding an
outbox or receipt could invite duplicate execution.

`palari proof export` normalizes this same lifecycle into a PCAW v1 statement.
An offline verifier derives `blocked`, `review-required`,
`human-decision-required`, `accept-ready`, `accepted`, or `completed` from the
included records rather than trusting the claimed state. Legacy lifecycle
records remain loadable, but absent artifact digests or stage timestamps are
reported honestly and cannot become PCAW acceptance verification.

Workspace work items may declare exact `create`, `modify`, and `delete` path
intents. A delete succeeds only as an absent-path tombstone corroborated by Git;
it is not treated as a missing required output. This is local lifecycle proof,
not a new PCAW v1 portability claim: the v1 protocol does not encode portable
deletion history.

## Complete Work And Record Outcome

```bash
./bin/palari lifecycle complete WORK-X

./bin/palari lifecycle outcome OUTCOME-X \
  --work-item-id WORK-X \
  --summary "The onboarding note was accepted."
```

Completion fails closed unless the queue says the work is ready to integrate.

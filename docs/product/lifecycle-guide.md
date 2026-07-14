# Lifecycle Guide

Palari Company OS models this loop:

```text
Goal -> Palari -> Work -> Attempt -> Receipt -> Evidence -> Review -> Human Decision -> Outcome
```

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

`palari proof export` normalizes this same lifecycle into a PCAW v1 statement.
An offline verifier derives `blocked`, `review-required`,
`human-decision-required`, `accept-ready`, `accepted`, or `completed` from the
included records rather than trusting the claimed state. Legacy lifecycle
records remain loadable, but absent artifact digests or stage timestamps are
reported honestly and cannot become PCAW acceptance verification.

## Complete Work And Record Outcome

```bash
./bin/palari lifecycle complete WORK-X

./bin/palari lifecycle outcome OUTCOME-X \
  --work-item-id WORK-X \
  --summary "The onboarding note was accepted."
```

Completion fails closed unless the queue says the work is ready to integrate.

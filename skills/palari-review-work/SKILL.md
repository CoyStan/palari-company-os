---
name: palari-review-work
description: Independently review completed work in a Palari-managed Git repository. Use when a Palari execution handoff, review boundary, review packet, or supervisor asks a reviewer model to inspect exact committed changes and proof, choose a review verdict, and record it without editing the candidate or performing human approval. Do not use for implementation, self-review, or human decisions.
---

# Palari Review Work

Use Palari's review packet as the authority for what to inspect and which
verdict command may run. Review is independent judgment, not another execution
pass and not human approval.

## Review the exact candidate

1. Use a reviewer identity distinct from the builder. Open the exact review
   task named by the handoff:

   ```bash
   palari agent start WORK-ID --as REVIEWER-ID --mode review --json
   ```

2. Continue only when the saved review task brief is `ready`, names the current
   reviewer, and binds current run, receipt, evidence, base, and candidate head.
   A review packet is read-only; do not edit or commit candidate files.
3. Inspect the exact base-to-head change against the task scope, acceptance
   target, path intents, sources, and forbidden actions. Confirm that:

   - every claimed output is present and inside the declared boundary;
   - evidence is current for the exact candidate head and adequate for the risk;
   - the receipt accurately states sources, outputs, external writes, omissions,
     and undo references; and
   - the change adds no undeclared behavior or authority.

4. Run only useful read-only checks allowed by the packet. Do not alter the
   candidate to make it pass. Report findings in severity order with exact file
   references, impact, and the smallest correction.
5. Choose a verdict. Read [verdicts.md](references/verdicts.md) when the choice
   is not immediate. Obtain a fresh canonical projection if needed:

   ```bash
   palari agent status WORK-ID --as REVIEWER-ID --mode review --json
   ```

   Treat missing, stale, or head-mismatched required proof as `blocked`, not
   `changes-requested`; there is no current candidate judgment to record.
6. Record only the exact command emitted for that verdict in
   `agent_action_commands` or `review_record_commands`. Confirm its actor is the
   current reviewer and its reviewed head is still the inspected head. Never
   reconstruct a command from a template, prose, or memory.
7. Inspect the post-review status, report the verdict and exact reviewed head,
   then stop at the human or next-owner boundary.

## Non-negotiable boundaries

- Never review work built by the same identity.
- Never edit, commit, rebase, merge, push, deploy, or perform an external write.
- Never run `palari approve` or `palari human-decision`.
- Never accept stale, missing, inaccessible, or contradictory proof.
- Never convert `accept-ready` into a claim that the task is complete or
  approved.
- Never add compatibility behavior or use removed legacy workflow commands.

If no material issue exists, say `No findings.` If review cannot be completed,
identify the missing fact or authority and select the matching emitted verdict;
do not guess.

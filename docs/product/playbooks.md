# External Playbooks

Palari can link to outside operating guides without letting them change task
permissions or approval rules.

This recommendation feature is parked pending a product decision. It is not a
current product feature and carries no pre-1.0 compatibility promise. The
retained pattern can point to `obra/Superpowers`, allow a specific list of
skills, and recommend those skills for a task. Recommendations do not become
required steps or grant permission.

Palari remains the source of truth for:

- goals;
- allowed files, sources, and actions;
- required checks and approvals;
- run records and check results;
- independent review results;
- human approvals; and
- final results.

External playbooks provide process guidance only.

## Stored format

Declare a playbook source in `workspace.json`:

```json
{
  "playbook_sources": [
    {
      "id": "superpowers",
      "label": "Superpowers skills",
      "provider": "github",
      "uri": "https://github.com/obra/Superpowers",
      "ref": "main",
      "license": "MIT",
      "enabled": true,
      "included_playbooks": [
        "brainstorming",
        "writing-plans",
        "executing-plans",
        "verification-before-completion",
        "requesting-code-review",
        "systematic-debugging",
        "subagent-driven-development"
      ]
    }
  ]
}
```

A task can pin skills selected by a human or agent:

```json
{
  "recommended_playbooks": [
    "superpowers:verification-before-completion",
    "superpowers:requesting-code-review"
  ]
}
```

Validation stops safely if a task names a missing playbook source or a skill
that source does not allow.

## Retained default set

Palari starts with three Superpowers skills as the default operating set for
active repository tasks:

- `superpowers:verification-before-completion`
- `superpowers:executing-plans`
- `superpowers:systematic-debugging`

These skills do not replace judgment. They give an agent a small reusable
working loop:

- keep the task structured and resumable;
- verify before saying it is complete; and
- use a disciplined repair loop when checks or review fail.

These defaults appear in `playbooks sources`, are included in recommendations
for open tasks when available, and are used in Palari's own repository.

## Commands

List configured sources and available playbooks:

```bash
./bin/palari playbooks sources
./bin/palari playbooks sources --json
```

Ask Palari which playbooks fit a task:

```bash
./bin/palari playbooks recommend WORK-0003
./bin/palari playbooks recommend WORK-0003 --json
```

The result includes one short `action_guidance` sentence for each recommended
playbook. This guidance helps an agent start, but it does not create a task
brief, required check, assignment, review result, or approval. The task's
allowed files, sources, actions, and approval rules remain the source of truth.

Create a playbook source with the existing command:

```bash
./bin/palari playbook-source create superpowers \
  --label "Superpowers skills" \
  --provider github \
  --uri https://github.com/obra/Superpowers \
  --ref main \
  --license MIT \
  --list included_playbooks=brainstorming,writing-plans,verification-before-completion
```

## Recommendation loop

Palari combines two signals:

- playbooks already selected on the task; and
- automatic suggestions based on task status.

Each recommendation also carries one practical `action_guidance` sentence for
CLI output and possible future UI or agent use.

Examples:

- no run yet: consider brainstorming and planning skills;
- open task: include the default set when available;
- a run exists but check results are missing: use
  `verification-before-completion`;
- checks passed but independent review is missing: use
  `requesting-code-review`;
- checks failed or review requested changes: use `systematic-debugging`;
- high-risk or high-intensity task: consider `subagent-driven-development`;
  and
- a final result lists failures or follow-up work: use `executing-plans`.

As completed tasks record results, failures, and follow-ups, maintainers can
improve these deterministic recommendations. Palari does not learn or execute
external instructions by itself.

## Boundaries

Do not treat imported playbooks as permission or approval. They are guidance
that must stay inside the Palari task boundary.

Do not blindly sync or execute external instructions. Pin sources by URI and
ref, list allowed skills explicitly, and keep workspace validation strict.

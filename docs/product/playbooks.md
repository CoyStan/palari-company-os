# External Playbooks

Palari Company OS can link to external operating playbooks without making them
the source of authority.

The first supported pattern is Superpowers compatibility. A workspace can point
at `obra/Superpowers`, list the specific skills it wants to allow, and then let
Palari recommend those skills for a work item.

Palari still owns:

- goals
- scope
- selected sources
- allowed actions
- authority boundaries
- receipts
- evidence
- review
- human decisions
- outcomes

External playbooks contribute process guidance only.

## Workspace Contract

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

Work items can pin human- or Palari-selected skills:

```json
{
  "recommended_playbooks": [
    "superpowers:verification-before-completion",
    "superpowers:requesting-code-review"
  ]
}
```

Validation fails closed if a work item references a missing playbook source or a
skill not listed by that source.

## Core Default Set

Palari starts with three Superpowers skills as the default operating set for
active repo work:

- `superpowers:verification-before-completion`
- `superpowers:executing-plans`
- `superpowers:systematic-debugging`

The point is not to outsource judgment to Superpowers. The point is to give a
Palari a small reusable operating loop:

- keep the work structured and resumable
- verify before completion claims
- switch into a disciplined repair loop when evidence or review fails

These defaults are exposed in `playbooks sources`, included in recommendation
payloads for open work when available, and dogfooded in the Palari Company OS
workspace.

## Commands

List configured sources and available playbooks:

```bash
./bin/palari playbooks sources
./bin/palari playbooks sources --json
```

Ask Palari which playbooks fit a work item:

```bash
./bin/palari playbooks recommend WORK-0003
./bin/palari playbooks recommend WORK-0003 --json
```

The recommendation output includes short operating guidance for each recommended
playbook. This guidance is intentionally lightweight: it helps an agent start
well, but it does not create a packet, gate, claim, review, or approval step.
The work item's scope and authority remain the source of truth.

Create a playbook source with the normal authoring command:

```bash
./bin/palari playbook-source create superpowers \
  --label "Superpowers skills" \
  --provider github \
  --uri https://github.com/obra/Superpowers \
  --ref main \
  --license MIT \
  --list included_playbooks=brainstorming,writing-plans,verification-before-completion
```

## Recommendation Loop

Palari combines two signals:

- selected playbooks already listed on the work item
- automatic recommendations from work state

Each recommendation also carries one practical `action_guidance` sentence for
CLI output and future UI/agent use.

Examples:

- no attempt yet: consider brainstorming and planning skills
- open work: include the core default operating set when available
- attempt exists but evidence is missing: use verification-before-completion
- evidence passed but review is missing: use requesting-code-review
- evidence failed or review requested changes: use systematic-debugging
- high-risk or high-intensity work: consider subagent-driven-development
- outcome has failures or follow-ups: use executing-plans

This is the start of a self-improving loop. As work accumulates outcomes,
failures, and follow-ups, Palari can recommend better operating playbooks for
future work packets.

## Boundaries

Do not treat imported playbooks as authority. They are guidance that must sit
inside the Palari work boundary.

Do not blindly sync or execute external instructions. Pin sources by URI/ref,
list allowed skills explicitly, and keep workspace validation strict.

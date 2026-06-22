# Palari Desktop App Data Contract

This document defines the read-only data contract used by the Palari Desktop shell prototype. It is a v0 contract for demo and product-shaping work, not a final backend API.

The contract is intentionally close to the product model:

- a workspace contains workbenches
- a workbench has assigned humans and Palaris
- a Palari works inside a bounded workbench
- sources describe what the Palari can read, cannot read, or can write only after approval
- work items contain attempts
- attempts produce receipts, authority state, history, and chat context

The current demo fixture lives at:

`examples/desktop-demo/workspace.json`

## Top-Level Shape

Required top-level fields:

- `schema_version`: string. Current value: `desktop-app-data/v0`.
- `workspace`: workspace object.
- `workbenches`: object keyed by workbench id.
- `selected_workbench_id`: id of the workbench rendered by default.
- `humans`: object keyed by human id.
- `palaris`: object keyed by Palari id.
- `sources`: object keyed by source id.
- `work_items`: object keyed by work item id.
- `ui`: prototype display defaults.

Unknown top-level fields should be treated cautiously. Future app code should fail closed or ignore only explicitly documented optional fields.

## Workspace

Required fields:

- `id`: stable workspace id.
- `label`: human-readable workspace name.
- `owner_human_id`: id in `humans`.
- `description`: short workspace description.

## Workbench

Required fields:

- `id`: stable workbench id.
- `path`: ordered path labels, such as `["Public Policy", "Housing"]`.
- `title`: display title.
- `selected_palari_id`: id in `palaris`.
- `assigned_human_ids`: array of ids in `humans`.
- `source_groups`: ordered source explorer groups.
- `work_queue`: queue tab/count metadata.
- `work_item_ids`: ordered ids in `work_items`.

Source group fields:

- `id`
- `label`
- `tone`: visual/system tone such as `read`, `inherit`, `write`, `blocked`.
- `source_ids`: ordered ids in `sources`.

## Human

Required fields:

- `id`
- `name`
- `role`
- `initials`
- `avatar_class`

Humans represent real people who can own sources, review work, or approve actions.

## Palari

Required fields:

- `id`
- `name`
- `role`
- `scope`
- `avatar_class`

A Palari is the named AI coworker face of a work scope. Execution may later be delegated to tools or agents, but the Palari remains the human-facing work identity.

## Source

Required fields:

- `id`
- `title`
- `provider`: examples include `Google Drive`, `Google Doc`, `Uploaded file`, `Local note`, `Public web`.
- `external_id`: provider-side or demo id. The prototype never dereferences it.
- `access`: display access boundary.
- `owner_human_id`: id in `humans`, or null when owned by an external/public source.
- `owner_label`: fallback label when no local human owns it.
- `last_seen`
- `allowed_palari_ids`: ids in `palaris`.
- `mode`: display mode, such as `Readable`, `Inherited`, `Writable after approval`, `Blocked`.
- `mode_class`: CSS chip class.
- `tone`: file badge tone.
- `type_label`: compact file/provider type label.
- `summary`: human-readable permission explanation.

Sources are permission objects, not file contents. A source row can represent a selected file, inherited source, output target, or blocked material.

## Work Item

Required fields:

- `id`: internal id.
- `public_id`: display id.
- `title`: task title.
- `artifact_title`: center artifact title.
- `palari_id`: assigned Palari id.
- `due_label`
- `priority_label`
- `priority_class`
- `risk_label`
- `allowed_source_ids`: source ids the Palari may use.
- `output_target_ids`: source ids that are output targets.
- `allowed_actions`: action labels for the work boundary.
- `approval_copy`: short explanation of approval/write behavior.
- `current_attempt_id`: id in `attempts`.
- `attempts`: object keyed by attempt id.

## Attempt

Required fields:

- `id`
- `number`
- `status_label`
- `status_class`
- `updated_label`
- `word_count`
- `language`
- `sources_used`: ordered source ids.
- `document_html`: trusted demo HTML for the static prototype.
- `receipt`: receipt object.
- `authority`: authority object.
- `chat_messages`: ordered chat message objects.
- `history_events`: ordered history event objects.

Attempts are selected render states for the prototype. Real app work should eventually store safer structured document blocks instead of arbitrary HTML.

## Receipt

Required fields:

- `id`
- `status_label`
- `status_class`
- `sources_used`
- `created`
- `external_writes`
- `not_done`
- `undo`

The receipt is human-facing trust evidence. It explains what the Palari used, created, did not do, whether anything external changed, and how to undo where applicable.

## Authority

Required fields:

- `requirement`
- `summary`
- `approvals`: ordered approval rows.

Approval row fields:

- `human_id`
- `role`
- `status_label`
- `status_class`

Authority models human review/approval state. It must not imply autonomous approval.

## Chat Message

Required fields:

- `id`
- `speaker_kind`: `human` or `palari`.
- `speaker_id`: id in `humans` or `palaris`.
- `time`
- `text`

Chat messages provide conversational context for the selected work item.

## History Event

Required fields:

- `id`
- `time`
- `text`
- `badge`

History events are human-readable timeline records for work item state.

## UI Defaults

Required fields:

- `default_source_id`
- `default_work_item_id`
- `mobile_breakpoint`

The UI block is prototype configuration. It should not become product state.

## Current Limits

- The prototype is static and read-only.
- No provider access occurs.
- No live document provider, backend service, persistence, or mutation is connected.
- `document_html` is trusted demo content only.
- The contract is not yet the canonical workspace schema.

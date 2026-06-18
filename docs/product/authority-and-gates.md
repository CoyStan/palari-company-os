# Authority And Gates

Palari Company OS separates capability from authority.

AI workers can prepare, inspect, draft, summarize, test, and recommend. Humans
or organizations hold authority for acceptance, deployment, policy activation,
broker side effects, spending, credential use, and other high-impact actions.

## Human Authority

Human profiles should identify:

- identity and aliases
- role
- ownership areas
- approval capabilities
- availability or capacity signals

For high-risk work, quorum can require more than one qualified human. The
system should fail closed when authority is unclear.

## AI Roles

AI roles describe capability and bounds, not final authority. A Palari can ask a
model or tool to perform bounded work, but the Palari cannot convert that work
into an authority-bearing decision without the required human action.

## Gate And Key Custody

Gate keys are authority-bearing infrastructure, not convenience tokens.

Default stance:

- raw keys must not be exposed to AI models or chat context
- humans or organizations own custody
- AI workers can request bounded signing operations only through explicit tools
- rotation, revocation, auditability, and recovery matter for team use
- signed gates supplement human acceptance and quorum; they do not replace them

Complex key custody is intentionally out of scope for the first repo slice, but
the model leaves room for it.


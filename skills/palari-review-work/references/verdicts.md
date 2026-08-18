# Review verdicts

Use the narrowest verdict supported by the inspected packet and current proof.
Palari's emitted commands remain authoritative.

| Verdict | Use when | Required report |
| --- | --- | --- |
| `accept-ready` | No material finding remains; scope and acceptance are satisfied, exact-head evidence is current, and the receipt is accurate. | Say `No findings.` and name any residual risk without turning the verdict into approval. |
| `changes-requested` | Current exact-head proof is reviewable, but a correctable product defect, scope mismatch, inadequate check coverage, or inaccurate receipt prevents acceptance. | List actionable findings in severity order with exact locations, impact, and smallest correction. |
| `needs-human-decision` | Evidence cannot resolve a real product, policy, risk, or authority choice reserved for a human. | State the decision needed and the competing consequences without choosing for the human. |
| `blocked` | The exact packet, candidate, required proof, source, or reviewer authority is missing, stale, head-mismatched, inaccessible, invalid, or contradictory, so judgment cannot be completed. | State the blocking fact and the next safe owner action. |

Do not use `blocked` for an ordinary defect that supports
`changes-requested`. Do not use `needs-human-decision` to avoid making a
technical judgment. Stale required proof is always `blocked`. One material
finding is enough to reject `accept-ready`.

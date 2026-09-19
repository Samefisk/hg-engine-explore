# Reviewed runtime test supersession

The canonical validator is `validate_runtime_migration` in `../validation.py`.
Schema version 1 keeps existing `pending` and `ported` records unchanged.
No historical requirement, claim, measurement digest or scenario is deleted.

A reviewed replacement uses `status: "superseded"`, an empty `tests` list,
and this extra `review` object:

```json
{
  "reviewer": "named reviewer",
  "reviewedAt": "2026-09-09",
  "reason": "The replacement covers the same requirement with less setup.",
  "coverage": [{
    "claim": "logical-commit",
    "measurement": "old-commit-count",
    "replacementRequirement": "legacy.replacement",
    "replacementClaim": "logical-commit",
    "replacementMeasurement": "replacement-commit-count",
    "reason": "The same two-commit check is part of the replacement test."
  }]
}
```

Every old measurement needs exactly one mapping. A mapping must name a known
requirement of the same verification kind and the same claim. Only the metric
name can differ: its type, validator, operator, bound and other constraints
must match. A contract change is a separate review, not test retirement.

Replacement chains must have no cycles. Each leaf must be `ported` and name
registered shared tests for its claims. Unknown targets, uncovered behavior,
pending replacements and incomplete reviews fail validation. Dates use
`YYYY-MM-DD` and cannot be in the future.

`resolve_runtime_migration_targets(document, requirement)` returns sorted leaf
requirement IDs after validation. This resolves coverage, not acceptance. The
controller must still check current evidence for those replacement requirements.
A supersession review cannot dismiss a runtime failure or turn an old result
into current proof. Do not change a current record without reviewed evidence.

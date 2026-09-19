# Overworld verification map

Use this index to choose only the recipe matching the requested behavior.
The machine-readable capability map is `tools/overworld/system_features.yaml`;
the current scenario catalog is `scripts/owctl scenario list`.

Use [verify-overworld](../SKILL.md#run-an-existing-test) for preflight,
registered execution, acceptance and reporting. Recipes add feature-specific
subjects, fixtures, triggers and measurements. They do not replace that run
path or require running every scenario they list.

## Features

- [Profiles and follower selection](profiles-and-selection.md)
- [Movement primitives](movement-primitives.md)
- [Named live actor behavior](named-actor-behavior.md)
- [Mounted movement](mounted-movement.md)
- [World and population](world-and-population.md)
- [Runtime proof gate](runtime-proof-gate.md)

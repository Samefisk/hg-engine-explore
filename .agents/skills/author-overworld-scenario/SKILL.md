---
name: author-overworld-scenario
description: Create or change a permanent hg-engine overworld test, including promoting memory data and adding missing observations. Register its exact claims for verify-overworld acceptance.
---

# Create or change an overworld test

Use this skill only when the existing test is missing or insufficient.
Running an unchanged registered test belongs to
[verify-overworld](../verify-overworld/SKILL.md).

## Define the claim

Check `scripts/owctl scenario list` and the matching
[feature recipe](../verify-overworld/features/README.md#features).
Reuse sufficient coverage. Before new measurement code, read
[test design](../../../documentation/overworld-system/verification.md#design-the-test-before-the-run)
and [scenario measurements](../verify-overworld/references/scenario-measurement.md).
They own expectation sources, exact subjects, setup labels, negative controls,
native ABI anchors and invalid-result rules.

Name the expected behavior, actor role and identity, starting profile, trigger,
observable, forbidden result, limits and cleanup. For live discovery or setup,
use [overworld-devtools](../overworld-devtools/SKILL.md).
For a runtime fix, follow [reproduction and acceptance](../../../documentation/overworld-system/verification.md#reproduction-before-editing-acceptance-before-closure):
a measured reproduction can support the product edit before permanent test
registration, but acceptance and durable coverage are required before closure.

## Implement and register

- Write the typed recipe using [test authoring](../../../documentation/overworld-system/devtools-tests.md#author-an-executable-test)
  and its matching measurement subsection. Read
  [setup and test selection](../../../documentation/overworld-system/devtools-tests.md#select-tests-and-setup)
  before a run. Prepared fixture data must not replace the normal trigger under test.
- Connect the recipe, scenario, capability and exact measurements through
  [scenario registration](../../../documentation/overworld-system/devtools-tests.md#register-an-acceptance-scenario).
  A draft, planned contract or direct recipe pass does not grant accepted proof.
- For spawn-work pacing, strengthen or use
  `population.spawn-work-budget`. Cover the actual legacy Pool and profile
  destination-mask paths. Bind candidate queries to completed game updates and
  reject more than 16 queries in one update. Also require exactly one profile, metadata,
  and class preparation for the complete automatic attempt; resumed scan updates
  must reuse it. Add a copied control that repeats preparation and verify that it
  fails for that reason. Measure resumed finalizer guest work and add a copied
  over-budget control. Keep the short current-ROM gate separate from the long
  intermittent cadence run. Register spawn, population, behavior profile,
  destination-mask and generated-profile inputs so they stale proof.
- If readers or checkers need changes, follow the
  [outcome-first loop](../../../documentation/overworld-system/devtools-tests.md#outcome-first-tool-work)
  and [retained proof recheck](../../../documentation/overworld-system/devtools-tests.md#recheck-retained-proof).
  Reuse shared observations. Changed live readers or missing native data need
  a fresh run; copied-data controls do not prove the live recorder.
  The spawn-budget checker must reject a known-bad 17-query batch and repeated-
  preparation inputs for their intended budget reasons.
- If retiring duplicate requirements, use
  [reviewed requirement replacement](../../../documentation/overworld-system/verification.md#reviewed-requirement-replacement).

## Accept and retain

Use [verify-overworld](../verify-overworld/SKILL.md) for the registered run.
Keep the scenario, measurements and reusable recipe in source; ignored run
artifacts alone are not a permanent regression test. Update the owning feature
recipe when coverage changes and use [handoff rules](../../../documentation/overworld-system/verification.md#progress-and-handoffs)
for the current result and next action. Keep required evidence under
[storage rules](../../../documentation/overworld-system/devtools-tests.md#storage-rules).

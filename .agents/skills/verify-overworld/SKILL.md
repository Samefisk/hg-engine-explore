---
name: verify-overworld
description: Run registered hg-engine overworld tests and check accepted proof. Use for requested verification or before claiming an overworld runtime bug is fixed.
---

# Verify the overworld system

## Choose the task

- **Run an existing test:** follow the path below. No test-authoring guide is
  required for an unchanged scenario.
- **Diagnose or preserve a reproduction:** use
  [overworld-devtools](../overworld-devtools/SKILL.md). For a runtime fix, read
  [reproduction and acceptance](../../../documentation/overworld-system/verification.md#reproduction-before-editing-acceptance-before-closure)
  before the product edit.
- **Create or repair a test:** use
  [author-overworld-scenario](../author-overworld-scenario/SKILL.md).
- **Recheck a checker-only change:** use
  [retained proof recheck](../../../documentation/overworld-system/devtools-tests.md#recheck-retained-proof)
  before another boot. A changed live reader or missing native data still needs
  a fresh run.

## Run an existing test

1. Select the exact requirement, actor role and scenario using
   `scripts/owctl scenario list`, `tools/overworld/system_features.yaml`, and
   only the matching [feature recipe](features/README.md#features).
   Apply [test selection and setup](../../../documentation/overworld-system/devtools-tests.md#select-tests-and-setup).
   Reuse a sufficient current result only under the controller's input checks.
   For spawn-work pacing, any spawn, population, behavior-profile,
   destination-mask or generated-profile change makes the older result stale.
   Run both extracted-C budget checks first, including the known-bad batching
   control, then use `population.spawn-work-budget` on the current ROM. Require
   exactly one profile/metadata/class preparation for the whole automatic
   attempt. Require the repeated-preparation and slow-resumed-finalizer controls
   to fail. The current cap is16 candidate queries per update; the full explicit
   scan must still preserve all240 queries across15 resumed batches. That cap
   alone cannot pass. A population count or legacy-helper-only pass cannot close D1. Run
   `world.unmounted.spawn-zero-stutter` from its unchanged Continue save and
   existing Mankey for the player-visible gate. Zero late loops is the only
   pass. Do not substitute prepared party, follower, spawn, or population
   state. If the user still reports the hitch on that exact `test.nds`, keep D1
   open even when both tool gates pass.
2. Read [run and stop](../../../documentation/overworld-system/devtools-tests.md#run-and-stop)
   for ownership, preflight, registered execution, progress and interruption
   cleanup. Both `scripts/owctl doctor` and `scripts/owctl scenario validate`
   must pass before the live run. Use melonDS through the shared service.
3. Start `scripts/owctl scenario run <id> --json`. Inspect
   `scripts/owctl dev test status --json --summary` for progress, then read the
   returned terminal manifest under [acceptance](../../../documentation/overworld-system/devtools-tests.md#accept-a-registered-result).
   Require both `passed: true` and controller-owned `acceptedProof: true`
   for the exact requirement. A start receipt or evaluator pass is not proof.
4. Retain the failed and passed evidence and report the scenario/run IDs,
   manifest path, tested ROM/save identity, measured subject, result and any
   exact proof gap. Follow [storage rules](../../../documentation/overworld-system/devtools-tests.md#storage-rules)
   and [handoff rules](../../../documentation/overworld-system/verification.md#progress-and-handoffs)
   when cleaning up or updating current work.

## Read extra rules only when they apply

- Intermittent report: [repeat coverage](../../../documentation/overworld-system/verification.md#intermittent-reports).
- Failed run: [failure records](../../../documentation/overworld-system/verification.md#failure-records).
  Stop at the failed layer and preserve its evidence; a later pass cannot
  dismiss an unresolved runtime failure.
- Rejected measurement or observer fault: [measurement rules](references/scenario-measurement.md).
- Slice integration or roadmap completion: [verification checkpoints](../../../documentation/overworld-system/verification.md#verification-cost-and-checkpoints)
  and [affected verification](../../../documentation/overworld-system/verification.md#affected-verification).
  The full roadmap gate belongs at completion, not every patch.

Source checks and documentation edits do not prove game behavior. Screenshots
are never an agent test step or gameplay proof.

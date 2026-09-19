# Scenario measurements and invalid results

Read when authoring or changing a scenario adapter, or diagnosing a rejected proof. These measurement constraints apply to all actor roles. Use the [acceptance rule](../../../../documentation/overworld-system/devtools-tests.md#accept-a-registered-result) for result acceptance and the [repository policy](../../../../AGENTS.md#build-and-test-requests) for execution authorization.

## Sampling constraints

1. Release held input at a semantic boundary, such as a counted engine step,
    not after a delayed coordinate poll. Assert that the number of engine step
    callbacks equals the number of authored motions.
2. If two hooks observe the same motion at elapsed frame zero, deduplicate
    only an exact match of actor, start tile, target tile, and elapsed frame.
    Never discard samples only because they are close in time.
3. A native video cycle is not a complete game update. Stock `main.c` can
    wait for two VBlanks per main-loop update. A video cycle can also end
    between the actor tick and the map-object task that applies its pose.
    Sample actor state and rendered position together after the main task
    queue returns. Authenticate that hook against the packaged ARM9 with
    `stock-main-queue-observation`; a missing hook fails the recorder.
    Keep every native-cycle timing record separately. Do not relax a motion
    check or discard duplicate clocks to hide a partial update. Name the
    clock unit in frame budgets and receipts; add controls for both a split
    update and a real missed completed update.
4. For normal player setup, use a bounded shared-tool input action with a typed
    completion predicate. Stock FACE commands 0–3 can be idle; command 255 alone
    is not the idle test. A reserved logical target is not completion: the
    previous tile, exact rendered tile center, and command-ready flags must
    agree. Prove a setup route through live input. A static clear tile does
    not account for another object's current or previous position.

## Test the observation path

- Define the expected result from the user contract or a verified reference,
  then test the exact production boundary and caller. A portable reducer can
  pass while its caller packs, drops, or misreads the result.
- Keep normal play separate from forced retries and injected state. Record all
  interventions and when they stop. The normal-play measurement window must
  use the actual resolved profile and normal timers.
- A missing/wrong starting species or role fails setup before motion
  measurement. When spawning is the behavior under test, failure to create the
  actor after the trigger is a behavior failure. Reaching the end of the script
  without the subject never passes.
- Evaluator controls mutate copied data. Recorder controls present known-bad
  behavior to the same recorder. Preserve both labels; one cannot stand in for
  the other. Add a focused recorder control when its sampling code changes.
- Use one bounded real symptom for the regression witness. Added edge-case
  tests can complement it but cannot replace it.

## Common invalid results

- The expected species was written into a test buffer, but no matching live
  actor existed.
- The runner exited zero, but `owctl` did not issue the proof session.
- The result used the right claim name with the wrong measurement.
- A different scenario in the same capability ran the wrong runtime adapter.
- The required behavior still passed after its semantic event was removed.
- The ROM matched an old build or the current Make target was stale.
- A screenshot, fresh or old, was used to judge any test claim instead of
  checked native observations. See [memory-backed proof](../../../../documentation/overworld-system/verification.md#memory-backed-proof).
- A soak declared 5000 frames but observed fewer frames.
- A soak reached its floor by adding frames from separate emulator boots.
- An intermittent check passed once after earlier failures.
- Input stayed held past the intended semantic motion count and started an
  extra move before the coordinate observer released it.
- A source or ABI check was reported as movement feel or control proof.
- A forced chain and cleared cooldown were reported as normal chain timing.
- A mounted run was used to close an unmounted or whole-engine stutter report.
- A later run overwrote the evidence file used to accept an earlier run.
- An intermediate host/link report was copied into the current ledger as a
  packaged-ROM pass.

# Runtime proof gate

The proof gate ensures that a future agent cannot mark gameplay correct from a
direct script exit, dummy evidence, stale files, too few frames, or the wrong
Pokemon.

## Sub-features

- `current-session` requires an `owctl`-issued proof session.
- `exact-measurements` binds every runner to exact names, operators, and value shapes.
- `native-presentation` requires checked current render/timing/effect observations;
  screenshots cannot supply missing proof or affect acceptance.
- `measured-soak` rejects an S5 run below its real frame floor and rejects a
  floor assembled from separate emulator sessions.
- `named-identity` rejects a species-specific run without full live identity.
- `fixture-identity` rejects a stale Make target, sealed manifest, packaged
  overlay, ROM, or debug descriptor before emulation.
- `evaluator-controls` remove the named subject and one required semantic
  event from copied evidence; both mutations must make the controller reject
  the run. These are not live recorder controls.
- `recorder-controls` pass known-bad behavior through a new or changed recorder
  and require detection. Run `observation.live-actor-and-motion-control` for
  Ledyba identity/render faults and `observation.live-route-control` for route
  render/CPU faults. Require both current receipts. Each starts one emulator
  process; do not recreate the native core inside a process or combine frames.
- `immutable-evidence` keeps each run's files independent of later runs.
- `content-identity` invalidates relevant input changes without treating notes
  or content-preserving commits as gameplay edits.
- `exact-coverage` requires each affected runtime check to execute its own
  registered scenario runner.
- `roadmap-exit` audits the complete catalog. It rejects planned scenarios,
  missing exact runner coverage, every missing exact `minimumProof` level, and
  actor-scoped S3-S5 adapters that do not use structured actor observation.
- `final-fixture` records and checks the final ROM, sealed build manifest,
  debug descriptor, and actor overlay identity without starting an emulator.

## How to get to it (user POV)

- Run an overworld scenario through `scripts/owctl`.
- Read its accepted run manifest.

## Driving it with owctl

Preconditions:

- The repository Python environment is available.
- Runtime scenario contracts and the proof registry are present.

- **Validate contracts.** Run `scripts/owctl scenario validate`. All scenarios, claims, native measurement contracts, and S5 frame floors validate.
- **Run host gate tests.** Run `python3 scripts/verify_overworld_proof_gate.py`. Tests reject direct runner proof, dummy equality, incomplete actor identity, unrelated scenario coverage, missing native presentation observations, declared-only soak frames, and soak time added across fresh emulator boots. Screenshots cannot change acceptance.
- **Run the roadmap exit gate.** Run `scripts/owctl verify roadmap --json`.
  It is green only when the complete proof catalog and final runtime fixture
  are ready. It does not run gameplay scenarios.
- **Run one live actor case.** Run `scripts/owctl scenario run chain.pause.counts-semantic-moves --json`. This exercises current Ledyba identity and controlled retry measurements in one accepted session; it is not normal chain timing proof.
- **Run one live presentation case.** Run `scripts/owctl scenario run mount.movement.frame-pacing --json` only when its shared-tool port is executable. Require native pose and frame-timing measurements, not a screenshot.
- **Inspect.** Open both returned manifests. Each starts with a successful
  runtime-fixture identity step and records the current proof session, observed
  frames, iteration results, exact registered evidence, and negative controls.
- **Proof.** The test system is healthy only when the host rejection tests and both live cases pass. A product failure remains a valid red result; it must not be reclassified as a proof-system failure.

## Gotchas

- `passed: true` inside runner JSON is not enough.
- A correct claim key with an unregistered measurement is rejected.
- Direct runner diagnostics intentionally exit nonzero as accepted proof.
- A named mounted soak uses a structured subject, full live identity, and the
  same absent-subject negative control as a named wild Pokemon test.
- A related scenario cannot cover a runtime check unless it runs that check's
  exact registered runner.
- One S5 receipt is one continuous emulator session. Repeated full soaks are
  separate accepted runs; short sessions cannot be summed.
- The gate must preserve a real red product result. It must not turn every run green.
- `scripts/owctl progress --json` summarizes recorded results only. It is not
  a replacement for the host checks, live cases, or final roadmap gate.

# Workflow checkpoint — 2026-09-09

Scope: the six approved fixes from the roadmap speed review. No game code,
ROM, save, build, emulator session, commit or push changed during this work.
Branch: `feature/overworld-actor-system-roadmap`. Existing dirty work preserved.

## Delivered

- D1 unmounted stutter is next; Crash stays paused. Missing old D1 and Ledyba
  manifests are labelled historical, not reusable proof.
- The three project skills and AGENTS route to the outcome-first work loop:
  one real memory sample, shared measurements, bounded tool task, game return point.
- One explicit adapter table replaces duplicated Corner/Matrix/Stomp dispatch.
- New preflights bind capture and checker inputs separately. Exact saved-run
  recheck needs no boot or evidence rewrite. Old manifests keep strict identity.
- Content-bound, bounded in-memory acceptance reuse and requirement-indexed
  recorder lookup avoid repeated replay and unrelated control searches.
  Final source checks precede cache publication; stale loaded code is rejected.
- Reviewed supersession maps every old measurement to an equal replacement.
  Final coverage needs all current replacement proofs. No requirement was retired
  just to clear a failure; no current migration record was changed to superseded.

## Checks actually run

- 83 focused host tests passed in 7.251s: input identities, cache rejection and
  publication, shared adapters, supersession/coverage, history, claims, retirement,
  and real HTTP source-change guards. Includes recheck manifest immutability.
- 25 movement-checker tests passed in 24.098s. Includes replay of saved matrix
  `test-32c9c4d92ffd42408c2585939a75c740` and all 17 required copied-data faults.
  This checks tool changes, not new game behavior.
- All 52 scenario contracts validated. Three project skill validators passed.
- Devtools-only guard passed (581 files); changed links and diff whitespace passed.
- Real input-scan experiment: compact scope 4,592 bytes; cold 8.36s, warm 3.18s.
  These are scan costs, not a claimed gameplay or whole-suite speedup.

The permanent host gate includes the new tests. Source tests define the exact
cases; do not copy their assertions into this archive.

Next: follow the [resume page](roadmap-progress.md), inspect the existing bounded
unmounted cadence-prefix recipe, and capture the missing native timing sample.
Do not repeat the old six-reader omission experiment by default.

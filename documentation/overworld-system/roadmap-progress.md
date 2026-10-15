# Overworld Roadmap — Current State

## Read this first

- [Roadmap](roadmap.md): scope and completion rules.
- This page owns resume state. Replace stale state; do not append run reports.
- Manifests own proof. Changed product, reader or recipe inputs can make older results stale.
- [History archive](roadmap-progress-archive-2026-10-04.md): prior HP delivery records and the ROM3500 ledger. Old branch names, candidate identities and next actions there are history.
- Earlier indexes: [September 7](roadmap-progress-archive-2026-09-07.md), [Walk/September 8](roadmap-progress-archive-2026-09-08-walk.md), [timing matrix/September 9](roadmap-progress-archive-2026-09-09-matrix.md), [stomp/September 9](roadmap-progress-archive-2026-09-09-stomp.md), and [crash/September 9](roadmap-progress-archive-2026-09-09-crash.md).
- Missing evidence reopens its requirement. Some old artifacts were deleted.

## Current work table

Checkpoint: 2026-10-09. The active checkout is `main` at this repo root.
The former Player HP worktree path resolves to this same checkout.
ROM3560 is the latest Workshop build and matching Delta copy. The original
Continue save is unchanged and build-open stays off. No branch, worktree,
commit, merge or push was created.

TKT-0053 restores the checked Route29/30/31/46 encounter tables and normal
Headbutt pools, removes their test overrides, and adds Violet Pidgey by day
and a Hoothoot99%/Rowlet1% night table. Existing spawn settings and random-walking
encounter disable remain unchanged. Source/table/native resolver checks pass.
The user owns the opening-route playtest and current-ROM pacing checks;
those checks have not run and TKT-0053 remains open for that proof.

TKT-0054 adds visible Skittish fear of other Pokémon for wild babies and a
separate Seek safety response for baby followers. Both use the existing Baby
Pokémon pool and visible Current Vision/100%/960-duration/970-cooldown settings.
Follower safety uses shared Walk toward the actual Player at travel time at
most4. Basic attack remains disabled, now also through an explicit application
Enabled switch. Existing player/pickup fear and unrelated authored fields stay
unchanged. TKT-0054 is done. Three final-input, current-ROM cases are accepted:

- `wild.baby-player-fear`: `test-2b0a6c5823a3416ea4647b29868b6b44`,41 observed frames. Cleffa retains the real Player source and completes a16-frame Walk away with commit and control return.
- `wild.baby-pokemon-fear`: `test-0950c351c60449429e1a65a81939f4f2`,39 observed frames. Cleffa captures the exact current Cyndaquil source and completes the same native flee response.
- `follower.baby-seek-safety`: `test-f0b6e7002bd44f3cbc6b9c3e9a44d0fc`,32 observed frames. Cleffa keeps its follower role, captures the current threat and completes a4-frame Walk toward the actual Player and away from that threat.

All three controller `acceptedProof` values are true. Their private sessions
closed without errors. These prepared cases prove one completed response each;
they do not claim the full timed expiration or opening-route pacing.
Retained failures showed the saved Mankey selection surviving a slot0 edit,
a follower blocking the initial test approach, a checker requiring truth
through a valid timed hold, and an incorrect expected follower spawn tile.
The public follower setup, short clear approach and timed-hold check are now
correct. The final cases use the same frozen source inputs. Earlier wild
passes were repeated after the final shared fixture edit because independent
retained rechecks rejected changed capture inputs; no proof was weakened.

The [final acceptance receipt](../../build/tickets/tkt54/final-3560-acceptance.json)
binds all three accepted manifests, matching workspace/Delta copies, original
save, frozen inputs and scoped source/host/native checks.
The prior ROM3559 ticket acceptance remains scoped to its recorded inputs;
its pacing passes do not apply to the changed current catalog. The hours-long
unattended lock and broader roadmap/Player HP acceptance remain open.
Scope and exit criteria live in the [finite slices](roadmap.md#finite-delivery-slices).

| Slice | Owner | State | Evidence / remaining work | Next action |
| --- | --- | --- | --- | --- |
| D0 — proof workflow | root | verified | Shared checked jobs, retained evidence, failure records and proof-input identity are in place | Reopen for a concrete tool fault |
| D1 — reported faults | root | active | TKT-0076 (2026-10-11): the Route 30 population lag was reproduced beside the pond (6 late loops in 955 on ROM3583, idle minimum 14k ticks) and traced to three measured costs (O(N²) map-object lookups in contact validity, repeated failed idle searches, a new actor's first tick stacked on its creation update); ROM3588 has 0 late loops and idle minimum 159k on the same walk (diagnostic recordings, not accepted proof). `population.route30.saturated-headroom` is the permanent gate; its accepted run is recorded in the TKT-0076 notes. ROM3559 short spawn and unchanged-save zero-stutter proofs are historical after encounter/catalog changes. Current extracted-C scan/refill budget checks pass. The user owns ROM3560 pacing checks under TKT-0053; no current-ROM game pacing claim is made. The hours-long unattended lock remains unproved | Wait for the user route/pacing result; keep D1 open |
| D2 — schema/resolver/facade | root | source-ready | Resolver, condition, controller, ABI and package check records exist; no whole-slice closure is recorded | Run only the affected roadmap gate after the user check |
| D3 — Walk/chains/roles/Ram | root | source-ready | ROM3547 accepts a brief sight while both actors move, delayed legal intent with the captured heading, acceleration, heading lock and Crash. The Ram-behind proof remains scoped to ROM3545. ROM3534 follower Ram accepts current target capture, first charge heading, real33HP damage, shared Jump3 landing and unchanged player/party HP. Prior Ram/ledge and mounted Linear evidence belongs to ROM3509 | User bird/Rattata timing and live lone-PAUSE chance below 100% remain unproved; recheck changed inputs before reusing scoped proof |
| D4 — Hop/Teleport/mount | root | active | ROM3481 contact/movement receipt is historical. Wild NPC chain-start, Pokémon-midpoint and long detach stress remain unaccepted | Keep user ride/rooftop checks and required missing Hop proof open |
| D5 — world/transition/population | root | source-ready | ROM3500 pacing records are historical. Scoped surface-height results belong to their ticket receipts | Recheck affected current inputs; pacing alone does not close this slice |
| D6 — remove old paths | root | source-ready | Active, attentive and the condition shadow bridge are removed; deletion/build check records are retained | Preserve through the affected roadmap gate |
| D7 — final acceptance | root | active | ROM3560 is built and copied to Delta with the original Continue save unchanged. TKT-0054 is done with three final-input accepted baby fear/Seek safety cases; all private sessions closed. TKT-0053 source/build work is ready for user route and pacing checks. Earlier45 completed tickets keep their scoped evidence | User owns TKT-0053 game proof; broader roadmap and Player HP acceptance stay open |
| Player HP — separate feature | root | active | HP/contact/shared knockback sources are integrated in this checkout on main. The stable contract and source routes are in the player HP plan. Broader healing/zero-HP/battle/capture/ordinary-Hop acceptance remains open | Keep ticket acceptance separate from broader HP gaps and the user's final display/sound check |

States: queued, active, paused, source-ready, open, verified, blocked.
Verified means the whole slice has current evidence; source-ready does not.

## Prior completed ticket batch — ROM3559

ROM3559 was the prior recorded build and matching Delta copy. Its45-ticket batch was complete. Wild Throw can select a nearer reachable cargo during pursuit, release only its prior claim, and finish accepted movement before following the new target. Distance means Chebyshev distance to a native-proved legal pickup standing tile. The profile exposes a12-frame target check interval and an initial1-tile switch advantage. HELD cargo and follower target selection retain their existing flow. Target selection no longer excludes the requested actor states or follower role. Physical pickup still has one carrier; an unheld pursuit claim does not reserve ownership, and ordinary abort preserves incoming claims.

The final ROM accepts Wild retarget for57 observations and reciprocal pickup for118 observations. Its short spawn-work run has468 observations, one profile/metadata/class preparation,240 queries over31 updates, and maximum resumed finalizer28379 ARM9 ticks. The unchanged-Continue run uses the save's existing Mankey with no prepared party, follower or population changes. It has2745 measured frames,1935 moving frames, zero late loops and zero render stalls. Random behavior Hop now chooses the first legal endpoint in a bounded shuffled list; open terrain needs one landing validation. The authored vector rules, uniform legal choice, Walk history tiers and fresh START checks remain intact. Its durable actual-C checks pass.

The [final acceptance receipt](../../build/tickets/tkt52-pickup/final-3559-acceptance.json)
links all four accepted current-ROM manifests, the matching ROM/save/source
hashes, focused host checks and the scoped prior follower evidence. The
ROM3558 three-cycle Hoothoot Hop failure remains retained; the same unchanged
route now passes on ROM3559. Earlier full repeated-Throw, follower, access,
Notice/Walk, Ram and Basic attack records keep their recorded scope. Basic
attack remains disabled. The original hours-long unattended lock was not
reproduced. Broader roadmap and Player HP acceptance remain open. The
Continue save is unchanged and build-open stays off. All four private test
sessions closed without errors. No branch, worktree, commit, merge or push
was created.

## Prior moving conditions and Throw work — ROM3547

The retained ROM3545 failures show Mankey losing a captured damage source
after the alert and wild Geodude losing moving Cargo before its query resumed.
The brief Onix trace shows Player entering the authored line while Onix's
ordinary Walk was still active, then leaving before that move ended. The new
shared moving path admits all condition kinds without replacing that Walk.
Pending presentation and timed endings survive until a legal intent.

ROM3547 also consumes a queued startup marker before its terminal startup
step. A refused entry origin cancels that attempt. Before the fix, the native
trace repeats the same refused attempt and resolves its profile again at
frames1003 and1004. The extracted production-C check preserves that RED case
and passes with retirement; all23 queued, scan and refill checks pass. The
full native Wild link fits its unchanged cap, and the Workshop build passes.

The ROM3547 short spawn-work run
`test-1dadab6d21fb4e0a8bf5685e4e764eb3` has272 observations, one preparation,
240 destination queries and bounded resumed work. Its original acceptance
failure was a copied-control event stamp error. The public retained recheck
accepts the same saved game data after that pure checker repair.
The ROM3547 unchanged-save walking run
`test-f538a15369c0450eb6e24a5deaba2dd7` stops after2413 observations at frame3401.
It completed one requested game update in three native cycles; this is a real
pacing miss, not a duplicate observation. No spawn work ran on the measured
queue frame. Global archive, model and population call counts also remain flat.
Six actors were active, including a Hop and Fly In. The exact guest cost owner
is unproved; use the existing CPU counter around that route segment before
changing a product owner. A later pass cannot erase this unresolved RED. Its closed private session and failed evidence are retained.

The four ROM3547 registered attack runs are accepted:

- `follower.throw-player-damage`: `test-0925ea54c08042028f57aa7b547714a0`,204 observations. A real player hit while the follower moves captures the exact source, then pickup, away Throw, landing and normal Follow complete.
- `wild.throw-moving-candidate`: `test-99472abc8c0444d1a623e8c0ff00483b`,79 observations. Geodude retains the authored alert, chases moving Snorlax and launches that same current actor.
- `profile.ram.brief-notice`: `test-f550f7d340a14890b20313c435294331`,45 observations. The condition admits during the accepted ordinary Walk; the plan and token stay intact. The sight survives Player leaving the line, and the next intent charges East without extra delay.
- `profile.ram.until-crash`: `test-afe00a455ede450997d8dde61b3ce225`,159 observations. Sixteen complete charge moves retain direction and speed, survive the old96-frame expiry, then end at real Crash with100-frame cooldown.

All four private sessions closed without errors. ROM3547 workspace and Delta
copies match SHA256 `f04efaeb4ff39847ac8f0f19d6a8ae03bc5938d872fff4a94589964986d6ac90`.
The unchanged Continue save keeps SHA256
`65c36abc15d442141a33cdffd682868514db6093890cb958964dd732a846eefb`.
Build-open stays off. No branch, worktree, commit, merge or push was created.
These scoped results do not close the failed D1 walking gate, the original
hours-long ground lock or broader Player HP acceptance.

## Prior Basic attack disable and Ram-facing proof — ROM3545

Basic attack is off at the user's request. Only its condition chance changes
100→0; stable IDs, application order, all-species membership and behavior fields
remain intact. The real-C host check proves no activation and release of a prior
while-true activation. Its prior behavior checks use an explicitly enabled
disposable catalog; they do not claim that the shipping catalog enables it.

Both Ram conditions already ignore facing through their Custom Vision
cardinal-lines rule. Source inspection and the shared C Vision truth table
cover all four facings. No Ram runtime or condition edit is needed.
The [actual C before/after case](../../build/basic-attack/disable-ram-facing/ram-basic-override-host-before-after.json)
shows the composition clash: with Player behind Onix and Geodude adjacent,
both Ram and Basic attack were active and Basic attack selected Geodude.
With Basic attack off, Ram alone captures Player.
The accepted current
[Ram-behind run](../../build/overworld-devtools/test-218a2718479641379c7b36df2c3ebfa1/manifest.json)
retains current idle Onix594404 facing South and Player594399 at frame829.
At830 its natural condition admits North Walk, and the charge keeps North
through Crash at918. It has149 observed frames and full controller acceptance.
The accepted
[short spawn-work run](../../build/overworld-devtools/test-b8882903dadd425c9d3c7358b2343488/manifest.json)
retains one profile/metadata/class preparation,240 candidate queries, at most12
per update, and bounded resumed finalizer work in275 observations.
The accepted unchanged-save
[pacing run](../../build/overworld-devtools/test-d2aa79b63f954f2d8936eb9736f0d4b5/manifest.json)
has2648 observations and1935 moving frames, with zero late loops or render
stalls. It keeps the existing Mankey and makes no party, follower, spawn,
population or healing preparation. All three private sessions are closed.
The [current result receipt](../../build/basic-attack/disable-ram-facing/final-result.json)
binds the source change, host checks, accepted game manifests and matching
workspace/Delta ROM copies. ROM3545 SHA256 is
`2f40c76ce2fec6905af5f458eb98d8c287b9b4a66ba080c5a423e347253da20a`.
The Continue save remains unchanged; build-open remains off. No branch,
worktree, commit, merge or push was created.

### Prior enabled Basic attack — ROM3544

`Basic attack` applies to all1393 numeric species/form IDs. A Pokémon on the
same tile as, or next to, another Pokémon captures it as its Object of interest,
then uses normal Chase/Hop to reach that actor's current tile. Hop time is
inherited unchanged; the `/2` operator is removed. Attacking is enabled with
minimum impact speed1 and damage20; knockback remains inherited.
Face movement is enabled on both legs. The new generic `Return after move`
profile checkbox is enabled for Basic attack: accepted ordinary Walk/Hop
captures its start and returns with the same time and style through Actor
Motion. No second movement engine is added.

The inverse move starts without the outward chain Pause. After it finishes,
the existing passive chain Pause supplies20–40 native frames (base40,
variance40, one move, no movement variance,100% Pause, zero extra Hop pause).
Terrain, current ownership, other occupants and reservations still apply.
Temporary busy results can retry on at most two distinct Actor frames; repeat
passes in one frame do not consume extra retries. A blocked return releases
control. Spawn entry, staged travel, held/Throw, forced hit and Mounted motion
do not create return pairs. Combat, field change or stale ownership cancels
the pair. Its while-true condition ends at the legal movement boundary when
no eligible target remains on the same or an adjacent tile.

Object of interest tile permits only the captured, fully current target at its
current engine tile. Cached Chase coordinates can lag accepted target movement
and no longer reject that current identity. Other blockers remain blocked.
The [retained pre-edit trace and source cause](../../build/basic-attack/return-interest-cause.json)
and production-C RED/GREEN preserve this return-landing fault and the narrow fix.

[ROM3544 build receipt](../../build/basic-attack/return-interest-build-status.json)
records a successful Workshop build. Workspace `test.nds` and Delta
`test3544.nds` have SHA256
`5548fd6edd110e21605bd7faffe6e8e505983ad1481f358664a30a5e171ced8c`.
The source Continue save remains unchanged with SHA256
`65c36abc15d442141a33cdffd682868514db6093890cb958964dd732a846eefb`.
Build-open remains off. No branch, worktree, commit, merge or push was created.

The accepted
[Basic attack run](../../build/overworld-devtools/test-d4dc7a94819a4f9cbd6aebbe17881834/manifest.json)
has150 observed frames. After declared actor setup, a current Wild Snorlax
jumps from595,396 to Cyndaquil at596,396 in four frames. Cyndaquil HP changes
79→59. The return starts on the same landing frame939, faces left, uses the
same four-frame Hop and commits the original tile at943. The next outward
Hop starts at969, after26 grounded Pause frames. Both legs have complete
airborne travel and return control. An earlier pair blocked for one frame by
a current foreign MOVING reservation is retained as diagnostic evidence;
it receives no immediate-return claim credit. Same-tile/all-direction
eligibility, condition release and inherited knockback have host proof,
not separate live claims from this run.

The accepted
[short spawn-work run](../../build/overworld-devtools/test-474a56f2911f4422bc4af46cd01e3a95/manifest.json)
retains one profile/metadata/class preparation,240 candidate queries, a maximum
of12 queries per update, and bounded resumed finalizer work in275 observations.
The current extracted-C scan/refill checks pass before the build. The strict
Query observer checks the exact current ELF/package and real ROM member;
all21 focused reader checks pass with the existing read cap unchanged.
The [current package seal receipt](../../build/basic-attack/query-interest-package-seal-proof.json)
records the changed Cargo code rather than claiming byte identity with the
prior package.

The unchanged-save
[zero-stutter run](../../build/overworld-devtools/test-0e3782a79963498eb279f33bfe46a021/manifest.json)
fails at frame1635 because the saved level3 Mankey leaves the field after its
party HP changes15→8→1→0. The run has no late loops or render stalls in647
observations, with471 moving frames, but does not complete the required2600
observations and1800 moving frames. No party, follower, spawn, population
or healing preparation was used. D1 remains open.
All three final private sessions are closed, and the source save is unchanged.
The [current result receipt](../../build/basic-attack/return-interest-final-result.json)
binds all three runs and both ROM copies. This feature proof does not close
the separate Geodude/Mankey ground-lock report or broader Player HP acceptance.

[ROM3540 contact-only results](../../build/basic-attack/contact-final-result.json)
are prior scope. Failed return runs on ROM3542/3543 remain retained with their
native observations. The prior ROM3538 zero-stutter failure and ROM3539
pause-only/canceled runs also remain historical, not current ROM3544 acceptance.

## Current Geodude ground-lock work

The requested fix stays in this checkout on `main`. No branch, worktree, commit,
merge or push was created. The original report remains open after the user's
new Geodude/follower Mankey screenshot. Two earlier product faults are fixed: an unclaimed terminal
Cargo search can no longer retain the shared workspace over a ready peer, and
successful pickup clears the target's old recovery bit with its old tired timer.
Both `RESOURCE_LIMIT` and `UNREACHABLE` have measured production-C failures and
passing fixes. Current ownership, existing claims and the per-frame work budget
remain protected.

The new ROM3537 fix checks current Cargo eligibility before waiting for the
shared workspace. An unavailable exact Interest or bound Cargo returns Invalid;
an empty unbound Wild search returns Unreachable. The existing idle abort clears
that search without touching the foreign route or taking extra native work.
Ordinary moving targets remain eligible. The new code adds no timeout or pause.

[Native ROM3536 wait](../../build/geodude-throw-lock/new-invalid-wait/native3536-unavailable-interest.json)
retains59 matching Mankey reads at frames1745–1803: current Interest is the
Geodude that already owns a pickup claim, yet the old query returns Pending.
This is a measured wait, not proof of the full permanent lock. The diagnostic
run used the unchanged Continue party and level3 Mankey; it also saw normal
movement and eventual follower fainting. The full memory log is retained.
[Production-C RED](../../build/geodude-throw-lock/new-invalid-wait/red.json) and
[GREEN](../../build/geodude-throw-lock/new-invalid-wait/green.json) cover that
unavailable exact Interest, empty Wild Cargo, valid moving targets, owned claims,
held Cargo and frame budgets. The independent source review found no blocker.
[ROM3537 identity](../../build/geodude-throw-lock/new-invalid-wait/rom3537-identity.json)
records matching workspace/Delta copies and the unchanged source save.
The first registered `follower.throw-moving-cargo` attempt
`test-6f1d16b14f134082852e9900c3fa48ce` stopped before play because its private
query reader still sealed the ROM3536 ELF. Its private session closed without
errors. The reviewed ROM3537 seal now checks the exact ELF/package, hosted Thumb
Tick extent and moved native literals; its read limit remains unchanged. All16
focused reader checks pass, including rejection of wrong code and excess reads.
The repeated registered run `test-0ce4b19b6ad4403abd634b48e4090673` has
`passed: true` and `acceptedProof: true`: Mankey picks up moving Cargo, throws
that same noticed actor away and resumes following. Its238 observed frames are
scoped regression proof, not the hours-long lock reproduction or S5 coverage.
[Final ROM3537 receipt](../../build/geodude-throw-lock/new-invalid-wait/final3537-scoped-acceptance.json)
retains the accepted manifest, matching workspace/Delta ROM identity and
unchanged Continue save. The private session is stopped and closed without errors.

[Same route after ROM3537](../../build/geodude-throw-lock/new-invalid-wait/native3537-same-route-result.json)
repeats the pre-edit Continue, teleport and five input steps without party,
spawn or healing setup. Mankey covers28 tiles over1,100 observed subject frames;
the two naturally spawned Geodudes cover41 and31 tiles. Mankey then faints and
is absent, so this does not meet the5,000-frame intermittent subject gate.
The original permanent lock and unavailable exact-Interest wait do not recur
in the retained measurement; there is no native cause verdict from this repeat.
All1,323 snapshots are retained, but the same4,000-item event ring drops older
events. This is diagnostic evidence only. Its private session is stopped, and
the source Continue save is unchanged. The full reported lock remains open.

[ROM3536 identity receipt](../../build/geodude-throw-lock/rom3536-copy-save.json)
records matching workspace/Delta copies and the unchanged Continue save.
The registered `wild.throw-ground-lock-soak` has accepted scoped proof from
run `test-b884bae183c04c49a40e40ac41cf3a75`: 5,040 continuous native frames,
14 complete primary-carrier Throws, one pickup of a recovering primary Geodude,
and all three current primary Geodudes through the full window. Player HP is 100
at both native boundaries. The private session is closed without errors.

[Final current controller decision](../../build/geodude-throw-lock/final/accepted-recheck.json)
has `passed: true` and `acceptedProof: true` for
`current.wild-throw-ground-lock-soak`. It replays the unchanged native data and
all five required copied-data controls. The original manifest remains unchanged:
its game evaluator passed, but its original replay check failed. Current
checker-only repairs cover authenticated optional Cargo distance removal,
ambient carrier ownership, dropped-cycle lifetime, and a coherent terminal-owner
fault copy. No further ROM build or game run was needed for those repairs.

The full window contains no native `RESOURCE_LIMIT`. A separate retained
[same-ROM native limit handoff](../../build/geodude-throw-lock/native3536-resource-limit.json)
proves that path; production-C failures and regressions cover both terminal
outcomes. These records do not repeat the user's full hours-long idle case.
The ROM3536 evidence is prior scoped proof, not current ROM3537 acceptance.
Broader roadmap and HP acceptance stay open; prior ROM3534 pacing results are
not fresh ROM3537 proof.

## Prior ROM3534 follower Ram work

The requested follower Ram change is complete on ROM3534. The separate Follower→Wild condition uses the shared locked charge and combat system. A moving victim finishes its current Walk before queued knockback starts; it then lands and returns control. The native follower test keeps player and party HP unchanged.

[Prior acceptance receipt](../../build/follower-ram/final/check-summary.json) binds ROM3534, its matching Delta copy, the unchanged Continue save, and all three accepted manifests: `follower.ram-pokemon`, `population.spawn-work-budget`, and `world.unmounted.spawn-zero-stutter`. Those test sessions are closed; these records do not establish fresh ROM3536 acceptance.

## Prior ROM3516 ticket batch

Use the read-only queue views instead of rereading the full ticket history:

```bash
python3 scripts/ticket.py list
python3 scripts/ticket.py show TKT-0011
```

At this checkpoint, all22 tickets are done. No open ticket remains.
[TICKETS.md](../../TICKETS.md) owns per-ticket status, checks and evidence.
The [final ticket acceptance receipt](../../build/tickets/tkt20-final/build3516-final-ticket-acceptance.json)
binds the current ROM, Delta copy, unchanged save and nine required game
records. Fresh public controller rechecks accept all nine records. The first
moving-Cargo run's failed checker manifest stays unchanged; its corrected
proof is recorded separately. A build alone cannot refresh older game proof.
Use [handoff rules](verification.md#progress-and-handoffs) for the next update.

ROM3516 includes the packed recipient override fix, same-encounter max HP
reuse, the existing refill wait, shared Cargo admission during accepted
movement, and carrier-first idle dispatch. Cargo keeps its own accepted
movement and profiles. At completed-move handoff, the carrier uses the normal
current-query and atomic pickup checks before Cargo starts its next step.
A deferred pickup permits Cargo's next normal move.

The current moving-Cargo run has342 observations: natural Mareep Walk before
Geodude, current Object of interest/Cargo claim, pursuit and legal pickup, then launch.
It has fresh REACHABLE query returns at the pickup frame. Current native Flee,
Mankey pickup/Throw/normal-follow return, on-foot and mounted hits, and both
signed-height directions pass. The mounted run keeps rider100HP and restores
the seat after mount-only damage and knockback.

Both D1 checks pass on this ROM. The short spawn-work run has275 observations
and retains its one-preparation and bounded resumed-work checks. The long run
has2680 observations, uses the unchanged Continue save and existing Mankey,
and has zero late loops. No party, follower or spawn preparation is used for
that long run. Older distance, range/rebind, surface and other closed-ticket
proof keeps its recorded scope and ROM identity.

Broader gaps stay open: user bird-chain/roof/ride checks, required ordinary Hop
cases, zero-HP Save/Continue and blackout, home rest/checkpoint controls,
battle/capture HP transfer, and final health-bar/sound/edge-tint appearance.
A reported hitch keeps D1 open; zero late loops is the only stutter pass.

## Prior ROM3516 candidate and checks

- Latest recorded build: ROM3516. [Identity receipt](../../build/tickets/tkt20-final/build3516-identity.json) and [build status](../../build/tickets/tkt20-final/build3516-status.json) record a successful build (`running:false`, `ok:true`, `code:0`).
- Workspace `test.nds` and Delta `test3516.nds` SHA256:
  `38e92c4e5b48e9cc3c7205713fdf7052c96074ea1f92de379fcf2e3172fc58d5`.
- Independent `test.sav` SHA256:
  `65c36abc15d442141a33cdffd682868514db6093890cb958964dd732a846eefb`.
- The receipt does not establish an automatic open. Preserve the saved Workshop preference.
- Scoped ROM3509 records: [Ram](../../build/overworld-devtools/test-c09c77c8d062464f8b83b6d9d32889e0/manifest.json), [ledge Ram](../../build/overworld-devtools/test-28835c307c40434ea6918e803cfc0ff7/manifest.json), and [mounted Linear](../../build/overworld-devtools/test-a32756ce80f84120bccbee0436b32df3/manifest.json). Each completed with `passed:true`, `acceptedProof:true` and stopped cleanup. These records belong to ROM3509; no ROM3516 freshness claim is made here.

## Session and candidate ownership

- Use this checkout on `main`; preserve dirty and unrelated work.
- Use melonDS shared tools only. No images or video. Do not add a private driver.
- Inspect `dev status` and `dev test status` before live work. Do not take over another owner. Tests own a fresh private session.
- Preserve source ROMs, saves, the user's emulator and the saved build-open preference.

## Completion

The roadmap is not complete. Recorded status is not final acceptance. The frozen
candidate must pass all required current proof and
`scripts/owctl verify roadmap --rom test.nds --json` must report `passed: true`.

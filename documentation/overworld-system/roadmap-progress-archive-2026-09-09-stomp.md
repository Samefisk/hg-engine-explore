# Stomp reader — September 9

The final registered runs below accept the exact `legacy.stomp` contract.
The earlier pilot and failed runs remain diagnostic evidence. All six original measurement rows remain
unchanged; its global lifecycle counts now correctly require two moves.

## Native pilot

Owned session `session-a8jhx9sl`, ROM3095, source `test.sav`. Prepared map33,
tile588/406, party slot0 Cyndaquil155, current follower mounted. Guarded Owner
setup: threshold2, no acceleration, first travel time2 then3. No screenshots.

- First normal LEFT move: one dust wrapper, allocation, render initialization,
  sound request2183 and successful native sound start. Player-step count1;
  actor returned IDLE at587/406 with one commit and no reservation.
- Second normal RIGHT move: no additional dust/sound calls. Player-step count2;
  actor returned IDLE at588/406 with two commits and no reservation. Frame778.
- Terminal same-reader control changed only threshold byte78 to255. The real
  reader rejected it. All184 bytes, binding, poses, input, registers and clocks
  were restored; the expected failure remained latched and the reader closed.
- Session stopped; verified private ROM removed (184,910,816 bytes). Sources
  and save preserved. No product edit or ROM build.

Retained native evidence:

- [Positive feedback](../../build/overworld-devtools/session-a8jhx9sl/event-details-db17be4c30b7.json): complete nested effect/sound receipts, native frame769.
- [Terminal reader control](../../build/overworld-devtools/session-a8jhx9sl/event-details-cdbf0b8c9eaf.json): exact restoration plus the last negative policy call.
- [Session identity and cleanup](../../build/overworld-devtools/session-a8jhx9sl/session.json).

## Tool findings and remaining proof

Full memory-data export failed: identity exceeded its old16 KiB cap. The actual
identity was17,469 bytes with whitespace. Export/draft now share a bounded1 MiB
limit; a permanent host test failed before and passes after the change, without
dropping any hash. Existing command-detail artifacts above survived. Do not
claim a complete replay stream for this pilot or repeat it just to repair notes.

Native policy COMMIT output has travelTime0, not the movement duration. The
stomp contract must use INPUT's actual selected travel time, then separately
check COMMIT/effect. Do not populate synthetic COMMIT data with the expected
duration. The retained positive call is the reference for this correction.
The corrected contract checks INPUT/TRY_STEP travel time separately from
COMMIT/CONSUMED. Both retained real COMMIT calls pass their native checks and
still fail on missing INPUT evidence; nothing is reconstructed. Final focused
suite:73 tests passed. Scenario validation and devtools-only guard passed.

The stream meter, fixed typed recipes and controller acceptance path are now
implemented. Complete synthetic raw streams exercise the real evaluator before
boot; these host results are not gameplay proof. Next run separate registered
reader control and two-case stomp jobs with complete compressed evidence.
No new Tick timing matrix is needed for these six claims. Source activation
does not close acceptance.

## Registered reader0837

[Manifest](../../build/overworld-devtools/test-0837e9d4fcbb48499751e0be893a3ae1/manifest.json):
failed after32.316s at the first observed frame768. The checker rejected
`native completed pose differs`; no gameplay acceptance was issued.
The saved completed frame, actor frame and native cycle match. The native
reader adds `unk88_z` and `unk94_z` to each object's pose, while the general
snapshot omits them. Comparing those dictionaries for equality was a test-tool
fault. Preserve the native values for full paired-position checks and compare
all common snapshot fields; do not invent zero values for missing fields.
Session-p8mocjm6 closed cleanly and its private184,910,816-byte ROM was removed.

## Registered reader9b36

[Manifest](../../build/overworld-devtools/test-9b3683ce5e384600aa8410e682442a4f/manifest.json):
failed after34.066s at frame771, after three accepted observation frames.
The pose-format fix passed. This second test-tool fault was
`native INPUT TRY_STEP count differs`. The input was not missing: shared
`walk-policy` receipt367 contains INPUT/TRY_STEP/time2 at frame769; receipt368
contains START_RESULT/CONSUMED/time2. The stomp output hook sees only that
START_RESULT and the later COMMIT/time0/effect1 at frame771. The native step,
one commit and control return are present. The checker must join the existing
shared INPUT receipt, not expect INPUT at the feedback-output function.
Source anchors: `ActorSystem_FinishMountedWalk`,
`OverworldMount_ApplyWalkPolicy` and `OverworldMount_CommitWalkBoundary`.
No new reader or game change is needed. Session-z8of5wep closed cleanly.

## Accepted checkpoint

- [Readercd87](../../build/overworld-devtools/test-cd8722bca1eb4ed0bc2ae2bd8783f451/manifest.json):
  `passed:true`, `acceptedProof:true`, exact same-reader threshold fault and
  full restoration, all23 copied-data controls. Eight observed frames;
  execution40.120s, acceptance15.091s, total55.211s.
- [Stomp706e](../../build/overworld-devtools/test-706e6c468cff4b9eaf039928f41debd5/manifest.json):
  `passed:true`, `acceptedProof:true`, all six original rows and14 copied-data
  controls. Two moves, dust/render initialization/native sound-start on the
  first and none on the second, paired poses and final control return.
  Eight observed frames; execution41.799s, total61.335s.

Both use ROM3095 and source test.sav through shared melonDS jobs. No product
edit, build, image capture, commit or push. All76 focused host tests passed;
scenario validation, doctor, retirement guard and diff checks passed.
The corrected saved0837 stream reaches its first frame; saved9b36 completes
case1. Both still reject their missing remainder. The permanent host fixtures
now retain sparse public poses, full native poses, shared INPUT and distinct
START_RESULT/COMMIT output calls. The proof skill links both registered jobs.
This does not prove Wild role parity, authored-profile timing, crash shake,
sound from speakers or the rest of D3. Next is exact legacy.crash.

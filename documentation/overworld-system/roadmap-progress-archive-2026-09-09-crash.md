# Mounted crash preparation — September 9

`legacy.crash` remains needed and unproved. Its six original rows require a
real held-input collision, mounted Cyndaquil identity, one stationary crash,
elapsed frames1–32, sound/shake, and reset followed by one recovery Walk.
No narrower sound-only or Wild-shake test can replace those rows.

## Completed setup seam

`mount-walk.configure` now accepts optional `turning` (`free`, `locked`) and
`crashSound` (`none`, `wall-hit`). Full184-byte checks, idle binding, no clock
advance and verified rollback remain in force. Only profile byte65's masks0x01/0x10
change; omitted options preserve the old bytes and receipt shape. The public
header compile check confirms the offset and masks independently.

Forty-six focused host tests passed, including nine option combinations,
invalid commands, write-failure restoration, old matrix/stomp recipes and
typed contracts. Scenario validation and diff checks passed. Independent
read-only review found no issues. No live run, build, product edit or ROM copy.

## Next bounded observation

- Existing `CrashPresentationReader` reads Wild's slot timer/base positions,
  not mounted crash. Do not use its output for the mounted requirement.
- Mounted state is184 bytes at0x023BC744. Public runtime header gives mode102,
  duration0x90, elapsed0x92. Crash mode3 has32 frames; face X/Z offsets are
  opposite signs, magnitude0x2000, selected by `elapsed & 2`. Keep logical and
  base positions fixed, then require exact restoration.
- Authenticate mounted StartWalkCrash, UpdateCustomMotion,
  ApplyCrashPresentation, FinishCustomMotion and PlayCrashSound. Reuse the
  full native pair/owner reader and sound-call authentication; do not reuse
  Stomp's hard-coded sound2183. Wall-hit is1536 in the vanilla sound header.
- Candidate shorter route: map33 at577/397, north through577/396 into wall
  577/395; release, then RIGHT recovery. These historical coordinates still
  require current native terrain/occupancy checks before use.
- Set lock+sound through the named guarded setup, not the old collector's
  write to state+0x82 (now adapter storage). Preserve normal input and timers.

Source anchors: `include/overworld_mount_internal.h`,
`include/overworld_wild_behavior_data.h`, and
`src/overworld_mount_overlay/overworld_mount_overlay.c`.
The registered crash scenario stays planned until its exact reader, evaluator,
separate live reader control and accepted execution are ready.

## Live diagnostic and pure meter checkpoint

Root-owned session-zfgkx946 on3099: idle mounted Cyndaquil155 at577/397;
current wall577/395 confirmed. Guarded lock+wall-hit configuration only.
Reader armed782, UP16/NONE32/RIGHT8/NONE8 gives one crash,33update returns,
32presentations elapsed1..32, sound1536 and successful stock soundStart return1.
Logical/base pose stays577/396 during crash. Finish native return still carries
shake; completed queue823 restores it. Recovery reaches578/396 by839.
Reader pending0/failureNone. Recording and private session closed.

recording-28a166107404.json in session-zfgkx946, SHA256
aa878865ab8f41ee9a71fe06333401efd3454145ea7bd970c5db524f4c7e5450:
65snapshots783–847,173events, no truncation. Expanded native events are retained
as adjacent hash-identified artifacts. No accepted proof from this manual run.

Helper froze devtools_mounted_crash_measurement.py and its9passing host tests.
Pure arm/command/observe/close/finish/result API retains the six original rows;
it checks wrong identity, missing events, elapsed/shake/sound, early reset,
extra commits, missing recovery and close mismatch. Tests replay the exact
retained artifact; their synthetic zero-advance close is not live calibration.
Main still must review/integrate controller wiring, recipe and same-reader
live negative control before accepted Crash execution. No product edit/build.

## Fresh record-before-arm and live reader control on3100

Root-owned session-6sz_20x4 recorded before arm783, then one real neutral
queue784 before input. No invented completed pose at arm. UP16/NONE32/RIGHT8/
NONE8 produced32 shake presentations, one wall-hit sound start, restoration
at824 and recovery to578/396 by848. Independent saved-data replay reports
ready:true, no failures, all six original rows. This is not controller acceptance.

Terminal crash.calibrate completed: mode255 rejected by the same reader as
`mounted pacing: crash state fields invalid`; two byte writes, zero guest
instruction advance, exact restoration, cleanupPending:false, reader closed.
No retry or later gameplay. Shared stop closed the core and removed only its
verified private ROM copy. Source ROM/save files are unchanged.

Post-control artifact: session-6sz_20x4/recording-d48e170fa316.json under
build/overworld-devtools; SHA256
f29a66c1820b7b4283033a8f6051ac748ecbae0e027a50739f56683fa794b594.
66 retained snapshots,181 events, no drops or truncation. Pre-control artifact
recording-9c4fc720fd37.json SHA256
aa6ccff48bee0f4e2154248f6a205b76594d72d0c07fecbe287b9ee9e7794b1e.
24 focused command/control/observer/support host checks pass. Control fixture
now uses the actual public subject shape, without invented movementPolicy data.
Checked recipe and controller acceptance remain open; D1 work takes priority.

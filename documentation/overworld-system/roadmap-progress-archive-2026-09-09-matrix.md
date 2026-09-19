# Walk timing matrix — 2026-09-09

Current work is on [the resume page](roadmap-progress.md). This is a detail index,
not a second work queue. All runs used ROM3095 and the shared melonDS service.
No product code or ROM build changed during this matrix port.

## Accepted checkpoint

- [Matrix8555](../../build/overworld-devtools/test-85551ae0e2f844d9a69cad428d4218e5/manifest.json): accepted65 motions/1177frames,130.930s. Six original `legacy.mounted-frames` rows and17 copied-data controls.
- [Readerd845](../../build/overworld-devtools/test-d845a54cd68e4691ad46a986d3c19e7d/manifest.json): accepted7frames,46.965s. Two real moves, same-reader phase fault, exact52-byte restoration,22 copied-data controls. No later guest execution.
- Each private session closed. Verified private ROM copies were removed automatically. Saves and compressed memory evidence remain.

## Reader and route contracts

- Read actual `OverworldMotion_Tick` entry0..N−1 and return1..N. No inferred elapsed0.
- Use one bound Mounted Cyndaquil155, actual reservation, clocks, raw bytes, input, lifecycle and completed rider/mount positions.
- Cardinal and diagonal durations1–32, then forbidden cardinal input under diagonal-only mode and a valid5-frame diagonal:65 motions total.
- Native mounted direction/facing is cardinal. Exact destination coordinates carry diagonal travel. NW permits facing0/2; SE1/3. Sample facing must match.
- Configure only named lane bytes at idle, with zero guest execution and exact readback. Do not reset policy or write movement state.
- Actor completion can precede its pending player-step receipt. After each diagonal, retain one normal neutral queue; the next configure still checks fully idle adapter state.
- Same-reader calibration checks phase decoding, not an injected timing fault. Copied-data controls check the evaluator separately.
- CPU clock precision bounds only the diagnostic thread/process comparison. Raw process timings and stutter limits are unchanged.

## Failures replayed before more boots

| Evidence | Finding and response |
| --- | --- |
| [118d](../../build/overworld-devtools/test-118d86e36f87421a93a73022e2dc41fd/manifest.json) | Live2-case control passed; proof adapter dropped its exact missing-return error. Preserve wrapper failures and replay all22 faults. |
| [18cb](../../build/overworld-devtools/test-18cb7c5299404424b81d70471e1f05cb/manifest.json), [803b](../../build/overworld-devtools/test-803bcce6e58c46db92615d3b1a2a3ca9/manifest.json) | Accepted control could not be revalidated after JSON storage. Case keys used tuples. Make them JSON-native lists; require exact save/reload replay.803b never booted. |
| [c3ef](../../build/overworld-devtools/test-c3ef0f8716b547419575634570360036/manifest.json) | CPU clocks differed by125ns with process precision1000ns and thread42ns. Record precision and bound independent endpoint rounding; never adjust raw timing. |
| [9eb9](../../build/overworld-devtools/test-9eb93088b4c547dcb869e08635e3e022/manifest.json) |32cardinal cases passed. First diagonal exposed the meter's wrong geometric-facing expectation. Source and raw memory confirm cardinal facing plus diagonal target. |
| [1fcf](../../build/overworld-devtools/test-1fcf58627594416c9310c6dc105808a5/manifest.json) | First diagonal completed but fixture saw walkEndState2/pendingFieldStep1. Short sessione96meql5 reproduced oneNW; frame772pending→773clear through normal neutral input. No flags cleared. |
| [32c9](../../build/overworld-devtools/test-32c9c4d92ffd42408c2585939a75c740/manifest.json) | All65 gameplay cases passed. Full meter dropped its precise missing-return failure after finish. Persist it, retain exact native sequence rejection for removed final motion, replay all17 faults before fresh acceptance. |

Earlier reader checkpoints7c71,3ff0,9b10 andce66 remain in their manifests;
later tool edits mean they are historical, not final input proof.

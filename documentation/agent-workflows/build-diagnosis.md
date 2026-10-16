# Build diagnosis

Use this guide when a build stops before Make or an overlay does not fit. Read
only the matching section. For a requested ROM build, use
`hg-engine-delta-build` and the V2 Workshop so the workspace lock, Delta copy
and saved open-after-build choice stay under the existing build workflow.
Reading this guide does not start a build.

## Checkout, logs, and build ownership

Each Workshop server is bound to the checkout that contains its server script.
Before a build, read `GET /api/v2/workspace-meta` and compare `workspaceRoot`
with the intended checkout. The build API cannot switch checkouts. For an
existing second checkout, start its `tools/overworld-viewer-v2/server.py` on
another port and use that service. Do not create a worktree for this step.

Build status includes `outputLogPath`. That local file contains the complete
output, including errors removed from the 60,000-character status tail. The
last status and log survive a server restart. A restart during an unfinished
build reports an unknown result; inspect the log and stop any remaining build
process before a retry. The normal restart endpoint rejects an active build.

The V2 workspace lock blocks Workshop source writes during a build. It does
not block shell tools or other agents. Freeze source edits and object/link
outputs until the build completes. If any input changes, discard that result
and repeat the checked build after the inputs stop changing.

For disposable compiler checks, use the production image's actual platform.
Do not force `linux/amd64` when the supplied image is `linux/arm64`. Inspect
it with `docker image inspect IMAGE --format '{{.Os}}/{{.Architecture}}'`.
Use the production compiler and complete link for size proof, as below.

If a host tool build needs CMake and `cmake` is absent, use the existing checked
project tool or the managed image. Installing CMake is a host setup task;
copying a tool does not prove a fresh host tool build.

If an existing worktree lacks the local vanilla reference, use
`git worktree list --porcelain` to find the primary checkout, then read its
`.codex-reference/README.local.md` and validated source directly. Do not copy
reference source or generated files into the project. This is a lookup
workaround; it does not provision the missing local reference.

## Rejection before Make

The Workshop build goes through [docker-makerom.cmd](../../docker-makerom.cmd).
Its `--managed-build-clean` entry calls
[`trusted_pre_make_source_mismatch`](../../scripts/verify_pokemon_move_history_capture.py)
before Make. This checks recorded SHA-256 values for the wrapper, Makefile and
included Make sources, then checks generated dependency inputs. A changed
`overlays.mk` can therefore stop the build before any compiler runs.

Find the first mismatched input with this read-only check from the repo root:

```bash
python3 -B - <<'PY'
from scripts import verify_pokemon_move_history_capture as gate
mismatch = gate.trusted_pre_make_source_mismatch((gate.REPO / "Makefile").read_text())
print(f"Pre-Make mismatch: {mismatch}" if mismatch else "Pre-Make sources match")
raise SystemExit(1 if mismatch else 0)
PY
```

If a named source changed, inspect its diff and intended effect first. The
matching records are `EXPECTED_MAKEFILE_SHA256`,
`EXPECTED_BUILD_WRAPPER_SHA256` and `EXPECTED_INCLUDED_MAKE_SOURCES` in the
same verifier. Update only a reviewed, intended input's record. A generated
dependency mismatch needs its named topology/safety check, not a new hash.
Keep the verification gate in the build path.

## Overlay size and toolchain

Start with the first failed target in the build output. The sources of truth
for that target are:

| Build fact | Read this source |
| --- | --- |
| Compiler/binutils identity and recorded flags from the last compile | `build/.compile-config`, written by `COMPILE_CONFIG_STAMP` in [Makefile](../../Makefile) |
| Flags applied to this specific source | `SRC_OBJ_INC_DEFINE` and its per-object flag branches in [Makefile](../../Makefile); the stamp does not list every special flag |
| Complete overlay object list and final link command | `OVERLAY_DEFINE` in [overlays.mk](../../overlays.mk), including its portable object groups |
| Overlay limits, sections and imports | The affected `src/<overlay>/linker.ld`, current `rom_gen.ld`, and its generator [generate_ld.py](../../scripts/generate_ld.py) |

Use the same configured Docker ARM compiler, version, flags, object list and
current generated imports as the production build. Host GCC or a different
ARM compiler can give a different size. A hand-picked partial link cannot
prove that the full overlay fits. If the stamp is missing or belongs to other
inputs, treat the identity as unknown until the authorized build records it.

Object targets contain the source-directory segment. For example, the Wild
object is `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`;
the complete overlay link is `build/overworld_wild_spawns_overlay_linked.o`.
Inspect the matching rule before choosing a narrow target. An object compile
proves compilation only. The full link and packaged ROM checks own fit and
final placement.

## Wild overlay change: pinned bodies, addresses and slot size

The Wild spawns overlay (overlay 149) occupies a fixed 0xB000-byte slot. A source
change that adds code moves the floating functions and data after it. Three
checks follow:

1. **Slot overflow.** The link stops with `linker.ld:213 cannot move location
   counter backwards`; the numbers are the overflow in bytes. Shrink the new code
   (or find real savings) until the link passes. Do not raise the slot.
2. **Pinned copied bodies.** The next stop is `shared Hop admission body
   differs` from `scripts/pack_overworld_actor_slam_jump.py`. The sealed
   functions embed link addresses of moved symbols. Before accepting new
   hashes, compile the previous and new source to unlinked objects with the
   production flags and prove that only the functions you edited changed
   (`python3 scripts/compare_relocatable_objects.py OLD.o NEW.o`). Then
   refresh every pin with `python3 scripts/reseal_wild_overlay_pins.py`:
   `scripts/pack_overworld_actor_slam_jump.py`,
   `tools/overworld/devtools_slam_admission_observer.py`,
   `scripts/verify_overworld_query_code_addon.py` (`WILD_ENTRY_NATIVE_*`),
   `tools/overworld/devtools_query_observer.py` (`ENTRY_NATIVE_OWNERS`) and
   `tools/overworld/devtools_fly_landing_cost.py` (`PINS`).
3. **Host checks.** `tools/overworld/test_spawn_refill_budget.py` and
   `tools/overworld/test_spawn_move_entry.py` extract and compile parts of
   `FrameMovementTask` and `TickMovementParams`; a new local variable or
   macro in an extracted region needs a matching stub there.

After a Wild or tool change restart Workshop (`POST /restart-server`) before
the next session; a stale service reports `server_restart_required`.

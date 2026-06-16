# Overworld Wild Overlay 150 Behavior Data Log

## Attempt A01: Move Behavior Data To Linked Overlay 150

Goal:

- Start the hybrid overlay-module path by keeping overlay 149 resident for active behavior code and moving the large behavior profile/rule/override data into linked resident overlay 150.
- Keep the shape expandable for future behavior-family modules through a fixed entry table instead of direct cross-overlay symbol use.
- Preserve normal spawn and behavior resolution when overlay 150 cannot be validated by falling back to the default profile.

Helper-agent findings incorporated:

- Overlay loader: extend the existing linked chain as `field -> 131 -> 149 -> 150`; this matches the current loader's one-hop linked overlay traversal.
- Data split: move the profile, class-rule, and override tables first. Keep active callbacks, task logic, and movement primitives in overlay 149.
- Verification: add explicit metadata checks for overlay 150 address/entry-table shape, syntax-check both overlay sources, and document the full build/runtime blocker if Docker is unavailable.

Code change:

- Added `include/overworld_wild_behavior_data.h` for the shared profile/rule/override structs, terrain/destination enums, override masks, magic/version constants, and fixed entry-table address.
- Added overlay 150 in `src/overworld_wild_behavior_data_overlay/` with a dedicated linker script at `0x023C3000` and an exported `gOverworldWildBehaviorDataOverlayEntry`.
- Added `OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA` to `include/constants/file.h`.
- Extended `src/overlay.c` with the linked resident chain `OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION -> OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA`.
- Updated overlay 149 to lazy-load and validate overlay 150 before resolving behavior profile data, then fall back to the default profile if the entry is missing or invalid.
- Updated `scripts/overworld_behavior_profile_viewer.py` so behavior profiles/rules/overrides are read and edited from overlay 150 while route/spawn settings still use overlay 149.

Static verification:

- `clang -target arm-none-eabi -fsyntax-only -DIMPLEMENT_OVERWORLD_WILD_SPAWNS -Iinclude src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`
  - Passed with only existing repository header warnings.
- `clang -target arm-none-eabi -fsyntax-only -DIMPLEMENT_OVERWORLD_WILD_SPAWNS -Iinclude src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
  - Passed with only existing repository header warnings.
- Overlay metadata script:
  - Confirmed overlay 150 linker origin is `0x023C3000`.
  - Confirmed overlay 150 linker length is `0x1000`.
  - Confirmed the overlay 150 entry section and magic/version fields are present.
- Data split script:
  - Confirmed `sOverworldWildBehaviorClassProfiles`, `sOverworldWildBehaviorClassRules`, and `sOverworldWildBehaviorOverrides` live in overlay 150.
  - Confirmed overlay 149 references the fixed behavior-data entry accessor instead of the old local static tables.
- `python3 -m py_compile scripts/overworld_behavior_profile_viewer.py`
  - Passed.
- Viewer data-model check with a `PIL.Image` import stub:
  - Passed.
  - Reported `classes=9`, `classRules=109`, `variableOverrides=2`, and `routes=142`.
  - Confirmed the viewer source metadata points behavior data at `src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c`.
- Build-system inspection:
  - `overlays.mk` discovers top-level `src` overlay directories automatically.
  - `scripts/make.py` likewise scans `src`, reads each overlay directory's `linker.ld`, and writes the overlay id from the first `/* Overlay ### */` comment.
  - Overlay 150's linker script matches the expected comment and `ORIGIN` format.
- `git diff --check`
  - Passed.

Build/runtime verification:

- `./docker-makerom.cmd`
  - Blocked in this environment because `docker` is not installed: `./docker-makerom.cmd: line 6: docker: command not found`.
- Local fallback checks:
  - `docker`, `arm-none-eabi-gcc`, and `arm-none-eabi-ld` were unavailable.
  - `PIL` was unavailable for a full unstubbed viewer import; the parser/data-model path was validated with an import stub because image rendering is not part of behavior table parsing.
  - Full ROM build, Delta copy, overlay-table ROM inspection, and headless runtime verification could not be completed here without Docker or the ARM toolchain.

Headless follow-up:

- Existing `test.nds` inspection with `ndspy`:
  - Y9 size is `0x12C0`, which is 150 rows and therefore only covers overlays `0..149`.
  - Overlay 149 is present at `0x023CD000` with size `0xAD18`.
  - Overlay 150 has no Y9 row in the existing ROM.
- `scripts/headless-overworld-test.py --rom test.nds --dsv .headless_desmume/.config/desmume/test.dsv --action screenshot:documentation/verification_screenshots/overlay150_existing_rom_00_ready.png --read ov150_magic:u32:0x023C3000 --no-screenshot`
  - Passed as a headless boot/read run against the existing ROM.
  - Screenshot shows the loaded overworld state.
  - Read `ov150_magic` at `0x023C3000` as `0x00000000`.
- `scripts/headless-overworld-test.py --rom test.nds --dsv .headless_desmume/.config/desmume/test.dsv --read ov150_magic:u32:0x023C3000 --expect ov150_magic=0x4F574244 --no-screenshot`
  - Failed as expected on the existing ROM.
  - Expected overlay 150 magic `0x4F574244`, actual `0x00000000`.
  - This proves the headless tester is runnable here, but the current `test.nds` does not contain this branch's overlay 150 changes.

Result:

- The code is split into a resident overlay 150 data module and overlay 149 entry-table consumer.
- Static checks passed for the changed C sources and the module metadata.
- Runtime confidence still needs a real ROM build on a machine with Docker/toolchain access, then the same headless magic/read and overworld scenario checks should be rerun against the rebuilt ROM.

Follow-up checks when Docker is available:

- Run `./docker-makerom.cmd`.
- Confirm `test.nds` copies to Delta if using the normal Mac build flow.
- Run a headless overworld scenario that spawns visible wild Pokemon and verifies behavior assignment still resolves for several species/classes.
- Inspect the built overlay metadata to confirm overlay 150 size stays under `0x1000` and the fixed entry address matches `y9.bin`.

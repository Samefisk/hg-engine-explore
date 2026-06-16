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

## Attempt A02: Build Then Test Request

Goal:

- Run the normal ROM build, then run the battle-test flow requested by the user.

Build:

- `./docker-makerom.cmd`
  - Failed immediately because Docker is unavailable in this environment: `./docker-makerom.cmd: line 6: docker: command not found`.

Test build:

- `make AUTO_TEST=Y -j1`
  - Used `-j1` because `nproc` is not available in this macOS environment.
  - Failed at the first compiler invocation because `arm-none-eabi-gcc` is unavailable: `make: arm-none-eabi-gcc: No such file or directory`.

Test runner:

- `SDL_VIDEODRIVER=dummy scripts/run_tests.sh` was not run.
- Reason: the `AUTO_TEST=Y` test ROM was not built. Running the battle-test runner against the stale existing `test.nds` would not validate this branch.

Result:

- Build blocked by missing Docker.
- Test build blocked by missing ARM toolchain.
- No tracked generated files were changed by the failed build/test build attempts.

## Attempt A03: Build Skill And Headless Runtime Verification

Goal:

- Re-run the normal Mac Docker build path through `./docker-makerom.cmd` after restoring this Codex shell's PATH to include Docker and the ARM toolchain.
- Verify the rebuilt regular ROM boots to the overworld and can run a short key-only movement scenario with overlay 149/150 present.

Build fix before rerun:

- `src/overlay.c`
  - Restored the priority-unload loop to use the matching row's linked overlay id instead of indexing through the first row. This preserves the existing priority-table shape and avoids unrelated unloads.
- `src/save.c`
  - Removed the always-emitted `"[SQRT]  RESULT = %08X\n"` format string from non-`DEBUG_SQRT` builds while keeping the hardware sqrt result read alive with a volatile write into the local buffer.
  - This fixed the root ROM region overflow caused by the orphan `.rodata.str1.1` string spill from `build/save.o`.

Build:

- `export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"; ./docker-makerom.cmd`
  - Passed.
  - Created `test.nds` at 176M.
  - Copied the ROM to `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test900.nds`.

Headless verification:

- `scripts/headless-test-ready.sh --screenshot documentation/verification_screenshots/overlay_modules_00_ready.png`
  - Passed.
  - Loaded `test.dsv` into the overworld in 6 seconds.
  - Screenshot showed the loaded Route 29 overworld, not a title/menu/black frame.
- `scripts/headless-overworld-test.py --action screenshot:documentation/verification_screenshots/overlay_modules_01_menu_open.png --action tap:B:6:24 --action wait:60 --action screenshot:documentation/verification_screenshots/overlay_modules_02_menu_closed.png --action hold:LEFT:45:24 --action wait:30 --action screenshot:documentation/verification_screenshots/overlay_modules_03_left.png --action hold:RIGHT:90:24 --action wait:30 --action screenshot:documentation/verification_screenshots/overlay_modules_04_right.png --action hold:DOWN:60:24 --action wait:30 --action screenshot:documentation/verification_screenshots/overlay_modules_05_down.png --read comm:s32:0x02FFF81C --expect comm=0 --screenshot documentation/verification_screenshots/overlay_modules_06_final.png`
  - Passed.
  - Used `/Users/christofferandersen/Library/Application Support/DeSmuME/0.9.13/Battery/test.dsv`.
  - Read `comm` at `0x02FFF81C` as `0`, matching the expectation.
  - Screenshots showed player movement, a visible wild overworld Pokemon, and no black-screen/crash state.

Battle-test note:

- A separate `AUTO_TEST=Y` battle-test ROM build was attempted through the same Docker image:
  - `docker run ... 'cd /hg-engine && make AUTO_TEST=Y -j$(nproc) VENV=/tmp/hg-engine-venv'`
  - Failed at root link with `region 'rom' overflowed by 2756 bytes`.
  - This is the battle scenario harness build, not the regular ROM build or the overworld headless runtime path.

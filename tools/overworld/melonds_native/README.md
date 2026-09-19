# Shared melonDS native transport

This is the native library for the shared overworld worker, not a game driver.
It builds official melonDS 1.1 at commit
`b86390e4428bf38ce4c1ce0e9ca446d6d25955e8`. The dependency keeps its upstream
GPL-3.0-or-later license; its source and license remain in the pinned checkout.
Do not put a user's app, ROM, BIOS dump, firmware or save into this directory.

Build with a C++17 compiler, Git and CMake (3.16 or later):

```sh
python3 -B tools/overworld/melonds_native/build.py
```

`--source` may name an existing **disposable** official checkout. The script
checks the full revision and rejects unrelated source changes before applying
the two exact interpreter taps. `--cmake` accepts a private CMake executable.
The manifest records its resolved executable path as `cmakeExecutable`.
The build has no Qt, SDL, JIT, OpenGL or GDB server dependency. It uses stock
software rendering. No image is captured automatically.

Output: `build/melonds/libow_melonds.dylib` (macOS) or `.so`, plus
`build/melonds/manifest.json`. Publishing these outputs requires the same
upstream source/license obligations as melonDS. The manifest seals the pinned
revision, bridge source inputs, resolved CMake executable, library hash and
native test result.

Before installing outputs, the build runs `ow_melonds_core_test`. It uses only
synthetic ARM/Thumb instructions, memory and registers. No cartridge is opened.
These tests check the transport, not game behavior.

For a bounded hook-lookup cost comparison, run the built test with
`build/melonds/native-build/ow_melonds_core_test --benchmark`.
It compares cached and uncached lookup on synthetic PC streams and checks
equal callbacks and dispatch counts. Timing is diagnostic, not a game pass.

## Semantics

`bridge.h` is the C ABI. One handle owns one DS core. Use one thread per handle;
no calls may race a frame. Read/write callbacks are synchronous on that thread.
Register 15 has architectural PC at instruction callbacks; `md_next_pc` gives
the exact before-execution instruction. `md_branch` flushes the instruction
pipeline and refreshes the code region even after an explicit register-15 edit.
An explicit callback abort latches the core and unwinds the native frame. That
core must be destroyed, never resumed. Read-only fault diagnostics remain valid.

Instruction lookup caches only exact-address misses, separately for each CPU.
Every hook add, replacement or removal invalidates that CPU's cached misses,
including edits made inside a callback. Hits still use the current hook map;
the cache stores no callback pointers and changes no guest instruction.

Optional native phase timing uses fixed current-thread CPU scopes, not an
instruction timer. The public sized read returns exclusive phase totals,
call counts, frame sequence and validity. Read a failed frame as diagnostic
data only. See [phase interpretation](../../../documentation/overworld-system/devtools-tests.md#keep-the-feedback-loop-short)
before comparing these costs with observer or whole-cycle timing.

Write taps report successful **CPU** stores after the store, including ARM9
ITCM/DTCM paths. Their address is the actual bus/TCM address used by the store;
register each needed alias explicitly. DMA and host writes are not CPU stores.
The write callback's raw PC is the architectural writing-instruction PC.
`md_next_pc` outside an exec callback is the next pipeline instruction.

`md_read_framebuffer` copies the two paused front buffers into RGBA bytes only
when explicitly called. It does not display or save an image. The frontend
must call it only for an explicit human Capture or video request. The native
test checks synthetic color bytes, not game images. `md_read_save` copies the
current owned battery memory; the frontend owns any explicitly requested file
export. Touch inputs use bounded screen coordinates and do not advance frames.

Open uses melonDS's built-in free BIOS and generated firmware, followed by stock
direct boot. The source save is read into core-owned battery memory. No automatic
save, firmware, network, camera or microphone writes reach the host. This is a
disposable test core. Optional human image capture is a separate frontend concern.

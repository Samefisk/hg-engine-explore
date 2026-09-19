#ifndef OW_MELONDS_BRIDGE_H
#define OW_MELONDS_BRIDGE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* ABI 1. CPU 0=ARM9, 1=ARM7. Status 0=success, -1=error. */
typedef void (*md_callback)(int cpu, uint32_t address, uint32_t width, void* user);
uint32_t md_abi_version(void);
const char* md_source_revision(void);
void* md_create(void);
void md_destroy(void* handle);
const char* md_last_error(void* handle);
int md_open_rom(void* handle, const char* path);
int md_import_save(void* handle, const char* path);
uint32_t md_save_size(void* handle);
int md_read_save(void* handle, void* out, uint32_t length);
/* Explicit capture only: 256x384 RGBA8, top screen followed by bottom.
 * The exact output size is 393216 bytes. Does not advance the core. */
int md_read_framebuffer(void* handle, void* out, uint32_t length);
int md_run_frame(void* handle);
/* Raw inclusive NDS scheduler clocks, not host CPU cost or instruction counts.
 * Exact 32-byte layout, version 1, flags: inside RunFrame=1 (otherwise 0).
 * Read-only during a synchronous exec callback or while paused; opened,
 * running NDS required. Faulted/stopped/invalid cores produce no receipt.
 * ARM.cpp adds instruction Cycles AFTER dispatch; pre-exec reads exclude
 * that instruction. IRQ and halted/wait advances are included. On NDS,
 * ARM9 raw ticks have twice ARM7's scale; do not subtract across CPUs.
 * frame_sequence is the bridge RunFrame attempt, not a completed game update.
 * No clock conversion, guest execution, memory access or guest write occurs. */
typedef struct md_guest_clock {
    uint32_t version, flags;
    uint64_t arm9_timestamp, arm7_timestamp, frame_sequence;
} md_guest_clock;
int md_read_guest_clock(void* handle, void* out, uint32_t length);
/* Optional dispatch accounting; no retired-instruction or host CPU claim.
 * Exact 32-byte native layout; flags: enabled=1, completed frame=2.
 * Reads remain valid after a fault. Toggle only while paused; disabling is
 * also allowed after a fault. Neither operation advances guest execution. */
typedef struct md_dispatch_counts {
    uint32_t version, flags;
    uint64_t frame_sequence, arm9, arm7;
} md_dispatch_counts;
int md_set_dispatch_counts(void* handle, uint32_t enabled);
int md_read_dispatch_counts(void* handle, void* out, uint32_t length);
/* Optional ARM9 dispatch PC histogram. Fixed 64-byte bins cover the half-open
 * range [0x02000000, 0x02400000); instructions outside that range are added
 * to unmapped. Exact 262176-byte layout, version 1, flags: enabled=1,
 * completed frame=2, invalid counter overflow=4. Counts are host memory only;
 * no guest memory is read or changed. The histogram counts instructions that
 * reach the interpreter, excluding exec-hook redirects. */
#define MD_PROFILE_PC_BASE 0x02000000U
#define MD_PROFILE_PC_LIMIT 0x02400000U
#define MD_PROFILE_PC_BIN_SHIFT 6U
#define MD_PROFILE_PC_BIN_COUNT 65536U
#define MD_PROFILE_FLAG_ENABLED 1U
#define MD_PROFILE_FLAG_COMPLETE 2U
#define MD_PROFILE_FLAG_INVALID 4U
typedef struct md_profile {
    uint32_t version, flags;
    uint64_t frame_sequence, total, unmapped;
    uint32_t counts[MD_PROFILE_PC_BIN_COUNT];
} md_profile;
int md_profile_enable(void* handle, uint32_t enabled);
int md_profile_read(void* handle, void* out, uint32_t length);
/* Optional exclusive thread-CPU diagnostics. Version 2, exact 64-byte layout.
 * flags enabled=1, completed frame=2, invalid timing=4. Ordered phases:
 * native non-render work, software 3D RenderFrame, software 2D DrawScanline.
 * Non-render includes guest execution, DMA/SPU, and synchronous host hooks.
 * Never subtract these costs from process CPU acceptance. */
typedef struct md_phase_cost { uint64_t cpu_ns, calls; } md_phase_cost;
typedef struct md_phase_timing {
    uint32_t version, flags;
    uint64_t frame_sequence;
    md_phase_cost phases[3];
} md_phase_timing;
int md_set_phase_timing(void* handle, uint32_t enabled);
int md_read_phase_timing(void* handle, void* out, uint32_t length);
int md_read_bytes(void* handle, int cpu, uint32_t address, void* out, uint32_t length);
int md_write_bytes(void* handle, int cpu, uint32_t address, const void* data, uint32_t length);
/* Registers 0..15, CPSR=16, current-mode SPSR=17. At exec callbacks r15 has ARM architectural
 * PC (instruction+8 ARM / +4 Thumb); md_next_pc is the instruction address.
 * Set r15 alone does NOT flush the pipeline: use md_branch afterwards. */
uint32_t md_get_reg(void* handle, int cpu, int index);
int md_set_reg(void* handle, int cpu, int index, uint32_t value);
uint32_t md_next_pc(void* handle, int cpu);
/* Address bit 0 selects Thumb. Flushes both prefetched instructions. */
int md_branch(void* handle, int cpu, uint32_t address);
int md_set_keys(void* handle, uint32_t pressed_mask);
int md_touch(void* handle, uint32_t x, uint32_t y);
int md_release_touch(void* handle);
/* One callback per key; NULL removes. Edits during dispatch affect the next
 * dispatch. Writes are AFTER successful CPU stores, not host memory edits. */
int md_hook_exec(void* handle, int cpu, uint32_t address, md_callback callback, void* user);
int md_hook_write(void* handle, int cpu, uint32_t address, uint32_t length, md_callback callback, void* user);
/* Callback errors latch permanently. The current instruction is not resumed
 * after an exec callback abort; write callbacks observe the completed store. */
void md_abort(void* handle, const char* message);
#ifdef __cplusplus
}
#endif
#endif

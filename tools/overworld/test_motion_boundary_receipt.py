"""Host witness for architecture.md's captured motion identity contract.

Compiles the production bridge and identity guard. The boundary's remaining
work is a counter stub: this proves receipt forwarding/rejection, not motion
completion, ARM argument passing, or game behavior.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def block(source, start):
    opening = source.index("{", start)
    depth = 1
    for end in range(opening + 1, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise ValueError("unterminated production body")


def harness():
    runtime = (ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
    actor = (ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
    bridge = "BOOL " + block(runtime, runtime.index("OverworldWildRuntime_ApplyMotionBoundary("))
    boundary = block(actor, actor.index("ActorSystem_EngineBoundary("))
    guard = block(boundary, boundary.index("if (call->motionIdentity"))
    # Exercise both old and new source with the same retained receipt. The old
    # ABI cannot carry it, which is the defect this witness must report.
    signature = bridge[:bridge.index("{")]
    extra = ", receipt" if re.search(r"u16\s+motionIdentity\s*\)", signature) else ""
    wild_header = (ROOT / "include/overworld_wild_spawns_internal.h").read_text()
    actor_header = (ROOT / "include/overworld_actor_system.h").read_text()
    names = ("OW_WILD_LAND_SURF_MAX_SPAWNS", "OW_WILD_HEADBUTT_MAX_SPAWNS",
             "OW_WILD_HEADBUTT_SLOT_START", "OW_WILD_FISH_SLOT_START",
             "OW_WILD_FOLLOWER_SLOT", "OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS")
    constants = "\n".join(re.search(r"^#define " + name + r" .+$",
                         wild_header + "\n" + actor_header, re.M)[0] for name in names)
    return constants + r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int BOOL;
#define FALSE 0
#define OVERWORLD_ACTOR_MOTION_CALL_VERSION 1
#define OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY 1
#define OVERWORLD_ACTOR_RESULT_OK 0
#define OVERWORLD_MOTION_DECISION_ACCEPTED 0
#define OVERWORLD_MOTION_DECISION_CONTEXT_LOST 1
typedef struct { int unused; } OverworldMotionSample;
typedef struct { int unused; } OverworldActorWalkPolicyCall;
typedef struct { u16 movementMotionIdentities[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS]; } OverworldWildRuntimeMotionPrefix;
typedef struct { u16 motionIdentity; } OverworldMountRuntimeState;
typedef struct { void *movementRuntimeState; } SpawnState;
typedef struct {
    u16 version, size;
    u8 operation, acknowledgements, cancelReason, phase, actorSlot, reserved;
    u16 fieldEpoch, acknowledgedPathAdvance, motionIdentity;
    u16 pendingLastPathAdvance, decision, tickFlags;
    OverworldMotionSample *sample;
    OverworldActorWalkPolicyCall *walkPolicy;
} OverworldActorMotionBoundaryCall;
static OverworldWildRuntimeMotionPrefix wild;
static OverworldMountRuntimeState mountState;
static SpawnState sOverworldWildSpawnState = { &wild };
#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR (&mountState)
#define OW_WILD_RUNTIME_MOTION(state) ((OverworldWildRuntimeMotionPrefix *)(state)->movementRuntimeState)
#define OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(value) (value)
static int OverworldWildRuntime_GetFieldContext(void) { return 1; }
static struct { u16 reservationId; } actorState;
static int workCount;
static u16 forwarded;
static int guardedBoundary(OverworldActorMotionBoundaryCall *call) {
    __typeof__(actorState) *actor = &actorState;
    forwarded = call->motionIdentity;
    call->decision = OVERWORLD_MOTION_DECISION_ACCEPTED;
    ''' + guard + r'''
    workCount++;
boundary_done:
    call->phase = 0;
    return OVERWORLD_ACTOR_RESULT_OK;
}
static struct { int (*boundary)(OverworldActorMotionBoundaryCall *); } entry = { guardedBoundary };
#define OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY (&entry)
''' + bridge + r'''
static int runCase(int slot, u16 receipt, int expectedAccept) {
    u8 phase = 0;
    int before = workCount;
    /* A was captured before its adapter slot was reused for B. */
    actorState.reservationId = 202;
    wild.movementMotionIdentities[slot] = 202;
    mountState.motionIdentity = 202;
    BOOL accepted = OverworldWildRuntime_ApplyMotionBoundary(slot, 1, 0, NULL, &phase''' + extra + r''');
    int good = forwarded == receipt && accepted == expectedAccept
        && workCount == before + expectedAccept;
    printf("%s role=%s receipt=%u current=202 forwarded=%u accepted=%d work=%d\n",
        good ? "PASS" : "FAIL", slot == OW_WILD_FOLLOWER_SLOT ? "Mounted/Follower" : "Wild",
        receipt, forwarded, accepted, workCount - before);
    return !good;
}
int main(void) {
    int failed = 0;
    for (int role = 0; role < 2; role++) {
        int slot = role ? OW_WILD_FOLLOWER_SLOT : 0;
        failed += runCase(slot, 101, 0);
        failed += runCase(slot, 0, 0);
        failed += runCase(slot, 202, 1);
    }
    return failed != 0;
}
'''


class MotionBoundaryReceiptTests(unittest.TestCase):
    def test_captured_receipt_survives_adapter_slot_reuse(self):
        with tempfile.TemporaryDirectory(prefix="motion-boundary-receipt-") as directory:
            source = Path(directory) / "receipt.c"
            binary = Path(directory) / "receipt"
            source.write_text(harness())
            compile_result = subprocess.run(
                shlex.split(os.environ.get("CC", "cc")) + ["-std=gnu11", str(source), "-o", str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count("PASS role="), 6)


if __name__ == "__main__":
    unittest.main()

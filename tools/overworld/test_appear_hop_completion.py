"""S1 regression for the native spot-emote completion policy.

The live spawn scenario separately proves the current ROM and actor lifecycle.
This host test extracts the production tick body and checks the exact state
transition that used to leave Appear Hop idle until its timeout expired.
"""
from pathlib import Path
import importlib.util
import os
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def production_function(source, name, result_type):
    path = ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py"
    spec = importlib.util.spec_from_file_location("appear_hop_extract", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper.production_function(source, name, result_type)


def harness_source():
    tick = production_function(
        WILD.read_text(), "OverworldWildSpawns_TickSpotEmote", "BOOL")
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND 1
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_SPAWNER_SPOT_STATE_EMOTING 1
#define OW_WILD_SPAWNER_SPOT_STATE_ACTIVE 2
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_PREP 0
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_FREEZE 2
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE 4
#define OW_WILD_SPAWNER_BUBBLE_ID_NONE 0

typedef struct LocalMapObject { BOOL movementActive; } LocalMapObject;
typedef struct Spawn { BOOL active; u16 species; u8 form; LocalMapObject *object; } Spawn;
typedef struct Runtime {
    u8 movementHopStartSoundSuppressFrames[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementEmotePartnerPrepObjects[OW_WILD_MAX_SPAWNS];
    u8 movementEmotePlayHopSound[OW_WILD_MAX_SPAWNS];
} Runtime;
typedef struct OverworldWildSpawnState {
    Spawn spawns[OW_WILD_MAX_SPAWNS];
    u8 movementSpotStates[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteTimers[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteSteps[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteJumpsRemaining[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteEndStates[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteBubbleIds[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteShowBubbleEachJump[OW_WILD_MAX_SPAWNS];
    u8 movementEmotePlayCryOnHop[OW_WILD_MAX_SPAWNS];
    Runtime *movementRuntimeState;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) ((state)->movementRuntimeState)

static BOOL commandFinishes;
static BOOL nextStepStarts;
static unsigned cancelCalls;
static unsigned activeCalls;

static BOOL MapObject_IsSingleMovementActive(LocalMapObject *object)
{ return object->movementActive; }
static void MapObject_ClearSingleMovementActive(LocalMapObject *object)
{ object->movementActive = FALSE; }
static BOOL OverworldWildSpawns_UpdateSpawnerMovementCommandSuppressingHopStartSound(
    OverworldWildSpawnState *state, LocalMapObject *object, int slot)
{ (void)state; (void)object; (void)slot; return commandFinishes; }
static void OverworldWildSpawns_TickHopStartSoundSuppression(
    OverworldWildSpawnState *state, int slot)
{ (void)state; (void)slot; }
static void PlayCry(u16 species, u8 form)
{ (void)species; (void)form; }
static void OverworldWildSpawns_ShowBubble(LocalMapObject *object, u8 bubble)
{ (void)object; (void)bubble; }
static BOOL OverworldWildSpawns_IsLookAroundEmoteStep(u8 step)
{ (void)step; return FALSE; }
static BOOL OverworldWildSpawns_TryStartPendingLookAroundEmoteStep(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; return FALSE; }
static BOOL OverworldWildSpawns_StartNextSpotEmoteStep(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; return nextStepStarts; }
static void OverworldWildSpawns_CancelSpotEmotePresentation(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; cancelCalls++; }
static void OverworldWildSpawns_EnterActiveStateFromGenericAlert(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; activeCalls++; }

/* @TICK@ */

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "check failed at line %d: %s\n", __LINE__, #condition); \
    return 1; } } while (0)

static void Reset(OverworldWildSpawnState *state, Runtime *runtime, LocalMapObject *object)
{
    memset(state, 0, sizeof(*state));
    memset(runtime, 0, sizeof(*runtime));
    memset(object, 0, sizeof(*object));
    state->movementRuntimeState = runtime;
    state->spawns[0].active = TRUE;
    state->spawns[0].object = object;
    state->movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_EMOTING;
    state->movementEmoteEndStates[0] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    state->movementEmoteSteps[0] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    state->movementEmoteTimers[0] = 51;
    object->movementActive = TRUE;
    commandFinishes = TRUE;
    nextStepStarts = TRUE;
    cancelCalls = activeCalls = 0;
}

int main(void)
{
    OverworldWildSpawnState state;
    Runtime runtime;
    LocalMapObject object;

    Reset(&state, &runtime, &object);
    state.movementEmoteJumpsRemaining[0] = 1;
    CHECK(OverworldWildSpawns_TickSpotEmote(&state, 0, &object));
    CHECK(state.movementSpotStates[0] == OW_WILD_SPAWNER_SPOT_STATE_CHILL);
    CHECK(state.movementEmoteTimers[0] == 0 && cancelCalls == 1);

    Reset(&state, &runtime, &object);
    state.movementEmoteJumpsRemaining[0] = 2;
    CHECK(OverworldWildSpawns_TickSpotEmote(&state, 0, &object));
    CHECK(state.movementSpotStates[0] == OW_WILD_SPAWNER_SPOT_STATE_EMOTING);
    CHECK(state.movementEmoteJumpsRemaining[0] == 1 && cancelCalls == 0);

    Reset(&state, &runtime, &object);
    commandFinishes = FALSE;
    state.movementEmoteJumpsRemaining[0] = 1;
    state.movementEmoteTimers[0] = 1;
    CHECK(OverworldWildSpawns_TickSpotEmote(&state, 0, &object));
    CHECK(state.movementSpotStates[0] == OW_WILD_SPAWNER_SPOT_STATE_CHILL);
    CHECK(cancelCalls == 1);

    Reset(&state, &runtime, &object);
    state.movementEmoteJumpsRemaining[0] = 0;
    CHECK(OverworldWildSpawns_TickSpotEmote(&state, 0, &object));
    CHECK(state.movementSpotStates[0] == OW_WILD_SPAWNER_SPOT_STATE_EMOTING);
    CHECK(state.movementEmoteTimers[0] == 50 && cancelCalls == 0);

    Reset(&state, &runtime, &object);
    state.movementEmoteJumpsRemaining[0] = 1;
    state.movementEmoteEndStates[0] = OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;
    CHECK(OverworldWildSpawns_TickSpotEmote(&state, 0, &object));
    CHECK(state.movementSpotStates[0] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE);
    CHECK(activeCalls == 1);

    puts("appear-hop completion regression: passed");
    return 0;
}
'''.replace("/* @TICK@ */", tick)


class AppearHopCompletionTests(unittest.TestCase):
    def test_production_tick_releases_on_final_restore(self):
        with tempfile.TemporaryDirectory(prefix="appear-hop-completion-") as directory:
            source = Path(directory) / "appear_hop.c"
            binary = Path(directory) / "appear_hop"
            source.write_text(harness_source())
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                       "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("appear-hop completion regression: passed", result.stdout)


if __name__ == "__main__":
    unittest.main()

"""Host regression checks for deferred distance despawn.

The C rules under test are extracted from the shipped translation units. Run:

    python3 -m unittest tools.overworld.test_distance_despawn -v
"""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
SPAWNS_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def extract_function(source: str, name: str, returns: str) -> str:
    pattern = re.compile(
        r"\b(?:static\s+)?"
        + re.escape(returns)
        + r"\b[^;{}]*?\b"
        + re.escape(name)
        + r"\s*\([^;{}]*\)\s*\{"
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected one definition of {name}")
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            start = source.index(name, match.start(), match.end())
            return f"static {returns} " + source[start : end + 1]
    raise ValueError(f"unterminated {name}")


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef int BOOL;
typedef int16_t s16;
typedef uint8_t u8;
typedef uint16_t u16;

#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_DISTANCE_DESPAWN_TILES 16
#define OW_WILD_DISTANCE_DESPAWN_SAMPLES 2
#define OW_WILD_SPAWN_ENTRY_NONE 0
#define OW_WILD_SPAWN_ENTRY_MOVE 1
#define OW_WILD_SPAWN_ENTRY_HOP 2
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) ((u16)(1u << (slot)))

typedef struct LocalMapObject {
    int x;
    int y;
} LocalMapObject;

typedef struct PlayerAvatar {
    int x;
    int y;
} PlayerAvatar;

typedef struct FieldSystem {
    PlayerAvatar *playerAvatar;
} FieldSystem;

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u16 encounterGeneration;
    u8 active;
    u8 shiny;
} OverworldWildSpawn;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    u8 movementSpawnRunActive[OW_WILD_MAX_SPAWNS];
    void *movementRuntimeState;
} OverworldWildSpawnState;

typedef struct OverworldWildPresentationState {
    s16 lastKnownX[OW_WILD_MAX_SPAWNS];
    s16 lastKnownY[OW_WILD_MAX_SPAWNS];
    u8 farSamples[OW_WILD_MAX_SPAWNS];
    u16 managerRestoreMask;
    u16 distanceDespawnPendingMask;
} OverworldWildPresentationState;

typedef struct OverworldWildDespawnTelemetry { int unused; } OverworldWildDespawnTelemetry;
typedef void (*OverworldWildHelperResetSlotFunc)(OverworldWildSpawnState *, int, BOOL);

#define OW_WILD_DESPAWN_REASON_DISTANCE 3

static BOOL host_exact_object = TRUE;

static BOOL OverworldWildHelper_IsExactObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    (void)fieldSystem;
    return host_exact_object && state->spawns[slot].object != NULL;
}

static int MapObject_GetCurrentX(LocalMapObject *object) { return object->x; }
static int MapObject_GetCurrentY(LocalMapObject *object) { return object->y; }
static int GetPlayerXCoord(PlayerAvatar *avatar) { return avatar->x; }
static int GetPlayerYCoord(PlayerAvatar *avatar) { return avatar->y; }

static int host_remove_count;
static BOOL OverworldWildHelper_RemoveEncounter(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    int reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    (void)fieldSystem;
    (void)state;
    (void)presentation;
    (void)telemetry;
    (void)slot;
    (void)expectedGeneration;
    (void)reason;
    (void)distance;
    (void)resetSlot;
    host_remove_count++;
    return TRUE;
}
'''


DRIVER = r'''
#define CHECK(condition, message) do { \
    if (!(condition)) { fprintf(stderr, "%s\n", message); return 1; } \
} while (0)

int main(void)
{
    FieldSystem field;
    PlayerAvatar player;
    LocalMapObject object;
    OverworldWildSpawnState state;
    OverworldWildPresentationState presentation;
    OverworldWildDespawnTelemetry telemetry;
    u8 distance = 0;

    memset(&state, 0, sizeof(state));
    memset(&presentation, 0, sizeof(presentation));
    memset(&telemetry, 0, sizeof(telemetry));
    player.x = 0;
    player.y = 0;
    object.x = 17;
    object.y = 0;
    field.playerAvatar = &player;
    state.spawns[0].active = TRUE;
    state.spawns[0].object = &object;
    state.spawns[0].encounterGeneration = 1;

    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, TRUE, &distance),
        "first moving far sample must defer removal");
    CHECK(presentation.farSamples[0] == 1 && distance == 17,
        "first moving far sample must be retained");
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, TRUE, &distance),
        "second moving far sample must still defer removal");
    CHECK(presentation.farSamples[0] == 2
            && presentation.distanceDespawnPendingMask == 1,
        "moving actor must reach confirmed-far state");

    CHECK(OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, FALSE, &distance),
        "terminal actor must consume retained far samples");

    object.x = 16;
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, FALSE, &distance),
        "exactly sixteen tiles must not despawn");
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0,
        "returning in range must cancel pending removal");

    object.x = 17;
    presentation.farSamples[0] = 2;
    presentation.distanceDespawnPendingMask = 1;
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, TRUE, FALSE, &distance),
        "hard protection must suppress removal");
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0,
        "hard protection must clear stale far samples");

    presentation.farSamples[0] = 1;
    presentation.distanceDespawnPendingMask = 1;
    state.movementSpawnRunActive[0] = OW_WILD_SPAWN_ENTRY_MOVE;
    OverworldWildHelper_DespawnFarEncounters(
        &field, &state, &presentation, &telemetry, 0, 0, NULL);
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0
            && host_remove_count == 0,
        "Move From Off Screen must stay hard protected");
    presentation.farSamples[0] = 1;
    presentation.distanceDespawnPendingMask = 1;
    state.movementSpawnRunActive[0] = OW_WILD_SPAWN_ENTRY_HOP;
    OverworldWildHelper_DespawnFarEncounters(
        &field, &state, &presentation, &telemetry, 0, 0, NULL);
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0
            && host_remove_count == 0,
        "Hop From Off Screen must stay hard protected");
    state.movementSpawnRunActive[0] = OW_WILD_SPAWN_ENTRY_NONE;

    host_exact_object = FALSE;
    presentation.farSamples[0] = 2;
    presentation.distanceDespawnPendingMask = 1;
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, FALSE, &distance),
        "identity mismatch must suppress distance removal");
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0,
        "identity mismatch must clear stale far samples");
    return 0;
}
'''


WRAPPER_PRELUDE = PRELUDE.replace(
    "void *movementRuntimeState;", "void *movementRuntimeState; u16 captureTargetMask; u16 movementInProgressMask;"
).replace("host_remove_count++;", "host_remove_count++; host_remove_slots |= 1u << slot; state->spawns[slot].active = FALSE;").replace(
    "static int host_remove_count;", "static int host_remove_count; static u16 host_remove_slots;"
) + r"""
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)(state)->movementRuntimeState)
typedef struct OverworldWildOverlayRuntimeState {
    struct { u16 targetMask; u16 carrierMask; } throwState;
    OverworldWildPresentationState spawnPresentations;
    OverworldWildDespawnTelemetry despawnTelemetry;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildHelperOverlayEntry {
    void (*despawnFarEncounters)(FieldSystem *, OverworldWildSpawnState *,
        OverworldWildPresentationState *, OverworldWildDespawnTelemetry *,
        u16, u16, OverworldWildHelperResetSlotFunc);
} OverworldWildHelperOverlayEntry;
static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void);
static void OverworldWildSpawns_ResetSlotState(OverworldWildSpawnState *s, int slot, BOOL remove) {
    (void)s; (void)slot; (void)remove;
}
"""

WRAPPER_DRIVER = r"""
#define CHECK(condition, message) do { \
    if (!(condition)) { fprintf(stderr, "%s\n", message); return 1; } \
} while (0)
static const OverworldWildHelperOverlayEntry host_helper = { OverworldWildHelper_DespawnFarEncounters };
static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void) { return &host_helper; }
int main(void) {
    OverworldWildSpawnState state = {0};
    OverworldWildOverlayRuntimeState runtime = {0};
    LocalMapObject objects[10] = {0};
    PlayerAvatar player = {0};
    FieldSystem field = { &player };
    int i;
    state.movementRuntimeState = &runtime;
    for (i=0;i<8;i++) {
        state.spawns[i].active=TRUE; state.spawns[i].object=&objects[i];
        state.spawns[i].encounterGeneration=1; objects[i].x=20;
    }
    runtime.throwState.carrierMask=1u<<0;
    runtime.throwState.targetMask=1u<<1;
    state.captureTargetMask=1u<<4;
    state.spawns[3].shiny=TRUE;
    state.movementSpawnRunActive[5]=OW_WILD_SPAWN_ENTRY_HOP;
    state.movementInProgressMask=1u<<2;
    OverworldWildSpawns_DespawnFarMons(&state,&field);
    CHECK(runtime.spawnPresentations.farSamples[2]==1 && runtime.spawnPresentations.farSamples[6]==1,
          "unrelated claim cleared first far samples");
    CHECK(host_remove_count==0 && state.movementInProgressMask==(1u<<2),
          "first sample removed actor or changed accepted motion");
    objects[6].x=16;
    OverworldWildSpawns_DespawnFarMons(&state,&field);
    CHECK(runtime.spawnPresentations.farSamples[2]==2 && runtime.spawnPresentations.distanceDespawnPendingMask==(1u<<2),
          "moving unrelated actor did not reach two samples");
    CHECK(runtime.spawnPresentations.farSamples[6]==0 && host_remove_count==0,
          "return in range did not clear samples");
    CHECK(state.movementInProgressMask==(1u<<2), "cleanup cancelled accepted motion");
    state.movementInProgressMask=0; /* native terminal seam, not product cancellation */
    OverworldWildSpawns_DespawnFarMons(&state,&field);
    CHECK(host_remove_count==1 && host_remove_slots==(1u<<2), "terminal unrelated actor was not removed");
    for (i=0;i<8;i++) if (i!=2 && i!=6) {
        CHECK(runtime.spawnPresentations.farSamples[i]==0 && state.spawns[i].active,
              "carrier/cargo/shiny/capture/startup/follower lost protection");
    }
    /* Existing exact native-object gate cannot retain samples for a stale owner. */
    objects[6].x=20; runtime.spawnPresentations.farSamples[6]=2;
    runtime.spawnPresentations.distanceDespawnPendingMask|=1u<<6;
    host_exact_object=FALSE;
    OverworldWildSpawns_DespawnFarMons(&state,&field);
    CHECK(runtime.spawnPresentations.farSamples[6]==0 && (runtime.spawnPresentations.distanceDespawnPendingMask&(1u<<6))==0,
          "stale object retained pending distance removal");
    CHECK(host_remove_count==1, "stale object requested removal");
    return 0;
}
"""



RESET_PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef int16_t s16;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK 1
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED 0
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) ((u16)(1u << (slot)))
#define MAP_NOTHING 1
#define SPECIES_NONE 0
#define CUSTOM_FOLLOWER_PARTY_SLOT_NONE -1
#define OW_WILD_BEHAVIOR_CLASS_DEFAULT 0
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
typedef struct LocalMapObject { int deleted; } LocalMapObject;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildSpawn {
    LocalMapObject *object; u32 personality; u16 encounterGeneration;
    int mapId,species,form,level,terrain,shiny,active;
} OverworldWildSpawn;
typedef struct OverworldWildPresentationState {
    s16 lastKnownX[10],lastKnownY[10]; u8 farSamples[10];
    u16 managerRestoreMask,distanceDespawnPendingMask;
} OverworldWildPresentationState;
typedef struct Resident { u16 savedHp[10]; } Resident;
typedef struct OverworldWildOverlayRuntimeState {
    Resident *residentData; u8 playerBallCatchValues[10],movementBehaviorLimitKeys[10];
    OverworldWildPresentationState spawnPresentations;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[10]; void *mapObjectMan; void *movementRuntimeState;
    int activeFollowerPartySlot,movementQueuedBattleSlot,pendingSlot;
    u16 captureTargetMask; u8 movementBehaviorClasses[10],movementActorControlModes[10];
    s16 movementSpawnRunTargetX[10],movementSpawnRunTargetY[10];
    u8 movementSpawnRunActive[10]; LocalMapObject *movementMankeyTreeTopProxyObjects[10];
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(s) ((OverworldWildOverlayRuntimeState *)(s)->movementRuntimeState)
static FieldSystem *gFieldSysPtr;
static void OverworldWildSpawns_ResetSlotMovementCommand(OverworldWildSpawnState *s,int i,BOOL b) {(void)s;(void)i;(void)b;}
static void OverworldWildSpawns_SetNativeShadowSuppressed(LocalMapObject *o,BOOL b) {(void)o;(void)b;}
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f,OverworldWildSpawn *s) {(void)f;return s->active && s->object;}
static void OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride(int i,LocalMapObject *o) {(void)i;(void)o;}
static void OverworldActorAppearance_ForgetLoaded(void *m,int i) {(void)m;(void)i;}
static void OverworldWildSpawns_ClearMankeyTreeTopProxyObject(OverworldWildSpawnState *s,int i,BOOL b) {(void)s;(void)i;(void)b;}
static void OverworldWildSpawns_ClearMankeyTreeTopCache(OverworldWildSpawnState *s,int i) {(void)s;(void)i;}
static void OverworldWildSpawns_ClearCachedBehaviorProfile(OverworldWildSpawnState *s,int i) {(void)s;(void)i;}
static void OverworldWildSpawns_ClearConditionSlot(OverworldWildSpawnState *s,int i) {(void)s;(void)i;}
static void OverworldWildSpawns_ResetPendingBattle(OverworldWildSpawnState *s) {s->pendingSlot=-1;}
typedef struct OverworldWildDespawnTelemetry { int unused; } OverworldWildDespawnTelemetry;
typedef enum OverworldWildDespawnAuthorization {
    OW_WILD_DESPAWN_DENIED, OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT, OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY
} OverworldWildDespawnAuthorization;
typedef int OverworldWildDespawnReason;
#define OW_WILD_DESPAWN_ACTION_DELETE_OBJECT 1
#define OW_WILD_DESPAWN_ACTION_CLEAR_LOGICAL_ONLY 2
#define OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED 3
typedef void (*OverworldWildHelperResetSlotFunc)(OverworldWildSpawnState *,int,BOOL);
static OverworldWildDespawnAuthorization OverworldWildHelper_AuthorizeDespawn(FieldSystem *f,OverworldWildSpawnState *s,
    OverworldWildPresentationState *p,int i,u16 gen,OverworldWildDespawnReason r,LocalMapObject **o) {
    (void)f;(void)p;(void)r;
    if (!s->spawns[i].active || s->spawns[i].encounterGeneration!=gen) return OW_WILD_DESPAWN_DENIED;
    *o=s->spawns[i].object;
    return *o ? OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT : OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
}
static void OverworldWildHelper_RecordDespawnEvent(FieldSystem *f,OverworldWildSpawnState *s,OverworldWildPresentationState *p,
    OverworldWildDespawnTelemetry *t,int i,OverworldWildDespawnReason r,int a,u8 d) {
    (void)f;(void)s;(void)p;(void)t;(void)i;(void)r;(void)a;(void)d;
}
static void DeleteMapObject(LocalMapObject *o) {o->deleted=1;}
"""

RESET_DRIVER = r"""
#define CHECK(c,m) do { if (!(c)) { fprintf(stderr,"%s\n",m); return 1; } } while (0)
int main(void) {
    OverworldWildSpawnState s={0}; OverworldWildOverlayRuntimeState r={0}; Resident data={0};
    FieldSystem f={0}; OverworldWildDespawnTelemetry t={0}; LocalMapObject o={0};
    s.movementRuntimeState=&r; r.residentData=&data; gFieldSysPtr=&f;
    for(int i=0;i<10;i++) {
        u16 bit=(u16)(1u<<i), others=(u16)(1023^bit);
        s.spawns[i].active=TRUE;s.spawns[i].object=&o;s.spawns[i].encounterGeneration=2;
        r.spawnPresentations.managerRestoreMask=1023;r.spawnPresentations.distanceDespawnPendingMask=1023;
        memset(r.spawnPresentations.farSamples,2,10);data.savedHp[i]=100;
        CHECK(!OverworldWildHelper_RemoveEncounter(&f,&s,&r.spawnPresentations,&t,i,1,3,18,OverworldWildSpawns_ResetSlotState),
              "stale generation reached reset");
        CHECK(r.spawnPresentations.distanceDespawnPendingMask==1023 && r.spawnPresentations.farSamples[i]==2,
              "denied deletion changed pending state");
        o.deleted=0;
        CHECK(OverworldWildHelper_RemoveEncounter(&f,&s,&r.spawnPresentations,&t,i,2,3,18,OverworldWildSpawns_ResetSlotState),
              "current deletion failed");
        CHECK(r.spawnPresentations.distanceDespawnPendingMask==others,
              "removed slot retained pending distance bit");
        CHECK(r.spawnPresentations.managerRestoreMask==others && r.spawnPresentations.farSamples[i]==0
              && !s.spawns[i].active && !s.spawns[i].object && data.savedHp[i]==0 && o.deleted,
              "reset/delete owner or distance cleanup changed");
        for(int j=0;j<10;j++) if(j!=i) CHECK(r.spawnPresentations.farSamples[j]==2,"other slot lost far history");
        /* Reuse cannot inherit the old pending marker; setting a later sample
           in another slot must remain independent of this repeated reset. */
        s.spawns[i].active=TRUE;s.spawns[i].object=&o;s.spawns[i].encounterGeneration=3;
        OverworldWildSpawns_ResetSlotState(&s,i,FALSE);
        CHECK(r.spawnPresentations.distanceDespawnPendingMask==others,"reused slot inherited pending bit");
    }
    return 0;
}
"""

class DistanceDespawnRegression(unittest.TestCase):
    def test_native_remove_and_reset_clear_only_the_removed_slot_pending_bit(self):
        source = RESET_PRELUDE + extract_function(SPAWNS_SOURCE.read_text(),
            "OverworldWildSpawns_ResetSlotState", "void") + extract_function(HELPER_SOURCE.read_text(),
            "OverworldWildHelper_RemoveEncounter", "BOOL") + RESET_DRIVER
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "reset_distance_pending.c"
            executable = Path(directory) / "reset_distance_pending"
            source_path.write_text(source)
            compiled = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                str(source_path), "-o", str(executable)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_cargo_wrapper_protects_only_participants_and_defers_accepted_motion(self):
        helper = HELPER_SOURCE.read_text()
        wild = SPAWNS_SOURCE.read_text()
        source = WRAPPER_PRELUDE + "\n".join([
            extract_function(helper, "OverworldWildHelper_ConfirmDistanceDespawn", "BOOL"),
            extract_function(helper, "OverworldWildHelper_DespawnFarEncounters", "void"),
            extract_function(wild, "OverworldWildSpawns_GetThrowParticipantMask", "u16"),
            extract_function(wild, "OverworldWildSpawns_DespawnFarMons", "void"),
        ]) + WRAPPER_DRIVER
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "cargo_distance_wrapper.c"
            executable = Path(directory) / "cargo_distance_wrapper"
            source_path.write_text(source)
            compiled = subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source_path), "-o", str(executable)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_moving_samples_defer_and_offscreen_entry_is_hard_protected(self):
        helper = HELPER_SOURCE.read_text()
        source = (
            PRELUDE
            + extract_function(
                helper, "OverworldWildHelper_ConfirmDistanceDespawn", "BOOL"
            )
            + "\n"
            + extract_function(
                helper, "OverworldWildHelper_DespawnFarEncounters", "void"
            )
            + DRIVER
        )
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "distance_despawn.c"
            executable = Path(directory) / "distance_despawn"
            source_path.write_text(source)
            compiled = subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source_path), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_terminal_boundary_blocks_follow_on_movement(self):
        source = SPAWNS_SOURCE.read_text()
        walk = extract_function(
            source,
            "OverworldWildSpawns_HandleFinishedWalkMovement",
            "BOOL",
        )
        terminal = extract_function(
            source,
            "OverworldWildSpawns_HandleFinishedMovementCommand",
            "void",
        )
        self.assertLess(
            walk.index("stopAfterCommit"),
            walk.index("OverworldWildSpawns_ExecuteWalkPolicy"),
        )
        self.assertIn("distanceDespawnPendingMask", terminal)
        self.assertIn(
            "OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE", terminal
        )
        first_terminal_gate = terminal.index("pendingDistanceDespawn")
        self.assertLess(
            first_terminal_gate,
            terminal.index("OverworldWildSpawns_RunChainReposition"),
        )
        self.assertLess(
            terminal.index("pendingDistanceDespawn", first_terminal_gate + 1),
            terminal.index("OverworldWildSpawns_ApplyUniversalChainMovementPause"),
        )

    def test_pending_slot_cannot_restart_in_same_frame(self):
        source = SPAWNS_SOURCE.read_text()
        tick = extract_function(
            source,
            "OverworldWildSpawns_TickMovementParams",
            "void",
        )
        pending_guard = tick.index("distanceDespawnPendingMask")
        first_ai_action = tick.index("OverworldWildSpawns_EnterAggroState")
        self.assertLess(pending_guard, first_ai_action)
        self.assertIn("continue;", tick[pending_guard:first_ai_action])


if __name__ == "__main__":
    unittest.main()

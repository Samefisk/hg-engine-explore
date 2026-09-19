#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef int BOOL;
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;
typedef int16_t s16;
#define TRUE 1
#define FALSE 0
#define SPECIES_NONE 0
#define BIT_VANISH (1u << 18)
#define MAPOBJECTFLAG_ACTIVE 1u
#define MAPOBJECTFLAG_UNK25 (1u << 25)
#define OW_WILD_OBJECT_ID_START 0xE0
#define OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT 2074
#define SEQ_SE_PL_KIRAKIRA 0
#define OW_WILD_SPAWNER_PERF_DIAGNOSTICS 1
#define OW_WILD_PERF_INC(value) ((value)++)
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
/* @CONSTANTS@ */

typedef struct LocalMapObject { u32 flags, id, scriptId, mapId; } LocalMapObject;
typedef struct FieldSystem FieldSystem;
typedef struct { u32 object_count; LocalMapObject *objects; FieldSystem *fsys; } MapObjectMan;
typedef struct { u32 mapId; } Location;
struct FieldSystem { MapObjectMan *mapObjectMan; Location *location; void *taskman; };
typedef struct { LocalMapObject *object; BOOL active; u32 objectId; } Spawn;
typedef struct { u16 managerRestoreMask; } OverworldWildPresentationState;
typedef struct {
    OverworldWildPresentationState spawnPresentations;
    LocalMapObject *movementEmotePartnerPrepObjects[OW_WILD_MAX_SPAWNS];
} Runtime;
typedef Runtime OverworldWildSpawnRuntimePrefix;
typedef struct {
    Spawn spawns[OW_WILD_MAX_SPAWNS];
    MapObjectMan *mapObjectMan;
    LocalMapObject *mapObjects;
    Runtime *movementRuntimeState;
    FieldSystem *movementFieldSystem;
    u32 mapId;
    BOOL shinySpawned;
    int pendingSlot, movementQueuedBattleSlot;
    LocalMapObject *movementMankeyTreeTopProxyObjects[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementTeleportFlickerObjects[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) ((state)->movementRuntimeState)
typedef int OverworldWildSpawnTerrain;
typedef struct { int startX, startY; } OverworldWildSpawnPosition;
typedef struct {
    s16 targetX, targetY, startX, startY;
    u8 locomotion, hopDirection;
} OverworldWildSpawnStartup;
typedef struct { u16 species; u8 level, form; u32 personality; } OverworldWildRolledEncounter;
typedef struct { int range; } OverworldWildBehaviorProfile;
typedef struct { int unused; } OverworldWildBehaviorPrimitives;
typedef struct {
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u8 behaviorClass, behaviorLimitKey;
} BehaviorResolveResult;
typedef struct {
    OverworldWildRolledEncounter encounter;
    BehaviorResolveResult behaviorResolution;
    OverworldWildSpawnPosition position;
    BOOL shiny;
    u8 playerBallCatchValue;
    OverworldWildSpawnStartup startup;
    int savedShinySlot;
} OverworldWildPreparedSpawn;

static LocalMapObject objects[64];
static Location location;
static MapObjectMan manager;
static FieldSystem field;
static OverworldWildSpawnState state;
static Runtime runtime;
static OverworldWildPreparedSpawn prepared;
static int assertions, deletes, creates, resets, startup_ok, creation_ok;
static int create_x, create_y, height_x, height_y;
static int sOverworldWildPerfMapObjectDeletesThisFrame;
static LocalMapObject *deleted[64];
#define CHECK(expr) do { assertions++; if (!(expr)) { \
    fprintf(stderr, "spawn identity invariant failed at %d: %s\n", __LINE__, #expr); return 1; } } while (0)

static void DeleteMapObject(LocalMapObject *object) {
    if (deletes >= 64 || !(object->flags & MAPOBJECTFLAG_ACTIVE)) abort();
    deleted[deletes++] = object;
    memset(object, 0, sizeof(*object));
}
static u32 OverworldWildSpawns_GetSpriteIDForSlot(u16 species, u8 form, u32 pid, int slot) {
    (void)form; (void)pid; (void)slot; return species;
}
static LocalMapObject *OverworldWildSpawns_CreateObject(FieldSystem *f,
    int x, int y, u32 sprite, BOOL shiny, const OverworldWildBehaviorPrimitives *b) {
    (void)sprite; (void)shiny; (void)b;
    create_x = x; create_y = y;
    creates++;
    if (!creation_ok) return NULL;
    for (u32 i = 0; i < f->mapObjectMan->object_count; i++) {
        LocalMapObject *o = &f->mapObjectMan->objects[i];
        if (!(o->flags & MAPOBJECTFLAG_ACTIVE)) {
            *o = (LocalMapObject){MAPOBJECTFLAG_ACTIVE, 0, 0, f->location->mapId};
            return o;
        }
    }
    return NULL;
}
static void OverworldWildSpawns_SetObjectPassThrough(LocalMapObject *o, BOOL b) { (void)o; (void)b; }
static void MapObject_SetID(LocalMapObject *o, u32 id) { o->id = id; }
static void MapObject_SetScript(LocalMapObject *o, u32 id) { o->scriptId = id; }
static void OverworldWildSpawns_ApplyMovementRange(LocalMapObject *o, int range) { (void)o; (void)range; }
static void OverworldWildSpawns_ApplyPokemonRenderParams(LocalMapObject *o,
    u16 species, u8 form, u32 sprite, BOOL shiny) { (void)o; (void)species; (void)form; (void)sprite; (void)shiny; }
static BOOL OverworldWildSpawns_IsCanopyHopper(const OverworldWildBehaviorPrimitives *p) { (void)p; return FALSE; }
static void OverworldWildSpawns_ClearObjectFlags(LocalMapObject *o, u32 flags) { o->flags &= ~flags; }
static void OverworldWildSpawns_ApplySurfaceHeight(FieldSystem *f, LocalMapObject *o, int x, int y) {
    (void)f; (void)o; height_x = x; height_y = y;
}
static void OverworldWildSpawns_InitSpawnSlotState(OverworldWildSpawnState *s, FieldSystem *f,
    OverworldWildSpawnTerrain terrain, int slot, LocalMapObject *o, const OverworldWildRolledEncounter *encounter,
    BOOL shiny, u8 behaviorClass, u8 behaviorLimitKey, u8 catchValue) {
    (void)f; (void)terrain; (void)encounter; (void)shiny; (void)behaviorClass; (void)behaviorLimitKey; (void)catchValue;
    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS) abort();
    s->spawns[slot] = (Spawn){o, TRUE, OW_WILD_OBJECT_ID_START + slot};
}
static BOOL OverworldWildSpawns_StartSpawnStartup(OverworldWildSpawnState *s, FieldSystem *f,
    int slot, const OverworldWildPreparedSpawn *prepared) { (void)s; (void)f; (void)slot; (void)prepared; return startup_ok; }
static void OverworldWildSpawns_ResetSlotState(OverworldWildSpawnState *s, int slot, BOOL aux) {
    (void)aux; resets++; memset(&s->spawns[slot], 0, sizeof(Spawn));
}
static void OverworldWildSpawns_ClearSavedShiny(OverworldWildSpawnState *s, int slot) { (void)s; (void)slot; }
static void PlaySE(int sound) { (void)sound; }
/* @APPLY_SETUP@ */
/* @PREPARE_IDENTITY@ */
/* @SPAWN@ */

static void reset(void) {
    memset(objects, 0, sizeof(objects)); memset(&state, 0, sizeof(state));
    memset(&runtime, 0, sizeof(runtime)); memset(deleted, 0, sizeof(deleted));
    location.mapId = 33; manager = (MapObjectMan){64, objects, &field};
    field = (FieldSystem){&manager, &location, NULL};
    state.mapObjectMan = &manager; state.mapObjects = objects; state.mapId = 33;
    state.movementRuntimeState = &runtime;
    state.pendingSlot = state.movementQueuedBattleSlot = -1;
    prepared = (OverworldWildPreparedSpawn){0};
    prepared.encounter.species = 56; prepared.encounter.level = 10; prepared.savedShinySlot = -1;
    prepared.position.startX = 30; prepared.position.startY = 40;
    prepared.startup.targetX = 30; prepared.startup.targetY = 40;
    prepared.startup.startX = 14; prepared.startup.startY = 40;
    deletes = creates = resets = 0; startup_ok = creation_ok = TRUE;
    create_x = create_y = height_x = height_y = -1;
    sOverworldWildPerfMapObjectDeletesThisFrame = 0;
}
static void orphan(int index, int slot) {
    objects[index] = (LocalMapObject){MAPOBJECTFLAG_ACTIVE, OW_WILD_OBJECT_ID_START + slot, 2074, 33};
}
static LocalMapObject *stock_first(int slot) {
    for (u32 i = 0; i < manager.object_count; i++)
        if ((objects[i].flags & MAPOBJECTFLAG_ACTIVE) && !(objects[i].flags & MAPOBJECTFLAG_UNK25)
            && objects[i].id == OW_WILD_OBJECT_ID_START + (u32)slot) return &objects[i];
    return NULL;
}
static BOOL spawn(int slot) { return OverworldWildSpawns_SpawnPreparedEncounter(&state, &field, 0, slot, &prepared); }

int main(void) {
    reset(); CHECK(spawn(0));
    CHECK(create_x == 30 && create_y == 40);
    CHECK(height_x == 30 && height_y == 40);
    reset(); prepared.startup.locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN;
    CHECK(spawn(0));
    CHECK(create_x == 14 && create_y == 40);
    CHECK(height_x == 14 && height_y == 40);
    /* The actual observed failure: a restored earlier ID hides a new actor. */
    for (int slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        reset();
        for (int i = 0; i < 18; i++) objects[i] = (LocalMapObject){1, (u32)i, 18, 33};
        orphan(2, slot); orphan(5, slot);
        CHECK(spawn(slot));
        CHECK(stock_first(slot) == state.spawns[slot].object);
        CHECK(deletes == 2); CHECK(creates == 1);
        CHECK(sOverworldWildPerfMapObjectDeletesThisFrame == 2);
        CHECK(deleted[0] == &objects[2] && deleted[1] == &objects[5]);
    }
    reset(); orphan(2, 7); objects[2].flags |= MAPOBJECTFLAG_UNK25; objects[2].mapId = 99;
    CHECK(spawn(7)); CHECK(deletes == 1); CHECK(stock_first(7) == state.spawns[7].object);
    reset(); orphan(2, 7); objects[2].flags = 0;
    CHECK(spawn(7)); CHECK(deletes == 0);
    reset(); orphan(2, 6); objects[3] = (LocalMapObject){1, 1, 18, 33};
    CHECK(spawn(7)); CHECK(deletes == 0); CHECK(objects[2].id == 0xE6 && objects[3].id == 1);
    /* Preflight is non-destructive even when a later matching row conflicts. */
    reset(); orphan(2, 7); orphan(60, 7); objects[60].scriptId = 18;
    CHECK(!spawn(7)); CHECK(deletes == 0 && creates == 0); CHECK(objects[2].flags == 1);
    for (int mode = 0; mode < 8; mode++) {
        reset(); orphan(2, 7);
        if (mode == 0) state.spawns[7].active = TRUE;
        if (mode == 1) state.spawns[7].object = &objects[2];
        if (mode == 2) state.spawns[6].object = &objects[2];
        if (mode == 3) runtime.spawnPresentations.managerRestoreMask = 1 << 7;
        if (mode == 4) state.movementMankeyTreeTopProxyObjects[6] = &objects[2];
        if (mode == 5) state.movementTeleportFlickerObjects[6] = &objects[2];
        if (mode == 6) runtime.movementEmotePartnerPrepObjects[6] = &objects[2];
        if (mode == 7) { state.spawns[6].active = TRUE; state.spawns[6].objectId = 0xE7; }
        CHECK(!spawn(7)); CHECK(deletes == 0 && creates == 0);
    }
    for (int mode = 0; mode < 12; mode++) {
        reset(); orphan(2, 7);
        if (mode == 0) manager.object_count = 0;
        if (mode == 1) manager.object_count = 65;
        if (mode == 2) manager.objects = NULL;
        if (mode == 3) field.mapObjectMan = NULL;
        if (mode == 4) field.location = NULL;
        if (mode == 5) state.mapId = 99;
        if (mode == 6) state.mapObjects = NULL;
        if (mode == 7) state.mapObjectMan = NULL;
        if (mode == 8) state.movementRuntimeState = NULL;
        if (mode == 9) manager.fsys = NULL;
        if (mode == 10) state.pendingSlot = 7;
        if (mode == 11) state.movementQueuedBattleSlot = 7;
        CHECK(!spawn(7)); CHECK(deletes == 0 && creates == 0);
    }
    reset(); CHECK(!spawn(-1)); CHECK(!spawn(OW_WILD_MAX_SPAWNS)); CHECK(creates == 0);
    reset(); manager.object_count = 1; orphan(0, 7);
    CHECK(spawn(7)); CHECK(deletes == 1); CHECK(state.spawns[7].object == &objects[0]);
    reset(); CHECK(!OverworldWildSpawns_SpawnPreparedEncounter(NULL, &field, 0, 7, &prepared));
    CHECK(!OverworldWildSpawns_SpawnPreparedEncounter(&state, NULL, 0, 7, &prepared));
    CHECK(!OverworldWildSpawns_SpawnPreparedEncounter(&state, &field, 0, 7, NULL));
    prepared.encounter.species = 0; CHECK(!spawn(7));
    prepared.encounter.species = 56; prepared.encounter.level = 0; CHECK(!spawn(7)); CHECK(creates == 0);
    reset(); CHECK(OverworldWildSpawnIdentity_PrepareSlot(&field, &state, 7, NULL) == -1);
    reset(); for (int i = 0; i < 64; i++) objects[i] = (LocalMapObject){1, (u32)i, 18, 33};
    orphan(63, 9); CHECK(spawn(9)); CHECK(deletes == 1); CHECK(state.spawns[9].object == &objects[63]);
    reset(); orphan(2, 7); creation_ok = FALSE;
    CHECK(!spawn(7)); CHECK(deletes == 1); CHECK(!state.spawns[7].active);
    reset(); orphan(2, 7); startup_ok = FALSE;
    CHECK(!spawn(7)); CHECK(deletes == 2); CHECK(resets == 1); CHECK(!state.spawns[7].active);
    CHECK(sOverworldWildPerfMapObjectDeletesThisFrame == 2);
    printf("PASS %d actual spawn identity assertions across %d slots\n", assertions, OW_WILD_MAX_SPAWNS);
    return 0;
}

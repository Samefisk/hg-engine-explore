/* Filled by verify_overworld_actor_view.py with unedited production bodies.
 * Public actor/motion values are real. Engine objects and fixed-address entry
 * tables below are host stubs, not claims about the Nintendo DS memory layout.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_actor_system.h"
#include "overworld_motion_model.h"

/* @ENGINE_CONSTANTS@ */

typedef int BOOL;
typedef struct LocalMapObject {
    u32 flags;
    s32 xCurr;
    s32 yCurr;
    s32 posVec[3];
} LocalMapObject;
typedef struct PlayerAvatar { LocalMapObject *mapObject; } PlayerAvatar;
typedef struct MapObjectMan { LocalMapObject *member; u16 objectId; } MapObjectMan;
typedef struct FieldSystem {
    MapObjectMan *mapObjectMan;
    PlayerAvatar *playerAvatar;
} FieldSystem;
typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u32 personality;
    u16 species;
    u16 encounterGeneration;
    u16 objectId;
    u8 form;
    u8 level;
    u8 active;
} OverworldWildSpawn;
typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    u16 mapGeneration;
    u8 movementSpotStates[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;

static BOOL mounted;
static BOOL IsMounted(void) { return mounted; }
static struct { BOOL (*isActive)(void); } mountEntry = { IsMounted };
#define OVERWORLD_MOUNT_OVERLAY_ENTRY (&mountEntry)
static LocalMapObject *GetMapObjectByID(MapObjectMan *manager, u16 objectId)
{
    return objectId == manager->objectId ? manager->member : NULL;
}

/* @FILL_ACTOR_VIEW@ */

static struct {
    struct {
        u32 policyGuard[8];
        OverworldActorStateSnapshot snapshot;
        u32 motionGuard[8];
    } slots[OW_WILD_MAX_SPAWNS];
} gOverworldActorSystemState;
static struct {
    void (*fillActorView)(FieldSystem *, OverworldWildSpawnState *, int, OverworldActorStateSnapshot *);
} runtimeEntry = { OverworldWildRuntime_FillActorView };
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)

static unsigned bindCalls, unbindCalls, traceCount;
static u16 unbindReason;
static OverworldActorStateSnapshot boundView;
static OverworldActorHandle unboundHandle;
static struct { OverworldActorHandle handle; u16 event; u32 a, b; } traces[16];
static OverworldActorResult OverworldActorSystem_CompatibilityBindImpl(
    const OverworldActorStateSnapshot *view, OverworldActorHandle *handle)
{
    bindCalls++;
    boundView = *view;
    *handle = view->handle;
    return OVERWORLD_ACTOR_RESULT_OK;
}
static OverworldActorResult OverworldActorSystem_CompatibilityUnbindImpl(
    const OverworldActorHandle *handle, u16 reason)
{
    unbindCalls++;
    unbindReason = reason;
    unboundHandle = *handle;
    return OVERWORLD_ACTOR_RESULT_OK;
}
static void ActorSystem_WriteTrace(const OverworldActorHandle *handle,
    u16 event, u16 reason, u32 a, u32 b)
{
    if (reason != OVERWORLD_ACTOR_REASON_OK || traceCount >= 16) abort();
    traces[traceCount].handle = *handle;
    traces[traceCount].event = event;
    traces[traceCount].a = a;
    traces[traceCount++].b = b;
}

/* @SYNC_ACTOR_VIEW@ */

static unsigned assertions, fillCases, syncCases;
#define CHECK(expression) do { assertions++; if (!(expression)) { \
    fprintf(stderr, "actor view invariant failed at line %d: %s\n", __LINE__, #expression); \
    exit(1); } } while (0)

static void CheckSnapshot(const OverworldActorStateSnapshot *actual,
    const OverworldActorStateSnapshot *expected)
{
    if (memcmp(actual, expected, sizeof(*actual))) {
        const u8 *a = (const u8 *)actual, *e = (const u8 *)expected;
        for (size_t index = 0; index < sizeof(*actual); index++) {
            if (a[index] != e[index]) {
                fprintf(stderr, "snapshot byte %zu: actual=%u expected=%u\n", index, a[index], e[index]);
            }
        }
    }
    CHECK(memcmp(actual, expected, sizeof(*actual)) == 0);
}

static OverworldActorStateSnapshot Seed(unsigned seed, unsigned phase)
{
    OverworldActorStateSnapshot value;
    u8 *bytes = (u8 *)&value;
    for (size_t index = 0; index < sizeof(value); index++) {
        bytes[index] = (u8)(17 + seed * 43 + index * 13);
    }
    value.motionPhase = (u8)phase;
    value.motionKind = OVERWORLD_MOTION_KIND_HOP;
    if (seed == 0) value.behaviorFingerprint = 0;
    value.active = TRUE;
    value.inputOwnership = TRUE; /* Demount must clear this, not retain it. */
    return value;
}

static void Arrange(OverworldWildSpawnState *state, FieldSystem *field,
    MapObjectMan *manager, PlayerAvatar *avatar, LocalMapObject *pokemon,
    LocalMapObject *player, unsigned slot, unsigned visibility, unsigned avatarMode)
{
    memset(state, 0, sizeof(*state));
    memset(pokemon, 0, sizeof(*pokemon));
    memset(player, 0, sizeof(*player));
    pokemon->xCurr = 41;
    pokemon->yCurr = -23;
    pokemon->posVec[0] = 117 * 65536;
    pokemon->posVec[2] = -92 * 65536;
    player->xCurr = -19;
    player->yCurr = 78;
    player->posVec[0] = -113 * 65536;
    player->posVec[2] = 95 * 65536;
    state->mapGeneration = 73;
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;
    OverworldWildSpawn *spawn = &state->spawns[slot];
    spawn->object = visibility == 3 ? NULL : pokemon;
    spawn->personality = 0x76543210;
    spawn->species = 165;
    spawn->form = 2;
    spawn->level = 19;
    spawn->encounterGeneration = 29;
    spawn->objectId = 0xE1;
    spawn->active = TRUE;
    pokemon->flags = visibility == 1 ? BIT_VANISH : 0;
    manager->member = visibility == 2 ? player : spawn->object;
    manager->objectId = spawn->objectId;
    avatar->mapObject = avatarMode == 2 ? NULL : player;
    field->mapObjectMan = manager;
    field->playerAvatar = avatarMode == 1 ? NULL : avatar;
}

static OverworldActorStateSnapshot ExpectedView(OverworldActorStateSnapshot before,
    unsigned slot, unsigned phase, unsigned visibility, unsigned avatarMode)
{
    const BOOL rider = mounted && slot == OW_WILD_FOLLOWER_SLOT;
    before.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    before.size = sizeof(before);
    before.handle.slot = (u16)slot;
    before.handle.mapGeneration = 73;
    before.handle.encounterGeneration = 29;
    before.subjectIdentity = 0x76543210;
    before.species = 165;
    before.form = 2;
    before.level = 19;
    before.role = rider ? OVERWORLD_ACTOR_ROLE_MOUNTED
        : slot == OW_WILD_FOLLOWER_SLOT ? OVERWORLD_ACTOR_ROLE_FOLLOWER : OVERWORLD_ACTOR_ROLE_WILD;
    before.lane = rider ? BEHAVIOR_RESOLUTION_LANE_OWNER : BEHAVIOR_RESOLUTION_LANE_ACTIVE;
    before.controllerState = rider ? OW_WILD_SPAWNER_SPOT_STATE_CHILL : OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;
    before.presentationState = visibility == 0 ? OVERWORLD_ACTOR_PRESENTATION_READY : 0;
    before.presentationAttached = visibility == 0;
    before.active = TRUE;
    before.inputOwnership = rider;
    const BOOL usePlayer = rider && avatarMode == 0;
    const BOOL hasObject = usePlayer || ((!(rider && avatarMode == 2)) && visibility != 3);
    if (hasObject) {
        if (phase == OVERWORLD_MOTION_PHASE_IDLE || phase == OVERWORLD_MOTION_PHASE_CANCELED) {
            before.logicalX = usePlayer ? -19 : 41;
            before.logicalY = usePlayer ? 78 : -23;
        }
        before.renderX = usePlayer ? -113 : 117;
        before.renderY = usePlayer ? 95 : -92;
    }
    return before;
}

static void CheckFillMatrix(void)
{
    const unsigned slots[] = {0, OW_WILD_FOLLOWER_SLOT};
    for (unsigned seed = 0; seed < 2; seed++)
    for (unsigned slotIndex = 0; slotIndex < 2; slotIndex++)
    for (unsigned mount = 0; mount < 2; mount++)
    for (unsigned phase = OVERWORLD_MOTION_PHASE_IDLE; phase <= OVERWORLD_MOTION_PHASE_CANCELED; phase++)
    for (unsigned visibility = 0; visibility < 4; visibility++)
    for (unsigned avatarMode = 0; avatarMode < 3; avatarMode++) {
        const unsigned slot = slots[slotIndex];
        OverworldWildSpawnState state;
        FieldSystem field;
        MapObjectMan manager;
        PlayerAvatar avatar;
        LocalMapObject pokemon, player;
        Arrange(&state, &field, &manager, &avatar, &pokemon, &player, slot, visibility, avatarMode);
        mounted = (BOOL)mount;
        struct { u64 prefix; OverworldActorStateSnapshot view; u64 suffix; } guarded;
        guarded.prefix = 0x123456789ABCDEFull;
        guarded.suffix = 0xFEDCBA9876543210ull;
        guarded.view = Seed(seed, phase);
        const OverworldActorStateSnapshot expected = ExpectedView(guarded.view, slot, phase, visibility, avatarMode);
        const OverworldWildSpawnState savedState = state;
        const LocalMapObject savedPokemon = pokemon, savedPlayer = player;
        OverworldWildRuntime_FillActorView(&field, &state, slot, &guarded.view);
        CheckSnapshot(&guarded.view, &expected);
        CHECK(guarded.prefix == 0x123456789ABCDEFull && guarded.suffix == 0xFEDCBA9876543210ull);
        CHECK(memcmp(&state, &savedState, sizeof(state)) == 0);
        CHECK(memcmp(&pokemon, &savedPokemon, sizeof(pokemon)) == 0);
        CHECK(memcmp(&player, &savedPlayer, sizeof(player)) == 0);
        fillCases++;
    }
}

static void CheckSync(void)
{
    const unsigned slot = OW_WILD_FOLLOWER_SLOT;
    for (unsigned seed = 0; seed < 2; seed++)
    for (unsigned mount = 0; mount < 2; mount++)
    for (unsigned priorMount = 0; priorMount < 2; priorMount++)
    for (unsigned visible = 0; visible < 2; visible++)
    for (unsigned priorVisible = 0; priorVisible < 2; priorVisible++)
    for (unsigned phase = OVERWORLD_MOTION_PHASE_IDLE; phase <= OVERWORLD_MOTION_PHASE_CANCELED; phase++) {
        OverworldWildSpawnState state;
        FieldSystem field;
        MapObjectMan manager;
        PlayerAvatar avatar;
        LocalMapObject pokemon, player;
        const unsigned visibility = visible ? 0 : 1;
        Arrange(&state, &field, &manager, &avatar, &pokemon, &player, slot, visibility, 0);
        memset(&gOverworldActorSystemState, 0x57, sizeof(gOverworldActorSystemState));
        OverworldActorStateSnapshot before = Seed(seed, phase);
        before.handle.slot = slot;
        before.handle.mapGeneration = 73;
        before.handle.encounterGeneration = 29;
        before.subjectIdentity = 0x76543210;
        before.role = priorMount ? OVERWORLD_ACTOR_ROLE_MOUNTED : OVERWORLD_ACTOR_ROLE_FOLLOWER;
        before.inputOwnership = (u8)priorMount;
        before.lane = priorMount ? BEHAVIOR_RESOLUTION_LANE_OWNER : BEHAVIOR_RESOLUTION_LANE_ACTIVE;
        before.presentationAttached = (u8)priorVisible;
        gOverworldActorSystemState.slots[slot].snapshot = before;
        mounted = (BOOL)mount;
        OverworldActorStateSnapshot expected = ExpectedView(before, slot, phase, visibility, 0);
        if (mount != priorMount) {
            expected.authorityGeneration++;
            expected.engineAnchorGeneration++;
        }
        if (visible != priorVisible) expected.presentationGeneration++;
        bindCalls = unbindCalls = traceCount = 0;
        ActorSystem_SyncLegacyActor(&field, &state, slot);
        CheckSnapshot(&gOverworldActorSystemState.slots[slot].snapshot, &expected);
        CHECK(bindCalls == 0 && unbindCalls == 0);
        CHECK(traceCount == 3 * (mount != priorMount) + (visible != priorVisible));
        unsigned counts[OVERWORLD_ACTOR_EVENT_ACTOR_REBOUND + 1] = {0};
        for (unsigned index = 0; index < traceCount; index++) {
            CHECK(memcmp(&traces[index].handle, &before.handle, sizeof(before.handle)) == 0);
            CHECK(traces[index].event <= OVERWORLD_ACTOR_EVENT_ACTOR_REBOUND);
            counts[traces[index].event]++;
        }
        CHECK(counts[OVERWORLD_ACTOR_EVENT_LANE_CHANGED] == (mount != priorMount));
        CHECK(counts[OVERWORLD_ACTOR_EVENT_ACTOR_REBOUND] == (mount != priorMount));
        CHECK(counts[OVERWORLD_ACTOR_EVENT_CONTROL_REBOUND] == (mount != priorMount));
        CHECK(counts[OVERWORLD_ACTOR_EVENT_PRESENTATION_SYNCED] == (visible != priorVisible));
        for (unsigned index = 0; index < 8; index++) {
            CHECK(gOverworldActorSystemState.slots[slot].policyGuard[index] == 0x57575757);
            CHECK(gOverworldActorSystemState.slots[slot].motionGuard[index] == 0x57575757);
        }
        syncCases++;
    }
}

int main(void)
{
    CheckFillMatrix();
    CheckSync();
    printf("PASS actual FillActorView: %u cases; actual SyncLegacyActor: %u cases; %u assertions\n",
        fillCases, syncCases, assertions);
    return 0;
}

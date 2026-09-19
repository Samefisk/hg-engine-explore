/* Actual service/header/wrapper code is injected by verify_overworld_field_stream.py.
 * Engine memory here is a host fixture. ARM pointer sizes/offsets remain S2 work.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_actor_system.h"
#include "overworld_motion_model.h"

typedef int BOOL;
typedef struct VecFx32 { s32 x, y, z; } VecFx32;
typedef struct LocalMapObject { s32 posVec[3]; } LocalMapObject;
typedef struct PlayerAvatar { LocalMapObject *mapObject; } PlayerAvatar;
/* A packed boundary object lets the unedited raw +0x2C lookup run on a host
 * with 64-bit pointers. It does not assert a native FieldSystem layout. */
typedef struct __attribute__((packed)) FieldSystem {
    u8 prefix[0x2C];
    void *manager;
    PlayerAvatar *playerAvatar;
} FieldSystem;

/* @CALL_TYPES@ */
/* @RUNTIME_TYPE@ */
/* @COMPATIBILITY_TYPES@ */

static u32 currentContext;
static u32 GetContext(void) { return currentContext; }
static OverworldActorCompatibilityEntry compatibility;
#undef OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compatibility)
#define LONG_CALL

static VecFx32 *watchedPosition;
static void *watchedManager;
static unsigned watcherChanges;
void ov01_021F62E8(VecFx32 *position, void *manager)
{
    /* Reference contract: native watcher stores the selected position and
     * initially copies its sample. Later sampling belongs to the engine. */
    watchedPosition = position;
    watchedManager = manager;
    memcpy((u8 *)manager + 0xD0, position, sizeof(*position));
    watcherChanges++;
}

/* @PRODUCT_SERVICE@ */

static OverworldFieldTerrainStreamRuntime sOverworldFieldTerrainStream;
/* @FIELD_WRAPPER@ */

typedef union Manager { u64 alignment; u8 bytes[0x100]; } Manager;
static Manager manager;
static FieldSystem field, otherField;
static PlayerAvatar avatar;
static LocalMapObject player;
static unsigned checks, pathCases, advances;
#define CHECK(expression) do { checks++; if (!(expression)) { \
    fprintf(stderr, "field stream invariant failed at line %d: %s\n", __LINE__, #expression); \
    exit(1); } } while (0)

static s32 Center(int tile) { return tile * 0x10000 + 0x8000; }
static void Reset(void)
{
    memset(&sOverworldFieldTerrainStream, 0, sizeof(sOverworldFieldTerrainStream));
    memset(&manager, 0, sizeof(manager));
    memset(&field, 0, sizeof(field));
    memset(&otherField, 0, sizeof(otherField));
    memset(&compatibility, 0, sizeof(compatibility));
    player.posVec[0] = Center(3);
    player.posVec[1] = 0x73456;
    player.posVec[2] = Center(-4);
    avatar.mapObject = &player;
    field.manager = &manager;
    field.playerAvatar = &avatar;
    otherField = field;
    currentContext = (7u << 16) | 11u;
    compatibility.magic = OVERWORLD_ACTOR_SYSTEM_COMPAT_MAGIC;
    compatibility.version = OVERWORLD_ACTOR_SYSTEM_COMPAT_VERSION;
    compatibility.size = sizeof(compatibility);
    compatibility.getContext = GetContext;
    watchedPosition = NULL;
    watchedManager = NULL;
    watcherChanges = 0;
}
static OverworldFieldTerrainStreamCall Call(unsigned operation, int dx, int dz)
{
    OverworldFieldTerrainStreamCall call;
    memset(&call, 0, sizeof(call));
    call.version = OVERWORLD_FIELD_TERRAIN_STREAM_CALL_VERSION;
    call.size = sizeof(call);
    call.fieldSystem = &field;
    call.fieldContext = currentContext;
    call.motionIdentity = 55;
    call.targetX = (s16)(3 + dx);
    call.targetY = (s16)(-4 + dz);
    call.operation = (u8)operation;
    return call;
}
static void Sample(void)
{
    CHECK(watchedPosition != NULL && watchedManager == &manager);
    memcpy(manager.bytes + 0xD0, watchedPosition, sizeof(*watchedPosition));
}
static void Unchanged(const OverworldFieldTerrainStreamCall *call,
    OverworldFieldTerrainStreamResult expected)
{
    const OverworldFieldTerrainStreamRuntime before = sOverworldFieldTerrainStream;
    const LocalMapObject oldPlayer = player;
    const unsigned oldWatchers = watcherChanges;
    CHECK(OverworldFieldService_TerrainStream(call) == expected);
    CHECK(memcmp(&before, &sOverworldFieldTerrainStream, sizeof(before)) == 0);
    CHECK(memcmp(&oldPlayer, &player, sizeof(player)) == 0);
    CHECK(watcherChanges == oldWatchers);
}
static void Clear(void)
{
    const OverworldFieldTerrainStreamRuntime zero = {0};
    CHECK(memcmp(&zero, &sOverworldFieldTerrainStream, sizeof(zero)) == 0);
}

static void ValidationCases(void)
{
    for (unsigned invalid = 0; invalid < 11; invalid++) {
        Reset();
        OverworldFieldTerrainStreamCall call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN, 8, 8);
        switch (invalid) {
        case 0: call.version++; break;
        case 1: call.size--; break;
        case 2: call.fieldSystem = NULL; break;
        case 3: call.operation = 99; break;
        case 4: call.fieldContext++; break;
        case 5: call.fieldContext += 1u << 16; break;
        case 6: compatibility.magic++; break;
        case 7: compatibility.version++; break;
        case 8: compatibility.size--; break;
        case 9: compatibility.getContext = NULL; break;
        case 10: call.motionIdentity = 0; break;
        }
        Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
        Clear();
    }
    Reset();
    Unchanged(NULL, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
    OverworldFieldTerrainStreamCall call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE, 0, 0);
    call.motionIdentity = 0;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    manager.bytes[0xA0] = 1;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY);
    manager.bytes[0xA0] = 0;
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN;
    call.motionIdentity = 55;
    field.playerAvatar = NULL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
    field.playerAvatar = &avatar;
    avatar.mapObject = NULL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
    avatar.mapObject = &player;
    field.manager = NULL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY);
    field.manager = &manager;
    manager.bytes[0xA0] = 1;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY);
}

static void ActiveIdentityCases(void)
{
    for (unsigned invalid = 0; invalid < 5; invalid++) {
        Reset();
        OverworldFieldTerrainStreamCall call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN, 8, 8);
        CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
        CHECK(watchedPosition == &sOverworldFieldTerrainStream.watchedAnchor);
        Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY);
        call.motionIdentity++;
        Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_RETRY_BUSY);
        call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_POLL, 8, 8);
        switch (invalid) {
        case 0: call.motionIdentity = 0; break;
        case 1: call.motionIdentity++; break;
        case 2: call.fieldSystem = &otherField; break;
        case 3: call.fieldContext++; currentContext++; break;
        case 4: call.fieldContext += 1u << 16; currentContext += 1u << 16; break;
        }
        Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
        call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL;
        if (invalid < 3) {
            Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
        } else {
            CHECK(OverworldFieldService_TerrainStream(&call)
                == OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
            Clear();
        }
    }
}

static void Travel(int dx, int dz)
{
    Reset();
    OverworldFieldTerrainStreamCall call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN, dx, dz);
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    CHECK(sOverworldFieldTerrainStream.active == TRUE);
    CHECK(sOverworldFieldTerrainStream.motionIdentity == 55);
    CHECK(sOverworldFieldTerrainStream.fieldSystem == &field);
    CHECK(watcherChanges == 1);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    const LocalMapObject oldPlayer = player;
    s32 expectedX = Center(3), expectedZ = Center(-4);
    for (int advance = 0; advance < abs(dx) + abs(dz); advance++) {
        manager.bytes[0xA0] = 1;
        Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
        manager.bytes[0xA0] = 0;
        CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
        if (advance < abs(dx)) expectedX += dx > 0 ? 0x10000 : -0x10000;
        else expectedZ += dz > 0 ? 0x10000 : -0x10000;
        CHECK(sOverworldFieldTerrainStream.watchedAnchor.x == expectedX);
        CHECK(sOverworldFieldTerrainStream.watchedAnchor.z == expectedZ);
        CHECK(sOverworldFieldTerrainStream.watchedAnchor.y == oldPlayer.posVec[1]);
        CHECK(memcmp(&oldPlayer, &player, sizeof(player)) == 0);
        /* Calling again is not a second engine sample or a second clock. */
        Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
        Sample();
        advances++;
    }
    /* Reattach to the engine's current player position, not a stale copy. */
    player.posVec[0] = Center(3 + dx);
    player.posVec[2] = Center(-4 + dz);
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_READY);
    CHECK(sOverworldFieldTerrainStream.active == TRUE);
    CHECK(watchedPosition == &sOverworldFieldTerrainStream.watchedAnchor);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL;
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    Clear();
    CHECK(watchedPosition == (VecFx32 *)player.posVec);
    CHECK(watcherChanges == 2);
    CHECK(memcmp(manager.bytes + 0xD0, player.posVec, sizeof(player.posVec)) == 0);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    pathCases++;
}

static void CancelAndRestoreCases(void)
{
    Reset();
    OverworldFieldTerrainStreamCall call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN, 8, 8);
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    field.manager = NULL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED);
    field.manager = &manager;
    player.posVec[0] = Center(5);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL;
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    Clear();
    CHECK(watchedPosition == (VecFx32 *)player.posVec && watcherChanges == 2);
    CHECK(memcmp(manager.bytes + 0xD0, player.posVec, sizeof(player.posVec)) == 0);
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);

    Reset();
    call = Call(OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN, 0, 0);
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    avatar.mapObject = NULL;
    Unchanged(&call, OVERWORLD_FIELD_TERRAIN_STREAM_READY);
    avatar.mapObject = &player;
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_READY);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL;
    CHECK(OverworldFieldService_TerrainStream(&call) == OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    Clear();
}

static void RetargetAndRebindCases(void)
{
    Reset();
    OverworldFieldTerrainStreamCall call = Call(
        OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN, 8, 8);
    CHECK(OverworldFieldService_TerrainStream(&call)
        == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    call.targetX = 4;
    call.targetY = -4;
    CHECK(OverworldFieldService_TerrainStream(&call)
        == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    CHECK(sOverworldFieldTerrainStream.watchedAnchor.x == Center(4));
    Sample();

    currentContext = (8u << 16) | 12u;
    call.fieldContext = currentContext;
    call.motionIdentity = 0;
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_REBIND;
    CHECK(OverworldFieldService_TerrainStream(&call)
        == OVERWORLD_FIELD_TERRAIN_STREAM_WAITING);
    CHECK(sOverworldFieldTerrainStream.fieldSystem == &field);
    call.motionIdentity = 55;
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_POLL;
    CHECK(OverworldFieldService_TerrainStream(&call)
        == OVERWORLD_FIELD_TERRAIN_STREAM_READY);
    call.operation = OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL;
    CHECK(OverworldFieldService_TerrainStream(&call)
        == OVERWORLD_FIELD_TERRAIN_STREAM_IDLE);
    Clear();
}

int main(void)
{
    ValidationCases();
    ActiveIdentityCases();
    const int paths[][2] = {{8, 0}, {-8, 0}, {0, 8}, {0, -8},
        {8, 8}, {8, -8}, {-8, 8}, {-8, -8}, {0, 0}};
    for (unsigned index = 0; index < sizeof(paths) / sizeof(paths[0]); index++) {
        Travel(paths[index][0], paths[index][1]);
    }
    CancelAndRestoreCases();
    RetargetAndRebindCases();
    printf("PASS actual Field stream service/wrapper: %u paths, %u sampled tile advances, %u assertions\n",
        pathCases, advances, checks);
    return 0;
}

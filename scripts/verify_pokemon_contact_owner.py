#!/usr/bin/env python3
"""Check production contact ownership against the boot-resident Actor facade.

This runs the real readiness and contact-owner functions with host engine stubs.
It does not prove collision geometry or game rendering.
"""

from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]

STUBS = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define COMBAT_CODE
#define MAPOBJECTFLAG_ACTIVE (1u << 0)
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(value) ((u16)((value) >> 16))
#define OVERLAY_OVERWORLD_ACTOR_SYSTEM 158

/* Keep the production facade's ARM9 ABI: four 32-bit function addresses. */
typedef u32 OverworldActorSystemValidateFunc;
typedef u32 OverworldActorSystemApplyFunc;
typedef u32 OverworldActorSystemTickFunc;
typedef u32 OverworldActorSystemInspectFunc;
typedef struct LocalMapObject { u32 flags; int id; } LocalMapObject;
typedef struct MapObjectMan { LocalMapObject *objects; u32 object_count; } MapObjectMan;
typedef struct TestLocation { u16 mapId; } TestLocation;
typedef struct FieldSystem {
    TestLocation *location;
    void *mapObjectMan;
} FieldSystem;
typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u16 mapId;
    u8 active, objectId;
} OverworldWildSpawn;
typedef struct OverworldWildSpawnState {
    FieldSystem *movementFieldSystem;
    u16 mapGeneration;
    OverworldWildSpawn spawns[10];
} OverworldWildSpawnState;
typedef struct TestCompatibilityEntry { u32 (*getContext)(void); }
    TestCompatibilityEntry;
static FieldSystem *gFieldSysPtr;
static u32 testContext;
static u32 contextCalls, managerCalls, sdkQueries;
static u32 TestGetContext(void) { ++contextCalls; return testContext; }
static TestCompatibilityEntry testCompatibility = { TestGetContext };
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&testCompatibility)
/* The stock ID lookup scans the whole object array. Contact validity must
 * never call it; any call is counted and fails the managerCalls == 0 gates. */
static __attribute__((unused)) LocalMapObject *GetMapObjectByID(void *manager, u32 objectId) {
    (void)manager; (void)objectId;
    ++managerCalls;
    return NULL;
}
static BOOL IsOverlayLoaded(u32 overlay) {
    assert(overlay == OVERLAY_OVERWORLD_ACTOR_SYSTEM);
    ++sdkQueries;
    return 0; /* The resident Actor image is absent from the SDK load table. */
}
"""

CASES = r"""
static LocalMapObject objects[4], otherObjects[2];
#define liveObject (objects[2])
#define foreignObject (otherObjects[0])
static TestLocation location;
static MapObjectMan manager;
static FieldSystem field, otherField;
static OverworldWildSpawnState wild;

static void reset_fixture(void) {
    memset(&testFacade, 0, sizeof(testFacade));
    testFacade.magic = OVERWORLD_ACTOR_SYSTEM_MAGIC;
    testFacade.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    testFacade.size = sizeof(testFacade);
    memset(objects, 0, sizeof(objects));
    memset(otherObjects, 0, sizeof(otherObjects));
    liveObject.flags = MAPOBJECTFLAG_ACTIVE;
    liveObject.id = 231;
    foreignObject.flags = MAPOBJECTFLAG_ACTIVE;
    foreignObject.id = 231;
    location.mapId = 33;
    manager = (MapObjectMan){.objects = objects, .object_count = 4};
    field = (FieldSystem){.location = &location, .mapObjectMan = &manager};
    otherField = field;
    gFieldSysPtr = &field;
    memset(&wild, 0, sizeof(wild));
    wild.movementFieldSystem = &field;
    wild.mapGeneration = 3;
    wild.spawns[2] = (OverworldWildSpawn){
        .object = &liveObject, .mapId = 33, .active = 1, .objectId = 231,
    };
    testContext = (3u << 16) | 7;
    contextCalls = managerCalls = sdkQueries = 0;
}

#define REJECT(change) do { \
    reset_fixture(); \
    change; \
    assert(!CombatContact_Current(&wild, 2)); \
} while (0)

int main(void) {
    _Static_assert(sizeof(OverworldActorSystemEntry) == 24, "ARM9 facade ABI");
    reset_fixture();
    assert(!IsOverlayLoaded(OVERLAY_OVERWORLD_ACTOR_SYSTEM));
    sdkQueries = 0;
    assert(CombatContact_Current(&wild, 2));
    assert(contextCalls == 1 && managerCalls == 0 && sdkQueries == 0);

    /* Missing or incompatible resident images stop before native queries. */
    REJECT(testFacade.magic = 0);
    assert(managerCalls == 0 && contextCalls == 0);
    REJECT(testFacade.magic ^= 1);
    REJECT(testFacade.version += 1);
    REJECT(testFacade.size -= 4);

    /* Preserve the existing field, map, manager, and object ownership gates. */
    REJECT(wild.movementFieldSystem = NULL);
    REJECT(wild.movementFieldSystem = &otherField);
    REJECT(gFieldSysPtr = &otherField);
    REJECT(field.location = NULL);
    REJECT(field.mapObjectMan = NULL);
    REJECT(wild.spawns[2].active = 0);
    REJECT(wild.spawns[2].object = NULL);
    REJECT(wild.spawns[2].mapId += 1);
    REJECT(wild.spawns[2].objectId += 1);
    /* O(1) ownership: a changed engine ID, an object that carries another ID
     * and an inactive object are rejected without any lookup. */
    REJECT(wild.spawns[2].object = &foreignObject; foreignObject.id = 232);
    REJECT(liveObject.id += 1);
    REJECT(liveObject.flags = 0);
    REJECT(wild.mapGeneration += 1);
    REJECT(testContext = (4u << 16) | 7);

    reset_fixture();
    testContext = (3u << 16) | 8; /* Same map generation, new frame context. */
    assert(CombatContact_Current(&wild, 2));
    assert(managerCalls == 0);
    reset_fixture();
    wild.spawns[2].object = &objects[3];
    wild.spawns[2].objectId = 7;
    objects[3] = (LocalMapObject){.flags = MAPOBJECTFLAG_ACTIVE, .id = 7};
    assert(CombatContact_Current(&wild, 2) && managerCalls == 0);
    /* A stale generation must stop before the stored pointer is read. */
    reset_fixture();
    testContext = (4u << 16) | 7;
    wild.spawns[2].object = (LocalMapObject *)(uintptr_t)0x10;
    assert(!CombatContact_Current(&wild, 2) && managerCalls == 0);
    puts("Production contact accepts the resident Actor and rejects stale owners.");
    return 0;
}
"""


def extracted_source() -> str:
    header = (ROOT / "include/overworld_actor_system.h").read_text()
    constants = "".join(re.findall(
        r"^#define OVERWORLD_ACTOR_SYSTEM_(?:MAGIC|ABI_VERSION)[^\n]*\n",
        header, re.MULTILINE,
    ))
    entry_start = header.index("typedef struct OverworldActorSystemEntry {")
    entry_end = header.index("} OverworldActorSystemEntry;", entry_start)
    entry_end += len("} OverworldActorSystemEntry;")
    helper_start = header.index("static inline u8 OverworldActorSystem_IsReady(void)")
    helper_end = header.index("\ntypedef char ", helper_start)
    contact = (ROOT / "src/player_health_contact.c").read_text()
    contact_start = contact.index("static BOOL COMBAT_CODE CombatContact_Current(")
    contact_end = contact.index("\nvoid COMBAT_CODE PlayerHealthContact_BeginFrame(",
                                contact_start)
    return (constants + header[entry_start:entry_end] + "\n"
            "static OverworldActorSystemEntry testFacade;\n"
            "#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&testFacade)\n"
            + header[helper_start:helper_end] + "\n"
            + contact[contact_start:contact_end])


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pokemon-contact-owner-") as temporary:
        source = Path(temporary) / "contact_owner.c"
        executable = Path(temporary) / "contact_owner"
        source.write_text(STUBS + extracted_source() + CASES)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()

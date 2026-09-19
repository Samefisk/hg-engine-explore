"""Host checks for the five compact spawn spatial queries and two guards.

The C under test is extracted from the shipped translation units.  The test
keeps the native field/object shape needed by the queries, but supplies the
fixed resident calls (player coordinates and facing deltas) as host stubs.
Expected values come from small Python rules below, not from the C result.

Run with::

    python3 -m unittest tools.overworld.test_spawn_spatial -v
"""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_spawn_spatial.c"
SELECTOR_SOURCE = ROOT / "src/overworld_follower_selector_overlay/overworld_spawn_spatial.c"
GUARD_SOURCE = ROOT / "src/pokemon_move_history_overlay/overworld_spawn_guard.c"


def extract_function(source, name, returns):
    """Extract one static or non-static C definition for host compilation."""

    pattern = re.compile(
        r"\b(?:static\s+)?"
        + re.escape(returns)
        + r"\b[^;{}]*?\b"
        + re.escape(name)
        + r"\s*\([^;{}]*\)\s*\{"
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError("expected one definition of " + name)
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            # Start at the function name.  This drops ROM-only attributes and
            # keeps the complete argument list and body.  Static linkage also
            # avoids collisions if a future source file adds another export.
            start = source.index(name, match.start(), match.end())
            return "static " + returns + " " + source[start : end + 1]
    raise ValueError("unterminated " + name)


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int BOOL;
typedef uint8_t u8;
typedef uint32_t u32;

#define TRUE 1
#define FALSE 0
#define MAPOBJECTFLAG_ACTIVE (1u << 0)
#define OW_WILD_MAX_SPAWNS 10

/* Keep the fields at their native LocalMapObject offsets.  The range query
 * uses sizeof(LocalMapObject), so a compact test-only struct would test a
 * different boundary. */
typedef struct LocalMapObject {
    u32 flags;
    u8 pad_to_facing[0x24];
    int curFacing;
    u8 pad_to_x[0x38];
    int xCurr;
    u8 pad_to_y[0x04];
    int yCurr;
    u8 tail[0xBC];
} LocalMapObject;

_Static_assert(sizeof(LocalMapObject) == 0x12C, "native object size");

typedef struct MapObjectMan {
    u32 object_count;
    u8 pad_to_objects[0x120];
    LocalMapObject *objects;
} MapObjectMan;

typedef struct Avatar {
    LocalMapObject *mapObject;
} Avatar;

typedef Avatar FIELD_PLAYER_AVATAR;

typedef struct FieldSystem {
    u8 pad_to_manager[0x3C];
    MapObjectMan *mapObjectMan;
    Avatar *playerAvatar;
} FieldSystem;

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u8 active;
} OverworldWildSpawn;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    u8 movementSpawnRunActive[OW_WILD_MAX_SPAWNS];
    int movementSpawnRunTargetX[OW_WILD_MAX_SPAWNS];
    int movementSpawnRunTargetY[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;

static int host_player_x;
static int host_player_y;

int OverworldSpawnSpatial_GetPlayerXCoord(FIELD_PLAYER_AVATAR *avatar)
{
    (void)avatar;
    return host_player_x;
}

int OverworldSpawnSpatial_GetPlayerYCoord(FIELD_PLAYER_AVATAR *avatar)
{
    (void)avatar;
    return host_player_y;
}

int OverworldWalk_DeltaX(u8 direction)
{
    if (direction == 2) return -1;
    return direction == 3 ? 1 : 0;
}

int OverworldWalk_DeltaY(u8 direction)
{
    if (direction == 0) return -1;
    return direction == 1 ? 1 : 0;
}

static inline u32 OverworldSpawnSpatial_ObjectCurrentX(LocalMapObject *object)
{
    return *(volatile u32 *)&object->xCurr;
}

static inline u32 OverworldSpawnSpatial_ObjectCurrentY(LocalMapObject *object)
{
    return *(volatile u32 *)&object->yCurr;
}

static int OverworldWildSpawnGuard_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildSpawnGuard_Max(int a, int b)
{
    return a > b ? a : b;
}

static int OverworldSpawnSpatial_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldSpawnSpatial_Max(int a, int b)
{
    return a > b ? a : b;
}
'''


DRIVER = r'''
typedef struct SpatialFixture {
    FieldSystem field;
    Avatar avatar;
    MapObjectMan manager;
    LocalMapObject objects[4];
    LocalMapObject stale;
    OverworldWildSpawnState state;
} SpatialFixture;

static SpatialFixture fixture;

static void reset_spatial(void)
{
    memset(&fixture, 0, sizeof(fixture));
    host_player_x = 10;
    host_player_y = -3;
    fixture.manager.object_count = 4;
    fixture.manager.objects = fixture.objects;
    fixture.field.mapObjectMan = &fixture.manager;
    fixture.field.playerAvatar = &fixture.avatar;
    fixture.avatar.mapObject = &fixture.objects[0];
}

static LocalMapObject *object_for_case(int object_case)
{
    switch (object_case) {
    case 0:
        return &fixture.objects[0];
    case 1:
        return &fixture.objects[3];
    case 2:
        return &fixture.stale;
    case 3:
        return NULL;
    case 4:
        fixture.field.mapObjectMan = NULL;
        return &fixture.objects[0];
    case 5:
        fixture.manager.objects = NULL;
        return &fixture.objects[0];
    case 6:
        fixture.manager.object_count = 0;
        return &fixture.objects[0];
    case 7:
        return &fixture.objects[4];
    default:
        abort();
    }
}

static void emit_value(int value)
{
    unsigned char before[sizeof(fixture)];
    memcpy(before, &fixture, sizeof(fixture));
    printf("%d %d\n", value,
        memcmp(before, &fixture, sizeof(fixture)) != 0);
}

static int arg(const char *value)
{
    return (int)strtol(value, NULL, 10);
}

static void run_player(int x, int y, int avatar_present)
{
    reset_spatial();
    host_player_x = 10;
    host_player_y = -3;
    fixture.field.playerAvatar = avatar_present ? &fixture.avatar : NULL;
    emit_value(OverworldSpawnSpatial_IsPlayerTile(&fixture.field, x, y));
}

static void run_current(int object_case)
{
    LocalMapObject *object;

    reset_spatial();
    object = object_for_case(object_case);
    emit_value(OverworldSpawnSpatial_IsCurrentMapObject(&fixture.field, object));
}

static void run_front(
    int x, int y, int avatar_present, int object_case, int active, int facing)
{
    LocalMapObject *object;

    reset_spatial();
    fixture.field.playerAvatar = avatar_present ? &fixture.avatar : NULL;
    object = object_for_case(object_case);
    if (fixture.field.playerAvatar != NULL) {
        fixture.avatar.mapObject = object;
    }
    if (object != NULL) {
        object->flags = active ? MAPOBJECTFLAG_ACTIVE : 0;
        object->curFacing = facing;
        object->xCurr = host_player_x;
        object->yCurr = host_player_y;
    }
    emit_value(OverworldSpawnSpatial_IsPlayerFrontTile(&fixture.field, x, y));
}

static void run_distance(int x, int y, int player_x, int player_y)
{
    reset_spatial();
    host_player_x = player_x;
    host_player_y = player_y;
    emit_value(OverworldSpawnSpatial_DistanceFromPlayer(
        &fixture.field, x, y));
}

static void run_object_tile(
    int x, int y, int avatar_present, int object_case)
{
    LocalMapObject *object;

    reset_spatial();
    fixture.field.playerAvatar = avatar_present ? &fixture.avatar : NULL;
    object = object_for_case(object_case);
    if (object != NULL) {
        object->xCurr = x;
        object->yCurr = y;
    }
    emit_value(OverworldSpawnSpatial_IsObjectOnPlayerTile(
        &fixture.field, object));
}

static void run_near(int scenario)
{
    LocalMapObject *object = &fixture.objects[0];
    int x = 0;
    int y = 0;
    int radius = 0;

    reset_spatial();
    object->xCurr = 10;
    object->yCurr = 10;
    switch (scenario) {
    case 0: /* empty state */
        break;
    case 1: /* current position at the edge */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        x = 10; y = 12; radius = 2;
        break;
    case 2: /* current position just outside */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        x = 10; y = 13; radius = 2;
        break;
    case 3: /* inactive object is ignored */
        fixture.state.spawns[0].object = object;
        x = 10; y = 10; radius = 0;
        break;
    case 4: /* active slot without an object is ignored */
        fixture.state.spawns[0].active = TRUE;
        x = 10; y = 10; radius = 0;
        break;
    case 5: /* reserved target can be near while current is far */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        object->xCurr = 0; object->yCurr = 0;
        fixture.state.movementSpawnRunActive[0] = TRUE;
        fixture.state.movementSpawnRunTargetX[0] = 10;
        fixture.state.movementSpawnRunTargetY[0] = 12;
        x = 10; y = 10; radius = 2;
        break;
    case 6: /* reserved target exactly at radius zero */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        object->xCurr = 20; object->yCurr = 20;
        fixture.state.movementSpawnRunActive[0] = TRUE;
        fixture.state.movementSpawnRunTargetX[0] = 4;
        fixture.state.movementSpawnRunTargetY[0] = 4;
        x = 4; y = 4; radius = 0;
        break;
    case 7: /* reserved target outside */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        object->xCurr = 20; object->yCurr = 20;
        fixture.state.movementSpawnRunActive[0] = TRUE;
        fixture.state.movementSpawnRunTargetX[0] = 4;
        fixture.state.movementSpawnRunTargetY[0] = 7;
        x = 4; y = 4; radius = 2;
        break;
    case 8: /* second active slot is still scanned */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        object->xCurr = 20; object->yCurr = 20;
        fixture.state.spawns[1].active = TRUE;
        fixture.state.spawns[1].object = &fixture.objects[1];
        fixture.objects[1].xCurr = 4; fixture.objects[1].yCurr = 5;
        x = 4; y = 4; radius = 1;
        break;
    case 9: /* negative radius cannot match, even at the same tile */
        fixture.state.spawns[0].active = TRUE;
        fixture.state.spawns[0].object = object;
        x = 10; y = 10; radius = -1;
        break;
    default:
        abort();
    }
    {
        unsigned char before[sizeof(fixture)];
        memcpy(before, &fixture, sizeof(fixture));
        printf("%d %d\n", OverworldWildSpawnGuard_IsNearActiveSpawn(
            &fixture.state, x, y, radius),
            memcmp(before, &fixture, sizeof(fixture)) != 0);
    }
}

static void run_surf(void)
{
    int behavior;

    for (behavior = 0; behavior < 256; behavior++) {
        if (behavior != 0) putchar(' ');
        printf("%d", OverworldWildSpawnGuard_IsSurfBehavior((u8)behavior));
    }
    putchar('\n');
}

int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    if (strcmp(argv[1], "player") == 0 && argc == 5) {
        run_player(arg(argv[2]), arg(argv[3]), arg(argv[4]));
    } else if (strcmp(argv[1], "current") == 0 && argc == 3) {
        run_current(arg(argv[2]));
    } else if (strcmp(argv[1], "front") == 0 && argc == 8) {
        run_front(arg(argv[2]), arg(argv[3]), arg(argv[4]), arg(argv[5]),
            arg(argv[6]), arg(argv[7]));
    } else if (strcmp(argv[1], "distance") == 0 && argc == 6) {
        run_distance(arg(argv[2]), arg(argv[3]), arg(argv[4]), arg(argv[5]));
    } else if (strcmp(argv[1], "object") == 0 && argc == 6) {
        run_object_tile(arg(argv[2]), arg(argv[3]), arg(argv[4]), arg(argv[5]));
    } else if (strcmp(argv[1], "near") == 0 && argc == 3) {
        run_near(arg(argv[2]));
    } else if (strcmp(argv[1], "surf") == 0 && argc == 2) {
        run_surf();
    } else {
        return 2;
    }
    return 0;
}
'''


def build_host_binary():
    helper = HELPER_SOURCE.read_text()
    selector = SELECTOR_SOURCE.read_text()
    guard = GUARD_SOURCE.read_text()
    actual = "\n".join(
        [
            extract_function(selector, "OverworldSpawnSpatial_IsCurrentMapObject", "BOOL"),
            extract_function(helper, "OverworldSpawnSpatial_IsPlayerTile", "BOOL"),
            extract_function(helper, "OverworldSpawnSpatial_IsPlayerFrontTile", "BOOL"),
            extract_function(selector, "OverworldSpawnSpatial_DistanceFromPlayer", "int"),
            extract_function(selector, "OverworldSpawnSpatial_IsObjectOnPlayerTile", "BOOL"),
            extract_function(guard, "OverworldWildSpawnGuard_IsSurfBehavior", "BOOL"),
            extract_function(guard, "OverworldWildSpawnGuard_IsNearActiveSpawn", "BOOL"),
        ]
    )
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-spatial-")
    source_path = Path(temp_dir.name) / "spawn_spatial_host.c"
    binary_path = Path(temp_dir.name) / "spawn_spatial_host"
    source_path.write_text(PRELUDE + actual + DRIVER)
    command = [
        "cc",
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wno-pointer-to-int-cast",
        "-Wno-int-to-pointer-cast",
        "-Wno-strict-aliasing",
        str(source_path),
        "-o",
        str(binary_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except Exception:
        temp_dir.cleanup()
        raise
    return temp_dir, binary_path


class SpawnSpatialParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir, cls.binary = build_host_binary()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def call(self, *args):
        output = subprocess.check_output(
            [str(self.binary), *map(str, args)], text=True
        ).strip()
        value, mutated = map(int, output.split())
        self.assertEqual(mutated, 0, f"{args} mutated its input fixture")
        return value

    def test_player_tile_matches_independent_rule(self):
        cases = [(10, -3, 1), (10, -2, 1), (9, -3, 1), (10, -3, 0)]
        for x, y, avatar_present in cases:
            expected = int(avatar_present and x == 10 and y == -3)
            self.assertEqual(self.call("player", x, y, avatar_present), expected)

    def test_current_map_object_checks_null_stale_and_range(self):
        # 0 and 1 are the first and last objects in [base, base + count*size).
        expected = {0: 1, 1: 1, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0}
        for object_case, value in expected.items():
            self.assertEqual(self.call("current", object_case), value)

    def test_front_tile_checks_active_facing_and_cardinal_deltas(self):
        deltas = {0: (0, -1), 1: (0, 1), 2: (-1, 0), 3: (1, 0)}
        for facing, (dx, dy) in deltas.items():
            self.assertEqual(
                self.call("front", 10 + dx, -3 + dy, 1, 0, 1, facing), 1
            )
            self.assertEqual(
                self.call("front", 10 + dx, -3 + dy + 1, 1, 0, 1, facing), 0
            )
        for facing in (4, 255):
            self.assertEqual(self.call("front", 10, -4, 1, 0, 1, facing), 0)
        self.assertEqual(self.call("front", 10, -4, 1, 0, 0, 0), 0)
        self.assertEqual(self.call("front", 10, -4, 1, 2, 1, 0), 0)
        self.assertEqual(self.call("front", 10, -4, 0, 0, 1, 0), 0)
        self.assertEqual(self.call("front", 10, -4, 1, 3, 1, 0), 0)

    def test_distance_matches_chebyshev_rule(self):
        cases = [
            (10, -3, 10, -3),
            (14, -8, 10, -3),
            (2, 4, 10, -3),
            (-20, 30, -4, -7),
        ]
        for x, y, player_x, player_y in cases:
            expected = max(abs(x - player_x), abs(y - player_y))
            self.assertEqual(
                self.call("distance", x, y, player_x, player_y), expected
            )

    def test_object_on_player_tile_reads_object_coordinates_only(self):
        cases = [
            (10, -3, 1, 0, 1),
            (9, -3, 1, 0, 0),
            (10, -3, 1, 2, 1),  # stale objects still use their coordinates here
            (10, -3, 1, 7, 1),  # one-past object is not dereferenced by current check
            (10, -3, 1, 3, 0),
            (10, -3, 0, 0, 0),
        ]
        for x, y, avatar_present, object_case, expected in cases:
            self.assertEqual(
                self.call("object", x, y, avatar_present, object_case), expected
            )

    def test_near_active_spawn_checks_current_and_reserved_targets(self):
        expected = {
            0: 0,
            1: 1,
            2: 0,
            3: 0,
            4: 0,
            5: 1,
            6: 1,
            7: 0,
            8: 1,
            9: 0,
        }
        for scenario, value in expected.items():
            self.assertEqual(self.call("near", scenario), value)

    def test_surf_behavior_matches_all_byte_values(self):
        output = subprocess.check_output([str(self.binary), "surf"], text=True)
        actual = [int(value) for value in output.split()]
        self.assertEqual(len(actual), 256)
        expected = [int(value in {16, 18, 21, 42}) for value in range(256)]
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()

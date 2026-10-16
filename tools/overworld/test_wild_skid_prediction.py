"""Actual-C checks for Wild/Follower skid prediction (planTurnSkidPath).

Compiles the shipped OverworldWildSpawns_IsPredictedRunwayBlocked body
against a small tile grid. Walk timing and direction deltas come from the
real policy headers; the landing check, ledges and the player are stubs.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
NAME = "OverworldWildSpawns_IsPredictedRunwayBlocked"


def function_body(source, name):
    match = re.search(r"\b" + name + r"\s*\([^;{}]*\)\s*\{", source)
    if match is None:
        raise ValueError("missing " + name)
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            return "static BOOL " + source[match.start():end + 1]
    raise ValueError("unterminated " + name)


PRELUDE = r'''
#include "overworld_walk_direction_policy.h"
#include "overworld_walk_timing_policy.h"
#include <stdlib.h>

#define OW_WILD_WALK_DIRECTION_NONE 0xFF
#define OW_WILD_TILE_LEDGE_EAST 56
#define OVERWORLD_ACTOR_WALK_STEP_SKID 0x02
#define OVERWORLD_ACTOR_WALK_STEP_STOP_SKID 0x04
#define OW_WILD_BEHAVIOR_PLANS_TURN_SKID_PATH(options) (((options) & 0x40) != 0)

typedef struct { int xCurr, yCurr; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; } PlayerAvatar;
typedef struct { PlayerAvatar *playerAvatar; } FieldSystem;
typedef struct { u8 tilesBeforeTurnSkid; } OverworldWildBehaviorProfileData;
typedef struct { int unused; } OverworldWildSpawnState;
typedef struct {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    u8 slot;
    u16 allowedTile;
} OverworldWildDirectionStepContext;
typedef struct {
    const OverworldWildBehaviorProfileData *lane;
    u8 distance, stepDirection, facingDirection, stepFlags;
    u8 reserved[4];
} OverworldActorWalkPolicyCall;

static char sGrid[16][16];
static u8 OverworldWalk_SkidTiles(u8 time) { return OverworldWalkTimingPolicy_SkidTiles(time); }
static int OverworldWildSpawns_MovementDirectionDeltaX(u8 d) { return OverworldWalkDirectionPolicy_DeltaX(d); }
static int OverworldWildSpawns_MovementDirectionDeltaY(u8 d) { return OverworldWalkDirectionPolicy_DeltaY(d); }
static int Cell(int x, int y) { return x < 0 || y < 0 || x > 15 || y > 15 ? '#' : sGrid[y][x]; }
/* '#' wall, 'E','W','N','S' ledges facing east/west/north/south. */
static u32 GetMetatileBehaviorAt(FieldSystem *f, int x, int y)
{
    (void)f;
    switch (Cell(x, y)) {
    case 'E': return OW_WILD_TILE_LEDGE_EAST;
    case 'W': return OW_WILD_TILE_LEDGE_EAST + 1;
    case 'N': return OW_WILD_TILE_LEDGE_EAST + 2;
    case 'S': return OW_WILD_TILE_LEDGE_EAST + 3;
    }
    return 0;
}
static BOOL OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
    OverworldWildSpawnState *s, int slot, FieldSystem *f, u16 allowed,
    int x, int y, int fx, int fy)
{
    (void)s; (void)slot; (void)f; (void)allowed; (void)fx; (void)fy;
    return Cell(x, y) == '.';
}
'''

MAIN = r'''
int main(int argc, char **argv)
{
    /* argv: rows... -- ax ay px py plans flags distance step facing time */
    int i = 1, row = 0;
    for (; i < argc && argv[i][0] != '-'; i++, row++) {
        for (int x = 0; x < 16; x++) sGrid[row][x] = argv[i][x] ? argv[i][x] : '.';
    }
    for (; row < 16; row++) for (int x = 0; x < 16; x++) sGrid[row][x] = '.';
    i++;
    LocalMapObject actor = { atoi(argv[i]), atoi(argv[i + 1]) };
    LocalMapObject playerObject = { atoi(argv[i + 2]), atoi(argv[i + 3]) };
    PlayerAvatar avatar = { &playerObject };
    FieldSystem field = { &avatar };
    OverworldWildBehaviorProfileData lane = { (u8)(atoi(argv[i + 4]) ? 0x40 : 0) };
    OverworldWildSpawnState state = { 0 };
    OverworldWildDirectionStepContext ctx = { &state, &field, &actor, 7, 1 };
    OverworldActorWalkPolicyCall call = { &lane, (u8)atoi(argv[i + 6]),
        (u8)atoi(argv[i + 7]), (u8)atoi(argv[i + 8]), (u8)atoi(argv[i + 5]),
        { (u8)atoi(argv[i + 9]) } };
    u8 distance = call.distance;
    printf("%d\n", NAME(&ctx, &call) ? 1 : 0);
    return call.distance == distance ? 0 : 3;
}
'''

N, S, W, E = 0, 1, 2, 3
SKID, STOP = 0x02, 0x06


class SkidPredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        body = function_body(SOURCE.read_text(), NAME)
        cls.tmp = tempfile.TemporaryDirectory()
        c = Path(cls.tmp.name) / "predict.c"
        c.write_text(PRELUDE + body + MAIN.replace("NAME", NAME))
        cls.binary = Path(cls.tmp.name) / "predict"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Werror", "-Wno-unused-function",
                        "-Wno-unknown-attributes", "-Wno-macro-redefined",
                        "-DOVERWORLD_BEHAVIOR_HOST", "-I", str(ROOT / "include"),
                        str(c), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def blocked(self, rows, actor, player, step, time, flags=0, distance=0,
                facing=None, plans=1):
        facing = step if facing is None else facing
        out = subprocess.run([str(self.binary), *rows, "--", *map(str, (
            actor[0], actor[1], player[0], player[1], plans, flags, distance,
            step, facing, time))], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, "the preview call was modified")
        return out.stdout.strip() == "1"

    def test_straight_runway_needs_stopping_room_at_speed(self):
        # Time 4 stops in two tiles: the step plus two more must be open.
        row = ["........#"]
        self.assertFalse(self.blocked(row, (4, 0), (15, 15), E, 4))
        self.assertTrue(self.blocked(row, (5, 0), (15, 15), E, 4))
        # Slow Walk (time 8) has no stop skid: only the next tile matters.
        self.assertFalse(self.blocked(row, (6, 0), (15, 15), E, 8))
        self.assertTrue(self.blocked(row, (7, 0), (15, 15), E, 8))

    def test_turn_into_a_dead_end_is_unsafe(self):
        # Route 29 case: heading east, a turn south one tile before a wall.
        rows = ["..........", "..........", "..........", "..#......."]
        self.assertTrue(self.blocked(rows, (1, 0), (9, 9), E, 4, SKID, 1, S))
        self.assertFalse(self.blocked(rows, (2, 0), (9, 9), E, 4, SKID, 1, S))

    def test_blocked_skid_slide_is_unsafe(self):
        rows = ["..#"]
        self.assertTrue(self.blocked(rows, (1, 0), (9, 9), E, 4, SKID, 1, S))

    def test_player_ends_a_runway_but_blocks_a_stop_slide(self):
        rows = ["....#"]
        self.assertFalse(self.blocked(rows, (0, 0), (2, 0), E, 4))
        self.assertTrue(self.blocked(rows, (0, 0), (1, 0), E, 4, STOP, 2))
        self.assertFalse(self.blocked(rows, (0, 0), (9, 9), E, 4, STOP, 2))

    def test_only_a_matching_ledge_ends_the_runway(self):
        self.assertFalse(self.blocked([".", "S", "#"], (0, 0), (9, 9), S, 4))
        self.assertTrue(self.blocked(["..S"], (0, 0), (9, 9), E, 4))
        self.assertFalse(self.blocked(["..E"], (0, 0), (9, 9), E, 4))

    def test_profile_without_prediction_never_predicts(self):
        self.assertFalse(self.blocked(["#"], (0, 0), (9, 9), E, 4, plans=0))


if __name__ == "__main__":
    unittest.main()

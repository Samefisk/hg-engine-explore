"""Run the real spawn-origin functions against an independent tile-line oracle.

Host-only geometry proof. Native terrain loading is a bounded stub; these tests
do not prove final-ROM packaging, live loading, or the rendered Hop.
"""

from pathlib import Path
import re
import unittest

from scripts.verify_overworld_spawn_identity import execute, function


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def harness_source():
    source = PRODUCT.read_text()
    names = (
        "OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN",
        "OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN",
        "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE",
        "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP",
        "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN",
        "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT",
        "OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT",
        "OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE",
        "OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE",
        "OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE",
        "OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES",
        "OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES",
        "OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES",
        "OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES",
    )
    constants = []
    for name in names:
        matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", source, re.M)
        if len(matches) != 1:
            raise AssertionError(f"expected one production constant: {name}")
        constants.extend(matches)
    header = (ROOT / "include/overworld_wild_helper.h").read_text()
    startup = re.findall(
        r"typedef struct OverworldWildSpawnStartup \{[^}]+\} OverworldWildSpawnStartup;",
        header,
    )
    if len(startup) != 1:
        raise AssertionError("expected exact public spawn-startup type")
    bodies = "\n".join((
        function(source, "OverworldWildSpawns_Abs", "int"),
        function(source, "OverworldWildSpawns_GetSpawnHopVisibleTravelScore", "int"),
        function(source, "OverworldWildSpawns_TryPickVisibleOffscreenOrigin", "BOOL"),
        function(source, "OverworldWildSpawns_PrepareSpawnAirborneStart", "BOOL"),
    ))
    return (PRELUDE.replace("/* CONSTANTS */", "\n".join(constants))
            .replace("/* STARTUP */", startup[0]) + bodies + DRIVER)


PRELUDE = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef int16_t s16;
typedef int32_t s32;
typedef int BOOL;
typedef int OverworldWildSpawnTerrain;
typedef struct { int unused; } OverworldWildSpawnState;
#define TRUE 1
#define FALSE 0
#define OW_WILD_SPAWN_TERRAIN_LAND 0
#define OW_WILD_SPAWN_TERRAIN_HEADBUTT 1
/* CONSTANTS */
/* STARTUP */
_Static_assert(sizeof(OverworldWildSpawnStartup) == 16, "startup public size");
_Static_assert(offsetof(OverworldWildSpawnStartup, targetX) == 0, "targetX ABI");
_Static_assert(offsetof(OverworldWildSpawnStartup, targetY) == 2, "targetY ABI");
_Static_assert(offsetof(OverworldWildSpawnStartup, startX) == 4, "startX ABI");
_Static_assert(offsetof(OverworldWildSpawnStartup, startY) == 6, "startY ABI");
_Static_assert(offsetof(OverworldWildSpawnStartup, locomotion) == 8, "locomotion ABI");
_Static_assert(offsetof(OverworldWildSpawnStartup, hopDirection) == 9, "direction ABI");
_Static_assert(offsetof(OverworldWildSpawnStartup, targetBaseY) == 12, "height ABI");
_Static_assert(OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP == 0, "UP ABI");
_Static_assert(OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN == 1, "DOWN ABI");
_Static_assert(OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT == 2, "LEFT ABI");
_Static_assert(OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT == 3, "RIGHT ABI");
_Static_assert(OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE == 255, "NONE ABI");
_Static_assert(OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN == 4, "Hop ABI");
_Static_assert(OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN == 9, "Fly In ABI");
_Static_assert(OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE == 8, "short Hop extent");
_Static_assert(OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE == 16, "Move extent");
_Static_assert(OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE == 16, "Fly In extent");
_Static_assert(OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES == 8, "view width");
_Static_assert(OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES == 6, "view height");
_Static_assert(OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES == 4, "safe margin");
_Static_assert(OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES == 1, "commit runway");
typedef struct { int x, y; } PlayerAvatar;
typedef struct { PlayerAvatar *playerAvatar; } FieldSystem;
static const int vx[4] = {0, 0, -1, 1};
static const int vy[4] = {-1, 1, 0, 0};
static int target_x, target_y, map_width, map_height, loaded_mask, queries;
static int walkable_mask, walkable_x[4], walkable_y[4];
static unsigned cases, checks;
static void require(int ok, const char *message) {
    checks++;
    if (!ok) {
        fprintf(stderr, "FAIL case %u: %s; target=(%d,%d) loaded=%X map=%dx%d\n",
                cases, message, target_x, target_y, loaded_mask, map_width, map_height);
        exit(1);
    }
}
static int GetPlayerXCoord(PlayerAvatar *p) { return p->x; }
static int GetPlayerYCoord(PlayerAvatar *p) { return p->y; }
static int OverworldWildSpawns_MovementDirectionDeltaX(u8 d) { return vx[d]; }
static int OverworldWildSpawns_MovementDirectionDeltaY(u8 d) { return vy[d]; }
static int loaded(int x, int y) {
    if (x < 0 || y < 0 || x >= map_width || y >= map_height) return 0;
    for (int d = 0; d < 4; d++) {
        if (((x == target_x - vx[d] * OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE
                    && y == target_y - vy[d] * OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE)
                || (x == target_x - vx[d] * OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE
                    && y == target_y - vy[d] * OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE)))
            return (loaded_mask & (1 << d)) != 0;
        if ((walkable_mask & (1 << d)) != 0
                && x == walkable_x[d] && y == walkable_y[d])
            return 1;
    }
    return 0;
}
static int GetMetatileBehaviorAt(FieldSystem *field, int x, int y) {
    require(field != NULL && x >= 0 && y >= 0, "native lookup received invalid source");
    queries++;
    return loaded(x, y) ? 0x02 : 0xFF;
}
static int OverworldWildSpawns_IsWalkableLandTile(FieldSystem *field, int x, int y) {
    (void)field;
    queries++;
    for (int d = 0; d < 4; d++)
        if ((walkable_mask & (1 << d)) != 0
                && x == walkable_x[d] && y == walkable_y[d])
            return 1;
    return 0;
}
static int OverworldWildSpawns_IsSpawnRunStartTile(
    FieldSystem *field, OverworldWildSpawnTerrain terrain, int x, int y) {
    (void)field; (void)terrain; (void)x; (void)y;
    return 0;
}
static int OverworldWildSpawns_IsNearActiveSpawn(
    OverworldWildSpawnState *state, int x, int y, int ignored) {
    (void)state; (void)x; (void)y; (void)ignored;
    return 0;
}
"""


DRIVER = r"""
static int inside(int x, int y, const PlayerAvatar *player) {
    return x >= player->x - 8 && x <= player->x + 8
        && y >= player->y - 6 && y <= player->y + 6;
}
static int safely_offscreen(int x, int y, const PlayerAvatar *player) {
    return abs(x - player->x) >= 8 + 4 || abs(y - player->y) >= 6 + 4;
}
static int safely_prepared(int x, int y, const PlayerAvatar *player) {
    return abs(x - player->x) >= 8 + 4 + 1 || abs(y - player->y) >= 6 + 4 + 1;
}
/* Independent geometry: enumerate the line's first inclusive on-screen tile.
 * The ranking measures remaining travel after entry, not a copied edge formula.
 * A start inside the safety margin is ineligible. A zero-travel ray is the
 * fallback when no ray enters the view before its destination.
 */
static int oracle(const PlayerAvatar *player) {
    int best = -1, best_travel = -1;
    for (int d = 0; d < 4; d++) {
        int x = target_x - vx[d] * OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE;
        int y = target_y - vy[d] * OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE;
        int travel = -1;
        if (!loaded(x, y) || !safely_prepared(x, y, player)) continue;
        for (int tile = 1; tile <= OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE; tile++) {
            if (!inside(x + tile * vx[d], y + tile * vy[d], player)) continue;
            travel = OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE - tile;
            break;
        }
        if (travel < 0
                && ((d < 2 && abs(target_x - player->x) > 8)
                    || (d >= 2 && abs(target_y - player->y) > 6)))
            travel = 0;
        if (travel > best_travel) { best = d; best_travel = travel; }
    }
    return best;
}
static int move_candidate(int direction, int distance) {
    walkable_x[direction] = target_x - vx[direction] * distance;
    walkable_y[direction] = target_y - vy[direction] * distance;
    return 1;
}
static int move_oracle(const PlayerAvatar *player) {
    for (int d = 0; d < 4; d++) {
        if ((walkable_mask & (1 << d)) != 0
                && safely_prepared(walkable_x[d], walkable_y[d], player))
            return d;
    }
    return -1;
}
static void run_case(int px, int py, int tx, int ty, int mask, int width, int height,
                     int explicit_direction) {
    cases++;
    PlayerAvatar player = {px, py};
    FieldSystem field = {&player};
    OverworldWildSpawnStartup state = {(s16)tx, (s16)ty, -1234, -2345, 0xA5, 0x5A, 0};
    OverworldWildSpawnStartup before = state;
    target_x = tx; target_y = ty; loaded_mask = mask;
    map_width = width; map_height = height; queries = 0;
    int expected = oracle(&player);
    if (explicit_direction != -2)
        require(expected == explicit_direction, "independent named-case direction differs");
    int accepted = OverworldWildSpawns_PrepareSpawnAirborneStart(
        &field, &state, OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN);
    require(queries <= 4, "more than four candidate lookups");
    require(accepted == (expected >= 0), "accept/reject differs from independent geometry");
    if (!accepted) {
        require(memcmp(&state, &before, sizeof(state)) == 0, "failure changed startup bytes");
        return;
    }
    require(safely_prepared(state.startX, state.startY, &player),
            "accepted origin lacks the commit runway");
    require(state.targetX == tx && state.targetY == ty, "selected landing changed");
    require(state.startX >= 0 && state.startY >= 0 && loaded(state.startX, state.startY),
            "accepted source is negative or unloaded");
    require(abs(state.startX - tx) + abs(state.startY - ty)
                == OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE
            && (state.startX == tx || state.startY == ty),
            "Hop is not exactly eight cardinal tiles");
    require(state.startX == tx - vx[expected] * OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE
            && state.startY == ty - vy[expected] * OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE,
            "best eligible visible direction or tie order changed");
    require(state.locomotion == 4 && state.hopDirection == expected,
            "startup output fields differ");
}
static void run_move_case(
    int px, int py, int tx, int ty, int mask, int expected_direction) {
    cases++;
    PlayerAvatar player = {px, py};
    FieldSystem field = {&player};
    OverworldWildSpawnState state = {0};
    int start_x = -1234, start_y = -2345;
    target_x = tx; target_y = ty; walkable_mask = mask; queries = 0;
    map_width = 1024; map_height = 1024;
    for (int d = 0; d < 4; d++)
        move_candidate(d, OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE);
    int expected = move_oracle(&player);
    require(expected == expected_direction, "independent Move direction differs");
    int accepted = OverworldWildSpawns_TryPickVisibleOffscreenOrigin(
        &state, &field, OW_WILD_SPAWN_TERRAIN_LAND,
        OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE,
        tx, ty, &start_x, &start_y);
    require(queries <= 128, "Move exceeded its bounded cardinal origin search");
    require(!!accepted == (expected >= 0), "Move accept/reject differs");
    if (!accepted) {
        require(start_x == -1234 && start_y == -2345, "failed Move changed output");
        return;
    }
    int distance = abs(start_x - tx) + abs(start_y - ty);
    require(start_x == walkable_x[expected] && start_y == walkable_y[expected],
            "Move did not select its eligible Hop-style origin");
    require(safely_prepared(start_x, start_y, &player),
            "Move origin lacks the commit runway");
    require(distance >= 1 && distance <= OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE
            && (start_x == tx || start_y == ty),
            "Move A is not within sixteen cardinal tiles of B");
}
static void run_move_fallback_case(void) {
    cases++;
    PlayerAvatar player = {32, 32};
    FieldSystem field = {&player};
    OverworldWildSpawnState state = {0};
    int start_x = -1234, start_y = -2345;
    target_x = 32; target_y = 42; walkable_mask = 1 << 0; queries = 0;
    map_width = 1024; map_height = 1024;
    move_candidate(0, 6);
    require(OverworldWildSpawns_TryPickVisibleOffscreenOrigin(
                &state, &field, OW_WILD_SPAWN_TERRAIN_LAND,
                OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE,
                target_x, target_y, &start_x, &start_y),
            "Move did not fall back from a blocked sixteen-tile point");
    require(start_x == 32 && start_y == 48,
            "Move did not keep the farthest eligible cardinal A");
    require(safely_prepared(start_x, start_y, &player),
            "Move fallback A lacks the commit runway");
}
static void run_commit_runway_case(void) {
    cases++;
    PlayerAvatar player = {568, 399};
    FieldSystem field = {&player};
    OverworldWildSpawnStartup state = {568, 405, -1234, -2345, 0xA5, 0x5A, 0};
    target_x = state.targetX; target_y = state.targetY; loaded_mask = 15;
    map_width = 1024; map_height = 1024; queries = 0;
    require(OverworldWildSpawns_PrepareSpawnAirborneStart(
                &field, &state, OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN),
            "initial Hop preparation failed");
    require(!(state.startX == 568 && state.startY == 389),
            "Hop preparation used a source without commit runway");
    require(safely_prepared(state.startX, state.startY, &player),
            "Hop preparation did not reserve commit runway");
    player.y = 398;
    require(safely_offscreen(state.startX, state.startY, &player),
            "one-tile commit drift consumed the required safety margin");
    require(queries <= 4, "Hop preparation exceeded four candidate lookups");
}
static void run_fly_in_case(void) {
    cases++;
    PlayerAvatar player = {32, 32};
    FieldSystem field = {&player};
    OverworldWildSpawnStartup state = {32, 32, -1234, -2345, 0xA5, 0x5A, 0};
    target_x = state.targetX; target_y = state.targetY; loaded_mask = 15;
    map_width = 64; map_height = 64; queries = 0;
    require(OverworldWildSpawns_PrepareSpawnAirborneStart(
                &field, &state, OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN),
            "Fly In preparation failed");
    require(abs(state.startX - state.targetX) + abs(state.startY - state.targetY)
                == OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE,
            "Fly In origin is not the fixed off-screen distance");
    require(state.locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN,
            "Fly In preparation did not publish its locomotion");
    require(safely_prepared(state.startX, state.startY, &player),
            "Fly In origin lacks the commit runway");
    require(queries <= 4, "Fly In preparation exceeded four candidate lookups");
}
int main(void) {
    /* Exact live RED: old code chooses (542,376), on the inclusive left edge. */
    run_case(550, 381, 558, 376, 15, 1024, 1024, -2);
    run_case(32, 32, 32, 32, 15, 64, 64, -2);
    run_case(32, 32, 32, 32, 3, 64, 64, -2);
    run_case(32, 32, 32, 32, 0, 64, 64, -1); /* all sources unloaded */
    for (int d = 0; d < 4; d++)
        run_case(32, 32, 32, 32, 1 << d, 64, 64, -2);
    /* Each view edge and adjacent tiles; one loaded source at a time. */
    for (int d = 0; d < 4; d++) {
        int edge = d < 2 ? 6 : 8;
        for (int offset = -1; offset <= 1; offset++)
            run_case(32, 32,
                     32 + vx[d] * (OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE
                         - edge + offset),
                     32 + vy[d] * (OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE
                         - edge + offset),
                     1 << d, 64, 64, -2);
    }
    /* Negative-coordinate source, map zero, and 32-tile map-block boundaries. */
    const int centers[][2] = {{0, 0}, {15, 16}, {31, 31}, {32, 32}, {63, 63}};
    for (unsigned p = 0; p < sizeof(centers) / sizeof(centers[0]); p++)
        for (int dx = -20; dx <= 20; dx++)
            for (int dy = -20; dy <= 20; dy++) {
                int tx = centers[p][0] + dx, ty = centers[p][1] + dy;
                if (tx < 0 || ty < 0 || tx >= 64 || ty >= 64) continue;
                for (int mask = 0; mask < 16; mask++)
                    run_case(centers[p][0], centers[p][1], tx, ty, mask, 64, 64, -2);
    run_move_case(585, 406, 584, 410, 1 << 1, 1);
    run_move_case(32, 32, 32, 28, 1 << 0, 0);
    run_move_case(32, 32, 32, 36, 1 << 1, 1);
    run_move_case(32, 32, 29, 32, 1 << 2, 2);
    run_move_case(32, 32, 35, 32, 1 << 3, 3);
    run_move_case(32, 32, 35, 35, 1 << 3, 3);
    run_move_case(32, 32, 33, 42, 1 << 3, 3);
    run_move_case(32, 32, 36, 32, 0, -1);
    /* A is walkable but still visible, so the spawn must fail. */
    run_move_case(32, 32, 44, 32, 1 << 3, -1);
    /* A negative visible-travel score must still be checked. */
    run_move_case(32, 32, 32, 60, 1 << 0, 0);
    run_move_fallback_case();
    run_commit_runway_case();
    run_fly_in_case();
            }
    printf("PASS %u cases, %u checks: actual source, independent offscreen geometry\n", cases, checks);
    return 0;
}
"""


class SpawnHopOriginTests(unittest.TestCase):
    def test_actual_source_geometry_and_startup_transaction(self):
        result = execute(harness_source())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, end="")

    def test_old_guard_and_boundary_tie_mutations_are_rejected(self):
        source = harness_source()
        controls = (
            ("missing safety margin",
             "|| (OverworldWildSpawns_Abs(candidateX - playerX)",
             "|| (0 && OverworldWildSpawns_Abs(candidateX - playerX)",
             "accept/reject differs"),
            ("reverse tie order", "if (visibleTravel > bestVisibleTravel)",
             "if (visibleTravel >= bestVisibleTravel)", "differs"),
        )
        for name, old, new, expected_error in controls:
            with self.subTest(control=name):
                self.assertEqual(source.count(old), 1, f"mutation seam differs: {name}")
                result = execute(source.replace(old, new))
                self.assertNotEqual(result.returncode, 0, f"known-bad control passed: {name}")
                self.assertIn(expected_error, result.stderr)

    def test_prepare_reserves_one_update_of_commit_runway(self):
        source = function(
            PRODUCT.read_text(),
            "OverworldWildSpawns_TryPickVisibleOffscreenOrigin",
            "BOOL",
        )
        self.assertEqual(
            source.count("OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES"),
            2,
        )


if __name__ == "__main__":
    unittest.main()

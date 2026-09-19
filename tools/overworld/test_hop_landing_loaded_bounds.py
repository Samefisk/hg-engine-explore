"""Host regression for rejecting Hop landings outside loaded terrain."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_spawn_identity import function


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def program():
    source = SOURCE.read_text()
    helper = ""
    for name in (
        "OverworldWildSpawns_IsPlayableMapMatrixTile",
    ):
        if name in source:
            helper += function(source, name, "BOOL")
    if "OverworldWildSpawns_TryGetLoadedMetatileBehavior" in source:
        helper += function(
            source,
            "OverworldWildSpawns_TryGetLoadedMetatileBehavior",
            "BOOL",
        )
    land = function(source, "OverworldWildSpawns_IsLandMapTile", "BOOL")
    return PRELUDE + helper + land + DRIVER


def execute():
    with tempfile.TemporaryDirectory(prefix="hop-loaded-bounds-") as temporary:
        binary = Path(temporary) / "hop-loaded-bounds"
        compiled = subprocess.run(
            [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O0",
             "-x", "c", "-", "-o", str(binary)],
            input=program(), text=True, capture_output=True,
        )
        if compiled.returncode:
            return compiled
        return subprocess.run([str(binary)], text=True, capture_output=True)


PRELUDE = r'''
#include <stdio.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define MAP_EVERYWHERE 0
#define OW_WILD_TILE_HEADBUTT 0x54
#define OW_WILD_MAP_BLOCK_SHIFT 5
#define OW_WILD_MAP_MATRIX_HEADERS_OFFSET 0x6
typedef struct FieldSystem { void *map_matrix; } FieldSystem;
static u8 behavior;
static BOOL blocked;
static int behaviorReads;
static u8 GetMetatileBehaviorAt(FieldSystem *field, int x, int y) {
    (void)field; (void)x; (void)y; behaviorReads++; return behavior;
}
static BOOL IsMetatileBlockedAt(FieldSystem *field, int x, int y) {
    (void)field; (void)x; (void)y; return blocked;
}
static BOOL OverworldWildSpawns_IsSurfBehavior(u8 value) {
    return value == 0x10;
}
'''


DRIVER = r'''
#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "line %d: %s; behavior=%u blocked=%d reads=%d\n", \
        __LINE__, #value, behavior, blocked, behaviorReads); return 1; \
} } while (0)
int main(void) {
    unsigned char matrix[16] = {1, 1, 0, 1, 1, 0, 33, 0};
    FieldSystem field = {matrix};
    behavior = 0xFF; blocked = FALSE; behaviorReads = 0;
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, 12, 9));
    CHECK(behaviorReads == 1);
    matrix[6] = MAP_EVERYWHERE;
    behavior = 0x02; blocked = FALSE; behaviorReads = 0;
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, 12, 9));
    CHECK(behaviorReads == 0);
    matrix[6] = 33;
    behavior = 0x02; blocked = FALSE; behaviorReads = 0;
    CHECK(OverworldWildSpawns_IsLandMapTile(&field, 12, 9));
    CHECK(behaviorReads == 1);
    behavior = OW_WILD_TILE_HEADBUTT;
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, 12, 9));
    behavior = 0x10;
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, 12, 9));
    behavior = 0x02; blocked = TRUE;
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, 12, 9));
    CHECK(!OverworldWildSpawns_IsLandMapTile(NULL, 12, 9));
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, -1, 9));
    CHECK(!OverworldWildSpawns_IsLandMapTile(&field, 12, -1));

    unsigned char route29[1604] = {47, 17};
    unsigned route29Index = 12 * 47 + 18;
    route29[6 + route29Index * 2] = 33;
    field.map_matrix = route29;
    CHECK(OverworldWildSpawns_IsPlayableMapMatrixTile(&field, 585, 415));
    CHECK(!OverworldWildSpawns_IsPlayableMapMatrixTile(&field, 585, 416));
    return 0;
}
'''


class HopLandingLoadedBoundsTests(unittest.TestCase):
    def test_invalid_native_tile_sentinel_is_not_land(self):
        result = execute()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shared_hop_classifier_checks_loaded_tile_before_surface_catalog(self):
        source = SOURCE.read_text()
        body = function(
            source,
            "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
            "OverworldMotionDecision",
        )
        loaded = body.find("OverworldWildSpawns_TryGetLoadedMetatileBehavior")
        surface = body.find("OverworldWildSpawns_QuerySurface")
        self.assertGreaterEqual(loaded, 0, "shared Hop classifier lacks loaded-tile gate")
        self.assertGreater(surface, loaded, "surface catalog runs before loaded-tile gate")

    def test_boundary_surface_does_not_require_adjacent_padding_to_be_playable(self):
        source = SOURCE.read_text()
        body = function(
            source,
            "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
            "OverworldMotionDecision",
        )
        self.assertNotIn(
            "OverworldWildSpawns_HasPlayableMapMatrixNeighborhood",
            body,
            "a valid boundary landing is rejected because its neighbor is padding",
        )


if __name__ == "__main__":
    unittest.main()

"""S1 spawn scan parity: actual C bodies, stubbed engine, no runtime proof.

The independent oracle preserves row-major candidates and reservoir RNG calls.
Run: python3 -m unittest tools.overworld.test_spawn_destination_scan -v
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def function(source, name, returns):
    matches = list(re.finditer(r"\bstatic\b[^;{}]*?\b" + name + r"\s*\([^;{}]*\)\s*\{", source))
    if len(matches) != 1:
        raise ValueError("expected one definition of " + name)
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            start = source.index(name, match.start(), match.end())
            return "static " + returns + " " + source[start:end + 1]
    raise ValueError("unterminated " + name)


PRELUDE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
typedef enum OverworldWildHelperPrepareResult {
    OW_WILD_HELPER_PREPARE_FAILED = 0,
    OW_WILD_HELPER_PREPARE_READY = 1,
    OW_WILD_HELPER_PREPARE_POSITION_PENDING = 2,
} OverworldWildHelperPrepareResult;
typedef struct { int unused; } Avatar;
typedef struct { Avatar *playerAvatar; } FieldSystem;
typedef struct { int startX, startY; } OverworldWildSpawnPosition;
typedef struct OverworldWildSpawnDestinationScan {
    int16_t playerX, playerY;
    int16_t nextX, nextY;
    u16 destinationMask;
    u8 candidateCount;
} OverworldWildSpawnDestinationScan;
typedef struct { OverworldWildSpawnPosition position; } OverworldWildPreparedSpawn;
typedef struct {
    OverworldWildPreparedSpawn queuedSpawn;
    u8 refillPositionChecksRemaining;
    OverworldWildSpawnDestinationScan spawnDestinationScan;
} OverworldWildOverlayRuntimeState;
typedef struct { void *movementRuntimeState; } OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)((state)->movementRuntimeState))
#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
#define OW_WILD_PROFILE_DESTINATION_CHECKS_PER_UPDATE 12
#define OVERWORLD_MOTION_DECISION_ACCEPTED 0
typedef struct { int height; u16 surfaceId; u8 surfaceType, nodeId; } OverworldWildSurfaceHit;
static int fixture, match_mode, test_behavior, test_surface, test_canopy;
static int front_calls, rng_calls, canopy_calls, metatile_calls, visit_x, visit_y;
static u32 rng_state;
static int trace[4096], trace_count;
static int index_at(int x,int y) { return (y-12)*17+x-12; }
static void record(int stage,int x,int y) { trace[trace_count++]=stage*1000+index_at(x,y); }
static int GetPlayerXCoord(Avatar *a) { (void)a; return 20; }
static int GetPlayerYCoord(Avatar *a) { (void)a; return 20; }
static int OverworldWildSpawns_Abs(int x) { return abs(x); }
static int OverworldWildSpawns_Max(int a,int b) { return a>b?a:b; }
static BOOL OverworldWildSpawns_IsPlayerTile(FieldSystem *f,int x,int y) { (void)f; return x==20 && y==20; }
static BOOL OverworldWildSpawns_IsPlayerFrontTile(FieldSystem *f,int x,int y) { (void)f; front_calls++; return x==21 && y==20; }
static u8 GetMetatileBehaviorAt(FieldSystem *f,int x,int y) {
    (void)f; metatile_calls++; return index_at(x,y)%4;
}
static BOOL OverworldWildSpawns_IsSurfBehavior(u8 b) { return b==2; }
static BOOL OverworldWildSpawns_IsLandMapTile(FieldSystem *f,int x,int y) {
    (void)f; return (match_mode?test_behavior:index_at(x,y)%4)!=2;
}
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *hit) {
    (void)f; int i=index_at(x,y);
    int surface=match_mode?test_surface:(fixture==1 && i%17==0?i%4:-1);
    if(surface<0) return FALSE;
    hit->surfaceType=surface==5?OW_WILD_SURFACE_TYPE_FLOWERBED:surface;
    hit->surfaceId=surface==5?OW_WILD_SURFACE_ID_NATIVE_GROUND:
        surface==4?OW_WILD_SURFACE_ID_NATIVE_CANOPY:42;
    return TRUE;
}
static u16 OverworldWildSpawns_GetCanopyTerrainBit(FieldSystem *f,int x,int y) {
    (void)f; canopy_calls++;
    return (match_mode?test_canopy:index_at(x,y)%19==0)?OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY:0;
}
static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *f,int x,int y) {
    (void)f; record(2,x,y); return fixture==2 || (fixture==1 && index_at(x,y)%11==0) || (x==20 && y==20);
}
static BOOL OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(FieldSystem *f,void *object,int x,int y) {
    (void)f; (void)object; record(3,x,y); return fixture==2 || (fixture==1 && index_at(x,y)%11==0);
}
static BOOL OverworldWildSpawns_IsNearActiveSpawn(OverworldWildSpawnState *s,int x,int y,int distance) {
    (void)s; if(distance!=OW_WILD_SPAWN_MIN_MON_DISTANCE) abort();
    record(4,x,y); return fixture==1 && index_at(x,y)%13==0;
}
static u32 gf_rand(void) {
    rng_calls++; record(5,visit_x,visit_y);
    rng_state=rng_state*1664525u+1013904223u; return rng_state;
}
'''

DRIVER = r'''
static int run_scan(OverworldWildSpawnState *state,FieldSystem *field,int mask,
        OverworldWildSpawnPosition *position,int *query_counts,int *update_count) {
    int result;
    *update_count=0;
    do {
        int before=trace_count, queries=0;
        result=OverworldWildSpawns_TryPickSpawnDestinationMask(state,field,mask,position);
        for(int i=before;i<trace_count;i++) if(trace[i]>=1000 && trace[i]<2000) queries++;
        query_counts[(*update_count)++]=queries;
        if(*update_count>=512) abort();
    } while(OW_WILD_RUNTIME(state)->refillPositionChecksRemaining==
            OW_WILD_PROFILE_DESTINATION_SCAN_PENDING);
    return result;
}
int main(int argc,char **argv) {
    Avatar avatar={0}; FieldSystem field={&avatar}; OverworldWildOverlayRuntimeState runtime={0};
    OverworldWildSpawnState state={&runtime}; int query_counts[512],update_count;
    if(argc==2 && argv[1][0]=='c') {
        for(int mask=0;mask<1024;mask++) {
            runtime=(OverworldWildOverlayRuntimeState){0};
            runtime.queuedSpawn.position=(OverworldWildSpawnPosition){777,888};
            trace_count=metatile_calls=rng_calls=front_calls=canopy_calls=0;
            rng_state=0x12345678;
            run_scan(&state,&field,mask,&runtime.queuedSpawn.position,query_counts,&update_count);
            printf("%d\n",metatile_calls);
        }
        return 0;
    }
    if(argc==2 && argv[1][0]=='m') {
        match_mode=1;
        for(int mask=0;mask<1024;mask++) for(test_behavior=0;test_behavior<4;test_behavior++)
        for(test_surface=-1;test_surface<6;test_surface++) for(test_canopy=0;test_canopy<2;test_canopy++)
        for(int point=0;point<3;point++) {
            int x=20+point;
            printf("%d\n",!!OverworldWildSpawns_DoesAllowedTileMatch(&field,mask,test_behavior,x,20));
        }
        return 0;
    }
    if(argc!=3) return 2;
    fixture=atoi(argv[1]); int mask=atoi(argv[2]); rng_state=0x12345678;
    runtime.queuedSpawn.position=(OverworldWildSpawnPosition){777,888};
    int result=run_scan(&state,&field,mask,&runtime.queuedSpawn.position,query_counts,&update_count);
    printf("{\"result\":%d,\"position\":[%d,%d],\"rngCalls\":%d,\"rngState\":%u,\"frontCalls\":%d,\"canopyCalls\":%d,\"metatileCalls\":%d,\"queryCounts\":[",
        !!result,runtime.queuedSpawn.position.startX,runtime.queuedSpawn.position.startY,
        rng_calls,rng_state,front_calls,canopy_calls,metatile_calls);
    for(int i=0;i<update_count;i++) printf("%s%d",i?",":"",query_counts[i]);
    printf("],\"trace\":[");
    for(int i=0;i<trace_count;i++) printf("%s%d",i?",":"",trace[i]);
    puts("]}"); return 0;
}
'''


def constants(source):
    header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    # Take complete continued macros so the C compiler sees production masks.
    joined = (source + "\n" + header).replace("\\\n", " ")
    names = ["OW_WILD_SPAWN_MIN_DISTANCE", "OW_WILD_SPAWN_MAX_DISTANCE",
             "OW_WILD_SPAWN_MIN_MON_DISTANCE", "OW_WILD_TILE_ENCOUNTER_GRASS",
             "OW_WILD_TILE_LONG_GRASS", "OW_WILD_SURFACE_TYPE_CANOPY",
             "OW_WILD_SURFACE_TYPE_FLOWERBED", "OW_WILD_SURFACE_ID_NATIVE_CANOPY",
             "OW_WILD_SURFACE_ID_NATIVE_GROUND"]
    lines = []
    for line in joined.splitlines():
        if re.match(r"#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_", line) or re.match(
                r"#define OW_WILD_SURFACE_TYPE_TERRAIN_MASK\(", line):
            lines.append(line)
    for name in names:
        found = re.findall(r"^#define " + name + r"\s+[^\n]+", joined, re.M)
        if len(found) != 1:
            raise ValueError("constant missing or repeated: " + name)
        lines.append(found[0])
    # Fixture codes are intentionally independent of the game metatile values.
    lines += ["#undef OW_WILD_TILE_ENCOUNTER_GRASS", "#define OW_WILD_TILE_ENCOUNTER_GRASS 0",
              "#undef OW_WILD_TILE_LONG_GRASS", "#define OW_WILD_TILE_LONG_GRASS 1"]
    return "\n".join(lines)


def allowed(mask, behavior, surface, canopy, point):
    # Authored surface owns occupancy even when it uses native-ground height.
    if mask == 8 and behavior not in (0, 1):
        return False
    if surface >= 0:
        surface_type = 3 if surface == 5 else surface
        surface_mask = 4 if surface_type == 4 else 64 << surface_type
        return bool(mask & surface_mask)
    permits = (1 if behavior != 2 else 2) | (8 if behavior in (0, 1) else 0)
    permits |= 16 if point == 0 else 32 if point == 1 else 0
    return bool(mask & permits)


def oracle(style, mask):
    trace, selected = [], [777, 888]
    seed, count = 0x12345678, 0
    for y in range(12, 29):
        for x in range(12, 29):
            idx = (y - 12) * 17 + x - 12
            point = 0 if (x, y) == (20, 20) else 1 if (x, y) == (21, 20) else 2
            if 17 <= x <= 23 and 17 <= y <= 23 and not (
                    point == 0 and mask & 16 or point == 1 and mask & 32):
                continue
            trace.append(1000 + idx)
            surface = idx % 4 if style == 1 and idx % 17 == 0 else -1
            if not allowed(mask, idx % 4, surface, idx % 19 == 0, point):
                continue
            trace.append((3000 if point == 0 else 2000) + idx)
            if style == 2 or style == 1 and idx % 11 == 0:
                continue
            trace.append(4000 + idx)
            if style == 1 and idx % 13 == 0:
                continue
            trace.append(5000 + idx)
            count += 1
            seed = (seed * 1664525 + 1013904223) & 0xffffffff
            if seed % count == 0:
                selected = [x, y]
    return dict(result=int(count != 0), position=selected, rngCalls=count, rngState=seed, trace=trace)


def require_candidate_query_budget(update_traces, maximum=12):
    """Reject any game update that exceeds the bounded tile-query batch."""
    for update, trace in enumerate(update_traces):
        candidate_queries = sum(1000 <= item < 2000 for item in trace)
        if candidate_queries > maximum:
            raise AssertionError(
                f"spawn destination update {update} checked {candidate_queries} "
                f"candidates; maximum is {maximum}"
            )


class SpawnDestinationScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="spawn-destination-scan-")
        cls.addClassCleanup(cls.directory.cleanup)
        source = SOURCE.read_text()
        matcher = "OverworldWildSpawns_DoesAllowedTileMatch"
        match_body = function(source, matcher, "BOOL").replace(matcher + "(", matcher + "_Body(", 1)
        # Mark candidate visits at the actual matcher boundary, not at an
        # optional terrain read. The production matcher body stays unchanged.
        wrapper = r'''
static BOOL OverworldWildSpawns_DoesAllowedTileMatch(FieldSystem *f,u16 mask,u8 behavior,int x,int y) {
    if(!match_mode) { visit_x=x;visit_y=y;record(1,x,y); }
    return OverworldWildSpawns_DoesAllowedTileMatch_Body(f,mask,behavior,x,y);
}

/*
 * The destination scanner now delegates terrain and occupancy to the shared
 * landing classifier. Other focused extracted-C tests cover the full
 * classifier. This adapter keeps this scan test bounded while preserving the
 * scanner-visible terrain, surface, and occupancy decisions.
 */
static int OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
        OverworldWildSpawnState *state,int slot,FieldSystem *field,u16 mask,
        int x,int y,int final_x,int final_y) {
    OverworldWildSurfaceHit hit;
    BOOL surface;
    BOOL player;
    u8 behavior=0;
    (void)state;(void)slot;(void)final_x;(void)final_y;
    surface=OverworldWildSpawns_QuerySurface(field,x,y,&hit);
    if(!surface) behavior=GetMetatileBehaviorAt(field,x,y);
    if(!OverworldWildSpawns_DoesAllowedTileMatch(field,mask,behavior,x,y)) return 2;
    player=OverworldWildSpawns_IsPlayerTile(field,x,y);
    if(player && (mask&OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER))
        return OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(field,NULL,x,y)?1:0;
    return OverworldWildSpawns_IsTileOccupiedByObject(field,x,y)?1:0;
}
'''
        bodies = "\n".join((function(source, "OverworldWildSpawns_GetTerrainBit", "u16"),
            match_body, wrapper,
            function(source, "OverworldWildSpawns_TryPickSpawnDestinationMask", "BOOL")))
        unit = Path(cls.directory.name) / "scan.c"
        cls.binary = Path(cls.directory.name) / "scan"
        unit.write_text(constants(source) + "\n" + PRELUDE + bodies + DRIVER)
        result = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                                 "-Wall", "-Wextra", "-Wno-unused-function", str(unit), "-o", str(cls.binary)],
                                text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def scan(self, style, mask):
        return json.loads(subprocess.check_output([str(self.binary), str(style), str(mask)], text=True))

    def test_budget_checker_rejects_more_than_twelve_candidates(self):
        with self.assertRaisesRegex(AssertionError, "checked 13 candidates"):
            require_candidate_query_budget([list(range(1000, 1013))])

    def test_profile_destination_masks_check_at_most_twelve_candidates_per_update(self):
        for mask in (0, 8, 448, 512, 15):
            with self.subTest(mask=mask):
                actual = self.scan(0, mask)
                self.assertEqual(actual["queryCounts"][0], 0,
                                 "profile work must not share the helper's final update")
                require_candidate_query_budget(
                    [[1000] * count for count in actual["queryCounts"]])
                self.assertLessEqual(len(actual["queryCounts"]), 21,
                                     "a full 240-candidate scan must finish in 12-query batches")

    def test_candidate_order_rng_occupancy_and_failure_output(self):
        for style in (0, 1, 2):
            for mask in sorted({0, 1, 2, 4, 8, 16, 32, 48, 49, 1023, *range(64, 1024, 64)}):
                with self.subTest(style=style, mask=mask):
                    actual = self.scan(style, mask)
                    del actual["queryCounts"]
                    del actual["frontCalls"]
                    del actual["canopyCalls"]
                    del actual["metatileCalls"]
                    self.assertEqual(actual, oracle(style, mask))

    def test_each_no_surface_candidate_reads_metatile_once(self):
        counts = list(map(int, subprocess.check_output([str(self.binary), "counts"], text=True).splitlines()))
        self.assertEqual(len(counts), 1024)
        # The shared landing classifier checks the catalog first. With this
        # no-surface fixture, every visited candidate then needs one native
        # metatile read. Player/front permissions add their normally skipped
        # center candidates.
        for mask, actual in enumerate(counts):
            expected = 240 + bool(mask & 16) + bool(mask & 32)
            with self.subTest(mask=mask):
                self.assertEqual(actual, expected)

    def test_no_front_lookup_without_front_permission(self):
        for mask in (0, 1, 2, 4, 8, 16, 64):
            with self.subTest(mask=mask):
                self.assertEqual(self.scan(0, mask)["frontCalls"], 0,
                                 "scan must not inspect the front object when FRONT is not permitted")

    def test_canopy_has_no_procedural_fallback(self):
        for mask in (0, 1, 2, 4, 8, 16, 32, 48, 64, 1023):
            with self.subTest(mask=mask):
                self.assertEqual(self.scan(0, mask)["canopyCalls"], 0,
                                 "scan must use only the generated Canopy catalog")

    def test_tile_masks_surface_veto_native_ground_and_catalog_canopy(self):
        actual = list(map(int, subprocess.check_output([str(self.binary), "match"], text=True).splitlines()))
        expected = [int(allowed(mask, behavior, surface, canopy, point))
                    for mask in range(1024) for behavior in range(4) for surface in range(-1, 6)
                    for canopy in range(2) for point in range(3)]
        self.assertEqual(len(actual), len(expected))
        for index, (got, want) in enumerate(zip(actual, expected)):
            if got != want:
                self.fail(f"tile contract case {index}: actual {got}, expected {want}")


if __name__ == "__main__":
    unittest.main()

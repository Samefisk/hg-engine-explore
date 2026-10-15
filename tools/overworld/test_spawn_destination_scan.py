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
from copy import deepcopy


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
#include <string.h>
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
typedef struct { Avatar *playerAvatar; const void *map_matrix; } FieldSystem;
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
typedef struct OverworldWildSurfaceCatalog { int unused; } OverworldWildSurfaceCatalog;
typedef struct OverworldWildBehaviorDataBlob { int surfaceModels[1]; } OverworldWildBehaviorDataBlob;
typedef struct OverworldPickupRouteWildOps { int unused; } OverworldPickupRouteWildOps;
typedef struct OverworldPickupRouteWildLandingCall {
    OverworldWildSpawnState *state;
    FieldSystem *field;
    const OverworldWildBehaviorDataBlob *behaviorData;
    const OverworldPickupRouteWildOps *ops;
    void *collisionIgnoredObject;
    int slot;
    u16 allowedTile;
    int x,y,finalTargetX,finalTargetY;
} OverworldPickupRouteWildLandingCall;
typedef struct OverworldQueryCodeAddonEntry {
    OverworldMotionDecision (*landingWild)(const OverworldPickupRouteWildLandingCall *);
} OverworldQueryCodeAddonEntry;
static const OverworldPickupRouteWildOps sOverworldWildRouteOps={0};
static void *sOverworldWildCollisionIgnoredObject=(void *)(uintptr_t)0x1234;
static OverworldWildBehaviorDataBlob fixture_blob;
static OverworldMotionDecision FixtureLanding(const OverworldPickupRouteWildLandingCall *);
static const OverworldQueryCodeAddonEntry fixture_entry={FixtureLanding};
static int addon_calls,blob_calls,landing_calls,missing_addon,missing_blob,expected_mask;
static int addon_per_update[512],blob_per_update[512],landing_per_update[512];
static OverworldWildSpawnState *expected_state;
static int expected_slot=-1,direct_mode,field_ready=1;
static FieldSystem *gFieldSysPtr;
static BOOL sub_0203DF8C(FieldSystem *field) { return field!=NULL && field_ready; }
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem *field,const void *transition) {
    if(!field || transition) abort();
    addon_calls++;
    return missing_addon?NULL:&fixture_entry;
}
/* Production GetBehaviorDataBlob publishes the cached package only after
 * DecodeBehaviorDataBlob -> Resolver.inspectClass -> BehaviorResolver_BlobValid
 * accepts its exact current header/layout. The resolver verifier covers that
 * admission; this cached-owner seam returns the valid package or NULL. */
static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void) {
    blob_calls++;
    return missing_blob?NULL:&fixture_blob;
}
typedef struct { int height; u16 surfaceId; u8 surfaceType, nodeId; } OverworldWildSurfaceHit;
static BOOL FixtureRuntimeQuerySurface(FieldSystem *,const OverworldWildSurfaceCatalog *,int,int,OverworldWildSurfaceHit *);
typedef struct { BOOL (*querySurface)(FieldSystem *,const OverworldWildSurfaceCatalog *,int,int,OverworldWildSurfaceHit *); } FixtureRuntimeEntry;
static const FixtureRuntimeEntry fixture_runtime={FixtureRuntimeQuerySurface};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&fixture_runtime)
static int fixture, match_mode, test_behavior, test_surface, test_canopy;
static int forced_height_owner=-1;
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
static BOOL IsMetatileBlockedAt(FieldSystem *f,int x,int y) { (void)f;(void)x;(void)y;return FALSE; }
static BOOL OverworldWildSpawns_IsLandMapTile(FieldSystem *f,int x,int y) {
    (void)f; return (match_mode?test_behavior:index_at(x,y)%4)!=2;
}
static BOOL FixtureRuntimeQuerySurface(FieldSystem *f,const OverworldWildSurfaceCatalog *catalog,int x,int y,OverworldWildSurfaceHit *hit) {
    (void)f; if(catalog!=(const OverworldWildSurfaceCatalog *)fixture_blob.surfaceModels) abort();
    int i=index_at(x,y);
    int surface=match_mode?test_surface:fixture==3?3:fixture==4?0:fixture==5?5:
        (fixture==1 && i%17==0?i%4:-1);
    if(surface<0) return FALSE;
    hit->surfaceType=surface==5?OW_WILD_SURFACE_TYPE_FLOWERBED:surface;
    hit->surfaceId=surface==5?OW_WILD_SURFACE_ID_NATIVE_GROUND:
        surface==4?OW_WILD_SURFACE_ID_NATIVE_CANOPY:42;
    if(forced_height_owner>=0) hit->surfaceId=forced_height_owner
        ? OW_WILD_SURFACE_ID_NATIVE_GROUND-(hit->surfaceType>>2) : 42;
    return TRUE;
}
static u16 OverworldWildSpawns_GetCanopyTerrainBit(FieldSystem *,int,int);
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
        int addon_before=addon_calls,blob_before=blob_calls,landing_before=landing_calls;
        result=OverworldWildSpawns_TryPickSpawnDestinationMask(state,field,mask,position);
        for(int i=before;i<trace_count;i++) if(trace[i]>=1000 && trace[i]<2000) queries++;
        addon_per_update[*update_count]=addon_calls-addon_before;
        blob_per_update[*update_count]=blob_calls-blob_before;
        landing_per_update[*update_count]=landing_calls-landing_before;
        query_counts[(*update_count)++]=queries;
        if(*update_count>=512) abort();
    } while(OW_WILD_RUNTIME(state)->refillPositionChecksRemaining==
            OW_WILD_PROFILE_DESTINATION_SCAN_PENDING);
    return result;
}
int main(int argc,char **argv) {
    u8 matrix[8]={1,1,0,0,0,0,1,0};
    Avatar avatar={0}; FieldSystem field={&avatar,matrix}; OverworldWildOverlayRuntimeState runtime={0};
    OverworldWildSpawnState state={&runtime}; int query_counts[512],update_count;
    gFieldSysPtr=&field;
    if(argc==2 && !strcmp(argv[1],"terrain")) {
        match_mode=1;
        for(test_surface=-1;test_surface<5;test_surface++) for(forced_height_owner=0;forced_height_owner<2;forced_height_owner++) {
            printf("%d %d %d %d\n",
                OverworldWildSpawns_GetTerrainBit(&field,12,12,TRUE),
                OverworldWildSpawns_GetTerrainBit(&field,12,12,FALSE),
                OverworldWildSpawns_GetElevatedTerrainBit(&field,12,12),
                OverworldWildSpawns_GetCanopyTerrainBit(&field,12,12));
        }
        return 0;
    }
    if(argc==2 && argv[1][0]=='p') {
        int probe=atoi(argv[1]+1),x=12,y=12;
        FieldSystem other={&avatar,matrix},*active=&field;
        direct_mode=match_mode=1;test_surface=-1;test_behavior=0;expected_mask=448;
        switch(probe) {
        case 1:test_surface=3;break;
        case 2:test_surface=0;break;
        case 3:missing_blob=1;break;
        case 4:field_ready=0;break;
        case 5:active=&other;break;
        case 6:matrix[6]=0;break;
        case 7:expected_state=&state;expected_slot=2;break;
        case 8:expected_slot=0;break;
        case 9:expected_mask=449;break;
        case 10:expected_mask=0;break;
        case 11:expected_mask=449;missing_blob=1;break;
        case 12:expected_mask=512;test_surface=5;break;
        case 13:x=-1;break;
        case 14:active=NULL;break;
        case 15:test_surface=0;missing_addon=1;break;
        default:if(probe!=0) abort();
        }
        OverworldMotionDecision decision=OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
            expected_state,expected_slot,active,expected_mask,x,y,-1,-1);
        printf("{\"decision\":%d,\"addonCalls\":%d,\"blobCalls\":%d,\"landingCalls\":%d,\"metatileCalls\":%d,\"rngCalls\":%d}\n",
            decision,addon_calls,blob_calls,landing_calls,metatile_calls,rng_calls);
        return 0;
    }
    if(argc==2 && argv[1][0]=='c') {
        for(int mask=0;mask<1024;mask++) {
            runtime=(OverworldWildOverlayRuntimeState){0};
            runtime.queuedSpawn.position=(OverworldWildSpawnPosition){777,888};
            trace_count=metatile_calls=rng_calls=front_calls=canopy_calls=0;
            rng_state=0x12345678;expected_mask=mask;
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
    fixture=atoi(argv[1]); int mask=atoi(argv[2]); expected_mask=mask;rng_state=0x12345678;
    runtime.queuedSpawn.position=(OverworldWildSpawnPosition){777,888};
    int result=run_scan(&state,&field,mask,&runtime.queuedSpawn.position,query_counts,&update_count);
    printf("{\"result\":%d,\"position\":[%d,%d],\"rngCalls\":%d,\"rngState\":%u,\"frontCalls\":%d,\"canopyCalls\":%d,\"metatileCalls\":%d,\"queryCounts\":[",
        !!result,runtime.queuedSpawn.position.startX,runtime.queuedSpawn.position.startY,
        rng_calls,rng_state,front_calls,canopy_calls,metatile_calls);
    for(int i=0;i<update_count;i++) printf("%s%d",i?",":"",query_counts[i]);
    printf("],\"addonCounts\":[");
    for(int i=0;i<update_count;i++) printf("%s%d",i?",":"",addon_per_update[i]);
    printf("],\"blobCounts\":[");
    for(int i=0;i<update_count;i++) printf("%s%d",i?",":"",blob_per_update[i]);
    printf("],\"landingCounts\":[");
    for(int i=0;i<update_count;i++) printf("%s%d",i?",":"",landing_per_update[i]);
    printf("],\"trace\":[");
    for(int i=0;i<trace_count;i++) printf("%s%d",i?",":"",trace[i]);
    puts("]}"); return 0;
}
'''


def constants(source):
    header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    maps = (ROOT / "include/constants/maps.h").read_text()
    runtime = (ROOT / "include/overworld_wild_runtime_state_internal.h").read_text()
    # Take complete continued macros so the C compiler sees production masks.
    joined = (source + "\n" + header + "\n" + maps + "\n" + runtime).replace("\\\n", " ")
    names = ["OW_WILD_SPAWN_MIN_DISTANCE", "OW_WILD_SPAWN_MAX_DISTANCE",
             "OW_WILD_SPAWN_MIN_MON_DISTANCE", "OW_WILD_TILE_ENCOUNTER_GRASS",
             "OW_WILD_TILE_LONG_GRASS", "OW_WILD_TILE_HEADBUTT", "OW_WILD_SURFACE_TYPE_CANOPY",
             "OW_WILD_SURFACE_TYPE_FLOWERBED", "OW_WILD_SURFACE_ID_NATIVE_CANOPY",
             "OW_WILD_SURFACE_ID_NATIVE_GROUND", "OW_WILD_MAP_BLOCK_SHIFT",
             "OW_WILD_MAP_MATRIX_HEADERS_OFFSET", "MAP_EVERYWHERE",
             "OW_WILD_PROFILE_DESTINATION_CHECKS_PER_UPDATE"]
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


def require_candidate_query_budget(update_traces, maximum=4):
    """Reject any game update that exceeds the bounded tile-query batch."""
    for update, trace in enumerate(update_traces):
        candidate_queries = sum(1000 <= item < 2000 for item in trace)
        if candidate_queries > maximum:
            raise AssertionError(
                f"spawn destination update {update} checked {candidate_queries} "
                f"candidates; maximum is {maximum}"
            )


def require_selection_parity(actual, expected):
    value = deepcopy(actual)
    for key in ("queryCounts", "frontCalls", "canopyCalls", "metatileCalls",
                "addonCounts", "blobCounts", "landingCounts"):
        value.pop(key)
    if value != expected:
        raise AssertionError("spawn candidate order, selection, failure output or RNG differs")


class SpawnDestinationScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="spawn-destination-scan-")
        cls.addClassCleanup(cls.directory.cleanup)
        source = SOURCE.read_text()
        matcher = "OverworldWildSpawns_DoesAllowedTileMatch"
        match_body = function(source, matcher, "BOOL").replace(matcher + "(", matcher + "_Body(", 1)
        # The production matcher body stays unchanged. Candidate visits are
        # counted at Classify below, including its new reject-only prefix.
        wrapper = r'''
static BOOL OverworldWildSpawns_DoesAllowedTileMatch(FieldSystem *f,u16 mask,u8 behavior,int x,int y) {
    return OverworldWildSpawns_DoesAllowedTileMatch_Body(f,mask,behavior,x,y);
}

/* Only the addon-native terrain/occupancy boundary is a fixture. The actual
 * scan and Classify wrapper below retain their complete production bodies. */
static OverworldMotionDecision FixtureLanding(const OverworldPickupRouteWildLandingCall *call) {
    OverworldWildSurfaceHit hit;
    BOOL surface;
    BOOL player;
    u8 behavior=0;
    FieldSystem *field=call->field;
    int x=call->x,y=call->y;u16 mask=call->allowedTile;
    landing_calls++;
    if(call->state!=expected_state || call->slot!=expected_slot || !field || mask!=expected_mask
        || call->ops!=&sOverworldWildRouteOps
        || call->collisionIgnoredObject!=sOverworldWildCollisionIgnoredObject
        || call->finalTargetX!=-1 || call->finalTargetY!=-1) abort();
    if(call->behaviorData==NULL) return OVERWORLD_MOTION_DECISION_PROFILE;
    if(call->behaviorData!=&fixture_blob) abort();
    surface=OverworldWildSpawns_QuerySurface(field,x,y,&hit);
    if(!surface) behavior=GetMetatileBehaviorAt(field,x,y);
    if(!OverworldWildSpawns_DoesAllowedTileMatch(field,mask,behavior,x,y)) return OVERWORLD_MOTION_DECISION_TERRAIN;
    player=OverworldWildSpawns_IsPlayerTile(field,x,y);
    if(player && (mask&OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER))
        return OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(field,NULL,x,y)?OVERWORLD_MOTION_DECISION_OCCUPIED:OVERWORLD_MOTION_DECISION_ACCEPTED;
    return OverworldWildSpawns_IsTileOccupiedByObject(field,x,y)?OVERWORLD_MOTION_DECISION_OCCUPIED:OVERWORLD_MOTION_DECISION_ACCEPTED;
}
'''
        classifier = "OverworldWildSpawns_ClassifyBehaviorHopLandingTile"
        classify_body = function(source, classifier, "OverworldMotionDecision").replace(
            classifier + "(", classifier + "_Body(", 1)
        classify_wrapper = r'''
static OverworldMotionDecision OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
    OverworldWildSpawnState *state,int slot,FieldSystem *field,u16 mask,
    int x,int y,int finalTargetX,int finalTargetY) {
    if(!direct_mode) { visit_x=x;visit_y=y;record(1,x,y); }
    return OverworldWildSpawns_ClassifyBehaviorHopLandingTile_Body(
        state,slot,field,mask,x,y,finalTargetX,finalTargetY);
}
'''
        canopy = "OverworldWildSpawns_GetCanopyTerrainBit"
        canopy_body = function(source, canopy, "u16").replace(canopy + "(", canopy + "_Body(", 1)
        canopy_wrapper = r'''
static u16 OverworldWildSpawns_GetCanopyTerrainBit(FieldSystem *field,int x,int y) {
    canopy_calls++;
    return OverworldWildSpawns_GetCanopyTerrainBit_Body(field,x,y);
}
'''
        bodies = "\n".join((function(source, "OverworldWildSpawns_QuerySurface", "BOOL"),
            function(source, "OverworldWildSpawns_IsPlayableMapMatrixTile", "BOOL"),
            function(source, "OverworldWildSpawns_GetTerrainBit", "u16"),
            function(source, "OverworldWildSpawns_GetConditionTerrainBit", "u16"),
            function(source, "OverworldWildSpawns_GetElevatedTerrainBit", "u16"),
            canopy_body, canopy_wrapper,
            match_body, wrapper,
            classify_body, classify_wrapper,
            function(source, "OverworldWildSpawns_TryPickSpawnDestinationMask", "BOOL")))
        unit = Path(cls.directory.name) / "scan.c"
        cls.binary = Path(cls.directory.name) / "scan"
        motion=(ROOT/"include/overworld_motion_model.h").read_text()
        start=motion.index("typedef enum OverworldMotionDecision {")
        end=motion.index("} OverworldMotionDecision;",start)+len("} OverworldMotionDecision;")
        unit.write_text(constants(source) + "\n" + motion[start:end] + "\n" + PRELUDE + bodies + DRIVER)
        result = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                                 "-Wall", "-Wextra", "-Wno-unused-function", str(unit), "-o", str(cls.binary)],
                                text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def scan(self, style, mask):
        return json.loads(subprocess.check_output([str(self.binary), str(style), str(mask)], text=True))

    def probe(self, number):
        return json.loads(subprocess.check_output([str(self.binary), f"p{number}"], text=True))

    def test_surface_miss_or_wrong_type_rejects_before_addon_acquisition(self):
        for style in (0, 3):
            with self.subTest(style=style):
                actual = self.scan(style, 448)
                self.assertEqual(actual["queryCounts"], [0] + [4] * 60)
                self.assertEqual(actual["addonCounts"], [0] * 61)
                self.assertEqual(actual["landingCounts"], [0] * 61)
                self.assertEqual(actual["rngCalls"], 0)
                self.assertEqual(actual["position"], [777, 888])
        # A matching authored surface still needs the complete native path.
        # FlowerBed may carry the native-ground surface ID: type owns admission.
        for style, mask in ((4, 448), (5, 512)):
            with self.subTest(style=style):
                actual = self.scan(style, mask)
                self.assertEqual(actual["addonCounts"], actual["queryCounts"])
                self.assertEqual(actual["landingCounts"], actual["queryCounts"])
                self.assertEqual(actual["rngCalls"], 240)

    def test_reject_prefix_keeps_unknown_and_full_native_paths(self):
        # These are the production enum values read by the compiled C unit.
        accepted, blocked, terrain, profile = 0, 2, 4, 8
        cases = (
            (0, terrain, 0, 0),  # Complete catalog has no surface.
            (1, terrain, 0, 0),  # Complete catalog has an authored wrong type.
            (2, accepted, 1, 1), # Matching roof.
            (3, profile, 0, 0),  # Missing package is unknown, never terrain.
            (4, profile, 0, 0),  # Field is not ready.
            (5, profile, 0, 0),  # Borrowed Field is not the current Field.
            (6, blocked, 0, 0),  # Actual matrix header is MAP_EVERYWHERE.
            (7, terrain, 1, 1),  # Bound actor keeps full native admission.
            (8, terrain, 1, 1),  # Raw slot form keeps full native admission.
            (9, accepted, 1, 1), # Surface plus LAND keeps full native admission.
            (10, terrain, 1, 1), # Default/zero mask keeps full native admission.
            (11, profile, 1, 1), # Missing mixed-mask package stays unknown.
            (12, accepted, 1, 1),# Native-ground FlowerBed is still a real hit.
            (13, blocked, 0, 0), # Negative coordinate retains old guard.
            (14, profile, 0, 0), # NULL Field retains old guard.
            (15, profile, 1, 0), # Matching surface still requires the addon.
        )
        for number, decision, addon_calls, landing_calls in cases:
            with self.subTest(probe=number):
                actual = self.probe(number)
                self.assertEqual(actual["decision"], decision)
                self.assertEqual(actual["addonCalls"], addon_calls)
                self.assertEqual(actual["landingCalls"], landing_calls)
                self.assertEqual(actual["rngCalls"], 0)

    def test_actual_surface_type_bits_preserve_native_height_owner(self):
        rows = [list(map(int, row.split())) for row in subprocess.check_output(
            [str(self.binary), "terrain"], text=True).splitlines()]
        expected = []
        for surface in range(-1, 5):
            for native_height in (False, True):
                bit = 0 if surface < 0 else 4 if surface == 4 else 64 << surface
                # Runtime's native-ground owner is FFFF for types0..3 and
                # FFFE for Canopy4. Type membership never depends on height.
                elevated = 0 if native_height and 0 <= surface < 4 else bit
                expected.append([bit, elevated, elevated, 4 if surface == 4 else 0])
        self.assertEqual(rows, expected)

    def test_budget_checker_rejects_five_and_old_nine_candidates(self):
        for count in (5, 9):
            with self.subTest(count=count), self.assertRaisesRegex(
                    AssertionError, f"checked {count} candidates; maximum is 4"):
                require_candidate_query_budget([list(range(1000, 1000 + count))])

    def test_profile_destination_masks_check_at_most_four_candidates_per_update(self):
        for mask in (0, 8, 448, 512, 15):
            with self.subTest(mask=mask):
                actual = self.scan(0, mask)
                self.assertEqual(actual["queryCounts"][0], 0,
                                 "profile work must not share the helper's final update")
                require_candidate_query_budget(
                    [[1000] * count for count in actual["queryCounts"]])
                self.assertEqual(actual["queryCounts"], [0] + [4] * 60,
                                 "all 240 visits must finish in 60 four-query batches")

    def test_candidate_order_rng_occupancy_and_failure_output(self):
        for style in (0, 1, 2):
            for mask in sorted({0, 1, 2, 4, 8, 16, 32, 48, 49, 1023, *range(64, 1024, 64)}):
                with self.subTest(style=style, mask=mask):
                    actual = self.scan(style, mask)
                    require_selection_parity(actual, oracle(style, mask))

    def test_selection_oracle_rejects_missing_tile_order_selection_and_rng(self):
        actual = self.scan(0, 8)
        expected = oracle(0, 8)
        for fault in ("missing-tile", "changed-order", "selection", "rng-calls", "rng-state"):
            with self.subTest(fault=fault):
                copied = deepcopy(actual)
                if fault == "missing-tile":
                    copied["trace"].remove(next(v for v in copied["trace"] if 1000 <= v < 2000))
                elif fault == "changed-order":
                    indexes = [i for i, v in enumerate(copied["trace"]) if 1000 <= v < 2000][:2]
                    a, b = indexes
                    copied["trace"][a], copied["trace"][b] = copied["trace"][b], copied["trace"][a]
                elif fault == "selection":
                    copied["position"][0] += 1
                elif fault == "rng-calls":
                    copied["rngCalls"] += 1
                else:
                    copied["rngState"] ^= 1
                with self.assertRaisesRegex(AssertionError, "RNG differs"):
                    require_selection_parity(copied, expected)

    def test_each_no_surface_candidate_reads_metatile_once(self):
        counts = list(map(int, subprocess.check_output([str(self.binary), "counts"], text=True).splitlines()))
        self.assertEqual(len(counts), 1024)
        # A known miss for a pure Surface mask needs no native behavior read.
        # All default/native/mixed masks retain one read per candidate.
        surface_mask = 4 | 64 | 128 | 256 | 512
        for mask, actual in enumerate(counts):
            expected = 0 if mask and not mask & ~surface_mask else (
                240 + bool(mask & 16) + bool(mask & 32))
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


POOL_PRELUDE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
typedef struct { void *map_matrix; } FieldSystem;
typedef struct { int startX,startY; } OverworldWildSpawnPosition;
typedef struct { OverworldWildSpawnPosition position; } PoolPrepared;
typedef struct { PoolPrepared queuedSpawn; u8 refillPositionChecksRemaining; } PoolRuntime;
typedef struct { void *movementRuntimeState; } OverworldWildSpawnState;
#define OW_WILD_RUNTIME(s) ((PoolRuntime *)((s)->movementRuntimeState))
#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
typedef struct { u8 spawnDestination; u16 spawnDestinationOverrideMask,spawnDestinationMask; } OverworldWildBehaviorProfile;
typedef struct { u16 surfaceId; u8 surfaceType; } OverworldWildSurfaceHit;
static u8 behavior;
static int blocked,surface=-1,native_height,metatile_reads,surface_reads,collision_reads,scan_calls,scan_mask,rng_calls;
static u32 rng_state=0x12345678;
static u32 gf_rand(void) { rng_calls++; rng_state=rng_state*1664525u+1013904223u;return rng_state; }
static u8 GetMetatileBehaviorAt(FieldSystem *f,int x,int y) { (void)f;(void)x;(void)y;metatile_reads++;return behavior; }
static BOOL IsMetatileBlockedAt(FieldSystem *f,int x,int y) { (void)f;(void)x;(void)y;collision_reads++;return blocked; }
static BOOL OverworldWildSpawns_IsSurfBehavior(u8 b) { return b==0x10; }
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *hit) {
    (void)f;(void)x;(void)y;surface_reads++;if(surface<0)return FALSE;
    hit->surfaceType=surface;hit->surfaceId=native_height?OW_WILD_SURFACE_ID_NATIVE_GROUND:42;return TRUE;
}
static BOOL OverworldWildSpawns_IsPlayerTile(FieldSystem *f,int x,int y) { (void)f;return x==20&&y==20; }
static BOOL OverworldWildSpawns_IsPlayerFrontTile(FieldSystem *f,int x,int y) { (void)f;return x==21&&y==20; }
/* Selection remains owned by the existing extracted scan/oracle tests. This
 * fixture measures only which branch receives the exact prepared position. */
static BOOL OverworldWildSpawns_TryPickSpawnDestinationMask(OverworldWildSpawnState *s,FieldSystem *f,u16 mask,OverworldWildSpawnPosition *p) {
    (void)s;(void)f;(void)p;scan_calls++;scan_mask=mask;return TRUE;
}
static BOOL OverworldWildSpawns_TryPickFishingSpawnPosition(FieldSystem *f,OverworldWildSpawnPosition *p) { (void)f;(void)p;abort(); }
static BOOL OverworldWildSpawns_TryGetPlayerRelativeSpawnDestination(OverworldWildSpawnDestination d,int *scale,int *distance) { (void)d;(void)scale;(void)distance;abort(); }
static BOOL OverworldWildSpawns_TryPickPlayerRelativeSpawnPosition(OverworldWildSpawnState *s,FieldSystem *f,const OverworldWildBehaviorProfile *p,OverworldWildSpawnDestination d,OverworldWildSpawnPosition *position) { (void)s;(void)f;(void)p;(void)d;(void)position;abort(); }
'''

POOL_DRIVER = r'''
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    int n=atoi(argv[1]);u8 matrix[8]={1,1,0,0,0,0,33,0};FieldSystem f={matrix};PoolRuntime runtime={0};
    OverworldWildSpawnState state={&runtime};OverworldWildSpawnPosition p={12,12};
    OverworldWildBehaviorProfile profile={OW_WILD_SPAWN_DESTINATION_POOL,0,OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL};
    OverworldWildSpawnTerrain terrain=OW_WILD_SPAWN_TERRAIN_LAND;FieldSystem *field=&f;
    switch(n) {
    case 0:behavior=0x10;break;
    case 1:break;
    case 2:terrain=OW_WILD_SPAWN_TERRAIN_SURF;behavior=0x10;break;
    case 3:terrain=OW_WILD_SPAWN_TERRAIN_FISHING;behavior=0x10;break;
    case 4:terrain=OW_WILD_SPAWN_TERRAIN_SURF;break;
    case 5:terrain=OW_WILD_SPAWN_TERRAIN_FISHING;break;
    case 6:terrain=OW_WILD_SPAWN_TERRAIN_HEADBUTT;surface=4;behavior=0x10;break;
    case 7:behavior=0xFF;break;
    case 8:matrix[6]=0;break;
    case 9:p.startX=-1;break;
    case 10:blocked=1;break;
    case 11:surface=4;behavior=0x10;break;
    case 12:surface=0;native_height=1;break;
    case 13:profile.spawnDestinationOverrideMask=1;profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;behavior=0x10;break;
    case 14:terrain=OW_WILD_SPAWN_TERRAIN_HEADBUTT;profile.spawnDestinationOverrideMask=1;profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;break;
    case 15:profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;break;
    case 16:field=NULL;break;
    case 17:behavior=OW_WILD_TILE_HEADBUTT;break;
    case 18:behavior=0xFF;break;
    default:return 3;
    }
    int result=n==18
        ? OverworldWildSpawns_DoesAllowedTileMatch(field,OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND,behavior,p.startX,p.startY)
        : OverworldWildSpawns_TryApplySpawnDestination(&state,field,terrain,&profile,&p);
    printf("{\"result\":%d,\"position\":[%d,%d],\"scanCalls\":%d,\"scanMask\":%d,\"rngCalls\":%d,\"rngState\":%u,\"metatileReads\":%d,\"surfaceReads\":%d,\"collisionReads\":%d}\n",!!result,p.startX,p.startY,scan_calls,scan_mask,rng_calls,rng_state,metatile_reads,surface_reads,collision_reads);
    return 0;
}
'''


class UntouchedPoolAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="pool-admission-")
        cls.addClassCleanup(cls.directory.cleanup)
        source = SOURCE.read_text()
        header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        enums = "\n".join(re.search(r"typedef enum " + name + r" \{.*?\} " + name + r";", header, re.S).group(0)
                          for name in ("OverworldWildSpawnTerrain", "OverworldWildSpawnDestination"))
        bodies = "\n".join(function(source, name, result) for name, result in (
            ("OverworldWildSpawns_IsPlayableMapMatrixTile", "BOOL"),
            ("OverworldWildSpawns_TryGetLoadedMetatileBehavior", "BOOL"),
            ("OverworldWildSpawns_IsLandMapTile", "BOOL"),
            ("OverworldWildSpawns_DoesAllowedTileMatch", "BOOL"),
            ("OverworldWildSpawns_GetSpawnDestinationMask", "u16"),
            ("OverworldWildSpawns_TryApplySpawnDestination", "BOOL")))
        unit = Path(cls.directory.name) / "pool.c"
        cls.binary = Path(cls.directory.name) / "pool"
        unit.write_text(constants(source) + "\n" + enums + "\n" + POOL_PRELUDE + bodies + POOL_DRIVER)
        compiled = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
            "-Wall", "-Wextra", "-Werror=implicit-function-declaration", "-Wno-unused-function",
            str(unit), "-o", str(cls.binary)], text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)

    def probe(self, number):
        return json.loads(subprocess.check_output([str(self.binary), str(number)], text=True))

    def test_land_pool_rejects_native_water_and_accepts_legal_land(self):
        self.assertEqual(self.probe(0)["result"], 0)
        self.assertEqual(self.probe(1)["result"], 1)
        self.assertEqual(self.probe(10)["result"], 0)  # collision still blocks Land.
        self.assertEqual(self.probe(15)["result"], 1) # no explicit override: encounter owns Pool.

    def test_loaded_pool_byte_is_reused_and_land_trees_are_rejected(self):
        for number in (0, 1, 2, 3, 4, 5, 10, 11, 12, 15, 17):
            with self.subTest(number=number):
                self.assertEqual(self.probe(number)["metatileReads"], 1)
        for number in (1, 10, 15):
            self.assertEqual(self.probe(number)["collisionReads"], 1)
        for number in (0, 2, 3, 4, 5, 11, 12, 17):
            self.assertEqual(self.probe(number)["collisionReads"], 0)
        tree = self.probe(17)
        self.assertEqual((tree["result"], tree["surfaceReads"]), (0, 1))

    def test_unknown_supplied_land_byte_still_fails_closed(self):
        unknown = self.probe(18)
        self.assertEqual((unknown["result"], unknown["metatileReads"],
                          unknown["collisionReads"], unknown["surfaceReads"]), (0, 0, 0, 1))

    def test_surf_fishing_keep_water_and_headbutt_keeps_catalog_canopy(self):
        for number in (2, 3):
            self.assertEqual(self.probe(number)["result"], 1)
        for number in (4, 5):
            self.assertEqual(self.probe(number)["result"], 0)
        for number in (6, 14):
            actual = self.probe(number)
            self.assertEqual((actual["result"], actual["scanCalls"], actual["scanMask"]), (1, 1, 4))
            self.assertEqual(actual["metatileReads"], 0)
        # Catalog type owns admission, including a Canopy above native water
        # and a Roof whose height happens to have a native-ground owner.
        for number in (11, 12):
            self.assertEqual(self.probe(number)["result"], 0)

    def test_unknown_or_blank_tile_is_rejected_before_surface_reads(self):
        for number in (7, 8, 9, 16):
            actual = self.probe(number)
            self.assertEqual(actual["result"], 0)
            self.assertEqual(actual["surfaceReads"], 0)
        self.assertEqual(self.probe(7)["metatileReads"], 1)
        for number in (8, 9, 16):
            self.assertEqual(self.probe(number)["metatileReads"], 0)

    def test_prepared_coordinates_and_rng_are_unchanged(self):
        for number in range(19):
            actual = self.probe(number)
            self.assertEqual(actual["position"], [-1, 12] if number == 9 else [12, 12])
            self.assertEqual((actual["rngCalls"], actual["rngState"]), (0, 0x12345678))
            if number not in (6, 13, 14):
                self.assertEqual(actual["scanCalls"], 0)
        explicit = self.probe(13)
        self.assertEqual((explicit["result"], explicit["scanCalls"], explicit["scanMask"]), (1, 1, 2))

    def test_existing_follower_failed_destination_exception_is_unchanged(self):
        entry = (ROOT / "lib/overworld/overworld_entry_route.c").read_text()
        finalize = function(entry, "NativeFinalize", "BOOL")
        self.assertRegex(finalize, r"!c->ops->destination\([\s\S]*?&& !isFollower\)\s*\{\s*return FALSE;")


if __name__ == "__main__":
    unittest.main()

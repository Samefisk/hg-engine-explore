"""Actual-C spawn destination shortcut checks for Behind Buildings.

The production mask reducer, shortcut dispatcher and prepared-tile matcher
run unchanged. Named scan/fishing/player-relative seams record which owner
receives a request. These are host dispatch checks, not game or pacing proof.
"""

from pathlib import Path
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.overworld.test_spawn_destination_scan import constants, function


SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
HEADER = ROOT / "include/overworld_wild_behavior_data.h"


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
typedef struct { void *map_matrix; } FieldSystem;
typedef struct { int startX,startY; } OverworldWildSpawnPosition;
typedef struct { OverworldWildSpawnPosition position; } Prepared;
typedef struct { Prepared queuedSpawn; u8 refillPositionChecksRemaining; } Runtime;
typedef struct { void *movementRuntimeState; } OverworldWildSpawnState;
#define OW_WILD_RUNTIME(s) ((Runtime *)((s)->movementRuntimeState))
#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
typedef struct { u8 spawnDestination; u16 spawnDestinationOverrideMask,spawnDestinationMask; } OverworldWildBehaviorProfile;
typedef struct { u16 surfaceId; u8 surfaceType; } OverworldWildSurfaceHit;
static u8 tileBehavior;
static int blocked,matcherCalls,matcherMask,metatileCalls,scanCalls,scanMask;
static int fishingCalls,relativeLookupCalls,relativePickCalls,rngCalls;
static int scanResult=1,scanYield,fishingResult=1,relativeResult=1;
static u32 nextRandom=3;
static FieldSystem *expectedField;
static OverworldWildSpawnState *expectedState;
static OverworldWildSpawnPosition *expectedPosition;
static const OverworldWildBehaviorProfile *expectedProfile;
#define CHECK(value) do { if (!(value)) { \
 fprintf(stderr,"line %d: %s\n",__LINE__,#value);return 1; \
} } while(0)
static u32 gf_rand(void) { rngCalls++;return nextRandom; }
static u8 GetMetatileBehaviorAt(FieldSystem *f,int x,int y) {
 if(f!=expectedField || x!=12 || y!=12) abort();
 metatileCalls++;return tileBehavior;
}
static BOOL IsMetatileBlockedAt(FieldSystem *f,int x,int y) {
 (void)f;(void)x;(void)y;return blocked;
}
static BOOL OverworldWildSpawns_IsSurfBehavior(u8 behavior) { return behavior==0x10; }
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *hit) {
 (void)f;(void)x;(void)y;(void)hit;return FALSE;
}
static BOOL OverworldWildSpawns_IsPlayerTile(FieldSystem *f,int x,int y) {
 (void)f;(void)x;(void)y;return FALSE;
}
static BOOL OverworldWildSpawns_IsPlayerFrontTile(FieldSystem *f,int x,int y) {
 (void)f;(void)x;(void)y;return FALSE;
}
static BOOL OverworldWildSpawns_TryPickSpawnDestinationMask(OverworldWildSpawnState *s,
 FieldSystem *f,u16 mask,OverworldWildSpawnPosition *position) {
 if(s!=expectedState || f!=expectedField || position!=expectedPosition) abort();
 if(scanCalls && mask!=scanMask) abort();
 scanMask=mask;scanCalls++;
 if(scanYield && scanCalls==1) {
  if(!s || !s->movementRuntimeState
   || position!=&OW_WILD_RUNTIME(s)->queuedSpawn.position) abort();
  OW_WILD_RUNTIME(s)->refillPositionChecksRemaining=OW_WILD_PROFILE_DESTINATION_SCAN_PENDING;
  return FALSE;
 }
 if(s && s->movementRuntimeState
  && position==&OW_WILD_RUNTIME(s)->queuedSpawn.position)
  OW_WILD_RUNTIME(s)->refillPositionChecksRemaining=0;
 if(scanResult) {position->startX=10;position->startY=11;}
 return scanResult;
}
static BOOL OverworldWildSpawns_TryPickFishingSpawnPosition(FieldSystem *f,
 OverworldWildSpawnPosition *position) {
 if(f!=expectedField || position!=expectedPosition) abort();
 fishingCalls++;return fishingResult;
}
static BOOL OverworldWildSpawns_TryGetPlayerRelativeSpawnDestination(
 OverworldWildSpawnDestination destination,int *scale,int *distance) {
 relativeLookupCalls++;*distance=1;
 switch(destination) {
 case OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER:*scale=1;return TRUE;
 case OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER:*scale=-1;return TRUE;
 default:return FALSE;
 }
}
static BOOL OverworldWildSpawns_TryPickPlayerRelativeSpawnPosition(
 OverworldWildSpawnState *s,FieldSystem *f,const OverworldWildBehaviorProfile *profile,
 OverworldWildSpawnDestination destination,OverworldWildSpawnPosition *position) {
 if(s!=expectedState || f!=expectedField || profile!=expectedProfile
  || destination!=profile->spawnDestination || position!=expectedPosition) abort();
 relativePickCalls++;return relativeResult;
}
'''


MATCHER_WRAPPER = r'''
static BOOL OverworldWildSpawns_DoesAllowedTileMatch(FieldSystem *field,u16 mask,
 u8 behavior,int x,int y) {
 matcherCalls++;matcherMask=mask;
 return OverworldWildSpawns_DoesAllowedTileMatch_Body(field,mask,behavior,x,y);
}
'''


DRIVER = r'''
int main(int argc,char **argv) {
 if(argc!=2)return 2;
 int test=atoi(argv[1]);
 u8 matrix[8]={1,1,0,0,0,0,33,0};FieldSystem field={matrix};
 Runtime runtime={0};OverworldWildSpawnState state={&runtime};
 OverworldWildSpawnPosition position={12,12};
 OverworldWildBehaviorProfile profile={OW_WILD_SPAWN_DESTINATION_POOL,
  OW_WILD_SPAWN_DESTINATION_MASK_ALL,OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS};
 OverworldWildSpawnTerrain terrain=OW_WILD_SPAWN_TERRAIN_LAND;
 expectedState=&state;expectedField=&field;expectedPosition=&position;expectedProfile=&profile;
 switch(test) {
 case 0:break;
 case 1:profile.spawnDestinationMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;break;
 case 2:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_SHORE;
  profile.spawnDestinationMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
  terrain=OW_WILD_SPAWN_TERRAIN_FISHING;break;
 case 3:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER;
  profile.spawnDestinationMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT;break;
 case 4:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER;
  profile.spawnDestinationMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;break;
 case 5:terrain=OW_WILD_SPAWN_TERRAIN_HEADBUTT;break;
 case 6:scanResult=0;break;
 case 7:runtime.queuedSpawn.position=position;expectedPosition=&runtime.queuedSpawn.position;
  scanYield=1;profile.spawnDestinationMask|=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;break;
 case 8:profile.spawnDestinationOverrideMask=0;
  profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;break;
 case 9:profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
  terrain=OW_WILD_SPAWN_TERRAIN_SURF;tileBehavior=0x10;break;
 case 10:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_SHORE;
  profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;break;
 case 11:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER;
  profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT;break;
 case 12:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER;
  profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;break;
 case 13:terrain=OW_WILD_SPAWN_TERRAIN_HEADBUTT;
  profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;break;
 case 14:profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
  terrain=OW_WILD_SPAWN_TERRAIN_SURF;tileBehavior=0x10;nextRandom=0;break;
 case 15:profile.spawnDestination=OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER;
  profile.spawnDestinationMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT;
  runtime.queuedSpawn.position=position;expectedPosition=&runtime.queuedSpawn.position;
  runtime.refillPositionChecksRemaining=OW_WILD_PROFILE_DESTINATION_SCAN_PENDING;break;
 default:return 3;
 }
 int result=OverworldWildSpawns_TryApplySpawnDestination(&state,&field,terrain,&profile,expectedPosition);
 if(test==5) {
  CHECK(!result && !scanCalls && !matcherCalls && !fishingCalls && !relativeLookupCalls && !rngCalls);
 } else if(test<8) {
  CHECK(!fishingCalls && !relativeLookupCalls && !relativePickCalls);
  CHECK(scanCalls==1 && scanMask==OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS);
  CHECK(OverworldWildSpawns_GetSpawnDestinationMask(&profile)&OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS);
  CHECK(!matcherCalls && !rngCalls && !metatileCalls);
  if(test==6) CHECK(!result && expectedPosition->startX==12 && expectedPosition->startY==12);
  else if(test==7) {
   CHECK(!result && runtime.refillPositionChecksRemaining==OW_WILD_PROFILE_DESTINATION_SCAN_PENDING);
   CHECK(expectedPosition->startX==12 && expectedPosition->startY==12);
   int oldMatcherCalls=matcherCalls,oldRngCalls=rngCalls;
   CHECK(OverworldWildSpawns_TryApplySpawnDestination(&state,&field,terrain,&profile,expectedPosition));
   CHECK(scanCalls==2 && scanMask==OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS);
   CHECK(matcherCalls==oldMatcherCalls && rngCalls==oldRngCalls);
   CHECK(!runtime.refillPositionChecksRemaining && expectedPosition->startX==10 && expectedPosition->startY==11);
  } else CHECK(result && expectedPosition->startX==10 && expectedPosition->startY==11);
 } else {
  CHECK(result);
  switch(test) {
  case 8:CHECK(matcherCalls==1 && matcherMask==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND);
   CHECK(!scanCalls && !fishingCalls && !relativeLookupCalls && !rngCalls);break;
  case 9:CHECK(matcherCalls==1 && matcherMask==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER);
   CHECK(!scanCalls && !fishingCalls && !relativeLookupCalls && rngCalls==1);break;
  case 10:CHECK(fishingCalls==1 && !scanCalls && !matcherCalls && !relativeLookupCalls);break;
  case 11:case 12:CHECK(relativeLookupCalls==1 && relativePickCalls==1);
   CHECK(!fishingCalls && !scanCalls && !matcherCalls);break;
  case 13:CHECK(scanCalls==1 && scanMask==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY);
   CHECK(!matcherCalls && !fishingCalls && !relativeLookupCalls && !rngCalls);break;
  case 14:CHECK(scanCalls==1 && scanMask==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER);
   CHECK(!matcherCalls && !fishingCalls && !relativeLookupCalls && rngCalls==1);break;
  case 15:CHECK(scanCalls==1 && scanMask==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT);
   CHECK(!matcherCalls && !fishingCalls && !relativeLookupCalls && !rngCalls);break;
  }
 }
 puts("spawn destination dispatch passed");return 0;
}
'''


def program(source):
    header = HEADER.read_text()
    joined = header.replace("\\\n", " ")
    destination_masks = "\n".join(re.findall(
        r"^#define OW_WILD_SPAWN_DESTINATION_MASK_\w+\s+[^\n]+", joined, re.M))
    enums = "\n".join(re.search(r"typedef enum " + name + r" \{.*?\} " + name + r";",
                                 header, re.S).group(0)
                      for name in ("OverworldWildSpawnTerrain", "OverworldWildSpawnDestination"))
    matcher = function(source, "OverworldWildSpawns_DoesAllowedTileMatch", "BOOL")
    matcher = matcher.replace("OverworldWildSpawns_DoesAllowedTileMatch(",
                              "OverworldWildSpawns_DoesAllowedTileMatch_Body(", 1)
    bodies = "\n".join(function(source, name, result) for name, result in (
        ("OverworldWildSpawns_IsPlayableMapMatrixTile", "BOOL"),
        ("OverworldWildSpawns_TryGetLoadedMetatileBehavior", "BOOL")))
    dispatch = "\n".join(function(source, name, result) for name, result in (
        ("OverworldWildSpawns_GetSpawnDestinationMask", "u16"),
        ("OverworldWildSpawns_TryApplySpawnDestination", "BOOL")))
    return "\n".join((constants(source), destination_masks, enums, PRELUDE,
                       bodies, matcher, MATCHER_WRAPPER, dispatch, DRIVER))


def compile_fixture(directory, source, name):
    unit = Path(directory) / (name + ".c")
    binary = Path(directory) / name
    unit.write_text(program(source))
    compiled = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")),
        "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror=implicit-function-declaration",
        "-Wno-unused-function", str(unit), "-o", str(binary)], text=True, capture_output=True)
    if compiled.returncode:
        raise RuntimeError(compiled.stderr)
    return binary


class BehindBuildingsShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="spawn-behind-shortcuts-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.source = SOURCE.read_text()
        cls.binary = compile_fixture(cls.directory.name, cls.source, "dispatch")

    def check_cases(self, cases):
        for case in cases:
            with self.subTest(case=case):
                result = subprocess.run([str(self.binary), str(case)], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_behind_and_mixed_masks_cannot_accept_shortcuts(self):
        self.check_cases(range(5))

    def test_headbutt_cannot_bypass_behind_land_requirement(self):
        self.check_cases([5])

    def test_failed_and_resumed_scan_keep_behind_constraint(self):
        self.check_cases([6, 7])

    def test_ordinary_pool_water_fishing_player_and_headbutt_paths_remain(self):
        self.check_cases(range(8, 16))

    def test_controls_detect_mixed_mask_pool_and_headbutt_leaks(self):
        behind_branch = ("    if (candidateMask & OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS) {\n"
                         "        candidateMask = OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS;\n"
                         "        goto destinationScan;\n"
                         "    }\n")
        headbutt_guard = ("if (candidateMask & OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS)\n"
                          "            return FALSE;")
        for name, guard, replacement, case in (
            ("shortcut-leak", behind_branch, "", 1),
            ("headbutt-leak", headbutt_guard, "", 5),
        ):
            with self.subTest(fault=name):
                self.assertEqual(self.source.count(guard), 1)
                binary = compile_fixture(self.directory.name, self.source.replace(guard, replacement), name)
                result = subprocess.run([str(binary), str(case)], text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0, "the missing guard did not fail the behavioral check")


if __name__ == "__main__":
    unittest.main()

"""Behind Buildings uses production bare landing and the existing Land leaf.

Native callbacks are named host seams. This proves placement decisions, not
ARM layout, map loading, rendering, or current-ROM pacing.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.overworld import test_bound_interest_landing as landing_fixture
from tools.overworld.test_spawn_destination_scan import function


WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"

DRIVER = landing_fixture.DRIVER.split("int main(void)", 1)[0] + r'''
static OverworldMotionDecision Place(u16 mask,int x,int y,BOOL actor) {
 OverworldPickupRouteWildLandingCall call={.state=actor?&state:NULL,
  .slot=actor?0:-1,.field=&field,.behaviorData=&behaviorData,.ops=&ops,
  .allowedTile=mask,.x=x,.y=y,.finalTargetX=-1,.finalTargetY=-1};
 return OverworldPickupLandingWild_Classify(&call);
}
int main(void) {
 const u16 behind=OW_WILD_SPAWN_DESTINATION_MASK_BEHIND_BUILDINGS;
 Reset();CertifyCatalog();
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 CHECK(landCalls==1);
 puts("ground immediately north of a roof accepts through Land");
 /* A mixed or inherited destination cannot bypass the active restriction. */
 CHECK(Place(behind|OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL,5,1,FALSE)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 CHECK(Place(behind|OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL,4,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 CHECK(Place(behind,5,3,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 CHECK(Place(behind,4,2,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 roofType=OW_WILD_SURFACE_TYPE_SIGNPOST;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 roofType=OW_WILD_SURFACE_TYPE_ROOFTOP;
 blockedGround=1;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 blockedGround=0;terrainByte=0x15;waterAllowed=1;
 CHECK(Place(behind|OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER,5,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 waterAllowed=0;terrainByte=OW_WILD_TILE_HEADBUTT;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 terrainByte=0xFF;
 CHECK(Place(behind,5,1,FALSE)!=OVERWORLD_MOTION_DECISION_ACCEPTED);
 terrainByte=0;paddingY=1;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_BLOCKED);
 paddingY=2;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 paddingY=-1;
 for(int i=0;i<OW_WILD_SURFACE_TYPE_COUNT;i++) {
  candidateType=i;
  CHECK(Place(behind|OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL,5,1,FALSE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 }
 candidateType=-1;bodyX=5;bodyY=1;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 bodyX=bodyY=-1;
 CHECK(Place(behind,5,1,TRUE)==OVERWORLD_MOTION_DECISION_TERRAIN);
 behaviorData.header.magic^=1;
 CHECK(Place(behind,5,1,FALSE)==OVERWORLD_MOTION_DECISION_PROFILE);
 puts("wrong row, water, blockers, missing data, surfaces, occupancy and actor use reject");
 Reset();CertifyCatalog();
 CHECK(Place(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND,4,1,FALSE)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 puts("ordinary Land placement stays valid away from buildings");
 return 0;
}
'''


def source_text(adapter=None):
    text = landing_fixture.source_text(landing=adapter, driver=DRIVER)
    # These native seams supply a roof south of the candidate, plus explicit
    # collision, loading, surface, and matrix-boundary facts.
    start = text.index("static BOOL OverworldWildRuntime_QuerySurface(")
    end = text.index("\n}", start) + 2
    text = text[:start] + r'''
static int roofType=OW_WILD_SURFACE_TYPE_ROOFTOP,candidateType=-1;
static int terrainByte,blockedGround,paddingY=-1;
static BOOL OverworldWildRuntime_QuerySurface(FieldSystem *field,const OverworldWildSurfaceCatalog *catalog,int x,int y,OverworldWildSurfaceHit *hit) {
 (void)field;(void)catalog;++surfaceCalls;
 int type=x==5&&y==2?roofType:x==5&&y==1?candidateType:-1;
 if(type<0)return FALSE;
 *hit=(OverworldWildSurfaceHit){.height=20,.surfaceId=42,.surfaceType=type};return TRUE;
}
''' + text[end:]
    text = text.replace("return x>=0&&x<20&&y>=0&&y<10;",
                        "return x>=0&&x<20&&y>=0&&y<10&&y!=paddingY;")
    text = text.replace("return x==missingTileX?0xFF:(u8)x;",
                        "return x==missingTileX?0xFF:(u8)terrainByte;")
    old = "static BOOL Land(FieldSystem *f,int x,int y) {(void)f;(void)x;(void)y;++landCalls;return landAllowed;}"
    if text.count(old) != 1:
        raise AssertionError("Land fixture seam changed")
    actual = function(WILD.read_text(), "OverworldWildSpawns_IsLandMapTile", "BOOL")
    actual = actual.replace("OverworldWildSpawns_IsLandMapTile(", "LandBody(", 1)
    leaf = r'''
#define OW_WILD_TILE_HEADBUTT 0x6A
static BOOL OverworldWildSpawns_TryGetLoadedMetatileBehavior(FieldSystem *f,int x,int y,u8 *b) {
 if(!Playable(f,x,y))return FALSE;*b=Behavior(f,x,y);return *b!=0xFF;
}
static BOOL OverworldWildSpawns_IsSurfBehavior(u8 b) {return b==0x15;}
static BOOL IsMetatileBlockedAt(FieldSystem *f,int x,int y) {(void)f;(void)x;(void)y;return blockedGround;}
'''
    return text.replace(old, leaf + actual + "\nstatic BOOL Land(FieldSystem *f,int x,int y) {++landCalls;return LandBody(f,x,y);}")


def run(adapter=None):
    compiler = shutil.which("cc")
    if compiler is None:
        raise unittest.SkipTest("host C compiler missing")
    with tempfile.TemporaryDirectory(prefix="behind-buildings-") as directory:
        source = Path(directory) / "placement.c"
        binary = Path(directory) / "placement"
        source.write_text(source_text(adapter))
        compiled = subprocess.run([
            compiler, "-std=c11", "-O2", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
            "-DOVERWORLD_PICKUP_ROUTE_HOST", "-DOVERWORLD_MOTION_HOST",
            "-I", str(ROOT / "include"), str(source),
            str(ROOT / "lib/overworld/overworld_pickup_route.c"),
            str(landing_fixture.NATIVE), "-o", str(binary),
        ], capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True)


class BehindBuildingsPlacementTests(unittest.TestCase):
    def test_production_land_placement(self):
        result = run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wrong_surface_and_mixed_mask_controls_fail(self):
        adapter = landing_fixture.LANDING.read_text()
        for old, new in (
            ("sourceSurface.surfaceType != OW_WILD_SURFACE_TYPE_ROOFTOP", "FALSE"),
            ("allowedTile = OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;",
             "allowedTile |= OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;"),
        ):
            with self.subTest(control=old):
                self.assertEqual(adapter.count(old), 1)
                result = run(adapter.replace(old, new))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Place(", result.stderr)


if __name__ == "__main__":
    from tools.overworld.test_behind_buildings_profile import BehindBuildingsProfileTests
    from tools.overworld.test_spawn_behind_shortcuts import BehindBuildingsShortcutTests

    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
        for case in (BehindBuildingsPlacementTests, BehindBuildingsProfileTests,
                     BehindBuildingsShortcutTests))
    raise SystemExit(not unittest.TextTestRunner().run(suite).wasSuccessful())

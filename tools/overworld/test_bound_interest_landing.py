"""Exact production-C landing permission, independent of contact damage.

The native object callbacks are named host seams. The landing adapter, target
identity checks, terrain reducer, and occupancy selection are current C bodies.
This fixture does not claim ARM layout or game proof.
"""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WILD = ROOT / "lib/overworld/overworld_pickup_route_wild.c"
LANDING = ROOT / "lib/overworld/overworld_pickup_landing_wild.c"
NATIVE = ROOT / "lib/overworld/overworld_pickup_route_native.c"
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
spec = importlib.util.spec_from_file_location(
    "wild_landing_fixture", ROOT / "scripts/verify_overworld_pickup_route_wild.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


DRIVER = r'''
/* Before the product edit this is the requested private policy marker. After
 * it, the real header is the only value used by the production adapter. */
#ifndef OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER
#define OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER 0x4000u
#endif
static void CertifyCatalog(void) {
 memset(&behaviorData,0,sizeof(behaviorData));behaviorData.header=sWildExpectedBlobHeader;
 /* A valid one-entry local bank, with named numeric rows and final wildcard.
  * The catalog sizes/header remain the exact current generated declarations. */
 for(unsigned i=0;i<OWBD_APPLICATION_BANK_DIRECTORY_COUNT;i++)
  behaviorData.applicationBankDirectory[i]=(OverworldApplicationBankDirectoryEntry){
   .species=i+1,.first=0,.count=1};
 behaviorData.applicationBankDirectory[OWBD_APPLICATION_BANK_DIRECTORY_COUNT-1].species=0xFFFF;
 behaviorData.applicationBankIndexes[0]=0;
 world.behaviorData=&behaviorData;
 world.catalog=(const OverworldWildSurfaceCatalog *)behaviorData.surfaceModels;
}
static void Interest(u8 kind) {
 CertifyCatalog();
 conditions.actors[0]=(OverworldBehaviorConditionPreparedActor){
  .subject=actors.slots[0].snapshot.handle,.states=conditionStates,
  .subjectSpecies=1,.count=1,.stateCapacity=3,.valid=1};
 conditionStates[0]=(OverworldBehaviorConditionEntryState){
  .targetKind=kind,.targetSlot=1,.targetGeneration=actors.slots[1].snapshot.handle.generation,
  .targetEncounterGeneration=actors.slots[1].snapshot.handle.encounterGeneration,
  .flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE};
 conditions.activeApplicationMasks[0]=1;conditions.targetValidMask=1;
 objects[1].xCurr=5;objects[1].yCurr=1;objectsOccupy=1;
}
static void MountPresentation(void) {
 mountedPresentation=(LocalMapObject){.flags=MAPOBJECTFLAG_ACTIVE,
  .xCurr=player.xCurr,.yCurr=player.yCurr};
 mountedPresentation.posVec[1]=objects[0].posVec[1];
 state.spawns[OW_WILD_FOLLOWER_SLOT]=(OverworldWildSpawn){1,12,707,&mountedPresentation};
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot=(OverworldActorStateSnapshot){
  .active=1,.role=OVERWORLD_ACTOR_ROLE_MOUNTED,.inputOwnership=1,
  .presentationAttached=1,.subjectIdentity=707,
  .handle={OW_WILD_FOLLOWER_SLOT,9,3,4,12,0}};
}
static OverworldMotionDecision Classify(u16 terrain,u8 kind) {
 LocalMapObject *target=kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER?&player:&objects[1];
 OverworldPickupRouteWildLandingCall call={.state=&state,.field=&field,
  .behaviorData=&behaviorData,.ops=&ops,.slot=0,
  .allowedTile=terrain|OVERWORLD_PICKUP_LANDING_WILD_PERMIT_BOUND_OOI_MARKER,
  .x=target->xCurr,.y=target->yCurr,.finalTargetX=target->xCurr,.finalTargetY=target->yCurr};
 return OverworldPickupLandingWild_Classify(&call);
}
int main(void) {
 const u8 playerKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
 const u8 actorKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
 const u16 land=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;
 const u16 interest=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
 Reset();Interest(playerKind);
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 CHECK(ignorePlayer && observedIgnored==&objects[0]);
 puts("legal ground accepts exact Player occupancy");
 Reset();Interest(actorKind);
 CHECK(Classify(land,actorKind)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 CHECK(observedIgnored==&objects[1] && !ignorePlayer);
 puts("legal ground accepts exact full Actor occupancy");
 Reset();Interest(playerKind);MountPresentation();
 puts("exact Player target with current mounted presentation");
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 CHECK(ignorePlayer && observedIgnored==&mountedPresentation);
 /* The same tile remains blocked for an unrelated or stale presentation. */
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.presentationAttached=0;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.presentationAttached=1;
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.active=0;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.active=1;
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.handle.generation=0;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.handle.generation=9;
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.handle.reserved=1;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.handle.reserved=0;
 state.spawns[OW_WILD_FOLLOWER_SLOT].personality++;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 state.spawns[OW_WILD_FOLLOWER_SLOT].personality--;
 mountedCurrent=0;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 mountedCurrent=1;
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.inputOwnership=0;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.inputOwnership=1;
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.handle.fieldEpoch++;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[OW_WILD_FOLLOWER_SLOT].snapshot.handle.fieldEpoch--;
 state.spawns[OW_WILD_FOLLOWER_SLOT].encounterGeneration++;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 state.spawns[OW_WILD_FOLLOWER_SLOT].encounterGeneration--;
 heldCarrier=(LocalMapObject){.flags=MAPOBJECTFLAG_ACTIVE,.xCurr=19,.yCurr=9};
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 heldCarrier.flags=0;
 objects[1].xCurr=player.xCurr;objects[1].yCurr=player.yCurr;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 objects[1].xCurr=5;objects[1].yCurr=1;
 OverworldPickupRoutePosition reservedPose={player.xCurr,player.yCurr,9,0xFFFF,0};
 actors.slots[2].snapshot.reservationId=9;actors.slots[2].snapshot.handle.fieldEpoch=3;
 actors.slots[2].snapshot.targetX=player.xCurr;actors.slots[2].snapshot.targetY=player.yCurr;
 actors.slots[2].policy.targetSurfaceId=0xFFFF;
 CHECK(Reservations(&world,&actors.slots[0].snapshot.handle,&reservedPose)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
 actors.slots[2].snapshot.reservationId=0;
 CHECK(Reservations(&world,&actors.slots[0].snapshot.handle,&reservedPose)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
 landAllowed=0;waterAllowed=1;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_TERRAIN);
 Reset();Interest(actorKind);MountPresentation();
 mountedPresentation.xCurr=objects[1].xCurr;mountedPresentation.yCurr=objects[1].yCurr;
 CHECK(Classify(land,actorKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 Reset();Interest(actorKind);
 /* OOI permission alone never grants ground, water, or a physical surface. */
 CHECK(Classify(interest,actorKind)==OVERWORLD_MOTION_DECISION_TERRAIN);
 landAllowed=0;waterAllowed=1;
 CHECK(Classify(land|interest,actorKind)==OVERWORLD_MOTION_DECISION_TERRAIN);
 CHECK(Classify(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER,actorKind)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 puts("actual terrain bits remain required and sufficient");
 Reset();Interest(actorKind);queryHasHit=1;
 queryHit=(OverworldWildSurfaceHit){9,8,0,0};
 CHECK(Classify(land|interest,actorKind)==OVERWORLD_MOTION_DECISION_TERRAIN);
 CHECK(Classify(OW_WILD_SURFACE_TYPE_TERRAIN_MASK(0),actorKind)==OVERWORLD_MOTION_DECISION_ACCEPTED);
 includeOriginSurface=0;
 CHECK(Classify(OW_WILD_SURFACE_TYPE_TERRAIN_MASK(0),actorKind)==OVERWORLD_MOTION_DECISION_TERRAIN);
 puts("surface permissions and same-surface checks remain required");
 Reset();Interest(actorKind);
 heldCarrier=(LocalMapObject){.flags=MAPOBJECTFLAG_ACTIVE,.xCurr=5,.yCurr=1};
 CHECK(Classify(land,actorKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 heldCarrier.flags=0;actors.slots[1].snapshot.handle.generation++;
 CHECK(Classify(land,actorKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 actors.slots[1].snapshot.handle.generation--;
 state.spawns[1].encounterGeneration++;
 CHECK(Classify(land,actorKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 state.spawns[1].encounterGeneration--;
 conditions.actors[0].subject.fieldEpoch++;
 CHECK(Classify(land,actorKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 puts("unrelated occupant and stale generation/encounter/subject reject");
 Reset();Interest(playerKind);bodyX=19;bodyY=9;
 CHECK(Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED);
 puts("ignoring Player does not ignore an unrelated occupant");
 /* The policy is generic bare landing only, never a route-query escape. */
#ifdef OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY
 Reset();CertifyCatalog();world.landingPolicy=2;
 CHECK(Binding(&world,NULL)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 world.landingPolicy=OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY;
 CHECK(Binding(&world,&query)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
 puts("unknown policy and route-query use reject");
#endif
 return 0;
}
'''


def source_text(wild=None, landing=None):
    prolog = '#define TRUE 1\n#define FALSE 0\n' + fixture.PROLOG.replace(
        "static int nativeHeightReady=1,nativeHeightDelta,nativeOrigin,queryHasHit;",
        "static int nativeHeightReady=1,nativeHeightDelta,nativeOrigin,queryHasHit;\n"
        "static int landAllowed=1,waterAllowed,includeOriginSurface=1;")
    prolog = prolog.replace(
        "*hit=queryHit;return TRUE;", "*hit=queryHit;if(!includeOriginSurface && x==0 && y==1)hit->surfaceId++;return TRUE;")
    prolog += '\n#include "overworld_application_bank.h"\n'
    runtime = RUNTIME.read_text()
    heights = fixture.function(runtime, "OverworldWildRuntime_ResolveBaseYAt", "BOOL")
    # Bare landing never calls a trajectory. The existing independent Slam
    # check covers the real trajectory's exact crossed-cell clearance.
    harness = fixture.HARNESS.split("static void CertifyCatalog(void)", 1)[0]
    harness = harness.replace("static LocalMapObject player,heldCarrier;",
                              "static LocalMapObject player,heldCarrier,mountedPresentation;")
    harness = harness.replace("static int objectsOccupy;", "static int objectsOccupy,mountedCurrent=1;")
    harness = harness.replace("||object==&player);", "||object==&player||(object==&mountedPresentation&&mountedCurrent));")
    harness = harness.replace("LocalMapObject *current[]={&objects[0],&objects[1],&heldCarrier};",
                              "LocalMapObject *current[]={&objects[0],&objects[1],&heldCarrier,&mountedPresentation};")
    harness = harness.replace("for(unsigned i=0;i<3;i++) {", "for(unsigned i=0;i<4;i++) {")
    harness = harness.replace("static void Reset(void) {",
                              "static void Reset(void) {\n mountedCurrent=1;memset(&mountedPresentation,0,sizeof(mountedPresentation));")
    harness = harness.replace("return OverworldActorHopPlanner_PlanTrajectory(call);",
                              "return OVERWORLD_MOTION_DECISION_ACCEPTED;")
    harness = harness.replace("(void)behavior;return FALSE;", "(void)behavior;return waterAllowed;")
    harness = harness.replace("++landCalls;return TRUE;", "++landCalls;return landAllowed;")
    harness = harness.replace("static void Reset(void) {", "static void Reset(void) {\n landAllowed=1;waterAllowed=0;includeOriginSurface=1;")
    product = (WILD.read_text() if wild is None else wild)
    product = product[product.index("typedef OverworldPickupRouteEdgeResult Result;"):]
    product = product.split("/* Delta uses unsigned subtraction", 1)[0]
    adapter = LANDING.read_text() if landing is None else landing
    adapter = "\n".join(line for line in adapter.splitlines() if not line.startswith("#include"))
    return prolog + heights + fixture.SEAMS + product + adapter + harness + DRIVER


def run_harness(wild=None, landing=None):
    compiler = shutil.which("cc")
    if compiler is None:
        raise unittest.SkipTest("host C compiler is missing")
    with tempfile.TemporaryDirectory(prefix="bound-interest-") as directory:
        source = Path(directory) / "landing.c"
        binary = Path(directory) / "landing"
        source.write_text(source_text(wild, landing))
        compiled = subprocess.run([
            compiler, "-std=c11", "-O2", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
            "-DOVERWORLD_PICKUP_ROUTE_HOST", "-DOVERWORLD_MOTION_HOST",
            "-I", str(ROOT / "include"), str(source), str(NATIVE), "-o", str(binary),
        ], text=True, capture_output=True)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        return subprocess.run([str(binary)], text=True, capture_output=True)


def run_grass_harness(wild=None, *, expected_fast=True):
    compiler = shutil.which("cc")
    if compiler is None:
        raise unittest.SkipTest("host C compiler is missing")
    with tempfile.TemporaryDirectory(prefix="pure-grass-landing-") as directory:
        source = Path(directory) / "grass.c"
        binary = Path(directory) / "grass"
        source.write_text(fixture.grass_source(wild, expected_fast=expected_fast))
        compiled = subprocess.run([
            compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
            "-Wno-unused-function", "-Wno-missing-field-initializers",
            "-Wno-misleading-indentation", "-Wno-sign-compare",
            "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include"),
            str(ROOT / "lib/overworld/overworld_pickup_route.c"), str(NATIVE),
            str(source), "-o", str(binary),
        ], text=True, capture_output=True)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        return subprocess.run([str(binary)], text=True, capture_output=True)


class BoundInterestLandingTests(unittest.TestCase):

    def test_pure_grass_same_eight_candidates_keep_decisions_and_skip_useless_surface_reads(self):
        result = run_grass_harness()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("batch eight: surface=2 behavior=8", result.stdout)
        # Independently run the previous exact reducer shape: same decisions,
        # all eight behavior reads, six unnecessary surface reads restored.
        wild = WILD.read_text()
        shortcut = """        if (c->wanted==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS
            && c->tile.behavior!=2 && c->tile.behavior!=3) {
            c->phase=9;break;
        }
"""
        self.assertEqual(wild.count(shortcut), 1)
        before = run_grass_harness(wild=wild.replace(shortcut, ""), expected_fast=False)
        self.assertEqual(before.returncode, 0, before.stdout + before.stderr)
        self.assertIn("batch eight: surface=8 behavior=8", before.stdout)

    def test_copied_pure_grass_shortcut_guard_faults_reject(self):
        wild = WILD.read_text()
        faults = {
            "mixed mask": ("c->wanted==OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS",
                "(c->wanted&OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS)", "surfaceCalls==1"),
            "real grass veto": ("c->tile.behavior!=2 && c->tile.behavior!=3", "1", "result=="),
            "unknown as known": ("if (c->tile.behavior==0xFF) { c->phase=0;return DEFERRED; }",
                "", "OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED"),
            "header": ("if (actualWord!=expectedWord) return FALSE;",
                "", "OVERWORLD_PICKUP_ROUTE_EDGE_INVALID"),
        }
        for name, (old, new, reason) in faults.items():
            with self.subTest(control=name):
                self.assertEqual(wild.count(old), 1)
                copied = run_grass_harness(wild=wild.replace(old, new))
                self.assertNotEqual(copied.returncode, 0, "known-bad Grass shortcut passed: " + name)
                self.assertIn(reason, copied.stderr)

    def test_exact_target_requires_actual_terrain_and_surface(self):
        result = run_harness()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_copied_mount_owner_guards_reject(self):
        wild = WILD.read_text()
        for guard in ("!actor->handle.generation || ", "|| !actor->presentationAttached"):
            self.assertEqual(wild.count(guard), 1)
            unsafe = run_harness(wild=wild.replace(guard, ""))
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("Classify(land,playerKind)==OVERWORLD_MOTION_DECISION_OCCUPIED", unsafe.stderr)

    def test_copied_missing_policy_and_terrain_grant_fail(self):
        landing = LANDING.read_text()
        assignment = "world.landingPolicy = OVERWORLD_PICKUP_ROUTE_WILD_PERMIT_BOUND_OOI_OCCUPANCY;"
        self.assertEqual(landing.count(assignment), 1)
        old_shape = run_harness(landing=landing.replace(assignment, "world.landingPolicy = 0;"))
        self.assertNotEqual(old_shape.returncode, 0)
        self.assertIn("Classify(land,playerKind)", old_shape.stderr)
        mask = ("    if (world.landingPolicy)\n"
                "        policy.allowedTerrainMask &= ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;\n")
        wild = WILD.read_text()
        grant = "if (!world->landingPolicy && (world->subjectObject!=NULL || !world->hitValid))"
        self.assertEqual(landing.count(mask), 1)
        self.assertEqual(wild.count(grant), 1)
        unsafe = run_harness(
            wild=wild.replace(grant, "if (world->subjectObject!=NULL || !world->hitValid)"),
            landing=landing.replace(mask, ""))
        self.assertNotEqual(unsafe.returncode, 0)
        self.assertIn("Classify(interest,actorKind)", unsafe.stderr)


if __name__ == "__main__":
    unittest.main()

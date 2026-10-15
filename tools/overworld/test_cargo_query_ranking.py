"""Actual shared Cargo query ranking; reuse the native route fixture."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cargo_query_fixture", ROOT / "scripts/verify_overworld_cargo_query.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

HARNESS = r'''
#ifndef OVERWORLD_CARGO_QUERY_SELECT_NEAREST
#define OVERWORLD_CARGO_QUERY_SELECT_NEAREST 0
#endif
static void Two(int far, int near, unsigned advantage, int incumbent) {
 Setup(12,3,far,1);
 bindingsWorld.actorCount=2;
 bindingsWorld.actors[1]=bindingsWorld.actors[0];
 bindingsWorld.actors[1].actor.slot=2;
 bindingsWorld.actors[1].actor.encounterGeneration=8;
 bindingsWorld.actors[1].x=near;
 world.body[1][near]=1;
 input.eligibleActorMask=3;
 /* The former reserved byte has the same address in both input versions. */
 ((unsigned char *)&input)[offsetof(OverworldCargoQueryInput,changesComplete)+1]
     =OVERWORLD_CARGO_QUERY_SELECT_NEAREST ? OVERWORLD_CARGO_QUERY_SELECT_NEAREST|(advantage<<1):0;
 if(incumbent)input.requiredCargo=&bindingsWorld.actors[0].actor;
}
static int Complete(unsigned expected, unsigned slot) {
 for(unsigned n=0;n<4000;n++) {
  CHECK(!Tick());
  if(output.status!=OVERWORLD_PICKUP_ROUTE_PENDING) {
   CHECK(output.status==expected);
   if(expected==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
    CHECK(output.route.cargo.slot==slot);
    CHECK(output.route.cargo.encounterGeneration==(slot==1?7:8));
    CHECK(output.eligibleActorMask==(slot==1?1:2));
    int dx=output.route.pickupPosition.x-output.route.origin.x;
    int dy=output.route.pickupPosition.y-output.route.origin.y;
    unsigned score=(unsigned)((dx<0?-dx:dx)>(dy<0?-dy:dy)?(dx<0?-dx:dx):(dy<0?-dy:dy));
#if OVERWORLD_CARGO_QUERY_SELECT_NEAREST
    if(input.selectionFlags&OVERWORLD_CARGO_QUERY_SELECT_NEAREST) CHECK(scheduler.bestScore==score);
#else
    (void)score;
#endif
   }
   return 0;
  }
 }
 CHECK(0);return 1;
}
static int Scanned(void) {
 for(unsigned n=0;n<4000;n++) {
  CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
  if(scheduler.rankPhase==OVERWORLD_CARGO_QUERY_RANK_REPROVE) return 0;
 }
 CHECK(0);return 1;
}
static void MoveCargo(unsigned n,int x) {
 changes[0]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[n].x,1};
 world.body[1][bindingsWorld.actors[n].x]=0;bindingsWorld.actors[n].x=x;world.body[1][x]=1;
 changes[1]=(OverworldCargoQueryChangedTile){x,1};input.changedTileCount=2;++query.dynamicRevision;
}
int main(int argc,char **argv) {
 CHECK(argc==2);
 if(!strcmp(argv[1],"nearest")) {Two(8,3,1,0);return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,2);}
 if(!strcmp(argv[1],"advantage")) {Two(4,3,2,1);return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,1);}
 if(!strcmp(argv[1],"switch")) {Two(4,3,1,1);return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,2);}
 if(!strcmp(argv[1],"unreachable")) {
  Two(8,3,3,1);for(unsigned y=0;y<3;y++)world.body[y][5]=1;
  return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,2);
 }
 if(!strcmp(argv[1],"stale-incumbent")) {
  Two(8,3,3,1);OverworldActorHandle stale=bindingsWorld.actors[0].actor;
  stale.encounterGeneration++;input.requiredCargo=&stale;
  return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,2);
 }
 if(!strcmp(argv[1],"fixed")) {
  Two(8,3,1,1);((unsigned char *)&input)[offsetof(OverworldCargoQueryInput,changesComplete)+1]=0;
  return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,1);
 }
 if(!strcmp(argv[1],"pending")) {
  Two(8,3,1,1);positionFail=OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED;
  for(unsigned n=0;n<8;n++){CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);}
  positionFail=0;return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,2);
 }
 if(!strcmp(argv[1],"limit")) {
  Two(8,3,1,1);world.reachFail=OVERWORLD_PICKUP_ROUTE_EDGE_RESOURCE_LIMIT;
  CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT && !output.eligibleActorMask);return 0;
 }
 if(!strcmp(argv[1],"flags")) {
  Two(8,3,1,0);((unsigned char *)&input)[offsetof(OverworldCargoQueryInput,changesComplete)+1]=8;
  CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_INVALID && !output.eligibleActorMask);return 0;
 }
 if(!strcmp(argv[1],"moving-origin")) {
  Two(8,3,1,1);unsigned progressed=0;
  for(unsigned n=0;n<4000;n++) {
   if(!(n%8)) {
    changes[0]=(OverworldCargoQueryChangedTile){query.origin.x,1};
    query.origin.x=(n/8)&1;bindingsWorld.subjectX=query.origin.x;
    changes[1]=(OverworldCargoQueryChangedTile){query.origin.x,1};input.changedTileCount=2;++query.dynamicRevision;
   }
   CHECK(!Tick());if(scheduler.rankPhase!=OVERWORLD_CARGO_QUERY_RANK_INCUMBENT)progressed=1;
   if(output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE) {
    CHECK(progressed && output.route.cargo.slot==2 && output.eligibleActorMask==2);
    CHECK(output.route.origin.x==query.origin.x);
    int dx=output.route.pickupPosition.x-query.origin.x;
    CHECK(scheduler.bestScore==(unsigned)(dx<0?-dx:dx));return 0;
   }
   CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
  }
  CHECK(0);return 1;
 }
 if(!strcmp(argv[1],"stale-winner")) {
  Two(8,3,1,0);CHECK(!Scanned());
  bindingsWorld.actors[1].actor.encounterGeneration++;
  input.eligibleActorMask=1;
  CHECK(!Tick());CHECK(output.status==OVERWORLD_PICKUP_ROUTE_PENDING && !output.eligibleActorMask);
  return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,1);
 }
 if(!strcmp(argv[1],"moved-incumbent")) {
  Two(4,3,2,1);CHECK(!Scanned());MoveCargo(0,10);
  return Complete(OVERWORLD_PICKUP_ROUTE_REACHABLE,2);
 }
 CHECK(0);return 1;
}
'''


class CargoQueryRankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="cargo-ranking-")
        folder = Path(cls.directory.name)
        prelude = fixture.PRELUDE.replace("q->cargo.encounterGeneration!=7", "(q->cargo.encounterGeneration!=7 && q->cargo.encounterGeneration!=8)")
        prelude = prelude[:prelude.index("static Result Classify(")].replace("static unsigned callsBefore;\n", "")
        harness = folder / "check.c"
        harness.write_text(prelude + fixture.HARNESS.split("static OverworldPickupRouteEdge hopEdges", 1)[0] + HARNESS)
        cls.binary = folder / "check"
        command = [shutil.which("cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include")]
        subprocess.run(command + [str(ROOT / "lib/overworld" / name) for name in ("overworld_cargo_query.c", "overworld_pickup_route_native.c", "overworld_pickup_route.c")] + [str(harness), "-o", str(cls.binary)], check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def check(self, name):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_closest_proved_pickup_position_wins(self): self.check("nearest")
    def test_incumbent_keeps_insufficient_advantage(self): self.check("advantage")
    def test_one_tile_advantage_switches(self): self.check("switch")
    def test_unreachable_incumbent_does_not_apply_advantage(self): self.check("unreachable")
    def test_stale_incumbent_can_be_replaced(self): self.check("stale-incumbent")
    def test_default_required_cargo_stays_fixed(self): self.check("fixed")
    def test_deferred_incumbent_stays_pending(self): self.check("pending")
    def test_limit_is_not_unreachable(self): self.check("limit")
    def test_unknown_selection_flags_fail_closed(self): self.check("flags")
    def test_moving_origin_retains_ranking_progress_and_fresh_score(self): self.check("moving-origin")
    def test_winner_identity_is_reproved_before_eligibility(self): self.check("stale-winner")
    def test_moved_incumbent_cannot_retain_old_pickup_score(self): self.check("moved-incumbent")


if __name__ == "__main__": unittest.main()

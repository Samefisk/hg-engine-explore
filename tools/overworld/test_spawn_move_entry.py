"""Actual-C Move From Off Screen arrival gate and shared idle intent path."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from tools.overworld.test_spawn_spatial import extract_function

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"

PREFIX = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef int BOOL; typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_LAND_SURF_MAX_SPAWNS 6
#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 60
#define OW_WILD_REFILL_FULL_DENSITY_COUNT 4
#define OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES 8
#define OW_WILD_SPAWN_ENTRY_NONE 0
#define OW_WILD_SPAWN_ENTRY_MOVE 1
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 6
#define OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN 0
#define OW_WILD_SPAWNER_IDLE_RETRY_REST_FRAMES 8
#define OW_WILD_SPAWNER_IDLE_CONDITION_REST_FRAMES 4
#define OW_WILD_SPAWNER_IDLE_INTENTS_PER_UPDATE 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK 0
#define OW_WILD_SPAWNER_THROW_TARGET_NONE 0
#define OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG 64
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_MOTION_PHASE_CANCELED 6
typedef struct LocalMapObject { int xCurr,yCurr; BOOL single; u32 flags; } LocalMapObject;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildSpawnState {
 struct { BOOL active; LocalMapObject *object; u16 encounterGeneration; } spawns[10];
 u8 movementSpawnRunActive[10],movementSpotStates[10],movementCooldowns[10];
 u8 movementTeleportVisiblePause[10],movementCrashShakeTimers[10];
 int movementSpawnRunTargetX[10],movementSpawnRunTargetY[10];
 u16 movementInProgressMask; int movementQueuedBattleSlot; FieldSystem *movementFieldSystem;
} OverworldWildSpawnState;
typedef struct OverworldActorPolicyView { u8 motionPhase; } OverworldActorPolicyView;
typedef struct OverworldWildBehaviorProfile { int onReachAction; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { u8 chillLocomotion; } OverworldWildBehaviorPrimitives;
static struct { u16 intentConditionsCheckedMask; } sOverworldWildFlags;
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ 0
#define OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR 1
#define OVERWORLD_TARGET_BINDING_CARGO 1
#define OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR 2
typedef struct OverworldBehaviorConditionTargetReference { int kind; struct { u16 slot,encounterGeneration; } actor; } OverworldBehaviorConditionTargetReference;
typedef struct OverworldTargetBindingPosition { OverworldBehaviorConditionTargetReference target; } OverworldTargetBindingPosition;
typedef struct OverworldWildBehaviorConditionRuntime { int unused; } OverworldWildBehaviorConditionRuntime;
static BOOL moving,policyKnown=TRUE,resolveOK=TRUE,ownerAccepted=TRUE,pendingBattle=FALSE;
static unsigned activeApplications; static int ownerTargetX,ownerTargetY;
static OverworldWildBehaviorConditionRuntime*OverworldWildSpawns_GetConditionRuntime(OverworldWildSpawnState*s){(void)s;return NULL;}
static BOOL PlayerHealthThrowService_IsReady(void){return FALSE;}
static BOOL Binding(OverworldWildSpawnState*s,int i,int name,OverworldTargetBindingPosition*out){(void)s;(void)i;(void)name;(void)out;assert(0);return FALSE;}
static struct { BOOL (*bindingPosition)(OverworldWildSpawnState*,int,int,OverworldTargetBindingPosition*); } service={Binding};
#define PLAYER_HEALTH_THROW_SERVICE_ENTRY (&service)
#define OW_WILD_RUNTIME(s) (&runtime)
static struct { struct { u8 targets[10]; } throwState; u32 entryRouteSerial[10]; } runtime;
static unsigned OverworldWildSpawns_GetActiveConditionApplications(OverworldWildSpawnState*s,int i){(void)s;(void)i;return activeApplications;}
static BOOL OverworldWildSpawns_TryReservePickupTarget(OverworldWildSpawnState*s,int i,int target){(void)s;(void)i;(void)target;assert(0);return FALSE;}
static void OverworldWildSpawns_AbortThrow(OverworldWildSpawnState*s,int i){(void)s;(void)i;assert(0);}
static BOOL OverworldWildSpawns_HasPendingBattle(OverworldWildSpawnState*s){(void)s;return pendingBattle;}
static u8 phase; static int clears,resolves,intents,landing,visual,post;
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *o){ return o->single; }
static BOOL OverworldWildSpawns_IsMovementSlotInProgress(OverworldWildSpawnState *s,int slot){(void)s;(void)slot;return moving;}
static BOOL OverworldActorPolicy_Inspect(u8 slot,OverworldActorPolicyView *p){(void)slot;p->motionPhase=phase;return policyKnown;}
static int OverworldWildSpawns_ObjectCurrentX(LocalMapObject *o){return o->xCurr;}
static int OverworldWildSpawns_ObjectCurrentY(LocalMapObject *o){return o->yCurr;}
static void OverworldWildSpawns_ClearSpawnRunState(OverworldWildSpawnState*s,int i){s->movementSpawnRunActive[i]=0;s->movementSpawnRunTargetX[i]=s->movementSpawnRunTargetY[i]=0;}
static void OverworldWildSpawns_SetObjectLandingTile(FieldSystem*f,LocalMapObject*o,int x,int y){(void)f;assert(o->xCurr==x&&o->yCurr==y);landing++;}
static void OverworldWildSpawns_RefreshCanopyHopperVisualStateAtLanding(OverworldWildSpawnState*s,FieldSystem*f,int i,LocalMapObject*o){(void)s;(void)f;(void)i;(void)o;visual++;}
static void OverworldWildSpawns_ClearWalkMovementState(OverworldWildSpawnState*s,int i,LocalMapObject*o){(void)s;(void)i;(void)o;clears++;}
static void OverworldWildSpawns_SetPostSpawnStartupCooldown(OverworldWildSpawnState*s,int i){post++;s->movementCooldowns[i]=12;}
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(OverworldWildSpawnState*s,int i,OverworldWildBehaviorProfile*p,OverworldWildBehaviorPrimitives*r){(void)s;(void)i;(void)p;r->chillLocomotion=2;}
static BOOL OverworldWildSpawns_ResolveConditionsAtIntentBoundary(OverworldWildSpawnState*s,int i,OverworldWildBehaviorProfile*p,OverworldWildBehaviorPrimitives*r){(void)s;(void)p;(void)r;resolves++;sOverworldWildFlags.intentConditionsCheckedMask|=1u<<i;return resolveOK;}
static void OverworldWildSpawns_PrepareConditionalTeleport(OverworldWildSpawnState*s,int i,LocalMapObject*o,OverworldWildBehaviorProfile*p){(void)s;(void)i;(void)o;(void)p;assert(0);}
static BOOL OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(OverworldWildSpawnState*s,int i,LocalMapObject*o,OverworldWildBehaviorProfile*p,OverworldWildBehaviorPrimitives*r){
 assert(o==s->spawns[i].object&&p!=NULL&&r!=NULL);
 intents++;ownerTargetX=s->movementSpawnRunTargetX[i];ownerTargetY=s->movementSpawnRunTargetY[i];return ownerAccepted;
}
'''

DRIVER = r'''
static void Reset(OverworldWildSpawnState *s,FieldSystem*f,LocalMapObject*o){
 memset(s,0,sizeof(*s));s->spawns[0].active=TRUE;s->spawns[0].object=o;
 o->xCurr=598;o->yCurr=404;o->single=FALSE;s->movementFieldSystem=f;
 s->movementSpawnRunActive[0]=1;s->movementSpawnRunTargetX[0]=582;s->movementSpawnRunTargetY[0]=404;
 s->movementQueuedBattleSlot=-1;moving=FALSE;phase=0;policyKnown=resolveOK=TRUE;
 sOverworldWildFlags.intentConditionsCheckedMask=0;clears=resolves=intents=landing=visual=post=0;
 activeApplications=0;ownerAccepted=TRUE;pendingBattle=FALSE;ownerTargetX=ownerTargetY=0;
}
static void TickIdleTailMany(OverworldWildSpawnState *state,FieldSystem*fieldSystem,int count,LocalMapObject*objects){
 int idleIntentsIssued=0;
  for(int i=0;i<count;i++){
  LocalMapObject*object=&objects[i];
  OverworldWildBehaviorProfile profile={0};OverworldWildBehaviorPrimitives primitives={0};
  BOOL frameTick=TRUE,actorMotionOwnsFacing=phase>0&&phase<6,shouldIssueLookCommand=FALSE;
  u8 cooldown=state->movementCooldowns[i],throwTarget=0;
  /* @TAIL@ */
 }
}
static void TickIdleTail(OverworldWildSpawnState *state,FieldSystem*fieldSystem){
 TickIdleTailMany(state,fieldSystem,1,state->spawns[0].object);
}
int main(int argc,char**argv){
 assert(argc==2);OverworldWildSpawnState s;FieldSystem f={0};LocalMapObject o;Reset(&s,&f,&o);
 if(!strcmp(argv[1],"idle")){
  TickIdleTail(&s,&f);assert(intents==1&&resolves==1&&!clears&&!landing);
  assert(s.movementSpawnRunActive[0]==1&&s.movementSpawnRunTargetX[0]==582&&o.xCurr==598);
  assert(ownerTargetX==582&&ownerTargetY==404);
  sOverworldWildFlags.intentConditionsCheckedMask=0;s.movementCooldowns[0]=5;
  TickIdleTail(&s,&f);assert(intents==1&&s.movementCooldowns[0]==4&&!clears);
  sOverworldWildFlags.intentConditionsCheckedMask=0;s.movementCooldowns[0]=0;resolveOK=FALSE;
  TickIdleTail(&s,&f);assert(intents==1&&!clears);
 }else if(!strcmp(argv[1],"accepted")){
  moving=TRUE;TickIdleTail(&s,&f);assert(!intents&&!resolves&&!clears);moving=FALSE;
  o.single=TRUE;TickIdleTail(&s,&f);assert(!intents&&!resolves&&!clears);o.single=FALSE;
  phase=1;TickIdleTail(&s,&f);assert(!intents&&!resolves&&!clears);
  phase=0;s.movementCrashShakeTimers[0]=1;TickIdleTail(&s,&f);assert(!intents&&!resolves);
  s.movementCrashShakeTimers[0]=0;s.movementQueuedBattleSlot=0;TickIdleTail(&s,&f);assert(!intents&&!resolves);
 }else if(!strcmp(argv[1],"rest")){
  /* A free-roaming actor whose search starts nothing rests between tries. */
  LocalMapObject many[4];
  Reset(&s,&f,&o);s.movementSpawnRunActive[0]=0;
  int observed=0,previous=-1;
  for(int tick=0;tick<20;tick++){
   sOverworldWildFlags.intentConditionsCheckedMask=0;
   TickIdleTail(&s,&f);
   if(s.movementCooldowns[0]==8&&previous!=8) observed++;
   previous=s.movementCooldowns[0];
  }
  assert(observed==3&&previous==5);
  /* No rest while moving; a Condition-controlled actor rests four updates, never zero. */
  Reset(&s,&f,&o);s.movementSpawnRunActive[0]=0;moving=TRUE;sOverworldWildFlags.intentConditionsCheckedMask=0;
  TickIdleTail(&s,&f);assert(s.movementCooldowns[0]==0);
  Reset(&s,&f,&o);s.movementSpawnRunActive[0]=0;sOverworldWildFlags.intentConditionsCheckedMask=0;
  activeApplications=1;TickIdleTail(&s,&f);assert(s.movementCooldowns[0]==4&&intents==1);
  Reset(&s,&f,&o);sOverworldWildFlags.intentConditionsCheckedMask=0;TickIdleTail(&s,&f);
  assert(s.movementSpawnRunActive[0]==1&&s.movementCooldowns[0]==8);
  /* One search per update: the other free actors keep a zero cooldown. */
  for(int n=0;n<4;n++){many[n]=o;s.spawns[n].active=TRUE;s.spawns[n].object=&many[n];s.movementSpawnRunActive[n]=0;s.movementCooldowns[n]=0;}
  sOverworldWildFlags.intentConditionsCheckedMask=0;activeApplications=0;moving=FALSE;
  TickIdleTailMany(&s,&f,4,many);
  assert(s.movementCooldowns[0]==8&&s.movementCooldowns[1]==0&&s.movementCooldowns[2]==0&&s.movementCooldowns[3]==0);
  sOverworldWildFlags.intentConditionsCheckedMask=0;
  TickIdleTailMany(&s,&f,4,many);
  assert(s.movementCooldowns[0]==7&&s.movementCooldowns[1]==8&&s.movementCooldowns[2]==0&&s.movementCooldowns[3]==0);
  /* Condition actors rest too: otherwise the first one would take the single
   * search every update and starve every later slot. */
  for(int n=0;n<4;n++){many[n]=o;s.spawns[n].active=TRUE;s.spawns[n].object=&many[n];s.movementSpawnRunActive[n]=0;s.movementCooldowns[n]=0;}
  intents=0;sOverworldWildFlags.intentConditionsCheckedMask=0;activeApplications=1;moving=FALSE;
  TickIdleTailMany(&s,&f,4,many);
  assert(intents==1&&s.movementCooldowns[0]==4&&s.movementCooldowns[1]==0);
  sOverworldWildFlags.intentConditionsCheckedMask=0;
  TickIdleTailMany(&s,&f,4,many);
  assert(intents==2&&s.movementCooldowns[0]==3&&s.movementCooldowns[1]==4&&s.movementCooldowns[2]==0);
 }else if(!strcmp(argv[1],"arrival")){
  o.xCurr=582;assert(OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,&f,0,&o));
  assert(!s.movementSpawnRunActive[0]&&s.movementSpawnRunTargetX[0]==0&&s.movementSpawnRunTargetY[0]==0);
  assert(landing==1&&visual==1&&clears==1&&post==1&&s.movementCooldowns[0]==12&&!resolves&&!intents);
  Reset(&s,&f,&o);assert(OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,&f,0,NULL));
  assert(!s.movementSpawnRunActive[0]&&!landing&&!clears&&!resolves&&!intents);
 }else if(!strcmp(argv[1],"inactive")){
  assert(!OverworldWildSpawns_UpdateSpawnMoveTargetState(NULL,&f,0,&o));
  assert(!OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,NULL,0,&o));
  assert(!OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,&f,-1,&o));
  assert(!OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,&f,10,&o));
  s.movementSpawnRunActive[0]=2;assert(!OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,&f,0,&o));
  s.movementSpawnRunActive[0]=1;s.spawns[0].active=FALSE;assert(!OverworldWildSpawns_UpdateSpawnMoveTargetState(&s,&f,0,&o));
  assert(!landing&&!clears&&!resolves&&!intents);
 }else if(!strcmp(argv[1],"dispatch")){
  OverworldWildBehaviorProfile p={0};OverworldWildBehaviorPrimitives primitives={2};
  assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));
  assert(intents==1&&ownerTargetX==582&&ownerTargetY==404&&!clears&&!resolves);
  ownerAccepted=FALSE;assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));
  assert(intents==2&&s.movementSpawnRunActive[0]==1&&s.movementSpawnRunTargetX[0]==582);
  s.movementSpawnRunActive[0]=0;assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));assert(intents==2);
  s.movementSpawnRunActive[0]=2;assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));assert(intents==2);
  activeApplications=1;ownerAccepted=TRUE;assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));assert(intents==3);
  pendingBattle=TRUE;assert(OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));assert(intents==4);
  ownerAccepted=FALSE;assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));assert(intents==5);
  p.onReachAction=OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR;
  assert(!OverworldWildSpawns_IssueIdleIntent(&s,&f,0,&o,&p,&primitives));assert(intents==5);
 }else assert(0);
 return 0;
}
'''


def program(source):
    resume = extract_function(source, "OverworldWildSpawns_ResumeOwnerAfterAlert", "void")
    update = extract_function(source, "OverworldWildSpawns_UpdateSpawnMoveTargetState", "BOOL")
    tick = extract_function(source, "OverworldWildSpawns_TickMovementParams", "void")
    start = tick.index("if (OverworldWildSpawns_UpdateSpawnMoveTargetState(")
    end = tick.index("        }\n    }\n}", start)
    issue = extract_function(source, "OverworldWildSpawns_IssueIdleIntent", "BOOL")
    # Update is now the typed Query op4 wrapper. Execute its actual NativeUpdate
    # reducer and resident finish owner; only the transport/stock seams are
    # mocked. Unexpected route queries must fail in this idle-intent fixture.
    from scripts.verify_overworld_spawn_move_entry import type_decl
    entry = (ROOT / "lib/overworld/overworld_entry_route.c").read_text()
    header = (ROOT / "include/overworld_entry_route.h").read_text()
    behavior = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    constants = "\n".join(line for line in behavior.splitlines()
                          if line.startswith("#define OW_WILD_BEHAVIOR_ON_REACH_ACTION("))
    constants += "\n" + "\n".join(line for line in header.splitlines()
                                   if line.startswith("#define OVERWORLD_ENTRY_NATIVE_UPDATE ")) + "\n"
    types = r"""
#define MAPOBJECTFLAG_SINGLE_MOVEMENT (1u << 1)
#define OVERWORLD_PICKUP_ROUTE_REACHABLE 1
#define OVERWORLD_ENTRY_ROUTE_GUIDE 2
#define OVERWORLD_ENTRY_ROUTE_RETIRE 3
typedef int OverworldPickupRouteStatus;
typedef struct OverworldWildPreparedSpawn OverworldWildPreparedSpawn;
typedef struct OverworldEntryRouteReceipt {u8 hasNextStep;} OverworldEntryRouteReceipt;
typedef struct OverworldEntryRouteNativeOps {
 void (*finish)(OverworldWildSpawnState*,FieldSystem*,int,LocalMapObject*,int,int,u8);
} OverworldEntryRouteNativeOps;
typedef struct EntryWorldOps {BOOL (*inspectPolicy)(u8,OverworldActorPolicyView*);} EntryWorldOps;
typedef struct EntryWorld {const EntryWorldOps *ops;} EntryWorld;
typedef struct OverworldCargoQueryWildCall {const EntryWorld *world;} OverworldCargoQueryWildCall;
"""
    control = type_decl(header, "OverworldEntryRouteNativeControl")
    native = extract_function(entry, "NativeUpdate", "BOOL")
    finish = extract_function(source, "OverworldWildSpawns_FinishEntryArrival", "void")
    seams = r"""
static OverworldPickupRouteStatus NativeQueryEntry(const OverworldCargoQueryWildCall *base,
 const OverworldEntryRouteNativeControl*c,OverworldWildSpawnState*s,FieldSystem*f,int slot,
 const OverworldWildBehaviorProfile*p,u8 operation,OverworldWildPreparedSpawn*prepared,
 u8 accepted,u8 idle,u32 sequence,OverworldEntryRouteReceipt*receipt)
{(void)base;(void)c;(void)s;(void)f;(void)slot;(void)p;(void)operation;(void)prepared;(void)accepted;(void)idle;(void)sequence;(void)receipt;assert(0);return 0;}
"""
    bridge = r"""
static u32 OverworldWildSpawns_EntryControl(OverworldWildSpawnState*s,FieldSystem*f,int slot,
 const OverworldWildBehaviorProfile*p,OverworldEntryRouteNativeControl*c)
{
 assert(c->operation==OVERWORLD_ENTRY_NATIVE_UPDATE && p==NULL);
 const OverworldEntryRouteNativeOps ops={OverworldWildSpawns_FinishEntryArrival};
 const EntryWorldOps worldOps={OverworldActorPolicy_Inspect};
 const EntryWorld world={&worldOps};const OverworldCargoQueryWildCall call={&world};
 c->ops=&ops;
 if(s!=NULL) s->movementInProgressMask=moving?1:0;
 if(c->object!=NULL) c->object->flags=c->object->single?MAPOBJECTFLAG_SINGLE_MOVEMENT:0;
 return NativeUpdate(&call,c,s,f,slot,c->object);
}
"""
    return (PREFIX + constants + types + control + seams + native + finish + bridge
            + resume + update + issue + DRIVER.replace("/* @TAIL@ */", tick[start:end]))


class SpawnMoveEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="ow-spawn-move-")
        cls.binary = Path(cls.tmp.name) / "check"
        source = Path(cls.tmp.name) / "check.c"
        source.write_text(program(SOURCE.read_text()))
        subprocess.run(["cc", "-std=c11", "-O2", str(source), "-o", str(cls.binary)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check_case(self, case):
        result = subprocess.run([str(self.binary), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_idle_startup_yields_to_shared_intent_without_reset(self):
        self.check_case("idle")

    def test_failed_idle_search_rests_and_one_search_runs_per_update(self):
        self.check_case("rest")

    def test_accepted_motion_crash_and_battle_keep_ownership(self):
        self.check_case("accepted")

    def test_arrival_and_lost_object_clear_only_startup(self):
        self.check_case("arrival")

    def test_startup_uses_shared_owner_without_conditions_and_preserves_returns(self):
        self.check_case("dispatch")

    def test_inactive_invalid_and_other_startup_modes_are_not_consumed(self):
        self.check_case("inactive")


class SpawnMoveLedgeGateTests(unittest.TestCase):
    def test_reverse_ledge_admission_savings_and_read_guards(self):
        from scripts import verify_overworld_spawn_move_entry as host
        with tempfile.TemporaryDirectory(prefix="ow-entry-ledge-") as temporary:
            work = Path(temporary)
            binary = host.compile_program(work / "current", host.ledge_program(), linked=True)
            result = subprocess.run([str(binary), "savings"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for fault, assertion in (
                ("old-ledge-path", "reads==1 && heightReads==0 && terrainReads==0 && calls==1"),
                ("negative-predecessor-read", "Complete()==INVALID && reads==0 && behaviorReads==0"),
            ):
                binary = host.compile_program(work / fault, host.ledge_program(fault=fault), linked=True)
                result = subprocess.run([str(binary), "savings"], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, fault)
                self.assertIn(assertion, result.stderr, fault)



class SpawnMoveRootBindingTests(unittest.TestCase):
    def test_live_root_excludes_only_bound_subject_and_keeps_landing_guards(self):
        from scripts import verify_overworld_spawn_move_entry as host
        with tempfile.TemporaryDirectory(prefix="ow-entry-root-") as temporary:
            work=Path(temporary)
            binary=host.compile_program(work / "current",host.entry_root_program(),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("reads=8,1,8,1 ignoredExact=1",result.stdout)
            binary=host.compile_program(work / "old",host.entry_root_program(fault="old-root-mode"),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("results[3]==LEGAL",result.stderr)

    def test_prepared_key_matches_live_with_finite_anchor_checks(self):
        from scripts import verify_overworld_spawn_move_entry as host
        with tempfile.TemporaryDirectory(prefix="ow-entry-policy-") as temporary:
            work=Path(temporary)
            binary=host.compile_program(work / "current",host.prepared_policy_program(),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            binary=host.compile_program(work / "old",host.prepared_policy_program(fault="old-prepared-key"),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("live==beforeBirth",result.stderr)


    def test_saved_witness_uses_checked_current_surface_before_first_motion(self):
        from scripts import verify_overworld_spawn_move_entry as host
        with tempfile.TemporaryDirectory(prefix="ow-entry-surface-") as temporary:
            work=Path(temporary)
            binary=host.compile_program(work / "current",host.saved_witness_program(),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("update=9 status=1 reads=0 next=1 nodes=0",result.stdout)
            self.assertIn("surface0, full height, stale Actor/Field",result.stdout)
            binary=host.compile_program(work / "old",host.saved_witness_program(fault="last-destination-token"),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("updates<12",result.stderr)



    def test_ready_entry_walk_uses_complete_physical_landing_contract(self):
        from scripts import verify_overworld_spawn_move_entry as host
        with tempfile.TemporaryDirectory(prefix="ow-entry-walk-") as temporary:
            work=Path(temporary)
            binary=host.compile_program(work / "current",host.bare_walk_program(),linked=True)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn("strict bare Walk decision=0 height=1 collision=1 source=1 target=1",result.stdout)
            self.assertIn("kind/pair/budget guards PASS",result.stdout)
            for fault in ("old-bare-pair","missing-bare-directions"):
                with self.subTest(fault=fault):
                    binary=host.compile_program(work / fault,host.bare_walk_program(fault=fault),linked=True)
                    result=subprocess.run([str(binary)],capture_output=True,text=True)
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn("actual==OVERWORLD_MOTION_DECISION_ACCEPTED",result.stderr)


if __name__ == "__main__":
    unittest.main()

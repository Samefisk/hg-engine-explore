"""Actual production-C Throw target-height latch and flight restoration.

Native pointer reads and START/ACK are named host seams. This verifies the
existing shared binding and Wild owners; it does not claim native game proof.
"""
from pathlib import Path
import sys,hashlib,json,subprocess,shlex,os,re
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/tickets/tkt26-throw-height-host'
from tools.overworld import test_throw_failure_composition as base
from tools.overworld.test_picked_up_actor_control import extract_function
WILD=ROOT/'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c'
p=base.PRELUDE
p=base.replace(p,'typedef struct LocalMapObject { int xCurr,yCurr; u32 posVec[3]; } LocalMapObject;','typedef struct LocalMapObject { int xCurr,yCurr; u32 posVec[3],flags,faceVec[3],unk88[3]; s16 hInit,hPrev,hCurr; } LocalMapObject;')
p=p.replace('u8 active; u16 encounterGeneration;','u8 active; u16 encounterGeneration; u32 personality;')
p=p.replace('s16 movementCustomJumpTargetX[10],movementCustomJumpTargetY[10];','s16 movementCustomJumpTargetX[10],movementCustomJumpTargetY[10]; u8 movementCustomMotionModes[10],movementCustomJumpActive[10];')
p=p.replace('struct FieldSystem { LocalMapObject *playerAvatar; };','typedef struct PlayerAvatar { LocalMapObject *mapObject; } PlayerAvatar; struct FieldSystem { PlayerAvatar *playerAvatar; }; static FieldSystem *gFieldSysPtr;')
# Keep the current borrowed Held owner, with only native START mocked.
start=p.index('static BOOL Flight(');end=p.index('\n}',start)+2
p=p[:start]+'static BOOL StartFlight(OverworldWildSpawnState *,FieldSystem *,int,LocalMapObject *,u8,u8,int,int,const OverworldWildBehaviorProfile *,BOOL);\nstatic BOOL Flight(OverworldWildSpawnState *s,FieldSystem *f,int slot,LocalMapObject *o,u8 direction,u8 distance,int x,int z,const OverworldWildBehaviorProfile *profile,BOOL flag) { return StartFlight(s,f,slot,o,direction,distance,x,z,profile,flag); }'+p[end:]
start=p.index('static const LocalMapObject *OverworldWildSpawns_GetThrowBindingBody(');end=p.index('\n}',start)+2
p=p[:start]+'static const LocalMapObject *OverworldWildSpawns_GetThrowBindingBody(OverworldWildSpawnState *,int,u8,int,int);'+p[end:]
p=p.replace('#define OverworldWildSpawns_StartThrowRecovery(...) ((void)0)','#define OverworldWildSpawns_StartThrowRecovery(...) ((void)0)')
p=p.replace('assert((code&255)==PLAYER_HEALTH_MOTION_CANCEL);','assert((code&255)==PLAYER_HEALTH_MOTION_CANCEL||(code&255)==PLAYER_HEALTH_THROW_LAUNCH);')
p=p.replace('static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void) { return &helper; }', 'static BOOL helperReady=TRUE; static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void) { return helperReady?&helper:NULL; }')
p=p.replace('const OverworldCargoReadWildTargetOps sOverworldWildCargoTargetOps={X,Y,', 'const OverworldCargoReadWildTargetOps sOverworldWildCargoTargetOps={X,Y,')
# The borrowed read owner sees a PlayerAvatar in production; its named getters receive the mapObject.
read=base.functions(base.READ,[('OverworldCargoReadWild_Target','u8')]).replace('field->playerAvatar','field->playerAvatar->mapObject')
EXTRA=r'''
#define MAPOBJECTFLAG_ACTIVE 1
typedef const LocalMapObject *LocalMapObjectPtr;
#define OW_WILD_SPAWNER_CUSTOM_MOTION_THROW_FLAG 3
#define OW_WILD_SPAWN_ENTRY_FLY_IN 2
#define OW_WILD_CUSTOM_MOTION_JUMP 2
#define OW_WILD_CUSTOM_MOTION_WALK 1
#define OVERWORLD_ACTOR_SYSTEM_ABI_VERSION 2
#define OVERWORLD_ACTOR_INSPECT_ACTOR_HANDLE 1
#define OVERWORLD_ACTOR_RESULT_OK 0
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_MOTION_PHASE_SETTLING 4
#define OVERWORLD_MOTION_PHASE_COMMIT_PENDING 3
#define OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED 1
#define OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED 2
#define OVERWORLD_ACTOR_BOUNDARY_STREAM_READY 4
/* Native pointer owners and the Actor inspect call are host boundaries. */


static OverworldActorHandle nativeHandles[10];static u32 nativePids[10];static BOOL nativeCurrent=TRUE;
static int Inspect(const OverworldActorQuery *q,OverworldActorSnapshot *v) { memset(v,0,sizeof(*v));assert(q->reserved==0&&q->sequence==0&&q->index==0);if(q->actor.slot>=10||memcmp(&q->actor,&nativeHandles[q->actor.slot],sizeof(q->actor)))return 2;v->hasActor=1;v->actor.active=1;v->actor.subjectIdentity=nativePids[q->actor.slot];return 0; }
static const struct { int (*inspect)(const OverworldActorQuery *,OverworldActorSnapshot *); } actorEntry={Inspect};
#undef OVERWORLD_ACTOR_SYSTEM_ENTRY
#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&actorEntry)
static BOOL OverworldWildSpawns_IsCurrentMapObject(FieldSystem *f,LocalMapObject *o) { return nativeCurrent&&f==gFieldSysPtr&&o!=NULL&&(o->flags&1); }
static s32 nativeCatalogY,flightY;
static s32 TargetY(OverworldWildSpawnState *,int,LocalMapObject *,BOOL,BOOL,BOOL,FieldSystem *,int,int,u8);
static BOOL StartFlight(OverworldWildSpawnState *s,FieldSystem *f,int slot,LocalMapObject *o,u8 direction,u8 distance,int x,int y,const OverworldWildBehaviorProfile *profile,BOOL mode) { (void)direction;(void)distance;(void)profile;flightCalls++;flightY=TargetY(s,slot,o,FALSE,mode,FALSE,f,x,y,direction);return TRUE; }
static BOOL sOverworldWildSpawnHopPreparing;
#define OverworldWildSpawns_ResolveObjectLandingHeight(...) ((void)0)
#define OverworldWildSpawns_MovementDirectionDeltaX(...) 0
#define OverworldWildSpawns_MovementDirectionDeltaY(...) 0
#define OverworldWildSpawns_SetObjectTile(...) ((void)0)
#define OverworldWildSpawns_GetObjectGroundBaseYAt(...) nativeCatalogY
static void OverworldWildSpawns_SetObjectLandingTile(FieldSystem *f,LocalMapObject *o,int x,int y) { (void)f;o->xCurr=x;o->yCurr=y;o->posVec[1]=nativeCatalogY;o->hInit=o->hPrev=o->hCurr=nativeCatalogY>>15; }
static BOOL OverworldWildSpawns_AcknowledgeSharedMotion(int slot,int flags,u16 applied,void *unused,u8 *phase) { (void)slot;(void)flags;(void)applied;(void)unused;*phase=0;return TRUE; }
'''
# Exact target-height decision from the real Timed function. Unused spawn-height native loop is retained.
def height(src):
 f=extract_function(src,'OverworldWildSpawns_StartPreparedCustomJumpCommandTimed','OverworldMotionDecision')
 begin=f.index('    if (flyIn');end=f.index('    if (flyIn)',begin+10)
 # The second if begins trajectory selection after the complete height selection.
 block=f[begin:end]
 return 'static s32 TargetY(OverworldWildSpawnState *state,int slot,LocalMapObject *object,BOOL flyIn,BOOL suppressHopStartSound,BOOL flatWalk,FieldSystem *fieldSystem,int targetX,int targetY,u8 direction) { OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(state);s32 targetBaseY,startBaseY=(s32)object->posVec[1];int objectX=object->xCurr,objectY=object->yCurr; (void)suppressHopStartSound;(void)flatWalk;(void)fieldSystem;(void)targetX;(void)targetY;(void)direction;(void)objectX;(void)objectY;(void)startBaseY;\n'+block+'return targetBaseY;}\n'
init=base.DRIVER[:base.DRIVER.index('static void Cleaned')]
init=base.replace(init,'player={.xCurr=80,.yCurr=80}','player={.xCurr=80,.yCurr=80,.flags=1}').replace('static FieldSystem field={&player};','static PlayerAvatar avatar={&player};static FieldSystem field={&avatar};')
init=base.replace(init,'objects[i]=(LocalMapObject){.xCurr=10+(int)i,.yCurr=10};','objects[i]=(LocalMapObject){.xCurr=10+(int)i,.yCurr=10,.flags=1};')
init=init.replace('state.spawns[i].active=1;','state.spawns[i].active=1;state.spawns[i].encounterGeneration=i+11;state.spawns[i].personality=100+i;nativeHandles[i]=Handle(i,i+1);nativePids[i]=100+i;')
init=init.replace('state.movementFieldSystem=&field;','gFieldSysPtr=&field;nativeCurrent=TRUE;helperReady=TRUE;flightCalls=0;state.movementFieldSystem=&field;')
DRIVER=r'''
static void ReleaseSetup(s32 y) { InitCase(TRUE);profile.chillState=OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR;profile.throwMaxRange=8;profile.throwWindupFrames=20;primitives.chillTarget=OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;objects[3].xCurr=10;objects[3].yCurr=6;conditions.frame.world.actors[2].x=10;conditions.frame.world.actors[2].y=6;objects[3].posVec[1]=y;objects[3].faceVec[1]=0x1000;objects[3].unk88[1]=0x2000;objects[1].posVec[1]=0;nativeCatalogY=0x50000; }
static void AimAndLaunch(s32 y) { ReleaseSetup(y);assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));assert(runtime.movementCustomJumpTargetBaseY[0]==y);assert(runtime.throwState.targets[0]&0x40);objects[3].posVec[1]=y+0x9000;objects[3].xCurr=9;conditions.frame.world.actors[2].x=9;assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));assert(flightCalls==1&&flightY==y);assert(runtime.movementCustomJumpTargetBaseY[1]==y);runtime.movementCustomJumpTargetX[1]=10;runtime.movementCustomJumpTargetY[1]=6;runtime.movementCustomJumpActive[1]=TRUE;runtime.movementCustomMotionModes[1]=OW_WILD_CUSTOM_MOTION_JUMP;assert(OverworldWildSpawns_CommitCustomJumpLanding(&state,1,&objects[1],0));assert((s32)objects[1].posVec[1]==y);runtime.movementCustomMotionModes[1]=OW_WILD_CUSTOM_MOTION_WALK;assert(OverworldWildSpawns_CommitCustomJumpLanding(&state,1,&objects[1],0));assert(objects[1].posVec[1]==(u32)nativeCatalogY);state.movementActorControlModes[1]=0;assert(OverworldWildSpawns_CommitCustomJumpLanding(&state,1,&objects[1],0));assert(objects[1].posVec[1]==(u32)nativeCatalogY);assert(TargetY(&state,1,&objects[1],FALSE,FALSE,FALSE,&field,10,6,0)==nativeCatalogY);free(blob); }
int main(void) {
 AimAndLaunch(0x1E000);AimAndLaunch(-0x10000);AimAndLaunch(0); /* elevated, lower, ground under roof */
 ReleaseSetup(0);helperReady=FALSE;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));assert(!(runtime.throwState.targets[0]&0x40)&&!flightCalls);free(blob);

 ReleaseSetup(0x1E000);conditions.frame.world.actors[2].actor.generation++;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));assert(!(runtime.throwState.targets[0]&0x40));free(blob);
 ReleaseSetup(0x1E000);state.spawns[3].encounterGeneration++;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));free(blob);
 ReleaseSetup(0x1E000);objects[3].flags=0;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));free(blob);
 ReleaseSetup(0);assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));conditions.frame.world.actors[0].actor.fieldEpoch++;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));assert(!flightCalls);free(blob);
 ReleaseSetup(0);state.spawns[3].object=NULL;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));free(blob);
 ReleaseSetup(0);state.spawns[3].active=FALSE;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));free(blob);
 ReleaseSetup(0);assert(OverworldTargetBindings_Clear(&conditions.bindings[0],&conditions.actors[0].subject,0,OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)==0);Bind(0,3,OVERWORLD_TARGET_BINDING_FRAMES,1);conditions.frame.world.frame++;assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));free(blob);
 ReleaseSetup(0);assert(OverworldTargetBindings_Clear(&conditions.bindings[0],&conditions.actors[0].subject,0,OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)==0);OverworldBehaviorConditionEntryResult admitted={0};admitted.active=admitted.triggered=admitted.conditionTrue=1;admitted.conditionId=12;admitted.applicationIndex=1;admitted.target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;conditions.frame.world.playerValid=1;conditions.frame.world.playerX=10;conditions.frame.world.playerY=6;player.xCurr=10;player.yCurr=6;player.posVec[1]=0x28000;assert(OverworldTargetBindings_CaptureEntry(&conditions.bindings[0],&conditions.frame.world,&conditions.actors[0].subject,&admitted,0,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0)==0);assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));assert(runtime.movementCustomJumpTargetBaseY[0]==0x28000);free(blob);
 puts("T26 actual Windup/launch/terminal owners: higher/lower/ground-under-roof/current Player/full identities pass");return 0;
}
'''
def fixture(src):
 pieces=[p,EXTRA,base.functions(base.HELPER,[('OverworldWildHelper_ClearPickupThrowState','u16')]),extract_function(src,'OverworldWildSpawns_ClearPendingNotices','void'),extract_function(src,'OverworldWildSpawns_ReleaseHeldActorControl','void'),base.functions(base.READ,[('OverworldCargoReadWild_Options','const OverworldWildBehaviorConditionOptions *')]),*[extract_function(src,n,t) for n,t in [('OverworldWildSpawns_PickupOptions','const OverworldWildBehaviorConditionOptions *'),('OverworldWildSpawns_RetireClearedThrowBindings','void'),('OverworldWildSpawns_ClearThrowRelations','void'),('OverworldWildSpawns_ClearThrowStateForSlot','void'),('OverworldWildSpawns_AbortThrow','void')]],base.functions(base.QUERY_OBSERVE,[('PlayerHealthThrow_Line','BOOL'),('OverworldThrowObservationQuery_Observe','u32')]),base.functions(base.OBSERVE,[('OverworldThrowObservation_Observe','u32')]),base.functions(base.HELD,[('OverworldThrowHeldWild_ReleaseCargo','BOOL')]).replace('static BOOL OverworldThrowHeldWild_ReleaseCargo(','BOOL OverworldThrowHeldWild_ReleaseCargo('),base.functions(base.HELD,[('OverworldThrowHeldWild_Run','BOOL')]).replace('static BOOL OverworldThrowHeldWild_Run(','BOOL OverworldThrowHeldWild_Run('),base.functions(base.READ,[('OverworldCargoReadWild_Observe','u32')]),read,height(src)]
 if 'OverworldWildSpawns_GetThrowBindingBody(' in src:pieces.append(extract_function(re.sub(r'const LocalMapObject \* __attribute__\(\([^;{]*?\)\)\s*OverworldWildSpawns_GetThrowBindingBody', 'LocalMapObjectPtr OverworldWildSpawns_GetThrowBindingBody', src),'OverworldWildSpawns_GetThrowBindingBody','LocalMapObjectPtr'))
 pieces.extend([extract_function(src,'OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand','BOOL'),extract_function(src,'OverworldWildSpawns_CommitCustomJumpLanding','BOOL'),init,DRIVER])
 return '\n'.join(pieces)
def run(src,stem):
 OUT.mkdir(parents=True,exist_ok=True)
 unit=OUT/(stem+'.c');unit.write_text(fixture(src));(OUT/'host_types.h').write_text(base.HOST_TYPES)
 cmd=[*shlex.split(os.environ.get('HOST_CC','cc')),'-std=gnu11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-Wno-pointer-to-int-cast','-DOVERWORLD_BEHAVIOR_HOST','-DOVERWORLD_ACTOR_SYSTEM_HOST','-include',str(OUT/'host_types.h'),'-I',str(ROOT/'include'),'-iquote',str(ROOT/'lib/overworld'),str(unit),str(ROOT/'lib/overworld/overworld_behavior_conditions.c'),str(ROOT/'lib/overworld/overworld_vision.c'),str(ROOT/'lib/overworld/overworld_behavior_condition_runtime.c'),str(ROOT/'lib/overworld/overworld_target_bindings.c'),str(ROOT/'lib/overworld/overworld_pickup_route.c'),str(ROOT/'data/OverworldWildBehaviorData.c'),'-o',str(OUT/stem)]
 c=subprocess.run(cmd,text=True,capture_output=True);(OUT/(stem+'-compile.log')).write_text(c.stdout+c.stderr)
 if c.returncode: print(c.stderr);raise SystemExit(c.returncode)
 r=subprocess.run([str(OUT/stem)],text=True,capture_output=True);(OUT/(stem+'.log')).write_text(r.stdout+r.stderr);return {'sourceSha':hashlib.sha256(src.encode()).hexdigest(),'command':cmd,'exitCode':r.returncode,'stdout':r.stdout,'stderr':r.stderr}
import unittest

class ThrowTargetHeightTests(unittest.TestCase):
 def test_actual_height_aim_launch_and_terminal_owners(self):
  result=run(WILD.read_text(),'height-current')
  self.assertEqual(result['exitCode'],0,result['stdout']+result['stderr'])

 def test_helper_loaded_admission_precedes_relocated_body(self):
  source=WILD.read_text()
  seam='if (OverworldWildSpawns_GetHelperOverlayEntry() == NULL) return FALSE;'
  self.assertEqual(source.count(seam),1)
  result=run(source.replace(seam,''),'height-unloaded-helper-fault')
  self.assertNotEqual(result['exitCode'],0)
  self.assertIn('!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand',result['stderr'])

 def test_catalog_height_cannot_replace_authenticated_throw_height(self):
  source=WILD.read_text()
  seam='if (flyIn || suppressHopStartSound == OW_WILD_SPAWNER_CUSTOM_MOTION_THROW_FLAG)'
  self.assertEqual(source.count(seam),1)
  result=run(source.replace(seam,'if (flyIn)'),'height-catalog-fault')
  self.assertNotEqual(result['exitCode'],0)
  self.assertIn('flightY==y',result['stderr'])

 def test_current_native_spawn_guard_is_required(self):
  source=WILD.read_text()
  seam='|| !OverworldWildSpawns_IsCurrentSpawnObject(field, spawn)) return NULL;'
  self.assertEqual(source.count(seam),1)
  result=run(source.replace(seam,') return NULL;'),'height-current-spawn-fault')
  self.assertNotEqual(result['exitCode'],0)
  self.assertIn('!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand',result['stderr'])

 def test_terminal_held_flight_height_is_not_resnapped(self):
  source=WILD.read_text()
  seam='|| ((runtime->throwState.targetMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0'
  self.assertEqual(source.count(seam),1)
  result=run(source.replace(seam,'|| ((runtime->throwState.targetMask & 0) != 0'),'height-terminal-fault')
  self.assertNotEqual(result['exitCode'],0)
  self.assertIn('objects[1].posVec[1]==y',result['stderr'])

if __name__=='__main__':unittest.main()

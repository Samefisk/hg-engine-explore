#!/usr/bin/env python3
"""Run actual NORMALIZE_SLOT, REBIND, surface height and pass-through on the host.

Only the selected production branches are extracted, unchanged. Identity lookup,
profile queries and shadow work are boundary stubs; this is not game proof.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
HELPER = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"


def block(source, marker):
    if source.count(marker) != 1:
        raise ValueError("production extraction boundary changed: " + marker)
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 1
    for end in range(brace + 1, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            return source[start:end + 1]
    raise ValueError("unterminated production block")


def sources():
    wild, helper = WILD.read_text(), HELPER.read_text()
    rebind = block(wild, "if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND)")
    start = helper.index("    if (call->operation != OW_WILD_HELPER_PRESENTATION_NORMALIZE_SLOT)")
    end = helper.index("\nstatic void OverworldWildHelper_SyncCarriedThrowTarget", start)
    normalize = helper[start:end].rstrip()
    if not normalize.endswith("}"):
        raise ValueError("NORMALIZE_SLOT tail boundary changed")
    setter = block(wild, "OverworldWildSpawns_SetObjectPassThrough(LocalMapObject *object, BOOL passThrough)")
    policy = block(wild, "static void OverworldWildSpawns_ApplySpawnPassThroughFlag(\n").removeprefix("static void ")
    height = block(wild, "static void __attribute__((noinline)) OverworldWildSpawns_ApplySurfaceHeight(\n")
    constants = []
    for filename, names in (
        ("include/map_events_internal.h", ("MAPOBJECTFLAG_UNK18", "MAPOBJECTFLAG_UNK15", "BIT_VANISH")),
        ("include/overworld_wild_spawns_internal.h", ("OW_WILD_LAND_SURF_MAX_SPAWNS", "OW_WILD_HEADBUTT_MAX_SPAWNS",
             "OW_WILD_FISH_MAX_SPAWNS", "OW_WILD_HEADBUTT_SLOT_START", "OW_WILD_FISH_SLOT_START",
             "OW_WILD_FOLLOWER_SLOT", "OW_WILD_MAX_SPAWNS")),
        ("include/overworld_wild_behavior_data.h", ("OW_WILD_SURFACE_TYPE_ROOFTOP",
             "OW_WILD_SURFACE_TYPE_SIGNPOST", "OW_WILD_SURFACE_TYPE_CANOPY",
             "OW_WILD_SURFACE_ID_NATIVE_CANOPY", "OW_WILD_SURFACE_ID_NATIVE_GROUND")),
    ):
        source = (ROOT / filename).read_text()
        for name in names:
            matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", source, re.M)
            if not matches:
                values = re.findall(r"^\s*" + name + r"\s*=\s*([^,\n]+),", source, re.M)
                matches = ["#define " + name + " " + value for value in values]
            if len(matches) != 1:
                raise ValueError("production constant missing: " + name)
            constants.append(matches[0])
    query = block(wild, "static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(\n")
    field = (ROOT / "lib/overworld/overworld_query_code_addon_field.c").read_text()
    current = block(field, "OverworldQueryCodeAddonField_AcquireCurrent(\n")
    return "\n".join(constants), normalize, setter, policy, height, rebind, current, query


FIXTURE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int BOOL; typedef uint32_t u32; typedef int32_t s32;
typedef uint8_t u8; typedef uint16_t u16;
#define TRUE 1
#define FALSE 0
#define OW_WILD_HELPER_PRESENTATION_NORMALIZE_SLOT 4
#define OVERWORLD_ACTOR_TRANSITION_WORK_REBIND 2
#define OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD 3
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
#define OW_WILD_BEHAVIOR_CLASS_PICKED_UP 9
#define OW_WILD_BEHAVIOR_CLASS_DEFAULT 0
typedef struct { u32 value; } OverworldActorHandle;
typedef struct { u32 flags; int xCurr,yCurr,xInit,yInit,xPrev,yPrev; u32 posVec[3];
    int faceVec[3],unk88[3],unk94[3],unkC,hInit,hPrev,hCurr; } LocalMapObject;
typedef struct { s32 height; u16 surfaceId; u8 surfaceType,nodeId; } OverworldWildSurfaceHit;
typedef struct { LocalMapObject *objects; } MapObjectMan;
typedef struct { int mapId; } Location;
typedef struct {int unused;} OverworldQueryCodeAddonEntry;
typedef struct {int unused;} OverworldQueryCodeAddonOps;
typedef struct { Location *location; MapObjectMan *mapObjectMan; } FieldSystem;
typedef struct { int movementNativeShadowRestorePending; } OverworldWildOverlayRuntimeState;
typedef struct { int unused; } OverworldWildBehaviorProfile;
typedef struct { LocalMapObject *object; int active,mapId; } Spawn;
typedef struct { Spawn spawns[10]; int mapGeneration,mapId,pendingSlot,movementQueuedBattleSlot;
    int pendingMapGeneration,pendingEncounterGeneration,battleGraceSteps,presentationRestorePending;
    MapObjectMan *mapObjectMan; LocalMapObject *mapObjects; FieldSystem *movementFieldSystem;
    OverworldWildOverlayRuntimeState *movementRuntimeState; int movementBehaviorClasses[10];
    int movementTeleportFlickerTimers[10]; u8 movementActorControlModes[10]; } OverworldWildSpawnState;
typedef struct { int work,disposition,retainedActorMask,currentMapId,nextMapGeneration,nextFieldEpoch; } OverworldActorTransitionCall;
typedef struct { int operation; } PresentationCall;
#define OW_WILD_RUNTIME(s) ((s)->movementRuntimeState)
static int teleport, teleportActive, onPlayer, identityOk=1, normalizeOk=1, shadows;
static int exactObjectOk=1, surfaceKnown, surfaceQueries, queryX, queryY;
static int addonReady=1, addonCalls, preparedCalls;
static int contextReads,gateReady=1,fieldReady=1,fieldLoaded=1;
static u32 residentContext=0x00030003;
static u32 GetContext(void) { contextReads++;return residentContext; }
const struct {u32 (*getContext)(void);} compat={GetContext};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compat)
#define OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(v) ((u16)(v))
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(v) ((u16)((v)>>16))
#define OVERLAY_FIELD 1
static BOOL IsOverlayLoaded(int id) {(void)id;return fieldLoaded;}
static BOOL sub_0203DF8C(FieldSystem *field) {(void)field;return fieldReady;}
static const void *Gate(void) {return gateReady?&compat:NULL;}
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE Gate
static struct {u8 residentDataCleaned;} sOverworldWildFlags;
static OverworldWildSpawnState *sOverworldWildLastState;
static const OverworldQueryCodeAddonOps sOverworldWildQueryCodeOps={0};
static OverworldQueryCodeAddonEntry addonEntry;
const OverworldQueryCodeAddonEntry *OverworldQueryCodeAddonField_Acquire(FieldSystem *field,
 u16 epoch,u16 generation,const OverworldQueryCodeAddonOps *ops,void *query)
{ (void)field;(void)query;(void)ops;
 if (((u32)epoch|((u32)generation<<16))!=residentContext) return NULL;
 addonCalls++;return addonReady?&addonEntry:NULL; }
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_CURRENT OverworldQueryCodeAddonField_AcquireCurrent
static OverworldWildSurfaceHit surface;
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *hit)
{ (void)f;surfaceQueries++;queryX=x;queryY=y;*hit=surface;return surfaceKnown; }
static BOOL OverworldWildSpawns_SlotUsesTeleportMovement(OverworldWildSpawnState *s,int slot)
{ (void)s; (void)slot; return teleport; }
static BOOL OverworldWildSpawns_IsTeleportMovementActive(OverworldWildSpawnState *s,int slot)
{ (void)s; (void)slot; return teleportActive; }
static BOOL OverworldWildSpawns_IsObjectOnPlayerTile(FieldSystem *f,LocalMapObject *o)
{ (void)f; (void)o; return onPlayer; }
static BOOL OverworldWildHelper_IsPresentationContextCurrent(FieldSystem *f,OverworldWildSpawnState *s)
{ (void)f; (void)s; return normalizeOk; }
static BOOL OverworldWildHelper_IsExactObject(FieldSystem *f,OverworldWildSpawnState *s,int slot)
{ (void)f; return exactObjectOk && s->spawns[slot].object != NULL; }
static int MapObject_GetCurrentX(LocalMapObject *o) { return o->xCurr; }
static int MapObject_GetCurrentY(LocalMapObject *o) { return o->yCurr; }
static void MapObject_ClearBits(LocalMapObject *o,u32 bits) { o->flags &= ~bits; }
static void OverworldWildSpawns_ClearObjectFlags(LocalMapObject *o,u32 bits) { o->flags &= ~bits; }
static void *OverworldWildSpawns_RetainedMaskNamesActiveSpawns(OverworldWildSpawnState *s,int mask)
{ (void)mask; return s; }
static BOOL OverworldWildSpawns_RebindRetainedSpawnObject(FieldSystem *f,OverworldWildSpawnState *s,
 const OverworldActorTransitionCall *c,int slot,OverworldActorHandle *handle)
{ (void)f;(void)s;(void)c;(void)slot;handle->value=1;return identityOk; }
static BOOL OverworldWildSpawns_PrepareConditionsForSlot(OverworldWildSpawnState *s,int slot,
 const OverworldActorHandle *handle,const OverworldWildBehaviorProfile *profile)
{ (void)s;(void)slot;(void)handle;(void)profile;
  if (!addonReady || !addonCalls) { fprintf(stderr,"condition prepare preceded Query admission\n"); return FALSE; }
  preparedCalls++;return TRUE; }
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
 OverworldWildSpawnState *s,int slot,OverworldWildBehaviorProfile *profile,void *primitives)
{ (void)s;(void)slot;(void)primitives;memset(profile,0,sizeof(*profile)); }
static void OverworldWildSpawns_ReconcileNativeShadow(FieldSystem *f,LocalMapObject *o)
{ (void)f;(void)o;shadows++; }
'''

DRIVER = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"rebind pass-through failed line %d: %s\n",__LINE__,#x); return 1; } } while(0)
int main(void) {
 CHECK(!OverworldWildSpawns_QueryAddon(NULL,NULL));
 unsigned cases=0;
 const int slots[]={7,0};
 for (unsigned role=0;role<2;role++) for(int mode=0;mode<5;mode++) for(int flags=1;flags<=7;flags+=2) {
  int slot=slots[role];
  LocalMapObject object={0}; MapObjectMan manager={&object}; Location location={67};
  FieldSystem field={&location,&manager}; OverworldWildOverlayRuntimeState runtime={1};
  OverworldWildSpawnState state={0}; OverworldActorTransitionCall call={2,0,1<<slot,67,3,3};
  state.spawns[slot]=(Spawn){&object,flags,33}; state.movementRuntimeState=&runtime;
  state.movementFieldSystem=&field;
  object.xCurr=9;object.yCurr=11;object.posVec[1]=0x12340;
  object.flags=1|BIT_VANISH|MAPOBJECTFLAG_UNK15|MAPOBJECTFLAG_UNK18;
  teleport=mode!=0;teleportActive=mode==1;onPlayer=mode==3;
  state.movementTeleportFlickerTimers[slot]=mode==2;
  BOOL expected=slot==7 || (mode>=1 && mode<=3);
  OverworldWildSpawns_ApplySpawnPassThroughFlag(&state,slot,&object);
  CHECK(!!(object.flags&MAPOBJECTFLAG_UNK18)==expected);
  object.flags|=BIT_VANISH|MAPOBJECTFLAG_UNK18;
  addonCalls=preparedCalls=0;
  CHECK(Rebind(&field,&state,&call));CHECK(addonCalls==1 && preparedCalls==1);
  if (!!(object.flags&MAPOBJECTFLAG_UNK18)!=expected)
   fprintf(stderr,"case role=%s slot=%d mode=%d sourceActive=%d expectedPassThrough=%d actual=%d\n",
    slot==7?"FOLLOWER":"WILD",slot,mode,flags,expected,!!(object.flags&MAPOBJECTFLAG_UNK18));
  CHECK(!!(object.flags&MAPOBJECTFLAG_UNK18)==expected);
  CHECK(!(object.flags&(BIT_VANISH|MAPOBJECTFLAG_UNK15)));
  CHECK(object.posVec[0]==9*0x10000+0x8000 && object.posVec[2]==11*0x10000+0x8000);
  CHECK(object.posVec[1]==0x12340 && object.unkC==67 && state.mapGeneration==3);
  CHECK(state.spawns[slot].active==flags && state.spawns[slot].object==&object);
  CHECK(Rebind(&field,&state,&call));
  CHECK(!!(object.flags&MAPOBJECTFLAG_UNK18)==expected);
  identityOk=0;CHECK(!Rebind(&field,&state,&call));identityOk=1;
  normalizeOk=0;CHECK(!Rebind(&field,&state,&call));normalizeOk=1;
  cases++;
 }
 /* Failed admission returns FALSE before mutating the retained actor or
  * preparing conditions. The existing Field driver owns DISCARD fallback. */
 {
  LocalMapObject object={0};MapObjectMan manager={&object};Location location={33};
  FieldSystem field={&location,&manager};OverworldWildSpawnState state={0};
  OverworldActorTransitionCall call={2,0,1<<7,33,3,3};
  state.spawns[7]=(Spawn){&object,1,67};
  OverworldWildSpawnState before=state;addonReady=0;addonCalls=preparedCalls=0;
  CHECK(!Rebind(&field,&state,&call));CHECK(addonCalls==1 && preparedCalls==0);
  CHECK(!memcmp(&state,&before,sizeof(state)));addonReady=1;
  /* A stale next-context call, including no retained actors, cannot drain
   * the current Query or publish its call-supplied map generation. */
  for(int mask=0;mask<=1;mask++) {
   call.retainedActorMask=mask?1<<7:0;
   for(int invalid=0;invalid<4;invalid++) {
    call.nextFieldEpoch=invalid==0?4:invalid==1||invalid==3?0:3;
    call.nextMapGeneration=invalid==2||invalid==3?0:3;
    contextReads=addonCalls=preparedCalls=0;
    CHECK(!Rebind(&field,&state,&call));CHECK(!addonCalls && !preparedCalls);
    CHECK(contextReads==(invalid==0));
    CHECK(!memcmp(&state,&before,sizeof(state)));
   }
   call.nextFieldEpoch=call.nextMapGeneration=3;
   for(int invalid=0;invalid<3;invalid++) {
    fieldLoaded=invalid!=0;fieldReady=invalid!=1;gateReady=invalid!=2;
    contextReads=addonCalls=preparedCalls=0;
    CHECK(!Rebind(&field,&state,&call));CHECK(!contextReads&&!addonCalls&&!preparedCalls);
    CHECK(!memcmp(&state,&before,sizeof(state)));
   }
   fieldLoaded=fieldReady=gateReady=1;
  }
 }
 /* Native red: canceled Fly In was moved to566403 but retained its202112
  * start height; authenticated roof support is261456. Sign control uses the
  * measured230912 support. Unknown, native-ground and relative canopy must
  * retain their existing native height; they are not absolute surfaces. */
 for(int mode=0;mode<5;mode++) {
  LocalMapObject object={0}; MapObjectMan manager={&object}; Location location={33};
  FieldSystem field={&location,&manager}; OverworldWildOverlayRuntimeState runtime={1};
  OverworldWildSpawnState state={0}; OverworldActorTransitionCall call={2,0,1,33,5,3};
  residentContext=0x00050003;
  state.spawns[0]=(Spawn){&object,1,67};state.movementRuntimeState=&runtime;
  state.movementFieldSystem=&field;object.xCurr=566;object.yCurr=403;
  object.posVec[1]=202112;object.hInit=object.hPrev=object.hCurr=6;
  surfaceKnown=mode!=2;surfaceQueries=0;teleport=teleportActive=onPlayer=0;
  surface=(OverworldWildSurfaceHit){261456,9303,OW_WILD_SURFACE_TYPE_ROOFTOP,0};
  if(mode==1) surface=(OverworldWildSurfaceHit){230912,9313,OW_WILD_SURFACE_TYPE_SIGNPOST,0};
  if(mode==3) surface.surfaceId=OW_WILD_SURFACE_ID_NATIVE_GROUND;
  if(mode==4) surface=(OverworldWildSurfaceHit){65536,OW_WILD_SURFACE_ID_NATIVE_CANOPY,OW_WILD_SURFACE_TYPE_CANOPY,0};
  CHECK(Rebind(&field,&state,&call));
  s32 expected=mode<2?surface.height:202112;
  CHECK(surfaceQueries==1 && queryX==566 && queryY==403);
  CHECK((s32)object.posVec[1]==expected);
  CHECK(object.hInit==(expected>>15) && object.hPrev==object.hInit && object.hCurr==object.hInit);
  CHECK(state.spawns[0].object==&object && state.spawns[0].active==1);
  CHECK(Rebind(&field,&state,&call));CHECK((s32)object.posVec[1]==expected);
  /* No height write/query may occur for a stale actor, context or object. */
  for(int invalid=0;invalid<3;invalid++) {
   LocalMapObject before=object;surfaceQueries=0;
   identityOk=invalid!=0;normalizeOk=invalid!=1;exactObjectOk=invalid!=2;
   CHECK(!Rebind(&field,&state,&call));CHECK(!surfaceQueries);
   CHECK(!memcmp(&before,&object,sizeof(object)));
   identityOk=normalizeOk=exactObjectOk=1;
  }
  cases++;
 }
 /* Normal fresh landing still adds the relative canopy offset once. */
 LocalMapObject canopy={0};canopy.posVec[1]=65536;surfaceKnown=1;
 surface=(OverworldWildSurfaceHit){32768,OW_WILD_SURFACE_ID_NATIVE_CANOPY,OW_WILD_SURFACE_TYPE_CANOPY,0};
 OverworldWildSpawns_ApplySurfaceHeight(NULL,&canopy,9,11,FALSE);
 CHECK(canopy.posVec[1]==98304 && canopy.hInit==3 && canopy.hPrev==3 && canopy.hCurr==3);
 printf("PASS actual NORMALIZE_SLOT/REBIND: %u cases, absolute surface restoration and identity controls\n",cases);return 0;
}
'''


def harness():
    constants, normalize, setter, policy, height, rebind, current, query = sources()
    return (FIXTURE + constants + "\nconst OverworldQueryCodeAddonEntry *" + current + "\n" + query + "\nstatic void " + setter + "\nstatic void " + policy
            + "\n" + height
            + "\nstatic BOOL Normalize(FieldSystem *fieldSystem,OverworldWildSpawnState *state,int operation,int slot) {\n"
            + "PresentationCall request={operation}; const PresentationCall *call=&request; LocalMapObject *object; int x,y;\n"
            + normalize
            + "\nstatic BOOL OverworldWildSpawns_ApplyPresentationCommand(FieldSystem *f,OverworldWildSpawnState *s,int op,u8 slot) { return Normalize(f,s,op,slot); }\n"
            + "static BOOL Rebind(FieldSystem *fieldSystem,OverworldWildSpawnState *state,const OverworldActorTransitionCall *call) { int i;\n"
            + rebind + "\nreturn FALSE; }\n" + DRIVER)


def execute(source):
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("host C compiler required")
    with tempfile.TemporaryDirectory(prefix="rebind-policy-") as folder:
        path = Path(folder)
        (path / "check.c").write_text(source)
        subprocess.run([compiler,"-std=c99","-Wall","-Wextra","-Werror",str(path / "check.c"),"-o",str(path / "check")],
                       check=True,capture_output=True,text=True,timeout=30)
        return subprocess.run([str(path / "check")],capture_output=True,text=True,timeout=5)


def main():
    source = harness()
    result = execute(source)
    print(result.stdout + result.stderr, end="")
    if result.returncode:
        return result.returncode
    call = "OverworldWildSpawns_ApplySurfaceHeight(\n                fieldSystem, object, object->xCurr, object->yCurr, TRUE);"
    if source.count(call) != 1:
        raise ValueError("retained height call changed")
    mutant = execute(source.replace(call, "/* omitted retained height restoration */"))
    if mutant.returncode == 0:
        raise AssertionError("height regression accepted missing retained restoration")
    print("PASS removal control rejects the old retained-flight height")
    admission = "OverworldWildSpawns_QueryAddon(fieldSystem, call) == NULL"
    if source.count(admission) != 1:
        raise ValueError("Query transition admission seam changed")
    missing_admission = execute(source.replace(admission, "FALSE"))
    if missing_admission.returncode == 0:
        raise AssertionError("rebind accepted condition preparation without current Query admission")
    print("PASS removal control rejects condition preparation before Query admission")
    context_guard = ("    if(transition!=NULL && context!=((u32)transition->nextFieldEpoch"
                     "\n        | ((u32)transition->nextMapGeneration<<16))) return NULL;")
    if source.count(context_guard) != 1:
        raise ValueError("Query transition context seam changed")
    if execute(source.replace(context_guard, "")).returncode == 0:
        raise AssertionError("rebind admitted a stale paired context before Query drain")
    print("PASS removal control rejects stale-context Query admission")
    nonzero = "        || transition->nextFieldEpoch==0 || transition->nextMapGeneration==0"
    if source.count(nonzero)!=1 or execute(source.replace(nonzero,"" )).returncode==0:
        raise AssertionError("rebind accepted zero transition context")
    print("PASS removal control rejects zero transition context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

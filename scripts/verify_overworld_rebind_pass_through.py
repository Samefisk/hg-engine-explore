#!/usr/bin/env python3
"""Run actual NORMALIZE_SLOT, REBIND and pass-through policy on the host.

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
    constants = []
    for filename, names in (
        ("include/map_events_internal.h", ("MAPOBJECTFLAG_UNK18", "MAPOBJECTFLAG_UNK15", "BIT_VANISH")),
        ("include/overworld_wild_spawns_internal.h", ("OW_WILD_LAND_SURF_MAX_SPAWNS", "OW_WILD_HEADBUTT_MAX_SPAWNS",
             "OW_WILD_FISH_MAX_SPAWNS", "OW_WILD_HEADBUTT_SLOT_START", "OW_WILD_FISH_SLOT_START",
             "OW_WILD_FOLLOWER_SLOT", "OW_WILD_MAX_SPAWNS")),
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
    return "\n".join(constants), normalize, setter, policy, rebind


FIXTURE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int BOOL; typedef uint32_t u32; typedef int32_t s32;
typedef uint8_t u8;
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
    int faceVec[3],unk88[3],unk94[3],unkC; } LocalMapObject;
typedef struct { LocalMapObject *objects; } MapObjectMan;
typedef struct { int mapId; } Location;
typedef struct { Location *location; MapObjectMan *mapObjectMan; } FieldSystem;
typedef struct { int movementNativeShadowRestorePending; } OverworldWildOverlayRuntimeState;
typedef struct { int unused; } OverworldWildBehaviorProfile;
typedef struct { LocalMapObject *object; int active,mapId; } Spawn;
typedef struct { Spawn spawns[10]; int mapGeneration,mapId,pendingSlot,movementQueuedBattleSlot;
    int pendingMapGeneration,pendingEncounterGeneration,battleGraceSteps,presentationRestorePending;
    MapObjectMan *mapObjectMan; LocalMapObject *mapObjects; FieldSystem *movementFieldSystem;
    OverworldWildOverlayRuntimeState *movementRuntimeState; int movementBehaviorClasses[10];
    int movementTeleportFlickerTimers[10]; u8 movementActorControlModes[10]; } OverworldWildSpawnState;
typedef struct { int work,disposition,retainedActorMask,currentMapId,nextMapGeneration; } OverworldActorTransitionCall;
typedef struct { int operation; } PresentationCall;
#define OW_WILD_RUNTIME(s) ((s)->movementRuntimeState)
static int teleport, teleportActive, onPlayer, identityOk=1, normalizeOk=1, shadows;
static BOOL OverworldWildSpawns_SlotUsesTeleportMovement(OverworldWildSpawnState *s,int slot)
{ (void)s; (void)slot; return teleport; }
static BOOL OverworldWildSpawns_IsTeleportMovementActive(OverworldWildSpawnState *s,int slot)
{ (void)s; (void)slot; return teleportActive; }
static BOOL OverworldWildSpawns_IsObjectOnPlayerTile(FieldSystem *f,LocalMapObject *o)
{ (void)f; (void)o; return onPlayer; }
static BOOL OverworldWildHelper_IsPresentationContextCurrent(FieldSystem *f,OverworldWildSpawnState *s)
{ (void)f; (void)s; return normalizeOk; }
static BOOL OverworldWildHelper_IsExactObject(FieldSystem *f,OverworldWildSpawnState *s,int slot)
{ (void)f; return s->spawns[slot].object != NULL; }
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
{ (void)s;(void)slot;(void)handle;(void)profile;return TRUE; }
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
 OverworldWildSpawnState *s,int slot,OverworldWildBehaviorProfile *profile,void *primitives)
{ (void)s;(void)slot;(void)primitives;memset(profile,0,sizeof(*profile)); }
static void OverworldWildSpawns_ReconcileNativeShadow(FieldSystem *f,LocalMapObject *o)
{ (void)f;(void)o;shadows++; }
'''

DRIVER = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"rebind pass-through failed line %d: %s\n",__LINE__,#x); return 1; } } while(0)
int main(void) {
 unsigned cases=0;
 const int slots[]={7,0};
 for (unsigned role=0;role<2;role++) for(int mode=0;mode<5;mode++) for(int flags=1;flags<=7;flags+=2) {
  int slot=slots[role];
  LocalMapObject object={0}; MapObjectMan manager={&object}; Location location={67};
  FieldSystem field={&location,&manager}; OverworldWildOverlayRuntimeState runtime={1};
  OverworldWildSpawnState state={0}; OverworldActorTransitionCall call={2,0,1<<slot,67,3};
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
  CHECK(Rebind(&field,&state,&call));
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
 printf("PASS actual NORMALIZE_SLOT/REBIND pass-through: %u cases\n",cases);return 0;
}
'''


def harness():
    constants, normalize, setter, policy, rebind = sources()
    return (FIXTURE + constants + "\nstatic void " + setter + "\nstatic void " + policy
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
    result = execute(harness())
    print(result.stdout + result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

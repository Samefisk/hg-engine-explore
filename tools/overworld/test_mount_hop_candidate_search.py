"""Actual mounted Hop selection: adjacent raised support, then long fallback.

The obsolete lateral-search owner is gone. Extract the current controller's
selection block and its real target/trajectory adapters; stub physical replies.
This is host policy proof, not a native landing or rendered-motion witness.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest
from scripts.verify_overworld_mount import function_body

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"
ACTION = ROOT / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c"

PRELUDE = r'''
#include <stdio.h>
#include <string.h>
typedef unsigned char u8; typedef unsigned short u16; typedef short s16;
typedef unsigned int u32; typedef int s32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOUNT_WALK_END_CHAIN_HOP 4
#define OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION 1
#define OVERWORLD_MOUNT_ACTION_CHAIN_FORWARD_TARGET 1
#define OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY 2
#define OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY 1
#define OVERWORLD_MOTION_DECISION_ACCEPTED 0
#define OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION 1
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER 2
#define OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
typedef struct { u8 chillAction,hopMinDistance,hopMaxDistance; u16 chillAllowedTerrainMask; } OverworldWildBehaviorProfileData;
typedef struct { int xCurr,yCurr; s32 posVec[3]; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR;
typedef struct { FIELD_PLAYER_AVATAR *playerAvatar; } FieldSystem;
typedef struct { FieldSystem *fieldSystem; void *surfaceCatalog;
 struct {OverworldWildBehaviorProfileData profile;} snapshot;
 s16 motionStartX,motionStartY,motionTargetX,motionTargetY;
 s32 motionStartBaseY,motionTargetBaseY; u8 walkEndState;
} OverworldMountRuntimeState;
typedef struct {u16 version,size;u8 operation,direction,action;OverworldMountRuntimeState *state;FIELD_PLAYER_AVATAR *avatar;u32 *trajectory;} OverworldMountActionCall;
typedef struct {int operation,spotState;const OverworldWildBehaviorProfileData *lane;FieldSystem *fieldSystem;void *surfaceCatalog;LocalMapObject *object;s32 startBaseY,targetBaseY;s16 startX,startY,targetX,targetY;u8 distance;u32 trajectory;} OverworldActorHopPlanCall;
static OverworldMountRuntimeState sOverworldMountState;
static LocalMapObject object;static FIELD_PLAYER_AVATAR avatarObject={&object};static FIELD_PLAYER_AVATAR *avatar=&avatarObject;static FieldSystem field={&avatarObject};
static int raised,landingBlock,arcBlock,farBlock,bad,landCount,heightCount,arcCount;
static int distances[32];static u8 direction;
static int OverworldWalkDirectionPolicy_DeltaX(u8 d){static const int v[8]={0,0,-1,1,-1,1,-1,1};return v[d];}
static int OverworldWalkDirectionPolicy_DeltaY(u8 d){static const int v[8]={-1,1,0,0,-1,-1,1,1};return v[d];}
static int Distance(int x,int y){int a=x-object.xCurr,b=y-object.yCurr;if(a<0)a=-a;if(b<0)b=-b;return a>b?a:b;}
static BOOL Landing(u16 version,int slot,FieldSystem *f,u16 mask,int x,int y,int tx,int ty){
 int d=Distance(x,y);if(version!=1||slot!=7||f!=&field||x!=tx||y!=ty||d<1||d>6||landCount>=32)bad=1;
 if((mask&~0x8002u)!=sOverworldMountState.snapshot.profile.chillAllowedTerrainMask)bad=1;
 if(((mask&0x8000u)!=0)!=(direction>=4))bad=1;
 distances[landCount++]=d;
 return !(d==1&&landingBlock)&&!(d==farBlock)&&((mask&(d==1&&raised?4:1))!=0);
}
static struct {BOOL(*validateHopLanding)(u16,int,FieldSystem*,u16,int,int,int,int);} wild={Landing};
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY (&wild)
static s32 Height(FieldSystem *f,void*c,LocalMapObject *o,int x,int y){
 (void)c; if(f!=&field||o!=&object)bad=1;heightCount++;return o->posVec[1]+(Distance(x,y)==1?raised:0);
}
static struct {s32(*getGroundBaseY)(FieldSystem*,void*,LocalMapObject*,int,int);} runtime={Height};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtime)
static int OverworldMountAction_RequestHopPlan(OverworldActorHopPlanCall *c){
 int d=Distance(c->targetX,c->targetY);arcCount++;
 if(c->operation!=1||c->spotState||c->object!=&object||c->fieldSystem!=&field||c->lane!=&sOverworldMountState.snapshot.profile||c->distance!=d||c->startX!=object.xCurr||c->startY!=object.yCurr||c->startBaseY!=object.posVec[1]||c->targetBaseY!=sOverworldMountState.motionTargetBaseY)bad=1;
 if(d==1&&arcBlock)return 2;c->trajectory=(16u<<16)|(7u*d+2);return 0;
}
static u8 Dispatch(OverworldMountActionCall *);
#define OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH Dispatch
'''

DRIVER = r'''
#define CHECK(v) do{if(!(v)){fprintf(stderr,"line%d %s target=%d,%d land=%d height=%d arc=%d bad=%d\n",__LINE__,#v,sOverworldMountState.motionTargetX,sOverworldMountState.motionTargetY,landCount,heightCount,arcCount,bad);return 1;}}while(0)
static void Reset(void){memset(&sOverworldMountState,0,sizeof(sOverworldMountState));object=(LocalMapObject){561,364,{0,131072,0}};sOverworldMountState.fieldSystem=&field;sOverworldMountState.snapshot.profile=(OverworldWildBehaviorProfileData){2,1,6,5};raised=202112;landingBlock=arcBlock=farBlock=bad=landCount=heightCount=arcCount=0;direction=3;}
static int Chosen(void){return Distance(sOverworldMountState.motionTargetX,sOverworldMountState.motionTargetY);}
int main(int argc,char **argv){if(argc!=2)return 2;Reset();
 if(!strcmp(argv[1],"raised")){for(direction=0;direction<8;direction++){landCount=heightCount=arcCount=0;CHECK(SelectHop());CHECK(Chosen()==1&&landCount==1&&heightCount==1&&arcCount==1&&!bad);CHECK(sOverworldMountState.motionTargetBaseY==333184);}}
 else if(!strcmp(argv[1],"flat")){raised=0;CHECK(SelectHop());CHECK(Chosen()==6&&landCount==2&&arcCount==1&&!bad);CHECK(distances[0]==1&&distances[1]==6);}
 else if(!strcmp(argv[1],"lower")){raised=-65536;CHECK(SelectHop());CHECK(Chosen()==6&&arcCount==1&&!bad);}
 else if(!strcmp(argv[1],"landing-blocked")){landingBlock=1;CHECK(SelectHop());CHECK(Chosen()==6&&heightCount==1&&arcCount==1&&!bad);}
 else if(!strcmp(argv[1],"arc-blocked")){arcBlock=1;CHECK(SelectHop());CHECK(Chosen()==6&&arcCount==2&&!bad);}
 else if(!strcmp(argv[1],"forbidden")){sOverworldMountState.snapshot.profile.chillAllowedTerrainMask=1;CHECK(SelectHop());CHECK(Chosen()==6&&heightCount==1&&arcCount==1&&!bad);}
 else if(!strcmp(argv[1],"fallback-order")){landingBlock=1;farBlock=6;CHECK(SelectHop());CHECK(Chosen()==5&&landCount==3&&distances[0]==1&&distances[1]==6&&distances[2]==5&&!bad);}
 else if(!strcmp(argv[1],"chain")){sOverworldMountState.walkEndState=4;CHECK(SelectHop());CHECK(Chosen()==6&&landCount==1&&distances[0]==6&&!bad);}
 else if(!strcmp(argv[1],"range")){sOverworldMountState.snapshot.profile.hopMinDistance=2;CHECK(SelectHop());CHECK(Chosen()==6&&landCount==1&&distances[0]==6&&!bad);}
 else if(!strcmp(argv[1],"single")){sOverworldMountState.snapshot.profile.hopMaxDistance=1;CHECK(SelectHop());CHECK(Chosen()==1&&landCount==1&&arcCount==1&&!bad);}
 else if(!strcmp(argv[1],"blocked")){landingBlock=1;sOverworldMountState.snapshot.profile.chillAllowedTerrainMask=4;CHECK(!SelectHop());CHECK(arcCount==0&&!bad);}
 else return 2;puts(argv[1]);return 0;}
'''


def selection_body(source):
    body = function_body(source, "OverworldMount_TryStartCustomMotion")
    marker = "    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {"
    start = body.index(marker) + len(marker)
    depth = 1
    for end in range(start, len(body)):
        depth += (body[end] == "{") - (body[end] == "}")
        if depth == 0:
            return body[start:end]
    raise AssertionError("mounted Hop selection block differs")


def program(source=None, fault=None):
    source = SOURCE.read_text() if source is None else source
    action = ACTION.read_text()
    if fault == "old-max-first":
        source, count = re.subn(r"BOOL adjacent = lane->hopMinDistance == 1 && lane->hopMaxDistance > 1\s*&& sOverworldMountState.walkEndState != OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;", "BOOL adjacent = FALSE;", source)
        if count != 1: raise AssertionError("adjacent preference seam differs")
    elif fault == "no-height-check":
        old="if (raised && sOverworldMountState.motionTargetBaseY\n            <= sOverworldMountState.motionStartBaseY)"
        if source.count(old)!=1:raise AssertionError("raised height seam differs")
        source=source.replace(old,"if (FALSE)")
    elif fault == "chain-included":
        old="            && sOverworldMountState.walkEndState != OVERWORLD_MOUNT_WALK_END_CHAIN_HOP"
        if source.count(old)!=1:raise AssertionError("chain exclusion seam differs")
        source=source.replace(old,"")
    elif fault is not None:raise AssertionError("unknown copied fault")
    parameters = re.search(r"OverworldMount_PlanHopTrajectory\s*\(([^)]*)\)", source).group(1)
    return (PRELUDE
        + "static u8 OverworldMountAction_ChainForwardTarget(OverworldMountActionCall *call){"+function_body(action,"OverworldMountAction_ChainForwardTarget")+"}\n"
        + "static u8 OverworldMountAction_PlanHopTrajectory(OverworldMountActionCall *call){"+function_body(action,"OverworldMountAction_PlanHopTrajectory")+"}\n"
        + "static u8 Dispatch(OverworldMountActionCall *c){return c->operation==1?OverworldMountAction_ChainForwardTarget(c):OverworldMountAction_PlanHopTrajectory(c); }\n"
        + "static BOOL OverworldMount_PlanHopTrajectory(" + parameters + "){"+function_body(source,"OverworldMount_PlanHopTrajectory")+"}\n"
        + "static BOOL SelectHop(void){const OverworldWildBehaviorProfileData *lane=&sOverworldMountState.snapshot.profile;LocalMapObject *player=&object;int targetX,targetY,distance;u32 trajectory;sOverworldMountState.motionStartX=player->xCurr;sOverworldMountState.motionStartY=player->yCurr;sOverworldMountState.motionStartBaseY=player->posVec[1];"
        + selection_body(source) + "return TRUE;}\n" + DRIVER)


def compile_program(directory,source=None,fault=None):
    binary=Path(directory)/"mounted-hop"
    result=subprocess.run([*shlex.split(os.environ.get("HOST_CC","cc")),"-std=c11","-O0","-x","c","-","-o",str(binary)],input=program(source,fault),capture_output=True,text=True)
    if result.returncode:raise AssertionError(result.stdout+result.stderr)
    return binary


class MountHopCandidateSearchTests(unittest.TestCase):
    def test_adjacent_raised_then_unchanged_long_fallback(self):
        with tempfile.TemporaryDirectory(prefix="mount-raised-") as directory:
            binary=compile_program(directory)
            for case in ("raised","flat","lower","landing-blocked","arc-blocked","forbidden","fallback-order","chain","range","single","blocked"):
                with self.subTest(case=case):
                    result=subprocess.run([str(binary),case],capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_copied_policy_faults_are_rejected(self):
        for fault,case in (("old-max-first","raised"),("no-height-check","flat"),("chain-included","chain")):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(prefix="mount-raised-fault-") as directory:
                binary=compile_program(directory,fault=fault)
                result=subprocess.run([str(binary),case],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,"copied policy fault passed")


if __name__ == "__main__":
    unittest.main()

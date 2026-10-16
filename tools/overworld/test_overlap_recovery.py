"""Actual shared overlap/Stable bodies; native ownership and mover seams stubbed."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import tempfile
from tools.overworld.test_spawn_spatial import extract_function

ROOT = Path(__file__).resolve().parents[2]
PRELUDE = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
typedef int BOOL; typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_DIRECTION_UP 0
#define OW_WILD_DIRECTION_DOWN 1
#define OW_WILD_DIRECTION_LEFT 2
#define OW_WILD_DIRECTION_RIGHT 3
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE 1
#define OW_WILD_HELPER_THROW_TARGET_NONE 0
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_SPAWN_ENTRY_HOP 2
#define BIT_VANISH (1u<<9)
typedef struct LocalMapObject {u32 flags;u8 p[0x60];int xCurr,hCurr,yCurr;u32 posVec[3];u8 tail[0xb0];} LocalMapObject;
_Static_assert(offsetof(LocalMapObject,xCurr)==0x64,"native X");
_Static_assert(offsetof(LocalMapObject,posVec[1])==0x74,"native base Y");
_Static_assert(sizeof(LocalMapObject)==0x12c,"native object extent");
typedef struct Avatar {LocalMapObject *mapObject;int x,y;} Avatar;
typedef struct FieldSystem {Avatar *playerAvatar;BOOL current;} FieldSystem;
typedef struct OverworldWildSpawnState {
 struct {int active;LocalMapObject *object;} spawns[10]; FieldSystem *movementFieldSystem;
 u16 captureTargetMask,movementInProgressMask;
 u8 movementActorControlModes[10],movementEmoteTimers[10],movementTeleportVisiblePause[10];
 u8 movementStagedHopPending[10],movementRamCrashShakeTimers[10],movementTeleportHidden[10];
 u8 movementTeleportFlickerTimers[10],movementSpotStates[10],movementSpawnRunActive[10];
 void *movementTeleportFlickerObjects[10];int movementQueuedBattleSlot,pendingSlot;
} OverworldWildSpawnState;
typedef struct OverworldWildThrowState {u16 targetMask,carrierMask;u8 targets[10];} OverworldWildThrowState;
typedef struct OverworldWildBehaviorProfile {int allowed;} OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives {int target;} OverworldWildBehaviorPrimitives;
typedef BOOL (*OverworldWildQueryPickupThrowTargetFunc)(OverworldWildSpawnState*,OverworldWildThrowState*,int,int,u8,u32);
typedef BOOL (*OverworldWildStartSpawnerMovementFunc)(OverworldWildSpawnState*,FieldSystem*,int,const u8*,int,const OverworldWildBehaviorProfile*,const OverworldWildBehaviorPrimitives*);
static LocalMapObject *exact[10];
static int MapObject_GetCurrentX(LocalMapObject *o){return o->xCurr;}
static int MapObject_GetCurrentY(LocalMapObject *o){return o->yCurr;}
static int GetPlayerXCoord(Avatar *a){return a->x;}
static int GetPlayerYCoord(Avatar *a){return a->y;}
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *o){return (o->flags&1)!=0;}
static BOOL OverworldWildHelper_IsPresentationContextCurrent(FieldSystem *f,OverworldWildSpawnState *s){return f->current && s->movementFieldSystem==f;}
static BOOL OverworldWildHelper_IsExactObject(FieldSystem *f,OverworldWildSpawnState *s,int slot){return f->current && exact[slot]==s->spawns[slot].object;}
"""
DRIVER = r"""
static int calls,started,mask,freeMask=15,targetX,targetY;
static BOOL Query(OverworldWildSpawnState*s,OverworldWildThrowState*t,int carrier,int target,u8 query,u32 masks){
 if(query!=OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE) abort();
 return OverworldWildHelper_IsEligiblePickupThrowTarget(s,t,carrier,target,(u16)masks,0);
}
static BOOL Start(OverworldWildSpawnState*s,FieldSystem*f,int slot,const u8*d,int n,const OverworldWildBehaviorProfile*p,const OverworldWildBehaviorPrimitives*r){
 static const int dx[4]={0,0,-1,1},dy[4]={-1,1,0,0};
 static const u8 wanted[4]={0,3,1,2}; calls++;
 if(f!=s->movementFieldSystem || slot!=0 || n!=4 || p!=NULL || r!=NULL) abort();
 for(int i=0;i<n;i++){
  if(d[i]!=wanted[i]) abort();
  /* Native destination/policy classifier remains the real mover's owner.
   * This fixture has only clear Land exits, using the authored mask. */
  if((mask&1) && (freeMask&(1<<d[i]))){started++;targetX=s->spawns[slot].object->xCurr+dx[d[i]];targetY=s->spawns[slot].object->yCurr+dy[d[i]];return TRUE;}
 }
 return FALSE;
}
int main(int argc,char**argv){
 if(argc!=3)return 2;int c=atoi(argv[1]);mask=atoi(argv[2]);
 LocalMapObject o={0},other={0},player={0};Avatar a={&player,585,407};FieldSystem f={&a,TRUE};
 OverworldWildSpawnState s={0};OverworldWildThrowState t={0};u16 unstable=0;
 o.xCurr=player.xCurr=other.xCurr=585;o.yCurr=player.yCurr=other.yCurr=407;
 o.posVec[1]=player.posVec[1]=other.posVec[1]=65536;
 s.spawns[0].active=TRUE;s.spawns[0].object=&o;s.movementFieldSystem=&f;
 s.pendingSlot=s.movementQueuedBattleSlot=-1;exact[0]=&o;
 switch(c){
 case 1:o.posVec[1]+=65536;break;
 case 2:case 3:a.x=580;s.spawns[1].active=TRUE;s.spawns[1].object=&other;
  if(c==3)other.posVec[1]+=65536;break;
 case 4:freeMask=0;break;case 5:unstable=1;break;
 case 6:s.movementInProgressMask=1;break;case 7:o.flags|=1;break;
 case 8:s.movementSpawnRunActive[0]=2;break;case 9:s.movementActorControlModes[0]=1;break;
 case 10:s.captureTargetMask=1;break;case 11:t.targetMask=1;break;case 12:t.carrierMask=1;break;
 case 13:s.movementEmoteTimers[0]=1;break;case 14:s.movementTeleportVisiblePause[0]=1;break;
 case 15:s.pendingSlot=0;break;case 16:s.movementQueuedBattleSlot=0;break;
 case 17:a.mapObject=NULL;break;case 18:f.current=FALSE;break;case 19:exact[0]=NULL;break;
 case 20:freeMask=1<<3;break;
 }
 BOOL ok=OverworldWildBehavior_TryResolveOverlap(&s,&t,unstable,Query,Start);
 printf("%d %d %d %d %d\n",ok,calls,started,targetX,targetY);return 0;
}
"""

def check(root):
    catalog=json.loads((root/'data/overworld_behavior_profiles.json').read_text())
    ambush=next(p for p in catalog['profiles'] if p['id']=='ambush')
    fields=ambush['fields'];mask=int(fields['chillAllowedTerrainMask']['value'])
    assert mask==int(fields['chillAllowedTerrainOverrideMask']['value'])
    assert fields['chillState']['value']=='OW_WILD_BEHAVIOR_KIND_CHASE'
    assert fields['chillTarget']['value']=='OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER'
    helper=(root/'src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c').read_text()
    overlay=(root/'src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c').read_text()
    bodies='\n'.join(extract_function(helper,n,'BOOL') for n in (
      'OverworldWildHelper_IsPickupThrowMovementContextCurrent',
      'OverworldWildHelper_IsValidPickupThrowTarget','OverworldWildHelper_IsEligiblePickupThrowTarget'))
    bodies+='\n'+extract_function(overlay,'OverworldWildBehavior_TryResolveOverlap','BOOL')
    with tempfile.TemporaryDirectory(prefix='overlap-recovery-') as td:
        source=Path(td)/'test.c';binary=Path(td)/'test';source.write_text(PRELUDE+bodies+DRIVER)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(source),'-o',str(binary)],check=True)
        for c in range(21):
            actual=list(map(int,subprocess.check_output([str(binary),str(c),str(mask)],text=True).split()))
            ok=c in (0,2,11,20);calls=1 if c in (0,2,4,11,20) else 0
            assert actual[:3]==[int(ok),calls,int(ok)],(c,actual)
            if c==20:assert actual[3:]==[586,407]
        assert list(map(int,subprocess.check_output([str(binary),'0','16'],text=True).split()))[:3]==[0,1,0], 'permissions bypassed'
    check_mounted_caller(root, bodies, mask)
    assert mask==17,'Ambush has no Land exit permission'
    print('GREEN: current-height recovery, roof/non-player height separation, all Stable/lifecycle gates, blocked exits and active profile permissions')

def check_mounted_caller(root, bodies, mask):
    """Use the real caller mask: a mount is a blocker, never an AI mover."""
    wild=(root/'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c').read_text()
    tick=extract_function(wild,'OverworldWildSpawns_TickMovementParams','void')
    match=re.search(r'OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY->tryResolve\(\s*state,\s*&runtime->throwState,(.*?)helperEntry->queryPickupThrowTarget,\s*OverworldWildSpawns_TryStartSpawnerMovementCommand\)',tick,re.S)
    assert match is not None,'actual overlap caller missing'
    call=match.group(0).replace('OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY->tryResolve','OverworldWildBehavior_TryResolveOverlap')
    call=call.replace('helperEntry->queryPickupThrowTarget','Query').replace('OverworldWildSpawns_TryStartSpawnerMovementCommand','Start')
    native=extract_function(wild,'OverworldWildSpawns_GetOverlapUnstableMask','u16')
    seam=r'''
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i) (1u<<(i))
typedef struct {OverworldWildThrowState throwState;u16 movementNativeHeldMask;} CallerRuntime;
static CallerRuntime *activeRuntime;
static int mounted,serviceReady=1;static u16 serviceMask;
#define OW_WILD_RUNTIME(s) (activeRuntime)
static BOOL OverworldWildSpawns_MountIsActive(void){return mounted;}
static BOOL PlayerHealthThrowService_IsReady(void){return serviceReady;}
static u16 ServiceUnstable(OverworldWildSpawnState*s){(void)s;return serviceMask;}
static struct {u16(*unstableMask)(OverworldWildSpawnState*);} serviceEntry={ServiceUnstable};
#define PLAYER_HEALTH_THROW_SERVICE_ENTRY (&serviceEntry)
'''
    driver=DRIVER.replace('targetX,targetY;','targetX,targetY,expectedSlot;').replace('slot!=0','slot!=expectedSlot')
    start,main=driver.split('int main(',1); main='int main('+main
    main=main.replace('u16 unstable=0;','u16 unstable=0,nativeHeld=0;')
    main=main.replace('case 20:freeMask=1<<3;break;',r'''case 20:freeMask=1<<3;break;
 case 21:case 23:
  s.spawns[0].active=FALSE;s.spawns[0].object=NULL;exact[0]=NULL;
  s.spawns[7].active=TRUE;s.spawns[7].object=&o;exact[7]=&o;
  s.spawns[8].active=TRUE;s.spawns[8].object=&other;exact[8]=&other;
  unstable=1u<<8;expectedSlot=7;mounted=c==21;break;
 case 22:
  s.spawns[7].active=TRUE;s.spawns[7].object=&other;exact[7]=&other;
  a.x=580;mounted=TRUE;break;
 case 24:mounted=TRUE;break;
 case 25:mounted=TRUE;unstable=1;break;
 case 26:mounted=TRUE;nativeHeld=1;break;
 case 27:serviceReady=0;break;
''')
    main=main.replace('OverworldWildBehavior_TryResolveOverlap(&s,&t,unstable,Query,Start)',
                      'ResolveCaller(&s,&t,unstable,nativeHeld)')
    caller=native+'''static BOOL ResolveCaller(OverworldWildSpawnState*state,OverworldWildThrowState*t,u16 unstable,u16 held){
 CallerRuntime local={*t,held};CallerRuntime*runtime=&local;serviceMask=unstable;activeRuntime=runtime;
 return '''+call+''';}\n'''
    with tempfile.TemporaryDirectory(prefix='mounted-overlap-recovery-') as td:
        source=Path(td)/'test.c';binary=Path(td)/'test'
        source.write_text(PRELUDE+seam+bodies+start+caller+main)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(source),'-o',str(binary)],check=True)
        for case in range(21,28):
            actual=list(map(int,subprocess.check_output([str(binary),str(case),str(mask)],text=True).split()))
            expected=case in (22,23,24)
            assert actual[:3]==[int(expected),int(expected),int(expected)],(case,actual)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,default=ROOT)
    args=parser.parse_args();check(args.source_root.resolve())

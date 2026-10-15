"""Actual native appearance glue with SDK/pointer-width boundaries only.

Reuse the core palette fixture. Refresh, field exit, cleanup, HP and cooldown
policy bodies stay production C. This proves ownership, not DS visual output.
"""
from pathlib import Path
import importlib.util
import os
import re
import shlex
import subprocess
import tempfile
import unittest

from tools.overworld import test_actor_appearance as core

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "lib/overworld/overworld_actor_appearance_native.c"


def declaration(file, prefix):
    spec = importlib.util.spec_from_file_location("native_appearance_extract", ROOT / "scripts/verify_overworld_role_controller.py")
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    text = file.read_text()
    first = text.index(prefix)
    start = text.index('{', first)
    end = extract.matching_delimiter(extract.strip_c_noncode(text), start, '{', '}')
    if prefix.startswith('static '):
        return text[first:end + 1] + '\n'
    return text[first:text.index(';', end) + 1] + '\n'


def harness_source(mutation=None):
    source = core.harness_source().removesuffix(core.DRIVER)
    source = source.replace('#define OVERWORLD_ACTOR_APPEARANCE_ENTRY \\\n',
        'extern const OverworldActorAppearanceEntry hostAppearanceEntry;\n#define OVERWORLD_ACTOR_APPEARANCE_ENTRY \\\n')
    source = source.replace('((const OverworldActorAppearanceEntry *)OVERWORLD_ACTOR_APPEARANCE_CAPSULE_BASE)',
                            '(&hostAppearanceEntry)')
    if mutation == 'cold-entry':
        source = source.replace('if (IsOverlayLoaded(1)) {', 'if (TRUE) {')
    native = re.sub(r'^#include .*$', '', NATIVE.read_text(), flags=re.M)
    native = re.sub(r'__asm__\(.*?\);', '', native, flags=re.S)
    native = re.sub(r'__attribute__\(\(section\("[^"]+"\)\)\)', '', native)
    native = native[:native.index('const OverworldActorAppearanceEntry gOverworldActorAppearanceEntry')]
    # Only the native pointer range and fixed stock/Selector entry addresses
    # differ on a 64-bit host. All native guard branches remain unchanged.
    for name, replacement in {
        'AppearanceNative_RamSpan': 'BOOL AppearanceNative_RamSpan(const void *p,u32 n) { return HostSpan(p,n,FALSE); }',
        'AppearanceNative_SelectorFunction': 'static BOOL AppearanceNative_SelectorFunction(const void *p) { return p==(const void *)HostCancel || p==(const void *)HostIsActive; }',
    }.items():
        start = native.rfind('\n', 0, native.index(name+'(')) + 1
        opening = native.index('{', start)
        depth, end = 1, opening + 1
        while depth:
            depth += (native[end] == '{') - (native[end] == '}')
            end += 1
        native = native[:start] + replacement + native[end:]
    native = native.replace('((StockFieldExit)0x021E5C25)', '((StockFieldExit)HostStockExit)')
    if mutation == 'map-generation':
        exact = '|| state->mapGeneration != actor->handle.mapGeneration'
        if native.count(exact) != 1:
            raise ValueError('native map-generation predicate changed')
        native = native.replace(exact, '|| FALSE')
    if mutation == 'exit-admission':
        exact = 'if (*exitState == 0 && (field == NULL'
        if native.count(exact) != 1:
            raise ValueError('native field-exit admission changed')
        native = native.replace(exact, 'if (FALSE && (field == NULL')
    if mutation == 'wild-drain':
        exact = '&& AppearanceNative_PrepareWildUnload()'
        if native.count(exact) != 1:
            raise ValueError('native Wild cleanup admission changed')
        native = native.replace(exact,
            '&& ((void)AppearanceNative_PrepareWildUnload, TRUE)')
    if mutation == 'cold-wild-entry':
        exact = '!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)'
        if native.count(exact) != 1:
            raise ValueError('native Wild overlay ownership guard changed')
        native = native.replace(exact, 'FALSE')
    if mutation == 'wild-cleanup-order':
        exact = 'return Appearance_ClearForUnload(manager)\n        && AppearanceNative_PrepareWildUnload();'
        if native.count(exact) != 1:
            raise ValueError('native palette/Wild cleanup order changed')
        native = native.replace(exact,
            'return AppearanceNative_PrepareWildUnload()\n        && Appearance_ClearForUnload(manager);')
    conditions = declaration(ROOT / 'include/overworld_behavior_conditions.h',
                             'typedef struct OverworldBehaviorConditionEntryState {')
    prepared = declaration(ROOT / 'include/overworld_behavior_condition_runtime.h',
                           'typedef struct OverworldBehaviorConditionPreparedActor {')
    role_applies = declaration(ROOT / 'include/overworld_behavior_conditions.h',
                              'static inline u8 OverworldBehaviorCondition_RoleApplies(')
    policy = re.sub(r'^#include .*$', '', (ROOT / 'lib/overworld/overworld_appearance_policy.c').read_text(), flags=re.M)
    return source + TYPES + conditions + prepared + role_applies + STATE + policy + native + ENTRY + DRIVER


TYPES = r'''
#define TYPES_H
#define OVERWORLD_BEHAVIOR_HOST 1
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES 32
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS 32
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE 1
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED 2
#include "overworld_wild_behavior_data.h"
typedef struct { int mapId; } HostLocation;
typedef struct FieldSystem { MapObjectMan *mapObjectMan; u32 movementSentinel; HostLocation *location; } FieldSystem;
typedef struct OverworldWildSpawn {
 LocalMapObject *object; u32 personality; u16 mapId,species;
 u8 form,level,terrain,shiny,active,objectId; u16 encounterGeneration;
} OverworldWildSpawn;
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_OBJECT_ID_START 0xe0
typedef struct OverworldWildSpawnState {
 OverworldWildSpawn spawns[10]; int mapId; MapObjectMan *mapObjectMan;
 LocalMapObject *mapObjects; FieldSystem *movementFieldSystem;
 void *movementRuntimeState; u16 mapGeneration;
 u32 movementSentinel[4];
} OverworldWildSpawnState;
'''

STATE = r'''
typedef struct { OverworldBehaviorConditionPreparedActor actors[10]; } ConditionOwner;
typedef struct OverworldWildOverlayRuntimeState { ConditionOwner *conditions; u32 movementSentinel[4]; } OverworldWildOverlayRuntimeState;
typedef struct { OverworldActorStateSnapshot snapshot; u32 movementSentinel[4]; } HostActorSlot;
typedef struct OverworldActorSystemState {
 u32 magic; u16 version,size; u32 frame; u16 fieldEpoch,mapGeneration;
 HostActorSlot slots[10];
} OverworldActorSystemState;
static OverworldActorSystemState residentActors;
#define OVERWORLD_ACTOR_SYSTEM_STATE_ADDR ((uintptr_t)&residentActors)
#define OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC 0x41535953u
static FieldSystem *gFieldSysPtr;
static BOOL actorReady=TRUE,combatReady=TRUE,selectorLoaded=FALSE,selectorValid=TRUE;
static BOOL cancelResult=FALSE,selectorActive=FALSE,restoreCallback=FALSE,overlayLoaded=FALSE;
static u32 hpReads,cancelCalls,activeCalls,stockCalls,loadedForgetCalls;
static BOOL wildLoaded=TRUE,wildCleanupReady=FALSE,wildResidentLive=TRUE;
static u32 wildEntryReads,wildCleanupCalls;
static u16 currentHp=75,maximumHp=100;
static BOOL hpValid=TRUE;
static MapObjectMan *currentManager;
static u32 *recallDraw;
static BOOL OverworldActorSystem_IsReady(void) { return actorReady; }
static BOOL OverworldCombat_IsReady(void) { return combatReady; }
static BOOL HostReadHp(const OverworldWildSpawnState *state,u8 slot,u16 *hp,u16 *maxHp)
 { check(state->mapObjectMan==currentManager && slot<10,"HP current owner");
   ++hpReads; *hp=currentHp; *maxHp=maximumHp; return hpValid; }
static const struct { BOOL (*readHp)(const OverworldWildSpawnState *,u8,u16 *,u16 *); } combatEntry={HostReadHp};
#define OVERWORLD_COMBAT_ENTRY (&combatEntry)
static BOOL HostCancel(FieldSystem *field)
 { check(field==gFieldSysPtr,"cancel current field"); ++cancelCalls;
   if(cancelResult && restoreCallback) { Appearance_SetCallback(recallDraw,Appearance_ApplyMaterial); selectorActive=FALSE; restoreCallback=FALSE; }
   return cancelResult; }
static BOOL HostIsActive(void) { ++activeCalls; return selectorActive; }
static BOOL OverworldFollowerSelector_IsDirectLoaded(void) { return selectorLoaded; }
static BOOL OverworldFollowerSelector_Validate(void) { return selectorValid; }
typedef struct OverworldFollowerSelectorOverlayEntry { BOOL (*inputCancel)(FieldSystem *); BOOL (*inputIsActive)(void); } OverworldFollowerSelectorOverlayEntry;
static const OverworldFollowerSelectorOverlayEntry selectorEntry={HostCancel,HostIsActive};
#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY (&selectorEntry)
#define OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION 149
static BOOL HostWildCleanup(void)
 { check(wildLoaded,"Wild cleanup has a loaded owner");
   check(heapCount==0,"Wild cleanup follows palette drain"); ++wildCleanupCalls;
   if(!wildCleanupReady) return FALSE;
   wildResidentLive=FALSE; return TRUE; }
/* Fixed table pointer is a host boundary; retain cleanup's fourth slot. */
typedef struct { void (*unused[3])(void); BOOL (*cleanupResidentData)(void); }
 HostWildSpawnsEntry;
static const HostWildSpawnsEntry wildEntry={{NULL,NULL,NULL},HostWildCleanup};
static const HostWildSpawnsEntry *HostWildEntry(void)
 { check(wildLoaded,"cold Wild does not access its entry");
   ++wildEntryReads; return &wildEntry; }
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY HostWildEntry()
static BOOL HostStockExit(void *manager,int *state)
 { check(manager==currentManager,"stock exit current manager");
   check(heapCount==0,"stock frees only after palette drain");
   check(!wildResidentLive,"stock exit requires drained Wild resident data"); ++stockCalls;
   if(*state==0) { *state=1; return FALSE; } return TRUE; }
u32 IsOverlayLoaded(u32 id)
 { if(id==1) return overlayLoaded;
   check(id==149,"only Field and Wild owners queried"); return wildLoaded; }
'''

ENTRY = r'''
static void HostForgetLoaded(MapObjectMan *manager,u16 slot)
 { ++loadedForgetCalls; OverworldActorAppearance_Forget(manager,slot); }
const OverworldActorAppearanceEntry hostAppearanceEntry={
 OVERWORLD_ACTOR_APPEARANCE_MAGIC,OVERWORLD_ACTOR_APPEARANCE_VERSION,
 sizeof(OverworldActorAppearanceEntry),OverworldActorAppearance_RefreshNative,
 HostForgetLoaded,OverworldActorAppearance_BeforeParentUnload,
 OverworldActorAppearance_Inspect,OverworldActorAppearance_RefreshAll};
'''

DRIVER = r'''
static void Put32(void *p,u32 off,u32 value) { *(u32 *)((u8 *)p+off)=value; }
static void Put16(void *p,u32 off,u16 value) { *(u16 *)((u8 *)p+off)=value; }
int main(void) {
 LocalMapObject objects[10]={0}; MapObjectMan manager={10,objects,NULL};
 HostLocation location={67};
 FieldSystem field={&manager,0xfeed,&location},otherField={&manager,0xbeef,&location};
 manager.fsys=&field; currentManager=&manager; gFieldSysPtr=&field;
 OverworldWildSpawnState spawns={0}; OverworldWildOverlayRuntimeState runtime={0};
 ConditionOwner conditions={0}; OverworldBehaviorConditionEntryState conditionStates[1]={0};
 OverworldWildBehaviorDataBlob blob={0};
 u32 model[16]={0},draw[49]={0},render[46]={0},material[14]={0};
 union {u32 words[48];u8 bytes[192];} texture={0};
 Register(&manager,sizeof(manager),FALSE);Register(objects,sizeof(objects),FALSE);
 Register(&field,sizeof(field),FALSE);Register(&otherField,sizeof(otherField),FALSE);
 Register(&location,sizeof(location),FALSE);
 Register(&residentActors,sizeof(residentActors),FALSE);Register(&spawns,sizeof(spawns),FALSE);
 Register(&runtime,sizeof(runtime),FALSE);Register(&conditions,sizeof(conditions),FALSE);
 Register(&blob,sizeof(blob),FALSE);Register(model,sizeof(model),FALSE);
 Register(draw,sizeof(draw),FALSE);Register(&texture,sizeof(texture),FALSE);
 Register(render,sizeof(render),TRUE);Register(material,sizeof(material),TRUE);
 residentActors=(OverworldActorSystemState){.magic=OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC,
   .version=2,.size=sizeof(residentActors),.frame=100,.fieldEpoch=2,.mapGeneration=3};
 OverworldActorStateSnapshot *actor=&residentActors.slots[7].snapshot;
 *actor=(OverworldActorStateSnapshot){.version=2,.size=sizeof(*actor),
   .handle={7,1,2,3,4,0},.subjectIdentity=101,.authorityGeneration=1,
   .engineAnchorGeneration=1,.presentationGeneration=1,.species=234,.level=50,
   .role=OVERWORLD_ACTOR_ROLE_WILD,.active=1,.presentationAttached=1};
 objects[7].flags=1;objects[7].id=0xe7;objects[7].unkB4=(uintptr_t)&manager;
 objects[7].unkC8=(void (*)(LocalMapObject *))(uintptr_t)0x021F7895;
 Put32(objects[7].unk108,0,Token(draw));
 Put32(draw,0x34,Token(model));Put32(draw,0x88,Token(model));
 Put32(draw,0x8c,Token(&texture));Put32(draw,0x9c,(8u<<16)|0x20);
 Put32(&texture,0,APPEARANCE_TEX_MAGIC);Put32(&texture,4,sizeof(texture));
 Put16(&texture,0x0e,0x3c);Put16(&texture,0x30,8);Put32(&texture,0x38,0x80);
 texture.bytes[0x3d]=1;Put16(&texture,0x3e,16);Put16(&texture,0x42,8);
 Put16(&texture,0x44,4);Put32(&texture,0x48,3u<<26);
 for(u32 n=0;n<32;n++) ((u16 *)(texture.bytes+0x80))[n]=(n%16)==0?0xffff:0x7c00;
 spawns=(OverworldWildSpawnState){.mapId=67,.mapObjectMan=&manager,.mapObjects=objects,
   .movementFieldSystem=&field,.movementRuntimeState=&runtime,.mapGeneration=3,
   .movementSentinel={1,2,3,4}};
 spawns.spawns[7]=(OverworldWildSpawn){.object=&objects[7],.personality=101,.mapId=67,
   .species=234,.level=50,.active=1,.objectId=0xe7,.encounterGeneration=4};
 runtime.conditions=&conditions;runtime.movementSentinel[0]=123;
 conditions.actors[7]=(OverworldBehaviorConditionPreparedActor){.subject=actor->handle,
   .states=conditionStates,.count=1,.valid=1,.stateCapacity=1};
 blob.header.magic=OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC;
 blob.header.version=OVERWORLD_WILD_BEHAVIOR_DATA_VERSION;
 blob.header.headerSize=sizeof(blob.header);blob.header.blobSize=sizeof(blob);
 blob.header.conditionEntryCount=1;blob.conditionEntries[0].applicationIndex=14;
 blob.conditionEntries[0].cooldownFrames=20;
 conditionStates[0].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
 conditionStates[0].cooldownUntil=120;
 for(u8 role=OVERWORLD_ACTOR_ROLE_WILD;role<=OVERWORLD_ACTOR_ROLE_MOUNTED;role++) {
  actor->role=role;++actor->authorityGeneration;currentHp=75;residentActors.frame=64;
  OverworldActorSystemState beforeActors=residentActors;
  OverworldWildSpawnState beforeSpawns=spawns;
  OverworldWildOverlayRuntimeState beforeRuntime=runtime;
  OverworldBehaviorConditionEntryState beforeCondition=conditionStates[0];
  LocalMapObject beforeObjects[10];memcpy(beforeObjects,objects,sizeof(objects));
  OverworldActorAppearance_RefreshAll(&spawns,&blob);
  const OverworldActorAppearanceSnapshot *view=OverworldActorAppearance_Inspect(7);
  check(view && view->mode==OVERWORLD_ACTOR_APPEARANCE_RED && view->strength==3,"native exact HP pulse strength all roles");
  check(view->role==role && sAppearance->actor==actor,"resident actor pointer all roles");
  check(sAppearance->object==&objects[7] && sAppearance->object!=&objects[0],"mounted Pokemon body not rider");
  check(!memcmp(&beforeActors,&residentActors,sizeof(residentActors))
    && !memcmp(&beforeSpawns,&spawns,sizeof(spawns)) && !memcmp(&beforeRuntime,&runtime,sizeof(runtime))
    && !memcmp(beforeObjects,objects,sizeof(objects))
    && !memcmp(&beforeCondition,&conditionStates[0],sizeof(beforeCondition)),"refresh has no condition or movement writes");
  u32 paletteKey=view->privatePaletteKey, allocationCount=allocations;
  blob.restEnabledApplications=1u<<14;
  residentActors.frame=0;OverworldActorAppearance_RefreshAll(&spawns,&blob);
  check(OverworldActorAppearance_Inspect(7)->mode==OVERWORLD_ACTOR_APPEARANCE_RED
    && OverworldActorAppearance_Inspect(7)->strength==0,"injured native OFF never becomes cooldown blue");
  check(!memcmp(uploaded,texture.bytes+0x80,64),"native OFF has exact original palette bytes");
  residentActors.frame=64;OverworldActorAppearance_RefreshAll(&spawns,&blob);
  check(OverworldActorAppearance_Inspect(7)->strength==3,"native pulse peak uses Actor clock");
  residentActors.frame=128;OverworldActorAppearance_RefreshAll(&spawns,&blob);
  check(OverworldActorAppearance_Inspect(7)->strength==0,"native pulse repeats without new HP loss");
  check(OverworldActorAppearance_Inspect(7)->privatePaletteKey==paletteKey
    && allocations==allocationCount,"native pulse reuses one private palette");
  residentActors.frame=64;
  currentHp=99;OverworldActorAppearance_RefreshAll(&spawns,&blob);
  check(OverworldActorAppearance_Inspect(7)->strength==2,"native small HP loss strength");
  residentActors.frame=16;
  currentHp=1;OverworldActorAppearance_RefreshAll(&spawns,&blob);
  check(OverworldActorAppearance_Inspect(7)->strength==6,"native low HP softer strength");
  blob.restEnabledApplications=0;residentActors.frame=100;
  currentHp=100;OverworldActorAppearance_RefreshAll(&spawns,&blob);
  check(!OverworldActorAppearance_Inspect(7) && Appearance_GetCallback(draw)==NULL,"native full HP clears tint");
 }
 blob.restEnabledApplications=1u<<14;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(OverworldActorAppearance_Inspect(7)->mode==OVERWORLD_ACTOR_APPEARANCE_BLUE,"native enabled cooldown tint");
 blob.conditionOptions[0].subjectRoleMask=1;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!OverworldActorAppearance_Inspect(7),"wild-only profile cannot tint current mounted body");
 blob.conditionOptions[0].subjectRoleMask=4;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(OverworldActorAppearance_Inspect(7)->mode==OVERWORLD_ACTOR_APPEARANCE_BLUE,"current mounted role enables applicable cooldown");
 actor->role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!OverworldActorAppearance_Inspect(7),"role change removes inapplicable cooldown tint");
 blob.conditionOptions[0].subjectRoleMask=2;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(OverworldActorAppearance_Inspect(7)->mode==OVERWORLD_ACTOR_APPEARANCE_BLUE,"native current follower role supplied to rest policy");
 blob.conditionOptions[0].subjectRoleMask=0;
 blob.restEnabledApplications=1u<<13;OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!OverworldActorAppearance_Inspect(7),"other application cannot enable cooldown tint");
 blob.restEnabledApplications=1u<<14;conditions.actors[7].subject.generation++;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!OverworldActorAppearance_Inspect(7),"stale prepared identity cannot tint");
 conditions.actors[7].subject=actor->handle;residentActors.frame=120;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!OverworldActorAppearance_Inspect(7),"existing cooldown expiry clears tint");
 residentActors.frame=100;blob.header.version--;OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!OverworldActorAppearance_Inspect(7),"old catalog cannot supply rest mask");
 blob.header.version++;blob.restEnabledApplications=0;
 OverworldActorAppearanceNativeInput input={actor,&spawns,&conditions.actors[7],&blob,0,100};
 currentHp=75;spawns.mapGeneration=5;
 check(OverworldActorAppearance_RefreshNative(&input)==OVERWORLD_ACTOR_APPEARANCE_INVALID && !sAppearance,"stale map cannot make palette");
 spawns.mapGeneration=3;location.mapId=33;
 check(OverworldActorAppearance_RefreshNative(&input)==OVERWORLD_ACTOR_APPEARANCE_INVALID && !sAppearance,"different native map cannot make palette");
 location.mapId=67;gFieldSysPtr=&otherField;
 check(OverworldActorAppearance_RefreshNative(&input)==OVERWORLD_ACTOR_APPEARANCE_INVALID && !sAppearance,"foreign current field cannot make palette");
 gFieldSysPtr=&field;spawns.spawns[7].personality++;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!sAppearance,"stale Pokemon identity cannot make palette");spawns.spawns[7].personality--;
 OverworldActorStateSnapshot copiedActor=*actor;input.actor=&copiedActor;
 check(OverworldActorAppearance_RefreshNative(&input)==OVERWORLD_ACTOR_APPEARANCE_INVALID,"stack inspect copy rejected");input.actor=actor;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(sAppearance && sAppearance->actor==actor,"refresh resumes current resident");
 hpValid=FALSE;OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(!sAppearance && heapCount==0,"unreadable HP clears old palette");hpValid=TRUE;
 OverworldActorAppearance_RefreshAll(&spawns,&blob);
 check(hpReads>0 && sAppearance,"native HP service used");
 recallDraw=draw;Appearance_SetCallback(draw,Foreign);selectorLoaded=TRUE;selectorActive=TRUE;
 int exitState=0;cancelResult=FALSE;u32 beforeFrees=frees;
 check(!OverworldActorAppearance_FieldExit(&manager,&exitState) && exitState==0
   && stockCalls==0 && frees==beforeFrees && Appearance_GetCallback(draw)==Foreign,"exit0 waits before stock free");
 check(wildCleanupCalls==0 && wildEntryReads==0,"pending recall never enters Wild cleanup");
 check(cancelCalls==1,"recall cancel consulted before stock exit");
 cancelResult=TRUE;selectorActive=FALSE;
 check(!OverworldActorAppearance_FieldExit(&manager,&exitState) && stockCalls==0
   && Appearance_GetCallback(draw)==Foreign,"live foreign callback still defers unload");
 selectorValid=FALSE;
 check(!OverworldActorAppearance_FieldExit(&manager,&exitState) && stockCalls==0,"invalid selector cannot unload");
 selectorValid=TRUE;restoreCallback=TRUE;
 check(!OverworldActorAppearance_FieldExit(&manager,&exitState) && exitState==0
   && stockCalls==0 && wildCleanupCalls==1 && wildResidentLive && heapCount==0,
   "pending Wild cleanup blocks stock exit after palette drain");
 u32 drainedFrees=frees;
 wildCleanupReady=TRUE;
 check(!OverworldActorAppearance_FieldExit(&manager,&exitState) && exitState==1
   && stockCalls==1 && heapCount==0 && Appearance_GetCallback(draw)==NULL
   && wildCleanupCalls==2 && !wildResidentLive && frees==drainedFrees,
   "cancel palette and Wild drain then stock exit");
 u32 beforeCancel=cancelCalls,beforeWildCleanup=wildCleanupCalls;gFieldSysPtr=NULL;
 check(OverworldActorAppearance_FieldExit(&manager,&exitState) && stockCalls==2
   && cancelCalls==beforeCancel && wildCleanupCalls==beforeWildCleanup,
   "state1 forwards stock without repeat cleanup");
 wildLoaded=FALSE;u32 beforeWildReads=wildEntryReads;
 selectorLoaded=FALSE;check(OverworldActorAppearance_BeforeParentUnload(NULL,NULL),"destroyed parent NULL cleanup");
 check(wildEntryReads==beforeWildReads && wildCleanupCalls==beforeWildCleanup,
   "cold Wild cleanup never accesses its fixed entry");
 overlayLoaded=FALSE;OverworldActorAppearance_ForgetLoaded(NULL,7);
 check(loadedForgetCalls==0,"cold field forget never enters capsule");
 overlayLoaded=TRUE;OverworldActorAppearance_ForgetLoaded(NULL,7);
 check(loadedForgetCalls==1,"loaded field forget enters current capsule");
 check(allocations==frees && heapCount==0,"native lifecycle releases all palettes once");
 puts("production native appearance ownership and exit checks passed");return 0;
}
'''


class ActorAppearanceNativeTests(unittest.TestCase):
    def compile_run(self, mutation=None):
        with tempfile.TemporaryDirectory(prefix="native-appearance-") as directory:
            source, binary = Path(directory) / 'check.c', Path(directory) / 'check'
            source.write_text(harness_source(mutation))
            compiled = subprocess.run(shlex.split(os.environ.get('CC','cc')) + [
                '-std=c11','-O2','-Wall','-Wextra','-Werror','-I',str(ROOT/'include'),
                str(source),'-o',str(binary)], capture_output=True,text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            return subprocess.run([str(binary)],capture_output=True,text=True)

    def test_native_refresh_and_stock_exit_ownership(self):
        result=self.compile_run()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('production native appearance ownership',result.stdout)

    def test_removing_native_map_guard_is_rejected(self):
        result=self.compile_run('map-generation')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('stale map cannot make palette',result.stderr)

    def test_skipping_exit_admission_is_rejected(self):
        result=self.compile_run('exit-admission')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('stock frees only after palette drain',result.stderr)

    def test_entering_cold_field_capsule_is_rejected(self):
        result=self.compile_run('cold-entry')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('cold field forget never enters capsule',result.stderr)

    def test_skipping_wild_cleanup_is_rejected(self):
        result=self.compile_run('wild-drain')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('stock exit requires drained Wild resident data',result.stderr)

    def test_entering_cold_wild_owner_is_rejected(self):
        result=self.compile_run('cold-wild-entry')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('cold Wild does not access its entry',result.stderr)

    def test_wild_cleanup_before_palette_drain_is_rejected(self):
        result=self.compile_run('wild-cleanup-order')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Wild cleanup follows palette drain',result.stderr)


if __name__=='__main__':
    unittest.main()

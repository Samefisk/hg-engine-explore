"""Run the production Wild cleanup, Query drain and tracked unload together.

Native overlay/task/allocator calls are boundaries. The owner receipt, ready
admission, free order and failed-cleanup retry are unchanged production C.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_role_controller import matching_delimiter, strip_c_noncode


ROOT = Path(__file__).resolve().parents[2]
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def function(text, signature):
    start = text.index(signature)
    opening = text.index("{", start)
    end = matching_delimiter(strip_c_noncode(text), opening, "{", "}")
    return text[start:end + 1] + "\n"


def harness(mutation=None):
    wild = WILD.read_text()
    wild = wild.replace(' __attribute__((noinline,\n    optimize("Os,no-ira-loop-pressure,no-tree-fre")))\n', ' ')
    flags = wild[wild.index("static void *sOverworldWildBehaviorDataBlob;"):wild.index(
        "static LocalMapObject *sOverworldWildCollisionIgnoredObject;")]
    cleanup = function(wild, "static BOOL OverworldWildSpawns_CleanupResidentData(void)\n{")
    query = function(wild, "static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(\n    FieldSystem *field, const OverworldActorTransitionCall *transition)\n{")
    drain = function(wild, "static BOOL OverworldWildSpawns_DrainQuery(void *raw)\n{")
    field = (ROOT / "lib/overworld/overworld_query_code_addon_field.c").read_text()
    service = function(field, "static const OverworldQueryCodeAddonServiceEntry *Field_Service(void)")
    field = re.sub(r'__attribute__\(\(noinline,used,section\("[^"]+"\)\)\)', '', field)
    field_unload = function(field, "OverworldQueryCodeAddonStatus\n\nOverworldQueryCodeAddonField_Unload(")
    current = function(field, "const OverworldQueryCodeAddonEntry *\n\nOverworldQueryCodeAddonField_AcquireCurrent(")
    overlay = (ROOT / "src/overlay.c").read_text()
    unload = function(overlay, "void LONG_CALL UnloadOverlayByID(u32 ovyId) {").replace("LONG_CALL ", "")
    if mutation == "release-first":
        exact = ("!OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->cleanupResidentData()\n"
                 "                    || !OverworldFieldService_ShutdownTransientServices()")
        assert unload.count(exact) == 1
        unload = unload.replace(exact, ("!OverworldFieldService_ShutdownTransientServices()\n"
            "                    || !OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->cleanupResidentData()"))
    elif mutation == "missing-receipt":
        exact = "sOverworldWildFlags.residentDataCleaned\n        && ((uintptr_t)state"
        assert cleanup.count(exact) == 1
        cleanup = cleanup.replace(exact, "TRUE\n        && ((uintptr_t)state")
    elif mutation == "no-ready-gate":
        exact = "!sub_0203DF8C(field)"
        assert query.count(exact) == 1
        query = query.replace(exact, "FALSE")
    elif mutation == "stale-clean-receipt":
        exact = "if (entry != NULL) sOverworldWildFlags.residentDataCleaned = FALSE;"
        assert query.count(exact) == 1
        query = query.replace(exact, "(void)entry;")
    return PRELUDE + flags + SUPPORT + service + field_unload + current + drain + cleanup + query + unload + DRIVER


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "constants/file.h"
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP 1
#define OVERWORLD_WILD_HELPER_OWNED_BEHAVIOR 1
#define OVERWORLD_WILD_HELPER_VALIDATE_ONLY 2
#define OVERWORLD_WILD_HELPER_LIFECYCLE_PREPARE_CLEANUP 1
#define OVERWORLD_WILD_HELPER_LIFECYCLE_FINISH_OWNED 2
#define OVERWORLD_WILD_HELPER_LIFECYCLE_FINISH_UNOWNED 3
#define OVERWORLD_QUERY_ADDON_OK 0
#define OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(c) ((u16)(c))
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(c) ((u16)((c)>>16))
#define CHECK(c) do {if(!(c)){fprintf(stderr,"%s:%d: %s\n",__FILE__,__LINE__,#c);exit(1);}}while(0)
typedef struct {void *objects;} MapObjectMan;
typedef struct {int mapId;} Location;
typedef struct FieldSystem {int ready;Location *location;MapObjectMan *mapObjectMan;} FieldSystem;
typedef struct {u8 bindings[8]; struct {struct {void *bindings;} world; BOOL valid;} frame;} OverworldWildBehaviorConditionRuntime;
typedef struct {void *pickupQuery,*movementBehaviorSlotCaches; OverworldWildBehaviorConditionRuntime *conditions;} OverworldWildOverlayRuntimeState;
typedef struct {FieldSystem *movementFieldSystem; void *movementRuntimeState;} OverworldWildSpawnState;
typedef struct {u32 unused;} OverworldQueryCodeAddonEntry;
typedef struct {int currentMapId;u16 nextFieldEpoch,nextMapGeneration;} OverworldActorTransitionCall;

typedef struct {u32 unused;} OverworldQueryCodeAddonOps;
typedef int OverworldQueryCodeAddonStatus;
typedef struct {u32 unused;} OverworldQueryCodeAddonState;
typedef struct {u32 magic;u16 version,size;} OverworldBehaviorConditionServiceEntry;
typedef struct {u32 magic;u16 version,size;OverworldQueryCodeAddonState *state;
 void (*load)(void),(*acquire)(void);int (*unload)(const OverworldQueryCodeAddonOps *,void *);
} OverworldQueryCodeAddonServiceEntry;
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC 0x434f4e44
#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION 10
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC 0x51535256
#define OVERWORLD_QUERY_CODE_ADDON_VERSION 1
#define OVERWORLD_QUERY_ADDON_INVALID 3
static OverworldQueryCodeAddonState gOverworldQueryCodeAddonState;
static const OverworldBehaviorConditionServiceEntry gOverworldBehaviorConditionServiceEntry={
 OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION,sizeof(OverworldBehaviorConditionServiceEntry)};
typedef struct {u32 id; BOOL active;} PMiLoadedOverlay;
static FieldSystem field={1,NULL,NULL};
static OverworldWildSpawnState subject;
static PMiLoadedOverlay overlays[MAX_ACTIVE_OVERLAYS];
static OverworldQueryCodeAddonEntry imageEntry;
static const OverworldQueryCodeAddonOps sOverworldWildQueryCodeOps={0};
static OverworldWildSpawnState *sOverworldWildLastState;
static BOOL fieldLoaded,selectorLoaded,helperValid,prepareReady,finishReady,queryReady,acquireReady;
static void *image;
static int gateCalls,acquires,shutdowns,mountCalls,drains,freeCount,presentationCalls,taskCalls;
static int metadataReads,regionReads;
static int events[64],eventCount;
enum {E_DRAIN=1,E_IMAGE_FREE,E_RUNTIME_FREE,E_SHUTDOWN,E_OWNER_FREE};
static void Event(int e){CHECK(eventCount<64);events[eventCount++]=e;}
static BOOL OverworldWildSpawns_CleanupResidentData(void);
static BOOL OverworldWildSpawns_DrainQuery(void *);
static void UnloadOverlayByID(u32);
'''

SUPPORT = r'''
#define OW_WILD_RUNTIME(s) ((OverworldWildOverlayRuntimeState *)(s)->movementRuntimeState)
static u32 GetOverlayLoadDestination(u32 id){(void)id;return 0;}
static PMiLoadedOverlay *GetLoadedOverlaysInRegion(u32 region){CHECK(region==0);++regionReads;return overlays;}
static BOOL IsOverlayLoaded(u32 id){
 if(id==OVERLAY_FIELD){++metadataReads;
  for(int i=0;i<MAX_ACTIVE_OVERLAYS;i++)
   if(overlays[i].id==id&&overlays[i].active==TRUE)return fieldLoaded;
  return FALSE;}
 for(int i=0;i<MAX_ACTIVE_OVERLAYS;i++)if(overlays[i].active&&overlays[i].id==id)return TRUE;
 return FALSE;
}
static BOOL CanOverlayBeLoaded(u32 id){CHECK(id==OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA);return TRUE;}
static void sys_FreeMemoryEz(void *p){
 CHECK(p);++freeCount;
 if(sOverworldWildLastState && p==sOverworldWildLastState->movementRuntimeState)Event(E_RUNTIME_FREE);
 free(p);
}
static void OverworldWildSpawns_MountCancel(u32 reason){CHECK(reason==OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP);++mountCalls;}
static BOOL HostHelperValidate(u32 mode){CHECK(mode==OVERWORLD_WILD_HELPER_OWNED_BEHAVIOR||mode==OVERWORLD_WILD_HELPER_VALIDATE_ONLY);return helperValid;}
#define OVERWORLD_WILD_HELPER_OVERLAY_VALIDATE HostHelperValidate
static BOOL HostLifecycle(u32 mode,FieldSystem *f){
 if(mode==OVERWORLD_WILD_HELPER_LIFECYCLE_PREPARE_CLEANUP){CHECK(f==NULL||f==&field);return prepareReady;}
 CHECK(f==NULL);return finishReady;
}
#define OVERWORLD_WILD_HELPER_OVERLAY_LIFECYCLE HostLifecycle
static const void *HostGate(void){++gateCalls;return fieldLoaded&&selectorLoaded?(void *)&imageEntry:NULL;}
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE HostGate
static const OverworldBehaviorConditionServiceEntry *OverworldBehaviorConditionService_Get(void){
 ++gateCalls;return fieldLoaded&&selectorLoaded?&gOverworldBehaviorConditionServiceEntry:NULL;
}
static int HostUnload(const OverworldQueryCodeAddonOps *ops,void *query){
 CHECK(ops==&sOverworldWildQueryCodeOps);CHECK(fieldLoaded&&selectorLoaded);
 if(!queryReady)return 1;
 ++drains;Event(E_DRAIN);CHECK(OverworldWildSpawns_DrainQuery(query));
 if(image){free(image);image=NULL;++freeCount;Event(E_IMAGE_FREE);}return 0;
}
static void HostTableCallback(void){}
static const OverworldQueryCodeAddonServiceEntry gOverworldQueryCodeAddonServiceEntry={
 OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC,OVERWORLD_QUERY_CODE_ADDON_VERSION,sizeof(OverworldQueryCodeAddonServiceEntry),
 &gOverworldQueryCodeAddonState,HostTableCallback,HostTableCallback,HostUnload};
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_UNLOAD OverworldQueryCodeAddonField_Unload
static void OverworldWildSpawns_CleanupPresentationBeforeUnload(OverworldWildSpawnState *s){
 CHECK(s==NULL||s==&subject);++presentationCalls;
}
static void OverworldWildSpawns_CleanupResidentTasks(void){++taskCalls;}
static u32 gOverworldWildNativeShadowSuppressedMask;
static void OverworldWildSpawns_ClearAllConditionState(OverworldWildBehaviorConditionRuntime *c){memset(c,0,sizeof(*c));}
BOOL sub_0203DF8C(FieldSystem *f){CHECK(f==&field);return f->ready;}
static u32 HostContext(void){CHECK(fieldLoaded&&selectorLoaded);return 0x00030002;}
static const struct {u32 (*getContext)(void);} compat={HostContext};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compat)
static const OverworldQueryCodeAddonEntry *HostAcquire(FieldSystem *f,u16 epoch,u16 generation,const OverworldQueryCodeAddonOps *ops,void *query){
 CHECK(f==&field&&epoch==2&&generation==3&&ops==&sOverworldWildQueryCodeOps);
 CHECK(query==NULL||query==subject.movementRuntimeState);++acquires;
 if(!acquireReady)return NULL;
 if(!image){image=malloc(128);CHECK(image);}return &imageEntry;
}
#define OverworldQueryCodeAddonField_Acquire HostAcquire
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_CURRENT OverworldQueryCodeAddonField_AcquireCurrent
static const struct {BOOL (*cleanupResidentData)(void);} wildEntry={OverworldWildSpawns_CleanupResidentData};
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY (&wildEntry)
static BOOL OverworldFieldService_ShutdownTransientServices(void){
 ++shutdowns;Event(E_SHUTDOWN);selectorLoaded=FALSE;return TRUE;
}
static BOOL ResetOverworldFieldServiceState(void){return OverworldFieldService_ShutdownTransientServices();}
static void FreeOverlayAllocation(PMiLoadedOverlay *p){
 CHECK(p->active);
 if(p->id==OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)Event(E_OWNER_FREE);
 p->active=FALSE;
}
static const struct {u32 first_id,ext_id;} gLinkedOverlayList[]={
 {OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION,OVERLAY_OVERWORLD_FOLLOWER_SELECTOR}};
#define NELEMS(a) (sizeof(a)/sizeof((a)[0]))
'''

DRIVER = r'''
static void Reset(void){
 CHECK(!image);memset(&sOverworldWildFlags,0,sizeof(sOverworldWildFlags));
 memset(&subject,0,sizeof(subject));sOverworldWildLastState=NULL;sOverworldWildBehaviorDataBlob=NULL;
 memset(overlays,0,sizeof(overlays));overlays[0]=(PMiLoadedOverlay){OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION,TRUE};
 overlays[7]=(PMiLoadedOverlay){OVERLAY_FIELD,TRUE};
 field.ready=fieldLoaded=selectorLoaded=helperValid=prepareReady=finishReady=queryReady=acquireReady=TRUE;
 gateCalls=acquires=shutdowns=mountCalls=drains=freeCount=presentationCalls=taskCalls=eventCount=0;
 metadataReads=regionReads=0;
}
static void Owned(void){
 Reset();sOverworldWildLastState=&subject;subject.movementFieldSystem=&field;
 OverworldWildOverlayRuntimeState *r=calloc(1,sizeof(*r));CHECK(r);subject.movementRuntimeState=r;
 r->pickupQuery=malloc(128);r->movementBehaviorSlotCaches=malloc(32);r->conditions=calloc(1,sizeof(*r->conditions));
 CHECK(r->pickupQuery&&r->movementBehaviorSlotCaches&&r->conditions);
 r->conditions->frame.valid=TRUE;r->conditions->frame.world.bindings=r->conditions->bindings;
 sOverworldWildBehaviorDataBlob=malloc(64);image=malloc(128);CHECK(sOverworldWildBehaviorDataBlob&&image);
 sOverworldWildBehaviorDataLoadAttempted=TRUE;sOverworldWildHelperOverlayReady=TRUE;
 overlays[1]=(PMiLoadedOverlay){OVERLAY_OVERWORLD_WILD_HELPER,TRUE};
}
static int At(int e){for(int i=0;i<eventCount;i++)if(events[i]==e)return i;return -1;}
int main(void){
 /* A pristine but uncleaned overlay cannot claim a completed teardown. */
 Reset();fieldLoaded=selectorLoaded=FALSE;
 CHECK(!OverworldWildSpawns_CleanupResidentData());CHECK(gateCalls==1&&!drains&&!freeCount&&!sOverworldWildFlags.residentDataCleaned);
 /* Pending helper/Query cleanup retains all code and data for the retry. */
 Owned();prepareReady=FALSE;UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
 CHECK(overlays[0].active&&selectorLoaded&&!shutdowns&&!freeCount&&!sOverworldWildFlags.residentDataCleaned);
 prepareReady=TRUE;queryReady=FALSE;UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
 CHECK(overlays[0].active&&selectorLoaded&&!shutdowns&&!freeCount&&!sOverworldWildFlags.residentDataCleaned);
 queryReady=TRUE;UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
 CHECK(!overlays[0].active&&!selectorLoaded&&!image&&!subject.movementRuntimeState&&!sOverworldWildLastState);
 CHECK(freeCount==6&&sOverworldWildFlags.residentDataCleaned);
 CHECK(At(E_DRAIN)<At(E_IMAGE_FREE)&&At(E_IMAGE_FREE)<At(E_RUNTIME_FREE));
 CHECK(At(E_RUNTIME_FREE)<At(E_SHUTDOWN)&&At(E_SHUTDOWN)<At(E_OWNER_FREE));
 /* Early parent cleanup is followed by a cold, idempotent tracked release. */
 Owned();CHECK(OverworldWildSpawns_CleanupResidentData());
 int oldGates=gateCalls,oldMounts=mountCalls,oldFrees=freeCount;
 fieldLoaded=selectorLoaded=FALSE;UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
 CHECK(!overlays[0].active&&gateCalls==oldGates&&mountCalls==oldMounts&&freeCount==oldFrees);
 /* A new successful acquire cancels the receipt; failure leaves it alone. */
 Reset();sOverworldWildFlags.residentDataCleaned=TRUE;
 CHECK(!OverworldWildSpawns_QueryAddon(NULL,NULL)&&!regionReads&&!gateCalls&&!acquires);
 overlays[7]=(PMiLoadedOverlay){0,FALSE};
 CHECK(!OverworldWildSpawns_QueryAddon(&field,NULL)&&!gateCalls&&!acquires);
 overlays[7]=(PMiLoadedOverlay){2,TRUE};
 CHECK(!OverworldWildSpawns_QueryAddon(&field,NULL)&&!gateCalls&&!acquires);
 overlays[7]=(PMiLoadedOverlay){OVERLAY_FIELD,FALSE};
 CHECK(!OverworldWildSpawns_QueryAddon(&field,NULL)&&!gateCalls&&!acquires);
 overlays[7].active=2;
 CHECK(!OverworldWildSpawns_QueryAddon(&field,NULL)&&!gateCalls&&!acquires);
 overlays[7].active=TRUE;
 CHECK(metadataReads==0); /* Exact loaded gate cannot re-read SDK metadata. */
 field.ready=FALSE;CHECK(!OverworldWildSpawns_QueryAddon(&field,NULL)&&!acquires&&sOverworldWildFlags.residentDataCleaned);
 field.ready=TRUE;acquireReady=FALSE;CHECK(!OverworldWildSpawns_QueryAddon(&field,NULL)&&acquires==1&&sOverworldWildFlags.residentDataCleaned);
 acquireReady=TRUE;CHECK(OverworldWildSpawns_QueryAddon(&field,NULL)&&acquires==2&&!sOverworldWildFlags.residentDataCleaned);
 CHECK(metadataReads==0);
 fieldLoaded=selectorLoaded=FALSE;CHECK(!OverworldWildSpawns_CleanupResidentData()&&image);
 fieldLoaded=selectorLoaded=TRUE;CHECK(OverworldWildSpawns_CleanupResidentData()&&!image);
 /* Even a stale completed receipt never hides a partial native owner. */
 Owned();sOverworldWildFlags.residentDataCleaned=TRUE;queryReady=FALSE;
 CHECK(!OverworldWildSpawns_CleanupResidentData()&&image&&subject.movementRuntimeState);
 queryReady=TRUE;CHECK(OverworldWildSpawns_CleanupResidentData());
 puts("Wild cleanup/ready receipt controls passed");return 0;
}
'''


class WildCleanupLifecycleTests(unittest.TestCase):
    def run_harness(self, mutation=None):
        with tempfile.TemporaryDirectory(prefix="wild-cleanup-") as directory:
            source = Path(directory) / "fixture.c"
            binary = Path(directory) / "fixture"
            source.write_text(harness(mutation))
            command = shlex.split(os.environ.get("CC", "cc")) + ["-std=c99", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "include"), str(source), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True)

    def test_current_production_cleanup_order_and_ready_receipt(self):
        result = self.run_harness()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_named_old_order_and_missing_contracts_are_rejected(self):
        for mutation in ("release-first", "missing-receipt", "no-ready-gate", "stale-clean-receipt"):
            with self.subTest(mutation=mutation):
                self.assertNotEqual(self.run_harness(mutation).returncode, 0)


if __name__ == "__main__":
    unittest.main()

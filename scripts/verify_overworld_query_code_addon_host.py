#!/usr/bin/env python3
"""Check production loader C; stub only engine allocation/cache boundaries and host address width."""
from pathlib import Path
import subprocess
import json
import hashlib

ROOT = Path(__file__).resolve().parents[1]
import argparse, tempfile
parser=argparse.ArgumentParser(description="Production query-loader admission, cache order and drain checks")
parser.add_argument("--package", type=Path, required=True)
args=parser.parse_args()
temporary=tempfile.TemporaryDirectory(prefix="query-addon-host-")
HERE=Path(temporary.name)
SOURCE = ROOT / 'lib/overworld/overworld_query_code_addon.c'
source = SOURCE.read_text()
needle = 'static u32 Addon_Address(const void *pointer) { return (u32)(uintptr_t)pointer; }'
assert source.count(needle) == 1
source = source.replace('#include "../../include/overworld_query_code_addon.h"', '')
source = source.replace(needle, 'static u32 Addon_Address(const void *pointer) { return pointer ? gNativeAddress : 0; }')
# The loader compares a serialized ARM size, not this host's pointer width.
# Its native header assertion and compiled package both independently bind424.
assert "CargoQueryStateMustRemain424[sizeof(OverworldCargoQueryState)==424?1:-1]" in (ROOT / "include/overworld_cargo_query.h").read_text()
assert source.count("sizeof(OverworldCargoQueryState)") == 1
source = source.replace("sizeof(OverworldCargoQueryState)", "424u")
service_source=(ROOT / 'lib/overworld/overworld_query_code_addon_service.c').read_text()
service_source=service_source.replace('#include "../../include/overworld_query_code_addon_service.h"','')
field_source=(ROOT / 'lib/overworld/overworld_query_code_addon_field.c').read_text()
field_source=field_source.replace('#include "../../include/overworld_query_code_addon_field.h"','').replace('#include "overworld_query_code_addon_package.h"','').replace('#include "../../include/overworld_actor_system_internal.h"','').replace('#include "../../include/map_events_internal.h"','')
# ELF section placement is checked by the ARM proof, not the Mach-O host.
import re
service_source=re.sub(r'section\("[^"\n]+"\)', 'unused', service_source)
field_source=re.sub(r'section\("[^"\n]+"\)', 'unused', field_source)
prefix = r'''
#define OVERWORLD_ACTOR_SYSTEM_HOST
#define OVERWORLD_BEHAVIOR_HOST
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#include "overworld_query_code_addon_field.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define CHECK(c) do { if(!(c)) { fprintf(stderr,"check failed %s:%d: %s\n",__FILE__,__LINE__,#c); exit(1); } } while(0)
static u32 gNativeAddress=0x020A0000;
static int fieldGateAvailable=1;
static u32 currentContext=0x00020002;
static u32 GetContext(void) {return currentContext;}
static const struct {u32 (*getContext)(void);} compat={GetContext};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compat)
#define OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(v) ((u16)(v))
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(v) ((u16)((v)>>16))
typedef struct {void *objects;} MapObjectMan;
typedef struct {int mapId;} Location;
struct FieldSystem {Location *location;void *mapObjectMan;};
#include "overworld_actor_system.h"
const OverworldBehaviorConditionServiceEntry gOverworldBehaviorConditionServiceEntry={OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION,sizeof(OverworldBehaviorConditionServiceEntry),NULL,NULL,NULL,NULL};
static OverworldBehaviorConditionServiceEntry wrongService;
const OverworldBehaviorConditionServiceEntry *OverworldBehaviorConditionService_Get(void) {return fieldGateAvailable==1 ? &gOverworldBehaviorConditionServiceEntry : fieldGateAvailable==2 ? &wrongService : NULL;}
'''
suffix = r'''
static OverworldQueryCodeAddonState state;
/* Measured Route 29 owner before the legitimate 2/2 -> 3/3 seam. */
static OverworldQueryCodeAddonOwner owner={0x022B125C,2,2};
static u8 *original,*input,*loaded;
static u32 length;
static u32 expectedMember=37;
static int loads,frees,caches,drains,loadResult=1,drainResult=1,expectRawFree=0;
static BOOL FakeLoad(u32 member,u32 expected,void **blob,u32 *size)
{
    CHECK(member==expectedMember && expected==length);
    ++loads; loaded=malloc(length); CHECK(loaded);
    memcpy(loaded,input,length); *blob=loaded; *size=length;
    return loadResult;
}
static void FakeFree(void *blob)
{
    CHECK(blob==loaded);
    CHECK(!state.entry && !state.blob && !state.phase);
    CHECK(!gOverworldQueryCodeAddonState.entry && !gOverworldQueryCodeAddonState.blob && !gOverworldQueryCodeAddonState.phase);
    if(expectRawFree) CHECK(!memcmp(loaded,input,length));
    ++frees; free(blob); loaded=NULL;
}
static void CacheCommon(void *base,u32 bytes,int next)
{
    CHECK(base==loaded+64 && bytes==((OverworldQueryCodeAddonHeader*)loaded)->imageSize);
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&owner));
    CHECK(!gOverworldQueryCodeAddonState.entry);
    CHECK(caches==next-1); caches=next;
}
static void FakeFlush(const void *p,u32 n) { CacheCommon((void*)p,n,1); }
static void FakeWait(void) {
    CHECK(caches==1 && !OverworldQueryCodeAddon_Acquire(&state,&owner)); caches=2;
}
static void FakeInvalidate(void *p,u32 n) { CacheCommon(p,n,3); }
static BOOL FakeDrain(void *context) {
    CHECK(context==&owner && (state.phase==ADDON_DRAINING || state.phase==ADDON_REBINDING || gOverworldQueryCodeAddonState.phase==ADDON_DRAINING || gOverworldQueryCodeAddonState.phase==ADDON_REBINDING));
    CHECK(!OverworldQueryCodeAddon_Acquire(&gOverworldQueryCodeAddonState,&owner));
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&owner));
    ++drains; return drainResult;
}
static OverworldQueryCodeAddonOps ops={FakeLoad,FakeFree,FakeFlush,FakeWait,FakeInvalidate,FakeDrain};
static void Reset(void) {
    CHECK(!loaded); memset(&state,0,sizeof(state));
    input=original; caches=0; gNativeAddress=0x020A0000;
    loadResult=drainResult=1; expectRawFree=0;
}
static void GoodLoad(void) {
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_OK);
    CHECK(caches==3 && state.blob==loaded && state.entry==(void*)(loaded+64) && state.phase==ADDON_READY);
    CHECK(OverworldQueryCodeAddon_Acquire(&state,&owner)==state.entry);
}
static void Bad(u8 *bytes) {
    Reset(); input=bytes; expectRawFree=1;
    int oldFrees=frees;
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_BAD_PACKAGE);
    CHECK(frees==oldFrees+1 && !loaded && !caches && !state.entry && !state.blob && !state.phase);
}
static void Checksum(u8 *bytes) {
    ((OverworldQueryCodeAddonHeader*)bytes)->checksum=Addon_Checksum(bytes,length);
}
int main(int argc,char **argv)
{
    CHECK(OVERWORLD_QUERY_CODE_ADDON_VERSION==9
        && OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION==2);
    CHECK(gOverworldQueryCodeAddonServiceEntry.version==2
        && gOverworldQueryCodeAddonServiceEntry.state==&gOverworldQueryCodeAddonState
        && Field_Service()==&gOverworldQueryCodeAddonServiceEntry);
    CHECK(argc==2); FILE *f=fopen(argv[1],"rb"); CHECK(f);
    CHECK(!fseek(f,0,SEEK_END)); long n=ftell(f); CHECK(n>=64);
    length=(u32)n; CHECK(!fseek(f,0,SEEK_SET));
    original=malloc(length); CHECK(original && fread(original,1,length,f)==length); fclose(f);
    Reset(); GoodLoad();
    const OverworldQueryCodeAddonHeader *h=(void*)original;
    const u32 *rel=(void*)(original+h->relocationOffset);
    const OverworldQueryCodeAddonImport *imports=(void*)(original+h->importOffset);
    CHECK(h->relocationCount>=OVERWORLD_QUERY_CODE_ADDON_CALLBACKS && h->importCount>=3);
    for(u32 i=0;i<h->relocationCount;++i) {
        u32 offset=rel[i];
        CHECK(*(u32*)(loaded+64+offset)==0x020A0040+(*(u32*)(original+64+offset)-h->linkBase));
    }
    for(u32 i=0;i<h->importCount;++i)
        CHECK(*(u32*)(loaded+64+imports[i].offset)==imports[i].target);
    OverworldQueryCodeAddonOwner stale=owner; ++stale.mapGeneration;
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&stale));
    int oldLoads=loads;
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_OK && loads==oldLoads);
    CHECK(OverworldQueryCodeAddon_Load(&state,&stale,&ops,37,length)==OVERWORLD_QUERY_ADDON_BUSY && loads==oldLoads);
    drainResult=0; int oldFrees=frees;
    CHECK(OverworldQueryCodeAddon_Unload(&state,&ops,&owner)==OVERWORLD_QUERY_ADDON_DRAIN_PENDING);
    CHECK(state.blob==loaded && state.phase==ADDON_DRAINING && frees==oldFrees);
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_BUSY);
    drainResult=1;
    CHECK(OverworldQueryCodeAddon_Unload(&state,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK && frees==oldFrees+1);
    CHECK(OverworldQueryCodeAddon_Unload(&state,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    Reset(); GoodLoad();
    oldLoads=loads; oldFrees=frees; int oldCaches=caches,oldDrains=drains;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&owner,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK && drains==oldDrains);
    stale=owner; ++stale.fieldEpoch;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_INVALID);
    stale=owner; stale.fieldIdentity+=4;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_INVALID);
    stale=owner; ++stale.mapGeneration; drainResult=0;
    const OverworldQueryCodeAddonEntry *sameImage=state.entry;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_DRAIN_PENDING);
    CHECK(state.phase==ADDON_REBINDING && state.owner.mapGeneration==owner.mapGeneration);
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&owner) && !OverworldQueryCodeAddon_Acquire(&state,&stale));
    CHECK(loads==oldLoads && frees==oldFrees && caches==oldCaches);
    drainResult=1;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    CHECK(state.entry==sameImage && OverworldQueryCodeAddon_Acquire(&state,&stale)==sameImage);
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&owner));
    CHECK(loads==oldLoads && frees==oldFrees && caches==oldCaches);
    CHECK(OverworldQueryCodeAddon_Unload(&state,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    /* Actor header transitions advance both generations while retaining the
     * same Field. The exact image stays private until its old query drains. */
    Reset(); GoodLoad(); oldLoads=loads; oldFrees=frees; oldCaches=caches;
    sameImage=state.entry; oldDrains=drains;
    for(int kind=0;kind<5;++kind) {
        stale=owner;
        switch(kind) {
        case 0:stale.fieldIdentity+=4; ++stale.fieldEpoch; ++stale.mapGeneration;break;
        case 1:++stale.fieldEpoch;break;
        case 2:stale.fieldEpoch+=2; stale.mapGeneration+=2;break;
        case 3:--stale.fieldEpoch; --stale.mapGeneration;break;
        case 4:stale.fieldEpoch=0; ++stale.mapGeneration;break;
        }
        CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_INVALID);
        CHECK(drains==oldDrains && state.phase==ADDON_READY && Addon_SameOwner(&state.owner,&owner));
        CHECK(OverworldQueryCodeAddon_Acquire(&state,&owner)==sameImage);
    }
    stale=owner; ++stale.fieldEpoch; ++stale.mapGeneration; drainResult=0;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_DRAIN_PENDING);
    CHECK(state.phase==ADDON_REBINDING && Addon_SameOwner(&state.owner,&owner));
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&owner) && !OverworldQueryCodeAddon_Acquire(&state,&stale));
    CHECK(loads==oldLoads && frees==oldFrees && caches==oldCaches && state.entry==sameImage);
    drainResult=1;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    CHECK(Addon_SameOwner(&state.owner,&stale) && OverworldQueryCodeAddon_Acquire(&state,&stale)==sameImage);
    CHECK(!OverworldQueryCodeAddon_Acquire(&state,&owner));
    CHECK(loads==oldLoads && frees==oldFrees && caches==oldCaches);
    CHECK(OverworldQueryCodeAddon_Unload(&state,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    OverworldQueryCodeAddonOwner savedOwner=owner;
    owner.fieldEpoch=owner.mapGeneration=0xFFFF; Reset(); GoodLoad(); sameImage=state.entry;
    stale=owner; stale.fieldEpoch=stale.mapGeneration=1;
    CHECK(OverworldQueryCodeAddon_Rebind(&state,&stale,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    CHECK(OverworldQueryCodeAddon_Acquire(&state,&stale)==sameImage && !OverworldQueryCodeAddon_Acquire(&state,&owner));
    CHECK(OverworldQueryCodeAddon_Unload(&state,&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    owner=savedOwner;
    u8 *bad=malloc(length); CHECK(bad);
    for(int kind=0;kind<18;++kind) {
        memcpy(bad,original,length); OverworldQueryCodeAddonHeader *b=(void*)bad;
        u32 *r=(void*)(bad+b->relocationOffset);
        OverworldQueryCodeAddonImport *im=(void*)(bad+b->importOffset);
        switch(kind) {
        case 0:b->version=OVERWORLD_QUERY_CODE_ADDON_VERSION+1;break;
        case 1:b->headerSize=60;break;
        case 2:b->entrySize=60;break;
        case 3:b->blobSize-=4;break;
        case 4:b->imageSize-=4;break;
        case 5:b->relocationOffset+=4;break;
        case 6:b->reserved[1]=1;break;
        case 7:r[1]=r[0];break;
        case 8:r[b->relocationCount-1]=b->imageSize;break;
        case 9:im[b->importCount-1].target=0x023DEE01;break;
        case 10:*(u32*)(bad+64+im[b->importCount-1].offset)^=2;break;
        case 11:r[0]=16;break;
        case 12:*(u32*)(bad+64+r[0])&=~1u;break;
        case 13:*(u32*)(bad+64+r[b->relocationCount-1])=b->linkBase+b->imageSize+1;break;
        case 14:im[0].offset=r[0];break;
        case 15:((u16*)(bad+64))[5]=183;break;
        case 16:*(u32*)(bad+64+r[0])=b->linkBase-1;break;
        case 17:*(u32*)(bad+64+r[0])=b->linkBase+OVERWORLD_QUERY_CODE_ADDON_ENTRY_BYTES-1;break;
        }
        Checksum(bad); Bad(bad);
    }
    static const u32 expectedImports[]={0x023DEEA3,0x023DEEBF,0x023DEE4D,
        0x01FF9A49,0x01FF9C95,0x01FFA39D,0x023C2F75,
        0x02208201,0x0205C67D,0x0205C689,0x023C7EA9,0x01FFD2CD};
    u32 seen[12], seenCount=0;
    for(u32 index=0;index<h->importCount;++index) {
        u32 target=imports[index].target, k;
        for(k=0;k<seenCount && seen[k]!=target;++k) {}
        if(k<seenCount) continue;
        for(k=0;k<12 && expectedImports[k]!=target;++k) {}
        CHECK(k<12 && seenCount<12); seen[seenCount++]=target;
        memcpy(bad,original,length);
        OverworldQueryCodeAddonHeader *b=(void*)bad;
        OverworldQueryCodeAddonImport *im=(void*)(bad+b->importOffset);
        im[index].target=target^2;
        *(u32*)(bad+64+im[index].offset)=im[index].target;
        Checksum(bad); Bad(bad);
        /* A fixed Thumb owner must not be admitted in ARM mode. */
        memcpy(bad,original,length);
        b=(void*)bad; im=(void*)(bad+b->importOffset);
        im[index].target=target&~1u;
        *(u32*)(bad+64+im[index].offset)=im[index].target;
        Checksum(bad); Bad(bad);
    }
    CHECK(seenCount==12);
    /* Independent physical ABI inventory: every callback must stay Thumb,
     * including each span on either side of the two metadata gaps. */
    static const u16 callbackOffsets[]={20,24,28,32,36,40,44,48,52,56,60,64,68,72,
        84,88,92,96,112,116,120,124,128,132,136,140,144,148,152,156,160,164,168,
        172,176,180,184,188};
    CHECK(sizeof(callbackOffsets)/sizeof(callbackOffsets[0])==OVERWORLD_QUERY_CODE_ADDON_CALLBACKS);
    for(u32 index=0;index<OVERWORLD_QUERY_CODE_ADDON_CALLBACKS;++index) {
        memcpy(bad,original,length);
        *(u32*)(bad+64+callbackOffsets[index])&=~1u;
        Checksum(bad); Bad(bad);
    }
    memcpy(bad,original,length); bad[100]^=1; Bad(bad);
    Reset(); gNativeAddress=0x020A0002; input=original; expectRawFree=1;
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_BAD_PACKAGE);
    Reset(); gNativeAddress=0x02400000-length+4; expectRawFree=1;
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_BAD_PACKAGE);
    Reset(); loadResult=0; expectRawFree=1;
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,length)==OVERWORLD_QUERY_ADDON_LOAD_FAILED);
    Reset(); OverworldQueryCodeAddonOps incomplete=ops; incomplete.invalidateCode=NULL; oldLoads=loads;
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&incomplete,37,length)==OVERWORLD_QUERY_ADDON_INVALID && loads==oldLoads);
    stale=owner; stale.fieldIdentity=0;
    CHECK(OverworldQueryCodeAddon_Load(&state,&stale,&ops,37,length)==OVERWORLD_QUERY_ADDON_INVALID && loads==oldLoads);
    CHECK(OverworldQueryCodeAddon_Load(&state,&owner,&ops,37,0)==OVERWORLD_QUERY_ADDON_INVALID && loads==oldLoads);
    Reset(); expectedMember=OVERWORLD_QUERY_CODE_ADDON_MEMBER_ID;
    FieldSystem *field=(void*)(uintptr_t)owner.fieldIdentity;
    oldLoads=loads;
    fieldGateAvailable=0;
    CHECK(!OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch,owner.mapGeneration,&ops,&owner) && loads==oldLoads);
    CHECK(OverworldQueryCodeAddonField_Unload(&ops,&owner)==OVERWORLD_QUERY_ADDON_INVALID);
    fieldGateAvailable=2;
    CHECK(!OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch,owner.mapGeneration,&ops,&owner) && loads==oldLoads);
    fieldGateAvailable=1;
    CHECK(OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch,owner.mapGeneration,&ops,&owner));
    oldLoads=loads; oldFrees=frees; oldCaches=caches;
    sameImage=gOverworldQueryCodeAddonState.entry;
    CHECK(OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch,owner.mapGeneration,&ops,&owner)==sameImage && loads==oldLoads);
    CHECK(!OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch+1,owner.mapGeneration,&ops,&owner));
    drainResult=0;
    CHECK(!OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch,owner.mapGeneration+1,&ops,&owner));
    CHECK(gOverworldQueryCodeAddonState.phase==ADDON_REBINDING);
    drainResult=1;
    CHECK(OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch,owner.mapGeneration+1,&ops,&owner)==sameImage);
    CHECK(loads==oldLoads && frees==oldFrees && caches==oldCaches);
    CHECK(OverworldQueryCodeAddonField_Acquire(field,owner.fieldEpoch+1,owner.mapGeneration+2,&ops,&owner)==sameImage);
    CHECK(loads==oldLoads && frees==oldFrees && caches==oldCaches);
    CHECK(OverworldQueryCodeAddonField_Unload(&ops,&owner)==OVERWORLD_QUERY_ADDON_OK);
    free(bad); free(original);
    printf("production loader admission, cache order and drain controls passed; loads=%d frees=%d drains=%d\n",loads,frees,drains);
    return 0;
}
'''
fixture = HERE / 'loader_controls.c'
fixture.write_text(prefix + source + service_source + field_source + suffix)
exe = HERE / 'loader_controls'
compile_args = ['cc', '-std=c11', '-Wall', '-Wextra', '-Wno-unknown-attributes', '-Wno-ignored-attributes', '-I', str(ROOT/'include'), '-DOVERWORLD_QUERY_CODE_ADDON_PACKAGE_BYTES='+str(args.package.stat().st_size), str(fixture), '-o', str(exe)]
compiled = subprocess.run(compile_args, text=True, capture_output=True)
(HERE/'host-compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode: raise SystemExit(compiled.stderr)
run = subprocess.run([str(exe), str(args.package.resolve())],text=True,capture_output=True)
print(run.stdout+run.stderr,end='')
if run.returncode: raise SystemExit(run.returncode)
receipt = ROOT / 'build/tickets/query-code-addon-v2/host-lifecycle-receipt.json'
receipt.parent.mkdir(parents=True, exist_ok=True)
receipt.write_text(json.dumps({
    'scope':'production loader C; only native address conversion is replaced; typed ARM callbacks are not executed',
    'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'packageSha256':hashlib.sha256(args.package.read_bytes()).hexdigest(),
    'result':run.stdout.strip(),
    'fixture':"temporary extracted production C"},indent=2)+'\n')

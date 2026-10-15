"""Compile the unlinked shared tint module with engine/VRAM boundaries only.

Production palette parsing, blending, identity checks, MAT override and cleanup
run unchanged. Pointer tokens stand in for ARM's 32-bit pointers on a 64-bit
host. This is not a DS renderer, VRAM, or visual acceptance test.
"""

from pathlib import Path
import importlib.util
import os
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "lib/overworld/overworld_actor_appearance.c"
HEADER = ROOT / "include/overworld_actor_appearance.h"


def harness_source(mutate=False, queued=False, mutation=None, source_path=None):
    spec = importlib.util.spec_from_file_location(
        "appearance_extract", ROOT / "scripts/verify_overworld_role_controller.py")
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    actor = (ROOT / "include/overworld_actor_system.h").read_text()

    def declaration(prefix):
        first = actor.index(prefix)
        start = actor.index("{", first)
        end = extract.matching_delimiter(extract.strip_c_noncode(actor), start, "{", "}")
        return actor[first:actor.index(";", end) + 1] + "\n"

    header = re.sub(r'^#include .*$', '', HEADER.read_text(), flags=re.M)
    source = re.sub(r'^#include .*$', '', (source_path or SOURCE).read_text(), flags=re.M)
    # Native placement has no effect on the host reducer. Mach-O uses a
    # different section spelling; keep the same noinline function body.
    source = source.replace('section(".overworld_appearance_release"), ', "")
    # Replace only storage, pointer-width and native SDK boundaries. The
    # resource parser, current-object check and every lifecycle path remain C.
    for name, replacement in BOUNDARIES.items():
        first = source.index(name + "(")
        first = source.rfind("\nstatic ", 0, first) + 1
        start = source.index("{", first)
        end = extract.matching_delimiter(extract.strip_c_noncode(source), start, "{", "}")
        source = source[:first] + replacement + source[end + 1:]
    if mutate:
        exact = "&& actor->handle.generation == view->handle.generation"
        if source.count(exact) != 1:
            raise ValueError("generation predicate changed")
        source = source.replace(exact, "&& TRUE")
    # Execute the production queue call and pending-count gate. Only native
    # SDK calls and ARM pointer representation are replaced on the host.
    source = source.replace("((AppearanceFlushFunc)0x020D2894)", "HostFlush")
    source = source.replace("((AppearanceQueueFunc)0x020205D9)", "HostQueue")
    source = source.replace("((AppearancePendingFunc)0x02020639)", "HostPending")
    # Retained old-source RED uses these same SDK seams, without queue credit.
    source = source.replace("((AppearanceBeginLoadFunc)0x020D0AD4)", "HostBegin")
    source = source.replace("((AppearanceBeginLoadFunc)0x020D0B74)", "HostEnd")
    source = source.replace("((AppearanceLoadFunc)0x020D0B08)", "HostImmediateLoad")
    if mutation is not None:
        exact, replacement = QUEUE_MUTATIONS[mutation]
        if source.count(exact) != 1:
            raise ValueError("queue predicate changed: " + mutation)
        source = source.replace(exact, replacement)
    prefix = (PRELUDE + declaration("typedef struct OverworldActorHandle {")
              + declaration("typedef struct OverworldActorStateSnapshot {")
              + declaration("typedef enum OverworldActorRole {")
              + header + SUPPORT + QUEUE_SUPPORT + source)
    if queued:
        return prefix + DRIVER.split(" OverworldActorAppearanceInput input=", 1)[0] + QUEUE_CASES
    # The original parser/blend/generation controls observe a completed stock
    # VBlank after each actual Update. Delayed controls below keep it pending.
    wrapper = """static OverworldActorAppearanceResult HostUpdateAndDrain(
        MapObjectMan *manager, const OverworldActorAppearanceInput *input)
        { OverworldActorAppearanceResult result=OverworldActorAppearance_Update(manager,input);
          HostDrain();return result; }
"""
    return prefix + wrapper + DRIVER.replace("OverworldActorAppearance_Update(", "HostUpdateAndDrain(")


BOUNDARIES = {
    "Appearance_RamSpan": """static BOOL Appearance_RamSpan(const void *p, u32 n)
        { return HostSpan(p, n, FALSE); }""",
    "Appearance_ScratchSpan": """static BOOL Appearance_ScratchSpan(const void *p, u32 n)
        { return HostSpan(p, n, TRUE); }""",
    "Appearance_Pointer": """static void *Appearance_Pointer(const void *p, u32 off)
        { return HostPointer(Appearance_U32(p, off)); }""",
    "Appearance_GetCallback": """static AppearanceCallback Appearance_GetCallback(void *p)
        { u32 v=Appearance_U32(p, APPEARANCE_DRAW_CALLBACK);
          return v==1 ? Appearance_ApplyMaterial : v==2 ? Foreign : NULL; }""",
    "Appearance_SetCallback": """static void Appearance_SetCallback(void *p, AppearanceCallback cb)
        { check(cb==NULL || cb==Appearance_ApplyMaterial || cb==Foreign, "callback boundary");
          *(u32 *)((u8 *)p + APPEARANCE_DRAW_CALLBACK)=cb==Appearance_ApplyMaterial ? 1 : cb==Foreign ? 2 : 0; }""",
    "Appearance_FreePalette": """static void Appearance_FreePalette(u32 k)
        { HostFreeKey(k); }""",
    "Appearance_AllocPalette": """static u32 Appearance_AllocPalette(u32 n)
        { check(n==64, "fixture palette bytes"); ++allocations;
          u32 key=(8u<<16) | (0x100u+allocations*8); liveKeys[key&255]=1; return key; }""",
}


PRELUDE = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int32_t s32; typedef int BOOL;
u32 IsOverlayLoaded(u32 overlayId);
#define TRUE 1
#define FALSE 0
#define OVERWORLD_ACTOR_SYSTEM_ABI_VERSION 2
#define OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS 10
#define HEAPID_WORLD 11
#define MAPOBJECTFLAG_ACTIVE 1
#define MAPOBJECTFLAG_UNK22 (1u<<22)
typedef struct LocalMapObject {
 u32 flags; int id; uintptr_t unkB4;
 void (*unkC8)(struct LocalMapObject *); u8 unk108[32];
} LocalMapObject;
typedef struct MapObjectMan {
 u32 object_count; LocalMapObject *objects; void *fsys;
} MapObjectMan;
"""


SUPPORT = r"""
typedef struct { const void *p; u32 n; BOOL scratch; } Span;
static Span spans[80]; static u32 spanCount;
static void *pointers[80]; static u32 pointerCount;
static u32 allocations, frees, uploads, heapCount;
static u8 liveKeys[256]; static u16 uploaded[32];
static void check(int ok,const char *label)
 { if(!ok) { fprintf(stderr,"%s\n",label); exit(1); } }
static void Register(const void *p,u32 n,BOOL scratch)
 { spans[spanCount++]=(Span){p,n,scratch}; }
static BOOL HostSpan(const void *p,u32 n,BOOL allowScratch)
 { uintptr_t a=(uintptr_t)p;
   for(u32 i=0;i<spanCount;i++) {
    uintptr_t lo=(uintptr_t)spans[i].p;
    if(p && (!spans[i].scratch || allowScratch) && a>=lo
       && a-lo<=spans[i].n && n<=spans[i].n-(a-lo)) return TRUE;
   } return FALSE; }
static u32 Token(void *p)
 { pointers[++pointerCount]=p; return pointerCount; }
static void *HostPointer(u32 token)
 { check(token<=pointerCount,"known native pointer token"); return pointers[token]; }
static void *sys_AllocMemory(u32 heap,u32 n)
 { check(heap==11,"world heap"); void *p=calloc(1,n); ++heapCount; Register(p,n,FALSE); return p; }
static void sys_FreeMemoryEz(void *p)
 { --heapCount; for(u32 i=0;i<spanCount;i++) if(spans[i].p==p) spans[i].p=NULL; free(p); }
static void HostFreeKey(u32 key);
static void Appearance_ApplyMaterial(void *);
static void Foreign(void *unused) { (void)unused; }
"""


DRIVER = r"""
typedef union { u32 words[48]; u8 bytes[192]; } Image;
static void Put32(void *p,u32 off,u32 v) { *(u32 *)((u8 *)p+off)=v; }
static void Put16(void *p,u32 off,u16 v) { *(u16 *)((u8 *)p+off)=v; }
int main(void)
{
 LocalMapObject objects[10]={0}; MapObjectMan manager={10,objects,&manager};
 OverworldActorStateSnapshot actors[10]={0};
 u32 model[16]={0}; Image texture={0}; u32 draws[2][49]={{0}};
 u32 render[46]={0},material[14]={0};
 Register(&manager,sizeof(manager),FALSE); Register(objects,sizeof(objects),FALSE);
 Register(actors,sizeof(actors),FALSE); Register(model,sizeof(model),FALSE);
 Register(&texture,sizeof(texture),FALSE); Register(draws,sizeof(draws),FALSE);
 Register(render,sizeof(render),TRUE); Register(material,sizeof(material),TRUE);
 Put32(&texture,0,APPEARANCE_TEX_MAGIC); Put32(&texture,4,sizeof(texture));
 Put16(&texture,0x0e,0x3c); Put16(&texture,0x30,8); Put32(&texture,0x38,0x80);
 texture.bytes[0x3d]=1; Put16(&texture,0x3e,16); Put16(&texture,0x42,8);
 Put16(&texture,0x44,4); Put32(&texture,0x48,3u<<26);
 u16 *colors=(u16 *)(texture.bytes+0x80);
 for(u32 i=0;i<32;i++) colors[i]=(i&15)==0 ? 0xffff : i%2 ? 0x7c00 : 0x03ff;
 Image originalTexture=texture;
 u32 modelToken=Token(model), textureToken=Token(&texture);
 for(u32 slot=0;slot<2;slot++) {
  actors[slot]=(OverworldActorStateSnapshot){.version=2,.size=88,
   .handle={slot,1,2,3,4,0},.subjectIdentity=100+slot,.authorityGeneration=1,
   .engineAnchorGeneration=1,.presentationGeneration=1,.species=234,.level=50,
   .role=OVERWORLD_ACTOR_ROLE_WILD,.active=1,.presentationAttached=1};
  objects[slot].flags=1; objects[slot].id=0xe0+slot; objects[slot].unkB4=(uintptr_t)&manager;
  objects[slot].unkC8=(void (*)(LocalMapObject *))(uintptr_t)0x021F7895;
  Put32(objects[slot].unk108,0,Token(draws[slot]));
  Put32(draws[slot],0x34,modelToken); Put32(draws[slot],0x88,modelToken);
  Put32(draws[slot],0x8c,textureToken); Put32(draws[slot],0x9c,(8u<<16)|0x20);
 }
 ((u8 *)draws[0])[0x54]=9; ((u8 *)draws[0])[0x55]=1;
 OverworldActorAppearanceInput input={&actors[0],&objects[0],3,1,0};
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_TINTED,"first red tint");
 const OverworldActorAppearanceSnapshot *view=OverworldActorAppearance_Inspect(0);
 check(view->mode==OVERWORLD_ACTOR_APPEARANCE_RED && view->strength==3,"red priority");
 check(uploaded[1]==(6|(25<<10)) && uploaded[2]==(31|(25<<5)),"blend original colors");
 check(uploaded[0]==0xffff && uploaded[16]==0xffff,"preserve each color zero");
 check(((u8 *)draws[0])[0x54]==4 && ((u8 *)draws[0])[0x55]==2,"MAT before emission");
 check(view->originalPalettePointer!=view->tintedPalettePointer,"separate palette buffers");
 input.actor=&actors[1]; input.pokemon=&objects[1]; input.redStrength=0; input.restTint=0;
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_CLEAR
    && Appearance_GetCallback(draws[1])==NULL && allocations==1,"same species stays normal");
 input.actor=&actors[0]; input.pokemon=&objects[0]; input.redStrength=3;
 Put32(render,4,Token((u8 *)draws[0]+0x30)); Put32(render,0xb0,Token(material));
 material[4]=3u<<26; material[5]=0x12;
 Appearance_GetCallback(draws[0])(render);
 check(material[5]==((view->privatePaletteKey&0xffff)>>1)+2 && view->appliedMaterials==1,"retain subpalette offset");
 check(!memcmp(&texture,&originalTexture,sizeof(texture)),"shared resource never changes");
 input.redStrength=12; OverworldActorAppearance_Update(&manager,&input);
 check(uploaded[1]==(23|(8<<10)),"stronger damage red");
 u32 before=uploads; OverworldActorAppearance_Update(&manager,&input);
 check(uploads==before,"unchanged palette not uploaded again");
 u32 pulseKey=view->privatePaletteKey, pulseAllocations=allocations, pulseFrees=frees;
 input.damageActive=1; input.redStrength=0; input.restTint=1;
 OverworldActorAppearance_Update(&manager,&input);
 check(view->mode==OVERWORLD_ACTOR_APPEARANCE_RED && view->strength==0,
   "injured OFF stays red instead of blue");
 check(!memcmp(uploaded,colors,64),"injured OFF uploads exact original palette");
 material[5]=0x12; Appearance_GetCallback(draws[0])(render);
 check(material[5]==0x12,"OFF uses normal game palette");
 before=uploads;OverworldActorAppearance_Update(&manager,&input);
 check(uploads==before && view->privatePaletteKey==pulseKey && allocations==pulseAllocations
   && frees==pulseFrees,"OFF dwell retains one private palette without churn");
 input.redStrength=3;OverworldActorAppearance_Update(&manager,&input);
 check(view->privatePaletteKey==pulseKey && allocations==pulseAllocations && frees==pulseFrees,
   "red resumes on the same private palette");
 input.damageActive=2;
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_INVALID,
   "damageActive is a strict boolean");
 input.damageActive=0;before=uploads;
 input.redStrength=0; input.restTint=1; OverworldActorAppearance_Update(&manager,&input);
 check(uploaded[2]==(27|(27<<5)|(4<<10)) && view->mode==OVERWORLD_ACTOR_APPEARANCE_BLUE,"slight blue from original");
 Appearance_SetCallback(draws[0],Foreign); ((u8 *)draws[0])[0x55]=3;
 input.redStrength=12; check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_YIELDED,"recall keeps callback");
 check(Appearance_GetCallback(draws[0])==Foreign && uploads==before+1,"no work under recall");
 Appearance_SetCallback(draws[0],Appearance_ApplyMaterial);
 OverworldActorAppearance_Update(&manager,&input);
 check(uploaded[1]==(23|(8<<10)),"resume after recall");
 Appearance_SetCallback(draws[0],Foreign); input.redStrength=0; input.restTint=0;
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_YIELDED,"full HP under recall");
 Appearance_SetCallback(draws[0],Appearance_ApplyMaterial); material[5]=0x12;
 Appearance_ApplyMaterial(render); check(material[5]==0x12,"cleared tint stops immediately");
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_CLEAR
    && heapCount==0 && allocations==frees && Appearance_GetCallback(draws[0])==NULL
    && ((u8 *)draws[0])[0x54]==9 && ((u8 *)draws[0])[0x55]==1,"full HP restores original callback settings");
 input.redStrength=3; OverworldActorAppearance_Update(&manager,&input);
 u32 oldKey=OverworldActorAppearance_Inspect(0)->privatePaletteKey;
 ++actors[0].handle.generation; material[5]=0x12;
 Appearance_ApplyMaterial(render); check(material[5]==0x12,"stale actor generation cannot tint");
 OverworldActorAppearance_Update(&manager,&input); view=OverworldActorAppearance_Inspect(0);
 check(view->handle.generation==2 && view->privatePaletteKey!=oldKey && view->appliedMaterials==0,"generation rebind owns fresh palette");
 for(u8 role=OVERWORLD_ACTOR_ROLE_FOLLOWER;role<=OVERWORLD_ACTOR_ROLE_MOUNTED;role++) {
  actors[0].role=role; ++actors[0].authorityGeneration; OverworldActorAppearance_Update(&manager,&input);
  material[5]=0x12; Appearance_ApplyMaterial(render);
  check(material[5]!=0x12 && OverworldActorAppearance_Inspect(0)->role==role,"one shared role path");
 }
 memset((u8 *)draws[0]+0x30,0,0x54); Put32(draws[0],0x34,modelToken);
 ++actors[0].presentationGeneration;
 OverworldActorAppearance_Update(&manager,&input);
 check(Appearance_GetCallback(draws[0])==Appearance_ApplyMaterial,"stock render reload rebinds");
 material[5]=0x14; Appearance_ApplyMaterial(render); check(material[5]==0x14,"bad material palette offset fails closed");
 ++actors[0].subjectIdentity; material[5]=0x12; Appearance_ApplyMaterial(render);
 check(material[5]==0x12,"changed Pokemon identity cannot tint");
 OverworldActorAppearance_Forget(&manager,0);
 check(heapCount==0 && allocations==frees && OverworldActorAppearance_Inspect(0)==NULL
    && ((u8 *)draws[0])[0x54]==0 && ((u8 *)draws[0])[0x55]==0,"forget releases once after stock reload");
 Put32(&texture,0x48,7u<<26);
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED && heapCount==0,"unsupported format");
 Put32(&texture,0x48,3u<<26); Put16(&texture,0x30,0x2008);
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED,"size cannot wrap to valid palette");
 Put16(&texture,0x30,8); Put32(&texture,0x38,0xc0);
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED,"palette source bound");
 Put32(&texture,0x38,0x81);
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED,"unaligned palette rejected");
 Put32(&texture,0x38,0x80); Put16(&texture,0x0e,0x3d);
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED,"unaligned dictionary rejected");
 Put16(&texture,0x0e,0x3c); OverworldActorAppearance_Update(&manager,&input);
 objects[0].flags=0; OverworldActorAppearance_Forget(&manager,0);
 check(heapCount==0 && allocations==frees,"removed object cleanup");
 objects[0].flags=1; Put32(draws[0],0x50,0);
 OverworldActorAppearance_Update(&manager,&input); OverworldActorAppearance_Reset(&manager);
 check(heapCount==0 && allocations==frees && Appearance_GetCallback(draws[0])==NULL,"field reset cleanup");
 puts("shared appearance palette and generation checks passed"); return 0;
}
"""


# One bounded stock queue stand-in. It retains the source address and bytes
# until HostDrain, and rejects freeing/reusing either owner before completion.
QUEUE_SUPPORT = r"""

typedef struct {const void *source;u32 destination,size;u8 before[64];BOOL used;} Queued;
static Queued queued[8];static u32 pendingCount,registered;static BOOL failQueue;
static u32 __attribute__((unused)) HostPending(void){return pendingCount;}
static void __attribute__((unused)) HostFlush(const void *p,u32 n){check(HostSpan(p,n,FALSE),"flush owned RAM");}
static BOOL __attribute__((unused)) HostQueue(u32 type,u32 dst,const void *p,u32 n){
 check(type==1 && n==64 && (dst&7)==0 && liveKeys[(dst>>3)&255],"queue exact texture-palette destination");
 ++pendingCount;if(failQueue)return FALSE;
 for(u32 i=0;i<8;i++)if(!queued[i].used){queued[i]=(Queued){.source=p,.destination=dst,.size=n,.used=TRUE};memcpy(queued[i].before,p,n);++registered;return TRUE;}
 check(FALSE,"bounded fixture queue");return FALSE;
}
static void HostDrain(void){
 for(u32 i=0;i<8;i++)if(queued[i].used){
  check(HostSpan(queued[i].source,queued[i].size,FALSE),"queued source remains allocated");
  check(liveKeys[(queued[i].destination>>3)&255],"queued key remains live");
  check(!memcmp(queued[i].before,queued[i].source,queued[i].size),"queued source was changed before completion");
  memcpy(uploaded,queued[i].source,queued[i].size);++uploads;queued[i].used=FALSE;
 }
 pendingCount=0;
}
static void HostFreeKey(u32 key){
 for(u32 i=0;i<8;i++)check(!queued[i].used || queued[i].destination!=((key&0xffff)<<3),"queued key must stay live");
 check(key!=0 && liveKeys[key&255],"private key released once");liveKeys[key&255]=0;++frees;
}
static void __attribute__((unused)) HostBegin(void){}
static void __attribute__((unused)) HostEnd(void){}
static void __attribute__((unused)) HostImmediateLoad(const void *p,u32 dst,u32 n){(void)dst;memcpy(uploaded,p,n);++uploads;}
"""

QUEUE_CASES = r"""

 OverworldActorAppearanceInput input={&actors[0],&objects[0],3,0,1};
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_TINTED,"queue initial tint");
 const OverworldActorAppearanceSnapshot *view=OverworldActorAppearance_Inspect(0);
 check(view!=NULL && pendingCount==1 && registered==1 && uploads==0,"Update queues without immediate SDK upload");
 Put32(render,4,Token((u8 *)draws[0]+0x30));Put32(render,0xb0,Token(material));material[4]=3u<<26;material[5]=0x12;
 Appearance_ApplyMaterial(render);check(material[5]==0x12,"pending palette cannot enter MAT");
 input.redStrength=12;u32 beforeRegistered=registered;
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_YIELDED,"same-frame second update waits");
 check(registered==beforeRegistered && uploads==0,"one queued source is not rewritten or requeued");
 HostDrain();check(uploaded[1]==(6|(25<<10)),"queue consumed original three-strength bytes");
 Appearance_ApplyMaterial(render);check(material[5]!=0x12,"completed own palette can enter MAT");
 OverworldActorAppearance_Update(&manager,&input);check(pendingCount==1,"new strength queues after prior completion");
 OverworldActorAppearance_Forget(&manager,0);
 view=OverworldActorAppearance_Inspect(0);check(view && view->mode==OVERWORLD_ACTOR_APPEARANCE_NONE && view->strength==0 && heapCount==1 && frees==0,"Forget retains queued source and clears visible tint");
 material[5]=0x12;Appearance_ApplyMaterial(render);check(material[5]==0x12,"forgotten pending tint uses normal MAT");
 HostDrain();OverworldActorAppearance_Forget(&manager,0);check(heapCount==0 && frees==allocations,"Forget frees exactly after completion");
 input.redStrength=3;OverworldActorAppearance_Update(&manager,&input);
 input.damageActive=0;input.redStrength=0;
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_CLEAR && heapCount==1,"full HP clears immediately but retains queued storage");
 material[5]=0x12;Appearance_ApplyMaterial(render);check(material[5]==0x12,"full HP never uses private pending MAT");
 HostDrain();OverworldActorAppearance_Update(&manager,&input);check(heapCount==0,"full HP deferred release ends next frame");
 input.damageActive=1;input.redStrength=3;OverworldActorAppearance_Update(&manager,&input);view=OverworldActorAppearance_Inspect(0);u32 oldKey=view->privatePaletteKey,oldAllocations=allocations;
 ++actors[0].handle.generation;
 check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_INVALID && allocations==oldAllocations && liveKeys[oldKey&255],"new generation waits for old queued owner");
 material[5]=0x12;Appearance_ApplyMaterial(render);check(material[5]==0x12,"stale generation cannot tint");
 HostDrain();OverworldActorAppearance_Update(&manager,&input);view=OverworldActorAppearance_Inspect(0);
 check(view->handle.generation==2 && view->privatePaletteKey!=oldKey && !liveKeys[oldKey&255],"completed old owner releases before exact new generation");
 input.actor=&actors[1];input.pokemon=&objects[1];input.damageActive=0;input.redStrength=0;input.restTint=1;OverworldActorAppearance_Update(&manager,&input);
 check(heapCount==2 && pendingCount==2,"two role-independent palettes queued");
 OverworldActorAppearance_Reset(&manager);check(heapCount==2 && sAppearance!=NULL,"Reset advances past pending records without looping or freeing");
 check(!Appearance_ClearForUnload(&manager),"parent unload waits for queued storage");
 HostDrain();check(Appearance_ClearForUnload(&manager) && heapCount==0 && allocations==frees,"parent unload releases after real stock drain");
 input.actor=&actors[0];input.pokemon=&objects[0];input.damageActive=1;input.redStrength=3;input.restTint=0;OverworldActorAppearance_Update(&manager,&input);
 Appearance_SetCallback(draws[0],Foreign);check(!Appearance_ClearForUnload(&manager),"foreign recall still blocks unload");
 HostDrain();check(!Appearance_ClearForUnload(&manager),"completed queue does not weaken recall guard");
 Appearance_SetCallback(draws[0],Appearance_ApplyMaterial);check(Appearance_ClearForUnload(&manager) && heapCount==0,"recall restoration permits old guarded cleanup");
 OverworldActorAppearance_Update(&manager,&input);HostDrain();Appearance_ApplyMaterial(render);
 check(Appearance_GetCallback(draws[0])==Appearance_ApplyMaterial,"prior tint callback is installed before queue failure");
 input.redStrength=12;failQueue=TRUE;check(OverworldActorAppearance_Update(&manager,&input)==OVERWORLD_ACTOR_APPEARANCE_YIELDED,"queue rejection is pending retry");
 material[5]=0x12;Appearance_ApplyMaterial(render);check(material[5]==0x12,"rejected upload cannot tint");
 OverworldActorAppearance_Forget(&manager,0);check(heapCount==0,"unregistered source can release despite foreign queue count");
 HostDrain();failQueue=FALSE;
 OverworldActorAppearance_Update(&manager,&input);actors[0].active=0;
 material[5]=0x12;Appearance_ApplyMaterial(render);check(material[5]==0x12,"removed actor cannot use pending tint");
 OverworldActorAppearance_Forget(&manager,0);check(heapCount==1,"removed actor source survives queued read");HostDrain();OverworldActorAppearance_Forget(&manager,0);
 check(heapCount==0 && allocations==frees && !memcmp(&texture,&originalTexture,sizeof(texture)),"all exact owners released with shared resources unchanged");
 puts("actual appearance delayed-queue lifecycle controls passed");return 0;
}
"""

QUEUE_MUTATIONS = {
    "direct-sdk-upload": (
        "    return HostQueue(1, (key & 0xFFFF) << 3, palette, bytes);",
        "    HostImmediateLoad(palette, (key & 0xFFFF) << 3, bytes); return TRUE;"),
    "release-before-complete": (
        "    if (!Appearance_CompleteUpload(record)) {\n        return FALSE;\n    }\n    draw = manager == record->manager",
        "    draw = manager == record->manager"),
    "write-before-complete": (
        "    if (!Appearance_CompleteUpload(record)) {\n        return OVERWORLD_ACTOR_APPEARANCE_YIELDED;\n    }", ""),
    "unload-before-complete": (
        "    if (sAppearance != NULL) {\n        return FALSE;\n    }", ""),
    "yielded-mat": ("            || record->view.yielded\n", ""),
}


class ActorAppearanceTests(unittest.TestCase):
    def compile_run(self, mutate=False, queued=False, mutation=None, source_path=None):
        with tempfile.TemporaryDirectory(prefix="actor-appearance-") as directory:
            source, binary = Path(directory) / "appearance.c", Path(directory) / "appearance"
            source.write_text(harness_source(mutate, queued, mutation, source_path))
            result = subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True)

    def test_production_palette_and_generation_lifecycle(self):
        result = self.compile_run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("shared appearance palette and generation checks passed", result.stdout)

    def test_removing_generation_guard_is_rejected(self):
        result = self.compile_run(mutate=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale actor generation cannot tint", result.stderr)


    def test_delayed_queue_owns_source_until_vblank(self):
        result = self.compile_run(queued=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("actual appearance delayed-queue lifecycle controls passed", result.stdout)

    def test_direct_sdk_upload_is_rejected(self):
        result = self.compile_run(queued=True, mutation="direct-sdk-upload")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Update queues without immediate SDK upload", result.stderr)

    def test_pending_palette_cannot_be_freed(self):
        result = self.compile_run(queued=True, mutation="release-before-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("queued key must stay live", result.stderr)

    def test_pending_source_cannot_be_rewritten(self):
        result = self.compile_run(queued=True, mutation="write-before-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same-frame second update waits", result.stderr)

    def test_parent_cannot_unload_with_pending_source(self):
        result = self.compile_run(queued=True, mutation="unload-before-complete")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("parent unload waits for queued storage", result.stderr)

    def test_rejected_upload_cannot_use_installed_tint_callback(self):
        result = self.compile_run(queued=True, mutation="yielded-mat")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejected upload cannot tint", result.stderr)


if __name__ == "__main__":
    unittest.main()

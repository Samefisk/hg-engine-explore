#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define OVERWORLD_EMOTE_HOST
#define TYPES_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef int BOOL;
typedef struct {s32 x,y,z;} VecFx32;
#define TRUE 1
#define FALSE 0
#include "overworld_emote_slots_internal.h"
struct LocalMapObject { unsigned id, map; };
struct SysTask { void (*callback)(SysTask *,void *); void *data; unsigned active; };
typedef struct { unsigned member; unsigned char tex[1024],palette[32]; } Asset;
typedef struct { unsigned active; u32 textureKey,paletteKey; void *geometry; } Model;
typedef struct { const OverworldEmoteNativeDescriptor *descriptor; OverworldEmoteNativeData data; OverworldEmoteInit init; VecFx32 pos; unsigned active; } Effect;
typedef struct { int type; u32 destination; const void *source; unsigned bytes; } Transfer;
static void *context[9];
static OverworldEmoteOwner *owner;
static SysTask task;
static Model models[16];
static Effect effects[16];
static Transfer transfers[64];
static unsigned pending,allocations,allocationAttempts,freeCount,modelCount,modelFrees,texCount,palCount;
static unsigned nextKey,texFrees,palFrees,plays,stops,nativeUpdates,taskCreations,taskDestructions;
static unsigned failAllocation,failTask,failTex,failPal,failFactory,failModel,failTransfer;
static unsigned validContext=1;
static u32 textureKeys[32],paletteKeys[32];
typedef struct { void *pointer; unsigned bytes; } Allocation;
static Allocation heap[64];
const u8 ov01_0220952C[24]={0};
static void *Allocate(unsigned size){allocationAttempts++;if(failAllocation==allocationAttempts)return NULL;void*p=malloc(size);assert(p);memset(p,0xA5,size);for(unsigned i=0;i<64;i++)if(!heap[i].pointer){heap[i]=(Allocation){p,size};allocations++;return p;}assert(0);return NULL;}
void MIi_CpuClear32(u32 value,void *destination,u32 bytes){assert(value==0&&destination&&bytes==sizeof(OverworldEmoteSlot));memset(destination,0,bytes);}
void *ov01_021F141C(void *c,int size,int end){assert(c==context&&validContext&&(end==0||end==1));return Allocate(size);}
void ov01_021F1448(void *p){assert(p&&allocations);unsigned found=0;for(unsigned i=0;i<64;i++)if(heap[i].pointer==p){for(unsigned j=0;j<pending;j++){uintptr_t source=(uintptr_t)transfers[j].source;assert(source<(uintptr_t)p||source>=(uintptr_t)p+heap[i].bytes);}heap[i]=(Allocation){0};found++;}assert(found==1);allocations--;freeCount++;free(p);}
void *ov01_021F1450(void *c,int id){assert(c==context&&validContext&&id==18);return owner;}
int ov01_021F149C(void*c,int member){assert(c==context&&validContext&&member>=0);return sizeof(Asset);}
void ov01_021F14A8(void*c,int member,void*p){assert(c==context&&validContext&&p&&member>=0);((Asset*)p)->member=member;}
void *NNS_G3dGetTex(const void *p){assert(p);return (void*)p;}
void sub_02026E18(const void *p,void *out){assert(p);memset(out,0,16);}
void *sub_02023F90(void *p){return p;}
void NNS_G3dMdlSetMdlFogEnableFlagAll(void *p,int value){assert(p&&!value);}
void sub_02023EA4(void *p,int value){assert(p&&!value);}
u32 sub_020209AC(const void *p,unsigned i){assert(p&&!i);return 512;}
void *sub_02020838(const void *p,unsigned i){assert(p&&!i);return ((Asset*)p)->tex;}
void *sub_02020888(const void *p,unsigned i){assert(p&&!i);return ((Asset*)p)->palette;}
static u32 TextureAllocate(u32 size,BOOL compressed,u32 opt){assert(size==512&&!compressed&&!opt);if(failTex)return 0;u32 k=0x00400000|(++nextKey*128);textureKeys[texCount++]=k;return k;}
static u32 PaletteAllocate(u32 size,BOOL four,u32 opt){assert(size==32&&!four&&!opt);if(failPal)return 0;u32 k=0x00040000|(++nextKey*4);paletteKeys[palCount++]=k;return k;}
static int TextureFree(u32 key){unsigned found=0;for(unsigned i=0;i<texCount;i++)if(textureKeys[i]==key){textureKeys[i]=0;found++;}assert(found==1);for(unsigned i=0;i<pending;i++)assert(transfers[i].type!=0||transfers[i].destination!=((key&65535)<<3));texFrees++;return 0;}
static int PaletteFree(u32 key){unsigned found=0;for(unsigned i=0;i<palCount;i++)if(paletteKeys[i]==key){paletteKeys[i]=0;found++;}assert(found==1);for(unsigned i=0;i<pending;i++)assert(transfers[i].type!=1||transfers[i].destination!=((key&65535)<<3));palFrees++;return 0;}
u32 (*NNS_GfdDefaultFuncAllocTexVram)(u32,BOOL,u32)=TextureAllocate;
int (*NNS_GfdDefaultFuncFreeTexVram)(u32)=TextureFree;
u32 (*NNS_GfdDefaultFuncAllocPlttVram)(u32,BOOL,u32)=PaletteAllocate;
int (*NNS_GfdDefaultFuncFreePlttVram)(u32)=PaletteFree;
SysTask *SysTask_CreateOnVWaitQueue(void(*callback)(SysTask*,void*),void*data,int priority){assert(!priority&&!task.active);if(failTask)return NULL;task=(SysTask){callback,data,1};taskCreations++;return &task;}
void SysTask_Destroy(SysTask*t){assert(t==&task&&t->active);t->active=0;taskDestructions++;}
u32 GF_GetNumPendingVramTransferTasks(void){return pending;}
BOOL GF_CreateNewVramTransferTask(int type,u32 dst,const void*src,u32 size){assert(src&&(type==0?size==512:size==32));if(failTransfer&&pending+1==failTransfer)return FALSE;assert(pending<64);transfers[pending++]=(Transfer){type,dst,src,size};return TRUE;}
void MapObject_CopyPositionVector(LocalMapObject*o,VecFx32*p){assert(o);*p=(VecFx32){10,20,30};}
void MapObject_CopyFacingVector(LocalMapObject*o,VecFx32*p){assert(o);*p=(VecFx32){1,1000,2};}
u32 MapObject_GetID(LocalMapObject*o){return o->id;}
u32 MapObject_GetMapID(LocalMapObject*o){return o->map;}
int MapObject_GetPriority(LocalMapObject*o){assert(o);return 5;}
void PlaySE(u32 se){assert(se==1501);plays++;}
static void StopSE(u32 se){assert(se==1501);stops++;}
const OverworldEmoteInit *sub_02068D98(void*e){return &((Effect*)e)->init;}
void sub_02068DB8(void*e,VecFx32*p){*p=((Effect*)e)->pos;}
void *ov01_021F16EC(void*c,const OverworldEmoteNativeModelTemplate*t,const VecFx32*p){assert(c==context&&validContext&&t->modelFile==owner->modelFile&&t->texture==owner->texture&&t->animation==ov01_0220952C&&t->textureKey&&t->paletteKey&&!t->texture4x4Key);assert(p->x==11&&p->y==20&&p->z==32);if(failModel)return NULL;Model*m=&models[modelCount++];assert(!m->active);*m=(Model){1,t->textureKey,t->paletteKey,t->modelFile};return m;}
void sub_02023DA4(void*p){Model*m=p;assert(m->active);m->active=0;modelFrees++;}
void *sub_02068B0C(void*manager,const OverworldEmoteNativeDescriptor*d,const VecFx32*p,int icon,const void*init,int priority){assert(manager==context[7]&&d->size==0x68&&d->draw==ov01_02203DC0&&icon>=0&&icon<14&&priority==6);if(failFactory)return NULL;unsigned next=0;while(next<16&&effects[next].active)next++;assert(next<16);Effect*e=&effects[next];*e=(Effect){.descriptor=d,.init=*(OverworldEmoteInit*)init,.pos=*p};if(!d->initialize(e,&e->data))return NULL;e->active=1;return e;}
void ov01_021F1640(void*p){Effect*e=p;assert(e->active);e->descriptor->destroy(e,&e->data);e->active=0;}
void ov01_02203CB8(void*e,OverworldEmoteNativeData*d){assert(e&&d->phase<3);nativeUpdates++;}
void ov01_02203DC0(void*e,OverworldEmoteNativeData*d){assert(e&&d->model);}
#include "overworld_emote_slots.c"
static void Reset(void){assert(!allocations&&!task.active);memset(models,0,sizeof(models));memset(effects,0,sizeof(effects));memset(textureKeys,0,sizeof(textureKeys));memset(paletteKeys,0,sizeof(paletteKeys));pending=allocationAttempts=freeCount=modelCount=modelFrees=texCount=palCount=nextKey=texFrees=palFrees=plays=stops=nativeUpdates=taskCreations=taskDestructions=0;failAllocation=failTask=failTex=failPal=failFactory=failModel=failTransfer=0;validContext=1;context[7]=context;owner=OverworldEmoteSlots_CreateOwner(context);assert(owner&&!task.active&&!owner->count&&allocations==3);}
static void Collect(unsigned drain){if(drain)pending=0;if(task.active)task.callback(&task,task.data);}
static void Close(void){for(unsigned i=0;i<16;i++)if(effects[i].active)ov01_021F1640(&effects[i]);OverworldEmoteSlots_DestroyOwner(owner);validContext=0;Collect(1);assert(!allocations&&!task.active&&modelFrees==modelCount&&taskCreations==taskDestructions);}
static void *ov01_02203A48(LocalMapObject *o,int i){return OverworldEmoteSlots_Admit(context,o,i);}
#define SEQ_SE_DP_DECIDE 1501
/* ACTUAL_QUIET_LEAF */
static struct LocalMapObject objects[4]={{1,33},{2,33},{3,33},{4,33}};
static void ThreeSlots(void){Reset();Effect*a=OverworldEmoteSlots_Admit(context,&objects[0],0);Effect*b=OverworldEmoteSlots_Admit(context,&objects[1],1);Effect*c=OverworldEmoteSlots_Admit(context,&objects[2],2);assert(a&&b&&c&&owner->count==3&&pending==6&&plays==3&&taskCreations==1);assert(a->data.frames.destination!=b->data.frames.destination&&b->data.frames.destination!=c->data.frames.destination);assert(paletteKeys[0]!=paletteKeys[1]&&paletteKeys[1]!=paletteKeys[2]);unsigned heap=allocations,attempts=allocationAttempts;assert(!OverworldEmoteSlots_Admit(context,&objects[3],3)&&!OverworldEmoteSlots_Admit(context,&objects[0],3));assert(heap==allocations&&attempts==allocationAttempts&&plays==3);for(unsigned phase=0;phase<3;phase++){a->data.phase=phase;a->descriptor->update(a,&a->data);}assert(nativeUpdates==3);a->data.phase=3;a->descriptor->update(a,&a->data);assert(modelFrees==1&&owner->count==3);a->descriptor->destroy(a,&a->data);assert(modelFrees==1);Collect(0);assert(owner->count==3&&texFrees==0&&palFrees==0&&allocations==heap);Collect(1);assert(owner->count==2&&texFrees==1&&palFrees==1&&allocations==heap-2&&task.active);assert(b->active&&c->active&&((Model*)b->data.model)->active);Close();}
static void SameIcons(void){Reset();Effect*a=OverworldEmoteSlots_Admit(context,&objects[0],0);Effect*b=OverworldEmoteSlots_Admit(context,&objects[1],0);Effect*c=OverworldEmoteSlots_Admit(context,&objects[2],0);assert(a&&b&&c&&a!=b&&b!=c&&a!=c&&owner->count==3);assert(a->data.frames.destination!=b->data.frames.destination&&b->data.frames.destination!=c->data.frames.destination);a->data.frames.elapsed=7;assert(!b->data.frames.elapsed&&!c->data.frames.elapsed);Close();}
static void QuietAndIdle(void){Reset();OverworldWildBubble_ShowQuiet(&objects[0],0);assert(plays==1&&stops==1);OverworldWildBubble_ShowQuiet(&objects[0],1);assert(plays==1&&stops==2&&owner->count==1);ov01_021F1640(&effects[0]);Collect(1);assert(!task.active&&!owner->count&&allocations==3);OverworldWildBubble_ShowQuiet(&objects[1],1);assert(plays==2&&stops==3&&taskCreations==2);Close();}
static void FailureControls(void){for(unsigned fault=0;fault<8;fault++){Reset();if(fault==0)failTask=1;else if(fault<3)failAllocation=allocationAttempts+fault;else if(fault==3)failTex=1;else if(fault==4)failPal=1;else if(fault==5)failFactory=1;else if(fault==6)failModel=1;else failTransfer=2;assert(!OverworldEmoteSlots_Admit(context,&objects[0],0)&&!plays);if(fault==7){assert(pending==1&&owner->count==1&&task.active);Collect(0);assert(owner->count==1&&allocations==5);Collect(1);}assert(!owner->count&&!task.active&&allocations==3&&modelFrees==modelCount);Close();}for(unsigned fault=1;fault<=3;fault++){assert(!allocations&&!task.active);validContext=1;failAllocation=allocationAttempts+fault;owner=OverworldEmoteSlots_CreateOwner(context);assert(!owner&&!allocations);OverworldEmoteSlots_DestroyOwner(owner);failAllocation=0;}}
static void ClosingControls(void){Reset();assert(OverworldEmoteSlots_Admit(context,&objects[0],0));ov01_021F1640(&effects[0]);OverworldEmoteSlots_DestroyOwner(owner);validContext=0;assert(task.active&&allocations==5);Collect(0);assert(allocations==5);Collect(1);assert(!allocations&&!task.active&&texFrees==1&&palFrees==1&&modelFrees==1);Reset();OverworldEmoteSlots_DestroyOwner(owner);assert(!allocations&&!task.active);}
int main(void){ThreeSlots();SameIcons();QuietAndIdle();FailureControls();ClosingControls();puts("three distinct keys/destinations; fourth and same-actor silent; native update/draw; finite VWait lifetime; cancellation/factory/partial-transfer rollback once; unchanged quiet leaf pair GREEN");return 0;}

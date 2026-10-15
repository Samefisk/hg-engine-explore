#ifndef OVERWORLD_EMOTE_SLOTS_INTERNAL_H
#define OVERWORLD_EMOTE_SLOTS_INTERNAL_H
#include "types.h"
#ifdef OVERWORLD_EMOTE_HOST
#define EMOTE_NATIVE
#else
#define EMOTE_NATIVE LONG_CALL
#endif

typedef struct LocalMapObject LocalMapObject;
typedef struct SysTask SysTask;
typedef struct OverworldEmoteOwner OverworldEmoteOwner;

typedef struct {
    void *modelFile;
    void *texture;
    const void *animation;
    u32 animationState[4];
    u32 textureKey, texture4x4Key, paletteKey;
} OverworldEmoteNativeModelTemplate;

typedef struct {
    const u16 *durations;
    const u8 *frames;
    u32 reserved, count;
    void *texture, *animationFile, *iconFile;
    u32 destination, frameBytes;
    u16 elapsed, frame;
} OverworldEmoteNativeFrames;

typedef struct {
    OverworldEmoteOwner *owner;
    LocalMapObject *object;
    void *effect, *model, *iconFile, *animationFile, *texture;
    u32 textureKey, paletteKey, state;
} OverworldEmoteSlot;

/* Context+0 and nonzero busy/count+4 keep the native script waiter contract. */
struct OverworldEmoteOwner {
    void *context;
    u32 count;
    void *modelFile, *animationFile, *texture;
    SysTask *retirementTask;
    u32 closing;
    OverworldEmoteSlot slots[3];
};

typedef struct {
    u32 phase, timer, objectId, mapId, hidden, finished;
    VecFx32 offset;
    u32 unused24;
    s32 riseVelocity;
    OverworldEmoteSlot *slot; /* Previously unused native word+0x2C. */
    void *context;
    OverworldEmoteOwner *owner;
    LocalMapObject *object;
    void *model;
    OverworldEmoteNativeFrames frames;
} OverworldEmoteNativeData;

typedef struct {
    u32 size;
    BOOL (*initialize)(void *, OverworldEmoteNativeData *);
    void (*destroy)(void *, OverworldEmoteNativeData *);
    void (*update)(void *, OverworldEmoteNativeData *);
    void (*draw)(void *, OverworldEmoteNativeData *);
} OverworldEmoteNativeDescriptor;

typedef struct {
    void *context;
    OverworldEmoteOwner *owner;
    LocalMapObject *object;
    OverworldEmoteSlot *slot;
} OverworldEmoteInit;

#ifndef OVERWORLD_EMOTE_HOST
typedef char EmotePrivateSlotSizeMustRemain28[sizeof(OverworldEmoteSlot) == 0x28 ? 1 : -1];
typedef char EmoteDataSizeMustRemain68[sizeof(OverworldEmoteNativeData) == 0x68 ? 1 : -1];
typedef char EmoteFramesSizeMustRemain28[sizeof(OverworldEmoteNativeFrames) == 0x28 ? 1 : -1];
typedef char EmoteTemplateSizeMustRemain28[sizeof(OverworldEmoteNativeModelTemplate) == 0x28 ? 1 : -1];
typedef char EmoteOwnerCountMustRemain4[__builtin_offsetof(OverworldEmoteOwner, count) == 4 ? 1 : -1];
typedef char EmotePrivateSlotWordMustBe2C[__builtin_offsetof(OverworldEmoteNativeData, slot) == 0x2C ? 1 : -1];
#endif

/* All SDK owners below are the named stock entry points; no new manager. */
void EMOTE_NATIVE MIi_CpuClear32(u32 value, void *destination, u32 bytes);
void *EMOTE_NATIVE ov01_021F141C(void *, int, int);
int EMOTE_NATIVE ov01_021F149C(void *, int);
void EMOTE_NATIVE ov01_021F14A8(void *, int, void *);
void EMOTE_NATIVE ov01_021F1448(void *);
void *EMOTE_NATIVE ov01_021F1450(void *, int);
void *EMOTE_NATIVE ov01_021F16EC(void *, const OverworldEmoteNativeModelTemplate *, const VecFx32 *);
void EMOTE_NATIVE ov01_021F1640(void *);
void EMOTE_NATIVE ov01_02203CB8(void *, OverworldEmoteNativeData *);
void EMOTE_NATIVE ov01_02203DC0(void *, OverworldEmoteNativeData *);
void *EMOTE_NATIVE sub_02068B0C(void *, const OverworldEmoteNativeDescriptor *, const VecFx32 *, int, const void *, int);
const OverworldEmoteInit *EMOTE_NATIVE sub_02068D98(void *);
void EMOTE_NATIVE sub_02068DB8(void *, VecFx32 *);
void EMOTE_NATIVE sub_02026E18(const void *, void *);
void EMOTE_NATIVE sub_02023DA4(void *);
void *EMOTE_NATIVE sub_02023F90(void *);
void EMOTE_NATIVE sub_02023EA4(void *, int);
void *EMOTE_NATIVE NNS_G3dGetTex(const void *);
void EMOTE_NATIVE NNS_G3dMdlSetMdlFogEnableFlagAll(void *, int);
u32 EMOTE_NATIVE sub_020209AC(const void *, unsigned);
void *EMOTE_NATIVE sub_02020838(const void *, unsigned);
void *EMOTE_NATIVE sub_02020888(const void *, unsigned);
BOOL EMOTE_NATIVE GF_CreateNewVramTransferTask(int, u32, const void *, u32);
u32 EMOTE_NATIVE GF_GetNumPendingVramTransferTasks(void);
SysTask *EMOTE_NATIVE SysTask_CreateOnVWaitQueue(void (*)(SysTask *, void *), void *, int);
void EMOTE_NATIVE SysTask_Destroy(SysTask *);
void EMOTE_NATIVE MapObject_CopyPositionVector(LocalMapObject *, VecFx32 *);
void EMOTE_NATIVE MapObject_CopyFacingVector(LocalMapObject *, VecFx32 *);
u32 EMOTE_NATIVE MapObject_GetID(LocalMapObject *);
u32 EMOTE_NATIVE MapObject_GetMapID(LocalMapObject *);
int EMOTE_NATIVE MapObject_GetPriority(LocalMapObject *);
void EMOTE_NATIVE PlaySE(u32);
extern u32 (*NNS_GfdDefaultFuncAllocTexVram)(u32, BOOL, u32);
extern int (*NNS_GfdDefaultFuncFreeTexVram)(u32);
extern u32 (*NNS_GfdDefaultFuncAllocPlttVram)(u32, BOOL, u32);
extern int (*NNS_GfdDefaultFuncFreePlttVram)(u32);
extern const u8 ov01_0220952C[];

OverworldEmoteOwner *OverworldEmoteSlots_CreateOwner(void *);
void OverworldEmoteSlots_DestroyOwner(OverworldEmoteOwner *);
void *OverworldEmoteSlots_Admit(void *context, LocalMapObject *, int);
#endif

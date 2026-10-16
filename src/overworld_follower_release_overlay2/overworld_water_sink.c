#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_water_sink.h"
#include "../../include/config.h"
#include "../../include/script.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_actor_system_internal.h"

/* Wild water sink presentation in the retired follower-interaction graph.
 * Field state stays in the Wild runtime; this leaf only crops a body. */
__asm__(".thumb_set OverworldWildSpawnGuard_IsSurfBehavior, 0x023C03D0\n"
    ".thumb_set WaterSink_CreateSplash, 0x021FF4FC\n");

/* ov01_021FF4FC: the stock shallow-water splash. Mode 1 keeps it on the
 * object's waterline until MAPOBJECTFLAG_UNK26 is cleared. */
void WaterSink_CreateSplash(LocalMapObject *object, int mode);

#define WATER_SINK_DRAW_USER_SBC 0x60   /* NNSG3dRenderObj.ptrUserSbc */
#define WATER_SINK_DRAW_MODEL 0x88
#define WATER_SINK_MODEL_OFS_SBC 0x04
#define WATER_SINK_MODEL_POS_SCALE 0x1C
#define WATER_SINK_SBC_BYTES 24
#define WATER_SINK_DL_BYTES 0x38
#define WATER_SINK_TILE_SHALLOW_WATER 0x17
#define WATER_SINK_ON_WATER 0x80
/* Lift above which a body counts as airborne. A ridden mount's gait bob
 * writes a fraction of a pixel; hops and fly-ins rise far past this. */
#define WATER_SINK_AIRBORNE_FX (3 << FX32_SHIFT)
/* Field-effect render pool: fieldSystem+0x44 -> +0x20 -> +0xC; capacity at
 * +0x8, records in use at +0xD4. Stock effects keep this many free. */
#define WATER_SINK_SPLASH_POOL_RESERVE 8
/* The Wild runtime remembers which body each slot's depth belongs to. It is
 * zeroed whenever it is (re)built, e.g. after a menu, so every body settles
 * again; a tag is never zero. */
#define WATER_SINK_TAG(generation) ((u8)((generation) | 0x80))

/* Both stock Pokemon billboards (mmodel 266 small, 269 large): NODEDESC,
 * NODE, BB, POSSCALE, MAT 0, SHP 0, inverse POSSCALE, RET. */
static const u8 sWaterSinkStockSbc[16] __attribute__((section(".overworld_water_sink_rodata"))) = {
    0x06, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0x07,
    0x00, 0x0B, 0x04, 0x00, 0x05, 0x00, 0x2B, 0x01,
};

static BOOL __attribute__((section(".overworld_water_sink")))
WaterSink_SplashFits(void)
{
    const u8 *field = (const u8 *)gFieldSysPtr;
    const u8 *effects;
    const u8 *models;
    const u8 *pool;

    if (((u32)field & 0xFFC00003) != 0x02000000) {
        return FALSE;
    }
    effects = *(const u8 * const *)(field + 0x44);
    if (((u32)effects & 0xFFC00003) != 0x02000000) {
        return FALSE;
    }
    models = *(const u8 * const *)(effects + 0x20);
    if (((u32)models & 0xFFC00003) != 0x02000000) {
        return FALSE;
    }
    pool = *(const u8 * const *)(models + 0xC);
    if (((u32)pool & 0xFFC00003) != 0x02000000) {
        return FALSE;
    }
    return *(const s32 *)(pool + 0xD4) + WATER_SINK_SPLASH_POOL_RESERVE
        < *(const s32 *)(pool + 0x8);
}

/* Each slot's private body and reflection quads. Draws keep pointing at them
 * while the Field renders, including while a menu has unloaded the Wild
 * overlay and freed its runtime, so they live on the Field heap (destroyed
 * with the Field at its exit, when overlay 2 also unloads). The pointer is
 * overlay data, so it starts NULL again with every Field. */
#define WATER_SINK_HEAP_FIELD 4   /* HEAP_ID_FIELD1 */
#define WATER_SINK_QUAD_BODY 0
#define WATER_SINK_QUAD_MIRROR 1
typedef u32 WaterSinkQuads[2][OW_WILD_MAX_SPAWNS][OVERWORLD_WATER_SINK_QUAD_WORDS];
static WaterSinkQuads *sWaterSinkQuads
    __attribute__((section(".overworld_water_sink_data")));
/* Keep the zero loop: memset is ARM code that would need an 8-byte stub. */
static u32 * __attribute__((section(".overworld_water_sink"),
    optimize("no-tree-loop-distribute-patterns")))
WaterSink_Quad(u32 kind, u32 slot)
{
    u32 *words;
    u32 i;

    if (sWaterSinkQuads == NULL) {
        words = sys_AllocMemory(WATER_SINK_HEAP_FIELD, sizeof(WaterSinkQuads));
        if (words == NULL) {
            return NULL;
        }
        for (i = 0; i < sizeof(WaterSinkQuads) / 4; i++) {
            words[i] = 0;
        }
        sWaterSinkQuads = (WaterSinkQuads *)words;
    }
    return (*sWaterSinkQuads)[kind][slot];
}

/* The model's SBC when it is the stock billboard program, else NULL. */
static inline const u8 * __attribute__((always_inline))
WaterSink_StockSbc(const u8 *model)
{
    const u8 *sbc;
    u32 i;

    if (((u32)model & 0xFFC00003) != 0x02000000) {
        return NULL;
    }
    sbc = model + *(const u32 *)(model + WATER_SINK_MODEL_OFS_SBC);
    for (i = 0; i < sizeof(sWaterSinkStockSbc); i++) {
        if (sbc[i] != sWaterSinkStockSbc[i]) {
            return NULL;
        }
    }
    return sbc;
}

static u8 * __attribute__((section(".overworld_water_sink")))
WaterSink_Draw(const LocalMapObject *object)
{
    const u32 *render = (const u32 *)object->unk108;
    u32 callback = (u32)object->unkC8;
    u32 draw;

    /* Same stock Pokemon draw callbacks and state layouts as the mount and
     * appearance owners. Other callbacks keep their stock drawing. */
    if (callback == 0x021F7895) {
        draw = render[0];
    } else if (callback == 0x021F88F1) {
        draw = render[1];
    } else {
        return NULL;
    }
    return (draw & 0xFFC00003) == 0x02000000 ? (u8 *)draw : NULL;
}

/* Hide the bottom rows of this object's sprite only. The model and texture
 * are shared, so the draw gets a private SBC whose SHP is replaced by a
 * CALLDL to a copy of the stock quad: the bottom edge stays on the anchor,
 * the top edge comes down, and the texture is cut by the same rows. */
static u32 __attribute__((section(".overworld_water_sink")))
WaterSink_Crop(u32 *quad, const LocalMapObject *object, u32 rows)
{
    u8 *draw = WaterSink_Draw(object);
    u8 *bytes = (u8 *)quad;
    u32 *userSbc;
    u32 *dl;
    const u8 *model;
    const u8 *sbc;
    u32 height;
    u32 shown;
    u32 top;
    u32 i;

    if (draw == NULL) {
        return 0;
    }
    userSbc = (u32 *)(draw + WATER_SINK_DRAW_USER_SBC);
    if (rows == 0) {
        if (*userSbc == (u32)quad) {
            *userSbc = 0;
        }
        return 0;
    }
    /* Another owner's user SBC keeps priority. */
    if (*userSbc != 0 && *userSbc != (u32)quad) {
        return 0;
    }
    model = *(const u8 **)(draw + WATER_SINK_DRAW_MODEL);
    sbc = WaterSink_StockSbc(model);
    if (sbc == NULL) {
        return 0;
    }
    /* posScale 8.0 or 16.0: the quad spans 32 or 64 texels and world units. */
    height = *(const u32 *)(model + WATER_SINK_MODEL_POS_SCALE) >> 10;
    if (height != 32 && height != 64) {
        return 0;
    }
    if (rows >= height) {
        rows = height - 1;
    }
    shown = height - rows;
    top = shown << (height == 32 ? 9 : 8); /* model y = 4.0 * shown / height */

    for (i = 0; i < 12; i++) {
        bytes[i] = sbc[i];
    }
    bytes[12] = 0x0A; /* CALLDL rel32 size32, relative to this opcode */
    bytes[13] = WATER_SINK_SBC_BYTES - 12;
    bytes[14] = 0;
    bytes[15] = 0;
    bytes[16] = 0;
    bytes[17] = WATER_SINK_DL_BYTES;
    bytes[18] = 0;
    bytes[19] = 0;
    bytes[20] = 0;
    bytes[21] = 0x2B;
    bytes[22] = 0x01;

    /* The stock quad DL with both bottom texcoords and both top vertices
     * patched. Small lists go through the CPU GE path; no cache flush. */
    dl = quad + WATER_SINK_SBC_BYTES / 4;
    dl[0] = 0x24212240;             /* BEGIN_VTXS, TEXCOORD, NORMAL, VTX_10 */
    dl[1] = 1;                      /* quads */
    dl[2] = (shown * 16) << 16;     /* (0, shown) */
    dl[3] = 0x1FF00000;
    dl[4] = 0x00000380;             /* (-2, 0, 0) */
    dl[5] = 0x25222522;             /* TEXCOORD, VTX_XY, TEXCOORD, VTX_XY */
    dl[6] = (height * 16) | ((shown * 16) << 16);
    dl[7] = 0x00002000;             /* (2, 0) */
    dl[8] = height * 16;            /* (height, 0) */
    dl[9] = 0x2000 | (top << 16);   /* (2, top) */
    dl[10] = 0x00412522;            /* TEXCOORD, VTX_XY, END_VTXS */
    dl[11] = 0;                     /* (0, 0) */
    dl[12] = 0xE000 | (top << 16);  /* (-2, top) */
    dl[13] = 0;
    *userSbc = (u32)quad;
    return height;
}

/* The body's stock reflection (field effect 1, "mirror" model) hangs from
 * its anchor: the near edge samples the sprite's bottom texel row, the far
 * edge its top row. Once the body is cropped the near edge would mirror the
 * hidden rows and leave a gap, then the whole body. Give this object's
 * reflection record a private copy of its quad whose near edge samples the
 * last visible row and whose far edge comes in by the same fraction, so the
 * reflection mirrors exactly the part above the waterline. The whole quad
 * is raised by OVERWORLD_WATER_SUBMERGE_REFLECTION_RAISE so it starts at the
 * cut line. */
#define WATER_SINK_TASK_LIVE 1
#define WATER_SINK_TASK_INIT 0xB0
#define WATER_SINK_TASK_WORK 0x30
#define WATER_SINK_TASK_STRIDE 0xC8
#define WATER_SINK_MIRROR_INIT 0x021FDAC1        /* ov01_021FDAC0 */
#define WATER_SINK_MIRROR_ALT_INIT 0x021FDFD5    /* ov01_021FDFD4 */

static u8 * __attribute__((noinline, section(".overworld_water_sink_tail")))
WaterSink_FindMirror(const LocalMapObject *object)
{
    const u8 *field = (const u8 *)gFieldSysPtr;
    const u8 *effects;
    const u8 *tasks;
    const u8 *entry;
    const u32 *work;
    u32 count;
    u32 i;

    if (((u32)field & 0xFFC00003) != 0x02000000) {
        return NULL;
    }
    effects = *(const u8 * const *)(field + 0x44);
    if (((u32)effects & 0xFFC00003) != 0x02000000) {
        return NULL;
    }
    tasks = *(const u8 * const *)(effects + 0x1C);
    if (((u32)tasks & 0xFFC00003) != 0x02000000) {
        return NULL;
    }
    count = *(const u32 *)tasks;
    entry = *(const u8 * const *)(tasks + 0xC);
    if (((u32)entry & 0xFFC00003) != 0x02000000 || count > 128) {
        return NULL;
    }
    for (i = 0; i < count; i++, entry += WATER_SINK_TASK_STRIDE) {
        if ((*(const u32 *)entry & WATER_SINK_TASK_LIVE) == 0
            || (*(const u32 *)(entry + WATER_SINK_TASK_INIT)
                    != WATER_SINK_MIRROR_INIT
                && *(const u32 *)(entry + WATER_SINK_TASK_INIT)
                    != WATER_SINK_MIRROR_ALT_INIT)) {
            continue;
        }
        /* work: +0xC model ready, +0x20 object, +0x24 render record */
        work = (const u32 *)(entry + WATER_SINK_TASK_WORK);
        if (work[8] == (u32)object && work[3] == 1
            && (work[9] & 0xFFC00003) == 0x02000000) {
            return (u8 *)work[9];
        }
    }
    return NULL;
}

static void __attribute__((noinline, section(".overworld_water_sink_tail")))
WaterSink_Mirror(u32 *quad, const LocalMapObject *object, u32 shown, u32 height)
{
    u8 *record = WaterSink_FindMirror(object);
    u8 *bytes = (u8 *)quad;
    const u8 *model;
    const u8 *sbc;
    const u8 *shapes;
    const u8 *shape;
    const u32 *stock;
    u32 *userSbc;
    u32 *dl;
    u32 shift;
    u32 near;
    s32 raise;
    s32 y;
    s32 z;
    u32 i;

    if (record == NULL) {
        return;
    }
    userSbc = (u32 *)(record + WATER_SINK_DRAW_USER_SBC);
    if (height == 0) {
        if (*userSbc == (u32)quad) {
            *userSbc = 0;
        }
        return;
    }
    if (*userSbc != 0 && *userSbc != (u32)quad) {
        return;
    }
    model = *(const u8 **)(record + WATER_SINK_DRAW_MODEL);
    sbc = WaterSink_StockSbc(model);
    if (sbc == NULL) {
        return;
    }
    /* One shape: dict entry block at +6, its first value is the offset. */
    shapes = model + *(const u32 *)(model + 0xC);
    if (shapes[1] != 1) {
        return;
    }
    shape = shapes + *(const u32 *)(shapes + *(const u16 *)(shapes + 6) + 4);
    stock = (const u32 *)(shape + *(const u32 *)(shape + 8));
    if (*(const u32 *)(shape + 12) != WATER_SINK_DL_BYTES
        || stock[0] != 0x24212240 || stock[5] != 0x27222522
        || stock[10] != 0x00412522
        || (stock[2] >> 16) == 0 || (stock[2] >> 16) != (stock[6] >> 16)
        || (stock[8] >> 16) != 0 || (stock[11] >> 16) != 0) {
        return;
    }
    /* Raise in world units -> model units: posScale 4.0 or 8.0. */
    if (*(const u32 *)(model + WATER_SINK_MODEL_POS_SCALE) == 0x4000) {
        raise = (OVERWORLD_WATER_SUBMERGE_REFLECTION_RAISE << FX32_SHIFT) >> 2;
    } else if (*(const u32 *)(model + WATER_SINK_MODEL_POS_SCALE) == 0x8000) {
        raise = (OVERWORLD_WATER_SUBMERGE_REFLECTION_RAISE << FX32_SHIFT) >> 3;
    } else {
        return;
    }
    shift = height == 32 ? 5 : 6;
    near = ((stock[2] >> 16) * shown) >> shift;

    for (i = 0; i < 12; i++) {
        bytes[i] = sbc[i];
    }
    bytes[12] = 0x0A;
    bytes[13] = WATER_SINK_SBC_BYTES - 12;
    bytes[14] = 0;
    bytes[15] = 0;
    bytes[16] = 0;
    bytes[17] = WATER_SINK_DL_BYTES;
    bytes[18] = 0;
    bytes[19] = 0;
    bytes[20] = 0;
    bytes[21] = 0x2B;
    bytes[22] = 0x01;
    bytes[23] = 0;

    dl = quad + WATER_SINK_SBC_BYTES / 4;
    for (i = 0; i < WATER_SINK_DL_BYTES / 4; i++) {
        dl[i] = stock[i];
    }
    /* Near edge: TEXCOORD t of both anchor vertices. */
    dl[2] = (stock[2] & 0xFFFF) | (near << 16);
    dl[6] = (stock[6] & 0xFFFF) | (near << 16);
    /* Near edge up by the raise: VTX_10 y (bits 10-19, 1/64 units) and
     * VTX_XY y. */
    dl[4] = (stock[4] & ~(0x3FFu << 10)) | (((u32)(raise >> 6) & 0x3FF) << 10);
    y = (s32)(s16)(stock[7] >> 16) + raise;
    dl[7] = (stock[7] & 0xFFFF) | ((u32)y << 16);
    /* Far edge: VTX_YZ (y, z) and VTX_XY (x, y) scaled by shown/height,
     * then raised by the same amount. */
    y = (((s32)(s16)(stock[9] & 0xFFFF) * (s32)shown) >> shift) + raise;
    z = ((s32)(s16)(stock[9] >> 16) * (s32)shown) >> shift;
    dl[9] = ((u32)y & 0xFFFF) | ((u32)z << 16);
    y = (((s32)(s16)(stock[12] >> 16) * (s32)shown) >> shift) + raise;
    dl[12] = (stock[12] & 0xFFFF) | ((u32)y << 16);
    *userSbc = (u32)quad;
}

/* A terrain reconcile passes the tile behavior and retargets: deep water
 * sinks the body by depth pixels unless the slot's resolved owner lane has
 * Water surface. A new body, a hop and an idle reconcile settle at once, so a
 * spawn appears already submerged; a walk across the bank passes EASE and
 * moves one pixel per frame. The hop arc in unk88 lifts the body
 * back out: the anchor drops by the lifted part so the cut stays on the
 * waterline, and an airborne body is drawn whole. A submerged body also
 * keeps the stock shallow-water splash on its waterline. */
BOOL __attribute__((noinline, used, section(".overworld_water_sink_entry")))
OverworldWaterSink_Update(LocalMapObject *object, u32 behavior, u32 depth)
{
    OverworldWildOverlayRuntimeState *runtime =
        sOverworldWildSpawnState.movementRuntimeState;
    const OverworldWildBehaviorSlotCache *caches;
    u32 slot = (u32)(object->id - OW_WILD_OBJECT_ID_START);
    BOOL water = FALSE;
    BOOL settle;
    BOOL onWater;
    BOOL reconcile = behavior != OVERWORLD_WATER_SINK_EASE;
    u32 *body;
    u32 *mirror;
    u8 *tag;
    u32 current;
    u32 target;
    s32 sink;
    s32 lift;
    u32 rows;
    u32 height;

    if (slot >= OW_WILD_MAX_SPAWNS || runtime == NULL) {
        return FALSE;
    }
    current = runtime->waterSinkPx[slot];
    /* Bit 7 records "on deep water" for every body, including a Water
     * Runner whose depth stays zero; the low bits are the target depth. */
    onWater = (runtime->waterSinkTargetPx[slot] & WATER_SINK_ON_WATER) != 0;
    target = runtime->waterSinkTargetPx[slot] & ~WATER_SINK_ON_WATER;
    settle = !runtime->movementCustomJumpActive[slot]
        || runtime->movementCustomJumpArcHeightsQ4[slot] != 0;
    /* A spawn reuses the slot's last depth; read its own tile at once. */
    body = WaterSink_Quad(WATER_SINK_QUAD_BODY, slot);
    mirror = WaterSink_Quad(WATER_SINK_QUAD_MIRROR, slot);
    if (body == NULL || mirror == NULL) {
        return FALSE;
    }
    tag = &runtime->waterSinkBodyTag[slot];
    if (*tag != WATER_SINK_TAG(sOverworldWildSpawnState.spawns[slot].encounterGeneration)) {
        *tag = WATER_SINK_TAG(sOverworldWildSpawnState.spawns[slot].encounterGeneration);
        settle = TRUE;
        if (behavior == OVERWORLD_WATER_SINK_EASE) {
            behavior = GetMetatileBehaviorAt(
                gFieldSysPtr, object->xCurr, object->yCurr);
        }
    }
    if (behavior != OVERWORLD_WATER_SINK_EASE) {
        water = OverworldWildSpawnGuard_IsSurfBehavior((u8)behavior);
        caches = runtime->movementBehaviorSlotCaches;
        target = water
            && (caches == NULL
                || (caches[slot].profile.owner.chillAllowedTerrainMask
                    & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER_SURFACE) == 0)
            ? depth : 0;
        onWater = water;
        runtime->waterSinkTargetPx[slot] =
            (u8)(target | (water ? WATER_SINK_ON_WATER : 0));
        if (settle) {
            current = target;
        }
        /* The stock terrain update keeps a Wild splash flag; shallow water
         * still raises its own splash there. */
        if (!water && (u8)behavior != WATER_SINK_TILE_SHALLOW_WATER) {
            object->flags &= ~MAPOBJECTFLAG_UNK26;
        }
    }
    if (current < target) {
        current++;
    } else if (current > target) {
        current--;
    }
    runtime->waterSinkPx[slot] = (u8)current;
    /* A terrain reconcile inside custom motion runs before that frame's
     * height is written (a fly-in reads as sitting on the water). Only
     * retarget here: the motion writer's EASE call later in the same frame
     * crops and splashes against the real arc, and a landing is applied by
     * the per-frame pass once the motion ends. */
    if (reconcile && runtime->movementCustomJumpActive[slot]) {
        return water;
    }
    sink = (s32)current << FX32_SHIFT;
    lift = (s32)object->unk88[1];
    if (lift < 0) {
        lift = 0;
    } else if (lift > sink) {
        lift = sink;
    }
    object->unk94[1] = (u32)-lift;
    rows = (u32)(sink - lift) >> FX32_SHIFT;
    height = WaterSink_Crop(body, object, rows);
    WaterSink_Mirror(mirror, object,
        height - (rows < height ? rows : height - 1), height);
    /* A body touching deep water splashes: a submerged one while its cut
     * rows are under water, a Water Runner (no depth) while it is not
     * airborne. A hop or fly-in over deep water drops it. One splash per
     * body: the flag is its lifetime, and stock effects keep a free part of
     * the shared pool. */
    if (!onWater) {
        /* Land and shallow water are cleared by the retarget above. */
    } else if (rows == 0
        && (target != 0 || (s32)object->unk88[1] > WATER_SINK_AIRBORNE_FX)) {
        object->flags &= ~MAPOBJECTFLAG_UNK26;
    } else if ((object->flags & MAPOBJECTFLAG_UNK26) == 0
        && WaterSink_SplashFits()) {
        WaterSink_CreateSplash(object, 1);
        object->flags |= MAPOBJECTFLAG_UNK26;
    }
    return water;
}

/* The appearance capsule's per-frame refresh is chained through here (its
 * entry table points at this fixed slot). A body that has not moved since
 * it spawned gets no terrain reconcile or motion frame, so it would stand on
 * the water whole until its first step. Give every new body its depth on the
 * first frame, and keep idle submerged bodies settled and cropped. Motion
 * frames stay with the frame writer so a walk eases once per frame. */
__asm__(".thumb_set OverworldActorAppearance_RefreshAllNative, 0x02208739\n");
void OverworldActorAppearance_RefreshAllNative(
    const OverworldWildSpawnState *spawns, const void *behavior);

/* A ridden Follower gets no Wild terrain reconcile or motion frame: its
 * object copies the player's tiles. Feed it its current tile every frame so
 * a Water Runner mount splashes on deep water (and is never cropped). */
static void __attribute__((noinline, section(".overworld_water_sink")))
WaterSink_MountFrame(const OverworldWildSpawnState *spawns)
{
    const OverworldMountRuntimeState *mount =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    LocalMapObject *object = spawns->spawns[OW_WILD_FOLLOWER_SLOT].object;

    if (mount->fieldSystem != gFieldSysPtr
        || mount->snapshot.phase != OVERWORLD_MOUNT_PHASE_RIDING
        || !spawns->spawns[OW_WILD_FOLLOWER_SLOT].active
        || ((u32)object & 0xFFC00003) != 0x02000000
        || object->id != (int)(OW_WILD_OBJECT_ID_START + OW_WILD_FOLLOWER_SLOT)) {
        return;
    }
    (void)OverworldWaterSink_Update(object,
        GetMetatileBehaviorAt(gFieldSysPtr, object->xCurr, object->yCurr),
        OVERWORLD_WATER_SINK_DEPTH);
    /* The retarget stops early while the mount's motion counts as custom
     * motion; the frame pass then applies crop and splash. */
    (void)OverworldWaterSink_Update(object, OVERWORLD_WATER_SINK_EASE,
        OVERWORLD_WATER_SINK_DEPTH);
}

void __attribute__((noinline, used, section(".overworld_water_sink_frame")))
OverworldWaterSink_RefreshAll(
    const OverworldWildSpawnState *spawns, const void *behavior)
{
    OverworldWildOverlayRuntimeState *runtime;
    LocalMapObject *object;
    u32 slot;

    OverworldActorAppearance_RefreshAllNative(spawns, behavior);
    if (spawns != &sOverworldWildSpawnState
        || spawns->movementFieldSystem != gFieldSysPtr
        || gFieldSysPtr == NULL
        || (runtime = spawns->movementRuntimeState) == NULL) {
        return;
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        object = spawns->spawns[slot].object;
        if (!spawns->spawns[slot].active || object == NULL
            || ((u32)object & 0xFFC00003) != 0x02000000
            || object->id != (int)(OW_WILD_OBJECT_ID_START + slot)
            || (object->flags & MAPOBJECTFLAG_ACTIVE) == 0) {
            continue;
        }
        if (runtime->waterSinkBodyTag[slot]
                == WATER_SINK_TAG(spawns->spawns[slot].encounterGeneration)
            && (runtime->movementCustomJumpActive[slot]
                || (runtime->waterSinkPx[slot] == 0
                    && runtime->waterSinkTargetPx[slot] == 0))) {
            continue;
        }
        (void)OverworldWaterSink_Update(
            object, OVERWORLD_WATER_SINK_EASE, OVERWORLD_WATER_SINK_DEPTH);
    }
    WaterSink_MountFrame(spawns);
}

/* The stock move-start terrain update (sub_02060274) raises a tall-grass
 * rustle that stays until the object leaves its tile. Wild motion starts a
 * move every frame, and a fly-in keeps its logical tile on the take-off
 * grass while it flies, so the stock call stacked one rustle per frame until
 * the field-effect pool ran out. A Wild body now rustles once per tile it
 * enters and never while airborne; other objects keep the stock call. */
__asm__(".thumb_set WaterSink_StockGrassRustle, 0x021FF071\n");
void WaterSink_StockGrassRustle(LocalMapObject *object, int mode);

static u32 sWaterSinkRustleTile[OW_WILD_MAX_SPAWNS]
    __attribute__((section(".overworld_water_sink_grass_data")));

void __attribute__((noinline, used, section(".overworld_water_sink_grass")))
OverworldWaterSink_GrassRustle(LocalMapObject *object, int mode)
{
    u32 slot = (u32)(object->id - OW_WILD_OBJECT_ID_START);
    u32 tile;

    if (slot < OW_WILD_MAX_SPAWNS) {
        tile = (u16)object->xCurr | ((u32)(u16)object->yCurr << 16);
        if ((s32)object->unk88[1] > 0 || sWaterSinkRustleTile[slot] == tile) {
            return;
        }
        sWaterSinkRustleTile[slot] = tile;
    }
    WaterSink_StockGrassRustle(object, mode);
}

/* The stock splash draw (ov01_021FF658) places its record at the object's
 * waterline, 8 units toward the camera, then calls sub_02023E50. That call is
 * routed here with the task work still in r5. A submerged Wild body's splash
 * is moved down on screen by about OVERWORLD_WATER_SUBMERGE_SPLASH_DROP
 * pixels so its ring sits on the cut line in front of the body. Other
 * splashes stay stock. */
__asm__(".thumb_set WaterSink_SetRecordPosition, 0x02023E51\n");
void WaterSink_SetRecordPosition(void *record, s32 *position);

static void __attribute__((noinline, used, section(".overworld_water_sink")))
WaterSink_PlaceSplash(void *record, s32 *position, const u8 *work)
{
    const LocalMapObject *object = *(LocalMapObject * const *)(work + 0x20);
    OverworldWildOverlayRuntimeState *runtime =
        sOverworldWildSpawnState.movementRuntimeState;
    u32 slot;

    if (((u32)object & 0xFFC00003) == 0x02000000 && runtime != NULL) {
        slot = (u32)(object->id - OW_WILD_OBJECT_ID_START);
        if (slot < OW_WILD_MAX_SPAWNS && runtime->waterSinkPx[slot] != 0) {
            /* Toward the camera, not down: the tilted camera shows it
             * lower while it stays in front of the body's billboard. A
             * lower y sinks the ring behind the body (worst facing north).
             * 5/4 keeps the on-screen drop about one unit per pixel. */
            position[2] += (OVERWORLD_WATER_SUBMERGE_SPLASH_DROP * 5)
                << (FX32_SHIFT - 2);
        }
    }
    WaterSink_SetRecordPosition(record, position);
}

void __attribute__((naked, used, section(".overworld_water_sink_splash")))
OverworldWaterSink_PlaceSplash(void)
{
    __asm__ volatile(
        "mov r2, r5\n"
        "b WaterSink_PlaceSplash\n");
}

/* The stock reflection draw (ov01_021FDBCC) places its record 20 units below
 * and 14 behind the body's anchor, under the translucent water that tints it.
 * That offset only roughly follows the view direction, so under the
 * perspective camera the short cropped reflection slid sideways off its body
 * away from the screen centre. While this body's mirror quad is installed,
 * keep the stock depth (and the tint) but move the record onto the camera ray
 * through the body's waterline point: R' = C + (B - C) * depth(R) / depth(B).
 * Its near edge then projects onto the cut line anywhere on screen. */
#define WATER_SINK_CAMERA_PTR 0x021D2204   /* sCameraPtr */
#define WATER_SINK_CAMERA_POS 0x14         /* lookAt.camPos */
#define WATER_SINK_CAMERA_TARGET 0x20      /* lookAt.camTarget */

static void __attribute__((noinline, used, section(".overworld_water_sink")))
WaterSink_PlaceMirror(u8 *record, s32 *position, const u8 *work)
{
    const LocalMapObject *object = *(LocalMapObject * const *)(work + 0x20);
    OverworldWildOverlayRuntimeState *runtime =
        sOverworldWildSpawnState.movementRuntimeState;
    const u8 *camera = *(const u8 * const *)WATER_SINK_CAMERA_PTR;
    const s32 *eye;
    const s32 *target;
    const u8 *draw;
    s32 body[3];
    s32 forward[3];
    s32 depthBody;
    s32 depthMirror;
    s32 ratio;
    u32 slot;
    u32 i;

    if (((u32)object & 0xFFC00003) == 0x02000000 && runtime != NULL
        && ((u32)camera & 0xFFC00003) == 0x02000000) {
        slot = (u32)(object->id - OW_WILD_OBJECT_ID_START);
        if (slot < OW_WILD_MAX_SPAWNS
            && *(const u32 *)(record + WATER_SINK_DRAW_USER_SBC)
                == (u32)WaterSink_Quad(WATER_SINK_QUAD_MIRROR, slot)
            && (draw = WaterSink_Draw(object)) != NULL) {
            eye = (const s32 *)(camera + WATER_SINK_CAMERA_POS);
            target = (const s32 *)(camera + WATER_SINK_CAMERA_TARGET);
            body[0] = *(const s32 *)(draw + 0);
            body[1] = (s32)object->posVec[1] + (s32)object->faceVec[1];
            body[2] = *(const s32 *)(draw + 8);
            /* Depths along the view direction, in 1/16 units. */
            depthBody = 0;
            depthMirror = 0;
            for (i = 0; i < 3; i++) {
                forward[i] = (target[i] - eye[i]) >> 8;
                depthBody += ((body[i] - eye[i]) >> 8) * forward[i];
                depthMirror += ((position[i] - eye[i]) >> 8) * forward[i];
            }
            if ((depthBody >> 12) > 0 && depthMirror > depthBody) {
                ratio = depthMirror / (depthBody >> 12);   /* x4096 */
                for (i = 0; i < 3; i++) {
                    position[i] = eye[i]
                        + ((((body[i] - eye[i]) >> 4) * ratio) >> 8);
                }
            }
        }
    }
    WaterSink_SetRecordPosition(record, position);
}

void __attribute__((naked, used, section(".overworld_water_sink_mirror")))
OverworldWaterSink_PlaceMirror(void)
{
    __asm__ volatile(
        "mov r2, r5\n"
        "b WaterSink_PlaceMirror\n");
}

/* Mounted water running. Riding uses the stock player step, whose collision
 * (sub_0205DA34) reports deep water as a plain block for anyone not
 * surfing. Its final "return flags" is routed here (0x0205DAA2) with the
 * player object in r6 and the facing in r7. A deep-water step is open while
 * riding a mount whose resolved terrain includes Water (Water Runner), and
 * also while the player already stands on deep water without surfing, so a
 * dismount on water (explicit or forced) can never strand the player. */

static u32 __attribute__((noinline, used, section(".overworld_water_sink_tail")))
WaterSink_PlayerCollision(u32 flags, const LocalMapObject *player, u32 direction)
{
    const OverworldMountRuntimeState *mount =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    int x;
    int y;

    /* Deep water reports 0x21: blocked (1) plus surfable water (0x20,
     * sub_0205DCA0). Any other reason, e.g. an object, keeps the block. */
    if (flags == 0 || (flags & ~0x21u) != 0 || gFieldSysPtr == NULL || direction > 3
        || ((u32)player & 0xFFC00003) != 0x02000000) {
        return flags;
    }
    x = player->xCurr + (direction == 2 ? -1 : direction == 3 ? 1 : 0);
    y = player->yCurr + (direction == 0 ? -1 : direction == 1 ? 1 : 0);
    if (!OverworldWildSpawnGuard_IsSurfBehavior(
            GetMetatileBehaviorAt(gFieldSysPtr, x, y))) {
        return flags;
    }
    if ((mount->fieldSystem == gFieldSysPtr
            && mount->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
            && (mount->snapshot.profile.chillAllowedTerrainMask
                & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER) != 0)
        || OverworldWildSpawnGuard_IsSurfBehavior(GetMetatileBehaviorAt(
            gFieldSysPtr, player->xCurr, player->yCurr))) {
        return 0;
    }
    return flags;
}

void __attribute__((naked, used, section(".overworld_water_sink_mount")))
OverworldWaterSink_PlayerCollision(void)
{
    /* Replaces "add r0, r4, #0; pop {r3-r7, pc}" of sub_0205DA34. */
    __asm__ volatile(
        "mov r0, r4\n"
        "mov r1, r6\n"
        "mov r2, r7\n"
        "bl WaterSink_PlayerCollision\n"
        "pop {r3, r4, r5, r6, r7, pc}\n");
}

/* Skid aim. A Sprint Chase toward the player (Follower, or a wild Pokemon
 * chasing the player) used to run at full speed until it was aligned, then
 * skid past the goal and walk back. Every Walk INPUT for an actor is routed
 * here (runtime overlay, 0x0224FFF4) before the normal reducer. While it is
 * still continuing in its committed direction:
 *  - player within one row/column of the line: once the stop skid at the
 *    current speed would end exactly on the first tile next to the player,
 *    request the stop now;
 *  - player two or more tiles off the line: once the turn skid would end
 *    exactly level with the player, request the turn now.
 * Only exact landings are taken, so a skid never runs into the player. */
#define SKID_AIM_KIND_CHASE 3
#define SKID_AIM_TARGET_TOWARD_PLAYER 2
#define SKID_AIM_TARGET_NEXT_TO_PLAYER 6
__asm__(".thumb_set SkidAim_ProfileSkidTiles, 0x01FFD337\n"
    ".thumb_set SkidAim_ReduceInput, 0x01FFF041\n");
u8 SkidAim_ProfileSkidTiles(u8 time, const OverworldWildBehaviorProfileData *lane,
    BOOL stop);
void SkidAim_ReduceInput(OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call);

static void __attribute__((noinline, used, section(".overworld_water_sink")))
SkidAim_Input(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call,
    const OverworldActorStateSnapshot *actor)
{
    const OverworldWildBehaviorProfileData *lane = call->lane;
    const OverworldWildWalkMomentumState *momentum = &policy->walkMomentum;
    const u8 *avatar;
    const LocalMapObject *player;
    s32 along;
    s32 side;
    u8 time;
    u8 tiles;
    u8 dir = momentum->direction;

    if (actor == NULL || lane == NULL
        || (actor->role != OVERWORLD_ACTOR_ROLE_WILD
            && actor->role != OVERWORLD_ACTOR_ROLE_FOLLOWER)
        || lane->chillState != SKID_AIM_KIND_CHASE
        || (lane->chillTarget != SKID_AIM_TARGET_TOWARD_PLAYER
            && lane->chillTarget != SKID_AIM_TARGET_NEXT_TO_PLAYER)
        || dir > 3 || momentum->speed == 0 || momentum->skidRemaining != 0
        || call->direction != dir
        || ((u32)gFieldSysPtr & 0xFFC00003) != 0x02000000) {
        goto reduce;
    }
    avatar = *(const u8 * const *)((const u8 *)gFieldSysPtr + 0x40);
    if (((u32)avatar & 0xFFC00003) != 0x02000000) {
        goto reduce;
    }
    player = *(const LocalMapObject * const *)(avatar + 0x30);
    if (((u32)player & 0xFFC00003) != 0x02000000) {
        goto reduce;
    }
    /* Distance to the player along the heading, and the side offset. */
    along = player->xCurr - actor->logicalX;
    side = player->yCurr - actor->logicalY;
    if (dir < 2) {
        s32 t = along;
        along = side;
        side = t;
    }
    if (dir == 0 || dir == 2) {
        along = -along;
    }
    time = policy->lastWalkTime != 0 ? policy->lastWalkTime : momentum->speed;
    if (side >= -1 && side <= 1) {
        /* The goal is the first tile next to the player on this line. */
        s32 remaining = along - (side == 0 ? 1 : 0);

        if (remaining <= 0
            || !OW_WILD_BEHAVIOR_STOPS_WITH_SKID(lane->tilesBeforeTurnSkid)) {
            goto reduce;
        }
        tiles = SkidAim_ProfileSkidTiles(time, lane, TRUE);
        if (tiles != 0 && remaining == (s32)tiles) {
            call->direction = OW_WILD_WALK_DIRECTION_NONE;
        }
        goto reduce;
    }
    /* Two or more tiles off this line: turn so the skid ends level with
     * the player, then the new heading runs straight in. */
    if (OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(lane->tilesBeforeTurnSkid) == 0
        || momentum->turnDirection
            < OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(lane->tilesBeforeTurnSkid)) {
        goto reduce;
    }
    tiles = SkidAim_ProfileSkidTiles(time, lane, FALSE);
    if (tiles != 0 && along == (s32)tiles) {
        call->direction = dir < 2 ? (side > 0 ? 3 : 2) : (side > 0 ? 1 : 0);
    }
reduce:
    SkidAim_ReduceInput(policy, call);
}

void __attribute__((naked, used, section(".overworld_skid_aim_entry")))
OverworldSkidAim_ReduceInput(void)
{
    __asm__ volatile("b SkidAim_Input\n");
}

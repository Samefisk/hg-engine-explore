#include "../../include/overworld_wild_helper.h"
#include "../../include/config.h"
#include "../../include/constants/file.h"
#include "../../include/constants/game.h"
#include "../../include/constants/item.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_spawns.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/overlay.h"
#include "../../include/pokemon.h"
#include "../../include/pokemon_storage_system.h"
#include "../../include/rtc.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/sound.h"
#include "../../include/sprite.h"

extern u32 space_for_setmondata;
u16 LONG_CALL MapHeader_GetMapSec(u32 map_no);
__asm__(
    ".global OverworldWildSpawns_StartFollowerReleaseBounce\n"
    ".type OverworldWildSpawns_StartFollowerReleaseBounce, %function\n"
    ".set OverworldWildSpawns_StartFollowerReleaseBounce, 0x0224F299\n"
    ".global OverworldWildSpawns_TickFollowerReleasePresentation\n"
    ".type OverworldWildSpawns_TickFollowerReleasePresentation, %function\n"
    ".set OverworldWildSpawns_TickFollowerReleasePresentation, 0x02250115\n"
    ".global OverworldWildSpawns_RenderPlayerBallProjectile\n"
    ".type OverworldWildSpawns_RenderPlayerBallProjectile, %function\n"
    ".set OverworldWildSpawns_RenderPlayerBallProjectile, 0x02250295\n");

BOOL OverworldWildSpawns_StartFollowerReleaseBounce(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    void *projectile,
    int slot);

#define OW_WILD_HELPER_GRASS_SLOTS 12
#define OW_WILD_HELPER_SURF_SLOTS 5
#define OW_WILD_HELPER_FISH_SLOTS 5
#define OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS 12
#define OW_WILD_HELPER_HEADBUTT_SPECIAL_SLOTS 6
#define OW_WILD_HELPER_HEADBUTT_NORMAL_TREE 0
#define OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE 1
#define OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT 20
#define OW_WILD_HELPER_SPAWN_MIN_DISTANCE 4
#define OW_WILD_HELPER_SPAWN_MAX_DISTANCE 8
#define OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH 1
#define OW_WILD_HELPER_SPAWN_POSITION_BUDGET 16
#define OW_WILD_HELPER_SPAWN_POSITION_DIAMETER (OW_WILD_HELPER_SPAWN_MAX_DISTANCE * 2 + 1)
#define OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT \
    (OW_WILD_HELPER_SPAWN_POSITION_DIAMETER * OW_WILD_HELPER_SPAWN_POSITION_DIAMETER)
#define OW_WILD_HELPER_SPAWN_POSITION_STRIDE 73
#define OW_WILD_HELPER_SPECIES_MASK 0x7FF
#define OW_WILD_HELPER_FORM_SHIFT 11
#define OW_WILD_HELPER_THROW_CARRIED_Y_OFFSET_FX32 (0x10000 / 2)
#define OW_WILD_HELPER_PLAYER_BALL_TAG 87
#define OW_WILD_HELPER_PLAYER_BALL_WHITE_TAG 231
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_WHITE_FRAMES 3
#define OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32 0x4000
#define OW_WILD_HELPER_PLAYER_BALL_RIGHT_HAND_OFFSET_FX32 0x6000
#define OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32 0x8000
#define OW_WILD_HELPER_PLAYER_BALL_SIDE_CURVE_FX32 0x5000
#define OW_WILD_HELPER_PLAYER_BALL_MOTION_SCALE 256
#define OW_WILD_HELPER_PLAYER_BALL_ACCEL_END 64
#define OW_WILD_HELPER_PLAYER_BALL_DECEL_DIVISOR 192
#define OW_WILD_HELPER_PLAYER_BALL_HANG_FRAMES 4
#define OW_WILD_HELPER_PLAYER_BALL_FALL_FRAMES 12
#define OW_WILD_HELPER_PLAYER_BALL_ROTATION_MIN_STEP 0x2000
#define OW_WILD_HELPER_PLAYER_BALL_ROTATION_MAX_STEP 0x4000
#define OW_WILD_HELPER_PLAYER_BALL_ROTATION_HANG_END_STEP 0x800
#define OW_WILD_HELPER_PLAYER_BALL_ROTATION_PIVOT_Y 0x6000
#define OW_WILD_HELPER_PLAYER_BALL_FRAMES_PER_TILE 2
#define OW_WILD_HELPER_PLAYER_BALL_LAUNCH_FRAMES 1
#define OW_WILD_HELPER_PLAYER_BALL_MAX_FRAMES 21
#define OW_WILD_HELPER_PLAYER_BALL_MIN_DISTANCE_FX32 0x50000
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_STEP_FX32 0x2000
#define OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES 40
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_RISE_FX32 0x3000
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_PULSE_STEP_FX32 0x100
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE SEQ_SE_GS_DOWSING_SINGLE
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_SLOW_INTERVAL 12
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_FAST_INTERVAL 5
#define OW_WILD_HELPER_PLAYER_BALL_CHARGE_SOUND_COMPLETE 0xFF
#define OW_WILD_HELPER_PLAYER_BALL_HIT_RADIUS_FX32 0x7000
#define OW_WILD_HELPER_PLAYER_BALL_AIM_HALF_WIDTH_FX32 0x18000
#define OW_WILD_HELPER_PLAYER_BALL_AIM_MIN_FORWARD_FX32 0x10000
#define OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT 12
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_ASCENT_FRAMES 30
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_FLASH_FRAMES 4
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME \
    (OW_WILD_HELPER_PLAYER_BALL_IMPACT_ASCENT_FRAMES - 1)
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_HOLD_FRAMES 4
#define OW_WILD_HELPER_PLAYER_BALL_SECOND_FLASH_EXTRA_FRAMES 4
#define OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_START_FRAME 22
#define OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_END_FRAME 33
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME \
    (OW_WILD_HELPER_PLAYER_BALL_IMPACT_ASCENT_FRAMES \
        + OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_HOLD_FRAMES)
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME 5
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES \
    (OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME \
        + OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES \
        - OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME - 1)
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX 256
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_REBOUND_STEP_FX32 0x1000
#define OW_WILD_HELPER_PLAYER_BALL_LAND_FRAMES 16
#define OW_WILD_HELPER_EXPERIMENT_BASE_ARC_APEX_HOLD 1
#if OW_WILD_HELPER_EXPERIMENT_BASE_ARC_APEX_HOLD
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES 14
#else
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES 15
#endif
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES 18
#define OW_WILD_HELPER_PLAYER_BALL_END_ARC_PAUSE_FRAMES 2
#define OW_WILD_HELPER_PLAYER_BALL_THIRD_ARC_PAUSE_FRAMES 4
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32 0x600
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_HEIGHT_UNITS 2400
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_HEIGHT_SCALE 125
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS 20
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_CURVE_MAX 32
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_LAUNCH_FRAME 1
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_35_DEGREES 0x18E4
#if OW_WILD_HELPER_EXPERIMENT_BASE_ARC_APEX_HOLD
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_START_FRAME 3
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_END_FRAME 10
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_PROGRESS_MAX 28
#else
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_START_FRAME 3
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_END_FRAME 10
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_PROGRESS_MAX 28
#endif
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ROTATION_START_FRAME 5
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ROTATION_END_FRAME 14
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ROTATION_PROGRESS_MAX 45
/* Tag 87 is a 3D billboard, so visible roll must run after its BB command. */
#define OW_WILD_HELPER_FIELD_ACTOR_ROTATION_MATRIX_OFFSET 0x18
#define OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_OFFSET 0x50
#define OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET 0x54
#define OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_TIMING_OFFSET 0x55
#define OW_WILD_HELPER_FIELD_ACTOR_PALETTE_KEY_OFFSET 0x9C
#define OW_WILD_HELPER_FIELD_ACTOR_BILLBOARD_COMMAND 7
#define OW_WILD_HELPER_FIELD_ACTOR_CALLBACK_AFTER_COMMAND 3
#define OW_WILD_HELPER_PLAYER_BALL_RESULT_FRAMES 24
#define OW_WILD_HELPER_PLAYER_BALL_SHAKE_SE SEQ_SE_DP_BOWA
#define OW_WILD_HELPER_PLAYER_BALL_IMPACT_SE SEQ_SE_DP_BALL_OPEN
#define OW_WILD_HELPER_PLAYER_BALL_DRAW_IN_SE SEQ_SE_DP_BALL_DRAW_IN
#define OW_WILD_HELPER_PLAYER_BALL_BREAKOUT_SE SEQ_SE_DP_BOWA2
#define OW_WILD_HELPER_PLAYER_BALL_CAUGHT_SE SEQ_SE_DP_GETTING
#define OW_WILD_HELPER_PLAYER_BALL_THROW_SE SEQ_SE_DP_NAGERU
#define OW_WILD_HELPER_FOLLOWER_EMERGE_SE SEQ_SE_DP_BOWA2
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE 0
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING 1
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING 2
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT 3
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_LANDED 4
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING 5
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT 6
#define OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT 7
#define OW_WILD_HELPER_PC_STORAGE_SAVE_BLOCK 41
#define OW_WILD_HELPER_CAPTURE_DESTINATION_PARTY (-1)
#define OW_WILD_HELPER_CAPTURE_DESTINATION_NONE (-2)
#define OW_WILD_HELPER_CAPTURE_HEAP_RESERVE_SIZE (101 * sizeof(u32))
#define OW_WILD_HELPER_VAR_SPECIAL_LAST_TALKED 0x800D
#define OW_WILD_HELPER_CAPTURE_TERRAIN_GRASS 2
#define OW_WILD_HELPER_CAPTURE_TERRAIN_WATER 7
#define OW_WILD_DESPAWN_TELEMETRY_MAGIC 0x4F574450
#define OW_WILD_DESPAWN_CONTEXT_CURRENT (1 << 0)
#define OW_WILD_DESPAWN_CONTEXT_TASK_BUSY (1 << 1)
#define OW_WILD_DESPAWN_CONTEXT_POINTER_IN_ARRAY (1 << 2)
#define OW_WILD_DESPAWN_CONTEXT_OBJECT_ACTIVE (1 << 3)
#define OW_WILD_DESPAWN_CONTEXT_EXACT_ID (1 << 4)
#define OW_WILD_DESPAWN_CONTEXT_EXACT_SCRIPT (1 << 5)
#define OW_WILD_BATTLE_RESULT_WIN 0x1
#define OW_WILD_BATTLE_RESULT_CAUGHT 0x4
#define OW_WILD_BATTLE_RESULT_PLAYER_FLED 0x5
#define OW_WILD_BATTLE_RESULT_TRY_FLEE 0x80
#define OW_WILD_HELPER_PAL_PARAM_SHINY 1
#define OW_WILD_HELPER_PAL_PARAM_ENABLE 2
#define OW_WILD_HELPER_NELEMS(array) (sizeof(array) / sizeof((array)[0]))
#define OverworldWildHelper_LoadHeadbuttDataByMapId(callbacks, context, mapId, offset, dest, size) \
    OverworldWildHelper_LoadArchiveData(callbacks, context, ARC_HEADBUTT_TREES, mapId, offset, dest, size)

typedef enum OverworldWildHelperFishingRodTable {
    OW_WILD_HELPER_FISHING_ROD_OLD,
    OW_WILD_HELPER_FISHING_ROD_GOOD,
    OW_WILD_HELPER_FISHING_ROD_SUPER,
} OverworldWildHelperFishingRodTable;

typedef struct OverworldWildHelperLandEncounterData {
    u8 levels[OW_WILD_HELPER_GRASS_SLOTS];
    u16 morningSpecies[OW_WILD_HELPER_GRASS_SLOTS];
    u16 daySpecies[OW_WILD_HELPER_GRASS_SLOTS];
    u16 nightSpecies[OW_WILD_HELPER_GRASS_SLOTS];
} OverworldWildHelperLandEncounterData;

typedef struct OverworldWildHelperEncounterDataSlot {
    u8 minLevel;
    u8 maxLevel;
    u16 species;
} OverworldWildHelperEncounterDataSlot;

typedef struct OverworldWildHelperEncounterData {
    u8 walkingRate;
    u8 surfingRate;
    u8 rockSmashRate;
    u8 oldRodRate;
    u8 goodRodRate;
    u8 superRodRate;
    u8 padding[2];
    OverworldWildHelperLandEncounterData landSlots;
    u16 hoennSoundsSpecies[2];
    u16 sinnohSoundsSpecies[2];
    OverworldWildHelperEncounterDataSlot surfSlots[OW_WILD_HELPER_SURF_SLOTS];
    OverworldWildHelperEncounterDataSlot rockSmashSlots[2];
    OverworldWildHelperEncounterDataSlot oldRodSlots[OW_WILD_HELPER_FISH_SLOTS];
    OverworldWildHelperEncounterDataSlot goodRodSlots[OW_WILD_HELPER_FISH_SLOTS];
    OverworldWildHelperEncounterDataSlot superRodSlots[OW_WILD_HELPER_FISH_SLOTS];
    u16 landSwarm;
    u16 surfSwarm;
    u16 nightFish;
    u16 fishSwarm;
} OverworldWildHelperEncounterData;

typedef struct OverworldWildHelperHeadbuttHeader {
    u16 normalTreeCount;
    u16 specialTreeCount;
} OverworldWildHelperHeadbuttHeader;

typedef struct OverworldWildHelperHeadbuttEncounterSlot {
    u16 species;
    u8 minLevel;
    u8 maxLevel;
} OverworldWildHelperHeadbuttEncounterSlot;

typedef struct OverworldWildHelperCoordOffset {
    s8 dx;
    s8 dy;
} OverworldWildHelperCoordOffset;

typedef struct OverworldWildHelperRotationMatrix {
    fx32 values[3][3];
} OverworldWildHelperRotationMatrix;

void LONG_CALL MTX_RotZ33_(
    OverworldWildHelperRotationMatrix *matrix,
    fx32 sinValue,
    fx32 cosValue);
void LONG_CALL G3_MultMtx33_(
    const OverworldWildHelperRotationMatrix *matrix);
extern const s16 FX_SinCosTable_[];
typedef union OverworldWildHelperPlayerBallScratch {
    /* IMPACT owns this arm until the target palette has been restored. */
    u32 whitePaletteKey;
    /* The successful fourth shake owns this arm until store or rollback. */
    struct PartyPokemon *preparedPokemon;
} OverworldWildHelperPlayerBallScratch;

typedef struct OverworldWildHelperPlayerBallProjectileState {
    FieldSystem *fieldSystem;
    OverworldWildSpawnState *state;
    MapObjectMan *manager;
    LocalMapObject *objects;
    LocalMapObject *object;
    OverworldWildHelperPlayerBallScratch scratch;
    s32 startX;
    s32 startY;
    s32 startZ;
    s32 targetX;
    s32 targetY;
    s32 targetZ;
    s32 startHeight;
    OverworldWildHelperRotationMatrix rotationMatrix;
    s16 rotation;
    u16 mapId;
    u16 mapGeneration;
    u16 impactEncounterGeneration;
    s8 impactSlot;
    u8 elapsedFrames;
    u8 totalFrames;
    u8 phase;
    u8 objectId;
    u8 shakeChecks;
    u8 shakeIndex;
    u8 targetHadPassThrough;
    u8 targetWhiteActive;
} OverworldWildHelperPlayerBallProjectileState;

#if OW_WILD_HELPER_EXPERIMENT_BASE_ARC_APEX_HOLD
/* Experiment: match arc four's apex drift and asymptotic endpoint settle. */
static const u8 sOverworldWildHelperShakeCurveProgress[] = {
    0, 17, 26, 30, 31, 32, 32,
    32, 32, 32, 32, 32, 32, 32,
};

static const u16 sOverworldWildHelperShakeHeightProgress[] = {
    0, 3954, 5283, 5595, 5600, 5584, 5532,
    5278, 4751, 3799, 2739, 2506, 2423, 2402,
};
#else
/* 20% faster motion, a tighter corner, and four paused endpoint frames. */
static const u8 sOverworldWildHelperShakeCurveProgress[] = {
    0, 14, 23, 29, 31, 32, 32, 32,
    32, 32, 32, 32, 32, 32, 32,
};

static const u16 sOverworldWildHelperShakeHeightProgress[] = {
    0, 3091, 4387, 4906, 4646, 4128, 3610, 3178,
    2918, 2659, 2400, 2400, 2400, 2400, 2400,
};
#endif

static const u8 sOverworldWildHelperCaughtCurveProgress[] = {
    0, 10, 18, 24, 28, 30, 31, 32, 32,
    32, 32, 32, 32, 32, 32, 32, 32, 32,
};

/* Doubled acceleration contrast, tapering to a stop at the capture apex. */
static const u16 sOverworldWildHelperImpactProgress[] = {
    0, 1, 4, 10, 21, 39, 63, 90, 117, 143,
    165, 185, 201, 215, 225, 232, 237, 241, 244, 246,
    247, 248, 249, 250, 251, 252, 253, 254, 255, 256,
};

static const u16 sOverworldWildHelperImpactRotationProgress[] = {
    0, 32, 51, 68, 84, 99, 112, 125, 136, 146,
    157, 166, 176, 184, 193, 200, 208, 214, 221, 226,
    232, 236, 241, 244, 248, 251, 253, 255, 256, 256,
};

/* Longer success arc: drift across a broad apex, then accelerate down. */
static const u16 sOverworldWildHelperCaughtHeightProgress[] = {
    7200, 9800, 11400, 12300, 12700, 12800, 12790, 12760, 12680,
    12480, 11800, 10400, 8200, 4800, 500, 180, 50, 10,
};

typedef char OverworldWildHelperShakeFrameCountCheck[
    OW_WILD_HELPER_NELEMS(sOverworldWildHelperShakeCurveProgress)
            == OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES
        && OW_WILD_HELPER_NELEMS(sOverworldWildHelperShakeHeightProgress)
            == OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES
        && OW_WILD_HELPER_NELEMS(sOverworldWildHelperCaughtCurveProgress)
            == OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES
        && OW_WILD_HELPER_NELEMS(sOverworldWildHelperCaughtHeightProgress)
            == OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES
        && OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME
            < OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES
        && OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES
                - OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME
            == OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES
                - OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME - 1
        && OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME
            == OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME
                + OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_HOLD_FRAMES + 1
        && OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME > 0
        && OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME
            < OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES
        && OW_WILD_HELPER_NELEMS(sOverworldWildHelperImpactProgress)
            == OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME + 1
        && OW_WILD_HELPER_NELEMS(
                sOverworldWildHelperImpactRotationProgress)
            == OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME + 1
        ? 1
        : -1];

static const u8 sOverworldWildHelperGrassSlotWeights[OW_WILD_HELPER_GRASS_SLOTS] = {
    20, 20, 10, 10, 10, 10, 5, 5, 4, 4, 1, 1,
};

static const u8 sOverworldWildHelperFiveSlotWeights[OW_WILD_HELPER_SURF_SLOTS] = {
    60, 30, 5, 4, 1,
};
typedef char OverworldWildHelperFiveSlotWeightsMatchSlotCounts[
    OW_WILD_HELPER_SURF_SLOTS == OW_WILD_HELPER_FISH_SLOTS
            && OW_WILD_HELPER_NELEMS(sOverworldWildHelperFiveSlotWeights)
                == OW_WILD_HELPER_FISH_SLOTS
        ? 1
        : -1];

static const OverworldWildHelperCoordOffset sOverworldWildHelperCardinalOffsets[] = {
    { 0, 1 },
    { 0, -1 },
    { -1, 0 },
    { 1, 0 },
};

#if OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH
// Stored as cursor + 1 so zero can mean uninitialized after the helper overlay is loaded.
static u16 sOverworldWildHelperSpawnPositionCursor[2];
#endif
static OverworldWildHelperPlayerBallProjectileState sOverworldWildHelperPlayerBallProjectile;
static BOOL sOverworldWildHelperPlayerBallRWasDown;
static BOOL sOverworldWildHelperPlayerBallInputArmed = TRUE;
static BOOL sOverworldWildHelperPlayerBallStaleCheckDone;
static u8 sOverworldWildHelperPlayerBallChargeFrames;
static u8 sOverworldWildHelperPlayerBallChargeSoundTimer;
static void *sOverworldWildHelperCaptureHeapReserve;
static void OverworldWildHelper_RestoreCaptureTargetPalette(
    FieldSystem *fieldSystem);
static void OverworldWildHelper_ApplyPlayerBallPostBillboardRotation(
    void *renderState);

static BOOL __attribute__((noinline))
OverworldWildHelper_IsPlayerBallFrameServiceActive(void)
{
    return !sOverworldWildHelperPlayerBallStaleCheckDone;
}

static int OverworldWildHelper_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildHelper_Max(int lhs, int rhs)
{
    return lhs > rhs ? lhs : rhs;
}

static int OverworldWildHelper_Min(int lhs, int rhs)
{
    return lhs < rhs ? lhs : rhs;
}

static int OverworldWildHelper_DirectionDeltaX(u8 direction)
{
    switch (direction) {
    case OW_WILD_HELPER_DIRECTION_LEFT:
        return -1;
    case OW_WILD_HELPER_DIRECTION_RIGHT:
        return 1;
    default:
        return 0;
    }
}

static int OverworldWildHelper_DirectionDeltaY(u8 direction)
{
    switch (direction) {
    case OW_WILD_HELPER_DIRECTION_UP:
        return -1;
    case OW_WILD_HELPER_DIRECTION_DOWN:
        return 1;
    default:
        return 0;
    }
}

static BOOL OverworldWildHelper_AreSpawnCallbacksValid(const OverworldWildHelperSpawnCallbacks *callbacks)
{
    const void * const *callbackFields = (const void * const *)callbacks;
    u32 callbackIndex;

    if (callbacks == NULL) {
        return FALSE;
    }

    for (callbackIndex = 0;
         callbackIndex < sizeof(*callbacks) / sizeof(callbackFields[0]);
         callbackIndex++) {
        if (callbackFields[callbackIndex] == NULL) {
            return FALSE;
        }
    }

    return TRUE;
}

static BOOL OverworldWildHelper_GetMapId(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u16 *mapId)
{
    return callbacks->getMapId(context, mapId);
}

static BOOL OverworldWildHelper_LoadArchiveData(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    int arcId,
    int datId,
    int offset,
    void *dest,
    int size)
{
    return callbacks->loadArchiveData(context, arcId, datId, offset, dest, size);
}

static BOOL OverworldWildHelper_TryPickSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain requestedTerrain,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperPlayerState playerState;
#if OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH
    u16 *storedCursor;
    u32 cursor;
    u32 checked = 0;
    u32 visited = 0;

    if (!callbacks->getPlayerState(context, &playerState)) {
        return FALSE;
    }

    storedCursor = &sOverworldWildHelperSpawnPositionCursor[
        requestedTerrain == OW_WILD_SPAWN_TERRAIN_SURF];
    cursor = *storedCursor == 0
        ? gf_rand() % OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT
        : *storedCursor - 1;

    while (checked < OW_WILD_HELPER_SPAWN_POSITION_BUDGET
        && visited < OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT) {
        u32 candidate = cursor;
        int dx;
        int dy;
        int x;
        int y;
        OverworldWildSpawnTerrain terrain;

        cursor = (cursor + OW_WILD_HELPER_SPAWN_POSITION_STRIDE)
            % OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT;
        visited++;
        dx = candidate % OW_WILD_HELPER_SPAWN_POSITION_DIAMETER
            - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
        dy = candidate / OW_WILD_HELPER_SPAWN_POSITION_DIAMETER
            - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;

        if (OverworldWildHelper_Max(
                OverworldWildHelper_Abs(dx),
                OverworldWildHelper_Abs(dy))
            < OW_WILD_HELPER_SPAWN_MIN_DISTANCE) {
            continue;
        }

        checked++;
        x = playerState.playerX + dx;
        y = playerState.playerY + dy;
        if (!callbacks->tryGetSpawnTerrain(context, x, y, &terrain)
            || terrain != requestedTerrain
            || callbacks->isTileOccupied(context, x, y)
            || callbacks->isNearActiveSpawn(
                context,
                x,
                y,
                OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        *storedCursor = cursor + 1;
        return TRUE;
    }

    *storedCursor = cursor + 1;
    return FALSE;
#else
    u32 candidateCount = 0;
    int x;
    int y;

    if (!callbacks->getPlayerState(context, &playerState)) {
        return FALSE;
    }

    for (y = playerState.playerY - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
         y <= playerState.playerY + OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
         y++) {
        for (x = playerState.playerX - OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
             x <= playerState.playerX + OW_WILD_HELPER_SPAWN_MAX_DISTANCE;
             x++) {
            int dx = x - playerState.playerX;
            int dy = y - playerState.playerY;
            int distance = OverworldWildHelper_Max(
                OverworldWildHelper_Abs(dx),
                OverworldWildHelper_Abs(dy));
            OverworldWildSpawnTerrain terrain;

            if (distance < OW_WILD_HELPER_SPAWN_MIN_DISTANCE
                || distance > OW_WILD_HELPER_SPAWN_MAX_DISTANCE
                || !callbacks->tryGetSpawnTerrain(context, x, y, &terrain)
                || terrain != requestedTerrain
                || callbacks->isTileOccupied(context, x, y)
                || callbacks->isNearActiveSpawn(
                    context,
                    x,
                    y,
                    OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE)) {
                continue;
            }

            candidateCount++;
            if ((gf_rand() % candidateCount) == 0) {
                position->startX = x;
                position->startY = y;
            }
        }
    }

    return candidateCount != 0;
#endif
}

static BOOL OverworldWildHelper_TryPickFishingSpawnPosition(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnPosition *position)
{
    OverworldWildHelperPlayerState playerState;
    u32 start;
    u32 i;

    if (position == NULL
        || !callbacks->getPlayerState(context, &playerState)) {
        return FALSE;
    }

    start = gf_rand() & 3;
    for (i = 0; i < OW_WILD_HELPER_NELEMS(sOverworldWildHelperCardinalOffsets); i++) {
        const OverworldWildHelperCoordOffset *offset =
            &sOverworldWildHelperCardinalOffsets[(start + i) & 3];
        OverworldWildSpawnTerrain terrain;
        int x = playerState.playerX + offset->dx;
        int y = playerState.playerY + offset->dy;

        if (!callbacks->tryGetSpawnTerrain(context, x, y, &terrain)
            || terrain != OW_WILD_SPAWN_TERRAIN_SURF
            || callbacks->isTileOccupied(context, x, y)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        return TRUE;
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryPickHeadbuttEncounterPool(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u8 *treeType)
{
    OverworldWildHelperHeadbuttHeader header;
    u32 treeCount;
    u16 mapId;

    if (treeType == NULL
        || !OverworldWildHelper_GetMapId(callbacks, context, &mapId)
        || !OverworldWildHelper_LoadHeadbuttDataByMapId(
            callbacks,
            context,
            mapId,
            0,
            &header,
            sizeof(header))) {
        return FALSE;
    }

    treeCount = header.normalTreeCount + header.specialTreeCount;
    if (treeCount == 0) {
        return FALSE;
    }

    *treeType = (gf_rand() % treeCount) < header.normalTreeCount
        ? OW_WILD_HELPER_HEADBUTT_NORMAL_TREE
        : OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE;
    return TRUE;
}

static BOOL OverworldWildHelper_TryPickSpawnPositionForTerrain(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    OverworldWildSpawnPosition *position)
{
    if (position == NULL) {
        return FALSE;
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
        return OverworldWildHelper_TryPickHeadbuttEncounterPool(
            callbacks,
            context,
            &position->headbuttTreeType);
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_FISHING) {
        return OverworldWildHelper_TryPickFishingSpawnPosition(callbacks, context, position);
    }
    return OverworldWildHelper_TryPickSpawnPosition(callbacks, context, terrain, position);
}

static u8 OverworldWildHelper_RollWeightedSlot(const u8 *weights, u8 count)
{
    u32 roll = gf_rand() % 100;
    u8 slot;

    for (slot = 0; slot < count; slot++) {
        if (roll < weights[slot]) {
            return slot;
        }
        roll -= weights[slot];
    }

    return count - 1;
}

static BOOL OverworldWildHelper_TryRollHeadbuttEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    u8 treeType,
    OverworldWildRolledEncounter *encounter)
{
    int attempts;
    u32 slotOffset = sizeof(OverworldWildHelperHeadbuttHeader);
    u8 slotCount = OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS;
    u16 mapId;

    if (encounter == NULL
        || !OverworldWildHelper_GetMapId(callbacks, context, &mapId)) {
        return FALSE;
    }

    if (treeType == OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE) {
        slotOffset += OW_WILD_HELPER_HEADBUTT_NORMAL_SLOTS
            * sizeof(OverworldWildHelperHeadbuttEncounterSlot);
        slotCount = OW_WILD_HELPER_HEADBUTT_SPECIAL_SLOTS;
    }

    for (attempts = 0; attempts < slotCount; attempts++) {
        OverworldWildHelperHeadbuttEncounterSlot slot;
        u32 slotIndex = gf_rand() % slotCount;
        u16 species;

        if (!OverworldWildHelper_LoadHeadbuttDataByMapId(
                callbacks,
                context,
                mapId,
                slotOffset + slotIndex * sizeof(slot),
                &slot,
                sizeof(slot))) {
            return FALSE;
        }

        species = slot.species & OW_WILD_HELPER_SPECIES_MASK;
        if (species != SPECIES_NONE && slot.minLevel != 0) {
            encounter->species = species;
            encounter->form = slot.species >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = slot.minLevel;
            if (slot.maxLevel > slot.minLevel) {
                encounter->level += gf_rand() % (slot.maxLevel - slot.minLevel + 1);
            }
            return TRUE;
        }
    }

    if (treeType == OW_WILD_HELPER_HEADBUTT_SPECIAL_TREE) {
        return OverworldWildHelper_TryRollHeadbuttEncounter(
            callbacks,
            context,
            OW_WILD_HELPER_HEADBUTT_NORMAL_TREE,
            encounter);
    }

    return FALSE;
}

static const u16 *OverworldWildHelper_GetTimeOfDaySpeciesTable(
    const OverworldWildHelperLandEncounterData *landSlots)
{
    if ((gf_rand() % 100) < OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT) {
        switch (gf_rand() % 3) {
        case 0:
            return landSlots->morningSpecies;
        case 1:
            return landSlots->daySpecies;
        case 2:
        default:
            return landSlots->nightSpecies;
        }
    }

    switch (GF_RTC_GetTimeOfDayWildParam()) {
    case TIMEOFDAY_WILD_MORN:
        return landSlots->morningSpecies;
    case TIMEOFDAY_WILD_NITE:
        return landSlots->nightSpecies;
    case TIMEOFDAY_WILD_DAY:
    default:
        return landSlots->daySpecies;
    }
}

static BOOL OverworldWildHelper_TryRollLandEncounter(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildRolledEncounter *encounter)
{
    int attempts;
    const u16 *speciesTable;

    speciesTable = OverworldWildHelper_GetTimeOfDaySpeciesTable(&encounterData->landSlots);

    for (attempts = 0; attempts < OW_WILD_HELPER_GRASS_SLOTS; attempts++) {
        u8 slot = OverworldWildHelper_RollWeightedSlot(
            sOverworldWildHelperGrassSlotWeights,
            OW_WILD_HELPER_GRASS_SLOTS);
        u16 encodedSpecies = speciesTable[slot];
        u16 species = encodedSpecies & OW_WILD_HELPER_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData->landSlots.levels[slot] != 0) {
            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = encounterData->landSlots.levels[slot];
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryRollSurfEncounter(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildRolledEncounter *encounter)
{
    int attempts;

    for (attempts = 0; attempts < OW_WILD_HELPER_SURF_SLOTS; attempts++) {
        u8 slot = OverworldWildHelper_RollWeightedSlot(
            sOverworldWildHelperFiveSlotWeights,
            OW_WILD_HELPER_SURF_SLOTS);
        u16 encodedSpecies = encounterData->surfSlots[slot].species;
        u16 species = encodedSpecies & OW_WILD_HELPER_SPECIES_MASK;

        if (species != SPECIES_NONE && encounterData->surfSlots[slot].minLevel != 0) {
            u8 minLevel = encounterData->surfSlots[slot].minLevel;
            u8 maxLevel = encounterData->surfSlots[slot].maxLevel;

            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = minLevel;
            if (maxLevel > minLevel) {
                encounter->level += gf_rand() % (maxLevel - minLevel + 1);
            }
            return TRUE;
        }
    }

    return FALSE;
}

static const OverworldWildHelperEncounterDataSlot *OverworldWildHelper_GetFishingSlots(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildHelperFishingRodTable rodTable)
{
    switch (rodTable) {
    case OW_WILD_HELPER_FISHING_ROD_OLD:
        return encounterData->oldRodSlots;
    case OW_WILD_HELPER_FISHING_ROD_GOOD:
        return encounterData->goodRodSlots;
    case OW_WILD_HELPER_FISHING_ROD_SUPER:
    default:
        return encounterData->superRodSlots;
    }
}

static u8 OverworldWildHelper_GetFishingRate(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildHelperFishingRodTable rodTable)
{
    switch (rodTable) {
    case OW_WILD_HELPER_FISHING_ROD_OLD:
        return encounterData->oldRodRate;
    case OW_WILD_HELPER_FISHING_ROD_GOOD:
        return encounterData->goodRodRate;
    case OW_WILD_HELPER_FISHING_ROD_SUPER:
    default:
        return encounterData->superRodRate;
    }
}

static BOOL OverworldWildHelper_FishingTableHasValidSlot(
    const OverworldWildHelperEncounterDataSlot *slots)
{
    u8 slot;

    for (slot = 0; slot < OW_WILD_HELPER_FISH_SLOTS; slot++) {
        if ((slots[slot].species & OW_WILD_HELPER_SPECIES_MASK) != SPECIES_NONE
            && slots[slot].minLevel != 0) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryPickFishingRodTable(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildHelperFishingRodTable *rodTable)
{
    u16 totalRate = 0;
    u16 roll;
    u8 rod;

    for (rod = 0; rod < 3; rod++) {
        OverworldWildHelperFishingRodTable currentRod =
            (OverworldWildHelperFishingRodTable)rod;
        const OverworldWildHelperEncounterDataSlot *slots =
            OverworldWildHelper_GetFishingSlots(encounterData, currentRod);
        u8 rate = OverworldWildHelper_GetFishingRate(encounterData, currentRod);

        if (rate != 0 && OverworldWildHelper_FishingTableHasValidSlot(slots)) {
            totalRate += rate;
        }
    }

    if (totalRate == 0) {
        return FALSE;
    }

    roll = gf_rand() % totalRate;
    for (rod = 0; rod < 3; rod++) {
        OverworldWildHelperFishingRodTable currentRod =
            (OverworldWildHelperFishingRodTable)rod;
        const OverworldWildHelperEncounterDataSlot *slots =
            OverworldWildHelper_GetFishingSlots(encounterData, currentRod);
        u8 rate = OverworldWildHelper_GetFishingRate(encounterData, currentRod);

        if (rate == 0 || !OverworldWildHelper_FishingTableHasValidSlot(slots)) {
            continue;
        }
        if (roll < rate) {
            *rodTable = currentRod;
            return TRUE;
        }
        roll -= rate;
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryRollFishingEncounter(
    const OverworldWildHelperEncounterData *encounterData,
    OverworldWildRolledEncounter *encounter)
{
    OverworldWildHelperFishingRodTable rodTable;
    const OverworldWildHelperEncounterDataSlot *slots;
    int attempts;

    if (!OverworldWildHelper_TryPickFishingRodTable(encounterData, &rodTable)) {
        return FALSE;
    }

    slots = OverworldWildHelper_GetFishingSlots(encounterData, rodTable);
    for (attempts = 0; attempts < OW_WILD_HELPER_FISH_SLOTS; attempts++) {
        u8 slot = OverworldWildHelper_RollWeightedSlot(
            sOverworldWildHelperFiveSlotWeights,
            OW_WILD_HELPER_FISH_SLOTS);
        u16 encodedSpecies = slots[slot].species;
        u16 species = encodedSpecies & OW_WILD_HELPER_SPECIES_MASK;

        if (species != SPECIES_NONE && slots[slot].minLevel != 0) {
            u8 minLevel = slots[slot].minLevel;
            u8 maxLevel = slots[slot].maxLevel;

            encounter->species = species;
            encounter->form = encodedSpecies >> OW_WILD_HELPER_FORM_SHIFT;
            encounter->level = minLevel;
            if (maxLevel > minLevel) {
                encounter->level += gf_rand() % (maxLevel - minLevel + 1);
            }
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_TryRollEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    OverworldWildRolledEncounter *encounter)
{
    int encounterDataId;
    OverworldWildHelperEncounterData encounterData;

    if (encounter == NULL
        || !callbacks->tryGetEncounterDataId(context, &encounterDataId)
        || !OverworldWildHelper_LoadArchiveData(
            callbacks,
            context,
            ARC_ENCOUNTERS,
            encounterDataId,
            0,
            &encounterData,
            sizeof(encounterData))) {
        return FALSE;
    }

    if (terrain == OW_WILD_SPAWN_TERRAIN_SURF) {
        return OverworldWildHelper_TryRollSurfEncounter(&encounterData, encounter);
    }
    if (terrain == OW_WILD_SPAWN_TERRAIN_FISHING) {
        return OverworldWildHelper_TryRollFishingEncounter(&encounterData, encounter);
    }
    return OverworldWildHelper_TryRollLandEncounter(&encounterData, encounter);
}

static BOOL OverworldWildHelper_RollShiny(BOOL shinyAlreadySpawned, u16 shinyOddsDenominator)
{
    (void)shinyAlreadySpawned;

    return (gf_rand() % shinyOddsDenominator) == 0;
}

static u32 OverworldWildHelper_RollPersonality(void)
{
    return gf_rand() | (gf_rand() << 16);
}

static BOOL OverworldWildHelper_TryPrepareSpawnEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    const OverworldWildSpawnPosition *position,
    BOOL shinyAlreadySpawned,
    u16 shinyOddsDenominator,
    OverworldWildRolledEncounter *encounter,
    int *savedShinySlot,
    BOOL *shiny)
{
    *savedShinySlot = callbacks->findSavedShiny(context, terrain);
    if (*savedShinySlot >= 0) {
        callbacks->loadSavedShiny(context, *savedShinySlot, encounter);
        *shiny = TRUE;
    } else {
        if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
            if (!OverworldWildHelper_TryRollHeadbuttEncounter(
                    callbacks,
                    context,
                    position->headbuttTreeType,
                    encounter)) {
                return FALSE;
            }
        } else if (!OverworldWildHelper_TryRollEncounter(callbacks, context, terrain, encounter)) {
            return FALSE;
        }

        encounter->personality = OverworldWildHelper_RollPersonality();
        *shiny = OverworldWildHelper_RollShiny(shinyAlreadySpawned, shinyOddsDenominator);
    }

    if (encounter->species == SPECIES_NONE || encounter->level == 0) {
        return FALSE;
    }

    return TRUE;
}

static BOOL OverworldWildHelper_CopyPreparedSpawn(
    const OverworldWildSpawnPosition *position,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    OverworldWildPreparedSpawn *prepared)
{
    if (encounter->species == SPECIES_NONE
        || encounter->level == 0) {
        return FALSE;
    }

    prepared->position = *position;
    prepared->encounter = *encounter;
    prepared->savedShinySlot = savedShinySlot;
    prepared->shiny = shiny;
    prepared->behaviorLimitKey = 0;
    prepared->playerBallCatchValue = 0;
    prepared->behaviorProfile = (OverworldWildBehaviorProfile){ 0 };
    prepared->startup = (OverworldWildSpawnStartup){ 0 };
    prepared->behaviorClass = 0;
    return TRUE;
}

static BOOL OverworldWildHelper_TryPrepareSpawn(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    int slot,
    BOOL shinyAlreadySpawned,
    u16 shinyOddsDenominator,
    OverworldWildPreparedSpawn *prepared)
{
    OverworldWildRolledEncounter encounter;
    OverworldWildSpawnPosition position = {
        .startX = -1,
        .startY = -1,
    };
    int savedShinySlot;
    BOOL shiny;

    if (!OverworldWildHelper_AreSpawnCallbacksValid(callbacks)
        || prepared == NULL
        || (!OverworldWildHelper_TryPickSpawnPositionForTerrain(
                callbacks,
                context,
                terrain,
                &position)
            && terrain != OW_WILD_SPAWN_TERRAIN_LAND
            && terrain != OW_WILD_SPAWN_TERRAIN_SURF)
        || !OverworldWildHelper_TryPrepareSpawnEncounter(
            callbacks,
            context,
            terrain,
            &position,
            shinyAlreadySpawned,
            shinyOddsDenominator,
            &encounter,
            &savedShinySlot,
            &shiny)) {
        return FALSE;
    }

    (void)terrain;
    (void)slot;
    return OverworldWildHelper_CopyPreparedSpawn(
        &position,
        &encounter,
        shiny,
        savedShinySlot,
        prepared);
}

static BOOL OverworldWildHelper_TryPrepareEncounterSpawn(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    int slot,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    BOOL rollPersonality,
    OverworldWildPreparedSpawn *prepared)
{
    OverworldWildRolledEncounter rolledEncounter;
    OverworldWildSpawnPosition position = {
        .startX = -1,
        .startY = -1,
    };

    if (!OverworldWildHelper_AreSpawnCallbacksValid(callbacks)
        || prepared == NULL
        || encounter == NULL
        || (!OverworldWildHelper_TryPickSpawnPositionForTerrain(
                callbacks,
                context,
                terrain,
                &position)
            && terrain != OW_WILD_SPAWN_TERRAIN_LAND
            && terrain != OW_WILD_SPAWN_TERRAIN_SURF)) {
        return FALSE;
    }

    rolledEncounter = *encounter;
    if (rollPersonality) {
        rolledEncounter.personality = OverworldWildHelper_RollPersonality();
    }

    (void)terrain;
    (void)slot;
    return OverworldWildHelper_CopyPreparedSpawn(
        &position,
        &rolledEncounter,
        shiny,
        savedShinySlot,
        prepared);
}

static int OverworldWildHelper_BuildDirections(int dx, int dy, u8 *directions)
{
    int count = 0;

    if (dx == 0 && dy == 0) {
        return 0;
    }

    if (OverworldWildHelper_Abs(dx) >= OverworldWildHelper_Abs(dy)) {
        if (dx > 0) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_RIGHT;
        }
        if (dx < 0) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_LEFT;
        }
        if (dy > 0) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_DOWN;
        }
        if (dy < 0) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_UP;
        }
        return count;
    }

    if (dy > 0) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_DOWN;
    }
    if (dy < 0) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_UP;
    }
    if (dx > 0) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_RIGHT;
    }
    if (dx < 0) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_LEFT;
    }

    return count;
}

static BOOL OverworldWildHelper_IsHopVectorShape(
    const OverworldWildHelperHopConfig *config,
    int dx,
    int dy)
{
    int absDx = OverworldWildHelper_Abs(dx);
    int absDy = OverworldWildHelper_Abs(dy);

    if (absDx == 0 && absDy == 0) {
        return FALSE;
    }
    if (absDx == 0 || absDy == 0) {
        return config->allowNonCardinal < 2;
    }
    return config->allowNonCardinal
        && absDx == absDy;
}

static BOOL OverworldWildHelper_TryGetHopVector(
    const OverworldWildHelperHopConfig *config,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    int jumpDistance;
    u8 directions[4];

    if (!OverworldWildHelper_IsHopVectorShape(config, dx, dy)
        || OverworldWildHelper_BuildDirections(dx, dy, directions) == 0) {
        return FALSE;
    }

    jumpDistance = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(dx),
        OverworldWildHelper_Abs(dy));
    if (jumpDistance < config->minDistance || jumpDistance > config->maxDistance) {
        return FALSE;
    }

    if (direction != NULL) {
        *direction = directions[0];
    }
    if (distance != NULL) {
        *distance = (u8)jumpDistance;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_IsLandingAllowed(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    int landingX,
    int landingY)
{
    return validator(
        landingX,
        landingY,
        config->targetX,
        config->targetY,
        context);
}

static BOOL OverworldWildHelper_SetHopResult(
    const OverworldWildHelperHopConfig *config,
    int landingX,
    int landingY,
    int finalTargetX,
    int finalTargetY,
    u8 flags,
    OverworldWildHelperHopResult *result)
{
    u8 direction;
    u8 distance;

    (void)OverworldWildHelper_TryGetHopVector(
        config,
        landingX - config->objectX,
        landingY - config->objectY,
        &direction,
        &distance);

    result->landingX = landingX;
    result->landingY = landingY;
    result->finalTargetX = finalTargetX;
    result->finalTargetY = finalTargetY;
    result->direction = direction;
    result->distance = distance;
    result->flags = flags;
    return TRUE;
}

static void OverworldWildHelper_AddHopPlanDirection(
    s8 *stepXs,
    s8 *stepYs,
    int *directionCount,
    int stepX,
    int stepY)
{
    int i;

    /* This private helper is only called with the local plan buffers. */
    if (stepX == 0 && stepY == 0) {
        return;
    }

    for (i = 0; i < *directionCount; i++) {
        if (stepXs[i] == stepX && stepYs[i] == stepY) {
            return;
        }
    }

    if (*directionCount >= OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS) {
        return;
    }

    stepXs[*directionCount] = (s8)stepX;
    stepYs[*directionCount] = (s8)stepY;
    (*directionCount)++;
}

static int OverworldWildHelper_BuildHopPlanDirections(
    const OverworldWildHelperHopConfig *config,
    int fromX,
    int fromY,
    s8 *stepXs,
    s8 *stepYs)
{
    int directionCount = 0;
    int dx;
    int dy;
    u8 targetDirections[4];
    int targetDirectionCount;
    int i;

    dx = config->targetX - fromX;
    dy = config->targetY - fromY;
    if (config->allowNonCardinal && dx != 0 && dy != 0) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            dx > 0 ? 1 : -1,
            dy > 0 ? 1 : -1);
    }

    targetDirectionCount = OverworldWildHelper_BuildDirections(
        dx,
        dy,
        targetDirections);
    for (i = 0; i < targetDirectionCount; i++) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            OverworldWildHelper_DirectionDeltaX(targetDirections[i]),
            OverworldWildHelper_DirectionDeltaY(targetDirections[i]));
    }

    for (i = 0; i < config->directionCount; i++) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            OverworldWildHelper_DirectionDeltaX(config->directions[i]),
            OverworldWildHelper_DirectionDeltaY(config->directions[i]));
    }

    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, 0);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, 0);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 0, 1);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 0, -1);

    if (config->allowNonCardinal) {
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, 1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, -1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, 1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, -1);
    }

    return directionCount;
}

static int OverworldWildHelper_GetHopPlanDistance(
    int x,
    int y,
    int targetX,
    int targetY)
{
    return OverworldWildHelper_Max(
        OverworldWildHelper_Abs(targetX - x),
        OverworldWildHelper_Abs(targetY - y));
}

static BOOL OverworldWildHelper_IsHopTargetOneHopAway(
    const OverworldWildHelperHopConfig *config,
    int fromX,
    int fromY,
    int targetX,
    int targetY)
{
    return OverworldWildHelper_TryGetHopVector(
        config,
        targetX - fromX,
        targetY - fromY,
        NULL,
        NULL);
}

static BOOL OverworldWildHelper_HopPlanHasVisited(
    const s16 *nodeXs,
    const s16 *nodeYs,
    int nodeCount,
    int x,
    int y)
{
    int i;

    for (i = 0; i < nodeCount; i++) {
        if (nodeXs[i] == x && nodeYs[i] == y) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsHopPlanCandidate(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    int fromX,
    int fromY,
    int toX,
    int toY)
{
    return OverworldWildHelper_TryGetHopVector(
            config,
            toX - fromX,
            toY - fromY,
            NULL,
            NULL)
        && OverworldWildHelper_IsLandingAllowed(
            config,
            validator,
            context,
            toX,
            toY);
}

static BOOL __attribute__((optimize("Os", "tree-dominator-opts", "if-conversion")))
OverworldWildHelper_PickRandomBehaviorHop(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result)
{
    int dx;
    int dy;
    int targetX = 0;
    int targetY = 0;
    u32 candidateCount = 0;
    BOOL hasBacktrack = FALSE;

    for (dy = -config->maxDistance; dy <= config->maxDistance; dy++) {
        for (dx = -config->maxDistance; dx <= config->maxDistance; dx++) {
            int candidateX;
            int candidateY;

            if (dx == 0 && dy == 0) {
                continue;
            }

            candidateX = config->objectX + dx;
            candidateY = config->objectY + dy;
            if (!OverworldWildHelper_TryGetHopVector(config, dx, dy, NULL, NULL)
                || !validator(
                    candidateX,
                    candidateY,
                    candidateX,
                    candidateY,
                    context)) {
                continue;
            }
            if ((config->directionCount & 0x80) != 0) {
                int straightX = config->objectX * 2 - config->targetX;
                int straightY = config->objectY * 2 - config->targetY;

                if (candidateX == straightX && candidateY == straightY) {
                    if (config->stopOneHopAway) {
                        return OverworldWildHelper_SetHopResult(
                            config,
                            candidateX,
                            candidateY,
                            candidateX,
                            candidateY,
                            OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT,
                            result);
                    }
                    continue;
                }
                if ((config->directionCount & 0x40) != 0
                    && candidateX == config->targetX
                    && candidateY == config->targetY) {
                    hasBacktrack = TRUE;
                    continue;
                }
            }
            candidateCount++;
            if ((gf_rand() % candidateCount) == 0) {
                targetX = candidateX;
                targetY = candidateY;
            }
        }
    }

    if (candidateCount == 0) {
        if (!hasBacktrack) {
            return FALSE;
        }
        targetX = config->targetX;
        targetY = config->targetY;
    }

    return OverworldWildHelper_SetHopResult(
        config,
        targetX,
        targetY,
        targetX,
        targetY,
        OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT,
        result);
}

static BOOL OverworldWildHelper_PlanBehaviorHopStep(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result)
{
    s16 nodeXs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 nodeYs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 firstXs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 firstYs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    u8 nodeDepths[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    int head = 0;
    int tail = 0;
    int bestFirstX = 0;
    int bestFirstY = 0;
    int bestTerminalX = 0;
    int bestTerminalY = 0;
    int bestDistance = 0x7FFF;
    u8 bestDepth = 0xFF;
    BOOL bestFound = FALSE;

    if (config == NULL
        || validator == NULL
        || result == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance) {
        return FALSE;
    }

    if ((config->stopOneHopAway
            || !OverworldWildHelper_IsLandingAllowed(
                config,
                validator,
                context,
                config->targetX,
                config->targetY))
        && (config->objectX != config->targetX || config->objectY != config->targetY)
        && OverworldWildHelper_IsHopTargetOneHopAway(
            config,
            config->objectX,
            config->objectY,
            config->targetX,
            config->targetY)) {
        return FALSE;
    }

    nodeXs[tail] = (s16)config->objectX;
    nodeYs[tail] = (s16)config->objectY;
    firstXs[tail] = (s16)config->objectX;
    firstYs[tail] = (s16)config->objectY;
    nodeDepths[tail] = 0;
    tail++;

    while (head < tail) {
        int fromX = nodeXs[head];
        int fromY = nodeYs[head];
        int nodeDistance = OverworldWildHelper_GetHopPlanDistance(
            fromX,
            fromY,
            config->targetX,
            config->targetY);
        s8 stepXs[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
        s8 stepYs[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
        int planDirectionCount = OverworldWildHelper_BuildHopPlanDirections(
            config,
            fromX,
            fromY,
            stepXs,
            stepYs);
        int directionIndex;

        if (nodeDepths[head] >= OW_WILD_HELPER_HOP_PLAN_MAX_HOPS) {
            head++;
            continue;
        }

        for (directionIndex = 0; directionIndex < planDirectionCount; directionIndex++) {
            int stepX = stepXs[directionIndex];
            int stepY = stepYs[directionIndex];
            int distance;

            for (distance = config->maxDistance; distance >= config->minDistance; distance--) {
                int landingX = fromX + stepX * distance;
                int landingY = fromY + stepY * distance;
                int landingDistance = OverworldWildHelper_GetHopPlanDistance(
                    landingX,
                    landingY,
                    config->targetX,
                    config->targetY);
                int firstX = nodeDepths[head] == 0 ? landingX : firstXs[head];
                int firstY = nodeDepths[head] == 0 ? landingY : firstYs[head];
                BOOL landingIsTarget;
                BOOL landingCanReachTarget;

                if (landingDistance >= nodeDistance) {
                    continue;
                }
                /*
                 * A coordinate already reached by this breadth-first search
                 * cannot produce a shorter route.  Reject it before the
                 * caller's comparatively expensive map/object validation.
                 */
                if (OverworldWildHelper_HopPlanHasVisited(
                        nodeXs,
                        nodeYs,
                        tail,
                        landingX,
                        landingY)) {
                    continue;
                }
                if (!OverworldWildHelper_IsHopPlanCandidate(
                        config,
                        validator,
                        context,
                        fromX,
                        fromY,
                        landingX,
                        landingY)) {
                    continue;
                }

                landingIsTarget = landingX == config->targetX
                    && landingY == config->targetY;
                landingCanReachTarget =
                    !landingIsTarget
                    && OverworldWildHelper_IsHopTargetOneHopAway(
                        config,
                        landingX,
                        landingY,
                        config->targetX,
                        config->targetY);

                if (!bestFound
                    || landingDistance < bestDistance
                    || (landingDistance == bestDistance
                        && nodeDepths[head] + 1 < bestDepth)) {
                    bestFound = TRUE;
                    bestFirstX = firstX;
                    bestFirstY = firstY;
                    bestTerminalX = firstX;
                    bestTerminalY = firstY;
                    bestDistance = landingDistance;
                    bestDepth = nodeDepths[head] + 1;
                }

                if ((!config->stopOneHopAway && landingIsTarget)
                    || (config->stopOneHopAway && landingCanReachTarget)) {
                    return OverworldWildHelper_SetHopResult(
                        config,
                        firstX,
                        firstY,
                        landingX,
                        landingY,
                        OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED,
                        result);
                }

                if (config->stopOneHopAway && landingIsTarget) {
                    continue;
                }

                if (nodeDepths[head] + 1 >= OW_WILD_HELPER_HOP_PLAN_MAX_HOPS
                    || tail >= OW_WILD_HELPER_HOP_PLAN_NODE_COUNT) {
                    continue;
                }

                nodeXs[tail] = (s16)landingX;
                nodeYs[tail] = (s16)landingY;
                firstXs[tail] = (s16)firstX;
                firstYs[tail] = (s16)firstY;
                nodeDepths[tail] = nodeDepths[head] + 1;
                tail++;
            }
        }

        head++;
    }

    if (!bestFound) {
        return FALSE;
    }

    return OverworldWildHelper_SetHopResult(
        config,
        bestFirstX,
        bestFirstY,
        bestTerminalX,
        bestTerminalY,
        OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED,
        result);
}

static BOOL OverworldWildHelper_IsContextCurrent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    MapObjectMan *manager;

    if (fieldSystem == NULL
        || state == NULL
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    return state->mapId == fieldSystem->location->mapId
        && state->mapObjectMan == manager
        && state->mapObjects == manager->objects;
}

static BOOL OverworldWildHelper_IsObjectInManager(
    MapObjectMan *manager,
    LocalMapObject *object)
{
    u32 offset;
    u32 index;

    if (manager == NULL
        || manager->objects == NULL
        || object == NULL
        || (u32)object < (u32)manager->objects) {
        return FALSE;
    }
    offset = (u32)object - (u32)manager->objects;
    index = offset / sizeof(LocalMapObject);
    return index < manager->object_count
        && object == &manager->objects[index];
}

static BOOL OverworldWildHelper_IsExactObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    MapObjectMan *manager;
    LocalMapObject *object;

    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !OverworldWildHelper_IsContextCurrent(fieldSystem, state)
        || !state->spawns[slot].active
        || state->spawns[slot].mapId != fieldSystem->location->mapId
        || state->spawns[slot].objectId != OW_WILD_OBJECT_ID_START + slot) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    object = state->spawns[slot].object;
    return OverworldWildHelper_IsObjectInManager(manager, object)
        && (object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && object->id == state->spawns[slot].objectId
        && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
}

static int OverworldWildHelper_FindBattleTalkSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject,
    u16 excludedMask)
{
    return OVERWORLD_WILD_CAPTURE_UTILITIES_ENTRY->findBattleTalkSlot(
        fieldSystem,
        state,
        talkedObject,
        excludedMask);
}

static BOOL OverworldWildHelper_IsPresentationContextCurrent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    return fieldSystem == gFieldSysPtr
        && OverworldWildHelper_IsContextCurrent(fieldSystem, state);
}

static BOOL OverworldWildHelper_RemoveEncounter(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot);
static OverworldWildDespawnAuthorization OverworldWildHelper_AuthorizeDespawn(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    LocalMapObject **verifiedObject);
static void OverworldWildHelper_RecordDespawnEvent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    OverworldWildDespawnReason reason,
    OverworldWildDespawnAction action,
    u8 distance);

static BOOL OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    int slot = sOverworldWildHelperPlayerBallProjectile.impactSlot;

    return slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state == sOverworldWildHelperPlayerBallProjectile.state
        && state->mapGeneration
            == sOverworldWildHelperPlayerBallProjectile.mapGeneration
        && OverworldWildHelper_IsExactObject(fieldSystem, state, slot)
        && state->spawns[slot].encounterGeneration
            == sOverworldWildHelperPlayerBallProjectile
                .impactEncounterGeneration;
}

static void OverworldWildHelper_ReservePlayerBallCaptureTarget(
    OverworldWildSpawnState *state)
{
    int slot = sOverworldWildHelperPlayerBallProjectile.impactSlot;
    LocalMapObject *targetObject = state->spawns[slot].object;

    state->captureTargetMask |= (u16)(1u << slot);
    state->movementCooldowns[slot] = 0xFF;
    MapObject_SetBits(targetObject, BIT_VANISH | MAPOBJECTFLAG_UNK18);
}

static void OverworldWildHelper_RestorePlayerBallCaptureTarget(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    OverworldWildSpawnState *state = projectile->state;
    int slot = projectile->impactSlot;
    LocalMapObject *targetObject;

    if (state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS) {
        state->captureTargetMask &= (u16)~(1u << slot);
    }
    if (state == NULL
        || !OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
            fieldSystem,
            state)) {
        return;
    }
    targetObject = state->spawns[slot].object;
    state->movementCooldowns[slot] = OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES;
    targetObject->faceVec[0] = 0;
    targetObject->faceVec[1] = 0;
    targetObject->unk88[0] = 0;
    targetObject->unk88[1] = 0;
    MapObject_ClearBits(targetObject, BIT_VANISH);
    if (!projectile->targetHadPassThrough) {
        MapObject_ClearBits(targetObject, MAPOBJECTFLAG_UNK18);
    }
}

static void OverworldWildHelper_DiscardPreparedCapturedPokemon(void)
{
    struct PartyPokemon *pokemon =
        sOverworldWildHelperPlayerBallProjectile.scratch.preparedPokemon;

    sOverworldWildHelperPlayerBallProjectile.scratch.preparedPokemon = NULL;
    if (pokemon != NULL) {
        sys_FreeMemoryEz(pokemon);
    }
}

static BOOL OverworldWildHelper_ReserveCaptureHeap(void)
{
    if (sOverworldWildHelperCaptureHeapReserve == NULL) {
        sOverworldWildHelperCaptureHeapReserve = sys_AllocMemory(
            HEAPID_DEFAULT,
            OW_WILD_HELPER_CAPTURE_HEAP_RESERVE_SIZE);
    }
    return sOverworldWildHelperCaptureHeapReserve != NULL;
}

static void OverworldWildHelper_ReleaseCaptureHeap(void)
{
    if (sOverworldWildHelperCaptureHeapReserve != NULL) {
        sys_FreeMemoryEz(sOverworldWildHelperCaptureHeapReserve);
    }
    sOverworldWildHelperCaptureHeapReserve = NULL;
}

static u8 OverworldWildHelper_CalculatePlayerBallShakes(u8 catchValue)
{
    return OVERWORLD_WILD_CAPTURE_UTILITIES_ENTRY->calculateShakes(catchValue);
}

static BOOL OverworldWildHelper_PrepareCapturedPokemonFrame(
    FieldSystem *fieldSystem,
    const OverworldWildSpawn *spawn,
    u8 frame)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    struct PlayerProfile *profile;
    struct PartyPokemon *pokemon = projectile->scratch.preparedPokemon;
    u32 ability2;
    u32 savedFormOverride;
    u32 value;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL || spawn == NULL) {
        return FALSE;
    }
    profile = Sav2_PlayerData_GetProfileAddr(fieldSystem->savedata);
    if (profile == NULL) {
        return FALSE;
    }

    if (frame == 0) {
        if (pokemon != NULL) {
            return FALSE;
        }
        pokemon = AllocMonZeroed(HEAPID_WORLD);
        if (pokemon == NULL) {
            return FALSE;
        }
        projectile->scratch.preparedPokemon = pokemon;
        projectile->targetX = (s32)spawn->personality;
        return TRUE;
    }
    if (pokemon == NULL) {
        return FALSE;
    }
    if (frame == 2 || frame > 10) {
        return TRUE;
    }

    /* Make the preflighted heap-0 scratch available for the whole staged build. */
    if (frame == 1) {
        OverworldWildHelper_ReleaseCaptureHeap();
    }
    switch (frame) {
    case 1:
        savedFormOverride = space_for_setmondata;
        space_for_setmondata = 0;
        /*
         * Player-ball capture only reaches this frame while the field is idle;
         * pending battles and task-manager transitions cancel it first.  Thus
         * no battle-personality override is armed when PokeParaSet constructs
         * the captured Pokemon.
         */
        PokeParaSet(
            pokemon,
            spawn->species,
            spawn->level,
            32,
            RND_SET,
            (u32)projectile->targetX,
            ID_SET,
            profile->id);
        space_for_setmondata = savedFormOverride;
        break;
    case 2:
        /* Construction completed before caught-SE playback on frame one. */
        break;
    case 3:
        value = spawn->terrain == OW_WILD_SPAWN_TERRAIN_SURF
                || spawn->terrain == OW_WILD_SPAWN_TERRAIN_FISHING
            ? OW_WILD_HELPER_CAPTURE_TERRAIN_WATER
            : OW_WILD_HELPER_CAPTURE_TERRAIN_GRASS;
        sub_020720FC(
            pokemon,
            profile,
            ITEM_POKE_BALL,
            MapHeader_GetMapSec((u16)projectile->targetY),
            value,
            HEAPID_WORLD);
        break;
    case 4:
        value = spawn->form;
        SetMonData(pokemon, MON_DATA_FORM, &value);
        WildMonSetRandomHeldItem(pokemon, 0, 0);
        break;
    case 5:
        value = GrabSexFromSpeciesAndForm(
            spawn->species,
            (u32)projectile->targetX,
            spawn->form);
        SetMonData(pokemon, MON_DATA_GENDER, &value);
        break;
    case 6:
        if (spawn->form != 0) {
            InitBoxMonMoveset(&pokemon->box);
        }
        break;
    case 7:
        RecalcPartyPokemonStats(pokemon);
        break;
    case 8:
        projectile->targetY = (s32)PokeFormNoPersonalParaGet(
            spawn->species,
            spawn->form,
            PERSONAL_ABILITY_1);
        break;
    case 9:
        ability2 = PokeFormNoPersonalParaGet(
            spawn->species,
            spawn->form,
            PERSONAL_ABILITY_2);
        value = ((u32)projectile->targetX & 1) != 0 && ability2 != 0
            ? ability2
            : (u32)projectile->targetY;
        SetMonData(pokemon, MON_DATA_ABILITY, &value);
        break;
    case 10:
        TrySetBabyBondRibbon(pokemon);
        break;
    default:
        break;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_FinalizePreparedCapturedPokemon(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    struct PartyPokemon *pokemon = projectile->scratch.preparedPokemon;
    struct Party *party;
    PCStorage *storage;
    BOOL stored = FALSE;

    OverworldWildHelper_ReleaseCaptureHeap();
    if (fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || pokemon == NULL) {
        OverworldWildHelper_DiscardPreparedCapturedPokemon();
        return FALSE;
    }
    if (projectile->startY == OW_WILD_HELPER_CAPTURE_DESTINATION_PARTY) {
        party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
        stored = party != NULL
            && party->count < party->maxPossibleCount
            && PokeParty_Add(party, pokemon);
        if (stored) {
            OverworldFollowerSelector_SetPartySnapshotDirty();
        }
    } else if (projectile->startY >= 0
        && projectile->startY < NUM_PC_BOXES) {
        storage = SaveArray_Get(
            fieldSystem->savedata,
            OW_WILD_HELPER_PC_STORAGE_SAVE_BLOCK);
        stored = storage != NULL
            && PCStorage_PlaceMonInFirstEmptySlotInAnyBox(
                storage,
                &pokemon->box);
    }
    if (stored) {
        UpdatePokedexWithReceivedSpecies(fieldSystem->savedata, pokemon);
    }
    OverworldWildHelper_DiscardPreparedCapturedPokemon();
    return stored;
}

static void OverworldWildHelper_ResetPlayerBallProjectile(void)
{
    if (sOverworldWildHelperPlayerBallProjectile.targetWhiteActive) {
        OverworldWildHelper_RestoreCaptureTargetPalette(
            sOverworldWildHelperPlayerBallProjectile.fieldSystem);
    }
    OverworldWildHelper_DiscardPreparedCapturedPokemon();
    OverworldWildHelper_ReleaseCaptureHeap();
    memset(
        &sOverworldWildHelperPlayerBallProjectile,
        0,
        sizeof(sOverworldWildHelperPlayerBallProjectile));
    sOverworldWildHelperPlayerBallProjectile.mapId = MAP_NOTHING;
    sOverworldWildHelperPlayerBallProjectile.impactSlot = -1;
    sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
}

static BOOL OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    MapObjectMan *manager;

    if (projectile->phase == 0
        || fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem != projectile->fieldSystem
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL
        || projectile->object == NULL
        || projectile->mapId != fieldSystem->location->mapId) {
        return FALSE;
    }

    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager != projectile->manager
        || manager->objects != projectile->objects) {
        return FALSE;
    }

    return OverworldWildHelper_IsObjectInManager(
            manager,
            projectile->object)
        && (projectile->object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && projectile->object->id == projectile->objectId;
}

static void OverworldWildHelper_PrepareCaptureWhiteBall(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;

    if (!OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
            fieldSystem)) {
        return;
    }
    ChangeMapObjSprite(
        projectile->object,
        OW_WILD_HELPER_PLAYER_BALL_WHITE_TAG);
    if (!projectile->targetWhiteActive) {
        projectile->targetZ = 0;
        projectile->scratch.whitePaletteKey = 0;
        projectile->targetWhiteActive = TRUE;
    }
}

static void OverworldWildHelper_RestoreCaptureWhiteBall(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;

    if (OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
            fieldSystem)) {
        ChangeMapObjSprite(
            projectile->object,
            OW_WILD_HELPER_PLAYER_BALL_TAG);
    }
}

static void OverworldWildHelper_ApplyCaptureTargetWhite(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *targetObject;
    void *ballActor;
    void *targetActor;
    u32 whitePaletteKey;

    if (!projectile->targetWhiteActive
        || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
            fieldSystem)) {
        return;
    }
    whitePaletteKey = projectile->scratch.whitePaletteKey;
    if (whitePaletteKey == 0
        && projectile->object->gfxId
            == OW_WILD_HELPER_PLAYER_BALL_WHITE_TAG) {
        ballActor = ov01_021F72DC(projectile->object);
        if (ballActor != NULL) {
            whitePaletteKey = *(u32 *)((u8 *)ballActor
                + OW_WILD_HELPER_FIELD_ACTOR_PALETTE_KEY_OFFSET);
            projectile->scratch.whitePaletteKey = whitePaletteKey;
        }
    }
    if (!OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
            fieldSystem,
            projectile->state)) {
        return;
    }
    targetObject = projectile->state->spawns[projectile->impactSlot].object;
    targetActor = ov01_021F72DC(targetObject);
    if (targetActor == NULL) {
        return;
    }
    if (projectile->targetZ == 0) {
        projectile->targetZ = *(u32 *)((u8 *)targetActor
            + OW_WILD_HELPER_FIELD_ACTOR_PALETTE_KEY_OFFSET);
    }
    if (whitePaletteKey == 0) {
        return;
    }
    *(u32 *)((u8 *)targetActor
        + OW_WILD_HELPER_FIELD_ACTOR_PALETTE_KEY_OFFSET) =
        (*(u32 *)((u8 *)targetActor
            + OW_WILD_HELPER_FIELD_ACTOR_PALETTE_KEY_OFFSET) & 0xFFFF0000)
        | (whitePaletteKey & 0xFFFF);
}

static void OverworldWildHelper_RestoreCaptureTargetPalette(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    void *targetActor = NULL;

    if (!projectile->targetWhiteActive) {
        return;
    }
    if (OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
            fieldSystem,
            projectile->state)) {
        targetActor = ov01_021F72DC(
            projectile->state->spawns[projectile->impactSlot].object);
    }
    if (targetActor != NULL && projectile->targetZ != 0) {
        *(u32 *)((u8 *)targetActor
            + OW_WILD_HELPER_FIELD_ACTOR_PALETTE_KEY_OFFSET) =
            (u32)projectile->targetZ;
    }
    projectile->targetZ = 0;
    projectile->scratch.whitePaletteKey = 0;
    projectile->targetWhiteActive = FALSE;
    /* Release IMPACT's union arm before preparedPokemon can own it. */
    if (fieldSystem != NULL && fieldSystem->taskman == NULL) {
        OverworldWildHelper_RestoreCaptureWhiteBall(fieldSystem);
    }
}

static void OverworldWildHelper_ApplyPlayerBallPostBillboardRotation(
    void *renderState)
{
    vu32 *translation = (vu32 *)0x04000470;

    (void)renderState;
    *translation = 0;
    *translation = OW_WILD_HELPER_PLAYER_BALL_ROTATION_PIVOT_Y;
    *translation = 0;
    G3_MultMtx33_(&sOverworldWildHelperPlayerBallProjectile.rotationMatrix);
    *translation = 0;
    *translation = -OW_WILD_HELPER_PLAYER_BALL_ROTATION_PIVOT_Y;
    *translation = 0;
}

static void OverworldWildHelper_DetachPlayerBallRotation(LocalMapObject *object)
{
    void *actor = ov01_021F72DC(object);
    void (**callback)(void *);

    if (actor == NULL) {
        return;
    }
    callback = (void (**)(void *))((u8 *)actor
        + OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_OFFSET);
    if (*callback
        == OverworldWildHelper_ApplyPlayerBallPostBillboardRotation) {
        *(void **)((u8 *)actor
            + OW_WILD_HELPER_FIELD_ACTOR_ROTATION_MATRIX_OFFSET) = NULL;
        *callback = NULL;
        *((u8 *)actor
            + OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET) = 0;
        *((u8 *)actor
            + OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_TIMING_OFFSET) = 0;
    }
}

static void __attribute__((noinline))
OverworldWildHelper_SetPlayerBallMotionVectors(
    LocalMapObject *object,
    u32 height)
{
    object->faceVec[0] = 0;
    object->faceVec[1] = height;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = height;
    object->unk88[2] = 0;
    object->unk94[0] = 0;
    object->unk94[1] = 0;
    object->unk94[2] = 0;
}

static void OverworldWildHelper_DeletePlayerBallObject(LocalMapObject *object)
{
    OverworldWildHelper_DetachPlayerBallRotation(object);
    OverworldWildHelper_SetPlayerBallMotionVectors(object, 0);
    MapObject_ClearBits(
        object,
        BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13);
    DeleteMapObject(object);
}

static void OverworldWildHelper_CancelPlayerBallProjectile(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *object = projectile->object;
    OverworldWildSpawnState *state =
        projectile->state;
    int slot = projectile->impactSlot;
    BOOL objectCurrent =
        OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem);
    BOOL presentationCurrent = state != NULL
        && !state->presentationRestorePending
        && OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state);
    BOOL hadUnsafeObject = object != NULL;
    BOOL unsafeCancellation = hadUnsafeObject
        && (fieldSystem == NULL
            || fieldSystem->taskman != NULL
            || !presentationCurrent
            || (object != NULL && !objectCurrent));

    if (unsafeCancellation) {
        sOverworldWildHelperPlayerBallInputArmed = FALSE;
        sOverworldWildHelperPlayerBallStaleCheckDone = FALSE;
    }

    OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
    if (state != NULL
        && state->followerReleaseState != OW_WILD_FOLLOWER_RELEASE_NONE) {
        if (state->followerReleaseState == OW_WILD_FOLLOWER_RELEASE_SPAWNED
            && state->spawns[OW_WILD_FOLLOWER_SLOT].active
            && state->spawns[OW_WILD_FOLLOWER_SLOT].object != NULL
            && OverworldWildHelper_IsExactObject(
                fieldSystem,
                state,
                OW_WILD_FOLLOWER_SLOT)) {
            LocalMapObject *follower =
                state->spawns[OW_WILD_FOLLOWER_SLOT].object;

            follower->faceVec[1] = 0;
            follower->unk88[1] = 0;
            MapObject_ClearBits(
                follower,
                BIT_VANISH
                    | BIT_JUMP_START
                    | BIT_MOVE_START
                    | MAPOBJECTFLAG_UNK13);
            state->movementCooldowns[OW_WILD_FOLLOWER_SLOT] = 1;
        }
        state->followerReleaseState =
            state->followerReleaseState == OW_WILD_FOLLOWER_RELEASE_SPAWNED
                && state->spawns[OW_WILD_FOLLOWER_SLOT].active
            ? OW_WILD_FOLLOWER_RELEASE_NONE
            : OW_WILD_FOLLOWER_RELEASE_REQUESTED
                | (state->followerReleaseState
                    & OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG);
    }
    if (state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS) {
        state->captureTargetMask &= (u16)~(1u << slot);
    }

    if (fieldSystem != NULL && fieldSystem->taskman != NULL) {
        OverworldWildHelper_RestorePlayerBallCaptureTarget(fieldSystem);
        if (objectCurrent) {
            OverworldWildHelper_DetachPlayerBallRotation(object);
        }
        if (hadUnsafeObject) {
            sOverworldWildHelperPlayerBallStaleCheckDone = FALSE;
        }
        OverworldWildHelper_ResetPlayerBallProjectile();
        return;
    }
    OverworldWildHelper_RestorePlayerBallCaptureTarget(fieldSystem);
    if (objectCurrent) {
        OverworldWildHelper_DeletePlayerBallObject(object);
    } else if (hadUnsafeObject) {
        sOverworldWildHelperPlayerBallStaleCheckDone = FALSE;
    }
    OverworldWildHelper_ResetPlayerBallProjectile();
}

static BOOL OverworldWildHelper_PlayerBallObjectIdAvailable(FieldSystem *fieldSystem)
{
    MapObjectMan *manager;
    int i;

    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->taskman != NULL
        || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager->objects == NULL) {
        return FALSE;
    }
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && object->id == OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID) {
            OverworldWildHelper_DeletePlayerBallObject(object);
            return FALSE;
        }
    }
    sOverworldWildHelperPlayerBallStaleCheckDone = TRUE;
    return TRUE;
}

static s32 OverworldWildHelper_LerpPlayerBallValue(
    s32 start,
    s32 target,
    u8 elapsed,
    u8 total)
{
    if (elapsed >= total) {
        return target;
    }
    return start + (((target - start) * elapsed) / total);
}

static void OverworldWildHelper_TickPlayerBallChargeSound(void)
{
    u8 interval = OW_WILD_HELPER_PLAYER_BALL_CHARGE_SLOW_INTERVAL
        - (sOverworldWildHelperPlayerBallChargeFrames
            * (OW_WILD_HELPER_PLAYER_BALL_CHARGE_SLOW_INTERVAL
                - OW_WILD_HELPER_PLAYER_BALL_CHARGE_FAST_INTERVAL))
            / OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES;

    if (sOverworldWildHelperPlayerBallChargeFrames
        >= OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES) {
        if (sOverworldWildHelperPlayerBallChargeSoundTimer
            != OW_WILD_HELPER_PLAYER_BALL_CHARGE_SOUND_COMPLETE) {
            PlaySE(OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE);
            sOverworldWildHelperPlayerBallChargeSoundTimer =
                OW_WILD_HELPER_PLAYER_BALL_CHARGE_SOUND_COMPLETE;
        }
        return;
    }
    if (sOverworldWildHelperPlayerBallChargeSoundTimer > interval) {
        sOverworldWildHelperPlayerBallChargeSoundTimer = interval;
    }
    if (sOverworldWildHelperPlayerBallChargeSoundTimer != 0) {
        sOverworldWildHelperPlayerBallChargeSoundTimer--;
    }
    if (sOverworldWildHelperPlayerBallChargeSoundTimer == 0) {
        PlaySE(OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE);
        sOverworldWildHelperPlayerBallChargeSoundTimer = interval;
    }
}

static int OverworldWildHelper_FindPlayerBallHit(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    s32 oldX,
    s32 oldZ,
    s32 newX,
    s32 newZ)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    s32 startX;
    s32 startZ;
    s32 endX;
    s32 endZ;
    s32 stepX;
    s32 stepZ;
    s32 lengthSquared;
    s32 radius = OW_WILD_HELPER_PLAYER_BALL_HIT_RADIUS_FX32
        >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    s32 bestEntry = 0x7FFFFFFF;
    int bestSlot = -1;
    int i;

    if ((state->followerReleaseState & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
            == OW_WILD_FOLLOWER_RELEASE_BOUNCING
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || state->mapGeneration != projectile->mapGeneration) {
        return -1;
    }
    startX = oldX >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    startZ = oldZ >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    endX = newX >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    endZ = newZ >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
    stepX = endX - startX;
    stepZ = endZ - startZ;
    lengthSquared = stepX * stepX + stepZ * stepZ;
    if (lengthSquared == 0) {
        return -1;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *targetObject;
        s32 targetX;
        s32 targetZ;
        s32 relativeX;
        s32 relativeZ;
        s32 dot;
        s32 distanceSquared;
        s32 entry;

        if (i == OW_WILD_FOLLOWER_SLOT
            || !OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            continue;
        }
        targetObject = state->spawns[i].object;
        if (state->movementTeleportHidden[i]
            || (targetObject->flags & BIT_VANISH) != 0) {
            continue;
        }
        targetX = (s32)targetObject->posVec[0]
            >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
        targetZ = (s32)targetObject->posVec[2]
            >> OW_WILD_HELPER_PLAYER_BALL_COLLISION_SHIFT;
        if (targetX < OverworldWildHelper_Min(startX, endX) - radius
            || targetX > OverworldWildHelper_Max(startX, endX) + radius
            || targetZ < OverworldWildHelper_Min(startZ, endZ) - radius
            || targetZ > OverworldWildHelper_Max(startZ, endZ) + radius) {
            continue;
        }
        relativeX = targetX - startX;
        relativeZ = targetZ - startZ;
        dot = relativeX * stepX + relativeZ * stepZ;
        if (dot <= 0) {
            distanceSquared = relativeX * relativeX + relativeZ * relativeZ;
            entry = 0;
        } else if (dot >= lengthSquared) {
            relativeX = targetX - endX;
            relativeZ = targetZ - endZ;
            distanceSquared = relativeX * relativeX + relativeZ * relativeZ;
            entry = lengthSquared;
        } else {
            s32 cross = relativeX * stepZ - relativeZ * stepX;

            if (cross * cross > radius * radius * lengthSquared) {
                continue;
            }
            distanceSquared = 0;
            entry = dot;
        }
        if (distanceSquared > radius * radius) {
            continue;
        }
        if (entry < bestEntry) {
            bestEntry = entry;
            bestSlot = i;
        }
    }
    return bestSlot;
}

static BOOL OverworldWildHelper_TryApplyPlayerBallAimAssist(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *playerObject,
    int directionX,
    int directionY,
    s32 distanceFx32)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    s32 playerX = (s32)playerObject->posVec[0];
    s32 playerZ = (s32)playerObject->posVec[2];
    s32 bestCross = 0x7FFFFFFF;
    s32 bestForward = 0x7FFFFFFF;
    int bestSlot = -1;
    int i;

    if (!OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || state->mapGeneration != projectile->mapGeneration) {
        return FALSE;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *targetObject;
        s32 deltaX;
        s32 deltaZ;
        s32 forward;
        s32 cross;

        if (i == OW_WILD_FOLLOWER_SLOT
            || !OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            continue;
        }
        targetObject = state->spawns[i].object;
        if (state->movementTeleportHidden[i]
            || (targetObject->flags & BIT_VANISH) != 0) {
            continue;
        }
        deltaX = (s32)targetObject->posVec[0] - playerX;
        deltaZ = (s32)targetObject->posVec[2] - playerZ;
        forward = deltaX * directionX + deltaZ * directionY;
        cross = OverworldWildHelper_Abs(
            deltaX * directionY - deltaZ * directionX);
        if (forward < OW_WILD_HELPER_PLAYER_BALL_AIM_MIN_FORWARD_FX32
            || forward > distanceFx32
            || cross > OW_WILD_HELPER_PLAYER_BALL_AIM_HALF_WIDTH_FX32) {
            continue;
        }
        if (cross < bestCross
            || (cross == bestCross && forward < bestForward)) {
            bestCross = cross;
            bestForward = forward;
            bestSlot = i;
        }
    }
    if (bestSlot < 0) {
        return FALSE;
    }
    {
        LocalMapObject *targetObject = state->spawns[bestSlot].object;
        s32 scaledX = ((s32)targetObject->posVec[0] - playerX) >> 8;
        s32 scaledZ = ((s32)targetObject->posVec[2] - playerZ) >> 8;
        u32 directionLength = sqrt(
            (u32)(scaledX * scaledX + scaledZ * scaledZ));

        if (directionLength == 0) {
            return FALSE;
        }
        projectile->targetX = playerX
            + scaledX * distanceFx32 / (s32)directionLength;
        projectile->targetZ = playerZ
            + scaledZ * distanceFx32 / (s32)directionLength;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_StartPlayerBallImpact(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildHelperPrepareCaptureTargetFunc prepareCaptureTarget,
    OverworldWildHelperCalculatePlayerBallShakesFunc calculateShakes)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *ballObject;
    LocalMapObject *targetObject;
    u16 encounterGeneration;
    u8 shakeChecks;

    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || state == NULL
        || calculateShakes == NULL
        || state->mapGeneration != projectile->mapGeneration
        || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        return FALSE;
    }
    encounterGeneration = state->spawns[slot].encounterGeneration;
    if (prepareCaptureTarget != NULL) {
        prepareCaptureTarget(state, slot);
    }
    if (!OverworldWildHelper_IsExactObject(fieldSystem, state, slot)
        || state->spawns[slot].encounterGeneration != encounterGeneration) {
        return FALSE;
    }
    shakeChecks = calculateShakes(
        state,
        slot,
        encounterGeneration);
    if (shakeChecks == 4
        && !OverworldWildHelper_ReserveCaptureHeap()) {
        /* Fail safely as a normal three-shake breakout under heap pressure. */
        shakeChecks = 3;
    }
    ballObject = projectile->object;
    targetObject = state->spawns[slot].object;
    ballObject->posVec[0] = targetObject->posVec[0];
    ballObject->posVec[1] = targetObject->posVec[1];
    ballObject->posVec[2] = targetObject->posVec[2];
    ballObject->hCurr = targetObject->hCurr;
    ballObject->faceVec[1] = targetObject->faceVec[1]
        + OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32;
    ballObject->unk88[1] = ballObject->faceVec[1];
    projectile->startHeight = (s32)ballObject->faceVec[1];
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT;
    projectile->elapsedFrames = 0;
    projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES;
    projectile->impactSlot = (s8)slot;
    projectile->impactEncounterGeneration = encounterGeneration;
    projectile->targetY = state->spawns[slot].mapId;
    projectile->shakeChecks = shakeChecks;
    projectile->shakeIndex = 0;
    projectile->targetHadPassThrough =
        (targetObject->flags & MAPOBJECTFLAG_UNK18) != 0;
    state->captureTargetMask |= (u16)(1u << slot);
    if (state->movementCooldowns[slot]
        < OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES) {
        state->movementCooldowns[slot] =
            OW_WILD_HELPER_PLAYER_BALL_IMPACT_FRAMES;
    }
    projectile->scratch.whitePaletteKey = 0;
    OverworldWildHelper_PrepareCaptureWhiteBall(fieldSystem);
    PlaySE(OW_WILD_HELPER_PLAYER_BALL_IMPACT_SE);
    return TRUE;
}

static BOOL OverworldWildHelper_ApplyPlayerBallChargeRender(
    FieldSystem *fieldSystem)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *playerObject;
    LocalMapObject *object = projectile->object;
    u8 pulseFrame;
    s32 pulseStep;
    s32 rise;
    s32 pulse;
    s32 renderY;

    if (object == NULL
        || fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL) {
        return FALSE;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing > 3) {
        return FALSE;
    }
    rise = (sOverworldWildHelperPlayerBallChargeFrames
        * OW_WILD_HELPER_PLAYER_BALL_CHARGE_RISE_FX32)
        / OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES;
    pulseFrame = projectile->elapsedFrames & 15;
    if (pulseFrame > 8) {
        pulseFrame = 16 - pulseFrame;
    }
    pulseStep = OW_WILD_HELPER_PLAYER_BALL_CHARGE_PULSE_STEP_FX32;
    if (sOverworldWildHelperPlayerBallChargeFrames
        == OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES) {
        pulseStep *= 2;
    }
    pulse = pulseFrame * pulseStep;
    renderY = (s32)playerObject->posVec[1];
    MapObject_SetCurrentX(object, MapObject_GetCurrentX(playerObject));
    MapObject_SetCurrentY(object, MapObject_GetCurrentY(playerObject));
    object->xInit = playerObject->xInit;
    object->yInit = playerObject->yInit;
    object->xPrev = playerObject->xPrev;
    object->yPrev = playerObject->yPrev;
    object->hPrev = playerObject->hPrev;
    object->posVec[0] = (u32)((s32)playerObject->posVec[0]
        + OverworldWildHelper_DirectionDeltaX(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32
        - OverworldWildHelper_DirectionDeltaY(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_RIGHT_HAND_OFFSET_FX32);
    object->posVec[1] = (u32)renderY;
    object->posVec[2] = (u32)((s32)playerObject->posVec[2]
        + OverworldWildHelper_DirectionDeltaY(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32
        + OverworldWildHelper_DirectionDeltaX(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_RIGHT_HAND_OFFSET_FX32);
    object->hCurr = (int)(renderY >> 15);
    object->curFacing = playerObject->curFacing;
    object->nextFacing = playerObject->nextFacing;
    projectile->startHeight = (s32)playerObject->faceVec[1]
        + OW_WILD_HELPER_PLAYER_BALL_HAND_HEIGHT_FX32
        + rise
        + pulse;
    OverworldWildHelper_SetPlayerBallMotionVectors(
        object,
        (u32)projectile->startHeight);
    MapObject_ClearBits(object, BIT_VANISH);
    return TRUE;
}

static void OverworldWildHelper_ApplyPlayerBallRotation(s16 rotation);

static void OverworldWildHelper_RefreshFollowerBallReturnTarget(
    FieldSystem *fieldSystem)
{
    LocalMapObject *playerObject;

    if (fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL) {
        return;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing < 0 || playerObject->curFacing > 3) {
        return;
    }
    sOverworldWildHelperPlayerBallProjectile.startX =
        (s32)playerObject->posVec[0]
        + OverworldWildHelper_DirectionDeltaX(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32
        - OverworldWildHelper_DirectionDeltaY(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_RIGHT_HAND_OFFSET_FX32;
    sOverworldWildHelperPlayerBallProjectile.startY =
        (s32)playerObject->posVec[1];
    sOverworldWildHelperPlayerBallProjectile.startZ =
        (s32)playerObject->posVec[2]
        + OverworldWildHelper_DirectionDeltaY(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_FORWARD_OFFSET_FX32
        + OverworldWildHelper_DirectionDeltaX(playerObject->curFacing)
            * OW_WILD_HELPER_PLAYER_BALL_RIGHT_HAND_OFFSET_FX32;
}

static void OverworldWildHelper_DispatchFollowerRelease(
    FieldSystem *fieldSystem,
    u8 action)
{
    if (action == 0) {
        OverworldWildHelper_PrepareCaptureWhiteBall(fieldSystem);
        OverworldWildHelper_ApplyCaptureTargetWhite(fieldSystem);
    } else if (action == 1) {
        OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
    } else if (action == 3) {
        OverworldWildHelper_ApplyCaptureTargetWhite(fieldSystem);
    } else {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
    }
}

static LocalMapObject *OverworldWildHelper_CreatePlayerBallObject(
    FieldSystem *fieldSystem)
{
    LocalMapObject *playerObject = fieldSystem->playerAvatar->mapObject;
    LocalMapObject *object;

    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    object = CreateSpecialFieldObjectWithParams(
        fieldSystem->mapObjectMan,
        MapObject_GetCurrentX(playerObject),
        MapObject_GetCurrentY(playerObject),
        playerObject->curFacing,
        OW_WILD_HELPER_PLAYER_BALL_TAG,
        OW_WILD_MOVE_STOCK_IDLE,
        fieldSystem->location->mapId,
        0,
        0,
        0);
    if (object == NULL) {
        return NULL;
    }
    MapObject_SetID(object, OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID);
    MapObject_SetBits(object, MAPOBJECTFLAG_UNK18 | MAPOBJECTFLAG_UNK20);
    return object;
}

static BOOL OverworldWildHelper_TryStartPlayerBallCharge(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    MapObjectMan *manager;
    LocalMapObject *playerObject;
    LocalMapObject *object;

    if (projectile->phase != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE
        || fieldSystem == NULL
        || fieldSystem->taskman != NULL
        || state == NULL
        || state->pendingSlot >= 0
        || state->movementQueuedBattleSlot >= 0
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || !sOverworldWildHelperPlayerBallStaleCheckDone) {
        return FALSE;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing > 3) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    object = OverworldWildHelper_CreatePlayerBallObject(fieldSystem);
    if (object == NULL) {
        return FALSE;
    }
    projectile->fieldSystem = fieldSystem;
    projectile->state = state;
    projectile->manager = manager;
    projectile->objects = manager->objects;
    projectile->object = object;
    projectile->mapId = fieldSystem->location->mapId;
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING;
    projectile->objectId = OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
    projectile->elapsedFrames = 0;
    projectile->totalFrames = 0;
    if (!OverworldWildHelper_ApplyPlayerBallChargeRender(fieldSystem)) {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
    OverworldWildHelper_TickPlayerBallChargeSound();
    return TRUE;
}

static BOOL OverworldWildHelper_TryLaunchPlayerBallProjectile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    s32 distanceFx32)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *playerObject;
    LocalMapObject *object;
    int directionX;
    int directionY;
    int totalFrames;

    if (projectile->phase != OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING
        || fieldSystem == NULL
        || fieldSystem->taskman != NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)) {
        return FALSE;
    }
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject->curFacing > 3) {
        return FALSE;
    }
    object = projectile->object;
    projectile->mapGeneration = state->mapGeneration;
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING;
    projectile->elapsedFrames = 0;
    projectile->targetHadPassThrough = playerObject->curFacing;
    projectile->startX = (s32)object->posVec[0];
    projectile->startY = (s32)object->posVec[1];
    projectile->startZ = (s32)object->posVec[2];
    directionX = OverworldWildHelper_DirectionDeltaX(playerObject->curFacing);
    directionY = OverworldWildHelper_DirectionDeltaY(playerObject->curFacing);
    projectile->targetX = (s32)playerObject->posVec[0]
        + directionX * distanceFx32;
    projectile->targetY = (s32)playerObject->posVec[1];
    projectile->targetZ = (s32)playerObject->posVec[2]
        + directionY * distanceFx32;
    (void)OverworldWildHelper_TryApplyPlayerBallAimAssist(
        fieldSystem,
        state,
        playerObject,
        directionX,
        directionY,
        distanceFx32);
    totalFrames = OW_WILD_HELPER_PLAYER_BALL_LAUNCH_FRAMES
        + ((distanceFx32
                * OW_WILD_HELPER_PLAYER_BALL_FRAMES_PER_TILE
                + 0xFFFF)
            >> 16);
    if (totalFrames > OW_WILD_HELPER_PLAYER_BALL_MAX_FRAMES) {
        totalFrames = OW_WILD_HELPER_PLAYER_BALL_MAX_FRAMES;
    }
    totalFrames += OW_WILD_HELPER_PLAYER_BALL_HANG_FRAMES
        + OW_WILD_HELPER_PLAYER_BALL_FALL_FRAMES;
    projectile->totalFrames = (u8)totalFrames;
    OverworldWildSpawns_RenderPlayerBallProjectile(
        &sOverworldWildHelperPlayerBallProjectile,
        OverworldWildHelper_ApplyPlayerBallRotation);
    StopSE(OW_WILD_HELPER_PLAYER_BALL_CHARGE_SE);
    PlaySE(OW_WILD_HELPER_PLAYER_BALL_THROW_SE);
    return TRUE;
}

static void OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
    LocalMapObject *targetObject,
    s32 offsetX,
    s32 height)
{
    LocalMapObject *ballObject =
        sOverworldWildHelperPlayerBallProjectile.object;

    ballObject->posVec[0] = (u32)((s32)targetObject->posVec[0] + offsetX);
    ballObject->posVec[1] = targetObject->posVec[1];
    ballObject->posVec[2] = targetObject->posVec[2];
    ballObject->hCurr = targetObject->hCurr;
    ballObject->faceVec[1] = (u32)height;
    ballObject->unk88[1] = ballObject->faceVec[1];
    MapObject_ClearBits(ballObject, BIT_VANISH);
}

static void OverworldWildHelper_ApplyPlayerBallRotation(s16 rotation)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    void *actor = ov01_021F72DC(projectile->object);
    void (**callback)(void *);
    u16 angle;
    u32 tableIndex;

    projectile->rotation = rotation;
    if (actor == NULL) {
        return;
    }

    angle = (u16)rotation;
    tableIndex = ((u32)angle >> 4) << 1;
    MTX_RotZ33_(
        &projectile->rotationMatrix,
        FX_SinCosTable_[tableIndex],
        FX_SinCosTable_[tableIndex + 1]);
    *(void **)((u8 *)actor
        + OW_WILD_HELPER_FIELD_ACTOR_ROTATION_MATRIX_OFFSET) = NULL;
    callback = (void (**)(void *))((u8 *)actor
        + OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_OFFSET);
    *((u8 *)actor
        + OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET) =
        OW_WILD_HELPER_FIELD_ACTOR_BILLBOARD_COMMAND;
    *((u8 *)actor
        + OW_WILD_HELPER_FIELD_ACTOR_RENDER_CALLBACK_TIMING_OFFSET) =
        OW_WILD_HELPER_FIELD_ACTOR_CALLBACK_AFTER_COMMAND;
    *callback = OverworldWildHelper_ApplyPlayerBallPostBillboardRotation;
}

static void OverworldWildHelper_BeginPlayerBallBreakout(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *targetObject =
        state->spawns[projectile->impactSlot].object;

    OverworldWildHelper_ReleaseCaptureHeap();
    /* Resolve IMPACT's union ownership before treating scratch as a pointer. */
    OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
    OverworldWildHelper_DiscardPreparedCapturedPokemon();
    if (projectile->object->gfxId != OW_WILD_HELPER_PLAYER_BALL_TAG) {
        ChangeMapObjSprite(
            projectile->object,
            OW_WILD_HELPER_PLAYER_BALL_TAG);
    }
    projectile->startX = (s32)projectile->object->posVec[0]
        - (s32)targetObject->posVec[0];
    projectile->startHeight = (s32)projectile->object->faceVec[1];
    OverworldWildHelper_RestorePlayerBallCaptureTarget(fieldSystem);
    projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT;
    projectile->elapsedFrames = 0;
    projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_RESULT_FRAMES;
    PlaySE(OW_WILD_HELPER_PLAYER_BALL_BREAKOUT_SE);
    PlayCry(
        state->spawns[projectile->impactSlot].species,
        state->spawns[projectile->impactSlot].form);
}

static BOOL OverworldWildHelper_TickPlayerBallCapture(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperResetSlotFunc resetSlot,
    OverworldWildHelperFindCapturedPokemonDestinationFunc findDestination)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *targetObject;
    int endOffsetUnits;
    int startOffsetUnits;
    int endRotation;
    int startRotation;
    int rotationStartFrame;
    int rotationEndFrame;
    int rotationProgressMax;
    int rotationProgress;
    int rotationStep;
    u16 curveProgress;
    s32 height;
    s32 offset;
    u8 frame;
    u8 visibleShakes;
    LocalMapObject *verifiedTarget;

    sOverworldWildHelperPlayerBallInputArmed = TRUE;
    sOverworldWildHelperPlayerBallChargeFrames = 0;
    if (!OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || state->presentationRestorePending
        || !OverworldWildHelper_IsPlayerBallCaptureTargetCurrent(
            fieldSystem,
            state)) {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    targetObject = state->spawns[projectile->impactSlot].object;

    switch (projectile->phase) {
    case OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT:
        frame = projectile->elapsedFrames;
        if (frame >= projectile->totalFrames) {
            OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
            OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
            OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
                targetObject,
                OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                    * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32,
                0);
            projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_LANDED;
            projectile->elapsedFrames = 0;
            projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_LAND_FRAMES;
            return TRUE;
        }
        if (frame <= OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME) {
            curveProgress = sOverworldWildHelperImpactProgress[frame];
            height = projectile->startHeight
                + (sOverworldWildHelperCaughtHeightProgress[
                        OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME]
                            * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
                            / OW_WILD_HELPER_PLAYER_BALL_SHAKE_HEIGHT_SCALE
                    - projectile->startHeight)
                    * curveProgress
                    / OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX;
            offset = OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                * curveProgress
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
                / OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX;
        } else if (frame
            < OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME) {
            height = sOverworldWildHelperCaughtHeightProgress[
                    OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME]
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
                / OW_WILD_HELPER_PLAYER_BALL_SHAKE_HEIGHT_SCALE;
            offset = OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32;
        } else {
            height = sOverworldWildHelperCaughtHeightProgress[
                    OW_WILD_HELPER_PLAYER_BALL_IMPACT_SOURCE_APEX_FRAME
                    + 1
                    + frame
                    - OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME]
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
                / OW_WILD_HELPER_PLAYER_BALL_SHAKE_HEIGHT_SCALE;
            offset = OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32;
        }
        if (frame > 0
            && frame <= OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME) {
            rotationStep = 12
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_35_DEGREES
                * (sOverworldWildHelperImpactRotationProgress[frame]
                    - sOverworldWildHelperImpactRotationProgress[frame - 1])
                / OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX;
            projectile->rotation = (s16)((u16)projectile->rotation
                + rotationStep);
        }
        if (frame >= OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_START_FRAME
            && frame <= OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_END_FRAME) {
            int pullFrame = frame
                - OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_START_FRAME;
            int pullFrames = OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_END_FRAME
                - OW_WILD_HELPER_PLAYER_BALL_TARGET_PULL_START_FRAME;
            int pullProgress = pullFrame * pullFrame * pullFrame * pullFrame
                * OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX
                / (pullFrames * pullFrames * pullFrames * pullFrames);

            targetObject->faceVec[0] = (u32)(offset * pullProgress
                / OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX);
            targetObject->faceVec[1] = (u32)(height * pullProgress
                / OW_WILD_HELPER_PLAYER_BALL_IMPACT_PROGRESS_MAX
                * 13 / 10);
            targetObject->unk88[0] = targetObject->faceVec[0];
            targetObject->unk88[1] = targetObject->faceVec[1];
        }
        if (frame < OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME) {
            OverworldWildHelper_ApplyCaptureTargetWhite(fieldSystem);
        }
        if (frame == OW_WILD_HELPER_PLAYER_BALL_IMPACT_FLASH_FRAMES) {
            OverworldWildHelper_RestoreCaptureWhiteBall(fieldSystem);
        }
        if (frame == OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME) {
            OverworldWildHelper_PrepareCaptureWhiteBall(fieldSystem);
            PlaySE(OW_WILD_HELPER_PLAYER_BALL_DRAW_IN_SE);
        }
        if (frame == OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME) {
            OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        } else if (frame
            == OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME
                + OW_WILD_HELPER_PLAYER_BALL_SECOND_FLASH_EXTRA_FRAMES) {
            OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
        }
        OverworldWildHelper_ApplyPlayerBallRotation(projectile->rotation);
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            offset,
            height);
        projectile->elapsedFrames++;
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_LANDED:
        OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32,
            0);
        if (++projectile->elapsedFrames < projectile->totalFrames) {
            return TRUE;
        }
        if (projectile->shakeChecks == 0) {
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING;
        projectile->elapsedFrames = 0;
        projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES
            + OW_WILD_HELPER_PLAYER_BALL_END_ARC_PAUSE_FRAMES;
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING:
        OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        frame = projectile->elapsedFrames;
        if (projectile->shakeIndex == 3) {
            if (!OverworldWildHelper_PrepareCapturedPokemonFrame(
                    fieldSystem,
                    &state->spawns[projectile->impactSlot],
                    frame)) {
                OverworldWildHelper_BeginPlayerBallBreakout(
                    fieldSystem,
                    state);
                return TRUE;
            }
            if (frame == 0) {
                ChangeMapObjSprite(
                    projectile->object,
                    OW_WILD_HELPER_PLAYER_BALL_WHITE_TAG);
            } else if (frame
                == OW_WILD_HELPER_PLAYER_BALL_CAUGHT_WHITE_FRAMES) {
                ChangeMapObjSprite(
                    projectile->object,
                    OW_WILD_HELPER_PLAYER_BALL_TAG);
            }
        }
        if (projectile->shakeIndex != 3
            && frame >= OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES) {
            frame = OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES - 1;
        } else if (projectile->shakeIndex == 3
            && frame >= OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES) {
            frame = OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES - 1;
        }
        if (projectile->shakeIndex == 3) {
            startOffsetUnits =
                -OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS;
            endOffsetUnits = 0;
        } else {
            endOffsetUnits = (projectile->shakeIndex & 1) != 0
                ? OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                : -OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS;
            startOffsetUnits = projectile->shakeIndex == 0
                ? OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_SIDE_UNITS
                : -endOffsetUnits;
        }
        curveProgress = projectile->shakeIndex == 3
            ? sOverworldWildHelperCaughtCurveProgress[frame]
            : sOverworldWildHelperShakeCurveProgress[frame];
        offset = (startOffsetUnits
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_CURVE_MAX
            + (endOffsetUnits - startOffsetUnits)
                * curveProgress)
            * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
            / OW_WILD_HELPER_PLAYER_BALL_SHAKE_CURVE_MAX;
        if (projectile->shakeIndex == 3) {
            height = sOverworldWildHelperCaughtHeightProgress[frame]
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
                / OW_WILD_HELPER_PLAYER_BALL_SHAKE_HEIGHT_SCALE;
        } else {
            height = (projectile->shakeIndex
                    * OW_WILD_HELPER_PLAYER_BALL_SHAKE_ARC_HEIGHT_UNITS
                + sOverworldWildHelperShakeHeightProgress[frame])
                * OW_WILD_HELPER_PLAYER_BALL_SHAKE_KEYFRAME_STEP_FX32
                / OW_WILD_HELPER_PLAYER_BALL_SHAKE_HEIGHT_SCALE;
        }
        endRotation = (projectile->shakeIndex & 1) != 0
            ? -OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_35_DEGREES
            : OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_35_DEGREES;
        startRotation = projectile->shakeIndex == 0
            ? 0
            : -endRotation;
        rotationStartFrame = projectile->shakeIndex == 3
            ? OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ROTATION_START_FRAME
            : OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_START_FRAME;
        rotationEndFrame = projectile->shakeIndex == 3
            ? OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ROTATION_END_FRAME
            : OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_END_FRAME;
        rotationProgressMax = projectile->shakeIndex == 3
            ? OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ROTATION_PROGRESS_MAX
            : OW_WILD_HELPER_PLAYER_BALL_SHAKE_ROTATION_PROGRESS_MAX;
        if (frame <= rotationStartFrame) {
            rotationProgress = 0;
        } else if (frame >= rotationEndFrame) {
            rotationProgress = rotationProgressMax;
        } else {
            rotationProgress =
                (frame - rotationStartFrame)
                * (frame - rotationStartFrame + 1)
                / 2;
        }
        OverworldWildHelper_ApplyPlayerBallRotation(
            (s16)(startRotation
                + (endRotation - startRotation) * rotationProgress
                    / rotationProgressMax));
        if (frame == OW_WILD_HELPER_PLAYER_BALL_SHAKE_LAUNCH_FRAME) {
            if (projectile->shakeChecks == 4
                && projectile->shakeIndex == 3) {
                PlaySE(OW_WILD_HELPER_PLAYER_BALL_CAUGHT_SE);
            } else {
                PlaySE(OW_WILD_HELPER_PLAYER_BALL_SHAKE_SE);
            }
        }
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            offset,
            height);
        if (++projectile->elapsedFrames < projectile->totalFrames) {
            return TRUE;
        }
        projectile->shakeIndex++;
        visibleShakes = projectile->shakeChecks == 4
            ? 3
            : projectile->shakeChecks;
        if (projectile->shakeIndex < visibleShakes) {
            projectile->elapsedFrames = 0;
            projectile->totalFrames = projectile->shakeIndex == 2
                ? OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES
                    + OW_WILD_HELPER_PLAYER_BALL_THIRD_ARC_PAUSE_FRAMES
                : OW_WILD_HELPER_PLAYER_BALL_SHAKE_FRAMES
                    + OW_WILD_HELPER_PLAYER_BALL_END_ARC_PAUSE_FRAMES;
            return TRUE;
        }
        if (projectile->shakeChecks == 4
            && projectile->shakeIndex == 3) {
            projectile->startY = findDestination != NULL
                ? findDestination(fieldSystem)
                : OW_WILD_HELPER_CAPTURE_DESTINATION_NONE;
            if (projectile->startY
                != OW_WILD_HELPER_CAPTURE_DESTINATION_NONE) {
                projectile->elapsedFrames = 0;
                projectile->totalFrames =
                    OW_WILD_HELPER_PLAYER_BALL_CAUGHT_ARC_FRAMES
                    + OW_WILD_HELPER_PLAYER_BALL_END_ARC_PAUSE_FRAMES;
                return TRUE;
            }
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        if (projectile->shakeChecks < 4) {
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        projectile->phase = OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT;
        projectile->elapsedFrames = 0;
        projectile->totalFrames = OW_WILD_HELPER_PLAYER_BALL_RESULT_FRAMES;
        projectile->startX = 0;
        projectile->startHeight = 0;
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            0,
            0);
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT:
        frame = projectile->elapsedFrames;
        if (frame >= projectile->totalFrames) {
            OverworldWildHelper_DeletePlayerBallObject(projectile->object);
            projectile->object = NULL;
            OverworldWildHelper_ResetPlayerBallProjectile();
            return FALSE;
        }
        offset = OverworldWildHelper_LerpPlayerBallValue(
            projectile->startX,
            0,
            frame,
            projectile->totalFrames);
        height = OverworldWildHelper_LerpPlayerBallValue(
            projectile->startHeight,
            0,
            frame,
            projectile->totalFrames);
        if (frame > projectile->totalFrames / 2) {
            frame = projectile->totalFrames - frame;
        }
        height += frame * OW_WILD_HELPER_PLAYER_BALL_IMPACT_REBOUND_STEP_FX32;
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            offset,
            height);
        projectile->elapsedFrames++;
        return TRUE;

    case OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT:
        OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        OverworldWildHelper_RenderPlayerBallOnCaptureTarget(
            targetObject,
            projectile->startX,
            projectile->startHeight);
        if (++projectile->elapsedFrames < projectile->totalFrames) {
            return TRUE;
        }
        verifiedTarget = NULL;
        if (telemetry == NULL
            || resetSlot == NULL
            || OverworldWildHelper_AuthorizeDespawn(
                    fieldSystem,
                    state,
                    presentation,
                    projectile->impactSlot,
                    projectile->impactEncounterGeneration,
                    OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
                    &verifiedTarget)
                != OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT
            || verifiedTarget != targetObject
            || !OverworldWildHelper_FinalizePreparedCapturedPokemon(
                fieldSystem)) {
            OverworldWildHelper_BeginPlayerBallBreakout(fieldSystem, state);
            return TRUE;
        }
        OverworldWildHelper_RecordDespawnEvent(
            fieldSystem,
            state,
            presentation,
            telemetry,
            projectile->impactSlot,
            OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
            OW_WILD_DESPAWN_ACTION_DELETE_OBJECT,
            0);
        resetSlot(state, projectile->impactSlot, TRUE);
        DeleteMapObject(verifiedTarget);
        OverworldWildHelper_DeletePlayerBallObject(projectile->object);
        projectile->object = NULL;
        OverworldWildHelper_ResetPlayerBallProjectile();
        return FALSE;

    default:
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
}

static BOOL OverworldWildHelper_TickPlayerBallProjectile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperResetSlotFunc resetSlot,
    OverworldWildHelperPrepareCaptureTargetFunc prepareCaptureTarget,
    OverworldWildHelperCalculatePlayerBallShakesFunc calculateShakes,
    OverworldWildHelperFindCapturedPokemonDestinationFunc findDestination)
{
    u32 pad = PAD_Read();
    BOOL rDown = (pad & PAD_BUTTON_R) != 0;
    BOOL rPressed = rDown && !sOverworldWildHelperPlayerBallRWasDown;
    BOOL rReleased = !rDown && sOverworldWildHelperPlayerBallRWasDown;
    s32 distanceFx32;
    s32 oldX;
    s32 oldZ;
    int hitSlot;

    sOverworldWildHelperPlayerBallRWasDown = rDown;

    if (fieldSystem == NULL) {
        sOverworldWildHelperPlayerBallInputArmed = FALSE;
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if ((OVERWORLD_FOLLOWER_SELECTOR_STATE
            & (OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG
                | OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG)) != 0
        && sOverworldWildHelperPlayerBallProjectile.phase
            < OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING) {
        /*
         * The selector reads physical L/R so it remains usable with L=A.
         * Once its pending hold begins, those shoulders must not also arm or
         * charge another custom Player Ball. An already launched ball still
         * owns its presentation and capture state, so keep ticking it while
         * the selector is open instead of cancelling the animation.
         */
        if (sOverworldWildHelperPlayerBallProjectile.phase
                != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE) {
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        } else {
            sOverworldWildHelperPlayerBallInputArmed = FALSE;
        }
        return FALSE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
            != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE
        && sOverworldWildHelperPlayerBallProjectile.objectId == 0) {
        if (fieldSystem->taskman != NULL
            || fieldSystem->location == NULL
            || sOverworldWildHelperPlayerBallProjectile.mapId
                != fieldSystem->location->mapId) {
            return TRUE;
        }
        sOverworldWildHelperPlayerBallProjectile.objectId =
            OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if (fieldSystem->taskman != NULL) {
        sOverworldWildHelperPlayerBallInputArmed = FALSE;
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return TRUE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
        == OW_WILD_HELPER_PLAYER_BALL_PHASE_CHARGING) {
        if (!sOverworldWildHelperPlayerBallInputArmed
            || (pad & PAD_BUTTON_L) != 0
            || !OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
                fieldSystem)) {
            if (rDown) {
                sOverworldWildHelperPlayerBallInputArmed = FALSE;
            }
            sOverworldWildHelperPlayerBallChargeFrames = 0;
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return FALSE;
        }
        if (rDown) {
            if (sOverworldWildHelperPlayerBallChargeFrames
                < OW_WILD_HELPER_PLAYER_BALL_MAX_CHARGE_FRAMES) {
                sOverworldWildHelperPlayerBallChargeFrames++;
            }
            sOverworldWildHelperPlayerBallProjectile.elapsedFrames++;
            if (!OverworldWildHelper_ApplyPlayerBallChargeRender(fieldSystem)) {
                sOverworldWildHelperPlayerBallInputArmed = FALSE;
                sOverworldWildHelperPlayerBallChargeFrames = 0;
                OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
                return OverworldWildHelper_IsPlayerBallFrameServiceActive();
            }
            OverworldWildHelper_TickPlayerBallChargeSound();
            return TRUE;
        }
        if (rReleased) {
            if (!OverworldWildHelper_ApplyPlayerBallChargeRender(fieldSystem)) {
                sOverworldWildHelperPlayerBallInputArmed = FALSE;
                sOverworldWildHelperPlayerBallChargeFrames = 0;
                OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
                return OverworldWildHelper_IsPlayerBallFrameServiceActive();
            }
            sOverworldWildHelperPlayerBallChargeSoundTimer = 0;
            distanceFx32 = OW_WILD_HELPER_PLAYER_BALL_MIN_DISTANCE_FX32
                + sOverworldWildHelperPlayerBallChargeFrames
                    * OW_WILD_HELPER_PLAYER_BALL_CHARGE_STEP_FX32;
            sOverworldWildHelperPlayerBallChargeFrames = 0;
            if (OverworldWildHelper_TryLaunchPlayerBallProjectile(
                    fieldSystem,
                    state,
                    distanceFx32)) {
                return TRUE;
            }
        }
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
            >= OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
        && sOverworldWildHelperPlayerBallProjectile.phase
            <= OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT) {
        BOOL active = OverworldWildHelper_TickPlayerBallCapture(
            fieldSystem,
            state,
            presentation,
            telemetry,
            resetSlot,
            findDestination);

        return active
            || OverworldWildHelper_IsPlayerBallFrameServiceActive();
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
        == OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING) {
        OverworldWildHelperPlayerBallProjectileState *projectile =
            &sOverworldWildHelperPlayerBallProjectile;

        if (rDown) {
            sOverworldWildHelperPlayerBallInputArmed = FALSE;
        } else {
            sOverworldWildHelperPlayerBallInputArmed = TRUE;
        }
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        if (!OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(fieldSystem)
            || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
            || state->presentationRestorePending
            || state->mapGeneration
                != sOverworldWildHelperPlayerBallProjectile.mapGeneration) {
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return FALSE;
        }
        if (state->followerReleaseState
            == OW_WILD_FOLLOWER_RELEASE_SPAWNED) {
            BOOL releaseActive;

            if (!OverworldWildHelper_IsExactObject(
                    fieldSystem,
                    state,
                    OW_WILD_FOLLOWER_SLOT)) {
                OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
                state->followerReleaseState =
                    OW_WILD_FOLLOWER_RELEASE_FAILED;
                return FALSE;
            }
            /* Home toward the player's current hand, not the throw origin. */
            OverworldWildHelper_RefreshFollowerBallReturnTarget(fieldSystem);
            releaseActive = OverworldWildSpawns_TickFollowerReleasePresentation(
                fieldSystem,
                state,
                projectile,
                OverworldWildHelper_DispatchFollowerRelease,
                OverworldWildHelper_ApplyPlayerBallRotation);
            if (projectile->shakeIndex == 1) {
                OverworldWildHelper_DispatchFollowerRelease(fieldSystem, 0);
            } else if (projectile->shakeIndex == 2) {
                OverworldWildHelper_DispatchFollowerRelease(fieldSystem, 3);
            } else if (projectile->shakeIndex == 5) {
                OverworldWildHelper_DispatchFollowerRelease(fieldSystem, 1);
            }
            return releaseActive;
        }
        if ((state->followerReleaseState
                & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
            == OW_WILD_FOLLOWER_RELEASE_READY) {
            return TRUE;
        }
        if (projectile->elapsedFrames >= projectile->totalFrames) {
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return FALSE;
        }
        oldX = (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[0];
        oldZ = (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[2];
        sOverworldWildHelperPlayerBallProjectile.elapsedFrames++;
        OverworldWildSpawns_RenderPlayerBallProjectile(
            &sOverworldWildHelperPlayerBallProjectile,
            OverworldWildHelper_ApplyPlayerBallRotation);
        hitSlot = OverworldWildHelper_FindPlayerBallHit(
            fieldSystem,
            state,
            oldX,
            oldZ,
            (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[0],
            (s32)sOverworldWildHelperPlayerBallProjectile.object->posVec[2]);
        if (hitSlot >= 0) {
            if ((state->followerReleaseState
                    & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
                    == OW_WILD_FOLLOWER_RELEASE_FLYING) {
                (void)OverworldWildSpawns_StartFollowerReleaseBounce(
                    fieldSystem,
                    state,
                    projectile,
                    hitSlot);
                return TRUE;
            }
            if (OverworldWildHelper_StartPlayerBallImpact(
                    fieldSystem,
                    state,
                    hitSlot,
                    prepareCaptureTarget,
                    calculateShakes)) {
                return TRUE;
            }
        }
        if (((state->followerReleaseState
                    & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
                    == OW_WILD_FOLLOWER_RELEASE_FLYING
                || (state->followerReleaseState
                        & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
                    == OW_WILD_FOLLOWER_RELEASE_BOUNCING)
            && projectile->elapsedFrames
                >= projectile->totalFrames
                    - OW_WILD_HELPER_PLAYER_BALL_HANG_FRAMES
                    - OW_WILD_HELPER_PLAYER_BALL_FALL_FRAMES) {
            projectile->impactSlot = OW_WILD_FOLLOWER_SLOT;
            state->captureTargetMask |=
                (u16)(1u << OW_WILD_FOLLOWER_SLOT);
            state->followerReleaseState =
                OW_WILD_FOLLOWER_RELEASE_READY
                | (state->followerReleaseState
                    & OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG);
            gOverworldWildFieldIdleRearmPending |=
                OW_WILD_FIELD_IDLE_REARM_PENDING
                | OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING;
            PlaySE(OW_WILD_HELPER_FOLLOWER_EMERGE_SE);
        }
        return TRUE;
    }
    if (sOverworldWildHelperPlayerBallProjectile.phase
        != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE) {
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return FALSE;
    }
    if (!sOverworldWildHelperPlayerBallStaleCheckDone) {
        if (!OverworldWildHelper_PlayerBallObjectIdAvailable(fieldSystem)) {
            return TRUE;
        }
        /* Preserve an R press held through bounded stale-object cleanup. */
        rPressed = rDown && sOverworldWildHelperPlayerBallInputArmed;
    }
    if (state->followerReleaseState == OW_WILD_FOLLOWER_RELEASE_FLYING) {
        state->followerReleaseState = OW_WILD_FOLLOWER_RELEASE_REQUESTED;
    }
    if ((state->followerReleaseState
            & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
            == OW_WILD_FOLLOWER_RELEASE_REQUESTED) {
        distanceFx32 = OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY
            ->getReleaseDistance(fieldSystem);
        if (distanceFx32 > 0
            && OverworldWildHelper_TryStartPlayerBallCharge(fieldSystem, state)
            && OverworldWildHelper_TryLaunchPlayerBallProjectile(
                fieldSystem,
                state,
                distanceFx32)) {
            state->followerReleaseState = OW_WILD_FOLLOWER_RELEASE_FLYING;
            return TRUE;
        }
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        state->followerReleaseState = OW_WILD_FOLLOWER_RELEASE_FAILED;
        return FALSE;
    }
    if (!sOverworldWildHelperPlayerBallInputArmed) {
        if (!rDown) {
            sOverworldWildHelperPlayerBallInputArmed = TRUE;
        }
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        return rDown || OverworldWildHelper_IsPlayerBallFrameServiceActive();
    }
    if ((pad & PAD_BUTTON_L) != 0) {
        if (rDown) {
            sOverworldWildHelperPlayerBallInputArmed = FALSE;
        }
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        return rDown || OverworldWildHelper_IsPlayerBallFrameServiceActive();
    }
    if (rPressed) {
        sOverworldWildHelperPlayerBallChargeFrames = 0;
        return OverworldWildHelper_TryStartPlayerBallCharge(
                fieldSystem,
                state)
            || OverworldWildHelper_IsPlayerBallFrameServiceActive();
    }
    return OverworldWildHelper_IsPlayerBallFrameServiceActive();
}

static LocalMapObject *OverworldWildHelper_GetPlayerBallProjectileObject(void)
{
    return sOverworldWildHelperPlayerBallProjectile.phase
            != OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE
            && sOverworldWildHelperPlayerBallProjectile.objectId
                == OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID
        ? sOverworldWildHelperPlayerBallProjectile.object
        : NULL;
}

static void OverworldWildHelper_CleanupResidentData(FieldSystem *fieldSystem)
{
    OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
    sOverworldWildHelperPlayerBallRWasDown = FALSE;
    sOverworldWildHelperPlayerBallInputArmed = FALSE;
    sOverworldWildHelperPlayerBallStaleCheckDone = FALSE;
    sOverworldWildHelperPlayerBallChargeFrames = 0;
}

static void OverworldWildHelper_NormalizeThrowPresentation(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldWildHelperPlayerBallProjectileState *projectile =
        &sOverworldWildHelperPlayerBallProjectile;
    LocalMapObject *object;
    int x;
    int y;

    if (slot == OW_WILD_HELPER_THROW_PRESENTATION_TRANSITION_DISCARD) {
        if (projectile->objectId == 0) {
            projectile->objectId = OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
        }
        OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
        return;
    }
    if (slot == OW_WILD_HELPER_THROW_PRESENTATION_TRANSITION_SUSPEND) {
        if (projectile->phase == OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE) {
            return;
        }
        if (projectile->objectId == 0) {
            return;
        }
        if (projectile->objectId != OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID
            || projectile->state != state) {
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return;
        }
        OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
        if (OverworldWildHelper_IsPlayerBallProjectileObjectCurrent(
                fieldSystem)) {
            OverworldWildHelper_DetachPlayerBallRotation(projectile->object);
        } else {
            projectile->object = NULL;
        }
        projectile->objectId = 0;
        return;
    }
    if (slot == OW_WILD_HELPER_THROW_PRESENTATION_TRANSITION_RESUME) {
        OVERWORLD_MOUNT_OVERLAY_ENTRY->prepareMapTransition(
            OW_WILD_MAP_HEADER_CHANGE_RESUME_PRESENTATION);
        if (projectile->phase == OW_WILD_HELPER_PLAYER_BALL_PHASE_NONE) {
            return;
        }
        if (projectile->objectId != 0
            || projectile->state != state
            || !OverworldWildHelper_IsPresentationContextCurrent(
                fieldSystem,
                state)
            || (projectile->phase >= OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
                && (!OverworldWildHelper_IsExactObject(
                        fieldSystem,
                        state,
                        projectile->impactSlot)
                    || state->spawns[projectile->impactSlot]
                            .encounterGeneration
                        != projectile->impactEncounterGeneration))) {
            projectile->objectId = OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return;
        }
        if (fieldSystem->playerAvatar == NULL
            || fieldSystem->playerAvatar->mapObject == NULL
            || fieldSystem->playerAvatar->mapObject->curFacing > 3
            || (object = OverworldWildHelper_CreatePlayerBallObject(
                    fieldSystem)) == NULL) {
            projectile->objectId = OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
            OverworldWildHelper_CancelPlayerBallProjectile(fieldSystem);
            return;
        }
        projectile->fieldSystem = fieldSystem;
        projectile->manager = (MapObjectMan *)fieldSystem->mapObjectMan;
        projectile->objects = projectile->manager->objects;
        projectile->object = object;
        projectile->mapId = fieldSystem->location->mapId;
        projectile->mapGeneration = state->mapGeneration;
        projectile->objectId = OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID;
        if (projectile->phase == OW_WILD_HELPER_PLAYER_BALL_PHASE_FLYING) {
            s16 rotation = projectile->rotation;

            projectile->object->curFacing = projectile->targetHadPassThrough;
            projectile->object->nextFacing = projectile->targetHadPassThrough;
            OverworldWildSpawns_RenderPlayerBallProjectile(
                &sOverworldWildHelperPlayerBallProjectile,
                OverworldWildHelper_ApplyPlayerBallRotation);
            OverworldWildHelper_ApplyPlayerBallRotation(rotation);
        }
        if ((projectile->phase > OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
                && projectile->phase
                    != OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT)
            || (projectile->phase == OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
                && projectile->elapsedFrames
                    >= OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME)) {
            OverworldWildHelper_ReservePlayerBallCaptureTarget(state);
        } else if (projectile->phase
            == OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT) {
            state->captureTargetMask |=
                (u16)(1u << projectile->impactSlot);
        }
        if (projectile->targetHadPassThrough
            && (projectile->phase == OW_WILD_HELPER_PLAYER_BALL_PHASE_BREAKOUT
                || (projectile->phase
                        == OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
                    && projectile->elapsedFrames
                        < OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME))) {
            MapObject_SetBits(
                state->spawns[projectile->impactSlot].object,
                MAPOBJECTFLAG_UNK18);
        }
        if (projectile->phase == OW_WILD_HELPER_PLAYER_BALL_PHASE_IMPACT
            && projectile->elapsedFrames
                <= OW_WILD_HELPER_PLAYER_BALL_IMPACT_DESCENT_FRAME
                    + OW_WILD_HELPER_PLAYER_BALL_SECOND_FLASH_EXTRA_FRAMES) {
            OverworldWildHelper_RestoreCaptureTargetPalette(fieldSystem);
            OverworldWildHelper_PrepareCaptureWhiteBall(fieldSystem);
            OverworldWildHelper_ApplyCaptureTargetWhite(fieldSystem);
            if (projectile->elapsedFrames
                    > OW_WILD_HELPER_PLAYER_BALL_IMPACT_FLASH_FRAMES
                && projectile->elapsedFrames
                    <= OW_WILD_HELPER_PLAYER_BALL_IMPACT_APEX_FRAME) {
                OverworldWildHelper_RestoreCaptureWhiteBall(fieldSystem);
            }
        } else if (projectile->phase
                == OW_WILD_HELPER_PLAYER_BALL_PHASE_SHAKING
            && projectile->shakeIndex == 3
            && projectile->elapsedFrames != 0
            && projectile->elapsedFrames
                <= OW_WILD_HELPER_PLAYER_BALL_CAUGHT_WHITE_FRAMES) {
            ChangeMapObjSprite(
                projectile->object,
                OW_WILD_HELPER_PLAYER_BALL_WHITE_TAG);
        }
        return;
    }

    if (!OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        return;
    }

    object = state->spawns[slot].object;
    x = MapObject_GetCurrentX(object);
    y = MapObject_GetCurrentY(object);
    object->xInit = x;
    object->yInit = y;
    object->xPrev = x;
    object->yPrev = y;
    object->posVec[0] = (u32)((s32)x * 0x10000 + 0x8000);
    object->posVec[2] = (u32)((s32)y * 0x10000 + 0x8000);
    /* Retained objects already carry their current coordinates and elevation. */
    object->faceVec[0] = 0;
    object->faceVec[1] = 0;
    object->faceVec[2] = 0;
    object->unk88[1] = 0;
    object->unk94[1] = 0;
    MapObject_ClearBits(
        object,
        BIT_VANISH | MAPOBJECTFLAG_UNK18);
}

static void OverworldWildHelper_SyncCarriedThrowTarget(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int carrierSlot,
    int targetSlot)
{
    LocalMapObject *carrierObject;
    LocalMapObject *targetObject;

    if (presentation == NULL
        || !OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, carrierSlot)
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, targetSlot)) {
        return;
    }

    carrierObject = state->spawns[carrierSlot].object;
    targetObject = state->spawns[targetSlot].object;
    targetObject->xCurr = carrierObject->xCurr;
    targetObject->yCurr = carrierObject->yCurr;
    targetObject->hCurr = carrierObject->hCurr;
    targetObject->xPrev = carrierObject->xPrev;
    targetObject->yPrev = carrierObject->yPrev;
    targetObject->hPrev = carrierObject->hPrev;
    targetObject->posVec[0] = carrierObject->posVec[0];
    targetObject->posVec[1] = carrierObject->posVec[1];
    targetObject->posVec[2] = carrierObject->posVec[2];
    targetObject->faceVec[0] = carrierObject->faceVec[0];
    targetObject->faceVec[1] =
        carrierObject->faceVec[1] + OW_WILD_HELPER_THROW_CARRIED_Y_OFFSET_FX32;
    targetObject->faceVec[2] = carrierObject->faceVec[2];
    targetObject->unk88[0] = carrierObject->unk88[0];
    targetObject->unk88[1] =
        carrierObject->unk88[1] + OW_WILD_HELPER_THROW_CARRIED_Y_OFFSET_FX32;
    targetObject->unk88[2] = carrierObject->unk88[2];
    targetObject->unk94[0] = carrierObject->unk94[0];
    targetObject->unk94[1] = carrierObject->unk94[1];
    targetObject->unk94[2] = carrierObject->unk94[2];
    MapObject_SetBits(targetObject, MAPOBJECTFLAG_UNK18);
    MapObject_ClearBits(targetObject, BIT_VANISH);
    presentation->lastKnownX[carrierSlot] = (s16)MapObject_GetCurrentX(carrierObject);
    presentation->lastKnownY[carrierSlot] = (s16)MapObject_GetCurrentY(carrierObject);
    presentation->lastKnownX[targetSlot] = presentation->lastKnownX[carrierSlot];
    presentation->lastKnownY[targetSlot] = presentation->lastKnownY[carrierSlot];
}

static BOOL OverworldWildHelper_IsPickupThrowMovementContextCurrent(
    OverworldWildSpawnState *state)
{
    FieldSystem *fieldSystem;

    if (state == NULL) {
        return FALSE;
    }
    fieldSystem = state->movementFieldSystem;
    return fieldSystem != NULL
        && fieldSystem->playerAvatar != NULL
        && OverworldWildHelper_IsPresentationContextCurrent(fieldSystem, state);
}

static BOOL OverworldWildHelper_IsValidPickupThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot)
{
    if (state == NULL
        || throwState == NULL
        || carrierSlot < 0
        || carrierSlot >= OW_WILD_MAX_SPAWNS
        || targetSlot < 0
        || targetSlot >= OW_WILD_MAX_SPAWNS
        || carrierSlot == OW_WILD_FOLLOWER_SLOT
        || targetSlot == OW_WILD_FOLLOWER_SLOT
        || carrierSlot == targetSlot
        || !state->spawns[targetSlot].active
        || state->spawns[targetSlot].object == NULL
        || state->movementBehaviorClasses[targetSlot] == OW_WILD_BEHAVIOR_CLASS_PICKED_UP
        || state->movementQueuedBattleSlot == targetSlot
        || state->pendingSlot == targetSlot
        || throwState->targets[targetSlot] != OW_WILD_HELPER_THROW_TARGET_NONE) {
        return FALSE;
    }

    return OverworldWildHelper_IsPickupThrowMovementContextCurrent(state)
        && OverworldWildHelper_IsExactObject(
            state->movementFieldSystem,
            state,
            targetSlot);
}

static BOOL OverworldWildHelper_IsStablePickupThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot,
    u16 unstableMask)
{
    LocalMapObject *object;

    if (!OverworldWildHelper_IsValidPickupThrowTarget(
            state,
            throwState,
            carrierSlot,
            targetSlot)
        || state->movementSpotStates[targetSlot] == 1
        || (unstableMask & (1u << targetSlot)) != 0
        || state->movementSpawnRunActive[targetSlot]
        || state->movementStagedHopPending[targetSlot]
        || state->movementRamCrashShakeTimers[targetSlot] != 0
        || state->movementTeleportHidden[targetSlot]
        || state->movementTeleportFlickerTimers[targetSlot] != 0
        || state->movementTeleportFlickerObjects[targetSlot] != NULL
        || (state->movementInProgressMask & (1u << targetSlot)) != 0) {
        return FALSE;
    }

    object = state->spawns[targetSlot].object;
    return !MapObject_IsSingleMovementActive(object)
        && (object->flags & BIT_VANISH) == 0;
}

static BOOL OverworldWildHelper_IsReservedPickupTargetNearCarrier(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int targetSlot)
{
    int carrierSlot;

    if (state == NULL
        || throwState == NULL
        || targetSlot < 0
        || targetSlot >= OW_WILD_MAX_SPAWNS
        || (throwState->targetMask & (1u << targetSlot)) == 0
        || state->movementBehaviorClasses[targetSlot] == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
        return FALSE;
    }

    for (carrierSlot = 0; carrierSlot < OW_WILD_MAX_SPAWNS; carrierSlot++) {
        u8 relation = throwState->targets[carrierSlot];
        LocalMapObject *carrierObject;
        LocalMapObject *targetObject;

        if (relation == OW_WILD_HELPER_THROW_TARGET_NONE
            || (relation & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) != 0
            || OW_WILD_HELPER_THROW_TARGET_DECODE(relation) != targetSlot
            || !OverworldWildHelper_IsValidPickupThrowTarget(
                state,
                throwState,
                carrierSlot,
                targetSlot)
            || !OverworldWildHelper_IsExactObject(
                state->movementFieldSystem,
                state,
                carrierSlot)) {
            continue;
        }

        carrierObject = state->spawns[carrierSlot].object;
        targetObject = state->spawns[targetSlot].object;
        return OverworldWildHelper_Max(
            OverworldWildHelper_Abs(
                MapObject_GetCurrentX(carrierObject) - MapObject_GetCurrentX(targetObject)),
            OverworldWildHelper_Abs(
                MapObject_GetCurrentY(carrierObject) - MapObject_GetCurrentY(targetObject))) <= 1;
    }
    return FALSE;
}

static BOOL OverworldWildHelper_QueryPickupThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot,
    u8 query,
    u16 unstableMask)
{
    if (query == OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE) {
        return OverworldWildHelper_IsStablePickupThrowTarget(
            state,
            throwState,
            carrierSlot,
            targetSlot,
            unstableMask);
    }
    if (query == OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_NEAR) {
        return OverworldWildHelper_IsReservedPickupTargetNearCarrier(
            state,
            throwState,
            targetSlot);
    }
    return query == OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID
        && OverworldWildHelper_IsValidPickupThrowTarget(
            state,
            throwState,
            carrierSlot,
            targetSlot);
}

static u16 OverworldWildHelper_ClearPickupThrowState(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    int slot)
{
    u16 restoreMask = 0;
    int i;

    if (state == NULL
        || throwState == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return 0;
    }

    throwState->targetMask &= ~(1u << slot);
    throwState->carrierMask &= ~(1u << slot);
    presentation->farSamples[slot] = 0;
    if (state->movementBehaviorClasses[slot] == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
        restoreMask |= 1u << slot;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u8 relation = throwState->targets[i];
        u8 target;

        if (relation == OW_WILD_HELPER_THROW_TARGET_NONE) {
            continue;
        }
        target = OW_WILD_HELPER_THROW_TARGET_DECODE(relation);
        if (target >= OW_WILD_MAX_SPAWNS) {
            throwState->targets[i] = OW_WILD_HELPER_THROW_TARGET_NONE;
            throwState->carrierMask &= ~(1u << i);
            state->movementEmoteTimers[i] = 0;
            continue;
        }
        if (i == slot || target == slot) {
            throwState->targetMask &= ~(1u << target);
            presentation->farSamples[target] = 0;
            if ((relation & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) != 0
                && state->movementBehaviorClasses[target]
                    == OW_WILD_BEHAVIOR_CLASS_PICKED_UP) {
                restoreMask |= 1u << target;
            }
            throwState->targets[i] = OW_WILD_HELPER_THROW_TARGET_NONE;
            throwState->carrierMask &= ~(1u << i);
            state->movementEmoteTimers[i] = 0;
        }
    }
    return restoreMask;
}

static BOOL OverworldWildHelper_TryStartPickupThrowAction(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    int slot,
    u16 unstableMask)
{
    int i;

    if (state == NULL
        || throwState == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || throwState->targets[slot] != OW_WILD_HELPER_THROW_TARGET_NONE
        || ((throwState->targetMask | throwState->carrierMask) & (1u << slot)) != 0) {
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u16 targetMask = 1u << i;

        if (OverworldWildHelper_IsStablePickupThrowTarget(
                state,
                throwState,
                slot,
                i,
                unstableMask)
            && throwState->targets[i] == OW_WILD_HELPER_THROW_TARGET_NONE
            && (throwState->targetMask & targetMask) == 0) {
            throwState->targets[slot] = OW_WILD_HELPER_THROW_TARGET_ENCODE(i);
            throwState->targetMask |= targetMask;
            throwState->carrierMask |= 1u << slot;
            presentation->farSamples[slot] = 0;
            presentation->farSamples[i] = 0;
            state->movementEmoteTimers[slot] =
                OW_WILD_HELPER_THROW_RESERVATION_DECISIONS;
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL OverworldWildHelper_StartCarriedThrowTarget(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    int carrierSlot,
    int targetSlot)
{
    LocalMapObject *targetObject;

    if (state == NULL
        || throwState == NULL
        || presentation == NULL
        || !OverworldWildHelper_IsPickupThrowMovementContextCurrent(state)
        || !OverworldWildHelper_IsExactObject(
            state->movementFieldSystem,
            state,
            carrierSlot)
        || !OverworldWildHelper_IsExactObject(
            state->movementFieldSystem,
            state,
            targetSlot)) {
        return FALSE;
    }

    targetObject = state->spawns[targetSlot].object;
    state->movementSpotStates[targetSlot] = 0;
    state->movementEmoteTimers[targetSlot] = 0;
    state->movementActiveSteps[targetSlot] = 0;
    state->movementBehaviorClasses[targetSlot] = OW_WILD_BEHAVIOR_CLASS_PICKED_UP;
    MapObject_SetBits(targetObject, MAPOBJECTFLAG_UNK18);
    MapObject_ClearBits(targetObject, BIT_VANISH);
    throwState->targets[carrierSlot] =
        OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(targetSlot);
    throwState->targetMask |= 1u << targetSlot;
    throwState->carrierMask |= 1u << carrierSlot;
    state->movementEmoteTimers[carrierSlot] = 0;
    OverworldWildHelper_SyncCarriedThrowTarget(
        state->movementFieldSystem,
        state,
        presentation,
        carrierSlot,
        targetSlot);
    return TRUE;
}

static BOOL OverworldWildHelper_ConfirmDistanceDespawn(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int slot,
    BOOL movementProtected,
    u8 *distance)
{
    LocalMapObject *object;
    int dx;
    int dy;
    int measured;

    if (state == NULL
        || fieldSystem == NULL
        || presentation == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->spawns[slot].shiny
        || movementProtected
        || fieldSystem->playerAvatar == NULL
        || !OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        if (state != NULL
            && presentation != NULL
            && slot >= 0
            && slot < OW_WILD_MAX_SPAWNS) {
            presentation->farSamples[slot] = 0;
        }
        return FALSE;
    }
    object = state->spawns[slot].object;
    presentation->lastKnownX[slot] = (s16)MapObject_GetCurrentX(object);
    presentation->lastKnownY[slot] = (s16)MapObject_GetCurrentY(object);
    dx = presentation->lastKnownX[slot] - GetPlayerXCoord(fieldSystem->playerAvatar);
    dy = presentation->lastKnownY[slot] - GetPlayerYCoord(fieldSystem->playerAvatar);
    dx = dx < 0 ? -dx : dx;
    dy = dy < 0 ? -dy : dy;
    measured = dx > dy ? dx : dy;
    if (distance != NULL) {
        *distance = measured > 255 ? 255 : (u8)measured;
    }
    if (measured <= OW_WILD_DISTANCE_DESPAWN_TILES) {
        presentation->farSamples[slot] = 0;
        return FALSE;
    }
    if (presentation->farSamples[slot] < OW_WILD_DISTANCE_DESPAWN_SAMPLES) {
        presentation->farSamples[slot]++;
    }
    return presentation->farSamples[slot] >= OW_WILD_DISTANCE_DESPAWN_SAMPLES;
}

static OverworldWildDespawnAuthorization OverworldWildHelper_AuthorizeDespawn(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    LocalMapObject **verifiedObject)
{
    MapObjectMan *manager;
    LocalMapObject *candidate = NULL;
    BOOL terminalBattle = reason == OW_WILD_DESPAWN_REASON_BATTLE_DEFEATED
        || reason == OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT;
    int candidateCount = 0;
    int i;

    if (verifiedObject != NULL) {
        *verifiedObject = NULL;
    }
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || presentation == NULL
        || !state->spawns[slot].active
        || expectedGeneration == 0
        || state->spawns[slot].encounterGeneration != expectedGeneration
        || reason <= OW_WILD_DESPAWN_REASON_NONE
        || reason > OW_WILD_DESPAWN_REASON_DISTANCE
        || (reason == OW_WILD_DESPAWN_REASON_DISTANCE
            && presentation->farSamples[slot] < OW_WILD_DISTANCE_DESPAWN_SAMPLES)) {
        return OW_WILD_DESPAWN_DENIED;
    }
    if (OverworldWildHelper_IsExactObject(fieldSystem, state, slot)) {
        if (verifiedObject != NULL) {
            *verifiedObject = state->spawns[slot].object;
        }
        return OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT;
    }
    if (!terminalBattle) {
        /* Distance removal never clears without the exact active presentation. */
        return OW_WILD_DESPAWN_DENIED;
    }
    if (!OverworldWildHelper_IsContextCurrent(fieldSystem, state)) {
        return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
    }
    if (state->spawns[slot].mapId != fieldSystem->location->mapId) {
        return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if (object->id == OW_WILD_OBJECT_ID_START + slot
            && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
            candidate = object;
            candidateCount++;
        }
    }
    if (candidateCount > 1) {
        return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
    }
    if (candidateCount == 1) {
        if ((candidate->flags & MAPOBJECTFLAG_ACTIVE) != 0) {
            state->spawns[slot].object = candidate;
        }
        if (verifiedObject != NULL) {
            *verifiedObject = candidate;
        }
        return OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT;
    }
    return OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY;
}

static void OverworldWildHelper_RecordDespawnEvent(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    OverworldWildDespawnReason reason,
    OverworldWildDespawnAction action,
    u8 distance)
{
    OverworldWildDespawnRecord *record;
    OverworldWildSpawn *spawn;
    LocalMapObject *object;
    BOOL exactObject;
    u8 flags = 0;

    if (state == NULL
        || presentation == NULL
        || telemetry == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }
    if (telemetry->magic != OW_WILD_DESPAWN_TELEMETRY_MAGIC) {
        telemetry->magic = OW_WILD_DESPAWN_TELEMETRY_MAGIC;
        telemetry->sequence = 0;
        telemetry->writeIndex = 0;
        telemetry->unexpectedCount = 0;
    }
    spawn = &state->spawns[slot];
    object = spawn->object;
    exactObject = OverworldWildHelper_IsExactObject(fieldSystem, state, slot);
    if (OverworldWildHelper_IsContextCurrent(fieldSystem, state)) {
        flags |= OW_WILD_DESPAWN_CONTEXT_CURRENT;
    }
    if (fieldSystem != NULL && fieldSystem->taskman != NULL) {
        flags |= OW_WILD_DESPAWN_CONTEXT_TASK_BUSY;
    }
    if (exactObject) {
        flags |= OW_WILD_DESPAWN_CONTEXT_POINTER_IN_ARRAY
            | OW_WILD_DESPAWN_CONTEXT_OBJECT_ACTIVE
            | OW_WILD_DESPAWN_CONTEXT_EXACT_ID
            | OW_WILD_DESPAWN_CONTEXT_EXACT_SCRIPT;
    }
    record = &telemetry->records[telemetry->writeIndex];
    record->sequence = ++telemetry->sequence;
    record->objectPtr = (u32)object;
    record->objectFlags = exactObject ? object->flags : 0;
    record->personality = spawn->personality;
    record->mapId = fieldSystem != NULL && fieldSystem->location != NULL
        ? (u16)fieldSystem->location->mapId
        : MAP_NOTHING;
    record->spawnMapId = spawn->mapId;
    record->mapGeneration = state->mapGeneration;
    record->encounterGeneration = spawn->encounterGeneration;
    record->objectX = exactObject
        ? (s16)MapObject_GetCurrentX(object)
        : presentation->lastKnownX[slot];
    record->objectY = exactObject
        ? (s16)MapObject_GetCurrentY(object)
        : presentation->lastKnownY[slot];
    record->playerX = fieldSystem != NULL && fieldSystem->playerAvatar != NULL
        ? (s16)GetPlayerXCoord(fieldSystem->playerAvatar)
        : 0;
    record->playerY = fieldSystem != NULL && fieldSystem->playerAvatar != NULL
        ? (s16)GetPlayerYCoord(fieldSystem->playerAvatar)
        : 0;
    record->objectId = exactObject ? (s16)object->id : -1;
    record->reason = (u8)reason;
    record->action = (u8)action;
    record->slot = (u8)slot;
    record->distance = distance;
    record->contextFlags = flags;
    record->expectedObjectId = spawn->objectId;
    if (reason < 4) {
        telemetry->reasonCounts[reason]++;
    }
    if (action == OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED
        || action == OW_WILD_DESPAWN_ACTION_IDENTITY_CONFLICT) {
        telemetry->unexpectedCount++;
    }
    telemetry->writeIndex = (telemetry->writeIndex + 1)
        % OW_WILD_DESPAWN_RECORD_COUNT;
}

static u8 OverworldWildHelper_ClassifyBattleResult(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 battleResult)
{
    int slot;

    if (state == NULL) {
        return OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
    slot = state->pendingSlot;
    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->pendingPersonality != state->spawns[slot].personality
        || state->pendingMapGeneration == 0
        || state->pendingMapGeneration != state->mapGeneration
        || state->pendingEncounterGeneration == 0
        || state->pendingEncounterGeneration != state->spawns[slot].encounterGeneration
        || state->spawns[slot].objectId != OW_WILD_OBJECT_ID_START + slot) {
        return OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
    (void)fieldSystem;
    switch (battleResult) {
    case OW_WILD_BATTLE_RESULT_WIN:
        return OW_WILD_BATTLE_DISPOSITION_DEFEATED;
    case OW_WILD_BATTLE_RESULT_CAUGHT:
        return OW_WILD_BATTLE_DISPOSITION_CAUGHT;
    case OW_WILD_BATTLE_RESULT_PLAYER_FLED:
        return OW_WILD_BATTLE_DISPOSITION_FLED;
    default:
        return (battleResult & OW_WILD_BATTLE_RESULT_TRY_FLEE) != 0
            ? OW_WILD_BATTLE_DISPOSITION_FLED
            : OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
}

static int OverworldWildHelper_ReconcilePresentations(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperRecreatePresentationFunc recreatePresentation)
{
    MapObjectMan *manager;
    int i;

    if (fieldSystem == NULL
        || state == NULL
        || presentation == NULL
        || recreatePresentation == NULL
        || !OverworldWildHelper_IsContextCurrent(fieldSystem, state)
        || fieldSystem->taskman != NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *candidate = NULL;
        u16 slotMask = (u16)(1u << i);
        int candidateCount = 0;
        int j;

        if (!state->spawns[i].active) {
            presentation->managerRestoreMask &= (u16)~slotMask;
            continue;
        }
        if (OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            presentation->lastKnownX[i] = (s16)MapObject_GetCurrentX(state->spawns[i].object);
            presentation->lastKnownY[i] = (s16)MapObject_GetCurrentY(state->spawns[i].object);
            presentation->managerRestoreMask &= (u16)~slotMask;
            continue;
        }
        state->spawns[i].object = NULL;
        for (j = 0; j < (int)manager->object_count; j++) {
            LocalMapObject *object = &manager->objects[j];

            if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
                && object->id == OW_WILD_OBJECT_ID_START + i
                && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
                candidate = object;
                candidateCount++;
            }
        }
        if (candidateCount > 1) {
            OverworldWildHelper_RecordDespawnEvent(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                OW_WILD_DESPAWN_REASON_NONE,
                OW_WILD_DESPAWN_ACTION_IDENTITY_CONFLICT,
                0);
            return OW_WILD_RECONCILE_POISONED_SLOT_BASE + i;
        }
        if (candidateCount == 1) {
            state->spawns[i].object = candidate;
            state->spawns[i].objectId = OW_WILD_OBJECT_ID_START + i;
            if (recreatePresentation(
                    state,
                    fieldSystem,
                    i,
                    candidate,
                    MapObject_GetCurrentX(candidate),
                    MapObject_GetCurrentY(candidate)) == NULL
                || !OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
                state->spawns[i].object = NULL;
                return OW_WILD_RECONCILE_POISONED_SLOT_BASE + i;
            }
            presentation->lastKnownX[i] = (s16)MapObject_GetCurrentX(candidate);
            presentation->lastKnownY[i] = (s16)MapObject_GetCurrentY(candidate);
            if ((presentation->managerRestoreMask & slotMask) != 0) {
                presentation->farSamples[i] = 0;
            }
            presentation->managerRestoreMask &= (u16)~slotMask;
            OverworldWildHelper_RecordDespawnEvent(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                OW_WILD_DESPAWN_REASON_NONE,
                OW_WILD_DESPAWN_ACTION_REBIND_OBJECT,
                0);
            continue;
        }
        if ((presentation->managerRestoreMask & slotMask) == 0) {
            /* A missing record in an unchanged manager is an invariant failure. */
            OverworldWildHelper_RecordDespawnEvent(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                OW_WILD_DESPAWN_REASON_NONE,
                OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED,
                0);
            return OW_WILD_RECONCILE_POISONED_SLOT_BASE + i;
        }
        OverworldWildHelper_RecordDespawnEvent(
            fieldSystem,
            state,
            presentation,
            telemetry,
            i,
            OW_WILD_DESPAWN_REASON_NONE,
            OW_WILD_DESPAWN_ACTION_PRESENTATION_MISSING,
            0);
        if (GetMetatileBehaviorAt(
                fieldSystem,
                presentation->lastKnownX[i],
                presentation->lastKnownY[i]) == 0xFF) {
            return OW_WILD_RECONCILE_POISONED_SLOT_BASE + i;
        }
        if (recreatePresentation(
                state,
                fieldSystem,
                i,
                NULL,
                presentation->lastKnownX[i],
                presentation->lastKnownY[i]) == NULL) {
            /* Object capacity/allocation failure is retryable, not poison. */
            return OW_WILD_RECONCILE_RETRY;
        }
        if (!OverworldWildHelper_IsExactObject(fieldSystem, state, i)) {
            return OW_WILD_RECONCILE_POISONED_SLOT_BASE + i;
        }
        presentation->managerRestoreMask &= (u16)~slotMask;
        presentation->farSamples[i] = 0;
        OverworldWildHelper_RecordDespawnEvent(
            fieldSystem,
            state,
            presentation,
            telemetry,
            i,
            OW_WILD_DESPAWN_REASON_NONE,
            OW_WILD_DESPAWN_ACTION_RECREATE_OBJECT,
            0);
    }
    return OW_WILD_RECONCILE_COMPLETE;
}

static BOOL OverworldWildHelper_RemoveEncounter(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    LocalMapObject *verifiedObject = NULL;
    OverworldWildDespawnAuthorization authorization =
        OverworldWildHelper_AuthorizeDespawn(
            fieldSystem,
            state,
            presentation,
            slot,
            expectedGeneration,
            reason,
            &verifiedObject);

    OverworldWildHelper_RecordDespawnEvent(
        fieldSystem,
        state,
        presentation,
        telemetry,
        slot,
        reason,
        authorization == OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT
            ? OW_WILD_DESPAWN_ACTION_DELETE_OBJECT
            : authorization == OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY
                ? OW_WILD_DESPAWN_ACTION_CLEAR_LOGICAL_ONLY
                : OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED,
        distance);
    if (authorization == OW_WILD_DESPAWN_DENIED || resetSlot == NULL) {
        return FALSE;
    }
    resetSlot(state, slot, TRUE);
    if (verifiedObject != NULL) {
        DeleteMapObject(verifiedObject);
    }
    return TRUE;
}

static void OverworldWildHelper_DespawnFarEncounters(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    u16 movementProtectedMask,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u8 distance;
        BOOL movementProtected = (movementProtectedMask & (1u << i)) != 0
            || state->movementSpawnRunActive[i];

        if (OverworldWildHelper_ConfirmDistanceDespawn(
                fieldSystem,
                state,
                presentation,
                i,
                movementProtected,
                &distance)) {
            (void)OverworldWildHelper_RemoveEncounter(
                fieldSystem,
                state,
                presentation,
                telemetry,
                i,
                state->spawns[i].encounterGeneration,
                OW_WILD_DESPAWN_REASON_DISTANCE,
                distance,
                resetSlot);
        }
    }
}

static u8 OverworldWildHelper_FinishBattle(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    u16 battleResult,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    u8 disposition = OverworldWildHelper_ClassifyBattleResult(
        fieldSystem,
        state,
        battleResult);

    if (disposition == OW_WILD_BATTLE_DISPOSITION_DEFEATED
        || disposition == OW_WILD_BATTLE_DISPOSITION_CAUGHT) {
        (void)OverworldWildHelper_RemoveEncounter(
            fieldSystem,
            state,
            presentation,
            telemetry,
            state->pendingSlot,
            state->pendingEncounterGeneration,
            disposition == OW_WILD_BATTLE_DISPOSITION_DEFEATED
                ? OW_WILD_DESPAWN_REASON_BATTLE_DEFEATED
                : OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
            0,
            resetSlot);
    }
    return disposition;
}

static LocalMapObject *OverworldWildHelper_CreatePresentationObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    int x,
    int y,
    u8 facing,
    u8 movementBehavior,
    u8 range)
{
    OverworldWildSpawn *spawn = &state->spawns[slot];
    u32 spriteId = OVERWORLD_WILD_SPAWN_METADATA_ENTRY->getSpriteId(
        spawn->species,
        spawn->form);
    LocalMapObject *object;

    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    object = CreateSpecialFieldObjectWithParams(
        fieldSystem->mapObjectMan,
        x,
        y,
        facing,
        spriteId,
        OW_WILD_MOVE_STOCK_IDLE,
        fieldSystem->location->mapId,
        0,
        movementBehavior,
        OW_WILD_HELPER_PAL_PARAM_ENABLE
            | (spawn->shiny ? OW_WILD_HELPER_PAL_PARAM_SHINY : 0));
    if (object == NULL) {
        return NULL;
    }
    MapObject_SetID(object, OW_WILD_OBJECT_ID_START + slot);
    MapObject_SetScript(object, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT);
    MapObject_SetXRange(object, range);
    MapObject_SetYRange(object, range);
    OVERWORLD_WILD_SPAWN_METADATA_ENTRY->applyRenderParams(
        object,
        spawn->species,
        spawn->form,
        spriteId,
        spawn->shiny);
    object->facingInit = facing;
    object->curFacing = facing;
    object->nextFacing = facing;
    object->curFacingBak = facing;
    object->nextFacingBak = facing;
    MapObject_SetCurrentX(object, (u32)x);
    MapObject_SetCurrentY(object, (u32)y);
    object->xInit = x;
    object->yInit = y;
    object->xPrev = x;
    object->yPrev = y;
    object->posVec[0] = (u32)((s32)x * 0x10000 + 0x8000);
    object->posVec[2] = (u32)((s32)y * 0x10000 + 0x8000);
    object->flags = (object->flags & ~(BIT_VANISH | MAPOBJECTFLAG_UNK8))
        | MAPOBJECTFLAG_KEEP;
    return object;
}

static BOOL OverworldWildHelper_ValidateDeferredBattle(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    u16 encounterGeneration)
{
    return state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->pendingSlot == slot
        && state->pendingMapGeneration == state->mapGeneration
        && state->pendingEncounterGeneration == encounterGeneration
        && state->pendingPersonality == state->spawns[slot].personality
        && state->spawns[slot].encounterGeneration == encounterGeneration
        && OverworldWildHelper_IsExactObject(fieldSystem, state, slot);
}

static void OverworldWildHelper_AppendFleeFallbackDirections(
    u8 *directions,
    int *directionCount,
    int fleeDx,
    int fleeDy)
{
    static const u8 baseDirections[] = {
        OW_WILD_HELPER_DIRECTION_UP,
        OW_WILD_HELPER_DIRECTION_RIGHT,
        OW_WILD_HELPER_DIRECTION_DOWN,
        OW_WILD_HELPER_DIRECTION_LEFT,
    };
    static const s8 directionDeltas[][2] = {
        {0, -1},
        {0, 1},
        {-1, 0},
        {1, 0},
    };
    int start;

    if (directions == NULL
        || directionCount == NULL
        || *directionCount >= 4
        || (fleeDx == 0 && fleeDy == 0)) {
        return;
    }
    if (*directionCount < 0) {
        *directionCount = 0;
    }

    start = gf_rand() % 4;
    while (*directionCount < 4) {
        int bestDirection = -1;
        int bestScore;
        int i;

        for (i = 0; i < 4; i++) {
            u8 direction = baseDirections[(start + i) % 4];
            int score;
            int j;

            for (j = 0; j < *directionCount; j++) {
                if (directions[j] == direction) {
                    break;
                }
            }
            if (j < *directionCount) {
                continue;
            }

            score = directionDeltas[direction][0] * fleeDx
                + directionDeltas[direction][1] * fleeDy;
            if (bestDirection < 0 || score > bestScore) {
                bestDirection = direction;
                bestScore = score;
            }
        }

        directions[*directionCount] = (u8)bestDirection;
        (*directionCount)++;
    }
}

#define OW_WILD_HELPER_OVERLAY_ENTRY_INITIALIZER { \
    OVERWORLD_WILD_HELPER_OVERLAY_MAGIC, \
    OVERWORLD_WILD_HELPER_OVERLAY_VERSION, \
    sizeof(OverworldWildHelperOverlayEntry), \
    OverworldWildHelper_TryPrepareSpawn, \
    OverworldWildHelper_TryPrepareEncounterSpawn, \
    OverworldWildHelper_PickRandomBehaviorHop, \
    OverworldWildHelper_PlanBehaviorHopStep, \
    OverworldWildHelper_IsPresentationContextCurrent, \
    OverworldWildHelper_NormalizeThrowPresentation, \
    OverworldWildHelper_SyncCarriedThrowTarget, \
    OverworldWildHelper_ReconcilePresentations, \
    OverworldWildHelper_DespawnFarEncounters, \
    OverworldWildHelper_FinishBattle, \
    OverworldWildHelper_CreatePresentationObject, \
    OverworldWildHelper_ValidateDeferredBattle, \
    NULL, \
    NULL, \
    OverworldWildHelper_TickPlayerBallProjectile, \
    OverworldWildHelper_CancelPlayerBallProjectile, \
    OverworldWildHelper_GetPlayerBallProjectileObject, \
    OverworldWildHelper_CleanupResidentData, \
    OverworldWildHelper_ClearPickupThrowState, \
    OverworldWildHelper_QueryPickupThrowTarget, \
    OverworldWildHelper_TryStartPickupThrowAction, \
    OverworldWildHelper_StartCarriedThrowTarget, \
    OverworldWildHelper_CalculatePlayerBallShakes, \
    OverworldWildHelper_FindBattleTalkSlot, \
}

static const OverworldWildHelperOverlayEntry sOverworldWildHelperExpectedOverlayEntry =
    OW_WILD_HELPER_OVERLAY_ENTRY_INITIALIZER;

static BOOL OverworldWildHelper_EntriesMatch(
    const volatile u32 *actual,
    const u32 *expected,
    u32 wordCount) __attribute__((noinline, noclone));
static BOOL OverworldWildHelper_EntriesMatch(
    const volatile u32 *actual,
    const u32 *expected,
    u32 wordCount)
{
    u32 i;

    for (i = 0; i < wordCount; i++) {
        if (actual[i] != expected[i]) {
            return FALSE;
        }
    }
    return TRUE;
}

static BOOL OverworldWildHelper_IsBehaviorOverlayAuthenticated(BOOL warmLearnsets)
    __attribute__((noinline, noclone));
typedef u32 OverworldWildHelperAliasU32 __attribute__((may_alias));
static BOOL OverworldWildHelper_IsBehaviorOverlayAuthenticated(BOOL warmLearnsets)
{
    const OverworldWildBehaviorOverlayEntry *entry =
        OVERWORLD_WILD_BEHAVIOR_OVERLAY_ENTRY;

    if (entry->magic != OVERWORLD_WILD_BEHAVIOR_OVERLAY_MAGIC
        || *(const OverworldWildHelperAliasU32 *)&entry->version
            != ((u32)sizeof(*entry) << 16
                | OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION)) {
        return FALSE;
    }
    if (!OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE()) {
        return FALSE;
    }
    if (warmLearnsets) {
        /* Failure is safe: the resident dispatch remains on its fallback. */
        OVERWORLD_WILD_LEARNSET_CACHE_ENTRY->warm();
    }
    return TRUE;
}

static BOOL OverworldWildHelper_ValidateOverlay(u32 behaviorMode)
    __attribute__((section(".overworld_wild_helper_validate"), noinline, used));
static BOOL OverworldWildHelper_ValidateOverlay(u32 behaviorMode)
{
    const volatile u32 *actual =
        (const volatile u32 *)OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR;
    const u32 *expected =
        (const u32 *)&sOverworldWildHelperExpectedOverlayEntry;

    if (!OverworldWildHelper_EntriesMatch(
            actual,
            expected,
            sizeof(OverworldWildHelperOverlayEntry) / sizeof(u32))) {
        return FALSE;
    }
    if (behaviorMode == OVERWORLD_WILD_HELPER_VALIDATE_ONLY) {
        return TRUE;
    }
    if (behaviorMode == OVERWORLD_WILD_HELPER_OWNED_BEHAVIOR) {
        return OverworldWildHelper_IsBehaviorOverlayAuthenticated(FALSE);
    }
    if (!CanOverlayBeLoaded(OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)) {
        return FALSE;
    }
    if (OverworldWildHelper_IsBehaviorOverlayAuthenticated(TRUE)) {
        return TRUE;
    }
    if (behaviorMode == OVERWORLD_WILD_HELPER_REQUIRE_BEHAVIOR) {
        return FALSE;
    }
    if (!LoadOverlayNormal(0, OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)) {
        return FALSE;
    }
    if (OverworldWildHelper_IsBehaviorOverlayAuthenticated(TRUE)) {
        return TRUE;
    }
    if (FS_UnloadOverlay(0, OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)) {
        *(u32 *)OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR = 0;
    }
    return FALSE;
}

static BOOL OverworldWildHelper_OverlayLifecycle(
    u32 lifecycleMode,
    FieldSystem *fieldSystem)
    __attribute__((section(".overworld_wild_helper_lifecycle"), noinline, used));
static BOOL OverworldWildHelper_OverlayLifecycle(
    u32 lifecycleMode,
    FieldSystem *fieldSystem)
{
    if (lifecycleMode == OVERWORLD_WILD_HELPER_LIFECYCLE_PREPARE_CLEANUP) {
        if (!OverworldWildHelper_ValidateOverlay(
                OVERWORLD_WILD_HELPER_VALIDATE_ONLY)) {
            return FALSE;
        }
        OVERWORLD_WILD_HELPER_OVERLAY_ENTRY->cleanupResidentData(fieldSystem);
        return TRUE;
    }
    if (lifecycleMode == OVERWORLD_WILD_HELPER_LIFECYCLE_FINISH_UNOWNED) {
        return TRUE;
    }
    if (lifecycleMode != OVERWORLD_WILD_HELPER_LIFECYCLE_FINISH_OWNED
        || !CanOverlayBeLoaded(OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)
        || !OverworldWildHelper_IsBehaviorOverlayAuthenticated(FALSE)) {
        return FALSE;
    }
    return UnloadOverworldWildBehaviorOverlay();
}

typedef char OverworldWildHelperOverlayEntrySizeMustRemain104Bytes[
    sizeof(OverworldWildHelperOverlayEntry) == 104 ? 1 : -1];

const OverworldWildHelperOverlayEntry gOverworldWildHelperOverlayEntry
    __attribute__((section(".overworld_wild_helper_entry"), used)) =
        OW_WILD_HELPER_OVERLAY_ENTRY_INITIALIZER;

const OverworldWildHelperFleeFallbackEntry gOverworldWildHelperFleeFallbackEntry
    __attribute__((section(".overworld_wild_helper_flee_fallback_entry"), used)) = {
        OverworldWildHelper_AppendFleeFallbackDirections,
    };

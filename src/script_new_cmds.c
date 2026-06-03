#include "../include/types.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns.h"
#include "../include/script.h"
#include "../include/sound.h"
#include "../include/repel.h"
#include "../include/constants/file.h"
#include "../include/constants/maps.h"
#include "../include/constants/sndseq.h"
#include "../include/constants/species.h"

#define SCRIPT_NEW_CMD_REPEL_USE    0
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE 1
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP 2
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP 3
#define SCRIPT_NEW_CMD_SOUND_TEST_GET_ID 4
#define SCRIPT_NEW_CMD_SOUND_TEST_ACTION 5
#define SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP_SOUND 6

#define SCRIPT_NEW_CMD_MAX          256
#define SOUND_TEST_SE_MIN           SEQ_SE_PL_W012
#define SOUND_TEST_SE_MAX           (SEQ_SE_END - 1)
#define SOUND_TEST_SE_COUNT         (SOUND_TEST_SE_MAX - SOUND_TEST_SE_MIN + 1)
#define SOUND_TEST_ACTION_PLAY      0
#define SOUND_TEST_ACTION_NEXT      1
#define SOUND_TEST_ACTION_PREVIOUS  2
#define SOUND_TEST_ACTION_FORWARD   3
#define SOUND_TEST_ACTION_BACK      4
#define VAR_BATTLE_RESULT           0x4013
#define SCRIPT_CMD_PLAY_CRY         76
#define SCRIPT_CMD_WAIT_CRY         77
#define SCRIPT_CMD_RUN_NEW_COMMAND  208
#define SCRIPT_CMD_FADE_SCREEN      174
#define SCRIPT_CMD_WAIT_FADE        175
#define SCRIPT_CMD_WARP             176
#define SCRIPT_CMD_RELEASE_ALL      97
#define SCRIPT_CMD_END              2
#define OW_WILD_MEW_WARP_NONE       0xFFFF
#define OW_WILD_MEW_WARP_DIR_NORTH  0
#define OW_WILD_MEW_WARP_DIR_SOUTH  1
#define OW_WILD_MEW_WARP_DIR_WEST   2
#define OW_WILD_MEW_WARP_DIR_EAST   3
#define OW_WILD_MEW_WARP_SOUND      SEQ_SE_PL_BREC03
#define OW_WILD_MEW_WARP_FLASH_COLOR 0x7FFF
#define OW_WILD_MEW_WARP_RETRY_COUNT 16
#define OW_WILD_MEW_WARP_FALLBACK_MAP MAP_T21PC0101
#define OW_WILD_MEW_WARP_FALLBACK_X 7
#define OW_WILD_MEW_WARP_FALLBACK_Z 7
#define OW_WILD_MEW_BG_EVENT_SIZE 20
#define OW_WILD_MEW_OBJECT_EVENT_SIZE 32
#define OW_WILD_MEW_WARP_EVENT_SIZE 12
#define OW_WILD_BATTLE_SCRIPT_SPECIES_OFFSET 2
#define OW_WILD_BATTLE_SCRIPT_LEVEL_OFFSET 4
#define OW_WILD_BATTLE_SCRIPT_SHINY_OFFSET 6

typedef struct OverworldWildMewWarpEvent {
    u16 x;
    u16 z;
    u16 header;
    u16 anchor;
    u32 height;
} OverworldWildMewWarpEvent;

static u8 sOverworldWildBattleScript[] = {
    0x4D, 0x02, // wild_battle
    0x13, 0x00, // species fallback: Rattata
    0x04, 0x00, // level fallback: 4
    0x00,       // shiny
    0xD0, 0x00, // RunNewCommand
    SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP,
    0x00, 0x00,
    0x61, 0x00, // releaseall
    0x02, 0x00, // end
};

static u8 sOverworldWildMewWarpScript[] = {
    SCRIPT_CMD_PLAY_CRY & 0xFF, SCRIPT_CMD_PLAY_CRY >> 8,
    SPECIES_MEW & 0xFF, SPECIES_MEW >> 8,
    0x00, 0x00,
    SCRIPT_CMD_WAIT_CRY & 0xFF, SCRIPT_CMD_WAIT_CRY >> 8,
    SCRIPT_CMD_RUN_NEW_COMMAND & 0xFF, SCRIPT_CMD_RUN_NEW_COMMAND >> 8,
    SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP_SOUND,
    0x00, 0x00,
    SCRIPT_CMD_FADE_SCREEN & 0xFF, SCRIPT_CMD_FADE_SCREEN >> 8,
    0x06, 0x00,
    0x01, 0x00,
    0x00, 0x00,
    OW_WILD_MEW_WARP_FLASH_COLOR & 0xFF, OW_WILD_MEW_WARP_FLASH_COLOR >> 8,
    SCRIPT_CMD_WAIT_FADE & 0xFF, SCRIPT_CMD_WAIT_FADE >> 8,
    SCRIPT_CMD_WARP & 0xFF, SCRIPT_CMD_WARP >> 8,
    MAP_T21PC0101 & 0xFF, MAP_T21PC0101 >> 8,
    OW_WILD_MEW_WARP_NONE & 0xFF, OW_WILD_MEW_WARP_NONE >> 8,
    0x07, 0x00,
    0x07, 0x00,
    OW_WILD_MEW_WARP_DIR_SOUTH & 0xFF, OW_WILD_MEW_WARP_DIR_SOUTH >> 8,
    SCRIPT_CMD_FADE_SCREEN & 0xFF, SCRIPT_CMD_FADE_SCREEN >> 8,
    0x06, 0x00,
    0x01, 0x00,
    0x01, 0x00,
    OW_WILD_MEW_WARP_FLASH_COLOR & 0xFF, OW_WILD_MEW_WARP_FLASH_COLOR >> 8,
    SCRIPT_CMD_WAIT_FADE & 0xFF, SCRIPT_CMD_WAIT_FADE >> 8,
    SCRIPT_CMD_RELEASE_ALL & 0xFF, SCRIPT_CMD_RELEASE_ALL >> 8,
    SCRIPT_CMD_END & 0xFF, SCRIPT_CMD_END >> 8,
};

static u16 sSoundTestSeqId = SOUND_TEST_SE_MIN;

static const u8 sOverworldWildMewMapWarpCounts[] = {
     0,  0,  0,  0,  0,  0,  2,  4,  2,  1,  4,  3,  2,  2,  0,  3,
     3,  3,  0,  0,  2,  2,  0,  4,  2,  0,  1,  4,  3,  3,  2,  2,
     3,  4,  1,  3,  4,  6,  0,  2,  2,  6,  6,  1,  1,  3,  3,  7,
     6,  8,  7,  8,  7, 11,  1,  2, 17,  5,  1,  1,  2,  1,  1,  2,
     5,  1,  2,  1,  1,  1, 11,  8,  8, 17,  9, 12,  1,  1,  3,  0,
     2,  1,  1,  1,  6,  2,  8,  2,  2,  2,  0,  2,  4,  7,  2,  2,
     8,  2,  2,  3,  2,  2,  0,  8,  6,  6,  2,  7,  3,  2, 17,  2,
     3,  2,  6, 10, 11,  4, 10,  7,  2,  3,  2,  3,  1,  0,  0,  1,
     2,  1,  2,  1,  2,  1,  1,  1,  1,  1,  2,  1,  1, 15,  6,  6,
     2,  1,  7,  0,  5,  5,  4,  1,  1,  2,  1,  1,  1,  1,  1,  1,
     2,  1,  1,  2,  1,  2,  2,  3,  3,  3,  2,  9,  6,  1,  2,  1,
     1,  1,  2,  2,  3,  4,  3,  1,  3,  3,  3,  3,  3,  2,  3,  0,
     7,  2,  2,  2,  1,  1,  1,  1,  3,  2,  2,  2,  2,  1,  3,  1,
     6,  4,  3,  2,  2,  1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  6,
     6,  4,  3,  1, 14,  6,  1,  2,  2,  2,  5,  4, 10,  2,  4,  3,
     3,  0,  0, 16,  6,  0,  3,  3,  3,  3,  2,  4,  3,  1,  2,  2,
     2,  2,  1,  1,  1,  1,  1,  1,  2,  1,  1,  1,  1,  1,  4,  3,
     4,  4,  4,  4,  2,  1, 13,  1,  2,  2,  2,  2,  0,  2,  2,  2,
     0,  2,  0,  0,  1,  1,  4,  1,  1,  1,  1,  2,  3,  3,  1,  3,
     3,  7,  5,  3,  5,  6,  8,  1,  3,  9,  2,  2,  1,  1,  1,  1,
     1,  1,  1,  2,  1,  1,  1,  3,  3,  3,  3,  3,  2,  3,  2,  1,
     3,  1,  1,  1,  1,  1,  1,  2,  2,  1,  2,  2,  2,  2,  2,  1,
     1,  2,  2,  1,  1,  3,  0,  2,  1,  2,  1,  2,  1,  1, 31,  7,
     2,  2,  6,  1,  1,  2,  2,  2,  2,  3,  2,  2,  2,  1,  1,  2,
     1,  1,  1,  1,  1,  2,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  6,  3,  6,  4,  8,  6, 12, 14, 12,  1,  7,  3,  1,
     1,  7,  2,  1,  2,  1,  4,  4,  1,  1,  1,  1,  2,  1,  1,  1,
     1,  1,  1,  2,  1,  1,  1,  1,  7,  1,  2,  2,  2,  2,  1,  1,
     1,  1,  2,  1,  1,  2,  1,  2,  2,  1,  1,  1,  2,  1,  1,  2,
     1,  2,  2,  1,  0,  1,  1,  1,  1,  2,  1,  1,  1,  1,  1,  2,
     2,  1,  1,  1,  6,  1,  2,  1,  1,  1,  1,
};

static void Script_WriteHalfword(u8 *script, u32 offset, u16 value)
{
    script[offset] = value & 0xFF;
    script[offset + 1] = value >> 8;
}

static void Script_QueueOverworldWildBattle(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    u16 encodedSpecies = SPECIES_RATTATA;
    u8 level = 4;

    OverworldWildSpawns_PopPendingBattle(&encodedSpecies, &level);

    Script_WriteHalfword(sOverworldWildBattleScript, OW_WILD_BATTLE_SCRIPT_SPECIES_OFFSET, encodedSpecies);
    Script_WriteHalfword(sOverworldWildBattleScript, OW_WILD_BATTLE_SCRIPT_LEVEL_OFFSET, level);
    sOverworldWildBattleScript[OW_WILD_BATTLE_SCRIPT_SHINY_OFFSET] = 0;
    VarSet(ctx->fsys, VAR_BATTLE_RESULT, 0);
#endif

    ScriptJump(ctx, sOverworldWildBattleScript);
}

static void Script_QueueOverworldWildMewWarp(SCRIPTCONTEXT *ctx)
{
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    u16 mapId = OW_WILD_MEW_WARP_FALLBACK_MAP;
    u16 x = OW_WILD_MEW_WARP_FALLBACK_X;
    u16 z = OW_WILD_MEW_WARP_FALLBACK_Z;
    u32 attempt;

    for (attempt = 0; attempt < OW_WILD_MEW_WARP_RETRY_COUNT; attempt++) {
        u16 candidateMapId = gf_rand() % NELEMS(sOverworldWildMewMapWarpCounts);
        u8 warpCount = sOverworldWildMewMapWarpCounts[candidateMapId];

        if (warpCount != 0) {
            u32 bgEventCount;
            u32 objectEventCount;
            u32 warpOffset;
            OverworldWildMewWarpEvent warpEvent;

            mapId = candidateMapId;
            ArchiveDataLoadOfs(&bgEventCount, ARC_MAP_EVENTS, mapId, 0, sizeof(bgEventCount));
            ArchiveDataLoadOfs(&objectEventCount, ARC_MAP_EVENTS, mapId,
                sizeof(bgEventCount) + bgEventCount * OW_WILD_MEW_BG_EVENT_SIZE,
                sizeof(objectEventCount));

            warpOffset = sizeof(bgEventCount)
                + bgEventCount * OW_WILD_MEW_BG_EVENT_SIZE
                + sizeof(objectEventCount)
                + objectEventCount * OW_WILD_MEW_OBJECT_EVENT_SIZE
                + sizeof(u32)
                + (gf_rand() % warpCount) * OW_WILD_MEW_WARP_EVENT_SIZE;

            ArchiveDataLoadOfs(&warpEvent, ARC_MAP_EVENTS, mapId, warpOffset, sizeof(warpEvent));
            x = warpEvent.x;
            z = warpEvent.z;
            break;
        }
    }

    Script_WriteHalfword(sOverworldWildMewWarpScript, 27, mapId);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 29, OW_WILD_MEW_WARP_NONE);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 31, x);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 33, z);
    Script_WriteHalfword(sOverworldWildMewWarpScript, 35, gf_rand() % 4);
#endif

    ScriptJump(ctx, sOverworldWildMewWarpScript);
}

static void Script_SoundTestOffset(s16 offset)
{
    s32 nextSeqId = sSoundTestSeqId + offset;

    while (nextSeqId < SOUND_TEST_SE_MIN) {
        nextSeqId += SOUND_TEST_SE_COUNT;
    }

    while (nextSeqId > SOUND_TEST_SE_MAX) {
        nextSeqId -= SOUND_TEST_SE_COUNT;
    }

    sSoundTestSeqId = nextSeqId;
}

static void Script_SoundTestRunAction(u16 action)
{
    switch (action) {
        case SOUND_TEST_ACTION_PLAY:
            break;

        case SOUND_TEST_ACTION_NEXT:
            Script_SoundTestOffset(1);
            break;

        case SOUND_TEST_ACTION_PREVIOUS:
            Script_SoundTestOffset(-1);
            break;

        case SOUND_TEST_ACTION_FORWARD:
            Script_SoundTestOffset(10);
            break;

        case SOUND_TEST_ACTION_BACK:
            Script_SoundTestOffset(-10);
            break;

        default:
            return;
    }

    PlaySE(sSoundTestSeqId);
}

BOOL Script_RunNewCmd(SCRIPTCONTEXT *ctx) {
    u8 sw = ScriptReadByte(ctx);
    u16 UNUSED arg0 = ScriptReadHalfword(ctx);

    switch (sw) {
        case SCRIPT_NEW_CMD_REPEL_USE:;
#ifdef IMPLEMENT_REUSABLE_REPELS
            u16 most_recent_repel = Repel_GetMostRecent();
            SetScriptVar(arg0, most_recent_repel);
            Repel_Use(most_recent_repel, HEAPID_MAIN_HEAP);
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE:
            Script_QueueOverworldWildBattle(ctx);
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_BATTLE_CLEANUP:
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
            OverworldWildSpawns_CleanupPendingBattle(VarGet(ctx->fsys, VAR_BATTLE_RESULT));
#endif
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP:
            Script_QueueOverworldWildMewWarp(ctx);
            break;

        case SCRIPT_NEW_CMD_OVERWORLD_WILD_MEW_WARP_SOUND:
            PlaySE(OW_WILD_MEW_WARP_SOUND);
            break;

        case SCRIPT_NEW_CMD_SOUND_TEST_GET_ID:
            SetScriptVar(arg0, sSoundTestSeqId);
            break;

        case SCRIPT_NEW_CMD_SOUND_TEST_ACTION:
            Script_SoundTestRunAction(GetScriptVar(arg0));
            break;

        default: break;
    }

    return FALSE;
}

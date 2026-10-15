#include "../include/overworld_combat.h"

#include "../include/constants/species.h"
#include "../include/battle.h"
#include "../include/overworld_actor_system_internal.h"
#include "../include/overworld_follower_selector.h"
#include "../include/overworld_mount_internal.h"
#include "../include/overworld_wild_runtime_state_internal.h"
#include "../include/save.h"

#define COMBAT_CODE __attribute__((noinline, section(".overworld_combat_text")))
#define COMBAT_CRASH_CODE __attribute__((noinline, section(".player_health_tail")))
#define COMBAT_IV_CODE __attribute__((noinline, aligned(4), section(".player_health_tail_end")))
#define COMBAT_IMMUNITY_FRAMES 60
#define COMBAT_BATTLE_OUTCOME_PLAYER_FLED 5
#define COMBAT_BATTLE_FLAG_HP_TRACKING_ACTIVE 0x04
#define COMBAT_BATTLE_FLAG_HP_APPLIED 0x08
#define COMBAT_BATTLE_FLAG_HP_RECORDED 0x10

typedef struct OverworldCombatTarget {
    u32 personality;
    u16 mapId;
    u16 mapGeneration;
    u16 encounterGeneration;
    u16 species;
    u16 maxHp;
    u16 currentHp;
    u16 hitCount;
    u8 form;
    u8 level;
    u8 initialized;
    u8 immunityFrames;
    u8 knockbackOptions;
    u8 knockbackDirection;
    u8 knockbackPending;
    u8 lastDamage;
    /* Reuse the alignment pad. The accepted motion ID guards settlement. */
    u16 crashMotionIdentity;
} OverworldCombatTarget;

typedef char CombatTargetSizeMustRemain28[sizeof(OverworldCombatTarget) == 28 ? 1 : -1];

typedef struct OverworldCombatState {
    FieldSystem *fieldSystem;
    SaveData *saveData;
    const OverworldWildSpawnState *frameState;
    OverworldCombatTarget targets[OW_WILD_MAX_SPAWNS];
} OverworldCombatState;

static OverworldCombatState sCombat
    __attribute__((section(".overworld_combat_state"))) = {0};

typedef BOOL (*CombatAcquireMonLockFunc)(struct PartyPokemon *);
typedef BOOL (*CombatReleaseMonLockFunc)(struct PartyPokemon *, BOOL);
#define COMBAT_ACQUIRE_MON_LOCK ((CombatAcquireMonLockFunc)0x0206DD41)
#define COMBAT_RELEASE_MON_LOCK ((CombatReleaseMonLockFunc)0x0206DD8D)

void COMBAT_CODE OverworldCombat_Reset(void)
{
    u8 *cursor = (u8 *)&sCombat;
    u32 remaining = sizeof(sCombat);

    while (remaining-- != 0) {
        *cursor++ = 0;
    }
}

int COMBAT_IV_CODE OverworldCombat_HpIV(u32 personality)
{
    /* Only HP IV is stable. Other native stats keep their normal rolls.
     * This needs no extra spawn RNG or construction pass. */
    return personality & 31;
}

static BOOL COMBAT_CODE Combat_HasContext(
    const OverworldWildSpawnState *state, u8 slot)
{
    FieldSystem *fieldSystem;

    if (state == NULL || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    fieldSystem = state->movementFieldSystem;
    return fieldSystem != NULL && fieldSystem == gFieldSysPtr
        && fieldSystem->location != NULL && fieldSystem->savedata != NULL
        && state->mapId == fieldSystem->location->mapId
        && state->mapGeneration != 0 && state->spawns[slot].active
        && state->spawns[slot].encounterGeneration != 0
        && state->spawns[slot].mapId == state->mapId
        && state->spawns[slot].species != SPECIES_NONE
        && state->spawns[slot].level != 0;
}

static BOOL COMBAT_CODE Combat_Matches(
    const OverworldCombatTarget *target,
    const OverworldWildSpawnState *state, u8 slot)
{
    const OverworldWildSpawn *spawn = &state->spawns[slot];

    return target->initialized && target->personality == spawn->personality
        && target->mapId == spawn->mapId
        && target->mapGeneration == state->mapGeneration
        && target->encounterGeneration == spawn->encounterGeneration
        && target->species == spawn->species && target->form == spawn->form
        && target->level == spawn->level;
}

static struct PartyPokemon *COMBAT_CODE Combat_ReadPartyTarget(
    const OverworldWildSpawnState *state, u16 *hp, u16 *maxHp)
{
    const OverworldWildSpawn *spawn = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    struct Party *party = SaveData_GetPlayerPartyPtr(
        state->movementFieldSystem->savedata);
    struct PartyPokemon *pokemon;
    BOOL locked;
    BOOL matches;
    u8 partySlot = state->activeFollowerPartySlot;

    if (party == NULL || partySlot >= 6 || partySlot >= party->count) {
        return NULL;
    }
    pokemon = Party_GetMonByIndex(party, partySlot);
    if (pokemon == NULL) {
        return NULL;
    }
    locked = COMBAT_ACQUIRE_MON_LOCK(pokemon);
    matches = GetMonData(pokemon, MON_DATA_PERSONALITY, NULL)
            == spawn->personality
        && GetMonData(pokemon, MON_DATA_SPECIES, NULL) == spawn->species
        && GetMonData(pokemon, MON_DATA_FORM, NULL) == spawn->form
        && GetMonData(pokemon, MON_DATA_LEVEL, NULL) == spawn->level
        && GetMonData(pokemon, MON_DATA_IS_EGG, NULL) == FALSE;
    if (matches) {
        *hp = (u16)GetMonData(pokemon, MON_DATA_HP, NULL);
        *maxHp = (u16)GetMonData(pokemon, MON_DATA_MAXHP, NULL);
        matches = *maxHp != 0 && *hp <= *maxHp;
    }
    COMBAT_RELEASE_MON_LOCK(pokemon, locked);
    return matches ? pokemon : NULL;
}

static OverworldCombatTarget *COMBAT_CODE Combat_ReadTarget(
    const OverworldWildSpawnState *state, u8 slot,
    u16 *hp, u16 *maxHp, struct PartyPokemon **partyPokemon)
{
    const OverworldWildSpawn *spawn;
    OverworldCombatTarget *target;
    struct PartyPokemon *pokemon = NULL;
    u16 currentHp;
    u16 maximumHp;
    u32 baseHp;

    if (!Combat_HasContext(state, slot)) {
        return NULL;
    }
    if (sCombat.fieldSystem != state->movementFieldSystem
        || sCombat.saveData != state->movementFieldSystem->savedata) {
        OverworldCombat_Reset();
        sCombat.fieldSystem = state->movementFieldSystem;
        sCombat.saveData = state->movementFieldSystem->savedata;
    }
    target = &sCombat.targets[slot];
    spawn = &state->spawns[slot];
    if (slot == OW_WILD_FOLLOWER_SLOT) {
        pokemon = Combat_ReadPartyTarget(state, &currentHp, &maximumHp);
        if (pokemon == NULL) {
            return NULL;
        }
    } else {
        /* Map rebind resets combat state, but the same encounter's stat is
         * unchanged. Read current resident HP and publish fresh context below. */
        maximumHp = target->maxHp;
        if (maximumHp == 0 || target->personality != spawn->personality
            || target->encounterGeneration != spawn->encounterGeneration
            || target->species != spawn->species || target->form != spawn->form
            || target->level != spawn->level) {
            baseHp = PokeFormNoPersonalParaGet(
                spawn->species, spawn->form, PERSONAL_BASE_HP);
            maximumHp = spawn->species == SPECIES_SHEDINJA ? 1
                : (u16)(((baseHp * 2 + OverworldCombat_HpIV(spawn->personality))
                    * spawn->level) / 100 + spawn->level + 10);
        }
        currentHp = gOverworldWildResidentData.savedHp[slot];
        /* OW_WILD_HP_UNINITIALIZED clamps to max. Numeric zero remains a
         * fainted encounter after presentation or combat cache reset. */
        if (currentHp > maximumHp) {
            currentHp = maximumHp;
            gOverworldWildResidentData.savedHp[slot] = currentHp;
        }
    }
    if (!Combat_Matches(target, state, slot)) {
        target->personality = spawn->personality;
        target->mapId = spawn->mapId;
        target->mapGeneration = state->mapGeneration;
        target->encounterGeneration = spawn->encounterGeneration;
        target->species = spawn->species;
        target->form = spawn->form;
        target->level = spawn->level;
        target->initialized = TRUE;
        target->immunityFrames = 0;
        target->knockbackPending = FALSE;
        target->hitCount = 0;
        target->lastDamage = 0;
    }
    target->maxHp = maximumHp;
    target->currentHp = currentHp;
    *hp = currentHp;
    *maxHp = maximumHp;
    if (partyPokemon != NULL) {
        *partyPokemon = pokemon;
    }
    return target;
}

BOOL COMBAT_CODE OverworldCombat_ReadHp(
    const OverworldWildSpawnState *state, u8 slot, u16 *hp, u16 *maxHp)
{
    return hp != NULL && maxHp != NULL
        && Combat_ReadTarget(state, slot, hp, maxHp, NULL) != NULL;
}

void COMBAT_CODE OverworldCombat_BeginFrame(
    const OverworldWildSpawnState *state)
{
    u8 slot;

    if (state != NULL && state->movementFieldSystem != NULL
        && (sCombat.fieldSystem != state->movementFieldSystem
            || sCombat.saveData != state->movementFieldSystem->savedata)) {
        OverworldCombat_Reset();
        sCombat.fieldSystem = state->movementFieldSystem;
        sCombat.saveData = state->movementFieldSystem->savedata;
    }
    sCombat.frameState = state;
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; ++slot) {
        OverworldCombatTarget *target = &sCombat.targets[slot];

        if (!Combat_HasContext(state, slot)
            || !Combat_Matches(target, state, slot)) {
            target->initialized = FALSE;
            target->immunityFrames = 0;
            target->knockbackPending = FALSE;
        } else if (target->immunityFrames != 0) {
            --target->immunityFrames;
        }
    }
}

static BOOL COMBAT_CODE Combat_IsMounted(
    const OverworldWildSpawnState *state, u8 slot)
{
    const OverworldMountRuntimeState *mount =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;

    return slot == OW_WILD_FOLLOWER_SLOT
        && OVERWORLD_MOUNT_OVERLAY_ENTRY->magic == OVERWORLD_MOUNT_OVERLAY_MAGIC
        && OVERWORLD_MOUNT_OVERLAY_ENTRY->version == OVERWORLD_MOUNT_OVERLAY_VERSION
        && OVERWORLD_MOUNT_OVERLAY_ENTRY->size == sizeof(OverworldMountOverlayEntry)
        && mount->fieldSystem == state->movementFieldSystem
        && mount->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING;
}

static OverworldActorRuntimeSlot *COMBAT_CRASH_CODE Combat_CrashActor(
    const OverworldWildSpawnState *state, u8 slot)
{
    OverworldActorSystemState *actors =
        (OverworldActorSystemState *)OVERWORLD_ACTOR_SYSTEM_STATE_ADDR;
    OverworldCombatTarget *target = &sCombat.targets[slot];
    OverworldActorRuntimeSlot *runtime = &actors->slots[slot];
    OverworldActorStateSnapshot *actor = &runtime->snapshot;

    if (!Combat_HasContext(state, slot) || !Combat_Matches(target, state, slot)
        || !OverworldActorSystem_IsReady() || !actor->active
        || actor->handle.slot != slot || actor->subjectIdentity != target->personality
        || actor->species != target->species
        || actor->handle.mapGeneration != target->mapGeneration
        || actor->handle.encounterGeneration != target->encounterGeneration
        || actors->mapGeneration != target->mapGeneration
        || actor->handle.fieldEpoch != actors->fieldEpoch
        || ((target->knockbackPending & OVERWORLD_COMBAT_PENDING_SETTLE) != 0
            && (target->crashMotionIdentity != 0
                ? (runtime->motion.phase != OVERWORLD_MOTION_PHASE_SUSPENDED
                    || actor->motionPhase != OVERWORLD_MOTION_PHASE_SUSPENDED
                    || actor->reservationId != target->crashMotionIdentity
                    || runtime->motion.plan.reservationId != target->crashMotionIdentity
                    || runtime->motion.plan.fieldEpoch != actors->fieldEpoch)
                : (actor->motionPhase != OVERWORLD_MOTION_PHASE_IDLE
                    || actor->reservationId != 0)))
        || ((target->knockbackPending & OVERWORLD_COMBAT_PENDING_CRASH_MASK) != 0
            && actor->role != ((target->knockbackPending & OVERWORLD_COMBAT_PENDING_MOUNTED) != 0
                ? OVERWORLD_ACTOR_ROLE_MOUNTED
                : slot == OW_WILD_FOLLOWER_SLOT
                    ? OVERWORLD_ACTOR_ROLE_FOLLOWER : OVERWORLD_ACTOR_ROLE_WILD))) {
        return NULL;
    }
    return runtime;
}

void COMBAT_CRASH_CODE OverworldCombat_AcceptedHit(
    const OverworldWildSpawnState *state, u8 slot)
{
    OverworldCombatTarget *target;
    OverworldActorRuntimeSlot *runtime;
    OverworldActorWalkPolicyCall call = {0};
    u16 hp, maxHp;

    target = Combat_ReadTarget(state, slot, &hp, &maxHp, NULL);
    if (target == NULL || hp == 0
        || (target->knockbackPending & OVERWORLD_COMBAT_PENDING_CRASH_MASK) != 0
        || (runtime = Combat_CrashActor(state, slot)) == NULL) {
        return;
    }
    call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call.size = sizeof(call);
    call.actorSlot = slot;
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH;
    *(u16 *)(void *)&call.reserved[2] = runtime->snapshot.handle.fieldEpoch;
    if (OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy->reduceWalk(&call)
        && call.effect == OVERWORLD_ACTOR_WORLD_EFFECT_CRASH) {
        OverworldWildConditions_NotifyWorldEffect(
            state, &runtime->snapshot.handle, call.effect);
        target->crashMotionIdentity = *(u16 *)(void *)call.reserved;
        target->knockbackPending |= OVERWORLD_COMBAT_PENDING_SETTLE;
        if (runtime->snapshot.role == OVERWORLD_ACTOR_ROLE_MOUNTED) {
            target->knockbackPending |= OVERWORLD_COMBAT_PENDING_MOUNTED;
        }
    }
}

BOOL __attribute__((noinline, section(".player_health_extended_text")))
OverworldCombat_MountedCrashPending(FieldSystem *fieldSystem)
{
    return sCombat.fieldSystem == fieldSystem
        && (sCombat.targets[OW_WILD_FOLLOWER_SLOT].knockbackPending
            & OVERWORLD_COMBAT_PENDING_CRASH_MASK) != 0
        && (sCombat.targets[OW_WILD_FOLLOWER_SLOT].knockbackPending
            & OVERWORLD_COMBAT_PENDING_MOUNTED) != 0;
}

BOOL COMBAT_CODE OverworldCombat_TryHit(
    const OverworldWildSpawnState *state, u8 slot, u8 damage,
    u8 knockbackOptions, u8 direction)
{
    OverworldCombatTarget *target;
    struct PartyPokemon *pokemon;
    u16 hp;
    u16 maxHp;
    u16 hitLimit;
    u8 dealtDamage;

    if (sCombat.frameState != state || damage == 0 || damage > 50) {
        return FALSE;
    }
    target = Combat_ReadTarget(state, slot, &hp, &maxHp, &pokemon);
    if (target == NULL || hp == 0 || target->immunityFrames != 0) {
        return FALSE;
    }
    hitLimit = maxHp / 2;
    if (hitLimit == 0) {
        hitLimit = 1;
    }
    if (damage > hitLimit) {
        damage = (u8)hitLimit;
    }
    dealtDamage = damage >= hp ? (u8)hp : damage;
    hp -= dealtDamage;
    if (pokemon != NULL) {
        SetMonData(pokemon, MON_DATA_HP, &hp);
        OverworldFollowerSelector_SetPartySnapshotDirty();
    } else {
        gOverworldWildResidentData.savedHp[slot] = hp;
    }
    target->immunityFrames = COMBAT_IMMUNITY_FRAMES;
    target->currentHp = hp;
    ++target->hitCount;
    target->lastDamage = dealtDamage;
    OverworldCombat_AcceptedHit(state, slot);
    if (hp != 0 && !Combat_IsMounted(state, slot)
        && direction < 4
        && OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(knockbackOptions)
            >= OW_WILD_BEHAVIOR_KNOCKBACK_SLIDE
        && OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(knockbackOptions)
            <= OW_WILD_BEHAVIOR_KNOCKBACK_JUMP
        && OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(knockbackOptions) >= 1
        && OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(knockbackOptions) <= 7) {
        target->knockbackOptions = knockbackOptions;
        target->knockbackDirection = direction;
        target->knockbackPending |= OVERWORLD_COMBAT_PENDING_KNOCKBACK;
    }
    return TRUE;
}

u8 __attribute__((noinline, section(".overworld_combat_prepare"))) OverworldCombat_Prepare(
    const OverworldWildSpawnState *state, u8 slot, OverworldMotionPlan *plan)
{
    OverworldCombatTarget *target;
    u16 hp;
    u16 maxHp;
    OverworldActorPolicyView policy;
    BOOL urgent = (slot & OVERWORLD_COMBAT_PROBE_URGENT) != 0;

    slot &= ~OVERWORLD_COMBAT_PROBE_URGENT;
    if (urgent && plan != NULL) {
        return OVERWORLD_COMBAT_NONE;
    }
    /* Urgent probes do no party reads before an old engine motion ticks. */
    target = slot < OW_WILD_MAX_SPAWNS ? &sCombat.targets[slot] : NULL;
    if (target != NULL
        && (target->knockbackPending & OVERWORLD_COMBAT_PENDING_CRASH_MASK) != 0) {
        OverworldActorRuntimeSlot *runtime = Combat_CrashActor(state, slot);
        if (runtime == NULL) {
            target->knockbackPending &= OVERWORLD_COMBAT_PENDING_KNOCKBACK;
            target->crashMotionIdentity = 0;
        } else {
            if (plan != NULL) {
                *plan = target->crashMotionIdentity != 0
                    ? runtime->motion.plan : (OverworldMotionPlan){0};
            }
            return (target->knockbackPending & OVERWORLD_COMBAT_PENDING_SETTLE) != 0
                ? OVERWORLD_COMBAT_CRASH_SETTLE : OVERWORLD_COMBAT_CRASH_PLAYING;
        }
    }
    if (urgent) {
        return OVERWORLD_COMBAT_NONE;
    }
    target = Combat_ReadTarget(state, slot, &hp, &maxHp, NULL);
    if (target == NULL) {
        return OVERWORLD_COMBAT_NONE;
    }
    if (hp == 0) {
        target->knockbackPending = FALSE;
        return OVERWORLD_COMBAT_FAINTED;
    }
    if ((target->knockbackPending & OVERWORLD_COMBAT_PENDING_KNOCKBACK) == 0 || plan == NULL
        || Combat_IsMounted(state, slot)) {
        return OVERWORLD_COMBAT_NONE;
    }
    if (OverworldActorPolicy_Inspect(slot, &policy)
        && policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE
        && policy.motionPhase != OVERWORLD_MOTION_PHASE_CANCELED) {
        *plan = (OverworldMotionPlan){0};
        return OVERWORLD_COMBAT_KNOCKBACK;
    }
    if (OverworldCombat_Plan(state->movementFieldSystem,
            state->spawns[slot].object, target->knockbackOptions,
            target->knockbackDirection, plan)) {
        return OVERWORLD_COMBAT_KNOCKBACK;
    }
    *plan = (OverworldMotionPlan){0};
    return OVERWORLD_COMBAT_KNOCKBACK;
}

void COMBAT_CODE OverworldCombat_Acknowledge(
    const OverworldWildSpawnState *state, u8 slot)
{
    if (Combat_HasContext(state, slot)
        && Combat_Matches(&sCombat.targets[slot], state, slot)) {
        OverworldCombatTarget *target = &sCombat.targets[slot];
        if ((target->knockbackPending & OVERWORLD_COMBAT_PENDING_SETTLE) != 0) {
            OverworldActorRuntimeSlot *runtime = Combat_CrashActor(state, slot);
            OverworldActorWalkPolicyCall call = {0};
            if (runtime == NULL) {
                return;
            }
            if (target->crashMotionIdentity != 0) {
                call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
                call.size = sizeof(call);
                call.actorSlot = slot;
                call.operation = OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH;
                call.flags = OVERWORLD_ACTOR_WALK_HIT_CRASH_SETTLE;
                *(u16 *)(void *)call.reserved = target->crashMotionIdentity;
                *(u16 *)(void *)&call.reserved[2] = runtime->snapshot.handle.fieldEpoch;
                if (!OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy->reduceWalk(&call)) {
                    return;
                }
            } else if (runtime->snapshot.motionPhase != OVERWORLD_MOTION_PHASE_IDLE
                || runtime->snapshot.reservationId != 0) {
                return;
            }
            target->knockbackPending ^= OVERWORLD_COMBAT_PENDING_SETTLE | OVERWORLD_COMBAT_PENDING_CRASH;
        } else if ((target->knockbackPending & OVERWORLD_COMBAT_PENDING_CRASH) != 0) {
            target->knockbackPending &= OVERWORLD_COMBAT_PENDING_KNOCKBACK;
            target->crashMotionIdentity = 0;
        } else {
            target->knockbackPending = FALSE;
        }
    }
}

static int COMBAT_CODE Combat_BattleTargetSlot(u32 personality)
{
    const OverworldWildSpawnState *state = &sOverworldWildSpawnState;
    int slot = state->pendingSlot;

    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || !state->spawns[slot].active
        || state->pendingPersonality != personality
        || state->spawns[slot].personality != personality
        || state->pendingMapGeneration == 0
        || state->pendingMapGeneration != state->mapGeneration
        || state->pendingEncounterGeneration == 0
        || state->pendingEncounterGeneration
            != state->spawns[slot].encounterGeneration) {
        return -1;
    }
    return slot;
}

u16 COMBAT_CODE OverworldCombat_BattleHp(u32 personality)
{
    int slot = Combat_BattleTargetSlot(personality);
    u16 hp;
    u16 maxHp;

    if (slot < 0 || !OverworldCombat_ReadHp(&sOverworldWildSpawnState,
            (u8)slot, &hp, &maxHp)) {
        return 0;
    }
    return hp;
}

void COMBAT_CODE OverworldCombat_BattleSync(
    struct BattleSystem *bsys, struct BattleStruct *ctx, u8 battler, u16 hp)
{
    struct PartyPokemon *pokemon;
    struct BattlePokemon *battlePokemon;
    u16 maxHp;

    if (bsys == NULL || ctx == NULL || battler >= bsys->maxBattlers
        || battler >= CLIENT_MAX || ctx->sel_mons_no[battler] >= 6) {
        return;
    }
    pokemon = BattleWorkPokemonParamGet(bsys, battler,
        ctx->sel_mons_no[battler]);
    battlePokemon = &ctx->battlemon[battler];
    if (pokemon == NULL || GetMonData(pokemon, MON_DATA_PERSONALITY, NULL)
            != battlePokemon->personal_rnd) {
        return;
    }
    maxHp = (u16)GetMonData(pokemon, MON_DATA_MAXHP, NULL);
    if (maxHp == 0) {
        return;
    }
    if (hp > maxHp) {
        hp = maxHp;
    }
    if (hp > battlePokemon->maxhp) {
        hp = (u16)battlePokemon->maxhp;
    }
    SetMonData(pokemon, MON_DATA_HP, &hp);
    battlePokemon->hp = hp;
}

static u8 COMBAT_CODE Combat_FindTrackedEnemy(
    struct BattleSystem *bsys, struct BattleStruct *ctx, u32 personality)
{
    u8 battler;

    for (battler = BATTLER_ENEMY;
        battler < bsys->maxBattlers && battler < CLIENT_MAX; battler += 2) {
        if (ctx->battlemon[battler].personal_rnd == personality) {
            return battler;
        }
    }
    return CLIENT_MAX;
}

void COMBAT_CODE OverworldCombat_BattleUpdate(
    struct BattleSystem *bsys, struct BattleStruct *ctx,
    u8 battleOutcome, u32 personality)
{
    struct BattlePokemon *mon;
    u16 hp;
    u8 battler;
    int slot;

    if (bsys == NULL || ctx == NULL
        || (gOverworldWildResidentData.battleFlags
            & COMBAT_BATTLE_FLAG_HP_TRACKING_ACTIVE) == 0) {
        return;
    }
    battler = Combat_FindTrackedEnemy(bsys, ctx, personality);
    if ((gOverworldWildResidentData.battleFlags
            & COMBAT_BATTLE_FLAG_HP_APPLIED) == 0
        && ctx->server_seq_no >= CONTROLLER_COMMAND_SELECTION_SCREEN_INIT) {
        hp = OverworldCombat_BattleHp(personality);
        if (hp == 0) {
            gOverworldWildResidentData.battleFlags |= COMBAT_BATTLE_FLAG_HP_APPLIED;
        } else if (battler < CLIENT_MAX) {
            mon = &ctx->battlemon[battler];
            if (hp > mon->maxhp) {
                hp = (u16)mon->maxhp;
            }
            if (hp != 0) {
                OverworldCombat_BattleSync(bsys, ctx, battler, hp);
                gOverworldWildResidentData.battleFlags |= COMBAT_BATTLE_FLAG_HP_APPLIED;
            }
        }
    }
    if ((gOverworldWildResidentData.battleFlags
            & COMBAT_BATTLE_FLAG_HP_RECORDED) == 0
        && battleOutcome == COMBAT_BATTLE_OUTCOME_PLAYER_FLED
        && battler < CLIENT_MAX) {
        mon = &ctx->battlemon[battler];
        hp = mon->hp > mon->maxhp ? (u16)mon->maxhp : (u16)mon->hp;
        slot = Combat_BattleTargetSlot(personality);
        if (hp != 0 && mon->maxhp != 0 && slot >= 0) {
            gOverworldWildResidentData.savedHp[slot] = hp;
            if (Combat_Matches(&sCombat.targets[slot],
                    &sOverworldWildSpawnState, (u8)slot)) {
                sCombat.targets[slot].currentHp = hp;
            }
            gOverworldWildResidentData.battleFlags |= COMBAT_BATTLE_FLAG_HP_RECORDED;
        }
    }
}

void COMBAT_CODE OverworldCombat_CaptureHp(
    const OverworldWildSpawnState *state, u8 slot, struct PartyPokemon *pokemon)
{
    u32 hpIV;
    u16 hp;
    u16 maxHp;

    if (pokemon == NULL || slot == OW_WILD_FOLLOWER_SLOT
        || !OverworldCombat_ReadHp(state, slot, &hp, &maxHp)
        || GetMonData(pokemon, MON_DATA_PERSONALITY, NULL)
            != state->spawns[slot].personality) {
        return;
    }
    hpIV = OverworldCombat_HpIV(state->spawns[slot].personality);
    SetMonData(pokemon, MON_DATA_HP_IV, &hpIV);
    RecalcPartyPokemonStats(pokemon);
    maxHp = (u16)GetMonData(pokemon, MON_DATA_MAXHP, NULL);
    if (hp > maxHp) {
        hp = maxHp;
    }
    SetMonData(pokemon, MON_DATA_HP, &hp);
}

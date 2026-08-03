#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define OVERWORLD_WILD_SPAWNS_INTERNAL_H
#define OW_WILD_MAX_SPAWNS 10
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int8_t s8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OWBD_ROLE_MASK(role) (1u << ((role) - 1))

#define TYPES_H
#include "../include/overworld_wild_behavior_data.h"
#define OWBD_VALIDATION_NO_PROJECTION_BUILDER
#include "overworld_wild_behavior_v40_validation_shared.h"

#define OW_WILD_RUNTIME_SIDECAR_CODE __attribute__((noinline))
#define OW_WILD_RUNTIME_HOST_TEST
#define OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
#include "../src/overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"
#undef OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
#include "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers_internal.h"

_Static_assert(sizeof(OverworldWildRuntimeLayerHandle) == 24, "handle ABI");
_Static_assert(sizeof(OverworldWildRuntimeDeltaOperation) == 28, "operation ABI");
_Static_assert(sizeof(OverworldWildRuntimeStackDeltaRequest) == 484, "request ABI");
_Static_assert(sizeof(OverworldWildRuntimeDeltaOperationResult) == 28, "op result ABI");
_Static_assert(sizeof(OverworldWildRuntimeStackDeltaResult) == 484, "result ABI");
_Static_assert(sizeof(OverworldWildRuntimeDefinition) == 24, "definition ABI");

typedef struct FixtureDefinitionCatalog {
    u32 schemaFingerprint;
    u16 definitionCount;
    u16 reserved;
    OverworldWildRuntimeDefinition definitions[40];
} FixtureDefinitionCatalog;

static FixtureDefinitionCatalog sFixtureCatalog;
static u32 sFixtureCatalogIdentity = 0xC88892BEu;

static u32 fixture_mix(u32 value, u32 input)
{
    value ^= input + 0x9E3779B9u + (value << 6) + (value >> 2);
    value ^= value >> 16;
    value *= 0x7FEB352Du;
    return value ^ (value >> 15);
}

static u32 fixture_hash_bytes(u32 hash, const void *data, u32 size)
{
    const u8 *bytes = data;
    while (size-- != 0) hash = fixture_mix(hash, *bytes++);
    return hash != 0 ? hash : 1;
}

enum {
    TASK11_TRANSITION_ALERT_COMPLETE = 0xA001,
    TASK11_DEF_CALM_OWNER_8102 = 0x7001,
    TASK11_DEF_CALM_OWNER_8103 = 0x7002,
    TASK11_DEF_CALM_OWNER_8104 = 0x7003,
    DEF_SHARED = 0x7001,
    DEF_EXCLUSIVE = 0x7002,
    DEF_EXACT = 0x7003,
    DEF_MULTI_INSTANCE = 0x7004,
    DEF_ORDINARY_TIRED = 0x7005,
    DEF_STAMINA = 0x7006,
    DEF_FLED = 0x7007,
    DEF_FLED_EXACT = 0x7008,
    DEF_BAD_GENERATED = 0x7009,
    DEF_INELIGIBLE = 0x700A,
    DEF_CALM = 0x700B,
    DEF_CUSTOM = 0x700C,
    DEF_HIGH_STATE = 0x700D,
    DEF_LOW_STATE = 0x700E,
    DEF_ALL_OPERATORS = 0x700F,
    DEF_SET_SPEED_FOUR = 0x7010,
    DEF_CLAMP_SPEED_FOUR = 0x7011,
    DEF_BAD_OVERFLOW = 0x7012,
    DEF_STATIC_ADD = 0x7013,
    DEF_RUNTIME_ADD = 0x7014,
    DEF_STATIC_SET_ORDER = 0x7015,
    DEF_ORDER_A = 0x7016,
    DEF_ORDER_B = 0x7017,
    DEF_SPEED_ZERO = 0x7018,
    DEF_AVOID_SET_ONE = 0x7019,
    DEF_AVOID_SET_ZERO = 0x701A,
    DEF_AVOID_SET_TWO = 0x701B,
    DEF_AVOID_ADD = 0x701C,
    DEF_CONFLICTING_BOUNDS = 0x701D,
    DEF_RUNTIME_S16_MIN = 0x701E,
    DEF_RUNTIME_S16_MAX = 0x701F,
};

#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static BOOL sUseTask11ProductionCatalog;

enum {
    TASK11_DEF_STAMINA = 0x7004,
    TASK11_DEF_FLED_SEMANTIC = 0x7005,
    TASK11_DEF_RAM_SEMANTIC = 0x7006,
    TASK11_DEF_THROW_SEMANTIC = 0x7007,
    TASK11_DEF_FORCED_SLEEP = 0x700A,
    TASK11_DEF_FLED_EXACT = 0x700B,
    TASK11_DEF_RAM_EXACT = 0x700E,
    TASK11_DEF_THROW_EXACT = 0x7011,
    TASK11_TRANSITION_STAMINA_APPLY = 0xA002,
    TASK11_TRANSITION_STAMINA_RECOVER = 0xA003,
    TASK11_TRANSITION_FLED_SEMANTIC = 0xA005,
    TASK11_TRANSITION_RAM_SEMANTIC = 0xA007,
    TASK11_TRANSITION_THROW_SEMANTIC = 0xA009,
    TASK11_TRANSITION_FORCED_SLEEP = 0xA00F,
    TASK11_TRANSITION_AGGRO_APPLY = 0xA00C,
    TASK11_TRANSITION_HELP_CALL_APPLY = 0xA00D,
    TASK11_TRANSITION_FLED_EXACT = 0xA012,
    TASK11_TRANSITION_RAM_EXACT = 0xA015,
    TASK11_TRANSITION_THROW_EXACT = 0xA018,
};

static union FixtureInstalledCatalogStorage {
    OverworldWildBehaviorDataBlobHeader alignment;
    u8 bytes[OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE];
} sFixtureInstalledStorage;

static const u8 sGeneratedV40Catalog[
    OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE] = {
#include "../data/OverworldWildBehaviorDataV40.generated.inc"
};
#endif

static int sChecks;

static void require(BOOL condition, const char *message)
{
    sChecks++;
    if (!condition) {
        fprintf(stderr, "runtime layers fixture failed: %s\n", message);
        fflush(stderr);
        _Exit(1);
    }
}

static OverworldWildRuntimeDefinition make_definition(
    u16 id,
    u8 kind,
    u8 selector,
    u8 role,
    u16 controller,
    u16 node,
    u8 flags)
{
    OverworldWildRuntimeDefinition definition;

    memset(&definition, 0, sizeof(definition));
    definition.immutableContextMask = 0xFFFFFFFFu;
    definition.stableId = id;
    definition.kind = kind;
    definition.selectorKind = selector;
    definition.semanticRole = role;
    definition.controllerId = controller;
    definition.nodeId = node;
    definition.flags = flags;
    definition.mapLifetime = 1;
    definition.battleLifetime = 1;
    definition.channel = kind == 2 ? 2 : 1;
    definition.priority = (u8)(id & 0xFF);
    return definition;
}

static FixtureDefinitionCatalog fixture_catalog(void)
{
    FixtureDefinitionCatalog catalog;
    u8 eligible = OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE;

    memset(&catalog, 0, sizeof(catalog));
    catalog.schemaFingerprint = 0xC88892BEu;
    catalog.definitionCount = 31;
    catalog.definitions[0] = make_definition(
        DEF_SHARED, 1, 2, 2, 0, 0,
        eligible | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS);
    catalog.definitions[0].mapLifetime = 2;
    catalog.definitions[1] = make_definition(
        DEF_EXCLUSIVE, 1, 2, 2, 0, 0, eligible);
    catalog.definitions[2] = make_definition(
        DEF_EXACT, 1, 1, 0, 0x3001, 0x4001, eligible);
    catalog.definitions[3] = make_definition(
        DEF_MULTI_INSTANCE, 2, 0, 0, 0, 0,
        eligible
            | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS
            | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES);
    catalog.definitions[3].effectiveProfileId = 0x2201;
    catalog.definitions[3].applicabilitySemanticRole = 2;
    catalog.definitions[4] = make_definition(
        DEF_ORDINARY_TIRED, 1, 2, 3, 0, 0, eligible);
    catalog.definitions[5] = make_definition(
        DEF_STAMINA, 1, 2, 3, 0, 0,
        eligible | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER);
    catalog.definitions[5].requiredOwnerId = 0x8105;
    catalog.definitions[6] = make_definition(
        DEF_FLED, 1, 2, 3, 0, 0,
        eligible
            | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN
            | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER);
    catalog.definitions[6].requiredOwnerId = 0x8107;
    catalog.definitions[6].tiredOriginKind = 1;
    catalog.definitions[7] = make_definition(
        DEF_FLED_EXACT, 1, 1, 0, 0x3001, 0x4001,
        eligible
            | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN
            | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER);
    catalog.definitions[7].requiredOwnerId = 0x8107;
    catalog.definitions[7].tiredOriginKind = 1;
    catalog.definitions[8] = make_definition(
        DEF_BAD_GENERATED, 1, 2, 3, 0, 0,
        eligible
            | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN
            | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER
            | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES);
    catalog.definitions[8].requiredOwnerId = 0x8107;
    catalog.definitions[8].tiredOriginKind = 1;
    catalog.definitions[9] = make_definition(
        DEF_INELIGIBLE, 1, 2, 2, 0, 0, 0);
    catalog.definitions[10] = make_definition(
        DEF_CALM, 1, 2, 1, 0, 0, eligible);
    catalog.definitions[10].channel = 4;
    catalog.definitions[10].priority = 250;
    catalog.definitions[11] = make_definition(
        DEF_CUSTOM, 1, 2, 7, 0, 0, eligible);
    catalog.definitions[12] = make_definition(
        DEF_HIGH_STATE, 1, 2, 1, 0, 0, eligible);
    catalog.definitions[12].channel = 4;
    catalog.definitions[12].priority = 240;
    catalog.definitions[13] = make_definition(
        DEF_LOW_STATE, 1, 2, 1, 0, 0, eligible);
    catalog.definitions[13].channel = 1;
    catalog.definitions[13].priority = 1;
    catalog.definitions[14] = make_definition(
        DEF_ALL_OPERATORS, 2, 0, 0, 0, 0,
        eligible | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS
            | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES);
    catalog.definitions[14].channel = 2;
    catalog.definitions[14].priority = 20;
    catalog.definitions[15] = make_definition(
        DEF_SET_SPEED_FOUR, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[15].channel = 2;
    catalog.definitions[15].priority = 30;
    catalog.definitions[16] = make_definition(
        DEF_CLAMP_SPEED_FOUR, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[16].channel = 2;
    catalog.definitions[16].priority = 30;
    catalog.definitions[17] = make_definition(
        DEF_BAD_OVERFLOW, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[17].channel = 2;
    catalog.definitions[17].priority = 40;
    catalog.definitions[18] = make_definition(
        DEF_STATIC_ADD, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[18].channel = 0;
    catalog.definitions[18].priority = 1;
    catalog.definitions[19] = make_definition(
        DEF_RUNTIME_ADD, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[19].channel = 2;
    catalog.definitions[19].priority = 1;
    catalog.definitions[20] = make_definition(
        DEF_STATIC_SET_ORDER, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[20].channel = 5;
    catalog.definitions[20].priority = 250;
    catalog.definitions[21] = make_definition(
        DEF_ORDER_A, 1, 2, 2, 0, 0,
        eligible | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS);
    catalog.definitions[21].channel = 3;
    catalog.definitions[21].priority = 50;
    catalog.definitions[22] = make_definition(
        DEF_ORDER_B, 1, 2, 2, 0, 0,
        eligible | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS);
    catalog.definitions[22].channel = 3;
    catalog.definitions[22].priority = 50;
    catalog.definitions[23] = make_definition(
        DEF_SPEED_ZERO, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[24] = make_definition(
        DEF_AVOID_SET_ONE, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[25] = make_definition(
        DEF_AVOID_SET_ZERO, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[26] = make_definition(
        DEF_AVOID_SET_TWO, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[27] = make_definition(
        DEF_AVOID_ADD, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[28] = make_definition(
        DEF_CONFLICTING_BOUNDS, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[29] = make_definition(
        DEF_RUNTIME_S16_MIN, 2, 0, 0, 0, 0, eligible);
    catalog.definitions[30] = make_definition(
        DEF_RUNTIME_S16_MAX, 2, 0, 0, 0, 0, eligible);
    return catalog;
}

#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static void init_fixture_installed_blob(void)
{
    memcpy(sFixtureInstalledStorage.bytes, sGeneratedV40Catalog,
        sizeof(sFixtureInstalledStorage.bytes));
}

static OverworldWildBehaviorDataBlobHeader *fixture_installed_header(void)
{
    return (OverworldWildBehaviorDataBlobHeader *)
        sFixtureInstalledStorage.bytes;
}

static void *fixture_section_record(
    OverworldWildBlobSection *section,
    u16 index,
    u16 recordSize)
{
    require(section != NULL && section->entrySize == recordSize
            && index < section->count
            && section->offset <= sizeof(sFixtureInstalledStorage.bytes)
            && recordSize <= sizeof(sFixtureInstalledStorage.bytes)
                - section->offset
            && (u32)index * recordSize
                <= sizeof(sFixtureInstalledStorage.bytes) - section->offset
                    - recordSize,
        "generated v40 fixture section record is outside the blob");
    return sFixtureInstalledStorage.bytes + section->offset
        + (u32)index * recordSize;
}

static OverworldWildTransitionRecord *fixture_transition(u16 stableId)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    u16 index;
    for (index = 0; index < header->transitions.count; index++) {
        OverworldWildTransitionRecord *record = fixture_section_record(
            &header->transitions, index, sizeof(*record));
        if (record->stableId == stableId) return record;
    }
    require(FALSE, "generated v40 transition is absent");
    return NULL;
}

static OverworldWildOverrideDefinitionRecord *fixture_override_definition(
    u16 stableId)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    u16 index;
    for (index = 0; index < header->overrideDefinitions.count; index++) {
        OverworldWildOverrideDefinitionRecord *record = fixture_section_record(
            &header->overrideDefinitions, index, sizeof(*record));
        if (record->stableId == stableId) return record;
    }
    require(FALSE, "generated v40 override definition is absent");
    return NULL;
}

static OverworldWildTransitionGuardRecord *fixture_transition_guard(
    u16 transitionId)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    u16 index;
    for (index = 0; index < header->transitionGuards.count; index++) {
        OverworldWildTransitionGuardRecord *record = fixture_section_record(
            &header->transitionGuards, index, sizeof(*record));
        if (record->transitionId == transitionId) return record;
    }
    require(FALSE, "generated v40 transition guard is absent");
    return NULL;
}

static OverworldWildTransitionOperationRecord *fixture_transition_operation(
    u16 transitionId,
    u8 ordinal)
{
    OverworldWildTransitionRecord *transition =
        fixture_transition(transitionId);
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    require(ordinal < transition->operationCount,
        "generated v40 transition operation ordinal is invalid");
    return fixture_section_record(&header->transitionOperations,
        (u16)(transition->operationStart + ordinal),
        sizeof(OverworldWildTransitionOperationRecord));
}

static OverworldWildTransitionActionRecord *fixture_transition_action(
    u16 transitionId,
    u8 ordinal)
{
    OverworldWildTransitionRecord *transition =
        fixture_transition(transitionId);
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    require(ordinal < transition->actionCount,
        "generated v40 transition action ordinal is invalid");
    return fixture_section_record(&header->transitionActions,
        (u16)(transition->actionStart + ordinal),
        sizeof(OverworldWildTransitionActionRecord));
}

static OverworldWildRecoveryActionRecord *fixture_recovery_action(
    u16 transitionId)
{
    OverworldWildTransitionRecord *transition =
        fixture_transition(transitionId);
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    require(transition->recoveryCount == 1,
        "generated v40 recovery route must have one recovery action");
    return fixture_section_record(&header->recoveryActions,
        transition->recoveryStart, sizeof(OverworldWildRecoveryActionRecord));
}

static OverworldWildTiredTranslationRecord *fixture_tired_translation(
    u8 origin,
    BOOL authoredTiredBound)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    OverworldWildTiredTranslationRecord *found = NULL;
    u16 index;
    for (index = 0; index < header->tiredTranslations.count; index++) {
        OverworldWildTiredTranslationRecord *record = fixture_section_record(
            &header->tiredTranslations, index, sizeof(*record));
        if (record->tiredOriginKind != origin
            || record->authoredTiredBound != (u8)authoredTiredBound
            || record->destinationControllerId != 0x3001)
            continue;
        require(found == NULL,
            "generated v40 tired translation is ambiguous");
        found = record;
    }
    require(found != NULL, "generated v40 tired translation is absent");
    return found;
}

static OverworldWildTiredTranslationRecord *fixture_tired_translation_for(
    u8 origin,
    BOOL authoredTiredBound,
    u16 destinationControllerId)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    OverworldWildTiredTranslationRecord *found = NULL;
    u16 index;
    for (index = 0; index < header->tiredTranslations.count; index++) {
        OverworldWildTiredTranslationRecord *record = fixture_section_record(
            &header->tiredTranslations, index, sizeof(*record));
        if (record->tiredOriginKind != origin
            || record->authoredTiredBound != (u8)authoredTiredBound
            || record->destinationControllerId != destinationControllerId)
            continue;
        require(found == NULL,
            "generated v40 tired translation key is ambiguous");
        found = record;
    }
    require(found != NULL, "generated v40 tired translation key is absent");
    return found;
}

static OverworldWildImportRecipeRecord *fixture_import_recipe_for(
    u16 ownerId,
    u8 semanticRole,
    u16 controllerId)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    OverworldWildImportRecipeRecord *found = NULL;
    u16 index;
    for (index = 0; index < header->importRecipes.count; index++) {
        OverworldWildImportRecipeRecord *record = fixture_section_record(
            &header->importRecipes, index, sizeof(*record));
        if (record->ownerId != ownerId
            || record->semanticRole != semanticRole
            || record->controllerId != controllerId)
            continue;
        require(found == NULL,
            "generated v40 import recipe key is ambiguous");
        found = record;
    }
    require(found != NULL, "generated v40 import recipe key is absent");
    return found;
}

static u32 fixture_crc32(const u8 *bytes, u32 size)
{
    u32 crc = 0xFFFFFFFFu;
    u32 byteIndex;
    for (byteIndex = 0; byteIndex < size; byteIndex++) {
        u8 bit;
        crc ^= bytes[byteIndex];
        for (bit = 0; bit < 8; bit++)
            crc = (crc >> 1) ^ (0xEDB88320u & (u32)-(int)(crc & 1));
    }
    return crc ^ 0xFFFFFFFFu;
}

static void fixture_reseal_installed_catalog(void)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    header->checksum = 0;
    header->checksum = fixture_crc32(sFixtureInstalledStorage.bytes,
        sizeof(sFixtureInstalledStorage.bytes));
}

static void fixture_assert_operation_claims_coherent(void)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    u8 claims[OWBD_TRANSITION_OPERATION_COUNT];
    u16 transitionIndex;
    u16 operationIndex;
    memset(claims, 0, sizeof(claims));
    for (transitionIndex = 0;
            transitionIndex < header->transitions.count; transitionIndex++) {
        OverworldWildTransitionRecord *transition = fixture_section_record(
            &header->transitions, transitionIndex, sizeof(*transition));
        require(transition->operationStart <= header->transitionOperations.count
                && transition->operationCount
                    <= header->transitionOperations.count
                        - transition->operationStart,
            "route-swap fixture operation slice is out of range");
        for (operationIndex = transition->operationStart;
                operationIndex < transition->operationStart
                    + transition->operationCount; operationIndex++) {
            OverworldWildTransitionOperationRecord *operation =
                fixture_section_record(&header->transitionOperations,
                    operationIndex, sizeof(*operation));
            require(operation->transitionId == transition->stableId,
                "route-swap fixture operation child backlink drifted");
            claims[operationIndex]++;
        }
    }
    for (operationIndex = 0;
            operationIndex < header->transitionOperations.count;
            operationIndex++)
        require(claims[operationIndex] == 1,
            "route-swap fixture operation claims are not globally coherent");
}

static void fixture_swap_recovery_route_claims(
    u16 targetTransitionId,
    u16 targetDefinitionId,
    u16 targetOwnerId,
    u16 donorTransitionId,
    u16 donorDefinitionId,
    u16 donorOwnerId)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    OverworldWildTransitionRecord *target =
        fixture_transition(targetTransitionId);
    OverworldWildTransitionRecord *donor =
        fixture_transition(donorTransitionId);
    OverworldWildOverrideDefinitionRecord *targetDefinition =
        fixture_override_definition(targetDefinitionId);
    OverworldWildOverrideDefinitionRecord *donorDefinition =
        fixture_override_definition(donorDefinitionId);
    OverworldWildTransitionOperationRecord *targetOperation =
        fixture_transition_operation(targetTransitionId, 0);
    OverworldWildTransitionOperationRecord *donorOperation =
        fixture_transition_operation(donorTransitionId, 0);
    OverworldWildRecoveryActionRecord *targetRecovery =
        fixture_recovery_action(targetTransitionId);
    OverworldWildRecoveryActionRecord *donorRecovery =
        fixture_recovery_action(donorTransitionId);
    u16 index;

    targetDefinition->recoveryTransitionId = donorTransitionId;
    donorDefinition->recoveryTransitionId = targetTransitionId;
    target->candidateDefinitionId = donorDefinitionId;
    target->ownerId = donorOwnerId;
    targetOperation->definitionId = donorDefinitionId;
    targetOperation->ownerId = donorOwnerId;
    targetRecovery->ownerId = donorOwnerId;
    donor->candidateDefinitionId = targetDefinitionId;
    donor->ownerId = targetOwnerId;
    donorOperation->definitionId = targetDefinitionId;
    donorOperation->ownerId = targetOwnerId;
    donorRecovery->ownerId = targetOwnerId;
    for (index = 0; index < header->tiredTranslations.count; index++) {
        OverworldWildTiredTranslationRecord *translation =
            fixture_section_record(&header->tiredTranslations, index,
                sizeof(*translation));
        if (translation->candidateDefinitionId == targetDefinitionId
            && translation->recoveryTransitionId == targetTransitionId)
            translation->recoveryTransitionId = donorTransitionId;
        else if (translation->candidateDefinitionId == donorDefinitionId
            && translation->recoveryTransitionId == donorTransitionId)
            translation->recoveryTransitionId = targetTransitionId;
    }
    for (index = 0; index < header->importRecipes.count; index++) {
        OverworldWildImportRecipeRecord *recipe = fixture_section_record(
            &header->importRecipes, index, sizeof(*recipe));
        if (recipe->recoveryTransitionId == targetTransitionId)
            recipe->recoveryTransitionId = donorTransitionId;
        else if (recipe->recoveryTransitionId == donorTransitionId)
            recipe->recoveryTransitionId = targetTransitionId;
    }
    fixture_assert_operation_claims_coherent();
}

/* These mutations deliberately model authenticated post-install catalog
 * drift. The portable v40 validator rejects each canonical table change;
 * all selected definition/transition plan bytes stay valid until the named
 * recovery backlink predicate is reached. */
static void fixture_mutate_semantic_tired_backlink(u8 malformedCase)
{
    OverworldWildBehaviorDataBlobHeader *header = fixture_installed_header();
    OverworldWildTiredTranslationRecord *first =
        fixture_tired_translation_for(
            OWBD_TIRED_ORIGIN_FLED, TRUE, 0x3001);
    OverworldWildTiredTranslationRecord *second =
        fixture_tired_translation_for(
            OWBD_TIRED_ORIGIN_FLED, TRUE, 0x3002);
    OverworldWildTiredTranslationRecord *third =
        fixture_tired_translation_for(
            OWBD_TIRED_ORIGIN_FLED, TRUE, 0x3003);
    OverworldWildTiredTranslationRecord *other =
        fixture_tired_translation_for(
            OWBD_TIRED_ORIGIN_RAM_CRASH, FALSE, 0x3001);
    OverworldWildTiredTranslationRecord *records[3] = {
        first, second, third,
    };
    u8 index;

    (void)header;
    switch (malformedCase) {
    case 0:
        for (index = 0; index < 3; index++) {
            records[index]->candidateDefinitionId =
                TASK11_DEF_RAM_SEMANTIC;
            records[index]->recoveryTransitionId =
                TASK11_TRANSITION_RAM_SEMANTIC;
        }
        break;
    case 1: second->destinationControllerId = first->destinationControllerId; break;
    case 2: first->recoveryTransitionId = TASK11_TRANSITION_RAM_SEMANTIC; break;
    case 3: other->recoveryTransitionId = TASK11_TRANSITION_FLED_SEMANTIC; break;
    case 4: first->stableId = 0; break;
    case 5: first->tiredOriginKind = OWBD_TIRED_ORIGIN_RAM_CRASH; break;
    case 6: first->destinationControllerId = 0; break;
    case 7: first->destinationControllerId = 0x3999; break;
    case 8: first->authoredProfileId = 0; break;
    case 9: first->timerOperator = OWBD_CANDIDATE_TIMER_ADD; break;
    case 10: first->timerSource = 0; break;
    case 11: first->mapLifetime = OWBD_LIFETIME_CLEAR; break;
    case 12: first->battleLifetime = OWBD_LIFETIME_PRESERVE_LOGICAL; break;
    case 13: first->flags = 1; break;
    case 14: first->reserved = 1; break;
    case 15: first->authoredTiredBound = FALSE; break;
    case 16: first->exactFallbackControllerId = 0x3001; break;
    case 17: first->exactFallbackNodeId = 0x3107; break;
    case 18: {
        u16 stableId = other->stableId;
        *other = *first;
        other->stableId = stableId;
        other->destinationControllerId = 0x3999;
        break;
    }
    }
}

static void fixture_mutate_exact_tired_backlink(u8 malformedCase)
{
    OverworldWildTiredTranslationRecord *target =
        fixture_tired_translation_for(
            OWBD_TIRED_ORIGIN_FLED, FALSE, 0x3001);
    OverworldWildTiredTranslationRecord *other =
        fixture_tired_translation_for(
            OWBD_TIRED_ORIGIN_RAM_CRASH, FALSE, 0x3001);

    switch (malformedCase) {
    case 0:
        target->candidateDefinitionId = TASK11_DEF_RAM_EXACT;
        target->recoveryTransitionId = TASK11_TRANSITION_RAM_EXACT;
        break;
    case 1: {
        u16 stableId = other->stableId;
        *other = *target;
        other->stableId = stableId;
        break;
    }
    case 2: target->recoveryTransitionId = TASK11_TRANSITION_RAM_EXACT; break;
    case 3: other->recoveryTransitionId = TASK11_TRANSITION_FLED_EXACT; break;
    case 4: target->stableId = 0; break;
    case 5: target->tiredOriginKind = OWBD_TIRED_ORIGIN_RAM_CRASH; break;
    case 6: target->destinationControllerId = 0; break;
    case 7: target->authoredProfileId = 0; break;
    case 8: target->timerOperator = OWBD_CANDIDATE_TIMER_ADD; break;
    case 9: target->timerSource = 0; break;
    case 10: target->mapLifetime = OWBD_LIFETIME_CLEAR; break;
    case 11: target->battleLifetime = OWBD_LIFETIME_PRESERVE_LOGICAL; break;
    case 12: target->flags = 1; break;
    case 13: target->reserved = 1; break;
    case 14: target->authoredTiredBound = TRUE; break;
    case 15: target->destinationControllerId = 0x3002; break;
    case 16: target->exactFallbackControllerId = 0x3002; break;
    case 17: target->exactFallbackNodeId = 0x310E; break;
    }
}

static void fixture_mutate_stamina_backlink(u8 malformedCase)
{
    if (malformedCase == 0)
        fixture_transition(TASK11_TRANSITION_STAMINA_APPLY)->trigger =
            OWBD_TRIGGER_ALERT_COMPLETE;
    else
        fixture_transition(0xA001)->trigger =
            OWBD_TRIGGER_STAMINA_EXHAUSTED;
}

static void fixture_mutate_forced_sleep_backlink(u8 malformedCase)
{
    OverworldWildImportRecipeRecord *first = fixture_import_recipe_for(
        0x810A, OWBD_ROLE_ASLEEP, 0x3001);
    OverworldWildImportRecipeRecord *second = fixture_import_recipe_for(
        0x810A, OWBD_ROLE_ASLEEP, 0x3002);
    OverworldWildImportRecipeRecord *third = fixture_import_recipe_for(
        0x810A, OWBD_ROLE_ASLEEP, 0x3003);
    OverworldWildImportRecipeRecord *other = fixture_import_recipe_for(
        0x810B, OWBD_ROLE_FOLLOWER, 0x3003);
    OverworldWildImportRecipeRecord *records[3] = {
        first, second, third,
    };
    u8 index;

    switch (malformedCase) {
    case 0:
        for (index = 0; index < 3; index++) {
            records[index]->ownerId = 0x8109;
            records[index]->recoveryTransitionId = 0;
        }
        break;
    case 1: second->controllerId = first->controllerId; break;
    case 2: other->recoveryTransitionId = TASK11_TRANSITION_FORCED_SLEEP; break;
    case 3: first->recoveryTransitionId = 0; break;
    case 4: first->ownerId = 0x8109; break;
    case 5: first->semanticRole = OWBD_ROLE_CARRIED; break;
    case 6: first->controllerId = 0; break;
    case 7: first->controllerId = 0x3999; break;
    case 8: first->nodeId = 0; break;
    case 9: first->nodeId = second->nodeId; break;
    case 10: first->profileIdentityId = 0; break;
    case 11: first->profileIdentityId = second->profileIdentityId; break;
    case 12: first->semanticSourceId = 0; break;
    case 13: first->semanticSourceId = other->semanticSourceId; break;
    case 14: first->actionCount = 0; break;
    case 15: first->actionStart++; break;
    case 16: first->truthVector = 0; break;
    case 17: first->lifetime = OWBD_LIFETIME_CLEAR; break;
    case 18: first->flags = 1; break;
    case 19: first->reserved = 1; break;
    case 20: {
        u16 stableId = other->stableId;
        *other = *first;
        other->stableId = stableId;
        other->controllerId = 0x3999;
        break;
    }
    case 21:
        fixture_override_definition(0x7009)->recoveryTransitionId =
            TASK11_TRANSITION_FORCED_SLEEP;
        break;
    }
}

BOOL OverworldWildRuntime_CopyInstalledCatalogBytes(
    u32 offset, void *bytesOut, u32 size)
{
    if (bytesOut == NULL || size == 0
        || offset > sizeof(sFixtureInstalledStorage.bytes)
        || size > sizeof(sFixtureInstalledStorage.bytes) - offset)
        return FALSE;
    memcpy(bytesOut, sFixtureInstalledStorage.bytes + offset, size);
    return TRUE;
}
#endif

#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static BOOL copy_task11_production_definition(
    u16 definitionId,
    OverworldWildRuntimeDefinition *definitionOut)
{
    u16 ownerId = 0;
    u8 origin = 0;
    u8 selector = OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE;
    u8 role = OWBD_ROLE_TIRED;
    u16 controllerId = 0;
    u16 nodeId = 0;
    u8 flags = OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE;

    if (definitionId >= TASK11_DEF_CALM_OWNER_8102
        && definitionId <= TASK11_DEF_CALM_OWNER_8104) {
        *definitionOut = make_definition(definitionId,
            OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE,
            OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE,
            OWBD_ROLE_ATTENTIVE, 0, 0, flags);
        definitionOut->mapLifetime = 2;
        definitionOut->channel = 1;
        definitionOut->priority = 200;
        return TRUE;
    } else if (definitionId == TASK11_DEF_STAMINA) ownerId = 0x8105;
    else if (definitionId == TASK11_DEF_FLED_SEMANTIC) {
        ownerId = 0x8107;
        origin = OWBD_TIRED_ORIGIN_FLED;
    } else if (definitionId == TASK11_DEF_RAM_SEMANTIC) {
        ownerId = 0x8106;
        origin = OWBD_TIRED_ORIGIN_RAM_CRASH;
    } else if (definitionId == TASK11_DEF_THROW_SEMANTIC) {
        ownerId = 0x8108;
        origin = OWBD_TIRED_ORIGIN_THROW_RECOVERY;
    } else if (definitionId == TASK11_DEF_FLED_EXACT) {
        ownerId = 0x8107;
        origin = OWBD_TIRED_ORIGIN_FLED;
        selector = OW_WILD_RUNTIME_SELECTOR_EXACT;
    } else if (definitionId == TASK11_DEF_RAM_EXACT) {
        ownerId = 0x8106;
        origin = OWBD_TIRED_ORIGIN_RAM_CRASH;
        selector = OW_WILD_RUNTIME_SELECTOR_EXACT;
    } else if (definitionId == TASK11_DEF_THROW_EXACT) {
        ownerId = 0x8108;
        origin = OWBD_TIRED_ORIGIN_THROW_RECOVERY;
        selector = OW_WILD_RUNTIME_SELECTOR_EXACT;
    } else if (definitionId == TASK11_DEF_FORCED_SLEEP) {
        *definitionOut = make_definition(definitionId,
            OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE,
            OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE,
            OWBD_ROLE_ASLEEP, 0, 0,
            flags | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES);
        definitionOut->mapLifetime = 2;
        definitionOut->channel = 2;
        definitionOut->priority = 200;
        return TRUE;
    } else {
        memset(definitionOut, 0, sizeof(*definitionOut));
        return FALSE;
    }
    flags |= OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER;
    if (origin != 0)
        flags |= OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN;
    if (selector == OW_WILD_RUNTIME_SELECTOR_EXACT) {
        controllerId = 0x3001;
        nodeId = 0x3107;
        role = 0;
    }
    *definitionOut = make_definition(definitionId,
        OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE,
        selector, role, controllerId, nodeId, flags);
    definitionOut->requiredOwnerId = ownerId;
    definitionOut->tiredOriginKind = origin;
    definitionOut->mapLifetime = 2;
    definitionOut->channel = 2;
    definitionOut->priority = 100;
    return TRUE;
}
#endif

BOOL OverworldWildRuntime_CopyInstalledDefinition(
    u16 definitionId,
    OverworldWildRuntimeDefinition *definitionOut)
{
    u16 index;
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    if (sUseTask11ProductionCatalog)
        return copy_task11_production_definition(
            definitionId, definitionOut);
#endif
    for (index = 0; index < sFixtureCatalog.definitionCount; index++) {
        if (sFixtureCatalog.definitions[index].stableId == definitionId) {
            *definitionOut = sFixtureCatalog.definitions[index];
            return TRUE;
        }
    }
    memset(definitionOut, 0, sizeof(*definitionOut));
    return FALSE;
}

BOOL OverworldWildRuntime_ResolveInstalledTimerDefinition(
    u16 definitionId,
    const OverworldWildRuntimeStaticCache *staticCache,
    OverworldWildRuntimeTimerDefinition *timerOut)
{
    memset(timerOut, 0, sizeof(*timerOut));
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    if (sUseTask11ProductionCatalog) {
        if (definitionId >= TASK11_DEF_CALM_OWNER_8102
            && definitionId <= TASK11_DEF_CALM_OWNER_8104) {
            return TRUE;
        } else if (definitionId == TASK11_DEF_STAMINA) {
            timerOut->recoveryTransitionId =
                TASK11_TRANSITION_STAMINA_RECOVER;
            timerOut->source = 3;
        } else if (definitionId == TASK11_DEF_FLED_SEMANTIC) {
            timerOut->recoveryTransitionId =
                TASK11_TRANSITION_FLED_SEMANTIC;
            timerOut->source = 1;
        } else if (definitionId == TASK11_DEF_RAM_SEMANTIC) {
            timerOut->recoveryTransitionId =
                TASK11_TRANSITION_RAM_SEMANTIC;
            timerOut->source = 1;
        } else if (definitionId == TASK11_DEF_THROW_SEMANTIC) {
            timerOut->recoveryTransitionId =
                TASK11_TRANSITION_THROW_SEMANTIC;
            timerOut->source = 1;
        } else if (definitionId == TASK11_DEF_FLED_EXACT) {
            timerOut->recoveryTransitionId = TASK11_TRANSITION_FLED_EXACT;
            timerOut->source = 1;
        } else if (definitionId == TASK11_DEF_RAM_EXACT) {
            timerOut->recoveryTransitionId = TASK11_TRANSITION_RAM_EXACT;
            timerOut->source = 1;
        } else if (definitionId == TASK11_DEF_THROW_EXACT) {
            timerOut->recoveryTransitionId = TASK11_TRANSITION_THROW_EXACT;
            timerOut->source = 1;
        } else if (definitionId == TASK11_DEF_FORCED_SLEEP) {
            timerOut->recoveryTransitionId =
                TASK11_TRANSITION_FORCED_SLEEP;
            timerOut->source = 1;
            timerOut->hiddenPolicy =
                OW_WILD_RUNTIME_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN;
        } else {
            return FALSE;
        }
        timerOut->clock = OW_WILD_RUNTIME_TIMER_CLOCK_FRAME;
        if (definitionId != TASK11_DEF_FORCED_SLEEP)
            timerOut->hiddenPolicy =
                OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN;
        timerOut->recoveryPolicy = 1;
        if (staticCache == NULL) return TRUE;
        if (!staticCache->valid) return FALSE;
        timerOut->duration = 4;
        return TRUE;
    }
#endif
    if (staticCache == NULL || !staticCache->valid) return FALSE;
    if (definitionId == DEF_ORDINARY_TIRED
        || definitionId == DEF_STAMINA) {
        timerOut->recoveryTransitionId = 0xA003;
        timerOut->clock = OW_WILD_RUNTIME_TIMER_CLOCK_FRAME;
        timerOut->source = 3;
        timerOut->hiddenPolicy =
            OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN;
        timerOut->recoveryPolicy = 1;
        timerOut->duration = definitionId == DEF_STAMINA ? 6 : 4;
    } else if (definitionId == DEF_HIGH_STATE) {
        timerOut->recoveryTransitionId = 0xA004;
        timerOut->clock = OW_WILD_RUNTIME_TIMER_CLOCK_FRAME;
        timerOut->source = 1;
        timerOut->hiddenPolicy =
            OW_WILD_RUNTIME_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN;
        timerOut->recoveryPolicy = 1;
        timerOut->duration = 2;
    } else if (definitionId == DEF_LOW_STATE) {
        timerOut->recoveryTransitionId = 0xA005;
        timerOut->clock = OW_WILD_RUNTIME_TIMER_CLOCK_FRAME;
        timerOut->source = 1;
        timerOut->hiddenPolicy =
            OW_WILD_RUNTIME_HIDDEN_TIMER_EXPIRE_ON_HIDE;
        timerOut->recoveryPolicy = 1;
        timerOut->duration = 3;
    } else if (definitionId == DEF_EXACT) {
        timerOut->recoveryTransitionId = 0xA006;
        timerOut->clock =
            OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT;
        timerOut->source = 1;
        timerOut->hiddenPolicy =
            OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN;
        timerOut->recoveryPolicy = 1;
        timerOut->duration = 5;
    } else if (definitionId == DEF_FLED) {
        timerOut->recoveryTransitionId = 0xA007;
        timerOut->clock = OW_WILD_RUNTIME_TIMER_CLOCK_FRAME;
        timerOut->source = 1;
        timerOut->hiddenPolicy =
            OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN;
        timerOut->recoveryPolicy = 1;
        timerOut->duration = 255;
    }
    return TRUE;
}

u8 OverworldWildRuntime_CountInstalledTiredTranslations(
    u8 tiredOriginKind,
    u16 destinationControllerId,
    BOOL authoredTiredBound,
    u16 *candidateDefinitionIdOut)
{
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    OverworldWildBehaviorDataBlobHeader *header;
    u16 index;
#endif
    *candidateDefinitionIdOut = 0;
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    if (sUseTask11ProductionCatalog) {
        u8 count = 0;
        header = fixture_installed_header();
        if (tiredOriginKind == 0) {
            for (index = 0; index < header->transitions.count; index++) {
                OverworldWildTransitionRecord *transition =
                    fixture_section_record(&header->transitions, index,
                        sizeof(*transition));
                if (transition->trigger
                        != OWBD_TRIGGER_STAMINA_EXHAUSTED)
                    continue;
                if (count++ == 0)
                    *candidateDefinitionIdOut =
                        transition->candidateDefinitionId;
            }
            return count;
        }
        for (index = 0; index < header->tiredTranslations.count; index++) {
            OverworldWildTiredTranslationRecord *translation =
                fixture_section_record(&header->tiredTranslations, index,
                    sizeof(*translation));
            if (translation->tiredOriginKind != tiredOriginKind
                || translation->destinationControllerId
                    != destinationControllerId
                || translation->authoredTiredBound
                    != (authoredTiredBound != FALSE))
                continue;
            if (count++ == 0)
                *candidateDefinitionIdOut =
                    translation->candidateDefinitionId;
        }
        return count;
    }
#endif
    if (tiredOriginKind != 1 || destinationControllerId != 0x3001)
        return 0;
    *candidateDefinitionIdOut = authoredTiredBound ? DEF_FLED : DEF_FLED_EXACT;
    return 1;
}

#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static void init_task11_resolved_node(
    OverworldWildRuntimeResolvedNode *node,
    u16 nodeId,
    u16 profileId,
    u8 role)
{
    memset(node, 0, sizeof(*node));
    node->nodeId = nodeId;
    node->profileId = profileId;
    node->semanticRole = role;
    node->bound = TRUE;
    node->stateValues[0] = role;
    node->stateValues[1] = 1;
    node->stateValues[2] = 2;
    node->stateValues[3] = 2;
    node->stateValues[4] = 4;
    node->stateValues[7] = 15;
    node->stateValues[9] = 1;
    node->stateValues[10] = 2;
    node->stateValues[12] = 4;
    node->stateValues[14] = 4;
}

static BOOL copy_task11_static_composition(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    OverworldWildRuntimeStaticComposition *compositionOut)
{
    const BOOL fallback = staticContext != NULL
        && (staticContext->behaviorClass == 1
            || staticContext->behaviorClass == 9);
    const BOOL asleep = staticContext != NULL
        && staticContext->behaviorClass == 2;
    const BOOL authoredRebind = staticContext != NULL
        && staticContext->behaviorClass == 8;
    const BOOL fallbackRebind = staticContext != NULL
        && staticContext->behaviorClass == 9;
    const BOOL calmBase = staticContext != NULL
        && staticContext->species == 56 && staticContext->groupFlags == 8;
    u8 index = 0;
    u8 inputIndex = 0;

    memset(compositionOut, 0, sizeof(*compositionOut));
    if (staticContext == NULL || staticContext->reserved != 0
        || staticContext->behaviorClass > 9)
        return FALSE;
    compositionOut->catalogIdentity =
        fixture_installed_header()->schemaFingerprint;
    compositionOut->staticContextIdentity =
        0x71000000u ^ staticContext->groupFlags
            ^ ((u32)staticContext->species << 8)
            ^ staticContext->behaviorClass;
    compositionOut->immutableContextMask = staticContext->groupFlags;
    compositionOut->staticContext = *staticContext;
    compositionOut->controllerId = 0x3001;
    compositionOut->baseNodeId = calmBase ? 0x3101 : 0x3102;
    compositionOut->baseProfileId = calmBase ? 0x2304 : 0x2202;
    compositionOut->spawnPolicyId = 0x4001;
    compositionOut->populationPolicyId = 0x4101;
    compositionOut->spawnConfiguration.minimumDistance = 1;
    compositionOut->spawnConfiguration.maximumDistance = 1;
    compositionOut->spawnConfiguration.spawnHopTime = 1;
    compositionOut->spawnConfiguration.populationLimit = 1;
    compositionOut->baseSemanticRole = calmBase
        ? OWBD_ROLE_CALM : OWBD_ROLE_ATTENTIVE;
    compositionOut->valid = TRUE;
    compositionOut->semanticRoleMask = OWBD_ROLE_MASK(OWBD_ROLE_CALM)
        | OWBD_ROLE_MASK(OWBD_ROLE_ATTENTIVE)
        | OWBD_ROLE_MASK(OWBD_ROLE_CUSTOM)
        | (fallback ? 0 : OWBD_ROLE_MASK(OWBD_ROLE_TIRED))
        | (asleep ? OWBD_ROLE_MASK(OWBD_ROLE_ASLEEP) : 0);
    init_task11_resolved_node(&compositionOut->resolvedNodes[index++],
        0x3101, calmBase ? 0x2304 : 0x2201, OWBD_ROLE_CALM);
    init_task11_resolved_node(&compositionOut->resolvedNodes[index++],
        0x3102, 0x2202, OWBD_ROLE_ATTENTIVE);
    if (!fallback)
        init_task11_resolved_node(&compositionOut->resolvedNodes[index++],
            0x3103, authoredRebind ? 0x2206 : 0x2203,
            OWBD_ROLE_TIRED);
    if (asleep)
        init_task11_resolved_node(&compositionOut->resolvedNodes[index++],
            0x3106, 0x220C, OWBD_ROLE_ASLEEP);
    init_task11_resolved_node(&compositionOut->resolvedNodes[index++],
        0x3107, fallbackRebind ? 0x2211 : 0x2210, OWBD_ROLE_CUSTOM);
    compositionOut->nodeCount = index;
    compositionOut->boundNodeCount = index;
    compositionOut->controllerValues[6] = 20;
    compositionOut->controllerValues[7] = 10;
    memcpy(compositionOut->stateValues,
        compositionOut->resolvedNodes[calmBase ? 0 : 1].stateValues,
        sizeof(compositionOut->stateValues));

    if (staticContext->behaviorClass == 3)
        compositionOut->semanticRoleMask &=
            (u8)~OWBD_ROLE_MASK(OWBD_ROLE_TIRED);
    else if (staticContext->behaviorClass == 4)
        compositionOut->boundNodeCount--;
    else if (staticContext->behaviorClass == 5)
        compositionOut->resolvedNodes[2].nodeId = 0;
    else if (staticContext->behaviorClass == 6)
        compositionOut->resolvedNodes[2].profileId = 0;

    compositionOut->staticSetHash = fixture_mix(0x4F575339u,
        compositionOut->catalogIdentity);
    compositionOut->staticSetHash = fixture_mix(
        compositionOut->staticSetHash, compositionOut->staticContextIdentity);
    compositionOut->staticSetHash = fixture_hash_bytes(
        compositionOut->staticSetHash, &compositionOut->immutableContextMask,
        sizeof(*compositionOut)
            - offsetof(OverworldWildRuntimeStaticComposition,
                immutableContextMask));
    if (input == NULL) return TRUE;
    if (input->immutableContextMask != compositionOut->immutableContextMask
        || input->controllerId != compositionOut->controllerId
        || input->effectiveProfileId != compositionOut->baseProfileId
        || input->effectiveSemanticRole != compositionOut->baseSemanticRole
        || input->boundNodeCount != compositionOut->boundNodeCount
        || input->semanticRoleMask != compositionOut->semanticRoleMask)
        return FALSE;
    for (index = 0; index < compositionOut->nodeCount; index++) {
        const OverworldWildRuntimeResolvedNode *node =
            &compositionOut->resolvedNodes[index];
        if (!node->bound) continue;
        if (inputIndex >= input->boundNodeCount
            || input->boundNodeIds[inputIndex++] != node->nodeId)
            return FALSE;
    }
    return inputIndex == input->boundNodeCount;
}
#endif

BOOL OverworldWildRuntime_CopyInstalledStaticComposition(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    OverworldWildRuntimeStaticComposition *compositionOut)
{
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    if (sUseTask11ProductionCatalog)
        return copy_task11_static_composition(
            staticContext, input, compositionOut);
#endif
    const BOOL authoredTiredBound = staticContext != NULL
        && staticContext->behaviorClass != 1;
    const BOOL authoredAsleepBound = staticContext != NULL
        && staticContext->behaviorClass == 2;
    const u8 boundNodeCount = (u8)((authoredTiredBound ? 4 : 3)
        + (authoredAsleepBound ? 1 : 0));
    const u8 semanticRoleMask = OWBD_ROLE_MASK(1) | OWBD_ROLE_MASK(2)
        | OWBD_ROLE_MASK(7)
        | (authoredTiredBound ? OWBD_ROLE_MASK(3) : 0)
        | (authoredAsleepBound ? OWBD_ROLE_MASK(4) : 0);

    memset(compositionOut, 0, sizeof(*compositionOut));
    if (staticContext == NULL || staticContext->reserved != 0
        || staticContext->behaviorClass > 2
        || (input != NULL && (input->controllerId != 0x3001
            || input->effectiveProfileId != 0x2201
            || input->effectiveSemanticRole != OWBD_ROLE_ATTENTIVE
            || input->immutableContextMask != staticContext->groupFlags
            || input->boundNodeCount != boundNodeCount
            || input->boundNodeIds[0]
                != (authoredTiredBound ? 0x4001 : 0x4100)
            || input->boundNodeIds[1]
                != (authoredTiredBound ? 0x4100 : 0x4101)
            || input->boundNodeIds[2]
                != (authoredTiredBound ? 0x4101 : 0x4107)
            || (authoredTiredBound && input->boundNodeIds[3] != 0x4107)
            || (authoredAsleepBound && input->boundNodeIds[4] != 0x4200)
            || input->semanticRoleMask != semanticRoleMask)))
        return FALSE;
    compositionOut->catalogIdentity = 0xC88892BEu;
    compositionOut->staticContextIdentity =
        0x61000000u ^ staticContext->groupFlags
            ^ ((u32)staticContext->species << 8);
    compositionOut->staticSetHash = 0x51000001u;
    compositionOut->immutableContextMask = staticContext->groupFlags;
    compositionOut->staticContext = *staticContext;
    compositionOut->controllerId = 0x3001;
    compositionOut->baseNodeId = 0x4101;
    compositionOut->baseProfileId = 0x2201;
    compositionOut->spawnPolicyId = 0x4201;
    compositionOut->populationPolicyId = 0x4301;
    compositionOut->spawnConfiguration.minimumDistance = 1;
    compositionOut->spawnConfiguration.maximumDistance = 1;
    compositionOut->spawnConfiguration.spawnHopTime = 1;
    compositionOut->spawnConfiguration.populationLimit = 1;
    compositionOut->baseSemanticRole = OWBD_ROLE_ATTENTIVE;
    compositionOut->valid = TRUE;
    compositionOut->nodeCount = boundNodeCount;
    compositionOut->boundNodeCount = boundNodeCount;
    compositionOut->semanticRoleMask = semanticRoleMask;
    compositionOut->stateValues[0] = 2;
    compositionOut->stateValues[1] = 1;
    compositionOut->stateValues[2] = 2;
    compositionOut->stateValues[3] = 2;
    compositionOut->stateValues[4] = 4;
    compositionOut->stateValues[6] = 0;
    compositionOut->stateValues[7] = 15;
    compositionOut->stateValues[9] = 1;
    compositionOut->stateValues[10] = 2;
    compositionOut->stateValues[12] = 4;
    compositionOut->stateValues[14] = 4;
    compositionOut->controllerValues[6] = 4;
    compositionOut->controllerValues[7] = 4;
    {
        static const u16 authoredNodeIds[5] = {
            0x4001, 0x4100, 0x4101, 0x4107, 0x4200};
        static const u8 authoredRoles[5] = {3, 1, 2, 7, 4};
        static const u16 fallbackNodeIds[3] = {0x4100, 0x4101, 0x4107};
        static const u8 fallbackRoles[3] = {1, 2, 7};
        u8 nodeIndex;
        for (nodeIndex = 0; nodeIndex < boundNodeCount; nodeIndex++) {
            OverworldWildRuntimeResolvedNode *node =
                &compositionOut->resolvedNodes[nodeIndex];
            const u8 role = authoredTiredBound
                ? authoredRoles[nodeIndex] : fallbackRoles[nodeIndex];
            node->nodeId = authoredTiredBound
                ? authoredNodeIds[nodeIndex] : fallbackNodeIds[nodeIndex];
            node->profileId = (u16)(0x2200 + role);
            node->semanticRole = role;
            node->bound = TRUE;
            node->stateValues[0] = role;
            node->stateValues[1] = 1;
            node->stateValues[2] = 2;
            node->stateValues[3] = 2;
            node->stateValues[4] = 4;
            node->stateValues[7] = 15;
            node->stateValues[9] = 1;
            node->stateValues[10] = 2;
            node->stateValues[12] = 4;
            node->stateValues[14] = 4;
        }
        compositionOut->resolvedNodes[authoredTiredBound ? 2 : 1].profileId =
            0x2201;
        memcpy(compositionOut->resolvedNodes[authoredTiredBound ? 2 : 1]
                .stateValues,
            compositionOut->stateValues,
            sizeof(compositionOut->stateValues));
        compositionOut->resolvedNodes[authoredTiredBound ? 1 : 0].profileId =
            0x2301;
        compositionOut->resolvedNodes[authoredTiredBound ? 1 : 0]
            .stateValues[3] = 3;
    }
    if (staticContext->groupFlags == 0x12345678u) {
        compositionOut->staticModifierCount = 2;
        compositionOut->staticModifiers[0].modifierDefinitionId =
            DEF_STATIC_SET_ORDER;
        compositionOut->staticModifiers[0].staticPriority = 1;
        compositionOut->staticModifiers[0].ruleStableId = 0x5001;
        compositionOut->staticModifiers[0].actionStableId = 0x6001;
        compositionOut->staticModifiers[1].modifierDefinitionId =
            DEF_STATIC_ADD;
        compositionOut->staticModifiers[1].staticPriority = 1;
        compositionOut->staticModifiers[1].ruleStableId = 0x5001;
        compositionOut->staticModifiers[1].actionStableId = 0x6002;
        compositionOut->staticSetHash = 0x51000002u;
    }
    compositionOut->staticSetHash = fixture_mix(0x4F575339u,
        compositionOut->catalogIdentity);
    compositionOut->staticSetHash = fixture_mix(
        compositionOut->staticSetHash, compositionOut->staticContextIdentity);
    compositionOut->staticSetHash = fixture_hash_bytes(
        compositionOut->staticSetHash, &compositionOut->immutableContextMask,
        sizeof(*compositionOut)
            - offsetof(OverworldWildRuntimeStaticComposition,
                immutableContextMask));
    return TRUE;
}

BOOL OverworldWildRuntime_CopyInstalledCatalogIdentity(u32 *identityOut)
{
    if (identityOut == NULL) return FALSE;
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    if (sUseTask11ProductionCatalog) {
        *identityOut = fixture_installed_header()->schemaFingerprint;
        return *identityOut != 0;
    }
#endif
    if (sFixtureCatalogIdentity == 0) {
        *identityOut = 0;
        return FALSE;
    }
    *identityOut = sFixtureCatalogIdentity;
    return TRUE;
}

const OverworldWildBehaviorDataBlobHeader *
OverworldWildRuntime_AcquireInstalledTransitionCatalog(void)
{
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    return sUseTask11ProductionCatalog
        ? fixture_installed_header() : NULL;
#else
    return NULL;
#endif
}

BOOL OverworldWildRuntime_CopyInstalledStaticCache(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    u32 staticContextGeneration,
    OverworldWildRuntimeStaticCache *cacheOut)
{
    OverworldWildRuntimeStaticComposition composition;
    if (!OverworldWildRuntime_CopyInstalledStaticComposition(
            staticContext, input, &composition)) return FALSE;
    memset(cacheOut, 0, sizeof(*cacheOut));
    cacheOut->catalogIdentity = composition.catalogIdentity;
    cacheOut->staticContextIdentity = composition.staticContextIdentity;
    cacheOut->staticContextGeneration = staticContextGeneration;
    memcpy(&cacheOut->immutableContextMask,
        &composition.immutableContextMask,
        sizeof(*cacheOut) - offsetof(OverworldWildRuntimeStaticCache,
            immutableContextMask));
    cacheOut->staticSetHash = fixture_mix(0x4F575339u,
        cacheOut->catalogIdentity);
    cacheOut->staticSetHash = fixture_mix(cacheOut->staticSetHash,
        cacheOut->staticContextIdentity);
    cacheOut->staticSetHash = fixture_hash_bytes(cacheOut->staticSetHash,
        &cacheOut->immutableContextMask,
        sizeof(*cacheOut) - offsetof(OverworldWildRuntimeStaticCache,
            immutableContextMask));
    return TRUE;
}

BOOL OverworldWildRuntime_ApplicabilityMatchesStaticCache(
    const OverworldWildRuntimeApplicabilityInput *input,
    const OverworldWildRuntimeStaticCache *cache)
{
    u8 nodeIndex, inputIndex = 0;
    if (input == NULL
        || input->immutableContextMask != cache->immutableContextMask
        || input->controllerId != cache->controllerId
        || input->effectiveProfileId != cache->baseProfileId
        || input->effectiveSemanticRole != cache->baseSemanticRole
        || input->boundNodeCount != cache->boundNodeCount
        || input->semanticRoleMask != cache->semanticRoleMask) return FALSE;
    for (nodeIndex = 0; nodeIndex < cache->nodeCount; nodeIndex++) {
        if (!cache->resolvedNodes[nodeIndex].bound) continue;
        if (inputIndex >= input->boundNodeCount
            || input->boundNodeIds[inputIndex++]
                != cache->resolvedNodes[nodeIndex].nodeId) return FALSE;
    }
    return inputIndex == input->boundNodeCount;
}

BOOL OverworldWildRuntime_MatchesPendingTimerExpiry(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    u8 index;
    if (runtime == NULL || expiry == NULL
        || expiry->slotIndex >= OW_WILD_MAX_SPAWNS)
        return FALSE;
    slot = &runtime->slots[expiry->slotIndex];
    for (index = 0; index < slot->activeLayerCount; index++) {
        const OverworldWildRuntimeTimer *timer = &slot->timerBank.timers[index];
        if (timer->entryGeneration == expiry->entryGeneration
            && timer->timerGeneration == expiry->timerGeneration
            && (timer->flags & (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
                == (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
            return TRUE;
    }
    return FALSE;
}

OverworldWildRuntimeStatus OverworldWildRuntime_ValidateStaticCache(
    const OverworldWildRuntimeStaticCache *cache,
    u32 staticContextGeneration)
{
    u32 identity;
    if (!OverworldWildRuntime_CopyInstalledCatalogIdentity(&identity)
        || identity != cache->catalogIdentity || !cache->valid
        || cache->staticContextGeneration != staticContextGeneration
        || cache->nodeCount == 0 || cache->nodeCount > 8
        || cache->boundNodeCount == 0
        || cache->boundNodeCount > cache->nodeCount
        || cache->spawnConfiguration.spawnState > 3
        || cache->spawnConfiguration.destination > 16
        || cache->spawnConfiguration.minimumDistance < 1
        || cache->spawnConfiguration.minimumDistance > 8
        || cache->spawnConfiguration.maximumDistance
            < cache->spawnConfiguration.minimumDistance
        || cache->spawnConfiguration.maximumDistance > 8
        || cache->spawnConfiguration.spawnHopTime > 64
        || cache->spawnConfiguration.spawnFlags
        || cache->spawnConfiguration.populationLimit > 10
        || cache->spawnConfiguration.populationFlags
        || cache->spawnConfiguration.helpCallInvocation > 1
        || cache->spawnConfiguration.pickupThrowEntry > 1
        || cache->spawnConfiguration.pickupThrowActiveLoop
            != cache->spawnConfiguration.pickupThrowEntry
        || (cache->spawnConfiguration.helpCallInvocation
            && cache->spawnConfiguration.pickupThrowEntry)
        || cache->spawnConfiguration.hookFlags
        || cache->staticModifierCount > 8)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_ResolveRetainedStaticCache(
    const OverworldWildRuntimeStaticCache *retainedCache,
    u32 staticContextGeneration,
    OverworldWildRuntimeStaticCache *resolvedOut)
{
    if (retainedCache == NULL || resolvedOut == NULL
        || retainedCache == resolvedOut
        || OverworldWildRuntime_ValidateStaticCache(
            retainedCache, staticContextGeneration)
            != OW_WILD_RUNTIME_STATUS_OK)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    *resolvedOut = *retainedCache;
    return OW_WILD_RUNTIME_STATUS_OK;
}

BOOL OverworldWildRuntime_CopyResolvedCachedNode(
    const OverworldWildRuntimeStaticCache *cache,
    const OverworldWildRuntimeDefinition *definition,
    OverworldWildRuntimeResolvedNode *nodeOut)
{
    u8 index;
    const OverworldWildRuntimeResolvedNode *match = NULL;
    memset(nodeOut, 0, sizeof(*nodeOut));
    for (index = 0; index < cache->nodeCount; index++) {
        const OverworldWildRuntimeResolvedNode *node =
            &cache->resolvedNodes[index];
        if (!node->bound) continue;
        if ((definition->selectorKind == 1
                && node->nodeId == definition->nodeId)
            || (definition->selectorKind == 2
                && node->semanticRole == definition->semanticRole)) {
            if (match != NULL) return FALSE;
            match = node;
        }
    }
    if (match == NULL) return FALSE;
    *nodeOut = *match;
    return TRUE;
}

BOOL OverworldWildRuntime_CopyInstalledResolvedNode(
    const OverworldWildRuntimeStaticComposition *composition,
    const OverworldWildRuntimeDefinition *definition,
    OverworldWildRuntimeResolvedNode *nodeOut)
{
    u8 index;
    const OverworldWildRuntimeResolvedNode *match = NULL;
    memset(nodeOut, 0, sizeof(*nodeOut));
    if (composition == NULL || definition == NULL || definition->kind != 1)
        return FALSE;
    for (index = 0; index < composition->nodeCount; index++) {
        const OverworldWildRuntimeResolvedNode *node =
            &composition->resolvedNodes[index];
        if (!node->bound) continue;
        if ((definition->selectorKind == 1
                && definition->nodeId == node->nodeId)
            || (definition->selectorKind == 2
                && definition->semanticRole == node->semanticRole)) {
            if (match != NULL) return FALSE;
            match = node;
        }
    }
    if (match == NULL) return FALSE;
    *nodeOut = *match;
    return TRUE;
}

BOOL OverworldWildRuntime_CopyInstalledModifierOperations(
    u16 definitionId,
    OverworldWildRuntimeModifierOperation *operationsOut,
    u8 capacity,
    u8 *operationCountOut)
{
    *operationCountOut = 0;
    if (capacity == 0) return FALSE;
    memset(operationsOut, 0, (size_t)capacity * sizeof(*operationsOut));
    if (definitionId == DEF_MULTI_INSTANCE
        || definitionId == DEF_STATIC_ADD
        || definitionId == DEF_RUNTIME_ADD) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 3;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_ADD;
        operationsOut[0].operand = 1;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_SET_SPEED_FOUR) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 3;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_SET;
        operationsOut[0].operand = 4;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_STATIC_SET_ORDER) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 3;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_SET;
        operationsOut[0].operand = 1;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_CLAMP_SPEED_FOUR) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 3;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_ADD;
        operationsOut[0].operand = 32;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_BAD_OVERFLOW) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 3;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_ADD;
        operationsOut[0].operand = 33;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_RUNTIME_S16_MIN
        || definitionId == DEF_RUNTIME_S16_MAX) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 4;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_ADD;
        operationsOut[0].operand = definitionId == DEF_RUNTIME_S16_MIN
            ? -32768 : 32767;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_CONFLICTING_BOUNDS && capacity >= 2) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 4;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_AT_LEAST;
        operationsOut[0].operand = 8;
        operationsOut[1].fieldNamespace = 1;
        operationsOut[1].fieldId = 4;
        operationsOut[1].operatorKind = OW_WILD_RUNTIME_OPERATOR_AT_MOST;
        operationsOut[1].operand = 16;
        *operationCountOut = 2;
        return TRUE;
    }
    if (definitionId == DEF_SPEED_ZERO) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 3;
        operationsOut[0].operatorKind = OW_WILD_RUNTIME_OPERATOR_SET;
        operationsOut[0].operand = 0;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_AVOID_SET_ONE
        || definitionId == DEF_AVOID_SET_ZERO
        || definitionId == DEF_AVOID_SET_TWO
        || definitionId == DEF_AVOID_ADD) {
        operationsOut[0].fieldNamespace = 1;
        operationsOut[0].fieldId = 22;
        operationsOut[0].operatorKind = definitionId == DEF_AVOID_ADD
            ? OW_WILD_RUNTIME_OPERATOR_ADD : OW_WILD_RUNTIME_OPERATOR_SET;
        operationsOut[0].operand = definitionId == DEF_AVOID_SET_ONE ? 1
            : definitionId == DEF_AVOID_SET_TWO ? 2
            : definitionId == DEF_AVOID_ADD ? 1 : 0;
        *operationCountOut = 1;
        return TRUE;
    }
    if (definitionId == DEF_ALL_OPERATORS && capacity >= 8) {
        u8 i;
        for (i = 0; i < 6; i++) {
            operationsOut[i].fieldNamespace = 1;
            operationsOut[i].operatorKind = (u8)(i + 1);
        }
        operationsOut[0].fieldId = 3;
        operationsOut[1].fieldId = 4;
        operationsOut[2].fieldId = 11;
        operationsOut[3].fieldId = 13;
        operationsOut[4].fieldId = 14;
        operationsOut[5].fieldId = 12;
        operationsOut[0].operand = 2;
        operationsOut[1].operand = 1;
        operationsOut[2].operand = 4;
        operationsOut[3].operand = 3;
        operationsOut[4].operand = -2;
        operationsOut[4].bound = 2;
        operationsOut[5].operand = 2;
        operationsOut[5].bound = 5;
        operationsOut[6].fieldNamespace = 1;
        operationsOut[6].fieldId = 9;
        operationsOut[6].operatorKind = OW_WILD_RUNTIME_OPERATOR_SET;
        operationsOut[6].operand = 12;
        operationsOut[7].fieldNamespace = 1;
        operationsOut[7].fieldId = 10;
        operationsOut[7].operatorKind = OW_WILD_RUNTIME_OPERATOR_SET;
        operationsOut[7].operand = 0;
        *operationCountOut = 8;
        return TRUE;
    }
    return FALSE;
}

#include "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c"
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
#include "../src/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.c"
#endif

static OverworldWildRuntimeApplicabilityInput fixture_applicability(void)
{
    OverworldWildRuntimeApplicabilityInput input;

    memset(&input, 0, sizeof(input));
    input.immutableContextMask = 0xFFFFFFFFu;
    input.controllerId = 0x3001;
    input.boundNodeIds[0] = 0x4001;
    input.boundNodeIds[1] = 0x4100;
    input.boundNodeIds[2] = 0x4101;
    input.boundNodeIds[3] = 0x4107;
    input.boundNodeCount = 4;
    input.semanticRoleMask = OWBD_ROLE_MASK(1) | OWBD_ROLE_MASK(2)
        | OWBD_ROLE_MASK(3) | OWBD_ROLE_MASK(7);
    input.effectiveProfileId = 0x2201;
    input.effectiveSemanticRole = 2;
    return input;
}

static OverworldWildRuntimeStaticContext fixture_static_context(void)
{
    OverworldWildRuntimeStaticContext context;
    memset(&context, 0, sizeof(context));
    context.groupFlags = 0xFFFFFFFFu;
    context.level = 1;
    return context;
}

static void prepare_runtime_unprimed(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex)
{
    OverworldWildRuntime_Init(runtime);
    OverworldWildRuntime_MarkSlotAssigned(runtime, slotIndex);
    require(
        OverworldWildRuntime_BindPrivateIdentity(runtime)
            == OW_WILD_RUNTIME_STATUS_OK,
        "runtime identity bind failed");
}

static void prepare_runtime(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex)
{
    OverworldWildRuntimeApplicabilityInput input = fixture_applicability();
    OverworldWildRuntimeStaticContext context = fixture_static_context();
    prepare_runtime_unprimed(runtime, slotIndex);
    require(OverworldWildRuntime_PrimeEffectiveCache(runtime, (u8)slotIndex,
            runtime->slots[slotIndex].slotGeneration, &context, &input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "runtime static snapshot prime failed");
}

static void assign_and_prime(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex)
{
    OverworldWildRuntimeApplicabilityInput input = fixture_applicability();
    OverworldWildRuntimeStaticContext context = fixture_static_context();
    OverworldWildRuntime_MarkSlotAssigned(runtime, slotIndex);
    require(OverworldWildRuntime_PrimeEffectiveCache(runtime, (u8)slotIndex,
            runtime->slots[slotIndex].slotGeneration, &context, &input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "secondary slot static snapshot prime failed");
}

static void refresh_cache_identity(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex)
{
    OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
    if (!(slot->effectiveCache.flags & OW_WILD_RUNTIME_CACHE_VALID)) return;
    slot->effectiveCache.cacheIdentity = CacheIdentity(
        runtime, slot, &slot->effectiveCache, &slot->provenance,
        sOverworldWildRuntimeLayerService.privateRuntimeIdentity);
    slot->provenance.cacheIdentity = slot->effectiveCache.cacheIdentity;
}

static OverworldWildRuntimeLayerHandle apply_one(
    OverworldWildBehaviorStackRuntime *runtime,
    int slot,
    const OverworldWildRuntimeApplicabilityInput *input,
    u16 definition,
    u16 owner,
    u16 key)
{
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeStatus status = OverworldWildRuntime_Apply(
        runtime, slot, runtime->slots[slot].slotGeneration,
        input, definition, owner, key, &result);

    if (status != OW_WILD_RUNTIME_STATUS_OK)
        fprintf(stderr, "fixture apply definition=%04X owner=%04X status=%u\n",
            definition, owner, status);
    require(status == OW_WILD_RUNTIME_STATUS_OK, "fixture apply failed");
    require(result.ok && result.mutated, "fixture apply did not mutate");
    require(result.operationResultCount == 1, "fixture apply result count");
    return result.operationResults[0].handle;
}

static OverworldWildRuntimeDeltaOperation apply_op(
    u16 operationId,
    u16 definition,
    u16 owner,
    u16 key)
{
    OverworldWildRuntimeDeltaOperation operation;

    memset(&operation, 0, sizeof(operation));
    operation.operationId = operationId;
    operation.kind = OW_WILD_RUNTIME_DELTA_APPLY;
    operation.payload.apply.definitionId = definition;
    operation.payload.apply.ownerId = owner;
    operation.payload.apply.instanceKey = key;
    return operation;
}

static OverworldWildRuntimeDeltaOperation remove_op(
    u16 operationId,
    u8 kind,
    OverworldWildRuntimeLayerHandle handle)
{
    OverworldWildRuntimeDeltaOperation operation;

    memset(&operation, 0, sizeof(operation));
    operation.operationId = operationId;
    operation.kind = kind;
    operation.payload.handle = handle;
    return operation;
}

static void test_apply_replace_remove(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle handle;
    OverworldWildRuntimeLayerHandle replacement;
    u32 layerGeneration;

    prepare_runtime(&runtime, 0);
    handle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9001, 0);
    layerGeneration = runtime.slots[0].layerGeneration;
    before = runtime;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_SHARED, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_IDEMPOTENT,
        "identical apply was not idempotent");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "idempotent apply changed runtime bytes");
    require(result.operationResults[0].handle.validityTag == handle.validityTag,
        "idempotent apply did not return existing handle");
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_EXCLUSIVE, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_OWNER_KEY_OCCUPIED,
        "occupied key apply did not reject");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "occupied key rejection changed runtime bytes");
    require(
        OverworldWildRuntime_Replace(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, 0x9001, 0, DEF_SHARED, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "same-definition replace failed");
    replacement = result.operationResults[0].handle;
    require(replacement.entryGeneration != handle.entryGeneration,
        "replace reused entry generation");
    require(runtime.slots[0].layerGeneration == layerGeneration + 1,
        "replace did not advance layer generation once");
    before = runtime;
    require(
        OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &handle, &result) == OW_WILD_RUNTIME_STATUS_STALE_NOOP,
        "public stale remove did not return STALE_NOOP");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "stale public remove changed runtime bytes");
    require(
        OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &replacement, &result) == OW_WILD_RUNTIME_STATUS_OK,
        "live public remove failed");
    require(runtime.slots[0].activeLayerCount == 0,
        "live remove retained layer");
}

static void test_handles_and_atomicity(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime other;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle first;
    OverworldWildRuntimeLayerHandle second;
    OverworldWildRuntimeLayerHandle forged;
    OverworldWildRuntimeLayerHandle edited[15];
    int editedIndex;

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    first = apply_one(&runtime, 0, input, DEF_SHARED, 0x9001, 0);
    second = apply_one(&runtime, 0, input, DEF_SHARED, 0x9002, 0);
    before = runtime;
    forged = first;
    forged.ownerId = second.ownerId;
    require(
        OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &forged, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "public-field-edited handle was accepted");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "forged handle changed runtime bytes");
    for (editedIndex = 0; editedIndex < 15; editedIndex++)
        edited[editedIndex] = first;
    edited[0].runtimeEpoch++;
    edited[1].slotGeneration++;
    edited[2].entryGeneration++;
    edited[3].ownerId++;
    edited[4].instanceKey++;
    edited[5].slotIndex = 1;
    edited[6].validityTag ^= 1;
    edited[7].reserved[0] = 1;
    edited[8].reserved[1] = 1;
    edited[9].reserved[2] = 1;
    edited[10].runtimeEpoch = 0;
    edited[11].slotGeneration = 0;
    edited[12].entryGeneration = 0;
    edited[13].ownerId = 0;
    edited[14].validityTag = 0;
    for (editedIndex = 0; editedIndex < 15; editedIndex++) {
        before = runtime;
        require(OverworldWildRuntime_Remove(
                &runtime, 0, runtime.slots[0].slotGeneration,
                &edited[editedIndex], &result)
                == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
            "edited handle did not return INVALID_HANDLE");
        require(!memcmp(&runtime, &before, sizeof(runtime)),
            "edited handle changed runtime bytes");
    }
    forged = first;
    forged.slotIndex = 1;
    forged.validityTag = HandleTag(
        &runtime, forged.runtimeEpoch, forged.slotIndex,
        forged.slotGeneration, forged.ownerId, forged.instanceKey,
        forged.entryGeneration);
    require(
        OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &forged, &result) == OW_WILD_RUNTIME_STATUS_WRONG_SLOT,
        "authentic wrong-slot handle was not distinguished");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "wrong-slot handle changed runtime bytes");

    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 2;
    request.operations[0] = remove_op(
        1, OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED, first);
    request.operations[0].payload.handle.entryGeneration++;
    request.operations[0].payload.handle.validityTag = HandleTag(
        &runtime,
        request.operations[0].payload.handle.runtimeEpoch,
        request.operations[0].payload.handle.slotIndex,
        request.operations[0].payload.handle.slotGeneration,
        request.operations[0].payload.handle.ownerId,
        request.operations[0].payload.handle.instanceKey,
        request.operations[0].payload.handle.entryGeneration);
    request.operations[1] = apply_op(2, DEF_MULTI_INSTANCE, 0x9010, 1);
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_STALE_HANDLE,
        "required stale removal did not abort delta");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "required stale rejection changed runtime bytes");

    prepare_runtime(&other, 0);
    (void)apply_one(&other, 0, input, DEF_SHARED, 0x9001, 0);
    before = other;
    require(
        OverworldWildRuntime_Remove(
            &other, 0, other.slots[0].slotGeneration,
            &first, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "transplanted handle survived private runtime rebind");
    require(!memcmp(&other, &before, sizeof(other)),
        "transplanted handle changed destination runtime");
}

static void test_boundary_phase_late_slot_atomicity(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStatus status = OW_WILD_RUNTIME_STATUS_OK;
    u8 lastSlot = OW_WILD_MAX_SPAWNS - 1;
    u8 phase;
    u8 slotIndex;

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, lastSlot);
    (void)apply_one(&runtime, 0, input, DEF_EXCLUSIVE, 0x9001, 0);
    (void)apply_one(&runtime, lastSlot, input, DEF_EXCLUSIVE, 0x9002, 0);

    runtime.slots[lastSlot].staticCache.valid = FALSE;
    before = runtime;
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime.slots[slotIndex];
        if (slot->lifecycleState != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
            continue;
        status = OverworldWildRuntime_RemoveBoundaryPolicySlotPhase(
            &runtime, slotIndex, slot->slotGeneration,
            OW_WILD_RUNTIME_POLICY_BOUNDARY_MAP, TRUE);
        if (status != OW_WILD_RUNTIME_STATUS_OK
            && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) {
            break;
        }
    }
    require(status == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "late-slot boundary preflight did not propagate failure");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "late-slot boundary preflight changed runtime bytes");

    runtime.slots[lastSlot].staticCache.valid = TRUE;
    for (phase = 0; phase < 2; phase++) {
        for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
            OverworldWildRuntimeSlotSidecar *slot =
                &runtime.slots[slotIndex];
            if (slot->lifecycleState
                != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED) {
                continue;
            }
            status = OverworldWildRuntime_RemoveBoundaryPolicySlotPhase(
                &runtime, slotIndex, slot->slotGeneration,
                OW_WILD_RUNTIME_POLICY_BOUNDARY_MAP, phase == 0);
            require(status == OW_WILD_RUNTIME_STATUS_OK
                    || status == OW_WILD_RUNTIME_STATUS_IDEMPOTENT,
                "boundary phase rejected repaired runtime");
        }
    }
    require(runtime.slots[0].activeLayerCount == 0
            && runtime.slots[lastSlot].activeLayerCount == 0,
        "boundary commit retained clear-lifetime layers");
}

static void test_ambiguity_and_order(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime left;
    OverworldWildBehaviorStackRuntime right;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult resultLeft;
    OverworldWildRuntimeStackDeltaResult resultRight;
    OverworldWildRuntimeLayer layerLeft;
    OverworldWildRuntimeLayer layerRight;
    int index;

    prepare_runtime(&left, 0);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = left.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 2;
    request.operations[0] = apply_op(1, DEF_MULTI_INSTANCE, 0x9001, 1);
    request.operations[1] = apply_op(2, DEF_MULTI_INSTANCE, 0x9001, 1);
    before = left;
    require(
        OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "same-key duplicate was not ambiguous");
    require(!memcmp(&left, &before, sizeof(left)),
        "ambiguous delta changed bytes");
    request.operations[1].kind = OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT;
    memset(&request.operations[1].payload, 0,
        sizeof(request.operations[1].payload));
    request.operations[1].payload.owner.ownerId = 0x9001;
    require(
        OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "owner-wide overlap was not ambiguous");

    prepare_runtime(&left, 0);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = left.slots[0].slotGeneration;
    request.operationCount = 2;
    request.operations[0].operationId = 2;
    request.operations[0].kind = OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT;
    request.operations[0].payload.owner.ownerId = 0x9A01;
    request.operations[1] = request.operations[0];
    request.operations[1].operationId = 1;
    require(OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "duplicate absent owner selectors were accepted");
    request.operations[0].kind = OW_WILD_RUNTIME_DELTA_REMOVE_POLICY;
    memset(&request.operations[0].payload, 0,
        sizeof(request.operations[0].payload));
    request.operations[0].payload.policy.mapLifetime = 3;
    request.operations[1] = request.operations[0];
    request.operations[1].operationId = 1;
    require(OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "duplicate absent policy selectors were accepted");

    request.applicability = *input;
    request.operations[0] = apply_op(20, DEF_SHARED, 0x9A02, 0);
    request.operations[0].reserved = 1;
    request.operations[1] = apply_op(10, DEF_SHARED, 0x9A02, 0);
    before = left;
    require(OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "ambiguous malformed delta used array-order validation precedence");
    require(!memcmp(&left, &before, sizeof(left)),
        "ambiguous malformed delta changed bytes");
    {
        OverworldWildRuntimeDeltaOperation swap = request.operations[0];
        request.operations[0] = request.operations[1];
        request.operations[1] = swap;
    }
    require(OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "permuted malformed delta changed rejection status");

    prepare_runtime(&left, 0);
    request.expectedSlotGeneration = left.slots[0].slotGeneration;
    request.operationCount = 3;
    request.operations[0] = apply_op(10, DEF_MULTI_INSTANCE, 0x9003, 3);
    request.operations[1] = apply_op(30, DEF_MULTI_INSTANCE, 0x9001, 1);
    request.operations[2] = apply_op(20, DEF_MULTI_INSTANCE, 0x9002, 2);
    require(
        OverworldWildRuntime_ApplyStackDelta(&left, &request, &resultLeft)
            == OW_WILD_RUNTIME_STATUS_OK,
        "ordered delta failed");
    prepare_runtime(&right, 0);
    request.expectedSlotGeneration = right.slots[0].slotGeneration;
    request.operations[0] = apply_op(20, DEF_MULTI_INSTANCE, 0x9002, 2);
    request.operations[1] = apply_op(10, DEF_MULTI_INSTANCE, 0x9003, 3);
    request.operations[2] = apply_op(30, DEF_MULTI_INSTANCE, 0x9001, 1);
    require(
        OverworldWildRuntime_ApplyStackDelta(&right, &request, &resultRight)
            == OW_WILD_RUNTIME_STATUS_OK,
        "permuted delta failed");
    require(!memcmp(&left.slots[0].layerBank, &right.slots[0].layerBank,
        sizeof(left.slots[0].layerBank)),
        "permuted delta changed canonical bank/generations");
    for (index = 0; index < 3; index++) {
        require(
            OverworldWildRuntime_GetLayerByIndex(
                &right, 0, right.slots[0].slotGeneration,
                (u8)index, &layerRight) == OW_WILD_RUNTIME_STATUS_OK,
            "right enumeration failed");
        ReadLayer(&left.slots[0], (u8)index, &layerLeft);
        require(layerLeft.ownerId == layerRight.ownerId
                && layerLeft.instanceKey == layerRight.instanceKey
                && layerLeft.entryGeneration == layerRight.entryGeneration,
            "order-independent layer identity differs");
    }
}

static void test_multiplicity_capacity_and_clear(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle handles[8];
    int index;

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_EXCLUSIVE, 0x9001, 0);
    before = runtime;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_EXCLUSIVE, 0x9002, 0, &result)
            == OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED,
        "definition ownership was not enforced");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "definition ownership rejection changed bytes");
    require(
        OverworldWildRuntime_ClearAllForSlot(
            &runtime, 0, runtime.slots[0].slotGeneration, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "clear failed");
    require(runtime.slots[0].activeLayerCount == 0,
        "clear retained layers");
    before = runtime;
    require(
        OverworldWildRuntime_ClearAllForSlot(
            &runtime, 0, runtime.slots[0].slotGeneration, &result)
            == OW_WILD_RUNTIME_STATUS_IDEMPOTENT,
        "empty clear was not idempotent");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "empty clear changed bytes");

    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 9;
    for (index = 0; index < 9; index++)
        request.operations[index] = apply_op(
            (u16)(index + 1), DEF_EXCLUSIVE, (u16)(0x9100 + index), 0);
    before = runtime;
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED,
        "capacity masked final multiplicity rejection");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "pre-capacity multiplicity rejection changed bytes");

    for (index = 0; index < 8; index++) {
        handles[index] = apply_one(
            &runtime, 0, input, DEF_MULTI_INSTANCE,
            0x9010, (u16)index);
    }
    before = runtime;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_SHARED, 0x9020, 0, &result)
            == OW_WILD_RUNTIME_STATUS_CAPACITY_EXCEEDED,
        "ninth layer did not reject capacity");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "capacity rejection changed bytes");
    require(
        OverworldWildRuntime_Replace(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, 0x9010, 4, DEF_MULTI_INSTANCE, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "replace at capacity failed");
    require(result.operationResults[0].handle.entryGeneration
            != handles[4].entryGeneration,
        "replace at capacity reused identity");
}

static void test_generated_applicability_and_generation(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeApplicabilityInput wrong = *input;
    OverworldWildRuntimeApplicabilityInput fallback = *input;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle fled;
    OverworldWildRuntimeLayer layer;

    prepare_runtime(&runtime, 0);
    before = runtime;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_STAMINA, 0x9999, 0, &result)
            == OW_WILD_RUNTIME_STATUS_OWNER_NOT_AUTHORIZED,
        "required owner authorization was not enforced");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "owner authorization rejection changed bytes");
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_FLED, 0x8107, 1, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER,
        "generated nonzero key used ordinary key status");
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_BAD_GENERATED, 0x8107, 0, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER,
        "malformed generated wrapper was accepted");
    wrong.controllerId = 0x3002;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &wrong, DEF_EXACT, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE,
        "controller applicability mismatch was accepted");
    fled = apply_one(&runtime, 0, input, DEF_FLED, 0x8107, 0);
    require(
        OverworldWildRuntime_FindLayer(
            &runtime, 0, runtime.slots[0].slotGeneration,
            0x8107, 0, &layer, &fled) == OW_WILD_RUNTIME_STATUS_OK,
        "generated layer lookup failed");
    require(layer.hasTiredOriginKind && layer.tiredOriginKind == 1
            && layer.hasRequiredOwnerId && layer.requiredOwnerId == 0x8107,
        "generated metadata was not copied from catalog");
    fallback.semanticRoleMask &= ~OWBD_ROLE_MASK(OWBD_ROLE_TIRED);
    require(
        OverworldWildRuntime_Replace(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &fallback, 0x8107, 0, DEF_FLED_EXACT, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "fallback tired-translation branch bypassed canonical roster authentication");
    require(
        OverworldWildRuntime_Replace(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, 0x8107, 0, DEF_FLED_EXACT, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION,
        "authored tired branch accepted the fallback wrapper");
    require(
        OverworldWildRuntime_Replace(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &fallback, 0x8107, 0, DEF_FLED, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION,
        "fallback tired branch accepted the authored wrapper");
    require(
        OverworldWildRuntime_Replace(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, 0x8107, 0, DEF_ORDINARY_TIRED, &result)
            == OW_WILD_RUNTIME_STATUS_GENERATED_WRAPPER_FAMILY_MISMATCH,
        "cross-family replace was accepted");

    (void)apply_one(&runtime, 0, input, DEF_SHARED, 0x9002, 0);
    before = runtime;
    runtime.slots[0].nextEntryGeneration = 0xFFFFFFFFu;
    before = runtime;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_MULTI_INSTANCE, 0x9010, 1, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "entry wrap rekey apply failed");
    require(runtime.handleEpoch == before.handleEpoch + 1,
        "entry wrap did not advance epoch");
    require(runtime.slots[0].layerGeneration
            == before.slots[0].layerGeneration + 1,
        "entry wrap advanced target layer generation more than once");
    {
        OverworldWildRuntimeStatus staleStatus = OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration, &fled, &result);
        if (staleStatus != OW_WILD_RUNTIME_STATUS_INVALID_HANDLE)
            fprintf(stderr, "pre-rekey stale status=%u epoch=%lu handle=%lu\n",
                staleStatus, (unsigned long)runtime.handleEpoch,
                (unsigned long)fled.runtimeEpoch);
        require(staleStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "pre-rekey handle remained usable");
    }
}

static void test_role_mask_boundaries(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeApplicabilityInput boundary = *input;
    OverworldWildRuntimeStackDeltaResult result;

    prepare_runtime(&runtime, 0);
    boundary = *input;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &boundary,
            DEF_CALM, 0x9301, 0, &result) == OW_WILD_RUNTIME_STATUS_OK,
        "role 1 did not map to semantic-mask bit 0");
    require(OverworldWildRuntime_ClearAllForSlot(
            &runtime, 0, runtime.slots[0].slotGeneration, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "role boundary cleanup failed");
    boundary = *input;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &boundary,
            DEF_CUSTOM, 0x9302, 0, &result) == OW_WILD_RUNTIME_STATUS_OK,
        "role 7 did not map to semantic-mask bit 6");
    require(OverworldWildRuntime_ClearAllForSlot(
            &runtime, 0, runtime.slots[0].slotGeneration, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "custom-role boundary cleanup failed");
    boundary.semanticRoleMask = OWBD_ROLE_MASK(OWBD_ROLE_FOLLOWER);
    before = runtime;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &boundary,
            DEF_CUSTOM, 0x9302, 0, &result)
            == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE,
        "adjacent role bit matched role 7");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "wrong role bit changed runtime bytes");
    boundary.semanticRoleMask = 0x80;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &boundary,
            DEF_CUSTOM, 0x9302, 0, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "out-of-range semantic-role mask bit was accepted");
}

static void test_batch_policy_owner_and_lifecycle(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle shared;
    OverworldWildRuntimeLayerHandle stale;
    u32 layerGeneration;
    u32 effectiveGeneration;

    prepare_runtime(&runtime, 0);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 3;
    request.operations[0] = apply_op(3, DEF_MULTI_INSTANCE, 0x9002, 2);
    request.operations[1] = apply_op(1, DEF_MULTI_INSTANCE, 0x9002, 0);
    request.operations[2] = apply_op(2, DEF_MULTI_INSTANCE, 0x9002, 1);
    layerGeneration = runtime.slots[0].layerGeneration;
    effectiveGeneration = runtime.slots[0].effectiveGeneration;
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "multi-apply batch failed");
    require(runtime.slots[0].layerGeneration == layerGeneration + 1,
        "changing batch did not advance layer generation exactly once");
    require(runtime.slots[0].effectiveGeneration == effectiveGeneration + 1,
        "Task-9 visible batch did not advance effective generation once");
    require(
        OverworldWildRuntime_RemoveOwner(
            &runtime, 0, runtime.slots[0].slotGeneration,
            0x9002, &result) == OW_WILD_RUNTIME_STATUS_OK,
        "owner removal failed");
    require(runtime.slots[0].activeLayerCount == 0,
        "owner removal did not remove every exact-owner layer");

    shared = apply_one(&runtime, 0, input, DEF_SHARED, 0x9010, 0);
    (void)apply_one(&runtime, 0, input, DEF_MULTI_INSTANCE, 0x9011, 0);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.operationCount = 1;
    request.operations[0].operationId = 1;
    request.operations[0].kind = OW_WILD_RUNTIME_DELTA_REMOVE_POLICY;
    request.operations[0].payload.policy.mapLifetime = 2;
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "policy removal failed");
    require(runtime.slots[0].activeLayerCount == 1
            && runtime.slots[0].layerBank.ownerIds[0] == 0x9011,
        "policy removal touched the wrong lifetime set");
    before = runtime;
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.operationCount = 2;
    request.operations[0].operationId = 1;
    request.operations[0].kind = OW_WILD_RUNTIME_DELTA_CLEAR;
    request.operations[1] = apply_op(2, DEF_SHARED, 0x9020, 0);
    request.applicability = *input;
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "CLEAR combined with another op was accepted");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "CLEAR ambiguity changed bytes");

    stale = shared;
    stale.entryGeneration++;
    stale.validityTag = HandleTag(
        &runtime, stale.runtimeEpoch, stale.slotIndex,
        stale.slotGeneration, stale.ownerId, stale.instanceKey,
        stale.entryGeneration);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    before = runtime;
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_IDEMPOTENT,
        "empty delta was not idempotent");
    require(result.operationResultCount == 0 && result.ok && !result.mutated,
        "empty delta returned noncanonical result metadata");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "empty delta changed runtime bytes");
    request.operationCount = 2;
    request.operations[0] = remove_op(
        1, OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT, stale);
    request.operations[1] = apply_op(2, DEF_MULTI_INSTANCE, 0x9030, 1);
    layerGeneration = runtime.slots[0].layerGeneration;
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "optional stale plus valid add did not commit");
    require(result.operationResults[0].status
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !result.operationResults[0].matched,
        "optional stale batch result was not explicit");
    require(runtime.slots[0].layerGeneration == layerGeneration + 1,
        "optional stale mixed batch advanced layer generation incorrectly");

    before = runtime;
    request.expectedSlotGeneration++;
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH,
        "expected slot generation mismatch was accepted");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "generation mismatch changed bytes");
    runtime.slots[0].lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
    before = runtime;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    require(
        OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT,
        "inactive slot mutation was accepted");
    require(!memcmp(&runtime, &before, sizeof(runtime)),
        "inactive slot rejection changed bytes");
}

static void test_global_rekey_and_terminal_restart(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle targetHandle;
    OverworldWildRuntimeLayerHandle otherHandle;
    u32 otherLayerGeneration;
    u32 emptyBystanderIncarnation;
    u32 dataIncarnation;
    OverworldWildRuntimeStaticContext changedContext =
        fixture_static_context();

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    targetHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9001, 0);
    otherHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9002, 0);
    otherLayerGeneration = runtime.slots[1].layerGeneration;
    emptyBystanderIncarnation = runtime.slots[2].cacheIncarnation;
    dataIncarnation = runtime.dataIncarnation;
    runtime.slots[0].nextEntryGeneration = 0xFFFFFFFFu;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_MULTI_INSTANCE, 0x9010, 1, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "global rekey trigger failed");
    require(runtime.slots[1].layerGeneration == otherLayerGeneration + 1,
        "global rekey did not advance surviving other slot once");
    require(runtime.dataIncarnation != dataIncarnation
            && runtime.slots[2].cacheIncarnation
                != emptyBystanderIncarnation,
        "global rekey reused data/empty-bystander cache incarnation");
    require(runtime.slots[1].layerBank.entryGenerations[0] == 1,
        "global rekey did not assign canonical nonzero other identity");
    before = runtime;
    changedContext.species = 1;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 1,
            runtime.slots[1].slotGeneration, &changedContext, input)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "retained-static bystander rekey accepted a changed context");
    changedContext = fixture_static_context();
    changedContext.reserved = 1;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 1,
            runtime.slots[1].slotGeneration, &changedContext, input)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "retained-static bystander rekey accepted reserved context bytes");
    require(
        OverworldWildRuntime_Remove(
            &runtime, 1, runtime.slots[1].slotGeneration,
            &otherHandle, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "global rekey left another-slot handle usable");
    require(
        OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &targetHandle, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "global rekey left target handle usable");

    runtime.handleEpoch = 0xFFFFFFFFu;
    runtime.slots[0].nextEntryGeneration = 0xFFFFFFFFu;
    before = runtime;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_MULTI_INSTANCE, 0x9020, 2, &result)
            == OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED,
        "terminal epoch did not return restart status");
    require(result.ok && result.mutated && result.operationResultCount == 0,
        "terminal restart result shape differs");
    require(runtime.handleEpoch == 1,
        "terminal restart did not reset epoch to one");
    require(runtime.slots[0].activeLayerCount == 0
            && runtime.slots[1].activeLayerCount == 0,
        "terminal restart did not clear every slot");
    require(runtime.slots[0].slotGeneration
            == OverworldWildRuntime_AdvanceNonzeroGeneration(
                before.slots[0].slotGeneration),
        "terminal restart did not advance slot identity");
}

static void test_task7_destructive_wrap_rekey(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle targetHandle;
    OverworldWildRuntimeLayerHandle survivorHandle;
    u32 survivorLayerGeneration;

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    targetHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9101, 0);
    survivorHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9102, 0);
    survivorLayerGeneration = runtime.slots[1].layerGeneration;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    refresh_cache_identity(&runtime, 0);
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == targetHandle.runtimeEpoch + 1,
        "Task-7 slot wrap did not advance the runtime epoch");
    require(runtime.slots[0].activeLayerCount == 0
            && runtime.slots[0].slotGeneration == 1,
        "Task-7 slot wrap did not invalidate the target slot");
    require(runtime.slots[1].activeLayerCount == 1
            && runtime.slots[1].layerBank.ownerIds[0] == 0x9102
            && runtime.slots[1].layerGeneration == survivorLayerGeneration + 1,
        "Task-7 slot wrap did not atomically rekey the surviving slot");
    require(OverworldWildRuntime_Remove(
            &runtime, 1, runtime.slots[1].slotGeneration,
            &survivorHandle, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "Task-7 slot wrap left a surviving-slot handle usable");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 0, input, DEF_SHARED, 0x9151, 0);
    survivorHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9152, 0);
    runtime.handleEpoch = 0xFFFFFFFEu;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    refresh_cache_identity(&runtime, 0);
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == 0xFFFFFFFFu
            && runtime.slots[1].activeLayerCount == 1,
        "Task-7 max-minus-one epoch wrap restarted one epoch too early");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    targetHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9201, 0);
    survivorHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9202, 0);
    runtime.handleEpoch = 0xFFFFFFFFu;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == 1
            && runtime.slots[0].activeLayerCount == 0
            && runtime.slots[1].activeLayerCount == 0,
        "Task-7 terminal epoch restart did not clear every slot");
    assign_and_prime(&runtime, 1);
    require(OverworldWildRuntime_Remove(
            &runtime, 1, runtime.slots[1].slotGeneration,
            &survivorHandle, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "Task-7 terminal restart did not rotate private validity material");
}

static void test_task7_corrupt_wrap_invalidation(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    u32 epoch;

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    runtime.slots[1].activeLayerCount =
        OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT + 1;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    epoch = runtime.handleEpoch;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == epoch + 1
            && runtime.slots[0].activeLayerCount == 0
            && runtime.slots[1].activeLayerCount == 0,
        "out-of-range layer count was normalized during slot wrap");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 1, input, DEF_SHARED, 0x9501, 0);
    runtime.slots[1].layerBank.entryGenerations[0] = 0;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[1].activeLayerCount == 0,
        "zero survivor entry generation was normalized during slot wrap");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 1, input, DEF_MULTI_INSTANCE, 0x9502, 0);
    (void)apply_one(&runtime, 1, input, DEF_MULTI_INSTANCE, 0x9502, 1);
    runtime.slots[1].layerBank.entryGenerations[1] =
        runtime.slots[1].layerBank.entryGenerations[0];
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[1].activeLayerCount == 0,
        "duplicate survivor entry generation was normalized during slot wrap");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 1, input, DEF_FLED, 0x8107, 0);
    runtime.slots[1].layerBank.ownerIds[0] = 0x9503;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[1].activeLayerCount == 0,
        "unauthorized surviving required-owner layer was rekeyed");

    prepare_runtime(&runtime, 0);
    runtime.handleEpoch = 0xFFFFFFFFu;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    runtime.slots[0].activeLayerCount = 0xFF;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == 1
            && runtime.slots[0].activeLayerCount == 0,
        "terminal slot wrap inspected corrupt layers before direct restart");
}

static void test_canonical_preflight_and_restart(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeApplicabilityInput changed;
    OverworldWildRuntimeStaticContext staticContext = fixture_static_context();
    OverworldWildRuntimeLayerHandle handle;
    u8 savedFlags;

    prepare_runtime(&runtime, 0);
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, input,
            0x7FFF, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION,
        "missing definition was not rejected");
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, input,
            DEF_INELIGIBLE, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION,
        "runtime-ineligible definition was not rejected");
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, input,
            DEF_EXCLUSIVE, 0x9001, 1, &result)
            == OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED,
        "ordinary definition accepted a nonzero instance key");

    changed = *input;
    changed.effectiveProfileId++;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &changed,
            DEF_MULTI_INSTANCE, 0x9001, 1, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "caller-selected unrelated profile replaced authenticated binding");
    changed = *input;
    changed.effectiveSemanticRole++;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &changed,
            DEF_MULTI_INSTANCE, 0x9001, 2, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "caller-selected unrelated role replaced authenticated binding");
    require(runtime.slots[0].activeLayerCount == 0,
        "rejected caller binding published a dormant modifier");

    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 2;
    request.operations[0] = apply_op(7, DEF_SHARED, 0x9001, 0);
    request.operations[1] = apply_op(7, DEF_SHARED, 0x9002, 0);
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "duplicate operation IDs were accepted");
    request.operationCount = OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS + 1;
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "out-of-range operation count was accepted");
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 1;
    request.operations[0] = apply_op(1, DEF_SHARED, 0x9001, 0);
    request.operations[0].kind = OW_WILD_RUNTIME_DELTA_CLEAR + 1;
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "invalid operation discriminator was accepted");
    request.operations[0] = apply_op(1, DEF_SHARED, 0x9001, 0);
    request.operations[1] = apply_op(2, DEF_SHARED, 0x9002, 0);
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "nonzero unused operation storage was accepted");

    handle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9001, 0);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 2;
    request.operations[0] = remove_op(
        1, OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED, handle);
    request.operations[1] = apply_op(2, DEF_SHARED, 0x9001, 0);
    require(OverworldWildRuntime_ApplyStackDelta(&runtime, &request, &result)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA,
        "remove-plus-apply of one owner/key was accepted");

    savedFlags = sFixtureCatalog.definitions[0].flags;
    sFixtureCatalog.definitions[0].flags = 0;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, input,
            DEF_SHARED, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION,
        "idempotent Apply skipped definition reauthorization");
    sFixtureCatalog.definitions[0].flags = savedFlags;
    runtime.slots[0].layerBank.generatedFlags[0] =
        OW_WILD_RUNTIME_GENERATED_FLAG_HAS_REQUIRED_OWNER;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, input,
            DEF_SHARED, 0x9001, 0, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER,
        "idempotent Apply accepted stale stored generated metadata");
    runtime.slots[0].layerBank.generatedFlags[0] = 0;

    OverworldWildRuntime_MarkResidentCold(&runtime);
    require(OverworldWildRuntime_BindPrivateIdentity(&runtime)
            == OW_WILD_RUNTIME_STATUS_OK,
        "cold restart identity did not rotate");
    OverworldWildRuntime_Activate(&runtime);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "cold restart did not establish a fresh static snapshot");
    require(OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration, &handle, &result)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "cold restart left an old handle usable");
}

static void test_forced_zero_identity_rotation(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle betweenHandle;
    OverworldWildRuntimeStaticContext staticContext = fixture_static_context();
    u32 firstIdentity;

    prepare_runtime(&runtime, 0);
    OverworldWildRuntime_MarkResidentCold(&runtime);
    sOverworldWildRuntimeForceZeroMix = TRUE;
    require(OverworldWildRuntime_BindPrivateIdentity(&runtime)
            == OW_WILD_RUNTIME_STATUS_OK,
        "first consecutive forced-zero private identity bind failed");
    sOverworldWildRuntimeForceZeroMix = FALSE;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "first forced-zero static snapshot prime failed");
    firstIdentity = sOverworldWildRuntimeLayerService.privateRuntimeIdentity;
    betweenHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9401, 0);
    OverworldWildRuntime_MarkResidentCold(&runtime);
    sOverworldWildRuntimeForceZeroMix = TRUE;
    require(OverworldWildRuntime_BindPrivateIdentity(&runtime)
            == OW_WILD_RUNTIME_STATUS_OK,
        "second consecutive forced-zero private identity bind failed");
    sOverworldWildRuntimeForceZeroMix = FALSE;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "second forced-zero static snapshot prime failed");
    require(sOverworldWildRuntimeLayerService.privateRuntimeIdentity != 0,
        "forced-zero Mix published a zero private identity");
    require(sOverworldWildRuntimeLayerService.privateRuntimeIdentity
            != firstIdentity,
        "consecutive forced-zero binds reused private identity");
    require(OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &betweenHandle, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "handle minted between forced-zero binds remained authenticated");
    (void)apply_one(&runtime, 0, input, DEF_SHARED, 0x9402, 0);
}

static void run_task6_crosscheck_corpus(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeLayerHandle handle;
    OverworldWildRuntimeStatus statuses[6];

    prepare_runtime(&runtime, 0);
    statuses[0] = OverworldWildRuntime_Apply(
        &runtime, 0, runtime.slots[0].slotGeneration, input,
        DEF_SHARED, 0x9001, 0, &result);
    handle = result.operationResults[0].handle;
    statuses[1] = OverworldWildRuntime_Apply(
        &runtime, 0, runtime.slots[0].slotGeneration, input,
        DEF_SHARED, 0x9001, 0, &result);
    statuses[2] = OverworldWildRuntime_Apply(
        &runtime, 0, runtime.slots[0].slotGeneration, input,
        DEF_EXCLUSIVE, 0x9001, 0, &result);
    statuses[3] = OverworldWildRuntime_Replace(
        &runtime, 0, runtime.slots[0].slotGeneration, input,
        0x9002, 0, DEF_SHARED, &result);
    handle.entryGeneration++;
    statuses[4] = OverworldWildRuntime_Remove(
        &runtime, 0, runtime.slots[0].slotGeneration, &handle, &result);
    memset(&request, 0, sizeof(request));
    request.slotIndex = 0;
    request.expectedSlotGeneration = runtime.slots[0].slotGeneration;
    request.applicability = *input;
    request.operationCount = 2;
    request.operations[0] = apply_op(1, DEF_SHARED, 0x9003, 0);
    request.operations[1] = apply_op(2, DEF_SHARED, 0x9003, 0);
    request.operations[1].kind = OW_WILD_RUNTIME_DELTA_REPLACE;
    statuses[5] = OverworldWildRuntime_ApplyStackDelta(
        &runtime, &request, &result);
    printf(
        "TASK6_CORPUS statuses=%u,%u,%u,%u,%u,%u count=%u layerGeneration=%lu\n",
        statuses[0], statuses[1], statuses[2], statuses[3], statuses[4],
        statuses[5], runtime.slots[0].activeLayerCount,
        (unsigned long)runtime.slots[0].layerGeneration);
}

static void test_task5_v40_scalar_domains(void)
{
    static const u8 body1202[28] = {
        3, 1, 9, 2, 32, 2, 0, 15, 1, 1, 2, 40, 4, 0,
        9, 30, 3, 4, 0, 0, 2, 1, 1, 0, 0, 0, 0, 15,
    };
    static const u8 body1209[28] = {
        11, 0, 0, 2, 32, 2, 0, 15, 1, 1, 2, 40, 4, 0,
        9, 30, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15,
    };
    u8 values[28];

    (void)OwbdValidateStream;

    require(OwbdStateValuesValid(body1202)
            && OwbdStateValuesValid(body1209),
        "production bodies 0x1202/0x1209 failed shared Task-5 domains");
    memcpy(values, body1202, sizeof(values));
    values[0] = 8;
    require(OwbdStateValuesValid(values), "behavior kind 8 was rejected");
    values[0] = 9;
    require(!OwbdStateValuesValid(values), "behavior kind gap 9 was accepted");
    values[0] = 10;
    require(OwbdStateValuesValid(values), "behavior kind 10 was rejected");
    values[0] = 11;
    require(OwbdStateValuesValid(values), "behavior kind 11 was rejected");
    values[0] = 12;
    require(!OwbdStateValuesValid(values), "behavior kind 12 was accepted");
    require(OwbdStaticValueValid(4, 2, 6)
            && !OwbdStaticValueValid(4, 2, 7)
            && OwbdStaticValueValid(4, 2, 8)
            && OwbdStaticValueValid(4, 2, 9)
            && !OwbdStaticValueValid(4, 2, 10),
        "target enum boundaries/gap diverged from Task 5");
    require(OwbdStaticValueValid(4, 6, 5)
            && !OwbdStaticValueValid(4, 6, 6)
            && !OwbdStaticValueValid(4, 7, 14)
            && OwbdStaticValueValid(4, 7, 15),
        "tile enum gaps diverged from Task 5");
    require(OwbdStaticValueValid(4, 3, 0)
            && OwbdStaticValueValid(4, 3, 4)
            && !OwbdStaticValueValid(4, 3, 5)
            && OwbdStaticValueValid(4, 5, 2)
            && !OwbdStaticValueValid(4, 5, 3)
            && OwbdStaticValueValid(4, 23, 2)
            && !OwbdStaticValueValid(4, 23, 3)
            && OwbdStaticValueValid(4, 26, 2)
            && !OwbdStaticValueValid(4, 26, 3),
        "state scalar boundaries diverged from Task 5");
    require(OwbdStaticValueValid(5, 1, 2)
            && !OwbdStaticValueValid(5, 1, 3)
            && OwbdStaticValueValid(5, 2, 10)
            && !OwbdStaticValueValid(5, 2, 11)
            && !OwbdStaticValueValid(5, 2, 254)
            && OwbdStaticValueValid(5, 2, 255)
            && OwbdStaticValueValid(5, 5, 5)
            && !OwbdStaticValueValid(5, 5, 6),
        "controller enum boundaries/gaps diverged from Task 5");
}

static void test_task9_composition_cache_and_provenance(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeEffectiveCache cache;
    OverworldWildRuntimeEffectiveCache copied;
    OverworldWildRuntimeProvenance provenance;
    OverworldWildRuntimeSlotSidecar bystander;
    OverworldWildRuntimeStaticCache hostileConfiguration;
    OverworldWildRuntimeLayerHandle high;
    OverworldWildRuntimeLayerHandle low;
    OverworldWildRuntimeStatus status;
    OverworldWildRuntimeApplicabilityInput staticInput = *input;
    OverworldWildRuntimeApplicabilityInput wrongInput = *input;
    OverworldWildRuntimeStaticContext staticContext = fixture_static_context();
    OverworldWildRuntimeStaticContext changedContext = fixture_static_context();
    u32 capabilities;
    u32 visibleEffective;
    u32 hiddenCapabilities;
    u32 hiddenEffective;
    u32 firstCacheIdentity;
    u32 firstDataIncarnation;
    u32 firstSlotIncarnation;
    u32 priorSlotGeneration;
    u8 speedZeroStatus;
    u8 avoidSetTwoStatus;
    u8 avoidAddStatus;
    u8 wide33;
    u8 wideMinimum;
    u8 wideMaximum;
    u8 conflictStatus;
    u8 i;

    prepare_runtime_unprimed(&runtime, 0);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "static-only composition failed");
    require(runtime.slots[0].layerGeneration == 1
            && runtime.slots[0].effectiveGeneration == 1,
        "static-only composition advanced a generation");
    require(runtime.slots[0].staticCache.spawnConfiguration.minimumDistance
                == 1
            && runtime.slots[0].staticCache.spawnConfiguration.maximumDistance
                == 1
            && runtime.slots[0].staticCache.spawnConfiguration.populationLimit
                == 1,
        "spawn configuration was not retained in the static cache");
    hostileConfiguration = runtime.slots[0].staticCache;
    hostileConfiguration.spawnConfiguration.populationLimit = 11;
    hostileConfiguration.staticSetHash = fixture_mix(0x4F575339u,
        hostileConfiguration.catalogIdentity);
    hostileConfiguration.staticSetHash = fixture_mix(
        hostileConfiguration.staticSetHash,
        hostileConfiguration.staticContextIdentity);
    hostileConfiguration.staticSetHash = fixture_hash_bytes(
        hostileConfiguration.staticSetHash,
        &hostileConfiguration.immutableContextMask,
        sizeof(hostileConfiguration)
            - offsetof(OverworldWildRuntimeStaticCache,
                immutableContextMask));
    require(hostileConfiguration.staticSetHash
                != runtime.slots[0].staticCache.staticSetHash
            && OverworldWildRuntime_ValidateStaticCache(
                &hostileConfiguration,
                runtime.slots[0].staticContextGeneration)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "spawn configuration was not authenticated or domain validated");
    require(OverworldWildRuntime_GetEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &cache)
            == OW_WILD_RUNTIME_STATUS_OK
            && cache.profileId == input->effectiveProfileId
            && cache.stateValues[3] == 2,
        "static-only effective cache is not canonical");
    copied = cache;
    copied.stateValues[3] = 99;
    require(OverworldWildRuntime_GetEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &copied)
            == OW_WILD_RUNTIME_STATUS_OK && copied.stateValues[3] == 2,
        "effective query exposed mutable cache storage");
    require(OverworldWildRuntime_GetCapabilityMask(&runtime, 0,
            runtime.slots[0].slotGeneration, &capabilities)
            == OW_WILD_RUNTIME_STATUS_OK
            && capabilities == cache.capabilityMask,
        "O(1) capability query missed the validated cache");
    firstCacheIdentity = cache.cacheIdentity;

    prepare_runtime_unprimed(&runtime, 0);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_GetEffectiveCache(&runtime, 0,
                runtime.slots[0].slotGeneration, &cache)
                == OW_WILD_RUNTIME_STATUS_OK,
        "retained-static hostile fixture could not restore clean state");
    firstCacheIdentity = cache.cacheIdentity;
    before = runtime;
    wrongInput.effectiveProfileId++;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, &wrongInput)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "prime returned IDEMPOTENT for a mismatched authenticated binding");
    changedContext.species = 1;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &changedContext, input)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "effective-cache hit accepted changed immutable context bytes");
    wrongInput = *input;
    wrongInput.immutableContextMask ^= 1u;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, &wrongInput)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "caller immutable mask authenticated itself");
    wrongInput = *input;
    wrongInput.boundNodeIds[1] = 0x4200;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, &wrongInput)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "caller node roster authenticated itself");
    wrongInput = *input;
    wrongInput.semanticRoleMask ^= OWBD_ROLE_MASK(OWBD_ROLE_CUSTOM);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, &wrongInput)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "caller role roster authenticated itself");
    wrongInput = *input;
    wrongInput.effectiveSemanticRole = OWBD_ROLE_CALM;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, &wrongInput)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "caller base role authenticated itself or changed runtime bytes");

    sFixtureCatalogIdentity = 0;
    memset(&copied, 0xA5, sizeof(copied));
    require(OverworldWildRuntime_GetEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &copied)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && !memcmp(&copied, &(OverworldWildRuntimeEffectiveCache){0},
                sizeof(copied))
            && OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
                runtime.slots[0].slotGeneration, &staticContext, input)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "released catalog returned cached data or IDEMPOTENT prime");
    sFixtureCatalogIdentity = 0xC88892BEu ^ 1u;
    capabilities = 0xFFFFFFFFu;
    require(OverworldWildRuntime_GetCapabilityMask(&runtime, 0,
            runtime.slots[0].slotGeneration, &capabilities)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && capabilities == 0,
        "replacement catalog returned a stale capability cache");
    sFixtureCatalogIdentity = 0xC88892BEu;

    runtime.slots[0].staticContextGeneration++;
    memset(&copied, 0xA5, sizeof(copied));
    memset(&provenance, 0xA5, sizeof(provenance));
    capabilities = 0xFFFFFFFFu;
    require(OverworldWildRuntime_GetEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &copied)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && OverworldWildRuntime_GetCapabilityMask(&runtime, 0,
                runtime.slots[0].slotGeneration, &capabilities)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && OverworldWildRuntime_GetProvenance(&runtime, 0,
                runtime.slots[0].slotGeneration, &provenance)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && capabilities == 0
            && !memcmp(&copied, &(OverworldWildRuntimeEffectiveCache){0},
                sizeof(copied))
            && !memcmp(&provenance, &(OverworldWildRuntimeProvenance){0},
                sizeof(provenance))
            && OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
                runtime.slots[0].slotGeneration, &staticContext, input)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
        "static-context generation change returned stale query/prime data");
    runtime.slots[0].staticContextGeneration--;

    before = runtime;
    sFixtureCatalogIdentity ^= 1u;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input, DEF_HIGH_STATE,
            0x94FF, 0, &result) == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "catalog identity mismatch changed live bytes");
    sFixtureCatalogIdentity ^= 1u;

    high = apply_one(&runtime, 0, input, DEF_HIGH_STATE, 0x9501, 0);
    require(runtime.slots[0].layerGeneration == 2
            && runtime.slots[0].effectiveGeneration == 2
            && runtime.slots[0].effectiveCache.nodeId == 0x4100
            && runtime.slots[0].effectiveCache.profileId == 0x2301
            && runtime.slots[0].effectiveCache.stateValues[3] == 3,
        "runtime non-base winner bypassed the resolved roster body");
    hiddenEffective = runtime.slots[0].effectiveGeneration;
    hiddenCapabilities = runtime.slots[0].effectiveCache.capabilityMask;
    low = apply_one(&runtime, 0, input, DEF_LOW_STATE, 0x9502, 0);
    require(runtime.slots[0].layerGeneration == 3
            && runtime.slots[0].effectiveGeneration == hiddenEffective
            && runtime.slots[0].effectiveCache.capabilityMask
                == hiddenCapabilities,
        "hidden lower candidate changed effective generation/capabilities");
    require(OverworldWildRuntime_GetProvenance(&runtime, 0,
            runtime.slots[0].slotGeneration, &provenance)
            == OW_WILD_RUNTIME_STATUS_OK
            && provenance.candidateCount == 3
            && provenance.winningDefinitionId == DEF_HIGH_STATE
            && provenance.candidates[0].definitionId == DEF_HIGH_STATE
            && provenance.candidates[0].isWinner
            && provenance.candidates[1].definitionId == 0
            && !provenance.candidates[1].isWinner
            && provenance.candidates[2].definitionId == DEF_LOW_STATE
            && !provenance.candidates[2].isWinner,
        "hidden candidate did not refresh winner/candidate provenance");
    (void)apply_one(&runtime, 0, input, DEF_ORDER_A, 0x9600, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDER_B, 0x9400, 0);
    require(OverworldWildRuntime_GetProvenance(&runtime, 0,
            runtime.slots[0].slotGeneration, &provenance)
            == OW_WILD_RUNTIME_STATUS_OK
            && provenance.candidateCount == 5
            && provenance.candidates[0].definitionId == DEF_HIGH_STATE
            && provenance.candidates[1].definitionId == 0
            && provenance.candidates[2].definitionId == DEF_LOW_STATE
            && provenance.candidates[3].definitionId == DEF_ORDER_A
            && provenance.candidates[3].ownerId == 0x9600
            && provenance.candidates[4].definitionId == DEF_ORDER_B
            && provenance.candidates[4].ownerId == 0x9400,
        "winner-first/global explained order ignored definition before owner");
    for (i = 0; i < provenance.candidateCount; i++)
        require(provenance.candidates[i].isWinner == (i == 0),
            "candidate provenance published an incorrect isWinner flag");
    require(OverworldWildRuntime_RemoveOwner(&runtime, 0,
            runtime.slots[0].slotGeneration, 0x9600, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_RemoveOwner(&runtime, 0,
                runtime.slots[0].slotGeneration, 0x9400, &result)
                == OW_WILD_RUNTIME_STATUS_OK,
        "adversarial candidate-order cleanup failed");
    require(OverworldWildRuntime_Remove(&runtime, 0,
            runtime.slots[0].slotGeneration, &low, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].layerGeneration == 8
            && runtime.slots[0].effectiveGeneration == hiddenEffective,
        "hidden lower removal changed effective output");
    status = OverworldWildRuntime_Replace(&runtime, 0,
        runtime.slots[0].slotGeneration, input, 0x9501, 0,
        DEF_EXACT, &result);
    if (status != OW_WILD_RUNTIME_STATUS_OK
        || runtime.slots[0].effectiveCache.semanticRole != OWBD_ROLE_TIRED)
        fprintf(stderr,
            "visible replace status=%u role=%u effective=%lu before=%lu\n",
            status, runtime.slots[0].effectiveCache.semanticRole,
            (unsigned long)runtime.slots[0].effectiveGeneration,
            (unsigned long)hiddenEffective);
    require(status == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.semanticRole == OWBD_ROLE_TIRED
            && runtime.slots[0].effectiveGeneration
                == OverworldWildRuntime_AdvanceNonzeroGeneration(
                    hiddenEffective),
        "visible state replacement did not publish one effective change");
    hiddenEffective = runtime.slots[0].effectiveGeneration;
    (void)apply_one(&runtime, 0, input, DEF_MULTI_INSTANCE, 0x9504, 1);
    require(runtime.slots[0].provenance.modifierCount == 1
            && !runtime.slots[0].provenance.modifiers[0].applied
            && runtime.slots[0].provenance.modifiers[0].skipReason != 0,
        "inapplicable active modifier lacked a concrete skip diagnostic");

    (void)apply_one(&runtime, 0, input, DEF_SET_SPEED_FOUR, 0x9503, 0);
    visibleEffective = runtime.slots[0].effectiveGeneration;
    require(runtime.slots[0].effectiveCache.stateValues[3] == 4
            && visibleEffective == hiddenEffective + 1,
        "visible modifier did not advance effective generation");
    require(OverworldWildRuntime_Replace(&runtime, 0,
            runtime.slots[0].slotGeneration, input, 0x9503, 0,
            DEF_CLAMP_SPEED_FOUR, &result) == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.stateValues[3] == 4
            && runtime.slots[0].effectiveGeneration == visibleEffective,
        "raw contributor with identical saturated output advanced effective generation");
    require(runtime.slots[0].provenance.contributionCount == 1
            && runtime.slots[0].provenance.contributions[0].definitionId
                == DEF_CLAMP_SPEED_FOUR,
        "no-op-normalized replacement did not refresh provenance");

    prepare_runtime_unprimed(&runtime, 0);
    staticInput.immutableContextMask = 0x12345678u;
    staticContext.groupFlags = 0x12345678u;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, &staticInput)
            == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.stateValues[3] == 2,
        "static modifier was not folded through the common operator pipeline");
    (void)apply_one(&runtime, 0, &staticInput, DEF_RUNTIME_ADD, 0x9510, 0);
    require(runtime.slots[0].effectiveCache.stateValues[3] == 3
            && runtime.slots[0].provenance.modifierCount == 3
            && runtime.slots[0].provenance.modifiers[0].definitionId
                == DEF_STATIC_SET_ORDER
            && runtime.slots[0].provenance.modifiers[0].staticPriority == 1
            && runtime.slots[0].provenance.modifiers[0].ruleStableId == 0x5001
            && runtime.slots[0].provenance.modifiers[0].actionStableId == 0x6001
            && runtime.slots[0].provenance.modifiers[1].definitionId
                == DEF_STATIC_ADD
            && runtime.slots[0].provenance.modifiers[1].actionStableId == 0x6002
            && runtime.slots[0].provenance.modifiers[2].definitionId
                == DEF_RUNTIME_ADD,
        "static action order or static-before-runtime folding changed");

    prepare_runtime_unprimed(&runtime, 0);
    staticContext = fixture_static_context();
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "operator fixture prime failed");
    (void)apply_one(&runtime, 0, input, DEF_ALL_OPERATORS, 0x9520, 0);
    require(runtime.slots[0].effectiveCache.stateValues[3] == 2
            && runtime.slots[0].effectiveCache.stateValues[4] == 5
            && runtime.slots[0].effectiveCache.stateValues[11] == 4
            && runtime.slots[0].effectiveCache.stateValues[13] == 0
            && runtime.slots[0].effectiveCache.stateValues[14] == 2
            && runtime.slots[0].effectiveCache.stateValues[12] == 5
            && runtime.slots[0].effectiveCache.stateValues[10] == 12
            && runtime.slots[0].provenance.contributionCount == 8
            && runtime.slots[0].provenance.normalizationCount == 1
            && runtime.slots[0].provenance.lastWriterDefinitionIds[3]
                == DEF_ALL_OPERATORS,
        "six operator families/normalization/provenance diverged from Task 6");

    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input, DEF_BAD_OVERFLOW,
            0x9521, 0, &result) == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.stateValues[3] == 4,
        "runtime s16 operand 33 was narrowed to the static wire domain");
    wide33 = runtime.slots[0].effectiveCache.stateValues[3];
    (void)apply_one(&runtime, 0, input, DEF_RUNTIME_S16_MIN, 0x9524, 0);
    wideMinimum = runtime.slots[0].effectiveCache.stateValues[4];
    require(runtime.slots[0].effectiveCache.stateValues[4] == 0,
        "runtime s16 operand -32768 did not saturate deterministically");
    require(OverworldWildRuntime_Replace(&runtime, 0,
            runtime.slots[0].slotGeneration, input, 0x9524, 0,
            DEF_RUNTIME_S16_MAX, &result) == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.stateValues[4] == 64,
        "runtime s16 operand 32767 did not saturate deterministically");
    wideMaximum = runtime.slots[0].effectiveCache.stateValues[4];

    before = runtime;
    conflictStatus = (u8)OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_CONFLICTING_BOUNDS, 0x9525, 0, &result);
    require(conflictStatus == OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "same-layer AT_LEAST/AT_MOST conflict changed live bytes");

    prepare_runtime(&runtime, 0);
    before = runtime;
    speedZeroStatus = (u8)OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input, DEF_SPEED_ZERO,
            0x9522, 0, &result);
    require(speedZeroStatus == OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "Task-6 speed SET zero was accepted or changed live bytes");
    (void)apply_one(&runtime, 0, input, DEF_AVOID_SET_ONE, 0x9523, 0);
    require(runtime.slots[0].effectiveCache.stateValues[22] == 1
            && runtime.slots[0].provenance.contributions[
                runtime.slots[0].provenance.contributionCount - 1].fieldId
                == 22,
        "Task-6 avoidPreviousTile SET one was not composed/provenanced");
    require(OverworldWildRuntime_Replace(&runtime, 0,
            runtime.slots[0].slotGeneration, input, 0x9523, 0,
            DEF_AVOID_SET_ZERO, &result) == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.stateValues[22] == 0,
        "Task-6 avoidPreviousTile SET zero was not composed");
    before = runtime;
    avoidSetTwoStatus = (u8)OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input, DEF_AVOID_SET_TWO,
            0x9524, 0, &result);
    require(avoidSetTwoStatus == OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "invalid avoidPreviousTile boolean changed live bytes");
    avoidAddStatus = (u8)OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input, DEF_AVOID_ADD,
            0x9525, 0, &result);
    require(avoidAddStatus == OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "non-SET avoidPreviousTile operator changed live bytes");
    printf("TASK6_DOMAINS speedSet0=%d avoidSet1=%u avoidSet0=%u "
           "avoidSet2=%d avoidAdd=%d\n",
        speedZeroStatus, 1u, 0u, avoidSetTwoStatus, avoidAddStatus);
    printf("TASK6_RUNTIME_S16 add33=%u min=%u max=%u conflict=%u\n",
        wide33, wideMinimum, wideMaximum, conflictStatus);

    prepare_runtime_unprimed(&runtime, 0);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "provenance truncation prime failed");
    for (i = 0; i < 3; i++)
        (void)apply_one(&runtime, 0, input, DEF_ALL_OPERATORS,
            (u16)(0x9530 + i), i);
    require((runtime.slots[0].provenance.flags
                & OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_CONTRIBUTIONS)
            && runtime.slots[0].provenance.contributionCount
                == OW_WILD_RUNTIME_MAX_PROVENANCE_CONTRIBUTIONS,
        "bounded provenance did not report deterministic truncation");

    prepare_runtime_unprimed(&runtime, 0);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK,
        "generation wrap prime failed");
    (void)apply_one(&runtime, 0, input, DEF_HIGH_STATE, 0x953F, 0);
    hiddenEffective = runtime.slots[0].effectiveGeneration;
    firstCacheIdentity = runtime.slots[0].effectiveCache.cacheIdentity;
    firstSlotIncarnation = runtime.slots[0].cacheIncarnation;
    runtime.slots[0].layerGeneration = 0xFFFFFFFFu;
    runtime.slots[0].effectiveCache.layerGeneration = 0xFFFFFFFFu;
    runtime.slots[0].provenance.layerGeneration = 0xFFFFFFFFu;
    runtime.slots[0].effectiveCache.cacheIdentity = CacheIdentity(
        &runtime, &runtime.slots[0], &runtime.slots[0].effectiveCache,
        &runtime.slots[0].provenance,
        sOverworldWildRuntimeLayerService.privateRuntimeIdentity);
    runtime.slots[0].provenance.cacheIdentity =
        runtime.slots[0].effectiveCache.cacheIdentity;
    low = apply_one(&runtime, 0, input, DEF_LOW_STATE, 0x9540, 0);
    require(runtime.slots[0].layerGeneration == 1
            && runtime.slots[0].effectiveGeneration == hiddenEffective
            && runtime.slots[0].cacheIncarnation != firstSlotIncarnation
            && runtime.slots[0].effectiveCache.cacheIdentity != 0
            && runtime.slots[0].effectiveCache.cacheIdentity
                != firstCacheIdentity,
        "layer generation wrap published zero/stale cache identity");
    require(OverworldWildRuntime_Remove(&runtime, 0,
            runtime.slots[0].slotGeneration, &low, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "post-wrap layer handle was not usable");
    runtime.slots[0].effectiveGeneration = 0xFFFFFFFFu;
    runtime.slots[0].effectiveCache.effectiveGeneration = 0xFFFFFFFFu;
    runtime.slots[0].provenance.effectiveGeneration = 0xFFFFFFFFu;
    firstCacheIdentity = runtime.slots[0].effectiveCache.cacheIdentity;
    firstSlotIncarnation = runtime.slots[0].cacheIncarnation;
    runtime.slots[0].effectiveCache.cacheIdentity = CacheIdentity(
        &runtime, &runtime.slots[0], &runtime.slots[0].effectiveCache,
        &runtime.slots[0].provenance,
        sOverworldWildRuntimeLayerService.privateRuntimeIdentity);
    runtime.slots[0].provenance.cacheIdentity =
        runtime.slots[0].effectiveCache.cacheIdentity;
    (void)apply_one(&runtime, 0, input, DEF_SET_SPEED_FOUR, 0x9541, 0);
    require(runtime.slots[0].effectiveGeneration == 1
            && runtime.slots[0].effectiveCache.effectiveGeneration == 1
            && runtime.slots[0].cacheIncarnation != firstSlotIncarnation
            && runtime.slots[0].effectiveCache.cacheIdentity
                != firstCacheIdentity,
        "effective generation wrap did not invalidate/restart at one");

    firstCacheIdentity = runtime.slots[0].effectiveCache.cacheIdentity;
    firstDataIncarnation = runtime.dataIncarnation;
    firstSlotIncarnation = runtime.slots[0].cacheIncarnation;
    OverworldWildRuntime_MarkResidentCold(&runtime);
    require(!runtime.slots[0].staticCache.valid
            && !(runtime.slots[0].effectiveCache.flags
                & OW_WILD_RUNTIME_CACHE_VALID)
            && runtime.slots[0].provenance.flags == 0
            && runtime.dataIncarnation != firstDataIncarnation
            && runtime.slots[0].cacheIncarnation != firstSlotIncarnation,
        "cold restart retained copied catalog/cache/provenance bytes");
    before = runtime;
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "resident-cold prime published or changed runtime/cache bytes");
    require(OverworldWildRuntime_BindPrivateIdentity(&runtime)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
                runtime.slots[0].slotGeneration, &staticContext, input)
                == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].effectiveCache.cacheIdentity
                != firstCacheIdentity,
        "cold reload reused the prior authenticated cache identity");
    before = runtime;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, FALSE);
    require(memcmp(&runtime, &before, sizeof(runtime)) == 0,
        "false destructive wrapper changed runtime bytes");
    priorSlotGeneration = runtime.slots[0].slotGeneration;
    firstSlotIncarnation = runtime.slots[0].cacheIncarnation;
    bystander = runtime.slots[1];
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[0].slotGeneration == priorSlotGeneration + 1
            && runtime.slots[0].cacheIncarnation
                == OverworldWildRuntime_AdvanceNonzeroGeneration(
                    firstSlotIncarnation)
            && !runtime.slots[0].staticCache.valid
            && runtime.slots[0].effectiveCache.cacheIdentity == 0
            && runtime.slots[0].provenance.freshnessGeneration == 0,
        "ordinary live invalidation did not advance identity and clear Task-9 caches");
    require(memcmp(&runtime.slots[1], &bystander, sizeof(bystander)) == 0,
        "ordinary live invalidation changed a bystander slot");
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 0);
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK
            && runtime.slots[0].staticCache.valid
            && runtime.slots[0].effectiveCache.cacheIdentity != 0,
        "repeated live-cycle setup did not repopulate Task-9 caches");
    priorSlotGeneration = runtime.slots[0].slotGeneration;
    firstSlotIncarnation = runtime.slots[0].cacheIncarnation;
    bystander = runtime.slots[1];
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[0].slotGeneration == priorSlotGeneration + 1
            && runtime.slots[0].cacheIncarnation
                == OverworldWildRuntime_AdvanceNonzeroGeneration(
                    firstSlotIncarnation)
            && !runtime.slots[0].staticCache.valid
            && runtime.slots[0].effectiveCache.cacheIdentity == 0
            && runtime.slots[0].provenance.freshnessGeneration == 0,
        "repeated live invalidation retained prior identity or Task-9 caches");
    require(memcmp(&runtime.slots[1], &bystander, sizeof(bystander)) == 0,
        "repeated live invalidation changed a bystander slot");
    (void)high;
}

static OverworldWildRuntimeTimer *timer_for_owner_key(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    u16 ownerId,
    u16 instanceKey)
{
    int index = FindLayer(
        &runtime->slots[slotIndex], ownerId, instanceKey);
    if (index < 0) return NULL;
    if (!(runtime->slots[slotIndex].timerBank.timers[index].flags
            & OW_WILD_RUNTIME_TIMER_VALID)) return NULL;
    return &runtime->slots[slotIndex].timerBank.timers[index];
}

static OverworldWildRuntimeTimer *timer_for_owner(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    u16 ownerId)
{
    return timer_for_owner_key(runtime, slotIndex, ownerId, 0);
}

static OverworldWildRuntimeTimerExpiry expiry_for_owner(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    u16 ownerId)
{
    OverworldWildRuntimeTimerExpiry expiry = {0};
    u8 i;
    memset(&expiry, 0, sizeof(expiry));
    for (i = 0; i < OverworldWildRuntime_GetPendingTimerExpiryCount(
            runtime, (u8)slotIndex,
            runtime->slots[slotIndex].slotGeneration); i++) {
        require(OverworldWildRuntime_GetPendingTimerExpiryByIndex(runtime,
                (u8)slotIndex, runtime->slots[slotIndex].slotGeneration,
                i, &expiry) == OW_WILD_RUNTIME_STATUS_OK,
            "pending expiry enumeration failed");
        if (expiry.ownerId == ownerId) return expiry;
    }
    memset(&expiry, 0, sizeof(expiry));
    return expiry;
}

static void test_task10_timer_engine(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime beforeFailure;
    OverworldWildRuntimeStackDeltaResult delta;
    OverworldWildRuntimeTimerTickResult tick;
    OverworldWildRuntimeLayerHandle low;
    OverworldWildRuntimeLayerHandle tired;
    OverworldWildRuntimeLayerHandle high;
    OverworldWildRuntimeLayerHandle calm;
    OverworldWildRuntimeLayerHandle exact;
    OverworldWildRuntimeTimerExpiry highExpiry;
    OverworldWildRuntimeTimerExpiry lowExpiry;
    OverworldWildRuntimeTimerExpiry staleExpiry;
    OverworldWildRuntimeTimerExpiry malformedExpiry;
    OverworldWildRuntimeTimer timerOut;
    OverworldWildRuntimeTimerTickResult
        frameTicks[OW_WILD_MAX_SPAWNS];
    OverworldWildRuntimeTimer preservedA;
    OverworldWildRuntimeTimer preservedC;
    OverworldWildRuntimeStaticCache cachedStatic;
    OverworldWildRuntimeEffectiveCache cachedEffective;
    OverworldWildRuntimeProvenance cachedProvenance;
    OverworldWildRuntimeStaticContext staticContext = fixture_static_context();
    u32 layerGeneration;
    u32 effectiveGeneration;
    u32 effectiveHash;
    u8 metadataStatus;
    u8 finiteStatus;
    u8 indefiniteStatus;
    u8 rekeyStatus;
    u8 restartStatus;
    u8 malformedStatus;
    u8 frameFailureStatus;
    u8 frameRetryStatus;
    u8 tagReplayStatus;
    u8 indefiniteDriftStatus;

    prepare_runtime(&runtime, 0);
    low = apply_one(&runtime, 0, input, DEF_LOW_STATE, 0x9601, 0);
    require(timer_for_owner(&runtime, 0, 0x9601)->remainingTicks == 3,
        "expire-on-hide timer did not arm");
    tired = apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9602, 0);
    require((timer_for_owner(&runtime, 0, 0x9601)->flags
            & OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
            && timer_for_owner(&runtime, 0, 0x9601)->remainingTicks == 0,
        "recomposition did not publish EXPIRE_ON_HIDE immediately");
    high = apply_one(&runtime, 0, input, DEF_HIGH_STATE, 0x9603, 0);
    calm = apply_one(&runtime, 0, input, DEF_CALM, 0x9604, 0);
    exact = apply_one(&runtime, 0, input, DEF_EXACT, 0x9605, 0);
    require(OverworldWildRuntime_GetTimerCount(&runtime, 0,
            runtime.slots[0].slotGeneration) == 4,
        "simultaneous layer timers were collapsed");
    require(timer_for_owner(&runtime, 0, 0x9602)->remainingTicks == 4
            && timer_for_owner(&runtime, 0, 0x9603)->remainingTicks == 2
            && timer_for_owner(&runtime, 0, 0x9605)->remainingTicks == 5,
        "simultaneous timer arm values differ");

    require(OverworldWildRuntime_SetTimerPresentationGate(&runtime, 0,
            runtime.slots[0].slotGeneration, TRUE)
            == OW_WILD_RUNTIME_STATUS_OK,
        "presentation gate did not activate");
    layerGeneration = runtime.slots[0].layerGeneration;
    effectiveGeneration = runtime.slots[0].effectiveGeneration;
    effectiveHash = runtime.slots[0].effectiveCache.effectiveHash;
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, TRUE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && tick.changedTimerCount == 0,
        "presentation gate advanced gameplay timers");
    require(timer_for_owner(&runtime, 0, 0x9602)->remainingTicks == 4
            && timer_for_owner(&runtime, 0, 0x9603)->remainingTicks == 2,
        "presentation gate changed hidden timers");
    require(OverworldWildRuntime_SetTimerPresentationGate(&runtime, 0,
            runtime.slots[0].slotGeneration, FALSE)
            == OW_WILD_RUNTIME_STATUS_OK,
        "presentation gate did not release");
    cachedStatic = runtime.slots[0].staticCache;
    cachedEffective = runtime.slots[0].effectiveCache;
    cachedProvenance = runtime.slots[0].provenance;
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "first ungated frame tick failed");
    require(timer_for_owner(&runtime, 0, 0x9602)->remainingTicks == 4
            && timer_for_owner(&runtime, 0, 0x9603)->remainingTicks == 1,
        "pause/continue hidden policies were conflated");
    require(runtime.slots[0].layerGeneration == layerGeneration
            && runtime.slots[0].effectiveGeneration == effectiveGeneration
            && runtime.slots[0].effectiveCache.effectiveHash == effectiveHash
            && !memcmp(&runtime.slots[0].staticCache, &cachedStatic,
                sizeof(cachedStatic))
            && !memcmp(&runtime.slots[0].effectiveCache, &cachedEffective,
                sizeof(cachedEffective))
            && !memcmp(&runtime.slots[0].provenance, &cachedProvenance,
                sizeof(cachedProvenance))
            && tick.layerGenerationBefore == tick.layerGenerationAfter
            && tick.effectiveGenerationBefore == tick.effectiveGenerationAfter,
        "ordinary timer decrement changed composition generations/hash");
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 9, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && (timer_for_owner(&runtime, 0, 0x9603)->flags
                & OW_WILD_RUNTIME_TIMER_ZERO_PENDING),
        "continue-hidden timer did not publish zero pending");
    highExpiry = expiry_for_owner(&runtime, 0, 0x9603);
    lowExpiry = expiry_for_owner(&runtime, 0, 0x9601);
    require(highExpiry.validityTag != 0 && lowExpiry.validityTag != 0,
        "exact pending expiry tickets were not published");
    require(OverworldWildRuntime_CommitTimerExpiry(&runtime, &highExpiry,
            &delta) == OW_WILD_RUNTIME_STATUS_OK
            && FindLayer(&runtime.slots[0], 0x9603, 0) < 0
            && FindLayer(&runtime.slots[0], 0x9604, 0) >= 0,
        "hidden middle timer expiry removed the wrong layer");
    require(OverworldWildRuntime_CommitTimerExpiry(&runtime, &highExpiry,
            &delta) == OW_WILD_RUNTIME_STATUS_STALE_NOOP,
        "consumed expiry ticket was not stale-safe");
    require(OverworldWildRuntime_Remove(&runtime, 0,
            runtime.slots[0].slotGeneration, &calm, &delta)
            == OW_WILD_RUNTIME_STATUS_OK,
        "top untimed layer removal failed");
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x9602)->remainingTicks == 3,
        "revealed paused timer did not resume");
    require(OverworldWildRuntime_CommitTimerExpiry(&runtime, &lowExpiry,
            &delta) == OW_WILD_RUNTIME_STATUS_OK
            && FindLayer(&runtime.slots[0], 0x9601, 0) < 0
            && timer_for_owner(&runtime, 0, 0x9602) != NULL
            && timer_for_owner(&runtime, 0, 0x9605) != NULL,
        "exact hidden expiry disturbed unrelated timers");

    prepare_runtime(&runtime, 0);
    exact = apply_one(&runtime, 0, input, DEF_EXACT, 0x9610, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 3, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x9610)->remainingTicks == 5,
        "FRAME tick advanced COMPLETED_MOVEMENT timer");
    require(OverworldWildRuntime_TickCompletedMovementTimers(&runtime, 0,
            runtime.slots[0].slotGeneration, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x9610)->remainingTicks == 4,
        "completed movement did not advance its timer clock");
    require(OverworldWildRuntime_ClearAllForSlot(&runtime, 0,
            runtime.slots[0].slotGeneration, &delta)
            == OW_WILD_RUNTIME_STATUS_OK,
        "movement clock fixture cleanup failed");
    (void)exact;
    (void)apply_one(&runtime, 0, input, DEF_FLED, 0x8107, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 254, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x8107)->remainingTicks == 255
            && !(timer_for_owner(&runtime, 0, 0x8107)->flags
                & OW_WILD_RUNTIME_TIMER_ZERO_PENDING),
        "indefinite 255 timer decremented or expired");

    prepare_runtime(&runtime, 0);
    tired = apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9620, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "replace fixture pre-tick failed");
    preservedA = *timer_for_owner(&runtime, 0, 0x9620);
    beforeFailure = runtime;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_ORDINARY_TIRED, 0x9620, 0, &delta)
            == OW_WILD_RUNTIME_STATUS_IDEMPOTENT
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "idempotent timed Apply refreshed timer state");
    require(OverworldWildRuntime_Replace(&runtime, 0,
            runtime.slots[0].slotGeneration, input, 0x9620, 0,
            DEF_ORDINARY_TIRED, &delta) == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x9620)->remainingTicks == 4
            && timer_for_owner(&runtime, 0, 0x9620)->entryGeneration
                != preservedA.entryGeneration
            && timer_for_owner(&runtime, 0, 0x9620)->timerGeneration
                != preservedA.timerGeneration,
        "same-definition Replace did not mint/restart exact timer");
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "replacement expiry tick failed");
    staleExpiry = expiry_for_owner(&runtime, 0, 0x9620);
    require(staleExpiry.validityTag != 0,
        "replacement did not publish expiry ticket");
    require(OverworldWildRuntime_Replace(&runtime, 0,
            runtime.slots[0].slotGeneration, input, 0x9620, 0,
            DEF_ORDINARY_TIRED, &delta) == OW_WILD_RUNTIME_STATUS_OK,
        "second replacement failed");
    require(OverworldWildRuntime_CommitTimerExpiry(&runtime, &staleExpiry,
            &delta) == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && timer_for_owner(&runtime, 0, 0x9620)->remainingTicks == 4,
        "stale expiry removed/refreshed replacement timer");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9701, 0);
    high = apply_one(&runtime, 0, input, DEF_HIGH_STATE, 0x9702, 0);
    (void)apply_one(&runtime, 0, input, DEF_EXACT, 0x9703, 0);
    preservedA = *timer_for_owner(&runtime, 0, 0x9701);
    preservedC = *timer_for_owner(&runtime, 0, 0x9703);
    require(OverworldWildRuntime_Remove(&runtime, 0,
            runtime.slots[0].slotGeneration, &high, &delta)
            == OW_WILD_RUNTIME_STATUS_OK
            && !memcmp(timer_for_owner(&runtime, 0, 0x9701),
                &preservedA, sizeof(preservedA))
            && !memcmp(timer_for_owner(&runtime, 0, 0x9703),
                &preservedC, sizeof(preservedC)),
        "middle removal changed unrelated aligned timer bytes");
    require(OverworldWildRuntime_RemoveOwner(&runtime, 0,
            runtime.slots[0].slotGeneration, 0x9701, &delta)
            == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x9703) != NULL,
        "bottom removal disturbed top timer");
    require(OverworldWildRuntime_RemoveOwner(&runtime, 0,
            runtime.slots[0].slotGeneration, 0x9703, &delta)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_GetTimerCount(&runtime, 0,
                runtime.slots[0].slotGeneration) == 0,
        "top removal retained timer");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9801, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "rekey fixture pre-tick failed");
    runtime.slots[0].nextEntryGeneration = 0xFFFFFFFFu;
    runtime.slots[0].nextTimerGeneration = 0xFFFFFFFFu;
    layerGeneration = runtime.handleEpoch;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_EXACT, 0x9802, 0, &delta) == OW_WILD_RUNTIME_STATUS_OK
            && runtime.handleEpoch == layerGeneration + 1
            && timer_for_owner(&runtime, 0, 0x9801)->remainingTicks == 3
            && timer_for_owner(&runtime, 0, 0x9801)->entryGeneration == 1
            && timer_for_owner(&runtime, 0, 0x9801)->timerGeneration == 1,
        "entry/timer wrap did not atomically rekey surviving timer");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9811, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "timer-only wrap pre-tick failed");
    require(runtime.slots[0].nextEntryGeneration != 0xFFFFFFFFu,
        "timer-only wrap fixture unexpectedly armed entry wrap");
    runtime.slots[0].nextTimerGeneration = 0xFFFFFFFFu;
    layerGeneration = runtime.handleEpoch;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_EXACT, 0x9812, 0, &delta) == OW_WILD_RUNTIME_STATUS_OK
            && runtime.handleEpoch == layerGeneration + 1
            && timer_for_owner(&runtime, 0, 0x9811)->remainingTicks == 3
            && timer_for_owner(&runtime, 0, 0x9811)->timerGeneration == 1,
        "timer-only carrier wrap did not rekey/preserve survivor");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9821, 0);
    (void)apply_one(&runtime, 1, input, DEF_ORDINARY_TIRED, 0x9822, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_TickCandidateTimers(&runtime, 1,
                runtime.slots[1].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK,
        "cross-slot wrap timer preparation failed");
    staleExpiry = expiry_for_owner(&runtime, 1, 0x9822);
    require(staleExpiry.validityTag != 0,
        "cross-slot rekey fixture did not capture its old expiry ticket");
    runtime.slots[0].nextTimerGeneration = 0xFFFFFFFFu;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_EXACT, 0x9823, 0, &delta) == OW_WILD_RUNTIME_STATUS_OK
            && timer_for_owner(&runtime, 0, 0x9821)->remainingTicks == 3
            && timer_for_owner(&runtime, 1, 0x9822)->remainingTicks == 0
            && (timer_for_owner(&runtime, 1, 0x9822)->flags
                & OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
            && timer_for_owner(&runtime, 1, 0x9822)->timerGeneration == 1,
        "cross-slot rekey changed survivor remaining/zero-pending state");
    beforeFailure = runtime;
    rekeyStatus = OverworldWildRuntime_CommitTimerExpiry(
        &runtime, &staleExpiry, &delta);
    require(rekeyStatus == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "old-identity rekey expiry was not a mutation-free stale no-op");
    malformedExpiry = staleExpiry;
    malformedExpiry.reserved[0] = 1;
    beforeFailure = runtime;
    malformedStatus = OverworldWildRuntime_CommitTimerExpiry(
        &runtime, &malformedExpiry, &delta);
    require(malformedStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "structurally malformed stale expiry was not rejected atomically");
    require(OverworldWildRuntime_PrimeEffectiveCache(&runtime, 1,
            runtime.slots[1].slotGeneration, &staticContext, input)
            == OW_WILD_RUNTIME_STATUS_OK
            && expiry_for_owner(&runtime, 1, 0x9822).validityTag != 0,
        "cross-slot rekey did not republish exact pending ticket");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9831, 0);
    (void)apply_one(&runtime, 1, input, DEF_ORDINARY_TIRED, 0x9832, 0);
    timer_for_owner(&runtime, 1, 0x9832)->ownerId ^= 1;
    runtime.slots[0].nextTimerGeneration = 0xFFFFFFFFu;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_EXACT, 0x9833, 0, &delta)
            == OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED
            && runtime.slots[0].activeLayerCount == 0
            && runtime.slots[1].activeLayerCount == 0
            && OverworldWildRuntime_GetPendingTimerExpiryCount(&runtime, 0,
                runtime.slots[0].slotGeneration) == 0,
        "corrupted bystander was not rejected by atomic wrap recovery");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9841, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "terminal epoch fixture did not publish expiry");
    staleExpiry = expiry_for_owner(&runtime, 0, 0x9841);
    runtime.handleEpoch = 0xFFFFFFFFu;
    runtime.slots[0].nextTimerGeneration = 0xFFFFFFFFu;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_EXACT, 0x9842, 0, &delta)
            == OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED
            && runtime.handleEpoch == 1
            && runtime.slots[0].activeLayerCount == 0
            && !memcmp(&runtime.slots[0].timerBank,
                &(OverworldWildRuntimeTimerBank){{{0}}},
                sizeof(runtime.slots[0].timerBank)),
        "terminal epoch restart retained timer state");
    beforeFailure = runtime;
    restartStatus = OverworldWildRuntime_CommitTimerExpiry(
        &runtime, &staleExpiry, &delta);
    require(restartStatus == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "old-identity restart expiry was not a mutation-free stale no-op");

    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[0].activeLayerCount == 0
            && runtime.slots[0].nextTimerGeneration == 1
            && !memcmp(&runtime.slots[0].timerBank,
                &(OverworldWildRuntimeTimerBank){{{0}}},
                sizeof(runtime.slots[0].timerBank)),
        "destructive reuse retained timer storage");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9901, 0);
    beforeFailure = runtime;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_EXCLUSIVE, 0x9901, 0, &delta)
            == OW_WILD_RUNTIME_STATUS_OWNER_KEY_OCCUPIED
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "failed atomic delta partially changed timer/layer state");
    timer_for_owner(&runtime, 0, 0x9901)->hiddenPolicy =
        OW_WILD_RUNTIME_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN;
    beforeFailure = runtime;
    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, input,
            DEF_ORDINARY_TIRED, 0x9901, 0, &delta)
            == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "idempotent Apply accepted unauthenticated timer metadata");
    metadataStatus = OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
        runtime.slots[0].slotGeneration,
        OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick);
    require(metadataStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "timer tick accepted valid-enum metadata drift or changed runtime");
    memset(&timerOut, 0xA5, sizeof(timerOut));
    require(OverworldWildRuntime_GetTimerCount(&runtime, 0,
                runtime.slots[0].slotGeneration) == 0
            && OverworldWildRuntime_GetTimerByIndex(&runtime, 0,
                runtime.slots[0].slotGeneration, 0, &timerOut)
                == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&timerOut, &(OverworldWildRuntimeTimer){0},
                sizeof(timerOut))
            && OverworldWildRuntime_GetPendingTimerExpiryCount(&runtime, 0,
                runtime.slots[0].slotGeneration) == 0
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "timer queries exposed valid-enum metadata drift");
    memset(&malformedExpiry, 0xA5, sizeof(malformedExpiry));
    require(OverworldWildRuntime_GetPendingTimerExpiryByIndex(&runtime, 0,
                runtime.slots[0].slotGeneration, 0, &malformedExpiry)
                == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&malformedExpiry,
                &(OverworldWildRuntimeTimerExpiry){0},
                sizeof(malformedExpiry))
            && OverworldWildRuntime_SetTimerPresentationGate(&runtime, 0,
                runtime.slots[0].slotGeneration, TRUE)
                == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "pending query/gate accepted valid-enum metadata drift");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9911, 0);
    timer_for_owner(&runtime, 0, 0x9911)->remainingTicks =
        timer_for_owner(&runtime, 0, 0x9911)->armedDuration + 1;
    beforeFailure = runtime;
    finiteStatus = OverworldWildRuntime_GetTimerByIndex(&runtime, 0,
        runtime.slots[0].slotGeneration, 0, &timerOut);
    require(finiteStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "finite timer extension was accepted or changed runtime");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9921, 0);
    timer_for_owner(&runtime, 0, 0x9921)->remainingTicks = 255;
    beforeFailure = runtime;
    indefiniteStatus = OverworldWildRuntime_SetTimerPresentationGate(
        &runtime, 0, runtime.slots[0].slotGeneration, TRUE);
    require(indefiniteStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "finite-to-indefinite timer edit was accepted or changed runtime");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_FLED, 0x8107, 0);
    require(timer_for_owner(&runtime, 0, 0x8107)->armedDuration == 255
            && timer_for_owner(&runtime, 0, 0x8107)->remainingTicks == 255,
        "indefinite drift fixture did not arm a genuine indefinite timer");
    timer_for_owner(&runtime, 0, 0x8107)->remainingTicks = 254;
    beforeFailure = runtime;
    indefiniteDriftStatus = OverworldWildRuntime_TickCandidateTimers(
        &runtime, 0, runtime.slots[0].slotGeneration,
        OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1, FALSE, &tick);
    require(indefiniteDriftStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "indefinite timer below 255 was accepted or changed runtime");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9931, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "commit semantic-preflight fixture did not expire");
    staleExpiry = expiry_for_owner(&runtime, 0, 0x9931);
    timer_for_owner(&runtime, 0, 0x9931)->clock =
        OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT;
    beforeFailure = runtime;
    require(OverworldWildRuntime_CommitTimerExpiry(&runtime, &staleExpiry,
                &delta) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime)),
        "expiry commit accepted valid-enum timer metadata drift");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9932, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "altered-tag fixture did not publish a pending expiry");
    staleExpiry = expiry_for_owner(&runtime, 0, 0x9932);
    require(staleExpiry.validityTag != 0,
        "altered-tag fixture captured a zero validity tag");
    malformedExpiry = staleExpiry;
    malformedExpiry.validityTag = staleExpiry.validityTag == 1 ? 2 : 1;
    beforeFailure = runtime;
    tagReplayStatus = OverworldWildRuntime_CommitTimerExpiry(
        &runtime, &malformedExpiry, &delta);
    highExpiry = expiry_for_owner(&runtime, 0, 0x9932);
    require(tagReplayStatus == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && delta.status == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && delta.ok && !delta.mutated
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime))
            && OverworldWildRuntime_GetPendingTimerExpiryCount(&runtime, 0,
                runtime.slots[0].slotGeneration) == 1
            && timer_for_owner(&runtime, 0, 0x9932) != NULL
            && (timer_for_owner(&runtime, 0, 0x9932)->flags
                & OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
            && !memcmp(&highExpiry, &staleExpiry, sizeof(highExpiry)),
        "altered nonzero current validity tag was not stale-safe");

    prepare_runtime(&runtime, 0);
    assign_and_prime(&runtime, 1);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9941, 0);
    (void)apply_one(&runtime, 1, input, DEF_ORDINARY_TIRED, 0x9942, 0);
    require(OverworldWildRuntime_SetTimerPresentationGate(&runtime, 0,
                runtime.slots[0].slotGeneration, TRUE)
                == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_SetTimerPresentationGate(&runtime, 1,
                runtime.slots[1].slotGeneration, TRUE)
                == OW_WILD_RUNTIME_STATUS_OK,
        "multi-slot frame fixture could not arm presentation gates");
    timer_for_owner(&runtime, 1, 0x9942)->remainingTicks =
        timer_for_owner(&runtime, 1, 0x9942)->armedDuration + 1;
    beforeFailure = runtime;
    frameFailureStatus = OverworldWildRuntime_TickFrameTimers(
        &runtime, 0, frameTicks);
    require(frameFailureStatus == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
            && !memcmp(&runtime, &beforeFailure, sizeof(runtime))
            && runtime.slots[0].presentationGate
            && timer_for_owner(&runtime, 0, 0x9941)->remainingTicks == 4,
        "later invalid frame slot partially changed an earlier slot");
    timer_for_owner(&runtime, 1, 0x9942)->remainingTicks =
        timer_for_owner(&runtime, 1, 0x9942)->armedDuration;
    frameRetryStatus = OverworldWildRuntime_TickFrameTimers(
        &runtime, 0, frameTicks);
    require(frameRetryStatus == OW_WILD_RUNTIME_STATUS_OK
            && !runtime.slots[0].presentationGate
            && !runtime.slots[1].presentationGate
            && timer_for_owner(&runtime, 0, 0x9941)->remainingTicks == 3
            && timer_for_owner(&runtime, 1, 0x9942)->remainingTicks == 3
            && frameTicks[0].changedTimerCount == 1
            && frameTicks[1].changedTimerCount == 1,
        "corrected frame retry did not decrement each slot exactly once");

    prepare_runtime(&runtime, 0);
    (void)apply_one(&runtime, 0, input, DEF_ORDINARY_TIRED, 0x9D01, 0);
    (void)apply_one(&runtime, 0, input, DEF_HIGH_STATE, 0x9D02, 0);
    (void)apply_one(&runtime, 0, input, DEF_CALM, 0x9D03, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 2, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "timer oracle trace tick failed");
    highExpiry = expiry_for_owner(&runtime, 0, 0x9D02);
    require(OverworldWildRuntime_CommitTimerExpiry(&runtime, &highExpiry,
            &delta) == OW_WILD_RUNTIME_STATUS_OK,
        "timer oracle trace commit failed");
    printf("TASK10_TIMER_TRACE paused=%u continued=0 pending=1 layers=%u timers=%u\n",
        timer_for_owner(&runtime, 0, 0x9D01)->remainingTicks,
        runtime.slots[0].activeLayerCount,
        OverworldWildRuntime_GetTimerCount(&runtime, 0,
            runtime.slots[0].slotGeneration));
    printf("TASK10_TIMER_CORRECTION_TRACE metadata=%u finite=%u indefinite=%u "
        "rekey=%u restart=%u malformed=%u frameFailure=%u frameRetry=%u "
        "tagReplay=%u indefiniteDrift=%u slot0=3 slot1=3\n",
        metadataStatus, finiteStatus, indefiniteStatus, rekeyStatus,
        restartStatus, malformedStatus, frameFailureStatus,
        frameRetryStatus, tagReplayStatus, indefiniteDriftStatus);
    (void)low;
    (void)tired;
}

#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static void prepare_task11_runtime(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    const OverworldWildRuntimeStaticContext *context,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut)
{
    prepare_runtime_unprimed(runtime, slotIndex);
    require(OverworldWildRuntime_ResolveCanonicalStaticContext(
            context, resolvedOut) == OW_WILD_RUNTIME_STATUS_OK
        && OverworldWildRuntime_PrimeEffectiveCache(runtime,
            slotIndex, runtime->slots[slotIndex].slotGeneration,
            context, NULL) == OW_WILD_RUNTIME_STATUS_OK,
        "Task11 runtime catalog-owned prime failed");
}

static void assign_task11_slot(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    const OverworldWildRuntimeStaticContext *context,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut)
{
    OverworldWildRuntime_MarkSlotAssigned(runtime, slotIndex);
    require(OverworldWildRuntime_ResolveCanonicalStaticContext(
            context, resolvedOut) == OW_WILD_RUNTIME_STATUS_OK
        && OverworldWildRuntime_PrimeEffectiveCache(runtime,
            slotIndex, runtime->slots[slotIndex].slotGeneration,
            context, NULL) == OW_WILD_RUNTIME_STATUS_OK,
        "Task11 secondary slot catalog-owned prime failed");
}

static void require_task11_invalid_recovery(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    const char *category,
    u8 malformedCase)
{
    OverworldWildBehaviorStackRuntime runtimeBefore = *runtime;
    OverworldWildRuntimeRecoveryPlan plan;
    BOOL accepted = ValidateRecoveryCatalogClosure(expiry, &plan);

    if (accepted || memcmp(runtime, &runtimeBefore, sizeof(*runtime)))
        fprintf(stderr,
            "%s invalid catalog case=%u accepted=%u\n",
            category, malformedCase, accepted);
    require(!accepted && !memcmp(runtime, &runtimeBefore, sizeof(*runtime)),
        "invalid catalog closure changed runtime or was accepted");
}

static void test_task11_substrate(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    static const u16 identityMutationOffsets[] = {
        offsetof(OverworldWildRuntimeCommandIdentity, commandGeneration),
        offsetof(OverworldWildRuntimeCommandIdentity, commandSerial),
        offsetof(OverworldWildRuntimeCommandIdentity, objectGeneration),
        offsetof(OverworldWildRuntimeCommandIdentity,
            staminaPolicyGeneration),
        offsetof(OverworldWildRuntimeCommandIdentity, staminaPolicyId),
        offsetof(OverworldWildRuntimeCommandIdentity, reserved[0]),
        offsetof(OverworldWildRuntimeCommandIdentity, reserved[1]),
    };
    static const u16 originMutationOffsets[] = {
        offsetof(OverworldWildRuntimeCommandOrigin, runtimeEpoch),
        offsetof(OverworldWildRuntimeCommandOrigin, slotGeneration),
        offsetof(OverworldWildRuntimeCommandOrigin, commandGeneration),
        offsetof(OverworldWildRuntimeCommandOrigin, commandSerial),
        offsetof(OverworldWildRuntimeCommandOrigin, winningEntryGeneration),
        offsetof(OverworldWildRuntimeCommandOrigin, effectiveGeneration),
        offsetof(OverworldWildRuntimeCommandOrigin, objectGeneration),
        offsetof(OverworldWildRuntimeCommandOrigin,
            staminaPolicyGeneration),
        offsetof(OverworldWildRuntimeCommandOrigin, controllerId),
        offsetof(OverworldWildRuntimeCommandOrigin, nodeId),
        offsetof(OverworldWildRuntimeCommandOrigin, stateProfileId),
        offsetof(OverworldWildRuntimeCommandOrigin, winningDefinitionId),
        offsetof(OverworldWildRuntimeCommandOrigin, winningOwnerId),
        offsetof(OverworldWildRuntimeCommandOrigin, winningInstanceKey),
        offsetof(OverworldWildRuntimeCommandOrigin, staminaPolicyId),
        offsetof(OverworldWildRuntimeCommandOrigin, slotIndex),
        offsetof(OverworldWildRuntimeCommandOrigin, winnerKind),
        offsetof(OverworldWildRuntimeCommandOrigin, flags),
        offsetof(OverworldWildRuntimeCommandOrigin, reserved[0]),
        offsetof(OverworldWildRuntimeCommandOrigin, reserved[1]),
        offsetof(OverworldWildRuntimeCommandOrigin, reserved[2]),
    };
    static const u8 imperativeOrigins[3] = {
        OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED,
        OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH,
        OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY,
    };
    static const u16 authoredDefinitions[3] = {
        TASK11_DEF_FLED_SEMANTIC,
        TASK11_DEF_RAM_SEMANTIC,
        TASK11_DEF_THROW_SEMANTIC,
    };
    static const u16 exactDefinitions[3] = {
        TASK11_DEF_FLED_EXACT,
        TASK11_DEF_RAM_EXACT,
        TASK11_DEF_THROW_EXACT,
    };
    static const u16 authoredTransitions[3] = {
        TASK11_TRANSITION_FLED_SEMANTIC,
        TASK11_TRANSITION_RAM_SEMANTIC,
        TASK11_TRANSITION_THROW_SEMANTIC,
    };
    static const u16 exactTransitions[3] = {
        TASK11_TRANSITION_FLED_EXACT,
        TASK11_TRANSITION_RAM_EXACT,
        TASK11_TRANSITION_THROW_EXACT,
    };
    static const u16 originOwners[3] = {0x8107, 0x8106, 0x8108};
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime runtimeBefore;
    OverworldWildBehaviorStackRuntime expiredRuntime;
    OverworldWildRuntimeResolvedStaticContext authored;
    OverworldWildRuntimeResolvedStaticContext fallback;
    OverworldWildRuntimeResolvedStaticContext resolved;
    OverworldWildRuntimeResolvedStaticContext resolvedBefore;
    OverworldWildRuntimeRecoveryCandidate candidate;
    OverworldWildRuntimeRecoveryCandidate zeroCandidate;
    OverworldWildRuntimeStaticContext context = fixture_static_context();
    OverworldWildRuntimeStaticContext fallbackContext = fixture_static_context();
    OverworldWildRuntimeStaticContext sleepContext = fixture_static_context();
    OverworldWildRuntimeStaticContext invalidContext = fixture_static_context();
    OverworldWildRuntimeStaticContext authoredRebindContext =
        fixture_static_context();
    OverworldWildRuntimeStaticContext fallbackRebindContext =
        fixture_static_context();
    OverworldWildRuntimeStaticContext mutationContexts[4];
    OverworldWildRuntimeCommandOriginBank commandBank;
    OverworldWildRuntimeCommandOriginBank commandBankBefore;
    OverworldWildRuntimeCommandOriginBank capturedCommandBank;
    OverworldWildRuntimeCommandOrigin consumed;
    OverworldWildRuntimeCommandIdentity mutatedCommand;
    OverworldWildRuntimeCommandIdentity commandA = {
        .commandGeneration = 1,
        .commandSerial = 101,
        .objectGeneration = 201,
        .staminaPolicyGeneration = 301,
        .staminaPolicyId = 401,
    };
    OverworldWildRuntimeCommandIdentity commandB = {
        .commandGeneration = 2,
        .commandSerial = 102,
        .objectGeneration = 202,
        .staminaPolicyGeneration = 302,
        .staminaPolicyId = 402,
    };
    OverworldWildRuntimeCommandIdentity wrongCommand = {
        .commandGeneration = 9,
        .commandSerial = 101,
        .objectGeneration = 201,
        .staminaPolicyGeneration = 301,
        .staminaPolicyId = 401,
    };
    OverworldWildRuntimeTimerTickResult tick;
    OverworldWildRuntimeTimerRecoveryResult recovery;
    OverworldWildRuntimeTimerExpiry expiry;
    union FixtureInstalledCatalogStorage catalogBefore;
    u32 oldSlotGeneration;
    u8 index;
    u8 mutationIndex;
    u8 malformedCase;
    u8 malformedRecoveryCount = 0;
    u8 closedFamilyMutationCount = 0;
    u8 semanticBacklinkMutationCount = 0;
    u8 exactBacklinkMutationCount = 0;
    u8 staminaBacklinkMutationCount = 0;
    u8 sleepBacklinkMutationCount = 0;
    u8 endToEndStatus;
    u8 invalidSelectionStatus;
    u8 staleCommandStatus;
    u8 calmRecoveryStatus;
    u8 removeSelfStatus;

    (void)input;
    sUseTask11ProductionCatalog = TRUE;
    memset(&zeroCandidate, 0, sizeof(zeroCandidate));
    fallbackContext.behaviorClass = 1;
    sleepContext.behaviorClass = 2;
    invalidContext.behaviorClass = 4;
    authoredRebindContext.behaviorClass = 8;
    fallbackRebindContext.behaviorClass = 9;
    for (index = 0; index < 4; index++) {
        mutationContexts[index] = fixture_static_context();
        mutationContexts[index].behaviorClass = (u8)(3 + index);
    }
    require(!memcmp(sFixtureInstalledStorage.bytes, sGeneratedV40Catalog,
            sizeof(sGeneratedV40Catalog))
            && fixture_installed_header()->schemaFingerprint != 0,
        "Task11 fixture bytes differ from the generated v40 catalog");
    catalogBefore = sFixtureInstalledStorage;
    fixture_reseal_installed_catalog();
    require(fixture_installed_header()->checksum
            == catalogBefore.alignment.checksum,
        "fixture catalog CRC reseal diverged from generated bytes");
    sFixtureInstalledStorage = catalogBefore;
    for (mutationIndex = 0; mutationIndex < 2; mutationIndex++) {
        const u16 *definitionIds = mutationIndex == 0
            ? authoredDefinitions : exactDefinitions;
        const u16 *transitionIds = mutationIndex == 0
            ? authoredTransitions : exactTransitions;
        for (index = 0; index < 3; index++) {
            OverworldWildOverrideDefinitionRecord *definition =
                fixture_override_definition(definitionIds[index]);
            OverworldWildTransitionRecord *transition =
                fixture_transition(transitionIds[index]);
            OverworldWildTransitionGuardRecord *guard =
                fixture_transition_guard(transitionIds[index]);
            OverworldWildRecoveryActionRecord *recoveryAction =
                fixture_recovery_action(transitionIds[index]);
            OverworldWildTiredTranslationRecord *translation =
                fixture_tired_translation((u8)(index + 1),
                    mutationIndex == 0);
            require(definition->stableId == definitionIds[index]
                    && definition->recoveryTransitionId
                        == transitionIds[index]
                    && definition->requiredOwnerId == originOwners[index]
                    && definition->selectorKind
                        == (mutationIndex == 0
                            ? OWBD_SELECTOR_SEMANTIC_ROLE
                            : OWBD_SELECTOR_EXACT)
                    && definition->semanticRole
                        == (mutationIndex == 0 ? OWBD_ROLE_TIRED : 0)
                    && definition->controllerId
                        == (mutationIndex == 0 ? 0 : 0x3001)
                    && definition->nodeId
                        == (mutationIndex == 0 ? 0 : 0x3107)
                    && definition->hasTiredOriginKind
                    && definition->tiredOriginKind == index + 1
                    && definition->hasRequiredOwnerId
                    && !definition->allowMultipleOwners
                    && !definition->allowMultipleInstancesPerOwner
                    && !definition->authoredTiredBound
                    && definition->flags == (u8)(mutationIndex != 0)
                    && definition->mapLifetime == 2
                    && definition->battleLifetime == 1
                    && definition->timerClock == OWBD_TIMER_CLOCK_FRAME
                    && definition->timerSource == 1
                    && definition->hiddenTimerPolicy
                        == OWBD_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN
                    && definition->recoveryPolicy
                        == OWBD_RECOVERY_ROUTE_TRANSITION
                    && definition->timerValue == 4
                    && !definition->reserved0 && !definition->reserved1,
                "generated v40 wrapper definition bytes drifted");
            require(transition->candidateDefinitionId
                        == definitionIds[index]
                    && transition->ownerId == originOwners[index]
                    && transition->guardCount == 1
                    && transition->operationCount
                        == (u16)(index == 0 ? 1 : 4)
                    && transition->actionCount == 2
                    && transition->trigger == OWBD_TRIGGER_TIRED_EXPIRED
                    && transition->fromRoleMask
                        == (mutationIndex == 0
                            ? 0x7F : OWBD_ROLE_MASK(OWBD_ROLE_CUSTOM))
                    && transition->recoveryCount == 1
                    && transition->dispatchPriority != 0
                    && guard->stableId != 0
                    && guard->transitionId == transitionIds[index]
                    && guard->kind == OWBD_GUARD_CANDIDATE_TIMER_EXPIRED
                    && !guard->negate
                    && guard->payload == OWBD_TRIGGER_TIRED_EXPIRED
                    && !guard->reserved0 && !guard->referenceId
                    && !guard->reserved,
                "generated v40 recovery topology bytes drifted");
            for (malformedCase = 0;
                    malformedCase < transition->operationCount;
                    malformedCase++) {
                OverworldWildTransitionOperationRecord *operation =
                    fixture_transition_operation(
                        transitionIds[index], malformedCase);
                require(operation->stableId != 0
                        && operation->transitionId == transitionIds[index]
                        && operation->busyPolicy == OWBD_BUSY_REJECT
                        && !operation->reserved
                        && (malformedCase == 0
                            ? (operation->kind
                                    == OWBD_TRANSITION_REMOVE_REQUIRED
                                && operation->required
                                && operation->definitionId
                                    == definitionIds[index]
                                && operation->ownerId == originOwners[index]
                                && !operation->replacementDefinitionId
                                && !operation->policyId
                                && !operation->instanceKey)
                            : (operation->kind
                                    == OWBD_TRANSITION_REMOVE_OWNER_IF_PRESENT
                                && !operation->required
                                && !operation->definitionId
                                && operation->ownerId
                                    == (u16)(0x8101 + malformedCase)
                                && !operation->replacementDefinitionId
                                && !operation->policyId
                                && !operation->instanceKey)),
                    "generated v40 recovery operation payload drifted");
            }
            require(fixture_transition_action(
                        transitionIds[index], 0)->kind
                        == OWBD_ACTION_RESET_TIRED_COUNTER
                    && fixture_transition_action(
                        transitionIds[index], 1)->kind
                        == OWBD_ACTION_START_POST_TIRED_COOLDOWN
                    && recoveryAction->stableId != 0
                    && recoveryAction->transitionId == transitionIds[index]
                    && recoveryAction->ownerId == originOwners[index]
                    && recoveryAction->required
                    && recoveryAction->kind
                        == (index == 0
                            ? OWBD_RECOVERY_ACTION_REMOVE_SELF
                            : OWBD_RECOVERY_ACTION_REMOVE_OWNER_IF_PRESENT)
                    && translation->candidateDefinitionId
                        == definitionIds[index]
                    && translation->recoveryTransitionId
                        == transitionIds[index]
                    && translation->authoredProfileId
                        == (mutationIndex == 0 ? 0x2203 : 0x2210)
                    && translation->exactFallbackControllerId
                        == (mutationIndex == 0 ? 0 : 0x3001)
                    && translation->exactFallbackNodeId
                        == (mutationIndex == 0 ? 0 : 0x3107)
                    && translation->timerOperator == 1
                    && translation->timerSource == 1
                    && translation->mapLifetime == 2
                    && translation->battleLifetime == 1
                    && !translation->flags && !translation->reserved,
                "generated v40 recovery action/translation bytes drifted");
        }
    }
    require(OverworldWildRuntime_ResolveCanonicalStaticContext(
            &context, &authored) == OW_WILD_RUNTIME_STATUS_OK
            && authored.controllerId == 0x3001
            && authored.baseNodeId == 0x3102
            && authored.baseProfileId == 0x2202
            && authored.authoredTiredBound
            && authored.tiredNodeId == 0x3103
            && authored.tiredProfileId == 0x2203
            && authored.stamina == 20 && authored.restTime == 10,
        "canonical context did not publish the exact installed binding");
    require(OverworldWildRuntime_ResolveCanonicalStaticContext(
            &fallbackContext, &fallback) == OW_WILD_RUNTIME_STATUS_OK
            && !fallback.authoredTiredBound
            && fallback.tiredNodeId == 0 && fallback.tiredProfileId == 0
            && fallback.applicability.boundNodeCount == 3
            && !(fallback.applicability.semanticRoleMask
                & OWBD_ROLE_MASK(OWBD_ROLE_TIRED)),
        "canonical context fabricated an authored tired binding");
    memset(&resolved, 0xA5, sizeof(resolved));
    require(OverworldWildRuntime_ResolveCanonicalStaticContext(
            &invalidContext, &resolved)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && !memcmp(&resolved,
                &(OverworldWildRuntimeResolvedStaticContext){0},
                sizeof(resolved)),
        "invalid canonical context retained partial output bytes");
    prepare_runtime_unprimed(&runtime, 0);
    require(OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &context, &resolved)
            == OW_WILD_RUNTIME_STATUS_OK
            && !memcmp(&resolved, &authored, sizeof(resolved))
            && runtime.slots[0].staticCache.catalogIdentity
                == authored.catalogIdentity
            && runtime.slots[0].staticCache.staticContextIdentity
                == authored.staticContextIdentity
            && runtime.slots[0].staticCache.staticSetHash
                == authored.staticSetHash,
        "canonical prime did not publish the resolved static cache");
    runtimeBefore = runtime;
    memset(&resolved, 0xA5, sizeof(resolved));
    require(OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &invalidContext, &resolved)
            == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime))
            && !memcmp(&resolved,
                &(OverworldWildRuntimeResolvedStaticContext){0},
                sizeof(resolved)),
        "invalid canonical prime changed runtime or output bytes");

    for (index = 0; index < 4; index++) {
        runtimeBefore = runtime;
        memset(&candidate, 0xA5, sizeof(candidate));
        require(OverworldWildRuntime_ResolveRecoveryCandidate(
                &mutationContexts[index],
                OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA
                && !memcmp(&candidate, &zeroCandidate, sizeof(candidate))
                && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
            "malformed canonical applicability changed output or runtime");
    }

    require(OverworldWildRuntime_ResolveRecoveryCandidate(&context,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &candidate)
            == OW_WILD_RUNTIME_STATUS_OK
            && candidate.definitionId == TASK11_DEF_STAMINA
            && candidate.ownerId == 0x8105
            && candidate.recoveryTransitionId
                == TASK11_TRANSITION_STAMINA_RECOVER
            && candidate.nodeId == authored.tiredNodeId
            && candidate.profileId == authored.tiredProfileId
            && candidate.selection
                == OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC,
        "stamina did not select the authored tired candidate");
    memset(&candidate, 0xA5, sizeof(candidate));
    require(OverworldWildRuntime_ResolveRecoveryCandidate(&fallbackContext,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &candidate)
            == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
            && !memcmp(&candidate, &zeroCandidate, sizeof(candidate)),
        "stamina recovery was enabled without an authored tired binding");
    for (index = 0; index < 3; index++) {
        require(OverworldWildRuntime_ResolveRecoveryCandidate(&context,
                imperativeOrigins[index], &candidate)
                == OW_WILD_RUNTIME_STATUS_OK
                && candidate.definitionId == authoredDefinitions[index]
                && candidate.nodeId == authored.tiredNodeId
                && candidate.profileId == authored.tiredProfileId
                && candidate.selection
                    == OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC
                && candidate.selectorKind
                    == OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE,
            "imperative recovery did not select the authored semantic wrapper");
        require(OverworldWildRuntime_ResolveRecoveryCandidate(
                &fallbackContext,
                imperativeOrigins[index], &candidate)
                == OW_WILD_RUNTIME_STATUS_OK
                && candidate.definitionId == exactDefinitions[index]
                && candidate.nodeId == 0x3107
                && candidate.profileId == 0x2210
                && candidate.selection
                    == OW_WILD_RUNTIME_RECOVERY_SELECTION_GENERATED_EXACT
                && candidate.selectorKind == OW_WILD_RUNTIME_SELECTOR_EXACT,
            "imperative recovery did not select the generated exact fallback");
    }
    require(OverworldWildRuntime_ResolveRecoveryCandidate(
            &authoredRebindContext,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_OK
            && candidate.nodeId == 0x3103
            && candidate.profileId == 0x2206,
        "semantic recovery ignored the freshly rebound tired profile");
    require(OverworldWildRuntime_ResolveRecoveryCandidate(
            &fallbackRebindContext,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_OK
            && candidate.nodeId == 0x3107
            && candidate.profileId == 0x2211
            && candidate.semanticRole == 0,
        "exact recovery ignored the freshly rebound custom profile");
    catalogBefore = sFixtureInstalledStorage;
    ((OverworldWildTiredTranslationRecord *)fixture_section_record(
        &fixture_installed_header()->tiredTranslations, 3,
        sizeof(OverworldWildTiredTranslationRecord)))
            ->destinationControllerId = 0x3001;
    resolvedBefore = authored;
    runtimeBefore = runtime;
    memset(&candidate, 0xA5, sizeof(candidate));
    require(OverworldWildRuntime_ResolveRecoveryCandidate(&context,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR
            && !memcmp(&candidate, &zeroCandidate, sizeof(candidate))
            && !memcmp(&authored, &resolvedBefore, sizeof(authored))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "invalid recovery selection changed caller or runtime bytes");
    sFixtureInstalledStorage = catalogBefore;
    fixture_installed_header()->tiredTranslations.count = 0;
    memset(&candidate, 0xA5, sizeof(candidate));
    require(OverworldWildRuntime_ResolveRecoveryCandidate(&context,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH, &candidate)
            == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
            && !memcmp(&candidate, &zeroCandidate, sizeof(candidate))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "missing recovery selection changed output or runtime bytes");
    sFixtureInstalledStorage = catalogBefore;
    fixture_override_definition(TASK11_DEF_FLED_SEMANTIC)->selectorKind =
        OW_WILD_RUNTIME_SELECTOR_EXACT;
    memset(&candidate, 0xA5, sizeof(candidate));
    invalidSelectionStatus = ResolveRecoveryCandidateCatalogOracle(
        &context, OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate);
    require(invalidSelectionStatus == OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION
            && !memcmp(&candidate, &zeroCandidate, sizeof(candidate))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "invalid recovery definition changed output or runtime bytes");
    sFixtureInstalledStorage = catalogBefore;
    fixture_tired_translation(OWBD_TIRED_ORIGIN_FLED, TRUE)
        ->authoredProfileId = 0x2202;
    memset(&candidate, 0xA5, sizeof(candidate));
    require(ResolveRecoveryCandidateCatalogOracle(&context,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION
            && !memcmp(&candidate, &zeroCandidate, sizeof(candidate))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "semantic translation profile mismatch changed output or runtime");
    sFixtureInstalledStorage = catalogBefore;
    fixture_tired_translation(OWBD_TIRED_ORIGIN_FLED, FALSE)
        ->authoredProfileId = 0x2203;
    memset(&candidate, 0xA5, sizeof(candidate));
    require(ResolveRecoveryCandidateCatalogOracle(&fallbackContext,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION
            && !memcmp(&candidate, &zeroCandidate, sizeof(candidate))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "exact translation profile mismatch changed output or runtime");
    sFixtureInstalledStorage = catalogBefore;

    prepare_task11_runtime(&runtime, 0, &context, &resolved);
    assign_task11_slot(&runtime, 1, &context, &resolved);
    memset(&commandBank, 0, sizeof(commandBank));
    runtimeBefore = runtime;
    require(OverworldWildRuntime_CaptureCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandA)
            == OW_WILD_RUNTIME_STATUS_OK
            && commandBank.records[0].winnerKind
                == OW_WILD_RUNTIME_COMMAND_WINNER_BASE
            && commandBank.records[0].winningDefinitionId == 0
            && commandBank.records[0].winningOwnerId == 0
            && commandBank.records[0].winningInstanceKey == 0
            && commandBank.records[0].winningEntryGeneration == 0
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "base command origin fabricated layer winner fields");
    require(OverworldWildRuntime_ConsumeCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandA, &consumed)
            == OW_WILD_RUNTIME_STATUS_OK
            && consumed.winnerKind == OW_WILD_RUNTIME_COMMAND_WINNER_BASE
            && !memcmp(&commandBank,
                &(OverworldWildRuntimeCommandOriginBank){0},
                sizeof(commandBank)),
        "base command origin was not consumable exactly once");
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_FLED_SEMANTIC, 0x8107, 0);
    (void)apply_one(&runtime, 1, &authored.applicability,
        TASK11_DEF_FLED_SEMANTIC, 0x8107, 0);
    runtimeBefore = runtime;
    require(OverworldWildRuntime_CaptureCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandA)
            == OW_WILD_RUNTIME_STATUS_OK
            && (commandBank.records[0].flags
                & OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID)
            && commandBank.records[0].commandGeneration == 1
            && commandBank.records[0].commandSerial == 101
            && commandBank.records[0].objectGeneration == 201
            && commandBank.records[0].staminaPolicyId == 401
            && commandBank.records[0].staminaPolicyGeneration == 301
            && commandBank.records[0].winnerKind
                == OW_WILD_RUNTIME_COMMAND_WINNER_LAYER
            && commandBank.records[0].winningDefinitionId
                == TASK11_DEF_FLED_SEMANTIC
            && commandBank.records[0].winningOwnerId == 0x8107
            && commandBank.records[0].winningInstanceKey == 0
            && commandBank.records[0].winningEntryGeneration != 0
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "command origin capture changed runtime or lost captured policy");
    capturedCommandBank = commandBank;
    for (mutationIndex = 0;
            mutationIndex < sizeof(identityMutationOffsets)
                / sizeof(identityMutationOffsets[0]); mutationIndex++) {
        mutatedCommand = commandA;
        ((u8 *)&mutatedCommand)[identityMutationOffsets[mutationIndex]]
            ^= (u8)(mutationIndex < 5 ? 0x80 : 1);
        commandBank = capturedCommandBank;
        commandBankBefore = commandBank;
        runtimeBefore = runtime;
        memset(&consumed, 0xA5, sizeof(consumed));
        require(OverworldWildRuntime_ConsumeCommandOrigin(&runtime,
                &commandBank, 0, runtime.slots[0].slotGeneration,
                &mutatedCommand, &consumed)
                == (mutationIndex < 5
                    ? OW_WILD_RUNTIME_STATUS_STALE_NOOP
                    : OW_WILD_RUNTIME_STATUS_INVALID_HANDLE)
                && !memcmp(&consumed,
                    &(OverworldWildRuntimeCommandOrigin){0},
                    sizeof(consumed))
                && !memcmp(&commandBank, &commandBankBefore,
                    sizeof(commandBank))
                && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
            "mutated V11 command identity changed captured state");
    }
    for (mutationIndex = 0;
            mutationIndex < sizeof(originMutationOffsets)
                / sizeof(originMutationOffsets[0]); mutationIndex++) {
        commandBank = capturedCommandBank;
        ((u8 *)&commandBank.records[0])[
            originMutationOffsets[mutationIndex]] ^= 0x80;
        commandBankBefore = commandBank;
        runtimeBefore = runtime;
        memset(&consumed, 0xA5, sizeof(consumed));
        require(OverworldWildRuntime_ConsumeCommandOrigin(&runtime,
                &commandBank, 0, runtime.slots[0].slotGeneration,
                &commandA, &consumed) == OW_WILD_RUNTIME_STATUS_STALE_NOOP
                && !memcmp(&consumed,
                    &(OverworldWildRuntimeCommandOrigin){0},
                    sizeof(consumed))
                && !memcmp(&commandBank, &commandBankBefore,
                    sizeof(commandBank))
                && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
            "mutated V11 captured-origin tuple was consumed or changed");
    }
    commandBank = capturedCommandBank;
    commandBankBefore = commandBank;
    require(OverworldWildRuntime_CaptureCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandB)
            == OW_WILD_RUNTIME_STATUS_DATA_BUSY
            && !memcmp(&commandBank, &commandBankBefore, sizeof(commandBank))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "busy command capture changed the existing origin or runtime");
    memset(&consumed, 0xA5, sizeof(consumed));
    require(OverworldWildRuntime_ConsumeCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &wrongCommand, &consumed)
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&consumed, &(OverworldWildRuntimeCommandOrigin){0},
                sizeof(consumed))
            && !memcmp(&commandBank, &commandBankBefore, sizeof(commandBank))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "stale command identity changed captured origin or runtime");
    require(OverworldWildRuntime_ConsumeCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandA, &consumed)
            == OW_WILD_RUNTIME_STATUS_OK
            && consumed.commandGeneration == commandA.commandGeneration
            && consumed.objectGeneration == commandA.objectGeneration
            && !(commandBank.records[0].flags
                & OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID)
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "consumed command origin was not an exact once-only result");
    commandBankBefore = commandBank;
    runtimeBefore = runtime;
    memset(&consumed, 0xA5, sizeof(consumed));
    staleCommandStatus = OverworldWildRuntime_ConsumeCommandOrigin(
        &runtime, &commandBank, 0, runtime.slots[0].slotGeneration,
        &commandA, &consumed);
    require(staleCommandStatus == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&consumed, &(OverworldWildRuntimeCommandOrigin){0},
                sizeof(consumed))
            && !memcmp(&commandBank, &commandBankBefore, sizeof(commandBank))
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "duplicate command completion changed the command bank or runtime");
    require(OverworldWildRuntime_CaptureCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandB)
            == OW_WILD_RUNTIME_STATUS_OK,
        "cancel fixture could not capture command origin");
    OverworldWildRuntime_InvalidateCommandOrigin(&commandBank, 0);
    commandBankBefore = commandBank;
    memset(&consumed, 0xA5, sizeof(consumed));
    require(OverworldWildRuntime_ConsumeCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandB, &consumed)
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&commandBank, &commandBankBefore, sizeof(commandBank)),
        "canceled command origin remained consumable");
    require(OverworldWildRuntime_CaptureCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandA)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_CaptureCommandOrigin(&runtime,
                &commandBank, 1, runtime.slots[1].slotGeneration, &commandB)
                == OW_WILD_RUNTIME_STATUS_OK,
        "per-slot command origins could not coexist");
    OverworldWildRuntime_InvalidateCommandOrigin(&commandBank, 0);
    require(!(commandBank.records[0].flags
                & OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID)
            && (commandBank.records[1].flags
                & OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID),
        "single-slot command invalidation changed a bystander slot");
    OverworldWildRuntime_InvalidateAllCommandOrigins(&commandBank);
    require(!memcmp(&commandBank,
            &(OverworldWildRuntimeCommandOriginBank){0}, sizeof(commandBank)),
        "all-bank invalidation retained a command origin");
    require(OverworldWildRuntime_CaptureCommandOrigin(&runtime, &commandBank,
            0, runtime.slots[0].slotGeneration, &commandA)
            == OW_WILD_RUNTIME_STATUS_OK,
        "slot-reuse fixture could not capture command origin");
    oldSlotGeneration = runtime.slots[0].slotGeneration;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 0);
    require(OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &context, &resolved)
            == OW_WILD_RUNTIME_STATUS_OK,
        "slot-reuse fixture could not prime replacement encounter");
    runtimeBefore = runtime;
    commandBankBefore = commandBank;
    memset(&consumed, 0xA5, sizeof(consumed));
    require(runtime.slots[0].slotGeneration != oldSlotGeneration
            && OverworldWildRuntime_ConsumeCommandOrigin(&runtime,
                &commandBank, 0, runtime.slots[0].slotGeneration,
                &commandA, &consumed) == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime))
            && !memcmp(&commandBank, &commandBankBefore,
                sizeof(commandBank)),
        "slot reuse consumed or changed a stale command origin");
    OverworldWildRuntime_InvalidateAllCommandOrigins(&commandBank);

    prepare_task11_runtime(&runtime, 0, &context, &resolved);
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_STAMINA, 0x8105, 0);
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_CALM_OWNER_8102, 0x8102, 0);
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_CALM_OWNER_8103, 0x8103, 0);
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_CALM_OWNER_8104, 0x8104, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "legacy calm recovery fixture could not expire stamina tired");
    expiry = expiry_for_owner(&runtime, 0, 0x8105);
    require(expiry.validityTag != 0,
        "legacy calm recovery fixture lacked exact identities");
    calmRecoveryStatus = OverworldWildRuntime_RecoverExpiredTimer(
        &runtime, &expiry, &recovery);
    require(calmRecoveryStatus == OW_WILD_RUNTIME_STATUS_OK
            && recovery.ok && recovery.mutated
            && recovery.route
                == OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM
            && recovery.calmResetOwnerCount == 3
            && recovery.actionFlags
                == (OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER
                    | OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN)
            && FindLayer(&runtime.slots[0], 0x8105, 0) < 0
            && FindLayer(&runtime.slots[0], 0x8102, 0) < 0
            && FindLayer(&runtime.slots[0], 0x8103, 0) < 0
            && FindLayer(&runtime.slots[0], 0x8104, 0) < 0,
        "legacy calm recovery disturbed an unrelated layer or timer");
    runtimeBefore = runtime;
    require(OverworldWildRuntime_RecoverExpiredTimer(
            &runtime, &expiry, &recovery)
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && !memcmp(&runtime, &runtimeBefore, sizeof(runtime)),
        "stale recovery ticket changed runtime bytes");

    prepare_task11_runtime(&runtime, 0, &context, &resolved);
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_STAMINA, 0x8105, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "rejected recovery fixture could not expire candidate");
    expiry = expiry_for_owner(&runtime, 0, 0x8105);
    expiredRuntime = runtime;
    catalogBefore = sFixtureInstalledStorage;
    for (malformedCase = 0; malformedCase < 66; malformedCase++) {
        OverworldWildTransitionRecord *transition;
        OverworldWildOverrideDefinitionRecord *definition;
        OverworldWildTransitionGuardRecord *guard;
        OverworldWildTransitionOperationRecord *operation;
        OverworldWildTransitionActionRecord *action;
        OverworldWildRecoveryActionRecord *recoveryAction;
        sFixtureInstalledStorage = catalogBefore;
        transition = fixture_transition(TASK11_TRANSITION_STAMINA_RECOVER);
        definition = fixture_override_definition(TASK11_DEF_STAMINA);
        guard = fixture_transition_guard(
            TASK11_TRANSITION_STAMINA_RECOVER);
        operation = fixture_transition_operation(
            TASK11_TRANSITION_STAMINA_RECOVER, 0);
        action = fixture_transition_action(
            TASK11_TRANSITION_STAMINA_RECOVER, 0);
        recoveryAction = fixture_recovery_action(
            TASK11_TRANSITION_STAMINA_RECOVER);
        switch (malformedCase) {
        case 0: transition->stableId = 0; break;
        case 1:
            fixture_transition(TASK11_TRANSITION_FLED_SEMANTIC)->stableId =
                TASK11_TRANSITION_STAMINA_RECOVER;
            break;
        case 2: transition->candidateDefinitionId ^= 1; break;
        case 3: transition->ownerId ^= 1; break;
        case 4: transition->guardStart++; break;
        case 5: transition->guardCount = 0; break;
        case 6: transition->operationStart++; break;
        case 7: transition->operationCount = 2; break;
        case 8: transition->actionStart++; break;
        case 9: transition->actionCount = 1; break;
        case 10: transition->trigger = 0; break;
        case 11: transition->fromRoleMask = 0; break;
        case 12: transition->recoveryStart++; break;
        case 13: transition->recoveryCount = 0; break;
        case 14: transition->dispatchPriority = 0; break;
        case 15: definition->stableId = 0; break;
        case 16:
            fixture_override_definition(TASK11_DEF_FLED_SEMANTIC)->stableId =
                TASK11_DEF_STAMINA;
            break;
        case 17: definition->recoveryTransitionId = 0; break;
        case 18: definition->hasRequiredOwnerId = 0; break;
        case 19: definition->requiredOwnerId = 0; break;
        case 20: definition->reserved0 = 1; break;
        case 21: definition->reserved1 = 1; break;
        case 22: guard->stableId = 0; break;
        case 23: guard->stableId = transition->stableId; break;
        case 24: guard->transitionId = 0; break;
        case 25: guard->kind = 0; break;
        case 26: guard->negate = 1; break;
        case 27: guard->payload = 0; break;
        case 28: guard->reserved0 = 1; break;
        case 29: guard->referenceId = 1; break;
        case 30: guard->reserved = 1; break;
        case 31: operation->stableId = 0; break;
        case 32: operation->stableId = guard->stableId; break;
        case 33: operation->transitionId = 0; break;
        case 34: operation->definitionId = 0; break;
        case 35: operation->ownerId = 0; break;
        case 36: operation->replacementDefinitionId = 1; break;
        case 37: operation->policyId = 1; break;
        case 38: operation->instanceKey = 1; break;
        case 39: operation->kind = 0; break;
        case 40: operation->busyPolicy = OWBD_BUSY_QUEUE_EXACT; break;
        case 41: operation->required = FALSE; break;
        case 42: operation->reserved = 1; break;
        case 43:
            fixture_transition_operation(
                TASK11_TRANSITION_STAMINA_RECOVER, 1)->required = TRUE;
            break;
        case 44:
            fixture_transition_operation(
                TASK11_TRANSITION_STAMINA_RECOVER, 1)->ownerId = 0x8103;
            break;
        case 45:
            fixture_transition_operation(
                TASK11_TRANSITION_STAMINA_RECOVER, 1)->definitionId = 1;
            break;
        case 46: action->stableId = 0; break;
        case 47: action->stableId = guard->stableId; break;
        case 48: action->transitionId = 0; break;
        case 49: action->phase = OWBD_ACTION_PHASE_ENTRY; break;
        case 50: action->kind = OWBD_ACTION_RESET_ACTIVE_STEPS; break;
        case 51: action->referenceId = 1; break;
        case 52: action->payload = 1; break;
        case 53: recoveryAction->stableId = 0; break;
        case 54: recoveryAction->stableId = guard->stableId; break;
        case 55: recoveryAction->transitionId = 0; break;
        case 56: recoveryAction->ownerId = 0; break;
        case 57: recoveryAction->kind = 3; break;
        case 58: recoveryAction->required = FALSE; break;
        case 59:
            fixture_transition_action(
                TASK11_TRANSITION_STAMINA_RECOVER, 1)->kind =
                    OWBD_ACTION_RESET_TIRED_COUNTER;
            break;
        case 60: definition->flags ^= 1; break;
        case 61: definition->selectorKind = OWBD_SELECTOR_EXACT; break;
        case 62: definition->controllerId = 0x3001; break;
        case 63: definition->nodeId = 0x3103; break;
        case 64: definition->semanticRole = OWBD_ROLE_ATTENTIVE; break;
        case 65: definition->authoredTiredBound = 1; break;
        }
        runtime = expiredRuntime;
        require_task11_invalid_recovery(
            &runtime, &expiry, "recovery-closure", malformedCase);
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    require(OverworldWildRuntime_ResolveRecoveryCandidate(&fallbackContext,
            OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_OK,
        "exact malformed-plan fixture could not resolve its wrapper");
    prepare_task11_runtime(&runtime, 0, &fallbackContext, &resolved);
    (void)apply_one(&runtime, 0, &resolved.applicability,
        candidate.definitionId, candidate.ownerId, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "exact malformed-plan fixture could not expire its wrapper");
    expiry = expiry_for_owner(&runtime, 0, candidate.ownerId);
    expiredRuntime = runtime;
    catalogBefore = sFixtureInstalledStorage;
    for (malformedCase = 0; malformedCase < 6; malformedCase++) {
        OverworldWildOverrideDefinitionRecord *definition;
        sFixtureInstalledStorage = catalogBefore;
        definition = fixture_override_definition(TASK11_DEF_FLED_EXACT);
        if (malformedCase == 0) definition->flags = 0;
        else if (malformedCase == 1)
            definition->selectorKind = OWBD_SELECTOR_SEMANTIC_ROLE;
        else if (malformedCase == 2) definition->controllerId = 0;
        else if (malformedCase == 3) definition->nodeId = 0;
        else if (malformedCase == 4)
            definition->semanticRole = OWBD_ROLE_TIRED;
        else definition->authoredTiredBound = 1;
        runtime = expiredRuntime;
        require_task11_invalid_recovery(
            &runtime, &expiry, "exact-recovery-closure", malformedCase);
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    for (malformedCase = 0; malformedCase < 24; malformedCase++) {
        const OverworldWildRuntimeStaticContext *candidateContext = &context;
        OverworldWildOverrideDefinitionRecord *definition;
        OverworldWildTransitionRecord *transition;
        OverworldWildRecoveryActionRecord *recoveryAction;
        u16 definitionId = TASK11_DEF_FLED_SEMANTIC;
        u16 transitionId = TASK11_TRANSITION_FLED_SEMANTIC;
        u16 ownerId = 0x8107;
        u8 familyIndex = 0;
        BOOL exactSelector = FALSE;

        sFixtureInstalledStorage = catalogBefore;
        if (malformedCase < 6 || (malformedCase >= 6
                && malformedCase < 12)) {
            familyIndex = (u8)((malformedCase % 6) / 2);
            exactSelector = (malformedCase & 1) != 0;
        } else if (malformedCase >= 13 && malformedCase < 16) {
            familyIndex = (u8)(malformedCase - 13);
        } else if (malformedCase == 17 || malformedCase == 23) {
            exactSelector = TRUE;
        }
        if ((malformedCase < 12)
            || (malformedCase >= 13 && malformedCase <= 17)
            || malformedCase >= 22) {
            definitionId = exactSelector
                ? exactDefinitions[familyIndex]
                : authoredDefinitions[familyIndex];
            transitionId = exactSelector
                ? exactTransitions[familyIndex]
                : authoredTransitions[familyIndex];
            ownerId = originOwners[familyIndex];
            candidateContext = exactSelector ? &fallbackContext : &context;
        } else if (malformedCase == 12) {
            definitionId = TASK11_DEF_STAMINA;
            transitionId = TASK11_TRANSITION_STAMINA_RECOVER;
            ownerId = 0x8105;
        } else {
            definitionId = TASK11_DEF_FORCED_SLEEP;
            transitionId = TASK11_TRANSITION_FORCED_SLEEP;
            ownerId = malformedCase == 20 ? 0x810B : 0x810A;
            candidateContext = &sleepContext;
        }

        if (malformedCase == 0) {
            fixture_swap_recovery_route_claims(
                TASK11_TRANSITION_FLED_SEMANTIC,
                TASK11_DEF_FLED_SEMANTIC, 0x8107,
                TASK11_TRANSITION_RAM_SEMANTIC,
                TASK11_DEF_RAM_SEMANTIC, 0x8106);
            transitionId = TASK11_TRANSITION_RAM_SEMANTIC;
            fixture_reseal_installed_catalog();
        } else if (malformedCase == 1) {
            fixture_swap_recovery_route_claims(
                TASK11_TRANSITION_FLED_EXACT,
                TASK11_DEF_FLED_EXACT, 0x8107,
                TASK11_TRANSITION_RAM_EXACT,
                TASK11_DEF_RAM_EXACT, 0x8106);
            transitionId = TASK11_TRANSITION_RAM_EXACT;
            fixture_reseal_installed_catalog();
        } else if (malformedCase == 21) {
            fixture_swap_recovery_route_claims(
                TASK11_TRANSITION_FORCED_SLEEP,
                TASK11_DEF_FORCED_SLEEP, 0x810A,
                TASK11_TRANSITION_STAMINA_RECOVER,
                TASK11_DEF_STAMINA, 0x8105);
            transitionId = TASK11_TRANSITION_STAMINA_RECOVER;
            fixture_reseal_installed_catalog();
        }

        prepare_task11_runtime(&runtime, 0, candidateContext, &resolved);
        (void)apply_one(&runtime, 0, &resolved.applicability,
            definitionId, ownerId,
            definitionId == TASK11_DEF_FORCED_SLEEP ? 7 : 0);
        require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK,
            "closed-family malformed fixture could not expire candidate");
        expiry = expiry_for_owner(&runtime, 0, ownerId);
        definition = fixture_override_definition(definitionId);
        transition = fixture_transition(transitionId);
        recoveryAction = fixture_recovery_action(transitionId);

        if (malformedCase < 6) {
            if (familyIndex == 0) {
                require(transition->operationCount
                            == OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS + 1
                        && recoveryAction->kind
                            == OWBD_RECOVERY_ACTION_REMOVE_OWNER_IF_PRESENT,
                    "globally coherent tired route swap lost calm topology");
            } else {
                transition->operationCount = 1;
                recoveryAction->kind = OWBD_RECOVERY_ACTION_REMOVE_SELF;
            }
        } else if (malformedCase < 12) {
            static const u8 wrongOrigins[3] = {
                OWBD_TIRED_ORIGIN_RAM_CRASH,
                OWBD_TIRED_ORIGIN_THROW_RECOVERY,
                OWBD_TIRED_ORIGIN_FLED,
            };
            definition->tiredOriginKind = wrongOrigins[familyIndex];
        } else if (malformedCase == 12) {
            definition->hasTiredOriginKind = TRUE;
            definition->tiredOriginKind = OWBD_TIRED_ORIGIN_FLED;
        } else if (malformedCase < 16) {
            static const u16 wrongOwners[3] = {0x8106, 0x8108, 0x8107};
            definition->requiredOwnerId = wrongOwners[familyIndex];
        } else if (malformedCase == 16) {
            definition->hasRequiredOwnerId = FALSE;
        } else if (malformedCase == 17) {
            definition->requiredOwnerId = 0;
        } else if (malformedCase == 18) {
            definition->hasRequiredOwnerId = TRUE;
            definition->requiredOwnerId = 0x810A;
        } else if (malformedCase == 19) {
            transition->ownerId = 0x810B;
        } else if (malformedCase == 20) {
            OverworldWildTransitionOperationRecord *operation =
                fixture_transition_operation(transitionId, 0);
            transition->ownerId = ownerId;
            operation->ownerId = ownerId;
            recoveryAction->ownerId = ownerId;
        } else if (malformedCase == 21) {
            require(transition->operationCount
                        == OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS + 1
                    && recoveryAction->kind
                        == OWBD_RECOVERY_ACTION_REMOVE_OWNER_IF_PRESENT,
                "globally coherent sleep route swap lost calm topology");
        } else if (malformedCase == 22) {
            const OverworldWildOverrideDefinitionRecord *exactDefinition =
                fixture_override_definition(TASK11_DEF_FLED_EXACT);
            definition->selectorKind = OWBD_SELECTOR_EXACT;
            definition->controllerId = exactDefinition->controllerId;
            definition->nodeId = exactDefinition->nodeId;
            definition->semanticRole = 0;
            definition->flags = 1;
            transition->fromRoleMask = OWBD_ROLE_MASK(OWBD_ROLE_CUSTOM);
        } else {
            definition->selectorKind = OWBD_SELECTOR_SEMANTIC_ROLE;
            definition->controllerId = 0;
            definition->nodeId = 0;
            definition->semanticRole = OWBD_ROLE_TIRED;
            definition->flags = 0;
            transition->fromRoleMask = 0x7F;
        }
        fixture_reseal_installed_catalog();
        require_task11_invalid_recovery(
            &runtime, &expiry, "closed-family", malformedCase);
        closedFamilyMutationCount++;
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    for (malformedCase = 0; malformedCase < 19; malformedCase++) {
        sFixtureInstalledStorage = catalogBefore;
        prepare_task11_runtime(&runtime, 0, &context, &resolved);
        (void)apply_one(&runtime, 0, &resolved.applicability,
            TASK11_DEF_FLED_SEMANTIC, 0x8107, 0);
        require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK,
            "semantic backlink fixture could not expire candidate");
        expiry = expiry_for_owner(&runtime, 0, 0x8107);
        fixture_mutate_semantic_tired_backlink(malformedCase);
        fixture_reseal_installed_catalog();
        require_task11_invalid_recovery(
            &runtime, &expiry, "semantic-backlink", malformedCase);
        semanticBacklinkMutationCount++;
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    for (malformedCase = 0; malformedCase < 18; malformedCase++) {
        sFixtureInstalledStorage = catalogBefore;
        prepare_task11_runtime(&runtime, 0, &fallbackContext, &resolved);
        (void)apply_one(&runtime, 0, &resolved.applicability,
            TASK11_DEF_FLED_EXACT, 0x8107, 0);
        require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK,
            "exact backlink fixture could not expire candidate");
        expiry = expiry_for_owner(&runtime, 0, 0x8107);
        fixture_mutate_exact_tired_backlink(malformedCase);
        fixture_reseal_installed_catalog();
        require_task11_invalid_recovery(
            &runtime, &expiry, "exact-backlink", malformedCase);
        exactBacklinkMutationCount++;
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    for (malformedCase = 0; malformedCase < 2; malformedCase++) {
        sFixtureInstalledStorage = catalogBefore;
        prepare_task11_runtime(&runtime, 0, &context, &resolved);
        (void)apply_one(&runtime, 0, &resolved.applicability,
            TASK11_DEF_STAMINA, 0x8105, 0);
        require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK,
            "stamina backlink fixture could not expire candidate");
        expiry = expiry_for_owner(&runtime, 0, 0x8105);
        fixture_mutate_stamina_backlink(malformedCase);
        fixture_reseal_installed_catalog();
        require_task11_invalid_recovery(
            &runtime, &expiry, "stamina-backlink", malformedCase);
        staminaBacklinkMutationCount++;
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    for (malformedCase = 0; malformedCase < 22; malformedCase++) {
        sFixtureInstalledStorage = catalogBefore;
        prepare_task11_runtime(&runtime, 0, &sleepContext, &resolved);
        (void)apply_one(&runtime, 0, &resolved.applicability,
            TASK11_DEF_FORCED_SLEEP, 0x810A, 7);
        require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK,
            "forced-sleep backlink fixture could not expire candidate");
        expiry = expiry_for_owner(&runtime, 0, 0x810A);
        fixture_mutate_forced_sleep_backlink(malformedCase);
        fixture_reseal_installed_catalog();
        require_task11_invalid_recovery(
            &runtime, &expiry, "sleep-backlink", malformedCase);
        sleepBacklinkMutationCount++;
        malformedRecoveryCount++;
    }
    sFixtureInstalledStorage = catalogBefore;

    prepare_task11_runtime(&runtime, 0, &context, &resolved);
    (void)apply_one(&runtime, 0, &authored.applicability,
        TASK11_DEF_FLED_SEMANTIC, 0x8107, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK,
        "remove-self recovery fixture could not expire FLED candidate");
    expiry = expiry_for_owner(&runtime, 0, 0x8107);
    removeSelfStatus = OverworldWildRuntime_RecoverExpiredTimer(
        &runtime, &expiry, &recovery);
    require(removeSelfStatus == OW_WILD_RUNTIME_STATUS_OK
            && recovery.route == OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF
            && recovery.calmResetOwnerCount == 0
            && FindLayer(&runtime.slots[0], 0x8107, 0) < 0
            && recovery.actionFlags
                == (OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER
                    | OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN),
        "remove-self recovery removed a bystander layer or timer");

    for (mutationIndex = 0; mutationIndex < 2; mutationIndex++) {
        const OverworldWildRuntimeStaticContext *candidateContext =
            mutationIndex == 0 ? &context : &fallbackContext;
        for (index = 0; index < 3; index++) {
            const u8 expectedRoute = index == 0
                ? OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF
                : OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM;
            require(OverworldWildRuntime_ResolveRecoveryCandidate(
                    candidateContext, imperativeOrigins[index], &candidate)
                    == OW_WILD_RUNTIME_STATUS_OK,
                "end-to-end recovery candidate resolution failed");
            prepare_task11_runtime(&runtime, 0,
                candidateContext, &resolved);
            (void)apply_one(&runtime, 0, &resolved.applicability,
                TASK11_DEF_CALM_OWNER_8102, 0x8102, 0);
            (void)apply_one(&runtime, 0, &resolved.applicability,
                TASK11_DEF_CALM_OWNER_8103, 0x8103, 0);
            (void)apply_one(&runtime, 0, &resolved.applicability,
                TASK11_DEF_CALM_OWNER_8104, 0x8104, 0);
            (void)apply_one(&runtime, 0, &resolved.applicability,
                candidate.definitionId, candidate.ownerId, 0);
            require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                    runtime.slots[0].slotGeneration,
                    OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
                    == OW_WILD_RUNTIME_STATUS_OK,
                "end-to-end generated wrapper timer did not tick");
            expiry = expiry_for_owner(&runtime, 0, candidate.ownerId);
            require(expiry.definitionId == candidate.definitionId
                    && expiry.recoveryTransitionId
                        == candidate.recoveryTransitionId,
                "expiry ticket lost its exact generated wrapper identity");
            endToEndStatus = OverworldWildRuntime_RecoverExpiredTimer(
                &runtime, &expiry, &recovery);
            if (endToEndStatus != OW_WILD_RUNTIME_STATUS_OK
                || recovery.route != expectedRoute
                || recovery.actionFlags
                    != (OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER
                        | OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN)
                || recovery.calmResetOwnerCount
                    != (u8)(index == 0 ? 0 : 3))
                fprintf(stderr,
                    "end-to-end recovery exact=%u origin=%u status=%u "
                    "route=%u actions=%u calm=%u\n",
                    mutationIndex, index + 1, endToEndStatus,
                    recovery.route, recovery.actionFlags,
                    recovery.calmResetOwnerCount);
            require(endToEndStatus == OW_WILD_RUNTIME_STATUS_OK
                    && recovery.route == expectedRoute
                    && recovery.actionFlags
                        == (OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER
                            | OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN)
                    && recovery.calmResetOwnerCount
                        == (u8)(index == 0 ? 0 : 3)
                    && FindLayer(&runtime.slots[0], candidate.ownerId, 0) < 0
                    && (index == 0
                        ? (FindLayer(&runtime.slots[0], 0x8102, 0) >= 0
                            && FindLayer(&runtime.slots[0], 0x8103, 0) >= 0
                            && FindLayer(&runtime.slots[0], 0x8104, 0) >= 0)
                        : (FindLayer(&runtime.slots[0], 0x8102, 0) < 0
                            && FindLayer(&runtime.slots[0], 0x8103, 0) < 0
                            && FindLayer(&runtime.slots[0], 0x8104, 0) < 0)),
                "semantic/exact generated wrapper recovery route diverged");
        }
    }

    prepare_runtime_unprimed(&runtime, 0);
    require(OverworldWildRuntime_PrimeCanonicalEffectiveCache(&runtime, 0,
            runtime.slots[0].slotGeneration, &sleepContext, &resolved)
            == OW_WILD_RUNTIME_STATUS_OK
            && (resolved.applicability.semanticRoleMask
                & OWBD_ROLE_MASK(OWBD_ROLE_ASLEEP)),
        "forced-sleep fixture did not bind an authored asleep node");
    (void)apply_one(&runtime, 0, &resolved.applicability,
        TASK11_DEF_FORCED_SLEEP, 0x810A, 7);
    (void)apply_one(&runtime, 0, &resolved.applicability,
        TASK11_DEF_CALM_OWNER_8102, 0x8121, 0);
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 4, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && (timer_for_owner_key(&runtime, 0, 0x810A, 7)->flags
                & OW_WILD_RUNTIME_TIMER_ZERO_PENDING),
        "hidden forced-sleep timer did not continue to expiry");
    expiry = expiry_for_owner(&runtime, 0, 0x810A);
    require(OverworldWildRuntime_RecoverExpiredTimer(
            &runtime, &expiry, &recovery) == OW_WILD_RUNTIME_STATUS_OK
            && recovery.route == OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF
            && FindLayer(&runtime.slots[0], 0x810A, 7) < 0
            && FindLayer(&runtime.slots[0], 0x8121, 0) >= 0,
        "forced-sleep remove-self recovery disturbed its covering layer");
    sUseTask11ProductionCatalog = FALSE;

    printf("TASK11_SUBSTRATE_TRACE invalidSelection=%u staleCommand=%u "
           "calmRecovery=%u removeSelf=%u canonicalMutations=6 "
           "commandMutations=28 recoveries=6 malformed=%u "
           "mappingMutations=%u backlinkMutations=61 "
           "semanticBacklinks=%u exactBacklinks=%u staminaBacklinks=%u "
           "sleepBacklinks=%u calmOwners=3 actions=10\n",
        invalidSelectionStatus, staleCommandStatus,
        calmRecoveryStatus, removeSelfStatus, malformedRecoveryCount,
        closedFamilyMutationCount, semanticBacklinkMutationCount,
        exactBacklinkMutationCount, staminaBacklinkMutationCount,
        sleepBacklinkMutationCount);
}

static void test_task11_transition_dispatcher(void)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeResolvedStaticContext resolved;
    OverworldWildRuntimeTransitionEvent event;
    OverworldWildRuntimeTransitionEvent oldReplayEvent;
    OverworldWildRuntimeTransitionResult result;
    OverworldWildRuntimeStackDeltaResult delta;
    OverworldWildRuntimeTimerTickResult tick;
    OverworldWildRuntimeTimerExpiry expiry = {0};
    OverworldWildRuntimeTimerExpiry rearmedExpiry = {0};
    OverworldWildRuntimeStaticContext calmContext;
    OverworldWildRuntimeStaticContext activeContext = fixture_static_context();
    union FixtureInstalledCatalogStorage catalogBefore;
    u16 fillDefinitions[8] = {
        0x7001, 0x7003, 0x7004, 0x7005,
        0x7006, 0x7007, 0x700A, 0x700A,
    };
    u16 fillOwners[8] = {
        0x8102, 0x8104, 0x8105, 0x8107,
        0x8106, 0x8108, 0x810A, 0x810A,
    };
    u16 fillKeys[8] = {0, 0, 0, 0, 0, 0, 1, 2};
    u8 index;

    sUseTask11ProductionCatalog = TRUE;
    calmContext = fixture_static_context();
    calmContext.species = 56;
    calmContext.groupFlags = 8;
    prepare_task11_runtime(&runtime, 0, &calmContext, &resolved);
    require(runtime.slots[0].effectiveCache.semanticRole == OWBD_ROLE_CALM,
        "transition fixture did not begin in calm role");
    memset(&event, 0, sizeof(event));
    event.trigger = OWBD_TRIGGER_ALERT_COMPLETE;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && result.ok && result.mutated && result.operationCount == 1
            && result.transitionId == TASK11_TRANSITION_ALERT_COMPLETE
            && result.definitionId == 0x7001
            && result.ownerId == 0x8102 && result.instanceKey == 0
            && result.actionFlags
                == (OW_WILD_RUNTIME_TRANSITION_ACTION(
                        OWBD_ACTION_RESET_ACTIVE_STEPS)
                    | OW_WILD_RUNTIME_TRANSITION_ACTION(
                        OWBD_ACTION_ALERT_COMPLETE)
                    | OW_WILD_RUNTIME_TRANSITION_ACTION(
                        OWBD_ACTION_ACTIVE_ENTRY_TRY_PICKUP_THROW))
            && result.effectiveAfter.semanticRole == OWBD_ROLE_ATTENTIVE
            && result.effectiveAfter.profileId != 0,
        "alert transition did not publish catalog action/winner output");
    before = runtime;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
            && !result.ok && !memcmp(&runtime, &before, sizeof(runtime)),
        "alert effective-role guard changed state when false");

    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    memset(&event, 0, sizeof(event));
    event.trigger = event.systemRoute = OWBD_TRIGGER_STAMINA_EXHAUSTED;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && result.ok && result.mutated && result.operationCount == 1
            && result.transitionId == TASK11_TRANSITION_STAMINA_APPLY
            && result.definitionId == TASK11_DEF_STAMINA
            && result.ownerId == 0x8105 && result.instanceKey == 0
            && result.actionFlags
                == OW_WILD_RUNTIME_TRANSITION_ACTION(
                    OWBD_ACTION_CLEAR_MOVEMENT_CHAIN)
            && result.effectiveAfter.semanticRole == OWBD_ROLE_TIRED
            && result.effectiveAfter.profileId == resolved.tiredProfileId,
        "stamina exhaustion did not apply the authored tired override");

    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    memset(&event, 0, sizeof(event));
    event.trigger = event.systemRoute = OWBD_TRIGGER_AGGRO_APPLY;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && result.transitionId == TASK11_TRANSITION_AGGRO_APPLY
            && result.definitionId == 0x7002 && result.ownerId == 0x8103
            && result.actionFlags
                == OW_WILD_RUNTIME_TRANSITION_ACTION(
                    OWBD_ACTION_RESET_ACTIVE_STEPS),
        "aggro transition did not use catalog-owned identity");
    before = runtime;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_IDEMPOTENT
            && result.ok && !result.mutated && result.actionFlags == 0
            && !memcmp(&runtime, &before, sizeof(runtime)),
        "duplicate aggro transition was not an action-free idempotent");
    event.systemRoute = 0;
    before = runtime;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
            && !memcmp(&runtime, &before, sizeof(runtime)),
        "system-route guard failure changed runtime");

    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    memset(&event, 0, sizeof(event));
    event.trigger = event.systemRoute = OWBD_TRIGGER_HELP_CALL_APPLY;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && result.transitionId == TASK11_TRANSITION_HELP_CALL_APPLY
            && result.definitionId == 0x7003 && result.ownerId == 0x8104,
        "help-call transition did not use catalog-owned identity");

    {
        static const u8 systemRoutes[] = {
            OWBD_TRIGGER_STAMINA_EXHAUSTED,
            OWBD_TRIGGER_FLED,
            OWBD_TRIGGER_RAM_CRASH,
            OWBD_TRIGGER_THROW_RECOVERY,
            OWBD_TRIGGER_AGGRO_APPLY,
            OWBD_TRIGGER_HELP_CALL_APPLY,
            OWBD_TRIGGER_FOLLOWER_APPLY,
        };
        for (index = 0; index < sizeof(systemRoutes); index++) {
            prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
            memset(&event, 0, sizeof(event));
            event.trigger = systemRoutes[index];
            event.systemRoute = systemRoutes[index]
                    == OWBD_TRIGGER_AGGRO_APPLY
                ? OWBD_TRIGGER_HELP_CALL_APPLY
                : OWBD_TRIGGER_AGGRO_APPLY;
            before = runtime;
            require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
                    runtime.slots[0].slotGeneration, &event, &result)
                    == OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
                    && !memcmp(&runtime, &before, sizeof(runtime)),
                "SYSTEM_ROUTE guard accepted mismatched live evidence");
            prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
            memset(&event, 0, sizeof(event));
            event.trigger = event.systemRoute = systemRoutes[index];
            require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
                    runtime.slots[0].slotGeneration, &event, &result)
                    != OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE,
                "SYSTEM_ROUTE guard rejected its exact live evidence");
        }
    }

    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    for (index = 0; index < sizeof(event.replayExpiry); index++) {
        memset(&event, 0, sizeof(event));
        event.trigger = OWBD_TRIGGER_ALERT_COMPLETE;
        ((u8 *)&event.replayExpiry)[index] = 1;
        before = runtime;
        require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
                runtime.slots[0].slotGeneration, &event, &result)
                == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE
                && !result.ok && !memcmp(&runtime, &before, sizeof(runtime)),
            "ordinary transition accepted a nonzero replay-only byte");
    }

    activeContext.behaviorClass = 2;
    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    for (index = 0; index < 3; index++)
        require(OverworldWildRuntime_Apply(&runtime, 0,
                runtime.slots[0].slotGeneration, &resolved.applicability,
                fillDefinitions[index], fillOwners[index], fillKeys[index],
                &delta)
                == OW_WILD_RUNTIME_STATUS_OK,
            "multi-operation recovery setup failed");
    require(OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
            runtime.slots[0].slotGeneration,
            OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 255, FALSE, &tick)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_GetPendingTimerExpiryByIndex(&runtime, 0,
                runtime.slots[0].slotGeneration, 0, &expiry)
                == OW_WILD_RUNTIME_STATUS_OK,
        "multi-operation recovery expiry setup failed");
    memset(&event, 0, sizeof(event));
    event.trigger = OWBD_TRIGGER_TIRED_EXPIRED;
    event.replayExpiry = expiry;
    event.flags = OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY;
    oldReplayEvent = event;
    before = runtime;
    event.replayExpiry.timerGeneration++;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && result.ok && !result.mutated
            && !memcmp(&runtime, &before, sizeof(runtime)),
        "edited replay timer identity was not a mutation-free stale no-op");
    event = oldReplayEvent;
    for (index = 0; index < runtime.slots[0].activeLayerCount; index++)
        if (runtime.slots[0].timerBank.timers[index].timerGeneration
                == expiry.timerGeneration)
            break;
    require(index < runtime.slots[0].activeLayerCount,
        "expiry replay lost its pending live timer");
    runtime.slots[0].timerBank.timers[index].remainingTicks = 1;
    runtime.slots[0].timerBank.timers[index].flags &=
        (u8)~OW_WILD_RUNTIME_TIMER_ZERO_PENDING;
    before = runtime;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && result.ok && !result.mutated
            && !memcmp(&runtime, &before, sizeof(runtime)),
        "non-pending replay ticket affected a live timer");
    runtime.slots[0].timerBank.timers[index].remainingTicks = 0;
    runtime.slots[0].timerBank.timers[index].flags |=
        OW_WILD_RUNTIME_TIMER_ZERO_PENDING;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_OK
            && result.mutated && result.operationCount == 4
            && runtime.slots[0].activeLayerCount == 0
            && result.actionFlags
                == (OW_WILD_RUNTIME_TRANSITION_ACTION(
                        OWBD_ACTION_RESET_TIRED_COUNTER)
                    | OW_WILD_RUNTIME_TRANSITION_ACTION(
                        OWBD_ACTION_START_POST_TIRED_COOLDOWN))
            && result.effectiveAfter.semanticRole
                == runtime.slots[0].staticCache.baseSemanticRole,
        "catalog multi-operation recovery was not one atomic winner reveal");

    require(OverworldWildRuntime_Apply(&runtime, 0,
            runtime.slots[0].slotGeneration, &resolved.applicability,
            expiry.definitionId, expiry.ownerId, expiry.instanceKey, &delta)
            == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_TickCandidateTimers(&runtime, 0,
                runtime.slots[0].slotGeneration,
                OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 255, FALSE, &tick)
                == OW_WILD_RUNTIME_STATUS_OK
            && OverworldWildRuntime_GetPendingTimerExpiryByIndex(&runtime, 0,
                runtime.slots[0].slotGeneration, 0, &rearmedExpiry)
                == OW_WILD_RUNTIME_STATUS_OK
            && (rearmedExpiry.entryGeneration != expiry.entryGeneration
                || rearmedExpiry.timerGeneration != expiry.timerGeneration),
        "timer replay fixture did not create a distinct rearmed identity");
    before = runtime;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &oldReplayEvent, &result)
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP
            && result.ok && !result.mutated
            && !memcmp(&runtime, &before, sizeof(runtime)),
        "old expiry ticket affected a rearmed current timer");

    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    for (index = 0; index < 8; index++)
        require(OverworldWildRuntime_Apply(&runtime, 0,
                runtime.slots[0].slotGeneration, &resolved.applicability,
                fillDefinitions[index], fillOwners[index], fillKeys[index],
                &delta)
                == OW_WILD_RUNTIME_STATUS_OK,
            "capacity rollback setup failed");
    before = runtime;
    memset(&event, 0, sizeof(event));
    event.trigger = event.systemRoute = OWBD_TRIGGER_AGGRO_APPLY;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_CAPACITY_EXCEEDED
            && !result.ok && !memcmp(&runtime, &before, sizeof(runtime)),
        "failed catalog transition published a partial delta");

    catalogBefore = sFixtureInstalledStorage;
    fixture_transition(TASK11_TRANSITION_HELP_CALL_APPLY)->trigger =
        OWBD_TRIGGER_AGGRO_APPLY;
    fixture_transition(TASK11_TRANSITION_HELP_CALL_APPLY)->dispatchPriority =
        fixture_transition(TASK11_TRANSITION_AGGRO_APPLY)->dispatchPriority;
    prepare_task11_runtime(&runtime, 0, &activeContext, &resolved);
    before = runtime;
    require(OverworldWildRuntime_DispatchTransition(&runtime, 0,
            runtime.slots[0].slotGeneration, &event, &result)
            == OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR
            && !memcmp(&runtime, &before, sizeof(runtime)),
        "equal-priority transition selection was not rejected atomically");
    sFixtureInstalledStorage = catalogBefore;
    sUseTask11ProductionCatalog = FALSE;
}
#endif

int main(void)
{
    OverworldWildRuntimeApplicabilityInput input = fixture_applicability();
    OverworldWildRuntimeDefinition copied;

    sFixtureCatalog = fixture_catalog();
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    init_fixture_installed_blob();
#endif
    require(
        OverworldWildRuntime_CopyInstalledDefinition(DEF_SHARED, &copied)
            && copied.stableId == DEF_SHARED,
        "validated definition copy-out failed");
    test_apply_replace_remove(&input);
    test_handles_and_atomicity(&input);
    test_boundary_phase_late_slot_atomicity(&input);
    test_ambiguity_and_order(&input);
    test_multiplicity_capacity_and_clear(&input);
    test_generated_applicability_and_generation(&input);
    test_role_mask_boundaries(&input);
    test_batch_policy_owner_and_lifecycle(&input);
    test_global_rekey_and_terminal_restart(&input);
    test_task7_destructive_wrap_rekey(&input);
    test_task7_corrupt_wrap_invalidation(&input);
    test_canonical_preflight_and_restart(&input);
    test_forced_zero_identity_rotation(&input);
    test_task5_v40_scalar_domains();
    test_task9_composition_cache_and_provenance(&input);
    test_task10_timer_engine(&input);
#ifdef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
    test_task11_substrate(&input);
    test_task11_transition_dispatcher();
#endif
    run_task6_crosscheck_corpus(&input);
    printf(
        "runtime layers host fixture: %d checks; handle=%lu op=%lu request=%lu result=%lu; maxOps=%d capacity=%d\n",
        sChecks,
        (unsigned long)sizeof(OverworldWildRuntimeLayerHandle),
        (unsigned long)sizeof(OverworldWildRuntimeDeltaOperation),
        (unsigned long)sizeof(OverworldWildRuntimeStackDeltaRequest),
        (unsigned long)sizeof(OverworldWildRuntimeStackDeltaResult),
        OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS,
        OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT);
    return 0;
}

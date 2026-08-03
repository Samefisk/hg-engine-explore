#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int8_t s8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_RUNTIME_STATE_VALUE_COUNT 28
#define OW_WILD_RUNTIME_CONTROLLER_VALUE_COUNT 9
#define OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS 8
#define OW_WILD_RUNTIME_MAX_RESOLVED_NODES 8
#define OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE 1
#define OW_WILD_RUNTIME_DEFINITION_MODIFIER 2
#define OW_WILD_RUNTIME_SELECTOR_EXACT 1
#define OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE 2
#define OWBD_NODE_FLAG_BASE (1u << 0)
#define OW_WILD_RUNTIME_FIELD_STATE 1
#define OW_WILD_RUNTIME_FIELD_CONTROLLER 2
#define OW_WILD_RUNTIME_OPERATOR_SET 1
#define OW_WILD_RUNTIME_OPERATOR_ADD 2
#define OW_WILD_RUNTIME_OPERATOR_AT_LEAST 3
#define OW_WILD_RUNTIME_OPERATOR_AT_MOST 4
#define OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST 5
#define OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST 6
#define OWBD_STATIC_ACTION_BIND_NODE 2
#define OWBD_STATIC_ACTION_UNBIND_NODE 3
#define OWBD_STATIC_ACTION_APPLY_STATE_MODIFIER 4
#define OWBD_STATIC_ACTION_APPLY_CONTROLLER_MODIFIER 5
#define OWBD_STATIC_ACTION_BIND_SPAWN_POLICY 6
#define OWBD_STATIC_ACTION_BIND_POPULATION_POLICY 8

#define OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE (1u << 0)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN (1u << 1)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER (1u << 2)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS (1u << 3)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES (1u << 4)

typedef enum OverworldWildRuntimeStatus {
    OW_WILD_RUNTIME_STATUS_OK = 0,
    OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA = 21,
} OverworldWildRuntimeStatus;

typedef struct __attribute__((packed)) OverworldWildBlobSection {
    u32 offset;
    u16 count;
    u16 entrySize;
} OverworldWildBlobSection;

typedef struct __attribute__((packed)) OverworldWildOverrideDefinitionRecord {
    u16 stableId;
    u16 nameId;
    u16 controllerId;
    u16 nodeId;
    u16 requiredOwnerId;
    u16 recoveryTransitionId;
    u16 applicabilityId;
    u16 priority;
    u8 kind;
    u8 channel;
    u8 selectorKind;
    u8 semanticRole;
    u8 mapLifetime;
    u8 battleLifetime;
    u8 timerClock;
    u8 timerSource;
    u8 hiddenTimerPolicy;
    u8 recoveryPolicy;
    u8 timerValue;
    u8 hasTiredOriginKind;
    u8 tiredOriginKind;
    u8 hasRequiredOwnerId;
    u8 allowMultipleOwners;
    u8 allowMultipleInstancesPerOwner;
    u8 authoredTiredBound;
    u8 flags;
    u8 reserved0;
    u8 reserved1;
} OverworldWildOverrideDefinitionRecord;

typedef struct __attribute__((packed)) OverworldWildApplicabilityRecord {
    u16 stableId;
    u16 flags;
    u32 immutableContextMask;
    u16 controllerId;
    u16 effectiveProfileId;
    u8 semanticRole;
    u8 reserved0;
    u16 reserved;
} OverworldWildApplicabilityRecord;

typedef struct __attribute__((packed)) OverworldWildStateBodyRecord {
    u16 stableId;
    u8 provenanceKind;
    u8 valueCount;
    u8 values[28];
} OverworldWildStateBodyRecord;

typedef struct __attribute__((packed)) OverworldWildProfileIdentityRecord {
    u16 stableId;
    u16 bodyId;
    u16 provenanceRecipeId;
    u8 tagA;
    u8 tagB;
} OverworldWildProfileIdentityRecord;

typedef struct __attribute__((packed)) OverworldWildControllerRecord {
    u16 stableId;
    u16 nameId;
    u16 nodeStart;
    u16 nodeCount;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u16 hookSetId;
    u8 alertState;
    u8 alertEmote;
    u8 alertTime;
    u8 alertness;
    u8 alertRange;
    u8 alertChance;
    u8 stamina;
    u8 restTime;
    u8 flags;
    u8 reserved;
} OverworldWildControllerRecord;

typedef struct __attribute__((packed)) OverworldWildControllerNodeRecord {
    u16 stableId;
    u16 controllerId;
    u16 profileIdentityId;
    u16 customRoleId;
    u8 semanticRole;
    u8 flags;
    u16 reserved;
} OverworldWildControllerNodeRecord;

typedef struct __attribute__((packed)) OverworldWildBehaviorMatch {
    u32 groupMask;
    u16 species;
    u8 terrain;
    u8 minLevel;
    u8 maxLevel;
    u8 shiny;
    u8 behaviorClass;
    u8 reserved;
} OverworldWildBehaviorMatch;

typedef struct __attribute__((packed)) OverworldWildOverrideSourceRecord {
    u16 stableId;
    u16 nameId;
    OverworldWildBehaviorMatch match;
    u16 memberStart;
    u16 memberCount;
    u16 actionStart;
    u16 actionCount;
    u8 targetMode;
    u8 order;
    u16 priority;
} OverworldWildOverrideSourceRecord;

typedef struct __attribute__((packed)) OverworldWildGenericAssignmentRecord {
    u16 stableId;
    OverworldWildBehaviorMatch match;
    u16 assignmentActionIndex;
    u16 priority;
    u16 reserved;
} OverworldWildGenericAssignmentRecord;

typedef struct __attribute__((packed)) OverworldWildSpeciesAssignmentRecord {
    u16 stableId;
    u16 species;
    u16 assignmentActionIndex;
    u16 priority;
} OverworldWildSpeciesAssignmentRecord;

typedef union __attribute__((packed)) OverworldWildStaticActionPayload {
    struct __attribute__((packed)) { u16 controllerId, reserved0, reserved1, reserved2; } assignController;
    struct __attribute__((packed)) { u16 controllerId, nodeId, profileIdentityId, reserved; } bindNode;
    struct __attribute__((packed)) { u8 fieldId, operatorKind; int8_t delta; u8 bound, semanticRoleMask, reserved; u16 controllerId; } modifier;
    struct __attribute__((packed)) { u16 policyId, reserved0, reserved1, reserved2; } bindPolicy;
    u8 raw[8];
} OverworldWildStaticActionPayload;

typedef struct __attribute__((packed)) OverworldWildStaticActionRecord {
    u16 stableId;
    u8 kind;
    u8 flags;
    OverworldWildStaticActionPayload payload;
} OverworldWildStaticActionRecord;

typedef struct __attribute__((packed)) OverworldWildTiredTranslationRecord {
    u16 stableId;
    u8 tiredOriginKind;
    u8 authoredTiredBound;
    u16 destinationControllerId;
    u16 authoredProfileId;
    u16 candidateDefinitionId;
    u16 recoveryTransitionId;
    u16 exactFallbackControllerId;
    u16 exactFallbackNodeId;
    u8 timerOperator;
    u8 timerSource;
    u8 mapLifetime;
    u8 battleLifetime;
    u16 flags;
    u16 reserved;
} OverworldWildTiredTranslationRecord;

typedef struct __attribute__((packed)) OverworldWildBehaviorDataBlobHeader {
    u32 magic;
    u16 version;
    u16 headerSize;
    u32 blobSize;
    u32 flags;
    u32 checksum;
    u32 schemaFingerprint;
    OverworldWildBlobSection stateBodies;
    OverworldWildBlobSection profileIdentities;
    OverworldWildBlobSection controllers;
    OverworldWildBlobSection controllerNodes;
    OverworldWildBlobSection sourceClassProfiles;
    OverworldWildBlobSection genericAssignments;
    OverworldWildBlobSection speciesAssignments;
    OverworldWildBlobSection overrideSources;
    OverworldWildBlobSection overrideMembers;
    OverworldWildBlobSection overrideActions;
    OverworldWildBlobSection spawnPolicies;
    OverworldWildBlobSection populationPolicies;
    OverworldWildBlobSection hookSets;
    OverworldWildBlobSection owners;
    OverworldWildBlobSection overrideDefinitions;
    OverworldWildBlobSection transitions;
    OverworldWildBlobSection transitionGuards;
    OverworldWildBlobSection transitionOperations;
    OverworldWildBlobSection transitionActions;
    OverworldWildBlobSection recoveryActions;
    OverworldWildBlobSection importRecipes;
    OverworldWildBlobSection applicability;
    OverworldWildBlobSection tiredTranslations;
    OverworldWildBlobSection semanticIds;
} OverworldWildBehaviorDataBlobHeader;

typedef struct OverworldWildRuntimeDefinition {
    u32 immutableContextMask;
    u16 stableId;
    u16 controllerId;
    u16 nodeId;
    u16 requiredOwnerId;
    u16 effectiveProfileId;
    u8 kind;
    u8 selectorKind;
    u8 semanticRole;
    u8 tiredOriginKind;
    u8 flags;
    u8 mapLifetime;
    u8 battleLifetime;
    u8 applicabilitySemanticRole;
    u8 channel;
    u8 priority;
} OverworldWildRuntimeDefinition;

typedef struct OverworldWildRuntimeApplicabilityInput {
    u32 immutableContextMask;
    u16 controllerId;
    u16 boundNodeIds[8];
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u16 effectiveProfileId;
    u8 effectiveSemanticRole;
    u8 reserved;
} OverworldWildRuntimeApplicabilityInput;

typedef struct OverworldWildRuntimeStaticContext {
    u32 groupFlags;
    u16 species;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 behaviorClass;
    u16 reserved;
} OverworldWildRuntimeStaticContext;

typedef struct OverworldWildRuntimeStaticModifierContribution {
    u16 modifierDefinitionId;
    u16 targetNodeId;
    u16 staticPriority;
    u16 ruleStableId;
    u16 actionStableId;
    signed short operand;
    u8 fieldNamespace;
    u8 fieldId;
    u8 operatorKind;
    u8 bound;
    u8 before;
    u8 after;
} OverworldWildRuntimeStaticModifierContribution;

typedef struct OverworldWildRuntimeResolvedNode {
    u16 nodeId;
    u16 profileId;
    u16 customRoleId;
    u8 semanticRole;
    u8 flags;
    u8 bound;
    u8 reserved;
    u8 stateValues[28];
} OverworldWildRuntimeResolvedNode;

typedef struct OverworldWildRuntimeStaticComposition {
    u32 catalogIdentity;
    u32 staticContextIdentity;
    u32 staticSetHash;
    u32 immutableContextMask;
    OverworldWildRuntimeStaticContext staticContext;
    u16 controllerId;
    u16 baseNodeId;
    u16 baseProfileId;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u8 baseSemanticRole;
    u8 valid;
    u8 nodeCount;
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u8 staticModifierCount;
    u8 reserved;
    u8 padding[3];
    u8 stateValues[28];
    u8 controllerValues[9];
    OverworldWildRuntimeResolvedNode
        resolvedNodes[OW_WILD_RUNTIME_MAX_RESOLVED_NODES];
    OverworldWildRuntimeStaticModifierContribution staticModifiers[8];
} OverworldWildRuntimeStaticComposition;

typedef struct OverworldWildRuntimeStaticCache {
    u32 catalogIdentity;
    u32 staticContextIdentity;
    u32 staticSetHash;
    u32 staticContextGeneration;
    u32 immutableContextMask;
    OverworldWildRuntimeStaticContext staticContext;
    u16 controllerId;
    u16 baseNodeId;
    u16 baseProfileId;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u8 baseSemanticRole;
    u8 valid;
    u8 nodeCount;
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u8 staticModifierCount;
    u8 reserved;
    u8 padding[3];
    u8 stateValues[28];
    u8 controllerValues[9];
    OverworldWildRuntimeResolvedNode resolvedNodes[8];
    OverworldWildRuntimeStaticModifierContribution staticModifiers[8];
} OverworldWildRuntimeStaticCache;

typedef struct OverworldWildRuntimeModifierOperation {
    signed short operand;
    u8 fieldNamespace;
    u8 fieldId;
    u8 operatorKind;
    u8 bound;
} OverworldWildRuntimeModifierOperation;

_Static_assert(sizeof(OverworldWildBehaviorDataBlobHeader) == 216,
    "v40 header ABI");
_Static_assert(sizeof(OverworldWildOverrideDefinitionRecord) == 36,
    "v40 definition ABI");
_Static_assert(sizeof(OverworldWildApplicabilityRecord) == 16,
    "v40 applicability ABI");
_Static_assert(sizeof(OverworldWildTiredTranslationRecord) == 24,
    "v40 tired translation ABI");
_Static_assert(sizeof(OverworldWildRuntimeDefinition) == 24,
    "runtime copy-out ABI");
_Static_assert(sizeof(OverworldWildRuntimeStaticModifierContribution) == 18
        && offsetof(OverworldWildRuntimeStaticModifierContribution,
            targetNodeId) == 2,
    "runtime static-contribution ABI");
_Static_assert(sizeof(OverworldWildRuntimeResolvedNode) == 38,
    "runtime resolved-node ABI");
_Static_assert(sizeof(OverworldWildRuntimeStaticComposition) == 536,
    "runtime static-composition ABI");
_Static_assert(sizeof(OverworldWildRuntimeStaticCache) == 540,
    "runtime static-cache ABI");

/* Compile the exact shared Task-5 resident scalar table/helpers into this host
 * accessor fixture; the production copy imports these same overlay-155
 * symbols. */
#define OWBD_CLASS_PROFILE_COUNT 4
#define OWBD_CLASS_RULE_COUNT 2
#define OWBD_SPECIES_CLASS_RULE_COUNT 113
#define OWBD_OVERRIDE_MEMBER_COUNT 155
#define OWBD_STATE_BODY_COUNT 58
#define OWBD_PROFILE_IDENTITY_COUNT 58
#define OWBD_CONTROLLER_COUNT 3
#define OWBD_CONTROLLER_NODE_COUNT 21
#define OWBD_TRANSITION_COUNT 26
#define OWBD_SPAWN_POLICY_COUNT 3
#define OWBD_POPULATION_POLICY_COUNT 6
#define OWBD_HOOK_SET_COUNT 3
#define OWBD_OVERRIDE_DEFINITION_COUNT 19
#define OWBD_OVERRIDE_SOURCE_COUNT 11
#define OWBD_OVERRIDE_ACTION_COUNT 207
#define OWBD_OWNER_COUNT 10
#define OWBD_RECOVERY_ACTION_COUNT 15
#define OWBD_TRANSITION_GUARD_COUNT 26
#define OWBD_TRANSITION_OPERATION_COUNT 35
#define OWBD_TRANSITION_ACTION_COUNT 32
#define OWBD_IMPORT_RECIPE_COUNT 12
#define OWBD_APPLICABILITY_COUNT 19
#define OWBD_TIRED_TRANSLATION_COUNT 18
#define OWBD_SEMANTIC_ID_COUNT 16
#define OWBD_ROLE_TIRED 3
#define OWBD_OPERATOR_SET 1
#define OWBD_OPERATOR_ADD 2
#define OWBD_OPERATOR_ADD_AT_LEAST 5
#define OWBD_SELECTOR_EXACT 1
#define OWBD_SELECTOR_SEMANTIC_ROLE 2
#define OWBD_DEFINITION_STATE_CANDIDATE 1
#define OWBD_DEFINITION_MODIFIER 2
#define OWBD_NODE_FLAG_OPTIONAL 2
#define OWBD_NODE_FLAG_HIDDEN 4
#define OWBD_CANDIDATE_TIMER_SET 1
#define OWBD_CANDIDATE_TIMER_ADD 2
#define OWBD_CANDIDATE_TIMER_ADD_MIN -32
#define OWBD_CANDIDATE_TIMER_ADD_MAX 32
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE 0x1600u
#define OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE 11220u
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC 0x4F574244u
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 40
#define OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM 0x6E9B5D94u
#define OVERWORLD_WILD_BEHAVIOR_DATA_SCHEMA_FINGERPRINT 0xC88892BEu
#define OWBD_BLOB_FLAG_NAMES_ARE_HASHES (1u << 1)
#define OWBD_BLOB_FLAG_AUTHORED_SOURCE (1u << 2)
#define OWBD_VALIDATION_NO_PROJECTION_BUILDER
#include "overworld_wild_behavior_v40_validation_shared.h"

#define OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
#include "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"

static int sChecks;

static void require(BOOL condition, const char *message)
{
    sChecks++;
    if (!condition) {
        fprintf(stderr, "runtime catalog fixture failed: %s\n", message);
        exit(1);
    }
}

static const OverworldWildApplicabilityRecord *find_application(
    const u8 *blob,
    const OverworldWildBehaviorDataBlobHeader *header,
    u16 stableId)
{
    const OverworldWildApplicabilityRecord *records =
        (const void *)(blob + header->applicability.offset);
    u16 index;
    for (index = 0; index < header->applicability.count; index++)
        if (records[index].stableId == stableId) return &records[index];
    return NULL;
}

int main(int argc, char **argv)
{
    OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildOverrideDefinitionRecord *definitions;
    const OverworldWildTiredTranslationRecord *translations;
    OverworldWildRuntimeDefinition actual;
    FILE *file;
    u8 *blob;
    long size;
    u16 index;
    BOOL sawAuthored = FALSE, sawFallback = FALSE;

    require(argc == 2, "expected one validated-v40 path");
    file = fopen(argv[1], "rb");
    require(file != NULL, "validated-v40 file did not open");
    require(fseek(file, 0, SEEK_END) == 0, "validated-v40 seek failed");
    size = ftell(file);
    require(size == 11220, "validated-v40 size changed");
    require(fseek(file, 0, SEEK_SET) == 0, "validated-v40 rewind failed");
    blob = malloc((size_t)size);
    require(blob != NULL, "fixture allocation failed");
    require(fread(blob, 1, (size_t)size, file) == (size_t)size,
        "validated-v40 read failed");
    require(fclose(file) == 0, "validated-v40 close failed");

    header = (void *)blob;
    require(header->version == 40 && header->headerSize == sizeof(*header),
        "validated-v40 header identity changed");
    require(header->blobSize == (u32)size,
        "validated-v40 header size disagrees with file");
    require(header->overrideDefinitions.entrySize == sizeof(*definitions),
        "definition record size changed");
    require(header->applicability.entrySize
            == sizeof(OverworldWildApplicabilityRecord),
        "applicability record size changed");
    require(header->tiredTranslations.entrySize == sizeof(*translations),
        "translation record size changed");
    sOverworldWildValidatedV40 = blob;

    {
        static const u8 expected1202[28] = {
            3, 1, 9, 2, 32, 2, 0, 15, 1, 1, 2, 40, 4, 0,
            9, 30, 3, 4, 0, 0, 2, 1, 1, 0, 0, 0, 0, 15,
        };
        static const u8 expected1209[28] = {
            11, 0, 0, 2, 32, 2, 0, 15, 1, 1, 2, 40, 4, 0,
            9, 30, 3, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15,
        };
        const OverworldWildStateBodyRecord *bodies =
            (const void *)(blob + header->stateBodies.offset);
        BOOL saw1202 = FALSE, saw1209 = FALSE;
        for (index = 0; index < header->stateBodies.count; index++) {
            if (bodies[index].stableId == 0x1202) {
                saw1202 = memcmp(bodies[index].values, expected1202, 28) == 0;
            } else if (bodies[index].stableId == 0x1209) {
                saw1209 = memcmp(bodies[index].values, expected1209, 28) == 0;
            }
        }
        require(saw1202 && saw1209,
            "production bodies 0x1202/0x1209 changed or were not copied whole");
    }

    definitions = (const void *)(blob + header->overrideDefinitions.offset);
    for (index = 0; index < header->overrideDefinitions.count; index++) {
        const OverworldWildOverrideDefinitionRecord *definition =
            &definitions[index];
        const OverworldWildApplicabilityRecord *application =
            find_application(blob, header, definition->applicabilityId);
        u8 expectedFlags = OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE;
        require(application != NULL, "definition application missing");
        require(OverworldWildRuntime_CopyInstalledDefinition(
                definition->stableId, &actual),
            "production definition copy-out rejected a v40 definition");
        if (definition->hasTiredOriginKind)
            expectedFlags |= OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN;
        if (definition->hasRequiredOwnerId)
            expectedFlags |= OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER;
        if (definition->allowMultipleOwners)
            expectedFlags |= OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS;
        if (definition->allowMultipleInstancesPerOwner)
            expectedFlags |= OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES;
        require(actual.stableId == definition->stableId
                && actual.controllerId == (definition->controllerId
                    ? definition->controllerId : application->controllerId)
                && actual.nodeId == definition->nodeId
                && actual.requiredOwnerId == definition->requiredOwnerId
                && actual.effectiveProfileId == application->effectiveProfileId
                && actual.kind == definition->kind
                && actual.selectorKind == definition->selectorKind
                && actual.semanticRole == definition->semanticRole
                && actual.tiredOriginKind == definition->tiredOriginKind
                && actual.flags == expectedFlags
                && actual.mapLifetime == definition->mapLifetime
                && actual.battleLifetime == definition->battleLifetime
                && actual.channel == definition->channel
                && actual.priority == definition->priority
                && actual.immutableContextMask == application->immutableContextMask
                && actual.applicabilitySemanticRole == application->semanticRole,
            "production definition copy-out changed v40 identity");
    }
    memset(&actual, 0xA5, sizeof(actual));
    require(!OverworldWildRuntime_CopyInstalledDefinition(0, &actual),
        "production definition copy-out accepted zero ID");
    {
        u8 zero[sizeof(actual)] = {0};
        require(memcmp(&actual, zero, sizeof(actual)) == 0,
            "missing definition did not zero copy-out");
    }

    translations = (const void *)(blob + header->tiredTranslations.offset);
    for (index = 0; index < header->tiredTranslations.count; index++) {
        u16 candidate = 0;
        u8 count = OverworldWildRuntime_CountInstalledTiredTranslations(
            translations[index].tiredOriginKind,
            translations[index].destinationControllerId,
            translations[index].authoredTiredBound != 0,
            &candidate);
        require(count == 1,
            "production translation copy-out did not select exactly one row");
        require(candidate == translations[index].candidateDefinitionId,
            "production translation copy-out returned the wrong candidate");
        if (translations[index].authoredTiredBound) sawAuthored = TRUE;
        else sawFallback = TRUE;
    }
    require(sawAuthored && sawFallback,
        "validated-v40 lacks authored/fallback translation coverage");
    {
        static const u8 expectedMankeyState[28] = {
            3, 2, 2, 1, 32, 2, 2, 15, 1, 1, 5, 20, 6, 0,
            9, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15,
        };
        static const u8 expectedMankeyController[9] = {
            2, 2, 20, 4, 4, 100, 60, 10, 0,
        };
        OverworldWildRuntimeStaticContext staticContext;
        OverworldWildRuntimeApplicabilityInput input;
        OverworldWildRuntimeStaticComposition first;
        OverworldWildRuntimeStaticComposition second;
        OverworldWildRuntimeStaticCache resolvedCache;
        OverworldWildRuntimeStaticCache retainedResolved;
        OverworldWildRuntimeStaticCache modifiedCache;
        OverworldWildRuntimeStaticContext wrongContext;
        OverworldWildRuntimeResolvedNode node;
        OverworldWildRuntimeModifierOperation operation;
        BOOL sawModifiedBase = FALSE;
        u8 operationCount = 0xFF;

        memset(&staticContext, 0, sizeof(staticContext));
        staticContext.species = 56;
        staticContext.groupFlags = 8;
        staticContext.level = 1;
        staticContext.terrain = 0;
        staticContext.behaviorClass = 0;
        memset(&input, 0, sizeof(input));
        input.immutableContextMask = 8;
        input.controllerId = 0x3001;
        for (index = 0; index < 7; index++)
            input.boundNodeIds[index] = (u16)(0x3101 + index);
        input.boundNodeCount = 7;
        input.semanticRoleMask = 0x7F;
        input.effectiveProfileId = 0x2304;
        input.effectiveSemanticRole = 1;
        require(OverworldWildRuntime_CopyInstalledStaticComposition(
                &staticContext, &input, &first)
                && first.controllerId == input.controllerId
                && first.baseProfileId == input.effectiveProfileId
                && first.baseNodeId == 0x3101
                && first.populationPolicyId == 0x4105
                && !memcmp(first.stateValues, expectedMankeyState,
                    sizeof(expectedMankeyState))
                && !memcmp(first.controllerValues, expectedMankeyController,
                    sizeof(expectedMankeyController))
                && first.staticModifierCount == 8 && first.reserved == 1
                && first.catalogIdentity != 0
                && first.staticContextIdentity != 0
                && first.staticSetHash != 0,
            "production resolved Mankey static snapshot differs");
        input.effectiveProfileId = 0x2201;
        require(!OverworldWildRuntime_CopyInstalledStaticComposition(
                &staticContext, &input, &second),
            "raw authored profile authenticated after matching base rebind");
        input.effectiveProfileId = 0x2304;
        input.controllerId = 0x3002;
        require(!OverworldWildRuntime_CopyInstalledStaticComposition(
                &staticContext, &input, &second),
            "caller-selected controller replaced resolved assignment");
        input.controllerId = 0x3001;
        first.stateValues[0] ^= 0xFF;
        require(OverworldWildRuntime_CopyInstalledStaticComposition(
                &staticContext, &input, &second)
                && first.stateValues[0] != second.stateValues[0],
            "static composition accessor retained caller storage");
        require(OverworldWildRuntime_CopyInstalledStaticCache(
                &staticContext, &input, 7, &resolvedCache)
                && OverworldWildRuntime_ValidateStaticCache(
                    &resolvedCache, 7) == OW_WILD_RUNTIME_STATUS_OK
                && OverworldWildRuntime_ApplicabilityMatchesStaticCache(
                    &input, &resolvedCache),
            "authenticated complete static-cache projection differs from resolver");
        memset(&retainedResolved, 0xA5, sizeof(retainedResolved));
        require(OverworldWildRuntime_ResolveRetainedStaticCache(
                &resolvedCache, &staticContext, 7, &retainedResolved)
                == OW_WILD_RUNTIME_STATUS_OK
                && !memcmp(&retainedResolved, &resolvedCache,
                    sizeof(resolvedCache)),
            "production retained resolver changed an independent valid copy");
        require(OverworldWildRuntime_ResolveRetainedStaticCache(
                &resolvedCache, &staticContext, 7, &resolvedCache)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
            "production retained resolver accepted exact input/output aliasing");
        wrongContext = staticContext;
        wrongContext.species++;
        require(OverworldWildRuntime_ResolveRetainedStaticCache(
                &resolvedCache, &wrongContext, 7, &retainedResolved)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
            "production retained resolver accepted a mismatched static context");
        require(OverworldWildRuntime_ResolveRetainedStaticCache(
                &resolvedCache, &staticContext, 8, &retainedResolved)
                == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
            "production retained resolver accepted a mismatched generation");
        modifiedCache = resolvedCache;
        modifiedCache.stateValues[3] =
            modifiedCache.stateValues[3] == 4 ? 3 : 4;
        for (index = 0; index < modifiedCache.nodeCount; index++) {
            if (modifiedCache.resolvedNodes[index].nodeId
                    != modifiedCache.baseNodeId)
                continue;
            modifiedCache.resolvedNodes[index].stateValues[3] =
                modifiedCache.stateValues[3];
            sawModifiedBase = TRUE;
            break;
        }
        modifiedCache.staticSetHash = RuntimeCatalogMix(
            0x4F575339u, modifiedCache.catalogIdentity);
        modifiedCache.staticSetHash = RuntimeCatalogMix(
            modifiedCache.staticSetHash, modifiedCache.staticContextIdentity);
        modifiedCache.staticSetHash = RuntimeCatalogHashBytes(
            modifiedCache.staticSetHash, &modifiedCache.immutableContextMask,
            sizeof(modifiedCache) - offsetof(
                OverworldWildRuntimeStaticCache, immutableContextMask));
        require(sawModifiedBase
                && OverworldWildRuntime_ValidateStaticCache(
                    &modifiedCache, 7) == OW_WILD_RUNTIME_STATUS_OK
                && OverworldWildRuntime_ResolveRetainedStaticCache(
                    &modifiedCache, &staticContext, 7, &retainedResolved)
                    == OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
            "production retained resolver accepted coherent bytes that differ "
            "from installed-catalog re-resolution");
        require(OverworldWildRuntime_CopyInstalledDefinition(
                definitions[0].stableId, &actual),
            "candidate definition recopy failed");
        require(OverworldWildRuntime_CopyInstalledResolvedNode(
                &second, &actual, &node)
                && node.nodeId != 0 && node.profileId != 0,
            "production candidate node/profile copy-out failed");
        require(OverworldWildRuntime_CopyInstalledModifierOperations(
                actual.stableId, &operation, 1, &operationCount)
                && operationCount == 0,
            "state-only v40 catalog exposed invented modifier payloads");

        /* Species 92 is a production member of source 0.  Its controller's
         * calm node is rebound while the base remains authored, and shipped
         * role-scoped scalar actions fold into the rebound copied body. */
        {
            OverworldWildRuntimeStaticContext ratContext;
            OverworldWildRuntimeApplicabilityInput ratInput;
            OverworldWildRuntimeStaticComposition ratComposition;
            OverworldWildRuntimeStaticComposition unboundComposition;
            OverworldWildStaticActionRecord *actions =
                (void *)(blob + header->overrideActions.offset);
            OverworldWildStaticActionRecord savedAction;
            OverworldWildRuntimeResolvedNode *calm = NULL;
            u8 rawProfile[28];
            u16 actionIndex;

            memset(&ratContext, 0, sizeof(ratContext));
            ratContext.species = 92;
            ratContext.level = 1;
            memset(&ratInput, 0, sizeof(ratInput));
            ratInput.controllerId = 0x3001;
            for (index = 0; index < 7; index++)
                ratInput.boundNodeIds[index] = (u16)(0x3101 + index);
            ratInput.boundNodeCount = 7;
            ratInput.semanticRoleMask = 0x7F;
            ratInput.effectiveProfileId = 0x2201;
            ratInput.effectiveSemanticRole = 1;
            require(OverworldWildRuntime_CopyInstalledStaticComposition(
                    &ratContext, &ratInput, &ratComposition),
                "production non-base rebind snapshot did not resolve");
            calm = FindResolvedNode(&ratComposition, 0x3102);
            require(calm != NULL && calm->bound
                    && calm->profileId == 0x2301
                    && CopyProfileValues(header, 0x2301, rawProfile)
                    && memcmp(calm->stateValues, rawProfile,
                        sizeof(rawProfile)) != 0,
                "production non-base rebind/role scalar was not fully folded");
            input = ratInput;
            input.boundNodeIds[1] = 0x3200;
            require(!OverworldWildRuntime_CopyInstalledStaticComposition(
                    &ratContext, &input, &unboundComposition),
                "caller node roster replaced the canonical resolved roster");
            input = ratInput;
            input.semanticRoleMask &= (u8)~1u;
            require(!OverworldWildRuntime_CopyInstalledStaticComposition(
                    &ratContext, &input, &unboundComposition),
                "caller semantic-role roster replaced the canonical roster");
            input = ratInput;
            input.effectiveSemanticRole = 2;
            require(!OverworldWildRuntime_CopyInstalledStaticComposition(
                    &ratContext, &input, &unboundComposition),
                "caller base semantic role replaced the canonical base role");

            for (actionIndex = 0;
                    actionIndex < header->overrideActions.count;
                    actionIndex++)
                if (actions[actionIndex].kind == OWBD_STATIC_ACTION_BIND_NODE
                    && actions[actionIndex].payload.bindNode.controllerId
                        == 0x3001
                    && actions[actionIndex].payload.bindNode.nodeId == 0x3102)
                    break;
            require(actionIndex < header->overrideActions.count,
                "production non-base binding action disappeared");
            savedAction = actions[actionIndex];
            actions[actionIndex].kind = OWBD_STATIC_ACTION_UNBIND_NODE;
            actions[actionIndex].payload.bindNode.profileIdentityId = 0;
            ratInput.boundNodeCount = 6;
            for (index = 1; index < 6; index++)
                ratInput.boundNodeIds[index] = (u16)(0x3102 + index);
            ratInput.boundNodeIds[6] = 0;
            ratInput.semanticRoleMask = 0x7D;
            require(OverworldWildRuntime_CopyInstalledStaticComposition(
                    &ratContext, &ratInput, &unboundComposition)
                    && unboundComposition.boundNodeCount == 6
                    && unboundComposition.semanticRoleMask == 0x7D
                    && (calm = FindResolvedNode(
                            &unboundComposition, 0x3102)) != NULL
                    && !calm->bound && calm->profileId == 0
                    && !memcmp(calm->stateValues, (u8[28]){0}, 28),
                "production-backed non-base UNBIND retained an operational node");
            actions[actionIndex] = savedAction;
        }
    }
    {
        u16 candidate = 0xFFFF;
        require(OverworldWildRuntime_CountInstalledTiredTranslations(
                0xFF, 0xFFFF, FALSE, &candidate) == 0
                && candidate == 0,
            "missing production translation was not canonical");
    }
    printf("runtime catalog host fixture: %d checks; definitions=%u translations=%u\n",
        sChecks, header->overrideDefinitions.count,
        header->tiredTranslations.count);
    sOverworldWildValidatedV40 = NULL;
    free(blob);
    return 0;
}

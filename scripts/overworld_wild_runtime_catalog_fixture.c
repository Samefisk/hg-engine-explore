#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0

#define OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE (1u << 0)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN (1u << 1)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER (1u << 2)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS (1u << 3)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES (1u << 4)

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
    u8 reserved[2];
} OverworldWildRuntimeDefinition;

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

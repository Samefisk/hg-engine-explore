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
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OWBD_ROLE_CALM 1
#define OWBD_ROLE_ATTENTIVE 2
#define OWBD_ROLE_TIRED 3
#define OWBD_ROLE_FOLLOWER 6
#define OWBD_ROLE_CUSTOM 7
#define OWBD_ROLE_MASK(role) (1u << ((role) - 1))

#define OW_WILD_RUNTIME_SIDECAR_CODE __attribute__((noinline))
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
    OverworldWildRuntimeDefinition definitions[32];
} FixtureDefinitionCatalog;

static FixtureDefinitionCatalog sFixtureCatalog;

enum {
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
};

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
    return definition;
}

static FixtureDefinitionCatalog fixture_catalog(void)
{
    FixtureDefinitionCatalog catalog;
    u8 eligible = OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE;

    memset(&catalog, 0, sizeof(catalog));
    catalog.schemaFingerprint = 0xC88892BEu;
    catalog.definitionCount = 12;
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
    catalog.definitions[11] = make_definition(
        DEF_CUSTOM, 1, 2, 7, 0, 0, eligible);
    return catalog;
}

BOOL OverworldWildRuntime_CopyInstalledDefinition(
    u16 definitionId,
    OverworldWildRuntimeDefinition *definitionOut)
{
    u16 index;
    for (index = 0; index < sFixtureCatalog.definitionCount; index++) {
        if (sFixtureCatalog.definitions[index].stableId == definitionId) {
            *definitionOut = sFixtureCatalog.definitions[index];
            return TRUE;
        }
    }
    memset(definitionOut, 0, sizeof(*definitionOut));
    return FALSE;
}

#define OW_WILD_RUNTIME_HOST_TEST
u8 OverworldWildRuntime_CountInstalledTiredTranslations(
    u8 tiredOriginKind,
    u16 destinationControllerId,
    BOOL authoredTiredBound,
    u16 *candidateDefinitionIdOut)
{
    *candidateDefinitionIdOut = 0;
    if (tiredOriginKind != 1 || destinationControllerId != 0x3001)
        return 0;
    *candidateDefinitionIdOut = authoredTiredBound
        ? DEF_FLED : DEF_FLED_EXACT;
    return 1;
}

#include "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c"

static OverworldWildRuntimeApplicabilityInput fixture_applicability(void)
{
    OverworldWildRuntimeApplicabilityInput input;

    memset(&input, 0, sizeof(input));
    input.immutableContextMask = 0xFFFFFFFFu;
    input.controllerId = 0x3001;
    input.boundNodeIds[0] = 0x4001;
    input.boundNodeCount = 1;
    input.semanticRoleMask = OWBD_ROLE_MASK(OWBD_ROLE_ATTENTIVE)
        | OWBD_ROLE_MASK(OWBD_ROLE_TIRED);
    input.effectiveProfileId = 0x2201;
    input.effectiveSemanticRole = 2;
    return input;
}

static void prepare_runtime(
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
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
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
            == OW_WILD_RUNTIME_STATUS_OK,
        "fallback tired-translation branch replace failed");
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
    require(
        OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &fled, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "pre-rekey handle remained usable");
}

static void test_role_mask_boundaries(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    OverworldWildBehaviorStackRuntime runtime;
    OverworldWildBehaviorStackRuntime before;
    OverworldWildRuntimeApplicabilityInput boundary = *input;
    OverworldWildRuntimeStackDeltaResult result;

    prepare_runtime(&runtime, 0);
    boundary.semanticRoleMask = OWBD_ROLE_MASK(OWBD_ROLE_CALM);
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &boundary,
            DEF_CALM, 0x9301, 0, &result) == OW_WILD_RUNTIME_STATUS_OK,
        "role 1 did not map to semantic-mask bit 0");
    require(OverworldWildRuntime_ClearAllForSlot(
            &runtime, 0, runtime.slots[0].slotGeneration, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "role boundary cleanup failed");
    boundary.semanticRoleMask = OWBD_ROLE_MASK(OWBD_ROLE_CUSTOM);
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
    require(runtime.slots[0].effectiveGeneration == effectiveGeneration,
        "Task-8 batch changed deferred effective generation");
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

    prepare_runtime(&runtime, 0);
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
    targetHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9001, 0);
    otherHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9002, 0);
    otherLayerGeneration = runtime.slots[1].layerGeneration;
    runtime.slots[0].nextEntryGeneration = 0xFFFFFFFFu;
    require(
        OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration,
            input, DEF_MULTI_INSTANCE, 0x9010, 1, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "global rekey trigger failed");
    require(runtime.slots[1].layerGeneration == otherLayerGeneration + 1,
        "global rekey did not advance surviving other slot once");
    require(runtime.slots[1].layerBank.entryGenerations[0] == 1,
        "global rekey did not assign canonical nonzero other identity");
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
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
    targetHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9101, 0);
    survivorHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9102, 0);
    survivorLayerGeneration = runtime.slots[1].layerGeneration;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
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
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
    (void)apply_one(&runtime, 0, input, DEF_SHARED, 0x9151, 0);
    survivorHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9152, 0);
    runtime.handleEpoch = 0xFFFFFFFEu;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == 0xFFFFFFFFu
            && runtime.slots[1].activeLayerCount == 1,
        "Task-7 max-minus-one epoch wrap restarted one epoch too early");

    prepare_runtime(&runtime, 0);
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
    targetHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9201, 0);
    survivorHandle = apply_one(&runtime, 1, input, DEF_SHARED, 0x9202, 0);
    runtime.handleEpoch = 0xFFFFFFFFu;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.handleEpoch == 1
            && runtime.slots[0].activeLayerCount == 0
            && runtime.slots[1].activeLayerCount == 0,
        "Task-7 terminal epoch restart did not clear every slot");
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
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
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
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
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
    (void)apply_one(&runtime, 1, input, DEF_SHARED, 0x9501, 0);
    runtime.slots[1].layerBank.entryGenerations[0] = 0;
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[1].activeLayerCount == 0,
        "zero survivor entry generation was normalized during slot wrap");

    prepare_runtime(&runtime, 0);
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
    (void)apply_one(&runtime, 1, input, DEF_MULTI_INSTANCE, 0x9502, 0);
    (void)apply_one(&runtime, 1, input, DEF_MULTI_INSTANCE, 0x9502, 1);
    runtime.slots[1].layerBank.entryGenerations[1] =
        runtime.slots[1].layerBank.entryGenerations[0];
    runtime.slots[0].slotGeneration = 0xFFFFFFFFu;
    OverworldWildRuntime_DestructivelyInvalidateSlot(&runtime, 0, TRUE);
    require(runtime.slots[1].activeLayerCount == 0,
        "duplicate survivor entry generation was normalized during slot wrap");

    prepare_runtime(&runtime, 0);
    OverworldWildRuntime_MarkSlotAssigned(&runtime, 1);
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
            == OW_WILD_RUNTIME_STATUS_OK,
        "dormant modifier was rejected by the current effective profile");
    changed = *input;
    changed.effectiveSemanticRole++;
    require(OverworldWildRuntime_Apply(
            &runtime, 0, runtime.slots[0].slotGeneration, &changed,
            DEF_MULTI_INSTANCE, 0x9001, 2, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "dormant modifier was rejected by the current effective role");
    require(runtime.slots[0].activeLayerCount == 2,
        "dormant modifiers were not stored independently of the winner");
    require(OverworldWildRuntime_ClearAllForSlot(
            &runtime, 0, runtime.slots[0].slotGeneration, &result)
            == OW_WILD_RUNTIME_STATUS_OK,
        "dormant modifier cleanup failed");

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
    u32 firstIdentity;

    prepare_runtime(&runtime, 0);
    OverworldWildRuntime_MarkResidentCold(&runtime);
    sOverworldWildRuntimeForceZeroMix = TRUE;
    require(OverworldWildRuntime_BindPrivateIdentity(&runtime)
            == OW_WILD_RUNTIME_STATUS_OK,
        "first consecutive forced-zero private identity bind failed");
    firstIdentity = sOverworldWildRuntimeLayerService.privateRuntimeIdentity;
    betweenHandle = apply_one(&runtime, 0, input, DEF_SHARED, 0x9401, 0);
    OverworldWildRuntime_MarkResidentCold(&runtime);
    require(OverworldWildRuntime_BindPrivateIdentity(&runtime)
            == OW_WILD_RUNTIME_STATUS_OK,
        "second consecutive forced-zero private identity bind failed");
    require(sOverworldWildRuntimeLayerService.privateRuntimeIdentity != 0,
        "forced-zero Mix published a zero private identity");
    require(sOverworldWildRuntimeLayerService.privateRuntimeIdentity
            != firstIdentity,
        "consecutive forced-zero binds reused private identity");
    require(OverworldWildRuntime_Remove(
            &runtime, 0, runtime.slots[0].slotGeneration,
            &betweenHandle, &result) == OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
        "handle minted between forced-zero binds remained authenticated");
    sOverworldWildRuntimeForceZeroMix = FALSE;
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

int main(void)
{
    OverworldWildRuntimeApplicabilityInput input = fixture_applicability();
    OverworldWildRuntimeDefinition copied;

    sFixtureCatalog = fixture_catalog();
    require(
        OverworldWildRuntime_CopyInstalledDefinition(DEF_SHARED, &copied)
            && copied.stableId == DEF_SHARED,
        "validated definition copy-out failed");
    test_apply_replace_remove(&input);
    test_handles_and_atomicity(&input);
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

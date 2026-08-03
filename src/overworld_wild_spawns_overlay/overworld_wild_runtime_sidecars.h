#ifndef OVERWORLD_WILD_RUNTIME_SIDECARS_H
#define OVERWORLD_WILD_RUNTIME_SIDECARS_H

#include "../../include/overworld_wild_spawns_internal.h"

#define OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT 8
#define OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS 16
#define OW_WILD_RUNTIME_MAX_CATALOG_DEFINITIONS 32
#define OW_WILD_RUNTIME_MAX_BOUND_NODES 8
#define OW_WILD_RUNTIME_MAX_RESOLVED_NODES 8
#define OW_WILD_RUNTIME_STATE_VALUE_COUNT 28
#define OW_WILD_RUNTIME_CONTROLLER_VALUE_COUNT 9
#define OW_WILD_RUNTIME_PRIMITIVE_VALUE_COUNT 5
#define OW_WILD_RUNTIME_MAX_PROVENANCE_CANDIDATES 9
#define OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS 8
#define OW_WILD_RUNTIME_MAX_PROVENANCE_CONTRIBUTIONS 16
#define OW_WILD_RUNTIME_MAX_PROVENANCE_NORMALIZATIONS 8
#define OW_WILD_RUNTIME_PROVENANCE_FIELD_COUNT 36

#define OW_WILD_RUNTIME_CACHE_VALID (1u << 0)
#define OW_WILD_RUNTIME_PROVENANCE_VALID (1u << 0)
#define OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_CANDIDATES (1u << 1)
#define OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_MODIFIERS (1u << 2)
#define OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_CONTRIBUTIONS (1u << 3)
#define OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_NORMALIZATIONS (1u << 4)

#define OW_WILD_RUNTIME_CAP_CAN_MOVE (1u << 0)
#define OW_WILD_RUNTIME_CAP_BATTLE_ON_CONTACT (1u << 1)
#define OW_WILD_RUNTIME_CAP_HOP (1u << 2)
#define OW_WILD_RUNTIME_CAP_TELEPORT (1u << 3)
#define OW_WILD_RUNTIME_CAP_RAM (1u << 4)
#define OW_WILD_RUNTIME_CAP_JUMP_LEDGES (1u << 5)
#define OW_WILD_RUNTIME_CAP_FRAME_WORK (1u << 6)

#define OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE (1u << 0)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN (1u << 1)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER (1u << 2)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS (1u << 3)
#define OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES (1u << 4)

#define OW_WILD_RUNTIME_GENERATED_FLAG_HAS_TIRED_ORIGIN (1u << 0)
#define OW_WILD_RUNTIME_GENERATED_FLAG_HAS_REQUIRED_OWNER (1u << 1)

#define OW_WILD_RUNTIME_TIMER_VALID (1u << 0)
#define OW_WILD_RUNTIME_TIMER_ZERO_PENDING (1u << 1)

#define OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID (1u << 0)

#define OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_ACTIVE_STEPS (1u << 0)
#define OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER (1u << 1)
#define OW_WILD_RUNTIME_RECOVERY_ACTION_CLEAR_MOVEMENT_CHAIN (1u << 2)
#define OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN (1u << 3)

#define OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY (1u << 0)
#define OW_WILD_RUNTIME_TRANSITION_ACTION(kind) (1u << ((kind) - 1))

#define OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS 3

typedef enum OverworldWildRuntimeTimerClock {
    OW_WILD_RUNTIME_TIMER_CLOCK_NONE = 0,
    OW_WILD_RUNTIME_TIMER_CLOCK_FRAME = 1,
    OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT = 2,
} OverworldWildRuntimeTimerClock;

typedef enum OverworldWildRuntimeHiddenTimerPolicy {
    OW_WILD_RUNTIME_HIDDEN_TIMER_NONE = 0,
    OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN = 1,
    OW_WILD_RUNTIME_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN = 2,
    OW_WILD_RUNTIME_HIDDEN_TIMER_EXPIRE_ON_HIDE = 3,
} OverworldWildRuntimeHiddenTimerPolicy;

typedef enum OverworldWildRuntimeRecoveryOrigin {
    OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA = 1,
    OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH = 2,
    OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY = 3,
    OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED = 4,
} OverworldWildRuntimeRecoveryOrigin;

typedef enum OverworldWildRuntimeRecoverySelection {
    OW_WILD_RUNTIME_RECOVERY_SELECTION_NONE = 0,
    OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC = 1,
    OW_WILD_RUNTIME_RECOVERY_SELECTION_GENERATED_EXACT = 2,
} OverworldWildRuntimeRecoverySelection;

typedef enum OverworldWildRuntimeTimerRecoveryRoute {
    OW_WILD_RUNTIME_TIMER_RECOVERY_NONE = 0,
    OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF = 1,
    OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM = 2,
} OverworldWildRuntimeTimerRecoveryRoute;

typedef enum OverworldWildRuntimeCommandWinnerKind {
    OW_WILD_RUNTIME_COMMAND_WINNER_BASE = 1,
    OW_WILD_RUNTIME_COMMAND_WINNER_LAYER = 2,
} OverworldWildRuntimeCommandWinnerKind;

typedef enum OverworldWildRuntimeStatus {
    OW_WILD_RUNTIME_STATUS_OK = 0,
    OW_WILD_RUNTIME_STATUS_IDEMPOTENT = 1,
    OW_WILD_RUNTIME_STATUS_STALE_NOOP = 2,
    OW_WILD_RUNTIME_STATUS_STALE_HANDLE = 3,
    OW_WILD_RUNTIME_STATUS_INVALID_HANDLE = 4,
    OW_WILD_RUNTIME_STATUS_WRONG_SLOT = 5,
    OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH = 6,
    OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION = 7,
    OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER = 8,
    OW_WILD_RUNTIME_STATUS_OWNER_NOT_AUTHORIZED = 9,
    OW_WILD_RUNTIME_STATUS_GENERATED_WRAPPER_FAMILY_MISMATCH = 10,
    OW_WILD_RUNTIME_STATUS_OWNER_KEY_OCCUPIED = 11,
    OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED = 12,
    OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED = 13,
    OW_WILD_RUNTIME_STATUS_NOT_FOUND = 14,
    OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE = 15,
    OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR = 16,
    OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA = 17,
    OW_WILD_RUNTIME_STATUS_CAPACITY_EXCEEDED = 18,
    OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER = 19,
    OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION = 20,
    OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA = 21,
    OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION = 22,
    OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT = 23,
    OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED = 24,
    OW_WILD_RUNTIME_STATUS_DATA_BUSY = 25,
} OverworldWildRuntimeStatus;

typedef enum OverworldWildRuntimeDeltaOperationKind {
    OW_WILD_RUNTIME_DELTA_APPLY = 1,
    OW_WILD_RUNTIME_DELTA_REPLACE = 2,
    OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED = 3,
    OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT = 4,
    OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT = 5,
    OW_WILD_RUNTIME_DELTA_REMOVE_POLICY = 6,
    OW_WILD_RUNTIME_DELTA_CLEAR = 7,
} OverworldWildRuntimeDeltaOperationKind;

typedef struct OverworldWildRuntimeLayerHandle {
    u32 runtimeEpoch;
    u32 slotGeneration;
    u32 entryGeneration;
    u32 validityTag;
    u16 ownerId;
    u16 instanceKey;
    u8 slotIndex;
    u8 reserved[3];
} OverworldWildRuntimeLayerHandle;

typedef union OverworldWildRuntimeDeltaOperationPayload {
    struct {
        u16 definitionId;
        u16 ownerId;
        u16 instanceKey;
        u8 reserved[18];
    } apply;
    OverworldWildRuntimeLayerHandle handle;
    struct {
        u16 ownerId;
        u8 reserved[22];
    } owner;
    struct {
        u8 mapLifetime;
        u8 reserved[23];
    } policy;
    u8 raw[24];
} OverworldWildRuntimeDeltaOperationPayload;

typedef struct OverworldWildRuntimeDeltaOperation {
    u16 operationId;
    u8 kind;
    u8 reserved;
    OverworldWildRuntimeDeltaOperationPayload payload;
} OverworldWildRuntimeDeltaOperation;

typedef struct OverworldWildRuntimeApplicabilityInput {
    u32 immutableContextMask;
    u16 controllerId;
    u16 boundNodeIds[OW_WILD_RUNTIME_MAX_BOUND_NODES];
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u16 effectiveProfileId;
    u8 effectiveSemanticRole;
    u8 reserved;
} OverworldWildRuntimeApplicabilityInput;

/* Full immutable matcher input is deliberately separate from the frozen
 * Task-8 mutation request.  Overlay 157 owns resolution and returns only a
 * copied, authenticated static snapshot to the composer. */
typedef struct OverworldWildRuntimeStaticContext {
    u32 groupFlags;
    u16 species;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 behaviorClass;
    u16 reserved;
} OverworldWildRuntimeStaticContext;

/* Canonical value-copy bridge from immutable spawn inputs to the installed
 * controller/node catalog. Callers never retain catalog pointers or infer a
 * generated definition/owner from serialized order. */
typedef struct OverworldWildRuntimeResolvedStaticContext {
    OverworldWildRuntimeApplicabilityInput applicability;
    u32 catalogIdentity;
    u32 staticContextIdentity;
    u32 staticSetHash;
    u16 controllerId;
    u16 baseNodeId;
    u16 baseProfileId;
    u16 tiredNodeId;
    u16 tiredProfileId;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u8 baseSemanticRole;
    u8 authoredTiredBound;
    u8 stamina;
    u8 restTime;
} OverworldWildRuntimeResolvedStaticContext;

typedef struct OverworldWildRuntimeRecoveryCandidate {
    u16 definitionId;
    u16 ownerId;
    u16 recoveryTransitionId;
    u16 controllerId;
    u16 nodeId;
    u16 profileId;
    u8 origin;
    u8 selection;
    u8 selectorKind;
    u8 semanticRole;
} OverworldWildRuntimeRecoveryCandidate;

typedef struct OverworldWildRuntimeCommandIdentity {
    u32 commandGeneration;
    u32 commandSerial;
    u32 objectGeneration;
    u32 staminaPolicyGeneration;
    u16 staminaPolicyId;
    u8 reserved[2];
} OverworldWildRuntimeCommandIdentity;

/* One caller-owned record per spawn slot. The live-spawns integration places
 * this bank before its fixed resident behaviorStackRuntime suffix. */
typedef struct OverworldWildRuntimeCommandOrigin {
    u32 runtimeEpoch;
    u32 slotGeneration;
    u32 commandGeneration;
    u32 commandSerial;
    u32 winningEntryGeneration;
    u32 effectiveGeneration;
    u32 objectGeneration;
    u32 staminaPolicyGeneration;
    u16 controllerId;
    u16 nodeId;
    u16 stateProfileId;
    u16 winningDefinitionId;
    u16 winningOwnerId;
    u16 winningInstanceKey;
    u16 staminaPolicyId;
    u8 slotIndex;
    u8 winnerKind;
    u8 flags;
    u8 reserved[3];
} OverworldWildRuntimeCommandOrigin;

typedef struct OverworldWildRuntimeCommandOriginBank {
    OverworldWildRuntimeCommandOrigin records[OW_WILD_MAX_SPAWNS];
} OverworldWildRuntimeCommandOriginBank;

typedef struct OverworldWildRuntimeStackDeltaRequest {
    u32 expectedSlotGeneration;
    u8 slotIndex;
    u8 operationCount;
    u16 reserved;
    OverworldWildRuntimeApplicabilityInput applicability;
    OverworldWildRuntimeDeltaOperation
        operations[OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS];
} OverworldWildRuntimeStackDeltaRequest;

typedef struct OverworldWildRuntimeDeltaOperationResult {
    u16 operationId;
    u8 status;
    u8 matched;
    OverworldWildRuntimeLayerHandle handle;
} OverworldWildRuntimeDeltaOperationResult;

typedef struct OverworldWildRuntimeStackDeltaResult {
    u32 runtimeEpochBefore;
    u32 runtimeEpochAfter;
    u32 slotGenerationBefore;
    u32 slotGenerationAfter;
    u32 layerGenerationBefore;
    u32 layerGenerationAfter;
    u32 effectiveGenerationBefore;
    u32 effectiveGenerationAfter;
    u8 status;
    u8 ok;
    u8 mutated;
    u8 operationResultCount;
    OverworldWildRuntimeDeltaOperationResult
        operationResults[OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS];
} OverworldWildRuntimeStackDeltaResult;

typedef enum OverworldWildRuntimeLifetimeState {
    OW_WILD_RUNTIME_LIFETIME_UNINITIALIZED = 0,
    OW_WILD_RUNTIME_LIFETIME_ACTIVE,
    OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD,
} OverworldWildRuntimeLifetimeState;

typedef enum OverworldWildRuntimeSlotLifecycleState {
    OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN = 0,
    OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED,
    OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED,
} OverworldWildRuntimeSlotLifecycleState;

/*
 * Runtime layers contain stable data identity only. They never own a spawn,
 * species, map-object, save-data, or effective-profile pointer.
 */
typedef struct OverworldWildRuntimeLayer {
    u32 entryGeneration;
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    u16 requiredOwnerId;
    u8 hasTiredOriginKind;
    u8 tiredOriginKind;
    u8 hasRequiredOwnerId;
    u8 reserved;
} OverworldWildRuntimeLayer;

typedef struct OverworldWildRuntimeLayerBank {
    u32 entryGenerations[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 definitionIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 ownerIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 instanceKeys[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u16 requiredOwnerIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u8 tiredOriginKinds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    u8 generatedFlags[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
} OverworldWildRuntimeLayerBank;

/* One timer record is stored at the same index as its owning sorted layer.
 * The complete logical key is duplicated deliberately: a timer is valid only
 * when all four owner/instance/entry/timer identity fields authenticate. */
typedef struct OverworldWildRuntimeTimer {
    u32 entryGeneration;
    u32 timerGeneration;
    u16 ownerId;
    u16 instanceKey;
    u16 definitionId;
    u16 recoveryTransitionId;
    u8 remainingTicks;
    u8 armedDuration;
    u8 clock;
    u8 hiddenPolicy;
    u8 recoveryPolicy;
    u8 flags;
    u8 reserved[2];
} OverworldWildRuntimeTimer;

typedef struct OverworldWildRuntimeTimerBank {
    OverworldWildRuntimeTimer timers[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
} OverworldWildRuntimeTimerBank;

typedef struct OverworldWildRuntimeTimerExpiry {
    u32 runtimeEpoch;
    u32 slotGeneration;
    u32 entryGeneration;
    u32 timerGeneration;
    u32 validityTag;
    u16 ownerId;
    u16 instanceKey;
    u16 definitionId;
    u16 recoveryTransitionId;
    u8 slotIndex;
    u8 recoveryPolicy;
    u8 reserved[2];
} OverworldWildRuntimeTimerExpiry;

typedef struct OverworldWildRuntimeTimerTickResult {
    u32 runtimeEpoch;
    u32 slotGeneration;
    u32 layerGenerationBefore;
    u32 layerGenerationAfter;
    u32 effectiveGenerationBefore;
    u32 effectiveGenerationAfter;
    u8 status;
    u8 ok;
    u8 changedTimerCount;
    u8 pendingExpiryCount;
} OverworldWildRuntimeTimerTickResult;

typedef struct OverworldWildRuntimeTimerRecoveryResult {
    u32 runtimeEpochBefore;
    u32 runtimeEpochAfter;
    u32 slotGeneration;
    u32 layerGenerationBefore;
    u32 layerGenerationAfter;
    u32 effectiveGenerationBefore;
    u32 effectiveGenerationAfter;
    u16 recoveryTransitionId;
    u16 calmResetOwnerIds[OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS];
    u8 status;
    u8 ok;
    u8 mutated;
    u8 route;
    u8 actionFlags;
    u8 calmResetOwnerCount;
    u8 slotIndex;
    u8 reserved;
} OverworldWildRuntimeTimerRecoveryResult;

typedef struct OverworldWildRuntimeEffectiveCache {
    u32 cacheIdentity;
    u32 dataIncarnation;
    u32 cacheIncarnation;
    u32 catalogIdentity;
    u32 staticContextIdentity;
    u32 staticSetHash;
    u32 staticContextGeneration;
    u32 effectiveHash;
    u32 provenanceHash;
    u32 layerGeneration;
    u32 effectiveGeneration;
    u32 capabilityMask;
    u16 controllerId;
    u16 nodeId;
    u16 profileId;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u8 semanticRole;
    u8 flags;
    u8 stateValues[OW_WILD_RUNTIME_STATE_VALUE_COUNT];
    u8 controllerValues[OW_WILD_RUNTIME_CONTROLLER_VALUE_COUNT];
    u8 primitives[OW_WILD_RUNTIME_PRIMITIVE_VALUE_COUNT];
} OverworldWildRuntimeEffectiveCache;

/* Runtime inputs only. Ordinary gameplay events leave replayExpiry entirely
 * zero.  Timer replay carries the complete authenticated expiry ticket so a
 * stale event can never target a newly armed timer with recycled catalog IDs. */
typedef struct OverworldWildRuntimeTransitionEvent {
    OverworldWildRuntimeTimerExpiry replayExpiry;
    u8 trigger;
    u8 systemRoute;
    u8 chanceRoll;
    u8 flags;
} OverworldWildRuntimeTransitionEvent;

typedef struct OverworldWildRuntimeTransitionResult {
    OverworldWildRuntimeEffectiveCache effectiveAfter;
    u32 actionFlags;
    u16 transitionId;
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    u8 status;
    u8 ok;
    u8 mutated;
    u8 operationCount;
} OverworldWildRuntimeTransitionResult;

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
    u8 stateValues[OW_WILD_RUNTIME_STATE_VALUE_COUNT];
} OverworldWildRuntimeResolvedNode;

/* Fully resolved spawn-time policy values.  Runtime consumers never retain
 * or parse the installed serialized policy/hook tables. */
typedef struct OverworldWildRuntimeSpawnConfiguration {
    u8 spawnState;
    u8 destination;
    u8 minimumDistance;
    u8 maximumDistance;
    u8 spawnHopTime;
    u8 spawnFlags;
    u8 populationLimit;
    u8 populationFlags;
    u8 helpCallInvocation;
    u8 pickupThrowEntry;
    u8 pickupThrowActiveLoop;
    u8 hookFlags;
} OverworldWildRuntimeSpawnConfiguration;

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
    OverworldWildRuntimeSpawnConfiguration spawnConfiguration;
    u8 baseSemanticRole;
    u8 valid;
    u8 nodeCount;
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u8 staticModifierCount;
    u8 reserved;
    u8 padding[3];
    u8 stateValues[OW_WILD_RUNTIME_STATE_VALUE_COUNT];
    u8 controllerValues[OW_WILD_RUNTIME_CONTROLLER_VALUE_COUNT];
    OverworldWildRuntimeResolvedNode
        resolvedNodes[OW_WILD_RUNTIME_MAX_RESOLVED_NODES];
    OverworldWildRuntimeStaticModifierContribution
        staticModifiers[OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS];
} OverworldWildRuntimeStaticCache;

typedef struct OverworldWildRuntimeCandidateProvenance {
    u32 entryGeneration;
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    u16 nodeId;
    u16 profileId;
    u8 channel;
    u8 priority;
    u8 semanticRole;
    u8 applicable;
    u8 skipReason;
    u8 isWinner;
} OverworldWildRuntimeCandidateProvenance;

typedef struct OverworldWildRuntimeModifierProvenance {
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    u16 staticPriority;
    u16 ruleStableId;
    u16 actionStableId;
    u8 channel;
    u8 priority;
    u8 applied;
    u8 skipReason;
} OverworldWildRuntimeModifierProvenance;

typedef struct OverworldWildRuntimeFieldContribution {
    u16 definitionId;
    u16 ownerId;
    u16 instanceKey;
    signed short operand;
    u8 fieldNamespace;
    u8 fieldId;
    u8 operatorKind;
    u8 bound;
    u8 before;
    u8 after;
} OverworldWildRuntimeFieldContribution;

typedef struct OverworldWildRuntimeNormalizationProvenance {
    u8 fieldNamespace;
    u8 fieldId;
    u8 rule;
    u8 before;
    u8 after;
    u8 reserved[3];
} OverworldWildRuntimeNormalizationProvenance;

typedef struct OverworldWildRuntimeProvenance {
    u32 freshnessGeneration;
    u32 cacheIdentity;
    u32 dataIncarnation;
    u32 cacheIncarnation;
    u32 catalogIdentity;
    u32 staticContextIdentity;
    u32 staticSetHash;
    u32 staticContextGeneration;
    u32 layerGeneration;
    u32 effectiveGeneration;
    u32 effectiveHash;
    u32 provenanceHash;
    u16 winningDefinitionId;
    u16 winningOwnerId;
    u16 winningInstanceKey;
    u8 flags;
    u8 candidateCount;
    u8 modifierCount;
    u8 contributionCount;
    u8 normalizationCount;
    u8 reserved;
    u16 lastWriterDefinitionIds[OW_WILD_RUNTIME_PROVENANCE_FIELD_COUNT];
    OverworldWildRuntimeCandidateProvenance
        candidates[OW_WILD_RUNTIME_MAX_PROVENANCE_CANDIDATES];
    OverworldWildRuntimeModifierProvenance
        modifiers[OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS];
    OverworldWildRuntimeFieldContribution
        contributions[OW_WILD_RUNTIME_MAX_PROVENANCE_CONTRIBUTIONS];
    OverworldWildRuntimeNormalizationProvenance
        normalizations[OW_WILD_RUNTIME_MAX_PROVENANCE_NORMALIZATIONS];
} OverworldWildRuntimeProvenance;

typedef struct OverworldWildRuntimeSlotSidecar {
    u32 slotGeneration;
    u32 staticContextGeneration;
    u32 nextEntryGeneration;
    u32 nextTimerGeneration;
    u32 layerGeneration;
    u32 effectiveGeneration;
    u32 cacheIncarnation;
    u16 lifecycleTransitions;
    u8 activeLayerCount;
    u8 lifecycleState;
    u8 presentationGate;
    u8 timerStateReserved[3];
    OverworldWildRuntimeLayerBank layerBank;
    OverworldWildRuntimeTimerBank timerBank;
    OverworldWildRuntimeStaticCache staticCache;
    OverworldWildRuntimeEffectiveCache effectiveCache;
    OverworldWildRuntimeProvenance provenance;
} OverworldWildRuntimeSlotSidecar;

typedef struct OverworldWildBehaviorStackRuntime {
    u32 handleEpoch;
    u32 dataIncarnation;
    u8 lifetimeState;
    u8 reserved[3];
    OverworldWildRuntimeSlotSidecar slots[OW_WILD_MAX_SPAWNS];
} OverworldWildBehaviorStackRuntime;

typedef char OverworldWildRuntimeSpawnCapacityMustRemain10[
    OW_WILD_MAX_SPAWNS == 10 ? 1 : -1];
typedef char OverworldWildRuntimeLayerCapacityMustRemain8[
    OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT == 8 ? 1 : -1];
typedef char OverworldWildRuntimeLayerSizeMustRemain16[
    sizeof(OverworldWildRuntimeLayer) == 16 ? 1 : -1];
typedef char OverworldWildRuntimeLayerBankSizeMustRemain112[
    sizeof(OverworldWildRuntimeLayerBank) == 112 ? 1 : -1];
typedef char OverworldWildRuntimeTimerSizeMustRemain24[
    sizeof(OverworldWildRuntimeTimer) == 24 ? 1 : -1];
typedef char OverworldWildRuntimeTimerBankSizeMustRemain192[
    sizeof(OverworldWildRuntimeTimerBank) == 192 ? 1 : -1];
typedef char OverworldWildRuntimeTimerExpirySizeMustRemain32[
    sizeof(OverworldWildRuntimeTimerExpiry) == 32 ? 1 : -1];
typedef char OverworldWildRuntimeStaticContextSizeMustRemain12[
    sizeof(OverworldWildRuntimeStaticContext) == 12 ? 1 : -1];
typedef char OverworldWildRuntimeResolvedStaticContextSizeMustRemain60[
    sizeof(OverworldWildRuntimeResolvedStaticContext) == 60 ? 1 : -1];
typedef char OverworldWildRuntimeRecoveryCandidateSizeMustRemain16[
    sizeof(OverworldWildRuntimeRecoveryCandidate) == 16 ? 1 : -1];
typedef char OverworldWildRuntimeCommandIdentitySizeMustRemain20[
    sizeof(OverworldWildRuntimeCommandIdentity) == 20 ? 1 : -1];
typedef char OverworldWildRuntimeCommandOriginSizeMustRemain52[
    sizeof(OverworldWildRuntimeCommandOrigin) == 52 ? 1 : -1];
typedef char OverworldWildRuntimeCommandOriginBankSizeMustRemain520[
    sizeof(OverworldWildRuntimeCommandOriginBank) == 520 ? 1 : -1];
typedef char OverworldWildRuntimeEffectiveCacheSizeMustRemain104[
    sizeof(OverworldWildRuntimeEffectiveCache) == 104 ? 1 : -1];
typedef char OverworldWildRuntimeTransitionEventSizeMustRemain36[
    sizeof(OverworldWildRuntimeTransitionEvent) == 36 ? 1 : -1];
typedef char OverworldWildRuntimeTransitionResultSizeMustRemain120[
    sizeof(OverworldWildRuntimeTransitionResult) == 120 ? 1 : -1];
typedef char OverworldWildRuntimeStaticModifierContributionSizeMustRemain18[
    sizeof(OverworldWildRuntimeStaticModifierContribution) == 18 ? 1 : -1];
typedef char OverworldWildRuntimeResolvedNodeSizeMustRemain38[
    sizeof(OverworldWildRuntimeResolvedNode) == 38 ? 1 : -1];
typedef char OverworldWildRuntimeSpawnConfigurationSizeMustRemain12[
    sizeof(OverworldWildRuntimeSpawnConfiguration) == 12 ? 1 : -1];
typedef char OverworldWildRuntimeStaticCacheSizeMustRemain552[
    sizeof(OverworldWildRuntimeStaticCache) == 552 ? 1 : -1];
typedef char OverworldWildRuntimeCandidateProvenanceSizeMustRemain20[
    sizeof(OverworldWildRuntimeCandidateProvenance) == 20 ? 1 : -1];
typedef char OverworldWildRuntimeModifierProvenanceSizeMustRemain16[
    sizeof(OverworldWildRuntimeModifierProvenance) == 16 ? 1 : -1];
typedef char OverworldWildRuntimeFieldContributionSizeMustRemain14[
    sizeof(OverworldWildRuntimeFieldContribution) == 14 ? 1 : -1];
typedef char OverworldWildRuntimeProvenanceSizeMustRemain728[
    sizeof(OverworldWildRuntimeProvenance) == 728 ? 1 : -1];
typedef char OverworldWildRuntimeSlotSidecarSizeMustRemain1724[
    sizeof(OverworldWildRuntimeSlotSidecar) == 1724 ? 1 : -1];
typedef char OverworldWildBehaviorStackRuntimeSizeMustRemain17252[
    sizeof(OverworldWildBehaviorStackRuntime) == 17252 ? 1 : -1];
typedef char OverworldWildRuntimeLayerArrayMustRemainFixed[
    sizeof(((OverworldWildRuntimeLayerBank *)0)->entryGenerations)
        == sizeof(u32) * OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT
        ? 1 : -1];
typedef char OverworldWildRuntimeSlotArrayMustRemainFixed[
    sizeof(((OverworldWildBehaviorStackRuntime *)0)->slots)
        == sizeof(OverworldWildRuntimeSlotSidecar) * OW_WILD_MAX_SPAWNS
        ? 1 : -1];
typedef char OverworldWildRuntimeHandleSizeMustRemain24[
    sizeof(OverworldWildRuntimeLayerHandle) == 24 ? 1 : -1];
typedef char OverworldWildRuntimeDeltaOperationSizeMustRemain28[
    sizeof(OverworldWildRuntimeDeltaOperation) == 28 ? 1 : -1];
typedef char OverworldWildRuntimeApplicabilityInputSizeMustRemain28[
    sizeof(OverworldWildRuntimeApplicabilityInput) == 28 ? 1 : -1];
typedef char OverworldWildRuntimeStackDeltaRequestSizeMustRemain484[
    sizeof(OverworldWildRuntimeStackDeltaRequest) == 484 ? 1 : -1];
typedef char OverworldWildRuntimeDeltaOperationResultSizeMustRemain28[
    sizeof(OverworldWildRuntimeDeltaOperationResult) == 28 ? 1 : -1];
typedef char OverworldWildRuntimeStackDeltaResultSizeMustRemain484[
    sizeof(OverworldWildRuntimeStackDeltaResult) == 484 ? 1 : -1];
typedef char OverworldWildRuntimeTimerRecoveryResultSizeMustRemain44[
    sizeof(OverworldWildRuntimeTimerRecoveryResult) == 44 ? 1 : -1];

#ifndef OW_WILD_RUNTIME_SIDECAR_CODE
#ifdef OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
#define OW_WILD_RUNTIME_SIDECAR_CODE \
    __attribute__((noinline, used, section(".ow_wild_runtime_sidecars")))
#else
#define OW_WILD_RUNTIME_SIDECAR_CODE
#endif
#endif

static inline u32 OverworldWildRuntime_AdvanceNonzeroGeneration(u32 generation)
{
    generation++;
    return generation != 0 ? generation : 1;
}

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_InitSlot(
    OverworldWildRuntimeSlotSidecar *slot);
void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_Init(
    OverworldWildBehaviorStackRuntime *runtime);
void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_DestructivelyInvalidateSlot(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    BOOL wasLive);
void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlotIndex);
/* Resident overlay-158 lifecycle helper used by the frozen overlay-155 ABI. */
void OverworldWildRuntime_ClearSlotStorage(
    OverworldWildRuntimeSlotSidecar *slot);
void OverworldWildRuntime_InitializeStorage(
    OverworldWildBehaviorStackRuntime *runtime);
void OverworldWildRuntime_MarkResidentCold(
    OverworldWildBehaviorStackRuntime *runtime);

/* Lifecycle-only binding. Definitions and generated metadata are copied from
 * the installed validated v40 bundle through a private resident accessor. */
OverworldWildRuntimeStatus OverworldWildRuntime_BindPrivateIdentity(
    OverworldWildBehaviorStackRuntime *runtime);

OverworldWildRuntimeStatus OverworldWildRuntime_ApplyStackDelta(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeStackDeltaRequest *request,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_Apply(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    u16 definitionId,
    u16 ownerId,
    u16 instanceKey,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_Replace(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    u16 ownerId,
    u16 instanceKey,
    u16 definitionId,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_Remove(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeLayerHandle *handle,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_RemoveOwner(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u16 ownerId,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_ClearAllForSlot(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_PrimeEffectiveCache(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *applicability);
#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
OverworldWildRuntimeStatus OverworldWildRuntime_ResolveCanonicalStaticContext(
    const OverworldWildRuntimeStaticContext *staticContext,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut);
OverworldWildRuntimeStatus OverworldWildRuntime_PrimeCanonicalEffectiveCache(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeStaticContext *staticContext,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut);
OverworldWildRuntimeStatus OverworldWildRuntime_ResolveRecoveryCandidate(
    const OverworldWildRuntimeStaticContext *staticContext,
    u8 origin,
    OverworldWildRuntimeRecoveryCandidate *candidateOut);
#endif
OverworldWildRuntimeStatus OverworldWildRuntime_GetEffectiveCache(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeEffectiveCache *cacheOut);
OverworldWildRuntimeStatus OverworldWildRuntime_GetCapabilityMask(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u32 *capabilityMaskOut);
OverworldWildRuntimeStatus OverworldWildRuntime_GetProvenance(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeProvenance *provenanceOut);
OverworldWildRuntimeStatus
OverworldWildRuntime_CopyValidatedSpawnConfiguration(
    const OverworldWildRuntimeStaticCache *staticCache,
    u32 expectedStaticContextGeneration,
    OverworldWildRuntimeSpawnConfiguration *configurationOut);

u8 OverworldWildRuntime_GetTimerCount(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration);
OverworldWildRuntimeStatus OverworldWildRuntime_GetTimerByIndex(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u8 timerIndex,
    OverworldWildRuntimeTimer *timerOut);
OverworldWildRuntimeStatus OverworldWildRuntime_TickCandidateTimers(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u8 clock,
    u8 ticks,
    BOOL presentationGate,
    OverworldWildRuntimeTimerTickResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_SetTimerPresentationGate(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    BOOL active);
OverworldWildRuntimeStatus OverworldWildRuntime_TickFrameTimers(
    OverworldWildBehaviorStackRuntime *runtime,
    u16 presentationGateMask,
    OverworldWildRuntimeTimerTickResult
        results[OW_WILD_MAX_SPAWNS]);
OverworldWildRuntimeStatus OverworldWildRuntime_TickCompletedMovementTimers(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    BOOL presentationGate,
    OverworldWildRuntimeTimerTickResult *result);
u8 OverworldWildRuntime_GetPendingTimerExpiryCount(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration);
OverworldWildRuntimeStatus OverworldWildRuntime_GetPendingTimerExpiryByIndex(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u8 pendingIndex,
    OverworldWildRuntimeTimerExpiry *expiryOut);
#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
OverworldWildRuntimeStatus OverworldWildRuntime_CommitTimerExpiry(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeStackDeltaResult *result);
OverworldWildRuntimeStatus OverworldWildRuntime_RecoverExpiredTimer(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeTimerRecoveryResult *result);
#endif
OverworldWildRuntimeStatus OverworldWildRuntime_DispatchTransition(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeTransitionEvent *event,
    OverworldWildRuntimeTransitionResult *result);

OverworldWildRuntimeStatus OverworldWildRuntime_CaptureCommandOrigin(
    const OverworldWildBehaviorStackRuntime *runtime,
    OverworldWildRuntimeCommandOriginBank *bank,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeCommandIdentity *identity);
OverworldWildRuntimeStatus OverworldWildRuntime_ConsumeCommandOrigin(
    const OverworldWildBehaviorStackRuntime *runtime,
    OverworldWildRuntimeCommandOriginBank *bank,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeCommandIdentity *identity,
    OverworldWildRuntimeCommandOrigin *originOut);
void OverworldWildRuntime_InvalidateCommandOrigin(
    OverworldWildRuntimeCommandOriginBank *bank,
    u8 slotIndex);
void OverworldWildRuntime_InvalidateAllCommandOrigins(
    OverworldWildRuntimeCommandOriginBank *bank);

u8 OverworldWildRuntime_GetLayerCount(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration);
OverworldWildRuntimeStatus OverworldWildRuntime_GetLayerByIndex(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u8 layerIndex,
    OverworldWildRuntimeLayer *layerOut);
OverworldWildRuntimeStatus OverworldWildRuntime_FindLayer(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u16 ownerId,
    u16 instanceKey,
    OverworldWildRuntimeLayer *layerOut,
    OverworldWildRuntimeLayerHandle *handleOut);

static inline void OverworldWildRuntime_Activate(
    OverworldWildBehaviorStackRuntime *runtime)
{
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
}

static inline void OverworldWildRuntime_MarkSlotAssigned(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex)
{
    runtime->slots[slotIndex].lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED;
}

#endif // OVERWORLD_WILD_RUNTIME_SIDECARS_H

#ifdef OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_InitSlot(
    OverworldWildRuntimeSlotSidecar *slot)
{
    OverworldWildRuntime_ClearSlotStorage(slot);
    slot->slotGeneration = 1;
    slot->staticContextGeneration = 1;
    slot->nextEntryGeneration = 1;
    slot->nextTimerGeneration = 1;
    slot->layerGeneration = 1;
    slot->effectiveGeneration = 1;
    slot->cacheIncarnation = 1;
    slot->lifecycleState = OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN;
    /* Preserve the frozen overlay-155 lifecycle entry offsets. */
    __asm__ volatile("nop");
}

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_Init(
    OverworldWildBehaviorStackRuntime *runtime)
{
    OverworldWildRuntime_InitializeStorage(runtime);
    /* Preserve the frozen 0x20-byte overlay-155 lifecycle entry. */
    __asm__ volatile(
        "nop\n\tnop\n\tnop\n\tnop\n\tnop\n\tnop\n\t"
        "nop\n\tnop\n\tnop\n\tnop\n\tnop\n\tnop");
}

void OW_WILD_RUNTIME_SIDECAR_CODE OverworldWildRuntime_DestructivelyInvalidateSlot(
    OverworldWildBehaviorStackRuntime *runtime,
    int slotIndex,
    BOOL wasLive)
{
    if (!wasLive) return;
    OverworldWildRuntime_HandleSlotGenerationWrap(runtime, slotIndex);
    /* Freeze this public overlay-155 entry at its intentional 0x30-byte ABI. */
    __asm__ volatile(
        "nop\n\tnop\n\tnop\n\tnop\n\tnop\n\tnop\n\t"
        "nop\n\tnop\n\tnop\n\tnop\n\tnop\n\tnop\n\t"
        "nop\n\tnop\n\tnop\n\tnop\n\tnop\n\tnop");
}

#endif // OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION

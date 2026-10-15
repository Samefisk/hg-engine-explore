#ifndef OVERWORLD_MOTION_MODEL_H
#define OVERWORLD_MOTION_MODEL_H

#ifdef OVERWORLD_MOTION_HOST
#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int16_t s16;
typedef int32_t s32;
typedef int64_t s64;
#ifndef TRUE
#define TRUE 1
#define FALSE 0
#endif
#else
#include "types.h"
#endif

/*
 * Pointer-free motion values shared by the Nintendo DS adapter and host
 * fixtures. Engine objects, collision queries, and presentation objects stay
 * outside this interface.
 */

#define OVERWORLD_MOTION_MODEL_VERSION 1
#define OVERWORLD_MOTION_MAX_CANDIDATES 8
#define OVERWORLD_MOTION_FLAG_FORCED (1u << 0)
#define OVERWORLD_MOTION_FLAG_SLAM (1u << 1)

typedef enum OverworldMotionKind {
    OVERWORLD_MOTION_KIND_NONE = 0,
    OVERWORLD_MOTION_KIND_WALK = 1,
    OVERWORLD_MOTION_KIND_HOP = 2,
    OVERWORLD_MOTION_KIND_TELEPORT = 3,
    OVERWORLD_MOTION_KIND_SKID = 4,
    OVERWORLD_MOTION_KIND_REPOSITION = 5,
    OVERWORLD_MOTION_KIND_FLY_IN = 6,
} OverworldMotionKind;

typedef enum OverworldMotionPhase {
    OVERWORLD_MOTION_PHASE_IDLE = 0,
    OVERWORLD_MOTION_PHASE_PLANNED = 1,
    OVERWORLD_MOTION_PHASE_MOVING = 2,
    OVERWORLD_MOTION_PHASE_COMMIT_PENDING = 3,
    OVERWORLD_MOTION_PHASE_SETTLING = 4,
    OVERWORLD_MOTION_PHASE_SUSPENDED = 5,
    OVERWORLD_MOTION_PHASE_CANCELED = 6,
} OverworldMotionPhase;

typedef enum OverworldMotionDecision {
    OVERWORLD_MOTION_DECISION_ACCEPTED = 0,
    OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY = 1,
    OVERWORLD_MOTION_DECISION_BLOCKED = 2,
    OVERWORLD_MOTION_DECISION_SIDE_TILE = 3,
    OVERWORLD_MOTION_DECISION_TERRAIN = 4,
    OVERWORLD_MOTION_DECISION_OCCUPIED = 5,
    OVERWORLD_MOTION_DECISION_RESERVED = 6,
    OVERWORLD_MOTION_DECISION_DIRECTION = 7,
    OVERWORLD_MOTION_DECISION_PROFILE = 8,
    OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE = 9,
    OVERWORLD_MOTION_DECISION_STALE_FIELD = 10,
    OVERWORLD_MOTION_DECISION_CONTEXT_LOST = 11,
    OVERWORLD_MOTION_DECISION_NO_CANDIDATE = 12,
} OverworldMotionDecision;

typedef enum OverworldMotionCommitPolicy {
    OVERWORLD_MOTION_COMMIT_NORMAL = 0,
    OVERWORLD_MOTION_COMMIT_NO_CHAIN = 1,
    OVERWORLD_MOTION_COMMIT_PRESENTATION_ONLY = 2,
} OverworldMotionCommitPolicy;

typedef enum OverworldMotionPathAdvancePolicy {
    OVERWORLD_MOTION_PATH_ADVANCE_NONE = 0,
    OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY = 1,
    OVERWORLD_MOTION_PATH_ADVANCE_PLAYER = 2,
} OverworldMotionPathAdvancePolicy;

typedef enum OverworldMotionVisibilityPolicy {
    OVERWORLD_MOTION_VISIBILITY_VISIBLE = 0,
    OVERWORLD_MOTION_VISIBILITY_HIDDEN = 1,
    OVERWORLD_MOTION_VISIBILITY_FLICKER = 2,
} OverworldMotionVisibilityPolicy;

#define OVERWORLD_MOTION_CANDIDATE_BLOCKED       (1u << 0)
#define OVERWORLD_MOTION_CANDIDATE_SIDE_BLOCKED  (1u << 1)
#define OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN   (1u << 2)
#define OVERWORLD_MOTION_CANDIDATE_OCCUPIED      (1u << 3)
#define OVERWORLD_MOTION_CANDIDATE_RESERVED      (1u << 4)
#define OVERWORLD_MOTION_CANDIDATE_BAD_DIRECTION (1u << 5)
#define OVERWORLD_MOTION_CANDIDATE_WORLD_BUSY    (1u << 6)

typedef struct OverworldMotionIntent {
    u16 version;
    u8 kind;
    u8 facing;
    u16 fieldEpoch;
    u16 behaviorFingerprint;
    u16 duration;
    u8 arcHeightQ4;
    /* Slam owns these phase bytes; other motion keeps its spin and sway. */
    __extension__ union { u8 spinSpeed; u8 arcRiseFrames; };
    __extension__ union { u8 swayWidth; u8 arcHangFrames; };
    u8 visibilityPolicy;
    u8 pauseFrames;
    u8 pathAdvancePolicy;
    u8 commitPolicy;
    u8 flags;
} OverworldMotionIntent;

static inline u8 OverworldMotion_ApplyWalkPauseVariance(
    u8 pauseFrames,
    u8 variance,
    u8 phase)
{
    u16 variedPause = pauseFrames
        + (u8)(((u16)phase * (variance + 1u)) >> 8);

    return variedPause > 255 ? 255 : (u8)variedPause;
}

/* Unit rise/drop height in fx32. Both callers pass a positive denominator.
 * Clearance passes exact crossed-cell fractions; Motion passes frame time. */
#ifdef OVERWORLD_MOTION_HOST
static inline u32 OverworldMotion_SlamUnitHeight(u32 progress, u32 total)
{
    return progress >= total ? 0x1000u : (progress << 12) / total;
}
static inline u32 OverworldMotion_SlamRiseUnitHeight(u32 progress, u32 total)
{
    u32 height = OverworldMotion_SlamUnitHeight(progress, total);

    return 2u * height - ((height * height) >> 12);
}
#else
extern u32 OverworldMotion_SlamUnitHeight(u32 progress, u32 total);
__asm__(".global OverworldMotion_SlamUnitHeight\n.type OverworldMotion_SlamUnitHeight, %function\n.thumb\n.thumb_func\n.thumb_set OverworldMotion_SlamUnitHeight, 0x01FFA4EC\n");
extern u32 OverworldMotion_SlamRiseUnitHeight(u32 progress, u32 total);
__asm__(".global OverworldMotion_SlamRiseUnitHeight\n.type OverworldMotion_SlamRiseUnitHeight, %function\n.thumb\n.thumb_func\n.thumb_set OverworldMotion_SlamRiseUnitHeight, 0x023B8601\n");
extern u32 OverworldMotion_SlamPhaseCheck(u32 kind, u32 peak, u32 rise,
    s32 durationMinusHang);
__asm__(".global OverworldMotion_SlamPhaseCheck\n.type OverworldMotion_SlamPhaseCheck, %function\n.thumb\n.thumb_func\n.thumb_set OverworldMotion_SlamPhaseCheck, 0x023BD4D9\n");
#endif

typedef struct OverworldMotionCandidate {
    s16 targetX;
    s16 targetY;
    s32 targetBaseY;
    u16 rejectionFlags;
    u8 direction;
    u8 distance;
    u16 reservationId;
} OverworldMotionCandidate;

typedef struct OverworldMotionPlan {
    u16 version;
    u8 kind;
    u8 facing;
    u16 fieldEpoch;
    u16 behaviorFingerprint;
    s16 startX;
    s16 startY;
    s16 targetX;
    s16 targetY;
    s32 startBaseY;
    s32 targetBaseY;
    u16 duration;
    u16 reservationId;
    u8 direction;
    u8 distance;
    u8 arcHeightQ4;
    /* Slam owns these phase bytes; other motion keeps its spin and sway. */
    __extension__ union { u8 spinSpeed; u8 arcRiseFrames; };
    __extension__ union { u8 swayWidth; u8 arcHangFrames; };
    u8 visibilityPolicy;
    u8 pauseFrames;
    u8 pathAdvancePolicy;
    u8 commitPolicy;
    u8 flags;
} OverworldMotionPlan;

typedef struct OverworldMotionState {
    OverworldMotionPlan plan;
    u16 elapsed;
    u16 settleRemaining;
    u16 pathAdvancesPublished;
    u16 commitSequence;
    u8 phase;
    u8 phaseBeforeSuspend;
    u8 commitPublished;
    u8 cancelReason;
} OverworldMotionState;

#define OVERWORLD_MOTION_TICK_MOVED          (1u << 0)
#define OVERWORLD_MOTION_TICK_PATH_ADVANCED  (1u << 1)
#define OVERWORLD_MOTION_TICK_REACHED_TARGET (1u << 2)
#define OVERWORLD_MOTION_TICK_COMMIT_READY   (1u << 3)
#define OVERWORLD_MOTION_TICK_FINISHED       (1u << 4)
#define OVERWORLD_MOTION_TICK_VISIBILITY     (1u << 5)

typedef struct OverworldMotionSample {
    s32 renderX;
    s32 renderY;
    s32 renderZ;
    s32 baseY;
    s32 heightOffset;
    s32 swayOffset;
    u16 elapsed;
    u16 duration;
    u16 firstPathAdvance;
    u16 lastPathAdvance;
    u16 flags;
    u8 facing;
    u8 visible;
} OverworldMotionSample;

static inline u8 OverworldMotion_BlocksWorldGate(
    u8 actorActive,
    u8 inputOwnership,
    u8 phase,
    u16 reservationId)
{
    return actorActive && inputOwnership
        && (reservationId != 0
            || (phase != OVERWORLD_MOTION_PHASE_IDLE
                && phase != OVERWORLD_MOTION_PHASE_CANCELED));
}

/*
 * Tick advances exactly one motion frame. firstPathAdvance..lastPathAdvance
 * is an inclusive, ordered range of newly crossed tiles; the adapter can map
 * each index to a logical tile with OverworldMotion_GetPathAdvanceTile.
 * Presentation offsets never add path advances.
 *
 * Reaching the target leaves the motion in COMMIT_PENDING until the engine
 * adapter acknowledges its one terminal boundary. Authored pause frames start
 * after that acknowledgement. A field transition must suspend first, then
 * rebind the snapshotted epoch before motion can resume.
 */
OverworldMotionDecision OverworldMotion_SelectPlan(
    const OverworldMotionIntent *intent,
    s16 startX,
    s16 startY,
    s32 startBaseY,
    const OverworldMotionCandidate *candidates,
    u8 candidateCount,
    OverworldMotionPlan *plan,
    u8 *selectedIndex);
void OverworldMotion_Reset(OverworldMotionState *state);
OverworldMotionDecision OverworldMotion_Begin(
    OverworldMotionState *state,
    const OverworldMotionPlan *plan);
u16 OverworldMotion_Tick(
    OverworldMotionState *state,
    u16 fieldEpoch,
    OverworldMotionSample *sample);
OverworldMotionDecision OverworldMotion_Read(
    const OverworldMotionState *state,
    u16 fieldEpoch,
    OverworldMotionSample *sample);
OverworldMotionDecision OverworldMotion_AcknowledgeCommit(
    OverworldMotionState *state,
    u16 fieldEpoch);
u8 OverworldMotion_GetPathAdvanceTile(
    const OverworldMotionPlan *plan,
    u16 advanceIndex,
    s16 *tileX,
    s16 *tileY);
void OverworldMotion_Suspend(OverworldMotionState *state);
OverworldMotionDecision OverworldMotion_Resume(
    OverworldMotionState *state,
    u16 fieldEpoch);
OverworldMotionDecision OverworldMotion_RebindField(
    OverworldMotionState *state,
    u16 previousFieldEpoch,
    u16 reboundFieldEpoch);
void OverworldMotion_Cancel(OverworldMotionState *state, u8 reason);

#endif // OVERWORLD_MOTION_MODEL_H

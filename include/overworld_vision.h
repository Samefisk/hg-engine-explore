#ifndef OVERWORLD_VISION_H
#define OVERWORLD_VISION_H

#if defined(OVERWORLD_VISION_HOST) \
    || defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <stdint.h>
typedef uint8_t u8;
typedef int16_t s16;
#else
#include "types.h"
#endif

/*
 * Pointer-free vision geometry shared by host fixtures and engine adapters.
 * Engine objects, terrain queries, and actor lists stay outside this API.
 */

#define OVERWORLD_VISION_DEFAULT_RANGE 3
#define OVERWORLD_VISION_MAX_RANGE 32

#define OVERWORLD_VISION_CONE_FORWARD_90 1
#define OVERWORLD_VISION_CONE_MASK 0x03
#define OVERWORLD_VISION_ADJACENT_AWARENESS (1u << 2)
#define OVERWORLD_VISION_OPTIONS_MASK \
    (OVERWORLD_VISION_CONE_MASK | OVERWORLD_VISION_ADJACENT_AWARENESS)
#define OVERWORLD_VISION_DEFAULT_OPTIONS \
    (OVERWORLD_VISION_CONE_FORWARD_90 \
        | OVERWORLD_VISION_ADJACENT_AWARENESS)

#define OVERWORLD_VISION_FACING_NORTH 0
#define OVERWORLD_VISION_FACING_SOUTH 1
#define OVERWORLD_VISION_FACING_WEST  2
#define OVERWORLD_VISION_FACING_EAST  3

typedef struct OverworldVisionSpec {
    u8 range;
    u8 options;
} OverworldVisionSpec;

#define OVERWORLD_VISION_DEFAULT_SPEC_INITIALIZER \
    { OVERWORLD_VISION_DEFAULT_RANGE, OVERWORLD_VISION_DEFAULT_OPTIONS }

typedef char OverworldVisionSpecSizeMustRemain2Bytes[
    sizeof(OverworldVisionSpec) == 2 ? 1 : -1];

u8 OverworldVision_IsValidSpec(const OverworldVisionSpec *spec);

/*
 * Returns whether the target is inside the observer's geometric view.
 * The view is an inclusive 90-degree forward cone. Every one-tile neighbor
 * is visible regardless of facing. Observer and target must occupy different
 * tiles.
 */
u8 OverworldVision_IsInView(
    const OverworldVisionSpec *spec,
    s16 observerX,
    s16 observerY,
    u8 observerFacing,
    s16 targetX,
    s16 targetY);

/*
 * Applies a caller-supplied occlusion fact after the geometry check.
 * The caller owns terrain access and should set occluded only for solid tiles
 * strictly between observer and target. Actors and both endpoint tiles are
 * not blockers.
 */
u8 OverworldVision_CanSee(
    const OverworldVisionSpec *spec,
    s16 observerX,
    s16 observerY,
    u8 observerFacing,
    s16 targetX,
    s16 targetY,
    u8 occluded);

#endif // OVERWORLD_VISION_H

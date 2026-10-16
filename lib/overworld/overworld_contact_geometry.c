#include "../../include/overworld_contact_geometry.h"

/* Relative poses use 1/1024-tile units. Exact rational slab times prevent
 * two disjoint axis intervals from becoming equal through Q10 truncation. */
static BOOL PlayerHealthContact_ClipAxis(s32 start, s32 end,
    s32 lower, s32 upper, BOOL landing,
    u32 *enterNum, u32 *enterDen, u32 *leaveNum, u32 *leaveDen)
{
    s32 delta;
    s32 first;
    s32 last;

    /* Check the raw pose before trimming the landing end or dividing. */
    if (start < -32768 || start > 32768
        || end < -32768 || end > 32768) {
        return FALSE;
    }
    if (landing) {
        end = start + (end - start) * 1023 / 1024;
    }
    delta = end - start;
    if ((start < lower && end < lower)
        || (start > upper && end > upper)) {
        return FALSE;
    }
    if (delta == 0) {
        return start >= lower && start <= upper;
    }
    if (delta < 0) {
        delta = -delta;
        first = start - upper;
        last = start - lower;
    } else {
        first = lower - start;
        last = upper - start;
    }
    /* Each numerator is at most 34048 and delta at most 65536, so these
     * unsigned cross-products fit in 32 bits. */
    if (first > 0
        && (u32)first * *enterDen > *enterNum * (u32)delta) {
        *enterNum = (u32)first;
        *enterDen = (u32)delta;
    }
    if (last < delta
        && (u32)last * *leaveDen < *leaveNum * (u32)delta) {
        *leaveNum = (u32)last;
        *leaveDen = (u32)delta;
    }
    return *enterNum * *leaveDen <= *leaveNum * *enterDen;
}

BOOL OverworldContactGeometry_Intersects(
    const PlayerHealthContactSegment *sample)
{
    s32 startX;
    s32 startY;
    s32 startZ;
    s32 endX;
    s32 endY;
    s32 endZ;
    u32 enterNum = 0;
    u32 enterDen = 1;
    u32 leaveNum = 1;
    u32 leaveDen = 1;

    if (sample == NULL) {
        return FALSE;
    }
    startX = sample->oldX;
    startY = sample->oldY;
    startZ = sample->oldZ;
    endX = sample->newX;
    endY = sample->newY;
    endZ = sample->newZ;

    if (sample->landingSample
        && startX == endX && startY == endY && startZ == endZ) {
        return FALSE;
    }
    /* The landing pose is harmless. Keep only the airborne portion. */
    return PlayerHealthContact_ClipAxis(
            startX, endX, -512, 512, sample->landingSample,
            &enterNum, &enterDen, &leaveNum, &leaveDen)
        && PlayerHealthContact_ClipAxis(
            startZ, endZ, -512, 512, sample->landingSample,
            &enterNum, &enterDen, &leaveNum, &leaveDen)
        && PlayerHealthContact_ClipAxis(
            startY, endY, -256, 1280, sample->landingSample,
            &enterNum, &enterDen, &leaveNum, &leaveDen);
}


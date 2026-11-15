/* The runner inserts unedited production bodies: the shared Hop clearance
 * reducer, Hop geometry, height interpolation, and Hop trajectory/arc. Only
 * the world reads are a fixture grid. This does not prove ARM layout, live
 * object occupancy, or gameplay feel.
 */
#include <stdio.h>
#include <assert.h>
#include <string.h>

/* @PRELUDE@ */

#define GRID 24
static u8 sBlocked[GRID][GRID];
static u8 sObject[GRID][GRID];
static u8 sBehavior[GRID][GRID];
static u8 sNoGround[GRID][GRID];
/* A native tree canopy: the blocked tree cell carries surface 0xFFFE, whose
 * top is 0x31580 FX32 (about three tiles) above the ground. */
static u8 sCanopy[GRID][GRID];
#define CANOPY_HEIGHT 0x31580
static s32 sStartY, sTargetY;
static s32 sGroundHeight[GRID][GRID], sCanopyHeight[GRID][GRID];
static u8 sNativeGround[GRID][GRID], sStrictHeight;
static int sExpectedDecision = -1;

static BOOL Blocked(FieldSystem *field, int x, int y)
{
    (void)field;
    return x < 0 || y < 0 || x >= GRID || y >= GRID || sBlocked[y][x];
}
static u8 Behavior(FieldSystem *field, int x, int y)
{
    (void)field;
    return x < 0 || y < 0 || x >= GRID || y >= GRID ? 0 : sBehavior[y][x];
}
static BOOL Occupied(FieldSystem *field, LocalMapObject *ignored,
    LocalMapObject *collisionIgnored, int x, int y, s32 baseY, int mode)
{
    (void)field; (void)ignored; (void)collisionIgnored; (void)baseY; (void)mode;
    return x >= 0 && y >= 0 && x < GRID && y < GRID && sObject[y][x];
}
static BOOL Surface(FieldSystem *field, const OverworldWildSurfaceCatalog *catalog,
    int x, int y, OverworldWildSurfaceHit *hit)
{
    (void)field; (void)catalog;
    if (x < 0 || y < 0 || x >= GRID || y >= GRID || (!sCanopy[y][x] && !sNativeGround[y][x])) {
        return FALSE;
    }
    memset(hit, 0, sizeof(*hit));
    hit->surfaceId = sCanopy[y][x] ? OW_WILD_SURFACE_ID_NATIVE_CANOPY
        : OW_WILD_SURFACE_ID_NATIVE_GROUND;
    hit->height = sCanopy[y][x] ? (sCanopyHeight[y][x] ? sCanopyHeight[y][x] : CANOPY_HEIGHT)
        : sGroundHeight[y][x];
    return TRUE;
}
static BOOL ResolveBaseY(FieldSystem *field, const OverworldWildSurfaceHit *hit,
    s32 startBaseY, u32 objectFlags, int x, int y, s32 *out)
{
    (void)field; (void)objectFlags;
    if (x < 0 || y < 0 || x >= GRID || y >= GRID || sNoGround[y][x]) {
        return FALSE;
    }
    if (hit != NULL) {
        *out = startBaseY + hit->height;
        return TRUE;
    }
    /* A cliff face has no native ground. */
    if (hit == NULL && x >= 0 && y >= 0 && x < GRID && y < GRID && sNoGround[y][x]) {
        return FALSE;
    }
    *out = startBaseY + sGroundHeight[y][x];
    return TRUE;
}
static s32 SlamArc(u16 n, u16 d, u8 p) { (void)n; (void)d; (void)p; return 0; }
static u32 SlamPhase(u32 a, u32 b, u32 c, s32 d) { (void)a; (void)b; (void)c; (void)d; return 0; }
static u32 UDiv(u32 a, u32 b) { return a / b; }
static s32 SDiv(s32 a, s32 b) { return a / b; }
static BOOL Current(FieldSystem *field, const void *entry) { (void)field; (void)entry; return TRUE; }

static const OverworldHopClearanceNativeOps sOps = {
    OVERWORLD_HOP_CLEARANCE_NATIVE_MAGIC, OVERWORLD_HOP_CLEARANCE_NATIVE_VERSION,
    sizeof(OverworldHopClearanceNativeOps), &gOverworldQueryCodeAddonEntry, Current,
    OverworldActorHopGeometry_Init, OverworldActorHopGeometry_NextCell,
    OverworldActorHopPlanner_LerpFx32, SlamArc, SlamPhase,
    Surface, ResolveBaseY,
    OverworldWildBehavior_CalculateJumpTrajectory, OverworldWildBehavior_CalculateJumpArc,
    UDiv, SDiv, Blocked, Behavior, Occupied,
};

/* Plan one Hop from (4,10). Prints: label accepted arc. */
static void Plan(const char *label, u8 jump, u8 minDistance, u8 maxDistance,
    u8 jumpLevel, u8 framesPerTile, int dx, int dy, u8 distance)
{
    OverworldWildBehaviorProfileData lane;
    OverworldActorHopPlanCall call;
    LocalMapObject object;
    OverworldMotionDecision decision;

    memset(&lane, 0, sizeof(lane));
    memset(&call, 0, sizeof(call));
    memset(&object, 0, sizeof(object));
    lane.hopAllowVerticalObstacles = jump;
    lane.hopMinDistance = minDistance;
    lane.hopMaxDistance = maxDistance;
    lane.jumpLevel = jumpLevel;
    lane.hopTime = framesPerTile;
    lane.hopElevationTimeScale = 100;
    call.lane = &lane;
    call.fieldSystem = (FieldSystem *)&object;
    call.object = &object;
    call.startX = 4;
    call.startY = 10;
    call.targetX = (s16)(4 + dx * distance);
    call.targetY = (s16)(10 + dy * distance);
    call.distance = distance;
    call.startBaseY = sStartY;
    call.targetBaseY = sTargetY;
    call.operation = OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY;
    call.spotState = sStrictHeight ? OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT : 0;
    decision = OverworldActorHopPlanner_PlanTrajectory(&call, &sOps);
    if (sExpectedDecision >= 0) { assert(decision == sExpectedDecision); }
    printf("%s %d %u\n", label, decision == OVERWORLD_MOTION_DECISION_ACCEPTED,
        (unsigned)(call.trajectory >> 16));
}

static void Clear(void)
{
    memset(sBlocked, 0, sizeof(sBlocked));
    memset(sObject, 0, sizeof(sObject));
    memset(sBehavior, 0, sizeof(sBehavior));
    memset(sNoGround, 0, sizeof(sNoGround));
    memset(sCanopy, 0, sizeof(sCanopy));
    sStartY = sTargetY = 0;
    memset(sGroundHeight, 0, sizeof(sGroundHeight));
    memset(sCanopyHeight, 0, sizeof(sCanopyHeight));
    memset(sNativeGround, 0, sizeof(sNativeGround));
    sStrictHeight = 0;
    sExpectedDecision = -1;
}

int main(void)
{
    unsigned d, t;
    char label[64];

    /* Each reach uses a Walk time of its own speed tier. */
    for (d = 2; d <= 4; d++) {
        u8 fpt = d == 2 ? 6 : d == 3 ? 4 : 2;

        Clear();
        snprintf(label, sizeof(label), "open-%u", d);
        Plan(label, 1, d, d, 1, fpt, 1, 0, (u8)d);
        for (t = 1; t < d; t++) {
            Clear();
            sBlocked[10][4 + t] = 1;
            snprintf(label, sizeof(label), "wall-%u-%u", d, t);
            Plan(label, 1, d, d, 1, fpt, 1, 0, (u8)d);
            Clear();
            sObject[10][4 + t] = 1;
            snprintf(label, sizeof(label), "object-%u-%u", d, t);
            Plan(label, 1, d, d, 1, fpt, 1, 0, (u8)d);
        }
    }
    /* Long reaches: six tiles at three frames, eight at two. */
    for (d = 6; d <= 8; d += 2) {
        u8 fpt = d == 6 ? 3 : 2;
        Clear();
        snprintf(label, sizeof(label), "open-%u", d);
        Plan(label, 1, d, d, 1, fpt, 1, 0, (u8)d);
        for (t = 1; t < d; t++) {
            Clear();
            sBlocked[10][4 + t] = 1;
            snprintf(label, sizeof(label), "wall-%u-%u", d, t);
            Plan(label, 1, d, d, 1, fpt, 1, 0, (u8)d);
        }
    }
    /* Ledge tile 56 (east downhill) east of the start. Stock ledge tiles
     * also carry collision. */
    Clear();
    sBehavior[10][5] = 56;
    sBlocked[10][5] = 1;
    Plan("ledge-downhill", 1, 2, 2, 1, 4, 1, 0, 2);
    Clear();
    sBehavior[10][5] = 57;
    sBlocked[10][5] = 1;
    Plan("ledge-uphill", 1, 2, 2, 1, 4, 1, 0, 2);
    Plan("ledge-uphill-both", 1, 2, 2, 2, 4, 1, 0, 2);
    /* Lanes outside the Jump model keep the old open-cell skip. */
    Clear();
    sBlocked[10][5] = 1;
    Plan("no-jump-wall", 0, 2, 2, 1, 4, 1, 0, 2);
    Plan("range-lane-wall", 1, 1, 6, 1, 4, 1, 0, 2);
    /* A diagonal Jump crosses a wall on its first diagonal cell. */
    Clear();
    sBlocked[11][5] = 1;
    Plan("diagonal-wall-2", 1, 2, 2, 1, 4, 1, 1, 2);
    /* Route 30 north: a level-3 plateau, its ground-less cliff face, then
     * level-2 ground (one tile = 0x10000). */
    for (d = 2; d <= 3; d++) {
        Clear();
        sBlocked[10][5] = 1;
        sNoGround[10][5] = 1;
        sStartY = 3 << 16;
        sTargetY = 2 << 16;
        snprintf(label, sizeof(label), "cliff-down-%u", d);
        Plan(label, 1, d, d, 1, 6, 1, 0, (u8)d);
    }
    /* Route 30 rows 288-289: a two-tile cliff face from level 5 to 3. */
    Clear();
    sBlocked[10][5] = sBlocked[10][6] = 1;
    sNoGround[10][5] = sNoGround[10][6] = 1;
    sStartY = 5 << 16;
    sTargetY = 3 << 16;
    Plan("cliff-thick-down-3", 1, 3, 3, 1, 5, 1, 0, 3);
    Clear();
    sBlocked[10][5] = 1;
    sStartY = 3 << 16;
    sTargetY = 2 << 16;
    Plan("tree-down-2", 1, 2, 2, 1, 6, 1, 0, 2);
    Clear();
    sBlocked[10][5] = 1;
    sNoGround[10][5] = 1;
    sStartY = sTargetY = 2 << 16;
    Plan("cliff-level-2", 1, 2, 2, 1, 6, 1, 0, 2);
    /* A ranged Hop must clear the native treetop. Exact Jump keeps its
     * separate capped model for the grounded tree. */
    Clear();
    sBlocked[10][5] = 1;
    sCanopy[10][5] = 1;
    Plan("canopy-range-hop-3", 0, 1, 6, 1, 4, 1, 0, 3);
    Clear();
    sBlocked[10][6] = 1;
    sCanopy[10][6] = 1;
    Plan("canopy-jump-4-2", 1, 4, 4, 1, 2, 1, 0, 4);
    Clear();
    sBlocked[10][5] = sCanopy[10][5] = 1;
    Plan("canopy-enabled-range-3", 1, 1, 6, 1, 7, 1, 0, 3);
    Clear();
    sBlocked[15][9] = sCanopy[15][9] = 1;
    Plan("canopy-diagonal-late-6", 1, 1, 6, 1, 7, 1, 1, 6);
    Clear();
    sBlocked[10][6] = sCanopy[10][6] = 1;
    sCanopyHeight[10][6] = 0x100000;
    Plan("canopy-too-high", 1, 1, 6, 1, 7, 1, 0, 6);
    Clear();
    sGroundHeight[10][6] = 24 << 12;
    Plan("native-ridge", 1, 1, 6, 1, 7, 1, 0, 6);
    Plan("native-ridge-disabled", 0, 1, 6, 1, 7, 1, 0, 6);
    Clear();
    sNativeGround[10][5] = 1;
    sGroundHeight[10][5] = 12 << 12;
    Plan("native-ground-hit", 1, 1, 6, 1, 7, 1, 0, 3);
    Clear();
    sCanopy[10][6] = sNoGround[10][6] = 1;
    sStrictHeight = 1;
    sExpectedDecision = OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    Plan("canopy-missing-height", 1, 1, 6, 1, 7, 1, 0, 6);
    Clear();
    sNoGround[10][6] = 1;
    sStrictHeight = 1;
    sExpectedDecision = OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    Plan("native-missing-height", 1, 1, 6, 1, 7, 1, 0, 6);
    /* The destination support belongs to the landing owner, not the
     * crossed-cell reducer. The adjacent T78 landing remains legal. */
    Clear();
    sCanopy[10][10] = 1;
    Plan("destination-canopy", 1, 1, 6, 1, 7, 1, 0, 6);
    Clear();
    sCanopy[10][5] = 1;
    Plan("adjacent-canopy", 1, 1, 6, 1, 7, 1, 0, 1);
    return 0;
}

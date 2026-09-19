/* Inserted into the existing engine-shell fixture. Planner, Wild trajectory
 * wrapper, and Timed caller are real production bodies. World queries and
 * Actor request transport are host stubs, not real map or DS ABI evidence.
 */
/* @TYPES@ */
typedef struct OverworldWildSurfaceHit { s32 height; u16 surfaceId; } OverworldWildSurfaceHit;
static s32 fixtureObstacle;
static unsigned surfaceQueries, vectorCalls;
static u32 returnedTrajectory;
static u8 observedOperation;

/* @TRAJECTORY@ */
/* @ARC@ */
static const struct {
    u32 (*calculateJumpTrajectory)(u8, u8, s32, u16);
    s32 (*calculateJumpArc)(u16, u16, u8);
} surfaceEntry = {OverworldWildBehavior_CalculateJumpTrajectory, OverworldWildBehavior_CalculateJumpArc};
#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY (&surfaceEntry)

static BOOL QuerySurface(FieldSystem *field, const OverworldWildSurfaceCatalog *catalog,
    int x, int y, OverworldWildSurfaceHit *hit)
{
    (void)field; (void)catalog;
    surfaceQueries++;
    if (x != 1 || y != 0) return FALSE;
    hit->height = fixtureObstacle;
    hit->surfaceId = 1;
    return TRUE;
}
static s32 GroundBaseY(FieldSystem *field, const OverworldWildSurfaceCatalog *catalog,
    LocalMapObject *object, int x, int y)
{ (void)field; (void)catalog; (void)object; (void)x; (void)y; return 0; }
static const struct {
    BOOL (*querySurface)(FieldSystem *, const OverworldWildSurfaceCatalog *, int, int, OverworldWildSurfaceHit *);
    s32 (*getGroundBaseY)(FieldSystem *, const OverworldWildSurfaceCatalog *, LocalMapObject *, int, int);
} runtimeEntry = {QuerySurface, GroundBaseY};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
/* @LERP@ */
/* Preserve the production mixed-sign comparison unchanged. Both operands are
 * positive on this path; the ARM build permits this existing source warning. */
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
/* @PLAN@ */
#pragma GCC diagnostic pop
static OverworldMotionDecision OverworldActorHopPlanner_PlanVector(OverworldActorHopPlanCall *call)
{ (void)call; vectorCalls++; return OVERWORLD_MOTION_DECISION_PROFILE; }
/* @DISPATCH@ */
static OverworldMotionDecision OverworldWildSpawns_RequestHopPlan(OverworldActorHopPlanCall *call)
{
    OverworldMotionDecision decision;
    observedOperation = call->operation;
    decision = OverworldActorHopPlanner_PlanImpl(call);
    returnedTrajectory = call->trajectory;
    return decision;
}
/* @WRAPPER@ */
/* @DRIVER@ */
static unsigned failures;
#undef CHECK
#define CHECK(expression) do { assertions++; if (!(expression)) { \
    fprintf(stderr, "flat Reposition invariant failed: %s, line %d: %s\n", caseName, __LINE__, #expression); \
    failures++; } } while (0)

static void RunClearanceCaseTimed(const char *name, BOOL flat, s32 obstacle,
    u8 allowLift, BOOL expectStart, u8 hopTime, u8 flatDuration)
{
    OverworldWildSpawnState state = {0};
    FieldSystem field = {0};
    LocalMapObject object = {.flags = 1, .movementCommand = 255};
    OverworldWildBehaviorProfile profile = {0};
    BOOL result;
    caseName = name;
    inspectOkay = trajectoryOkay = prepOkay = requestOkay = TRUE;
    shellStarts = prepareCalls = restoreCalls = beginCalls = taskCalls = 0;
    shellBeforeAdmission = soundBeforeAdmission = surfaceQueries = vectorCalls = 0;
    returnedTrajectory = 0;
    observedOperation = 255;
    fixtureObstacle = obstacle;
    admitted = sOverworldWildSpawnHopPreparing = FALSE;
    selectedPolicy = (OverworldActorPolicyView){.actorActive = TRUE, .chainPauseTicks = flatDuration,
        /* Match BEGIN: the grid marker is installed before the first request.
         * The pending remaining count alone does not select Reposition. */
        .chainPauseAction = flat ? OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER : 0,
        .chainStepsRemaining = flat ? OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING
            | OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID | 1 : 0};
    memset(&motion, 0, sizeof(motion));
    profile.lane.hopTime = hopTime;
    profile.lane.hopElevationTimeScale = 100;
    profile.lane.hopElevationArcScale = 0;
    profile.lane.hopAllowVerticalObstacles = allowLift;
    result = OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
        &state, &field, 0, &object, 3, 2, 2, 0, &profile, flat, 8)
        == OVERWORLD_MOTION_DECISION_ACCEPTED;
    cases++;
    printf("case %s: start=%d, plannerArc=%u, executedArc=%u, queries=%u, operation=%u\n",
        name, result, (unsigned)(returnedTrajectory >> 16),
        state.runtime.movementCustomJumpArcHeightsQ4[0], surfaceQueries, observedOperation);
    CHECK(surfaceQueries > 0 && vectorCalls == 0);
    CHECK(result == expectStart);
    if (expectStart) {
        CHECK(shellStarts == 1 && beginCalls == 1 && admitted);
        CHECK((returnedTrajectory >> 16) == state.runtime.movementCustomJumpArcHeightsQ4[0]);
        CHECK(motion.plan.arcHeightQ4 == state.runtime.movementCustomJumpArcHeightsQ4[0]);
        if (flat) {
            CHECK(motion.plan.arcHeightQ4 == 0 && motion.plan.duration == flatDuration);
        } else {
            CHECK(motion.plan.arcHeightQ4 >= 16 && motion.plan.duration == 14);
        }
    } else {
        CHECK(shellStarts == 0 && beginCalls == 0 && !admitted);
        CHECK(state.movementInProgressMask == 0 && !MapObject_IsSingleMovementActive(&object));
    }
}

static void RunClearanceCase(const char *name, BOOL flat, s32 obstacle,
    u8 allowLift, BOOL expectStart)
{
    RunClearanceCaseTimed(name, flat, obstacle, allowLift, expectStart, 8, 8);
}

int main(void)
{
    RunClearanceCase("flat skid must reject low obstacle", TRUE, 4096, 0, FALSE);
    RunClearanceCase("Hop clears the same low obstacle", FALSE, 4096, 0, TRUE);
    RunClearanceCase("flat clear route remains flat", TRUE, 0, 0, TRUE);
    RunClearanceCase("flat never auto-lifts", TRUE, 32 * 4096, 1, FALSE);
    RunClearanceCase("Hop can auto-lift when allowed", FALSE, 32 * 4096, 1, TRUE);
    RunClearanceCase("Hop rejects high obstacle without lift", FALSE, 32 * 4096, 0, FALSE);
    RunClearanceCaseTimed("flat obstacle with Hop time zero", TRUE, 4096, 0, FALSE, 0, 1);
    RunClearanceCaseTimed("flat clear with Hop time zero", TRUE, 0, 0, TRUE, 0, 1);
    RunClearanceCaseTimed("flat obstacle with Hop time one", TRUE, 4096, 0, FALSE, 1, 1);
    RunClearanceCaseTimed("flat clear with Hop time one", TRUE, 0, 0, TRUE, 1, 1);
    RunClearanceCaseTimed("zero-duration input still checks clearance", TRUE, 4096, 0, FALSE, 0, 0);
    printf("flat Reposition clearance: %u cases, %u assertions, %u failures\n", cases, assertions, failures);
    return failures ? 1 : 0;
}

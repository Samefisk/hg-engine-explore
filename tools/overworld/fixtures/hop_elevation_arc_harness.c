/* The runner inserts unedited production helper bodies. Zero-scale expectations
 * come from the authored field contract: 0 retains the base level-Hop arc.
 * Positive-scale comparisons preserve the deployed pre-fix arithmetic. This
 * does not prove the ROM planner, live object attachment, or ARM memory layout.
 */
#include "overworld_motion_model.h"
#include <stdio.h>
#include <string.h>

/* @CONSTANTS@ */
/* @TRAJECTORY@ */
/* @ARC@ */

static unsigned checks;
static unsigned failures;
static void Check(int condition, const char *label)
{
    checks++;
    if (!condition) {
        if (failures < 20) fprintf(stderr, "Hop arc invariant failed: %s\n", label);
        failures++;
    }
}

/* Fixed observations, not values obtained from the function under test. */
static void CheckVectors(void)
{
    static const struct {
        u8 frames, distance, timeScale, arcScale;
        s32 elevation;
        u16 duration;
        u8 arc;
    } cases[] = {
        {8, 1, 100, 0, 0, 8, 16},
        {8, 16, 100, 0, 0, 98, 16}, /* Natural Ledyba off-screen Hop. */
        {8, 1, 100, 0, 16 * 4096, 16, 16},
        {8, 1, 100, 0, -16 * 4096, 16, 16},
        {8, 1, 100, 100, 0, 8, 16},
        {8, 1, 100, 100, 16 * 4096, 16, 24},
        {8, 1, 100, 100, -16 * 4096, 16, 24},
        {8, 1, 100, 50, 16 * 4096, 16, 20},
        {8, 1, 100, 150, 32 * 4096, 24, 40},
        {8, 1, 0, 100, 16 * 4096, 8, 24},
        {7, 4, 100, 100, 0, 25, 16},
        {8, 1, 100, 50, 12 * 4096 + 2048, 14, 19},
        {8, 1, 100, 255, 1024 * 4096, 520, 255},
        {255, 255, 255, 255, 65535 * 4096, 65535, 255},
    };
    unsigned i;
    for (i = 0; i < sizeof(cases) / sizeof(*cases); i++) {
        u32 result = OverworldWildBehavior_CalculateJumpTrajectory(
            cases[i].frames, cases[i].distance, cases[i].elevation,
            cases[i].timeScale | ((u16)cases[i].arcScale << 8));
        Check((result & 0xFFFF) == cases[i].duration, "fixed duration vector");
        Check((result >> 16) == cases[i].arc, "fixed arc vector (zero retains base 16)");
    }
}

static void CheckNonzeroReference(void)
{
    static const u8 frames[] = {1, 2, 7, 8, 32, 255};
    static const u8 distances[] = {1, 2, 6, 16, 32, 255};
    static const u8 timeScales[] = {0, 1, 30, 100, 150, 255};
    static const s32 heights[] = {0, 1, 15, 16, 32, 1024, 65535};
    unsigned f, d, t, h, scale;
    for (f = 0; f < sizeof(frames); f++)
    for (d = 0; d < sizeof(distances); d++)
    for (t = 0; t < sizeof(timeScales); t++)
    for (h = 0; h < sizeof(heights) / sizeof(*heights); h++)
    for (scale = 1; scale <= 255; scale++) {
        u32 duration = frames[f] + (u32)(distances[d] - 1)
            * (frames[f] - (frames[f] >> 2));
        u32 arc = 16 + (u32)heights[h] * scale / 200;
        u32 result, expected;
        duration += (u32)heights[h] * frames[f] * timeScales[t] / 1600;
        if (duration > 65535) duration = 65535;
        if (arc > 255) arc = 255;
        expected = (arc << 16) | duration;
        result = OverworldWildBehavior_CalculateJumpTrajectory(
            frames[f], distances[d], heights[h] * 4096,
            timeScales[t] | (scale << 8));
        Check(result == expected, "nonzero scales preserve deployed arithmetic");
        result = OverworldWildBehavior_CalculateJumpTrajectory(
            frames[f], distances[d], -heights[h] * 4096,
            timeScales[t] | (scale << 8));
        Check(result == expected, "ascent and descent retain equal scaling");
    }
}

static void CheckActualMotion(void)
{
    static const s32 heights[] = {0, 16 * 4096, -16 * 4096};
    unsigned i;
    for (i = 0; i < sizeof(heights) / sizeof(*heights); i++) {
        OverworldMotionIntent intent = {0};
        OverworldMotionCandidate candidate = {0};
        OverworldMotionPlan plan;
        OverworldMotionState state;
        OverworldMotionSample sample;
        u32 trajectory = OverworldWildBehavior_CalculateJumpTrajectory(8, 16, heights[i], 100);
        u16 frame, duration = trajectory & 0xFFFF;
        s32 peak = 0;
        intent.version = OVERWORLD_MOTION_MODEL_VERSION;
        intent.kind = OVERWORLD_MOTION_KIND_HOP;
        intent.duration = duration;
        intent.fieldEpoch = 7;
        intent.facing = 3;
        intent.arcHeightQ4 = trajectory >> 16;
        intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
        intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NORMAL;
        candidate.targetX = 16;
        candidate.targetBaseY = heights[i];
        candidate.distance = 16;
        OverworldMotion_Reset(&state);
        Check(OverworldMotion_SelectPlan(&intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED, "real motion accepts trajectory");
        Check(OverworldMotion_Begin(&state, &plan) == OVERWORLD_MOTION_DECISION_ACCEPTED,
            "real motion begins");
        Check(OverworldWildBehavior_CalculateJumpArc(0, duration, intent.arcHeightQ4) == 0,
            "arc begins at base");
        for (frame = 1; frame <= duration; frame++) {
            (void)OverworldMotion_Tick(&state, 7, &sample);
            Check(sample.heightOffset == OverworldWildBehavior_CalculateJumpArc(
                frame, duration, intent.arcHeightQ4), "helper and real renderer agree each frame");
            if (sample.heightOffset > peak) peak = sample.heightOffset;
        }
        Check(peak == 16 * 4096, "zero-scale Hop retains positive base apex");
        Check(sample.heightOffset == 0 && sample.renderY == heights[i], "Hop lands at target base");
        Check(OverworldMotion_AcknowledgeCommit(&state, 7) == OVERWORLD_MOTION_DECISION_ACCEPTED
            && state.commitSequence == 1, "one terminal commit");
    }
}

int main(void)
{
    CheckVectors();
    CheckNonzeroReference();
    CheckActualMotion();
    printf("Hop elevation arc: %u checks, %u failures\n", checks, failures);
    return failures ? 1 : 0;
}

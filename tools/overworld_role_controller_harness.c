#include "overworld_role_controller.h"

#include <stdio.h>
#include <string.h>

static int sFailures;

#define CHECK(condition, label) \
    do { \
        if (!(condition)) { \
            fprintf(stderr, "FAIL: %s\n", label); \
            sFailures++; \
        } \
    } while (0)

static OverworldRoleControllerInput MakeInput(u8 role, u8 event)
{
    OverworldRoleControllerInput input;

    memset(&input, 0, sizeof(input));
    input.version = OVERWORLD_ROLE_CONTROLLER_VERSION;
    input.size = sizeof(input);
    input.role = role;
    input.event = event;
    input.requestedDirection = 3;
    input.committedDirection = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
    return input;
}

static void CheckRoleIntentSources(void)
{
    OverworldRoleControllerOutput output;
    u8 intent;
    u8 role;

    for (role = OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
         role <= OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
         role++) {
        for (intent = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
             intent <= OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE;
             intent++) {
            OverworldRoleControllerInput input = MakeInput(
                role, OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);

            input.intentKind = intent;
            if (intent == OVERWORLD_ROLE_CONTROLLER_INTENT_PAUSE
                || intent == OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE) {
                input.requestedDirection =
                    OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
            }
            OverworldRoleController_Reduce(&input, &output);
            if (intent == OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE
                && role != OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER) {
                CHECK(output.decision
                        == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED
                        && output.intentKind
                            == OVERWORLD_ROLE_CONTROLLER_INTENT_NONE
                        && output.direction
                            == OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE,
                    "only Follower accepts Release");
            } else {
                CHECK(output.decision
                        == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT,
                    "active roles accept their semantic intents");
                CHECK(output.intentKind == input.intentKind
                        && output.direction == input.requestedDirection,
                    "role intent preserves primitive and requested direction");
            }
        }
    }
}

static void CheckRamLockAndCrash(void)
{
    OverworldRoleControllerInput input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    OverworldRoleControllerOutput output;

    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
    input.committedDirection = 1;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
            && output.direction == 1,
        "Ram keeps the actor-owned committed direction");
    CHECK((output.intentFlags
            & (OVERWORLD_ROLE_CONTROLLER_INTENT_LOCK_DIRECTION
                | OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED))
            == (OVERWORLD_ROLE_CONTROLLER_INTENT_LOCK_DIRECTION
                | OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED),
        "Ram is a locked Walk with blocked crash reaction");

    input.event = OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.terminalKind == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH,
        "Ram emits a normal crash on blocked terrain");
    input.flags |= OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE
        | OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.terminalKind
            == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH_BATTLE,
        "Ram emits a battle crash only for an eligible actor target");

    input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM
        | OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
    input.committedDirection = 6;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.direction == 6
            && (output.intentFlags
                & OVERWORLD_ROLE_CONTROLLER_INTENT_LOCK_DIRECTION) != 0,
        "Mounted Ram uses the same actor-owned direction lock");
    CHECK((output.intentFlags
            & OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN) == 0,
        "Mounted Ram cannot inherit Wild AI chain actions");
}

static void CheckChainTerminalOwnership(void)
{
    OverworldRoleControllerOutput output;
    u8 role;

    for (role = OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
         role <= OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
         role++) {
        OverworldRoleControllerInput input = MakeInput(
            role, OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT);

        input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
        input.chainAction = 2;
        input.chainTicks = 9;
        OverworldRoleController_Reduce(&input, &output);
        if (role == OVERWORLD_ROLE_CONTROLLER_ROLE_WILD
            || role == OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER) {
            CHECK(output.decision
                    == OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL
                    && output.terminalKind
                        == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CHAIN
                    && output.terminalAction == 2
                    && output.terminalTicks == 9,
                "Wild and Follower consume shared chain terminal output");
        } else {
            CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_NONE,
                "Mounted role does not inherit AI chains");
        }
    }

    {
        OverworldRoleControllerInput invalid = MakeInput(
            OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
            OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT);

        invalid.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
        invalid.chainAction = OVERWORLD_ROLE_CONTROLLER_CHAIN_ACTION_MAX + 1;
        OverworldRoleController_Reduce(&invalid, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_NONE,
            "unknown chain actions cannot escape the controller seam");
    }
}

static void CheckRejectedInputs(void)
{
    OverworldRoleControllerInput input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    OverworldRoleControllerOutput output;

    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
    input.requestedDirection = 8;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "invalid direction is rejected");
    input.requestedDirection = 2;
    input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "Ram cannot silently change into a different primitive");

    input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    input.version++;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "unknown interface versions are rejected");
    input.version = OVERWORLD_ROLE_CONTROLLER_VERSION;
    input.size--;
    memset(&output, 0xA5, sizeof(output));
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "truncated interface values are rejected");
    CHECK(output.version == OVERWORLD_ROLE_CONTROLLER_VERSION
            && output.size == sizeof(output)
            && output.intentKind == OVERWORLD_ROLE_CONTROLLER_INTENT_NONE
            && output.direction
                == OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
            && output.intentFlags == 0
            && output.terminalKind
                == OVERWORLD_ROLE_CONTROLLER_TERMINAL_NONE,
        "rejected input fully replaces stale output bytes");
}

static void CheckSingleFieldMutations(void)
{
    OverworldRoleControllerInput baseline = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    OverworldRoleControllerInput input;
    OverworldRoleControllerOutput output;
    u8 intent;

    baseline.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;

    input = baseline;
    input.role = 0;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "role below the ABI range is rejected");

    input = baseline;
    input.role = OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED + 1;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "role immediately above the active ABI range is rejected");

    input = baseline;
    input.role = 0xFF;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "role above the ABI range is rejected");

    input = baseline;
    input.event = 0;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "event below the ABI range is rejected");

    input = baseline;
    input.event = OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED + 1;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "event above the ABI range is rejected");

    input = baseline;
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_NONE;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "empty request intent is rejected");

    input = baseline;
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE + 1;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "request intent above the ABI range is rejected");

    for (intent = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
         intent <= OVERWORLD_ROLE_CONTROLLER_INTENT_LOOK;
         intent++) {
        input = baseline;
        input.intentKind = intent;
        input.requestedDirection =
            OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX + 1;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision
                == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
            "each directional intent rejects an invalid direction");
    }

    input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE;
    input.requestedDirection = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
            && output.intentKind
                == OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE,
        "Follower Release does not require a movement direction");

    input.role = OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "Wild cannot request Follower Release");

    input.role = OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
        "Mounted cannot request Follower Release");
}

static void CheckEventIsolationMutations(void)
{
    OverworldRoleControllerInput input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED);
    OverworldRoleControllerOutput output;

    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_NONE,
        "blocked Walk without Ram does not publish a terminal");

    input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE
        | OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_NONE,
        "battle flags without Ram do not publish a crash");

    input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT);
    input.chainAction = OVERWORLD_ROLE_CONTROLLER_CHAIN_LOOK_AROUND;
    input.chainTicks = 5;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_NONE,
        "chain action without the chain flag is not consumed");

    input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
    input.chainAction = OVERWORLD_ROLE_CONTROLLER_CHAIN_NONE;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_NONE,
        "empty chain action does not publish a terminal");

    input = MakeInput(
        OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED,
        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);
    input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
    input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
    input.committedDirection = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
    OverworldRoleController_Reduce(&input, &output);
    CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
            && output.direction == input.requestedDirection,
        "Ram with no committed direction keeps the requested direction");
}

static void CheckOptionalDirectionSemantics(void)
{
    OverworldRoleControllerOutput output;
    u8 intent;
    u8 role;

    for (role = OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
         role <= OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER;
         role++) {
        for (intent = OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
             intent <= OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT;
             intent++) {
            OverworldRoleControllerInput input = MakeInput(
                role, OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);

            input.intentKind = intent;
            input.requestedDirection =
                OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
            OverworldRoleController_Reduce(&input, &output);
            CHECK(output.decision
                    == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
                "directionless motion needs an explicit optional request");

            input.flags =
                OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL
                | OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
            OverworldRoleController_Reduce(&input, &output);
            CHECK(output.decision
                    == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
                    && output.intentKind == intent
                    && output.direction
                        == OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE,
                "Wild and Follower can defer Hop or Teleport direction");
            CHECK((output.intentFlags
                    & OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN) != 0,
                "Wild and Follower Hop or Teleport keep chain eligibility");
        }
    }

    {
        OverworldRoleControllerInput input = MakeInput(
            OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
            OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);

        input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
        input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL;
        input.requestedDirection =
            OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
            "Walk cannot defer its requested direction");

        input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
        input.requestedDirection =
            OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX + 1;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
            "optional direction accepts only the explicit none value");

        input.role = OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
        input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
        input.requestedDirection =
            OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED,
            "Mounted Hop needs current rider direction");

        input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT;
        input.requestedDirection = 2;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
                && output.direction == 2,
            "a concrete Mounted direction cannot become deferred");
    }
}

static void CheckMountedMotionOutcomes(void)
{
    OverworldRoleControllerOutput output;
    u8 intent;

    for (intent = OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
         intent <= OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT;
         intent++) {
        OverworldRoleControllerInput input = MakeInput(
            OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED,
            OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST);

        input.intentKind = intent;
        input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT
                && output.intentKind == intent
                && output.direction == input.requestedDirection,
            "Mounted Hop and Teleport keep current rider direction");
        CHECK((output.intentFlags
                & OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN) == 0,
            "Mounted Hop and Teleport cannot inherit AI chains");
    }

    {
        OverworldRoleControllerInput input = MakeInput(
            OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED,
            OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED);

        input.intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_WALK;
        input.flags = OVERWORLD_ROLE_CONTROLLER_INPUT_RAM
            | OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED
            | OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE
            | OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR;
        OverworldRoleController_Reduce(&input, &output);
        CHECK(output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL
                && output.terminalKind
                    == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH,
            "Mounted Ram blocked terminal is a normal crash");
        CHECK(output.terminalAction == OVERWORLD_ROLE_CONTROLLER_CHAIN_NONE
                && output.terminalTicks == 0,
            "Mounted Ram crash cannot publish an AI chain payload");
    }
}

int main(void)
{
    CheckRoleIntentSources();
    CheckRamLockAndCrash();
    CheckChainTerminalOwnership();
    CheckRejectedInputs();
    CheckSingleFieldMutations();
    CheckEventIsolationMutations();
    CheckOptionalDirectionSemantics();
    CheckMountedMotionOutcomes();
    if (sFailures != 0) {
        fprintf(stderr, "%d role-controller checks failed\n", sFailures);
        return 1;
    }
    puts("overworld role-controller checks passed");
    return 0;
}

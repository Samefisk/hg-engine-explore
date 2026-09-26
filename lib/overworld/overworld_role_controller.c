#include "overworld_role_controller.h"

#ifdef OVERWORLD_ROLE_CONTROLLER_HOST
#include <string.h>
#endif

static u8 OverworldRoleController_IsRoleValid(u8 role)
{
    return role >= OVERWORLD_ROLE_CONTROLLER_ROLE_WILD
        && role <= OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
}

static u8 OverworldRoleController_RoleUsesChain(u8 role)
{
    return role == OVERWORLD_ROLE_CONTROLLER_ROLE_WILD
        || role == OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER
        || role == OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
}

void OverworldRoleController_Reduce(
    const OverworldRoleControllerInput *input,
    OverworldRoleControllerOutput *output)
{
    if (output == NULL) {
        return;
    }
    memset(output, 0, sizeof(*output));
    output->version = OVERWORLD_ROLE_CONTROLLER_VERSION;
    output->size = sizeof(*output);
    output->direction = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
    if (input == NULL
        || input->version != OVERWORLD_ROLE_CONTROLLER_VERSION
        || input->size != sizeof(*input)
        || !OverworldRoleController_IsRoleValid(input->role)) {
        output->decision = OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED;
        return;
    }

    if (input->event == OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT) {
        if ((input->flags & OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED) != 0
            && OverworldRoleController_RoleUsesChain(input->role)
            && input->chainAction != OVERWORLD_ROLE_CONTROLLER_CHAIN_NONE
            && input->chainAction
                <= OVERWORLD_ROLE_CONTROLLER_CHAIN_ACTION_MAX) {
            output->decision = OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL;
            output->terminalKind = OVERWORLD_ROLE_CONTROLLER_TERMINAL_CHAIN;
            output->terminalAction = input->chainAction;
            output->terminalTicks = input->chainTicks;
        }
        return;
    }

    if (input->event == OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED) {
        if ((input->flags & OVERWORLD_ROLE_CONTROLLER_INPUT_RAM) != 0) {
            output->decision = OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL;
            if (input->role != OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED
                && (input->flags
                    & (OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE
                        | OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR))
                    == (OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE
                        | OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR)) {
                output->terminalKind =
                    OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH_BATTLE;
            } else {
                output->terminalKind =
                    OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH;
            }
        }
        return;
    }

    if (input->event != OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST
        || input->intentKind == OVERWORLD_ROLE_CONTROLLER_INTENT_NONE
        || input->intentKind > OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE
        || (input->intentKind == OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE
            && input->role != OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER)
        || (input->intentKind <= OVERWORLD_ROLE_CONTROLLER_INTENT_LOOK
            && input->requestedDirection
                > OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX
            && (input->requestedDirection
                    != OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                || (input->flags
                        & OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL)
                    == 0
                || input->role == OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED
                || (u8)(input->intentKind
                        - OVERWORLD_ROLE_CONTROLLER_INTENT_HOP) > 1))) {
        output->decision = OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED;
        return;
    }

    output->decision = OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT;
    output->intentKind = input->intentKind;
    output->direction = input->requestedDirection;
    if ((input->flags & OVERWORLD_ROLE_CONTROLLER_INPUT_RAM) != 0) {
        if (input->intentKind != OVERWORLD_ROLE_CONTROLLER_INTENT_WALK) {
            output->decision = OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED;
            output->intentKind = OVERWORLD_ROLE_CONTROLLER_INTENT_NONE;
            output->direction = OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;
            return;
        }
        if (input->committedDirection
            <= OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX) {
            output->direction = input->committedDirection;
        }
        output->intentFlags |= OVERWORLD_ROLE_CONTROLLER_INTENT_LOCK_DIRECTION
            | OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED;
    }
    if ((input->flags & OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED) != 0
        && OverworldRoleController_RoleUsesChain(input->role)) {
        output->intentFlags |= OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN;
    }
}

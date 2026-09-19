#ifndef OVERWORLD_ROLE_CONTROLLER_H
#define OVERWORLD_ROLE_CONTROLLER_H

#ifdef OVERWORLD_ROLE_CONTROLLER_HOST
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
#else
#include "types.h"
#endif

/*
 * Pointer-free role decisions shared by the field adapters and host proofs.
 * The controller selects semantic intent. Collision, coordinates, engine
 * commands, actor commits, and presentation stay outside this interface.
 */

#define OVERWORLD_ROLE_CONTROLLER_VERSION 1

typedef enum OverworldRoleControllerRole {
    OVERWORLD_ROLE_CONTROLLER_ROLE_WILD = 1,
    OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER = 2,
    OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED = 3,
} OverworldRoleControllerRole;

typedef enum OverworldRoleControllerEvent {
    OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST = 1,
    OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT = 2,
    OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED = 3,
} OverworldRoleControllerEvent;

typedef enum OverworldRoleControllerIntentKind {
    OVERWORLD_ROLE_CONTROLLER_INTENT_NONE = 0,
    OVERWORLD_ROLE_CONTROLLER_INTENT_WALK = 1,
    OVERWORLD_ROLE_CONTROLLER_INTENT_HOP = 2,
    OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT = 3,
    OVERWORLD_ROLE_CONTROLLER_INTENT_LOOK = 4,
    OVERWORLD_ROLE_CONTROLLER_INTENT_PAUSE = 5,
    OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE = 6,
} OverworldRoleControllerIntentKind;

typedef enum OverworldRoleControllerDecision {
    OVERWORLD_ROLE_CONTROLLER_DECISION_NONE = 0,
    OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT = 1,
    OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL = 2,
    OVERWORLD_ROLE_CONTROLLER_DECISION_REJECTED = 3,
} OverworldRoleControllerDecision;

typedef enum OverworldRoleControllerTerminalKind {
    OVERWORLD_ROLE_CONTROLLER_TERMINAL_NONE = 0,
    OVERWORLD_ROLE_CONTROLLER_TERMINAL_CHAIN = 1,
    OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH = 2,
    OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH_BATTLE = 3,
} OverworldRoleControllerTerminalKind;

/* These are semantic terminal actions, not engine movement commands. */
typedef enum OverworldRoleControllerChainAction {
    OVERWORLD_ROLE_CONTROLLER_CHAIN_NONE = 0,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_HOP_IN_PLACE = 1,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_LOOK_AROUND = 2,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_REPOSITION_JUMPS = 3,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_REPOSITION_STEPS = 4,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_REPOSITION_SKIDS = 5,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_PAUSE = 6,
    OVERWORLD_ROLE_CONTROLLER_CHAIN_HOP_FORWARD = 7,
} OverworldRoleControllerChainAction;

#define OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE 0xFF
#define OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX 7
#define OVERWORLD_ROLE_CONTROLLER_CHAIN_ACTION_MAX \
    OVERWORLD_ROLE_CONTROLLER_CHAIN_HOP_FORWARD

#define OVERWORLD_ROLE_CONTROLLER_INPUT_RAM              (1u << 0)
#define OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED    (1u << 1)
#define OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE (1u << 2)
#define OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR (1u << 3)
#define OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL (1u << 4)

#define OVERWORLD_ROLE_CONTROLLER_INTENT_LOCK_DIRECTION   (1u << 0)
#define OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN     (1u << 1)
#define OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED (1u << 2)

typedef struct OverworldRoleControllerInput {
    u16 version;
    u16 size;
    u8 role;
    u8 event;
    u8 intentKind;
    u8 requestedDirection;
    u8 committedDirection;
    u8 flags;
    u8 chainAction;
    u8 chainTicks;
} OverworldRoleControllerInput;

typedef struct OverworldRoleControllerOutput {
    u16 version;
    u16 size;
    u8 decision;
    u8 intentKind;
    u8 direction;
    u8 intentFlags;
    u8 terminalKind;
    u8 terminalAction;
    u8 terminalTicks;
    u8 reserved;
} OverworldRoleControllerOutput;

typedef char OverworldRoleControllerInputSizeMustRemain12Bytes[
    sizeof(OverworldRoleControllerInput) == 12 ? 1 : -1];
typedef char OverworldRoleControllerOutputSizeMustRemain12Bytes[
    sizeof(OverworldRoleControllerOutput) == 12 ? 1 : -1];

void OverworldRoleController_Reduce(
    const OverworldRoleControllerInput *input,
    OverworldRoleControllerOutput *output);

#endif // OVERWORLD_ROLE_CONTROLLER_H

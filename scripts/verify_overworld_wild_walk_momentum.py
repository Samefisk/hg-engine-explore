#!/usr/bin/env python3
"""Verify exact-frame wild Walk motion and shared momentum rules."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

from verify_overworld_role_controller import packed_role_path_errors


REPO = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str) -> str:
    search_name = name.rstrip("(").rstrip()
    start = -1
    while True:
        match = re.search(
            rf"\b{re.escape(search_name)}\s*\(",
            source[start + 1:],
        )
        if match is None:
            raise ValueError(f"missing function body: {name}")
        start += 1 + match.start()
        line_start = source.rfind("\n", 0, start) + 1
        declaration_prefix = source[line_start:start]
        if declaration_prefix and not any(
            token in declaration_prefix
            for token in ("static", "BOOL", "u8", "void")
        ):
            continue
        opening = source.find("{", start)
        declaration = source.find(";", start)
        if opening >= 0 and (declaration < 0 or opening < declaration):
            break
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise ValueError(f"unterminated body: {name}")


def require(source: str, values: tuple[str, ...], label: str) -> None:
    missing = [value for value in values if value not in source]
    if missing:
        raise SystemExit(f"{label} is incomplete: {', '.join(missing)}")


def reject(source: str, values: tuple[str, ...], label: str) -> None:
    found = [value for value in values if value in source]
    if found:
        raise SystemExit(f"{label} still contains: {', '.join(found)}")


def delta_linker_errors(source: str) -> list[str]:
    """Accept exact placement, not one GNU ld spelling of a Thumb symbol."""
    clean = re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.DOTALL)
    errors = []
    for axis, start, end in (("x", "119C", "11BE"), ("y", "11BE", "11E2")):
        name = f"OverworldWalk_Delta{axis.upper()}"
        placement = re.search(
            rf"\.\s*=\s*ORIGIN\(rom\)\s*\+\s*0x{start}\s*;\s*"
            rf"KEEP\(\*\(\.overworld_walk_delta_{axis}\)\)", clean,
        )
        if placement is None:
            errors.append(f"{name}: exact section placement missing")
            continue
        tail = clean[placement.end():]
        next_placement = re.search(r"\.\s*=\s*ORIGIN\(rom\)", tail)
        block = tail[:next_placement.start()] if next_placement else tail
        exact = re.search(rf"ASSERT\(\s*{name}\s*==\s*ORIGIN\(rom\)\s*\+\s*0x{start}\s*,", block)
        thumb = re.search(rf"ASSERT\(\s*DEFINED\({name}\)\s*&&\s*\({name}\s*&\s*1\)\s*==\s*1\s*,", block)
        bound = re.search(rf"ASSERT\(\s*\.\s*<=\s*ORIGIN\(rom\)\s*\+\s*0x{end}\s*,", block)
        if not (exact or thumb) or bound is None:
            errors.append(f"{name}: symbol/Thumb or end-of-slot guard missing")
    return errors


def verify_delta_linker_and_controls(source: str) -> None:
    errors = delta_linker_errors(source)
    if errors:
        raise SystemExit("fixed direct Walk helper linker ABI: " + "; ".join(errors))
    equivalent = source
    for axis, start in (("X", "119C"), ("Y", "11BE")):
        equivalent = equivalent.replace(
            f"DEFINED(OverworldWalk_Delta{axis}) && (OverworldWalk_Delta{axis} & 1) == 1",
            f"OverworldWalk_Delta{axis} == ORIGIN(rom) + 0x{start}")
    if delta_linker_errors(equivalent):
        raise SystemExit("Delta linker guard rejected equivalent exact-address assertions")
    mutations = {
        "moved entry": source.replace(". = ORIGIN(rom) + 0x119C;", ". = ORIGIN(rom) + 0x119E;", 1),
        "wrong section": source.replace("KEEP(*(.overworld_walk_delta_y))", "KEEP(*(.not_walk_delta_y))", 1),
        "missing symbol": source.replace("DEFINED(OverworldWalk_DeltaX)", "DEFINED(NotDeltaX)", 1),
        "wrong mode": source.replace("(OverworldWalk_DeltaY & 1) == 1", "(OverworldWalk_DeltaY & 1) == 0", 1),
        "overlapping slot": source.replace('ASSERT(. <= ORIGIN(rom) + 0x11BE,', 'ASSERT(. <= ORIGIN(rom) + 0x11C0,', 1),
    }
    for label, changed in mutations.items():
        if changed == source or not delta_linker_errors(changed):
            raise SystemExit(f"Delta linker negative control did not reject {label}")


def verify_linked_delta_entries(path: Path) -> None:
    """S2 check: raw ELF function values retain their Thumb bit, including ABS."""
    command = os.environ.get("ARM_NONE_EABI_READELF", "arm-none-eabi-readelf")
    result = subprocess.run([command, "-sW", str(path)], check=True, capture_output=True, text=True)
    entries = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[3] == "FUNC" and parts[-1] in ("OverworldWalk_DeltaX", "OverworldWalk_DeltaY"):
            entries[parts[-1]] = (int(parts[1], 16), int(parts[2]))
    for name, address, maximum in (("OverworldWalk_DeltaX", 0x023BF59D, 34),
                                   ("OverworldWalk_DeltaY", 0x023BF5BF, 36)):
        actual = entries.get(name)
        if actual is None or actual[0] != address or not 0 < actual[1] <= maximum:
            raise SystemExit(f"linked {name} ABI changed: {actual}, expected Thumb entry {address:#x}, size<= {maximum}")
    print("linked DeltaX/DeltaY exact Thumb entry checks passed")


def actor_chain_receipt_errors(actor_source: str, runtime_source: str) -> list[str]:
    """A chain receipt belongs to acknowledged normal actor motion, not Walk."""
    try:
        body = function_body(actor_source, "ActorSystem_TryAcknowledgeMotionCommit")
        commit = function_body(runtime_source, "OverworldActorWalkPolicy_ReduceCommit")
    except ValueError as error:
        return [str(error)]
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", body, flags=re.DOTALL)
    clean = re.sub(r"\s+", "", body)
    receipt = "policy->pendingStep=OVERWORLD_ACTOR_WALK_PENDING_CHAIN;"
    guard = (
        "if(motion->plan.commitPolicy==OVERWORLD_MOTION_COMMIT_NORMAL"
        "&&policy->pendingStep==OVERWORLD_ACTOR_WALK_PENDING_NONE"
        "&&(walkPolicy==NULL||(walkPolicy->stepFlags&OVERWORLD_ACTOR_WALK_STEP_SKID)==0)){"
        + receipt + "}"
    )
    ordered = (
        "walkPolicy->operation!=OVERWORLD_ACTOR_WALK_POLICY_COMMIT",
        "->reduceWalk(walkPolicy)",
        "if(walkPolicy->decision!=OVERWORLD_ACTOR_WALK_POLICY_CONSUMED"
        "&&walkPolicy->decision!=OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP){returnOVERWORLD_MOTION_DECISION_PROFILE;}",
        "decision=OverworldMotion_AcknowledgeCommit(motion,fieldEpoch);",
        "if(decision!=OVERWORLD_MOTION_DECISION_ACCEPTED){returndecision;}",
        guard,
        "actor->commitSequence++;",
    )
    positions = [clean.find(value) for value in ordered]
    errors = []
    if any(position < 0 for position in positions) or positions != sorted(positions):
        errors.append("actor chain receipt lacks ordered policy/acknowledgement/normal-role-skid guards")
    if clean.count(receipt) != 1:
        errors.append("actor acknowledgement must issue one guarded chain receipt")
    if "OVERWORLD_ACTOR_WALK_PENDING_CHAIN" in commit:
        errors.append("Walk reducer duplicates actor-owned chain receipt")
    return errors


def verify_actor_chain_receipt(actor_source: str, runtime_source: str) -> None:
    errors = actor_chain_receipt_errors(actor_source, runtime_source)
    if errors:
        raise SystemExit("actor chain receipt contract: " + "; ".join(errors))
    body = function_body(actor_source, "ActorSystem_TryAcknowledgeMotionCommit")
    # Bounded copied function fixtures avoid coupling controls to unrelated code.
    actor = "void ActorSystem_TryAcknowledgeMotionCommit(void) {" + body + "}"
    mutations = {
        "chain receipt disabled": actor.replace("policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;", "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;", 1),
        "skid counts as chain": actor.replace("OVERWORLD_ACTOR_WALK_STEP_SKID) == 0", "OVERWORLD_ACTOR_WALK_STEP_SKID) != 0", 1),
        "no-chain motion counts": actor.replace("motion->plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NORMAL", "motion->plan.commitPolicy != OVERWORLD_MOTION_COMMIT_NORMAL", 1),
        "failed acknowledgement counts": actor.replace("decision != OVERWORLD_MOTION_DECISION_ACCEPTED", "decision == OVERWORLD_MOTION_DECISION_ACCEPTED", 1),
        "wrong terminal operation": actor.replace("walkPolicy->operation != OVERWORLD_ACTOR_WALK_POLICY_COMMIT", "walkPolicy->operation != OVERWORLD_ACTOR_WALK_POLICY_INPUT", 1),
        "premature receipt": actor.replace("decision = OverworldMotion_AcknowledgeCommit(motion, fieldEpoch);", "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;\n    decision = OverworldMotion_AcknowledgeCommit(motion, fieldEpoch);", 1),
        "duplicate receipt": actor.replace("actor->commitSequence++;", "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;\n    actor->commitSequence++;", 1),
        "plan-local counter resets actor lifetime": actor.replace("actor->commitSequence++;", "actor->commitSequence = motion->commitSequence;", 1),
    }
    for label, changed in mutations.items():
        if changed == actor or not actor_chain_receipt_errors(changed, runtime_source):
            raise SystemExit(f"actor chain receipt negative control did not reject {label}")
    changed_runtime = runtime_source.replace(
        function_body(runtime_source, "OverworldActorWalkPolicy_ReduceCommit"),
        "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;", 1)
    if not actor_chain_receipt_errors(actor, changed_runtime):
        raise SystemExit("actor chain receipt negative control accepted duplicate Walk owner")
    print("actor-owned chain receipt checks passed; 9 known-bad copies rejected")


def chain_trace_errors(runtime: str) -> list[str]:
    try:
        chain = function_body(runtime, "OverworldActorWalkPolicy_ReduceChain")
        publish = function_body(runtime, "OverworldActorWalkPolicy_PublishEffect")
    except ValueError as error:
        return [str(error)]
    clean = lambda value: re.sub(r"\s+", "", re.sub(r"/\*.*?\*/|//[^\n]*", "", value, flags=re.DOTALL))
    expected_call = "OverworldActorWalkPolicy_PublishEffect(actor,actor->commitSequence,pauseAction)"
    expected_publish = ("returnOVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->recordTrace("
                        "&actor->handle,OVERWORLD_ACTOR_EVENT_WORLD_EFFECT,"
                        "OVERWORLD_ACTOR_REASON_OK,effect,sequence)==OVERWORLD_ACTOR_RESULT_OK;")
    if clean(chain).count(expected_call) != 1 or clean(publish) != expected_publish:
        return ["chain terminal does not publish its actor/commit/action through the trace helper"]
    return []


def verify_chain_trace(runtime: str) -> None:
    errors = chain_trace_errors(runtime)
    if errors:
        raise SystemExit("chain trace routing: " + "; ".join(errors))
    mutations = {
        "swapped trace values": runtime.replace("actor, actor->commitSequence, pauseAction);", "actor, pauseAction, actor->commitSequence);", 1),
        "wrong trace helper": runtime.replace("(void)OverworldActorWalkPolicy_PublishEffect(", "(void)Unrelated_PublishEffect(", 1),
        "wrong trace event": runtime.replace("OVERWORLD_ACTOR_EVENT_WORLD_EFFECT,", "OVERWORLD_ACTOR_EVENT_LOGICAL_COMMIT,", 1),
    }
    for label, changed in mutations.items():
        if changed == runtime or not chain_trace_errors(changed):
            raise SystemExit(f"chain trace negative control did not reject {label}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c",
    )
    parser.add_argument(
        "--runtime-source",
        type=Path,
        default=REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c",
    )
    parser.add_argument(
        "--movement-header",
        type=Path,
        default=REPO / "include/overworld_wild_movement.h",
    )
    parser.add_argument(
        "--timing-policy-header",
        type=Path,
        default=REPO / "include/overworld_walk_timing_policy.h",
    )
    parser.add_argument(
        "--direction-policy-header",
        type=Path,
        default=REPO / "include/overworld_walk_direction_policy.h",
    )
    parser.add_argument(
        "--walk-module-source",
        type=Path,
        default=REPO
        / "src/pokemon_move_history_overlay/overworld_walk_module.c",
    )
    parser.add_argument(
        "--walk-module-header",
        type=Path,
        default=REPO / "include/overworld_walk_module.h",
    )
    parser.add_argument(
        "--mount-source",
        type=Path,
        default=REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c",
    )
    parser.add_argument(
        "--linked-walk-module", type=Path,
        help="also verify the linked ELF DeltaX/DeltaY Thumb addresses and slot sizes",
    )
    args = parser.parse_args()

    source = args.source.read_text()
    runtime = args.runtime_source.read_text()
    header = args.movement_header.read_text()
    timing_policy = args.timing_policy_header.read_text()
    direction_policy = args.direction_policy_header.read_text()
    module = args.walk_module_source.read_text()
    module_header = args.walk_module_header.read_text()
    module_linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    behavior_header = (REPO / "include/overworld_wild_behavior_data.h").read_text()
    helper_header = (REPO / "include/overworld_wild_helper.h").read_text()
    metadata_generator = (
        REPO / "scripts/build_overworld_wild_spawn_metadata.py"
    ).read_text()
    mount_source = args.mount_source.read_text()
    actor_source = (REPO / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()

    reject(
        module_header + module + source,
        (
            "OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY",
            "OverworldWalkWildPolicyModuleEntry",
            "Walk_WildResolvePrimitives",
            "Walk_WildGroupFlagsForTypes",
            "Walk_WildSelectConditionalOverrideMask",
            "gOverworldWalkWildPolicyModuleEntry",
            "0x023BF474",
        ),
        "retired resident wild-policy ABI",
    )
    require(
        source,
        (
            "OverworldWildBehaviorPrimitives primitives;",
            "cache->primitives = *primitives;",
            "primitives = cache->primitives;",
            "primitives = resolution.primitives;",
            "behaviorContext.groupFlags = metadata.groupFlags;",
            "prepared->behaviorResolution.primitives",
        ),
        "canonical resolved primitive and group metadata routing",
    )
    require(
        behavior_header + helper_header + metadata_generator,
        (
            "#define OVERWORLD_WILD_SPAWN_METADATA_VERSION 3",
            "u32 groupFlags;",
            "OWSM_VERSION = 3",
            "OWSM_RECORD_SIZE = 12",
            "OWSM_EXCEPTION_SIZE = 16",
            "group_flags=group_flags",
        ),
        "generated subject-group metadata contract",
    )
    require(
        module_header,
        (
            "OVERWORLD_WALK_DECELERATE_TIME_ADDR 0x023BF400",
            "OVERWORLD_WALK_PROPOSE_STEP_ADDR 0x023BF45C",
            "OVERWORLD_WALK_CLAMP_TIME_ADDR 0x023BF488",
            "OVERWORLD_WALK_ACCELERATE_TIME_ADDR 0x023BF49E",
            "OVERWORLD_WALK_SKID_TILES_ADDR 0x023BF4D6",
            "OVERWORLD_WALK_SKID_TIME_ADDR 0x023BF4F0",
            "OVERWORLD_WALK_STOMP_APPLIES_ADDR 0x023BF504",
            "OVERWORLD_WALK_DIRECTION_FROM_KEYS_ADDR 0x023BF534",
            "OVERWORLD_WALK_DIRECTION_KEY_ADDR 0x023BF586",
            "OVERWORLD_WALK_DELTA_X_ADDR 0x023BF59C",
            "OVERWORLD_WALK_DELTA_Y_ADDR 0x023BF5BE",
            "OVERWORLD_WALK_IS_FORTY_FIVE_DEGREE_TURN_ADDR 0x023BF5E2",
            "OVERWORLD_WALK_DIRECTION_FROM_DELTA_ADDR 0x023BF68C",
            "OVERWORLD_WALK_STRICT_DIAGONAL_ALLOWED_ADDR 0x023BF6CE",
            "OVERWORLD_WALK_DIAGONAL_FACING_ADDR 0x023BF74E",
            "OVERWORLD_WALK_RESOLVE_MOUNTED_DIAGONAL_ADDR 0x023BF780",
            "OVERWORLD_WALK_START_MOUNTED_FLAT_ADDR 0x023BF840",
            "OVERWORLD_WALK_FILTER_MOUNTED_INPUT_ADDR 0x023BF9A0",
        ),
        "direct resident Walk helper ABI",
    )
    reject(
        module_header + module + source + runtime + mount_source,
        (
            "OVERWORLD_WALK_MODULE_ENTRY",
            "OVERWORLD_WALK_MOUNT_MODULE_ENTRY",
            "OverworldWalkModuleEntry",
            "OverworldWalkMountModuleEntry",
            "gOverworldWalkModuleEntry",
            "gOverworldWalkProfileModuleEntry",
            "gOverworldWalkMountModuleEntry",
            "gOverworldWalkFaceModuleEntry",
            "Walk_ApplyFacePlayerFacing",
            "OverworldWalkMountCall",
        ),
        "retired Walk tables or duplicate face-player service",
    )
    require(
        module_linker,
        (
            ". = ORIGIN(rom) + 0x1000;",
            "KEEP(*(.overworld_walk_decelerate_time))",
            "OverworldWalk_DecelerateTime == ORIGIN(rom) + 0x1000",
            "KEEP(*(.overworld_walk_propose_step))",
            "OverworldWalk_ProposeStep == ORIGIN(rom) + 0x105C",
            "ASSERT(. <= ORIGIN(rom) + 0x1088",
        ),
        "reclaimed direct Walk deceleration helper slot",
    )
    require(
        module_linker,
        (
            "OverworldWalk_ClampTime == ORIGIN(rom) + 0x1088",
            "OverworldWalk_AccelerateTime == ORIGIN(rom) + 0x109E",
            "OverworldWalk_SkidTiles == ORIGIN(rom) + 0x10D6",
            "OverworldWalk_SkidTime == ORIGIN(rom) + 0x10F0",
            "OverworldWalk_StompApplies == ORIGIN(rom) + 0x1104",
            "OverworldWalk_DirectionKey == ORIGIN(rom) + 0x1186",
        ),
        "fixed direct Walk helper linker ABI",
    )
    verify_delta_linker_and_controls(module_linker)

    require(
        header,
        (
            "#define OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG 0x80",
            "#define OW_WILD_WALK_TRAVEL_TIME_MIN 1",
            "#define OW_WILD_WALK_TRAVEL_TIME_MAX 32",
            "OVERWORLD_ACTOR_WALK_POLICY_INPUT",
            "OVERWORLD_ACTOR_WALK_POLICY_START_RESULT",
            "OVERWORLD_ACTOR_WALK_POLICY_COMMIT",
            "OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT",
            "OverworldActorWalkPolicyCallSizeMustRemain28Bytes",
        ),
        "typed Walk request ABI",
    )
    policy_call_initializer = function_body(
        source,
        "OverworldWildSpawns_InitPolicyCall",
    )
    require(
        policy_call_initializer,
        (
            "memset(call, 0, sizeof(*call));",
            "call->version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;",
            "call->size = sizeof(*call);",
            "call->actorSlot = (u8)slot;",
            "call->operation = operation;",
        ),
        "wild typed Walk request initialization",
    )
    clamp = function_body(timing_policy, "OverworldWalkTimingPolicy_Clamp")
    require(
        clamp,
        (
            "travelTime < OVERWORLD_WALK_TIMING_MIN",
            "travelTime > OVERWORLD_WALK_TIMING_MAX",
        ),
        "Walk frame-time clamp",
    )
    accelerate = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_Accelerate",
    )
    require(
        accelerate,
        (
            "OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2",
            "nextTravelTime = currentTravelTime;",
            "(currentTravelTime + 1u) / 2u",
            "accelerationStep == 0",
            "currentTravelTime > accelerationStep",
            "currentTravelTime - accelerationStep",
            "nextTravelTime < fastestTravelTime",
        ),
        "Walk profile acceleration amount",
    )
    decelerate = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_Decelerate",
    )
    require(
        decelerate,
        (
            "accelerationStep == 0",
            "currentTravelTime + accelerationStep",
            "OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2",
            "while (nextTravelTime > currentTravelTime)",
            "(nextTravelTime + 1u) / 2u",
        ),
        "Walk turn deceleration amount",
    )
    skid_tiles = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_SkidTiles",
    )
    require(
        skid_tiles,
        (
            "travelTime <= 1",
            "travelTime <= 4",
            "travelTime <= 6",
        ),
        "Walk skid distance bands",
    )
    skid_time = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_SkidTime",
    )
    require(
        skid_time,
        ("OVERWORLD_WALK_TIMING_MAX / 2", "travelTime * 2u"),
        "Walk skid frame time",
    )

    reducer = function_body(runtime, "OverworldActorWalkPolicy_Reduce(")
    require(
        reducer,
        (
            "call->version != OVERWORLD_ACTOR_WALK_POLICY_VERSION",
            "call->size != sizeof(*call)",
            "call->actorSlot >= OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS",
            "OverworldActorWalkPolicy_ReduceInput(policy, call);",
            "OverworldActorWalkPolicy_ReduceStartResult(policy, call);",
            "OverworldActorWalkPolicy_ReduceCommit(policy, call);",
            "OverworldActorWalkPolicy_ReduceChain(policy, actor, call);",
        ),
        "typed Walk reducer dispatch",
    )

    walk_input = function_body(runtime, "OverworldActorWalkPolicy_ReduceInput")
    require(
        walk_input,
        (
            "OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID",
            "OverworldWalk_IsFortyFiveDegreeTurn(",
            "OverworldWalk_SkidTiles(state->speed)",
            "OverworldWalk_SkidTime(state->speed)",
            "OVERWORLD_ACTOR_WALK_STEP_STOP_SKID",
            "OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION",
            "OverworldWalk_DecelerateTime(",
            "OverworldWalk_ProposeStep(",
        ),
        "typed Walk input transition",
    )
    reject(
        walk_input,
        (
            "requestedDirection &= 3",
            "requestedDirection & 3",
            "state->speed--;",
            "state->speed++;",
            "1u <<",
        ),
        "typed Walk input speed-tier handling",
    )

    start_result = function_body(
        runtime,
        "OverworldActorWalkPolicy_ReduceStartResult",
    )
    require(
        start_result,
        (
            "policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL",
            "call->startResult != OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED",
            "call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_CRASH",
            "OverworldWalkDirectionPolicy_ApplyStartResult(",
            "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED",
            "call->reserved[0]",
        ),
        "typed Walk engine START_RESULT transition",
    )
    mounted_start_result = function_body(
        actor_source,
        "ActorSystem_FinishMountedWalk",
    )
    require(
        mounted_start_result + mount_source,
        (
            "OVERWORLD_MOUNT_WALK_NOMINAL_TIME_INDEX",
            "= call->reserved[0]",
            "output->reserved[0] = state->reservedPolicyProfile[",
        ),
        "mounted turn keeps nominal deceleration through START_RESULT",
    )

    commit = function_body(runtime, "OverworldActorWalkPolicy_ReduceCommit")
    require(
        commit,
        (
            "policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED",
            "call->distance != 1",
            "call->direction != state->direction",
            "OverworldWalk_StompApplies(",
            "state->tileCounter >= call->lane->tilesToAccelerate",
            "OverworldWalk_AccelerateTime(",
            "call->lane->walkAccelerationStep",
        ),
        "typed Walk terminal COMMIT transition",
    )
    verify_actor_chain_receipt(actor_source, runtime)
    reject(
        commit,
        ("state->speed--;", "state->speed++;", "1u <<"),
        "typed Walk completion speed-tier handling",
    )

    chain_pause = function_body(runtime, "OverworldActorWalkPolicy_ReduceChain")
    require(
        chain_pause,
        (
            "encodedPauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE",
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE",
            "OverworldActorWalkPolicy_SelectChainPauseAction(",
            "policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_CHAIN",
            "OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED",
            "policy->chainStepsRemaining = 0;",
            "policy->deferredChainPauseAction = 0;",
            "call->chainAction = pauseAction;",
            "actor->commitSequence",
            "pauseAction",
            "call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;",
        ),
        "typed Walk chain eligibility and action",
    )
    require(
        function_body(runtime, "OverworldActorWalkPolicy_SelectChainPauseAction"),
        (
            "gf_rand() & 7u",
            "actionMask & (1u << action)",
            "return action + 1u;",
        ),
        "uniform Movement Chain pause-action selection",
    )
    verify_chain_trace(runtime)

    mount_commit = function_body(mount_source, "OverworldMount_ApplyWalkPolicy")
    require(
        mount_commit,
        (
            "->finishMountedWalk(",
            "OverworldMount_ApplyWalkPolicyOutput(",
            "output.decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED",
        ),
        "mounted actor-owned Walk START_RESULT",
    )
    reject(
        mount_commit,
        (
            "OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED",
            "->reduceWalk(",
        ),
        "mounted policy ownership",
    )

    direction_from_delta = function_body(
        direction_policy,
        "OverworldWalkDirectionPolicy_FromDelta",
    )
    require(
        direction_from_delta,
        (
            "OVERWORLD_WALK_DIRECTION_NORTH_WEST",
            "OVERWORLD_WALK_DIRECTION_NORTH_EAST",
            "OVERWORLD_WALK_DIRECTION_SOUTH_WEST",
            "OVERWORLD_WALK_DIRECTION_SOUTH_EAST",
            "OVERWORLD_WALK_DIRECTION_NONE",
        ),
        "eight-way direction encoding",
    )
    forty_five_rule = function_body(
        direction_policy,
        "OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn",
    )
    require(
        forty_five_rule,
        (
            "OverworldWalkDirectionPolicy_DeltaX(from)",
            "OverworldWalkDirectionPolicy_DeltaX(to)",
            "OverworldWalkDirectionPolicy_DeltaY(from)",
            "OverworldWalkDirectionPolicy_DeltaY(to)",
            "> 0",
        ),
        "45-degree dot-product rule",
    )
    strict_diagonal = function_body(module, "Walk_DiagonalRejection")
    if strict_diagonal.count("Walk_CanCardinal(avatar,") != 2:
        raise SystemExit(
            "strict diagonal movement must clear both cardinal neighbor tiles"
        )
    require(
        strict_diagonal,
        ("targetX", "targetY", "Walk_ValidateDiagonalLanding("),
        "strict diagonal destination validation",
    )
    require(
        function_body(module, "Walk_ValidateDiagonalLanding"),
        ("validateHopLanding(", "targetX", "targetY"),
        "strict diagonal landing service",
    )

    planned = function_body(
        source,
        "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand",
    )
    require(
        planned,
        (
            "OverworldWalk_DirectionFromDelta(",
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(",
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(",
            "distance = 1;",
            "OverworldWildSpawns_TryStartAcceleratedWalkStep(",
            "state->movementStagedHopPending[slot] = pendingMarker",
            ": flatWalk ? OW_WILD_SPAWNER_STAGED_WALK_PENDING",
        ),
        "wild flat Walk planning",
    )
    reject(
        planned,
        (
            "OverworldWildSpawns_MovementDirectionDeltaX(direction)",
            "OverworldWildSpawns_MovementDirectionDeltaY(direction)",
            "MapObject_MovementCommandFromDirection(",
        ),
        "wild diagonal Walk stock-direction handling",
    )

    prepared = function_body(
        source,
        "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed",
    )
    require(
        prepared,
        (
            "frameCount = OverworldWalk_ClampTime(walkTime);",
            "runtime->movementCustomMotionModes[slot] = flatWalk",
            "OW_WILD_CUSTOM_MOTION_WALK",
            "movementCustomJumpArcHeightsQ4[slot] = !flatWalk",
            "OverworldWalk_DiagonalFacing(",
            "runtime->movementCustomJumpPrepActive[slot] = !flatWalk;",
            "if (chainReposition && !repositionUsesArc)",
            "(object->flags & MAPOBJECTFLAG_UNK7) != 0",
        ),
        "wild exact flat-motion setup",
    )
    reject(
        prepared,
        ("frameCount = 1u <<", "frameCount = 1 <<"),
        "wild flat Walk frame timing",
    )

    landing = function_body(
        source,
        "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
    )
    require(
        landing,
        (
            "OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER",
            "x != movingObject->xCurr",
            "y != movingObject->yCurr",
            "x,\n                movingObject->yCurr",
            "movingObject->xCurr,\n                y",
        ),
        "wild strict diagonal clearance",
    )

    reject(
        source,
        ("OverworldWildSpawns_IsTileReservedByOtherWild",),
        "wild private target-reservation owner",
    )
    require(
        landing,
        (
            "OverworldWildSpawns_IsTileOccupiedOnSurface(",
            "targetSurface.height",
        ),
        "wild physical-surface occupancy",
    )

    start_step = function_body(source, "OverworldWildSpawns_StartMomentumWalkStep")
    require(
        start_step,
        (
            "OVERWORLD_ACTOR_WALK_STEP_SKID",
            "OVERWORLD_ACTOR_WALK_STEP_VALIDATE",
            "OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG",
            "OverworldWalk_DeltaX(call->stepDirection)",
            "OverworldWalk_DeltaY(call->stepDirection)",
            "OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER",
            "call->stepDirection <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT",
            "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(",
            "call->travelTime",
            "validated_step_blocked:",
            "return FALSE;",
        ),
        "wild typed Walk engine adapter",
    )
    reject(
        start_step,
        ("OverworldWildSpawns_PlayMovementCrashFeedback(",),
        "wild adapter-owned crash reduction",
    )
    crash_feedback = function_body(
        source,
        "OverworldWildSpawns_PlayMovementCrashFeedback",
    )
    require(
        crash_feedback,
        (
            "OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(lane->walkOptions)",
            "OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT",
            "PlaySE(OW_WILD_SPAWNER_WALK_CRASH_SE);",
        ),
        "authored blocked skid crash feedback",
    )
    effect = function_body(source, "OverworldWildSpawns_ApplyWalkPolicyOutput")
    require(
        effect,
        (
            "OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION",
            "movementPreviousTileLocked[stepContext->slot] =",
            "movementLastDistances[stepContext->slot] = 0;",
            "OVERWORLD_ACTOR_WORLD_EFFECT_SKID_DUST",
            "OVERWORLD_ACTOR_WORLD_EFFECT_STOMP",
            "OVERWORLD_ACTOR_WORLD_EFFECT_CRASH",
            "call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_NONE;",
        ),
        "wild typed Walk effect publication",
    )
    execute = function_body(source, "OverworldWildSpawns_ExecuteWalkPolicy")
    require(
        source,
        (
            '".global OverworldWildSpawns_ReduceWalk\\n.thumb_func\\n"',
            '"OverworldWildSpawns_ReduceWalk:\\n"',
            '"ldr r3, [r3, #8]\\n"',
            '"ldr r3, [r3, #12]\\n"',
        ),
        "wild resident Walk reducer wrapper",
    )
    require(
        execute,
        (
            "call->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP",
            "OverworldWildSpawns_StartMomentumWalkStep(stepContext, call)",
            "call->operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;",
            "OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED",
            "OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED",
            "OverworldWildSpawns_ReduceWalk(call)",
        ),
        "wild INPUT to START_RESULT transaction",
    )

    accelerated = function_body(
        source,
        "OverworldWildSpawns_TryStartAcceleratedWalkStep",
    )
    require(
        accelerated,
        (
            "u8 roleFlags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;",
            "u8 spotState = stepContext->state->movementSpotStates[stepContext->slot];",
            "OverworldWildSpawns_InitPolicyCall(\n"
            "        &call,\n"
            "        stepContext->slot,\n"
            "        OVERWORLD_ACTOR_WALK_POLICY_INPUT);",
            "call.flags = 0;",
            "OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN",
            "OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED",
            "OverworldWildSpawns_ReduceWalk(&call)",
            "OverworldWildSpawns_ExecuteWalkPolicy(",
        ),
        "wild typed Walk input",
    )
    reject(
        accelerated,
        (
            "movementSpawnRunActive[stepContext->slot]",
            "OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID",
        ),
        "move-from-off-screen Walk policy exception",
    )
    errors = packed_role_path_errors(
        source, "OverworldWildSpawns_TryStartAcceleratedWalkStep", "WALK")
    if errors:
        raise SystemExit("wild typed Walk role request: " + "; ".join(errors))
    finished_walk = function_body(
        source,
        "OverworldWildSpawns_HandleFinishedWalkMovement",
    )
    require(
        finished_walk,
        (
            "OverworldWildSpawns_InitPolicyCall(\n"
            "        &call,\n"
            "        slot,\n"
            "        OVERWORLD_ACTOR_WALK_POLICY_COMMIT);",
            "call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED\n"
            "        | OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;",
            "->terminalWalk(",
            "OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS",
            "OverworldWildSpawns_ExecuteWalkPolicy(&stepContext, &call)",
        ),
        "wild typed Walk terminal COMMIT",
    )
    reject(
        finished_walk,
        ("movementSpawnRunActive[slot]",),
        "move-from-off-screen Walk COMMIT exception",
    )
    chain_commit = function_body(
        source,
        "OverworldWildSpawns_ApplyUniversalChainMovementPause",
    )
    require(
        chain_commit,
        (
            "OverworldWildSpawns_InitPolicyCall(\n"
            "        &call,\n"
            "        slot,\n"
            "        OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT);",
            "call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;",
            "call.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED",
            "OverworldWildSpawns_CommitDeferredChainMovementPause(",
        ),
        "wild typed chain COMMIT and public trace",
    )
    single_step = function_body(
        source,
        "OverworldWildSpawns_TryStartSingleDirectionMovementStep",
    )
    require(
        single_step,
        (
            "direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT",
            "OverworldWildSpawns_GetCurrentMovementLocomotion(",
            "== OW_WILD_BEHAVIOR_LOCOMOTION_WANDER",
            "OverworldWildSpawns_TryStartAcceleratedWalkStep(",
        ),
        "profile Walk route",
    )
    reject(
        single_step,
        ("movementSpawnRunActive[stepContext->slot]",),
        "spawn movement must not force Walk",
    )
    spawn_step = function_body(
        source,
        "OverworldWildSpawns_UpdateSpawnMoveTargetState",
    )
    require(
        spawn_step,
        (
            "movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE",
            "OverworldWildSpawns_ObjectCurrentX(object)",
            "OverworldWildSpawns_ObjectCurrentY(object)",
            "state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;",
            "OverworldWildSpawns_ClearSpawnRunState(state, slot);",
            "OverworldWildSpawns_ClearWalkMovementState(state, slot, object);",
            "OverworldWildSpawns_SetPostSpawnStartupCooldown(state, slot);",
        ),
        "move-from-off-screen target lifecycle",
    )
    if spawn_step.count("OverworldWildSpawns_SetObjectLandingTile(") != 1:
        raise SystemExit(
            "move-from-off-screen route can snap to the destination before arrival"
        )
    reject(
        spawn_step,
        (
            "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(",
            "OverworldWildSpawns_TryStartSpawnMoveTeleport(",
            "OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(",
            "OverworldWildSpawns_TryStartSpawnerMovementCommand(",
        ),
        "separate move-from-off-screen movement driver",
    )
    reject(
        source,
        ("OverworldWildSpawns_TryStartSpawnRunStep",),
        "dedicated move-from-off-screen scheduler",
    )
    owner_motion = function_body(
        source,
        "OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand",
    )
    require(
        owner_motion,
        (
            "throwTarget = runtime->throwState.targets[slot];",
            "OverworldWildSpawns_GetActiveConditionApplications(state, slot)",
            "movementTarget = state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_MOVE",
            "? OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER",
            "? state->movementSpawnRunTargetX[slot]",
            "? state->movementSpawnRunTargetY[slot]",
            "OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(",
        ),
        "move-from-off-screen fixed chase target",
    )
    reject(
        owner_motion,
        (
            "? OW_WILD_SPAWNER_THROW_TARGET_NONE",
            "(!state->movementSpawnRunActive[slot]",
        ),
        "move-from-off-screen Owner policy exception",
    )
    movement_command = function_body(
        source,
        "OverworldWildSpawns_TryStartSpawnerMovementCommand",
    )
    require(
        movement_command,
        ("avoidPreviousTile = OverworldWildSpawns_ShouldAvoidPreviousTileForResolvedProfile(",),
        "authored backtrack policy",
    )
    reject(
        movement_command,
        ("movementSpawnRunActive[slot]",),
        "move-from-off-screen direction policy exception",
    )
    spawn_origin = function_body(
        source,
        "OverworldWildSpawns_TryPickSpawnRunStart",
    )
    require(
        source + spawn_origin,
        (
            "#define OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE 16",
            "#define OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES 4",
            "#define OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES 1",
            "direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP",
            "triedDirections",
            "int bestVisibleTravel = state != NULL ? -0x7FFFFFFF : -1;",
            "OverworldWildSpawns_GetSpawnHopVisibleTravelScore(",
            "minimumCandidateDistance = state == NULL",
            "for (candidateDistance = OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE;",
            "* candidateDistance;",
            "entryDistance >= OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE",
            "OverworldWildSpawns_Abs(candidateX - playerX)",
            "+ OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES",
            "+ OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES",
            "OverworldWildSpawns_Abs(candidateY - playerY)",
            "GetMetatileBehaviorAt(fieldSystem, candidateX, candidateY) == 0xFF",
            "terrain == OW_WILD_SPAWN_TERRAIN_LAND",
            "OverworldWildSpawns_IsWalkableLandTile(",
            "OverworldWildSpawns_IsNearActiveSpawn(",
        ),
        "long bounded move-from-off-screen route",
    )
    reject(
        source + spawn_origin,
        (
            "SPAWN_RUN_LEGACY_MIN_TRAVEL_TILES",
            "SPAWN_RUN_START_ATTEMPTS",
            "SPAWN_RUN_OFFSCREEN_MIN_DISTANCE",
            "SPAWN_RUN_OFFSCREEN_MAX_DISTANCE",
            "SPAWN_RUN_LATERAL_SPREAD",
            "Preserve the old random sequence",
        ),
        "unused move-from-off-screen random origin path",
    )
    spawn_startup = function_body(source, "OverworldWildSpawns_PrepareSpawnStartup")
    require(
        spawn_startup,
        (
            "if (!OverworldWildSpawns_TryPickSpawnRunStart(",
            "return FALSE;",
            "startup->locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN;",
        ),
        "Move From Off Screen must reject a spawn with no off-screen A tile",
    )
    spawn_finalize = function_body(
        source,
        "OverworldWildSpawns_FinalizePreparedSpawn",
    )
    require(
        source + spawn_finalize,
        (
            "#define OW_WILD_SPAWN_STARTUP_PENDING 0xFE",
            "pendingStage != OW_WILD_SPAWN_STARTUP_PENDING",
            "pendingStage == OW_WILD_PROFILE_DESTINATION_SCAN_PENDING",
            "OW_WILD_RUNTIME(state)->refillPositionChecksRemaining =\n"
            "                OW_WILD_SPAWN_STARTUP_PENDING;",
        ),
        "destination and spawn-startup work split",
    )
    spawn_commit = function_body(
        source,
        "OverworldWildSpawns_CommitQueuedSpawn",
    )
    require(
        spawn_commit,
        (
            "runtime->refillPositionChecksRemaining >= OW_WILD_SPAWN_STARTUP_PENDING",
            "destinationFinished = TRUE;",
        ),
        "queued spawn-startup continuation",
    )
    reject(
        source,
        ("OverworldWildSpawns_HandleFinishedSpawnRunMovementCommand",),
        "dedicated move-from-off-screen completion path",
    )
    spawn_start = function_body(source, "OverworldWildSpawns_SetSpawnRunState")
    move_start = function_body(source, "OverworldWildSpawns_StartSpawnRun")
    spawn_clear = function_body(source, "OverworldWildSpawns_ClearSpawnRunState")
    require(
        spawn_start,
        (
            "state->movementSpawnRunTargetX[slot] = (s16)targetX;",
            "state->movementSpawnRunTargetY[slot] = (s16)targetY;",
            "state->movementSpawnRunActive[slot] = entryMode;",
        ),
        "spawn entry target storage",
    )
    reject(
        spawn_start,
        (
            "movementCooldowns[slot]",
            "OverworldWildSpawns_ClearWalkMovementState",
        ),
        "spawn entry movement policy reset",
    )
    require(
        move_start,
        (
            "OW_WILD_SPAWN_ENTRY_MOVE",
            "state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;",
            "OverworldWildSpawns_ResumeOwnerAfterAlert(",
        ),
        "move-from-off-screen Owner lane",
    )
    require(
        spawn_clear,
        (
            "state->movementSpawnRunTargetX[slot] = 0;",
            "state->movementSpawnRunTargetY[slot] = 0;",
            "state->movementSpawnRunActive[slot] = OW_WILD_SPAWN_ENTRY_NONE;",
        ),
        "spawn entry target cleanup",
    )
    reject(
        spawn_clear,
        (
            "movementSpotStates[slot]",
            "OverworldWildSpawns_ClearWalkMovementState",
        ),
        "spawn entry cleanup policy mutation",
    )
    reject(
        source,
        ("OverworldWildSpawns_GetMovementWalkCommandForProfile",),
        "obsolete quantized profile Walk command",
    )
    directed = function_body(
        source,
        "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand",
    )
    require(
        directed,
        (
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(movementDirections)",
            "!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(movementDirections)",
        ),
        "wild directed diagonal/cardinal policy",
    )
    reject(
        directed,
        ("hopAllowNonCardinal == OW_WILD_BEHAVIOR_BOOL_YES",),
        "old diagonal-only exclusion",
    )
    owner_motion = function_body(
        source,
        "OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand",
    )
    require(
        owner_motion,
        (
            "primitives->chillLocomotion\n"
            "                == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER",
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(",
            "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(",
        ),
        "directed diagonal Wander/Chase routing",
    )

    require(
        source,
        (
            "#define OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT "
            "OW_WILD_BEHAVIOR_WALK_TIME_DEFAULT",
            "boostedProfile.chillSpeed > profile->chaseBoostSpeed",
        ),
        "wild frame-time fallback and scheduler",
    )
    reject(
        source,
        (
            "OverworldWildSpawns_GetFrameMovementDecisionIntervalForSpeed",
            "OverworldWildSpawns_ShouldRunFrameMovementDecisionForSpeed",
        ),
        "old tier-only wild speed policy",
    )

    if args.linked_walk_module is not None:
        verify_linked_delta_entries(args.linked_walk_module)
    print(
        "wild exact-frame Walk timing, skid, diagonal, and completion rules verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

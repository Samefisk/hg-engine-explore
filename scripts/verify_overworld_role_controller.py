#!/usr/bin/env python3
"""Build host proofs and verify the role-controller adapter ownership seam."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


def require(source: str, fragment: str, label: str) -> None:
    if fragment not in source:
        raise SystemExit(f"missing {label}: {fragment}")


def forbid(source: str, fragment: str, label: str) -> None:
    if fragment in source:
        raise SystemExit(f"stale {label}: {fragment}")


def strip_c_noncode(source: str) -> str:
    """Keep source positions stable while hiding comments and literals."""
    result = list(source)
    index = 0
    state = "code"
    quote = ""
    while index < len(source):
        current = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if current == "/" and following == "/":
                result[index] = result[index + 1] = " "
                index += 2
                state = "line-comment"
                continue
            if current == "/" and following == "*":
                result[index] = result[index + 1] = " "
                index += 2
                state = "block-comment"
                continue
            if current in ('"', "'"):
                quote = current
                result[index] = " "
                index += 1
                state = "literal"
                continue
        elif state == "line-comment":
            if current == "\n":
                state = "code"
            else:
                result[index] = " "
            index += 1
            continue
        elif state == "block-comment":
            if current == "*" and following == "/":
                result[index] = result[index + 1] = " "
                index += 2
                state = "code"
                continue
            if current != "\n":
                result[index] = " "
            index += 1
            continue
        else:
            result[index] = " "
            if current == "\\" and following:
                if following != "\n":
                    result[index + 1] = " "
                index += 2
                continue
            if current == quote:
                state = "code"
            index += 1
            continue
        index += 1
    return "".join(result)


def matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    for index in range(start, len(source)):
        if source[index] == opening:
            depth += 1
        elif source[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    return -1


def function_bodies(source: str) -> dict[str, str]:
    clean = strip_c_noncode(source)
    bodies: dict[str, str] = {}
    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", clean):
        name = match.group(1)
        close = matching_delimiter(clean, clean.find("(", match.start()), "(", ")")
        if close < 0:
            continue
        cursor = close + 1
        while cursor < len(clean) and clean[cursor].isspace():
            cursor += 1
        if cursor >= len(clean) or clean[cursor] != "{":
            continue
        end = matching_delimiter(clean, cursor, "{", "}")
        if end >= 0:
            bodies[name] = source[cursor + 1:end]
    return bodies


def reachable_body(source: str, root: str) -> str | None:
    bodies = function_bodies(source)
    if root not in bodies:
        return None
    pending = [root]
    visited: set[str] = set()
    result: list[str] = []
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        body = bodies[name]
        result.append(body)
        clean = strip_c_noncode(body)
        for call in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", clean):
            called = call.group(1)
            if called in bodies and called not in visited:
                pending.append(called)
    return "\n".join(result)


def reachable_functions(source: str, root: str) -> dict[str, str] | None:
    bodies = function_bodies(source)
    if root not in bodies:
        return None
    pending = [root]
    result: dict[str, str] = {}
    while pending:
        name = pending.pop()
        if name in result:
            continue
        body = bodies[name]
        result[name] = body
        clean = strip_c_noncode(body)
        for call in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", clean):
            called = call.group(1)
            if called in bodies and called not in result:
                pending.append(called)
    return result


def call_arguments(body: str) -> list[tuple[str, str]]:
    clean = strip_c_noncode(body)
    calls: list[tuple[str, str]] = []
    for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", clean):
        opening = clean.find("(", match.start())
        close = matching_delimiter(clean, opening, "(", ")")
        if close >= 0:
            calls.append((match.group(1), clean[opening + 1:close]))
    return calls


ROLE = "OVERWORLD_ROLE_CONTROLLER_"
WILD_ROLE_HELPER = "OverworldWildSpawns_ReduceRole"
MOUNT_ROLE_HELPER = "OverworldMount_ReduceRole"
PACKED_ROLE_ROOTS = {
    "OverworldWildSpawns_TryStartAcceleratedWalkStep": "WALK",
    "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand": "HOP",
    "OverworldWildSpawns_TryStartChillTeleportMovementCommand": "TELEPORT",
    "OverworldWildSpawns_TryStartTeleportMovementCommand": "TELEPORT",
    "OverworldWildSpawns_HandleLockedWalkCrash": "BLOCKED",
    "OverworldMount_TryStartCustomMotion": "CUSTOM",
    "OverworldMount_StartWalkCrash": "BLOCKED",
}


def compact(source: str) -> str:
    return re.sub(r"\s+", "", strip_c_noncode(source))


def split_arguments(arguments: str) -> list[str]:
    result = []
    start = depth = 0
    for index, char in enumerate(arguments):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            result.append(arguments[start:index])
            start = index + 1
    return result + [arguments[start:]]


def packed_terms(expression: str) -> set[str]:
    expression = re.sub(r"\(\s*u(?:8|16|32)\s*\)", "", expression)
    return set(re.sub(r"[()\s]", "", expression).split("|"))


def role_transport_errors(source: str, mounted: bool) -> list[str]:
    """Check the actual transport, not no-op references to role/output names.

    The word packing is the public twelve-byte role ABI. Keep this bounded
    source check separate from the caller checks and the pure reducer harness.
    This is S1 ownership evidence, not gameplay evidence or a full C verifier.
    """
    helper = MOUNT_ROLE_HELPER if mounted else WILD_ROLE_HELPER
    body = compact(function_bodies(source).get(helper, ""))
    if mounted:
        statements = (
            "OverworldRoleControllerInput value;u32 words[3];",
            "u8 outputOffset = (u8)(request >> 8) + 5;",
            "input.words[0] = OVERWORLD_ROLE_CONTROLLER_VERSION | sizeof(input.value) << 16;",
            "input.words[1] = request;", "input.words[2] = details;",
            "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(&input.value, &output);",
            "return ((const u8 *)(const void *)&output)[outputOffset];",
        )
    else:
        statements = (
            "roleInput.version = OVERWORLD_ROLE_CONTROLLER_VERSION;",
            "roleInput.size = sizeof(roleInput);",
            "roleInput.role = slot == OW_WILD_FOLLOWER_SLOT ? OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER : OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;",
            "roleInput.event = (u8)request;",
            "roleInput.intentKind = (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT);",
            "roleInput.requestedDirection = (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT);",
            "roleInput.committedDirection = (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT);",
            "roleInput.flags = (u8)details;",
            "roleInput.chainAction = (u8)(details >> OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT);",
            "roleInput.chainTicks = (u8)(details >> OW_WILD_SPAWNER_ROLE_RESULT_TICKS_SHIFT);",
            "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(&roleInput, &roleOutput);",
            "decision = ((const u32 *)(const void *)&roleOutput)[1];",
            "if (roleOutput.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT) { if (roleOutput.intentKind != roleInput.intentKind) { return 0; }",
            "return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED | (decision >> 16);",
            "if (roleOutput.decision != OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL) { return 0; }",
            "return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED | ((const u32 *)(const void *)&roleOutput)[2];",
        )
    errors = [f"{helper}: missing transport statement {statement}"
              for statement in statements if compact(statement) not in body]
    if body.count("OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(") != 1:
        errors.append(f"{helper}: resident reducer must be called exactly once")
    if not mounted:
        macros = {
            "INPUT_INTENT_SHIFT": "8", "INPUT_DIRECTION_SHIFT": "16",
            "INPUT_COMMITTED_SHIFT": "24", "RESULT_FLAGS_SHIFT": "8",
            "RESULT_TICKS_SHIFT": "16", "RESULT_ACCEPTED": "(1u<<24)",
        }
        clean = strip_c_noncode(source)
        for suffix, value in macros.items():
            match = re.search(rf"^\s*#define\s+OW_WILD_SPAWNER_ROLE_{suffix}\s+([^\n]+)", clean, re.MULTILINE)
            if match is None or compact(match.group(1)) != value:
                errors.append(f"{helper}: wrong packed field {suffix}")
    return errors


def packed_role_path_errors(source: str, root: str, intent: str) -> list[str]:
    """Follow each real request through its arguments, helper, and output guard."""
    mounted = root.startswith("OverworldMount_")
    helper = MOUNT_ROLE_HELPER if mounted else WILD_ROLE_HELPER
    errors = role_transport_errors(source, mounted)
    body = strip_c_noncode(function_bodies(source).get(root, ""))
    calls = [arguments for name, arguments in call_arguments(body) if name == helper]
    if len(calls) != 1:
        return errors + [f"{root}: expected one direct call to {helper}"]
    arguments = split_arguments(calls[0])
    if len(arguments) != (2 if mounted else 3):
        return errors + [f"{root}: wrong role-helper argument count"]
    request, details = arguments[-2:]
    clean = compact(body)
    call_index = clean.find(helper + "(")
    before, after = clean[:call_index], clean[call_index:]
    assignment = re.search(r"([A-Za-z_]\w*)=$", before)
    result = assignment.group(1) if assignment else ""
    blocked = PACKED_ROLE_ROOTS[root] == "BLOCKED"
    if mounted:
        expected = {ROLE + "ROLE_MOUNTED", ROLE + ("EVENT_BLOCKED" if blocked else "EVENT_REQUEST") + "<<8"}
        if blocked:
            expected |= {ROLE + "INTENT_WALK<<16", ROLE + "DIRECTION_NONE<<24"}
            if packed_terms(details) != {ROLE + "DIRECTION_NONE", ROLE + "INPUT_RAM<<8"}:
                errors.append("Mounted crash details do not encode RAM at the flags byte")
            guard = ")!=" + ROLE + "TERMINAL_CRASH){return;}"
            effect = "OverworldMount_ApplyPolicyValue(" + "OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT,OVERWORLD_ACTOR_WORLD_EFFECT_CRASH)"
            if guard not in after or effect not in after or after.find(guard) > after.find(effect) or effect in before:
                errors.append("Mounted crash effect is not after the returned CRASH guard")
        else:
            match = re.search(r"([A-Za-z_]\w*)=rawLocomotion==OW_WILD_BEHAVIOR_LOCOMOTION_HOP\?" + ROLE + r"INTENT_HOP:" + ROLE + r"INTENT_TELEPORT;", before)
            if match is None or intent not in ("HOP", "TELEPORT"):
                errors.append("Mounted locomotion does not select the requested semantic intent")
            else:
                expected.add(match.group(1) + "<<16")
            expected.add(result + "<<24")
            if not result or compact(details) != result or ("if(" + result + ">" + ROLE + "DIRECTION_MAX){returnFALSE;}") not in after:
                errors.append("Mounted request does not consume/reject the returned direction")
            first_work = after.find("startX=player->xCurr;")
            if first_work < 0 or after.find("DIRECTION_MAX){returnFALSE;}") > first_work:
                errors.append("Mounted planning starts without accepted role direction")
    else:
        expected = {ROLE + ("EVENT_BLOCKED" if blocked else "EVENT_REQUEST"),
                    ROLE + "INTENT_" + ("WALK" if blocked else intent) + "<<OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT"}
        expected_slot = "stepContext->slot" if intent == "WALK" or blocked else "slot"
        if compact(arguments[0]) != expected_slot:
            errors.append("Wild/Follower request uses the wrong actor slot")
        direction = ROLE + "DIRECTION_NONE" if intent == "TELEPORT" else "direction"
        committed = ("direction" if blocked else "policy.walkMomentum.direction"
                     if intent == "WALK" else ROLE + "DIRECTION_NONE")
        expected |= {direction + "<<OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT",
                     committed + "<<OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT"}
        if blocked:
            if ROLE + "INPUT_RAM" not in packed_terms(details):
                errors.append("Wild crash does not request RAM")
            if not result or ("if((u8)" + result + "==" + ROLE + "TERMINAL_CRASH||" + "(u8)" + result + "==" + ROLE + "TERMINAL_CRASH_BATTLE){OverworldWildSpawns_EndMovementCrash(stepContext);}") not in after:
                errors.append("Wild crash does not consume the returned terminal")
        else:
            accepted = "OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED"
            flags = compact(details)
            if intent == "TELEPORT":
                if packed_terms(details) != {ROLE + "INPUT_DIRECTION_OPTIONAL", ROLE + "INPUT_CHAIN_ENABLED"}:
                    errors.append("Wild Teleport request loses direction-optional/chain flags")
            elif not re.fullmatch(r"[A-Za-z_]\w*", flags) or flags + "=" + ROLE + "INPUT_CHAIN_ENABLED;" not in before:
                errors.append("Wild Walk/Hop request loses its initialized chain flags")
            if result:
                guard = "if((" + result + "&" + accepted + ")==0){returnFALSE;}"
                consumed = ("call.direction=" if intent == "WALK" else "direction=") + "(u8)" + result + ";"
                if guard not in after or consumed not in after or after.find(guard) > after.find(consumed):
                    errors.append("Wild request does not consume an accepted role direction")
            elif intent == "TELEPORT":
                guard = re.search(r"\)&" + accepted + r"\)==0\)\{[^{}]*returnFALSE;\}", after)
                work = after.find("OverworldWildSpawns_TryStartPlannedTeleport(")
                if guard is None or work < 0 or guard.end() > work:
                    errors.append("Wild Teleport starts without role acceptance")
            else:
                errors.append("Wild request ignores the role output")
    if packed_terms(request) != expected:
        errors.append(f"{root}: role/event/intent/direction packed request differs")
    return errors


def run_packed_role_mutation_tests(wild: str, mount: str) -> None:
    """Apply known-bad changes to copies of the actual adapters, never ROMs."""
    fixtures = {}
    for mounted, source in ((False, wild), (True, mount)):
        bodies = function_bodies(source)
        helper = MOUNT_ROLE_HELPER if mounted else WILD_ROLE_HELPER
        macros = "\n".join(re.findall(
            r"^\s*#define\s+OW_WILD_SPAWNER_ROLE_[^\n]+", source, re.MULTILINE))
        for root, kind in PACKED_ROLE_ROOTS.items():
            if root.startswith("OverworldMount_") != mounted:
                continue
            # Only the real helper, real caller and ABI constants can be witnesses.
            fixture = macros + "\n" + "\n".join(
                f"void {name}(void) {{{bodies[name]}}}" for name in (helper, root))
            intent = "HOP" if kind == "CUSTOM" else "WALK" if kind == "BLOCKED" else kind
            errors = packed_role_path_errors(fixture, root, intent)
            if errors:
                raise SystemExit("invalid packed role adapter: " + "; ".join(errors))
            fixtures[root] = (fixture, intent)
            renamed = fixture.replace("roleIntent", "selectedIntent").replace("roleDecision", "decisionReceipt")
            if packed_role_path_errors(renamed, root, intent):
                raise SystemExit("packed role check rejected an equivalent local-name refactor")

    changes = (
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "wrong wild role", ": OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;", ": OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;"),
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "wrong slot", "stepContext->slot,\n            OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST", "0,\n            OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST"),
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "ignored accepted flag", "roleDecision & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0", "roleDecision & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) != 0"),
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "ignored returned direction", "call.direction = (u8)roleDecision;", "call.direction = direction;"),
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "wrong request flags", "            roleFlags);", "            0);"),
        ("OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand", "wrong intent", "OVERWORLD_ROLE_CONTROLLER_INTENT_HOP\n", "OVERWORLD_ROLE_CONTROLLER_INTENT_WALK\n"),
        ("OverworldWildSpawns_TryStartChillTeleportMovementCommand", "wrong request", "| OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST,", "| OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED,"),
        ("OverworldWildSpawns_TryStartTeleportMovementCommand", "wrong field shift", "#define OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT 8", "#define OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT 16"),
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "wrong resident route", "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(", "OtherRuntime->reduceRole("),
        ("OverworldWildSpawns_TryStartAcceleratedWalkStep", "wrong helper route", "roleDecision = OverworldWildSpawns_ReduceRole(", "roleDecision = Unrelated_ReduceRole("),
        ("OverworldMount_TryStartCustomMotion", "wrong mounted role", "OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED\n            |", "OVERWORLD_ROLE_CONTROLLER_ROLE_WILD\n            |"),
        ("OverworldMount_TryStartCustomMotion", "wrong mounted intent", "? OVERWORLD_ROLE_CONTROLLER_INTENT_HOP", "? OVERWORLD_ROLE_CONTROLLER_INTENT_WALK"),
        ("OverworldMount_TryStartCustomMotion", "wrong mounted event byte", "OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST << 8", "OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST << 16"),
        ("OverworldMount_TryStartCustomMotion", "wrong mounted output byte", "(request >> 8) + 5", "(request >> 8) + 4"),
        ("OverworldMount_TryStartCustomMotion", "ignored mounted rejection", "direction > OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX", "direction < OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX"),
        ("OverworldMount_StartWalkCrash", "wrong RAM byte", "OVERWORLD_ROLE_CONTROLLER_INPUT_RAM << 8", "OVERWORLD_ROLE_CONTROLLER_INPUT_RAM << 16"),
        ("OverworldMount_StartWalkCrash", "crash output ignored", "!= OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH", "== OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH"),
        ("OverworldWildSpawns_HandleLockedWalkCrash", "wrong terminal consumption", "== OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH\n", "!= OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH\n"),
    )
    for root, label, old, new in changes:
        fixture, intent = fixtures[root]
        changed = fixture.replace(old, new, 1)
        if changed == fixture:
            raise SystemExit(f"packed role mutation did not apply: {label}")
        # A comment or unrelated (void) marker must not rescue a broken route.
        changed += f"\nvoid Unrelated(void) {{ (void){ROLE}ROLE_MOUNTED; (void){ROLE}INTENT_HOP; }}\n/* {old} */"
        if not packed_role_path_errors(changed, root, intent):
            raise SystemExit(f"packed role verifier accepted mutation: {label}")
    print(f"packed role caller/transport checks passed; {len(changes)} known-bad copies rejected", flush=True)


def has_semantic_controller_path(
    source: str,
    root: str,
    semantic_markers: Iterable[str],
    controller_markers: Iterable[str],
) -> bool:
    """Require the semantic value and reducer on one real call path."""
    if root in PACKED_ROLE_ROOTS:
        intent = next((marker.removeprefix(ROLE + "INTENT_")
                       for marker in semantic_markers
                       if marker.startswith(ROLE + "INTENT_")), "WALK")
        return not packed_role_path_errors(source, root, intent)
    reachable = reachable_functions(source, root)
    if reachable is None:
        return False
    semantic = tuple(semantic_markers)
    controller = tuple(controller_markers)
    for body in reachable.values():
        clean_body = strip_c_noncode(body)
        if (all(marker in clean_body for marker in semantic)
                and all(marker in clean_body for marker in controller)):
            return True
        for called, arguments in call_arguments(body):
            callee = reachable.get(called)
            if (callee is not None
                    and all(marker in arguments for marker in semantic)
                    and all(marker in strip_c_noncode(callee)
                        for marker in controller)):
                return True
    return False


def run_static_audit_mutation_tests() -> None:
    controller = """
static void RoleRequest(unsigned role, unsigned intent)
{
    OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST;
    OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT;
    OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
    OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER;
    reduceRole(role, intent);
}
"""
    generic = controller + """
static void HopRoot(void)
{
    RoleRequest(OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        OVERWORLD_ROLE_CONTROLLER_INTENT_HOP);
}
"""
    markers = REQUEST_MARKERS + (
        "OVERWORLD_ROLE_CONTROLLER_ROLE_WILD",
        "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER",
    )
    if not has_semantic_controller_path(
            generic,
            "HopRoot",
            ("OVERWORLD_ROLE_CONTROLLER_INTENT_HOP",),
            markers):
        raise SystemExit("role-controller verifier rejected a typed helper path")

    unrelated = controller + """
static void HopRoot(void)
{
    (void)OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
    RoleRequest(OVERWORLD_ROLE_CONTROLLER_ROLE_WILD, 1);
}
"""
    if has_semantic_controller_path(
            unrelated,
            "HopRoot",
            ("OVERWORLD_ROLE_CONTROLLER_INTENT_HOP",),
            markers):
        raise SystemExit(
            "role-controller verifier accepted an unrelated request path"
        )

    comment_only = """
static void HopRoot(void)
{
    /* OVERWORLD_ROLE_CONTROLLER_INTENT_HOP;
     * OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST;
     * OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT;
     * OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
     * OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER;
     * reduceRole(); */
}
"""
    if has_semantic_controller_path(
            comment_only,
            "HopRoot",
            ("OVERWORLD_ROLE_CONTROLLER_INTENT_HOP",),
            markers):
        raise SystemExit(
            "role-controller verifier accepted comment-only evidence"
        )


def follower_release_adapter_errors(source: str) -> list[str]:
    errors: list[str] = []
    bodies = function_bodies(source)
    helper = strip_c_noncode(bodies.get(
        "OverworldFollowerTransitionQueue_RequestRelease", ""))
    tick = strip_c_noncode(bodies.get(
        "OverworldFollowerTransitionQueue_Tick", ""))
    if not helper:
        return ["missing Follower Release request helper"]
    if not tick:
        return ["missing Follower transition queue tick"]
    for marker in (
        "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER",
        "OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST",
        "OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE",
        "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole",
        "OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT",
    ):
        if marker not in helper:
            errors.append(f"Follower Release helper lacks {marker}")
    if "OverworldRoleController_Reduce" in helper:
        errors.append("Follower Release helper duplicates the resident reducer")
    if helper.count("OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(") != 1:
        errors.append("Follower Release helper must call the resident reducer once")
    request_call = "OverworldFollowerTransitionQueue_RequestRelease()"
    if tick.count(request_call) != 1:
        errors.append("Follower Release must have one queue-head call site")
    for marker in (
        "FOLLOWER_TRANSITION_HEAD_RELEASE_ACCEPTED",
        "FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED",
        "FOLLOWER_TRANSITION_HEAD_ENGINE_ISSUED",
    ):
        if marker not in tick:
            errors.append(f"Follower Release queue state lacks {marker}")
    if not re.search(
            r"if\s*\(\s*OVERWORLD_FOLLOWER_TRANSITION_QUEUE"
            r"->headIssued\s*==\s*0\s*\)", tick):
        errors.append("Follower Release is not guarded as a one-shot request")
    if not re.search(
            r"OverworldFollowerTransitionQueue_RequestRelease\(\)\s*"
            r"\?\s*FOLLOWER_TRANSITION_HEAD_RELEASE_ACCEPTED\s*"
            r":\s*FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED", tick):
        errors.append("Follower Release decision is not latched on the queue head")
    if not re.search(
            r"if\s*\([^{};]*headIssued[^{};]*"
            r"FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED[^{};]*\)"
            r"\s*\{\s*return\s*;\s*\}", tick, re.DOTALL):
        errors.append("Follower Release rejection does not fail closed")
    if re.search(r"headIssued\s*=\s*(?:FALSE|0)\s*;", tick):
        errors.append("Follower Release retry clears the one-shot latch")
    if "headIssued =\n                        FOLLOWER_TRANSITION_HEAD_RELEASE_ACCEPTED" not in tick:
        errors.append("Follower recall retry does not preserve Release acceptance")
    request_index = tick.find(request_call)
    engine_calls = (
        "OverworldFollowerRecall_Begin(",
        "OverworldFollowerRecall_Tick(",
        "OverworldWildSpawns_SelectFollowerPartySlot(",
    )
    first_engine = min(
        (index for marker in engine_calls
         if (index := tick.find(marker)) >= 0),
        default=-1,
    )
    if request_index < 0 or first_engine < 0 or request_index > first_engine:
        errors.append("Follower engine work can start before Release acceptance")
    for marker in engine_calls:
        if marker in helper:
            errors.append("Follower Release helper performs engine work")
    return errors


def run_follower_release_mutation_tests(source: str) -> None:
    failures = follower_release_adapter_errors(source)
    if failures:
        raise SystemExit("invalid Follower Release adapter: " + "; ".join(failures))
    mutations = {
        "wrong role": source.replace(
            "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER,\n"
            "        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST,",
            "OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED,\n"
            "        OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST,",
            1,
        ),
        "direct reducer": source.replace(
            "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(&input, &output);",
            "OverworldRoleController_Reduce(&input, &output);",
            1,
        ),
        "duplicate publish": source.replace(
            "OverworldFollowerTransitionQueue_RequestRelease()\n",
            "OverworldFollowerTransitionQueue_RequestRelease(),\n"
            "                  OverworldFollowerTransitionQueue_RequestRelease()\n",
            1,
        ),
        "missing accepted latch": source.replace(
            "? FOLLOWER_TRANSITION_HEAD_RELEASE_ACCEPTED\n"
            "                    : FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED;",
            "? FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED\n"
            "                    : FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED;",
            1,
        ),
        "retry clears latch": source.replace(
            "OVERWORLD_FOLLOWER_TRANSITION_QUEUE->headIssued =\n"
            "                        FOLLOWER_TRANSITION_HEAD_RELEASE_ACCEPTED;",
            "OVERWORLD_FOLLOWER_TRANSITION_QUEUE->headIssued = FALSE;",
            1,
        ),
        "rejection continues": source.replace(
            "== FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED) {\n"
            "            return;\n"
            "        }",
            "== FOLLOWER_TRANSITION_HEAD_RELEASE_REJECTED) {\n"
            "            (void)fieldSystem;\n"
            "        }",
            1,
        ),
        "engine before intent": source.replace(
            "if (OVERWORLD_FOLLOWER_TRANSITION_QUEUE->headIssued == 0) {",
            "OverworldFollowerRecall_Begin(fieldSystem);\n"
            "        if (OVERWORLD_FOLLOWER_TRANSITION_QUEUE->headIssued == 0) {",
            1,
        ),
    }
    for label, mutated in mutations.items():
        if mutated == source:
            raise SystemExit(f"Follower Release mutation did not apply: {label}")
        if not follower_release_adapter_errors(mutated):
            raise SystemExit(
                f"Follower Release verifier accepted mutation: {label}"
            )


class SourceAudit:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def require(self, source: str, fragment: str, label: str) -> None:
        if fragment not in source:
            self.failures.append(f"missing {label}: {fragment}")

    def forbid(self, source: str, fragment: str, label: str) -> None:
        if fragment in source:
            self.failures.append(f"stale {label}: {fragment}")

    def require_path(
        self,
        source: str,
        root: str,
        fragments: Iterable[str],
        label: str,
    ) -> None:
        body = reachable_body(source, root)
        if body is None:
            self.failures.append(f"missing {label} root: {root}")
            return
        missing = [fragment for fragment in fragments if fragment not in body]
        if missing:
            self.failures.append(
                f"incomplete {label} path {root}: " + ", ".join(missing)
            )

    def require_semantic_path(
        self,
        source: str,
        root: str,
        semantic_markers: Iterable[str],
        controller_markers: Iterable[str],
        label: str,
    ) -> None:
        if root not in function_bodies(source):
            self.failures.append(f"missing {label} root: {root}")
            return
        if not has_semantic_controller_path(
                source, root, semantic_markers, controller_markers):
            self.failures.append(
                f"missing co-located semantic controller path for {label}: "
                f"{root}"
            )

    def finish(self) -> None:
        if not self.failures:
            return
        for failure in self.failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(
            f"{len(self.failures)} role-controller source checks failed"
        )


REQUEST_MARKERS = (
    "OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST",
    "OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT",
    "reduceRole(",
)


def main() -> int:
    if len(sys.argv) > 2 or (
            len(sys.argv) == 2 and sys.argv[1] != "--controller-only"):
        raise SystemExit(
            "usage: verify_overworld_role_controller.py [--controller-only]"
        )
    controller_only = len(sys.argv) == 2
    compiler = shlex.split(os.environ.get("CC", "cc"))
    if not compiler:
        raise SystemExit("CC must name a C compiler")
    with tempfile.TemporaryDirectory(prefix="overworld-role-controller-") as directory:
        executable = Path(directory) / "overworld-role-controller"
        command = compiler + [
            "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-DOVERWORLD_ROLE_CONTROLLER_HOST=1",
            "-I", str(ROOT / "include"),
            str(ROOT / "lib/overworld/overworld_role_controller.c"),
            str(ROOT / "tools/overworld_role_controller_harness.c"),
            "-o", str(executable),
        ]
        subprocess.run(command, cwd=ROOT, check=True, timeout=30)
        subprocess.run([str(executable)], cwd=ROOT, check=True, timeout=30)
    run_static_audit_mutation_tests()
    print("role-controller source-audit mutation checks passed", flush=True)
    if controller_only:
        print("pure role-controller host checks passed")
        return 0

    role_header = (ROOT / "include/overworld_role_controller.h").read_text()
    runtime_header = (ROOT / "include/overworld_wild_runtime.h").read_text()
    runtime = (ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
    runtime_linker = (ROOT / "src/overworld_wild_runtime_overlay/linker.ld").read_text()
    task6_linker = (ROOT / "src/pokemon_move_history_task6_overlay/linker.ld").read_text()
    overlays = (ROOT / "overlays.mk").read_text()
    packager = (ROOT / "scripts/make.py").read_text()
    wild = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    mount = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    walk = (ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c").read_text()
    follower = (ROOT / "src/overworld_follower_selector_overlay/follower_selector_input.c").read_text()
    actor = (ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
    movement_header = (ROOT / "include/overworld_wild_movement.h").read_text()
    run_packed_role_mutation_tests(wild, mount)
    run_follower_release_mutation_tests(follower)
    print("Follower Release adapter mutation checks passed", flush=True)
    require(runtime, "OverworldRoleController_Reduce", "portable runtime adapter")
    require(runtime_header, "OverworldWildRuntimeReduceRoleFunc reduceRole", "fixed runtime role-controller slot")
    require(runtime_header, "#define OVERWORLD_WILD_RUNTIME_VERSION 16", "runtime service version")
    require(runtime_header, "OverworldWildRuntimeBindActorFunc bindActor", "single-actor binding callback")
    forbid(runtime_header, "reservedResolverCallbacks", "retired resolver callback slots")
    require(runtime, "entry->reduceRole == OverworldRoleController_Reduce", "runtime role-controller validation")
    require(runtime_linker, "OverworldRoleController_Reduce = 0x023BE240 | 1", "resident role-controller import")
    require(task6_linker, "KEEP(*(.text.OverworldRoleController_Reduce))", "resident role-controller code home")
    require(overlays, "OVERWORLD_TASK6_PORTABLE_OBJS", "portable role-controller build input")
    require(packager, "expected_header = (0x3152574F, 16, expected_entry_size)", "runtime package version")
    audit = SourceAudit()
    audit.require_semantic_path(
        wild,
        "OverworldWildSpawns_TryStartAcceleratedWalkStep",
        ("OVERWORLD_ROLE_CONTROLLER_INTENT_WALK",),
        REQUEST_MARKERS + (
            "OVERWORLD_ROLE_CONTROLLER_ROLE_WILD",
            "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER",
            "roleOutput.direction",
        ),
        "Wild/Follower Walk request",
    )
    audit.require_semantic_path(
        wild,
        "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand",
        ("OVERWORLD_ROLE_CONTROLLER_INTENT_HOP",),
        REQUEST_MARKERS + (
            "OVERWORLD_ROLE_CONTROLLER_ROLE_WILD",
            "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER",
        ),
        "Wild/Follower Hop request",
    )
    for function in (
        "OverworldWildSpawns_TryStartChillTeleportMovementCommand",
        "OverworldWildSpawns_TryStartTeleportMovementCommand",
    ):
        audit.require_semantic_path(
            wild,
            function,
            ("OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT",),
            REQUEST_MARKERS + (
                "OVERWORLD_ROLE_CONTROLLER_ROLE_WILD",
                "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER",
            ),
            "Wild/Follower Teleport request",
        )
    audit.require_semantic_path(
        walk,
        "OverworldWalk_FilterMountedInput",
        ("OVERWORLD_ROLE_CONTROLLER_INTENT_WALK",),
        REQUEST_MARKERS + (
            "OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED",
            "roleOutput.direction",
        ),
        "Mounted Walk request",
    )
    for intent, label in (
        ("OVERWORLD_ROLE_CONTROLLER_INTENT_HOP", "Mounted Hop request"),
        (
            "OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT",
            "Mounted Teleport request",
        ),
    ):
        audit.require_semantic_path(
            mount,
            "OverworldMount_TryStartCustomMotion",
            (intent,),
            REQUEST_MARKERS + (
                "OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED",
            ),
            label,
        )
    audit.require_semantic_path(
        follower,
        "OverworldFollowerTransitionQueue_Tick",
        ("OVERWORLD_ROLE_CONTROLLER_INTENT_RELEASE",),
        REQUEST_MARKERS + (
            "OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER",
        ),
        "Follower release request",
    )

    if "OVERWORLD_ROLE_CONTROLLER_ROLE_SCRIPTED" in role_header:
        scripted_found = False
        for path in (ROOT / "src").rglob("*.c"):
            source = path.read_text(errors="replace")
            if "OVERWORLD_ROLE_CONTROLLER_ROLE_SCRIPTED" not in source:
                continue
            for function, direct_body in function_bodies(source).items():
                if "OVERWORLD_ROLE_CONTROLLER_ROLE_SCRIPTED" not in direct_body:
                    continue
                if has_semantic_controller_path(
                        source,
                        function,
                        ("OVERWORLD_ROLE_CONTROLLER_ROLE_SCRIPTED",),
                        REQUEST_MARKERS):
                    scripted_found = True
                    break
            if scripted_found:
                break
        if not scripted_found:
            audit.failures.append(
                "public reducer advertises deferred Scripted role without "
                "a production adapter"
            )

    audit.require_semantic_path(
        wild,
        "OverworldWildSpawns_HandleLockedWalkCrash",
        (
            "OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED",
            "OVERWORLD_ROLE_CONTROLLER_INPUT_RAM",
        ),
        (
            "OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH",
            "reduceRole(",
        ),
        "Wild/Follower Ram blocked terminal",
    )
    audit.require_semantic_path(
        mount,
        "OverworldMount_StartWalkCrash",
        (
            "OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED",
            "OVERWORLD_ROLE_CONTROLLER_INPUT_RAM",
        ),
        (
            "OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED",
            "OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH",
            "OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT",
            "reduceRole(",
        ),
        "Mounted Ram blocked terminal",
    )
    audit.forbid(
        mount,
        "OverworldMount_ResetMomentum(OVERWORLD_ACTOR_WORLD_EFFECT_CRASH)",
        "mounted crash through RESET side channel",
    )
    audit.forbid(
        reachable_body(runtime, "OverworldActorWalkPolicy_Reduce") or "",
        "policy->deferredChainPauseAction = 0x80 | call->direction",
        "RESET effect stored as a chain action",
    )
    audit.forbid(
        reachable_body(actor, "ActorSystem_SyncLegacyActor") or "",
        ".deferredChainPauseAction & 0x80",
        "mounted effect published from chain storage",
    )
    audit.require(
        movement_header,
        "OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT",
        "typed actor-owned effect publication operation",
    )

    commit_body = reachable_body(
        actor, "ActorSystem_TryAcknowledgeMotionCommit") or ""
    audit.require(
        commit_body,
        "motion->plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NORMAL",
        "semantic commit-policy receipt guard",
    )
    audit.require(
        commit_body,
        "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN",
        "Hop/Teleport semantic chain receipt",
    )
    chain_body = reachable_body(
        runtime, "OverworldActorWalkPolicy_ReduceChain") or ""
    receipt = chain_body.find(
        "policy->pendingStep != OVERWORLD_ACTOR_WALK_PENDING_CHAIN")
    walk_gate = chain_body.find(
        "call->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK")
    if receipt < 0 or (walk_gate >= 0 and walk_gate < receipt):
        audit.failures.append(
            "chain receipt guard is still limited to Walk locomotion"
        )
    audit.require(
        chain_body,
        "policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE",
        "one-shot semantic chain receipt consumption",
    )
    audit.require_path(
        runtime,
        "OverworldWildRuntime_RequestMotion",
        (
            "OVERWORLD_MOTION_COMMIT_NO_CHAIN",
            "OVERWORLD_MOTION_COMMIT_NORMAL",
            "OVERWORLD_MOTION_KIND_REPOSITION",
        ),
        "reposition chain exclusion",
    )

    audit.require_path(
        wild,
        "OverworldWildSpawns_CommitDeferredChainMovementPause",
        (
            "OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT",
            "OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING",
            "OVERWORLD_ACTOR_WALK_POLICY_CHAIN_PUT_PENDING",
            "state->movementCooldowns[slot] = 1",
        ),
        "chain terminal retry transaction",
    )
    audit.forbid(
        mount,
        "sOverworldWildSpawnState.movementCooldowns[OW_WILD_FOLLOWER_SLOT]",
        "mounted direct Wild AI cooldown ownership",
    )

    provider_sources = [
        (ROOT / "lib/overworld/overworld_role_controller.c").read_text()
    ] + [path.read_text(errors="replace") for path in (ROOT / "src").rglob("*.c")]
    provider_definition = re.compile(
        r"\bvoid\s+OverworldRoleController_Reduce\s*\(")
    provider_count = sum(
        len(provider_definition.findall(strip_c_noncode(source)))
        for source in provider_sources
    )
    if provider_count != 1:
        audit.failures.append(
            "role reducer must have one implementation; "
            f"found {provider_count}"
        )
    for label, source in (
        ("Wild", wild),
        ("Mount", mount),
        ("Walk", walk),
        ("Follower", follower),
        ("Actor", actor),
    ):
        if provider_definition.search(strip_c_noncode(source)):
            audit.failures.append(
                f"{label} adapter has a duplicate role reducer implementation"
            )
    audit.finish()
    print("overworld role-controller source ownership checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

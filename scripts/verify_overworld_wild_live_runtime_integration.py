#!/usr/bin/env python3
"""Verify the live stackable-profile integration contract.

This is intentionally a source-shape verifier, not a replacement for the C
compiler or the runtime scenarios.  It keeps the integration gate aligned
with the one-state V40 architecture: effective stack state is authoritative,
presentation mirrors are not behavior state, asynchronous work is generation
authenticated, and lifecycle/possession paths reconcile the effective entry.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPAWNS = (
    ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)
DEFAULT_STATE = ROOT / "include/overworld_wild_spawns_internal.h"
DEFAULT_HELPER = (
    ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
)
DEFAULT_SIDECARS = (
    ROOT
    / "src/overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"
)


class SourceShapeError(ValueError):
    pass


def mask_non_code(source: str) -> str:
    """Blank comments and literals while preserving byte offsets/newlines."""

    result = list(source)
    index = 0
    state = "code"
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == "/" and following == "/":
                result[index] = result[index + 1] = " "
                state = "line"
                index += 2
                continue
            if char == "/" and following == "*":
                result[index] = result[index + 1] = " "
                state = "block"
                index += 2
                continue
            if char == '"':
                result[index] = " "
                state = "string"
            elif char == "'":
                result[index] = " "
                state = "character"
        elif state == "line":
            if char == "\n":
                state = "code"
            else:
                result[index] = " "
        elif state == "block":
            if char == "*" and following == "/":
                result[index] = result[index + 1] = " "
                state = "code"
                index += 2
                continue
            if char != "\n":
                result[index] = " "
        else:
            if char == "\\":
                result[index] = " "
                if index + 1 < len(source):
                    if source[index + 1] != "\n":
                        result[index + 1] = " "
                    index += 2
                    continue
            if (state == "string" and char == '"') or (
                state == "character" and char == "'"
            ):
                result[index] = " "
                state = "code"
            elif char != "\n":
                result[index] = " "
        index += 1
    return "".join(result)


def matching_delimiter(source: str, start: int, opening: str, closing: str) -> int:
    if start < 0 or start >= len(source) or source[start] != opening:
        raise SourceShapeError(f"expected {opening!r} at offset {start}")
    depth = 1
    for index in range(start + 1, len(source)):
        if source[index] == opening:
            depth += 1
        elif source[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    raise SourceShapeError(f"unclosed {opening!r} at offset {start}")


def function_body(source: str, name: str) -> str:
    code = mask_non_code(source)
    for match in re.finditer(r"\b" + re.escape(name) + r"\s*\(", code):
        opening = code.find("(", match.start())
        closing = matching_delimiter(code, opening, "(", ")")
        cursor = closing + 1
        while cursor < len(code) and code[cursor].isspace():
            cursor += 1
        if cursor < len(code) and code[cursor] == "{":
            end = matching_delimiter(code, cursor, "{", "}")
            return code[cursor + 1 : end]
    raise SourceShapeError(f"missing function definition {name}")


def struct_body(source: str, name: str) -> str:
    code = mask_non_code(source)
    match = re.search(r"\btypedef\s+struct\s+" + re.escape(name) + r"\b", code)
    if match is None:
        raise SourceShapeError(f"missing struct {name}")
    opening = code.find("{", match.end())
    closing = matching_delimiter(code, opening, "{", "}")
    return code[opening + 1 : closing]


def normalized(source: str) -> str:
    return re.sub(r"\s+", "", source)


def has_call(body: str, name: str) -> bool:
    return re.search(r"\b" + re.escape(name) + r"\s*\(", body) is not None


def if_blocks(body: str) -> list[tuple[str, str, int, int]]:
    """Return syntactic if conditions and their immediate then bodies."""

    blocks: list[tuple[str, str, int, int]] = []
    for match in re.finditer(r"\bif\s*\(", body):
        opening = body.find("(", match.start())
        closing = matching_delimiter(body, opening, "(", ")")
        cursor = closing + 1
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor < len(body) and body[cursor] == "{":
            end = matching_delimiter(body, cursor, "{", "}")
            then_body = body[cursor + 1 : end]
        else:
            end = body.find(";", cursor)
            if end < 0:
                continue
            then_body = body[cursor : end + 1]
        blocks.append((body[opening + 1 : closing], then_body, match.start(), end))
    return blocks


def block_with_condition(body: str, fragment: str) -> tuple[str, str, int, int] | None:
    compact_fragment = normalized(fragment)
    for block in if_blocks(body):
        if compact_fragment in normalized(block[0]):
            return block
    return None


@dataclass(frozen=True)
class Sources:
    spawns: str
    state: str
    helper: str
    sidecars: str


class IntegrationVerifier:
    def __init__(self, sources: Sources):
        self.sources = sources
        self.issues: list[str] = []

    def issue(self, category: str, message: str) -> None:
        self.issues.append(f"{category}: {message}")

    def body(self, name: str, category: str) -> str | None:
        try:
            return function_body(self.sources.spawns, name)
        except SourceShapeError as error:
            self.issue(category, str(error))
            return None

    def structure(self, source: str, name: str, category: str) -> str | None:
        try:
            return struct_body(source, name)
        except SourceShapeError as error:
            self.issue(category, str(error))
            return None

    def require_calls(
        self, body: str, category: str, owner: str, names: tuple[str, ...]
    ) -> None:
        for name in names:
            if not has_call(body, name):
                self.issue(category, f"{owner} must call {name}")

    def verify_layout(self) -> None:
        category = "runtime-layout"
        live = self.structure(
            self.sources.spawns, "OverworldWildOverlayRuntimeState", category
        )
        state = self.structure(
            self.sources.state, "OverworldWildSpawnState", category
        )
        command = self.structure(
            self.sources.sidecars, "OverworldWildRuntimeCommandOrigin", category
        )
        if live is not None:
            for field in (
                "pickupRelations",
                "movementCommandOrigins",
                "behaviorStackRuntime",
            ):
                if re.search(r"\b" + field + r"\b", live) is None:
                    self.issue(category, f"live runtime is missing {field}")
            if live.find("movementCommandOrigins") > live.find("behaviorStackRuntime"):
                self.issue(category, "behavior stack must remain the resident suffix")
            if re.search(r"\bobjectId\b", live):
                self.issue(category, "live runtime must authenticate object generations, not objectId")
        suffix_assert = "OverworldWildBehaviorStackRuntimeMustRemainResidentSuffix"
        if suffix_assert not in self.sources.spawns:
            self.issue(category, "resident behavior-stack suffix assertion is missing")
        if state is not None:
            if "movementRuntimeState" not in state:
                self.issue(category, "spawn state does not retain the runtime pointer")
            if re.search(r"\bmovementBehaviorClasses\b", state):
                self.issue(category, "movementBehaviorClasses remains live behavior authority")
        if command is not None:
            for identity in (
                "slotGeneration",
                "commandGeneration",
                "commandSerial",
                "objectGeneration",
                "winningEntryGeneration",
                "effectiveGeneration",
            ):
                if re.search(r"\b" + identity + r"\b", command) is None:
                    self.issue(category, f"command origin is missing {identity}")
            if re.search(r"\bobjectId\b", command):
                self.issue(category, "command origin still authenticates by objectId")

    def verify_effective_authority(self) -> None:
        category = "effective-authority"
        current = self.body("OverworldWildSpawns_GetCurrentBehavior", category)
        if current is not None:
            self.require_calls(
                current,
                category,
                "GetCurrentBehavior",
                ("OverworldWildRuntime_GetEffectiveCache",),
            )
            compact = normalized(current)
            if "behaviorStackRuntime.slots[slot].slotGeneration" not in compact:
                self.issue(category, "effective-cache lookup is not bound to slot generation")
            if (
                "movementPresentationStates" in current
                or "OverworldWildSpawns_GetMovementPresentationState" in current
                or "movementBehaviorClasses" in current
            ):
                self.issue(category, "effective lookup reads a presentation/legacy mirror")

        for name in (
            "OverworldWildSpawns_EffectiveRoleIs",
            "OverworldWildSpawns_EffectiveRoleIsTired",
        ):
            body = self.body(name, category)
            if body is None:
                continue
            self.require_calls(body, category, name, ("OverworldWildSpawns_GetCurrentBehavior",))
            if "semanticRole" not in body:
                self.issue(category, f"{name} does not read the winning semantic role")

        for name in (
            "OverworldWildSpawns_TryStartBattle",
            "OverworldWildSpawns_CopySpawnConfiguration",
            "OverworldWildSpawns_ReconcileRuntimeEffectiveEntry",
        ):
            body = self.body(name, category)
            if body is not None and "movementBehaviorClasses" in body:
                self.issue(category, f"{name} reads removed behavior-class authority")

        obsolete = (
            "OverworldWildSpawns_GetBehaviorProfile(",
            "OverworldWildSpawns_GetMovementTickProfile(",
            "OverworldWildSpawns_ResolveBehaviorPrimitives(",
            "OverworldWildSpawns_ApplyBehaviorOverride(",
            "OverworldWildSpawns_RestorePickedUpBehaviorClass(",
            "OverworldWildSpawns_StartTiredEmoteWithProfile(",
        )
        for spelling in obsolete:
            if spelling in self.sources.spawns:
                self.issue(category, f"obsolete multi-state wrapper remains: {spelling[:-1]}")

    def verify_reconciliation(self) -> None:
        category = "action-reconciliation"
        dispatch = self.body("OverworldWildSpawns_TryDispatchRuntimeTransition", category)
        if dispatch is not None:
            self.require_calls(
                dispatch,
                category,
                "TryDispatchRuntimeTransition",
                (
                    "OverworldWildRuntime_DispatchTransition",
                    "OverworldWildSpawns_ReconcileRuntimeEffectiveEntry",
                ),
            )
            compact = normalized(dispatch)
            if "transition.effectiveAfter,transition.actionFlags" not in compact:
                self.issue(category, "transition result is not reconciled with its action flags")
            dispatch_at = dispatch.find("OverworldWildRuntime_DispatchTransition")
            reconcile_at = dispatch.find("OverworldWildSpawns_ReconcileRuntimeEffectiveEntry")
            if dispatch_at < 0 or reconcile_at < dispatch_at:
                self.issue(category, "effective entry is reconciled before transition commit")

        reconcile = self.body("OverworldWildSpawns_ReconcileRuntimeEffectiveEntry", category)
        if reconcile is not None:
            self.require_calls(
                reconcile,
                category,
                "ReconcileRuntimeEffectiveEntry",
                ("OverworldWildSpawns_ProjectRuntimeEffectiveBehavior",),
            )
            for field in ("beforeNodeId", "after->nodeId", "actionFlags", "semanticRole"):
                if field not in reconcile:
                    self.issue(category, f"reconciliation is missing {field}")
            if (
                "movementPresentationStates" in reconcile
                or "OverworldWildSpawns_GetMovementPresentationState" in reconcile
            ):
                self.issue(category, "reconciliation treats presentation mirror as behavior state")

    def verify_presentation_authority(self) -> None:
        category = "typed-presentation-authority"
        state = self.structure(
            self.sources.state, "OverworldWildSpawnState", category
        )
        if state is not None and re.search(
            r"\bu8\s+movementPresentationStates\s*\[\s*OW_WILD_MAX_SPAWNS\s*\]",
            state,
        ) is None:
            self.issue(category, "spawn state lacks the byte-sized presentation field")

        for name, enum_name in (
            (
                "OverworldWildSpawns_GetMovementPresentationState",
                "OverworldWildMovementPresentationState",
            ),
            (
                "OverworldWildSpawns_SetMovementPresentationState",
                "OverworldWildMovementPresentationState",
            ),
        ):
            try:
                body = function_body(self.sources.state, name)
            except SourceShapeError as error:
                self.issue(category, str(error))
                continue
            if enum_name not in self.sources.state or "movementPresentationStates" not in body:
                self.issue(category, f"{name} is not the typed field boundary")

        for enum_name in (
            "OW_WILD_MOVEMENT_PRESENTATION_NONE",
            "OW_WILD_MOVEMENT_PRESENTATION_SPOT_EMOTE",
        ):
            if enum_name not in self.sources.state:
                self.issue(category, f"missing explicit presentation enum {enum_name}")

        if self.sources.state.count("movementPresentationStates") != 3:
            self.issue(category, "presentation field is accessed outside its declaration/get/set boundary")
        for label, source in (
            ("spawn overlay", self.sources.spawns),
            ("helper overlay", self.sources.helper),
        ):
            if "movementPresentationStates" in source:
                self.issue(category, f"{label} bypasses the typed presentation API")
            if re.search(
                r"OverworldWildSpawns_GetMovementPresentationState\s*\([^()]*\)\s*"
                r"(?:==|!=)\s*[01]\b",
                mask_non_code(source),
            ):
                self.issue(category, f"{label} compares presentation state numerically")

        if "OverworldWildSpawns_SetMovementPresentationState" not in self.sources.spawns:
            self.issue(category, "spawn overlay does not publish presentation state through the typed API")
        if "OverworldWildSpawns_GetMovementPresentationState" not in self.sources.spawns:
            self.issue(category, "spawn overlay does not gate presentation through the typed API")
        if "OverworldWildSpawns_GetMovementPresentationState" not in self.sources.helper:
            self.issue(category, "helper overlay does not gate presentation through the typed API")

    def verify_pending_work(self) -> None:
        category = "authenticated-pending-work"
        dispatch = self.body("OverworldWildSpawns_TryDispatchRuntimeTransition", category)
        if dispatch is not None:
            busy = block_with_condition(
                dispatch, "status == OW_WILD_RUNTIME_STATUS_DATA_BUSY"
            )
            if busy is None:
                self.issue(category, "DATA_BUSY retention guard is missing")
                busy_body = ""
            else:
                busy_body = normalized(busy[1])
            for field in (
                "movementPendingRuntimeTransitions[slot]",
                "movementEmoteSlotGenerations[slot]",
                "movementPendingObjectGenerations[slot]",
                "movementObjectGenerations[slot]",
            ):
                if field not in busy_body:
                    self.issue(category, f"busy transition does not retain {field}")
            if busy is not None and (
                "movementEmoteSlotGenerations[slot]=slotGeneration" not in busy_body
                or "movementPendingObjectGenerations[slot]=runtime->movementObjectGenerations[slot]"
                not in busy_body
                or "returnFALSE" not in busy_body
            ):
                self.issue(category, "DATA_BUSY guard does not atomically retain slot/object identity before returning")

        retry = self.body("OverworldWildSpawns_RetryPendingRuntimeTransitions", category)
        if retry is not None:
            invalid = block_with_condition(retry, "!state->spawns[slot].active")
            invalid_condition = normalized(invalid[0]) if invalid is not None else ""
            invalid_body = normalized(invalid[1]) if invalid is not None else ""
            for comparison in (
                "runtime->movementEmoteSlotGenerations[slot]!=runtime->behaviorStackRuntime.slots[slot].slotGeneration",
                "runtime->movementPendingObjectGenerations[slot]!=runtime->movementObjectGenerations[slot]",
            ):
                if comparison not in invalid_condition:
                    self.issue(category, f"retry authentication is missing {comparison}")
            if invalid is None or (
                "OverworldWildSpawns_ClearPendingRuntimeTransition(runtime,slot)"
                not in invalid_body
                or "continue" not in invalid_body
            ):
                self.issue(category, "invalid pending identity is not cleared before retry dispatch")
            dispatch_position = retry.find("OverworldWildSpawns_TryDispatchRuntimeTransition")
            if invalid is not None and dispatch_position >= 0 and invalid[3] > dispatch_position:
                self.issue(category, "retry dispatch precedes slot/object authentication")
            self.require_calls(
                retry,
                category,
                "RetryPendingRuntimeTransitions",
                ("OverworldWildSpawns_TryDispatchRuntimeTransition",),
            )

        expiry = self.body(
            "OverworldWildSpawns_ProcessPendingRuntimeTimerExpiries", category
        )
        if expiry is not None:
            self.require_calls(
                expiry,
                category,
                "ProcessPendingRuntimeTimerExpiries",
                (
                    "OverworldWildRuntime_GetPendingTimerExpiryCount",
                    "OverworldWildRuntime_GetPendingTimerExpiryByIndex",
                    "OverworldWildRuntime_DispatchTransition",
                    "OverworldWildSpawns_ReconcileRuntimeEffectiveEntry",
                ),
            )
            compact = normalized(expiry)
            for ticket in (
                "event.replayExpiry=expiry",
                "event.flags=OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY",
                "expiry.slotIndex,expiry.slotGeneration",
                "transition.actionFlags",
            ):
                if ticket not in compact:
                    self.issue(category, f"timer replay is missing {ticket}")

        for name, runtime_name in (
            (
                "OverworldWildSpawns_CaptureMovementCommandOrigin",
                "OverworldWildRuntime_CaptureCommandOrigin",
            ),
            (
                "OverworldWildSpawns_ConsumeMovementCommandOrigin",
                "OverworldWildRuntime_ConsumeCommandOrigin",
            ),
        ):
            body = self.body(name, category)
            if body is not None:
                self.require_calls(body, category, name, (runtime_name,))
                for identity in (
                    "slotGeneration",
                    "commandGeneration",
                    "commandSerial",
                    "objectGeneration",
                    "staminaPolicyGeneration",
                ):
                    if identity not in body:
                        self.issue(category, f"{name} is missing {identity}")
                compact = normalized(body)
                status_guard = (
                    "if(status!=OW_WILD_RUNTIME_STATUS_OK){returnFALSE;}"
                )
                call_at = compact.find(runtime_name + "(")
                guard_at = compact.find(status_guard, call_at)
                if call_at < 0 or guard_at < call_at:
                    self.issue(category, f"{name} does not require exact OK status")
                object_identity = (
                    "identity.objectGeneration="
                    "runtime->movementObjectGenerations[slot]"
                )
                object_at = compact.find(object_identity)
                if object_at < 0 or call_at < object_at:
                    self.issue(
                        category,
                        f"{name} does not authenticate the current object generation",
                    )
                if name.endswith("CaptureMovementCommandOrigin"):
                    stamina_identity = (
                        "identity.staminaPolicyGeneration="
                        "effective.effectiveGeneration"
                    )
                    stamina_at = compact.find(stamina_identity)
                    if stamina_at < 0 or call_at < stamina_at:
                        self.issue(
                            category,
                            "capture does not authenticate the current stamina policy generation",
                        )
                    publish_at = compact.find(
                        "runtime->movementCommandGenerations[slot]=nextCommandGeneration"
                    )
                    if guard_at < 0 or publish_at < guard_at:
                        self.issue(category, "capture publishes command generation before exact OK")
                elif not compact.endswith("returnTRUE;") or guard_at > compact.rfind("returnTRUE;"):
                    self.issue(category, "consume returns success before exact OK")

    def verify_lifecycle(self) -> None:
        category = "map-battle-lifecycle"
        prepare = self.body("OverworldWildSpawns_PrepareMapHeaderChange", category)
        if prepare is not None:
            self.require_calls(
                prepare,
                category,
                "PrepareMapHeaderChange",
                (
                    "OverworldWildRuntime_RemoveBoundaryPolicySlotPhase",
                    "OverworldWildSpawns_DetachAllMovementStateOnContextLoss",
                ),
            )
            compact = normalized(prepare)
            for item in (
                "OW_WILD_RUNTIME_POLICY_BOUNDARY_MAP",
                "OW_WILD_RUNTIME_POLICY_BOUNDARY_BATTLE",
                "phase<2",
                "slot->slotGeneration",
            ):
                if item not in compact:
                    self.issue(category, f"lifecycle boundary is missing {item}")

        reset = self.body("OverworldWildSpawns_ResetSlotState", category)
        if reset is not None:
            self.require_calls(
                reset,
                category,
                "ResetSlotState",
                (
                    "OverworldWildSpawns_ClearThrowStateForSlot",
                    "OverworldWildRuntime_DestructivelyInvalidateSlot",
                ),
            )
            compact = normalized(reset)
            cleanup_guard = (
                "if(!OverworldWildSpawns_ClearThrowStateForSlot(state,slot))"
                "returnFALSE;"
            )
            cleanup_at = compact.find(cleanup_guard)
            invalidate_at = compact.find("OverworldWildRuntime_DestructivelyInvalidateSlot(")
            if cleanup_at < 0 or invalidate_at < cleanup_at + len(cleanup_guard):
                self.issue(category, "slot invalidation precedes possession cleanup")

        detach = self.body(
            "OverworldWildSpawns_DetachAllMovementStateOnContextLoss", category
        )
        if detach is not None:
            self.require_calls(
                detach,
                category,
                "DetachAllMovementStateOnContextLoss",
                (
                    "OverworldWildSpawns_InvalidateAllMovementCommandOrigins",
                    "OverworldWildSpawns_CancelDeferredBattleScript",
                    "OverworldWildSpawns_ResetPendingBattle",
                ),
            )

        battle = self.body("OverworldWildSpawns_OverlayCleanupPendingBattle", category)
        if battle is not None:
            if "OW_WILD_BATTLE_DISPOSITION_FLED" not in battle:
                self.issue(category, "battle cleanup does not retain the fled route")
            self.require_calls(
                battle,
                category,
                "OverlayCleanupPendingBattle",
                (
                    "OverworldWildSpawns_TryDispatchRuntimeTransition",
                    "OverworldWildSpawns_ResetPendingBattle",
                ),
            )
            if "OWBD_TRIGGER_FLED" not in battle:
                self.issue(category, "battle fled result is not dispatched through the controller")

    def verify_possession(self) -> None:
        category = "possession-reveal"
        relation = self.structure(
            self.sources.spawns, "OverworldWildPickupRelation", category
        )
        if relation is not None:
            for field in (
                "possessionHandle",
                "relationGeneration",
                "throwRelationGeneration",
                "throwCommandGeneration",
                "throwCommandSerial",
                "carrierSlotPlusOne",
                "cleanupPending",
            ):
                if re.search(r"\b" + field + r"\b", relation) is None:
                    self.issue(category, f"pickup relation is missing {field}")

        apply = self.body("OverworldWildSpawns_StartCarriedThrowTarget", category)
        if apply is not None:
            self.require_calls(
                apply,
                category,
                "StartCarriedThrowTarget",
                (
                    "OverworldWildSpawns_IsCurrentPickupRelation",
                    "OverworldWildRuntime_DispatchTransition",
                    "OverworldWildRuntime_FindLayer",
                ),
            )
            if "OWBD_TRIGGER_POSSESSION_APPLY" not in apply:
                self.issue(category, "pickup does not apply the possession controller transition")
            for identity in ("ownerId", "instanceKey", "slotGeneration"):
                if f"possessionHandle.{identity}" not in normalized(apply):
                    self.issue(category, f"possession handle is missing {identity}")
            compact = normalized(apply)
            dispatch_at = compact.find("status=OverworldWildRuntime_DispatchTransition(")
            dispatch_guard = compact.find(
                "if(status!=OW_WILD_RUNTIME_STATUS_OK){returnFALSE;}", dispatch_at
            )
            handle_write = compact.find("relation->possessionHandle.ownerId=")
            exact_find = (
                "OverworldWildRuntime_FindLayer(&runtime->behaviorStackRuntime,"
                "targetSlot,relation->possessionHandle.slotGeneration,"
                "transition.ownerId,transition.instanceKey,&layer,"
                "&relation->possessionHandle)!=OW_WILD_RUNTIME_STATUS_OK"
            )
            if (
                dispatch_at < 0
                or dispatch_guard < dispatch_at
                or handle_write < dispatch_guard
                or exact_find not in compact
            ):
                self.issue(category, "possession apply does not authenticate commit/handle identity before presentation")

        remove = self.body("OverworldWildSpawns_RemovePickupPossession", category)
        if remove is not None:
            self.require_calls(
                remove,
                category,
                "RemovePickupPossession",
                (
                    "OverworldWildRuntime_FindLayer",
                    "OverworldWildRuntime_Remove",
                    "OverworldWildSpawns_GetCurrentBehavior",
                    "OverworldWildSpawns_ReconcileRuntimeEffectiveEntry",
                ),
            )
            compact = normalized(remove)
            if "state,targetSlot,beforeNodeId,&current,0" not in compact:
                self.issue(category, "possession removal does not reveal/reconcile the underlying state")
            if "cleanupPending=TRUE" not in compact:
                self.issue(category, "failed possession removal is not retained for retry")
            exact_lookup = (
                "status=OverworldWildRuntime_FindLayer(&runtime->behaviorStackRuntime,"
                "targetSlot,relation->possessionHandle.slotGeneration,"
                "relation->possessionHandle.ownerId,"
                "relation->possessionHandle.instanceKey,&layer,&currentHandle)"
            )
            ok_block = block_with_condition(
                remove, "status == OW_WILD_RUNTIME_STATUS_OK"
            )
            ok_body = normalized(ok_block[1]) if ok_block is not None else ""
            if exact_lookup not in compact or ok_block is None:
                self.issue(category, "possession removal does not reauthenticate the exact stored handle")
            elif (
                "relation->possessionHandle=currentHandle" not in ok_body
                or "OverworldWildRuntime_Remove(" not in ok_body
                or ok_body.find("relation->possessionHandle=currentHandle")
                > ok_body.find("OverworldWildRuntime_Remove(")
            ):
                self.issue(category, "possession removal does not refresh the exact handle before remove")
            failure_at = compact.find("relation->cleanupPending=TRUE")
            reconcile_at = compact.find("OverworldWildSpawns_ReconcileRuntimeEffectiveEntry(")
            clear_at = compact.rfind("relation->cleanupPending=FALSE")
            if reconcile_at < 0 or clear_at < reconcile_at or failure_at < 0:
                self.issue(category, "possession cleanup publication ordering is invalid")

        clear = self.body("OverworldWildSpawns_ClearThrowStateForSlot", category)
        if clear is not None:
            compact = normalized(clear)
            remove_at = compact.find("OverworldWildSpawns_RemovePickupPossession(")
            clear_at = compact.find("helperEntry->clearPickupThrowState(")
            forget_at = compact.find("OverworldWildSpawns_ForgetPickupRelation(")
            if min(remove_at, clear_at, forget_at) < 0 or not (
                remove_at < clear_at < forget_at
            ):
                self.issue(category, "throw cleanup forgets/normalizes relation before stack removal")

    def verify(self) -> list[str]:
        self.verify_layout()
        self.verify_effective_authority()
        self.verify_reconciliation()
        self.verify_presentation_authority()
        self.verify_pending_work()
        self.verify_lifecycle()
        self.verify_possession()
        return self.issues


def verify_sources(spawns: str, state: str, helper: str, sidecars: str) -> list[str]:
    return IntegrationVerifier(Sources(spawns, state, helper, sidecars)).verify()


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SPAWNS)
    parser.add_argument("--state-header", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--helper-source", type=Path, default=DEFAULT_HELPER)
    parser.add_argument("--sidecars-header", type=Path, default=DEFAULT_SIDECARS)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        sources = tuple(
            path.read_text(encoding="utf-8")
            for path in (
                args.source,
                args.state_header,
                args.helper_source,
                args.sidecars_header,
            )
        )
    except OSError as error:
        print(f"live runtime integration verifier: {error}", file=sys.stderr)
        return 1
    issues = verify_sources(*sources)
    if issues:
        print("live runtime integration verifier failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print("live runtime integration verifier: stack/effective authority green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

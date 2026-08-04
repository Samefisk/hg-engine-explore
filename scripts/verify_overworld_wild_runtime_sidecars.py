#!/usr/bin/env python3
"""Task-7 source topology and exact production lifecycle host fixture."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
SUPPORT = ROOT / "src/pokemon_move_history_task6_overlay/overworld_wild_behavior_support.c"
LAYERS_SOURCE = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c"
SPAWNS_LINKER = ROOT / "src/overworld_wild_spawns_overlay/linker.ld"
TASK6_LINKER = ROOT / "src/pokemon_move_history_task6_overlay/linker.ld"
OVERLAYS_MK = ROOT / "overlays.mk"
MAKEFILE = ROOT / "Makefile"
CAPTURE_VERIFIER = ROOT / "scripts/verify_pokemon_move_history_capture.py"
HELPER = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
FIXTURE = Path(__file__).with_name("overworld_wild_runtime_sidecars_fixture.c")
PUBLIC_HEADERS = (
    ROOT / "include/overworld_wild_spawns.h",
    ROOT / "include/overworld_wild_spawns_internal.h",
    ROOT / "include/overworld_wild_behavior_data.h",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"runtime sidecar verification failed: {message}")


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    state = "code"
    index = opening
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "line-comment":
            if char == "\n":
                state = "code"
        elif state == "block-comment":
            if char == "*" and next_char == "/":
                state = "code"
                index += 1
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == '"':
                state = "code"
        elif state == "char":
            if char == "\\":
                index += 1
            elif char == "'":
                state = "code"
        elif char == "/" and next_char == "/":
            state = "line-comment"
            index += 1
        elif char == "/" and next_char == "*":
            state = "block-comment"
            index += 1
        elif char == '"':
            state = "string"
        elif char == "'":
            state = "char"
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise SystemExit("runtime sidecar verification failed: unterminated source body")


def function_body(text: str, name: str) -> str:
    for match in re.finditer(rf"\b{re.escape(name)}\s*\(", text):
        index = match.end() - 1
        depth = 0
        while index < len(text):
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        index += 1
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "{":
            return text[index + 1:matching_brace(text, index)]
    raise SystemExit(f"runtime sidecar verification failed: function body missing: {name}")


def struct_body(text: str, name: str) -> str:
    match = re.search(rf"typedef\s+struct\s+{re.escape(name)}\s*\{{", text)
    require(match is not None, f"private structure missing: {name}")
    opening = text.find("{", match.start())
    return text[opening + 1:matching_brace(text, opening)]


def require_tokens(body: str, label: str, tokens: tuple[str, ...]) -> None:
    for token in tokens:
        require(token in body, f"{label} is missing {token}")


def require_non_destructive(body: str, label: str) -> None:
    for token in (
        "OverworldWildRuntime_DestructivelyInvalidateSlot",
        "OverworldWildRuntime_MarkSlotAssigned",
        "OverworldWildSpawns_ResetSlotState",
        "OverworldWildSpawns_ClearSlotAndSaveShiny",
    ):
        require(token not in body, f"non-destructive {label} reaches {token}")


def verify_private_layout(
    header: str,
    source: str,
    support: str,
    spawns_linker: str,
    task6_linker: str,
    overlays_mk: str,
    makefile: str,
    layers_source: str,
) -> None:
    require_tokens(header, "private runtime header", (
        "#define OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT 8",
        "OW_WILD_MAX_SPAWNS == 10",
        "sizeof(OverworldWildRuntimeLayer) == 16",
        "sizeof(OverworldWildRuntimeLayerBank) == 112",
        "sizeof(OverworldWildRuntimeTimer) == 24",
        "sizeof(OverworldWildRuntimeTimerBank) == 192",
        "sizeof(OverworldWildRuntimeTimerExpiry) == 32",
        "sizeof(OverworldWildRuntimeStaticContext) == 12",
        "sizeof(OverworldWildRuntimeResolvedStaticContext) == 60",
        "sizeof(OverworldWildRuntimeRecoveryCandidate) == 16",
        "sizeof(OverworldWildRuntimeCommandIdentity) == 20",
        "sizeof(OverworldWildRuntimeCommandOrigin) == 52",
        "sizeof(OverworldWildRuntimeCommandOriginBank) == 520",
        "sizeof(OverworldWildRuntimeTimerRecoveryResult) == 44",
        "sizeof(OverworldWildRuntimeStaticModifierContribution) == 18",
        "sizeof(OverworldWildRuntimeResolvedNode) == 38",
        "sizeof(OverworldWildRuntimeStaticCache) == 552",
        "sizeof(OverworldWildRuntimeEffectiveCache) == 104",
        "sizeof(OverworldWildRuntimeProvenance) == 728",
        "sizeof(OverworldWildRuntimeResidentProvenance) == 56",
        "sizeof(OverworldWildRuntimeSlotSidecar) == 1052",
        "sizeof(OverworldWildBehaviorStackRuntime) == 10532",
        "u32 handleEpoch;",
        "u32 dataIncarnation;",
        "u32 slotGeneration;",
        "u32 staticContextGeneration;",
        "u32 nextEntryGeneration;",
        "u32 nextTimerGeneration;",
        "u32 layerGeneration;",
        "u32 effectiveGeneration;",
        "u32 cacheIncarnation;",
        "u16 lifecycleTransitions;",
        "u8 lifecycleState;",
        "u8 activeLayerCount;",
        "u8 presentationGate;",
        "u32 entryGenerations[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];",
        "u16 definitionIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];",
        "u16 ownerIds[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];",
        "u16 instanceKeys[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];",
        "OverworldWildRuntimeLayerBank layerBank;",
        "OverworldWildRuntimeTimerBank timerBank;",
        "OverworldWildRuntimeStaticCache staticCache;",
        "OverworldWildRuntimeEffectiveCache effectiveCache;",
        "OverworldWildRuntimeResidentProvenance provenance;",
        "OverworldWildRuntimeSlotSidecar slots[OW_WILD_MAX_SPAWNS];",
    ))
    for name in (
        "OverworldWildRuntimeLayer",
        "OverworldWildRuntimeLayerBank",
        "OverworldWildRuntimeTimer",
        "OverworldWildRuntimeTimerBank",
        "OverworldWildRuntimeSlotSidecar",
        "OverworldWildBehaviorStackRuntime",
    ):
        body = struct_body(header, name)
        require("*" not in body, f"{name} contains a member pointer")
        for token in ("SaveData", "LocalMapObject", "OverworldWildSpawn", "species", "object"):
            require(token.lower() not in body.lower(), f"{name} binds runtime state to {token}")
    lowered = header.lower()
    for token in ("malloc(", "calloc(", "realloc(", "sys_alloc", "heapid_", "savedata_", "save_"):
        require(token not in lowered, f"private lifecycle header contains allocation/persistence token {token}")
    require("extern OverworldWildBehaviorStackRuntime" not in header,
            "runtime exposes a mutable extern root")
    for public_header in PUBLIC_HEADERS:
        public = public_header.read_text()
        require("OverworldWildBehaviorStackRuntime" not in public
                and "OverworldWildRuntimeSlotSidecar" not in public
                and "behaviorStackRuntime" not in public,
                f"runtime sidecars leaked into public ABI header {public_header.name}")
    require("OverworldWildBehaviorStackRuntime behaviorStackRuntime;" in source,
            "overlay-private resident runtime does not own fixed sidecars")
    require(source.count("OverworldWildBehaviorStackRuntime behaviorStackRuntime;") == 1,
            "overlay has multiple mutable sidecar roots")
    require("OverworldWildBehaviorStackRuntimeMustRemainResidentSuffix" in source,
            "resident sidecars are not frozen at the retained allocation suffix")
    require_tokens(support, "boot-resident lifecycle implementation", (
        "#define OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION",
        "../overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h",
    ))
    require("OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION" not in source,
            "overlay 149 still emits the lifecycle helper bodies")
    require_tokens(task6_linker, "overlay-155 lifecycle placement", (
        "__ow_wild_runtime_sidecars_start",
        "KEEP(*(.ow_wild_runtime_sidecars))",
        "KEEP(*(.ow_wild_runtime_sidecar_wrapper))",
        "__ow_wild_runtime_sidecars_end",
        "__ow_wild_runtime_sidecars_start == ORIGIN(rom) + 0x994",
        "OverworldWildRuntime_Init == ORIGIN(rom) + 0x9B4",
        "== ORIGIN(rom) + 0x9D4",
        "__wrap_memset == ORIGIN(rom) + 0xA48",
        "__ow_wild_runtime_sidecars_end == ORIGIN(rom) + 0xA50",
        "- __ow_wild_runtime_sidecars_start <= 0xEC",
        "__ow_wild_runtime_sidecars_end <= ORIGIN(rom) + 0xA80",
        "__owbd_resident_private_start == ORIGIN(rom) + 0xA80",
    ))
    require(".ow_wild_runtime_sidecars" not in spawns_linker,
            "overlay 149 still owns the relocated lifecycle section")
    require_tokens(overlays_mk, "overlay-149 resident symbol import", (
        "OVERWORLD_WILD_SPAWNS_OVERLAY_LDFLAGS := --just-symbols=$(OVERWORLD_WILD_RUNTIME_SYMBOLS)",
        "$(BUILD)/overworld_wild_spawns_overlay_linked.o:",
        "$(OVERWORLD_WILD_RUNTIME_SYMBOLS):",
        "$(BUILD)/pokemon_move_history_task6_overlay_linked.o",
        "--keep-symbol=OverworldWildRuntime_Init",
        "--keep-symbol=OverworldWildRuntime_DestructivelyInvalidateSlot",
        "--keep-symbol=OverworldWildRuntime_HandleSlotGenerationWrap",
        "POKEMON_MOVE_HISTORY_TASK6_OVERLAY_LDFLAGS := --just-symbols=$(OVERWORLD_WILD_TASK8_SYMBOLS) --wrap=memset",
    ))
    require_tokens(support, "resident memset wrapper", (
        "section(\".ow_wild_runtime_sidecar_wrapper\")",
        "__wrap_memset(void)",
        "blx 0x020E5B44",
    ))
    require(
        "LDFLAGS=rom_gen.ld -T $(C_SUBDIR)/pokemon_move_history_task6_overlay/linker.ld "
        "$(POKEMON_MOVE_HISTORY_TASK6_OVERLAY_LDFLAGS)" in makefile,
        "overlay-155 flag stamp omits the resident memset wrapper link flag",
    )
    destructive = function_body(
        header, "OverworldWildRuntime_DestructivelyInvalidateSlot")
    require_tokens(destructive, "frozen destructive wrapper", (
        "if (!wasLive) return;",
        "OverworldWildRuntime_HandleSlotGenerationWrap(runtime, slotIndex);",
        "Freeze this public overlay-155 entry at its intentional 0x30-byte ABI.",
    ))
    require(destructive.count(
                "OverworldWildRuntime_HandleSlotGenerationWrap(") == 1
            and destructive.count("nop") == 18,
            "overlay-155 destructive wrapper is not one call plus exact padding")
    for forbidden in (
        "OverworldWildRuntime_InitSlot",
        "slotGeneration",
        "cacheIncarnation",
        "lifecycleTransitions",
        "lifecycleState",
    ):
        require(forbidden not in destructive,
                f"overlay-155 destructive wrapper retained inline write path: {forbidden}")
    live_destructive = function_body(
        layers_source, "OverworldWildRuntime_HandleSlotGenerationWrap")
    require_tokens(live_destructive, "overlay-158 live invalidation", (
        "OverworldWildRuntimeSlotSidecar *targetSlot;",
        "targetSlot = &runtime->slots[targetSlotIndex];",
        "slotGeneration = targetSlot->slotGeneration + 1;",
        "targetSlot->cacheIncarnation",
        "InitializeInvalidatedSlot(\n            targetSlot, slotGeneration, cacheIncarnation);",
    ))
    require(live_destructive.count("InitializeInvalidatedSlot(") == 2
            and "static void __attribute__((noinline)) InitializeInvalidatedSlot("
                in layers_source,
            "overlay-158 live invalidation is not outlined through existing primitives")

    cleanup = function_body(source, "OverworldWildSpawns_CleanupResidentData")
    require_tokens(cleanup, "resident cleanup lifetime", (
        "offsetof(OverworldWildOverlayRuntimeState, behaviorStackRuntime)",
        "OverworldWildRuntime_MarkResidentCold(",
        "memset(&runtime->movementHelpSpawnParentSlotPlusOne, 0,",
    ))
    require("sys_FreeMemoryEz(runtime);" not in cleanup,
            "resident cleanup frees the sidecar allocation")
    prefix_clear = cleanup.index("memset(runtime, 0,")
    runtime_clear = cleanup.index(
        "memset(&runtime->movementHelpSpawnParentSlotPlusOne")
    mark_cold = cleanup.index("OverworldWildRuntime_MarkResidentCold(")
    require(cleanup.count("memset(") == 2
            and "offsetof(OverworldWildOverlayRuntimeState,\n"
                "                playerBallCatchValues));" in cleanup
            and "offsetof(OverworldWildOverlayRuntimeState, behaviorStackRuntime)\n"
                "                - offsetof(OverworldWildOverlayRuntimeState,\n"
                "                    movementHelpSpawnParentSlotPlusOne));"
                in cleanup
            and prefix_clear < runtime_clear < mark_cold,
            "resident cleanup does not preserve catch values, clear runtime "
            "projection state, then cold-mark the retained behavior cache")
    ensure = function_body(source, "OverworldWildSpawns_EnsureRuntimeState")
    require_tokens(ensure, "resident activation lifetime", (
        "memset(runtime, 0, sizeof(*runtime));",
        "OverworldWildRuntime_Init(&runtime->behaviorStackRuntime);",
        "OverworldWildRuntime_BindPrivateIdentity(",
        "== OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD",
    ))
    require(ensure.count("OverworldWildRuntime_BindPrivateIdentity(") == 2,
            "private runtime identity is not bound on init and cold restart")
    rebuild_call = ensure.index("OverworldWildSpawns_RebuildColdRuntime(state)")
    require(rebuild_call
            < ensure.index("OverworldWildRuntime_MarkResidentCold(", rebuild_call)
            < ensure.index("return NULL;", rebuild_call),
            "failed cold reconstruction remains externally accessible")
    cold_mark = function_body(layers_source,
        "OverworldWildRuntime_MarkResidentCold")
    require_tokens(cold_mark, "retained immutable static context", (
        "OverworldWildRuntimeStaticContext staticContext =",
        "runtime->slots[slot].staticCache.staticContext;",
        "offsetof(OverworldWildRuntimeSlotSidecar, staticCache)",
        "runtime->slots[slot].staticCache.staticContext = staticContext;",
    ))
    require(cold_mark.index("staticCache.staticContext;")
            < cold_mark.index("memset(")
            < cold_mark.index("staticCache.staticContext = staticContext;"),
            "resident-cold transition does not save, clear, then restore context")


def verify_lifecycle_topology(source: str, helper: str) -> None:
    projection = function_body(
        source, "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior")
    for mask in (
        "movementFrameDrivenChillMask",
        "movementFrameDrivenActiveMask",
        "movementChillPhantomMask",
        "movementActivePhantomMask",
    ):
        require(f"runtime->{mask} |= slotMask;" in projection
                and f"runtime->{mask} &= ~slotMask;" in projection,
                f"cold retry cannot converge both states of {mask}")
    reset = function_body(source, "OverworldWildSpawns_ResetSlotState")
    require_tokens(reset, "authoritative destructive reset", (
        "BOOL wasAssigned =",
        "behaviorStackRuntime.slots[slot].lifecycleState",
        "== OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED;",
        "OverworldWildRuntime_DestructivelyInvalidateSlot(",
        "&OW_WILD_RUNTIME(state)->behaviorStackRuntime",
        "wasAssigned",
        "state->spawns[slot].active = FALSE;",
    ))
    require(reset.count("OverworldWildRuntime_DestructivelyInvalidateSlot(") == 1,
            "authoritative reset advances more than once")
    require(reset.index("OverworldWildRuntime_DestructivelyInvalidateSlot(")
            < reset.index("state->spawns[slot].active = FALSE;"),
            "destructive reset captures liveness after clearing the encounter")
    for mask in (
        "movementFrameDrivenChillMask",
        "movementFrameDrivenActiveMask",
        "movementChillPhantomMask",
        "movementActivePhantomMask",
    ):
        clear = f"OW_WILD_RUNTIME(state)->{mask} &= ~slotMask;"
        require(clear in reset
                and reset.index("state->spawns[slot].active = FALSE;")
                    < reset.index(clear),
                f"inactive-slot publication does not clear {mask}")
    require(source.count("state->spawns[slot].active = FALSE;") == 1,
            "spawn inactivity is published outside the mask-clearing reset hub")
    cold_rebuild = function_body(source, "OverworldWildSpawns_RebuildColdRuntime")
    require_tokens(cold_rebuild, "cold orphan invalidation", (
        "runtimeSlot->lifecycleState",
        "!= OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED",
        "if (!state->spawns[slot].active)",
        "OverworldWildRuntime_DestructivelyInvalidateSlot(\n                stack, slot, TRUE);",
    ))
    require_tokens(cold_rebuild, "retained-context cold reconstruction", (
        "&runtimeSlot->staticCache.staticContext, NULL",
        "OverworldWildRuntime_PrimeEffectiveCache(",
        "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(\n"
            "            state, slot, &runtimeSlot->effectiveCache);",
        "return FALSE;",
    ))
    require("OverworldWildSpawns_BuildSpawnStaticContext(" not in cold_rebuild
            and "OVERWORLD_WILD_SPAWN_METADATA_ENTRY" not in cold_rebuild
            and "playerBallCatchValues" not in cold_rebuild
            and "OverworldWildRuntime_GetEffectiveCache(" not in cold_rebuild
            and cold_rebuild.count(
                "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(") == 1,
            "cold reconstruction recomputes immutable state or splits projection")
    cold_prime = cold_rebuild.index(
        "status = OverworldWildRuntime_PrimeEffectiveCache(")
    cold_failure = cold_rebuild.index(
        "if (status > OW_WILD_RUNTIME_STATUS_IDEMPOTENT)", cold_prime)
    cold_project = cold_rebuild.index(
        "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(", cold_failure)
    require(cold_rebuild.index("for (slot = 0;")
            < cold_prime < cold_failure < cold_project
            and "state, slot, &runtimeSlot->effectiveCache" in
                cold_rebuild[cold_project:],
            "cold reconstruction does not prime successfully before projecting "
            "the rebuilt slot-effective cache")
    require(cold_rebuild.count("for (slot = 0;") == 1,
            "cold reconstruction split authoritative per-slot work across loops")
    require(source.count("OverworldWildRuntime_DestructivelyInvalidateSlot(") == 2,
            "destructive lifecycle routes differ from reset and cold-orphan repair")

    clear_slot = function_body(source, "OverworldWildSpawns_ClearSlotAndSaveShiny")
    require(clear_slot.count("OverworldWildSpawns_ResetSlotState(") == 1,
            "context cleanup wrapper does not reset exactly once")
    require("OverworldWildRuntime_DestructivelyInvalidateSlot" not in clear_slot,
            "context cleanup wrapper double-advances the sidecar")
    require_tokens(function_body(source, "OverworldWildSpawns_Clear"), "bulk context clear", (
        "OverworldWildSpawns_ClearSlotAndSaveShiny(state, i, deleteObjects);",
    ))
    clear_lite = function_body(source, "OverworldWildSpawns_ClearContextLite")
    require_tokens(clear_lite, "light context clear", (
        "runtime = OW_WILD_RUNTIME(state);",
        "OverworldWildSpawns_PreflightAllSlotCleanup(state)",
        "runtime->residentData = &gOverworldWildResidentData;",
        "if (state->spawns[i].active",
        "|| runtime->behaviorStackRuntime.slots[i]",
        "== OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED",
        "OverworldWildSpawns_TrySaveShinyReservation(",
        "OverworldWildSpawns_ResetSlotState(state, i, FALSE);",
    ))
    require("residentData != NULL" not in clear_lite,
            "cold retained runtime still bypasses destructive slot reset")
    require(
        clear_lite.index(
            "runtime->residentData = &gOverworldWildResidentData;"
        ) < clear_lite.index("for (i = 0; i < OW_WILD_MAX_SPAWNS; i++)"),
        "cold discard reattaches resident data after destructive cleanup",
    )

    capture_dispatch = function_body(source, "OverworldWildSpawns_TickPlayerBallProjectile")
    require_tokens(capture_dispatch, "capture callback dispatch", (
        "helperEntry->tickPlayerBallProjectile(",
        "OverworldWildSpawns_ResetSlotState",
        "OverworldWildSpawns_PrepareSlotForCapture",
    ))
    capture_finish = function_body(helper, "OverworldWildHelper_TickPlayerBallCapture")
    require_tokens(capture_finish, "capture completion", (
        "OW_WILD_HELPER_PLAYER_BALL_PHASE_CAUGHT",
        "OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT",
    ))
    capture_reset = (
        r"if\s*\(\s*!resetSlot\s*\(\s*state\s*,\s*"
        r"projectile->impactSlot\s*,\s*TRUE\s*\)\s*\)\s*"
        r"\{\s*return TRUE;\s*\}"
    )
    require(re.search(capture_reset, capture_finish) is not None,
            "capture completion does not stop when slot reset is quarantined")
    require(re.search(
                r"(?m)^\s*resetSlot\s*\(\s*state\s*,\s*"
                r"projectile->impactSlot\s*,\s*TRUE\s*\)\s*;\s*$",
                capture_finish) is None,
            "capture completion deletes through an unchecked slot reset")

    distance_dispatch = function_body(source, "OverworldWildSpawns_DespawnFarMons")
    require_tokens(distance_dispatch, "distance-despawn callback dispatch", (
        "helperEntry->despawnFarEncounters(",
        "OverworldWildSpawns_ResetSlotState",
    ))
    distance = function_body(helper, "OverworldWildHelper_DespawnFarEncounters")
    require_tokens(distance, "distance-despawn route", (
        "OW_WILD_DESPAWN_REASON_DISTANCE",
        "OverworldWildHelper_RemoveEncounter(",
        "resetSlot",
    ))

    battle_dispatch = function_body(source, "OverworldWildSpawns_OverlayCleanupPendingBattle")
    require_tokens(battle_dispatch, "battle callback dispatch", (
        "helperEntry->finishBattle(",
        "OverworldWildSpawns_ResetSlotState",
    ))
    battle = function_body(helper, "OverworldWildHelper_FinishBattle")
    require_tokens(battle, "battle destructive route", (
        "OW_WILD_BATTLE_DISPOSITION_DEFEATED",
        "OW_WILD_BATTLE_DISPOSITION_CAUGHT",
        "OverworldWildHelper_RemoveEncounter(",
        "resetSlot",
    ))
    remove = function_body(helper, "OverworldWildHelper_RemoveEncounter")
    remove_reset = (
        r"if\s*\(\s*!resetSlot\s*\(\s*state\s*,\s*slot\s*,\s*"
        r"TRUE\s*\)\s*\)\s*\{\s*return FALSE;\s*\}"
    )
    require(re.search(remove_reset, remove) is not None,
            "shared distance/battle removal does not quarantine reset failure")
    require(re.search(
                r"(?m)^\s*resetSlot\s*\(\s*state\s*,\s*slot\s*,\s*"
                r"TRUE\s*\)\s*;\s*$",
                remove) is None,
            "shared distance/battle removal uses an unchecked slot reset")

    follower = function_body(source, "OverworldWildSpawns_RemoveFollower")
    require(follower.count("OverworldWildSpawns_ResetSlotState(") == 1,
            "follower recall does not use the authoritative reset exactly once")
    require("OverworldWildRuntime_DestructivelyInvalidateSlot" not in follower,
            "follower recall double-advances the runtime sidecar")

    assignment = function_body(source, "OverworldWildSpawns_FinalizePreparedSpawn")
    require(assignment.count("OverworldWildRuntime_MarkSlotAssigned(") == 1,
            "encounter assignment does not mark the resident slot exactly once")
    require("OverworldWildRuntime_DestructivelyInvalidateSlot" not in assignment,
            "new encounter assignment advances slot generation")
    require(source.count("OverworldWildRuntime_MarkSlotAssigned(") == 1,
            "assignment lifecycle is published outside its authoritative hub")
    spawn = function_body(source, "OverworldWildSpawns_SpawnPreparedEncounter")
    require(spawn.count("OverworldWildSpawns_InitSpawnSlotState(") == 1,
            "ordinary spawn reuse bypasses the assignment hub")

    for name in (
        "OverworldWildSpawns_PrepareSlotForCapture",
        "OverworldWildSpawns_PrepareSlotForBattle",
        "OverworldWildSpawns_ResetSlotMovementCommand",
        "OverworldWildSpawns_ResetSlotMovementCommandForMapHeaderChange",
        "OverworldWildSpawns_ResetAllMovementCommands",
        "OverworldWildSpawns_ResetAllMovementStateOnly",
        "OverworldWildSpawns_DetachAllMovementStateOnContextLoss",
        "OverworldWildSpawns_CleanupPresentationBeforeUnload",
        "OverworldWildSpawns_RecreateSpawnObjectAtTile",
    ):
        require_non_destructive(function_body(source, name), name)

    map_change = function_body(source, "OverworldWildSpawns_PrepareMapHeaderChange")
    require(map_change.count("OverworldWildSpawns_ClearContextLite(state)") == 1
            and "if (!OverworldWildSpawns_ClearContextLite(state)) return FALSE;"
                in map_change,
            "map-header discard does not have one explicit destructive context clear")
    require("if (mode == OW_WILD_MAP_HEADER_CHANGE_DISCARD)" in map_change,
            "destructive map-header clear is not guarded by DISCARD")
    require("OverworldWildSpawns_ResetSlotState" not in map_change
            and "OverworldWildRuntime_DestructivelyInvalidateSlot" not in map_change,
            "map-header preparation bypasses the context-clear wrapper")
    discard = map_change.index("if (mode == OW_WILD_MAP_HEADER_CHANGE_DISCARD)")
    preserve = map_change.index("if (mode == OW_WILD_LIFECYCLE_BATTLE_START")
    require("|| mode == OW_WILD_MAP_HEADER_CHANGE_PRESERVE" in map_change,
            "map-preserve policy no longer shares the bounded boundary path")
    require_tokens(map_change, "boundary effective-cache projection", (
        "status = OverworldWildRuntime_RemoveBoundaryPolicySlotPhase(",
        "if (status > OW_WILD_RUNTIME_STATUS_IDEMPOTENT)",
        "if (phase != 0 && state->spawns[slotIndex].active)",
        "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(\n"
            "                        state, slotIndex, &slot->effectiveCache);",
    ))
    boundary_remove = map_change.index(
        "status = OverworldWildRuntime_RemoveBoundaryPolicySlotPhase(")
    boundary_failure = map_change.index(
        "if (status > OW_WILD_RUNTIME_STATUS_IDEMPOTENT)", boundary_remove)
    boundary_phase = map_change.index(
        "if (phase != 0 && state->spawns[slotIndex].active)",
        boundary_failure)
    boundary_project = map_change.index(
        "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(", boundary_phase)
    battle_return = map_change.index(
        "if (mode == OW_WILD_LIFECYCLE_BATTLE_START) return TRUE;",
        boundary_project)
    preserve_detach = map_change.index(
        "OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, TRUE);",
        battle_return)
    require(map_change.count(
                "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior(") == 1
            and boundary_remove < boundary_failure < boundary_phase
                < boundary_project < battle_return < preserve_detach,
            "boundary removal does not project the successful final-phase "
            "effective cache before battle return or map detach")
    canonicalize = map_change.index("if (mode == OW_WILD_MAP_HEADER_CHANGE_CANONICALIZE)")
    require(preserve < canonicalize < discard,
            "non-destructive map-header paths no longer return before DISCARD")


def run_host_fixture() -> str:
    compiler = shutil.which("clang") or shutil.which("cc")
    require(compiler is not None, "no host C compiler is available")
    with tempfile.TemporaryDirectory(prefix="ow-runtime-sidecars-") as temp_name:
        executable = Path(temp_name) / "runtime-sidecars-fixture"
        subprocess.run([
            compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            str(FIXTURE), "-o", str(executable),
        ], cwd=ROOT, check=True)
        result = subprocess.run([executable], cwd=ROOT, check=True,
                                text=True, capture_output=True)
    return result.stdout.strip()


def main() -> int:
    header = HEADER.read_text()
    source = SOURCE.read_text()
    support = SUPPORT.read_text()
    spawns_linker = SPAWNS_LINKER.read_text()
    task6_linker = TASK6_LINKER.read_text()
    overlays_mk = OVERLAYS_MK.read_text()
    makefile = MAKEFILE.read_text()
    layers_source = LAYERS_SOURCE.read_text()
    capture_verifier = CAPTURE_VERIFIER.read_text()
    helper = HELPER.read_text()
    verify_private_layout(
        header, source, support, spawns_linker, task6_linker, overlays_mk,
        makefile, layers_source)
    verify_lifecycle_topology(source, helper)
    require(
        capture_verifier.count(
            'str(REPO / "scripts/verify_overworld_wild_runtime_sidecars.py")'
        ) == 1
        and capture_verifier.count("\n    run_runtime_sidecar_verifier()\n") == 1
        and "scripts/verify_overworld_wild_runtime_sidecars.py" not in makefile,
        "runtime verifier is missing from or duplicated in package verification",
    )
    fixture_output = run_host_fixture()
    require(fixture_output.startswith("runtime sidecars host fixture:"),
            "host fixture did not publish its deterministic summary")
    print(fixture_output)
    print(
        "runtime sidecars source verifier: private fixed SoA layout, retained cold/active lifetime, "
        "nonallocating primitives, "
        "single-advance destructive routes, cold-discard reset, terminal all-slot restart, "
        "stable assignment, and non-destructive preparations verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

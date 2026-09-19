#!/usr/bin/env python3
"""Build and run deterministic host proofs for motion and its world seam."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str) -> str:
    bodies = []
    for match in re.finditer(
        rf"^(?:[A-Za-z_][^\n;{{}}]*\s+)?\b{re.escape(name)}"
        rf"\s*\([^;{{}}]*\)\s*\{{",
        source,
        re.MULTILINE,
    ):
        opening = match.end() - 1
        depth = 0
        for index in range(opening, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(source[opening + 1:index])
                    break
    return max(bodies, key=len) if bodies else ""


def world_gate_sources_hold(actor: str, mount: str, wild: str) -> bool:
    actor_gate = " ".join(
        function_body(actor, "ActorSystem_WorldGateOpen").split()
    )
    actor_masks = " ".join(
        function_body(actor, "ActorSystem_ActorMasks").split()
    )
    run_command = " ".join(
        function_body(actor, "ActorSystem_RunCommand").split()
    )
    mount_entry = " ".join(
        function_body(mount, "OverworldMount_FieldInputProcess").split()
    )
    mount_gate = " ".join(
        function_body(mount, "OverworldMount_ProcessFieldInput").split()
    )
    battle_gate = " ".join(function_body(
        wild, "OverworldWildSpawns_IsPlayerStableForBattle"
    ).split())
    queue = " ".join(function_body(
        wild, "OverworldWildSpawns_QueueBattleForSlot"
    ).split())
    start_queued = " ".join(function_body(
        wild, "OverworldWildSpawns_TryStartQueuedBattle"
    ).split())
    return all((
        "OverworldMotion_BlocksWorldGate(" in actor_masks,
        "(ActorSystem_ActorMasks() >> 16) == 0" in actor_gate,
        "ActorSystem_TransitionIsActive()" in actor_gate,
        "case OVERWORLD_ACTOR_INSPECT_WORLD_GATE:" in actor,
        "return OVERWORLD_MOUNT_FIELD_INPUT_HOST(fieldInput, fieldSystem," in mount_entry,
        "OVERWORLD_ACTOR_WORLD_GATE_WARP" in mount_gate,
        "OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(" in mount_gate,
        "snapshot.motionMode" not in mount_gate,
        "OVERWORLD_ACTOR_WORLD_GATE_BATTLE" in battle_gate,
        "OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(" in battle_gate,
        "state->pendingMapGeneration = state->mapGeneration;" in queue,
        "state->pendingEncounterGeneration ="
            " state->spawns[slot].encounterGeneration;" in queue,
        "state->pendingMapGeneration != state->mapGeneration" in start_queued,
        "state->pendingEncounterGeneration"
            " != state->spawns[slot].encounterGeneration" in start_queued,
        "command->expectedFieldEpoch != 0" in run_command,
        "command->expectedFieldEpoch"
            " != gOverworldActorSystemState.fieldEpoch" in run_command,
    ))


def verify_world_gate_sources() -> None:
    actor = (
        ROOT
        / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
    ).read_text()
    mount = (
        ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"
    ).read_text()
    mount += "\n" + (ROOT / "src/field/overworld_mount_field_input.c").read_text()
    wild = (
        ROOT
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    if not world_gate_sources_hold(actor, mount, wild):
        raise SystemExit("world gate or queued-generation ownership is incomplete")
    mutations = (
        (
            1,
            "return OVERWORLD_MOUNT_FIELD_INPUT_HOST(fieldInput, fieldSystem,",
            "return BYPASSED_FIELD_INPUT_HOST(fieldInput, fieldSystem,",
        ),
        (
            0,
            "return !ActorSystem_TransitionIsActive()\n"
            "        && (ActorSystem_ActorMasks() >> 16) == 0;",
            "return TRUE\n"
            "        && (ActorSystem_ActorMasks() >> 16) == 0;",
        ),
        (
            1,
            "OVERWORLD_ACTOR_WORLD_GATE_WARP",
            "OVERWORLD_ACTOR_WORLD_GATE_BATTLE",
        ),
        (
            2,
            "state->pendingMapGeneration != state->mapGeneration",
            "FALSE",
        ),
        (
            2,
            "state->pendingEncounterGeneration\n"
            "            != state->spawns[slot].encounterGeneration",
            "FALSE",
        ),
        (
            0,
            "command->expectedFieldEpoch\n"
            "            != gOverworldActorSystemState.fieldEpoch",
            "FALSE",
        ),
    )
    sources = [actor, mount, wild]
    for source_index, needle, replacement in mutations:
        if needle not in sources[source_index]:
            raise SystemExit(f"world-gate mutation anchor differs: {needle}")
        candidates = list(sources)
        candidates[source_index] = candidates[source_index].replace(
            needle, replacement, 1
        )
        if world_gate_sources_hold(*candidates):
            raise SystemExit(f"world-gate mutation survived: {needle}")


def run_host_proof(
    common: list[str],
    executable: Path,
    sources: list[Path],
    *,
    expect_success: bool = True,
) -> None:
    command = common + [str(source) for source in sources] + [
        "-o", str(executable)
    ]
    subprocess.run(command, cwd=ROOT, check=True, timeout=30)
    result = subprocess.run(
        [str(executable)], cwd=ROOT, check=False, timeout=30,
        stdout=subprocess.DEVNULL if not expect_success else None,
        stderr=subprocess.DEVNULL if not expect_success else None,
    )
    if (expect_success and result.returncode != 0):
        raise subprocess.CalledProcessError(result.returncode, executable)
    if not expect_success and result.returncode == 0:
        raise SystemExit(f"mutation survived host proof: {executable.name}")


def main() -> int:
    compiler = shlex.split(os.environ.get("CC", "cc"))
    if not compiler:
        raise SystemExit("CC must name a C compiler")
    with tempfile.TemporaryDirectory(prefix="overworld-motion-") as directory:
        common = compiler + [
            "-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic",
            "-DOVERWORLD_MOTION_HOST=1",
            "-I", str(ROOT / "include"),
            "-I", str(ROOT / "tools"),
            str(ROOT / "lib/overworld/overworld_motion_model.c"),
        ]
        proofs = (
            (
                "overworld-motion-model",
                [ROOT / "tools/overworld_motion_model_harness.c"],
            ),
            (
                "overworld-motion-world",
                [
                    ROOT / "tools/overworld_motion_world_fixture.c",
                    ROOT / "tools/overworld_motion_world_harness.c",
                ],
            ),
            (
                "overworld-teleport-planner",
                [ROOT / "tools/overworld_teleport_planner_harness.c"],
            ),
        )
        for name, sources in proofs:
            executable = Path(directory) / name
            run_host_proof(common, executable, list(sources))

        fixture = (ROOT / "tools/overworld_motion_world_fixture.c").read_text()
        mutations = (
            (
                "wrong-surface-occupancy",
                "&& tile->occupantSurface == request->surfaceId",
                "&& tile->occupantSurface != request->surfaceId",
            ),
            (
                "wrong-surface-reservation",
                "&& tile->reservationSurface == request->surfaceId) {\n"
                "        flags |= OVERWORLD_MOTION_CANDIDATE_RESERVED;",
                "&& tile->reservationSurface != request->surfaceId) {\n"
                "        flags |= OVERWORLD_MOTION_CANDIDATE_RESERVED;",
            ),
            (
                "leaked-terminal-reservation",
                "tile->reserved = FALSE;",
                "tile->reserved = TRUE;",
            ),
        )
        for name, needle, replacement in mutations:
            if fixture.count(needle) != 1:
                raise SystemExit(f"mutation anchor differs: {name}")
            mutated = Path(directory) / f"{name}.c"
            mutated.write_text(fixture.replace(needle, replacement, 1))
            run_host_proof(
                common,
                Path(directory) / name,
                [mutated, ROOT / "tools/overworld_motion_world_harness.c"],
                expect_success=False,
            )
        model_path = ROOT / "include/overworld_motion_model.h"
        model = model_path.read_text()
        gate_needle = "actorActive && inputOwnership"
        if model.count(gate_needle) != 1:
            raise SystemExit("world-gate motion mutation anchor differs")
        mutated_include = Path(directory) / "include"
        mutated_include.mkdir()
        (mutated_include / model_path.name).write_text(model.replace(
            gate_needle, "actorActive && !inputOwnership", 1
        ))
        mutated_common = list(common)
        root_include = mutated_common.index(str(ROOT / "include"))
        mutated_common[root_include] = str(mutated_include)
        run_host_proof(
            mutated_common,
            Path(directory) / "wrong-world-gate-owner",
            [ROOT / "tools/overworld_motion_model_harness.c"],
            expect_success=False,
        )
    verify_world_gate_sources()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

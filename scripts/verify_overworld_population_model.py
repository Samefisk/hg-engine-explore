#!/usr/bin/env python3
"""Build and run the deterministic host proof for population ownership."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def compatibility_update_is_retired(actor: str) -> bool:
    table = actor.split(
        "const OverworldActorCompatibilityEntry gOverworldActorCompatibilityEntry",
        1,
    )[-1].split("const OverworldActorSystemDebugLayout", 1)[0]
    return (
        "OverworldActorSystem_CompatibilityUpdateImpl" not in actor
        and "OverworldActorSystem_CompatibilityBindImpl,\n        0,\n"
        in table
    )


def population_inspect_normalizes_work_pending(actor: str) -> bool:
    return (
        "output->workPending = state->maintenanceState != 0;" in actor
        and "output->workPending = state->maintenanceState;" not in actor
    )


def verify_live_actor_adapter() -> None:
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    actor = (
        ROOT
        / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
    ).read_text()
    wild_runtime = (
        ROOT
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    ).read_text()
    overlays = (ROOT / "overlays.mk").read_text()
    actor_header = (ROOT / "include/overworld_actor_system.h").read_text()
    actor_linker = (
        ROOT / "src/overworld_actor_system_overlay/linker.ld"
    ).read_text()
    save_constants = (ROOT / "include/constants/save.h").read_text()

    require(
        "OverworldPopulationState population;" in internal
        and "populationRefillTimer" not in internal
        and "populationRefillArmed" not in internal
        and "populationMaintenanceState" not in internal,
        "actor state does not own the portable population value object",
    )
    require(
        "overworld_actor_system_overlay/overworld_population_model.o"
            in overlays
        and "lib/overworld/overworld_population_model.c" in overlays
        and "overworld_actor_system_overlay/overworld_population_model.d"
            in overlays,
        "actor overlay does not compile and link the portable population model",
    )
    require(
        "OverworldPopulation_Apply(" in actor
        and "OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->populationControl("
            not in actor,
        "actor population facade still delegates ownership to Wild",
    )
    require(
        "ActorSystem_PublishNativePlayerPathAdvance(" in actor
        and "GetPlayerXCoord(fieldSystem->playerAvatar)" in actor
        and "GetPlayerYCoord(fieldSystem->playerAvatar)" in actor
        and "OVERWORLD_POPULATION_INPUT_PATH_ADVANCE" in actor
        and "OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED" in actor
        and "ActorSystem_PublishPopulationPathAdvances(" not in actor
        and "ActorSystem_PopulationMotionSequence(" not in actor
        and "ActorSystem_PublishPopulationCommit();" in actor
        and "OVERWORLD_POPULATION_INPUT_COMMIT" in actor,
        "population center is not driven by native player logical tiles",
    )
    require(
        "OVERWORLD_ACTOR_INSPECT_POPULATION" in actor_header
        and "OverworldActorPopulationSnapshot" in actor_header
        and "case OVERWORLD_ACTOR_INSPECT_POPULATION:" in actor
        and "snapshot->hasPopulation = 1;" in actor,
        "population is not exposed through the public Inspect value ABI",
    )
    require(
        population_inspect_normalizes_work_pending(actor),
        "population Inspect leaks the private maintenance phase as a boolean",
    )
    require(
        not population_inspect_normalizes_work_pending(actor.replace(
            "output->workPending = state->maintenanceState != 0;",
            "output->workPending = state->maintenanceState;",
            1,
        )),
        "population Inspect boolean mutation survived",
    )
    for event in ("SUSPEND", "REBIND", "RESUME", "DISCARD"):
        require(
            f"OVERWORLD_POPULATION_FIELD_{event}" in actor,
            f"actor transition does not publish FIELD_{event}",
        )
    require(
        "operation == OVERWORLD_ACTOR_POPULATION_CONTROL_RESET" in actor
        and "ActorSystem_TransitionIsActive()" in actor
        and "legacy Wild clear during DISCARD" in actor,
        "legacy transition reset can erase actor-owned reconciliation work",
    )
    require(
        "OverworldWildRuntime_PopulationControl" not in wild_runtime
        and "entry->reservedPopulationControl == 0" in wild_runtime,
        "retired Wild population callback was not removed and zero-validated",
    )
    require(
        "OVERWORLD_ACTOR_SYSTEM_OVERLAY_LOAD_ADDR 0x023B6500"
            in actor_header
        and "OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE 0x023B6B00"
            in actor_header
        and "OVERWORLD_ACTOR_SYSTEM_OVERLAY_SIZE 0x4600" in actor_header
        and "ORIGIN = 0x023B6500, LENGTH = 0x4600" in actor_linker
        and "ACTOR_CORE_ORIGIN = 0x023B6B00" in actor_linker
        and ".overworld_actor_population_adapter" in actor_linker
        and ". = ORIGIN(rom) + 0x3C70;" in actor_linker
        and "#define NEW_HEAP3_SIZE 0x106500" in save_constants,
        "resident population deployment does not preserve the actor ABI and field heap",
    )
    require(
        "OVERWORLD_ACTOR_SYSTEM_POPULATION_MAGIC" in internal
        and "OVERWORLD_ACTOR_POPULATION_SERVICE_VERSION 3" in internal
        and "OverworldActorPopulationFrameCall" in internal
        and "sizeof(OverworldActorPopulationServiceEntry) == 16" in internal,
        "fixed actor population service ABI changed",
    )
    require(
        compatibility_update_is_retired(actor),
        "retired compatibility update code or table pointer remains",
    )
    require(
        not compatibility_update_is_retired(
            actor.replace(
                "OverworldActorSystem_CompatibilityBindImpl,\n        0,\n",
                "OverworldActorSystem_CompatibilityBindImpl,\n"
                "        OverworldActorSystem_CompatibilityUpdateImpl,\n",
                1,
            )
        ),
        "compatibility update slot mutation survived",
    )
    require(
        not compatibility_update_is_retired(
            actor + "\nvoid OverworldActorSystem_CompatibilityUpdateImpl(void);\n"
        ),
        "compatibility update symbol mutation survived",
    )


def compile_and_run(
    compiler: list[str], directory: Path, model: Path, output_name: str
) -> subprocess.CompletedProcess[str]:
    executable = directory / output_name
    command = compiler + [
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-pedantic",
        "-DOVERWORLD_POPULATION_HOST=1",
        "-I",
        str(ROOT / "include"),
        str(model),
        str(ROOT / "tools/overworld_population_model_harness.c"),
        "-o",
        str(executable),
    ]
    subprocess.run(command, cwd=ROOT, check=True, timeout=30)
    return subprocess.run(
        [str(executable)], cwd=ROOT, text=True, capture_output=True, timeout=30
    )


def verify_sequence_mutations(compiler: list[str], directory: Path) -> None:
    source_path = ROOT / "lib/overworld/overworld_population_model.c"
    source = source_path.read_text()
    mutations = {
        "accept-stale-sequence": (
            "(s32)distance <= 0",
            "distance == 0",
        ),
        "split-path-commit-sequence": (
            "state->lastWorldEventSequence = input->eventSequence;",
            "state->reservedWorldEventSequence = input->eventSequence;",
        ),
        "accept-invalid-field-event": (
            "if (input->event == OVERWORLD_POPULATION_FIELD_NONE\n"
            "        || input->event > OVERWORLD_POPULATION_FIELD_DISCARD) {",
            "if (0) {",
        ),
    }
    for name, (before, after) in mutations.items():
        require(before in source, f"mutation target missing: {name}")
        mutant = directory / f"{name}.c"
        mutant.write_text(source.replace(before, after, 1))
        result = compile_and_run(compiler, directory, mutant, name)
        require(result.returncode != 0, f"population mutation survived: {name}")


def verify_public_value_abi(compiler: list[str], directory: Path) -> None:
    probe = directory / "population-public-abi.c"
    probe.write_text(
        "#include <stddef.h>\n"
        '#include "overworld_actor_system.h"\n'
        "int main(void) {\n"
        "  OverworldActorSnapshot snapshot = {0};\n"
        "  snapshot.population.lastWorldEventSequence = 1;\n"
        "  snapshot.hasPopulation = 1;\n"
        "  return sizeof(snapshot) == 176\n"
        "      && sizeof(snapshot.population) == 32\n"
        "      && sizeof(snapshot.population.workPending) == 1\n"
        "      && offsetof(OverworldActorSnapshot, population)\n"
        "          + offsetof(OverworldActorPopulationSnapshot, workPending)"
        " == 161\n"
        "      && OVERWORLD_ACTOR_INSPECT_POPULATION == 5\n"
        "      && OVERWORLD_ACTOR_INSPECT_WORLD_GATE == 6 ? 0 : 1;\n"
        "}\n"
    )
    executable = directory / "population-public-abi"
    subprocess.run(
        compiler
        + [
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-pedantic",
            "-DOVERWORLD_ACTOR_SYSTEM_HOST=1",
            "-I",
            str(ROOT / "include"),
            str(probe),
            "-o",
            str(executable),
        ],
        cwd=ROOT,
        check=True,
        timeout=30,
    )
    subprocess.run([str(executable)], cwd=ROOT, check=True, timeout=30)


def main() -> int:
    compiler = shlex.split(os.environ.get("CC", "cc"))
    if not compiler:
        raise SystemExit("CC must name a C compiler")
    with tempfile.TemporaryDirectory(prefix="overworld-population-") as directory:
        temp = Path(directory)
        result = compile_and_run(
            compiler,
            temp,
            ROOT / "lib/overworld/overworld_population_model.c",
            "overworld-population-model",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)
        verify_sequence_mutations(compiler, temp)
        verify_public_value_abi(compiler, temp)
    verify_live_actor_adapter()
    print("overworld population actor adapter: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Task-8 atomic runtime-layer API, host semantics, and oracle gate."""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"
FIXTURE = Path(__file__).with_name("overworld_wild_runtime_layers_fixture.c")
CATALOG_FIXTURE = Path(__file__).with_name(
    "overworld_wild_runtime_catalog_fixture.c"
)
VALIDATED_V40 = ROOT / "build/OverworldWildBehaviorDataV40.expected.bin"
MODEL = Path(__file__).with_name("overworld_behavior_stack_model.py")
OVERLAY_SOURCE = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
IMPLEMENTATION = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c"
OVERLAY_LINKER = ROOT / "src/overworld_wild_runtime_overlay/linker.ld"
TASK6_LINKER = ROOT / "src/pokemon_move_history_task6_overlay/linker.ld"
HISTORY_LINKER = ROOT / "src/pokemon_move_history_overlay/linker.ld"
OVERLAYS_MK = ROOT / "overlays.mk"
SAVE_HEADER = ROOT / "include/constants/save.h"
STARTUP = ROOT / "armips/asm/syntheticoverlay.s"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"runtime layer verification failed: {message}")


def load_model():
    spec = importlib.util.spec_from_file_location("ow_stack_model_task8", MODEL)
    require(spec is not None and spec.loader is not None, "Task-6 oracle cannot be imported")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    require(start >= 0, f"missing implementation: {signature}")
    brace = source.find("{", start)
    require(brace >= 0, f"missing implementation body: {signature}")
    depth = 0
    for cursor in range(brace, len(source)):
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:cursor + 1]
    raise SystemExit(f"runtime layer verification failed: unterminated body: {signature}")


def verify_oracle_status_trace(fixture_output: str) -> int:
    model = load_model()
    c_statuses = re.findall(
        r"OW_WILD_RUNTIME_STATUS_([A-Z_]+)\s*=\s*(\d+)",
        HEADER.read_text(),
    )
    expected_names = [status.name for status in model.Status]
    require([name for name, _value in c_statuses] == expected_names,
            "C status inventory/order differs from the Task-6 oracle")
    require([int(value) for _name, value in c_statuses] == list(range(len(expected_names))),
            "C status numeric ABI is not explicit and contiguous")

    catalog, ids = model._fixture_catalog()
    runtime = model.StackRuntime(catalog)
    slot = runtime.install_slot(0, model.StaticContext(map_id=1))
    first = runtime.apply(0, 1, ids["owner_awareness"])
    identical = runtime.apply(0, 1, ids["owner_awareness"])
    collision = runtime.apply(0, 5, ids["owner_awareness"])
    missing_replace = runtime.replace(0, ids["owner_weather"], 0, 5)
    stale = runtime.remove(0, model.dataclasses.replace(
        first.operation_results[0].handle,
        entry_generation=first.operation_results[0].handle.entry_generation + 1,
    ))
    ambiguous = runtime.apply_stack_delta(
        0,
        slot.slot_generation,
        (
            runtime.bind_delta_operation(model.DeltaOperation.apply(
                "a", 5, ids["owner_weather"])),
            runtime.bind_delta_operation(model.DeltaOperation.replace(
                "b", 5, ids["owner_weather"])),
        ),
        "task8-oracle-crosscheck",
    )
    trace = (
        first.status.name,
        identical.status.name,
        collision.status.name,
        missing_replace.status.name,
        stale.status.name,
        ambiguous.status.name,
    )
    require(trace == (
        "OK", "IDEMPOTENT", "OWNER_KEY_OCCUPIED", "NOT_FOUND",
        "INVALID_HANDLE", "AMBIGUOUS_DELTA",
    ), f"Task-6 oracle trace changed: {trace}")
    match = re.search(
        r"TASK6_CORPUS statuses=([0-9,]+) count=(\d+) layerGeneration=(\d+)",
        fixture_output,
    )
    require(match is not None, "C fixture did not publish its Task-6 corpus")
    status_by_value = {int(value): name for name, value in c_statuses}
    c_trace = tuple(
        status_by_value.get(int(value), f"UNKNOWN_{value}")
        for value in match.group(1).split(",")
    )
    normalized_model_state = (len(slot.layers), slot.layer_generation)
    normalized_c_state = (int(match.group(2)), int(match.group(3)))
    require(c_trace == trace,
            f"C/Task-6 normalized status corpus differs: {c_trace} != {trace}")
    require(normalized_c_state == normalized_model_state,
            "C/Task-6 normalized final layer state differs: "
            f"{normalized_c_state} != {normalized_model_state}")
    return len(trace)


def verify_source_contracts() -> None:
    header = HEADER.read_text()
    source = OVERLAY_SOURCE.read_text()
    implementation = IMPLEMENTATION.read_text()
    linker = OVERLAY_LINKER.read_text()
    fixture = FIXTURE.read_text()
    task6_linker = TASK6_LINKER.read_text()
    history_linker = HISTORY_LINKER.read_text()
    overlays_mk = OVERLAYS_MK.read_text()
    save_header = SAVE_HEADER.read_text()
    startup = STARTUP.read_text()

    for token in (
        "#define OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS 16",
        "OW_WILD_RUNTIME_DELTA_APPLY = 1",
        "OW_WILD_RUNTIME_DELTA_REPLACE = 2",
        "OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED = 3",
        "OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT = 4",
        "OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT = 5",
        "OW_WILD_RUNTIME_DELTA_REMOVE_POLICY = 6",
        "OW_WILD_RUNTIME_DELTA_CLEAR = 7",
        "sizeof(OverworldWildRuntimeLayerHandle) == 24",
        "sizeof(OverworldWildRuntimeDeltaOperation) == 28",
        "sizeof(OverworldWildRuntimeApplicabilityInput) == 28",
        "sizeof(OverworldWildRuntimeStackDeltaRequest) == 484",
        "OverworldWildRuntime_ApplyStackDelta(",
        "OverworldWildRuntime_Apply(",
        "OverworldWildRuntime_Replace(",
        "OverworldWildRuntime_Remove(",
        "OverworldWildRuntime_RemoveOwner(",
        "OverworldWildRuntime_ClearAllForSlot(",
        "OverworldWildRuntime_GetLayerByIndex(",
        "OverworldWildRuntime_FindLayer(",
        "OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED",
    ):
        require(token in header, f"closed API/source assertion missing: {token}")

    declaration_start = header.index("/* Lifecycle-only binding.")
    declaration_end = header.index("static inline void OverworldWildRuntime_MarkResidentCold")
    declarations = header[declaration_start:declaration_end]
    require("OverworldWildRuntimeLayerBank *" not in declarations,
            "query API returns mutable layer-bank storage")
    require("OverworldWildRuntimeSlotSidecar **" not in declarations,
            "query API returns mutable slot storage")
    require("generatedMetadata" not in header and "definitionMetadata" not in header,
            "mutation request accepts caller-generated metadata")
    apply_body = function_body(
        implementation,
        "OverworldWildRuntimeStatus OverworldWildRuntime_ApplyStackDelta(\n"
        "    OverworldWildBehaviorStackRuntime *runtime,\n"
        "    const OverworldWildRuntimeStackDeltaRequest *request,\n"
        "    OverworldWildRuntimeStackDeltaResult *result)\n{",
    )
    require("effectiveGeneration =" not in apply_body,
            "Task-8 mutation writes deferred effective generation")
    for forbidden in ("malloc(", "calloc(", "realloc(", "sys_AllocMemory("):
        require(forbidden not in implementation,
                f"mutation implementation allocates through {forbidden}")
    require("overworld_wild_runtime_layers_internal.h" in source,
            "production runtime overlay does not bind the internal module")
    for token in (
        "ORIGIN = 0x023BB400, LENGTH = 0x2000",
        "OverworldWildBehavior_LoadValidatedBundle == ORIGIN(rom)",
        "__bss_end__ - __bss_start__ <= 0x140",
        "__bss_end__ <= ORIGIN(rom) + 0x1F80",
        "__bss_end__ <= 0x023BD380",
    ):
        require(token in linker, f"overlay157 fixed-link assertion missing: {token}")
    require("ORIGIN = 0x023BD400, LENGTH = 0x1000" in task6_linker,
            "frozen overlay155 window changed")
    require("ORIGIN = 0x023BE400, LENGTH = 0x2000" in history_linker,
            "overlay153 guarded window changed")
    require("#define NEW_HEAP3_SIZE 0x10B000" in save_header,
            "heap3 does not reserve the approved 0x5000 resident footprint")
    require(
        startup.count("mov r1, #155") == 1
        and startup.count("mov r1, #157") == 1
        and startup.count("mov r1, #153") == 1
        and startup.index("mov r1, #155")
            < startup.index("mov r1, #157")
            < startup.index("mov r1, #153"),
        "resident boot order is not 155 -> 157 -> 153",
    )
    for token in (
        "OVERWORLD_WILD_TASK8_SYMBOLS :=",
        "--keep-symbol=OverworldWildBehavior_LoadValidatedBundle",
        "--keep-symbol=OverworldWildRuntime_ApplyStackDelta",
        "$(BUILD)/overworld_wild_runtime_overlay_linked.o",
        "--overlay 157",
    ):
        require(token in overlays_mk, f"overlay157 build/link integration missing: {token}")
    for token in (
        "OverworldWildBehavior_LoadValidatedBundle(",
        "OverworldWildBehavior_ReleaseValidatedBundle(",
        "OverworldWildBehavior_FreeValidatedBundle(",
        "OverworldWildRuntime_CopyInstalledDefinition(",
        "sOverworldWildValidatedV40",
        "OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE",
        "OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE",
    ):
        require(token in source, f"resident validated-bundle contract missing: {token}")
    require("InstallValidatedCatalog" not in source + implementation + header,
            "caller-installed copied definition catalog remains exposed")
    assignment = re.compile(
        r"(?:layerBank\.(?:entryGenerations|definitionIds|ownerIds|instanceKeys|"
        r"requiredOwnerIds|tiredOriginKinds|generatedFlags)\[[^]]+\]|"
        r"activeLayerCount)\s*="
    )
    writers = []
    for path in (ROOT / "src").rglob("*.[ch]"):
        if path == IMPLEMENTATION:
            continue
        if assignment.search(path.read_text(errors="replace")):
            writers.append(path.relative_to(ROOT).as_posix())
    require(not writers, "external direct layer-bank writers exist: " + ", ".join(writers))
    require("public-field-edited handle was accepted" in fixture,
            "adversarial public-handle mutation fixture is absent")
    require("global rekey did not advance surviving other slot once" in fixture,
            "cross-slot generation rekey fixture is absent")
    for token in (
        "OW_WILD_RUNTIME_ROLE_MASK(role) (1u << ((role) - 1))",
        "input->semanticRoleMask & ~0x7Fu",
        "CheckGeneratedTranslation",
        "ValidatePlannedMultiplicity",
        "RotatePrivateIdentity(runtime)",
        "RestartRuntime(runtime, TRUE)",
    ):
        require(token in implementation,
                f"review-correction source assertion missing: {token}")
    for token in (
        "dormant modifier was rejected by the current effective profile",
        "role 1 did not map to semantic-mask bit 0",
        "role 7 did not map to semantic-mask bit 6",
        "authored tired branch accepted the fallback wrapper",
        "duplicate absent owner selectors were accepted",
        "edited handle did not return INVALID_HANDLE",
        "capacity masked final multiplicity rejection",
        "terminal slot wrap inspected corrupt layers before direct restart",
        "handle minted between forced-zero binds remained authenticated",
    ):
        require(token in fixture, f"review fixture is absent: {token}")


def run_host_fixture() -> str:
    compiler = shutil.which("cc") or shutil.which("clang")
    require(compiler is not None, "no host C compiler available")
    with tempfile.TemporaryDirectory(prefix="ow-runtime-layers-") as directory:
        binary = Path(directory) / "fixture"
        subprocess.run([
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            str(FIXTURE),
            "-o",
            str(binary),
        ], cwd=ROOT, check=True)
        completed = subprocess.run(
            [str(binary)], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    require("runtime layers host fixture:" in completed.stdout,
            "host fixture did not publish its deterministic summary")
    return completed.stdout.strip()


def run_catalog_fixture() -> str:
    compiler = shutil.which("cc") or shutil.which("clang")
    require(compiler is not None, "no host C compiler available")
    require(VALIDATED_V40.is_file(),
            "validated v40 fixture is absent; regenerate source artifacts first")
    with tempfile.TemporaryDirectory(prefix="ow-runtime-catalog-") as directory:
        binary = Path(directory) / "fixture"
        subprocess.run([
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            str(CATALOG_FIXTURE),
            "-o",
            str(binary),
        ], cwd=ROOT, check=True)
        completed = subprocess.run(
            [str(binary), str(VALIDATED_V40)], cwd=ROOT, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    require("runtime catalog host fixture:" in completed.stdout,
            "production catalog fixture did not publish its summary")
    return completed.stdout.strip()


def main() -> None:
    verify_source_contracts()
    fixture_summary = run_host_fixture()
    oracle_checks = verify_oracle_status_trace(fixture_summary)
    catalog_summary = run_catalog_fixture()
    print(fixture_summary)
    print(catalog_summary)
    print(
        "runtime layer source verifier: closed tagged-union ABI, canonical fixed "
        f"scratch semantics, authenticated handles, and {oracle_checks}-status "
        "Task-6 oracle trace verified"
    )


if __name__ == "__main__":
    main()

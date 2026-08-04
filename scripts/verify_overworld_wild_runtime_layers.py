#!/usr/bin/env python3
"""Task-8 atomic runtime-layer API, host semantics, and oracle gate."""

from __future__ import annotations

import ast
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
CATALOG_TIMER_FIXTURE = Path(__file__).with_name(
    "overworld_wild_runtime_catalog_timer_fixture.c"
)
VALIDATED_V40 = ROOT / "build/OverworldWildBehaviorDataV40.expected.bin"
MODEL = Path(__file__).with_name("overworld_behavior_stack_model.py")
OVERLAY_SOURCE = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
IMPLEMENTATION = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.c"
INTERNAL_HEADER = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers_internal.h"
OVERLAY_LINKER = ROOT / "src/overworld_wild_runtime_overlay/linker.ld"
LAYERS_LINKER = ROOT / "src/overworld_wild_runtime_layers_overlay/linker.ld"
TIMERS_LINKER = ROOT / "src/overworld_wild_runtime_timers_overlay/linker.ld"
TIMERS_SOURCE = ROOT / "src/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.c"
SPAWNS_LINKER = ROOT / "src/overworld_wild_spawns_overlay/linker.ld"
TASK6_LINKER = ROOT / "src/pokemon_move_history_task6_overlay/linker.ld"
HISTORY_LINKER = ROOT / "src/pokemon_move_history_overlay/linker.ld"
OVERLAYS_MK = ROOT / "overlays.mk"
SAVE_HEADER = ROOT / "include/constants/save.h"
STARTUP = ROOT / "armips/asm/syntheticoverlay.s"
BYTE_REPLACEMENT = ROOT / "bytereplacement"
SHARED_V40_VALIDATION = ROOT / "scripts/overworld_wild_behavior_v40_validation_shared.h"
V40_SCALAR_SYMBOLS = ROOT / "asm/overworld_wild_runtime_layers_overlay/owbd_v40_scalar_symbols.s"
MAKE_SCRIPT = ROOT / "scripts/make.py"


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
    speed_spec = model.FIELD_SPECS["state.speed"]
    require((speed_spec.minimum, speed_spec.maximum) == (1, 4),
            "Task-6 speed domain is not 1..4")

    def accepts(path, operation):
        try:
            model._validate_operation(path, operation, runtime=True)
            return True
        except model.ModelError:
            return False

    require(not accepts("state.speed",
                model.ModifierOperation(model.OperatorKind.SET, 0))
            and accepts("state.speed",
                model.ModifierOperation(model.OperatorKind.ADD, 33))
            and accepts("state.speed",
                model.ModifierOperation(model.OperatorKind.ADD, -32768))
            and accepts("state.speed",
                model.ModifierOperation(model.OperatorKind.ADD, 32767))
            and not accepts("state.speed",
                model.ModifierOperation(model.OperatorKind.ADD, -32769))
            and not accepts("state.speed",
                model.ModifierOperation(model.OperatorKind.ADD, 32768))
            and accepts("state.avoidPreviousTile",
                model.ModifierOperation(model.OperatorKind.SET, True))
            and accepts("state.avoidPreviousTile",
                model.ModifierOperation(model.OperatorKind.SET, False))
            and not accepts("state.avoidPreviousTile",
                model.ModifierOperation(model.OperatorKind.SET, 2))
            and not accepts("state.avoidPreviousTile",
                model.ModifierOperation(model.OperatorKind.ADD, 1)),
            "Task-6 speed/avoidPreviousTile oracle domains changed")
    from resolve_overworld_wild_behavior_v40 import apply_typed_operator
    require(apply_typed_operator(4, 22, 1, 0, 1, 0) == 1
            and apply_typed_operator(4, 22, 1, 1, 0, 0) == 0,
            "Task-5 typed executor disagrees on avoidPreviousTile SET")
    domain_match = re.search(
        r"TASK6_DOMAINS speedSet0=(\d+) avoidSet1=(\d+) "
        r"avoidSet0=(\d+) avoidSet2=(\d+) avoidAdd=(\d+)",
        fixture_output,
    )
    invalid_modifier = next(
        int(value) for name, value in c_statuses if name == "INVALID_MODIFIER"
    )
    require(domain_match is not None
            and tuple(map(int, domain_match.groups()))
                == (invalid_modifier, 1, 0, invalid_modifier, invalid_modifier),
            "C/Task-5/Task-6 scalar-domain trace differs")
    wide_match = re.search(
        r"TASK6_RUNTIME_S16 add33=(\d+) min=(\d+) max=(\d+) conflict=(\d+)",
        fixture_output,
    )
    require(wide_match is not None
            and tuple(map(int, wide_match.groups()))
                == (4, 0, 64, invalid_modifier),
            "C/Task-6 s16 saturation/conflicting-bound trace differs")
    return len(trace) + 6


def verify_timer_oracle_trace(fixture_output: str) -> int:
    model = load_model()
    catalog, ids = model._fixture_catalog()
    runtime = model.StackRuntime(catalog)
    slot = runtime.install_slot(0, model.StaticContext(map_id=1))
    runtime.apply(0, 2, ids["owner_stamina"])
    runtime.apply(0, 3, ids["owner_sleep"])
    runtime.apply(0, 4, ids["owner_pickup"])
    runtime.tick_candidate_timers(0, 2)
    paused = slot.timers[(ids["owner_stamina"], 0)].remaining_ticks
    continued = slot.timers[(ids["owner_sleep"], 0)].remaining_ticks
    plans = runtime.pending_expiry_plans(0)
    pending = len(plans)
    require(pending == 1, f"Task-10 oracle pending set changed: {plans}")
    runtime.commit_expiry(plans[0])
    expected = (paused, continued, pending, len(slot.layers), len(slot.timers))
    match = re.search(
        r"TASK10_TIMER_TRACE paused=(\d+) continued=(\d+) pending=(\d+) "
        r"layers=(\d+) timers=(\d+)",
        fixture_output,
    )
    require(match is not None, "C fixture did not publish its Task-10 timer trace")
    actual = tuple(int(value) for value in match.groups())
    require(actual == expected,
            f"C Task-10 timer trace {actual} differs from oracle {expected}")

    def timer_snapshot(candidate_runtime, candidate_slot, candidate_timer):
        return (
            model.canonical_json_bytes(model.to_data(candidate_timer)),
            model.canonical_json_bytes(model.to_data(
                candidate_slot.mandatory_expiry_registry)),
            candidate_runtime.runtime_epoch,
            candidate_slot.presentation_gate,
            candidate_slot.layer_generation,
            candidate_slot.effective_generation,
        )

    def rejected_without_mutation(mutator) -> bool:
        candidate_runtime = model.StackRuntime(catalog)
        candidate_slot = candidate_runtime.install_slot(
            0, model.StaticContext(map_id=1))
        candidate_runtime.apply(0, 2, ids["owner_stamina"])
        candidate_timer = candidate_slot.timers[(ids["owner_stamina"], 0)]
        mutator(candidate_timer)
        before = timer_snapshot(
            candidate_runtime, candidate_slot, candidate_timer)
        try:
            candidate_runtime.tick_candidate_timers(0, 1)
        except model.ModelError:
            return before == timer_snapshot(
                candidate_runtime, candidate_slot, candidate_timer)
        return False

    require(rejected_without_mutation(lambda timer: setattr(
                timer, "hidden_policy",
                model.HiddenPolicy.CONTINUE_WHILE_HIDDEN))
            and rejected_without_mutation(lambda timer: setattr(
                timer, "remaining_ticks", timer.armed_duration + 1))
            and rejected_without_mutation(lambda timer: setattr(
                timer, "remaining_ticks", 255)),
            "Task-10 oracle accepted metadata/duration drift or mutated state")

    rekey_runtime = model.StackRuntime(catalog)
    rekey_slot = rekey_runtime.install_slot(0, model.StaticContext(map_id=1))
    rekey_runtime.install_slot(1, model.StaticContext(map_id=1))
    rekey_runtime.apply(0, 5, ids["owner_weather"])
    rekey_runtime.apply(1, 3, ids["owner_sleep"], 77)
    rekey_runtime.tick_candidate_timers(1, 2)
    old_rekey_plan = rekey_runtime.pending_expiry_plans(1)[0]
    rekey_slot.next_timer_generation = model.GEN_MAX
    require(rekey_runtime.apply(0, 3, ids["owner_sleep"], 88).ok
            and rekey_runtime.commit_expiry(old_rekey_plan).status
                is model.Status.STALE_NOOP,
            "Task-10 oracle old rekey expiry is not stale-safe")

    restart_runtime = model.StackRuntime(catalog, runtime_epoch=model.GEN_MAX)
    restart_slot = restart_runtime.install_slot(
        0, model.StaticContext(map_id=1))
    restart_runtime.install_slot(1, model.StaticContext(map_id=1))
    restart_runtime.apply(1, 3, ids["owner_sleep"], 77)
    restart_runtime.tick_candidate_timers(1, 2)
    old_restart_plan = restart_runtime.pending_expiry_plans(1)[0]
    restart_slot.next_timer_generation = model.GEN_MAX
    require(restart_runtime.apply(0, 3, ids["owner_sleep"], 88).status
                is model.Status.RUNTIME_EPOCH_RESTARTED
            and restart_runtime.commit_expiry(old_restart_plan).status
                is model.Status.STALE_NOOP,
            "Task-10 oracle old restart expiry is not stale-safe")

    tag_runtime = model.StackRuntime(catalog)
    tag_slot = tag_runtime.install_slot(0, model.StaticContext(map_id=1))
    tag_runtime.apply(0, 3, ids["owner_sleep"], 77)
    tag_runtime.tick_candidate_timers(0, 2)
    live_tag_plan = tag_runtime.pending_expiry_plans(0)[0]
    altered_tag_plan = dict(live_tag_plan)
    altered_tag_plan["authenticator"] = (
        "1" * 64 if live_tag_plan["authenticator"] != "1" * 64
        else "2" * 64
    )
    tag_timer = tag_slot.timers[(ids["owner_sleep"], 77)]
    tag_before = timer_snapshot(tag_runtime, tag_slot, tag_timer)
    tag_result = tag_runtime.commit_expiry(altered_tag_plan)
    require(tag_result.status is model.Status.STALE_NOOP
            and tag_result.ok and not tag_result.mutated
            and tag_before == timer_snapshot(tag_runtime, tag_slot, tag_timer)
            and tag_runtime.pending_expiry_plans(0) == [live_tag_plan],
            "Task-10 oracle altered current expiry tag was not stale-safe")

    indefinite_runtime = model.StackRuntime(catalog)
    indefinite_slot = indefinite_runtime.install_slot(
        0, model.StaticContext(map_id=1))
    indefinite_runtime.apply(0, 13, ids["owner_sleep"], 88)
    indefinite_timer = indefinite_slot.timers[(ids["owner_sleep"], 88)]
    require(indefinite_timer.armed_duration == 255
            and indefinite_timer.remaining_ticks == 255,
            "Task-10 oracle did not arm a genuine indefinite timer")
    indefinite_timer.remaining_ticks = 254
    indefinite_before = timer_snapshot(
        indefinite_runtime, indefinite_slot, indefinite_timer)
    try:
        indefinite_runtime.tick_candidate_timers(0, 1)
    except model.ModelError as error:
        indefinite_rejected = error.status is model.Status.INVALID_HANDLE
    else:
        indefinite_rejected = False
    require(indefinite_rejected
            and indefinite_before == timer_snapshot(
                indefinite_runtime, indefinite_slot, indefinite_timer),
            "Task-10 oracle accepted indefinite duration drift or mutated state")

    status_values = {
        name: int(value) for name, value in re.findall(
            r"OW_WILD_RUNTIME_STATUS_([A-Z_]+)\s*=\s*(\d+)",
            HEADER.read_text())
    }
    correction_match = re.search(
        r"TASK10_TIMER_CORRECTION_TRACE metadata=(\d+) finite=(\d+) "
        r"indefinite=(\d+) rekey=(\d+) restart=(\d+) malformed=(\d+) "
        r"frameFailure=(\d+) frameRetry=(\d+) tagReplay=(\d+) "
        r"indefiniteDrift=(\d+) slot0=(\d+) slot1=(\d+)",
        fixture_output,
    )
    correction_expected = (
        status_values["INVALID_HANDLE"],
        status_values["INVALID_HANDLE"],
        status_values["INVALID_HANDLE"],
        status_values["STALE_NOOP"],
        status_values["STALE_NOOP"],
        status_values["INVALID_HANDLE"],
        status_values["INVALID_HANDLE"],
        status_values["OK"],
        status_values["STALE_NOOP"],
        status_values["INVALID_HANDLE"],
        3,
        3,
    )
    require(correction_match is not None
            and tuple(map(int, correction_match.groups()))
                == correction_expected,
            "C Task-10 correction trace differs from the oracle contract")
    return len(expected) + len(correction_expected)


def verify_task11_substrate_trace(fixture_output: str) -> int:
    status_values = {
        name: int(value) for name, value in re.findall(
            r"OW_WILD_RUNTIME_STATUS_([A-Z_]+)\s*=\s*(\d+)",
            HEADER.read_text())
    }
    match = re.search(
        r"TASK11_SUBSTRATE_TRACE invalidSelection=(\d+) "
        r"staleCommand=(\d+) calmRecovery=(\d+) removeSelf=(\d+) "
        r"canonicalMutations=(\d+) commandMutations=(\d+) "
        r"recoveries=(\d+) malformed=(\d+) mappingMutations=(\d+) "
        r"backlinkMutations=(\d+) semanticBacklinks=(\d+) "
        r"exactBacklinks=(\d+) staminaBacklinks=(\d+) "
        r"sleepBacklinks=(\d+) "
        r"calmOwners=(\d+) actions=(\d+)",
        fixture_output,
    )
    expected = (
        status_values["INVALID_TRANSLATION"],
        status_values["STALE_NOOP"],
        status_values["OK"],
        status_values["OK"],
        6,
        28,
        6,
        157,
        24,
        61,
        19,
        18,
        2,
        22,
        3,
        10,
    )
    require(match is not None and tuple(map(int, match.groups())) == expected,
            "Task11 substrate trace differs from the typed runtime contract")
    return len(expected)


def verify_make_package_invocation() -> None:
    source = MAKE_SCRIPT.read_text()
    require("if loader != 0x023BB980:" in source
            and "0x023BB400" not in source,
            "packaging overlay157 loader identity did not follow the split")
    try:
        tree = ast.parse(source, filename=str(MAKE_SCRIPT))
    except SyntaxError as error:
        raise SystemExit(
            f"runtime layer verification failed: packaging module is invalid: {error}"
        ) from error
    parser_functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "ParseOverlayLinkerId"
    ]
    require(len(parser_functions) == 1,
            "packaging overlay linker identity parser drifted")
    parser_module = ast.Module(body=[parser_functions[0]], type_ignores=[])
    ast.fix_missing_locations(parser_module)
    parser_namespace = {"re": re}
    exec(compile(parser_module, str(MAKE_SCRIPT), "exec"), parser_namespace)
    parse_overlay_id = parser_namespace["ParseOverlayLinkerId"]
    timer_header = TIMERS_LINKER.read_text().splitlines(keepends=True)[0]
    require(parse_overlay_id(timer_header, str(TIMERS_LINKER)) == 159,
            "overlay159 linker directory does not discover overlay ID 159")
    for malformed_header in (
        "",
        "OUTPUT_ARCH(arm)\n",
        "/* Overlay */\n",
        "/* Overlay 159 */ trailing\n",
        " /* Overlay 159 */\n",
        "/* Overlay 65536 */\n",
    ):
        try:
            parse_overlay_id(malformed_header, str(TIMERS_LINKER))
        except RuntimeError:
            continue
        require(False,
                "malformed/missing overlay linker identity header was accepted")

    writealls = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "writeall"
    ]
    require(len(writealls) == 1, "packaging writeall definition drifted")
    parser_calls = [
        node for node in ast.walk(writealls[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ParseOverlayLinkerId"
    ]
    require(len(parser_calls) == 2
            and all(len(call.args) == 2 and not call.keywords
                and isinstance(call.args[0], ast.Call)
                and isinstance(call.args[0].func, ast.Attribute)
                and isinstance(call.args[0].func.value, ast.Name)
                and call.args[0].func.value.id == "file"
                and call.args[0].func.attr == "readline"
                and not call.args[0].args
                and isinstance(call.args[1], ast.Name)
                and call.args[1].id == "linkerPath"
                for call in parser_calls)
            and "int(line.split(\" \")[2])" not in source,
            "writeall does not use the strict first-line overlay ID parser")
    runtime_verifier_names = (
        "VerifyOverworldWildRuntimeOverlay",
        "VerifyOverworldWildRuntimeLayersOverlay",
        "VerifyOverworldWildRuntimeTimersOverlay",
    )
    for verifier_name in runtime_verifier_names:
        verifier = next((
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == verifier_name
        ), None)
        require(verifier is not None,
                f"packaging {verifier_name} definition is missing")
        assignments = {
            statement.targets[0].id: statement.value.value
            for statement in verifier.body
            if isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        }
        check_calls = [
            node for node in ast.walk(verifier)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr == "check_call"
        ]
        require(assignments.get("core_owner") == "build/linked.o"
                and len(check_calls) == 1 and len(check_calls[0].args) == 1
                and isinstance(check_calls[0].args[0], ast.List),
                f"packaging {verifier_name} lacks the same-build core owner")
        command = check_calls[0].args[0].elts
        core_flags = [
            index for index, element in enumerate(command)
            if isinstance(element, ast.Constant)
            and element.value == "--core-owner"
        ]
        require(len(core_flags) == 1 and core_flags[0] + 1 < len(command)
                and isinstance(command[core_flags[0] + 1], ast.Name)
                and command[core_flags[0] + 1].id == "core_owner",
                f"packaging {verifier_name} does not pass --core-owner")

    functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "VerifyOverworldWildRuntimeLayersOverlay"
    ]
    require(len(functions) == 1, "packaging overlay158 verifier definition drifted")
    function = functions[0]
    arguments = function.args
    require(not isinstance(function, ast.AsyncFunctionDef)
            and not arguments.posonlyargs
            and [argument.arg for argument in arguments.args]
                == ["linked_path", "output_path", "packaged_path"]
            and not arguments.vararg
            and not arguments.kwonlyargs
            and not arguments.kwarg
            and not arguments.defaults,
            "packaging overlay158 verifier signature drifted")

    executable = ("attribute", "sys", "executable")
    values: dict[str, object] = {
        "linked_path": ("parameter", "linked_path"),
        "output_path": ("parameter", "output_path"),
        "packaged_path": ("parameter", "packaged_path"),
    }

    def evaluate(expression: ast.expr) -> object:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return expression.value
        if isinstance(expression, ast.Name) and expression.id in values:
            return values[expression.id]
        if (isinstance(expression, ast.Attribute)
                and isinstance(expression.value, ast.Name)
                and expression.value.id == "sys"
                and expression.attr == "executable"):
            return executable
        if isinstance(expression, ast.List):
            return [evaluate(element) for element in expression.elts]
        raise ValueError(ast.dump(expression, include_attributes=False))

    invocations: list[list[object]] = []
    for statement in function.body:
        if (isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)):
            try:
                values[statement.targets[0].id] = evaluate(statement.value)
            except ValueError:
                pass
            continue
        if (isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Attribute)
                and isinstance(statement.value.func.value, ast.Name)
                and statement.value.func.value.id == "subprocess"
                and statement.value.func.attr == "check_call"):
            require(len(statement.value.args) == 1 and not statement.value.keywords,
                    "packaging-time overlay158 verifier call shape drifted")
            try:
                command = evaluate(statement.value.args[0])
            except ValueError as error:
                raise SystemExit(
                    "runtime layer verification failed: packaging-time overlay158 "
                    f"verifier arguments cannot be resolved: {error}"
                ) from error
            require(isinstance(command, list),
                    "packaging-time overlay158 verifier command is not a list")
            invocations.append(command)

    require(invocations == [[
        executable,
        "scripts/verify_overworld_wild_overlay_size.py",
        ("parameter", "linked_path"),
        "--binary", ("parameter", "output_path"), "--overlay", "158",
        "--task5-owner", "build/pokemon_move_history_task6_overlay_linked.o",
        "--lifecycle-consumer",
        "build/pokemon_move_history_task6_overlay_linked.o",
        "--lifecycle-object",
        "build/pokemon_move_history_task6_overlay/overworld_wild_behavior_support.o",
        "--scalar-shard",
        "build/overworld_wild_runtime_layers_overlay/owbd_v40_scalar_symbols.o",
        "--core-owner", "build/linked.o",
        "--catalog-owner", "build/overworld_wild_runtime_overlay_linked.o",
        "--catalog-carrier",
        "build/overworld_wild_runtime_overlay_catalog_symbols.o",
        "--task8-carrier",
        "build/overworld_wild_runtime_layers_overlay_task8_symbols.o",
        "--production-object",
        "build/overworld_wild_runtime_overlay/overworld_wild_runtime_layers.o",
        "--runtime-carrier",
        "build/pokemon_move_history_task6_overlay_task7_runtime_symbols.o",
        "--spawns-consumer", "build/overworld_wild_spawns_overlay_linked.o",
    ]], "packaging-time overlay158 verifier invocation drifted")

    def named_call(node: ast.AST, name: str) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == name)

    def indexed_name(node: ast.AST, name: str, plus_one: bool) -> bool:
        if (not isinstance(node, ast.Subscript)
                or not isinstance(node.value, ast.Name)
                or node.value.id != name):
            return False
        index = node.slice
        if plus_one:
            return (isinstance(index, ast.BinOp)
                    and isinstance(index.left, ast.Name)
                    and index.left.id == "i"
                    and isinstance(index.op, ast.Add)
                    and isinstance(index.right, ast.Constant)
                    and index.right.value == 1)
        return isinstance(index, ast.Name) and index.id == "i"

    def overlay158_guard(node: ast.AST) -> bool:
        return (isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "newOverlay"
                and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.Eq)
                and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value == 158)

    def writeall_integration_matches(candidate: ast.Module) -> bool:
        writealls = [
            node for node in candidate.body
            if isinstance(node, ast.FunctionDef) and node.name == "writeall"
        ]
        if len(writealls) != 1:
            return False
        writeall = writealls[0]
        calls = [
            node for node in ast.walk(writeall)
            if named_call(node, "VerifyOverworldWildRuntimeLayersOverlay")
        ]
        if len(calls) != 1:
            return False
        call = calls[0]
        guards = [
            node for node in ast.walk(writeall)
            if overlay158_guard(node)
            and any(isinstance(statement, ast.Expr)
                    and statement.value is call for statement in node.body)
        ]
        if len(guards) != 1:
            return False
        parents = {
            child: parent for parent in ast.walk(writeall)
            for child in ast.iter_child_nodes(parent)
        }
        ancestor = parents.get(call)
        while ancestor is not None and ancestor is not writeall:
            if isinstance(ancestor, ast.If) and ancestor is not guards[0]:
                return False
            ancestor = parents.get(ancestor)
        return (len(call.args) == 3 and not call.keywords
                and indexed_name(call.args[0], "LINKED_SECTIONS", True)
                and indexed_name(call.args[1], "NEW_OVERLAYS", False)
                and isinstance(call.args[2], ast.Name)
                and call.args[2].id == "overlayPath")

    require(writeall_integration_matches(tree),
            "writeall overlay158 verifier integration drifted")

    missing = ast.parse(source, filename=str(MAKE_SCRIPT))
    missing_call = next(
        node for node in ast.walk(missing)
        if named_call(node, "VerifyOverworldWildRuntimeLayersOverlay")
    )
    missing_call.func.id = "DeletedOverworldWildRuntimeLayersVerifier"
    require(not writeall_integration_matches(missing),
            "writeall verifier deletion negative fixture was accepted")

    wrong_guard = ast.parse(source, filename=str(MAKE_SCRIPT))
    guarded_call = next(
        node for node in ast.walk(wrong_guard)
        if named_call(node, "VerifyOverworldWildRuntimeLayersOverlay")
    )
    guard = next(
        node for node in ast.walk(wrong_guard)
        if overlay158_guard(node)
        and guarded_call in ast.walk(node)
    )
    guard.test.comparators[0].value = 159
    require(not writeall_integration_matches(wrong_guard),
            "writeall wrong-guard negative fixture was accepted")

    misrouted = ast.parse(source, filename=str(MAKE_SCRIPT))
    misrouted_call = next(
        node for node in ast.walk(misrouted)
        if named_call(node, "VerifyOverworldWildRuntimeLayersOverlay")
    )
    misrouted_call.args[0] = ast.Subscript(
        value=ast.Name(id="NEW_OVERLAYS", ctx=ast.Load()),
        slice=ast.Name(id="i", ctx=ast.Load()), ctx=ast.Load())
    require(not writeall_integration_matches(misrouted),
            "writeall misrouted-argument negative fixture was accepted")

    timer_functions = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "VerifyOverworldWildRuntimeTimersOverlay"
    ]
    require(len(timer_functions) == 1,
            "packaging overlay159 verifier definition drifted")
    timer_function = timer_functions[0]
    require(
        not isinstance(timer_function, ast.AsyncFunctionDef)
        and [argument.arg for argument in timer_function.args.args]
            == ["linked_path", "output_path", "packaged_path"]
        and not timer_function.args.posonlyargs
        and not timer_function.args.vararg
        and not timer_function.args.kwonlyargs
        and not timer_function.args.kwarg
        and not timer_function.args.defaults,
        "packaging overlay159 verifier signature drifted")
    def timer_package_invocations(candidate: ast.Module) -> list[list[object]]:
        functions = [
            node for node in candidate.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "VerifyOverworldWildRuntimeTimersOverlay"
        ]
        if len(functions) != 1:
            return []
        values: dict[str, object] = {
            "linked_path": ("parameter", "linked_path"),
            "output_path": ("parameter", "output_path"),
            "packaged_path": ("parameter", "packaged_path"),
        }

        def evaluate_timer(expression: ast.expr) -> object:
            if (isinstance(expression, ast.Constant)
                    and isinstance(expression.value, str)):
                return expression.value
            if isinstance(expression, ast.Name) and expression.id in values:
                return values[expression.id]
            if (isinstance(expression, ast.Attribute)
                    and isinstance(expression.value, ast.Name)
                    and expression.value.id == "sys"
                    and expression.attr == "executable"):
                return executable
            if isinstance(expression, ast.List):
                return [evaluate_timer(element) for element in expression.elts]
            raise ValueError(ast.dump(expression, include_attributes=False))

        invocations: list[list[object]] = []
        for statement in functions[0].body:
            if (isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)):
                try:
                    values[statement.targets[0].id] = evaluate_timer(
                        statement.value)
                except ValueError:
                    pass
                continue
            if (isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Attribute)
                    and isinstance(statement.value.func.value, ast.Name)
                    and statement.value.func.value.id == "subprocess"
                    and statement.value.func.attr == "check_call"):
                try:
                    invocations.append(evaluate_timer(statement.value.args[0]))
                except (IndexError, ValueError):
                    return []
        return invocations

    expected_timer_invocations = [[
        executable,
        "scripts/verify_overworld_wild_overlay_size.py",
        ("parameter", "linked_path"),
        "--binary", ("parameter", "output_path"), "--overlay", "159",
        "--layers-owner", "build/overworld_wild_runtime_layers_overlay_linked.o",
        "--task8-carrier",
        "build/overworld_wild_runtime_layers_overlay_task8_symbols.o",
        "--catalog-owner", "build/overworld_wild_runtime_overlay_linked.o",
        "--catalog-carrier",
        "build/overworld_wild_runtime_overlay_catalog_symbols.o",
        "--core-owner", "build/linked.o",
        "--timer-carrier",
        "build/overworld_wild_runtime_timers_overlay_timer_symbols.o",
        "--timer-object",
        "build/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.o",
        "--production-object",
        "build/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.o",
    ]]
    require(timer_package_invocations(tree) == expected_timer_invocations,
            "packaging-time overlay159 verifier invocation drifted")
    for mutation, message in (
        ("missing", "packaging overlay159 accepted absent timer-object wiring"),
        ("wrong", "packaging overlay159 accepted wrong timer-object wiring"),
    ):
        candidate = ast.parse(source, filename=str(MAKE_SCRIPT))
        candidate_function = next(
            node for node in candidate.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "VerifyOverworldWildRuntimeTimersOverlay"
        )
        if mutation == "wrong":
            assignment = next(
                node for node in candidate_function.body
                if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "timer_object"
            )
            assignment.value = ast.Constant(
                "build/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.o"
            )
        else:
            invocation = next(
                node.value for node in candidate_function.body
                if isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "check_call"
            )
            command = invocation.args[0]
            flag_index = next(
                index for index, element in enumerate(command.elts)
                if isinstance(element, ast.Constant)
                and element.value == "--timer-object"
            )
            del command.elts[flag_index:flag_index + 2]
        require(timer_package_invocations(candidate)
                != expected_timer_invocations, message)

    def overlay159_integration_matches(candidate: ast.Module) -> bool:
        writeall = next((node for node in candidate.body
                         if isinstance(node, ast.FunctionDef)
                         and node.name == "writeall"), None)
        if writeall is None:
            return False
        calls = [node for node in ast.walk(writeall)
                 if named_call(node, "VerifyOverworldWildRuntimeTimersOverlay")]
        if len(calls) != 1:
            return False
        call = calls[0]
        guards = [node for node in ast.walk(writeall)
                  if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Compare)
                  and isinstance(node.test.left, ast.Name)
                  and node.test.left.id == "newOverlay"
                  and len(node.test.comparators) == 1
                  and isinstance(node.test.comparators[0], ast.Constant)
                  and node.test.comparators[0].value == 159
                  and call in ast.walk(node)]
        return (len(guards) == 1 and len(call.args) == 3 and not call.keywords
                and indexed_name(call.args[0], "LINKED_SECTIONS", True)
                and indexed_name(call.args[1], "NEW_OVERLAYS", False)
                and isinstance(call.args[2], ast.Name)
                and call.args[2].id == "overlayPath")

    require(overlay159_integration_matches(tree),
            "writeall overlay159 verifier integration drifted")
    for mutation, message in (
        ("delete", "overlay159 verifier deletion negative fixture was accepted"),
        ("guard", "overlay159 wrong-guard negative fixture was accepted"),
        ("route", "overlay159 misrouted-argument negative fixture was accepted"),
    ):
        candidate = ast.parse(source, filename=str(MAKE_SCRIPT))
        call = next(node for node in ast.walk(candidate)
                    if named_call(node, "VerifyOverworldWildRuntimeTimersOverlay"))
        if mutation == "delete":
            call.func.id = "DeletedOverworldWildRuntimeTimersVerifier"
        elif mutation == "guard":
            guard = next(node for node in ast.walk(candidate)
                         if isinstance(node, ast.If) and call in ast.walk(node))
            guard.test.comparators[0].value = 158
        else:
            call.args[0] = ast.Subscript(
                value=ast.Name(id="NEW_OVERLAYS", ctx=ast.Load()),
                slice=ast.Name(id="i", ctx=ast.Load()), ctx=ast.Load())
        require(not overlay159_integration_matches(candidate), message)


def verify_source_contracts() -> None:
    header = HEADER.read_text()
    source = OVERLAY_SOURCE.read_text()
    implementation = IMPLEMENTATION.read_text()
    internal_header = INTERNAL_HEADER.read_text()
    linker = OVERLAY_LINKER.read_text()
    layers_linker = LAYERS_LINKER.read_text()
    timers_linker = TIMERS_LINKER.read_text()
    timers_source = TIMERS_SOURCE.read_text()
    spawns_linker = SPAWNS_LINKER.read_text()
    fixture = FIXTURE.read_text()
    catalog_fixture = CATALOG_FIXTURE.read_text()
    catalog_timer_fixture = CATALOG_TIMER_FIXTURE.read_text()
    task6_linker = TASK6_LINKER.read_text()
    history_linker = HISTORY_LINKER.read_text()
    overlays_mk = OVERLAYS_MK.read_text()
    save_header = SAVE_HEADER.read_text()
    startup = STARTUP.read_text()
    byte_replacement = BYTE_REPLACEMENT.read_text()
    shared_v40_validation = SHARED_V40_VALIDATION.read_text()
    v40_scalar_symbols = V40_SCALAR_SYMBOLS.read_text()

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

    projection_flag_definitions = (
        "#define OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL (1u << 0)",
        "#define OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE (1u << 1)",
        "#define OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL_PHANTOM (1u << 2)",
        "#define OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE_PHANTOM (1u << 3)",
    )
    for token in projection_flag_definitions:
        require(header.count(token) == 1,
                f"shared movement projection flag differs: {token}")
    projection_prototype = (
        "u8 OverworldWildRuntime_GetMovementProjectionFlags(\n"
        "    const OverworldWildRuntimeStaticCache *staticCache,\n"
        "    const OverworldWildRuntimeEffectiveCache *effective);"
    )
    require(header.count(projection_prototype) == 1,
            "movement projection helper prototype is missing or duplicated")

    declaration_start = header.index("/* Lifecycle-only binding.")
    declaration_end = header.index("static inline void OverworldWildRuntime_Activate")
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
    require("OwbdStaticValueValid" in shared_v40_validation
            and "OwbdModifierPayloadValid" in shared_v40_validation,
            "shared Task-5 v40 scalar domain helpers are absent")
    for token in (
        ".type sOwbdStateValueMax, %object",
        ".set sOwbdStateValueMax, 0x023BDEAE",
        ".type sOwbdNumericFieldMasks, %object",
        ".set sOwbdNumericFieldMasks, 0x023BDECC",
        ".type OwbdStaticValueValid, %function",
        ".thumb_set OwbdStaticValueValid, 0x023BDF8D",
        ".type OwbdModifierPayloadValid, %function",
        ".thumb_set OwbdModifierPayloadValid, 0x023BE031",
    ):
        require(token in v40_scalar_symbols,
                f"typed overlay155 scalar-symbol shard differs: {token}")
    for token in (
        "sOwbdNumericFieldMasks[maskIndex]",
        "OwbdStaticValueValid(kind, fieldId, maximum)",
        "OwbdModifierPayloadValid(",
        "ValidateCacheKey(",
        "OverworldWildRuntime_ValidateStaticCache(",
        "OverworldWildRuntime_CopyResolvedCachedNode(",
        "OverworldWildRuntime_ResolveRetainedStaticCache(",
        "OverworldWildRuntime_HandleSlotGenerationWrap(",
        "InitializeInvalidatedSlot(",
        "provenanceOut->candidates[i].isWinner = i == 0;",
        "contribution->staticPriority",
        "contribution->ruleStableId",
        "contribution->actionStableId",
    ):
        require(token in implementation,
                f"Task-9 correction source assertion missing: {token}")
    require(implementation.count("ValidateCacheKey(runtime, slot)") >= 2
            and implementation.count("ValidateCacheQuery(") >= 4,
            "prime/copy-out queries do not share full cache-key validation")
    require("CopyRetainedApplicability(" not in implementation
            and "ResolveRetainedStaticCache(\n"
                "    const OverworldWildRuntimeSlotSidecar" not in implementation
            and "OverworldWildRuntime_ResolveRetainedStaticCache(\n"
                "        &slot->staticCache, slot->staticContextGeneration,\n"
                "        &prospectiveStatic);"
                in implementation,
            "overlay158 retained-static authentication ownership drifted")
    require("OverworldWildRuntimeStatus "
                "OverworldWildRuntime_ResolveRetainedStaticCache(\n"
                "    const OverworldWildRuntimeStaticCache *retainedCache,\n"
                "    u32 staticContextGeneration,\n"
                "    OverworldWildRuntimeStaticCache *resolvedOut);"
                in internal_header,
            "typed retained-static catalog API declaration drifted")
    for token in (
        "OverworldWildRuntimeStatus OverworldWildRuntime_ResolveRetainedStaticCache(",
        "retainedCache == resolvedOut",
        "OverworldWildRuntime_ValidateStaticCache(\n"
            "            retainedCache, staticContextGeneration)",
        "*resolvedOut = *retainedCache",
    ):
        require(token in source,
                f"overlay157 retained-static API assertion missing: {token}")
    require("RuntimeCopyRetainedApplicability(" not in source,
            "overlay157 retained re-resolution rebuilt caller applicability")
    projection_helper = function_body(
        source, "u8 OverworldWildRuntime_GetMovementProjectionFlags(")
    require_tokens = (
        "u8 flags = 0;",
        "u8 locomotion = effective->primitives[0];",
        "effective->semanticRole == OWBD_ROLE_CALM",
        "staticCache->spawnConfiguration.pickupThrowEntry != 0",
        "effective->primitives[1] == OW_WILD_BEHAVIOR_TARGET_TREE_TOP",
        "locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP",
        "locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_RAM",
        "flags |= OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL;",
        "locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT",
        "flags |= OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL_PHANTOM;",
        "effective->semanticRole == OWBD_ROLE_ATTENTIVE",
        "flags |= OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE_PHANTOM;",
        "effective->capabilityMask & OW_WILD_RUNTIME_CAP_FRAME_WORK",
        "flags |= OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE;",
        "return flags;",
    )
    for token in require_tokens:
        require(token in projection_helper,
                f"movement projection helper semantic drift: {token}")
    require(source.count(
                "u8 OverworldWildRuntime_GetMovementProjectionFlags(") == 1,
            "movement projection helper definition is missing or duplicated")
    require("overworld_wild_runtime_layers_internal.h" in source,
            "production runtime overlay does not bind the internal module")
    require("void OverworldWildRuntime_MarkResidentCold(" in source
            and "#ifdef OW_WILD_RUNTIME_HOST_TEST\nvoid "
                "OverworldWildRuntime_MarkResidentCold(" in implementation
            and "static inline void OverworldWildRuntime_MarkResidentCold"
                not in header,
            "resident cold lifecycle helper ownership drifted")
    for label, body in (
        ("production", function_body(source,
            "void OverworldWildRuntime_MarkResidentCold(")),
        ("host", function_body(implementation,
            "void OverworldWildRuntime_MarkResidentCold(")),
    ):
        for token in (
            "OverworldWildRuntimeStaticContext staticContext =",
            "runtime->slots[slot].staticCache.staticContext;",
            "offsetof(OverworldWildRuntimeSlotSidecar, staticCache)",
            "runtime->slots[slot].staticCache.staticContext = staticContext;",
        ):
            require(token in body,
                f"{label} resident-cold context retention missing: {token}")
        require(body.index("staticCache.staticContext;")
                < body.index("memset(")
                < body.index("staticCache.staticContext = staticContext;"),
                f"{label} resident-cold context save/clear/restore order drifted")
    for token in (
        "ORIGIN = 0x023CD000, LENGTH = 0xB000",
        "ASSERT(. <= ORIGIN(rom) + 0xAEC4,",
        ". = ORIGIN(rom) + 0xAEC4;",
        "__bss_end__ <= ORIGIN(rom) + 0xAF80",
    ):
        require(token in spawns_linker,
                f"overlay149 sealed-link assertion missing: {token}")
    for token in (
        "ORIGIN = 0x023BB980, LENGTH = 0x1A80",
        "OverworldWildBehavior_LoadValidatedBundle == ORIGIN(rom)",
        "__bss_end__ - __bss_start__ <= 0x140",
        "__bss_end__ <= ORIGIN(rom) + LENGTH(rom) - 0x80",
        "__bss_end__ <= 0x023BD380",
    ):
        require(token in linker, f"overlay157 frozen-link assertion missing: {token}")
    for token in (
        "ORIGIN = 0x023B8400, LENGTH = 0x3580",
        "*overworld_wild_runtime_layers.o(.text*)",
        "*overworld_wild_runtime_layers.o(\n                    .ow_wild_runtime_composition)",
        "__bss_end__ - __bss_start__ <= 0x140",
        "__bss_end__ <= 0x023BB900",
    ):
        require(token in layers_linker,
                f"overlay158 fixed-link assertion missing: {token}")
    for token in (
        "ORIGIN = 0x023BF480, LENGTH = 0xF80",
        "OverworldWildRuntime_GetTimerCount = .;",
        "OverworldWildRuntime_GetTimerCount == ORIGIN(rom)",
        "__bss_end__ <= 0x023C0380",
    ):
        require(token in timers_linker,
                f"overlay159 fixed-link assertion missing: {token}")
    require("ORIGIN = 0x023BD400, LENGTH = 0x1000" in task6_linker,
            "frozen overlay155 window changed")
    require("ORIGIN = 0x023BE400, LENGTH = 0x2000" in history_linker,
            "overlay153 guarded window changed")
    require("#define NEW_HEAP3_SIZE 0x108000" in save_header,
            "heap3 does not reserve the approved 0x8000 resident footprint")
    require("#define NEW_FIELD2_HEAP_SIZE 0x19000" in save_header,
            "field2 does not return the paired 0x3000 to heap3")
    require("arm9 0203DFE2 19 22" in byte_replacement
            and "arm9 0203DFEA 12 03" in byte_replacement,
            "FieldSystem_New field2 heap-size patch is missing")
    require(startup.count("mov r1, #155") == 1
            and startup.count("mov r1, #153") == 1
            and startup.count("mov r4, #157") == 1
            and startup.count("cmp r4, #160") == 1
            and startup.index("mov r1, #155")
                < startup.index("bl LoadResidentRuntimeOverlays")
                < startup.index("mov r1, #153"),
            "resident boot order is not 155 -> loop(157..159) -> 153")
    for token in (
        "bl LoadResidentRuntimeOverlays",
        ".org 0x021102E0",
        ".area 0x14, 0xFF",
        "LoadResidentRuntimeOverlays:",
        "LoadNextResidentRuntimeOverlay:",
        "push {r3-r5, lr}",
        "pop {r3-r5, pc}",
        ".endarea",
    ):
        require(token in startup,
                f"bounded overlay158 startup helper is missing: {token}")
    helper = startup[startup.index("LoadResidentRuntimeOverlays:"):
                     startup.index(".endarea", startup.index(
                         "LoadResidentRuntimeOverlays:"))]
    instructions = [line.strip() for line in helper.splitlines()
                    if line.startswith("    ")]
    require(instructions == [
        "push {r3-r5, lr}", "mov r4, #157", "mov r1, r4",
        "bl LoadResidentOverlay", "add r4, #1", "cmp r4, #160",
        "blo LoadNextResidentRuntimeOverlay", "pop {r3-r5, pc}",
    ], "resident runtime loop instruction inventory drifted")
    for token in (
        "OVERWORLD_WILD_TASK8_SYMBOLS :=",
        "OVERWORLD_WILD_TIMER_SYMBOLS :=",
        "OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS :=",
        "OVERWORLD_WILD_V40_SCALAR_SYMBOLS :=",
        "--keep-symbol=OverworldWildBehavior_LoadValidatedBundle",
        "--keep-symbol=OverworldWildRuntime_ApplyStackDelta",
        "--keep-symbol=OverworldWildRuntime_PrimeEffectiveCache",
        "--keep-symbol=OverworldWildRuntime_GetEffectiveCache",
        "--keep-symbol=OverworldWildRuntime_GetCapabilityMask",
        "--keep-symbol=OverworldWildRuntime_GetProvenance",
        "$(BUILD)/overworld_wild_runtime_overlay_linked.o",
        "$(BUILD)/overworld_wild_runtime_layers_overlay_linked.o",
        "$(BUILD)/overworld_wild_runtime_timers_overlay_linked.o",
        "OVERWORLD_WILD_RUNTIME_LAYERS_OVERLAY_CFLAGS := -frename-registers",
        "-fno-inline-functions-called-once",
        "-fno-tree-sra -fno-tree-vrp -fno-ipa-cp",
        "--keep-symbol=OverworldWildRuntime_CopyInstalledStaticCache",
        "--keep-symbol=OverworldWildRuntime_ResolveRetainedStaticCache",
        "--keep-symbol=OverworldWildRuntime_ValidateStaticCache",
        "--keep-symbol=OverworldWildRuntime_CopyValidatedSpawnConfiguration",
        "--keep-symbol=OverworldWildRuntime_CopyResolvedCachedNode",
        "--keep-symbol=OverworldWildRuntime_MarkResidentCold",
        "--keep-symbol=OverworldWildRuntime_GetMovementProjectionFlags",
        "--task5-owner $(BUILD)/pokemon_move_history_task6_overlay_linked.o",
        "--lifecycle-consumer $(BUILD)/pokemon_move_history_task6_overlay_linked.o",
        "--lifecycle-object $(BUILD)/pokemon_move_history_task6_overlay/overworld_wild_behavior_support.o",
        "--scalar-shard $(OVERWORLD_WILD_V40_SCALAR_SYMBOLS)",
        "--core-owner $(LINK)",
        "--just-symbols=$(LINK)",
        "--catalog-owner $(overworld_wild_runtime_overlay_LINK)",
        "--catalog-carrier $(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS)",
        "--task8-carrier $(OVERWORLD_WILD_TASK8_SYMBOLS)",
        "--production-object $(OVERWORLD_WILD_LAYERS_OBJECT)",
        "--runtime-carrier $(OVERWORLD_WILD_RUNTIME_SYMBOLS)",
        "--spawns-consumer $(BUILD)/overworld_wild_spawns_overlay_linked.o",
        "--overlay 157",
        "--overlay 158",
        "--overlay 159",
        "--layers-owner $(overworld_wild_runtime_layers_overlay_LINK)",
        "--timer-carrier $(OVERWORLD_WILD_TIMER_SYMBOLS)",
        "--timer-object $(OVERWORLD_WILD_TIMERS_OBJECT)",
    ):
        require(token in overlays_mk, f"resident build/link integration missing: {token}")
    require(overlays_mk.count("--just-symbols=$(LINK)") == 3
            and overlays_mk.count("--core-owner $(LINK)") == 3,
            "resident core Thumb owner is not wired exactly once per overlay")
    task8_carrier = overlays_mk[
        overlays_mk.index("$(OVERWORLD_WILD_TASK8_SYMBOLS):"):
        overlays_mk.index("$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS):")]
    catalog_carrier = overlays_mk[
        overlays_mk.index("$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS):"):
        overlays_mk.index(
            "$(BUILD)/overworld_wild_runtime_layers_overlay_linked.o:")]
    require("--keep-symbol=OverworldWildRuntime_MarkResidentCold"
            not in task8_carrier
            and "--keep-symbol=OverworldWildRuntime_MarkResidentCold"
                in catalog_carrier,
            "resident cold helper is not owned by overlay157 catalog carrier")
    require("--keep-symbol=OverworldWildRuntime_ResolveRetainedStaticCache"
            not in task8_carrier
            and "--keep-symbol=OverworldWildRuntime_ResolveRetainedStaticCache"
                in catalog_carrier,
            "retained-static API is not owned by overlay157 catalog carrier")
    require("--keep-symbol=OverworldWildRuntime_GetMovementProjectionFlags"
            not in task8_carrier
            and catalog_carrier.count(
                "--keep-symbol=OverworldWildRuntime_GetMovementProjectionFlags")
                == 1,
            "movement projection helper is not exported exactly once by the "
            "overlay157 catalog carrier")
    timer_api_names = (
        "OverworldWildRuntime_GetTimerCount",
        "OverworldWildRuntime_GetTimerByIndex",
        "OverworldWildRuntime_SetTimerPresentationGate",
        "OverworldWildRuntime_TickCandidateTimers",
        "OverworldWildRuntime_TickFrameTimers",
        "OverworldWildRuntime_TickCompletedMovementTimers",
        "OverworldWildRuntime_GetPendingTimerExpiryCount",
        "OverworldWildRuntime_GetPendingTimerExpiryByIndex",
        "OverworldWildRuntime_DispatchTransition",
        "OverworldWildRuntime_CaptureCommandOrigin",
        "OverworldWildRuntime_ConsumeCommandOrigin",
        "OverworldWildRuntime_InvalidateCommandOrigin",
        "OverworldWildRuntime_InvalidateAllCommandOrigins",
    )
    timer_carrier_start = overlays_mk.index("$(OVERWORLD_WILD_TIMER_SYMBOLS):")
    timer_carrier = overlays_mk[timer_carrier_start:]
    require(all(f"--keep-symbol={name}" not in task8_carrier
                and f"--keep-symbol={name}" in timer_carrier
                for name in timer_api_names),
            "public timer API carrier ownership did not move to overlay159")
    for name in (
        "OverworldWildRuntime_ValidateTimerQueryInternal",
        "OverworldWildRuntime_TimerExpiryTagInternal",
        "OverworldWildRuntime_PreflightTimerExpiryInternal",
        "OverworldWildRuntime_MakeTimerRemovalHandleInternal",
        "OverworldWildRuntime_ApplyStackDeltaCompact",
    ):
        require(f"--keep-symbol={name}" in task8_carrier,
                f"overlay158 timer-internal carrier is missing {name}")
    require("OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD" in overlays_mk,
            "overlay158 production compile does not externalize timer APIs")
    layers_output_rule = overlays_mk[
        overlays_mk.index("$(overworld_wild_runtime_layers_overlay_OUTPUT):"):
        overlays_mk.index("$(overworld_wild_runtime_timers_overlay_LINK):")]
    require(layers_output_rule.count("$(overworld_wild_runtime_overlay_LINK)") == 2,
            "overlay158 package gate does not depend on and authenticate the exact "
            "same-build overlay157 owner")
    timers_output_rule = overlays_mk[
        overlays_mk.index("$(overworld_wild_runtime_timers_overlay_OUTPUT):"):
        overlays_mk.index("$(BUILD)/overworld_wild_behavior_validator_overlay_linked.o:")]
    def timers_output_gate_matches(rule: str) -> bool:
        prerequisite_end = rule.find("\n\t")
        if prerequisite_end < 0:
            return False
        prerequisites = rule[:prerequisite_end]
        recipe = rule[prerequisite_end:]
        return (
            rule.count("$(overworld_wild_runtime_layers_overlay_LINK)") == 2
            and rule.count("$(overworld_wild_runtime_overlay_LINK)") == 2
            and rule.count("$(OVERWORLD_WILD_TASK8_SYMBOLS)") == 2
            and rule.count("$(OVERWORLD_WILD_RUNTIME_CATALOG_SYMBOLS)") == 2
            and rule.count("$(LINK)") == 2
            and rule.count("$(OVERWORLD_WILD_TIMER_SYMBOLS)") == 2
            and prerequisites.count("$(OVERWORLD_WILD_TIMERS_OBJECT)") == 1
            and recipe.count(
                "--core-owner $(LINK)") == 1
            and recipe.count(
                "--timer-object $(OVERWORLD_WILD_TIMERS_OBJECT)") == 1
        )

    require(timers_output_gate_matches(timers_output_rule),
            "overlay159 package gate lacks exact same-build owner/carriers")
    missing_prerequisite = timers_output_rule.replace(
        "    $(OVERWORLD_WILD_TIMERS_OBJECT) \\\n", "", 1)
    missing_core_prerequisite = timers_output_rule.replace(
        "    $(LINK) \\\n", "", 1)
    missing_argument = timers_output_rule.replace(
        " \\\n\t\t--timer-object $(OVERWORLD_WILD_TIMERS_OBJECT)", "", 1)
    missing_core_argument = timers_output_rule.replace(
        " \\\n\t\t--core-owner $(LINK)", "", 1)
    wrong_argument = timers_output_rule.replace(
        "--timer-object $(OVERWORLD_WILD_TIMERS_OBJECT)",
        "--timer-object $(OVERWORLD_WILD_RUNTIME_SYMBOLS)", 1)
    require(not timers_output_gate_matches(missing_prerequisite)
            and not timers_output_gate_matches(missing_core_prerequisite)
            and not timers_output_gate_matches(missing_argument)
            and not timers_output_gate_matches(missing_core_argument)
            and not timers_output_gate_matches(wrong_argument),
            "overlay159 timer-object Make wiring mutation was accepted")
    require(all(name + "(" in timers_source for name in timer_api_names),
            "overlay159 timer shard is missing a public API implementation")
    command_origin_body = function_body(
        timers_source,
        "static OverworldWildRuntimeStatus CopyCommandOrigin(\n"
        "    const OverworldWildBehaviorStackRuntime *runtime,",
    )
    require("OverworldWildRuntime_GetEffectiveCache(" in command_origin_body
            and "slot->provenance.winningDefinitionId" in command_origin_body
            and "OverworldWildRuntime_GetProvenance(" not in command_origin_body,
            "command-origin hot path reconstructs diagnostic provenance")
    timer_query_body = function_body(
        implementation,
        "OverworldWildRuntimeStatus OverworldWildRuntime_ValidateTimerQueryInternal(\n"
        "    const OverworldWildBehaviorStackRuntime *runtime,\n"
        "    u8 slotIndex,\n"
        "    u32 expectedSlotGeneration)\n{",
    )
    require("ValidateBank(&runtime->slots[slotIndex])" in timer_query_body
            and "ValidateStoredSlotSemantics(&runtime->slots[slotIndex])"
                in timer_query_body
            and "timer->armedDuration == 255" in implementation
            and "timer->remainingTicks > timer->armedDuration" in implementation,
            "timer query preflight does not authenticate definition/duration state")
    expiry_preflight_body = function_body(
        implementation,
        "OverworldWildRuntimeStatus OverworldWildRuntime_PreflightTimerExpiryInternal(\n"
        "    const OverworldWildBehaviorStackRuntime *runtime,\n"
        "    const OverworldWildRuntimeTimerExpiry *expiry)\n{",
    )
    require(expiry_preflight_body.index(
                "expiry->runtimeEpoch != runtime->handleEpoch")
            < expiry_preflight_body.index(
                "OverworldWildRuntime_TimerExpiryTagInternal(runtime, expiry)"),
            "stale expiry identity is authenticated after the rotated tag")
    for frame_source, validator in (
        (implementation, "ValidateTimerQuery(runtime, i,"),
        (timers_source,
            "OverworldWildRuntime_ValidateTimerQueryInternal(runtime, i,"),
    ):
        frame_body = function_body(
            frame_source,
            "OverworldWildRuntimeStatus OverworldWildRuntime_TickFrameTimers(\n"
            "    OverworldWildBehaviorStackRuntime *runtime, u16 presentationGateMask,\n"
            "    OverworldWildRuntimeTimerTickResult results[OW_WILD_MAX_SPAWNS])\n{",
        )
        require(frame_body.count(
                    "for (i = 0; i < OW_WILD_MAX_SPAWNS; i++)") == 2
                and frame_body.index(validator)
                    < frame_body.index(
                        "OverworldWildRuntime_SetTimerPresentationGate(runtime, i,"),
                "multi-slot frame tick does not preflight every slot before writes")
    for token in (
        "OverworldWildBehavior_LoadValidatedBundle(",
        "OverworldWildBehavior_ReleaseValidatedBundle(",
        "OverworldWildBehavior_FreeValidatedBundle(",
        "OverworldWildRuntime_CopyInstalledDefinition(",
        "sOverworldWildValidatedV40",
        "CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA",
        "OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE",
        "compositionOut->baseProfileId = base->profileId;",
        "compositionOut->baseSemanticRole = base->semanticRole;",
        "CanonicalApplicabilityMatches(compositionOut, input)",
        "compositionOut->resolvedNodes",
        "OWBD_STATIC_ACTION_UNBIND_NODE",
        "StaticMatch(context, &candidate->match)",
        "ApplyStaticScalar(4, action, target->stateValues,",
        "StaticCompositionSetHash(compositionOut)",
    ):
        require(token in source, f"resident validated-bundle contract missing: {token}")
    require("InstallValidatedCatalog" not in source + implementation + header,
            "caller-installed copied definition catalog remains exposed")
    assignment = re.compile(
        r"(?:layerBank\.(?:entryGenerations|definitionIds|ownerIds|instanceKeys|"
        r"requiredOwnerIds|tiredOriginKinds|generatedFlags)\[[^]]+\]|"
        r"activeLayerCount)\s*=(?!=)"
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
        "caller-selected unrelated role replaced authenticated binding",
        "role 1 did not map to semantic-mask bit 0",
        "role 7 did not map to semantic-mask bit 6",
        "authored tired branch accepted the fallback wrapper",
        "duplicate absent owner selectors were accepted",
        "edited handle did not return INVALID_HANDLE",
        "capacity masked final multiplicity rejection",
        "terminal slot wrap inspected corrupt layers before direct restart",
        "handle minted between forced-zero binds remained authenticated",
        "production bodies 0x1202/0x1209 failed shared Task-5 domains",
        "released catalog returned cached data or IDEMPOTENT prime",
        "static-context generation change returned stale query/prime data",
        "global rekey reused data/empty-bystander cache incarnation",
        "candidate provenance published an incorrect isWinner flag",
        "static action order or static-before-runtime folding changed",
        "OverworldWildRuntime_ResolveRetainedStaticCache(\n",
        "false destructive wrapper changed runtime bytes",
        "ordinary live invalidation did not advance identity and clear Task-9 caches",
        "repeated live invalidation retained prior identity or Task-9 caches",
        "repeated live invalidation changed a bystander slot",
        "timer tick accepted valid-enum metadata drift or changed runtime",
        "finite timer extension was accepted or changed runtime",
        "finite-to-indefinite timer edit was accepted or changed runtime",
        "old-identity rekey expiry was not a mutation-free stale no-op",
        "old-identity restart expiry was not a mutation-free stale no-op",
        "structurally malformed stale expiry was not rejected atomically",
        "later invalid frame slot partially changed an earlier slot",
        "corrected frame retry did not decrement each slot exactly once",
        "altered nonzero current validity tag was not stale-safe",
        "indefinite timer below 255 was accepted or changed runtime",
        "TASK10_TIMER_CORRECTION_TRACE",
        "canonical context did not publish the exact installed binding",
        "stamina recovery was enabled without an authored tired binding",
        "imperative recovery did not select the authored semantic wrapper",
        "imperative recovery did not select the generated exact fallback",
        "Task11 fixture bytes differ from the generated v40 catalog",
        "generated v40 wrapper definition bytes drifted",
        "generated v40 recovery operation payload drifted",
        "malformed canonical applicability changed output or runtime",
        "semantic recovery ignored the freshly rebound tired profile",
        "exact recovery ignored the freshly rebound custom profile",
        "semantic translation profile mismatch changed output or runtime",
        "exact translation profile mismatch changed output or runtime",
        "invalid recovery selection changed caller or runtime bytes",
        "base command origin fabricated layer winner fields",
        "mutated V11 command identity changed captured state",
        "mutated V11 captured-origin tuple was consumed or changed",
        "consumed command origin was not an exact once-only result",
        "duplicate command completion changed the command bank or runtime",
        "canceled command origin remained consumable",
        "all-bank invalidation retained a command origin",
        "legacy calm recovery disturbed an unrelated layer or timer",
        "remove-self recovery removed a bystander layer or timer",
        "stale recovery ticket changed runtime bytes",
        "invalid catalog closure changed runtime or was accepted",
        "fixture_reseal_installed_catalog();",
        "fixture_swap_recovery_route_claims(",
        "route-swap fixture operation claims are not globally coherent",
        "fixture_mutate_semantic_tired_backlink(",
        "fixture_mutate_exact_tired_backlink(",
        "fixture_mutate_stamina_backlink(",
        "fixture_mutate_forced_sleep_backlink(",
        "authenticated post-install catalog",
        "fixture catalog CRC reseal diverged from generated bytes",
        "expiry ticket lost its exact generated wrapper identity",
        "semantic/exact generated wrapper recovery route diverged",
        "forced-sleep remove-self recovery disturbed its covering layer",
        "../data/OverworldWildBehaviorDataV40.generated.inc",
        "TASK11_SUBSTRATE_TRACE",
    ):
        require(token in fixture, f"review fixture is absent: {token}")
    for token in (
        "production retained resolver changed an independent valid copy",
        "production retained resolver accepted exact input/output aliasing",
        "production retained resolver accepted a mutated retained context",
        "production retained resolver accepted a mismatched generation",
    ):
        require(token in catalog_fixture,
                f"production retained-resolver fixture is absent: {token}")
    for token in (
        "production canonical static composition rejected NULL input",
        "production stamina trigger projection was not unique/exact",
        "production stamina identity-only timer projection differs",
    ):
        require(token in catalog_fixture,
                f"production catalog projection fixture is absent: {token}")
    actual_fixture_includes = (
        "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c",
        "../src/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.c",
    )
    projected_apis = (
        "OverworldWildRuntime_CopyInstalledStaticComposition",
        "OverworldWildRuntime_CountInstalledTiredTranslations",
        "OverworldWildRuntime_ResolveInstalledTimerDefinition",
    )

    def catalog_timer_ownership_matches(candidate: str) -> bool:
        for path in actual_fixture_includes:
            include_pattern = (
                rf'(?m)^[ \t]*#[ \t]*include[ \t]+"{re.escape(path)}"'
                r'[ \t]*$'
            )
            if len(re.findall(include_pattern, candidate)) != 1:
                return False
        code = re.sub(r"/\*.*?\*/|//[^\n]*", "", candidate,
                      flags=re.DOTALL)
        for path in actual_fixture_includes:
            code = re.sub(
                rf'(?m)^[ \t]*#[ \t]*include[ \t]+"{re.escape(path)}"'
                r'[ \t]*$', "", code)
        for api in projected_apis:
            if re.search(rf"(?m)^[ \t]*#[^\n]*\b{api}\b", code):
                return False
            declaration = (
                rf"(?ms)^[ \t]*(?:(?:extern|static|inline|const|volatile)"
                rf"[ \t]+)*(?:BOOL|u8|int|void)[ \t*]+{api}[ \t]*"
                r"\([^;{}]*\)[ \t\r\n]*(?:;|\{)"
            )
            split_definition = (
                rf"(?ms)^[ \t]*{api}[ \t]*\([^;{{}}]*\)"
                r"[ \t\r\n]*(?:;|\{)"
            )
            if (re.search(declaration, code)
                    or re.search(split_definition, code)):
                return False
        return True

    require(catalog_timer_ownership_matches(catalog_timer_fixture),
            "production catalog/timer fixture ownership is not structural")
    for path in actual_fixture_includes:
        include_line = f'#include "{path}"'
        comment_only = catalog_timer_fixture.replace(
            include_line, f'/* {include_line} */', 1)
        require(not catalog_timer_ownership_matches(comment_only),
                "comment-only production source path bypass was accepted")
    for api in projected_apis:
        for mutation in (
            f"\nBOOL {api}(void) {{ return FALSE; }}\n",
            f"\nextern BOOL {api}(void);\n",
            f"\n#define {api} FixtureReplacement\n",
            f"\n#define FixtureReplacement {api}\n",
        ):
            require(not catalog_timer_ownership_matches(
                        catalog_timer_fixture + mutation),
                    f"local replacement for {api} was accepted")
    for token in (
        "OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA",
        "actual overlay157-to-overlay159 stamina recovery differs",
        "actual overlay157-to-overlay159 semantic recovery differs",
    ):
        require(token in catalog_timer_fixture,
                f"production catalog/timer integration fixture is absent: {token}")


def run_host_fixture() -> str:
    compiler = shutil.which("cc") or shutil.which("clang")
    require(compiler is not None, "no host C compiler available")
    with tempfile.TemporaryDirectory(prefix="ow-runtime-layers-") as directory:
        binary = Path(directory) / "fixture"
        command = [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O2",
            str(FIXTURE),
            "-o",
            str(binary),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        completed = subprocess.run(
            [str(binary)], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        split_binary = Path(directory) / "split-fixture"
        split_command = command.copy()
        split_command.insert(-2, "-DOW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD")
        split_command[-1] = str(split_binary)
        subprocess.run(split_command, cwd=ROOT, check=True)
        split_completed = subprocess.run(
            [str(split_binary)], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        legacy_trace_prefixes = (
            "TASK6_", "TASK10_TIMER_TRACE", "TASK10_TIMER_CORRECTION_TRACE",
        )
        legacy_trace = tuple(
            line for line in completed.stdout.splitlines()
            if line.startswith(legacy_trace_prefixes)
        )
        split_legacy_trace = tuple(
            line for line in split_completed.stdout.splitlines()
            if line.startswith(legacy_trace_prefixes)
        )
        require(split_legacy_trace == legacy_trace,
                "overlay159 split fixture differs from monolithic Task6/Task10 semantics")
        require("TASK11_SUBSTRATE_TRACE" in split_completed.stdout,
                "overlay159 split fixture did not execute Task11 substrate coverage")
        completed = split_completed
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
            "-Wno-unused-function",
            "-O2",
            str(CATALOG_FIXTURE),
            "-o",
            str(binary),
        ], cwd=ROOT, check=True)
        completed = subprocess.run(
            [str(binary), str(VALIDATED_V40)], cwd=ROOT, check=True,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    expected_summary = (
        "runtime catalog host fixture: 193 checks; definitions=19 translations=18"
    )
    require(completed.stdout.strip() == expected_summary,
            "production catalog fixture summary changed: "
            f"{completed.stdout.strip()!r}")
    return completed.stdout.strip()


def run_catalog_timer_fixture() -> str:
    compiler = shutil.which("cc") or shutil.which("clang")
    require(compiler is not None, "no host C compiler available")
    with tempfile.TemporaryDirectory(
            prefix="ow-runtime-catalog-timer-") as directory:
        binary = Path(directory) / "fixture"
        command = [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-function",
            "-Wno-address-of-packed-member",
            "-O2",
            "-ffunction-sections",
            "-fdata-sections",
            str(CATALOG_TIMER_FIXTURE),
            "-Wl,-dead_strip" if sys.platform == "darwin"
                else "-Wl,--gc-sections",
            "-o",
            str(binary),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        completed = subprocess.run(
            [str(binary)], cwd=ROOT, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
    expected_summary = (
        "runtime catalog/timer host fixture: 14 checks; "
        "stamina=0x7004 semantic=0x7005 transition=0xA005"
    )
    require(completed.stdout.strip() == expected_summary,
            "production catalog/timer fixture summary changed: "
            f"{completed.stdout.strip()!r}")
    return completed.stdout.strip()


def main() -> None:
    verify_source_contracts()
    verify_make_package_invocation()
    fixture_summary = run_host_fixture()
    oracle_checks = verify_oracle_status_trace(fixture_summary)
    timer_oracle_checks = verify_timer_oracle_trace(fixture_summary)
    task11_checks = verify_task11_substrate_trace(fixture_summary)
    catalog_summary = run_catalog_fixture()
    catalog_timer_summary = run_catalog_timer_fixture()
    print(fixture_summary)
    print(catalog_summary)
    print(catalog_timer_summary)
    print(
        "runtime layer source verifier: closed tagged-union ABI, canonical fixed "
        f"scratch semantics, authenticated handles, {oracle_checks}-status "
        f"Task-6, {timer_oracle_checks}-field Task-10, and "
        f"{task11_checks}-field Task-11 oracle traces verified"
    )


if __name__ == "__main__":
    main()

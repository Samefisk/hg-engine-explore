#!/usr/bin/env python3
"""Pure fixtures for the bounded overworld runtime snapshot wrapper."""

from __future__ import annotations

import importlib.util
import re
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/headless_overworld_runtime_snapshot.py"
SPEC = importlib.util.spec_from_file_location("ow_runtime_snapshot", PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("cannot load runtime snapshot module")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def hex_value(data: bytes) -> str:
    return data.hex()


def layer_bank(layers: list[tuple[int, int, int, int]]) -> str:
    values = layers + [(0, 0, 0, 0)] * (MODULE.MAX_LAYERS - len(layers))
    data = bytearray(MODULE.LAYER_BANK_SIZE)
    struct.pack_into("<8I", data, 0, *(item[0] for item in values))
    struct.pack_into("<8H", data, 32, *(item[3] for item in values))
    struct.pack_into("<8H", data, 48, *(item[1] for item in values))
    struct.pack_into("<8H", data, 64, *(item[2] for item in values))
    return hex_value(data)


def timer_bank(timers: list[tuple[int, int, int, int, int]]) -> str:
    data = bytearray(MODULE.TIMER_BANK_SIZE)
    for index, (entry, generation, owner, instance, definition) in enumerate(timers):
        struct.pack_into(
            "<IIHHHHBBBBBB2x",
            data,
            index * 24,
            entry,
            generation,
            owner,
            instance,
            definition,
            7,
            3,
            4,
            1,
            1,
            1,
            MODULE.TIMER_VALID,
        )
    return hex_value(data)


def relations(carried_slot: int | None = None, generation: int = 3) -> str:
    data = bytearray(MODULE.PICKUP_RELATION_SIZE * MODULE.MAX_SLOTS)
    if carried_slot is not None:
        offset = carried_slot * MODULE.PICKUP_RELATION_SIZE
        struct.pack_into("<IIIIHHB3x", data, offset, 9, generation, 5, 6, 104, 2, carried_slot)
        struct.pack_into("<IIII", data, offset + 24, 8, 8, 4, 12)
        struct.pack_into("<BBBB", data, offset + 40, 2, 1, 0, 0)
    return hex_value(data)


def result_fixture(*, bad_timer: bool = False, carried: bool = False) -> dict:
    reads = [
        {"label": "runtime_pointer_confirm", "value": 0x2340000},
        {"label": "map_id", "value": 1},
        {"label": "map_generation", "value": 2},
        {"label": "movement_in_progress", "value": 0},
        {"label": "active_steps", "value": bytes(10).hex()},
        {"label": "presentation_positions", "value": bytes(40).hex()},
        {"label": "movement_object_generations", "value": bytes(40).hex()},
        {"label": "runtime_epoch", "value": 9},
        {"label": "data_incarnation", "value": 4},
        {"label": "lifetime_state", "value": 1},
        {"label": "pickup_relations", "value": relations(0 if carried else None)},
    ]
    for index in range(MODULE.MAX_SLOTS):
        assigned = index == 0
        layers = [(5, 104, 2, 77)] if assigned else []
        timers = [(6 if bad_timer else 5, 11, 104, 2, 77)] if assigned else []
        reads.extend(
            (
                {"label": f"slot{index}_generation", "value": 3 if assigned else 0},
                {"label": f"slot{index}_layer_count", "value": len(layers)},
                {"label": f"slot{index}_lifecycle", "value": 1 if assigned else 0},
                {"label": f"slot{index}_presentation_gate", "value": 0},
                {"label": f"slot{index}_role", "value": 5 if carried and assigned else (1 if assigned else 0)},
                {"label": f"slot{index}_layers", "value": layer_bank(layers)},
                {"label": f"slot{index}_timers", "value": timer_bank(timers)},
            )
        )
    return {"reads": reads, "heap_margin": {"passed": True}}


def layout_contract(source: str) -> dict[str, int]:
    return {
        name: int(value, 0)
        for name, value in re.findall(
            r"^#define (OW_WILD_SNAPSHOT_[A-Z_]+_OFFSET) "
            r"(0x[0-9A-Fa-f]+|[0-9]+)$",
            source,
            re.MULTILINE,
        )
    }


def require_current_layout_contract(source: str) -> None:
    require(
        layout_contract(source)
        == {
            "OW_WILD_SNAPSHOT_PRESENTATION_POSITIONS_OFFSET": (
                MODULE.LIVE_PRESENTATION_POSITIONS_OFFSET
            ),
            "OW_WILD_SNAPSHOT_MOVEMENT_OBJECT_GENERATIONS_OFFSET": (
                MODULE.LIVE_MOVEMENT_OBJECT_GENERATIONS_OFFSET
            ),
            "OW_WILD_SNAPSHOT_PICKUP_RELATIONS_OFFSET": (
                MODULE.PICKUP_RELATIONS_OFFSET
            ),
            "OW_WILD_SNAPSHOT_BEHAVIOR_STACK_OFFSET": MODULE.LIVE_STACK_OFFSET,
            "OW_WILD_SNAPSHOT_SLOT_EFFECTIVE_CACHE_OFFSET": (
                MODULE.SLOT_EFFECTIVE_CACHE_OFFSET
            ),
            "OW_WILD_SNAPSHOT_EFFECTIVE_ROLE_OFFSET": MODULE.EFFECTIVE_ROLE_OFFSET,
        },
        "snapshot decoder offsets differ from the live overlay contract",
    )


def main() -> int:
    checks = 0
    source = (
        ROOT
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
    ).read_text()
    require_current_layout_contract(source)
    checks += 1
    try:
        require_current_layout_contract(
            source.replace(
                "#define OW_WILD_SNAPSHOT_BEHAVIOR_STACK_OFFSET 0x804",
                "#define OW_WILD_SNAPSHOT_BEHAVIOR_STACK_OFFSET 0x808",
            )
        )
    except AssertionError:
        checks += 1
    else:
        raise AssertionError("mutated enclosing runtime offset was accepted")
    require(
        source.count("#define OW_WILD_SNAPSHOT_BEHAVIOR_STACK_OFFSET 0x804")
        == 1,
        "layout mutation fixture did not target exactly one source definition",
    )
    checks += 1
    for scenario in MODULE.SCENARIOS.values():
        frames = MODULE.validate_actions(scenario.actions, scenario.frame_budget)
        require(0 < frames <= scenario.frame_budget, f"{scenario.name} budget differs")
        checks += 1
    try:
        MODULE.validate_actions(("wait:7201",), 7200)
    except ValueError:
        checks += 1
    else:
        raise AssertionError("over-budget action was accepted")

    specs = MODULE.read_specs(0x1000)
    require(len(specs) == 81, "read inventory differs")
    require(any("pickup_relations:bytes440" in item for item in specs), "possession read missing")
    require(any(item.count(":") == 3 for item in specs), "pointer-relative reads missing")
    checks += 3

    arm9 = b"arm9-image"
    linked129 = b"resident-linked"
    linked149 = b"spawns-linked"
    overlay129 = bytearray(0x8000)
    overlay129[0x600 : 0x600 + len(linked129)] = linked129
    rows = {
        129: ((129, 0x023D8000, len(overlay129), 0, 0, 0, 129, 0), bytes(overlay129)),
        149: ((149, 0x023CD000, len(linked149), 0, 0, 0, 149, 0), linked149),
    }
    identity = MODULE.verify_component_identity(
        packaged_arm9=(0x02000000, arm9),
        overlays=rows,
        built_arm9=arm9 + b"pad",
        linked129_image=linked129,
        linked149_image=linked149,
        linked129_text_start=0x023D8600,
        linked149_text_start=0x023CD000,
        state_address=0x023DF938,
        state_size=MODULE.STATE_SIZE,
    )
    require(identity["linked_overlay149_sha256"] == identity["packaged_overlay149_sha256"], "identity digest differs")
    checks += 1
    bad_rows = dict(rows)
    bad_rows[149] = (rows[149][0], b"X" + linked149[1:])
    try:
        MODULE.verify_component_identity(
            packaged_arm9=(0x02000000, arm9), overlays=bad_rows,
            built_arm9=arm9 + b"pad", linked129_image=linked129,
            linked149_image=linked149, linked129_text_start=0x023D8600,
            linked149_text_start=0x023CD000, state_address=0x023DF938,
            state_size=MODULE.STATE_SIZE,
        )
    except ValueError:
        checks += 1
    else:
        raise AssertionError("mismatched packaged overlay was accepted")

    parsed = MODULE.snapshot_from_result(result_fixture(carried=True))
    issues = MODULE.evaluate_snapshot(
        parsed,
        dsv_unchanged=True,
        rom_unchanged=True,
    )
    require(not issues, f"valid snapshot rejected: {issues}")
    checks += 1

    timer = parsed["slots"][0]["timers"][0]
    require(
        timer["instance_key"] == 2,
        "timer instance key was decoded from the wrong field",
    )
    require(timer["flags"] == MODULE.TIMER_VALID, "timer flags were not decoded")
    checks += 2

    bad = MODULE.snapshot_from_result(result_fixture(bad_timer=True))
    issues = MODULE.evaluate_snapshot(
        bad,
        dsv_unchanged=True,
        rom_unchanged=True,
    )
    require(any("timer has no exact owning layer" in issue for issue in issues), "orphan timer accepted")
    checks += 1

    parsed["pickup_relations"][0]["slot_generation"] = 2
    issues = MODULE.evaluate_snapshot(
        parsed,
        dsv_unchanged=False,
        rom_unchanged=True,
    )
    require(any("current handle" in issue for issue in issues), "stale possession accepted")
    require(any("test.dsv changed" in issue for issue in issues), "save mutation accepted")
    checks += 2

    for field, value in (("runtime_epoch", 8), ("slot_index", 1), ("entry_generation", 6)):
        current = MODULE.snapshot_from_result(result_fixture(carried=True))
        current["pickup_relations"][0][field] = value
        issues = MODULE.evaluate_snapshot(current, dsv_unchanged=True, rom_unchanged=True)
        require(any("current handle" in issue for issue in issues), f"bad {field} accepted")
        checks += 1

    valid_zero = MODULE.snapshot_from_result(result_fixture())
    valid_zero["slots"][0]["timers"][0]["timer_generation"] = 0
    issues = MODULE.evaluate_snapshot(valid_zero, dsv_unchanged=True, rom_unchanged=True)
    require(any("valid timer has generation zero" in issue for issue in issues), "VALID timer with zero generation accepted")
    checks += 1

    static_timeline = [MODULE.snapshot_from_result(result_fixture()) for _ in range(8)]
    for item in static_timeline:
        item["keys_held"] = True
    require(any("rolling gameplay progress" in issue for issue in MODULE.scenario_evidence("spawn-freeze", static_timeline)), "static scenario accepted")
    checks += 1

    early_only = [MODULE.snapshot_from_result(result_fixture()) for _ in range(8)]
    for index, item in enumerate(early_only):
        item["keys_held"] = True
        item["active_steps"][0] = min(index, 2)
    require(
        any(
            "rolling gameplay progress" in issue
            for issue in MODULE.scenario_evidence("spawn-freeze", early_only)
        ),
        "early progress with a static tail was accepted",
    )
    checks += 1

    slot_only = [MODULE.snapshot_from_result(result_fixture()) for _ in range(8)]
    for index, item in enumerate(slot_only):
        item["keys_held"] = True
        item["active_steps"][0] = index
        if index >= 4:
            item["slots"][0]["generation"] = 4
    require(
        any(
            "no map/battle boundary" in issue
            for issue in MODULE.scenario_evidence("lifecycle", slot_only)
        ),
        "ordinary slot generation replacement counted as a lifecycle boundary",
    )
    checks += 1

    replaced_target = []
    for index in range(8):
        item = MODULE.snapshot_from_result(result_fixture(carried=index < 4))
        item["keys_held"] = True
        item["active_steps"][0] = index
        carrier = item["slots"][1]
        carrier["generation"] = 7
        carrier["lifecycle"] = 1
        carrier["role"] = 1
        carrier["layer_count"] = 1
        carrier["layers"][0].update(
            entry_generation=12, owner_id=105, instance_key=1, definition_id=78
        )
        if index >= 4:
            item["slots"][0]["generation"] = 4
            item["slots"][0]["role"] = 1
        replaced_target.append(item)
    require(
        any(
            "same target generation" in issue
            for issue in MODULE.scenario_evidence("pickup-throw", replaced_target)
        ),
        "target despawn/reassignment counted as possession reveal",
    )
    checks += 1

    print(f"headless runtime snapshot fixtures: {checks} checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

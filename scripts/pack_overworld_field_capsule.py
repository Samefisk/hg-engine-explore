#!/usr/bin/env python3
"""Retain fully linked private role helpers in the stock Field code capsule."""

import argparse
import hashlib
from pathlib import Path
import struct
import subprocess
import tempfile

if __package__:
    from .pack_overworld_combat_capsules import section_bytes
    from .verify_pokemon_move_history_capture import elf_helper_bindings, packaged_thumb_calls
else:
    from pack_overworld_combat_capsules import section_bytes
    from verify_pokemon_move_history_capture import elf_helper_bindings, packaged_thumb_calls


REST_POLICY_ADDRESS, REST_POLICY_SIZE = 0x023B8E50, 500
# The boot Actor copy slot ends at the fixed Pickup cancel entry (0x023B9048).
REST_POLICY_SLOT_SIZE = 0x1F8
REST_POLICY_SECTION = ".overworld_appearance_rest_policy"
REST_POLICY_SOURCE = "OverworldAppearancePolicy_ShouldRestTint"
REST_POLICY_COPY = "OverworldActorPrivateRestTint"
REST_POLICY_SHA256 = "b965152ad5efa78e3c87d8d110a7bdb44469cf4433327ac7857667cac8add538"
REST_APPLICABLE_ADDRESS, REST_APPLICABLE_SIZE = 0x022088EA, 22


def rest_policy_contract(hosted, applicable, body):
    if (hosted is None or hosted[:3] !=
            (REST_POLICY_ADDRESS | 1, REST_POLICY_SIZE, "FUNC")
            or hosted[3] in ("ABS", "UND")
            or applicable is None or applicable[:3] !=
            (REST_APPLICABLE_ADDRESS | 1, REST_APPLICABLE_SIZE, "FUNC")
            or applicable[3] in ("ABS", "UND")):
        raise ValueError("Field Rest tint policy owner, Thumb mode or extent differs")
    if (len(body) != REST_POLICY_SIZE
            or hashlib.sha256(body).hexdigest() != REST_POLICY_SHA256):
        raise ValueError("Field Rest tint policy body differs")
    calls = packaged_thumb_calls(body, REST_POLICY_ADDRESS,
                                 REST_POLICY_ADDRESS, REST_POLICY_SIZE)
    if calls != [(REST_POLICY_ADDRESS + 0x106, "bl", REST_APPLICABLE_ADDRESS)]:
        raise ValueError("Field Rest tint policy lost its sole exact Field role read")


def rest_policy_body(build):
    owner = build / "overworld_field_capsule_linked.o"
    symbols = elf_helper_bindings(owner, (REST_POLICY_SOURCE,
        "OverworldAppearancePolicy_ApplicableMask"))
    body = section_bytes(owner, REST_POLICY_SECTION, REST_POLICY_ADDRESS,
                         REST_POLICY_SIZE)
    rest_policy_contract(symbols.get(REST_POLICY_SOURCE),
        symbols.get("OverworldAppearancePolicy_ApplicableMask"), body)
    return body


def pack_rest_policy(build, assembler):
    """Copy one fully linked pure Field read into existing boot Actor filler."""
    body = rest_policy_body(build)
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        binary = temp / "overworld_actor_rest_tint.bin"
        binary.write_bytes(body)
        assembly = temp / "overworld_actor_rest_tint.s"
        assembly.write_text('.syntax unified\n.thumb\n.section '
            + REST_POLICY_SECTION + ',"ax",%progbits\n.balign 4\n.global '
            + REST_POLICY_COPY + '\n.type ' + REST_POLICY_COPY
            + ',%function\n.thumb_func\n' + REST_POLICY_COPY
            + ':\n.incbin "overworld_actor_rest_tint.bin"\n.size '
            + REST_POLICY_COPY + ',.-' + REST_POLICY_COPY + '\n'
            # Keep the following private Pickup entry at its existing address.
            + '.space %d,0\n' % (REST_POLICY_SLOT_SIZE - REST_POLICY_SIZE))
        wrapper = temp / "overworld_actor_rest_tint.o"
        subprocess.run([assembler, "-mthumb", "-mcpu=arm7tdmi", "-march=armv4t",
            assembly.name, "-o", wrapper.name], cwd=temp, check=True)
        binary.replace(build / binary.name)
        wrapper.replace(build / wrapper.name)


def pack_appearance_release(build):
    """Copy one linked Field leaf into its reserved HP padding after both links.

    Field output depends on the already-built HP binary. No HP object/link
    depends on Field. Only this packaging step replaces the reserved bytes.
    """
    health = build / "output_player_health_overlay.bin"
    baseline = section_bytes(build / "player_health_overlay_linked.o",
                             ".text", 0x01FFA580, 0x5A80)
    begin, end = 0x01FFD250 - 0x01FFA580, 0x01FFD2CC - 0x01FFA580
    if baseline[begin:end] != b"\xff" * (end - begin):
        raise ValueError("appearance release gap overlaps linked HP code/state")
    current = health.read_bytes()
    if (len(current) != len(baseline) or current[:begin] != baseline[:begin]
            or current[end:] != baseline[end:]):
        raise ValueError("appearance release HP payload differs outside its gap")
    release = section_bytes(build / "overworld_field_capsule_linked.o",
                            ".overworld_appearance_release", 0x01FFD250, end - begin)
    combined = baseline[:begin] + release + baseline[end:]
    # Keep already-correct inputs' mtime unchanged on an incremental build.
    if combined != current:
        with tempfile.NamedTemporaryFile(dir=build, prefix="appearance-release-",
                                         delete=False) as output:
            output.write(combined)
            temporary = Path(output.name)
        temporary.replace(health)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--objcopy", default="arm-none-eabi-objcopy")
    parser.add_argument("--as", dest="assembler", default="arm-none-eabi-as")
    parser.add_argument("--rest-policy-only", action="store_true",
                        help="copy the pure Field Rest tint read into boot Actor filler")
    parser.add_argument("--cargo-only", action="store_true",
                        help="pack only the private Field131 Cargo observation")
    parser.add_argument("--appearance-release-only", action="store_true",
                        help="retain the private Field release leaf in HP padding")
    args = parser.parse_args()
    build = args.build_dir.resolve()
    if args.rest_policy_only:
        if args.cargo_only or args.appearance_release_only:
            parser.error("Rest tint policy and other capsule modes are separate")
        pack_rest_policy(build, args.assembler)
        return
    if args.appearance_release_only:
        if args.cargo_only:
            parser.error("appearance release and cargo modes are separate")
        pack_appearance_release(build)
        return
    if args.cargo_only:
        payload = section_bytes(build / "overworld_wild_spawns_overlay_linked.o",
            ".overworld_field_wild_cargo_observation", 0x023CCDC8, 0xD0)
        with tempfile.TemporaryDirectory(dir=build) as temporary:
            temp = Path(temporary)
            binary = temp / "overworld_field_cargo_observation.bin"
            binary.write_bytes(payload)
            wrapper = temp / "overworld_field_cargo_observation.o"
            subprocess.run([args.objcopy, "-I", "binary", "-O", "elf32-littlearm",
                "-B", "arm", "--rename-section",
                ".data=.overworld_field_wild_cargo_observation,alloc,load,readonly,code,contents",
                str(binary), str(wrapper)], check=True)
            image = bytearray(wrapper.read_bytes())
            struct.pack_into("<I", image, 36, 0x05000000)
            wrapper.write_bytes(image)
            binary.replace(build / binary.name)
            wrapper.replace(build / wrapper.name)
        return
    # Condition subject leaves now link in the retired FindActor reserve.
    # Retain private Wild and player helpers at their fully linked addresses.
    payload = section_bytes(
        build / "pokemon_move_history_overlay_linked.o",
        ".overworld_field_spawn_orphans", 0x02208360, 0x58)
    mount_hop_tick = section_bytes(
        build / "overworld_mount_overlay_linked.o",
        ".overworld_field_mount_hop_tick", 0x022083B8, 0x48)
    wild = section_bytes(
        build / "overworld_wild_spawns_overlay_linked.o",
        ".overworld_field_wild_walk_output", 0x02208400, 0x100)
    route_base_y = section_bytes(
        build / "overworld_wild_spawns_overlay_linked.o",
        ".overworld_field_wild_route_base_y", 0x022081E0, 0x20)
    hop_support = section_bytes(
        build / "overworld_wild_spawns_overlay_linked.o",
        ".overworld_field_wild_hop_support", 0x0220833C, 0x24)
    tuning = section_bytes(
        build / "player_health_overlay_linked.o",
        ".overworld_field_walk_input_tuning", 0x02208500, 0xD0)
    tuning += section_bytes(
        build / "overworld_wild_spawns_overlay_linked.o",
        ".overworld_field_wild_policy_init", 0x022085D0, 0x30)
    tuning += section_bytes(
        build / "overworld_follower_selector_overlay_linked.o",
        ".overworld_throw_binding_refresh", 0x02208600, 0x100)
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        (temp / "overworld_field_condition.bin").write_bytes(payload)
        (temp / "overworld_field_wild_walk.bin").write_bytes(wild)
        (temp / "overworld_field_wild_route_base_y.bin").write_bytes(route_base_y)
        (temp / "overworld_field_wild_hop_support.bin").write_bytes(hop_support)
        (temp / "overworld_field_mount_hop_tick.bin").write_bytes(mount_hop_tick)
        (temp / "overworld_field_walk_input_tuning.bin").write_bytes(tuning)
        subprocess.run([
            args.objcopy, "-I", "binary", "-O", "elf32-littlearm", "-B", "arm",
            "--rename-section",
            ".data=.overworld_field_spawn_orphans,alloc,load,readonly,code,contents",
            "--add-section", ".overworld_field_wild_walk_output=overworld_field_wild_walk.bin",
            "--set-section-flags",
            ".overworld_field_wild_walk_output=alloc,load,readonly,code,contents",
            "--add-section", ".overworld_field_wild_route_base_y=overworld_field_wild_route_base_y.bin",
            "--set-section-flags",
            ".overworld_field_wild_route_base_y=alloc,load,readonly,code,contents",
            "--add-section", ".overworld_field_wild_hop_support=overworld_field_wild_hop_support.bin",
            "--set-section-flags",
            ".overworld_field_wild_hop_support=alloc,load,readonly,code,contents",
            "--add-section", ".overworld_field_mount_hop_tick=overworld_field_mount_hop_tick.bin",
            "--set-section-flags",
            ".overworld_field_mount_hop_tick=alloc,load,readonly,code,contents",
            "--add-section", ".overworld_field_walk_input_tuning=overworld_field_walk_input_tuning.bin",
            "--set-section-flags",
            ".overworld_field_walk_input_tuning=alloc,load,readonly,code,contents",
            "overworld_field_condition.bin", "overworld_field_condition.o",
        ], cwd=temp, check=True)
        wrapper = temp / "overworld_field_condition.o"
        image = bytearray(wrapper.read_bytes())
        struct.pack_into("<I", image, 36, 0x05000000)
        wrapper.write_bytes(image)
        (temp / "overworld_field_condition.bin").replace(
            build / "overworld_field_condition.bin")
        (temp / "overworld_field_wild_walk.bin").replace(
            build / "overworld_field_wild_walk.bin")
        (temp / "overworld_field_wild_route_base_y.bin").replace(
            build / "overworld_field_wild_route_base_y.bin")
        (temp / "overworld_field_wild_hop_support.bin").replace(
            build / "overworld_field_wild_hop_support.bin")
        (temp / "overworld_field_mount_hop_tick.bin").replace(
            build / "overworld_field_mount_hop_tick.bin")
        (temp / "overworld_field_walk_input_tuning.bin").replace(
            build / "overworld_field_walk_input_tuning.bin")
        wrapper.replace(build / "overworld_field_condition.o")


if __name__ == "__main__":
    main()

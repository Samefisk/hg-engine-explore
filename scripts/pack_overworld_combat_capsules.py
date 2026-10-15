#!/usr/bin/env python3
"""Pack fully linked role adapters into the boot-resident combat reservation."""

import argparse
from pathlib import Path
import struct
import subprocess
import tempfile


CAPSULES = (
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_combat",
     0x01FFF580, 0x180),
    ("overworld_mount_overlay_linked.o", ".overworld_mount_combat_tail",
     0x01FFF700, 0x100),
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_carrier_hit",
     0x01FFF800, 0x180),
    ("overworld_mount_overlay_linked.o", ".overworld_mount_combat",
     0x01FFF980, 0x200),
)
HIT_ADAPTERS = (
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_teleport_read",
     0x01FFEF54, 0xAC),
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_combat_tail",
     0x01FFFB80, 0x3A0),
)
CLEANUP_ADAPTERS = (
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_cleanup_task",
     0x01FFC124, 0x3C),
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_cleanup_hop_request",
     0x01FFEEFC, 0x58),
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_cleanup_progress",
     0x01FFF318, 0x28),
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_cleanup_spawn",
     0x01FFF3D4, 0x2C),
    ("overworld_wild_spawns_overlay_linked.o", ".overworld_wild_cleanup_presentation",
     0x01FFF432, 0x4E),
)


def section_bytes(linked, name, address, capacity):
    data = linked.read_bytes()
    if data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError(f"{linked.name}: expected little-endian ELF32")
    if struct.unpack_from("<HH", data, 16) != (2, 40):
        raise ValueError(f"{linked.name}: expected fully linked ARM executable")
    offset = struct.unpack_from("<I", data, 32)[0]
    stride, count, names_index = struct.unpack_from("<HHH", data, 46)
    if stride != 40 or names_index >= count:
        raise ValueError(f"{linked.name}: invalid section table")
    sections = [struct.unpack_from("<10I", data, offset + i * stride)
                for i in range(count)]
    names = sections[names_index]
    strings = data[names[4]:names[4] + names[5]]
    for section in sections:
        end = strings.find(b"\0", section[0])
        if strings[section[0]:end].decode() != name:
            continue
        if (section[1] != 1 or section[2] & 6 != 6
                or section[3] != address or not 0 < section[5] <= capacity):
            raise ValueError(f"{linked.name}: capsule address, flags or size differ")
        payload = data[section[4]:section[4] + section[5]]
        if len(payload) != section[5]:
            raise ValueError(f"{linked.name}: truncated capsule")
        return payload + bytes(capacity - len(payload))
    raise ValueError(f"{linked.name}: missing {name}")


def pack_throw_height(build, objcopy):
    """Retain one fully linked Wild getter in the existing Helper151 filler.

    Only the wrapper depends on Wild's ELF. Wild never depends on the helper
    ELF, so fully linked native calls are copied without a link cycle.
    """
    payload = section_bytes(build / "overworld_wild_spawns_overlay_linked.o",
                            ".overworld_wild_throw_height", 0x023C7D34, 0xC4)
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        binary = temp / "overworld_throw_height.bin"
        wrapper = temp / "overworld_throw_height.o"
        binary.write_bytes(payload)
        subprocess.run([objcopy, "-I", "binary", "-O", "elf32-littlearm",
            "-B", "arm", "--rename-section",
            ".data=.overworld_wild_throw_height,alloc,load,readonly,code,contents",
            str(binary), str(wrapper)], check=True)
        image = bytearray(wrapper.read_bytes())
        struct.pack_into("<I", image, 36, 0x05000000)
        wrapper.write_bytes(image)
        binary.replace(build / binary.name)
        wrapper.replace(build / wrapper.name)


def pack_notice_callers(build, objcopy):
    """Retain fully linked private Wild leaves in existing Selector152 filler.

    Wild links the real calls once. The Selector wrapper depends on Wild,
    while Wild imports no Selector ELF. No RAM or overlay file extent changes.
    """
    payload = section_bytes(build / "overworld_wild_spawns_overlay_linked.o",
                            ".overworld_wild_notice_callers", 0x023C2C1C, 0x164)
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        binary = temp / "overworld_notice_callers.bin"
        wrapper = temp / "overworld_notice_callers.o"
        binary.write_bytes(payload)
        subprocess.run([objcopy, "-I", "binary", "-O", "elf32-littlearm",
            "-B", "arm", "--rename-section",
            ".data=.overworld_wild_notice_callers,alloc,load,readonly,code,contents",
            str(binary), str(wrapper)], check=True)
        image = bytearray(wrapper.read_bytes())
        struct.pack_into("<I", image, 36, 0x05000000)
        wrapper.write_bytes(image)
        binary.replace(build / binary.name)
        wrapper.replace(build / wrapper.name)


def pack_mount_leaves(build, objcopy):
    """Copy already-linked Mount leaves into existing boot Action/Chain filler."""
    owner = build / "overworld_mount_overlay_linked.o"
    idle = section_bytes(owner, ".overworld_mount_private_terrain_idle", 0x01FF9770, 0x10)
    inspect = section_bytes(owner, ".overworld_mount_private_inspect", 0x01FFA4E0, 0xC)
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        binary = temp / "overworld_mount_private_leaves.bin"
        binary.write_bytes(idle)
        second = temp / "overworld_mount_private_inspect.bin"
        second.write_bytes(inspect)
        wrapper = temp / "overworld_mount_private_leaves.o"
        subprocess.run([objcopy, "-I", "binary", "-O", "elf32-littlearm", "-B", "arm",
            "--rename-section", ".data=.overworld_mount_private_terrain_idle,alloc,load,readonly,code,contents",
            "--add-section", ".overworld_mount_private_inspect=" + str(second),
            "--set-section-flags", ".overworld_mount_private_inspect=alloc,load,readonly,code,contents",
            str(binary), str(wrapper)], check=True)
        image = bytearray(wrapper.read_bytes())
        struct.pack_into("<I", image, 36, 0x05000000)
        wrapper.write_bytes(image)
        binary.replace(build / binary.name)
        second.replace(build / second.name)
        wrapper.replace(build / wrapper.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--objcopy", default="arm-none-eabi-objcopy")
    parser.add_argument("--throw-height-only", action="store_true",
                        help="pack the private Helper151 Throw-height getter")
    parser.add_argument("--notice-callers-only", action="store_true",
                        help="pack private Wild callers in Selector152 filler")
    parser.add_argument("--mount-leaves-only", action="store_true",
                        help="pack private Mount leaves in Action/Chain filler")
    args = parser.parse_args()
    build = args.build_dir.resolve()
    if args.mount_leaves_only:
        pack_mount_leaves(build, args.objcopy)
        return
    if args.notice_callers_only:
        pack_notice_callers(build, args.objcopy)
        return
    if args.throw_height_only:
        pack_throw_height(build, args.objcopy)
        return
    fragments = [section_bytes(build / linked, name, address, capacity)
                 for linked, name, address, capacity in CAPSULES]
    # The carrier leaf fills only the former empty capsule. All existing
    # Wild/Mount entries and the total resident reservation stay fixed.
    payload = b"".join(fragments)
    if len(payload) != 0x600:
        raise ValueError("combat capsule reservation changed")
    # Keep the input basename stable, so binary-generated symbols are stable.
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        (temp / "overworld_combat_capsules.bin").write_bytes(payload)
        command = [
            args.objcopy, "-I", "binary", "-O", "elf32-littlearm", "-B", "arm",
            "--rename-section",
            ".data=.overworld_combat_capsules,alloc,load,readonly,code,contents",
        ]
        for linked, name, address, capacity in HIT_ADAPTERS + CLEANUP_ADAPTERS:
            adapter = temp / (name[1:] + ".bin")
            adapter.write_bytes(section_bytes(build / linked, name, address, capacity))
            command.extend([
                "--add-section", name + "=" + str(adapter),
                "--set-section-flags", name + "=alloc,load,readonly,code,contents",
            ])
        command.extend(["overworld_combat_capsules.bin", "overworld_combat_capsules.o"])
        subprocess.run(command, cwd=temp, check=True)
        # Binary inputs have no ABI metadata. These bytes are already linked
        # ARM EABI5 code; mark the wrapper to match the owning executables.
        wrapper = temp / "overworld_combat_capsules.o"
        object_data = bytearray(wrapper.read_bytes())
        struct.pack_into("<I", object_data, 36, 0x05000000)
        wrapper.write_bytes(object_data)
        (temp / "overworld_combat_capsules.bin").replace(
            build / "overworld_combat_capsules.bin")
        (temp / "overworld_combat_capsules.o").replace(
            build / "overworld_combat_capsules.o")


if __name__ == "__main__":
    main()

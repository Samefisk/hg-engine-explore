#!/usr/bin/env python3
"""Copy authenticated Wild Hop and pickup handoff leaves into the Actor front."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile
if __package__:
    from .pack_overworld_combat_capsules import section_bytes
    from .verify_pokemon_move_history_capture import elf_bytes_at, elf_helper_bindings
else:
    from pack_overworld_combat_capsules import section_bytes
    from verify_pokemon_move_history_capture import elf_bytes_at, elf_helper_bindings
ADDRESS, SIZE = 0x023B8800, 1616
SECTION = ".overworld_actor_slam_jump"
SOURCE = "OverworldWildSpawns_StartPreparedCustomJumpCommandWithArc"
COPY = "OverworldActorPrivateSlamJump"
BODY_SHA256 = "802e4d3b3e754f991045bbfb9d86d0838167b5aad69f68fcae4fc88a35a951dc"
DRIVER = "OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand"
DRIVER_ADDRESS, DRIVER_SIZE = 0x023D6334, 2698
DRIVER_SHA256 = "11c6e0643b1634b9c8e280c27498f9955876c53b79f43f0f1a4523f8ef09a8a9"
PICKUP_ADDRESS, PICKUP_SIZE = 0x023B9048, 200
PICKUP_SECTION = ".overworld_actor_pickup_cancel"
PICKUP_SOURCE = "OverworldWildSpawns_CancelCargoMotionForPickup"
PICKUP_COPY = "OverworldActorPrivatePickupCancel"
PICKUP_SHA256 = "643a83f80ba378034db68f6b372ff8fc37f20ccd9ee64d8a2831b7ebe5c6b9f6"

def _hosted(binding, address, size, owner="Slam body/driver"):
    if (binding is None or binding[:3] != (address | 1, size, "FUNC")
            or binding[3] in ("ABS", "UND")):
        raise ValueError(f"private {owner} owner, Thumb mode or extent differs")

def source_body(wild):
    symbols = elf_helper_bindings(wild, (SOURCE, DRIVER, "OverworldConditionSubject_HandleEquals"))
    _hosted(symbols.get(SOURCE), ADDRESS, SIZE)
    _hosted(symbols.get(DRIVER), DRIVER_ADDRESS, DRIVER_SIZE)
    if symbols.get("OverworldConditionSubject_HandleEquals") != (0x02208321, 0, "FUNC", "ABS"):
        raise ValueError("Slam source capture lost the exact typed Field identity import")
    body = section_bytes(wild, SECTION, ADDRESS, SIZE)
    if hashlib.sha256(body).hexdigest() != BODY_SHA256:
        raise ValueError("shared Hop admission body differs")
    driver = elf_bytes_at(wild, DRIVER_ADDRESS, DRIVER_SIZE)
    if hashlib.sha256(driver).hexdigest() != DRIVER_SHA256:
        raise ValueError("Slam source/winning Arc/current full target driver differs")
    return body

def source_pickup_body(wild):
    binding = elf_helper_bindings(wild, (PICKUP_SOURCE,)).get(PICKUP_SOURCE)
    _hosted(binding, PICKUP_ADDRESS, PICKUP_SIZE, "Wild pickup cancel")
    body = section_bytes(wild, PICKUP_SECTION, PICKUP_ADDRESS, PICKUP_SIZE)
    if len(body) != PICKUP_SIZE or hashlib.sha256(body).hexdigest() != PICKUP_SHA256:
        raise ValueError("Wild pickup cancel body differs")
    return body

def pack(build, assembler):
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    leaves = ((SECTION, COPY, "overworld_actor_slam_jump.bin", source_body(wild)),
              (PICKUP_SECTION, PICKUP_COPY, "overworld_actor_pickup_cancel.bin",
               source_pickup_body(wild)))
    with tempfile.TemporaryDirectory(dir=build) as temporary:
        temp = Path(temporary)
        for _, _, name, body in leaves:
            (temp / name).write_bytes(body)
        assembly = temp / "overworld_actor_slam_jump.s"
        assembly.write_text('.syntax unified\n.thumb\n' + ''.join(
            '.section '+section+',"ax",%progbits\n.balign 4\n.global '+copy+'\n'
            '.type '+copy+',%function\n.thumb_func\n'+copy+':\n.incbin "'+name+'"\n'
            '.size '+copy+',.-'+copy+'\n' for section, copy, name, _ in leaves))
        wrapper = temp / "overworld_actor_slam_jump.o"
        subprocess.run([assembler, "-mthumb", "-mcpu=arm7tdmi", "-march=armv4t",
            assembly.name, "-o", wrapper.name], cwd=temp, check=True)
        for _, _, name, _ in leaves:
            (temp / name).replace(build / name)
        wrapper.replace(build / wrapper.name)

def verify_shared_slam_jump(build, overlays, overlay_span):
    wild = build / "overworld_wild_spawns_overlay_linked.o"
    actor = build / "overworld_actor_system_overlay_linked.o"
    for address, size, copy, body in (
            (ADDRESS, SIZE, COPY, source_body(wild)),
            (PICKUP_ADDRESS, PICKUP_SIZE, PICKUP_COPY, source_pickup_body(wild))):
        _hosted(elf_helper_bindings(actor, (copy,)).get(copy), address, size, copy)
        if (elf_bytes_at(actor, address, size) != body
                or overlay_span(overlays, 158, address, size) != body):
            raise ValueError(f"Actor linked/packaged {copy} copy differs")
    if overlay_span(overlays, 149, DRIVER_ADDRESS, DRIVER_SIZE) != elf_bytes_at(
            build / "overworld_wild_spawns_overlay_linked.o", DRIVER_ADDRESS, DRIVER_SIZE):
        raise ValueError("Wild packaged current Arc driver differs")
    if len((build / "output_overworld_wild_spawns_overlay.bin").read_bytes()) != 0xB000:
        raise ValueError("Wild output retained the private Actor body")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--as", dest="assembler", default="arm-none-eabi-as")
    args = parser.parse_args()
    pack(args.build_dir.resolve(), args.assembler)
if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Assemble and execute the bounded grass-effect allocation guard on the host.

This checks instructions/ABI, not game behavior. No emulator core is started.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SITE = 0x021FF1F0
CONTINUE = SITE + 8
BASE = 0x023D0000  # Arbitrary executable location for the relocatable helper.
SYMBOL = "OverworldGrassEffect_InitAllocationGuard"
DISPLACED = bytes.fromhex("e0630221206b0902")


def check(value, message):
    if not value:
        raise ValueError(message)


def stock_guard():
    import ndspy.code
    import ndspy.rom
    rom = ndspy.rom.NintendoDSRom.fromFile(ROOT / "rom.nds")
    overlay = ndspy.code.loadOverlayTable(rom.arm9OverlayTable,
        lambda _id, file_id: rom.files[file_id], {1})[1]
    offset = SITE - overlay.ramAddress
    check(hashlib.sha256(overlay.data[0x021FF174 - overlay.ramAddress:0x021FF228 - overlay.ramAddress]).hexdigest()
          == "bee3113682eda39fd2f9eb3498bc9a5bc5cd49637ea67843cf8a414ef682f21b",
          "stock grass-effect init body differs")
    check(bytes(overlay.data[offset:offset + 8]) == DISPLACED,
          "grass init displaced stock instructions differ")
    check(bytes(overlay.data[0x021FF222 - overlay.ramAddress:0x021FF226 - overlay.ramAddress])
          == bytes.fromhex("03b078bd"), "stock init FALSE-return frame differs")
    reference = (ROOT / ".codex-reference/pokeheartgold/asm/overlay_01_021FEEEC.s").read_text()
    owner = reference.split("ov01_021FF174: ;", 1)[1].split("thumb_func_end ov01_021FF174", 1)[0]
    check("push {r3, r4, r5, r6, lr}" in owner and "sub sp, #0xc" in owner,
          "stock init frame ownership differs")
    lines = [line.strip() for line in (ROOT / "hooks").read_text().splitlines()
             if not line.lstrip().startswith("#") and SYMBOL in line]
    check(lines == [f"0001 {SYMBOL} 021FF1F0 1"], "grass hook routing differs")


def hook_bytes():
    # Execute the real packaging function, not a copied LDR/BX encoder.
    source = ast.parse((ROOT / "scripts/make.py").read_text())
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "Hook")
    function.returns = None
    for arg in function.args.args:
        arg.annotation = None
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "scripts/make.py:Hook", "exec"), namespace)
    out = io.BytesIO()
    namespace["Hook"](out, BASE, 0, 1, SITE)
    data = out.getvalue()
    check(len(data) == 8, "grass redirect does not fit its displaced span")
    return data


def assemble():
    with tempfile.TemporaryDirectory(prefix="grass-effect-guard-") as folder:
        # GNU as is the same assembler used by Make. Only this source is read;
        # the repository is read-only and outputs belong to the temp folder.
        subprocess.run(["docker", "run", "--rm", "-v", f"{ROOT}:/repo:ro",
            "-v", f"{folder}:/out", "hg-engine", "sh", "-c",
            "arm-none-eabi-as -mthumb -o /out/guard.o "
            "/repo/asm/overworld_grass_effect_guard.s && "
            "arm-none-eabi-ld -T /repo/src/linker.ld -o /out/guard-linked.o /out/guard.o && "
            "arm-none-eabi-objcopy -O binary -j .overworld_grass_effect_guard /out/guard-linked.o /out/guard.bin"],
            check=True, capture_output=True, text=True)
        return (Path(folder) / "guard.bin").read_bytes()


def execute(code, pointer):
    """Tiny Thumb interpreter: only instructions this ABI adapter may use."""
    regs = [0x11000000 + i * 4 for i in range(16)]
    regs[0], regs[4], regs[13], regs[14], regs[15] = pointer, 0x02200000, 0x023F0000, SITE + 1, SITE
    original = regs[:]
    memory = {regs[4] + 0x30: 0x02210000, regs[4] + 0x3C: 0xDEADBEEF}
    saved = [0x33, 0x44, 0x55, 0x66, 0x02001001]
    for i, value in enumerate(saved):
        memory[regs[13] + 12 + i * 4] = value
    image = {SITE + i: b for i, b in enumerate(hook_bytes())}
    image.update({BASE + i: b for i, b in enumerate(code)})
    writes, zero = [], False
    def word(address):
        if address in memory:
            return memory[address]
        return sum(image[address + i] << (8 * i) for i in range(4))
    for _ in range(32):
        pc = regs[15]
        if pc in (CONTINUE, 0x02001000):
            return regs, original, memory, writes, saved
        op = image[pc] | image[pc + 1] << 8
        regs[15] += 2
        if op & 0xF800 == 0x2800:  # CMP immediate
            zero = regs[(op >> 8) & 7] == (op & 255)
        elif op & 0xFF00 == 0xD000:  # BEQ
            displacement = op & 255
            if displacement & 128:
                displacement -= 256
            if zero:
                regs[15] = pc + 4 + displacement * 2
        elif op & 0xF800 == 0x2000:  # MOV immediate
            regs[(op >> 8) & 7] = op & 255
        elif op & 0xF800 == 0:  # LSL immediate
            regs[op & 7] = (regs[(op >> 3) & 7] << ((op >> 6) & 31)) & 0xFFFFFFFF
        elif op & 0xF800 in (0x6000, 0x6800):
            address = regs[(op >> 3) & 7] + ((op >> 6) & 31) * 4
            if op & 0xF800 == 0x6800:
                regs[op & 7] = word(address)
            else:
                memory[address] = regs[op & 7]
                writes.append(address)
        elif op & 0xF800 == 0x4800:  # LDR literal
            regs[(op >> 8) & 7] = word(((pc + 4) & ~3) + (op & 255) * 4)
        elif op & 0xFF87 == 0x4700:  # BX
            regs[15] = regs[(op >> 3) & 15] & ~1
        elif op & 0xFE00 == 0xB400:  # PUSH
            selected = [i for i in range(8) if op & (1 << i)] + ([14] if op & 256 else [])
            regs[13] -= 4 * len(selected)
            for i, register in enumerate(selected):
                memory[regs[13] + 4 * i] = regs[register]
                writes.append(regs[13] + 4 * i)
        elif op & 0xFE00 == 0xBC00:  # POP
            selected = [i for i in range(8) if op & (1 << i)] + ([15] if op & 256 else [])
            sp = regs[13]
            for i, register in enumerate(selected):
                regs[register] = word(sp + 4 * i)
            regs[13] = sp + 4 * len(selected)
            regs[15] &= ~1
        elif op & 0xF800 == 0x9000:  # STR SP-relative
            address = regs[13] + (op & 255) * 4
            memory[address] = regs[(op >> 8) & 7]
            writes.append(address)
        elif op & 0xFF80 == 0xB000:  # ADD SP
            regs[13] += (op & 127) * 4
        else:
            raise ValueError(f"unexpected guard instruction {op:04X} at {pc:08X}")
    raise ValueError("guard did not terminate within 32 instructions")


def verify(code):
    check(len(code) <= 32, "guard exceeds its bounded 32-byte code budget")
    for pointer in (0, 0x02280000, 0x023FFFFC):
        regs, before, memory, writes, saved = execute(code, pointer)
        if pointer:
            expected = before[:]
            expected[0], expected[1], expected[15] = 0x02210000, 0x200, CONTINUE
            check(regs == expected, "nonNULL guard differs from displaced register/SP/LR behavior")
            check(memory[before[4] + 0x3C] == pointer, "effect handle not stored")
            check(all(address == before[4] + 0x3C or before[13] - 8 <= address < before[13]
                      for address in writes), "nonNULL guard wrote outside owned frame/handle")
        else:
            check(regs[0] == 0 and regs[15] == (saved[-1] & ~1), "NULL guard did not return FALSE")
            check(regs[3:7] == saved[:4] and regs[13] == before[13] + 32,
                  "NULL guard did not restore the stock init frame")
            check(not writes, "NULL guard wrote data or created ownership")
    # A changed branch condition must fail the same assembled-byte checker.
    corrupted = bytearray(code)
    corrupted[2:4] = bytes.fromhex("0000")
    try:
        regs, _, _, _, _ = execute(corrupted, 0)
        check(regs[15] == 0x02001000 and regs[0] == 0, "negative control rejected")
    except ValueError:
        pass
    else:
        raise ValueError("missing NULL branch negative control was accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-only", action="store_true", help="authenticate original ROM seam and hook routing")
    parser.add_argument("--assembled", type=Path, help="check a raw .overworld_grass_effect_guard extraction")
    args = parser.parse_args()
    stock_guard()
    if not args.stock_only:
        code = args.assembled.read_bytes() if args.assembled else assemble()
        verify(code)
    print(json.dumps({"passed": True, "scope": "stock-seam" if args.stock_only else "assembled-guard-ABI",
                      "gameBehaviorVerified": False}))


if __name__ == "__main__":
    main()

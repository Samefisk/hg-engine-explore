#!/usr/bin/env python3
"""Check the assembled bubble admission guard and its stock entry frame.

This executes the actual Thumb bytes and real Hook encoder on the host. It does
not start a game, claim native behavior, or write ROM files.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENTRY = 0x02203A48
SITE = 0x02203A50
CONTINUE = 0x02203A58
GET_CONTEXT = 0x021F146C
BASE = 0x023D0000
SYMBOL = "OverworldBubbleEffect_ModelAdmissionGuard"
PROLOGUE = bytes.fromhex("78b58bb0051c0c1c")
DISPLACED = bytes.fromhex("edf70cfd061c1221")


def check(value, message):
    if not value:
        raise ValueError(message)


def stock_guard():
    import ndspy.code
    import ndspy.rom
    rom = ndspy.rom.NintendoDSRom.fromFile(ROOT / "rom.nds")
    overlay = ndspy.code.loadOverlayTable(rom.arm9OverlayTable,
        lambda _id, file_id: rom.files[file_id], {1})[1]
    start = ENTRY - overlay.ramAddress
    body = bytes(overlay.data[start:start + 0x6C])
    check(hashlib.sha256(body).hexdigest()
          == "e8624892211f409e67349bacf60b43a1b19bb962331e77bea38feac560c4af33",
          "stock bubble entry body differs")
    check(body[:16] == PROLOGUE + DISPLACED, "bubble displaced stock instructions differ")
    check(body[0x1E:0x26] == bytes.fromhex("02d00bb0002078bd"),
          "stock bubble FALSE-return frame differs")
    reference = (ROOT / ".codex-reference/pokeheartgold/asm/overlay_01_02203A18.s").read_text()
    owner = reference.split("ov01_02203A48: ;", 1)[1].split("thumb_func_end ov01_02203A48", 1)[0]
    check("push {r3, r4, r5, r6, lr}" in owner and "sub sp, #0x2c" in owner,
          "stock bubble frame ownership differs")
    lines = [line.strip() for line in (ROOT / "hooks").read_text().splitlines()
             if not line.lstrip().startswith("#") and SYMBOL in line]
    check(lines == [f"0001 {SYMBOL} 02203A50 2"], "bubble hook routing differs")


def hook_bytes():
    # Use the production encoder, including its register choice and Thumb bit.
    source = ast.parse((ROOT / "scripts/make.py").read_text())
    function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == "Hook")
    function.returns = None
    for arg in function.args.args:
        arg.annotation = None
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "scripts/make.py:Hook", "exec"), namespace)
    out = io.BytesIO()
    namespace["Hook"](out, BASE, 0, 2, SITE)
    data = out.getvalue()
    check(len(data) == 8, "bubble redirect exceeds its displaced span")
    return data


def assemble():
    # Compile only this source. No repository Make target or ROM build runs.
    names = ("arm-none-eabi-as", "arm-none-eabi-ld", "arm-none-eabi-objcopy")
    commands = [shutil.which(name) for name in names]
    check(all(commands), "local ARM assembler/linker/objcopy are required")
    with tempfile.TemporaryDirectory(prefix="bubble-effect-guard-") as folder:
        folder = Path(folder)
        linker = folder / "guard.ld"
        linker.write_text(f"SECTIONS {{ .overworld_bubble_effect_guard 0x{BASE:X} : "
                          "{ *(.overworld_bubble_effect_guard) } }\n")
        subprocess.run([commands[0], "-mcpu=arm946e-s", "-mthumb", "-o", str(folder / "guard.o"),
                        str(ROOT / "asm/overworld_bubble_effect_guard.s")], check=True, capture_output=True)
        subprocess.run([commands[1], "-T", str(linker), "-o", str(folder / "guard.elf"),
                        str(folder / "guard.o")], check=True, capture_output=True)
        subprocess.run([commands[2], "-O", "binary", "-j", ".overworld_bubble_effect_guard",
                        str(folder / "guard.elf"), str(folder / "guard.bin")], check=True, capture_output=True)
        return (folder / "guard.bin").read_bytes()


def signed(value):
    return value - (1 << 32) if value & 0x80000000 else value


def execute(code, manager=0x02220000, pool=0x02230000, used=0, capacity=1, redirect=True):
    """Bounded instruction interpreter; unexpected reads/opcodes fail closed."""
    regs = [0x11000000 + i * 4 for i in range(16)]
    regs[0], regs[1], regs[13], regs[14], regs[15] = 0x02210000, 7, 0x023F0000, 0x02001001, ENTRY
    original = regs[:]
    context = 0x02218000
    memory = {context + 0x20: manager, 0x02240004: 0, 0x02240008: 0xCAFEBABE}
    if manager:
        memory[manager + 0x0C] = pool
    if pool:
        memory[pool + 8], memory[pool + 0xD4] = capacity, used
    original_memory = memory.copy()
    image = {ENTRY + i: b for i, b in enumerate(PROLOGUE + (hook_bytes() if redirect else DISPLACED))}
    image.update({BASE + i: b for i, b in enumerate(code)})
    reads, writes, calls = [], [], 0
    compare = (0, 0)

    def word(address):
        reads.append(address)
        if address in memory:
            return memory[address]
        check(all(address + i in image for i in range(4)), f"unowned word read {address:08X}")
        return sum(image[address + i] << (8 * i) for i in range(4))

    def get_context(return_pc):
        nonlocal calls
        check(regs[0] == original[0] and regs[4] == original[1] and regs[5] == original[0],
              "GetContext arguments or saved bubble/object differ")
        check(regs[13] == original[13] - 64, "GetContext stock frame differs")
        calls += 1
        regs[0], regs[1], regs[2], regs[3] = context, 0xDEAD0001, 0xDEAD0002, 0xDEAD0003
        regs[14] = return_pc | 1

    for _ in range(48):
        pc = regs[15]
        if pc in (CONTINUE, original[14] & ~1):
            return {"regs": regs, "before": original, "memory": memory, "beforeMemory": original_memory,
                    "reads": reads, "writes": writes, "calls": calls, "context": context}
        check(pc in image and pc + 1 in image, f"unowned instruction {pc:08X}")
        op = image[pc] | image[pc + 1] << 8
        regs[15] = pc + 2
        if op & 0xF800 == 0x2800:
            compare = (regs[(op >> 8) & 7], op & 255)
        elif op & 0xFFC0 == 0x4280:
            compare = (regs[op & 7], regs[(op >> 3) & 7])
        elif op & 0xFF00 in (0xD000, 0xDA00):
            offset = (op & 255) - (256 if op & 128 else 0)
            take = compare[0] == compare[1] if op & 0xFF00 == 0xD000 else signed(compare[0]) >= signed(compare[1])
            if take:
                regs[15] = pc + 4 + offset * 2
        elif op & 0xF800 == 0x2000:
            regs[(op >> 8) & 7] = op & 255
        elif op & 0xF800 == 0x3000:
            register = (op >> 8) & 7
            regs[register] = (regs[register] + (op & 255)) & 0xFFFFFFFF
        elif op & 0xFE00 == 0x1C00:
            regs[op & 7] = (regs[(op >> 3) & 7] + ((op >> 6) & 7)) & 0xFFFFFFFF
        elif op & 0xF800 == 0x6800:
            regs[op & 7] = word(regs[(op >> 3) & 7] + ((op >> 6) & 31) * 4)
        elif op & 0xF800 == 0x4800:
            regs[(op >> 8) & 7] = word(((pc + 4) & ~3) + (op & 255) * 4)
        elif op & 0xFF87 == 0x4780:
            check(regs[(op >> 3) & 15] == GET_CONTEXT | 1, "guard called a different native owner")
            get_context(pc + 2)
        elif op & 0xFF87 == 0x4700:
            regs[15] = regs[(op >> 3) & 15] & ~1
        elif op & 0xF800 == 0xF000:
            second = image[pc + 2] | image[pc + 3] << 8
            check(second & 0xF800 == 0xF800, "stock BL encoding differs")
            offset = ((op & 0x7FF) << 12) | ((second & 0x7FF) << 1)
            if offset & (1 << 22):
                offset -= 1 << 23
            check(pc + 4 + offset == GET_CONTEXT, "stock displaced call owner differs")
            get_context(pc + 4)
            regs[15] = pc + 4
        elif op & 0xFE00 == 0xB400:
            selected = [i for i in range(8) if op & (1 << i)] + ([14] if op & 256 else [])
            regs[13] -= 4 * len(selected)
            for i, register in enumerate(selected):
                memory[regs[13] + 4 * i] = regs[register]
                writes.append(regs[13] + 4 * i)
        elif op & 0xFE00 == 0xBC00:
            selected = [i for i in range(8) if op & (1 << i)] + ([15] if op & 256 else [])
            sp = regs[13]
            for i, register in enumerate(selected):
                regs[register] = word(sp + 4 * i)
            regs[13] = sp + 4 * len(selected)
            regs[15] &= ~1
        elif op & 0xFF80 in (0xB000, 0xB080):
            regs[13] += (op & 127) * (-4 if op & 128 else 4)
        else:
            raise ValueError(f"unexpected guard instruction {op:04X} at {pc:08X}")
    raise ValueError("bubble guard exceeded 48 instructions")


CASES = (
    ("null-manager", {"manager": 0}, False),
    ("null-pool", {"pool": 0}, False),
    ("empty-capacity", {"used": 0, "capacity": 0}, False),
    ("full", {"used": 4, "capacity": 4}, False),
    ("overfull", {"used": 5, "capacity": 4}, False),
    ("available", {"used": 0, "capacity": 1}, True),
    ("one-free", {"used": 3, "capacity": 4}, True),
    ("signed-less", {"used": 0x80000000, "capacity": 0}, True),
    ("signed-greater", {"used": 0, "capacity": 0x80000000}, False),
)


def verify_case(code, facts, admitted):
    result = execute(code, **facts)
    regs, before, context = result["regs"], result["before"], result["context"]
    check(result["calls"] == 1, "GetContext must run exactly once")
    check(all(before[13] - 20 <= address < before[13] for address in result["writes"]),
          "bubble guard wrote outside its original saved frame")
    check(all(result["memory"][key] == value for key, value in result["beforeMemory"].items()),
          "bubble guard changed pool, busy flag, or resource state")
    check(regs[7:13] == before[7:13], "bubble guard changed preserved registers")
    if admitted:
        check(regs[15] == CONTINUE and regs[0] == context and regs[1] == 0x12 and regs[6] == context,
              "admitted bubble differs from displaced context/type setup")
        check(regs[4:6] == [before[1], before[0]] and regs[13] == before[13] - 64,
              "admitted bubble lost object/id or original stock frame")
        check(result["memory"][before[13] - 4] == before[14], "saved caller return changed")
    else:
        check(regs[0] == 0 and regs[15] == before[14] & ~1, "unavailable bubble did not return FALSE")
        check(regs[3:7] == before[3:7] and regs[13] == before[13],
              "rejected bubble did not restore its stock registers/stack")
    return result


def verify(code):
    check(len(code) <= 48, "bubble guard exceeds its bounded 48-byte slot")
    for _, facts, admitted in CASES:
        verify_case(code, facts, admitted)
    # The authentic unguarded entry admits the full pool: the measured fault's
    # admission defect remains RED independently of the new instruction bytes.
    for facts in ({"used": 4, "capacity": 4}, {"pool": 0}):
        stock = execute(b"", **facts, redirect=False)
        check(stock["regs"][15] == CONTINUE, "stock unavailable-pool RED no longer reaches resource admission")
    for offset, facts in ((8, {"manager": 0}), (14, {"pool": 0}),
                          (24, {"used": 4, "capacity": 4})):
        corrupted = bytearray(code)
        check(corrupted[offset + 1] in (0xD0, 0xDA), "negative-control branch offset differs")
        corrupted[offset:offset + 2] = bytes.fromhex("c046")  # Real Thumb NOP.
        try:
            verify_case(corrupted, facts, False)
        except (ValueError, KeyError):
            pass
        else:
            raise ValueError("removed admission branch was accepted")
    return {"cases": [name for name, _, _ in CASES], "copiedFaultsRejected": 3,
            "unguardedStockFullPool": "RED-resource-admission",
            "unguardedStockNullPool": "RED-resource-admission"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-only", action="store_true")
    parser.add_argument("--assembled", type=Path)
    args = parser.parse_args()
    stock_guard()
    report = {"passed": True, "gameBehaviorVerified": False, "scope": "stock-entry-seam"}
    if not args.stock_only:
        code = args.assembled.read_bytes() if args.assembled else assemble()
        report.update(verify(code), scope="assembled-bubble-admission-ABI", size=len(code),
                      assembledSha256=hashlib.sha256(code).hexdigest())
    print(json.dumps(report))


if __name__ == "__main__":
    main()

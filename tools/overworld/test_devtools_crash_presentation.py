"""Bounded native-layout and read-only crash presentation controls."""
import hashlib
from pathlib import Path
import re
import struct
import subprocess
import unittest
from unittest.mock import patch

from tools.overworld import devtools_crash_presentation as crash


class CrashPresentationTests(unittest.TestCase):
    def relocated_fixture(self, start=0x023CE000, restore=0x023CD000, ensure=0x023CDF00, fault=None):
        """Synthetic reviewed layout; no game bytes or emulator needed."""
        name = "OverworldWildSpawns_StartMovementCrashShake"
        data = bytearray(range(72))
        def branch(offset, target):
            displacement = target - (start + offset + 4)
            self.assertEqual(displacement & 1, 0)
            bits = displacement & 0x7FFFFF
            struct.pack_into("<HH", data, offset, 0xF000 | (bits >> 12),
                             0xF800 | ((bits >> 1) & 0x7FF))
        branch(22, restore)
        branch(60, ensure)
        digest = hashlib.sha256(crash._layout_code(name, data)).hexdigest()
        if fault == "target": branch(22, restore + 2)
        elif fault == "second-target": branch(60, ensure + 2)
        elif fault == "opcode": struct.pack_into("<H", data, 24, 0xE800)
        elif fault == "layout": data[40] ^= 1
        bodies = {name: (start, bytes(data)),
                  "OverworldWildSpawns_RestoreMovementCrashShake": (restore, b"restore"),
                  "OverworldWildSpawns_EnsureFrameMovementTask": (ensure, b"ensure")}
        memory = {address: code for address, code in bodies.values()}
        def lookup(image, symbol_name, kind, **kwargs):
            if kind == 1: return 0x02200000, crash.STATE_SIZE, None
            address, code = bodies[symbol_name]
            if "expected_size" in kwargs: self.assertEqual(len(code), kwargs["expected_size"])
            return address, len(code), code
        def package(address, size):
            if fault == "target-package" and address == ensure: return b"wrong"
            return memory[address]
        with patch.object(crash, "symbol", side_effect=lookup), patch.object(crash, "CODE", ((name, 72, digest),)):
            reader = crash.CrashPresentationReader(lambda _: b"elf", package)
        return reader, memory

    def test_relocation_preserves_layout_and_authenticates_both_targets(self):
        for locations in ((0x023CE000, 0x023CD000, 0x023CDF00),
                          (0x023CE102, 0x023CCFFE, 0x023CE200)):
            reader, memory = self.relocated_fixture(*locations)
            reader.boundary(lambda address, size: memory[address])
            self.assertEqual(len(reader.code), 3)
            memory[locations[2]] = b"changed"
            with self.assertRaisesRegex(ValueError, "live-code"):
                reader.boundary(lambda address, size: memory[address])

    def test_wrong_branch_target_opcode_layout_and_callee_package_reject(self):
        for fault in ("target", "second-target", "opcode", "layout", "target-package"):
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                self.relocated_fixture(fault=fault)

    def fixture(self):
        code = b"abcd"
        def symbol(image, name, kind, **kwargs):
            if kind == 1:
                self.assertEqual(kwargs["expected_size"], crash.STATE_SIZE)
                return 0x02200000, crash.STATE_SIZE, None
            self.assertEqual(kwargs["expected_size"], 4)
            return 0x023CD000, 4, code
        with patch.object(crash, "symbol", side_effect=symbol), patch.object(crash, "CODE",
                (("test", 4, hashlib.sha256(code).hexdigest()),)):
            reader = crash.CrashPresentationReader(lambda _: b"elf", lambda a,n: code)
        owner = 0x02210000; slot = 7
        memory = {0x023CD000: code, reader.state + slot*20: struct.pack("<I",owner),
            reader.state+714+slot: b"\x0a", reader.state+724+slot*4: struct.pack("<i",38174720),
            reader.state+764+slot*4: struct.pack("<i",26050560)}
        actor = {"identityVerified":True,"handle":{"slot":slot,"value":131079},
                 "engineIdentity":{"pointer":owner},"sourceIdentity":{"object":owner}}
        return reader, memory, actor

    def test_known_active_and_inactive_keep_exact_owner_and_clock(self):
        reader, memory, actor = self.fixture()
        for timer in (10,0):
            memory[reader.state+714+7] = bytes([timer])
            reader.boundary(lambda a,n: memory[a])
            value = reader.observe(lambda a,n: memory[a],actor,848,2113)
            self.assertTrue(value["known"])
            self.assertEqual((value["timer"],value["baseX"],value["baseZ"]),(timer,38174720,26050560))
            self.assertEqual((value["frame"],value["nativeCycle"]),(848,2113))
            self.assertEqual(value["handle"],actor["handle"])
            self.assertEqual(value["objectPointer"],actor["engineIdentity"]["pointer"])

    def test_live_code_absent_or_changed_rejects_boundary(self):
        reader, _, _ = self.fixture()
        for data in (b"",b"abce"):
            with self.assertRaisesRegex(ValueError,"live-code"):
                reader.boundary(lambda a,n: data)

    def test_short_data_and_changed_or_unverified_owner_are_unknown(self):
        for fault in ("short","owner","unverified"):
            reader,memory,actor = self.fixture()
            if fault=="short": memory[reader.state+714+7] = b""
            elif fault=="owner": memory[reader.state+140] = struct.pack("<I",0x02220000)
            else: actor["identityVerified"] = False
            value=reader.observe(lambda a,n: memory[a],actor,848,2113)
            self.assertFalse(value["known"])
            self.assertNotIn("timer",value)

    def test_unknown_layout_and_wrong_package_fail(self):
        code=b"abcd"
        for fault in ("layout-code", "package", "size"):
            with self.subTest(fault=fault):
                def lookup(image,name,kind,**kwargs):
                    if fault=="size": raise ValueError("wrong-symbol-size")
                    return (0x02200000,944,None) if kind==1 else (0x023CD000,4,code)
                digest=hashlib.sha256(b"bad" if fault=="layout-code" else code).hexdigest()
                with patch.object(crash,"symbol",side_effect=lookup), patch.object(crash,"CODE",(("test",4,digest),)):
                    with self.assertRaises(ValueError):
                        crash.CrashPresentationReader(lambda _:b"elf",lambda a,n:b"wrong")
        with self.assertRaisesRegex(ValueError,"invalid-linked-elf"):
            crash.CrashPresentationReader(lambda _:b"wrong",lambda a,n:b"")

    def test_actual_arm32_header_layout(self):
        root=Path(__file__).resolve().parents[2]
        fields=("movementCrashShakeTimers","movementCrashShakeBaseX","movementCrashShakeBaseZ")
        source='#include "overworld_wild_spawns_internal.h"\nconst unsigned offsets[]={sizeof(OverworldWildSpawnState),'+','.join(
            '__builtin_offsetof(OverworldWildSpawnState,'+name+')' for name in fields)+'};\n'
        result=subprocess.run(["clang","-target","armv5te-none-eabi","-ffreestanding","-w",
            "-Iinclude","-I.","-x","c","-S","-emit-llvm","-o","-","-"],input=source,
            cwd=root,text=True,capture_output=True,check=True,timeout=15)
        row=next(line for line in result.stdout.splitlines() if line.startswith("@offsets ="))
        self.assertEqual(tuple(map(int,re.findall(r"i32 (\d+)",row))), (952,*crash.OFFSETS))


if __name__ == "__main__": unittest.main()

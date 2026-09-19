"""Same native reader with host memory faults; no gameplay proof."""
from pathlib import Path
import unittest
import struct

from tools.overworld.devtools_corner_observer import NativeCornerObserver
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
from tools.overworld import test_devtools_mount_pacing_observer as pacing_fixture


class CornerTests(unittest.TestCase):
    def fixture(self):
        old, s, actor, engine, regs, put, calls, poses = pacing_fixture.MountPacingTests().fixture()
        path = s.rt.REPO / "build/pokemon_move_history_overlay_linked.o"
        if not path.exists():
            self.skipTest("current linked Walk object needed for full-body reader control")
        names = ["OverworldWalk_StrictDiagonalAllowed", "OverworldWalk_StrictDiagonalAllowedBody",
                 "Walk_ValidateDiagonalLanding"]
        if b"Walk_DiagonalRejection\0" in path.read_bytes():
            names.append("Walk_DiagonalRejection")
        symbols = {name: _elf_function_extent(path, name)[0] for name in names}
        s.rt.linked_symbols = lambda p: symbols
        s.rt.MOUNT_SYMBOLS["sOverworldMountState"] = 0x023BC744
        s.native_observation.elf_code = _elf_code
        for name in names:
            address, size = _elf_function_extent(path, name)
            data = _elf_code(path, address, max(32, size))
            s.code_regions.append((address, data)); put(address, data)
        address = 0x0205DA34
        stock = (s.rt.REPO / "build/arm9.bin").read_bytes()[0x5DA34:0x5DAA8]
        s.code_regions.append((address, stock)); put(address, stock)
        def packaged(address, size):
            for base, data in s.code_regions:
                if base <= address and address + size <= base + len(data):
                    return data[address-base:address-base+size]
            return b""
        s.packaged_code = packaged
        previous_unsigned = s.rt.unsigned
        s.rt.unsigned = lambda emu, address, size=4: s.field_pointer() if address == 0x023BC744 else previous_unsigned(emu,address,size)
        profile = bytearray(72); profile[19] = 1; profile[12] = 1
        put(0x023BC744,struct.pack("<II",s.field_pointer(),0x02213000))
        put(0x023BC744 + 8, profile)
        put(0x023BC744+80,struct.pack("<IHHHHBBBB",123,155,33,3,4,0,6,1,0))
        put(0x023BC744+96,struct.pack("<IBBBB",7,2,0,0,0))
        s._selector_observation = lambda: dict(heldKeys=80, newKeys=80, rawHeld=80)
        reader = NativeCornerObserver(s, old.subject, 10)
        return reader, s, actor, regs, put

    def invoke(self, r, name):
        address = r.code[name][0] if isinstance(name, str) else name
        for callback in tuple(r.observer.hooks.callbacks.get(address, ())):
            callback()

    def strict(self, r, regs):
        regs.r0, regs.r1, regs.r2 = r.mount_state, r.owner["avatarPointer"], 5
        regs.lr = 0x02010001
        self.invoke(r, r.strict_function)

    def test_noop_then_short_circuit_actual_raw_mask_and_cleanup(self):
        r,s,a,regs,put = self.fixture()
        self.assertEqual(r.observer.hooks.callbacks,{})
        r.arm()
        self.assertIn(r.code[r.strict_function][0], r.observer.hooks.callbacks)
        self.assertNotIn(r.code["OverworldWalk_StrictDiagonalAllowed"][0], r.observer.hooks.callbacks)
        # Unselected global collision entry must not create a return hook.
        self.invoke(r,"stockCollision")
        self.assertEqual(r.counts["collision"],0)
        self.strict(r,regs)
        regs.sp -= 16
        regs.r0,regs.r1,regs.r2 = r.owner["avatarPointer"],r.owner["playerPointer"],0
        regs.lr = 0x02010101
        self.invoke(r,"stockCollision")
        regs.r0=9
        self.invoke(r,0x02010100)
        regs.sp += 16; regs.r0=2 if r.return_kind == "candidate-flags" else 0
        self.invoke(r,0x02010000)
        receipt=r.result()["calls"][0]
        self.assertEqual(receipt["collisions"][0]["rawMask"],9)
        self.assertEqual(receipt["landings"],[])
        self.assertEqual(receipt["input"]["heldKeys"],80)
        self.assertEqual(receipt["returnValue"],0)
        self.assertEqual(receipt["returnKind"],r.return_kind)
        self.assertEqual(receipt["rawReturnValue"],2 if r.return_kind == "candidate-flags" else 0)
        self.assertEqual(receipt["target"],dict(x=2,y=1))
        self.assertEqual(r.result()["guestMemoryWrites"],0)
        self.assertIsNone(r.close()["failure"])
        self.assertEqual(r.observer.hooks.callbacks,{})

    def test_wrong_owner_context_return_code_and_bound(self):
        for fault in ("owner","arguments","return","code","profile","bound"):
            r,s,a,regs,put=self.fixture(); r.arm()
            with self.subTest(fault=fault):
                if fault in ("return","code","profile"):
                    self.strict(r,regs)
                    regs.r0=3 if fault=="return" else 0
                    if fault=="code":put(r.code[r.strict_function][0]+34,b"\xff")
                    if fault=="profile":put(r.mount_state+8+19,b"\x02")
                    with self.assertRaises(NativeObservationError): self.invoke(r,0x02010000)
                else:
                    if fault=="owner":a["authorityGeneration"]+=1
                    if fault=="bound":r.counts["strict"]=128
                    if fault=="arguments":
                        regs.r0=0;regs.r1=0;regs.r2=5
                        with self.assertRaises(NativeObservationError): self.invoke(r,r.strict_function)
                    else:
                        with self.assertRaises((ValueError,NativeObservationError)): self.strict(r,regs)
                r.close()
                self.assertIsNotNone(r.failure)
                self.assertEqual(r.observer.hooks.callbacks,{})

    def test_packaged_full_body_mismatch_and_pending_close(self):
        r,s,a,regs,put=self.fixture()
        original=s.packaged_code
        s.packaged_code=lambda address,size: b"\xff"*size if size>32 else original(address,size)
        with self.assertRaises(NativeObservationError):r.arm()
        self.assertEqual(r.observer.hooks.callbacks,{})
        r,s,a,regs,put=self.fixture();r.arm();self.strict(r,regs)
        self.assertIn("pending callback",r.close()["failure"])
        self.assertEqual(r.observer.contexts,[])
        self.assertEqual(r.observer.hooks.callbacks,{})

    def test_landing_is_actual_normal_return_and_wrong_nested_player_fails(self):
        r,s,a,regs,put=self.fixture();r.arm();self.strict(r,regs)
        regs.sp-=16
        for direction in (0,3):
            regs.r0,regs.r1,regs.r2=r.owner["avatarPointer"],r.owner["playerPointer"],direction
            regs.lr=0x02010101;self.invoke(r,"stockCollision")
            regs.r0=0;self.invoke(r,0x02010100)
        regs.r0,regs.r1,regs.r2=r.mount_state,2,1
        regs.lr=0x02010201;self.invoke(r,"Walk_ValidateDiagonalLanding")
        regs.r0=1;self.invoke(r,0x02010200)
        regs.sp+=16;regs.r0=0 if r.return_kind == "candidate-flags" else 1;self.invoke(r,0x02010000)
        receipt=r.result()["calls"][0]
        self.assertEqual(len(receipt["collisions"]),2)
        self.assertEqual(receipt["landings"][0]["returnValue"],1)
        self.assertTrue(receipt["landings"][0]["normalReturn"])
        r.close()
        r,s,a,regs,put=self.fixture();r.arm();self.strict(r,regs)
        regs.r0,regs.r1,regs.r2=r.owner["avatarPointer"],0,0
        with self.assertRaises(NativeObservationError):self.invoke(r,"stockCollision")
        r.close();self.assertEqual(r.observer.hooks.callbacks,{})

    def test_actual_public_header_caller_and_stock_extent_anchor(self):
        root=Path(__file__).resolve().parents[2]
        header=(root/"include/overworld_walk_module.h").read_text()
        self.assertRegex(header,r"OverworldWalk_StrictDiagonalAllowed\(\s*struct OverworldMountRuntimeState \*state,\s*struct FIELD_PLAYER_AVATAR \*avatar,\s*u8 direction")
        source=(root/"src/pokemon_move_history_overlay/overworld_walk_module.c").read_text()
        self.assertIn("WALK_COLLISION_CHECK(avatar, avatar->mapObject, direction) == 0",source)
        resolver = source.split("OverworldWalk_ResolveMountedDiagonal(", 1)[1]
        self.assertTrue("rejectionFlags = Walk_DiagonalRejection(state, avatar, direction);" in resolver,
                        "mounted resolution must call the observed typed classifier")
        self.assertIn("return Walk_DiagonalRejection(state, avatar, direction) == 0;",source)
        asm=root/".codex-reference/pokeheartgold/asm/unk_0205CB48.s"
        if asm.exists():
            text=asm.read_text()
            self.assertRegex(text,r"sub_0205DA34: ; 0x0205DA34")
            self.assertRegex(text,r"thumb_func_end sub_0205DA34\s+thumb_func_start sub_0205DAA8")

    def test_actual_profile_layout_and_avatar_layout(self):
        from tools.overworld import test_devtools_mount_walk_fixture as fixture
        fixture.IndependentAnchors().test_real_headers_compile_profile_and_arm_state_offsets()
        pacing_fixture.MountPacingTests().test_avatar_offsets_from_actual_arm_header()

    def test_typed_classifier_raw_returns_and_unknown_flags(self):
        # Host return-register controls work on retained BOOL packages too.
        # New-package tap selection is separately authenticated by arm().
        for raw in (0, 2, 4, 32, 1, 3, 6, 0x10000):
            r,s,a,regs,put = self.fixture();r.arm()
            r.return_kind = "candidate-flags"
            self.strict(r,regs);regs.r0=raw
            if raw in (0,2,4,32):
                self.invoke(r,0x02010000)
                value=r.result()["calls"][0]
                self.assertEqual(value["rawReturnValue"],raw)
                self.assertEqual(value["returnValue"],int(raw==0))
                self.assertEqual(value["returnKind"],"candidate-flags")
            else:
                with self.assertRaisesRegex(NativeObservationError,"known candidate reason"):
                    self.invoke(r,0x02010000)
            r.close()

    def test_candidate_reason_values_from_public_header(self):
        import re
        import subprocess
        from tools.overworld.devtools_corner_observer import CANDIDATE_RETURNS
        root=Path(__file__).resolve().parents[2]
        header=(root/"include/overworld_motion_model.h").read_text()
        source=""
        for name,expected in (("SIDE_BLOCKED",2),("BAD_TERRAIN",4),("BAD_DIRECTION",32)):
            symbol="OVERWORLD_MOTION_CANDIDATE_"+name
            source += re.search(r"^#define\s+"+symbol+r"\s+[^\n]+",header,re.M)[0]+"\n"
            source += f'_Static_assert({symbol} == {expected}, "{symbol}");\n'
        run=subprocess.run(["clang","-target","armv5te-none-eabi","-fsyntax-only","-x","c","-"],
                           input=source,text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(CANDIDATE_RETURNS,{0,2,4,32})

    def test_pose_binding_and_stock_mask_faults(self):
        for fault in ("pose","binding","mask"):
            r,s,a,regs,put=self.fixture();r.arm();self.strict(r,regs)
            if fault=="pose":
                original=s.rt.object_state
                s.rt.object_state=lambda emu,pointer:{**original(emu,pointer),"x":999}
            elif fault=="binding":put(r.mount_state+80,b"\xff")
            else:
                regs.sp-=16
                regs.r0,regs.r1,regs.r2=r.owner["avatarPointer"],r.owner["playerPointer"],0
                regs.lr=0x02010101;self.invoke(r,"stockCollision")
            regs.r0=0x10 if fault=="mask" else 0
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):
                self.invoke(r,0x02010100 if fault=="mask" else 0x02010000)
            r.close();self.assertEqual(r.observer.hooks.callbacks,{})


if __name__ == "__main__":
    unittest.main()

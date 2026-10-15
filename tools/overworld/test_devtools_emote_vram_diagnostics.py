"""Focused synthetic owner/VRAM controls; no emulator or guest work.

Intended home: tools/overworld/test_devtools_emote_vram_diagnostics.py.
The read-only stock ROM supplies authenticated code to a synthetic byte store;
only the native data boundary is replaced. No real session is read or changed.
Run from repository root only after root applies/reviews the draft.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import importlib.util
import struct
import unittest
from unittest.mock import patch


source = Path(__file__).with_name("devtools_emote_vram_diagnostics.py")
spec = importlib.util.spec_from_file_location("emote_vram_draft", source)
meter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meter)


class NativeBytes:
    def __init__(self, code):
        self.code = list(code)
        self.memory, self.reads = {}, []
        self.completed_frames = 381
        self.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=921)
        self.field = 0x02210000
        self.control, self.manager = 0x02210100, 0x02210200
        self.context, self.table, self.owner = 0x02210300, 0x02210400, 0x02210500
        self.tex_work, self.pal_work = 0x02220004, 0x02230004
        self.model_state, self.model_pool = 0x02210700, 0x02210800
        self.global_field = 0x021D4100  # synthetic pointer slot, never a live address
        self.write_words(self.global_field, self.field)
        self.write_words(self.field, self.control)
        self.write_words(self.field + 0x44, self.context)
        self.write_words(self.field + 0x6C, 1)
        self.write_words(self.control, self.manager, 0, 0, 0)
        self.write_words(self.manager, *meter.FIELD_TEMPLATE, 2, 0, self.field, 0, 0, 0)
        self.write_words(self.context, 4, 2, 0, 0, self.field, self.table, 0, 0, self.model_state)
        self.write_words(self.model_state, 4, 48 | (32 << 16), 0, self.model_pool, 0, 0, 0, 0, 0)
        self.write_words(self.model_pool, 0x0101, 0x02260000, 48)
        self.write_words(self.model_pool + 0xD4, 5)
        self.write_words(self.table, 0x12, self.owner, 0x13, 0x02210600)
        self.write_words(self.owner, self.context, 1, 0x02250000, 0x02250100, 0x02250200, 0x02250300, 0,
            self.owner, 0x02251000, 0x02251100, 0x02251200, 0x02251300, 0x02251400, 0x02251500, 0x10001, 0x20002, 2,
            *([0] * 20))
        self.write_words(meter.DISPATCH, *meter.DISPATCH_WORDS)
        self.write_words(meter.TEXTURE_STATE,
            self.tex_work, 0, self.tex_work + 16, 0x40000, 0, self.tex_work, 4096)
        self.write_words(self.tex_work, 0x100, 2048, 0, 0)
        self.write_words(self.tex_work + 16, 0, 0, 0xDEADBEEF, 0)
        self.write_words(meter.PALETTE_STATE,
            self.pal_work, self.pal_work + 16, 0x8000, self.pal_work, 16384)
        self.write_words(self.pal_work, 8, 136, 0, 0)
        self.write_words(self.pal_work + 16, 0, 0, 0xDEADBEEF, 0)

    def write_words(self, address, *words):
        self.write(address, struct.pack("<" + "I" * len(words), *words))

    def write(self, address, data):
        for offset, value in enumerate(data):
            self.memory[address + offset] = value

    def read(self, address, size):
        self.reads.append((address, size))
        fallback = next((data[address - base:address - base + size]
            for base, data in self.code if base <= address <= base + len(data) - size), bytes(size))
        return bytes(self.memory.get(address + i, value) for i, value in enumerate(fallback))

    def field_pointer(self):
        return struct.unpack("<I", self.read(self.global_field, 4))[0]

    def packaged_code(self, address, size):
        expected = next(data[address - base:address - base + size]
            for base, data in self.code if base <= address <= base + len(data) - size)
        live = self.read(address, size)
        if live != expected:
            raise ValueError("live/package code differs")
        return live


class EmoteVramControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ndspy.rom, ndspy.code, ndspy.codeCompression
        filename = Path.cwd() / "rom.nds"
        assert hashlib.sha1(filename.read_bytes()).hexdigest() == \
            "4fcded0e2713dc03929845de631d0932ea2b5a37"
        rom = ndspy.rom.NintendoDSRom.fromFile(filename)
        overlay = ndspy.code.loadOverlayTable(rom.arm9OverlayTable,
            lambda _id, file_id: rom.files[file_id], {1})[1]
        # New owners come from the current compiled product, not a private ticket fixture.
        # The reader still checks each full named body against its exact native SHA.
        from scripts.verify_pokemon_move_history_capture import elf_bytes_at
        elf = Path.cwd() / 'build/overworld_actor_system_overlay_linked.o'
        cls.code = [(rom.arm9RamAddress, ndspy.codeCompression.decompress(rom.arm9)),
                    (overlay.ramAddress, bytes(overlay.data))]
        for address,size,_sha,name in meter.STOCK_SEALS:
            if name.startswith('OverworldEmoteSlots_') or name=='descriptor':
                cls.code.insert(0,(address,elf_bytes_at(elf,address,size)))
        # Authenticate the exact redirected destructor tail from the compiled installer.
        from scripts.pack_overworld_emote_slots import source_contract, SECTIONS
        _bindings,_bodies,segments = source_contract(elf)
        patched = bytearray(overlay.data)
        for section,address,cap,_used,_sha,_original in SECTIONS:
            patched[address-overlay.ramAddress:address-overlay.ramAddress+cap] = segments[section]
        cls.code.insert(0,(overlay.ramAddress,bytes(patched)))

    def fixture(self):
        return NativeBytes(self.code)

    def test_busy_free_largest_and_alignment_with_no_guest_work(self):
        s = self.fixture()
        before = (s.completed_frames, s.rt.EXECUTED_FRAME_COUNT, dict(s.memory))
        result = meter.observe_emote_vram_diagnostics(s)
        self.assertTrue(result["known"], result)
        self.assertEqual(result["bubble"]["activeCount"], 1)
        self.assertEqual((result["texture"]["totalFreeBytes"],
            result["texture"]["largestUsableBytes"]), (2048, 2048))
        self.assertEqual((result["palette"]["totalFreeBytes"],
            result["palette"]["largestUsableBytes"]), (136, 128))
        self.assertEqual(result["palette"]["additionalTwoSlots"]["plannedVramOffsets"], [16, 48])
        self.assertTrue(result["canAdmitTwoAdditionalIndependentSlots"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["bytesRead"], sum(n for _, n in s.reads))
        self.assertLessEqual(result["bytesRead"], 24 * 1024)
        self.assertEqual(before, (s.completed_frames, s.rt.EXECUTED_FRAME_COUNT, s.memory))

    def test_native_model_pool_free_and_exhausted_counts_are_read_only(self):
        for count in (0, 5, 48):
            with self.subTest(count=count):
                s = self.fixture()
                s.write_words(s.model_pool + 0xD4, count)
                before = dict(s.memory)
                result = meter.observe_emote_vram_diagnostics(s)
                self.assertTrue(result["known"], result)
                pool = result["modelPool"]
                self.assertEqual((pool["pointer"], pool["capacity"], pool["allocatedCount"],
                    pool["freeSlots"], pool["exhausted"]),
                    (s.model_pool, 48, count, 48 - count, count == 48))
                self.assertFalse(result["acceptedProof"])
                self.assertEqual(s.memory, before)
                self.assertEqual(result["bytesRead"], sum(n for _, n in s.reads))
                self.assertLessEqual(result["bytesRead"], 24 * 1024)

    def test_native_model_pool_absence_invalid_counts_and_stale_owner_fail_closed(self):
        for fault in ("state-absent", "manager-absent", "unaligned", "outside", "state-heap",
                      "state-capacity", "capacity", "count", "negative-count", "short-read",
                      "changed-pool", "changed-count", "changed-state", "code"):
            with self.subTest(fault=fault):
                s = self.fixture()
                if fault == "state-absent": s.write_words(s.context + 0x20, 0)
                elif fault == "manager-absent": s.write_words(s.model_state + 0x0C, 0)
                elif fault == "unaligned": s.write_words(s.model_state + 0x0C, s.model_pool + 1)
                elif fault == "outside": s.write_words(s.model_state + 0x0C, 0x023FFF80)
                elif fault == "state-heap": s.write_words(s.model_state, 3)
                elif fault == "state-capacity": s.write_words(s.model_state + 4, 32)
                elif fault == "capacity": s.write_words(s.model_pool + 8, 32)
                elif fault == "count": s.write_words(s.model_pool + 0xD4, 49)
                elif fault == "negative-count": s.write_words(s.model_pool + 0xD4, 0xFFFFFFFF)
                elif fault == "code": s.write(0x02024280, b"\xff")
                else:
                    read = s.read
                    calls = 0
                    def changed(address, size):
                        nonlocal calls
                        data = read(address, size)
                        if address == s.model_pool and size == 12:
                            calls += 1
                            if fault == "short-read": return data[:-1]
                            if calls == 1:
                                if fault == "changed-pool": s.write_words(s.model_state + 0x0C, s.model_pool + 4)
                                elif fault == "changed-state": s.write_words(s.model_state + 4, 47)
                        if fault == "changed-count" and address == s.model_pool + 0xD4:
                            s.write_words(s.model_pool + 0xD4, 6)
                        return data
                    s.read = changed
                result = meter.observe_emote_vram_diagnostics(s)
                self.assertFalse(result["known"], result)
                self.assertNotIn("modelPool", result)
                self.assertLessEqual(result["bytesRead"], 24 * 1024)
                if fault == "outside": self.assertNotIn((0x023FFF80, 12), s.reads)

    def test_native_spare_head_previous_link_can_be_stale(self):
        s = self.fixture()  # both spare heads deliberately retain stale prev values
        self.assertTrue(meter.observe_emote_vram_diagnostics(s)["known"])

    def test_full_native_spare_pools_fit_unchanged_read_budget(self):
        s = self.fixture()
        for work, size in ((s.tex_work, 4096), (s.pal_work, 16384)):
            for offset in range(16, size, 16):
                following = work + offset + 16 if offset + 16 < size else 0
                s.write_words(work + offset, 0, 0, 0xDEADBEEF, following)
        result = meter.observe_emote_vram_diagnostics(s)
        self.assertTrue(result["known"], result)
        self.assertEqual(result["texture"]["spareNodeCount"], 255)
        self.assertEqual(result["palette"]["spareNodeCount"], 1023)
        self.assertEqual(result["bytesRead"], sum(n for _, n in s.reads))
        self.assertLessEqual(result["bytesRead"], 24 * 1024)

    def test_alignment_without_spare_node_is_known_no_fit(self):
        s = self.fixture()
        s.write_words(meter.PALETTE_STATE + 4, 0)
        result = meter.observe_emote_vram_diagnostics(s)
        self.assertTrue(result["known"], result)
        self.assertFalse(result["canAdmitTwoAdditionalIndependentSlots"])
        self.assertEqual(result["palette"]["additionalTwoSlots"]["reason"],
            "alignment-needs-spare-node")

    def test_fragmented_total_is_not_two_slot_admission(self):
        s = self.fixture()
        s.write_words(s.tex_work, 0x100, 768, 0, s.tex_work + 32)
        s.write_words(s.tex_work + 32, 0x1000, 256, s.tex_work, 0)
        result = meter.observe_emote_vram_diagnostics(s)
        self.assertTrue(result["known"], result)
        self.assertEqual(result["texture"]["totalFreeBytes"], 1024)
        self.assertFalse(result["texture"]["additionalTwoSlots"]["canAdmit"])

    def test_native_first_fit_spare_recycling_and_failure_order(self):
        # Stock exact-fit removal returns a node, which the next aligned
        # request can use. Initial zero spares alone does not mean no fit.
        recycled = meter._first_fit_two([(0, 32), (40, 40)], 0, 32, 16)
        self.assertTrue(recycled["canAdmit"])
        self.assertEqual(recycled["plannedVramOffsets"], [0, 48])
        # The first byte-fit needs a prefix node. Native failure here does
        # not search a later aligned block, even though total bytes suffice.
        first_failure = meter._first_fit_two([(8, 40), (96, 96)], 0, 32, 16)
        self.assertFalse(first_failure["canAdmit"])
        self.assertEqual(first_failure["reason"], "alignment-needs-spare-node")

    def test_malformed_nodes_and_limited_buffers_fail_closed(self):
        for mutation in ("cycle", "previous", "outside", "node-offset", "overlap", "work-overlap",
                         "duplicate-spare", "work-size", "short-read"):
            with self.subTest(mutation=mutation):
                s = self.fixture()
                if mutation == "cycle":
                    s.write_words(s.tex_work + 12, s.tex_work)
                elif mutation == "previous":
                    s.write_words(s.tex_work + 8, 0x02250000)
                elif mutation == "outside":
                    s.write_words(s.tex_work + 12, s.tex_work + 4096)
                elif mutation == "node-offset":
                    s.write_words(s.tex_work + 12, s.tex_work + 4)
                elif mutation == "overlap":
                    s.write_words(s.tex_work + 12, s.tex_work + 32)
                    s.write_words(s.tex_work + 32, 0x200, 16, s.tex_work, 0)
                elif mutation == "duplicate-spare":
                    s.write_words(meter.TEXTURE_STATE + 8, s.tex_work)
                elif mutation == "work-overlap":
                    s.write_words(meter.PALETTE_STATE + 12, s.tex_work)
                elif mutation == "work-size":
                    s.write_words(meter.TEXTURE_STATE + 24, 8192)
                else:
                    read = s.read
                    s.read = lambda address, n: read(address, n)[:-1] if address == s.tex_work else read(address, n)
                result = meter.observe_emote_vram_diagnostics(s)
                self.assertFalse(result["known"], result)
                self.assertNotIn("texture", result)
                self.assertNotIn("canAdmitTwoAdditionalIndependentSlots", result)
                self.assertNotIn((s.tex_work + 4096, 16), s.reads)
                if mutation == "work-overlap":
                    self.assertNotIn((s.tex_work, 16), s.reads)

    def test_owner_phase_code_or_budget_change_cannot_publish_free_space(self):
        for mutation in ("field-owner", "context-owner", "bubble-owner", "duplicate-owner",
                         "busy-count", "exiting", "dispatch", "clock", "late-owner",
                         "code", "code-package-and-live", "budget"):
            with self.subTest(mutation=mutation):
                s = self.fixture()
                if mutation == "field-owner":
                    s.write_words(s.manager + 24, s.field + 4)
                elif mutation == "context-owner":
                    s.write_words(s.context + 16, s.field + 4)
                elif mutation == "bubble-owner":
                    s.write_words(s.owner, s.context + 4)
                elif mutation == "duplicate-owner":
                    s.write_words(s.table + 8, 0x12, s.owner)
                elif mutation == "busy-count":
                    s.write_words(s.owner + 4, 4)
                elif mutation == "exiting":
                    s.write_words(s.control + 12, 1)
                elif mutation == "dispatch":
                    s.write_words(meter.DISPATCH, 0x020B5B20)
                elif mutation in ("code", "code-package-and-live"):
                    address = meter.STOCK_SEALS[0][0]
                    s.write(address, b"\xff")
                    if mutation == "code-package-and-live":
                        base, data = s.code[0]
                        offset = address - base
                        s.code[0] = (base, data[:offset] + b"\xff" + data[offset + 1:])
                elif mutation in ("clock", "late-owner"):
                    read = s.read
                    def changed(address, n):
                        data = read(address, n)
                        if address == s.pal_work + 28:
                            if mutation == "clock":
                                s.rt.EXECUTED_FRAME_COUNT += 1
                            else:
                                s.write_words(s.owner + 4, 0)
                        return data
                    s.read = changed
                with patch.object(meter, "READ_BUDGET", 64 if mutation == "budget" else 24 * 1024):
                    result = meter.observe_emote_vram_diagnostics(s)
                self.assertFalse(result["known"], result)
                self.assertNotIn("bubble", result)
                self.assertNotIn("texture", result)
                self.assertLessEqual(result["bytesRead"], result["readBudgetBytes"])

    def test_three_slot_active_retiring_and_exact_alias_faults(self):
        s = self.fixture()
        raw = s.read(s.owner, 148)
        owner = meter.decode_emote_owner(s.owner, s.context, raw)
        self.assertEqual(owner["slotLimit"], 3)
        self.assertEqual(owner["slots"][0]["pointer"], s.owner + 28)
        for fault in ("shared-object", "shared-effect", "shared-model", "shared-tex", "shared-pal", "missing-task", "free-not-zero", "count", "state"):
            with self.subTest(fault=fault):
                words = list(struct.unpack("<37I", raw))
                words[1] = 2
                words[17:27] = words[7:17]
                for key in (1, 2, 3, 4, 5, 6): words[17 + key] += 0x1000
                words[24] += 1; words[25] += 1
                index = {"shared-object": 18, "shared-effect": 19, "shared-model": 20,
                         "shared-tex": 24, "shared-pal": 25}.get(fault)
                if index is not None: words[index] = words[index - 10]
                elif fault == "missing-task": words[5] = 0
                elif fault == "free-not-zero": words[27] = s.owner
                elif fault == "count": words[1] = 3
                else: words[26] = 4
                with self.assertRaises(ValueError):
                    meter.decode_emote_owner(s.owner, s.context, struct.pack("<37I", *words))
        words = list(struct.unpack("<37I", raw)); words[9] = words[10] = 0; words[16] = 3
        self.assertEqual(meter.decode_emote_owner(s.owner, s.context, struct.pack("<37I", *words))["slots"][0]["state"], 3)


if __name__ == "__main__":
    unittest.main()

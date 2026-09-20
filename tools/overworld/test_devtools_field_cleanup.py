import struct
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.overworld import devtools_field_cleanup as d


def elf_fixture(file, base, fault=None):
    names = b"\0.text\0.bss\0.symtab\0.strtab\0.shstrtab\0"
    strings, symbols = bytearray(b"\0"), bytearray(16)
    memory = {}
    def add(name, address, size, kind, section):
        label = len(strings)
        strings.extend(name.encode() + b"\0")
        symbols.extend(struct.pack("<IIIBBH", label, address, size, kind, 0, section))
    for i, (owner, name) in enumerate(d.CODE):
        if owner == file:
            add(name, base + i * 16 + 1, 16, 2, 1)
    for i, (key, owner, name, section, size) in enumerate(d.DATA):
        if owner != file:
            continue
        address = base + (0x300 if section == ".bss" else 0x100) + i * 24
        if key == "actorState":
            address = d.ACTOR_STATE_ADDRESS
        add(name, address, size + (1 if fault == "size" else 0), 1,
            (1 if section == ".text" else 2) if fault != "section" else 4)
        memory[address] = bytes(size)
        if key == "actorState":
            memory[address] = struct.pack("<IHH", 0x5353574F, 2, size) + bytes(size - 8)
    blob = bytearray(52)
    rows = [(0,) * 10]
    for name, kind, flags, address, content, size, link, entry in (
        (".text", 1, 6, base, bytes(512), 512, 0, 0),
        (".bss", 8, 3, d.ACTOR_STATE_ADDRESS if file == d.ACTOR_ELF else base + 0x300,
         b"", 3000, 0, 0),
        (".symtab", 2, 0, 0, symbols, len(symbols), 4, 16),
        (".strtab", 3, 0, 0, strings, len(strings), 0, 0),
        (".shstrtab", 3, 0, 0, names, len(names), 0, 0),
    ):
        rows.append((names.index(name.encode()), kind, flags, address, len(blob), size, link, 0, 4, entry))
        blob.extend(content)
    offset = len(blob)
    for row in rows:
        blob.extend(struct.pack("<10I", *row))
    blob[:7] = b"\x7fELF\x01\x01\x01"
    struct.pack_into("<I", blob, 32, offset)
    struct.pack_into("<3H", blob, 46, 40, len(rows), 5)
    return bytes(blob), memory


class CleanupReaderTests(unittest.TestCase):
    def fixture(self, fault=None):
        images, memory = {}, {}
        for i, file in enumerate(sorted({x[1] for x in d.DATA})):
            base = d.ACTOR_REGION[0] if file == d.ACTOR_ELF else 0x02300000 + i * 0x1000
            images[file], values = elf_fixture(file, base, fault)
            memory.update(values)
        return images, memory

    def observe(self, fault=None, overlays=(131, 149), auth=True, short=False):
        images, memory = self.fixture(fault)
        return d.observe_field_cleanup(lambda address, size: memory[address][:size - 1] if short else memory[address][:size],
            lambda *args: auth, images.__getitem__, set(overlays), 30, 60)

    def test_current_typed_layout_is_read_without_inferred_return(self):
        result = self.observe()
        self.assertTrue(result["known"], result)
        self.assertEqual(result["readBytes"], 77)
        self.assertEqual(result["actorTransition"]["phase"], 0)
        self.assertEqual(result["wildFlags"]["helperOverlayReady"], 0)
        self.assertEqual(result["fieldTransition"]["active"], 0)
        self.assertFalse(result["acceptedProof"])
        self.assertNotIn("cleanupReturned", result)

    def test_actor_boot_resident_owner_is_not_required_in_sdk_table(self):
        self.assertTrue(self.observe(overlays=(131, 149))["known"])
        root = Path(__file__).resolve().parents[2]
        boot = (root / "armips/asm/syntheticoverlay.s").read_text()
        self.assertRegex(boot, r"mov r0, #0\s+mov r1, #158\s+bl LoadResidentOverlay")
        self.assertRegex(boot, r"LoadResidentOverlay:\s+ldr r2, =0x02007188\|1[^\n]*\n\s+bx r2")
        public = (root / "include/overworld_actor_system.h").read_text()
        self.assertIn("OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE 0x023B6B00", public)
        self.assertIn("OVERWORLD_ACTOR_SYSTEM_OVERLAY_END 0x023BAB00", public)
        internal = (root / "include/overworld_actor_system_internal.h").read_text()
        self.assertIn("(OVERWORLD_ACTOR_SYSTEM_OVERLAY_BASE + 0x3670)", internal)

    def test_actor_transition_values_and_invalid_header_or_phase(self):
        images, memory = self.fixture()
        address, _, _ = d.symbol(images["overworld_actor_system_overlay_linked.o"],
                                "gOverworldActorSystemState", 1)
        data = bytearray(memory[address])
        struct.pack_into("<I6H2B", data, 24, 17, 67, 69, 3, 2, 255, 128, 4, 1)
        memory[address] = data
        def observe():
            return d.observe_field_cleanup(lambda a, n: memory[a][:n], lambda *a: True,
                images.__getitem__, {131, 149, 158}, 30, 60)
        result = observe()
        self.assertTrue(result["known"], result)
        self.assertEqual(result["actorTransition"], dict(sequence=17, previousMapId=67,
            currentMapId=69, previousFieldEpoch=3, previousMapGeneration=2,
            actorMask=255, resumeMotionMask=128, phase=4, disposition=1))
        for offset in (0, 4, 6, 40):
            with self.subTest(offset=offset):
                previous = data[offset]
                data[offset] = 255
                self.assertFalse(observe()["known"])
                data[offset] = previous

    def test_public_header_anchors_actor_transition_prefix_and_layout(self):
        root = Path(__file__).resolve().parents[2]
        internal = (root / "include/overworld_actor_system_internal.h").read_text()
        public = (root / "include/overworld_actor_system.h").read_text()
        transition = (root / "include/overworld_actor_transition_model.h").read_text()
        prefix = internal.split("typedef struct OverworldActorSystemState {", 1)[1].split(
            "OverworldActorTransitionState transition;", 1)[0]
        fields = re.findall(r"(u32|u16|u8)\s+(\w+);", prefix)
        self.assertEqual(fields, [("u32", "magic"), ("u16", "version"), ("u16", "size"),
            ("u32", "frame"), ("u16", "fieldEpoch"), ("u8", "actorCount"),
            ("u8", "queueHead"), ("u8", "queueCount"), ("u8", "ackWriteIndex"),
            ("u16", "lastReason"), ("u32", "lastAcknowledgedSequence")])
        self.assertEqual(sum({"u32": 4, "u16": 2, "u8": 1}[t] for t, _ in fields), 24)
        self.assertIn("OVERWORLD_ACTOR_SYSTEM_OVERLAY_ID 158", public)
        self.assertIn("OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC 0x5353574F", public)
        self.assertIn("OVERWORLD_ACTOR_SYSTEM_ABI_VERSION 2", public)
        body = transition.split("typedef struct OverworldActorTransitionState {", 1)[1].split(
            "} OverworldActorTransitionState;", 1)[0]
        self.assertEqual(re.findall(r"(u32|u16|u8)\s+(\w+);", body), [
            ("u32", "sequence"), ("u16", "previousMapId"), ("u16", "currentMapId"),
            ("u32", "mapIdentity"), ("u16", "previousFieldEpoch"),
            ("u16", "previousMapGeneration"), ("u32", "previousFieldContext"),
            ("u16", "actorMask"), ("u16", "resumeMotionMask"), ("u8", "phase"),
            ("u8", "disposition")])
        self.assertIn("sizeof(OverworldActorTransitionState) == 20", transition)

    def test_wrong_code_absent_owner_wrong_size_and_partial_data_are_unknown(self):
        for args, reason in (({"auth": False}, "code-identity"),
                             ({"overlays": (131,)}, "overlay-missing"),
                             ({"fault": "size"}, "symbol-size"),
                             ({"fault": "section"}, "symbol"),
                             ({"short": True}, "short-data")):
            with self.subTest(args=args):
                result = self.observe(**args)
                self.assertFalse(result["known"])
                self.assertIn(reason, result["reason"])

    def test_partial_actor_prefix_and_wrong_actor_code_are_unknown(self):
        images, memory = self.fixture()
        file = "overworld_actor_system_overlay_linked.o"
        address = d.symbol(images[file], "gOverworldActorSystemState", 1)[0]
        code_address = d.symbol(images[file], "ActorSystem_EnsureInitialized", 2)[0]
        for partial in (True, False):
            result = d.observe_field_cleanup(
                lambda a, n: memory[a][:n - 1 if partial and a == address else n],
                lambda a, *args: partial or a != code_address,
                images.__getitem__, {131, 149, 158}, 30, 60)
            self.assertFalse(result["known"])
            self.assertIn("short-data: actorState" if partial else "code-identity", result["reason"])

    def test_actor_symbols_outside_resident_region_are_unknown(self):
        original = d.symbol
        for name in ("gOverworldActorSystemState", "ActorSystem_EnsureInitialized"):
            def moved(image, symbol_name, *args):
                address, size, code = original(image, symbol_name, *args)
                return (0x023C0000 if symbol_name == name else address, size, code)
            with self.subTest(symbol=name), patch.object(d, "symbol", moved):
                result = self.observe()
                self.assertFalse(result["known"])
                self.assertIn("outside-resident-region", result["reason"])

    def test_runtime_authenticates_loaded_ids_and_live_code(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        images, memory = self.fixture()
        code = {}
        for file, name in d.CODE:
            address, size, expected = d.symbol(images[file], name, 2)
            code[address] = expected
        s = DevtoolsSession.__new__(DevtoolsSession)
        s.rt = SimpleNamespace(REPO=Path("fixture"), EXECUTED_FRAME_COUNT=60)
        s.completed_frames = 30
        s._authenticate_field_reader_code = lambda *args: True
        memory[0x0200713C] = struct.pack("<I", 0x02100000)
        memory[0x02100000] = struct.pack("<16I", 131, 1, 149, 1, *([0] * 12))
        s.read = lambda address, size: (code[address] if address in code else memory[address])[:size]
        s.packaged_code = lambda address, size: code[address]
        with patch("pathlib.Path.read_bytes", lambda path: images[path.name]):
            self.assertTrue(s._field_cleanup_diagnostics()["known"])
            first = next(iter(code))
            good_read = s.read
            s.read = lambda address, size: bytes([255]) * size if address == first else good_read(address, size)
            result = s._field_cleanup_diagnostics()
            self.assertFalse(result["known"])
            self.assertIn("live/package/ELF", result["reason"])


if __name__ == "__main__":
    unittest.main()

"""Host boundaries for the disposable worker. These are not game proof."""

from pathlib import Path
from types import SimpleNamespace
import ast
import inspect
import struct
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import (
    Call, DevtoolsFailure, DevtoolsHooks, DevtoolsSession, FieldReturnBridge, PreparedPartyWorkHeap, LINKED_CALLS,
    STOCK_CALLS, STOCK_CALLBACKS, _crypt, _elf_function_extent, actor_identity_checks, decode_party, integer,
    native_callback_cpu_observation, owned_path,
    native_trampoline_code, TRAMPOLINE_BYTES, TRAMPOLINE_GUARD, PARTY_WORK_HEAP_SITES,
)
from tools.overworld.test_devtools_trace import NativeRing, natives, notices
from tools.overworld.devtools_engine import Hooks, SUBSTRUCT_OFFSETS


class Registers:
    def __init__(self):
        for i in range(15):
            setattr(self, f"r{i}", i + 10)
        self.r13, self.r14, self.cpsr, self.pc = 0x027E3D00, 0x02001001, 0x3F, 0x02000000
        self.spsr = 0xA000003F

    sp = property(lambda self: self.r13, lambda self, value: setattr(self, "r13", value))
    lr = property(lambda self: self.r14, lambda self, value: setattr(self, "r14", value))


class SignedRegisters(Registers):
    """Match pydesmume's signed c_int32 readback for high register bits."""
    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if (name in ("cpsr", "spsr") or name.startswith("r") and name[1:].isdigit()) and value & 0x80000000:
            return (value & 0xFFFFFFFF) - 0x100000000
        return value


class BridgeFixture:
    """A native ABI/control model, not an ARM instruction emulator."""
    def __init__(self, *, corrupt=False, timeout=False, result=1, stale_ldr=True, skip_entry=False,
                 bootstrap=False, poll_lr=None):
        self.regs, self.memory, self.hooks = Registers(), {}, {}
        self.regs.r0 = self.field_pointer()
        self.initial = [getattr(self.regs, f"r{i}") for i in range(15)]
        self.initial_cpsr = self.regs.cpsr
        self.corrupt, self.timeout, self.result = corrupt, timeout, result
        self.stale_ldr, self.skip_entry = stale_ldr, skip_entry
        memory = SimpleNamespace(register_arm9=self.regs, register_exec=self.register,
                                 set_next_instruction=lambda value: setattr(self.regs, "pc", value))
        self.emu = SimpleNamespace(memory=memory)
        self.rt = SimpleNamespace(h=SimpleNamespace(set_key_mask=lambda *args: None))
        self.party_getter_hooks = Hooks(self.rt, self.emu)
        self.native_bridge_active = False
        self.native_trampoline_in_use = False
        self.native_heap_generation = 0
        self.memory.update({0x02001000 + index: value for index, value in enumerate(bytes.fromhex("244b254a"))})
        self.write(0x027E3FFC, struct.pack("<I", 0x01FF8000))
        self.started, self.closed, self.steps, self.invocations = False, False, 0, []
        self.thread = {"pointer": 0x021E1000, "id": 0, "state": 1,
                       "stackTop": 0x027E0100, "stackBottom": 0x027E3F00,
                       "topGuard": 0x7BF9DD5B, "bottomGuard": 0xFDDB597D,
                       "irqDepth": 0, "mode": 0x1F}
        self.native_trampoline = {"address": 0x02280000, "bytes": TRAMPOLINE_BYTES,
                                  "code": native_trampoline_code(0x02280000), "lifetime": "field-system-heap11",
                                  "fieldPointer": self.field_pointer(), "heapGeneration": 0}
        self.write(0x02280000, self.native_trampoline["code"])
        self.write(0x02280000 + TRAMPOLINE_BYTES - 16, TRAMPOLINE_GUARD)
        self.native_saved = None
        self.poll_lr, self.bootstrap_calls = poll_lr, []
        self.bootstrap_result = 0x02280000
        if bootstrap:
            self.native_trampoline = None

    def field_pointer(self):
        return 0x02200000

    def require_quiescent(self):
        pass

    def _authenticate_party_work_heap(self):
        pass  # ABI model; real source identity has its own host test below.

    def target(self, name):
        if name not in STOCK_CALLS and name not in LINKED_CALLS:
            raise DevtoolsFailure("invalid-state", "not whitelisted")
        return 0x02300000 if name == "poll" else 0x02301000

    def read(self, address, size):
        return bytes(self.memory.get(address + i, 0) for i in range(size))

    packaged_code = read

    def _native_irq_vector(self):
        return {"address": 0x027E3FFC, "target": struct.unpack("<I", self.read(0x027E3FFC, 4))[0],
                "expectedStockTarget": 0x01FF8000}

    def _native_thread_ownership(self):
        return dict(self.thread)

    def write(self, address, data):
        if not data:
            raise IndexError("pydesmume cannot write an empty slice")
        self.memory.update({address + i: value for i, value in enumerate(data)})

    def register(self, address, callback):
        if callback is None:
            self.hooks.pop(address, None)
        else:
            self.hooks[address] = callback

    def cycle(self, frames):
        self.steps += frames
        if not self.started:
            self.started = True
            self.hooks[0x02300000](0x02300000, 2)
            if self.poll_lr is not None:
                self.regs.lr = self.poll_lr
                self.initial[14] = self.poll_lr
            if 0x02001000 in self.hooks:
                self.hooks[0x02001000](0x02001000, 2)
            if self.stale_ldr:
                self.regs.r3 = 0x2405D001
        elif not self.timeout:
            if self.native_trampoline is None:
                self.hooks[0x02301000](0x02301000, 2)
                self.bootstrap_calls.append({"args": [self.regs.r0, self.regs.r1],
                                             "sp": self.regs.sp, "lr": self.regs.lr,
                                             "cpsr": self.regs.cpsr})
                self.regs.r0, self.regs.lr = self.bootstrap_result, 0x0201AB01
                self.hooks[0x02001000](0x02001000, 2)
                if self.stale_ldr:
                    self.regs.r3 = 0x2405D001
                return
            base = self.native_trampoline["address"]
            control = base + 0x100
            if self.native_saved is None:
                self.native_saved = [getattr(self.regs, f"r{i}") & 0xFFFFFFFF for i in range(15)]
                self.native_saved[3] = struct.unpack("<I", self.read(control + 44, 4))[0]
                self.native_cpsr = struct.unpack("<I", self.read(control + 48, 4))[0]
                self.regs.sp -= 80
                self.regs.r4, self.regs.r5 = self.native_cpsr, control
                self.regs.cpsr &= ~0x20
                self.hooks[base + 0x18](base + 0x18, 4)
            command = struct.unpack("<9I", self.read(control, 36))
            if command[0] == 0:
                self.native_return()
                return
            for index, value in enumerate(command[1:5]):
                setattr(self.regs, f"r{index}", value)
            self.write(self.regs.sp, struct.pack("<4I", *command[5:9]))
            self.regs.lr = base + 0x4C
            self.regs.cpsr |= 0x20
            if not self.skip_entry:
                self.hooks[0x02301000](0x02301000, 2)
            if hasattr(self, "on_callee"):
                self.on_callee()
            self.invocations.append({"registers": [getattr(self.regs, f"r{i}") for i in range(4)],
                                     "stack": self.read(self.regs.sp, 16)})
            self.regs.r0 = self.result
            if self.corrupt:
                self.thread["topGuard"] = 1
            self.write(control + 36, struct.pack("<II", self.result, 1))
            self.regs.cpsr &= ~0x20
            self.hooks[base + 0x18](base + 0x18, 4)
            if struct.unpack("<I", self.read(control, 4))[0] == 0:
                self.native_return()

    def native_return(self):
        for index, value in enumerate(self.native_saved):
            setattr(self.regs, f"r{index}", value)
        self.regs.cpsr = self.native_cpsr
        continuation = struct.unpack("<I", self.read(self.native_trampoline["address"] + 0x134, 4))[0]
        self.regs.pc = continuation & ~1
        self.hooks[continuation & ~1](continuation & ~1, 2)

    def close(self):
        self.closed, self.emu = True, None


class BridgeTests(unittest.TestCase):
    def test_native_bytes_match_independent_armv5_assembly(self):
        assembler, linker, objcopy = (shutil.which("arm-none-eabi-" + name)
                                      for name in ("as", "ld", "objcopy"))
        self.assertTrue(assembler and linker and objcopy, "ARM host tools are required for instruction identity")
        source = """.syntax unified
.cpu arm946e-s
.text
.thumb
bx pc
mov r8, r8
.arm
ldr r3, saved_r3
push {r0-r12, lr}
ldr r4, saved_cpsr
sub sp, sp, #24
ldr r5, control_literal
command_loop:
ldr r12, [r5]
cmp r12, #0
beq finished
ldr r0, [r5, #20]
str r0, [sp]
ldr r0, [r5, #24]
str r0, [sp, #4]
ldr r0, [r5, #28]
str r0, [sp, #8]
ldr r0, [r5, #32]
str r0, [sp, #12]
ldmib r5, {r0-r3}
blx r12
str r0, [r5, #36]
mov r0, #1
str r0, [r5, #40]
b command_loop
finished:
add sp, sp, #24
msr CPSR_f, r4
pop {r0-r12, lr}
ldr pc, continuation
control_literal:
.word control
.org 0x100
control:
.space 44
saved_r3:
.word 0
saved_cpsr:
.word 0
continuation:
.word 0
"""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            assembly, obj, elf, binary = (folder / name for name in ("thunk.s", "thunk.o", "thunk.elf", "thunk.bin"))
            assembly.write_text(source)
            subprocess.run([assembler, str(assembly), "-o", str(obj)], check=True, capture_output=True)
            subprocess.run([linker, "-Ttext=0x02280000", str(obj), "-o", str(elf)], check=True, capture_output=True)
            subprocess.run([objcopy, "-O", "binary", str(elf), str(binary)], check=True, capture_output=True)
            expected = binary.read_bytes()[:0x70]
        self.assertEqual(native_trampoline_code(0x02280000), expected)
        self.assertEqual(len(TRAMPOLINE_GUARD), 16)
        # These prior/wrong-mode forms must not become the accepted template.
        for offset, opcode in ((0x48, 0xE12FFF1C), (0x60, 0xE129F004), (0x68, 0xE12FFF1E)):
            mutant = bytearray(expected)
            struct.pack_into("<I", mutant, offset, opcode)
            self.assertNotEqual(native_trampoline_code(0x02280000), bytes(mutant))

    def test_bootstrap_uses_native_stack_and_separate_continuation(self):
        fixture = BridgeFixture(bootstrap=True, poll_lr=0x023BD897)
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
            return "complete"
        result = FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.bootstrap_calls, [{"args": [11, 1536], "sp": fixture.initial[13],
                                                   "lr": 0x02001001, "cpsr": fixture.initial_cpsr}])
        self.assertEqual(result["value"], "complete")
        self.assertEqual(fixture.regs.lr, 0x023BD897)
        self.assertEqual(fixture.regs.pc, 0x02001000)
        self.assertEqual([getattr(fixture.regs, f"r{i}") for i in range(15)], fixture.initial)
        self.assertEqual(result["trampoline"]["heapId"], 11)
        self.assertFalse(fixture.closed)

    def test_existing_block_preserves_inner_lr_but_returns_to_outer_caller(self):
        fixture = BridgeFixture(poll_lr=0x023BD897)
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.regs.lr, 0x023BD897)
        self.assertEqual(fixture.regs.pc, 0x02001000)
        self.assertEqual(fixture.bootstrap_calls, [])

    def test_failed_bootstrap_keeps_actual_return_before_endpoint_changes(self):
        fixture = BridgeFixture(bootstrap=True)
        fixture.bootstrap_result = 0
        cycle = fixture.cycle
        def changed_endpoint(frames):
            cycle(frames)
            if fixture.bootstrap_calls:
                fixture.regs.r0 = 0x0227C32A  # later native work must not replace first failure
        fixture.cycle = changed_endpoint
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaisesRegex(DevtoolsFailure, "heap 11, pointer 0x00000000") as caught:
            FieldReturnBridge(fixture).run(recipe)
        bootstrap = caught.exception.details["bootstrap"]
        self.assertEqual(bootstrap["returnValue"], 0)
        self.assertEqual(bootstrap["requestedArguments"], [11, 1536])
        self.assertEqual(bootstrap["returnBoundary"], "observed-allocator-return-before-validation")
        self.assertEqual(caught.exception.details["cpu"]["registers"]["r0"], 0x0227C32A)
        self.assertEqual(fixture.invocations, [])
        self.assertTrue(fixture.closed)

    def test_two_commands_reuse_one_owned_heap_allocation(self):
        fixture = BridgeFixture(bootstrap=True, poll_lr=0x023BD897)
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        first = FieldReturnBridge(fixture).run(recipe)
        fixture.started, fixture.native_saved = False, None
        fixture.regs.lr = 0x02001001  # next natural call entry, before Poll's inner BL
        second = FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(len(fixture.bootstrap_calls), 1)
        self.assertEqual(first["trampoline"], second["trampoline"])
        self.assertEqual(len(fixture.invocations), 2)
        self.assertEqual(fixture.regs.lr, 0x023BD897)
        self.assertEqual(fixture.regs.pc, 0x02001000)

    def test_changed_owned_code_or_guard_fails_closed(self):
        for offset in (0x48, TRAMPOLINE_BYTES - 1):
            with self.subTest(offset=offset):
                fixture = BridgeFixture()
                address = fixture.native_trampoline["address"] + offset
                fixture.memory[address] ^= 1
                def recipe(_scratch):
                    yield Call("set_mon", (1, 2, 3))
                with self.assertRaisesRegex(DevtoolsFailure, "identity changed") as caught:
                    FieldReturnBridge(fixture).run(recipe)
                self.assertTrue(caught.exception.fatal)
                self.assertTrue(fixture.closed)
                self.assertEqual(fixture.invocations, [])

    def test_changed_field_or_heap_owner_rejects_even_unchanged_code(self):
        for field in (True, False):
            fixture = BridgeFixture()
            if field:
                fixture.native_trampoline["fieldPointer"] += 4
            else:
                fixture.native_heap_generation += 1
            def recipe(_scratch):
                yield Call("set_mon", (1, 2, 3))
            with self.assertRaisesRegex(DevtoolsFailure, "owner changed"):
                FieldReturnBridge(fixture).run(recipe)
            self.assertEqual(fixture.invocations, [])
            self.assertTrue(fixture.closed)

    def test_field_heap_teardown_expires_buffer_but_unrelated_heap_does_not(self):
        fixture = BridgeFixture()
        original = fixture.native_trampoline
        fixture.regs.r0 = 4
        DevtoolsSession._observe_heap_destroy(fixture)
        self.assertIs(fixture.native_trampoline, original)
        fixture.regs.r0 = 11
        DevtoolsSession._observe_heap_destroy(fixture)
        self.assertIsNone(fixture.native_trampoline)
        self.assertEqual(fixture.native_heap_generation, 1)
        fixture.native_trampoline_in_use = True
        with self.assertRaises(DevtoolsFailure) as caught:
            DevtoolsSession._observe_heap_destroy(fixture)
        self.assertTrue(caught.exception.fatal)

    def test_heap_teardown_after_native_return_in_same_cycle_keeps_completed_receipt(self):
        fixture = BridgeFixture()
        cycle = fixture.cycle
        def finish_then_destroy(frames):
            cycle(frames)
            if fixture.native_saved is not None:
                self.assertTrue(fixture.native_bridge_active)
                self.assertFalse(fixture.native_trampoline_in_use)
                fixture.regs.r0 = 11
                DevtoolsSession._observe_heap_destroy(fixture)
        fixture.cycle = finish_then_destroy
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        result = FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(result["trampoline"]["heapId"], 11)
        self.assertEqual(result["trampoline"]["heapGeneration"], 0)
        self.assertEqual(fixture.native_heap_generation, 1)
        self.assertIsNone(fixture.native_trampoline)
        self.assertFalse(fixture.closed)

    def test_bridge_does_not_assign_host_sp_or_cpsr(self):
        tree = ast.parse(inspect.getsource(FieldReturnBridge))
        writes = [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                  and isinstance(node.ctx, ast.Store) and node.attr in ("sp", "cpsr", "r13")]
        self.assertEqual(writes, [])

    def test_private_return_observer_native_registrations_stay_bounded(self):
        fixture = BridgeFixture()
        registrations = []
        def register(address, callback):
            registrations.append((address, callback is not None))
            fixture.register(address, callback)
        fixture.emu.memory.register_exec = register
        hooks = DevtoolsHooks(fixture.rt, fixture.emu)
        seen = []
        hooks.observe_call(0x02301000, lambda: True, lambda _context: seen.append(hooks.current_callback))
        for _ in range(3000):
            fixture.hooks[0x02301000](0x02301000, 2)
            fixture.hooks[0x02001000](0x02001000, 2)
        self.assertEqual(len(seen), 3000)
        self.assertEqual(registrations, [(0x02301000, True), (0x02001000, True)])
        self.assertEqual(seen[-1], {"address": 0x02001000, "size": 2})
        self.assertIsNone(hooks.current_callback)
        hooks.close()
        self.assertEqual(fixture.hooks, {})
        self.assertEqual(registrations[-2:], [(0x02301000, False), (0x02001000, False)])

    def test_callback_cpu_receipt_keeps_actual_event_and_both_cpu_positions(self):
        fixture = BridgeFixture()
        fixture.party_getter_hooks = DevtoolsHooks(fixture.rt, fixture.emu)
        fixture.regs.pc, fixture.regs.cpsr = 0x02000008, 0x92
        fixture.emu.memory.register_arm7 = SimpleNamespace(pc=0x01FF81A8, cpsr=0x92)
        fixture.emu.memory.get_next_instruction = lambda: 0x02000004
        seen = []
        fixture.party_getter_hooks.add(0x01FF81A0,
            lambda: seen.append(native_callback_cpu_observation(fixture, 0x01FF81A0)))
        fixture.hooks[0x01FF81A0](0x01FF81A0, 4)
        receipt = seen[0]
        self.assertEqual(receipt["actualCallback"], {"address": 0x01FF81A0, "size": 4})
        self.assertEqual(receipt["arm7"]["executionAddressFromPc"], 0x01FF81A0)
        self.assertEqual(receipt["arm9"]["executionAddressFromPc"], 0x02000000)
        self.assertEqual(receipt["arm9"]["nextInstruction"], 0x02000004)

    def test_irq_switch_retains_exact_chosen_and_changed_restore_context(self):
        fixture = BridgeFixture()
        chosen, wrong = 0x021E3864, 0x021E3000
        def thread(pointer, cpsr):
            data = bytearray(0x98)
            struct.pack_into("<I", data, 0, cpsr)
            struct.pack_into("<4I", data, 0x38, 0x021E3700, 0, 0x020DD004, 0x021E3780)
            struct.pack_into("<I", data, 0x64, 1)
            struct.pack_into("<I", data, 0x6C, 3)
            struct.pack_into("<II", data, 0x90, 0x021E3500, 0x021E3800)
            fixture.write(pointer, data)
        thread(chosen, 0x1F)
        thread(wrong, 0x040000A4)
        fixture._native_target_is_mapped_code = lambda address: 0x02000000 <= address < 0x02110000
        fixture._native_thread_snapshot = lambda pointer: DevtoolsSession._native_thread_snapshot(fixture, pointer)
        fixture._native_checkpoint_points = lambda: [("irq-thread-chosen", 0x01FF8120),
            ("irq-thread-svc-pop", 0x01FF8178), ("irq-thread-restore", 0x01FF8188),
            ("irq-dispatch", 0x01FF804C)]
        cycle = fixture.cycle
        def instrumented(frames):
            cycle(frames)
            if fixture.steps == 1:
                original_r0, original_r1 = fixture.regs.r0, fixture.regs.r1
                sp = fixture.regs.sp
                fixture.regs.r1 = chosen
                fixture.hooks[0x01FF8120](0x01FF8120, 4)
                fixture.regs.sp = 0x027E3FB8
                fixture.write(fixture.regs.sp, struct.pack("<I", wrong))
                fixture.hooks[0x01FF8178](0x01FF8178, 4)
                fixture.regs.r1 = wrong
                fixture.hooks[0x01FF8188](0x01FF8188, 4)
                fixture.regs.sp = sp
                fixture.regs.r0 = 0x02001000
                for _ in range(40):
                    fixture.hooks[0x01FF804C](0x01FF804C, 4)
                fixture.regs.r0, fixture.regs.r1 = original_r0, original_r1
        fixture.cycle = instrumented
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        result = FieldReturnBridge(fixture).run(recipe)
        bundle = result["firstInvalidThreadSwitch"]
        self.assertTrue(bundle["chosen"]["chosenThread"]["validContext"])
        self.assertEqual(bundle["chosen"]["chosenThread"]["pointer"], chosen)
        self.assertEqual(bundle["svcPop"]["savedChosenPointer"], wrong)
        self.assertFalse(bundle["restore"]["restoreThread"]["validContext"])
        self.assertEqual(bundle["restore"]["restoreThread"]["cpsr"], 0x040000A4)
        self.assertFalse(bundle["sameChosenPointer"])
        self.assertFalse(bundle["sameChosenContext"])
        self.assertEqual(len(result["nativeCheckpoints"]), 32)

    def test_sdk_thread_reader_uses_real_context_and_stack_field_offsets(self):
        fixture = BridgeFixture()
        fixture.native_thread_info_address = 0x021E16A0
        pointer, top, bottom = 0x021E1000, 0x027E0100, 0x027E3F00
        fixture.write(fixture.native_thread_info_address, struct.pack("<HHIII", 0, 0, pointer, pointer, 0))
        data = bytearray(0x98)
        struct.pack_into("<I", data, 0x64, 1)
        struct.pack_into("<I", data, 0x6C, 7)
        struct.pack_into("<II", data, 0x90, top, bottom)
        fixture.write(pointer, data)
        fixture.write(top, struct.pack("<I", 0x7BF9DD5B))
        fixture.write(bottom - 4, struct.pack("<I", 0xFDDB597D))
        actual = DevtoolsSession._native_thread_ownership(fixture)
        self.assertEqual(actual, {**fixture.thread, "id": 7})

    def test_changed_sdk_thread_on_final_return_is_not_restored_or_resumed(self):
        fixture = BridgeFixture()
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
            fixture.thread["pointer"] += 0x100
        with self.assertRaises(DevtoolsFailure) as caught:
            FieldReturnBridge(fixture).run(recipe)
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(fixture.closed)
        self.assertIn("owning SDK thread", str(caught.exception))
        self.assertFalse(caught.exception.details["registersRestored"])

    def test_bridge_rejects_stack_outside_current_sdk_thread_before_native_call(self):
        fixture = BridgeFixture()
        fixture.thread["stackBottom"] = fixture.initial[13] - 4
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaisesRegex(DevtoolsFailure, "thread stack"):
            FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.invocations, [])

    def test_bridge_does_not_restore_bytes_below_its_private_call_frame(self):
        fixture = BridgeFixture()
        address = fixture.initial[13] - 0x1000
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
            fixture.write(address, b"native update")
        FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.read(address, 13), b"native update")

    def test_fixed_irq_vector_reader_retains_unexpected_target_without_writes(self):
        reads = []
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        def read(emu, address, size):
            reads.append((emu, address, size))
            return struct.pack("<I", 0x01FF8058)
        session.rt = SimpleNamespace(actor_memory_read=read)
        value = session._native_irq_vector()
        self.assertEqual(reads, [(session.emu, 0x027E3FFC, 4)])
        self.assertEqual(value["target"], 0x01FF8058)
        self.assertEqual(value["expectedStockTarget"], 0x01FF8000)

    def test_linked_dependency_extent_requires_full_typed_unique_function(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "linked.o"
            data = bytearray(512)
            data[:7] = b"\x7fELF\x01\x01\x01"
            struct.pack_into("<I", data, 32, 64)
            struct.pack_into("<HH", data, 46, 40, 3)
            struct.pack_into("<10I", data, 104, 0, 2, 0, 0, 256, 16, 2, 0, 4, 16)
            struct.pack_into("<10I", data, 144, 0, 3, 0, 0, 320, 18, 0, 0, 1, 0)
            data[320:338] = b"\0CreateBoxMonData\0\0"
            struct.pack_into("<IIIBBH", data, 256, 1, 0x023DC091, 584, 0x12, 0, 1)
            path.write_bytes(data)
            self.assertEqual(_elf_function_extent(path, "CreateBoxMonData"), (0x023DC090, 584))
            struct.pack_into("<I", data, 264, 0)
            path.write_bytes(data)
            with self.assertRaisesRegex(DevtoolsFailure, "typed extent"):
                _elf_function_extent(path, "CreateBoxMonData")
            with self.assertRaisesRegex(DevtoolsFailure, "not unique"):
                _elf_function_extent(path, "Absent")

    def test_irq_return_records_saved_resume_and_spsr_without_changing_frame(self):
        fixture = BridgeFixture()
        fixture.regs.__class__ = SignedRegisters
        fixture._native_checkpoint_points = lambda: [("irq-return-if-idle", 0x01FF80B4)]
        fixture._native_target_is_mapped_code = lambda address: address == 0xFFFF0290
        words = [0xFFFF0290, 11, 12, 13, 14, 15, 0x0206E114]
        data = struct.pack("<7I", *words)
        fixture.write(0x027E3F60, data)
        cycle = fixture.cycle
        def instrumented(frames):
            cycle(frames)
            if fixture.steps == 1:
                saved = fixture.regs.sp, fixture.regs.cpsr
                fixture.regs.sp, fixture.regs.cpsr = 0x027E3F60, 0x60000092
                fixture.hooks[0x01FF80B4](0x01FF80B4, 4)
                fixture.regs.sp, fixture.regs.cpsr = saved
        fixture.cycle = instrumented
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        result = FieldReturnBridge(fixture).run(recipe)
        checkpoint = result["nativeCheckpoints"][0]
        self.assertEqual(checkpoint["spsr"], 0xA000003F)
        self.assertEqual(checkpoint["irqStackWords"], words)
        self.assertEqual(checkpoint["savedInterruptedLink"], 0x0206E114)
        self.assertEqual(checkpoint["savedInterruptedResume"], 0x0206E110)
        self.assertEqual(checkpoint["irqVector"]["target"], 0x01FF8000)
        self.assertEqual(fixture.read(0x027E3F60, 28), data)
        self.assertEqual(fixture.regs.spsr & 0xFFFFFFFF, 0xA000003F)
        self.assertIsNone(result["firstBadCheckpoint"])

    def test_first_bad_irq_checkpoint_survives_bounded_trace_rollover(self):
        fixture = BridgeFixture()
        fixture._native_checkpoint_points = lambda: [("irq-dispatch", 0x01FF804C),
                                                     ("create-box-mon-entry", 0x023DC090)]
        fixture._native_target_is_mapped_code = lambda address: address == 0x02001001
        cycle = fixture.cycle
        def instrumented(frames):
            cycle(frames)
            if fixture.steps == 1:
                original_r0 = fixture.regs.r0
                fixture.hooks[0x023DC090](0x023DC090, 2)
                for index in range(40):
                    fixture.regs.r0 = 0x021E3A28 if index == 0 else 0x02001001
                    fixture.hooks[0x01FF804C](0x01FF804C, 4)
                fixture.regs.r0 = original_r0
        fixture.cycle = instrumented
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        result = FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(result["checkpointCount"], 41)
        self.assertEqual(len(result["nativeCheckpoints"]), 32)
        self.assertEqual(result["firstBadCheckpoint"]["target"], 0x021E3A28)
        self.assertFalse(result["firstBadCheckpoint"]["targetInMappedCode"])
        self.assertEqual(result["firstCreateBoxEntry"]["address"], 0x023DC090)
        self.assertEqual(result["firstCreateBoxEntry"]["stackArguments"], [0, 0, 0, 0])
        self.assertEqual(fixture.hooks, {})

    def test_box_internal_call_return_survives_irq_trace_rollover(self):
        fixture = BridgeFixture(timeout=True)
        fixture._native_checkpoint_points = lambda: [("create-box-internal-species-name-call", 0x023DC14A),
            ("create-box-internal-species-name-return", 0x023DC14E),
            ("create-box-internal-level-exp-call", 0x023DC154), ("irq-dispatch", 0x01FF804C)]
        fixture._native_target_is_mapped_code = lambda _address: True
        cycle = fixture.cycle
        def instrumented(frames):
            cycle(frames)
            if fixture.steps == 1:
                for address in (0x023DC14A, 0x023DC14E, 0x023DC154):
                    fixture.hooks[address](address, 2)
                for _ in range(40):
                    fixture.hooks[0x01FF804C](0x01FF804C, 4)
        fixture.cycle = instrumented
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaises(DevtoolsFailure) as caught:
            FieldReturnBridge(fixture).run(recipe)
        detail = caught.exception.details
        self.assertEqual(detail["boxCallBoundaryCount"], 3)
        self.assertEqual([item["kind"] for item in detail["boxCallBoundaries"]], [
            "create-box-internal-species-name-call", "create-box-internal-species-name-return",
            "create-box-internal-level-exp-call"])
        self.assertEqual(len(detail["nativeCheckpoints"]), 32)
        self.assertTrue(fixture.closed)

    def test_exp_probe_retains_null_allocation_and_archive_destination_on_owned_stack(self):
        fixture = BridgeFixture()
        fixture._native_checkpoint_points = lambda: [("create-box-internal-level-exp-call", 0x023DC154),
            ("level-exp-internal-allocate-return", 0x0206FD50),
            ("level-exp-internal-archive-call", 0x0206FD28)]
        def on_callee():
            old_sp = fixture.regs.sp
            fixture.regs.sp = old_sp - 64
            fixture.hooks[0x023DC154](0x023DC154, 2)
            fixture.regs.r0 = 0
            fixture.hooks[0x0206FD50](0x0206FD50, 2)  # wrong stack: ignore
            fixture.regs.sp -= 24
            fixture.hooks[0x0206FD50](0x0206FD50, 2)
            fixture.regs.sp -= 16
            fixture.regs.r1, fixture.regs.r2 = 3, 4
            fixture.hooks[0x0206FD28](0x0206FD28, 2)
            fixture.regs.sp = old_sp
        fixture.on_callee = on_callee
        def recipe(_scratch):
            yield Call("create_mon", (0x02210000, 56, 10, 32, 1, 99, 0, 0))
        result = FieldReturnBridge(fixture).run(recipe)
        points = result["boxCallBoundaries"]
        self.assertEqual(len(points), 3)
        self.assertEqual(points[1]["allocatedPointer"], 0)
        self.assertEqual((points[2]["destination"], points[2]["archiveId"], points[2]["memberId"]), (0, 3, 4))

    def test_missing_native_free_is_fatal_even_with_handled_recipe_error(self):
        fixture = BridgeFixture()
        fixture.prepared = True
        original = PreparedPartyWorkHeap.__init__
        def missed_free(adapter, session, state):
            original(adapter, session, state)
            adapter.receipts.append({"released": False, "allocation": 0x02220000})
        def recipe(_scratch):
            yield Call("create_mon", (0x02210000, 56, 10, 32, 1, 99, 0, 0))
            raise DevtoolsFailure("invalid-hp", "handled rejection")
        with patch.object(PreparedPartyWorkHeap, "__init__", missed_free):
            with self.assertRaisesRegex(DevtoolsFailure, "was not freed") as caught:
                FieldReturnBridge(fixture).run(recipe, prepared_party_work_heap=True)
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(fixture.closed)

    def test_moveset_probe_keeps_exact_164_byte_null_allocation_and_load_destination(self):
        fixture = BridgeFixture()
        fixture._native_checkpoint_points = lambda: [("create-box-internal-moveset-call", 0x023DC224),
            ("moveset-internal-allocate-return", 0x020712E6), ("moveset-internal-load-call", 0x0207131A)]
        def on_callee():
            old_sp = fixture.regs.sp
            fixture.regs.sp = old_sp - 64
            fixture.hooks[0x023DC224](0x023DC224, 2)
            fixture.regs.sp -= 32
            fixture.regs.r0 = 0
            fixture.hooks[0x020712E6](0x020712E6, 2)
            fixture.regs.r0, fixture.regs.r1, fixture.regs.r2 = 56, 0, 0
            fixture.hooks[0x0207131A](0x0207131A, 2)
            fixture.regs.sp = old_sp
        fixture.on_callee = on_callee
        def recipe(_scratch):
            yield Call("create_mon", (0x02210000, 56, 10, 32, 1, 99, 0, 0))
        result = FieldReturnBridge(fixture).run(recipe)
        points = result["boxCallBoundaries"]
        self.assertEqual(points[1]["allocatedPointer"], 0)
        self.assertEqual((points[2]["species"], points[2]["form"], points[2]["destination"]), (56, 0, 0))

    def test_unproven_owned_allocation_cleanup_closes_disposable_core(self):
        fixture = BridgeFixture()
        fixture.native_allocations = {0x02210000: {"purpose": "temporary-party-pokemon", "bytes": 236}}
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
            raise DevtoolsFailure("cleanup-failed", "native cleanup could not be dispatched")
        with self.assertRaises(DevtoolsFailure) as caught:
            FieldReturnBridge(fixture).run(recipe)
        self.assertTrue(fixture.closed)
        self.assertTrue(caught.exception.fatal)
        self.assertIn(0x02210000, caught.exception.details["ownedAllocations"])

    def test_initial_hook_failure_clears_partial_registration_and_bridge_mode(self):
        fixture = BridgeFixture()
        def fail_after_registration(address, callback):
            fixture.register(address, callback)
            if callback is not None:
                raise RuntimeError("registration failed after binding")
        fixture.emu.memory.register_exec = fail_after_registration
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaisesRegex(RuntimeError, "registration failed"):
            FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.hooks, {})
        self.assertEqual(fixture.party_getter_hooks.callbacks, {})
        self.assertFalse(fixture.native_bridge_active)
        self.assertFalse(fixture.closed)
        self.assertEqual(fixture.steps, 0)

    def test_signed_native_registers_compare_as_32_bit_patterns(self):
        fixture = BridgeFixture(result=0xFFFFFFFF)
        fixture.regs.__class__ = SignedRegisters
        fixture.regs.cpsr = 0xA000003F
        def recipe(_scratch):
            result = yield Call("transition", (1, 33, -1, 585, 406, 1, 6))
            return result
        result = FieldReturnBridge(fixture).run(recipe)
        call = result["calls"][0]
        self.assertEqual(call["entryArguments"], [1, 33, 0xFFFFFFFF, 585, 406, 1, 6])
        self.assertEqual(call["entryCpsr"], 0xA000003F)
        self.assertEqual(call["returnValue"], 0xFFFFFFFF)
        self.assertEqual(result["value"], 0xFFFFFFFF)
        self.assertEqual(fixture.regs.cpsr & 0xFFFFFFFF, 0xA000003F)
        self.assertFalse(fixture.closed)

    def test_native_arguments_and_full_return_restore(self):
        fixture = BridgeFixture()
        def recipe(scratch):
            fixture.write(scratch, b"temporary buffer")
            value = yield Call("transition", (1, 2, -1, 4, 5, 6, 7))
            self.assertEqual(value, 1)
            yield Call("set_mon", (9, 10, scratch))
            return {"complete": True}
        result = FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(result["value"], {"complete": True})
        self.assertEqual(len(result["calls"]), 2)
        self.assertEqual(fixture.invocations[0]["registers"], [1, 2, 0xFFFFFFFF, 4])
        self.assertEqual(struct.unpack("<3I", fixture.invocations[0]["stack"][:12]), (5, 6, 7))
        self.assertEqual([getattr(fixture.regs, f"r{i}") for i in range(15)], fixture.initial)
        self.assertEqual(fixture.regs.cpsr, fixture.initial_cpsr)
        self.assertFalse(any(value for address, value in fixture.memory.items()
                             if 0x027E0000 <= address < fixture.initial[13] - 80))
        self.assertEqual(fixture._native_irq_vector()["target"], 0x01FF8000)
        self.assertEqual(fixture.hooks, {})
        self.assertFalse(fixture.closed)
        self.assertEqual(result["calls"][0]["entryArguments"], [1, 2, 0xFFFFFFFF, 4, 5, 6, 7])
        self.assertEqual(result["calls"][1]["entryArguments"][:2], [9, 10])
        ownership = result["stackOwnership"]
        self.assertEqual(ownership["hostRestoredFrameBytes"], 0)
        self.assertEqual(ownership["nativeFrameBytes"], 80)
        self.assertEqual(ownership["callSp"] + 80, fixture.initial[13])
        self.assertEqual(ownership["scratchBytes"], 268)

    def test_expected_native_rejection_restores_at_completed_return(self):
        fixture = BridgeFixture(result=0)
        def recipe(_scratch):
            result = yield Call("set_mon", (1, 2, 3))
            if not result:
                raise DevtoolsFailure("spawn-rejected", "native rejection")
        with self.assertRaisesRegex(DevtoolsFailure, "native rejection") as caught:
            FieldReturnBridge(fixture).run(recipe)
        self.assertFalse(fixture.closed)
        self.assertEqual(caught.exception.details["bridge"]["calls"][0]["routine"], "set_mon")
        self.assertTrue(caught.exception.details["bridge"]["registersRestored"])
        self.assertEqual([getattr(fixture.regs, f"r{i}") for i in range(15)], fixture.initial)

    def test_final_callee_stack_guard_is_checked_before_restore(self):
        fixture = BridgeFixture(corrupt=True)
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaises(DevtoolsFailure) as caught:
            FieldReturnBridge(fixture).run(recipe)
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(fixture.closed)

    def test_interrupted_callee_closes_without_fake_restore(self):
        fixture = BridgeFixture(timeout=True)
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaises(DevtoolsFailure) as caught:
            FieldReturnBridge(fixture).run(recipe)
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(fixture.closed)
        self.assertEqual(fixture.steps, 180)
        self.assertFalse(caught.exception.details["dispatchPending"])
        cpu = caught.exception.details["cpu"]
        self.assertEqual(cpu["boundary"], "failed-native-call-before-core-close")
        self.assertEqual(cpu["registers"]["pc"], 0x02280000)
        self.assertEqual(cpu["registers"]["sp"], fixture.initial[13])
        self.assertEqual(cpu["instructionSet"], "Thumb")
        self.assertIn("instructionBytes", cpu)

    def test_unknown_routine_is_not_called(self):
        fixture = BridgeFixture()
        def recipe(_scratch):
            yield Call("user-address", (1, 2, 3))
        with self.assertRaises(DevtoolsFailure):
            FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.invocations, [])
        self.assertFalse(fixture.closed)

    def test_wrong_argument_count_does_not_call(self):
        fixture = BridgeFixture()
        def recipe(_scratch):
            yield Call("set_mon", (1, 2))
        with self.assertRaisesRegex(DevtoolsFailure, "argument count"):
            FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.invocations, [])

    def test_entry_setup_runs_before_and_preserves_existing_observers(self):
        fixture = BridgeFixture()
        observed = []
        fixture.party_getter_hooks.add(0x02301000, lambda: observed.append(fixture.regs.r3))
        def recipe(_scratch):
            yield Call("transition", (1, 2, 3, 585, 406, 1, 6))
        FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(observed, [585])
        self.assertIn(0x02301000, fixture.hooks)
        self.assertEqual(len(fixture.party_getter_hooks.callbacks[0x02301000]), 1)
        self.assertFalse(fixture.native_bridge_active)

    def test_missing_callee_entry_never_looks_like_a_completed_call(self):
        fixture = BridgeFixture(skip_entry=True)
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaises(DevtoolsFailure) as caught:
            FieldReturnBridge(fixture).run(recipe)
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(fixture.closed)

    def test_unreviewed_return_instruction_rejected_before_dispatch(self):
        fixture = BridgeFixture()
        fixture.memory[0x02001000] = 0
        def recipe(_scratch):
            yield Call("set_mon", (1, 2, 3))
        with self.assertRaisesRegex(DevtoolsFailure, "literal-load seam"):
            FieldReturnBridge(fixture).run(recipe)
        self.assertEqual(fixture.invocations, [])
        self.assertFalse(fixture.closed)


class FreshObservationTests(unittest.TestCase):
    def fixture(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.completed_frames, session.sample_error = 40, None
        session.latest_frame = {"frame": 40, "matches": True}
        session.snapshot = lambda: dict(session.latest_frame)
        session._control_diagnostics = lambda: {"taskPointer": 123, "boundary": "paused-native-cycle-end"}
        return session

    def test_command_cannot_pass_from_old_matching_snapshot(self):
        session = self.fixture()
        count = [0]
        def cycle(_frames):
            count[0] += 1
            if count[0] == 3:
                session.completed_frames = 41
                session.latest_frame = {"frame": 41, "matches": True}
        session.cycle = cycle
        value = session._wait_new_frame(40, lambda frame: frame["matches"], native_limit=5,
                                        code="readback", message="missing")
        self.assertEqual(count[0], 3)
        self.assertEqual(value["frame"], 41)

    def test_new_nonmatching_frame_cannot_pass_and_timeout_keeps_diagnostics(self):
        session = self.fixture()
        def cycle(_frames):
            session.completed_frames += 1
            session.latest_frame = {"frame": session.completed_frames, "matches": False}
        session.cycle = cycle
        with self.assertRaises(DevtoolsFailure) as caught:
            session._wait_new_frame(40, lambda frame: frame["matches"], native_limit=3,
                                    code="readback", message="missing")
        self.assertEqual(caught.exception.details["latestCompleteFrame"]["frame"], 43)
        self.assertEqual(caught.exception.details["nativeEndpoint"]["taskPointer"], 123)

    def test_failed_sampler_is_not_treated_as_timeout_or_success(self):
        session = self.fixture()
        def cycle(_frames):
            session.sample_error = "checksum mismatch"
        session.cycle = cycle
        with self.assertRaises(DevtoolsFailure) as caught:
            session._wait_new_frame(40, lambda _frame: True, native_limit=3, code="timeout", message="missing")
        self.assertEqual(caught.exception.code, "observation-failed")

    def test_field_required_predicate_waits_without_consuming_absence(self):
        session = self.fixture()
        rows, calls = [], []
        def cycle(_frames):
            session.completed_frames += 1
            session.latest_frame = {"frame": session.completed_frames, "fieldAvailable": len(rows) == 2}
            if session.latest_frame["fieldAvailable"]:
                session.latest_frame["party"] = [{"hp": 20}]
            rows.append(dict(session.latest_frame))
        session.cycle = cycle
        def predicate(value):
            calls.append(value["frame"])
            return True  # The party-edit caller needs a fresh full snapshot.
        value = session._wait_new_frame(40, predicate, native_limit=3, code="readback", message="missing")
        self.assertEqual(value["party"], [{"hp": 20}])
        self.assertEqual(calls, [43])
        self.assertEqual([row["fieldAvailable"] for row in rows], [False, False, True])

    def test_absence_timeout_is_bounded_and_does_not_call_field_predicate(self):
        session = self.fixture()
        calls = []
        def cycle(_frames):
            session.completed_frames += 1
            session.latest_frame = {"frame": session.completed_frames, "fieldAvailable": False}
        session.cycle = cycle
        with self.assertRaises(DevtoolsFailure) as caught:
            session._wait_new_frame(40, lambda value: calls.append(value["context"]),
                                    native_limit=3, code="readback", message="field unavailable")
        self.assertEqual(caught.exception.code, "readback")
        self.assertEqual(caught.exception.details["latestCompleteFrame"], {"frame": 43, "fieldAvailable": False})
        self.assertEqual(calls, [])

    def test_malformed_present_field_predicate_is_not_silently_skipped(self):
        session = self.fixture()
        session.cycle = lambda _frames: setattr(session, "latest_frame", {"frame": 41, "fieldAvailable": True})
        with self.assertRaises(KeyError):
            session._wait_new_frame(40, lambda value: value["context"]["mapId"] == 33,
                                    native_limit=3, code="readback", message="missing")

    def test_identity_mismatch_is_named_without_blessing_handle(self):
        actor = {"role": "WILD", "presentationAttached": True, "species": 165, "subjectIdentity": 99,
                 "authorityGeneration": 1, "engineAnchorGeneration": 1, "presentationGeneration": 1,
                 "handle": {"fieldEpoch": 2, "mapGeneration": 3, "encounterGeneration": 4}}
        source = {"active": 1, "species": 165, "personality": 99, "encounter_generation": 4,
                  "object_id": 0xE0, "map_id": 33}
        engine = {"in_manager": True, "active": True, "object_manager": 123, "current_manager": 123,
                  "object_id": 0xE0, "object_map_id": 33, "script_id": 2074}
        checks = actor_identity_checks(actor, source, engine, {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}, 0)
        self.assertEqual([key for key, passed in checks.items() if not passed], ["mapGeneration"])
        actor["handle"]["mapGeneration"] = 2
        self.assertTrue(all(actor_identity_checks(actor, source, engine,
                                                {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}, 0).values()))
        # Native release sets TRUE | AGGRO; a ball hit also adds PENDING.
        # These flags do not retire the actor. Flags without the active bit
        # or outside the authored flag set must not create a valid identity.
        for flags in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 255, -1, True):
            with self.subTest(source_active=flags):
                source["active"] = flags
                checks = actor_identity_checks(actor, source, engine,
                    {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 2}, 0)
                self.assertEqual(checks["sourceActive"],
                                 type(flags) is int and flags in (1, 3, 5, 7))

    def test_terrain_has_separate_endpoint_clock_and_context(self):
        session = self.fixture()
        session.emu = object()
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=83,
            ACTOR_DESCRIPTOR={"state": {"address": 0x02300000}},
            player_ptr=lambda _emu: 123, object_state=lambda *_args: {"x": 12, "y": 13},
            loaded_terrain_cell=lambda *_args: None, loaded_warp_events=lambda _emu: [],
            field_map_id=lambda _emu: 33, unsigned=lambda _emu, _address, _size: 2)
        value = session.terrain(0)["terrain"]
        self.assertEqual(value["observation"]["boundary"], "paused-native-cycle-end")
        self.assertEqual(value["observation"]["nativeCycle"], 83)
        self.assertEqual(value["observation"]["lastCompletedGameFrame"], 40)
        self.assertFalse(value["cells"][0]["loaded"])

    def test_point_terrain_reads_only_requested_cell_without_player_or_images(self):
        session = self.fixture()
        reads = []
        session.emu = object()
        def read_cell(_emu, x, z):
            reads.append((x, z))
            return {"attribute": 0x8002, "behavior": 2, "collision": True,
                    "attribute_address": 0x02214040}
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=83,
            ACTOR_DESCRIPTOR={"state": {"address": 0x02300000}},
            loaded_terrain_cell=read_cell, loaded_warp_events=lambda _emu: [],
            field_map_id=lambda _emu: 34, unsigned=lambda _emu, _address, _size: 2)
        value = session.terrain(0, x=558, z=373)["terrain"]
        self.assertEqual(reads, [(558, 373)])
        self.assertEqual(value["observation"]["center"], {"x": 558, "z": 373})
        self.assertEqual(value["observation"]["lastCompletedGameFrame"], 40)
        self.assertEqual(value["cells"], [{"x": 558, "y": 373, "z": 373,
            "loaded": True, "attribute": 0x8002, "behavior": 2, "collision": True,
            "attribute_address": 0x02214040}])

    def test_terrain_center_validation_precedes_native_reads(self):
        session = self.fixture()
        for args in ({"x": 1}, {"z": 1}, {"x": -1, "z": 2}, {"x": True, "z": 2},
                     {"x": 32768, "z": 2}):
            with self.subTest(args=args), self.assertRaises(DevtoolsFailure):
                session.terrain(0, **args)

    def test_diagnostics_uses_native_state_without_screenshot(self):
        session = self.fixture()
        session.directory = Path("/unused-host-fixture")
        session.capture = lambda *_: self.fail("diagnostics must not capture images")
        with patch("tools.overworld.devtools_runtime.native_cpu_diagnostics", return_value={"pc": 123}):
            result = session.diagnostics()
        self.assertNotIn("screenshot", result)
        self.assertEqual(result["captureErrors"], [])
        self.assertEqual(result["cpu"], {"pc": 123})
        self.assertEqual(result["lastCompleteSnapshot"]["frame"], 40)

    def test_checked_snapshot_keeps_native_frame_without_endpoint_enrichment(self):
        session = self.fixture()
        session.native_observation = None
        session.prepared = False
        session.latest_frame.update(party=[{"species": 165}], selector={"state": 0},
                                    context={"fieldEpoch": 4, "mapId": 34})
        session.terrain = lambda *_: self.fail("checked snapshot must not scan terrain")
        session.party_snapshot = lambda: self.fail("checked snapshot must keep its coherent party read")
        result = DevtoolsSession.snapshot(session, diagnostic_details=False)
        self.assertEqual(result, {**session.latest_frame, "prepared": False})
        result["party"][0]["species"] = 56
        self.assertEqual(session.latest_frame["party"][0]["species"], 165)

    def test_worker_forwards_point_and_checked_step_options(self):
        source = Path(__file__).resolve().parents[2] / "scripts/overworld_devtools_worker.py"
        tree = ast.parse(source.read_text())
        for operation, args, expected in (
                ("terrain", {"radius": 0, "x": 558, "z": 373}, ((0,), {"x": 558, "z": 373})),
                ("step", {"frames": 1, "keys": [], "diagnosticDetails": False},
                 ((1, []), {"release_at_end": True, "diagnostic_details": False})),
                ("step", {"frames": 1, "keys": []},
                 ((1, []), {"release_at_end": True, "diagnostic_details": True}))):
            with self.subTest(operation=operation, args=args):
                calls = []
                function = lambda *a, **kw: calls.append((a, kw)) or {"observed": True}
                session = SimpleNamespace(**{operation: function})
                branch = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                              and ast.unparse(node.test) == f"operation == '{operation}'")
                module = ast.fix_missing_locations(ast.Module(body=branch.body, type_ignores=[]))
                scope = {"session": session, "args": args}
                exec(compile(module, str(source), "exec"), scope)
                self.assertEqual(calls, [expected])
                self.assertEqual(scope["result"], {"observed": True})


class ScriptWarpTests(unittest.TestCase):
    def fixture(self, *, allocation=0x02201000, wrong_owner=False, arrival_step=False):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.prepared, session.completed_frames = False, 50
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=100)
        session.sample_error = session.native_observation = session.semantic_trace = None
        session.drain_events = lambda: []
        session.field_pointer = lambda: 0x02200000
        session.target = lambda name: STOCK_CALLBACKS[name]
        writes, calls = [], []
        session.write = lambda address, data: writes.append((address, data))
        requested = {"kind": "script-warp", "state": 0, "mapId": 33, "warpId": -1,
                     "x": 585, "z": 404, "facing": 1}
        def diagnostics(*, boundary):
            return {"boundary": boundary, "taskPointer": 0x02202000, "tasks": [{
                "pointer": 0x02202000, "previous": 0, "function": STOCK_CALLBACKS["script_warp_task"] | 1,
                "environment": allocation, "fieldPointer": 0 if wrong_owner else 0x02200000,
                "transition": requested}]}
        session._control_diagnostics = diagnostics
        class HeapFreeObserver:
            closed = False
            def check(self):
                return None
            def result(self):
                return {"eventCount": 1, "ownedEnvironmentFreeSeen": True, "closed": self.closed}
            def finish(self):
                self.closed = True
                return self.result()
        session._new_script_warp_heap_free_observer = lambda constructor: HeapFreeObserver()
        def bridge(recipe):
            generator = recipe(0x027E2000)
            response = None
            while True:
                try:
                    call = generator.send(response)
                except StopIteration as result:
                    return {"value": result.value, "calls": calls}
                calls.append(call)
                if call.name == "allocate_task_environment":
                    response = allocation
                elif call.name == "create_field_task":
                    response = 0x02202000
                else:
                    self.fail(f"unexpected native recipe call {call.name}")
        session.bridge = SimpleNamespace(run=bridge)
        def wait(after, predicate, **_kwargs):
            self.assertEqual(after, 50)
            session.completed_frames = 51
            session.rt.EXECUTED_FRAME_COUNT = 102
            value = {"frame": 51, "nativeCycle": 102, "prepared": True,
                     "context": {"mapId": 33}, "fieldControl": {"taskPointer": 0},
                     "player": {"x": 585, "y": 405 if arrival_step else 404, "facing": 1}}
            if not predicate(value):
                raise DevtoolsFailure("transition-timeout", "requested position not observed")
            return value
        session._wait_new_frame = wait
        return session, writes, calls

    def test_real_recipe_allocates_exact_environment_and_transfers_to_stock_task(self):
        session, writes, calls = self.fixture()
        result = session.teleport({"map": 33, "x": 585, "z": 404, "facing": 1})
        self.assertEqual(calls, [Call("allocate_task_environment", (11, 24)),
                                Call("create_field_task", (0x02200000, 0x0205380D, 0x02201000))])
        self.assertEqual(writes, [(0x02201000, struct.pack("<6i", 0, 33, -1, 585, 404, 1))])
        self.assertEqual(result["snapshot"]["player"]["y"], 404)
        self.assertEqual(result["setupBoundary"]["nativeCycle"], 102)
        self.assertEqual(result["value"]["environmentOwnership"], "transferred-to-native-Task_ScriptWarp")
        self.assertTrue(result["heapFreeObservation"]["ownedEnvironmentFreeSeen"])

    def test_allocation_failure_does_not_write_or_create_task(self):
        session, writes, calls = self.fixture(allocation=0)
        with self.assertRaisesRegex(DevtoolsFailure, "allocation failed"):
            session.teleport({"map": 33, "x": 585, "z": 404, "facing": 1})
        self.assertEqual(writes, [])
        self.assertEqual(len(calls), 1)

    def test_wrong_task_owner_cannot_pass_constructor(self):
        session, _writes, _calls = self.fixture(wrong_owner=True)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.teleport({"map": 33, "x": 585, "z": 404, "facing": 1})
        self.assertEqual(caught.exception.code, "transition-constructor-mismatch")

    def test_arrival_step_is_not_treated_as_requested_position(self):
        session, _writes, _calls = self.fixture(arrival_step=True)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.teleport({"map": 33, "x": 585, "z": 404, "facing": 1})
        self.assertEqual(caught.exception.code, "transition-timeout")
        self.assertEqual(caught.exception.details["nativeCommand"]["heapFreeObservation"]["eventCount"], 1)

    def test_real_teleport_wait_skips_absence_then_checks_exact_arrival(self):
        session, _writes, calls = self.fixture()
        del session._wait_new_frame  # Exercise the real wait and actual caller predicate.
        session.sample_error = None
        session.latest_frame = {"frame": 50, "fieldAvailable": True}
        session.snapshot = lambda: dict(session.latest_frame)
        rows = []
        def cycle(_frames):
            session.completed_frames += 1
            session.rt.EXECUTED_FRAME_COUNT += 2
            value = {"frame": session.completed_frames, "fieldAvailable": len(rows) == 2,
                     "nativeCycle": session.rt.EXECUTED_FRAME_COUNT, "prepared": session.prepared}
            if value["fieldAvailable"]:
                value.update(context={"mapId": 33}, fieldControl={"taskPointer": 0},
                             player={"x": 585, "y": 404, "facing": 1})
            session.latest_frame = value
            rows.append(dict(value))
        session.cycle = cycle
        result = session.teleport({"map": 33, "x": 585, "z": 404, "facing": 1})
        self.assertEqual(result["snapshot"]["frame"], 53)
        self.assertEqual(result["snapshot"]["player"]["y"], 404)
        self.assertEqual([row["fieldAvailable"] for row in rows], [False, False, True])
        self.assertEqual(len(calls), 2)

class SelectorInputTests(unittest.TestCase):
    """Model slow input polling independently from native/game frame clocks."""
    def fixture(self, *, missing_press=False, stuck_release=False, initially_visible=False):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu, session.sample_error, session.completed_frames = object(), None, 0
        session.latest_frame = {"frame": 0, "selector": {
            "state": 2 if initially_visible else 0, "highlight": 2,
            "flags": 0, "newKeys": 0, "heldKeys": 0, "rawHeld": 0, "rawNew": 0,
            "queue": {"request": 0, "count": 0}}}
        def install_observer():
            self.assertEqual(session.latest_frame["selector"]["state"], 2,
                             "overlay getter installed before the menu is visible")
        session._ensure_selector_getter_observer = install_observer
        masks, edges, cycles = [], [], [0]
        keys = {"Y": 1, "R": 2, "SELECT": 4}
        session.rt = SimpleNamespace(h=SimpleNamespace(key_constant=lambda name: keys[name],
            keymask=lambda value: value, set_key_mask=lambda _emu, mask: masks.append(mask)))
        def cycle(_frames, mask=0):
            cycles[0] += 1
            observation = session.latest_frame["selector"]
            # One field input update per 10 native cycles. Old R3/release4
            # taps can vanish between these updates.
            if cycles[0] % 10 == 0:
                old = observation["heldKeys"]
                current = old if stuck_release and not mask else mask
                observation["heldKeys"], observation["newKeys"] = current, current & ~old
                observation["rawHeld"], observation["rawNew"] = current, current & ~old
                if not current:
                    observation["flags"] = 0
                if observation["newKeys"] and not missing_press:
                    edges.append(current)
                    if current == 1:
                        observation["state"] = 2 if observation["state"] == 0 else 0
                        if observation["state"] == 0:
                            observation["queue"] = {"request": 0x80 | observation["highlight"], "count": 0}
                            observation["flags"] = 0x80
                    elif current == 2:
                        observation["highlight"] = (observation["highlight"] + 1) % 6
                    elif current == 4:
                        observation["state"] = 0
                        observation["queue"] = {"request": 0xC0 | observation["highlight"], "count": 0}
                        observation["flags"] = 0x80
            if cycles[0] % 2 == 0:
                session.completed_frames += 1
                session.latest_frame["frame"] = session.completed_frames
        session.cycle = cycle
        return session, masks, edges, cycles

    def test_slow_poll_reaches_exact_slot_and_records_confirmed_request(self):
        session, masks, edges, _ = self.fixture()
        result = session._select_party_subject(0, "FOLLOWER")
        self.assertTrue(result["passed"])
        self.assertEqual(result["selections"], [2, 3, 4, 5, 0])
        self.assertEqual(edges, [1, 2, 2, 2, 2, 1])
        self.assertEqual(result["confirmation"]["queue"]["request"], 0x80)
        self.assertEqual(masks[-1], 0)
        self.assertGreater(result["inputs"][1]["nativeCycles"], 3)

    def test_existing_visible_menu_is_not_closed_by_an_extra_open_press(self):
        session, _, edges, _ = self.fixture(initially_visible=True)
        self.assertTrue(session._select_party_subject(2, "FOLLOWER")["passed"])
        self.assertEqual(edges, [1])

    def test_mount_uses_select_not_y_confirmation(self):
        session, _, edges, _ = self.fixture()
        result = session._select_party_subject(2, "MOUNTED")
        self.assertTrue(result["passed"])
        self.assertEqual(edges, [1, 4])
        self.assertEqual(result["confirmation"]["queue"]["request"], 0xC2)

    def test_unconsumed_key_fails_bounded_and_always_releases(self):
        session, masks, _, cycles = self.fixture(missing_press=True)
        result = session._select_party_subject(0, "FOLLOWER")
        self.assertFalse(result["passed"])
        self.assertEqual(result["reason"], "selector-input-timeout")
        self.assertLessEqual(cycles[0], 1000)
        self.assertEqual(masks[-1], 0)

    def test_release_must_reach_native_input_before_next_press(self):
        session, masks, edges, _ = self.fixture(stuck_release=True)
        result = session._select_party_subject(0, "FOLLOWER")
        self.assertFalse(result["passed"])
        self.assertEqual(edges, [1])
        self.assertEqual(masks[-1], 0)

    def test_confirmed_release_is_not_blocked_only_by_retained_task_poll_gate(self):
        session, _, _, _ = self.fixture()
        cycle = session.cycle
        def gated_cycle(*args):
            cycle(*args)
            current = session.latest_frame["selector"]
            if current["queue"]["request"]:
                current["flags"] = 0x80
        session.cycle = gated_cycle
        result = session._select_party_subject(0, "FOLLOWER")
        self.assertTrue(result["passed"])
        self.assertEqual(result["afterRelease"]["flags"], 0x80)
        self.assertEqual(result["afterRelease"]["rawHeld"], 0)

    def test_getter_requires_live_code_and_does_not_reuse_an_unloaded_overlay(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        code, registrations = [bytes(32)], []
        expected = bytes(range(32))
        session.read = lambda _address, _size: code[0]
        def target(name):
            self.assertEqual(name, "selected_follower_slot")
            if code[0] != expected:
                raise DevtoolsFailure("abi-mismatch", "live code differs from ROM")
            return 0x023C0D98
        session.target = target
        session.party_getter_hooks = SimpleNamespace(observe_call=lambda *args: registrations.append(args))
        session.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=SimpleNamespace(r0=0x02200000)))
        session.native_bridge_active, session.completed_frames = False, 10
        session.field_pointer = lambda: 0x02200000
        session.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=25)
        with self.assertRaisesRegex(DevtoolsFailure, "differs from ROM"):
            session._ensure_selector_getter_observer()
        self.assertEqual(registrations, [])
        code[0] = expected
        session._ensure_selector_getter_observer()
        session._ensure_selector_getter_observer()
        self.assertEqual(len(registrations), 1)
        _, before, after = registrations[0]
        context = before()
        self.assertEqual(context, 0x02200000)
        session.emu.memory.register_arm9.r0 = 2
        after(context)
        self.assertEqual(session.selected_follower_observation["slot"], 2)
        code[0] = bytes(32)
        self.assertIsNone(before())
        after(context)
        self.assertIsNone(session.selected_follower_observation)


class NativeFollowerSetupTests(unittest.TestCase):
    def fixture(self, *, role=None, pid=123, rejected=False):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = SimpleNamespace(memory=SimpleNamespace(register_write=lambda *_args, **_kwargs: None))
        session.completed_frames = 10
        session.native_irq_live_baseline = bytes(0x1AC)
        session.sample_error = session.semantic_trace = session.native_observation = None
        session.trace_events, session.trace_pending, session.trace_events_dropped = [], [], 0
        mon = {"species": 56, "personality": 123, "hp": 10, "isEgg": False, "form": 0, "level": 10}
        session.party_snapshot = lambda: [mon]
        def actor(current_role, current_pid=123):
            return {"role": current_role, "subjectIdentity": current_pid, "species": 56,
                    "identityVerified": True, "active": True, "motionPhase": "IDLE", "reservationId": 0,
                    "form": 0, "level": 10}
        state = {"actors": [actor(role, pid)] if role else [], "selector": {
            "queue": {"count": 0, "request": 0}, "followerReleaseState": 0,
            "captureTargetMask": 0, "activeFollowerPartySlot": 0 if role else 255,
            "follower": {"active": bool(role)}}}
        state.update(frame=10, nativeCycle=20, prepared=True)
        calls, waits = [], []
        session.snapshot = lambda *_args: state
        session.require_quiescent = lambda: None
        session.field_pointer = lambda: 0x02200000
        session.rt = SimpleNamespace(WILD_STATE=0x023DF9C8, EXECUTED_FRAME_COUNT=20)
        session._native_checkpoint_points = lambda: []
        def run(recipe):
            generator = recipe(0x02280000)
            call = next(generator)
            calls.append(call)
            if not rejected:
                if call.name == "recall_follower":
                    state["actors"] = [] if call.args[1] == 255 else [actor("FOLLOWER")]
                    state["selector"]["activeFollowerPartySlot"] = call.args[1]
                elif call.name == "mount_selected_follower":
                    self.assertEqual(state["selector"]["followerReleaseState"], 0)
                    self.assertEqual(state["selector"]["captureTargetMask"] & 128, 0)
                    state["actors"] = [actor("MOUNTED")]
                elif call.name == "cancel_mount":
                    state["actors"] = [actor("FOLLOWER", pid)]
                state["selector"]["follower"]["active"] = bool(state["actors"])
            try:
                generator.send(0 if rejected else 1)
            except StopIteration as complete:
                return {"value": complete.value, "calls": [{"routine": call.name}]}
            self.fail("unexpected second native call")
        session.bridge = SimpleNamespace(run=run)
        def wait(_frame, predicate, **options):
            waits.append(options["message"])
            session.completed_frames += 1
            session.rt.EXECUTED_FRAME_COUNT += 2
            state.update(frame=session.completed_frames, nativeCycle=session.rt.EXECUTED_FRAME_COUNT)
            if not predicate(state):
                raise DevtoolsFailure("spawn-failed", "fixture did not reach the exact live subject")
            return state
        session._wait_new_frame = wait
        return session, calls, waits, state

    def test_prepared_follower_uses_native_request_not_y(self):
        session, calls, _, _ = self.fixture()
        result = session.spawn({"role": "follower", "slot": 0, "species": 56})
        self.assertEqual([(call.name, call.args) for call in calls], [("recall_follower", (0x02200000, 0))])
        self.assertEqual(result["lifecycle"], "prepared-native-follower-lifecycle")
        self.assertEqual(result["snapshot"]["actors"][0]["subjectIdentity"], 123)

    def test_mount_waits_for_real_follower_and_settled_release(self):
        session, calls, waits, _ = self.fixture()
        result = session.spawn({"role": "mounted", "slot": 0, "species": 56})
        self.assertEqual([call.name for call in calls], ["recall_follower", "mount_selected_follower"])
        self.assertIn("selected follower release presentation did not settle", waits)
        self.assertEqual(result["snapshot"]["actors"][0]["role"], "MOUNTED")

    def test_exact_current_follower_is_not_toggled_off(self):
        session, calls, _, _ = self.fixture(role="FOLLOWER")
        self.assertTrue(session.spawn({"role": "follower", "slot": 0})["alreadySelected"])
        self.assertEqual(calls, [])
        session.spawn({"role": "mounted", "slot": 0})
        self.assertEqual([call.name for call in calls], ["mount_selected_follower"])

    def test_duplicate_pid_in_another_slot_is_not_the_requested_follower(self):
        session, calls, _, state = self.fixture(role="FOLLOWER")
        state["selector"]["activeFollowerPartySlot"] = 2
        result = session.spawn({"role": "follower", "slot": 0})
        self.assertFalse(result.get("alreadySelected", False))
        self.assertEqual([call.args[1] for call in calls], [255, 0])
        self.assertEqual(result["snapshot"]["selector"]["activeFollowerPartySlot"], 0)

    def test_existing_exact_actor_with_pending_removal_is_not_success(self):
        for key, value in (("count", 1), ("request", 128), ("release", 4), ("capture", 128)):
            with self.subTest(key=key):
                session, calls, _, state = self.fixture(role="FOLLOWER")
                if key in ("count", "request"):
                    state["selector"]["queue"][key] = value
                else:
                    state["selector"]["followerReleaseState" if key == "release" else "captureTargetMask"] = value
                with self.assertRaises(DevtoolsFailure) as caught:
                    session.spawn({"role": "follower", "slot": 0})
                self.assertEqual(caught.exception.code, "busy")
                self.assertEqual(calls, [])

    def test_follower_success_waits_for_release_and_capture_to_finish(self):
        session, _, waits, state = self.fixture()
        original_wait = session._wait_new_frame
        saw_visible = [False]
        def wait(frame, predicate, **options):
            if not saw_visible[0]:
                saw_visible[0] = True
                result = original_wait(frame, predicate, **options)
                state["selector"].update(followerReleaseState=4, captureTargetMask=128)
                return result
            self.assertFalse(predicate(state), "visible follower accepted before ball return completed")
            state["selector"]["followerReleaseState"] = 0
            self.assertFalse(predicate(state), "capture ownership must also be released")
            state["selector"]["captureTargetMask"] = 0
            return original_wait(frame, predicate, **options)
        session._wait_new_frame = wait
        result = session.spawn({"role": "follower", "slot": 0})
        self.assertEqual(len(waits), 2)
        self.assertEqual(result["snapshot"]["selector"]["followerReleaseState"], 0)
        self.assertEqual(result["snapshot"]["selector"]["captureTargetMask"], 0)

    def test_same_species_wrong_pid_is_recalled_before_selection(self):
        session, calls, _, _ = self.fixture(role="MOUNTED", pid=999)
        session.spawn({"role": "follower", "slot": 0})
        self.assertEqual([(call.name, call.args[-1]) for call in calls],
                         [("cancel_mount", 1), ("recall_follower", 255), ("recall_follower", 0)])

    def test_existing_queue_is_not_cleared_or_bypassed(self):
        session, calls, _, state = self.fixture()
        state["selector"]["queue"]["count"] = 1
        with self.assertRaisesRegex(DevtoolsFailure, "already pending"):
            session.spawn({"role": "follower", "slot": 0})
        self.assertEqual(calls, [])
        self.assertEqual(state["selector"]["queue"]["count"], 1)

    def test_native_acceptance_does_not_accept_absent_wrong_or_invalid_actor(self):
        session, _, _, state = self.fixture()
        def wait(_frame, predicate, **_options):
            exact = dict(state["actors"][0])
            self.assertFalse(predicate({**state, "actors": []}))
            for field, wrong in (("role", "MOUNTED"), ("subjectIdentity", 124),
                                 ("species", 155), ("form", 1), ("level", 11), ("identityVerified", False)):
                self.assertFalse(predicate({**state, "actors": [{**exact, field: wrong}]}))
            state["actors"] = [{**exact, "identityVerified": False, "identityFailures": ["mapGeneration"]}]
            raise DevtoolsFailure("spawn-failed", "no valid actor")
        session._wait_new_frame = wait
        with self.assertRaises(DevtoolsFailure) as caught:
            session.spawn({"role": "follower", "slot": 0})
        self.assertEqual(caught.exception.details["snapshot"]["actors"][0]["identityFailures"], ["mapGeneration"])
        self.assertEqual(caught.exception.details["nativeSetup"]["nativeCommands"][0]["value"]["returned"], 1)

    def test_native_rejection_is_retained_without_claiming_spawn(self):
        session, _, _, _ = self.fixture(rejected=True)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.spawn({"role": "follower", "slot": 0})
        self.assertEqual(caught.exception.code, "spawn-rejected")
        self.assertEqual(caught.exception.details["nativeSetup"]["nativeCommands"][0]["value"]["returned"], 0)


class PartyAllocationTests(unittest.TestCase):
    def test_finite_work_descriptors_match_real_stock_native_call_sites(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.rt = SimpleNamespace(REPO=Path(__file__).resolve().parents[2])
        stock = (session.rt.REPO / "base/arm9.bin").read_bytes()
        session.packaged_code = lambda address, size: stock[address - 0x02000000:address - 0x02000000 + size]
        session._authenticate_party_work_heap()
        self.assertEqual([site[0] for site in PARTY_WORK_HEAP_SITES], ["exp", "moveset", "personal", "stats", "mail"])

    def adapter_fixture(self):
        fixture = BridgeFixture()
        fixture.prepared = True
        state = {"started": True, "done": False, "callee_active": True,
                 "calls": [{"routine": "create_mon"}], "thread": dict(fixture.thread)}
        adapter = PreparedPartyWorkHeap(fixture, state)
        adapter.growth_entry()
        fixture.regs.sp -= 16
        fixture.regs.r0, fixture.regs.r1, fixture.regs.lr = 0, 404, 0x0206FD51
        return fixture, state, adapter

    def test_only_exact_prepared_exp_allocation_changes_heap_and_native_free_is_tracked(self):
        fixture, _state, adapter = self.adapter_fixture()
        adapter.allocate_entry()
        self.assertEqual(fixture.regs.r0, 11)
        pointer = 0x02220000
        fixture.regs.r0 = pointer
        fixture.write(pointer - 4, bytes([11, 33, 44, 55]))  # heap ID is only the low byte
        adapter.allocate_return()
        fixture.regs.lr = 0x0206FD65
        adapter.free_entry()
        adapter.free_return()
        self.assertEqual(adapter.receipts[0]["allocation"], pointer)
        self.assertEqual(adapter.receipts[0]["nativeHeaderHeap"], 11)
        self.assertTrue(adapter.receipts[0]["released"])

    def test_other_caller_size_thread_phase_and_normal_play_are_not_changed(self):
        for variant in ("caller", "size", "thread", "not-party", "not-active", "normal", "stack", "heap", "field"):
            with self.subTest(variant=variant):
                fixture, state, adapter = self.adapter_fixture()
                if variant == "caller": fixture.regs.lr += 2
                elif variant == "size": fixture.regs.r1 = 400
                elif variant == "thread": fixture.thread["pointer"] += 4
                elif variant == "not-party": state["calls"][-1]["routine"] = "transition"
                elif variant == "not-active": state["callee_active"] = False
                elif variant == "normal": fixture.prepared = False
                elif variant == "stack": fixture.regs.sp -= 4
                elif variant == "heap": fixture.regs.r0 = 3
                elif variant == "field": fixture.native_heap_generation += 1
                old_heap = fixture.regs.r0
                adapter.allocate_entry()
                self.assertEqual(fixture.regs.r0, old_heap)
                self.assertEqual(adapter.receipts, [])

    def test_nested_moveset_and_personal_buffers_keep_distinct_native_free_frames(self):
        fixture, _state, adapter = self.adapter_fixture()
        sites = {site[0]: site for site in PARTY_WORK_HEAP_SITES}
        initial_sp = fixture.initial[13]
        def allocate(name, owner_sp, pointer):
            site = sites[name]
            fixture.regs.sp = owner_sp
            adapter.owner_entry(site)
            fixture.regs.sp = owner_sp - site[5]
            fixture.regs.r0, fixture.regs.r1, fixture.regs.lr = 0, site[3], site[4] | 1
            adapter.allocate_entry(site[2])
            self.assertEqual(fixture.regs.r0, 11)
            fixture.regs.r0 = pointer
            fixture.write(pointer - 4, bytes([11, 0, 0, 0]))
            adapter.allocate_return(site[4])
        def free(name, owner_sp, pointer):
            site = sites[name]
            fixture.regs.sp = owner_sp - site[7]
            fixture.regs.r0, fixture.regs.lr = pointer, site[6] | 1
            adapter.free_entry()
            adapter.free_return(site[6])
        allocate("moveset", initial_sp, 0x02220000)
        allocate("personal", initial_sp - 64, 0x02221000)
        self.assertEqual(len(adapter.open), 2)
        free("personal", initial_sp - 64, 0x02221000)
        self.assertEqual(len(adapter.open), 1)
        free("moveset", initial_sp, 0x02220000)
        allocate("stats", initial_sp, 0x02222000)
        free("stats", initial_sp, 0x02222000)
        allocate("mail", initial_sp - 80, 0x02223000)
        free("mail", initial_sp - 80, 0x02223000)
        self.assertEqual(adapter.open, [])
        self.assertTrue(all(item["released"] for item in adapter.receipts))

    def test_exp_work_heap_refuses_insufficient_space_before_constructor(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        session.party_snapshot = lambda: [{"species": 56}]
        session._prepared_personality = lambda _args: 123
        session.rt = SimpleNamespace(actor_state=lambda *_args: {"active": False})
        calls = []
        def run(recipe, **options):
            self.assertTrue(options.get("prepared_party_work_heap"))
            generator, value = recipe(0x027E2000), None
            while True:
                call = generator.send(value)
                calls.append(call)
                self.assertNotEqual(call.name, "create_mon", "constructor ran without available EXP work memory")
                value = 0x02210000 if call.name == "allocate_mon" else 0
        session.bridge = SimpleNamespace(run=run)
        with self.assertRaisesRegex(DevtoolsFailure, "EXP work memory"):
            session.party({"slot": 0, "species": 56, "level": 10})
        self.assertEqual(calls, [Call("allocate_mon", (11,)), Call("allocate_work_memory", (11, 404)),
                                 Call("free", (0x02210000,))])
        self.assertEqual(session.native_allocations, {})

    def test_closed_core_generator_cleanup_never_yields_another_native_call(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        session.party_snapshot = lambda: [{"species": 56}]
        session._prepared_personality = lambda _args: 123
        session.rt = SimpleNamespace(actor_state=lambda *_args: {"active": False})
        calls = []
        def abort(recipe, **options):
            generator = recipe(0x027E2000)
            calls.append(next(generator))
            calls.append(generator.send(0x02210000))
            calls.append(generator.send(0x02220000))
            calls.append(generator.send(1))
            session.emu = None  # Native abort already destroyed this core.
            generator.close()  # Must not raise 'generator ignored GeneratorExit'.
            raise DevtoolsFailure("native-call-aborted", "closed", fatal=True)
        session.bridge = SimpleNamespace(run=abort)
        with self.assertRaises(DevtoolsFailure) as caught:
            session.party({"slot": 0, "species": 56, "level": 10})
        self.assertTrue(caught.exception.fatal)
        self.assertEqual([call.name for call in calls], ["allocate_mon", "allocate_work_memory", "free", "create_mon"])

    def test_handled_hp_move_and_add_rejections_free_owned_mon_before_error(self):
        for failure in ("hp", "move", "add"):
            with self.subTest(failure=failure):
                session = DevtoolsSession.__new__(DevtoolsSession)
                session.emu = object()
                session.party_snapshot = lambda: [] if failure == "add" else [{"species": 56}]
                session._prepared_personality = lambda _args: 123
                session.party_pointer = lambda: 0x02200000
                session.rt = SimpleNamespace(actor_state=lambda *_args: {"active": False})
                session.write = lambda *_args: None
                calls = []
                def run(recipe, **options):
                    generator, value = recipe(0x027E2000), None
                    while True:
                        call = generator.send(value)
                        calls.append(call)
                        if call.name == "allocate_mon":
                            value = 0x02210000
                        elif call.name == "allocate_work_memory":
                            value = 0x02220000
                        elif call.name == "get_mon":
                            value = 10
                        elif call.name in ("replace_move", "add_party_mon"):
                            value = 0
                        else:
                            value = 1
                session.bridge = SimpleNamespace(run=run)
                args = {"slot": 0, "species": 56, "level": 10}
                if failure == "hp":
                    args["hp"] = 11
                elif failure == "move":
                    args["moves"] = [33, 0, 0, 0]
                with self.assertRaises(DevtoolsFailure):
                    session.party(args)
                self.assertEqual(calls[-1], Call("free", (0x02210000,)))
                self.assertEqual(session.native_allocations, {})
                self.assertEqual(sum(call.name == "free" for call in calls), 2)


class ValueTests(unittest.TestCase):
    def test_empty_transport_never_calls_pydesmume(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu, session.prepared = object(), True
        def forbidden(*_args):
            self.fail("empty transport reached pydesmume")
        session.rt = SimpleNamespace(actor_memory_write=forbidden, actor_memory_read=forbidden)
        session.write(0x02001000, b"")
        self.assertEqual(session.read(0x02001000, 0), b"")

    def test_strict_integer_rejects_bool_and_float(self):
        for value in (True, 1.0, "1", -1, 33):
            with self.assertRaises(DevtoolsFailure):
                integer(value, "frames", 0, 32)

    def test_owned_input_and_fresh_output(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder).resolve()
            source = directory / "copied.sav"
            source.write_bytes(b"fixture")
            self.assertEqual(owned_path(str(source), directory), source)
            with self.assertRaises(DevtoolsFailure):
                owned_path(str(source), directory, exists=False)
            with self.assertRaises(DevtoolsFailure):
                owned_path(str(directory.parent / "external.sav"), directory)
            link = directory / "alias.sav"
            link.hardlink_to(source)
            with self.assertRaises(DevtoolsFailure):
                owned_path(str(source), directory)

    def test_party_decode_uses_copy_and_keeps_identity_health_moves(self):
        pid = 123
        box = bytearray(128)
        struct.pack_into("<H", box, 0, 155)
        struct.pack_into("<4H", box, 32, 33, 45, 52, 0)
        box[40:44] = bytes((12, 13, 14, 0))
        box[56] = 3 << 3
        checksum = sum(struct.unpack("<64H", box)) & 0xFFFF
        extra = bytearray(100)
        struct.pack_into("<I", extra, 0, 8)
        extra[4] = 12
        struct.pack_into("<HH", extra, 6, 20, 30)
        record = struct.pack("<IHH", pid, 0, checksum) + _crypt(box, checksum) + _crypt(extra, pid)
        party = struct.pack("<II", 6, 1) + record + bytes(5 * 236)
        before = bytes(party)
        mon = decode_party(party, SUBSTRUCT_OFFSETS)[0]
        self.assertEqual((mon["species"], mon["personality"], mon["level"], mon["hp"], mon["maxHp"], mon["form"]),
                         (155, pid, 12, 20, 30, 3))
        self.assertEqual(mon["moves"], [33, 45, 52, 0])
        self.assertEqual(party, before)
        changed = bytearray(party)
        changed[20] ^= 1
        with self.assertRaisesRegex(DevtoolsFailure, "checksum"):
            decode_party(changed, SUBSTRUCT_OFFSETS)

    def test_prepared_personalities_repeat_only_for_same_session_sequence(self):
        def session(save):
            result = DevtoolsSession.__new__(DevtoolsSession)
            result.rom_hash, result.save_hash, result.personality_sequence = "abc", save, 0
            return result
        first, repeated, other = session("def"), session("def"), session("ghi")
        values = [first._prepared_personality({}) for _ in range(3)]
        self.assertEqual(values, [repeated._prepared_personality({}) for _ in range(3)])
        self.assertEqual(len(set(values)), 3)
        self.assertNotEqual(values[0], other._prepared_personality({}))
        self.assertEqual(first._prepared_personality({"personality": 99}), 99)
        self.assertEqual(first.personality_sequence, 3)

    def test_party_snapshot_never_reads_mid_getter_bytes(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.sample_error = None
        session.latest_frame = {"frame": 42}
        session.latest_party_frame = 42
        session.latest_party = [{"slot": 0, "species": 163, "hp": 19}]
        def forbidden(*args):
            self.fail("snapshot read an arbitrary native-cycle endpoint")
        session.read = forbidden
        session.party_pointer = forbidden
        value = session.party_snapshot()
        self.assertEqual(value, session.latest_party)
        value[0]["hp"] = 0
        self.assertEqual(session.latest_party[0]["hp"], 19)

    def test_party_cache_rejects_missing_stale_and_failed_frames(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.latest_frame = {"frame": 43}
        session.latest_party_frame = 42
        session.latest_party = [{"species": 163}]
        session.sample_error = None
        with self.assertRaisesRegex(DevtoolsFailure, "current complete party"):
            session.party_snapshot()
        session.latest_party_frame = 43
        session.sample_error = ValueError("checksum differs")
        with self.assertRaisesRegex(DevtoolsFailure, "checksum differs"):
            session.party_snapshot()

    def test_snapshot_does_not_replace_coherent_native_receipt_watermark(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.sample_error = None
        session.latest_frame = {"frame": 42, "nativeObservation": {"sequence": 5, "pendingUnframedEvents": 0},
            "partyObservation": {"frame": 42, "nativeGetterChecks": [{"frame": 42, "native": 0}]}}
        session.latest_party_frame, session.latest_party = 42, []
        session.party_getter_checks = {(1, 163): {"frame": 43, "native": 20}}
        session.prepared = False
        session.latest_resolved_profiles = [{"fingerprint": 1}]
        session.native_observation = SimpleNamespace(hooks=SimpleNamespace(error=None), snapshot=lambda **kw: {
            "sequence": 6, "pendingUnframedEvents": 1, "resolvedProfiles": [{"fingerprint": 2}]})
        session.terrain = lambda radius: {"terrain": {}}
        value = session.snapshot()
        self.assertEqual(value["nativeObservation"], {"sequence": 5, "pendingUnframedEvents": 0,
            "resolvedProfiles": [{"fingerprint": 1}]})
        self.assertEqual(value["partyObservation"], session.latest_frame["partyObservation"])

    def test_unchanged_lock_flags_do_not_make_temporary_getter_data_valid(self):
        # Retail GetMonData decrypts both regions while flags stay zero, then
        # restores encryption before return. That temporary state MUST fail;
        # the fix is the observation boundary, not a checksum fallback.
        pid = 123
        box = bytearray(128)
        struct.pack_into("<H", box, 0, 163)
        checksum = sum(struct.unpack("<64H", box)) & 0xFFFF
        extra = bytes(100)
        temporary = struct.pack("<IHH", pid, 0, checksum) + box + extra
        with self.assertRaisesRegex(DevtoolsFailure, "checksum"):
            decode_party(struct.pack("<II", 6, 1) + temporary + bytes(5 * 236),
                         SUBSTRUCT_OFFSETS)
        completed = struct.pack("<IHH", pid, 0, checksum) + _crypt(box, checksum) + _crypt(extra, pid)
        self.assertEqual(decode_party(struct.pack("<II", 6, 1) + completed + bytes(5 * 236),
                                     SUBSTRUCT_OFFSETS)[0]["species"], 163)


class ObserverControlSessionTests(unittest.TestCase):
    def test_snapshot_shares_id_scan_only_within_one_boundary(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        session.completed_frames = 12
        session.prepared = False
        session.rom_hash = session.save_hash = "fixture"
        session.native_observation = None
        session.field_pointer = lambda: 0x02004000
        session.read = lambda *_: bytes(4)
        session._crash_presentation_reader = SimpleNamespace(
            boundary=lambda _: None, observe=lambda *_: {"known": False})
        caches = []
        def identity(emu, slot, *, id_scan_cache):
            caches.append(id_scan_cache)
            id_scan_cache[slot] = slot
            return {"in_manager": False}
        session.rt = SimpleNamespace(
            EXECUTED_FRAME_COUNT=30, ACTOR_DESCRIPTOR={"state": {"address": 0x02001000},
                "capacities": {"actors": 2}},
            object_state=lambda *_: {}, player_ptr=lambda _: 0x02002000,
            unsigned=lambda *_: 1, field_map_id=lambda _: 33,
            actor_state=lambda _, slot: {"active": True, "role": "WILD",
                "lastDecision": 0, "lastCancelReason": 0}, wild_spawn=lambda *_: {},
            live_wild_object_identity=identity, movement_policy_state=lambda *_: {},
            actor_probe=SimpleNamespace(_enum_name=lambda *_: "ACCEPTED"))
        with patch("tools.overworld.devtools_runtime.actor_identity_checks", return_value={"current": True}):
            first = session._snapshot(0, details=False)
            second = session._snapshot(0, details=False)
        self.assertEqual(first, second)
        self.assertIs(caches[0], caches[1])
        self.assertIs(caches[2], caches[3])
        self.assertIsNot(caches[0], caches[2])

    def test_arm_revalidates_subject_and_advances_no_frames(self):
        from tools.overworld.test_devtools_test_contract import snapshot
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.completed_frames, session.prepared = 10, False
        session.snapshot = lambda: {**snapshot(10), "prepared": session.prepared}
        closed = []
        session.observer_control = SimpleNamespace(close=lambda: closed.append("old"))
        class Control:
            def __init__(self, owner, subject): self.owner, self.subject = owner, subject
            def arm(self, kind, max_frames): self.kind, self.limit = kind, max_frames
            def result(self): return {"state": "armed", "kind": self.kind, "subject": self.subject}
        args = {"subject": snapshot()["actors"][0], "kind": "render-stall", "maxFrames": 1200}
        with patch("tools.overworld.devtools_observer_control.NativeObserverControl", Control):
            stale = {**args, "subject": {**args["subject"], "subjectIdentity": 987}}
            with self.assertRaises(ValueError): session.observer_control_arm(stale)
            self.assertEqual(closed, [])
            self.assertFalse(session.prepared)
            result = session.observer_control_arm(args)
        self.assertEqual(closed, ["old"])
        self.assertEqual(session.completed_frames, 10)
        self.assertEqual(result["snapshot"]["frame"], 10)
        self.assertTrue(result["snapshot"]["prepared"])
        self.assertEqual(result["snapshot"]["observerControl"]["kind"], "render-stall")

    def test_installed_completed_callback_runs_control_before_real_snapshot(self):
        order, callbacks = [], {}
        session = DevtoolsSession.__new__(DevtoolsSession)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "base").mkdir(); (root / "base/arm9.bin").write_bytes(bytes(64))
            session.rt = SimpleNamespace(REPO=root, MAIN_TASK_QUEUE_RETURN=0x02000010,
                G_FIELD_SYS_PTR=0x02001000, ACTOR_DESCRIPTOR={"state": {"address": 0x02002000}},
                unsigned=lambda emu, address: 0x5353574F if address == 0x02002000 else 0x02003000)
            session.emu = SimpleNamespace(memory=SimpleNamespace(register_exec=lambda a, cb: callbacks.update({a: cb})))
            session.packaged_code = lambda *args: bytes(12)
            session._install_party_getter_checks = lambda: None
            session._install_heap_lifetime_observer = lambda: None
            # This callback-order fixture has no stock ROM. The free-entry
            # check has its own byte-authenticated tests.
            session._install_native_free_guard = lambda: None
            session._field_actor_availability = lambda field: {"reason": None}
            session._read_guest_queue_clock = lambda: {}
            session.party_getter_hooks = SimpleNamespace(error=None)
            session.party_getter_checks = {}
            session.completed_frames, session.sample_error, session.step_release_at_frame = 3, None, None
            session.pending_samples, session.latest_profile_keys = [], ()
            session._read_party_at_boundary = lambda: []
            session._selector_observation = lambda: {}
            session._dialogue_observation = lambda field: (order.append("dialogue") or {
                "fieldPointer": field, "frame": session.completed_frames, "state": "idle"})
            session._complete_trace_boundary = lambda: order.append("trace")
            session._snapshot = lambda *a, **k: (order.append("snapshot") or {
                "frame": session.completed_frames, "nativeObservation": {"profileFingerprints": []}})
            session.observer_control = SimpleNamespace(completed_boundary=lambda: order.append("control"),
                result=lambda: {"state": "injected", "frame": session.completed_frames})
            class Native:
                def __init__(self, *args): pass
                def install(self): pass
                def completed_frame(self, frame): order.append("native")
            with patch("tools.overworld.devtools_observer.NativeObservation", Native): session._install_sampler()
            callbacks[session.sampling_hook](session.sampling_hook, 4)
            self.assertEqual(order, ["native", "control", "snapshot", "dialogue", "trace"])
            self.assertEqual(session.pending_samples[0]["observerControl"], {"state": "injected", "frame": 4})
            self.assertEqual(session.pending_samples[0]["dialogue"]["frame"], 4)
            self.assertIsNone(session.sample_error)
            def failed(): raise ValueError("owned control failed")
            session.observer_control.completed_boundary = failed
            callbacks[session.sampling_hook](session.sampling_hook, 4)
            self.assertIsInstance(session.sample_error, ValueError)
            self.assertEqual(len(session.pending_samples), 1)

    def test_close_restores_control_before_other_shutdown(self):
        order = []
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = SimpleNamespace(destroy=lambda: order.append("destroy"))
        session.observer_control = SimpleNamespace(close=lambda: order.append("restore"))
        session.semantic_trace = SimpleNamespace(stop=lambda: order.append("trace"))
        session.sampling_hook = session.native_observation = session.party_getter_hooks = None
        session.rt = SimpleNamespace(h=SimpleNamespace(set_key_mask=lambda *args: order.append("release")))
        session.close()
        self.assertEqual(order, ["restore", "trace", "release", "destroy"])

    def test_explicit_close_retains_restore_receipt_without_frames(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.completed_frames = 9
        restored = []
        session.observer_control = SimpleNamespace(close=lambda: restored.append(True),
            result=lambda: {"state": "closed", "restored": True})
        session.latest_frame = {"frame": 9, "prepared": True, "active": False}
        session.snapshot = lambda: dict(session.latest_frame)
        session._snapshot = lambda *args, **kwargs: {"frame": 9, "prepared": True, "active": True}
        result = session.observer_control_close()
        self.assertEqual(restored, [True])
        self.assertEqual(result["advancedFrames"], 0)
        self.assertEqual(result["snapshot"]["frame"], 9)
        self.assertTrue(result["observerControl"]["restored"])
        self.assertTrue(result["snapshot"]["active"])
        self.assertFalse(session.latest_frame["active"])
        self.assertEqual(result["snapshot"]["observationBoundary"], "observer-control-restoration-readback")
        self.assertEqual(result["snapshot"]["observedFrameCredit"], 0)
        def failed_snapshot(*args, **kwargs): raise ValueError("original failed sample")
        session._snapshot = failed_snapshot
        result = session.observer_control_close()
        self.assertTrue(result["closed"])
        self.assertTrue(result["observerControl"]["restored"])
        self.assertIn("original failed sample", result["snapshotError"])

    def test_actual_worker_dispatch_uses_only_internal_control_methods(self):
        source = Path(__file__).resolve().parents[2] / "scripts/overworld_devtools_worker.py"
        tree = ast.parse(source.read_text())
        calls = []
        session = SimpleNamespace(observer_control_arm=lambda args: calls.append(("arm", args)) or {"armed": True},
                                  observer_control_close=lambda: calls.append(("close", None)) or {"closed": True})
        for operation in ("observer-control.arm", "observer-control.close"):
            branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                        and ast.unparse(node.test) == f"operation == '{operation}'"]
            self.assertEqual(len(branches), 1)
            module = ast.fix_missing_locations(ast.Module(body=branches[0].body, type_ignores=[]))
            scope = {"session": session, "args": {"kind": "render-stall"}}
            exec(compile(module, str(source), "exec"), scope)
            self.assertTrue(scope["result"]["armed" if operation.endswith("arm") else "closed"])
        self.assertEqual(calls, [("arm", {"kind": "render-stall"}), ("close", None)])


class CompletedFieldAvailabilityTests(unittest.TestCase):
    """Actual installed queue callback with missing native field state.

    This host boundary fixture proves recorder shape and default rejection,
    not a real map transition or a permitted cadence setup interval.
    """
    def fixture(self):
        from tools.overworld.test_devtools_test_contract import snapshot
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "base").mkdir()
        (root / "base/arm9.bin").write_bytes(bytes(64))
        session = DevtoolsSession.__new__(DevtoolsSession)
        callbacks, reads, releases, trace_frames = {}, [], [], []
        memory = {0x02001000: 0x02003000, 0x02002000: 0x5353574F}
        session.rt = SimpleNamespace(REPO=root, MAIN_TASK_QUEUE_RETURN=0x02000010,
            G_FIELD_SYS_PTR=0x02001000, ACTOR_DESCRIPTOR={"state": {"address": 0x02002000}},
            EXECUTED_FRAME_COUNT=7, unsigned=lambda emu, address: memory[address],
            h=SimpleNamespace(set_key_mask=lambda emu, mask: releases.append(mask),
                              keymask=lambda value: value, key_constant=lambda key: 1))
        session.emu = SimpleNamespace(memory=SimpleNamespace(register_exec=lambda a, cb: callbacks.update({a: cb})))
        session.emu.guest_clock = lambda: dict(version=1, running=True,
            scope="nds-scheduler-ticks-not-cpu-or-instructions",
            arm9Timestamp=7000, arm7Timestamp=3500, frameSequence=7)
        session.packaged_code = lambda *args: bytes(12)
        session._install_party_getter_checks = session._install_heap_lifetime_observer = lambda: None
        session._install_native_free_guard = lambda: None
        # Clock/absence transport fixture; real lifecycle reads have their own
        # installed-sampler tests in test_devtools_field_availability.py.
        session._field_actor_availability = lambda field: {"reason": None}
        session.party_getter_hooks = SimpleNamespace(error=None)
        session.party_getter_checks = {}
        session.completed_frames, session.sample_error, session.step_release_at_frame = 3, None, None
        session.pending_samples, session.latest_profile_keys, session.latest_resolved_profiles = [], (), []
        session.prepared, session.rom_hash, session.save_hash = False, "a" * 64, "b" * 64
        session.observer_control, session.trace_request = None, None
        session.trace_observing, session.trace_events, session.trace_events_dropped = True, [], 0
        session.trace_pending, session.trace_pending_dropped = [], 0
        session.semantic_trace = SimpleNamespace(sample=lambda frame: trace_frames.append(frame) or [])
        def field_snapshot(*args, **kwargs):
            reads.append("field")
            return {**snapshot(session.completed_frames), "nativeCycle": session.rt.EXECUTED_FRAME_COUNT,
                    "nativeObservation": session.native_observation.snapshot()}
        session._snapshot = field_snapshot
        session._read_party_at_boundary = lambda: reads.append("party") or []
        session._selector_observation = lambda: reads.append("selector") or {}
        session._dialogue_observation = lambda field: {
            "fieldPointer": field, "frame": session.completed_frames, "state": "idle"}
        session.party_snapshot = lambda: reads.append("party-endpoint") or []
        session.terrain = lambda radius: reads.append("terrain-endpoint") or {"terrain": {}}
        session.latest_frame = {**snapshot(3), "nativeObservation": {"profileFingerprints": []}}
        class Native:
            def __init__(self, *args):
                self.frame, self.ready, self.hooks = 3, [], session.party_getter_hooks
            def install(self): pass
            def completed_frame(self, frame):
                self.frame = frame
                self.ready.append({"frame": frame, "kind": "native-observation", "data": {"sequence": frame}})
            def snapshot(self, **kwargs):
                return {"profileFingerprints": [], "resolvedProfiles": [], "sequence": self.frame,
                        "playerStepFrame": self.frame, "pendingUnframedEvents": 0,
                        "error": session.party_getter_hooks.error,
                        "coverageComplete": session.party_getter_hooks.error is None}
            def drain(self):
                result, self.ready = self.ready, []
                return result
        with patch("tools.overworld.devtools_observer.NativeObservation", Native): session._install_sampler()
        def boundary(): callbacks[session.sampling_hook](session.sampling_hook, 4)
        return session, memory, boundary, reads, releases, trace_frames

    def test_null_field_and_invalid_actor_magic_each_record_exact_absence(self):
        for field, magic, reasons in (
            (0, 0x5353574F, ["null-field-pointer"]),
            (0x02003000, 0, ["actor-system-uninitialized"]),
            (0, 0xBAD, ["null-field-pointer", "actor-system-uninitialized"]),
        ):
            with self.subTest(field=field, magic=magic):
                session, memory, boundary, reads, _, trace_frames = self.fixture()
                memory[0x02001000], memory[0x02002000] = field, magic
                boundary()
                self.assertEqual(len(session.pending_samples), 1)
                row = session.pending_samples[0]
                self.assertIs(row["fieldAvailable"], False)
                self.assertEqual(row["fieldAvailability"], {"fieldPointer": field,
                    "actorStateMagic": magic, "reasons": reasons})
                self.assertEqual((row["frame"], row["nativeCycle"]), (4, 7))
                self.assertEqual(row["observationBoundary"], "main-task-queue-completion")
                self.assertEqual((row["romSha256"], row["sourceSaveSha256"]), ("a" * 64, "b" * 64))
                self.assertFalse(row["prepared"])
                self.assertEqual(row["observationErrors"], [])
                self.assertEqual(row["nativeObservation"]["sequence"], 4)
                self.assertEqual(row["nativeObservation"]["playerStepFrame"], 4)
                self.assertFalse(set(row) & {"actors", "player", "party", "terrain", "context", "actorFrame", "selector"})
                self.assertEqual(session.snapshot(), row)
                self.assertEqual(reads, [])
                self.assertEqual(trace_frames, [4])
                self.assertEqual(session.drain_events()[0]["frame"], 4)

    def test_mixed_step_keeps_all_completed_rows_and_native_cycles(self):
        session, memory, boundary, _, _, trace_frames = self.fixture()
        fields = iter((0x02003000, 0, 0x02003000))
        def cycle(*args):
            session.rt.EXECUTED_FRAME_COUNT += 1
            memory[0x02001000] = next(fields)
            boundary()
        session.cycle = cycle
        result = session.step(3, [])  # Queue/absence coverage, not a keypad fixture.
        self.assertEqual([row["frame"] for row in result["samples"]], [4, 5, 6])
        self.assertEqual([row["fieldAvailable"] for row in result["samples"]], [True, False, True])
        self.assertEqual(result["completedGameFrames"], 3)
        self.assertEqual(result["observedFieldFrames"], 2)
        self.assertEqual(result["nativeCycles"], 3)
        self.assertEqual([row["completedGameFrame"] for row in result["cycleIntervals"]], [4, 5, 6])
        self.assertEqual([event["frame"] for event in result["events"]], [4, 5, 6])
        self.assertEqual(trace_frames, [4, 5, 6])
        self.assertEqual(result["snapshot"]["frame"], 6)
        self.assertIsNone(session.sample_error)

    def test_step_ending_without_field_does_not_enrich_cached_endpoint(self):
        session, memory, boundary, reads, releases, _ = self.fixture()
        memory[0x02001000] = 0
        session.cycle = lambda *args: boundary()
        result = session.step(1, [])
        self.assertEqual(result["completedGameFrames"], 1)
        self.assertEqual(result["observedFieldFrames"], 0)
        self.assertEqual(result["snapshot"], result["samples"][0])
        self.assertEqual(reads, [])
        self.assertTrue(releases)

    def test_checked_step_preserves_samples_without_extra_terrain_reads(self):
        outputs = []
        for detailed in (True, False):
            session, _memory, boundary, reads, _releases, _ = self.fixture()
            def cycle(*args):
                session.rt.EXECUTED_FRAME_COUNT += 1
                boundary()
            session.cycle = cycle
            result = session.step(1, [], diagnostic_details=detailed)
            if detailed:
                self.assertIn("terrain-endpoint", reads)
                self.assertIn("terrain", result["snapshot"])
            else:
                self.assertNotIn("terrain-endpoint", reads)
                self.assertNotIn("party-endpoint", reads)
                self.assertNotIn("terrain", result["snapshot"])
            outputs.append(result)
        for key in ("samples", "events", "completedGameFrames", "nativeCycles", "observedFieldFrames"):
            self.assertEqual(outputs[0][key], outputs[1][key], key)

    def test_readback_wait_retains_absent_callback_rows_and_trace(self):
        session, memory, boundary, _, _, trace_frames = self.fixture()
        fields, predicate_frames = iter((0, 0, 0x02003000)), []
        def cycle(*args):
            session.rt.EXECUTED_FRAME_COUNT += 1
            memory[0x02001000] = next(fields)
            boundary()
        session.cycle = cycle
        def predicate(value):
            predicate_frames.append(value["frame"])
            return value["context"]["fieldEpoch"] == 1
        value = session._wait_new_frame(3, predicate, native_limit=3, code="readback", message="missing field")
        self.assertEqual(value["frame"], 6)
        self.assertEqual(predicate_frames, [6])
        self.assertEqual([row["fieldAvailable"] for row in session.pending_samples], [False, False, True])
        self.assertEqual([row["nativeCycle"] for row in session.pending_samples], [8, 9, 10])
        self.assertEqual(trace_frames, [4, 5, 6])
        self.assertEqual([event["frame"] for event in session.drain_events()], [4, 5, 6])

    def test_absence_preserves_observer_error_and_does_not_become_success(self):
        session, memory, boundary, reads, _, _ = self.fixture()
        memory[0x02001000] = 0
        session.party_getter_hooks.error = "native getter value differs"
        boundary()
        self.assertEqual(len(session.pending_samples), 1)
        row = session.pending_samples[0]
        self.assertEqual(row["nativeObservation"]["error"], "native getter value differs")
        self.assertFalse(row["nativeObservation"]["coverageComplete"])
        self.assertEqual(row["observationErrors"], [{"code": "party-getter-mismatch",
                                                  "message": "native getter value differs"}])
        self.assertIsInstance(session.sample_error, DevtoolsFailure)
        with self.assertRaisesRegex(DevtoolsFailure, "native getter value differs"): session.snapshot()
        self.assertEqual(reads, [])

    def test_absent_trace_drain_preserves_event_frame_and_invalid_ring_notice(self):
        session, memory, boundary, _, _, _ = self.fixture()
        memory[0x02002000] = 0
        session.trace_pending = [{"frame": 0, "kind": "native", "data": {"actorFrame": 61}}]
        session.semantic_trace.sample = lambda frame: [{"frame": frame, "kind": "trace-status",
            "data": {"code": "invalid-native-ring", "coverageComplete": False}}]
        boundary()
        events = session.drain_events()
        self.assertEqual([event["frame"] for event in events], [4, 4, 4])
        self.assertEqual(events[0]["data"]["actorFrame"], 61)
        self.assertEqual(events[1]["data"]["code"], "invalid-native-ring")
        self.assertFalse(events[1]["data"]["coverageComplete"])
        self.assertEqual(session.trace_pending, [])

    def test_trace_control_waits_for_field_without_dropping_absent_frame(self):
        session, memory, boundary, _, _, trace_frames = self.fixture()
        memory[0x02001000] = 0
        session.trace_observing = False
        starts = []
        session.semantic_trace.start = lambda frames: starts.append(frames)
        session.trace_request = {"operation": "start", "maxFrames": 60, "complete": False, "error": None}
        boundary()
        self.assertEqual(starts, [])
        self.assertFalse(session.trace_request["complete"])
        self.assertFalse(session.pending_samples[0]["fieldAvailable"])
        memory[0x02001000] = 0x02003000
        boundary()
        self.assertEqual(starts, [60])
        self.assertTrue(session.trace_request["complete"])
        self.assertEqual(trace_frames, [5])
        self.assertEqual([row["frame"] for row in session.pending_samples], [4, 5])

    def test_step_failure_keeps_absence_row_and_timing_in_error_details(self):
        session, memory, boundary, reads, releases, _ = self.fixture()
        memory[0x02001000] = 0
        session.party_getter_hooks.error = "native getter value differs"
        session.cycle = lambda *args: boundary()
        session.diagnostics = lambda: {"scope": "host fixture"}
        with self.assertRaises(DevtoolsFailure) as caught: session.step(1, [])
        details = caught.exception.details
        self.assertEqual(details["completedGameFrames"], 1)
        self.assertEqual(len(details["cycleIntervals"]), 1)
        self.assertFalse(details["recentSamples"][0]["fieldAvailable"])
        self.assertEqual(details["recentSamples"][0]["observationErrors"][0]["code"], "party-getter-mismatch")
        self.assertEqual(reads, [])
        self.assertTrue(releases)

    def test_later_hook_error_cannot_hide_behind_cached_absence(self):
        session, memory, boundary, reads, _, _ = self.fixture()
        memory[0x02001000] = 0
        boundary()
        session.party_getter_hooks.error = "later native return differs"
        with self.assertRaisesRegex(DevtoolsFailure, "later native return differs"): session.snapshot()
        self.assertEqual(session.latest_frame["nativeObservation"]["error"], None)
        self.assertEqual(session.latest_frame["frame"], 4)
        self.assertEqual(reads, [])

    def test_default_evaluator_rejects_recorded_absence_even_without_subject(self):
        from tools.overworld.test_devtools_test_contract import recipe, TestEvaluator
        session, memory, boundary, _, _, _ = self.fixture()
        memory[0x02001000] = 0
        boundary()
        for with_subject in (False, True):
            value = recipe()
            if not with_subject:
                value["subjects"] = []
                value["assertions"] = [{"kind": "frame-count", "operator": "gte", "value": 1}]
            evaluator = TestEvaluator(value)
            result = evaluator.observe(session.pending_samples[0])
            self.assertEqual(result["state"], "failed")
            self.assertFalse(result["acceptedProof"])
            self.assertEqual(result["observedFrames"], 0)
            self.assertIn("actor list", result["failures"][0]["message"])


class TraceAndClockTests(unittest.TestCase):
    def fixture(self):
        ring = NativeRing()
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.rt = SimpleNamespace(ACTOR_DESCRIPTOR=ring.descriptor, REPO=Path(__file__).resolve().parents[2],
                                     actor_memory_write=lambda emu, address, data: ring.write(address, data),
                                     h=SimpleNamespace(set_key_mask=lambda *args: None,
                                                       keymask=lambda value: value, key_constant=lambda name: 1))
        session.read = ring.read
        session.emu = object()
        session.prepared, session.sample_error = False, None
        session.completed_frames = 40
        session.semantic_trace, session.trace_request = None, None
        # This fixture tests queue publication; the installed native writer
        # callback is exercised separately by test_devtools_trace_publication.
        session._install_trace_publication = lambda: None
        session.native_observation = None
        session.trace_events, session.trace_events_dropped, session.trace_observing = [], 0, False
        session.snapshot = lambda: {"frame": session.completed_frames, "prepared": session.prepared}
        session.cycle = lambda frames: self.boundary(session)
        return session, ring

    def boundary(self, session):
        session.completed_frames += 1
        session._complete_trace_boundary()

    def test_record_controls_use_real_public_ring_without_prepared_mode(self):
        session, ring = self.fixture()
        original_cycle = session.cycle
        def cycle(frames):
            self.assertEqual(ring.writes, [])  # start was not done at arbitrary endpoint
            original_cycle(frames)
        session.cycle = cycle
        started = session.record_start(60)
        self.assertTrue(started["recording"])
        self.assertFalse(session.prepared)
        self.assertIn("window-started", notices(started["events"]))
        ring.emit(13, frame=101)
        self.boundary(session)
        events = session.drain_events()
        self.assertEqual(natives(events)[0]["event"], "LOGICAL_COMMIT")
        self.assertEqual(events[0]["frame"], 42)
        self.assertEqual(natives(events)[0]["actorFrame"], 101)
        session.cycle = original_cycle
        stopped = session.record_stop()
        self.assertFalse(stopped["recording"])
        self.assertFalse(session.prepared)
        self.assertIn("window-ended", notices(stopped["events"]))
        self.assertEqual(ring.values()[13], 0)

    def test_instrumentation_transport_rejects_other_addresses_and_nonzero_ring(self):
        session, ring = self.fixture()
        for address, data in ((ring.base, bytes(4)), (ring.base + ring.header + 1, bytes(36)),
                              (ring.base + ring.events, b"\x01" * 512)):
            with self.subTest(address=address), self.assertRaises(DevtoolsFailure):
                session._trace_write(address, data)
        self.assertEqual(ring.writes, [])

    def test_worker_trace_overflow_is_explicit_without_fake_native_records(self):
        session, ring = self.fixture()
        session.record_start(60)
        session.trace_events = [{"frame": 1, "kind": "trace-status", "data": {"code": "fixture"}}] * 4096
        ring.emit(13)
        self.boundary(session)
        events = session.drain_events()
        self.assertEqual(notices(events)["worker-event-buffer-overflow"]["count"], 1)
        self.assertEqual(natives(events), [])
        self.assertEqual(session.drain_events(), [])

    def test_step_counts_complete_game_frames_not_native_cycles(self):
        session, _ = self.fixture()
        cycles = []
        def cycle(frames, mask):
            cycles.append(mask)
            if len(cycles) % 2 == 0:
                session.completed_frames += 1
                session.pending_samples.append({"frame": session.completed_frames})
        session.cycle = cycle
        result = session.step(3, [])  # Input-poll timing has its own native-phase fixture.
        self.assertEqual(result["nativeCycles"], 6)
        self.assertEqual(result["completedGameFrames"], 3)
        self.assertEqual([sample["frame"] for sample in result["samples"]], [41, 42, 43])
        self.assertEqual(natives(result["events"]), [])
        self.assertIsNone(session.step_release_at_frame)

    def test_missing_main_queue_is_bounded_and_releases_input(self):
        session, _ = self.fixture()
        cycles, released = [], []
        session.cycle = lambda *args: cycles.append(args)
        session.rt.h.set_key_mask = lambda emu, mask: released.append(mask)
        with self.assertRaisesRegex(DevtoolsFailure, "only 0/2"):
            session.step(2, [])
        self.assertEqual(len(cycles), 120)
        self.assertEqual(released, [0])
        self.assertIsNone(session.pending_samples)

    def test_complete_transition_receipt_is_not_busy(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.emu = object()
        phase = [4]
        session.field_pointer = lambda: 0x02001000
        def unsigned(emu, address, size=4):
            return phase[0] if address == 0x02002000 + 40 else 0
        session.rt = SimpleNamespace(unsigned=unsigned, SELECTOR_STATE=0x02003000,
                                     ACTOR_DESCRIPTOR={"state": {"address": 0x02002000}},
                                     actor_state=lambda *args: {"active": False},
                                     player_ptr=lambda emu: 0x02004000,
                                     object_state=lambda *args: {"flags": 1, "x": 4, "y": 5,
                                       "pos_x": (4 << 16) + 0x8000, "pos_z": (5 << 16) + 0x8000})
        for value in (0, 4):
            phase[0] = value
            session.require_quiescent()
        for value in (1, 2, 3, 5):
            phase[0] = value
            with self.assertRaisesRegex(DevtoolsFailure, f"phase={value}"):
                session.require_quiescent()

    def test_close_disarms_public_trace_before_destroying_core(self):
        session, ring = self.fixture()
        session.record_start(60)
        order = []
        session.sampling_hook, session.party_getter_hooks = None, None
        def destroyed():
            self.assertEqual(ring.values()[13], 0)
            order.append("destroyed")
        session.emu = SimpleNamespace(destroy=destroyed)
        session.close()
        self.assertEqual(order, ["destroyed"])
        self.assertIsNone(session.emu)
        self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()

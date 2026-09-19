"""Exercise the real Python boundary with a fake C ABI; never load a core."""
import ctypes as C
import struct
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.overworld import melonds_backend as backend


class FakeLibrary:
    def __init__(self):
        self.calls = []
        self.data = {}
        self.registers = {}
        self.hooks = {}
        self.on_frame = None
        self.aborted = False
        self.dispatch = backend.DispatchCounts(1,0,0,0,0)
        self.phases = backend.PhaseTimings(2,0,0)
        self.profile = backend.InstructionProfile(1,0,0,0,0)
        self.guest = (1,0,101,53,7)

    def md_profile_enable(self, handle, enabled):
        self.calls.append(("profile-enable", enabled))
        if self.aborted and enabled:return -1
        self.profile = backend.InstructionProfile(1,enabled,0,0,0)
        return 0

    def md_profile_read(self, handle, out, length):
        if length != C.sizeof(self.profile):return -1
        C.memmove(out, C.byref(self.profile), length)
        return 0

    def md_read_guest_clock(self, handle, out, length):
        self.calls.append(("guest-clock-read",length))
        if self.aborted or length != 32:return -1
        C.memmove(out,struct.pack("=IIQQQ",*self.guest),length)
        return 0

    def md_set_phase_timing(self, handle, enabled):
        self.calls.append(("phase-enable",enabled))
        if self.aborted and enabled:return -1
        if bool(self.phases.flags&1)!=bool(enabled):
            self.phases=backend.PhaseTimings(2,enabled,self.phases.frame_sequence)
        return 0

    def md_read_phase_timing(self, handle, out, length):
        self.calls.append(("phase-read",length))
        if length!=64:return -1
        C.memmove(out,C.byref(self.phases),length)
        return 0

    def md_set_dispatch_counts(self, handle, enabled):
        self.calls.append(("dispatch-enable",enabled))
        if enabled not in (0,1) or self.aborted and enabled:return -1
        if bool(self.dispatch.flags&1)!=bool(enabled):
            self.dispatch.flags=enabled;self.dispatch.arm9=self.dispatch.arm7=0
        return 0

    def md_read_dispatch_counts(self, handle, out, length):
        self.calls.append(("dispatch-read",length))
        if length!=32:return -1
        C.memmove(out,C.byref(self.dispatch),length)
        return 0

    def md_create(self):
        self.calls.append(("create",))
        return 123

    def md_destroy(self, handle):
        self.calls.append(("destroy", handle))

    def md_last_error(self, handle):
        return b"native error"

    def md_read_bytes(self, handle, cpu, address, buffer, length):
        self.calls.append(("read", cpu, address, length))
        C.memmove(buffer, bytes(self.data.get(address+i, 0) for i in range(length)), length)
        return 0

    def md_write_bytes(self, handle, cpu, address, buffer, length):
        data = C.string_at(buffer, length)
        self.calls.append(("write", cpu, address, data, length))
        self.data.update((address+i, byte) for i, byte in enumerate(data))
        return 0

    def md_get_reg(self, handle, cpu, index):
        self.calls.append(("get-reg", cpu, index))
        return self.registers.get((cpu, index), 0)

    def md_set_reg(self, handle, cpu, index, value):
        self.calls.append(("set-reg", cpu, index, value))
        self.registers[cpu, index] = value
        return 0

    def md_next_pc(self, handle, cpu):
        self.calls.append(("next-pc", cpu))
        return 0x02000102

    def md_branch(self, handle, cpu, address):
        self.calls.append(("branch", cpu, address))
        return 0

    def md_hook_exec(self, handle, cpu, address, callback, user):
        return self._hook("exec", cpu, address, 1, callback)

    def md_hook_write(self, handle, cpu, address, size, callback, user):
        return self._hook("write", cpu, address, size, callback)

    def _hook(self, kind, cpu, address, size, callback):
        self.calls.append(("hook", kind, cpu, address, size, bool(callback)))
        key = kind, address, size
        if callback:
            self.hooks[key] = callback
        else:
            self.hooks.pop(key, None)
        return 0

    def md_run_frame(self, handle):
        self.calls.append(("frame",))
        self.dispatch.flags &= 1
        self.dispatch.frame_sequence += 1
        self.dispatch.arm9,self.dispatch.arm7=(13,7) if self.dispatch.flags else (0,0)
        self.phases.flags &= 1
        self.phases.frame_sequence += 1
        for i,row in enumerate(self.phases.rows):
            row.cpu_ns,row.calls=((i+1)*100,i+1) if self.phases.flags else (0,0)
        if not self.aborted and self.on_frame is not None:
            self.on_frame()
        if not self.aborted:self.dispatch.flags |= 2
        if not self.aborted:self.phases.flags |= 2
        return -1 if self.aborted else 0

    def md_abort(self, handle, reason):
        self.calls.append(("abort", reason))
        self.aborted = True

    def md_open_rom(self, handle, path):
        self.calls.append(("open", path))
        return 0

    def md_import_save(self, handle, path):
        self.calls.append(("save", path))
        return 0

    def md_set_keys(self, handle, mask):
        self.calls.append(("keys", mask))
        return 0

    def md_touch(self, handle, x, y):
        self.calls.append(("touch",x,y))
        return 0

    def md_release_touch(self, handle):
        self.calls.append(("release-touch",))
        return 0

    def md_save_size(self, handle):
        return 4

    def md_read_save(self, handle, buffer, length):
        C.memmove(buffer,b"save",length)
        return 0


class MelonDSBoundaryTests(unittest.TestCase):
    def test_instruction_profile_layout_counts_and_invalid_receipts(self):
        self.assertEqual(C.sizeof(backend.InstructionProfile), 262176)
        self.assertEqual(backend.InstructionProfile.bins.offset, 32)
        self.assertFalse(self.core.instruction_profile()["enabled"])
        self.core.enable_instruction_profile(True)
        self.lib.profile.flags = 3
        self.lib.profile.frame_sequence = 42
        self.lib.profile.total = 10
        self.lib.profile.unmapped = 3
        self.lib.profile.bins[1] = 7
        result = self.core.instruction_profile()
        self.assertEqual(result["bins"], [[0x02000040, 7]])
        self.assertEqual(result["total"], 10)
        result["bins"][0][1] = 0
        self.assertEqual(self.core.instruction_profile()["bins"][0][1], 7)
        self.lib.profile.total = 11
        with self.assertRaisesRegex(RuntimeError, "totals differ"):
            self.core.instruction_profile()
        self.lib.profile.flags = 7
        with self.assertRaisesRegex(RuntimeError, "invalid"):
            self.core.instruction_profile()
        self.core.enable_instruction_profile(False)
        self.assertEqual(self.core.instruction_profile()["total"], 0)

    def test_explicit_export_and_touch_do_not_advance_or_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"copy.sav"
            self.assertTrue(self.core.backup.export_file(path))
            self.assertEqual(path.read_bytes(),b"save")
        self.core.input.touch_set_pos(255,191)
        self.core.input.touch_release()
        self.assertIn(("touch",255,191),self.lib.calls)
        self.assertIn(("release-touch",),self.lib.calls)
        self.assertNotIn(("frame",),self.lib.calls)
        for x,y in ((256,0),(0,192),(-1,0)):
            with self.assertRaises(ValueError):self.core.input.touch_set_pos(x,y)

    def setUp(self):
        self.lib = FakeLibrary()
        self.core = backend.MelonDS(self.lib)
        self.addCleanup(self.core.destroy)

    def test_guest_clock_reads_exact_detached_values_without_stepping(self):
        self.assertEqual(C.sizeof(backend.GuestClockValue),32)
        self.assertEqual([getattr(backend.GuestClockValue,k).offset for k in
            ("version","flags","arm9_timestamp","arm7_timestamp","frame_sequence")],[0,4,8,16,24])
        value = self.core.guest_clock()
        self.assertEqual(value, dict(version=1,running=False,arm9Timestamp=101,
            arm7Timestamp=53,frameSequence=7,scope="nds-scheduler-ticks-not-cpu-or-instructions"))
        value["arm9Timestamp"] = 0
        self.assertEqual(self.core.guest_clock()["arm9Timestamp"],101)
        self.assertEqual(self.lib.calls,[("create",),("guest-clock-read",32),("guest-clock-read",32)])

    def test_guest_clock_callback_and_full_width_unsigned_values(self):
        values=[]
        self.lib.guest=(1,1,(1<<64)-1,1<<63,99)
        self.core.memory.register_exec(0x02000100,lambda address,width: values.append(self.core.guest_clock()))
        self.lib.hooks["exec",0x02000100,1](0,0x02000100,4,None)
        self.assertEqual(len(values),1)
        self.assertTrue(values[0]["running"])
        self.assertEqual(values[0]["arm9Timestamp"],(1<<64)-1)
        self.assertEqual(values[0]["arm7Timestamp"],1<<63)
        self.assertNotIn(("frame",),self.lib.calls)

    def test_guest_clock_rejects_schema_native_fault_closed_and_callback_fault(self):
        for version,flags in ((0,0),(2,0),(1,2),(1,0xffffffff)):
            self.lib.guest=(version,flags,0,0,0)
            with self.assertRaisesRegex(RuntimeError,"guest clock schema"):
                self.core.guest_clock()
        self.lib.guest=(1,0,0,0,0)
        self.lib.aborted=True
        with self.assertRaisesRegex(RuntimeError,"native error"):self.core.guest_clock()
        self.lib.aborted=False
        original=ValueError("first callback fault")
        self.core.callback_error=original
        count=len(self.lib.calls)
        with self.assertRaises(ValueError) as failure:self.core.guest_clock()
        self.assertIs(failure.exception,original)
        self.assertEqual(len(self.lib.calls),count)
        self.core.destroy()
        with self.assertRaisesRegex(RuntimeError,"closed"):self.core.guest_clock()

    def test_dispatch_counts_opt_in_fixed_layout_reset_and_detached_receipt(self):
        self.assertEqual(C.sizeof(backend.DispatchCounts),32)
        self.assertEqual([getattr(backend.DispatchCounts,k).offset for k in
                          ("version","flags","frame_sequence","arm9","arm7")],[0,4,8,16,24])
        self.assertFalse(self.core.dispatch_counts()["enabled"])
        self.assertFalse(self.core.enable_dispatch_counts(True))
        self.assertTrue(self.core.enable_dispatch_counts(True))
        self.core.cycle();first=self.core.dispatch_counts()
        self.assertEqual(first,dict(version=1,enabled=True,complete=True,frameSequence=1,
            arm9=13,arm7=7,scope="interpreter-dispatches-not-retired-instructions"))
        self.core.cycle();second=self.core.dispatch_counts()
        self.assertEqual((second["frameSequence"],second["arm9"]),(2,13))
        first["arm9"]=999
        self.assertEqual(self.core.dispatch_counts()["arm9"],13)
        self.assertTrue(self.core.enable_dispatch_counts(False))
        self.core.cycle();self.assertEqual(self.core.dispatch_counts()["arm9"],0)

    def test_phase_fixed_layout_opt_in_and_detached_readback(self):
        self.assertEqual(C.sizeof(backend.PhaseTimings),64)
        self.assertEqual([getattr(backend.PhaseTimings,k).offset for k in
                          ("version","flags","frame_sequence","rows")],[0,4,8,16])
        self.assertEqual(C.sizeof(backend.PhaseRow),16)
        self.assertEqual(backend.PhaseRow.calls.offset,8)
        self.assertFalse(self.core.phase_timings()["enabled"])
        self.assertFalse(self.core.enable_phase_timings(True))
        self.assertTrue(self.core.enable_phase_timings(True))
        self.core.cycle();first=self.core.phase_timings()
        self.assertEqual(first,dict(version=2,enabled=True,complete=True,invalid=False,
            frameSequence=1,phases={name:dict(cpuNs=(i+1)*100,calls=i+1) for i,name in
            enumerate(("nonRender","render3d","render2d"))},
            scope="native-exclusive-thread-cpu-diagnostic-v2"))
        first["phases"]["nonRender"]["cpuNs"]=999
        self.assertEqual(self.core.phase_timings()["phases"]["nonRender"]["cpuNs"],100)
        self.core.cycle();self.assertEqual(self.core.phase_timings()["frameSequence"],2)
        self.assertTrue(self.core.enable_phase_timings(False))
        self.core.cycle();self.assertEqual(self.core.phase_timings()["phases"]["nonRender"]["calls"],0)

    def test_phase_fault_read_disable_and_invalid_receipt_preserve_first_error(self):
        self.core.enable_phase_timings(True)
        original=RuntimeError("first native callback fault")
        def fail():
            self.core.callback_error=original;self.lib.aborted=True
            self.lib.phases.flags |= 4
        self.lib.on_frame=fail
        with self.assertRaises(RuntimeError) as caught:self.core.cycle()
        self.assertIs(caught.exception,original)
        value=self.core.phase_timings()
        self.assertTrue(value["invalid"]);self.assertFalse(value["complete"])
        self.assertEqual(value["phases"]["nonRender"]["cpuNs"],100)
        before=list(self.lib.calls)
        with self.assertRaises(RuntimeError) as caught:self.core.enable_phase_timings(True)
        self.assertIs(caught.exception,original);self.assertEqual(self.lib.calls,before)
        self.core.enable_phase_timings(False)
        self.assertIs(self.core.callback_error,original)

    def test_phase_bad_enable_schema_read_error_and_closed_core(self):
        for enabled in (0,1,None,"yes"):
            with self.assertRaises(ValueError):self.core.enable_phase_timings(enabled)
        for version,flags,cpu in ((1,0,0),(2,8,0),(2,0,1)):
            self.lib.phases=backend.PhaseTimings(version,flags,0)
            self.lib.phases.rows[0].cpu_ns=cpu
            with self.assertRaises(RuntimeError):self.core.phase_timings()
        with patch.object(self.lib,"md_read_phase_timing",return_value=-1):
            with self.assertRaisesRegex(RuntimeError,"native error"):self.core.phase_timings()
        self.core.destroy()
        with self.assertRaisesRegex(RuntimeError,"closed"):self.core.phase_timings()

    def test_dispatch_partial_fault_read_and_disable_preserve_original_error(self):
        self.core.enable_dispatch_counts(True)
        original=RuntimeError("first native callback fault")
        def fail():
            self.core.callback_error=original;self.lib.aborted=True
        self.lib.on_frame=fail
        with self.assertRaises(RuntimeError) as caught:self.core.cycle()
        self.assertIs(caught.exception,original)
        receipt=self.core.dispatch_counts()
        self.assertFalse(receipt["complete"]);self.assertEqual(receipt["arm9"],13)
        self.core.enable_dispatch_counts(False)
        self.assertIs(self.core.callback_error,original)
        with self.assertRaises(RuntimeError) as caught:self.core.cycle()
        self.assertIs(caught.exception,original)

    def test_dispatch_bad_enable_schema_and_native_error_reject(self):
        for value in (0,1,None,"yes"):
            with self.assertRaises(ValueError):self.core.enable_dispatch_counts(value)
        for version,flags,arm9 in ((2,0,0),(1,4,0),(1,0,1)):
            self.lib.dispatch=backend.DispatchCounts(version,flags,0,arm9,0)
            with self.assertRaises(RuntimeError):self.core.dispatch_counts()
        with patch.object(self.lib,"md_read_dispatch_counts",return_value=-1):
            with self.assertRaisesRegex(RuntimeError,"native error"):self.core.dispatch_counts()
        self.core.destroy()
        with self.assertRaisesRegex(RuntimeError,"closed"):self.core.dispatch_counts()

    def test_bulk_and_scalar_signed_unsigned_reads_use_one_exact_native_span(self):
        self.lib.data.update(enumerate(b"\xff\x80\x34\x12\x00\x00\x00\x80", 0x2000000))
        for view, width, expected in (
            (self.core.memory.unsigned, 1, 255),
            (self.core.memory.signed, 1, -1),
            (self.core.memory.unsigned, 2, 0x80ff),
            (self.core.memory.signed, 2, -32513),
            (self.core.memory.unsigned, 4, 0x123480ff),
        ):
            with self.subTest(width=width, signed=view.signed):
                self.assertEqual(view[0x2000000:0x2000000:width], expected)
                self.assertEqual(self.lib.calls[-1], ("read", 0, 0x2000000, width))
        self.assertEqual(self.core.memory.signed[0x2000004:0x2000004:4], -2147483648)
        self.assertEqual(self.core.memory.unsigned[0x2000000:0x2000008:2], [0x80ff, 0x1234, 0, 0x8000])
        self.assertEqual(self.lib.calls[-1], ("read", 0, 0x2000000, 8))
        self.assertEqual(self.core.memory.signed[0x2000000:0x2000002:1], [-1, -128])

    def test_block_decode_copies_native_buffer_once(self):
        class Buffer:
            copies = 0
            @property
            def raw(self):
                self.copies += 1
                return b"\xff\x80\x34\x12\x00\x00\x00\x80"

        class Core:
            def call(self, name, cpu, address, buffer, length):
                self.last = (name, cpu, address, length)

        for signed in (False, True):
            for width in (1, 2, 4):
                with self.subTest(signed=signed, width=width):
                    buffer, core = Buffer(), Core()
                    expected = [int.from_bytes(buffer.raw[i:i+width], "little", signed=signed)
                                for i in range(0, 8, width)]
                    buffer.copies = 0
                    with patch.object(backend.C, "create_string_buffer", return_value=buffer):
                        actual = backend.MemoryValues(core, signed)[0x2000000:0x2000008:width]
                    self.assertEqual(actual, expected)
                    self.assertEqual(core.last, ("md_read_bytes", 0, 0x2000000, 8))
                    self.assertEqual(buffer.copies, 1)

    def test_writes_preserve_width_sign_length_and_do_not_append_buffer_nul(self):
        self.core.memory.unsigned[0x2000000:0x2000004:2] = [0x1234, 0xffff]
        self.assertEqual(self.lib.calls[-1], ("write", 0, 0x2000000, b"\x34\x12\xff\xff", 4))
        self.core.memory.signed[0x2000004:0x2000004:4] = -2147483648
        self.assertEqual(self.lib.calls[-1], ("write", 0, 0x2000004, b"\0\0\0\x80", 4))
        self.core.memory.unsigned[0x2000008:0x200000b:1] = b"\0\xff\x80"
        self.assertEqual(self.lib.calls[-1][-2:], (b"\0\xff\x80", 3))
        for value in ([1], [1, 2, 3]):
            before = len(self.lib.calls)
            with self.assertRaises(ValueError):
                self.core.memory.unsigned[0x2000000:0x2000002:1] = value
            self.assertEqual(len(self.lib.calls), before)

    def test_invalid_memory_spans_fail_before_native_call(self):
        for key in (3, slice(-1, 2, 1), slice(4, 2, 1), slice(0, 3, 2),
                    slice(0, 4, 3), slice(0xffffffff, 0xffffffff, 4),
                    slice(0, 0x1000001, 1)):
            with self.subTest(key=key):
                before = len(self.lib.calls)
                with self.assertRaises((TypeError, ValueError)):
                    self.core.memory.unsigned[key]
                self.assertEqual(len(self.lib.calls), before)

    def test_both_cpu_register_banks_and_aliases_include_status_registers(self):
        for cpu, regs in enumerate((self.core.memory.register_arm9, self.core.memory.register_arm7)):
            for index in range(18):
                name = f"r{index}" if index < 16 else ("cpsr" if index == 16 else "spsr")
                setattr(regs, name, 0x80000000 + cpu * 32 + index)
                self.assertEqual(getattr(regs, name), self.lib.registers[cpu, index])
            for name, index in (("sp", 13), ("lr", 14), ("pc", 15)):
                self.assertEqual(getattr(regs, name), self.lib.registers[cpu, index])
        for invalid in (-1, 0x100000000, True):
            with self.assertRaises(ValueError):
                self.core.memory.register_arm9.r0 = invalid
        with self.assertRaises(AttributeError):
            self.core.memory.register_arm9.not_a_register = 1

    def test_pipeline_branch_uses_current_cpsr_thumb_bit_not_pc_assignment(self):
        regs = self.core.memory.register_arm9
        for cpsr, target in ((0x1f, 0x2000400), (0x3f, 0x2000401)):
            regs.cpsr = cpsr
            regs.pc = 0x2000400
            self.core.memory.set_next_instruction(0x2000400)
            self.assertEqual(self.lib.calls[-1], ("branch", 0, target))
        self.assertEqual(self.core.memory.get_next_instruction(), 0x2000102)

    def test_callbacks_cross_real_ctypes_boundary_with_address_and_width(self):
        seen = []
        self.core.memory.register_exec(0x2000000, lambda address, size: seen.append((address, size)))
        self.lib.hooks["exec", 0x2000000, 1](0, 0x2000000, 2, None)
        self.core.memory.register_write(0, lambda address, size: seen.append((address, size)), size=428)
        self.lib.hooks["write", 0, 428](0, 184, 4, None)
        self.assertEqual(seen, [(0x2000000, 2), (184, 4)])

    def test_callback_failure_aborts_and_repeated_cycles_preserve_first_exception(self):
        first = ValueError("first reader fault")
        def fail(*unused):
            raise first
        self.core.memory.register_exec(0x2000000, fail)
        callback = self.lib.hooks["exec", 0x2000000, 1]
        self.lib.on_frame = lambda: callback(0, 0x2000000, 2, None)
        for unused in range(2):
            with self.assertRaises(ValueError) as caught:
                self.core.cycle(False)
            self.assertIs(caught.exception, first)
        self.assertTrue(self.lib.aborted)
        self.assertIs(self.core.callback_error, first)
        callback(1, 0x2000000, 2, None)
        with self.assertRaises(ValueError) as caught:
            self.core.cycle()
        self.assertIs(caught.exception, first)

    def test_wrong_cpu_callback_fails_closed_without_calling_arm9_reader(self):
        seen = []
        self.core.memory.register_exec(0x2000000, lambda *args: seen.append(args))
        self.lib.on_frame = lambda: self.lib.hooks["exec", 0x2000000, 1](1, 0x2000000, 4, None)
        with self.assertRaisesRegex(RuntimeError, "another CPU"):
            self.core.cycle()
        self.assertEqual(seen, [])
        self.assertTrue(self.lib.aborted)

    def test_latched_callback_fault_blocks_mutations_but_keeps_diagnostics_and_cleanup(self):
        first = ValueError("first reader fault")
        def fail(*unused):
            raise first
        self.core.memory.register_exec(0x2000000, fail)
        later = []
        self.core.memory.register_exec(0x2000002, lambda *args: later.append(args))
        self.lib.hooks["exec", 0x2000000, 1](0, 0x2000000, 2, None)
        self.lib.hooks["exec", 0x2000002, 1](0, 0x2000002, 2, None)
        self.assertEqual(later, [], "a later callback must not run after the first fault")
        operations = (
            lambda: self.core.input.keypad_update(1),
            lambda: self.core.memory.unsigned.__setitem__(slice(0x2000000, 0x2000000, 1), 1),
            lambda: setattr(self.core.memory.register_arm9, "r0", 7),
            lambda: self.core.memory.set_next_instruction(0x2000000),
            self.core.cycle,
            lambda: self.core.memory.register_exec(0x2000004, lambda *unused: None),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                before = len(self.lib.calls)
                with self.assertRaises(ValueError) as caught:
                    operation()
                self.assertIs(caught.exception, first)
                self.assertTrue(all(call[0] in ("read", "get-reg", "next-pc")
                                    for call in self.lib.calls[before:]),
                                "faulted operations must not reach a native mutation or cycle")
        self.assertEqual(self.core.memory.register_arm9.r0, 0)
        self.assertEqual(self.core.memory.register_arm7.cpsr, 0)
        self.assertEqual(self.core.memory.get_next_instruction(), 0x2000102)
        self.assertEqual(self.core.memory.unsigned[0x2000000:0x2000002:1], [0, 0])
        self.core.memory.register_exec(0x2000000, None)
        self.core.memory.register_exec(0x2000002, None)
        self.assertEqual(self.lib.hooks, {})
        self.assertIs(self.core.callback_error, first)

    def test_callback_removal_keeps_c_pointer_alive_until_cycle_returns(self):
        key = "exec", 0x2000000, 1
        def remove(*unused):
            old = self.core.callbacks[key]
            self.core.memory.register_exec(key[1], None)
            self.assertNotIn(key, self.core.callbacks)
            self.assertNotIn(key, self.lib.hooks)
            self.assertIn(old, self.core.retired)
        self.core.memory.register_exec(key[1], remove)
        self.lib.on_frame = lambda: self.lib.hooks[key](0, key[1], 2, None)
        self.core.cycle()
        self.assertEqual(self.core.retired, [])
        self.core.memory.register_exec(key[1], lambda *unused: None)
        old = self.core.callbacks[key]
        self.core.memory.register_exec(key[1], lambda *unused: None)
        self.assertIn(old, self.core.retired)

    def test_open_save_input_and_destroy_use_only_declared_native_abi(self):
        self.core.volume_set(0)
        self.core.open("fixture.nds")
        self.core.backup.import_file("fixture.sav", force_size=0)
        self.core.input.keypad_update(0xc01)
        self.assertEqual(self.lib.calls[-3:], [("open", b"fixture.nds"), ("save", b"fixture.sav"), ("keys", 0xc01)])
        with self.assertRaises(ValueError):
            self.core.backup.import_file("fixture.sav", force_size=1)
        with self.assertRaises(ValueError):
            self.core.input.keypad_update(0x1000)
        self.core.destroy()
        self.core.destroy()
        self.assertEqual(self.lib.calls.count(("destroy", 123)), 1)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            self.core.memory.register_arm9.cpsr

    def test_missing_melonds_library_has_no_alternate_core_fallback(self):
        error = FileNotFoundError("authenticated melonDS library is absent")
        with patch.object(backend, "load_library", side_effect=error) as load:
            with self.assertRaises(FileNotFoundError) as caught:
                backend.MelonDS()
        self.assertIs(caught.exception, error)
        load.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

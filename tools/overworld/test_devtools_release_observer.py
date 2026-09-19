import struct
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch
import json
import argparse

from tools.overworld.devtools_release_observer import ReleaseObserver, _effect_pool_diagnostic
from tools.overworld.devtools_contract import validate_command


class ReleaseDiagnosticsContractTests(unittest.TestCase):
    def test_follower_and_mount_opt_in_but_wild_rejects(self):
        for role in ("follower", "mounted"):
            for mode in ("write", "irq"):
                value = validate_command("spawn", {"species": 155, "role": role, "releaseDiagnostics": mode})
                self.assertEqual(value["releaseDiagnostics"], mode)
        self.assertNotIn("releaseDiagnostics", validate_command("spawn", {"species": 165}))
        for role, mode in (("wild", "irq"), ("wild", "write"), ("follower", "all"), ("follower", True)):
            with self.assertRaises(ValueError):
                validate_command("spawn", {"species": 155, "role": role, "releaseDiagnostics": mode})

    def test_generic_cli_retains_opt_in(self):
        from tools.overworld import devtools_cli
        parser = argparse.ArgumentParser()
        devtools_cli.register(parser.add_subparsers(required=True))
        args = parser.parse_args(["dev", "command", "spawn", "--args",
            '{"species":155,"role":"follower","slot":1,"releaseDiagnostics":"irq"}'])
        self.assertEqual(validate_command(args.dev_operation, args.dev_args)["releaseDiagnostics"], "irq")

    def test_runtime_spawn_passes_only_explicit_irq_and_rejects_wild_before_mutation(self):
        mon = {"species": 155, "isEgg": False, "hp": 21}
        calls = []
        session = NS(prepared=False, party_snapshot=lambda: [mon],
                     _spawn_party_subject=lambda *a, **kw: calls.append((a, kw)) or {},
                     _prepared_result_boundary=lambda value: value)
        for mode in (None, "irq"):
            args = {"role": "follower", "slot": 0, "species": 155}
            if mode:
                args["releaseDiagnostics"] = mode
            DevtoolsSession.spawn(session, args)
        self.assertEqual(calls[0][1], {})
        self.assertEqual(calls[1][1], {"release_diagnostics": "irq"})
        session.prepared = False
        with self.assertRaises(DevtoolsFailure):
            DevtoolsSession.spawn(session, {"species": 165, "releaseDiagnostics": "irq"})
        self.assertFalse(session.prepared)


class ReleaseProgressTests(unittest.TestCase):
    def fixture(self):
        session = NS(completed_frames=766, rt=NS(EXECUTED_FRAME_COUNT=1945),
                     native_bridge_active=False,
                     latest_frame={"frame": 765, "selector": {"followerReleaseState": 133}},
                     emu=NS(memory=NS(register_arm9=NS(pc=0x02001000, cpsr=0x3F, sp=0x027E3600))))
        return session, ReleaseObserver(session)

    def test_rate_limited_cached_progress_at_cycle_check(self):
        session, observer = self.fixture()
        observer.count, observer.write_count = 123, 2
        with patch("tools.overworld.devtools_release_observer.time.monotonic",
                   side_effect=[10, 10.2, 10.999, 11]), patch(
                   "tools.overworld.devtools_release_observer.os.write") as write:
            for _ in range(4):
                observer.check()
        self.assertEqual(write.call_count, 2)
        fd, raw = write.call_args.args
        self.assertEqual(fd, 2)
        self.assertLess(len(raw), 700)
        self.assertEqual(raw.count(b"\n"), 1)
        value = json.loads(raw)
        self.assertEqual((value["frame"], value["nativeCycle"]), (766, 1945))
        self.assertEqual((value["checkpointCount"], value["writeCount"]), (123, 2))
        self.assertEqual(value["cachedSelector"], {"snapshotFrame": 765,
                         "followerReleaseState": 133, "releasePhase": 5})
        self.assertEqual(value["arm9"]["pc"], 0x02001000)

    def test_missing_cpu_and_selector_are_explicit_and_bridge_phase_is_live(self):
        session, observer = self.fixture()
        session.emu = session.latest_frame = None
        session.native_bridge_active = True
        with patch("tools.overworld.devtools_release_observer.os.write") as write:
            observer.check()
        value = json.loads(write.call_args.args[1])
        self.assertEqual(value["arm9"], {"pc": None, "cpsr": None, "sp": None})
        self.assertIsNone(value["cachedSelector"]["followerReleaseState"])
        self.assertEqual(value["phase"], "native-bridge")

    def test_progress_failure_does_not_mask_existing_fault(self):
        session, observer = self.fixture()
        with patch("tools.overworld.devtools_release_observer.os.write", side_effect=OSError("closed")):
            observer.check()
        fault = RuntimeError("first native fault")
        observer.failure = fault
        with patch("tools.overworld.devtools_release_observer.time.monotonic", side_effect=AssertionError("no IO")):
            with self.assertRaises(RuntimeError) as raised:
                observer.check()
        self.assertIs(raised.exception, fault)


class EffectPoolDiagnosticTests(unittest.TestCase):
    def fixture(self, used=1, capacity=2, slot=0):
        class Root:
            def __init__(self, path=""):
                self.path = path
            def __truediv__(self, value):
                return Root(value)
            def read_bytes(self):
                if self.path == "base/overarm9.bin":
                    data = bytearray(64)
                    struct.pack_into("<I", data, 36, 0x021E5900)
                    return bytes(data)
                return bytes(0x300000)
        self.reads, self.auth = [], []
        env, manager, renderer, pool, slots = [0x02010000 + i * 0x1000 for i in range(5)]
        self.memory = {env + 0x28: manager, manager + 0x20: renderer, renderer + 0x0C: pool,
                       pool + 8: capacity, pool + 0xD4: used, pool + 0xD0: slots,
                       slots: slot, slots + 4: 0x02020000}
        def read(address, size):
            self.reads.append((address, size))
            self.assertEqual(size, 4)
            return struct.pack("<I", self.memory[address])
        def auth(address, size):
            self.auth.append((address, size))
            return bytes(size)
        s = NS(rt=NS(REPO=Root()), read=read, packaged_code=auth)
        words = [0] * 16
        words[1], words[3] = env, 0x021FF21D
        return s, {"pc": 0x02023F30, "stack": {"words": words}}

    def test_null_previous_slot_and_next_slot_are_distinct_post_call_data(self):
        s, cpu = self.fixture()
        value = _effect_pool_diagnostic(s, cpu)
        self.assertTrue(value["known"])
        self.assertEqual(value["previousSlot"], {"index": 0, "pointer": 0})
        self.assertEqual(value["nextSlot"], {"index": 1, "pointer": 0x02020000})
        self.assertEqual(len(self.auth), 5)
        self.assertEqual(len(self.reads), 8)

    def test_full_state_does_not_read_next_slot(self):
        s, cpu = self.fixture(used=2)
        value = _effect_pool_diagnostic(s, cpu)
        self.assertTrue(value["full"])
        self.assertNotIn("nextSlot", value)
        self.assertEqual(value["previousSlot"]["index"], 1)

    def test_missing_manager_is_retained_without_dereference(self):
        s, cpu = self.fixture()
        self.memory[0x02010028] = 0
        value = _effect_pool_diagnostic(s, cpu)
        self.assertFalse(value["known"])
        self.assertEqual(value["manager"], 0)
        self.assertEqual(self.reads, [(0x02010028, 4)])

    def test_unrelated_caller_or_pc_has_no_reads(self):
        for key in ("pc", "caller"):
            s, cpu = self.fixture()
            if key == "pc":
                cpu["pc"] += 2
            else:
                cpu["stack"]["words"][3] += 2
            self.assertIsNone(_effect_pool_diagnostic(s, cpu))
            self.assertEqual(self.reads, [])
            self.assertEqual(self.auth, [])

    def test_wrong_code_and_out_of_bound_counts_do_not_read_slots(self):
        s, cpu = self.fixture()
        s.packaged_code = lambda address, size: b"x" * size
        self.assertFalse(_effect_pool_diagnostic(s, cpu)["known"])
        self.assertEqual(self.reads, [])
        s, cpu = self.fixture(used=4097, capacity=4097)
        self.assertFalse(_effect_pool_diagnostic(s, cpu)["known"])
        self.assertEqual(len(self.reads), 6)
from tools.overworld.devtools_runtime import DevtoolsFailure, DevtoolsSession


class IrqCodeIdentityTests(unittest.TestCase):
    def read_identity(self, changes=(), short=False, baseline_is_actual=False):
        expected = bytes(428)
        actual = bytearray(expected)
        for offset, value in changes:
            struct.pack_into("<I", actual, offset, value)
        reads = []
        def read(emu, address, size):
            reads.append((address, size))
            return bytes(actual[:-1] if short else actual)
        session = NS(native_irq_code=expected, native_irq_live_baseline=bytes(actual) if baseline_is_actual else expected,
                     emu=object(), rt=NS(actor_memory_read=read))
        result = DevtoolsSession._native_irq_code_identity(session)
        self.assertEqual(reads, [(0x01FF8000, 428)])
        return result

    def test_same_body(self):
        result = self.read_identity()
        self.assertTrue(result["matchesBeforeCall"])
        self.assertEqual(result["changedWordCount"], 0)
        self.assertEqual(result["changedWords"], [])
        self.assertFalse(result["changedWordsTruncated"])

    def test_multiple_words_including_final_word(self):
        result = self.read_identity(((0, 0xE92D4000), (0xF4, 1), (424, 0x12345678)))
        self.assertFalse(result["matchesBeforeCall"])
        self.assertEqual(result["comparisonSource"], "stock-autoload-image")
        self.assertEqual(result["changedWordCount"], 3)
        self.assertEqual(result["changedWords"], [
            {"offset": 0, "expected": 0, "actual": 0xE92D4000},
            {"offset": 0xF4, "expected": 0, "actual": 1},
            {"offset": 424, "expected": 0, "actual": 0x12345678}])
        self.assertEqual(result["baselineChangedWords"], result["changedWords"])

    def test_changes_capped_without_losing_total(self):
        result = self.read_identity(tuple((i * 4, i + 1) for i in range(107)))
        self.assertEqual(result["changedWordCount"], 107)
        self.assertEqual(len(result["changedWords"]), 16)
        self.assertEqual(result["changedWords"][-1]["offset"], 60)
        self.assertTrue(result["changedWordsTruncated"])
        self.assertEqual(result["baselineChangedWordCount"], 107)
        self.assertEqual(len(result["baselineChangedWords"]), 16)
        self.assertTrue(result["baselineChangedWordsTruncated"])

    def test_short_read_fails_without_partial_identity(self):
        with self.assertRaises(DevtoolsFailure) as error:
            self.read_identity(short=True)
        self.assertEqual(error.exception.code, "abi-mismatch")

    def test_existing_stock_difference_is_not_a_new_live_change(self):
        result = self.read_identity(((4, 17),), baseline_is_actual=True)
        self.assertTrue(result["matchesBeforeCall"])
        self.assertFalse(result["matchesStock"])
        self.assertEqual(result["changedWordCount"], 1)
        self.assertEqual(result["baselineChangedWordCount"], 0)
        self.assertEqual(result["baselineChangedWords"], [])


class ReleaseObserverTests(unittest.TestCase):
    def setUp(self):
        self.regs = NS(pc=0, cpsr=0x60000092, spsr=0x1F, sp=0x027E3F60,
                       lr=0, r0=0x02001000, r1=0x02100000)
        self.hooks = NS(current_callback=None, add=self.add, remove=self.remove)
        self.callbacks = []
        self.words = [0xFFFF0010, 0, 0, 0, 0, 0, 0x02001004]
        self.s = NS(completed_frames=766, native_bridge_active=False,
                    rt=NS(EXECUTED_FRAME_COUNT=1945), party_getter_hooks=self.hooks,
                    emu=NS(memory=NS(register_arm9=self.regs)),
                    _native_checkpoint_points=lambda: [("irq-dispatch", 0x01FF804C)],
                    _native_irq_vector=lambda: {"target": 0x01FF8000},
                    _native_irq_code_identity=lambda: {"matchesBeforeCall": True},
                    _native_target_is_mapped_code=lambda p: p in (0x02001000, 0xFFFF0010),
                    _native_thread_snapshot=lambda p: {"pointer": p, "validContext": p == 0x02100000},
                    read=lambda p, n: struct.pack("<7I", *self.words)[:n])
        self.observer = ReleaseObserver(self.s, mode="irq")
        self.code = bytearray(428)
        self.write_hooks = {}
        self.s.native_irq_live_baseline = bytes(self.code)
        self.s.rt.actor_memory_read = lambda emu, address, size: bytes(self.code)
        self.s.emu.memory.register_write = self.register_write
        self.s.emu.memory.register_arm7 = NS(**{key: 7 for key in
            ("pc", "cpsr", "spsr", "sp", "lr") + tuple("r" + str(i) for i in range(13))})
        for i in range(13):
            if not hasattr(self.regs, "r" + str(i)):
                setattr(self.regs, "r" + str(i), i)

    def register_write(self, address, callback, size):
        self.assertEqual(size, 428)
        if callback is None:
            self.write_hooks.pop(address, None)
        else:
            self.write_hooks[address] = callback

    def test_default_write_only_keeps_first_write_guard_without_exec_hooks(self):
        observer = ReleaseObserver(self.s)
        observer.install()
        self.assertEqual(self.callbacks, [])
        self.assertEqual(observer.receipt()["coverage"], {"irqExecutionCheckpoints": False,
                                                        "irqCodeWriteWatches": True})
        self.assertEqual(observer.receipt()["mode"], "write")
        self.code[0] = 1
        self.write_hooks[0](0, 1)
        with self.assertRaises(DevtoolsFailure) as error:
            observer.check()
        self.assertEqual(error.exception.code, "prepared-release-irq-code-write")
        observer.close()
        self.assertEqual(self.write_hooks, {})

    def test_explicit_irq_retains_exec_hooks_and_declares_coverage(self):
        self.observer.install()
        self.assertEqual(len(self.callbacks), 1)
        self.assertTrue(self.observer.receipt()["coverage"]["irqExecutionCheckpoints"])
        self.assertEqual(self.observer.receipt()["mode"], "irq")
        self.observer.close()

    def test_write_without_changed_itcm_does_not_claim_writer(self):
        self.observer.install()
        self.write_hooks[0](0, 4)
        self.assertIsNone(self.observer.failure)
        self.assertEqual(self.observer.write_count, 1)
        self.assertEqual(set(self.write_hooks), {0, 0x01FF8000})
        self.observer.close()
        self.assertEqual(self.write_hooks, {})

    def test_low_and_direct_postwrite_changes_keep_both_cpus_and_first_fault(self):
        for base in (0, 0x01FF8000):
            with self.subTest(base=base):
                self.setUp()
                self.observer.install()
                self.s.native_bridge_active = True
                # Memory is already changed when the binding calls Python.
                struct.pack_into("<I", self.code, 424, 0xDEADBEEF)
                self.s.native_irq_live_baseline = bytes(self.code)
                self.write_hooks[base](base + 424, 4)
                first = self.observer.receipt()
                item = first["firstInvalid"]
                self.assertEqual(item["canonicalAddress"], 0x01FF81A8)
                self.assertEqual(item["changedWords"], [{"offset": 424, "expected": 0,
                                                        "actual": 0xDEADBEEF}])
                self.assertTrue(item["nativeBridgeActive"])
                self.assertEqual(item["writerCpu"], "unknown")
                self.assertEqual(item["arm9"]["r0"], self.regs.r0)
                self.assertEqual(item["arm7"]["pc"], 7)
                self.code[0] = 1
                self.write_hooks[base](base, 1)
                self.observe("irq-dispatch")
                self.assertEqual(self.observer.receipt(), first)
                with self.assertRaises(DevtoolsFailure) as error:
                    self.observer.check()
                self.assertEqual(error.exception.code, "prepared-release-irq-code-write")
                self.observer.close()
                self.assertEqual(self.write_hooks, {})
                self.assertEqual(self.callbacks, [])

    def test_existing_irq_fault_cannot_be_replaced_by_write(self):
        self.observer.install()
        self.regs.r0 = 0
        self.observe("irq-dispatch")
        first = self.observer.receipt()
        self.code[0] = 1
        self.write_hooks[0](0, 1)
        self.assertEqual(self.observer.receipt(), first)
        self.observer.close()

    def test_first_write_reads_only_two_bounded_public_stacks(self):
        self.observer.install()
        self.s.emu.memory.register_arm7.sp = 0x02000100
        reads = []
        def memory_read(emu, address, size):
            reads.append((address, size))
            if address == 0x01FF8000:
                return bytes(self.code)
            return struct.pack("<16I", *range(16))
        self.s.rt.actor_memory_read = memory_read
        self.s.read = lambda address, size: DevtoolsSession.read(self.s, address, size)
        self.code[184] = 1
        self.write_hooks[0](184, 4)
        item = self.observer.first_invalid
        self.assertEqual(reads, [(0x01FF8000, 428), (self.regs.sp, 64), (0x02000100, 64)])
        for name in ("arm9", "arm7"):
            self.assertEqual(item[name]["stack"]["words"], list(range(16)))
        self.write_hooks[0](184, 4)
        self.assertEqual(len(reads), 3)
        self.observer.close()

    def test_bad_stack_bounds_and_short_read_preserve_first_write(self):
        self.observer.install()
        reads = []
        def memory_read(emu, address, size):
            reads.append((address, size))
            return bytes(self.code) if address == 0x01FF8000 else bytes(60)
        self.s.rt.actor_memory_read = memory_read
        self.s.read = lambda address, size: DevtoolsSession.read(self.s, address, size)
        # ARM7 SP=7 is outside the shared public read bounds.
        self.code[184] = 1
        self.write_hooks[0](184, 4)
        item = self.observer.first_invalid
        self.assertIn("incomplete", item["arm9"]["stack"]["unavailable"])
        self.assertIn("outside", item["arm7"]["stack"]["unavailable"])
        self.assertEqual(reads, [(0x01FF8000, 428), (self.regs.sp, 64)])
        self.assertEqual(self.observer.failure.code, "prepared-release-irq-code-write")
        self.assertEqual(item["address"], 184)
        self.assertEqual(item["invalidReason"],
                         "IRQ code differs from release probe start after a watched write")
        self.observer.close()

    def test_partial_write_install_cleans_up_both_ranges_and_irq_hooks(self):
        normal = self.register_write
        def register(address, callback, size):
            normal(address, callback, size)
            if callback is not None and address == 0x01FF8000:
                raise ValueError("registration failed")
        self.s.emu.memory.register_write = register
        with self.assertRaisesRegex(ValueError, "registration failed"):
            self.observer.install()
        self.assertEqual(self.write_hooks, {})
        self.assertEqual(self.callbacks, [])

    def test_destroyed_core_cleanup_does_not_call_native_memory(self):
        self.observer.install()
        self.s.emu = None
        self.observer.write_memory.register_write = lambda *a, **k: self.fail("destroyed core")
        self.observer.close()
        self.assertEqual(self.observer.write_watches, [])
        self.assertEqual(self.callbacks, [])

    def add(self, address, callback):
        token = (address, callback)
        self.callbacks.append(token)
        return token

    def remove(self, token):
        self.callbacks.remove(token)

    def observe(self, kind, address=0x01FF804C):
        self.hooks.current_callback = {"address": address, "size": 4}
        self.regs.pc = address + 8
        self.observer.observe(kind, address)

    def test_bad_dispatch_preserves_first_and_bounded_recent(self):
        for _ in range(40):
            self.observe("irq-dispatch")
        self.regs.r0 = 0x0233BF7C
        self.observe("irq-dispatch")
        first = self.observer.receipt()
        self.regs.r0 = 0
        self.observe("irq-dispatch")
        self.assertEqual(self.observer.receipt(), first)
        self.assertEqual(first["checkpointCount"], 41)
        self.assertEqual(len(first["checkpoints"]), 32)
        self.assertEqual(first["firstInvalid"]["target"], 0x0233BF7C)
        with self.assertRaises(DevtoolsFailure):
            self.observer.check()

    def test_conditional_return_only_when_z_set(self):
        self.words[0] = 0x0233BF7C
        self.regs.cpsr &= ~0x40000000
        self.observe("irq-return-if-idle")
        self.assertEqual(self.observer.count, 0)
        self.regs.cpsr |= 0x40000000
        self.observe("irq-return-if-idle")
        self.assertEqual(self.observer.first_invalid["savedInterruptedResume"], 0x02001000)

    def test_wrong_cpu_callback_is_not_called_valid_target(self):
        self.hooks.current_callback = {"address": 0x01FF804C, "size": 4}
        self.regs.pc = 0x02000008
        self.observer.observe("irq-dispatch", 0x01FF804C)
        self.assertIn("not attributable", self.observer.first_invalid["invalidReason"])
        self.assertNotIn("target", self.observer.first_invalid)

    def test_bridge_excluded_and_hooks_removed(self):
        self.observer.install()
        self.s.native_bridge_active = True
        self.regs.r0 = 0
        self.observe("irq-dispatch")
        self.assertEqual(self.observer.count, 0)
        self.observer.close()
        self.assertEqual(self.callbacks, [])

    def test_invalid_chosen_thread(self):
        self.regs.r1 = 3
        self.observe("irq-thread-chosen")
        self.assertIn("invalid context", self.observer.first_invalid["invalidReason"])

    def test_thread_restore_requires_same_selected_pointer_and_saved_pop(self):
        self.observe("irq-thread-chosen")
        self.words[0] = self.regs.r1
        self.observe("irq-thread-svc-pop")
        self.observe("irq-thread-restore")
        self.assertIsNone(self.observer.failure)
        self.observer.thread["svcPop"]["savedChosenPointer"] += 4
        self.observe("irq-thread-restore")
        self.assertIn("differs", self.observer.first_invalid["invalidReason"])

    def test_real_cycle_checks_callback_fault_before_later_health_fault(self):
        self.s.runtime_health_failure = None
        self.s.release_observer = self.observer
        def cycle(*args):
            self.regs.r0 = 0x0233BF7C
            self.observe("irq-dispatch")
        self.s.rt.h = NS(cycle=cycle)
        self.s._check_runtime_health = lambda: self.fail("later health fault replaced first callback")
        with self.assertRaises(DevtoolsFailure) as error:
            DevtoolsSession.cycle(self.s, 1)
        self.assertIs(error.exception, self.observer.failure)

    def test_real_setup_wrapper_retains_error_and_removes_hooks(self):
        original = DevtoolsFailure("field-fault", "existing field failure")
        def body(*args):
            raise original
        self.s._spawn_party_subject_observed = body
        with self.assertRaises(DevtoolsFailure) as error:
            DevtoolsSession._spawn_party_subject(self.s, 1, "FOLLOWER", {})
        self.assertIs(error.exception, original)
        self.assertEqual(error.exception.code, "field-fault")
        self.assertEqual(self.callbacks, [])
        self.assertIsNone(self.s.release_observer)


if __name__ == "__main__":
    unittest.main()

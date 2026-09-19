"""Synthetic memory controls for the real read-only dialogue decoder."""
import struct
import unittest

from tools.overworld import devtools_dialogue as d


class Memory:
    field, task, env, ctx = 0x02210000, 0x02211000, 0x02212000, 0x02213000
    printer_task, printer = 0x02214000, 0x02215000
    parent, parent_env, child, menu = 0x02216000, 0x02217000, 0x02218000, 0x02219000

    def __init__(self):
        self.bytes = {}
        self.authenticated = []
        self.overlays = {1, 27}
        self.put(self.field + 0x10, self.task)
        self.put(self.task + 4, d.TASK_RUN_SCRIPTS | 1)
        self.put(self.task + 12, self.env)
        self.put(self.task + 24, self.field)
        self.put(self.env, 222271)
        self.put(self.env + 4, 1, 1)
        self.put(self.env + 9, 1, 1)
        self.put(self.env + 10, 2002, 2)
        self.put(self.env + 0x38, self.ctx)
        self.put(self.ctx + 1, 2, 1)
        self.put(self.ctx + 4, d.BUTTON_WAIT | 1)
        self.put(self.ctx + 8, 0x02220010)
        self.put(self.ctx + 0x74, self.task)
        self.put(self.ctx + 0x80, self.field)

    def put(self, address, value, size=4):
        for offset, byte in enumerate(value.to_bytes(size, "little")):
            self.bytes[address + offset] = byte

    def read(self, address, size):
        return bytes(self.bytes.get(address + i, 0) for i in range(size))

    def authenticate(self, address, size):
        self.authenticated.append((address, size))
        return True

    def observe(self, **kwargs):
        return d.observe_dialogue(self.read, self.authenticate, self.field,
                                  kwargs.get("frame", 100), kwargs.get("native_cycle", 200), self.overlays)

    def page(self, state=2):
        self.put(self.ctx + 4, d.MESSAGE_WAIT | 1)
        self.put(d.PRINTER_TASKS, self.printer_task)
        self.put(self.printer_task + 16, self.printer)
        self.put(self.printer_task + 20, d.RUN_TEXT_PRINTER | 1)
        self.put(self.printer, 0x02221010)
        self.put(self.printer + 4, self.env + 0x14)
        self.put(self.printer + 0x27, 1, 1)
        self.put(self.printer + 0x28, state, 1)
        return self

    def choice(self, state=4, cursor=0):
        self.put(self.ctx + 4, d.MENU_WAIT | 1)
        self.put(self.field + 0xD8, self.parent)
        self.put(self.parent + 16, self.parent_env)
        self.put(self.parent + 20, d.MENU_PARENT | 1)
        self.put(self.parent_env, 3, 1)
        self.put(self.parent_env + 1, 1, 1)
        self.put(self.parent_env + 4, self.child)
        self.put(self.parent_env + 8, self.field)
        self.put(self.child + 16, self.menu)
        self.put(self.child + 20, d.MENU_CHILD | 1)
        self.put(self.menu, state)
        self.put(self.menu + 4, self.ctx + 0x68)
        self.put(self.menu + 0x1C, self.child)
        self.put(self.menu + 0x24, self.field)
        self.put(self.menu + 0x394, cursor)
        for i, value in enumerate((0x0225C251, 0x0225C399, 0x0225C419, 0xFFFFFFFF)):
            self.put(d.MENU_DISPATCH + 4 * i, value)
        for i, value in enumerate(d.MENU_STATE_FUNCTIONS):
            self.put(d.MENU_STATES + 4 * i, value | 1)
        return self

    def healing(self):
        self.overlays.add(2)
        self.put(self.field + 16, self.child)
        self.put(self.child, self.task)
        self.put(self.child + 4, d.POKECENTER_ANIM | 1)
        self.put(self.child + 12, self.menu)
        self.put(self.child + 24, self.field)
        self.put(self.menu + 12, 2, 1)
        self.put(self.ctx + 1, 1, 1)
        return self

    def nested(self, count=2):
        original = self.read(self.ctx, 0x84)
        self.put(self.env + 9, count, 1)
        self.put(self.env + 7, (1 << (count - 1)) - 1, 1)
        for index in range(count):
            ctx = self.ctx + index * 0x100
            for offset, byte in enumerate(original):
                self.put(ctx + offset, byte, 1)
            self.put(self.env + 0x38 + index * 4, ctx)
            self.put(ctx + 3, index, 1)
            if index < count - 1:
                self.put(ctx + 1, 2, 1)
                self.put(ctx + 4, 0x02040BCD)
        return self


class DialogueTests(unittest.TestCase):
    def test_nested_callstd_button_and_page_ready(self):
        for count in (2, 3):
            for page in (False, True):
                mem = Memory()
                if page:
                    mem.page()
                mem.nested(count)
                value = mem.observe()
                self.assertEqual(value["state"], "page-wait" if page else "script-button-wait")
                self.assertEqual(value["script"]["context"], mem.ctx + (count - 1) * 0x100)
                self.assertIn((0x02040BCC, 0x30), mem.authenticated)

    def test_nested_callstd_rejects_unrelated_or_stale_contexts(self):
        for address, value, size in (
                (Memory.ctx + 4, d.BUTTON_WAIT | 1, 4),
                (Memory.ctx + 1, 1, 1),
                (Memory.ctx + 3, 1, 1),
                (Memory.ctx + 0x103, 0, 1),
                (Memory.ctx + 0x174, Memory.child, 4),
                (Memory.ctx + 0x180, Memory.parent, 4),
                (Memory.env + 7, 0, 1), (Memory.env + 7, 3, 1),
                (Memory.env + 9, 3, 1),
                (Memory.env + 0x3C, Memory.ctx, 4),
                (Memory.env + 0x38, 0, 4)):
            with self.subTest(address=address, value=value):
                mem = Memory().nested()
                mem.put(address, value, size)
                result = self.assertUnknown(mem)
                self.assertIn("contextPointers", result["script"])
                self.assertIn("activeContextCount", result["script"])

    def test_nested_callstd_menu_uses_leaf_result_owner(self):
        mem = Memory().choice().nested()
        self.assertUnknown(mem, "menu-result-owner-mismatch")
        mem.put(mem.menu + 4, mem.ctx + 0x100 + 0x68)
        self.assertEqual(mem.observe()["state"], "yes-no-ready")

    def test_nested_healing_is_busy_and_returned_parent_is_busy(self):
        mem = Memory().healing().nested()
        self.assertEqual(mem.observe()["state"], "busy")
        mem = Memory()
        mem.put(mem.ctx + 4, 0x02040BCD)
        self.assertEqual(mem.observe()["reason"], "standard-script-return")

    def test_nested_callstd_auth_failure_is_unknown(self):
        mem = Memory().nested()
        mem.authenticate = lambda address, size: address != 0x02040BCC
        self.assertUnknown(mem, "code-identity-mismatch")

    def test_nested_callstd_returns_remove_only_leaf(self):
        mem = Memory().nested(3)
        first_identity = mem.observe()["waitIdentity"]
        mem.put(mem.env + 0x40, 0)
        mem.put(mem.env + 9, 2, 1)
        mem.put(mem.env + 7, 1, 1)
        self.assertEqual(mem.observe()["reason"], "standard-script-return")
        mem.put(mem.ctx + 0x104, d.BUTTON_WAIT | 1)
        value = mem.observe()
        self.assertEqual(value["state"], "script-button-wait")
        self.assertNotEqual(first_identity, value["waitIdentity"])

    def test_nested_callstd_requires_every_parent(self):
        mem = Memory().nested(3)
        mem.put(mem.ctx + 0x104, d.BUTTON_WAIT | 1)
        self.assertUnknown(mem, "script-parent-not-standard-wait")

    def assertUnknown(self, mem, reason=None):
        value = mem.observe()
        self.assertFalse(value["known"])
        self.assertEqual(value["state"], "unknown")
        self.assertIsNone(value["waitIdentity"])
        if reason:
            self.assertEqual(value["reason"], reason)
        self.assertLessEqual(value["readBytes"], d.MAX_READ_BYTES)
        return value

    def test_idle_has_no_input_identity_and_needs_no_overlay(self):
        mem = Memory()
        mem.put(mem.field + 16, 0)
        mem.overlays = set()
        value = mem.observe()
        self.assertEqual((value["known"], value["state"]), (True, "idle"))
        self.assertIsNone(value["waitIdentity"])

    def test_exact_button_wait_and_complete_body_authenticated(self):
        mem = Memory()
        value = mem.observe()
        self.assertEqual(value["state"], "script-button-wait")
        self.assertEqual(value["boundary"], "main-task-queue-completion")
        self.assertIn((d.BUTTON_WAIT, 0x6C), mem.authenticated)
        self.assertEqual(value["waitIdentity"], mem.observe(frame=101, native_cycle=500)["waitIdentity"])
        mem.put(mem.ctx + 8, 0x02220020)
        self.assertNotEqual(value["waitIdentity"], mem.observe()["waitIdentity"])

    def test_page_waits_2_and_3_have_stable_distinct_identity(self):
        for state in (2, 3):
            with self.subTest(state=state):
                mem = Memory().page(state)
                value = mem.observe()
                self.assertEqual(value["state"], "page-wait")
                self.assertIn((d.MESSAGE_WAIT, 0x14), mem.authenticated)
                self.assertEqual(value["waitIdentity"], mem.observe(frame=101)["waitIdentity"])
                mem.put(mem.printer, 0x02221020)
                self.assertNotEqual(value["waitIdentity"], mem.observe()["waitIdentity"])

    def test_printer_input_is_suppressed_by_flags(self):
        for offset, value in ((d.TEXT_FLAGS, 4), (d.PRINTER_SUSPENDED, 1),
                              (Memory.printer + 0x2D, 1)):
            mem = Memory().page()
            mem.put(offset, value, 1)
            result = mem.observe()
            self.assertEqual(result["state"], "busy")
            self.assertIsNone(result["waitIdentity"])

    def test_printing_and_completed_printer_do_not_permit_input(self):
        for state in (0, 1, 4, 5, 6, 7, 8):
            value = Memory().page(state).observe()
            self.assertEqual(value["state"], "printing")
            self.assertIsNone(value["waitIdentity"])
        mem = Memory().page()
        mem.put(d.PRINTER_TASKS, 0)
        self.assertEqual(mem.observe()["state"], "busy")
        mem.put(mem.env + 5, 8, 1)
        self.assertEqual(mem.observe()["state"], "busy")

    def test_printer_wrong_id_window_callback_pointer_and_state(self):
        controls = ((Memory.env + 5, 255, 1), (Memory.printer + 4, 0x02212018, 4),
                    (Memory.printer + 0x2C, 1, 1), (Memory.printer_task + 20, 0x020202EC, 4),
                    (Memory.printer_task + 16, 0xFFFFFFFF, 4), (Memory.printer, 0x02221011, 4),
                    (Memory.printer + 0x27, 0, 1), (Memory.printer + 0x28, 255, 1),
                    (Memory.printer + 0x1C, 0x02000001, 4))
        for address, value, size in controls:
            with self.subTest(address=address):
                mem = Memory().page()
                mem.put(address, value, size)
                self.assertUnknown(mem)

    def test_yes_only_when_cursor_is_yes_and_menu_ready(self):
        mem = Memory().choice()
        value = mem.observe()
        self.assertEqual(value["state"], "yes-no-ready")
        self.assertIn((d.MENU_WAIT, 0x38), mem.authenticated)
        self.assertEqual(value["waitIdentity"], mem.observe(frame=101)["waitIdentity"])
        for state, cursor in ((4, 1), (0, 0), (1, 0), (2, 0), (3, 0), (5, 0), (6, 0)):
            value = Memory().choice(state, cursor).observe()
            self.assertEqual(value["state"], "busy")
            self.assertIsNone(value["waitIdentity"])

    def test_menu_ownership_and_tables_fail_closed(self):
        controls = ((Memory.parent + 20, d.MENU_PARENT), (Memory.child + 20, d.MENU_CHILD),
                    (Memory.parent_env + 8, Memory.field + 4), (Memory.menu + 0x24, Memory.field + 4),
                    (Memory.menu + 0x1C, Memory.child + 4), (Memory.menu + 4, Memory.ctx + 0x64),
                    (Memory.parent_env + 4, Memory.parent), (Memory.child + 16, Memory.parent_env),
                    (Memory.field + 0xD8, 1), (Memory.menu + 0x394, 2), (Memory.menu, 7),
                    (d.MENU_DISPATCH, 0), (d.MENU_STATES + 16, 0))
        for address, value in controls:
            with self.subTest(address=address):
                mem = Memory().choice()
                mem.put(address, value)
                self.assertUnknown(mem)
        for offset, value in ((0, 0), (1, 0)):
            mem = Memory().choice()
            mem.put(mem.parent_env + offset, value, 1)
            self.assertUnknown(mem)

    def test_missing_overlays_fail_closed(self):
        for mem, missing in ((Memory().page(), 1), (Memory().choice(), 1), (Memory().choice(), 27)):
            mem.overlays.remove(missing)
            self.assertUnknown(mem, "required-overlay-missing")

    def test_each_authentication_failure_prevents_input(self):
        for factory in (Memory, lambda: Memory().page(), lambda: Memory().choice(), lambda: Memory().healing()):
            baseline = factory()
            baseline.observe()
            for address, size in baseline.authenticated:
                with self.subTest(address=address):
                    mem = factory()
                    mem.authenticate = lambda a, s: (a, s) != (address, size)
                    self.assertUnknown(mem, "code-identity-mismatch")
        mem = Memory()
        def failed_auth(*_args):
            raise ValueError("wrong package")
        mem.authenticate = failed_auth
        self.assertUnknown(mem, "reader-or-authentication-failed")

    def test_unknown_callbacks_and_context_owners_fail_closed(self):
        for address, value, size in ((Memory.task + 4, 0x02000001, 4),
                                     (Memory.ctx + 4, 0x02000001, 4),
                                     (Memory.task + 24, Memory.field + 4, 4),
                                     (Memory.ctx + 0x74, Memory.task + 4, 4),
                                     (Memory.ctx + 0x80, Memory.field + 4, 4),
                                     (Memory.env, 0, 4), (Memory.ctx + 1, 3, 1),
                                     (Memory.ctx + 8, 1, 4), (Memory.env + 0x38, 1, 4)):
            mem = Memory()
            mem.put(address, value, size)
            self.assertUnknown(mem)

    def test_duplicate_script_and_context_owners_and_task_cycle(self):
        mem = Memory()
        mem.put(mem.task, mem.task)
        self.assertUnknown(mem, "task-chain-cycle")
        mem = Memory()
        mem.put(mem.env + 0x3C, mem.ctx)
        self.assertUnknown(mem, "script-context-count-or-state")
        mem = Memory()
        second = mem.task + 0x100
        mem.put(mem.task, second)
        for offset, value in ((4, d.TASK_RUN_SCRIPTS | 1), (12, mem.env), (24, mem.field)):
            mem.put(second + offset, value)
        self.assertUnknown(mem, "script-owner-count")

    def test_parent_chain_is_bounded(self):
        mem = Memory()
        for i in range(9):
            address = mem.task + 32 * i
            mem.put(address, address + 32 if i < 8 else 0)
            mem.put(address + 4, d.TASK_RUN_SCRIPTS | 1)
            mem.put(address + 12, mem.env)
            mem.put(address + 24, mem.field)
        value = self.assertUnknown(mem, "task-chain-limit")
        self.assertEqual(len(value["tasks"]), 8)

    def test_bytecode_and_script_setup_are_known_busy(self):
        for mode in (0, 1):
            mem = Memory()
            mem.put(mem.ctx + 1, mode, 1)
            self.assertEqual(mem.observe()["state"], "busy")
        mem = Memory()
        mem.put(mem.env + 4, 0, 1)
        mem.put(mem.env + 9, 0, 1)
        mem.put(mem.env + 0x38, 0)
        self.assertEqual(mem.observe()["state"], "busy")

    def test_verified_movement_fade_and_timer_callbacks_are_busy(self):
        for address, (size, reason) in d.BUSY_WAITS.items():
            mem = Memory()
            mem.put(mem.ctx + 4, address | 1)
            value = mem.observe()
            self.assertEqual((value["state"], value["reason"]), ("busy", reason))
            self.assertIsNone(value["waitIdentity"])
            self.assertIn((address, size), mem.authenticated)
            mem.authenticate = lambda a, s: a != address
            self.assertUnknown(mem, "code-identity-mismatch")

    def test_healing_child_reports_busy_only_with_exact_ownership(self):
        for phase in range(6):
            mem = Memory().healing()
            mem.put(mem.menu + 15, phase, 1)
            value = mem.observe()
            self.assertEqual((value["state"], value["reason"]), ("busy", "pokecenter-animation"))
            self.assertIsNone(value["waitIdentity"])
            self.assertIn((d.POKECENTER_ANIM, 0x258), mem.authenticated)
        mem = Memory().healing()
        mem.overlays.remove(2)
        self.assertUnknown(mem, "required-overlay-missing")
        for address, value, size in ((Memory.child + 24, Memory.field + 4, 4),
                                     (Memory.child + 12, Memory.env, 4),
                                     (Memory.ctx + 0x74, Memory.child, 4),
                                     (Memory.ctx + 1, 2, 1),
                                     (Memory.menu + 12, 7, 1), (Memory.menu + 13, 3, 1),
                                     (Memory.menu + 14, 13, 1), (Memory.menu + 15, 6, 1)):
            mem = Memory().healing()
            mem.put(address, value, size)
            self.assertUnknown(mem)

    def test_short_reads_bad_fields_and_clocks_fail_closed(self):
        mem = Memory()
        mem.read = lambda address, size: bytes(size - 1)
        self.assertUnknown(mem, "short-read")
        for field in (0, 1, 0xFFFFFFFF):
            mem = Memory()
            mem.field = field
            self.assertUnknown(mem, "invalid-pointer")
        mem = Memory()
        self.assertFalse(mem.observe(frame=True)["known"])

    def test_nurse_follower_recall_child_is_busy_and_owned(self):
        mem = Memory().healing()
        mem.put(mem.child + 4, d.NURSE_FOLLOWER_RECALL | 1)
        for phase in range(8):
            mem.put(mem.menu, phase, 1)
            result = mem.observe()
            self.assertEqual((result["state"], result["reason"]), ("busy", "nurse-follower-recall"))
            self.assertIsNone(result["waitIdentity"])
        self.assertIn((d.NURSE_FOLLOWER_RECALL, 0x1DC), mem.authenticated)
        for offset, value in ((0, 8), (1, 9), (2, 21), (3, 3)):
            mem.put(mem.menu, 0)
            mem.put(mem.menu + offset, value, 1)
            self.assertUnknown(mem, "nurse-recall-state-invalid")
        mem.put(mem.menu, 0)
        mem.overlays.remove(1)
        self.assertUnknown(mem, "required-overlay-missing")


if __name__ == "__main__":
    unittest.main()

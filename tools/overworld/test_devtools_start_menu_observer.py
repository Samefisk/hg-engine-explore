"""The Save cursor reader must not guess from the remembered menu position."""

import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.overworld.devtools_start_menu_observer import (
    START_MENU_CALLBACK, observe_start_menu,
)
from tools.overworld.devtools_runtime import DevtoolsSession


FIELD = 0x02200000
ENV = 0x022C6DFC


def memory(*, actions=(0, 1, 2, 11, 3, 4, 5), cursor=5, initial=0,
           state=3, active=1):
    payload = bytearray(0x44)
    struct.pack_into("<IHH", payload, 0x20, active, initial, state)
    struct.pack_into("<I", payload, 0x2C, len(actions))
    payload[0x3A:0x3A + len(actions)] = bytes(actions)
    cells = {ENV: bytes(payload), FIELD + 0xD3: bytes([cursor])}

    def read(address, size):
        if address not in cells or len(cells[address]) != size:
            raise AssertionError("unexpected guest read")
        return cells[address]

    return read


class StartMenuObserverTests(unittest.TestCase):
    def test_reads_live_cursor_and_save_position(self):
        result = observe_start_menu(memory(), FIELD, START_MENU_CALLBACK, FIELD, ENV)
        self.assertTrue(result["ready"])
        self.assertEqual(result["currentIndex"], 5)
        self.assertEqual(result["currentAction"], 4)
        self.assertEqual(result["saveIndex"], 5)
        self.assertEqual(result["initialIndex"], 0)

    def test_save_position_changes_with_unlocked_icons(self):
        result = observe_start_menu(memory(actions=(1, 2, 3, 4, 5), cursor=1),
                                    FIELD, START_MENU_CALLBACK, FIELD, ENV)
        self.assertEqual(result["currentAction"], 2)
        self.assertEqual(result["saveIndex"], 3)

    def test_non_input_state_never_grants_a_selection(self):
        result = observe_start_menu(memory(state=6), FIELD, START_MENU_CALLBACK, FIELD, ENV)
        self.assertFalse(result["ready"])
        self.assertIsNone(result["currentAction"])
        self.assertIsNone(result["currentIndex"])

    def test_save_wait_reads_stock_app_state(self):
        controller, controller_data = 0x02210000, 0x02220000
        app_task, app_data = 0x02230000, 0x02240000
        cells = {
            FIELD + 0xD8: struct.pack("<I", controller),
            controller: struct.pack("<7I", 0, 0, 0, 0, controller_data, 0, 0),
            controller_data: struct.pack("<4B3I", 1, 5, 1, 0, app_task, 0, 0),
            app_task: struct.pack("<7I", 0, 0, 0, 0, app_data, 0x0225D701, 0),
        }
        payload = bytearray(0x20)
        struct.pack_into("<4I", payload, 0x0C, 7, 0, 0, 0)
        struct.pack_into("<I", payload, 0x1C, FIELD)
        cells[app_data] = bytes(payload)
        base = memory(state=7)

        def read(address, size):
            if address in cells:
                self.assertEqual(len(cells[address]), size)
                return cells[address]
            return base(address, size)

        result = observe_start_menu(read, FIELD, START_MENU_CALLBACK, FIELD, ENV)
        self.assertEqual(result["saveApp"]["save"]["state"], 7)
        self.assertEqual(result["saveApp"]["phase"], 5)

    def test_wrong_task_or_out_of_range_cursor_fails_closed(self):
        for function, owner, reader in (
            (START_MENU_CALLBACK - 1, FIELD, memory()),
            (START_MENU_CALLBACK, FIELD + 4, memory()),
            (START_MENU_CALLBACK, FIELD, memory(cursor=9)),
            (START_MENU_CALLBACK, FIELD, memory(actions=(1, 2, 99))),
        ):
            with self.subTest(function=function, owner=owner), self.assertRaises(ValueError):
                observe_start_menu(reader, FIELD, function, owner, ENV)

    def test_existing_diagnostics_exposes_selected_save(self):
        task = 0x02210000
        menu_read = memory()
        task_data = struct.pack("<8I", 0, START_MENU_CALLBACK, 0, ENV, 0, 0, FIELD, 0)

        def read(address, size):
            if (address, size) == (task, 32):
                return task_data
            return menu_read(address, size)

        def unsigned(_emu, address, size=4):
            if address == FIELD + 0x10:
                return task
            if address == 0x02250028:
                return 0
            raise AssertionError("unexpected native scalar read")

        rt = SimpleNamespace(EXECUTED_FRAME_COUNT=100,
                             ACTOR_DESCRIPTOR={"state": {"address": 0x02250000}},
                             unsigned=unsigned, field_map_id=lambda _emu: 34,
                             player_ptr=lambda _emu: 0x02220000,
                             object_state=lambda _emu, _ptr: {"x": 1, "y": 1})
        session = SimpleNamespace(rt=rt, emu=object(), completed_frames=90,
                                  field_pointer=lambda: FIELD, read=read,
                                  _field_cleanup_diagnostics=lambda: {"known": True},
                                  _authenticate_field_reader_code=lambda *_args: None)
        with patch("tools.overworld.devtools_field_lifecycle.observe_field_lifecycle",
                   return_value={"known": True}):
            result = DevtoolsSession._control_diagnostics(session)
        self.assertNotIn("diagnosticError", result)
        self.assertEqual(result["tasks"][0]["startMenu"]["currentAction"], 4)
        self.assertEqual(result["tasks"][0]["startMenu"]["saveIndex"], 5)


if __name__ == "__main__":
    unittest.main()

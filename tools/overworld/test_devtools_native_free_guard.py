"""Stock null-free must fail even on a core that tolerates its invalid read."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure


class NativeFreeGuardTests(unittest.TestCase):
    def fixture(self, pointer):
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.completed_frames = 4
        session.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=
            SimpleNamespace(r0=pointer, lr=0x023C3371, sp=0x027E32B8)))
        return session

    def test_null_call_reports_actual_caller_without_changing_registers(self):
        session = self.fixture(0)
        before = vars(session.emu.memory.register_arm9).copy()
        with self.assertRaises(DevtoolsFailure) as raised:
            session._observe_native_free()
        self.assertEqual(raised.exception.code, "native-null-free")
        self.assertEqual(raised.exception.details,
            dict(caller=0x023C3371, sp=0x027E32B8, frame=4, pointer=0))
        self.assertEqual(vars(session.emu.memory.register_arm9), before)

    def test_nonnull_free_is_not_modified_or_simulated(self):
        session = self.fixture(0x022B1000)
        self.assertIsNone(session._observe_native_free())
        self.assertEqual(session.emu.memory.register_arm9.r0, 0x022B1000)

    def test_installed_guard_is_bound_to_packaged_stock_free(self):
        session = self.fixture(0)
        root = Path(__file__).resolve().parents[2]
        session.rt = SimpleNamespace(REPO=root)
        stock = (root / "base/arm9.bin").read_bytes()
        session.packaged_code = lambda address, size: stock[address-0x02000000:address-0x02000000+size]
        hooks = []
        session.party_getter_hooks = SimpleNamespace(add=lambda address, callback: hooks.append((address, callback)))
        session._install_native_free_guard()
        self.assertEqual(hooks[0][0], 0x0201AB0C)
        with self.assertRaises(DevtoolsFailure): hooks[0][1]()
        session.packaged_code = lambda address, size: b"\0" * size
        with self.assertRaises(DevtoolsFailure): session._install_native_free_guard()


if __name__ == "__main__":
    unittest.main()

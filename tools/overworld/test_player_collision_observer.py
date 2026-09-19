"""Installed native collision observer; no game core or memory writes in the reader."""
from copy import deepcopy
import struct
import tempfile
import unittest

from tools.overworld.test_devtools_observer import Fixture
from tools.overworld.devtools_observer import PLAYER_WALK_COLLISION_RETURN, NativeObservationError


class PlayerCollisionObserverTests(unittest.TestCase):
    def fixture(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        f = Fixture(directory.name)
        f.player["pos_y"] = 65536
        f.put(0x02231040, struct.pack("<I", 0x02232000))
        return f

    def enter(self, f, **changes):
        args = dict(r0=0x02232000, r1=f.player_pointer, r2=2,
                    lr=PLAYER_WALK_COLLISION_RETURN | 1)
        args.update(changes)
        f.enter("player-collision", **args)

    def test_exact_walking_call_is_read_only_and_framed_at_completed_queue(self):
        for mask in (0, 2, 1, 4, 8, 32):
            with self.subTest(mask=mask):
                f = self.fixture(); before = deepcopy(f.player)
                self.enter(f)
                f.returned(mask, address=PLAYER_WALK_COLLISION_RETURN)
                self.assertIsNone(f.hooks.error)
                self.assertEqual(f.observer.drain(), [])
                f.observer.completed_frame(12)
                row, = f.observer.drain()
                self.assertEqual(row["frame"], 12)
                data = row["data"]
                self.assertEqual(data["observation"], "player-collision")
                self.assertEqual(data["collisionMask"], mask)
                self.assertEqual(data["target"], [549, 381])
                self.assertEqual(data["objectBefore"], before)
                self.assertEqual(data["objectAfter"], before)
                self.assertEqual(f.player, before)

    def test_other_callers_are_not_walking_proof(self):
        f = self.fixture(); self.enter(f, lr=0x02001001)
        self.assertEqual(f.observer.contexts, [])
        self.assertEqual(f.observer.calls["player-collision"]["entered"], 0)

    def test_wrong_owner_direction_or_mutated_return_fail(self):
        for fault in ("avatar", "object", "direction", "map", "pose", "mask"):
            with self.subTest(fault=fault):
                f = self.fixture()
                changes = {"avatar": {"r0": 0}, "object": {"r1": 0}, "direction": {"r2": 4}}.get(fault, {})
                self.enter(f, **changes)
                if fault not in ("avatar", "object", "direction"):
                    if fault == "map": f.map_id += 1
                    if fault == "pose": f.player["pos_x"] += 1
                    f.returned(16 if fault == "mask" else 2, address=PLAYER_WALK_COLLISION_RETURN)
                self.assertIsNotNone(f.hooks.error)
                f.observer.completed_frame(12)
                self.assertEqual(f.observer.drain(), [])

    def test_decisive_mapping_and_caller_live_changes_fail_before_or_after_query(self):
        for address in (0x0205DA68, PLAYER_WALK_COLLISION_RETURN - 4, PLAYER_WALK_COLLISION_RETURN):
            for moment in ("entry", "return"):
                with self.subTest(address=hex(address), moment=moment):
                    f = self.fixture()
                    if moment == "return":
                        self.enter(f)
                    f.put(address, bytes([f.read(address, 1)[0] ^ 1]))
                    if moment == "entry":
                        self.enter(f)
                    else:
                        f.returned(2, address=PLAYER_WALK_COLLISION_RETURN)
                    self.assertIsNotNone(f.hooks.error)
                    f.observer.completed_frame(12)
                    self.assertEqual(f.observer.drain(), [])

    def test_cached_package_auth_rejects_changed_mapping_caller_and_truncated_stock(self):
        for address in (0x0205DA68, PLAYER_WALK_COLLISION_RETURN - 4):
            with self.subTest(address=hex(address)):
                f = self.fixture()
                stock = (f.rt.REPO / "base/arm9.bin").read_bytes()
                base, data = f.code_regions[0]
                changed = bytearray(data); changed[address-base] ^= 1
                f.code_regions[0] = (base, bytes(changed))
                with self.assertRaisesRegex(NativeObservationError, "packaged ROM"):
                    f.observer._install_player_collision_identity(stock)
        f = self.fixture()
        with self.assertRaises(NativeObservationError):
            f.observer._install_player_collision_identity(bytes(32))


if __name__ == "__main__": unittest.main()

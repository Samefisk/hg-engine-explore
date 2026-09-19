"""Exact spawn resident-tail checks, without a ROM or emulator."""
import copy
import struct
import unittest
from unittest.mock import patch

from scripts import verify_pokemon_move_history_capture as gate


class Overlay153OccupancyTailTests(unittest.TestCase):
    def setUp(self):
        self.occupancy = "OverworldWildOccupancy_Query"
        self.entry = 0x023C0184
        self.symbols = {
            gate.OVERLAY153_SPAWN_FUNCTION: (gate.OVERLAY153_SPAWN_ENTRY, 386, ".spawn_identity", "F"),
            self.occupancy: (self.entry, 214, ".spawn_identity", "F"),
            "OverworldWildSpawnGuard_Read": (0x023C025C, 240, ".spawn_identity", "F"),
            "OverworldWildSpawnGuard_IsNearActiveSpawn": (0x023C034C, 132, ".spawn_identity", "F"),
            "OverworldWildSpawnGuard_IsSurfBehavior": (0x023C03D0, 32, ".spawn_identity", "F"),
        }
        self.bindings = {name: (address | 1, size, "FUNC", "4")
                         for name, (address, size, _section, _kind) in self.symbols.items()}
        tail = bytearray([0xFF]) * (0x023C03F0 - gate.OVERLAY153_SPAWN_ENTRY)
        for index, (address, size, _, _) in enumerate(self.symbols.values()):
            offset = address - gate.OVERLAY153_SPAWN_ENTRY
            tail[offset:offset + size] = bytes([0x51 + index]) * size
        self.tail = bytes(tail)
        self.resident = bytes(gate.OVERLAY153_SPAWN_ENTRY - gate.OVERLAY_BASE) + self.tail
        self.prefix = self.resident[:gate.OVERLAY153_PREFIX_SIZE]

    def test_exact_five_function_extent(self):
        gate.overlay153_extent_contracts(self.resident, self.symbols)

    def test_linked_tail_and_permanent_negative_controls(self):
        gate.overlay153_spawn_tail_mutation_fixtures(
            self.resident, self.symbols, self.bindings, self.tail, self.prefix)

    def test_current_linked_walk_change_does_not_need_historical_hash(self):
        changed = bytearray(self.resident)
        changed[0x1380] = 0x23
        gate.overlay153_spawn_tail_contracts(
            bytes(changed), self.symbols, self.bindings, self.tail,
            bytes(changed[:gate.OVERLAY153_PREFIX_SIZE]))

    def test_package_change_without_matching_linked_prefix_fails(self):
        for offset in (0x100, 0x12D0, 0x1380, 0x1860, 0x1A50, 0x1BEA):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(self.resident)
                changed[offset] ^= 1
                with self.assertRaises(SystemExit):
                    gate.overlay153_spawn_tail_contracts(
                        bytes(changed), self.symbols, self.bindings, self.tail, self.prefix)

    def test_missing_occupancy_and_overlap_fail(self):
        symbols = copy.deepcopy(self.symbols)
        del symbols[self.occupancy]
        with self.assertRaises(SystemExit):
            gate.overlay153_extent_contracts(self.resident, symbols)
        symbols = copy.deepcopy(self.symbols)
        symbols[gate.OVERLAY153_SPAWN_FUNCTION] = (
            gate.OVERLAY153_SPAWN_ENTRY, 390, ".spawn_identity", "F")
        with self.assertRaises(SystemExit):
            gate.overlay153_extent_contracts(self.resident, symbols)

    def test_earlier_field_layout_controls_still_run(self):
        gate.field_terrain_layout_mutation_fixtures()


class Overlay153CopyClearOwnerTests(unittest.TestCase):
    def setUp(self):
        self.owner = "Walk_RejectDiagonalCandidate"
        self.copy, self.clear = "PokemonMoveHistory_OverlayMemcpy", "PokemonMoveHistory_OverlayMemset"
        self.symbols = {self.owner: 0x023BFE50, self.copy: 0x023BF354, self.clear: 0x023BF35C}
        self.sizes = {self.owner: 194}
        self.calls = sorted(
            [(address, "bl", self.symbols[self.copy]) for address in (0x023BE694, 0x023BEBF6, 0x023BEE0E)]
            + [(address, "bl", self.symbols[self.clear]) for address in
               (0x023BE52C, 0x023BFA4E, 0x023BFAB6, 0x023BFE66, 0x023BFE70, 0x023BFE7A)])

    def test_old_owners_and_three_typed_request_clears_pass(self):
        result = gate.overlay153_copy_clear_owner_contracts(self.calls, self.symbols, self.sizes)
        self.assertEqual(len(result[self.clear]), 6)
        self.assertEqual(len(result[self.copy]), 3)

    def test_missing_extra_wrong_mode_or_external_owner_fails(self):
        missing = self.calls[:-1]
        extra = sorted(self.calls + [(0x023BFE80, "bl", self.symbols[self.clear])])
        external = sorted(self.calls[:-1] + [(0x023BFD00, "bl", self.symbols[self.clear])])
        wrong_mode = self.calls[:-1] + [(self.calls[-1][0], "blx", self.symbols[self.clear])]
        changed_old = list(self.calls)
        changed_old[0] = (changed_old[0][0] + 2, *changed_old[0][1:])
        for calls in (missing, extra, external, wrong_mode, changed_old):
            with self.subTest(calls=calls), self.assertRaises(SystemExit):
                gate.overlay153_copy_clear_owner_contracts(calls, self.symbols, self.sizes)

    def test_owner_cannot_move_into_field_or_overrun_abort(self):
        with self.assertRaises(SystemExit):
            gate.overlay153_copy_clear_owner_contracts(
                self.calls, {**self.symbols, self.owner: 0x023BFD00}, self.sizes)
        with self.assertRaises(SystemExit):
            gate.overlay153_copy_clear_owner_contracts(
                self.calls, self.symbols, {self.owner: 0x200})

    def test_three_compiler_local_offsets_can_move_within_same_owner(self):
        calls = [(address + 2 if address >= 0x023BFE50 else address, mode, target)
                 for address, mode, target in self.calls]
        gate.overlay153_copy_clear_owner_contracts(calls, self.symbols, self.sizes)


class Overlay153CallInventoryTests(unittest.TestCase):
    def setUp(self):
        image = bytearray(0x1E5C)
        # A synthetic fixed history core and one call in each evolving host.
        # The real scanner decodes these Thumb BL instructions; no mocked
        # scanner or current ROM is required for the invariant tests.
        for offset in [4 * index for index in range(112)] + [0x1380, 0x1860, 0x1A50, 0x1C00]:
            struct.pack_into("<2H", image, offset, 0xF000, 0xF800)
        self.image = bytes(image)
        calls = gate.packaged_thumb_calls(self.image, gate.OVERLAY_BASE,
                                         gate.OVERLAY_BASE, len(self.image))
        core = [call for call in calls if call[0] < gate.OVERLAY_BASE + 0xFBC]
        self.core_hash = patch.object(gate, "OVERLAY153_CORE_CALL_INVENTORY_SHA256",
                                      gate.call_inventory_sha256(core))
        self.core_hash.start()
        self.addCleanup(self.core_hash.stop)

    def test_current_complete_linked_graph_passes(self):
        gate.overlay153_call_inventory_contracts(self.image, self.image)

    def test_changed_movement_field_rejection_and_tail_calls_fail(self):
        for offset in (0x1380, 0x1860, 0x1A50, 0x1C00):
            with self.subTest(offset=hex(offset)):
                changed = bytearray(self.image)
                changed[offset + 2] ^= 1
                with self.assertRaises(SystemExit):
                    gate.overlay153_call_inventory_contracts(bytes(changed), self.image)

    def test_changed_core_cannot_pass_by_matching_new_linked_graph(self):
        changed = bytearray(self.image)
        changed[2] ^= 1
        with self.assertRaises(SystemExit):
            gate.overlay153_call_inventory_contracts(bytes(changed), bytes(changed))

    def test_legitimate_new_movement_call_uses_current_link_without_new_digest(self):
        changed = bytearray(self.image)
        struct.pack_into("<2H", changed, 0x1A54, 0xF000, 0xF800)
        gate.overlay153_call_inventory_contracts(bytes(changed), bytes(changed))


if __name__ == "__main__":
    unittest.main()

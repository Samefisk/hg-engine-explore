import unittest
from unittest.mock import patch

try:
    from . import verify_overworld_walk_helper_alignment as checker
except ImportError:
    import verify_overworld_walk_helper_alignment as checker


class WalkHelperAlignmentTests(unittest.TestCase):
    def fixture(self):
        sections = [{"name": name, "flags": 6, "size": 20, "alignment": 4}
                    for name in sorted(checker.REQUIRED_SECTIONS)]
        symbols = [{"name": "Helper" + str(i), "section": i, "type": 2, "value": 1}
                   for i in range(len(sections))]
        linked = [dict(s, section=1, value=0x023BF000 + i * 32 + 1)
                  for i, s in enumerate(symbols)]
        return sections, symbols, linked

    def inspect_fixture(self, sections, symbols, linked):
        with patch.object(checker, "elf", side_effect=[(sections, symbols), ([], linked)]):
            return checker.inspect("input", "linked")

    def inspect_at(self, name, address, alignment=4):
        sections, symbols, linked = self.fixture()
        index = next(i for i, s in enumerate(sections) if s["name"] == name)
        sections[index]["alignment"] = alignment
        linked[index]["value"] = address | 1
        return self.inspect_fixture(sections, symbols, linked)

    def test_direction_key_original_placement_is_rejected(self):
        self.assertFalse(self.inspect_at(".overworld_walk_direction_key", 0x023BF586)["passed"])

    def test_strict_diagonal_original_placement_is_rejected(self):
        self.assertFalse(self.inspect_at(".overworld_walk_strict_diagonal_allowed", 0x023BF6CE)["passed"])

    def test_aligned_body_and_halfword_entry_are_valid(self):
        self.assertTrue(self.inspect_at(".overworld_walk_direction_key_body", 0x023BF588)["passed"])
        self.assertTrue(self.inspect_at(".overworld_walk_direction_key", 0x023BF586, 2)["passed"])

    def test_no_walk_sections_is_not_a_pass(self):
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            self.inspect_fixture([], [], [])

    def test_each_required_section_must_be_present_nonempty_and_executable(self):
        self.assertEqual(len(checker.REQUIRED_SECTIONS), 25)
        for index in range(len(checker.REQUIRED_SECTIONS)):
            for fault in ("delete", "empty", "nonexecutable"):
                with self.subTest(index=index, fault=fault):
                    sections, symbols, linked = self.fixture()
                    if fault == "delete":
                        del sections[index]
                    elif fault == "empty":
                        sections[index]["size"] = 0
                    else:
                        sections[index]["flags"] = 2
                    with self.assertRaisesRegex(ValueError, "inventory mismatch"):
                        self.inspect_fixture(sections, symbols, linked)

    def test_duplicate_and_unexpected_sections_fail_closed(self):
        for name in (".overworld_walk_module", ".overworld_walk_unexpected"):
            sections, symbols, linked = self.fixture()
            sections.append(dict(sections[0], name=name))
            with self.assertRaisesRegex(ValueError, "inventory mismatch"):
                self.inspect_fixture(sections, symbols, linked)

    def test_shared_section_mapping_accounts_for_function_offset(self):
        sections, symbols, linked = self.fixture()
        symbols.append(dict(symbols[0], name="Later", value=27))
        linked.append(dict(linked[0], name="Later", value=linked[0]["value"] + 26))
        result = self.inspect_fixture(sections, symbols, linked)
        self.assertTrue(result["passed"])
        self.assertEqual(result["sections"][0]["address"], 0x023BF000)

    def test_missing_linked_function_fails_closed(self):
        sections, symbols, linked = self.fixture()
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            self.inspect_fixture(sections, symbols, linked[1:])


if __name__ == "__main__":
    unittest.main()

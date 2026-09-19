"""Compile the actual walking wrapper; validate lock ownership, not game speed."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.test_spawn_spatial import extract_function
from scripts import verify_pokemon_move_history_capture as package_gate

ROOT = Path(__file__).resolve().parents[2]


class WalkingFriendshipTests(unittest.TestCase):
    def test_embedded_bss_never_requests_loader_zeroing_after_the_code(self):
        with tempfile.TemporaryDirectory(prefix="friendship-package-") as directory:
            root = Path(directory)
            (root / "build").mkdir()
            image = bytearray(0x4FB2)
            image[0x4F90:] = b"C" * 34
            output = root / "build/output_field.bin"
            sections = [(8, 3, 0x023CCF5C, 0x2C)]
            with patch.object(package_gate, "REPO", root), patch.object(
                    package_gate, "elf_section_layout", return_value=sections):
                output.write_bytes(image)
                self.assertEqual(package_gate.current_field_overlay_metadata()[1:3], (0x4FB2, 0))
                image[0x4F5C] = 1
                output.write_bytes(image)
                with self.assertRaises(SystemExit):
                    package_gate.current_field_overlay_metadata()
                output.write_bytes(bytes(0x4F5C))
                self.assertEqual(package_gate.current_field_overlay_metadata()[1:3], (0x4F5C, 0x2C))

    def test_native_lock_token_and_original_arguments_are_preserved(self):
        source = (ROOT / "src/field/walking_friendship.c").read_text()
        body = extract_function(source, "OverworldField_ApplyWalkingFriendship", "void")
        harness = r'''
#include <assert.h>
typedef int BOOL;
typedef unsigned char u8;
typedef unsigned short u16;
struct PartyPokemon { int locked, friendship; };
static int phase, incoming, skip, applications, acquired, released;
static BOOL WalkingFriendship_Acquire(struct PartyPokemon *mon) {
    assert(phase++ == 0); incoming = mon->locked; mon->locked = 1;
    acquired++; return !incoming;
}
static void WalkingFriendship_Apply(struct PartyPokemon *mon, u8 kind, u16 location) {
    assert(phase++ == 1 && mon->locked && kind == 5 && location == 127);
    applications++; if (!skip) mon->friendship++;
}
static BOOL WalkingFriendship_Release(struct PartyPokemon *mon, BOOL token) {
    assert(phase++ == 2 && token == !incoming);
    if (token) mon->locked = 0;
    released++; return token;
}
''' + body + r'''
int main(void) {
    for (int locked = 0; locked < 2; locked++) for (skip = 0; skip < 2; skip++) {
        struct PartyPokemon mon = {locked, 70}; phase = 0;
        OverworldField_ApplyWalkingFriendship(&mon, 5, 127);
        assert(phase == 3 && mon.locked == locked && mon.friendship == 71-skip);
    }
    assert(acquired == 4 && applications == 4 && released == 4);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="walking-friendship-") as directory:
            path = Path(directory)
            (path / "test.c").write_text(harness)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Werror", str(path / "test.c"),
                            "-o", str(path / "test")], check=True, capture_output=True)
            subprocess.run([str(path / "test")], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()

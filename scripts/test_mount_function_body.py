"""Check exact C function selection used by package gates."""
import unittest

from scripts.verify_overworld_mount import function_body


class FunctionBodyTests(unittest.TestCase):
    def test_exact_name_skips_prefix_and_prototype(self):
        source = '''int WorkForSlot(void) { return 9; }
int Work(void);
int Work (void) __attribute__((unused)) { return 3; }
'''
        self.assertEqual(function_body(source, "Work").strip(), "return 3;")
        self.assertEqual(function_body(source, "Work(").strip(), "return 3;")

    def test_missing_exact_name_does_not_use_prefix(self):
        with self.assertRaisesRegex(SystemExit, "function is missing"):
            function_body("int WorkForSlot(void) { return 9; }", "Work")


if __name__ == "__main__":
    unittest.main()

"""Read-only authored lookup tests; no current-ROM support claim."""
from pathlib import Path
import tempfile
import unittest

from tools.overworld.devtools_catalog import catalog


ROOT = Path(__file__).resolve().parents[2]


class AuthoredCatalogTests(unittest.TestCase):
    def test_real_named_species_map_and_move(self):
        for kind, query, number, symbol in (
            ("species", "Ledyba", 165, "SPECIES_LEDYBA"),
            ("maps", "MAP_R30", 34, "MAP_R30"),
            ("moves", "karate-chop", 2, "MOVE_KARATE_CHOP"),
        ):
            with self.subTest(kind=kind):
                result = catalog(ROOT, kind, query)
                self.assertEqual(result["items"][0]["id"], number)
                self.assertEqual(result["items"][0]["symbol"], symbol)
                self.assertEqual(result["source"], "authored-catalog")
                self.assertEqual(len(result["sourceSha256"]), 64)
                self.assertTrue(result["complete"], result["unresolved"])
                self.assertNotIn("supported", result)
                self.assertNotIn("acceptedProof", result)

    def test_real_all_headers_resolve_without_runtime(self):
        for kind in ("species", "maps", "moves"):
            with self.subTest(kind=kind):
                result = catalog(ROOT, kind)
                self.assertGreater(result["total"], 500)
                self.assertEqual(result["unresolvedCount"], 0)
                self.assertEqual(result["returned"], 30)
                self.assertTrue(result["truncated"])

    def test_exact_numeric_and_normalized_unicode(self):
        self.assertEqual(catalog(ROOT, "species", "0165")["items"][0]["symbol"], "SPECIES_LEDYBA")
        self.assertEqual(catalog(ROOT, "species", "0xA5")["items"][0]["symbol"], "SPECIES_LEDYBA")
        self.assertEqual(catalog(ROOT, "species", "  Flabébé  ")["items"][0]["symbol"], "SPECIES_FLABEBE")
        self.assertEqual(catalog(ROOT, "species", "not-a-pokemon")["items"], [])

    def test_limits_and_types_are_strict(self):
        for kind, query, limit in (("items", "", 30), ([], "", 30), ("species", None, 30),
                                   ("species", "x" * 129, 30), ("species", "", True),
                                   ("species", "", 0), ("species", "", 101)):
            with self.subTest(kind=kind, limit=limit), self.assertRaises(ValueError):
                catalog(ROOT, kind, query, limit)

    def fixture(self, directory, contents):
        path = Path(directory) / "include/constants/species.h"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
        return path

    def test_forward_aliases_and_arithmetic_use_existing_safe_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            self.fixture(directory, """
                #define SPECIES_ALIAS SPECIES_BASE
                #define SPECIES_LATER (SPECIES_ALIAS + 2 - 1)
                #define SPECIES_BASE 0xA5U
                #define SPECIES_RANGE_START (SPECIES_BASE + 10)
                #define SPECIES_FORM (SPECIES_RANGE_START + 1)
                // #define SPECIES_COMMENT 9
                /* #define SPECIES_BLOCK 8 */
            """)
            result = catalog(directory, "species", "", 100)
            self.assertTrue(result["complete"])
            self.assertEqual({i["symbol"]: i["id"] for i in result["items"]},
                             {"SPECIES_ALIAS": 165, "SPECIES_BASE": 165, "SPECIES_LATER": 166, "SPECIES_FORM": 176})
            self.assertEqual(len(catalog(directory, "species", "165")["items"]), 2)

    def test_unsupported_expressions_cycles_and_conflicts_stay_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            self.fixture(directory, """
                #define SPECIES_GOOD 1
                #define SPECIES_CALL __import__('os').system('no')
                #define SPECIES_A SPECIES_B
                #define SPECIES_B SPECIES_A
                #define SPECIES_UNKNOWN MISSING_NAME
                #define SPECIES_CONFLICT 2
                #define SPECIES_CONFLICT 3
                #define SPECIES_BOOLEAN True
                #define SPECIES_RANGE 999999
            """)
            result = catalog(directory, "species")
            self.assertFalse(result["complete"])
            self.assertEqual(result["items"], [{"id": 1, "name": "Good", "symbol": "SPECIES_GOOD"}])
            self.assertEqual(result["unresolvedCount"], 7)

    def test_prefix_precedes_contains_with_stable_id_order(self):
        with tempfile.TemporaryDirectory() as directory:
            self.fixture(directory, """
                #define SPECIES_SNOW_COLD 1
                #define SPECIES_COLD_WAVE 3
                #define SPECIES_COLD 9
                #define SPECIES_COLD_FRONT 2
            """)
            result = catalog(directory, "species", "cold", 3)
            self.assertEqual([item["id"] for item in result["items"]], [9, 2, 3])
            self.assertEqual(result["matched"], 4)
            self.assertTrue(result["truncated"])
            self.assertEqual(result, catalog(directory, "species", "cold", 3))

    def test_content_change_invalidates_cache_and_results_are_detached(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(directory, "#define SPECIES_FIRST 1\n")
            first = catalog(directory, "species")
            first["items"][0]["name"] = "changed"
            self.assertEqual(catalog(directory, "species")["items"][0]["name"], "First")
            path.write_text("#define SPECIES_OTHER 1\n")
            second = catalog(directory, "species")
            self.assertNotEqual(first["sourceSha256"], second["sourceSha256"])
            self.assertEqual(second["items"][0]["name"], "Other")


if __name__ == "__main__":
    unittest.main()

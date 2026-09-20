"""Legacy POOL resets placement; it is not an explicit all-surface selector.

Run the actual portable C resolver and Workshop parser. These host checks do
not establish spawn motion or physical landing behavior in the game.

The removed copy-form tests belonged to the retired pre-v4 editor. The v4
Workshop writes one complete validated catalog, so resolver cases below own
the remaining POOL compatibility proof.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/overworld-viewer-v2"))
import native_resolver  # noqa: E402


def load_viewer():
    spec = importlib.util.spec_from_file_location(
        "pool_spawn_test_viewer", ROOT / "scripts/overworld_behavior_profile_viewer.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VIEWER = load_viewer()
POOL = "OW_WILD_SPAWN_DESTINATION_POOL"
LAND = "OW_WILD_SPAWN_DESTINATION_LAND"
SCHEMA = json.loads((ROOT / "tools/overworld/behavior_schema.json").read_text())
FIELDS = {field["key"]: field for field in SCHEMA["fields"]}


def authored(**values):
    return {key: {"operator": "replace", "value": value} for key, value in values.items()}


def lane_fields(result, lane):
    raw = bytes.fromhex(result["profileHex"])
    size = SCHEMA["compactSize"]
    if len(raw) != size * 2:
        raise AssertionError("native resolver did not return two complete public lanes")
    raw = raw[lane * size:(lane + 1) * size]
    return {
        key: int.from_bytes(raw[field["offset"]:field["offset"] +
                                  {"u8": 1, "u16": 2}[field["cType"]]], "little")
        for key, field in FIELDS.items()
        if key in {"spawnDestination", "spawnDestinationMask", "spawnDestinationOverrideMask"}
    }


class PoolSpawnResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="pool-spawn-resolution-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.temp = Path(cls.temporary.name)
        cls.catalog = VIEWER.load_behavior_catalog()
        _, _, cls.macros = VIEWER.behavior_authoring_context()
        cls.native = native_resolver.build(ROOT, force=True, output=cls.temp / "actual-resolver")
        # Keep the real catalog's ABI counts, targets and base profiles. Only
        # override bodies change; explicit request bits choose test layers.
        matrix = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        matrix_profiles = {
            profile["id"]: profile for profile in matrix["profiles"]
        }
        # An empty override is a true inheritance-only layer.
        neutral = {}
        for application in matrix["applications"]:
            matrix_profiles[application["profile"]]["fields"] = copy.deepcopy(neutral)
        layers = [
            authored(spawnDestination=LAND),
            authored(spawnDestinationMask=4, spawnDestinationOverrideMask=1023),
            authored(spawnDestination=POOL),
            authored(spawnDestinationMask=15, spawnDestinationOverrideMask=1023),
            neutral,
            authored(spawnDestinationMask=0, spawnDestinationOverrideMask=0),
            authored(tiredProfile="apply-default-active"),
            authored(spawnDestination=POOL),
            authored(spawnDestinationMask=8, spawnDestinationOverrideMask=1023),
        ]
        for index, fields in enumerate(layers):
            application = matrix["applications"][index]
            matrix_profiles[application["profile"]]["fields"] = fields
        matrix_path = cls.temp / "layer-catalog.json"
        matrix_path.write_text(json.dumps(matrix))
        cls.matrix_native = native_resolver.build(
            ROOT, force=True, catalog=matrix_path, output=cls.temp / "layer-resolver"
        )

    def resolve_layers(self, *layers):
        result = native_resolver.resolve(None, {
            "species": 0, "level": 1, "terrain": 0, "behaviorClass": 0,
            "forcedOverrideMask": sum(1 << layer for layer in layers),
        }, root=ROOT, executable=self.matrix_native)
        self.assertEqual(result["status"], 0)
        self.assertEqual(result["traceDropped"], 0)
        self.assertEqual(result["forcedOverrideMask"], sum(1 << layer for layer in layers))
        return result

    def assert_destinations(self, result, expected):
        for lane, (destination, values, explicit) in enumerate(expected):
            with self.subTest(lane=lane):
                self.assertEqual(lane_fields(result, lane), {
                    "spawnDestination": self.macros[destination],
                    "spawnDestinationMask": values,
                    "spawnDestinationOverrideMask": explicit,
                })

    def test_actual_ledyba_owner_and_tired_preserve_own_pool_site(self):
        flying = next(profile for profile in self.catalog["overrideProfiles"]
                      if profile["name"] == "Flying insect")
        flying_index = self.catalog["overrideProfiles"].index(flying)
        self.assertEqual(flying["fields"]["spawnDestination"], authored(spawnDestination=POOL)["spawnDestination"])
        for terrain in (0, 1):
            result = native_resolver.resolve(None, {"species": 165, "level": 16, "terrain": terrain},
                                             root=ROOT, executable=self.native)
            self.assertEqual(result["status"], 0)
            self.assertTrue(result["matchedOverrideMask"] & (1 << flying_index))
            for lane in range(2):
                with self.subTest(terrain=terrain, lane=lane):
                    self.assertEqual(lane_fields(result, lane), {
                        "spawnDestination": self.macros[POOL],
                        "spawnDestinationMask": 15,
                        "spawnDestinationOverrideMask": 0,
                    })

    def test_pool_clears_prior_legacy_land_in_all_lanes(self):
        self.assert_destinations(self.resolve_layers(0), [(LAND, 1, 1023)] * 2)
        self.assert_destinations(self.resolve_layers(0, 2), [(POOL, 15, 0)] * 2)

    def test_pool_clears_prior_modern_mask_in_all_lanes(self):
        self.assert_destinations(self.resolve_layers(1), [(POOL, 4, 1023)] * 2)
        self.assert_destinations(self.resolve_layers(1, 2), [(POOL, 15, 0)] * 2)

    def test_later_explicit_modern_all_surface_selection_is_retained(self):
        for earlier in ((), (0,), (1,)):
            with self.subTest(earlier=earlier):
                self.assert_destinations(self.resolve_layers(*earlier, 2, 3), [(POOL, 15, 1023)] * 2)

    def test_base_empty_and_zero_explicit_inheritance_are_unchanged(self):
        self.assert_destinations(self.resolve_layers(), [(POOL, 15, 0)] * 2)
        for prior in ((), (0,), (1,)):
            for unchanged in ((4,), (5,), (4, 5)):
                with self.subTest(prior=prior, unchanged=unchanged):
                    self.assertEqual(self.resolve_layers(*prior)["profileHex"],
                                     self.resolve_layers(*prior, *unchanged)["profileHex"])

    def test_tired_modern_selection_remains_lane_local(self):
        self.assert_destinations(self.resolve_layers(0, 6), [
            (LAND, 1, 1023), (LAND, 8, 1023),
        ])

if __name__ == "__main__":
    unittest.main()

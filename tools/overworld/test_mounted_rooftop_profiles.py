"""Actual-C profile proof for Mounted chain Off and Mankey rooftop access.

This is host resolver proof. It does not claim a native landing or spawn pass.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LINE = {"SPECIES_MANKEY": (56, 8), "SPECIES_PRIMEAPE": (57, 8),
        "SPECIES_ANNIHILAPE": (1029, 520)}


def load_module(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MountedRooftopProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native = load_module("mounted_rooftop_native", "tools/overworld-viewer-v2/native_resolver.py")
        cls.authoring = load_module("mounted_rooftop_authoring", "scripts/overworld_behavior_profile_viewer.py")
        cls.catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        cls.index = {a["id"]: i for i, a in enumerate(cls.catalog["applications"])}
        cls.profile = {p["id"]: p for p in cls.catalog["profiles"]}
        cls.temp = tempfile.TemporaryDirectory(prefix="mounted-rooftop-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.hosts = {}
        controls = {"current": cls.catalog,
                    "roof-off": copy.deepcopy(cls.catalog),
                    "mounted-chain-inherited": copy.deepcopy(cls.catalog)}
        roof = next(p for p in controls["roof-off"]["profiles"] if p["id"] == "rooftop-access")
        roof["fields"]["chillAllowedTerrainMask"] = {"operator": "replace", "value": 1}
        mounted = next(p for p in controls["mounted-chain-inherited"]["profiles"] if p["id"] == "mounted")
        mounted["fields"].pop("ramAccelerationSteps")
        for name, catalog in controls.items():
            source = cls.directory / (name + ".json")
            source.write_text(json.dumps(catalog))
            cls.hosts[name] = cls.native.build(ROOT, catalog=source,
                                               output=cls.directory / name)
        cls.roles = {"normal": 0,
                     "follower": 1 << cls.index["apply-follower"],
                     "mounted": 1 << cls.index["apply-mounted"],
                     "asleep": 1 << cls.index["apply-asleep"]}

    def resolve(self, requests, name="current"):
        results = self.native.resolve_many(None, requests, root=ROOT,
                                           executable=self.hosts[name])
        for result in results:
            self.assertEqual(result["status"], 0)
            self.assertEqual(result["traceDropped"], 0)
        return results

    def request(self, species, groups, role="normal", level=20, terrain=0, shiny=0, conditional=0):
        winning = 0xFFFF
        if conditional:
            application = self.catalog["applications"][conditional.bit_length() - 1]
            profile = self.profile[application["profile"]]
            winning = self.authoring._stable_condition_id(profile["id"], profile["conditions"][0]["id"])
        return {"species": species, "level": level, "terrain": terrain, "shiny": shiny,
                "groupFlags": groups, "behaviorClass": "auto",
                "forcedOverrideMask": self.roles[role], "activeConditionalMask": conditional,
                "winningConditionId": winning}

    def test_visible_settings_and_supported_line_assignments(self):
        mounted = self.profile["mounted"]
        self.assertEqual(mounted["fields"]["ramAccelerationSteps"],
                         {"operator": "replace", "value": 0})
        self.assertEqual(mounted["classification"], "follower-mount")
        roof = self.profile["rooftop-access"]
        self.assertEqual((roof["name"], roof["parent"], roof["kind"], roof["classification"]),
                         ("Rooftop Access", "default", "normal", "placement"))
        self.assertEqual(set(roof["fields"]), {"chillAllowedTerrainMask"})
        selected = {s["match"]["species"] for s in self.catalog["selectors"]
                    if s["profile"] == "rooftop-access"}
        self.assertEqual(selected, set(LINE))
        self.assertIn({"profile": "rooftop-access", "symbol": "OW_WILD_BEHAVIOR_CLASS_ROOFTOP_ACCESS"},
                      self.catalog["runtimeBindings"]["classOrder"])
        self.assertEqual(len(self.catalog["applications"]), 32)
        evo = (ROOT / "armips/data/evodata.s").read_text()
        sprites = (ROOT / "armips/data/monoverworlds.s").read_text()
        for before, after in (("SPECIES_MANKEY", "SPECIES_PRIMEAPE"),
                              ("SPECIES_PRIMEAPE", "SPECIES_ANNIHILAPE")):
            body = evo.split("evodata " + before + "\n", 1)[1].split("terminateevodata", 1)[0]
            self.assertIn(after, body)
        for species in LINE:
            self.assertRegex(sprites, r"(?m)^overworlddata\s+\d+,[^\n]*// " + species + r"$")

    def test_mounted_chain_is_disabled_by_its_authored_override(self):
        requests = [self.request(56, 8, role) for role in ("normal", "mounted")]
        normal, mounted = self.resolve(requests)
        inherited = self.resolve(requests, "mounted-chain-inherited")[1]
        for lane in (0, 80):
            self.assertGreater(bytes.fromhex(normal["profileHex"])[lane + 29], 1)
            self.assertEqual(bytes.fromhex(mounted["profileHex"])[lane + 29], 0)
            self.assertEqual(bytes.fromhex(inherited["profileHex"])[lane + 29],
                             bytes.fromhex(normal["profileHex"])[lane + 29])
        for lane in (0, 2):
            steps = [s for s in mounted["trace"] if s["lane"] == lane
                     and s["sourceIndex"] == self.index["apply-mounted"]]
            self.assertTrue(steps)
            self.assertTrue(any(s["flags"] & 4 for s in steps))
        self.assertEqual(mounted["forcedOverrideMask"], self.roles["mounted"])
        self.assertNotEqual(mounted["fingerprint"], inherited["fingerprint"])

    def test_roof_permission_composes_in_all_roles_and_both_lanes(self):
        # Ordinary and admitted Canopy/Throw capability inputs; condition truth
        # is tested separately. These use the real resolver's explicit inputs.
        conditions = [0] + [1 << self.index[name] for name in
                      ("apply-canopy-hop", "apply-throw", "apply-throw-find-position", "apply-throw-release")]
        requests = [self.request(species, groups, role, level, terrain, shiny, conditional)
                    for species, groups in LINE.values() for role in self.roles
                    for level, terrain, shiny in ((1, 0, 0), (50, 1, 1))
                    for conditional in conditions]
        current = self.resolve(requests)
        off = self.resolve(requests, "roof-off")
        for request, result, control in zip(requests, current, off):
            with self.subTest(request=request):
                value = bytearray.fromhex(result["profileHex"])
                previous = bytes.fromhex(control["profileHex"])
                for lane in (0, 80):
                    offset = lane + 32
                    terrain = int.from_bytes(value[offset:offset + 2], "little")
                    self.assertEqual(terrain & 69, 69)  # Land, Canopy, Rooftop.
                    self.assertEqual(int.from_bytes(previous[offset:offset + 2], "little") & 64, 0)
                    value[offset:offset + 2] = (terrain & ~64).to_bytes(2, "little")
                self.assertEqual(bytes(value), previous)
                self.assertEqual(result["primitivesHex"], control["primitivesHex"])
                self.assertEqual(result["appliedOverrideMask"], control["appliedOverrideMask"])
                self.assertEqual(result["forcedOverrideMask"], request["forcedOverrideMask"])
                self.assertEqual(result["behaviorClass"], 1)
                self.assertNotEqual(result["fingerprint"], control["fingerprint"])

    def test_nearby_species_have_no_rooftop_change(self):
        # Sentret shares Canopy Access; Pidgey shares elevated terrain routines.
        requests = [self.request(species, groups, role)
                    for species, groups in ((161, 4), (16, 20), (234, 4), (19, 4))
                    for role in self.roles]
        for current, control in zip(self.resolve(requests), self.resolve(requests, "roof-off")):
            self.assertEqual(current, control)


if __name__ == "__main__":
    unittest.main()

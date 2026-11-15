"""Execute map-filtered authored applications in the real C resolver."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.overworld.test_workshop_authoring import VIEWER, native_resolver


class MapProfileMatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="map-profile-match-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.directory = Path(cls.temporary.name)
        cls.catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        # Use the shipped Goldenrod application, then move that same rule to
        # map zero. This proves zero is an explicit map, never an Any default.
        changed = copy.deepcopy(cls.catalog)
        application = next(a for a in changed["applications"]
                           if a["id"] == "apply-goldenrod-behind-buildings")
        application["target"]["match"]["mapId"] = 0
        source = cls.directory / "catalog.json"
        source.write_text(json.dumps(changed))
        cls.executable = native_resolver.build(REPO, force=True, catalog=source,
                                               output=cls.directory / "resolver")

    def resolve(self, species, map_id=None):
        request = dict(species=species, level=15, terrain=0)
        if map_id is not None:
            request["mapId"] = map_id
        return native_resolver.resolve(None, request, root=REPO, executable=self.executable)

    def test_map_zero_application_matches_only_map_zero(self):
        for map_id in (0, 76, 199, 65535, None):
            with self.subTest(map_id=map_id):
                result = self.resolve(52, map_id)
                self.assertEqual(result["status"], 0)
                mask = int.from_bytes(bytes.fromhex(result["profileHex"])[52:54], "little")
                self.assertEqual(bool(mask & 0x800), map_id == 0)

    def test_application_any_map_matches_every_context(self):
        changed = copy.deepcopy(self.catalog)
        application = next(a for a in changed["applications"]
                           if a["id"] == "apply-goldenrod-behind-buildings")
        application["target"]["match"].pop("mapId")
        source = self.directory / "any-map-catalog.json"
        source.write_text(json.dumps(changed))
        executable = native_resolver.build(REPO, force=True, catalog=source,
                                           output=self.directory / "any-map-resolver")
        for map_id in (0, 76, 199, 65535):
            with self.subTest(map_id=map_id):
                result = native_resolver.resolve(None, dict(species=52, level=15,
                    terrain=0, mapId=map_id), root=REPO, executable=executable)
                self.assertEqual(result["status"], 0)
                mask = int.from_bytes(bytes.fromhex(result["profileHex"])[52:54], "little")
                self.assertTrue(mask & 0x800)

    def test_base_selectors_reject_map_filters(self):
        for map_id in (0, 76, 199):
            changed = copy.deepcopy(self.catalog)
            changed["selectors"][0]["match"]["mapId"] = map_id
            with self.subTest(map_id=map_id), self.assertRaisesRegex(VIEWER.ParseError, "mapId must be Any"):
                VIEWER.validate_behavior_catalog(changed)
        for map_id in (65535, "OW_WILD_BEHAVIOR_MATCH_ANY_MAP"):
            changed = copy.deepcopy(self.catalog)
            changed["selectors"][0]["match"]["mapId"] = map_id
            VIEWER.validate_behavior_catalog(changed)

    def test_omitted_match_field_lowers_to_any_and_rejects_out_of_range(self):
        match = {k: v for k, v in VIEWER.default_behavior_match_raws().items() if k != "mapId"}
        lowered = VIEWER._catalog_match_raws(match, "fixture")
        self.assertEqual(lowered["mapId"], "OW_WILD_BEHAVIOR_MATCH_ANY_MAP")
        for bad in (-1, 65536, "-1", "65536", "0x10000"):
            with self.subTest(bad=bad), self.assertRaises(VIEWER.ParseError):
                VIEWER._validate_catalog_match({**match, "mapId": bad}, "fixture")
        for good in (0, 76, 199, 65535, "0"):
            VIEWER._validate_catalog_match({**match, "mapId": good}, "fixture")

    def test_editor_keeps_and_shows_map_filter(self):
        source = (REPO / "tools/overworld-viewer-v2/static/profiles.js").read_text()
        with tempfile.TemporaryDirectory(prefix="map-profile-editor-") as directory:
            module = Path(directory) / "profiles.mjs"
            module.write_text(source + "\nexport { DEFAULT_MATCH, MATCH_FIELDS, SELECTOR_MATCH_FIELDS, cloneRawMatch };\n")
            script = Path(directory) / "test.mjs"
            script.write_text(f'''
import assert from 'node:assert/strict';
import {{ DEFAULT_MATCH, MATCH_FIELDS, SELECTOR_MATCH_FIELDS, cloneRawMatch }} from {json.dumps(module.as_uri())};
assert.ok(MATCH_FIELDS.some(([key, label]) => key === 'mapId' && label === 'Map ID'));
assert.ok(!SELECTOR_MATCH_FIELDS.some(([key]) => key === 'mapId'));
assert.equal(cloneRawMatch({{}}).mapId, 'OW_WILD_BEHAVIOR_MATCH_ANY_MAP');
assert.equal(cloneRawMatch({{ mapId: '0' }}).mapId, '0');
assert.equal(cloneRawMatch({{ mapId: '76' }}).mapId, '76');
assert.equal(cloneRawMatch({{ mapId: '199' }}).mapId, '199');
''')
            result = subprocess.run(["node", str(script)], cwd=REPO, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()

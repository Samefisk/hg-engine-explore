"""Goldenrod's real encounter data, scoped placements, and clock selection.

Host proof only. Natural births, native surface heights, and frame pacing
remain current-ROM observations.
"""

from collections import Counter
import copy
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import build_overworld_wild_encounter_data as owed
from tools.overworld.test_workshop_authoring import REPO, REQUEST, VIEWER, native_resolver
from tools.overworld.test_spawn_destination_scan import function


PLACEMENT_IDS = {"behind-buildings", "land-placement", "land-rooftop-placement", "rooftop-canopy-placement"}
APPLICATION_IDS = {"apply-goldenrod-behind-buildings", "apply-goldenrod-land",
    "apply-goldenrod-land-rooftop", "apply-goldenrod-rooftop-canopy", "apply-underground-land"}
LEVELS = [12, 12, 13, 13, 14, 14, 14, 15, 15, 15, 16, 16]


def route_data():
    _, _, macros = VIEWER.behavior_authoring_context()
    rows = VIEWER.parse_route_encounters({}, macros, VIEWER.parse_lookup_encounter_area_maps(macros))
    return {row["id"]: row for row in rows}, macros


def species_slots(route, time):
    return next(table["slots"] for table in route["pokemonTables"] if table["key"] == time)


def weights(route, time):
    output = Counter()
    for weight, slot in zip(VIEWER.GRASS_SLOT_WEIGHTS, species_slots(route, time)):
        output[slot["species"]["symbol"].removeprefix("SPECIES_")] += weight
    return dict(output)


class GoldenrodEncounterTests(unittest.TestCase):
    def test_exact_slots_levels_and_time_tables(self):
        routes, _ = route_data()
        day = {"MEOWTH": 30, "PIDOVE": 30, "RATTATA": 20, "SNUBBULL": 10,
               "TRUBBISH": 9, "GRIMER": 1}
        night = {"RATTATA": 40, "MEOWTH": 30, "SNUBBULL": 10, "MURKROW": 10,
                 "TRUBBISH": 8, "GRIMER": 1, "ROTOM": 1}
        for time, expected in (("morning", day), ("day", day), ("night", night)):
            self.assertEqual(weights(routes[142], time), expected)
            self.assertEqual(weights(routes[143], time), {"RATTATA": 95, "GRIMER": 5})
        for index in (142, 143):
            self.assertEqual([slot["value"] for slot in routes[index]["grassLevels"]], LEVELS)
            self.assertTrue(all(rate["value"] == 0 for rate in routes[index]["rates"]))
        source = (REPO / "armips/data/encounters.s").read_text()
        strict = []
        for number, body in re.findall(r"encounterdata\s+(\d+)(.*?)(?=\nencounterdata|\Z)", source, re.S):
            if "overworldtimepolicy" in body:
                self.assertEqual(re.findall(r"^overworldtimepolicy\s+(\d+)$", body, re.M), ["1"])
                strict.append(int(number))
        self.assertEqual(strict, [142, 143])

    def test_sparse_and_native_map_authorities_agree(self):
        mappings = owed.parse_mapping(REPO / "data/OverworldWildEncounterLookupData.c",
                                      REPO / "include/constants/maps.h")
        self.assertEqual(len(mappings), 147)
        self.assertEqual({row.map_id: row.data_id for row in mappings if row.data_id >= 142},
                         {76: 142, 199: 143})
        native = (REPO / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c").read_text()
        maps_body = re.search(r"sOverworldWildLegacyEncounterAreaMapIds\[[^\]]+\]\s*=\s*\{([^}]+)\}", native)[1]
        ids_body = re.search(r"sOverworldWildLegacyEncounterAreaDataIds\[[^\]]+\]\s*=\s*\{([^}]+)\}", native)[1]
        defines = owed.parse_defines(REPO / "include/constants/maps.h")
        actual = list(zip((defines[token] for token in re.findall(r"\bMAP_\w+", maps_body)),
                          map(int, re.findall(r"\b\d+\b", ids_body))))
        self.assertEqual(actual, [(row.map_id, row.data_id) for row in mappings])
        self.assertIn("#define OW_WILD_LEGACY_ENCOUNTER_AREA_COUNT OWED_ENCOUNTER_AREA_COUNT", native)

    def test_lookup_uses_the_native_header_table_where_one_exists(self):
        # The lookup was hand-written from encounter-table comment names; Mt.
        # Silver had shifted onto the wrong rooms (summit given 3F's table,
        # 2F omitted). A map whose stock header names a table must use it.
        arm9 = REPO / "build/arm9.bin"
        if not arm9.exists():
            self.skipTest("stock build/arm9.bin is absent")
        raw = arm9.read_bytes()
        table, row_size, vanilla_count, no_table = 0xF6BE0, 24, 540, 0xFF
        mappings = owed.parse_mapping(REPO / "data/OverworldWildEncounterLookupData.c",
                                      REPO / "include/constants/maps.h")
        wrong = {row.map_id: (row.data_id, raw[table + row.map_id * row_size])
                 for row in mappings
                 if row.map_id < vanilla_count
                 and raw[table + row.map_id * row_size] not in (no_table, row.data_id)}
        self.assertEqual(wrong, {})
        lookup = {row.map_id for row in mappings}
        # Every stock map whose header names a table must be listed, or the
        # map silently never spawns. Deliberate exclusions need a reason.
        excluded = {
            357: "Safari Zone: stock rolls per-area a/2/3/0 data; header table 91 is an all-Rattata placeholder",
        }
        unlisted = {map_id: raw[table + map_id * row_size] for map_id in range(vanilla_count)
                    if raw[table + map_id * row_size] != no_table
                    and map_id not in lookup and map_id not in excluded}
        self.assertEqual(unlisted, {})
        self.assertFalse(lookup & excluded.keys())
        for map_id in (463, 464, 459):  # Mt. Silver 2F, 3F, upper mountainside
            self.assertIn(map_id, lookup)
        self.assertNotIn(465, lookup)  # summit: no native table, no encounter tiles

    def test_strict_policy_survives_sparse_directory_without_changing_old_payload(self):
        plain = bytearray(196)
        plain[8:20] = bytes(LEVELS)
        struct.pack_into("<12H", plain, 20, *([19] * 12))
        strict = bytearray(plain)
        strict[6] = 1
        self.assertEqual(owed.encode_sparse_record(plain), owed.encode_sparse_record(strict))
        blob = owed.build_blob([owed.EncounterMapping(1, 0), owed.EncounterMapping(2, 1)], [plain, strict])
        rows = list(struct.iter_unpack("<HHIHH", blob[32:56]))
        self.assertEqual([row[4] for row in rows], [0, 1])
        self.assertEqual(rows[0][2:4], rows[1][2:4])
        for offset, value in ((6, 2), (6, 0x80), (7, 1)):
            with self.subTest(offset=offset, value=value):
                bad = bytearray(plain)
                bad[offset] = value
                with self.assertRaisesRegex(ValueError, "time policy|padding"):
                    owed.build_blob([owed.EncounterMapping(1, 0)], [bad])

    def test_owed_validator_checks_clock_policy_against_narc(self):
        from scripts import validate_overworld_wild_blobs as validator
        plain = bytearray(196)
        strict = bytearray(plain)
        strict[6] = 1
        blob = owed.build_blob([owed.EncounterMapping(1, 0), owed.EncounterMapping(2, 1)], [plain, strict])
        with tempfile.TemporaryDirectory(prefix="goldenrod-clock-policy-") as directory:
            header = Path(directory) / "header.h"
            output = Path(directory) / "owed.bin"
            header.write_text("#define OWED_ENCOUNTER_AREA_COUNT 2\n")
            output.write_bytes(blob)
            with mock.patch.object(validator, "read_narc_members", return_value=[plain, strict]):
                validator.validate_owed(output, header, Path("test-members.narc"))
                for value, reason in ((0, "clock policy mismatch"), (2, "bad flags")):
                    bad = bytearray(blob)
                    struct.pack_into("<H", bad, 32 + 12 + 10, value)
                    struct.pack_into("<I", bad, 24, owed.owed_checksum(bad))
                    output.write_bytes(bad)
                    with self.assertRaisesRegex(ValueError, reason):
                        validator.validate_owed(output, header, Path("test-members.narc"))

    def test_scoped_actual_resolver_preserves_normal_movement_and_other_maps(self):
        catalog = json.loads(VIEWER.BEHAVIOR_CATALOG_SOURCE.read_text())
        baseline = copy.deepcopy(catalog)
        baseline["profiles"] = [p for p in baseline["profiles"] if p["id"] not in PLACEMENT_IDS]
        baseline["applications"] = [a for a in baseline["applications"] if a["id"] not in APPLICATION_IDS]
        _, _, macros = VIEWER.behavior_authoring_context()
        expected = {"MEOWTH": 2049, "RATTATA": 2049, "TRUBBISH": 2049,
                    "GRIMER": 2049, "ROTOM": 2049, "SNUBBULL": 1,
                    "PIDOVE": 65, "MURKROW": 68}
        with tempfile.TemporaryDirectory(prefix="goldenrod-resolve-") as directory:
            temp = Path(directory)
            source = temp / "baseline.json"
            source.write_text(json.dumps(baseline))
            old = native_resolver.build(REPO, catalog=source, output=temp / "old", force=True)
            current = native_resolver.build(REPO, output=temp / "current", force=True)
            for name, destination in expected.items():
                for map_id in (76, 199, 29, 34):
                    with self.subTest(species=name, map=map_id):
                        request = {**REQUEST, "species": macros["SPECIES_" + name], "level": 16, "mapId": map_id}
                        before = native_resolver.resolve(None, request, root=REPO, executable=old)
                        after = native_resolver.resolve(None, request, root=REPO, executable=current)
                        left, right = bytes.fromhex(before["profileHex"]), bytes.fromhex(after["profileHex"])
                        changed = map_id == 76 or map_id == 199 and name in ("RATTATA", "GRIMER")
                        allowed = {52, 53, 54, 55} if changed else set()
                        if map_id == 76 and name in ("PIDOVE", "MURKROW"):
                            allowed.update((32, 33, 34, 35))
                        for lane in (0, 1):
                            for byte in range(80):
                                if byte not in allowed:
                                    self.assertEqual(left[lane * 80 + byte], right[lane * 80 + byte], (name, map_id, lane, byte))
                            if changed:
                                start = lane * 80 + 52
                                self.assertEqual(int.from_bytes(right[start:start + 2], "little"),
                                                 destination if map_id == 76 else 1)
                        self.assertEqual(before["primitivesHex"], after["primitivesHex"])
            for map_id in (76, 199):
                request = {**REQUEST, "species": 155, "mapId": map_id}
                self.assertEqual(native_resolver.resolve(None, request, root=REPO, executable=old)["profileHex"],
                                 native_resolver.resolve(None, request, root=REPO, executable=current)["profileHex"])

    def test_actual_c_clock_choice_and_weighted_roll(self):
        source = (REPO / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c").read_text()
        routes, _ = route_data()
        structs = []
        for name in ("OverworldWildHelperLandEncounterData", "OverworldWildHelperEncounterDataSlot", "OverworldWildHelperEncounterData"):
            structs.append(re.search(r"typedef struct " + name + r"\s*\{.*?\}\s*" + name + r";", source, re.S)[0])
        functions = "\n".join(function(source, name, returns) for name, returns in (
            ("OverworldWildHelper_RollWeightedSlot", "u8"),
            ("OverworldWildHelper_GetTimeOfDaySpeciesTable", "const u16 *"),
            ("OverworldWildHelper_TryRollLandEncounter", "BOOL")))
        data = []
        for time in ("morning", "day", "night"):
            data.append("{" + ",".join(str(slot["species"]["value"]) for slot in species_slots(routes[142], time)) + "}")
        prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define SPECIES_NONE 0
#define OW_WILD_HELPER_GRASS_SLOTS 12
#define OW_WILD_HELPER_SURF_SLOTS 5
#define OW_WILD_HELPER_FISH_SLOTS 5
#define OW_WILD_HELPER_SPECIES_MASK 0x7FF
#define OW_WILD_HELPER_FORM_SHIFT 11
#define OW_WILD_HELPER_RANDOM_TIME_TABLE_CHANCE_PERCENT 20
#define TIMEOFDAY_WILD_MORN 0
#define TIMEOFDAY_WILD_DAY 1
#define TIMEOFDAY_WILD_NITE 2
typedef struct {u16 species;u8 form,level;} OverworldWildRolledEncounter;
static u32 randoms[4];static int calls, now;
static u32 gf_rand(void) {assert(calls<4);return randoms[calls++];}
static int GF_RTC_GetTimeOfDayWildParam(void) {return now;}
static const u8 sOverworldWildHelperGrassSlotWeights[]={20,20,10,10,10,10,5,5,4,4,1,1};
'''
        driver = r'''
int main(void) {
 OverworldWildHelperEncounterData e={0};OverworldWildRolledEncounter out={0};
 const u16 rows[3][12]=TABLES;const u8 levels[12]=LEVELS;
 memcpy(e.landSlots.levels,levels,12);memcpy(e.landSlots.morningSpecies,rows,72);
 e.overworldTimePolicy=1;
 for(now=0;now<3;now++) {
  calls=0;randoms[0]=0;randoms[1]=2;
  assert(OverworldWildHelper_GetTimeOfDaySpeciesTable(&e.landSlots,1)==e.landSlots.morningSpecies+now*12);
  assert(calls==0);
  for(int roll=0;roll<100;roll++) {
   int slot=0,remaining=roll;while(remaining>=sOverworldWildHelperGrassSlotWeights[slot])remaining-=sOverworldWildHelperGrassSlotWeights[slot++];
   calls=0;randoms[0]=roll;assert(OverworldWildHelper_TryRollLandEncounter(&e,&out));
   assert(calls==1 && out.species==rows[now][slot] && out.level==levels[slot]);
  }
 }
 // A legacy pool still takes the existing20% random-time branch.
 e.overworldTimePolicy=0;now=1;calls=0;randoms[0]=0;randoms[1]=2;randoms[2]=99;
 assert(OverworldWildHelper_TryRollLandEncounter(&e,&out));assert(calls==3 && out.species==rows[2][11]);
 calls=0;randoms[0]=20;randoms[1]=99;
 assert(OverworldWildHelper_TryRollLandEncounter(&e,&out));assert(calls==2 && out.species==rows[1][11]);
 return 0;
}
'''.replace("TABLES", "{" + ",".join(data) + "}").replace("LEVELS", "{" + ",".join(map(str, LEVELS)) + "}")
        with tempfile.TemporaryDirectory(prefix="goldenrod-clock-") as directory:
            temp = Path(directory)
            file = temp / "clock.c"
            file.write_text(prelude + "\n".join(structs) + functions + driver)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", str(file), "-o", str(temp / "clock")], check=True, capture_output=True)
            subprocess.run([str(temp / "clock")], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()

"""Prove large authored catalogs reach the real C Resolver through small banks."""

import copy
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools/overworld-viewer-v2"))

import native_resolver
import overworld_behavior_profile_viewer as authoring
from overworld_application_bank_compiler import BankCapacityError, compile_bank, _species_values
import validate_overworld_wild_blobs as blob_validator
from tools.overworld.test_spawn_spatial import extract_function


class ApplicationBankCapacityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        self.species_header = ROOT / "include/constants/species.h"

    def test_generated_shared_blob_validates_and_rejects_bad_slices(self):
        """Validate the real generated C blob, including its owner sidecars."""
        with tempfile.TemporaryDirectory(prefix="application-bank-blob-") as name:
            scratch = Path(name)
            source, executable = scratch / "dump.c", scratch / "dump"
            source.write_text('''#include <stddef.h>
#include <stdio.h>
#include "overworld_wild_behavior_data.h"
extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;
int main(void){
    fprintf(stderr,"%zu %zu %zu %u %u %u\\n",
        offsetof(OverworldWildBehaviorDataBlob,applicationBankDirectory),
        offsetof(OverworldWildBehaviorDataBlob,applicationBankIndexes),
        offsetof(OverworldWildBehaviorDataBlob,conditionGlobalApplications),
        OWBD_APPLICATION_BANK_DIRECTORY_COUNT,OWBD_APPLICATION_BANK_INDEX_COUNT,
        OWBD_OVERRIDE_PROFILE_COUNT);
    return fwrite(&gOverworldWildBehaviorDataBlob,1,
        sizeof(gOverworldWildBehaviorDataBlob),stdout)
        !=sizeof(gOverworldWildBehaviorDataBlob);
}
''')
            subprocess.run(["cc", "-std=c99", "-DOVERWORLD_BEHAVIOR_HOST",
                "-I", str(ROOT / "include"), "-I", str(ROOT / "data"),
                str(ROOT / "data/OverworldWildBehaviorData.c"), str(source),
                "-o", str(executable)], check=True, capture_output=True)
            dumped = subprocess.run([str(executable)], check=True, capture_output=True)
            blob = bytearray(dumped.stdout)
            directory, indexes, owners, row_count, index_count, app_count = map(
                int, dumped.stderr.split())
            rows = [struct.unpack_from("<HHBB", blob, directory + n * 6)
                    for n in range(row_count)]
            spans = [(first, count) for _, first, count, _ in rows if count]
            shared = next(span for span in spans if spans.count(span) > 1 and span[1] > 1)
            first_shared = next(i for i, row in enumerate(rows) if row[1:3] == shared)
            later_shared = next(i for i, row in enumerate(rows)
                                if i > first_shared and row[1:3] == shared)
            target = scratch / "behavior.bin"
            header = ROOT / "include/overworld_wild_behavior_data.h"

            def validate(data):
                target.write_bytes(data)
                blob_validator.validate_owbd(target, header)

            validate(blob)
            cases = []
            bad = blob.copy()
            struct.pack_into("<H", bad, directory + first_shared * 6 + 2, index_count)
            cases.append(("range", bad, "application bank row.*invalid"))
            bad = blob.copy()
            struct.pack_into("<B", bad, directory + first_shared * 6 + 4, 33)
            cases.append(("capacity", bad, "application bank row.*invalid"))
            bad = blob.copy()
            struct.pack_into("<H", bad, directory + 6, rows[0][0])
            cases.append(("species-order", bad, "application bank row.*invalid"))
            bad = blob.copy()
            struct.pack_into("<H", bad, indexes + shared[0] * 2, app_count)
            cases.append(("global-id", bad, "invalid global IDs"))
            bad = blob.copy()
            struct.pack_into("<H", bad, indexes + (shared[0] + 1) * 2,
                             struct.unpack_from("<H", bad, indexes + shared[0] * 2)[0])
            cases.append(("id-order", bad, "invalid global IDs"))
            bad = blob.copy()
            struct.pack_into("<HB", bad, directory + later_shared * 6 + 2,
                             shared[0] + 1, shared[1] - 1)
            cases.append(("partial-alias", bad, "partially overlaps"))
            # Redirect every owner of one whole slice to another legal whole
            # slice. Bounds and IDs still pass, but its old storage is orphaned.
            lost = next(span for span in spans if span != shared)
            bad = blob.copy()
            for n, row in enumerate(rows):
                if row[1:3] == lost:
                    struct.pack_into("<HB", bad, directory + n * 6 + 2, *shared)
            cases.append(("unowned-storage", bad, "index table is incomplete"))
            bad = blob.copy()
            struct.pack_into("<H", bad, owners, app_count)
            cases.append(("condition-owner", bad, "invalid global owner"))
            for label, broken, error in cases:
                with self.subTest(fault=label), self.assertRaisesRegex(ValueError, error):
                    validate(broken)

    def test_equal_ordered_banks_share_storage_and_real_c_selection(self):
        def subjects(*symbols):
            return {"mode": "members", "members": list(symbols)}

        catalog = {
            "profiles": [
                {"id": "normal", "kind": "normal", "fields": {}},
                {"id": "conditional", "kind": "conditional", "fields": {},
                 "conditions": [{"subjects": {"mode": "all"}},
                                {"subjects": subjects("SPECIES_FARFETCHD")}]},
            ],
            "applications": [
                {"id": "common", "profile": "normal", "target": {"mode": "all"}},
                {"id": "pair", "profile": "normal",
                 "target": subjects("SPECIES_PIDGEY", "SPECIES_SPEAROW")},
                {"id": "different", "profile": "normal",
                 "target": subjects("SPECIES_MANKEY")},
                {"id": "conditional", "profile": "conditional"},
                *({"id": role, "profile": "normal", "target": {"mode": "disabled"}}
                  for role in ("follower", "mounted", "asleep", "tired")),
            ],
            "runtimeBindings": {"followerApplication": "follower",
                "mountedApplication": "mounted", "forcedAsleepApplication": "asleep",
                "defaultTiredApplication": "tired"},
        }
        bank = compile_bank(catalog, self.species_header)
        self.assertEqual(bank, compile_bank(catalog, self.species_header))
        rows = {row[0]: row for row in bank["rows"]}
        expected = {16: [0, 1, 3, 4, 5, 6], 21: [0, 1, 3, 4, 5, 6],
                    56: [0, 2, 3, 4, 5, 6], 83: [0, 3, 4, 5, 6],
                    155: [0, 3, 4, 5, 6]}
        self.assertEqual([row[0] for row in bank["rows"]], [16, 21, 56, 83, "0xFFFF"])
        self.assertEqual(rows[16][1], rows[21][1])
        self.assertNotEqual(rows[16][1], rows[56][1])
        self.assertEqual(rows[83][1], rows["0xFFFF"][1])
        self.assertEqual(len(bank["indexes"]), sum(map(len, {tuple(x) for x in expected.values()})))
        self.assertLess(len(bank["indexes"]), sum(row[2] for row in bank["rows"]))

        with tempfile.TemporaryDirectory(prefix="application-bank-intern-") as name:
            scratch = Path(name)
            actual = self._compiled_bank_selection(scratch / "shared", bank,
                                                   len(catalog["applications"]), expected)
            self.assertEqual(actual, expected)
            # The same native selector must return the same full ordered IDs
            # with the old physical layout, not merely valid slice bounds.
            unshared = copy.deepcopy(bank)
            unshared["rows"], unshared["indexes"] = [], []
            for species, first, count in bank["rows"]:
                unshared["rows"].append((species, len(unshared["indexes"]), count))
                unshared["indexes"].extend(bank["indexes"][first:first + count])
            self.assertEqual(self._compiled_bank_selection(scratch / "unshared", unshared,
                len(catalog["applications"]), expected), actual)

            wrong_alias = copy.deepcopy(bank)
            index = next(i for i, row in enumerate(bank["rows"]) if row[0] == 56)
            wrong_alias["rows"][index] = (56, rows[16][1], rows[56][2])
            self.assertNotEqual(self._compiled_bank_selection(scratch / "wrong-alias", wrong_alias,
                len(catalog["applications"]), expected)[56], expected[56])
            for fault, change in (
                ("reversed", lambda b: b["indexes"].__setitem__(
                    slice(rows[16][1], rows[16][1] + rows[16][2]), list(reversed(expected[16])))),
                ("out-of-range", lambda b: b["rows"].__setitem__(
                    0, (16, len(b["indexes"]), rows[16][2]))),
                ("over-capacity", lambda b: b["rows"].__setitem__(0, (16, rows[16][1], 33))),
                ("bad-global-id", lambda b: b["indexes"].__setitem__(
                    rows[16][1], len(catalog["applications"]))),
            ):
                broken = copy.deepcopy(bank)
                change(broken)
                with self.subTest(fault=fault):
                    self.assertIsNone(self._compiled_bank_selection(scratch / fault, broken,
                        len(catalog["applications"]), expected)[16])

    def test_more_than_255_enabled_apps_and_32_total_conditions_reach_c(self):
        catalog = copy.deepcopy(self.catalog)
        applications = catalog["applications"]
        style = next(a for a in applications if a["id"] == "apply-waddle")
        insertion = applications.index(style) + 1
        species_by_id = {}
        for symbol, value in _species_values(self.species_header).items():
            if 1 <= value <= 493:
                species_by_id.setdefault(value, symbol)
        species = sorted(species_by_id.items())[:270]
        self.assertEqual(len(species), 270)
        additions = []
        for index, (_, symbol) in enumerate(species):
            application = copy.deepcopy(style)
            application["id"] = f"growth-style-{index}"
            application["target"]["members"] = [symbol]
            additions.append(application)
        applications[insertion:insertion] = additions

        playful = next(p for p in catalog["profiles"] if p["id"] == "playful")
        template = playful["conditions"][0]
        playful["conditions"] = []
        for index, (_, symbol) in enumerate(species[:33]):
            condition = copy.deepcopy(template)
            condition["id"] = f"growth-condition-{index}"
            condition["subjects"] = {
                "mode": "members", "match": copy.deepcopy(style["target"]["match"]),
                "members": [symbol],
            }
            playful["conditions"].append(condition)

        authoring.validate_behavior_catalog(catalog)
        runtime = authoring._runtime_source_behavior_catalog(catalog)
        bank = compile_bank(runtime, self.species_header)
        self.assertGreater(len(runtime["applications"]), 255)
        self.assertLessEqual(max(row[2] for row in bank["rows"]), 32)
        selected = additions[-1]
        global_id = next(i for i, a in enumerate(runtime["applications"])
                         if a["id"] == selected["id"])
        self.assertGreater(global_id, 255)
        subject = species[-1][0]
        _, first, count = next(row for row in bank["rows"] if row[0] == subject)
        local_ids = bank["indexes"][first:first + count]
        local_slot = local_ids.index(global_id)
        with tempfile.TemporaryDirectory(prefix="application-bank-capacity-") as scratch:
            scratch = Path(scratch)
            source = scratch / "catalog.json"
            source.write_text(json.dumps(catalog))
            executable = native_resolver.build(ROOT, catalog=source, output=scratch / "resolver")
            result = native_resolver.resolve(None, {"species": subject, "level": 10},
                                             root=ROOT, executable=executable)
        self.assertEqual(result["status"], 0)
        self.assertTrue(result["appliedOverrideMask"] & (1 << local_slot))
        self.assertTrue(any(step["sourceIndex"] == global_id and step["lane"] == 0
                            and step["kind"] == 3 and step["flags"] & 2
                            for step in result["trace"]))

    def test_one_subject_application_overflow_is_rejected(self):
        runtime = authoring._runtime_source_behavior_catalog(self.catalog)
        template = next(a for a in runtime["applications"] if a["id"] == "apply-scavenger")
        for index in range(33):
            application = copy.deepcopy(template)
            application["id"] = f"overflow-application-{index}"
            runtime["applications"].append(application)
        with self.assertRaisesRegex(BankCapacityError, "local application bits"):
            compile_bank(runtime, self.species_header)

    def test_one_subject_condition_overflow_is_rejected(self):
        runtime = authoring._runtime_source_behavior_catalog(self.catalog)
        template = next(a for a in runtime["applications"] if a["id"] == "apply-throw")
        for index in range(6):
            application = copy.deepcopy(template)
            application["id"] = f"overflow-condition-{index}"
            runtime["applications"].append(application)
        with self.assertRaisesRegex(BankCapacityError, "local condition entries"):
            compile_bank(runtime, self.species_header)

    def test_forced_follower_and_mount_roles_use_subject_local_bits(self):
        """The actual shared C request builder must agree with the C Resolver."""
        source = (ROOT / "lib/overworld/overworld_player_damage_condition.c").read_text()
        body = extract_function(source, "OverworldBehaviorCondition_BuildRequest", "BOOL")
        shift = "local >= 0 ? 1u << local : 0"
        self.assertEqual(body.count(shift), 1)
        old_shift = ("forcedGlobalApplication >= 0 "
                     "&& forcedGlobalApplication < OWBD_MASKABLE_APPLICATION_COUNT "
                     "? 1u << forcedGlobalApplication : 0")
        copied_old_body = body.replace(shift, old_shift)

        large = copy.deepcopy(self.catalog)
        applications = large["applications"]
        follower_name = large["runtimeBindings"]["followerApplication"]
        insertion = next(i for i, app in enumerate(applications)
                         if app["id"] == follower_name)
        style = next(app for app in applications if app["id"] == "apply-waddle")
        species_by_id = {}
        for symbol, value in _species_values(self.species_header).items():
            if 1 <= value <= 493:
                species_by_id.setdefault(value, symbol)
        species = sorted(species_by_id.items())[:270]
        self.assertEqual(len(species), 270)
        additions = []
        for index, (_, symbol) in enumerate(species):
            app = copy.deepcopy(applications[insertion])
            app["id"] = f"forced-role-growth-{index}"
            app["target"] = copy.deepcopy(style["target"])
            app["target"]["members"] = [symbol]
            additions.append(app)
        applications[insertion:insertion] = additions

        with tempfile.TemporaryDirectory(prefix="application-bank-roles-") as name:
            scratch = Path(name)
            for label, catalog in (("current", self.catalog), ("large", large)):
                authoring.validate_behavior_catalog(catalog)
                runtime = authoring._runtime_source_behavior_catalog(catalog)
                bank = compile_bank(runtime, self.species_header)
                self.assertLessEqual(max(row[2] for row in bank["rows"]), 32)
                catalog_file = scratch / f"{label}.json"
                catalog_file.write_text(json.dumps(catalog))
                resolver = native_resolver.build(
                    ROOT, catalog=catalog_file, output=scratch / f"{label}-resolver")
                applications = runtime["applications"]
                for role, subject in (("follower", 155), ("mounted", 234)):
                    role_name = catalog["runtimeBindings"][role + "Application"]
                    global_id = next(i for i, app in enumerate(applications)
                                     if app["id"] == role_name)
                    row = next((row for row in bank["rows"] if row[0] == subject),
                               bank["rows"][-1])
                    local_ids = bank["indexes"][row[1]:row[1] + row[2]]
                    local_slot = local_ids.index(global_id)
                    if label == "large":
                        self.assertGreater(global_id, 255)
                    expected = 1 << local_slot
                    actual = self._compiled_role_mask(scratch / f"{label}-{role}",
                                                      bank, len(applications), subject,
                                                      global_id, body)
                    old = self._compiled_role_mask(scratch / f"{label}-{role}-old",
                                                   bank, len(applications), subject,
                                                   global_id, copied_old_body)
                    self.assertEqual(actual, expected)
                    self.assertNotEqual(old, expected)
                    accepted = native_resolver.resolve(None, dict(species=subject,
                        level=50, forcedOverrideMask=actual), root=ROOT,
                        executable=resolver)
                    self.assertEqual((accepted["status"],
                        accepted["forcedOverrideMask"]), (0, expected))
                    old_call = subprocess.run([str(resolver), "--species", str(subject),
                        "--level", "50", "--terrain", "0", "--shiny", "0",
                        "--groups", "0", "--forced-override-mask", str(old),
                        "--behavior-class", "0", "--request-version", "2"],
                        capture_output=True, text=True)
                    rejected = json.loads(old_call.stdout)
                    if global_id < 32:
                        self.assertEqual(rejected["status"], 3)
                    else:
                        # Old u8-range logic silently omits a forced role >255.
                        self.assertEqual((old, rejected["status"],
                            rejected["forcedOverrideMask"]), (0, 0, 0))

    def _bank_fixture(self, case, bank, application_count):
        case.mkdir()
        rows, indexes = bank["rows"], bank["indexes"]
        fake_header = f"""#ifndef OW_FAKE_DATA_H
#define OW_FAKE_DATA_H
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OWBD_MASKABLE_APPLICATION_COUNT 32
#define OWBD_APPLICATION_BANK_DIRECTORY_COUNT {len(rows)}
#define OWBD_APPLICATION_BANK_INDEX_COUNT {len(indexes)}
typedef struct {{u16 species;u16 first;u8 count;u8 reserved;}} OverworldApplicationBankDirectoryEntry;
typedef struct {{int unused;}} OverworldWildBehaviorOverrideProfile;
typedef struct {{struct {{u16 overrideProfileCount;}} header;
    OverworldApplicationBankDirectoryEntry applicationBankDirectory[{len(rows)}];
    u16 applicationBankIndexes[{len(indexes)}];
    OverworldWildBehaviorOverrideProfile overrideProfiles[1];
}} OverworldWildBehaviorDataBlob;
#endif
"""
        (case / "overworld_wild_behavior_data.h").write_text(fake_header)
        shutil.copyfile(ROOT / "include/overworld_application_bank.h",
                        case / "overworld_application_bank.h")
        directory = ",".join("{%d,%d,%d,0}" % (
            row[0] if isinstance(row[0], int) else 0xFFFF, row[1], row[2])
            for row in rows)
        index_values = ",".join(map(str, indexes))
        initializer = ("static const OverworldWildBehaviorDataBlob blob={"
                       f".header={{{application_count}}},"
                       f".applicationBankDirectory={{{directory}}},"
                       f".applicationBankIndexes={{{index_values}}}}};\n")
        return initializer

    def _compiled_bank_selection(self, case, bank, application_count, species):
        initializer = self._bank_fixture(case, bank, application_count)
        source = case / "driver.c"
        source.write_text("#include <stdio.h>\n#include <stdlib.h>\n"
            '#include "overworld_application_bank.h"\n' + initializer + """
int main(int argc,char **argv){
    for(int i=1;i<argc;i++){
        unsigned species=(unsigned)strtoul(argv[i],NULL,10);
        OverworldApplicationBank bank;
        printf("%u",species);
        if(!OverworldApplicationBank_Select(&blob,(u16)species,&bank)) printf(" invalid");
        else for(unsigned n=0;n<bank.count;n++) printf(" %u",bank.globalIds[n]);
        putchar('\\n');
    }
    return 0;
}
""")
        executable = case / "driver"
        subprocess.run(["cc", "-std=c99", "-O0", "-Wall", "-Wextra", "-I",
                        str(case), str(source), "-o", str(executable)],
                       check=True, capture_output=True, text=True)
        output = subprocess.check_output([str(executable), *map(str, species)], text=True)
        return {int(parts[0]): None if parts[1:] == ["invalid"] else list(map(int, parts[1:]))
                for line in output.splitlines() if (parts := line.split())}

    def _compiled_role_mask(self, case, bank, application_count, species,
                            global_id, body):
        initializer = self._bank_fixture(case, bank, application_count)
        prelude = """#include <stdio.h>
#include <string.h>
#include "overworld_application_bank.h"
#define BEHAVIOR_RESOLVE_REQUEST_VERSION 2
typedef struct {u16 species;u8 behaviorClass;} Context;
typedef struct {u8 kind;} Target;
typedef struct {Context context;u32 forcedOverrideMask,activeConditionalMask;
    u16 winningConditionId,resolvedTargetConditionId;
    u8 behaviorClass,requestVersion,targetSourceApplication;Target resolvedTarget;} Request;
typedef struct {u32 activeApplicationMask;u16 winningConditionId,resolvedTargetConditionId;
    u8 resolvedTargetSourceApplication;Target resolvedTarget;} Result;
typedef struct {Context context;Request request;Result result;} OverworldWildBehaviorConditionRuntime;
"""
        driver = (initializer +
                  "int main(void){OverworldWildBehaviorConditionRuntime runtime={0};"
                  f"runtime.context.species={species};"
                  f"int ok=OverworldBehaviorCondition_BuildRequest(&runtime,{global_id},&blob);"
                  'printf("%d %u\\n",ok,runtime.request.forcedOverrideMask);return 0;}\n')
        source = case / "driver.c"
        source.write_text(prelude + body + "\n" + driver)
        executable = case / "driver"
        subprocess.run(["cc", "-std=c99", "-O0", "-Wall", "-Wextra", "-I",
                        str(case), str(source), "-o", str(executable)],
                       check=True, capture_output=True, text=True)
        accepted, mask = map(int, subprocess.check_output([str(executable)],
                                                         text=True).split())
        self.assertEqual(accepted, 1)
        return mask


if __name__ == "__main__":
    unittest.main()

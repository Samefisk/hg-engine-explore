"""Prove large authored catalogs reach the real C Resolver through small banks."""

import copy
import json
from pathlib import Path
import shutil
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
from tools.overworld.test_spawn_spatial import extract_function


class ApplicationBankCapacityTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        self.species_header = ROOT / "include/constants/species.h"

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

    def _compiled_role_mask(self, case, bank, application_count, species,
                            global_id, body):
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
        driver = ("static const OverworldWildBehaviorDataBlob blob={"
                  f".header={{{application_count}}},"
                  f".applicationBankDirectory={{{directory}}},"
                  f".applicationBankIndexes={{{index_values}}}}};\n"
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

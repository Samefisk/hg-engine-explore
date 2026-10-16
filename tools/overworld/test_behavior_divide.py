"""Check /N authoring and the production resolver's packed divide operator."""

from __future__ import annotations

import copy
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.overworld.test_behavior_catalog_v5 import load_viewer
from tools.overworld.test_behavior_resolver_conditions import run_resolver_harness


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "tools/overworld/behavior_schema.json").read_text())
FIELDS = [field for field in SCHEMA["fields"] if "divide" in field["operators"]]
VIEWER = load_viewer()
SPEC = importlib.util.spec_from_file_location(
    "divide_blob_validator", ROOT / "scripts/validate_overworld_wild_blobs.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


BRIDGE = r"""
u8 DivideTest_Read(const OverworldWildBehaviorProfileData *p, u8 field)
{
    return BehaviorResolver_ReadFieldValue(p, field, BehaviorResolver_FieldOffset(field));
}
void DivideTest_Write(OverworldWildBehaviorProfileData *p, u8 field, u8 value)
{
    BehaviorResolver_WriteFieldValue(p, field, BehaviorResolver_FieldOffset(field), value);
}
void DivideTest_Apply(OverworldWildBehaviorProfileData *p,
    const OverworldWildBehaviorOverrideProfile *o)
{
    BehaviorResolver_ApplyOverride(p, o);
}
"""


HARNESS = r"""
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_behavior_resolver.h"
extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;
extern u8 DivideTest_Read(const OverworldWildBehaviorProfileData *, u8);
extern void DivideTest_Write(OverworldWildBehaviorProfileData *, u8, u8);
extern void DivideTest_Apply(OverworldWildBehaviorProfileData *,
    const OverworldWildBehaviorOverrideProfile *);
static const struct { u8 field, minimum, maximum; } fields[] = { FIELD_ROWS };
#define MASK_WORD(o, field, word) (*(u32 *)((u8 *)(o) \
    + offsetof(OverworldWildBehaviorOverrideProfile, field) + (word) * sizeof(u32)))

static void SetOperator(OverworldWildBehaviorOverrideProfile *o,
    u8 field, u8 divisor, int relative)
{
    unsigned word = field < 27 ? 0 : field < 42 ? 1 : 2;
    unsigned bit = field - (word == 0 ? 0 : word == 1 ? 27 : 42);
    u32 mask = 1u << bit;
    MASK_WORD(o, mask, word) = mask;
    MASK_WORD(o, atLeastMask, word) = mask;
    MASK_WORD(o, atMostMask, word) = mask;
    if (relative) MASK_WORD(o, relativeMask, word) = mask;
    DivideTest_Write(&o->profile, field, divisor);
}

static void CheckCase(u8 field, u8 initial, u8 divisor, int relative,
    int minimum, int maximum, int admitted)
{
    OverworldWildBehaviorProfileData p, expected;
    OverworldWildBehaviorOverrideProfile o, saved;
    memset(&p, 0xa5, sizeof(p));
    memset(&o, 0, sizeof(o));
    DivideTest_Write(&p, field, initial);
    SetOperator(&o, field, divisor, relative);
    expected = p;
    saved = o;
    if (admitted) {
        int result = DivideTest_Read(&p, field) / divisor;
        if (result < minimum) result = minimum;
        if (result > maximum) result = maximum;
        DivideTest_Write(&expected, field, result);
    }
    DivideTest_Apply(&p, &o);
    if (memcmp(&p, &expected, sizeof(p))) {
        fprintf(stderr, "field%u initial%u divisor%u: expected%u actual%u\n",
            field, initial, divisor, DivideTest_Read(&expected, field),
            DivideTest_Read(&p, field));
        abort();
    }
    assert(memcmp(&o, &saved, sizeof(o)) == 0);
}

static void Ordering(void)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    BehaviorResolveRequest q;
    BehaviorResolveResult r;
    unsigned i;
    assert(blob);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    for (i = 0; i < blob->header.overrideProfileCount; ++i)
        memset(&blob->overrideProfiles[i], 0, sizeof(blob->overrideProfiles[i]));
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillSpeed = 13;
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].maxWalkSpeed = 1;
    memset(&q, 0, sizeof(q));
    q.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    q.context.level = 5;
    q.context.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    q.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    q.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    q.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    q.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    q.forcedOverrideMask = 3;
    blob->overrideProfiles[0].mask = OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED;
    blob->overrideProfiles[0].relativeMask = OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED;
    blob->overrideProfiles[0].profile.chillSpeed = 2;
    SetOperator(&blob->overrideProfiles[1], 7, 2, 0);
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &q, &r, NULL) == BEHAVIOR_RESOLVE_OK);
    assert(r.profile.owner.chillSpeed == 7); /* (13 + 2) / 2 */
    {
        OverworldWildBehaviorOverrideProfile swap = blob->overrideProfiles[0];
        blob->overrideProfiles[0] = blob->overrideProfiles[1];
        blob->overrideProfiles[1] = swap;
    }
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &q, &r, NULL) == BEHAVIOR_RESOLVE_OK);
    assert(r.profile.owner.chillSpeed == 8); /* (13 / 2) + 2 */
    free(blob);
}

static void LegacyOperators(void)
{
    unsigned i, j, operation;
    const u8 initials[] = {0, 7, 255};
    for (i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i) {
        u8 field = fields[i].field;
        unsigned word = field < 27 ? 0 : field < 42 ? 1 : 2;
        unsigned bit = field - (word == 0 ? 0 : word == 1 ? 27 : 42);
        u32 mask = 1u << bit;
        int maximum = field == 5 || field == 6 ? 64 : field == 39 ? 15
            : field == 44 ? 0 : fields[i].maximum;
        for (j = 0; j < sizeof(initials); ++j)
            for (operation = 0; operation < 6; ++operation) {
                OverworldWildBehaviorProfileData p, expected;
                OverworldWildBehaviorOverrideProfile o;
                int result, threshold = fields[i].maximum < 8 ? fields[i].maximum : 8;
                int relative = operation < 2 || operation >= 4;
                int lower = operation == 2 || operation == 5;
                int upper = operation == 3 || operation == 4;
                int delta = operation == 1 || operation == 5 ? -2 : 2;
                memset(&p, 0xa5, sizeof(p));
                memset(&o, 0, sizeof(o));
                DivideTest_Write(&p, field, initials[j]);
                expected = p;
                result = DivideTest_Read(&p, field);
                MASK_WORD(&o, mask, word) = mask;
                if (relative) MASK_WORD(&o, relativeMask, word) = mask;
                if (lower) MASK_WORD(&o, atLeastMask, word) = mask;
                if (upper) MASK_WORD(&o, atMostMask, word) = mask;
                if (upper) threshold = 4;
                DivideTest_Write(&o.profile, field, relative ? (u8)delta : threshold);
                DivideTest_Write(&o.compoundBoundProfile, field, threshold);
                if (relative) {
                    result += delta;
                    if (result < fields[i].minimum) result = fields[i].minimum;
                    if (result > maximum) result = maximum;
                }
                if (lower && result < threshold) result = threshold;
                if (upper && result > threshold) result = threshold;
                DivideTest_Write(&expected, field, result);
                DivideTest_Apply(&p, &o);
                assert(memcmp(&p, &expected, sizeof(p)) == 0);
            }
    }
}

static void PackedHitOptions(void)
{
    unsigned selected, current, replacement;
    for (selected = 0; selected < 8; ++selected)
        for (current = 0; current < 256; ++current)
            for (replacement = 0; replacement < 256; ++replacement) {
                OverworldWildBehaviorProfileData p, expected;
                OverworldWildBehaviorOverrideProfile o;
                memset(&p, 0xa5, sizeof(p));
                memset(&o, 0, sizeof(o));
                p.knockbackOptions = current;
                expected = p;
                o.mask2 = selected << 20;
                o.profile.knockbackOptions = replacement;
                /* Use the existing field setters as the independent control. */
                if (selected & 1)
                    OW_WILD_BEHAVIOR_SET_KNOCKBACK_TYPE(expected.knockbackOptions,
                        OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(replacement));
                if (selected & 2)
                    OW_WILD_BEHAVIOR_SET_KNOCKBACK_DISTANCE(expected.knockbackOptions,
                        OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(replacement));
                if (selected & 4)
                    OW_WILD_BEHAVIOR_SET_DAMAGE_RECIPIENTS(expected.knockbackOptions,
                        OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(replacement));
                DivideTest_Apply(&p, &o);
                assert(memcmp(&p, &expected, sizeof(p)) == 0);
                assert(o.profile.knockbackOptions == replacement);
            }
}

int main(int argc, char **argv)
{
    unsigned i, j, k, cases = 0;
    const u8 initials[] = {0, 1, 7, 16, 255};
    const u8 divisors[] = {1, 2, 3, 127};
    assert(sizeof(OverworldWildBehaviorProfileData) == 80);
    assert(sizeof(OverworldWildBehaviorProfile) == 160);
    assert(sizeof(OverworldWildBehaviorOverrideProfile) == 228);
    for (i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i) {
        for (j = 0; j < sizeof(initials); ++j)
            for (k = 0; k < sizeof(divisors); ++k) {
                CheckCase(fields[i].field, initials[j], divisors[k], 0,
                    fields[i].minimum, fields[i].maximum, 1);
                ++cases;
            }
        CheckCase(fields[i].field, 7, 0, 0, 0, 0, 0);
        CheckCase(fields[i].field, 7, 2, 1, 0, 0, 0);
    }
    CheckCase(7, 7, 128, 0, 0, 0, 0);
    CheckCase(7, 7, 255, 0, 0, 0, 0);
    for (i = 0; i < 256; ++i)
        CheckCase(7, 7, i, 0, 1, 32, i >= 1 && i <= 127);
    CheckCase(0, 7, 2, 0, 0, 0, 0); /* enum */
    CheckCase(67, 33, 2, 0, 0, 0, 0); /* legacy acceleration mode */
    CheckCase(67, 34, 2, 0, 0, 0, 0); /* Linear mode */
    Ordering();
    LegacyOperators();
    PackedHitOptions();
    if (argc > 1) {
        FILE *f = fopen(argv[1], "wb");
        assert(f);
        assert(fwrite(&gOverworldWildBehaviorDataBlob, sizeof(gOverworldWildBehaviorDataBlob), 1, f) == 1);
        assert(fclose(f) == 0);
    }
    printf("%u actual-C divide cases; invalid guards, packed neighbors, ordering and ABI pass\n", cases);
    return 0;
}
"""


class BehaviorDivideTests(unittest.TestCase):
    def test_authoring_formula_limits_and_old_operators(self):
        _, _, macros = VIEWER.behavior_authoring_context()
        self.assertEqual(len(FIELDS), 36)
        for field in FIELDS:
            key = field["key"]
            for divisor in (1, 2, 3, 127):
                raw = f"/{divisor}"
                authored = {"operator": "divide", "value": divisor}
                VIEWER._validate_catalog_override_field(key, authored, "test")
                self.assertEqual(VIEWER.canonical_profile_change_raw(
                    key, raw, macros, allow_relative=True), raw)
                self.assertEqual(VIEWER._catalog_override_field(key, raw), authored)
                self.assertEqual(VIEWER._catalog_override_raw(key, authored), raw)
            for bad in (0, 128, 255, -2, True):
                with self.assertRaises(VIEWER.ParseError):
                    VIEWER._validate_catalog_override_field(
                        key, {"operator": "divide", "value": bad}, "test")
            for raw in ("/0", "/128"):
                with self.assertRaises(ValueError):
                    VIEWER.canonical_profile_change_raw(
                        key, raw, macros, allow_relative=True)
        for key in ("chillState", "chillAction", "walkAccelerationStep", "mountStride"):
            with self.assertRaises(VIEWER.ParseError):
                VIEWER._validate_catalog_override_field(
                    key, {"operator": "divide", "value": 2}, "test")
        with self.assertRaises(ValueError):
            VIEWER.canonical_profile_change_raw("chillSpeed", "/2", macros)
        for raw in ("-2", "/<8", "/>8", "-2, /<8", "+2, />8"):
            authored = VIEWER._catalog_override_field("chillSpeed", raw)
            VIEWER._validate_catalog_override_field("chillSpeed", authored, "test")
            self.assertEqual(VIEWER._catalog_override_raw("chillSpeed", authored), raw)

    def test_generated_parse_display_and_export_roundtrip(self):
        catalog = copy.deepcopy(VIEWER.load_behavior_catalog_v4())
        profiles = {p["id"]: p for p in catalog["profiles"]}
        for application in catalog["applications"]:
            profile = profiles[application["profile"]]
            if profile["id"] in {"throw", "throw-find-position"}:
                profile["fields"]["chillSpeed"] = {"operator": "divide", "value": 2}
                profile["fields"]["hopTime"] = {"operator": "divide", "value": 2}
        source = VIEWER.render_behavior_catalog(catalog, VIEWER.BEHAVIOR_DATA_SOURCE.read_text())
        _, _, macros = VIEWER.behavior_authoring_context()
        parsed = VIEWER.parse_behavior_override_profiles(VIEWER.strip_c_comments(source), macros)
        divides = [p["behavior"] for p in parsed if p["behavior"]["divideFields"]]
        self.assertGreaterEqual(len(divides), 2)
        for profile in divides:
            for field in profile["divideFields"]:
                value = profile["profile"][field]
                raw = f"/{value['value']}"
                self.assertEqual(value["raw"], raw)
                self.assertEqual(VIEWER.canonical_profile_value_raw(value, field), raw)
                exported = VIEWER.profile_numeric_view(profile["profile"])[field]
                self.assertEqual(exported["raw"], raw)
                self.assertEqual(VIEWER._catalog_override_field(field, exported["raw"]),
                    {"operator": "divide", "value": value["value"]})
                self.assertNotIn(field, profile["atLeastFields"])
                self.assertNotIn(field, profile["atMostFields"])
                self.assertNotIn(field, profile["relativeFields"])

    def test_actual_c_matrix_and_blob_validation(self):
        rows = ",\n".join("{%d,%d,%d}" % (
            f["mask"]["bit"] + {1: 0, 2: 27, 3: 42}[f["mask"]["word"]],
            f["bounds"]["min"], f["bounds"]["max"]) for f in FIELDS)
        resolver = (ROOT / "lib/overworld/overworld_behavior_resolver.c").read_text()
        with tempfile.TemporaryDirectory(prefix="behavior-divide-") as directory:
            blob_path = Path(directory) / "behavior.bin"
            compiled, completed = run_resolver_harness(
                HARNESS.replace("FIELD_ROWS", rows), resolver + BRIDGE, (blob_path,))
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("720 actual-C divide cases", completed.stdout)
            source = VIEWER.BEHAVIOR_DATA_HEADER
            VALIDATOR.validate_owbd(blob_path, source)
            pristine = blob_path.read_bytes()
            override = struct.unpack_from("<I", pristine, 36)[0]
            # A fresh numeric override in the real generated blob exercises
            # operands above the field maximum, without changing the layout.
            changed = bytearray(pristine)
            struct.pack_into("<3I", changed, override + 20, 1 << 7, 0, 0)
            struct.pack_into("<9I", changed, override + 112,
                0, 0, 0, 1 << 7, 0, 0, 1 << 7, 0, 0)
            changed[override + 32 + 7] = 127
            blob_path.write_bytes(changed)
            VALIDATOR.validate_owbd(blob_path, source)
            for operand in (0, 128, 255):
                invalid = bytearray(changed)
                invalid[override + 32 + 7] = operand
                blob_path.write_bytes(invalid)
                with self.assertRaisesRegex(Exception, "divide divisor"):
                    VALIDATOR.validate_owbd(blob_path, source)
            invalid = bytearray(changed)
            struct.pack_into("<I", invalid, override + 112, 1 << 7)
            blob_path.write_bytes(invalid)
            with self.assertRaisesRegex(Exception, "divide overlaps relative"):
                VALIDATOR.validate_owbd(blob_path, source)
            invalid = bytearray(changed)
            mode_bit = 1 << 25  # walkAccelerationStep, mask3
            struct.pack_into("<3I", invalid, override + 20, 0, 0, mode_bit)
            struct.pack_into("<9I", invalid, override + 112,
                0, 0, 0, 0, 0, mode_bit, 0, 0, mode_bit)
            invalid[override + 32 + 71] = 2
            blob_path.write_bytes(invalid)
            with self.assertRaisesRegex(Exception, "non-numeric divide"):
                VALIDATOR.validate_owbd(blob_path, source)


if __name__ == "__main__":
    unittest.main()

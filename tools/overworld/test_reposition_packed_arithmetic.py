"""Actual author serialization and portable-C count operators in byte57."""

from pathlib import Path
import importlib.util
import re
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body


ROOT = Path(__file__).resolve().parents[2]
VIEWER_PATH = ROOT / "scripts/overworld_behavior_profile_viewer.py"
RESOLVER = ROOT / "lib/overworld/overworld_behavior_resolver.c"


def viewer():
    spec = importlib.util.spec_from_file_location("count_formula_viewer", VIEWER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RepositionPackedArithmeticTests(unittest.TestCase):
    def test_count_operator_encoding_keeps_authored_formula_and_other_fields(self):
        author = viewer()
        for raw, stored in (("-127", "OW_WILD_BEHAVIOR_RELATIVE(-8)"),
                            ("-2", "OW_WILD_BEHAVIOR_RELATIVE(-2)"),
                            ("+8", "OW_WILD_BEHAVIOR_RELATIVE(+7)"),
                            ("+127, /<6", "OW_WILD_BEHAVIOR_RELATIVE(+7)"),
                            ("-127, />3", "OW_WILD_BEHAVIOR_RELATIVE(-8)"),
                            ("/18", "8"), ("/127", "8"), ("/2", "2")):
            with self.subTest(raw=raw):
                raws = {"chainRepositionJumpCount": raw, "chillSpeed": "-2",
                        "chainHopInPlaceExtraHops": "2"}
                result = author.override_profile_storage_raws(raws)
                self.assertEqual(result["chainRepositionJumpCount"], stored)
                self.assertEqual(raws["chainRepositionJumpCount"], raw)
                self.assertEqual(result["chillSpeed"], "OW_WILD_BEHAVIOR_RELATIVE(-2)")
                self.assertEqual(result["chainHopInPlaceExtraHops"], "2")
        self.assertEqual(author.compound_bound_profile_storage_raws(
            {"chainRepositionJumpCount": "-127, />3"})["chainRepositionJumpCount"],
            "OW_WILD_BEHAVIOR_AT_MOST(3)")

    def test_all_legacy_count_formulas_use_actual_portable_reducer(self):
        author = viewer()
        source = RESOLVER.read_text()
        program = ('#define OVERWORLD_BEHAVIOR_HOST\n'
                   '#include "overworld_behavior_resolver.h"\n'
                   '#include "overworld_behavior_packed_options.h"\n'
                   '#include <stddef.h>\n#include <stdio.h>\n'
                   '#define RESOLVER_WALK_ACCELERATION_LINEAR_SPEED 34\n'
                   '#define RESOLVER_WALK_ACCELERATION_DIVIDE_BY_2 33\n')
        program += re.search(r"static const u8 sRelativeFieldMaximums\[\] = \{.*?\};",
                             source, re.S)[0] + "\n"
        signatures = (
            ("u8", "FieldOffset", "u8 fieldIndex"),
            ("u8", "ReadFieldValue", "const OverworldWildBehaviorProfileData *profile, u8 fieldIndex, u8 offset"),
            ("void", "WriteFieldValue", "OverworldWildBehaviorProfileData *profile, u8 fieldIndex, u8 offset, u8 value"),
            ("int", "RelativeFieldValue", "u8 fieldIndex, u8 value"),
            ("void", "ApplyMask", "OverworldWildBehaviorProfileData *profile, const OverworldWildBehaviorOverrideProfile *overrideProfile, u32 mask, u8 fieldIndex"),
        )
        for result, suffix, arguments in signatures:
            name = "BehaviorResolver_" + suffix
            program += f"static {result} {name}({arguments}) {{" + function_body(source, name) + "}\n"
        rows = []
        operators = [(str(value), 0, 0, 0, 0, lambda count, value=value: value)
                     for value in range(1, 9)]
        operators += [(f"{delta:+d}", 1, 0, 0, 0,
                       lambda count, delta=delta: max(1, min(8, count + delta)))
                      for delta in range(-127, 128) if delta]
        operators += [(f"/{divisor}", 0, 1, 1, 0,
                       lambda count, divisor=divisor: max(1, count // divisor))
                      for divisor in range(1, 128)]
        for bound in range(1, 9):
            operators += [(f"/<{bound}", 0, 1, 0, 0, lambda count, bound=bound: max(count, bound)),
                          (f"/>{bound}", 0, 0, 1, 0, lambda count, bound=bound: min(count, bound))]
            for delta in (-127, -8, -2, 7, 8, 127):
                operators += [(f"{delta:+d}, /<{bound}", 1, 1, 0, bound,
                               lambda count, delta=delta, bound=bound: max(max(1, min(8, count + delta)), bound)),
                              (f"{delta:+d}, />{bound}", 1, 0, 1, bound,
                               lambda count, delta=delta, bound=bound: min(max(1, min(8, count + delta)), bound))]
        for count in range(1, 9):
            for extra in range(3):
                for raw, relative, least, most, threshold, expected in operators:
                    operand = author.override_profile_storage_raws({"chainRepositionJumpCount": raw})["chainRepositionJumpCount"]
                    # Use the actual author formatter, including its packed C macro.
                    raws = {field: "0" for field in author.PROFILE_FIELDS}
                    raws["chainRepositionJumpCount"] = operand
                    initializer = author.format_profile_initializer(raws, "")
                    encoded = next(line.strip().rstrip(",") for line in initializer.splitlines()
                                   if "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_EFFECT_OPTIONS" in line)
                    rows.append(f"{{{count}, {extra}, {encoded}, {relative}, {least}, {most}, {threshold}, {expected(count)}, 0, 0}}")
                # A same-application Extra Hops replacement must coexist with formulas.
                for new_extra in range(3):
                    for raw, relative, least, most, threshold, expected in operators[8:12]:
                        operand = author.override_profile_storage_raws({"chainRepositionJumpCount": raw})["chainRepositionJumpCount"]
                        rows.append(f"{{{count}, {extra}, OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_OPTIONS({operand}, {new_extra}), {relative}, {least}, {most}, {threshold}, {expected(count)}, 1, {new_extra}}}")
        program += ('typedef struct {u8 count, extra, operand, relative, least, most, '
                    'threshold, expected, replaceExtra, newExtra;} Case;\n'
                    'static const Case cases[] = {\n' + ",\n".join(rows) + '\n};\n')
        program += r'''
int main(void) {
    for (unsigned index = 0; index < sizeof(cases)/sizeof(cases[0]); index++) {
        const Case *row = &cases[index];
        OverworldWildBehaviorProfileData profile = {0};
        OverworldWildBehaviorOverrideProfile override = {0};
        const u32 mask = OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_JUMP_COUNT;
        for (u8 heart = 0; heart < 4; heart++) {
        profile.chainRepositionJumpCount = OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_EFFECT_OPTIONS(row->count, row->extra, heart);
        override.profile.chainRepositionJumpCount = row->operand;
        override.compoundBoundProfile.chainRepositionJumpCount = row->threshold;
        override.relativeMask3 = row->relative ? mask : 0;
        override.atLeastMask3 = row->least ? mask : 0;
        override.atMostMask3 = row->most ? mask : 0;
        BehaviorResolver_ApplyMask(&profile, &override, mask, 42);
        override.mask2 = row->replaceExtra ? OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_EXTRA_HOPS : 0;
        OverworldBehaviorPackedOptions_ApplyInline(&profile, &override, 0);
        if (OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMP_COUNT(profile.chainRepositionJumpCount) != row->expected
            || OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_EXTRA_HOPS(profile.chainRepositionJumpCount)
                != (row->replaceExtra ? row->newExtra : row->extra)
            || OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_HEART_CHANCE(profile.chainRepositionJumpCount) != heart) {
            fprintf(stderr, "count row %u: before %u/%u operand %u result %u expected %u\n",
                index, row->count, row->extra, row->operand, profile.chainRepositionJumpCount, row->expected);
            return 1;
        }
        }
    }
    printf("%zu actual portable-C rows passed\n", sizeof(cases)/sizeof(cases[0]));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="packed-count-") as temporary:
            binary = Path(temporary) / "counts"
            compiled = subprocess.run(["cc", "-std=c99", "-O0", "-I", str(ROOT / "include"),
                                       "-x", "c", "-", "-o", str(binary)], input=program,
                                      text=True, capture_output=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(binary)], text=True, capture_output=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stderr)


    def test_effect_chance_options_and_packed_round_trip(self):
        author = viewer()
        _, _, macros = author.behavior_authoring_context()
        options = author.build_edit_options(macros, [])
        expected = [("OW_WILD_BEHAVIOR_HOP_EFFECT_CHANCE_" + name, value, label)
                    for name, value, label in (("OFF", 0, "Off (0%)"), ("25", 1, "25%"),
                                               ("50", 2, "50%"), ("100", 3, "100%"))]
        for key in ("chainHopInPlaceHeartChance", "chainHopInPlaceCryChance"):
            self.assertNotIn(key, author.NUMERIC_PROFILE_FIELDS)
            self.assertEqual([(row["raw"], row["value"], row["label"])
                              for row in options[key]], expected)
            self.assertFalse(author.is_relative_override_raw(key, "+1"))
            self.assertFalse(author.is_divide_override_raw(key, "/2"))
        for heart in range(4):
            for cry in range(4):
                for count in range(1, 9):
                    raws = {key: "0" for key in author.PROFILE_FIELDS}
                    raws.update(chainRepositionJumpCount=str(count),
                                chainHopInPlaceExtraHops="2",
                                chainHopInPlaceHeartChance=str(heart),
                                chainHopInPlaceCryChance=str(cry), onReachAction="1")
                    items = author.parse_initializer(author.format_profile_initializer(raws, ""))
                    decoded = author.parse_profile(items, macros)
                    for key in raws:
                        if key not in author.PROFILE_RESERVED_FIELDS:
                            self.assertEqual(decoded[key]["value"], int(raws[key]))
        # Existing two-argument source rows retain zero new effects.
        raws = {key: "0" for key in author.PROFILE_FIELDS}
        formatted = author.format_profile_initializer(raws, "").replace(
            "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_EFFECT_OPTIONS(0, 0, 0)",
            "OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_OPTIONS(0, 0)")
        decoded = author.parse_profile(author.parse_initializer(formatted), macros)
        self.assertEqual(decoded["chainHopInPlaceHeartChance"]["value"], 0)

    def test_portable_effect_slices_compose_independently(self):
        program = r'''
#define OVERWORLD_BEHAVIOR_HOST
#include "overworld_behavior_packed_options.h"
#include <assert.h>
#include <string.h>
int main(void) {
    const unsigned expectedMasks[8]={0,3,28,31,224,227,252,255};
    for(unsigned flags=0;flags<8;flags++) {
        u32 mask2=flags<<20;
        u32 knockbackMask=(((mask2>>20)&1u)*0x03)
            | ((((mask2>>19)&0x04)|((mask2>>17)&0x20))*7);
        assert(knockbackMask==expectedMasks[flags]);
        assert(knockbackMask<=255);
    }
    for (unsigned old=0; old<256; old++) for(unsigned value=0; value<256; value++)
    for(unsigned mask=0; mask<8; mask++) {
        OverworldWildBehaviorProfileData p={0}, expected={0};
        OverworldWildBehaviorOverrideProfile o={0}, before;
        p.chainRepositionJumpCount=(u8)old;p.onReachAction=(u8)old;expected=p;
        o.profile.chainRepositionJumpCount=(u8)value;o.profile.onReachAction=(u8)value;
        o.mask2=(mask&1 ? OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_HEART_CHANCE:0)
              | (mask&2 ? OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_CRY_CHANCE:0)
              | (mask&4 ? OW_WILD_BEHAVIOR_OVERRIDE2_ON_REACH_ACTION:0);
        if(mask&1)expected.chainRepositionJumpCount=(old&63)|(value&192);
        if(mask&2)expected.onReachAction=(expected.onReachAction&63)|(value&192);
        if(mask&4)expected.onReachAction=(expected.onReachAction&254)|(value&1);
        before=o;OverworldBehaviorPackedOptions_ApplyInline(&p,&o,0);
        assert(!memcmp(&p,&expected,sizeof p));assert(!memcmp(&o,&before,sizeof o));
    }
    assert(sizeof(OverworldWildBehaviorProfileData)==80);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="packed-effects-") as temporary:
            binary = Path(temporary) / "effects"
            built = subprocess.run(["cc", "-std=c99", "-O2", "-I", str(ROOT / "include"),
                                    "-x", "c", "-", "-o", str(binary)], input=program,
                                   text=True, capture_output=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stderr)


if __name__ == "__main__":
    unittest.main()

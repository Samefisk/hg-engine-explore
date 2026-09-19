#!/usr/bin/env python3

import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#include "overworld_behavior_semantic_compare.h"

#include <assert.h>
#include <string.h>

static OverworldBehaviorSemantic legacy(u8 state, u8 target)
{
    OverworldBehaviorLegacySemanticInput input;
    memset(&input, 0, sizeof(input));
    input.enabled = 1;
    input.responseState = state;
    input.targetSelector = target;
    return OverworldBehaviorSemantic_FromLegacy(&input);
}

static OverworldBehaviorSemantic conditional(
    u32 mask, u8 triggered, u8 alert, u8 target, u8 targetKind)
{
    OverworldBehaviorConditionalSemanticInput input;
    memset(&input, 0, sizeof(input));
    input.enabled = 1;
    input.activeApplicationMask = mask;
    input.conditionTriggered = triggered;
    input.alertPresentationRequested = alert;
    input.targetSelector = target;
    input.targetKind = targetKind;
    return OverworldBehaviorSemantic_FromConditional(&input);
}

int main(void)
{
    assert(legacy(OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ALERT, 0)
        == conditional(1, 1, 1, 0, 0));
    assert(legacy(OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ACTIVE,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_TOWARD)
        == conditional(1, 0, 0,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_TOWARD,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_PLAYER));
    assert(legacy(OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ACTIVE,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_AWAY)
        == conditional(1, 0, 0,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_AWAY,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_ACTOR));
    assert(legacy(OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_OWNER,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_RANDOM_NEARBY)
        == conditional(0, 0, 0,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_RANDOM_NEARBY,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_NONE));
    assert(conditional(1, 0, 0,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_TOWARD,
            OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_NONE)
        == OVERWORLD_BEHAVIOR_SEMANTIC_ORDINARY_OWNER);
    assert(OverworldBehaviorSemantic_FromLegacy(0)
        == OVERWORLD_BEHAVIOR_SEMANTIC_NO_RESPONSE);
    assert(OverworldBehaviorSemantic_FromConditional(0)
        == OVERWORLD_BEHAVIOR_SEMANTIC_NO_RESPONSE);
    return 0;
}
'''


class BehaviorSemanticCompareTests(unittest.TestCase):
    def test_representative_old_and_conditional_results_match(self):
        with tempfile.TemporaryDirectory(prefix="behavior-semantic-") as directory:
            source = Path(directory) / "semantic.c"
            binary = Path(directory) / "semantic"
            source.write_text(HARNESS)
            command = [
                *shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DOVERWORLD_BEHAVIOR_HOST",
                "-I",
                str(ROOT / "include"),
                str(source),
                str(ROOT / "lib/overworld/overworld_behavior_semantic_compare.c"),
                "-o",
                str(binary),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()

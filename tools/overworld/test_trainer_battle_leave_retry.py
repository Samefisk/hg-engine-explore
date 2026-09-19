"""Regression checks for trainer-battle overworld teardown."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"\b{name}\s*\([^;]*?\)\s*\{{",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"missing function: {name}")
    start = match.end()
    depth = 1
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index]
    raise AssertionError(f"unterminated function: {name}")


class TrainerBattleLeaveRetryTests(unittest.TestCase):
    def test_cold_shutdown_discards_pending_field_transition(self):
        source = (ROOT / "src/field/map_teleport.c").read_text()
        assembly = (ROOT / "asm/field/resident_helpers.s").read_text()
        body = function_body(source, "OverworldFieldService_PollFrameImpl")
        cold = body.split("if (fieldSystem == NULL) {", 1)[1].split(
            "\n    }", 1
        )[0]

        self.assertIn("OverworldFieldService_FinishPendingTransition(", cold)
        helper = assembly.split(
            "OverworldFieldService_FinishPendingTransition:", 1
        )[1].split(
            ".section .overworld_follower_transition_queue_append", 1
        )[0]
        self.assertRegex(helper, r"ldrb r2, \[r4, #18\]")
        self.assertRegex(helper, r"strb r2, \[r4, #16\]")
        self.assertRegex(helper, r"ldrh r3, \[r4, #14\]")
        self.assertRegex(helper, r"ldrh r2, \[r4, #12\]")
        self.assertIn("bl OverworldFieldService_OnMapHeaderChangedResident", helper)
        self.assertNotRegex(
            cold,
            r"if \(sOverworldFieldTransition\.active\)\s*\{\s*return FALSE;",
        )

    def test_stock_leave_wait_retries_custom_cleanup(self):
        assembly = (ROOT / "asm/wild_field_leave_hook.s").read_text()
        hooks = (ROOT / "hooks").read_text()
        wait = assembly.split("FieldSystem_WaitLeaveFieldHook:", 1)[1]

        self.assertIn("bl FieldSystem_LeaveFieldHook", wait)
        self.assertRegex(wait, r"ldr r0, \[r0, #0x18\]")
        self.assertRegex(wait, r"ldr r0, \[r0\]\s+ldr r0, \[r0\]")
        self.assertIn(
            "arm9 FieldSystem_WaitLeaveFieldHook 02055244 1",
            hooks,
        )


if __name__ == "__main__":
    unittest.main()

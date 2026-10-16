"""Check the stock checkpoint is changed only during one blackout task call."""

from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "src/player_health_recovery.c"


def function_body(source, name):
    match = re.search(r"\b" + name + r"\s*\([^;]*\)\s*\{", source)
    if match is None:
        raise AssertionError(name + " is missing")
    depth = 1
    for index in range(match.end(), len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[match.end():index]
    raise AssertionError(name + " body is incomplete")


class PlayerHealthRecoverySourceTest(unittest.TestCase):
    def test_stock_checkpoint_restored_before_every_wrapper_return(self):
        source = SOURCE.read_text()
        wrapper = function_body(source, "PlayerHealthRecovery_StockBlackoutTask")
        start = wrapper.index("previousSpawn = *stockSpawn;")
        substitute = wrapper.index("*stockSpawn = PlayerHealthSave_GetHealingSpawn", start)
        invoke = wrapper.index("complete = PLAYER_HEALTH_STOCK_BLACKOUT_TASK(taskman);", substitute)
        restore = wrapper.index("*stockSpawn = previousSpawn;", invoke)
        returned = wrapper.index("return complete;", restore)
        self.assertLess(start, substitute)
        self.assertLess(substitute, invoke)
        self.assertLess(invoke, restore)
        self.assertLess(restore, returned)
        self.assertEqual(wrapper.count("PLAYER_HEALTH_STOCK_BLACKOUT_TASK(taskman)"), 1)
        self.assertEqual(wrapper.count("*stockSpawn ="), 2)
        self.assertNotIn("return", wrapper[substitute:restore])
        begin = function_body(source, "PlayerHealthRecovery_BeginBlackout")
        self.assertNotIn("*stockSpawn =", begin)


if __name__ == "__main__":
    unittest.main()

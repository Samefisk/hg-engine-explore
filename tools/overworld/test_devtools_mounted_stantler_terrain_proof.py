"""Copied-data checks for the exact mounted Stantler terrain route."""

from copy import deepcopy
import unittest

from tools.overworld.devtools_mounted_stantler_terrain_proof import (
    ROUTE, negative_controls, run,
)


CONTEXT = {"mapId": 33, "fieldEpoch": 1, "mapGeneration": 1}
ACTOR = {"active": True, "role": "MOUNTED", "species": 234,
         "identityVerified": True, "presentationAttached": True,
         "inputOwnership": 1, "handle": {"slot": 7, "value": 123},
         "behaviorFingerprint": 456}
PROVENANCE = {"fieldPointer": 1, "mapMatrixPointer": 2,
              "readerPointer": 3, "store": "rolling-land-manager"}


def frame(number, x, z):
    return {"frame": number, "nativeCycle": number, "player": {"x": x, "y": z},
            "context": deepcopy(CONTEXT), "actors": [deepcopy(ACTOR)]}


def terrain_row(action, sample, radius):
    x, z = sample["player"]["x"], sample["player"]["y"]
    cells = [{"x": x + dx, "z": z + dz, "loaded": True,
              "provenance": deepcopy(PROVENANCE)}
             for dz in range(-radius, radius + 1)
             for dx in range(-radius, radius + 1)]
    return {"phase": "observe", "action": action, "command": "terrain",
            "receipt": {"terrain": {"cells": cells,
                "observation": {"boundary": "paused-native-cycle-end",
                                "lastCompletedGameFrame": sample["frame"],
                                "nativeCycle": sample["nativeCycle"],
                                "context": deepcopy(CONTEXT),
                                "center": {"x": x, "z": z}}}}}


def passing_rows():
    rows = []
    number = 1
    for index, (action, _) in enumerate(ROUTE):
        x, z = (585, 402) if index == 0 else (576, 397)
        samples = [frame(number + offset, x, z) for offset in range(120)]
        rows.append({"phase": "observe", "action": action,
                     "completedGameFrames": 120, "samples": samples})
        number += 120
    rows.append(terrain_row("route-terrain", rows[-1]["samples"][-1], 1))
    samples = [frame(number + offset, 586, 396) for offset in range(120)]
    rows.append({"phase": "observe", "action": "recovery-right",
                 "completedGameFrames": 120, "samples": samples})
    rows.append(terrain_row("recovery-terrain", samples[-1], 2))
    return rows


class MountedStantlerTerrainProofTest(unittest.TestCase):
    def test_loaded_route_and_recovery_pass_with_controls(self):
        rows = passing_rows()
        self.assertTrue(run(rows)["passed"])
        self.assertTrue(negative_controls(rows)["passed"])

    def test_old_unloaded_route_fails(self):
        rows = passing_rows()
        for cell in rows[7]["receipt"]["terrain"]["cells"]:
            cell["loaded"] = False
        result = run(rows)
        self.assertFalse(result["passed"])
        self.assertIn("terrain has an unloaded nearby cell", result["failures"][0])

    def test_stale_terrain_clock_fails(self):
        rows = passing_rows()
        rows[7]["receipt"]["terrain"]["observation"]["lastCompletedGameFrame"] -= 1
        self.assertFalse(run(rows)["passed"])


if __name__ == "__main__":
    unittest.main()

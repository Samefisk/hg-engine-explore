"""Copied native-record controls for the registered zero-HP Continue meter."""

from copy import deepcopy
import unittest

from tools.overworld.player_health_zero_load_fixture import prepare_bytes
from tools.overworld.test_player_health_zero_load_fixture import source
from tools.overworld.devtools_player_health_zero_load_complete_measurement import KIND
from tools.overworld.devtools_dispatch_counts import SCOPE as DISPATCH_SCOPE
from tools.overworld.devtools_phase_timings import SCOPE as PHASE_SCOPE
from tools.overworld.devtools_player_health_zero_load_proof import FAULTS, faulted_rows, measurements
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test

ROM = "a" * 64
OVERLAY = "b" * 64
FIELD = 0x02100000
ROOT = 0x02110000
STOCK = 0x02110100


def trace(frame, root=True, stock=True, ready=False):
    return {"frame": frame, "nativeCycle": frame + 100, "field": FIELD,
            "root": {"pointer": ROOT, "state": 2} if root else None,
            "stock": {"pointer": STOCK, "state": 4 if ready else 5} if stock else None,
            "messageInputReady": ready}


def snapshot(frame, fixture, *, root=True, stock=True, ready=False, dialogue="busy",
             free=False, moved=False):
    return {"frame": frame, "nativeCycle": frame + 100,
            "observationBoundary": "main-task-queue-completion",
            "fieldAvailable": True, "romSha256": ROM,
            "sourceSaveSha256": fixture["fixtureSha256"],
            "zeroLoadRecovery": trace(frame, root, stock, ready),
            "fieldControl": {"taskPointer": 0 if free else ROOT},
            "context": {"mapId": 158 if free else 33},
            "dialogue": {"known": True, "state": dialogue},
            "party": [{"identityVerified": True, "maxHp": 20, "hp": 20, "status": 0}],
            "player": {"x": 4, "y": 12 if moved else 13},
            "nativeObservation": {"playerStepCount": int(moved)}}


def chunk(action, samples, prior):
    return {"phase": "setup" if action not in ("normal-step", "release-step") else "observe",
            "action": action, "completedGameFrames": len(samples),
            "observedFieldFrames": len(samples), "nativeCycles": len(samples),
            "samples": samples,
            "cycleIntervals": [{"cpuNs": 1000, "wallNs": 1000,
                                "completedGameFrame": sample["frame"]} for sample in samples],
            "events": []}


def receipt(snap, fixture):
    return {"snapshot": snap, "playerHealth": {
        "schemaVersion": 1, "frame": snap["frame"], "nativeCycle": snap["nativeCycle"],
        "identity": {"descriptorVersion": 1, "overlayId": 161,
                     "overlaySha256": OVERLAY, "romSha256": ROM},
        "hp": 100, "savedHp": 100, "maxHp": 100,
        "checkpointSpawn": 3, "recoveryPending": False,
        "pause": {"fieldTaskActive": False},
        "economy": deepcopy(fixture["baselineEconomy"])}}


def rows():
    from pathlib import Path
    import json
    recipe = validate_test(json.loads(Path("tests/overworld/test-recipes/player-hp.zero-load.json").read_text()))
    _, fixture = prepare_bytes(source())
    first = snapshot(4, fixture, ready=True)
    first["bootRecovery"] = {"kind": "player-health-pending-blackout",
        "boundary": "paused-native-cycle-end", "acceptedProof": False,
        "actorClockReady": False, "recoveryInputSent": False,
        "saveSha256": fixture["fixtureSha256"], "copyBase": fixture["copyBase"],
        "saveCount": fixture["saveCount"], "hp": 0, "checkpointSpawn": 3,
        "preBootFrames": [trace(1, False, False), trace(2, True, False),
                          trace(3, True, True), trace(4, True, True, True)]}
    out = [{"phase": "setup", "initialSnapshot": first, "zeroLoadFixture": fixture}]
    out.append(chunk("dismiss-message", [snapshot(5, fixture)], first))
    out.append(chunk("release-message", [snapshot(f, fixture, dialogue="page-wait" if f == 17 else "busy")
                                         for f in range(6, 18)], None))
    out.append(chunk("dismiss-arrival", [snapshot(18, fixture)], None))
    out.append(chunk("release-arrival", [snapshot(f, fixture, root=f < 20,
                    stock=f < 20, free=f >= 20) for f in range(19, 31)], None))
    settled = out[-1]["samples"][-1]
    out.extend({"phase": "setup", "action": name, "command": "skip", "snapshot": settled}
               for name in ("dismiss-arrival-again", "release-arrival-again"))
    recovered = snapshot(30, fixture, root=False, stock=False, free=True)
    out.append({"phase": "observe", "action": "after-recovery", "command": "player-health.observe",
                "receipt": receipt(recovered, fixture), "snapshot": recovered})
    out.append(chunk("normal-step", [snapshot(f, fixture, root=False, stock=False,
                   free=True, moved=f >= 42) for f in range(31, 47)], None))
    out.append(chunk("release-step", [snapshot(f, fixture, root=False, stock=False,
                   free=True, moved=True) for f in range(47, 71)], None))
    final = snapshot(70, fixture, root=False, stock=False, free=True, moved=True)
    out.append({"phase": "observe", "action": "after-step", "command": "player-health.observe",
                "receipt": receipt(final, fixture), "snapshot": final})
    return recipe, fixture, out


def replay(recipe, fixture, records):
    evaluator = TestEvaluator(recipe)
    evaluator.install_measurements({KIND: {"contractVersion": 1, "overlaySha256": OVERLAY,
        "romSha256": ROM, "sourceSaveSha256": fixture["sourceSha256"]}})
    for row in records:
        if evaluator.observe_record(row)["state"] == "failed":
            return evaluator.result()
    return evaluator.finish()


def with_boot_native_gap(records, gap=1):
    changed = deepcopy(records)
    shifted = set()
    def shift(snap):
        if id(snap) in shifted:
            return
        shifted.add(id(snap))
        snap["nativeCycle"] += gap
        snap["zeroLoadRecovery"]["nativeCycle"] += gap
    for row in changed[1:]:
        for snap in row.get("samples", []):
            shift(snap)
        if "snapshot" in row:
            shift(row["snapshot"])
        if "receipt" in row:
            row["receipt"]["playerHealth"]["nativeCycle"] += gap
    first = changed[1]
    cycle = first["samples"][0]["nativeCycle"]
    first["cycleIntervals"][0]["guestDispatches"] = {
        "version": 1, "enabled": True, "complete": True, "frameSequence": cycle,
        "arm9": 1, "arm7": 1, "scope": DISPATCH_SCOPE}
    first["cycleIntervals"][0]["nativePhases"] = {
        "version": 2, "enabled": True, "complete": True, "invalid": False,
        "frameSequence": cycle, "scope": PHASE_SCOPE,
        "phases": {name: {"cpuNs": 0, "calls": 0}
                   for name in ("nonRender", "render3d", "render2d")}}
    return changed


class ZeroLoadCompleteTests(unittest.TestCase):
    def test_complete_trace_and_all_copied_faults(self):
        recipe, fixture, records = rows()
        result = replay(recipe, fixture, records)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["observedFrames"], 66)
        self.assertEqual(len(measurements(records, result)["measurements"]), 7)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                rejected = replay(recipe, fixture, faulted_rows(records, fault))
                self.assertFalse(rejected["passed"])
                self.assertTrue(rejected["failures"])

    def test_one_queue_free_boot_cycle_is_bounded_to_first_input(self):
        recipe, fixture, records = rows()
        bridged = with_boot_native_gap(records)
        accepted = replay(recipe, fixture, bridged)
        self.assertTrue(accepted["passed"], accepted["failures"])
        self.assertEqual(accepted["measurements"][KIND]["bootNativeGapCycles"], 1)

        two_cycles = replay(recipe, fixture, with_boot_native_gap(records, 2))
        self.assertFalse(two_cycles["passed"])
        self.assertIn("raw native cycle count differs", str(two_cycles["failures"]))

        wrong_sequence = deepcopy(bridged)
        wrong_sequence[1]["cycleIntervals"][0]["guestDispatches"]["frameSequence"] += 1
        rejected = replay(recipe, fixture, wrong_sequence)
        self.assertFalse(rejected["passed"])
        self.assertIn("boot-to-input native gap", str(rejected["failures"]))

        later_gap = deepcopy(bridged)
        later_gap[2]["samples"][0]["nativeCycle"] += 1
        later_gap[2]["samples"][0]["zeroLoadRecovery"]["nativeCycle"] += 1
        rejected = replay(recipe, fixture, later_gap)
        self.assertFalse(rejected["passed"])
        self.assertIn("raw native cycle count differs", str(rejected["failures"]))

    def test_recipe_rejects_unchecked_button_and_source_save_path(self):
        recipe, _, _ = rows()
        changed = deepcopy(recipe)
        changed["setup"][1]["args"]["keys"] = ["B"]
        with self.assertRaises(ValueError):
            validate_test(changed)
        changed = deepcopy(recipe)
        changed["fixture"]["save"] = "other.sav"
        with self.assertRaises(ValueError):
            validate_test(changed)


if __name__ == "__main__":
    unittest.main()

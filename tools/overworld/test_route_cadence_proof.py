"""Full-route controller controls; reuse the real raw cadence meter."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.test_devtools_cadence_measurement import Route
from tools.overworld.route_cadence_proof import (
    cadence_measurements, check_crash_proof, game_cadence_measurements, RULES,
)
from tools.overworld.runtime_cadence import classify_frame_hitches

ROOT = Path(__file__).resolve().parents[2]


class RouteCadenceProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        route = Route(); route.setup_bind()
        for tile in range(1,161): route.move(tile)
        meter = UnmountedCadenceMeasurement(route.test, max_frames=32000)
        for row in route.records: meter.observe_record(row, full_report=False)
        cls.report = meter.finish()
        assert cls.report["passed"] is True

    def test_real_full_host_stream_exact_registry_and_no_mutation(self):
        before = deepcopy(self.report)
        rows = cadence_measurements(self.report)
        self.assertEqual(len(rows), 10)
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        contract = registry["measurementContracts"]["legacy.unmounted-long-travel"]
        self.assertEqual(RULES, tuple((claim, row["name"], row["operator"], row.get("minimum",row.get("expected")))
            for claim, entries in contract.items() for row in entries))
        self.assertEqual(rows[1]["value"], 5120)
        self.assertEqual(rows[7]["value"], 20)
        self.assertEqual(self.report, before)

    def test_current_game_rows_keep_host_hitch_as_diagnostic_only(self):
        value = deepcopy(self.report)
        value["cpuSamples"][0] = 1_000_000_000
        value["cpu"] = classify_frame_hitches(value["cpuSamples"], 2000, 250000)
        self.assertGreater(value["cpu"]["hitchCount"], 0)
        rows = game_cadence_measurements(value)
        self.assertEqual(len(rows), 9)
        self.assertNotIn("host-cpu-pacing", {row["claim"] for row in rows})
        value["cpu"] = self.report["cpu"]
        with self.assertRaises(ValueError):
            game_cadence_measurements(value)

    def test_retained_transition_crash_prefix_when_available(self):
        directory = ROOT / "build/overworld-devtools/test-efb988d6d31c48e6997a8b8f4ee7c749"
        path = directory / "observations.jsonl"
        if not path.is_file():
            self.skipTest("optional immutable transition memory data is absent")
        from tools.overworld.control import _replay_shared_test
        recipe = json.loads((ROOT / "tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json").read_text())
        with path.open() as stream:
            result = _replay_shared_test(recipe, (json.loads(line) for line in stream))
        meter = result["measurements"]["unmounted-cadence-v1"]
        self.assertEqual([f["code"] for f in meter["failures"]], ["long-route-measurement-incomplete"])
        self.assertFalse(result["passed"])
        proof = meter["crashPresentations"][-1]
        self.assertEqual(proof["termination"], "transition-restored")
        self.assertEqual(proof["restoredFrame"], 847)
        self.assertEqual(len(proof["samples"]), 6)

    def test_each_original_floor_and_terminal_gap_rejects(self):
        mutations = {
            "active": lambda m: m.__setitem__("activeMovementFrames", 4999),
            "tiles": lambda m: m.__setitem__("routeTiles", m["routeTiles"][:79]),
            "cells": lambda m: m.__setitem__("routeCells", m["routeCells"][:2]),
            "maps": lambda m: m.__setitem__("maps", [33]),
            "followers": lambda m: m.__setitem__("followerMotions", 15),
            "held": lambda m: m.__setitem__("heldMultiTileSegments", 0),
            "held-cell": lambda m: m.__setitem__("heldCellCrossings", 0),
            "held-map": lambda m: m.__setitem__("heldMapCrossings", 0),
            "changed-limit": lambda m: m["limits"].__setitem__("inputFrames", 3),
            "hitch": lambda m: m["cpuSamples"].__setitem__(0, 1000000000),
            "missing-cpu": lambda m: m["cpuSamples"].pop(),
            "missing-export": lambda m: m.pop("terminalState"),
            "pending-player": lambda m: m["terminalState"].__setitem__("playerInFlight", True),
            "pending-collision": lambda m: m["terminalState"].__setitem__("playerCollisionWaitPending", True),
            "pending-follower": lambda m: m["terminalState"].__setitem__("followerInFlight", True),
            "pending-crash": lambda m: m["terminalState"].__setitem__("crashPresentationPending", True),
            "pending-transition": lambda m: m["terminalState"].__setitem__("setupTransitionPending", True),
            "mounted": lambda m: m["subject"].__setitem__("role", "MOUNTED"),
            "missing-current": lambda m: m["settledSnapshot"].__setitem__("actors", []),
            "missing-hp": lambda m: m["settledSnapshot"]["partyObservation"].__setitem__("nativeGetterChecks", []),
            "active-crash": lambda m: m["settledSnapshot"]["actors"][0]["crashPresentation"].__setitem__("timer", 1),
            "frame-gap": lambda m: m.__setitem__("observedFrames", m["observedFrames"]+1),
            "no-rebind": lambda m: m.__setitem__("handoffs", []),
            "bad-rebind": lambda m: m["handoffs"][0]["rebound"].__setitem__("event", "WORLD_EFFECT"),
            "missing-return": lambda m: m["lastFollowerTerminal"]["events"].__setitem__("control", []),
            "failure": lambda m: m["failures"].append({"code":"real-player-error"}),
            "gap": lambda m: m["evidenceGaps"].append("missing-frame"),
        }
        for name, change in mutations.items():
            with self.subTest(name=name):
                value = deepcopy(self.report); change(value)
                with self.assertRaises(ValueError): cadence_measurements(value)

    def test_retained_full_839_stream_when_available(self):
        directory = ROOT / "build/overworld-devtools/test-839dec8cf9b348a98d8f2acf1b55afb7"
        if not (directory / "observations.jsonl").is_file():
            self.skipTest("optional immutable full-route memory data is absent")
        from tools.overworld.control import _replay_shared_test
        from tools.overworld.devtools_test_contract import validate_test
        recipe = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json").read_text()))
        with (directory / "observations.jsonl").open() as stream:
            replay = _replay_shared_test(recipe, (json.loads(line) for line in stream))
        self.assertTrue(replay["passed"], replay.get("failures"))
        measurement = replay["measurements"]["unmounted-cadence-v1"]
        rows = cadence_measurements(measurement)
        self.assertEqual(rows[1]["value"], 5428)
        self.assertEqual(rows[4]["value"], 85)
        for key in ("recoveryTerminal",):
            bad = deepcopy(measurement); del bad["handoffs"][0][key]
            with self.assertRaises(ValueError): cadence_measurements(bad)
        bad = deepcopy(measurement)
        bad["crashPresentations"][0]["restoredFrame"] = None
        with self.assertRaises(ValueError): cadence_measurements(bad)
        bad = deepcopy(measurement)
        bad["handoffs"][0]["canceledMotion"]["terminal"]["actor"]["commitSequence"] += 1
        with self.assertRaises(ValueError): cadence_measurements(bad)


class CrashTransitionProofTests(unittest.TestCase):
    def test_controller_replays_a_validated_timer_eleven_preroll(self):
        from tools.overworld.devtools_crash_measurement import CrashPresentationMeasurement
        from tools.overworld.test_devtools_crash_measurement import fixture
        initial, old, rows = fixture()
        old.update(motionPhase="IDLE", motionKind="NONE", motionElapsed=2,
                   commitSequence=17, logical=deepcopy(old["target"]),
                   inputOwnership=0, reservationId=0)
        old["engineObject"].update(x=582, pos_x=38174720, pos_z=26050560)
        preroll = deepcopy(rows[0][1])
        preroll.update(motionPhase="IDLE", motionKind="NONE", motionElapsed=2,
                       commitSequence=17, logical=deepcopy(old["target"]),
                       inputOwnership=0, reservationId=0)
        preroll["engineObject"].update(x=582, pos_x=38174720, pos_z=26050560)
        preroll["crashPresentation"].update(timer=11, baseX=38174720, baseZ=26050560)
        shifted = []
        for snapshot, actor in rows:
            snapshot = deepcopy(snapshot); actor = deepcopy(actor)
            snapshot["frame"] += 1; snapshot["nativeCycle"] += 2
            actor["crashPresentation"]["frame"] += 1
            actor["crashPresentation"]["nativeCycle"] += 2
            shifted.append((snapshot, actor))
        meter = CrashPresentationMeasurement()
        meter.observe(initial, old, None)
        meter.observe(rows[0][0], preroll, old)
        previous = preroll
        for snapshot, actor in shifted:
            meter.observe(snapshot, actor, previous)
            previous = actor
        proof = meter.proofs[0]
        check_crash_proof(proof, [])
        del proof["preRollPreviousActor"]
        with self.assertRaises(ValueError):
            check_crash_proof(proof, [])

    def test_controller_replays_transition_and_rejects_missing_or_changed_evidence(self):
        from tools.overworld.test_devtools_crash_measurement import CrashMeasurementTests
        meter, old, snapshot, actor, transition = CrashMeasurementTests().transition_fixture()
        meter.observe(snapshot, actor, old, transition=transition)
        proof = meter.proofs[0]
        handoffs = [deepcopy(transition)]
        check_crash_proof(proof, handoffs)
        with self.assertRaises(ValueError):
            check_crash_proof(proof, [])
        for fault in ("pose", "termination", "receipt", "removed-restoration"):
            with self.subTest(fault=fault):
                bad = deepcopy(proof)
                if fault == "pose":
                    bad["transitionRestoration"]["actor"]["engineObject"]["pos_x"] += 1
                elif fault == "termination":
                    bad["termination"] = "countdown-restored"
                elif fault == "receipt":
                    bad["transitionRestoration"]["transition"]["rebound"]["sequence"] += 1
                else:
                    del bad["transitionRestoration"]
                with self.assertRaises(ValueError):
                    check_crash_proof(bad, handoffs)


if __name__ == "__main__": unittest.main()

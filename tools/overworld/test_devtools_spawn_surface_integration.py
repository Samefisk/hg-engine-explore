"""Shared per-frame stream controls for the separate spawn surface claim."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_spawn_measurement import PoolSpawnSurfaceMeasurement
from tools.overworld.test_devtools_spawn_measurement import landing_stream, AUTHORED, SOURCE, SCHEMA
from tools.overworld.test_devtools_spawn_surface_measurement import surface_fixture


def surface_stream():
    stream = landing_stream()
    h = surface_fixture()[0]["jumpReceipts"][0]["landingHeight"]
    h.update(observation="spawn-landing-height", sequence=2, setupMode="normal")
    for snapshot, events in stream.items:
        for actor in snapshot["actors"]:
            actor["engineIdentity"]["id_lookup"] = {"eligible_count": 1, "pointer_matches": True}
        if snapshot["frame"] < 2:
            continue
        snapshot["nativeObservation"]["sequence"] += 1
        for event in events:
            if event["kind"] != "native-observation":
                continue
            data = event["data"]
            if data["sequence"] >= 2:
                data["sequence"] += 1
            if data.get("observation") == "spawn-prepared":
                data["jumpReceipts"][0]["landingHeight"] = deepcopy(h)
        if snapshot["frame"] == 2:
            events.insert(1, {"kind": "native-observation", "frame": 2, "data": deepcopy(h)})
    return stream


class PoolSpawnSurfaceIntegrationTests(unittest.TestCase):
    def meter(self):
        return PoolSpawnSurfaceMeasurement(SCHEMA, SOURCE, authored_profiles=AUTHORED, max_frames=100)

    def run_stream(self, stream):
        meter = self.meter()
        for snapshot, events in stream.items:
            result = meter.observe(snapshot, events)
            if result["failures"] or result["ready"]:
                break
        return meter, result

    def test_surface_waits_for_original_complete_spawn(self):
        meter = self.meter()
        stream = surface_stream()
        before = deepcopy(stream.items)
        for snapshot, events in stream.items[:-1]:
            result = meter.observe(snapshot, events)
            self.assertFalse(result["ready"])
            self.assertIsNone(result["surface"])
        result = meter.observe(*stream.items[-1])
        self.assertTrue(result["ready"], result)
        self.assertTrue(result["spawnPassed"])
        self.assertTrue(meter.finish()["passed"])
        self.assertEqual(stream.items, before)

    def test_legacy_missing_receipt_is_not_accepted(self):
        meter, result = self.run_stream(landing_stream())
        self.assertFalse(result["ready"])
        self.assertTrue(result["surfaceErrors"])
        self.assertEqual(result["state"], "failed")
        self.assertFalse(meter.finish()["passed"])

    def test_same_frame_exact_queued_receipt_is_required(self):
        for fault in ("missing", "changed", "duplicate", "wrong-frame", "meaning-deleted"):
            stream = surface_stream()
            events = stream.items[1][1]
            height = next(e for e in events if e["data"].get("observation") == "spawn-landing-height")
            if fault == "missing": events.remove(height)
            elif fault == "changed": height["data"]["target"][0] += 1
            elif fault == "duplicate": events.append(deepcopy(height))
            elif fault == "wrong-frame": height["frame"] += 1
            elif fault == "meaning-deleted": height["data"]["observation"] = "unrelated-native-event"
            with self.subTest(fault=fault):
                meter, result = self.run_stream(stream)
                self.assertTrue(result["failures"], result)
                if fault in ("changed", "meaning-deleted"):
                    self.assertEqual(result["surfaceErrors"][0]["code"], "missing-spawn-height-event")
                self.assertFalse(meter.finish()["passed"])

    def test_same_frame_successor_keeps_exact_landing_credit(self):
        stream = surface_stream()
        snapshot, events = stream.items[-1]
        actor = snapshot["actors"][0]
        actor.update(origin=deepcopy(actor["logical"]), target={"x": 17, "y": 0},
                     motionKind="WALK", motionPhase="MOVING", motionElapsed=0,
                     motionDuration=8, reservationId=2)
        started = deepcopy(events[-1])
        started["data"].update(event="MOTION_STARTED", valueA=1, valueB=8,
                               sequence=started["data"]["sequence"] + 1)
        events.append(started)
        meter, result = self.run_stream(stream)
        self.assertTrue(result["ready"], result)
        self.assertEqual(result["stopBoundary"]["kind"], "terminal-with-unmeasured-successor")
        self.assertEqual(result["completeMotions"], 1)
        self.assertTrue(meter.finish()["passed"])

    def test_forbidden_or_unknown_native_height_fails_after_full_spawn(self):
        for fault in ("collision", "refresh", "unknown"):
            stream = surface_stream()
            for event in stream.items[1][1]:
                data = event["data"]
                if data.get("observation") == "spawn-landing-height": h = data
                elif data.get("observation") == "spawn-prepared": h = data["jumpReceipts"][0]["landingHeight"]
                else: continue
                if fault == "refresh": h["heightRefresh"]["returnValue"] = 0
                elif fault == "unknown": h["loadedTerrain"]["status"] = "unknown"
                else:
                    for name in ("loadedTerrainBefore", "loadedTerrain"):
                        cell = h[name]["cell"]
                        cell.update(attribute=0x8002, collision=True)
                        cell["provenance"]["rawWord"] = 0x8002
            with self.subTest(fault=fault):
                meter, result = self.run_stream(stream)
                self.assertTrue(result["spawnPassed"], result)
                self.assertTrue(result["surfaceErrors"], result)
                self.assertFalse(meter.finish()["passed"])

    def test_surface_cannot_replace_missing_motion_proof(self):
        stream = surface_stream()
        stream.items.pop()
        meter, result = self.run_stream(stream)
        self.assertFalse(result["ready"])
        self.assertIsNone(result["surface"])
        self.assertFalse(meter.finish()["passed"])

    def test_surface_success_does_not_stop_later_base_observation(self):
        for fault in ("identity", "gap", "none"):
            with self.subTest(fault=fault):
                stream = surface_stream()
                meter, result = self.run_stream(stream)
                self.assertTrue(result["ready"])
                surface = deepcopy(result["surface"])
                later = deepcopy(stream.items[-1][0])
                later["frame"] += 1
                later["actorFrame"] += 1
                later["nativeCycle"] += 2
                if fault == "identity": later["actors"][0]["subjectIdentity"] += 1
                elif fault == "gap": later["frame"] += 1; later["actorFrame"] += 1
                result = meter.observe(later, [])
                self.assertEqual(result["surface"], surface)
                if fault == "none": self.assertTrue(result["ready"], result)
                else:
                    self.assertTrue(result["failures"], result)
                    self.assertFalse(meter.finish()["passed"])

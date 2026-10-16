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


class PoolFlySurfaceIntegrationTests(unittest.TestCase):
    def run_fly(self, stream):
        from tools.overworld.test_devtools_spawn_measurement import fly_authored
        meter = PoolSpawnSurfaceMeasurement(SCHEMA, SOURCE, authored_profiles=fly_authored(), max_frames=200)
        for snapshot, events in stream.items:
            result = meter.observe(snapshot, events)
            if result["failures"] or result["ready"]:
                break
        return meter, result

    def test_current_canonical_bank_and_complete_normal_fly_height(self):
        from tools.overworld.test_devtools_spawn_measurement import fly_stream
        for elapsed in (0, 1):
            stream = fly_stream(first_elapsed=elapsed)
            before = deepcopy(stream.items)
            meter, result = self.run_fly(stream)
            self.assertTrue(meter.finish()["passed"], result)
            self.assertEqual(result["placement"]["startupKind"], 9)
            self.assertEqual(result["surface"]["nativeLandingY"], 65536)
            self.assertFalse(result["surface"]["nativeHeightRefreshRequired"])
            self.assertEqual(stream.items, before)

    def test_current_fly_cannot_replace_normal_source_surface_or_terminal_proof(self):
        from tools.overworld.test_devtools_spawn_measurement import fly_stream
        for fault in ("prepared", "missing-cell", "surface", "water", "collision", "base", "offset", "duration", "gap", "foreign", "missing-finish", "missing-control", "wrong-source"):
            stream = fly_stream()
            for snapshot, events in stream.items:
                if fault == "prepared":
                    snapshot["prepared"] = True
                    for event in events:
                        if event["kind"] == "native-observation": event["data"]["setupMode"] = "prepared"
                if "terrain" in snapshot:
                    cell = snapshot["terrain"]["cells"][0]
                    if fault == "missing-cell": snapshot["terrain"]["cells"] = []
                    if fault == "surface": cell["surface"]["present"] = True
                    if fault == "water": cell.update(attribute=16, behavior=16);cell["provenance"]["rawWord"] = 16
                    if fault == "collision": cell.update(attribute=0x8002, collision=True);cell["provenance"]["rawWord"] = 0x8002
                for actor in snapshot["actors"]:
                    if fault == "duration": actor["motionDuration"] = 143
                    if fault == "foreign" and snapshot["frame"] > 20: actor["handle"]["generation"] += 1
                    if actor["motionPhase"] == "IDLE":
                        if fault == "base": actor["engineObject"]["pos_y"] += 1
                        if fault == "offset": actor["engineObject"]["unk88_y"] = 1
                for event in events:
                    data = event["data"]
                    if fault == "missing-finish" and data.get("event") == "MOTION_FINISHED": data["event"] = "WORLD_EFFECT"
                    if fault == "missing-control" and data.get("event") == "CONTROL_RETURNED": data["event"] = "WORLD_EFFECT"
                    if fault == "wrong-source" and data.get("observation") == "spawn-prepared":
                        data["finalization"]["receipt"]["resolverReceipts"][0]["sourceSha256"] = "b" * 64
            if fault == "gap": stream.items.pop(20)
            with self.subTest(fault=fault):
                meter, result = self.run_fly(stream)
                self.assertFalse(meter.finish()["passed"], result)

    @staticmethod
    def collect_fly(stream, *, fault=None):
        """Run the real hook-free collector; substitute only native memory reads."""
        from types import SimpleNamespace
        from tools.overworld.devtools_observer import NativeObservation
        observer = NativeObservation.__new__(NativeObservation)
        observer.pool_fly_terrain = {}
        spawn = next(e['data'] for _, es in stream.items for e in es
                     if e.get('data', {}).get('observation') == 'spawn-prepared')
        world = deepcopy(spawn['worldContext'])
        cell = deepcopy(stream.items[1][0]['terrain']['cells'][0])
        calls = []
        def terrain(emu, x, y):
            calls.append(('terrain', x, y))
            return None if fault == 'unloaded' else deepcopy(cell)
        def surface(emu, x, y, value):
            calls.append(('surface', x, y))
            return deepcopy(cell['surface'])
        observer.session = SimpleNamespace(emu=object(), rt=SimpleNamespace(
            loaded_terrain_cell=terrain, loaded_surface_cell=surface))
        observer._world_context = lambda: deepcopy(world)
        for sample, events in stream.items:
            observer.ready = events
            observer._pool_fly_terrain_snapshot(sample)
            sample.pop('terrain', None)  # normal sampler has no terrain radius
        return observer, calls, spawn

    def test_hook_free_collector_reads_only_admission_and_logical_terminal(self):
        from tools.overworld.test_devtools_spawn_measurement import fly_stream
        stream = fly_stream()
        observer, calls, _ = self.collect_fly(stream)
        self.assertEqual(calls, [('terrain', 16, 0), ('surface', 16, 0)] * 2)
        rows = [(s['frame'], s['poolFlyTerrain'][0]['stage']) for s, _ in stream.items
                if 'poolFlyTerrain' in s]
        self.assertEqual(rows, [(stream.items[1][0]['frame'], 'admission'),
                                (stream.items[-1][0]['frame'], 'terminal')])
        self.assertEqual(observer.pool_fly_terrain, {})
        meter, result = self.run_fly(stream)
        self.assertTrue(meter.finish()['passed'], result)
        # Render can finish one queue before logical commit. Do not spend the
        # terminal read early or discard the saved full identity then.
        stream = fly_stream()
        old = deepcopy(stream.items[-1][0]); old['actors'][0]['logical'] = {'x': 0, 'y': 0}
        stream.items.insert(-1, (old, []))
        stream.items[-1][0]['frame'] += 1
        observer, calls, _ = self.collect_fly(stream)
        self.assertEqual(calls, [('terrain', 16, 0), ('surface', 16, 0)] * 2)
        self.assertNotIn('poolFlyTerrain', stream.items[-2][0])
        self.assertEqual(stream.items[-1][0]['poolFlyTerrain'][0]['stage'], 'terminal')

    def test_collector_and_checker_reject_foreign_unknown_or_reused_cell(self):
        from tools.overworld.test_devtools_spawn_measurement import fly_stream
        from tools.overworld.devtools_observer import NativeObservationError
        for fault in ('source', 'field', 'duration', 'duplicate', 'unloaded', 'stage'):
            stream = fly_stream()
            if fault == 'source': stream.items[1][0]['actors'][0]['sourceIdentity']['object'] += 4
            if fault == 'field': stream.items[1][0]['context']['fieldEpoch'] += 1
            if fault == 'duration': stream.items[1][0]['actors'][0]['motionDuration'] = 143
            if fault == 'duplicate':
                data = next(e for e in stream.items[1][1]
                            if e.get('data', {}).get('observation') == 'spawn-prepared')
                stream.items[1][1].append(deepcopy(data))
            with self.subTest(fault=fault):
                if fault in ('source', 'duration', 'duplicate'):
                    with self.assertRaises(NativeObservationError): self.collect_fly(stream)
                else:
                    _, calls, _ = self.collect_fly(stream, fault=fault)
                    if fault == 'field': self.assertEqual(calls, [])
                    if fault == 'unloaded': self.assertEqual(calls, [('terrain', 16, 0)] * 2)
                    if fault == 'stage': stream.items[-1][0]['poolFlyTerrain'][0]['stage'] = 'admission'
                    meter, result = self.run_fly(stream)
                    self.assertFalse(meter.finish()['passed'], result)

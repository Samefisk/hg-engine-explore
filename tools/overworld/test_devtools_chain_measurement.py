"""Synthetic shared receipt replay controls; no emulator or ROM proof."""
from copy import deepcopy
import json
import re
from pathlib import Path
import struct
import tempfile
import unittest

from tools.overworld.devtools_chain_measurement import LedybaChainMeasurement


SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "tools/overworld/behavior_schema.json").read_text())
SOURCE = "a" * 64


class Stream:
    """Explicit authored 8–14 moves, four flat 8-frame/two-tile skids.

    The fixture supplies observed positions and ABI packets, not the game
    reducer, private remaining count, or production variance generator.
    """
    def __init__(self, *, initial_commit=0):
        self.frame = self.sequence = self.trace_sequence = 0
        self.items = []
        self.lane = bytearray(72)
        values = {"ramAccelerationSteps": 8, "chainMovementVariance": 6, "chainPauseAction": 5,
                  "chainPauseActionChance": 60, "chainRepositionJumpCount": 4, "chainRepositionSpeed": 8,
                  "chainRepositionDistance": 2, "chainRepositionAllowCardinal": 0,
                  "chainRepositionAllowDiagonal": 1, "walkPause": 0, "hopPause": 2,
                  "ramMaxSpeed": 0, "chainPauseVariance": 0, "walkOptions": 96}
        fields = {item["key"]: item for item in SCHEMA["fields"]}
        for key, value in values.items():
            self.lane[fields[key]["offset"]] = value
        active_lane = bytearray(self.lane); active_lane[0] = 19
        self.lanes = [bytes(self.lane).hex(), bytes(active_lane).hex(), bytes(active_lane).hex()]
        resolved = bytearray(256)
        for index, lane in enumerate(self.lanes): resolved[index * 72:(index + 1) * 72] = bytes.fromhex(lane)
        resolved[248:252] = (3).to_bytes(4, "little")
        resolved[252:256] = (12345).to_bytes(4, "little")
        request = bytearray(20); request[:2] = (165).to_bytes(2, "little"); request[8] = 5
        self.profile = {"resolved": True, "requestHex": request.hex(), "resultHex": resolved.hex(),
                        "fingerprint": 12345, "sourceSha256": SOURCE, "lanes": self.lanes, "appliedOverrides": 3}
        self.actor = {"active": True, "species": 165, "form": 0, "level": 5, "role": "WILD",
            "subjectIdentity": 55, "behaviorFingerprint": 12345, "matchedLayerMask": 3,
            "handle": {"value": 65536, "slot": 0, "generation": 1, "fieldEpoch": 2,
                       "mapGeneration": 4, "encounterGeneration": 1},
            "presentationAttached": True, "authorityGeneration": 1, "engineAnchorGeneration": 1,
            "presentationGeneration": 1, "identityVerified": True,
            "sourceIdentity": {"object": 0x02010000, "active": 1, "species": 165, "form": 0, "level": 5, "personality": 55,
                               "object_id": 224, "map_id": 34, "encounter_generation": 1},
            "engineIdentity": {"pointer": 0x02010000, "in_manager": True, "active": True,
                "object_manager": 0x02020000, "current_manager": 0x02020000, "object_id": 224,
                "spawn_object_id": 224, "object_map_id": 34, "spawn_map_id": 34,
                "current_map_id": 34, "encounter_generation": 1, "script_id": 2074},
            "origin": {"x": 0, "y": 0}, "target": {"x": 0, "y": 0}, "logical": {"x": 0, "y": 0},
            "render": {"x": 0, "y": 0},
            "motionKind": "NONE", "motionPhase": "IDLE", "motionElapsed": 0, "motionDuration": 0,
            "reservationId": 0, "commitSequence": initial_commit, "inputOwnership": 0,
            "engineObject": {"pos_x": 0x8000, "pos_y": 0, "pos_z": 0x8000,
                             "x": 0, "y": 0, "facing": 2, "flags": 1, "unk88_y": 0}}
        self.append([], actors=False)

    def public(self, **changed):
        return {"status": "observed-public-subject", "slot": 0,
                **{key: deepcopy(self.actor[key]) for key in ("handle", "species", "form", "level", "role",
                   "subjectIdentity", "behaviorFingerprint", "matchedLayerMask", "commitSequence", "motionPhase",
                   "motionKind", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")}, **changed}

    def native(self, observation, **data):
        self.sequence += 1
        return {"frame": self.frame + 1, "kind": "native-observation", "data": {
            "observation": observation, "sequence": self.sequence, "setupMode": "normal", "returnValue": 1,
            "entryActorFrame": self.frame, "returnActorFrame": self.frame,
            "entryNativeCycle": self.frame * 2, "returnNativeCycle": self.frame * 2, **data}}

    def trace(self, event, a, b):
        self.trace_sequence += 1
        return {"frame": self.frame + 1, "kind": "native", "data": {"traceStream": 1,
            "sequence": self.trace_sequence, "event": event, "actorHandle": self.actor["handle"]["value"],
            "actor": {key: value for key, value in self.actor["handle"].items() if key != "value"},
            "reason": "OK", "valueA": a, "valueB": b}}

    def policy(self, operation, *, counter=None, roll=None, selected=False, skid=False, lane_index=0,
               reset=False, lane_state=0):
        request = bytearray(28); request[:4] = b"\x01\x00\x1c\x00"
        request[9] = operation; request[12] = 1; request[13] = lane_state; request[14] = 0x0C
        response = bytearray(request)
        response[20] = (2 if skid else 0) | (8 if reset else 0)
        response[22] = 5 if selected else 0; response[23] = 8 if selected else 0
        subject = self.public(**({"commitSequence": counter} if counter is not None else {}))
        return self.native("walk-policy", slot=0, operation=operation, requestHex=request.hex(), responseHex=response.hex(),
            publicSubject=subject, publicSubjectAfter=deepcopy(subject), laneHex=self.lanes[lane_index],
            rngReturns=[] if roll is None else [{"value": roll, "actorFrame": self.frame, "nativeCycle": self.frame * 2}])

    def append(self, events=(), *, actors=True):
        self.frame += 1
        self.items.append(({"frame": self.frame, "nativeCycle": self.frame * 2, "actorFrame": self.frame,
            "observationBoundary": "main-task-queue-completion",
            "prepared": False, "context": {"mapId": 34, "fieldEpoch": 2, "mapGeneration": 4},
            "player": {"x": -100, "y": 0},
            "actors": [deepcopy(self.actor)] if actors else [],
            "nativeObservation": {"installedBeforeBoot": True, "coverageComplete": True,
                "eventsDropped": 0, "profilesEvicted": 0, "error": None, "sequence": self.sequence, "pendingUnframedEvents": 0,
                "resolvedProfiles": [deepcopy(self.profile)]}}, deepcopy(list(events))))

    def motion(self, kind, delta, *, pause=0, spawn=False, roll=None, selected=False, skid=False, lane_index=0):
        ids = {"WALK": 1, "HOP": 2, "REPOSITION": 5}
        origin = list(self.actor["logical"].values()); target = [origin[i] + delta[i] for i in range(2)]
        before = self.actor["commitSequence"]
        self.actor.update(motionKind=kind, motionPhase="MOVING", motionDuration=8, reservationId=1,
                          origin=dict(zip(("x", "y"), origin)), target=dict(zip(("x", "y"), target)))
        for elapsed in range(8):
            self.actor["motionElapsed"] = elapsed
            engine = self.actor["engineObject"]
            engine.update(pos_x=(origin[0] << 16) + 0x8000 + delta[0] * 0x10000 * elapsed // 8,
                          pos_z=(origin[1] << 16) + 0x8000 + delta[1] * 0x10000 * elapsed // 8,
                          unk88_y=-4000 if kind == "HOP" and elapsed else 0)
            self.actor["render"] = {"x": engine["pos_x"] >> 16, "y": engine["pos_z"] >> 16}
            events = [self.trace("MOTION_STARTED", ids[kind], 8)] if elapsed == 0 else []
            if spawn and elapsed == 0:
                startup = {"origin": origin, "target": target, "locomotion": 4,
                           "hopDirection": 3}
                encounter = {"personality": self.actor["subjectIdentity"], "species": 165,
                             "form": 0, "level": 5}
                prefix = struct.pack("<iiB3xIHBB4hBB", *target, 0,
                    encounter["personality"], 165, 0, 5, *target, *origin, 4, 3)
                jump = {"returnValue": 1, "slot": 0, "sourceIdentity": deepcopy(self.actor["sourceIdentity"]),
                        "publicSubject": self.public(), "origin": origin, "target": target,
                        "playerAtEntry": {"pointer": 0x02210000, "mapId": 34, "tile": target}}
                events += [self.native("spawn-object-create", slot=0,
                            arguments=[self.actor["engineIdentity"]["current_manager"], *origin, 1],
                            returnValue=self.actor["sourceIdentity"]["object"]),
                           self.native("spawn-motion", **jump), self.native("spawn-prepared", slot=0, terrain=0,
                            publicSubject=self.public(), jumpReceipts=[jump],
                            resolverReceipts=[{**deepcopy(self.profile), "slot": 0,
                                "sourceIdentity": deepcopy(self.actor["sourceIdentity"])}], preparedPointer=0x02240000,
                            preparedPrefixHex=prefix.hex(), preparedEncounter=encounter, startup=startup)]
            self.append(events)
        self.actor.update(motionElapsed=8, commitSequence=(before + 1) & 0xFFFFFFFF, reservationId=0,
                          logical=deepcopy(self.actor["target"]), render=deepcopy(self.actor["target"]),
                          motionPhase="SETTLING" if pause else "IDLE")
        self.actor["engineObject"].update(pos_x=(target[0] << 16) + 0x8000, pos_z=(target[1] << 16) + 0x8000,
                                          x=target[0], y=target[1], unk88_y=0)
        if not pause: self.actor["motionKind"] = "NONE"
        events = [self.trace("LOGICAL_COMMIT", self.actor["commitSequence"], ids[kind])]
        if not spawn and kind == "WALK":
            events += [self.policy(3, counter=before, skid=skid)]
        if not spawn and kind == "WALK" and not skid:
            events += [self.policy(4, roll=roll, selected=selected, lane_index=lane_index)]
        if not pause:
            events += [self.trace("MOTION_FINISHED", self.actor["commitSequence"], ids[kind]),
                       self.trace("CONTROL_RETURNED", 0, self.actor["commitSequence"])]
        self.append(events)
        for index in range(1, pause + 1):
            events = []
            if index == pause:
                self.actor.update(motionPhase="IDLE", motionKind="NONE")
                events = [self.trace("MOTION_FINISHED", self.actor["commitSequence"], ids[kind]),
                          self.trace("CONTROL_RETURNED", 0, self.actor["commitSequence"])]
            self.append(events)

    def complete(self):
        self.motion("HOP", (16, 0), pause=2, spawn=True)
        for count in (8, 14, 10):
            for index in range(count):
                self.motion("WALK", (1, 0), roll=20 if index == count - 1 else None,
                            selected=index == count - 1, lane_index=1)
            for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)):
                self.motion("REPOSITION", delta)
        return self

    def abort_reposition(self, *, completed_legs=2, finish=True):
        origin = list(self.actor["logical"].values())
        encoded = 0x20 if completed_legs == 0 else 0xA0 | (5 - completed_legs)
        targets = [[origin[0] + dx, origin[1] + dz] for dx, dz in ((2, 2), (-2, 2), (-2, -2), (2, -2))]
        result = bytes((encoded, 0, 3, 12))
        attempt = self.native("chain-reposition-attempt", observationVersion=2, attemptId=self.sequence + 1,
            slot=0, publicSubject=self.public(), publicSubjectAfter=self.public(),
            sourceIdentity=deepcopy(self.actor["sourceIdentity"]), engineIdentity=deepcopy(self.actor["engineIdentity"]),
            worldContext={"mapId": 34, "fieldEpoch": 2, "mapGeneration": 4, "fieldPointer": 0x02050000},
            encodedRemaining=encoded, nativeOrigin=origin, resultHex=result.hex(),
            nativeResult={"encodedRemaining": encoded, "gridDelta": 0, "outcome": 3, "outcomeName": "ABORT",
                "reason": 12, "reasonName": "NO_CANDIDATE"},
            nativeControlAfter={"inputOwnership": 0, "reservationId": 0, "motionPhase": "IDLE",
                "motionKind": "NONE", "engineFlags": 1},
            landings=[{"index": index, "target": target, "finalTarget": target, "origin": origin,
                "returnValue": 4, "decision": 4, "decisionName": "TERRAIN", "accepted": False, "allowedMask": 0}
                for index, target in enumerate(targets)], preparedStarts=[], returnValue=0)
        events = [attempt]
        if finish:
            handoff = self.policy(12)
            handoff["data"].pop("laneHex")
            events.append(handoff)
        self.append(events)
        return attempt


def replay(items, *, maximum=None):
    meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=maximum or len(items) + 1)
    for snapshot, events in items:
        meter.observe(snapshot, events)
        if meter.failures: break
    return meter, meter.finish()


class ChainMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.good = Stream().complete().items

    @staticmethod
    def retry(stream, operation, returned=1):
        event = stream.policy(operation)
        data = event["data"]
        data.pop("laneHex")
        data["returnValue"] = returned
        return event

    def test_retry_calls_retain_diagnostics_without_movement_or_chance_credit(self):
        _, expected = replay(self.good)
        stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
        for operation in range(9, 14):
            for returned in (0, 1):
                stream.append([self.retry(stream, operation, returned)])
        for count in (8, 14, 10):
            for index in range(count):
                stream.motion("WALK", (1, 0), roll=20 if index == count - 1 else None,
                              selected=index == count - 1, lane_index=1)
            for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)):
                stream.motion("REPOSITION", delta)
        meter, result = replay(stream.items)
        self.assertTrue(result["passed"], result["failures"])
        for key in ("completeMotions", "eligibleMoves", "spawnPassed", "fingerprint"):
            self.assertEqual(result[key], expected[key])
        self.assertEqual([row["count"] for row in result["intervals"]], [8, 14, 10])
        self.assertEqual([row["motions"] for row in result["actions"]], [4, 4, 4])
        self.assertEqual(len(meter.boundaries), 3)
        self.assertEqual(meter.resets, [])

    def test_retry_still_checks_subject_profile_packet_and_actual_input_scope(self):
        for fault in ("pid", "after-pid", "slot", "operation", "header", "profile", "after-profile",
                      "form", "level", "authority", "lane", "rng", "return"):
            with self.subTest(fault=fault):
                stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                retry = self.retry(stream, 13)
                data = retry["data"]
                if fault == "pid": data["publicSubject"]["subjectIdentity"] += 1
                elif fault == "after-pid": data["publicSubjectAfter"]["subjectIdentity"] += 1
                elif fault in ("slot", "operation", "header"):
                    raw = bytearray.fromhex(data["responseHex"])
                    raw[{"slot": 8, "operation": 9, "header": 0}[fault]] ^= 1
                    data["responseHex"] = raw.hex()
                elif fault == "profile": data["publicSubject"]["behaviorFingerprint"] += 1
                elif fault == "after-profile": data["publicSubjectAfter"]["behaviorFingerprint"] += 1
                elif fault in ("form", "level"): data["publicSubjectAfter"][fault] += 1
                elif fault == "authority": data["publicSubjectAfter"]["authorityGeneration"] += 1
                elif fault == "lane": data["laneHex"] = stream.lanes[0]
                elif fault == "rng": data["rngReturns"] = [{"value": 20, "actorFrame": 1, "nativeCycle": 2}]
                else: data["returnValue"] = 2
                stream.append([retry])
                meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=100)
                for sample, events in stream.items: meter.observe(sample, events)
                self.assertTrue(meter.failures, fault)
        for operation in (5, 6, 7, 8, 14):
            with self.subTest(unrequested=operation):
                stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                stream.append([self.retry(stream, operation)])
                meter, result = replay(stream.items)
                self.assertIn("unexpected observed policy operation", json.dumps(meter.failures))

    def test_retry_cannot_bridge_a_pending_reset_to_a_later_lane_change(self):
        for operation in range(9, 14):
            with self.subTest(operation=operation):
                stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                stream.append([stream.policy(1, reset=True, lane_state=0)])
                for _ in range(5): stream.motion("WALK", (1, 0))
                stream.append([stream.policy(0)])
                meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=1000)
                for sample, events in stream.items: meter.observe(sample, events)
                self.assertTrue(meter.pending_resets)
                stream.append([self.retry(stream, operation)])
                meter.observe(*stream.items[-1])
                self.assertFalse(meter.pending_resets)
                stream.append([stream.policy(1, reset=True, lane_state=2)])
                meter.observe(*stream.items[-1])
                self.assertFalse(any(reset.get("laneTransition") for reset in meter.resets))
                self.assertIn("unexplained-chain-reset", json.dumps(meter.result()["measurementErrors"]))

    def seamless_successor(self):
        """The fourth skid ends as the next Walk starts, without an idle frame."""
        items = deepcopy(self.good)
        snapshot, events = items[-1]
        actor = snapshot["actors"][0]
        actor.update(origin=deepcopy(actor["logical"]),
                     target={"x": actor["logical"]["x"] + 1, "y": actor["logical"]["y"]},
                     motionKind="WALK", motionPhase="MOVING", motionElapsed=0,
                     motionDuration=8, reservationId=2)
        started = deepcopy(events[-1])
        started["data"].update(event="MOTION_STARTED", valueA=1, valueB=8,
                               sequence=started["data"]["sequence"] + 1)
        events.append(started)
        return items

    def test_stop_at_complete_action_with_zero_elapsed_successor(self):
        meter, result = replay(self.seamless_successor())
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(len(result["actions"]), 3)
        self.assertEqual(result["completeMotions"], 45)
        self.assertEqual(result["stopBoundary"]["kind"], "terminal-with-unmeasured-successor")
        self.assertEqual(result["stopBoundary"]["successor"]["elapsed"], 0)
        self.assertIsNotNone(meter.recorder.current)  # Never discard or count it.

    def test_successor_boundary_does_not_forgive_missing_terminal_or_later_motion(self):
        for fault in ("missing-terminal", "missing-successor-start", "duplicate-successor-start",
                      "later-frame", "advanced-successor", "wrong-origin"):
            with self.subTest(fault=fault):
                items = self.seamless_successor()
                snapshot, events = items[-1]
                actor = snapshot["actors"][0]
                if fault == "missing-terminal":
                    next(e for e in events if e["data"].get("event") == "CONTROL_RETURNED")["data"]["event"] = "UNRELATED_EVENT"
                elif fault == "missing-successor-start":
                    events[-1]["data"]["event"] = "UNRELATED_EVENT"
                elif fault == "duplicate-successor-start":
                    duplicate = deepcopy(events[-1])
                    duplicate["data"]["sequence"] += 1
                    events.append(duplicate)
                elif fault == "wrong-origin":
                    actor["origin"]["x"] += 1
                elif fault == "advanced-successor":
                    actor["motionElapsed"] = 1
                    actor["engineObject"]["pos_x"] += 8192
                else:
                    later = deepcopy(snapshot)
                    later["frame"] += 1
                    later["nativeCycle"] += 2
                    later["actorFrame"] += 1
                    later["actors"][0]["motionElapsed"] = 1
                    later["actors"][0]["engineObject"]["pos_x"] += 8192
                    items.append((later, []))
                _, result = replay(items)
                self.assertFalse(result["passed"])

    def test_trace_kind_mapping_matches_public_actor_abi(self):
        from tools.overworld.devtools_chain_measurement import KIND_IDS
        header = (Path(__file__).resolve().parents[2] / "include/overworld_actor_system.h").read_text()
        for name, value in KIND_IDS.items():
            native = re.search(r"OVERWORLD_ACTOR_MOTION_" + name + r"\s*=\s*(\d+)", header)
            self.assertIsNotNone(native)
            self.assertEqual(value, int(native.group(1)), name)

    def test_missing_completed_terminal_fails_without_waiting_for_budget(self):
        items = deepcopy(self.good)
        changed = False
        for _, events in items:
            for event in events:
                if not changed and event["data"].get("event") == "MOTION_FINISHED":
                    event["data"]["event"] = "UNRELATED_EVENT"
                    changed = True
        meter, result = replay(items)
        self.assertFalse(result["passed"])
        self.assertLess(meter.frames, len(items))
        self.assertEqual(meter.failures[0]["code"], "completed-motion-proof-failed")

    def test_complete_normal_profile_and_three_skid_actions(self):
        original = deepcopy(self.good)
        meter, result = replay(self.good)
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["acceptedProof"])
        self.assertTrue(result["spawnPassed"])
        self.assertEqual([item["count"] for item in result["intervals"]], [8, 14, 10])
        self.assertEqual([item["motions"] for item in result["actions"]], [4, 4, 4])
        self.assertEqual(result["eligibleMoves"], 32)
        self.assertEqual(result["completeMotions"], 45)
        self.assertEqual(result["fingerprint"], 12345)
        self.assertEqual(result["selectedProfileReceipt"]["resultHex"], self.good[0][0]["nativeObservation"]["resolvedProfiles"][0]["resultHex"])
        self.assertEqual(result["selectedProfileObservationCount"], 1)
        self.assertEqual(result["observedProfileCount"], 1)
        self.assertEqual(result["spawnGeometry"]["delta"], [16, 0])
        self.assertEqual(result["spawnGeometry"]["creation"]["arguments"][1:3], [0, 0])
        for group in ("identity", "chain", "render", "observation"):
            self.assertEqual(result[group + "Errors"], [])
        self.assertEqual(result["errorCoverage"]["completeRenderedMotions"], 45)
        self.assertEqual(result["intervals"][0]["matchingLaneIndexes"], [1, 2])
        self.assertEqual(self.good, original)
        with self.assertRaises(ValueError): meter.observe(*self.good[-1])

    def test_spawn_requires_actual_prepared_cardinal_offscreen_contract(self):
        for fault in ("absent-prefix", "wrong-locomotion", "wrong-pid", "wrong-species",
                      "wrong-prefix", "wrong-start", "wrong-target", "wrong-direction",
                      "inside", "edge-x", "edge-z", "wrong-map", "absent-player", "borrowed-spawn-location"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                spawn = next(e["data"] for _, events in items for e in events
                             if e["data"].get("observation") == "spawn-prepared")
                jump = spawn["jumpReceipts"][0]
                if fault == "borrowed-spawn-location":
                    prefix = bytearray.fromhex(spawn["preparedPrefixHex"])
                    struct.pack_into("<ii", prefix, 0, 100, 200)
                    spawn["preparedPrefixHex"] = prefix.hex()
                elif fault == "absent-prefix": del spawn["preparedPrefixHex"]
                elif fault == "wrong-locomotion": spawn["startup"]["locomotion"] = 0
                elif fault == "wrong-pid": spawn["preparedEncounter"]["personality"] += 1
                elif fault == "wrong-species": spawn["preparedEncounter"]["species"] = 56
                elif fault == "wrong-prefix": spawn["preparedPrefixHex"] = "00" * 30
                elif fault == "wrong-start": spawn["startup"]["origin"][0] += 1
                elif fault == "wrong-target": spawn["startup"]["target"][1] += 1
                elif fault == "wrong-direction": spawn["startup"]["hopDirection"] = 2
                elif fault in ("inside", "edge-x", "edge-z"):
                    jump["playerAtEntry"]["tile"] = {"inside": [0, 0], "edge-x": [8, 0], "edge-z": [0, 6]}[fault]
                elif fault == "wrong-map": jump["playerAtEntry"]["mapId"] = 67
                else: del jump["playerAtEntry"]
                self.assertFalse(replay(items)[1]["passed"], fault)

    def test_spawn_hop_frame_zero_rejects_landing_tile_flash(self):
        items = deepcopy(self.good)
        snapshot = next(snapshot for snapshot, events in items
                        if any(event["data"].get("observation") == "spawn-prepared"
                               for event in events))
        actor = snapshot["actors"][0]
        actor["render"] = deepcopy(actor["target"])
        result = replay(items)[1]
        self.assertFalse(result["passed"])
        self.assertIn("off-screen spawn Hop frame zero is not rendered at its origin",
                      str(result["renderErrors"]))

    def test_spawn_hop_rejects_sprite_created_at_landing_before_frame_zero(self):
        for fault in ("wrong-manager", "landing", "wrong-object", "wrong-direction"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                snapshot, events = next(item for item in items if any(
                    event["data"].get("observation") == "spawn-prepared"
                    for event in item[1]))
                create = next(event["data"] for event in events
                              if event["data"].get("observation") == "spawn-object-create")
                spawn = next(event["data"] for event in events
                             if event["data"].get("observation") == "spawn-prepared")
                if fault == "wrong-manager":
                    create["arguments"][0] += 4
                elif fault == "landing":
                    create["arguments"][1:3] = spawn["startup"]["target"]
                elif fault == "wrong-object":
                    create["returnValue"] += 0x12C
                else:
                    create["arguments"][3] = 2
                result = replay(items)[1]
                self.assertFalse(result["passed"])
                self.assertIn("visible field sprite was not created at the off-screen Hop origin",
                              str(result["renderErrors"]))

    def test_prepared_spawn_accepts_real_dtcm_stack_buffer_but_not_out_of_bounds(self):
        # Actual normal Route30 spawn in test-6d54a90b... used 0x027E35BC.
        for pointer, passed in ((0x027E35BC, True), (0x023FFFF0, False),
                                (0x027E3FB0, False), (0x027E35BD, False),
                                (0x027DF000, False), (0, False)):
            items = deepcopy(self.good)
            spawn = next(e["data"] for _, events in items for e in events
                         if e["data"].get("observation") == "spawn-prepared")
            spawn["preparedPointer"] = pointer
            with self.subTest(pointer=hex(pointer)):
                self.assertEqual(replay(items)[1]["passed"], passed)

    def test_short_or_diagonal_spawn_is_not_offscreen_hop_proof(self):
        for delta in ((3, 3), (15, 0), (17, 0), (8, 8), (0, 0)):
            with self.subTest(delta=delta):
                stream = Stream(); stream.motion("HOP", delta, pause=2, spawn=True)
                meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=20)
                for snapshot, events in stream.items: meter.observe(snapshot, events)
                self.assertTrue(meter.result()["failures"], delta)

    def test_error_groups_retain_actual_failed_checks_not_verdict_defaults(self):
        for group in ("identity", "chain", "render", "observation"):
            with self.subTest(group=group):
                items = deepcopy(self.good)
                if group == "identity": items[4][0]["actors"][0]["presentationAttached"] = False
                elif group == "render":
                    items[4][0]["actors"][0]["engineObject"] = deepcopy(items[3][0]["actors"][0]["engineObject"])
                elif group == "observation": items[4][0]["nativeObservation"]["coverageComplete"] = False
                else:
                    policy = next(e["data"] for _, events in items for e in events if e["data"].get("operation") == 4)
                    policy["laneHex"] = "00" * 72
                result = replay(items)[1]
                self.assertFalse(result["passed"])
                self.assertTrue(result[group + "Errors"], result)
        absent = replay([self.good[0]])[1]
        self.assertIsNone(absent["selectedProfileReceipt"])
        self.assertEqual(absent["selectedProfileObservationCount"], 0)
        self.assertEqual(absent["errorCoverage"]["identitySamples"], 0)
        self.assertTrue(absent["identityErrors"])

    def test_same_profile_accepts_exact_live_rattata_requests_at_two_levels(self):
        items = deepcopy(self.good)
        for request in ("1300000000000000030000000000000000000000",
                        "1300000000000000020000000000000000000000"):
            profile = deepcopy(items[0][0]["nativeObservation"]["resolvedProfiles"][0])
            profile["requestHex"] = request
            profile["fingerprint"] = 3990395777
            result = bytearray.fromhex(profile["resultHex"])
            result[252:256] = (3990395777).to_bytes(4, "little")
            profile["resultHex"] = result.hex()
            items[0][0]["nativeObservation"]["resolvedProfiles"].append(profile)
        meter, result = replay(items)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["selectedProfileReceipt"]["requestHex"], self.good[0][0]["nativeObservation"]["resolvedProfiles"][0]["requestHex"])
        self.assertEqual(len(meter.profile_requests[3990395777]), 2)

    def test_shared_fingerprint_keeps_earlier_exact_subject_request(self):
        items = deepcopy(self.good)
        for snapshot, _ in items:
            original = snapshot["nativeObservation"]["resolvedProfiles"][0]
            other = deepcopy(original)
            request = bytearray.fromhex(other["requestHex"]); request[8] = 2
            other["requestHex"] = request.hex()
            snapshot["nativeObservation"]["resolvedProfiles"].append(other)
        meter, result = replay(items)
        self.assertTrue(result["passed"], result)
        self.assertEqual(bytes.fromhex(result["selectedProfileReceipt"]["requestHex"])[8], 5)
        self.assertEqual(len(meter.profile_requests[12345]), 2)
        self.assertEqual(result["selectedProfileObservationCount"], 1)

    def test_request_variants_do_not_allow_wrong_subject_or_changed_output(self):
        for fault in ("species", "level", "terrain", "forced", "source", "result"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                for snapshot, events in items:
                    profiles = snapshot["nativeObservation"]["resolvedProfiles"]
                    profile = profiles[0]
                    if fault in ("species", "level", "terrain", "forced"):
                        request = bytearray.fromhex(profile["requestHex"])
                        request[{"species": 0, "level": 8, "terrain": 9, "forced": 12}[fault]] ^= 1
                        profile["requestHex"] = request.hex()
                    elif fault == "source": profile["sourceSha256"] = "b" * 64
                    elif fault == "result":
                        other = deepcopy(profile)
                        result = bytearray.fromhex(other["resultHex"]); result[216] ^= 1
                        other["resultHex"] = result.hex()
                        profiles.append(other)
                    for event in events:
                        if event["data"].get("observation") == "spawn-prepared":
                            event["data"]["resolverReceipts"][0].update(deepcopy(profile))
                result = replay(items)[1]
                self.assertFalse(result["passed"], result)
                self.assertTrue(result["chainErrors"], result)

    def test_nested_resolver_uses_last_actual_context_not_global_uniqueness(self):
        items = deepcopy(self.good)
        spawn = next(e["data"] for _, events in items for e in events
                     if e["data"].get("observation") == "spawn-prepared")
        later = deepcopy(spawn["resolverReceipts"][0])
        request = bytearray.fromhex(later["requestHex"]); request[2] = 0x40
        later["requestHex"] = request.hex()
        spawn["resolverReceipts"].append(later)
        result = replay(items)[1]
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["selectedProfileReceipt"]["requestHex"], later["requestHex"])

    def test_finalizer_owned_resolver_is_reused_by_spawn(self):
        items = deepcopy(self.good)
        spawn = next(e["data"] for _, events in items for e in events
                     if e["data"].get("observation") == "spawn-prepared")
        receipt = spawn["resolverReceipts"].pop()
        finalization_id = 7
        final = {key: deepcopy(spawn[key]) for key in
                 ("slot", "terrain", "preparedPointer", "preparedPrefixHex",
                  "preparedEncounter", "startup")}
        final.update(finalizationId=finalization_id, returnValue=1, pairEligible=True,
                     inputEncounter=deepcopy(spawn["preparedEncounter"]),
                     resolverReceipts=[{key: deepcopy(value) for key, value in receipt.items()
                                        if key not in ("slot", "sourceIdentity")}])
        final["resolverReceipts"][0].update(finalizationId=finalization_id,
                                             inputEncounter=deepcopy(final["inputEncounter"]))
        spawn["finalization"] = {"status": "matched", "receipt": final}
        result = replay(items)[1]
        self.assertTrue(result["passed"], result)

    def test_finalizer_resolver_requires_exact_pair_ownership(self):
        for fault in ("status", "eligible", "pointer", "id", "encounter", "missing"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                spawn = next(e["data"] for _, events in items for e in events
                             if e["data"].get("observation") == "spawn-prepared")
                receipt = spawn["resolverReceipts"].pop()
                finalization_id = 7
                final = {key: deepcopy(spawn[key]) for key in
                         ("slot", "terrain", "preparedPointer", "preparedPrefixHex",
                          "preparedEncounter", "startup")}
                final.update(finalizationId=finalization_id, returnValue=1, pairEligible=True,
                             inputEncounter=deepcopy(spawn["preparedEncounter"]),
                             resolverReceipts=[{key: deepcopy(value) for key, value in receipt.items()
                                                if key not in ("slot", "sourceIdentity")}])
                final["resolverReceipts"][0].update(finalizationId=finalization_id,
                                                     inputEncounter=deepcopy(final["inputEncounter"]))
                pair = spawn["finalization"] = {"status": "matched", "receipt": final}
                if fault == "status": pair["status"] = "missing"
                elif fault == "eligible": final["pairEligible"] = False
                elif fault == "pointer": final["preparedPointer"] += 4
                elif fault == "id": final["resolverReceipts"][0]["finalizationId"] += 1
                elif fault == "encounter": final["resolverReceipts"][0]["inputEncounter"]["level"] += 1
                else: final["resolverReceipts"] = []
                self.assertFalse(replay(items)[1]["passed"])

    def test_nested_resolver_missing_stale_or_wrong_source_cannot_pass(self):
        for fault in ("missing", "slot", "pid", "object", "fingerprint", "failed"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                spawn = next(e["data"] for _, events in items for e in events
                             if e["data"].get("observation") == "spawn-prepared")
                receipt = spawn["resolverReceipts"][0]
                if fault == "missing": spawn.pop("resolverReceipts")
                elif fault == "slot": receipt["slot"] += 1
                elif fault == "pid": receipt["sourceIdentity"]["personality"] += 1
                elif fault == "object": receipt["sourceIdentity"]["object"] += 4
                elif fault == "failed": receipt["resolved"] = False
                else: receipt["fingerprint"] += 1
                self.assertFalse(replay(items)[1]["passed"])

    def test_vacant_slot_policy_before_spawn_is_not_current_actor_history(self):
        for after in (False, True):
            items = deepcopy(self.good)
            events = items[1][1]
            policy = deepcopy(next(e for _, es in items for e in es
                                   if e["data"].get("observation") == "walk-policy"))
            policy["frame"] = items[1][0]["frame"]
            policy["data"]["publicSubject"] = {"status": "not-active", "slot": 0}
            events.insert(len(events) if after else 1, policy)
            sequence = 0
            for snapshot, es in items:
                for event in es:
                    if event["kind"] == "native-observation":
                        sequence += 1; event["data"]["sequence"] = sequence
                snapshot["nativeObservation"]["sequence"] = sequence
            result = replay(items)[1]
            self.assertEqual(result["passed"], not after, result)

    def test_request_storage_is_bounded_and_repeated_cache_is_not_new_evidence(self):
        meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=1)
        profile = deepcopy(self.good[0][0]["nativeObservation"]["resolvedProfiles"][0])
        for value in range(256):
            request = bytearray.fromhex(profile["requestHex"])
            request[2:4] = value.to_bytes(2, "little")
            profile["requestHex"] = request.hex()
            meter._profile(profile)
            meter._profile(profile)
        self.assertEqual(meter.profile_request_count, 256)
        request[2:4] = (256).to_bytes(2, "little"); profile["requestHex"] = request.hex()
        with self.assertRaisesRegex(ValueError, "request observation bound"):
            meter._profile(profile)
        self.assertEqual(meter.profile_request_count, 256)

    def test_missing_subject_and_preexisting_actor_never_pass(self):
        _, result = replay([self.good[0]])
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"][0]["code"], "missing-natural-ledyba")
        items = deepcopy(self.good); items[0][0]["actors"] = deepcopy(items[1][0]["actors"])
        self.assertFalse(replay(items)[1]["passed"])

    def test_identity_mode_profile_and_coverage_fail_closed(self):
        changes = [lambda s: s.update(prepared=True),
                   lambda s: s["context"].update(mapGeneration=5),
                   lambda s: s["context"].update(mapId=67),
                   lambda s: s["actors"][0].update(species=56),
                   lambda s: s["actors"][0].update(role="FOLLOWER"),
                   lambda s: s["actors"][0].update(presentationAttached=False),
                   lambda s: s["actors"][0].update(identityVerified=False),
                   lambda s: s["actors"][0].update(behaviorFingerprint=54321),
                   lambda s: s["actors"][0]["sourceIdentity"].update(form=1),
                   lambda s: s["actors"][0]["sourceIdentity"].update(level=6),
                   lambda s: s["actors"][0]["engineIdentity"].update(current_manager=0),
                   lambda s: s["nativeObservation"].update(eventsDropped=1),
                   lambda s: s["nativeObservation"].update(coverageComplete=False),
                   lambda s: s["nativeObservation"].update(installedBeforeBoot=False)]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                items = deepcopy(self.good); change(items[4][0])
                self.assertFalse(replay(items)[1]["passed"])

    def test_missing_render_frame_frozen_pose_high_skid_and_changed_facing_fail(self):
        for fault in ("missing-frame", "frozen", "jump", "facing", "late-start", "pause", "control"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                index = next(i for i, (s, _) in enumerate(items) if s["actors"]
                    and s["actors"][0]["motionKind"] == "REPOSITION" and s["actors"][0]["motionElapsed"] == 4)
                actor = items[index][0]["actors"][0]
                if fault == "missing-frame": items.pop(index)
                elif fault == "frozen": actor["engineObject"] = deepcopy(items[index - 1][0]["actors"][0]["engineObject"])
                elif fault == "jump": actor["engineObject"]["unk88_y"] = -3000
                elif fault == "facing": actor["engineObject"]["facing"] = 1
                elif fault == "late-start":
                    items = [items[0], *items[3:]]
                elif fault == "pause":
                    # The spawn's observed settle is one frame shorter.
                    items[10][0]["actors"][0].update(motionPhase="IDLE", motionKind="NONE")
                else:
                    end = next(s for s, _ in items[index:] if s["actors"][0]["motionPhase"] == "IDLE")
                    end["actors"][0]["engineObject"]["flags"] = 0x11
                self.assertFalse(replay(items)[1]["passed"])

    def test_normal_walk_must_face_player_from_its_first_frame(self):
        items = deepcopy(self.good)
        index = next(i for i, (snapshot, _) in enumerate(items)
            if snapshot["actors"]
            and snapshot["actors"][0]["motionKind"] == "WALK"
            and snapshot["actors"][0]["motionElapsed"] == 0)
        items[index][0]["actors"][0]["engineObject"]["facing"] = 3
        result = replay(items)[1]
        self.assertFalse(result["passed"])
        self.assertIn("face the player", result["failures"][0]["message"])

    def test_missing_start_commit_control_and_chance_receipts_fail(self):
        for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED", "rng"):
            with self.subTest(name=name):
                items = deepcopy(self.good)
                found = False
                for _, events in items:
                    for event in events:
                        data = event["data"]
                        if name == "rng" and data.get("operation") == 4 and data.get("rngReturns"):
                            data["rngReturns"] = []; found = True; break
                        if data.get("event") == name:
                            # Keep sequence intact: remove the meaning, not transport.
                            data["event"] = "WORLD_EFFECT"; found = True; break
                    if found: break
                self.assertTrue(found)
                self.assertFalse(replay(items)[1]["passed"])

    def test_wrong_chance_lane_and_action_timing_fail(self):
        for fault in ("chance", "unknown-lane", "changed-chain", "timing"):
            with self.subTest(fault=fault):
                items = deepcopy(self.good)
                data = next(e["data"] for _, events in items for e in events
                            if e["data"].get("operation") == 4 and e["data"].get("rngReturns"))
                if fault == "chance": data["rngReturns"][0]["value"] = 80
                elif fault == "timing":
                    response = bytearray.fromhex(data["responseHex"]); response[23] = 4; data["responseHex"] = response.hex()
                else:
                    lane = bytearray.fromhex(data["laneHex"]); lane[0 if fault == "unknown-lane" else 29] ^= 1
                    data["laneHex"] = lane.hex()
                self.assertFalse(replay(items)[1]["passed"])

    def test_three_moves_reposition_misclassification_and_incomplete_actions_fail(self):
        for count, kind in ((3, "REPOSITION"), (8, "HOP")):
            stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
            for _ in range(3):
                for index in range(count): stream.motion("WALK", (1, 0), roll=20 if index == count - 1 else None, selected=index == count - 1)
                for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)): stream.motion(kind, delta, pause=2 if kind == "HOP" else 0)
            self.assertFalse(replay(stream.items)[1]["passed"])
        self.assertFalse(replay(self.good[:-1])[1]["passed"])

    def test_wrap_counter_and_explicit_bounds(self):
        _, result = replay(Stream(initial_commit=0xFFFFFFFE).complete().items)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["eligibleMoves"], 32)
        self.assertFalse(replay(self.good, maximum=12)[1]["passed"])
        with self.assertRaises(ValueError): LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=0)

    def test_preacquisition_trace_and_cached_resolver_are_not_dropped(self):
        items = deepcopy(self.good)
        old = {"frame": 1, "kind": "native", "data": {"traceStream": 1, "sequence": 1,
            "event": "ACTOR_ATTACHED", "actorHandle": 65538,
            "actor": {"slot": 2, "generation": 1, "fieldEpoch": 2, "mapGeneration": 4, "encounterGeneration": 1}}}
        items[0][1].append(old)
        for _, events in items[1:]:
            for event in events:
                if event["kind"] == "native": event["data"]["sequence"] += 1
        self.assertTrue(replay(items)[1]["passed"])
        # Cache loss cannot be replaced by the public actor's fingerprint label.
        for snapshot, _ in items: snapshot["nativeObservation"]["resolvedProfiles"] = []
        self.assertFalse(replay(items)[1]["passed"])

    def test_regular_skid_commits_do_not_count_toward_the_chain(self):
        stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
        for _ in range(3):
            stream.motion("WALK", (1, 0), skid=True)
            for index in range(8): stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
            for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)): stream.motion("REPOSITION", delta)
        _, result = replay(stream.items)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["eligibleMoves"], 24)
        self.assertEqual([item["count"] for item in result["intervals"]], [8, 8, 8])

    def test_actual_lane_reset_can_interrupt_but_an_unexplained_reset_cannot(self):
        for changed_lane in (True, False):
            stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
            stream.append([stream.policy(1, reset=True, lane_state=0)])
            for _ in range(5): stream.motion("WALK", (1, 0))
            stream.append([stream.policy(1, reset=True, lane_state=2 if changed_lane else 0)])
            for _ in range(3):
                for index in range(8): stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
                for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)): stream.motion("REPOSITION", delta)
            _, result = replay(stream.items)
            self.assertEqual(result["passed"], changed_lane, result)
            if changed_lane:
                self.assertEqual([item["count"] for item in result["intervals"]], [8, 8, 8])
                self.assertEqual(result["interruptedIntervals"][-1]["count"], 5)
            else:
                self.assertIn("unexplained-chain-reset", [item["reason"] for item in result["measurementErrors"]])

    def test_explicit_reset_pairs_with_next_real_lane_input_not_its_zero_lane_byte(self):
        for old_lane, new_lane, intervening_move in ((0, 2, False), (2, 0, False),
                                                    (2, 2, False), (0, 2, True)):
            with self.subTest(old=old_lane, new=new_lane, intervening=intervening_move):
                stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                stream.append([stream.policy(1, reset=True, lane_state=old_lane)])
                for _ in range(5): stream.motion("WALK", (1, 0))
                # Native ClearWalkMovementState sends a zero-filled RESET.
                # Its lane byte is not a lane observation. The next frame's
                # INPUT supplies that fact for the same live actor.
                stream.append([stream.policy(0)])
                if intervening_move:
                    stream.motion("WALK", (1, 0))
                stream.append([stream.policy(1, reset=True, lane_state=new_lane)])
                for _ in range(3):
                    for index in range(8):
                        stream.motion("WALK", (1, 0), roll=20 if index == 7 else None,
                                      selected=index == 7)
                    for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)):
                        stream.motion("REPOSITION", delta)
                meter, result = replay(stream.items)
                allowed = old_lane != new_lane and not intervening_move
                self.assertEqual(result["passed"], allowed, result)
                if allowed:
                    paired = [item for item in result["interruptedIntervals"]
                              if item["reset"]["reason"] == "explicit-policy-reset"]
                    self.assertEqual(len(paired), 1)
                    transition = paired[0]["reset"]["laneTransition"]
                    self.assertEqual(transition["fromLaneState"], old_lane)
                    self.assertEqual(transition["toLaneState"], new_lane)
                    self.assertEqual([item["count"] for item in result["intervals"]], [8, 8, 8])
                else:
                    self.assertTrue(meter.failures, "known invalid reset must stop the live job")
                    self.assertLess(meter.frames, len(stream.items))

    def test_wrong_complete_chain_count_fails_before_waiting_for_more_actions(self):
        stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
        for index in range(3):
            stream.motion("WALK", (1, 0), roll=20 if index == 2 else None, selected=index == 2)
        meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=6000)
        for snapshot, events in stream.items:
            meter.observe(snapshot, events)
        self.assertTrue(meter.failures, "a completed three-move chain cannot repair itself later")
        self.assertIn("chain-move-count", [item["reason"] for item in meter.result()["measurementErrors"]])

    def test_later_missing_boundary_cannot_hide_behind_three_good_actions(self):
        stream = Stream().complete()
        for _ in range(15):
            stream.motion("WALK", (1, 0))
        meter, result = replay(stream.items)
        self.assertFalse(result["passed"])
        self.assertTrue(meter.failures)
        self.assertIn("chain-boundary-overdue", [item["reason"] for item in result["measurementErrors"]])

    def test_partial_action_fails_when_normal_motion_resumes(self):
        stream = Stream().complete()
        for index in range(8):
            stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
        for delta in ((2, 2), (-2, 2)):
            stream.motion("REPOSITION", delta)
        partial_end = len(stream.items)
        stream.motion("WALK", (1, 0))
        meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=len(stream.items) + 1)
        for item in stream.items[:partial_end]:
            meter.observe(*item)
        self.assertFalse(meter.failures, "two pending legs are not yet a lost action")
        for item in stream.items[partial_end:]:
            result = meter.observe(*item)
        self.assertTrue(meter.failures, "ordinary motion closed the partial action; do not wait out the job")
        self.assertIn("reposition-action-truncated", [item["reason"] for item in result["measurementErrors"]])

    def test_explicit_native_permanent_abort_closes_without_four_leg_credit(self):
        stream = Stream().complete()
        for index in range(8):
            stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
        for delta in ((2, 2), (-2, 2)): stream.motion("REPOSITION", delta)
        stream.abort_reposition()
        stream.motion("WALK", (1, 0))
        _, result = replay(stream.items)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(len(result["actions"]), 3)
        self.assertEqual(len(result["abortedActions"]), 1)
        self.assertEqual(result["abortedActions"][0]["motions"], 2)
        self.assertFalse(result["abortedActions"][0]["countsAsCompleteAction"])

    @staticmethod
    def partial_abort(*, legs=2, finish=True, complete_prefix=True):
        stream = Stream()
        if complete_prefix: stream.complete()
        else: stream.motion("HOP", (16, 0), pause=2, spawn=True)
        for index in range(8):
            stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
        for delta in ((2, 2), (-2, 2))[:legs]: stream.motion("REPOSITION", delta)
        stream.abort_reposition(completed_legs=legs, finish=finish)
        return stream

    def test_abort_zero_legs_uses_last_ordinary_control_return(self):
        stream = self.partial_abort(legs=0)
        stream.motion("WALK", (1, 0))
        _, result = replay(stream.items)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["abortedActions"][0]["motions"], 0)
        self.assertEqual(len(result["actions"]), 3)

    def test_abort_never_replaces_three_complete_four_leg_actions(self):
        stream = self.partial_abort(complete_prefix=False)
        stream.motion("WALK", (1, 0))
        _, result = replay(stream.items)
        self.assertFalse(result["passed"])
        self.assertEqual(result["actions"], [])
        self.assertEqual(len(result["abortedActions"]), 1)
        self.assertEqual(result["abortedActions"][0]["motions"], 2)

    def test_abort_meaning_reasons_destinations_and_finish_are_required(self):
        for fault in ("meaning", "legacy", "result-bytes", "unknown-child", "occupied", "busy", "duplicate-target",
                      "missing-target", "wrong-origin", "pid", "profile", "commit", "missing-finish", "failed-finish",
                      "wrong-finish-commit", "missing-control", "reserved-control", "wrong-count", "wrong-mask",
                      "occupied-detail", "wrong-world", "wrong-native-object"):
            with self.subTest(fault=fault):
                stream = self.partial_abort()
                events = stream.items[-1][1]
                attempt, finish = events[0]["data"], events[1]["data"]
                if fault == "meaning": attempt["observation"] = "unrelated-native-call"
                elif fault == "legacy": attempt.pop("observationVersion")
                elif fault == "result-bytes": attempt["resultHex"] = "a3000304"
                elif fault in ("unknown-child", "occupied", "busy"):
                    decision, name = {"unknown-child": (8, "PROFILE"), "occupied": (5, "OCCUPIED"), "busy": (1, "RETRY_WORLD_BUSY")}[fault]
                    attempt["landings"][0].update(decision=decision, decisionName=name, returnValue=decision)
                elif fault == "duplicate-target": attempt["landings"][1] = deepcopy(attempt["landings"][0])
                elif fault == "missing-target": attempt["landings"].pop()
                elif fault == "wrong-origin": attempt["nativeOrigin"][0] += 1
                elif fault == "pid": attempt["publicSubjectAfter"]["subjectIdentity"] += 1
                elif fault == "profile": attempt["publicSubject"]["behaviorFingerprint"] += 1
                elif fault == "commit": attempt["publicSubject"]["commitSequence"] += 1
                elif fault == "missing-finish": finish["observation"] = "unrelated-native-call"
                elif fault == "failed-finish": finish["returnValue"] = 0
                elif fault == "wrong-finish-commit":
                    finish["publicSubject"]["commitSequence"] += 1
                    finish["publicSubjectAfter"]["commitSequence"] += 1
                elif fault == "missing-control":
                    for _, trace_events in stream.items[:-1]:
                        for event in trace_events:
                            if event.get("kind") == "native" and event["data"].get("event") == "CONTROL_RETURNED" \
                                    and event["data"]["valueB"] == stream.actor["commitSequence"]:
                                event["data"]["event"] = "WORLD_EFFECT"
                elif fault == "reserved-control": attempt["nativeControlAfter"]["reservationId"] = 1
                elif fault == "wrong-mask": attempt["landings"][0]["allowedMask"] = 99
                elif fault == "occupied-detail": attempt["landings"][0]["occupancyQueries"] = [{"returnValue": 1}]
                elif fault == "wrong-world": attempt["worldContext"]["mapGeneration"] += 1
                elif fault == "wrong-native-object": attempt["engineIdentity"]["pointer"] += 4
                elif fault == "wrong-count":
                    attempt["encodedRemaining"] = 0xA4
                    attempt["nativeResult"]["encodedRemaining"] = 0xA4
                    attempt["resultHex"] = "a400030c"
                stream.motion("WALK", (1, 0))
                _, result = replay(stream.items)
                self.assertFalse(result["passed"])
                self.assertEqual(result["abortedActions"], [])

    def test_abort_keeps_actual_partial_leg_render_checks(self):
        stream = self.partial_abort()
        # Damage one already executed leg, not an unused candidate.
        for snapshot, _ in reversed(stream.items):
            if snapshot["actors"] and snapshot["actors"][0]["motionKind"] == "REPOSITION" \
                    and snapshot["actors"][0]["motionPhase"] == "MOVING":
                snapshot["actors"][0]["engineObject"]["unk88_y"] = -100
                break
        _, result = replay(stream.items)
        self.assertFalse(result["passed"])
        self.assertTrue(result["renderErrors"])

    def test_abort_native_decision_decoder_matches_public_header(self):
        from tools.overworld.devtools_chain_measurement import MOTION_DECISIONS, CHAIN_OUTCOMES
        header = (Path(__file__).resolve().parents[2] / "include/overworld_motion_model.h").read_text()
        actual = {int(value): name for name, value in re.findall(r"OVERWORLD_MOTION_DECISION_(\w+)\s*=\s*(\d+)", header)}
        self.assertEqual({index: name for index, name in enumerate(MOTION_DECISIONS)}, actual)
        source = (Path(__file__).resolve().parents[2] / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        outcomes = {int(value): name for name, value in re.findall(r"#define OW_WILD_CHAIN_(RETRY|STARTED|COMPLETE|ABORT)\s+(\d+)", source)}
        self.assertEqual(dict(enumerate(CHAIN_OUTCOMES)), outcomes)

    def test_attempt_and_handoff_revisions_invalidate_cached_evaluation(self):
        stream = self.partial_abort()
        meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=6000)
        for snapshot, events in stream.items[:-1]: meter.observe(snapshot, events)
        before = meter.evaluation_cache[0]
        result = meter.observe(*stream.items[-1])
        self.assertNotEqual(before, meter.evaluation_cache[0])
        self.assertEqual(len(result["abortedActions"]), 1)
        self.assertEqual(len(result["actions"]), 3)

    def test_flat_planner_blocked_candidate_can_supply_permanent_abort_reason(self):
        for fault in (None, "missing-plan", "wrong-lane", "request-started", "unknown-reason", "different-target"):
            with self.subTest(fault=fault):
                stream = self.partial_abort()
                attempt = stream.items[-1][1][0]["data"]
                candidate = attempt["landings"][0]
                candidate.update(decision=0, returnValue=0, decisionName="ACCEPTED", accepted=True)
                plan = {"decision": 2, "returnValue": 2, "decisionName": "BLOCKED", "operation": 2,
                    "origin": candidate["origin"], "target": candidate["target"], "laneHex": stream.lanes[0],
                    "objectPointer": stream.actor["sourceIdentity"]["object"], "fieldPointer": 0x02050000}
                start = {"landingIndex": 0, "returnValue": 2, "accepted": False,
                    "startReason": 2, "startReasonName": "BLOCKED", "target": candidate["target"],
                    "distance": 2, "motionRequests": [], "hopPlans": [plan]}
                attempt["preparedStarts"] = [start]
                if fault == "missing-plan": start["hopPlans"] = []
                elif fault == "wrong-lane": plan["laneHex"] = stream.lanes[1]
                elif fault == "request-started": start["motionRequests"] = [{"decision": 0}]
                elif fault == "unknown-reason": start.update(returnValue=8, startReason=8, startReasonName="PROFILE")
                elif fault == "different-target": plan["target"] = [999, 999]
                stream.motion("WALK", (1, 0))
                _, result = replay(stream.items)
                self.assertEqual(result["passed"], fault is None, result["failures"])

    def test_stop_skid_does_not_close_a_pending_chain_action(self):
        stream = Stream().complete()
        for index in range(8):
            stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
        stream.motion("WALK", (1, 0), skid=True)
        for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)):
            stream.motion("REPOSITION", delta)
        meter, result = replay(stream.items)
        self.assertFalse(meter.failures)
        self.assertTrue(result["passed"], result["measurementErrors"])
        self.assertEqual(result["eligibleMoves"], 40)

    def test_tail_at_upper_limit_and_skids_do_not_invent_missing_boundary(self):
        stream = Stream().complete()
        for _ in range(14):
            stream.motion("WALK", (1, 0))
        _, result = replay(stream.items)
        self.assertTrue(result["passed"], result["failures"])

    def test_overdue_tail_waits_for_full_settle_not_just_logical_commit(self):
        stream = Stream().complete()
        for _ in range(14):
            stream.motion("WALK", (1, 0))
        stream.motion("WALK", (1, 0), pause=3)
        meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=len(stream.items) + 1)
        for snapshot, events in stream.items[:-1]:
            meter.observe(snapshot, events)
            self.assertFalse(meter.failures)
        result = meter.observe(*stream.items[-1])
        self.assertIn("chain-boundary-overdue", [item["reason"] for item in result["measurementErrors"]])

    def test_ready_prefix_does_not_hide_later_identity_render_or_frame_fault(self):
        for fault in ("identity", "render", "frame-gap", "terminal"):
            with self.subTest(fault=fault):
                stream = Stream().complete()
                prefix = len(stream.items)
                stream.motion("WALK", (1, 0))
                current, events = stream.items[prefix + 1]
                if fault == "identity":
                    current["actors"][0]["subjectIdentity"] += 1
                elif fault == "render":
                    current["actors"][0]["engineObject"]["pos_x"] += 0x10000
                elif fault == "frame-gap":
                    current["frame"] += 1
                else:
                    current, events = stream.items[-1]
                    events[:] = [event for event in events
                        if event["data"].get("event") != "CONTROL_RETURNED"]
                meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=len(stream.items) + 1)
                for item in stream.items[:prefix]:
                    result = meter.observe(*item)
                self.assertTrue(result["ready"])
                for item in stream.items[prefix:]:
                    result = meter.observe(*item)
                self.assertTrue(result["failures"], fault)
                self.assertFalse(meter.finish()["passed"])

    def test_pending_reset_cannot_pass_without_real_input_or_cross_a_policy_barrier(self):
        for barrier in (None, 2, 3, 4, "counter", "subject", "too-many-moves"):
            with self.subTest(barrier=barrier):
                stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                stream.append([stream.policy(1, reset=True, lane_state=2)])
                for _ in range(20 if barrier == "too-many-moves" else 5):
                    stream.motion("WALK", (1, 0))
                stream.append([stream.policy(0)])
                if type(barrier) is int:
                    stream.append([stream.policy(barrier)])
                if barrier is not None:
                    event = stream.policy(1, reset=True, lane_state=0,
                                          counter=stream.actor["commitSequence"] + (barrier == "counter"))
                    if barrier == "subject":
                        event["data"]["publicSubject"]["subjectIdentity"] += 1
                    stream.append([event])
                meter, result = replay(stream.items)
                self.assertFalse(result["passed"])
                self.assertFalse(result["ready"])
                self.assertTrue(meter.failures)
                if barrier == "too-many-moves":
                    # The open-tail guard now catches the fifteenth move,
                    # before a later RESET can even be offered as an excuse.
                    self.assertIn("chain-boundary-overdue",
                                  [item["reason"] for item in result["measurementErrors"]])

    def test_pending_reset_uses_input_boundary_pose_not_end_of_frame_pose(self):
        for input_phase in ("IDLE", "MOVING", "SETTLING"):
            with self.subTest(input_phase=input_phase):
                stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                stream.append([stream.policy(1, reset=True, lane_state=0)])
                for _ in range(5): stream.motion("WALK", (1, 0))
                stream.append([stream.policy(0)])
                event = stream.policy(1, reset=True, lane_state=2)
                for key in ("publicSubject", "publicSubjectAfter"):
                    event["data"][key]["motionPhase"] = input_phase
                first = len(stream.items)
                for action in range(3):
                    for index in range(8):
                        stream.motion("WALK", (1, 0), roll=20 if index == 7 else None,
                                      selected=index == 7)
                    for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)):
                        stream.motion("REPOSITION", delta)
                # A legitimate IDLE INPUT can start this frame's motion.
                # Sampling the end-of-frame MOVING pose alone is too late.
                stream.items[first][1].insert(0, event)
                meter, result = replay(stream.items)
                self.assertEqual(result["passed"], input_phase == "IDLE", result)
                if input_phase != "IDLE":
                    self.assertTrue(meter.failures)
                    self.assertIn("unexplained-chain-reset",
                                  [item["reason"] for item in result["measurementErrors"]])

    def test_ignored_candidate_does_not_publish_a_lane_handoff(self):
        for explicit in (False, True):
            for next_lane in (0, 2):
                with self.subTest(explicit=explicit, next_lane=next_lane):
                    stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
                    stream.append([stream.policy(1, reset=True, lane_state=0)])
                    for _ in range(5): stream.motion("WALK", (1, 0))
                    if explicit:
                        stream.append([stream.policy(0)])
                    ignored = stream.policy(1, lane_state=next_lane)
                    # The fixture lane is cardinal-only; direction4 is a
                    # rejected diagonal. IGNORED with no reset is not a
                    # completed policy lane handoff.
                    for key in ("requestHex", "responseHex"):
                        packet = bytearray.fromhex(ignored["data"][key]); packet[10] = 4
                        ignored["data"][key] = packet.hex()
                    stream.append([ignored])
                    stream.append([stream.policy(1, reset=True, lane_state=next_lane)])
                    for _ in range(3):
                        for index in range(8):
                            stream.motion("WALK", (1, 0), roll=20 if index == 7 else None,
                                          selected=index == 7)
                        for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)):
                            stream.motion("REPOSITION", delta)
                    _, result = replay(stream.items)
                    self.assertEqual(result["passed"], next_lane == 2, result)

    def test_observed_chance_skip_starts_a_new_interval_without_an_action(self):
        stream = Stream(); stream.motion("HOP", (16, 0), pause=2, spawn=True)
        for index in range(8): stream.motion("WALK", (1, 0), roll=80 if index == 7 else None)
        for _ in range(3):
            for index in range(8): stream.motion("WALK", (1, 0), roll=20 if index == 7 else None, selected=index == 7)
            for delta in ((2, 2), (-2, 2), (-2, -2), (2, -2)): stream.motion("REPOSITION", delta)
        _, result = replay(stream.items)
        self.assertTrue(result["passed"], result)
        self.assertEqual(len(result["intervals"]), 4)
        self.assertFalse(result["intervals"][0]["selected"])
        self.assertEqual(len(result["actions"]), 3)

    def test_preview_never_claims_pass_and_terminal_failure_is_sticky(self):
        meter = LedybaChainMeasurement(SCHEMA, SOURCE, max_frames=len(self.good) + 1)
        for snapshot, events in self.good:
            result = meter.observe(snapshot, events)
            self.assertFalse(result["passed"])
            self.assertFalse(result["acceptedProof"])
        self.assertTrue(result["ready"])
        bad = deepcopy(self.good[-1][0]); bad["frame"] += 1; bad["prepared"] = True
        first = meter.observe(bad)["failures"]
        self.assertEqual(meter.observe(bad)["failures"], first)
        self.assertFalse(meter.finish()["passed"])

    def test_explicit_preboot_sequence_baseline_does_not_forgive_later_gaps(self):
        items = deepcopy(self.good)
        for snapshot, events in items:
            snapshot["nativeObservation"]["sequence"] += 40
            for event in events:
                if event["kind"] == "native-observation": event["data"]["sequence"] += 40
        _, result = replay(items)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["observationBaseline"]["nativeSequence"], 40)
        # A missing whole last receipt is visible even with no later event.
        items[1][1].pop()
        self.assertFalse(replay(items)[1]["passed"])
        items = deepcopy(self.good); items[0][0]["nativeObservation"]["pendingUnframedEvents"] = 1
        self.assertFalse(replay(items)[1]["passed"])

    def test_real_installed_observer_receipts_feed_the_same_measurement(self):
        # Exercise the shared observer's real callbacks/ABI readers, not only
        # our synthetic event builder. The host supplies read-only fake memory.
        from tools.overworld.test_devtools_observer import Fixture
        stream = Stream().complete()
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)
            fixture.actor = deepcopy(stream.items[1][0]["actors"][0])
            fixture.rt.wild_spawn = lambda emu, slot: deepcopy(fixture.actor["sourceIdentity"])
            fixture.rt.object_state = lambda emu, pointer: {"x": 16 if pointer == fixture.player_pointer else 0, "y": 0}
            fixture.prepare_spawn(origin=(0, 0), target=(16, 0))
            fixture.put(0x02220000, bytes.fromhex(stream.profile["requestHex"]))
            fixture.put(0x02220100, bytes.fromhex(stream.profile["resultHex"]))
            fixture.enter("behavior-resolved", r2=0x02220000, r3=0x02220100); fixture.returned(0)
            fixture.enter("spawn-prepared", r2=0, r3=0)
            fixture.enter("spawn-object-create", lr=0x02001081,
                          r0=0x02020000, r1=0, r2=0, r3=1)
            fixture.returned(0x02010000, address=0x02001080)
            fixture.enter("behavior-resolved", sp=0x027E3760, lr=0x02001061, r2=0x02220000, r3=0x02220100)
            fixture.returned(0, sp=0x027E3760, address=0x02001060)
            fixture.put(0x027E3788, struct.pack("<ii", 16, 0))
            fixture.enter("spawn-motion", sp=0x027E3780, lr=0x02001041, r2=0, r3=0x02010000)
            fixture.returned(1, sp=0x027E3780, address=0x02001040); fixture.returned(1)
            for operation in range(9, 14):
                packet = bytearray(28); struct.pack_into("<HH", packet, 0, 1, 28)
                packet[9] = operation; packet[10:12] = bytes((0xFD, 0x23))
                packet[22:24] = bytes((5, 8))
                fixture.put(0x02220000, packet)
                fixture.enter("walk-policy", r0=0x02220000)
                fixture.returned(0 if operation == 13 else 1)
            fixture.observer.completed_frame(2)
            actual = fixture.observer.drain()
            self.assertEqual([item["data"]["observation"] for item in actual],
                             ["behavior-resolved", "spawn-object-create", "behavior-resolved",
                              "spawn-motion", "spawn-prepared"]
                             + ["walk-policy"] * 5)
            self.assertEqual([item["data"]["operation"] for item in actual[-5:]], list(range(9, 14)))
            self.assertIsNone(fixture.hooks.error)
            items = stream.items
            sequence_delta = len(actual) - sum(event["kind"] == "native-observation" for event in items[1][1])
            items[1][1][:] = [item for item in items[1][1] if item["kind"] != "native-observation"] + actual
            for index, (snapshot, events) in enumerate(items):
                snapshot["nativeObservation"]["resolvedProfiles"][0]["sourceSha256"] = fixture.observer.source_hash
                if index: snapshot["nativeObservation"]["sequence"] += sequence_delta
                if index > 1:
                    for event in events:
                        if event["kind"] == "native-observation": event["data"]["sequence"] += sequence_delta
            meter = LedybaChainMeasurement(SCHEMA, fixture.observer.source_hash, max_frames=len(items) + 1)
            for snapshot, events in items: meter.observe(snapshot, events)
            self.assertTrue(meter.finish()["passed"], meter.result())
            fixture.observer.close()


if __name__ == "__main__": unittest.main()

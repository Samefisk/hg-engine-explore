"""Host-authored binding replay controls, not captured game proof."""
from copy import deepcopy
from pathlib import Path
import re
import unittest

from tools.overworld.devtools_binding_measurement import BindingMeasurement, EVENTS


def actor_fixture():
    handle = dict(value=65536, slot=0, generation=1, fieldEpoch=2,
                  mapGeneration=4, encounterGeneration=3)
    source = dict(object=0x02010000, active=1, species=19, form=0, level=5,
                  personality=12345, object_id=224, map_id=33, encounter_generation=3)
    engine = dict(pointer=0x02010000, in_manager=True, active=True,
        object_manager=0x02020000, current_manager=0x02020000, object_id=224,
        spawn_object_id=224, object_map_id=33, spawn_map_id=33, current_map_id=33,
        encounter_generation=3, script_id=2074,
        id_lookup=dict(status="complete", pointer_matches=True, eligible_count=1,
                       first_active_pointer=0x02010000))
    return dict(active=True, species=19, form=0, level=5, role="WILD", subjectIdentity=12345,
        handle=handle, presentationAttached=True, presentationState=7, identityVerified=True,
        authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1,
        sourceIdentity=source, engineIdentity=engine,
        engineObject=dict(flags=1, x=5, y=6, pos_x=360448, pos_y=0, pos_z=425984),
        motionKind="NONE", motionPhase="IDLE", motionElapsed=0, motionDuration=0,
        origin=dict(x=5, y=6), target=dict(x=5, y=6), logical=dict(x=5, y=6),
        commitSequence=40, reservationId=0, inputOwnership=0)


def fixture():
    owner = dict(fieldEpoch=2, mapGeneration=4, mapId=33)
    actor = actor_fixture()
    rows = []
    def sample(index, events=(), *, native_sequence=1):
        return (dict(frame=100+index, actorFrame=1000+index, nativeCycle=2000+index*2,
            prepared=False, fieldAvailable=True, observationBoundary="main-task-queue-completion",
            context=deepcopy(owner), actors=[deepcopy(actor)],
            nativeObservation=dict(installedBeforeBoot=True, coverageComplete=True, eventsDropped=0,
                profilesEvicted=0, pendingUnframedEvents=0, error=None, sequence=native_sequence)), list(events))
    rows.append(sample(0, native_sequence=0))
    receipt = dict(observation="actor-binding-context", sequence=1, setupMode="normal",
        status="observed", readError=None, boundary="public-getContext-return",
        entryActorFrame=1000, returnActorFrame=1000, entryNativeCycle=2001, returnNativeCycle=2001,
        returnValue=(4 << 16) | 2, packedContext=(4 << 16) | 2,
        ownerContext=deepcopy(owner), residentContext=deepcopy(owner), returnMatchesResident=True,
        fieldPointer=0x02080000, fieldLifecycle=dict(authenticated=True, reason=None, fieldReady=1,
            controlPointer=0x02080100, managerPointer=0x02080200, managerExecState=2, managerProcState=0),
        candidates=[dict(slot=0, publicSubject=deepcopy(actor), sourceIdentity=deepcopy(actor["sourceIdentity"]),
            engineIdentity=deepcopy(actor["engineIdentity"]), engineObject=deepcopy(actor["engineObject"]),
            identityChecks=dict(native=True), readError=None)])
    rows.append(sample(1, [dict(frame=101, kind="native-observation", data=receipt)]))
    def event(index, sequence, name, a, b):
        return dict(frame=100+index, kind="native", data=dict(traceStream=1, sequence=sequence,
            actorFrame=1000+index, actorHandle=actor["handle"]["value"],
            actor={key:value for key,value in actor["handle"].items() if key != "value"},
            event=name, reason="OK", valueA=a, valueB=b))
    actor.update(motionKind="WALK", motionPhase="MOVING", motionElapsed=0, motionDuration=2,
                 target=dict(x=6, y=6), reservationId=9, inputOwnership=1)
    rows.append(sample(2, [event(2, 1, "MOTION_STARTED", 1, 2)]))
    actor["motionElapsed"] = 1
    rows.append(sample(3))
    actor.update(motionKind="NONE", motionPhase="IDLE", motionElapsed=2, commitSequence=41,
                 logical=dict(x=6, y=6), reservationId=0, inputOwnership=0)
    actor["engineObject"].update(x=6, pos_x=425984)
    rows.append(sample(4, [event(4, 2, "LOGICAL_COMMIT", 41, 1),
                          event(4, 3, "MOTION_FINISHED", 41, 1),
                          event(4, 4, "CONTROL_RETURNED", 0, 41)]))
    return rows


def replay(rows, **kwargs):
    meter = BindingMeasurement(**kwargs)
    for snapshot, events in rows:
        meter.observe(snapshot, events)
    return meter


class BindingMeasurementTests(unittest.TestCase):
    def test_native_movement_and_vanish_flags_match_the_project_header(self):
        header = (Path(__file__).resolve().parents[2] / "include/map_events_internal.h").read_text()
        def bit(name):
            match = re.search(r"(?:#define\s+" + name + r"\s+|\b" + name + r"\s*=\s*)"
                              r"\(\s*1\s*<<\s*(\d+)\s*\)", header)
            self.assertIsNotNone(match, name)
            return 1 << int(match[1])
        active, movement, vanish = (bit(name) for name in
            ("MAPOBJECTFLAG_ACTIVE", "MAPOBJECTFLAG_SINGLE_MOVEMENT", "BIT_VANISH"))
        self.assertEqual((active, movement, vanish), (1, 2, 512))
        for flags, expected in ((active, True), (active | movement, True),
                                (active | vanish, False), (active | movement | vanish, False),
                                (movement, False)):
            rows = fixture()
            for snapshot, events in rows:
                for actor in snapshot["actors"]:
                    actor["engineObject"]["flags"] = flags
                for event in events:
                    if event["kind"] == "native-observation":
                        for candidate in event["data"]["candidates"]:
                            candidate["engineObject"]["flags"] = flags
            with self.subTest(flags=flags):
                self.assertEqual(replay(rows).finish()["passed"], expected)

    def test_existing_motion_terminal_is_uncredited_and_exact(self):
        for phase in ("MOVING", "SETTLING"):
            rows = fixture()
            actor = rows[1][1][0]["data"]["candidates"][0]["publicSubject"]
            actor.update(motionKind="HOP", motionPhase=phase, motionDuration=2,
                         commitSequence=40 if phase == "SETTLING" else 39)
            rows[1][0]["actors"][0] = deepcopy(actor)
            prefix = []
            for original in rows[-1][1][1 if phase == "SETTLING" else 0:]:
                event = deepcopy(original); event["frame"] = 102
                data = event["data"]; data["actorFrame"] = 1002
                data["valueB" if data["event"] == "CONTROL_RETURNED" else "valueA"] = 40
                if data["event"] != "CONTROL_RETURNED": data["valueB"] = 2
                prefix.append(event)
            rows[2][1][:0] = prefix
            sequence = 0
            for _, events in rows:
                for event in events:
                    if event["kind"] == "native":
                        sequence += 1; event["data"]["sequence"] = sequence
            with self.subTest(phase=phase):
                meter = replay(rows)
                self.assertTrue(meter.finish()["passed"], meter.result())
                self.assertEqual(len(meter.result()["lifecycleEvents"]), 4)
                self.assertEqual(meter.result()["lifecycleEvents"][0]["data"]["valueA"], 1)

    def test_same_frame_start_is_a_complete_uncredited_prefix(self):
        rows = fixture()
        # Bind while idle at actor frame1002; ordering against this frame's
        # subsequent start is unknown. Its full terminal must not earn proof.
        rows[1][0]["actorFrame"] = 1002
        rows[1][1][0]["data"].update(returnActorFrame=1002)
        first = replay(rows)
        self.assertFalse(first.result()["ready"])
        self.assertEqual(first.result()["failures"], [])
        self.assertEqual(first.result()["lifecycleEvents"], [])
        later = deepcopy(rows[2:])
        for snapshot, events in later:
            snapshot["frame"] += 3; snapshot["actorFrame"] += 3; snapshot["nativeCycle"] += 6
            actor = snapshot["actors"][0]
            actor["commitSequence"] += 1
            for key in ("origin", "target", "logical"): actor[key]["x"] += 1
            actor["engineObject"]["x"] += 1; actor["engineObject"]["pos_x"] += 65536
            for event in events:
                event["frame"] += 3; event["data"]["actorFrame"] += 3; event["data"]["sequence"] += 4
                if event["data"]["event"] != "MOTION_STARTED":
                    event["data"]["valueB" if event["data"]["event"] == "CONTROL_RETURNED" else "valueA"] += 1
            first.observe(snapshot, events)
        self.assertTrue(first.finish()["passed"], first.result())
        self.assertEqual(first.result()["lifecycleEvents"][0]["frame"], 105)

    def test_native_baseline_and_wild_slot_six_remain_valid(self):
        rows = fixture()
        for snapshot, events in rows:
            snapshot["nativeObservation"]["sequence"] += 500
            actors = snapshot["actors"]
            for event in events:
                data = event["data"]
                if event["kind"] == "native-observation":
                    data["sequence"] += 500
                    candidate = data["candidates"][0]; candidate["slot"] = 6
                    actors = actors + [candidate["publicSubject"]]
                    candidate["sourceIdentity"]["object_id"] = 230
                    candidate["engineIdentity"].update(object_id=230, spawn_object_id=230)
                elif event["kind"] == "native":
                    data["actor"]["slot"] = 6; data["actorHandle"] = 65542
            for actor in actors:
                actor["handle"].update(slot=6, value=65542)
                actor["sourceIdentity"]["object_id"] = 230
                actor["engineIdentity"].update(object_id=230, spawn_object_id=230)
        result = replay(rows).finish()
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["subject"]["handle"]["slot"], 6)

    def test_exact_binding_and_walk_retains_only_three_original_measurements(self):
        rows = fixture(); before = deepcopy(rows)
        meter = replay(rows)
        self.assertTrue(meter.result()["ready"], meter.result())
        self.assertFalse(meter.result()["passed"])
        result = meter.finish()
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["measurements"], {"binding-live-subject-count":1,
            "binding-owner-context-mismatch-count":0, "binding-identity-failure-count":0})
        self.assertEqual([event["data"]["event"] for event in result["lifecycleEvents"]], list(EVENTS))
        self.assertEqual(result["observedFrames"], 4)
        self.assertEqual(result["nativeCycles"], 8)
        self.assertEqual(result["identitySamples"], 4)
        self.assertEqual(rows, before)
        result["subject"]["species"] = 165
        self.assertEqual(meter.result()["subject"]["species"], 19)

    def test_no_subject_or_context_cannot_pass(self):
        for fault in ("no-actor", "no-receipt", "hidden", "wrong-species", "wrong-role"):
            rows = fixture()
            for snapshot, events in rows:
                if fault == "no-actor": snapshot["actors"] = []
                if fault == "no-receipt":
                    events[:] = [event for event in events if event["kind"] != "native-observation"]
                    snapshot["nativeObservation"]["sequence"] = 0
            candidate = rows[1][1][0]["data"]["candidates"][0] if fault != "no-receipt" else None
            if fault == "no-actor": rows[1][1][0]["data"]["candidates"] = []
            elif fault == "hidden": candidate["publicSubject"]["presentationState"] = 3
            elif fault == "wrong-species": candidate["publicSubject"]["species"] = 165
            elif fault == "wrong-role": candidate["publicSubject"]["role"] = "FOLLOWER"
            with self.subTest(fault=fault): self.assertFalse(replay(rows).finish()["passed"])

    def test_bad_first_candidate_is_not_filtered_to_a_good_replacement(self):
        rows = fixture(); data = rows[1][1][0]["data"]
        other = deepcopy(data["candidates"][0]); other["slot"] = 1
        other["publicSubject"]["handle"].update(slot=1, value=65537)
        data["candidates"].append(other)
        data["candidates"][0]["publicSubject"]["handle"]["mapGeneration"] = 3
        result = replay(rows).finish()
        self.assertFalse(result["passed"])
        self.assertEqual(result["measurements"]["binding-owner-context-mismatch-count"], 1)
        self.assertIn("same-return owner context", result["failures"][0]["detail"])

    def test_same_return_owner_fields_are_independently_required(self):
        for fault in ("owner", "resident", "flag", "return", "field", "unknown", "late-cycle", "stale-cycle", "late-frame", "stale-frame"):
            rows = fixture(); data = rows[1][1][0]["data"]
            if fault == "owner": data["ownerContext"]["mapGeneration"] += 1
            elif fault == "resident": data["residentContext"]["mapGeneration"] += 1
            elif fault == "flag": data["returnMatchesResident"] = False
            elif fault == "return": data["returnValue"] += 1
            elif fault == "field": data["fieldLifecycle"]["authenticated"] = False
            elif fault == "unknown": data["status"] = "unknown"
            elif fault == "late-cycle": data["returnNativeCycle"] = 2003
            elif fault == "stale-cycle": data["entryNativeCycle"] = data["returnNativeCycle"] = 1999
            elif fault == "late-frame": data["returnActorFrame"] = 1002
            else: data["entryActorFrame"] = data["returnActorFrame"] = 999
            with self.subTest(fault=fault): self.assertFalse(replay(rows).finish()["passed"])

    def test_every_native_identity_field_is_checked(self):
        for container, key, value in (
            ("sourceIdentity", "personality", 999), ("sourceIdentity", "form", 1),
            ("sourceIdentity", "level", 9), ("sourceIdentity", "active", 2),
            ("sourceIdentity", "map_id", 99), ("engineIdentity", "script_id", 123),
            ("engineIdentity", "object_id", 225), ("engineIdentity", "object_manager", 0x02030000),
            ("engineIdentity", "pointer", 0x0201012C), ("engineIdentity", "in_manager", False),
            ("engineIdentity", "encounter_generation", 4), ("engineObject", "flags", 0),
            ("publicSubject", "presentationGeneration", 0), ("identityChecks", "native", False),
        ):
            rows = fixture(); candidate = rows[1][1][0]["data"]["candidates"][0]
            candidate[container][key] = value
            with self.subTest(container=container,key=key):
                result = replay(rows).finish()
                self.assertFalse(result["passed"])
                self.assertEqual(result["measurements"]["binding-identity-failure-count"], 1)

    def test_missing_each_required_event_fails_even_with_repaired_sequences(self):
        for name in EVENTS:
            rows = fixture(); sequence = 0
            for _, events in rows:
                events[:] = [event for event in events if event["data"].get("event") != name]
                for event in events:
                    if event["kind"] == "native":
                        sequence += 1; event["data"]["sequence"] = sequence
            with self.subTest(name=name): self.assertFalse(replay(rows).finish()["passed"])

    def test_wrong_actor_cancel_order_kind_commit_and_stream_fail(self):
        for fault in ("actor", "cancel", "order", "kind", "commit", "stream", "boolean"):
            rows = fixture(); event = rows[-1][1][0]["data"]
            if fault == "actor": event["actor"]["encounterGeneration"] += 1
            elif fault == "cancel": event["event"] = "MOTION_CANCELED"
            elif fault == "order": event["event"] = "MOTION_FINISHED"
            elif fault == "kind": event["valueB"] = 2
            elif fault == "commit": event["valueA"] += 1
            elif fault == "stream": event.update(traceStream=2, sequence=1)
            else: rows[2][1][0]["data"]["valueA"] = True
            with self.subTest(fault=fault): self.assertFalse(replay(rows).finish()["passed"])

    def test_coverage_and_frame_loss_fail(self):
        for fault in ("watermark", "native-sequence", "trace-sequence", "dropped", "prepared", "frame", "trace-status"):
            rows = fixture()
            if fault == "watermark": rows[1][0]["nativeObservation"]["sequence"] = 2
            elif fault == "native-sequence": rows[1][1][0]["data"]["sequence"] = 2
            elif fault == "trace-sequence": rows[-1][1][0]["data"]["sequence"] = 5
            elif fault == "dropped": rows[1][0]["nativeObservation"]["eventsDropped"] = 1
            elif fault == "prepared": rows[1][0]["prepared"] = True
            elif fault == "frame": del rows[3]
            else: rows[-1][1].append(dict(frame=104,kind="trace-status",data=dict(code="unread-events-lost",coverageComplete=False)))
            with self.subTest(fault=fault): self.assertFalse(replay(rows).finish()["passed"])

    def test_ready_does_not_disable_identity_or_context_checks(self):
        for fault in ("missing", "personality", "generation", "context"):
            rows = fixture(); final = deepcopy(rows[-1][0])
            final.update(frame=105, actorFrame=1005, nativeCycle=2010)
            if fault == "missing": final["actors"] = []
            elif fault == "personality": final["actors"][0]["subjectIdentity"] += 1
            elif fault == "generation": final["actors"][0]["presentationGeneration"] += 1
            else: final["context"]["mapGeneration"] += 1
            meter = replay(rows); self.assertTrue(meter.result()["ready"])
            meter.observe(final, [])
            with self.subTest(fault=fault): self.assertFalse(meter.finish()["passed"])

    def test_frame_and_native_cycle_caps_are_separate_and_bounded(self):
        self.assertTrue(replay(fixture(),max_frames=4,max_native_cycles=8).finish()["passed"])
        self.assertFalse(replay(fixture(),max_frames=3).finish()["passed"])
        self.assertFalse(replay(fixture(),max_native_cycles=7).finish()["passed"])
        for kwargs in (dict(max_frames=901),dict(max_native_cycles=4097),dict(max_frames=True)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): BindingMeasurement(**kwargs)


if __name__ == "__main__":
    unittest.main()

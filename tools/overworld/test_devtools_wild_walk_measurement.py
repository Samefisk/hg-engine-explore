"""Synthetic memory data checks. These do not grant live Wild Walk proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_wild_walk_measurement import WildWalkMeasurement
from tools.overworld.devtools_wild_walk_observer import ENGINE
from tools.overworld.test_devtools_acceleration_measurement import fixture


def wild_fixture(*, pause=32, delta=(1,0), duration=4, startup_noop=False):
    baseline, reset, travel = fixture(role="WILD", species=19, durations=(duration,),
        counters=(0,), speeds=(4,), base=4, fastest=4, delta=delta)
    subject = reset["subject"]
    reader = dict(armed=True, closed=False, failure=None, acceptedProof=False, guestMemoryWrites=0,
        subject=deepcopy(subject), startFrame=baseline["frame"], counts={"clear":0})
    rows = deepcopy(travel[:-1])
    terminal, events = deepcopy(travel[-1])
    finish_events = [e for e in events if e.get("data",{}).get("event") in ("MOTION_FINISHED","CONTROL_RETURNED")]
    events = [e for e in events if e not in finish_events and e["kind"] != "native-observation"]
    actor = terminal["actors"][0]
    if pause: actor.update(motionPhase="SETTLING",motionKind="WALK")
    current = dict(subject=deepcopy(subject), publicSubject=deepcopy(actor), sourceIdentity=deepcopy(actor["sourceIdentity"]),
        engineIdentity={k:actor["engineIdentity"].get(k) for k in ENGINE}, worldContext=deepcopy(terminal["context"]),
        statePointer=0x02040000,runtimePointer=0x02060000,objectPointer=actor["engineIdentity"]["pointer"],slot=actor["handle"]["slot"])
    current["worldContext"]["statePointer"] = current["statePointer"]
    clear = dict(frame=terminal["frame"],kind="native-observation", data=dict(observation="wild-walk-clear",subject=deepcopy(subject),
        before=dict(current=deepcopy(current),active=1,mode=1,objectFlags=0x12005),
        after=dict(current=deepcopy(current),active=0,mode=0,objectFlags=1)))
    events.append(clear)
    if not pause: events.extend(finish_events)
    rows.append((terminal,events))
    for tick in range(1,pause+1):
        snapshot = deepcopy(terminal)
        snapshot["frame"] += tick; snapshot["actorFrame"] += tick; snapshot["nativeCycle"] += tick*2
        ending = []
        if tick == pause:
            snapshot["actors"][0].update(motionPhase="IDLE",motionKind="NONE")
            ending = deepcopy(finish_events)
        rows.append((snapshot,ending))
    native_seq = baseline["nativeObservation"]["sequence"]
    trace_seq = 0
    cleared = 0
    if startup_noop:
        noop = deepcopy(clear)
        current = deepcopy(noop["data"]["before"]["current"])
        current["publicSubject"] = deepcopy(baseline["actors"][0])
        endpoint = dict(current=current, active=0, mode=0, objectFlags=1066017)
        noop["data"].update(before=deepcopy(endpoint), after=deepcopy(endpoint))
        rows[0][1].insert(0, noop)
    for snapshot, events in rows:
        a = snapshot["actors"][0]
        if a["motionPhase"] == "MOVING" and a["motionElapsed"] >= (duration+1)//2:
            a["logical"] = deepcopy(a["target"])
        for e in events:
            e["frame"] = snapshot["frame"]
            if e["kind"] == "native":
                trace_seq += 1; e["data"].update(sequence=trace_seq,actorFrame=snapshot["actorFrame"])
            elif e["kind"] == "native-observation":
                native_seq += 1
                e["data"].update(sequence=native_seq,entryActorFrame=snapshot["actorFrame"],returnActorFrame=snapshot["actorFrame"],
                    entryNativeCycle=snapshot["nativeCycle"],returnNativeCycle=snapshot["nativeCycle"])
                cleared += 1
        snapshot["nativeObservation"]["sequence"] = native_seq
        snapshot["wildWalk"] = dict(reader, counts={"clear":int(cleared)}, latestCompletedInput=dict(frame=snapshot["frame"],
            nativeCycle=snapshot["nativeCycle"],heldKeys=0,newKeys=0))
    return baseline,subject,reader,rows


def replay(data):
    initial,subject,receipt,rows = data
    meter = WildWalkMeasurement(1200)
    meter.arm(subject,initial,receipt)
    for snapshot,events in rows:
        meter.observe(snapshot,events)
        if meter.failures: break
    return meter


class WildWalkMeasurementTests(unittest.TestCase):
    def test_startup_noop_is_retained_not_terminal_clear(self):
        data = wild_fixture(startup_noop=True)
        meter = replay(data)
        self.assertEqual(meter.failures, [])
        self.assertEqual(len(meter.idle_noop_clears), 1)
        self.assertEqual(len(meter.clears), 1)
        self.assertTrue(meter.close(dict(data[2],closed=True,counts={"clear":2}),data[3][-1][0])["passed"])
        data = wild_fixture(startup_noop=True)
        for snapshot, events in data[3]:
            for event in events:
                if event["kind"] == "native-observation" and event["data"]["before"]["active"] == 1:
                    event["data"]["observation"] = "other-native-receipt"
            snapshot["wildWalk"]["counts"]["clear"] = 1
        self.assertIn("missing native wild Walk clear",replay(data).failures)

    def test_changed_or_late_idle_clear_is_not_excluded(self):
        for fault in ("changed","logical","commit","phase","kind","flags","late"):
            data = wild_fixture(startup_noop=True)
            noop = data[3][0][1][0]
            if fault == "changed": noop["data"]["after"]["objectFlags"] += 2
            elif fault == "late":
                data[3][0][1].remove(noop)
                first, _ = data[3][0]
                first["nativeObservation"]["sequence"] -= 1
                first["wildWalk"]["counts"]["clear"] = 0
                second, events = data[3][1]
                noop["frame"] = second["frame"]
                noop["data"].update(entryNativeCycle=second["nativeCycle"],returnNativeCycle=second["nativeCycle"])
                events.insert(0,noop)
            else:
                for side in ("before","after"):
                    endpoint = noop["data"][side]; public = endpoint["current"]["publicSubject"]
                    if fault == "logical": public["logical"]["x"] += 1
                    elif fault == "commit": public["commitSequence"] += 1
                    elif fault == "phase": public["motionPhase"] = "MOVING"
                    elif fault == "kind": public["motionKind"] = "WALK"
                    elif fault == "flags": endpoint["objectFlags"] |= 4
            with self.subTest(fault=fault): self.assertTrue(replay(data).failures)

    def test_four_frames_and_native_clear_then_real_pause(self):
        data = wild_fixture()
        meter = replay(data)
        self.assertEqual(meter.failures, [])
        self.assertTrue(meter.ready)
        self.assertEqual(meter.motion["pauseFrames"],32)
        self.assertEqual([s["elapsed"] for s in meter.motion["samples"]],[0,1,2,3])
        self.assertEqual(meter.motion["travelEnd"]["elapsed"],4)
        self.assertEqual(len(meter.clears),1)
        receipt = dict(data[2],closed=True,counts={"clear":1})
        self.assertTrue(meter.close(receipt,data[3][-1][0])["passed"])

    def test_all_unit_directions(self):
        for delta in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)):
            with self.subTest(delta=delta): self.assertEqual(replay(wild_fixture(delta=delta)).failures,[])

    def test_invalid_duration_rejected(self):
        self.assertIn("wild Walk requires exact four-frame travel",replay(wild_fixture(duration=8)).failures)

    def test_clear_is_not_inferred_from_idle(self):
        data = wild_fixture()
        for s,events in data[3]:
            events[:] = [e for e in events if e["kind"] != "native-observation"]
            s["nativeObservation"]["sequence"] = data[0]["nativeObservation"]["sequence"]
            s["wildWalk"]["counts"]["clear"] = 0
        self.assertIn("missing native wild Walk clear",replay(data).failures)

    def test_faults_do_not_pass(self):
        for fault in ("identity","render","elapsed","facing","held","new","active","mode","flags","duplicate","missing-finish","wrong-slot","world","clear-commit","reader"):
            data = wild_fixture(); rows = data[3]
            clear = next(e for _,events in rows for e in events if e["kind"] == "native-observation")
            if fault == "identity": rows[0][0]["actors"][0]["authorityGeneration"] += 1
            elif fault == "render": rows[1][0]["actors"][0]["engineObject"]["pos_x"] += 1
            elif fault == "elapsed": rows[1][0]["actors"][0]["motionElapsed"] += 1
            elif fault == "facing": rows[-2][0]["actors"][0]["engineObject"]["facing"] ^= 1
            elif fault in ("held","new"): rows[0][0]["wildWalk"]["latestCompletedInput"][fault+"Keys"] = 16
            elif fault in ("active","mode"): clear["data"]["after"][fault] = 1
            elif fault == "flags": clear["data"]["after"]["objectFlags"] |= 4
            elif fault == "wrong-slot": clear["data"]["after"]["current"]["slot"] += 1
            elif fault == "world": clear["data"]["after"]["current"]["worldContext"]["mapId"] += 1
            elif fault == "clear-commit":
                for side in ("before","after"): clear["data"][side]["current"]["publicSubject"]["commitSequence"] -= 1
            elif fault == "missing-finish":
                for _,events in rows:
                    for e in events:
                        if e["data"].get("event") == "MOTION_FINISHED": e["data"]["event"] = "WORLD_EFFECT"
            elif fault == "reader": rows[0][0].pop("wildWalk")
            else:
                duplicate=deepcopy(clear); duplicate["data"]["sequence"]+=1
                next(events for _,events in rows if clear in events).append(duplicate)
            with self.subTest(fault=fault): self.assertTrue(replay(data).failures)

    def test_no_close_is_not_pass(self):
        self.assertFalse(replay(wild_fixture()).finish()["passed"])

    def test_clear_before_commit_rejected(self):
        data = wild_fixture()
        clear = next(e for _,events in data[3] for e in events if e["kind"] == "native-observation")
        clear["data"]["entryActorFrame"] -= 1
        self.assertIn("wild Walk clear outside terminal window",replay(data).failures)

    def test_zero_loss_wrap_only(self):
        for bad in (False, True):
            data = wild_fixture()
            s,events = data[3][1]
            events.append(dict(frame=s["frame"],kind="trace-status",data=dict(code="ring-overwrite",traceStream=1,count=1,
                diagnosticOnly=True,unreadEventsLost=int(bad),coverageComplete=not bad)))
            with self.subTest(bad=bad): self.assertEqual(bool(replay(data).failures),bad)


if __name__ == "__main__": unittest.main()

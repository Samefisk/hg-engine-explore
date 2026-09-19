"""Host evaluator controls, plus optional replay of retained diagnostic memory data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_corner_measurement import CornerMeasurement
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_acceleration_measurement import fixture as actor_fixture


def fixture():
    """Synthetic evaluator fixture; never a substitute for native recorder proof."""
    baseline, _, _ = actor_fixture(role="MOUNTED", species=155, durations=())
    actor = baseline["actors"][0]
    actor.update(logical=dict(x=588, y=406), motionKind="NONE", motionPhase="IDLE", reservationId=0)
    baseline["player"].update(x=588, y=406)
    baseline["selector"] = dict(heldKeys=0, rawHeld=0, simulatedKeys=0)
    baseline["nativeObservation"]["sequence"] = 0
    subject = select_current_actor(baseline, actor)
    raw = bytearray(104)
    struct.pack_into("<II", raw, 0, 0x02010000, 0x02020000)
    raw[27] = 1
    struct.pack_into("<I", raw, 96, 1)
    before = dict(origin=[588, 406], frame=baseline["frame"], avatar=0x02030000,
                  player=actor["engineIdentity"]["anchorPointer"], mountStateHex=raw.hex())
    query = dict(completed=True, prepared=True, acceptedProof=False, batchAdvancedFrames=0,
        scope="prepared-mounted-corner-query", subject=deepcopy(subject), before=before, after=deepcopy(before),
        cardinals=[dict(direction=d, result=int(d == 1), open=d != 1) for d in range(4)],
        diagonals=[dict(direction=d, target=[588+dx, 406+dy], result=1, destinationOpen=True,
            sideDirections=[v,h], blockedSides=int(v == 1), oneSideCorner=v == 1)
            for d,dx,dy,v,h in ((4,-1,-1,0,2),(5,1,-1,0,3),(6,-1,1,1,2),(7,1,1,1,3))])
    reader = dict(armed=True, closed=False, failure=None, acceptedProof=False, guestMemoryWrites=0,
                  subject=deepcopy(subject), startFrame=baseline["frame"],
                  calls=[], counts=dict(strict=0, collision=0, landing=0))
    baseline["walkCorner"] = deepcopy(reader)
    current = dict(subject=deepcopy(subject), publicSubject=deepcopy(actor),
        sourceIdentity=deepcopy(actor["sourceIdentity"]), engineIdentity=deepcopy(actor["engineIdentity"]),
        playerPointer=before["player"], mountPointer=actor["engineIdentity"]["pointer"],
        worldContext=deepcopy(baseline["context"]))
    clock = dict(nativeCycle=baseline["nativeCycle"]+2, actorFrame=baseline.get("actorFrame", 0)+1)
    child = dict(direction=1, normalReturn=True, rawMask=1, returnValue=1, before=deepcopy(current),
        profileHex=raw[8:80].hex(), input=dict(heldKeys=160, rawHeld=160, simulatedKeys=0),
        entryClock=clock, returnClock=clock)
    strict = dict(observation="walk-corner-strict", sequence=1, before=current,
        completedFrame=baseline["frame"], entryNativeCycle=clock["nativeCycle"], returnNativeCycle=clock["nativeCycle"],
        direction=6, origin=dict(x=588,y=406), target=dict(x=587,y=407), normalReturn=True, returnValue=0,
        input=deepcopy(child["input"]), profileHex=raw[8:80].hex(), profile19=1,
        mountBinding=dict(bindingHex=raw[80:96].hex(), sessionGeneration=1,
                          fieldPointer=0x02010000, surfacePointer=0x02020000),
        avatarPointer=before["avatar"], playerPointer=before["player"], collisions=[child], landings=[],
        entryClock=clock, returnClock=clock)
    rows = []
    seq = 0
    def trace(frame, name, reason="OK", a=1, b=1):
        nonlocal seq
        seq += 1
        return dict(frame=frame, kind="native", data=dict(sequence=seq, traceStream=1,
            actorHandle=actor["handle"]["value"], actor={k:v for k,v in actor["handle"].items() if k != "value"},
            event=name, reason=reason, valueA=a, valueB=b))
    for offset, mask in enumerate((160, 0, 32, 0, 0, 0, 0, 0), 1):
        snapshot = deepcopy(baseline)
        snapshot["frame"] += offset
        snapshot["nativeCycle"] += offset*2
        snapshot["nativeObservation"]["sequence"] = 1
        snapshot["walkCorner"].update(calls=[deepcopy(strict)], counts=dict(strict=1,collision=1,landing=0))
        snapshot["selector"].update(heldKeys=mask, rawHeld=mask)
        events = []
        f = snapshot["frame"]
        if offset == 1:
            events = [dict(frame=f,kind="native-observation",data=deepcopy(strict)),
                      trace(f,"CANDIDATE_REJECTED","REJECTED_SIDE_TILE")]
        if 3 <= offset < 7:
            snapshot["actors"][0].update(motionKind="WALK",motionPhase="MOVING", reservationId=1)
        if offset == 3:
            events = [trace(f,"MOTION_STARTED")]
        if offset >= 7:
            snapshot["actors"][0].update(logical=dict(x=587,y=406), commitSequence=actor["commitSequence"]+1)
        if offset == 7:
            events = [trace(f,name) for name in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED")]
        rows.append((snapshot,events))
    return baseline, subject, query, reader, rows


def replay_fixture(mutate=None):
    baseline, subject, query, reader, rows = fixture()
    if mutate:
        mutate(baseline, subject, query, reader, rows)
    meter = CornerMeasurement(50)
    meter.probe(query, baseline)
    meter.arm(subject, baseline, reader)
    for index, (snapshot,events) in enumerate(rows):
        meter.observe(snapshot, events)
        if index == 1 and not meter.failures:
            meter.begin_recovery(snapshot)
    start = baseline["frame"]
    for count, keys in ((1,["DOWN","LEFT"]),(1,[]),(1,["LEFT"]),(5,[])):
        meter.command(dict(op="step",args=dict(frames=count,keys=keys),startFrame=start),
                      dict(requestedGameFrames=count,completedGameFrames=count,observedFieldFrames=count))
        start += count
    closed = deepcopy(rows[-1][0]["walkCorner"])
    closed["closed"] = True
    if not meter.failures:
        meter.close(closed, rows[-1][0])
    else:
        meter.finish()
    return meter, reader, rows


def replay_recording(path):
    """Read-only offline diagnostic replay; no synthetic semantic additions."""
    path = Path(path)
    raw = json.loads(path.read_text())
    def expand(data):
        if not data.get("detailsOmitted"):
            return data
        artifact = data["artifact"]
        content = (path.parent / Path(artifact["path"]).name).read_bytes()
        if hashlib.sha256(content).hexdigest() != artifact["sha256"]:
            raise ValueError("diagnostic artifact hash differs")
        return json.loads(content)
    queries = [json.loads(p.read_text()) for p in path.parent.glob("event-details-*.json")]
    query = next(q["receipt"] for q in queries if q.get("op") == "walk-corner.probe")
    first = raw["snapshots"][0]
    meter = CornerMeasurement(120)
    meter.probe(query, first)
    meter.arm(first["walkCorner"]["subject"], first, first["walkCorner"])
    events = [{**e,"data":expand(e["data"])} for e in raw["events"]]
    close = next(e for e in events if e["kind"] == "command" and e["data"].get("op") == "walk-corner.close")
    recovery = next(e["frame"] for e in events if e["kind"] == "command-request"
                    and e["data"].get("args", {}).get("keys") == ["UP"])
    for snapshot in raw["snapshots"][1:]:
        if snapshot["frame"] > close["frame"]:
            break
        frame_events = [e for e in events if e["frame"] == snapshot["frame"]
                        and e["kind"] in ("native", "native-observation", "trace-status")]
        meter.observe(snapshot, frame_events)
        for event in events:
            if event["frame"] == snapshot["frame"] and event["kind"] == "command" and event["data"].get("op") == "step":
                meter.command(event["data"],event["data"])
        if snapshot["frame"] == recovery:
            meter.begin_recovery(snapshot)
    meter.close(close["data"]["receipt"], meter.last)
    return meter.result()


class CornerTests(unittest.TestCase):
    def test_native_rejection_kind_and_raw_flags(self):
        for kind,raw,valid in (('candidate-flags',2,True),('bool',0,True),
            ('candidate-flags',0,False),('candidate-flags',4,False),('candidate-flags',32,False),
            ('candidate-flags',True,False),('bool',2,False),('unknown',0,False),(None,0,False)):
            def mutate(baseline,subject,query,reader,rows):
                for snapshot,events in rows:
                    for call in snapshot['walkCorner']['calls']:
                        call.update(returnKind=kind,rawReturnValue=raw)
                    for event in events:
                        if event['kind']=='native-observation' and event['data'].get('observation')=='walk-corner-strict':
                            event['data'].update(returnKind=kind,rawReturnValue=raw)
            meter,_,_=replay_fixture(mutate)
            with self.subTest(kind=kind,raw=raw):
                self.assertEqual(meter.result()['passed'],valid,meter.failures)
                if not valid:self.assertIn('corner raw rejection kind or flags differ',meter.failures)

    def test_exact_seven_rows_and_no_acceptance(self):
        meter, _, _ = replay_fixture()
        self.assertEqual(meter.failures, [])
        self.assertTrue(meter.result()["passed"])
        self.assertFalse(meter.result()["acceptedProof"])
        self.assertEqual(sum(map(len,meter.result()["proofEvidence"].values())),7)

    def test_missing_side_event_fails_even_with_all_seven_rows(self):
        def remove(*args):
            rows = args[-1]
            rows[0][1].pop()
            for _,events in rows:
                for event in events:
                    if event["kind"] == "native":
                        event["data"]["sequence"] -= 1
        meter, _, _ = replay_fixture(remove)
        self.assertFalse(meter.result()["passed"])
        self.assertIn("missing exact CANDIDATE_REJECTED REJECTED_SIDE_TILE",meter.failures)
        self.assertTrue(all(r["actual"] == r["expected"] for rows in meter.result()["proofEvidence"].values() for r in rows))

    def test_missing_required_event_controls(self):
        for name in ("MOTION_STARTED","LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"):
            def remove(*args):
                for _,events in args[-1]:
                    events[:] = [e for e in events if e["data"].get("event") != name]
            meter, _, _ = replay_fixture(remove)
            self.assertFalse(meter.result()["passed"],name)

    def test_wrong_subject_frame_input_mask_and_duplicate_controls(self):
        mutations = [
            lambda rows: rows[0][0]["actors"][0].update(species=19),
            lambda rows: rows[0][0].update(frame=999),
            lambda rows: rows[0][0]["selector"].update(simulatedKeys=160),
            lambda rows: rows[0][0]["player"].update(pos_x=0),
            lambda rows: rows[0][1][0]["data"]["collisions"][0].update(rawMask=0),
            lambda rows: rows[0][1][0]["data"]["before"]["engineIdentity"].update(pointer=123),
            lambda rows: rows[0][1][0]["data"].update(returnValue=1),
            lambda rows: rows[-1][0]["actors"][0].update(commitSequence=2),
            lambda rows: rows[-1][1].append(deepcopy(rows[-2][1][-1])),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                meter, _, _ = replay_fixture(lambda *args: mutation(args[-1]))
                self.assertFalse(meter.result()["passed"])

    def test_unknown_and_closed_destination_fail_setup(self):
        for field, value in (("result",None),("result",0),("target",[0,0])):
            baseline, subject, query, reader, _ = fixture()
            query["diagonals"][2][field] = value
            with self.assertRaises(ValueError):
                CornerMeasurement(20).probe(query,baseline)

    def test_wrong_rejection_reason_and_duplicate_rejection(self):
        for duplicate in (False, True):
            def change(*args):
                events = args[-1][0][1]
                if duplicate:
                    events.append(deepcopy(events[-1]))
                else:
                    events[-1]["data"]["reason"] = "REJECTED_DESTINATION"
            meter, _, _ = replay_fixture(change)
            self.assertFalse(meter.result()["passed"])

    def test_chunked_commands_count_decision_episodes(self):
        meter, _, _ = replay_fixture()
        final = meter.commands.pop()
        meter.closed = False
        for frame in range(final["startFrame"], final["endFrame"]):
            meter.command(dict(op="step", args=dict(keys=[],frames=1), startFrame=frame),
                          dict(requestedGameFrames=1,completedGameFrames=1,observedFieldFrames=1))
        self.assertEqual(meter.failures, [])
        self.assertTrue(meter.ready)
        self.assertEqual(meter.result()["proofEvidence"]["natural-input"][0]["actual"], 2)

    def test_recovery_completion_can_report_missing_rejection(self):
        meter, _, _ = replay_fixture()
        self.assertTrue(meter.stage("recovery-complete"))
        meter.traces[:] = [e for e in meter.traces if e["data"]["event"] != "CANDIDATE_REJECTED"]
        self.assertTrue(meter.stage("recovery-complete"))
        self.assertFalse(meter.ready)

    def test_retained_diagnostic_does_not_fabricate_rejection(self):
        path = Path("build/overworld-devtools/session-36_ivc88/recording-b9eaffad42da.json")
        if not path.exists():
            self.skipTest("optional private diagnostic memory data is absent")
        result = replay_recording(path)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failures"], ["corner recovery is not the tested diagonal clear side",
                                              "missing exact CANDIDATE_REJECTED REJECTED_SIDE_TILE"])
        self.assertEqual(len(result["strictCalls"]),4)
        self.assertEqual(result["terminal"]["player"]["y"],405)


if __name__ == "__main__":
    unittest.main()

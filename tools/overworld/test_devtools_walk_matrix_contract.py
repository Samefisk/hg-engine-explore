"""Synthetic host controls, never game evidence, for the exact matrix contract."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_walk_matrix_contract import (
    CASES, DURATIONS, LIFECYCLE, validate_matrix, validate_motion,
)


def fixture(index=4):
    case = deepcopy(CASES[index])
    subject = dict(handle=dict(slot=6, generation=1), species=155, role="MOUNTED")
    reservation = index + 1
    ticks = []
    for elapsed in range(case["duration"]):
        before = dict(elapsed=elapsed, duration=case["duration"], phase="MOVING",
                      subject=deepcopy(subject), reservationId=reservation,
                      frame=100+elapsed, actorFrame=200+elapsed, nativeCycle=10000+elapsed*100)
        after = dict(deepcopy(before), elapsed=elapsed+1, nativeCycle=before["nativeCycle"]+10,
                     phase="COMMIT_PENDING" if elapsed+1 == case["duration"] else "MOVING")
        ticks.append(dict(before=before, after=after))
    events = [dict(event=event, reason="OK", subject=deepcopy(subject), sequence=i+1,
                   actorFrame=200 if i == 0 else 200+case["duration"],
                   frame=100 if i == 0 else 100+case["duration"], valueA=1, valueB=1)
              for i, event in enumerate(LIFECYCLE)]
    return dict(case=case, subject=subject, reservation=reservation, ticks=ticks, events=events)


class WalkMatrixContractTests(unittest.TestCase):
    def test_exact_cases_and_registry_vectors(self):
        self.assertEqual(DURATIONS, (*range(1, 33), *range(1, 33), 5))
        self.assertEqual([c["direction"] for c in CASES[:4]], [2,3,2,3])
        self.assertEqual([c["direction"] for c in CASES[32:36]], [4,7,4,7])
        self.assertEqual(CASES[-1], dict(index=64,duration=5,direction=4,keys=["UP","LEFT"],mode=2))
        result = validate_matrix([fixture(i) for i in range(65)],
            dict(before=[10,10],after=[10,10],mode="IDLE",pending=0))
        self.assertEqual(result["counts"]["durations"], list(DURATIONS))
        self.assertEqual(result["counts"]["elapsedCounts"], list(DURATIONS))
        self.assertEqual(result["elapsed"]["sequences"], [list(range(n)) for n in DURATIONS])

    def test_raw_elapsed_not_completed_index(self):
        motion = fixture(0)
        self.assertEqual(validate_motion(**motion)["sequence"], [0])
        motion["ticks"][0]["before"]["elapsed"] = 1
        with self.assertRaisesRegex(ValueError,"native elapsed"):
            validate_motion(**motion)

    def test_tick_faults(self):
        faults = (
            ("before","elapsed",1), ("after","elapsed",0),
            ("before","duration",4), ("after","subject",{}),
            ("after","reservationId",99), ("before","elapsed",False),
            ("before","phase","IDLE"), ("after","nativeCycle",1),
            ("after","frame",101), ("after","actorFrame",201),
        )
        for endpoint,key,value in faults:
            with self.subTest(endpoint=endpoint,key=key):
                motion=fixture();motion["ticks"][0][endpoint][key]=value
                with self.assertRaises(ValueError):validate_motion(**motion)
        for change in (lambda t:t.pop(), lambda t:t.reverse(), lambda t:t.append(deepcopy(t[-1]))):
            motion=fixture();change(motion["ticks"])
            with self.assertRaises(ValueError):validate_motion(**motion)

    def test_cadence_and_same_cycle_pair(self):
        motion=fixture();motion["ticks"][0]["after"]["nativeCycle"]=10000
        validate_motion(**motion)
        for key in ("frame","actorFrame","nativeCycle"):
            bad=deepcopy(motion)
            for endpoint in ("before","after"):
                bad["ticks"][1][endpoint][key]=bad["ticks"][0][endpoint][key]
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,"cadence"):
                validate_motion(**bad)

    def test_lifecycle_missing_duplicate_cancel_and_identity(self):
        for index in range(4):
            for duplicate in (False,True):
                motion=fixture()
                if duplicate:motion["events"].append(deepcopy(motion["events"][index]))
                else:motion["events"].pop(index)
                with self.assertRaisesRegex(ValueError,"lifecycle count"):
                    validate_motion(**motion)
        motion=fixture();motion["events"].append(dict(event="MOTION_CANCELED"))
        with self.assertRaisesRegex(ValueError,"canceled"):validate_motion(**motion)
        motion=fixture();motion["events"][1]["subject"]={}
        with self.assertRaisesRegex(ValueError,"identity"):validate_motion(**motion)
        motion=fixture();motion["events"].insert(1,dict(event="PATH_ADVANCED"))
        validate_motion(**motion)

    def test_matrix_missing_case_and_bad_gating(self):
        motions=[fixture(i) for i in range(65)]
        gate=dict(before=[10,10],after=[10,10],mode="IDLE",pending=0)
        with self.assertRaisesRegex(ValueError,"matrix count"):validate_matrix(motions[:-1],gate)
        for key,value in (("after",[11,10]),("mode","MOVING"),("pending",1)):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,"gating"):
                validate_matrix(motions,dict(gate,**{key:value}))

    def test_lifecycle_uses_actor_clock_and_keeps_delivery_order(self):
        motion=fixture()
        for event in motion['events']:
            event['frame']+=1000  # Delivery can be later; actor timestamps are unchanged.
        validate_motion(**motion)
        for index,field,value in ((0,'actorFrame',999),(1,'actorFrame',201),
                                  (2,'actorFrame',False),(2,'frame',0)):
            with self.subTest(index=index,field=field):
                bad=deepcopy(motion);bad['events'][index][field]=value
                with self.assertRaises(ValueError):validate_motion(**bad)

    def test_retained_two_cases_preserve_native_clock_domains(self):
        source=Path(__file__).resolve().parents[2]/(
            'build/overworld-devtools/session-2pzeigtv/recording-10d5d86b182e.json')
        if not source.exists():
            self.skipTest('optional two-case native diagnostic is absent')
        raw=json.loads(source.read_text())
        expanded=[]
        for event in raw['events']:
            data=event['data']
            if data.get('detailsOmitted'):
                artifact=data['artifact'];target=source.parent/Path(artifact['path']).name
                content=target.read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(),artifact['sha256'])
                data=json.loads(content)
            expanded.append(dict(event,data=data))
        ticks_by_reservation={}
        for event in expanded:
            data=event['data']
            if data.get('observation')!='walk-matrix-tick' or data['before']['phase']!='MOVING':continue
            pair={}
            for endpoint,clock,current in (('before','entryClock','beforeCurrent'),('after','returnClock','afterCurrent')):
                state=data[endpoint]
                pair[endpoint]=dict(elapsed=state['elapsed'],duration=state['plan']['duration'],phase=state['phase'],
                    subject=data[current]['subject'],reservationId=state['plan']['reservationId'],
                    frame=data['completedFrame'],**data[clock])
            ticks_by_reservation.setdefault(pair['before']['reservationId'],[]).append(pair)
        self.assertEqual(list(ticks_by_reservation),[22,23])
        lifecycle_groups=[]
        for event in expanded:
            data=event['data']
            if event['kind']!='native' or data.get('event') not in LIFECYCLE:continue
            if data['event']=='MOTION_STARTED':lifecycle_groups.append([])
            lifecycle_groups[-1].append((event['frame'],data))
        self.assertEqual(len(lifecycle_groups),2)
        for index,(reservation,ticks) in enumerate(ticks_by_reservation.items()):
            subject=ticks[0]['before']['subject'];events=[]
            for delivery,data in lifecycle_groups[index]:
                self.assertEqual(data['actorHandle'],subject['handle']['value'])
                for key,value in data['actor'].items():self.assertEqual(value,subject['handle'][key])
                events.append(dict(data,frame=delivery,subject=subject))
            motion=dict(case=deepcopy(CASES[index]),subject=subject,reservation=reservation,ticks=ticks,events=events)
            self.assertEqual(validate_motion(**motion)['sequence'],[0] if index==0 else [0,1])
            for endpoint in ('before','after'):
                bad=deepcopy(motion);bad['ticks'][0][endpoint]['elapsed']+=1
                with self.assertRaisesRegex(ValueError,'elapsed'):validate_motion(**bad)
            bad=deepcopy(motion);bad['events'][0]['actorFrame']=events[0]['frame']
            with self.assertRaises(ValueError):validate_motion(**bad)


if __name__ == "__main__":
    unittest.main()

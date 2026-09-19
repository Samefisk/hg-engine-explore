"""Controller contract rows and copied-data controls for D4 stress proof. No I/O."""
from copy import deepcopy
from hashlib import sha256
import json

from tools.overworld.devtools_mount_control_stress import KIND, CONTRACTS, LIFECYCLE, require
from tools.overworld.normal_play_observer import complete_travel
from tools.overworld.devtools_movement_predicates import player_settled_at

WALK_REQUIREMENT = "legacy.cyndaquil-control-stress"
HOP_REQUIREMENT = "legacy.mankey-control-stress"
REQUIREMENTS = (WALK_REQUIREMENT, HOP_REQUIREMENT)
CLAIMS = ("natural-input", "live-actor-identity", "rendered-motion", "control-release")


def contract(requirement):
    require(requirement in REQUIREMENTS, "unknown mounted stress requirement")
    return deepcopy(_CONTRACTS[requirement])


def measurements(result, requirement):
    """Recompute rows after independent replay; session cleanup stays with controller."""
    rules = CONTRACTS.get(requirement)
    require(rules is not None, "unknown mounted stress requirement")
    meter = result.get("measurements", {}).get(KIND, result)
    require(result.get("passed") is True and result.get("failures") == []
            and meter.get("passed") is True and meter.get("closed") is True and meter.get("failures") == []
            and meter.get("acceptedProof") is False and meter.get("contract") == requirement,
            "stress lacks a closed independent replay")
    initial = meter["initial"]; actor = initial["actor"]
    require(actor.get("species") == rules["species"] and actor.get("role") == "MOUNTED"
            and actor.get("inputOwnership") == 1 and actor.get("identityVerified") is True
            and actor.get("presentationAttached") is True and actor["handle"].get("slot") == 7,
            "stress proof has wrong initial subject")
    require(meter["subject"]["handle"] == actor["handle"] and meter["subject"]["species"] == actor["species"]
            and actor["sourceIdentity"]["personality"] == actor["subjectIdentity"]
            and actor["sourceIdentity"]["object"] == actor["engineIdentity"]["pointer"],
            "stress proof initial binding differs")
    summaries = meter.get("motionSummaries")
    require(isinstance(summaries,list) and 1 <= len(summaries) <= 40000, "stress proof lacks bounded motion evidence")
    main = []; recovery = []; frame_set = set(); directions=[]; previous_finish=-1
    allowed_kinds = (("WALK", "SKID") if rules["motion"] == "WALK"
                     else (rules["motion"],))
    kind_ids = {"WALK": 1, "HOP": 2, "SKID": 4}
    for summary in summaries:
        motion = summary["motion"]
        require(summary["sha256"] == sha256(json.dumps(motion,sort_keys=True).encode()).hexdigest(),
                "stress raw motion digest differs")
        require(complete_travel(motion) and motion.get("kind") in allowed_kinds
                and motion.get("handle") == actor["handle"] and motion.get("fingerprint") == actor["behaviorFingerprint"]
                and motion.get("commitAfter") == (motion.get("commitBefore")+1)&0xFFFFFFFF
                and motion.get("terminalLogical") == motion.get("target"), "stress motion is incomplete or wrong kind")
        require([motion["terminalRender"][0],motion["terminalRender"][2]] == [(v<<16)+32768 for v in motion["target"]],
                "stress motion terminal presentation differs")
        dx,dz=(t-o for o,t in zip(motion["origin"],motion["target"]))
        require((dx or dz) and all((b["render"][0]-a["render"][0])*dx + (b["render"][2]-a["render"][2])*dz > 0
                for a,b in zip(motion["samples"],motion["samples"][1:])), "stress motion presentation stalled or reversed")
        require(all(summary.get(k) == motion.get(k) for k in ("kind","startFrame","commitFrame","finishFrame","commitBefore","commitAfter","duration","origin","target")),
                "stress motion summary differs")
        require(initial["frame"] < motion["startFrame"] <= motion["commitFrame"] <= motion["finishFrame"]
                <= initial["frame"] + meter["frames"] and motion["startFrame"] >= previous_finish,
                "stress motion frame range differs")
        previous_finish=motion["finishFrame"]
        events=summary["lifecycle"]
        require([e.get("event") for e in events] == list(LIFECYCLE)
                and all(e.get("reason") == "OK" and e.get("actorHandle") == actor["handle"]["value"] for e in events),
                "stress motion lacks lifecycle")
        kind_id = kind_ids[motion["kind"]]
        expected=((kind_id,motion["duration"]),(motion["commitAfter"],kind_id),
                  (motion["commitAfter"],kind_id),(1,motion["commitAfter"]))
        require([(e.get("valueA"),e.get("valueB")) for e in events] == list(expected)
                and [e["sequence"] for e in events] == sorted(set(e["sequence"] for e in events)),
                "stress lifecycle values/order differ")
        if summary["phase"] == "stress":
            frame_set.update(range(motion["startFrame"],motion["finishFrame"]+1))
            if motion["kind"] == rules["motion"]:
                main.append(summary)
                directions.append(tuple((t>o)-(t<o) for o,t in zip(motion["origin"],motion["target"])))
        elif summary["phase"] == "recovery":
            require(motion["kind"] == rules["motion"], "stress recovery has wrong kind")
            recovery.append(summary)
        else: require(summary["phase"] == "detach", "unknown stress motion phase")
    turns=sum(a!=b for a,b in zip(directions,directions[1:]))
    require(len(main) >= rules["motions"] and turns >= rules["turns"] and len(frame_set) >= rules["frames"],
            "stress count/frame/turn floors incomplete")
    require(meter["motions"] == len(main) and meter["turns"] == turns and meter["routeFrames"] == len(frame_set)
            and 0 < meter["frames"] <= 40000, "stress reported totals differ from motion evidence")
    milestones=meter.get("milestones",{})
    required=("detach","unmounted-step","remount","recovery")
    require(all(type(milestones.get(k)) is int for k in required)
            and [milestones[k] for k in required] == sorted(set(milestones[k] for k in required))
            and bool(recovery) and recovery[0]["startFrame"] > milestones["remount"]
            and recovery[-1]["finishFrame"] <= milestones["recovery"], "stress control milestones incomplete")
    points=meter["milestoneEvidence"]
    for name in (*required,"unmounted-progress"):
        point=points[name];subject=point["actor"]
        require(point["context"]==initial["context"] and subject["handle"]==actor["handle"]
                and subject["species"]==actor["species"] and subject["subjectIdentity"]==actor["subjectIdentity"]
                and subject.get("identityVerified") is True and point.get("fieldAvailable") is True
                and point.get("observationBoundary")=="main-task-queue-completion",
                "stress milestone subject/context differs")
        if name in milestones:require(point["frame"]==milestones[name],"stress milestone frame differs")
        mounted=name in ("remount","recovery")
        require(subject["role"]==("MOUNTED" if mounted else "FOLLOWER")
                and subject["inputOwnership"]==int(mounted),"stress milestone control differs")
    detached,normal=points["detach"],points["unmounted-step"]
    require(detached["actor"]["reservationId"]==0
            and detached["frame"] < points["unmounted-progress"]["frame"] < normal["frame"]
            and (detached["player"]["x"],detached["player"]["y"]) != (normal["player"]["x"],normal["player"]["y"])
            and player_settled_at(normal,normal["context"]["mapId"],normal["player"]["x"],normal["player"]["y"])
            and points["recovery"]["actor"]["motionPhase"]=="IDLE"
            and points["recovery"]["actor"]["reservationId"]==0,"stress milestone native control is incomplete")
    generations=[actor["handle"]["encounterGeneration"],actor["sourceIdentity"]["encounter_generation"],actor["engineIdentity"]["encounter_generation"]]
    require(generations[0]>0 and len(set(generations))==1, "stress encounter generations differ")
    values = {
        "held-input-commit-count":len(main),"held-input-turn-count":turns,"held-input-route-frame-count":len(frame_set),
        "cyndaquil-species":actor["species"],"mounted-object-pointer":actor["engineIdentity"]["pointer"],
        "actor-handle":actor["handle"],"mounted-object-identity-flags":[1,1,1,1,7,actor["species"],1],
        "encounter-generation-match":generations,"valid-mounted-walk-callback-count":[len(main),len(main)],
        "dismount-remount-control-milestones":["IDLE",0,1,1,1,1,1],
        "completed-natural-hop-count":len(main),"mankey-stress-active-frame-count":len(frame_set),
        "mankey-stress-identity":[1,"MOUNTED",actor["species"],1],"actor-owned-hop-motion-count":len(main),
        "valid-mounted-hop-motion-count":[len(main),len(main)],"dismount-and-remount-milestones":[1,1,1,1,"IDLE",0],
    }
    rows=[]
    for claim,specs in contract(requirement).items():
        for spec in specs:
            value=values[spec["name"]]
            rows.append(dict(claim=claim,name=spec["name"],value=deepcopy(value),
                             expected=deepcopy(spec.get("expected",value)),operator=spec["operator"],passed=True))
    return rows


MEANINGS = {"stress-missing-start":"MOTION_STARTED","stress-missing-commit":"LOGICAL_COMMIT",
            "stress-missing-finish":"MOTION_FINISHED","stress-missing-return":"CONTROL_RETURNED"}
FAULTS = ("stress-absent-subject","stress-stale-subject","stress-bad-pair","stress-wrong-kind",*MEANINGS)


class MountControlStressNegative:
    def __init__(self,fault):
        require(fault in FAULTS,"unknown stress negative fault")
        self.fault,self.applied=fault,False

    def mutate(self,row,subjects):
        if self.applied or row.get("phase") != "observe" or not subjects:return row
        changed=deepcopy(row);handles={s["handle"]["value"] for s in subjects.values()}
        for sample in changed.get("samples",[]):
            actor=next((a for a in sample.get("actors",[]) if a.get("handle",{}).get("value") in handles),None)
            if actor is None:continue
            if self.fault=="stress-absent-subject":sample["actors"].remove(actor);self.applied=True
            elif self.fault=="stress-stale-subject":actor["authorityGeneration"]+=1;self.applied=True
            elif self.fault=="stress-bad-pair" and actor.get("role")=="MOUNTED":actor["engineObject"]["pos_x"]+=1;self.applied=True
            elif self.fault=="stress-wrong-kind" and actor.get("motionPhase")=="MOVING":
                actor["motionKindId"]=2 if actor["motionKind"]=="WALK" else 1;self.applied=True
            if self.applied:break
        if not self.applied:
            for event in changed.get("events",[]):
                data=event.get("data",{})
                if self.fault in MEANINGS and data.get("actorHandle") in handles and data.get("event")==MEANINGS[self.fault]:
                    data["event"]="WORLD_EFFECT";self.applied=True;break
        return changed if self.applied else row


def validate_negative_result(result,fault):
    require(fault in FAULTS and result.get("passed") is False,"stress copied control did not fail")
    failures=result.get("failures",[])+result.get("measurements",{}).get(KIND,{}).get("failures",[])
    reasons=[]
    for item in failures:
        if isinstance(item,str):reasons.append(item)
        elif isinstance(item,dict):reasons.extend(item[k] for k in ("detail","message") if isinstance(item.get(k),str))
    expected=("missing/duplicate native "+MEANINGS[fault]) if fault in MEANINGS else {
        "stress-absent-subject":"missing or duplicate mounted subject",
        "stress-stale-subject":"ownership changed without role rebound",
        "stress-bad-pair":"player/presentation base positions differ",
        "stress-wrong-kind":"wrong active stress motion kind"}[fault]
    require(expected in reasons,"stress copied control failed for an unrelated reason: "+fault)
_CONTRACTS = {'legacy.cyndaquil-control-stress': {'natural-input': [{'name': 'held-input-commit-count',
                                                        'operator': 'gte',
                                                        'type': 'integer',
                                                        'validator': 'meaningful-observation',
                                                        'minimum': 2000},
                                                       {'name': 'held-input-turn-count',
                                                        'operator': 'gte',
                                                        'type': 'integer',
                                                        'validator': 'meaningful-observation',
                                                        'minimum': 250},
                                                       {'name': 'held-input-route-frame-count',
                                                        'operator': 'gte',
                                                        'type': 'integer',
                                                        'validator': 'meaningful-observation',
                                                        'minimum': 5000}],
                                     'live-actor-identity': [{'name': 'cyndaquil-species',
                                                              'operator': 'eq',
                                                              'type': 'integer',
                                                              'validator': 'meaningful-observation',
                                                              'expected': 155},
                                                             {'name': 'mounted-object-pointer',
                                                              'operator': 'eq',
                                                              'type': 'integer',
                                                              'validator': 'meaningful-observation',
                                                              'minimum': 1},
                                                             {'name': 'actor-handle',
                                                              'operator': 'eq',
                                                              'type': 'object',
                                                              'validator': 'actor-handle-current',
                                                              'requiredKeys': ['slot',
                                                                               'generation',
                                                                               'fieldEpoch',
                                                                               'mapGeneration',
                                                                               'encounterGeneration',
                                                                               'value']},
                                                             {'name': 'mounted-object-identity-flags',
                                                              'operator': 'eq',
                                                              'type': 'array',
                                                              'validator': 'meaningful-observation',
                                                              'expected': [1, 1, 1, 1, 7, 155, 1]},
                                                             {'name': 'encounter-generation-match',
                                                              'operator': 'eq',
                                                              'type': 'array',
                                                              'validator': 'positive-identical-values',
                                                              'minItems': 3}],
                                     'rendered-motion': [{'name': 'valid-mounted-walk-callback-count',
                                                          'operator': 'eq',
                                                          'type': 'array',
                                                          'validator': 'complete-motion-observation-v1',
                                                          'minimumTotal': 2000}],
                                     'control-release': [{'name': 'dismount-remount-control-milestones',
                                                          'operator': 'eq',
                                                          'type': 'array',
                                                          'validator': 'meaningful-observation',
                                                          'expected': ['IDLE', 0, 1, 1, 1, 1, 1]}]},
 'legacy.mankey-control-stress': {'natural-input': [{'name': 'completed-natural-hop-count',
                                                     'operator': 'gte',
                                                     'type': 'integer',
                                                     'validator': 'meaningful-observation',
                                                     'minimum': 200},
                                                    {'name': 'mankey-stress-active-frame-count',
                                                     'operator': 'gte',
                                                     'type': 'integer',
                                                     'validator': 'meaningful-observation',
                                                     'minimum': 5001}],
                                  'live-actor-identity': [{'name': 'mankey-stress-identity',
                                                           'operator': 'eq',
                                                           'type': 'array',
                                                           'validator': 'meaningful-observation',
                                                           'expected': [1, 'MOUNTED', 56, 1]},
                                                          {'name': 'actor-owned-hop-motion-count',
                                                           'operator': 'eq',
                                                           'type': 'integer',
                                                           'validator': 'meaningful-observation',
                                                           'minimum': 1}],
                                  'rendered-motion': [{'name': 'valid-mounted-hop-motion-count',
                                                       'operator': 'eq',
                                                       'type': 'array',
                                                       'validator': 'complete-motion-observation-v1',
                                                       'minimumTotal': 200}],
                                  'control-release': [{'name': 'dismount-and-remount-milestones',
                                                       'operator': 'eq',
                                                       'type': 'array',
                                                       'validator': 'meaningful-observation',
                                                       'expected': [1, 1, 1, 1, 'IDLE', 0]}]}}

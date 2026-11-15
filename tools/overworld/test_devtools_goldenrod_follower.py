"""Host controls for T85. Synthetic streams do not prove game movement."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.overworld import control
from tools.overworld.devtools_goldenrod_follower_measurement import (
    KIND, REQUIREMENT, NAME, PID, GoldenrodFollowerMeasurement, initial_hop_witness, source_inputs)
from tools.overworld.devtools_goldenrod_follower_proof import GoldenrodFollowerNegative, FAULTS, measurements, validate_negative_result
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(contractVersion=1, profileSha256="1" * 64)


def recipe():
    return json.loads((ROOT / "tests/overworld/test-recipes" / (NAME + ".json")).read_text())


def sample(frame, map_id=76, epoch=1, player_z=374, tick=100, origin=365, target=367):
    handle = dict(value=65543, slot=7, generation=1, fieldEpoch=epoch, mapGeneration=epoch, encounterGeneration=1)
    moving = tick is not None and tick < 4
    settling = tick == 4
    elapsed = min(tick + 1, 4) if moving else 4
    committed = tick is not None and tick >= 4
    logical_z = target if committed else origin
    render_z = origin if tick is None else origin + (target - origin) * elapsed / 4 if moving else target
    engine = dict(pos_x=(358 << 16) + 32768, pos_y=0, pos_z=int(render_z * 65536) + 32768,
                  unk88_y=0, facing=1, flags=1)
    source = dict(object=0x02200000, personality=PID, map_id=map_id, species=56, form=0, level=3,
                  active=1, object_id=231, encounter_generation=1)
    binding = dict(pointer=source["object"], active=True, in_manager=True, object_manager=0x02210000, current_manager=0x02210000,
                   object_id=231, spawn_object_id=231, object_map_id=map_id, spawn_map_id=map_id,
                   current_map_id=map_id, encounter_generation=1, script_id=2074)
    actor = dict(handle=handle, active=True, species=56, role="FOLLOWER", form=0, level=3, presentationAttached=True,
        identityVerified=True, authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1,
        subjectIdentity=PID, behaviorFingerprint=123, sourceIdentity=source, engineIdentity=binding,
        engineObject=engine, logical=dict(x=358, y=logical_z), origin=dict(x=358, y=origin), target=dict(x=358, y=target),
        motionKind="HOP" if moving or settling else "NONE", motionPhase="MOVING" if moving else "SETTLING" if settling else "IDLE",
        motionDuration=4, motionElapsed=elapsed, commitSequence=int(committed), reservationId=1 if moving else 0,
        inputOwnership=0)
    lane = bytearray(80); lane[12] = 2; lane[32] = 69
    context = dict(mapId=map_id, fieldEpoch=epoch, mapGeneration=epoch)
    party = [dict(slot=i, species=56, personality=PID if i == 2 else i + 1, identityVerified=True, isEgg=False,
                  hp=15, maxHp=15, status=0, form=0, level=3) for i in range(3)]
    return dict(frame=frame, nativeCycle=frame, actorFrame=frame, fieldAvailable=True, prepared=False,
        observationBoundary="main-task-queue-completion", context=context, fieldControl=dict(taskPointer=0),
        player=dict(x=358, y=player_z, x_prev=358, y_prev=player_z, pos_x=(358 << 16) + 32768,
                    pos_z=(player_z << 16) + 32768, unk88_y=0, flags=1, movement_cmd=1),
        party=party, partyObservation=dict(frame=frame, boundary="main-task-queue-completion"), actors=[actor],
        selector=dict(activeFollowerPartySlot=2), terrain=dict(cells=[dict(x=358, z=target, loaded=True,
            collision=False, surface=dict(known=True, present=False))], observation=dict(context=deepcopy(context),
                lastCompletedGameFrame=frame, nativeCycle=frame)),
        nativeObservation=dict(installedBeforeBoot=True, coverageComplete=True, eventsDropped=0, profilesEvicted=0,
            pendingUnframedEvents=0, error=None, profileFingerprints=[123], resolvedProfiles=[dict(fingerprint=123, resolved=True,
                sourceSha256=SOURCE["profileSha256"], lanes=[lane.hex(), lane.hex()])]))


def rows():
    initial = sample(100, player_z=366, tick=None)
    result = [dict(phase="setup", initialSnapshot=initial), dict(phase="setup", action="bind-saved-mankey",
        command="bind", snapshot=initial, receipt=select_current_actor(initial, initial["actors"][0]))]
    frame, sequence = 100, 0
    for action, count, map_id, epoch, player_z, origin, target, hops in (
            ("gold-walk",32,76,1,374,365,367,True), ("gold-rest",64,76,1,374,365,367,False),
            ("route-down",8,38,2,385,382,384,True), ("route-rest",64,38,2,385,382,384,False),
            ("gold-up",8,76,3,380,383,381,True), ("gold-return-rest",64,76,3,380,383,381,False)):
        samples = [sample(frame+i+1,map_id,epoch,player_z,i if hops else 100,origin,target) for i in range(count)]
        keys = ["DOWN"] if action in ("gold-walk","route-down") else ["UP"] if action == "gold-up" else []
        events = []
        if hops:
            sequence += 1
            old_epoch = epoch - 1 if epoch > 1 else epoch
            handle = deepcopy(samples[0]["actors"][0]["handle"])
            handle.update(fieldEpoch=old_epoch, mapGeneration=old_epoch)
            value = handle.pop("value")
            if epoch > 1:
                events.append(dict(frame=samples[0]["frame"], kind="trace-status", data=dict(
                    code="field-epoch-changed", traceStream=1, diagnosticOnly=True,
                    previousEpoch=old_epoch, fieldEpoch=epoch, sequenceReset=False)))
                events.append(dict(frame=samples[0]["frame"], kind="trace-status", data=dict(
                    code="ring-overwrite", traceStream=1, diagnosticOnly=True, count=1, unreadEventsLost=0)))
            events.append(dict(frame=samples[0]["frame"], kind="native", data=dict(
                sequence=sequence, traceStream=1, traceFieldEpoch=epoch, actorHandle=value,
                actor=handle, event="CONTEXT_CHANGED" if epoch > 1 else "MOTION_STARTED",
                valueA=old_epoch, valueB=epoch)))
        result.append(dict(phase="observe",action=action,requestedInput=dict(keys=keys), requestedGameFrames=count,
            completedGameFrames=count,observedFieldFrames=count,nativeCycles=count,samples=samples,snapshot=samples[-1],events=events,
            cycleIntervals=[dict(completedGameFrame=s["frame"],cpuNs=1,wallNs=1) for s in samples]))
        frame += count
    return result


def replay(fault=None, stream=None):
    meter = GoldenrodFollowerMeasurement(recipe(), SOURCE)
    negative = GoldenrodFollowerNegative(fault) if fault else None
    for row in deepcopy(stream or rows()):
        if negative: row = negative.mutate(row,{})
        result = meter.observe_record(row)
        if result["failures"]: break
    result = meter.finish()
    return dict(passed=result["passed"],failures=result["failures"],measurements={KIND:result})


class GoldenrodFollowerTests(unittest.TestCase):
    def test_exact_cached_field_epoch_notice_has_normal_transition_witness(self):
        meter = GoldenrodFollowerMeasurement(recipe(), SOURCE)
        meter.latest = sample(847, epoch=2)
        meter.trace_sequences = {1: 46}
        current = sample(848, map_id=38, epoch=3)
        handle = deepcopy(meter.latest["actors"][0]["handle"])
        value = handle.pop("value")
        events = [dict(frame=848, kind="trace-status", data=dict(code="field-epoch-changed",
            traceStream=1, diagnosticOnly=True, previousEpoch=2, fieldEpoch=3, sequenceReset=False)),
            dict(frame=848, kind="native", data=dict(sequence=47, traceStream=1, traceFieldEpoch=3,
                actorHandle=value, actor=handle, event="CONTEXT_CHANGED", valueA=2, valueB=3))]
        meter._events(events, current)
        self.assertEqual(meter.transition_notice, current["context"])
        self.assertEqual(meter.trace_sequences, {1:47})

    def test_semantic_sequence_gap_is_rejected_at_either_seam(self):
        for action in ("route-down", "gold-up"):
            stream = rows()
            row = next(row for row in stream if row.get("action") == action)
            next(event for event in row["events"] if event["kind"] == "native")["data"]["sequence"] += 1
            result = replay(stream=stream)
            self.assertFalse(result["passed"])
            self.assertIn("semantic trace has a gap or duplicate", repr(result))

    def test_dense_chunks_use_observed_profile_receipts_without_terrain(self):
        stream = rows()
        for row in stream:
            for sample_ in row.get("samples", []):
                sample_.pop("terrain")
                sample_["nativeObservation"].pop("resolvedProfiles")
        result = replay(stream=stream)
        self.assertTrue(result["passed"], result)

    def test_complete_three_context_hops_and_all_copied_faults(self):
        value = replay()
        self.assertTrue(value["passed"],value)
        proof = measurements(value,dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[])))
        self.assertTrue(all(row["passed"] for row in proof))
        for fault in FAULTS:
            with self.subTest(fault=fault):
                changed = replay(fault)
                self.assertFalse(changed["passed"])
                validate_negative_result(changed,fault)

    def test_first_walk_predicate_requires_real_hop_not_valid_profile(self):
        stream = rows()
        snapshots = [stream[0]["initialSnapshot"]] + stream[2]["samples"] + stream[3]["samples"]
        self.assertTrue(initial_hop_witness(snapshots))
        for sample_ in snapshots:
            sample_["actors"][0].update(motionKind="NONE",motionPhase="IDLE")
        with self.assertRaisesRegex(ValueError,"initial walk lacks a completed shared Hop"):
            initial_hop_witness(snapshots)

    def test_actual_controller_registration_and_dispatch_install(self):
        value = recipe();self.assertEqual(validate_test(value)["mode"],"normal")
        registration,digest = control._shared_test_registration(value,ROOT)
        self.assertEqual(registration["recipeSha256"],digest)
        evaluator = TestEvaluator(value);evaluator.install_measurements(measurement_inputs(value,ROOT))
        self.assertIsInstance(evaluator.measurements[KIND],GoldenrodFollowerMeasurement)
        for fault in ("input","setup","frame-floor","claim","contract"):
            changed,registry = recipe(),json.loads((ROOT/'tools/overworld/runtime_proof_registry.json').read_text())
            entry = registry['sharedTests'][NAME]
            if fault == 'input':changed['actions'][0]['args']['keys']=['UP']
            elif fault == 'setup':changed['setup'][0]['op']='teleport'
            elif fault == 'frame-floor':changed['budgets']['minObservedFrames']-=1
            elif fault == 'claim':entry['claims'].pop()
            else:entry['measurementContract']['logical-commit'][0]['expected']=[0,0,0]
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);p=root/'tests/overworld/test-recipes'/f'{NAME}.json';p.parent.mkdir(parents=True)
                content=json.dumps(changed).encode();p.write_bytes(content);entry['recipeSha256']=hashlib.sha256(content).hexdigest()
                p=root/'tools/overworld/runtime_proof_registry.json';p.parent.mkdir(parents=True);p.write_text(json.dumps(registry))
                with self.assertRaises((ValueError,control.ValidationFailure)):
                    control._shared_test_registration(changed,root)


if __name__=='__main__':unittest.main()

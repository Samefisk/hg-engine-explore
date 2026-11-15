"""Narrow checker controls copied from the real T78 no-movement record.

These data prove rejection/identity/profile checks. They are not a generated
positive flight and never supply runtime acceptance.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_canopy_hop_measurement import (
    KIND, TEST, REQUIREMENT, MountedCanopyHopMeasurement, validate_recipe)
from tools.overworld.devtools_mounted_canopy_hop_proof import (
    FAULTS, MountedCanopyHopNegative, measurements, validate_negative_result)

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'TICKETS.md').is_file())

# Actual completed no-movement baseline; native Motion bytes are real IDLE, not a simulated Hop.
BASELINE=json.loads('{"frame":808,"nativeCycle":2092,"actorFrame":350,"fieldAvailable":true,"observationBoundary":"main-task-queue-completion","romSha256":"0cb93091ef8dc50c6b2c19d7bb6a7c4a6c8cf3963d039bc44a3aa770f460f30a","context":{"fieldEpoch":3,"mapGeneration":3,"mapId":34},"fieldControl":{"fieldPointer":36377180,"taskPointer":0},"selector":{"rawHeld":0,"heldKeys":0,"simulatedKeys":0,"activeFollowerPartySlot":2},"party":[{"checksum":31719,"form":0,"hp":15,"identityVerified":true,"isEgg":false,"level":3,"maxHp":15,"moves":[10,43,116,343],"personality":2920357538,"pp":[8,8,8,8],"slot":2,"species":56,"status":0}],"nativeObservation":{"coverageComplete":true,"installedBeforeBoot":true,"eventsDropped":0,"profilesEvicted":0,"pendingUnframedEvents":0,"error":null,"profileFingerprints":[1241468534,298835013,3568671740]},"terrain":{"observation":{"boundary":"paused-native-cycle-end","center":{"x":561,"z":364},"context":{"fieldEpoch":3,"mapGeneration":3,"mapId":34},"lastCompletedGameFrame":808,"nativeCycle":2092},"cells":[{"attribute":1024,"behavior":0,"block":2,"collision":false,"loaded":true,"matrix_index":534,"provenance":{"attributeAddress":36964954,"chunkMatrixIndex":534,"chunkModelLoaded":1,"chunkPointer":36964152,"currentMatrixIndex":534,"currentSlot":2,"fieldPointer":36377180,"landDataId":8,"landDataIdentity":"current-map-matrix","landManagerPointer":36806852,"mapHeaderId":34,"mapMatrixPointer":36377556,"matrixAltitude":0,"matrixHeight":17,"matrixId":0,"matrixWidth":47,"rawWord":1024,"readerPointer":33900505,"selectedSlot":2,"store":"rolling-land-manager","terrainAttributesPointer":null},"surface":{"catalogPointer":37219204,"known":true,"landDataId":8,"localX":17,"localZ":12,"present":false,"scope":"live authored surface catalog; native-ground offsets are not final world heights"},"terrain_class":4,"x":561,"y":364,"z":364},{"attribute":32774,"behavior":6,"block":2,"collision":true,"loaded":true,"matrix_index":534,"provenance":{"attributeAddress":36964956,"chunkMatrixIndex":534,"chunkModelLoaded":1,"chunkPointer":36964152,"currentMatrixIndex":534,"currentSlot":2,"fieldPointer":36377180,"landDataId":8,"landDataIdentity":"current-map-matrix","landManagerPointer":36806852,"mapHeaderId":34,"mapMatrixPointer":36377556,"matrixAltitude":0,"matrixHeight":17,"matrixId":0,"matrixWidth":47,"rawWord":32774,"readerPointer":33900505,"selectedSlot":2,"store":"rolling-land-manager","terrainAttributesPointer":null},"surface":{"catalogPointer":37219204,"known":true,"landDataId":8,"localX":18,"localZ":12,"present":false,"scope":"live authored surface catalog; native-ground offsets are not final world heights"},"terrain_class":0,"x":562,"y":364,"z":364}]},"pokemonCombat":{"available":true,"schemaVersion":1,"frame":808,"nativeCycle":2092,"identity":{"descriptorVersion":1,"overlaySha256":"62ac03e8f522c35e88750a37639ae5a74ba0250439e2929f1ae7e408f0c7cd20","romSha256":"0cb93091ef8dc50c6b2c19d7bb6a7c4a6c8cf3963d039bc44a3aa770f460f30a"},"targets":[{"handle":{"encounterGeneration":1,"fieldEpoch":3,"generation":2,"mapGeneration":3,"slot":7,"value":131079},"hp":15,"hpSource":"party","knockbackPending":0,"motion":{"cancelReason":0,"commitPublished":0,"commitSequence":0,"elapsed":0,"pathAdvancesPublished":0,"phase":"IDLE","phaseBeforeSuspend":0,"phaseId":0,"plan":{"arcHeightQ4":0,"behaviorFingerprint":0,"commitPolicy":0,"direction":0,"distance":0,"duration":0,"facing":0,"fieldEpoch":0,"flags":0,"kind":0,"origin":[0,0],"pathAdvancePolicy":0,"pauseFrames":0,"reservationId":0,"spinSpeed":0,"startBaseY":0,"swayWidth":0,"target":[0,0],"targetBaseY":0,"version":0,"visibilityPolicy":0},"rawHex":"00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000","settleRemaining":0},"personality":2920357538,"role":"MOUNTED","species":56}]},"player":{"x":561,"y":364,"pos_x":36798464,"pos_y":131072,"pos_z":23887872,"face_y":32768,"unk88_y":0},"actors":[{"handle":{"encounterGeneration":1,"fieldEpoch":3,"generation":2,"mapGeneration":3,"slot":7,"value":131079},"species":56,"form":0,"level":3,"role":"MOUNTED","subjectIdentity":2920357538,"behaviorFingerprint":3568671740,"authorityGeneration":3,"engineAnchorGeneration":3,"presentationGeneration":2,"active":true,"presentationAttached":true,"identityVerified":true,"inputOwnership":1,"logical":{"x":561,"y":364},"origin":{"x":0,"y":0},"target":{"x":0,"y":0},"motionKind":"NONE","motionPhase":"IDLE","motionElapsed":0,"motionDuration":0,"commitSequence":0,"reservationId":0,"engineIdentity":{"active":true,"anchorInCurrentManager":true,"anchorPointer":36384756,"current_manager":36384424,"current_map_id":34,"encounter_generation":1,"id_lookup":{"capacity_limit":64,"eligible_count":1,"first_active_index":15,"first_active_pointer":36389256,"matching_objects":[{"active":true,"flag25":false,"flags":2147796001,"lookup_eligible":true,"manager_index":15,"object_id":231,"object_map_id":34,"pointer":36389256,"script_id":2074}],"object_count":64,"pointer_matches":true,"requested_id":231,"source":"stock-first-active-id-semantics","status":"complete"},"in_manager":true,"manager_index":15,"object_id":231,"object_manager":36384424,"object_map_id":34,"pointer":36389256,"script_id":2074,"spawn_map_id":34,"spawn_object_id":231},"engineObject":{"pos_x":36798464,"pos_y":131072,"pos_z":23887872,"face_y":0,"unk88_y":0}}]}')
CACHE=json.loads('{"frame":808,"nativeCycle":2092,"resolvedProfiles":[{"appliedOverrides":523,"fingerprint":3568671740,"lanes":["0203080a01140a06050200030200010f5a030001010605091e000001050000024500ff0707000000040170010218000b1e9601020800ff0306010000040509010500321e000300010000000008143c04","0203080a01140a06050200030200010f5a030001010605091e000001050000024500ff0707000000040170010218000b1e9601020800ff0306010000040509010500321e000300010000000008143c04"],"requestHex":"38000000080000000300000100020000000000000000000000000000000000000000ffff01ff0200ffff0000","resolved":true,"resultHex":"0203080a01140a06050200030200010f5a030001010605091e000001050000024500ff0707000000040170010218000b1e9601020800ff0306010000040509010500321e000300010000000008143c040203080a01140a06050200030200010f5a030001010605091e000001050000024500ff0707000000040170010218000b1e9601020800ff0306010000040509010500321e000300010000000008143c0407020100000201050101ffff000000000b00000000020000000000000b020000fc9bb5d40000000000000000000000000000ffffff00ffff","sourceSha256":"54e437c9e547c482b4f4101a100b938a5afcd36125e392412330f9b582f5e84a"}]}')
SOURCE={'contractVersion': 1, 'romSha256': '0cb93091ef8dc50c6b2c19d7bb6a7c4a6c8cf3963d039bc44a3aa770f460f30a', 'overlaySha256': '62ac03e8f522c35e88750a37639ae5a74ba0250439e2929f1ae7e408f0c7cd20', 'profileSha256': '54e437c9e547c482b4f4101a100b938a5afcd36125e392412330f9b582f5e84a'}

# Actual isolated long-Hop stream wait. This checks the terminal seam only,
# not the T78 adjacent-tree positive claim or the reported no-move baseline.
PLATEAU=json.loads('{"packet":{"sample":{"frame":1415,"nativeCycle":3433,"player":{"x":558,"y":375}},"actor":{"motionKind":"HOP","motionPhase":"COMMIT_PENDING","motionElapsed":37,"streamState":1,"reservationId":15,"origin":{"x":564,"y":375},"target":{"x":558,"y":375},"logical":{"x":558,"y":375},"commitSequence":0,"engineObject":{"pos_x":36601856,"pos_y":65536,"pos_z":24608768,"face_y":0,"unk88_y":0}},"motion":{"rawHex":"010002020600fc9b340277012e027701000001000000010025000f00020610000000000200000000250000000600000003000000","plan":{"version":1,"kind":2,"facing":2,"fieldEpoch":6,"behaviorFingerprint":39932,"origin":[564,375],"target":[558,375],"startBaseY":65536,"targetBaseY":65536,"duration":37,"reservationId":15,"direction":2,"distance":6,"arcHeightQ4":16,"spinSpeed":0,"swayWidth":0,"visibilityPolicy":0,"pauseFrames":0,"pathAdvancePolicy":2,"commitPolicy":0,"flags":0},"elapsed":37,"settleRemaining":0,"pathAdvancesPublished":6,"commitSequence":0,"phase":"COMMIT_PENDING","phaseId":3,"phaseBeforeSuspend":0,"commitPublished":0,"cancelReason":0}},"clocks":[{"frame":1415,"nativeCycle":3433,"player":{"x":558,"y":375}},{"frame":1416,"nativeCycle":3435,"player":{"x":558,"y":375}},{"frame":1417,"nativeCycle":3437,"player":{"x":558,"y":375}},{"frame":1418,"nativeCycle":3439,"player":{"x":558,"y":375}},{"frame":1419,"nativeCycle":3441,"player":{"x":558,"y":375}},{"frame":1420,"nativeCycle":3443,"player":{"x":558,"y":375}},{"frame":1421,"nativeCycle":3445,"player":{"x":558,"y":375}},{"frame":1422,"nativeCycle":3447,"player":{"x":558,"y":375}},{"frame":1423,"nativeCycle":3449,"player":{"x":558,"y":375}},{"frame":1424,"nativeCycle":3451,"player":{"x":558,"y":375}},{"frame":1425,"nativeCycle":3453,"player":{"x":558,"y":375}},{"frame":1426,"nativeCycle":3455,"player":{"x":558,"y":375}},{"frame":1427,"nativeCycle":3457,"player":{"x":558,"y":375}},{"frame":1428,"nativeCycle":3459,"player":{"x":558,"y":375}},{"frame":1429,"nativeCycle":3461,"player":{"x":558,"y":375}},{"frame":1430,"nativeCycle":3463,"player":{"x":558,"y":375}},{"frame":1431,"nativeCycle":3465,"player":{"x":558,"y":375}},{"frame":1432,"nativeCycle":3467,"player":{"x":558,"y":375}}],"travel":[{"frame":1378,"elapsed":1},{"frame":1379,"elapsed":2},{"frame":1380,"elapsed":3},{"frame":1381,"elapsed":4},{"frame":1382,"elapsed":5},{"frame":1383,"elapsed":6},{"frame":1384,"elapsed":7},{"frame":1385,"elapsed":8},{"frame":1386,"elapsed":9},{"frame":1387,"elapsed":10},{"frame":1388,"elapsed":11},{"frame":1389,"elapsed":12},{"frame":1390,"elapsed":13},{"frame":1391,"elapsed":14},{"frame":1392,"elapsed":15},{"frame":1393,"elapsed":16},{"frame":1394,"elapsed":17},{"frame":1395,"elapsed":18},{"frame":1396,"elapsed":19},{"frame":1397,"elapsed":20},{"frame":1398,"elapsed":21},{"frame":1399,"elapsed":22},{"frame":1400,"elapsed":23},{"frame":1401,"elapsed":24},{"frame":1402,"elapsed":25},{"frame":1403,"elapsed":26},{"frame":1404,"elapsed":27},{"frame":1405,"elapsed":28},{"frame":1406,"elapsed":29},{"frame":1407,"elapsed":30},{"frame":1408,"elapsed":31},{"frame":1409,"elapsed":32},{"frame":1410,"elapsed":33},{"frame":1411,"elapsed":34},{"frame":1412,"elapsed":35},{"frame":1413,"elapsed":36},{"frame":1414,"elapsed":37}],"terminal":[{"frame":1433,"kind":"native","data":{"sequence":10,"frame":856,"actorHandle":393223,"actor":{"slot":7,"generation":6,"fieldEpoch":6,"mapGeneration":6,"encounterGeneration":2},"eventId":13,"event":"LOGICAL_COMMIT","reasonId":0,"reason":"OK","valueA":1,"valueB":2,"actorFrame":856,"traceStream":4,"traceFieldEpoch":6}},{"frame":1433,"kind":"native","data":{"sequence":11,"frame":856,"actorHandle":393223,"actor":{"slot":7,"generation":6,"fieldEpoch":6,"mapGeneration":6,"encounterGeneration":2},"eventId":16,"event":"MOTION_FINISHED","reasonId":0,"reason":"OK","valueA":1,"valueB":2,"actorFrame":856,"traceStream":4,"traceFieldEpoch":6}},{"frame":1433,"kind":"native","data":{"sequence":12,"frame":856,"actorHandle":393223,"actor":{"slot":7,"generation":6,"fieldEpoch":6,"mapGeneration":6,"encounterGeneration":2},"eventId":20,"event":"CONTROL_RETURNED","reasonId":0,"reason":"OK","valueA":1,"valueB":1,"actorFrame":856,"traceStream":4,"traceFieldEpoch":6}}],"baselineCommitSequence":0}')


class MountedCanopyHopChecks(unittest.TestCase):
    def meter(self):return MountedCanopyHopMeasurement(SOURCE)


    def plateau_meter(self):
        meter=self.meter()
        meter.baseline=dict(actor=dict(commitSequence=PLATEAU['baselineCommitSequence']))
        meter.hop=dict(plan=deepcopy(PLATEAU['packet']['motion']['plan']),
            startSequence=3,samples=deepcopy(PLATEAU['travel']))
        return meter

    def test_actual_retained_terminal_plateau_waits_without_extra_travel_or_commit(self):
        meter=self.plateau_meter()
        for clock in PLATEAU['clocks']:
            row=deepcopy(PLATEAU['packet']);row['sample']=clock
            meter._terminal_wait(row['sample'],row['actor'],row['motion'])
            self.assertIsNone(meter.release)
            self.assertEqual(len(meter.hop['samples']),37)
        self.assertEqual([s['frame'] for s in meter.hop['terminalWaitSamples']],list(range(1415,1433)))
        self.assertEqual([e['data']['event'] for e in PLATEAU['terminal']],
            ['LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED'])
        self.assertTrue(all(e['frame']==1433 for e in PLATEAU['terminal']))
        self.assertFalse(meter.result()['passed'])

    def test_terminal_plateau_copied_faults_and_missing_travel_are_rejected(self):
        for fault in ('plan','pose','phase','reservation','stream','early-commit','event','travel-gap','elapsed'):
            meter=self.plateau_meter();row=deepcopy(PLATEAU['packet'])
            if fault=='plan':row['motion']['plan']['targetBaseY']+=1
            elif fault=='pose':row['actor']['engineObject']['pos_y']+=1
            elif fault=='phase':row['motion']['phase']='MOVING'
            elif fault=='reservation':row['actor']['reservationId']+=1
            elif fault=='stream':row['actor']['streamState']=0
            elif fault=='early-commit':row['motion']['commitPublished']=1
            elif fault=='event':meter.events=[dict(sequence=4,event='LOGICAL_COMMIT')]
            elif fault=='travel-gap':meter.hop['samples'].pop(5)
            else:row['motion']['elapsed']-=1
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'terminal stream wait'):
                meter._terminal_wait(row['sample'],row['actor'],row['motion'])

    def test_real_no_move_baseline_cannot_pass(self):
        meter=self.meter()
        with self.assertRaisesRegex(ValueError,'tree footprint/support'):
            meter.arm(deepcopy(BASELINE),BASELINE['actors'][0])
        self.assertFalse(meter.finish()['passed'])

    def test_real_native_profile_is_accepted_and_canopy_permission_is_required(self):
        meter=self.meter();actor=BASELINE['actors'][0]
        self.assertEqual(meter._profile(BASELINE,actor,CACHE),CACHE['resolvedProfiles'][0])
        for offset,value in ((92,1),(112,1),(128,0)):
            cache=deepcopy(CACHE);raw=bytearray.fromhex(cache['resolvedProfiles'][0]['resultHex'])
            raw[offset]=value;cache['resolvedProfiles'][0]['resultHex']=raw.hex()
            with self.assertRaisesRegex(ValueError,'normal Hop/LongHop'):
                meter._profile(BASELINE,actor,cache)

    def test_actual_zero_idle_motion_is_not_a_hop_or_proof(self):
        meter=self.meter();actor=BASELINE['actors'][0]
        native=meter._native(BASELINE,actor)
        self.assertEqual(native['plan']['version'],0)
        self.assertEqual(native['phase'],'IDLE')
        self.assertFalse(meter.finish()['passed'])
        with self.assertRaisesRegex(ValueError,'complete exact adjacent'):
            measurements(dict(passed=True,failures=[],observedFrames=64,measurements={KIND:meter.result()}),{})

    def test_wrong_native_owner_height_or_decoded_bytes_reject(self):
        for fault in ('owner','bytes','clock'):
            sample=deepcopy(BASELINE);target=sample['pokemonCombat']['targets'][0]
            if fault=='owner':target['personality']+=1
            elif fault=='bytes':target['motion']['plan']['targetBaseY']=1
            else:sample['pokemonCombat']['nativeCycle']+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                self.meter()._native(sample,sample['actors'][0])

    def test_missing_native_coverage_and_wrong_world_cannot_pass(self):
        for key in ('coverageComplete','installedBeforeBoot','eventsDropped','pendingUnframedEvents'):
            sample=deepcopy(BASELINE);sample['nativeObservation'][key]=False if key.endswith(('Complete','Boot')) else 1
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'coverage differs'):
                self.meter()._boundary(sample)

    def test_copied_drop_and_B_controls_mutate_real_data_and_reject_exact_reason(self):
        row=dict(phase='observe',samples=[deepcopy(BASELINE)],events=[])
        for fault in ('dropped-frame','B-input','wrong-owner'):
            negative=MountedCanopyHopNegative(fault);changed=negative.mutate(row,{})
            self.assertTrue(negative.applied)
            self.assertNotEqual(changed,row)
        for fault in FAULTS:
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'exact fault'):
                validate_negative_result(dict(passed=False,failures=['unrelated wrong clock']),fault)

    def test_exact_recipe_and_wrong_direction_B_or_long_range_setup(self):
        source=Path(__file__).resolve().parents[2]
        source=source if (source/'tests').is_dir() else ROOT
        recipe=json.loads((source/'tests/overworld/test-recipes'/f'{TEST}.json').read_text())
        validate_recipe(recipe)
        for keys in (['B'],['LEFT'],['RIGHT','B']):
            bad=deepcopy(recipe);bad['actions'][0]['args']['keys']=keys
            with self.subTest(keys=keys),self.assertRaisesRegex(ValueError,'RIGHT-only'):
                validate_recipe(bad)
        bad=deepcopy(recipe);bad['setup'][0]['args']['x']=564
        with self.assertRaisesRegex(ValueError,'adjacent-tree trigger'):validate_recipe(bad)


if __name__=='__main__':unittest.main()

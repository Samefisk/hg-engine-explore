"""Synthetic host regressions; these never grant game acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_move_entry_arrival_proof import (
    FAULTS, measurements, faulted_rows, recipe_scope)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.test_devtools_wild_walk_measurement import wild_fixture


def fixture():
    initial, _, _, travel = wild_fixture(pause=0, duration=4)
    samples = [initial, *[s for s, _ in travel]]
    for sample in samples:
        sample['context']['mapId'] = 34
        sample['fieldControl'] = dict(fieldPointer=0x2200000)
        sample['observationBoundary'] = 'main-task-queue-completion'
        sample['nativeObservation'].update(coverageComplete=True, installedBeforeBoot=True,
            eventsDropped=0, pendingUnframedEvents=0, profilesEvicted=0, error=None)
        actor = sample['actors'][0]
        actor.update(level=4, inputOwnership=0)
        actor['sourceIdentity'].update(map_id=34, level=4)
        actor['engineIdentity'].update(object_map_id=34, current_map_id=34, spawn_map_id=34)
        actor['engineObject']['unk94_y'] = actor['engineObject']['unk88_y'] = 0
    actor = initial['actors'][0]; handle = actor['handle']
    origin = [actor['logical']['x'], actor['logical']['y'], actor['engineObject']['pos_y'], 65535]
    target = [travel[-1][0]['actors'][0]['logical']['x'], travel[-1][0]['actors'][0]['logical']['y'], origin[2], 65535]
    subject = select_current_actor(initial, actor)
    world = dict(initial['context'], fieldPointer=0x2200000, statePointer=0x2300000)
    serial = 5
    def route(op, seq, frame, status=1, next_step=False):
        raw = bytearray(64);struct.pack_into('<HHI',raw,0,1,64,serial)
        bound = handle if op in (1,2) else None
        if bound:struct.pack_into('<6H',raw,8,*[handle[k] for k in ('slot','generation','fieldEpoch','mapGeneration','encounterGeneration')],0)
        if op in (0,1):struct.pack_into('<hhiHH',raw,20,*origin,0)
        if op != 3:struct.pack_into('<hhiHH',raw,32,*target,0)
        if next_step:struct.pack_into('<hhiHH',raw,44,*target,0)
        struct.pack_into('<HH4B',raw,56,3 if next_step else 0,1 if next_step else 0,status,0,int(op==0),int(next_step))
        r=dict(serial=serial,actor=bound,status=status,readsUsed=0,queued=int(op==0),hasNextStep=int(next_step),rawHex=raw.hex())
        return observation('entry-route-query',seq,frame,dict(kind='ordinary-route',operation=op,receipt=r),handle if op else None)
    def observation(kind,seq,frame,entry,bound):
        epoch,generation=world['fieldEpoch'],world['mapGeneration']
        d=dict(observation=kind,sequence=seq,entryActorFrame=frame,returnActorFrame=frame,
               entryNativeCycle=frame*2,returnNativeCycle=frame*2,
               entry=entry,subject=deepcopy(bound),slot=handle['slot'],returnValue=1,resultStatus=1,
               boundary='native-entry-route-tick-return' if kind=='entry-route-query' else 'native-entry-control-tick-return',
               routeOperation=1,cargoOwnerCredited=False,diagnosticOnly=True,acceptedProof=False,
               readBytes=dict(entry=34500,returned=34500),
               imageIdentity=dict(elfSha256='a'*64,packageSha256='b'*64,
                  loaderOwner=struct.pack('<4I2HIB3s',0x2100000,69636,0x2100040,world['fieldPointer'],epoch,generation,21,1,bytes(3)).hex()))
        return dict(frame=frame,kind='native-observation',data=d)
    raw=bytearray(30)
    struct.pack_into('<2i',raw,0,*origin[:2]);struct.pack_into('<IHB',raw,12,actor['subjectIdentity'],19,0)
    raw[19]=4;struct.pack_into('<4hBB',raw,20,*target[:2],*origin[:2],3,0)
    startup_hex=(raw[20:30]+bytes(2)+struct.pack('<i',target[2])).hex()
    spawn=dict(slot=handle['slot'],terrain=0,statePointer=world['statePointer'],fieldPointer=world['fieldPointer'],
        preparedPointer=0x2210000,worldContext=world,returnWorldContext=world,preparedPrefixHex=raw.hex(),
        preparedEncounter=dict(personality=actor['subjectIdentity'],species=19,form=0,level=4),
        startup=dict(origin=origin[:2],target=target[:2],locomotion=3,hopDirection=0,targetBaseY=target[2]),
        startupHex=startup_hex,position=origin[:2],returnValue=1,sequence=4,
        observation='spawn-prepared',publicSubject=subject)
    final=dict(spawn,observation='spawn-finalized',sequence=2,pairEligible=True)
    spawn['finalization']=dict(status='matched',receipt=final)
    spawn_event=dict(frame=initial['frame'],kind='native-observation',data=spawn)
    initial['queuedEntrySpawn']=dict(tripSerial=serial,queueSerial=serial,
        receipt=dict(status=1,queued=0,serial=serial,origin=origin,target=target))
    prepared_events=[route(0,1,initial['frame']-1,next_step=True),
        dict(frame=initial['frame'],kind='native-observation',data=deepcopy(final)),
        route(1,3,initial['frame']),spawn_event]
    receipt=dict(value=dict(species=19,slot=handle['slot'],personality=actor['subjectIdentity']),events=prepared_events)
    rows=[dict(phase='setup',command='spawn',snapshot=initial,receipt=receipt)]
    native_seq=0
    for index,(sample,events) in enumerate(travel):
        retained=[]
        if index==0:retained.append(route(2,5,sample['frame'],next_step=True))
        if index == 0 and not any(e.get('data', {}).get('event') == 'PLAN_ACCEPTED' for e in events):
            started = next(e for e in events if e.get('data', {}).get('event') == 'MOTION_STARTED')
            accepted = deepcopy(started);accepted['data']['event'] = 'PLAN_ACCEPTED'
            events = [accepted, *events]
        for event in events:
            if event['kind']!='native':continue
            event=deepcopy(event);native_seq+=1;event['data'].update(sequence=native_seq,
                actorHandle=handle['value'],actor={k:handle[k] for k in ('slot','generation','fieldEpoch','mapGeneration','encounterGeneration')},reason='OK')
            retained.append(event)
        if index==len(travel)-1:
            retained += [route(2,6,sample['frame']),route(3,7,sample['frame']),
                observation('entry-native-control',8,sample['frame'],dict(kind='native-control',operation=4,value=1),handle)]
        rows.append(dict(phase='observe',action='travel',samples=[sample],events=retained))
    return rows,dict(passed=True,failures=[],observedFrames=len(travel),subjects=dict(rattata=subject))


class MoveEntryArrivalProofTests(unittest.TestCase):
    def test_existing_motion_and_native_receipts_prove_one_exact_arrival(self):
        rows,replay=fixture();result=measurements(rows,replay)
        self.assertEqual(result['completeMotions'],1)
        self.assertEqual(result['queuedPreparationReceipts'],1)
        self.assertEqual(len(result['measurements']),5)

    def test_missing_stale_false_arrival_and_clear_controls_reach_selected_trip(self):
        for fault in FAULTS:
            rows,replay=fixture()
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                measurements(faulted_rows(rows,fault),replay)

    def test_queued_ready_is_not_birth_or_arrival(self):
        rows,replay=fixture()
        with self.assertRaisesRegex(ValueError,'trip clear'):
            measurements(rows[:1],replay)

    def test_wrong_height_and_missing_dense_travel_are_rejected(self):
        rows,replay=fixture();last=rows[-1]['samples'][0]
        last['actors'][0]['engineObject']['pos_y']+=1
        with self.assertRaises(ValueError):measurements(rows,replay)
        rows,replay=fixture();del rows[2]
        with self.assertRaisesRegex(ValueError,'frames missing'):measurements(rows,replay)

    def test_generic_recipe_and_native_target_scope_are_exact(self):
        p=Path(__file__).resolve().parents[2]/'tests/overworld/test-recipes/spawn.move-entry.arrival.json'
        test=validate_test(json.loads(p.read_text()));self.assertTrue(recipe_scope(test))
        for key,value in (('x',561),('level',5),('form',1)):
            changed=deepcopy(test);changed['setup'][2]['args'][key]=value
            self.assertFalse(recipe_scope(changed))


if __name__=='__main__':unittest.main()

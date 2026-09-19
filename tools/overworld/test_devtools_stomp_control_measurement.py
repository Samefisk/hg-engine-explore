"""Same reader host receipts; no generated terminal receipt is ROM proof."""
from copy import deepcopy
import struct
import unittest
import json
from pathlib import Path

from tools.overworld import test_devtools_stomp_control as native_fixture
from tools.overworld.devtools_stomp_control import calibrate_stomp_policy, BAD_THRESHOLD
from tools.overworld.devtools_stomp_control_measurement import validate_control, StompControlMeasurement


def native_control_fixture():
    reader,session,actor,regs,put,writes,aborts=native_fixture.StompControlTests().fixture()
    # The lower-level reader fixture tests memory restoration, not pair physics.
    # Give this host-only fixture a complete valid west-facing pair.
    old_object=session.rt.object_state;old_signed=session.rt.signed
    player=reader.owner['playerPointer'];mount=reader.owner['mountPointer']
    def object_state(emu,pointer):
        return dict(old_object(emu,pointer),facing=2,face_x=32768 if pointer==player else 0,
            face_y=32768 if pointer==player else 0,face_z=0,
            unk88_x=0,unk88_y=0,unk94_x=0,unk94_y=0)
    session.rt.object_state=object_state
    session.rt.signed=lambda emu,address,size=4: 0 if address in {
        player+0x90,player+0x9c,mount+0x90,mount+0x9c} else old_signed(emu,address,size)
    reader.latest_completed_pose.update(reader._read_pose(reader._current()))
    control=calibrate_stomp_policy(reader)
    clean=control['clean'];current=clean['current']
    terminal_actor=dict(deepcopy(actor),identityVerified=True,engineIdentity=deepcopy(reader.subject['engineIdentity']),
        sourceIdentity=deepcopy(current['sourceIdentity']),engineObject=deepcopy(clean['pose']['mount']),
        movementPolicy=dict(pending=0))
    terminal=dict(frame=session.completed_frames,**reader.observer._clock(),actors=[terminal_actor],
        context=deepcopy(current['worldContext']),player=deepcopy(clean['pose']['player']))
    return control,deepcopy(reader.latest),terminal,reader.subject


def enrich_control_rows(rows,first):
    actor=first['actors'][0]
    personality=actor['subjectIdentity']
    binding_raw=struct.pack('<IHHHHBBBB',personality,155,33,actor['handle']['mapGeneration'],
        actor['handle']['encounterGeneration'],0,10,0,0)
    binding=dict(bindingHex=binding_raw.hex(),sessionGeneration=1,fieldPointer=0x02280000,surfacePointer=0x02290000)
    def enrich(value):
        if isinstance(value,dict):
            if 'handle' in value and isinstance(value['handle'],dict):
                value['handle']['slot']=7
                value['handle']['value']=(value['handle']['generation']<<16)|7
            if 'actorHandle' in value:
                value['actorHandle']=(value['actorHandle'] & ~0xffff)|7
                value['actor']['slot']=7
            if value.get('role')=='MOUNTED' and 'motionPhase' in value:
                value.setdefault('form',0);value.setdefault('level',10)
            for key in ('context','worldContext'):
                if key in value:value[key]['mapId']=33
            if 'sourceIdentity' in value:
                value['sourceIdentity'].update(personality=personality,species=155,active=1,object_id=231,
                    map_id=33,encounter_generation=actor['handle']['encounterGeneration'])
            if 'engineIdentity' in value and 'in_manager' in value['engineIdentity']:
                value['engineIdentity']['current_map_id']=33
            if value.get('kind')=='policy':value['mountBinding']=deepcopy(binding)
            if 'policyHex' in value:
                raw=bytearray.fromhex(value['policyHex']);raw[8]=7;value['policyHex']=raw.hex()
            if value.get('observation')=='walk-policy':
                value['slot']=7
                for key in ('requestHex','responseHex'):
                    raw=bytearray.fromhex(value[key]);raw[8]=7;value[key]=raw.hex()
            for child in value.values():enrich(child)
        elif isinstance(value,list):
            for child in value:enrich(child)
    enrich(rows)
    return binding_raw,binding


def host_control_fixture():
    """Complete synthetic stream and terminal receipt, never accepted game data."""
    from tools.overworld.test_devtools_stomp_measurement import fixture
    rows=fixture()
    binding_raw,binding=enrich_control_rows(rows,rows[0]['snapshot'])
    meter=StompControlMeasurement(100)
    for row in rows:
        row=deepcopy(row);op=row.pop('op')
        if op=='close':break
        getattr(meter,op)(**row)
        if meter.failures:raise AssertionError(meter.failures)
    if not meter.natural.ready:raise AssertionError(meter.natural.finish())
    return control_receipt_for(meter,binding_raw,binding)


def control_receipt_for(meter,binding_raw,binding):
    terminal=deepcopy(meter.last);actor=terminal['actors'][0]
    prior=deepcopy(meter.natural.cases[-1]['feedback']['calls'][-1])
    current=deepcopy(prior['before']);current['publicSubject']=deepcopy(actor)
    state=bytearray(184);struct.pack_into('<II',state,0,binding['fieldPointer'],binding['surfacePointer'])
    state[8:80]=bytes.fromhex(prior['profileHex']);state[80:96]=binding_raw
    struct.pack_into('<I',state,96,1);state[100]=2
    clean=dict(current=current,profile=dict(profileHex=state[8:80].hex(),stompTime=2),mountBinding=binding,
        mountStateHex=state.hex(),pose=dict(current,
            player=deepcopy(terminal['stompFeedback']['latestCompletedPose']['player']),
            mount=deepcopy(terminal['stompFeedback']['latestCompletedPose']['mount']),
            avatarControl=dict(flags=0,moveState=0,playerMoveState=0)),
        input=dict(heldKeys=0,newKeys=0,rawHeld=0,rawNew=0,simulatedKeys=0))
    bad=bytearray(state);bad[78]=255
    clock={k:terminal[k] for k in ('frame','actorFrame','nativeCycle')}
    registers={k:0 for k in (*('r'+str(i) for i in range(16)),'cpsr','spsr')}
    control=dict(state='complete',failure=None,cleanupPending=False,acceptedProof=False,terminal=True,
        readerClosed=True,readerFailure=BAD_THRESHOLD,guestInstructionAdvance=0,guestMemoryWrites=2,
        clean=clean,restored=deepcopy(clean),bad=dict(mountStateHex=bad.hex(),failure=BAD_THRESHOLD),policyReceipt=prior,
        stateAddress=0x023BC744,stateBytes=184,changedAddress=0x023BC744+78,changedOffset=78,profileOffset=70,
        originalHex='02',changedHex='ff',clock=clock,restoredClock=deepcopy(clock),
        registers=registers,restoredRegisters=deepcopy(registers))
    reader=dict(terminal['stompFeedback'],closed=True,failure=BAD_THRESHOLD,guestMemoryWrites=2,calibration=control)
    receipt=dict(prepared=True,acceptedProof=False,advancedFrames=0,terminalGuard=True,
        calibration=control,snapshot=terminal,stompFeedback=reader)
    return meter,receipt,terminal


class StompControlMeasurementTests(unittest.TestCase):
    def test_full_two_case_baseline_then_terminal_control(self):
        meter,receipt,terminal=host_control_fixture()
        self.assertFalse(meter.ready)
        self.assertFalse(meter.result()['passed'])
        meter.calibrate(receipt,terminal)
        self.assertTrue(meter.ready);self.assertFalse(meter.result()['passed'])
        meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=terminal,
            stompFeedback=receipt['stompFeedback']),terminal)
        result=meter.finish()
        self.assertTrue(result['passed'],result['failures'])
        self.assertFalse(result['acceptedProof'])

    def test_actual_reader_receipt_revalidates_exact_fault_and_restore(self):
        control,policy,terminal,subject=native_control_fixture()
        validate_control(control,policy,terminal,subject)
        self.assertEqual(control['readerFailure'],BAD_THRESHOLD)
        self.assertTrue(control['readerClosed'])
        self.assertFalse(control['acceptedProof'])

    def test_native_only_z_fields_are_checked_not_filled_or_discarded(self):
        control,policy,terminal,subject=native_control_fixture()
        for obj in (terminal['player'],terminal['actors'][0]['engineObject']):
            obj.pop('unk88_z');obj.pop('unk94_z')
        validate_control(control,policy,terminal,subject)
        for fault in ('extra','missing','public','pair'):
            changed=deepcopy(control)
            pose=changed['clean']['pose']['player']
            if fault=='extra':pose['unknown_extra']=1
            elif fault=='missing':pose.pop('unk88_z')
            elif fault=='public':pose['pos_x']+=1
            else:pose['unk88_z']+=1
            changed['restored']=deepcopy(changed['clean'])
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                validate_control(changed,policy,terminal,subject)

    def test_retained_frame_778_native_pair(self):
        # The old diagnostic has no public snapshot or terminalGuard. It proves
        # only the actual native pair shape, never a complete control scenario.
        from tools.overworld.devtools_stomp_measurement import same_completed_object
        from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
        path=Path(__file__).resolve().parents[2]/'build/overworld-devtools/session-a8jhx9sl/event-details-cdbf0b8c9eaf.json'
        if not path.exists():self.skipTest('optional retained frame 778 diagnostic absent')
        row=json.loads(path.read_text());self.assertEqual(row['startFrame'],778)
        control=row['receipt']['calibration'];pose=control['clean']['pose']
        self.assertEqual(control['clean'],control['restored'])
        check_pair_pose(pose)
        for role in ('player','mount'):
            public={k:v for k,v in pose[role].items() if k not in ('unk88_z','unk94_z')}
            self.assertTrue(same_completed_object(public,pose[role]))
            changed=deepcopy(pose);changed[role]['unk88_z']+=1
            with self.assertRaises(ValueError):check_pair_pose(changed)

    def test_each_native_fact_and_restoration_is_required(self):
        for fault in ('actor','policy','address','raw','binding','bad','restore','pose','input','clock','registers','latch','advance'):
            control,policy,terminal,subject=native_control_fixture()
            if fault=='actor':terminal['actors'][0]['authorityGeneration']+=1
            elif fault=='policy':policy['stompTime']+=1
            elif fault=='address':control['changedAddress']+=1
            elif fault=='raw':control['clean']['profile']['stompTime']+=1
            elif fault=='binding':control['clean']['mountBinding']['sessionGeneration']+=1
            elif fault=='bad':control['bad']['mountStateHex']=control['clean']['mountStateHex']
            elif fault=='restore':control['restored']['mountStateHex']=control['bad']['mountStateHex']
            elif fault=='pose':
                control['clean']['pose']['player']['pos_x']+=1
                control['restored']=deepcopy(control['clean'])
            elif fault=='input':
                control['clean']['input']['heldKeys']=1;control['restored']=deepcopy(control['clean'])
            elif fault=='clock':control['restoredClock']['nativeCycle']+=1
            elif fault=='registers':control['restoredRegisters']['r0']+=1
            elif fault=='latch':control['readerFailure']=None
            else:control['guestInstructionAdvance']=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError,TypeError)):
                validate_control(control,policy,terminal,subject)

    def test_baseline_required_and_no_gameplay_after_control(self):
        meter=StompControlMeasurement(100)
        with self.assertRaisesRegex(ValueError,'complete positive and negative baseline'):meter.calibrate({}, {})
        self.assertFalse(meter.ready)
        meter.control={}
        with self.assertRaisesRegex(ValueError,'after calibration'):meter.command({}, {})
        with self.assertRaisesRegex(ValueError,'after calibration'):meter.configure({}, {})
        result=meter.observe({},[])
        self.assertFalse(result['passed'])
        self.assertIn('stomp control observed gameplay after calibration',result['failures'])


if __name__=='__main__':unittest.main()

"""Stopped-guest motion-state reader validation, not a timing-fault test."""
from copy import deepcopy

from tools.overworld.devtools_walk_matrix_observer import MOTION_BYTES

BAD_ENUM = "Walk matrix motion state enum is invalid"
PHASE_OFFSET = 48  # Compiled real OverworldMotionState.phase layout anchor.


class WalkMatrixControlError(RuntimeError):
    code = "walk-matrix-control-invalid"


def require(ok, reason):
    if not ok:
        raise WalkMatrixControlError(reason)


def calibrate_walk_matrix(reader):
    """Write one invalid phase byte, invoke the same reader, restore exactly.

    The owning shared session must prohibit later guest execution, including
    after failure. This function never drives the guest or publishes a tick.
    """
    s=reader.session
    require(reader.calibration is None and reader.armed and not reader.closed and reader.failure is None
        and s.emu is not None and s.prepared and not s.native_bridge_active and not reader.data
        and reader.counts['ticks']==reader.completed_count and reader.completed_count>0
        and reader.last_moving_tick is not None
        and s.rom.resolve().is_relative_to(s.directory.resolve())
        and s.rom.resolve()!=(s.rt.REPO/'test.nds').resolve(),
        'Walk matrix calibration requires an owned paused reader after real Walk ticks')
    control=dict(state='checking',failure=None,cleanupPending=False,acceptedProof=False,
        guestInstructionAdvance=0,guestMemoryWrites=0,
        scope='observer-control-only; motion-state reader validation, not a timing-fault or gameplay test')
    reader.calibration=control
    regs=s.emu.memory.register_arm9
    def registers():
        return {name:getattr(regs,name) for name in (*('r'+str(i) for i in range(16)),'cpsr','spsr')}
    def clock():
        return dict(reader.observer._clock(),frame=s.completed_frames)
    def capture():
        reader._live_code()
        current=reader._current()
        return dict(current=current,motion=reader._read_motion(reader.motion_pointer),
            input=deepcopy(s._selector_observation()),
            player=s.rt.object_state(s.emu,current['playerPointer']),
            mount=s.rt.object_state(s.emu,current['mountPointer']))
    try:
        clean=capture()
        current=clean['current'];actor=current['publicSubject'];motion=clean['motion']
        boundary=reader.latest_completed
        require(isinstance(boundary,dict) and boundary['current']==current and boundary['frame']==s.completed_frames
            and boundary['actorFrame']==clock()['actorFrame'] and boundary['nativeCycle']<=clock()['nativeCycle'],
            'Walk matrix calibration lacks a current completed boundary')
        require(actor['species']==155 and actor['role']=='MOUNTED' and actor['motionPhase']=='IDLE'
            and actor['motionKind']=='NONE' and actor['reservationId']==0 and actor['inputOwnership']==1
            and motion['phase']=='IDLE', 'Walk matrix calibration requires idle mounted Cyndaquil')
        require(all(type(clean['input'].get(key)) is int and clean['input'][key]==0
            for key in ('heldKeys','newKeys','rawHeld','rawNew','simulatedKeys')),
            'Walk matrix calibration requires released normal input')
        prior=reader.last_moving_tick
        require(prior['qualification']=='moving-walk' and prior['phaseBefore']=='MOVING'
            and prior['phaseAfter']=='COMMIT_PENDING' and prior['returnFlags'] & 12 == 12
            and prior['duration']>0 and prior['returnElapsed']==prior['duration']
            and prior['completedFrame']<s.completed_frames and prior['fieldEpoch']==current['worldContext']['fieldEpoch']
            and motion['plan']['kind']==1 and motion['plan']['reservationId']==prior['reservationId']
            and motion['plan']['duration']==prior['duration'] and motion['elapsed']==prior['returnElapsed'],
            'Walk matrix calibration lacks its completed native Walk')
        original=bytes.fromhex(motion['rawHex'])
        address=reader.motion_pointer
        require(len(original)==MOTION_BYTES and original[PHASE_OFFSET]==0 and s.read(address,MOTION_BYTES)==original,
                'Walk matrix calibration original motion bytes differ')
        before_clock,before_regs=clock(),registers()
        changed=bytearray(original);changed[PHASE_OFFSET]=255
        control.update(clean=clean,motionPointer=address,stateBytes=MOTION_BYTES,changedAddress=address+PHASE_OFFSET,
            changedOffset=PHASE_OFFSET,originalHex='00',changedHex='ff',priorMovingTick=deepcopy(prior),
            clock=before_clock,registers=before_regs,cleanupPending=True)
        try:
            control['guestMemoryWrites']+=1;s.write(address+PHASE_OFFSET,b'\xff')
            bad_raw=s.read(address,MOTION_BYTES)
            require(bad_raw==bytes(changed),'Walk matrix phase fault changed unrelated bytes')
            failure=None
            try:reader._read_motion(address)
            except ValueError as error:failure=str(error)
            control['bad']=dict(rawHex=bad_raw.hex(),failure=failure)
            require(failure==BAD_ENUM,'same Walk matrix reader did not reject invalid phase')
            require(reader._current()==current and clock()==before_clock and registers()==before_regs,
                    'Walk matrix fault changed owner or execution boundary')
        finally:
            try:
                control['guestMemoryWrites']+=1;s.write(address+PHASE_OFFSET,original[PHASE_OFFSET:PHASE_OFFSET+1])
                restored=capture()
                control.update(restored=restored,restoredClock=clock(),restoredRegisters=registers())
                require(s.read(address,MOTION_BYTES)==original and restored==clean,
                        'Walk matrix exact motion or owner restoration differs')
                require(control['restoredClock']==before_clock and control['restoredRegisters']==before_regs,
                        'Walk matrix restored execution boundary differs')
                control['cleanupPending']=False
            except Exception as error:
                control.update(state='failed',failure=str(error))
                s.abort_native_control(WalkMatrixControlError(str(error)))
                raise
        control['state']='complete'
        return deepcopy(control)
    except Exception as error:
        control.update(state='failed',failure=str(error))
        raise

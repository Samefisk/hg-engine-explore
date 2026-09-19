"""Terminal same-reader invalid-mode control; no Crash gameplay acceptance."""
from copy import deepcopy

from tools.overworld.devtools_mounted_crash_observer import STATE_BYTES, MODE_OFFSET
from tools.overworld.devtools_observer import NativeObservationError

BAD_MODE = 'mounted pacing: crash state fields invalid'
EXPECTED_COUNTS = dict(start=1,update=33,presentation=32,finish=1,crashSound=1,sound=1,soundStart=1)


class MountedCrashControlError(RuntimeError):
    code = 'mounted-crash-control-invalid'


def require(ok, reason):
    if not ok:raise MountedCrashControlError(reason)


def calibrate_mounted_crash(reader):
    """Reject mode255 via the same _sample; restore its byte and close forever.

    Caller must first require its full Crash measurement ready, then set
    session.crash_calibrated=True and permanently gate future stepping on it.
    That guard must survive errors. This function does not set or clear it.
    All184 state bytes, owner, paired pose, input, registers and both clock
    receipts must remain exact. Only the mode byte is written, twice. A failed
    restore aborts the native control; no register/pose repair is attempted.
    """
    s=reader.session
    require(getattr(s,'crash_calibrated',False) is True
        and getattr(reader,'calibration',None) is None and reader.armed and not reader.closed
        and reader.failure is None and s.emu is not None and s.prepared
        and not s.native_bridge_active and not reader.active and not reader.data
        and not reader.observer.contexts and reader.counts==EXPECTED_COUNTS
        and isinstance(reader.latest,dict) and reader.latest.get('normalReturn') is True
        and reader.latest.get('kind')=='update'
        and s.rom.resolve().is_relative_to(s.directory.resolve())
        and s.rom.resolve()!=(s.rt.REPO/'test.nds').resolve(),
        'Crash calibration requires terminal guard and owned paused completed reader')
    receipt=dict(state='checking',failure=None,cleanupPending=False,acceptedProof=False,
        guestInstructionAdvance=0,guestMemoryWrites=0,terminal=True,
        scope='observer-control-only; invalid mounted mode reader, not Crash gameplay proof')
    reader.calibration=receipt
    regs=s.emu.memory.register_arm9

    def registers():
        return {k:getattr(regs,k) for k in (*('r'+str(i) for i in range(16)),'cpsr','spsr')}

    def clock():
        guest=s.emu.guest_clock()
        require(guest.get('version')==1 and guest.get('running') is False
            and guest.get('scope')=='nds-scheduler-ticks-not-cpu-or-instructions',
            'Crash calibration requires paused native guest clock')
        return dict(reader.observer._clock(),frame=s.completed_frames,guestClock=deepcopy(guest))

    def capture():
        reader._live_code()
        return dict(sample=reader._sample(),input=deepcopy(s._selector_observation()))

    try:
        initial_clock=clock();initial_registers=registers();clean=capture()
        sample=clean['sample'];current=sample['current'];actor=current['publicSubject']
        prior=reader.latest;boundary=reader.latest_completed
        require(isinstance(boundary,dict) and boundary.get('boundary')=='main-task-queue-completion'
            and boundary.get('frame')==s.completed_frames and boundary.get('actorFrame')==initial_clock['actorFrame']
            and type(boundary.get('nativeCycle')) is int and boundary['nativeCycle']<=initial_clock['nativeCycle']
            and all(boundary.get(k)==v for k,v in sample.items()),
            'Crash calibration lacks current completed native boundary')
        require(actor.get('species')==155 and actor.get('role')=='MOUNTED' and actor.get('active') is True
            and actor.get('presentationAttached') is True and actor.get('inputOwnership')==1
            and actor.get('motionPhase')=='IDLE' and actor.get('motionKind')=='NONE'
            and actor.get('reservationId')==0
            and (sample['mode'],sample['duration'],sample['elapsed'])==(0,0,0),
            'Crash calibration requires idle attached mounted Cyndaquil')
        require(all(type(clean['input'].get(k)) is int and clean['input'][k]==0
            for k in ('heldKeys','newKeys','rawHeld','rawNew','simulatedKeys')),
            'Crash calibration requires released normal input')
        old=prior['after']['current'];old_actor=old['publicSubject']
        require((prior['before']['mode'],prior['before']['duration'],prior['before']['elapsed'])==(3,32,32)
            and (prior['after']['mode'],prior['after']['duration'],prior['after']['elapsed'])==(0,0,0)
            and prior['completedFrame']<s.completed_frames
            and all(old[k]==current[k] for k in ('subject','sourceIdentity','engineIdentity','worldContext',
                'playerPointer','mountPointer','avatarPointer'))
            and prior['after']['mountBinding']==sample['mountBinding']
            and actor['commitSequence']==old_actor['commitSequence']+1
            and abs(actor['logical']['x']-old_actor['logical']['x'])
                +abs(actor['logical']['y']-old_actor['logical']['y'])==1,
            'Crash calibration lacks completed crash and one recovery commit')
        original=bytes.fromhex(sample['mountStateHex'])
        require(len(original)==STATE_BYTES and original[MODE_OFFSET]==0,
            'Crash full state differs from idle mode reader')
        changed=bytearray(original);changed[MODE_OFFSET]=255;address=reader.mount_state+MODE_OFFSET
        receipt.update(clean=clean,terminalCrashReceipt=deepcopy(prior),stateAddress=reader.mount_state,
            stateBytes=STATE_BYTES,changedAddress=address,changedOffset=MODE_OFFSET,
            field='snapshot.motionMode',originalHex='00',changedHex='ff',clock=initial_clock,
            registers=initial_registers,cleanupPending=True)
        try:
            receipt['guestMemoryWrites']+=1;s.write(address,b'\xff')
            bad=s.read(reader.mount_state,STATE_BYTES)
            require(bad==bytes(changed),'Crash fault changed unrelated mounted state')
            failure=None
            try:reader._sample()
            except NativeObservationError as error:failure=str(error)
            receipt['bad']=dict(mountStateHex=bad.hex(),failure=failure)
            require(failure==BAD_MODE and reader.failure==BAD_MODE,
                'same Crash reader did not latch invalid mode')
            require(clock()==initial_clock and registers()==initial_registers,'Crash control advanced native execution')
        finally:
            try:
                receipt['guestMemoryWrites']+=1;s.write(address,original[MODE_OFFSET:MODE_OFFSET+1])
                restored=capture()
                receipt.update(restored=restored,restoredClock=clock(),restoredRegisters=registers())
                require(s.read(reader.mount_state,STATE_BYTES)==original and restored==clean,
                    'Crash exact state, identity, input or pose restoration differs')
                require(receipt['restoredClock']==initial_clock and receipt['restoredRegisters']==initial_registers,
                    'Crash restored execution boundary differs')
                receipt['cleanupPending']=False
            except Exception as error:
                receipt.update(state='failed',failure=str(error))
                s.abort_native_control(MountedCrashControlError(str(error)));raise
        require(reader.failure==BAD_MODE,'Crash reader failure latch changed')
        receipt.update(state='complete',readerFailure=reader.failure)
    except Exception as error:
        reader.failure=reader.failure or 'mounted crash control: '+str(error)
        receipt.update(state='failed',failure=str(error));raise
    finally:
        try:
            reader.close();receipt.update(readerClosed=reader.closed,readerFailure=reader.failure)
            require(reader.closed and not reader.active and not reader.data
                and all(t not in reader.observer.tokens and t not in reader.observer.return_tokens
                    for t in reader.entries+reader.returns),'Crash terminal reader cleanup differs')
        except Exception as error:
            reader.failure=reader.failure or 'mounted crash control: '+str(error)
            receipt.update(state='failed',failure=str(error),cleanupPending=True)
            s.abort_native_control(MountedCrashControlError(str(error)));raise
    return deepcopy(receipt)

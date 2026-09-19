"""Completed natural Crash, then one terminal same-reader mode control."""
from copy import deepcopy
import struct

from .devtools_mounted_crash_measurement import MountedCrashMeasurement
from .devtools_mounted_crash_control import BAD_MODE, EXPECTED_COUNTS
from .devtools_mounted_crash_observer import STATE_ADDRESS, STATE_BYTES, MODE_OFFSET, DURATION_OFFSET
from .devtools_records import select_current_actor
from .devtools_wild_walk_measurement import IDENTITY

KIND = 'live-crash-control-v1'
REQUIREMENT = 'shared.crash-recorder-control-v1'


def require(ok, reason):
    if not ok: raise ValueError('Crash control '+reason)


def _body(receipt):
    envelope = {'observation','sequence','entryActorFrame','entryNativeCycle',
                'returnActorFrame','returnNativeCycle','setupMode'}
    return {k: v for k, v in receipt.items() if k not in envelope}


def validate_control(control, terminalCrashReceipt, terminalSnapshot, subject):
    c, terminal = control, terminalSnapshot
    require(isinstance(c,dict) and c.get('state')=='complete' and c.get('failure') is None
        and c.get('cleanupPending') is False and c.get('terminal') is True
        and c.get('readerClosed') is True and c.get('readerFailure')==BAD_MODE
        and c.get('acceptedProof') is False
        and type(c.get('guestInstructionAdvance')) is int and c['guestInstructionAdvance']==0
        and type(c.get('guestMemoryWrites')) is int and c['guestMemoryWrites']==2,
        'missing restoration or terminal failure latch')
    clean=c['clean'];sample=clean['sample'];current=sample['current']
    selected=select_current_actor(terminal,subject)
    actor=next(a for a in terminal['actors'] if a['handle']==selected['handle'])
    require(current['subject']==subject and actor['species']==155 and actor['role']=='MOUNTED'
        and actor['inputOwnership']==1 and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE'
        and actor['reservationId']==0 and actor['movementPolicy']['pending']==0
        and all(current['publicSubject'].get(k)==actor.get(k) for k in
                (*IDENTITY,'logical','commitSequence','motionKind','motionPhase','reservationId','inputOwnership')),
        'terminal actor differs')
    boundary=terminal['crashFeedback']['latestCompleted']
    require(boundary.get('boundary')=='main-task-queue-completion'
        and all(boundary[k]==terminal[k] for k in ('frame','actorFrame','nativeCycle'))
        and all(boundary.get(k)==v for k,v in sample.items()),'terminal native sample differs')
    prior=terminalCrashReceipt
    require(_body(c['terminalCrashReceipt'])==_body(prior) and prior['kind']=='update'
        and prior['normalReturn'] is True and prior['completedFrame']<terminal['frame']
        and tuple(prior['before'][k] for k in ('mode','duration','elapsed'))==(3,32,32)
        and tuple(prior['after'][k] for k in ('mode','duration','elapsed'))==(0,0,0),
        'terminal crash call differs')
    old=prior['after']['current'];old_actor=old['publicSubject']
    require(all(old[k]==current[k] for k in ('subject','sourceIdentity','engineIdentity','worldContext',
        'playerPointer','mountPointer','avatarPointer'))
        and prior['after']['mountBinding']==sample['mountBinding']
        and actor['commitSequence']==old_actor['commitSequence']+1
        and actor['logical']==dict(x=old_actor['logical']['x']+1,y=old_actor['logical']['y']),
        'recovery owner or commit differs')
    raw=bytes.fromhex(sample['mountStateHex'])
    require(c.get('stateAddress')==STATE_ADDRESS and c.get('stateBytes')==STATE_BYTES
        and c.get('changedAddress')==STATE_ADDRESS+MODE_OFFSET and c.get('changedOffset')==MODE_OFFSET
        and c.get('field')=='snapshot.motionMode' and c.get('originalHex')=='00' and c.get('changedHex')=='ff'
        and len(raw)==STATE_BYTES and raw[MODE_OFFSET]==0
        and struct.unpack_from('<HH',raw,DURATION_OFFSET)==(0,0)
        and tuple(sample[k] for k in ('mode','duration','elapsed'))==(0,0,0), 'mode address or bytes differ')
    changed=bytearray(raw);changed[MODE_OFFSET]=255
    require(c['bad']==dict(mountStateHex=changed.hex(),failure=BAD_MODE) and c['restored']==clean,
        'same-reader fault or exact restoration differs')
    require(all(type(clean['input'].get(k)) is int and clean['input'][k]==0
        for k in ('heldKeys','newKeys','rawHeld','rawNew','simulatedKeys')),'input not released')
    clock=c['clock'];guest=clock['guestClock']
    require(set(clock)=={'frame','actorFrame','nativeCycle','guestClock'}
        and all(type(clock[k]) is int and clock[k]>=0 for k in ('frame','actorFrame','nativeCycle'))
        and clock['frame']==terminal['frame'] and clock['actorFrame']==terminal['actorFrame']
        and clock['nativeCycle']>=terminal['nativeCycle'] and c['restoredClock']==clock
        and type(guest.get('version')) is int and guest['version']==1 and guest.get('running') is False
        and guest.get('scope')=='nds-scheduler-ticks-not-cpu-or-instructions'
        and all(type(guest.get(k)) is int and 0<=guest[k]<(1<<64)
                for k in ('arm9Timestamp','arm7Timestamp','frameSequence')),'execution clocks differ')
    registers=c['registers']
    require(set(registers)=={*('r'+str(i) for i in range(16)),'cpsr','spsr'}
        and registers==c['restoredRegisters']
        and all(type(v) is int and 0<=v<=0xffffffff for v in registers.values()),'registers differ')
    return True


class MountedCrashControlMeasurement:
    def __init__(self,max_frames):
        self.natural=MountedCrashMeasurement(max_frames)
        self.control=self.cleanup=self.calibration_receipt=self.terminal=None
        self.closed=False;self._failures=[]
    def __getattr__(self,name):return getattr(self.natural,name)
    @property
    def failures(self):return self._failures+list(self.natural.failures)
    @property
    def ready(self):return self.natural.ready and self.control is not None and not self.failures
    def command(self,*args,**kwargs):
        require(self.control is None and not self.closed,'command after calibration')
        return self.natural.command(*args,**kwargs)
    def observe(self,snapshot,events):
        if self.control is not None or self.closed:self._failures.append('Crash control gameplay after calibration')
        elif not self.failures:self.natural.observe(snapshot,events)
        return self.result()
    def _reader(self,reader,snapshot):
        require(reader.get('closed') is True and reader.get('failure')==BAD_MODE
            and reader.get('guestMemoryWrites')==2 and reader.get('calibration')==self.control
            and reader.get('counts')==EXPECTED_COUNTS,'terminal reader differs')
        # Normalize a detached proof value only, after checking the real latch.
        self.natural._reader(dict(reader,failure=None,guestMemoryWrites=0,calibration=None),snapshot,True)
    def calibrate(self,receipt,snapshot):
        require(self.natural.ready and not self.failures and self.control is None and not self.closed,
                'requires complete natural crash and recovery')
        from .devtools_test_contract import _same_mounted_reader_boundary
        require(receipt.get('prepared') is True and receipt.get('acceptedProof') is False
            and receipt.get('advancedFrames')==0 and receipt.get('terminalGuard') is True
            and receipt.get('snapshot')==snapshot
            and _same_mounted_reader_boundary(self.natural.last,snapshot)
            and {k:v for k,v in snapshot.items() if k not in ('nativeObservation','crashFeedback')}
                == {k:v for k,v in self.natural.last.items() if k not in ('nativeObservation','crashFeedback')}
            and set(snapshot['nativeObservation'])-set(self.natural.last['nativeObservation']) == {'resolvedProfiles'}
            and all(snapshot['nativeObservation'].get(k)==v for k,v in self.natural.last['nativeObservation'].items()
                    if k!='resolvedProfiles')
            and snapshot.get('crashFeedback')==receipt.get('crashFeedback'),
            'runtime terminal guard or boundary differs')
        validate_control(receipt.get('calibration'),self.natural.calls['update'][-1],snapshot,self.subject)
        self.control=deepcopy(receipt['calibration'])
        self._reader(receipt['crashFeedback'],snapshot)
        self.calibration_receipt=deepcopy(receipt);self.terminal=deepcopy(snapshot)
        return self.result()
    def close(self,receipt,snapshot):
        from .devtools_test_contract import _same_mounted_reader_boundary
        require(self.ready and not self.closed and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and receipt.get('snapshot')==snapshot and _same_mounted_reader_boundary(self.terminal,snapshot)
            and {k:v for k,v in snapshot.items() if k!='crashFeedback'}
                == {k:v for k,v in self.terminal.items() if k!='crashFeedback'}
            and snapshot.get('crashFeedback')==receipt.get('crashFeedback'),
            'cleanup boundary differs')
        self._reader(receipt['crashFeedback'],snapshot)
        self.closed=True;self.cleanup=deepcopy(receipt)
        return self.result()
    def finish(self):
        if not self.ready or not self.closed:
            if not self.failures:self._failures.append('Crash control incomplete')
        return self.result()
    def result(self):
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,closed=self.closed,
            acceptedProof=False,subject=self.subject,frames=self.frames,failures=self.failures,
            stage=self.natural.result()['stage'],natural=self.natural.result(full=True),
            terminal=self.terminal,control=self.control,calibrationReceipt=self.calibration_receipt,cleanup=self.cleanup))

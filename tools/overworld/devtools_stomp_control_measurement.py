"""Two normal Stomp cases followed by one terminal same-reader control."""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_stomp_control import BAD_THRESHOLD, THRESHOLD_OFFSET
from tools.overworld.devtools_stomp_contract import validate_stomp
from tools.overworld.devtools_stomp_measurement import same_completed_object
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
from tools.overworld.devtools_wild_walk_measurement import IDENTITY

KIND = 'live-stomp-control-v1'


def require(value, reason):
    if not value:raise ValueError('stomp control '+reason)


def policy_body(value):
    """Drop only the shared event envelope, not a native policy field."""
    envelope={'observation','sequence','entryActorFrame','entryNativeCycle','returnActorFrame','returnNativeCycle','setupMode'}
    return {k:deepcopy(v) for k,v in value.items() if k not in envelope}


def validate_control(control, policy, terminal, subject):
    require(isinstance(control,dict) and control.get('state')=='complete' and control.get('failure') is None
        and control.get('cleanupPending') is False and control.get('acceptedProof') is False
        and control.get('terminal') is True and control.get('readerClosed') is True
        and control.get('readerFailure')==BAD_THRESHOLD
        and type(control.get('guestInstructionAdvance')) is int and control['guestInstructionAdvance']==0
        and type(control.get('guestMemoryWrites')) is int and control['guestMemoryWrites']==2,
        'is missing, not restored, or not terminal')
    selected=select_current_actor(terminal,subject)
    actor=next(a for a in terminal['actors'] if a['handle']==selected['handle'])
    clean=control['clean'];current=clean['current'];profile=clean['profile']
    require(current['subject']==subject and actor['species']==155 and actor['role']=='MOUNTED'
        and actor['inputOwnership']==1 and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE'
        and actor['reservationId']==0 and actor['movementPolicy']['pending']==0
        and all(current['publicSubject'].get(k)==actor.get(k) for k in
            (*IDENTITY,'logical','commitSequence','motionKind','motionPhase','reservationId','inputOwnership')),
        'terminal actor differs')
    require(policy_body(control['policyReceipt'])==policy_body(policy) and policy.get('kind')=='policy'
        and policy.get('normalReturn') is True and policy['completedFrame']<terminal['frame']
        and all(policy['before'][k]==current[k] for k in ('subject','sourceIdentity','engineIdentity',
            'worldContext','playerPointer','mountPointer','avatarPointer')),
        'lacks matching native policy call')
    raw=bytes.fromhex(clean['mountStateHex']);address=control.get('stateAddress')
    require(type(address) is int and address==0x023BC744 and control.get('stateBytes')==184
        and control.get('changedAddress')==address+THRESHOLD_OFFSET and control.get('changedOffset')==THRESHOLD_OFFSET
        and control.get('profileOffset')==70 and control.get('changedHex')=='ff','address differs')
    require(len(raw)==184 and raw[8:80].hex()==profile['profileHex']==policy['profileHex']
        and type(profile.get('stompTime')) is int and raw[78]==profile['stompTime']==policy['stompTime']<=32
        and control.get('originalHex')==raw[78:79].hex(),'original profile differs')
    binding=clean['mountBinding'];native_binding=struct.unpack_from('<IHHHHBBBB',raw,80)
    require(binding==policy['mountBinding'] and binding['bindingHex']==raw[80:96].hex()
        and binding['sessionGeneration']==struct.unpack_from('<I',raw,96)[0]>0
        and struct.unpack_from('<II',raw)==(binding['fieldPointer'],binding['surfacePointer'])
        and binding['fieldPointer']==current['worldContext']['fieldPointer']
        and native_binding[:7]==(current['sourceIdentity']['personality'],actor['species'],current['worldContext']['mapId'],
            actor['handle']['mapGeneration'],actor['handle']['encounterGeneration'],actor['form'],actor['level'])
        and native_binding[7]<6 and raw[100]==2 and raw[20]==1,'native binding differs')
    changed=bytearray(raw);changed[78]=255
    require(control['bad']==dict(mountStateHex=changed.hex(),failure=BAD_THRESHOLD)
        and control['restored']==clean,'threshold fault or restoration differs')
    pose=clean['pose']
    require(all(pose.get(k)==v for k,v in current.items())
        and same_completed_object(terminal['player'],pose['player'])
        and same_completed_object(actor['engineObject'],pose['mount']),'terminal pose differs')
    check_pair_pose(pose)
    require(all(type(clean['input'].get(k)) is int and clean['input'][k]==0
        for k in ('heldKeys','newKeys','rawHeld','rawNew','simulatedKeys')),'input not released')
    clock=control['clock']
    require(set(clock)=={'frame','actorFrame','nativeCycle'} and all(type(v) is int and v>=0 for v in clock.values())
        and clock==control['restoredClock'] and clock['frame']==terminal['frame']
        and clock['actorFrame']==terminal['actorFrame'] and clock['nativeCycle']>=terminal['nativeCycle'],
        'clocks differ')
    registers=control['registers']
    require(set(registers)=={*('r'+str(i) for i in range(16)),'cpsr','spsr'}
        and registers==control['restoredRegisters'] and all(type(v) is int and 0<=v<=0xffffffff for v in registers.values()),
        'registers differ')


class StompControlMeasurement:
    def __init__(self,max_frames):
        from tools.overworld.devtools_stomp_measurement import StompMeasurement
        self.natural=StompMeasurement(max_frames)
        self.control=self.cleanup=self.calibration_receipt=None
        self.closed=False;self.failures=[]
    def __getattr__(self,name):return getattr(self.natural,name)
    @property
    def ready(self):return self.natural.ready and self.control is not None and not self.failures
    def stage(self,name):return self.natural.stage(name) and not self.failures
    def configure(self,*args,**kwargs):
        require(self.control is None and not self.closed,'configure after calibration')
        return self.natural.configure(*args,**kwargs)
    def command(self,*args,**kwargs):
        require(self.control is None and not self.closed,'command after calibration')
        return self.natural.command(*args,**kwargs)
    def observe(self,snapshot,events):
        if self.control is not None or self.closed:self.failures.append('stomp control observed gameplay after calibration')
        elif not self.failures:
            self.natural.observe(snapshot,events);self.failures=list(self.natural.failures)
        return self.result()
    def _reader(self,reader):
        require(reader.get('closed') is True and reader.get('failure')==BAD_THRESHOLD
            and reader.get('guestMemoryWrites')==2 and reader.get('calibration')==self.control,
            'terminal reader differs')
        # Validate the copied counters/owner with the base reader. Never clear
        # a live safety latch, and never normalize before validating the fault.
        normalized=dict(reader,failure=None,guestMemoryWrites=0,calibration=None)
        self.natural._reader(normalized,True)
    def calibrate(self,receipt,snapshot):
        require(self.natural.ready and not self.failures and self.control is None and not self.closed,
            'requires complete positive and negative baseline')
        require(receipt.get('prepared') is True and receipt.get('acceptedProof') is False
            and receipt.get('advancedFrames')==0 and receipt.get('terminalGuard') is True
            and receipt.get('snapshot')==snapshot,'runtime terminal guard or boundary differs')
        require(all(snapshot.get(k)==self.natural.last.get(k) for k in
            ('frame','actorFrame','nativeCycle','actors','player','context','selector')),'calibration moved baseline endpoint')
        natural=self.natural.result()
        validate_stomp(natural['cases'],self.subject,self.natural.last)
        policy=natural['cases'][-1]['feedback']['calls'][-1]
        validate_control(receipt.get('calibration'),policy,self.natural.last,self.subject)
        self.control=deepcopy(receipt['calibration'])
        self._reader(receipt['stompFeedback'])
        self.calibration_receipt=deepcopy(receipt)
        return self.result()
    def close(self,receipt,snapshot):
        require(self.ready and not self.closed and receipt.get('closed') is True and receipt.get('advancedFrames')==0
            and receipt.get('acceptedProof') is False and receipt.get('snapshot')==snapshot
            and all(snapshot.get(k)==self.natural.last.get(k) for k in
                ('frame','actorFrame','nativeCycle','actors','player','context','selector')),'cleanup boundary differs')
        self._reader(receipt['stompFeedback']);self.closed=True;self.cleanup=deepcopy(receipt)
        return self.result()
    def finish(self):
        baseline=self.natural.finish()
        if not self.natural.ready:
            self.failures.extend(f for f in baseline['failures'] if f not in self.failures)
        if (not self.ready or not self.closed) and not self.failures:self.failures.append('stomp control incomplete')
        result=self.result();result['natural']=self.natural.result() if self.natural.ready else baseline
        return result
    def result(self):
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,closed=self.closed,
            acceptedProof=False,subject=self.subject,frames=self.frames,failures=self.failures,natural=self.natural.result(),
            terminal=self.natural.last,control=self.control,calibrationReceipt=self.calibration_receipt,cleanup=self.cleanup))

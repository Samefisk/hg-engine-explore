"""Complete original corner baseline, then calibrate its policy reader at rest."""
from copy import deepcopy

from tools.overworld.devtools_corner_measurement import CornerMeasurement, require, ENVELOPE
from tools.overworld.devtools_wild_walk_measurement import IDENTITY
from tools.overworld.devtools_mount_walk_fixture import STATE_BYTES

KIND='live-corner-control-v1'


def native_call(value):
    """Join a raw callback to its framed copy, not to another observation.

    CornerMeasurement has already checked each envelope's stream sequence,
    completed frame and native cycle bounds. Keep every native field here,
    including the entryClock/returnClock pair and complete actor identity.
    """
    return {key:item for key,item in value.items() if key not in ENVELOPE}


def validate_control(control,strict,terminal,subject):
    require(isinstance(control,dict) and control.get('state')=='complete' and control.get('failure') is None
        and control.get('cleanupPending') is False and control.get('acceptedProof') is False
        and type(control.get('guestInstructionAdvance')) is int and control['guestInstructionAdvance']==0
        and control.get('guestMemoryWrites')==2,'corner control is missing or not restored')
    clean,bad,restored=(control[k] for k in ('clean','bad','restored'))
    actor=next(a for a in terminal['actors'] if a['handle']==subject['handle'])
    current=clean['current'];policy=clean['policy']
    require(current['subject']==subject and all(current['publicSubject'].get(k)==actor.get(k)
        for k in (*IDENTITY,'logical','commitSequence','motionKind','motionPhase','reservationId'))
        and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0
        and all(current.get(k)==strict['before'].get(k) for k in
            ('sourceIdentity','engineIdentity','worldContext','playerPointer','mountPointer','avatarPointer'))
        and clean['mountBinding']==strict['mountBinding'], 'corner control terminal owner differs')
    require(isinstance(control.get('strictReceipt'),dict)
        and native_call(control['strictReceipt'])==native_call(strict) and policy.get('profileHex')==strict['profileHex']
        and type(policy.get('profile19')) is int and policy['profile19']==strict['profile19']==1,
        'corner control lacks original strict policy read')
    state=bytes.fromhex(clean['mountStateHex']);profile=bytes.fromhex(policy['profileHex'])
    require(control.get('stateBytes')==STATE_BYTES and len(state)==STATE_BYTES
        and len(profile)==72 and state[8:80]==profile and (profile[19]&0x03)==1,
        'corner control native policy bytes differ')
    expected=deepcopy(clean);changed_state=bytearray(state);changed_state[27]=0
    changed_profile=bytearray(profile);changed_profile[19]&=~0x03
    expected['mountStateHex']=changed_state.hex()
    expected['policy']=dict(policy,profileHex=changed_profile.hex(),profile19=0)
    require(bad==expected and restored==clean,'corner policy fault or restoration differs')
    from tools.overworld.devtools_corner_observer import check_corner_policy
    check_corner_policy(policy);check_corner_policy(restored['policy'])
    try:check_corner_policy(bad['policy'])
    except ValueError:pass
    else:raise ValueError('corner bad policy passed unchanged checker')
    address=control.get('stateAddress')
    require(type(address) is int and address==strict.get('statePointer') and address%4==0
        and 0x02000000<=address<=0x02400000-STATE_BYTES and control.get('policyAddress')==address+8
        and control.get('changedAddress')==address+27 and control.get('changedOffset')==19
        and control.get('originalHex')=='01' and control.get('changedHex')=='00',
        'corner control policy address differs')
    clock=control.get('clock',{})
    require(set(clock)=={'frame','actorFrame','nativeCycle'} and all(type(v) is int and v>=0 for v in clock.values())
        and clock==control.get('restoredClock') and clock['frame']==terminal['frame']
        and clock['actorFrame']==terminal['actorFrame'] and clock['nativeCycle']>=terminal['nativeCycle'],
        'corner control clocks differ')
    registers=control.get('registers',{})
    require(set(registers)=={*('r'+str(i) for i in range(16)),'cpsr','spsr'}
        and registers==control.get('restoredRegisters')
        and all(type(v) is int and 0<=v<=0xFFFFFFFF for v in registers.values()),'corner control registers differ')
    for raw,observed in ((clean['player'],terminal['player']),(clean['mount'],actor['engineObject'])):
        require(raw==observed,'corner control terminal pose differs')


class CornerControlMeasurement:
    def __init__(self,max_frames):
        self.natural=CornerMeasurement(max_frames)
        self.control=self.cleanup=None
        self.closed=False;self.failures=[]
    @property
    def initial(self):return self.natural.initial
    @property
    def frames(self):return self.natural.frames
    @property
    def ready(self):return self.natural.ready and self.control is not None and not self.failures
    def probe(self,*args,**kwargs):return self.natural.probe(*args,**kwargs)
    def arm(self,*args,**kwargs):return self.natural.arm(*args,**kwargs)
    def command(self,*args,**kwargs):return self.natural.command(*args,**kwargs)
    def begin_recovery(self,*args,**kwargs):return self.natural.begin_recovery(*args,**kwargs)
    def stage(self,name):return self.natural.stage(name) and not self.failures
    def observe(self,snapshot,events):
        if self.closed or self.control is not None:
            self.failures.append('corner control observed gameplay after calibration')
        elif not self.failures:
            self.natural.observe(snapshot,events);self.failures=list(self.natural.failures)
        return self.result()

    def _reader(self,value,closed,control):
        require(value.get('armed') is True and value.get('closed') is closed and value.get('failure') is None
            and value.get('acceptedProof') is False and value.get('guestMemoryWrites')==2
            and value.get('subject')==self.natural.subject and value.get('startFrame')==self.initial['frame']
            and isinstance(value.get('calls'),list)
            and [native_call(call) for call in value['calls']]==[native_call(call) for call in self.natural.calls]
            and value.get('counts')==dict(strict=len(self.natural.calls),
                collision=sum(len(c['collisions']) for c in self.natural.calls),
                landing=sum(len(c['landings']) for c in self.natural.calls))
            and value.get('policyCalibration')==control,'corner calibrated reader differs')

    def calibrate(self,receipt,snapshot):
        # ready is a polling predicate and deliberately hides completion
        # errors. At this terminal command retain the exact missing baseline
        # fact so copied controls cannot pass on a generic setup failure.
        if self.natural.initial is not None and not self.failures:
            self.natural._complete()
        require(self.natural.ready and not self.failures and self.control is None and not self.closed
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and receipt.get('prepared') is True and receipt.get('snapshot')==snapshot,
            'corner calibration lacks complete original baseline')
        self.natural._complete();self.natural._actor(snapshot)
        require(all(snapshot.get(k)==self.natural.last.get(k) for k in ('frame','actorFrame','actors','context','player')),
            'corner calibration moved terminal endpoint')
        control=receipt.get('calibration')
        validate_control(control,self.natural.calls[-1],self.natural.last,self.natural.subject)
        self._reader(snapshot['walkCorner'],False,control)
        self.control=deepcopy(control)

    def close(self,receipt,snapshot):
        require(self.ready and not self.closed and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and all(snapshot.get(k)==self.natural.last.get(k) for k in ('frame','actorFrame','actors','context','player'))
            and all(receipt.get('snapshot',{}).get(k)==snapshot.get(k) for k in
                ('frame','nativeCycle','actorFrame','actors','context','player')),'corner control cleanup missing')
        self.natural._actor(snapshot);self._reader(receipt['walkCorner'],True,self.control)
        self.closed=True;self.cleanup=deepcopy(receipt)
        return self.result()

    def finish(self):
        if not self.ready or not self.closed:self.failures.append('corner control incomplete')
        return self.result()

    def result(self):
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,acceptedProof=False,
            closed=self.closed,subject=self.natural.subject,frames=self.frames,failures=self.failures,
            control=self.control,cleanup=self.cleanup,terminal=self.natural.last,natural=self.natural.result()))

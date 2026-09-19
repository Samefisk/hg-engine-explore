"""Two real timing cases, followed by a terminal same-reader state control."""
from copy import deepcopy

from tools.overworld.devtools_corner_measurement import require
from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.devtools_walk_matrix_control import BAD_ENUM
from tools.overworld.devtools_wild_walk_measurement import IDENTITY

KIND='live-walk-matrix-control-v1'


def moving_summary(tick):
    return dict(completedFrame=tick['completedFrame'],entryElapsed=tick['before']['elapsed'],
        returnElapsed=tick['after']['elapsed'],reservationId=tick['after']['plan']['reservationId'],
        qualification=tick['qualification'],duration=tick['after']['plan']['duration'],
        phaseBefore=tick['before']['phase'],phaseAfter=tick['after']['phase'],returnFlags=tick['returnFlags'],
        fieldEpoch=tick['expectedFieldEpoch'],entryClock=tick['entryClock'],returnClock=tick['returnClock'])


def validate_control(control,tick,terminal,subject,pointer):
    require(isinstance(control,dict) and control.get('state')=='complete' and control.get('failure') is None
        and control.get('cleanupPending') is False and control.get('acceptedProof') is False
        and type(control.get('guestInstructionAdvance')) is int and control['guestInstructionAdvance']==0
        and control.get('guestMemoryWrites')==2,'matrix control is missing or not restored')
    clean=control['clean'];current=clean['current'];motion=clean['motion']
    actor=next(a for a in terminal['actors'] if a['handle']==subject['handle'])
    require(current['subject']==subject and all(current['publicSubject'].get(k)==actor.get(k)
        for k in (*IDENTITY,'logical','commitSequence','motionKind','motionPhase','reservationId'))
        and actor['species']==155 and actor['role']=='MOUNTED' and actor['inputOwnership']==1
        and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0
        and all(current[k]==tick['afterCurrent'][k] for k in ('subject','sourceIdentity','engineIdentity',
            'worldContext','playerPointer','mountPointer','avatarPointer')),'matrix control terminal owner differs')
    require(control['priorMovingTick']==moving_summary(tick) and tick['movingWalk'] is True
        and tick['before']['phase']=='MOVING' and tick['after']['phase']=='COMMIT_PENDING'
        and tick['after']['elapsed']==tick['after']['plan']['duration']>0
        and tick['returnFlags'] & 12==12 and tick['completedFrame']<terminal['frame'],
        'matrix control lacks actual completed moving Tick')
    raw=bytes.fromhex(motion['rawHex'])
    require(len(raw)==52 and decode_motion(raw)==motion and motion['phase']=='IDLE'
        and motion['plan']==tick['after']['plan'] and motion['elapsed']==tick['after']['elapsed'],
        'matrix control original motion differs')
    changed=bytearray(raw);changed[48]=255
    require(control['bad']==dict(rawHex=changed.hex(),failure=BAD_ENUM)
        and control['restored']==clean,'matrix control bad state or restoration differs')
    try:decode_motion(bytes(changed))
    except ValueError as error:require(str(error)==BAD_ENUM,'matrix control reader error differs')
    else:raise ValueError('matrix control invalid phase was accepted')
    require(control.get('motionPointer')==pointer and type(pointer) is int and pointer%4==0
        and 0x02000000<=pointer<=0x02400000-52 and control.get('stateBytes')==52
        and control.get('changedAddress')==pointer+48 and control.get('changedOffset')==48
        and control.get('originalHex')=='00' and control.get('changedHex')=='ff','matrix control address differs')
    clock=control.get('clock',{})
    require(set(clock)=={'frame','actorFrame','nativeCycle'} and all(type(v) is int and v>=0 for v in clock.values())
        and clock==control.get('restoredClock') and clock['frame']==terminal['frame']
        and clock['actorFrame']==terminal['actorFrame'] and clock['nativeCycle']>=terminal['nativeCycle'],
        'matrix control clocks differ')
    registers=control.get('registers',{})
    require(set(registers)=={*('r'+str(i) for i in range(16)),'cpsr','spsr'}
        and registers==control.get('restoredRegisters')
        and all(type(v) is int and 0<=v<=0xFFFFFFFF for v in registers.values()),'matrix control registers differ')
    require(clean['player']==terminal['player'] and clean['mount']==actor['engineObject'],
        'matrix control terminal pose differs')
    require(all(type(clean['input'].get(k)) is int and clean['input'][k]==0
        for k in ('heldKeys','newKeys','rawHeld','rawNew','simulatedKeys')),'matrix control input not released')


class WalkMatrixControlMeasurement:
    def __init__(self,max_frames):
        self.natural=WalkMatrixMeasurement(max_frames,case_limit=2)
        self.control=self.cleanup=self.last_moving=None
        self.closed=False;self.failures=[]
    def __getattr__(self,name):return getattr(self.natural,name)
    @property
    def ready(self):return self.natural.ready and self.control is not None and not self.failures
    def stage(self,name):return self.natural.stage(name) and not self.failures
    def command(self,*args,**kwargs):
        require(self.control is None and not self.closed,'matrix command after calibration')
        return self.natural.command(*args,**kwargs)
    def configure(self,*args,**kwargs):
        require(self.control is None and not self.closed,'matrix configure after calibration')
        return self.natural.configure(*args,**kwargs)
    def observe(self,snapshot,events):
        if self.control is not None or self.closed:self.failures.append('matrix control observed gameplay after calibration')
        elif not self.failures:
            self.natural.observe(snapshot,events);self.failures=list(self.natural.failures)
            if not self.failures:
                for event in events:
                    data=event['data']
                    if event['kind']=='native-observation' and data.get('observation')=='walk-matrix-tick' and data['movingWalk']:
                        self.last_moving=deepcopy(data)
        return self.result()
    def _reader(self,value,closed):
        require(value.get('calibration')==self.control and value.get('guestMemoryWrites')==2
            and value.get('lastMovingTick')==moving_summary(self.last_moving),'matrix calibrated reader differs')
        # The original reader checks every other counter, owner, layout and last Tick.
        normalized=dict(value,guestMemoryWrites=0)
        self.natural._reader(normalized,closed)
    def calibrate(self,receipt,snapshot):
        require(self.natural.ready and not self.failures and self.control is None and not self.closed
            and self.last_moving is not None and receipt.get('advancedFrames')==0
            and receipt.get('acceptedProof') is False and receipt.get('prepared') is True
            and receipt.get('snapshot')==snapshot,'matrix calibration lacks complete two-case baseline')
        require(all(snapshot.get(k)==self.natural.last.get(k) for k in ('frame','actorFrame','actors','context','player')),
            'matrix calibration moved terminal endpoint')
        self.natural._actor(snapshot)
        validate_control(receipt.get('calibration'),self.last_moving,self.natural.last,self.subject,self.motion_pointer)
        self.control=deepcopy(receipt['calibration']);self._reader(snapshot['walkMatrix'],False)
        return self.result()
    def close(self,receipt,snapshot):
        require(self.ready and not self.closed and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and all(snapshot.get(k)==self.natural.last.get(k) for k in ('frame','actorFrame','actors','context','player'))
            and all(receipt.get('snapshot',{}).get(k)==snapshot.get(k) for k in
                ('frame','nativeCycle','actorFrame','actors','context','player')),'matrix control cleanup missing')
        self.natural._actor(snapshot);self._reader(receipt['walkMatrix'],True)
        self.closed=True;self.cleanup=deepcopy(receipt)
        return self.result()
    def finish(self):
        baseline=self.natural.finish()
        if not self.natural.ready:
            for failure in baseline['failures']:
                if failure not in self.failures:self.failures.append(failure)
        if (not self.ready or not self.closed) and not self.failures:
            self.failures.append('matrix control incomplete')
        result=self.result()
        # The wrapper owns close after calibration. A complete natural prefix
        # needs no separate close; an incomplete one must retain its exact cause.
        result['natural']=self.natural.result(full=True) if self.natural.ready else baseline
        return result
    def result(self):
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,acceptedProof=False,
            closed=self.closed,subject=self.subject,frames=self.frames,failures=self.failures,control=self.control,
            cleanup=self.cleanup,terminal=self.natural.last,natural=self.natural.result(),lastMovingTick=self.last_moving))


MatrixControlMeasurement=WalkMatrixControlMeasurement

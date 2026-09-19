"""Pure bounded replay of mounted Crash receipts; never grants game proof.

Expectations come from the mounted controller and legacy.crash contract:
32 updates/presentations, +/-0x2000 face displacement, wall-hit sound1536,
stationary base coordinates, completed-queue restoration, one recovery Walk.
Caller expands retained event artifacts and authenticates setup/reader code.
No native memory offsets, file access, guest writes or emulator dependency.
"""
from copy import deepcopy

from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement
from tools.overworld.devtools_mount_pacing_observer import ENGINE
from tools.overworld.devtools_wild_walk_measurement import IDENTITY, LIFECYCLE

KIND = 'mounted-crash-v1'
KINDS = ('start','update','presentation','finish','crashSound','sound','soundStart')
BOUNDARY = 'main-task-queue-completion'
POSITION = ('x','y','pos_x','pos_y','pos_z')


def require(ok, message):
    if not ok: raise ValueError('Mounted Crash: '+message)


def state(sample):
    value=tuple(sample[k] for k in ('mode','duration','elapsed'))
    require(all(type(v) is int for v in value),'invalid native state types')
    return value


class MountedCrashMeasurement:
    _actor = WalkMatrixMeasurement._actor

    def __init__(self, max_frames):
        require(type(max_frames) is int and 1<=max_frames<=600,'invalid frame bound')
        self.max_frames=max_frames
        self.subject=self.actor=self.initial=self.last=None
        self.owner=self.binding=self.start=self.finish_call=self.restored=None
        self.calls={k:[] for k in KINDS};self.commands=[];self.recovery=[]
        self.sequence=self.frames=0;self.command_end=None;self.streams={}
        self.reader_start=None;self.closed=False;self.failures=[]
        self.crash_commit=None

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        require(self.initial is None,'reader already armed')
        self.subject=deepcopy(subject);self.actor=deepcopy(self._actor(snapshot))
        require(self.actor['motionPhase']=='IDLE' and self.actor['reservationId']==0,'arm not idle')
        self.initial=self.last=deepcopy(snapshot);self.command_end=snapshot['frame']
        self.sequence=snapshot['nativeObservation']['sequence'];self.streams=dict(trace_sequences or {})
        r=receipt.get('crashFeedback',receipt);self.reader_start=r['startFrame']
        require(self.reader_start<=snapshot['frame'],'reader starts after initial snapshot')
        self._reader(r,snapshot,False)
        require(state(r['latestCompleted'])==(0,0,0),'arm during crash')
        return self.result()

    def command(self, request, receipt):
        require(self.initial is not None and not self.closed and not self.failures,'command outside window')
        args=request['args'];r=receipt.get('receipt',receipt);n=args['frames'];keys=args['keys']
        require(request['op']=='step' and request['startFrame']==self.command_end
            and type(n) is int and 1<=n<=self.max_frames
            and all(r.get(k)==n for k in ('requestedGameFrames','completedGameFrames','observedFieldFrames')),
            'normal input command boundary differs')
        require(keys in ([],['UP'],['RIGHT']),'unexpected input direction')
        self.commands.append(dict(startFrame=self.command_end,endFrame=self.command_end+n,
            mask=64 if keys==['UP'] else 16 if keys else 0))
        self.command_end+=n

    def _input(self, snapshot):
        frame=snapshot['frame'];selector=snapshot['selector']
        matches=[c for c in self.commands if c['startFrame']<frame<=c['endFrame']]
        require(len(matches)==1,'missing command window')
        command=matches[0];mask=selector['heldKeys']
        require(type(mask) is int and mask==selector['rawHeld'] and selector['simulatedKeys']==0,
            'native input is missing or simulated')
        prior=next((c for c in self.commands if c['endFrame']==command['startFrame']),None)
        stale=frame==command['startFrame']+1 and prior is not None and mask==prior['mask']
        require(mask==command['mask'] or stale,'held keys differ from normal command')
        return mask

    def _sample(self, sample):
        current=sample['current'];pose=sample['pose']
        require(current['subject']==self.subject and pose['subject']==self.subject,
            'native subject differs')
        for value in (current,pose):
            require(all(value['publicSubject'].get(k)==self.actor.get(k) for k in IDENTITY)
                and value['sourceIdentity']==self.actor['sourceIdentity']
                and value['engineIdentity']=={k:self.actor['engineIdentity'][k] for k in ENGINE}
                and all(value['worldContext'].get(k)==v for k,v in self.initial['context'].items())
                and value['playerPointer']==self.actor['engineIdentity']['anchorPointer']
                and value['mountPointer']==self.actor['engineIdentity']['pointer'],'native owner/context differs')
        owner={k:current[k] for k in ('subject','sourceIdentity','engineIdentity','worldContext',
            'playerPointer','mountPointer','avatarPointer')}
        if self.owner is None:self.owner=deepcopy(owner);self.binding=deepcopy(sample['mountBinding'])
        require(owner==self.owner and sample['mountBinding']==self.binding,'native binding changed')
        require(all(type(pose[o].get(k)) is int for o in ('player','mount')
            for k in (*POSITION,'face_x','face_y','face_z')),'native paired pose missing')
        require(all(pose['player'][k]==pose['mount'][k] for k in POSITION),'mount detached from anchor')
        state(sample)
        return pose

    def _stationary(self, sample):
        pose=self._sample(sample);base=self.start['before']['pose']
        require(all(pose[o][k]==base[o][k] for o in ('player','mount') for k in POSITION),
            'crash displaced logical or base position')
        require(all(pose[o][prefix+axis]==base[o][prefix+axis] for o in ('player','mount')
            for prefix in ('unk88_','unk94_') for axis in 'xyz'),'crash changed another presentation offset')

    def _reader(self, r, snapshot, closed):
        require(r.get('armed') is True and r.get('closed') is closed and r.get('failure') is None
            and r.get('acceptedProof') is False and r.get('guestMemoryWrites')==0 and r.get('pending')==0
            and r.get('subject')==self.subject and r.get('startFrame')==self.reader_start
            and r.get('counts')=={k:len(v) for k,v in self.calls.items()},'reader coverage/counts differ')
        s=r['latestCompleted'];self._sample(s)
        require(s.get('boundary')==BOUNDARY and all(s[k]==snapshot[k] for k in ('frame','actorFrame','nativeCycle')),
            'completed native state boundary differs')
        actor=self._actor(snapshot);pose=s['pose']
        require(all(pose['player'][k]==snapshot['player'][k]
            and pose['mount'][k]==actor['engineObject'][k] for k in (*POSITION,'face_x','face_y','face_z')),
            'completed public/native pose differs')
        return s

    def _call(self,d,mask):
        kind=d['kind'];require(kind in self.calls and d['observation']=='mounted-crash-'+kind,
            'unknown crash event')
        require(d.get('normalReturn') is True,'native return missing')
        self._sample(d['before']);self._sample(d['after'])
        require(d['entryClock']==dict(actorFrame=d['entryActorFrame'],nativeCycle=d['entryNativeCycle'])
            and d['returnClock']==dict(actorFrame=d['returnActorFrame'],nativeCycle=d['returnNativeCycle']),
            'native callback clocks disagree')
        if kind=='start':
            require(self.start is None and mask==64 and state(d['before'])==(0,0,0)
                and state(d['after'])==(3,32,0),'missing held-input single crash start')
            require(d['completedFrame']>self.initial['frame']+1,'held-input hit too early')
            self.start=deepcopy(d)
        require(self.start is not None,'crash event before start')
        self._stationary(d['before']);self._stationary(d['after'])
        if kind=='presentation':
            elapsed=len(self.calls[kind])+1
            require(elapsed<=32 and state(d['before'])==state(d['after'])==(3,32,elapsed)
                and d['entryActorFrame']==self.start['entryActorFrame']+elapsed-1,
                'presentation elapsed schedule differs')
            offset=8192 if elapsed&2 else -8192
            before,after=d['before']['pose'],d['after']['pose']
            base=self.start['before']['pose']
            require(after['player']['face_x']==base['player']['face_x']+offset
                and after['player']['face_z']==base['player']['face_z']-offset
                and after['mount']['face_x']==offset and after['mount']['face_z']==-offset
                and all(after[o]['face_y']==before[o]['face_y'] for o in ('player','mount')),
                'sound/shake displacement differs')
        elif kind=='update':
            elapsed=len(self.calls[kind])
            require(elapsed<=32 and state(d['before'])==(3,32,elapsed)
                and state(d['after'])==((3,32,elapsed+1) if elapsed<32 else (0,0,0))
                and d['entryActorFrame']==self.start['entryActorFrame']+elapsed,'update/reset schedule differs')
        elif kind=='finish':
            require(not self.calls[kind] and len(self.calls['presentation'])==32
                and state(d['before'])==(3,32,32) and state(d['after'])==(0,0,0)
                and d['entryActorFrame']==self.start['entryActorFrame']+32,'early or duplicate reset')
            self.finish_call=deepcopy(d)
        elif kind in ('sound','crashSound','soundStart'):
            require(not self.calls[kind] and d['entryActorFrame']==self.start['entryActorFrame'],
                'missing or duplicate crash sound')
            if kind!='soundStart':require(d['args'][0]==1536,'wrong crash sound ID')
            else:require(d['returnValue']==1,'native sound start failed')
        self.calls[kind].append(deepcopy(d))

    def observe(self,snapshot,events):
        if self.failures:return self.result()
        try:
            require(self.initial is not None and not self.closed,'observation outside window')
            actor=self._actor(snapshot)
            require(snapshot['observationBoundary']==BOUNDARY and snapshot['frame']==self.last['frame']+1
                and snapshot['actorFrame']==self.last['actorFrame']+1
                and snapshot['nativeCycle']>=self.last['nativeCycle'],'completed frame gap')
            self.frames+=1;require(self.frames<=self.max_frames,'frame bound exceeded')
            mask=self._input(snapshot);n=snapshot['nativeObservation']
            require(n.get('installedBeforeBoot') is True and n.get('coverageComplete') is True
                and n.get('error') is None and n.get('eventsDropped')==n.get('profilesEvicted')==0,
                'native observation coverage missing')
            for event in events:
                require(event['frame']==snapshot['frame'],'event delivery frame differs')
                d=event['data']
                if event['kind']=='native-observation':
                    require(d['sequence']==self.sequence+1,'native event missing')
                    self.sequence=d['sequence']
                    require(self.last['nativeCycle']<=d['entryNativeCycle']<=d['returnNativeCycle']<=snapshot['nativeCycle'],
                        'native event clock outside frame')
                    if d.get('observation','').startswith('mounted-crash-'):self._call(d,mask)
                elif event['kind']=='native':
                    stream=d['traceStream'];previous=self.streams.get(stream,d['sequence']-1)
                    require(d['sequence']==previous+1,'native actor trace gap')
                    self.streams[stream]=d['sequence']
                    if d.get('actorHandle')!=self.subject['handle']['value']:continue
                    require(d.get('reason')=='OK' and d.get('actor')=={k:v for k,v in self.subject['handle'].items() if k!='value'},
                        'actor event identity/reason differs')
                    require(d['event']!='MOTION_CANCELED','motion canceled')
                    if self.start and not self.restored:
                        require(d['event'] not in LIFECYCLE,'new motion/commit during crash')
                    if self.restored and d['event'] in LIFECYCLE:
                        require(len(self.recovery)<4 and d['event']==LIFECYCLE[len(self.recovery)],'recovery lifecycle differs')
                        if not self.recovery:require(mask==16 and d['valueA']==1,'recovery not natural RIGHT Walk')
                        elif d['event'] in ('LOGICAL_COMMIT','MOTION_FINISHED'):require(d['valueB']==1,'recovery not Walk')
                        self.recovery.append(deepcopy(d))
            require(self.sequence==n['sequence'],'native tail event missing')
            s=self._reader(snapshot['crashFeedback'],snapshot,False)
            if self.start and self.restored is None:
                self._stationary(s)
                if self.crash_commit is None:self.crash_commit=actor['commitSequence']
                require(actor['commitSequence']==self.crash_commit,'logical commit during crash')
                require(actor['logical']==dict(zip(('x','y'),(self.start['before']['pose']['player'][k] for k in ('x','y')))),
                    'crash logical actor displaced')
                if self.finish_call:
                    require(state(s)==(0,0,0) and actor['motionPhase']=='IDLE' and actor['reservationId']==0
                        and actor['movementPolicy']['pending']==0,'completed reset missing')
                    require(all(s['pose'][o][k]==self.start['before']['pose'][o][k]
                        for o in ('player','mount') for k in ('face_x','face_y','face_z')),'completed pose not restored')
                    self.restored=deepcopy(snapshot)
                else:require(state(s)==(3,32,len(self.calls['presentation'])),'early completed reset')
            self.last=deepcopy(snapshot)
        except (ValueError,KeyError,TypeError,IndexError,StopIteration) as error:
            self.failures.append('Mounted Crash: '+str(error))
        return self.result()

    @property
    def ready(self):
        if self.failures or self.restored is None or len(self.recovery)!=4:return False
        a=next(a for a in self.last['actors'] if a['handle']==self.subject['handle'])
        origin=self.start['before']['pose']['player']
        return (a['motionPhase']=='IDLE' and a['reservationId']==0 and a['movementPolicy']['pending']==0
            and a['logical']=={'x':origin['x']+1,'y':origin['y']}
            and a['commitSequence']==next(a for a in self.restored['actors'] if a['handle']==self.subject['handle'])['commitSequence']+1
            and {k:len(v) for k,v in self.calls.items()}==dict(start=1,update=33,presentation=32,finish=1,crashSound=1,sound=1,soundStart=1))

    def close(self,receipt,snapshot):
        from tools.overworld.devtools_test_contract import _same_mounted_reader_boundary
        require(self.ready and not self.closed and _same_mounted_reader_boundary(self.last,snapshot)
            and all(snapshot.get(k)==self.last.get(k) for k in
                ('selector','fieldControl','observationBoundary')) and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and _same_mounted_reader_boundary(snapshot,receipt.get('snapshot',{}))
            and all(receipt.get('snapshot',{}).get(k)==snapshot.get(k) for k in
                ('selector','fieldControl','observationBoundary')),'close before complete recovery or changed boundary')
        self._reader(receipt['crashFeedback'],snapshot,True);self.closed=True
        return self.result(full=True)

    def finish(self):
        if not self.ready and not self.failures:self.failures.append('Mounted Crash: incomplete crash/restoration/recovery')
        if not self.closed and not self.failures:self.failures.append('Mounted Crash: close missing')
        return self.result(full=True)

    def result(self,full=False):
        evidence={}
        if self.ready:
            origin=[self.start['before']['pose']['player'][k] for k in ('x','y','pos_x','pos_z')]
            values=(('natural-input','crash-held-input-hit-frame',self.start['completedFrame']-self.initial['frame']),
                ('live-actor-identity','crash-cyndaquil-identity-flags',[1,'MOUNTED',155,1,1]),
                ('engine-boundary','single-stationary-crash',[1,origin,origin]),
                ('frame-pacing','crash-presentation-elapsed-schedule',[d['after']['elapsed'] for d in self.calls['presentation']]),
                ('feedback-effect','crash-sound-and-shake',[1,1]),
                ('control-release','crash-reset-and-recovery-state',['IDLE',0,1,0,1]))
            evidence={claim:[dict(name=name,actual=value)] for claim,name,value in values}
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,closed=self.closed,
            acceptedProof=False,subject=self.subject,frames=self.frames,failures=self.failures,proofEvidence=evidence,
            stage='recovered' if self.ready else 'restored' if self.restored else 'crash' if self.start else 'waiting',
            counts={k:len(v) for k,v in self.calls.items()},
            terminalSnapshot=self.last if full else None,restoredFrame=self.restored['frame'] if self.restored else None))

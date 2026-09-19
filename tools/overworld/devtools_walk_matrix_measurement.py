"""Bounded pure matrix replay. Raw receipts remain in the shared stream once."""
from copy import deepcopy

from tools.overworld.devtools_walk_matrix_contract import CASES, LIFECYCLE, validate_motion, validate_matrix
from tools.overworld.devtools_walk_matrix_observer import decode_motion, decode_sample
from tools.overworld.devtools_corner_measurement import KEYS, require
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_wild_walk_measurement import IDENTITY

KIND = 'mounted-frame-matrix-v1'
DELTAS = {2:(-1,0),3:(1,0),4:(-1,-1),7:(1,1)}


class WalkMatrixMeasurement:
    def __init__(self,max_frames,case_limit=65):
        require(type(max_frames) is int and 1<=max_frames<=4096,'invalid matrix frame bound')
        require(type(case_limit) is int and case_limit in (2,65),'invalid matrix case limit')
        self.max_frames,self.case_limit=max_frames,case_limit
        self.initial=self.last=self.subject=self.actor=self.current=self.reader_layout=None
        self.configurations=[];self.cases=[];self.failures=[];self.commands=[]
        self.streams={};self.sequence=0;self.frames=0;self.ticks=0;self.moving=0
        self.closed=False;self.cleanup=None;self.gate=None;self.pending_config=None
        self.command_end=None;self.tick_owner=None;self.last_tick=None
        self.lastMovingTick=None

    def _actor(self,snapshot):
        bound=select_current_actor(snapshot,self.subject)
        actor=next(a for a in snapshot['actors'] if a['handle']==bound['handle'])
        require(actor['species']==155 and actor['role']=='MOUNTED' and actor['inputOwnership']==1,
                'matrix requires mounted Cyndaquil')
        if self.actor is not None:
            require(all(actor.get(k)==self.actor.get(k) for k in IDENTITY)
                and actor['sourceIdentity']==self.actor['sourceIdentity']
                and engine_binding_identity(actor['engineIdentity'])==engine_binding_identity(self.actor['engineIdentity'])
                and snapshot['context']==self.initial['context'],'matrix actor or context changed')
        reservations=[]
        for other in snapshot['actors']:
            if other.get('active'):
                require(other.get('presentationAttached') is True
                    and other['handle']['fieldEpoch']==snapshot['context']['fieldEpoch'],'matrix actor presentation or epoch differs')
                if other.get('reservationId'):reservations.append(other['reservationId'])
        require(len(reservations)==len(set(reservations)),'matrix duplicate reservation')
        return actor

    @staticmethod
    def _idle(actor):
        return actor['motionPhase']=='IDLE' and actor['motionKind']=='NONE' and actor['reservationId']==0

    def configure(self,receipt,snapshot):
        q=receipt.get('value',receipt)
        require(not self.closed and not self.failures and len(self.configurations)<self.case_limit
            and len(self.configurations)==len(self.cases),'matrix configure before prior completion')
        case=CASES[len(self.configurations)]
        require(q.get('completed') is True and q.get('prepared') is True and q.get('acceptedProof') is False
            and q.get('guestAdvanced') is False and q.get('scope')=='prepared-idle-mounted-walk-fixture'
            and q.get('directionMode')==case['mode'] and q.get('travelTime')==case['duration']
            and q.get('changedOffsets')==[7,19,50,51],'matrix configure contract differs')
        before,after=q['before'],q['after']
        original=bytes.fromhex(before['mountStateHex']);actual=bytes.fromhex(after['mountStateHex'])
        require(len(original)==len(actual)==184,'matrix configure bytes missing')
        expected=bytearray(original)
        for offset,value in ((7,case['duration']),(19,case['mode']),(50,0),(51,case['duration'])):expected[8+offset]=value
        require(actual==bytes(expected) and q['expectedStateHex']==actual.hex()
            and before['profileHex']==original[8:80].hex() and after['profileHex']==actual[8:80].hex()
            and before['readiness']==after['readiness'] and before['clock']==after['clock']
            and before['bindingHex']==after['bindingHex']==actual[80:96].hex()
            and before['sessionGeneration']==after['sessionGeneration'],'matrix configure changed unrelated state')
        require(actual[20]==1 and actual[58]==0 and actual[15]==actual[59]==case['duration'],
                'matrix configured Walk timing differs')
        selected=select_current_actor(snapshot,q['subject'])
        actor=next(a for a in snapshot['actors'] if a['handle']==selected['handle'])
        require(self._idle(actor) and actor['movementPolicy']['pending']==0
            and actor['species']==155 and actor['role']=='MOUNTED'
            and all(after['readiness']['actor'].get(k)==actor.get(k) for k in (*IDENTITY,'logical','commitSequence'))
            and after['clock']['frame']<=snapshot['frame'],'matrix configure not coherent idle')
        if self.initial is not None:
            self._actor(snapshot)
            require(snapshot['frame']==self.last['frame'],'matrix configure advanced field')
            previous=bytes.fromhex(self.configurations[-1]['profileHex'])
            require(original[8:80]==previous,'matrix profile changed between cases')
        self.pending_config=deepcopy(q)
        self.configurations.append(dict(caseIndex=case['index'],profileHex=after['profileHex'],
            beforeProfileHex=before['profileHex'],changedOffsets=q['changedOffsets'],bindingHex=after['bindingHex'],
            sessionGeneration=after['sessionGeneration']))
        self.current=dict(case=deepcopy(case),subject=None,reservation=None,ticks=[],events=[],
            origin=deepcopy(actor['logical']),commit=actor['commitSequence'],inputFrame=None)
        return self.result()

    def _reader(self,receipt,closed):
        r=receipt.get('walkMatrix',receipt)
        require(r.get('armed') is True and r.get('closed') is closed and r.get('failure') is None
            and r.get('acceptedProof') is False and r.get('guestMemoryWrites')==0
            and r.get('subject')==self.subject and r.get('startFrame')==self.initial['frame']
            and r.get('pending')==0 and r.get('returned')==self.ticks
            and r.get('counts')==dict(ticks=self.ticks,movingWalk=self.moving),'matrix reader receipts lost')
        if self.reader_layout is None:
            self.reader_layout=deepcopy(r['layout']);self.motion_pointer=r['motionPointer']
            layout=self.reader_layout
            current=(layout.get('actorStride')==172 and layout.get('policyOffset')==140
                and layout.get('policyBytes')==32)
            retained_host_fixture=(layout.get('actorStride')==140
                and 'policyOffset' not in layout and 'policyBytes' not in layout)
            require(layout.get('actorsOffset')==68 and layout.get('snapshotBytes')==88
                and layout.get('motionBytes')==52 and layout.get('capacity')==10
                and (current or retained_host_fixture)
                and self.motion_pointer==layout['stateAddress']+68
                    +self.subject['handle']['slot']*layout['actorStride']+88,
                'matrix reader layout differs')
        require(r['layout']==self.reader_layout and r['motionPointer']==self.motion_pointer,'matrix reader layout changed')
        if self.last_tick is not None:require(r.get('lastTick')==self.last_tick,'matrix last native tick differs')

    def arm(self,subject,snapshot,receipt,trace_sequences=None):
        require(self.initial is None and len(self.configurations)==1,'matrix needs first configure before arm')
        self.subject=deepcopy(subject);self.actor=deepcopy(self._actor(snapshot))
        require(self._idle(self.actor),'matrix arm not idle')
        require(self.actor['handle']==self.pending_config['subject']['handle']
            and self.actor['logical']==self.current['origin'],'matrix configured owner changed')
        self.initial=self.last=deepcopy(snapshot);self.current['subject']=deepcopy(subject)
        self._reader(receipt,False);self.sequence=snapshot['nativeObservation']['sequence']
        self.streams=dict(trace_sequences or {});self.command_end=snapshot['frame']
        return self.result()

    def command(self,request,receipt):
        require(self.initial is not None and not self.closed and not self.failures,'matrix command outside window')
        args=request['args'];r=receipt.get('receipt',receipt);n=args['frames'];keys=args['keys']
        require(request.get('op')=='step' and type(n) is int and 1<=n<=self.max_frames
            and r.get('completedGameFrames')==r.get('requestedGameFrames')==r.get('observedFieldFrames')==n
            and request['startFrame']==self.command_end,'matrix normal command differs')
        require(isinstance(keys,list) and len(keys)==len(set(keys)) and all(k in KEYS for k in keys),
                'matrix input keys differ')
        mask=sum(KEYS[k] for k in keys);case=self.current['case']
        if mask:
            require(n==1 and len(self.cases)<len(self.configurations),'matrix input must be one frame')
            if case['index']==64 and (self.gate is None or not self.gate['complete']):
                require(keys==['LEFT'] and self.current['inputFrame'] is None,'matrix gate input differs')
                if self.gate is None:
                    self.gate=dict(startFrame=request['startFrame'],complete=False,released=False,
                        before=deepcopy(self.current['origin']),commit=self.current['commit'])
            else:
                require(keys==case['keys'] and not self.current['ticks'] and not self.current['events']
                    and (case['index']!=64 or self.gate['released']),'matrix motion input differs')
                if self.current['inputFrame'] is None:self.current['inputFrame']=request['startFrame']
        self.commands.append(dict(startFrame=request['startFrame'],endFrame=request['startFrame']+n,mask=mask))
        self.command_end+=n
        return self.result()

    def _input(self,value,frame):
        matches=[c for c in self.commands if c['startFrame']<frame<=c['endFrame']]
        require(len(matches)==1,'matrix command window missing')
        command=matches[0];mask=value['heldKeys']
        require(type(mask) is int and mask==value['rawHeld'] and value['simulatedKeys']==0,
                'matrix native input differs')
        waiting=(not self.current['ticks'] and not self.current['events']
                 and len(self.cases)<len(self.configurations))
        stale_release=(command['mask']==0 and frame==command['startFrame']+1
            and any(c['endFrame']==command['startFrame'] and c['mask']==mask and mask!=0 for c in self.commands))
        require(mask==command['mask'] or mask==0 and waiting or stale_release,'matrix native input differs')
        return command,mask

    def _tick(self,data):
        require(self.current is not None and data.get('normalReturn') is True
            and data['motionPointer']==self.motion_pointer and data['completedFrame']==self.last['frame'],
            'matrix native tick boundary differs')
        before,after=data['before'],data['after']
        require(decode_motion(bytes.fromhex(before['rawHex']))==before
            and decode_motion(bytes.fromhex(after['rawHex']))==after
            and decode_sample(bytes.fromhex(data['sample']['rawHex']))==data['sample'],
            'matrix raw Tick bytes differ')
        require(before['plan']==after['plan'] and data['returnFlags']==data['returnValue']==data['sample']['flags']
            and data['entryClock']==dict(actorFrame=data['entryActorFrame'],nativeCycle=data['entryNativeCycle'])
            and data['returnClock']==dict(actorFrame=data['returnActorFrame'],nativeCycle=data['returnNativeCycle']),
            'matrix Tick return or clock differs')
        for key in ('beforeCurrent','afterCurrent'):
            current=data[key];public=current['publicSubject']
            require(current['subject']==self.subject and all(public.get(k)==self.actor.get(k) for k in IDENTITY)
                and current['sourceIdentity']==self.actor['sourceIdentity']
                and current['playerPointer']==self.actor['engineIdentity']['anchorPointer']
                and current['mountPointer']==self.actor['engineIdentity']['pointer']
                and all(current['worldContext'].get(k)==v for k,v in self.initial['context'].items()),
                'matrix native tick owner differs')
            stable={k:current[k] for k in ('subject','sourceIdentity','engineIdentity','worldContext',
                'playerPointer','mountPointer','avatarPointer')}
            if self.tick_owner is None:self.tick_owner=deepcopy(stable)
            require(stable==self.tick_owner,'matrix native engine binding changed')
        moving=before['phase']=='MOVING' and before['plan']['kind']==1
        require(data['movingWalk'] is moving and before['phase'] not in ('SUSPENDED','CANCELED'),
                'matrix wrong motion or cancellation')
        self.ticks+=1;self.moving+=int(moving)
        self.last_tick=dict(completedFrame=data['completedFrame'],entryElapsed=before['elapsed'],returnElapsed=after['elapsed'],
            reservationId=after['plan']['reservationId'],qualification=data['qualification'])
        require(self.ticks<=8192,'matrix native callback bound exceeded')
        try:self._input(data['input'],data['completedFrame']+1)
        except (ValueError,KeyError,TypeError) as error:raise ValueError('matrix native tick input differs') from error
        if not moving:return
        self.lastMovingTick=deepcopy(data)
        c=self.current;plan=before['plan'];case=c['case']
        require(len(self.cases)<len(self.configurations) and c['inputFrame'] is not None
            and len(c['ticks'])<case['duration'],'matrix extra or unrequested moving tick')
        dx,dy=DELTAS[case['direction']]
        # Mounted plans carry a cardinal presentation direction. The actual
        # diagonal travel is the exact origin/target vector, not a facing enum.
        headings = (0, 2) if case['direction'] == 4 else (1, 3) if case['direction'] == 7 else (case['direction'],)
        require(plan['duration']==case['duration'] and plan['direction'] in headings
            and plan['facing']==plan['direction'] and data['sample']['facing']==plan['facing']
            and plan['distance']==1 and plan['origin']==[c['origin']['x'],c['origin']['y']]
            and plan['target']==[c['origin']['x']+dx,c['origin']['y']+dy]
            and plan['fieldEpoch']==self.initial['context']['fieldEpoch']
            and plan['arcHeightQ4']==plan['spinSpeed']==plan['swayWidth']==plan['pauseFrames']==0,
            'matrix native plan differs')
        if c['reservation'] is None:c['reservation']=plan['reservationId']
        require(plan['reservationId']==c['reservation'] and plan['reservationId']>0
            and all(data[k]['publicSubject']['reservationId']==plan['reservationId'] for k in ('beforeCurrent','afterCurrent')),
            'matrix reservation changed')
        c['subject']=deepcopy(self.subject)
        tick={}
        for endpoint,clock in (('before','entryClock'),('after','returnClock')):
            value=data[endpoint]
            tick[endpoint]=dict(elapsed=value['elapsed'],duration=value['plan']['duration'],phase=value['phase'],
                subject=self.subject,reservationId=value['plan']['reservationId'],frame=data['completedFrame'],**data[clock])
        c['ticks'].append(tick)

    def observe(self,snapshot,events):
        if self.failures:return self.result()
        try:
            require(self.initial is not None and not self.closed,'matrix observation outside window')
            actor=self._actor(snapshot)
            require(snapshot['observationBoundary']=='main-task-queue-completion'
                and snapshot['frame']==self.last['frame']+1 and snapshot['nativeCycle']>self.last['nativeCycle'],
                'matrix completed frame gap')
            self.frames+=1;require(self.frames<=self.max_frames,'matrix frame budget exceeded')
            n=snapshot['nativeObservation']
            require(n.get('installedBeforeBoot') is True and n.get('coverageComplete') is True
                and n.get('error') is None and n.get('eventsDropped')==n.get('profilesEvicted')==0,
                'matrix native coverage incomplete')
            for event in events:
                data=event['data'];require(event['frame']==snapshot['frame'],'matrix event delivery differs')
                if event['kind']=='native-observation':
                    require(data['sequence']==self.sequence+1,'matrix native sequence gap');self.sequence+=1
                    require(self.last['nativeCycle']<=data['entryNativeCycle']<=data['returnNativeCycle']<=snapshot['nativeCycle'],
                            'matrix native clock gap')
                    if data.get('observation')=='walk-matrix-tick':self._tick(data)
                    if data.get('observation')=='walk-policy' and data.get('slot')==self.subject['handle']['slot']:
                        if data.get('operation') in (1,3):
                            require(data.get('laneHex')==self.configurations[-1]['profileHex'],'matrix native profile differs')
                elif event['kind']=='native':
                    stream=data['traceStream'];require(data['sequence']==self.streams.get(stream,0)+1,'matrix trace sequence gap')
                    self.streams[stream]=data['sequence']
                    if data['actorHandle']!=self.actor['handle']['value']:continue
                    require(data['actor']=={k:v for k,v in self.actor['handle'].items() if k!='value'},'matrix trace identity differs')
                    require(data['event'] not in ('MOTION_CANCELED','ACTOR_REBOUND','CONTEXT_CHANGED','CONTROL_REBOUND'),
                            'matrix canceled or rebound')
                    if data['event'] in LIFECYCLE:
                        require(self.current['inputFrame'] is not None and len(self.cases)<len(self.configurations),
                                'matrix unrequested lifecycle')
                        self.current['events'].append(dict(data,frame=event['frame'],subject=self.subject))
                        require(len(self.current['events'])<=4,'matrix extra lifecycle')
                elif event['kind']=='trace-status':
                    require(data.get('code')=='ring-overwrite' and data.get('diagnosticOnly') is True
                        and data.get('unreadEventsLost')==0,'matrix trace coverage gap')
                else:raise ValueError('matrix unexpected event kind')
            require(n['sequence']==self.sequence,'matrix missing native observation')
            reader_closed=snapshot['walkMatrix'].get('closed')
            require(type(reader_closed) is bool,'matrix reader close state missing')
            self._reader(snapshot['walkMatrix'],reader_closed)
            selector=snapshot['selector']
            command,actual_mask=self._input(selector,snapshot['frame'])
            c=self.current
            require(actor['movementPolicy']['skid']==actor['movementPolicy']['pendingSkid']==0,
                    'matrix unexpected skid')
            require(c['commit']<=actor['commitSequence']<=c['commit']+int(c['inputFrame'] is not None),
                    'matrix extra commit')
            if self.gate is not None and not self.gate['complete']:
                require(self._idle(actor) and actor['logical']==self.gate['before'] and actor['commitSequence']==self.gate['commit']
                    and actor['movementPolicy']['pending']==0 and not c['ticks'] and not c['events'],
                    'matrix cardinal gate moved')
                if command['mask']==actual_mask==KEYS['LEFT']:
                    self.gate.update(complete=True,after=deepcopy(actor['logical']),mode=actor['motionPhase'],
                        pending=actor['movementPolicy']['pending'])
            if self.gate is not None and self.gate['complete'] and not self.gate['released']:
                require(self._idle(actor) and actor['logical']==self.gate['before']
                    and actor['commitSequence']==self.gate['commit'],'matrix gate release moved')
                if command['mask']==actual_mask==0:self.gate['released']=True
            self.last=deepcopy(snapshot)
            if c['events'] and c['events'][-1]['event']=='CONTROL_RETURNED' and len(self.cases)<len(self.configurations):
                motion={k:c[k] for k in ('case','subject','reservation','ticks','events')}
                validate_motion(**motion)
                dx,dy=DELTAS[c['case']['direction']]
                require(self._idle(actor) and actor['movementPolicy']['pending']==0 and actor['commitSequence']==c['commit']+1
                    and actor['logical']==dict(x=c['origin']['x']+dx,y=c['origin']['y']+dy),'matrix terminal displacement differs')
                player,mount=snapshot['player'],actor['engineObject']
                require(all(type(player.get('pos_'+axis)) is int and player['pos_'+axis]==mount.get('pos_'+axis)
                    for axis in 'xyz') and player['unk88_y']==mount['unk88_y']==0
                    and player['face_y']-mount['face_y']==32768,'matrix completed pair base differs')
                self.cases.append(deepcopy(motion))
            require(not reader_closed or len(self.cases)==len(self.configurations),
                    'matrix reader closed during motion')
            return self.result()
        except (ValueError,KeyError,TypeError) as error:
            self.failures.append(str(error));return self.result()

    def stage(self,name):
        if self.failures:return False
        if name=='case-started':return self.current is not None and bool(self.current['events'])
        if name=='case-complete':return bool(self.configurations) and len(self.cases)==len(self.configurations)
        if name=='gate-complete':return self.gate is not None and self.gate['complete']
        if name=='gate-released':return self.gate is not None and self.gate['released']
        return False

    @property
    def ready(self):
        return not self.failures and len(self.cases)==self.case_limit and (self.case_limit==2 or self.stage('gate-complete'))

    def close(self,receipt,snapshot):
        from tools.overworld.devtools_test_contract import _same_mounted_reader_boundary
        require(not self.closed and snapshot==self.last and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False,'matrix close boundary differs')
        endpoint=receipt.get('snapshot',{})
        require(_same_mounted_reader_boundary(snapshot,endpoint)
            and all(endpoint.get(k)==snapshot.get(k) for k in ('selector','fieldControl','observationBoundary')),
            'matrix close snapshot differs')
        self._reader(receipt,True);self.closed=True;self.cleanup=deepcopy(receipt)
        return self.finish()

    def finish(self):
        result=self.result(full=True)
        if not result['passed'] and not self.failures and self.current and self.current['ticks']:
            missing=[name for name in LIFECYCLE if not any(e['event']==name for e in self.current['events'])]
            if missing:
                self.failures.append('matrix exact lifecycle missing: '+missing[0])
                result['failures']=list(self.failures)
        if not result['passed']:result['failures']=result['failures'] or ['matrix incomplete']
        return result

    def result(self,full=False):
        # Per-frame calls need progress, not another copy of every old tick.
        full=full or self.ready or self.closed
        gate=None if not self.stage('gate-complete') else dict(before=[self.gate['before'][k] for k in ('x','y')],
            after=[self.gate['after'][k] for k in ('x','y')],mode=self.gate['mode'],pending=self.gate['pending'])
        vectors=validate_matrix(self.cases,gate) if self.ready and self.case_limit==65 else None
        evidence={}
        if vectors is not None:
            for claim,name,value in (
                ('natural-input','started-motion-count',sum(e['event']=='MOTION_STARTED' for c in self.cases for e in c['events'])),
                ('live-actor-identity','mounted-frames-cyndaquil-identity',
                    [1,self.actor['role'],self.actor['species'],int(self.actor['presentationAttached'])]),
                ('profile-resolution','resolved-frame-counts',vectors['counts']),
                ('frame-pacing','elapsed-frame-sequences',vectors['elapsed']),
                ('control-release','completed-motion-count',len(self.cases)),
                ('control-release','terminal-mount-state',['IDLE',0])):
                evidence.setdefault(claim,[]).append(dict(name=name,actual=value))
        return dict(passed=self.ready and self.closed,acceptedProof=False,ready=self.ready,closed=self.closed,
            expectedCases=self.case_limit,prefixOnly=self.case_limit!=65,frames=self.frames,failures=list(self.failures),
            subject=deepcopy(self.subject),initial=deepcopy(self.initial) if full else None,
            terminalSnapshot=deepcopy(self.last) if full else None,
            terminal=dict(phase='IDLE' if self.last and self._idle(next(a for a in self.last['actors'] if a['handle']==self.subject['handle'])) else None,pending=0 if self.ready else None),
            completedCases=len(self.cases),startedMotions=len(self.cases)+(int(bool(self.current and self.current['events'])) if len(self.cases)<len(self.configurations) else 0),
            completedMotions=len(self.cases),cases=deepcopy(self.cases) if full else [],
            configurations=deepcopy(self.configurations) if full else [],
            diagonalAttempt=gate,vectors=vectors,proofEvidence=evidence,cleanup=deepcopy(self.cleanup))

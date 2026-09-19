"""Bounded Stomp stream replay. No Tick reader and no generated game samples."""
from copy import deepcopy

from tools.overworld.devtools_stomp_contract import CASES, KIND, validate_stomp, validate_lifecycle, validate_feedback, validate_shared_policies, _idle, same_completed_object
from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement
from tools.overworld.devtools_corner_measurement import KEYS, ENVELOPE
from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_mount_pacing_observer import ENGINE
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
from tools.overworld.devtools_wild_walk_measurement import IDENTITY, LIFECYCLE

SINKS=('dust','allocate','init','sound','soundStart')


def require(ok,message):
    if not ok:raise ValueError('Stomp stream: '+message)


def native(value):return {k:v for k,v in value.items() if k not in ENVELOPE}


class StompMeasurement:
    _actor=WalkMatrixMeasurement._actor
    _input=WalkMatrixMeasurement._input
    def __init__(self,max_frames):
        require(type(max_frames) is int and 1<=max_frames<=3000,'invalid frame bound')
        self.max_frames=max_frames
        self.initial=self.last=self.subject=self.actor=self.current=None
        self.configurations=[];self.cases=[];self.failures=[];self.commands=[]
        self.frames=self.sequence=self.step_count=0;self.streams={}
        self.counts=dict.fromkeys(('policy',*SINKS),0)
        self.pending={k:[] for k in SINKS};self.latest=None;self.owner=None
        self.closed=False;self.cleanup=None;self.command_end=None
    def configure(self,receipt,snapshot):
        q=receipt.get('value',receipt)
        require(not self.closed and not self.failures and len(self.configurations)==len(self.cases)<2,
            'configure before prior completion')
        case=CASES[len(self.cases)]
        require(q.get('completed') is True and q.get('prepared') is True and q.get('acceptedProof') is False
            and q.get('guestAdvanced') is False and q.get('scope')=='prepared-idle-mounted-walk-fixture'
            and q.get('directionMode')==0 and q.get('travelTime')==case['duration'] and q.get('stompTime')==2
            and q.get('changedOffsets')==[7,19,50,51,70],'fixture contract differs')
        before,after=q['before'],q['after']
        raw=bytes.fromhex(before['mountStateHex']);actual=bytes.fromhex(after['mountStateHex'])
        require(len(raw)==len(actual)==184,'fixture native bytes missing')
        expected=bytearray(raw)
        for k,v in ((7,case['duration']),(19,0),(50,0),(51,case['duration']),(70,2)):expected[8+k]=v
        require(actual==bytes(expected) and actual.hex()==q['expectedStateHex']
            and before['profileHex']==raw[8:80].hex() and after['profileHex']==actual[8:80].hex()
            and before['readiness']==after['readiness'] and before['clock']==after['clock']
            and before['bindingHex']==after['bindingHex']==actual[80:96].hex()
            and before['sessionGeneration']==after['sessionGeneration'] and actual[20]==1,
            'fixture changed unrelated native state')
        select_current_actor(snapshot,q['subject'])
        actor=next(a for a in snapshot['actors'] if a['handle']==q['subject']['handle'])
        require(_idle(actor) and all(after['readiness']['actor'].get(k)==actor.get(k)
            for k in (*IDENTITY,'logical','commitSequence')),'fixture not coherent idle')
        require(set(after['clock'])=={'frame','nativeCycle'}
            and all(after['clock'][k]==snapshot[k] for k in ('frame','nativeCycle')),
            'fixture clock differs')
        if self.initial is not None:
            from tools.overworld.devtools_test_contract import _same_mounted_reader_boundary
            self._actor(snapshot)
            require(_same_mounted_reader_boundary(self.last,snapshot)
                and before['profileHex']==self.configurations[-1]['profileHex'],'intercase fixture boundary differs')
        self.configurations.append(dict(case=case,profileHex=after['profileHex'],beforeProfileHex=before['profileHex'],
            bindingHex=after['bindingHex'],sessionGeneration=after['sessionGeneration']))
        self.current=dict(case=deepcopy(case),subject=self.subject,reservation=None,events=[],steps=[],poses=[],policies=[],
            initial=deepcopy(snapshot),input=None,ticks=[],inputFrame=None,
            feedback=dict(complete=False,startFrame=snapshot['frame'],endFrame=None,
                counts=dict.fromkeys(('policy',*SINKS),0),calls=[]))
        return self.result()
    def arm(self,subject,snapshot,receipt,trace_sequences=None):
        require(self.initial is None and len(self.configurations)==1,'arm needs first fixture')
        self.subject=deepcopy(subject);self.actor=deepcopy(self._actor(snapshot))
        require(_idle(self.actor),'arm not idle')
        self.initial=self.last=deepcopy(snapshot);self.current['initial']=deepcopy(snapshot)
        self.current['subject']=deepcopy(subject);self.current['feedback']['startFrame']=snapshot['frame']
        self.command_end=snapshot['frame'];self.sequence=snapshot['nativeObservation']['sequence']
        self.streams=dict(trace_sequences or {});self._reader(receipt.get('stompFeedback',receipt),False,pose=False)
        return self.result()
    def command(self,request,receipt):
        require(self.initial is not None and not self.closed and not self.failures,'command outside window')
        args=request['args'];r=receipt.get('receipt',receipt);n=args['frames'];keys=args['keys']
        require(request['op']=='step' and type(n) is int and 1<=n<=self.max_frames
            and all(r.get(k)==n for k in ('requestedGameFrames','completedGameFrames','observedFieldFrames'))
            and request['startFrame']==self.command_end,'normal command boundary differs')
        require(isinstance(keys,list) and (keys==[] or len(keys)==1 and keys[0] in ('UP','DOWN','LEFT','RIGHT')),
            'input keys differ')
        if keys:
            require(n==1 and len(self.cases)<len(self.configurations) and not self.current['events']
                and self.current['input'] is None,'held input continued after admission')
            if self.current['inputFrame'] is None:self.current['inputFrame']=request['startFrame']
        self.commands.append(dict(startFrame=request['startFrame'],endFrame=request['startFrame']+n,
            mask=sum(KEYS[k] for k in keys),keys=deepcopy(keys)))
        self.command_end+=n
    def _identity(self,current):
        require(current['subject']==self.subject and all(current['publicSubject'].get(k)==self.actor.get(k) for k in IDENTITY)
            and current['sourceIdentity']==self.actor['sourceIdentity']
            and current['engineIdentity']=={k:self.actor['engineIdentity'][k] for k in ENGINE}
            and current['playerPointer']==self.actor['engineIdentity']['anchorPointer']
            and current['mountPointer']==self.actor['engineIdentity']['pointer']
            and all(current['worldContext'].get(k)==v for k,v in self.initial['context'].items()),'native owner differs')
        owner={k:current[k] for k in ('subject','sourceIdentity','engineIdentity','worldContext','playerPointer','mountPointer','avatarPointer')}
        if self.owner is None:self.owner=deepcopy(owner)
        require(owner==self.owner,'native binding changed')
    def _reader(self,r,closed,pose=True):
        require(r.get('armed') is True and r.get('closed') is closed and r.get('failure') is None
            and r.get('acceptedProof') is False and r.get('guestMemoryWrites')==0 and r.get('pending')==0
            and r.get('subject')==self.subject and r.get('startFrame')==self.initial['frame']
            and r.get('counts')==self.counts and r.get('playerStepCount')==self.step_count,
            'reader coverage/counts differ')
        if self.latest is not None:require(native(r['latest'])==self.latest,'reader last policy differs')
        if pose:
            p=r['latestCompletedPose'];self._identity(p)
            require(p['boundary']=='main-task-queue-completion' and all(p[k]==self.last[k] for k in ('frame','actorFrame'))
                and self.last['nativeCycle']==p['nativeCycle'] and same_completed_object(self.last['player'],p['player'])
                and same_completed_object(next(a for a in self.last['actors'] if a['handle']==self.subject['handle'])['engineObject'],p['mount']),
                'native completed pose differs')
            require(p['input']['heldKeys']==self.last['selector']['heldKeys'],'pose input differs')
            check_pair_pose(p)
    def observe(self,snapshot,events):
        if self.failures:return self.result()
        try:
            require(self.initial is not None and not self.closed,'observation outside window')
            actor=self._actor(snapshot)
            require(snapshot['observationBoundary']=='main-task-queue-completion'
                and snapshot['frame']==self.last['frame']+1 and snapshot['actorFrame']==self.last['actorFrame']+1
                and snapshot['nativeCycle']>self.last['nativeCycle'],'completed frame gap')
            self.frames+=1;require(self.frames<=self.max_frames,'frame budget exceeded')
            command,mask=self._input(snapshot['selector'],snapshot['frame'])
            c=self.current;n=snapshot['nativeObservation']
            require(n.get('installedBeforeBoot') is True and n.get('coverageComplete') is True and n.get('error') is None
                and n.get('eventsDropped')==n.get('profilesEvicted')==0,'native coverage incomplete')
            for event in events:
                d=event['data'];require(event['frame']==snapshot['frame'],'event delivery differs')
                if event['kind']=='native-observation':
                    require(d['sequence']==self.sequence+1,'native sequence gap');self.sequence+=1
                    require(self.last['nativeCycle']<=d['entryNativeCycle']<=d['returnNativeCycle']<=snapshot['nativeCycle'],
                        'native clock gap')
                    label=d.get('observation','')
                    if label=='walk-policy' and d.get('slot')==self.subject['handle']['slot']:
                        require(len(self.cases)<len(self.configurations),'shared policy after completed case')
                        request,response=(bytes.fromhex(d[k]) for k in ('requestHex','responseHex'))
                        require(len(request)==len(response)==28 and request[:4]==b'\x01\x00\x1c\x00'
                            and request[:10]==response[:10] and request[8]==d['slot'] and request[9]==d['operation']
                            and type(d['returnValue']) is int and d['returnValue']==1,'shared policy ABI/result differs')
                        require(all(d[k].get('status')=='observed-public-subject'
                            and all(d[k].get(field)==self.actor.get(field) for field in IDENTITY)
                            for k in ('publicSubject','publicSubjectAfter')),'shared policy public identity differs')
                        if d['operation'] in (1,3):require(d.get('laneHex')==self.configurations[-1]['profileHex'],'shared policy lane differs')
                        if d['operation']==1 and response[16]==2:
                            require(c['input'] is None and len(command['keys'])==1 and mask==command['mask'],
                                'native admission lacks normal input')
                            require(request[10]==response[17]=={'UP':0,'DOWN':1,'LEFT':2,'RIGHT':3}[command['keys'][0]],
                                'native admission direction differs')
                            require(response[19]==c['case']['duration'],'native input travel time differs')
                            c['input']=dict(keys=command['keys'],requestedGameFrames=1,completedGameFrames=1,observedFieldFrames=1)
                        c['policies'].append(dict(deepcopy(d),frame=event['frame']))
                        require(len(c['policies'])<=128,'shared policy bound exceeded')
                    if not label.startswith('stomp-'):continue
                    require(len(self.cases)<len(self.configurations),'native callback after completed case')
                    kind=d['kind'];self._identity(d if kind=='playerStep' else d['before'])
                    require(d['normalReturn'] is True and d['completedFrame']==self.last['frame']
                        and d['entryClock']==dict(actorFrame=d['entryActorFrame'],nativeCycle=d['entryNativeCycle'])
                        and d['returnClock']==dict(actorFrame=d['returnActorFrame'],nativeCycle=d['returnNativeCycle']),
                        'native return framing differs')
                    if kind=='playerStep':
                        require(label=='stomp-playerStep' and d['eventConsumed']==0,'player step result differs')
                        self.step_count+=1
                        require(self.step_count<=2 and not c['steps'],'extra native player step')
                        c['steps'].append(dict(subject=self.subject,playerPointer=d['playerPointer'],normalReturn=True,
                            eventConsumed=d['eventConsumed'],frame=d['completedFrame'],**d['returnClock']))
                    else:
                        require(kind in self.counts and label=='stomp-'+kind,'unexpected feedback kind')
                        self.counts[kind]+=1;c['feedback']['counts'][kind]+=1
                        require(self.counts[kind]<=64,'native call bound exceeded')
                        if kind in SINKS:self.pending[kind].append(native(d))
                        else:
                            require(d['feedback']==self.pending,'nested feedback stream differs')
                            self.pending={k:[] for k in SINKS};self.latest=native(d)
                            require(d['profileHex']==self.configurations[-1]['profileHex'],'native profile differs')
                            raw=bytes.fromhex(d['policyHex'])
                            c['feedback']['calls'].append(deepcopy(self.latest))
                elif event['kind']=='native':
                    stream=d['traceStream'];require(d['sequence']==self.streams.get(stream,0)+1,'trace sequence gap')
                    self.streams[stream]=d['sequence']
                    if d['actorHandle']!=self.subject['handle']['value']:continue
                    require(d['actor']=={k:v for k,v in self.subject['handle'].items() if k!='value'},'trace owner differs')
                    require(d['event'] not in ('MOTION_CANCELED','ACTOR_REBOUND','CONTROL_REBOUND','CONTEXT_CHANGED'),'canceled or rebound')
                    if d['event'] in LIFECYCLE:
                        require(c['inputFrame'] is not None and len(self.cases)<len(self.configurations),'unrequested lifecycle')
                        c['events'].append(dict(d,frame=event['frame'],subject=self.subject))
                        require(len(c['events'])<=4,'extra lifecycle')
                elif event['kind']=='trace-status':
                    require(d.get('code')=='ring-overwrite' and d.get('diagnosticOnly') is True and d.get('unreadEventsLost')==0,
                        'trace coverage gap')
                else:raise ValueError('Stomp stream: unexpected event kind')
            require(n['sequence']==self.sequence,'missing native observation')
            if actor['reservationId']:
                if c['reservation'] is None:c['reservation']=actor['reservationId']
                require(c['reservation']==actor['reservationId'],'reservation changed')
            require(actor['commitSequence'] in (c['initial']['actors'][next(i for i,a in enumerate(c['initial']['actors'])
                if a['handle']==self.subject['handle'])]['commitSequence'],
                c['initial']['actors'][next(i for i,a in enumerate(c['initial']['actors']) if a['handle']==self.subject['handle'])]['commitSequence']+1),
                'extra logical commit')
            self.last=deepcopy(snapshot);self._reader(snapshot['stompFeedback'],False)
            if len(self.cases)<len(self.configurations):
                c['poses'].append(deepcopy(snapshot))
            if c['events'] and c['events'][-1]['event']=='CONTROL_RETURNED' and _idle(actor) and mask==command['mask']==0 and len(c['steps'])==1:
                c['terminal']=deepcopy(snapshot);c['feedback'].update(complete=True,endFrame=snapshot['frame'])
                validate_lifecycle(c);validate_feedback(c['feedback'],c,engine_binding_identity(actor['engineIdentity']));validate_shared_policies(c)
                require(c['reservation'] is not None,'native reservation missing')
                self.cases.append(deepcopy({k:v for k,v in c.items() if k not in ('ticks','inputFrame')}))
            return self.result()
        except (ValueError,KeyError,TypeError,IndexError) as error:
            self.failures.append(str(error));return self.result()
    def stage(self,name):
        return not self.failures and (bool(self.current and self.current['events']) if name=='case-started' else
            bool(self.configurations) and len(self.cases)==len(self.configurations) if name=='case-complete' else False)
    @property
    def ready(self):return not self.failures and len(self.cases)==2
    def close(self,receipt,snapshot):
        from tools.overworld.devtools_test_contract import _same_mounted_reader_boundary
        require(self.ready and not self.closed and snapshot==self.last and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and _same_mounted_reader_boundary(snapshot,receipt.get('snapshot',{}))
            and all(receipt.get('snapshot',{}).get(k)==snapshot.get(k) for k in
                ('selector','fieldControl','observationBoundary')),'close boundary differs')
        self._reader(receipt['stompFeedback'],True);self.closed=True;self.cleanup=deepcopy(receipt)
        return self.finish()
    def finish(self):
        if not self.ready and not self.failures:
            missing=[name for name in LIFECYCLE if not self.current or not any(e['event']==name for e in self.current['events'])]
            self.failures.append('Stomp stream: exact lifecycle missing: '+missing[0] if missing else 'Stomp stream: incomplete')
        result=self.result(full=True)
        if not self.closed and not result['failures']:result['failures']=['Stomp stream: close missing']
        return result
    def result(self,full=False):
        full=full or self.ready or self.closed
        proof=validate_stomp(self.cases,self.subject,self.last)['proofEvidence'] if self.ready else {}
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,closed=self.closed,
            acceptedProof=False,subject=self.subject,frames=self.frames,failures=self.failures,
            initial=self.initial if full else None,terminalSnapshot=self.last if full else None,
            cases=self.cases if full else [],configurations=self.configurations if full else [],
            proofEvidence=proof,cleanup=self.cleanup,completedCases=len(self.cases),counts=self.counts,playerStepCount=self.step_count,
            lastPolicy=self.latest))

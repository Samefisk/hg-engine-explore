"""A mounted Teleport starts while facing a loaded door, then Walk enters it."""
from copy import deepcopy
from .devtools_mounted_teleport_matrix import MountedTeleportMatrixMeasurement
from .devtools_mount_control_stress import MountControlStressMeasurement, check_snapshot_pair, require
from .normal_play_observer import complete_travel

KIND='warp-gate-v1'
REQUIREMENT='legacy.warp-blocked-mid-motion'
DOORS={(564,391):69,(555,391):68,(547,399):70,(558,401):71,(567,405):72}


class WarpGateMeasurement(MountedTeleportMatrixMeasurement):
    def __init__(self,max_frames=1200):
        require(type(max_frames) is int and 1<=max_frames<=1200,'invalid warp frame bound')
        super().__init__(max_frames)
        self.rules.update(motions=2)
        self.door=None;self.destination=None;self.walk_restored=False;self.walk_pressed=False;self.walk_started=False
        self.journal=[];self.original_profile=None;self.arrival=None

    def arm(self,subject,snapshot,trace_sequences=None,door=None):
        require(door is not None and tuple(door) in DOORS,'unknown warp door fixture')
        require(snapshot['context'].get('mapId')==67,'warp fixture is not Cherrygrove')
        require(snapshot['player']['x']==door[0] and snapshot['player']['y']==door[1]+1,
                'warp fixture must start immediately south of door')
        streams={int(stream):sequence for stream,sequence in (trace_sequences or {}).items()}
        super().arm(subject,snapshot,streams)
        self.door=list(door);self.destination=DOORS[tuple(door)]
        self.full_initial=deepcopy(snapshot)
        self.initial_streams=streams;self.bound_subject=deepcopy(self.subject)

    def configure(self,receipt,snapshot):
        require(len(self.cases)<2,'two warp Teleports already complete')
        if self.original_profile is None:
            rows=receipt.get('value',receipt).get('loadedWarps',self.full_initial.get('terrain',{}).get('warps',[]))
            require(any((row.get('x'),row.get('y'))==tuple(self.door) and row.get('header')==self.destination for row in rows), 'loaded warp table does not match door')
            self.original_profile=bytes.fromhex(receipt.get('value',receipt)['before']['profileHex'])
            require(self.original_profile[12]==1,'warp original profile must use Walk')
        super().configure(receipt,snapshot)
        self.journal.append(dict(op='configure',receipt=deepcopy(receipt),snapshot=deepcopy(snapshot)))
        return self.result()

    def restore(self,receipt,snapshot):
        require(len(self.cases)==2 and self.config is None and not self.walk_restored
                and not self.failures,'warp Walk restore before two complete Teleports')
        value=receipt.get('value',receipt);before,after=value['before'],value['after']
        actor=self._actor(snapshot)
        require(before['readiness'].get('subject')==self.subject and all(before['readiness'].get('actor',{}).get(k)==actor.get(k) for k in ('handle','subjectIdentity','species','role','authorityGeneration','engineAnchorGeneration','presentationGeneration')), 'warp restore actor differs')
        a,b=bytes.fromhex(before['mountStateHex']),bytes.fromhex(after['mountStateHex'])
        require(len(a)==len(b)==184 and a[8:80]==self.last_profile
                and bytes.fromhex(before['profileHex'])==a[8:80]
                and bytes.fromhex(after['profileHex'])==self.original_profile
                and b==a[:8]+self.original_profile+a[80:], 'warp restore changed unrelated state')
        require(value.get('completed') is True and value.get('guestAdvanced') is False
                and value.get('subject')==self.subject and value.get('changedOffsets')==[12,23,24]
                and before['bindingHex']==after['bindingHex']==a[80:96].hex()
                and before['clock']==after['clock'] and before['readiness']==after['readiness']
                and before['sessionGeneration']==after['sessionGeneration']>0
                and snapshot['frame']==self.last['frame'] and snapshot['nativeCycle']==self.last['nativeCycle'],
                'warp restore receipt differs')
        self.walk_restored=True
        self.journal.append(dict(op='restore',receipt=deepcopy(receipt),snapshot=deepcopy(snapshot)))
        return self.result()

    def observe(self,snapshot,events):
        if self.phase=='unarmed' or self.failures:return self.result()
        try:
            require(not self.closed and self.frames<self.max_frames and len(events)<=256,'warp observation bound exceeded')
            self.journal.append(dict(op='observe',snapshot=deepcopy(snapshot),events=deepcopy(events)))
            loading=snapshot.get('fieldAvailable') is False
            loading_batch=loading or self.last.get('fieldAvailable') is False
            require(snapshot['frame']==self.last['frame']+1
                    and (snapshot['nativeCycle']>self.last['nativeCycle']
                         or (loading_batch and snapshot['nativeCycle']==self.last['nativeCycle']))
                    and snapshot.get('observationBoundary')=='main-task-queue-completion','warp completed frame gap')
            self.frames+=1
            native=snapshot['nativeObservation']
            require(native.get('installedBeforeBoot') is True and native.get('coverageComplete') is True
                    and native.get('error') is None and native.get('eventsDropped')==0
                    and native.get('profilesEvicted')==0,'warp native coverage incomplete')
            inputs=snapshot.get('selector',{});held=inputs.get('rawHeld',inputs.get('heldKeys',0))
            require((loading and self.walk_restored and self.walk_started) or
                    (inputs.get('heldKeys')==held and inputs.get('physicalPressed') in (0, held)
                    and inputs.get('simulatedKeys')==0),'warp input ownership differs')
            if self.walk_restored:
                for event in events:
                    data=event.get('data',{})
                    require(event.get('frame')==snapshot['frame'],'warp event frame differs')
                    if event.get('kind')=='native-observation':
                        require(data.get('sequence')==self.sequence+1,'warp native sequence gap');self.sequence+=1
                    elif event.get('kind')=='native':
                        stream,sequence=data.get('traceStream'),data.get('sequence')
                        require(type(sequence) is int and (stream not in self.streams or sequence==self.streams[stream]+1),'warp semantic sequence gap')
                        self.streams[stream]=sequence
                    elif event.get('kind')=='trace-status':
                        if data.get('code')=='ring-overwrite':
                            valid=(data.get('unreadEventsLost')==0
                                   and data.get('coverageComplete',True) is True
                                   and data.get('diagnosticOnly') is True
                                   and data.get('traceStream') in self.streams)
                        elif data.get('code')=='field-epoch-changed':
                            valid=(set(data)=={'code','traceStream','diagnosticOnly','previousEpoch',
                                               'fieldEpoch','sequenceReset'}
                                   and data.get('diagnosticOnly') is True
                                   and data.get('sequenceReset') is False
                                   and data.get('previousEpoch')==self.initial['context']['fieldEpoch']
                                   and data.get('fieldEpoch')==snapshot['context']['fieldEpoch'])
                        else:valid=False
                        require(valid,'warp trace lost events')
                    else:raise ValueError('warp unknown event')
                require(native['sequence']==self.sequence,'warp missing native receipt')
                if loading:
                    self.last=deepcopy(snapshot)
                    return self.result()
                require(held in (0,64),'warp normal entry requires UP input')
                if held==64:self.walk_pressed=True
                if snapshot['context'].get('mapId')==67 and not self.walk_started:
                    actor=self._actor(snapshot)
                    player=snapshot['player'];field=snapshot.get('fieldControl',{})
                    if (player['x'],player['y'])==tuple(self.door) and field.get('taskPointer') not in (None,0):
                        require(self.walk_pressed and player['facing']==0
                                and actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE'
                                and actor['logical']==dict(x=self.door[0],y=self.door[1]+1)
                                and actor['reservationId']==0, 'warp normal entry lacks UP input')
                        self.walk_started=True
                if snapshot['context'].get('mapId')!=67:
                    require(self.walk_pressed and self.walk_started and snapshot['context'].get('mapId')==self.destination
                            and snapshot.get('fieldAvailable') is True,'warp reached wrong destination')
                    current=snapshot['context'];initial=self.initial['context']
                    rebound=(current['fieldEpoch']!=initial['fieldEpoch']
                             and current['mapGeneration']!=initial['mapGeneration'])
                    if not rebound:
                        require(current['fieldEpoch']==initial['fieldEpoch']
                                and current['mapGeneration']==initial['mapGeneration']
                                and snapshot.get('fieldControl',{}).get('taskPointer') not in (None,0),
                                'warp reached wrong destination')
                        self.last=deepcopy(snapshot)
                        return self.result()
                    self.arrival=deepcopy(snapshot)
                self.last=deepcopy(snapshot)
                return self.result()
            require(snapshot['context']==self.initial['context'] and snapshot.get('fieldAvailable') is True,
                    'warp fired during Teleport')
            actor=self._actor(snapshot)
            require(actor['role']=='MOUNTED' and actor['inputOwnership']==1,'warp lost mounted ownership')
            # Existing Teleport identity helper authenticates temporary hidden presentation.
            for key in ('authorityGeneration','engineAnchorGeneration'):
                require(actor[key]==self.actor[key],'warp actor generation changed')
            prior=self.actor['presentationGeneration'] if self.presentation_generation is None else self.presentation_generation
            attached=self.actor['presentationAttached'] if self.presentation_attached is None else self.presentation_attached
            require((actor['presentationGeneration']==prior and actor['presentationAttached']==attached)
                    or (actor['presentationGeneration']==prior+1 and actor['presentationAttached'] is not attached),
                    'warp presentation generation differs')
            self.presentation_generation=actor['presentationGeneration'];self.presentation_attached=actor['presentationAttached']
            self.subject['presentationGeneration']=actor['presentationGeneration']
            for key,value in (('observedFrame',snapshot['frame']),('engineIdentity',actor['engineIdentity'])):
                if key in self.subject:self.subject[key]=deepcopy(value)
            check_snapshot_pair(snapshot,actor);self._events(snapshot,events,actor)
            index=len(self.cases);mask=128 if index==0 else 64
            allowed=(0,64,mask) if index==0 and not self.case_started else (0,mask)
            require(held in allowed,'warp Teleport direction input differs')
            lag=self._terminal_snapshot_lag(snapshot,actor)
            if actor['motionKind']=='TELEPORT' and not lag:
                require(self.config is not None and actor['motionKindId']==3,'warp unconfigured motion')
                if not self.case_started:
                    require(held==mask,'warp Teleport lacks natural input')
                    origin,target=actor['origin'],actor['target'];x,y=self.door
                    require((origin==dict(x=x,y=y+1) and target==dict(x=x,y=y+7)) if index==0
                            else (origin==dict(zip(('x','y'),self.cases[0]['target'])) and target==dict(x=x,y=y+1)),
                            'Teleport did not start beside the door and return')
                    self.case_started=True
            travel=actor
            if actor['motionKind']=='TELEPORT' and actor['motionPhase']=='COMMIT_PENDING' and not lag:
                travel=deepcopy(actor);travel['motionPhase']='MOVING'
            if not lag:self.recorder.observe(snapshot['frame'],travel,snapshot['player'])
            require(not self.recorder.failures,'warp Teleport travel differs')
            while self.recorder.completed:
                motion=self.recorder.completed.pop(0)
                require(self.case_started and complete_travel(motion) and motion['commitAfter']==(motion['commitBefore']+1)&0xffffffff,
                        'warp incomplete Teleport commit')
                MountControlStressMeasurement._join(self,motion)
                require(actor['motionKind']=='NONE' and actor['motionPhase']=='IDLE' and actor['reservationId']==0
                        and held==0,'warp Teleport control not returned')
                self.cases.append(deepcopy(self.motion_summaries[-1]));self.config=None;self.case_started=False
            self.last=deepcopy(snapshot)
        except (ValueError,KeyError,TypeError,IndexError) as error:self.failures.append(str(error))
        return self.result()

    def stage(self,name):
        return not self.failures and {'case-started':self.case_started,
            'case-complete':bool(self.cases) and self.config is None and self.presentation_attached is True,
            'teleports-complete':len(self.cases)==2 and self.presentation_attached is True,
            'walk-started':self.walk_started, 'arrived':self.ready}.get(name,False)

    @property
    def ready(self):return self.arrival is not None and not self.failures

    def finish(self):
        if not self.ready and not self.failures:self.failures.append('warp requires two gated Teleports and normal Walk entry')
        self.closed=True;return self.result()

    def result(self,*args):
        return deepcopy(dict(kind=KIND,requirement=REQUIREMENT,acceptedProof=False,passed=self.closed and self.ready,
            ready=self.ready,closed=self.closed,failures=self.failures,subject=getattr(self,'bound_subject',self.subject),initial=getattr(self,'full_initial',self.initial),
            maxFrames=self.max_frames,traceSequences=getattr(self,'initial_streams',{}),door=self.door,
            destination=self.destination,cases=self.cases,arrival=self.arrival,journal=self.journal))


def replay(result):
    meter=WarpGateMeasurement(result['maxFrames']);meter.arm(result['subject'],result['initial'],result['traceSequences'],result['door'])
    for row in result['journal']:
        if meter.failures:break
        if row['op']=='observe':meter.observe(row['snapshot'],row['events'])
        else:
            try:getattr(meter,row['op'])(row['receipt'],row['snapshot'])
            except (ValueError,KeyError,TypeError) as error:meter.failures.append(str(error))
    return meter.finish()

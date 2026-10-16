"""Synthetic copies prove finite query witness checks; these are not game proof."""
from copy import deepcopy
import struct
import unittest
from tools.overworld.devtools_cargo_route_continuity import packets, same_graph, follower_witness, wild_witness
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import WildThrowMovingCandidateMeasurement, THROW_APPLICATION_BIT

IMAGE=dict(elfSha256='d'*64,packageSha256='e'*64)
SOURCE=dict(contractVersion=2,romSha256='a'*64,overlaySha256='b'*64,profileSha256='c'*64,queryImage=IMAGE)

def query_event(sample, actor, image=IMAGE, nodes=4, status=0, step=False):
    h=deepcopy(actor['handle']);raw=bytearray(140);raw[104]=status;raw[105]=int(step);raw[138]=status
    work=bytes(28)
    context=dict(cargo=dict(value=65536,slot=0,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1),
        bounds=[580,390,600,420],scopeRevision=1,edges=[],edgeCount=0,requestKey=3,roleMask=1,
        pickupDistance=1,required=1,movementPolicyRevision=123)
    workspace=dict(owner=h,ownerCurrent=True,valid=True,stateSubject=h,stateFrame=sample['actorFrame'],
        storage=0x2300000,nodeCount=nodes,compatibility=context,lastWorkHex=work.hex(),
        origin=dict(x=actor['engineObject']['x'],y=actor['engineObject']['y']))
    after=dict(subject=h,worldSubject=h,frameValid=True,worldFrame=sample['actorFrame'],queryPointer=0x2300000,workspace=workspace)
    return dict(frame=sample['frame'],kind='native-observation',data=dict(observation='throw-cargo-query',slot=h['slot'],
        sequence=sample['frame'],subject=h,boundary='native-cargo-tick-return',entryActorFrame=sample['actorFrame'],
        returnActorFrame=sample['actorFrame'],entryNativeCycle=sample['nativeCycle'],returnNativeCycle=sample['nativeCycle'],
        imageIdentity=dict(**image,loadedEntry=0x2300000,tickEntry=0x2300100,loaderOwner=bytes(28).hex()),
        resultHex=raw.hex(),returnValue=status,resultStatus=status,status=('PENDING','REACHABLE')[status],
        before=deepcopy(after),after=after))


def alert_fixture():
    from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor
    a=actor(74,1,74,402);a.update(matchedLayerMask=1<<15,behaviorFingerprint=5)
    a['engineObject']=dict(x=585,y=402);a.update(motionKind='NONE',motionPhase='IDLE',motionElapsed=0)
    m=WildThrowMovingCandidateMeasurement(SOURCE)
    m.subjects['stantler']=dict(handle=dict(value=65536,slot=0,generation=1,fieldEpoch=1,mapGeneration=1,encounterGeneration=1))
    lane=bytearray(80);lane[3]=20;lane[7]=8;lane[36]=2
    raw=bytearray(lane+lane+bytes(56));struct.pack_into('<II',raw,188,THROW_APPLICATION_BIT|(1<<15),6)
    resolved=dict(observation='behavior-resolved',resolved=True,fingerprint=6,sourceSha256='c'*64,
        resultHex=raw.hex(),lanes=[lane.hex(),lane.hex()])
    a.update(origin=dict(x=585,y=402),target=dict(x=585,y=401),logical=dict(x=585,y=402),commitSequence=0)
    a['engineObject'].update(pos_x=(585<<16)+32768,pos_z=(402<<16)+32768)
    rows=[]
    for frame in range(99,131):
        if frame>=100:a.update(matchedLayerMask=THROW_APPLICATION_BIT|(1<<15),behaviorFingerprint=6)
        s=dict(frame=frame,actorFrame=frame,nativeCycle=frame+1000,pokemonCombat=dict(movementTimers=[dict(
            handle=deepcopy(a['handle']),movementEmoteTimer=max(0,120-frame) if frame>=100 else 0)]))
        e=[]
        if frame==100:e.append(dict(frame=frame,kind='native-observation',data=resolved))
        if frame==99 or frame>=120:e.append(query_event(s,a,nodes=4 if frame<121 else 5,status=int(frame>=121),step=frame>=121))
        if 121<=frame<129:
            a.update(motionKind='WALK',motionPhase='MOVING',motionElapsed=frame-121,motionDuration=8)
            a['engineObject']['pos_z']=(402<<16)+32768-65536*(frame-121)//8
        if frame==121:
            e.append(dict(frame=frame,kind='native',data=dict(sequence=frame*10,event='MOTION_STARTED',valueA=1,valueB=8,actorFrame=frame,
                actorHandle=a['handle']['value'],actor={k:v for k,v in a['handle'].items() if k!='value'})))
        if frame>=129:
            a.update(motionKind='NONE',motionPhase='IDLE',motionElapsed=8,commitSequence=1,logical=dict(x=585,y=401))
            a['engineObject']['pos_z']=(401<<16)+32768
        if frame==129:
            for n,(name,va,vb) in enumerate((('LOGICAL_COMMIT',1,1),('MOTION_FINISHED',1,1),('CONTROL_RETURNED',0,1))):
                e.append(dict(frame=frame,kind='native',data=dict(sequence=frame*10+n,event=name,valueA=va,valueB=vb,actorFrame=frame,
                    actorHandle=a['handle']['value'],actor={k:v for k,v in a['handle'].items() if k!='value'})))
        rows.append((s,e,deepcopy(a)))
    return m,rows


def notice_fixture():
    from tools.overworld.test_devtools_wild_throw_moving_candidate_measurement import interactions
    from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor,ROM,OVERLAY
    from tools.overworld.devtools_wild_throw_moving_candidate_measurement import TRIGGER_CONDITION,CARGO_CONDITION
    from tools.overworld.devtools_records import select_current_actor
    m,rows=alert_fixture();rows=rows[1:];m.latest=dict(nativeCycle=1099);m.source=dict(SOURCE,romSha256=ROM,overlaySha256=OVERLAY)
    cargo=actor(234,0,234,403)
    for sample,events,geo in rows:
        frame=sample['frame'];sample.update(actors=[geo,deepcopy(cargo)],fieldControl=dict(fieldPointer=0x2200000),observationBoundary='main-task-queue-completion',fieldAvailable=True,context=dict(mapId=33,fieldEpoch=1,mapGeneration=1))
        sample['pokemonCombat'].update(available=True,frame=frame,nativeCycle=sample['nativeCycle'],
            identity=dict(romSha256=m.source['romSha256'],overlaySha256=m.source['overlaySha256']))
        sample['pokemonCombat']['interactions']=interactions(sample,frame>=120)
        m.subjects['stantler']=select_current_actor(sample,sample['actors'][1])
        if frame==100:
            events.append(query_event(sample,geo))
            query=next(e for e in events if e.get('data',{}).get('observation')=='throw-cargo-query')
            for stage in ('before','after'):query['data'][stage].update(queryPointer=0,workspace=None)
            query['data']['resultHex']=bytes(140).hex()
            resolved=events[0]['data'];resolved.update(sequence=query['data']['sequence']+1,
                entryActorFrame=frame,returnActorFrame=frame,entryNativeCycle=sample['nativeCycle'],returnNativeCycle=sample['nativeCycle'])
        elif frame>=120:
            for query in [e for e in events if e.get('data',{}).get('observation')=='throw-cargo-query']:
                query['data']['before']['workspace']['compatibility']['required']=0 if frame<=121 else 1
                query['data']['after']['workspace']['compatibility']['required']=0 if frame==120 else 1
    return m,rows

class ContinuityTests(unittest.TestCase):
    def test_cargo_tick_can_cross_vblank_inside_one_completed_interval(self):
        _,rows=alert_fixture();sample,_,actor=rows[0]
        sample.update(frame=840,actorFrame=372,nativeCycle=2156)
        event=query_event(sample,actor)
        event['data'].update(entryNativeCycle=2155,returnNativeCycle=2156)
        for pending_ok in (False,True):
            with self.subTest(pending_ok=pending_ok):
                receipt,=packets(sample,[event],actor,IMAGE,2153,pending_ok=pending_ok)
                self.assertEqual((receipt['frame'],receipt['actorFrame']),(840,372))
                self.assertEqual(receipt['workspace']['owner'],actor['handle'])
                self.assertEqual(receipt['workspace']['stateFrame'],372)

    def test_spanning_cargo_tick_keeps_clock_owner_and_image_guards(self):
        _,rows=alert_fixture();sample,_,actor=rows[0]
        sample.update(frame=840,actorFrame=372,nativeCycle=2156)
        original=query_event(sample,actor)
        original['data'].update(entryNativeCycle=2155,returnNativeCycle=2156)
        for fault in ('old-entry','future-return','reverse-cycle','entry-frame','return-frame',
                      'queue-frame','full-owner','elf-image','package-image','return-boundary'):
            with self.subTest(fault=fault):
                event=deepcopy(original);data=event['data']
                if fault=='old-entry':data['entryNativeCycle']=2153
                elif fault=='future-return':data['returnNativeCycle']=2157
                elif fault=='reverse-cycle':data.update(entryNativeCycle=2156,returnNativeCycle=2155)
                elif fault=='entry-frame':data['entryActorFrame']=371
                elif fault=='return-frame':data['returnActorFrame']=373
                elif fault=='queue-frame':event['frame']=839
                elif fault=='full-owner':data['subject']['encounterGeneration']+=1
                elif fault=='elf-image':data['imageIdentity']['elfSha256']='f'*64
                elif fault=='package-image':data['imageIdentity']['packageSha256']='f'*64
                else:data['boundary']='native-cargo-tick-entry'
                with self.assertRaisesRegex(ValueError,'owner, clock or sealed image'):
                    packets(sample,[event],actor,IMAGE,2153)

    def test_spanning_unprepared_pending_grants_no_route_graph(self):
        _,rows=alert_fixture();sample,_,actor=rows[0]
        sample.update(frame=840,actorFrame=372,nativeCycle=2156)
        event=query_event(sample,actor)
        event['data'].update(entryNativeCycle=2155,returnNativeCycle=2156,resultHex=bytes(140).hex())
        event['data']['after'].update(queryPointer=0,workspace=None)
        self.assertEqual(packets(sample,[event],actor,IMAGE,2153),[])
        event['data']['after']['worldFrame']=371
        with self.assertRaisesRegex(ValueError,'current Pending'):
            packets(sample,[event],actor,IMAGE,2153)

    def test_initial_pending_notice_keeps_alert_then_full_walk_and_binding_fixation(self):
        from tools.overworld.devtools_wild_throw_moving_candidate_proof import route_witness
        m,rows=notice_fixture()
        for sample,events,geo in rows:m._route_sample(sample,events,geo)
        self.assertEqual(m.route_witness['mode'],'initial-pending')
        self.assertEqual(m.route_witness['walk']['returnFrame'],129)
        route_witness(m.route_witness,dict(handle=rows[-1][2]['handle'],subjectIdentity=rows[-1][2]['subjectIdentity']))

    def test_first_prepared_allocation_is_native_and_later_rows_retain_it(self):
        from tools.overworld.devtools_wild_throw_moving_candidate_proof import route_witness
        m,rows=notice_fixture()
        query=next(e['data'] for e in rows[20][1] if e.get('data',{}).get('observation')=='throw-cargo-query')
        query['before'].update(queryPointer=0,workspace=None)
        for sample,events,geo in rows:m._route_sample(sample,events,geo)
        subject=dict(handle=rows[-1][2]['handle'],subjectIdentity=rows[-1][2]['subjectIdentity'])
        route_witness(m.route_witness,subject)
        for fault in ('wrong-allocation','later-ownership-loss','missing-return'):
            with self.subTest(fault=fault):
                witness=deepcopy(m.route_witness)
                if fault=='wrong-allocation':
                    witness['baseline']['allocation']['event']['data']['before']['queryPointer']=123
                elif fault=='later-ownership-loss':
                    row=witness['routeReceipts'][3]
                    for stage in ('before','workspace'):row[stage]['compatibility']['required']=0
                else:witness['walk']['lifecycle'].pop()
                with self.assertRaises(ValueError):route_witness(witness,subject)

    def test_initial_pending_owner_clock_notice_and_full_walk_faults_reject(self):
        faults=('pending-clock','pending-raw','pending-owner','notice-player','alert','slow-walk',
                'ownership-loss','later-ownership-loss','wrong-cargo','missing-return','wrong-commit','missing-query')
        for fault in faults:
            with self.subTest(fault=fault):
                m,rows=notice_fixture()
                if fault.startswith('pending-'):
                    q=next(e['data'] for e in rows[0][1] if e.get('data',{}).get('observation')=='throw-cargo-query')
                    if fault=='pending-clock':q['entryActorFrame']-=1
                    elif fault=='pending-raw':q['resultHex']=bytes(139).hex()
                    else:q['subject']['generation']+=1
                elif fault=='notice-player':
                    binding=rows[0][0]['pokemonCombat']['interactions']['carriers'][0]['bindings']['trigger']
                    binding['target']['kind']='ACTOR'
                elif fault=='alert':rows[1][0]['pokemonCombat']['movementTimers'][0]['movementEmoteTimer']-=1
                elif fault=='slow-walk':rows[21][2]['motionDuration']=9
                elif fault in ('ownership-loss','later-ownership-loss','wrong-cargo','intra-reset'):
                    q=next(e['data'] for e in rows[23][1] if e.get('data',{}).get('observation')=='throw-cargo-query')
                    if fault=='ownership-loss':q['after']['workspace']['compatibility']['required']=0
                    elif fault=='later-ownership-loss':
                        for stage in ('before','after'):q[stage]['workspace']['compatibility']['required']=0
                    elif fault=='wrong-cargo':q['after']['workspace']['compatibility']['cargo']['generation']+=1
                    else:q['before']['workspace']['nodeCount']=q['after']['workspace']['nodeCount']+1
                elif fault=='missing-query':
                    rows[24][1][:]=[e for e in rows[24][1] if e.get('data',{}).get('observation')!='throw-cargo-query']
                else:
                    events=rows[29][1]
                    if fault=='missing-return':events[:]=[e for e in events if e.get('data',{}).get('event')!='CONTROL_RETURNED']
                    else:next(e['data'] for e in events if e.get('data',{}).get('event')=='LOGICAL_COMMIT')['valueA']+=1
                with self.assertRaises(ValueError):
                    for sample,events,geo in rows:m._route_sample(sample,events,geo)

    def test_alert_clock_pending_work_and_native_walk(self):
        m,rows=alert_fixture()
        for s,e,a in rows:m._route_sample(s,e,a)
        self.assertEqual(m.route_witness['endFrame'],120)
        self.assertEqual(m.route_witness['searchStartFrame'],121)
        wild_witness(m.route_witness,dict(handle=rows[-1][2]['handle']))

    def test_copied_owner_key_graph_clock_and_spacing_faults_reject(self):
        faults={'stale-owner':'owner, clock','wrong-image':'sealed image','reset-policy':'route policy changed',
            'missing-resume':'did not resume','changed-alert':'authored Cargo alert clock',
            'late-admission':'admit a native Walk'}
        for fault,reason in faults.items():
            with self.subTest(fault=fault):
                m,rows=alert_fixture()
                if fault in ('stale-owner','wrong-image','reset-policy'):
                    q=rows[21][1][0]['data']
                    if fault=='stale-owner':q['subject']['generation']+=1
                    if fault=='wrong-image':q['imageIdentity']['elfSha256']='f'*64
                    if fault=='reset-policy':q['after']['workspace']['compatibility']['movementPolicyRevision']+=1
                elif fault=='missing-resume':rows[21][1].clear();rows[22][1].clear()
                elif fault=='changed-alert':rows[2][0]['pokemonCombat']['movementTimers'][0]['movementEmoteTimer']-=1
                else:
                    rows[22][2]['motionKind']='NONE';rows[23][2].update(motionKind='WALK',motionPhase='MOVING',motionElapsed=0,motionDuration=8)
                    rows[23][1][-1]['data'].update(event='MOTION_STARTED',valueA=1,valueB=8,actorFrame=122,
                        actorHandle=rows[23][2]['handle']['value'],actor={k:v for k,v in rows[23][2]['handle'].items() if k!='value'})
                    # Reachable route at121, more than one frame before admission.
                    rows[23][0]['frame']=124;rows[23][0]['actorFrame']=124;rows[23][0]['nativeCycle']=1124
                    rows[23][1][:]=[rows[23][1][-1]];rows[23][1][-1]['frame']=124;rows[23][1][-1]['data']['actorFrame']=124;rows[23][1][-1]['kind']='native';rows[23][1][-1]['data'].pop('observation',None)
                with self.assertRaisesRegex(ValueError,reason):
                    for s,e,a in rows:m._route_sample(s,e,a)

    def test_wild_ranking_graph_restart_is_allowed(self):
        # TKT-0051 nearest ranking restarts the graph on each target check;
        # the old TKT-0041 no-reset rule no longer applies to Wild routes.
        m,rows=alert_fixture()
        rows[21][1][0]['data']['after']['workspace']['nodeCount']=1
        for s,e,a in rows:m._route_sample(s,e,a)
        wild_witness(m.route_witness,dict(handle=rows[-1][2]['handle']))

    def test_first_follower_receipt_can_grow_graph_before_same_tick_hop(self):
        from tools.overworld.test_devtools_follower_throw_measurement import stream,evaluate
        result=evaluate(stream());self.assertTrue(result['passed'],result)
        witness=deepcopy(result['measurements']['follower-throw-moving-cargo-v1']['routeContinuity'])
        witness['observations'][0]['before']['nodeCount']=1
        witness['observations'][0]['workspace']['nodeCount']=2
        follower_witness(witness,result['measurements']['follower-throw-moving-cargo-v1']['speedWitnesses']['cargo'])

    def test_first_and_later_follower_receipts_still_reject_graph_or_context_loss(self):
        from tools.overworld.test_devtools_follower_throw_measurement import stream,evaluate
        result=evaluate(stream());self.assertTrue(result['passed'],result)
        for fault,reason in (('first-reset','route graph reset'),('later-entry-reset','route graph reset'),
                            ('later-return-reset','route graph reset'),('later-intra-call-reset','route graph reset'),
                            ('first-owner','route workspace owner changed'),('first-policy','route policy changed'),
                            ('first-cargo','route static context')):
            with self.subTest(fault=fault):
                witness=deepcopy(result['measurements']['follower-throw-moving-cargo-v1']['routeContinuity']);rows=witness['observations']
                rows[0]['before']['nodeCount']=1;rows[0]['workspace']['nodeCount']=2
                if fault=='first-reset':rows[0]['before']['nodeCount']=3
                elif fault=='later-entry-reset':rows[1]['before']['nodeCount']=1
                elif fault=='later-return-reset':rows[1]['workspace']['nodeCount']=1
                elif fault=='later-intra-call-reset':rows[1]['before']['nodeCount']=rows[1]['workspace']['nodeCount']+1
                elif fault=='first-owner':rows[0]['workspace']['owner']['generation']+=1
                elif fault=='first-policy':rows[0]['workspace']['compatibility']['movementPolicyRevision']+=1
                else:rows[0]['workspace']['compatibility']['cargo']['generation']+=1
                with self.assertRaisesRegex(ValueError,reason):
                    follower_witness(witness,result['measurements']['follower-throw-moving-cargo-v1']['speedWitnesses']['cargo'])

    def test_complete_follower_hop_return_key_faults(self):
        from tools.overworld.test_devtools_follower_throw_measurement import stream,evaluate
        baseline=evaluate(stream());self.assertTrue(baseline['passed'],baseline)
        for fault,reason in (('key','route policy changed'),('graph','route graph reset'),('return','current route read')):
            with self.subTest(fault=fault):
                rows=stream();events=rows[0]['events'];q=next(e for e in events if e['frame']==11 and e.get('data',{}).get('observation')=='throw-cargo-query')
                if fault=='key':q['data']['after']['workspace']['compatibility']['movementPolicyRevision']+=1
                if fault=='graph':q['data']['after']['workspace']['nodeCount']=1
                if fault=='return':rows[0]['events']=[e for e in events if not(e['frame']==18 and e.get('data',{}).get('observation')=='throw-cargo-query')]
                result=evaluate(rows);self.assertFalse(result['passed'],result)
                self.assertTrue(any(reason in f for f in result['failures']),result)

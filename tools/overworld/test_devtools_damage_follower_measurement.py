"""Small copied native-shape guards; these fixtures are not game acceptance."""
from copy import deepcopy
import json,struct,unittest
from pathlib import Path
from tools.overworld.devtools_damage_follower_measurement import (
    ACTIONS,CASE,CARGO_CONDITION,DAMAGE_CONDITION,KIND,SETUP,THROW_APP,FOLLOWER,FIND_CARGO,FIND_POSITION,RELEASE,AWAY,SEARCH_TIME,
    DamageFollowerMeasurement,validate_recipe,
)
from tools.overworld.devtools_damage_follower_proof import (
    FAULTS,DamageFollowerNegative,validate_negative_result,measurements,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.test_devtools_follower_throw_measurement import snapshot as shared_snapshot,SOURCE,binding as shared_binding
from tools.overworld.test_devtools_player_health_throw_contact_measurement import health
ROOT=Path(__file__).resolve().parents[2]


def sample(frame=20):
    s=shared_snapshot(9);s.update(frame=frame,actorFrame=frame,nativeCycle=frame+1000)
    m,src=s['actors'][:2];src['species']=70
    s['actors']=[m,src]
    for a in s['actors']:a['engineObject'].update(pos_y=65536,unk88_y=0)
    s['party'][0].update(slot=0,isEgg=False,form=m.get('form',0),level=m['level'],status=0,moves=[1],pp=[8],checksum=1)
    s['partyObservation']=dict(frame=frame,boundary=s['observationBoundary'],nativeGetterChecks=[
        dict(slot=0,field=k,native=s['party'][0][k],decoded=s['party'][0][k],passed=True,
            personality=m['subjectIdentity'],nativeCycle=frame+1000,frame=frame,boundary='natural-GetMonData-return')
        for k in ('hp','maxHp','species','level')])
    s['pokemonCombat'].update(frame=frame,nativeCycle=frame+1000,observationBoundary=s['observationBoundary'])
    target=next(r for r in s['pokemonCombat']['targets'] if r['handle']==m['handle'])
    target.update(personality=m['subjectIdentity'],species=56,form=m.get('form',0),level=m['level'],
        mapId=s['context']['mapId'],mapGeneration=m['handle']['mapGeneration'],encounterGeneration=m['handle']['encounterGeneration'],
        initialized=1,hpSource='party',hpMirrorMatches=True,hp=s['party'][0]['hp'],currentHp=s['party'][0]['hp'],
        maxHp=s['party'][0]['maxHp'],actualMaxHp=s['party'][0]['maxHp'],hitCount=0,lastDamage=0)
    inter=s['pokemonCombat']['interactions'];inter.update(frame=frame,nativeCycle=frame+1000)
    return s


def binding(actor,condition):
    b=shared_binding(actor,condition)
    if actor:
        raw=bytearray.fromhex(b['rawHex']);raw[20]=THROW_APP;b['sourceApplication']=THROW_APP;b['rawHex']=raw.hex()
    return b


def bindings(s,trigger=True,cargo=True):
    m,src=s['actors'];r=s['pokemonCombat']['interactions']['carriers'][0]
    r['bindings']=dict(trigger=binding(src if trigger else None,DAMAGE_CONDITION),
                       cargo=binding(src if cargo else None,CARGO_CONDITION))
    r['rawBindingsHex']=(raw_handle(m['handle'])+bytes.fromhex(r['bindings']['trigger']['rawHex'])+
                         bytes.fromhex(r['bindings']['cargo']['rawHex'])).hex()
    return r


def native(a,frame,event,A,B,sequence):
    return dict(frame=frame,kind='native',data=dict(actorHandle=a['handle']['value'],
        actor={k:v for k,v in a['handle'].items() if k!='value'},frame=frame,actorFrame=frame,
        event=event,reason='OK',valueA=A,valueB=B,sequence=sequence))


def motion(s,a,*,phase='MOVING',elapsed=0,commit=4,origin=(586,408),target=(586,416),reservation=21,kind=2):
    raw=bytearray(52);struct.pack_into('<HBBHH',raw,0,1,kind,1,a['handle']['fieldEpoch'],0)
    struct.pack_into('<4h2i',raw,8,*origin,*target,65536,65536)
    struct.pack_into('<HH',raw,24,8,reservation);raw[28]=1;raw[29]=8;raw[34]=2
    phaseid={'IDLE':0,'MOVING':2,'SETTLING':4}[phase]
    struct.pack_into('<4H4B',raw,40,elapsed,2 if phase=='SETTLING' else 0,0,0,phaseid,0,int(commit==5),0)
    value=decode_motion(bytes(raw))
    a.update(motionPhase=phase,motionKind={1:'WALK',2:'HOP'}[kind],motionElapsed=elapsed,motionDuration=8,
        reservationId=reservation if phase=='MOVING' else 0,commitSequence=commit,
        origin=dict(zip(('x','y'),origin)),target=dict(zip(('x','y'),target)),
        logical=dict(zip(('x','y'),target if commit==5 else origin)))
    a['engineObject'].update(pos_x=(a['logical']['x']<<16)+32768,pos_z=(a['logical']['y']<<16)+32768)
    rows=s['pokemonCombat']['targets'];rows[:]=[r for r in rows if r['handle']!=a['handle']]
    rows.append(dict(handle=deepcopy(a['handle']),role=a['role'],motion=value))
    return value


def meter(s=None):
    s=s or sample();m=DamageFollowerMeasurement(SOURCE)
    m.latest=deepcopy(s);m.context=deepcopy(s['context']);m.field=s['fieldControl']['fieldPointer']
    m.subjects={n:select_current_actor(s,a) for n,a in zip(('mankey','source'),s['actors'])}
    m.hit=dict(frame=s['frame'],source=deepcopy(s['actors'][1]['handle']))
    m.hp_before=health(s,100,0,0);m.hp_before['identity'].update(romSha256=SOURCE['romSha256'],overlaySha256=SOURCE['overlaySha256'])
    m.hp_after=dict(hp=80,acceptedHits=1,lastDamage=20)
    m.busy_return=dict(returnFrame=s['frame']+1)
    return m


def hp_row(s):
    h=health(s,80,20,1);h['identity'].update(romSha256=SOURCE['romSha256'],overlaySha256=SOURCE['overlaySha256'])
    return dict(phase='observe',action='accepted-hit',command='player-health.observe',snapshot=deepcopy(s),receipt=dict(playerHealth=h))


def rejected(error,fault):
    r=dict(passed=False,failures=[str(error)],measurements={KIND:dict(failures=[str(error)])})
    validate_negative_result(r,fault)


class DamageFollowerTests(unittest.TestCase):
    def test_current_authored_condition_and_exact_recipe(self):
        r=json.loads((ROOT/'tests/overworld/test-recipes'/f'{CASE}.json').read_text());validate_recipe(r)
        self.assertEqual((DAMAGE_CONDITION,CARGO_CONDITION,THROW_APP),(65099,26783,19))
        for fault in ('Sight','forced-event','longer','wrong-input','south-start','extra-settle','late-left-release','held-settle','missing-follower-settle'):
            bad=deepcopy(r)
            if fault=='Sight':bad['subjects'][1]['species']=69
            elif fault=='forced-event':bad['setup'].append(dict(id='fake',op='step',args=dict(frames=1,keys=[])))
            elif fault=='longer':bad['actions'][3]['args']['frames']+=1
            elif fault=='south-start':bad['setup'][0]['args']['facing']=0
            elif fault=='extra-settle':bad['setup'].insert(3,dict(id='settle-follower',op='step',args=dict(frames=16,keys=[])))
            elif fault=='late-left-release':bad['setup'][4]['args']['until']=dict(kind='player-settled-at',map=33,x=585,z=407,when='final')
            elif fault=='held-settle':bad['setup'][5]['args']['keys']=['LEFT']
            elif fault=='missing-follower-settle':bad['setup'].pop(6)
            else:bad['actions'][1]['args']['keys']=['UP']
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'normal input'):validate_recipe(bad)

    def test_native_follower_bind_keeps_the_north_running_path_clear(self):
        s=sample();a=s['actors'][0]
        s['player'].update(x=586,y=407,facing=1)
        a['logical']=dict(x=586,y=408)
        a['engineObject'].update(x=586,y=408,pos_x=(586<<16)+32768,pos_z=(408<<16)+32768)
        def bound(current):
            m=DamageFollowerMeasurement(SOURCE)
            m.setup_index=next(i for i,(name,_,_) in enumerate(SETUP) if name=='bind-mankey')
            a=current['actors'][0]
            row=dict(phase='setup',action='bind-mankey',command='bind',snapshot=current,
                receipt=select_current_actor(current,a))
            return m.observe_record(row)
        self.assertEqual(bound(deepcopy(s))['failures'],[])
        for fault in ('south-start','front-follower','still-moving'):
            bad=deepcopy(s);a=bad['actors'][0]
            if fault=='south-start':bad['player']['facing']=0
            elif fault=='front-follower':
                a['logical']['y']=406;a['engineObject'].update(y=406,pos_z=(406<<16)+32768)
            else:a.update(motionPhase='MOVING',reservationId=21)
            result=bound(bad)
            with self.subTest(fault=fault):
                self.assertTrue(result['failures'])
                self.assertTrue(any(('did not settle' if fault=='still-moving' else 'blocks the north running path') in e for e in result['failures']))

    def lane_sample(self,frame,*,center=True,follower_phase='IDLE'):
        from tools.overworld.test_devtools_movement_predicates import MovementPredicateTests
        from tools.overworld.test_devtools_player_health_throw_contact_measurement import step_row
        current=sample(frame);native=MovementPredicateTests().follower()
        a=native['actors'][0];a.update(species=56,level=20)
        a['sourceIdentity'].update(species=56,level=20)
        a.update(logical=dict(x=586,y=407),origin=dict(x=586,y=408),target=dict(x=586,y=407),
            motionPhase=follower_phase,motionKind='NONE' if follower_phase=='IDLE' else 'HOP',
            reservationId=0 if follower_phase=='IDLE' else 21)
        a['engineObject'].update(x=586,y=407,pos_x=(586<<16)+32768,pos_z=(407<<16)+32768)
        current.update(context=native['context'],actors=[a],selector=native['selector'],party=native['party'],
            partyObservation=dict(frame=frame,boundary=current['observationBoundary']))
        current['party'][0].update(species=56,level=20)
        current['player']=dict(native['player'],x=585,y=407,x_prev=586,y_prev=407,
            pos_x=(585<<16)+32768+(0 if center else 49152),pos_z=(407<<16)+32768,
            movement_cmd=90,facing=2,flags=0x31 if center else 0x11)
        return current

    def test_left_releases_at_admission_then_neutral_settles_both_owners(self):
        from tools.overworld.test_devtools_player_health_throw_contact_measurement import step_row
        start=self.lane_sample(20);start['player'].update(x=586,pos_x=(586<<16)+32768)
        m=DamageFollowerMeasurement(SOURCE);m.latest=start;m.setup_index=4
        m.subjects['mankey']=select_current_actor(start,start['actors'][0])
        def advance(name,current):
            row=step_row(name,[current]);row['phase']='setup';return m.observe_record(row)
        admission=self.lane_sample(21,center=False,follower_phase='MOVING')
        self.assertEqual(advance('step-left-to-lane',admission)['failures'],[])
        self.assertEqual(m.setup_index,5)  # Release while Player and Follower still move.
        self.assertEqual(advance('settle-player-at-lane',self.lane_sample(22,center=False,follower_phase='MOVING'))['failures'],[])
        self.assertEqual(m.setup_index,5)
        self.assertEqual(advance('settle-player-at-lane',self.lane_sample(23,follower_phase='MOVING'))['failures'],[])
        self.assertEqual(m.setup_index,6)
        self.assertEqual(advance('settle-follower-at-lane',self.lane_sample(24,follower_phase='SETTLING'))['failures'],[])
        self.assertEqual(m.setup_index,6)
        self.assertEqual(advance('settle-follower-at-lane',self.lane_sample(25))['failures'],[])
        self.assertEqual(m.setup_index,7)
        self.assertEqual(m.setup_action_frames[4:7],[1,2,2])
        self.assertEqual(m.observed_frames,0)

    def test_lane_settle_keeps_bounds_pose_current_identity_and_source_order(self):
        from tools.overworld.test_devtools_player_health_throw_contact_measurement import step_row
        for fault in ('stale-party','wrong-follower','Player-moving','bound','early-source'):
            with self.subTest(fault=fault):
                start=self.lane_sample(20);m=DamageFollowerMeasurement(SOURCE);m.latest=start;m.setup_index=6
                m.subjects['mankey']=select_current_actor(start,start['actors'][0]);current=self.lane_sample(21)
                if fault=='stale-party':current['partyObservation']['frame']-=1
                elif fault=='wrong-follower':current['actors'][0]['subjectIdentity']+=1
                elif fault=='Player-moving':current['player']['pos_x']+=1
                elif fault=='bound':m.setup_action_frames[6]=16
                else:
                    m.setup_index=7;m.latest['actors'][0].update(motionPhase='SETTLING',motionKind='HOP')
                if fault=='early-source':
                    row=dict(phase='setup',action='spawn-source',command='spawn',snapshot=current,receipt={})
                else:
                    row=step_row('settle-follower-at-lane',[current]);row['phase']='setup'
                result=m.observe_record(row)
                self.assertTrue(result['failures'])
                self.assertEqual(m.observed_frames,0)

    def test_living_same_party_owner_accepts_only_current_native_hit_damage(self):
        before=sample(20);m=DamageFollowerMeasurement(SOURCE);m.latest=deepcopy(before)
        m._party_health(before,before['actors'][0],initial=True)
        after=sample(21);after['party'][0]['hp']-=20
        target=next(t for t in after['pokemonCombat']['targets'] if t['handle']==after['actors'][0]['handle'])
        target.update(hp=26,currentHp=26,hitCount=1,lastDamage=20)
        check=next(r for r in after['partyObservation']['nativeGetterChecks'] if r['field']=='hp')
        check.update(native=26,decoded=26)
        m._party_health(after,after['actors'][0]);self.assertEqual((m.party_hp,m.party_hits),(26,1))
        for fault in ('fainted','owner','status','moves','maxHp','stale-party','stale-combat','wrong-native',
                      'stale-native','mirror','wrong-source','wrong-hit','wrong-damage','no-HP-drop'):
            with self.subTest(fault=fault):
                bad=deepcopy(after);a=bad['actors'][0];mon=bad['party'][0]
                hp=next(t for t in bad['pokemonCombat']['targets'] if t['handle']==a['handle'])
                check=next(r for r in bad['partyObservation']['nativeGetterChecks'] if r['field']=='hp')
                if fault=='fainted':mon['hp']=0
                elif fault=='owner':mon['personality']+=1
                elif fault=='status':mon['status']=8
                elif fault=='moves':mon['moves'][0]+=1
                elif fault=='maxHp':mon['maxHp']+=1
                elif fault=='stale-party':bad['partyObservation']['frame']-=1
                elif fault=='stale-combat':bad['pokemonCombat']['frame']-=1
                elif fault=='wrong-native':check['native']+=1
                elif fault=='stale-native':check['nativeCycle']=before['nativeCycle']
                elif fault=='mirror':hp['hpMirrorMatches']=False
                elif fault=='wrong-source':hp['hpSource']='wild-resident'
                elif fault=='wrong-hit':hp['hitCount']=0
                elif fault=='wrong-damage':hp['lastDamage']=19
                else:
                    mon['hp']=46;hp.update(hp=46,currentHp=46);check.update(native=46,decoded=46)
                fresh=DamageFollowerMeasurement(SOURCE);fresh.latest=deepcopy(before)
                fresh._party_health(before,before['actors'][0],initial=True)
                with self.assertRaises(ValueError):fresh._party_health(bad,a)

    def test_only_actual_current_position_profile_earns_away_before_windup(self):
        s=sample(20);a=s['actors'][0];m=meter(s)
        flags=dict(carried=True,windup=False)
        # Newly carried may still show the prior Cargo profile; no Away credit.
        a.update(matchedLayerMask=1<<THROW_APP,behaviorFingerprint=7)
        m._held_profile(s,a,flags);self.assertIsNone(m.position_profile);self.assertIsNone(m.windup)
        mask=FIND_POSITION|AWAY;raw=bytearray(216);raw[13]=14;raw[7]=raw[36]=SEARCH_TIME;raw[76]=8;raw[77]=20
        struct.pack_into('<II',raw,188,mask,8)
        profile=dict(fingerprint=8,appliedOverrides=mask,resultHex=raw.hex())
        a.update(matchedLayerMask=mask,behaviorFingerprint=8);m.profiles[8]=profile
        m._held_profile(s,a,flags);self.assertEqual(m.frames['position'],20)
        for fault in ('missing-Away','wrong-aim','stale-profile','skipped-position','lost-Away'):
            with self.subTest(fault=fault):
                current=deepcopy(s);actor=current['actors'][0];fresh=meter(current);fresh.profiles[8]=deepcopy(profile)
                if fault=='missing-Away':actor['matchedLayerMask']&=~AWAY
                elif fault=='wrong-aim':
                    changed=bytearray(raw);changed[13]=13;fresh.profiles[8]['resultHex']=changed.hex()
                elif fault=='stale-profile':fresh.profiles[8]['appliedOverrides']^=1
                elif fault=='skipped-position':
                    actor['matchedLayerMask']=RELEASE|AWAY;fresh.profiles[8]['appliedOverrides']=actor['matchedLayerMask']
                    current['pokemonCombat']['movementTimers']=[dict(handle=actor['handle'],movementCooldown=20)]
                else:fresh.position_profile=deepcopy(profile);actor['matchedLayerMask']=1<<THROW_APP
                with self.assertRaises(ValueError):fresh._held_profile(current,actor,dict(carried=True,windup=fault=='skipped-position'))
        # Actual Release must also resolve current Away; a stale Position result
        # cannot supply the new mask or the native windup timer.
        a.update(matchedLayerMask=mask|RELEASE,behaviorFingerprint=9)
        released=bytearray(raw);struct.pack_into('<II',released,188,mask|RELEASE,9)
        m.profiles[9]=dict(fingerprint=9,appliedOverrides=mask|RELEASE,resultHex=released.hex())
        s['pokemonCombat']['movementTimers']=[dict(handle=a['handle'],movementCooldown=20)]
        m._held_profile(s,a,dict(carried=True,windup=True));self.assertEqual(m.windup['timer'],20)
        for offset in range(1,21):
            current=deepcopy(s);current['frame']=20+offset
            current['pokemonCombat']['movementTimers'][0]['movementCooldown']=20-offset
            m._held_profile(current,current['actors'][0],dict(carried=True,windup=True))
        self.assertEqual(m.windup['zeroFrame'],40)
        for fault in ('skipped-tick','extra-wait','missing-timer'):
            current=deepcopy(s);current['frame']=21
            current['pokemonCombat']['movementTimers'][0]['movementCooldown']=18 if fault=='skipped-tick' else 20
            if fault=='missing-timer':current['pokemonCombat']['movementTimers']=[]
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                m._held_profile(current,current['actors'][0],dict(carried=True,windup=True))

    def test_only_current_accepted_health_drop_earns_damage(self):
        s=sample();m=meter(s);row=hp_row(s)
        self.assertEqual(m._health(row,True)['hp'],80)
        for name in ('contact-only','stale-health'):
            fault=f'{KIND}:{name}';control=DamageFollowerNegative(fault);bad=control.mutate(row,m.subjects)
            self.assertTrue(control.applied)
            with self.subTest(fault=name),self.assertRaises(ValueError) as failure:m._health(bad,True)
            rejected(failure.exception,fault)
        for name in ('protected','duplicate','wrong-ROM','wrong-cycle','unsaved'):
            bad=deepcopy(row);h=bad['receipt']['playerHealth']
            if name=='protected':h.update(hp=100,savedHp=100,lastDamage=0,acceptedHits=0)
            elif name=='duplicate':h['acceptedHits']=0
            elif name=='wrong-ROM':h['identity']['romSha256']='f'*64
            elif name=='wrong-cycle':h['nativeCycle']+=1
            else:h['savedHp']+=1
            with self.subTest(fault=name),self.assertRaises(ValueError):m._health(bad,True)

    def test_damage_contact_stops_before_delayed_knockback_for_the_strict_hp_read(self):
        previous=sample(20);current=sample(21)
        before=previous['actors'][1];source=current['actors'][1]
        source.update(motionKind='HOP',motionPhase='MOVING',motionElapsed=4,motionDuration=6)
        # Native retained contact shape: the Player is still in a blocked step,
        # while the source crosses its body and the damage binding is published.
        current['player'].update(pos_x=38371328,pos_y=65536,pos_z=26312704,
            face_x=0,face_y=0,face_z=2048,movement_cmd=28)
        before['engineObject'].update(pos_x=38371328,pos_y=65536,pos_z=26279936)
        source['engineObject'].update(pos_x=38371328,pos_y=65536,pos_z=26290858)
        carrier=bindings(current,cargo=False)
        m=meter(previous);m.hit=None;m.hp_after=None
        self.assertTrue(m._damage_contact(current,source,carrier))
        self.assertIsNone(m.hit)
        self.assertIsNone(m.binding)
        self.assertFalse(m.stage('physical-hit'))
        for fault in ('Sight','wrong-source','stale','flags','application','lifetime','far',
                      'idle','start','end','repeated-hit'):
            bad=deepcopy(current);src=bad['actors'][1]
            c=bad['pokemonCombat']['interactions']['carriers'][0];b=c['bindings']['trigger']
            fresh=meter(previous);fresh.hit=None
            if fault=='Sight':b['sourceConditionId']=12365
            elif fault=='wrong-source':b['target']['actor']['generation']+=1
            elif fault=='stale':b['targetCurrent']=False
            elif fault=='flags':b['flags']=3
            elif fault=='application':b['sourceApplication']+=1
            elif fault=='lifetime':b['lifetime']=1
            elif fault=='far':
                src['engineObject']['pos_x']+=65536
                fresh.latest['actors'][1]['engineObject']['pos_x']+=65536
            elif fault=='idle':src['motionPhase']='IDLE'
            elif fault=='start':src['motionElapsed']=0
            elif fault=='end':src['motionElapsed']=src['motionDuration']
            else:fresh.hit=dict(frame=20)
            with self.subTest(fault=fault):self.assertFalse(fresh._damage_contact(bad,src,c))

    def test_delayed_player_damage_binding_keeps_the_same_accepted_hop(self):
        current=sample(22);source=current['actors'][1]
        hop=motion(current,source,phase='IDLE',elapsed=8,commit=5,
            origin=(585,400),target=(585,401),reservation=10)
        carrier=bindings(current,cargo=False)
        base=meter(sample(20));base.hit=None
        base.contact=dict(frame=20,source=deepcopy(source['handle']),
            plan=deepcopy(hop['plan']),commitBefore=4)
        base.contact_returned=True
        self.assertTrue(base._delayed_damage_binding(current,source,hop,carrier))
        for fault in ('Sight','wrong-source','changed-plan','late','no-return'):
            bad=deepcopy(current);actor=bad['actors'][1]
            current_carrier=bad['pokemonCombat']['interactions']['carriers'][0]
            current_hop=deepcopy(hop);fresh=DamageFollowerMeasurement(SOURCE)
            fresh.contact=deepcopy(base.contact);fresh.contact_returned=True
            if fault=='Sight':
                current_carrier['bindings']['trigger']['sourceConditionId']=12365
            elif fault=='wrong-source':
                actor['handle']['generation']+=1
            elif fault=='changed-plan':
                current_hop['plan']['target'][1]+=1
            elif fault=='late':
                bad['frame']+=1
            else:
                fresh.contact_returned=False
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,
                    'accepted physical damage source|accepted physical source'):
                fresh._delayed_damage_binding(bad,actor,current_hop,current_carrier)

    def test_interest_and_cargo_are_the_same_damage_source_during_busy_move(self):
        s=sample();m=meter(s);r=bindings(s)
        m.busy_return=None
        m._carrier(s,s['actors'][0]);m._binding(s,r,s['actors'][1]);self.assertEqual(m.binding['binding']['target']['actor'],s['actors'][1]['handle'])
        for name in ('sight-trigger','wrong-cargo'):
            fault=f'{KIND}:{name}';control=DamageFollowerNegative(fault)
            bad=control.mutate(dict(phase='observe',action='natural-damage-throw',samples=[s],events=[]),m.subjects)
            fresh=meter(bad['samples'][0]);carrier,_=fresh._carrier(bad['samples'][0],bad['samples'][0]['actors'][0])
            self.assertTrue(control.applied)
            with self.subTest(fault=name),self.assertRaises(ValueError) as failure:fresh._binding(bad['samples'][0],carrier,bad['samples'][0]['actors'][1])
            rejected(failure.exception,fault)
        for name in ('no-damage','unconfirmed-later-frame','Player','stale','pre-hit'):
            fresh=meter(s);bad=deepcopy(r)
            if name=='no-damage':fresh.hit=None
            elif name=='unconfirmed-later-frame':fresh.hp_after=None;fresh.hit['frame']-=1
            elif name=='Player':bad['bindings']['trigger']['target']=dict(kind='PLAYER',actor=None)
            elif name=='pre-hit':fresh.hit['frame']+=1
            else:bad['bindings']['trigger']['targetCurrent']=False
            with self.subTest(fault=name),self.assertRaises(ValueError):fresh._binding(s,bad,s['actors'][1])
        # Same-frame binding waits for the existing explicit accepted-hit HP
        # receipt; it cannot earn proof by a physical contact alone.
        fresh=meter(s);fresh.hp_after=None;fresh.busy_return=None
        fresh._binding(s,r,s['actors'][1]);self.assertEqual(fresh.frames['capture'],s['frame'])
        fresh.hp_after=fresh._health(hp_row(s),True)
        self.assertEqual(fresh.hp_after['hp'],80)

    def test_sight_fault_keeps_the_real_hit_then_tests_the_exact_binding_guard(self):
        s=sample();bindings(s,cargo=False);m=meter(s)
        fault=f'{KIND}:sight-trigger';control=DamageFollowerNegative(fault)
        hit=dict(phase='observe',action='run-to-hit',samples=[s],events=[])
        self.assertEqual(control.mutate(hit,m.subjects),hit)
        self.assertFalse(control.applied)
        receipt=hp_row(s)
        self.assertEqual(control.mutate(receipt,m.subjects),receipt)
        self.assertFalse(control.applied)
        throwing=dict(phase='observe',action='natural-damage-throw',samples=[s],events=[])
        changed=control.mutate(throwing,m.subjects)
        self.assertTrue(control.applied)
        actor=changed['samples'][0]['actors'][0]
        carrier,_=m._carrier(changed['samples'][0],actor)
        bad=carrier['bindings']['trigger'];good=s['pokemonCombat']['interactions']['carriers'][0]['bindings']['trigger']
        self.assertEqual(bad['target'],good['target'])
        self.assertEqual(bad['sourceConditionId'],DAMAGE_CONDITION^1)
        with self.assertRaisesRegex(ValueError,'Interest is not the accepted physical damage source') as failure:
            m._binding(changed['samples'][0],carrier,changed['samples'][0]['actors'][1])
        rejected(failure.exception,fault)
        with self.assertRaisesRegex(ValueError,'failed at another guard'):
            rejected(ValueError('Damage Follower captured before accepted damage'),fault)

    def test_damage_capture_keeps_old_plan_until_exact_control_return(self):
        start=sample(20);a=start['actors'][0];mv=motion(start,a);m=meter(start)
        m.busy=m._start(start,a,mv,m._native(start,[native(a,20,'MOTION_STARTED',2,8,50)],a))
        m.busy_return=None;m.hit['frame']=21
        captured=sample(21);a=captured['actors'][0];mv=motion(captured,a,elapsed=1)
        a['engineObject']['pos_y']+=1000
        self.assertFalse(m._advance(captured,a,mv,[],m.busy))
        carrier=bindings(captured);m._carrier(captured,a);m._binding(captured,carrier,captured['actors'][1])
        self.assertEqual(m.frames['capture'],21)
        self.assertIsNone(m.busy['returnFrame'])
        end=sample(28);a=end['actors'][0];mv=motion(end,a,phase='IDLE',elapsed=8,commit=5)
        events=[native(a,28,'LOGICAL_COMMIT',5,2,51),native(a,28,'MOTION_FINISHED',5,2,52),
                native(a,28,'CONTROL_RETURNED',0,5,53)]
        self.assertTrue(m._advance(end,a,mv,m._native(end,events,a),m.busy))
        self.assertEqual(m.busy['returnFrame'],28)
        for fault in ('plan','missing-control'):
            fresh=meter(start);w=fresh._start(start,start['actors'][0],motion(start,start['actors'][0]),
                fresh._native(start,[native(start['actors'][0],20,'MOTION_STARTED',2,8,50)],start['actors'][0]))
            bad=deepcopy(captured if fault=='plan' else end);a=bad['actors'][0]
            value=bad['pokemonCombat']['targets'][-1]['motion'];events2=[] if fault=='plan' else events[:-1]
            if fault=='plan':value['plan']['target'][0]+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                fresh._advance(bad,a,value,fresh._native(bad,events2,a),w)

    def test_proof_accepts_moving_capture_but_requires_return_before_claim(self):
        s=sample(20);m=meter(s);src,mankey=s['actors'][1]['handle'],s['actors'][0]['handle']
        f=dict(hit=20,capture=20,moveReturn=28,claim=29,pickup=30,windup=31,launch=52,landed=60,followStart=61,followReturn=70)
        m.hit['physicalContact']=dict(frame=20,source=deepcopy(src),
            plan=dict(kind=2,reservationId=21))
        r=dict(passed=True,ready=True,acceptedProof=False,failures=[],observedFrames=50,
            observedFrameUnit='completed-game-frame',subjects=m.subjects,frames=f,acceptedHit=m.hit,
            busyMovement=dict(handle=mankey,frame=19,returnFrame=28),
            damageBinding=dict(binding=binding(s['actors'][1],DAMAGE_CONDITION)),
            flight=dict(handle=src,commit=dict(sequence=8),returnFrame=60,moved=True),
            normalFollow=dict(handle=mankey,returnFrame=70,moved=True),healthBefore=m.hp_before,healthAfter=m.hp_after)
        replay=dict(passed=True,failures=[],observedFrames=50,measurements={KIND:r})
        record=dict(sessionId='owned',sessionCleanup=dict(sessionId='owned',closed=True,errors=[]))
        result=measurements(replay,record)
        self.assertIn('accepted-busy-move-finishes-before-pickup',[x['name'] for x in result])
        for fault in ('wrong-contact-source','late-contact','wrong-contact-plan'):
            bad=deepcopy(replay);contact=bad['measurements'][KIND]['acceptedHit']['physicalContact']
            if fault=='wrong-contact-source':contact['source']['generation']+=1
            elif fault=='late-contact':contact['frame']-=3
            else:contact['plan']['kind']=1
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'actual hit source'):
                measurements(bad,record)
        for field,value in (('capture',19),('claim',27),('pickup',27),('moveReturn',19)):
            bad=deepcopy(replay);bad['measurements'][KIND]['frames'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'stage order'):
                measurements(bad,record)

    def test_pre_tick_lane_change_keeps_motion_clocks_strict(self):
        before=sample(20);before['actorFrame']=100;before['actors'][0]['laneId']=0
        current=sample(21);current['actorFrame']=101;current['actors'][0]['laneId']=2
        m=meter(before);a=current['actors'][0]
        event=native(a,21,'LANE_CHANGED',0,2,50)
        event['data'].update(frame=100,actorFrame=100)
        self.assertEqual(len(m._native(current,[event],a)),1)
        for fault in ('older','future','wrong-before','wrong-after','motion','missing-clock'):
            bad=deepcopy(event)
            if fault=='older':bad['data'].update(frame=99,actorFrame=99)
            elif fault=='future':bad['data'].update(frame=102,actorFrame=102)
            elif fault=='wrong-before':bad['data']['valueA']=1
            elif fault=='wrong-after':bad['data']['valueB']=1
            elif fault=='motion':bad['data']['event']='MOTION_STARTED'
            else:bad['data'].pop('actorFrame')
            with self.subTest(fault=fault),self.assertRaises(ValueError):m._native(current,[bad],a)

    def test_same_queue_commit_finish_control_precedes_new_walk(self):
        start=sample(20);a=start['actors'][1];m=meter(start)
        old=motion(start,a,origin=(583,409),target=(582,409),kind=1)
        w=m._start(start,a,old,m._native(start,[native(a,20,'MOTION_STARTED',1,8,50)],a))
        end=sample(28);a=end['actors'][1]
        current=motion(end,a,commit=5,origin=(582,409),target=(583,409),reservation=22,kind=1)
        a['logical']=dict(x=582,y=409);a['engineObject']['pos_x']=(582<<16)+32768
        events=[native(a,28,'LOGICAL_COMMIT',5,1,51),native(a,28,'MOTION_FINISHED',5,1,52),
                native(a,28,'CONTROL_RETURNED',0,5,53),native(a,28,'MOTION_STARTED',1,8,54)]
        done=deepcopy(w)
        self.assertTrue(m._advance(end,a,current,m._native(end,events,a),done))
        self.assertEqual((done['commit']['sequence'],done['returnSequence']),(51,53))
        for fault in ('missing-commit','missing-control','wrong-order','wrong-old-target','wrong-height','wrong-owner','late-successor'):
            bad=deepcopy(end);a=bad['actors'][1];es=deepcopy(events)
            mv=bad['pokemonCombat']['targets'][-1]['motion']
            if fault=='missing-commit':es.pop(0)
            elif fault=='missing-control':es.pop(2)
            elif fault=='wrong-order':es[3]['data']['sequence']=52
            elif fault=='wrong-old-target':a['logical']['x']+=1
            elif fault=='wrong-height':a['engineObject']['pos_y']+=1
            elif fault=='wrong-owner':a['handle']['generation']+=1
            else:a['motionElapsed']=mv['elapsed']=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                m._advance(bad,a,mv,m._native(bad,es,a),deepcopy(w))

    def test_native_commit_finish_control_and_successor_are_strict(self):
        start=sample(20);a=start['actors'][1];mo=motion(start,a);m=meter(start)
        e=[native(a,20,'MOTION_STARTED',2,8,50)]
        w=m._start(start,a,mo,m._native(start,e,a))
        commit=sample(28);a=commit['actors'][1];mo=motion(commit,a,phase='SETTLING',elapsed=8,commit=5)
        e=[native(a,28,'LOGICAL_COMMIT',5,2,51)];m._advance(commit,a,mo,m._native(commit,e,a),w)
        end=sample(30);a=end['actors'][1];mo=motion(end,a,phase='IDLE',elapsed=8,commit=5)
        ev=[native(a,30,'MOTION_FINISHED',5,2,52),native(a,30,'CONTROL_RETURNED',0,5,53)]
        self.assertTrue(m._advance(end,a,mo,m._native(end,ev,a),deepcopy(w)))
        successor=deepcopy(end);a=successor['actors'][1]
        mo2=motion(successor,a,commit=5,origin=(586,416),target=(587,416),reservation=22,kind=1)
        ev2=ev+[native(a,30,'MOTION_STARTED',1,8,54)]
        self.assertTrue(m._advance(successor,a,mo2,m._native(successor,ev2,a),deepcopy(w)))
        for fault in ('missing-commit','wrong-control','wrong-full-owner','early-start','wrong-epoch','wrong-origin','wrong-height','missing-clock'):
            bad=deepcopy(successor);a=bad['actors'][1];mv=bad['pokemonCombat']['targets'][-1]['motion'];es=deepcopy(ev2);ww=deepcopy(w)
            if fault=='missing-commit':ww['commit']=None
            elif fault=='wrong-control':es[1]['data']['valueB']=1
            elif fault=='wrong-full-owner':a['handle']['encounterGeneration']+=1
            elif fault=='early-start':es[-1]['data']['sequence']=52
            elif fault=='wrong-epoch':mv['plan']['fieldEpoch']+=1
            elif fault=='wrong-origin':mv['plan']['origin'][0]+=1
            elif fault=='wrong-height':mv['plan']['startBaseY']+=1
            else:es[0]['data'].pop('actorFrame')
            with self.subTest(fault=fault),self.assertRaises(ValueError):m._advance(bad,a,mv,m._native(bad,es,a),ww)
        # Each named missing-control fault removes the actual full-owner return.
        for name,owner,action in (('missing-move-return','mankey','natural-damage-throw'),('missing-flight-control','source','natural-damage-throw'),('missing-follow-control','mankey','normal-follow-return')):
            x=deepcopy(end);ix=0 if owner=='mankey' else 1;a=x['actors'][ix]
            mv=motion(x,a,phase='IDLE',elapsed=8,commit=5);ww=deepcopy(w);ww['handle']=deepcopy(a['handle'])
            es=[native(a,30,'MOTION_FINISHED',5,2,52),native(a,30,'CONTROL_RETURNED',0,5,53)]
            fresh=meter(x);f=f'{KIND}:{name}';control=DamageFollowerNegative(f)
            row=control.mutate(dict(phase='observe',action=action,samples=[x],events=es),fresh.subjects)
            self.assertTrue(control.applied)
            with self.subTest(fault=name),self.assertRaises(ValueError) as failure:fresh._advance(x,a,mv,fresh._native(x,row['events'],a),ww)
            rejected(failure.exception,f)

    def test_real_away_launch_rejects_toward_and_early_rewrite(self):
        s=sample(40);s['player'].update(x=586,y=407);a=s['actors'][1];mv=motion(s,a)
        m=meter(s);m.position_profile=dict(validated=True);m.windup=dict(frame=19,timer=20,zeroFrame=39,player=[586,407],carrier=[586,408]);m.frames['pickup']=18
        carrier=bindings(s,False,False);carrier['throw'].update(targetRaw=0,carrier=False,recovering=True)
        es=[native(a,40,'MOTION_STARTED',2,8,50)]
        m._launch(s,a,mv,m._native(s,es,a),carrier);self.assertEqual(m.frames['launch'],40)
        for frame,zero in ((39,38),(41,40),(40,None)):
            fresh=meter(s);fresh.position_profile=dict(validated=True);fresh.frames['pickup']=18
            fresh.windup=deepcopy(m.windup)
            if zero is None:fresh.windup.pop('zeroFrame')
            else:fresh.windup['zeroFrame']=zero
            current=deepcopy(s);current['frame']=frame
            with self.subTest(frame=frame,zero=zero),self.assertRaises(ValueError):
                fresh._launch(current,a,mv,m._native(s,es,a),carrier)
        f=f'{KIND}:toward-player';control=DamageFollowerNegative(f)
        row=control.mutate(dict(phase='observe',action='natural-damage-throw',samples=[s],events=es),m.subjects)
        bad=row['samples'][0];self.assertTrue(control.applied)
        with self.assertRaises(ValueError) as failure:m._launch(bad,bad['actors'][1],bad['pokemonCombat']['targets'][-1]['motion'],m._native(bad,row['events'],bad['actors'][1]),carrier)
        rejected(failure.exception,f)
        s2=sample(41);a=s2['actors'][1];mv=motion(s2,a,elapsed=1);bindings(s2,False,False)['throw'].update(recovering=True,carrier=False,targetRaw=0)
        f=f'{KIND}:early-flight-overwrite';control=DamageFollowerNegative(f)
        row=control.mutate(dict(phase='observe',action='natural-damage-throw',samples=[s2],events=[]),m.subjects)
        bad=row['samples'][0];self.assertTrue(control.applied)
        with self.assertRaises(ValueError) as failure:m._advance(bad,bad['actors'][1],bad['pokemonCombat']['targets'][-1]['motion'],[],m.flight)
        rejected(failure.exception,f)
        self.assertEqual(len(FAULTS),9)

    def test_normal_follow_keeps_its_plan_when_fresh_sight_applies_during_motion(self):
        def fixture():
            start=sample(20);a=start['actors'][0];a['matchedLayerMask']=FOLLOWER
            bindings(start,False,False);mv=motion(start,a)
            m=meter(start);m.flight=dict(returnFrame=19)
            m.binding=dict(frame=15,binding=binding(start['actors'][1],DAMAGE_CONDITION))
            m.follow=m._start(start,a,mv,m._native(start,[native(a,20,'MOTION_STARTED',2,8,50)],a))
            prior=sample(28);a=prior['actors'][0];a['matchedLayerMask']=FOLLOWER
            bindings(prior,False,False);mv=motion(prior,a,phase='SETTLING',elapsed=8,commit=5)
            self.assertFalse(m._advance(prior,a,mv,m._native(prior,[native(a,28,'LOGICAL_COMMIT',5,2,51)],a),m.follow))
            m.latest=deepcopy(prior)
            end=sample(30);a=end['actors'][0];a['matchedLayerMask']=FOLLOWER|FIND_CARGO
            mv=motion(end,a,phase='IDLE',elapsed=8,commit=5)
            carrier=bindings(end,False,False)
            carrier['bindings']['trigger']=binding(end['actors'][1],12365)
            carrier['rawBindingsHex']=(raw_handle(a['handle'])+
                bytes.fromhex(carrier['bindings']['trigger']['rawHex'])+
                bytes.fromhex(carrier['bindings']['cargo']['rawHex'])).hex()
            ev=[native(a,30,'MOTION_FINISHED',5,2,52),native(a,30,'CONTROL_RETURNED',0,5,53)]
            return m,end,a,mv,ev,carrier

        def finish(m,end,a,mv,ev,carrier):
            m._follow_return(end,a,mv,m._native(end,ev,a),carrier)
            # A fresh Sight binding can bypass the old damage-source check
            # only after the actual old Follow FINISH and CONTROL return.
            m._binding(end,carrier,end['actors'][1])

        m,end,a,mv,ev,carrier=fixture();old=deepcopy(m.binding)
        m._carrier(end,a)
        finish(m,end,a,mv,ev,carrier)
        self.assertEqual(m.frames['followReturn'],30)
        self.assertEqual((m.follow['returnFrame'],m.follow['returnSequence']),(30,53))
        self.assertEqual(m.binding,old)
        self.assertFalse(m.result()['passed']);self.assertFalse(m.result()['acceptedProof'])
        m.action_index=len(ACTIONS);self.assertTrue(m.result()['passed']);self.assertFalse(m.result()['acceptedProof'])
        # Both Sight Interest and its exact Cargo may bind before the old
        # accepted Follow has returned control. The same plan must finish.
        m,end,a,mv,ev,carrier=fixture()
        prior=m.latest;prior_actor=prior['actors'][0];prior_actor['matchedLayerMask']=FOLLOWER|FIND_CARGO
        previous=bindings(prior,True,True)
        previous['bindings']['trigger']=binding(prior['actors'][1],12365)
        previous['rawBindingsHex']=(raw_handle(prior_actor['handle'])+
            bytes.fromhex(previous['bindings']['trigger']['rawHex'])+
            bytes.fromhex(previous['bindings']['cargo']['rawHex'])).hex()
        carrier['bindings']['cargo']=binding(end['actors'][1],CARGO_CONDITION)
        carrier['rawBindingsHex']=(raw_handle(a['handle'])+
            bytes.fromhex(carrier['bindings']['trigger']['rawHex'])+
            bytes.fromhex(carrier['bindings']['cargo']['rawHex'])).hex()
        m._carrier(prior,prior_actor);m._carrier(end,a)
        m._binding(prior,previous,prior['actors'][1])
        self.assertIsNone(m.follow['returnFrame'])
        claimed=deepcopy(previous);claimed['throw']['carrier']=True
        with self.assertRaisesRegex(ValueError,'before control return'):
            m._binding(prior,claimed,prior['actors'][1])
        finish(m,end,a,mv,ev,carrier);self.assertEqual(m.frames['followReturn'],30)
        for fault in ('early','missing-control','missing-finish','flight-moving','wrong-condition','wrong-application',
                      'stale-target','wrong-owner','cargo','claim','prior-interest','prior-profile','new-profile'):
            m,end,a,mv,ev,carrier=fixture()
            if fault=='early':m.follow['commit']=None
            elif fault=='missing-control':ev.pop()
            elif fault=='missing-finish':ev.pop(0)
            elif fault=='flight-moving':m.flight['returnFrame']=None
            elif fault=='wrong-condition':carrier['bindings']['trigger']=binding(end['actors'][1],DAMAGE_CONDITION)
            elif fault=='wrong-application':carrier['bindings']['trigger']['sourceApplication']+=1
            elif fault=='stale-target':carrier['bindings']['trigger']['targetCurrent']=False
            elif fault=='wrong-owner':carrier['bindings']['trigger']['target']['actor']['generation']+=1
            elif fault=='cargo':
                carrier['bindings']['cargo']=binding(end['actors'][1],CARGO_CONDITION)
                carrier['bindings']['cargo']['target']['actor']['generation']+=1
            elif fault=='claim':carrier['throw']['carrier']=True
            elif fault=='prior-interest':bindings(m.latest,True,False)
            elif fault=='prior-profile':m.latest['actors'][0]['matchedLayerMask']|=FIND_CARGO
            else:a['matchedLayerMask']|=FIND_POSITION
            with self.subTest(fault=fault),self.assertRaises(ValueError):finish(m,end,a,mv,ev,carrier)
            self.assertNotIn('followReturn',m.frames)


if __name__=='__main__':unittest.main()

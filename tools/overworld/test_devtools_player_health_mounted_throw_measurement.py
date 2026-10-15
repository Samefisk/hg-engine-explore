"""Host checks for the north-facing mounted Throw clearance regression."""

from copy import deepcopy
import struct
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_mounted_throw_measurement import (
    CROSS_FRAMES, KIND, MIN_FRAMES, SETUP, TARGET_START, THROW_RELEASE_BIT, THROW_MAX_RANGE,
    TRIGGER_APPLICATION, TRIGGER_CONDITION,
    PlayerHealthMountedThrowMeasurement,
)
from tools.overworld.devtools_player_health_mounted_throw_proof import (
    FAULTS, contract, faulted_rows, measurements,
)
from tools.overworld.test_devtools_player_health_throw_contact_measurement import (
    OVERLAY, ROM, actor, health, step_row, set_flight as set_projectile_flight,
)

REPO = Path(__file__).resolve().parents[2]
RECIPE = REPO / 'tests/overworld/test-recipes/player-hp.mounted-throw.json'
SCENARIO = REPO / 'tests/overworld/scenarios/player-hp.mounted-throw.json'
SOURCE = {'contractVersion': 1, 'romSha256': ROM, 'overlaySha256': OVERLAY}
BASE_Z = 26705920


def snapshot(frame, *, map_id=33, mounted=False, weep=False, geo=False,
             weep_y=403, geo_y=404, hop=False, elapsed=0):
    actors = []
    if mounted:
        mount = actor(155, 2, 1550, 407)
        mount['role'] = 'MOUNTED'
        mount.update(inputOwnership=1, commitSequence=4)
        mount['engineIdentity']['anchorPointer'] = 0x02101000
        mount['engineObject'].update(pos_y=65536, face_x=0, face_y=0, face_z=0,
            unk88_x=0, unk88_y=0, unk88_z=0, unk94_x=0, unk94_y=0, unk94_z=0,
            facing=0, movement_cmd=255, movement_step=0, flags=1)
        actors.append(mount)
    if weep:
        target = actor(69, 0, 700, weep_y, hop=hop, elapsed=elapsed)
        if hop:
            # Flight from Z401.5 to Z407.5. It enters the old anchor box at
            # Z407.0, but remains below the rider box until harmless landing.
            target['engineObject'] = {
                'pos_z': int((401.5 + 6 * elapsed / 24) * 65536),
                'unk88_y': 10000,
            }
        actors.append(target)
    if geo:
        source = actor(74, 1, 740, geo_y)
        if hop:
            source['matchedLayerMask'] = THROW_RELEASE_BIT
        actors.append(source)
    result = {'frame': frame, 'actorFrame': frame + 9000, 'nativeCycle': frame + 1000,
            'observationBoundary': 'main-task-queue-completion',
            'fieldAvailable': True, 'romSha256': ROM,
            'context': {'mapId': map_id, 'fieldEpoch': 1, 'mapGeneration': 1},
            'fieldControl': {'taskPointer': 0, 'fieldPointer': 0x02210000},
            'player': {'x': 585, 'y': 407, 'facing': 0,
                       'pos_x': 38371328, 'pos_z': BASE_Z,
                       'pos_y': 65536, 'face_x': 0, 'face_y': 32768, 'face_z': 32768,
                       'unk88_x': 0, 'unk88_y': 0, 'unk88_z': 0,
                       'unk94_x': 0, 'unk94_y': 0, 'unk94_z': 0,
                       'flags': 1, 'x_prev': 585, 'y_prev': 407,
                       'movement_cmd': 0, 'movement_step': 1},
            'actors': actors}
    if mounted:
        native_mount(result, hit=False)
    return result



def native_mount(snap, *, hit, elapsed=None):
    """Native3505 r3 contact shape:14HP hit, one forced8-frame slide, one commit."""
    from tools.overworld.devtools_mount_gait import POSE_KEYS, STATE_ADDRESS, expected_pose
    mount = next(a for a in snap['actors'] if a['role'] == 'MOUNTED')
    player = snap['player'];body = mount['engineObject']
    # The copied stream may be replanned at a different native flight duration.
    player.update(y=407,pos_z=BASE_Z,x_prev=585,y_prev=407,flags=1,
                  movement_cmd=0,movement_step=1)
    body.update(y=407,pos_z=BASE_Z,movement_cmd=255,flags=1)
    mount.update(logical=dict(x=585,y=407),render=dict(x=585,y=407),
                 origin=dict(x=585,y=407),target=dict(x=585,y=407),
                 motionKind='NONE',motionPhase='IDLE',motionElapsed=0,
                 motionDuration=0,reservationId=0,commitSequence=4)
    plan = dict(version=1, kind=2, fieldEpoch=1, origin=[585,407], target=[585,408],
        direction=1, distance=1, flags=1, arcHeightQ4=0, startBaseY=65536,
        targetBaseY=65536, pathAdvancePolicy=2, commitPolicy=1, duration=8,
        reservationId=31)
    motion = dict(plan=plan, elapsed=0, phase='IDLE', commitPublished=0, commitSequence=0)
    if elapsed is not None:
        active = elapsed <= 8
        elapsed = min(elapsed, 8)
        z = BASE_Z + 65536 * elapsed // 8
        tile_y = 408 if elapsed >= 7 else 407
        player.update(y=tile_y, pos_z=z, x_prev=585,
            y_prev=407 if active else 408, flags=0x31 if not active else 1,
            movement_cmd=62 if active else 255, movement_step=2 if elapsed>=7 else 1)
        body.update(y=tile_y,pos_z=z, movement_cmd=62 if active else 255)
        mount.update(logical=dict(x=585,y=tile_y),render=dict(x=585,y=tile_y),
            origin=dict(x=585,y=407),target=dict(x=585,y=408),
            motionKind='HOP' if active else 'NONE',
            motionPhase=('MOVING' if elapsed<8 else 'COMMIT_PENDING') if active else 'IDLE',
            motionElapsed=elapsed,motionDuration=8,reservationId=31 if active else 0,
            commitSequence=4 if active else 5)
        motion.update(elapsed=elapsed,phase=mount['motionPhase'],
                      commitPublished=0 if active else 1,commitSequence=0 if active else 1)
    hp=14 if hit else 28
    target=dict(handle=deepcopy(mount['handle']),personality=1550,role='MOUNTED',
        species=155,initialized=1,hpSource='party',hpMirrorMatches=True,
        hp=hp,currentHp=hp,maxHp=28,actualMaxHp=28,hitCount=1 if hit else 0,
        lastDamage=14 if hit else 0,motion=motion)
    snap['pokemonCombat']=dict(schemaVersion=1,available=True,frame=snap['frame'],
        nativeCycle=snap['nativeCycle'],observationBoundary='main-task-queue-completion',
        fieldSystem=0x02210000,identity=dict(descriptorVersion=1,romSha256=ROM,
        overlaySha256=OVERLAY),targets=[target])
    snap['party']=[dict(personality=1550,species=155,identityVerified=True,hp=hp,maxHp=28)]
    snap['partyObservation']=dict(frame=snap['frame'],boundary='main-task-queue-completion')
    pair=dict(playerPointer=mount['engineIdentity']['anchorPointer'],
              mountPointer=mount['engineIdentity']['pointer'],player=deepcopy(player),mount=deepcopy(body))
    previous={k:0 for k in POSE_KEYS};previous.update(x=player['pos_x'],z=player['pos_z'])
    inp=dict(x=player['pos_x'],z=player['pos_z'],stamp=snap['frame']+1000,
             session=1,owner=pair['playerPointer'],mode=0,options=90)
    pair['gait']=dict(schemaVersion=1,address=STATE_ADDRESS,previous=previous,
        pose=expected_pose(previous,inp),stamp=inp['stamp'],session=1,owner=inp['owner'],
        initialized=1,input=inp)
    snap['mountedPair']=pair


def cargo_motion(snap, plan=None):
    """Serialize the existing 52-byte receipt, without computing motion timing."""
    from tools.overworld.devtools_walk_matrix_observer import decode_motion, PHASES
    cargo = next(a for a in snap['actors'] if a['species'] == 69)
    if plan is None:
        plan = dict(version=1, kind=2, facing=1, fieldEpoch=cargo['handle']['fieldEpoch'],
            behaviorFingerprint=1, origin=[cargo['origin']['x'], cargo['origin']['y']],
            target=[cargo['target']['x'], cargo['target']['y']], startBaseY=65536,
            targetBaseY=65536, duration=cargo['motionDuration'], reservationId=9,
            direction=1, distance=cargo['target']['y']-cargo['origin']['y'], arcHeightQ4=16,
            spinSpeed=0, swayWidth=0, visibilityPolicy=0, pauseFrames=0,
            pathAdvancePolicy=1, commitPolicy=0, flags=0)
    phase=PHASES.index(cargo['motionPhase'])
    done = cargo['motionKind'] == 'NONE'
    names=('direction','distance','arcHeightQ4','spinSpeed','swayWidth','visibilityPolicy',
           'pauseFrames','pathAdvancePolicy','commitPolicy','flags')
    raw=struct.pack('<HBBHH4h2iHH10B2x4H4B',
        plan['version'],plan['kind'],plan['facing'],plan['fieldEpoch'],plan['behaviorFingerprint'],
        *plan['origin'],*plan['target'],plan['startBaseY'],plan['targetBaseY'],
        plan['duration'],plan['reservationId'],*(plan[k] for k in names),
        cargo['motionElapsed'],0,plan['distance'] if done else 0,int(done),phase,0,int(done),0)
    target=dict(handle=deepcopy(cargo['handle']), personality=cargo['subjectIdentity'],
        species=69,role='WILD',initialized=1,motion=decode_motion(raw))
    combat=snap['pokemonCombat']
    combat['targets']=[r for r in combat['targets'] if r.get('species') != 69]+[target]
    return target['motion']


def terminal_event(snap, name, sequence, value_a, value_b):
    cargo=next(a for a in snap['actors'] if a['species']==69)
    return dict(frame=snap['frame'],kind='native',data=dict(event=name,sequence=sequence,
        reason='OK',frame=snap['actorFrame'],actorFrame=snap['actorFrame'],
        actorHandle=cargo['handle']['value'],actor={k:v for k,v in cargo['handle'].items() if k!='value'},
        valueA=value_a,valueB=value_b))


def set_flight(stream, *, origin_y=401, duration=24, commit_sequence=0, successor=False):
    set_projectile_flight(stream, origin_y=origin_y, duration=duration, cargo_species=69)
    launch=next(r for r in stream if r.get('action')=='launch-natural-throw')['samples'][-1]
    hit_frame=launch['frame']+duration-1
    crossing=next(r for r in stream if r.get('action')=='cross-player')
    crossing['events']=[]
    for snap in [launch]+crossing['samples']:
        cargo=next(a for a in snap['actors'] if a['species']==69)
        cargo['engineObject']['pos_y']=65536
        cargo['commitSequence']=commit_sequence+int(snap['frame']>hit_frame)
        if snap is not launch:
            native_mount(snap,hit=snap['frame']>=hit_frame,
                         elapsed=snap['frame']-hit_frame if snap['frame']>hit_frame else None)
        cargo_motion(snap)
    terminal=crossing['samples'][duration-1]
    for name,seq,a,b in (('LOGICAL_COMMIT',141,commit_sequence+1,2),
                         ('MOTION_FINISHED',142,commit_sequence+1,2),
                         ('CONTROL_RETURNED',143,0,commit_sequence+1)):
        crossing['events'].append(terminal_event(terminal,name,seq,a,b))
    if successor:
        cargo=next(a for a in terminal['actors'] if a['species']==69)
        cargo.update(motionKind='WALK',motionPhase='MOVING',motionElapsed=0,motionDuration=15,
            origin=dict(x=585,y=407),target=dict(x=584,y=407),reservationId=10)
        plan=dict(version=1,kind=1,facing=2,fieldEpoch=cargo['handle']['fieldEpoch'],
            behaviorFingerprint=2,origin=[585,407],target=[584,407],startBaseY=65536,
            targetBaseY=65536,duration=15,reservationId=10,direction=2,distance=1,arcHeightQ4=0,
            spinSpeed=0,swayWidth=0,visibilityPolicy=0,pauseFrames=0,pathAdvancePolicy=1,commitPolicy=0,flags=0)
        cargo_motion(terminal,plan)
        crossing['events'].append(terminal_event(terminal,'MOTION_STARTED',148,1,15))
    return stream


def read(name, snap, hp=100, damage=0, hits=0):
    return {'phase': 'observe', 'action': name, 'command': 'player-health.observe',
            'snapshot': snap, 'receipt': {'playerHealth': health(snap, hp, damage, hits)}}


def player_trigger(snap):
    from tools.overworld.devtools_follower_throw_measurement import raw_handle
    geo=next(a for a in snap["actors"] if a["species"]==74)
    raw=bytes(12)+bytes([1,0])+struct.pack("<HIBBBB",TRIGGER_CONDITION,0,TRIGGER_APPLICATION,0,1,0)
    binding=dict(bound=True,flags=1,sourceConditionId=TRIGGER_CONDITION,
        sourceApplication=TRIGGER_APPLICATION,expiresAt=0,lifetime=0,reason=0,
        target=dict(kind="PLAYER",actor=None),targetCurrent=True,rawHex=raw.hex())
    row=dict(handle=deepcopy(geo["handle"]),role="WILD",available=True,
             rawBindingsHex=(raw_handle(geo["handle"])+raw+bytes(24)).hex(),bindings=dict(trigger=binding))
    combat=snap["pokemonCombat"]
    combat["interactions"]=dict(schemaVersion=1,available=True,frame=snap["frame"],
        nativeCycle=snap["nativeCycle"],observationBoundary=snap["observationBoundary"],
        fieldSystem=snap["fieldControl"]["fieldPointer"],identity=dict(romSha256=ROM),carriers=[row])
    return snap


def rows():
    initial = snapshot(10, map_id=34)
    tile = snapshot(11)
    party = snapshot(12)
    mount = snapshot(13, mounted=True)
    settled = [snapshot(frame, mounted=True) for frame in range(14, 30)]
    weep = snapshot(30, mounted=True, weep=True)
    both = snapshot(31, mounted=True, weep=True, geo=True)
    geo_only = snapshot(30, mounted=True, geo=True)
    captured = player_trigger(snapshot(31, mounted=True, geo=True))
    capture = step_row("capture-player-trigger", [captured]); capture["phase"] = "setup"
    mount_bound = select_current_actor(mount, mount['actors'][0])
    weep_bound = select_current_actor(both, both['actors'][1])
    geo_bound = select_current_actor(geo_only, geo_only['actors'][1])
    launch = [snapshot(frame, mounted=True, weep=True, geo=True,
                       weep_y=403 if frame < 37 else 401, geo_y=401,
                       hop=frame == 37)
              for frame in range(32, 38)]
    crossing = [snapshot(frame, mounted=True, weep=True, geo=True,
                         weep_y=407, geo_y=401, hop=frame - 37 < 24,
                         elapsed=frame - 37)
                for frame in range(38, 102)]
    settle = step_row('settle-mount', settled)
    settle['phase'] = 'setup'
    stream = [
        {'phase': 'setup', 'initialSnapshot': initial},
        {'phase': 'setup', 'action': 'throw-tile', 'command': 'teleport',
         'snapshot': tile, 'receipt': {}},
        {'phase': 'setup', 'action': 'prepare-cyndaquil', 'command': 'party',
         'snapshot': party, 'receipt': {}},
        {'phase': 'setup', 'action': 'mount-cyndaquil', 'command': 'spawn',
         'snapshot': mount, 'receipt': {'value': {'species': 155}}},
        settle,
        {'phase': 'setup', 'action': 'bind-cyndaquil', 'command': 'bind',
         'snapshot': settled[-1], 'receipt': mount_bound},
        {'phase': 'setup', 'action': 'spawn-geodude', 'command': 'spawn',
         'snapshot': geo_only, 'receipt': {'value': {'species': 74, 'slot': 1,
                                                 'personality': 740}}},
        {'phase': 'setup', 'action': 'bind-geodude', 'command': 'bind',
         'snapshot': geo_only, 'receipt': geo_bound},
        capture,
        {'phase': 'setup', 'action': 'spawn-bellsprout', 'command': 'spawn',
         'snapshot': both, 'receipt': {'value': {'species': 69, 'slot': 0,
                                                 'personality': 700}}},
        {'phase': 'setup', 'action': 'bind-bellsprout', 'command': 'bind',
         'snapshot': both, 'receipt': weep_bound},
        read('before-throw', both),
        step_row('launch-natural-throw', launch),
        read('at-launch', launch[-1]),
        step_row('cross-player', crossing),
        read('after-contact', crossing[-1]),
    ]
    return set_flight(stream)


def evaluate(stream):
    meter = PlayerHealthMountedThrowMeasurement(SOURCE)
    for row in stream:
        result = meter.observe_record(row)
        if result['failures']:
            break
    return meter.finish(), meter.result()


class PlayerHealthMountedThrowMeasurementTest(unittest.TestCase):
    def test_authored_fixture_and_registration(self):
        from tools.overworld.devtools_test_contract import validate_test
        recipe = validate_test(json.loads(RECIPE.read_text()))
        scenario = json.loads(SCENARIO.read_text())
        registry = json.loads((REPO / 'tools/overworld/runtime_proof_registry.json').read_text())
        registration = registry['sharedTests']['player-hp.mounted-throw']
        self.assertEqual(recipe['measurements'], [{'kind': KIND,
                          'subjects': ['cyndaquil', 'bellsprout', 'geodude']}])
        self.assertEqual(recipe['setup'][3]['args'], {'frames': 16, 'keys': []})
        self.assertEqual(recipe['setup'][8]['args']['z'], 403)
        self.assertEqual(TARGET_START, (585, 403))
        self.assertEqual(recipe['budgets']['minObservedFrames'], MIN_FRAMES)
        self.assertEqual(scenario['adapter']['minimumFrames'], MIN_FRAMES)
        self.assertEqual(registration['recipeSha256'], hashlib.sha256(RECIPE.read_bytes()).hexdigest())
        self.assertEqual(registration['measurementContract'], contract())
        catalog = json.loads((REPO / 'data/overworld_behavior_profiles.json').read_text())
        indexes = {row['id']: i for i, row in enumerate(catalog['applications'])}
        self.assertEqual(THROW_RELEASE_BIT, 1 << indexes['apply-throw-release'])
        find_position = next(p for p in catalog['profiles']
                             if p['id'] == 'throw-find-position')
        self.assertEqual(THROW_MAX_RANGE, find_position['fields']['throwMaxRange']['value'])

    def test_trigger_first_needs_current_native_player_binding(self):
        good=rows(); finished,result=evaluate(good)
        self.assertTrue(finished["passed"],result["failures"])
        for fault in ("clock","world","owner","raw-owner","target","condition","application","current"):
            wrong=deepcopy(good);row=next(r for r in wrong if r.get("action")=="capture-player-trigger")
            sample=row["samples"][0];value=sample["pokemonCombat"]["interactions"];carrier=value["carriers"][0];binding=carrier["bindings"]["trigger"]
            if fault=="clock":value["nativeCycle"]-=1
            elif fault=="world":value["fieldSystem"]+=4
            elif fault=="owner":carrier["handle"]["generation"]+=1
            elif fault=="raw-owner":carrier["rawBindingsHex"]="ff"+carrier["rawBindingsHex"][2:]
            elif fault=="target":binding["target"]["kind"]="ACTOR"
            elif fault=="condition":binding["sourceConditionId"]^=1
            elif fault=="application":binding["sourceApplication"]+=1
            else:binding["targetCurrent"]=False
            with self.subTest(fault=fault):
                done,result=evaluate(wrong);self.assertFalse(done["passed"])
                self.assertTrue(any("Trigger" in failure for failure in result["failures"]),result)

    def test_passive_cargo_is_catalog_legal_and_preserves_native_crossing(self):
        catalog = json.loads((REPO / 'data/overworld_behavior_profiles.json').read_text())
        profiles = {row['id']: row for row in catalog['profiles']}
        applications = {row['id']: row for row in catalog['applications']}
        pools = {row['id']: row for row in catalog['pools']}
        self.assertEqual(pools['throw-cargo']['mode'], 'all')
        self.assertEqual(pools['throw-cargo']['match']['species'],
                         'OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES')
        for name in ('apply-meander', 'apply-waddle'):
            self.assertIn('SPECIES_BELLSPROUT', applications[name]['target']['members'])
        self.assertIn('SPECIES_BELLSPROUT',
                      profiles['startled']['conditions'][0]['subjects']['members'])
        self.assertNotIn('SPECIES_BELLSPROUT',
                         profiles['ambush']['conditions'][0]['subjects']['members'])
        self.assertEqual(profiles['default']['fields']['attacking']['value'], 0)
        self.assertEqual(profiles['default']['fields']['collisionDamage']['value'], 0)
        for name in ('meander', 'waddle', 'startled', 'rest'):
            self.assertNotIn('attacking', profiles[name]['fields'])
            self.assertNotIn('collisionDamage', profiles[name]['fields'])
        release = profiles['throw-release']['fields']
        self.assertEqual(release['attacking']['value'], 1)
        self.assertEqual(release['minImpactSpeed']['value'], 16)
        self.assertEqual(release['collisionDamage']['value'], 20)
        self.assertEqual(release['knockbackType']['value'], 'OW_WILD_BEHAVIOR_KNOCKBACK_SLIDE')
        self.assertEqual(release['knockbackDistance']['value'], 1)
        stream = set_flight(rows(), origin_y=399, duration=25)
        finished, result = evaluate(stream)
        self.assertTrue(finished['passed'], result['failures'])
        self.assertEqual(result['flightFrames'], 24)
        self.assertEqual(result['hpAfterThrow'], 100)
        self.assertTrue(result['oldBoxCrossed'])
        self.assertTrue(result['mountSeatRestored'])
        self.assertEqual(result['mountKnockback']['duration'], 8)
        self.assertEqual(result['mountKnockback']['arcHeightQ4'], 0)
        self.assertEqual(len(next(r for r in stream if r.get('action') == 'cross-player')['samples']), CROSS_FRAMES)
        recipe = json.loads(RECIPE.read_text())
        self.assertEqual(recipe['actions'][3]['args'], {'frames': 64, 'keys': []})

    def test_nearby_cargo_requires_the_actual_finalized_tile(self):
        from tools.overworld.devtools_test_contract import validate_test
        self.assertEqual(TARGET_START, (585, 403))
        for tile in (400, 402, 404):
            with self.subTest(tile=tile):
                recipe = json.loads(RECIPE.read_text())
                next(s for s in recipe['setup'] if s['id'] == 'spawn-bellsprout')['args']['z'] = tile
                with self.assertRaisesRegex(ValueError, 'exact north rider'):
                    validate_test(recipe)
                stream = rows()
                bind = next(r for r in stream if r.get('action') == 'bind-bellsprout')
                cargo = next(a for a in bind['snapshot']['actors'] if a['species'] == 69)
                cargo['logical']['y'] = tile
                finished, result = evaluate(stream)
                self.assertFalse(finished['passed'], result)
                self.assertIn('prepared tile', ' '.join(result['failures']))

    def test_hostile_or_substituted_cargo_is_not_the_passive_fixture(self):
        from tools.overworld.devtools_test_contract import validate_test
        recipe = json.loads(RECIPE.read_text())
        for species in (70, 43):
            with self.subTest(species=species):
                bad = deepcopy(recipe)
                bad['subjects'][1]['species'] = species
                bad['setup'][5]['args']['species'] = species
                with self.assertRaisesRegex(ValueError, 'exact north rider'):
                    validate_test(bad)
        stream = rows()
        target = next(a for a in stream[-2]['samples'][0]['actors'] if a['species'] == 69)
        target['species'] = 70
        finished, result = evaluate(stream)
        self.assertFalse(finished['passed'])
        self.assertTrue(result['failures'])

    def test_current_airborne_old_box_crossing_misses_rider(self):
        stream = rows()
        finished, result = evaluate(stream)
        self.assertTrue(finished['passed'], result['failures'])
        self.assertTrue(result['oldBoxCrossed'])
        self.assertEqual((result['hpAfterThrow'], result['observedFrames']),
                         (100, 6 + CROSS_FRAMES))

    def test_native_eight_tile_launch_uses_actual_carrier_origin(self):
        # Native 3505 starts at399, eight tiles north of407, duration25.
        stream = set_flight(rows(), origin_y=399, duration=25)
        finished, result = evaluate(stream)
        self.assertTrue(finished['passed'], result['failures'])
        self.assertTrue(result['oldBoxCrossed'])
        self.assertEqual(result['hpAfterThrow'], 100)
        for fault in ('too-far', 'wrong-pose', 'wrong-owner', 'wrong-logical'):
            with self.subTest(fault=fault):
                bad = set_flight(rows(), origin_y=398 if fault == 'too-far' else 399,
                                 duration=25)
                launch = next(row for row in bad if row.get('action') == 'launch-natural-throw')
                source = next(a for a in launch['samples'][-1]['actors'] if a['species'] == 74)
                if fault == 'wrong-pose': source['engineObject']['pos_z'] += 65536
                if fault == 'wrong-owner': source['handle']['generation'] += 1
                if fault == 'wrong-logical': source['logical']['y'] += 1
                finished, result = evaluate(bad)
                self.assertFalse(finished['passed'], result)

    def test_idle_before_first_commit_cannot_end_the_flight_guard(self):
        stream = set_flight(rows(), origin_y=399, duration=25)
        target = next(a for a in stream[-2]['samples'][24]['actors'] if a['species'] == 69)
        target['commitSequence'] = 0
        finished, result = evaluate(stream)
        self.assertFalse(finished['passed'], result)
        self.assertIn('completed first flight', ' '.join(result['failures']))

    def test_real_mount_only_hit_finishes_shared_knockback_in_the_same_seat(self):
        stream=set_flight(rows(),origin_y=399,duration=25)
        finished,result=evaluate(stream)
        self.assertTrue(finished['passed'],result['failures'])
        self.assertEqual(result['mountHitFrame'],61)
        self.assertEqual(result['mountKnockback']['target'],[585,408])
        self.assertTrue(result['mountSeatRestored'])
        self.assertEqual(result['hpAfterThrow'],100)

    def test_copied_mount_knockback_needs_current_hit_owner_and_completed_seat(self):
        for fault in ('no-real-hit','stale-combat','stale-party','wrong-plan','wrong-reservation',
                      'wrong-pair-owner','wrong-seat-height','unfinished-commit','residual-height'):
            with self.subTest(fault=fault):
                stream=set_flight(rows(),origin_y=399,duration=25)
                crossing=next(r for r in stream if r.get('action')=='cross-player')
                moving=crossing['samples'][24] # First forced frame62, after the mount hit61.
                terminal=crossing['samples'][33]
                mount=next(a for a in moving['actors'] if a['role']=='MOUNTED')
                hp=moving['pokemonCombat']['targets'][0]
                if fault=='no-real-hit':
                    contact=crossing['samples'][23]
                    contact['pokemonCombat']['targets'][0].update(hp=28,currentHp=28,hitCount=0,lastDamage=0)
                    contact['party'][0]['hp']=28
                elif fault=='stale-combat': moving['pokemonCombat']['frame']-=1
                elif fault=='stale-party': moving['party'][0]['hp']+=1
                elif fault=='wrong-plan': hp['motion']['plan']['flags']=0
                elif fault=='wrong-reservation': mount['reservationId']+=1
                elif fault=='wrong-pair-owner': moving['mountedPair']['mountPointer']+=4
                elif fault=='wrong-seat-height':
                    moving['player']['face_y']+=4096
                    moving['mountedPair']['player']['face_y']+=4096
                elif fault=='unfinished-commit':
                    a=next(a for a in terminal['actors'] if a['role']=='MOUNTED')
                    a['commitSequence']=4
                else:
                    terminal['player']['unk88_y']=4096
                    terminal['mountedPair']['player']['unk88_y']=4096
                finished,result=evaluate(stream)
                self.assertFalse(finished['passed'],result)
                self.assertTrue(result['failures'])

    def test_positioning_application_is_not_a_throw_release(self):
        stream = rows()
        launch = next(row for row in stream if row.get('action') == 'launch-natural-throw')
        source = next(a for a in launch['samples'][-1]['actors'] if a['species'] == 74)
        source['matchedLayerMask'] = 1 << 21
        finished, result = evaluate(stream)
        self.assertFalse(finished['passed'])
        self.assertIsNone(result['launchFrame'])

    def test_ordinary_hop_waits_for_exact_release_before_launched_stage(self):
        from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
        recipe = validate_test(json.loads(RECIPE.read_text()))
        predicate = recipe['actions'][1]['args']['until']
        self.assertEqual(predicate, {'kind': 'measurement-stage', 'measurement': KIND,
                                     'stage': 'launched', 'when': 'final'})
        stream = rows()
        index = next(i for i, row in enumerate(stream)
                     if row.get('action') == 'launch-natural-throw')
        launch = stream[index]
        ordinary = next(a for a in launch['samples'][0]['actors'] if a['species'] == 69)
        ordinary.update(motionKind='HOP', motionPhase='MOVING', motionDuration=7,
                        origin={'x': 585, 'y': 400}, target={'x': 587, 'y': 400})
        meter = PlayerHealthMountedThrowMeasurement(SOURCE)
        for row in stream[:index]: meter.observe_record(row)
        meter.observe_record(step_row('launch-natural-throw', launch['samples'][:1]))
        self.assertEqual(meter.result()['failures'], [])
        evaluator = SimpleNamespace(specs={}, latest=meter.latest, uses_raw_records=False,
                                    measurements={KIND: meter})
        self.assertFalse(TestEvaluator.check(evaluator, predicate))
        meter.observe_record(step_row('launch-natural-throw', launch['samples'][1:]))
        evaluator.latest = meter.latest
        self.assertTrue(TestEvaluator.check(evaluator, predicate))
        self.assertFalse(meter.result()['ready'])
        for row in stream[index+1:]: meter.observe_record(row)
        self.assertTrue(meter.finish()['passed'], meter.result()['failures'])

    def test_later_independent_hop_does_not_change_the_completed_throw(self):
        stream = rows()
        target = next(a for a in stream[-2]['samples'][50]['actors']
                      if a['species'] == 69)
        target.update({'motionKind': 'HOP', 'motionPhase': 'MOVING',
                       'origin': {'x': 585, 'y': 406},
                       'target': {'x': 584, 'y': 407},
                       'motionElapsed': 1, 'motionDuration': 6})
        finished, result = evaluate(stream)
        self.assertTrue(finished['passed'], result['failures'])

    def test_same_queue_successor_requires_exact_full_cargo_terminal(self):
        stream=set_flight(rows(),origin_y=399,duration=25,commit_sequence=2,successor=True)
        done,result=evaluate(stream)
        self.assertTrue(done['passed'],result['failures'])
        terminal=result['flightTerminal']
        self.assertEqual((terminal['commitSequence'],terminal['commitEventSequence'],
            terminal['finishEventSequence'],terminal['controlEventSequence']),(3,141,142,143))
        self.assertEqual(result['flightFrames'],24)
        self.assertTrue(result['oldBoxCrossed']);self.assertTrue(result['mountSeatRestored'])
        for fault in ('missing-commit','stale-commit','missing-finish','missing-control',
                      'early-start','wrong-owner','missing-clock','wrong-clock',
                      'wrong-origin','wrong-height','wrong-reservation','wrong-plan'):
            with self.subTest(fault=fault):
                bad=deepcopy(stream);cross=next(r for r in bad if r.get('action')=='cross-player')
                snap=cross['samples'][24];cargo=next(a for a in snap['actors'] if a['species']==69)
                event={e['data']['event']:e for e in cross['events']}
                if fault.startswith('missing-') and fault!='missing-clock':
                    name={'missing-commit':'LOGICAL_COMMIT','missing-finish':'MOTION_FINISHED',
                          'missing-control':'CONTROL_RETURNED'}[fault]
                    cross['events'].remove(event[name])
                elif fault=='stale-commit':event['LOGICAL_COMMIT']['data']['valueA']=2
                elif fault=='early-start':event['MOTION_STARTED']['data']['sequence']=140
                elif fault=='wrong-owner':event['LOGICAL_COMMIT']['data']['actor']['generation']+=1
                elif fault=='missing-clock':event['LOGICAL_COMMIT']['data'].pop('actorFrame')
                elif fault=='wrong-clock':event['LOGICAL_COMMIT']['data']['frame']-=1
                elif fault=='wrong-origin':cargo['origin']['x']-=1
                elif fault=='wrong-height':cargo['engineObject']['pos_y']+=4096
                elif fault=='wrong-reservation':cargo['reservationId']=9
                else:
                    raw=bytearray.fromhex(snap['pokemonCombat']['targets'][1]['motion']['rawHex'])
                    raw[28]^=1
                    snap['pokemonCombat']['targets'][1]['motion']['rawHex']=raw.hex()
                finished,result=evaluate(bad)
                self.assertFalse(finished['passed'],result)
                named={'missing-commit':'ordered full Cargo finish',
                    'missing-finish':'ordered full Cargo finish','missing-control':'ordered full Cargo finish',
                    'stale-commit':'completed first flight commit','early-start':'successor motion preceded',
                    'wrong-owner':'stale Cargo owner or Actor clock','missing-clock':'stale Cargo owner or Actor clock',
                    'wrong-clock':'stale Cargo owner or Actor clock','wrong-origin':'successor motion preceded',
                    'wrong-height':'wrong landing pose','wrong-reservation':'successor motion preceded',
                    'wrong-plan':'flight motion bytes differ'}
                self.assertIn(named[fault],' '.join(result['failures']))

    def test_current_party_max_hp_controls_the_contact_cap(self):
        # Current native owner is30→15; earlier28→14 remains a valid different PID.
        for maximum in (28,30):
            stream=set_flight(rows(),origin_y=399,duration=25,successor=True)
            for row in stream:
                for snap in row.get('samples',[])+([row['snapshot']] if 'snapshot' in row else []):
                    if not snap.get('party'):continue
                    hp=snap['pokemonCombat']['targets'][0]
                    damage=min(20,max(1,maximum//2)) if hp['hitCount'] else 0
                    hp.update(hp=maximum-damage,currentHp=maximum-damage,maxHp=maximum,
                        actualMaxHp=maximum,lastDamage=damage)
                    snap['party'][0].update(hp=maximum-damage,maxHp=maximum)
            done,result=evaluate(stream);self.assertTrue(done['passed'],result['failures'])
            bad=deepcopy(stream);snap=next(r for r in bad if r.get('action')=='cross-player')['samples'][23]
            hp=snap['pokemonCombat']['targets'][0]
            hp.update(hp=maximum-14,currentHp=maximum-14,lastDamage=14)
            snap['party'][0]['hp']=maximum-14
            if maximum==30:
                done,result=evaluate(bad);self.assertFalse(done['passed'],result)
                self.assertIn('capped damage differs',' '.join(result['failures']))

    def test_proof_requires_current_command_order_and_terminal(self):
        stream=set_flight(rows(),origin_y=399,duration=25,successor=True)
        done,result=evaluate(stream)
        replay=dict(passed=done['passed'],observedFrames=result['observedFrames'],measurements={KIND:result})
        self.assertEqual(measurements(stream,replay)['flightFrames'],24)
        stale=deepcopy(stream)
        geo=[r for r in stale if r.get('action') in ('spawn-geodude','bind-geodude')]
        bell=[r for r in stale if r.get('action') in ('spawn-bellsprout','bind-bellsprout')]
        for left,right in zip(geo,bell):left['action'],right['action']=right['action'],left['action']
        with self.assertRaisesRegex(ValueError,'sealed command stream'):measurements(stale,replay)
        missing=deepcopy(replay);missing['measurements'][KIND]['flightTerminal']['controlEventSequence']=142
        with self.assertRaisesRegex(ValueError,'ordered full Cargo terminal'):measurements(stream,missing)

    def test_post_flight_hp_or_hit_copied_data_is_rejected(self):
        stream = rows()
        finished, result = evaluate(faulted_rows(stream, 'post-flight-damage'))
        self.assertFalse(finished['passed'])
        self.assertIn('damaged the rider', ' '.join(result['failures']))
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, result = evaluate(faulted_rows(stream, fault))
                self.assertFalse(finished['passed'])
                self.assertTrue(result['failures'])


if __name__ == '__main__':
    unittest.main()

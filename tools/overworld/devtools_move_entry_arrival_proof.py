"""Host-only proof over the existing MotionRecorder and sealed Entry receipts.

A prepared request selects the site. Native PREPARE owns the actual origin
and target; ADOPT owns the created actor. READY alone never proves arrival.
No live callback, guest write, profile override, or new measurement is added.
"""
from copy import deepcopy
import re
import struct

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_test_contract import _wild_spawn_setup
from tools.overworld.devtools_spawn_outcome_records import loader_identity
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = 'move-entry-arrival-v1'
TEST_ID = 'spawn.move-entry.arrival'
REQUIREMENT = 'current.move-entry-arrival'
CLAIMS = ['live-actor-identity', 'terrain-selection', 'logical-commit', 'rendered-motion', 'control-release']
NAMES = ['move-entry-current-rattata', 'move-entry-prepared-native-route',
         'move-entry-real-start-end', 'move-entry-exact-target-pose', 'move-entry-trip-cleared']
FAULTS = ('missing-prepare', 'stale-adopt', 'missing-guide', 'missing-start',
          'missing-end', 'false-arrival', 'missing-trip-clear')
HANDLE = ('value', 'slot', 'generation', 'fieldEpoch', 'mapGeneration', 'encounterGeneration')


def need(ok, reason):
    if not ok:
        raise ValueError('Move entry: ' + reason)


def contract():
    return {claim: [dict(name=name, operator='eq', type='integer',
                        validator='meaningful-observation', expected=1)]
            for claim, name in zip(CLAIMS, NAMES)}


def recipe_scope(test):
    """Exact generic actions, not a new test-contract measurement kind."""
    return (test['id'] == TEST_ID and test['mode'] == 'prepared'
            and test['fixture'] == dict(rom='test.nds', save='test.sav')
            and test['requirements'] == [REQUIREMENT]
            and test['subjects'] == [dict(id='rattata', species=19, role='WILD', acquire='spawn')]
            and test.get('measurements') in (None, [])
            and [(a['id'], a['op'], a['args']) for a in test['setup']] == [
                ('route30-shore', 'teleport', dict(map=34, x=565, z=369, facing=0)),
                ('settle-route30', 'step', dict(frames=60, keys=[])),
                ('request-rattata', 'spawn', dict(species=19, form=0, role='wild', level=4, x=560, z=375)),
                ('bind-rattata', 'bind', dict(subject='rattata'))]
            and [(a['id'], a['op'], a['args']) for a in test['actions']] == [
                ('travel', 'step', dict(frames=240, keys=[]))]
            and test['budgets']['minObservedFrames'] == 240)


def _key(value):
    need(isinstance(value, dict) and all(type(value.get(k)) is int for k in HANDLE),
         'full actor handle missing')
    need(0 <= value['slot'] < 10 and value['slot'] != 7
         and all(value[k] > 0 for k in HANDLE[2:])
         and value['value'] == value['slot'] | value['generation'] << 16,
         'full actor handle invalid')
    return tuple(value[k] for k in HANDLE)


def _receipt(data):
    receipt = data.get('entry', {}).get('receipt', {})
    raw = bytes.fromhex(receipt.get('rawHex', ''))
    need(len(raw) == 64 and struct.unpack_from('<HH', raw) == (1, 64), 'typed route receipt missing')
    serial = struct.unpack_from('<I', raw, 4)[0]
    fields = struct.unpack_from('<6H', raw, 8)
    actor = None if fields == (0,) * 6 else dict(zip(HANDLE[1:], fields[:5]),
                                              value=fields[0] | fields[1] << 16)
    need(fields[5] == 0 and serial > 0, 'route receipt owner invalid')
    positions = [list(struct.unpack_from('<hhiH', raw, o)) for o in (20, 32, 44)]
    need(all(raw[o:o + 2] == bytes(2) for o in (30, 42, 54)), 'route position padding differs')
    tag, steps, status, reads, queued, has_next = struct.unpack_from('<HH4B', raw, 56)
    need(status in range(5) and reads <= 8 and steps <= 96 and queued <= 2 and has_next <= 1
         and (serial, actor, status, reads, queued, has_next) ==
         (receipt.get('serial'), receipt.get('actor'), receipt.get('status'),
          receipt.get('readsUsed'), receipt.get('queued'), receipt.get('hasNextStep'))
         and data.get('returnValue') == data.get('resultStatus') == status,
         'raw/typed route result differs')
    return dict(serial=serial, actor=actor, origin=positions[0], target=positions[1],
                nextStep=positions[2], edgeTag=tag, steps=steps, status=status,
                reads=reads, queued=queued, hasNext=has_next)


def _stream(rows):
    """Keep actual command queue work, dense samples and all native receipts."""
    samples, events, seen = {}, [], {}
    for row in rows:
        candidates = list(row.get('samples', []))
        for key in ('initialSnapshot', 'boundarySnapshot', 'snapshot'):
            if isinstance(row.get(key), dict):
                candidates.append(row[key])
        receipt = row.get('receipt', {})
        if isinstance(receipt, dict):
            candidates.extend(receipt.get('samples', []))
        for sample in candidates:
            frame = sample.get('frame')
            need(type(frame) is int, 'completed frame missing')
            if frame in samples:
                need(all(samples[frame].get(k) == sample.get(k) for k in
                         ('nativeCycle', 'actorFrame', 'context', 'actors', 'player')),
                     'changed duplicate completed frame')
            samples[frame] = sample
        source_events = [*row.get('initialEvents', []), *row.get('events', [])]
        if isinstance(receipt, dict):
            source_events.extend(receipt.get('events', []))
        for event in source_events:
            data = event.get('data', {})
            if event.get('kind') not in ('native', 'native-observation'):
                continue
            need(type(event.get('frame')) is int and type(data.get('sequence')) is int,
                 'native event has no ordered clock')
            key = (event['kind'], data.get('traceStream', 0), data['sequence'])
            if key in seen:
                need(seen[key] == event, 'changed duplicate native receipt')
                continue
            seen[key] = event
            events.append(event)
    need(0 < len(samples) <= 1200 and 0 < len(events) <= 50000, 'stream is absent or too large')
    # Sequences use separate authenticated native-observation and trace streams.
    previous = {}
    for event in events:
        data = event['data']; key = (event['kind'], data.get('traceStream', 0))
        need(data['sequence'] > 0 and (key not in previous or data['sequence'] == previous[key] + 1),
             'native receipt sequence has a gap or reversal')
        previous[key] = data['sequence']
    return samples, events


def measurements(rows, replay):
    need(replay.get('passed') is True and replay.get('failures') == [], 'generic shared replay failed')
    subject = replay.get('subjects', {}).get('rattata', {})
    subject_key = _key(subject.get('handle'))
    need(subject.get('species') == 19 and subject.get('role') == 'WILD'
         and subject.get('identityVerified') is True, 'bound Rattata identity differs')
    commands = [r for r in rows if r.get('command') == 'spawn']
    need(len(commands) == 1, 'one public spawn request required')
    command = commands[0]; spawn_snapshot = command['snapshot']; receipt = command['receipt']
    prepared = _wild_spawn_setup(receipt, spawn_snapshot, species=19, locomotion=3)
    need(_key(prepared['subject']['handle']) == subject_key
         and prepared['subject']['subjectIdentity'] == subject['subjectIdentity'], 'spawn/adopt subject differs')
    spawn = prepared['nativeSpawn']['data']
    world = spawn['worldContext']
    need(world['mapId'] == 34 and spawn['preparedEncounter']['level'] == 4, 'native spawn scope differs')
    admitted = spawn_snapshot.get('queuedEntrySpawn', {})
    native = admitted.get('receipt', {})
    need(native.get('status') == 1 and native.get('queued') == 0 and native.get('serial') > 0
         and admitted.get('tripSerial') == admitted.get('queueSerial') == native['serial'],
         'actual constructor has no adopted trip')
    serial = native['serial']; origin, target = native['origin'], native['target']
    need(origin != target and origin[:2] == spawn['startup']['origin']
         and target[:2] == spawn['startup']['target'] and target[2] == spawn['startup']['targetBaseY'],
         'native route target/height differs from prepared startup')
    samples, events = _stream(rows)
    routes = []; image = None
    for event in events:
        data = event['data']
        if data.get('observation') not in ('entry-route-query', 'entry-native-control'):
            continue
        if data.get('slot') != subject['handle']['slot']:
            continue
        need(data.get('routeOperation') == 1 and data.get('cargoOwnerCredited') is False
             and data.get('diagnosticOnly') is True and data.get('acceptedProof') is False
             and data.get('boundary') == ('native-entry-route-tick-return'
                 if data['observation'] == 'entry-route-query' else 'native-entry-control-tick-return')
             and isinstance(data.get('readBytes'), dict)
             and set(data['readBytes']) == {'entry', 'returned'}
             and all(type(n) is int and 0 < n <= 0x9000 for n in data['readBytes'].values()),
             'Entry receipt coverage or budget differs')
        owner = loader_identity(data)
        need(owner == (world['fieldPointer'], world['fieldEpoch'], world['mapGeneration']),
             'Entry receipt belongs to stale world')
        identity = data['imageIdentity']
        hashes = tuple(identity.get(k) for k in ('elfSha256', 'packageSha256'))
        need(all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in hashes)
             and (image is None or image == hashes), 'native code identity changed during trip')
        image = hashes
        if data.get('entry', {}).get('kind') == 'ordinary-route':
            value = _receipt(data)
            if value['serial'] == serial:
                routes.append((event, value))
    ready = [(e, r) for e, r in routes if e['data']['entry']['operation'] == 0
             and r['status'] == 1 and r['queued'] == 1 and r['hasNext'] == 1]
    adopts = [(e, r) for e, r in routes if e['data']['entry']['operation'] == 1 and r['status'] == 1]
    need(len(ready) == len(adopts) == 1, 'missing exact PREPARE READY or ADOPT')
    preparation = [(e, r) for e, r in routes if e['data']['entry']['operation'] == 0]
    need(preparation and preparation[-1] == ready[0]
         and all(r['actor'] is None and r['status'] == (1 if i == len(preparation)-1 else 0)
                 and e['data']['entryActorFrame'] == e['data']['returnActorFrame']
                 for i, (e, r) in enumerate(preparation))
         and all(b[0]['frame'] == a[0]['frame'] + 1
                 and b[0]['data']['entryActorFrame'] == a[0]['data']['entryActorFrame'] + 1
                 for a, b in zip(preparation, preparation[1:])),
         'queued preparation has a missing, duplicate or rejected update')
    prep_event, prep = ready[0]; adopt_event, adopt = adopts[0]
    need(prep_event['data']['sequence'] < adopt_event['data']['sequence'] < spawn['sequence']
         and prep['actor'] is None and adopt['actor'] == subject['handle']
         and adopt_event['data']['subject'] == subject['handle']
         and prep['origin'] == adopt['origin'] == origin and prep['target'] == adopt['target'] == target,
         'PREPARE/ADOPT full identity, order or endpoint differs')
    retires = [(e, r) for e, r in routes if e['data']['entry']['operation'] == 3 and r['status'] == 1]
    need(len(retires) == 1, 'missing exact trip clear')
    retire, cleared = retires[0]; end_frame = retire['frame']
    need(cleared == dict(serial=serial, actor=None, origin=[0]*4, target=[0]*4,
                        nextStep=[0]*4, edgeTag=0, steps=0, status=1, reads=0, queued=0, hasNext=0)
         and retire['data']['subject'] == subject['handle'], 'trip clear retains state or wrong owner')
    guides = [(e, r) for e, r in routes if e['data']['entry']['operation'] == 2
              and r['status'] == 1 and r['actor'] == subject['handle']]
    terminal = [(e, r) for e, r in guides if not r['hasNext'] and e['frame'] == end_frame
                and r['target'] == target]
    need(terminal and terminal[-1][0]['data']['sequence'] < retire['data']['sequence'],
         'arrival has no terminal GUIDE before trip clear')
    updates = [e for e in events if e['frame'] == end_frame
               and e['data'].get('observation') == 'entry-native-control'
               and e['data'].get('slot') == subject['handle']['slot']
               and e['data'].get('subject') == subject['handle']
               and e['data'].get('entry') == dict(kind='native-control', operation=4, value=1)
               and e['data'].get('returnValue') == 1
               and e['data']['sequence'] > retire['data']['sequence']]
    need(updates, 'arrival lacks authenticated native trip-clear return')
    frames = list(range(spawn_snapshot['frame'], end_frame + 1))
    need(len(frames) > 1 and all(f in samples for f in frames), 'actual queue/acquire/travel frames missing')
    recorder = MotionRecorder(); actors = {}
    for frame in frames:
        sample = samples[frame]; coverage = sample.get('nativeObservation', {})
        need(sample.get('observationBoundary') == 'main-task-queue-completion'
             and coverage.get('coverageComplete') is True and coverage.get('installedBeforeBoot') is True
             and coverage.get('eventsDropped') == 0 and coverage.get('pendingUnframedEvents') == 0
             and coverage.get('profilesEvicted') == 0 and coverage.get('error') is None,
             'completed queue coverage incomplete')
        need(sample['context'] == spawn_snapshot['context'], 'trip world changed')
        selected = select_current_actor(sample, subject)
        actor = next(a for a in sample['actors'] if a['handle'] == selected['handle'])
        first_actor = next(a for a in spawn_snapshot['actors'] if a['handle'] == subject['handle'])
        need(actor['subjectIdentity'] == subject['subjectIdentity']
             and actor['sourceIdentity'] == first_actor['sourceIdentity']
             and engine_binding_identity(actor['engineIdentity']) == engine_binding_identity(first_actor['engineIdentity'])
             and actor['level'] == 4 and actor['inputOwnership'] == 0,
             'trip current PID/object/full identity differs')
        actors[frame] = actor
        recorder.observe(frame, actor, actor['engineObject'])
    need(not recorder.failures and recorder.current is None and recorder.completed,
         'shared MotionRecorder did not complete real movement')
    previous = origin[:2]; used_guides = []
    semantic = [e for e in events if e['kind'] == 'native' and e['data'].get('actorHandle') == subject['handle']['value']]
    for motion in recorder.completed:
        need(motion['handle'] == subject['handle'] and motion['kind'] == 'WALK'
             and motion['origin'] == previous and complete_travel(motion)
             and motion['commitAfter'] == (motion['commitBefore'] + 1) & 0xFFFFFFFF,
             'shared START/END route continuity differs')
        matching = [(e, r) for e, r in guides if r['hasNext'] and r['target'] == target
                    and r['nextStep'][:2] == motion['target']
                    and e['data']['returnActorFrame'] == samples[motion['startFrame']]['actorFrame']]
        need(matching, 'shared START has no exact saved GUIDE')
        guide, _ = matching[0]; used_guides.append(guide['data']['sequence'])
        chain = []
        for meaning, frame in (('PLAN_ACCEPTED', motion['startFrame']), ('MOTION_STARTED', motion['startFrame']),
                               ('LOGICAL_COMMIT', motion['commitFrame']), ('MOTION_FINISHED', motion['finishFrame']),
                               ('CONTROL_RETURNED', motion['finishFrame'])):
            candidates = [e for e in semantic if e['frame'] == frame and e['data'].get('event') == meaning]
            need(len(candidates) == 1, 'missing or duplicate ' + meaning)
            event = candidates[0]; full = dict(event['data']['actor'], value=event['data']['actorHandle'])
            need(_key(full) == subject_key and event['data'].get('reason') == 'OK', 'motion event has stale owner')
            chain.append(event['data']['sequence'])
        need(chain == sorted(set(chain)), 'shared motion event order differs')
        previous = motion['target']
    need(previous == target[:2], 'completed route did not reach exact native target')
    actor = actors[end_frame]; engine = actor['engineObject']
    need(actor['motionKind'] == 'NONE' and actor['motionPhase'] == 'IDLE'
         and actor['logical'] == dict(x=target[0], y=target[1]) and actor['reservationId'] == 0
         and engine['pos_x'] == (target[0] << 16) + 0x8000
         and engine['pos_z'] == (target[1] << 16) + 0x8000 and engine['pos_y'] == target[2]
         and engine['unk88_y'] == engine['unk94_y'] == 0,
         'false arrival or residual offset')
    return dict(observedFrames=replay['observedFrames'], arrivalFrame=end_frame,
                queuedPreparationReceipts=len(preparation),
                queueReceiptFrames=[preparation[0][0]['frame'], preparation[-1][0]['frame']],
                queueCoverage='Every typed Pending/READY callback; public command does not retain dense queue poses',
                origin=origin, target=target, serial=serial, subject=subject,
                completeMotions=len(recorder.completed), savedGuideSequences=used_guides,
                prepareSequence=prep_event['data']['sequence'], adoptSequence=adopt_event['data']['sequence'],
                tripClearSequence=retire['data']['sequence'], nativeImageIdentity=image,
                measurements=[dict(claim=claim, name=name, value=1, operator='eq', expected=1)
                              for claim, name in zip(CLAIMS, NAMES)])


def faulted_rows(rows, fault):
    need(fault in FAULTS, 'unknown copied control')
    changed = deepcopy(rows)
    command = next(r for r in changed if r.get('command') == 'spawn')
    slot = command['receipt']['value']['slot']
    selected_handle = next(a['handle'] for a in command['snapshot']['actors'] if a['handle']['slot'] == slot)
    def source(row):
        yield row.get('events', [])
        yield row.get('receipt', {}).get('events', [])
    for row in changed:
        for events in source(row):
            for index, event in enumerate(events):
                data = event.get('data', {}); entry = data.get('entry') or {}
                op = entry.get('operation'); r = entry.get('receipt', {})
                selected = data.get('observation') == 'entry-route-query' and r.get('status') == 1 and data.get('slot') == slot
                if fault == 'missing-prepare' and selected and op == 0 and r.get('queued') == 1:
                    del events[index]; return changed
                if fault == 'stale-adopt' and selected and op == 1:
                    data['subject']['generation'] += 1; return changed
                if fault == 'missing-guide' and selected and op == 2 and r.get('hasNextStep') == 1:
                    del events[index]; return changed
                if fault == 'missing-trip-clear' and selected and op == 3:
                    del events[index]; return changed
                if fault in ('missing-start', 'missing-end') and event.get('kind') == 'native' \
                        and data.get('event') == ('MOTION_STARTED' if fault == 'missing-start' else 'MOTION_FINISHED') \
                        and data.get('actorHandle') == selected_handle['value']:
                    del events[index]; return changed
    if fault == 'false-arrival':
        # Select the exact successful RETIRE boundary and its full actor.
        retire = next(e for row in changed for events in source(row) for e in events
                      if e.get('data', {}).get('observation') == 'entry-route-query'
                      and e['data'].get('entry', {}).get('operation') == 3
                      and e['data']['entry']['receipt']['status'] == 1
                      and e['data'].get('subject') == selected_handle)
        handle = retire['data']['subject']; frame = retire['frame']
        applied = False
        for row in changed:
            for sample in [*row.get('samples', []), row.get('snapshot', {})]:
                if sample.get('frame') == frame:
                    actor = next(a for a in sample['actors'] if a['handle'] == handle)
                    actor['engineObject']['unk88_y'] = 1; applied = True
        need(applied, 'arrival control has no exact terminal sample')
        return changed
    raise ValueError('Move entry copied control did not reach selected trip: ' + fault)

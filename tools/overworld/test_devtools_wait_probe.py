"""Host-only stock wait sampling checks; no emulator execution."""
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
import gzip
import hashlib
import json

from tools.overworld.devtools_wait_probe import WaitProbe

POST_WAIT_SITES = (0x02000E3C, 0x02000E40, 0x02000DAC, 0x02000DE0, 0x02000DE4, 0x02000DE8)


class WaitProbeTests(unittest.TestCase):
    def test_retained_first_event_exposes_missing_normal_envelope(self):
        """Saved raw event stays unchanged; rebuilt envelope is host-only data."""
        from tools.overworld.devtools_observer import NativeObservation
        from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
        from tools.overworld.test_devtools_cadence_measurement import Route
        root = Path(__file__).resolve().parents[2]
        run = root / 'build/overworld-devtools/test-7705e4e1da584ecd8caa38dd583f9227'
        if not run.exists(): self.skipTest('optional retained diagnostic is unavailable')
        manifest = json.loads((run / 'manifest.json').read_text())
        artifact = run / 'observations.jsonl.gz'
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),
                         manifest['observationsArtifact']['sha256'])
        with gzip.open(artifact, 'rt') as stream:
            saved = next(event for line in stream for event in json.loads(line).get('events', [])
                         if event.get('data', {}).get('observation') == 'stock-main-waits')
        meter = UnmountedCadenceMeasurement(Route().test, max_frames=32000)
        meter.prepared_seen = True
        meter.native_sequence = saved['data']['sequence'] - 1
        with self.assertRaisesRegex(ValueError, 'native observations missing, reordered, or prepared'):
            meter._events([saved], saved['frame'])
        probe, hooks, state, session = self.fixture()
        session.rt = SimpleNamespace(REPO=root)
        observer = NativeObservation(session, probe.hooks, None)
        observer.sequence = saved['data']['sequence'] - 1
        # Exercise the real normal envelope builder. These clock values are
        # explicitly synthetic: the old reader did not retain native clocks.
        observer._queue('stock-main-waits', dict(entry=dict(actorFrame=1, nativeCycle=2),
            returned=dict(actorFrame=1, nativeCycle=3), setupMode='prepared', returnValue=0), saved['data'])
        rebuilt = dict(frame=saved['frame'], kind='native-observation', data=observer.pending.popleft())
        self.assertEqual(meter._events([rebuilt], saved['frame']), [])
        self.assertEqual(rebuilt['data']['mandatory'], saved['data']['mandatory'])

    def fixture(self):
        arm9 = (Path(__file__).resolve().parents[2] / "build/arm9.bin").read_bytes()
        callbacks = {}
        callback_lists = {}
        regs = SimpleNamespace(r4=0x021D110C, r0=1, r1=1, sp=0x027E0000)
        state = dict(counter=0, tick=100, mode="baseline")
        def read(address, size):
            if address == 0x021D113C:
                return struct.pack('<I', state['counter'])
            return arm9[address-0x02000000:address-0x02000000+size]
        def clock():
            state['tick'] += 10
            return dict(version=1, running=True, scope='nds-scheduler-ticks-not-cpu-or-instructions',
                        arm9Timestamp=state['tick'], arm7Timestamp=state['tick']//2, frameSequence=10)
        session = SimpleNamespace(read=read, packaged_code=read,
            spawn_cost_probe=SimpleNamespace(mode='baseline'),
            emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=regs)))
        def add_hook(address, callback):
            items = callback_lists.setdefault(address, [])
            items.append(callback)
            if len(items) == 1:
                callbacks[address] = lambda: [item() for item in tuple(callback_lists.get(address, ()))]
            return address, callback
        def remove_hook(token):
            address, callback = token if isinstance(token, tuple) else (token, callbacks.get(token))
            items = callback_lists.get(address, [])
            if callback in items:
                items.remove(callback)
            if not items:
                callback_lists.pop(address, None)
                callbacks.pop(address, None)
        hooks = SimpleNamespace(add=add_hook, remove=remove_hook)
        return WaitProbe(session, hooks, clock, lambda: dict(actorFrame=885, nativeCycle=10)), callbacks, state, session

    def test_skip_conditional_and_complete_exactly_eight_cycles(self):
        probe, hooks, state, session = self.fixture()
        state['counter'] = 2
        rows = []
        for frame in range(1306, 1510):
            rows.extend(probe.completed_frame(frame))
            if hooks:
                for address in (0x02000DF4, 0x02000E1E, 0x02000E22):
                    hooks[address]()
                for address in POST_WAIT_SITES:
                    hooks[address]()
        self.assertEqual([r['afterQueueFrame'] for r in rows],
                         [1307, 1308, 1309, 1310, 1505, 1506, 1507, 1508])
        self.assertTrue(all(r['conditional'] is None for r in rows))
        self.assertFalse(hooks)
        self.assertEqual(probe.result()['completedCycles'], 8)
        result = probe.result()
        result['windows'][0][0] = 0
        self.assertEqual(probe.result()['windows'][0][0], 1307)
        probe.close(); probe.close()
        self.assertIsNone(probe.result()['failure'])

    def test_late_route_window_completes_six_cycles_and_keeps_old_windows(self):
        probe, hooks, state, session = self.fixture()
        state['counter'] = 2
        rows = []
        for frame in range(4638, 4646):
            rows.extend(probe.completed_frame(frame))
            if hooks:
                for address in (0x02000DF4, 0x02000E1E, 0x02000E22):
                    hooks[address]()
                for address in POST_WAIT_SITES:
                    hooks[address]()
        self.assertEqual([r['afterQueueFrame'] for r in rows], list(range(4639, 4645)))
        self.assertEqual(probe.result()['windows'], [[1307, 1310], [1505, 1508], [3566, 3575], [4639, 4644]])
        self.assertEqual(probe.result()['completedCycles'], 6)
        self.assertFalse(hooks)
        probe.close()
        self.assertIsNone(probe.result()['failure'])

    def test_failed_spawn_window_is_complete(self):
        probe, hooks, state, _ = self.fixture()
        state['counter'] = 1
        rows = []
        for frame in range(3565, 3577):
            rows.extend(probe.completed_frame(frame))
            if hooks:
                for address in (0x02000DF4, 0x02000E1E, 0x02000E22) + POST_WAIT_SITES:
                    hooks[address]()
        self.assertEqual([r['afterQueueFrame'] for r in rows], list(range(3566, 3576)))
        self.assertFalse(hooks)
        probe.close()
        self.assertIsNone(probe.result()['failure'])

    def test_bad_owner_arguments_order_and_clock_latch_failure(self):
        for fault, cause in (('owner', 'system owner'), ('args', 'arguments'),
                             ('order', 'order'), ('clock', 'backwards'), ('stack', 'stack owner')):
            with self.subTest(fault=fault):
                probe, hooks, state, session = self.fixture()
                probe.completed_frame(1307)
                regs = session.emu.memory.register_arm9
                if fault == 'owner': regs.r4 += 4
                if fault == 'owner':
                    with self.assertRaisesRegex(ValueError, cause): hooks[0x02000DF4]()
                else:
                    hooks[0x02000DF4]()
                    if fault == 'args': regs.r0 = 0
                    if fault == 'clock': state['tick'] = 0
                    if fault == 'stack': regs.sp -= 4
                    with self.assertRaisesRegex(ValueError, cause):
                        hooks[0x02000E22 if fault == 'order' else 0x02000DFE]()
                self.assertIn(cause, probe.result()['failure'])
                probe.close()
                self.assertFalse(hooks)

    def test_missing_pair_and_code_change_detach_hooks(self):
        for fault in ('missing', 'code'):
            with self.subTest(fault=fault):
                probe, hooks, state, session = self.fixture()
                probe.completed_frame(1307)
                for address in (0x02000DF4, 0x02000DFE, 0x02000E02, 0x02000E1E):
                    hooks[address]()
                if fault == 'code':
                    hooks[0x02000E22]()
                    for address in POST_WAIT_SITES:
                        hooks[address]()
                    session.packaged_code = lambda address, size: bytes(size)
                with self.assertRaisesRegex(ValueError, 'lacks wait pair' if fault == 'missing' else 'code identity'):
                    probe.completed_frame(1308)
                self.assertFalse(hooks)

    def test_partial_install_cleanup_and_nonbaseline_rejection(self):
        probe, hooks, state, session = self.fixture()
        original = probe.hooks.add
        def add(address, callback):
            if address == 0x02000E02: raise RuntimeError('registration failed')
            return original(address, callback)
        probe.hooks.add = add
        with self.assertRaisesRegex(RuntimeError, 'registration failed'):
            probe.completed_frame(1307)
        self.assertFalse(hooks)
        for mode in (None, 'omit-spawn-details'):
            session.spawn_cost_probe.mode = mode
            with self.assertRaisesRegex(ValueError, 'requires diagnostic baseline'):
                WaitProbe(session, probe.hooks, probe.clock, probe.native_clock)

    def test_native_observer_default_off_and_baseline_event_delivery(self):
        from tools.overworld.devtools_observer import NativeObservation
        probe, hooks, state, session = self.fixture()
        session.rt = SimpleNamespace(REPO=Path(__file__).resolve().parents[2])
        session.emu.guest_clock = probe.clock
        probe.hooks.error = None
        session.spawn_cost_probe.mode = None
        session.prepared = True
        observer = NativeObservation(session, probe.hooks, None)
        observer._clock = probe.native_clock
        observer.completed_frame(1306)
        self.assertIsNone(observer.wait_probe)
        session.spawn_cost_probe.mode = 'baseline'
        observer.completed_frame(1307)
        for address in (0x02000DF4, 0x02000DFE, 0x02000E02, 0x02000E1E, 0x02000E22):
            hooks[address]()
        for address in POST_WAIT_SITES:
            hooks[address]()
        observer.completed_frame(1308)
        drained = observer.drain()
        row, = [event for event in drained
                 if event['data']['observation'] == 'stock-main-waits']
        loop_rows = [event for event in drained
                     if event['data']['observation'] == 'stock-main-loop-pacing']
        self.assertEqual(len(loop_rows), 1)
        self.assertEqual(loop_rows[0]['data']['returnSite'], 0x02000E22)
        self.assertEqual(loop_rows[0]['data']['intervalFromPrevious'], None)
        self.assertEqual((row['frame'], row['data']['afterQueueFrame']), (1308, 1307))
        self.assertEqual(row['data']['observation'], 'stock-main-waits')
        self.assertEqual(row['data']['setupMode'], 'prepared')
        self.assertEqual(row['data']['entryActorFrame'], 885)
        self.assertEqual([s['site'] for s in row['data']['stages']], list(POST_WAIT_SITES) + [0x02000DEE])
        from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
        from tools.overworld.test_devtools_cadence_measurement import Route
        meter = UnmountedCadenceMeasurement(Route().test, max_frames=32000)
        meter.prepared_seen = True
        self.assertEqual(meter._events([row], 1308), [])
        self.assertEqual(observer.snapshot()['stockWaitProbe']['completedCycles'], 1)
        observer.close()
        self.assertFalse(hooks)

    def test_invalid_clock_types_and_unsigned_bounds(self):
        for field, value in [('version', True)] + [(key, 1 << 64) for key in
                ('arm9Timestamp', 'arm7Timestamp', 'frameSequence')]:
            with self.subTest(field=field):
                probe, hooks, state, session = self.fixture()
                original = probe.clock
                probe.clock = lambda: {**original(), field: value}
                probe.completed_frame(1307)
                with self.assertRaisesRegex(ValueError, 'invalid guest clock'):
                    hooks[0x02000DF4]()
                probe.close()
                self.assertFalse(hooks)

    def test_missing_reordered_and_wrong_owner_stage_fail(self):
        for fault, cause in (('missing', 'lacks wait pair or stage'),
                             ('order', 'wait order'), ('owner', 'system owner')):
            with self.subTest(fault=fault):
                probe, hooks, state, session = self.fixture()
                probe.completed_frame(1307)
                for address in (0x02000DF4, 0x02000DFE, 0x02000E02, 0x02000E1E, 0x02000E22):
                    hooks[address]()
                if fault == 'missing':
                    with self.assertRaisesRegex(ValueError, cause): probe.completed_frame(1308)
                else:
                    if fault == 'owner': session.emu.memory.register_arm9.r4 += 4
                    with self.assertRaisesRegex(ValueError, cause):
                        hooks[0x02000E40 if fault == 'order' else 0x02000E3C]()
                probe.close()
                self.assertFalse(hooks)

    def test_two_real_wait_pairs_are_framed_at_following_queue(self):
        probe, hooks, state, session = self.fixture()
        self.assertEqual(probe.completed_frame(1306), [])
        self.assertFalse(hooks)
        self.assertEqual(probe.completed_frame(1307), [])
        for address in (0x02000DF4, 0x02000DFE, 0x02000E02, 0x02000E1E, 0x02000E22):
            hooks[address]()
        for address in POST_WAIT_SITES:
            hooks[address]()
        rows = probe.completed_frame(1308)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['afterQueueFrame'], 1307)
        self.assertEqual(rows[0]['flushedAtQueueFrame'], 1308)
        self.assertEqual(rows[0]['conditional']['arm9Ticks'], 10)
        self.assertEqual(rows[0]['mandatory']['arm9Ticks'], 10)
        self.assertEqual([s['site'] for s in rows[0]['stages']], list(POST_WAIT_SITES) + [0x02000DEE])
        self.assertEqual(rows[0]['stages'][-1]['clock']['arm9Timestamp'] -
                         rows[0]['mandatory']['returned']['clock']['arm9Timestamp'], 70)
        probe.close()
        self.assertFalse(hooks)


if __name__ == '__main__':
    unittest.main()

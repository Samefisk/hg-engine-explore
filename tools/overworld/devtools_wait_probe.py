"""Bounded diagnostic stock-main wait cycles, with no guest writes or LR hooks.

Queue F completes before these waits. Its record is published at queue F+1.
Only the existing spawn-cost baseline diagnostic can enable this reader.
"""
from copy import deepcopy
import hashlib
import struct

WINDOWS = ((1307, 1310), (1505, 1508), (3566, 3575), (4639, 4644))
MAX_CYCLES = sum(end - start + 1 for start, end in WINDOWS)
SITES = (0x02000DF4, 0x02000DFE, 0x02000E02, 0x02000E1E, 0x02000E22)
STAGES = (
    (0x02000E3C, 'after-display-callback'), (0x02000E40, 'after-sound'),
    (0x02000DAC, 'after-vwait-tasks'), (0x02000DE0, 'before-main-overlay'),
    (0x02000DE4, 'after-main-overlay'), (0x02000DE8, 'before-main-queue'),
    (0x02000DEE, 'completed-main-queue'),
)
STAGE_SITES = tuple(address for address, _ in STAGES)
SYSTEM = 0x021D110C
COUNTER = SYSTEM + 0x30
IDENTITIES = (
    (0x02000DA6, 2, 'd4ae3f18f30287286d6128ecd2450dcad6d54a5b7ec08cc2bfcd33ade7b8aabd'),
    (0x02000E64, 4, '5aef138e6d7e569819712106b1a636e7c6bcd69c7921e5c65ea1b8d9fd521346'),
    (0x02000DAC, 156, 'c703bc77c00bf50273ef4aa864802da4081cdd503782e8fad9491ecaea7910f5'),
    (0x020D0E6C, 116, 'eb2d22331914c2668b42876093b57b22613db856cb82c72c66b91517a00eb1c8'),
)


class WaitProbe:
    def __init__(self, session, hooks, clock, native_clock, *, windows=WINDOWS):
        self.session, self.hooks, self.clock = session, hooks, clock
        self.native_clock = native_clock
        self.tokens, self.active = [], None
        self.completed, self.closed, self.failure = 0, False, None
        self.last_frame = None
        self.windows = tuple(windows)
        self._require(bool(self.windows) and all(type(a) is int and type(b) is int
                      and 0 <= a <= b for a, b in self.windows)
                      and all(a > self.windows[i - 1][1] for i, (a, b) in enumerate(self.windows) if i),
                      'invalid sample windows')
        self.max_cycles = sum(b - a + 1 for a, b in self.windows)
        self._require(self.max_cycles <= 5000, 'sample window exceeds bound')
        self._require(getattr(getattr(session, 'spawn_cost_probe', None), 'mode', None) == 'baseline',
                      'requires diagnostic baseline')

    def _require(self, condition, reason):
        if not condition:
            self.failure = self.failure or 'stock wait probe: ' + reason
            raise ValueError(self.failure)

    def _authenticate(self):
        for address, size, digest in IDENTITIES:
            code = self.session.packaged_code(address, size)
            self._require(len(code) == size and hashlib.sha256(code).hexdigest() == digest,
                          f'code identity differs at {address:#x}')

    def _detach(self):
        for token in self.tokens:
            self.hooks.remove(token)
        self.tokens.clear()

    def _sample(self, site):
        self._require(self.failure is None and not self.closed and self.active is not None,
                      'callback outside active window')
        value = deepcopy(self.clock())
        self._require(type(value.get('version')) is int and value['version'] == 1 and value.get('running') is True
                      and value.get('scope') == 'nds-scheduler-ticks-not-cpu-or-instructions'
                      and all(type(value.get(k)) is int and 0 <= value[k] < (1 << 64) for k in
                              ('arm9Timestamp', 'arm7Timestamp', 'frameSequence')), 'invalid guest clock')
        regs = self.session.emu.memory.register_arm9
        raw = self.session.read(COUNTER, 4)
        self._require(len(raw) == 4, 'counter read incomplete')
        native = self.native_clock()
        self._require(all(type(native.get(k)) is int and native[k] >= 0
                          for k in ('actorFrame', 'nativeCycle')), 'invalid native clock')
        row = dict(site=site, clock=value, native=deepcopy(native), r0=regs.r0 & 0xFFFFFFFF,
                   frameCounter=struct.unpack('<I', raw)[0], sp=regs.sp & 0xFFFFFFFF)
        active = self.active
        samples = active['samples']
        if samples:
            prior = samples[-1]
            self._require(row['sp'] == prior['sp'], 'stack owner differs')
            self._require(all(value[k] >= prior['clock'][k] for k in
                              ('arm9Timestamp', 'arm7Timestamp', 'frameSequence')), 'guest clock went backwards')
        self._require(len(samples) < 12, 'sample limit reached')
        expected = (SITES if not samples or samples[0]['frameCounter'] == 0
                    else (SITES[0], SITES[3], SITES[4])) + STAGE_SITES
        self._require(len(samples) < len(expected) and site == expected[len(samples)],
                      'wait order or pair differs')
        self._require(regs.r4 & 0xFFFFFFFF == SYSTEM, 'system owner differs')
        if site in (SITES[1], SITES[3]):
            self._require(regs.r0 & 0xFFFFFFFF == 1 and regs.r1 & 0xFFFFFFFF == 1,
                          'wait arguments differ')
        samples.append(row)

    def completed_frame(self, frame):
        self._require(self.failure is None and not self.closed, 'reader is stopped')
        self._require(type(frame) is int and frame >= 0 and
                      (self.last_frame is None or frame == self.last_frame + 1), 'queue sequence differs')
        self.last_frame = frame
        rows = []
        try:
            if self.active is not None:
                active = self.active
                samples = active['samples']
                wait_count = 5 if samples and samples[0]['frameCounter'] == 0 else 3
                self._require(frame == active['afterQueueFrame'] + 1 and samples
                              and len(samples) == wait_count + 6,
                              'completed queue lacks wait pair or stage')
                self._sample(STAGE_SITES[-1])
                self._authenticate()
                def pair(a, b):
                    return dict(entry=deepcopy(a), returned=deepcopy(b),
                                arm9Ticks=b['clock']['arm9Timestamp']-a['clock']['arm9Timestamp'])
                rows.append(dict(observation='stock-main-waits', afterQueueFrame=active['afterQueueFrame'],
                    flushedAtQueueFrame=frame, branch=deepcopy(samples[0]),
                    conditional=pair(samples[1], samples[2]) if wait_count == 5 else None,
                    mandatory=pair(samples[wait_count-2], samples[wait_count-1]),
                    stages=[dict(deepcopy(sample), stage=name) for sample, (_, name)
                            in zip(samples[wait_count:], STAGES)],
                    scope='inclusive-arm9-scheduler-ticks-including-waits-and-irqs',
                    diagnosticOnly=True, acceptedProof=False))
                self.completed += 1
                self.active = None
            selected = any(start <= frame <= end for start, end in self.windows)
            if selected:
                self._require(self.completed < self.max_cycles, 'cycle limit reached')
                if not self.tokens:
                    self._authenticate()
                    for site in SITES + STAGE_SITES[:-1]:
                        self.tokens.append(self.hooks.add(site, lambda site=site: self._sample(site)))
                self.active = dict(afterQueueFrame=frame, samples=[])
            else:
                self._detach()
            return rows
        except Exception as error:
            self.failure = self.failure or str(error)
            self._detach()
            raise

    def result(self):
        return deepcopy(dict(schemaVersion=1, windows=[list(x) for x in self.windows],
            identities=[dict(address=a, size=n, sha256=h) for a, n, h in IDENTITIES],
            completedCycles=self.completed, active=self.active, closed=self.closed,
            failure=self.failure, attachedHooks=len(self.tokens), guestMemoryWrites=0,
            diagnosticOnly=True, acceptedProof=False))

    def close(self):
        if not self.closed:
            if self.active is not None:
                self.failure = self.failure or 'stock wait probe: closed before next queue flushed window'
            self._detach()
            self.closed = True

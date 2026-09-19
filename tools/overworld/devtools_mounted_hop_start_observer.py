"""One opt-in Hop takeoff receipt at the real custom-start return boundary.

The vanilla position setter normalizes coordinates/held movement; it does not
sample the Hop arc. Read the actual ridden object's facing vector after that
setter and both freeze commands, before the first UpdateCustomMotion tick.
"""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver
from tools.overworld.devtools_observer import public_bytes

SYMBOL = 'OverworldMount_TryStartCustomMotion.constprop.0'
STATE_ADDRESS, STATE_BYTES = 0x023BC744, 184
MAX_ATTEMPTS = 256


class NativeMountedHopStartObserver(NativeMountedPacingObserver):
    def __init__(self, session, subject, max_frames):
        super().__init__(session, subject, max_frames)
        self.counts = dict(attempts=0, starts=0)
        self.latest = None
        self.code = None

    def _authenticate(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        s = self.session
        path = s.rt.REPO / 'build/overworld_mount_overlay_linked.o'
        address, size = _elf_function_extent(path, SYMBOL)
        code = self.observer.elf_code(path, address, size)
        self._require(s.rt.linked_symbol(s.rt.MOUNT_SYMBOLS, 'sOverworldMountState') == STATE_ADDRESS
            and s.rt.linked_symbol(s.rt.MOUNT_SYMBOLS, SYMBOL) & ~1 == address
            and size >= 32 and len(code) == size and s.packaged_code(address, size) == code,
            'Hop start linked/package code differs')
        self.code = (address, code)
        self.provenance = dict(symbol=SYMBOL, address=address, size=size,
            sha256=hashlib.sha256(code).hexdigest(), stateAddress=STATE_ADDRESS, stateBytes=STATE_BYTES)
        self._live_code()

    def _live_code(self):
        address, code = self.code
        self._require(self.session.read(address, len(code)) == code, 'Hop start live code differs')

    def arm(self):
        self._require(not self.armed and not self.closed and type(self.maximum) is int
            and 1 <= self.maximum <= 7800, 'invalid Hop start arm/bound')
        s = self.session
        self._require(s.emu is not None and not s.native_bridge_active
            and s.rom.resolve().is_relative_to(s.directory.resolve())
            and s.rom.resolve() != (s.rt.REPO / 'test.nds').resolve(), 'Hop start requires private session')
        self.started = s.completed_frames
        try:
            self.owner = self._current()
            self._authenticate()
            self.armed = True
            self._install('mounted-hop-start', SYMBOL, self._before_start, self._after_start)
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close()
            raise
        return self.result()

    def _before_start(self):
        self._check_deadline()
        self._live_code()
        self._require(self.counts['attempts'] < MAX_ATTEMPTS, 'Hop start attempt bound exceeded')
        current = self._current()
        pose = self._read_pose(current)
        self._require(type(pose['mount'].get('face_y')) is int, 'missing actual mount face_y')
        value = dict(current=current, baseFaceY=pose['mount']['face_y'],
            completedFrame=self.session.completed_frames)
        self.counts['attempts'] += 1
        self.data.append(value)
        return value

    def _after_start(self, before, context):
        try:
            self._check_deadline()
            self._live_code()
            self._require(context['returnValue'] in (0, 1), 'custom start returned invalid BOOL')
            current = self._current()
            raw = public_bytes(self.session, STATE_ADDRESS, STATE_BYTES)
            if context['returnValue'] == 0 or raw[102] != 1:
                return None
            actor = current['publicSubject']
            identity, = struct.unpack_from('<H', raw, 126)
            duration, elapsed = struct.unpack_from('<HH', raw, 144)
            coordinates = struct.unpack_from('<4h', raw, 152)
            self._require(actor['motionKind'] == 'HOP' and actor['motionPhase'] in ('PLANNED', 'MOVING')
                and 0 < identity == actor['reservationId'] and duration > 0 and elapsed == 0
                and actor['motionElapsed'] == 0 and actor['motionDuration'] == duration
                and coordinates == (actor['origin']['x'], actor['origin']['y'], actor['target']['x'], actor['target']['y']),
                'Hop start actor/state receipt differs')
            pose = self._read_pose(current)
            self._require(type(pose['mount'].get('face_y')) is int, 'missing actual start face_y')
            self._require(self.session.completed_frames == before['completedFrame'], 'Hop start crossed completed frame')
            value = dict(subject=deepcopy(self.subject), current=current, pose=pose,
                start=dict(elapsed=0, duration=duration, origin=deepcopy(actor['origin']),
                    target=deepcopy(actor['target']), motionIdentity=identity,
                    baseFaceY=before['baseFaceY'], faceY=pose['mount']['face_y'],
                    arcHeightQ4=raw[141]),
                completedFrame=before['completedFrame'], mountStateHex=raw.hex(),
                provenance=deepcopy(self.provenance), normalReturn=True,
                meaning='actual custom-start return pose before first Hop update; no synthetic elapsed sample')
            self.counts['starts'] += 1
            self.latest = deepcopy(value)
            return value  # Shared _tap adds sequence, actor frames and native clocks.
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(self.session, 'abort_native_control', None)
            if abort is not None:
                abort(error)
            raise
        finally:
            if before in self.data:
                self.data.remove(before)

    def completed_boundary(self):
        self._check_deadline()

    def result(self):
        return {**super().result(), 'latestStart': deepcopy(self.latest),
            'maxAttempts': MAX_ATTEMPTS, 'scope': 'native mounted Hop start only; no gameplay verdict'}

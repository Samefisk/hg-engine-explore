"""Bounded native UP landing queries; prepared evidence, never motion proof."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_mount_walk_fixture import STATE_ADDRESS, STATE_BYTES, authenticate_mount
from tools.overworld.devtools_walk_reset import WalkResetError, WalkPolicyReset

LANDING = 'OverworldMount_IsLandingTileAllowed'
SEARCH = 'OverworldMount_TryNextHopLandingCandidate.constprop.0'
MAX_QUERIES = 16 * 16 + 2 * 16


class HopCandidateProbeError(WalkResetError):
    code = 'mounted-hop-candidate-probe-invalid'


def require(ok, message):
    if not ok:
        raise HopCandidateProbeError(message)


def linked_identity(root):
    """Exact linked bodies used by both live collection and independent replay."""
    from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
    path = root/'build/overworld_mount_overlay_linked.o'
    result = dict(stateAddress=STATE_ADDRESS, stateBytes=STATE_BYTES)
    for name in (LANDING, SEARCH):
        address, size = _elf_function_extent(path, name)
        code = _elf_code(path, address, size)
        require(16 <= size <= 16384 and len(code) == size,
                'Hop linked function extent differs: '+name)
        result[name] = dict(address=address, size=size,
                            sha256=hashlib.sha256(code).hexdigest())
    return result


def authenticate(session):
    from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
    rt = session.rt
    require(rt.linked_symbol(rt.MOUNT_SYMBOLS, 'sOverworldMountState') == STATE_ADDRESS,
            'Hop mounted state address differs')
    path = rt.REPO/'build/overworld_mount_overlay_linked.o'
    result = linked_identity(rt.REPO)
    for name in (LANDING, SEARCH):
        address, size = result[name]['address'], result[name]['size']
        code = _elf_code(path, address, size)
        require(address == rt.linked_symbol(rt.MOUNT_SYMBOLS, name) & ~1
                and 16 <= size <= 16384 and len(code) == size
                and session.packaged_code(address, size) == code
                and session.read(address, size) == code, 'Hop whole linked/package/live body differs: '+name)
        if name == LANDING:
            require(session.target('mount_hop_landing') == address, 'Hop native landing target differs')
    return result


def candidate_order(origin, profile):
    """The current search order for UP; profile remains an observed input."""
    direction_mode = profile[19] & 0x03
    require(len(profile) == 72 and direction_mode in (0, 1, 2), 'invalid mounted Hop profile')
    minimum = profile[20] or 1
    maximum = min(16, max(minimum, profile[21]))
    require(1 <= minimum <= maximum, 'Hop profile has no bounded distance')
    x, y = origin
    require(all(type(v) is int and maximum <= v <= 0x7FFF-maximum for v in origin),
            'Hop origin cannot contain bounded candidates')
    rows = []
    for lateral in range(maximum+1):
        for distance in range(maximum, minimum-1, -1):
            magnitude = distance if lateral == maximum else lateral
            if lateral != maximum and magnitude >= distance:
                continue
            if magnitude == 0 and direction_mode == 2 or magnitude != 0 and direction_mode == 0:
                continue
            for side in (1,) if magnitude == 0 else (1, -1):
                rows.append(dict(kind='straight' if not magnitude else 'equal' if magnitude == distance else 'near',
                    distance=distance, lateral=magnitude*side, target=[x+magnitude*side, y-distance]))
    require(0 < len(rows) <= MAX_QUERIES, 'Hop candidate count exceeds bound')
    return minimum, maximum, rows


class MountedHopCandidateProbe:
    def __init__(self, session, subject):
        self.session = session
        # Existing idle policy guard only. Never dispatch RESET or edit a lane.
        require(session.prepared is True and not session.native_bridge_active
                and session.rom.resolve().parent == session.directory.resolve()
                and session.save.resolve().parent == session.directory.resolve(), 'Hop probe needs private prepared session')
        self.owner = (session.emu, session.directory.resolve(), session.rom, session.save, session.rom_hash, session.save_hash)
        self.reset = WalkPolicyReset(session, subject)
        self.identity = authenticate_mount(session)
        ready = self.reset._capture()
        raw = session.read(STATE_ADDRESS, STATE_BYTES)
        require(len(raw) == STATE_BYTES, 'incomplete mounted state')
        actor = ready['actor']; source = actor['sourceIdentity']; context = ready['snapshot']['context']
        field, surface = struct.unpack_from('<II', raw)
        binding = struct.unpack_from('<IHHHHBBBB', raw, 80)
        require(field == self.reset.field and surface % 2 == 0 and 0x02000000 <= surface <= 0x023FFFFC
                and binding[:7] == (source['personality'], actor['species'], context['mapId'],
                    actor['handle']['mapGeneration'], actor['handle']['encounterGeneration'], actor['form'], actor['level'])
                and binding[7] < 6, 'mounted Hop binding differs')
        require(struct.unpack_from('<I',raw,96)[0] > 0 and tuple(raw[100:104]) == (2,0,0,0)
                and raw[122] == 1 and not any(raw[i] for i in (120,123,128,148,149,150,151,180,182,183)),
                'mounted Hop is not idle')
        self.initial = dict(readiness=ready, mountStateHex=raw.hex(), profileHex=raw[8:80].hex())
        actor = self.initial['readiness']['actor']
        require(actor['species'] == 56 and actor['role'] == 'MOUNTED' and actor['handle']['slot'] == 7
                and actor.get('presentationAttached') is True
                and actor['engineIdentity'].get('anchorInCurrentManager') is True,
                'Hop probe requires current mounted Mankey')
        self.profile = bytes.fromhex(self.initial['profileHex'])
        require(self.profile[12] == 2, 'mounted profile does not use Hop')
        pose = self.initial['readiness']['snapshot']['player']
        self.origin = [pose['x'], pose['y']]
        self.minimum, self.maximum, self.targets = candidate_order(self.origin, self.profile)
        self.service = authenticate(session)
        self.started = False

    def _capture(self):
        s = self.session
        require(s.prepared is True and s.native_bridge_active is True and self.owner ==
                (s.emu, s.directory.resolve(), s.rom, s.save, s.rom_hash, s.save_hash),
                'Hop probe lost prepared bridge/session owner')
        require(authenticate_mount(s) == self.identity and authenticate(s) == self.service,
                'Hop probe code owner changed')
        ready = self.reset._capture()
        raw = s.read(STATE_ADDRESS, STATE_BYTES)
        require(raw.hex() == self.initial['mountStateHex'], 'Hop mounted state/profile changed')
        initial = self.initial['readiness']
        require(ready['actor'] == initial['actor'], 'Hop actor changed at bridge entry')
        require(ready['snapshot']['player'] == initial['snapshot']['player'], 'Hop player changed at bridge entry')
        return dict(frame=s.completed_frames, actor=deepcopy(ready['actor']),
            player=deepcopy(ready['snapshot']['player']), inputs=deepcopy(ready['inputs']),
            stateHex=ready['state'].hex(), mountStateHex=raw.hex())

    def recipe(self, scratch, call):
        require(not self.started, 'Hop query is single-use')
        self.started = True
        require(scratch == self.session.native_trampoline['address']+0x200, 'Hop scratch is not bridge-owned')
        before = self._capture()
        rows = []
        for target in self.targets:
            result = yield call('mount_hop_landing', tuple(target['target']))
            after = self._capture()
            require(after == before, 'Hop query advanced a game frame or changed actor/policy/input/state')
            require(type(result) is int and result in (0, 1), 'Hop landing returned a non-BOOL')
            rows.append(dict(deepcopy(target), result=result))
        # Detached JSON-shaped values: callers cannot mutate the probe baseline.
        return deepcopy(dict(completed=True, prepared=True, acceptedProof=False,
            scope='prepared-mounted-hop-candidate-query', subject=self.reset.subject,
            direction='UP', origin=self.origin, profileHex=self.profile.hex(), minDistance=self.minimum,
            maxDistance=self.maximum, serviceIdentity=self.service, before=before, after=after, rows=rows,
            orderedNearTargets=[r['target'] for r in rows if r['kind']=='near' and r['result']==1],
            equalDiagonalTargets=[r['target'] for r in rows if r['kind']=='equal' and r['result']==1],
            batchAdvancedFrames=0, guestMemoryWrites=0,
            limits='Native landing queries only; actual candidate selection requires normal input afterward'))

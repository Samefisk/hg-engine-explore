"""Eight fixed native corner queries; prepared arrangement, never movement proof."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_mount_walk_fixture import (
    MountWalkFixture, STATE_ADDRESS, STATE_BYTES, authenticate_mount)
from tools.overworld.devtools_walk_reset import WalkResetError

COLLISION_ADDRESS, COLLISION_BYTES = 0x0205DA34, 0x74
LANDING_ENTRY, LANDING_ENTRY_BYTES, LANDING_OFFSET = 0x023CD000, 40, 28
TERRAIN_OFFSET = 32
BRIDGE_HOUSEKEEPING_FLAGS = 0x400004
DIAGONALS = ((4, -1, -1, 0, 2), (5, 1, -1, 0, 3),
             (6, -1, 1, 1, 2), (7, 1, 1, 1, 3))


class CornerProbeError(WalkResetError):
    code = "corner-probe-invalid"


def require(ok, message):
    if not ok:
        raise CornerProbeError(message)


def changed_leaves(before, after, path=""):
    """Bounded diagnostic paths; never relax an ownership comparison."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            result.extend(changed_leaves(before.get(key), after.get(key),
                                         f"{path}.{key}" if path else key))
            if len(result) >= 12:
                return result[:12]
        return result
    return [] if before == after else [path]


def authenticate(session):
    from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
    rt = session.rt
    require(session.target("corner_collision") == COLLISION_ADDRESS,
            "corner stock collision target differs")
    stock = (rt.REPO / "base/arm9.bin").read_bytes()
    expected = stock[COLLISION_ADDRESS - 0x02000000:COLLISION_ADDRESS - 0x02000000 + COLLISION_BYTES]
    base, arm9 = session.arm9_code_region
    packaged = arm9[COLLISION_ADDRESS - base:COLLISION_ADDRESS - base + COLLISION_BYTES]
    require(len(expected) == COLLISION_BYTES and packaged == expected
            and session.read(COLLISION_ADDRESS, COLLISION_BYTES) == expected,
            "corner stock collision whole body differs from exact ARM9 package")
    linked = rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
    symbol = "OverworldWildSpawns_ValidateHopLandingValue"
    address, size = _elf_function_extent(linked, symbol)
    require(address == session.target("corner_landing")
            == rt.linked_symbol(rt.WILD_SYMBOLS, symbol) & ~1
            and 16 <= size <= 16384, "corner landing linked extent differs")
    code = _elf_code(linked, address, size)
    require(len(code) == size and session.packaged_code(address, size) == code,
            "corner landing whole body differs from linked package")
    require(rt.linked_symbol(rt.WILD_SYMBOLS, "gOverworldWildSpawnsOverlayEntry") == LANDING_ENTRY,
            "corner landing public entry address differs")
    entry = _elf_code(linked, LANDING_ENTRY, LANDING_ENTRY_BYTES)
    require(len(entry) == LANDING_ENTRY_BYTES
            and session.packaged_code(LANDING_ENTRY, LANDING_ENTRY_BYTES) == entry
            and struct.unpack_from("<I", entry, LANDING_OFFSET)[0] == address | 1,
            "corner landing public callback differs")
    return dict(collisionAddress=COLLISION_ADDRESS, collisionSize=COLLISION_BYTES,
                collisionSha256=hashlib.sha256(expected).hexdigest(), landingAddress=address,
                landingSize=size, landingSha256=hashlib.sha256(code).hexdigest(), entryHex=entry.hex())


class CornerProbe:
    def __init__(self, session, subject):
        self.session = session
        # This object supplies guards only. Neither fixture.run nor RESET runs.
        self.fixture = MountWalkFixture(session, subject, 0)
        self.initial = self.fixture._capture()
        actor = self.initial["readiness"]["actor"]
        require(actor["species"] == 155, "corner fixture requires mounted Cyndaquil")
        self.service = authenticate(session)
        self.started = False

    def _capture(self):
        s, f = self.session, self.fixture
        require(s.prepared is True and s.native_bridge_active is True and f.owner ==
                (s.emu, s.directory.resolve(), s.rom, s.save, s.rom_hash, s.save_hash),
                "corner query lost its prepared bridge/session owner")
        require(authenticate_mount(s) == f.identity and authenticate(s) == self.service,
                "corner query code owner changed")
        ready = f.reset._capture()
        raw = s.read(STATE_ADDRESS, STATE_BYTES)
        require(raw.hex() == self.initial["mountStateHex"], "corner mounted state/profile changed")
        actor, initial = ready["actor"], self.initial["readiness"]["actor"]
        initial_player = self.initial["readiness"]["snapshot"]["player"]
        player_pose = ready["snapshot"]["player"]
        # Reaching the native poll is setup and may run field housekeeping.
        # RESET validates idle flags at both boundaries. Freeze the complete
        # flags at query entry below, not at the earlier paused host boundary.
        require((initial_player["flags"] ^ player_pose["flags"])
                & ~BRIDGE_HOUSEKEEPING_FLAGS == 0,
                "corner bridge arrival changed flags beyond observed field housekeeping")
        changes = changed_leaves(initial, actor, "actor") + changed_leaves(
            {k: v for k, v in initial_player.items() if k != "flags"},
            {k: v for k, v in player_pose.items() if k != "flags"}, "player")
        require(not changes, "corner actor or player changed: " + ", ".join(changes[:12]))
        avatar = struct.unpack("<I", s.read(f.reset.field + 0x40, 4))[0]
        require(avatar % 4 == 0 and 0x02000000 <= avatar <= 0x023FFFC0,
                "corner player avatar pointer is invalid")
        avatar_bytes = s.read(avatar, 64)
        player = struct.unpack_from("<I", avatar_bytes, 0x30)[0]
        require(player == actor["engineIdentity"]["anchorPointer"]
                and player == s.rt.player_ptr(s.emu), "corner avatar does not own current player anchor")
        mask = struct.unpack_from("<H", raw, 8 + TERRAIN_OFFSET)[0]
        require(mask != 0 and not mask & 0x8000, "corner destination mask is empty or includes side checks")
        pose = ready["snapshot"]["player"]
        require(all(type(pose[k]) is int and 1 <= pose[k] <= 0x7FFE for k in ("x", "y")),
                "corner origin cannot contain all eight neighbors")
        return dict(readiness=ready, mountStateHex=raw.hex(), avatar=avatar,
                    avatarHex=avatar_bytes.hex(), player=player, mask=mask,
                    playerFlags=pose["flags"],
                    origin=[pose["x"], pose["y"]], frame=s.completed_frames)

    @staticmethod
    def _public(value):
        return {k: deepcopy(value[k]) for k in
                ("origin", "frame", "avatar", "player", "playerFlags", "mask", "mountStateHex", "avatarHex")}

    def recipe(self, scratch, call):
        require(not self.started, "corner query is single-use")
        self.started = True
        require(scratch == self.session.native_trampoline["address"] + 0x200,
                "corner query scratch is not bridge-owned")
        before = self._capture()
        # Native cycles may advance to execute BLX, but no game update may
        # complete between these eight calls. Bridge entry/exit remains setup.
        stable = {k: v for k, v in before.items() if k != "readiness"}
        def check():
            after = self._capture()
            require({k: v for k, v in after.items() if k != "readiness"} == stable
                    and after["readiness"]["state"] == before["readiness"]["state"]
                    and after["readiness"]["inputs"] == before["readiness"]["inputs"],
                    "corner query advanced a game update or changed actor/policy/input")
            return after
        cardinals, diagonals = [], []
        for direction in range(4):
            result = yield call("corner_collision", (before["avatar"], before["player"], direction))
            after = check()
            require(type(result) is int and 0 <= result <= 0x2F and not result & 0x10,
                    "corner stock collision returned an unknown mask")
            cardinals.append(dict(direction=direction, result=result, open=result == 0))
        x, y = before["origin"]
        for direction, dx, dy, vertical, horizontal in DIAGONALS:
            target = (x + dx, y + dy)
            result = yield call("corner_landing", (1, 7, self.fixture.reset.field, before["mask"],
                                                   *target, *target))
            after = check()
            require(type(result) is int and result in (0, 1), "corner landing returned a non-BOOL")
            blocked = sum(not cardinals[d]["open"] for d in (vertical, horizontal))
            diagonals.append(dict(direction=direction, target=list(target), result=result,
                                  destinationOpen=bool(result), sideDirections=[vertical, horizontal],
                                  blockedSides=blocked, oneSideCorner=bool(result) and blocked == 1))
        return dict(completed=True, prepared=True, acceptedProof=False,
                    scope="prepared-mounted-corner-query", subject=deepcopy(before["readiness"]["subject"]),
                    serviceIdentity=deepcopy(self.service), before=self._public(before), after=self._public(after),
                    cardinals=cardinals, diagonals=diagonals, batchAdvancedFrames=0,
                    preBridgePlayerFlags=self.initial["readiness"]["snapshot"]["player"]["flags"],
                    limits="Native setup queries only; bridge arrival/exit is setup, not normal movement proof")

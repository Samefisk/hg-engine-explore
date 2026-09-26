"""Bounded idle mounted Owner edits in a private prepared session, never proof."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_walk_reset import WalkPolicyReset, WalkResetError

STATE_ADDRESS, STATE_BYTES = 0x023BC744, 184
ENTRY_ADDRESS, PROFILE_OFFSET, PROFILE_BYTES = 0x023BB600, 8, 72
DIRECTION_OFFSET, TRAVEL_OFFSET, ACCEL_OFFSET, FASTEST_OFFSET = 19, 7, 50, 51
STOMP_OFFSET = 70
OPTIONS_OFFSET = 65


class MountWalkFixtureError(WalkResetError):
    code = "mount-walk-fixture-invalid"


def require(ok, message):
    if not ok:
        raise MountWalkFixtureError(message)


def authenticate_mount(session):
    from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
    rt = session.rt
    linked = rt.REPO / "build/overworld_mount_overlay_linked.o"
    state = rt.linked_symbol(rt.MOUNT_SYMBOLS, "sOverworldMountState")
    require(state == STATE_ADDRESS, "mounted state linked address differs")
    address, size = _elf_function_extent(linked, "OverworldMount_Begin")
    require(address == rt.linked_symbol(rt.MOUNT_SYMBOLS, "OverworldMount_Begin") & ~1
            and 32 <= size <= 16384, "mounted Begin linked extent differs")
    code = _elf_code(linked, address, size)
    require(len(code) == size and session.packaged_code(address, size) == code,
            "mounted Begin differs from linked/package code")
    entry = session.packaged_code(ENTRY_ADDRESS, 32)
    require(len(entry) == 32 and struct.unpack_from("<IHHI", entry) ==
            (0x544E554D, 11, 32, address | 1), "mounted entry ABI/callback differs")
    # Begin copies the Owner and binding into this exact fixed allocation.
    require(struct.pack("<I", state) in code, "mounted Begin lacks linked state anchor")
    return dict(stateAddress=state, stateBytes=STATE_BYTES, entryHex=entry.hex(),
                beginAddress=address, beginSize=size, beginSha256=hashlib.sha256(code).hexdigest())


class MountWalkFixture:
    def __init__(self, session, subject, direction_mode, travel_time=None, stomp_time=None,
                 *, turning=None, crash_sound=None):
        require(type(direction_mode) is int and 0 <= direction_mode <= 2,
                "directionMode must be an integer 0..2")
        require(travel_time is None or type(travel_time) is int and 1 <= travel_time <= 32,
                "travelTime must be an integer 1..32")
        require(stomp_time is None or type(stomp_time) is int and 0 <= stomp_time <= 32,
                "stompTime must be an integer 0..32")
        self.session, self.direction_mode, self.travel_time = session, direction_mode, travel_time
        self.stomp_time = stomp_time
        require(turning is None or turning in ('free', 'locked'), "turning must be free or locked")
        require(crash_sound is None or crash_sound in ('none', 'wall-hit'),
                "crashSound must be none or wall-hit")
        self.turning, self.crash_sound = turning, crash_sound
        require(session.prepared is True and not session.native_bridge_active,
                "fixture requires a paused prepared private session")
        # DevtoolsSession owns copies; do not accept a source ROM/save path.
        directory = session.directory.resolve()
        require(session.rom.resolve().parent == directory and session.save.resolve().parent == directory
                and session.rom != session.save and directory != session.rt.REPO.resolve(),
                "fixture requires private session ROM/save copies")
        self.owner = (session.emu, directory, session.rom, session.save, session.rom_hash, session.save_hash)
        self.reset = WalkPolicyReset(session, subject)  # readiness only; never call recipe()
        self.identity = authenticate_mount(session)
        self.started, self.receipt = False, None

    def _clock(self):
        s = self.session
        return dict(frame=s.completed_frames, nativeCycle=s.rt.EXECUTED_FRAME_COUNT)

    def _capture(self):
        s = self.session
        require(s.prepared is True and not s.native_bridge_active and self.owner ==
                (s.emu, s.directory.resolve(), s.rom, s.save, s.rom_hash, s.save_hash),
                "fixture session owner changed")
        require(authenticate_mount(s) == self.identity, "fixture mounted code changed")
        ready = self.reset._capture()
        actor, context = ready["actor"], ready["snapshot"]["context"]
        require(actor["role"] == "MOUNTED" and actor["handle"]["slot"] == 7
                and actor.get("presentationAttached") is True
                and actor["engineIdentity"].get("anchorInCurrentManager") is True,
                "fixture needs the current attached mounted actor and player anchor")
        raw = s.read(STATE_ADDRESS, STATE_BYTES)
        require(len(raw) == STATE_BYTES, "fixture mounted state read is incomplete")
        require(raw[PROFILE_OFFSET + 12] == 1, "fixture requires mounted Walk locomotion")
        field, surface = struct.unpack_from("<II", raw)
        binding = struct.unpack_from("<IHHHHBBBB", raw, 80)
        source = actor["sourceIdentity"]
        require(field == self.reset.field and surface % 2 == 0
                and 0x02000000 <= surface <= 0x023FFFFC,
                "fixture mounted field/surface owner differs")
        require(binding[:6] == (source["personality"], actor["species"], context["mapId"],
                actor["handle"]["mapGeneration"], actor["handle"]["encounterGeneration"], actor["form"])
                and binding[6] == actor["level"] and binding[7] < 6,
                "fixture mounted binding differs from live subject")
        generation, phase, cancel, motion, reserved = struct.unpack_from("<IBBBB", raw, 96)
        pending = {i: raw[i] for i in (120, 123, 128, 148, 149, 150, 151, 180, 182, 183) if raw[i]}
        require(generation > 0 and (phase, cancel, motion, reserved) == (3, 0, 0, 0)
                and raw[122] == 1 and not pending,
                "fixture mounted motion/input/stream state is not idle: "
                + str(dict(generation=generation, phase=phase, cancel=cancel, motion=motion,
                           reserved=reserved, attached=raw[122], nonzeroBytes=pending)))
        return dict(readiness=ready, mountStateHex=raw.hex(), profileHex=raw[8:80].hex(),
                    bindingHex=raw[80:96].hex(), sessionGeneration=generation, clock=self._clock())

    @staticmethod
    def _public(value):
        result = deepcopy(value)
        for key in ("state", "policyOffset"):
            result["readiness"].pop(key, None)
        # The selected actor is already retained separately. Do not duplicate
        # every unrelated actor and its terrain grid in each setup receipt.
        snapshot = result["readiness"]["snapshot"]
        result["readiness"]["snapshot"] = {key: snapshot.get(key) for key in
            ("frame", "nativeCycle", "actorFrame", "context", "player")}
        return result

    def run(self):
        require(not self.started, "fixture is single-use")
        self.started = True
        before = self._capture()
        original = bytes.fromhex(before["mountStateHex"])
        expected = bytearray(original)
        changes = {DIRECTION_OFFSET: self.direction_mode}
        if self.travel_time is not None:
            changes.update({TRAVEL_OFFSET: self.travel_time, FASTEST_OFFSET: self.travel_time, ACCEL_OFFSET: 0})
        if self.stomp_time is not None:
            changes[STOMP_OFFSET] = self.stomp_time
        if self.turning is not None or self.crash_sound is not None:
            options = original[PROFILE_OFFSET + OPTIONS_OFFSET]
            if self.turning is not None:
                options = (options & ~1) | int(self.turning == 'locked')
            if self.crash_sound is not None:
                options = (options & ~16) | (16 if self.crash_sound == 'wall-hit' else 0)
            changes[OPTIONS_OFFSET] = options
        for offset, value in changes.items():
            expected[PROFILE_OFFSET + offset] = value
        self.receipt = dict(completed=False, prepared=True, acceptedProof=False,
            scope="prepared-idle-mounted-walk-fixture", subject=deepcopy(before["readiness"]["subject"]),
            mountIdentity=deepcopy(self.identity), policyServiceIdentity=deepcopy(self.reset.service),
            directionMode=self.direction_mode, travelTime=self.travel_time, changedOffsets=sorted(changes),
            before=self._public(before), expectedStateHex=bytes(expected).hex(), after=None,
            restoredOnError=None, guestAdvanced=False,
            limits="Private mounted Owner fixture only; no normal resolved-profile or gameplay proof")
        if self.stomp_time is not None:
            self.receipt["stompTime"] = self.stomp_time
        if self.turning is not None:
            self.receipt["turning"] = self.turning
        if self.crash_sound is not None:
            self.receipt["crashSound"] = self.crash_sound
        try:
            # Write only the named bytes, never the containing state allocation.
            for offset, value in changes.items():
                self.session.write(STATE_ADDRESS + PROFILE_OFFSET + offset, bytes((value,)))
            after = self._capture()
            self.receipt["after"] = self._public(after)
            require(after["mountStateHex"] == bytes(expected).hex(), "fixture changed unexpected mounted bytes")
            require(after["readiness"] == before["readiness"] and after["clock"] == before["clock"],
                    "fixture changed actor/policy/input/clock")
            self.receipt["completed"] = True
            return deepcopy(self.receipt)
        except Exception as error:
            self.receipt["failure"] = str(error)
            try:
                self.receipt["failedStateHex"] = self.session.read(STATE_ADDRESS, STATE_BYTES).hex()
                self.receipt["failedClock"] = self._clock()
            except Exception as read_error:
                self.receipt["failedReadError"] = str(read_error)
            try:
                for offset in changes:
                    self.session.write(STATE_ADDRESS + PROFILE_OFFSET + offset,
                                       original[PROFILE_OFFSET + offset:PROFILE_OFFSET + offset + 1])
                restored = self._capture()
                self.receipt["restoredOnError"] = self._public(restored)
                require(restored == before, "fixture rollback or owner/clock verification differs")
            except Exception as rollback:
                fatal = MountWalkFixtureError("fixture rollback unverified: " + str(rollback), fatal=True)
                fatal.receipt = deepcopy(self.receipt)
                self.session.abort_native_control(fatal)
                raise fatal from error
            error.receipt = deepcopy(self.receipt)
            raise

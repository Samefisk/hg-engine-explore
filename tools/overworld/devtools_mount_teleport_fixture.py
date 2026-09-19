"""Three named idle mounted lane edits for a private Teleport timing fixture."""
from copy import deepcopy
import struct

from tools.overworld.devtools_mount_walk_fixture import (
    MountWalkFixture, MountWalkFixtureError, authenticate_mount,
    STATE_ADDRESS, STATE_BYTES, PROFILE_OFFSET,
)


class MountTeleportFixtureError(MountWalkFixtureError):
    code = "mount-teleport-fixture-invalid"


def require(ok, message):
    if not ok:
        raise MountTeleportFixtureError(message)


class MountTeleportFixture(MountWalkFixture):
    def __init__(self, session, subject, locomotion, teleport_time, teleport_pause):
        require(type(locomotion) is int and locomotion in (6, 9, 10, 11),
                "locomotion must be 6, 9, 10 or 11")
        require(type(teleport_time) is int and 1 <= teleport_time <= 32,
                "teleportTime must be an integer 1..32")
        require(type(teleport_pause) is int and 0 <= teleport_pause <= 255,
                "teleportPause must be an integer 0..255")
        # Reuse private ownership, package authentication and idle readiness.
        # The Walk constructor does not edit or dispatch a movement reducer.
        super().__init__(session, subject, 0)
        self.locomotion = locomotion
        self.teleport_time = teleport_time
        self.teleport_pause = teleport_pause

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
        require(raw[PROFILE_OFFSET + 12] in (1, 6, 9, 10, 11),
                "fixture requires mounted Walk or Teleport locomotion")
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
        require(generation > 0 and (phase, cancel, motion, reserved) == (2, 0, 0, 0)
                and raw[122] == 1 and not pending,
                "fixture mounted motion/input/stream state is not idle: "
                + str(dict(generation=generation, phase=phase, cancel=cancel, motion=motion,
                           reserved=reserved, attached=raw[122], nonzeroBytes=pending)))
        return dict(readiness=ready, mountStateHex=raw.hex(), profileHex=raw[8:80].hex(),
                    bindingHex=raw[80:96].hex(), sessionGeneration=generation, clock=self._clock())

    def run(self):
        require(not self.started, "fixture is single-use")
        self.started = True
        before = self._capture()
        original = bytes.fromhex(before["mountStateHex"])
        expected = bytearray(original)
        changes = {12: self.locomotion, 23: self.teleport_time, 24: self.teleport_pause}
        for offset, value in changes.items():
            expected[PROFILE_OFFSET + offset] = value
        self.receipt = dict(completed=False, prepared=True, acceptedProof=False,
            scope="prepared-idle-mounted-teleport-fixture", subject=deepcopy(before["readiness"]["subject"]),
            mountIdentity=deepcopy(self.identity), policyServiceIdentity=deepcopy(self.reset.service),
            locomotion=self.locomotion, teleportTime=self.teleport_time,
            teleportPause=self.teleport_pause, changedOffsets=sorted(changes),
            before=self._public(before), expectedStateHex=bytes(expected).hex(), after=None,
            restoredOnError=None, guestAdvanced=False,
            loadedWarps=(self.session.rt.loaded_warp_events(self.session.emu)
                         if hasattr(self.session.rt, "loaded_warp_events") else []),
            limits="Private mounted Owner fixture only; no normal resolved-profile or gameplay proof")
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
                fatal = MountTeleportFixtureError("fixture rollback unverified: " + str(rollback), fatal=True)
                fatal.receipt = deepcopy(self.receipt)
                self.session.abort_native_control(fatal)
                raise fatal from error
            error.receipt = deepcopy(self.receipt)
            raise


class MountTeleportRestoreFixture(MountTeleportFixture):
    """Restore only the original three bytes retained by this session."""
    def __init__(self, session, subject, original_profile):
        super().__init__(session, subject, 9, 7, 0)
        require(isinstance(original_profile, bytes) and len(original_profile) == 72
                and original_profile[12] == 1, "restore needs the original Walk profile")
        self.original_profile = original_profile
        self.locomotion = original_profile[12]
        self.teleport_time = original_profile[23]
        self.teleport_pause = original_profile[24]

    def _capture(self):
        value = super()._capture()
        current = bytes.fromhex(value["profileHex"])
        require(all(current[i] == self.original_profile[i] for i in range(72)
                    if i not in (12, 23, 24)), "restore profile changed outside fixture bytes")
        return value

"""Opt-in, read-only mounted strict-corner call receipts; not gameplay proof."""
from copy import deepcopy
import struct

from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver
from tools.overworld.devtools_observer import PLAYER_WALK_COLLISION

MAX_CALLS = 128
# include/overworld_motion_model.h. The classifier returns one reason, not a
# combination; old linked diagnostic packages expose the BOOL entry instead.
CANDIDATE_RETURNS = frozenset((0, 1 << 1, 1 << 2, 1 << 5))


def check_corner_policy(value):
    """Check the actual 72-byte mounted lane, including diagonal permission."""
    try:
        raw = bytes.fromhex(value["profileHex"])
        valid = (len(raw) == 72 and type(value["profile19"]) is int
                 and value["profile19"] == raw[19] and raw[19] in (1, 2))
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("mounted direction profile differs")
    return True


class NativeCornerObserver(NativeMountedPacingObserver):
    def __init__(self, session, subject, max_frames):
        super().__init__(session, subject, max_frames)
        self.counts = dict(strict=0, collision=0, landing=0)
        self.receipts, self.active_strict, self.code = [], [], {}
        self.policy_calibration = None
        self.latest_completed = None
        self.strict_function = "OverworldWalk_StrictDiagonalAllowedBody"
        self.return_kind = "bool"
        # Keep inherited owned entry/return tracking, but resolve our own code.
        self.linked = self._linked_corner

    def _linked_corner(self, label, path, symbols, name, before, after, **kwargs):
        address, expected = self.code[name]
        self.observer._tap(label, address, self.session.packaged_code(address, 32),
                           before, after, **kwargs)

    def _authenticate(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        s, rt = self.session, self.session.rt
        path = rt.REPO / "build/pokemon_move_history_overlay_linked.o"
        symbols = rt.linked_symbols(path)
        if "Walk_DiagonalRejection" in symbols:
            self.strict_function = "Walk_DiagonalRejection"
            self.return_kind = "candidate-flags"
        names = {"OverworldWalk_StrictDiagonalAllowed", "OverworldWalk_StrictDiagonalAllowedBody",
                 "Walk_ValidateDiagonalLanding", self.strict_function}
        for name in sorted(names):
            address, size = _elf_function_extent(path, name)
            self._require(address == rt.linked_symbol(symbols, name) & ~1, "linked function differs")
            expected = self.observer.elf_code(path, address, size)
            self._require(len(expected) == size and s.packaged_code(address, size) == expected,
                          "full linked corner body differs: " + name)
            self.code[name] = (address, expected)
        # Stock unk_0205CB48.s sub_0205DA34 ends before sub_0205DAA8.
        address, size = PLAYER_WALK_COLLISION, 0x74
        expected = (rt.REPO / "build/arm9.bin").read_bytes()[address-0x02000000:address-0x02000000+size]
        self._require(len(expected) == size and s.packaged_code(address, size) == expected,
                      "full stock cardinal collision body differs")
        self.code["stockCollision"] = (address, expected)
        self.mount_state = rt.linked_symbol(rt.MOUNT_SYMBOLS, "sOverworldMountState")

    def _live_code(self):
        for name, (address, expected) in self.code.items():
            self._require(self.session.read(address, len(expected)) == expected,
                          "resident full corner body differs: " + name)

    def arm(self):
        self._require(not self.armed and not self.closed, "reader can arm only once")
        self._require(type(self.maximum) is int and 1 <= self.maximum <= 600, "invalid frame limit")
        self.started = self.session.completed_frames
        try:
            self.owner = self._current()
            self._require(self.owner["publicSubject"]["species"] == 155, "corner requires mounted species 155")
            self._authenticate()
            self.armed = True
            # The typed classifier sees the actual caller and BOOL wrapper.
            # Older packages have only the BOOL body. Never hook both paths.
            for kind, name in (("strict", self.strict_function),
                               ("collision", "stockCollision"), ("landing", "Walk_ValidateDiagonalLanding")):
                self._install("walk-corner-" + kind, name,
                              lambda kind=kind: self._entry(kind), self._returned)
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close()
            raise
        return self.result()

    def _mount_binding(self, current):
        raw = self.session.read(self.mount_state, 104)
        self._require(len(raw) == 104, "mount state read incomplete")
        field, surface = struct.unpack_from("<II", raw)
        binding = struct.unpack_from("<IHHHHBBBB", raw, 80)
        actor, source = current["publicSubject"], current["sourceIdentity"]
        self._require(field == current["worldContext"]["fieldPointer"]
                      and surface % 2 == 0 and 0x02000000 <= surface <= 0x023FFFFC,
                      "mount field/surface differs")
        self._require(binding[:7] == (source["personality"], actor["species"],
                      current["worldContext"]["mapId"], actor["handle"]["mapGeneration"],
                      actor["handle"]["encounterGeneration"], actor["form"], actor["level"])
                      and binding[7] < 6, "mount snapshot binding differs")
        generation = struct.unpack_from("<I", raw, 96)[0]
        self._require(generation > 0 and raw[100] == 2 and raw[20] == 1,
                      "mount session/Walk lane differs")
        return dict(bindingHex=raw[80:96].hex(), sessionGeneration=generation,
                    surfacePointer=surface, fieldPointer=field)

    def completed_boundary(self):
        self._check_deadline()
        if self.armed and not self.closed:
            self.latest_completed = dict(current=self._current(), frame=self.session.completed_frames,
                                         **self.observer._clock())

    def _check_deadline(self):
        super()._check_deadline()
        self._require(self.policy_calibration is None,
                      "corner policy calibration cannot resume gameplay")

    def _read_policy(self, current):
        """Same memory read for native entry/return and stopped-guest control."""
        self._require(self.session.rt.unsigned(self.session.emu, self.mount_state)
                      == current["worldContext"]["fieldPointer"], "mount state field differs")
        profile = self.session.read(self.mount_state + 8, 72)
        self._require(len(profile) == 72, "mounted direction profile read incomplete")
        return dict(profileHex=profile.hex(), profile19=profile[19] & 0x03)

    def _checked_policy(self, current):
        value = self._read_policy(current)
        try:
            check_corner_policy(value)
        except ValueError as error:
            self._require(False, str(error))
        return value

    def _entry(self, kind):
        if kind != "strict" and not self.active_strict:
            return None
        self._check_deadline()
        self._live_code()
        current = self._current()
        regs = self.session.emu.memory.register_arm9
        rt, emu = self.session.rt, self.session.emu
        state = self.mount_state
        self._require(rt.unsigned(emu, state) == current["worldContext"]["fieldPointer"],
                      "mount state field differs")
        policy = self._checked_policy(current)
        value = dict(kind=kind, before=current, entryClock=self.observer._clock(),
                     completedFrame=self.session.completed_frames,
                     input=deepcopy(self.session._selector_observation()),
                     **policy, statePointer=state,
                     avatarPointer=current["avatarPointer"], playerPointer=current["playerPointer"],
                     mountBinding=self._mount_binding(current),
                     playerPose=rt.object_state(emu, current["playerPointer"]))
        if kind == "strict":
            self._require(not self.active_strict and self.counts[kind] < MAX_CALLS, "strict call bound/nesting differs")
            self._require(regs.r0 == state and regs.r1 == current["avatarPointer"] and 4 <= regs.r2 <= 7,
                          "strict arguments differ")
            origin = rt.object_state(emu, current["playerPointer"])
            direction = regs.r2
            value.update(direction=direction, origin=dict(x=origin["x"], y=origin["y"]),
                         target=dict(x=origin["x"] + (1 if direction & 1 else -1),
                                     y=origin["y"] + (1 if direction >= 6 else -1)),
                         collisions=[], landings=[])
            self.active_strict.append(value)
        else:
            parent = self.active_strict[-1]
            self._require(current == parent["before"] and policy["profileHex"] == parent["profileHex"],
                          "nested owner/profile differs")
            value["parent"] = parent
            if kind == "collision":
                self._require(regs.r0 == current["avatarPointer"] and regs.r1 == current["playerPointer"]
                              and 0 <= regs.r2 <= 3 and len(parent["collisions"]) < 2,
                              "cardinal arguments/bound differ")
                value["direction"] = regs.r2
            else:
                signed = lambda n: (n & 0xFFFFFFFF) - (0x100000000 if n & 0x80000000 else 0)
                target = dict(x=signed(regs.r1), y=signed(regs.r2))
                self._require(regs.r0 == state and target == parent["target"] and not parent["landings"],
                              "landing arguments/bound differ")
                value["target"] = target
        self.counts[kind] += 1
        self.data.append(value)
        return value

    def _returned(self, value, context):
        try:
            self._check_deadline()
            self._live_code()
            self._require(self._current() == value["before"], "corner return owner/context differs")
            self._require(self._mount_binding(value["before"]) == value["mountBinding"],
                          "corner return mounted binding differs")
            self._require(self.session.rt.object_state(self.session.emu, value["playerPointer"])
                          == value["playerPose"], "corner query changed player pose")
            self._require(self._checked_policy(value["before"])["profileHex"] == value["profileHex"],
                          "corner return profile differs")
            result = {k: deepcopy(v) for k, v in value.items() if k != "parent"}
            result.update(returnClock=context["returned"], returnValue=context["returnValue"],
                          normalReturn=True)
            if value["kind"] == "collision":
                self._require(type(context["returnValue"]) is int and context["returnValue"] & ~0x2F == 0,
                              "stock collision mask invalid")
                result["rawMask"] = context["returnValue"]
                value["parent"]["collisions"].append(result)
            else:
                raw = context["returnValue"]
                if value["kind"] == "strict" and self.return_kind == "candidate-flags":
                    self._require(type(raw) is int and raw in CANDIDATE_RETURNS,
                                  "corner classifier return is not a known candidate reason")
                    result.update(returnKind=self.return_kind, rawReturnValue=raw, returnValue=int(raw == 0))
                else:
                    self._require(type(raw) is int and raw in (0, 1), "corner return is not BOOL")
                    if value["kind"] == "strict":
                        result.update(returnKind=self.return_kind, rawReturnValue=raw)
                if value["kind"] == "landing":
                    value["parent"]["landings"].append(result)
                else:
                    self._require(self.active_strict == [value] and len(self.data) == 1,
                                  "strict returned with pending nested call")
                    self.active_strict.pop()
                    self.receipts.append(result)
            return result
        except Exception as error:
            self.failure = self.failure or str(error)
            raise
        finally:
            if value in self.data:
                self.data.remove(value)

    def result(self):
        return deepcopy(dict(armed=self.armed, closed=self.closed, failure=self.failure,
                             subject=self.subject, startFrame=self.started, maxFrames=self.maximum,
                             maxCalls=MAX_CALLS, counts=self.counts, calls=self.receipts,
                             guestMemoryWrites=(self.policy_calibration or {}).get("guestMemoryWrites", 0),
                             policyCalibration=deepcopy(self.policy_calibration), acceptedProof=False,
                             latestCompleted=deepcopy(self.latest_completed),
                             strictFunction=self.strict_function, returnKind=self.return_kind,
                             scope="actual strict calls and only nested calls that occurred"))

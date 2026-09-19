"""Bounded Wild direction input, before the normal role/policy/planner call."""
from copy import deepcopy
import struct

from tools.overworld.devtools_observer import public_bytes
from tools.overworld.devtools_records import _subject, GENERATION_FIELDS


class WalkIntentError(RuntimeError):
    code = "walk-intent-invalid"


class NativeWalkIntent:
    def __init__(self, session, subject, direction, max_frames):
        if (not _subject(subject)["species"] or subject["role"] != "WILD"
                or not 0 <= subject["handle"]["slot"] < 6):
            raise ValueError("Walk intent requires an exact bound WILD actor")
        if type(direction) is not int or not 0 <= direction <= 7:
            raise ValueError("Walk intent requires a direction 0..7")
        if type(max_frames) is not int or not 1 <= max_frames <= 600:
            raise ValueError("Walk intent budget must be 1..600 frames")
        self.session, self.subject = session, deepcopy(subject)
        self.direction, self.max_frames = direction, max_frames
        self.start_frame = session.completed_frames
        self.accepted = 0
        self.rows, self.tokens = [], []
        self.failure = None
        self.closed = False
        self.inflight = False
        self.terminal = False

    def fail(self, message):
        self.failure = self.failure or str(message)
        self.session.abort_native_control(WalkIntentError(self.failure))
        raise WalkIntentError(self.failure)

    def current(self):
        s = self.session
        if self.closed or self.failure or s.native_bridge_active:
            raise WalkIntentError("Walk intent scope unavailable")
        if s.completed_frames - self.start_frame > self.max_frames:
            raise WalkIntentError("Walk intent frame budget exceeded")
        actor, source, engine, world = s.native_observation._chain_current(self.subject["handle"]["slot"])
        if (_subject(actor) != _subject(self.subject)
                or any(actor.get(k) != self.subject.get(k) for k in GENERATION_FIELDS)
                or any(engine.get(k) != self.subject["engineIdentity"].get(k) for k in
                       ("pointer", "current_manager", "object_manager", "manager_index"))):
            raise WalkIntentError("Walk intent owner changed")
        return dict(publicSubject=actor, sourceIdentity=source, engineIdentity=engine, worldContext=world,
                    policy=s.rt.movement_policy_state(s.emu, self.subject["handle"]["slot"]))

    def install(self):
        s, o = self.session, self.session.native_observation
        name = "OverworldWildSpawns_TryStartAcceleratedWalkStep"
        address = s.rt.linked_symbol(s.rt.WILD_SYMBOLS, name) & ~1
        code = o.elf_code(s.rt.REPO / "build/overworld_wild_spawns_overlay_linked.o", address, 32)
        before = len(o.tokens)
        o._tap("walk-direction-intent", address, code, self.before, self.after,
               scope=lambda: not self.closed)
        self.tokens = o.tokens[before:]

    def before(self):
        try:
            s, o = self.session, self.session.native_observation
            regs = s.emu.memory.register_arm9
            pointer = regs.r0 & 0xffffffff
            raw = public_bytes(s, pointer, 28)
            if raw[20] != self.subject["handle"]["slot"]:
                return None
            current = self.current()
            state, field, obj, profile, primitives = struct.unpack_from("<5I", raw)
            if (state != s.rt.WILD_STATE or field != s.rt.unsigned(s.emu, s.rt.G_FIELD_SYS_PTR)
                    or obj != current["engineIdentity"]["pointer"]):
                raise WalkIntentError("Walk intent native context owner differs")
            profile_bytes = public_bytes(s, profile, 144)
            resolved = o.profiles.get(current["publicSubject"]["behaviorFingerprint"], {})
            if not resolved.get("resolved") or resolved.get("resultHex", "")[:288] != profile_bytes.hex():
                raise WalkIntentError("Walk intent profile lacks exact native resolver identity")
            # The normal flat-Walk staged-target caller passes NULL here;
            # this routine uses the profile lane, not the optional primitives.
            primitives_bytes = public_bytes(s, primitives, 8) if primitives else None
            if primitives_bytes is not None and resolved["resultHex"][288:304] != primitives_bytes.hex():
                raise WalkIntentError("Walk intent primitives differ from native resolver")
            slot = raw[20]
            spot = 2 if s.rt.unsigned(s.emu, state + 494 + slot, 1) else s.rt.unsigned(s.emu, state + 264 + slot, 1)
            lane_index = 1 if spot == 3 else 0
            lane = profile_bytes[lane_index * 72:(lane_index + 1) * 72]
            direction_mode = lane[19] & 0x03
            if direction_mode not in (0, 1, 2) or (self.direction < 4 and direction_mode == 2) \
                    or (self.direction >= 4 and direction_mode == 0):
                raise WalkIntentError("Walk intent direction is not allowed by the current lane")
            if self.inflight or len(self.rows) >= 64:
                raise WalkIntentError("Walk intent nesting or receipt bound exceeded")
            registers = {"r" + str(i): getattr(regs, "r" + str(i)) & 0xffffffff for i in range(15)}
            if not regs.lr & 1:
                raise WalkIntentError("Walk intent return is not Thumb")
            suppressed = self.accepted >= 7
            value = dict(contextPointer=pointer, contextHex=raw.hex(), profilePointer=profile,
                         profileHex=profile_bytes.hex(), primitivesPointer=primitives,
                         primitivesHex=primitives_bytes.hex() if primitives_bytes is not None else None,
                         laneHex=lane.hex(), laneIndex=lane_index, spotState=spot,
                         before=current, direction=self.direction, suppressed=suppressed,
                         registersBefore=registers, guestMemoryWrites=0)
            if current["publicSubject"].get("motionKind") == "WALK" \
                    and current["publicSubject"].get("motionPhase") in (
                        "PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING"):
                # Even after the seventh start this is not an eighth admission.
                # Forced FALSE here makes the caller reset the settling Walk.
                return None
            if not suppressed and (current["publicSubject"].get("motionKind") != "NONE"
                                   or current["policy"]["pending"] != 0):
                raise WalkIntentError("Walk intent start boundary is not idle")
            self.inflight = True
            if suppressed:
                regs.r0 = 0
                s.emu.memory.set_next_instruction(regs.lr)
            else:
                regs.r1 = self.direction
            value["registersAfter"] = {"r" + str(i): getattr(regs, "r" + str(i)) & 0xffffffff for i in range(15)}
            changed = "r0" if suppressed else "r1"
            if any(value["registersAfter"][key] != number for key, number in registers.items() if key != changed):
                raise WalkIntentError("Walk intent changed preserved register")
            return value
        except Exception as error:
            self.fail(error)

    def after(self, value, context):
        try:
            current = self.current()
            if (public_bytes(self.session, value["contextPointer"], 28).hex() != value["contextHex"]
                    or public_bytes(self.session, value["profilePointer"], 144).hex() != value["profileHex"]
                    or value["primitivesPointer"] and public_bytes(self.session,
                        value["primitivesPointer"], 8).hex() != value["primitivesHex"]):
                raise WalkIntentError("Walk intent context or profile changed during call")
            if value["suppressed"]:
                if context["returnValue"] != 0 or current != value["before"]:
                    raise WalkIntentError("Walk intent suppressed call had side effects")
            else:
                if (context["returnValue"] != 1 or current["publicSubject"].get("motionKind") != "WALK"
                        or current["publicSubject"].get("motionPhase") != "MOVING"
                        or current["policy"]["pending"] != 2):
                    raise WalkIntentError("Walk intent did not start an actual Walk")
                self.accepted += 1
            self.inflight = False
            row = dict(value, after=current, acceptedStarts=self.accepted,
                       entryClock=context["entry"], returnClock=context["returned"], returnValue=context["returnValue"])
            self.rows.append(deepcopy(row))
            return row
        except Exception as error:
            self.fail(error)

    def completed_boundary(self):
        if self.closed:
            return
        try:
            current = self.current()
            if self.accepted == 7 and current["publicSubject"].get("motionKind") == "NONE" \
                    and current["publicSubject"].get("motionPhase") == "IDLE":
                self.terminal = True
        except Exception as error:
            self.fail(error)

    def close(self, *, disposing=False):
        if self.closed:
            return
        if not disposing and (not self.terminal or self.inflight):
            self.fail("Walk intent closed before seventh terminal")
        o = self.session.native_observation
        for token in self.tokens:
            o.hooks.remove(token)
            if token in o.tokens:
                o.tokens.remove(token)
        self.tokens.clear()
        self.closed = True

    def result(self):
        return deepcopy(dict(armed=True, closed=self.closed, failure=self.failure, acceptedStarts=self.accepted,
                             terminal=self.terminal, direction=self.direction, subject=self.subject,
                             calls=self.rows, guestMemoryWrites=0, acceptedProof=False))

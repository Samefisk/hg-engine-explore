"""Bound one Wild obstacle direction choice at the real Walk/Hop gate.

This control changes only the candidate direction register. The game still
decides whether the attempted Walk and obstacle Hop can start.
"""

from copy import deepcopy
import struct

from tools.overworld.devtools_observer import public_bytes
from tools.overworld.devtools_records import _subject, GENERATION_FIELDS


class ObstacleIntentError(RuntimeError):
    code = "obstacle-intent-invalid"


class NativeObstacleIntent:
    LANDINGS = {(580, 397): (582, 397), (582, 397): (584, 397),
                (599, 395): (601, 395)}

    def __init__(self, session, subject, max_frames):
        if _subject(subject)["species"] != 234 or subject["role"] != "WILD":
            raise ValueError("Obstacle intent needs one Wild Stantler")
        if type(max_frames) is not int or not 1 <= max_frames <= 120:
            raise ValueError("Obstacle intent needs a 1..120 frame bound")
        self.session, self.subject = session, deepcopy(subject)
        self.max_frames, self.start_frame = max_frames, session.completed_frames
        self.stage, self.calls, self.tokens = 0, [], []
        self.initial_commit = None
        self.origin = None
        self.failure, self.closed, self.terminal, self.inflight = None, False, False, False

    def fail(self, message):
        self.failure = self.failure or str(message)
        self.session.abort_native_control(ObstacleIntentError(self.failure))
        raise ObstacleIntentError(self.failure)

    def current(self):
        session = self.session
        if self.closed or self.failure or session.native_bridge_active:
            raise ObstacleIntentError("Obstacle intent scope is unavailable")
        public_subject, source, engine, world = session.native_observation._chain_current(
            self.subject["handle"]["slot"])
        actor = session.rt.actor_state(session.emu, self.subject["handle"]["slot"])
        if (_subject(public_subject) != _subject(self.subject)
                or _subject(actor) != _subject(public_subject)
                or any(actor.get(key) != self.subject.get(key) for key in GENERATION_FIELDS)
                or any(engine.get(key) != self.subject["engineIdentity"].get(key)
                       for key in ("pointer", "current_manager", "object_manager", "manager_index"))):
            raise ObstacleIntentError("Obstacle intent owner changed")
        return dict(actor=actor, source=source, engine=engine, world=world)

    def install(self):
        session, observer = self.session, self.session.native_observation
        address = session.rt.linked_symbol(
            session.rt.WILD_SYMBOLS,
            "OverworldWildSpawns_TryStartSingleDirectionMovementStep") & ~1
        code = observer.elf_code(
            session.rt.REPO / "build/overworld_wild_spawns_overlay_linked.o", address, 32)
        before = len(observer.tokens)
        observer._tap("obstacle-direction-intent", address, code, self.before, self.after,
                      scope=lambda: not self.closed)
        self.tokens = observer.tokens[before:]

    def before(self):
        try:
            session, observer = self.session, self.session.native_observation
            regs = session.emu.memory.register_arm9
            pointer = regs.r0 & 0xffffffff
            context = public_bytes(session, pointer, 28)
            if context[20] != self.subject["handle"]["slot"] or self.stage == 1:
                return None
            current = self.current()
            state, field, obj, profile, primitives = struct.unpack_from("<5I", context)
            if (state != session.rt.WILD_STATE
                    or field != session.rt.unsigned(session.emu, session.rt.G_FIELD_SYS_PTR)
                    or obj != current["engine"]["pointer"]):
                raise ObstacleIntentError("Obstacle intent native owner differs")
            profile_bytes = public_bytes(session, profile, 144)
            resolved = observer.profiles.get(current["actor"]["behaviorFingerprint"], {})
            if not resolved.get("resolved") or resolved.get("resultHex", "")[:288] != profile_bytes.hex():
                raise ObstacleIntentError("Obstacle intent profile differs from resolver")
            primitive_bytes = public_bytes(session, primitives, 8) if primitives else None
            if (primitive_bytes is not None
                    and resolved["resultHex"][288:304] != primitive_bytes.hex()):
                raise ObstacleIntentError("Obstacle intent primitives differ from resolver")
            x, y = self.origin
            actor = current["actor"]
            if actor.get("motionKind") != "NONE" or actor.get("motionPhase") != "IDLE":
                return None
            if actor.get("logical") != {"x": x, "y": y}:
                raise ObstacleIntentError("Obstacle intent left the reviewed approach")
            if len(self.calls) >= 32:
                # A rejected direction must fail the bounded test, not flood
                # native receipts or abort the worker.
                return None
            if self.inflight or not regs.lr & 1:
                raise ObstacleIntentError("Obstacle intent nested or entered in ARM mode")
            registers = {f"r{i}": getattr(regs, f"r{i}") & 0xffffffff for i in range(15)}
            self.inflight = True
            regs.r1 = 3  # East over the reviewed middle tile.
            value = dict(stage=self.stage, expectedKind="HOP", contextPointer=pointer,
                         contextHex=context.hex(), profilePointer=profile,
                         profileHex=profile_bytes.hex(), primitivesPointer=primitives,
                         primitivesHex=primitive_bytes.hex() if primitive_bytes else None,
                         before=current, originalDirection=registers["r1"], direction=3,
                         registersBefore=registers,
                         registersAfter={f"r{i}": getattr(regs, f"r{i}") & 0xffffffff
                                         for i in range(15)}, guestMemoryWrites=0)
            if any(value["registersAfter"][key] != number
                   for key, number in registers.items() if key != "r1"):
                raise ObstacleIntentError("Obstacle intent changed a preserved register")
            return value
        except Exception as error:
            self.fail(error)

    def after(self, value, context):
        try:
            session = self.session
            if (public_bytes(session, value["contextPointer"], 28).hex() != value["contextHex"]
                    or public_bytes(session, value["profilePointer"], 144).hex()
                    != value["profileHex"]
                    or value["primitivesPointer"] and public_bytes(
                        session, value["primitivesPointer"], 8).hex()
                    != value["primitivesHex"]):
                raise ObstacleIntentError("Obstacle intent native inputs changed")
            current = self.current()
            result = context["returnValue"]
            if result not in (1, 2):
                raise ObstacleIntentError("Obstacle intent returned an unknown decision")
            if result == 2:
                actor = current["actor"]
                if actor.get("motionKind") != value["expectedKind"] or actor.get("motionPhase") != "MOVING":
                    raise ObstacleIntentError("Obstacle intent accepted a different motion")
                self.stage += 1
            self.inflight = False
            self.calls.append(deepcopy(dict(value, after=current, returnValue=result,
                                            entryClock=context["entry"],
                                            returnClock=context["returned"])))
        except Exception as error:
            self.fail(error)

    def completed_boundary(self):
        if self.closed or self.stage != 1:
            return
        try:
            actor = self.current()["actor"]
            landingX, landingY = self.LANDINGS[self.origin]
            if (actor.get("commitSequence") == self.initial_commit + 1
                    and actor.get("logical") == {"x": landingX, "y": landingY}):
                self.terminal = True
        except Exception as error:
            self.fail(error)

    def close(self, *, disposing=False):
        if self.closed:
            return
        if not disposing and (not self.terminal or self.inflight):
            self.fail("Obstacle intent closed before the Hop landing")
        observer = self.session.native_observation
        for token in self.tokens:
            observer.hooks.remove(token)
            if token in observer.tokens:
                observer.tokens.remove(token)
        self.tokens.clear()
        self.closed = True

    def result(self):
        return deepcopy(dict(armed=True, closed=self.closed, terminal=self.terminal,
                             failure=self.failure, stage=self.stage, calls=self.calls,
                             subject=self.subject, maxFrames=self.max_frames,
                             initialCommit=self.initial_commit,
                             guestMemoryWrites=0, acceptedProof=False))

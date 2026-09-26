"""Bounded south/down and north/up requests at the real Wild ledge planner."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_mount_pacing_observer import ENGINE, NativeMountedPacingObserver
from tools.overworld.devtools_observer import NativeObservationError, public_bytes
from tools.overworld.devtools_records import select_current_actor

ORIGIN = [590, 395]
TARGET = [590, 397]
SPECIES = 35
SYMBOL = "OverworldWildSpawns_TryStartLedgeJumpCommand"
CALLER = "OverworldWildSpawns_TryStartSpawnerMovementCommand"
IDENTITY = ("handle", "species", "form", "level", "subjectIdentity", "role",
            "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
            "behaviorFingerprint", "matchedLayerMask")


class WildLedgeFailure(NativeObservationError):
    fatal = True
    code = "wild-ledge-observation-failed"


class NativeWildLedgeObserver(NativeMountedPacingObserver):
    """Change only the direction word for two naturally reached planner calls."""
    def __init__(self, session, subject, max_frames):
        super().__init__(session, subject, max_frames)
        self.slot = subject.get("handle", {}).get("slot")
        self.phase = "south-pending"
        self.calls = []
        self.suppressed = 0
        self.guest_memory_writes = 0
        self.pending_writes = 0
        self.latest_completed_input = None
        self.call_sites = {}
        self.code = None
        self.provenance = None

    def _require(self, value, reason):
        if not value:
            self.failure = self.failure or "wild ledge: " + reason
            raise WildLedgeFailure(self.failure)

    def _current(self):
        from tools.overworld.devtools_runtime import actor_identity_checks
        s, rt, slot = self.session, self.session.rt, self.slot
        self._require(type(slot) is int and 0 <= slot < 6, "invalid Wild slot")
        actor, source = rt.actor_state(s.emu, slot), rt.wild_spawn(s.emu, slot)
        engine, world = rt.live_wild_object_identity(s.emu, slot), self.observer._world_context()
        self._require(all(actor_identity_checks(actor, source, engine, world, slot).values())
            and actor.get("role") == "WILD" and actor.get("species") == SPECIES
            and actor.get("inputOwnership") == 0 and actor.get("form") == source.get("form")
            and actor.get("level") == source.get("level"), "current Wild Clefairy binding differs")
        checked = {**actor, "identityVerified": True, "engineIdentity": engine, "sourceIdentity": source}
        select_current_actor({"actors": [checked], "context": world, "frame": s.completed_frames}, self.subject)
        current = dict(subject=deepcopy(self.subject), publicSubject=actor, sourceIdentity=source,
                       engineIdentity={key: engine.get(key) for key in ENGINE}, worldContext=world,
                       statePointer=rt.WILD_STATE, objectPointer=source["object"], slot=slot,
                       policy=rt.movement_policy_state(s.emu, slot))
        if self.owner is not None:
            self._require(all(current[key] == self.owner[key] for key in current if key not in ("publicSubject", "policy"))
                and all(actor.get(key) == self.owner["publicSubject"].get(key) for key in IDENTITY),
                "Wild ledge owner changed")
        return current

    def _authenticate(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        s = self.session
        path = s.rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
        address, size = _elf_function_extent(path, SYMBOL)
        code = self.observer.elf_code(path, address, size)
        self._require(s.rt.linked_symbol(s.rt.WILD_SYMBOLS, SYMBOL) & ~1 == address
            and size >= 32 and len(code) == size and s.packaged_code(address, size) == code,
            "linked/package ledge planner differs")
        self.code = (address, code)
        self.provenance = dict(symbol=SYMBOL, address=address, size=size,
                               sha256=hashlib.sha256(code).hexdigest(), caller=CALLER)
        self._live_code()

    def _live_code(self):
        address, code = self.code
        self._require(self.session.read(address, len(code)) == code, "live ledge planner differs")

    def _idle_at(self, current, point):
        actor = current["publicSubject"]
        return (actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE"
                and actor.get("reservationId") == 0 and current["policy"].get("pending") == 0
                and [actor.get("logical", {}).get(key) for key in ("x", "y")] == point)

    def _profile(self, current, pointer, allowed_tile, jump_level):
        raw = public_bytes(self.session, pointer, 144)
        resolved = self.observer.profiles.get(current["publicSubject"]["behaviorFingerprint"], {})
        self._require(resolved.get("resolved") is True and resolved.get("resultHex", "")[:288] == raw.hex(),
                      "profile lacks exact native resolver identity")
        rt, emu = self.session.rt, self.session.emu
        spot = (2 if rt.unsigned(emu, rt.WILD_STATE + 494 + self.slot, 1)
                else rt.unsigned(emu, rt.WILD_STATE + 264 + self.slot, 1))
        lane_index = 1 if spot == 3 else 0
        lane = raw[lane_index * 72:(lane_index + 1) * 72]
        self._require(allowed_tile == struct.unpack_from("<H", lane, 32)[0]
            and jump_level == raw[9] == 2 and raw[17] == 0,
            "Clefairy ledge profile inputs differ")
        return raw, lane_index, spot

    def _before(self):
        try:
            self._check_deadline()
            self._live_code()
            regs = self.session.emu.memory.register_arm9
            if regs.r2 & 0xffffffff != self.slot:
                return None
            current = self._current()
            self._require((regs.r0 & 0xffffffff) == self.session.rt.WILD_STATE
                and (regs.r1 & 0xffffffff) == current["worldContext"]["fieldPointer"]
                and (regs.r3 & 0xffffffff) == current["objectPointer"], "native ledge context differs")
            self.observer._chain_caller(CALLER, cache=self.call_sites)
            stack = regs.sp & 0xffffffff
            raw_stack = public_bytes(self.session, stack, 20)
            profile, allowed, jump, original_direction, avoid = struct.unpack("<5I", raw_stack)
            profile_raw, lane_index, spot = self._profile(current, profile, allowed, jump)
            self._require(original_direction <= 3 and avoid in (0, 1), "native ledge inputs exceed widths")
            if self.phase == "south-pending":
                direction, point, label = 1, ORIGIN, "south"
            elif self.phase == "north-pending":
                direction, point, label = 0, TARGET, "north"
            elif self.phase == "terminal":
                self._require(self._idle_at(current, ORIGIN), "terminal suppression is not idle at origin")
                before = deepcopy(current)
                regs.r0 = 0
                self.session.emu.memory.set_next_instruction(regs.lr)
                self.suppressed += 1
                return dict(case="suppressed", suppressed=True, before=before,
                            originalDirection=original_direction, direction=original_direction,
                            avoidPreviousTile=avoid, guestMemoryWrites=0)
            else:
                return None
            self._require(not self.data and self._idle_at(current, point), label + " request is not at its idle ledge side")
            value = dict(case=label, suppressed=False, subject=deepcopy(self.subject),
                         before=deepcopy(current), stack=stack,
                         stackHex=raw_stack.hex(), profilePointer=profile, profileHex=profile_raw.hex(),
                         laneIndex=lane_index, spotState=spot, allowedTile=allowed, jumpLevel=jump,
                         originalDirection=original_direction, direction=direction,
                         avoidPreviousTile=avoid, guestMemoryWrites=2)
            self.session.write(stack + 12, struct.pack("<I", direction))
            self.guest_memory_writes += 1
            self.pending_writes += 1
            self.data.append(value)
            return value
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(self.session, "abort_native_control", None)
            if abort is not None:
                abort(error)
            raise

    def _after(self, value, context):
        try:
            if value["suppressed"]:
                current = self._current()
                self._require(context["returnValue"] == 0 and current == value["before"],
                              "suppressed ledge call changed state")
                return dict(**value, after=current, returnValue=0)
            original = bytes.fromhex(value["stackHex"])[12:16]
            self.session.write(value["stack"] + 12, original)
            self.guest_memory_writes += 1
            self.pending_writes -= 1
            self._require(public_bytes(self.session, value["stack"], 20).hex() == value["stackHex"],
                          "ledge direction stack word was not restored")
            self._live_code()
            current = self._current()
            if value["case"] == "south":
                actor = current["publicSubject"]
                self._require(context["returnValue"] == 2 and actor.get("motionKind") == "HOP"
                    and actor.get("motionPhase") in ("PLANNED", "MOVING") and actor.get("reservationId", 0) > 0
                    and [actor.get("origin", {}).get(key) for key in ("x", "y")] == ORIGIN
                    and [actor.get("target", {}).get(key) for key in ("x", "y")] == TARGET,
                    "south ledge request did not start the real two-tile Hop")
                self.phase = "south-started"
            else:
                actor = current["publicSubject"]
                self._require(context["returnValue"] == 2 and actor.get("motionKind") == "HOP"
                    and actor.get("motionPhase") in ("PLANNED", "MOVING") and actor.get("reservationId", 0) > 0
                    and [actor.get("origin", {}).get(key) for key in ("x", "y")] == TARGET
                    and [actor.get("target", {}).get(key) for key in ("x", "y")] == ORIGIN,
                    "north ledge request did not start the real two-tile Hop")
                self.phase = "north-started"
            row = dict(**value, after=current, returnValue=context["returnValue"],
                       entryClock=deepcopy(context["entry"]), returnClock=deepcopy(context["returned"]))
            self.calls.append(deepcopy(row))
            return row
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(self.session, "abort_native_control", None)
            if abort is not None:
                abort(error)
            raise
        finally:
            if value in self.data:
                self.data.remove(value)

    def arm(self):
        self._require(not self.armed and not self.closed and type(self.maximum) is int
                      and 1 <= self.maximum <= 1200, "reader can arm only once with a bounded window")
        self.started = self.session.completed_frames
        try:
            self.owner = self._current()
            self._require(self._idle_at(self.owner, ORIGIN), "Clefairy must start idle at the south ledge origin")
            self._authenticate()
            self.armed = True
            def linked(label, _path, _symbols, name, before, after, **_kwargs):
                rt = self.session.rt
                path = rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
                address = rt.linked_symbol(rt.WILD_SYMBOLS, name) & ~1
                expected = self.observer.elf_code(path, address, 32)
                self.observer._tap(label, address, expected, before, after,
                    scope=lambda: self.armed and not self.closed
                    and (self.session.emu.memory.register_arm9.r2 & 0xffffffff) == self.slot,
                    resident=True)
            self.linked = linked
            self._install("wild-ledge-intent", SYMBOL, self._before, self._after)
            return self.result()
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close(disposing=True)
            raise

    def completed_boundary(self):
        self._check_deadline()
        if not self.armed or self.closed:
            return
        current = self._current()
        if self.phase == "south-started" and self._idle_at(current, TARGET):
            self.phase = "north-pending"
        elif self.phase == "north-started" and self._idle_at(current, ORIGIN):
            self.phase = "terminal"
        self.latest_completed_input = dict(frame=self.session.completed_frames, **self.observer._clock(),
            heldKeys=self.session.rt.unsigned(self.session.emu, 0x021D1150),
            newKeys=self.session.rt.unsigned(self.session.emu, 0x021D1154))

    def close(self, disposing=False):
        if self.closed:
            return self.result()
        if not disposing:
            self._require(self.phase == "terminal" and not self.pending_writes and len(self.calls) == 2,
                          "ledge reader closed before both terminal decisions")
        return super().close(disposing=disposing)

    def result(self):
        return deepcopy(dict(armed=self.armed, closed=self.closed, failure=self.failure,
            subject=self.subject, startFrame=self.started, maxFrames=self.maximum, phase=self.phase,
            terminal=self.phase == "terminal", calls=self.calls, suppressedCalls=self.suppressed,
            provenance=self.provenance, latestCompletedInput=self.latest_completed_input,
            guestMemoryWrites=self.guest_memory_writes, pendingWrites=self.pending_writes,
            acceptedProof=False,
            scope="two restored direction inputs start complete south/down and north/up Hops at the authenticated natural Wild ledge planner"))

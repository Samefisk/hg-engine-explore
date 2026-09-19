"""Opt-in native Wild Walk clear receipts; no guest writes or game driver."""
from copy import deepcopy

from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver, IDENTITY, ENGINE
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_observer import NativeObservationError, MOTION_DECISIONS, public_bytes

STATE_RUNTIME = 0xE4
STATE_COOLDOWN = 0xED
RUNTIME_ACTIVE = 0xA
RUNTIME_MOTION_IDENTITY = 0xDC
RUNTIME_MODE = 0x3D6
MAX_CLEARS = 64
MAX_REQUESTS = 256


def check_cleared_state(value):
    if value.get("active") != 0 or value.get("mode") != 0 \
            or type(value.get("objectFlags")) is not int or value["objectFlags"] & 0x12004:
        raise ValueError("Wild Walk clear state remains active")
    return True


class WildWalkObservationFailure(NativeObservationError):
    fatal = True
    code = "wild-walk-observation-failed"


class NativeWildWalkObserver(NativeMountedPacingObserver):
    """Share owned-hook cleanup mechanics, not mounted pose assumptions."""
    def __init__(self, session, subject, max_frames):
        super().__init__(session, subject, max_frames)
        self.counts = {"clear": 0}
        self.slot = subject.get("handle", {}).get("slot")
        self.clear_calibration = None
        self.latest_clear = None
        self.latest_completed_input = None
        self.request_count = 0
        self.latest_request = None

    def _require(self, value, reason):
        if not value:
            self.failure = self.failure or "wild Walk: " + reason
            raise WildWalkObservationFailure(self.failure)

    def _current(self):
        from tools.overworld.devtools_runtime import actor_identity_checks
        s, rt, slot = self.session, self.session.rt, self.slot
        self._require(type(slot) is int and 0 <= slot < 6, "invalid Wild slot")
        actor, source = rt.actor_state(s.emu, slot), rt.wild_spawn(s.emu, slot)
        engine, world = rt.live_wild_object_identity(s.emu, slot), self.observer._world_context()
        self._require(all(actor_identity_checks(actor, source, engine, world, slot).values())
            and actor.get("role") == "WILD" and actor.get("species") == 19
            and actor.get("inputOwnership") == 0 and actor.get("form") == source.get("form")
            and actor.get("level") == source.get("level"), "current Wild Rattata binding differs")
        checked = {**actor,"identityVerified":True,"engineIdentity":engine,"sourceIdentity":source}
        select_current_actor(dict(actors=[checked],context=world,frame=s.completed_frames),self.subject)
        runtime = rt.unsigned(s.emu, rt.WILD_STATE + STATE_RUNTIME)
        self._require(type(runtime) is int and runtime % 4 == 0
                      and 0x02000000 <= runtime <= 0x02400000-RUNTIME_MODE-10, "invalid runtime pointer")
        current = dict(subject=deepcopy(self.subject),publicSubject=actor,sourceIdentity=source,
                       engineIdentity={k:engine.get(k) for k in ENGINE},worldContext=world,
                       statePointer=rt.WILD_STATE,runtimePointer=runtime,objectPointer=source["object"],slot=slot)
        if self.owner is not None:
            self._require(all(current[k] == self.owner[k] for k in current if k != "publicSubject")
                and all(actor.get(k) == self.owner["publicSubject"].get(k) for k in IDENTITY),
                "Wild owner changed")
        return current

    def _read_clear_state(self, current):
        rt, emu, slot = self.session.rt, self.session.emu, self.slot
        runtime, obj = current["runtimePointer"], current["sourceIdentity"]["object"]
        return dict(current=deepcopy(current), active=rt.unsigned(emu,runtime+RUNTIME_ACTIVE+slot,1),
                    mode=rt.unsigned(emu,runtime+RUNTIME_MODE+slot,1), objectFlags=rt.unsigned(emu,obj))

    def _read_request_state(self, current):
        rt, emu = self.session.rt, self.session.emu
        return dict(self._read_clear_state(current),
            cooldown=rt.unsigned(emu,current["statePointer"]+STATE_COOLDOWN+self.slot,1),
            motionIdentity=rt.unsigned(emu,current["runtimePointer"]+RUNTIME_MOTION_IDENTITY+2*self.slot,2))

    def _before_request(self):
        regs = self.session.emu.memory.register_arm9
        if regs.r1 != self.slot: return None
        self._check_deadline()
        self._require(regs.r0 == self.session.rt.WILD_STATE, "request state argument differs")
        self._require(self.request_count < MAX_REQUESTS, "request limit exceeded")
        current = self._current()
        # Same checked ARM stack-word reader and public lane as chain requests,
        # without the chain-only prepared-start ownership assumptions.
        words = self.observer._chain_words(7)
        self._require(0 <= regs.r3 <= 255 and all(value <= limit for value, limit in
            zip(words,(255,255,255,65535,255,255,65535))), "request arguments exceed native widths")
        request = dict(kind=regs.r3,lanePointer=regs.r2,
            laneHex=public_bytes(self.session,regs.r2,72).hex(),
            **dict(zip(("visibility","arc","facing","duration","spin","sway","surfaceId"),words)))
        value = dict(request=request,before=self._read_request_state(current))
        self.request_count += 1
        self.data.append(value)
        return value

    def _after_request(self, before, context):
        try:
            decision = context["returnValue"]
            self._require(0 <= decision < len(MOTION_DECISIONS), "request decision enum differs")
            value = dict(subject=deepcopy(self.subject),**before,
                after=self._read_request_state(self._current()),decision=decision,
                decisionName=MOTION_DECISIONS[decision],
                entryClock=deepcopy(context["entry"]),returnClock=deepcopy(context["returned"]),
                meaning="native Wild RequestMotion return; diagnostic only")
            self.latest_request = deepcopy(value)
            return value
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(self.session,"abort_native_control",None)
            if abort is not None: abort(error)
            raise
        finally:
            if before in self.data: self.data.remove(before)

    def _before_clear(self):
        regs = self.session.emu.memory.register_arm9
        if regs.r1 != self.slot: return None
        self._check_deadline()
        self._require(regs.r0 == self.session.rt.WILD_STATE, "clear state argument differs")
        self._require(self.counts["clear"] < MAX_CLEARS, "clear limit exceeded")
        before = self._read_clear_state(self._current())
        self.counts["clear"] += 1
        self.data.append(before)
        return before

    def _after_clear(self, before, context):
        try:
            after = self._read_clear_state(self._current())
            value = dict(subject=deepcopy(self.subject),before=before,after=after,
                         entryClock=deepcopy(context["entry"]),returnClock=deepcopy(context["returned"]),
                         meaning="native ClearCustomJumpLocal return; not cancellation or inferred idle")
            self.latest_clear = deepcopy(value)
            return value
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(self.session,"abort_native_control",None)
            if abort is not None:abort(error)
            raise
        finally:
            if before in self.data: self.data.remove(before)

    def arm(self):
        self._require(not self.armed and not self.closed, "reader can arm only once")
        self._require(type(self.maximum) is int and 1 <= self.maximum <= 1200, "invalid frame limit")
        self.started = self.session.completed_frames
        try:
            self.owner = self._current()
            self.armed = True
            # Reuse the parent's exact entry/return token ownership wrapper.
            # This routing closure selects Wild packaging, not its mount path.
            def linked(label, ignored_path, ignored_symbols, name, before, after, **kwargs):
                rt = self.session.rt
                request = label == "wild-walk-request"
                path = rt.REPO / ("build/overworld_wild_runtime_overlay_linked.o" if request
                                  else "build/overworld_wild_spawns_overlay_linked.o")
                symbols = rt.linked_symbols(path) if request else rt.WILD_SYMBOLS
                address = rt.linked_symbol(symbols,name) & ~1
                expected = self.observer.elf_code(path,address,32)
                self.observer._tap(label,address,expected,before,after,
                    scope=lambda:self.armed and not self.closed and self.session.emu.memory.register_arm9.r1 == self.slot,
                    resident=True)
            self.linked = linked
            self._install("wild-walk-clear","OverworldWildSpawns_ClearCustomJumpLocal",self._before_clear,self._after_clear)
            self._install("wild-walk-request","OverworldWildRuntime_RequestMotion",self._before_request,self._after_request)
            return self.result()
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close(disposing=True)
            raise

    def _check_deadline(self):
        if self.armed and not self.closed:
            self._require(self.failure is None,"reader already failed")
            self._require(0 <= self.session.completed_frames-self.started <= self.maximum, "frame limit exceeded")
            self._require(self.observer.events_dropped == 0 and self.observer.hooks.error is None,
                          "native events dropped or hook failed")

    def completed_boundary(self):
        self._check_deadline()
        if self.armed and not self.closed:
            self._current()
            self.latest_completed_input = dict(frame=self.session.completed_frames,**self.observer._clock(),
                heldKeys=self.session.rt.unsigned(self.session.emu,0x021D1150),
                newKeys=self.session.rt.unsigned(self.session.emu,0x021D1154))

    def result(self):
        return deepcopy(dict(armed=self.armed,closed=self.closed,failure=self.failure,subject=self.subject,
            startFrame=self.started,maxFrames=self.maximum,maxClears=MAX_CLEARS,counts=self.counts,
            acceptedProof=False,guestMemoryWrites=0 if self.clear_calibration is None else 2,
            latestClear=self.latest_clear,clearCalibration=self.clear_calibration,
            latestCompletedInput=self.latest_completed_input,
            requestCount=self.request_count,maxRequests=MAX_REQUESTS,latestRequest=self.latest_request,
            scope="native Wild clear and request receipts; shared completion framing"))

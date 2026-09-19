"""Bounded native Walk Tick entry/return data, never inferred elapsed samples.

The shared stream owns each full receipt once. result() is deliberately small.
Completed queue poses remain a different observation from these native ticks.
"""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_field_cleanup import symbol
from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver, IDENTITY
from tools.overworld.devtools_observer import public_bytes

MAX_FRAMES = 4096
MAX_CALLBACKS = 8192
SLOT_STRIDE, SNAPSHOT_BYTES, MOTION_BYTES, POLICY_BYTES, SAMPLE_BYTES = 172, 88, 52, 32, 36
ACTORS_OFFSET, ACTOR_CAPACITY = 68, 10
PHASES = ("IDLE", "PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING", "SUSPENDED", "CANCELED")


def decode_motion(raw):
    """Decode actual native bytes. No expected timing is computed here."""
    if not isinstance(raw, bytes) or len(raw) != MOTION_BYTES:
        raise ValueError("Walk matrix motion state read is incomplete")
    version, kind, facing, epoch, fingerprint = struct.unpack_from("<HBBHH", raw)
    origin_x, origin_y, target_x, target_y, origin_height, target_height = struct.unpack_from("<4h2i", raw, 8)
    duration, reservation = struct.unpack_from("<HH", raw, 24)
    names = ("direction", "distance", "arcHeightQ4", "spinSpeed", "swayWidth", "visibilityPolicy",
             "pauseFrames", "pathAdvancePolicy", "commitPolicy", "flags")
    plan = dict(version=version, kind=kind, facing=facing, fieldEpoch=epoch,
        behaviorFingerprint=fingerprint, origin=[origin_x, origin_y], target=[target_x, target_y],
        startBaseY=origin_height, targetBaseY=target_height, duration=duration, reservationId=reservation,
        **dict(zip(names, raw[28:38])))
    elapsed, settle, advances, commit, phase, prior, published, cancel = struct.unpack_from("<4H4B", raw, 40)
    if phase >= len(PHASES) or prior >= len(PHASES) or kind > 5 or published not in (0, 1):
        raise ValueError("Walk matrix motion state enum is invalid")
    if phase not in (0, 6) and (version != 1 or kind == 0 or epoch == 0 or reservation == 0
                              or elapsed > duration or (kind != 3 and duration == 0)):
        raise ValueError("Walk matrix active motion state is invalid")
    return dict(rawHex=raw.hex(), plan=plan, elapsed=elapsed, settleRemaining=settle,
                pathAdvancesPublished=advances, commitSequence=commit, phase=PHASES[phase],
                phaseId=phase, phaseBeforeSuspend=prior, commitPublished=published, cancelReason=cancel)


def decode_sample(raw):
    if not isinstance(raw, bytes) or len(raw) != SAMPLE_BYTES:
        raise ValueError("Walk matrix sample read is incomplete")
    names = ("renderX", "renderY", "renderZ", "baseY", "heightOffset", "swayOffset",
             "elapsed", "duration", "firstPathAdvance", "lastPathAdvance", "flags", "facing", "visible")
    value = dict(zip(names, struct.unpack("<6i5H2B", raw)))
    if value["flags"] & ~0x3F or value["visible"] not in (0, 1):
        raise ValueError("Walk matrix sample flags or visibility are invalid")
    return dict(rawHex=raw.hex(), **value)


class NativeWalkMatrixObserver(NativeMountedPacingObserver):
    def __init__(self, session, subject, max_frames):
        super().__init__(session, subject, max_frames)
        self.counts = dict(ticks=0, movingWalk=0)
        self.completed_count = 0
        self.code = self.layout = self.last_tick = None
        self.motion_pointer = None
        self.last_moving_tick = self.latest_completed = self.calibration = None
        self.ignored_other_slots = 0
        self.retired_return_addresses = set()
        self.linked = self._linked_tick

    def _authenticate(self):
        s, rt = self.session, self.session.rt
        image = (rt.REPO / "build/overworld_actor_system_overlay_linked.o").read_bytes()
        descriptor = deepcopy(rt.ACTOR_DESCRIPTOR)
        state = descriptor["state"]
        address, size, code = symbol(image, "OverworldMotion_Tick", 2)
        state_address, state_bytes, _ = symbol(image, "gOverworldActorSystemState", 1,
                                               section_name=".bss", expected_size=state["size"])
        self._require(state_address == state["address"] and state["actorStride"] == SLOT_STRIDE
            and state["offsets"]["actors"] == ACTORS_OFFSET
            and state["actorPolicyOffset"] == SNAPSHOT_BYTES + MOTION_BYTES
            and descriptor["structures"]["actorPolicyState"] == POLICY_BYTES
            and descriptor["capacities"]["actors"] == ACTOR_CAPACITY
            and SNAPSHOT_BYTES + MOTION_BYTES + POLICY_BYTES == SLOT_STRIDE
            and state_bytes >= ACTORS_OFFSET + SLOT_STRIDE * ACTOR_CAPACITY,
            "Walk matrix linked state and descriptor layout differ")
        self._require(len(code) == size and size >= 32 and s.packaged_code(address, size) == code,
                      "Walk matrix full Tick package differs")
        self.code = (address, code)
        self.layout = dict(stateAddress=state_address, stateBytes=state_bytes, actorsOffset=ACTORS_OFFSET,
            actorStride=SLOT_STRIDE, capacity=ACTOR_CAPACITY, snapshotBytes=SNAPSHOT_BYTES,
            motionOffset=SNAPSHOT_BYTES, motionBytes=MOTION_BYTES,
            policyOffset=SNAPSHOT_BYTES + MOTION_BYTES, policyBytes=POLICY_BYTES,
            sampleBytes=SAMPLE_BYTES,
            tickAddress=address, tickSize=size, tickSha256=hashlib.sha256(code).hexdigest())
        self.motion_pointer = state_address + ACTORS_OFFSET + self.subject["handle"]["slot"]*SLOT_STRIDE + SNAPSHOT_BYTES
        self._live_code()

    def _linked_tick(self, label, path, symbols, name, before, after, **kwargs):
        address, code = self.code
        self.observer._tap(label, address, code[:32], before, after, **kwargs)

    def _live_code(self):
        address, code = self.code
        self._require(self.session.read(address, len(code)) == code, "Walk matrix full live Tick differs")

    def arm(self):
        s = self.session
        self._require(not self.armed and not self.closed and type(self.maximum) is int
            and 1 <= self.maximum <= MAX_FRAMES, "Walk matrix arm or frame bound differs")
        self._require(s.emu is not None and not s.native_bridge_active
            and s.rom.resolve().is_relative_to(s.directory.resolve())
            and s.rom.resolve() != (s.rt.REPO / "test.nds").resolve(),
            "Walk matrix requires an owned private session")
        self.started = s.completed_frames
        try:
            self.owner = self._current()
            actor = self.owner["publicSubject"]
            self._require(actor["species"] == 155 and actor["role"] == "MOUNTED",
                          "Walk matrix requires mounted Cyndaquil")
            self._authenticate()
            self.armed = True
            self._install("walk-matrix-tick", "OverworldMotion_Tick", self._before_tick, self._after_tick)
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close()
            raise
        return self.result()

    def completed_boundary(self):
        self._check_deadline()
        if self.armed and not self.closed:
            self.latest_completed = dict(current=self._current(), frame=self.session.completed_frames,
                                         **self.observer._clock())
            self._live_code()

    def _read_motion(self, pointer):
        # Native callbacks and stopped-guest calibration use this same read.
        self._require(pointer == self.motion_pointer, "Walk matrix motion pointer differs")
        return decode_motion(self.session.read(pointer, MOTION_BYTES))

    def _before_tick(self):
        self._check_deadline()
        self._live_code()
        regs = self.session.emu.memory.register_arm9
        pointer = regs.r0
        first = self.layout["stateAddress"] + ACTORS_OFFSET + SNAPSHOT_BYTES
        self._require(type(pointer) is int and first <= pointer < first+SLOT_STRIDE*ACTOR_CAPACITY
            and (pointer-first) % SLOT_STRIDE == 0, "Walk matrix Tick motion pointer is not an actor slot")
        if pointer != self.motion_pointer:
            self.ignored_other_slots += 1
            return None
        self._require(not self.data and self.counts["ticks"] < MAX_CALLBACKS,
                      "Walk matrix callback nesting or bound differs")
        current = self._current()
        self._require(type(regs.r1) is int and regs.r1 == current["worldContext"]["fieldEpoch"],
                      "Walk matrix Tick field epoch differs")
        sample_pointer = regs.r2
        self._require(type(sample_pointer) is int and sample_pointer % 4 == 0
            and not (self.layout["stateAddress"] <= sample_pointer < self.layout["stateAddress"]+self.layout["stateBytes"]),
            "Walk matrix output sample pointer differs")
        public_bytes(self.session, sample_pointer, SAMPLE_BYTES)
        motion = self._read_motion(pointer)
        if motion["phase"] not in ("IDLE", "CANCELED"):
            self._require(motion["plan"]["fieldEpoch"] == regs.r1, "Walk matrix plan field epoch differs")
            self._require(current["publicSubject"].get("reservationId") == motion["plan"]["reservationId"],
                          "Walk matrix plan reservation owner differs")
        moving = motion["phase"] == "MOVING" and motion["plan"]["kind"] == 1
        qualification = "moving-walk" if moving else "non-moving-walk" if motion["plan"]["kind"] == 1 else "other-motion"
        value = dict(beforeCurrent=current, before=motion, motionPointer=pointer, samplePointer=sample_pointer,
            expectedFieldEpoch=regs.r1, completedFrame=self.session.completed_frames,
            entryClock=self.observer._clock(), qualification=qualification, movingWalk=moving,
            input=deepcopy(self.session._selector_observation()))
        self.counts["ticks"] += 1
        self.counts["movingWalk"] += int(moving)
        self.data.append(value)
        return value

    def _after_tick(self, value, context):
        try:
            self._check_deadline()
            self._live_code()
            current = self._current()
            before_current = value["beforeCurrent"]
            self._require(all(current[k] == before_current[k] for k in
                ("subject", "sourceIdentity", "engineIdentity", "worldContext", "playerPointer", "mountPointer", "avatarPointer"))
                and all(current["publicSubject"].get(k) == before_current["publicSubject"].get(k) for k in IDENTITY),
                "Walk matrix Tick return owner differs")
            after = self._read_motion(value["motionPointer"])
            self._require(after["rawHex"][:80] == value["before"]["rawHex"][:80],
                          "Walk matrix Tick changed its plan")
            sample = decode_sample(public_bytes(self.session, value["samplePointer"], SAMPLE_BYTES))
            flags = context["returnValue"]
            self._require(type(flags) is int and not flags & ~0x3F and flags == sample["flags"],
                          "Walk matrix native return flags differ")
            result = dict(value, afterCurrent=current, after=after, sample=sample,
                          returnFlags=flags, returnClock=deepcopy(context["returned"]), normalReturn=True)
            self.completed_count += 1
            self.last_tick = dict(completedFrame=value["completedFrame"],
                                 entryElapsed=value["before"]["elapsed"], returnElapsed=after["elapsed"],
                                 reservationId=after["plan"]["reservationId"], qualification=value["qualification"])
            if value["movingWalk"]:
                self.last_moving_tick = dict(self.last_tick, duration=after["plan"]["duration"],
                    phaseBefore=value["before"]["phase"], phaseAfter=after["phase"], returnFlags=flags,
                    fieldEpoch=value["expectedFieldEpoch"], entryClock=deepcopy(value["entryClock"]),
                    returnClock=deepcopy(context["returned"]))
            return result
        except Exception as error:
            self.failure = self.failure or str(error)
            raise
        finally:
            if value in self.data:
                self.data.remove(value)
            # _tap removes its return token before calling this method. The
            # inherited entry tracker otherwise retains that token's closure
            # (and the full raw tick) until close. Keep pending tokens only.
            pending = []
            for token in self.returns:
                if token in self.observer.return_tokens:
                    pending.append(token)
                else:
                    self.retired_return_addresses.add(token[0])
            self.returns[:] = pending

    def close(self, disposing=False):
        super().close(disposing)
        # Keep only integer addresses until close; unregistering the native
        # dispatcher after every tick would add needless callback churn.
        for address in self.retired_return_addresses:
            try:
                self.observer.hooks.retire_empty(address)
            except Exception as error:
                self.failure = self.failure or "Walk matrix return cleanup: " + str(error)
        self.retired_return_addresses.clear()
        return self.result()

    def result(self):
        return deepcopy(dict(armed=self.armed, closed=self.closed, failure=self.failure, subject=self.subject,
            startFrame=self.started, maxFrames=self.maximum, maxCallbacks=MAX_CALLBACKS,
            counts=self.counts, returned=self.completed_count, pending=len(self.data),
            ignoredOtherSlots=self.ignored_other_slots, layout=self.layout, motionPointer=self.motion_pointer,
            lastTick=self.last_tick, lastMovingTick=self.last_moving_tick,
            guestMemoryWrites=(self.calibration or {}).get("guestMemoryWrites",0),
            calibration=self.calibration, acceptedProof=False,
            scope="actual native Tick entry/return; each raw receipt emitted once through shared events"))

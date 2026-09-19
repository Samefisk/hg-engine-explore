"""Bounded, read-only main-loop pacing samples.

The stock wait reader records the whole wait envelope.  This reader observes
only the authenticated return from the mandatory VBlank wait.  That gives one
sample for each completed main-loop wait, with no guest writes or return-hook
rewrites.  Diagnostic routes use the existing spawn-cost ``baseline`` mode.
Acceptance tests can arm a bounded dynamic window without changing guest state.
"""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_wait_probe import (
    COUNTER,
    IDENTITIES,
    SITES,
    SYSTEM,
)


RETURN_SITE = SITES[-1]
WINDOWS = ((770, 1530), (3564, 3580))
MAX_CYCLES = sum(end - start + 1 for start, end in WINDOWS)
SCOPE = "postmandatory-vblank-return-inclusive-guest-scheduler-ticks"
VBLANK_ARM9_TICKS = 1120380
NORMAL_MAIN_LOOP_ARM9_TICKS = 2 * VBLANK_ARM9_TICKS
NORMAL_MAIN_LOOP_NATIVE_CYCLES = 2
# The scheduler clocks are sampled on two different hooks. A normal two-cycle
# loop can therefore differ by a small part of one VBlank. Crossing the half
# VBlank margin is still rejected even if the exact cycle counters are wrong.
MAX_ZERO_STUTTER_ARM9_TICKS = NORMAL_MAIN_LOOP_ARM9_TICKS + VBLANK_ARM9_TICKS // 2


class MainLoopProbe:
    """Observe fixed post-wait returns between shared queue boundaries."""

    def __init__(self, session, hooks, clock, native_clock, *, windows=WINDOWS,
                 require_diagnostic_baseline=True):
        self.session, self.hooks = session, hooks
        self.clock, self.native_clock = clock, native_clock
        self.tokens = []
        self.active = None
        self.last_sample = None
        self.completed = 0
        self.last_frame = None
        self.previous = None
        self.closed = False
        self.failure = None
        self.windows = tuple(windows)
        self._require(bool(self.windows) and all(type(a) is int and type(b) is int
                      and 0 <= a <= b for a, b in self.windows)
                      and all(a > self.windows[i - 1][1] for i, (a, b) in enumerate(self.windows) if i),
                      "invalid sample windows")
        self.max_cycles = sum(b - a + 1 for a, b in self.windows)
        self._require(self.max_cycles <= 5000, "sample window exceeds bound")
        self.diagnostic_only = require_diagnostic_baseline
        if require_diagnostic_baseline:
            self._require(getattr(getattr(session, "spawn_cost_probe", None), "mode", None)
                          == "baseline", "requires diagnostic baseline")

    def _require(self, condition, reason):
        if not condition:
            self.failure = self.failure or "main-loop pacing probe: " + reason
            raise ValueError(self.failure)

    def _authenticate(self):
        for address, size, digest in IDENTITIES:
            code = self.session.packaged_code(address, size)
            self._require(len(code) == size and hashlib.sha256(code).hexdigest() == digest,
                          f"code identity differs at {address:#x}")

    def _detach(self):
        for token in self.tokens:
            self.hooks.remove(token)
        self.tokens.clear()

    @staticmethod
    def _clock_ok(value):
        return (isinstance(value, dict) and type(value.get("version")) is int
                and value["version"] == 1 and value.get("running") is True
                and value.get("scope") == "nds-scheduler-ticks-not-cpu-or-instructions"
                and all(type(value.get(key)) is int and 0 <= value[key] < (1 << 64)
                        for key in ("arm9Timestamp", "arm7Timestamp", "frameSequence")))

    @staticmethod
    def _native_ok(value):
        return (isinstance(value, dict)
                and all(type(value.get(key)) is int and 0 <= value[key] < (1 << 64)
                        for key in ("actorFrame", "nativeCycle")))

    def _sample(self):
        self._require(self.failure is None and not self.closed and self.active is not None,
                      "callback outside active window")
        guest = deepcopy(self.clock())
        self._require(self._clock_ok(guest), "invalid guest clock")
        native = deepcopy(self.native_clock())
        self._require(self._native_ok(native), "invalid native clock")
        regs = self.session.emu.memory.register_arm9
        self._require(regs.r4 & 0xFFFFFFFF == SYSTEM, "system owner differs")
        raw = self.session.read(COUNTER, 4)
        self._require(len(raw) == 4, "frame counter read incomplete")
        counter = struct.unpack("<I", raw)[0]
        if self.previous is not None:
            prior = self.previous
            self._require(all(guest[key] >= prior["guestClock"][key]
                              for key in ("arm9Timestamp", "arm7Timestamp", "frameSequence")),
                          "guest clock went backwards")
            self._require(all(native[key] >= prior[key]
                              for key in ("actorFrame", "nativeCycle")),
                          "native clock went backwards")
        # Stock main resets this counter at E28 after each sampled E22 return.
        # A late loop can therefore have 3 here, followed by a normal 2.
        self._require(self.completed + len(self.active["samples"]) < self.max_cycles,
                      "sample limit reached")
        sample = dict(returnSite=RETURN_SITE, frameCounter=counter,
                      guestClock=guest, actorFrame=native["actorFrame"],
                      nativeCycle=native["nativeCycle"], systemPointer=regs.r4 & 0xFFFFFFFF,
                      armedAtQueueFrame=self.active["afterQueueFrame"],
                      windowIndex=self.active["windowIndex"])
        self.active["samples"].append(sample)
        self.previous = sample

    def _install(self):
        if self.tokens:
            return
        try:
            # E22 is resident main code. Authenticate its containing regions
            # once before arming this fixed-address reader; every callback
            # then performs only the clocks, owner and counter reads.
            self._authenticate()
            self.tokens.append(self.hooks.add(RETURN_SITE, self._sample))
        except Exception as error:
            self.failure = self.failure or str(error)
            self._detach()
            raise

    def _window(self, frame):
        for index, (start, end) in enumerate(self.windows):
            if start <= frame <= end:
                return index
        return None

    @staticmethod
    def _interval(previous, current):
        return dict(
            arm9Ticks=current["guestClock"]["arm9Timestamp"] - previous["guestClock"]["arm9Timestamp"],
            arm7Ticks=current["guestClock"]["arm7Timestamp"] - previous["guestClock"]["arm7Timestamp"],
            frameSequence=current["guestClock"]["frameSequence"] - previous["guestClock"]["frameSequence"],
            actorFrames=current["actorFrame"] - previous["actorFrame"],
            nativeCycles=current["nativeCycle"] - previous["nativeCycle"],
        )

    def completed_frame(self, frame):
        rows = []
        try:
            self._require(self.failure is None and not self.closed, "reader is stopped")
            self._require(type(frame) is int and frame >= 0
                          and (self.last_frame is None or frame == self.last_frame + 1),
                          "queue sequence differs")
            self.last_frame = frame
            if self.active is not None:
                active = self.active
                self._require(len(active["samples"]) == 1,
                              "completed queue has missing or duplicate loop return")
                sample = deepcopy(active["samples"][0])
                loop_id = self.completed + 1
                previous = self.last_sample
                same_window = (previous is not None
                               and previous["windowIndex"] == active["windowIndex"])
                row = dict(observation="stock-main-loop-pacing", loopId=loop_id,
                           previousLoopId=loop_id - 1 if previous is not None else None,
                           afterQueueFrame=active["afterQueueFrame"],
                           flushedAtQueueFrame=frame, returnSite=sample["returnSite"],
                           windowIndex=active["windowIndex"],
                           frameCounter=sample["frameCounter"], guestClock=sample["guestClock"],
                           actorFrame=sample["actorFrame"], nativeCycle=sample["nativeCycle"],
                           systemPointer=sample["systemPointer"],
                           intervalFromPrevious=(self._interval(previous, sample)
                                                 if same_window else None),
                           scope=SCOPE, diagnosticOnly=self.diagnostic_only,
                           acceptedProof=False)
                self.last_sample = row
                self.completed += 1
                rows.append(row)
                self.active = None
            window = self._window(frame)
            if window is not None:
                self._require(self.completed < self.max_cycles, "cycle limit reached")
                self._install()
                self.active = dict(afterQueueFrame=frame, windowIndex=window, samples=[])
            else:
                self._detach()
            return rows
        except Exception as error:
            self.failure = self.failure or str(error)
            self._detach()
            raise

    def result(self):
        return deepcopy(dict(schemaVersion=1, windows=[list(x) for x in self.windows],
            returnSite=RETURN_SITE,
            identities=[dict(address=a, size=n, sha256=h) for a, n, h in IDENTITIES],
            completedLoops=self.completed, lastSample=self.last_sample, active=self.active,
            closed=self.closed, failure=self.failure, attachedHooks=len(self.tokens),
            guestMemoryWrites=0, scope=SCOPE, diagnosticOnly=self.diagnostic_only,
            acceptedProof=False))

    def close(self):
        if self.closed:
            return self.result()
        if self.active is not None:
            self.failure = self.failure or (
                "main-loop pacing probe: closed before next queue flushed window")
        self._detach()
        self.closed = True
        return self.result()


def arm_main_loop_pacing(session, args):
    """Arm one acceptance-input window at the next completed queue frame."""
    max_frames = args.get("maxFrames")
    if type(max_frames) is not int or not 2 <= max_frames <= 5000:
        raise ValueError("main-loop pacing window must contain 2 to 5000 frames")
    observer = session.native_observation
    if observer is None or observer.main_loop_probe is not None:
        raise ValueError("main-loop pacing reader is unavailable or already armed")
    start = session.completed_frames + 1
    observer.main_loop_probe = MainLoopProbe(
        session, observer.hooks, observer._guest_clock, observer._clock,
        windows=((start, start + max_frames),), require_diagnostic_baseline=False)
    return {
        "schemaVersion": 1,
        "armedAtQueueFrame": session.completed_frames,
        "firstObservedQueueFrame": start,
        "lastObservedQueueFrame": start + max_frames,
        "normalMaximumArm9Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS,
        "maximumZeroStutterArm9Ticks": MAX_ZERO_STUTTER_ARM9_TICKS,
        "normalMaximumNativeCycles": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
        "guestMemoryWrites": 0,
        "acceptedProof": False,
    }

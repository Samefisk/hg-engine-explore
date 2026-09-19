"""Session-long native progress checks; no actor-motion or wall-clock policy."""


class RuntimeHealthFailure(Exception):
    def __init__(self, code, details):
        self.code = code
        self.details = details
        super().__init__(code)


class RuntimeHealthMonitor:
    """Observe native-cycle endpoints outside the tool's native bridge.

    A completed main queue resets the progress deadline. Host time does not.
    A failed monitor stays failed; only a new session gets a new monitor.
    """

    def __init__(self, initial_frame, initial_native_cycle):
        if not self._counter(initial_frame) or not self._counter(initial_native_cycle):
            raise RuntimeHealthFailure("invalid-sample", {
                "completedFrame": initial_frame, "nativeCycle": initial_native_cycle})
        self._frame = initial_frame
        self._cycle = initial_native_cycle
        self._progress_cycle = initial_native_cycle
        self._failure = None
        self._native_call_start = None

    @staticmethod
    def _counter(value):
        return type(value) is int and value >= 0

    def observe(self, native_cycle, completed_frame, cpsr):
        details = self._validate(native_cycle, completed_frame, cpsr)
        if self._native_call_start is not None:
            self._fail("invalid-sample", {**details, "reason": "native call still active"})
        self._advance(native_cycle, completed_frame, details)

    def begin_native_call(self, native_cycle, completed_frame, cpsr):
        """Mark the endpoint immediately before the owned bridge advances."""
        self.observe(native_cycle, completed_frame, cpsr)
        self._native_call_start = native_cycle

    def complete_native_call(self, native_cycle, completed_frame, cpsr):
        """Exclude bridge cycles without erasing prior queue-stall debt."""
        details = self._validate(native_cycle, completed_frame, cpsr)
        if self._native_call_start is None:
            self._fail("invalid-sample", {**details, "reason": "no native call active"})
        self._progress_cycle += native_cycle - self._native_call_start
        self._native_call_start = None
        # Bridge execution is not normal queue-progress credit, even if a
        # callback was crossed while the tool owned native execution.
        self._frame, self._cycle = completed_frame, native_cycle

    def _validate(self, native_cycle, completed_frame, cpsr):
        if self._failure is not None:
            raise self._failure
        valid = (self._counter(native_cycle) and self._counter(completed_frame)
                 and type(cpsr) is int and 0 <= cpsr <= 0xFFFFFFFF)
        details = {"nativeCycle": native_cycle, "completedFrame": completed_frame,
                   "previousNativeCycle": self._cycle, "previousCompletedFrame": self._frame,
                   "lastProgressNativeCycle": self._progress_cycle,
                   "cpsr": cpsr, "mode": (cpsr & 0x1F) if type(cpsr) is int else None}
        if not valid or native_cycle < self._cycle or completed_frame < self._frame:
            self._fail("invalid-sample", details)
        details["nativeCyclesWithoutProgress"] = native_cycle - self._progress_cycle
        if details["mode"] in (0x17, 0x1B):
            self._fail("arm9-abort" if details["mode"] == 0x17 else "arm9-undefined", details)
        return details

    def _advance(self, native_cycle, completed_frame, details):
        details["lastProgressNativeCycle"] = self._progress_cycle
        details["nativeCyclesWithoutProgress"] = native_cycle - self._progress_cycle
        if completed_frame > self._frame:
            self._progress_cycle = native_cycle
        elif native_cycle - self._progress_cycle >= 120:
            self._fail("main-queue-stalled", details)
        self._frame, self._cycle = completed_frame, native_cycle

    def _fail(self, code, details):
        self._failure = RuntimeHealthFailure(code, details)
        raise self._failure

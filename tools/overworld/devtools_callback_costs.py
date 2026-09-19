"""Partial current-thread CPU costs for selected synchronous callbacks only.

Nested callbacks receive exclusive time. Nothing here subtracts from the
native-cycle process-CPU measurement or changes its hitch classification.
The default thread clock excludes concurrent emulator-thread CPU work.
"""
from contextlib import contextmanager
import gc
import threading
import time

MAX_LABELS = 2064  # Bounded native sites plus sampler phases and three GC generations.
MAX_CPU_NS = 10**12
SCOPE = "partial selected current-thread callbacks only; not whole-emulator CPU attribution"


def _integer(value, low=0, high=MAX_CPU_NS):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid callback cost integer")
    return value


def _label(value):
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError("invalid callback cost label")
    return value


def validate_callback_costs(value, total_cpu_ns):
    """Validate optional raw-cycle attribution without modifying the record."""
    total = _integer(total_cpu_ns)
    if not isinstance(value, dict) or set(value) != {
            "schemaVersion", "totalCpuNs", "measuredCpuNs", "categories", "scope"}:
        raise ValueError("invalid callback cost schema")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1 \
            or _integer(value["totalCpuNs"]) != total or value["scope"] != SCOPE:
        raise ValueError("callback cost scope or cycle total differs")
    categories = value["categories"]
    if not isinstance(categories, dict) or len(categories) > MAX_LABELS:
        raise ValueError("callback cost category bound exceeded")
    measured = 0
    for label, row in categories.items():
        _label(label)
        if not isinstance(row, dict) or set(row) != {"cpuNs", "calls"}:
            raise ValueError("invalid callback cost category")
        measured += _integer(row["cpuNs"])
        _integer(row["calls"], 1, 0xFFFFFFFF)
    if measured != _integer(value["measuredCpuNs"]) or measured > total:
        raise ValueError("callback costs exceed or disagree with the measured cycle")
    return value


class CallbackCosts:
    def __init__(self, clock=time.thread_time_ns):
        self.clock = clock
        self._stack = []
        self._categories = {}
        self._last_clock = None
        self._failure = None

    def begin_cycle(self):
        if self._stack:
            raise ValueError("cannot reset callback costs inside a callback")
        self._categories = {}
        self._failure = None

    def _read(self):
        value = self.clock()
        if type(value) is not int or value < 0 \
                or self._last_clock is not None and value < self._last_clock:
            raise ValueError("invalid or reversed callback CPU clock")
        self._last_clock = value
        return value

    def call(self, label, callback, *args, **kwargs):
        # Native hooks are hot: no generator/context-manager allocation here.
        frame = self._enter(label)
        original = None
        try:
            return callback(*args, **kwargs)
        except BaseException as error:
            original = error
            raise
        finally:
            self._leave(label, frame, original)

    def _enter(self, label):
        if self._failure is not None:
            raise ValueError(self._failure)
        _label(label)
        if label not in self._categories:
            if len(self._categories) >= MAX_LABELS:
                raise ValueError("callback cost category bound exceeded")
            self._categories[label] = {"cpuNs": 0, "calls": 0}
        try:
            start = self._read()
        except Exception as error:
            self._failure = str(error)
            raise
        frame = [start, 0]
        self._stack.append(frame)
        return frame

    @contextmanager
    def _measure(self, label):
        frame = self._enter(label)
        original = None
        try:
            yield
        except BaseException as error:
            original = error
            raise
        finally:
            self._leave(label, frame, original)

    def _leave(self, label, frame, original):
        try:
            try:
                elapsed = self._read() - frame[0]
                exclusive = elapsed - frame[1]
                _integer(exclusive)
                row = self._categories[label]
                row["cpuNs"] += exclusive
                row["calls"] += 1
                if len(self._stack) > 1:
                    self._stack[-2][1] += elapsed
            except Exception as error:
                self._failure = str(error)
                if original is None:
                    raise
                if hasattr(original, "add_note"):
                    original.add_note("Callback cost measurement also failed: " + str(error))
        finally:
            self._stack.pop()

    @contextmanager
    def measure_gc(self):
        """Measure synchronous GC on this thread; never change GC scheduling.

        Wrap only the timed cycle. Python ignores exceptions from GC callbacks,
        so malformed notifications latch an error for result(), not gameplay.
        """
        if getattr(self, "_gc_active", False):
            raise ValueError("GC measurement scope is already active")
        self._gc_active = True
        owner = threading.get_ident()
        pending = None

        def observe(phase, info):
            nonlocal pending
            if threading.get_ident() != owner:
                return
            try:
                generation = info.get("generation")
                if type(generation) is not int or generation not in (0, 1, 2):
                    raise ValueError("invalid GC generation")
                if phase == "start":
                    if pending is not None:
                        raise ValueError("nested GC start notification")
                    timing = self._measure("gc:generation-" + str(generation))
                    timing.__enter__()
                    pending = (generation, timing)
                elif phase == "stop":
                    if pending is None or pending[0] != generation:
                        raise ValueError("unmatched GC stop notification")
                    _, timing = pending
                    pending = None
                    timing.__exit__(None, None, None)
                else:
                    raise ValueError("invalid GC phase")
            except Exception as error:
                self._failure = str(error)

        gc.callbacks.append(observe)
        try:
            yield
        finally:
            gc.callbacks.remove(observe)
            self._gc_active = False
            if pending is not None:
                _, timing = pending
                # Close the exclusive stack without replacing a native error.
                try:
                    timing.__exit__(None, None, None)
                except Exception as error:
                    self._failure = str(error)
                self._failure = "GC collection did not stop inside measured cycle"

    def result(self, total_cpu_ns):
        if self._failure is not None:
            raise ValueError(self._failure)
        if self._stack:
            raise ValueError("callback cost result requested during a callback")
        categories = {name: dict(row) for name, row in self._categories.items()}
        value = dict(schemaVersion=1, totalCpuNs=total_cpu_ns,
                     measuredCpuNs=sum(row["cpuNs"] for row in categories.values()),
                     categories=categories, scope=SCOPE)
        return validate_callback_costs(value, total_cpu_ns)

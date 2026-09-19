"""Validate physical native cycles without assuming one queue per cycle.

Return ordered (sample, events, finished_intervals) rows. Timing belongs to
physical intervals, never synthesized per-queue slices. A multi-queue cycle's
timing is charged only at its last queue; earlier zero-queue cycles can be
charged at the first following queue. Validation has no measurement effects.
"""
from tools.overworld.devtools_callback_costs import validate_callback_costs
from tools.overworld.devtools_dispatch_counts import validate_dispatch_counts
from tools.overworld.devtools_host_probe import validate_host_probe
from tools.overworld.devtools_phase_timings import validate_phase_timings


def validate_raw_chunk(record, previous):
    def integer(value, label, low=0, high=0xFFFFFFFF):
        if type(value) is not int or not low <= value <= high:
            raise ValueError("invalid " + label)
        return value

    prior_frame = integer(previous.get("frame"), "prior completed frame")
    prior_native = integer(previous.get("nativeCycle"), "prior native cycle")
    samples, intervals, events = (record.get(key) for key in ("samples", "cycleIntervals", "events"))
    completed = integer(record.get("completedGameFrames"), "completed frame count", 1, 600)
    native_count = integer(record.get("nativeCycles"), "native cycle count", 1, completed * 6 + 120)
    if not isinstance(samples, list) or len(samples) != completed \
            or any(not isinstance(s, dict) or type(s.get("fieldAvailable")) is not bool for s in samples) \
            or type(record.get("observedFieldFrames")) is not int \
            or record["observedFieldFrames"] != sum(s["fieldAvailable"] for s in samples) \
            or not isinstance(intervals, list) or len(intervals) != native_count \
            or any(not isinstance(i, dict) for i in intervals) \
            or not isinstance(events, list) or len(events) > 4096:
        raise ValueError("raw chunk has missing samples, cycle intervals or field counts")
    final_frame = prior_frame + completed
    for index, sample in enumerate(samples, 1):
        if integer(sample.get("frame"), "sample frame") != prior_frame + index:
            raise ValueError("raw completed samples skip, duplicate or reverse")
        integer(sample.get("nativeCycle"), "sample native cycle")
    by_frame = {s["frame"]: [] for s in samples}
    for event in events:
        if not isinstance(event, dict) or type(event.get("frame")) is not int or event["frame"] not in by_frame:
            raise ValueError("raw event is outside the observed frames")
        by_frame[event["frame"]].append(event)
    charged = {s["frame"]: [] for s in samples}
    current, idle_cycles, pending = prior_frame, 0, []
    has_dispatches = any("guestDispatches" in i for i in intervals)
    last_dispatch = None
    has_phases = any("nativePhases" in i for i in intervals)
    last_phase = None
    for index, interval in enumerate(intervals, 1):
        integer(interval.get("cpuNs"), "cycle CPU", 1, 10**12)
        integer(interval.get("wallNs"), "cycle wall", 1, 10**12)
        rounding = 0
        if "cpuClockResolutionNs" in interval:
            resolution = interval["cpuClockResolutionNs"]
            if not isinstance(resolution, dict) or set(resolution) != {"process", "thread"}:
                raise ValueError("invalid CPU clock resolution")
            # Each measured delta subtracts two independently rounded reads.
            # This bounds only a diagnostic cross-clock comparison. Retain
            # cpuNs unchanged for every process-CPU pacing threshold.
            rounding = 2 * sum(integer(resolution[name], "CPU clock resolution", 1, 10**6)
                               for name in ("process", "thread"))
        if "threadCpuNs" in interval:
            integer(interval["threadCpuNs"], "cycle thread CPU", 0, interval["cpuNs"] + rounding)
        if any(key in interval for key in ("callbackCostError", "threadCostError", "guestDispatchError", "hostWorkProbeError", "nativePhaseError")):
            raise ValueError("callback cost observation failed")
        if "callbackCosts" in interval:
            validate_callback_costs(interval["callbackCosts"], interval["cpuNs"])
        if "hostWorkProbe" in interval:
            probe = interval["hostWorkProbe"]
            if not isinstance(probe, dict) or set(probe) != {"before", "after"}:
                raise ValueError("invalid host work probe pair")
            validate_host_probe(probe["before"])
            validate_host_probe(probe["after"])
        if has_dispatches:
            counts = validate_dispatch_counts(interval.get("guestDispatches"))
            if last_dispatch is not None and counts["frameSequence"] != last_dispatch + 1:
                raise ValueError("guest dispatch sequence skips or reverses")
            last_dispatch = counts["frameSequence"]
        if has_phases:
            phases = validate_phase_timings(interval.get("nativePhases"), cpu_ns=interval["cpuNs"])
            sequence = phases["frameSequence"]
            if last_phase is not None and sequence != last_phase + 1:
                raise ValueError("native phase sequence skips or reverses")
            if has_dispatches and sequence != last_dispatch:
                raise ValueError("native phase and dispatch sequences differ")
            last_phase = sequence
        end = integer(interval.get("completedGameFrame"), "cycle queue endpoint", current, final_frame)
        if end == current:
            idle_cycles += 1
            if idle_cycles >= 120:
                raise ValueError("no completed queue for120 native cycles")
            pending.append(interval)
            continue
        idle_cycles = 0
        for frame in range(current + 1, end + 1):
            if samples[frame - prior_frame - 1]["nativeCycle"] != prior_native + index:
                raise ValueError("raw native cycle count differs from the coherent sample clock")
        charged[current + 1].extend(pending)
        pending = []
        charged[end].append(interval)
        current = end
    if current != final_frame or pending:
        raise ValueError("native intervals do not end at the final sampled queue")
    return [(sample, by_frame[sample["frame"]], charged[sample["frame"]]) for sample in samples]

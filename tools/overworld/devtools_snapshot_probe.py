"""Measure the real paused snapshot reader; never advance or credit gameplay.

Only the snapshot call is timed. Serialization and equality checks are outside
that bracket. Native memory reads retain the normal CDLL transport.
"""
import hashlib
import json
import time


def probe_snapshot(session, args):
    if type(args) is not dict or set(args) - {"iterations"}:
        raise ValueError("invalid snapshot probe arguments")
    iterations = args.get("iterations", 128)
    if type(iterations) is not int or not 1 <= iterations <= 256:
        raise ValueError("snapshot probe iterations must be 1..256")
    emu = session.emu
    if emu is None or not getattr(emu, "handle", None):
        raise ValueError("snapshot probe requires an open paused core")
    if getattr(session, "native_bridge_active", False) or getattr(session, "pending_samples", None) is not None:
        raise ValueError("snapshot probe requires no active step or bridge")
    frame, cycle = session.completed_frames, session.rt.EXECUTED_FRAME_COUNT
    if any(type(v) is not int or v < 0 for v in (frame, cycle)):
        raise ValueError("invalid snapshot probe game clocks")
    original_call = emu.call
    had_override = "call" in vars(emu)
    counters = dict(readCalls=0, readBytes=0)
    forbidden = None

    def read_only_call(name, *values):
        nonlocal forbidden
        if name != "md_read_bytes":
            forbidden = forbidden or ValueError("snapshot probe forbidden native call: " + str(name))
            raise forbidden
        if len(values) != 4 or type(values[3]) is not int or not 0 <= values[3] <= 0x1000000:
            raise ValueError("snapshot probe invalid native read")
        counters["readCalls"] += 1
        counters["readBytes"] += values[3]
        return original_call(name, *values)

    def unchanged():
        if session.emu is not emu or session.completed_frames != frame or session.rt.EXECUTED_FRAME_COUNT != cycle:
            raise ValueError("snapshot probe game clocks or core changed")

    baseline = None
    intervals = []
    emu.call = read_only_call
    try:
        for _ in range(iterations):
            unchanged()
            counters.update(readCalls=0, readBytes=0)
            wall_start = time.perf_counter_ns()
            cpu_start = time.process_time_ns()
            thread_start = time.thread_time_ns()
            value = session._snapshot(0, details=False)
            thread_end = time.thread_time_ns()
            cpu_end = time.process_time_ns()
            wall_end = time.perf_counter_ns()
            if forbidden is not None:
                raise forbidden
            unchanged()
            clocks = ((cpu_start, cpu_end), (thread_start, thread_end), (wall_start, wall_end))
            if any(type(v) is not int or v < 0 for pair in clocks for v in pair) or any(end < start for start, end in clocks):
                raise ValueError("snapshot probe invalid host clocks")
            encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            if len(encoded) > 8 * 1024 * 1024:
                raise ValueError("snapshot probe output exceeds 8MiB")
            if baseline is None:
                baseline = encoded
            elif encoded != baseline:
                raise ValueError("snapshot probe output changed")
            intervals.append(dict(cpuNs=cpu_end-cpu_start, threadCpuNs=thread_end-thread_start,
                                  wallNs=wall_end-wall_start, **counters))
        unchanged()
    finally:
        if had_override:
            emu.call = original_call
        else:
            del emu.call
    return dict(schemaVersion=1, scope="paused-snapshot-reader-diagnostic", acceptedProof=False,
                proofStatus="diagnostic-only", frame=frame, nativeCycle=cycle,
                iterations=iterations, snapshotsEqual=True, gameClocksUnchanged=True,
                snapshotSha256=hashlib.sha256(baseline).hexdigest(), snapshotBytes=len(baseline),
                intervals=intervals)

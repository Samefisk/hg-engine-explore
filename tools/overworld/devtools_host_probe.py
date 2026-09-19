"""Small fixed-work thread CPU probe; not guest timing or acceptance credit."""
import time

ITERATIONS = 64
EXPECTED_RESULT = 3263322488
MAX_CPU_NS = 10**12
SCOPE = "fixed-work-host-thread-diagnostic-not-guest-timing"


def validate_host_probe(value):
    """Return the original receipt, or reject incomplete/changed measurements."""
    if type(value) is not dict or set(value) != {
            "version", "iterations", "result", "cpuNs", "scope"}:
        raise ValueError("invalid host probe schema")
    for name, expected in (("version", 1), ("iterations", ITERATIONS),
                           ("result", EXPECTED_RESULT)):
        if type(value[name]) is not int or value[name] != expected:
            raise ValueError("invalid host probe " + name)
    if type(value["cpuNs"]) is not int or not 0 <= value["cpuNs"] <= MAX_CPU_NS:
        raise ValueError("invalid host probe CPU time")
    if value["scope"] != SCOPE:
        raise ValueError("invalid host probe scope")
    return value


def measure_host_probe(clock=None):
    """Two clock reads around 64 fixed four-operation integer updates.

    No CPU time is subtracted from another measurement. A changed result or
    clock fault produces no receipt. The caller owns the measurement boundary.
    """
    if clock is None:
        clock = time.thread_time_ns
    value = 0x12345678
    start = clock()
    for _ in range(ITERATIONS):
        value = ((value ^ 0x9E3779B9) * 1664525 + 1013904223) & 0xFFFFFFFF
    end = clock()
    if type(start) is not int or type(end) is not int or start < 0 or end < start:
        raise ValueError("invalid host probe clock")
    return validate_host_probe(dict(version=1, iterations=ITERATIONS,
        result=value, cpuNs=end-start, scope=SCOPE))

"""Native phase attribution only; never subtract it from pacing checks."""

SCOPE = "native-exclusive-thread-cpu-diagnostic-v2"
PHASES = ("nonRender", "render3d", "render2d")


def validate_phase_timings(value, *, cpu_ns=None, require_complete=True):
    if not isinstance(value, dict) or set(value) != {
            "version", "enabled", "complete", "invalid", "frameSequence", "phases", "scope"}:
        raise ValueError("invalid native phase schema")
    if type(value["version"]) is not int or value["version"] != 2 or value["scope"] != SCOPE:
        raise ValueError("invalid native phase version or scope")
    if any(type(value[key]) is not bool for key in ("enabled", "complete", "invalid")):
        raise ValueError("invalid native phase flags")
    if type(value["frameSequence"]) is not int or not 0 <= value["frameSequence"] <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("invalid native phase sequence")
    if require_complete and (not value["enabled"] or not value["complete"] or value["invalid"]
                             or not value["frameSequence"]):
        raise ValueError("native phase frame incomplete or invalid")
    phases = value["phases"]
    if not isinstance(phases, dict) or set(phases) != set(PHASES):
        raise ValueError("invalid native phase names")
    total = 0
    for phase in phases.values():
        if not isinstance(phase, dict) or set(phase) != {"cpuNs", "calls"}:
            raise ValueError("invalid native phase entry")
        for key, high in (("cpuNs", 10**12), ("calls", 100000)):
            if type(phase[key]) is not int or not 0 <= phase[key] <= high:
                raise ValueError("invalid native phase " + key)
        if not phase["calls"] and phase["cpuNs"]:
            raise ValueError("native phase time without a call")
        total += phase["cpuNs"]
    if cpu_ns is not None and (type(cpu_ns) is not int or total > cpu_ns):
        raise ValueError("native phase costs exceed cycle CPU")
    return value

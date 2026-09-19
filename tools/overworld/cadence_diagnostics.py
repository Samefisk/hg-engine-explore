"""Read-only guest queue cadence from retained shared-tool memory data.

This is a diagnostic, not acceptance. A native cycle is one RunFrame bin;
its phase within that bin is unknown. Host CPU time is not guest time.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .devtools_evidence_stream import MAX_LINE_BYTES, MAX_ROWS, open_observations


# Symptom-specific full-route budget: five measured native frame periods.
# This is not a universal scheduler or frame-time threshold.
UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS = 5 * 1120380


def _queue_clock(sample):
    if "guestQueueClock" not in sample:
        return None
    value = sample["guestQueueClock"]
    if not isinstance(value, dict) or type(value.get("version")) is not int \
            or value["version"] != 1 or value.get("running") is not True \
            or value.get("scope") != "nds-scheduler-ticks-not-cpu-or-instructions" \
            or any(type(value.get(key)) is not int or not 0 <= value[key] < (1 << 64)
                   for key in ("arm9Timestamp", "arm7Timestamp", "frameSequence")):
        raise ValueError("invalid guest queue clock")
    return value


def _median(histogram, count):
    if not count:
        return None
    positions = ((count - 1) // 2, count // 2)
    total, selected = 0, []
    for value, frequency in sorted(histogram.items()):
        selected.extend(value for position in positions if total <= position < total + frequency)
        total += frequency
        if len(selected) == 2:
            return (selected[0] + selected[1]) / 2 if count % 2 == 0 else selected[0]


def summarize(rows):
    previous = None
    two_queue_start = None
    histogram = Counter()
    breaks = Counter()
    severe = []
    exact_histogram = Counter()
    exact_top = []
    two_queue_top = []
    exact_count = missing_clocks = 0
    eligible_two_queue = exact_two_queue = missing_clock_triples = 0
    samples = pairs = cumulative = 0
    for row_index, row in enumerate(rows):
        if row_index >= MAX_ROWS:
            raise ValueError("too many observation rows")
        if row.get("phase") != "observe":
            previous = None
            two_queue_start = None
            continue
        # Commands/prepared actions are not continuous normal guest execution.
        if "command" in row or "boundarySnapshot" in row:
            previous = None
            two_queue_start = None
            continue
        for current in row.get("samples", []):
            samples += 1
            if samples > MAX_ROWS:
                raise ValueError("too many observation samples")
            current_clock = _queue_clock(current)
            for key in ("frame", "nativeCycle"):
                if type(current.get(key)) is not int or current[key] < 0:
                    raise ValueError("missing or invalid " + key)
            control = current.get("fieldControl", {})
            eligible = (current.get("fieldAvailable") is True
                and current.get("observationBoundary") == "main-task-queue-completion"
                and type(control.get("fieldPointer")) is int and control["fieldPointer"] > 0
                and control.get("taskPointer") == 0
                and isinstance(current.get("context"), dict) and bool(current["context"]))
            if not eligible:
                breaks["field-or-boundary-unavailable"] += 1
                previous = None
                two_queue_start = None
                continue
            if previous is not None:
                if current["frame"] != previous["frame"] + 1:
                    breaks["missing-or-repeated-sample"] += 1
                    two_queue_start = None
                elif current["context"] != previous["context"] or control != previous["fieldControl"]:
                    breaks["context-or-control-change"] += 1
                    two_queue_start = None
                else:
                    delta = current["nativeCycle"] - previous["nativeCycle"]
                    if delta < 0:
                        raise ValueError("native clock moved backwards")
                    pairs += 1
                    histogram[delta] += 1
                    cumulative += delta - 2
                    previous_clock = _queue_clock(previous)
                    if previous_clock is None or current_clock is None:
                        missing_clocks += 1
                    else:
                        if any(current_clock[key] < previous_clock[key] for key in
                               ("arm9Timestamp", "arm7Timestamp", "frameSequence")):
                            raise ValueError("guest queue clock moved backwards")
                        elapsed = current_clock["arm9Timestamp"] - previous_clock["arm9Timestamp"]
                        exact_count += 1
                        exact_histogram[elapsed] += 1
                        exact_top.append({"row": row_index, "action": row.get("action"),
                            "frames": [previous["frame"], current["frame"]],
                            "nativeCycles": [previous["nativeCycle"], current["nativeCycle"]],
                            "nativeFrameBins": delta, "arm9Ticks": elapsed,
                            "context": dict(current["context"])})
                        exact_top.sort(key=lambda item: item["arm9Ticks"], reverse=True)
                        del exact_top[8:]
                    if two_queue_start is not None:
                        eligible_two_queue += 1
                        start_clock = _queue_clock(two_queue_start)
                        if start_clock is None or previous_clock is None or current_clock is None:
                            missing_clock_triples += 1
                        else:
                            elapsed_two_queue = (current_clock["arm9Timestamp"]
                                                 - start_clock["arm9Timestamp"])
                            exact_two_queue += 1
                            two_queue_top.append({"row": row_index, "action": row.get("action"),
                                "frames": [two_queue_start["frame"], current["frame"]],
                                "nativeCycles": [two_queue_start["nativeCycle"],
                                                 current["nativeCycle"]],
                                "nativeFrameBins": (current["nativeCycle"]
                                                    - two_queue_start["nativeCycle"]),
                                "arm9Ticks": elapsed_two_queue,
                                "context": dict(current["context"])})
                            two_queue_top.sort(key=lambda item: item["arm9Ticks"], reverse=True)
                            del two_queue_top[8:]
                    two_queue_start = previous
                    if delta >= 4:
                        if len(severe) >= 256:
                            raise ValueError("long-gap detail limit exceeded")
                        severe.append({"row": row_index, "action": row.get("action"),
                            "frames": [previous["frame"], current["frame"]],
                            "nativeCycles": [previous["nativeCycle"], current["nativeCycle"]],
                            "nativeFrameBins": delta,
                            "conditionalElapsedFrameLowerBoundExclusive": delta - 1,
                            "context": current["context"],
                            "playerBefore": previous.get("player"),
                            "playerAfter": current.get("player")})
            previous = current
    if not pairs:
        raise ValueError("no continuous active-field sample pairs")
    return {"schema": "guest-queue-cadence-diagnostic-v1", "acceptedProof": False,
        "scope": "retained main-queue completion bins; not rendered-frame or cause proof",
        "boundAssumption": "successful normal one-frame melonDS calls; artifact hashing does not authenticate backend or sleep state",
        "samples": samples, "continuousPairs": pairs, "pairBreaks": dict(breaks),
        "nativeFrameBinHistogram": dict(sorted(histogram.items())),
        "sumPairExcessBinsAgainstTwoPerQueue": cumulative,
        "guestQueueClock": {"scope": "exact ARM9 scheduler intervals; no duration threshold or acceptance",
            "observedIntervals": exact_count, "missingClockPairs": missing_clocks,
            "coverageComplete": missing_clocks == 0,
            "minimumArm9Ticks": min(exact_histogram) if exact_count else None,
            "medianArm9Ticks": _median(exact_histogram, exact_count),
            "maximumArm9Ticks": max(exact_histogram) if exact_count else None,
            "topIntervals": exact_top,
            "eligibleTwoQueueIntervals": eligible_two_queue,
            "observedTwoQueueIntervals": exact_two_queue,
            "missingClockTriples": missing_clock_triples,
            "twoQueueCoverageComplete": (eligible_two_queue > 0
                                         and missing_clock_triples == 0),
            "maximumTwoQueueArm9Ticks": (two_queue_top[0]["arm9Ticks"]
                                         if two_queue_top else None),
            "topTwoQueueIntervals": two_queue_top},
        "longGaps": severe}


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_manifest(path):
    path = Path(path).resolve(strict=True)
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("state") not in ("completed", "failed", "canceled"):
        raise ValueError("requires a terminal shared test manifest")
    artifact = manifest["observationsArtifact"]
    evidence = Path(artifact["path"]).resolve(strict=True)
    if not evidence.is_relative_to(path.parent) or not evidence.is_file():
        raise ValueError("observations are not owned by this run")
    if evidence.stat().st_size != artifact["size"] or _hash(evidence) != artifact["sha256"]:
        raise ValueError("observation identity differs")

    def rows():
        with open_observations(evidence) as stream:
            for index in range(MAX_ROWS + 1):
                line = stream.readline(MAX_LINE_BYTES + 1)
                if not line:
                    return
                if index >= MAX_ROWS or len(line.encode("utf-8")) > MAX_LINE_BYTES:
                    raise ValueError("observation stream bound exceeded")
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("observation row is not an object")
                yield row

    result = summarize(rows())
    if path.read_bytes() != manifest_bytes or _hash(evidence) != artifact["sha256"]:
        raise ValueError("evidence changed during diagnosis")
    return {**result, "runId": manifest["runId"], "rom": manifest.get("identity", {}).get("rom"),
            "observationsSha256": artifact["sha256"]}


def _max_two_queue_ticks_check(result, budget):
    clock = result["guestQueueClock"]
    maximum = clock["maximumTwoQueueArm9Ticks"]
    if not clock["eligibleTwoQueueIntervals"]:
        reason = "no-eligible-triples"
    elif not clock["twoQueueCoverageComplete"]:
        reason = "missing-clock-triples"
    elif maximum > budget:
        reason = "budget-exceeded"
    else:
        reason = "within-budget"
    return {"budgetArm9Ticks": budget, "maximumTwoQueueArm9Ticks": maximum,
            "passed": reason == "within-budget", "reason": reason}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--max-two-queue-ticks", type=int, metavar="N",
                        help="diagnostic failure budget for two consecutive queue intervals")
    args = parser.parse_args(argv)
    if args.max_two_queue_ticks is not None and args.max_two_queue_ticks < 0:
        parser.error("--max-two-queue-ticks must be nonnegative")
    result = inspect_manifest(args.manifest)
    status = 0
    if args.max_two_queue_ticks is not None:
        check = _max_two_queue_ticks_check(result, args.max_two_queue_ticks)
        result["maxTwoQueueTicksCheck"] = check
        status = 0 if check["passed"] else 1
    print(json.dumps(result, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

"""Pure fail-closed checks used by overworld cadence runtime scenarios."""

from __future__ import annotations

import statistics
from typing import Any, Iterable
from tools.overworld.spawn_identity import live_spawn_flags


def counts_as_active_motion_frame(
    motion_mode: int,
    expected_motion_mode: int,
) -> bool:
    """Count proof time only while the requested engine motion is active."""
    return motion_mode == expected_motion_mode


def guest_queue_delay(previous, current):
    """Conservative missed-update witness from authenticated RunFrame bins.

    Stock main.c normally targets two VBlanks per queue. Four bins between
    consecutive queue endpoints mean more than three full frame periods,
    even with unknown endpoint phase. A3/1 phase pair is not rejected.
    The caller owns native backend, dense sample and normal input validation.
    """
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return None
    for value in (previous, current):
        if value.get("fieldAvailable") is not True \
                or value.get("observationBoundary") != "main-task-queue-completion":
            return None
        control = value.get("fieldControl")
        if not isinstance(control, dict) \
                or type(control.get("fieldPointer")) is not int or control["fieldPointer"] <= 0 \
                or type(control.get("taskPointer")) is not int or control["taskPointer"] < 0:
            raise ValueError("missing or invalid guest queue control identity")
        if control["taskPointer"] != 0:
            return None
        if not value.get("context"):
            raise ValueError("missing guest queue context")
        for key in ("frame", "nativeCycle"):
            if type(value.get(key)) is not int or value[key] < 0:
                raise ValueError("invalid guest queue clock")
    if current["frame"] != previous["frame"] + 1 \
            or current["context"] != previous["context"] \
            or current["fieldControl"] != previous["fieldControl"]:
        return None
    delta = current["nativeCycle"] - previous["nativeCycle"]
    if delta < 0:
        raise ValueError("guest queue clock moved backwards")
    if delta >= 4:
        return {"fromFrame": previous["frame"], "toFrame": current["frame"],
                "fromNativeCycle": previous["nativeCycle"],
                "toNativeCycle": current["nativeCycle"], "nativeFrameBins": delta,
                "context": dict(current["context"])}
    return None


def classify_frame_hitches(
    samples: Iterable[int],
    ratio_per_mille: int,
    extra_ns: int,
) -> dict[str, Any]:
    """Classify every sample; there is no warm-up or allowed hitch count."""
    values = list(samples)
    median_ns = int(statistics.median(values)) if values else 0
    hitch_frames = [
        index
        for index, sample in enumerate(values)
        if median_ns > 0
        and sample * 1000 >= median_ns * ratio_per_mille
        and sample - median_ns >= extra_ns
    ]
    return {
        "sampleCount": len(values),
        "medianNs": median_ns,
        "maximumNs": max(values) if values else 0,
        "hitchRatioPerMille": ratio_per_mille,
        "hitchExtraNs": extra_ns,
        "hitchFrames": hitch_frames,
        "hitchCount": len(hitch_frames),
    }


def classify_player_motion(
    samples: Iterable[dict[str, Any]],
    start_render: Iterable[int],
    target_render: Iterable[int],
    *,
    maximum_acceptance_frames: int,
    maximum_start_frames: int,
    maximum_settle_frames: int,
) -> dict[str, Any]:
    """Classify one player step from per-emulated-frame engine state."""
    values = list(samples)
    start = list(start_render)
    target = list(target_render)
    accepted = [
        index for index, sample in enumerate(values)
        if sample.get("accepted") is True
    ]
    acceptance_frames = accepted[0] + 1 if accepted else len(values) + 1
    positions = [start] + [list(sample["render"]) for sample in values]
    changed = [
        index for index in range(1, len(positions))
        if positions[index] != positions[index - 1]
    ]
    first_change = changed[0] if changed else None
    last_change = changed[-1] if changed else None
    accepted_position = accepted[0] + 1 if accepted else None
    start_delay_frames = (
        max(0, first_change - accepted_position)
        if first_change is not None and accepted_position is not None
        else len(values) + 1
    )
    interior_stalls = 0
    render_regressions = 0
    active_frames = 0
    if first_change is not None and last_change is not None:
        delta_x = target[0] - start[0]
        delta_z = target[1] - start[1]
        active_frames = last_change - first_change + 1
        for index in range(first_change + 1, last_change + 1):
            progress = (
                (positions[index][0] - positions[index - 1][0]) * delta_x
                + (positions[index][1] - positions[index - 1][1]) * delta_z
            )
            if progress == 0:
                interior_stalls += 1
            elif progress < 0:
                render_regressions += 1
    settle_frames = (
        len(values) - last_change if last_change is not None else len(values)
    )
    return {
        "sampleCount": len(values),
        "acceptanceFrames": acceptance_frames,
        "acceptanceStall": int(
            not accepted or acceptance_frames > maximum_acceptance_frames
        ),
        "startDelayFrames": start_delay_frames,
        "startStall": int(start_delay_frames > maximum_start_frames),
        "firstChange": first_change,
        "lastChange": last_change,
        "activeFrames": active_frames,
        "interiorStalls": interior_stalls,
        "renderRegressions": render_regressions,
        "settleFrames": settle_frames,
        "settleStall": int(
            last_change is None or settle_frames > maximum_settle_frames
        ),
        "reachedTarget": bool(positions and positions[-1] == target),
    }


def count_player_timing_mismatches(
    signatures: Iterable[Iterable[int]],
) -> int:
    """Require every repeated step to retain one request-to-settle cadence."""
    values = [list(signature) for signature in signatures]
    if not values:
        return 1
    return sum(signature != values[0] for signature in values[1:])


def count_player_step_callback_mismatches(
    callback_counts: Iterable[int],
    authored_motions: int,
    completed_motions: int,
) -> int:
    """Reject missing, repeated, or padded player step callbacks."""
    values = list(callback_counts)
    return (
        sum(value != 1 for value in values)
        + abs(len(values) - completed_motions)
        + abs(sum(values) - authored_motions)
        + abs(completed_motions - authored_motions)
    )


def actor_identity_is_current(
    *,
    role: str,
    species: int,
    slot: int,
    actor: dict[str, Any],
    object_pointer: int,
    initial_handle: dict[str, Any],
    initial_subject: int,
    initial_object: int,
    source_record: dict[str, Any],
    live_object: dict[str, Any],
    acquisition_passed: bool,
) -> bool:
    """Require one unchanged actor, source slot, and live map object identity."""
    generation = initial_handle.get("encounterGeneration", 0)
    base_identity = (
        acquisition_passed
        and actor.get("active") is True
        and actor.get("role") == role
        and actor.get("species") == species
        and actor.get("presentationAttached") is True
        and actor.get("handle") == initial_handle
        and initial_handle.get("slot") == slot
        and actor.get("subjectIdentity") == initial_subject
        and object_pointer == initial_object
        and object_pointer != 0
        and generation > 0
        and live_spawn_flags(source_record.get("active"))
        and source_record.get("species") == species
        and source_record.get("object") == initial_object
        and source_record.get("encounter_generation") == generation
        and live_object.get("pointer") == initial_object
        and live_object.get("in_manager") is True
        and live_object.get("active") is True
        and live_object.get("object_id") == source_record.get("object_id")
        and live_object.get("spawn_object_id") == source_record.get("object_id")
        and live_object.get("object_map_id") == source_record.get("map_id")
        and live_object.get("spawn_map_id") == source_record.get("map_id")
        and live_object.get("current_map_id") == source_record.get("map_id")
        and live_object.get("encounter_generation") == generation
    )
    if role == "FOLLOWER":
        return base_identity and slot == 7
    if role == "WILD":
        return base_identity and 0 <= slot < 6
    return False

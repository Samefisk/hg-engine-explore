"""Acceptance rows and copied-data controls for incremental spawn work."""
from copy import deepcopy

from tools.overworld.devtools_spawn_work_budget_measurement import (
    ENTRY_OFFSCREEN_MARGIN_TILES,
    ENTRY_TARGET_MAX_DISTANCE_TILES,
    EXPECTED_SCAN_CANDIDATES,
    EXPECTED_DESTINATION_UPDATES,
    KIND,
    MAX_CANDIDATE_QUERIES_PER_UPDATE,
    MAX_RESUMED_FINALIZER_ARM9_TICKS,
    MINIMUM_ENTRY_PROGRESS,
    POST_SPAWN_PACING_SAMPLES,
    MINIMUM_INTERIOR_MOVING_FRAMES,
    REQUIREMENT,
    require,
)
from tools.overworld.devtools_main_loop_probe import (
    MAX_ZERO_STUTTER_ARM9_TICKS,
    NORMAL_MAIN_LOOP_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
)


CLAIMS = (
    "live-actor-identity",
    "profile-resolution",
    "population-bounds",
    "engine-boundary",
    "logical-commit",
    "rendered-motion",
    "frame-pacing",
)
FAULTS = (
    "spawn-work-budget-missing-queue",
    "spawn-work-budget-over-query-batch",
    "spawn-work-budget-missing-update",
    "spawn-work-budget-repeated-resolution",
    "spawn-work-budget-repeated-metadata",
    "spawn-work-budget-repeated-class-selection",
    "spawn-work-budget-slow-resumed-finalizer",
    "spawn-work-budget-wrong-profile-source",
    "spawn-work-budget-late-main-loop",
    "spawn-work-budget-missing-post-spawn-pacing",
    "spawn-work-budget-missing-natural-spawn",
    "spawn-work-budget-entry-special-path",
    "spawn-work-budget-entry-onscreen-origin",
    "spawn-work-budget-player-render-stall",
)


def contract():
    return {
        "live-actor-identity": [
            {
                "name": "spawn-work-anchor-identity", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, "FOLLOWER", 56, 1],
            },
            {
                "name": "spawn-work-entry-actor-identity", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [1, "WILD", 163, 1],
            },
        ],
        "profile-resolution": [
            {
                "name": "spawn-work-profile-receipt-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 1,
            },
            {
                "name": "spawn-work-metadata-receipt-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 1,
            },
            {
                "name": "spawn-work-class-selection-receipt-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 1,
            },
        ],
        "population-bounds": [
            {
                "name": "spawn-work-maximum-candidate-queries", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": MAX_CANDIDATE_QUERIES_PER_UPDATE,
            },
            {
                "name": "spawn-work-total-candidate-queries", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": EXPECTED_SCAN_CANDIDATES,
            },
        ],
        "engine-boundary": [
            {
                "name": "spawn-work-destination-update-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": EXPECTED_DESTINATION_UPDATES,
            },
            {
                "name": "spawn-work-completed-scan-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 1,
            },
            {
                "name": "spawn-work-successful-spawn-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 1,
            },
            {
                "name": "spawn-work-maximum-resumed-finalizer-arm9-ticks",
                "operator": "lte", "type": "integer",
                "validator": "meaningful-observation",
                "maximum": MAX_RESUMED_FINALIZER_ARM9_TICKS,
            },
        ],
        "logical-commit": [
            {
                "name": "spawn-work-entry-target-distance", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": ENTRY_TARGET_MAX_DISTANCE_TILES,
            },
            {
                "name": "spawn-work-entry-offscreen-clearance", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": ENTRY_OFFSCREEN_MARGIN_TILES,
            },
            {
                "name": "spawn-work-entry-normal-hop-evidence", "operator": "eq",
                "type": "array", "validator": "meaningful-observation",
                "expected": [4, 1],
            },
            {
                "name": "spawn-work-entry-distance-progress", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": MINIMUM_ENTRY_PROGRESS,
            },
        ],
        "rendered-motion": [{
            "name": "spawn-work-entry-render-displacement", "operator": "gte",
            "type": "integer", "validator": "meaningful-observation",
            "minimum": MINIMUM_ENTRY_PROGRESS,
        }],
        "frame-pacing": [
            {
                "name": "spawn-work-late-main-loop-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 0,
            },
            {
                "name": "spawn-work-maximum-main-loop-arm9-ticks", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": MAX_ZERO_STUTTER_ARM9_TICKS,
            },
            {
                "name": "spawn-work-maximum-main-loop-native-cycles", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            },
            {
                "name": "spawn-work-maximum-main-loop-frame-sequence", "operator": "lte",
                "type": "integer", "validator": "meaningful-observation",
                "maximum": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            },
            {
                "name": "spawn-work-post-spawn-pacing-count", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": POST_SPAWN_PACING_SAMPLES,
            },
            {
                "name": "spawn-work-player-interior-moving-frames", "operator": "gte",
                "type": "integer", "validator": "meaningful-observation",
                "minimum": MINIMUM_INTERIOR_MOVING_FRAMES,
            },
            {
                "name": "spawn-work-player-interior-render-stall-count", "operator": "eq",
                "type": "integer", "validator": "meaningful-observation",
                "expected": 0,
            },
        ],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    attempt = meter.get("attempt") or {}
    entry = meter.get("entry") or {}
    pacing = meter.get("pacing") or {}
    subject = meter.get("subject") or {}
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == []
            and meter.get("requirements") == [REQUIREMENT]
            and attempt.get("completed") is True
            and attempt.get("callCount") == EXPECTED_DESTINATION_UPDATES
            and attempt.get("finalizerCallCount") == EXPECTED_DESTINATION_UPDATES + 1
            and type(attempt.get("candidateQueryCount")) is int
            and 0 <= attempt["candidateQueryCount"] <= EXPECTED_SCAN_CANDIDATES
            and attempt.get("maxQueriesPerUpdate") == MAX_CANDIDATE_QUERIES_PER_UPDATE
            and attempt.get("resolverReceiptCount") == 1
            and attempt.get("metadataReceiptCount") == 1
            and attempt.get("classSelectionReceiptCount") == 1
            and attempt.get("successfulSpawnCount") == 1
            and meter.get("contextTransition", {}).get("from", {}).get("mapId") == 33
            and meter.get("contextTransition", {}).get("to", {}).get("mapId") == 67
            and entry.get("locomotion") == 4
            and entry.get("species") == 163
            and type(entry.get("targetDistance")) is int
            and 1 <= entry["targetDistance"] <= ENTRY_TARGET_MAX_DISTANCE_TILES
            and type(entry.get("offscreenClearance")) is int
            and entry["offscreenClearance"] >= ENTRY_OFFSCREEN_MARGIN_TILES
            and entry.get("spawnHopObserved") is True
            and entry.get("ownerHopFrames", 0) > 0
            and entry.get("distanceProgress", 0) >= MINIMUM_ENTRY_PROGRESS
            and entry.get("maximumRenderDisplacement", 0) >= MINIMUM_ENTRY_PROGRESS
            and type(attempt.get("maxResumedFinalizerArm9Ticks")) is int
            and attempt["maxResumedFinalizerArm9Ticks"] <= MAX_RESUMED_FINALIZER_ARM9_TICKS
            and type(pacing.get("sampleCount")) is int and pacing["sampleCount"] >= 2
            and type(pacing.get("intervalCount")) is int and pacing["intervalCount"] >= 1
            and pacing.get("lateMainLoopCount") == 0
            and pacing.get("maximumArm9Ticks") <= MAX_ZERO_STUTTER_ARM9_TICKS
            and pacing.get("maximumNativeCycles") <= NORMAL_MAIN_LOOP_NATIVE_CYCLES
            and pacing.get("maximumFrameSequence") <= NORMAL_MAIN_LOOP_NATIVE_CYCLES
            and pacing.get("postSpawnSampleCount") >= POST_SPAWN_PACING_SAMPLES
            and pacing.get("interiorMovingFrameCount") >= MINIMUM_INTERIOR_MOVING_FRAMES
            and pacing.get("interiorRenderStallCount") == 0
            and subject.get("species") == 56
            and subject.get("role") == "FOLLOWER",
            "spawn-work proof lacks one complete bounded destination scan")
    require(record.get("sessionCleanup") == {
        "sessionId": record.get("sessionId"), "closed": True, "errors": [],
    }, "spawn-work private session did not close cleanly")
    return [
        {
            "claim": "live-actor-identity", "name": "spawn-work-anchor-identity",
            "value": [1, subject["role"], subject["species"],
                      int(subject.get("identityVerified") is True)],
            "operator": "eq", "expected": [1, "FOLLOWER", 56, 1], "passed": True,
        },
        {
            "claim": "live-actor-identity", "name": "spawn-work-entry-actor-identity",
            "value": [1, "WILD", entry["species"],
                      int(bool(entry.get("subjectIdentity")))],
            "operator": "eq", "expected": [1, "WILD", 163, 1],
            "passed": entry["species"] == 163 and bool(entry.get("subjectIdentity")),
        },
        {
            "claim": "profile-resolution", "name": "spawn-work-profile-receipt-count",
            "value": attempt["resolverReceiptCount"], "operator": "eq", "expected": 1,
            "passed": attempt["resolverReceiptCount"] == 1,
        },
        {
            "claim": "profile-resolution", "name": "spawn-work-metadata-receipt-count",
            "value": attempt["metadataReceiptCount"], "operator": "eq", "expected": 1,
            "passed": attempt["metadataReceiptCount"] == 1,
        },
        {
            "claim": "profile-resolution", "name": "spawn-work-class-selection-receipt-count",
            "value": attempt["classSelectionReceiptCount"], "operator": "eq", "expected": 1,
            "passed": attempt["classSelectionReceiptCount"] == 1,
        },
        {
            "claim": "population-bounds", "name": "spawn-work-maximum-candidate-queries",
            "value": attempt["maxQueriesPerUpdate"], "operator": "lte",
            "maximum": MAX_CANDIDATE_QUERIES_PER_UPDATE,
            "passed": attempt["maxQueriesPerUpdate"] <= MAX_CANDIDATE_QUERIES_PER_UPDATE,
        },
        {
            "claim": "population-bounds", "name": "spawn-work-total-candidate-queries",
            "value": attempt["candidateQueryCount"], "operator": "lte",
            "maximum": EXPECTED_SCAN_CANDIDATES,
            "passed": attempt["candidateQueryCount"] <= EXPECTED_SCAN_CANDIDATES,
        },
        {
            "claim": "engine-boundary", "name": "spawn-work-destination-update-count",
            "value": attempt["callCount"], "operator": "eq",
            "expected": EXPECTED_DESTINATION_UPDATES,
            "passed": attempt["callCount"] == EXPECTED_DESTINATION_UPDATES,
        },
        {
            "claim": "engine-boundary", "name": "spawn-work-completed-scan-count",
            "value": 1, "operator": "eq", "expected": 1, "passed": True,
        },
        {
            "claim": "engine-boundary", "name": "spawn-work-successful-spawn-count",
            "value": attempt["successfulSpawnCount"], "operator": "eq", "expected": 1,
            "passed": attempt["successfulSpawnCount"] == 1,
        },
        {
            "claim": "engine-boundary",
            "name": "spawn-work-maximum-resumed-finalizer-arm9-ticks",
            "value": attempt["maxResumedFinalizerArm9Ticks"], "operator": "lte",
            "maximum": MAX_RESUMED_FINALIZER_ARM9_TICKS,
            "passed": attempt["maxResumedFinalizerArm9Ticks"] <= MAX_RESUMED_FINALIZER_ARM9_TICKS,
        },
        {
            "claim": "logical-commit", "name": "spawn-work-entry-target-distance",
            "value": entry["targetDistance"],
            "operator": "lte", "maximum": ENTRY_TARGET_MAX_DISTANCE_TILES,
            "passed": 1 <= entry["targetDistance"] <= ENTRY_TARGET_MAX_DISTANCE_TILES,
        },
        {
            "claim": "logical-commit", "name": "spawn-work-entry-offscreen-clearance",
            "value": entry["offscreenClearance"],
            "operator": "gte", "minimum": ENTRY_OFFSCREEN_MARGIN_TILES,
            "passed": entry["offscreenClearance"] >= ENTRY_OFFSCREEN_MARGIN_TILES,
        },
        {
            "claim": "logical-commit", "name": "spawn-work-entry-normal-hop-evidence",
            "value": [entry["locomotion"], int(entry["spawnHopObserved"])],
            "operator": "eq", "expected": [4, 1],
            "passed": True,
        },
        {
            "claim": "logical-commit", "name": "spawn-work-entry-distance-progress",
            "value": entry["distanceProgress"], "operator": "gte",
            "minimum": MINIMUM_ENTRY_PROGRESS,
            "passed": entry["distanceProgress"] >= MINIMUM_ENTRY_PROGRESS,
        },
        {
            "claim": "rendered-motion", "name": "spawn-work-entry-render-displacement",
            "value": entry["maximumRenderDisplacement"], "operator": "gte",
            "minimum": MINIMUM_ENTRY_PROGRESS,
            "passed": entry["maximumRenderDisplacement"] >= MINIMUM_ENTRY_PROGRESS,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-late-main-loop-count",
            "value": pacing["lateMainLoopCount"], "operator": "eq", "expected": 0,
            "passed": pacing["lateMainLoopCount"] == 0,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-maximum-main-loop-arm9-ticks",
            "value": pacing["maximumArm9Ticks"], "operator": "lte",
            "maximum": MAX_ZERO_STUTTER_ARM9_TICKS,
            "passed": pacing["maximumArm9Ticks"] <= MAX_ZERO_STUTTER_ARM9_TICKS,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-maximum-main-loop-native-cycles",
            "value": pacing["maximumNativeCycles"], "operator": "lte",
            "maximum": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            "passed": pacing["maximumNativeCycles"] <= NORMAL_MAIN_LOOP_NATIVE_CYCLES,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-maximum-main-loop-frame-sequence",
            "value": pacing["maximumFrameSequence"], "operator": "lte",
            "maximum": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
            "passed": pacing["maximumFrameSequence"] <= NORMAL_MAIN_LOOP_NATIVE_CYCLES,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-post-spawn-pacing-count",
            "value": pacing["postSpawnSampleCount"], "operator": "gte",
            "minimum": POST_SPAWN_PACING_SAMPLES,
            "passed": pacing["postSpawnSampleCount"] >= POST_SPAWN_PACING_SAMPLES,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-player-interior-moving-frames",
            "value": pacing["interiorMovingFrameCount"], "operator": "gte",
            "minimum": MINIMUM_INTERIOR_MOVING_FRAMES,
            "passed": pacing["interiorMovingFrameCount"] >= MINIMUM_INTERIOR_MOVING_FRAMES,
        },
        {
            "claim": "frame-pacing", "name": "spawn-work-player-interior-render-stall-count",
            "value": pacing["interiorRenderStallCount"], "operator": "eq", "expected": 0,
            "passed": pacing["interiorRenderStallCount"] == 0,
        },
    ]


class SpawnWorkBudgetNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown spawn-work copied fault")
        self.fault = fault
        self.applied = False
        self.seen_destinations = 0
        self.source_sha256 = None
        self.metadata_template = None
        self.class_selection_template = None
        self.previous_player_pose = None
        self.destination_context_seen = False
        self.strict_pacing_samples = 0

    @staticmethod
    def _destination(event):
        data = event.get("data", {})
        return (event.get("kind") == "native-observation"
                and data.get("observation") == "spawn-destination-search")

    def mutate(self, row, subjects):
        if row.get("phase") != "observe" or self.applied:
            return row
        changed = deepcopy(row)
        events = changed.get("events", [])
        strict_window = self.destination_context_seen
        samples = changed.get("samples", [])
        if any(sample.get("context", {}).get("mapId") == 67
               for sample in samples):
            self.destination_context_seen = True
        if self.fault == "spawn-work-budget-player-render-stall":
            for sample in samples:
                player = sample.get("player", {})
                pose = [player.get("pos_x"), player.get("pos_z")]
                if strict_window and self.previous_player_pose is not None \
                        and (player.get("x") != player.get("x_prev")
                             or player.get("y") != player.get("y_prev")):
                    player["pos_x"], player["pos_z"] = self.previous_player_pose
                    self.applied = True
                    return changed
                if self.destination_context_seen \
                        and all(type(value) is int for value in pose):
                    self.previous_player_pose = pose
        pacing = [event for event in events
                  if event.get("kind") == "native-observation"
                  and event.get("data", {}).get("observation") == "stock-main-loop-pacing"]
        if strict_window:
            self.strict_pacing_samples += len(pacing)
        if self.fault == "spawn-work-budget-late-main-loop" \
                and self.strict_pacing_samples >= 2:
            for event in pacing:
                interval = event["data"].get("intervalFromPrevious")
                if interval is None:
                    continue
                event["data"]["frameCounter"] = 3
                interval["arm9Ticks"] = MAX_ZERO_STUTTER_ARM9_TICKS + 1
                interval["nativeCycles"] = NORMAL_MAIN_LOOP_NATIVE_CYCLES + 1
                self.applied = True
                return changed
        if self.fault == "spawn-work-budget-missing-post-spawn-pacing" \
                and self.seen_destinations == EXPECTED_DESTINATION_UPDATES \
                and not any(self._destination(event) for event in events) and pacing:
            changed["events"] = [event for event in events if event not in pacing]
            self.applied = True
            return changed
        if self.fault == "spawn-work-budget-missing-natural-spawn" \
                and self.seen_destinations == EXPECTED_DESTINATION_UPDATES:
            completed = [event for event in events
                         if event.get("kind") == "native-observation"
                         and event.get("data", {}).get("observation") == "spawn-finalized"
                         and event.get("data", {}).get("returnValue") == 1]
            if completed:
                changed["events"] = [item for item in events
                                     if item.get("data", {}).get("observation")
                                     not in ("spawn-prepared", "spawn-object-create")]
                self.applied = True
                return changed
        if self.fault == "spawn-work-budget-entry-special-path":
            prepared = [event for event in events
                        if event.get("kind") == "native-observation"
                        and event.get("data", {}).get("observation") == "spawn-prepared"]
            if prepared:
                prepared[0]["data"]["startup"]["locomotion"] = 2
                self.applied = True
                return changed
        if self.fault == "spawn-work-budget-entry-onscreen-origin":
            prepared = [event for event in events
                        if event.get("kind") == "native-observation"
                        and event.get("data", {}).get("observation") == "spawn-prepared"]
            creates = [event for event in events
                       if event.get("kind") == "native-observation"
                       and event.get("data", {}).get("observation") == "spawn-object-create"]
            completed = [event for event in events
                         if event.get("kind") == "native-observation"
                         and event.get("data", {}).get("observation") == "spawn-finalized"
                         and event.get("data", {}).get("returnValue") == 1]
            if prepared and creates and completed:
                target = prepared[0]["data"]["startup"]["target"]
                origin = [target[0], target[1] - 1]
                prepared[0]["data"]["startup"]["origin"] = origin
                completed[0]["data"]["startup"]["origin"] = origin
                creates[0]["data"]["arguments"][1:3] = origin
                self.applied = True
                return changed
        for index, event in enumerate(events):
            if not self._destination(event):
                continue
            self.seen_destinations += 1
            data = event["data"]
            finals = [item for item in events
                      if item.get("kind") == "native-observation"
                      and item.get("data", {}).get("observation") == "spawn-finalized"]
            if finals and finals[0]["data"].get("resolverReceipts"):
                self.source_sha256 = finals[0]["data"]["resolverReceipts"][0].get("sourceSha256")
            metadata = [item for item in events
                        if item.get("kind") == "native-observation"
                        and item.get("data", {}).get("observation") == "spawn-metadata"
                        and item.get("data", {}).get("finalizationId") == data.get("finalizationId")]
            class_selections = [item for item in events
                                if item.get("kind") == "native-observation"
                                and item.get("data", {}).get("observation") == "spawn-class-selection"
                                and item.get("data", {}).get("finalizationId") == data.get("finalizationId")]
            if metadata:
                self.metadata_template = deepcopy(metadata[0])
            if class_selections:
                self.class_selection_template = deepcopy(class_selections[0])
            if self.fault == "spawn-work-budget-missing-queue":
                if data.get("candidateQueryCount") != 0:
                    continue
                events[:] = [item for item in events
                             if not (item.get("kind") == "native-observation"
                                     and item.get("data", {}).get("observation") == "spawn-queued")]
            elif self.fault == "spawn-work-budget-over-query-batch":
                if data.get("candidateQueryCount") != MAX_CANDIDATE_QUERIES_PER_UPDATE:
                    continue
                data["candidateQueryCount"] = MAX_CANDIDATE_QUERIES_PER_UPDATE + 1
            elif self.fault == "spawn-work-budget-missing-update":
                if self.seen_destinations != 2:
                    continue
                del events[index]
            elif self.fault == "spawn-work-budget-repeated-resolution":
                if self.seen_destinations != 2:
                    continue
                if (not finals or finals[0]["data"].get("resolverReceipts")
                        or not self.source_sha256):
                    continue
                finals[0]["data"]["resolverReceipts"] = [{
                    "resolved": True,
                    "finalizationId": finals[0]["data"]["finalizationId"],
                    "inputEncounter": deepcopy(finals[0]["data"]["inputEncounter"]),
                    "sourceSha256": self.source_sha256,
                }]
            elif self.fault == "spawn-work-budget-repeated-metadata":
                if self.seen_destinations != 2 or not self.metadata_template:
                    continue
                repeated = deepcopy(self.metadata_template)
                repeated["frame"] = event.get("frame")
                repeated["data"]["finalizationId"] = data["finalizationId"]
                events.append(repeated)
            elif self.fault == "spawn-work-budget-repeated-class-selection":
                if self.seen_destinations != 2 or not self.class_selection_template:
                    continue
                repeated = deepcopy(self.class_selection_template)
                repeated["frame"] = event.get("frame")
                repeated["data"]["finalizationId"] = data["finalizationId"]
                events.append(repeated)
            elif self.fault == "spawn-work-budget-slow-resumed-finalizer":
                if self.seen_destinations != 2 or not finals:
                    continue
                finals[0]["data"]["guestTiming"]["arm9Ticks"] = \
                    MAX_RESUMED_FINALIZER_ARM9_TICKS + 1
            elif self.fault in ("spawn-work-budget-late-main-loop",
                                 "spawn-work-budget-missing-post-spawn-pacing",
                                 "spawn-work-budget-missing-natural-spawn",
                                 "spawn-work-budget-entry-special-path",
                                 "spawn-work-budget-entry-onscreen-origin",
                                 "spawn-work-budget-player-render-stall"):
                continue
            else:
                if not finals or not finals[0]["data"].get("resolverReceipts"):
                    continue
                finals[0]["data"]["resolverReceipts"][-1]["sourceSha256"] = "0" * 64
            self.applied = True
            return changed
        return row


Negative = SpawnWorkBudgetNegative


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False,
            "spawn-work copied control did not fail")
    text = repr(result.get("failures", [])) + repr(
        result.get("measurements", {}).get(KIND, {}).get("failures", []))
    expected = {
        "spawn-work-budget-missing-queue": "scan did not start after the helper-owned queue attempt",
        "spawn-work-budget-over-query-batch": "destination receipt exceeds the candidate batch",
        "spawn-work-budget-missing-update": "queued scan skipped a completed game update",
        "spawn-work-budget-repeated-resolution": "resumed scan repeated profile resolution",
        "spawn-work-budget-repeated-metadata": "resumed scan repeated metadata preparation",
        "spawn-work-budget-repeated-class-selection": "resumed scan repeated class selection",
        "spawn-work-budget-slow-resumed-finalizer": "resumed finalizer exceeds guest work budget",
        "spawn-work-budget-wrong-profile-source": "profile receipt differs from the current source",
        "spawn-work-budget-late-main-loop": "main loop missed normal frame pace",
        "spawn-work-budget-missing-post-spawn-pacing": "lacks one main-loop pacing sample",
        "spawn-work-budget-missing-natural-spawn": "did not create its prepared wild actor",
        "spawn-work-budget-entry-special-path": "entry did not retain its exact A and B",
        "spawn-work-budget-entry-onscreen-origin": "A is not safely outside player view",
        "spawn-work-budget-player-render-stall": "player render froze during admitted movement",
    }[fault]
    require(expected in text,
            "spawn-work copied control failed for an unrelated reason: " + fault)

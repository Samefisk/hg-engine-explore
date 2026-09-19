"""Short live proof for the incremental automatic spawn destination scan."""
from copy import deepcopy

from tools.overworld.devtools_main_loop_probe import (
    MAX_ZERO_STUTTER_ARM9_TICKS,
    NORMAL_MAIN_LOOP_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
    RETURN_SITE,
    SCOPE as MAIN_LOOP_SCOPE,
)


KIND = "spawn-work-budget-v1"
REQUIREMENT = "shared.spawn-work-budget-v1"
DESTINATION_MASKS = (8, 15, 448, 512)
EXPECTED_SCAN_CANDIDATES = 240
MAX_CANDIDATE_QUERIES_PER_UPDATE = 12
EXPECTED_DESTINATION_UPDATES = (
    1 + (EXPECTED_SCAN_CANDIDATES
         + MAX_CANDIDATE_QUERIES_PER_UPDATE - 1)
    // MAX_CANDIDATE_QUERIES_PER_UPDATE
)
MAX_RESUMED_FINALIZER_ARM9_TICKS = 50000
POST_SPAWN_PACING_SAMPLES = 4
MINIMUM_INTERIOR_MOVING_FRAMES = 120
MINIMUM_ENTRY_PROGRESS = 4
ENTRY_TARGET_MAX_DISTANCE_TILES = 16
ENTRY_OFFSCREEN_MARGIN_TILES = 4
ENTRY_VIEW_HALF_WIDTH_TILES = 8
ENTRY_VIEW_HALF_HEIGHT_TILES = 6


def require(value, reason):
    if not value:
        raise ValueError(reason)


def _boundary(snapshot):
    return {
        "frame": snapshot["frame"],
        "nativeCycle": snapshot["nativeCycle"],
        "actorFrame": snapshot["actorFrame"],
        "context": deepcopy(snapshot["context"]),
        "player": [snapshot["player"]["x"], snapshot["player"]["y"]],
        "nativeSequence": snapshot["nativeObservation"]["sequence"],
    }


class SpawnWorkBudgetMeasurement:
    """Follow one natural explicit destination scan from queue to final result."""

    def __init__(self, test, source, *, max_frames):
        require(test.get("mode") == "normal"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "mankey", "species": 56,
                    "role": "FOLLOWER", "acquire": "existing",
                }]
                and isinstance(source, dict)
                and isinstance(source.get("schema"), dict)
                and isinstance(source.get("sourceSha256"), str)
                and len(source["sourceSha256"]) == 64
                and type(max_frames) is int and 240 <= max_frames <= 2400,
                "spawn-work measurement requires one bounded current-profile fixture")
        self.max_frames = max_frames
        self.source_sha256 = source["sourceSha256"]
        self.initial = None
        self.terminal = None
        self.subject = None
        self.last_frame = None
        self.last_native_cycle = None
        self.last_actor_frame = None
        self.attempt = None
        self.calls = []
        self.profile_receipts = 0
        self.metadata_receipts = 0
        self.class_selection_receipts = 0
        self.resumed_finalizer_ticks = []
        self.frames = 0
        self.pacing_samples = 0
        self.pacing_intervals = 0
        self.max_main_loop_arm9_ticks = 0
        self.max_main_loop_native_cycles = 0
        self.max_main_loop_frame_sequence = 0
        self.late_main_loops = 0
        self.last_pacing_after_frame = None
        self.post_spawn_pacing_samples = 0
        self.first_late_main_loop = None
        self.last_player_pose = None
        self.interior_moving_frames = 0
        self.interior_render_stalls = 0
        self.first_render_stall = None
        self.entry = None
        self.failures = []
        self.closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    def arm(self, subject, snapshot):
        require(self.initial is None
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0
                and snapshot.get("context", {}).get("mapId") == 33
                and snapshot.get("player", {}).get("x") == 585
                and snapshot.get("player", {}).get("y") == 406
                and snapshot.get("nativeObservation", {}).get("coverageComplete") is True
                and snapshot.get("nativeObservation", {}).get("error") is None
                and snapshot.get("nativeObservation", {}).get("eventsDropped") == 0
                and subject.get("species") == 56
                and subject.get("role") == "FOLLOWER"
                and subject.get("handle", {}).get("value"),
                "spawn-work measurement requires the reviewed Route 30 boundary")
        self.initial = _boundary(snapshot)
        self.subject = deepcopy(subject)
        self.last_frame = snapshot["frame"]
        self.last_native_cycle = snapshot["nativeCycle"]
        self.last_actor_frame = snapshot["actorFrame"]
        self.last_player_pose = [snapshot["player"]["pos_x"], snapshot["player"]["pos_z"]]
        return self.result()

    def _check_subject(self, snapshot):
        actors = [actor for actor in snapshot.get("actors", [])
                  if actor.get("handle") == self.subject["handle"]]
        require(len(actors) == 1
                and actors[0].get("active") is True
                and actors[0].get("species") == 56
                and actors[0].get("role") == "FOLLOWER"
                and actors[0].get("identityVerified") is True,
                "spawn-work field anchor changed identity")

    def _observe_pacing(self, snapshot, events):
        rows = [event.get("data", {}) for event in events
                if event.get("kind") == "native-observation"
                and event.get("data", {}).get("observation") == "stock-main-loop-pacing"]
        if self.frames == 0 and not rows:
            return
        require(len(rows) == 1, "spawn-work update lacks one main-loop pacing sample")
        row = rows[0]
        require(row.get("setupMode") == "normal"
                and row.get("returnSite") == RETURN_SITE
                and row.get("scope") == MAIN_LOOP_SCOPE
                and row.get("diagnosticOnly") is False
                and row.get("acceptedProof") is False
                and row.get("flushedAtQueueFrame") == snapshot["frame"]
                and row.get("afterQueueFrame") == snapshot["frame"] - 1,
                "spawn-work main-loop pacing sample changed owner or source")
        after_frame = row["afterQueueFrame"]
        if self.last_pacing_after_frame is not None:
            require(after_frame == self.last_pacing_after_frame + 1,
                    "spawn-work main-loop pacing samples are not continuous")
        self.last_pacing_after_frame = after_frame
        self.pacing_samples += 1

        frame_counter = row.get("frameCounter")
        require(type(frame_counter) is int and frame_counter >= 0,
                "spawn-work main-loop pacing counter is invalid")
        interval = row.get("intervalFromPrevious")
        if self.pacing_samples == 1:
            require(interval is None,
                    "spawn-work first main-loop pacing sample has a foreign interval")
        else:
            require(isinstance(interval, dict)
                    and all(type(interval.get(key)) is int and interval[key] >= 0
                            for key in ("arm9Ticks", "nativeCycles", "frameSequence", "actorFrames")),
                    "spawn-work main-loop pacing interval is invalid")
            self.pacing_intervals += 1
            self.max_main_loop_arm9_ticks = max(
                self.max_main_loop_arm9_ticks, interval["arm9Ticks"])
            self.max_main_loop_native_cycles = max(
                self.max_main_loop_native_cycles, interval["nativeCycles"])
            self.max_main_loop_frame_sequence = max(
                self.max_main_loop_frame_sequence, interval["frameSequence"])
        late = (frame_counter > 2
                or (interval is not None
                    and (interval["arm9Ticks"] > MAX_ZERO_STUTTER_ARM9_TICKS
                         or interval["nativeCycles"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES
                         or interval["frameSequence"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES)))
        if late:
            self.late_main_loops += 1
            self.first_late_main_loop = deepcopy(row)
            raise ValueError("spawn-work main loop missed normal frame pace")
        if self.attempt and self.attempt.get("completed") \
                and after_frame >= self.attempt["endFrame"]:
            self.post_spawn_pacing_samples += 1

    def _observe_player_render(self, snapshot):
        player = snapshot.get("player", {})
        require(all(type(player.get(key)) is int for key in
                    ("x", "y", "x_prev", "y_prev", "pos_x", "pos_z")),
                "spawn-work player render sample is invalid")
        pose = [player["pos_x"], player["pos_z"]]
        in_transit = (player["x"] != player["x_prev"]
                      or player["y"] != player["y_prev"])
        if in_transit:
            self.interior_moving_frames += 1
            if pose == self.last_player_pose:
                self.interior_render_stalls += 1
                self.first_render_stall = {
                    "frame": snapshot["frame"],
                    "pose": pose,
                    "tile": [player["x"], player["y"]],
                    "previousTile": [player["x_prev"], player["y_prev"]],
                    "movementCommand": player.get("movement_cmd"),
                    "movementStep": player.get("movement_step"),
                }
                raise ValueError("spawn-work player render froze during admitted movement")
        self.last_player_pose = pose

    def _check_finalizer(self, final, destination):
        require(final.get("spawnAttemptId") == destination["spawnAttemptId"]
                and final.get("finalizationId") == destination["finalizationId"]
                and final.get("slot") == destination["slot"]
                and final.get("worldContext") == destination["worldContext"]
                and final.get("returnWorldContext") == destination["worldContext"]
                and final.get("statePointer") == destination["worldContext"].get("statePointer")
                and final.get("fieldPointer") == destination["worldContext"].get("fieldPointer"),
                "spawn-work finalizer lost its scan owner")
        encounter = final.get("inputEncounter")
        require(isinstance(encounter, dict)
                and type(encounter.get("personality")) is int
                and encounter["personality"] > 0
                and type(encounter.get("species")) is int
                and 1 <= encounter["species"] <= 1025,
                "spawn-work encounter identity is invalid")
        receipts = final.get("resolverReceipts")
        require(isinstance(receipts, list) and len(receipts) <= 1,
                "spawn-work finalizer has repeated profile resolution")
        if receipts:
            receipt = receipts[0]
            require(receipt.get("resolved") is True
                    and receipt.get("finalizationId") == final["finalizationId"]
                    and receipt.get("inputEncounter") == encounter
                    and receipt.get("sourceSha256") == self.source_sha256,
                    "spawn-work profile receipt differs from the current source")
        timing = final.get("guestTiming")
        require(isinstance(timing, dict)
                and type(timing.get("arm9Ticks")) is int
                and timing["arm9Ticks"] >= 0,
                "spawn-work finalizer lacks guest work timing")
        return encounter, len(receipts), timing["arm9Ticks"]

    def _observe_destination(self, snapshot, destination, events):
        require(destination.get("destinationMask") in DESTINATION_MASKS
                and destination.get("setupMode") == "normal"
                and destination.get("entryActorFrame") == destination.get("returnActorFrame")
                and destination.get("entryNativeCycle") <= destination.get("returnNativeCycle")
                and type(destination.get("candidateQueryCount")) is int
                and 0 <= destination["candidateQueryCount"]
                    <= MAX_CANDIDATE_QUERIES_PER_UPDATE,
                "spawn-work destination receipt exceeds the candidate batch")
        finals = [event.get("data", {}) for event in events
                  if event.get("kind") == "native-observation"
                  and event.get("data", {}).get("observation") == "spawn-finalized"
                  and event.get("data", {}).get("finalizationId") == destination["finalizationId"]]
        require(len(finals) == 1, "spawn-work destination lacks its exact finalizer")
        encounter, receipt_count, finalizer_ticks = self._check_finalizer(finals[0], destination)
        metadata = [event.get("data", {}) for event in events
                    if event.get("kind") == "native-observation"
                    and event.get("data", {}).get("observation") == "spawn-metadata"
                    and event.get("data", {}).get("finalizationId") == destination["finalizationId"]]
        class_selections = [event.get("data", {}) for event in events
                            if event.get("kind") == "native-observation"
                            and event.get("data", {}).get("observation") == "spawn-class-selection"
                            and event.get("data", {}).get("finalizationId") == destination["finalizationId"]]
        require(len(metadata) <= 1, "spawn-work finalizer repeated metadata preparation")
        require(len(class_selections) <= 1, "spawn-work finalizer repeated class selection")
        self.profile_receipts += receipt_count
        self.metadata_receipts += len(metadata)
        self.class_selection_receipts += len(class_selections)

        if self.attempt is None:
            queued = [event.get("data", {}) for event in events
                      if event.get("kind") == "native-observation"
                      and event.get("data", {}).get("observation") == "spawn-queued"
                      and event.get("data", {}).get("spawnAttemptId") == destination["spawnAttemptId"]]
            require(len(queued) == 1
                    and queued[0].get("queued") is True
                    and queued[0].get("pendingDestination") is True
                    and destination["candidateQueryCount"] == 0
                    and destination.get("returnValue") == 0
                    and finals[0].get("returnValue") == 0
                    and receipt_count == 1,
                    "spawn-work scan did not start after the helper-owned queue attempt")
            require(len(metadata) == 1 and len(class_selections) == 1,
                    "spawn-work initial scan lacks one metadata/class preparation")
            self.attempt = {
                "spawnAttemptId": destination["spawnAttemptId"],
                "slot": destination["slot"],
                "terrain": finals[0].get("terrain"),
                "encounter": deepcopy(encounter),
                "worldContext": deepcopy(destination["worldContext"]),
                "destinationMask": destination["destinationMask"],
                "startFrame": snapshot["frame"],
            }
        else:
            require(receipt_count == 0,
                    "spawn-work resumed scan repeated profile resolution")
            require(not metadata,
                    "spawn-work resumed scan repeated metadata preparation")
            require(not class_selections,
                    "spawn-work resumed scan repeated class selection")
            require(finalizer_ticks <= MAX_RESUMED_FINALIZER_ARM9_TICKS,
                    "spawn-work resumed finalizer exceeds guest work budget")
            self.resumed_finalizer_ticks.append(finalizer_ticks)
        require(destination["spawnAttemptId"] == self.attempt["spawnAttemptId"]
                and destination["slot"] == self.attempt["slot"]
                and destination["destinationMask"] == self.attempt["destinationMask"]
                and encounter == self.attempt["encounter"]
                and destination["worldContext"] == self.attempt["worldContext"]
                and {key: destination["worldContext"].get(key)
                     for key in ("mapId", "fieldEpoch", "mapGeneration")}
                    == self.initial["context"],
                "spawn-work scan changed attempt, encounter, slot, or field")
        if self.calls:
            require(snapshot["frame"] == self.calls[-1]["frame"] + 1
                    and destination["entryActorFrame"] == self.calls[-1]["actorFrame"] + 1,
                    "spawn-work scan did not resume on the next completed game update")
        self.calls.append({
            "frame": snapshot["frame"],
            "actorFrame": destination["entryActorFrame"],
            "finalizationId": destination["finalizationId"],
            "candidateQueries": destination["candidateQueryCount"],
            "returnValue": destination["returnValue"],
        })
        if len(self.calls) == 1:
            require(destination["candidateQueryCount"] == 0,
                    "spawn-work first scan update performed profile terrain work")
        else:
            require(destination["candidateQueryCount"]
                    <= MAX_CANDIDATE_QUERIES_PER_UPDATE,
                    "spawn-work resumed update has an invalid candidate batch")
        if destination["returnValue"] == 1:
            require(len(self.calls) == EXPECTED_DESTINATION_UPDATES
                    and finals[0].get("returnValue") == 0,
                    "spawn-work scan completed outside the bounded reservoir batches")
            self.attempt.update(
                scanEndFrame=snapshot["frame"],
                callCount=len(self.calls),
                candidateQueryCount=sum(
                    call["candidateQueries"] for call in self.calls),
                maxQueriesPerUpdate=max(call["candidateQueries"] for call in self.calls),
                resolverReceiptCount=self.profile_receipts,
                metadataReceiptCount=self.metadata_receipts,
                classSelectionReceiptCount=self.class_selection_receipts,
                maxResumedFinalizerArm9Ticks=max(self.resumed_finalizer_ticks),
                profileSourceSha256=self.source_sha256,
                scanCompleted=True,
            )
        else:
            require(finals[0].get("returnValue") == 0,
                    "spawn-work pending destination and finalizer results differ")

    def _observe_spawn_completion(self, snapshot, events):
        finals = [event.get("data", {}) for event in events
                  if event.get("kind") == "native-observation"
                  and event.get("data", {}).get("observation") == "spawn-finalized"
                  and event.get("data", {}).get("spawnAttemptId")
                      == self.attempt["spawnAttemptId"]]
        require(len(finals) == 1
                and snapshot["frame"] == self.attempt["scanEndFrame"] + 1,
                "spawn-work startup did not finish on the update after its scan")
        final = finals[0]
        owner = {
            "spawnAttemptId": self.attempt["spawnAttemptId"],
            "finalizationId": final.get("finalizationId"),
            "slot": self.attempt["slot"],
            "worldContext": self.attempt["worldContext"],
        }
        encounter, receipt_count, finalizer_ticks = self._check_finalizer(final, owner)
        metadata = [event for event in events
                    if event.get("kind") == "native-observation"
                    and event.get("data", {}).get("observation") == "spawn-metadata"
                    and event.get("data", {}).get("finalizationId")
                        == final["finalizationId"]]
        class_selections = [event for event in events
                            if event.get("kind") == "native-observation"
                            and event.get("data", {}).get("observation")
                                == "spawn-class-selection"
                            and event.get("data", {}).get("finalizationId")
                                == final["finalizationId"]]
        prepared = [event.get("data", {}) for event in events
                    if event.get("kind") == "native-observation"
                    and event.get("data", {}).get("observation") == "spawn-prepared"
                    and event.get("data", {}).get("slot") == self.attempt["slot"]]
        object_creates = [event.get("data", {}) for event in events
                          if event.get("kind") == "native-observation"
                          and event.get("data", {}).get("observation")
                              == "spawn-object-create"
                          and event.get("data", {}).get("slot") == self.attempt["slot"]]
        require(encounter == self.attempt["encounter"]
                and receipt_count == 0
                and not metadata
                and not class_selections
                and finalizer_ticks <= MAX_RESUMED_FINALIZER_ARM9_TICKS
                and final.get("returnValue") == 1,
                "spawn-work startup completion repeated preparation or changed its attempt")
        require(len(prepared) == 1
                and len(object_creates) == 1
                and isinstance(object_creates[0].get("arguments"), list)
                and len(object_creates[0]["arguments"]) >= 3
                and type(object_creates[0].get("returnValue")) is int
                and object_creates[0]["returnValue"] != 0
                and prepared[0].get("returnValue") == 1
                and prepared[0].get("worldContext") == self.attempt["worldContext"]
                and prepared[0].get("preparedEncounter") == encounter
                and prepared[0].get("finalization", {}).get("status") == "matched"
                and prepared[0].get("finalization", {}).get("receipt", {}).get("finalizationId")
                    == final["finalizationId"]
                and prepared[0].get("publicSubject", {}).get("role") == "WILD"
                and prepared[0].get("publicSubject", {}).get("species") == encounter["species"],
                "spawn-work completed scan did not create its prepared wild actor")
        public_subject = prepared[0]["publicSubject"]
        startup = prepared[0].get("startup", {})
        origin = object_creates[0]["arguments"][1:3]
        target = startup.get("target")
        require(all(type(value) is int for value in origin)
                and isinstance(target, list) and len(target) == 2
                and all(type(value) is int for value in target)
                and startup.get("locomotion") == 3
                and final.get("position") == origin
                and final.get("startup", {}).get("target") == target
                and isinstance(public_subject.get("handle"), dict)
                and type(public_subject["handle"].get("value")) is int,
                "spawn-work Move entry did not retain its exact A and B")
        distance = abs(target[0] - origin[0]) + abs(target[1] - origin[1])
        player = snapshot["player"]
        player_x = player["x"]
        player_y = player["y"]
        require(1 <= distance <= ENTRY_TARGET_MAX_DISTANCE_TILES
                and (origin[0] == target[0] or origin[1] == target[1]),
                "spawn-work Move entry A is not within 16 cardinal tiles of B")
        offscreen_clearance = max(
            abs(origin[0] - player_x) - ENTRY_VIEW_HALF_WIDTH_TILES,
            abs(origin[1] - player_y) - ENTRY_VIEW_HALF_HEIGHT_TILES,
        )
        require(offscreen_clearance >= ENTRY_OFFSCREEN_MARGIN_TILES,
                "spawn-work Move entry A is not safely outside player view")
        self.entry = {
            "locomotion": startup["locomotion"],
            "handle": deepcopy(public_subject["handle"]),
            "subjectIdentity": public_subject.get("subjectIdentity"),
            "species": public_subject["species"],
            "origin": origin,
            "target": deepcopy(target),
            "startDistance": distance,
            "targetDistance": distance,
            "offscreenClearance": offscreen_clearance,
            "playerAtSpawn": [player_x, player_y],
            "minimumDistance": distance,
            "distanceProgress": 0,
            "maximumRenderDisplacement": 0,
            "observedFrames": 0,
            "ownerWalkFrames": 0,
            "baseSpeed": None,
            "startedAtBaseSpeed": False,
            "accelerationObserved": False,
            "chainObserved": False,
            "turnObserved": False,
            "walkPauseObserved": False,
            "resumedAfterPause": False,
            "tiredObserved": False,
        }
        self.resumed_finalizer_ticks.append(finalizer_ticks)
        self.attempt.update(
            endFrame=snapshot["frame"],
            finalizerCallCount=len(self.calls) + 1,
            maxResumedFinalizerArm9Ticks=max(self.resumed_finalizer_ticks),
            successfulSpawnCount=1,
            completed=True,
        )
        self.terminal = _boundary(snapshot)

    def _observe_spawn_entry(self, snapshot):
        actors = [actor for actor in snapshot.get("actors", [])
                  if actor.get("handle") == self.entry["handle"]]
        require(len(actors) == 1,
                "spawn-work Move entry actor lost its exact identity")
        actor = actors[0]
        require(actor.get("active") is True
                and actor.get("identityVerified") is True
                and actor.get("subjectIdentity") == self.entry["subjectIdentity"]
                and actor.get("species") == self.entry["species"],
                "spawn-work Move entry actor changed identity")
        logical = actor.get("logical", {})
        render = actor.get("render", {})
        require(all(type(logical.get(key)) is int for key in ("x", "y"))
                and all(type(render.get(key)) is int for key in ("x", "y")),
                "spawn-work Move entry lacks logical or rendered position")
        distance = (abs(self.entry["target"][0] - logical["x"])
                    + abs(self.entry["target"][1] - logical["y"]))
        render_displacement = (abs(render["x"] - self.entry["origin"][0])
                               + abs(render["y"] - self.entry["origin"][1]))
        self.entry["observedFrames"] += 1
        self.entry["minimumDistance"] = min(self.entry["minimumDistance"], distance)
        self.entry["distanceProgress"] = (
            self.entry["startDistance"] - self.entry["minimumDistance"])
        self.entry["maximumRenderDisplacement"] = max(
            self.entry["maximumRenderDisplacement"], render_displacement)
        policy = actor.get("movementPolicy", {})
        if actor.get("motionKind") == "WALK":
            require(type(policy.get("base")) is int and policy["base"] > 0
                    and type(policy.get("speed")) is int and policy["speed"] > 0,
                    "spawn-work Move entry did not use normal Walk policy")
            if self.entry["baseSpeed"] is None:
                self.entry["baseSpeed"] = policy["base"]
                self.entry["startedAtBaseSpeed"] = policy["speed"] == policy["base"]
            require(policy["base"] == self.entry["baseSpeed"],
                    "spawn-work Move entry changed its Walk base speed")
            if actor.get("lane") == "OWNER":
                self.entry["ownerWalkFrames"] += 1
            if policy["speed"] < policy["base"]:
                self.entry["accelerationObserved"] = True
            if policy.get("chain", 0) > 0:
                self.entry["chainObserved"] = True
            if policy.get("turn", 0) > 0:
                self.entry["turnObserved"] = True
        if (self.entry["ownerWalkFrames"] > 0
                and actor.get("lane") == "OWNER"
                and actor.get("motionKind") == "NONE"):
            self.entry["walkPauseObserved"] = True
        if (self.entry["walkPauseObserved"]
                and actor.get("lane") == "OWNER"
                and actor.get("motionKind") == "WALK"):
            self.entry["resumedAfterPause"] = True
        if actor.get("lane") == "TIRED":
            self.entry["tiredObserved"] = True

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("frame") == self.last_frame + 1
                    and snapshot.get("nativeCycle") >= self.last_native_cycle
                    and snapshot.get("actorFrame") == self.last_actor_frame + 1
                    and snapshot.get("context") == self.initial["context"]
                    and snapshot.get("nativeObservation", {}).get("coverageComplete") is True
                    and snapshot.get("nativeObservation", {}).get("error") is None
                    and snapshot.get("nativeObservation", {}).get("eventsDropped") == 0,
                    "spawn-work completed frame or field context changed")
            self._check_subject(snapshot)
            self._observe_pacing(snapshot, events)
            self._observe_player_render(snapshot)
            destinations = [event.get("data", {}) for event in events
                            if event.get("kind") == "native-observation"
                            and event.get("data", {}).get("observation") == "spawn-destination-search"
                            and ((self.attempt is not None
                                  and event.get("data", {}).get("spawnAttemptId")
                                      == self.attempt["spawnAttemptId"])
                                 or (self.attempt is None
                                     and event.get("data", {}).get("destinationMask")
                                         in DESTINATION_MASKS))]
            require(len(destinations) <= 1,
                    "spawn-work update contains more than one destination call")
            if destinations:
                self._observe_destination(snapshot, destinations[0], events)
            elif self.attempt is not None and not self.attempt.get("completed"):
                if self.attempt.get("scanCompleted"):
                    self._observe_spawn_completion(snapshot, events)
                else:
                    raise ValueError("spawn-work queued scan skipped a completed game update")
            if self.entry is not None:
                self._observe_spawn_entry(snapshot)
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "spawn-work frame bound exceeded")
            self.last_frame = snapshot["frame"]
            self.last_native_cycle = snapshot["nativeCycle"]
            self.last_actor_frame = snapshot["actorFrame"]
        except (ValueError, KeyError, TypeError) as error:
            self._fail(error)
        return self.result()

    @property
    def ready(self):
        return bool(self.attempt and self.attempt.get("completed")
                    and self.entry
                    and self.entry["startedAtBaseSpeed"]
                    and self.entry["accelerationObserved"]
                    and self.entry["chainObserved"]
                    and self.entry["turnObserved"]
                    and self.entry["walkPauseObserved"]
                    and self.entry["resumedAfterPause"]
                    and self.entry["tiredObserved"]
                    and self.entry["distanceProgress"] >= MINIMUM_ENTRY_PROGRESS
                    and self.entry["maximumRenderDisplacement"] >= MINIMUM_ENTRY_PROGRESS
                    and self.post_spawn_pacing_samples >= POST_SPAWN_PACING_SAMPLES
                    and self.interior_moving_frames >= MINIMUM_INTERIOR_MOVING_FRAMES) \
            and not self.failures

    def stage(self, name):
        if name != "complete":
            raise ValueError("unknown spawn-work measurement stage")
        return self.ready

    def finish(self):
        if not self.failures and not self.ready:
            if self.attempt and self.attempt.get("completed"):
                self._fail("spawn-work completion lacks its following main-loop pacing sample")
            else:
                self._fail("spawn-work measurement did not observe one complete explicit scan")
        self.closed = True
        return self.result()

    def result(self):
        return {
            "kind": KIND,
            "requirements": [REQUIREMENT],
            "passed": self.closed and self.ready,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "subject": deepcopy(self.subject),
            "attempt": deepcopy(self.attempt),
            "entry": deepcopy(self.entry),
            "destinationFrames": [call["frame"] for call in self.calls],
            "pacing": {
                "sampleCount": self.pacing_samples,
                "intervalCount": self.pacing_intervals,
                "maximumArm9Ticks": self.max_main_loop_arm9_ticks,
                "maximumNativeCycles": self.max_main_loop_native_cycles,
                "maximumFrameSequence": self.max_main_loop_frame_sequence,
                "normalMaximumArm9Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS,
                "maximumZeroStutterArm9Ticks": MAX_ZERO_STUTTER_ARM9_TICKS,
                "normalMaximumNativeCycles": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                "lateMainLoopCount": self.late_main_loops,
                "postSpawnSampleCount": self.post_spawn_pacing_samples,
                "firstLateMainLoop": deepcopy(self.first_late_main_loop),
                "interiorMovingFrameCount": self.interior_moving_frames,
                "interiorRenderStallCount": self.interior_render_stalls,
                "minimumInteriorMovingFrames": MINIMUM_INTERIOR_MOVING_FRAMES,
                "firstRenderStall": deepcopy(self.first_render_stall),
            },
        }

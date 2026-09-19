"""Fail-closed whole-game pacing check during steady unmounted spawn work."""
from copy import deepcopy

from tools.overworld.devtools_main_loop_probe import (
    MAX_ZERO_STUTTER_ARM9_TICKS,
    NORMAL_MAIN_LOOP_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
    RETURN_SITE,
    SCOPE as MAIN_LOOP_SCOPE,
)


KIND = "unmounted-zero-stutter-v1"
REQUIREMENT = "current.unmounted-zero-stutter"
START = {"mapId": 67, "x": 565, "y": 398}
MINIMUM_FRAMES = 2600
MINIMUM_MOVING_FRAMES = 1800
MANKEY_PROFILE_HOP_PAUSE_FRAMES = 5
MANKEY_PROFILE_HOP_MAX_DISTANCE = 6
MAX_DESTINATION_SCAN_FRAME_SPAN = 21


def require(value, reason):
    if not value:
        raise ValueError(reason)


class UnmountedZeroStutterMeasurement:
    """Measure every steady-state game loop after the fixed Cherrygrove anchor."""

    def __init__(self, test, source, *, max_frames):
        require(test.get("mode") == "normal"
                and test.get("fixture") == {"rom": "test.nds", "save": "test.sav"}
                and test.get("subjects") == [{
                    "id": "mankey", "species": 56,
                    "role": "FOLLOWER", "acquire": "existing",
                }]
                and type(max_frames) is int
                and MINIMUM_FRAMES <= max_frames <= 5000,
                "zero-stutter measurement requires the fixed unmodified-save route")
        require(isinstance(source, dict)
                and set(source) == {"schema", "sourceSha256"}
                and isinstance(source["schema"], dict)
                and isinstance(source["sourceSha256"], str)
                and len(source["sourceSha256"]) == 64,
                "zero-stutter measurement requires the current behavior source")
        self.max_frames = max_frames
        self.schema = deepcopy(source["schema"])
        self.source_sha256 = source["sourceSha256"]
        self.initial = None
        self.subject = None
        self.current_subject = None
        self.last_frame = None
        self.started = None
        self.frames = 0
        self.moving_frames = 0
        self.pacing_samples = 0
        self.pacing_intervals = 0
        self.last_pacing_after_frame = None
        self.maximum_arm9_ticks = 0
        self.maximum_native_cycles = 0
        self.maximum_frame_sequence = 0
        self.late_main_loops = 0
        self.first_late_main_loop = None
        self.last_player_pose = None
        self.render_stalls = 0
        self.first_render_stall = None
        self.spawn_finalizers = 0
        self.spawn_searches = 0
        self.spawn_work = {}
        self.spawn_work_witnesses = 0
        self.last_spawn_work_frame = None
        self.spawn_work_frames = set()
        self.spawn_attempt_frames = {}
        self.maximum_spawn_attempt_frame_span = 0
        self.profile = None
        self.failures = []
        self.closed = False

    def _fail(self, reason):
        if not self.failures:
            self.failures.append(str(reason))

    @staticmethod
    def _is_anchor(snapshot):
        player = snapshot.get("player", {})
        return (snapshot.get("fieldAvailable") is True
                and snapshot.get("context", {}).get("mapId") == START["mapId"]
                and player.get("x") == player.get("x_prev") == START["x"]
                and player.get("y") == player.get("y_prev") == START["y"]
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0)

    @staticmethod
    def _pacing_rows(events):
        return [event.get("data", {}) for event in events
                if event.get("kind") == "native-observation"
                and event.get("data", {}).get("observation") == "stock-main-loop-pacing"]

    def arm(self, subject, snapshot, *, resolved_profiles=None):
        require(self.initial is None
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and snapshot.get("context", {}).get("mapId") == 33
                and snapshot.get("player", {}).get("x") == 585
                and snapshot.get("player", {}).get("y") == 406
                and subject.get("species") == 56
                and subject.get("role") == "FOLLOWER"
                and subject.get("identityVerified") is True
                and subject.get("handle", {}).get("value"),
                "zero-stutter measurement requires the reviewed Route 30 start")
        self.initial = {
            "frame": snapshot["frame"],
            "context": deepcopy(snapshot["context"]),
            "player": [snapshot["player"]["x"], snapshot["player"]["y"]],
        }
        candidates = [actor for actor in snapshot.get("actors", [])
                      if actor.get("active") is True
                      and actor.get("handle") == subject.get("handle")
                      and actor.get("subjectIdentity") == subject.get("subjectIdentity")
                      and actor.get("species") == 56
                      and actor.get("role") == "FOLLOWER"
                      and actor.get("identityVerified") is True]
        require(len(candidates) == 1,
                "zero-stutter start lacks the bound Mankey actor")
        self.subject = deepcopy(subject)
        self.current_subject = deepcopy(candidates[0])
        self.last_frame = snapshot["frame"]
        self._observe_profile(snapshot, resolved_profiles=resolved_profiles)
        require(self.profile is not None,
                "zero-stutter Mankey Hop lacks its resolved profile")
        return self.result()

    def _check_snapshot(self, snapshot):
        require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                and type(snapshot.get("frame")) is int
                and snapshot["frame"] == self.last_frame + 1
                and snapshot.get("nativeObservation", {}).get("coverageComplete") is True
                and snapshot.get("nativeObservation", {}).get("error") is None
                and snapshot.get("nativeObservation", {}).get("eventsDropped") == 0,
                "zero-stutter completed frame coverage changed")
        require(not any(actor.get("active") is True and actor.get("role") == "MOUNTED"
                        for actor in snapshot.get("actors", [])),
                "zero-stutter route became mounted")

    def _check_subject(self, snapshot):
        candidates = [actor for actor in snapshot.get("actors", [])
                      if actor.get("active") is True
                      and actor.get("species") == 56
                      and actor.get("role") == "FOLLOWER"
                      and actor.get("identityVerified") is True
                      and actor.get("subjectIdentity") == self.subject.get("subjectIdentity")]
        require(len(candidates) == 1,
                "zero-stutter route lost the saved Mankey follower")
        candidate = candidates[0]
        previous = self.current_subject
        old_handle = previous.get("handle", {})
        new_handle = candidate.get("handle", {})
        context = snapshot.get("context", {})
        require(new_handle.get("fieldEpoch") == context.get("fieldEpoch")
                and new_handle.get("mapGeneration") == context.get("mapGeneration"),
                "zero-stutter follower handle is stale for the current field")
        if new_handle != old_handle:
            stable = ("value", "slot", "generation", "encounterGeneration")
            generations = (
                "authorityGeneration", "engineAnchorGeneration",
                "presentationGeneration",
            )
            require(all(new_handle.get(key) == old_handle.get(key) for key in stable)
                    and all(candidate.get(key) == previous.get(key) for key in generations)
                    and all(new_handle.get(key) == ((old_handle.get(key) + 1) & 0xFFFF or 1)
                            for key in ("fieldEpoch", "mapGeneration")),
                    "zero-stutter follower changed instead of rebinding to the next field")
        self.current_subject = deepcopy(candidate)

    def _observe_spawn_work(self, snapshot, events):
        observed = []
        for event in events:
            data = event.get("data", {})
            observation = data.get("observation")
            if event.get("kind") != "native-observation" or observation not in (
                    "spawn-finalized", "spawn-destination-search"):
                continue
            context = data.get("worldContext")
            require(data.get("setupMode") == "normal"
                    and type(data.get("spawnAttemptId")) is int
                    and data["spawnAttemptId"] > 0
                    and type(data.get("finalizationId")) is int
                    and data["finalizationId"] > 0
                    and type(data.get("slot")) is int
                    and 0 <= data["slot"] < 10
                    and isinstance(context, dict)
                    and context.get("mapId") == START["mapId"]
                    and context.get("fieldEpoch") == snapshot["context"]["fieldEpoch"]
                    and context.get("mapGeneration") == snapshot["context"]["mapGeneration"]
                    and type(context.get("fieldPointer")) is int
                    and context["fieldPointer"] > 0
                    and type(context.get("statePointer")) is int
                    and context["statePointer"] > 0,
                    "zero-stutter spawn-work identity is invalid")
            key = (
                data["spawnAttemptId"], data["finalizationId"], data["slot"],
                context["fieldPointer"], context["fieldEpoch"],
                context["mapGeneration"], context["mapId"], context["statePointer"],
            )
            entry = self.spawn_work.setdefault(key, set())
            before = len(entry)
            entry.add(observation)
            if before == 1 and len(entry) == 2:
                self.spawn_work_witnesses += 1
            observed.append((event, observation))
            if observation == "spawn-destination-search" \
                    and type(event.get("frame")) is int:
                span = self.spawn_attempt_frames.setdefault(
                    data["spawnAttemptId"], [event["frame"], event["frame"]])
                span[0] = min(span[0], event["frame"])
                span[1] = max(span[1], event["frame"])
                frame_span = span[1] - span[0] + 1
                self.maximum_spawn_attempt_frame_span = max(
                    self.maximum_spawn_attempt_frame_span, frame_span)
                require(frame_span <= MAX_DESTINATION_SCAN_FRAME_SPAN,
                        "zero-stutter spawn destination scan exceeded its frame budget")
        self.spawn_finalizers += sum(name == "spawn-finalized" for _, name in observed)
        self.spawn_searches += sum(name == "spawn-destination-search" for _, name in observed)
        if observed:
            frames = {
                event.get("frame")
                for event, _ in observed
                if type(event.get("frame")) is int
            }
            self.spawn_work_frames.update(frames)
            self.last_spawn_work_frame = max(frames) if frames else snapshot["frame"]

    def _observe_profile(self, snapshot, *, resolved_profiles=None):
        actor = self.current_subject or {}
        fingerprint = actor.get("behaviorFingerprint")
        mask = actor.get("matchedLayerMask")
        fields = {item.get("key"): item
                  for item in self.schema.get("fields", [])}
        compact_size = self.schema.get("compactSize")
        require(compact_size == 72
                and fields.get("hopPause", {}).get("cType") == "u8"
                and fields.get("hopMaxDistance", {}).get("cType") == "u8",
                "zero-stutter behavior schema changed")
        if resolved_profiles is None:
            resolved_profiles = []
        require(isinstance(resolved_profiles, list) and len(resolved_profiles) <= 64,
                "zero-stutter profile cache is invalid")
        matches = []
        for receipt in [*snapshot.get("nativeObservation", {}).get(
                "resolvedProfiles", []), *resolved_profiles]:
            try:
                raw = bytes.fromhex(receipt.get("resultHex", ""))
                request = bytes.fromhex(receipt.get("requestHex", ""))
            except (TypeError, ValueError):
                continue
            lanes = [raw[offset:offset + compact_size].hex()
                     for offset in (0, compact_size, compact_size * 2)]
            if (receipt.get("resolved") is True
                    and receipt.get("sourceSha256") == self.source_sha256
                    and receipt.get("fingerprint") == fingerprint
                    and receipt.get("appliedOverrides") == mask
                    and len(raw) == 256
                    and len(request) == 44
                    and int.from_bytes(request[:2], "little") == 56
                    and receipt.get("lanes") == lanes
                    and int.from_bytes(raw[248:252], "little") == mask
                    and int.from_bytes(raw[252:256], "little") == fingerprint):
                matches.append(raw[:compact_size])
        if not matches:
            return
        require(all(lane == matches[0] for lane in matches),
                "zero-stutter Mankey fingerprint names changed profile bytes")
        lane = matches[0]
        value = {
            "fingerprint": fingerprint,
            "mask": mask,
            "pauseFrames": lane[fields["hopPause"]["offset"]],
            "maxDistance": lane[fields["hopMaxDistance"]["offset"]],
        }
        require(value["pauseFrames"] == MANKEY_PROFILE_HOP_PAUSE_FRAMES
                and value["maxDistance"] == MANKEY_PROFILE_HOP_MAX_DISTANCE,
                "zero-stutter resolved Mankey profile changed")
        if self.profile is None:
            self.profile = value

    def _observe_pacing(self, snapshot, events):
        rows = self._pacing_rows(events)
        require(len(rows) == 1,
                "zero-stutter update lacks one main-loop pacing sample")
        row = rows[0]
        require(row.get("setupMode") == "normal"
                and row.get("returnSite") == RETURN_SITE
                and row.get("scope") == MAIN_LOOP_SCOPE
                and row.get("diagnosticOnly") is False
                and row.get("acceptedProof") is False
                and row.get("flushedAtQueueFrame") == snapshot["frame"]
                and row.get("afterQueueFrame") == snapshot["frame"] - 1,
                "zero-stutter pacing sample changed owner or source")
        after_frame = row["afterQueueFrame"]
        if self.last_pacing_after_frame is not None:
            require(after_frame == self.last_pacing_after_frame + 1,
                    "zero-stutter pacing samples are not continuous")
        self.last_pacing_after_frame = after_frame
        self.pacing_samples += 1
        frame_counter = row.get("frameCounter")
        require(type(frame_counter) is int and frame_counter >= 0,
                "zero-stutter main-loop counter is invalid")
        interval = row.get("intervalFromPrevious")
        require(isinstance(interval, dict)
                and all(type(interval.get(key)) is int and interval[key] >= 0
                        for key in ("arm9Ticks", "nativeCycles", "frameSequence", "actorFrames")),
                "zero-stutter main-loop interval is invalid")
        self.pacing_intervals += 1
        self.maximum_arm9_ticks = max(self.maximum_arm9_ticks, interval["arm9Ticks"])
        self.maximum_native_cycles = max(self.maximum_native_cycles, interval["nativeCycles"])
        self.maximum_frame_sequence = max(self.maximum_frame_sequence, interval["frameSequence"])
        late = (frame_counter > NORMAL_MAIN_LOOP_NATIVE_CYCLES
                or interval["arm9Ticks"] > MAX_ZERO_STUTTER_ARM9_TICKS
                or interval["nativeCycles"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES
                or interval["frameSequence"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES)
        if late:
            self.late_main_loops += 1
            self.first_late_main_loop = {
                **deepcopy(row),
                "player": deepcopy(snapshot.get("player")),
                "mapId": snapshot.get("context", {}).get("mapId"),
                "spawnWorkOnMeasuredQueueFrame": after_frame in self.spawn_work_frames,
            }
            raise ValueError("zero-stutter route observed an extra game frame")

    def _observe_player(self, snapshot):
        player = snapshot.get("player", {})
        require(all(type(player.get(key)) is int for key in
                    ("x", "y", "x_prev", "y_prev", "pos_x", "pos_z")),
                "zero-stutter player sample is invalid")
        pose = [player["pos_x"], player["pos_z"]]
        moving = player["x"] != player["x_prev"] or player["y"] != player["y_prev"]
        if moving:
            self.moving_frames += 1
            if pose == self.last_player_pose:
                self.render_stalls += 1
                self.first_render_stall = {
                    "frame": snapshot["frame"],
                    "pose": pose,
                    "tile": [player["x"], player["y"]],
                    "previousTile": [player["x_prev"], player["y_prev"]],
                }
                raise ValueError("zero-stutter player render froze during movement")
        self.last_player_pose = pose

    def observe(self, snapshot, events):
        if self.failures or self.closed:
            return self.result()
        try:
            require(self.initial is not None, "zero-stutter measurement was not armed")
            self._check_snapshot(snapshot)
            self.last_frame = snapshot["frame"]
            if self.started is None:
                if snapshot.get("fieldAvailable") is True:
                    # The route crosses Route 30 -> Cherrygrove before the
                    # measured steady-state window. Keep the same saved
                    # follower bound at the exact transition frame so live
                    # checking and retained replay cannot diverge.
                    self._check_subject(snapshot)
                    self._observe_profile(snapshot)
                if self._is_anchor(snapshot):
                    rows = self._pacing_rows(events)
                    require(len(rows) == 1,
                            "zero-stutter anchor lacks its main-loop pacing sample")
                    self.started = {
                        "frame": snapshot["frame"],
                        "mapId": START["mapId"],
                        "player": [START["x"], START["y"]],
                    }
                    self.last_pacing_after_frame = rows[0].get("afterQueueFrame")
                    self.last_player_pose = [snapshot["player"]["pos_x"], snapshot["player"]["pos_z"]]
                return self.result()
            require(snapshot.get("fieldAvailable") is True
                    and snapshot.get("context", {}).get("mapId") == START["mapId"],
                    "zero-stutter steady-state route left Cherrygrove")
            self._check_subject(snapshot)
            self._observe_spawn_work(snapshot, events)
            self._observe_profile(snapshot)
            self._observe_pacing(snapshot, events)
            self._observe_player(snapshot)
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "zero-stutter frame bound exceeded")
        except (ValueError, KeyError, TypeError) as error:
            self._fail(error)
        return self.result()

    @property
    def ready(self):
        return (self.started is not None
                and self.profile is not None
                and self.frames >= MINIMUM_FRAMES
                and self.moving_frames >= MINIMUM_MOVING_FRAMES
                and self.spawn_work_witnesses >= 1
                and self.maximum_spawn_attempt_frame_span
                    <= MAX_DESTINATION_SCAN_FRAME_SPAN
                and self.pacing_intervals == self.frames
                and self.late_main_loops == 0
                and self.render_stalls == 0
                and not self.failures)

    def stage(self, name):
        if name != "complete":
            raise ValueError("unknown zero-stutter measurement stage")
        return self.ready

    def finish(self):
        if not self.failures and self.profile is None:
            self._fail("zero-stutter Mankey lacks its current-field profile")
        elif not self.failures and not self.ready:
            self._fail("zero-stutter route ended before its full spawn-work witness")
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
            "started": deepcopy(self.started),
            "subject": deepcopy(self.current_subject),
            "spawnWork": {
                "finalizerCount": self.spawn_finalizers,
                "destinationSearchCount": self.spawn_searches,
                "joinedWitnessCount": self.spawn_work_witnesses,
                "lastFrame": self.last_spawn_work_frame,
                "maximumAttemptFrameSpan": self.maximum_spawn_attempt_frame_span,
            },
            "hopRhythm": {
                "profileFingerprint": (self.profile or {}).get("fingerprint"),
                "profileMask": (self.profile or {}).get("mask"),
                "profilePauseFrames": (self.profile or {}).get("pauseFrames"),
                "profileMaxDistance": (self.profile or {}).get("maxDistance"),
            },
            "pacing": {
                "sampleCount": self.pacing_samples,
                "intervalCount": self.pacing_intervals,
                "maximumArm9Ticks": self.maximum_arm9_ticks,
                "maximumNativeCycles": self.maximum_native_cycles,
                "maximumFrameSequence": self.maximum_frame_sequence,
                "normalMaximumArm9Ticks": NORMAL_MAIN_LOOP_ARM9_TICKS,
                "maximumZeroStutterArm9Ticks": MAX_ZERO_STUTTER_ARM9_TICKS,
                "normalMaximumNativeCycles": NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                "lateMainLoopCount": self.late_main_loops,
                "firstLateMainLoop": deepcopy(self.first_late_main_loop),
                "movingFrameCount": self.moving_frames,
                "minimumMovingFrames": MINIMUM_MOVING_FRAMES,
                "renderStallCount": self.render_stalls,
                "firstRenderStall": deepcopy(self.first_render_stall),
            },
        }

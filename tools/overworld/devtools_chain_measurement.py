"""Pure normal-WILD-Ledyba measurement over the shared devtools stream.

No IO, emulator, input, game mutation, profile resolver or acceptance gate.
The caller supplies the authored schema/source digest and every coherent frame,
including setup frames, with the shared native observations captured preboot.
Success here is measurement only, never accepted ROM/visual proof.
"""
from __future__ import annotations

from copy import deepcopy
import struct

from tools.overworld.devtools_records import HANDLE_FIELDS, select_current_actor
from tools.overworld.spawn_identity import live_spawn_flags
from tools.overworld.normal_play_observer import (
    MotionRecorder, decode_lane, evaluate_chain_intervals, live_identity,
    observed_chain_reset,
)


KIND_IDS = {"WALK": 1, "HOP": 2, "TELEPORT": 3, "REPOSITION": 5}
MOTION_DECISIONS = ("ACCEPTED", "RETRY_WORLD_BUSY", "BLOCKED", "SIDE_TILE", "TERRAIN", "OCCUPIED",
                    "RESERVED", "DIRECTION", "PROFILE", "ALREADY_ACTIVE", "STALE_FIELD", "CONTEXT_LOST", "NO_CANDIDATE")
CHAIN_OUTCOMES = ("RETRY", "STARTED", "COMPLETE", "ABORT")
# Reviewed Flying insect authored contract, not the variance generator.
LEDYBA_CONTRACT = {"ramAccelerationSteps": 8, "chainMovementVariance": 6,
                  "chainPauseAction": 5, "chainRepositionJumpCount": 4}


def _integer(value, label, low=0, high=0xFFFFFFFF):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label + " is not a bounded integer")
    return value


def _bytes(value, size, label):
    if not isinstance(value, str) or len(value) != size * 2:
        raise ValueError(label + " has the wrong byte count")
    try:
        result = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(label + " is not hexadecimal") from error
    if len(result) != size:
        raise ValueError(label + " has the wrong byte count")
    return result


def _handle(value):
    return tuple(value[key] for key in HANDLE_FIELDS)


class LedybaChainMeasurement:
    """observe(snapshot, events), result(), finish(); first failure is sticky.

    max_frames is explicit and counts all supplied complete game frames. The
    caller owns separate setup, wall-time and no-progress budgets. Subjects are
    acquired from native spawn receipts, never from a requested species label.
    At most 64 profiles, 256 distinct resolver requests, 2048 motions, 256
    boundaries/resets and max_frames raw motion samples are retained. Reaching
    a bound fails; data is never evicted.
    """

    def __init__(self, schema, expected_source_sha256, *, max_frames, accepted_setup_mode="normal"):
        if accepted_setup_mode not in ("normal", "prepared"):
            raise ValueError("unknown accepted observation setup mode")
        self.accepted_setup_mode = accepted_setup_mode
        self.max_frames = _integer(max_frames, "max_frames", 1, 60000)
        _bytes(expected_source_sha256, 32, "authored source SHA-256")
        if schema.get("compactSize") != 72:
            raise ValueError("the public resolver lane ABI must be 72 bytes")
        self.schema = deepcopy(schema)
        self.source_sha256 = expected_source_sha256
        self.frames = self.identity_samples = 0
        self.last_frame = self.last_native_sequence = None
        self.observation_baseline = None
        self.trace_sequences = {}
        self.first_handles = None
        self.subject = self.spawn = self.profile = self.expectation = None
        self.profiles = {}
        self.profile_requests = {}
        self.profile_request_count = 0
        self.spawn_geometry = None
        self.observation_group = "observation"
        self.recorder = MotionRecorder()
        self.motions, self.boundaries, self.resets, self.traces = [], [], [], []
        self.terminal_events, self.start_events = {}, {}
        self.evaluation_cache = None
        self.attempt_revision = self.handoff_revision = 0
        self.abort_attempts, self.chain_handoffs = [], []
        self.last_lane = None
        self.pending_resets = []
        self.base_commit = None
        self.latest_commit = None
        self.face_player_walk_frames = 0
        self.walk_options = None
        self.failures = []
        self.closed = False

    def _fail(self, code, **details):
        if not self.failures:
            self.failures.append({"code": code, "frame": self.last_frame,
                                  "group": self.observation_group, **details})

    def _same_subject(self, value):
        return isinstance(value, dict) and self.subject is not None and all(
            value.get(key) == self.subject[key]
            for key in ("handle", "species", "role", "subjectIdentity"))

    def _profile(self, receipt):
        if receipt.get("resolved") is not True:
            return
        result = _bytes(receipt.get("resultHex"), 200, "resolved profile")
        request = _bytes(receipt.get("requestHex"), 44, "resolver request").hex()
        fingerprint = _integer(receipt.get("fingerprint"), "profile fingerprint", 1)
        lanes = [result[offset:offset + 72].hex() for offset in (0, 72)]
        if receipt.get("sourceSha256") != self.source_sha256 \
                or receipt.get("lanes") != lanes \
                or int.from_bytes(result[176:180], "little") != fingerprint \
                or receipt.get("appliedOverrides") != int.from_bytes(result[172:176], "little"):
            raise ValueError("resolver source, fingerprint or full lanes differ")
        value = {key: deepcopy(receipt[key]) for key in
                 ("fingerprint", "sourceSha256", "lanes", "resultHex", "appliedOverrides")}
        if fingerprint in self.profiles and self.profiles[fingerprint] != value:
            raise ValueError("the same fingerprint names a changed resolver result")
        if fingerprint not in self.profiles and len(self.profiles) >= 64:
            raise ValueError("profile observation bound exceeded")
        requests = self.profile_requests.setdefault(fingerprint, {})
        if request not in requests:
            if self.profile_request_count >= 256:
                raise ValueError("distinct resolver request observation bound exceeded")
            # Many contexts can produce one immutable resolved value. Retain
            # each actual request; do not overwrite earlier subject provenance.
            requests[request] = 1
            self.profile_request_count += 1
        self.profiles[fingerprint] = value

    def _spawn_contract(self, data, jump, actor, snapshot):
        self.observation_group = "identity"
        raw = _bytes(data.get("preparedPrefixHex"), 30, "prepared spawn prefix")
        pointer = _integer(data.get("preparedPointer"), "prepared spawn pointer")
        main = 0x02000000 <= pointer < pointer + len(raw) <= 0x02400000
        stack = 0x027E0000 <= pointer < pointer + len(raw) <= 0x027E3FC0
        if pointer & 3 or not (main or stack):
            raise ValueError("prepared spawn buffer is outside aligned RAM/stack")
        pid, species, form, level = struct.unpack_from("<IHBB", raw, 12)
        encounter = {"personality": pid, "species": species, "form": form, "level": level}
        if data.get("preparedEncounter") != encounter or any(
                encounter[key] != actor["sourceIdentity"].get(key) for key in encounter) \
                or (pid, species, form, level) != (actor["subjectIdentity"], actor["species"], actor["form"], actor["level"]):
            raise ValueError("prepared encounter does not name the actual spawned Pokemon")
        self.observation_group = "render"
        tx, tz, ox, oz, locomotion, direction = struct.unpack_from("<4hBB", raw, 20)
        origin, target = [ox, oz], [tx, tz]
        startup = {"origin": origin, "target": target, "locomotion": locomotion,
                   "hopDirection": direction, "targetBaseY": 0}
        # PrepareSpawnStartup takes this Hop destination from this encounter's
        # selected spawn position. Borrowed destinations can strand an actor
        # on another species' tree/roof/flower-bed surface.
        spawn_position = list(struct.unpack_from("<ii", raw, 0))
        if spawn_position != target:
            raise ValueError("Hop landing does not match this Pokemon's own spawn location")
        if data.get("startup") != startup or locomotion != 4 \
                or jump.get("origin") != origin or jump.get("target") != target:
            raise ValueError("native off-screen startup and actual nested Hop differ")
        delta = [tx - ox, tz - oz]
        cardinal = ((0, -16), (0, 16), (-16, 0), (16, 0))
        if tuple(delta) not in cardinal:
            raise ValueError("off-screen spawn must travel exactly 16 cardinal tiles")
        player = jump.get("playerAtEntry", {})
        player_pointer = _integer(player.get("pointer"), "spawn-entry player pointer", 0x02000000, 0x023FFFFF)
        tile = player.get("tile")
        if player_pointer & 3 or player.get("mapId") != snapshot["context"]["mapId"] \
                or not isinstance(tile, list) or len(tile) != 2:
            raise ValueError("off-screen origin has no current spawn-entry player observation")
        px, pz = (_integer(value, "spawn-entry player coordinate", -32768, 32767) for value in tile)
        if abs(ox - px) <= 8 and abs(oz - pz) <= 6:
            raise ValueError("spawn origin is inside the player-relative 8 by 6 visible rectangle")
        self.spawn_geometry = {"preparedPointer": pointer, "preparedPrefixHex": raw.hex(),
            "spawnPosition": spawn_position,
            "preparedEncounter": encounter, "startup": startup, "playerAtEntry": deepcopy(player),
            "delta": delta, "outsideVisibleRectangle": True,
            "visibleRectangleHalfExtents": [8, 6]}

    def _acquire(self, snapshot, receipts):
        for data in receipts:
            if data.get("observation") != "spawn-prepared" or data.get("returnValue") != 1:
                continue
            subject = data.get("publicSubject", {})
            if subject.get("species") != 165 or subject.get("role") != "WILD":
                continue
            self.observation_group = "identity"
            if data.get("setupMode") != "normal" or not 0 <= data.get("slot", -1) < 6:
                raise ValueError("Ledyba spawn was not a normal wild native preparation")
            if _handle(subject["handle"]) in self.first_handles:
                raise ValueError("spawn receipt names an actor present before the trigger")
            selected = select_current_actor(snapshot, subject)
            actor = next(item for item in snapshot["actors"] if item["handle"] == selected["handle"])
            jumps = data.get("jumpReceipts")
            if not isinstance(jumps, list) or len(jumps) != 1 or jumps[0].get("returnValue") != 1:
                raise ValueError("successful natural spawn has no single successful nested Hop")
            jump = jumps[0]
            starts = [item for item in receipts if item.get("observation") == "spawn-motion"
                      and all(item.get(key) == jump.get(key) for key in
                              ("slot", "sourceIdentity", "publicSubject", "origin", "target", "returnValue"))]
            if len(starts) != 1 or starts[0]["sequence"] >= data["sequence"]:
                raise ValueError("spawn has no unique ordered native Hop receipt")
            if any(jump.get("publicSubject", {}).get(key) != selected[key]
                   for key in ("handle", "species", "role", "subjectIdentity")) \
                    or jump.get("slot") != selected["handle"]["slot"] \
                    or jump.get("sourceIdentity") != actor.get("sourceIdentity"):
                raise ValueError("spawn Hop receipt does not name the current subject/object")
            self._spawn_contract(data, jump, actor, snapshot)
            if actor["motionKind"] != "HOP" or actor["motionPhase"] != "MOVING" \
                    or actor["motionElapsed"] != 0 \
                    or jump.get("origin") != [actor["origin"]["x"], actor["origin"]["y"]] \
                    or jump.get("target") != [actor["target"]["x"], actor["target"]["y"]] \
                    or jump["origin"] == jump["target"]:
                raise ValueError("the actual off-screen spawn Hop start was not observed")
            origin = jump["origin"]
            creates = [item for item in receipts
                       if item.get("observation") == "spawn-object-create"
                       and item.get("slot") == data["slot"]
                       and item.get("returnValue") == actor["sourceIdentity"]["object"]]
            expected_create = [
                actor["engineIdentity"]["current_manager"],
                origin[0],
                origin[1],
                1,
            ]
            if len(creates) != 1 \
                    or creates[0].get("arguments") != expected_create \
                    or creates[0].get("sequence", data["sequence"]) >= data["sequence"]:
                raise ValueError(
                    "visible field sprite was not created at the off-screen Hop origin")
            if [actor.get("render", {}).get("x"), actor.get("render", {}).get("y")] != origin \
                    or [actor["engineObject"]["pos_x"] >> 16,
                        actor["engineObject"]["pos_z"] >> 16] != origin:
                raise ValueError("off-screen spawn Hop frame zero is not rendered at its origin")
            self.spawn_geometry["creation"] = {
                "arguments": deepcopy(creates[0]["arguments"]),
                "objectPointer": creates[0]["returnValue"],
                "sequence": creates[0]["sequence"],
            }
            self.observation_group = "chain"
            fingerprint = actor["behaviorFingerprint"]
            if fingerprint not in self.profiles:
                raise ValueError("spawn has no observed public resolved profile")
            nested = data.get("resolverReceipts")
            resolver_owner = "spawn"
            if nested == []:
                # The paced spawn path resolves once in its finalizer and then
                # reuses that prepared profile while it creates the actor.
                # The observer's matched finalization receipt is the bounded
                # ownership link between that resolver call and this spawn.
                pair = data.get("finalization")
                final = pair.get("receipt") if isinstance(pair, dict) else None
                shared = ("slot", "terrain", "preparedPointer", "preparedPrefixHex",
                          "preparedEncounter", "startup")
                if not isinstance(pair, dict) or pair.get("status") != "matched" \
                        or not isinstance(final, dict) \
                        or final.get("returnValue") != 1 or final.get("pairEligible") is not True \
                        or any(final.get(key) != data.get(key) for key in shared):
                    raise ValueError("spawn has no exact successful finalizer profile owner")
                nested = final.get("resolverReceipts")
                if not isinstance(nested, list) or not 1 <= len(nested) <= 64:
                    raise ValueError("spawn finalizer has no bounded resolver receipts")
                resolver_owner = "finalizer"
            elif not isinstance(nested, list) or not 1 <= len(nested) <= 64:
                raise ValueError("spawn has no bounded source-bound resolver receipts")
            for receipt in nested:
                if resolver_owner == "spawn":
                    owned = receipt.get("slot") == selected["handle"]["slot"] \
                        and receipt.get("sourceIdentity") == actor.get("sourceIdentity")
                else:
                    owned = receipt.get("finalizationId") == final.get("finalizationId") \
                        and receipt.get("inputEncounter") == final.get("inputEncounter")
                if not owned or receipt.get("resolved") is not True:
                    raise ValueError("nested resolver does not name the current spawn owner")
                self._profile(receipt)
                request = bytes.fromhex(receipt["requestHex"])
                # BehaviorResolveRequest's context has no form or PID fields.
                # Their independent prepared/current actor check above remains
                # required; byte9 is the observed spawn terrain, not form.
                if int.from_bytes(request[:2], "little") != actor["species"] \
                        or request[8] != actor["level"] or request[9] != data["terrain"] \
                        or int.from_bytes(request[12:16], "little") != 0:
                    raise ValueError("resolved request does not name the normal wild subject")
            # Native call order supplies provenance. Preparing a candidate and
            # settling its physical terrain can resolve the same output from
            # different requests; a global fingerprint cache cannot pick one.
            latest = nested[-1]
            if latest["fingerprint"] != fingerprint:
                raise ValueError("last spawn resolver result differs from the current actor")
            self.profile = {**deepcopy(self.profiles[fingerprint]), "requestHex": latest["requestHex"]}
            self.expectation = decode_lane(bytes.fromhex(self.profile["lanes"][0]), self.schema)
            if any(self.expectation[key] != value for key, value in LEDYBA_CONTRACT.items()):
                raise ValueError("resolved profile is not the reviewed Ledyba 8–14/four-skid contract")
            walk_field = next(field for field in self.schema["fields"]
                              if field["key"] == "walkOptions")
            self.walk_options = [bytes.fromhex(value)[walk_field["offset"]]
                                 for value in self.profile["lanes"]]
            if self.walk_options != [96, 96]:
                raise ValueError("resolved Ledyba lanes lost face-player Walk")
            # All potential AI lanes must preserve the measured projection.
            if any(decode_lane(bytes.fromhex(lane), self.schema) != self.expectation for lane in self.profile["lanes"]):
                raise ValueError("resolved AI lanes disagree on the captured chain/pause contract")
            self.subject, self.spawn = selected, deepcopy(data)
            self.spawn_frame = snapshot["frame"]
            self.spawn_sequence = starts[0]["sequence"]
            self.base_commit = actor["commitSequence"]
            self.recorder.expected_pause_by_kind = {"WALK": self.expectation["walkPause"],
                "HOP": self.expectation["hopPause"], "REPOSITION": 0}
            return

    def _eligible(self, sequence):
        ordinal = (sequence - self.base_commit) & 0xFFFFFFFF
        return sum(motion.get("commitFrame") is not None and motion["kind"] in ("WALK", "HOP", "TELEPORT")
                   and not motion.get("spawn") and not motion.get("skid")
                   and 0 < ((motion["commitBefore"] + 1 - self.base_commit) & 0xFFFFFFFF) <= ordinal
                   for motion in self.motions)

    def _policy(self, data, actor):
        if self.last_frame == self.spawn_frame and data["sequence"] < self.spawn_sequence:
            # Startup can reset a vacant slot before registering its new
            # actor. Those earlier calls are not this actor's chain history.
            return
        before, after = data.get("publicSubject"), data.get("publicSubjectAfter")
        if not self._same_subject(before):
            # The selected slot cannot quietly be recycled in a callback.
            if data.get("slot") == self.subject["handle"]["slot"]:
                raise ValueError("policy receipt has a stale or different selected subject")
            return
        if not self._same_subject(after):
            raise ValueError("selected policy call did not return for the same actor")
        request = _bytes(data.get("requestHex"), 28, "policy request")
        response = _bytes(data.get("responseHex"), 28, "policy response")
        if request[:4] != b"\x01\x00\x1c\x00" or response[:4] != request[:4] \
                or response[8:10] != request[8:10] or request[8] != self.subject["handle"]["slot"] \
                or request[9] != data.get("operation"):
            raise ValueError("public policy ABI/slot/operation differs")
        operation = request[9]
        retry = 9 <= operation <= 13
        if operation not in range(5) and not retry:
            raise ValueError("unexpected observed policy operation")
        returned = data.get("returnValue")
        if (retry and (type(returned) is not int or returned not in (0, 1))) or (not retry and returned != 1):
            raise ValueError("selected policy call did not return for the same actor")
        if before.get("behaviorFingerprint") != self.profile["fingerprint"] \
                or after.get("behaviorFingerprint") != self.profile["fingerprint"]:
            raise ValueError("policy profile changed after capture")
        if retry:
            identity = ("form", "level", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
            if any(subject.get(key) != actor.get(key) for subject in (before, after) for key in identity):
                raise ValueError("chain retry public subject identity differs")
            if "laneHex" in data or data.get("rngReturns") != []:
                raise ValueError("chain retry has an invented lane or RNG input")
            # These are handoff attempts, including native rejections. Neither
            # result grants a motion/chance/count credit or excuses an earlier
            # RESET through a later, unrelated INPUT lane transition.
            self.pending_resets.clear()
            self.handoff_revision += 1
            if len(self.chain_handoffs) >= self.max_frames * 8:
                raise ValueError("chain handoff receipt bound exceeded")
            self.chain_handoffs.append({"sequence": data["sequence"], "frame": self.last_frame,
                "operation": operation, "returned": returned, "commitSequence": before["commitSequence"],
                "subject": deepcopy(before), "subjectAfter": deepcopy(after),
                "entryActorFrame": data.get("entryActorFrame"), "returnActorFrame": data.get("returnActorFrame")})
            return
        if operation == 3:
            # COMMIT executes before the actor increments its lifetime counter.
            expected = (before["commitSequence"] + 1) & 0xFFFFFFFF
            for motion in self.motions:
                if (motion["commitBefore"] + 1) & 0xFFFFFFFF == expected:
                    motion["skid"] = bool(response[20] & 0x02)
        lane = None
        if operation in (1, 4):
            lane_hex = data.get("laneHex")
            lane = decode_lane(_bytes(lane_hex, 72, "policy lane"), self.schema)
            indexes = [index for index, value in enumerate(self.profile["lanes"]) if value == lane_hex]
            if not indexes or lane != self.expectation:
                self._fail("chain-profile-changed", expected=self.expectation, actual=lane,
                           laneHex=lane_hex, matchingLaneIndexes=indexes)
                return
        eligible = self._eligible(before["commitSequence"])
        reset = observed_chain_reset(request, response, True)
        if operation == 1 and response[16] == 0 and reset is None:
            # A rejected candidate cannot publish a policy lane change or
            # consume the pending RESET of a real, later INPUT handoff.
            # Public call ABI: decision is actorSlot+8; IGNORED is zero.
            return
        transition = None
        # RESET has no lane pointer/state: InitPolicyCall zeroes its packet.
        # Only the next real INPUT can prove an AI lane handoff. The native
        # alert path can clear Walk one frame before that INPUT arrives.
        if operation == 1:
            if reset and self.last_lane is not None and request[13] != self.last_lane["state"]:
                transition = {"fromLaneState": self.last_lane["state"], "toLaneState": request[13],
                    "eligibleMoves": eligible, "boundaryIndex": len(self.boundaries),
                    "beforeFrame": self.last_lane["frame"], "frame": self.last_frame}
            for pending in self.pending_resets:
                if transition is not None and pending["commitSequence"] == before["commitSequence"] \
                        and before.get("motionPhase") == after.get("motionPhase") == "IDLE" \
                        and pending["eligibleMoves"] == eligible \
                        and pending["boundaryIndex"] == len(self.boundaries) \
                        and pending["frame"] >= self.last_lane["frame"]:
                    pending["laneTransition"] = deepcopy(transition)
            self.pending_resets.clear()
            self.evaluation_cache = None
        elif operation != 0:
            # A start result, commit or chain decision is not part of this
            # pending handoff. A later lane change cannot excuse its reset.
            self.pending_resets.clear()
        if reset:
            record = {"frame": self.last_frame, "eligibleMoves": eligible, "boundaryIndex": len(self.boundaries),
                      "reason": reset, "returned": True, "requestHex": request.hex(), "responseHex": response.hex(),
                      "lane": deepcopy(self.expectation), "commitSequence": before["commitSequence"]}
            if transition is not None:
                record["laneTransition"] = transition
            self.resets.append(record)
            if operation == 0 and before.get("motionPhase") == "IDLE" \
                    and after.get("motionPhase") == "IDLE":
                self.pending_resets.append(record)
        if operation == 1:
            self.last_lane = {"state": request[13], "frame": self.last_frame}
        if operation != 4:
            return
        draws = data.get("rngReturns")
        if not isinstance(draws, list) or len(draws) > 1:
            raise ValueError("chain chance call has an invalid RNG observation count")
        selected = response[22] != 0
        # For the authored 60% chance, one actual RNG call is the independent
        # chain boundary even when the action was skipped.
        chance = lane["chainPauseActionChance"] or 100
        boundary = bool(draws) if chance < 100 else selected
        if selected and (not boundary or response[22] != 5 or response[23] != lane["chainRepositionSpeed"]):
            raise ValueError("selected chain action/timing lacks its observed chance boundary")
        if not boundary:
            return
        roll = _integer(draws[0]["value"], "chain RNG return") if draws else 0
        if not request[14] & 0x08:
            raise ValueError("chain boundary lacks normal chain eligibility")
        self.boundaries.append({"frame": self.last_frame, "lane": deepcopy(lane), "laneHex": data["laneHex"],
            "matchingLaneIndexes": indexes, "fingerprint": self.profile["fingerprint"], "eligibleMoves": eligible,
            "commitSequence": before["commitSequence"], "nativeSequence": data["sequence"],
            "subject": deepcopy(before),
            "roll": roll, "selected": selected, "requestHex": request.hex(), "responseHex": response.hex()})

    def _attempt(self, data):
        if not self._same_subject(data.get("publicSubject")):
            if data.get("slot") == self.subject["handle"]["slot"]:
                raise ValueError("chain attempt has a stale selected subject")
            return
        self.attempt_revision += 1
        if self.attempt_revision > self.max_frames * 8:
            raise ValueError("chain attempt receipt bound exceeded")
        # Historical BOOL/stage observations cannot prove a native abort.
        if data.get("observationVersion") != 2:
            return
        raw = _bytes(data.get("resultHex"), 4, "native chain result")
        native = data.get("nativeResult", {})
        if native != {"encodedRemaining": raw[0], "gridDelta": int.from_bytes(raw[1:2], "little", signed=True),
                      "outcome": raw[2], "outcomeName": CHAIN_OUTCOMES[raw[2]],
                      "reason": raw[3], "reasonName": MOTION_DECISIONS[raw[3]]}:
            raise ValueError("native chain result bytes and meaning differ")
        if raw[2] == 3:
            if len(self.abort_attempts) >= 256:
                raise ValueError("selected abort boundary count exceeded")
            self.abort_attempts.append({"frame": self.last_frame, **deepcopy(data)})

    def _abort_proofs(self):
        proofs, errors = [], []
        for attempt in self.abort_attempts:
            try:
                before, after = attempt["publicSubject"], attempt["publicSubjectAfter"]
                identities = ("handle", "species", "role", "subjectIdentity", "form", "level", "behaviorFingerprint",
                              "authorityGeneration", "engineAnchorGeneration", "presentationGeneration", "commitSequence")
                if not self._same_subject(after) or any(before.get(key) != after.get(key) for key in identities) \
                        or before["behaviorFingerprint"] != self.profile["fingerprint"] \
                        or before.get("motionPhase") != "IDLE" or after.get("motionPhase") != "IDLE" \
                        or attempt["returnValue"] != 0 or attempt["nativeResult"]["reason"] != 12:
                    raise ValueError("abort subject/profile/terminal result differs")
                source, engine, world = attempt["sourceIdentity"], attempt["engineIdentity"], attempt["worldContext"]
                if any(source.get(key) != before.get(key) for key in ("species", "form", "level")) \
                        or source.get("personality") != before["subjectIdentity"] or not live_spawn_flags(source.get("active")) \
                        or source.get("object") != engine.get("pointer") or engine.get("pointer") != self.subject["engineIdentity"]["pointer"] \
                        or engine.get("in_manager") is not True or engine.get("active") is not True \
                        or engine.get("object_manager") != engine.get("current_manager") \
                        or source.get("encounter_generation") != before["handle"]["encounterGeneration"] \
                        or source.get("map_id") != engine.get("current_map_id") or world.get("mapId") != engine.get("current_map_id") \
                        or any(world.get(key) != before["handle"][key] for key in ("fieldEpoch", "mapGeneration")):
                    raise ValueError("abort source/engine/world is not the selected live actor")
                boundaries = [item for item in self.boundaries if item["selected"]
                    and item["nativeSequence"] < attempt["sequence"] and item["frame"] <= attempt["frame"]]
                if not boundaries: raise ValueError("abort has no selected chain boundary")
                boundary = boundaries[-1]
                if any(before.get(key) != boundary["subject"].get(key) for key in identities if key != "commitSequence"):
                    raise ValueError("abort differs from selected boundary identity")
                counter = before["commitSequence"]
                last = next((motion for motion in self.recorder.completed if motion["commitAfter"] == counter), None)
                if last is None or last["finishFrame"] > attempt["frame"] or list(last["target"]) != attempt["nativeOrigin"]:
                    raise ValueError("abort lacks same-commit native origin/control terminal")
                releases = self.terminal_events.get(("CONTROL_RETURNED", counter), [])
                if len(releases) != 1 or releases[0]["data"].get("valueA") != 0 \
                        or not last["startFrame"] <= releases[0]["frame"] <= attempt["frame"]:
                    raise ValueError("abort lacks exactly one prior control return")
                control = attempt["nativeControlAfter"]
                flags = _integer(control.get("engineFlags"), "abort native flags")
                if control.get("inputOwnership") != 0 or control.get("reservationId") != 0 \
                        or control.get("motionPhase") != "IDLE" or control.get("motionKind") != "NONE" \
                        or not flags & 1 or flags & 2 or flags & 0x10 and not flags & 0x20:
                    raise ValueError("abort did not return native control")
                origin = attempt["nativeOrigin"]
                if not isinstance(origin, list) or len(origin) != 2:
                    raise ValueError("abort native origin is missing")
                for coordinate in origin: _integer(coordinate, "abort origin coordinate", -32768, 32767)
                lane = boundary["lane"]
                terrain_field = next(field for field in self.schema["fields"] if field["key"] == "chillAllowedTerrainMask")
                if terrain_field["cType"] != "u16": raise ValueError("terrain mask ABI changed")
                lane_raw = _bytes(boundary["laneHex"], 72, "abort resolved lane")
                terrain_mask = int.from_bytes(lane_raw[terrain_field["offset"]:terrain_field["offset"] + 2], "little")
                distance = lane["chainRepositionDistance"]
                expected = set()
                if lane["chainRepositionAllowCardinal"]:
                    expected.update((origin[0] + dx * distance, origin[1] + dz * distance)
                                    for dx, dz in ((0, 1), (0, -1), (1, 0), (-1, 0)))
                if lane["chainRepositionAllowDiagonal"]:
                    expected.update((origin[0] + dx * distance, origin[1] + dz * distance)
                                    for dx, dz in ((1, 1), (1, -1), (-1, 1), (-1, -1)))
                landings, starts = attempt["landings"], attempt["preparedStarts"]
                if not expected or len(landings) != len(expected) or {tuple(item["target"]) for item in landings} != expected \
                        or [item["index"] for item in landings] != list(range(len(landings))):
                    raise ValueError("abort did not inspect every unique enabled destination")
                accepted_indexes = set()
                for landing in landings:
                    decision = landing.get("decision")
                    _integer(landing.get("index"), "abort candidate index", 0, 7)
                    _integer(decision, "abort candidate decision", 0, 12)
                    if landing.get("returnValue") != decision or landing.get("finalTarget") != landing["target"] \
                            or landing.get("origin") != origin or landing.get("allowedMask") != terrain_mask \
                            or any(query.get("returnValue") != 0 for query in landing.get("occupancyQueries", [])):
                        raise ValueError("abort candidate native destination or result differs")
                    if decision in (2, 4):
                        if landing.get("accepted") is not False or landing.get("decisionName") != {2: "BLOCKED", 4: "TERRAIN"}[decision]:
                            raise ValueError("abort candidate reason differs")
                    elif decision == 0 and landing.get("accepted") is True and landing.get("decisionName") == "ACCEPTED":
                        accepted_indexes.add(landing["index"])
                        matching = [start for start in starts if start.get("landingIndex") == landing["index"]]
                        if len(matching) != 1: raise ValueError("abort accepted landing lacks its unique planner rejection")
                        start = matching[0]
                        reason = start.get("startReason")
                        plans = start.get("hopPlans")
                        if start.get("returnValue") != reason or start.get("accepted") is not False or reason not in (2, 4) \
                                or start.get("startReasonName") != {2: "BLOCKED", 4: "TERRAIN"}[reason] \
                                or start.get("target") != landing["target"] or start.get("distance") != distance \
                                or start.get("motionRequests") != [] or not isinstance(plans, list) or len(plans) != 1:
                            raise ValueError("abort start is busy, unknown or lacks permanent planner rejection")
                        plan = plans[0]
                        if plan.get("decision") != reason or plan.get("returnValue") != reason \
                                or plan.get("decisionName") != start["startReasonName"] or plan.get("operation") != 2 \
                                or plan.get("origin") != origin or plan.get("target") != landing["target"] \
                                or plan.get("laneHex") != boundary["laneHex"] \
                                or plan.get("objectPointer") != source["object"] or plan.get("fieldPointer") != world["fieldPointer"]:
                            raise ValueError("abort planner does not prove this exact flat candidate")
                    else:
                        raise ValueError("abort candidate is occupied, busy or unknown")
                if len(starts) != len(accepted_indexes) or {item.get("landingIndex") for item in starts} != accepted_indexes:
                    raise ValueError("abort has an unpaired native start")
                encoded = _integer(attempt.get("encodedRemaining"), "abort selected count", 0, 255)
                remaining = (encoded - 1) & 15 if encoded & 0x80 else lane["chainRepositionJumpCount"]
                legs = [motion for motion in self.recorder.completed if motion["kind"] == "REPOSITION"
                        and boundary["frame"] <= motion["startFrame"] <= attempt["frame"]]
                if encoded & 0x70 != 0x20 or not 0 < remaining <= lane["chainRepositionJumpCount"] \
                        or len(legs) != lane["chainRepositionJumpCount"] - remaining \
                        or attempt["nativeResult"]["encodedRemaining"] != encoded or attempt["nativeResult"]["gridDelta"] != 0:
                    raise ValueError("abort lost or fabricated an executed leg")
                following = [handoff for handoff in self.chain_handoffs if handoff["sequence"] > attempt["sequence"]]
                if not following: raise ValueError("abort has no FINISH handoff")
                finish = following[0]
                if finish["operation"] != 12 or finish["returned"] != 1 or finish["frame"] != attempt["frame"] \
                        or finish["commitSequence"] != counter or finish["subject"] != before or finish["subjectAfter"] != after \
                        or finish["entryActorFrame"] != attempt.get("returnActorFrame"):
                    raise ValueError("abort FINISH did not clear this exact selected action")
                proofs.append({"decisionFrame": boundary["frame"], "frame": attempt["frame"],
                    "attemptId": attempt["attemptId"], "commitSequence": counter, "reason": "NO_CANDIDATE",
                    "candidateCount": len(landings), "finishSequence": finish["sequence"],
                    "controlReturnFrame": releases[0]["frame"]})
            except (KeyError, TypeError, ValueError, IndexError, AttributeError, StopIteration) as error:
                errors.append({"reason": "invalid-native-chain-abort", "frame": attempt["frame"], "detail": str(error)})
        return proofs, errors

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("measurement is closed")
        if self.failures:
            return self.result()
        try:
            self.observation_group = "observation"
            frame = _integer(snapshot.get("frame"), "completed game frame")
            initial = self.last_frame is None
            if self.last_frame is not None and frame != self.last_frame + 1:
                raise ValueError("complete game frame is missing, duplicated or reordered")
            self.last_frame = frame
            self.frames += 1
            if self.frames > self.max_frames:
                raise ValueError("measurement frame budget exceeded")
            if snapshot.get("prepared") is not (self.accepted_setup_mode == "prepared"):
                raise ValueError("normal observation was prepared or has unknown setup mode")
            if snapshot.get("observationBoundary") != "main-task-queue-completion":
                raise ValueError("actor/engine sample lacks the coherent main-queue boundary")
            coverage = snapshot.get("nativeObservation", {})
            if coverage.get("coverageComplete") is not True or coverage.get("installedBeforeBoot") is not True \
                    or coverage.get("eventsDropped") != 0 or coverage.get("profilesEvicted") != 0 \
                    or coverage.get("error") is not None:
                raise ValueError("preboot native observation coverage is missing or incomplete")
            watermark = _integer(coverage.get("sequence"), "coherent native sequence watermark")
            if coverage.get("pendingUnframedEvents") != 0:
                raise ValueError("native observation watermark is ahead of the coherent frame")
            if not isinstance(events, (list, tuple)) or len(events) > 2048:
                raise ValueError("frame event bound exceeded")
            if initial:
                native = [event for event in events if event.get("kind") == "native-observation"]
                baseline = _integer(native[0].get("data", {}).get("sequence"), "initial receipt sequence", 1) - 1 \
                    if native else watermark
                self.last_native_sequence = baseline
                self.observation_baseline = {"frame": frame, "nativeSequence": baseline,
                    "scope": "earlier preboot receipts are not observed-frame credit; profile cache retains resolver provenance"}
            receipts = []
            for event in events:
                if event.get("frame") != frame or not isinstance(event.get("data"), dict):
                    raise ValueError("event is not attached to its coherent frame")
                data = event["data"]
                if event.get("kind") == "trace-status" and (data.get("coverageComplete") is False
                        or data.get("code") in {"sequence-reset", "window-rearmed-externally", "unread-events-lost", "trace-filter-changed"}):
                    raise ValueError("semantic trace coverage is incomplete")
                if event.get("kind") == "native":
                    stream, sequence = data.get("traceStream"), data.get("sequence")
                    _integer(stream, "trace stream", 1)
                    _integer(sequence, "trace sequence", 1)
                    if sequence != self.trace_sequences.get(stream, 0) + 1:
                        raise ValueError("semantic trace sequence is missing or reordered")
                    self.trace_sequences[stream] = sequence
                if event.get("kind") != "native-observation":
                    continue
                sequence = _integer(data.get("sequence"), "native observation sequence", 1)
                if self.last_native_sequence is not None and sequence != self.last_native_sequence + 1:
                    raise ValueError("native observation was lost, duplicated or reordered")
                self.last_native_sequence = sequence
                if data.get("setupMode") != self.accepted_setup_mode:
                    raise ValueError("native observation came from prepared setup")
                receipts.append(data)
            if self.last_native_sequence != watermark:
                raise ValueError("coherent native receipts do not reach their published watermark")
            self.observation_group = "chain"
            for receipt in coverage.get("resolvedProfiles", []):
                self._profile(receipt)
            for receipt in receipts:
                if receipt.get("observation") == "behavior-resolved":
                    self._profile(receipt)
            if self.first_handles is None:
                self.first_handles = {_handle(item["handle"]) for item in snapshot["actors"] if item.get("active") is True}
            if self.subject is None:
                self._acquire(snapshot, receipts)
            if self.subject is None:
                return self.result()
            self.observation_group = "identity"
            select_current_actor(snapshot, self.subject)
            actor = next(item for item in snapshot["actors"] if item["handle"] == self.subject["handle"])
            if not live_identity(actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                                 species=165, role="WILD", current_epoch=snapshot["context"]["fieldEpoch"]):
                raise ValueError("selected subject lost exact live engine identity")
            if actor["engineIdentity"]["current_map_id"] != snapshot["context"].get("mapId") \
                    or any(actor.get(key) != actor["sourceIdentity"].get(key) for key in ("form", "level")):
                raise ValueError("selected engine map or source form/level differs")
            self.observation_group = "chain"
            if actor.get("behaviorFingerprint") != self.profile["fingerprint"]:
                raise ValueError("selected actor profile changed after capture")
            self.latest_commit = actor["commitSequence"]
            self.identity_samples += 1
            engine = actor["engineObject"]
            self.observation_group = "render"
            self.recorder.observe(frame, actor, engine)
            current = self.recorder.current
            if current is not None and (not self.motions or self.motions[-1] is not current):
                if len(self.motions) >= 2048:
                    raise ValueError("motion bound exceeded")
                current["spawn"] = not self.motions
                self.motions.append(current)
            if self.recorder.failures:
                self._fail("motion-measurement", failures=deepcopy(self.recorder.failures))
            if actor["motionPhase"] == "MOVING" \
                    and actor["motionKind"] in ("WALK", "REPOSITION") \
                    and self.walk_options[0] & 0x40:
                player = snapshot.get("player", {})
                dx = _integer(player.get("x"), "player x", -32768, 32767) - engine["x"]
                dy = _integer(player.get("y"), "player y", -32768, 32767) - engine["y"]
                horizontal = 3 if dx > 0 else 2
                vertical = 1 if dy > 0 else 0
                self.face_player_walk_frames += 1
                if not (dx != 0 and engine["facing"] == horizontal \
                        or dy != 0 and engine["facing"] == vertical):
                    raise ValueError("face-player motion does not face the player on this frame")
            if actor["motionPhase"] == "MOVING" and actor["motionKind"] == "REPOSITION":
                if engine.get("unk88_y") != 0:
                    raise ValueError("chain skid has a separate vertical jump offset")
                if actor["motionDuration"] != self.expectation["chainRepositionSpeed"]:
                    raise ValueError("chain skid duration differs from the captured authored time")
            if actor["motionPhase"] == "IDLE" and (actor.get("reservationId") != 0
                    or actor.get("inputOwnership") != 0 or not engine["flags"] & 1
                    or engine["flags"] & 2 or engine["flags"] & 0x10 and not engine["flags"] & 0x20):
                raise ValueError("terminal actor did not return native control")
            for data in receipts:
                if data.get("observation") == "walk-policy":
                    self.observation_group = "chain"
                    self._policy(data, actor)
                elif data.get("observation") == "chain-reposition-attempt":
                    self.observation_group = "chain"
                    self._attempt(data)
            self.pending_resets[:] = [reset for reset in self.pending_resets
                if reset["commitSequence"] == actor["commitSequence"]
                and not (current is not None and current["startFrame"] > reset["frame"])]
            self.observation_group = "render"
            for event in events:
                if event.get("kind") != "native":
                    continue
                data = event["data"]
                handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
                if handle != self.subject["handle"]:
                    continue
                if data.get("event") in ("MOTION_CANCELED", "ACTOR_DETACHED", "CONTEXT_CHANGED"):
                    raise ValueError("selected actor motion/lifetime was interrupted")
                if data.get("event") in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
                    retained = deepcopy(event)
                    self.traces.append(retained)
                    if data["event"] == "MOTION_STARTED":
                        key = (frame, data.get("valueA"), data.get("valueB"))
                        self.start_events.setdefault(key, []).append(retained)
                    else:
                        counter = data.get("valueB" if data["event"] == "CONTROL_RETURNED" else "valueA")
                        self.terminal_events.setdefault((data["event"], counter), []).append(retained)
            if len(self.boundaries) > 256 or len(self.resets) > 256 or len(self.traces) > 8192 or len(self.trace_sequences) > 64:
                raise ValueError("chain measurement receipt bound exceeded")
            # These checks concern completed motions only. A missing terminal
            # cannot be repaired by observing more unrelated game frames.
            _, errors, _ = self._evaluate()
            terminal_errors = [error for error in errors if error.get("reason") in
                               ("missing-or-duplicate-terminal-event", "missing-motion-start-event",
                                "spawn-hop-has-no-observed-arc", "skid-not-flat")]
            if terminal_errors:
                self._fail("completed-motion-proof-failed", failures=terminal_errors)
            self.observation_group = "chain"
            durable_errors = [error for error in errors if error.get("reason") in
                ("invalid-chain-reset", "invalid-chain-reset-order", "chain-reset-after-range",
                 "chain-move-count", "chance-selection", "reposition-time",
                 "reposition-distance-direction", "reposition-facing", "chain-boundary-overdue",
                 "reposition-action-truncated", "invalid-native-chain-abort", "duplicate-chain-abort",
                 "invalid-chain-abort-window", "chain-resumed-before-abort")
                or error.get("reason") == "unexplained-chain-reset"
                and error.get("reset") not in self.pending_resets]
            if durable_errors:
                self._fail("completed-chain-proof-failed", failures=durable_errors)
        except (KeyError, TypeError, ValueError, IndexError) as error:
            self._fail("invalid-observation", message=str(error))
        return self.result()

    def _evaluate(self):
        stamp = (len(self.recorder.completed), len(self.boundaries), len(self.resets), len(self.traces),
                 self.attempt_revision, self.handoff_revision)
        if self.evaluation_cache is not None and self.evaluation_cache[0] == stamp:
            return self.evaluation_cache[1]
        aborts, abort_errors = self._abort_proofs()
        chain = evaluate_chain_intervals(self.boundaries, self.recorder.completed, resets=self.resets, aborts=aborts)
        chain["errors"].extend(abort_errors)
        if self.expectation is not None and self.recorder.completed:
            # Check the open tail too. Earlier good actions cannot hide a
            # later chain that never publishes its chance boundary. Use only
            # fully returned motions and oracle-accepted lane resets: a raw
            # pending RESET or an in-flight commit cannot grant a new window.
            baseline = max([0] + [item["eligibleMoves"] for item in chain["intervals"]]
                + [item["startEligibleMoves"] + item["count"]
                   for item in chain["interruptedIntervals"] if item["acceptedBoundary"]])
            eligible = self._eligible(self.recorder.completed[-1]["commitAfter"])
            maximum = self.expectation["ramAccelerationSteps"] + self.expectation["chainMovementVariance"]
            if eligible - baseline > maximum:
                chain["errors"].append({"reason": "chain-boundary-overdue",
                    "actual": eligible - baseline, "maximum": maximum,
                    "startEligibleMoves": baseline, "eligibleMoves": eligible})
        errors = list(chain["errors"])
        spawn_passed = False
        for motion in self.recorder.completed:
            motion_error_start = len(errors)
            counter = motion["commitAfter"]
            for name, field, expected in (("LOGICAL_COMMIT", "valueA", counter),
                                           ("MOTION_FINISHED", "valueA", counter),
                                           ("CONTROL_RETURNED", "valueB", counter)):
                events = self.terminal_events.get((name, expected), [])
                if len(events) != 1 or not motion["startFrame"] <= events[0]["frame"] <= motion["finishFrame"] \
                        or events[0]["data"].get("valueA" if name == "CONTROL_RETURNED" else "valueB") != \
                            (0 if name == "CONTROL_RETURNED" else KIND_IDS[motion["kind"]]):
                    errors.append({"reason": "missing-or-duplicate-terminal-event", "event": name, "commit": counter})
            start_frames = {motion["startFrame"]}
            if motion["samples"]:
                start_frames.add(motion["startFrame"] - motion["samples"][0]["elapsed"])
            starts = [event for frame in start_frames for event in
                      self.start_events.get((frame, KIND_IDS[motion["kind"]], motion["duration"]), [])]
            if len(starts) != 1:
                errors.append({"reason": "missing-motion-start-event", "frame": motion["startFrame"]})
            if motion.get("spawn"):
                arc = motion["kind"] == "HOP" and any(sample["jumpOffset"] != 0 for sample in motion["samples"])
                spawn_passed = arc and len(errors) == motion_error_start
                if not arc:
                    errors.append({"reason": "spawn-hop-has-no-observed-arc"})
            if motion["kind"] == "REPOSITION" and any(sample["jumpOffset"] != 0 for sample in motion["samples"]):
                errors.append({"reason": "skid-not-flat"})
        self.evaluation_cache = (stamp, (chain, errors, spawn_passed))
        return self.evaluation_cache[1]

    def _stop_boundary(self):
        """Close a measured prefix, not the just-started successor motion.

        Zero-pause motion need not expose an idle frame. The recorder and
        _evaluate still prove every predecessor sample, terminal and control
        receipt. This witness never adds the successor to completed motions.
        """
        current = self.recorder.current
        if current is None:
            return {"kind": "idle", "frame": self.last_frame}
        if not self.recorder.completed or len(current["samples"]) != 1:
            return None
        previous, sample = self.recorder.completed[-1], current["samples"][0]
        starts = self.start_events.get(
            (self.last_frame, KIND_IDS[current["kind"]], current["duration"]), [])
        if previous["finishFrame"] != self.last_frame \
                or current["startFrame"] != self.last_frame or sample["frame"] != self.last_frame \
                or sample["elapsed"] != 0 or len(starts) != 1 \
                or current["handle"] != previous["handle"] \
                or current["fingerprint"] != previous["fingerprint"] \
                or current["origin"] != previous["target"] \
                or current["commitBefore"] != previous["commitAfter"] \
                or sample["render"] != previous["terminalRender"] or sample["jumpOffset"] != 0:
            return None
        return {"kind": "terminal-with-unmeasured-successor", "frame": self.last_frame,
                "completedCommit": previous["commitAfter"],
                "successor": {"handle": deepcopy(current["handle"]), "kind": current["kind"],
                    "origin": list(current["origin"]), "target": list(current["target"]),
                    "elapsed": 0, "countedAsComplete": False},
                "scope": "predecessor terminal proof only; no successor completion claim"}

    def result(self):
        chain, errors, spawn_passed = self._evaluate()
        # Preserve the measured error sets independently of the final verdict.
        # Empty sets before their coverage exists are not a passing claim.
        render_reasons = {"reposition-facing", "reposition-distance-direction", "reposition-time"}
        chain_errors = [deepcopy(error) for error in chain["errors"] if error.get("reason") not in render_reasons]
        render_errors = [deepcopy(error) for error in errors
                         if error not in chain["errors"] or error.get("reason") in render_reasons]
        groups = {"identity": [], "chain": chain_errors, "render": render_errors, "observation": []}
        for failure in self.failures:
            groups[failure["group"]].append(deepcopy(failure))
        stop_boundary = self._stop_boundary()
        complete = self.subject is not None and spawn_passed and len(chain["intervals"]) >= 3 \
            and len(chain["actions"]) >= 3 and all(action["motions"] == 4 for action in chain["actions"]) \
            and not errors and not self.failures and not self.pending_resets and stop_boundary is not None
        return {"state": "failed" if self.failures or self.closed and not complete else "completed" if self.closed else "observing",
                "passed": self.closed and complete, "ready": complete, "acceptedProof": False,
                "scope": "pure shared-stream Ledyba measurement; live recorder controls and controller acceptance are separate",
                "frames": self.frames, "identitySamples": self.identity_samples, "subject": deepcopy(self.subject),
                "stopBoundary": stop_boundary,
                "observationBaseline": deepcopy(self.observation_baseline),
                "fingerprint": self.profile["fingerprint"] if self.profile else None,
                "selectedProfileReceipt": deepcopy(self.profile),
                "walkOptions": deepcopy(self.walk_options),
                "selectedProfileObservationCount": self.profile_requests[self.profile["fingerprint"]].get(self.profile["requestHex"], 0) if self.profile else 0,
                "observedProfileCount": len(self.profiles),
                "observedProfileRequestCount": self.profile_request_count,
                "profileObservationCountScope": "distinct validated native resolver receipts, including the preboot cache; repeated cache snapshots are not new calls",
                "expectedChain": deepcopy(self.expectation), "spawnPassed": spawn_passed,
                "spawnGeometry": deepcopy(self.spawn_geometry),
                "facePlayerWalkFrames": self.face_player_walk_frames,
                "eligibleMoves": self._eligible(self.latest_commit) if self.latest_commit is not None else 0,
                "completeMotions": len(self.recorder.completed), "intervals": deepcopy(chain["intervals"]),
                "actions": deepcopy(chain["actions"]), "interruptedIntervals": deepcopy(chain["interruptedIntervals"]),
                "abortedActions": deepcopy(chain["abortedActions"]),
                "failures": deepcopy(self.failures), "measurementErrors": errors,
                **{name + "Errors": values for name, values in groups.items()},
                "errorCoverage": {"identitySamples": self.identity_samples,
                    "chainIntervals": len(chain["intervals"]), "completeRenderedMotions": len(self.recorder.completed),
                    "completeFrames": self.frames, "facePlayerWalkFrames": self.face_player_walk_frames,
                    "scope": "zero errors only describes the retained measured coverage, not an unobserved behavior"}}

    def finish(self):
        self.closed = True
        if self.subject is None:
            self.observation_group = "identity"
            self._fail("missing-natural-ledyba")
        elif self._stop_boundary() is None:
            self.observation_group = "render"
            self._fail("incomplete-motion-at-stop")
        elif not self.result()["ready"]:
            self.observation_group = "chain"
            chain, errors, spawn_passed = self._evaluate()
            self._fail("incomplete-chain-measurement", spawnPassed=spawn_passed,
                       completeIntervals=len(chain["intervals"]), completeActions=len(chain["actions"]),
                       requiredActions=3, measurementErrors=deepcopy(errors))
        return self.result()

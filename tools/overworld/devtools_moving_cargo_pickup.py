"""Shared native Cargo CANCEL, control return and HELD receipt validation.

Authored Trigger/Cargo binding checks stay with each caller. This leaf reads
accepted native motion and current owners; it never creates or changes motion.
"""
from copy import deepcopy
import struct
from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion


def require(value, message):
    if not value:
        raise ValueError(message)


def tile(actor, field):
    return tuple(actor[field][key] for key in ("x", "y"))


def pickup_motion(sample, actor, source):
    combat = sample.get("pokemonCombat", {})
    require(combat.get("schemaVersion") == 1 and combat.get("available") is True
            and combat.get("frame") == sample["frame"]
            and combat.get("nativeCycle") == sample["nativeCycle"]
            and combat.get("observationBoundary") == sample["observationBoundary"]
            and combat.get("fieldSystem") == sample["fieldControl"]["fieldPointer"]
            and combat.get("identity", {}).get("romSha256") == source["romSha256"]
            and combat["identity"].get("overlaySha256") == source["overlaySha256"],
            "moving pickup lacks its current native motion owner")
    rows = [r for r in combat.get("targets", []) if r.get("handle") == actor["handle"]]
    timers = [r for r in combat.get("movementTimers", []) if r.get("handle") == actor["handle"]]
    require(len(rows) == len(timers) == 1 and rows[0].get("role") == actor["role"]
            and timers[0].get("slot") == actor["handle"]["slot"]
            and timers[0].get("sourceIdentity") == actor.get("sourceIdentity")
            and isinstance(actor.get("sourceIdentity"), dict),
            "moving pickup has no exact native actor/control source")
    motion = rows[0]["motion"]
    require(motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
            "moving pickup native motion bytes differ")
    return motion, timers[0]


class CargoAutonomy:
    """Selection keeps the target's own profile and native AUTO movement.

    These finite fixtures have no other target-profile trigger. Retain their
    real unclaimed profile as the baseline, then reject a changed profile,
    early HELD control or a stopped/replaced accepted move while pursued.
    Only the callers' authenticated actual pickup may end this window.
    """
    def __init__(self, source):
        self.source = source
        self.baseline = self.previous = self.first = self.progress = self.held = None
        self.frames = 0

    def observe(self, sample, actor, events, profiles, *, claimed, held):
        if self.held is not None:
            return
        resolved = profiles.get(actor["behaviorFingerprint"])
        if not claimed and not held and self.first is None:
            if resolved is not None:
                self._profile(actor, resolved)
                self.baseline = dict(sample=deepcopy(sample), profile=deepcopy(resolved))
            return
        require(self.baseline is not None, "pickup autonomy lacks its unclaimed native profile baseline")
        if held:
            motion, timer = pickup_motion(sample, actor, self.source)
            require(self.first is not None and self.progress is not None
                    and timer["movementActorControlMode"] == 1,
                    "pickup autonomy lacks free motion before actual HELD control")
            self.held = deepcopy(sample)
            return
        require(claimed, "pickup autonomy lost its free target claim before HELD")
        self._profile(actor, resolved)
        require(resolved["resultHex"] == self.baseline["profile"]["resultHex"],
                "pickup selection changed the target's own resolved profile")
        motion, timer = pickup_motion(sample, actor, self.source)
        require(timer["movementActorControlMode"] == 0
                and not any(e.get("kind") == "native"
                            and e.get("data", {}).get("actorHandle") == actor["handle"]["value"]
                            and e["data"].get("event") == "MOTION_CANCELED" for e in events),
                "pickup selection took target control or canceled its accepted motion")
        if self.first is None:
            self.first = deepcopy(sample)
        self.frames += 1
        if self.previous is not None:
            before_sample, before, before_motion = self.previous
            require(sample["frame"] == before_sample["frame"] + 1
                    and sample["actorFrame"] == before_sample["actorFrame"] + 1
                    and actor["handle"] == before["handle"]
                    and actor["subjectIdentity"] == before["subjectIdentity"],
                    "pickup autonomy lost its dense current target window")
            if before_motion["phase"] == "MOVING":
                same_plan = motion["plan"] == before_motion["plan"]
                if same_plan:
                    require(motion["phase"] in ("MOVING", "SETTLING", "IDLE")
                            and motion["elapsed"] == before_motion["elapsed"] + 1
                            and motion["elapsed"] <= motion["plan"]["duration"],
                            "pickup selection stopped the target's accepted motion")
                    if motion["phase"] == "MOVING":
                        require(actor["commitSequence"] == before["commitSequence"]
                                and actor["reservationId"] == before["reservationId"] > 0
                                and [actor["engineObject"][k] for k in ("pos_x", "pos_z")]
                                    != [before["engineObject"][k] for k in ("pos_x", "pos_z")],
                                "pickup selection froze the target's rendered motion")
                        self.progress = dict(previous=deepcopy(before_sample), current=deepcopy(sample))
                else:
                    own = [e.get("data", {}) for e in events if e.get("kind") == "native"
                           and e.get("data", {}).get("actorHandle") == actor["handle"]["value"]]
                    require(before_motion["elapsed"] + 1 == before_motion["plan"]["duration"]
                            and any(e.get("event") == "CONTROL_RETURNED"
                                    and e.get("valueB") == before["commitSequence"] + 1 for e in own),
                            "pickup selection replaced target motion before its own control return")
        self.previous = (deepcopy(sample), deepcopy(actor), deepcopy(motion))

    def _profile(self, actor, resolved):
        require(isinstance(resolved, dict) and resolved.get("resolved") is True
                and resolved.get("sourceSha256") == self.source["profileSha256"],
                "pickup autonomy lacks its authored native target profile")
        raw = bytes.fromhex(resolved.get("resultHex", ""))
        require(len(raw) == 216 and struct.unpack_from("<II", raw, 188) ==
                (actor["matchedLayerMask"], actor["behaviorFingerprint"])
                and resolved.get("appliedOverrides") == actor["matchedLayerMask"]
                and resolved.get("fingerprint") == actor["behaviorFingerprint"]
                and resolved.get("lanes") == [raw[:80].hex(), raw[80:160].hex()],
                "pickup autonomy target profile bytes differ")

    def result(self):
        return dict(baseline=deepcopy(self.baseline), firstClaim=deepcopy(self.first),
                    movingProgress=deepcopy(self.progress), held=deepcopy(self.held),
                    freeClaimFrames=self.frames, ready=self.held is not None and self.progress is not None)


def verify_cargo_autonomy(witness, rows, source, subject):
    """Recheck the witness against its exact retained native stream."""
    require(isinstance(witness, dict) and witness.get("ready") is True,
            "pickup autonomy lacks its complete free-target and HELD witness")
    baseline, first = witness["baseline"], witness["firstClaim"]
    progress, held = witness["movingProgress"], witness["held"]
    require(type(witness.get("freeClaimFrames")) is int and witness["freeClaimFrames"] >= 2
            and baseline["sample"]["frame"] < first["frame"]
                <= progress["previous"]["frame"] < progress["current"]["frame"] < held["frame"],
            "pickup autonomy does not precede the actual held transfer")
    leaf = CargoAutonomy(source)
    def actor(sample):
        selected = select_current_actor(sample, subject)
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])
    for sample in (baseline["sample"], first, progress["previous"], progress["current"]):
        leaf._profile(actor(sample), baseline["profile"])
        if sample is not baseline["sample"]:
            _, timer = pickup_motion(sample, actor(sample), source)
            require(timer["movementActorControlMode"] == 0,
                    "pickup autonomy took target control before HELD")
    previous_motion, _ = pickup_motion(progress["previous"], actor(progress["previous"]), source)
    leaf.baseline = deepcopy(baseline)
    leaf.previous = (progress["previous"], actor(progress["previous"]), previous_motion)
    leaf.first = deepcopy(first)
    leaf.observe(progress["current"], actor(progress["current"]), [],
                 {baseline["profile"]["fingerprint"]: baseline["profile"]}, claimed=True, held=False)
    leaf.observe(held, actor(held), [], {}, claimed=True, held=True)
    if rows is None:
        return deepcopy(witness)
    samples, events = [], []
    for row in rows:
        samples.extend(row.get("samples", []))
        for key in ("initialSnapshot", "snapshot"):
            if key in row:
                samples.append(row[key])
        events.extend(row.get("initialEvents", []))
        events.extend(row.get("events", []))
        events.extend(row.get("receipt", {}).get("events", []))
    require(baseline["sample"] in samples and witness["held"] in samples
            and any(e.get("kind") == "native-observation" and e.get("data") == baseline["profile"]
                    for e in events),
            "pickup autonomy baseline is not its retained native stream")
    profiles = {e["data"]["fingerprint"]: e["data"] for e in events
                if e.get("kind") == "native-observation"
                and e.get("data", {}).get("observation") == "behavior-resolved"
                and e["data"].get("resolved") is True}
    meter = CargoAutonomy(source)
    def observe(sample):
        selected = select_current_actor(sample, subject)
        actor = next(a for a in sample["actors"] if a["handle"] == selected["handle"])
        targets = sample["pokemonCombat"]["interactions"]["throwState"]["targets"]
        codes = [v for v in targets if v & 63 == actor["handle"]["slot"] + 1]
        own_events = [e for e in events if e.get("frame") == sample["frame"]]
        meter.observe(sample, actor, own_events, profiles,
                      claimed=bool(codes), held=any(v & 128 for v in codes))
    observe(baseline["sample"])
    window = [s for s in samples if baseline["sample"]["frame"] < s["frame"] <= witness["held"]["frame"]]
    unique = {}
    for sample in window:
        require(sample["frame"] not in unique or unique[sample["frame"]] == sample,
                "pickup autonomy has conflicting native boundaries")
        unique[sample["frame"]] = sample
    for sample in sorted(unique.values(), key=lambda s: s["frame"]):
        observe(sample)
    require(meter.result() == witness, "pickup autonomy witness differs from the retained native stream")
    return deepcopy(witness)


def checked_moving_pickup(previous, current, events, source,
                          before, after, carrier_before, carrier):
    """Authenticate the existing native receipts; never infer a cancellation."""
    require(current["frame"] == previous["frame"] + 1
            and type(current.get("actorFrame")) is int
            and type(previous.get("actorFrame")) is int
            and current["actorFrame"] == previous["actorFrame"] + 1
            and current["nativeCycle"] >= previous["nativeCycle"]
            and current["context"] == previous["context"]
            and current["fieldControl"]["fieldPointer"] == previous["fieldControl"]["fieldPointer"],
            "moving pickup lacks adjacent current queue receipts")
    # Callers authenticate their authored bindings. This shared leaf checks
    # the same current public owners again before trusting native motion.
    for sample, actor in ((previous, before), (current, after),
                          (previous, carrier_before), (current, carrier)):
        select_current_actor(sample, actor)
    require(carrier_before["handle"] == carrier["handle"]
            and carrier_before["subjectIdentity"] == carrier["subjectIdentity"]
            and carrier_before["sourceIdentity"] == carrier["sourceIdentity"]
            and engine_binding_identity(carrier_before["engineIdentity"])
                == engine_binding_identity(carrier["engineIdentity"]),
            "moving pickup changed its carrier owner")
    motion, timer = pickup_motion(previous, before, source)
    ended, held = pickup_motion(current, after, source)
    plan = motion["plan"]
    require(before["handle"] == after["handle"]
            and before["subjectIdentity"] == after["subjectIdentity"]
            and before["sourceIdentity"] == after["sourceIdentity"]
            and engine_binding_identity(before["engineIdentity"])
                == engine_binding_identity(after["engineIdentity"])
            and motion["phase"] == before.get("motionPhase") == "MOVING"
            and plan["kind"] in (1, 2)
            and before.get("motionKind") == {1: "WALK", 2: "HOP"}[plan["kind"]]
            and plan["version"] == 1 and plan["fieldEpoch"] == before["handle"]["fieldEpoch"]
            and plan["flags"] == 0 and plan["visibilityPolicy"] == 0
            and plan["origin"] == list(tile(before, "origin"))
            and plan["target"] == list(tile(before, "target"))
            and plan["origin"] != plan["target"]
            and plan["reservationId"] == before["reservationId"] > 0
            and motion["elapsed"] == before["motionElapsed"]
            and plan["duration"] == before["motionDuration"]
            and 0 < motion["elapsed"] < plan["duration"]
            and timer["movementActorControlMode"] == 0,
            "moving pickup Cargo was not an ordinary accepted moving actor")
    # The native renderer's exact signed Lerp and Sway law. A phase label
    # alone cannot give credit to a body stopped at either endpoint.
    elapsed, duration = motion["elapsed"], plan["duration"]
    def lerp(a, b):
        delta = b - a
        return a + (1 if delta >= 0 else -1) * (abs(delta) * elapsed // duration)
    pose = [lerp((a << 16) + 32768, (b << 16) + 32768)
            for a, b in zip(plan["origin"], plan["target"])]
    sway_elapsed = elapsed * 2
    part = sway_elapsed - duration if sway_elapsed >= duration else sway_elapsed
    curve = 4 * part * (duration - part) // duration
    sway = plan["swayWidth"] * ((curve << 12) // duration)
    pose[1 if plan["origin"][1] == plan["target"][1] else 0] += -sway if sway_elapsed >= duration else sway
    require([before["engineObject"].get("pos_x"), before["engineObject"].get("pos_z")] == pose,
            "moving pickup Cargo body differs from its accepted native motion")
    state = current["pokemonCombat"]["interactions"]["throwState"]
    require(state["targets"][carrier["handle"]["slot"]] == ((after["handle"]["slot"] + 1) | 128)
            and held["movementActorControlMode"] == 1
            and [i for i, value in enumerate(state["targets"])
                 if value & 128 and value & 63 == after["handle"]["slot"] + 1] == [carrier["handle"]["slot"]]
            and ended["phase"] == "CANCELED" and ended["cancelReason"] == 16
            and ended["plan"] == plan and ended["commitPublished"] == 0
            and motion["elapsed"] <= ended["elapsed"] <= min(plan["duration"], motion["elapsed"] + 1)
            and after.get("motionPhase") == "CANCELED"
            and after.get("reservationId") == 0 and after.get("inputOwnership") == 0
            and after["commitSequence"] == before["commitSequence"],
            "moving pickup lacks its exact canceled receipt and HELD handoff")
    own = [e for e in events if e.get("kind") == "native"
           and e.get("data", {}).get("actorHandle") == after["handle"]["value"]
           and e["data"].get("event") in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED",
                                          "MOTION_CANCELED", "CONTROL_RETURNED")]
    expected = [("MOTION_CANCELED", plan["kind"], before["commitSequence"]),
                ("CONTROL_RETURNED", 0, before["commitSequence"])]
    require([(e["data"]["event"], e["data"].get("valueA"), e["data"].get("valueB")) for e in own] == expected
            and all(e.get("frame") == current["frame"]
                    and e["data"].get("frame") == e["data"].get("actorFrame") == current["actorFrame"]
                    and e["data"].get("actor") == {k: v for k, v in after["handle"].items() if k != "value"}
                    and e["data"].get("reason") == "CONTEXT_LOST"
                    and type(e["data"].get("sequence")) is int for e in own)
            and own[0]["data"]["sequence"] < own[1]["data"]["sequence"],
            "moving pickup lacks ordered exact Cargo CANCEL and CONTROL return")
    require(not any(e.get("kind") == "native"
                    and e.get("data", {}).get("actorHandle") == carrier["handle"]["value"]
                    and e["data"].get("event") == "MOTION_CANCELED" for e in events),
            "moving pickup canceled the carrier")
    return dict(frame=current["frame"], actorFrame=current["actorFrame"],
                handle=deepcopy(after["handle"]), motionIdentity=plan["reservationId"],
                source=deepcopy(source), previous=deepcopy(previous), current=deepcopy(current),
                events=deepcopy(events))

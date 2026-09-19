"""Replay real known-bad frames after a frozen normal Ledyba baseline.

Owns no emulator, writes, setup or acceptance. Expected fault detections stay
separate from failures; neither is normal-play credit.
"""
from copy import deepcopy

from tools.overworld.devtools_chain_measurement import LedybaChainMeasurement
from tools.overworld.devtools_records import GENERATION_FIELDS, select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder


def same_subject(left, right):
    return isinstance(left, dict) and isinstance(right, dict) and all(
        left.get(key) == right.get(key) for key in ("handle", "species", "role", "subjectIdentity"))


class LiveObserverControlMeasurement:
    def __init__(self, schema, source_sha256, *, max_frames):
        self.baseline = LedybaChainMeasurement(schema, source_sha256, max_frames=max_frames)
        self.max_frames = max_frames
        self.baseline_result = self.subject = self.latest = None
        self.render = MotionRecorder()
        self.histories, self.detections, self.failures = {}, {}, []
        self.armed_kind = None
        self.cleanup = None
        self.closed = False
        self.frames = 0

    def stage(self, name):
        return not self.failures and {"baseline": self.baseline_result is not None,
            "render-detected": "render-stall" in self.detections,
            "complete": len(self.detections) == 2}.get(name, False)

    def arm_args(self, subject, kind):
        if not self.stage("baseline") or not same_subject(subject, self.subject):
            raise ValueError("observer control requires its passed natural subject baseline")
        if kind not in ("render-stall", "inactive-object") or kind in self.histories:
            raise ValueError("observer control kind is invalid or already used")
        if kind == "inactive-object" and not self.stage("render-detected"):
            raise ValueError("identity control requires the retained live render detection")
        if self.armed_kind and self.armed_kind not in self.detections:
            raise ValueError("previous observer control has not completed")
        select_current_actor(self.latest, self.subject)
        self.armed_kind = kind
        return {"subject": {key: deepcopy(self.subject[key]) for key in
                            ("handle", "species", "role", "subjectIdentity")},
                "kind": kind, "maxFrames": 1200}

    def expected_identity_failure(self, snapshot, subject):
        detection = self.detections.get("inactive-object", {})
        return not self.failures and detection.get("frame") == snapshot.get("frame") \
            and same_subject(subject, self.subject)

    def observe_cleanup(self, receipt):
        if not self.stage("complete") or self.cleanup is not None:
            raise ValueError("cleanup requires the two completed live controls exactly once")
        value, snapshot = receipt.get("observerControl", {}), receipt.get("snapshot", {})
        if receipt.get("closed") is not True or receipt.get("frame") != self.latest["frame"] \
                or snapshot.get("frame") != self.latest["frame"] \
                or value.get("kind") != "inactive-object" or value.get("closed") is not True \
                or value.get("cleanupPending") is not False or value.get("failure") is not None \
                or not same_subject(value.get("subject"), self.subject):
            raise ValueError("control cleanup has no exact terminal restore receipt")
        previous = self.histories["inactive-object"]
        rows = value.get("receipts", [])
        if len(rows) != len(previous) + 1 or rows[:-1] != previous:
            raise ValueError("control cleanup changed the retained fault history")
        restore = rows[-1]
        selected = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])
        bad = next(a for a in self.latest["actors"] if a.get("handle") == selected["handle"])
        if actor.get("sourceIdentity") != bad.get("sourceIdentity") \
                or any(actor.get(k) != bad.get(k) for k in GENERATION_FIELDS) \
                or any(actor["engineIdentity"].get(k) != v for k, v in bad["engineIdentity"].items()
                       if k not in ("active", "id_lookup")):
            raise ValueError("control cleanup source or native binding changed")
        if restore.get("action") != "active-bit-restored" or restore.get("frame") != self.latest["frame"] \
                or restore.get("sourceIdentity") != actor.get("sourceIdentity") \
                or restore.get("beforeFlags") != bad["engineObject"]["flags"] \
                or restore.get("afterFlags") != restore["beforeFlags"] | 1 \
                or actor["engineObject"]["flags"] != restore["afterFlags"]:
            raise ValueError("control cleanup did not restore only its owned active bit")
        self.cleanup = deepcopy(receipt)

    def _control(self, snapshot):
        value = snapshot.get("observerControl")
        if not isinstance(value, dict) or value.get("kind") != self.armed_kind \
                or not same_subject(value.get("subject"), self.subject) \
                or value.get("failure") is not None or value.get("scope") != "native-observer-control-only":
            raise ValueError("armed native control has no exact current receipt")
        receipts = value.get("receipts")
        if not isinstance(receipts, list) or not 1 <= len(receipts) <= 8:
            raise ValueError("native control receipt bound differs")
        previous = self.histories.get(self.armed_kind, [])
        if receipts[:len(previous)] != previous:
            raise ValueError("native control receipt history changed")
        actor = next(a for a in snapshot["actors"] if a.get("handle") == self.subject["handle"])
        for item in receipts:
            if item.get("type") != "native-observer-control-v1" \
                    or item.get("kind") != self.armed_kind \
                    or not same_subject(item.get("subject"), self.subject) \
                    or item.get("sourceIdentity") != actor.get("sourceIdentity") \
                    or item.get("context") != {k: snapshot["context"][k] for k in ("fieldEpoch", "mapGeneration", "mapId")} \
                    or type(item.get("frame")) is not int or item["frame"] > snapshot["frame"]:
                raise ValueError("control receipt source/context/frame differs")
        self.histories[self.armed_kind] = deepcopy(receipts)
        return value, actor, [item for item in receipts if item["frame"] == snapshot["frame"]]

    def observe(self, snapshot, events=()):
        if self.closed: raise ValueError("observer measurement is closed")
        if self.failures: return self.result()
        try:
            frame = snapshot["frame"]
            if self.latest is not None and frame != self.latest["frame"] + 1:
                raise ValueError("observer control lost a completed frame")
            self.frames += 1
            if self.frames > self.max_frames: raise ValueError("observer control frame budget exceeded")
            coverage = snapshot.get("nativeObservation", {})
            if snapshot.get("observationBoundary") != "main-task-queue-completion" \
                    or coverage.get("coverageComplete") is not True or coverage.get("installedBeforeBoot") is not True \
                    or any(coverage.get(key) != 0 for key in ("eventsDropped", "profilesEvicted", "pendingUnframedEvents")) \
                    or coverage.get("error") is not None:
                raise ValueError("observer control frame lacks complete native observation")
            self.latest = deepcopy(snapshot)
            if self.baseline_result is None:
                if snapshot.get("observerControl"):
                    raise ValueError("fault was armed before the normal baseline")
                measured = self.baseline.observe(snapshot, events)
                if measured["failures"]: raise ValueError("normal baseline failed: " + str(measured["failures"][:1]))
                if measured["ready"]:
                    self.baseline_result = self.baseline.finish()
                    self.subject = deepcopy(measured["subject"])
                return self.result()
            if self.armed_kind is None:
                if snapshot.get("prepared") is not False or snapshot.get("observerControl"):
                    raise ValueError("unarmed baseline subject was changed")
                select_current_actor(snapshot, self.subject)
                return self.result()
            if snapshot.get("prepared") is not True:
                raise ValueError("native fault must be marked non-normal")
            value, actor, fresh = self._control(snapshot)
            if self.armed_kind == "render-stall":
                select_current_actor(snapshot, self.subject)
                pinned = [r for r in value["receipts"] if r["action"] == "render-pinned"]
                if pinned:
                    self.render.observe(frame, actor, actor["engineObject"])
                    for item in fresh:
                        if item["action"] in ("render-pinned", "render-restored") \
                                and any(item["afterPose"].get(k) != actor["engineObject"].get(k)
                                        for k in ("pos_x", "pos_z", "flags")):
                            raise ValueError("render control readback differs from recorded frame")
                if value.get("state") == "complete":
                    writes = [r for r in value["receipts"] if r["action"] == "render-restored"]
                    detected = [f for f in self.render.failures if f.get("reason") == "render-stall"]
                    if len(pinned) != 1 or len(writes) != 2 or value.get("writes") != 2 \
                            or [r["frame"] for r in writes] != [pinned[0]["frame"] + 1, pinned[0]["frame"] + 2] \
                            or not detected:
                        raise ValueError("live render fault lacks two frames and actual recorder rejection")
                    self.detections["render-stall"] = {"frame": frame, "faultFrames": 2,
                        "failures": deepcopy(detected), "receipts": deepcopy(value["receipts"])}
            else:
                cleared = [r for r in fresh if r["action"] == "active-bit-cleared"]
                if len(cleared) != 1 or value.get("state") != "complete" or value.get("writes") != 1:
                    raise ValueError("inactive control lacks its single current native write")
                item = cleared[0]
                engine = actor["engineIdentity"]
                before = item["engineIdentity"]
                if not item["beforeFlags"] & 1 or item["afterFlags"] != item["beforeFlags"] & ~1 \
                        or actor["engineObject"]["flags"] != item["afterFlags"] or engine.get("active") is not False \
                        or any(engine.get(k) != v for k, v in before.items() if k not in ("active", "id_lookup")):
                    raise ValueError("inactive fault changed more than the selected active bit")
                try: select_current_actor(snapshot, self.subject)
                except ValueError as error:
                    self.detections["inactive-object"] = {"frame": frame, "failure": str(error),
                        "receipts": deepcopy(value["receipts"])}
                else: raise ValueError("actual identity reader accepted the inactive object")
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append({"code": "observer-control-measurement", "frame": snapshot.get("frame"), "message": str(error)})
        return self.result()

    def result(self):
        ready = self.stage("complete")
        baseline = self.baseline_result or self.baseline.result()
        return {"passed": self.closed and ready and self.cleanup is not None, "ready": ready, "acceptedProof": False,
            "subject": deepcopy(self.subject or baseline.get("subject")), "frames": self.frames, "baseline": deepcopy(self.baseline_result),
            "detections": deepcopy(self.detections), "failures": deepcopy(self.failures),
            "cleanup": deepcopy(self.cleanup),
            "measurementErrors": [], "completeMotions": baseline.get("completeMotions", 0),
            "eligibleMoves": baseline.get("eligibleMoves", 0), "spawnPassed": baseline.get("spawnPassed", False),
            "scope": "separate live recorder controls; no normal-play credit"}

    def finish(self):
        self.closed = True
        if (not self.stage("complete") or self.cleanup is None) and not self.failures:
            self.failures.append({"code": "observer-control-incomplete", "frame": self.latest.get("frame") if self.latest else None})
        return self.result()

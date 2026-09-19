"""Controlled retry proof over the normal Ledyba reader; no IO or acceptance."""
from copy import deepcopy

from tools.overworld.devtools_chain_measurement import LedybaChainMeasurement
from tools.overworld.devtools_records import select_current_actor


class ChainRetryMeasurement:
    def __init__(self, schema, expected_source_sha256, *, max_frames):
        self.base = LedybaChainMeasurement(schema, expected_source_sha256, max_frames=max_frames)
        self.latest = self.arm = self.injection = self.rejected = self.retried = None
        self.retry_attempt = None
        self.started_attempt = None
        self.cooldowns = []
        self.idle_frames = []
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.base, name)

    def _require(self, condition, message):
        if not condition:
            raise ValueError(message)

    def _subject(self, value):
        self._require(self.base._same_subject(value), "retry subject differs")
        for key in ("form", "level", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"):
            self._require(value.get(key) == self.actor.get(key), "retry subject generation differs")

    @property
    def actor(self):
        return next(a for a in self.latest["actors"] if a["handle"] == self.subject["handle"])

    def stage(self, name):
        if name == "complete":
            return self.result()["ready"]
        if name != "baseline":
            raise ValueError("unknown chain retry stage")
        r = self.base.result()
        return not self.arm and not self.failures and not r["measurementErrors"] and r["spawnPassed"] \
            and r["eligibleMoves"] >= 1 and self.latest is not None

    def arm_args(self, subject):
        self._require(self.stage("baseline"), "chain retry baseline is not ready")
        self._require(subject.get("handle") == self.subject["handle"], "arm subject differs")
        return {"subject": deepcopy(subject), "maxFrames": 1800}

    def observe_control(self, receipt, snapshot):
        try:
            self._require(self.stage("baseline"), "chain retry may arm only once after natural baseline")
            self._require(receipt.get("armed") is True and receipt.get("prepared") is True
                and receipt.get("snapshot") == snapshot and snapshot.get("prepared") is True,
                "invalid chain retry arm receipt")
            self._require(receipt.get("frame") == self.latest["frame"] and all(snapshot.get(k) == self.latest.get(k)
                for k in ("frame", "nativeCycle", "context", "actors")), "arm changed the completed state")
            control = receipt.get("chainRetryControl")
            self._require(isinstance(control, dict) and control == snapshot.get("chainRetryControl")
                and control.get("armed") is True and control.get("injected") is False,
                "arm control state differs")
            self._require(control.get("subject") == select_current_actor(self.latest, self.subject),
                          "arm control subject differs")
            self.arm = deepcopy(receipt)
            self.base.accepted_setup_mode = "prepared"
            self.latest = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.base._fail("invalid-chain-retry-control", message=str(error))
        return self.result()

    def _parent(self, event):
        data = event["data"]
        if self.retried is not None:
            self._require(data.get("controlAttemptId") is None, "duplicate rejection")
            return
        if data.get("controlAttemptId") is None and self.rejected is None:
            return
        self._subject(data.get("publicSubject")); self._subject(data.get("publicSubjectAfter"))
        clocks = [data.get("entryClock"), data.get("returnClock")]
        self._require(clocks == [
            {"actorFrame": data.get("entryActorFrame"), "nativeCycle": data.get("entryNativeCycle")},
            {"actorFrame": data.get("returnActorFrame"), "nativeCycle": data.get("returnNativeCycle")}],
            "retry parent clocks differ from native tap")
        self._require(all(isinstance(c, dict) and type(c.get("nativeCycle")) is int
            and type(c.get("actorFrame")) is int for c in clocks)
            and self.arm["snapshot"]["nativeCycle"] <= clocks[0]["nativeCycle"] <= clocks[1]["nativeCycle"] <= self.latest["nativeCycle"]
            and clocks[0]["actorFrame"] <= clocks[1]["actorFrame"], "retry parent clock differs")
        selected = [b for b in self.boundaries if b["selected"] and b["frame"] <= event["frame"]]
        self._require(bool(selected), "retry has no natural selected action")
        boundary = selected[-1]
        before, after = data["policyBefore"], data["policyAfter"]
        expected = {"chainPauseAction": 0x80 | bytes.fromhex(boundary["responseHex"])[22],
                    "chainPauseTicks": bytes.fromhex(boundary["responseHex"])[23]}
        self._require(all(before.get(k) == v for k, v in expected.items()), "retry lost selected action or ticks")
        if data.get("controlAttemptId") is not None:
            self._require(self.arm is not None and self.rejected is None, "missing arm or duplicate rejection")
            self._require(all(after.get(k) == v for k, v in expected.items())
                and data.get("movementCooldownAfter") == 1, "retry did not restore pending action and cooldown")
            self._require(data["publicSubject"]["commitSequence"] == data["publicSubjectAfter"]["commitSequence"]
                == boundary["commitSequence"] and data["publicSubjectAfter"]["motionPhase"] == "IDLE",
                "rejected start advanced motion or commit")
            self._require(self.injection is not None and data.get("attemptIds") == [self.injection["attemptId"]]
                and clocks[0]["nativeCycle"] <= self.injection["entryClock"]["nativeCycle"] <= clocks[1]["nativeCycle"]
                and self.injection["policyBefore"] == before, "rejection is not owned by its selected parent")
            self.rejected = {**deepcopy(data), "nativeCompletedFrame": data.get("frame"),
                "frame": event["frame"], "decisionFrame": boundary["frame"]}
        elif self.retried is None:
            self._require(event["frame"] > self.rejected["frame"] and data.get("movementCooldownBefore") == 0
                and any(self.rejected["frame"] <= row["frame"] < event["frame"]
                    and self.rejected["returnClock"]["nativeCycle"] <= row["nativeCycle"] <= clocks[0]["nativeCycle"]
                    for row in self.idle_frames), "retry skipped its full cooldown frame")
            self._require(data["publicSubject"]["commitSequence"] == self.rejected["publicSubject"]["commitSequence"],
                "commit changed before retry")
            self._require(self.started_attempt is not None and data.get("attemptIds") == [self.started_attempt["data"]["attemptId"]],
                "successful retry has no owned native attempt")
            self._require(self.started_attempt["data"].get("nativeOrigin") == self.retry_attempt["data"].get("nativeOrigin"),
                "retry changed its stationary origin")
            self.retried = {**deepcopy(data), "nativeCompletedFrame": data.get("frame"), "frame": event["frame"]}

    def _control(self, snapshot, events):
        control = snapshot.get("chainRetryControl")
        if not self.arm:
            self._require(control is None, "unarmed retry control appeared")
            return
        self._require(isinstance(control, dict) and control.get("armed") is True, "retry control disappeared")
        self._require(control.get("failure") is None and control.get("acceptedProof") is False
            and control.get("guestMemoryWrites") == 0 and control.get("pendingWrites") == 0,
            "retry native control failed or changed guest memory")
        injection = control.get("injection")
        if injection is not None:
            if self.injection is not None:
                self._require(injection == self.injection, "injection receipt changed")
            else:
                self._require(self.base._same_subject(injection.get("subject"))
                    and all(injection["subject"].get(k) == self.actor.get(k) for k in
                        ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")),
                    "injection bound subject differs")
                self._require(injection.get("returnReason") == 8 and type(injection.get("returnReason")) is int
                    and injection.get("guestMemoryWrites") == 0 and type(injection.get("guestMemoryWrites")) is int,
                    "rejection was not the one owned no-write start")
                current = injection["current"]
                self._subject(current.get("publicSubject"))
                self._require(all(current["sourceIdentity"].get(k) == self.actor["sourceIdentity"].get(k)
                        for k in ("object", "species", "form", "level", "personality", "object_id", "map_id", "encounter_generation"))
                    and all(current["engineIdentity"].get(k) == self.actor["engineIdentity"].get(k)
                        for k in ("pointer", "object_manager", "current_manager")), "injection object owner differs")
                before, after = injection["registersBefore"], injection["registersAfter"]
                self._require(set(before) == {"r" + str(i) for i in range(15)} and set(after) == set(before)
                    and all(type(v) is int and 0 <= v <= 0xffffffff for v in before.values())
                    and after == {**before, "r0": 8}, "injection changed preserved registers")
                self._require(injection["requestedArguments"] == [before["r" + str(i)] for i in range(4)]
                    and injection["returnAddress"] == before["r14"] and before["r14"] & 1
                    and type(injection["entryAddress"]) is int and 0x02000000 <= injection["entryAddress"] < 0x02400000
                    and not injection["entryAddress"] & 1
                    and len(injection["stackArguments"]) == 7
                    and all(type(v) is int and 0 <= v <= 0xffffffff for v in injection["stackArguments"]),
                    "injection arguments or native return differ")
                self.injection = deepcopy(injection)
        self._require(control.get("injected") is (self.injection is not None), "injection flag differs")
        for event in events:
            data = event.get("data", {})
            if event.get("kind") != "native-observation" or data.get("observation") != "chain-reposition-attempt":
                continue
            if self.injection and data.get("attemptId") == self.injection.get("attemptId"):
                self._subject(data.get("publicSubject")); self._subject(data.get("publicSubjectAfter"))
                native = data.get("nativeResult", {})
                self._require(data.get("returnValue") == 0 and native.get("outcome") == 0
                    and native.get("reason") == 8 and native.get("encodedRemaining") == data.get("encodedRemaining"),
                    "injected attempt did not return unchanged RETRY")
                starts = data.get("preparedStarts", [])
                self._require(len(starts) == 1 and starts[0].get("returnValue") == 8
                    and starts[0].get("accepted") is False and starts[0].get("hopPlans") == []
                    and starts[0].get("motionRequests") == [], "rejected start performed native motion work")
                self.retry_attempt = deepcopy(event)
            elif self.rejected and self.started_attempt is None:
                self._subject(data.get("publicSubject")); self._subject(data.get("publicSubjectAfter"))
                self._require(data.get("returnValue") == 1 and data.get("nativeResult", {}).get("outcome") == 1,
                    "next retry did not start the pending action")
                self.started_attempt = deepcopy(event)
        boundaries = control.get("cooldownBoundaries", [])
        self._require(isinstance(boundaries, list) and len(boundaries) <= 120, "cooldown boundary bound exceeded")
        self._require(boundaries[:len(self.cooldowns)] == self.cooldowns, "cooldown history changed")
        for row in boundaries[len(self.cooldowns):]:
            self._require(type(row.get("frame")) is int and row["frame"] == snapshot["frame"]
                and row.get("nativeCycle") == snapshot["nativeCycle"], "cooldown evidence is stale")
            self._subject(row.get("publicSubject"))
            self._require(type(row.get("movementCooldown")) is int and 0 <= row["movementCooldown"] <= 255,
                "cooldown is not a native byte")
            self.cooldowns.append(deepcopy(row))

    def observe(self, snapshot, events):
        if self.closed or self.failures:
            return self.result()
        self.base.observe(snapshot, events)
        if self.failures:
            return self.result()
        self.latest = deepcopy(snapshot)
        try:
            self._control(snapshot, events)
            for event in events:
                if event.get("kind") == "native-observation" and event["data"].get("observation") == "chain-retry-parent":
                    self._parent(event)
            if self.rejected and not self.retried:
                self._require(self.actor["motionPhase"] == "IDLE" and self.actor["commitSequence"]
                    == self.rejected["publicSubject"]["commitSequence"], "premature retry motion or commit")
                expected = self.rejected["policyAfter"]
                for row in self.cooldowns:
                    self._require(row["publicSubject"]["commitSequence"] == self.rejected["publicSubject"]["commitSequence"]
                        and all(row.get("policy", {}).get(k) == expected[k] for k in ("chainPauseAction", "chainPauseTicks")),
                        "cooldown lost pending action, ticks or commit")
                current = [row for row in self.cooldowns if row["frame"] == snapshot["frame"]]
                origin = self.retry_attempt["data"].get("nativeOrigin") if self.retry_attempt else None
                actor, engine = self.actor, self.actor["engineObject"]
                self._require(isinstance(origin,list) and len(origin)==2
                    and [actor["logical"]["x"],actor["logical"]["y"]] == origin
                    and [engine["x"],engine["y"]] == origin
                    and [engine["pos_x"],engine["pos_z"]] == [(x<<16)+0x8000 for x in origin]
                    and actor["motionKind"] == "NONE" and not actor["inputOwnership"] and not actor["reservationId"],
                    "retry idle frame changed position or control")
                if current:
                    self._require(len(current)==1 and current[0]["movementCooldown"] in (0,1), "invalid consumed retry cooldown")
                    self.idle_frames.append({"frame":snapshot["frame"],"nativeCycle":snapshot["nativeCycle"],
                        "actor":deepcopy(actor),"context":deepcopy(snapshot["context"]),"cooldown":deepcopy(current[0])})
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.base._fail("invalid-chain-retry", message=str(error))
        return self.result()

    def result(self):
        result = self.base.result()
        completed = [a for a in result["actions"] if self.rejected and a["decisionFrame"] == self.rejected["decisionFrame"]]
        checks = {"naturalSubjectAndBaseline": self.arm is not None,
            "selectedActionAndTicksPreserved": self.rejected is not None,
            "fullCooldownFrame": self.retried is not None and self.retried.get("movementCooldownBefore") == 0
                and bool(self.idle_frames),
            "oneInjectedRejection": self.injection is not None and self.retry_attempt is not None
                and self.rejected is not None and self.rejected["controlAttemptId"] == self.injection["attemptId"],
            "profileDefinedCompleteAction": len(completed) == 1 and completed[0]["motions"] == 4
                and self.started_attempt is not None and self.retried is not None
                and self.started_attempt["frame"] == self.retried["frame"]
                and completed[0]["startFrame"] == self.retried["frame"],
            "nativeMotionAndControl": len(completed) == 1 and not result["measurementErrors"]
                and result["stopBoundary"] is not None}
        ready = all(checks.values()) and not self.failures and not self.pending_resets
        result.update(ready=ready, passed=self.closed and ready,
            state="failed" if self.failures else "completed" if self.closed and ready else "observing",
            proofChecks=checks, retryProof={"arm": deepcopy(self.arm), "rejected": deepcopy(self.rejected),
                "retried": deepcopy(self.retried), "injection": deepcopy(self.injection), "cooldownBoundaries": deepcopy(self.cooldowns),
                "completedIdleFrames":deepcopy(self.idle_frames)},
            scope="one controlled retry after natural Ledyba acquisition; not normal-only timing or accepted proof")
        return result

    def finish(self):
        self.closed = True
        if not self.result()["ready"]:
            self.base._fail("incomplete-chain-retry")
        return self.result()


RETRY_FAULTS = ("retry-wrong-subject", "retry-lost-ticks", "retry-changed-commit",
                "retry-missing-cooldown", "retry-native-request", "retry-changed-register",
                "retry-missing-parent", "retry-missing-control-return")


class ChainRetryNegative:
    """Change one retained input row, then replay through the same checker."""
    def __init__(self, fault):
        if fault not in RETRY_FAULTS:
            raise ValueError("unknown copied chain retry fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.applied or not isinstance(row, dict):
            return row
        selected = [s for s in subjects.values() if s.get("species") == 165 and s.get("role") == "WILD"]
        if len(selected) != 1:
            return row
        result = deepcopy(row)
        for event in result.get("events", []):
            data = event.get("data", {})
            if data.get("observation") == "chain-retry-parent" and data.get("controlAttemptId") is not None:
                if self.fault == "retry-wrong-subject": data["publicSubjectAfter"]["subjectIdentity"] ^= 1
                elif self.fault == "retry-lost-ticks": data["policyAfter"]["chainPauseTicks"] ^= 1
                elif self.fault == "retry-changed-commit": data["publicSubjectAfter"]["commitSequence"] += 1
                elif self.fault == "retry-missing-parent": data["observation"] = "copied-data-removed-parent"
                else: continue
                self.applied = True; return result
            if self.fault == "retry-native-request" and data.get("observation") == "chain-reposition-attempt" \
                    and data.get("nativeResult", {}).get("reason") == 8 and data.get("preparedStarts"):
                data["preparedStarts"][0]["motionRequests"] = [{"copiedControl": True}]
                self.applied = True; return result
            if self.fault == "retry-missing-control-return" and data.get("event") == "CONTROL_RETURNED" \
                    and any(s.get("chainRetryControl", {}).get("injected") for s in result.get("samples", [])):
                data["event"] = "WORLD_EFFECT"; self.applied = True; return result
        for snapshot in result.get("samples", []):
            control = snapshot.get("chainRetryControl") or {}
            if self.fault == "retry-changed-register" and control.get("injection"):
                control["injection"]["registersAfter"]["r13"] ^= 4
                self.applied = True; return result
            if self.fault == "retry-missing-cooldown":
                if control.get("cooldownBoundaries"):
                    control["cooldownBoundaries"] = []; self.applied = True; return result
        return row

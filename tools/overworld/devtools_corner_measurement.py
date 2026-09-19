"""Pure, bounded diagonal-corner witness. No driver and no proof acceptance.

The retained corner scenario supplies the seven rows and exact semantic event
contract. A false strict return is NOT a substitute for REJECTED_SIDE_TILE.
Feed full (artifact-expanded) events before their completed-frame snapshot.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_wild_walk_measurement import IDENTITY

KEYS = {"UP": 64, "DOWN": 128, "LEFT": 32, "RIGHT": 16}
CARDINALS = {64: (0, 0, -1), 128: (1, 0, 1), 32: (2, -1, 0), 16: (3, 1, 0)}
DIAGONALS = {4: (96, -1, -1, 0, 2), 5: (80, 1, -1, 0, 3),
             6: (160, -1, 1, 1, 2), 7: (144, 1, 1, 1, 3)}
LIFECYCLE = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
ENVELOPE = {"observation", "sequence", "entryActorFrame", "entryNativeCycle",
            "returnActorFrame", "returnNativeCycle", "setupMode"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


class CornerMeasurement:
    def __init__(self, max_frames):
        require(type(max_frames) is int and 1 <= max_frames <= 600, "invalid corner frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.actor = self.subject = self.query = None
        self.blocked = self.recovery_frame = self.recovery_target = None
        self.frames = self.sequence = 0
        self.streams = {}
        self.events, self.traces, self.calls, self.commands, self.inputs = [], [], [], [], []
        self.failures = []
        self.closed = False
        self.reader_closed_frame = None
        self.cleanup = None

    def probe(self, receipt, snapshot):
        require(self.initial is None and self.query is None, "corner query already supplied")
        q = receipt.get("value", receipt)
        require(q.get("completed") is True and q.get("prepared") is True
                and q.get("acceptedProof") is False and q.get("batchAdvancedFrames") == 0
                and q.get("scope") == "prepared-mounted-corner-query"
                and q["before"] == q["after"], "corner query incomplete or changed state")
        select_current_actor(snapshot, q["subject"])
        require(q["before"]["origin"] == [snapshot["player"][k] for k in ("x", "y")]
                and q["before"]["player"] == q["subject"]["engineIdentity"]["anchorPointer"]
                and q["before"]["frame"] <= snapshot["frame"], "corner query point or anchor differs")
        require(len(q["cardinals"]) == 4 and len(q["diagonals"]) == 4, "corner query rows missing")
        for direction, row in enumerate(q["cardinals"]):
            require(row.get("direction") == direction and type(row.get("result")) is int
                    and row["result"] & ~0x2F == 0 and row.get("open") is (row["result"] == 0),
                    "corner cardinal mask differs")
        x, y = q["before"]["origin"]
        for direction, row in zip(DIAGONALS, q["diagonals"]):
            _, dx, dy, v, h = DIAGONALS[direction]
            count = sum(q["cardinals"][d]["result"] != 0 for d in (v, h))
            require(row.get("direction") == direction and row.get("target") == [x+dx, y+dy]
                    and row.get("sideDirections") == [v, h]
                    and type(row.get("result")) is int and row["result"] in (0, 1)
                    and row.get("destinationOpen") is bool(row["result"])
                    and row.get("blockedSides") == count
                    and row.get("oneSideCorner") is (bool(row["result"]) and count == 1),
                    "corner destination or side query differs")
        require(any(r["oneSideCorner"] for r in q["diagonals"]), "no open one-side corner")
        self.query = deepcopy(q)
        return self.result()

    def _actor(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(a for a in snapshot["actors"] if a["handle"] == selected["handle"])
        if self.actor is not None:
            require(all(actor.get(k) == self.actor.get(k) for k in IDENTITY)
                    and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
                    and engine_binding_identity(actor["engineIdentity"]) == engine_binding_identity(self.actor["engineIdentity"])
                    and snapshot["context"] == self.initial["context"], "corner actor, profile or context changed")
        require(actor["species"] == 155 and actor["role"] == "MOUNTED"
                and actor.get("inputOwnership") == 1, "corner requires live mounted Cyndaquil")
        reservations = []
        for current in snapshot["actors"]:
            if current.get("active"):
                require(current.get("presentationAttached") is True
                        and current["handle"]["fieldEpoch"] == snapshot["context"]["fieldEpoch"],
                        "active actor presentation or epoch differs")
                if current.get("reservationId"):
                    reservations.append(current["reservationId"])
        require(len(set(reservations)) == len(reservations), "duplicate target reservation")
        return actor

    def _reader(self, receipt, closed):
        r = receipt.get("walkCorner", receipt)
        require(r.get("armed") is True and r.get("closed") is closed and r.get("failure") is None
                and r.get("acceptedProof") is False and r.get("guestMemoryWrites") == 0
                and r.get("subject") == self.subject and r.get("startFrame") == self.initial["frame"],
                "corner reader identity, boundary or status differs")
        strip = lambda rows: [{k:v for k,v in row.items() if k not in ENVELOPE} for row in rows]
        require(strip(r.get("calls", [])) == strip(self.calls) and r.get("counts") == dict(strict=len(self.calls),
                collision=sum(len(c["collisions"]) for c in self.calls),
                landing=sum(len(c["landings"]) for c in self.calls)), "corner native receipts lost")
        return r

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        require(self.initial is None and self.query is not None, "corner needs one prepared query before arm")
        self.subject = deepcopy(subject)
        self.actor = deepcopy(self._actor(snapshot))
        self.initial = self.last = deepcopy(snapshot)
        require(self.actor["motionPhase"] == "IDLE" and self.actor["motionKind"] == "NONE"
                and self.actor["reservationId"] == 0, "corner arm is not idle")
        select_current_actor(snapshot, self.query["subject"])
        require(self.actor["logical"] == dict(zip(("x", "y"), self.query["before"]["origin"]))
                and self.query["subject"]["handle"] == self.subject["handle"], "query no longer binds corner actor")
        self._reader(receipt, False)
        self.sequence = snapshot["nativeObservation"]["sequence"]
        self.streams = dict(trace_sequences or {})
        return self.result()

    def command(self, request, receipt):
        """Receive a completed normal step; request contains op,args,startFrame."""
        try:
            require(self.initial is not None and not self.closed, "corner window is not open")
            args = request["args"]
            r = receipt.get("receipt", receipt)
            n = r.get("completedGameFrames")
            require(request.get("op") == "step" and receipt.get("ok", True) is True
                    and type(n) is int and 1 <= n <= args["frames"] <= self.max_frames
                    and r.get("requestedGameFrames") == args["frames"]
                    and r.get("observedFieldFrames") == n, "corner normal-input receipt differs")
            keys = args["keys"]
            require(isinstance(keys, list) and len(keys) == len(set(keys)) and all(k in KEYS for k in keys),
                    "corner normal input keys differ")
            start = request["startFrame"]
            require(type(start) is int and start >= self.initial["frame"]
                    and (not self.commands or start == self.commands[-1]["endFrame"]), "corner command frame gap")
            require(len(self.commands) < self.max_frames, "corner command bound exceeded")
            self.commands.append(dict(startFrame=start, endFrame=start+n,
                mask=sum(KEYS[k] for k in keys), request=deepcopy(request), receipt=deepcopy(receipt)))
        except (ValueError, KeyError, TypeError) as error:
            self.failures.append(str(error))
        return self.result()

    def _strict(self, data):
        require(self.recovery_frame is None and len(self.calls) < 128, "late or excess strict corner call")
        before = data["before"]
        public = before["publicSubject"]
        require(all(public.get(k) == self.actor.get(k) for k in IDENTITY)
                and before["subject"] == self.subject
                and before["sourceIdentity"] == self.actor["sourceIdentity"]
                and all(v == self.actor["engineIdentity"].get(k) for k, v in before["engineIdentity"].items())
                and before["playerPointer"] == self.actor["engineIdentity"]["anchorPointer"]
                and before["mountPointer"] == self.actor["engineIdentity"]["pointer"]
                and all(before["worldContext"][k] == self.initial["context"][k]
                        for k in ("mapId", "mapGeneration", "fieldEpoch")), "strict corner native identity differs")
        require(public.get("logical") == self.actor["logical"]
                and public.get("commitSequence") == self.actor["commitSequence"]
                and public.get("motionPhase") == "IDLE" and public.get("reservationId") == 0,
                "strict corner call did not stay idle")
        direction = data["direction"]
        require(direction in DIAGONALS, "strict corner direction differs")
        mask, _, _, _, _ = DIAGONALS[direction]
        query = self.query["diagonals"][direction-4]
        require(query["oneSideCorner"] and data["origin"] == self.actor["logical"]
                and [data["target"][k] for k in ("x", "y")] == query["target"]
                and data["normalReturn"] is True and type(data["returnValue"]) is int
                and data["returnValue"] == 0 and data["input"]["heldKeys"] == mask
                and data["input"]["rawHeld"] == mask and data["input"]["simulatedKeys"] == 0,
                "strict corner decision or normal input differs")
        if 'returnKind' in data or 'rawReturnValue' in data:
            # include/overworld_motion_model.h: SIDE_BLOCKED=(1u<<1).
            # Retained old diagnostics lack both fields; new native readers
            # must preserve their actual classifier kind and raw result.
            kind,raw_return=data.get('returnKind'),data.get('rawReturnValue')
            require(type(raw_return) is int and ((kind=='candidate-flags' and raw_return==2)
                    or (kind=='bool' and raw_return==0)) and data['returnValue']==0,
                    'corner raw rejection kind or flags differ')
        raw = bytes.fromhex(self.query["before"]["mountStateHex"])
        binding = data["mountBinding"]
        require(data["profileHex"] == raw[8:80].hex() and data["profile19"] == raw[27]
                and binding["bindingHex"] == raw[80:96].hex()
                and binding["sessionGeneration"] == struct.unpack_from("<I", raw, 96)[0]
                and binding["fieldPointer"] == struct.unpack_from("<I", raw)[0]
                and binding["surfacePointer"] == struct.unpack_from("<I", raw, 4)[0]
                and data["avatarPointer"] == self.query["before"]["avatar"]
                and data["playerPointer"] == self.query["before"]["player"], "corner prepared/native binding differs")
        collisions = data["collisions"]
        require(1 <= len(collisions) <= 2 and not data["landings"], "blocked corner nested call shape differs")
        for index, child in enumerate(collisions):
            d = query["sideDirections"][index]
            require(child["direction"] == d and child["normalReturn"] is True
                    and type(child["rawMask"]) is int and child["rawMask"] == child["returnValue"]
                    == self.query["cardinals"][d]["result"] and child["before"] == before
                    and child["profileHex"] == data["profileHex"] and child["input"] == data["input"]
                    and data["entryClock"]["nativeCycle"] <= child["entryClock"]["nativeCycle"]
                    <= child["returnClock"]["nativeCycle"] <= data["returnClock"]["nativeCycle"],
                    "corner nested collision binding, clock or mask differs")
            require((child["rawMask"] != 0) is (index == len(collisions)-1), "corner short circuit differs")
        if self.calls:
            require(direction == self.calls[0]["direction"], "corner changed diagonal direction")
        self.calls.append(deepcopy(data))

    def feed_event(self, event):
        require(len(self.events) < 4096, "corner pending event bound exceeded")
        self.events.append(deepcopy(event))

    def feed_snapshot(self, snapshot):
        try:
            require(self.initial is not None and not self.closed, "corner window is not open")
            require(self.reader_closed_frame is None, "corner observation continued after reader close")
            actor = self._actor(snapshot)
            require(snapshot["observationBoundary"] == "main-task-queue-completion"
                    and snapshot["frame"] == self.last["frame"]+1
                    and snapshot["nativeCycle"] > self.last["nativeCycle"], "corner completed frame gap")
            self.frames += 1
            require(self.frames <= self.max_frames, "corner frame bound exceeded")
            n = snapshot["nativeObservation"]
            require(n.get("installedBeforeBoot") is True and n.get("coverageComplete") is True
                    and n.get("error") is None and n.get("eventsDropped") == n.get("profilesEvicted") == 0,
                    "corner native coverage incomplete")
            for event in self.events:
                data = event["data"]
                require(event["frame"] == snapshot["frame"], "corner event completion frame differs")
                if event["kind"] == "native-observation":
                    require(data["sequence"] == self.sequence+1, "corner native sequence gap")
                    self.sequence += 1
                    require(self.last["nativeCycle"] <= data["entryNativeCycle"]
                            <= data["returnNativeCycle"] <= snapshot["nativeCycle"], "corner native callback clock differs")
                    if data.get("observation") == "walk-corner-strict":
                        require(data["completedFrame"] == self.last["frame"], "corner strict completed boundary differs")
                        self._strict(data)
                elif event["kind"] == "native":
                    stream, seq = data["traceStream"], data["sequence"]
                    require(seq == self.streams.get(stream, 0)+1, "corner semantic sequence gap")
                    self.streams[stream] = seq
                    if data["actorHandle"] == self.actor["handle"]["value"]:
                        require(data["actor"] == {k:v for k,v in self.actor["handle"].items() if k != "value"},
                                "corner semantic actor differs")
                        require(data["event"] not in ("MOTION_CANCELED", "CONTEXT_CHANGED", "ACTOR_REBOUND", "CONTROL_REBOUND"),
                                "corner canceled or rebound")
                        if data["event"] == "MOTION_STARTED":
                            require(self.recovery_frame is not None and actor["motionKind"] == "WALK"
                                    and actor["motionPhase"] != "IDLE", "corner start boundary differs")
                        if data["event"] in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
                            require(self.recovery_frame is not None
                                    and actor["commitSequence"] == self.actor["commitSequence"]+1
                                    and actor["logical"] == self.recovery_target,
                                    "corner terminal commit boundary differs")
                            if data["event"] in ("MOTION_FINISHED", "CONTROL_RETURNED"):
                                require(actor["motionPhase"] == "IDLE" and actor["reservationId"] == 0,
                                        "corner terminal control boundary differs")
                        require(len(self.traces) < 256, "corner semantic trace bound exceeded")
                        self.traces.append(deepcopy(event))
                elif event["kind"] == "trace-status":
                    require(data.get("code") == "ring-overwrite" and data.get("diagnosticOnly") is True
                            and data.get("unreadEventsLost") == 0 and data.get("count", 0) > 0
                            and data.get("traceStream") in self.streams, "corner trace coverage gap")
                else:
                    raise ValueError("corner unknown event; commands must use command()")
            self.events.clear()
            require(n["sequence"] == self.sequence, "corner missing native receipt")
            reader_closed = snapshot["walkCorner"].get("closed")
            require(type(reader_closed) is bool, "corner reader close state missing")
            self._reader(snapshot["walkCorner"], reader_closed)
            if reader_closed:
                self.reader_closed_frame = snapshot["frame"]
            selector = snapshot["selector"]
            require(selector["heldKeys"] == selector["rawHeld"] and selector["simulatedKeys"] == 0,
                    "corner input is not normal native input")
            self.inputs.append(dict(frame=snapshot["frame"], mask=selector["heldKeys"]))
            if self.recovery_frame is None:
                require(actor["logical"] == self.actor["logical"]
                        and actor["commitSequence"] == self.actor["commitSequence"]
                        and actor["motionPhase"] == "IDLE" and actor["motionKind"] == "NONE"
                        and actor["reservationId"] == 0, "blocked corner moved or committed")
                for current, initial in ((snapshot["player"], self.initial["player"]),
                                         (actor["engineObject"], self.actor["engineObject"])):
                    pose_keys = [k for k in initial if k.startswith(("pos_", "face_", "unk88_", "unk94_"))]
                    require(pose_keys and all(current.get(k) == initial[k] for k in pose_keys),
                            "blocked corner rendered pose changed")
            else:
                mask = selector["heldKeys"]
                if mask:
                    require(mask in CARDINALS, "corner recovery is not cardinal")
                    direction, dx, dy = CARDINALS[mask]
                    require(self.query["cardinals"][direction]["open"], "corner recovery cardinal is blocked")
                    target = dict(x=self.actor["logical"]["x"]+dx, y=self.actor["logical"]["y"]+dy)
                    require(self.recovery_target in (None, target), "corner recovery direction changed")
                    self.recovery_target = target
                require(actor["commitSequence"]-self.actor["commitSequence"] in (0, 1)
                        and actor["motionKind"] in ("NONE", "WALK"), "extra corner recovery commit or motion")
                if self.recovery_target:
                    require(actor["logical"] in (self.actor["logical"], self.recovery_target), "corner recovery left cardinal path")
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            if str(error) not in self.failures:
                self.failures.append(str(error))
        return self.result()

    def observe(self, snapshot, events):
        for event in events:
            self.feed_event(event)
        return self.feed_snapshot(snapshot)

    def begin_recovery(self, snapshot):
        require(snapshot == self.last and self.calls and self.recovery_frame is None and not self.failures,
                "corner recovery needs latest blocked snapshot")
        self.blocked = deepcopy(self._actor(snapshot))
        self.recovery_frame = snapshot["frame"]
        return self.result()

    def _events(self, name):
        return [e for e in self.traces if e["data"]["event"] == name]

    @property
    def current_stage(self):
        if self.recovery_frame is not None:
            return "recovery-started" if self._events("MOTION_STARTED") else "recovery"
        return "blocked" if self.calls else "armed"

    def stage(self, name):
        if name == "recovery-complete":
            if self.failures or self.recovery_target is None:
                return False
            final = self._actor(self.last)
            return (final["motionPhase"] == "IDLE" and final["motionKind"] == "NONE"
                    and final["reservationId"] == 0 and final["logical"] == self.recovery_target
                    and final["commitSequence"] == self.actor["commitSequence"]+1
                    and all(len(self._events(event)) == 1 for event in LIFECYCLE))
        return not self.failures and (self.current_stage == name or (name == "complete" and self.ready))

    def _episodes(self):
        episodes = []
        for command in self.commands:
            if episodes and episodes[-1]["mask"] == command["mask"]:
                episodes[-1]["endFrame"] = command["endFrame"]
            else:
                episodes.append({k:command[k] for k in ("startFrame", "endFrame", "mask")})
        return episodes

    def _complete(self):
        require(self.blocked is not None and self.recovery_target is not None, "corner recovery missing")
        rejected = self._events("CANDIDATE_REJECTED")
        require(len(rejected) == 1 and rejected[0]["data"]["reason"] == "REJECTED_SIDE_TILE"
                and self.initial["frame"] < rejected[0]["frame"] <= self.recovery_frame,
                "missing exact CANDIDATE_REJECTED REJECTED_SIDE_TILE")
        ordered = [rejected[0]]
        for name in LIFECYCLE:
            rows = self._events(name)
            require(len(rows) == 1 and rows[0]["data"]["reason"] == "OK"
                    and rows[0]["frame"] > self.recovery_frame, "corner exact lifecycle missing: " + name)
            value = rows[0]["data"]
            require(name == "CONTROL_RETURNED" or value["valueA" if name == "MOTION_STARTED" else "valueB"] == 1,
                    "corner lifecycle Walk value differs")
            ordered.append(rows[0])
        seqs = [r["data"]["sequence"] for r in ordered]
        require(seqs == sorted(set(seqs)), "corner lifecycle order differs")
        final = self._actor(self.last)
        direction = self.calls[0]["direction"]
        clear_sides = [d for d in DIAGONALS[direction][3:] if self.query["cardinals"][d]["open"]]
        recovery_delta = (self.recovery_target["x"]-self.actor["logical"]["x"],
                          self.recovery_target["y"]-self.actor["logical"]["y"])
        require(any((dx, dy) == recovery_delta and d in clear_sides for d,dx,dy in CARDINALS.values()),
                "corner recovery is not the tested diagonal clear side")
        require(final["motionPhase"] == "IDLE" and final["motionKind"] == "NONE" and final["reservationId"] == 0
                and final["logical"] == self.recovery_target
                and final["commitSequence"] == self.actor["commitSequence"]+1, "corner recovery terminal differs")
        require(self.commands and self.commands[0]["startFrame"] == self.initial["frame"]
                and self.commands[-1]["endFrame"] == self.last["frame"], "corner normal command window missing")
        for observed in self.inputs:
            matches = [c for c in self.commands if c["startFrame"] < observed["frame"] <= c["endFrame"]]
            require(len(matches) == 1 and matches[0]["mask"] == observed["mask"], "corner command/native input differs")
        positive = [c for c in self._episodes() if c["mask"]]
        require(len(positive) == 2 and positive[0]["mask"] == DIAGONALS[self.calls[0]["direction"]][0]
                and positive[0]["endFrame"] <= self.recovery_frame
                and positive[1]["startFrame"] >= self.recovery_frame and positive[1]["mask"] in CARDINALS
                and positive[1]["endFrame"] == positive[1]["startFrame"]+1
                and self.commands[-1]["mask"] == 0, "corner needs diagonal request, one cardinal tap, and release")

    @property
    def ready(self):
        if self.failures or self.initial is None:
            return False
        try:
            self._complete()
            return True
        except (ValueError, KeyError, TypeError):
            return False

    def close(self, receipt, snapshot):
        require(snapshot == self.last, "corner close snapshot differs")
        self._reader(receipt, True)
        self.cleanup = deepcopy(receipt)
        self.closed = True
        return self.finish()

    def finish(self):
        # Keep independent gaps together. Historical diagnostic recovery can
        # be an open cardinal without being the diagonal's clear side.
        if self.calls and self.recovery_target is not None:
            _, dx, dy, vertical, horizontal = DIAGONALS[self.calls[0]["direction"]]
            targets = [dict(x=self.actor["logical"]["x"]+dx, y=self.actor["logical"]["y"]),
                       dict(x=self.actor["logical"]["x"], y=self.actor["logical"]["y"]+dy)]
            if self.recovery_target not in targets:
                message = "corner recovery is not the tested diagonal clear side"
                if message not in self.failures:
                    self.failures.append(message)
        try:
            self._complete()
            require(self.closed, "corner reader was not closed")
        except (ValueError, KeyError, TypeError) as error:
            if str(error) not in self.failures:
                self.failures.append(str(error))
        return self.result()

    def result(self):
        evidence = {}
        def row(claim, name, actual, expected):
            evidence.setdefault(claim, []).append(dict(name=name, actual=actual, expected=expected, operator="eq"))
        if self.actor is not None:
            initial_tile = [self.actor["logical"][k] for k in ("x", "y")]
            blocked_tile = [self.blocked["logical"][k] for k in ("x", "y")] if self.blocked else None
            blocked_seq = self.blocked["commitSequence"] if self.blocked else None
            row("natural-input", "natural-input-motion-count", sum(bool(c["mask"]) for c in self._episodes()), 2)
            row("live-actor-identity", "diagonal-corner-cyndaquil-identity",
                [int(self.actor["identityVerified"]), self.actor["role"], self.actor["species"], int(self.actor["presentationAttached"])],
                [1, "MOUNTED", 155, 1])
            row("collision-decision", "blocked-commit-sequence", [self.actor["commitSequence"], blocked_seq],
                [self.actor["commitSequence"]]*2)
            row("collision-decision", "blocked-final-tile", [initial_tile, blocked_tile], [initial_tile, initial_tile])
            row("logical-commit", "cardinal-logical-commit-count", len(self._events("LOGICAL_COMMIT")), 1)
            row("engine-boundary", "cardinal-lifecycle-counts",
                [len(self._events(n)) for n in ("MOTION_STARTED", "MOTION_FINISHED", "MOTION_CANCELED", "CONTROL_RETURNED")], [1, 1, 0, 1])
            final = next((a for a in self.last["actors"] if a["handle"] == self.actor["handle"]), {})
            terminal = int(final.get("motionPhase") == "IDLE" and final.get("motionKind") == "NONE"
                           and final.get("reservationId") == 0 and final.get("logical") == self.recovery_target
                           and len(self._events("CONTROL_RETURNED")) == 1)
            row("control-release", "cardinal-terminal-result", terminal, 1)
        return dict(passed=self.closed and self.ready, acceptedProof=False, ready=self.ready,
                    stage=self.current_stage, closed=self.closed, frames=self.frames, failures=list(self.failures),
                    proofEvidence=evidence, subject=deepcopy(self.subject), query=deepcopy(self.query),
                    initial=deepcopy(self.initial), terminal=deepcopy(self.last), blocked=deepcopy(self.blocked),
                    strictCalls=deepcopy(self.calls), traces=deepcopy(self.traces), commands=deepcopy(self.commands),
                    inputs=deepcopy(self.inputs), cleanup=deepcopy(self.cleanup),
                    recoveryFrame=self.recovery_frame, recoveryTarget=deepcopy(self.recovery_target))

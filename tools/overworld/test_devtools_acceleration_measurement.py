"""Synthetic shared memory data; these host tests do not claim game proof."""
from copy import deepcopy
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from tools.overworld.devtools_acceleration_measurement import AccelerationMeasurement, POLICY_FIELDS
from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE, Stream


def fixture(role="WILD", durations=(9, 9, 5, 5, 3, 3, 2), *, initial_commit=0, base=9, fastest=2,
            acceleration=33,
            counters=(1, 0, 1, 0, 1, 0, 0), speeds=(9, 5, 5, 3, 3, 2, 2),
            tiles=2, direction=3, delta=(1, 0), species=165, direction_mode=0, fingerprint=None,
            lane_state=0, first_elapsed=0):
    stream = Stream(initial_commit=initial_commit)
    stream.items = []
    actor = stream.actor
    fingerprint = fingerprint or (12345 if fastest == 2 else 12345 + fastest)
    actor["behaviorFingerprint"] = fingerprint
    actor["role"] = role
    actor["species"] = actor["sourceIdentity"]["species"] = species
    actor["inputOwnership"] = int(role == "MOUNTED")
    if role == "MOUNTED":
        actor["handle"].update(slot=7, value=65543)
        actor["engineIdentity"].update(anchorPointer=0x02050000, anchorInCurrentManager=True)
    staged = dict(known=True, idle=True, slot=actor["handle"]["slot"],
                  objectPointer=actor["engineIdentity"]["pointer"])
    actor["stagedMovement"] = deepcopy(staged)
    lane = bytearray(72)
    for key, value in {"chillSpeed": base, "maxWalkSpeed": fastest, "tilesToAccelerate": tiles,
                       "walkAccelerationStep": acceleration,
                       "hopAllowNonCardinal": direction_mode}.items():
        lane[next(f["offset"] for f in SCHEMA["fields"] if f["key"] == key)] = value
    lanes = [bytearray(lane) for _ in range(3)]
    for index, item in enumerate(lanes):
        item[0] = index
    stream.lanes = [item.hex() for item in lanes]
    lane = lanes[{2: 1, 3: 2}.get(lane_state, 0)]
    profile = bytearray.fromhex(stream.profile["resultHex"])
    profile[:216] = b"".join(lanes)
    profile[252:256] = fingerprint.to_bytes(4, "little")
    stream.profile.update(resultHex=profile.hex(), lanes=stream.lanes, fingerprint=fingerprint)
    request_profile = bytearray.fromhex(stream.profile["requestHex"])
    request_profile[:2] = species.to_bytes(2, "little")
    stream.profile["requestHex"] = request_profile.hex()
    player = deepcopy(actor["engineObject"])
    def append(events=()):
        stream.append(events)
        snapshot = stream.items[-1][0]
        snapshot["prepared"] = True
        snapshot["player"] = deepcopy(player if role == "MOUNTED" else actor["engineObject"])
        for event in stream.items[-1][1]:
            if event["kind"] == "native-observation":
                event["data"]["setupMode"] = "prepared"
        return snapshot
    baseline = append()
    policy = bytearray(32)
    policy[8:12] = fingerprint.to_bytes(4, "little")
    policy[12:16] = (3).to_bytes(4, "little")
    policy[:8] = bytes((255, 0, 0, 0, 255, 0, 0, 0))
    policy[20] = 255
    inputs = {k: 0 for k in ("state", "heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys", "physicalPressed")}
    endpoint = dict(snapshot=deepcopy(baseline), subject=deepcopy(actor), actor=deepcopy(actor),
                    policyHex=policy.hex(), inputs=inputs, stagedMovement=deepcopy(staged))
    request = b"\x01\x00\x1c\x00" + bytes(4) + bytes((actor["handle"]["slot"], 0)) + bytes(18)
    reset = dict(completed=True, prepared=True, acceptedProof=False, scope="prepared-idle-walk-policy-reset",
                 scratchRestored=True, returnValue=1, subject=deepcopy(actor), before=deepcopy(endpoint),
                 after=deepcopy(endpoint), requestHex=request.hex(), responseHex=request.hex())
    # Independent expected nine->five->three->two values, not the reducer formula.
    for index, duration in enumerate(durations):
        origin = [actor["logical"][k] for k in ("x", "y")]
        target = [origin[i] + delta[i] for i in (0, 1)]
        before_commit = actor["commitSequence"]
        actor.update(motionKind="WALK", motionPhase="MOVING", motionDuration=duration,
                     origin=dict(zip(("x", "y"), origin)), target=dict(zip(("x", "y"), target)), reservationId=1)
        anchor = player if role == "MOUNTED" else actor["engineObject"]
        for elapsed in range(first_elapsed, duration):
            actor["motionElapsed"] = elapsed
            pose = [(origin[i] << 16) + 0x8000 + (1 if delta[i] >= 0 else -1)
                    * (abs(delta[i]) * 0x10000 * elapsed // duration) for i in (0, 1)]
            anchor.update(pos_x=pose[0], pos_z=pose[1])
            append([stream.trace("MOTION_STARTED", 1, duration)] if elapsed == first_elapsed else [])
        raw_before = bytearray(policy)
        raw_before[0:8] = bytes((direction, 0 if index == 0 else counters[index - 1], duration, base, lane_state, 0, index, 0))
        raw_before[22] = 2
        raw_after = bytearray(raw_before)
        raw_after[1], raw_after[2], raw_after[6], raw_after[22] = counters[index], speeds[index], index + 1, 0
        request = bytearray(28)
        request[:4] = b"\x01\x00\x1c\x00"
        request[8:15] = bytes((actor["handle"]["slot"], 3, direction, 1, 1, lane_state, 4))
        response = bytearray(request); response[16] = 1
        public = stream.public()
        public["slot"] = actor["handle"]["slot"]
        event = stream.native("walk-policy", slot=actor["handle"]["slot"], operation=3,
            publicSubject=deepcopy(public), publicSubjectAfter=deepcopy(public), requestHex=request.hex(),
            responseHex=response.hex(), laneHex=lane.hex(), policyBeforeHex=raw_before.hex(), policyAfterHex=raw_after.hex(),
            policyBefore={k: raw_before[i] for k, i in POLICY_FIELDS.items()},
            policyAfter={k: raw_after[i] for k, i in POLICY_FIELDS.items()})
        actor.update(motionElapsed=duration, commitSequence=(before_commit + 1) & 0xFFFFFFFF,
                     logical=deepcopy(actor["target"]), motionPhase="IDLE", motionKind="NONE", reservationId=0)
        anchor.update(pos_x=(target[0] << 16) + 0x8000, pos_z=(target[1] << 16) + 0x8000, x=target[0], y=target[1])
        append([event, stream.trace("LOGICAL_COMMIT", actor["commitSequence"], 1),
                stream.trace("MOTION_FINISHED", actor["commitSequence"], 1),
                stream.trace("CONTROL_RETURNED", int(role == "MOUNTED"), actor["commitSequence"])])
    return baseline, reset, stream.items[1:]


def replay(meter, role, data):
    baseline, reset, rows = data
    meter.bind(role, reset["subject"], baseline, reset)
    for snapshot, events in rows:
        meter.observe(snapshot, events)
        if meter.failures:
            break
    return meter


class AccelerationMeasurementTests(unittest.TestCase):
    def test_final_idle_reset_requires_all_seven_terminal_lifecycles(self):
        for fault in (None, "mid-series", "missing-finish", "missing-control", "wrong-commit", "moving",
                      "identity", "pose", "raw-response", "failed-reset", "early-reset", "short-travel"):
            with self.subTest(fault=fault):
                data = fixture("MOUNTED")
                rows = data[2]
                index = -1 if fault != "mid-series" else next(
                    i for i, (_, events) in enumerate(rows) if any(
                        e.get("data", {}).get("operation") == 3 for e in events))
                snapshot, events = rows[index]
                commit = next(e for e in events if e.get("data", {}).get("operation") == 3)
                for event in events:
                    if event["kind"] == "native":
                        event["data"]["actorFrame"] = commit["data"]["entryActorFrame"]
                reset = deepcopy(commit)
                raw = bytearray(28)
                raw[:4] = b"\x01\x00\x1c\x00"
                raw[8] = 7
                public = deepcopy(commit["data"]["publicSubject"])
                public.update(motionKind="NONE", motionPhase="IDLE",
                              commitSequence=snapshot["actors"][0]["commitSequence"])
                reset["data"].update(operation=0, sequence=commit["data"]["sequence"] + 1,
                    publicSubject=deepcopy(public), publicSubjectAfter=deepcopy(public),
                    requestHex=raw.hex(), responseHex=raw.hex())
                events.append(reset)
                snapshot["nativeObservation"]["sequence"] += 1
                if fault == "missing-finish":
                    next(e for e in events if e.get("data", {}).get("event") == "MOTION_FINISHED")["data"]["event"] = "WORLD_EFFECT"
                elif fault == "wrong-commit":
                    reset["data"]["publicSubject"]["commitSequence"] -= 1
                elif fault == "missing-control":
                    next(e for e in events if e.get("data", {}).get("event") == "CONTROL_RETURNED")["data"]["event"] = "WORLD_EFFECT"
                elif fault == "moving":
                    reset["data"]["publicSubject"]["motionPhase"] = "SETTLING"
                elif fault == "identity":
                    reset["data"]["publicSubjectAfter"]["subjectIdentity"] += 1
                elif fault == "pose":
                    snapshot["player"]["pos_x"] += 1
                elif fault == "raw-response":
                    raw[10] = 1
                    reset["data"]["responseHex"] = raw.hex()
                elif fault == "early-reset":
                    reset["data"]["entryActorFrame"] -= 1
                elif fault == "failed-reset":
                    reset["data"]["returnValue"] = 0
                elif fault == "short-travel":
                    rows[-2][0]["actors"][0]["motionElapsed"] = 0
                meter = replay(self.meter(), "MOUNTED", data)
                if fault is None:
                    self.assertEqual(meter.failures, [])
                    self.assertEqual(len(meter.roles["MOUNTED"]["motions"]), 7)
                    self.assertEqual(meter.result()["roles"]["MOUNTED"]["terminalResets"], [reset])
                else:
                    self.assertTrue(meter.failures)

    def test_completed_profile_receipts_bind_unmodified_raw_reset(self):
        for fault in (None, "missing", "source", "mask", "oversize"):
            meter = self.meter()
            baseline, reset, _ = fixture()
            profiles = deepcopy(baseline["nativeObservation"]["resolvedProfiles"])
            baseline["nativeObservation"]["resolvedProfiles"] = []
            for side in ("before", "after"):
                reset[side]["snapshot"]["nativeObservation"]["resolvedProfiles"] = []
            original = deepcopy(reset)
            if fault == "missing": profiles = []
            elif fault == "source": profiles[0]["sourceSha256"] = "wrong"
            elif fault == "mask":
                data = bytearray.fromhex(profiles[0]["resultHex"])
                data[248:252] = (9).to_bytes(4, "little")
                profiles[0].update(resultHex=data.hex(), appliedOverrides=9)
            elif fault == "oversize": profiles *= 65
            with self.subTest(fault=fault):
                if fault:
                    with self.assertRaises(ValueError):
                        meter.bind("WILD", reset["subject"], baseline, reset, resolved_profiles=profiles)
                else:
                    meter.bind("WILD", reset["subject"], baseline, reset, resolved_profiles=profiles)
                self.assertEqual(reset, original)

    def test_reset_seeds_first_completed_boundary_without_motion_credit(self):
        for role in ("WILD", "MOUNTED"):
            for advance in (0, 1):
                for fault in (None, "skip", "pose", "event", "clock", "not-completed"):
                    meter = self.meter()
                    baseline, reset, _ = fixture(role)
                    meter.bind(role, reset["subject"], baseline, reset)
                    endpoint = deepcopy(baseline)
                    endpoint.update(fieldAvailable=True, observationBoundary="main-task-queue-completion")
                    endpoint["frame"] += advance
                    endpoint["actorFrame"] += advance
                    endpoint["nativeCycle"] += advance
                    events = []
                    if fault == "skip": endpoint["frame"] += 2
                    elif fault == "pose": endpoint["player"]["pos_x"] += 1
                    elif fault == "clock": endpoint["actorFrame"] += 2
                    elif fault == "not-completed": endpoint["fieldAvailable"] = False
                    elif fault == "event":
                        events = [dict(kind="native", frame=endpoint["frame"],
                            data=dict(actorHandle=reset["subject"]["handle"]["value"], event="MOTION_STARTED"))]
                    with self.subTest(role=role, advance=advance, fault=fault):
                        if fault:
                            with self.assertRaises(ValueError):
                                meter.seed_window_boundary(endpoint, events, {})
                        else:
                            meter.seed_window_boundary(endpoint, events, {})
                            self.assertEqual(meter.roles[role]["frame"], endpoint["frame"])
                            self.assertEqual(meter.roles[role]["actorFrame"], endpoint["actorFrame"])
                            self.assertEqual(meter.roles[role]["motions"], [])

    def meter(self):
        return AccelerationMeasurement(SCHEMA, SOURCE, max_frames=2000)

    def test_elapsed_one_has_real_start_and_complete_dense_travel(self):
        meter = self.meter()
        for role in ("WILD", "MOUNTED"):
            data = fixture(role, first_elapsed=1)
            replay(meter, role, data)
            self.assertEqual(meter.failures, [])
            motions = meter.result()["roles"][role]["motions"]
            self.assertEqual(len(motions), 7)
            self.assertEqual(motions[0]["startFrame"], data[2][0][0]["frame"])
            self.assertEqual([s["elapsed"] for s in motions[0]["samples"]], list(range(1, 9)))
        self.assertTrue(meter.finish()["passed"])

    def test_consumed_ring_reuse_preserves_trace_coverage(self):
        data = fixture()
        snapshot, events = data[2][1]
        # Sequence one was retained in the preceding completed frame.
        notice = dict(frame=snapshot["frame"], kind="trace-status", data=dict(
            code="ring-overwrite", traceStream=1, diagnosticOnly=True, count=1, unreadEventsLost=0))
        events.append(notice)
        self.assertEqual(replay(self.meter(), "WILD", data).failures, [])

    def test_ring_reuse_cannot_hide_loss_or_invalid_notice(self):
        for key, value in (("unreadEventsLost", 1), ("unreadEventsLost", None),
                           ("unreadEventsLost", False), ("unreadEventsLost", "0"),
                           ("coverageComplete", False), ("coverageComplete", 1),
                           ("diagnosticOnly", False), ("diagnosticOnly", None),
                           ("traceStream", 2), ("traceStream", True),
                           ("count", 0), ("count", True), ("code", "unread-events-lost")):
            with self.subTest(key=key, value=value):
                data = fixture()
                snapshot, events = data[2][1]
                notice = dict(code="ring-overwrite", traceStream=1, diagnosticOnly=True,
                              count=1, unreadEventsLost=0)
                notice[key] = value
                events.append(dict(frame=snapshot["frame"], kind="trace-status", data=notice))
                self.assertTrue(replay(self.meter(), "WILD", data).failures)
        data = fixture()
        snapshot, events = data[2][1]
        events.append(dict(frame=snapshot["frame"], kind="trace-status", data=dict(
            code="ring-overwrite", traceStream=1, diagnosticOnly=True, count=1, unreadEventsLost=0)))
        # A no-loss notice does not excuse an omitted lifecycle event.
        data[2][0][1].clear()
        self.assertTrue(replay(self.meter(), "WILD", data).failures)

    def test_elapsed_one_rejects_unproven_start_or_missing_travel(self):
        for change in ("event", "event-frame", "reason", "duration", "elapsed-two", "elapsed-bool",
                       "previous-pose", "previous-logical", "commit", "gap"):
            with self.subTest(change=change):
                data = fixture("MOUNTED", first_elapsed=1)
                baseline, reset, rows = data
                snapshot, events = rows[0]
                if change == "event": events.clear()
                elif change == "event-frame": events[0]["frame"] -= 1
                elif change == "reason": events[0]["data"]["reason"] = "BLOCKED"
                elif change == "duration": events[0]["data"]["valueB"] += 1
                elif change == "elapsed-two": snapshot["actors"][0]["motionElapsed"] = 2
                elif change == "elapsed-bool": snapshot["actors"][0]["motionElapsed"] = True
                elif change in ("previous-pose", "previous-logical"):
                    if change == "previous-pose": baseline["player"]["pos_x"] += 1
                    else: baseline["actors"][0]["logical"]["x"] += 1
                    for endpoint in (reset["before"], reset["after"]):
                        endpoint["snapshot"] = deepcopy(baseline)
                        endpoint["actor"] = deepcopy(baseline["actors"][0])
                elif change == "commit": snapshot["actors"][0]["commitSequence"] += 1
                else: del rows[2]
                self.assertTrue(replay(self.meter(), "MOUNTED", data).failures)

    def test_seven_per_role_exact_ceil_half_and_mounted_player_anchor(self):
        meter = self.meter()
        replay(meter, "WILD", fixture(initial_commit=0xFFFFFFFC))
        self.assertEqual(meter.failures, [])
        replay(meter, "MOUNTED", fixture("MOUNTED"))
        self.assertEqual(meter.failures, [])
        result = meter.finish()
        self.assertTrue(result["passed"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(len(result["measurements"]), 4)
        self.assertEqual(result["measurements"][1]["value"]["durations"], [[9, 9, 5, 5, 3, 3, 2]] * 2)
        self.assertEqual(result["measurements"][2]["value"]["series"][0],
                         [0xFFFFFFFD, 0xFFFFFFFE, 0xFFFFFFFF, 0, 1, 2, 3])
        # The mounted Pokemon display stays still; the actual player moves.
        self.assertEqual(fixture("MOUNTED")[2][-1][0]["actors"][0]["engineObject"]["x"], 0)

    def test_fixed_acceleration_amount_removes_authored_frames(self):
        settings = dict(
            durations=(9, 9, 6, 6, 3, 3, 2),
            speeds=(9, 6, 6, 3, 3, 2, 2),
            counters=(1, 0, 1, 0, 1, 0, 0),
            acceleration=3,
        )
        meter = replay(self.meter(), "WILD", fixture(**settings))
        self.assertEqual(meter.failures, [])
        proof = meter.result()["roles"]["WILD"]
        self.assertEqual(
            [bytes.fromhex(event["data"]["policyAfterHex"])[2] for event in proof["policies"]],
            list(settings["speeds"]),
        )

    def test_authored_eight_three_two_wild_diagonal_mounted_cardinal(self):
        # Execute the real public direction helpers. The fixture and meter must
        # agree with production, not just with the same copied direction table.
        source = '''#include <stdio.h>
#include <stdint.h>
/* Only host primitive typedefs replace target platform declarations. */
#define TYPES_H
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#include "overworld_walk_direction_policy.h"
int main(void) {
    unsigned directions[] = {OVERWORLD_WALK_DIRECTION_NORTH_WEST, OVERWORLD_WALK_DIRECTION_EAST};
    for (unsigned i = 0; i < 2; ++i)
        printf("%u %d %d\\n", directions[i],
            OverworldWalkDirectionPolicy_DeltaX(directions[i]),
            OverworldWalkDirectionPolicy_DeltaY(directions[i]));
    return 0;
}
'''
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix="acceleration-direction-") as temporary:
            binary = str(Path(temporary) / "directions")
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                       "-I", str(root / "include"), "-x", "c", "-", "-o", binary]
            compiled = subprocess.run(command, input=source, text=True, capture_output=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            observed = subprocess.run([binary], text=True, capture_output=True, check=True)
        directions = [tuple(map(int, row.split())) for row in observed.stdout.splitlines()]
        self.assertEqual(len(directions), 2)
        self.assertTrue(all(axis != 0 for axis in directions[0][1:]))
        self.assertEqual(sum(axis != 0 for axis in directions[1][1:]), 1)
        expected = (8, 8, 8, 4, 4, 4, 2)
        settings = dict(durations=expected, base=8, fastest=2, tiles=3,
                        counters=(1, 2, 0, 1, 2, 0, 0), speeds=(8, 8, 4, 4, 4, 2, 2))
        meter = self.meter()
        for role, species, mode, (direction, dx, dy) in zip(("WILD", "MOUNTED"), (165, 155), (2, 0), directions):
            # Separate resolved values for distinct species/role lanes.
            data = fixture(role, species=species, direction_mode=mode,
                           direction=direction, delta=(dx, dy), lane_state=2 if role == "WILD" else 0,
                           fingerprint=12345 + int(role == "MOUNTED"), **settings)
            replay(meter, role, data)
            self.assertEqual(meter.failures, [])
            proof = meter.result()["roles"][role]
            self.assertEqual([bytes.fromhex(e["data"]["policyBeforeHex"])[2] for e in proof["policies"]], list(expected))
            self.assertEqual([m["duration"] for m in proof["motions"]], list(expected))
            self.assertEqual([m["target"][i] - m["origin"][i] for m in proof["motions"] for i in (0, 1)],
                             [dx, dy] * 7)
            for meaning in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
                self.assertEqual(sum(e["data"]["event"] == meaning for e in proof["traces"]), 7)
        self.assertTrue(meter.ready)

    def test_exact_role_lane_raw_binding_and_actor_clocks(self):
        for role in ("WILD", "MOUNTED"):
            for change in ("lane", "binding", "mask", "missing-entry", "missing-return", "future-return", "old-entry"):
                with self.subTest(role=role, change=change):
                    data = fixture(role)
                    event = next(e for _, events in data[2] for e in events if e["kind"] == "native-observation")
                    receipt = event["data"]
                    if change == "lane":
                        receipt["laneHex"] = data[0]["nativeObservation"]["resolvedProfiles"][0]["lanes"][1]
                    elif change in ("binding", "mask"):
                        for key in ("policyBeforeHex", "policyAfterHex"):
                            raw = bytearray.fromhex(receipt[key]); raw[8 if change == "binding" else 12] ^= 1
                            receipt[key] = raw.hex()
                    elif change == "missing-entry": del receipt["entryActorFrame"]
                    elif change == "missing-return": del receipt["returnActorFrame"]
                    elif change == "future-return": receipt["returnActorFrame"] += 1000
                    else: receipt["entryActorFrame"] = 0
                    self.assertTrue(replay(self.meter(), role, data).failures)
        for lane_state in (1, 2, 3):
            with self.subTest(wild_lane_state=lane_state):
                self.assertEqual(replay(self.meter(), "WILD", fixture(lane_state=lane_state)).failures, [])

    def test_policy_mutations_fail(self):
        for field in ("speed", "counter", "base", "direction", "skid", "resume", "pending"):
            with self.subTest(field=field):
                data = fixture()
                event = next(e for _, events in data[2] for e in events if e["kind"] == "native-observation")
                value = event["data"]
                raw = bytearray.fromhex(value["policyAfterHex"])
                raw[POLICY_FIELDS[field]] ^= 1
                value["policyAfterHex"] = raw.hex()
                value["policyAfter"][field] = raw[POLICY_FIELDS[field]]
                meter = replay(self.meter(), "WILD", data)
                self.assertTrue(meter.failures)

    def test_fastest_clamp_and_unequal_valid_roles_not_parity(self):
        clamped = dict(durations=(9, 9, 5, 5, 4, 4, 4), fastest=4,
                       counters=(1, 0, 1, 0, 0, 0, 0), speeds=(9, 5, 5, 4, 4, 4, 4))
        meter = replay(self.meter(), "WILD", fixture(**clamped))
        replay(meter, "MOUNTED", fixture("MOUNTED", **clamped))
        self.assertEqual(meter.failures, [])
        self.assertTrue(meter.ready)
        different = replay(self.meter(), "WILD", fixture())
        replay(different, "MOUNTED", fixture("MOUNTED", **clamped))
        self.assertEqual(different.failures, [])
        self.assertFalse(different.finish()["passed"])

    def test_sequence_clocks_and_raw_bytes_cannot_disagree(self):
        for key in ("sequence", "clock", "bytes", "generation"):
            data = fixture()
            event = next(e for _, events in data[2] for e in events if e["kind"] == "native-observation")
            receipt = event["data"]
            if key == "sequence": receipt["sequence"] += 1
            elif key == "clock": receipt["returnNativeCycle"] += 10000
            elif key == "bytes": receipt["policyAfter"]["speed"] += 1
            else: receipt["publicSubjectAfter"]["handle"]["generation"] += 1
            with self.subTest(key=key):
                self.assertTrue(replay(self.meter(), "WILD", data).failures)

    def test_missing_duplicate_and_wrong_native_terminal(self):
        for meaning in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            for mutation in ("rename", "duplicate", "value"):
                with self.subTest(meaning=meaning, mutation=mutation):
                    data = fixture()
                    for _, events in data[2]:
                        found = next((e for e in events if e["kind"] == "native" and e["data"]["event"] == meaning), None)
                        if found:
                            if mutation == "rename": found["data"]["event"] = "WORLD_EFFECT"
                            elif mutation == "duplicate": events.append(deepcopy(found))
                            else: found["data"]["valueA"] += 1
                            break
                    self.assertTrue(replay(self.meter(), "WILD", data).failures)

    def test_wrong_identity_frame_profile_and_mounted_anchor_fail(self):
        for key in ("identity", "context", "gap", "profile", "anchor", "pose"):
            with self.subTest(key=key):
                data = fixture("MOUNTED")
                snapshot = data[2][2][0]
                if key == "identity": snapshot["actors"][0]["authorityGeneration"] += 1
                elif key == "context": snapshot["context"]["mapGeneration"] += 1
                elif key == "gap": snapshot["frame"] += 1
                elif key == "profile": snapshot["actors"][0]["behaviorFingerprint"] += 1
                elif key == "anchor": snapshot["actors"][0]["engineIdentity"]["anchorInCurrentManager"] = False
                else: snapshot["player"]["pos_x"] = data[2][1][0]["player"]["pos_x"]
                self.assertTrue(replay(self.meter(), "MOUNTED", data).failures)

    def test_missing_or_changed_reset_and_short_series_fail(self):
        data = fixture()
        for key in ("scratchRestored", "policyHex", "subject"):
            bad = deepcopy(data[1])
            if key == "scratchRestored": bad[key] = False
            elif key == "policyHex": bad["after"][key] = bytes(32).hex()
            else: bad[key]["subjectIdentity"] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.meter().bind("WILD", data[1]["subject"], data[0], bad)
        meter = replay(self.meter(), "WILD", (data[0], data[1], data[2][:-1]))
        self.assertFalse(meter.finish()["passed"])


if __name__ == "__main__":
    unittest.main()

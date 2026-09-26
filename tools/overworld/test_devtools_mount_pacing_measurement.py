"""Host-only reducer controls. These fixtures do not grant live proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_mount_pacing_measurement import MountedPacingMeasurement, check_pair_pose
from tools.overworld.devtools_mount_pacing_observer import ENGINE
from tools.overworld.devtools_mount_speed_slew_measurement import EasedMountedMotionRecorder, walk_step_fx32
from tools.overworld.test_devtools_acceleration_measurement import fixture


def pacing_fixture(durations=(16, 16, 16, 15, 15, 15, 14, 16), *, species=155,
                   initial_commit=0):
    baseline, reset, rows = fixture(role="MOUNTED", species=species, durations=durations,
                                    counters=(0,)*len(durations), speeds=durations,
                                    initial_commit=initial_commit)
    subject = reset["subject"]
    meter_receipt = dict(armed=True, closed=False, failure=None, acceptedProof=False,
        guestMemoryWrites=0, subject=deepcopy(subject), startFrame=baseline["frame"],
        counts={"presentation":0,"playerStep":0})
    seq = baseline["nativeObservation"]["sequence"]
    counts = dict(presentation=0,playerStep=0)
    for snapshot, events in rows:
        actor = snapshot["actors"][0]
        if actor["motionKind"] == "WALK" and actor["motionPhase"] == "MOVING":
            index = actor["commitSequence"] - initial_commit
            # Recovery is a separate input window. Its Walk starts fresh
            # after control release, not from the held run's final speed.
            prior = durations[index-1] if 0 < index < 7 else 0
            snapshot["player"]["pos_x"] = (actor["origin"]["x"] << 16) + 32768 \
                + walk_step_fx32(actor["motionElapsed"], actor["motionDuration"], prior)
        player = deepcopy(snapshot["player"])
        for prefix in ("face_", "unk88_", "unk94_"):
            for axis in "xyz":
                player[prefix+axis] = 0
        mount = deepcopy(player)
        player["face_y"] = 32768
        player["facing"] = mount["facing"] = 3
        player["face_x"] = -32768
        data = dict(subject=deepcopy(subject), publicSubject=deepcopy(actor), sourceIdentity=deepcopy(actor["sourceIdentity"]),
            engineIdentity={k:actor["engineIdentity"].get(k) for k in ENGINE},
            playerPointer=actor["engineIdentity"]["anchorPointer"], mountPointer=actor["engineIdentity"]["pointer"],
            player=player, mount=mount, avatarControl=dict(flags=2,moveState=0,playerMoveState=0),
            kind="presentation", observation="mount-pacing-presentation", setupMode="prepared",
            returnActorFrame=snapshot["actorFrame"], entryActorFrame=snapshot["actorFrame"],
            entryNativeCycle=snapshot["nativeCycle"], returnNativeCycle=snapshot["nativeCycle"])
        events[:] = [e for e in events if e["kind"] != "native-observation"]
        for e in events:
            if e["kind"] == "native": e["data"]["actorFrame"] = snapshot["actorFrame"]
        seq += 1
        data["sequence"] = seq
        events.append(dict(frame=snapshot["frame"],kind="native-observation",data=deepcopy(data)))
        counts["presentation"] += 1
        if actor["motionPhase"] == "IDLE":
            seq += 1
            step = dict(data, kind="playerStep", observation="mount-pacing-player-step",sequence=seq,eventConsumed=0)
            events.append(dict(frame=snapshot["frame"],kind="native-observation",data=step))
            counts["playerStep"] += 1
        snapshot["nativeObservation"]["sequence"] = seq
        pose = dict(data, boundary="main-task-queue-completion", frame=snapshot["frame"],nativeCycle=snapshot["nativeCycle"])
        snapshot["mountPacing"] = dict(meter_receipt, latestCompletedPose=pose, counts=deepcopy(counts))
    return baseline, subject, meter_receipt, rows


class MountedPacingTests(unittest.TestCase):
    def test_eased_successor_has_exact_first_pose(self):
        recorder = EasedMountedMotionRecorder()
        actor = dict(origin=dict(x=9, y=4), target=dict(x=10, y=4), motionDuration=15)
        pose = recorder._successor_pose(actor, dict(duration=16))
        self.assertEqual(pose, [(9 << 16) + 32768 + walk_step_fx32(1, 15, 16),
                                (4 << 16) + 32768])
        self.assertNotEqual(pose[0], (9 << 16) + 32768 + 65536 // 15)

    def test_pair_offset_follows_native_facing(self):
        _, _, _, rows = pacing_fixture()
        pose = deepcopy(rows[0][0]["mountPacing"]["latestCompletedPose"])
        for facing, x, z in ((0,0,32768),(1,0,-40960),(2,32768,0),(3,-32768,0),
                             (4,32768,32768),(5,-32768,32768),
                             (6,32768,-32768),(7,-32768,-32768)):
            pose["player"]["facing"] = pose["mount"]["facing"] = facing
            pose["player"]["face_x"], pose["player"]["face_z"] = x,z
            with self.subTest(facing=facing): self.assertTrue(check_pair_pose(pose))
        pose["player"]["face_x"], pose["player"]["face_z"] = 0,32768
        with self.assertRaisesRegex(ValueError,"rider offset differs"): check_pair_pose(pose)

    def replay(self, mutate=None, durations=(16, 16, 16, 15, 15, 15, 14, 16)):
        baseline, subject, receipt, rows = pacing_fixture(durations)
        if mutate: mutate(rows)
        meter = MountedPacingMeasurement(200)
        meter.arm(subject, baseline, receipt)
        for snapshot, events in rows:
            meter.observe(snapshot, events)
            if meter.failures: break
            if meter.main_complete and len(meter.windows) == 1:
                meter.begin_recovery(snapshot)
        return meter, receipt, rows

    def test_seven_and_separate_recovery(self):
        meter, receipt, rows = self.replay()
        self.assertEqual(meter.failures, [])
        self.assertTrue(meter.ready)
        receipt.update(closed=True,counts=meter.counts,
                       latestCompletedPose=rows[-1][0]["mountPacing"]["latestCompletedPose"])
        result = meter.close(receipt, rows[-1][0])
        self.assertTrue(result["passed"])
        self.assertEqual(sum(map(len,result["proofEvidence"].values())),9)
        self.assertEqual([w["joined"] for w in result["windows"]],[7,1])

    def test_wrong_pair_fails(self):
        def wrong(rows): rows[2][1][-1]["data"]["mount"]["pos_x"] += 1
        meter, _, _ = self.replay(wrong)
        self.assertTrue(meter.failures)

    def test_retained_trace_wrap_is_not_unread_loss(self):
        def wrap(rows, **changes):
            event = next(e for e in rows[0][1] if e['kind'] == 'native')
            data = dict(code='ring-overwrite', diagnosticOnly=True, count=1,
                        unreadEventsLost=0, traceStream=event['data']['traceStream'])
            data.update(changes)
            rows[0][1].append(dict(frame=rows[0][0]['frame'], kind='trace-status', data=data))
        meter, _, _ = self.replay(wrap)
        self.assertEqual(meter.failures, [])
        for fault in ({'unreadEventsLost':1}, {'traceStream':999}, {'count':0},
                      {'diagnosticOnly':False}, {'coverageComplete':False}):
            with self.subTest(fault=fault):
                meter, _, _ = self.replay(lambda rows: wrap(rows, **fault))
                self.assertEqual(meter.failures, ['mounted pacing trace lost unread events'])

    def test_constant_speed_stream_rejected_at_first_acceleration_boundary(self):
        # All positions, elapsed samples, lifecycle events and callback clocks
        # agree with these durations. Only the required acceleration is absent.
        meter, _, _ = self.replay(durations=(16,)*8)
        self.assertEqual(meter.failures, ["mounted Cyndaquil acceleration duration differs"])
        self.assertEqual(meter.windows[0]["joined"], 3)
        self.assertFalse(meter.ready)

    def test_linear_speed_change_pose_is_rejected(self):
        def linear(rows):
            snapshot = next(snapshot for snapshot, _ in rows
                            if snapshot["actors"][0]["motionKind"] == "WALK"
                            and snapshot["actors"][0]["commitSequence"] == 3
                            and snapshot["actors"][0]["motionElapsed"] == 1)
            actor = snapshot["actors"][0]
            snapshot["player"]["pos_x"] = (actor["origin"]["x"] << 16) + 32768 \
                + 65536 // actor["motionDuration"]

        meter, _, _ = self.replay(linear)
        self.assertIn("mounted Walk pose differs from eased path", meter.failures)

    def test_missing_completed_pose_fails(self):
        meter, _, _ = self.replay(lambda rows: rows[0][0].pop("mountPacing"))
        self.assertTrue(meter.failures)

    def test_missing_lifecycle_fails(self):
        def wrong(rows):
            for _, events in rows:
                events[:] = [e for e in events if e.get("data",{}).get("event") != "CONTROL_RETURNED"]
        meter, _, _ = self.replay(wrong)
        self.assertTrue(meter.failures)

    def test_no_close_never_passes(self):
        meter, _, _ = self.replay()
        self.assertFalse(meter.finish()["passed"])

    def test_missing_callback_fails_sequence(self):
        def wrong(rows):
            rows[0][1][:] = [e for e in rows[0][1] if e["kind"] != "native-observation"]
        meter, _, _ = self.replay(wrong)
        self.assertIn("missing native receipt",meter.failures)

    def test_changed_profile_fails(self):
        def wrong(rows): rows[1][0]["actors"][0]["behaviorFingerprint"] += 1
        meter, _, _ = self.replay(wrong)
        self.assertIn("mounted identity, profile or context changed",meter.failures)

    def test_late_pair_overwrite_fails(self):
        def wrong(rows): rows[0][0]["mountPacing"]["latestCompletedPose"]["mount"]["pos_x"] += 1
        meter, _, _ = self.replay(wrong)
        self.assertTrue(meter.failures)

    def test_release_failure_rejected(self):
        meter, receipt, rows = self.replay()
        receipt.update(closed=True,counts=meter.counts,
                       latestCompletedPose=deepcopy(rows[-1][0]["mountPacing"]["latestCompletedPose"]))
        receipt["latestCompletedPose"]["avatarControl"]["flags"] = 1
        with self.assertRaisesRegex(ValueError,"not released"):
            meter.close(receipt,rows[-1][0])

    def test_lost_world_step_never_completes(self):
        def wrong(rows):
            # Retain sequence ownership but remove its callback meaning.
            for _, events in rows:
                for e in events:
                    if e.get("data",{}).get("kind") == "playerStep":
                        e["data"]["observation"] = "unrelated-observation"
        meter, _, _ = self.replay(wrong)
        self.assertFalse(meter.ready)

    def test_callback_cycles_not_completion_frames(self):
        def wrong(rows):
            rows[0][1][-1]["data"]["returnNativeCycle"] += 10
        meter, _, _ = self.replay(wrong)
        self.assertIn("native callback clock differs",meter.failures)

    def test_wrong_species_rejected(self):
        baseline, subject, receipt, _ = pacing_fixture()
        baseline["actors"][0]["species"] = 95
        with self.assertRaises(ValueError): MountedPacingMeasurement(100).arm(subject,baseline,receipt)


if __name__ == "__main__":
    unittest.main()

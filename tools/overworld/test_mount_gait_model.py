"""Compile the production mounted gait model and test presentation invariants."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Pose(C.Structure):
    _fields_ = [(key, C.c_int32) for key in ("x", "z", "velocityX", "velocityZ")] + [
        (key, C.c_int16) for key in ("bodyY", "riderY", "leanX", "leanZ")] + [
        ("phase", C.c_uint16), ("walking", C.c_uint8), ("reserved", C.c_uint8)]


class State(C.Structure):
    _fields_ = [("previous", Pose), ("pose", Pose)] + [
        (key, C.c_uint32) for key in ("stamp", "session", "owner")] + [
        ("initialized", C.c_uint8), ("reserved", C.c_uint8 * 3)]


class Input(C.Structure):
    _fields_ = [("x", C.c_int32), ("z", C.c_int32)] + [
        (key, C.c_uint32) for key in ("stamp", "session", "owner")] + [
        ("mode", C.c_uint8), ("options", C.c_uint8)]


class MountGaitModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="mount-gait-model-")
        binary = Path(cls.directory.name) / "gait.so"
        built = subprocess.run([
            "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-shared", "-fPIC",
            "-DOVERWORLD_MOUNT_GAIT_HOST", str(ROOT / "lib/overworld/overworld_mount_gait_model.c"),
            "-o", str(binary)], capture_output=True, text=True)
        if built.returncode:
            cls.directory.cleanup()
            raise AssertionError(built.stderr)
        cls.library = C.CDLL(str(binary))
        cls.sample = cls.library.OverworldMountGait_Sample
        cls.sample.argtypes = [C.POINTER(State), C.POINTER(Input)]
        cls.sample.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def step(self, state, x=0, z=0, stamp=0, mode=1, options=0xA6, session=1, owner=1):
        self.sample(C.byref(state), C.byref(Input(x, z, stamp, session, owner, mode, options)))
        return state.pose

    def assert_rest(self, pose):
        self.assertEqual((pose.bodyY, pose.riderY, pose.leanX, pose.leanZ), (0, 0, 0, 0))

    def test_all_configurations_and_32_speeds_keep_the_seat_and_offsets_bounded(self):
        for options in range(256):
            bounce, stride, settle, lean = options & 3, ((options >> 2) & 3) + 1, (options >> 4) & 3, options >> 6
            for duration in range(1, 33):
                state = State()
                self.step(state, options=options)
                x = previous_x = previous_phase = previous_body = previous_lean = 0
                for frame in range(1, 65):
                    x = frame * 65536 // duration
                    pose = self.step(state, x=x, stamp=frame, options=options)
                    self.assertEqual(pose.phase, (previous_phase + min((x - previous_x) // stride, 8192)) & 65535)
                    self.assertLessEqual(abs(pose.bodyY - previous_body), 1024)
                    self.assertLessEqual(abs(pose.leanX - previous_lean), 512)
                    self.assertGreaterEqual(pose.bodyY, 0)
                    self.assertLessEqual(pose.bodyY, bounce * 4096)
                    self.assertLessEqual(abs(pose.riderY - pose.bodyY), settle * 512)
                    self.assertLessEqual(abs(pose.leanX), lean * 4096)
                    self.assertEqual(pose.leanZ, 0)
                    previous_x, previous_phase, previous_body, previous_lean = x, pose.phase, pose.bodyY, pose.leanX
                for frame in range(65, 129):
                    self.step(state, x=x, stamp=frame, mode=0, options=options)
                self.assert_rest(state.pose)

    def test_tile_and_speed_changes_preserve_distance_phase_in_all_directions(self):
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
            state = State()
            self.step(state, options=0xA6)
            stamp = distance = expected_phase = 0
            # Both acceleration and braking, including extremes and variance.
            for duration in (*range(32, 0, -1), *range(1, 33)):
                origin = distance
                for elapsed in range(1, duration + 1):
                    stamp += 1
                    next_distance = origin + elapsed * 65536 // duration
                    expected_phase = (expected_phase + min((next_distance - distance) // 2, 8192)) & 65535
                    pose = self.step(state, x=next_distance * dx, z=next_distance * dz, stamp=stamp)
                    self.assertEqual(pose.phase, expected_phase)
                    distance = next_distance

    def test_same_update_recomputes_once_from_the_previous_update(self):
        state = State()
        self.step(state)
        self.step(state, x=4000, stamp=1)
        prior = State.from_buffer_copy(state)
        self.step(state, x=8000, stamp=2)
        self.step(state, x=12000, stamp=2)
        final = bytes(state)
        self.step(prior, x=12000, stamp=2)
        self.assertEqual(final, bytes(prior))
        self.step(state, x=12000, stamp=2)
        self.assertEqual(final, bytes(state))

    def test_acceleration_and_braking_lean_have_opposite_signs(self):
        for direction in (-1, 1):
            state = State()
            self.step(state)
            self.step(state, x=8192 * direction, stamp=1)
            self.assertLess(state.pose.leanX * direction, 0)
            for frame in range(2, 25):
                self.step(state, x=frame * 8192 * direction, stamp=frame)
            for frame in range(25, 30):
                self.step(state, x=24 * 8192 * direction, stamp=frame, mode=0)
            self.assertGreater(state.pose.leanX * direction, 0)
            for frame in range(30, 95):
                self.step(state, x=24 * 8192 * direction, stamp=frame, mode=0)
            self.assert_rest(state.pose)

    def test_other_motion_teleport_and_new_mount_clear_old_offsets(self):
        for change in (dict(mode=2), dict(x=196608), dict(session=2), dict(owner=2)):
            state = State()
            self.step(state)
            self.step(state, x=8192, stamp=1)
            self.assertNotEqual(state.pose.bodyY, 0)
            self.step(state, x=change.get("x", 8192), stamp=2,
                      mode=change.get("mode", 1), session=change.get("session", 1), owner=change.get("owner", 1))
            self.assert_rest(state.pose)
            self.assertEqual(state.pose.phase, 0)


if __name__ == "__main__":
    unittest.main()

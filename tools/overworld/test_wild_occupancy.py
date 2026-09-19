"""Fast actual-C occupancy relocation guards; no emulator or images."""
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import verify_overworld_wild_occupancy as occupancy


class WildOccupancyTests(unittest.TestCase):
    def test_actual_c_parity(self):
        occupancy.host_checks()

    def test_wrong_native_predicates(self):
        occupancy.negative_controls()

    def test_actual_arm_header(self):
        occupancy.abi_checks()

    def test_package_negative_controls(self):
        occupancy.package_controls()

    def test_host_compiler_is_separate_and_accepts_arguments(self):
        with patch.dict(occupancy.os.environ, {
            "CC": "not-a-host-compiler --arm-target",
            "HOST_CC": "cc -O0",
        }):
            occupancy.host_checks()
            occupancy.negative_controls()


if __name__ == "__main__":
    unittest.main()

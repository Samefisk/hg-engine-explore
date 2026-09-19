#!/usr/bin/env python3
"""Bounded actual-C command sequence/cancel check; no ROM or engine run."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.overworld.test_actor_facade_commands import ActorFacadeCommandsTests


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ActorFacadeCommandsTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)

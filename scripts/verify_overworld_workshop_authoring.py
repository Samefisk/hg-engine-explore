#!/usr/bin/env python3
"""Run the permanent Workshop authoring ownership checks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "tools.overworld.test_workshop_authoring"
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)

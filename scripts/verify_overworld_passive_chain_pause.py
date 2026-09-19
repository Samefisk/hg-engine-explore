#!/usr/bin/env python3
"""Run the extracted-C passive Movement Chain regression."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.overworld.test_passive_chain_pause import PassiveChainPauseTests


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PassiveChainPauseTests
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

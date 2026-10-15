#!/usr/bin/env python3
"""Run the real save adapter and HP reducer with isolated host save blocks.

This proves record compatibility and the zero-to-recovery boundary, not ROM
Continue, flash saving, or stock blackout execution.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="player-health-save-") as temporary:
        binary = Path(temporary) / "save-test"
        subprocess.run([
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-DOVERWORLD_BEHAVIOR_HOST", "-DPLAYER_HEALTH_HOST",
            "-Wno-unknown-attributes",
            "-Wno-macro-redefined", "-Wno-incompatible-library-redeclaration",
            "-I", str(ROOT / "include"),
            str(ROOT / "src/player_health_save.c"),
            str(ROOT / "lib/overworld/player_health_model.c"),
            str(ROOT / "tests/player_health_save_host.c"),
            "-o", str(binary),
        ], check=True)
        subprocess.run([str(binary)], check=True)
    print("Player HP save compatibility and zero recovery boundary passed.")


if __name__ == "__main__":
    main()

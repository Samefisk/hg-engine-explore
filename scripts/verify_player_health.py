#!/usr/bin/env python3
"""Build and run the production player-health reducer on the host."""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="player-health-") as temporary:
        binary = Path(temporary) / "player-health-model-test"
        subprocess.run(
            [
                "cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                "-DPLAYER_HEALTH_HOST", "-I", str(ROOT / "include"),
                str(ROOT / "lib/overworld/player_health_model.c"),
                str(ROOT / "tests/overworld/player_health_model_test.c"),
                "-o", str(binary),
            ],
            check=True,
        )
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()

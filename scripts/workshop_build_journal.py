"""Keep the complete Workshop build log and last status across restarts."""
from pathlib import Path
import json
import os
import time


class BuildJournal:
    def __init__(self, root: Path):
        self.directory = root / "build" / "workshop"
        self.log = self.directory / "last-build.log"
        self.status = self.directory / "last-build.json"

    def save(self, state: dict, *, start: bool = False) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        if start:
            self.log.write_text(state.get("output") or "", encoding="utf-8")
        temporary = self.status.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state) + "\n", encoding="utf-8")
        os.replace(temporary, self.status)

    def append(self, text: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.log.open("a", encoding="utf-8") as output:
            output.write(text)

    def restore(self, limit: int) -> dict:
        try:
            state = json.loads(self.status.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return {}
        except (OSError, ValueError):
            return {}
        try:
            # Read a bounded tail while preserving the whole log on disk.
            with self.log.open("rb") as output:
                output.seek(0, 2)
                output.seek(max(0, output.tell() - limit * 4))
                state["output"] = output.read().decode("utf-8", errors="replace")[-limit:]
        except OSError:
            pass
        if state.get("running"):
            state.update(running=False, ok=False, endedAt=time.time(),
                         error="Workshop restarted during this build. The build result is unknown; inspect the retained log before retrying.")
        return state

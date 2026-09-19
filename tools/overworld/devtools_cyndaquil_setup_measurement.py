"""Diagnostic normal nurse/selector setup, not a long-route proof."""
from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement


class CyndaquilNormalSetupMeasurement(UnmountedCadenceMeasurement):
    def result(self):
        result = super().result()
        ready = not self.failures and self.pending_transition is None \
            and len(self.completed_setup_transitions) == 2 \
            and all(self.setup.get(key) is not None for key in
                    ("healed", "exitedCenter", "confirmed", "bound")) \
            and self.subject is not None and self.subject.get("subjectIdentity") == 2046726716 \
            and self.saved_mon is not None and self.saved_mon.get("maxHp") == 21
        result.update(ready=ready, passed=self.closed and ready,
                      state="failed" if self.failures else "passed" if self.closed and ready else "running",
                      scope="normal saved Cyndaquil setup only; no route, cadence or accepted proof")
        result.pop("limits", None)  # Do not advertise unmeasured long-route floors.
        return result

    def finish(self):
        if not self.closed:
            if not self.failures and not self.result()["ready"]:
                self._fail("normal-cyndaquil-setup-incomplete", gap=True)
            self.closed = True
        return self.result()

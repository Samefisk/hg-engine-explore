"""Calibrate the shared spawn-height reader against one restored native read.

The unchanged POOL checker must reject only the observed preparation Y error.
This module owns no memory writes, emulator, setup, or accepted proof.
"""
from copy import deepcopy

from tools.overworld.devtools_spawn_measurement import PoolSpawnSurfaceMeasurement
from tools.overworld.devtools_spawn_surface_measurement import check_pool_spawn_surface


HEIGHT_ENVELOPE = frozenset(("observation", "sequence", "setupMode", "entryActorFrame",
                            "entryNativeCycle", "returnActorFrame", "returnNativeCycle",
                            "guestTiming"))
EXPECTED_REASON = "terminal Y differs from native landing height"


class LiveSpawnHeightControlMeasurement:
    def __init__(self, schema, source_sha256, *, max_frames, authored_profiles):
        self.baseline = PoolSpawnSurfaceMeasurement(schema, source_sha256,
            max_frames=max_frames, authored_profiles=authored_profiles)
        self.receipt = self.receipt_frame = self.height_frame = None
        self.detection = self.cleanup = None
        self.failures = []
        self.closed = False

    def _check_control(self, snapshot, baseline):
        receipt = self.receipt
        if not isinstance(receipt, dict):
            raise ValueError("native spawn-height read control is missing")
        if (receipt.get("state") != "complete" or receipt.get("scope") != "native-observer-control-only"
                or receipt.get("cleanupPending") is not False or receipt.get("failure") is not None
                or receipt.get("acceptedProof") is not False
                or type(receipt.get("delta")) is not int or receipt["delta"] != 4096
                or type(receipt.get("writes")) is not int or receipt["writes"] != 2):
            raise ValueError("native spawn-height control lacks exact write/restore completion")
        spawn = self.baseline.landing.spawn
        height = spawn["jumpReceipts"][0]["landingHeight"]
        raw = {key: value for key, value in height.items() if key not in HEIGHT_ENVELOPE}
        if receipt.get("clean") != raw or receipt.get("restored") != raw:
            raise ValueError("native height control clean/restored source, context, point or data differs")
        # Both rows are queued synchronously by the same native return hook.
        # The sampler increments completed_frames before flushing that queue,
        # so the read's completed-frame count is exactly one before its row.
        # No emulated instruction runs between the return clock and the read.
        clocks = ("entryActorFrame", "entryNativeCycle", "returnActorFrame", "returnNativeCycle")
        if (self.receipt_frame != self.height_frame
                or type(receipt.get("frame")) is not int or receipt["frame"] != self.receipt_frame - 1
                or receipt["frame"] < 0
                or any(type(receipt.get(key)) is not int or receipt[key] != height[key] for key in clocks)
                or type(receipt.get("nativeCycle")) is not int
                or receipt["nativeCycle"] != height["returnNativeCycle"]):
            raise ValueError("native height control is stale or outside its height read boundary")
        bad = deepcopy(raw)
        y = bad["positionAfter"]["pos_y"]
        if type(y) is not int or not -0x80000000 <= y + 4096 <= 0x7FFFFFFF:
            raise ValueError("native control Y delta is outside signed position bounds")
        bad["positionAfter"]["pos_y"] = y + 4096
        if receipt.get("bad") != bad:
            raise ValueError("native bad receipt did not change only preparation Y by 4096")
        altered = deepcopy(spawn)
        altered["jumpReceipts"][0]["landingHeight"] = {
            **deepcopy(receipt["bad"]), **{key: deepcopy(height[key]) for key in HEIGHT_ENVELOPE if key in height}}
        try:
            check_pool_spawn_surface(altered, snapshot,
                source_sha256=self.baseline.landing.source_sha256,
                authored_profiles=self.baseline.authored_profiles,
                verified_stop_boundary=baseline["stopBoundary"])
        except ValueError as error:
            if str(error) != EXPECTED_REASON:
                raise ValueError("native bad height failed for a different reason: " + str(error)) from error
        else:
            raise ValueError("native bad height was accepted by the unchanged surface checker")
        self.detection = {"kind": "spawn-height-read", "reason": EXPECTED_REASON,
            "frame": snapshot["frame"], "subject": deepcopy(baseline["subject"]),
            "target": deepcopy(raw["target"]), "cleanY": y, "badY": y + 4096,
            "stopBoundary": deepcopy(baseline["stopBoundary"])}
        self.cleanup = {"restored": True, "cleanupPending": False,
            "receipt": deepcopy(receipt), "frame": self.receipt_frame}

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("spawn height control measurement is closed")
        if self.failures:
            return self.result()
        observed = self.baseline.observe(snapshot, events)
        try:
            for event in events:
                data = event.get("data", {})
                if event.get("kind") != "native-observation":
                    continue
                if data.get("observation") == "spawn-height-read-control":
                    if self.receipt is not None:
                        raise ValueError("native spawn-height control is duplicated")
                    self.receipt, self.receipt_frame = deepcopy(data), event["frame"]
                if data.get("observation") == "spawn-landing-height" and self.baseline.landing.spawn is not None:
                    height = self.baseline.landing.spawn["jumpReceipts"][0]["landingHeight"]
                    if data == height:
                        self.height_frame = event["frame"]
            if observed["ready"] and self.detection is None:
                self._check_control(snapshot, observed)
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
            self.failures.append({"code": "invalid-spawn-height-control", "frame": snapshot.get("frame"),
                                  "message": str(error)})
        return self.result()

    def result(self):
        baseline = self.baseline.result()
        failures = deepcopy(self.failures) + baseline["failures"]
        ready = baseline["ready"] and self.detection is not None and self.cleanup is not None and not failures
        return {"state": "failed" if failures or self.closed and not ready
                else "completed" if self.closed else "observing",
            "passed": self.closed and ready, "ready": ready, "acceptedProof": False,
            "subject": deepcopy(baseline["subject"]), "frames": baseline["frames"],
            "baseline": baseline, "detections": {"spawn-height-read": deepcopy(self.detection)} if self.detection else {},
            "cleanup": deepcopy(self.cleanup), "failures": failures,
            "measurementErrors": baseline["measurementErrors"], "completeMotions": baseline["completeMotions"],
            "spawnPassed": baseline["spawnPassed"], "scope": "separate native spawn-height reader calibration; no normal-play credit"}

    def finish(self):
        self.baseline.finish()
        self.closed = True
        if not self.result()["ready"] and not self.result()["failures"]:
            self.failures.append({"code": "incomplete-spawn-height-control", "frame": self.baseline.landing.last_frame})
        return self.result()

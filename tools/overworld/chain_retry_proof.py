"""Exact controlled retry contract; values come from shared native replay."""
RULES = (
    ("live-actor-identity", "retry-natural-subject", "naturalSubjectAndBaseline"),
    ("controlled-action", "retry-one-rejected-start", "oneInjectedRejection"),
    ("controlled-action", "retry-full-cooldown-frame", "fullCooldownFrame"),
    ("logical-commit", "retry-selection-and-count-preserved", "selectedActionAndTicksPreserved"),
    ("rendered-motion", "retry-profile-defined-complete-action", "profileDefinedCompleteAction"),
    ("engine-boundary", "retry-native-motion-boundaries", "nativeMotionAndControl"),
    ("control-release", "retry-terminal-control", "nativeMotionAndControl"),
)
CLAIMS = ["controlled-action", "live-actor-identity", "logical-commit",
          "engine-boundary", "rendered-motion", "control-release"]
REQUIREMENT = "legacy.ledyba-chain-pause"
KIND = "chain-retry-v1"


def contract():
    result = {}
    for claim, name, _ in RULES:
        result.setdefault(claim, []).append({"name": name, "operator": "eq",
            "type": "integer", "validator": "meaningful-observation", "expected": 1})
    return result


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    if meter.get("passed") is not True or meter.get("ready") is not True \
            or any(meter.get(key) != [] for key in
                   ("failures", "measurementErrors", "identityErrors", "chainErrors", "renderErrors", "observationErrors")):
        raise ValueError("controlled retry lacks complete same-subject native coverage")
    checks = meter.get("proofChecks", {})
    if set(checks) != {key for _, _, key in RULES} or any(value is not True for value in checks.values()):
        raise ValueError("controlled retry did not meet its exact contract")
    cleanup = record.get("sessionCleanup", {})
    if cleanup != {"sessionId": record.get("sessionId"), "closed": True, "errors": []}:
        raise ValueError("controlled retry private session did not close cleanly")
    native = record.get("chainRetryCleanup") or {}
    state = native.get("chainRetryControl") or {}
    proof = meter.get("retryProof") or {}
    arm = (proof.get("arm") or {}).get("chainRetryControl") or {}
    if native.get("closed") is not True or native.get("advancedFrames") != 0 \
            or state.get("closed") is not True or state.get("failure") is not None \
            or state.get("pendingWrites") != 0 or state.get("guestMemoryWrites") != 0 \
            or state.get("injected") is not True or state.get("acceptedProof") is not False \
            or not arm.get("subject") or state.get("subject") != arm["subject"] \
            or not proof.get("injection") or state.get("injection") != proof["injection"]:
        raise ValueError("controlled retry control cleanup is missing")
    return [{"claim": claim, "name": name, "value": int(checks[key]),
             "operator": "eq", "threshold": 1, "passed": True} for claim, name, key in RULES]

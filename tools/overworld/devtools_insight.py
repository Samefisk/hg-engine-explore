"""Read-only explanations and first differences; unknown is never a guess."""
from copy import deepcopy


def explain_actor(snapshot, handle, schema=None):
    actors = [actor for actor in snapshot.get("actors", []) if actor.get("handle", {}).get("value") == handle]
    if len(actors) != 1:
        raise ValueError("explanation requires one current actor handle")
    actor = actors[0]
    native = snapshot.get("nativeObservation", {})
    fingerprint = actor.get("behaviorFingerprint")
    profiles = [profile for profile in native.get("resolvedProfiles", [])
                if fingerprint is not None and profile.get("fingerprint") == fingerprint]
    resolved = deepcopy(profiles[0]) if len(profiles) == 1 else None
    if resolved and schema:
        lanes = {}
        for name, encoded in zip(("owner", "tired"), resolved.get("lanes", [])):
            raw = bytes.fromhex(encoded)
            if len(raw) != schema["compactSize"]:
                raise ValueError("observed lane size differs from the current schema")
            lanes[name] = {field["key"]: {"value": int.from_bytes(raw[field["offset"]:field["offset"] +
                {"u8": 1, "u16": 2, "u32": 4}[field["cType"]]], "little"), "unit": field["unit"]}
                for field in schema["fields"]}
        resolved["decodedLanes"] = lanes
    return {"subject": deepcopy(actor), "frame": snapshot.get("frame"),
            "context": deepcopy(snapshot.get("context")),
            "resolvedProfile": resolved,
            "profileStatus": "observed" if len(profiles) == 1 else "unknown: no unique observed resolver receipt for this fingerprint",
            "decision": {key: actor.get(key) for key in ("lastDecisionName", "lastCancelReasonName", "motionKind", "motionPhase", "inputOwnership")},
            "coverage": {key: native.get(key) for key in ("installedBeforeBoot", "coverageComplete", "eventsDropped", "profilesEvicted", "error")},
            "scope": "Current observations only. A missing rejection or profile receipt is unknown, not inferred from the sprite or source configuration."}


def first_difference(left, right):
    """Exact ordered JSON comparison, explicitly not semantic parity proof."""
    def visit(a, b, path):
        if type(a) is not type(b): return {"path": path, "left": a, "right": b, "reason": "type"}
        if isinstance(a, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a or key not in b:
                    return {"path": path + [key], "leftPresent": key in a, "rightPresent": key in b,
                            "left": a.get(key), "right": b.get(key), "reason": "missing-field"}
                found = visit(a[key], b[key], path + [key])
                if found: return found
        elif isinstance(a, list):
            for index in range(min(len(a), len(b))):
                found = visit(a[index], b[index], path + [index])
                if found: return found
            if len(a) != len(b): return {"path": path, "leftLength": len(a), "rightLength": len(b), "reason": "length"}
        elif a != b: return {"path": path, "left": a, "right": b, "reason": "value"}
        return None
    difference = visit(left, right, [])
    return {"equal": difference is None, "firstDifference": difference,
            "scope": "Exact saved observation comparison; different frame or identity is not itself a gameplay regression.", "acceptedProof": False}

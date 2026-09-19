"""Fixed source inputs for shared measurement, used by execution and replay.

Recipes cannot select a Python module or a source path. No engine or acceptance
is owned here; the enclosing job/controller seals the current source identity.
"""
import hashlib
import json


def measurement_inputs(test, root):
    if not test.get("measurements"):
        return {}
    fixed_contract = ("unmounted-cadence-v1", "unmounted-game-cadence-v1", "center-entry-exit-v1", "cyndaquil-normal-setup-v1", "live-route-control-v1", "packaged-resolver-parity-v1", "actor-binding-context-v1", "actor-inspect-handle-v1", "live-walk-policy-control-v1", "mounted-frame-pacing-v1", "mounted-control-stress-v1", "mounted-hop-arc-v1", "mounted-nearest-diagonal-v1", "live-mount-pose-control-v1", "wild-walk-v1", "wild-ledge-v1", "wild-teleport-v1", "runner-stop-skid-v1", "runner-turn-runway-v1", "appear-hop-timing-v1", "wild-transition-invalidation-v1", "follower-transition-rebind-v1", "mounted-streaming-path-v1", "mounted-cardinal-streaming-v1", "mounted-walk-transition-v1", "land-surf-separation-v1", "population-fast-travel-v1", "mounted-teleport-matrix-v1", "live-wild-clear-control-v1", "turn-skid-v1", "wild-battle-handoff-v1", "mounted-hop-transition-v1", "warp-gate-v1", "diagonal-corner-v1", "live-corner-control-v1", "mounted-frame-matrix-v1", "live-walk-matrix-control-v1", "mounted-stomp-v1", "live-stomp-control-v1", "mounted-crash-v1", "live-crash-control-v1")
    if all(item["kind"] in fixed_contract for item in test["measurements"]):
        # Setup transitions are already in the immutable typed recipe. Do not
        # add unrelated profile reads to a fixed-contract route measurement.
        return {item["kind"]: {"contractVersion": 1} for item in test["measurements"]}
    raw_profiles = (root / "data/overworld_behavior_profiles.json").read_bytes()
    source = {
        "schema": json.loads((root / "tools/overworld/behavior_schema.json").read_text()),
        "sourceSha256": hashlib.sha256(raw_profiles).hexdigest(),
    }
    if any(item["kind"] == "unmounted-zero-stutter-v1"
           for item in test["measurements"]):
        return {item["kind"]: (source
                if item["kind"] == "unmounted-zero-stutter-v1"
                else {"contractVersion": 1})
                for item in test["measurements"]}
    # Retain authored POOL meaning from the same bytes as its sealed digest.
    # Existing measurements keep their exact, two-key input contract.
    return {item["kind"]: ({**source, "authoredProfiles": json.loads(raw_profiles)}
                          if item["kind"] in ("pool-spawn-v1", "pool-spawn-surface-v1", "live-spawn-height-control-v1") else source)
            for item in test["measurements"]}

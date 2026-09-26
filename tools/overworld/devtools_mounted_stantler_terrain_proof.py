"""Pure checked proof of the mounted Stantler terrain-loss route.

The job owns the private session and keeps every completed frame. The two
paused terrain receipts use the existing native loaded-terrain reader.
"""

from copy import deepcopy


KIND = "mounted-stantler-terrain-route-v1"
REQUIREMENT = "current.mounted-stantler-terrain-route"
CLAIMS = ("natural-input", "live-actor-identity", "streaming-path")
ROUTE = (
    ("route-right-1", "RIGHT"), ("route-right-2", "RIGHT"),
    ("route-up-1", "UP"), ("route-left-1", "LEFT"),
    ("route-left-2", "LEFT"), ("route-up-2", "UP"),
    ("route-down", "DOWN"),
)
STAGES = tuple(name for name, _ in ROUTE) + (
    "route-terrain", "recovery-right", "recovery-terrain",
)
FAULTS = ("route-cell-unloaded", "recovery-cell-unloaded")


def contract():
    def exact(name, expected):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": expected}

    return {
        "natural-input": [exact("exact-mounted-route-frames", 840)],
        "live-actor-identity": [exact("current-mounted-stantler", 1)],
        "streaming-path": [exact("route-nearby-loaded-cells", 9),
                           exact("recovery-nearby-loaded-cells", 25),
                           {"name": "right-recovery-distance", "operator": "gte",
                            "type": "integer", "validator": "meaningful-observation",
                            "expected": 8}],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mounted Stantler terrain route: " + reason)


def _actor(sample):
    actors = [actor for actor in sample.get("actors", [])
              if actor.get("active") is True and actor.get("role") == "MOUNTED"
              and actor.get("species") == 234]
    _require(len(actors) == 1, "expected one current mounted Stantler")
    actor = actors[0]
    _require(actor.get("identityVerified") is True
             and actor.get("presentationAttached") is True
             and actor.get("inputOwnership") == 1
             and actor.get("handle", {}).get("slot") == 7,
             "mounted Stantler identity or presentation differs")
    return actor


def _observations(rows):
    expected = STAGES
    seen = []
    frames = {name: [] for name in (*[item[0] for item in ROUTE], "recovery-right")}
    terrain = {}
    for row in rows:
        if row.get("phase") != "observe" or not row.get("action"):
            continue
        action = row["action"]
        _require(action in expected, "unexpected observation action")
        if not seen or action != seen[-1]:
            seen.append(action)
            _require(seen == list(expected[:len(seen)]), "route action order differs")
        if action in frames:
            samples = row.get("samples")
            _require(isinstance(samples, list) and samples
                     and row.get("completedGameFrames") == len(samples),
                     "route step lacks complete frame samples")
            frames[action].extend(samples)
        else:
            _require(row.get("command") == "terrain" and action not in terrain,
                     "terrain probe is absent or repeated")
            terrain[action] = row.get("receipt", {}).get("terrain")
    _require(seen == list(expected), "exact route or terrain probe is missing")
    _require(all(len(samples) == 120 for samples in frames.values()),
             "a held direction did not last 120 completed frames")
    ordered = [sample for name in frames for sample in frames[name]]
    _require(all(right.get("frame") == left.get("frame") + 1
                 and right.get("nativeCycle", 0) >= left.get("nativeCycle", 0)
                 for left, right in zip(ordered, ordered[1:])),
             "route has a missing completed frame or reversed clock")
    return frames, terrain


def _terrain_probe(probe, sample, radius):
    _require(isinstance(probe, dict), "terrain receipt is missing")
    observation = probe.get("observation", {})
    player = sample.get("player", {})
    center = {"x": player.get("x"), "z": player.get("y")}
    _require(observation.get("boundary") == "paused-native-cycle-end"
             and observation.get("lastCompletedGameFrame") == sample.get("frame")
             and observation.get("nativeCycle", 0) >= sample.get("nativeCycle", 0)
             and observation.get("context") == sample.get("context")
             and observation.get("center") == center,
             "terrain receipt is not from the route endpoint")
    cells = probe.get("cells")
    expected = {(center["x"] + dx, center["z"] + dz)
                for dz in range(-radius, radius + 1)
                for dx in range(-radius, radius + 1)}
    _require(isinstance(cells, list) and len(cells) == len(expected)
             and {(cell.get("x"), cell.get("z")) for cell in cells
                  if isinstance(cell, dict)} == expected,
             "terrain grid does not cover the exact nearby tiles")
    loaded = sum(cell.get("loaded") is True for cell in cells)
    _require(loaded == len(expected), "terrain has an unloaded nearby cell")
    _require(all(isinstance(cell.get("provenance"), dict)
                 and type(cell["provenance"].get("fieldPointer")) is int
                 and type(cell["provenance"].get("mapMatrixPointer")) is int
                 and type(cell["provenance"].get("readerPointer")) is int
                 and cell["provenance"].get("store") in
                     ("rolling-land-manager", "full-terrain-attributes")
                 for cell in cells), "terrain lacks native loaded-cell provenance")
    return loaded


def _measure(rows):
    frames, terrain = _observations(rows)
    first = frames[ROUTE[0][0]][0]
    route = frames[ROUTE[-1][0]][-1]
    recovery = frames["recovery-right"][-1]
    start_actor, route_actor, end_actor = (_actor(sample)
                                          for sample in (first, route, recovery))
    _require(first.get("context", {}).get("mapId") == 33
             and first.get("context") == route.get("context") == recovery.get("context")
             and first.get("player", {}).get("x") == 585
             and first.get("player", {}).get("y") == 402
             and start_actor.get("handle") == route_actor.get("handle")
                 == end_actor.get("handle")
             and start_actor.get("behaviorFingerprint") == route_actor.get("behaviorFingerprint")
                 == end_actor.get("behaviorFingerprint"),
             "route lacks one prepared current mounted Stantler")
    route_player, end_player = route["player"], recovery["player"]
    _require(route_player.get("x") == 576 and route_player.get("y") in (397, 398),
             "the 840-frame route did not reach its measured endpoint")
    route_loaded = _terrain_probe(terrain["route-terrain"], route, 1)
    distance = end_player.get("x", -1) - route_player["x"]
    _require(distance >= 8 and end_player.get("y") in (395, 396, 397, 398),
             "RIGHT recovery did not move away from the old freeze endpoint")
    recovery_loaded = _terrain_probe(terrain["recovery-terrain"], recovery, 2)
    return {"values": {"exact-mounted-route-frames": 840,
                       "current-mounted-stantler": 1,
                       "route-nearby-loaded-cells": route_loaded,
                       "recovery-nearby-loaded-cells": recovery_loaded,
                       "right-recovery-distance": distance},
            "routeEndpoint": [route_player["x"], route_player["y"]],
            "recoveryEndpoint": [end_player["x"], end_player["y"]],
            "subjectHandle": deepcopy(end_actor["handle"])}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "world.streaming.stantler-mounted-route"
                     and [action.get("id") for action in test.get("actions", [])]
                         == list(STAGES), "reviewed route recipe differs")
        copied = deepcopy(rows) if fault else rows
        if fault:
            _require(fault in FAULTS, "unknown copied-data fault")
            target = "route-terrain" if fault == FAULTS[0] else "recovery-terrain"
            for row in copied:
                if row.get("action") == target and row.get("command") == "terrain":
                    cells = row.get("receipt", {}).get("terrain", {}).get("cells", [])
                    if cells:
                        cells[0]["loaded"] = False
                        applied = True
                        break
            _require(applied, "copied-data terrain fault did not find its receipt")
        return {"passed": True, "faultApplied": applied, "failures": [],
                **_measure(copied)}
    except (ValueError, KeyError, TypeError, IndexError) as error:
        return {"passed": False, "faultApplied": applied, "failures": [str(error)]}


def negative_controls(rows, test=None):
    controls = {fault: run(rows, test, fault) for fault in FAULTS}
    return {"passed": all(value["faultApplied"] and not value["passed"]
                          and any("terrain has an unloaded nearby cell" in failure
                                  for failure in value["failures"])
                          for value in controls.values()),
            "controls": controls}

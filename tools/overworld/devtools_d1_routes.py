"""Three reviewed normal-input D1 routes. No observation can author a route.

Only coordinates and input waypoints vary. Spawn, clock, frame, identity and
preparation requirements remain with the existing measurement owners.
"""
from copy import deepcopy

CHERRYGROVE = "cherrygrove-v1"
GOLDENROD = "goldenrod-route34-v1"
GOLDENROD35 = "goldenrod-route35-v1"

ROUTES = {
    CHERRYGROVE: {
        "start": (67, 564, 392), "arm": (33, 585, 406), "steps": 35,
        "warmup": (("east", "RIGHT", 1, 16, 67, 565, 392),
                   ("south", "DOWN", 7, 40, 67, 565, 398),
                   ("east-seam", "RIGHT", 27, 96, 33, 585, 398),
                   ("south-start", "DOWN", 35, 48, 33, 585, 406)),
        "crossing": (33, 67, 575, 398), "anchor": (67, 565, 398),
    },
    GOLDENROD35: {
        "start": (76, 358, 366), "arm": (101, 5, 3), "steps": 50,
        "warmup": (("north-gate", "UP", 41, 256, 101, 5, 12),
                   ("gatehouse", "UP", 50, 96, 101, 5, 3)),
        "crossing": (101, 39, 358, 316), "anchor": (39, 358, 315),
    },
    GOLDENROD: {
        "start": (76, 358, 366), "arm": (76, 358, 383), "steps": 17,
        "warmup": (("south", "DOWN", 17, 96, 76, 358, 383),),
        "crossing": (76, 38, 358, 384), "anchor": (38, 358, 385),
    },
}


def descriptor(key=CHERRYGROVE):
    if not isinstance(key, str) or key not in ROUTES:
        raise ValueError("unknown sealed D1 route")
    return deepcopy(ROUTES[key])


def selected_route(test, kind):
    rows = [row for row in test.get("measurements", []) if row.get("kind") == kind]
    if len(rows) > 1:
        raise ValueError("ambiguous sealed D1 route")
    key = rows[0].get("route", CHERRYGROVE) if len(rows) == 1 else CHERRYGROVE
    descriptor(key)
    return key


def warmup_admissions(key):
    route = descriptor(key)
    if key == GOLDENROD35:
        return [(76, 0, [358,366-i], [358,365-i]) for i in range(41)] + [
            (101, 0, [5,12-i], [5,11-i]) for i in range(9)]
    _, x, z = route["start"]
    rows = []
    for _, direction, count, _, _, target_x, target_z in route["warmup"]:
        dx, dz, native_direction = {
            "RIGHT": (1, 0, 3), "DOWN": (0, 1, 1),
        }[direction]
        while len(rows) < count:
            map_id = 76 if key == GOLDENROD else 67 if len(rows) < 18 else 33
            rows.append((map_id, native_direction, [x, z], [x + dx, z + dz]))
            x += dx; z += dz
        if (x, z) != (target_x, target_z):
            raise ValueError("sealed D1 warm-up is inconsistent")
    return rows


def settle(action_id, map_id, x, z):
    return {"id": action_id, "op": "wait", "args": {"predicate": {
        "kind": "player-settled-at", "map": map_id, "x": x, "z": z,
        "when": "final"}}, "budget": {
            "maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 8}}


def goldenrod_actions(kind):
    short = kind == "spawn-work-budget-v1"
    if kind not in ("spawn-work-budget-v1", "unmounted-zero-stutter-v1"):
        raise ValueError("unknown D1 measurement")
    actions = []
    if short:
        actions.append({"id": "route-before-seam-idle", "op": "step",
            "args": {"frames": 36, "keys": []}, "budget": {
                "maxSeconds": 10, "maxFrames": 36, "noProgressFrames": 36}})
    points = [("DOWN", 38, 358, 385)]
    for _ in range(2 if short else 21):
        points.extend((("DOWN", 38, 358, 399), ("LEFT", 38, 356, 399),
                       ("UP", 38, 356, 385), ("RIGHT", 38, 358, 385)))
    for index, (key, map_id, x, z) in enumerate(points, 1):
        action_id = f"route-{index:03d}"
        if not short and index >= 42 and (index - 42) % 4 == 0:
            # Leave the measured Rattata road tile before every remaining lap.
            # Normal input keeps the first ten laps and all later route IDs.
            detour_id = action_id + "-detour-east"
            actions.append({"id": detour_id, "op": "step", "args": {
                "frames": 16, "keys": ["RIGHT"], "until": {
                    "kind": "player-field", "path": "x", "operator": "eq",
                    "value": 359, "when": "final"}}, "budget": {
                        "maxSeconds": 10, "maxFrames": 16, "noProgressFrames": 16}})
            actions.append(settle(detour_id + "-settle", map_id, 359, 385))
            x = 359
        actions.append({"id": action_id, "op": "step", "args": {
            "frames": 256, "keys": [key], "until": {
                "kind": "player-field", "path": "y" if key in ("UP", "DOWN") else "x",
                "operator": "eq", "value": z if key in ("UP", "DOWN") else x,
                "when": "final"}}, "budget": {
                    "maxSeconds": 90, "maxFrames": 256, "noProgressFrames": 32}})
        actions.append(settle(action_id + "-settle", map_id, x, z))
    actions.append({"id": "finish-natural-entry" if short else "complete-zero-stutter-window",
        "op": "wait", "args": {"predicate": {
            "kind": "measurement-stage" if short else "measurement-complete",
            "measurement": kind, **({"stage": "complete"} if short else {}),
            "when": "final"}}, "budget": {
                "maxSeconds": 60 if short else 15,
                "maxFrames": 256 if short else 80,
                "noProgressFrames": 32 if short else 80}})
    return actions


def cherrygrove_actions(kind):
    """Retain the original sealed recipe for replay and fixture controls."""
    short = kind == "spawn-work-budget-v1"
    points = [("route-up", "UP", 33, 585, 398, 64),
              ("route-left-city", "LEFT", 67, 565, 398, 128),
              ("route-up-city", "UP", 67, 565, 393, 64),
              ("route-left-window", "LEFT", 67, 543, 393, 128),
              ("route-down-window", "DOWN", 67, 543, 402, 64)]
    if not short:
        for _ in range(14):
            points.extend((("", "RIGHT", 67, 555, 402, 256),
                           ("", "UP", 67, 555, 393, 256),
                           ("", "LEFT", 67, 543, 393, 256),
                           ("", "DOWN", 67, 543, 402, 256)))
        points.extend((("", "RIGHT", 67, 555, 402, 256),
                       ("", "UP", 67, 555, 393, 256)))
    actions = []
    for index, (name, key, map_id, x, z, frames) in enumerate(points, 1):
        action_id = name if short else f"route-{index:03d}"
        frames = frames if short else 256
        actions.append({"id": action_id, "op": "step", "args": {
            "frames": frames, "keys": [key], "until": {
                "kind": "player-field", "path": "y" if key in ("UP", "DOWN") else "x",
                "operator": "eq", "value": z if key in ("UP", "DOWN") else x,
                "when": "final"}}, "budget": {
                    "maxSeconds": (30 if frames == 64 else 50) if short else 90,
                    "maxFrames": frames, "noProgressFrames": 32}})
        actions.append(settle(action_id + "-settle", map_id, x, z))
        if short and index == 1:
            actions.append({"id": "route-up-scan-idle", "op": "step",
                "args": {"frames": 36, "keys": []}, "budget": {
                    "maxSeconds": 10, "maxFrames": 36, "noProgressFrames": 36}})
    actions.append(goldenrod_actions(kind)[-1])
    return actions


def route35_actions(kind):
    if kind != "spawn-work-budget-v1":
        raise ValueError("Route35 is only a reviewed short D1 route")
    actions = []
    # A real gate warp replaces the field. Bind no prior engine handle after it.
    # Release UP at its exact admission, before the arrival Field can consume
    # another step. Split the same160-frame/45-second gate allowance.
    actions.append({"id":"route35-gate", "op":"step", "args":{
        "frames":16,"keys":["UP"],"until":{"kind":"player-step-count",
        "operator":"eq","value":51,"when":"final"}},"budget":{
        "maxSeconds":10,"maxFrames":16,"noProgressFrames":16}})
    actions.append({"id":"route35-arrival", "op":"wait", "args":{
        "predicate":{"kind":"player-settled-at","map":39,"x":358,"z":316,"when":"final"}},
        "budget":{"maxSeconds":35,"maxFrames":144,"noProgressFrames":96}})
    actions.append({"id":"route35-current-follower","op":"wait","args":{
        "predicate":{"kind":"follower-settled","species":56,"partySlot":2,"when":"final"}},
        "budget":{"maxSeconds":30,"maxFrames":64,"noProgressFrames":64}})
    # Keep the natural bird Signpost in range while ordinary Land/Surf
    # candidates stay absent. Never step back onto the gate warp row316.
    points=[("route35-001","UP",358,315)]
    for lap in range(1,9):
        points.extend(((f"route35-lap{lap}-east","RIGHT",360,315),
                       (f"route35-lap{lap}-north","UP",360,314),
                       (f"route35-lap{lap}-west","LEFT",358,314),
                       (f"route35-lap{lap}-south","DOWN",358,315)))
    for aid,key,x,z in points:
        actions.append({"id":aid,"op":"step","args":{"frames":128,"keys":[key],
            "until":{"kind":"player-field","path":"y" if key in ("UP","DOWN") else "x",
                     "operator":"eq","value":z if key in ("UP","DOWN") else x,"when":"final"}},
            "budget":{"maxSeconds":30,"maxFrames":128,"noProgressFrames":32}})
        actions.append(settle(aid+"-settle",39,x,z))
    actions.append(goldenrod_actions(kind)[-1])
    return actions

"""One bounded route for the retained fixed/per-tile Teleport matrix."""

from tools.overworld.devtools_mounted_teleport_matrix import (
    CASES, DIRECTIONS, KIND, configuration,
)


KEYS = {16: "RIGHT", 32: "LEFT", 64: "UP", 128: "DOWN"}


def _stage(name):
    return {"kind": "measurement-stage", "measurement": KIND,
            "stage": name, "when": "final"}


def route(subject):
    actions = []
    for index, name in enumerate(CASES):
        config = configuration(index)
        actions.append(("mount-teleport.configure", {"subject": subject, **config}))
        actions.append(("step", {"frames": 8, "keys": [KEYS[DIRECTIONS[index][0]]],
                                 "until": _stage("case-started")}))
        actions.append(("wait", {"predicate": _stage("case-complete")}))
    return actions


def validate_recipe(value, measurement):
    if measurement != {"kind": KIND, "subject": "cyndaquil"}:
        raise ValueError("Teleport matrix measurement shape differs")
    if value["mode"] != "prepared" \
            or value["subjects"] != [{"id": "cyndaquil", "species": 155,
                                      "role": "MOUNTED", "acquire": "existing"}] \
            or value["budgets"]["maxFrames"] > 800:
        raise ValueError("Teleport matrix requires one mounted Cyndaquil and at most 800 frames")
    expected_setup = [
        ("teleport", {"map": 33, "x": 588, "z": 406, "facing": 3}),
        ("party", {"slot": 0, "species": 155, "level": 10, "hp": 1, "status": 0}),
        ("spawn", {"species": 155, "form": 0, "role": "mounted", "slot": 0,
                   "level": 5}),
        ("step", {"frames": 16, "keys": []}),
        ("bind", {"subject": "cyndaquil"}),
    ]
    for phase, expected in (("setup", expected_setup),
                            ("actions", route("cyndaquil"))):
        actual = [(action["op"], action["args"]) for action in value[phase]]
        if actual != expected:
            raise ValueError("Teleport matrix fixed " + phase + " route differs")
    if value["assertions"] != [
            {"kind": "measurement-complete", "measurement": KIND, "when": "final"}]:
        raise ValueError("Teleport matrix requires its complete terminal measurement")

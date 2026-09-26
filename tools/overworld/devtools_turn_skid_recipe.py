"""One fixed cardinal turn-skid route over the existing Walk reader."""

from tools.overworld.devtools_turn_skid_measurement import KIND, REQUIREMENT


def _stage(name):
    return {"kind": "measurement-stage", "measurement": KIND,
            "stage": name, "when": "final"}


def validate_recipe(value, measurement):
    subject = "cyndaquil"
    if measurement != {"kind": KIND, "subject": subject} \
            or value["mode"] != "prepared" \
            or value["fixture"] != {"rom": "test.nds", "save": "test.sav"} \
            or value["requirements"] != [REQUIREMENT] \
            or value["budgets"] != {"maxSeconds": 180, "maxFrames": 221,
                                     "noProgressFrames": 64, "minObservedFrames": 102} \
            or value["subjects"] != [{"id": subject, "species": 155,
                                       "role": "MOUNTED", "acquire": "existing"}]:
        raise ValueError("turn-skid exact fixture, subject or bounds differ")
    expected = {
        "setup": [
            ("teleport", {"map": 67, "x": 543, "z": 402, "facing": 3}),
            ("party", {"slot": 0, "species": 155, "level": 10, "hp": 1, "status": 0}),
            ("spawn", {"species": 155, "form": 0, "role": "mounted",
                       "slot": 0, "level": 10}),
            ("step", {"frames": 16, "keys": []}),
            ("bind", {"subject": subject}),
            ("mount-walk.configure", {"subject": subject, "directionMode": 0}),
        ],
        "actions": [
            ("walk-matrix.arm", {"subject": subject}),
            ("stomp.arm", {"subject": subject}),
            ("step", {"frames": 96, "keys": ["RIGHT"],
                      "until": _stage("acceleration-complete")}),
            ("step", {"frames": 48, "keys": ["LEFT"],
                      "until": _stage("recovery-started")}),
            ("step", {"frames": 16, "keys": [],
                      "until": _stage("complete")}),
            ("stomp.close", {}),
            ("walk-matrix.close", {}),
        ],
    }
    for phase, route in expected.items():
        if [(action["op"], action["args"]) for action in value[phase]] != route \
                or any("skipIf" in action for action in value[phase]):
            raise ValueError("turn-skid fixed " + phase + " route differs")
    if value["assertions"] != [
            {"kind": "measurement-complete", "measurement": KIND, "when": "final"}]:
        raise ValueError("turn-skid requires its complete terminal measurement")

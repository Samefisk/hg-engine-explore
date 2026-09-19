"""One fixed natural Wild actor to battle-request route."""

from tools.overworld.devtools_wild_battle_handoff_measurement import KIND, REQUIREMENT


def _stage(name):
    return {"kind": "measurement-stage", "measurement": KIND,
            "stage": name, "when": "final"}


def validate_recipe(value, measurement):
    subject = "rattata"
    if measurement != {"kind": KIND, "subject": subject} \
            or value["mode"] != "prepared" \
            or value["fixture"] != {"rom": "test.nds", "save": "test.sav"} \
            or value["requirements"] != [REQUIREMENT] \
            or value["budgets"] != {"maxSeconds": 180, "maxFrames": 600,
                                     "noProgressFrames": 120, "minObservedFrames": 12} \
            or value["subjects"] != [{"id": subject, "species": 19,
                                       "role": "WILD", "acquire": "spawn"}]:
        raise ValueError("Wild battle exact fixture, subject or bounds differ")
    expected = {
        "setup": [
            ("teleport", {"map": 33, "x": 585, "z": 408, "facing": 0}),
            ("spawn", {"species": 19, "form": 0, "role": "wild", "level": 5,
                       "x": 583, "z": 406}),
            ("wait", {"predicate": {"kind": "actor-count", "subject": subject,
                                      "motionPhase": "IDLE", "operator": "eq",
                                      "value": 1, "when": "final"}}),
            ("bind", {"subject": subject}),
        ],
        "actions": [
            ("wait", {"predicate": _stage("motion-started")}),
            ("step", {"frames": 32, "keys": ["UP"], "until":
                      {"kind": "player-settled-at", "map": 33,
                       "x": 585, "z": 404, "when": "final"}}),
            ("step", {"frames": 8, "keys": ["LEFT"], "until":
                      {"kind": "player-settled-at", "map": 33,
                       "x": 584, "z": 404, "when": "final"}}),
            ("step", {"frames": 8, "keys": []}),
            ("step", {"frames": 8, "keys": ["LEFT"], "until":
                      {"kind": "player-settled-at", "map": 33,
                       "x": 583, "z": 404, "when": "final"}}),
            ("wait", {"predicate": _stage("motion-complete")}),
            ("step", {"frames": 1, "keys": ["UP"]}),
            ("step", {"frames": 120, "keys": ["A"],
                      "until": _stage("request-complete")}),
        ],
    }
    for phase, route in expected.items():
        if [(action["op"], action["args"]) for action in value[phase]] != route \
                or any("skipIf" in action for action in value[phase]):
            raise ValueError("Wild battle fixed " + phase + " route differs")
    if value["assertions"] != [
            {"kind": "measurement-complete", "measurement": KIND, "when": "final"}]:
        raise ValueError("Wild battle requires its complete terminal measurement")

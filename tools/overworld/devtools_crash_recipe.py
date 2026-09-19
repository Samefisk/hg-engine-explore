"""The retained prepared Crash route, with a separate terminal reader control."""
from . import devtools_crash_test_support as support

KIND = support.KIND
CONTROL = "live-crash-control-v1"


def setup(subject):
    return [
        ("party", dict(slot=1, hp=21, status=0)),
        ("teleport", dict(map=33, x=577, z=397, facing=0)),
        ("spawn", dict(species=155, form=0, role="mounted", slot=1, level=5)),
        ("step", dict(frames=16, keys=[])),
        ("bind", dict(subject=subject)),
        ("mount-walk.configure", dict(subject=subject, directionMode=0,
                                      turning="locked", crashSound="wall-hit")),
    ]


def route(subject, kind):
    return [("crash.arm", dict(subject=subject)),
        ("step", dict(frames=1, keys=[])),
        ("step", dict(frames=16, keys=["UP"])),
        ("step", dict(frames=32, keys=[])),
        ("step", dict(frames=8, keys=["RIGHT"])),
        ("step", dict(frames=8, keys=[])),
        *([("crash.calibrate", {})] if kind == CONTROL else []),
        ("crash.close", {})]


def validate_crash_recipe(value, measurement):
    kind, subject = measurement.get("kind"), measurement.get("subject")
    control = kind == CONTROL
    if kind not in (KIND, CONTROL) or value["mode"] != ("observer-control" if control else "prepared"):
        raise ValueError("Crash recipe mode differs")
    support.validate_measurement(dict(measurement, kind=KIND), "prepared",
                                 value["budgets"]["maxFrames"], value["subjects"])
    if value["subjects"] != [dict(id=subject, species=155, role="MOUNTED", acquire="existing")] \
            or value["requirements"] != (["shared.crash-recorder-control-v1"] if control else [support.REQUIREMENT]) \
            or value["fixture"] != dict(rom="test.nds", save="test.sav"):
        raise ValueError("Crash exact fixture, subject or requirements differ")
    for phase, expected in (("setup", setup(subject)), ("actions", route(subject, kind))):
        if [(a["op"], a["args"]) for a in value[phase]] != expected \
                or any("skipIf" in a for a in value[phase]):
            raise ValueError("Crash fixed " + phase + " route differs")
    if value["assertions"] != [dict(kind="measurement-complete", measurement=kind, when="final")]:
        raise ValueError("Crash requires its complete terminal measurement")

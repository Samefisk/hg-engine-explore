"""Fixed Walk timing route. Recipes cannot shrink or reorder its witness."""
from tools.overworld.devtools_walk_matrix_contract import CASES

KIND = "mounted-frame-matrix-v1"
CONTROL = "live-walk-matrix-control-v1"


def route(subject, kind):
    """Return op/args pairs; budgets remain bounded by the shared validator."""
    def stage(name):
        return dict(kind="measurement-stage", measurement=kind, stage=name, when="final")

    def configure(case):
        return ("mount-walk.configure", dict(subject=subject,
                directionMode=case["mode"], travelTime=case["duration"]))

    cases = CASES[:2] if kind == CONTROL else CASES
    result = [("walk-matrix.arm", {"subject": subject})]
    for case in cases:
        if case["index"]:
            result.append(configure(case))
        if case["mode"] == 2:
            result += [("step", dict(frames=8, keys=["LEFT"], until=stage("gate-complete"))),
                       ("wait", dict(predicate=stage("gate-released")))]
        result += [("step", dict(frames=8, keys=list(case["keys"]), until=stage("case-started"))),
                   ("wait", dict(predicate=stage("case-complete")))]
        if case["direction"] >= 4:
            # Actor completion precedes the mounted adapter's pending field
            # step by one queue. Preserve that real neutral boundary; the next
            # zero-time configure still proves all adapter flags are clear.
            result.append(("step", dict(frames=1, keys=[])))
    if kind == CONTROL:
        result.append(("walk-matrix.calibrate", {}))
    result.append(("walk-matrix.close", {}))
    return result


def validate_matrix_recipe(value, measurement):
    kind, subject = measurement.get("kind"), measurement.get("subject")
    if set(measurement) != {"kind", "subject"} or kind not in (KIND, CONTROL):
        raise ValueError("matrix measurement shape differs")
    if value["mode"] != ("observer-control" if kind == CONTROL else "prepared") \
            or value["subjects"] != [dict(id=subject, species=155, role="MOUNTED", acquire="existing")] \
            or value["budgets"]["maxFrames"] > 4096:
        raise ValueError("matrix requires one mounted Cyndaquil and at most4096 frames")
    expected_setup = [
        ("teleport", dict(map=33, x=588, z=406, facing=3)),
        ("party", dict(slot=0, species=155, level=10, hp=1, status=0)),
        ("spawn", dict(species=155, form=0, role="mounted", slot=0, level=5)),
        ("bind", dict(subject=subject)),
        ("mount-walk.configure", dict(subject=subject, directionMode=0, travelTime=1)),
    ]
    for phase, expected in (("setup", expected_setup), ("actions", route(subject, kind))):
        if [(a["op"], a["args"]) for a in value[phase]] != expected:
            raise ValueError("matrix fixed " + phase + " route differs")
    if value["assertions"] != [dict(kind="measurement-complete", measurement=kind, when="final")]:
        raise ValueError("matrix requires its complete terminal measurement")

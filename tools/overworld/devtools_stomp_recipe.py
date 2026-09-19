"""Two fixed normal-input feedback cases, not a second timing matrix."""
KIND = "mounted-stomp-v1"
CONTROL = "live-stomp-control-v1"


def setup(subject):
    return [
        ("teleport", dict(map=33, x=588, z=406, facing=3)),
        ("party", dict(slot=0, species=155, level=10, hp=1, status=0)),
        ("spawn", dict(species=155, form=0, role="mounted", slot=0, level=5)),
        ("bind", dict(subject=subject)),
        ("mount-walk.configure", dict(subject=subject, directionMode=0, travelTime=2, stompTime=2)),
    ]


def route(subject, kind):
    def stage(name):
        return dict(kind="measurement-stage", measurement=kind, stage=name, when="final")
    result = [("stomp.arm", dict(subject=subject))]
    for index, key in enumerate(("LEFT", "RIGHT")):
        if index:
            result.append(("mount-walk.configure", dict(subject=subject, directionMode=0, travelTime=3, stompTime=2)))
        result += [
            ("step", dict(frames=8, keys=[key], until=stage("case-started"))),
            ("wait", dict(predicate=stage("case-complete"))),
        ]
    if kind == CONTROL:
        result.append(("stomp.calibrate", {}))
    result.append(("stomp.close", {}))
    return result


def validate_stomp_recipe(value, measurement):
    kind, subject = measurement.get("kind"), measurement.get("subject")
    if set(measurement) != {"kind", "subject"} or kind not in (KIND, CONTROL):
        raise ValueError("stomp measurement shape differs")
    if value["mode"] != ("observer-control" if kind == CONTROL else "prepared") \
            or value["subjects"] != [dict(id=subject, species=155, role="MOUNTED", acquire="existing")] \
            or value["budgets"]["maxFrames"] > 600:
        raise ValueError("stomp requires one mounted Cyndaquil and at most600 frames")
    for phase, expected in (("setup", setup(subject)), ("actions", route(subject, kind))):
        if [(a["op"], a["args"]) for a in value[phase]] != expected:
            raise ValueError("stomp fixed " + phase + " route differs")
    if value["assertions"] != [dict(kind="measurement-complete", measurement=kind, when="final")]:
        raise ValueError("stomp requires its complete terminal measurement")

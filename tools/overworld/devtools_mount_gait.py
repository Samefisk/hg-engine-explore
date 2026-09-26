"""Read and independently check mounted presentation; never advance the guest."""
from copy import deepcopy

STATE_ADDRESS = 0x01FFA500
MOUNT_ADDRESS = 0x023BC744
POSE_KEYS = ("x", "z", "velocityX", "velocityZ", "bodyY", "riderY", "leanX", "leanZ", "phase", "walking")


def read_gait(session, current):
    rt, emu = session.rt, session.emu
    def pose(address):
        result = {key: rt.signed(emu, address + index * 4) for index, key in enumerate(POSE_KEYS[:4])}
        result.update({key: rt.signed(emu, address + 16 + index * 2, 2)
                       for index, key in enumerate(POSE_KEYS[4:8])})
        result.update(phase=rt.unsigned(emu, address + 24, 2), walking=rt.unsigned(emu, address + 26, 1))
        return result
    mode = rt.unsigned(emu, MOUNT_ADDRESS + 0x67, 1)
    return dict(schemaVersion=1, address=STATE_ADDRESS,
        previous=pose(STATE_ADDRESS), pose=pose(STATE_ADDRESS + 28),
        stamp=rt.unsigned(emu, STATE_ADDRESS + 56),
        session=rt.unsigned(emu, STATE_ADDRESS + 60),
        owner=rt.unsigned(emu, STATE_ADDRESS + 64),
        initialized=rt.unsigned(emu, STATE_ADDRESS + 68, 1),
        input=dict(x=rt.signed(emu, current["playerPointer"] + 0x70),
            z=rt.signed(emu, current["playerPointer"] + 0x78),
            stamp=rt.unsigned(emu, 0x021D1138),
            session=rt.unsigned(emu, MOUNT_ADDRESS + 0x60), owner=current["playerPointer"],
            mode=1 if mode == 4 else 0 if mode == 0 else 2,
            options=rt.unsigned(emu, MOUNT_ADDRESS + 0x18, 1)))


def expected_pose(previous, input):
    """Integer reference from measured ground distance and authored controls."""
    def clamp(value, limit):
        return max(-limit, min(limit, value))
    def divide(value, divisor):
        return (1 if value >= 0 else -1) * (abs(value) // divisor)
    def follow(value, target, divisor):
        return target if abs(target - value) < 16 else value + divide(target - value, divisor)
    result = deepcopy(previous)
    dx, dz = input["x"] - previous["x"], input["z"] - previous["z"]
    result.update(x=input["x"], z=input["z"], walking=int(input["mode"] == 1))
    if input["mode"] == 2:
        return dict(zip(POSE_KEYS, (input["x"], input["z"], 0, 0, 0, 0, 0, 0, 0, 0)))
    if input["mode"] != 1 and not previous["walking"]:
        dx = dz = 0
    options = input["options"]
    amplitude, stride, settling, lean = options & 3, ((options >> 2) & 3) + 1, (options >> 4) & 3, options >> 6
    distance = max(abs(dx), abs(dz))
    result["phase"] = (previous["phase"] + min(distance // stride, 8192)) & 65535
    phase = result["phase"] >> 8
    target = phase * (256 - phase) * amplitude // 4 if distance else 0
    result["bodyY"] = previous["bodyY"] + clamp(target - previous["bodyY"], 1024)
    rider = follow(previous["riderY"], result["bodyY"], settling + 1)
    result["riderY"] = result["bodyY"] + clamp(rider - result["bodyY"], settling * 512)
    for axis, delta in (("X", dx), ("Z", dz)):
        target = clamp(divide(-(delta - previous["velocity" + axis]), 8), lean * 4096)
        key = "lean" + axis
        result[key] = previous[key] + clamp(target - previous[key], 512)
        result["velocity" + axis] = follow(previous["velocity" + axis], delta, 2)
    return result


def check_gait(data, *, required=False):
    gait = data.get("gait")
    if gait is None:
        if required:
            raise ValueError("mounted gait native observation is missing")
        return dict(bodyY=0, riderY=0, leanX=0, leanZ=0)
    if gait.get("schemaVersion") != 1 or gait.get("address") != STATE_ADDRESS:
        raise ValueError("mounted gait reader identity differs")
    input, pose, previous = gait["input"], gait["pose"], gait["previous"]
    if any(type(value.get(key)) is not int for value in (pose, previous) for key in POSE_KEYS) \
            or any(type(input.get(key)) is not int for key in ("x", "z", "stamp", "session", "owner", "mode", "options")):
        raise ValueError("mounted gait observation fields are missing")
    if gait.get("initialized") != 1 or any(gait.get(key) != input[key] for key in ("stamp", "session", "owner")) \
            or input["owner"] != data["playerPointer"] \
            or input["x"] != data["player"]["pos_x"] or input["z"] != data["player"]["pos_z"]:
        raise ValueError("mounted gait input, state, or owner differs")
    if pose != expected_pose(previous, input):
        raise ValueError("mounted gait differs from distance and frame reference")
    return pose


def normalized_pair(data):
    """Remove only exactly checked gait offsets before existing seat checks."""
    pose = check_gait(data)
    result = deepcopy(data)
    result["player"]["unk88_y"] -= pose["riderY"]
    result["mount"]["unk88_y"] -= pose["bodyY"]
    result["player"]["face_x"] -= pose["leanX"]
    result["player"]["face_z"] -= pose["leanZ"]
    return result


def check_ground_camera(frame, previous=None):
    """Stock camera runs before the task queue; compare its real prior target."""
    camera, pair = frame["camera"], frame["pair"]
    if camera.get("targetPointer") != pair["playerPointer"] + 0x70 \
            or any(not isinstance(camera.get(key), list) or len(camera[key]) != 3
                   or any(type(value) is not int for value in camera[key])
                   for key in ("lastTarget", "lookAtTarget")):
        raise ValueError("mounted gait actual camera target is missing")
    if previous is None:
        return
    before = previous["camera"]
    if any(camera["lastTarget"][axis] != previous["pair"]["player"]["pos_" + key]
           for axis, key in ((0, "x"), (2, "z"))) \
            or camera["lastTarget"][1] != before["lastTarget"][1] \
            or any(camera["lookAtTarget"][axis] - camera["lastTarget"][axis]
                   != before["lookAtTarget"][axis] - before["lastTarget"][axis]
                   for axis in range(3)):
        raise ValueError("mounted gait moved or shook the actual ground camera")

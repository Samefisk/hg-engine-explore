"""Read and independently check mounted presentation; never advance the guest."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_observer import NativeObservationError

STATE_ADDRESS = 0x01FFA500
STATE_BYTES = 72
MOUNT_ADDRESS = 0x023BC744
MOUNT_SESSION_OFFSET = 0x68
MOUNT_MODE_OFFSET = 0x6F
POSE_KEYS = ("x", "z", "velocityX", "velocityZ", "bodyY", "riderY", "leanX", "leanZ", "phase", "walking")


def authenticate_gait(session):
    """Seal resident code/state layout once for this exact session and ROM."""
    from scripts.verify_pokemon_move_history_capture import elf_bytes_at, elf_section_layout

    owner = (id(session), session.emu, session.rom_hash)
    if session.emu is None:
        raise NativeObservationError("mounted gait session is closed")
    cached = getattr(session, "_mounted_gait_identity", None)
    if (cached is not None and cached[0][0] == owner[0]
            and cached[0][1] is owner[1] and cached[0][2] == owner[2]):
        return deepcopy(cached[1])
    linked = session.rt.REPO / "build/overworld_mount_chain_overlay_linked.o"
    sections = elf_section_layout(linked)
    identity = {}
    for name, address, limit in (("gait", 0x01FF9D00, 0x01FFA100),
                                 ("presentation", 0x01FFA100, STATE_ADDRESS)):
        matches = [row for row in sections if row[2] == address]
        if (len(matches) != 1 or matches[0][0] != 1 or not matches[0][1] & 4
                or not 0 < matches[0][3] <= limit - address):
            raise NativeObservationError("mounted " + name + " code host differs")
        size = matches[0][3]
        expected = elf_bytes_at(linked, address, size)
        # GCC10's sealed Apply entry reads these current Mount fields. Older
        # profile layouts used +60/+67; do not read those bytes as gait input.
        if name == "gait" and any(expected[offset:offset + 2] != instruction
                for offset, instruction in ((0x12, b"\x83\x6e"),
                                             (0x1A, b"\x6f\x33"),
                                             (0x1C, b"\x1b\x78"),
                                             (0x32, b"\x03\x7e"))):
            raise NativeObservationError("mounted gait input layout differs")
        if len(expected) != size or session.packaged_code(address, size) != expected:
            raise NativeObservationError("mounted " + name + " linked/package code differs")
        if session.rt.actor_memory_read(session.emu, address, size) != expected:
            raise NativeObservationError("mounted " + name + " loaded code differs")
        identity[name] = dict(address=address, size=size,
                              sha256=hashlib.sha256(expected).hexdigest())
    state = [row for row in sections if row[2] == STATE_ADDRESS]
    if (len(state) != 1 or state[0][0] != 1 or state[0][1] & 3 != 3
            or not STATE_BYTES <= state[0][3] <= 128):
        raise NativeObservationError("mounted gait state layout differs")
    identity["state"] = dict(address=STATE_ADDRESS, size=STATE_BYTES)
    session._mounted_gait_identity = (owner, deepcopy(identity))
    return identity


def read_gait(session, current):
    rt, emu = session.rt, session.emu
    pointer = current.get("playerPointer")
    if (type(pointer) is not int or pointer % 4
            or not 0x02000000 <= pointer <= 0x02400000 - 0x12C):
        raise NativeObservationError("mounted gait player pointer differs")
    authenticate_gait(session)
    raw = rt.actor_memory_read(emu, STATE_ADDRESS, STATE_BYTES)
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != STATE_BYTES:
        raise NativeObservationError("mounted gait state read is incomplete")
    def pose(offset):
        return dict(zip(POSE_KEYS, struct.unpack_from("<4i4hHB", raw, offset)))
    stamp, generation, owner, initialized = struct.unpack_from("<3IB", raw, 56)
    mode = rt.unsigned(emu, MOUNT_ADDRESS + MOUNT_MODE_OFFSET, 1)
    return dict(schemaVersion=1, address=STATE_ADDRESS,
        previous=pose(0), pose=pose(28),
        stamp=stamp, session=generation, owner=owner, initialized=initialized,
        input=dict(x=rt.signed(emu, current["playerPointer"] + 0x70),
            z=rt.signed(emu, current["playerPointer"] + 0x78),
            stamp=rt.unsigned(emu, 0x021D1138),
            session=rt.unsigned(emu, MOUNT_ADDRESS + MOUNT_SESSION_OFFSET), owner=current["playerPointer"],
            mode=1 if mode == 4 else 0 if mode == 0 else 2,
            options=rt.unsigned(emu, MOUNT_ADDRESS + 0x18, 1)))


def read_gait_pair(session, current, *, player=None, mount=None):
    """Collect actual pair/state bytes only; consumers judge the guest pose."""
    value = dict(playerPointer=current["playerPointer"], mountPointer=current["mountPointer"])
    for name, supplied in (("player", player), ("mount", mount)):
        pointer = value[name + "Pointer"]
        if (type(pointer) is not int or pointer % 4
                or not 0x02000000 <= pointer <= 0x02400000 - 0x12C):
            raise NativeObservationError("mounted gait " + name + " pointer differs")
    value["gait"] = read_gait(session, current)
    for name, supplied in (("player", player), ("mount", mount)):
        pointer = value[name + "Pointer"]
        value[name] = deepcopy(supplied if supplied is not None else
                               session.rt.object_state(session.emu, pointer))
        value[name].update(unk88_z=session.rt.signed(session.emu, pointer + 0x90),
                           unk94_z=session.rt.signed(session.emu, pointer + 0x9C))
    return value


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

"""Paused-guest calibration of the exact mounted pair reader; not gameplay proof."""
from copy import deepcopy


class MountedPoseControlError(RuntimeError):
    code = "mounted-pose-control-invalid"


def _read_calibration_pose(reader, current):
    """Bind a paused read to its checked queue sample, never to the state stamp.

    Stock NitroMain can increment vblankCounter at its two waits after the main
    queue. No gait callback runs there. Only this paused memory control may use
    the completed input; ordinary callback/completed readers remain exact.
    """
    from tools.overworld.devtools_mount_gait import check_gait
    raw = reader._read_pose(current)
    # Keep the unmodified failing read, including its native clock, for diagnosis.
    reader.pose_calibration["latestRawPose"] = deepcopy(raw)
    gait = raw.get("gait")
    if gait is None:
        return raw
    completed = reader.latest_completed_pose
    if completed is None and gait["input"]["stamp"] == gait["stamp"]:
        return raw
    clock = dict(reader.observer._clock(), frame=reader.session.completed_frames)
    if (not completed or completed.get("boundary") != "main-task-queue-completion"
            or clock["frame"] != completed["frame"]
            or clock["actorFrame"] != completed["actorFrame"]
            or clock["nativeCycle"] < completed["nativeCycle"]):
        raise MountedPoseControlError("paused gait read has no matching completed queue sample")
    check_gait(completed, required=True)
    queued = completed["gait"]
    advance = (gait["input"]["stamp"] - queued["input"]["stamp"]) & 0xFFFFFFFF
    bound = deepcopy(raw)
    bound["gait"]["input"]["stamp"] = queued["input"]["stamp"]
    if (advance not in (0, 1, 2) or bound["gait"] != queued
            or any(raw.get(k) != completed.get(k) for k in (
                "subject", "publicSubject", "sourceIdentity", "engineIdentity",
                "worldContext", "playerPointer", "mountPointer", "avatarPointer"))):
        raise MountedPoseControlError("paused gait differs from completed capsule or inputs")
    if advance == 0:
        return raw
    bound["pausedGaitClock"] = dict(completedStamp=queued["input"]["stamp"],
        nativeStamp=gait["input"]["stamp"], completedFrame=completed["frame"],
        completedActorFrame=completed["actorFrame"], completedNativeCycle=completed["nativeCycle"],
        pausedNativeCycle=clock["nativeCycle"])
    return bound


def _calibrate_gait_offset(reader, checker, clean):
    """Perturb one actual presentation byte; do not run guest instructions."""
    s = reader.session
    address = clean["mountPointer"] + 0x8C
    original = s.read(address, 2)
    value = int.from_bytes(original, "little", signed=True)
    if value == 32767 or value != clean["mount"]["unk88_y"]:
        raise MountedPoseControlError("mounted gait offset is not a checked two-byte value")
    changed = (value + 1).to_bytes(2, "little", signed=True)
    before_clock = dict(reader.observer._clock(), frame=s.completed_frames)
    result = dict(address=address, originalHex=original.hex(), changedHex=changed.hex(),
                  clean=deepcopy(clean), clock=before_clock, restored=None)
    try:
        s.write(address, changed)
        bad = _read_calibration_pose(reader, reader._current())
        expected = deepcopy(clean)
        expected["mount"]["unk88_y"] += 1
        if bad != expected or s.read(address, 2) != changed:
            raise MountedPoseControlError("same gait reader did not observe only the changed offset")
        result["bad"] = bad
        try:
            rejected = checker(bad) is False
        except ValueError:
            rejected = True
        if not rejected:
            raise MountedPoseControlError("gait checker accepted the native offset fault")
    finally:
        try:
            s.write(address, original)
            restored = _read_calibration_pose(reader, reader._current())
            after_clock = dict(reader.observer._clock(), frame=s.completed_frames)
            if restored != clean or checker(restored) is not True \
                    or s.read(address, 2) != original or before_clock != after_clock:
                raise MountedPoseControlError("mounted gait offset restoration differs")
            result.update(restored=restored, restoredClock=after_clock)
        except Exception as error:
            s.abort_native_control(MountedPoseControlError(str(error)))
            raise
    return result


def calibrate_mounted_pose(reader, *, checker=None):
    if checker is None:
        from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
        checker = check_pair_pose
    s = reader.session
    if getattr(reader, "pose_calibration", None) is not None:
        raise MountedPoseControlError("mounted pose calibration is single-use")
    if (not reader.armed or reader.closed or reader.failure is not None
            or s.emu is None or s.native_bridge_active
            or not s.rom.resolve().is_relative_to(s.directory.resolve())
            or s.rom.resolve() == (s.rt.REPO / "test.nds").resolve()):
        raise MountedPoseControlError("mounted pose calibration requires an armed owned paused session")
    receipt = dict(state="checking", failure=None, cleanupPending=False,
        acceptedProof=False, scope="observer-control-only; no gameplay claim",
        guestInstructionAdvance=0, clean=None, bad=None, restored=None)
    reader.pose_calibration = receipt
    registers = s.emu.memory.register_arm9
    def register_state():
        return {name: getattr(registers, name) for name in
                (*("r" + str(i) for i in range(16)), "cpsr", "spsr")}
    def clock():
        return dict(reader.observer._clock(), frame=s.completed_frames)
    try:
        current = reader._current()
        initial_clock, initial_registers = clock(), register_state()
        clean = _read_calibration_pose(reader, current)
        receipt.update(clean=clean, clock=initial_clock, registers=initial_registers)
        address = current["mountPointer"] + 0x70
        original = s.read(address, 4)
        if len(original) != 4 or int.from_bytes(original, "little", signed=True) != clean["mount"]["pos_x"]:
            raise MountedPoseControlError("mounted pose native bytes differ from reader")
        if checker(clean) is not True:
            raise MountedPoseControlError("clean mounted pair failed the unchanged checker")
        value = int.from_bytes(original, "little", signed=True)
        if value == 0x7FFFFFFF:
            raise MountedPoseControlError("mounted pose control would overflow")
        corrupted = (value + 1).to_bytes(4, "little", signed=True)
        receipt.update(clean=clean, clock=initial_clock, registers=initial_registers,
                       poseAddress=address, originalHex=original.hex(), changedHex=corrupted.hex())
        receipt["cleanupPending"] = True
        try:
            s.write(address, corrupted)
            bad = _read_calibration_pose(reader, reader._current())
            receipt["bad"] = bad
            expected = deepcopy(clean)
            expected["mount"]["pos_x"] += 1
            if bad != expected or s.read(address, 4) != corrupted:
                raise MountedPoseControlError("same mounted reader did not observe only the changed position")
            try:
                rejected = checker(bad) is False
            except ValueError:
                rejected = True
            if not rejected:
                raise MountedPoseControlError("unchanged pair checker accepted the bad position")
        finally:
            # Restore the exact allocation even if identity or the bad read failed.
            # Any restore/clock/identity failure must stop this private core.
            try:
                s.write(address, original)
                if s.read(address, 4) != original:
                    raise MountedPoseControlError("mounted pose restore bytes differ")
                restored_current = reader._current()
                restored = _read_calibration_pose(reader, restored_current)
                receipt.update(restored=restored, restoredClock=clock(), restoredRegisters=register_state())
                if restored_current != current or restored != clean or checker(restored) is not True:
                    raise MountedPoseControlError("mounted pose restored reader or owner differs")
                if clock() != initial_clock or receipt["restoredRegisters"] != initial_registers:
                    raise MountedPoseControlError("mounted pose control crossed native execution boundary")
                receipt["cleanupPending"] = False
            except Exception as error:
                receipt.update(state="failed", failure=str(error))
                s.abort_native_control(MountedPoseControlError(str(error)))
                raise MountedPoseControlError(str(error)) from error
        if clean.get("gait") is not None:
            receipt["gaitOffsetControl"] = _calibrate_gait_offset(reader, checker, clean)
        receipt["state"] = "complete"
        return deepcopy(receipt)
    except Exception as error:
        receipt.update(state="failed", failure=str(error))
        raise

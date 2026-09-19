"""Paused-guest calibration of the exact mounted pair reader; not gameplay proof."""
from copy import deepcopy


class MountedPoseControlError(RuntimeError):
    code = "mounted-pose-control-invalid"


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
        clean = reader._read_pose(current)
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
            bad = reader._read_pose(reader._current())
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
                restored = reader._read_pose(restored_current)
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
        receipt["state"] = "complete"
        return deepcopy(receipt)
    except Exception as error:
        receipt.update(state="failed", failure=str(error))
        raise

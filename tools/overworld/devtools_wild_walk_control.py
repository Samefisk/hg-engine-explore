"""Paused, exactly restored fault for the Wild clear-state reader only."""
from copy import deepcopy


class WildWalkControlError(RuntimeError):
    code = "wild-walk-control-invalid"


def calibrate_wild_walk_clear(reader, *, checker=None):
    if checker is None:
        from tools.overworld.devtools_wild_walk_observer import check_cleared_state
        checker = check_cleared_state
    s = reader.session
    if (getattr(reader, "clear_calibration", None) is not None or not reader.armed
            or reader.closed or reader.failure is not None or s.emu is None
            or s.native_bridge_active or not reader.result().get("latestClear")
            or not s.rom.resolve().is_relative_to(s.directory.resolve())
            or s.rom.resolve() == (s.rt.REPO / "test.nds").resolve()):
        raise WildWalkControlError("Wild clear calibration requires an owned paused reader after a real clear")
    receipt = dict(state="checking", failure=None, cleanupPending=False,
                   acceptedProof=False, guestInstructionAdvance=0,
                   scope="observer-control-only; no natural movement proof")
    reader.clear_calibration = receipt
    registers = s.emu.memory.register_arm9

    def register_state():
        return {k: getattr(registers, k) for k in
                (*("r" + str(i) for i in range(16)), "cpsr", "spsr")}

    def clock():
        return dict(reader.observer._clock(), frame=s.completed_frames)

    try:
        current = reader._current()
        clean = reader._read_clear_state(current)
        # A prior no-op clear or another owner's receipt cannot calibrate this
        # Walk boundary. The native before/after pair must show a real clear.
        prior = reader.result()["latestClear"]
        before, after = prior.get("before", {}), prior.get("after", {})
        if (prior.get("subject") != reader.subject or before.get("active") != 1
                or before.get("mode") != 1 or checker(after) is not True
                or any(after.get("current", {}).get(k) != current.get(k) for k in
                       ("subject", "sourceIdentity", "engineIdentity", "worldContext",
                        "statePointer", "runtimePointer", "objectPointer", "slot"))):
            raise WildWalkControlError("Wild calibration lacks a matching real Walk clear")
        if checker(clean) is not True:
            raise WildWalkControlError("current Wild state is not cleared")
        address = current["runtimePointer"] + 0xA + reader.subject["handle"]["slot"]
        original = s.read(address, 1)
        if original != b"\0" or clean["active"] != 0:
            raise WildWalkControlError("Wild active byte differs from the reader")
        original_clock, original_registers = clock(), register_state()
        receipt.update(clean=clean, stateAddress=address, originalHex=original.hex(),
                       changedHex="01", clock=original_clock, registers=original_registers,
                       cleanupPending=True)
        try:
            s.write(address, b"\1")
            bad = reader._read_clear_state(reader._current())
            receipt["bad"] = bad
            expected = deepcopy(clean);expected["active"] = 1
            if bad != expected or s.read(address, 1) != b"\1":
                raise WildWalkControlError("Wild reader did not observe only the active-byte fault")
            try:
                rejected = checker(bad) is False
            except ValueError:
                rejected = True
            if not rejected:
                raise WildWalkControlError("unchanged Wild checker accepted uncleared state")
        finally:
            try:
                s.write(address, original)
                restored_current = reader._current()
                restored = reader._read_clear_state(restored_current)
                receipt.update(restored=restored, restoredClock=clock(), restoredRegisters=register_state())
                if (s.read(address, 1) != original or restored_current != current
                        or restored != clean or checker(restored) is not True
                        or receipt["restoredClock"] != original_clock
                        or receipt["restoredRegisters"] != original_registers):
                    raise WildWalkControlError("Wild clear restoration or execution boundary differs")
                receipt["cleanupPending"] = False
            except Exception as error:
                receipt.update(state="failed", failure=str(error))
                s.abort_native_control(WildWalkControlError(str(error)))
                raise WildWalkControlError(str(error)) from error
        receipt["state"] = "complete"
        return deepcopy(receipt)
    except Exception as error:
        receipt.update(state="failed", failure=str(error))
        raise

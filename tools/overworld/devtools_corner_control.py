"""Exactly restored corner policy-reader control; not collision/gameplay proof."""
from copy import deepcopy

from tools.overworld.devtools_corner_observer import check_corner_policy
from tools.overworld.devtools_mount_walk_fixture import STATE_BYTES


class CornerControlError(RuntimeError):
    code = "corner-policy-control-invalid"


def require(ok, message):
    if not ok:
        raise CornerControlError(message)


def calibrate_corner_policy(reader, *, checker=None):
    """Change one native lane byte with the CPU stopped, then close the reader.

    No code, return register, collision mask, or semantic event is fabricated.
    All observations use the native corner reader's existing memory path.
    """
    checker = checker or check_corner_policy
    s = reader.session
    require(reader.policy_calibration is None and reader.armed and not reader.closed
            and reader.failure is None and s.emu is not None and s.prepared
            and not s.native_bridge_active and not reader.active_strict and not reader.data
            and bool(reader.receipts) and reader.receipts[-1].get("normalReturn") is True
            and s.rom.resolve().is_relative_to(s.directory.resolve())
            and s.rom.resolve() != (s.rt.REPO / "test.nds").resolve(),
            "corner calibration requires an owned paused reader after a real strict call")
    receipt = dict(state="checking", failure=None, cleanupPending=False, acceptedProof=False,
                   guestInstructionAdvance=0, guestMemoryWrites=0,
                   scope="observer-control-only; corner policy reader, not collision or gameplay proof")
    reader.policy_calibration = receipt
    registers = s.emu.memory.register_arm9

    def register_state():
        return {key: getattr(registers, key) for key in
                (*("r"+str(i) for i in range(16)), "cpsr", "spsr")}

    def clock():
        return dict(reader.observer._clock(), frame=s.completed_frames)

    def capture():
        reader._live_code()
        current = reader._current()
        return dict(current=current, mountBinding=reader._mount_binding(current),
                    policy=reader._read_policy(current),
                    mountStateHex=s.read(reader.mount_state, STATE_BYTES).hex(),
                    input=deepcopy(s._selector_observation()),
                    player=s.rt.object_state(s.emu,current["playerPointer"]),
                    mount=s.rt.object_state(s.emu,current["mountPointer"]))

    try:
        clean = capture()
        completed = reader.latest_completed
        require(isinstance(completed, dict) and completed.get("frame") == s.completed_frames
                and completed.get("current") == clean["current"]
                and completed.get("actorFrame") == clock()["actorFrame"]
                and completed.get("nativeCycle") <= clock()["nativeCycle"],
                "corner calibration is not at its completed observation boundary")
        actor = clean["current"]["publicSubject"]
        require(actor.get("species") == 155 and actor.get("role") == "MOUNTED"
                and actor.get("motionPhase") == "IDLE" and actor.get("motionKind") == "NONE"
                and actor.get("reservationId") == 0 and actor.get("inputOwnership") == 1,
                "corner calibration requires idle mounted Cyndaquil")
        require(all(type(clean["input"].get(k)) is int and clean["input"][k] == 0
                    for k in ("heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys")),
                "corner calibration requires released normal input")
        prior = reader.receipts[-1]
        require(prior["completedFrame"] < s.completed_frames
                and all(prior["before"][k] == clean["current"][k] for k in
                        ("subject", "sourceIdentity", "engineIdentity", "worldContext",
                         "playerPointer", "mountPointer", "avatarPointer"))
                and prior["mountBinding"] == clean["mountBinding"]
                and prior["profileHex"] == clean["policy"]["profileHex"],
                "corner calibration lacks matching completed native strict evidence")
        require(checker(clean["policy"]) is True, "clean corner policy failed unchanged checker")
        original_state = bytes.fromhex(clean["mountStateHex"])
        require(len(original_state) == STATE_BYTES and original_state[8:80].hex() == clean["policy"]["profileHex"],
                "corner full state differs from the same reader")
        address = reader.mount_state + 27
        original = original_state[27:28]
        initial_clock, initial_registers = clock(), register_state()
        receipt.update(clean=clean, clock=initial_clock, registers=initial_registers,
                       stateAddress=reader.mount_state, stateBytes=STATE_BYTES, policyAddress=reader.mount_state+8,
                       changedOffset=19, changedAddress=address, originalHex=original.hex(), changedHex="00",
                       strictReceipt=deepcopy(prior), cleanupPending=True)
        expected = deepcopy(clean)
        changed_state = bytearray(original_state); changed_state[27] = 0
        expected["mountStateHex"] = changed_state.hex()
        expected["policy"] = dict(profileHex=changed_state[8:80].hex(), profile19=0)
        try:
            receipt["guestMemoryWrites"] += 1
            s.write(address, b"\0")
            bad = capture()
            receipt["bad"] = bad
            require(bad == expected and s.read(address, 1) == b"\0",
                    "same corner reader did not observe only the policy byte fault")
            try:
                rejected = checker(bad["policy"]) is False
            except ValueError:
                rejected = True
            require(rejected, "unchanged corner policy checker accepted the bad direction mode")
            require(clock() == initial_clock and register_state() == initial_registers,
                    "corner calibration advanced native execution")
        finally:
            try:
                receipt["guestMemoryWrites"] += 1
                s.write(address, original)
                restored = capture()
                receipt.update(restored=restored, restoredClock=clock(), restoredRegisters=register_state())
                require(s.read(reader.mount_state, STATE_BYTES) == original_state and restored == clean
                        and checker(restored["policy"]) is True,
                        "corner policy exact state or owner restoration differs")
                require(receipt["restoredClock"] == initial_clock
                        and receipt["restoredRegisters"] == initial_registers,
                        "corner policy restored execution boundary differs")
                receipt["cleanupPending"] = False
            except Exception as error:
                receipt.update(state="failed", failure=str(error))
                s.abort_native_control(CornerControlError(str(error)))
                raise
        receipt["state"] = "complete"
        return deepcopy(receipt)
    except Exception as error:
        receipt.update(state="failed", failure=str(error))
        raise

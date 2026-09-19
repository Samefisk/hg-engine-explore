"""Terminal paused threshold-reader control, never gameplay or acceptance."""
from copy import deepcopy

from tools.overworld.devtools_corner_observer import NativeCornerObserver
from tools.overworld.devtools_mount_walk_fixture import STATE_BYTES
from tools.overworld.devtools_observer import NativeObservationError

THRESHOLD_OFFSET = 78  # Fixed mount Owner +8, profile.walkStompTime +70.
BAD_THRESHOLD = "mounted pacing: stomp threshold byte invalid"


class StompControlError(RuntimeError):
    code = "stomp-control-invalid"


def require(value, reason):
    if not value:
        raise StompControlError(reason)


def calibrate_stomp_policy(reader):
    """Read bad data through the same reader, restore one byte, close forever.

    The session must set its terminal guard before calling this operation. The
    expected reader failure stays latched even when restoration succeeds.
    No CPU call, input injection, register correction or game tick occurs here.
    """
    s = reader.session
    require(getattr(reader, "calibration", None) is None and reader.armed and not reader.closed
            and reader.failure is None and s.emu is not None and s.prepared
            and not s.native_bridge_active and not reader.active and not reader.data
            and isinstance(reader.latest, dict) and reader.latest.get("normalReturn") is True
            and reader.latest.get("kind") == "policy" and reader.counts.get("policy", 0) > 0
            and s.rom.resolve().is_relative_to(s.directory.resolve())
            and s.rom.resolve() != (s.rt.REPO / "test.nds").resolve(),
            "stomp calibration requires an owned paused reader after a completed policy call")
    receipt = dict(state="checking", failure=None, cleanupPending=False, acceptedProof=False,
        guestInstructionAdvance=0, guestMemoryWrites=0, terminal=True,
        scope="observer-control-only; threshold reader validation, not stomp gameplay proof")
    reader.calibration = receipt
    regs = s.emu.memory.register_arm9

    def registers():
        return {name: getattr(regs, name) for name in (*("r"+str(i) for i in range(16)), "cpsr", "spsr")}

    def clock():
        return dict(reader.observer._clock(), frame=s.completed_frames)

    def capture():
        reader._live_code()
        current = reader._current()
        # _read_profile intentionally remains callable after its failure latch;
        # no deadline/callback path is resumed to make this read succeed.
        return dict(current=current, profile=reader._read_profile(current),
            mountBinding=NativeCornerObserver._mount_binding(reader, current),
            mountStateHex=s.read(reader.mount_state, STATE_BYTES).hex(),
            pose=reader._read_pose(current), input=deepcopy(s._selector_observation()))

    try:
        clean = capture()
        current, prior = clean["current"], reader.latest
        actor = current["publicSubject"]
        boundary = reader.latest_completed_pose
        now = clock()
        require(isinstance(boundary, dict) and boundary.get("boundary") == "main-task-queue-completion"
                and boundary.get("frame") == s.completed_frames and boundary.get("actorFrame") == now["actorFrame"]
                and type(boundary.get("nativeCycle")) is int and boundary["nativeCycle"] <= now["nativeCycle"]
                and all(boundary.get(k) == value for k, value in clean["pose"].items()),
                "stomp calibration lacks its completed paired boundary")
        require(actor.get("species") == 155 and actor.get("role") == "MOUNTED"
                and actor.get("active") is True and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 1 and actor.get("motionPhase") == "IDLE"
                and actor.get("motionKind") == "NONE" and actor.get("reservationId") == 0,
                "stomp calibration requires idle attached mounted Cyndaquil")
        require(all(type(clean["input"].get(k)) is int and clean["input"][k] == 0
                    for k in ("heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys")),
                "stomp calibration requires released normal input")
        require(prior["completedFrame"] < s.completed_frames
                and all(prior["before"][k] == current[k] for k in
                    ("subject", "sourceIdentity", "engineIdentity", "worldContext",
                     "playerPointer", "mountPointer", "avatarPointer"))
                and prior["mountBinding"] == clean["mountBinding"]
                and prior["profileHex"] == clean["profile"]["profileHex"]
                and prior["stompTime"] == clean["profile"]["stompTime"],
                "stomp calibration lacks matching native policy evidence")
        original = bytes.fromhex(clean["mountStateHex"])
        require(len(original) == STATE_BYTES and original[8:80].hex() == clean["profile"]["profileHex"]
                and original[THRESHOLD_OFFSET] == clean["profile"]["stompTime"] <= 32,
                "stomp full state differs from native profile reader")
        address = reader.mount_state + THRESHOLD_OFFSET
        initial_clock, initial_registers = clock(), registers()
        changed = bytearray(original); changed[THRESHOLD_OFFSET] = 255
        receipt.update(clean=clean, policyReceipt=deepcopy(prior), stateAddress=reader.mount_state,
            stateBytes=STATE_BYTES, changedAddress=address, changedOffset=THRESHOLD_OFFSET,
            profileOffset=70, originalHex=original[THRESHOLD_OFFSET:THRESHOLD_OFFSET+1].hex(), changedHex="ff",
            clock=initial_clock, registers=initial_registers, cleanupPending=True)
        try:
            receipt["guestMemoryWrites"] += 1
            s.write(address, b"\xff")
            bad_raw = s.read(reader.mount_state, STATE_BYTES)
            require(bad_raw == bytes(changed), "stomp fault changed unrelated mounted state")
            failure = None
            try:
                reader._read_profile(current)
            except NativeObservationError as error:
                failure = str(error)
            receipt["bad"] = dict(mountStateHex=bad_raw.hex(), failure=failure)
            require(failure == BAD_THRESHOLD and reader.failure == BAD_THRESHOLD,
                    "same stomp reader did not latch the invalid threshold")
            require(clock() == initial_clock and registers() == initial_registers,
                    "stomp calibration advanced native execution")
        finally:
            try:
                receipt["guestMemoryWrites"] += 1
                s.write(address, original[THRESHOLD_OFFSET:THRESHOLD_OFFSET+1])
                restored = capture()
                receipt.update(restored=restored, restoredClock=clock(), restoredRegisters=registers())
                require(s.read(reader.mount_state, STATE_BYTES) == original and restored == clean,
                        "stomp exact state, binding, input or pose restoration differs")
                require(receipt["restoredClock"] == initial_clock and receipt["restoredRegisters"] == initial_registers,
                        "stomp restored execution boundary differs")
                receipt["cleanupPending"] = False
            except Exception as error:
                receipt.update(state="failed", failure=str(error))
                s.abort_native_control(StompControlError(str(error)))
                raise
        require(reader.failure == BAD_THRESHOLD, "stomp reader failure latch changed")
        receipt["readerFailure"] = reader.failure
        receipt["state"] = "complete"
    except Exception as error:
        receipt.update(state="failed", failure=str(error))
        raise
    finally:
        # Close is idempotent; later session disposal may close it again.
        try:
            reader.close()
            receipt["readerClosed"] = reader.closed
            receipt["readerFailure"] = reader.failure
            require(reader.closed and not reader.active and not reader.data
                    and all(token not in reader.observer.tokens and token not in reader.observer.return_tokens
                            for token in reader.entries + reader.returns),
                    "stomp terminal reader cleanup differs")
        except Exception as error:
            receipt.update(state="failed", failure=str(error), cleanupPending=True)
            s.abort_native_control(StompControlError(str(error)))
            raise
    return deepcopy(receipt)

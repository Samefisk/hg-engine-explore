"""One checked idle RESET through the public Walk reducer; prepared setup only."""
from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_records import GENERATION_FIELDS, select_current_actor

GUARD = b"WalkResetGuard!!"
RESET_BYTES = 28


class WalkResetError(ValueError):
    code = "walk-policy-reset-invalid"

    def __init__(self, message, *, fatal=False, code=None):
        super().__init__(message)
        self.fatal = fatal
        if code is not None:
            self.code = code


def require(value, message, *, fatal=False):
    if not value:
        raise WalkResetError(message, fatal=fatal)


def authenticate(session):
    services = [x for x in session.rt.ACTOR_DESCRIPTOR["privateServices"]
                if x.get("name") == "movementPolicy"]
    require(len(services) == 1, "missing public movement policy service")
    service = services[0]
    target = session.target("reduce_walk")
    require(service.get("status") == "available" and service.get("version") == 4
            and service.get("size") == 16 and service.get("reserved") == 0,
            "public movement policy ABI differs")
    expected = struct.pack("<IHHII", 0x504D574F, 4, 16, service["policy"], 0)
    require(session.packaged_code(service["address"], 16) == expected,
            "public movement policy entry differs")
    table = session.packaged_code(service["policy"], 24)
    require(len(table) == 24 and struct.unpack_from("<I", table, 12)[0] == target | 1,
            "public reduceWalk callback differs")
    return dict(address=service["address"], entryHex=expected.hex(), tableHex=table.hex(),
                reduceWalkAddress=target | 1,
                entrySha256=hashlib.sha256(session.packaged_code(target, 32)).hexdigest())


class WalkPolicyReset:
    def __init__(self, session, subject):
        self.session = session
        require(isinstance(subject, dict) and all(key in subject for key in GENERATION_FIELDS),
                "RESET requires the full selected subject and all generations")
        self.subject = deepcopy(subject)
        self.service = authenticate(session)
        self.field, self.heap = session.field_pointer(), session.native_heap_generation
        self.started = False
        self.expected_actor = None
        self._capture()

    def _capture(self):
        s = self.session
        require(s.emu is not None and self.field and s.field_pointer() == self.field
                and s.native_heap_generation == self.heap, "RESET field/heap owner changed", fatal=True)
        require(authenticate(s) == self.service, "RESET service changed", fatal=True)
        s.require_quiescent()
        snapshot = s._snapshot(0, details=False)
        selected = select_current_actor(snapshot, self.subject)
        if "engineIdentity" in self.subject:
            require(selected["engineIdentity"] == self.subject["engineIdentity"], "selected engine identity changed")
        actor = next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])
        reader = getattr(s.rt, "wild_staged_motion", None)
        staged = reader(s.emu, selected["handle"]["slot"]) if callable(reader) else None
        if not isinstance(staged, dict) or staged.get("known") is not True:
            reason = staged.get("reason", "unavailable") if isinstance(staged, dict) else "reader unavailable"
            raise WalkResetError("RESET needs authenticated staged movement readiness: " + str(reason)[:160],
                                 code="walk-reset-staged-state-unavailable")
        require(staged.get("idle") is True, "RESET staged movement is active")
        require(staged.get("slot") == selected["handle"]["slot"]
                and staged.get("objectPointer") == actor.get("engineIdentity", {}).get("pointer"),
                "RESET staged readiness names a different actor")
        actor["stagedMovement"] = deepcopy(staged)
        require(actor["role"] in ("WILD", "MOUNTED"), "unsupported RESET actor role")
        require(actor.get("motionPhase") == "IDLE" and actor.get("reservationId") == 0
                and actor.get("inputOwnership") == int(actor["role"] == "MOUNTED"), "RESET actor is busy")
        inputs = s._selector_observation()
        require(inputs.get("state") == 0 and all(inputs.get(k) == 0 for k in
                ("heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys", "physicalPressed")),
                "RESET requires released input and a closed selector")
        for obj in (actor.get("engineObject"), snapshot.get("player")):
            require(isinstance(obj, dict) and type(obj.get("flags")) is int, "RESET engine pose is missing")
            flags = obj["flags"]
            require(flags & 1 and not flags & 2 and (not flags & 0x10 or flags & 0x20)
                    and [obj.get("pos_x"), obj.get("pos_z")] ==
                    [(obj[k] << 16) + 0x8000 for k in ("x", "y")], "RESET engine movement is active")
        state = s.rt.ACTOR_DESCRIPTOR["state"]
        capacity = s.rt.ACTOR_DESCRIPTOR["capacities"]["actors"]
        policy_size = s.rt.ACTOR_DESCRIPTOR["structures"]["actorPolicyState"]
        base, size, stride, offset, policy_member = (state["address"], state["size"],
            state["actorStride"], state["offsets"]["actors"], state["actorPolicyOffset"])
        require(all(type(v) is int for v in
                    (base, size, stride, offset, policy_member, policy_size, capacity))
                and base % 4 == 0 and 0x02000000 <= base <= 0x02400000 - size
                and 48 <= size <= 65535 and 1 <= capacity <= 10 and stride >= 88 and stride % 4 == 0
                and offset >= 48 and offset % 4 == 0 and policy_size == 32
                and 88 <= policy_member <= stride - policy_size
                and offset + capacity * stride <= size,
                "RESET actor/policy layout differs")
        slot = selected["handle"]["slot"]
        require(slot < capacity, "RESET actor slot outside capacity")
        policy_offset = offset + stride * slot + policy_member
        raw = s.read(base, size)
        require(len(raw) == size and raw[:8] == struct.pack("<IHH", 0x5353574F, 1, size),
                "RESET actor state is not initialized")
        policy = raw[policy_offset:policy_offset + 32]
        require(policy[5] == 0 and policy[22] == 0 and policy[23] == 0,
                "RESET has pending Walk work")
        stable_actor = {k: deepcopy(v) for k, v in actor.items()
                        if k not in ("movementPolicy", "crashPresentation")}
        if self.expected_actor is None:
            self.expected_actor = stable_actor
        else:
            # Clocks inside crash diagnostics are not part of subject ownership.
            keys = ("handle", "subjectIdentity", "species", "form", "level", "role",
                    *GENERATION_FIELDS, "engineIdentity", "sourceIdentity")
            require(all(stable_actor.get(k) == self.expected_actor.get(k) for k in keys),
                    "RESET selected actor changed before dispatch")
        return dict(snapshot=deepcopy(snapshot), subject=selected, actor=stable_actor,
                    policyHex=policy.hex(), policy=deepcopy(actor.get("movementPolicy")),
                    stagedMovement=deepcopy(staged), state=raw, policyOffset=policy_offset, inputs=inputs)

    def recipe(self, scratch, call):
        require(not self.started, "RESET is one-shot")
        self.started = True
        s = self.session
        require(scratch == s.native_trampoline["address"] + 0x200, "RESET scratch is not bridge-owned")
        before = self._capture()
        request = struct.pack("<HHI", 1, RESET_BYTES, 0) + bytes((self.subject["handle"]["slot"], 0)) + bytes(18)
        original = s.read(scratch, 60)
        require(len(original) == 60, "RESET scratch is incomplete")
        completed = False
        try:
            s.write(scratch, GUARD + request + GUARD)
            status = yield call("reduce_walk", (scratch + 16,))
            after = self._capture()
            observed = s.read(scratch, 60)
            require(observed == GUARD + request + GUARD and type(status) is int and status == 1,
                    "RESET native return or guarded request differs")
            expected = bytearray.fromhex(before["policyHex"])
            expected[:8] = bytes((255, 0, 0, 0, 255, 0, 0, 0))
            expected[16:19] = bytes(3)
            expected[20:24] = bytes((255, 0, 0, 0))
            require(after["policyHex"] == expected.hex(), "RESET policy readback differs")
            offset = before["policyOffset"]
            expected_state = before["state"][:offset] + expected + before["state"][offset + 32:]
            require(after["state"] == expected_state and before["actor"] == after["actor"]
                    and before["snapshot"]["player"] == after["snapshot"]["player"]
                    and before["inputs"] == after["inputs"], "RESET changed pose, profile, anchor or actor state")
            completed = True
        finally:
            require(s.field_pointer() == self.field and s.native_heap_generation == self.heap,
                    "RESET scratch owner changed", fatal=True)
            s.write(scratch, original)
            require(s.read(scratch, 60) == original, "RESET scratch restoration failed", fatal=True)
        return dict(completed=completed, prepared=True, acceptedProof=False, scope="prepared-idle-walk-policy-reset",
                    fieldPointer=self.field, heapGeneration=self.heap,
                    mutation="public RESET clears momentum, pending step and chain state; not gameplay proof",
                    readinessScope="observed staged readiness, public IDLE/reservation, policy pending/skid and native settled objects",
                    subject=before["subject"], serviceIdentity=self.service, requestHex=request.hex(),
                    responseHex=observed[16:44].hex(), returnValue=status,
                    before={k: v for k, v in before.items() if k not in ("state", "policyOffset")},
                    after={k: v for k, v in after.items() if k not in ("state", "policyOffset")},
                    scratchRestored=True)

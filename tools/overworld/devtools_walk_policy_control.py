"""One stopped-guest COMMIT reader check; no incorrect value enters normal data."""
from copy import deepcopy

from tools.overworld.devtools_records import _subject, GENERATION_FIELDS, select_current_actor


class WalkPolicyControlError(RuntimeError):
    code = "walk-policy-control-invalid"


class NativeWalkPolicyReadControl:
    def __init__(self, session, subject):
        _subject(subject)
        self.session, self.subject = session, deepcopy(subject)
        self.state, self.failure, self.receipt = "new", None, None
        self.cleanup_pending = False

    def arm(self):
        if self.state != "new":
            raise WalkPolicyControlError("Walk policy reader control is single-use")
        self._identity()
        self.state = "armed"
        return self.result()

    def _identity(self):
        s = self.session
        if s.emu is None or s.native_bridge_active:
            raise WalkPolicyControlError("Walk policy control requires a paused native game call")
        actor = select_current_actor(s._snapshot(0, details=False), self.subject)
        if (_subject(actor) != _subject(self.subject)
                or any(actor.get(k) != self.subject.get(k) for k in GENERATION_FIELDS)
                or any(actor["engineIdentity"].get(k) != self.subject["engineIdentity"].get(k)
                       for k in ("pointer", "current_manager", "object_manager", "manager_index"))):
            raise WalkPolicyControlError("Walk policy control owner changed")
        return actor

    @staticmethod
    def _receipt(value):
        raw, policy = value
        data = bytes.fromhex(raw)
        if len(data) != 32 or type(policy.get("counter")) is not int or policy["counter"] != data[1]:
            raise WalkPolicyControlError("Walk policy reader counter or byte size differs")
        return dict(rawHex=raw, policy=deepcopy(policy))

    def capture(self, observer, slot, read_fn):
        clean_value = read_fn()
        if self.state != "armed" or slot != self.subject["handle"]["slot"]:
            return clean_value
        self.state = "capturing"
        try:
            self._identity()
            clean = self._receipt(clean_value)
            original = bytes.fromhex(clean["rawHex"])
            if original[1] == 255:
                raise WalkPolicyControlError("Walk policy counter cannot be incremented without overflow")
            address = observer._commit_policy_address(slot)
            if self.session.read(address, 32) != original:
                raise WalkPolicyControlError("Walk policy native bytes differ from clean read")
            self.receipt = dict(clean=clean, bad=None, restored=None, clock=observer._clock(),
                                policyAddress=address, changedOffset=1, guestInstructionAdvance=0)
            corrupted = bytearray(original)
            corrupted[1] += 1
            self.cleanup_pending = True
            try:
                self.session.write(address + 1, bytes((corrupted[1],)))
                bad = self._receipt(read_fn())
                self.receipt["bad"] = bad
                expected = deepcopy(clean)
                expected["rawHex"] = corrupted.hex()
                expected["policy"]["counter"] = corrupted[1]
                if bad != expected:
                    raise WalkPolicyControlError("same Walk policy reader did not observe only changed counter")
            finally:
                owner_error = None
                try:
                    self._identity()
                except Exception as error:
                    owner_error = error
                try:
                    # Restore our exact original allocation even on owner error;
                    # such an error remains fatal and cannot resume gameplay.
                    self.session.write(address + 1, original[1:2])
                    if self.session.read(address, 32) != original:
                        raise WalkPolicyControlError("Walk policy native restore readback differs")
                    restored = self._receipt(read_fn())
                    self.receipt["restored"] = restored
                    if restored != clean:
                        raise WalkPolicyControlError("Walk policy same-reader restore differs")
                    self.receipt["restoredClock"] = observer._clock()
                    if self.receipt["restoredClock"] != self.receipt["clock"]:
                        raise WalkPolicyControlError("Walk policy control crossed native execution boundary")
                    self.cleanup_pending = False
                    if owner_error is not None:
                        raise owner_error
                except Exception as error:
                    self.failure, self.state = str(error), "failed"
                    self.session.abort_native_control(WalkPolicyControlError(self.failure))
                    raise WalkPolicyControlError(self.failure) from error
            self.state = "complete"
            return clean_value
        except Exception as error:
            self.failure, self.state = str(error), "failed"
            raise

    def close(self):
        if self.cleanup_pending:
            self.session.abort_native_control(WalkPolicyControlError("Walk policy control cleanup is pending"))
        if self.state == "armed":
            self.failure, self.state = "Walk policy control closed without its COMMIT", "failed"
        return self.result()

    def result(self):
        return deepcopy(dict(state=self.state, failure=self.failure, cleanupPending=self.cleanup_pending,
                             subject=self.subject, receipt=self.receipt, acceptedProof=False))

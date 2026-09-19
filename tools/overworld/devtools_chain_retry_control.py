"""One owned, typed native chain-start denial. No guest-memory or RNG writes."""
from copy import deepcopy
from tools.overworld.devtools_records import _subject, GENERATION_FIELDS


class ChainRetryControlError(RuntimeError):
    code = "chain-retry-control-invalid"


class NativeChainRetryControl:
    COOLDOWN_OFFSET = 0xED

    def __init__(self, session, subject, max_frames):
        self.session = session
        self.subject = deepcopy(subject)
        self.failure = None
        self.closed = False
        self.injection = None
        self.parents = []
        self.boundaries = []
        self.parent = None
        self.tokens = []
        self.armed_frame = session.completed_frames
        if _subject(subject)["species"] != 165 or subject["role"] != "WILD" or not 0 <= subject["handle"]["slot"] < 6:
            raise ValueError("chain retry needs the exact natural WILD Ledyba")
        if type(max_frames) is not int or not 1 <= max_frames <= 1800:
            raise ValueError("chain retry budget must be 1..1800 completed frames")
        self.max_frames = max_frames

    def fail(self, message):
        self.failure = self.failure or message
        raise ChainRetryControlError(self.failure)

    def install(self):
        o, rt = self.session.native_observation, self.session.rt
        path = rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
        name = "OverworldWildSpawns_CommitDeferredChainMovementPause"
        address = rt.linked_symbol(rt.WILD_SYMBOLS, name) & ~1
        before = len(o.tokens)
        o._tap("chain-retry-parent", address, o.elf_code(path, address, 32),
               self.parent_before, self.parent_after, scope=lambda: not self.closed and self.failure is None)
        self.tokens = o.tokens[before:]

    def current(self):
        s, o = self.session, self.session.native_observation
        if self.closed or self.failure or s.emu is None or s.native_bridge_active:
            self.fail("chain retry scope unavailable")
        if s.completed_frames - self.armed_frame > self.max_frames:
            self.fail("chain retry observation deadline exceeded")
        slot = self.subject["handle"]["slot"]
        actor, source, engine, world = o._chain_current(slot)
        if (_subject(actor) != _subject(self.subject)
                or any(actor[k] != self.subject[k] for k in GENERATION_FIELDS)
                or any(engine[k] != self.subject["engineIdentity"][k] for k in
                       ("pointer", "current_manager", "object_manager", "manager_index"))):
            self.fail("chain retry selected owner changed")
        p = s.rt.movement_policy_state(s.emu, slot)
        policy = dict(chainPauseAction=p["action"], chainPauseTicks=p["ticks"], chainStepsRemaining=p["chain"])
        cooldown = s.rt.unsigned(s.emu, s.rt.WILD_STATE + self.COOLDOWN_OFFSET + slot, 1)
        return dict(publicSubject=actor, sourceIdentity=source, engineIdentity=engine, worldContext=world,
                    policy=policy, movementCooldown=cooldown,
                    frame=s.completed_frames, nativeCycle=s.rt.EXECUTED_FRAME_COUNT)

    def parent_before(self):
        regs = self.session.emu.memory.register_arm9
        if regs.r1 != self.subject["handle"]["slot"]: return None
        if self.session.rt.movement_policy_state(self.session.emu, regs.r1)["action"] != 0x85:
            return None
        if self.parent is not None or len(self.parents) >= 32:
            self.fail("chain retry parent bound or nesting differs")
        if regs.r0 != self.session.rt.WILD_STATE:
            self.fail("chain retry parent state differs")
        before = self.current()
        self.parent = dict(before=before, profilePointer=regs.r2, controlAttemptId=None, attemptIds=[])
        return self.parent

    def parent_after(self, value, context):
        after = self.current()
        if self.parent is not value: self.fail("chain retry parent ownership differs")
        row = dict(publicSubject=value["before"]["publicSubject"], publicSubjectAfter=after["publicSubject"],
            policyBefore=value["before"]["policy"], policyAfter=after["policy"],
            movementCooldownBefore=value["before"]["movementCooldown"], movementCooldownAfter=after["movementCooldown"],
            controlAttemptId=value["controlAttemptId"], entryClock=context["entry"], returnClock=context["returned"],
            attemptIds=deepcopy(value["attemptIds"]),
            frame=self.session.completed_frames, nativeCycle=self.session.rt.EXECUTED_FRAME_COUNT)
        self.parents.append(deepcopy(row))
        self.parent = None
        return row

    def start(self, value, context, entry_address):
        """Called only after the ordinary observer's return hook is installed."""
        if self.closed: return
        parent = value["parent"]
        if parent["slot"] != self.subject["handle"]["slot"]: return
        if self.parent is not None and parent["attemptId"] not in self.parent["attemptIds"]:
            self.parent["attemptIds"].append(parent["attemptId"])
        if self.injection is not None: return
        if self.parent is None:
            # Same actor can enter other reposition actions before our natural
            # action5 window. Leave those calls untouched. A still-pending
            # selected action without its parent receipt is an observation gap.
            policy = self.session.rt.movement_policy_state(self.session.emu, parent["slot"])
            if policy["action"] != 0x85:
                return
            self.fail("chain start has no owned retry parent")
        current = self.current()
        if self.parent["before"]["policy"]["chainPauseAction"] != (0x80 | 5):
            self.fail("chain retry action is not naturally selected action5")
        s, o = self.session, self.session.native_observation
        regs = s.emu.memory.register_arm9
        o._chain_caller("OverworldWildSpawns_RunChainReposition")
        lr, sp = regs.lr & 0xffffffff, regs.sp & 0xffffffff
        if not lr & 1 or sp != context["sp"]: self.fail("chain retry return frame differs")
        code = s.read((lr & ~1) - 4, 4)
        first, second = int.from_bytes(code[:2], "little"), int.from_bytes(code[2:], "little")
        displacement = ((first & 0x7ff) << 12) | ((second & 0x7ff) << 1)
        if displacement & (1 << 22): displacement -= 1 << 23
        if (first & 0xf800 != 0xf000 or second & 0xf800 != 0xf800
                or ((lr & ~1) + displacement) & 0xffffffff != entry_address):
            self.fail("chain retry BL target differs")
        registers = {"r"+str(i): getattr(regs, "r"+str(i)) & 0xffffffff for i in range(15)}
        injection = dict(attemptId=parent["attemptId"], landingIndex=value["record"]["landingIndex"],
            subject=deepcopy(self.subject), entryClock=deepcopy(context["entry"]), entryAddress=entry_address,
            returnAddress=lr, returnReason=8, requestedArguments=[registers["r"+str(i)] for i in range(4)],
            stackArguments=o._chain_words(7), policyBefore=deepcopy(self.parent["before"]["policy"]),
            current=current, registersBefore=registers, guestMemoryWrites=0)
        # Publish ownership before redirect, so an exception cannot re-inject.
        self.injection = injection
        self.parent["controlAttemptId"] = parent["attemptId"]
        regs.r0 = 8
        s.emu.memory.set_next_instruction(lr)
        injection["registersAfter"] = {"r"+str(i): getattr(regs, "r"+str(i)) & 0xffffffff for i in range(15)}
        if any(injection["registersAfter"][k] != v for k, v in registers.items() if k != "r0"):
            self.fail("chain retry changed preserved register")

    def completed_boundary(self):
        if self.closed: return
        if self.failure: self.fail(self.failure)
        if self.session.completed_frames - self.armed_frame > self.max_frames:
            self.fail("chain retry observation deadline exceeded")
        if self.injection is None or len(self.boundaries) >= 4: return
        # Exact real queue samples; meter decides whether these prove cooldown.
        value = self.current()
        if not self.boundaries or value["frame"] != self.boundaries[-1]["frame"]:
            self.boundaries.append(deepcopy(value))

    def close(self):
        if self.closed: return
        if self.parent is not None:
            self.failure = self.failure or "chain retry closed with native parent in flight"
        o = self.session.native_observation
        for token in self.tokens:
            o.hooks.remove(token)
            if token in o.tokens: o.tokens.remove(token)
        self.tokens.clear()
        self.closed = True

    def result(self):
        return dict(armed=True, injected=self.injection is not None, closed=self.closed, failure=self.failure,
            acceptedProof=False, guestMemoryWrites=0, pendingWrites=0, subject=deepcopy(self.subject),
            injection=deepcopy(self.injection), parents=deepcopy(self.parents), cooldownBoundaries=deepcopy(self.boundaries))

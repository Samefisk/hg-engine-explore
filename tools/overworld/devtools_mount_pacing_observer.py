"""Opt-in mounted callback receipts. Native clocks are not completed frames."""
from copy import deepcopy

from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld.devtools_records import select_current_actor

IDENTITY = ("handle", "species", "form", "level", "subjectIdentity", "role",
            "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
            "behaviorFingerprint", "matchedLayerMask")
ENGINE = ("pointer", "current_manager", "object_manager", "manager_index", "object_id",
          "object_map_id", "script_id")
MAX_CALLBACKS = 4096


class MountedPacingFailure(NativeObservationError):
    fatal = True
    code = "mounted-pacing-observation-failed"


class NativeMountedPacingObserver:
    def __init__(self, session, subject, max_frames):
        self.observer, self.session = session.native_observation, session
        def linked(label, path, symbols, name, before, after, **kwargs):
            address = session.rt.linked_symbol(symbols, name) & ~1
            self.observer._tap(label, address, self.observer.elf_code(path, address, 32), before, after, **kwargs)
        self.linked = linked
        self.subject, self.owner = deepcopy(subject), None
        self.armed = self.closed = False
        self.failure = None
        self.entries, self.returns, self.data = [], [], []
        self.counts = {"presentation": 0, "playerStep": 0}
        self.started, self.maximum = None, max_frames
        self.latest_completed_pose = None

    def _require(self, value, reason):
        if not value:
            self.failure = self.failure or "mounted pacing: " + reason
            raise MountedPacingFailure(self.failure)

    def _current(self):
        from tools.overworld.devtools_runtime import actor_identity_checks
        s, rt = self.session, self.session.rt
        actor = rt.actor_state(s.emu, 7)
        source = rt.wild_spawn(s.emu, 7)
        engine = rt.live_wild_object_identity(s.emu, 7)
        world = self.observer._world_context()
        self._require(all(actor_identity_checks(actor, source, engine, world, 7).values())
            and actor.get("role") == "MOUNTED" and actor.get("active") is True
            and actor.get("inputOwnership") == 1 and actor.get("form") == source.get("form")
            and actor.get("level") == source.get("level") and source.get("object") == engine.get("pointer"),
            "current mounted binding differs")
        self._require(type(engine.get("pointer")) is int and engine["pointer"] % 4 == 0
            and 0x02000000 <= engine["pointer"] <= 0x02400000-0x12C, "invalid mount object")
        player = rt.player_ptr(s.emu)
        # FieldSystem.playerAvatar +0x40 and FIELD_PLAYER_AVATAR.mapObject +0x30:
        # include/pokemon.h and include/map_events_internal.h, matching vanilla.
        avatar = rt.unsigned(s.emu, world["fieldPointer"] + 0x40)
        self._require(type(avatar) is int and avatar % 4 == 0
            and 0x02000000 <= avatar <= 0x02400000-0x40
            and rt.unsigned(s.emu, avatar+0x30) == player, "avatar anchor differs")
        manager = engine["current_manager"]
        self._require(type(manager) is int and manager % 4 == 0 and 0x02000000 <= manager <= 0x02400000-0x128,
                      "invalid current manager")
        objects, count = rt.unsigned(s.emu, manager+0x124), rt.unsigned(s.emu, manager+4)
        self._require(type(count) is int and 1 <= count <= 64
            and type(objects) is int and objects % 4 == 0
            and 0x02000000 <= objects <= 0x02400000-count*0x12C,
            "invalid current object array")
        self._require(type(player) is int and player % 4 == 0 and 0x02000000 <= player <= 0x02400000-0x12C
            and objects and player >= objects and (player-objects) % 0x12C == 0
            and (player-objects)//0x12C < count and rt.unsigned(s.emu, player) & 1
            and rt.unsigned(s.emu, player+0xB4) == manager, "current player anchor differs")
        engine = {**engine, "anchorPointer": player, "anchorInCurrentManager": True}
        self._require(isinstance(self.subject.get("engineIdentity"), dict) and
            all(self.subject["engineIdentity"].get(k) == engine.get(k)
                for k in (*ENGINE, "anchorPointer", "anchorInCurrentManager")), "bound engine owner differs")
        checked = {**actor, "identityVerified": True, "engineIdentity": engine, "sourceIdentity": source}
        select_current_actor({"actors": [checked], "context": world, "frame": s.completed_frames}, self.subject)
        current = dict(subject=deepcopy(self.subject), publicSubject=deepcopy(actor), sourceIdentity=source,
            engineIdentity={k: engine.get(k) for k in ENGINE}, worldContext=world,
            playerPointer=player, mountPointer=engine["pointer"], avatarPointer=avatar)
        if self.owner is not None:
            self._require(all(current[k] == self.owner[k] for k in ("subject", "sourceIdentity", "engineIdentity",
                "worldContext", "playerPointer", "mountPointer", "avatarPointer")) and
                all(actor.get(k) == self.owner["publicSubject"].get(k) for k in IDENTITY), "mounted owner changed")
        return current

    def _install(self, label, name, before, after):
        o, rt = self.observer, self.session.rt
        start = len(o.tokens)
        try:
            self.linked(label, rt.REPO / "build/overworld_mount_overlay_linked.o", rt.MOUNT_SYMBOLS,
                name, before, after, scope=lambda: self.armed and not self.closed, resident=True)
        finally:
            self.entries.extend(o.tokens[start:])
        for token in list(o.tokens[start:]):
            address, callback = token
            def tracked(callback=callback):
                previous = list(o.return_tokens)
                try:
                    return callback()
                except Exception as error:
                    self.failure = self.failure or str(error)
                    abort = getattr(self.session, "abort_native_control", None)
                    if abort is not None: abort(error)
                    raise
                finally:
                    self.returns.extend(t for t in o.return_tokens if t not in previous)
            o.hooks.remove(token)
            replacement = o.hooks.add(address, tracked)
            o.tokens[o.tokens.index(token)] = replacement
            self.entries[self.entries.index(token)] = replacement

    def arm(self):
        self._require(not self.armed and not self.closed, "reader can arm only once")
        self._require(type(self.maximum) is int and 1 <= self.maximum <= 1200, "invalid frame limit")
        self.started = self.session.completed_frames
        try:
            self.owner = self._current()
            self.armed = True
            self._install("mount-pacing-presentation", "OverworldMount_SyncPresentation",
                          lambda: self._before("presentation"), self._after)
            self._install("mount-pacing-player-step", "OverworldMount_PlayerStepBridge",
                          lambda: self._before("playerStep"), self._after)
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close()
            raise
        return self.result()

    def _check_deadline(self):
        if self.armed and not self.closed:
            self._require(self.failure is None, "reader already failed")
            self._require(0 <= self.session.completed_frames-self.started <= self.maximum, "frame deadline exceeded")

    def completed_boundary(self):
        self._check_deadline()
        if self.armed and not self.closed:
            clock = self.observer._clock()
            self.latest_completed_pose = dict(self._read_pose(self._current()),
                boundary="main-task-queue-completion", frame=self.session.completed_frames,
                **clock)
            # Same stock gSystem fields as the selector input reader. Keep the
            # real held-key value with the completed pose, not only a host request.
            self.latest_completed_pose["input"] = {
                "heldKeys": self.session.rt.unsigned(self.session.emu, 0x021D1150),
                "newKeys": self.session.rt.unsigned(self.session.emu, 0x021D1154),
            }

    def _before(self, kind):
        self._check_deadline()
        self._require(sum(self.counts.values()) < MAX_CALLBACKS, "callback limit exceeded")
        current = self._current()
        field = self.session.emu.memory.register_arm9.r0 if kind == "playerStep" else current["worldContext"]["fieldPointer"]
        self._require(field == current["worldContext"]["fieldPointer"], "player-step field argument differs")
        self.counts[kind] += 1
        value = dict(kind=kind, before=current, fieldPointer=field)
        self.data.append(value)
        return value

    def _read_pose(self, current):
        """Read actual pair bytes without advancing or correcting the guest."""
        rt, emu = self.session.rt, self.session.emu
        value = {**current,
            "player": rt.object_state(emu, current["playerPointer"]),
            "mount": rt.object_state(emu, current["mountPointer"]),
            "avatarControl": {
                "flags": rt.unsigned(emu, current["avatarPointer"]),
                "moveState": rt.unsigned(emu, current["avatarPointer"]+0x10),
                "playerMoveState": rt.unsigned(emu, current["avatarPointer"]+0x14),
            }}
        for name, pointer in (("player", current["playerPointer"]), ("mount", current["mountPointer"])):
            value[name].update(unk88_z=rt.signed(emu, pointer+0x90),
                               unk94_z=rt.signed(emu, pointer+0x9C))
        return value

    def _after(self, before, context):
        try:
            current = self._current()
            self._require(before["before"]["subject"] == current["subject"], "callback owner changed")
            value = {**self._read_pose(current), "kind": before["kind"], "fieldPointer": before["fieldPointer"]}
            if before["kind"] == "playerStep":
                self._require(context["returnValue"] in (0, 1), "player-step returned invalid BOOL")
                value["eventConsumed"] = context["returnValue"]
                value["meaning"] = "native mounted world-step bridge returned; not tile admission"
            return value
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(self.session, "abort_native_control", None)
            if abort is not None: abort(error)
            raise
        finally:
            if before in self.data: self.data.remove(before)

    def close(self, disposing=False):
        if self.closed: return self.result()
        self.closed = True
        o = self.observer
        pending = [c for c in o.contexts if any(c.get("data") is d for d in self.data)]
        if pending: self.failure = self.failure or "mounted pacing: pending callback at close"
        o.contexts[:] = [c for c in o.contexts if not any(c is p for p in pending)]
        errors = []
        for token in self.entries + self.returns:
            try:
                o.hooks.remove(token)
                for collection in (o.tokens, o.return_tokens):
                    if token in collection: collection.remove(token)
                o.hooks.retire_empty(token[0])
            except Exception as error: errors.append(str(error))
        if errors: self.failure = self.failure or "mounted pacing cleanup: " + errors[0]
        self.data.clear()
        return self.result()

    def result(self):
        return deepcopy(dict(armed=self.armed, closed=self.closed, failure=self.failure,
            subject=self.subject, startFrame=self.started, maxFrames=self.maximum,
            maxCallbacks=MAX_CALLBACKS, counts=self.counts, acceptedProof=False,
            latestCompletedPose=self.latest_completed_pose,
            guestMemoryWrites=0 if getattr(self, "pose_calibration", None) is None else 2,
            poseCalibration=deepcopy(getattr(self, "pose_calibration", None)),
            scope="native callback receipts; completion framing belongs to shared queue"))

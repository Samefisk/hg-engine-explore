"""Controlled live observer for one Wild conditional-profile boundary.

This is not the copied condition-service probe.  It patches three predicate
bytes in the disposable process, observes the real Wild wrapper calling the
real condition adapter, and restores every changed byte before close.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_condition_controller import (
    CONDITION_APPLICATION,
    CONDITION_ID,
    KIND,
    PREPARED_ACTOR_BYTES,
    PREPARED_STATE_POINTER_OFFSET,
    RUNTIME_ACTIVE_MASKS_OFFSET,
    SUBJECT_ROLE,
    SUBJECT_SPECIES,
    TARGET_ROLE,
    build_live_controller_fixture,
    decode_profile,
    expected_profile,
    stale_generation,
    target_generation_address,
)
from tools.overworld.devtools_mount_pacing_observer import (
    NativeMountedPacingObserver,
)
from tools.overworld.devtools_observer import NativeObservationError, public_bytes
from tools.overworld.devtools_records import select_current_actor


RUNTIME_ACTORS_OFFSET = 0
RUNTIME_SCRATCH_OFFSET = PREPARED_ACTOR_BYTES * 10
RUNTIME_RESULT_OFFSET = RUNTIME_SCRATCH_OFFSET + 32
RUNTIME_RESOLUTION_OFFSET = RUNTIME_RESULT_OFFSET + 540 + 44
RUNTIME_ACTOR_SNAPSHOT_OFFSET = RUNTIME_RESOLUTION_OFFSET + 200 + 12 + 396
RUNTIME_TIMED_MASKS_OFFSET = RUNTIME_ACTIVE_MASKS_OFFSET + 40
RUNTIME_TARGET_X_OFFSET = RUNTIME_TIMED_MASKS_OFFSET + 40
RUNTIME_TARGET_Y_OFFSET = RUNTIME_TARGET_X_OFFSET + 20
RUNTIME_TARGET_VALID_OFFSET = RUNTIME_TARGET_Y_OFFSET + 20
RUNTIME_MIN_BYTES = RUNTIME_TARGET_VALID_OFFSET + 4

PREPARED_CATALOG_INDICES_OFFSET = 16
PREPARED_COUNT_OFFSET = 48
PREPARED_VALID_OFFSET = 49
PREPARED_CAPACITY_OFFSET = 50

MAX_CALLS = 16


class ConditionControllerObservationFailure(NativeObservationError):
    fatal = True
    code = "condition-controller-observation-failed"


def _require(value, reason):
    if not value:
        raise ConditionControllerObservationFailure(
            "condition controller: " + reason)


def _pointer(value, size=4):
    _require(type(value) is int and value % 4 == 0
             and 0x02000000 <= value <= 0x02400000 - size,
             "invalid main-memory pointer")
    return value


def _public_pointer(value, size=4):
    main = (type(value) is int and value % 4 == 0
            and 0x02000000 <= value <= 0x02400000 - size)
    stack = (type(value) is int and value % 4 == 0
             and 0x027E0000 <= value <= 0x027E3FC0 - size)
    _require(main or stack, "invalid public RAM/stack pointer")
    return value


def _handle(raw):
    _require(isinstance(raw, bytes) and len(raw) == 12,
             "condition target handle bytes differ")
    slot, generation, field, map_generation, encounter, reserved = \
        struct.unpack("<6H", raw)
    _require(reserved == 0 and generation != 0 and field != 0
             and map_generation != 0 and encounter != 0,
             "condition target handle fields differ")
    return {
        "value": (generation << 16) | slot,
        "slot": slot,
        "generation": generation,
        "fieldEpoch": field,
        "mapGeneration": map_generation,
        "encounterGeneration": encounter,
    }


class LiveConditionControllerFixture:
    """Own the exact three-byte live catalog patch and its restoration."""

    def __init__(self, session):
        self.session = session
        self.applied = False
        self.restored = False
        self.failure = None
        self.address = None
        self.source = self.patched = None
        self.fixture = None
        self.write_bytes = 0
        self.write_operations = 0

    def apply(self):
        _require(not self.applied and not self.restored,
                 "catalog fixture can apply only once")
        session = self.session
        _require(session.prepared and session.emu is not None
                 and not session.native_bridge_active,
                 "catalog fixture requires a paused prepared session")
        discovery = session.native_observation.resolver_discovery
        _require(isinstance(discovery, dict)
                 and discovery.get("status") == 0,
                 "natural resolver blob discovery is missing")
        source = (session.rt.REPO / "build/OverworldWildBehaviorData.bin").read_bytes()
        address = discovery.get("blobAddress")
        _pointer(address, len(source))
        _require(discovery.get("blobSize") == len(source)
                 and session.read(address, len(source)) == source,
                 "live behavior blob differs from the packaged source")
        patched, receipt = build_live_controller_fixture(source)
        try:
            for change in receipt["changes"]:
                absolute = address + change["offset"]
                _require(session.read(absolute, 1) == bytes((change["before"],)),
                         "catalog source byte changed before patch")
                session.write(absolute, bytes((change["after"],)))
                self.write_bytes += 1
                self.write_operations += 1
            _require(session.read(address, len(source)) == patched,
                     "live catalog patch readback differs")
        except Exception:
            for change in reversed(receipt["changes"]):
                absolute = address + change["offset"]
                if session.read(absolute, 1) == bytes((change["after"],)):
                    session.write(absolute, bytes((change["before"],)))
            raise
        self.source, self.patched = source, patched
        self.address, self.fixture = address, receipt
        self.applied = True
        return self.result()

    def restore(self):
        if self.restored:
            return self.result()
        _require(self.applied and self.fixture is not None,
                 "catalog fixture was not applied")
        session = self.session
        try:
            _require(session.read(self.address, len(self.patched)) == self.patched,
                     "live catalog changed before restore")
            for change in reversed(self.fixture["changes"]):
                absolute = self.address + change["offset"]
                session.write(absolute, bytes((change["before"],)))
                self.write_bytes += 1
                self.write_operations += 1
            _require(session.read(self.address, len(self.source)) == self.source,
                     "live catalog did not restore")
            self.restored = True
        except Exception as error:
            self.failure = self.failure or str(error)
            abort = getattr(session, "abort_native_control", None)
            if abort is not None:
                abort(error)
            raise
        return self.result()

    def result(self):
        return deepcopy({
            "fixture": self.fixture,
            "catalogAddress": self.address,
            "catalogPatch": {
                "applied": self.applied,
                "restored": self.restored,
                "restoredSha256": (hashlib.sha256(self.source).hexdigest()
                                    if self.restored else None),
            },
            "failure": self.failure,
            "guestMemoryWriteBytes": self.write_bytes,
            "guestMemoryWriteOperations": self.write_operations,
            "acceptedProof": False,
        })


class NativeConditionControllerObserver(NativeMountedPacingObserver):
    """Observe one real Wild wrapper and inject one retained-target fault."""

    def __init__(self, session, subject, max_frames, fixture):
        super().__init__(session, subject, max_frames)
        _require(isinstance(fixture, LiveConditionControllerFixture)
                 and fixture.applied and not fixture.restored,
                 "live catalog fixture is not active")
        self.fixture_owner = fixture
        self.slot = subject.get("handle", {}).get("slot")
        self.calls = {"adapter": 0, "wrapper": 0}
        self.adapter_records = []
        self.wrapper_records = []
        self.active_wrappers = []
        self.controlled_state_reset = None
        self.target_fault = None
        self.cleanup_errors = []
        self.hooks_removed = False

    def _require(self, value, reason):
        if not value:
            self.failure = self.failure or "condition controller: " + reason
            raise ConditionControllerObservationFailure(self.failure)

    def _current(self):
        from tools.overworld.devtools_runtime import actor_identity_checks
        session, rt, slot = self.session, self.session.rt, self.slot
        self._require(type(slot) is int and 0 <= slot < 6,
                      "subject is not a Wild slot")
        actor = rt.actor_state(session.emu, slot)
        source = rt.wild_spawn(session.emu, slot)
        engine = rt.live_wild_object_identity(session.emu, slot)
        world = self.observer._world_context()
        self._require(all(actor_identity_checks(
            actor, source, engine, world, slot).values())
            and actor.get("active") is True
            and actor.get("species") == SUBJECT_SPECIES
            and actor.get("role") == SUBJECT_ROLE
            and actor.get("presentationAttached") is True,
            "current Wild Weepinbell binding differs")
        checked = {**actor, "identityVerified": True,
                   "engineIdentity": engine, "sourceIdentity": source}
        select_current_actor({"actors": [checked], "context": world,
                              "frame": session.completed_frames}, self.subject)
        return checked

    def _target(self, handle):
        from tools.overworld.devtools_runtime import actor_identity_checks
        rt, emu = self.session.rt, self.session.emu
        slot = handle["slot"]
        self._require(0 <= slot < 10, "target slot differs")
        actor = rt.actor_state(emu, slot)
        source = rt.wild_spawn(emu, slot)
        engine = rt.live_wild_object_identity(emu, slot)
        world = self.observer._world_context()
        self._require(actor.get("active") is True
            and actor.get("handle") == handle
            and actor.get("role") == TARGET_ROLE
            and actor.get("presentationAttached") is True
            and all(actor_identity_checks(
                actor, source, engine, world, slot).values()),
            "condition target is not the current live Follower")
        return {**actor, "identityVerified": True,
                "sourceIdentity": source, "engineIdentity": engine}

    def _runtime(self, value):
        return _pointer(value, RUNTIME_MIN_BYTES)

    def _prepared(self, runtime):
        prepared = runtime + self.slot * PREPARED_ACTOR_BYTES
        count = self.session.rt.unsigned(
            self.session.emu, prepared + PREPARED_COUNT_OFFSET, 1)
        valid = self.session.rt.unsigned(
            self.session.emu, prepared + PREPARED_VALID_OFFSET, 1)
        capacity = self.session.rt.unsigned(
            self.session.emu, prepared + PREPARED_CAPACITY_OFFSET, 2)
        self._require(valid == 1 and 1 <= count <= 32,
                      "prepared condition owner differs")
        self._require(capacity == count,
                      "prepared condition state capacity differs")
        states = _pointer(self.session.rt.unsigned(
            self.session.emu,
            prepared + PREPARED_STATE_POINTER_OFFSET,
        ), count * 16)
        catalog_index = self.fixture_owner.fixture["condition"]["index"]
        matches = [index for index in range(count)
                   if self.session.rt.unsigned(
                       self.session.emu,
                       prepared + PREPARED_CATALOG_INDICES_OFFSET + index,
                       1) == catalog_index]
        self._require(len(matches) == 1,
                      "controlled condition is not prepared exactly once")
        return matches[0], states

    def _resolution(self, runtime, prepared_index, state_pointer):
        session, rt, emu = self.session, self.session.rt, self.session.emu
        result = public_bytes(session, runtime + RUNTIME_RESULT_OFFSET, 540)
        entry_flags = rt.unsigned(
            emu, runtime + RUNTIME_SCRATCH_OFFSET + prepared_index, 1)
        state = public_bytes(
            session,
            state_pointer + prepared_index * 16,
            16,
        )
        self._require(result[20] == 2 and result[21] == 0
            and struct.unpack_from("<H", result, 22)[0] == CONDITION_ID
            and result[24] == CONDITION_APPLICATION
            and result[25] == CONDITION_APPLICATION
            and struct.unpack_from("<H", result, 26)[0] == CONDITION_ID,
            "condition result winner or target source differs")
        handle = _handle(result[8:20])
        target = self._target(handle)
        active_mask = rt.unsigned(
            emu, runtime + RUNTIME_ACTIVE_MASKS_OFFSET + self.slot * 4)
        target_valid = bool(rt.unsigned(
            emu, runtime + RUNTIME_TARGET_VALID_OFFSET, 2) & (1 << self.slot))
        return {
            "condition": {
                "id": CONDITION_ID,
                "applicationIndex": CONDITION_APPLICATION,
                "active": bool(entry_flags & 1),
                "conditionTrue": bool(entry_flags & 2),
                "triggered": bool(entry_flags & 4),
                "timed": True,
                "durationFrames": self.fixture_owner.fixture["condition"]
                    ["durationFrames"],
                "cooldownFrames": self.fixture_owner.fixture["condition"]
                    ["cooldownFrames"],
                "activeUntil": struct.unpack_from("<I", state, 0)[0],
                "cooldownUntil": struct.unpack_from("<I", state, 4)[0],
            },
            "activeApplicationMask": active_mask,
            "resolvedTarget": {
                "kind": "ACTOR",
                "role": TARGET_ROLE,
                "handle": handle,
                "position": [target["logical"]["x"],
                             target["logical"]["y"]],
            },
            "targetValid": target_valid,
            "profileHex": public_bytes(
                session, runtime + RUNTIME_RESOLUTION_OFFSET, 144).hex(),
        }

    def _before_wrapper(self):
        regs = self.session.emu.memory.register_arm9
        if regs.r2 != self.slot:
            return None
        self._check_deadline()
        self._require(regs.r0 == self.session.rt.WILD_STATE,
                      "Wild wrapper state argument differs")
        self._require(len(self.active_wrappers) == 0
                      and self.calls["wrapper"] < MAX_CALLS,
                      "Wild wrapper nesting or call bound differs")
        value = {
            "subject": deepcopy(self.subject),
            "slot": self.slot,
            "profilePointer": _public_pointer(regs.r3, 144),
            "fieldPointer": regs.r1 & 0xFFFFFFFF,
            "motionAtEntry": {
                "phase": self._current()["motionPhase"],
                "kind": self._current()["motionKind"],
            },
        }
        self.calls["wrapper"] += 1
        self.active_wrappers.append(value)
        self.data.append(value)
        return value

    def _after_wrapper(self, value, context):
        try:
            self._require(self.active_wrappers == [value],
                          "Wild wrapper return owner differs")
            result = context["returnValue"]
            flags = result & 0xFF
            direction = result >> 8
            self._require(0 <= flags <= 7 and 0 <= direction <= 7,
                          "Wild wrapper result flags differ")
            self._require(bool(self.adapter_records),
                          "Wild wrapper returned without an adapter call")
            latest = self.adapter_records[-1]
            self._require(latest["wrapperCall"] == self.calls["wrapper"],
                          "Wild wrapper did not own one adapter call")
            runtime = latest["runtimePointer"]
            active = self.session.rt.unsigned(
                self.session.emu,
                runtime + RUNTIME_ACTIVE_MASKS_OFFSET + self.slot * 4,
            )
            valid = bool(self.session.rt.unsigned(
                self.session.emu, runtime + RUNTIME_TARGET_VALID_OFFSET, 2)
                & (1 << self.slot))
            receipt = {
                **{key: deepcopy(value[key])
                   for key in ("subject", "slot", "motionAtEntry")},
                "resultFlags": flags,
                "triggerDirection": direction,
                "activeApplicationMaskAfter": active,
                "targetValidAfter": valid,
                "meaning": ("return from the real Wild intent-boundary "
                            "condition wrapper"),
            }
            if (flags & 4) == 0:
                receipt["profileHex"] = public_bytes(
                    self.session, value["profilePointer"], 144).hex()
                self._require(receipt["profileHex"] == latest["profileHex"],
                              "Wild wrapper did not receive adapter profile")
            self.wrapper_records.append(deepcopy(receipt))
            return receipt
        finally:
            if value in self.active_wrappers:
                self.active_wrappers.remove(value)
            if value in self.data:
                self.data.remove(value)

    def _before_adapter(self):
        regs = self.session.emu.memory.register_arm9
        if not self.active_wrappers:
            return None
        self._check_deadline()
        stack = public_bytes(self.session, regs.sp & 0xFFFFFFFF, 32)
        words = struct.unpack("<8I", stack)
        runtime, state, field, blob = (
            getattr(regs, name) & 0xFFFFFFFF
            for name in ("r0", "r1", "r2", "r3"))
        self._require(state == self.session.rt.WILD_STATE
            and field == self.active_wrappers[-1]["fieldPointer"]
            and blob == self.fixture_owner.address
            and words[0] == len(self.fixture_owner.patched)
            and words[1] == self.slot
            and self.calls["adapter"] < MAX_CALLS,
            "condition adapter arguments differ from the Wild wrapper")
        prepared_index, state_pointer = self._prepared(runtime)
        if self.controlled_state_reset is None:
            state_address = state_pointer + prepared_index * 16
            mask_address = (runtime + RUNTIME_ACTIVE_MASKS_OFFSET
                            + self.slot * 4)
            state_before = self.session.read(state_address, 16)
            mask_before = self.session.read(mask_address, 4)
            state_after = bytes(16)
            mask_after = bytes(4)
            self.session.write(state_address, state_after)
            self.session.write(mask_address, mask_after)
            self.fixture_owner.write_bytes += len(state_after) + len(mask_after)
            self.fixture_owner.write_operations += 2
            self._require(self.session.read(state_address, len(state_after))
                          == state_after,
                          "controlled condition state did not reset")
            self._require(self.session.read(mask_address, len(mask_after))
                          == mask_after,
                          "controlled profile cache did not reset")
            self.controlled_state_reset = {
                "stateAddress": state_address,
                "activeApplicationMaskAddress": mask_address,
                "preparedIndex": prepared_index,
                "stateBeforeHex": state_before.hex(),
                "stateAfterHex": state_after.hex(),
                "activeApplicationMaskBeforeHex": mask_before.hex(),
                "activeApplicationMaskAfterHex": mask_after.hex(),
                "bytesWritten": len(state_after) + len(mask_after),
                "writeOperations": 2,
                "meaning": ("clear the controlled condition state and its "
                            "cached active profile before the first observed "
                            "call"),
            }
        value = {
            "subject": deepcopy(self.subject),
            "slot": self.slot,
            "runtimePointer": self._runtime(runtime),
            "statePointer": state_pointer,
            "outcomePointer": _public_pointer(words[7], 8),
            "preparedIndex": prepared_index,
            "wrapperCall": self.calls["wrapper"],
            "motionAtEntry": deepcopy(
                self.active_wrappers[-1]["motionAtEntry"]),
        }
        self.calls["adapter"] += 1
        self.data.append(value)
        return value

    def _after_adapter(self, value, context):
        try:
            status = context["returnValue"]
            self._require(status in (0, 3),
                          "condition adapter returned unexpected status "
                          + str(status))
            receipt = {**deepcopy(value), "status": status,
                       "caller":
                       "OverworldWildSpawns_EvaluateConditionsForSlot"}
            if status == 0:
                receipt.update(self._resolution(
                    value["runtimePointer"], value["preparedIndex"],
                    value["statePointer"]))
                self._require(receipt["condition"]["id"] == CONDITION_ID
                    and receipt["condition"]["applicationIndex"]
                        == CONDITION_APPLICATION
                    and receipt["activeApplicationMask"]
                        & (1 << CONDITION_APPLICATION)
                    and receipt["targetValid"] is True
                    and all(decode_profile(receipt["profileHex"])[key] == item
                            for key, item in expected_profile().items()),
                    "successful conditional resolution differs")
            else:
                runtime = value["runtimePointer"]
                receipt.update({
                    "staleTarget": self.target_fault["after"]
                        if self.target_fault else None,
                    "activeApplicationMask": self.session.rt.unsigned(
                        self.session.emu,
                        runtime + RUNTIME_ACTIVE_MASKS_OFFSET
                        + self.slot * 4),
                    "targetValid": bool(self.session.rt.unsigned(
                        self.session.emu,
                        runtime + RUNTIME_TARGET_VALID_OFFSET, 2)
                        & (1 << self.slot)),
                })
            self.adapter_records.append(deepcopy(receipt))
            return receipt
        finally:
            if value in self.data:
                self.data.remove(value)

    def _inject_stale_target(self, actor):
        latest = self.adapter_records[-1]
        target = latest["resolvedTarget"]["handle"]
        runtime = latest["runtimePointer"]
        state_pointer = latest["statePointer"]
        prepared = latest["preparedIndex"]
        address = target_generation_address(state_pointer, prepared)
        original = self.session.read(address, 2)
        before = int.from_bytes(original, "little")
        after = stale_generation(before)
        self._require(before == target["generation"],
                      "retained target generation differs before fault")
        target_before = deepcopy(self._target(target))
        self.session.write(address, after.to_bytes(2, "little"))
        self.fixture_owner.write_bytes += 2
        self.fixture_owner.write_operations += 1
        self._require(self.session.read(address, 2)
                      == after.to_bytes(2, "little")
                      and self._target(target) == target_before,
                      "stale-target fault changed more than retained generation")
        self.target_fault = {
            "subject": deepcopy(self.subject),
            "runtimePointer": runtime,
            "statePointer": state_pointer,
            "preparedIndex": prepared,
            "targetHandle": target,
            "before": before,
            "after": after,
            "address": address,
            "bytesWritten": 2,
            "actorTargetUnchanged": True,
            "motionAtWrite": {"phase": actor["motionPhase"],
                              "kind": actor["motionKind"]},
        }
        clock = self.observer._clock()
        context = {"entry": clock, "returned": clock,
                   "setupMode": "prepared", "returnValue": 0}
        self.observer._queue("condition-controller-target-staled", context,
                             deepcopy(self.target_fault))

    def arm(self):
        self._require(not self.armed and not self.closed,
                      "reader can arm only once")
        self._require(type(self.maximum) is int and 1 <= self.maximum <= 600,
                      "invalid frame limit")
        self.started = self.session.completed_frames
        try:
            self.owner = self._current()
            self._require(self.owner["motionPhase"]
                          in ("IDLE", "MOVING", "SETTLING")
                          and isinstance(self.owner["motionKind"], str),
                          "subject has no live motion state at arm")
            self.armed = True

            def linked(label, _path, _symbols, name, before, after, **kwargs):
                rt = self.session.rt
                actor = label == "condition-controller-evaluate"
                path = rt.REPO / ("build/overworld_actor_system_overlay_linked.o"
                                  if actor else
                                  "build/overworld_wild_spawns_overlay_linked.o")
                symbols = (rt.ACTOR_SYMBOLS if actor else rt.WILD_SYMBOLS)
                address = rt.linked_symbol(symbols, name) & ~1
                self.observer._tap(
                    label, address, self.observer.elf_code(path, address, 32),
                    before, after,
                    scope=lambda: self.armed and not self.closed,
                    resident=True,
                )

            self.linked = linked
            self._install(
                "condition-controller-wrapper",
                "OverworldWildSpawns_EvaluateConditionsForSlot",
                self._before_wrapper,
                self._after_wrapper,
            )
            self._install(
                "condition-controller-evaluate",
                "OverworldBehaviorConditionAdapter_EvaluateActor",
                self._before_adapter,
                self._after_adapter,
            )
            return self.result()
        except Exception as error:
            self.failure = self.failure or str(error)
            self.close(disposing=True)
            raise

    def completed_boundary(self):
        self._check_deadline()
        if not self.armed or self.closed:
            return
        actor = self._current()
        if (self.target_fault is None
                and len([item for item in self.adapter_records
                         if item["status"] == 0]) >= 2
                and actor["motionPhase"] == "MOVING"
                and actor["motionKind"] == "HOP"):
            self._inject_stale_target(actor)

    def close(self, disposing=False):
        if self.closed:
            return self.result()
        try:
            if not disposing:
                self._require(self.target_fault is not None,
                              "stale-target fault was not applied")
            result = super().close(disposing=disposing)
            self.hooks_removed = not any(
                token in collection
                for token in self.entries + self.returns
                for collection in (self.observer.tokens,
                                   self.observer.return_tokens)
            )
            self.fixture_owner.restore()
            return self.result() if result is not None else self.result()
        except Exception as error:
            self.failure = self.failure or str(error)
            try:
                if self.fixture_owner.applied and not self.fixture_owner.restored:
                    self.fixture_owner.restore()
            except Exception as cleanup_error:
                self.cleanup_errors.append(str(cleanup_error))
            raise

    def result(self):
        fixture = self.fixture_owner.result()
        callback_names = {
            "adapterEvaluate": "condition-controller-evaluate",
            "wildEvaluate": "condition-controller-wrapper",
        }
        callbacks = {
            public: deepcopy(self.observer.calls[native])
            for public, native in callback_names.items()
            if native in self.observer.calls
        }
        return deepcopy({
            "armed": self.armed,
            "closed": self.closed,
            "failure": self.failure or fixture["failure"],
            "subject": self.subject,
            "startFrame": self.started,
            "maxFrames": self.maximum,
            "fixture": fixture["fixture"],
            "catalogPatch": fixture["catalogPatch"],
            "callbacks": callbacks,
            "counts": deepcopy(self.calls),
            "controlledStateReset": deepcopy(self.controlled_state_reset),
            "targetFault": deepcopy(self.target_fault),
            "guestMemoryWriteBytes": fixture["guestMemoryWriteBytes"],
            "guestMemoryWriteOperations": fixture["guestMemoryWriteOperations"],
            "hookCleanup": {
                "removed": self.closed and self.hooks_removed,
                "errors": deepcopy(self.cleanup_errors),
            },
            "acceptedProof": False,
            "scope": ("controlled live Wild caller; authored profile unchanged; "
                      "no Follower-caller or mounted-exclusion credit"),
        })

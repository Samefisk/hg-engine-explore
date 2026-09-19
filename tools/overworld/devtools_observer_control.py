"""Two fixed native faults for the shared observer's known-bad controls.

No hooks, core, input loop, public address argument, or gameplay setup lives
here. The session invokes completed_boundary before its real snapshot. The
caller must first prove the exact subject's natural spawn and Hop baseline.
These writes are observer controls, never normal-play behavior proof.
"""
from __future__ import annotations

from copy import deepcopy
import struct

from tools.overworld.devtools_records import _subject, GENERATION_FIELDS


class ObserverControlFailure(RuntimeError):
    code = "observer-control-failed"

    def __init__(self, message, *, details=None, fatal=False):
        super().__init__(message)
        self.details, self.fatal = details, fatal


class NativeObserverControl:
    """One bounded fault tied to a freshly revalidated native WILD Ledyba."""

    KINDS = ("render-stall", "inactive-object")

    def __init__(self, session, subject):
        self.session = session
        self.subject = _subject(subject)
        if self.subject["species"] != 165 or self.subject["role"] != "WILD" \
                or not 0 <= self.subject["handle"]["slot"] < 7:
            raise ValueError("observer control requires an exact WILD Ledyba subject")
        self.state, self.kind = "new", None
        self.receipts, self.failure = [], None
        self.binding, self.pinned = None, None
        self.armed_frame = self.last_frame = None
        self.max_frames, self.writes = None, 0
        self.inactive_owned = False
        self.closed = False

    def _fail(self, message, *, fatal=False):
        if self.failure is None:
            self.failure = {"message": message, "frame": self.session.completed_frames,
                            "kind": self.kind, "subject": deepcopy(self.subject)}
        self.state = "failed"
        raise ObserverControlFailure(message, details=self.result(), fatal=fatal or self.inactive_owned)

    def _current(self, *, allow_inactive=False):
        try:
            return self._read_current(allow_inactive=allow_inactive)
        except ObserverControlFailure:
            raise
        except Exception as error:
            self._fail("observer control native read failed: " + str(error)[:240],
                       fatal=self.inactive_owned)

    def _read_current(self, *, allow_inactive=False):
        # Lazy import permits the session to import this module at startup.
        from tools.overworld.devtools_runtime import actor_identity_checks
        s, rt = self.session, self.session.rt
        if s.emu is None or s.closed:
            self._fail("observer control session is closed")
        if s.native_bridge_active:
            self._fail("observer control cannot run inside a prepared native call")
        state = rt.ACTOR_DESCRIPTOR["state"]
        offsets, address = state["offsets"], state["address"]
        if offsets.get("fieldEpoch") != 12 or offsets.get("mapGeneration") != 46 \
                or rt.unsigned(s.emu, address) != 0x5353574F:
            self._fail("observer control context ABI is unavailable")
        slot = self.subject["handle"]["slot"]
        actor = rt.actor_state(s.emu, slot)
        source = rt.wild_spawn(s.emu, slot)
        engine = rt.live_wild_object_identity(s.emu, slot)
        context = {"fieldEpoch": rt.unsigned(s.emu, address + 12, 2),
                   "mapGeneration": rt.unsigned(s.emu, address + 46, 2),
                   "mapId": rt.field_map_id(s.emu)}
        checks = actor_identity_checks(actor, source, engine, context, slot)
        checks.update(activeActor=actor.get("active") is True,
                      exactSubject=_subject(actor) == self.subject,
                      exactSourcePointer=source.get("object") == engine.get("pointer"),
                      sourceForm=actor.get("form") == source.get("form"),
                      sourceLevel=actor.get("level") == source.get("level"))
        lookup = engine.get("id_lookup", {})
        if allow_inactive:
            # Only the single bit deliberately cleared by this instance may
            # differ. The native reader must still find this exact typed row.
            rows = lookup.get("matching_objects", [])
            exact = [row for row in rows if row.get("pointer") == source.get("object")]
            checks["engineActive"] = self.inactive_owned
            checks["stockLookup"] = (lookup.get("status") == "complete" and len(exact) == 1
                                      and not exact[0].get("flag25")
                                      and all(not row.get("lookup_eligible") for row in rows
                                              if row.get("pointer") != source.get("object")))
        else:
            checks["stockLookup"] = (lookup.get("status") == "complete"
                                      and lookup.get("pointer_matches") is True
                                      and lookup.get("eligible_count") == 1)
        pointer = source.get("object", 0)
        checks["objectSpan"] = (isinstance(pointer, int) and pointer % 4 == 0
                                 and 0x02000000 <= pointer <= 0x02400000 - 0x12C)
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            self._fail("observer control lost native identity: " + ", ".join(failed))
        binding = {"source": {key: source[key] for key in
                              ("object", "personality", "map_id", "species", "form", "level",
                               "active", "object_id", "encounter_generation")},
                   "currentManager": engine["current_manager"],
                   "managerIndex": engine["manager_index"], "context": context,
                   **{key: actor[key] for key in GENERATION_FIELDS}}
        if self.binding is not None and binding != self.binding:
            self._fail("observer control object, owner, or presentation generation changed")
        return actor, source, engine, context, rt.object_state(s.emu, pointer), binding

    def _receipt(self, action, current, **data):
        actor, source, engine, context, _pose, _binding = current
        receipt = {"type": "native-observer-control-v1", "kind": self.kind,
                   "action": action, "frame": self.session.completed_frames,
                   "nativeCycle": self.session.rt.EXECUTED_FRAME_COUNT,
                   "subject": deepcopy(self.subject), "sourceIdentity": deepcopy(source),
                   "engineIdentity": deepcopy(engine), "context": deepcopy(context),
                   "generations": {key: actor[key] for key in GENERATION_FIELDS}, **data}
        self.receipts.append(receipt)
        return deepcopy(receipt)

    def arm(self, kind, max_frames=1200):
        if self.state != "new" or self.closed:
            raise ValueError("observer control is single-use")
        if kind not in self.KINDS or type(max_frames) is not int or not 1 <= max_frames <= 5000:
            raise ValueError("unknown observer control or invalid completed-frame bound")
        self.kind, self.max_frames = kind, max_frames
        current = self._current()
        self.binding = current[-1]
        self.armed_frame = self.last_frame = self.session.completed_frames
        self.state = "armed"
        self._receipt("armed", current, maxFrames=max_frames)
        return self.result()

    def completed_boundary(self):
        try:
            return self._apply_completed_boundary()
        except ObserverControlFailure:
            raise
        except Exception as error:
            self._fail("observer control native callback failed: " + str(error)[:240], fatal=True)

    def _apply_completed_boundary(self):
        if self.closed or self.state in ("new", "failed", "complete"):
            return []
        before_count = len(self.receipts)
        frame = self.session.completed_frames
        if frame == self.last_frame:
            return []  # The callback cannot apply twice to one completed frame.
        if frame != self.last_frame + 1:
            self._fail("observer control missed a completed frame")
        self.last_frame = frame
        if frame - self.armed_frame > self.max_frames:
            self._fail("observer control completed-frame deadline expired")
        current = self._current(allow_inactive=self.inactive_owned)
        actor, source, _engine, _context, pose, _binding = current
        pointer = source["object"]
        if self.kind == "inactive-object":
            flags = pose["flags"]
            # Own this bit before writing: failed readback still needs cleanup.
            self.inactive_owned = True
            try:
                self.session.rt.actor_memory_write(self.session.emu, pointer,
                                                   struct.pack("<I", flags & ~1))
            except Exception as error:
                self._fail("inactive-object control write failed: " + str(error)[:240], fatal=True)
            actual = self.session.rt.unsigned(self.session.emu, pointer)
            self._receipt("active-bit-cleared", current, beforeFlags=flags, afterFlags=actual)
            if actual != flags & ~1:
                self._fail("inactive-object control flag readback differs", fatal=True)
            self.state, self.writes = "complete", 1
        elif self.pinned is None:
            if actor["motionKind"] != "WALK" or actor["motionPhase"] != "MOVING" \
                    or actor["motionElapsed"] not in (0, 1):
                return []
            if actor["origin"] == actor["target"] \
                    or actor["motionDuration"] <= actor["motionElapsed"] + 2:
                return []
            self.pinned = {"pose": {key: pose[key] for key in ("pos_x", "pos_z")},
                           "origin": deepcopy(actor["origin"]), "target": deepcopy(actor["target"]),
                           "duration": actor["motionDuration"], "elapsed": actor["motionElapsed"],
                           "commitSequence": actor["commitSequence"]}
            self.state = "applying"
            self._receipt("render-pinned", current, beforePose=deepcopy(pose), afterPose=deepcopy(pose),
                          motion=deepcopy(self.pinned))
        else:
            pin = self.pinned
            if actor["motionKind"] != "WALK" or actor["motionPhase"] != "MOVING" \
                    or actor["origin"] != pin["origin"] or actor["target"] != pin["target"] \
                    or actor["motionDuration"] != pin["duration"] \
                    or actor["motionElapsed"] != pin["elapsed"] + self.writes + 1 \
                    or actor["commitSequence"] != pin["commitSequence"]:
                self._fail("render-stall control's exact motion changed before two samples")
            try:
                for key, offset in (("pos_x", 0x70), ("pos_z", 0x78)):
                    self.session.rt.actor_memory_write(self.session.emu, pointer + offset,
                                                       struct.pack("<i", pin["pose"][key]))
            except Exception as error:
                self._fail("render-stall control write failed: " + str(error)[:240], fatal=True)
            after = self.session.rt.object_state(self.session.emu, pointer)
            self._receipt("render-restored", current, beforePose=deepcopy(pose), afterPose=deepcopy(after),
                          motionElapsed=actor["motionElapsed"])
            if any(after[key] != value for key, value in pin["pose"].items()) \
                    or any(after[key] != value for key, value in pose.items() if key not in pin["pose"]):
                self._fail("render-stall control pose readback differs", fatal=True)
            self.writes += 1
            if self.writes == 2:
                self.state = "complete"
        return deepcopy(self.receipts[before_count:])

    def close(self):
        if self.closed:
            return self.result()
        try:
            if self.inactive_owned:
                current = self._current(allow_inactive=True)
                flags = current[4]["flags"]
                pointer = current[1]["object"]
                try:
                    self.session.rt.actor_memory_write(self.session.emu, pointer,
                                                       struct.pack("<I", flags | 1))
                except Exception as error:
                    self._fail("inactive-object cleanup write failed: " + str(error)[:240], fatal=True)
                actual = self.session.rt.unsigned(self.session.emu, pointer)
                self._receipt("active-bit-restored", current, beforeFlags=flags, afterFlags=actual)
                if actual != flags | 1:
                    self._fail("inactive-object cleanup readback differs", fatal=True)
                self.inactive_owned = False
            elif self.state in ("armed", "applying"):
                self._fail("observer control closed before the fault completed")
        finally:
            self.closed = True
        return self.result()

    def result(self):
        return deepcopy({"schemaVersion": 1, "kind": self.kind, "state": self.state,
                         "subject": self.subject, "writes": self.writes, "closed": self.closed,
                         "cleanupPending": self.inactive_owned, "failure": self.failure,
                         "receipts": self.receipts, "scope": "native-observer-control-only"})

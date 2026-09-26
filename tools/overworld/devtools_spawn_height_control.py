"""One native height-reader calibration; no core, input or acceptance owner."""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import _copy_json


class SpawnHeightControlFailure(RuntimeError):
    code = "spawn-height-control-failed"

    def __init__(self, message, *, fatal=False):
        super().__init__(message)
        self.fatal = fatal


class NativeSpawnHeightReadControl:
    """Temporarily change only native Y while the authenticated reader runs."""

    def __init__(self):
        self.state = "new"
        self.receipt = None
        self.failure = None
        self.cleanup_pending = False

    def arm(self):
        if self.state != "new":
            raise ValueError("spawn height control is single-use")
        self.state = "armed"
        return self.result()

    @staticmethod
    def _need(value, message):
        if not value:
            raise ValueError(message)

    def _identity(self, session, record, clean):
        need, rt, emu = self._need, session.rt, session.emu
        need(not session.closed and emu is not None and not session.native_bridge_active,
             "spawn height control needs a live normal native callback")
        source, world, slot = clean["sourceIdentity"], clean["worldContext"], clean["slot"]
        need(type(slot) is int and 0 <= slot < 7 and source["species"] == 179
             and source["active"] and source["encounter_generation"] > 0,
             "spawn height control needs an active Wild Mareep encounter")
        pointer = source["object"]
        need(type(pointer) is int and pointer % 4 == 0
             and 0x02000000 <= pointer <= 0x02400000 - 0x12C, "invalid native object span")
        need(rt.wild_spawn(emu, slot) == source, "native encounter changed")
        state = rt.ACTOR_DESCRIPTOR["state"]
        actual_world = {"fieldPointer": rt.unsigned(emu, rt.G_FIELD_SYS_PTR),
                        "statePointer": rt.WILD_STATE, "mapId": rt.field_map_id(emu),
                        **{key: rt.unsigned(emu, state["address"] + state["offsets"][key], 2)
                           for key in ("fieldEpoch", "mapGeneration")}}
        need(actual_world == world and all(world[k] > 0 for k in ("fieldEpoch", "mapGeneration")),
             "native world changed")
        engine = rt.live_wild_object_identity(emu, slot)
        need(engine == clean["engineIdentity"] == clean["engineIdentityAfter"], "native binding changed")
        lookup = engine["id_lookup"]
        need(engine["pointer"] == pointer and engine["active"] and engine["in_manager"]
             and engine["object_manager"] == engine["current_manager"]
             and engine["object_id"] == source["object_id"]
             and engine["object_map_id"] == world["mapId"] == source["map_id"]
             and engine["script_id"] == 2074 and lookup["status"] == "complete"
             and lookup["eligible_count"] == 1 and lookup["pointer_matches"] is True,
             "native Wild ownership is unavailable")
        parent = record["_spawn"]
        need(record.get("initialPlacement") is True
             and parent["startup"]["locomotion"] == 7
             and parent["startup"]["target"] == parent["position"] == clean["target"]
             and parent["slot"] == slot and parent["worldContext"] == world
             and parent["preparedPointer"] == clean["preparedPointer"]
             and parent["preparedEncounter"] == clean["preparedEncounter"]
             and all(source[key] == value for key, value in clean["preparedEncounter"].items()),
             "native landing is not its own prepared target")
        need(record["sourceIdentity"] == source and record["target"] == clean["target"],
             "native landing record changed")
        return pointer

    def capture(self, session, record, read_fn):
        clean = read_fn()
        if self.state != "armed" or clean.get("sourceIdentity", {}).get("species") != 179:
            return clean
        self.state = "capturing"
        try:
            clean = _copy_json(clean, 65536)
            pointer = self._identity(session, record, clean)
            query, refresh, pose = clean["surfaceQuery"], clean["heightRefresh"], clean["positionAfter"]
            self._need(clean["status"] == "observed" and clean["nativeReturnKind"] == "void"
                       and clean["returnValue"] is None and clean["heightSource"] == "native-refresh"
                       and query["returnValue"] == 0 and query["hit"] is None
                       and refresh["returnValue"] == 1 and refresh["objectPointer"] == pointer
                       and not refresh["positionBefore"]["flags"] & (1 << 23)
                       and refresh["positionAfter"]["pos_y"] == pose["pos_y"]
                       and [pose["x"], pose["y"]] == clean["target"], "native height baseline is incomplete")
            original = session.read(pointer + 0x74, 4)
            self._need(len(original) == 4 and struct.unpack("<i", original)[0] == pose["pos_y"],
                       "native height bytes differ from reader")
            wrong_y = pose["pos_y"] + 4096
            self._need(-(1 << 31) <= wrong_y < 1 << 31, "height fault would overflow")
            bad = None
            self.cleanup_pending = True
            try:
                session.rt.actor_memory_write(session.emu, pointer + 0x74, struct.pack("<i", wrong_y))
                bad = _copy_json(read_fn(), 65536)
                expected = deepcopy(clean)
                expected["positionAfter"]["pos_y"] = wrong_y
                self._need(bad == expected, "same native reader did not observe only the height fault")
            finally:
                # Even an identity/read failure cannot leave our four owned
                # bytes changed. No emulated instruction ran in this scope.
                identity_error = None
                try:
                    self._identity(session, record, clean)
                except Exception as error:
                    identity_error = error
                try:
                    session.rt.actor_memory_write(session.emu, pointer + 0x74, original)
                    self._need(session.read(pointer + 0x74, 4) == original, "height restoration readback differs")
                    self.cleanup_pending = False
                except Exception as error:
                    raise SpawnHeightControlFailure("native height restoration failed: " + str(error)[:200], fatal=True) from error
                if identity_error is not None:
                    raise SpawnHeightControlFailure("native height identity changed during control: " + str(identity_error)[:200], fatal=True)
            restored = _copy_json(read_fn(), 65536)
            self._need(restored == clean, "restored native height reader differs")
            self.receipt = {"clean": clean, "bad": bad, "restored": restored,
                            "delta": 4096, "writes": 2, "frame": session.completed_frames,
                            "nativeCycle": session.rt.EXECUTED_FRAME_COUNT}
            self.state = "complete"
            return clean
        except Exception as error:
            self.state = "failed"
            self.failure = str(error)[:240]
            if isinstance(error, SpawnHeightControlFailure):
                raise
            raise SpawnHeightControlFailure(self.failure, fatal=self.cleanup_pending) from error

    def result(self):
        return deepcopy({"state": self.state, "receipt": self.receipt,
                         "failure": self.failure, "cleanupPending": self.cleanup_pending,
                         "scope": "native-observer-control-only", "acceptedProof": False})

"""Opt-in native owner-context receipts; read-only, never an acquisition verdict."""
from copy import deepcopy
import struct

from tools.overworld.devtools_observer import NativeObservationError

FUNCTION = "OverworldActorSystem_CompatibilityGetContextImpl"
LABEL = "actor-binding-context"
MAX_RECEIPTS = 1024


def install_binding_context(observer, linked):
    return BindingContextObserver(observer, linked)


class BindingContextObserver:
    def __init__(self, observer, linked):
        self.observer, self.session = observer, observer.session
        self.linked = linked
        self.enabled = False
        self.last_frame = None
        self.count = 0

    def enable(self):
        """Install once on explicit opt-in; never reset receipt/rate limits."""
        if self.enabled:
            return
        rt = self.session.rt
        self.descriptor = deepcopy(rt.ACTOR_DESCRIPTOR)
        table = self.descriptor["compatibility"]
        self.address = rt.linked_symbol(rt.ACTOR_SYMBOLS, FUNCTION) & ~1
        if (table.get("version") != 3 or table.get("size") != 32
                or table.get("callbacks", {}).get("getContext") != (self.address | 1)):
            raise NativeObservationError("binding context compatibility descriptor differs")
        self.table_address = table["address"]
        self._pointer(self.table_address, 32)
        self.table_bytes = self._packaged(self.table_address, 32)
        magic, version, size = struct.unpack_from("<IHH", self.table_bytes)
        if ((magic, version, size) != (0x4341574F, 3, 32)
                or struct.unpack_from("<I", self.table_bytes, 28)[0] != (self.address | 1)):
            raise NativeObservationError("binding context packaged compatibility entry differs")
        state = self.descriptor["state"]
        if rt.linked_symbol(rt.ACTOR_SYMBOLS, "gOverworldActorSystemState") != state["address"]:
            raise NativeObservationError("binding context defining state symbol differs")
        self._pointer(state["address"], state["size"])
        for key in ("fieldEpoch", "mapGeneration"):
            offset = state["offsets"][key]
            if type(offset) is not int or offset % 2 or not 0 <= offset <= state["size"] - 2:
                raise NativeObservationError("binding context state layout differs")
        self.linked(LABEL, rt.REPO / "build/overworld_actor_system_overlay_linked.o",
               rt.ACTOR_SYMBOLS, FUNCTION, self._before, self._after,
               scope=self._scope, resident=True)
        self.enabled = True

    def _scope(self):
        return self.enabled

    @staticmethod
    def _pointer(address, size):
        if (type(address) is not int or address % 4 or type(size) is not int
                or size <= 0 or not 0x02000000 <= address <= 0x02400000 - size):
            raise NativeObservationError("binding context pointer outside aligned RAM")

    def _read(self, address, size):
        data = self.session.read(address, size)
        if not isinstance(data, (bytes, bytearray)) or len(data) != size:
            raise NativeObservationError("binding context short native read")
        return bytes(data)

    def _packaged(self, address, size):
        for base, data in self.session.code_regions:
            if base <= address <= base + len(data) - size:
                return bytes(data[address-base:address-base+size])
        raise NativeObservationError("binding context entry absent from packaged ROM")

    def _before(self):
        frame = self.observer._clock()["actorFrame"]
        if self.last_frame is not None and frame < self.last_frame:
            raise NativeObservationError("binding context actor clock regressed")
        if frame == self.last_frame:
            return None
        if self._read(self.table_address, 32) != self.table_bytes:
            raise NativeObservationError("binding context live compatibility entry differs")
        return {}

    def _after(self, before, context):
        frame = context["returned"]["actorFrame"]
        if self.last_frame is not None and frame < self.last_frame:
            raise NativeObservationError("binding context return clock regressed")
        if frame == self.last_frame:
            return None
        if self.count >= MAX_RECEIPTS:
            raise NativeObservationError("binding context receipt limit reached")
        self.last_frame, self.count = frame, self.count + 1
        packed = context["returnValue"]
        result = {"boundary": "public-getContext-return", "status": "unknown",
                  "packedContext": packed,
                  "ownerContext": {"fieldEpoch": packed & 0xffff,
                                   "mapGeneration": packed >> 16},
                  "residentContext": None, "returnMatchesResident": None, "fieldPointer": None,
                  "fieldLifecycle": None, "candidates": [], "readError": None}
        try:
            if self._read(self.table_address, 32) != self.table_bytes:
                raise NativeObservationError("binding context compatibility changed before return")
            rt, emu = self.session.rt, self.session.emu
            state = self.descriptor["state"]
            prefix = self._read(state["address"], 8)
            if struct.unpack("<IHH", prefix) != (
                0x5353574F,
                self.descriptor["facade"]["version"],
                state["size"],
            ):
                raise NativeObservationError("binding context resident state header differs")
            current = {key: int.from_bytes(self._read(state["address"] + state["offsets"][key], 2), "little")
                       for key in ("fieldEpoch", "mapGeneration")}
            result["residentContext"] = current
            result["returnMatchesResident"] = all(result["ownerContext"][key] == current[key] for key in current)
            field = self.session.field_pointer()
            result["fieldPointer"] = field
            self._pointer(field, 0x70)
            lifecycle = self.session._field_actor_availability(field)
            result["fieldLifecycle"] = deepcopy(lifecycle)
            if lifecycle.get("authenticated") is not True or lifecycle.get("reason") is not None:
                result["status"] = "field-unavailable"
                return result
            # Validate manager reads before the existing engine identity reader.
            manager = int.from_bytes(self._read(field + 0x3c, 4), "little")
            self._pointer(manager, 0x128)
            count = int.from_bytes(self._read(manager + 4, 4), "little")
            objects = int.from_bytes(self._read(manager + 0x124, 4), "little")
            if not 1 <= count <= 64:
                raise NativeObservationError("binding context object manager count differs")
            self._pointer(objects, count * 0x12c)
            map_id = rt.field_map_id(emu)
            result["ownerContext"]["mapId"] = map_id
            current["mapId"] = map_id
            from tools.overworld.devtools_runtime import actor_identity_checks
            for slot in range(min(7, self.descriptor["capacities"]["actors"])):
                actor = rt.actor_state(emu, slot)
                # Never filter on owner generations or identity check results.
                if actor.get("active") is not True or actor.get("species") != 19 or actor.get("role") != "WILD":
                    continue
                candidate = {"slot": slot, "publicSubject": deepcopy(actor),
                             "sourceIdentity": None, "engineIdentity": None,
                             "engineObject": None, "identityChecks": {}, "readError": None}
                result["candidates"].append(candidate)
                source = rt.wild_spawn(emu, slot)
                candidate["sourceIdentity"] = deepcopy(source)
                engine = rt.live_wild_object_identity(emu, slot)
                candidate["engineIdentity"] = deepcopy(engine)
                checks = actor_identity_checks(actor, source, engine, result["ownerContext"], slot)
                lookup = engine.get("id_lookup", {})
                checks.update(pointer=source.get("object") == engine.get("pointer"),
                              form=actor.get("form") == source.get("form"),
                              level=actor.get("level") == source.get("level"),
                              lookup=lookup.get("status") == "complete" and lookup.get("pointer_matches") is True
                                     and lookup.get("eligible_count") == 1)
                candidate["identityChecks"] = checks
                if engine.get("in_manager") is True:
                    pointer = engine["pointer"]
                    self._pointer(pointer, 0x12c)
                    if not objects <= pointer <= objects + count * 0x12c - 0x12c or (pointer-objects) % 0x12c:
                        raise NativeObservationError("binding context engine member differs")
                    candidate["engineObject"] = deepcopy(rt.object_state(emu, pointer))
            result["status"] = "observed"
        except Exception as error:
            result["readError"] = str(error)[:320]
            result["status"] = "unknown"
        return result

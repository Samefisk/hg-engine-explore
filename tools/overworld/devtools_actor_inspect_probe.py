"""Two fixed read-only Inspect calls through the owned FieldReturnBridge.

Only the query/output allocation is written. Host receipts are diagnostic data,
not controller acceptance. The session authenticates the linked public facade.
"""
from copy import deepcopy
import struct
import hashlib

BUFFER_BYTES = 232
QUERY = 16
OUTPUT = 40
GUARD = b"ActorInspect-v1!"
HANDLE_KEYS = ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")
GENERATION_KEYS = ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
ENGINE_OWNER_KEYS = ("pointer", "current_manager", "object_manager", "manager_index",
                     "object_id", "object_map_id", "current_map_id", "script_id", "encounter_generation")


class ActorInspectProbeError(ValueError):
    code = "actor-inspect-probe-invalid"

    def __init__(self, message, *, fatal=False):
        super().__init__(message)
        self.fatal = fatal


def require(value, message, *, fatal=False):
    if not value:
        raise ActorInspectProbeError(message, fatal=fatal)


class ActorInspectProbe:
    def __init__(self, session, *, expected_actor, service_identity):
        self.session = session
        require(isinstance(expected_actor, dict) and expected_actor.get("identityVerified") is True,
                "selected actor is not verified")
        self.expected = deepcopy(expected_actor)
        self.service = deepcopy(service_identity)
        self.field = session.field_pointer()
        self.generation = session.native_heap_generation
        self.state = deepcopy(session.rt.ACTOR_DESCRIPTOR["state"])
        structures = session.rt.ACTOR_DESCRIPTOR["structures"]
        require(all(structures.get(k) == n for k, n in
                    (("query", 24), ("snapshot", 176), ("actorState", 88))), "Inspect ABI sizes differ")
        self.capacity = session.rt.ACTOR_DESCRIPTOR["capacities"]["actors"]
        size, address, stride, offset = (self.state["size"], self.state["address"],
                                        self.state["actorStride"], self.state["offsets"]["actors"])
        require(all(type(v) is int for v in (size, address, stride, offset, self.capacity))
                and 48 <= size <= 65535 and address % 4 == 0
                and 0x02000000 <= address <= 0x02400000 - size
                and 1 <= self.capacity <= 10 and stride >= 88 and stride % 4 == 0
                and offset >= 48 and offset % 4 == 0
                and offset + self.capacity * stride <= size, "actor state layout differs")
        for name in ("fieldEpoch", "mapGeneration"):
            value = self.state["offsets"][name]
            require(type(value) is int and 0 <= value <= size - 2 and value % 2 == 0,
                    "invalid actor context offset")
        self.pointer = None
        self.started = self.completed = self.released = False
        self.receipts = []

    def _owner(self):
        s = self.session
        require(s.emu is not None and self.field and s.field_pointer() == self.field
                and s.native_heap_generation == self.generation, "actor field/heap owner changed", fatal=True)
        require(s._actor_inspect_probe_service() == self.service, "authenticated Inspect service changed", fatal=True)
        require(s.read(self.state["address"], 8) == struct.pack("<IHH", 0x5353574F, 1, self.state["size"]),
                "actor state is not initialized", fatal=True)

    def _select(self):
        self._owner()
        actors = self.session._snapshot(0, details=False)["actors"]
        matches = [a for a in actors if a.get("handle") == self.expected["handle"]]
        require(len(matches) == 1 and matches[0].get("identityVerified") is True,
                "exact verified actor is absent or duplicated")
        actor = matches[0]
        for key in ("subjectIdentity", "species", "form", "level", "role") + GENERATION_KEYS:
            require(key in actor and actor[key] == self.expected[key], "selected actor identity changed")
        for key in ENGINE_OWNER_KEYS:
            require(key in actor.get("engineIdentity", {}) and key in self.expected.get("engineIdentity", {})
                    and actor["engineIdentity"][key] == self.expected["engineIdentity"][key],
                    "selected engine owner changed")
        require(actor.get("sourceIdentity", {}).get("object") == actor["engineIdentity"]["pointer"]
                == self.expected.get("sourceIdentity", {}).get("object"), "selected engine owner changed")
        handle = actor["handle"]
        require(all(type(handle.get(k)) is int and 0 <= handle[k] <= 65535 for k in HANDLE_KEYS)
                and 0 <= handle["slot"] < self.capacity and handle["generation"] > 0, "invalid actor handle")
        raw = self.session.read(self.state["address"] + self.state["offsets"]["actors"]
                                + handle["slot"] * self.state["actorStride"], 88)
        require(len(raw) == 88 and raw[:4] == struct.pack("<HH", 1, 88)
                and raw[4:14] == struct.pack("<5H", *(handle[k] for k in HANDLE_KEYS))
                and raw[84] == 1 and struct.unpack_from("<I", raw, 16)[0] == actor["subjectIdentity"],
                "raw actor identity differs")
        state = self.session.read(self.state["address"], self.state["size"])
        require(len(state) == self.state["size"], "partial actor state")
        require(all(struct.unpack_from("<H", state, self.state["offsets"][key])[0] == handle[key]
                    for key in ("fieldEpoch", "mapGeneration")), "stale actor context")
        return deepcopy(actor), raw, state

    def _clock(self):
        return dict(frame=self.session.completed_frames, nativeCycle=self.session.rt.EXECUTED_FRAME_COUNT)

    def recipe(self, _scratch, call):
        require(not self.started, "Inspect probe is one-shot")
        self.started = True
        self._owner()
        pointer = yield call("allocate_work_memory", (11, BUFFER_BYTES))
        require(type(pointer) is int and pointer != 0, "Inspect allocation failed")
        self.pointer = pointer
        self.session.native_allocations[pointer] = dict(purpose="actor-inspect-probe", bytes=BUFFER_BYTES)
        require(pointer % 4 == 0 and 0x02000000 <= pointer <= 0x02400000 - BUFFER_BYTES,
                "invalid allocation span", fatal=True)
        require(pointer + BUFFER_BYTES <= self.state["address"]
                or self.state["address"] + self.state["size"] <= pointer, "allocation overlaps actor state", fatal=True)
        try:
            selected, original, _ = self._select()
            for name in ("current-handle", "stale-generation"):
                actor, raw, state = self._select()
                require(raw == original and actor == selected, "actor changed between Inspect calls")
                handle = list(struct.unpack_from("<6H", raw, 4))
                if name == "stale-generation":
                    handle[1] = handle[1] % 65535 + 1
                query = struct.pack("<HHBBH6HI", 1, 24, 1, 0, 0, *handle, 0)
                block = GUARD + query + bytes(176) + GUARD
                self.session.write(pointer, block)
                dispatched = self._clock()
                status = yield call("inspect_actor", (pointer + QUERY, pointer + OUTPUT))
                returned = self._clock()
                current, current_raw, current_state = self._select()
                require(current == actor and current_raw == raw and current_state == state,
                        "Inspect changed actor or state")
                observed = self.session.read(pointer, BUFFER_BYTES)
                require(len(observed) == BUFFER_BYTES and observed[:16] == observed[-16:] == GUARD,
                        "Inspect output guard changed")
                require(observed[QUERY:OUTPUT] == query, "Inspect query changed")
                output = observed[OUTPUT:OUTPUT + 176]
                present = name == "current-handle"
                require(type(status) is int and status == (0 if present else 2)
                        and output[:8] == struct.pack("<HH4B", 1, 176, 1, int(present), 0, 0),
                        "Inspect status/header differs")
                require(output[20:108] == (raw if present else bytes(88)), "Inspect actor bytes differ")
                require(all(returned[k] >= dispatched[k] for k in dispatched), "Inspect clock moved backwards")
                self.receipts.append(dict(name=name, queryHex=query.hex(), outputHex=output.hex(),
                    currentActorHex=raw.hex(), currentActorAfterHex=current_raw.hex(),
                    stateBeforeSha256=hashlib.sha256(state).hexdigest(),
                    stateAfterSha256=hashlib.sha256(current_state).hexdigest(),
                    actor=actor, status=status, dispatchClock=dispatched,
                    returnClock=returned, fieldPointer=self.field, heapGeneration=self.generation,
                    serviceIdentity=deepcopy(self.service)))
            self.completed = True
        finally:
            self._owner()
            yield call("free", (pointer,))
            self._owner()
            self.session.native_allocations.pop(pointer)
            self.released = True
        return self.result()

    def result(self):
        return dict(completed=self.completed and self.released, acceptedProof=False,
                    receipts=deepcopy(self.receipts), allocation=dict(heapId=11, bytes=BUFFER_BYTES,
                    pointer=self.pointer, released=self.released), scope="controlled-native-actor-inspect",
                    comparisonScope="full actor88 parity and unchanged state; other snapshot metadata retained, not accepted")

"""Fixed bounded resolver recipe for the existing FieldReturnBridge.

The session caller authenticates natural blob/service discovery and the named
linked call target. This module writes only its own heap allocation. It neither
drives a core nor changes registers, stack, game state, or acceptance policy.
"""
from copy import deepcopy
import hashlib
import json
import struct

from tools.overworld.devtools_resolver_parity import CASE_NAMES, request_bytes

BUFFER_BYTES = 1536
CAPACITY = 14
REQUEST = 16
RESULT = 64
TRACE = 340
STEPS = 352
GUARD = b"ResolverGuard-v1"

if STEPS + CAPACITY * 80 > BUFFER_BYTES - len(GUARD):
    raise RuntimeError("resolver probe trace overlaps its ending guard")


class ResolverProbeError(ValueError):
    code = "resolver-probe-invalid"

    def __init__(self, message, *, fatal=False):
        super().__init__(message)
        self.fatal = fatal


def require(condition, message, *, fatal=False):
    if not condition:
        raise ResolverProbeError(message, fatal=fatal)


class ResolverProbe:
    def __init__(self, session, *, blob_address, blob_bytes, service_identity):
        self.session = session
        require(type(blob_address) is int and blob_address % 4 == 0
                and isinstance(blob_bytes, bytes) and 0 < len(blob_bytes) <= 1024 * 1024
                and 0x02000000 <= blob_address <= 0x02400000 - len(blob_bytes), "invalid bounded blob")
        require(isinstance(service_identity, dict), "missing authenticated service")
        self.blob_address, self.blob = blob_address, blob_bytes
        self.service = deepcopy(service_identity)
        self.blob_identity = {"size": len(blob_bytes), "sha256": hashlib.sha256(blob_bytes).hexdigest()}
        self.field = session.field_pointer()
        self.generation = session.native_heap_generation
        require(type(self.field) is int and self.field != 0, "missing field owner")
        corpus = json.loads((session.rt.REPO / "tools/overworld/native/behavior_resolver_golden.json").read_text())
        vectors = corpus.get("vectors")
        by_name = {
            vector.get("name"): vector
            for vector in vectors
            if isinstance(vector, dict)
        } if isinstance(vectors, list) else {}
        self.vectors = [by_name.get(name) for name in CASE_NAMES]
        require(corpus.get("blobVersion") == 81
                and all(isinstance(vector, dict) for vector in self.vectors),
                "canonical resolver cases differ")
        self.requests = [request_bytes(v["request"]) for v in self.vectors]
        self.receipts = []
        self.started = self.completed = self.released = False
        self.pointer = None

    def _owner(self):
        require(self.session.emu is not None and self.session.field_pointer() == self.field
                and self.session.native_heap_generation == self.generation,
                "resolver field/heap owner changed", fatal=True)

    def _blob(self):
        self._owner()
        for offset in range(0, len(self.blob), 4096):
            expected = self.blob[offset:offset + 4096]
            require(self.session.read(self.blob_address + offset, len(expected)) == expected,
                    "live resolver blob changed")

    def _clock(self):
        return {"frame": self.session.completed_frames,
                "nativeCycle": self.session.rt.EXECUTED_FRAME_COUNT}

    def recipe(self, _scratch, call):
        """Pass as bridge.run(lambda scratch: probe.recipe(scratch, Call))."""
        require(not self.started, "resolver recipe is one-shot")
        self.started = True
        self._blob()
        pointer = yield call("allocate_work_memory", (11, BUFFER_BYTES))
        require(type(pointer) is int and pointer != 0, "resolver allocation failed")
        self.pointer = pointer
        self.session.native_allocations[pointer] = {"purpose": "conditional-resolver-parity", "bytes": BUFFER_BYTES}
        require(pointer % 4 == 0 and 0x02000000 <= pointer <= 0x02400000 - BUFFER_BYTES,
                "resolver allocator returned an invalid span", fatal=True)
        require(pointer + BUFFER_BYTES <= self.blob_address or self.blob_address + len(self.blob) <= pointer,
                "resolver allocation overlaps source blob", fatal=True)
        try:
            for vector, request in zip(self.vectors, self.requests):
                self._blob()
                block = bytearray(BUFFER_BYTES)
                block[:16] = block[-16:] = GUARD
                block[REQUEST:REQUEST + 44] = request
                struct.pack_into("<IHHHH", block, TRACE, pointer + STEPS, CAPACITY, 0, 0, 0)
                self.session.write(pointer, block)
                dispatched = self._clock()
                status = yield call("resolve_behavior", (self.blob_address, len(self.blob),
                                                          pointer + REQUEST, pointer + RESULT, pointer + TRACE))
                returned = self._clock()
                self._blob()
                observed = self.session.read(pointer, BUFFER_BYTES)
                require(len(observed) == BUFFER_BYTES, "resolver buffer read is incomplete")
                require(observed[:16] == observed[-16:] == GUARD, "resolver buffer guard changed")
                require(observed[REQUEST:REQUEST + 44] == request, "resolver request changed")
                steps, capacity, count, dropped, reserved = struct.unpack_from("<IHHHH", observed, TRACE)
                require(steps == pointer + STEPS and capacity == CAPACITY and reserved == 0,
                        "resolver trace header changed")
                require(0 < count <= CAPACITY and dropped == 0, "resolver trace missing, overflowed or dropped")
                require(type(status) is int and 0 <= status <= 5, "invalid resolver return status")
                require(returned["nativeCycle"] >= dispatched["nativeCycle"]
                        and returned["frame"] >= dispatched["frame"], "resolver clocks moved backwards")
                trace = []
                for index in range(count):
                    offset = STEPS + index * 80
                    source, lane, kind, flags = struct.unpack_from("<HBBB", observed, offset)
                    require(observed[offset + 5:offset + 8] == bytes(3), "resolver trace reserved bytes changed")
                    trace.append(dict(sourceIndex=source, lane=lane, kind=kind, flags=flags,
                                      profileHex=observed[offset + 8:offset + 80].hex()))
                self.receipts.append(dict(name=vector["name"], requestHex=request.hex(),
                    resultHex=observed[RESULT:RESULT + 200].hex(), status=status,
                    traceDropped=dropped, trace=trace, blobIdentity=deepcopy(self.blob_identity),
                    serviceIdentity=deepcopy(self.service), dispatchClock=dispatched, returnClock=returned))
            self.completed = True
        finally:
            # Never free an address from a destroyed/replaced field heap.
            # A retained allocation and fatal error make the bridge close the core.
            self._owner()
            yield call("free", (pointer,))
            self._owner()
            self.session.native_allocations.pop(pointer)
            self.released = True
        return self.result()

    def result(self):
        return {"completed": self.completed and self.released, "acceptedProof": False,
                "receipts": deepcopy(self.receipts), "allocation": {"heapId": 11, "bytes": BUFFER_BYTES,
                "pointer": self.pointer, "released": self.released},
                "scope": "controlled native resolver calls; comparator and live acceptance remain separate"}

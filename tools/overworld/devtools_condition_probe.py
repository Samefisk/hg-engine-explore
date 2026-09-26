"""Bounded packaged-ROM condition-service probe.

The live behavior blob and condition service are authenticated by the session.
This probe temporarily replaces three bounded catalog ranges, exercises four
fixed condition entries, and restores the exact source bytes before it returns.
The owned heap11 allocation contains only call inputs and outputs.  The probe
never changes actor state, registers, stack, or the source save.
"""
from copy import deepcopy
import hashlib
import struct


BUFFER_BYTES = 1536
GUARD = b"Cnd!"
PREPARED_STRUCT_BYTES = 52
PREPARED_STATE_COUNT = 4
PREPARED_STATE_BYTES = 16
PREPARED_BYTES = (PREPARED_STRUCT_BYTES
                  + PREPARED_STATE_COUNT * PREPARED_STATE_BYTES)
WORLD_BYTES = 240
CANDIDATE_BYTES = 32
SCRATCH_BYTES = 32
RESULT_BYTES = 540
CONTEXT_BYTES = 12
HANDLE_BYTES = 12
CHANCE_SEED = 0x12345678
CASE_NAMES = (
    "wild-initial-overlap-stack",
    "wild-timed-hold",
    "wild-cooldown-block",
    "wild-retrigger-restarts-duration",
    "wild-stale-actor-target",
    "wild-fresh-actor-target",
    "follower-copied-input-parity",
)


class ConditionProbeError(ValueError):
    code = "condition-probe-invalid"

    def __init__(self, message, *, fatal=False):
        super().__init__(message)
        self.fatal = fatal


def require(condition, message, *, fatal=False):
    if not condition:
        raise ConditionProbeError(message, fatal=fatal)


def _align4(value):
    return (value + 3) & ~3


def buffer_layout(blob_size):
    require(type(blob_size) is int and 84 <= blob_size <= 0xB000,
            "invalid condition blob size")
    sizes = (
        ("context", CONTEXT_BYTES),
        ("subject", HANDLE_BYTES),
        ("prepared", PREPARED_BYTES),
        ("world", WORLD_BYTES),
        ("candidates", CANDIDATE_BYTES),
        ("scratch", SCRATCH_BYTES),
        ("result", RESULT_BYTES),
    )
    cursor = len(GUARD)
    regions = {}
    guards = [0]
    for name, size in sizes:
        cursor = _align4(cursor)
        regions[name] = {"offset": cursor, "bytes": size}
        cursor += size
        guards.append(cursor)
        cursor += len(GUARD)
    guards.append(BUFFER_BYTES - len(GUARD))
    require(cursor <= BUFFER_BYTES, "condition probe layout exceeds owned buffer")
    require(guards[-2] + len(GUARD) <= guards[-1],
            "condition probe ending guards overlap")
    return {"bufferBytes": BUFFER_BYTES, "sourceBlobBytes": blob_size,
            "regions": regions,
            "guards": guards, "usedBytes": cursor}


def _profile(blob, header, index, *, kind, condition_start, condition_count,
             target_mode=0):
    offset, count, stride = header["overrideProfiles"]
    require(0 <= index < count and stride == 212,
            "condition profile layout differs")
    start = offset + index * stride
    require(start + stride <= len(blob), "condition profile is outside blob")
    blob[start:start + 12] = struct.pack("<IH5Bx", 0, 0, 0xFF, 0, 0, 0xFF, 0xFF)
    struct.pack_into("<HH4B", blob, start + 12, 0, 0, target_mode, kind,
                     condition_start, condition_count)


def _entry(*, condition_id, application, kind, activation, target, role_mask,
           duration=0, cooldown=0, terrain_mask=0, terrain_override=0):
    raw = bytearray(48)
    struct.pack_into("<HHHH", raw, 16, terrain_mask, terrain_override,
                     duration, cooldown)
    struct.pack_into("<H", raw, 32, condition_id)
    raw[34:47] = bytes((
        application,
        2,      # subject mode: all; subject application below owns matching
        0xFF,   # V5 conditions own subjects; no application-owned subject
        kind,
        activation,
        target,
        role_mask,
        0,      # nearest target
        4,      # radius
        4,
        100,
        0,
        0,
    ))
    return bytes(raw)


def _blob_header(blob):
    require(isinstance(blob, (bytes, bytearray)) and len(blob) >= 84,
            "condition source blob is truncated")
    magic, version, header_size, blob_size = struct.unpack_from("<IHHI", blob)
    require(magic == 0x4F574244 and version == 81 and header_size == 84
            and blob_size == len(blob), "condition source blob header differs")
    sections = {}
    for name, offset in (("overrideProfiles", 36), ("overrideMembers", 44),
                         ("conditionEntries", 52)):
        section, count, stride = struct.unpack_from("<IHH", blob, offset)
        require(section % 4 == 0 and stride > 0
                and section + count * stride <= len(blob),
                "condition source blob section differs")
        sections[name] = (section, count, stride)
    require(sections["overrideProfiles"][1] >= 4
            and sections["overrideProfiles"][2] == 212
            and sections["overrideMembers"][2] == 2
            and sections["conditionEntries"][1] >= 4
            and sections["conditionEntries"][2] == 48,
            "condition source blob capacities differ")
    return sections


def build_test_blob(source):
    """Return the exact source bytes with one bounded copied-input fixture."""
    blob = bytearray(source)
    header = _blob_header(blob)
    struct.pack_into("<H", blob, 56, 4)
    _profile(blob, header, 0, kind=0, condition_start=0,
             condition_count=0, target_mode=2)
    _profile(blob, header, 1, kind=1, condition_start=0, condition_count=2)
    _profile(blob, header, 2, kind=1, condition_start=2, condition_count=1)
    _profile(blob, header, 3, kind=1, condition_start=3, condition_count=1)
    condition_offset = header["conditionEntries"][0]
    entries = (
        _entry(condition_id=500, application=1, kind=1, activation=0,
               target=2, role_mask=1),
        _entry(condition_id=501, application=1, kind=1, activation=0,
               target=2, role_mask=2),
        _entry(condition_id=502, application=2, kind=0, activation=1,
               target=1, role_mask=0, duration=10, cooldown=5),
        _entry(condition_id=503, application=3, kind=2, activation=0,
               target=0, role_mask=0, terrain_mask=4, terrain_override=4),
    )
    for index, entry in enumerate(entries):
        start = condition_offset + index * 48
        blob[start:start + 48] = entry
    return bytes(blob)


def fixture_patch_plan(source, test_blob=None):
    """Describe the only live catalog ranges replaced by the fixture."""
    require(isinstance(source, bytes), "condition source blob must be bytes")
    test_blob = build_test_blob(source) if test_blob is None else test_blob
    require(isinstance(test_blob, bytes) and len(test_blob) == len(source),
            "condition test blob size differs")
    header = _blob_header(source)
    profile_offset = header["overrideProfiles"][0]
    condition_offset = header["conditionEntries"][0]
    ranges = (
        (56, 2, "condition-count"),
        (profile_offset, 4 * 212, "profiles-0-3"),
        (condition_offset, 4 * 48, "conditions-0-3"),
    )
    patched = bytearray(source)
    receipt = []
    previous_end = 0
    for offset, size, name in ranges:
        require(previous_end <= offset and offset + size <= len(source),
                "condition fixture ranges overlap or exceed the blob")
        before = source[offset:offset + size]
        after = test_blob[offset:offset + size]
        patched[offset:offset + size] = after
        receipt.append({
            "name": name,
            "offset": offset,
            "bytes": size,
            "beforeSha256": hashlib.sha256(before).hexdigest(),
            "afterSha256": hashlib.sha256(after).hexdigest(),
        })
        previous_end = offset + size
    require(bytes(patched) == test_blob,
            "condition fixture changes escape declared ranges")
    return {
        "fixtureVersion": 2,
        "rangeCount": len(receipt),
        "rangeBytes": sum(item["bytes"] for item in receipt),
        "ranges": receipt,
        "scope": ("temporary live behavior-catalog fixture; exact declared "
                  "ranges are restored before the probe returns"),
    }


def handle_bytes(slot, generation):
    return struct.pack("<6H", slot, generation, 3, 4, generation + 10, 0)


def context_bytes():
    return struct.pack("<HHIBBBB", 16, 0, 0, 5, 0, 0, 0)


def candidates_bytes():
    def candidate(role):
        return struct.pack("<HHIBBBB4B", 25, 0, 0, 5, 0, 0, 0,
                           role, 0, 0, 0)
    return candidate(1) + candidate(2)


def world_bytes(frame, *, player_x=12, follower_generation=3):
    raw = bytearray(WORLD_BYTES)
    raw[:12] = handle_bytes(0, 1)
    struct.pack_into(
        "<I4hH9B3x",
        raw,
        12,
        frame,
        10,
        10,
        player_x,
        10,
        4,
        3,  # subject facing: east
        8,  # subject movement speed
        1,  # player valid
        2,  # actor count
        2,  # player facing: west; no occlusion flags
        3,  # subject Vision range
        5,  # subject Vision: forward cone + adjacent awareness
        3,  # player Vision range
        5,  # player Vision: forward cone + adjacent awareness
    )
    raw[38:50] = handle_bytes(1, 2)
    struct.pack_into("<hh4B", raw, 50, 11, 10, 1, 2, 3, 5)
    raw[58:70] = handle_bytes(2, follower_generation)
    struct.pack_into("<hh4B", raw, 70, 12, 10, 1, 2, 3, 5)
    return bytes(raw)


class ConditionProbe:
    def __init__(self, session, *, blob_address, blob_bytes, service_identity):
        self.session = session
        require(type(blob_address) is int and blob_address % 4 == 0
                and isinstance(blob_bytes, bytes) and 0 < len(blob_bytes) <= 1024 * 1024
                and 0x02000000 <= blob_address <= 0x02400000 - len(blob_bytes),
                "invalid bounded condition blob")
        require(isinstance(service_identity, dict),
                "missing authenticated condition service")
        self.blob_address = blob_address
        self.source_blob = blob_bytes
        self.test_blob = build_test_blob(blob_bytes)
        self.fixture_plan = fixture_patch_plan(blob_bytes, self.test_blob)
        self.layout = buffer_layout(len(blob_bytes))
        self.service = deepcopy(service_identity)
        self.source_identity = {
            "size": len(blob_bytes),
            "sha256": hashlib.sha256(blob_bytes).hexdigest(),
        }
        self.test_identity = {
            "size": len(self.test_blob),
            "sha256": hashlib.sha256(self.test_blob).hexdigest(),
            "fixtureVersion": 2,
        }
        self.field = session.field_pointer()
        self.generation = session.native_heap_generation
        require(type(self.field) is int and self.field != 0,
                "missing condition field owner")
        self.pointer = None
        self.started = self.completed = self.released = False
        self.patched = self.restored = False
        self.fixture_intact_before_restore = False
        self.prepare_receipts = []
        self.receipts = []

    def _owner(self):
        require(self.session.emu is not None
                and self.session.field_pointer() == self.field
                and self.session.native_heap_generation == self.generation,
                "condition field/heap owner changed", fatal=True)

    def _source(self):
        self._owner()
        for offset in range(0, len(self.source_blob), 4096):
            expected = self.source_blob[offset:offset + 4096]
            require(self.session.read(self.blob_address + offset, len(expected))
                    == expected, "live condition source blob changed")

    def _test_source(self):
        self._owner()
        for offset in range(0, len(self.test_blob), 4096):
            expected = self.test_blob[offset:offset + 4096]
            require(self.session.read(self.blob_address + offset, len(expected))
                    == expected, "temporary condition fixture changed")

    def _patch_source(self):
        self._source()
        for item in self.fixture_plan["ranges"]:
            offset = item["offset"]
            size = item["bytes"]
            expected = self.source_blob[offset:offset + size]
            replacement = self.test_blob[offset:offset + size]
            require(hashlib.sha256(expected).hexdigest()
                    == item["beforeSha256"]
                    and hashlib.sha256(replacement).hexdigest()
                    == item["afterSha256"],
                    "condition fixture range identity differs", fatal=True)
            self.session.write(self.blob_address + offset, replacement)
        self.patched = True
        self._test_source()

    def _restore_source(self):
        if not self.patched:
            return
        observed = self.session.read(self.blob_address, len(self.test_blob))
        self.fixture_intact_before_restore = observed == self.test_blob
        if self.fixture_intact_before_restore:
            for item in self.fixture_plan["ranges"]:
                offset = item["offset"]
                size = item["bytes"]
                self.session.write(
                    self.blob_address + offset,
                    self.source_blob[offset:offset + size],
                )
        else:
            # A bad native write can escape a declared fixture range.  Restore
            # the complete authenticated blob before the disposable core closes.
            self.session.write(self.blob_address, self.source_blob)
        require(self.session.read(self.blob_address, len(self.source_blob))
                == self.source_blob, "condition source restoration failed",
                fatal=True)
        self.restored = True
        return self.fixture_intact_before_restore

    def _clock(self):
        return {"frame": self.session.completed_frames,
                "nativeCycle": self.session.rt.EXECUTED_FRAME_COUNT}

    def _region(self, name):
        item = self.layout["regions"][name]
        return item["offset"], item["bytes"]

    def _new_block(self):
        block = bytearray(BUFFER_BYTES)
        for offset in self.layout["guards"]:
            block[offset:offset + len(GUARD)] = GUARD
        for name, value in (("context", context_bytes()),
                            ("subject", handle_bytes(0, 1)),
                            ("world", world_bytes(100)),
                            ("candidates", candidates_bytes())):
            offset, size = self._region(name)
            require(len(value) == size, "condition input size differs")
            block[offset:offset + size] = value
        return block

    def _checked(self, expected_world):
        observed = self.session.read(self.pointer, BUFFER_BYTES)
        require(len(observed) == BUFFER_BYTES,
                "condition buffer read is incomplete")
        require(all(observed[offset:offset + len(GUARD)] == GUARD
                    for offset in self.layout["guards"]),
                "condition buffer guard changed")
        for name, expected in (("context", context_bytes()),
                               ("subject", handle_bytes(0, 1)),
                               ("world", expected_world),
                               ("candidates", candidates_bytes())):
            offset, size = self._region(name)
            require(observed[offset:offset + size] == expected,
                    "condition " + name + " input changed")
        return observed

    def _write_region(self, block, name, value):
        offset, size = self._region(name)
        require(len(value) == size, "condition region size differs")
        block[offset:offset + size] = value

    def _prepare(self, block, call, role_label):
        self._write_region(block, "prepared", bytes(PREPARED_BYTES))
        prepared, _ = self._region("prepared")
        states_pointer = self.pointer + prepared + PREPARED_STRUCT_BYTES
        struct.pack_into("<I", block, prepared + 12, states_pointer)
        struct.pack_into("<H", block, prepared + 50, PREPARED_STATE_COUNT)
        self._write_region(block, "world", world_bytes(100))
        self.session.write(self.pointer, block)
        self._test_source()
        dispatched = self._clock()
        context, _ = self._region("context")
        subject, _ = self._region("subject")
        status = yield call("prepare_conditions", (
            self.blob_address,
            len(self.test_blob),
            self.pointer + context,
            self.pointer + subject,
            self.pointer + prepared,
        ))
        returned = self._clock()
        observed = self._checked(world_bytes(100))
        prepared_raw = observed[prepared:prepared + PREPARED_BYTES]
        require(status == 0
                and struct.unpack_from("<I", prepared_raw, 12)[0]
                    == states_pointer
                and prepared_raw[16:20] == bytes((0, 1, 2, 3))
                and prepared_raw[48:52] == bytes((4, 1, 4, 0)),
                "condition prepare result differs")
        self.prepare_receipts.append({
            "subjectRoleLabel": role_label,
            "status": status,
            "preparedHex": prepared_raw.hex(),
            "dispatchClock": dispatched,
            "returnClock": returned,
        })
        return bytearray(observed)

    def _evaluate(self, block, call, name, world, role_label, expected_status):
        self._write_region(block, "world", world)
        self._write_region(block, "scratch", bytes(SCRATCH_BYTES))
        self._write_region(block, "result", bytes(RESULT_BYTES))
        self.session.write(self.pointer, block)
        self._test_source()
        dispatched = self._clock()
        offsets = {name: self._region(name)[0] for name in self.layout["regions"]}
        status = yield call("evaluate_conditions", (
            self.blob_address,
            len(self.test_blob),
            self.pointer + offsets["prepared"],
            self.pointer + offsets["world"],
            self.pointer + offsets["candidates"],
            2,
            CHANCE_SEED,
            self.pointer + offsets["scratch"],
            self.pointer + offsets["result"],
        ))
        returned = self._clock()
        observed = self._checked(world)
        require(
            status == expected_status,
            (f"condition evaluate status differs for {name}: "
             f"expected {expected_status}, got {status}"),
        )
        prepared = observed[offsets["prepared"]:
                            offsets["prepared"] + PREPARED_BYTES]
        scratch = observed[offsets["scratch"]:
                           offsets["scratch"] + SCRATCH_BYTES]
        result = observed[offsets["result"]:
                          offsets["result"] + RESULT_BYTES]
        self.receipts.append({
            "name": name,
            "subjectRoleLabel": role_label,
            "status": status,
            "chanceSeed": CHANCE_SEED,
            "contextHex": context_bytes().hex(),
            "subjectHex": handle_bytes(0, 1).hex(),
            "worldHex": world.hex(),
            "candidatesHex": candidates_bytes().hex(),
            "preparedHex": prepared.hex(),
            "scratchHex": scratch.hex(),
            "resultHex": result.hex(),
            "dispatchClock": dispatched,
            "returnClock": returned,
        })
        return bytearray(observed)

    def recipe(self, _scratch, call):
        require(not self.started, "condition probe is one-shot")
        self.started = True
        self._source()
        self._patch_source()
        pointer = 0
        try:
            pointer = yield call("allocate_work_memory", (11, BUFFER_BYTES))
            require(type(pointer) is int and pointer != 0,
                    "condition allocation failed")
            self.pointer = pointer
            self.session.native_allocations[pointer] = {
                "purpose": "packaged-condition-service",
                "bytes": BUFFER_BYTES,
            }
            require(pointer % 4 == 0
                    and 0x02000000 <= pointer <= 0x02400000 - BUFFER_BYTES,
                    "condition allocator returned an invalid span", fatal=True)
            require(pointer + BUFFER_BYTES <= self.blob_address
                    or self.blob_address + len(self.source_blob) <= pointer,
                    "condition allocation overlaps source blob", fatal=True)
            block = self._new_block()
            block = yield from self._prepare(block, call, "WILD")
            baseline = None
            for name, world, status in (
                (CASE_NAMES[0], world_bytes(100), 0),
                (CASE_NAMES[1], world_bytes(103, player_x=30), 0),
                (CASE_NAMES[2], world_bytes(104), 0),
                (CASE_NAMES[3], world_bytes(105), 0),
                (CASE_NAMES[4], world_bytes(106, follower_generation=9), 3),
                (CASE_NAMES[5], world_bytes(107, follower_generation=9), 0),
            ):
                block = yield from self._evaluate(
                    block, call, name, world, "WILD", status)
                if name == CASE_NAMES[0]:
                    baseline = deepcopy(self.receipts[-1])
            block = yield from self._prepare(block, call, "FOLLOWER")
            block = yield from self._evaluate(
                block, call, CASE_NAMES[-1], world_bytes(100), "FOLLOWER", 0)
            parity = self.receipts[-1]
            require(baseline is not None
                    and all(parity[key] == baseline[key]
                            for key in ("status", "chanceSeed", "contextHex",
                                        "subjectHex", "worldHex", "candidatesHex",
                                        "preparedHex", "scratchHex", "resultHex")),
                    "copied Wild/Follower condition inputs differ")
            self.completed = True
        finally:
            fixture_intact = self._restore_source()
            if pointer:
                self._owner()
                yield call("free", (pointer,))
                self._owner()
                self.session.native_allocations.pop(pointer)
                self.released = True
            require(fixture_intact,
                    "temporary condition fixture changed outside declared outputs",
                    fatal=True)
        return self.result()

    def result(self):
        return {
            "completed": self.completed and self.released,
            "acceptedProof": False,
            "sourceBlobIdentity": deepcopy(self.source_identity),
            "testBlobIdentity": deepcopy(self.test_identity),
            "serviceIdentity": deepcopy(self.service),
            "fixture": {
                **deepcopy(self.fixture_plan),
                "patched": self.patched,
                "intactBeforeRestore": self.fixture_intact_before_restore,
                "restored": self.restored,
            },
            "layout": deepcopy(self.layout),
            "prepareReceipts": deepcopy(self.prepare_receipts),
            "receipts": deepcopy(self.receipts),
            "allocation": {
                "heapId": 11,
                "bytes": BUFFER_BYTES,
                "pointer": self.pointer,
                "released": self.released,
            },
            "scope": ("controlled native condition-service calls over an owned "
                      "input/output buffer and a temporary restored catalog "
                      "fixture; no live role caller or movement credit"),
        }

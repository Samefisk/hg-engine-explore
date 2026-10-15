"""Opt-in read-only Cargo Tick receipts for the existing Throw record window.

This is a diagnostic of the actual call, not route admission. No guest calls,
writes, input or extra frames are used. The current linked image seals the
private offsets; an unrelated image must get a new reviewed layout seal.
"""
import hashlib
import struct

from tools.overworld.devtools_field_cleanup import symbol
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld.pack_query_code_addon import package, BASE, ENTRY, MAX_IMAGE

LABEL = "throw-cargo-query"
MAX_RECEIPTS = 256
# Full image discovery is a separate bounded check. Every Tick still reads
# the current Cargo ABI, full Cargo prefix and complete moved CargoWild module within this same cap.
READ_BUDGET = 0x9000
TICK_MAX_METADATA = 2337  # Original661 + typed packet/receipt284 + constructor1390 + aligned prefix2.
INITIAL_READ_BUDGET = MAX_IMAGE + 37  # Image plus the existing loader/owner reads.
CARGO_CODE_START, CARGO_CODE_END = 196, 24156
CARGO_WILD_START, CARGO_WILD_END = 0xB0D8, 0xD83C
CARGO_WILD_SHA256 = "23d391c7271973087bffb3c8db9d7583e3587b77004f5e6d585aada0d8a1b54d"
CARGO_ABI_OFFSET, CARGO_ABI_SIZE = 100, 16
ELF_SHA = "f65d43d7de5d1345bfe86582a595a410abfc4865f22e1f67a8c34dfd94d83292"
PACKAGE_SHA = "715af802ec759a66db57fbed0f429060f77c985267f7545f1d9bdd1b31072d10"
CARGO_CODE_SHA256 = "365333b96d5c6a958250f01bb08a8bb307f400e5528f77e3a46380693f12348e"
TICK_OFFSET, TICK_SIZE = 0xC274, 0x15B0
RUNTIME_CONDITIONS, RUNTIME_QUERY = 0x514, 0x518
FRAME_WORLD, FRAME_VALID, BINDINGS = 0x6BC, 0x857, 0x998
QUERY_STATE_SIZE = 424
QUERY_SIZE, QUERY_OWNER, QUERY_VALID = 43516, 28408, 28588
QUERY_WAITING = 28590
QUERY_ENTRY_ACTIVE = 30250
QUERY_PREFIX_SIZE = 384
WORLD_VERSION, WORLD_SIZE, OPS_SIZE = 3, 84, 84
RUNTIME_SIZE = 2856
CONDITION_ACTOR_SIZE, CONDITION_ACTIVE_MASKS = 88, 2332
ENTRY_LABEL = "entry-route-query"
ENTRY_CONTROL_LABEL = "entry-native-control"
# Final native-glue ARM layout and owner seals are required before integration.
ENTRY_LAYOUT = {
    "Command": 88,
    "Request": 72,
    "Control": 52,
    "ControlOps": 72,
    "Receipt": 64,
    "Command_request": 0,
    "Command_receipt": 72,
    "Command_startCommitSequence": 76,
    "Command_accepted": 80,
    "Command_usableIdle": 81,
    "Command_safelyOffscreen": 82,
    "Command_reserved": 83,
    "Command_nativeControl": 84,
    "Request_version": 0,
    "Request_size": 2,
    "Request_serial": 4,
    "Request_fieldEpoch": 8,
    "Request_mapGeneration": 12,
    "Request_actor": 16,
    "Request_destination": 28,
    "Request_origin": 40,
    "Request_physical": 52,
    "Request_expectedSlotGeneration": 68,
    "Request_slot": 70,
    "Request_operation": 71,
    "Control_version": 0,
    "Control_size": 2,
    "Control_ops": 4,
    "Control_state": 8,
    "Control_field": 12,
    "Control_profile": 16,
    "Control_primitives": 20,
    "Control_prepared": 24,
    "Control_object": 28,
    "Control_receipt": 32,
    "Control_startCommitSequence": 36,
    "Control_value": 40,
    "Control_operation": 44,
    "Control_slot": 45,
    "Control_terrain": 46,
    "Control_queryOperation": 47,
    "Control_accepted": 48,
    "Control_usableIdle": 49,
    "Control_reserved": 50,
    "ControlOps_magic": 0,
    "ControlOps_version": 4,
    "ControlOps_size": 6,
    "ControlOps_actors": 8,
    "ControlOps_initWorld": 12,
    "ControlOps_allowed": 16,
    "ControlOps_start": 20,
    "ControlOps_finish": 24,
    "ControlOps_remove": 28,
    "ControlOps_occupied": 32,
    "ControlOps_resolve": 36,
    "ControlOps_limit": 40,
    "ControlOps_destination": 44,
    "ControlOps_groundHeight": 48,
    "ControlOps_personality": 52,
    "ControlOps_prepare": 56,
    "ControlOps_guard": 60,
    "ControlOps_placementBlocked": 64,
    "ControlOps_spawn": 68,
    "Receipt_version": 0,
    "Receipt_size": 2,
    "Receipt_serial": 4,
    "Receipt_actor": 8,
    "Receipt_origin": 20,
    "Receipt_target": 32,
    "Receipt_nextStep": 44,
    "Receipt_edgeTag": 56,
    "Receipt_stepsRemaining": 58,
    "Receipt_status": 60,
    "Receipt_readsUsed": 61,
    "Receipt_queued": 62,
    "Receipt_hasNextStep": 63,
    "Runtime_queuedSpawn": 992,
    "Runtime_queuedSpawnSlotPlusOne": 240,
    "Runtime_refillPositionChecksRemaining": 244,
    "Runtime_queuedSpawnSerial": 2748,
    "Runtime_entryRouteReceipt": 2752,
    "Runtime_entryRouteSerial": 2816
}
ENTRY_NATIVE_OWNERS = {'ops': (37584724, 72, 'b3fa3371a761a7ab5a7712847d1984ce39c1ee50568fe0895686527d77452273'),
 'remove': (37560532, 52, 'ac2cbbfe34ddcab9f9182f4e39f62780ba97dc11c217240017b2b0d4716b314f'),
 'spawn': (37565892, 1204, 'ae67ca6350285bb8d5c5c58fd089031a223cd90f9221ee7749dee9766c709b2c')}
# Each offset is measured from the actual ARM types; route and saved-query
# fields grow at different boundaries. See the T65 native layout receipt.
STATE_OFFSETS = {
    "route": 0,
    "query": 188,
    "goal": 288,
    "storage": 300,
    "lastWork": 308,
    "requestKey": 336,
    "frame": 340,
    "version": 364,
    "size": 366,
    "edgeOwed": 369,
    "candidate": 370,
    "scan": 371,
    "roleMask": 372,
    "distance": 373,
    "active": 374,
    "started": 375,
    "goalValid": 376,
    "goalDirty": 377,
    "required": 380,
    "query_subject": 192,
    "query_cargo": 204,
    "query_bounds": 216,
    "query_origin": 224,
    "query_cargoPosition": 236,
    "query_scopeRevision": 248,
    "query_movementPolicyRevision": 252,
    "query_goalRevision": 256,
    "query_dynamicRevision": 260,
    "query_edges": 264,
    "query_edgeCount": 280,
    "route_query_subject": 4,
    "route_query_goalRevision": 68,
    "route_nodeCount": 148,
    "route_goalNode": 156,
    "route_proofNode": 158,
    "route_proofLength": 172,
    "route_phase": 178,
    "route_probeNeeded": 180,
    "work_edgeQueries": 327,
    "work_goalQueries": 328
}
HANDLE_KEYS = ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")


def need(ok, reason):
    if not ok:
        raise NativeObservationError("cargo query reader: " + reason)


def handle(raw):
    values = struct.unpack("<6H", raw)
    if values == (0,) * 6:
        return None
    need(values[0] < 10 and all(values[1:5]) and values[5] == 0, "full handle differs")
    return dict(zip(HANDLE_KEYS, values[:5]), value=values[0] | values[1] << 16)


def sealed_package(elf, staged, member):
    need(hashlib.sha256(elf).hexdigest() == ELF_SHA, "private ARM layout seal differs")
    blob, receipt = package(elf)
    need(blob == staged == member and hashlib.sha256(blob).hexdigest() == PACKAGE_SHA,
         "ROM member21 differs from exact linked package")
    image = blob[64:64 + receipt["imageBytes"]]
    need(ENTRY == CARGO_CODE_START and receipt["cargoCodeBytes"] == CARGO_CODE_END
         and CARGO_CODE_START < CARGO_CODE_END < CARGO_WILD_START < CARGO_WILD_END <= len(image) <= MAX_IMAGE
         and CARGO_CODE_END % 4 == 0 and len(image) % 4 == 0
         and CARGO_ABI_OFFSET + CARGO_ABI_SIZE <= CARGO_CODE_START
         and CARGO_CODE_END + CARGO_WILD_END - CARGO_WILD_START + TICK_MAX_METADATA <= READ_BUDGET,
         "authenticated Cargo code range differs")
    need(hashlib.sha256(image[CARGO_CODE_START:CARGO_CODE_END]).hexdigest()==CARGO_CODE_SHA256,
         "private Cargo code seal differs")
    need(hashlib.sha256(image[CARGO_WILD_START:CARGO_WILD_END]).hexdigest() == CARGO_WILD_SHA256
         and CARGO_WILD_START <= TICK_OFFSET < TICK_OFFSET + TICK_SIZE <= CARGO_WILD_END,
         "private CargoWild module seal differs")
    need(struct.unpack_from("<6H", image, 100) == (2, QUERY_STATE_SIZE, 40, 140, 24604, 0)
         and struct.unpack_from("<I", image, 112)[0] == (BASE + TICK_OFFSET | 1),
         "typed Cargo callback/layout differs")
    # These native literals prove the current conditions, valid-frame and sole
    # workspace-owner offsets before any private pointer is followed.
    need(tuple(struct.unpack_from("<I", image, offset)[0]
               for offset in (0xC25C, 0xD32C, 0xC264, 0xC258, 0xC268, 0xBFB8))
         == (RUNTIME_CONDITIONS, FRAME_VALID, QUERY_OWNER, QUERY_VALID,
             QUERY_WAITING, QUERY_SIZE), "native Tick/turn layout literals differ")
    return blob, image, dict(receipt, cargoWildRange=(CARGO_WILD_START, CARGO_WILD_END))



def native_entry_bindings(data, elf_code, packaged_code):
    need(bool(ENTRY_LAYOUT) and set(ENTRY_NATIVE_OWNERS) == {"ops", "remove", "spawn"},
         "final native Entry owner seals are absent")
    result = {}
    for key, name, kind in (("ops", "sOverworldWildEntryNativeOps", 1),
                            ("remove", "OverworldWildSpawns_RemoveEncounter", 2),
                            ("spawn", "OverworldWildSpawns_SpawnPreparedEncounter", 2)):
        address, size, _ = symbol(data, name, kind)
        need((address, size) == tuple(ENTRY_NATIVE_OWNERS[key][:2]),
             "native Entry " + key + " owner differs")
        expected = elf_code(address, size)
        need(hashlib.sha256(expected).hexdigest() == ENTRY_NATIVE_OWNERS[key][2]
             and packaged_code(address, size) == expected,
             "native Entry " + key + " full package/body differs")
        result[key] = (address, expected)
    ops = result["ops"][1]
    need(len(ops) == ENTRY_LAYOUT["ControlOps"]
         and struct.unpack_from("<IHH", ops) == (0x4E454F57, 1, ENTRY_LAYOUT["ControlOps"])
         and all(struct.unpack_from("<I", ops, ENTRY_LAYOUT["ControlOps_" + name])[0] & 1
                 for name in ("actors", "initWorld", "allowed", "start", "finish", "remove", "occupied",
                              "resolve", "limit", "destination", "groundHeight", "personality", "prepare",
                              "guard", "placementBlocked", "spawn"))
         and struct.unpack_from("<I", ops, ENTRY_LAYOUT["ControlOps_remove"])[0] == result["remove"][0] | 1
         and struct.unpack_from("<I", ops, ENTRY_LAYOUT["ControlOps_spawn"])[0] == result["spawn"][0] | 1,
         "native Entry typed Ops/callbacks differ")
    return result


def native_unload_binding(data):
    name = "OverworldQueryCodeAddon_Unload"
    address, size, code = symbol(data, name, 2)
    # symbol() already proves one real executable owner and its whole extent.
    # Retain the raw ELF st_value here to prove this exact callback is Thumb.
    table = struct.unpack_from("<I", data, 32)[0]
    count = struct.unpack_from("<H", data, 48)[0]
    sections = [struct.unpack_from("<10I", data, table + i * 40) for i in range(count)]
    values = []
    for row in sections:
        if row[1] != 2:
            continue
        strings = sections[row[6]]
        names = data[strings[4]:strings[4] + strings[5]]
        for pos in range(row[4], row[4] + row[5], 16):
            label, value = struct.unpack_from("<2I", data, pos)
            if names[label:].split(b"\0", 1)[0] == name.encode():
                values.append(value)
    need(values == [address | 1] and 0x023C2324 <= address <= 0x023C2A80 - size,
         "native Unload hosted Thumb extent differs")
    return address, size, code


def relocated_image(image, receipt, entry):
    need(entry % 4 == 0 and 0x02000000 <= entry <= 0x02400000 - len(image),
         "loaded image range differs")
    result = bytearray(image)
    for offset in receipt["localAbs32"]:
        old = struct.unpack_from("<I", result, offset)[0]
        need(BASE <= (old & ~1) < BASE + len(image), "local relocation differs")
        struct.pack_into("<I", result, offset, old + entry - BASE)
    return bytes(result)


def authenticate_loaded_query_functions(session, elf, staged, member, owners):
    """Read-only native owner proof. It installs no hooks or record window.

    The existing current-lease reader authenticates the full relocated image,
    services, Field/Actor epochs and current owner on every call.
    """
    from tools.overworld.devtools_resolver_parity import current_query_owner

    blob, image, receipt = sealed_package(elf, staged, member)
    need(bool(owners), "loaded Query function seals are absent")
    bindings = {}
    for name, expected in owners.items():
        need(isinstance(expected, tuple) and len(expected) == 3,
             "loaded Query function seal is absent")
        address, size, body = symbol(elf, name, 2)
        need((address, size) == expected[:2]
             and BASE + ENTRY <= address <= BASE + len(image) - size
             and body == image[address - BASE:address - BASE + size]
             and hashlib.sha256(body).hexdigest() == expected[2],
             "loaded Query typed function differs: " + name)
        bindings[name] = (address - BASE, size)
    owner = current_query_owner(session, blob, receipt)
    relocated = relocated_image(image, receipt, owner["entry"])
    for name, (offset, size) in bindings.items():
        need(session.read(owner["entry"] + offset, size) == relocated[offset:offset + size],
             "loaded Query current function differs: " + name)
    return owner


class NativeQueryObserver:
    def __init__(self, observer):
        import ndspy.narc
        import ndspy.rom
        self.observer, self.session = observer, observer.session
        self.active, self.count = True, 0
        self.count_cycle = None
        self.tokens, self.returns, self.contexts = [], [], []
        self.loaded = None
        self.pending_detaches = {}
        self.tick_token = self.draining = None
        build = self.session.rt.REPO / "build"
        directory = build / "overworld_query_code_addon"
        rom = ndspy.rom.NintendoDSRom.fromFile(self.session.rom)
        member = ndspy.narc.NARC(rom.getFileByName("a/0/2/8")).files[21]
        self.blob, self.image, self.receipt = sealed_package(
            (directory / "image.elf").read_bytes(), (directory / "query.bin").read_bytes(), member)
        selector = build / "overworld_follower_selector_overlay_linked.o"
        data = selector.read_bytes()
        self.service = symbol(data, "gOverworldQueryCodeAddonServiceEntry", 1, expected_size=24)[0]
        self.state = symbol(data, "gOverworldQueryCodeAddonState", 1, expected_size=28)[0]
        need((self.service, self.state) == (0x023C22F0, 0x023C2308), "Selector homes differ")
        self.service_bytes = observer.elf_code(selector, self.service, 24)
        need(struct.unpack_from("<IHHI", self.service_bytes) == (0x53444F57, 2, 24, self.state),
             "Selector service ABI differs")
        wild = build / "overworld_wild_spawns_overlay_linked.o"
        self.discovery = self.session.rt.linked_symbol(self.session.rt.WILD_SYMBOLS,
                                                       "OverworldWildSpawns_QueryAddon") & ~1
        self.discovery_bytes = observer.elf_code(wild, self.discovery, 32)
        need(self.session.packaged_code(self.discovery, 32) == self.discovery_bytes,
             "fixed QueryAddon package differs")
        self._tap(self.discovery, self._discover_before, self._discover_after, None)
        self.unload, size, self.unload_bytes = native_unload_binding(data)
        need(self.session.packaged_code(self.unload, size) == self.unload_bytes,
             "native Unload package body differs")
        self._tap(self.unload, self._unload_before, self._unload_after, None)
        native = native_entry_bindings(wild.read_bytes(),
            lambda address, size: observer.elf_code(wild, address, size), self.session.packaged_code)
        self.native_ops_address, self.native_ops_bytes = native["ops"]
        self.remove_address, self.remove_bytes = native["remove"]
        self.native_spawn_address, self.native_spawn_bytes = native["spawn"]
        need(observer.calls.get("spawn-prepared", {}).get("address") == self.native_spawn_address,
             "native constructor observer owner differs")
        self._tap(self.remove_address, self._remove_before, self._remove_after, None)

    def _read(self, address, size):
        need(type(address) is int and address % 4 == 0 and 0 < size <= READ_BUDGET
             and (0x02000000 <= address <= 0x02400000 - size
                  or 0x027E0000 <= address <= 0x027E3FC0 - size), "pointer range differs")
        self.read_bytes += size
        need(self.read_bytes <= getattr(self,"read_limit",READ_BUDGET), "callback read budget exceeded")
        raw = self.session.read(address, size)
        need(isinstance(raw, bytes) and len(raw) == size, "short native read")
        return raw

    def _image_identity(self, entry, expected, full_image=False):
        need(CARGO_CODE_START == ENTRY and CARGO_CODE_END == self.receipt["cargoCodeBytes"]
             and CARGO_CODE_START < CARGO_CODE_END < CARGO_WILD_START < CARGO_WILD_END <= len(expected) <= MAX_IMAGE
             and CARGO_CODE_END % 4 == 0 and len(expected) % 4 == 0
             and self.receipt["cargoWildRange"] == (CARGO_WILD_START, CARGO_WILD_END)
             and CARGO_ABI_OFFSET == 100 and CARGO_ABI_SIZE == 16,
             "authenticated Cargo code range differs")
        if full_image:
            for offset in range(0,len(expected),READ_BUDGET):
                chunk=expected[offset:offset+READ_BUDGET]
                need(self._read(entry+offset,len(chunk))==chunk,"live relocated image differs")
        else:
            # Prefix includes its exact typed descriptor; no partial-tail read.
            need(self._read(entry,CARGO_CODE_END) == expected[:CARGO_CODE_END],
                 "live Cargo code/ABI differs")
            need(self._read(entry+CARGO_WILD_START,CARGO_WILD_END-CARGO_WILD_START)
                    == expected[CARGO_WILD_START:CARGO_WILD_END],
                 "live CargoWild module differs")

    def _authenticate(self, expected_entry=None, full_image=False):
        self.read_bytes = 0
        self.read_limit = INITIAL_READ_BUDGET if full_image else READ_BUDGET
        need(self.session.packaged_code(self.service, 24) == self.service_bytes,
             "current Selector service differs")
        flag = self._read(0x023C8148, 1)[0]
        need(flag & 0x40, "Selector is unloaded")
        raw = self._read(self.state, 28)
        blob, size, entry, field, epoch, generation, member, phase, reserved = struct.unpack("<4I2HIB3s", raw)
        need(phase == 1 and reserved == bytes(3) and member == 21 and size == len(self.blob)
             and entry == blob + 64 and epoch and generation, "loader is not current/active")
        need(expected_entry is None or entry == expected_entry, "QueryAddon return differs from loader")
        need(field == self.session.field_pointer(), "current Field identity differs")
        lifecycle = self.session._field_actor_availability(field)
        need(lifecycle.get("authenticated") is True and lifecycle.get("reason") is None,
             "current Field is unavailable")
        descriptor = self.session.rt.ACTOR_DESCRIPTOR["state"]
        owner_context = self._read(descriptor["address"] + 12, 4)
        map_generation = self._read(descriptor["address"] + 44, 4)
        need(struct.unpack_from("<H", owner_context)[0] == epoch
             and struct.unpack_from("<H", map_generation, 2)[0] == generation,
             "current Actor owner differs")
        expected = relocated_image(self.image, self.receipt, entry)
        self._image_identity(entry,expected,full_image)
        return dict(rawHex=raw.hex(), field=field, entry=entry, fieldEpoch=epoch,
                    mapGeneration=generation, expected=expected)

    def _discover_before(self):
        need(self.session.packaged_code(self.discovery, 32) == self.discovery_bytes,
             "fixed QueryAddon live body differs")
        return {}

    def _discover_after(self, before, context):
        need(self.session.packaged_code(self.discovery, 32) == self.discovery_bytes,
             "fixed QueryAddon lost code identity before return")
        entry = context["returnValue"]
        if entry == 0:
            return None
        owner = self._authenticate(entry,full_image=self.loaded is None)
        if self.loaded is None:
            self.loaded = owner
            self.tick_token = self._tap(entry + TICK_OFFSET, self._tick_before, self._tick_after, LABEL)
        elif owner["rawHex"] != self.loaded["rawHex"]:
            previous = bytes.fromhex(self.loaded["rawHex"])
            current = bytes.fromhex(owner["rawHex"])
            # Rebind drains before publishing. It keeps this exact loaded image
            # and Field; only the authenticated current context pair may change.
            need(current[:16] == previous[:16] and current[20:] == previous[20:],
                 "recorded addon image/Field owner changed")
            epoch, generation = self.loaded["fieldEpoch"], self.loaded["mapGeneration"]
            need(owner["fieldEpoch"] == epoch
                 or (owner["fieldEpoch"] == (epoch % 0xFFFF + 1)
                     and owner["mapGeneration"] == (generation % 0xFFFF + 1)),
                 "recorded addon owner skipped paired Rebind")
            self.loaded = owner
        return None

    def _unload_identity(self):
        need(self.session.packaged_code(self.unload, len(self.unload_bytes)) == self.unload_bytes,
             "native Unload live body differs")
        need(self.session.packaged_code(self.service, 24) == self.service_bytes,
             "current Selector service differs during Unload")
        need(self._read(0x023C8148, 1)[0] & 0x40, "Selector is unloaded during Unload")

    def _unload_before(self):
        self.read_bytes = 0
        self.read_limit = INITIAL_READ_BUDGET if self.loaded is None else READ_BUDGET
        self._unload_identity()
        need(self.session.emu.memory.register_arm9.r0 & 0xFFFFFFFF == self.state,
             "Unload state pointer differs")
        need(not any(c["label"] in (LABEL, ENTRY_LABEL, ENTRY_CONTROL_LABEL) for c in self.contexts),
             "Unload has an in-flight Tick")
        need(not self.pending_detaches, "Unload precedes observed Actor detach")
        raw = self._read(self.state, 28)
        if raw != bytes(28):
            blob, size, entry, field, epoch, generation, member, phase, reserved = struct.unpack("<4I2HIB3s", raw)
            need(size == len(self.blob) and entry == blob + 64 and field == self.session.field_pointer()
                 and epoch and generation and member == 21 and reserved == bytes(3)
                 and phase in (1, 2), "Unload has no authenticated published owner")
            if self.loaded is not None:
                need(raw == bytes.fromhex(self.loaded["rawHex"]) or raw == self.draining,
                     "Unload recorded owner changed")
            else:
                need(phase == 1, "Unload has an unobserved pending drain")
            expected = relocated_image(self.image, self.receipt, entry)
            self._image_identity(entry,expected,full_image=self.loaded is None)
        else:
            need(self.loaded is None, "recorded owner cleared without completed Unload")
        return dict(rawHex=raw.hex())

    def _unload_after(self, before, context):
        self.read_bytes = 0
        self.read_limit = READ_BUDGET
        self._unload_identity()
        need(not any(c["label"] in (LABEL, ENTRY_LABEL, ENTRY_CONTROL_LABEL) for c in self.contexts),
             "Unload returned with an in-flight Tick")
        raw = self._read(self.state, 28)
        status = context["returnValue"]
        need(status in (0, 1, 5), "Unload return enum differs")
        prior = bytes.fromhex(before["rawHex"])
        if status == 0:
            # The implementation drains, clears this entire state, then frees.
            # Only this authenticated return may retire a recorded image tap.
            need(raw == bytes(28), "successful Unload did not clear publication")
            if self.tick_token is not None:
                self.observer.hooks.remove(self.tick_token)
                self.tokens.remove(self.tick_token)
                self.observer.tokens.remove(self.tick_token)
            self.tick_token = self.draining = self.loaded = None
        elif status == 5:
            need(prior != bytes(28) and raw[:24] == prior[:24]
                 and raw[24] == 2 and raw[25:] == prior[25:],
                 "pending Unload changed its owner")
            self.draining = raw
        else:
            need(raw == prior, "failed Unload changed publication")
        return None

    def _current_handle(self, value):
        if value is None:
            return False
        actor = self.session.rt.actor_state(self.session.emu, value["slot"])
        return actor.get("active") is True and actor.get("handle") == value

    def _state_view(self, state, slot, owner, route_operation=0, *, entry=None, boundary="tick-entry"):
        need(state == self.session.rt.WILD_STATE, "Wild state owner differs")
        field, runtime = struct.unpack("<2I", self._read(state + 0xE0, 8))
        native = (entry or {}).get("nativeControl")
        request = (entry or {}).get("request")
        # Follower metadata is resolved before creation can bind the Wild
        # movement Field. This exact typed call cannot acquire an Actor.
        follower_finalize = False
        if route_operation == 1 and native is not None and native["operation"] == 2 and slot == 7:
            o = ENTRY_LAYOUT
            raw = bytes.fromhex(native["rawHex"])
            u32 = lambda name: struct.unpack_from("<I", raw, o["Control_" + name])[0]
            follower_finalize = (native["prepared"] % 4 == 0
                and 0x02000000 <= native["prepared"] <= 0x02800000 - 260
                and all(u32(name) == 0 for name in ("profile", "primitives", "object",
                             "receipt", "startCommitSequence", "value"))
                and all(raw[o["Control_" + name]] == 0 for name in
                        ("terrain", "queryOperation", "accepted", "usableIdle")))
        need((field == owner["field"] or (field == 0 and follower_finalize))
             and runtime % 4 == 0
             and 0x02000000 <= runtime <= 0x02400000 - RUNTIME_SIZE,
             "Wild runtime owner differs "
             f"(expectedField={owner['field']:#x}, field={field:#x}, runtime={runtime:#x}, "
             f"boundary={boundary}, routeOperation={route_operation}, slot={slot}, "
             f"nativeOperation={(native or {}).get('operation')}, "
             f"entryOperation={(request or {}).get('operation')})")
        conditions, query = struct.unpack("<2I", self._read(runtime + RUNTIME_CONDITIONS, 8))
        absent_reason = ("conditions are absent or outside owner memory "
            f"(boundary={boundary}, slot={slot}, routeOperation={route_operation}, "
            f"nativeOperation={(native or {}).get('operation')}, "
            f"queryOperation={(native or {}).get('queryOperation')}, "
            f"entryOperation={(request or {}).get('operation')})")
        if conditions == 0:
            # The complete packet/Ops is authenticated first and immutable at
            # return. These three setup paths precede lazy condition allocation;
            # none can credit Cargo or an ordinary current Actor binding.
            refill = route_operation == 1 and native is not None and (
                native["operation"] in (7, 9)
                or (native["operation"] == 8 and native["queryOperation"] == 1))
            prepare = route_operation == 1 and native is None and request is not None \
                and request["operation"] == 0 and request["actor"] is None
            need(refill or follower_finalize or prepare, absent_reason)
            need(self.session.rt.actor_state(self.session.emu, slot).get("active") is False,
                 "current full Subject differs")
            if prepare:
                o = ENTRY_LAYOUT
                at = o["Runtime_queuedSpawnSlotPlusOne"]
                queued_slot = self._read(runtime + (at & ~3), 4)[at & 3]
                serial = struct.unpack("<I", self._read(runtime + o["Runtime_queuedSpawnSerial"], 4))[0]
                need(queued_slot == slot + 1 and serial == request["serial"],
                     "cold PREPARE queued owner differs")
            result = dict(runtime=runtime, conditions=0, queryPointer=query,
                          frameValid=False, worldFrame=None, worldSubject=None,
                          subject=None, workspace=None, conditionState="not-prepared")
        else:
            need(conditions % 4 == 0 and 0x02000000 <= conditions <= 0x02400000 - 3100,
                 absent_reason)
            frame = self._read(conditions + FRAME_WORLD, 16)
            tail = self._read(conditions + FRAME_VALID - 3, 4)
            need(tail[3] in (0, 1), "condition frame valid byte differs")
            binding = self._read(conditions + BINDINGS + slot * 60, 60 if field == 0 else 12)
            subject = handle(binding[:12])
            actor = self.session.rt.actor_state(self.session.emu, slot)
            if field == 0:
                # Context detach keeps this allocation and its old World cache.
                # Only the cleared selected record may describe absence.
                prepared = self._read(conditions + slot * CONDITION_ACTOR_SIZE, CONDITION_ACTOR_SIZE)
                count, valid, capacity = struct.unpack_from("<BBH", prepared, 80)
                active_mask = self._read(conditions + CONDITION_ACTIVE_MASKS + slot * 4, 4)
                need(tail[3] == 0 and binding == bytes(60)
                     and actor.get("active") is False
                     and struct.unpack_from("<I", prepared, 12)[0] == 0
                     and valid == 0 and count <= capacity <= 32 and active_mask == bytes(4),
                     "unbound follower condition record is not cleared")
            if subject is None:
                need(route_operation == 1 and (actor.get("active") is False
                     or (boundary == "tick-return" and self._pending_actor(slot, owner, actor))),
                     "current full Subject differs")
            else:
                need(subject["slot"] == slot and subject["fieldEpoch"] == owner["fieldEpoch"]
                     and subject["mapGeneration"] == owner["mapGeneration"]
                     and actor.get("active") is True and actor.get("handle") == subject,
                     "current full Subject differs")
            result = dict(runtime=runtime, conditions=conditions, queryPointer=query,
                          frameValid=bool(tail[3]), worldFrame=struct.unpack_from("<I", frame, 12)[0],
                          worldSubject=handle(frame[:12]), subject=subject, workspace=None)
        if field == 0:
            result.update(wildFieldState="unbound", conditionState="not-prepared",
                          worldFrame=None, worldSubject=None)
        if query == 0:
            return result
        need(0x02000000 <= query <= 0x02400000 - QUERY_SIZE, "workspace allocation range differs")
        prefix = self._read(query, QUERY_PREFIX_SIZE)
        qowner = handle(self._read(query + QUERY_OWNER, 12))
        valid = self._read(query + QUERY_VALID, 4)
        entry_active = self._read(query + (QUERY_ENTRY_ACTIVE & ~3), 4)[QUERY_ENTRY_ACTIVE & 3]
        o = STATE_OFFSETS
        u16 = lambda name: struct.unpack_from("<H", prefix, o[name])[0]
        u32 = lambda name: struct.unpack_from("<I", prefix, o[name])[0]
        position = lambda name: dict(zip(("x", "y", "baseY", "surfaceId", "reserved"),
                                        struct.unpack_from("<hhiHH", prefix, o[name])))
        need((u16("version"), u16("size")) == (2, QUERY_STATE_SIZE)
             and u32("storage") == query + QUERY_STATE_SIZE
             and valid[0] in (0, 1) and prefix[o["started"]] in (0, 1)
             and entry_active in (0, 1) and u16("route_nodeCount") <= 256,
             "workspace layout/header differs")
        owner_current = self._current_handle(qowner)
        result["workspace"] = dict(owner=qowner, ownerCurrent=owner_current,
            cargoOwnerCredited=route_operation == 0 and bool(valid[0]) and owner_current,
            entryActive=bool(entry_active), valid=bool(valid[0]), started=bool(prefix[o["started"]]),
            phase=prefix[o["route_phase"]], nodeCount=u16("route_nodeCount"),
            routeSubject=handle(prefix[o["route_query_subject"]:o["route_query_subject"]+12]),
            stateSubject=handle(prefix[o["query_subject"]:o["query_subject"]+12]),
            edgeQueries=prefix[o["work_edgeQueries"]], goalQueries=prefix[o["work_goalQueries"]],
            compatibility=dict(cargo=handle(prefix[o["query_cargo"]:o["query_cargo"]+12]),
                bounds=dict(zip(("minX", "minY", "maxX", "maxY"), struct.unpack_from("<4h", prefix, o["query_bounds"]))),
                scopeRevision=u32("query_scopeRevision"), movementPolicyRevision=u32("query_movementPolicyRevision"),
                edges=u32("query_edges"), edgeCount=u16("query_edgeCount"), requestKey=u32("requestKey"),
                roleMask=prefix[o["roleMask"]], pickupDistance=prefix[o["distance"]], required=prefix[o["required"]]),
            origin=position("query_origin"), dynamicRevision=u32("query_dynamicRevision"),
            storage=u32("storage"), stateFrame=u32("frame"), candidate=prefix[o["candidate"]],
            scan=prefix[o["scan"]], active=prefix[o["active"]],
            routeProgress=dict(goal=position("goal"), cargoPosition=position("query_cargoPosition"),
                goalRevision=u32("query_goalRevision"), routeGoalRevision=u32("route_query_goalRevision"),
                goalNode=u16("route_goalNode"), proofNode=u16("route_proofNode"), proofLength=u16("route_proofLength"),
                probeNeeded=prefix[o["route_probeNeeded"]], edgeOwed=prefix[o["edgeOwed"]],
                goalValid=prefix[o["goalValid"]], goalDirty=prefix[o["goalDirty"]]),
            lastWorkHex=prefix[o["lastWork"]:o["lastWork"]+28].hex())
        return result

    def _entry_packet(self, call, world, owner):
        # The native tag is read before the ordinary request. Native controls
        # deliberately contain an all-zero ordinary request.
        o = ENTRY_LAYOUT
        need(bool(o), "final Entry ARM layout is not sealed")
        pointer = struct.unpack_from("<I", call, 8)[0]
        raw = self._read(pointer, o["Command"])
        control_pointer = struct.unpack_from("<I", raw, o["Command_nativeControl"])[0]
        base = dict(pointer=pointer, rawHex=raw.hex(), nativeControl=None)
        if control_pointer:
            control = self._read(control_pointer, o["Control"])
            u32 = lambda name: struct.unpack_from("<I", control, o["Control_" + name])[0]
            u8 = lambda name: control[o["Control_" + name]]
            need(struct.unpack_from("<HH", control) == (1, o["Control"])
                 and control[o["Control_reserved"]:] == bytes(2)
                 and u8("operation") in range(10) and u8("slot") == world[52]
                 and u8("accepted") in (0, 1) and u8("usableIdle") in (0, 1)
                 and u32("state") == struct.unpack_from("<I", world, 8)[0]
                 and u32("field") == owner["field"]
                 # Follower maintenance issues GUIDE/UPDATE, which the native
                 # owner rejects before writing even the value output.
                 and (u8("slot") != 7 or u8("operation") in (2, 3, 4))
                 and (u8("operation") != 1 or u8("queryOperation") in range(4)),
                 "typed native Entry control differs")
            if u8("operation") == 8:
                need(u8("queryOperation") in (0, 1), "native Spawn subtype differs")
            if u8("operation") in (7, 9) or (u8("operation") == 8 and u8("queryOperation") == 1):
                need(u32("value") == 0 and u8("slot") == 0 and u8("terrain") == 0
                     and u8("accepted") == 0 and u8("usableIdle") == 0
                     and all(u32(name) == 0 for name in ("profile", "primitives", "prepared",
                              "object", "receipt", "startCommitSequence"))
                     and (u8("queryOperation") == 0 if u8("operation") == 7
                          else u8("queryOperation") in (0, 1)),
                     "native refill control input differs")
            need(raw[:o["Command_nativeControl"]] == bytes(o["Command_nativeControl"])
                 and u32("profile") == struct.unpack_from("<I", call, 4)[0],
                 "native Entry command/input differs")
            need(u32("ops") == self.native_ops_address
                 and self._read(u32("ops"), o["ControlOps"]) == self.native_ops_bytes,
                 "current native Entry Ops differs")
            base["nativeControl"] = dict(pointer=control_pointer, rawHex=control.hex(),
                operation=u8("operation"), slot=u8("slot"), terrain=u8("terrain"),
                queryOperation=u8("queryOperation"), prepared=u32("prepared"),
                object=u32("object"), receipt=u32("receipt"), value=u32("value"))
            if u8("slot") == 7 and u8("operation") in (3, 4):
                base["nativeControl"]["rejectedFollower"] = True
            return base
        request = raw[:o["Request"]]
        u32 = lambda name: struct.unpack_from("<I", request, o["Request_" + name])[0]
        op, slot = request[o["Request_operation"]], request[o["Request_slot"]]
        actor_offset = o["Request_actor"]
        actor = handle(request[actor_offset:actor_offset + 12])
        need(struct.unpack_from("<HH", request) == (1, o["Request"])
             and op in range(4) and slot == world[52] and slot != 7
             and u32("serial") and u32("fieldEpoch") == owner["fieldEpoch"]
             and u32("mapGeneration") == owner["mapGeneration"]
             and (actor is None if op == 0 else actor is not None)
             and raw[o["Command_reserved"]] == 0
             and all(raw[o["Command_" + key]] in (0, 1)
                     for key in ("accepted", "usableIdle", "safelyOffscreen")),
             "typed ordinary Entry request differs")
        for name in ("destination", "origin"):
            need(struct.unpack_from("<H", request, o["Request_" + name] + 10)[0] == 0,
                 "Entry position reserved differs")
        receipt_pointer = struct.unpack_from("<I", raw, o["Command_receipt"])[0]
        need(receipt_pointer % 4 == 0 and 0x02000000 <= receipt_pointer <= 0x02800000 - o["Receipt"],
             "Entry receipt pointer differs")
        base["request"] = dict(operation=op, slot=slot, serial=u32("serial"), actor=actor,
                               receipt=receipt_pointer)
        return base

    def _entry_receipt(self, pointer):
        o = ENTRY_LAYOUT
        raw = self._read(pointer, o["Receipt"])
        actor_at = o["Receipt_actor"]
        actor = handle(raw[actor_at:actor_at + 12])
        status, reads, queued, has_next = (raw[o["Receipt_" + name]]
                                          for name in ("status", "readsUsed", "queued", "hasNextStep"))
        need(struct.unpack_from("<HH", raw) == (1, o["Receipt"])
             and status in range(5) and reads <= 8 and queued in (0, 1, 2) and has_next in (0, 1)
             and struct.unpack_from("<H", raw, o["Receipt_stepsRemaining"])[0] <= 96,
             "typed Entry receipt differs")
        for name in ("origin", "target", "nextStep"):
            need(struct.unpack_from("<H", raw, o["Receipt_" + name] + 10)[0] == 0,
                 "Entry receipt position reserved differs")
        return dict(serial=struct.unpack_from("<I", raw, o["Receipt_serial"])[0], actor=actor,
                    status=status, readsUsed=reads, queued=queued, hasNextStep=has_next, rawHex=raw.hex())

    def _constructor_identity(self):
        # A typed Thumb body may start on the second halfword. Keep data reads
        # word aligned, and charge the small enclosing prefix to this budget.
        prefix = self.native_spawn_address & 3
        need(prefix in (0, 2)
             and self.session.packaged_code(self.native_spawn_address, len(self.native_spawn_bytes)) == self.native_spawn_bytes
             and self._read(self.native_spawn_address - prefix,
                            len(self.native_spawn_bytes) + prefix)[prefix:] == self.native_spawn_bytes,
             "Commit constructor full body differs")

    def _commit_queue(self, runtime):
        self._constructor_identity()
        o = ENTRY_LAYOUT
        at = o["Runtime_queuedSpawnSlotPlusOne"]
        slot_plus_one = self._read(runtime + (at & ~3), 4)[at & 3]
        serial = struct.unpack("<I", self._read(runtime + o["Runtime_queuedSpawnSerial"], 4))[0]
        need(slot_plus_one <= 10 and (slot_plus_one == 0 or serial != 0),
             "Commit queued owner differs")
        return dict(slot=None if slot_plus_one == 0 else slot_plus_one - 1,
                    serial=serial, prepared=runtime + o["Runtime_queuedSpawn"],
                    sequence=self.observer.sequence, adoptions=[])

    def _entry_return(self, before, owner, context):
        entry = before.get("entry")
        if entry is None:
            return None
        need(self._read(entry["pointer"], ENTRY_LAYOUT["Command"]).hex() == entry["rawHex"],
             "Entry command changed before return")
        native = entry["nativeControl"]
        if native is not None:
            raw = self._read(native["pointer"], ENTRY_LAYOUT["Control"])
            prior = bytes.fromhex(native["rawHex"])
            offset = ENTRY_LAYOUT["Control_value"]
            need(raw[:offset] == prior[:offset] and raw[offset + 4:] == prior[offset + 4:]
                 and self._read(self.native_ops_address, ENTRY_LAYOUT["ControlOps"]) == self.native_ops_bytes,
                 "native Entry input/owner changed before return")
            result = dict(kind="native-control", operation=native["operation"],
                          value=struct.unpack_from("<I", raw, offset)[0])
            if native["operation"] in (7, 9):
                value = result["value"]
                delay = (value >> 8) & 0xFFFF if native["operation"] == 7 else value
                need(context["returnValue"] == 1 and delay in (0, 15, 60, 120, 180, 240, 300, 360)
                     and (native["operation"] != 7 or (value >> 24 == 0
                          and (value & 0xFF) in range(4)
                          and ((value & 0xFF) in (2, 3) or delay == 0))),
                     "native refill control outcome/delay differs")
                result["refillDelay"] = delay
                if native["operation"] == 7:
                    result["outcome"] = value & 0xFF
            if native["operation"] == 8 and native["queryOperation"] == 1:
                value = result["value"]
                prepare_result, delay = value & 0xFF, (value >> 8) & 0xFFFF
                need(context["returnValue"] == 1 and value >> 24 == 0
                     and prepare_result in (0, 1, 2)
                     and delay in (0, 15, 60, 120, 180, 240, 300, 360)
                     and (prepare_result == 0 or delay == 0),
                     "native ordinary refill outcome/delay differs")
                result.update(queryOperation=1, prepareResult=prepare_result, refillDelay=delay)
            if native.get("rejectedFollower"):
                need(context["returnValue"] == 3 and raw == prior,
                     "rejected follower Entry control changed or was not INVALID")
                result["rejectedFollower"] = True
            return result
        request = entry["request"]
        receipt = self._entry_receipt(request["receipt"])
        need(receipt["serial"] == request["serial"] and receipt["status"] == context["returnValue"],
             "Entry receipt lost its request")
        if request["operation"] == 1 and context["returnValue"] == 1:
            need(receipt["actor"] == request["actor"] and self._current_handle(receipt["actor"]),
                 "ADOPT receipt full Subject differs")
            parents = [item["data"] for item in self.contexts
                       if ((item["data"].get("entry") or {}).get("nativeControl") or {}).get("operation") == 7]
            if parents:
                parent = parents[-1]
                queue = parent["queued"]
                need(parent["owner"] == before["owner"] and queue["slot"] == request["slot"]
                     and queue["serial"] == request["serial"] and self.observer.spawn_contexts,
                     "ADOPT has no exact Commit constructor owner")
                constructor = self.observer.spawn_contexts[-1]
                need(constructor["slot"] == queue["slot"]
                     and constructor["preparedPointer"] == queue["prepared"]
                     and constructor["statePointer"] == before["state"]
                     and constructor["fieldPointer"] == owner["field"]
                     and not queue["adoptions"], "ADOPT constructor/queue binding differs")
                queue["adoptions"].append(dict(receipt, constructorPointer=queue["prepared"]))
        if request["operation"] == 2:
            parents = [item["data"] for item in self.contexts
                       if ((item["data"].get("entry") or {}).get("nativeControl") or {}).get("operation") == 3]
            if parents:
                parent = parents[-1]
                need(parent["owner"] == before["owner"] and parent["slot"] == request["slot"]
                     and parent["before"]["subject"] == request["actor"], "GUIDE route parent differs")
                parent["guideRetirement"] = receipt
        if request["operation"] == 3:
            removals = [item["data"] for item in self.contexts
                        if item.get("address") == self.remove_address]
            if removals:
                removal = removals[-1]
                parent = removal["parent"]
                expected = bytearray(ENTRY_LAYOUT["Receipt"])
                struct.pack_into("<HHI", expected, 0, 1, ENTRY_LAYOUT["Receipt"], request["serial"])
                expected[ENTRY_LAYOUT["Receipt_status"]] = 1
                need(context["returnValue"] == 1 and receipt["rawHex"] == expected.hex()
                     and parent["owner"] == before["owner"]
                     and all(parent[key] == before[key] for key in ("state", "field", "slot"))
                     and request["actor"] == removal["subject"]
                     and request["serial"] == removal["serial"]
                     and removal.get("entryRetired") is None, "GUIDE removal Entry RETIRE differs")
                removal["entryRetired"] = receipt
        return dict(kind="ordinary-route", operation=request["operation"], receipt=receipt)

    def _commit_admission(self, before, owner, context, entry_result):
        queue = before.get("queued")
        if queue is None:
            return None
        self._constructor_identity()
        if queue["slot"] is None:
            need(entry_result["outcome"] == 0, "empty Commit outcome differs")
            return None
        rows = [row for row in self.observer.pending
                if row.get("observation") == "spawn-prepared" and row.get("sequence", -1) > queue["sequence"]
                and row.get("slot") == queue["slot"] and row.get("preparedPointer") == queue["prepared"]
                and row.get("fieldPointer") == owner["field"] and row.get("statePointer") == before["state"]
                and row.get("returnValue") == 1]
        need(len(rows) <= 1, "Commit has repeated constructor receipts")
        need((entry_result["outcome"] == 3) == bool(rows),
             "Commit outcome and constructor differ")
        if not rows:
            return None
        row = rows[0]
        need(self.observer.calls.get("spawn-prepared", {}).get("address") == self.native_spawn_address,
             "Commit constructor hook owner differs")
        subject = row.get("publicSubject", {})
        actor = subject.get("handle")
        need(row.get("setupMode") == context["setupMode"]
             and context["entry"]["nativeCycle"] <= row["entryNativeCycle"] <= row["returnNativeCycle"]
                 <= context["returned"]["nativeCycle"]
             and subject.get("status") == "observed-public-subject"
             and actor is not None and actor["slot"] == queue["slot"]
             and actor["fieldEpoch"] == owner["fieldEpoch"] and actor["mapGeneration"] == owner["mapGeneration"]
             and self._current_handle(actor), "Commit constructor full admission differs")
        world = row.get("worldContext", {})
        need(world.get("fieldPointer") == owner["field"] and world.get("statePointer") == before["state"]
             and world.get("fieldEpoch") == owner["fieldEpoch"]
             and world.get("mapGeneration") == owner["mapGeneration"]
             and struct.unpack("<I", self._read(before["before"]["runtime"]
                       + ENTRY_LAYOUT["Runtime_queuedSpawnSerial"], 4))[0] == queue["serial"],
             "Commit constructor queue/Field changed")
        if row.get("startup", {}).get("locomotion") == 3:
            need(len(queue["adoptions"]) == 1 and queue["adoptions"][0]["actor"] == actor,
                 "Move constructor has no exact ADOPT receipt")
        return dict(slot=queue["slot"], serial=queue["serial"], actor=actor,
                    constructorSequence=row["sequence"], moveAdopted=bool(queue["adoptions"]))

    def _remove_before(self):
        parents = [item["data"] for item in self.contexts
                   if ((item["data"].get("entry") or {}).get("nativeControl") or {}).get("operation") == 3]
        if not parents:
            return None
        parent = parents[-1]
        owner = self._authenticate()
        need(owner["rawHex"] == parent["owner"], "GUIDE removal lease differs")
        guide = parent.get("guideRetirement")
        need(guide is not None and guide["status"] == 2 and guide["queued"] == 2,
             "GUIDE removal has no exact retiring route result")
        regs = self.session.emu.memory.register_arm9
        need([getattr(regs, name) & 0xFFFFFFFF for name in ("r0", "r1", "r2")]
                 == [parent["state"], parent["field"], parent["slot"]],
             "GUIDE removal state/Field/slot differs")
        subject = parent["before"]["subject"]
        native = parent["entry"]["nativeControl"]
        need(subject is not None and self._current_handle(subject) and native["object"],
             "GUIDE removal full Subject differs")
        source = self.session.rt.wild_spawn(self.session.emu, parent["slot"])
        engine = self.session.rt.live_wild_object_identity(self.session.emu, parent["slot"])
        from tools.overworld.devtools_runtime import actor_identity_checks
        actor = self.session.rt.actor_state(self.session.emu, parent["slot"])
        world = dict(fieldEpoch=subject["fieldEpoch"], mapGeneration=subject["mapGeneration"],
                     mapId=self.session.rt.field_map_id(self.session.emu))
        need(all(actor_identity_checks(actor, source, engine, world, parent["slot"]).values())
             and source.get("object") == engine.get("pointer") == native["object"],
             "GUIDE removal current native object differs")
        need(self.session.packaged_code(self.remove_address, len(self.remove_bytes)) == self.remove_bytes
             and self._read(self.remove_address, len(self.remove_bytes)) == self.remove_bytes,
             "GUIDE removal native body differs")
        need(parent["slot"] not in self.pending_detaches and guide["serial"] != 0
             and struct.unpack("<I", self._read(parent["before"]["runtime"]
                 + ENTRY_LAYOUT["Runtime_entryRouteSerial"] + parent["slot"] * 4, 4))[0] == guide["serial"],
             "GUIDE removal repeats pending detach or changed its trip")
        return dict(parent=parent, subject=subject, object=native["object"],
                    source=dict(source), species=actor["species"], personality=actor["subjectIdentity"],
                    serial=guide["serial"])

    def _pending_actor(self, slot, owner, actor):
        pending = self.pending_detaches.get(slot)
        if pending is None:
            return False
        need(owner["rawHex"] == pending["owner"] and type(actor.get("active")) is bool
             and actor.get("handle") == pending["actor"]
             and actor.get("role") == "WILD" and actor.get("species") == pending["species"]
             and actor.get("subjectIdentity") == pending["personality"],
             "pending detach Actor identity changed")
        source = self.session.rt.wild_spawn(self.session.emu, slot)
        need(all(type(value) is int for value in source.values())
             and source == pending["clearedSource"]
             and self._read(pending["object"], 4) == bytes(4),
             "pending detach source or deleted object changed")
        return True

    def _remove_after(self, before, context):
        parent = before["parent"]
        owner = self._authenticate()
        need(owner["rawHex"] == parent["owner"] and parent.get("removal") is None
             and self.session.packaged_code(self.remove_address, len(self.remove_bytes)) == self.remove_bytes
             and self._read(self.remove_address, len(self.remove_bytes)) == self.remove_bytes,
             "GUIDE removal owner changed")
        source = self.session.rt.wild_spawn(self.session.emu, parent["slot"])
        cleared = dict(before["source"], object=0, personality=0, map_id=1,  # MAP_NOTHING
                       species=0, form=0, level=0, active=0)
        retired = before.get("entryRetired")
        runtime = parent["before"]["runtime"]
        conditions = parent["before"]["conditions"]
        need(all(type(value) is int for value in source.values())
             and source == cleared and self._read(before["object"], 4) == bytes(4)
             and retired is not None and retired["serial"] == before["serial"]
             and self._read(runtime + ENTRY_LAYOUT["Runtime_entryRouteSerial"] + parent["slot"] * 4, 4) == bytes(4)
             and self._read(conditions + BINDINGS + parent["slot"] * 60, 12) == bytes(12),
             "GUIDE removal lacks exact source/delete/Entry retirement")
        pending = dict(actor=before["subject"], object=before["object"], source=before["source"],
                       clearedSource=cleared, species=before["species"], personality=before["personality"],
                       serial=before["serial"], field=parent["field"], state=parent["state"], slot=parent["slot"],
                       owner=parent["owner"], mapId=self.session.rt.field_map_id(self.session.emu),
                       runtime=runtime, conditions=conditions, removed=dict(context["returned"]),
                       guideReturned=False)
        self.pending_detaches[parent["slot"]] = pending
        actor = self.session.rt.actor_state(self.session.emu, parent["slot"])
        need(self._pending_actor(parent["slot"], owner, actor), "GUIDE removal pending identity differs")
        parent["removal"] = dict(actor=pending["actor"], object=pending["object"], serial=pending["serial"],
                                 field=pending["field"], slot=pending["slot"], actorDetached=False)
        return None

    def completed_snapshot(self, snapshot):
        if not self.pending_detaches:
            return
        owner = self._authenticate()
        need(not self.contexts and snapshot.get("observationBoundary") == "main-task-queue-completion",
             "pending detach sample is not a completed boundary")
        clock = {key: snapshot.get(key) for key in ("actorFrame", "nativeCycle")}
        need(all(type(value) is int and value >= 0 for value in clock.values())
             and type(snapshot.get("frame")) is int and snapshot["frame"] >= 0
             and clock == self.observer._clock(), "pending detach completed clock differs")
        completed = []
        for slot, pending in self.pending_detaches.items():
            need(owner["rawHex"] == pending["owner"] and pending["guideReturned"]
                 and snapshot.get("context") == dict(mapId=pending["mapId"],
                     fieldEpoch=pending["actor"]["fieldEpoch"], mapGeneration=pending["actor"]["mapGeneration"])
                 and clock["nativeCycle"] >= pending["removed"]["nativeCycle"]
                 and clock["actorFrame"] >= pending["removed"]["actorFrame"],
                 "pending detach world or call order changed")
            need(struct.unpack("<2I", self._read(pending["state"] + 0xE0, 8))
                    == (pending["field"], pending["runtime"])
                 and struct.unpack("<I", self._read(pending["runtime"] + RUNTIME_CONDITIONS, 4))[0]
                    == pending["conditions"]
                 and self._read(pending["conditions"] + BINDINGS + slot * 60, 12) == bytes(12)
                 and self._read(pending["runtime"] + ENTRY_LAYOUT["Runtime_entryRouteSerial"] + slot * 4, 4)
                    == bytes(4), "pending detach runtime or trip changed")
            # The existing typed readers consume exactly Actor88 + Wild20.
            # Include those reads in this completed-sample ceiling as well.
            need(self.read_bytes + 108 <= READ_BUDGET, "callback read budget exceeded")
            self.read_bytes += 108
            actor = self.session.rt.actor_state(self.session.emu, slot)
            need(self._pending_actor(slot, owner, actor), "pending detach Actor differs")
            if clock["actorFrame"] == pending["removed"]["actorFrame"]:
                continue  # Removal can follow the current frame's Actor synchronization.
            need(actor.get("active") is False and actor.get("inputOwnership") == 0
                 and actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE"
                 and not any(item.get("handle", {}).get("slot") == slot for item in snapshot.get("actors", [])),
                 "subsequent Actor synchronization did not detach the exact actor")
            context = dict(entry=pending["removed"], returned=clock,
                           setupMode="prepared" if self.session.prepared else "normal", returnValue=0)
            self.observer._queue("entry-actor-detached", context, dict(
                boundary="native-entry-actor-detached", actor=pending["actor"], object=pending["object"],
                field=pending["field"], slot=slot, serial=pending["serial"],
                personality=pending["personality"], actorDetached=True,
                diagnosticOnly=True, acceptedProof=False, readBytes=self.read_bytes))
            completed.append(slot)
        for slot in completed:
            del self.pending_detaches[slot]
        if completed:
            self.observer._flush_pending(snapshot["frame"])

    def _tick_before(self):
        owner = self._authenticate()
        need(self.loaded is not None and owner["rawHex"] == self.loaded["rawHex"],
             "Tick lost its authenticated image owner")
        regs = self.session.emu.memory.register_arm9
        call_pointer, result_pointer = regs.r0 & 0xFFFFFFFF, regs.r1 & 0xFFFFFFFF
        call = self._read(call_pointer, 32)
        operation = call[29]
        need(operation in (0, 1) and call[30:] == bytes(2), "typed route operation differs")
        world = self._read(struct.unpack_from("<I", call)[0], WORLD_SIZE)
        need(struct.unpack_from("<HH", world) == (WORLD_VERSION, WORLD_SIZE) and world[52] < 10
             and struct.unpack_from("<I", world, 4)[0] == owner["field"],
             "current typed Wild world differs")
        ops = self._read(struct.unpack_from("<I", world, 28)[0], 4)
        need(struct.unpack("<HH", ops) == (WORLD_VERSION, OPS_SIZE), "current typed Wild Ops differs")
        state = struct.unpack_from("<I", world, 8)[0]
        entry = self._entry_packet(call, world, owner) if operation else None
        before = self._state_view(state, world[52], owner, operation, entry=entry, boundary="tick-entry")
        if entry is not None and entry["nativeControl"] is None:
            need(entry["request"]["actor"] == before["subject"], "Entry request current Subject differs")
        queued = self._commit_queue(before["runtime"]) if entry is not None \
            and entry["nativeControl"] is not None and entry["nativeControl"]["operation"] == 7 else None
        return dict(state=state, field=owner["field"], slot=world[52], call=call_pointer, result=result_pointer,
                    callHex=call.hex(), entry=entry, queued=queued,
                    routeOperation=operation, owner=owner["rawHex"], before=before, readBytes=self.read_bytes)

    def _tick_after(self, before, context):
        owner = self._authenticate()
        need(owner["rawHex"] == before["owner"], "Tick owner changed before return")
        operation = before["routeOperation"]
        call = self._read(before["call"], 32)
        need(call[29] == operation and call[30:] == bytes(2) and call.hex() == before["callHex"],
             "Tick route operation/input changed before return")
        need(context["returnValue"] in range(5), "Tick return enum differs")
        entry_result = self._entry_return(before, owner, context)
        admission = self._commit_admission(before, owner, context, entry_result)
        after = self._state_view(before["state"], before["slot"], owner, operation, entry=before["entry"], boundary="tick-return")
        if "unbound" in (before["before"].get("wildFieldState"), after.get("wildFieldState")):
            need(before["before"].get("wildFieldState") == after.get("wildFieldState") == "unbound"
                 and after["conditions"] == before["before"]["conditions"]
                 and after["runtime"] == before["before"]["runtime"]
                 and after["queryPointer"] == before["before"]["queryPointer"]
                 and context["returnValue"] == 1
                 and (entry_result or {}).get("value") in (0, 1),
                 "unbound follower metadata owner or return changed")
        same_subject = after["subject"] == before["before"]["subject"]
        created_subject = admission is not None and admission["slot"] == before["slot"] \
            and admission["actor"] == after["subject"] and context["returnValue"] == 1
        retirement = None  # RemoveEncounter does not synchronize the Actor facade.
        removal = before.get("removal")
        removed_subject = removal is not None and removal["actor"] == before["before"]["subject"] \
            and after["subject"] is None and context["returnValue"] == 1 \
            and entry_result == dict(kind="native-control", operation=3, value=1)
        need(same_subject or created_subject or removed_subject, "Tick Subject changed before return")
        if removal is not None:
            need(removed_subject and not same_subject and not created_subject,
                 "GUIDE removal did not return its exact successful result")
            need(self._pending_actor(before["slot"], owner,
                     self.session.rt.actor_state(self.session.emu, before["slot"])),
                 "GUIDE pending detach identity changed before return")
            self.pending_detaches[before["slot"]]["guideReturned"] = True
        output = self._read(before["result"], 140)
        if (entry_result or {}).get("rejectedFollower"):
            need(same_subject and admission is None and retirement is None and output == bytes(140),
                 "rejected follower Entry control acquired work or changed its result")
        boundary = "native-cargo-tick-return" if operation == 0 else ("native-entry-control-tick-return" \
            if before["entry"]["nativeControl"] is not None else "native-entry-route-tick-return")
        return dict(boundary=boundary, entry=entry_result, admission=admission, retirement=retirement, removal=removal,
            diagnosticOnly=True, acceptedProof=False, routeOperation=operation,
            cargoOwnerCredited=operation == 0 and bool(after["workspace"] and after["workspace"]["cargoOwnerCredited"]),
            slot=before["slot"], subject=after["subject"],
            status=("PENDING", "REACHABLE", "UNREACHABLE", "INVALID", "RESOURCE_LIMIT")[context["returnValue"]],
            before=before["before"], after=after, resultStatus=output[138], resultHex=output.hex(),
            imageIdentity=dict(elfSha256=ELF_SHA, packageSha256=PACKAGE_SHA,
                loadedEntry=owner["entry"], tickEntry=owner["entry"] + TICK_OFFSET,
                loaderOwner=before["owner"]), readBytes=dict(entry=before["readBytes"], returned=self.read_bytes))

    def _receipt_cycle(self, clock):
        cycle = clock.get("nativeCycle")
        need(type(cycle) is int and cycle >= 0, "native cycle is invalid")
        need(self.count_cycle is None or cycle >= self.count_cycle, "native cycle moved backwards")
        if cycle != self.count_cycle:
            self.count_cycle, self.count = cycle, 0

    def _retirement_discovery(self, address, label):
        # GUIDE's quiet removal synchronously retires its exact Entry path.
        # The inner RETIRE reads Actor state through the native discovery leaf.
        # Permit only this fifth, unlabelled context; it gets all normal code,
        # current-lease and image checks before returning, and cannot recurse.
        if address != self.discovery or label is not None or len(self.contexts) != 4 or self.loaded is None:
            return False
        guide, removal, retire, request = self.contexts
        tick = self.loaded["entry"] + TICK_OFFSET
        if [item.get("address") for item in self.contexts] != [tick, self.remove_address, tick, tick]:
            return False
        if [item["label"] for item in self.contexts] != [ENTRY_CONTROL_LABEL, None, ENTRY_CONTROL_LABEL, ENTRY_LABEL]:
            return False
        parent, native, ordinary = guide["data"], retire["data"], request["data"]
        controls = [(item.get("entry") or {}).get("nativeControl") or {} for item in (parent, native)]
        route = (ordinary.get("entry") or {}).get("request") or {}
        subject = parent.get("before", {}).get("subject")
        terminal = parent.get("guideRetirement") or {}
        return (controls[0].get("operation") == 3 and controls[1].get("operation") == 6
            and route.get("operation") == 3 and subject is not None and route.get("actor") == subject
            and terminal.get("status") == 2 and terminal.get("queued") == 2
            and route.get("serial") == terminal.get("serial")
            and removal["data"].get("parent") is parent
            and removal["data"].get("subject") == subject
            and removal["data"].get("object") == controls[0].get("object")
            and all(item.get("routeOperation") == 1
                and item.get("owner") == parent.get("owner") == self.loaded["rawHex"]
                and all(item.get(key) == parent.get(key) for key in ("state", "field", "slot"))
                and item.get("before", {}).get("subject") == subject for item in (native, ordinary)))

    def _tap(self, address, before, after, label):
        def entered():
            if not self.active or not getattr(self.session, "_throw_interactions_window", False):
                return
            entry = self.observer._clock()
            self._receipt_cycle(entry)
            need(len(self.contexts) < 4 or self._retirement_discovery(address, label),
                 "receipt/depth cap reached")
            if label is not None:
                need(self.count < MAX_RECEIPTS, "receipt/depth cap reached")
                self.count += 1  # Reserve each labelled start, including calls still in flight.
            value = before()
            if value is None:
                return
            receipt_label = label
            if label == LABEL and value.get("routeOperation") == 1:
                receipt_label = ENTRY_CONTROL_LABEL if value["entry"]["nativeControl"] is not None else ENTRY_LABEL
            regs = self.session.emu.memory.register_arm9
            context = dict(entry=entry, setupMode="prepared" if self.session.prepared else "normal",
                           data=value, sp=regs.sp & 0xFFFFFFFF, label=receipt_label, address=address)
            self.contexts.append(context)
            token = None

            def returned():
                if regs.sp & 0xFFFFFFFF != context["sp"]:
                    return
                self.observer.hooks.remove(token)
                self.returns.remove(token)
                self.observer.return_tokens.remove(token)
                self.contexts.remove(context)
                returned_clock = self.observer._clock()
                self._receipt_cycle(returned_clock)
                context.update(returned=returned_clock, returnValue=regs.r0 & 0xFFFFFFFF)
                result = after(value, context)
                if label is not None and result is not None:
                    self.observer._queue(receipt_label, context, result)

            token = self.observer.hooks.add(regs.lr, returned)
            self.returns.append(token)
            self.observer.return_tokens.append(token)

        token = self.observer.hooks.add(address, entered)
        self.tokens.append(token)
        self.observer.tokens.append(token)
        return token

    def close(self):
        self.active = False
        for own, shared in ((self.tokens, self.observer.tokens), (self.returns, self.observer.return_tokens)):
            for token in own:
                self.observer.hooks.remove(token)
                if token in shared:
                    shared.remove(token)
            own.clear()
        self.contexts.clear()

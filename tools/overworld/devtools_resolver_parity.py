"""Pure bounded deployment comparison, never live proof or a behavior oracle.

The caller owns native call/code authentication, current input hashes, clocks,
scratch restoration and host execution against that same blob. Host results
use the unchanged Workshop native_resolver.resolve_many JSON format.
"""
from copy import deepcopy
import hashlib
import struct
from pathlib import Path

RESOLVER_BLOB_VERSION = 95
RESOLVER_SERVICE_VERSION = 3
QUERY_CALLBACK_OFFSET = 68

CASE_NAMES = (
    "default-class-and-lanes",
    "pidgey-small-bird-fly-in",
    "forced-follower-profile",
    "stantler-sprint-one-frame-acceleration",
    "forced-mounted-sprint-profile",
    "conditional-perch-replay",
    "conditional-playful-actor-target",
    "forced-asleep-profile",
    "mankey-canopy-capability-on-canopy",
)
METADATA = ("behaviorClass", "behaviorLimitKey", "speciesClassRuleIndex", "matchedClassRuleMask",
            "matchedOverrideMask", "forcedOverrideMask", "conditionalOverrideMask", "appliedOverrideMask",
            "fingerprint")


def require(value, reason):
    if not value:
        raise ValueError("resolver parity: " + reason)


def integer(value, maximum=0xFFFFFFFF):
    require(type(value) is int and 0 <= value <= maximum, "invalid integer")
    return value


def raw_hex(value, size):
    require(isinstance(value, str) and len(value) == size * 2, "wrong byte extent")
    try:
        raw = bytes.fromhex(value)
    except ValueError as error:
        raise ValueError("resolver parity: invalid hex") from error
    require(len(raw) == size and raw.hex() == value, "noncanonical bytes")
    return raw


def request_bytes(request):
    """Public request layout plus the Workshop adapter's defaults."""
    allowed = {"species", "groupFlags", "level", "terrain", "shiny",
               "forcedOverrideMask", "behaviorClass", "activeConditionalMask",
               "requestVersion", "resolvedTarget", "winningConditionId",
               "targetSourceApplication", "resolvedTargetConditionId"}
    require(isinstance(request, dict) and set(request) <= allowed, "unknown request field")
    behavior_class = request.get("behaviorClass", "auto")
    behavior_class = 255 if behavior_class == "auto" else integer(behavior_class, 255)
    request_version = integer(request.get("requestVersion", 2), 255)
    require(request_version == 2, "unsupported request version")
    target = request.get("resolvedTarget") or {}
    require(isinstance(target, dict), "invalid resolved target")
    target_kind = target.get("kind", "none")
    if isinstance(target_kind, str):
        require(target_kind in ("none", "player", "actor"), "invalid resolved target kind")
        target_kind = {"none": 0, "player": 1, "actor": 2}[target_kind]
    return struct.pack("<HHIBBBBII6HBBHBBBBH2x",
        integer(request.get("species", 0), 65535),
        0, integer(request.get("groupFlags", 0)),
        integer(request.get("level", 1), 255), integer(request.get("terrain", 0), 255),
        integer(request.get("shiny", 0), 255), 0,
        integer(request.get("forcedOverrideMask", 0)),
        integer(request.get("activeConditionalMask", 0)),
        integer(target.get("actorSlot", 0), 65535),
        integer(target.get("actorGeneration", 0), 65535),
        integer(target.get("fieldEpoch", 0), 65535),
        integer(target.get("mapGeneration", 0), 65535),
        integer(target.get("encounterGeneration", 0), 65535),
        integer(target.get("actorReserved", 0), 65535),
        integer(target_kind, 2), 0,
        integer(request.get("winningConditionId", 65535), 65535),
        behavior_class,
        integer(request.get("targetSourceApplication", 255), 255),
        request_version, 0,
        integer(request.get("resolvedTargetConditionId", 65535), 65535))


def host_result_bytes(result):
    require(isinstance(result, dict), "missing host result")
    prefix = raw_hex(result.get("profileHex"), 160) + raw_hex(result.get("primitivesHex"), 8) + struct.pack(
        "<BBHIIIIII", *(integer(result.get(key), 255 if index < 2 else 65535 if index == 2 else 0xFFFFFFFF)
                        for index, key in enumerate(METADATA)))
    target = result.get("resolvedTarget") or {}
    require(isinstance(target, dict), "missing resolved target")
    return prefix + struct.pack(
        "<6HBBHBBH",
        integer(target.get("actorSlot", 0), 65535),
        integer(target.get("actorGeneration", 0), 65535),
        integer(target.get("fieldEpoch", 0), 65535),
        integer(target.get("mapGeneration", 0), 65535),
        integer(target.get("encounterGeneration", 0), 65535),
        integer(target.get("actorReserved", 0), 65535),
        integer(target.get("kind", 0), 2), 0,
        integer(result.get("winningConditionId", 65535), 65535),
        integer(result.get("targetSourceApplication", 255), 255), 0,
        integer(result.get("resolvedTargetConditionId", 65535), 65535))


def checked_trace(result):
    require(type(result.get("traceDropped")) is int and result["traceDropped"] == 0,
            "provenance was dropped")
    trace = result.get("trace")
    require(isinstance(trace, list) and 1 <= len(trace) <= 256, "missing or unbounded provenance")
    for step in trace:
        require(isinstance(step, dict) and set(step) == {"sourceIndex", "lane", "kind", "flags", "profileHex"},
                "provenance fields differ")
        integer(step["sourceIndex"], 65535)
        require(type(step["lane"]) is int and step["lane"] in (0, 2, 255), "invalid provenance lane")
        integer(step["kind"], 6)
        integer(step["flags"], 15)
        raw_hex(step["profileHex"], 80)
    return trace


def packaged_query_identity(repo, rom):
    """Bind the resolver callback to member 21 of this exact ROM and ELF."""
    import ndspy.narc
    import ndspy.rom
    from tools.overworld.pack_query_code_addon import package, BASE, ENTRY, VERSION

    root = Path(repo)
    directory = root / "build/overworld_query_code_addon"
    elf = (directory / "image.elf").read_bytes()
    blob, receipt = package(elf)
    require((directory / "query.bin").read_bytes() == blob,
            "Query package differs from linked ELF")
    image = blob[64:64 + receipt["imageBytes"]]
    member = ndspy.narc.NARC(ndspy.rom.NintendoDSRom.fromFile(str(rom)).getFileByName("a/0/2/8")).files[21]
    require(member == blob and len(image) >= ENTRY,
            "Query ROM member differs from linked package")
    callback = struct.unpack_from("<I", image, QUERY_CALLBACK_OFFSET)[0]
    require(callback & 1 and BASE + ENTRY <= (callback & ~1) <= BASE + len(image) - 32,
            "Query resolver callback differs")
    return dict(queryVersion=VERSION, queryPackageSha256=hashlib.sha256(blob).hexdigest(),
                queryImageSha256=hashlib.sha256(image).hexdigest(),
                queryResolverOffset=(callback & ~1) - BASE,
                queryResolverEntrySha256=hashlib.sha256(
                    image[(callback & ~1) - BASE:(callback & ~1) - BASE + 32]).hexdigest()), blob, receipt


def current_query_owner(session, blob, receipt):
    """Authenticate the loaded, current Field Query image before a probe."""
    from tools.overworld.devtools_field_cleanup import symbol
    from tools.overworld.pack_query_code_addon import BASE

    build = session.rt.REPO / "build"
    selector = build / "overworld_follower_selector_overlay_linked.o"
    data = selector.read_bytes()
    table = symbol(data, "gOverworldQueryCodeAddonServiceEntry", 1, expected_size=24)[0]
    state = symbol(data, "gOverworldQueryCodeAddonState", 1, expected_size=28)[0]
    condition = symbol(data, "gOverworldBehaviorConditionServiceEntry", 1, expected_size=24)[0]
    delegate = symbol(data, "OverworldQueryCodeAddon_ResolverCall", 2)[0] | 1
    from tools.overworld.devtools_runtime import _elf_code
    table_bytes = _elf_code(selector, table, 24)
    condition_bytes = _elf_code(selector, condition, 24)
    require(struct.unpack_from("<IHHI", table_bytes) == (0x53444F57, 2, 24, state)
            and struct.unpack_from("<IHH", condition_bytes) == (0x4342574F, 13, 24)
            and struct.unpack_from("<I", condition_bytes, 16)[0] == delegate
            and session.packaged_code(table, 24) == table_bytes
            and session.packaged_code(condition, 24) == condition_bytes
            and session.packaged_code(delegate & ~1, 32)
                == _elf_code(selector, delegate & ~1, 32),
            "current Query/condition service differs")
    flag = symbol((build / "field_linked.o").read_bytes(),
                  "gOverworldFollowerSelectorStateStorage", 1, expected_size=1)[0]
    require(session.read(flag, 1)[0] & 0x40, "Query Selector is unloaded")
    raw = session.read(state, 28)
    require(len(raw) == 28, "Query owner read is incomplete")
    address, size, entry, field, epoch, generation, member, phase, reserved = \
        struct.unpack("<4I2HIB3s", raw)
    require(phase == 1 and member == 21 and reserved == bytes(3)
            and size == len(blob) and entry == address + 64
            and field == session.field_pointer() and epoch and generation
            and 0x02000000 <= address <= 0x02400000 - size,
            "loaded Query has no current Field owner")
    availability = session._field_actor_availability(field)
    require(availability.get("authenticated") is True and availability.get("reason") is None,
            "loaded Query Field is unavailable")
    actor = session.rt.ACTOR_DESCRIPTOR["state"]["address"]
    owner_epoch = int.from_bytes(session.read(actor + 12, 2), "little")
    owner_generation = int.from_bytes(session.read(actor + 46, 2), "little")
    require((epoch, generation) == (owner_epoch, owner_generation),
            "loaded Query Actor owner differs")
    image = bytearray(blob[64:64 + receipt["imageBytes"]])
    for offset in receipt["localAbs32"]:
        word = struct.unpack_from("<I", image, offset)[0]
        require(BASE <= (word & ~1) < BASE + len(image), "Query relocation differs")
        struct.pack_into("<I", image, offset, word + entry - BASE)
    for offset in range(0, len(image), 0x8000):
        chunk = image[offset:offset + 0x8000]
        require(session.read(entry + offset, len(chunk)) == chunk,
                "loaded Query code differs from packaged ROM")
    return dict(stateAddress=state, rawHex=raw.hex(), entry=entry,
                fieldEpoch=epoch, mapGeneration=generation)


def compare_resolver_parity(vectors, native_receipts, host_results, *, blob_identity, service_identity):
    """Compare exact ordered calls. Missing data raises; equality grants no live credit."""
    require(isinstance(vectors, list) and len(vectors) == len(CASE_NAMES)
            and [v.get("name") for v in vectors if isinstance(v, dict)] == list(CASE_NAMES),
            "the authored cases differ")
    require(isinstance(native_receipts, list) and len(native_receipts) == len(CASE_NAMES)
            and isinstance(host_results, list) and len(host_results) == len(CASE_NAMES),
            "all resolver results are required")
    require(isinstance(blob_identity, dict) and set(blob_identity) == {"size", "sha256"}, "blob identity missing")
    require(integer(blob_identity["size"]) > 0, "empty blob")
    raw_hex(blob_identity["sha256"], 32)
    require(isinstance(service_identity, dict) and set(service_identity) ==
            {"magic", "version", "size", "resolveAddress", "entrySha256",
             "queryVersion", "queryPackageSha256", "queryImageSha256",
             "queryResolverOffset", "queryResolverEntrySha256"}, "service identity missing")
    for key in ("magic", "version", "size", "resolveAddress"):
        require(integer(service_identity[key]) > 0, "empty service identity")
    require(service_identity["version"] == RESOLVER_SERVICE_VERSION
            and service_identity["queryVersion"] == 9
            and integer(service_identity["queryResolverOffset"]) >= 196,
            "unsupported resolver service version")
    for key in ("entrySha256", "queryPackageSha256", "queryImageSha256", "queryResolverEntrySha256"):
        raw_hex(service_identity[key], 32)
    cases = []
    for vector, native, host in zip(vectors, native_receipts, host_results):
        require(isinstance(native, dict) and isinstance(host, dict), "missing result")
        require(native.get("name") == vector["name"], "native case order differs")
        require(native.get("blobIdentity") == blob_identity and native.get("serviceIdentity") == service_identity,
                "native blob or service identity differs")
        for key, expected in (("blobIdentity", blob_identity), ("serviceIdentity", service_identity)):
            require(all(type(native[key][field]) is type(value) for field, value in expected.items()),
                    "native identity field types differ")
        require(isinstance(vector.get("request"), dict), "authored request missing")
        request = request_bytes(vector["request"])
        require(raw_hex(native.get("requestHex"), 44) == request, "native request differs")
        require(type(native.get("status")) is int and type(host.get("status")) is int
                and native["status"] == host["status"] == 0, "native/host status differs or failed")
        result = raw_hex(native.get("resultHex"), 216)
        require(result == host_result_bytes(host), "full result bytes differ")
        require(checked_trace(native) == checked_trace(host), "ordered provenance differs")
        cases.append({"name": vector["name"], "status": 0, "requestHex": request.hex(),
                      "resultSha256": hashlib.sha256(result).hexdigest(), "traceCount": len(native["trace"])})
    return {"passed": True, "acceptedProof": False, "caseCount": len(CASE_NAMES), "cases": cases,
            "blobIdentity": deepcopy(blob_identity), "serviceIdentity": deepcopy(service_identity),
            "scope": "bounded deployment equality only; live authenticity and authored behavior proof are separate"}

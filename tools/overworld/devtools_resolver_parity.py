"""Pure bounded deployment comparison, never live proof or a behavior oracle.

The caller owns native call/code authentication, current input hashes, clocks,
scratch restoration and host execution against that same blob. Host results
use the unchanged Workshop native_resolver.resolve_many JSON format.
"""
from copy import deepcopy
import hashlib
import struct

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
    prefix = raw_hex(result.get("profileHex"), 144) + raw_hex(result.get("primitivesHex"), 8) + struct.pack(
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
        raw_hex(step["profileHex"], 72)
    return trace


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
            {"magic", "version", "size", "resolveAddress", "entrySha256"}, "service identity missing")
    for key in ("magic", "version", "size", "resolveAddress"):
        require(integer(service_identity[key]) > 0, "empty service identity")
    require(service_identity["version"] == 2, "unsupported resolver service version")
    raw_hex(service_identity["entrySha256"], 32)
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
        result = raw_hex(native.get("resultHex"), 200)
        require(result == host_result_bytes(host), "full result bytes differ")
        require(checked_trace(native) == checked_trace(host), "ordered provenance differs")
        cases.append({"name": vector["name"], "status": 0, "requestHex": request.hex(),
                      "resultSha256": hashlib.sha256(result).hexdigest(), "traceCount": len(native["trace"])})
    return {"passed": True, "acceptedProof": False, "caseCount": len(CASE_NAMES), "cases": cases,
            "blobIdentity": deepcopy(blob_identity), "serviceIdentity": deepcopy(service_identity),
            "scope": "bounded deployment equality only; live authenticity and authored behavior proof are separate"}

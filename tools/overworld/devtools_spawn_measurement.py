"""Pure checks for a species-bound, native POOL placement receipt.

No emulator, mutation, file access or proof grant. The shared job must still
prove the live actor, completed landing and observation coverage. In particular,
preserving a pool site is NOT proof of its physical surface or later movement.
"""
from copy import deepcopy
import struct

from tools.overworld.devtools_chain_measurement import LedybaChainMeasurement


def _bytes(value, size, name):
    if not isinstance(value, str) or len(value) != size * 2:
        raise ValueError(name + " has the wrong byte count")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise ValueError(name + " is not hexadecimal") from error


def _encounter(raw):
    pid, species, form, level = struct.unpack_from("<IHBB", raw, 12)
    return {"personality": pid, "species": species, "form": form, "level": level}


def check_pool_spawn_receipt(spawn, *, source_sha256, authored_profiles):
    """Require the actual winning legacy POOL rule to preserve its own site.

    Expected meaning comes from the retained Pool-default authoring contract,
    not the resolver's current mask15 compatibility conversion. Modern explicit
    destinations and headbutt encounters are outside this exact witness.
    Invalid/missing evidence raises ValueError; changed placement returns a
    measured failure with both sites retained.
    """
    pair = spawn.get("finalization", {})
    receipt = pair.get("receipt")
    if pair.get("status") != "matched" or not isinstance(receipt, dict):
        raise ValueError("spawn has no matched native finalization")
    if receipt.get("observation") != "spawn-finalized" or receipt.get("returnValue") != 1 \
            or receipt.get("setupMode") != "normal" or spawn.get("setupMode") != "normal" \
            or spawn.get("returnValue") != 1:
        raise ValueError("placement needs successful normal finalization and spawn")
    for key in ("slot", "terrain", "preparedPointer", "statePointer", "fieldPointer"):
        if type(receipt.get(key)) is not int or receipt[key] != spawn.get(key):
            raise ValueError("finalization/spawn binding differs: " + key)
    if any(not 0x02000000 <= receipt[key] < 0x02400000 or receipt[key] % 4
           for key in ("statePointer", "fieldPointer")):
        raise ValueError("finalization has an invalid native pointer")
    pointer = receipt["preparedPointer"]
    if pointer % 4 or not (0x02000000 <= pointer < pointer + 30 <= 0x02400000
                          or 0x027E0000 <= pointer < pointer + 30 <= 0x027E3FC0):
        raise ValueError("finalization has an invalid native prepared buffer")
    if not 0 <= receipt["slot"] < 6 or receipt["terrain"] not in (0, 1, 3):
        raise ValueError("POOL witness requires an ordinary regular Wild encounter")
    context = receipt.get("worldContext")
    if not isinstance(context, dict) or context != spawn.get("worldContext") \
            or receipt.get("returnWorldContext") != context or receipt.get("pairEligible") is not True \
            or any(context.get(k) != receipt[k] for k in ("statePointer", "fieldPointer")) \
            or any(type(context.get(k)) is not int or context[k] <= 0
                   for k in ("fieldEpoch", "mapGeneration")) \
            or type(context.get("mapId")) is not int or not 0 <= context["mapId"] <= 65535:
        raise ValueError("finalization and spawn world contexts differ")
    if any(type(receipt.get(key)) is not int or type(spawn.get(key)) is not int
           or receipt[key] >= spawn[key] for key in ("sequence",)):
        raise ValueError("finalization did not precede this spawn")
    if type(receipt.get("finalizationId")) is not int or receipt["finalizationId"] < 1:
        raise ValueError("finalization identity is missing")
    for clock in ("ActorFrame", "NativeCycle"):
        clocks = [receipt.get("entry" + clock), receipt.get("return" + clock),
                  spawn.get("entry" + clock), spawn.get("return" + clock)]
        if any(type(value) is not int or value < 0 for value in clocks) or clocks != sorted(clocks):
            raise ValueError("finalizer/spawn clocks are missing or out of order")
    before = _bytes(receipt.get("inputPrefixHex"), 20, "input prepared prefix")
    after = _bytes(receipt.get("preparedPrefixHex"), 30, "final prepared prefix")
    if after != _bytes(spawn.get("preparedPrefixHex"), 30, "spawn prepared prefix"):
        raise ValueError("spawn does not consume the exact finalized encounter")
    incoming, outgoing = _encounter(before), _encounter(after)
    if receipt.get("inputEncounter") != incoming or receipt.get("preparedEncounter") != outgoing \
            or spawn.get("preparedEncounter") != outgoing \
            or any(incoming[k] != outgoing[k] for k in ("species", "form", "level")):
        raise ValueError("finalized encounter identity differs")
    # PID may change in the native shiny/personality finalizer. The actor must
    # match its output, never the earlier candidate's PID.
    subject = spawn.get("publicSubject", {})
    if subject.get("role") != "WILD" \
            or any(subject.get(k) != outgoing[k] for k in ("species", "form", "level")) \
            or subject.get("subjectIdentity") != outgoing["personality"] \
            or subject.get("handle", {}).get("slot") != receipt["slot"] \
            or any(subject.get("handle", {}).get(k) != context[k] for k in ("fieldEpoch", "mapGeneration")):
        raise ValueError("finalized encounter is not this spawned actor")
    profiles = receipt.get("resolverReceipts")
    if not isinstance(profiles, list) or not 1 <= len(profiles) <= 64:
        raise ValueError("finalization has no bounded native resolver provenance")
    if any(p.get("finalizationId") != receipt["finalizationId"] or p.get("inputEncounter") != incoming
           for p in profiles):
        raise ValueError("nested resolver does not belong to this finalization")
    resolved = profiles[-1]
    if resolved.get("resolved") is not True or resolved.get("sourceSha256") != source_sha256:
        raise ValueError("finalizer profile has missing or stale source identity")
    request = _bytes(resolved.get("requestHex"), 44, "resolver request")
    result = _bytes(resolved.get("resultHex"), 200, "resolver result")
    applied = int.from_bytes(result[172:176], "little")
    matched, forced, conditional = struct.unpack_from("<III", result, 160)
    owner = matched | forced
    # Tired references also enter appliedOverrideMask. They are not Owner
    # layers. Conditional layering and canopy-hopper exceptions require a
    # separate witness; this narrow legacy POOL check must not infer them.
    if forced or conditional or owner & ~applied or result[146] == 4 or result[150] == 4:
        raise ValueError("conditional, forced or tree-top placement is outside this POOL witness")
    if resolved.get("appliedOverrides") != applied \
            or resolved.get("fingerprint") != int.from_bytes(result[176:180], "little") \
            or resolved.get("lanes") != [result[n:n + 72].hex() for n in (0, 72)]:
        raise ValueError("native finalizer profile bytes differ")
    if int.from_bytes(request[:2], "little") != incoming["species"] \
            or request[8] != incoming["level"] or request[9] != receipt["terrain"] \
            or int.from_bytes(request[12:16], "little") != 0:
        raise ValueError("finalizer resolved a different or forced subject")
    overrides = authored_profiles.get("overrideProfiles")
    if not isinstance(overrides, list) or len(overrides) > 32 or applied >> len(overrides):
        raise ValueError("applied layers exceed current authored source")
    winner = None
    for index, override in enumerate(overrides):
        if not owner & (1 << index):
            continue
        fields = override["fields"]
        if "spawnDestinationOverrideMask" in fields:
            raise ValueError("modern destination override is outside the legacy POOL witness")
        if "spawnDestination" in fields:
            winner = (index, override["name"], fields["spawnDestination"])
    if winner is None or winner[2] != {"operator": "replace", "value": "OW_WILD_SPAWN_DESTINATION_POOL"} \
            or result[17] != 0:
        raise ValueError("current winning authored destination is not legacy POOL")
    source = list(struct.unpack_from("<ii", before))
    destination = list(struct.unpack_from("<ii", after))
    target = list(struct.unpack_from("<hh", after, 20))
    if any(not 0 <= coordinate <= 32767 for coordinate in source + destination + target):
        raise ValueError("pool position is outside the supported map coordinate range")
    if receipt.get("inputPosition") != source or receipt.get("position") != destination \
            or receipt.get("startup", {}).get("target") != target or after[28] != 4:
        raise ValueError("native position/startup fields disagree or are not an off-screen Hop")
    preserved = source == destination == target
    return {"passed": preserved, "reason": None if preserved else "pool-destination-replaced",
            "finalizationId": receipt["finalizationId"], "finalizationSequence": receipt["sequence"],
            "spawnSequence": spawn["sequence"], "subject": deepcopy(subject),
            "terrain": receipt["terrain"], "sourcePosition": source,
            "destination": destination, "landingTarget": target,
            "authoredLayer": {"index": winner[0], "name": winner[1]},
            "inputPersonality": incoming["personality"], "finalPersonality": outgoing["personality"],
            "scope": "own encounter-pool position preservation only; physical landing and mobility unproved"}


class PoolSpawnMeasurement:
    """One normal Ledyba's POOL receipt plus its complete first spawn Hop.

    Reuses the shared identity, profile, coverage, motion and terminal recorder.
    It does not grant the chain recorder's three-action claim, nor infer terrain
    legality from matching coordinates. No actions or engine state are owned.
    """

    def __init__(self, schema, source_sha256, *, authored_profiles, max_frames):
        self.landing = LedybaChainMeasurement(schema, source_sha256, max_frames=max_frames)
        self.authored_profiles = deepcopy(authored_profiles)
        self.placement = None
        self.finalizer_receipts = {}
        self.failures = []
        self.closed = False

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("measurement is closed")
        if self.failures:
            return self.result()
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "native-observation" and data.get("observation") == "spawn-finalized":
                slot = data.get("slot")
                if type(slot) is int and 0 <= slot < 7:
                    self.finalizer_receipts[slot] = deepcopy(data)
        landed = self.landing.observe(snapshot, events)
        if self.landing.spawn is not None and self.placement is None:
            try:
                receipt = self.landing.spawn.get("finalization", {}).get("receipt")
                if not isinstance(receipt, dict) \
                        or self.finalizer_receipts.get(receipt.get("slot")) != receipt:
                    raise ValueError("spawn lacks its exact observed finalizer receipt")
                self.placement = check_pool_spawn_receipt(self.landing.spawn,
                    source_sha256=self.landing.source_sha256, authored_profiles=self.authored_profiles)
            except (ValueError, TypeError, KeyError) as error:
                self.failures.append({"code": "invalid-pool-receipt", "frame": snapshot["frame"],
                                      "message": str(error)})
        # Retain the actual completed landing before calling a replaced site
        # a measured failure. An input/output mismatch alone cannot prove where
        # the live presentation finished.
        if self.placement is not None and not self.placement["passed"] and landed["spawnPassed"]:
            self.failures.append({"code": "pool-destination-replaced", "frame": snapshot["frame"],
                                  "placement": deepcopy(self.placement)})
        return self.result()

    def result(self):
        observed = self.landing.result()
        failures = deepcopy(self.failures) + observed["failures"]
        ready = self.placement is not None and self.placement["passed"] \
            and observed["spawnPassed"] and observed["stopBoundary"] is not None \
            and not failures and not observed["measurementErrors"]
        return {"state": "failed" if failures or self.closed and not ready else "completed" if self.closed else "observing",
            "passed": self.closed and ready, "ready": ready, "acceptedProof": False,
            "scope": "one normal Wild Ledyba keeps its own POOL site and completes its native spawn Hop; physical surface legality and later mobility unproved",
            "subject": observed["subject"], "frames": observed["frames"],
            "identitySamples": observed["identitySamples"],
            "selectedProfileObservationCount": observed["selectedProfileObservationCount"],
            "placement": deepcopy(self.placement), "spawnPassed": observed["spawnPassed"],
            "spawnGeometry": observed["spawnGeometry"], "stopBoundary": observed["stopBoundary"],
            "completeMotions": observed["completeMotions"],
            "measurementErrors": observed["measurementErrors"], "failures": failures}

    def finish(self):
        if not self.closed and not self.result()["ready"] and not self.result()["failures"]:
            self.failures.append({"code": "incomplete-pool-spawn", "frame": self.landing.last_frame})
        self.closed = True
        return self.result()


class PoolSpawnSurfaceMeasurement(PoolSpawnMeasurement):
    """Separate surface witness layered on the unchanged POOL lifecycle check.

    Only the first checked landing boundary is sampled. The child owns neither
    motion decoding nor game control, and cannot replace missing spawn proof.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.surface = None
        self.surfaceErrors = []
        self._height_event_bound = False

    def observe(self, snapshot, events=()):
        if self.closed:
            raise ValueError("measurement is closed")
        if self.surfaceErrors:
            return self.result()
        super().observe(snapshot, events)
        if self.landing.spawn is not None and not self._height_event_bound:
            try:
                jumps = self.landing.spawn.get("jumpReceipts")
                if not isinstance(jumps, list) or len(jumps) != 1:
                    raise ValueError("spawn lacks one native jump receipt")
                height = jumps[0].get("landingHeight")
                if not isinstance(height, dict) or height.get("status") != "observed":
                    raise ValueError("spawn lacks native landing height")
                queued = [e for e in events if e.get("kind") == "native-observation"
                          and e.get("data", {}).get("observation") == "spawn-landing-height"
                          and e["data"].get("slot") == self.landing.spawn.get("slot")]
                if len(queued) != 1 or queued[0].get("frame") != snapshot.get("frame") \
                        or queued[0]["data"] != height:
                    raise ValueError("spawn lacks its exact same-frame queued height receipt")
                self._height_event_bound = True
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                self.surfaceErrors.append({"code": "missing-spawn-height-event", "frame": snapshot.get("frame"),
                                           "message": str(error)})
        old = PoolSpawnMeasurement.result(self)
        if old["ready"] and self._height_event_bound and not self.surfaceErrors and self.surface is None:
            from tools.overworld.devtools_spawn_surface_measurement import check_pool_spawn_surface
            try:
                self.surface = check_pool_spawn_surface(self.landing.spawn, snapshot,
                    source_sha256=self.landing.source_sha256, authored_profiles=self.authored_profiles,
                    verified_stop_boundary=old["stopBoundary"])
            except ValueError as error:
                self.surfaceErrors.append({"code": "invalid-spawn-surface", "frame": snapshot.get("frame"),
                                           "message": str(error)})
        return self.result()

    def result(self):
        result = PoolSpawnMeasurement.result(self)
        ready = result["ready"] and self.surface is not None and self.surface.get("passed") is True \
            and not self.surfaceErrors
        failures = result["failures"] + deepcopy(self.surfaceErrors)
        return {**result, "ready": ready, "passed": self.closed and ready,
                "scope": "own POOL site, complete spawn Hop, loaded metatile legality, authored surface exclusion and native terminal height; unmodeled geometry and later mobility unproved",
                "state": "failed" if failures or self.closed and not ready
                         else "completed" if self.closed else "observing",
                "surface": deepcopy(self.surface), "surfaceErrors": deepcopy(self.surfaceErrors),
                "failures": failures}

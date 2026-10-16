#!/usr/bin/env python3
"""Read saved T74 exports; report native spawn timing, never grant proof.

No game calls, writes, profile overrides, or new observations. The only birth
is a successful native constructor with its own field-object creation and
full subject handle. READY/TRUE queue replies remain pending.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import json
import re
from pathlib import Path
import struct


WORLD = ("fieldPointer", "statePointer", "mapId", "fieldEpoch", "mapGeneration")
HANDLE = ("value", "slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")
DELAYS = {0, 15, 60, 120, 180, 240, 300, 360}
PENDING = {0xFB, 0xFC, 0xFD, 0xFE, 0xFF}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value):
    return type(value) is int


def world_key(data):
    world = data.get("worldContext", {})
    need(all(integer(world.get(k)) for k in WORLD), "native world identity is missing")
    need(world["fieldEpoch"] > 0 and world["mapGeneration"] > 0,
         "native world generation is missing")
    for key in ("fieldPointer", "statePointer"):
        need(data.get(key) == world[key], "native " + key + " differs from its world")
    return tuple(world[k] for k in WORLD)


def reference(event):
    data = event["data"]
    return {"frame": event["frame"], "sequence": data["sequence"],
            **{k: data[k] for k in ("entryActorFrame", "returnActorFrame",
                                    "entryNativeCycle", "returnNativeCycle")}}


def quality(record):
    snapshots, events = record.get("snapshots"), record.get("events")
    counts = record.get("counts", {})
    need(isinstance(snapshots, list) and 0 < len(snapshots) <= 10000
         and isinstance(events, list) and len(events) <= 50000, "record size is missing or unbounded")
    need(record.get("truncated") is False, "record was truncated")
    for key in ("snapshotsDropped", "eventsDropped", "failuresDropped"):
        need(counts.get(key) == 0, "recorder dropped data: " + key)
    need(counts.get("snapshotsRetained") == len(snapshots)
         and counts.get("eventsRetained") == len(events), "retained counts differ")
    need(counts.get("failuresReceived") == 0 and not record.get("definiteFailures"),
         "record contains a definite failure")
    frames = [s.get("frame") for s in snapshots]
    need(all(integer(f) for f in frames)
         and all(b == a + 1 for a, b in zip(frames, frames[1:])), "completed snapshots have a gap or duplicate")
    for snapshot in snapshots:
        coverage = snapshot.get("nativeObservation", {})
        need(snapshot.get("observationBoundary") == "main-task-queue-completion"
             and coverage.get("coverageComplete") is True
             and coverage.get("installedBeforeBoot") is True
             and coverage.get("eventsDropped") == 0 and coverage.get("profilesEvicted") == 0
             and coverage.get("pendingUnframedEvents") == 0 and coverage.get("error") is None,
             "native completed-boundary coverage is incomplete")
    native = [e for e in events if e.get("kind") == "native-observation"]
    sequences = [e.get("data", {}).get("sequence") for e in native]
    need(all(integer(n) and n > 0 for n in sequences)
         and all(b == a + 1 for a, b in zip(sequences, sequences[1:])),
         "native receipt sequence has a gap or duplicate")
    for event in native:
        data = event["data"]
        need(integer(event.get("frame")), "native receipt frame is missing")
        for suffix in ("ActorFrame", "NativeCycle"):
            begin, end = data.get("entry" + suffix), data.get("return" + suffix)
            need(integer(begin) and integer(end) and 0 <= begin <= end,
                 "native receipt clock interval is invalid")
    return {"firstFrame": frames[0], "lastFrame": frames[-1],
            "snapshots": len(snapshots), "nativeReceipts": len(native),
            "firstNativeSequence": sequences[0] if sequences else None,
            "lastNativeSequence": sequences[-1] if sequences else None,
            "snapshotsDropped": 0, "eventsDropped": 0, "truncated": False,
            "nativeCoverageComplete": True}, native


def loader_identity(data):
    raw = bytes.fromhex(data.get("imageIdentity", {}).get("loaderOwner", ""))
    need(len(raw) == 28, "control receipt loader identity is missing")
    blob, size, entry, field, epoch, generation, member, phase, reserved = struct.unpack("<4I2HIB3s", raw)
    need(blob and size and entry == blob + 64 and field and epoch and generation
         and member == 21 and phase == 1 and reserved == bytes(3), "control receipt loader is not current")
    return field, epoch, generation


def inside(child, parent):
    return all(parent["entry" + k] <= child["entry" + k]
               <= child["return" + k] <= parent["return" + k]
               for k in ("ActorFrame", "NativeCycle"))


def creation_delay_anchor(snapshot, event, events):
    """Bind one Commit SUCCESS to its real same-call object constructor.

    A READY queue reply is deliberately outside this seam. The full native
    finalizer is the existing paired receipt, which can precede this update.
    The control, constructor and actual object-create must nest in this call.
    """
    from tools.overworld.devtools_records import select_current_actor
    data, entry = event.get("data", {}), event.get("data", {}).get("entry", {})
    if event.get("kind") != "native-observation" or data.get("observation") != "entry-native-control" \
            or entry.get("operation") != 7 or entry.get("outcome") != 3:
        return None
    need(data.get("boundary") == "native-entry-control-tick-return" and data.get("returnValue") == 1
         and entry.get("kind") == "native-control" and integer(entry.get("value"))
         and entry["value"] & 255 == 3 and entry["value"] >> 24 == 0
         and entry.get("refillDelay") == (entry["value"] >> 8) & 65535
         and entry["refillDelay"] in DELAYS and entry["refillDelay"] >= 60,
         "creation refill anchor lacks its density delay")
    admission = data.get("admission", {})
    field, epoch, generation = loader_identity(data)
    need(event.get("frame") == snapshot["frame"] and (field, epoch, generation) == (
        snapshot["fieldControl"]["fieldPointer"], snapshot["context"]["fieldEpoch"],
        snapshot["context"]["mapGeneration"]), "creation refill anchor has a stale Field owner")
    constructors = [e for e in events if e.get("kind") == "native-observation"
        and e.get("data", {}).get("observation") == "spawn-prepared"
        and e["data"].get("sequence") == admission.get("constructorSequence")]
    need(len(constructors) == 1, "creation refill anchor lacks its exact constructor")
    constructor = constructors[0]
    spawn = constructor["data"]
    world = world_key(spawn)
    subject = spawn.get("publicSubject", {})
    selected = select_current_actor(snapshot, subject)
    pair = spawn.get("finalization", {})
    finalizer = pair.get("receipt", {})
    need(spawn.get("returnValue") == 1 and subject.get("status") == "observed-public-subject"
         and subject.get("role") == "WILD" and admission.get("actor") == selected["handle"]
         and integer(admission.get("serial")) and admission["serial"] > 0
         and admission["serial"] == finalizer.get("querySerial", finalizer.get("nativeEntry", {}).get("querySerial"))
         and pair.get("status") == "matched" and finalizer.get("returnValue") == 1
         and world_key(finalizer) == world and world[-2:] == (epoch, generation)
         and spawn.get("slot") == selected["handle"]["slot"] == finalizer.get("slot")
         and spawn.get("terrain") == finalizer.get("terrain")
         and spawn.get("preparedPointer") == finalizer.get("preparedPointer")
         and spawn.get("preparedPrefixHex") == finalizer.get("preparedPrefixHex")
         and finalizer.get("spawnAttemptId") is not None
         and finalizer["sequence"] < spawn["sequence"] < data["sequence"]
         and constructor["frame"] == event["frame"] and inside(spawn, data),
         "creation refill anchor differs from its full owned finalizer")
    actor = next(a for a in snapshot["actors"] if a.get("handle") == selected["handle"])
    source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
    creates = [e for e in events if e.get("kind") == "native-observation"
        and e.get("data", {}).get("observation") == "spawn-object-create"
        and e["frame"] == event["frame"] and e["data"].get("slot") == spawn["slot"]
        and finalizer["sequence"] < e["data"].get("sequence", 0) < spawn["sequence"]]
    need(len(creates) == 1 and creates[0]["data"].get("returnValue") == source.get("object")
         and source.get("active") == 1 and source.get("map_id") == world[2]
         and engine.get("pointer") == source.get("object") and engine.get("active") is True
         and engine.get("in_manager") is True and engine.get("script_id") == 2074
         and engine.get("object_manager") == engine.get("current_manager")
         and engine.get("object_map_id") == engine.get("current_map_id") == world[2],
         "creation refill anchor lacks one real current engine object")
    return dict(spawnAttemptId=finalizer["spawnAttemptId"], returnActorFrame=data["returnActorFrame"],
        sequence=data["sequence"], worldContext=deepcopy(spawn["worldContext"]),
        handle=deepcopy(selected["handle"]), querySerial=admission["serial"],
        constructorSequence=spawn["sequence"], refillDelay=entry["refillDelay"])


def parse_record(record):
    coverage, native = quality(record)
    attempts, finalizers, constructors, controls = {}, {}, [], []
    manual = []
    for event in native:
        data = event["data"]
        name, attempt_id = data.get("observation"), data.get("spawnAttemptId")
        if name in ("spawn-finalized", "spawn-queued") and integer(attempt_id):
            world = world_key(data)
            key = (*world, attempt_id)
            row = attempts.setdefault(key, {"world": dict(zip(WORLD, world)), "spawnAttemptId": attempt_id,
                "querySerial": None, "slot": data["slot"], "terrain": data["terrain"],
                "species": None, "events": [], "leafs": [], "queues": [], "creations": [], "controls": []})
            need((row["slot"], row["terrain"]) == (data["slot"], data["terrain"]),
                 "natural attempt changed slot or terrain")
            serial = data.get("querySerial", data.get("nativeEntry", {}).get("querySerial"))
            if serial is not None:
                need(integer(serial) and serial > 0
                     and row["querySerial"] in (None, serial), "natural attempt changed queue serial")
                row["querySerial"] = serial
            encounter = data.get("inputEncounter", data.get("nativeEntry", {}).get("inputEncounter", {}))
            if encounter:
                species = encounter.get("species")
                need(integer(species) and species > 0 and row["species"] in (None, species),
                     "natural attempt changed encounter species")
                row["species"] = species
            row["events"].append(event)
            row["leafs" if name == "spawn-finalized" else "queues"].append(event)
            if name == "spawn-finalized":
                fid = data.get("finalizationId")
                need(integer(fid) and fid > 0 and fid not in finalizers, "native finalizer ID was reused")
                finalizers[fid] = (key, event)
        elif name == "spawn-prepared" and data.get("returnValue") == 1:
            constructors.append(event)
        elif name == "entry-native-control":
            entry = data.get("entry") or {}
            if entry.get("operation") not in (7, 8, 9):
                continue
            need(data.get("boundary") == "native-entry-control-tick-return"
                 and entry.get("kind") == "native-control" and data.get("returnValue") == 1,
                 "refill control return boundary differs")
            controls.append(event)

    for event in constructors:
        data = event["data"]
        pair = data.get("finalization", {})
        receipt = pair.get("receipt", {})
        subject = data.get("publicSubject", {})
        handle = subject.get("handle", {})
        world = world_key(data)
        need(subject.get("status") == "observed-public-subject" and subject.get("role") == "WILD"
             and all(integer(handle.get(k)) for k in HANDLE) and handle["slot"] == data["slot"]
             and handle["generation"] > 0 and handle["encounterGeneration"] > 0
             and (handle["fieldEpoch"], handle["mapGeneration"]) == world[-2:],
             "constructor lacks a full current Wild handle")
        encounter = data.get("preparedEncounter", {})
        need(all(subject.get("subjectIdentity" if k == "personality" else k) == encounter.get(k)
                 for k in ("species", "form", "level", "personality")), "constructor encounter differs from subject")
        fid = receipt.get("finalizationId")
        natural = fid in finalizers
        if not natural:
            manual.append({**reference(event), "species": subject["species"], "handle": deepcopy(handle),
                           "classification": "manual-or-unattributed; excluded from natural timing"})
            continue
        key, leaf = finalizers[fid]
        row = attempts[key]
        need(pair.get("status") == "matched" and receipt == leaf["data"]
             and receipt.get("returnValue") == 1 and tuple(row["world"][k] for k in WORLD) == world
             and data["slot"] == row["slot"] and data["terrain"] == row["terrain"]
             and data.get("preparedPointer") == receipt.get("preparedPointer")
             and data.get("preparedPrefixHex") == receipt.get("preparedPrefixHex")
             and leaf["data"]["sequence"] < data["sequence"], "constructor does not consume its exact natural finalizer")
        pointers = {j.get("sourceIdentity", {}).get("object") for j in data.get("jumpReceipts", [])}
        for jump in data.get("jumpReceipts", []):
            need(jump.get("publicSubject", {}).get("handle") == handle
                 and all(jump.get("sourceIdentity", {}).get(k) == encounter[k]
                         for k in ("species", "form", "level", "personality")),
                 "constructor and native motion have different full handles")
        all_bound = [(s, a) for s in record["snapshots"] for a in s.get("actors", []) if a.get("handle") == handle]
        detached = [e for e in record["events"] if e.get("kind") == "native"
                    and e.get("data", {}).get("event") == "ACTOR_DETACHED"
                    and {"value": e["data"].get("actorHandle"), **e["data"].get("actor", {})} == handle]
        need(len(detached) <= 1, "created handle has repeated detach receipts")
        bound, retired_samples = [], []
        for snapshot, actor in all_bound:
            source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
            # Native source retirement can precede its public detach by one
            # completed boundary. It is not another birth pointer. Require
            # the exact full-handle detach and an empty native body; never
            # discard a changed or invalid still-live object.
            retired = (source.get("active") == 0 and source.get("object") == 0
                       and engine.get("pointer") == 0 and actor.get("identityVerified") is False
                       and len(detached) == 1 and snapshot["frame"] >= detached[0]["frame"] - 1
                       and detached[0]["frame"] > event["frame"])
            if retired:
                retired_samples.append(snapshot["frame"])
            else:
                bound.append(actor)
        need(bool(bound), "natural birth lacks a valid current binding")
        pointers.update(a.get("sourceIdentity", {}).get("object") for a in bound)
        pointers.discard(None)
        creates = [e for e in native if e["data"].get("observation") == "spawn-object-create"
                   and e["data"].get("slot") == row["slot"] and e["frame"] == event["frame"]
                   and leaf["data"]["sequence"] < e["data"]["sequence"] < data["sequence"]]
        need(len(creates) == 1 and len(pointers) == 1 and creates[0]["data"]["returnValue"] in pointers,
             "natural constructor has no unique actual native object creation")
        for actor in bound:
            source, engine = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {})
            need(actor.get("active") is True and actor.get("identityVerified") is True
                 and actor.get("species") == subject["species"] and actor.get("role") == "WILD"
                 and actor.get("subjectIdentity") == subject["subjectIdentity"]
                 and source.get("object") in pointers and source.get("active") == 1
                 and source.get("personality") == subject["subjectIdentity"]
                 and source.get("map_id") == world[2]
                 and engine.get("pointer") in pointers and engine.get("active") is True
                 and engine.get("in_manager") is True and engine.get("script_id") == 2074
                 and engine.get("object_manager") == engine.get("current_manager")
                 and engine.get("object_map_id") == engine.get("current_map_id") == world[2],
                 "created handle lost its full current object identity")
        need(not row["creations"], "one natural attempt created more than one actor")
        row["creations"].append({**reference(event), "constructor": "spawn-prepared", "returnValue": 1,
            "objectCreation": reference(creates[0]), "object": next(iter(pointers)),
            "handle": deepcopy(handle), "species": subject["species"],
            "currentIdentitySamples": len(bound), "laterRetiredSourceFrames": retired_samples,
            "laterDetachFrame": detached[0]["frame"] if detached else None,
            "insideSnapshotWindow": coverage["firstFrame"] <= event["frame"] <= coverage["lastFrame"]})

    unbound_controls = []
    for event in controls:
        data, entry = event["data"], event["data"]["entry"]
        op, value = entry["operation"], entry.get("value")
        need(integer(value) and 0 <= value <= 0xFFFFFFFF, "control value is missing")
        expected_delay = value if op == 9 else (value >> 8) & 0xFFFF
        delay = entry.get("refillDelay")
        # Direct op8 is not the ordinary refill selector and grants no timer.
        if op == 8 and entry.get("queryOperation") != 1:
            continue
        need(delay == expected_delay and delay in DELAYS, "decoded native delay differs from raw value")
        if op == 7:
            need(entry.get("outcome") == value & 255 and value >> 24 == 0
                 and value & 255 in (0, 1, 2, 3)
                 and (value & 255 in (2, 3) or delay == 0), "Commit outcome/delay is invalid")
        if op == 8:
            need(entry.get("prepareResult") == value & 255 and value >> 24 == 0
                 and value & 255 in (0, 1, 2)
                 and (value & 255 == 0 or delay == 0), "READY/PENDING reply published a delay")
        field, epoch, generation = loader_identity(data)
        runtime = data.get("before", {}).get("runtime")
        candidates = [row for row in attempts.values() if (row["world"]["fieldPointer"], row["world"]["fieldEpoch"], row["world"]["mapGeneration"]) == (field, epoch, generation)
                      and any(e["data"].get("operation") == op and inside(e["data"], data)
                              and e["data"]["sequence"] < data["sequence"]
                              and e["data"].get("queueAfter", {}).get("runtime") == runtime for e in row["leafs"])]
        if op == 7 and entry["outcome"] == 3 and not candidates:
            # A prepared queue need not run a finalizer again on its constructor
            # frame. The native admission binds that exact queue/Actor instead.
            admission = data.get("admission")
            need(isinstance(admission, dict), "Commit SUCCESS lacks native admission")
            for row in attempts.values():
                if (row["world"]["fieldPointer"], row["world"]["fieldEpoch"],
                        row["world"]["mapGeneration"]) != (field, epoch, generation):
                    continue
                if len(row["creations"]) != 1:
                    continue
                creation = row["creations"][0]
                constructor = next(e for e in constructors if e["data"]["sequence"] == creation["sequence"])
                if (admission.get("slot") == row["slot"]
                    and admission.get("serial") == row["querySerial"]
                    and admission.get("actor") == creation["handle"]
                    and admission.get("constructorSequence") == creation["sequence"]
                    and creation["frame"] == event["frame"]
                    and creation["sequence"] < data["sequence"]
                    and inside(constructor["data"], data)
                    and runtime == data.get("after", {}).get("runtime")
                    and any(e["data"].get("queueAfter", {}).get("runtime") == runtime for e in row["leafs"])):
                    candidates.append(row)
            need(len(candidates) == 1, "Commit SUCCESS has no exact admitted constructor/world/queue")
        if op == 9:
            # No invented serial: retain this standalone series receipt only.
            candidates = []
        need(len(candidates) <= 1, "control interval has more than one natural queue owner")
        raw = {**reference(event), "observation": "entry-native-control", "fieldPointer": field,
               "fieldEpoch": epoch, "mapGeneration": generation, "operation": op,
               "value": value, "refillDelay": delay, "rawField": "events[].data.entry.refillDelay",
               **{k: entry[k] for k in ("queryOperation", "prepareResult", "outcome") if k in entry}}
        if candidates:
            row = candidates[0]
            admission = data.get("admission")
            if op == 7 and entry["outcome"] == 3:
                need(len(row["creations"]) == 1 and isinstance(admission, dict)
                     and admission.get("serial") == row["querySerial"]
                     and admission.get("actor") == row["creations"][0]["handle"]
                     and admission.get("constructorSequence") == row["creations"][0]["sequence"],
                     "Commit SUCCESS has no same owned constructor/full-handle admission")
            row["controls"].append(raw)
        else:
            raw["attribution"] = "no exact nested natural finalizer; standalone refill receipt only"
            unbound_controls.append(raw)

    reports = []
    for row in attempts.values():
        events, leafs, queues = row.pop("events"), row.pop("leafs"), row.pop("queues")
        first, last = min(events, key=lambda e:e["data"]["sequence"]), max(events, key=lambda e:e["data"]["sequence"])
        terminal = None
        outcome = "pending"
        if row["creations"]:
            outcome = "created"
            terminal = row["creations"][0]
        else:
            failed_controls = [c for c in row["controls"] if c["operation"] == 7 and c.get("outcome") == 2]
            if failed_controls:
                outcome, terminal = "rejected", failed_controls[-1]
            elif leafs and leafs[-1]["data"]["returnValue"] == 0 and (
                    leafs[-1]["data"].get("queueAfter", {}).get("stage") == 0
                    or queues and queues[-1]["data"].get("queued") is False):
                outcome, terminal = "rejected", reference(leafs[-1])
            elif leafs and leafs[-1]["data"]["returnValue"] == 1:
                outcome = "pending-ready; constructor not observed"
        reports.append({**row, "start": reference(first), "lastObserved": reference(last),
            "startProven": bool(queues) or bool(leafs and leafs[0]["data"].get("queryQueueStage") in (0, 1)),
            "terrainName": {0:"LAND", 1:"SURF", 2:"HEADBUTT", 3:"FISHING"}.get(row["terrain"], "unknown"),
            "outcome": outcome, "terminal": terminal,
            "insideSnapshotWindow": coverage["firstFrame"] <= first["frame"] <= coverage["lastFrame"],
            "finalizerCalls": len(leafs), "queuedReplies": [
                {**reference(e), **{k:e["data"].get(k) for k in ("returnValue", "queued", "pendingDestination", "pendingEntry")}}
                for e in queues],
            "stages": [{**reference(e), "before": e["data"].get("queryQueueStage"),
                        "after": e["data"].get("queueAfter", {}).get("stage"),
                        "returnValue": e["data"]["returnValue"]} for e in leafs]})
    reports.sort(key=lambda r:r["start"]["sequence"])
    for index, row in enumerate(reports):
        later = next((r for r in reports[index+1:] if r["world"] == row["world"]), None)
        row["nextStartFrame"] = later["start"]["frame"] if later else None
        row["startToNextStartFrames"] = row["nextStartFrame"] - row["start"]["frame"] if later else None
        row["terminalToNextAttemptFrames"] = row["nextStartFrame"] - row["terminal"]["frame"] if later and row["terminal"] else None
    return {"diagnosticOnly": True, "acceptedProof": False, "quality": coverage,
            "sessionId": record.get("identity", {}).get("sessionId"),
            "romSha256": record.get("identity", {}).get("rom", {}).get("sha256"),
            "sourceSaveSha256": record.get("identity", {}).get("save", {}).get("sha256"),
            "mode": record.get("mode"), "naturalAttempts": reports,
            "naturalOutcomes": dict(Counter(r["outcome"] for r in reports)),
            "manualOrUnattributedCreationsExcluded": manual,
            "standaloneRefillControls": unbound_controls,
            "limits": ["Saved native receipts only; not registered acceptance or pacing proof.",
                       "Boot-history events outside the snapshot window are labeled; they earn no completed-frame coverage.",
                       "READY is not creation. A missing terminal stays pending.",
                       "No inner rejection reason or timer consumption is inferred from a delay value.",
                       "Next-attempt gaps are not necessarily next-series gaps; terrain alternatives remain separate."]}


def expand_event_details(record, recording_path):
    """Restore only authenticated saved native receipts; keep quality checks exact."""
    source = Path(recording_path).resolve()
    need(source.parent.name == record.get("identity", {}).get("sessionId"),
         "recording artifact session differs")
    expanded, audit = [], []
    for original in record.get("events", []):
        data = original.get("data", {})
        if original.get("kind") != "native-observation" or not data.get("detailsOmitted"):
            expanded.append(original)
            continue
        need(original.get("kind") == "native-observation" and data.get("detailsOmitted") is True,
             "saved detail is not a native receipt")
        artifact = data.get("artifact", {})
        raw_path, digest = artifact.get("path"), artifact.get("sha256")
        need(isinstance(raw_path, str) and isinstance(digest, str)
             and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
             "saved event detail identity is missing")
        detail = Path(raw_path)
        need(detail.is_absolute() and detail.resolve().parent == source.parent
             and re.fullmatch(r"event-details-[0-9a-f]{12}\.json", detail.name) is not None
             and artifact.get("url") == f"/api/v2/devtools/artifacts/{source.parent.name}/{detail.name}",
             "saved event detail path/kind differs")
        need(detail.is_file() and 0 < detail.stat().st_size <= 1024 * 1024
             and len(audit) < 64, "saved event detail is missing or exceeds limit")
        content = detail.read_bytes()
        need(0 < len(content) <= 1024 * 1024
             and hashlib.sha256(content).hexdigest() == digest, "saved event detail hash differs")
        full = json.loads(content)
        need(isinstance(full, dict) and not full.get("detailsOmitted")
             and isinstance(full.get("observation"), str) and 0 < len(full["observation"]) <= 128
             and integer(full.get("sequence")) and full["sequence"] > 0
             and all(integer(full.get(k)) for k in
                     ("entryActorFrame", "returnActorFrame", "entryNativeCycle", "returnNativeCycle")),
             "saved event detail is not a full native receipt")
        expanded.append({**original, "data": full})
        audit.append(dict(path=str(detail), sha256=digest, bytes=len(content),
                          frame=original.get("frame"), sequence=full["sequence"]))
    return {**record, "events": expanded, "eventArtifactExpansions": audit}

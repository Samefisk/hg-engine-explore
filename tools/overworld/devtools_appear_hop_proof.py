"""Accepted rows and copied-data controls for Appear Hop timing."""
from copy import deepcopy

from tools.overworld.devtools_appear_hop_measurement import (
    IDLE_COMMAND, JUMP_COMMANDS, KIND, REQUIREMENT, RESTORE_COMMAND, require,
)
from tools.overworld.devtools_records import engine_binding_identity, select_current_actor


CLAIMS = (
    "live-actor-identity", "profile-resolution", "rendered-motion",
    "frame-pacing", "control-release",
)
FAULTS = (
    "appear-hop-absent-subject",
    "appear-hop-stale-subject",
    "appear-hop-flat-arc",
    "appear-hop-command-order",
    "appear-hop-late-control",
)


def contract():
    return {
        "live-actor-identity": [{
            "name": "appear-hop-clefairy-identity", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, "WILD", 35, 1, 1, 0],
        }],
        "profile-resolution": [{
            "name": "appear-hop-startup-profile", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [35, 7, 1],
        }],
        "rendered-motion": [{
            "name": "appear-hop-rendered-arc", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [1, 0],
        }],
        "frame-pacing": [{
            "name": "appear-hop-command-order-and-tail", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [49, 62, 74, 255, 0],
        }],
        "control-release": [{
            "name": "appear-hop-terminal-control", "operator": "eq",
            "type": "array", "validator": "meaningful-observation",
            "expected": [0, 255],
        }],
    }


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    require(replay.get("passed") is True and replay.get("failures") == []
            and meter.get("passed") is True and meter.get("ready") is True
            and meter.get("closed") is True and meter.get("acceptedProof") is False
            and meter.get("failures") == [] and meter.get("requirements") == [REQUIREMENT],
            "Appear Hop lacks a closed independent replay")
    require(record.get("sessionCleanup") == {
                "sessionId": record.get("sessionId"), "closed": True, "errors": []},
            "Appear Hop private session did not close cleanly")
    setup = replay.get("spawnSetup") or {}
    native = setup.get("nativeSpawn", {}).get("data", {})
    startup = native.get("startup", {})
    prepared = native.get("preparedEncounter", {})
    require(prepared.get("species") == 35 and startup.get("locomotion") == 7
            and native.get("returnValue") == 1
            and native.get("finalization", {}).get("status") == "matched",
            "Appear Hop lacks its exact native Clefairy startup receipt")
    initial, terminal, subject = meter["initial"], meter["terminal"], meter["subject"]
    first = next(actor for actor in initial["actors"]
                 if actor["handle"] == subject["handle"])
    selected = select_current_actor(terminal, subject)
    last = next(actor for actor in terminal["actors"]
                if actor["handle"] == selected["handle"])
    require(first["species"] == last["species"] == 35
            and first["role"] == last["role"] == "WILD"
            and last.get("identityVerified") is True
            and last.get("presentationAttached") is True
            and last.get("inputOwnership") == 0
            and first.get("sourceIdentity") == last.get("sourceIdentity")
            and engine_binding_identity(first.get("engineIdentity"))
                == engine_binding_identity(last.get("engineIdentity")),
            "Appear Hop terminal Clefairy identity differs")
    samples = meter["samples"]
    require(samples and any(sample["faceY"] > 0 for sample in samples)
            and samples[-1]["faceY"] == 0,
            "Appear Hop rendered arc is incomplete")
    commands = []
    for sample in samples:
        if not commands or commands[-1] != sample["command"]:
            commands.append(sample["command"])
    require(len(commands) == 4 and commands[0] in JUMP_COMMANDS
            and commands[1:] == [62, RESTORE_COMMAND, IDLE_COMMAND],
            "Appear Hop command sequence differs")
    tail = samples[-1]["frame"] - meter["restoreFrame"] - 1
    require(tail == 0 and samples[-1]["controllerState"] == 0
            and samples[-1]["command"] == IDLE_COMMAND,
            "Appear Hop retained a post-restore control tail")
    values = {
        "appear-hop-clefairy-identity": [
            1, last["role"], last["species"], int(last["identityVerified"]),
            int(last["presentationAttached"]), last["inputOwnership"],
        ],
        "appear-hop-startup-profile": [35, startup["locomotion"],
                                        int(native["finalization"]["status"] == "matched")],
        "appear-hop-rendered-arc": [int(any(sample["faceY"] > 0 for sample in samples)),
                                    samples[-1]["faceY"]],
        "appear-hop-command-order-and-tail": [*commands, tail],
        "appear-hop-terminal-control": [samples[-1]["controllerState"],
                                         samples[-1]["command"]],
    }
    rows = []
    for claim, specs in contract().items():
        for spec in specs:
            rows.append({
                "claim": claim, "name": spec["name"],
                "value": deepcopy(values[spec["name"]]),
                "operator": spec["operator"],
                "expected": deepcopy(spec["expected"]), "passed": True,
            })
    return rows


class AppearHopNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown Appear Hop copied-data fault")
        self.fault = fault
        self.mutated = False

    @property
    def applied(self):
        return self.mutated

    def mutate(self, row, subjects):
        if self.mutated and self.fault != "appear-hop-flat-arc":
            return row
        changed = deepcopy(row)
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        for snapshot in changed.get("samples", []):
            actor = next((item for item in snapshot.get("actors", [])
                          if item.get("handle", {}).get("value") in handles), None)
            if actor is None:
                continue
            if self.fault == "appear-hop-absent-subject":
                snapshot["actors"].remove(actor)
            elif self.fault == "appear-hop-stale-subject":
                actor["authorityGeneration"] += 1
            elif self.fault == "appear-hop-flat-arc":
                actor["engineObject"]["face_y"] = 0
            elif self.fault == "appear-hop-command-order" \
                    and actor["engineObject"]["movement_cmd"] == 62:
                actor["engineObject"]["movement_cmd"] = IDLE_COMMAND
            elif self.fault == "appear-hop-late-control" \
                    and actor["engineObject"]["movement_cmd"] == IDLE_COMMAND \
                    and actor.get("controllerState") == 0:
                actor["controllerState"] = 1
            else:
                continue
            self.mutated = True
            if self.fault != "appear-hop-flat-arc":
                return changed
        return changed if self.mutated else row

    def result(self, replay):
        require(self.mutated, "Appear Hop negative control never reached its subject")
        return {
            "fault": self.fault, "mutated": True,
            "rejected": replay.get("passed") is False and bool(replay.get("failures")),
            "acceptedProof": False,
        }


def validate_negative_result(value, fault=None):
    return isinstance(value, dict) and value.get("fault") in FAULTS \
        and (fault is None or value.get("fault") == fault) \
        and value.get("mutated") is True and value.get("rejected") is True \
        and value.get("acceptedProof") is False

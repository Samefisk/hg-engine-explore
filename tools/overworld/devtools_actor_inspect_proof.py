"""Controlled native lookup proof. Package oracle and cleanup belong to controller."""
from copy import deepcopy
from tools.overworld.devtools_actor_inspect_measurement import ActorInspectMeasurement, checked_receipt, require, actor_bytes

NAMES = ("packaged-inspect-entry", "bound-subject-identity", "current-actor-byte-parity",
         "stale-generation-rejection", "owned-buffer-cleanup", "native-call-boundaries")
RULES = tuple(("controlled-action", name, "eq", 1) for name in NAMES)


def actor_inspect_measurements(test, rows, record, repo, *, oracle):
    saved = []
    for row in rows:
        require(len(saved) < 3, "exact initial/bind/probe rows required")
        saved.append(row)
    require(len(saved) == 3, "exact initial/bind/probe rows required")
    meter = ActorInspectMeasurement(test)
    for row in saved:
        meter.observe_record(row)
    result = meter.finish()
    require(result["passed"], result["failures"][0]["detail"] if result["failures"] else "incomplete probe")
    try:
        counts = checked_receipt(saved[-1], saved[1]["receipt"], oracle=oracle)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("actor inspect: malformed proof") from error
    value = saved[-1]["receipt"]["value"]
    return dict(measurements=[dict(claim="controlled-action", name=name, value=1,
                operator="eq", expected=1) for name in NAMES],
                caseProof=dict(currentHandle=True, staleGenerationRejected=True,
                    acceptedProof=False, subject=deepcopy(saved[1]["receipt"]),
                    cases=deepcopy(value["receipts"]), scope="native lookup only; no motion credit"), **counts)


def negative_controls(test, rows, record, repo, *, oracle):
    saved = list(rows)
    actor_inspect_measurements(test, saved, record, repo, oracle=oracle)
    controls = {}
    reasons = dict(zip(("wrong-subject", "wrong-current-byte", "wrong-stale-generation", "missing-free", "wrong-service", "wrong-entry-argument", "changed-state"),
        ("bound subject differs", "native Inspect result differs", "query differs", "native call list differs", "packaged entry differs", "native arguments differ", "state changed")))
    generation_controls = {"changed-authority-generation": "authorityGeneration",
        "changed-engine-anchor-generation": "engineAnchorGeneration",
        "changed-presentation-generation": "presentationGeneration"}
    reasons.update({name: "bound generations differ" for name in generation_controls})
    reasons.update({"changed-engine-owner": "bound engine owner differs", "wrong-native-role": "native follower role differs"})
    for name in reasons:
        changed = deepcopy(saved)
        receipt = changed[-1]["receipt"]
        cases = receipt["value"]["receipts"]
        if name == "wrong-subject": cases[0]["actor"]["subjectIdentity"] ^= 1
        elif name == "wrong-current-byte": cases[0]["outputHex"] = cases[0]["outputHex"][:40] + "ff" + cases[0]["outputHex"][42:]
        elif name == "wrong-stale-generation": cases[1]["queryHex"] = cases[0]["queryHex"]
        elif name == "missing-free": receipt["calls"].pop()
        elif name == "wrong-service": cases[0]["serviceIdentity"]["entrySha256"] = "ff" * 32
        elif name == "wrong-entry-argument": receipt["calls"][1]["entryArguments"][0] ^= 4
        elif name == "changed-state": cases[0]["stateAfterSha256"] = "ff" * 32
        else:
            for index, case in enumerate(cases):
                actor = case["actor"]
                if name in generation_controls: actor[generation_controls[name]] += 1
                elif name == "changed-engine-owner":
                    actor["sourceIdentity"]["object"] += 300
                    actor["engineIdentity"]["pointer"] += 300
                else: actor["roleId"] = 3
                current = actor_bytes(actor)
                case["currentActorHex"] = case["currentActorAfterHex"] = current.hex()
                if index == 0:
                    output = bytearray.fromhex(case["outputHex"])
                    output[20:108] = current
                    case["outputHex"] = output.hex()
        try:
            actor_inspect_measurements(test, changed, record, repo, oracle=oracle)
        except ValueError as error:
            require(str(error).removeprefix("actor inspect: ").removeprefix("actor inspect: ") == reasons[name],
                    "negative rejected for unrelated reason: " + name + ": " + str(error))
            controls[name] = dict(rejected=True, reason=str(error))
        else:
            raise ValueError("actor inspect: negative accepted: " + name)
    return dict(scope="copied-data evaluator controls, not live recorder controls", controls=controls)

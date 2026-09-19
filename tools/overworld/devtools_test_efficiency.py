"""Cheap, advisory setup accounting for an already validated checked test.

No emulator, filesystem, timing prediction, test mutation or acceptance policy.
Conditional actions count toward the ceilings because they may execute. The
overall test budget can stop execution before these summed ceilings are reached.
"""
from tools.overworld.devtools_contract import PREPARED_OPS


def setup_efficiency_report(test):
    """Describe setup cost and avoidable dialogue; never reject a valid fixture."""
    setup = test["setup"]
    ceilings = {key: sum(action["budget"][key] for action in setup)
                for key in ("maxSeconds", "maxFrames")}
    kinds = {measurement["kind"] for measurement in test.get("measurements", [])}
    warnings = []
    # Setup-specific diagnostics intentionally exercise these actions. This is
    # not a blanket rule against normal setup or prepared movement fixtures.
    if kinds.intersection({"unmounted-cadence-v1", "unmounted-game-cadence-v1", "live-route-control-v1"}) and not kinds.intersection(
            {"cyndaquil-normal-setup-v1", "center-entry-exit-v1"}):
        dialogue_actions = []
        for action in setup:
            args = action["args"]
            predicates = (args.get("predicate"), args.get("until"), action.get("skipIf"))
            typed_dialogue = any(isinstance(predicate, dict)
                                 and predicate.get("kind") == "dialogue-state"
                                 for predicate in predicates)
            if typed_dialogue:
                dialogue_actions.append(action["id"])
        if dialogue_actions:
            warnings.append({
                "code": "avoidable-dialogue-setup",
                "message": "This cadence test depends on nurse/dialogue setup. If healing is not the claim, "
                           "use an authorized prepared party/follower fixture and measure normal movement afterward. "
                           "Keep the declared fixture provenance and movement requirements.",
                "actionIds": dialogue_actions,
            })
    return {
        "setupActionCount": len(setup),
        "setupBudgetCeilings": ceilings,
        "preparedOperationCount": sum(action["op"] in PREPARED_OPS for action in setup),
        "warnings": warnings,
        "budgetNote": "Sums of setup action budget ceilings, including conditional actions; not estimated runtime. "
                      "The overall test budget still applies. This report does not grant or deny proof.",
    }

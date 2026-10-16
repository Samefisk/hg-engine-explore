"""The final Select edge must survive a queued follower switch after a mount cycle.

The shared test runner supplies complete game-frame samples. This pure checker
does not start a game or change the save.
"""

from copy import deepcopy


KIND = "mount-select-switch-v1"
REQUIREMENT = "current.mount-select-during-follower-switch"
CLAIMS = ("natural-input", "live-actor-identity", "frame-pacing", "control-release")
MAX_MOUNT_FRAMES = 120
ACTIONS = (
    "wait-saved-stantler", "press-select-mount-stantler", "release-select-mount",
    "press-select-dismount-stantler", "wait-stantler-follower",
    "open-selector", "release-y", "highlight-mankey",
    "confirm-mankey", "release-confirm", "press-select-during-switch",
    "wait-one-press-mount", "bind-mounted-mankey", "observe-mounted-mankey",
)
FAULTS = ("missing-select-edge", "second-select-edge", "missing-initial-mount",
          "missing-mount", "changed-actor")


def contract():
    def exact(name):
        return {"name": name, "operator": "eq", "type": "integer",
                "validator": "meaningful-observation", "expected": 1}

    return {
        "natural-input": [exact("select-edge-during-switch-queue"),
                          exact("one-final-select-edge")],
        "live-actor-identity": [exact("same-stantler-mount-dismount"),
                                exact("switch-created-mankey-follower"),
                                exact("same-mankey-mounted")],
        "frame-pacing": [{"name": "select-to-mount-completed-frames", "operator": "lte",
                          "type": "integer", "validator": "meaningful-observation",
                          "expected": MAX_MOUNT_FRAMES}],
        "control-release": [exact("mounted-mankey-owns-input")],
    }


def _require(condition, reason):
    if not condition:
        raise ValueError("mount Select during switch: " + reason)


def _actor(sample, species, role):
    actors = [actor for actor in sample.get("actors", [])
              if actor.get("active") is True and actor.get("species") == species
              and actor.get("role") == role]
    _require(len(actors) == 1, f"expected one current {species} {role}")
    actor = actors[0]
    _require(actor.get("identityVerified") is True and
             actor.get("presentationAttached") is True,
             "current actor identity or presentation is missing")
    return actor


def _stream(rows):
    frames = []
    for row in rows:
        if row.get("phase") == "setup":
            _require(not frames and row.get("initialSnapshot") is not None,
                     "saved follower setup snapshot is missing or out of order")
            # An already-settled saved follower makes the first wait consume
            # zero frames. Its read-only initial snapshot is the baseline.
            frames.append(("wait-saved-stantler", deepcopy(row["initialSnapshot"])))
            continue
        samples = row.get("samples")
        if samples is None:
            continue
        _require(row.get("phase") == "observe" and row.get("action") in ACTIONS
                 and row.get("completedGameFrames") == len(samples) and samples,
                 "sample chunk is not a complete reviewed action")
        frames.extend((row["action"], deepcopy(sample)) for sample in samples)
    _require(frames, "no completed game frames")
    for (_, left), (_, right) in zip(frames, frames[1:]):
        _require(right["frame"] == left["frame"] + 1,
                 "completed game frame is missing")
        _require(right.get("nativeCycle", 0) >= left.get("nativeCycle", 0),
                 "native clock reversed")
    return frames


def _measure(frames):
    initial = next((sample for action, sample in frames
                    if action == "wait-saved-stantler"), None)
    _require(initial is not None, "saved follower was not sampled")
    initial_follower = _actor(initial, 234, "FOLLOWER")
    select_actions = ("press-select-mount-stantler", "press-select-dismount-stantler")
    select_rows = {}
    for action in select_actions:
        matches = [(index, sample) for index, (actual, sample) in enumerate(frames)
                   if actual == action]
        _require(len(matches) == 1, action + " did not take exactly one completed frame")
        index, sample = matches[0]
        selector = sample.get("selector", {})
        _require(selector.get("rawNew") == 4 and selector.get("newKeys") == 4 and
                 selector.get("rawHeld") == 4 and selector.get("heldKeys") == 4,
                 action + " lacks one native Select edge")
        select_rows[action] = (index, sample)
    final_press = [(index, sample) for index, (action, sample) in enumerate(frames)
                   if action == "press-select-during-switch"]
    _require(len(final_press) == 1, "final Select action did not take one frame")
    press_index, _ = final_press[0]
    _require(press_index > 0 and frames[press_index - 1][0] == "release-confirm",
             "Select did not follow the Y release")
    # The menu release can defer the raw key snapshot by one game update.
    # Accept the edge on the press frame or the first neutral wait frame.
    final_edges = [(index, sample) for index, (_, sample) in
                   enumerate(frames[press_index:press_index + 2], press_index)
                   if sample.get("selector", {}).get("rawNew") == 4]
    _require(len(final_edges) == 1, "final Select lacks one native edge")
    select_index, select = final_edges[0]
    select_rows["press-select-during-switch"] = (select_index, select)
    _require(select.get("selector", {}).get("newKeys") == 4 and
             select.get("selector", {}).get("rawHeld") == 4 and
             select.get("selector", {}).get("heldKeys") == 4,
             "final Select native edge is incomplete")
    _require(not any(sample.get("selector", {}).get("rawNew", 0) & 4
                     for index, (_, sample) in enumerate(frames)
                     if index not in {entry[0] for entry in select_rows.values()}),
             "a fourth Select edge was used")
    first_index = select_rows["press-select-mount-stantler"][0]
    second_index = select_rows["press-select-dismount-stantler"][0]
    release_rows = [sample for action, sample in frames[first_index + 1:second_index]
                    if action == "release-select-mount"]
    _require(first_index < second_index and release_rows and
             release_rows[-1].get("selector", {}).get("rawHeld") == 0,
             "first Select was not released before dismount")
    mounted_stantler_rows = [(index, sample) for index, (action, sample) in enumerate(frames)
                             if first_index < index < second_index and
                             action == "release-select-mount" and
                             any(actor.get("active") is True and actor.get("species") == 234
                                 and actor.get("role") == "MOUNTED"
                                 for actor in sample.get("actors", []))]
    _require(mounted_stantler_rows, "first Select never mounted Stantler")
    mounted_stantler = _actor(mounted_stantler_rows[0][1], 234, "MOUNTED")
    _require(mounted_stantler.get("subjectIdentity") == initial_follower.get("subjectIdentity")
             and mounted_stantler.get("handle") == initial_follower.get("handle")
             and mounted_stantler.get("inputOwnership") == 1,
             "first Select mounted a different Stantler or lost input")
    dismount_rows = [(index, sample) for index, (action, sample) in enumerate(frames)
                     if second_index < index and action == "wait-stantler-follower"]
    _require(dismount_rows, "Stantler dismount wait has no complete frame")
    dismounted = _actor(dismount_rows[-1][1], 234, "FOLLOWER")
    _require(dismounted.get("subjectIdentity") == initial_follower.get("subjectIdentity")
             and dismounted.get("handle") == initial_follower.get("handle")
             and dismount_rows[-1][1].get("selector", {}).get("activeFollowerPartySlot") == 0,
             "second Select did not restore the same Stantler Follower")
    highlight = next((sample for action, sample in frames
                      if action == "highlight-mankey" and
                      sample.get("selector", {}).get("highlight") == 2), None)
    _require(highlight is not None, "normal R did not highlight slot 2")
    confirm = next((sample for action, sample in frames
                    if action == "confirm-mankey" and
                    sample.get("selector", {}).get("state") == 0), None)
    _require(confirm is not None and confirm["selector"]["queue"]["count"] > 0,
             "Y did not start a queued follower change")
    selector = select.get("selector", {})
    _require(selector.get("rawNew") == 4 and selector.get("newKeys") == 4 and
             selector.get("rawHeld") == 4 and selector.get("heldKeys") == 4 and
             selector.get("state") == 0 and selector.get("queue", {}).get("count", 0) > 0,
             "native Select edge was not seen while the switch queue was active")
    _require(select.get("fieldAvailable") is True and
             select.get("observationBoundary") == "main-task-queue-completion",
             "Select was not read after a complete field update")
    wait_rows = [(index, sample) for index, (action, sample) in enumerate(frames)
                 if index > select_index and action == "wait-one-press-mount"]
    _require(wait_rows and all(sample.get("selector", {}).get("rawHeld") == 0
                               and sample.get("selector", {}).get("heldKeys") == 0
                               for _, sample in wait_rows),
             "Select was held or pressed again during the wait")
    follower_rows = [(index, sample) for index, sample in wait_rows
                     if any(actor.get("active") is True and actor.get("role") == "FOLLOWER"
                            and actor.get("species") == 56 for actor in sample.get("actors", []))]
    _require(follower_rows, "queued switch never created Mankey as Follower")
    follower_index, follower_sample = follower_rows[0]
    follower = _actor(follower_sample, 56, "FOLLOWER")
    mounted_rows = [(index, sample) for index, sample in wait_rows
                    if any(actor.get("active") is True and actor.get("role") == "MOUNTED"
                           and actor.get("species") == 56 for actor in sample.get("actors", []))]
    _require(mounted_rows, "the chosen Mankey never mounted after one Select")
    mount_index, mount_sample = mounted_rows[0]
    _require(mount_index > follower_index, "Mankey did not become Follower before mount")
    elapsed = mount_sample["frame"] - select["frame"]
    _require(0 < elapsed <= MAX_MOUNT_FRAMES,
             "Select-to-mount exceeded 120 completed game frames")
    mounted = _actor(mount_sample, 56, "MOUNTED")
    _require(mounted.get("subjectIdentity") == follower.get("subjectIdentity") and
             mounted.get("handle") == follower.get("handle") and
             mounted.get("engineIdentity", {}).get("pointer") ==
             follower.get("engineIdentity", {}).get("pointer") and
             mount_sample.get("context") == follower_sample.get("context"),
             "the mounted Mankey is not the selected Follower")
    _require(mounted.get("inputOwnership") == 1 and mounted.get("lane") == "OWNER" and
             mount_sample.get("selector", {}).get("queue", {}).get("count") == 0 and
             mount_sample.get("selector", {}).get("activeFollowerPartySlot") == 2,
             "mounted Mankey does not own input after the queue drains")
    return {"values": {
        "select-edge-during-switch-queue": 1,
        "one-final-select-edge": 1,
        "same-stantler-mount-dismount": 1,
        "switch-created-mankey-follower": 1,
        "same-mankey-mounted": 1,
        "select-to-mount-completed-frames": elapsed,
        "mounted-mankey-owns-input": 1,
    }, "selectFrame": select["frame"], "mountFrame": mount_sample["frame"],
        "subjectIdentity": mounted["subjectIdentity"], "actorHandle": mounted["handle"]}


def run(rows, test=None, fault=None):
    applied = False
    try:
        if test is not None:
            _require(test.get("id") == "mount.select-during-follower-switch" and
                     test.get("mode") == "normal" and test.get("setup") == [] and
                     [action["id"] for action in test.get("actions", [])] == list(ACTIONS),
                     "reviewed one-press recipe changed")
        frames = _stream(rows)
        if fault == "missing-select-edge":
            sample = next(sample for action, sample in frames
                          if action in ("press-select-during-switch", "wait-one-press-mount")
                          and sample.get("selector", {}).get("rawNew") == 4)
            sample["selector"]["rawNew"] = 0
            applied = True
        elif fault == "second-select-edge":
            edge_frame = next(sample["frame"] for action, sample in frames
                              if action in ("press-select-during-switch", "wait-one-press-mount")
                              and sample.get("selector", {}).get("rawNew") == 4)
            sample = next(sample for action, sample in frames
                          if action == "wait-one-press-mount" and
                          sample["frame"] > edge_frame)
            sample["selector"]["rawNew"] = 4
            applied = True
        elif fault == "missing-initial-mount":
            for action, sample in frames:
                if action != "release-select-mount":
                    continue
                for actor in sample.get("actors", []):
                    if actor.get("species") == 234 and actor.get("role") == "MOUNTED":
                        actor["role"] = "FOLLOWER"
                        applied = True
        elif fault == "missing-mount":
            for _, sample in frames:
                for actor in sample.get("actors", []):
                    if actor.get("species") == 56 and actor.get("role") == "MOUNTED":
                        actor["role"] = "FOLLOWER"
                        applied = True
        elif fault == "changed-actor":
            sample = next(sample for action, sample in frames
                          if action == "wait-one-press-mount" and
                          any(a.get("species") == 56 and a.get("role") == "MOUNTED"
                              for a in sample.get("actors", [])))
            _actor(sample, 56, "MOUNTED")["subjectIdentity"] ^= 1
            applied = True
        elif fault is not None:
            raise ValueError("unknown Select switch control: " + str(fault))
        evidence = _measure(frames)
        return {"passed": True, "faultApplied": applied, "failures": [], **evidence}
    except (ValueError, KeyError, StopIteration) as exc:
        return {"passed": False, "faultApplied": applied, "failures": [str(exc)]}


def negative_controls(rows, test=None):
    results = {name: run(rows, test, name) for name in FAULTS}
    return {"passed": all(result["faultApplied"] and not result["passed"]
                          for result in results.values()), "controls": results}

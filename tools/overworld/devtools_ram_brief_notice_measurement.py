"""A brief player sighting activates Ram while its ordinary Walk completes."""

from copy import deepcopy

from tools.overworld.devtools_profile_feature_measurement import ProfileFeatureMeasurement, require
from tools.overworld.devtools_ram_until_crash_measurement import (
    RamUntilCrashMeasurement, CONDITION, RAM_MASK,
)


KIND = "ram-brief-notice-v1"
REQUIREMENT = "current.ram-brief-notice"
PENDING = 1 << 5
ACTIVE = 1
UNTIL_CRASH = 1 << 3
BRIEF_WINDOW_FRAMES = 6
SETUP = (("teleport", {"map": 33, "x": 606, "z": 403, "facing": 0}),
         ("party", {"slot": 0, "species": 155, "level": 20}),
         ("spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20}),
         ("spawn", {"species": 95, "form": 0, "role": "wild", "level": 5,
                    "x": 602, "z": 402}),
         ("bind", {"subject": "onix"}),
         ("terrain", {"x": 603, "z": 402, "radius": 3}))
STEPS = (("wait-ordinary-walk", 120, (), "ordinary-moving"),
         ("cross-into-line", 12, ("UP", "B"), "player-on-line"),
         ("brief-line-hold", 6, (), None),
         ("leave-line", 12, ("DOWN", "B"), "player-off-line"),
         ("wait-charge", 80, (), "charge-started"),
         ("finish-first-charge-tile", 48, (), "complete"))


def validate_recipe(test):
    require(test["id"] == "profile.ram.brief-notice" and test["mode"] == "prepared"
            and test["measurements"] == [{"kind": KIND, "subject": "onix"}]
            and tuple((a["op"], a["args"]) for a in test["setup"]) == SETUP
            and len(test["actions"]) == len(STEPS)
            and test["budgets"]["minObservedFrames"] >= 25
            and test["budgets"]["maxFrames"] <= 300,
            "brief Ram notice fixture differs")
    for action, (_, frames, keys, stage) in zip(test["actions"], STEPS):
        expected = {"frames": frames, "keys": list(keys)}
        if stage is not None:
            expected["until"] = ({"kind": "measurement-complete", "measurement": KIND,
                                  "when": "final"} if stage == "complete" else
                                 {"kind": "measurement-stage", "measurement": KIND,
                                  "stage": stage, "when": "final"})
        require(action["op"] == "step" and action["args"] == expected,
                "brief Ram notice input differs")


class RamBriefNoticeMeasurement(ProfileFeatureMeasurement):
    _condition_state = RamUntilCrashMeasurement._condition_state

    def __init__(self, kind=KIND, test=None, max_frames=300):
        super().__init__(kind, test, max_frames)
        self.condition_reader_identity = None
        self.current_events = []
        self.ordinary = None
        self.line_frame = self.pending_frame = self.off_line_frame = None
        self.ordinary_complete = None
        self.trigger = self.first_charge = self.charge_complete = None
        self.activation_state = self.off_line_active = self.presentation = None
        self.charge_heading = None
        self.charge_starts = []
        self.pending_after_exit = False
        self.terrain_witness = None
        self.line_entry = None

    def observe(self, snapshot, events):
        self.current_events = list(events)
        return super().observe(snapshot, events)

    def observe_terrain(self, snapshot):
        require(self.terrain_witness is None, "Ram notice terrain was read more than once")
        terrain = snapshot.get("terrain", {})
        observation = terrain.get("observation", {})
        require(observation.get("boundary") == "paused-native-cycle-end"
                and observation.get("nativeCycle") == snapshot.get("nativeCycle")
                and observation.get("lastCompletedGameFrame") == snapshot.get("frame")
                and observation.get("context") == snapshot.get("context")
                and observation.get("center") == {"x": 603, "z": 402}
                and snapshot.get("context", {}).get("mapId") == 33,
                "Ram notice terrain lacks its exact current native boundary")
        cells = terrain.get("cells", [])
        require(len(cells) == 49 and {(c.get("x"), c.get("y")) for c in cells}
                == {(x, y) for y in range(399, 406) for x in range(600, 607)},
                "Ram notice native terrain box differs")
        lane = [next((c for c in cells if c.get("x") == x and c.get("y") == 402), None)
                for x in range(601, 607)]
        require(all(isinstance(c, dict) and c.get("loaded") is True
                    and c.get("collision") is False
                    and c.get("provenance", {}).get("mapHeaderId") == 33
                    and c.get("provenance", {}).get("landDataIdentity") == "current-map-matrix"
                    for c in lane), "Ram notice line has no current clear native terrain")
        self.terrain_witness = {"frame": snapshot["frame"],
                                "nativeCycle": snapshot["nativeCycle"],
                                "context": deepcopy(snapshot["context"]),
                                "romSha256": snapshot["romSha256"],
                                "observation": deepcopy(observation),
                                "cells": deepcopy(lane)}

    def _line_terrain(self, snapshot):
        witness = self.terrain_witness
        require(witness is not None and witness["frame"] <= snapshot["frame"]
                and witness["nativeCycle"] <= snapshot["nativeCycle"]
                and witness["context"] == snapshot["context"]
                and witness["romSha256"] == snapshot["romSha256"],
                "Ram notice sight lacks the same current native terrain")

    def _accepted_plan(self, snapshot, actor):
        combat = snapshot.get("pokemonCombat", {})
        require(combat.get("schemaVersion") == 1 and combat.get("available") is True
                and combat.get("frame") == snapshot["frame"]
                and combat.get("nativeCycle") == snapshot.get("nativeCycle")
                and combat.get("observationBoundary") == "main-task-queue-completion"
                and combat.get("identity", {}).get("romSha256") == snapshot.get("romSha256"),
                "Ram lacks a current native accepted-plan reader")
        targets = [target for target in combat.get("targets", [])
                   if target.get("handle") == actor["handle"]
                   and target.get("role") == "WILD"
                   and target.get("species") == 95]
        require(len(targets) == 1, "Ram accepted plan has no current Onix owner")
        motion = targets[0].get("motion", {})
        plan = motion.get("plan", {})
        require(motion.get("phase") == actor.get("motionPhase")
                and plan.get("version") == 1 and plan.get("kind") == 1
                and plan.get("fieldEpoch") == actor["handle"]["fieldEpoch"]
                and plan.get("reservationId") == actor.get("reservationId")
                and plan.get("origin") == [actor["origin"][key] for key in ("x", "y")]
                and plan.get("target") == [actor["target"][key] for key in ("x", "y")]
                and plan.get("duration") == actor.get("motionDuration")
                and plan.get("facing") == actor.get("engineObject", {}).get("facing")
                and type(plan.get("behaviorFingerprint")) is int
                and plan["behaviorFingerprint"] > 0,
                "Ram accepted Walk plan differs from its live actor")
        return plan

    def _same_ordinary(self, snapshot, actor):
        motion = self.ordinary
        return motion is not None and actor.get("motionKind") == "WALK" \
            and actor.get("motionPhase") == "MOVING" \
            and actor.get("origin") == motion["origin"] \
            and actor.get("target") == motion["target"] \
            and actor.get("motionDuration") == motion["duration"] \
            and actor.get("reservationId") == motion["reservationId"] \
            and actor.get("engineObject", {}).get("facing") == motion["facing"] \
            and self._accepted_plan(snapshot, actor) == motion["plan"]

    def _same_active_lifetime(self, state):
        first = self.activation_state
        return first is not None and state.get("flags", 0) & (ACTIVE | UNTIL_CRASH) \
            == ACTIVE | UNTIL_CRASH \
            and state.get("targetKind") == 1 \
            and all(state.get(key) == first.get(key) for key in (
                "targetSlot", "targetGeneration", "targetEncounterGeneration",
                "activeUntil", "cooldownUntil"))

    def _ordinary_terminal_receipts(self, actor, motion):
        events = [event for event in self.events
                  if event.get("kind") == "native"
                  and event.get("frame") == motion["finishFrame"]
                  and event.get("data", {}).get("actorHandle") == actor["handle"]["value"]
                  and event["data"].get("actor") == {
                      key: value for key, value in actor["handle"].items() if key != "value"}]
        ordered = []
        for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            event = next((item for item in events
                          if item["data"].get("event") == name
                          and (not ordered or item["data"].get("sequence", 0)
                               > ordered[-1]["data"]["sequence"])), None)
            require(event is not None,
                    "ordinary Walk lacks same-owner native commit and control")
            ordered.append(event)
        require(ordered[0]["data"].get("valueA") == motion["commitAfter"]
                and ordered[1]["data"].get("valueA") == motion["commitAfter"]
                and ordered[2]["data"].get("valueB") == motion["commitAfter"],
                "ordinary Walk native terminal token differs")

    def _sample(self, snapshot, actors):
        actor = actors["onix"]
        frame = snapshot["frame"]
        player = snapshot["player"]
        require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0
                and snapshot.get("context", {}).get("mapId") == 33
                and player.get("x") == 606,
                "brief Ram notice left its current Route 29 field")
        state, _, _ = self._condition_state(snapshot, actor)
        flags = state["flags"]
        super()._sample(snapshot, actors)
        if self.ordinary is None and actor.get("motionKind") == "WALK" \
                and actor.get("motionPhase") == "MOVING" \
                and actor.get("motionElapsed") in (0, 1) \
                and not actor.get("matchedLayerMask", 0) & RAM_MASK:
            origin, target = actor["origin"], actor["target"]
            if origin == {"x": 602, "y": 402} and target.get("y") == 402 \
                    and abs(target.get("x", 999) - 602) == 1:
                plan = self._accepted_plan(snapshot, actor)
                self.ordinary = {"startFrame": frame, "origin": deepcopy(origin),
                                 "target": deepcopy(target),
                                 "duration": actor["motionDuration"],
                                 "reservationId": actor["reservationId"],
                                 "plan": deepcopy(plan),
                                 "planFingerprint": plan["behaviorFingerprint"],
                                 "facing": actor["engineObject"]["facing"],
                                 "commitBefore": actor["commitSequence"]}
                require(1 <= self.ordinary["duration"] <= 32,
                        "ordinary Walk duration differs")
        if self.ordinary is not None and self.ordinary_complete is None:
            for motion in self.motion.completed:
                if motion.get("kind") == "WALK" \
                        and motion.get("startFrame") == self.ordinary["startFrame"] \
                        and motion.get("origin") == [self.ordinary["origin"][k] for k in ("x", "y")]:
                    require(self._complete_motion(motion)
                            and motion.get("target") == [self.ordinary["target"][k] for k in ("x", "y")]
                            and motion.get("duration") == self.ordinary["duration"]
                            and motion.get("commitAfter") == self.ordinary["commitBefore"] + 1,
                            "ordinary Walk did not complete unchanged")
                    self._ordinary_terminal_receipts(actor, motion)
                    self.ordinary_complete = deepcopy(motion)
                    break
            if self.ordinary_complete is None and actor.get("motionKind") == "WALK" and actor.get("motionPhase") == "MOVING":
                require(self._same_ordinary(snapshot, actor),
                        "Ram replaced or retimed the accepted ordinary Walk")
            on_line = player.get("y") == 402
            if on_line and self.line_frame is None and self.ordinary_complete is None:
                require(self._same_ordinary(snapshot, actor),
                        "player reached Ram line after ordinary Walk ended")
                require(player.get("x_prev") == 606 and player.get("y_prev") == 403
                        and player.get("movement_cmd") == 88
                        and player.get("movement_step") == 1
                        and player.get("facing") == 0
                        and (402 << 16) + 0x8000 < player.get("pos_z", 0)
                            < (403 << 16) + 0x8000,
                        "Ram notice did not enter the logical sight row through normal Up+B")
                self.line_frame = frame
                self.line_entry = {"frame": frame, "player": deepcopy(player)}
                self._line_terrain(snapshot)
            if self.ordinary_complete is None:
                require(self.line_frame is not None or not flags & (ACTIVE | PENDING)
                        and not actor.get("matchedLayerMask", 0) & RAM_MASK,
                        "Ram activated before the brief player sighting")
            if flags & (ACTIVE | PENDING) and self.ordinary_complete is None:
                require(self.line_frame is not None and self._same_ordinary(snapshot, actor)
                        and flags & (ACTIVE | PENDING | UNTIL_CRASH)
                            == ACTIVE | PENDING | UNTIL_CRASH
                        and state.get("targetKind") == 1
                        and state.get("activeUntil") == 0
                        and actor.get("matchedLayerMask", 0) & RAM_MASK,
                        "Ram did not become active with pending presentation during ordinary Walk")
                if self.trigger is None:
                    require(on_line and frame <= self.line_frame + BRIEF_WINDOW_FRAMES,
                            "Ram activation missed the brief player sighting")
                    self.pending_frame = frame
                    self.activation_state = deepcopy(state)
                    self.trigger = {"frame": frame, "active": True,
                                    "untilCrash": True, "targetKind": state["targetKind"],
                                    "activeUntil": state["activeUntil"],
                                    "cooldownUntil": state["cooldownUntil"],
                                    "source": "authenticated-prepared-state"}
                else:
                    require(self._same_active_lifetime(state),
                            "active Ram lifetime changed before ordinary Walk ended")
            if player.get("y") == 403 and self.line_frame is not None and self.ordinary_complete is None:
                if self.off_line_frame is None:
                    require(self.pending_frame is not None and self._same_ordinary(snapshot, actor)
                            and self._same_active_lifetime(state)
                            and flags & PENDING,
                            "player left before active Ram and pending presentation were retained")
                    self.off_line_frame = frame
                    self.off_line_active = deepcopy(state)
                self.pending_after_exit |= bool(flags & (ACTIVE | PENDING)
                                                == ACTIVE | PENDING)
        if self.trigger is not None:
            require(self._same_active_lifetime(state)
                    and actor.get("matchedLayerMask", 0) & RAM_MASK,
                    "Ram lost its active Until Crash lifetime")
            if self.first_charge is None and self.ordinary_complete is not None:
                require(self.off_line_frame is not None and self.pending_after_exit,
                        "Ram did not stay active after the player left its sight line")
                if flags & PENDING:
                    require(self.presentation is None,
                            "Ram restarted pending presentation after consumption")
                else:
                    intent = next((event for event in self.current_events
                        if event.get("kind") == "native"
                        and event.get("data", {}).get("actorHandle")
                            == actor["handle"]["value"]
                        and event["data"].get("actor") == {
                            key: value for key, value in actor["handle"].items()
                            if key != "value"}
                        and event["data"].get("event") == "INTENT_CREATED"), None)
                    require(self.presentation is not None or intent is not None,
                            "Ram cleared pending presentation before a legal intent")
                    if self.presentation is None:
                        self.presentation = {"frame": frame, "intent": deepcopy(intent),
                                             "state": deepcopy(state)}
            if self.first_charge is not None:
                require(self.presentation is not None and not flags & PENDING,
                        "Ram restarted or retained pending presentation during charge")
            for event in self.current_events:
                data = event.get("data", {})
                if event.get("kind") != "native" or data.get("actorHandle") != actor["handle"]["value"] \
                        or data.get("event") != "MOTION_STARTED" or data.get("valueA") != 1:
                    continue
                if event["frame"] < self.trigger["frame"]:
                    continue
                require(self.ordinary_complete is not None
                        and self.presentation is not None
                        and self.presentation["intent"]["data"]["sequence"]
                            < data.get("sequence", 0)
                        and not flags & PENDING,
                        "Ram did not consume pending presentation at the next legal intent")
                origin, target = actor["origin"], actor["target"]
                heading = (target["x"] - origin["x"], target["y"] - origin["y"])
                require(heading == (1, 0) and player.get("x") > origin["x"]
                        and abs(player.get("x") - origin["x"]) > abs(player.get("y") - origin["y"]),
                        "Ram did not aim East at the current off-axis player")
                require(self.charge_heading in (None, heading),
                        "Ram changed its committed charge heading")
                self.charge_heading = heading
                self.charge_starts.append(frame)
                if self.first_charge is None:
                    require(0 <= frame - self.presentation["frame"] <= 1,
                            "Ram paused after pending presentation was consumed")
                    self.first_charge = deepcopy(event)
        if self.first_charge is not None:
            for motion in self.motion.completed:
                if motion.get("kind") == "WALK" and motion.get("startFrame") == self.first_charge["frame"] \
                        and self._complete_motion(motion):
                    self.charge_complete = deepcopy(motion)
                    break

    def stage(self, name):
        return not self.failures and {
            "ordinary-moving": self.ordinary is not None,
            "player-on-line": self.line_frame is not None,
            "player-off-line": self.off_line_frame is not None,
            "charge-started": self.first_charge is not None,
        }.get(name, False)

    @property
    def ready(self):
        return bool(not self.failures and self.terrain_witness
                    and self.line_entry
                    and self.ordinary_complete and self.pending_after_exit
                    and self.trigger and self.activation_state and self.off_line_active
                    and self.presentation and self.first_charge and self.charge_complete
                    and self.charge_heading == (1, 0)
                    and self.line_frame <= self.pending_frame == self.trigger["frame"]
                    <= self.line_frame + BRIEF_WINDOW_FRAMES < self.off_line_frame
                    < self.ordinary_complete["finishFrame"]
                    <= self.presentation["frame"] <= self.first_charge["frame"])

    def result(self):
        return {**super().result(), "ordinary": deepcopy(self.ordinary),
                "ordinaryComplete": deepcopy(self.ordinary_complete),
                "lineFrame": self.line_frame, "pendingFrame": self.pending_frame,
                "offLineFrame": self.off_line_frame,
                "activationState": deepcopy(self.activation_state),
                "offLineActive": deepcopy(self.off_line_active),
                "pendingAfterExit": self.pending_after_exit,
                "terrainWitness": deepcopy(self.terrain_witness),
                "lineEntry": deepcopy(self.line_entry),
                "trigger": deepcopy(self.trigger),
                "presentation": deepcopy(self.presentation),
                "firstCharge": deepcopy(self.first_charge),
                "chargeComplete": deepcopy(self.charge_complete),
                "chargeHeading": self.charge_heading,
                "chargeStarts": deepcopy(self.charge_starts)}

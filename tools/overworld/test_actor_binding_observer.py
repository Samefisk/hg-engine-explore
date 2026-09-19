"""Public actor decoder/evidence round trips, independent of any game driver."""

from copy import deepcopy
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.overworld import actor_probe
from tools.overworld.trace import HEADER, RECORD, load_trace_schema
from tools.overworld.validation import ValidationFailure
from tools.overworld.test_host_verification import retained_scenario_contract


class BindingEvidenceRoundTripTests(unittest.TestCase):
    """Exercise the real public binary decoder and accepted evidence reader.

    Bytes below are authored host fixtures, not captured game/ROM data. This
    checks the observer boundary only; it cannot replace the live scenario.
    """

    def capture(self, *, presentation_state=7):
        schema = load_trace_schema(REPO / "tools/overworld/schemas/semantic-trace-v1.json")
        actor_format = "<HH6H8I8h4H16B"
        actor_size = struct.calcsize(actor_format)
        actor_address, header_address, events_address = 32, 128, 192
        descriptor = {
            "formatVersion": 1, "facade": {"version": 1},
            "overlay": {"sha256": "0" * 64},
            "state": {"address": 0, "actorStride": 96,
                      "offsets": {"fieldEpoch": 0, "actors": actor_address,
                                  "traceHeader": header_address, "traceEvents": events_address}},
            "capacities": {"actors": 1, "traceEvents": 8},
            "structures": {"traceHeader": HEADER.size, "traceEvent": RECORD.size},
            "publicLayouts": {"actorState": {"format": actor_format, "size": actor_size}},
            "enums": {
                "OverworldActorRole": {"OVERWORLD_ACTOR_ROLE_WILD": 1},
                "BehaviorResolutionLane": {"BEHAVIOR_RESOLUTION_LANE_OWNER": 0},
                "OverworldActorMotionKind": {"OVERWORLD_ACTOR_MOTION_NONE": 0},
                "OverworldActorMotionPhase": {"OVERWORLD_ACTOR_PHASE_IDLE": 0},
            },
        }
        memory = bytearray(events_address + 8 * RECORD.size)
        struct.pack_into("<H", memory, 0, 2)
        # Public actor handle: slot 0, generation 1, field/map 2, encounter 3.
        values = (
            1, actor_size, 0, 1, 2, 2, 3, 0,
            0xF0000001, 0x1234, 0x56, 4, 9, 1, 1, 1,
            585, 406, 585, 406, 584, 406, 585, 406,
            8, 8, 41, 19,
            0, 5, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1,
            presentation_state, 0,
        )
        struct.pack_into(actor_format, memory, actor_address, *values)
        HEADER.pack_into(memory, header_address, b"OWTR", 1, HEADER.size,
                         1, 5, 0, 0, 2, 0xFFFF, 0, 0, 4, 4, 0, 0)
        event_ids = {name: int(key) for key, name in schema["events"].items()}
        events = [(100, "MOTION_STARTED", 1, 8), (108, "LOGICAL_COMMIT", 41, 1),
                  (108, "MOTION_FINISHED", 41, 1), (108, "CONTROL_RETURNED", 0, 41)]
        for index, (frame, event, value_a, value_b) in enumerate(events):
            RECORD.pack_into(memory, events_address + index * RECORD.size,
                             index + 1, frame, 0, 1, 2, 2, 3, 0,
                             event_ids[event], 0, value_a, value_b)
        evidence = actor_probe.capture_observation(
            lambda address, size: bytes(memory[address:address + size]), descriptor, schema)
        return evidence, schema

    def round_trip(self, evidence, schema):
        with tempfile.TemporaryDirectory(prefix="actor-binding-evidence-") as directory:
            path = Path(directory) / "evidence.json"
            actor_probe.write_evidence(evidence, path)
            return actor_probe.load_evidence(path, schema)

    def scenario(self):
        return retained_scenario_contract(
            REPO / "tests/overworld/scenarios/actor.binding.current-context.json")

    def test_actual_decoder_capture_and_file_reader_agree(self):
        evidence, schema = self.capture()
        loaded = self.round_trip(evidence, schema)
        self.assertEqual(loaded, evidence)
        actor = loaded["observation"]["actors"][0]
        self.assertEqual(actor["subjectIdentity"], 0xF0000001)
        self.assertEqual(actor["presentationState"], 7)
        self.assertEqual(actor["handle"]["mapGeneration"], 2)
        scenario = self.scenario()
        result = actor_probe.evaluate_scenario_evidence(scenario, loaded, schema)
        self.assertTrue(result["passed"], result)
        self.assertTrue(actor_probe.evaluate_subject_negative_control(scenario, loaded, schema)["passed"])
        self.assertTrue(actor_probe.evaluate_behavior_negative_control(scenario, loaded, schema)["passed"])

    def test_old_reader_schema_rejects_actual_decoder_output(self):
        evidence, schema = self.capture()
        with mock.patch.object(actor_probe, "ACTOR_STATE_KEYS",
                               actor_probe.ACTOR_STATE_KEYS - {"presentationState"}):
            with self.assertRaisesRegex(ValidationFailure, "actor snapshot 0 keys differ"):
                self.round_trip(evidence, schema)

    def test_missing_unknown_and_invalid_presentation_fields_still_rejected(self):
        evidence, schema = self.capture()
        for mutation in ("missing", "unknown", "negative", "boolean"):
            with self.subTest(mutation=mutation):
                changed = deepcopy(evidence)
                actor = changed["observation"]["actors"][0]
                if mutation == "missing":
                    del actor["presentationState"]
                elif mutation == "unknown":
                    actor["unrecognizedState"] = 7
                else:
                    actor["presentationState"] = -1 if mutation == "negative" else True
                with self.assertRaises(ValidationFailure):
                    self.round_trip(changed, schema)

    def test_decoded_nonvisible_actor_remains_a_failed_subject(self):
        for state in (0, 1, 3, 6):
            with self.subTest(presentation_state=state):
                evidence, schema = self.capture(presentation_state=state)
                loaded = self.round_trip(evidence, schema)
                result = actor_probe.evaluate_scenario_evidence(self.scenario(), loaded, schema)
                self.assertFalse(result["passed"])
                self.assertEqual(result["subjectAssertions"][0]["actual"], 0)


if __name__ == "__main__":
    unittest.main()

"""Exact registry rows and reason-sensitive copied negative controls."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from .devtools_mounted_nearest_diagonal_proof import (
    contract, measurements, REQUIREMENT, FAULTS, Negative, validate_negative_result,
)
from .test_devtools_mounted_nearest_diagonal import replay


class NearestProofTests(unittest.TestCase):
    def test_exact_contract_and_roundtrip(self):
        registry=json.loads((Path(__file__).parent/'runtime_proof_registry.json').read_text())
        self.assertEqual(contract(),registry['measurementContracts'][REQUIREMENT])
        rows=measurements(json.loads(json.dumps(replay())))
        self.assertEqual(len(rows),4);self.assertEqual(rows[0]['actual'],3)
        self.assertEqual(rows[-1]['actual']['chosen'],[546,390])

    def test_every_copied_fault_has_its_exact_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=Negative(fault);result=replay(negative)
                self.assertTrue(negative.applied)
                validate_negative_result(result,fault)

    def test_final_target_and_arc_cannot_be_relabelled(self):
        good=replay()
        for mutate in (lambda q:q['choice'].update(final=[547,390]),
                       lambda q:q['cases'][0]['samples'].pop(0),
                       lambda q:q['cases'][0]['terminalActor'].update(inputOwnership=0)):
            q=deepcopy(good);mutate(q)
            with self.assertRaises(ValueError):measurements(q)

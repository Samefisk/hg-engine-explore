"""Independent evidence-row checks for the exact retained Hop contract."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from .devtools_mounted_hop_arc_proof import contract, measurements, REQUIREMENT
from .test_devtools_mounted_hop_arc import replay


class HopArcProofTests(unittest.TestCase):
    def test_exact_registry_rows_and_json_round_trip(self):
        registry=json.loads((Path(__file__).parent/'runtime_proof_registry.json').read_text())
        self.assertEqual(contract(),registry['measurementContracts'][REQUIREMENT])
        result=json.loads(json.dumps(replay()))
        rows=measurements(result)
        self.assertEqual([row['name'] for row in rows],['started-hop-count','mankey-hops-identity','hop-arc-samples','recovered-hop-count'])
        self.assertEqual(rows[0]['actual'],3);self.assertEqual(len(rows[2]['actual']['cases']),3)

    def test_edited_proof_cannot_hide_missing_arc_start_lifecycle_or_terminal(self):
        good=replay()
        mutations=[lambda q:q['cases'][0]['samples'].pop(0),
                   lambda q:q['cases'][0]['observations'][1].update(faceY=0),
                   lambda q:q['cases'][0]['startReceipt']['data']['start'].update(elapsed=1),
                   lambda q:q['cases'][0]['summary']['lifecycle'][2].update(valueB=1),
                   lambda q:q['cases'][0]['terminalActor'].update(inputOwnership=0),
                   lambda q:q.update(closed=False)]
        for mutation in mutations:
            changed=deepcopy(good);mutation(changed)
            with self.assertRaises(ValueError):measurements(changed)

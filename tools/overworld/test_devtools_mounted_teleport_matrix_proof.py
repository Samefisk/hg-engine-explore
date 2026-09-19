from copy import deepcopy
import json
from pathlib import Path
import unittest
from .test_devtools_mounted_teleport_matrix import run_matrix
from .devtools_mounted_teleport_matrix_proof import measurements, contract, FAULTS, Negative, validate_negative_result


class MatrixProofTests(unittest.TestCase):
    def test_exact_registry_and_independent_rows(self):
        registry=json.loads((Path(__file__).parent/'runtime_proof_registry.json').read_text())
        def find(value):
            if isinstance(value,dict):
                if value.get('legacy.teleport-timing')==contract():return True
                return any(find(v) for v in value.values())
            return False
        self.assertTrue(find(registry))
        result=run_matrix();rows=measurements(result);self.assertEqual(len(rows),7)
        self.assertTrue(all('value' in row and row['passed'] is True for row in rows))
        bad=deepcopy(result)
        for sample in bad['cases'][4]['samples']:sample['visible']=False
        with self.assertRaisesRegex(ValueError,'compact matrix evidence'):measurements(bad)

    def test_all_copied_faults_fail_for_named_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=Negative(fault);result=run_matrix(negative)
                self.assertTrue(negative.applied);self.assertFalse(result['passed'],result['failures'])
                validate_negative_result(result,fault)


if __name__=='__main__':unittest.main()

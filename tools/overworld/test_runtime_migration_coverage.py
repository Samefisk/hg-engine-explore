"""Coverage replacement does not grant proof or dismiss failed runs."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld.test_runtime_migration_supersession import fixture


class MigrationCoverageTests(unittest.TestCase):
    def setUp(self):
        self.document,self.registry=fixture();self.registry['executionMethod']='shared-devtools'
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.repo=Path(self.temp.name)
        directory=self.repo/'tools/overworld';directory.mkdir(parents=True)
        (directory/'runtime_proof_migration.json').write_text(json.dumps(self.document))
        for name,row in self.registry['sharedTests'].items():row.update(mode='prepared',proofLevel='S3')
        self.scenarios={name:dict(id=name,status='active',proofLevel='S3',capabilities=['walk'],subjects=[],
            adapter=dict(kind='devtools-test',test=name,claims=['logical-commit'])) for name in ('old','middle','new')}
        self.evidence={name:dict(execution='shared-devtools',proofLevel='S3',claims=['logical-commit'],
            requirements=['legacy.'+name],manifest='host',runId='accepted-'+name) for name in ('middle','new')}
        self.check=dict(id='walk-check',proofLevel='S3',command=['python3','scripts/owctl','scenario','run','legacy.old'])
        self.manifest=dict(checks=[self.check],capabilities=[dict(id='walk',checks=['walk-check'],
            scenarios=['old','new'],minimumProof=['S3'],traceGroups=[])])
        self.addCleanup(patch.stopall)
        patch.object(control,'REPO',self.repo).start();patch.object(control,'RUNTIME_PROOF_REGISTRY',self.registry).start()

    def test_reviewed_summary_and_current_leaf_coverage(self):
        summary=control._runtime_migration_summary()
        self.assertEqual(summary['supersededCount'],1);self.assertEqual(summary['pendingCount'],0)
        exact=control._exact_runtime_scenarios(self.check,{'new'},self.scenarios,self.evidence)
        self.assertEqual(exact,{'new'})
        # Identity-only, wrong level, unlinked or no current receipt cannot stand in.
        for fault in ('claims','level','requirements','execution','missing','unlinked','control'):
            with self.subTest(fault=fault):
                evidence=deepcopy(self.evidence);scenarios=deepcopy(self.scenarios);linked={'new'}
                if fault=='claims':evidence['new']['claims']=['live-actor-identity']
                elif fault=='level':evidence['new']['proofLevel']='S4'
                elif fault=='requirements':evidence['new']['requirements']=['legacy.middle']
                elif fault=='execution':evidence['new']['execution']='legacy'
                elif fault=='missing':evidence={}
                elif fault=='unlinked':linked={'old'}
                elif fault=='control':scenarios['new']['verification']=dict(kind='observer-control')
                self.assertFalse(control._exact_runtime_scenarios(self.check,linked,scenarios,evidence))

    def test_all_split_replacement_leaves_required(self):
        # Two old metrics are checked by two separate leaf tests.
        old=self.document['requirements']['legacy.old'];extra=deepcopy(old['review']['coverage'][0])
        extra.update(measurement='second',replacementRequirement='legacy.middle',replacementMeasurement='middle-count')
        old['review']['coverage'].append(extra)
        contract=self.registry['measurementContracts']['legacy.old']
        contract['logical-commit'].append(dict(contract['logical-commit'][0],name='second'))
        old['measurementContractSha256']=hashlib.sha256(json.dumps(contract,
            sort_keys=True,separators=(',',':')).encode()).hexdigest()
        from tools.overworld.validation import resolve_runtime_migration_targets, validate_runtime_migration
        validate_runtime_migration(self.document,self.registry)
        self.assertEqual(resolve_runtime_migration_targets(self.document,'legacy.old'),['legacy.middle','legacy.new'])
        self.assertFalse(control._exact_runtime_scenarios(self.check,{'new','middle'},self.scenarios,
            {'new':self.evidence['new']},migration=self.document))
        self.assertEqual(control._exact_runtime_scenarios(self.check,{'new','middle'},self.scenarios,
            self.evidence,migration=self.document),{'new','middle'})

    def test_reader_requirement_needs_reader_proof_not_normal_behavior(self):
        for item in self.document['requirements'].values():
            item['verificationKind'] = 'observer-control'
        self.registry['sharedTests']['new']['mode'] = 'observer-control'
        self.scenarios['new']['verification'] = dict(kind='observer-control')
        self.assertEqual(control._exact_runtime_scenarios(self.check, {'new'}, self.scenarios,
            self.evidence, migration=self.document), {'new'})
        self.registry['sharedTests']['new']['mode'] = 'prepared'
        self.assertFalse(control._exact_runtime_scenarios(self.check, {'new'}, self.scenarios,
            self.evidence, migration=self.document))

    def test_old_obligation_omitted_only_after_current_replacement_and_no_catalog_mutation(self):
        before=deepcopy(self.scenarios)
        passed=control._roadmap_contract_audit(self.manifest,self.scenarios,[],self.evidence)
        self.assertEqual(passed['supersededScenarios'],['old'])
        self.assertNotIn('old',[row['id'] for row in passed['runtimeScenarioEvidence']])
        failed=control._roadmap_contract_audit(self.manifest,self.scenarios,[],{})
        self.assertEqual(failed['supersededScenarios'],[])
        self.assertIn('old',[row['id'] for row in failed['runtimeScenarioEvidenceGaps']])
        self.assertEqual(self.scenarios,before)


if __name__=='__main__':unittest.main()

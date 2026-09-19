"""Reviewed test replacement preserves every still-required behavior metric."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.validation import ValidationFailure, validate_runtime_migration, resolve_runtime_migration_targets


def fixture():
    registry=dict(runners={},runnerKinds={},measurementContracts={},sharedTests={})
    document=dict(schemaVersion=1,executionMethod='shared-devtools',legacyExecution='retired',
        requirements={},historicalScenarios={})
    for name in ('old','middle','new'):
        key='legacy.'+name;claim='logical-commit'
        contract={claim:[dict(name=name+'-count',operator='eq',type='integer',validator='meaningful-observation',expected=2)]}
        registry['runners'][key]=[claim];registry['runnerKinds'][key]='normal'
        registry['measurementContracts'][key]=contract
        registry['sharedTests'][name]=dict(requirements=[key],claims=[claim])
        document['requirements'][key]=dict(status='ported',verificationKind='normal',claims=[claim],
            measurementContractSha256=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            scenarios=[name],tests=[name],reason='existing contract',originRunner='retired.py::'+name)
        document['historicalScenarios'][name]=dict(id=name)
    supersede(document,'old','new')
    return document,registry


def supersede(document,source,target):
    document['requirements']['legacy.'+source].update(status='superseded',tests=[],
        review=dict(reviewer='reviewer-one',reviewedAt='2026-09-01',reason='Equivalent merged test with same bound',
            coverage=[dict(claim='logical-commit',measurement=source+'-count',replacementRequirement='legacy.'+target,
                replacementClaim='logical-commit',replacementMeasurement=target+'-count',reason='Same two-commit assertion')]))


def obsolete(document, source):
    document['requirements']['legacy.'+source].update(status='obsolete', tests=[],
        review=dict(reviewer='reviewer-one', reviewedAt='2026-09-12',
            reason='The product no longer has the measured operation.',
            removedAssumption='One update completes the whole operation and returns false.',
            currentContract='The operation resumes in bounded parts and reports pending.',
            evidence=['source:bounded-operation', 'runtime:bounded-operation']))


class MigrationSupersessionTests(unittest.TestCase):
    def test_current_requirement_is_not_a_legacy_migration_record(self):
        document, registry = fixture()
        contract = {
            'logical-commit': [dict(
                name='current-count', operator='eq', type='integer',
                validator='meaningful-observation', expected=2,
            )],
        }
        registry['runners']['current.runner-turn-runway'] = ['logical-commit']
        registry['runnerKinds']['current.runner-turn-runway'] = 'normal'
        registry['measurementContracts']['current.runner-turn-runway'] = contract

        validate_runtime_migration(document, registry)

        document['requirements'].pop('legacy.middle')
        with self.assertRaises(ValidationFailure):
            validate_runtime_migration(document, registry)

    def test_renamed_test_and_chained_replacement_preserve_coverage(self):
        document,registry=fixture();validate_runtime_migration(document,registry)
        self.assertEqual(resolve_runtime_migration_targets(document,'legacy.old'),['legacy.new'])
        supersede(document,'old','middle');supersede(document,'middle','new')
        validate_runtime_migration(document,registry)
        self.assertEqual(resolve_runtime_migration_targets(document,'legacy.old'),['legacy.new'])

    def test_missing_review_unknown_cycles_and_required_behavior_are_rejected(self):
        for fault in ('review','date','future','reason','missing','duplicate','unknown','claim','metric','weaken',
                      'cycle','pending','unregistered','missing-claim','own-tests','delete-required'):
            with self.subTest(fault=fault):
                document,registry=fixture();item=document['requirements']['legacy.old'];review=item['review'];row=review['coverage'][0]
                if fault=='review':review['reviewer']=''
                elif fault=='date':review['reviewedAt']='not-date'
                elif fault=='future':review['reviewedAt']='9999-01-01'
                elif fault=='reason':row['reason']=''
                elif fault=='missing':review['coverage']=[]
                elif fault=='duplicate':review['coverage'].append(deepcopy(row))
                elif fault=='unknown':row['replacementRequirement']='legacy.absent'
                elif fault=='claim':row['replacementClaim']='natural-input'
                elif fault=='metric':row['replacementMeasurement']='absent'
                elif fault=='weaken':
                    r=registry['measurementContracts']['legacy.new'];r['logical-commit'][0]['expected']=1
                    document['requirements']['legacy.new']['measurementContractSha256']=hashlib.sha256(
                        json.dumps(r,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                elif fault=='cycle':supersede(document,'new','old')
                elif fault=='pending':document['requirements']['legacy.new'].update(status='pending',tests=[])
                elif fault=='unregistered':registry['sharedTests'].pop('new')
                elif fault=='missing-claim':registry['sharedTests']['new']['claims']=[]
                elif fault=='own-tests':item['tests']=['old']
                elif fault=='delete-required':document['requirements'].pop('legacy.old')
                with self.assertRaises(ValidationFailure):validate_runtime_migration(document,registry)

    def test_obsolete_contract_is_retained_but_has_no_runtime_target(self):
        document, registry = fixture()
        obsolete(document, 'old')
        validate_runtime_migration(document, registry)
        self.assertEqual(resolve_runtime_migration_targets(document, 'legacy.old'), [])

    def test_obsolete_contract_requires_complete_distinct_evidence(self):
        for fault in ('review', 'date', 'future', 'evidence', 'duplicate', 'own-tests'):
            with self.subTest(fault=fault):
                document, registry = fixture()
                obsolete(document, 'old')
                item = document['requirements']['legacy.old']
                if fault == 'review': item['review']['currentContract'] = ''
                elif fault == 'date': item['review']['reviewedAt'] = 'bad-date'
                elif fault == 'future': item['review']['reviewedAt'] = '9999-01-01'
                elif fault == 'evidence': item['review']['evidence'] = ['one']
                elif fault == 'duplicate': item['review']['evidence'] = ['same', 'same']
                else: item['tests'] = ['old']
                with self.assertRaises(ValidationFailure):
                    validate_runtime_migration(document, registry)

    def test_current_catalog_unchanged_and_pending_ported_compatible(self):
        repo=Path(__file__).resolve().parents[2]
        document=json.loads((repo/'tools/overworld/runtime_proof_migration.json').read_text())
        registry=json.loads((repo/'tools/overworld/runtime_proof_registry.json').read_text())
        before=deepcopy(document)
        self.assertEqual(validate_runtime_migration(document,registry),before)
        self.assertFalse(any(v['status']=='superseded' for v in document['requirements'].values()))
        self.assertEqual([key for key,value in document['requirements'].items()
                         if value['status']=='obsolete'],
                         ['legacy.acceleration-parity',
                          'legacy.cyndaquil-step-taps',
                          'legacy.diagonal-turn-skid',
                          'legacy.mounted-diagonal-streaming',
                          'legacy.population-after-fast-travel',
                          'legacy.turn-skid',
                          'legacy.unmounted-failed-grass-scan-pacing',
                          'legacy.unmounted-follower-frame-cadence',
                          'legacy.unmounted-wild-frame-cadence',
                          'legacy.wild-ledge-reverse'])


if __name__=='__main__':unittest.main()

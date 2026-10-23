import copy
import json
import unittest
from ai.workflow.evidence import ingest_document, review_observation
from ai.workflow.forms import question_form, review_form
from ai.workflow.matching import match_form, review_matches
from ai.workflow.outcome import prepare_outcome, approve_outcome, export_preparation


REVIEW = {'reviewer': 'simulated-auditor', 'reason': 'Explicit simulated review', 'at': '2026-10-23T14:00:00+08:00'}


def scenario(question='Report Scope 2 emissions for 2026 in tCO2e.', *, end='2026-12-31', factor=True, activity_grid='peninsular'):
    form = question_form('q', question, {'boundary': {'organisation_id': 'demo-org', 'site_id': 'demo-site',
                        'consolidation_method': 'operational_control'}})
    form = review_form(form, decision='accept', **REVIEW)
    entry = {'organisation_id': 'demo-org', 'site_id': 'demo-site', 'consolidation_method': 'operational_control',
             'metric_id': 'electricity_consumption', 'value': '1000', 'unit': 'kWh', 'grid_region': activity_grid,
             'period': {'start': '2026-01-01', 'end': end}, 'location': {'page': 1, 'text': 'Staff estimate: 1000 kWh'}}
    row = ingest_document(b'SYNTHETIC staff assertion only', document_id='demo-staff', kind='staff_record', observations=[entry])['observations'][0]
    row = review_observation(row, decision='accept', **REVIEW)
    declarations = {'reviewed': True, 'factor_reviewed': True, 'factor_value': '0.740',
                    'factor_unit': 'kgCO2e/kWh', 'factor_vintage': '2024', 'grid_region': 'peninsular',
                    'factor_source': 'https://myenergystats.st.gov.my/documents/d/guest/grid-emission-factor-gef-in-malaysia-2022-2024-provisional-',
                    'accounting_method': 'location_based', 'provisional': True, 'factor_site_ids': ['demo-site'],
                    'factor_selection_justification': 'DEMO ONLY: explicitly use 2024 vintage for fictional 2026 estimate; not a 2026 factor.'} if factor else {}
    bundle = review_matches(match_form(form, [row], declarations), decision='accept', **REVIEW)
    return prepare_outcome(bundle)


class OutcomeTests(unittest.TestCase):
    def test_scope2_calculation_keeps_unverified_source(self):
        outcome = scenario()
        row = outcome['rows'][0]
        self.assertEqual(row['value'], '0.740')
        self.assertEqual(row['state'], 'calculated_candidate')
        self.assertIn('source_not_independently_corroborated', row['issues'])
        self.assertFalse(row['is_verified_disclosure'])

    def test_missing_factor_or_partial_year_blocks_calculation(self):
        for outcome in (scenario(factor=False), scenario(end='2026-09-30')):
            self.assertIsNone(outcome['rows'][0]['value'])

    def test_wrong_or_unconfirmed_activity_grid_blocks_factor_application(self):
        for grid in ('sabah', None):
            outcome = scenario(activity_grid=grid)
            self.assertIsNone(outcome['rows'][0]['value'])
            self.assertIn('calculation_coverage_or_factor_review_required', outcome['rows'][0]['issues'])

    def test_non_emissions_only_converts_without_emissions_factor(self):
        row = scenario('Report electricity consumption for 2026 in MWh.', factor=False)['rows'][0]
        self.assertEqual(row['value'], '1')
        self.assertIsNone(row['calculation'])

    def test_no_silent_export_or_hidden_gaps(self):
        outcome = scenario()
        with self.assertRaises(ValueError):
            export_preparation(outcome)
        with self.assertRaises(ValueError):
            approve_outcome(outcome, acknowledged_requirements=[], **REVIEW)
        approved = approve_outcome(outcome, acknowledged_requirements=['q-r1'], **REVIEW)
        self.assertEqual(json.loads(export_preparation(approved))['purpose'], 'preparation_only')
        changed = copy.deepcopy(approved)
        changed['rows'][0]['value'] = '0'
        with self.assertRaises(ValueError):
            export_preparation(changed)
        changed = copy.deepcopy(approved)
        changed['audit'][0]['actor'] = 'someone-else'
        with self.assertRaises(ValueError):
            export_preparation(changed)

    def test_missing_value_remains_null_after_approval(self):
        outcome = scenario(factor=False)
        approved = approve_outcome(outcome, acknowledged_requirements=['q-r1'], **REVIEW)
        self.assertIsNone(json.loads(export_preparation(approved))['rows'][0]['value'])

    def test_gaps_cannot_be_removed_between_preparation_and_approval(self):
        outcome = scenario(factor=False)
        outcome['rows'][0]['issues'] = []
        outcome['rows'][0]['value'] = '0'
        with self.assertRaises(ValueError):
            approve_outcome(outcome, acknowledged_requirements=[], **REVIEW)

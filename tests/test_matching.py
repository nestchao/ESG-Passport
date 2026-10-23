import copy
import unittest
from ai.workflow.evidence import ingest_document, review_observation
from ai.workflow.forms import question_form, review_form
from ai.workflow.matching import match_form, review_matches


def reviewed_fixture():
    form = question_form('q', 'Report electricity consumption for 2026 in kWh.', {'boundary': {
        'organisation_id': 'demo-org', 'site_id': 'demo-site', 'consolidation_method': 'operational_control'}})
    review = {'reviewer': 'demo', 'decision': 'accept', 'reason': 'Synthetic review', 'at': '2026-10-23'}
    form = review_form(form, **review)
    row = {'organisation_id': 'demo-org', 'site_id': 'demo-site', 'metric_id': 'electricity_consumption',
           'value': '120', 'unit': 'kWh', 'period': {'start': '2026-01-01', 'end': '2026-12-31'},
           'consolidation_method': 'operational_control', 'location': {'page': 1, 'text': 'Estimated 120 kWh'}}
    row = ingest_document(b'SYNTHETIC STAFF ENTRY', document_id='d', kind='staff_record', observations=[row])['observations'][0]
    return form, [review_observation(row, **review)]


class MatchingTests(unittest.TestCase):
    def test_staff_assertion_stays_partial_with_traceable_candidate(self):
        form, rows = reviewed_fixture()
        match = match_form(form, rows)['payload']['matches'][0]
        self.assertEqual(match['state'], 'partial')
        self.assertEqual(match['normalized_candidate_total'], '120000')
        self.assertEqual(match['evidence'][0]['source_status'], 'self_declared')

    def test_changed_value_invalidates_evidence_review(self):
        form, rows = reviewed_fixture()
        rows[0]['value'] = '999'
        with self.assertRaises(ValueError):
            match_form(form, rows)

    def test_missing_and_changed_match_require_attention(self):
        form, _ = reviewed_fixture()
        bundle = match_form(form, [])
        self.assertEqual(bundle['payload']['matches'][0]['priority'], 'P1')
        changed = copy.deepcopy(bundle)
        changed['payload']['matches'][0]['state'] = 'direct_evidence'
        with self.assertRaises(ValueError):
            review_matches(changed, reviewer='demo', decision='accept', reason='x', at='2026-10-23')

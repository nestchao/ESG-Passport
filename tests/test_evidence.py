import unittest
from ai.workflow.evidence import ingest_document, review_observation, review_priority


class EvidenceTests(unittest.TestCase):
    def row(self):
        return {'metric_id': 'electricity_consumption', 'value': '120', 'unit': 'kWh',
                'organisation_id': 'fictional-org', 'period': {'start': '2026-01-01', 'end': '2026-01-31'},
                'location': {'page': 1, 'text': 'Electricity consumed: 120 kWh'}}

    def test_untrusted_review_flags_are_reset_and_logo_does_not_authenticate(self):
        row = self.row() | {'reviewed': True, 'source_status': 'verified', 'logo': 'familiar'}
        result = ingest_document(b'fictional', document_id='d', kind='receipt', observations=[row])['observations'][0]
        self.assertFalse(result['reviewed'])
        self.assertEqual(result['source_status'], 'unverified_upload')

    def test_manual_record_remains_low_strength_after_acceptance(self):
        record = ingest_document(b'fictional staff entry', document_id='s', kind='staff_record', observations=[self.row()])['observations'][0]
        accepted = review_observation(record, reviewer='demo-auditor', decision='accept', reason='Transcription checked; no supporting bill', at='2026-10-23T12:00:00+08:00')
        self.assertEqual(accepted['evidence_strength'], 'low')
        self.assertEqual(accepted['source_status'], 'self_declared')
        self.assertEqual(review_priority(accepted)['priority'], 'P2')

    def test_disagreement_prioritised_even_with_logo(self):
        self.assertEqual(review_priority({'logo': 'familiar', 'conflicts': ['kWh']})['priority'], 'P1')

    def test_invalid_quantity_or_missing_provenance_rejected(self):
        for extra in ({'value': 'NaN'}, {'location': {}}, {'period': {'start': '2026-02-01', 'end': '2026-01-01'}}):
            with self.assertRaises(ValueError):
                ingest_document(b'x', document_id='d', kind='bill', observations=[self.row() | extra])

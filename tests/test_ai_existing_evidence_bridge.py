"""Evidence checks stay advisory inside existing questionnaire responses."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'backend'))
from esg_backend.ai_evidence import normalize_confirmed_activities, existing_question_coverage, question_period

class ExistingEvidenceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {'id':'water-1','file_hash':'a'*64,'confirmed':True,'archived':False,
             'activities':[{'id':'a1','category':'water','quantity':'10','unit':'m3',
                            'period_start':'2026-09-01','period_end':'2026-09-30',
                            'confirmed_by':'Clerk','confirmed_at':'2026-10-01T09:00:00Z'}]},
            {'id':'water-unconfirmed','file_hash':'b'*64,'confirmed':False,'archived':False,
             'activities':[{'id':'a2','category':'water','quantity':'20','unit':'m3',
                            'period_start':'2026-09-01','period_end':'2026-09-30'}]},
        ]
    def test_confirmed_only_and_no_source_claim(self):
        observations=normalize_confirmed_activities(self.documents,'lim-carton')
        self.assertEqual(len(observations),1)
        self.assertEqual(observations[0]['metric_id'],'water_withdrawal')
        self.assertEqual(observations[0]['source_status'],'unverified_upload')
        self.assertEqual(observations[0]['review']['decision'],'accept')
        self.assertEqual(observations[0]['review_priority']['priority'],'P2')
        self.assertFalse(observations[0]['covers_organisation_boundary'])
    def test_september_no_false_date_gap(self):
        observations=normalize_confirmed_activities(self.documents,'lim-carton')
        q={'id':'q1','text':'How much water did your company withdraw during September 2026?',
           'codes':['E3.1'],'reviewed':True,'manual_answer':None,
           'reviewed_by':'Clerk','reviewed_at':'2026-10-03T09:00:00Z'}
        note=existing_question_coverage(q,observations,'lim-carton','2026-09')
        self.assertIn('E3.1 partial',note)
        self.assertIn('company_site_coverage_unconfirmed',note)
        self.assertIn('water_source_applicability_unconfirmed',note)
        self.assertIn('source_not_independently_corroborated',note)
        self.assertNotIn('partial_period_coverage',note)
        self.assertIn('not independently verified',note)
    def test_unreviewed_or_manual_not_modified(self):
        observations=normalize_confirmed_activities(self.documents,'lim-carton')
        q={'id':'q1','text':'How much water did your company withdraw?',
           'codes':['E3.1'],'reviewed':False,'manual_answer':None}
        self.assertEqual(existing_question_coverage(q,observations,'lim-carton','2026-09'),'')
        q.update(reviewed=True,manual_answer='Owner statement')
        self.assertEqual(existing_question_coverage(q,observations,'lim-carton','2026-09'),'')
    def test_annual_query_not_reduced_to_month(self):
        self.assertEqual(question_period('Water withdrawn in 2026',
            {'start':'2026-01-01','end':'2026-12-31'},[], '2026-09'),
            {'start':'2026-01-01','end':'2026-12-31'})
    def test_cross_month_allocation_not_counted(self):
        doc=self.documents[0].copy()
        doc['activities']=[{**self.documents[0]['activities'][0], 'period_end':'2026-10-03', 'allocated_period':'2026-09'}]
        self.assertEqual(normalize_confirmed_activities([doc],'lim-carton'),[])

    def test_missing_confirmation_identity_cannot_count_as_review(self):
        doc = self.documents[0].copy()
        doc['activities'] = [{**self.documents[0]['activities'][0], 'confirmed_by': ''}]
        records = normalize_confirmed_activities([doc], 'lim-carton')
        self.assertFalse(records[0]['reviewed'])
        self.assertIsNone(records[0]['review'])
        self.assertEqual(records[0]['review_priority']['priority'], 'P2')
        q = {'id': 'q1', 'text': 'Water withdrawn during September 2026',
             'codes': ['E3.1'], 'reviewed': True, 'manual_answer': None,
             'reviewed_by':'Clerk','reviewed_at':'2026-10-03T09:00:00Z'}
        self.assertIn('evidence_review_or_provenance_required',
                      existing_question_coverage(q, records, 'lim-carton', '2026-09'))

import unittest
from ai.workflow.demo import run_demo


class DemoTests(unittest.TestCase):
    def test_published_fixture_survives_all_four_stages_without_filling_gaps(self):
        demo = run_demo()
        self.assertEqual(demo['model_calls'], 0)
        self.assertTrue(demo['synthetic'])
        self.assertEqual(len(demo['preparations']), 5)
        self.assertEqual(len(demo['manual_only_assertions']), 3)
        for preparation in demo['preparations']:
            self.assertIsNotNone(preparation['approval'])
            self.assertFalse(preparation['rows'][0]['is_verified_disclosure'])
            self.assertNotEqual(preparation['rows'][0]['state'], 'direct_evidence')
        scope2 = demo['preparations'][1]['rows'][0]
        self.assertIsNone(scope2['value'])
        self.assertIn('partial_period_coverage', scope2['issues'])
        self.assertEqual(demo['preparations'][3]['rows'][0]['state'], 'missing')

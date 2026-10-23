"""Smoke checks for the offline mapper bridge used by Customer requests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src' / 'backend'))
from esg_backend.ai_mapping import suggest_reviewed_codes

class FrontendMappingBridgeTests(unittest.TestCase):
    def check(self, text, expected):
        result = suggest_reviewed_codes('test', text)
        self.assertEqual(result['codes'], expected)
        self.assertIn('confirm', result['uncertainty'].lower())

    def test_scope2(self):
        self.check('Please disclose Scope 2 emissions from purchased electricity.', ['E1.2'])

    def test_malay_scope2(self):
        self.check('Berapa jumlah pelepasan skop 2 daripada elektrik grid?', ['E1.2'])

    def test_purchased_water_legacy_compatibility(self):
        self.check('State your purchased water volume.', ['E3.1'])

    def test_governance_legacy(self):
        self.check('How many directors are on the board?', ['G1.1'])

    def test_scope3_stays_unsupported(self):
        self.check('What were your Scope 3 emissions?', [])

    def test_ambiguous_water_stays_unmapped(self):
        self.check('How much water was consumed?', [])

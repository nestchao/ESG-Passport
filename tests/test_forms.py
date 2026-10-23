import copy
import unittest
from ai.workflow.forms import question_form, review_form, require_reviewed_form


class FormTests(unittest.TestCase):
    def test_highlights_are_exact_original_offsets(self):
        form = question_form('q', 'Report electricity consumption in 2026 in kWh.')
        self.assertTrue(form['highlights'])
        for cue in form['highlights']:
            self.assertEqual(form['mapping']['original_text'][cue['start']:cue['end']], cue['text'])

    def test_edit_invalidates_review_and_unsupported_cannot_be_accepted(self):
        form = review_form(question_form('q', 'Report electricity consumption in 2026 in kWh.'),
                           reviewer='demo', decision='accept', reason='Question checked', at='2026-10-23')
        self.assertTrue(require_reviewed_form(form))
        edited = copy.deepcopy(form)
        edited['mapping']['requirements'][0]['boundary']['organisation_id'] = 'different-org'
        with self.assertRaises(ValueError):
            require_reviewed_form(edited)
        with self.assertRaises(ValueError):
            review_form(question_form('q', 'Report injuries in 2026.'), reviewer='demo', decision='accept', reason='Checked', at='2026-10-23')

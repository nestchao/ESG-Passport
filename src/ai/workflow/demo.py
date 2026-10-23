"""Offline synthetic walkthrough. Every reviewer action below is simulated."""
import json
from pathlib import Path
from .evidence import ingest_document, review_observation
from .forms import question_form, review_form
from .matching import match_form, review_matches
from .outcome import prepare_outcome, approve_outcome, export_preparation


def run_demo():
    folder = Path(__file__).resolve().parent / 'fixtures' / 'staff_records'
    labels = json.loads((folder / 'labels.json').read_text(encoding='utf-8'))
    content = (folder / labels['document']).read_bytes()
    text = content.decode('utf-8')
    observations = []
    for item in labels['observations']:
        if item['location']['text'] not in text:
            raise ValueError('Fixture label text does not occur in the fictional source')
        observations.append({key: labels[key] for key in ('organisation_id', 'site_id', 'consolidation_method', 'period')} | item)
    rows = ingest_document(content, document_id='synthetic-staff-register', kind='staff_record', observations=observations)['observations']
    review = {'reviewer': 'SIMULATED-reviewer', 'reason': 'DEMO transcription review only; no source corroboration',
              'at': '2026-10-23T14:00:00+08:00'}
    rows = [review_observation(row, decision='accept', **review) for row in rows]
    context = {'boundary': {key: labels[key] for key in ('organisation_id', 'site_id', 'consolidation_method')}}
    questions = [
        'Report electricity consumption for 2026 in kWh.',
        'Report Scope 2 emissions for 2026 in tCO2e.',
        'Report water withdrawn for 2026 in litres.',
        'Report Scope 1 emissions for 2026 in tCO2e.',
        'Report waste generated for 2026 in tonnes.'
    ]
    exports = []
    for number, question in enumerate(questions, 1):
        form = review_form(question_form(f'demo-q{number}', question, context), decision='accept', **review)
        bundle = review_matches(match_form(form, rows), decision='accept', **review)
        outcome = prepare_outcome(bundle)
        approved = approve_outcome(outcome, acknowledged_requirements=[row['requirement_id'] for row in outcome['rows']], **review)
        exports.append(json.loads(export_preparation(approved)))
    return {'synthetic': True, 'review_actions_simulated': True, 'model_calls': 0,
            'notice': 'Annual requirements deliberately exceed staff-record period; gaps stay visible.',
            'manual_only_assertions': labels['manual_only_assertions'], 'preparations': exports}


if __name__ == '__main__':
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))

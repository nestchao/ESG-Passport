"""Stage 2: editable requirement forms and review snapshots."""
from copy import deepcopy
import hashlib
import json
import re
from .mapping import map_question, validate_result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def question_form(question_id, text, context=None):
    mapping = map_question(question_id, text, context)
    pattern = r'\b(?:SEDG[- ]?)?[ESG]\d+\.\d+\b|\b(?:scope|skop)\s*[123]\b|\b(?:electricity|energy|fuel|diesel|water|withdrawn|waste|generated|diverted|disposal|elektrik|tenaga|bahan api|pengambilan|air|sisa|dijana|dilupus\w*|kWh|MWh|litres?|m3|kg|tonnes?|tCO2e|20\d{2})\b'
    highlights = [{'start': m.start(), 'end': m.end(), 'text': m.group(), 'role': 'review_cue'}
                  for m in re.finditer(pattern, text, re.I)]
    return {'mapping': mapping, 'highlights': highlights, 'review': None,
            'editable_fields': ['sedg_code', 'metric_id', 'requested_unit', 'target_period', 'boundary', 'required_breakdowns'],
            'notice': 'Cues are not verified semantic explanations. Review each requirement against the original question.'}


def review_form(form, *, reviewer, decision, reason, at):
    if decision not in ('accept', 'reject') or not all((reviewer, reason, at)):
        raise ValueError('Explicit reviewer, decision, reason and timestamp required')
    result = deepcopy(form)
    validate_result(result['mapping'])
    if decision == 'accept' and (result['mapping']['mapping_status'] != 'mapped' or not result['mapping']['requirements']):
        raise ValueError('Unresolved/unsupported mapping needs correction or manual handling')
    result['review'] = {'reviewer': reviewer, 'decision': decision, 'reason': reason, 'at': at,
                        'mapping_sha256': fingerprint(result['mapping'])}
    return result


def require_reviewed_form(form):
    review = form.get('review') or {}
    validate_result(form['mapping'])
    if review.get('decision') != 'accept' or not review.get('reviewer') or review.get('mapping_sha256') != fingerprint(form['mapping']):
        raise ValueError('Accepted requirement review is missing or stale')
    return form['mapping']['requirements']

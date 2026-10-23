"""Stage 3: deterministic matches, explicit gaps and review priority."""
from copy import deepcopy
from .coverage import assess_coverage
from .evidence import observation_fingerprint, review_priority
from .forms import require_reviewed_form, fingerprint


def match_form(form, observations, declarations=None):
    requirements = require_reviewed_form(form)
    declarations = deepcopy(declarations or {})
    seen = set()
    for row in observations:
        if row['evidence_id'] in seen:
            raise ValueError('Evidence IDs must be unique')
        seen.add(row['evidence_id'])
        review = row.get('review') or {}
        if row.get('reviewed') and (review.get('decision') != 'accept' or
                not review.get('reviewer') or review.get('observation_sha256') != observation_fingerprint(row)):
            raise ValueError('Evidence review missing or stale')
    matches = []
    lookup = {row['evidence_id']: row for row in observations}
    for req in requirements:
        result = assess_coverage(req, observations, declarations)
        selected = [lookup[key] for key in result['evidence_ids']]
        weak = [row['evidence_id'] for row in selected if row.get('source_status') != 'verified_acquisition']
        if weak:
            result['issues'].append('source_not_independently_corroborated')
            if result['state'] == 'direct_evidence':
                result['state'] = 'partial'
        result['source_limitations'] = weak
        result['evidence'] = [{'evidence_id': row['evidence_id'], 'document_sha256': row['document_sha256'],
                              'location': row.get('location'), 'value': row['value'], 'unit': row['unit'],
                              'period': row['period'], 'synthetic': row.get('synthetic'),
                              'site_id': row.get('site_id'), 'grid_region': row.get('grid_region'),
                              'source_status': row.get('source_status'), 'evidence_strength': row.get('evidence_strength'),
                              'review_priority': review_priority(row)} for row in selected]
        result['priority'] = 'P1' if result['state'] in ('missing', 'manual_review') or any(
            issue in result['issues'] for issue in ('partial_period_coverage', 'company_site_coverage_unconfirmed')) else 'P2'
        matches.append(result)
    payload = {'mapping': deepcopy(form['mapping']), 'observations': deepcopy(observations),
               'declarations': declarations, 'matches': matches}
    return {'payload': payload, 'snapshot_sha256': fingerprint(payload), 'decision': None}


def review_matches(bundle, *, reviewer, decision, reason, at):
    if decision not in ('accept', 'reject') or not all((reviewer, reason, at)):
        raise ValueError('Explicit reviewer, decision, reason and timestamp required')
    if bundle['snapshot_sha256'] != fingerprint(bundle['payload']):
        raise ValueError('Match snapshot changed; rematch required')
    result = deepcopy(bundle)
    result['decision'] = {'reviewer': reviewer, 'decision': decision, 'reason': reason, 'at': at,
                          'snapshot_sha256': bundle['snapshot_sha256']}
    return result

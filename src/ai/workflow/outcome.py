"""Stage 4: controlled calculation, gap-preserving approval and preparation export."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import re
from .coverage import UNIT
from .forms import fingerprint


def checked_bundle(bundle):
    if fingerprint(bundle['payload']) != bundle['snapshot_sha256']:
        raise ValueError('Matching inputs changed')
    decision = bundle.get('decision') or {}
    if decision.get('decision') != 'accept' or not decision.get('reviewer') or decision.get('snapshot_sha256') != bundle['snapshot_sha256']:
        raise ValueError('Accepted matching decision required')


def prepare_outcome(bundle):
    checked_bundle(bundle)
    payload = bundle['payload']
    requirements = {r['requirement_id']: r for r in payload['mapping']['requirements']}
    declarations = payload['declarations']
    rows = []
    for match in payload['matches']:
        req = requirements[match['requirement_id']]
        row = {'requirement_id': req['requirement_id'], 'sedg_code': req['sedg_code'],
               'metric_id': req['metric_id'], 'boundary': req['boundary'], 'period': req['target_period'],
               'value': None, 'unit': req['requested_unit'], 'state': match['state'],
               'issues': list(match['issues']), 'priority': match['priority'],
               'evidence': deepcopy(match['evidence']), 'calculation': None,
               'is_verified_disclosure': False}
        if match.get('normalized_candidate_total') is not None:
            target = UNIT.get(req['requested_unit'])
            base = UNIT.get(match['candidate_unit'])
            if target and base and target[0] == base[0]:
                row['value'] = str(Decimal(match['normalized_candidate_total']) * base[1] / target[1])
            else:
                row['issues'].append('requested_unit_conversion_unavailable')
        if req['sedg_code'] == 'E1.2' and match.get('readiness') == 'inputs_ready':
            # A matching review alone cannot authorise calculation across missing periods,
            # sites or unresolved source streams. Source weakness remains visible.
            allowed = {'scope2_factor_application_required', 'source_not_independently_corroborated'}
            factor_year = str(declarations.get('factor_vintage', ''))
            period = req['target_period']
            sites = {e.get('site_id') for e in row['evidence']}
            region_valid = (bool(sites) and None not in sites and
                            sites.issubset(set(declarations.get('factor_site_ids', []))) and
                            all(e.get('grid_region') == declarations.get('grid_region') for e in row['evidence']))
            factor_metadata_valid = (re.fullmatch(r'20\d{2}', factor_year) and
                                     period['start'][:4] == period['end'][:4] and
                                     factor_year <= period['end'][:4] and
                                     declarations.get('reviewed') is True and
                                     declarations.get('factor_reviewed') is True and region_valid)
            if set(row['issues']) <= allowed and factor_metadata_valid:
                try:
                    factor = Decimal(str(declarations['factor_value']))
                    if not factor.is_finite() or factor < 0:
                        raise ValueError()
                    activity_kwh = sum((Decimal(e['value']) * UNIT[e['unit']][1] / Decimal(1000)
                                        for e in row['evidence']), Decimal(0))
                    tonnes = activity_kwh * factor
                    if declarations['factor_unit'] == 'kgCO2e/kWh':
                        tonnes /= Decimal(1000)
                    if req['requested_unit'] not in ('tCO2e', 'kgCO2e'):
                        raise ValueError()
                    row.update(value=str(tonnes if req['requested_unit'] == 'tCO2e' else tonnes * 1000),
                               unit=req['requested_unit'], state='calculated_candidate',
                               calculation={'method': 'location_based_grid_activity_times_factor',
                                            'activity_kwh': str(activity_kwh), 'factor': deepcopy(declarations)})
                    row['issues'].remove('scope2_factor_application_required')
                except (ValueError, KeyError, InvalidOperation):
                    row['issues'].append('calculation_input_review_required')
            else:
                row['issues'].append('calculation_coverage_or_factor_review_required')
        # Scope 1 and fuel-energy conversion remain explicit gaps, never guessed.
        row['issues'] = list(dict.fromkeys(row['issues']))
        row['quality'] = 'unverified_candidate' if row['value'] is not None else 'unresolved'
        rows.append(row)
    result = {'schema_version': '1.0', 'purpose': 'preparation_only',
              'mapping_snapshot': deepcopy(payload['mapping']),
              'match_snapshot_sha256': bundle['snapshot_sha256'],
              'match_decision': deepcopy(bundle['decision']),
              'rows': rows, 'approval': None, 'audit': []}
    append_event(result, 'preparation_created', bundle['decision']['reviewer'], bundle['decision']['at'],
                 {'match_snapshot_sha256': bundle['snapshot_sha256'], 'rows_sha256': fingerprint(rows),
                  'payload_sha256': fingerprint(approval_payload(result))})
    return result


def append_event(outcome, action, actor, at, details):
    event = {'sequence': len(outcome['audit']) + 1, 'action': action, 'actor': actor, 'at': at,
             'details': details, 'previous_sha256': outcome['audit'][-1]['sha256'] if outcome['audit'] else None}
    event['sha256'] = fingerprint(event)
    outcome['audit'].append(event)


def approval_payload(outcome):
    return {key: value for key, value in outcome.items() if key not in ('approval', 'audit')}


def approve_outcome(outcome, *, reviewer, reason, at, acknowledged_requirements):
    if not all((reviewer, reason, at)):
        raise ValueError('Explicit final reviewer, reason and timestamp required')
    if not outcome.get('audit') or outcome['audit'][0]['details'].get('payload_sha256') != fingerprint(approval_payload(outcome)):
        raise ValueError('Preparation changed; review inputs and regenerate before approval')
    unresolved = {r['requirement_id'] for r in outcome['rows'] if r['issues'] or r['value'] is None}
    if not unresolved.issubset(set(acknowledged_requirements)):
        raise ValueError('Every outstanding limitation/gap must be explicitly acknowledged')
    result = deepcopy(outcome)
    result['approval'] = {'reviewer': reviewer, 'reason': reason, 'at': at,
                          'acknowledged_requirements': sorted(set(acknowledged_requirements)),
                          'payload_sha256': fingerprint(approval_payload(result))}
    append_event(result, 'preparation_approved', reviewer, at, deepcopy(result['approval']))
    return result


def export_preparation(outcome):
    approval = outcome.get('approval') or {}
    if not approval.get('reviewer') or approval.get('payload_sha256') != fingerprint(approval_payload(outcome)):
        raise ValueError('Final approval is missing or stale')
    if not outcome.get('audit') or outcome['audit'][0]['details'].get('payload_sha256') != fingerprint(approval_payload(outcome)):
        raise ValueError('Preparation snapshot changed')
    previous = None
    for event in outcome['audit']:
        if event['previous_sha256'] != previous or event['sha256'] != fingerprint({k: v for k, v in event.items() if k != 'sha256'}):
            raise ValueError('Audit record changed')
        previous = event['sha256']
    if not outcome['audit'] or outcome['audit'][-1]['action'] != 'preparation_approved' or outcome['audit'][-1]['details'] != approval:
        raise ValueError('Final approval audit record required')
    return json.dumps(outcome, ensure_ascii=False, indent=2, allow_nan=False) + '\n'

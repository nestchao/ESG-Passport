"""Read-only adapter from existing confirmed activities to the PR #9 coverage rules.

Coverage checks are advisory only; they never change the original rule-based
profile, stored records, owner reviews, or approved snapshots.
"""
from calendar import monthrange
from datetime import date
from pathlib import Path
import re
import sys

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ai.workflow.coverage import assess_coverage
from ai.workflow.mapping import map_question
from ai.workflow.evidence import review_observation, review_priority

CATEGORIES = {
    'electricity': 'electricity_consumption', 'diesel': 'fuel_consumed',
    'petrol': 'fuel_consumed', 'water': 'water_withdrawal',
    'waste_generated': 'waste_generated', 'waste_diverted': 'waste_diverted',
    'waste_disposed': 'waste_disposed',
}
SUPPORTED = frozenset(('E1.1', 'E1.2', 'E2.1', 'E3.1', 'E4.1'))
MONTHS = {name.lower(): number for number, name in enumerate(
    ('January', 'February', 'March', 'April', 'May', 'June',
     'July', 'August', 'September', 'October', 'November', 'December'), 1)}


def normalize_confirmed_activities(documents, company_id):
    """Only latest confirmed, active activity values, with unknown metadata left unknown."""
    observations = []
    for doc in documents:
        if not doc.get('confirmed') or doc.get('archived'):
            continue
        for activity in doc.get('activities') or []:
            metric = CATEGORIES.get(activity.get('category'))
            if not metric or activity.get('quantity') is None:
                continue
            start, end = activity.get('period_start'), activity.get('period_end')
            if not start or not end:
                continue
            # Cross-month allocations require a separate reviewed allocation model;
            # never present the full original amount as a monthly observation.
            if activity.get('allocated_period') or str(start)[:7] != str(end)[:7]:
                continue
            unit = activity.get('unit')
            if unit == 'm³':
                unit = 'm3'
            observation = {
                'evidence_id': f"{doc['id']}:{activity.get('id', metric)}",
                'document_id': doc['id'], 'document_sha256': doc.get('file_hash') or '',
                'metric_id': metric, 'value': activity['quantity'], 'unit': unit,
                'period': {'start': str(start), 'end': str(end)},
                'organisation_id': company_id, 'site_id': None, 'source': None,
                'covers_organisation_boundary': False, 'consolidation_method': None,
                'reviewed': False, 'review': None,
                'source_status': 'unverified_upload', 'evidence_strength': 'unassessed',
            }
            observation['review_priority'] = review_priority(observation)
            # Existing clerk confirmation can be recorded as an explicit FIELD
            # review when its reviewer and timestamp are available. It does not
            # independently authenticate the source bill.
            reviewer, confirmed_at = activity.get('confirmed_by'), activity.get('confirmed_at')
            if reviewer and confirmed_at:
                observation = review_observation(observation, reviewer=reviewer,
                    decision='accept', reason='Existing confirmed activity', at=str(confirmed_at))
            observations.append(observation)
    return observations


def question_period(text, mapped, missing, default_month):
    # Keep explicit day ranges and fiscal/multiple periods unchanged.
    if re.search(r'\b(?:FY\s*20\d{2}|financial year|fiscal year)\b', text, re.I):
        return mapped
    if re.search(r'\b20\d{2}-\d{2}-\d{2}\b', text):
        return mapped
    named = list(re.finditer(r'\b(' + '|'.join(MONTHS) + r')\s+(20\d{2})\b', text, re.I))
    numeric = list(re.finditer(r'\b(20\d{2})-(0[1-9]|1[0-2])\b', text))
    if len(named) + len(numeric) == 1:
        if named:
            year, month = int(named[0].group(2)), MONTHS[named[0].group(1).lower()]
        else:
            year, month = int(numeric[0].group(1)), int(numeric[0].group(2))
        return {'start': f'{year:04d}-{month:02d}-01',
                'end': f'{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}'}
    if len(named) + len(numeric) > 1:
        return {'start': None, 'end': None}
    if mapped.get('start') is None and 'reporting_period_required' in missing:
        year, month = map(int, default_month.split('-'))
        return {'start': f'{year:04d}-{month:02d}-01',
                'end': f'{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}'}
    return mapped


def reviewed_pr9_form(question, company_id, reporting_month):
    """Bridge an explicit existing question review to PR #9's requirement form.

    Reject changed/ambiguous mappings instead of inventing a human review.
    """
    from ai.workflow.forms import question_form, review_form
    selected = set(question.get('codes') or ()) & SUPPORTED
    if (not selected or not question.get('reviewed') or question.get('manual_answer')
            or not question.get('reviewed_by') or not question.get('reviewed_at')):
        return None
    form = question_form(question['id'], question['text'], context={
        'boundary': {'organisation_id': company_id, 'site_id': None,
                     'consolidation_method': None}})
    mapped = form['mapping']
    if mapped['mapping_status'] != 'mapped' or set(mapped['codes']) != selected:
        return None
    for requirement in mapped['requirements']:
        requirement['target_period'] = question_period(
            question['text'], requirement['target_period'],
            requirement['missing_inputs'], reporting_month)
        if not requirement['target_period'].get('start'):
            return None
    return review_form(form, reviewer=question['reviewed_by'], decision='accept',
        reason='Existing explicit questionnaire code review; other inputs remain unverified',
        at=str(question['reviewed_at']))


def existing_question_coverage(question, observations, company_id, reporting_month):
    """PR #9 requirement and evidence matching in existing question review.

    Do not forge a match acceptance from merely viewing an answer.
    """
    selected = set(question.get('codes') or ()) & SUPPORTED
    if not question.get('reviewed') or question.get('manual_answer') or not selected:
        return ''
    from ai.workflow.matching import match_form
    try:
        form = reviewed_pr9_form(question, company_id, reporting_month)
        if form is None:
            return ('AI evidence readiness: existing question review does not establish '
                    'an accepted PR #9 requirement snapshot; manual verification required.')
        bundle = match_form(form, observations, declarations={})
    except (ValueError, KeyError, TypeError):
        return ('AI evidence readiness: PR #9 matching prerequisites are missing '
                'or stale; manual verification required.')
    # Use the code in the requirements, not a generated requirement-id prefix.
    lines = [f"{req['sedg_code']} {match['state']}: " +
             (', '.join(dict.fromkeys(match['issues'])) or 'independent source and completeness review required')
             for req, match in zip(form['mapping']['requirements'], bundle['payload']['matches'])]
    return ('AI evidence readiness (PR #9 matching preview; not independently verified): '
            + '; '.join(lines) + '. Existing calculated values are unchanged; owner verification required.')


def prepare_pr9_at_owner_approval(question, observations, company_id, reporting_month, owner, at):
    """Generate a PR #9 preparation for the existing Approve & Share flow.

    The caller MUST explicitly collect per-issue acknowledgement before calling
    approve_outcome. Never infer owner consent from a questionnaire code review.
    """
    from ai.workflow.matching import match_form, review_matches
    from ai.workflow.outcome import prepare_outcome
    if not (set(question.get('codes') or ()) & SUPPORTED) or question.get('manual_answer'):
        return None
    try:
        form = reviewed_pr9_form(question, company_id, reporting_month)
        if form is None:
            return {'question_id': question['id'], 'status': 'manual_review_required',
                    'issues': ['requirement_review_missing_or_changed'],
                    'requirements': [], 'unresolved_count': 1}
        bundle = match_form(form, observations, declarations={})
        # Match acceptance is performed only at the existing owner action;
        # it does NOT assert independently verified source authenticity.
        accepted = review_matches(bundle, reviewer=owner, decision='accept',
            reason='Owner initiated review of selected evidence for this customer pack', at=at)
        outcome = prepare_outcome(accepted)
        requirement_rows = []
        for record in outcome['rows']:
            issues = list(dict.fromkeys(record['issues']))
            if record['value'] is None and 'value_not_available' not in issues:
                issues.append('value_not_available')
            requirement_rows.append({'requirement_id': record['requirement_id'],
                'sedg_code': record['sedg_code'], 'issues': issues,
                'state': record['state']})
        return {'question_id': question['id'], 'status': 'preparation_only_unresolved',
                'issues': sorted({issue for record in requirement_rows for issue in record['issues']}),
                'requirements': requirement_rows,
                'requirement_count': len(outcome['rows']),
                'unresolved_count': sum(bool(record['issues']) for record in requirement_rows),
                '_outcome': outcome}
    except (ValueError, KeyError, TypeError):
        return {'question_id': question['id'], 'status': 'manual_review_required',
                'issues': ['preparation_prerequisites_missing_or_stale'],
                'requirements': [], 'unresolved_count': 1}


def pr9_acknowledgement_items(reviews):
    """Stable identifiers for EACH gap; never use guessed/derived consent."""
    items = []
    for review in reviews:
        for requirement in review.get('requirements', []):
            for issue in requirement['issues']:
                items.append({'id': f"{review['question_id']}::{requirement['requirement_id']}::{issue}",
                              'question_id': review['question_id'],
                              'requirement_id': requirement['requirement_id'],
                              'code': requirement['sedg_code'], 'issue': issue})
        if review['status'] == 'manual_review_required':
            for issue in review['issues']:
                items.append({'id': f"{review['question_id']}::manual::{issue}",
                              'question_id': review['question_id'],
                              'requirement_id': None, 'code': '', 'issue': issue})
    return sorted(items, key=lambda item: item['id'])

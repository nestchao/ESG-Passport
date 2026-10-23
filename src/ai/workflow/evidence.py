"""Stage 1: normalise saved OCR/manual inputs without claiming authenticity."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json


def observation_fingerprint(record):
    payload = {k: v for k, v in record.items() if k not in ('review', 'reviewed')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def ingest_document(content, *, document_id, kind, observations, synthetic=True):
    """Accept adapter output. OCR adapters must supply page/region text themselves.

    File identity is not authentication. Acquisition is unverified until a separate
    reviewer records corroboration. No filename, logo or model score upgrades it.
    """
    if kind not in ('receipt', 'bill', 'staff_record', 'document'):
        raise ValueError('Unknown document kind')
    if not isinstance(content, bytes) or not content or not document_id:
        raise ValueError('Nonempty bytes and document identity required')
    digest = hashlib.sha256(content).hexdigest()
    records = []
    for index, observation in enumerate(observations):
        row = deepcopy(observation)
        try:
            value = Decimal(str(row['value']))
            if not value.is_finite() or value < 0:
                raise ValueError()
            left, right = date.fromisoformat(row['period']['start']), date.fromisoformat(row['period']['end'])
            if left > right:
                raise ValueError()
            if not all(row.get(key) for key in ('metric_id', 'unit', 'organisation_id')):
                raise ValueError()
            provenance = row['location']
            if not provenance.get('text') or not isinstance(provenance.get('page'), int) or provenance['page'] < 1:
                raise ValueError()
        except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
            raise ValueError('Observation needs valid quantity, dates, boundary and source text/page') from exc
        extraction_status = row.get('extraction_status', 'manual_entry' if kind == 'staff_record' else 'uncertain')
        if extraction_status not in ('manual_entry', 'uncertain', 'disagreement', 'candidate'):
            raise ValueError('Extraction status must be an unreviewed adapter state')
        row.update(evidence_id=f'{document_id}:{index + 1}', document_id=document_id,
                   document_sha256=digest, document_kind=kind, synthetic=bool(synthetic),
                   reviewed=False, source_status='self_declared' if kind == 'staff_record' else 'unverified_upload',
                   evidence_strength='low' if kind == 'staff_record' else 'unassessed',
                   extraction_status=extraction_status, review=None)
        records.append(row)
    return {'document_id': document_id, 'sha256': digest, 'synthetic': bool(synthetic),
            'observations': records}


def review_priority(record):
    """Review urgency is separate from evidence strength; P1 is highest."""
    reasons = []
    if record.get('conflicts'):
        reasons.append('conflicting_fields')
    if record.get('boundary_conflict'):
        reasons.append('boundary_conflict')
    if not record.get('reviewed') and record.get('extraction_status') in ('uncertain', 'disagreement'):
        reasons.append('extraction_review_required')
    if reasons:
        return {'priority': 'P1', 'reasons': reasons}
    if record.get('source_status') in ('self_declared', 'unverified_upload'):
        reasons.append('source_not_corroborated')
    if not record.get('reviewed'):
        reasons.append('field_review_pending')
    return {'priority': 'P2' if reasons else 'P3', 'reasons': reasons or ['routine_review_available']}


def review_observation(record, *, reviewer, decision, reason, at):
    """Domain helper; the caller must enforce reviewer identity and permission."""
    if decision not in ('accept', 'reject') or not all((reviewer, reason, at)):
        raise ValueError('Reviewer, decision, reason and timestamp required')
    result = deepcopy(record)
    result['reviewed'] = decision == 'accept'
    result['review'] = {'reviewer': reviewer, 'decision': decision, 'reason': reason, 'at': at,
                        'observation_sha256': observation_fingerprint(result)}
    # Accepting a field does not authenticate its source or increase its strength.
    return result

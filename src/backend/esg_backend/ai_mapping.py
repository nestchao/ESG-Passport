"""Adapter: offline reviewed SEDG mapper -> existing questionnaire suggestion contract.

This does not wire OCR, evidence matching, or the offline approval/export engine.
No mapping from this adapter bypasses human review.
"""
from pathlib import Path
import sys
import re
from .rules import suggest_codes

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from ai.workflow.mapping import map_question

_BASIC = {'E1.1', 'E1.2', 'E2.1', 'E3.1', 'E4.1'}
_OWNER = {'S1.1', 'S4.1', 'G1.1', 'G2.1', 'G3.1', 'G4.1'}


def suggest_reviewed_codes(question_id: str, question_text: str) -> dict:
    mapped = map_question(question_id, question_text)
    # Use only supported, unambiguous mappings. Unsupported and candidate codes
    # remain unselected for manual review; never turn Scope 3 into Scope 2.
    basic = [c for c in mapped['codes'] if c in _BASIC and mapped['mapping_status'] == 'mapped']
    owner = [c for c in suggest_codes(question_text) if c in _OWNER]
    # Existing customer wording: an explicit PURCHASED water volume is a
    # withdrawal, but generic 'water consumed' is not necessarily withdrawal.
    if re.search(r'\bpurchased\s+water\b', question_text, re.I) and re.search(r'\b(volume|quantity|amount|litres?|m3)\b', question_text, re.I):
        basic.append('E3.1')
    codes = list(dict.fromkeys(basic + owner))
    issues = mapped.get('issues') or []
    candidates = mapped.get('candidate_codes') or []
    uncertain = mapped['mapping_status'] != 'mapped' or bool(issues or candidates)
    notes = ['Offline EN/BM SEDG rules; confirm the mapping and reporting period.']
    if mapped['mapping_status'] != 'mapped':
        notes.append('AI workflow status: ' + mapped['mapping_status'] + '.')
    if issues:
        notes.append('Review flags: ' + ', '.join(issues[:5]) + '.')
    if candidates:
        notes.append('Candidate codes not automatically selected: ' + ', '.join(candidates) + '.')
    # Surface the offline Stage-2 requirement checks in the EXISTING question
    # review uncertainty field; never silently fill or approve missing inputs.
    requirement_gaps = list(dict.fromkeys(
        gap for requirement in mapped.get('requirements', [])
        if requirement.get('sedg_code') in basic
        for gap in requirement.get('missing_inputs', [])))
    if requirement_gaps:
        notes.append('Required input checks: ' + ', '.join(requirement_gaps) + '.')
    if owner:
        notes.append('Social/Governance suggestions use the legacy matcher, not the new offline core.')
    return {
        'codes': codes,
        'confidence': 'Low' if not codes or uncertain else 'Medium',
        'rationale': 'Proposed by reviewed SEDG rules (offline EN/BM) with legacy Social/Governance fallback.',
        'uncertainty': ' '.join(notes) + ' No live OCR or independent verification is performed.',
    }

"""Deterministic, monthly disclosure rules. No inference or AI is used here."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re

from .ai_calculation import normalize_existing_quantity, factor_unit_compatible

TITLES = {'E1.1':'Direct emissions','E1.2':'Electricity emissions','E2.1':'Energy consumption','E3.1':'Water withdrawn','E4.1':'Waste management','S1.1':'Labour incidents','S4.1':'Health & safety','G1.1':'Company directors','G2.1':'Policies in place','G3.1':'Financial reporting','G4.1':'Corruption incidents'}
CODES = list(TITLES)
POLICIES = ('Code of Conduct','Anti-Corruption Policy','Whistleblowing Policy','Health and Safety Policy')

def _strings(value):
    if isinstance(value, Decimal):
        text=format(value,'f')
        return text.rstrip('0').rstrip('.') if '.' in text else text
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, dict): return {k:_strings(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [_strings(v) for v in value]
    return value

def _number(value):
    if isinstance(value, bool): raise ValueError('Quantity must be a finite non-negative decimal.')
    try: result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError): raise ValueError('Quantity must be a finite non-negative decimal.') from None
    if not result.is_finite() or result < 0: raise ValueError('Quantity must be a finite non-negative decimal.')
    return result

def _text(value):
    if value is None: return False
    if not isinstance(value, str): raise ValueError('Description must be text.')
    return bool(value.strip())

def validate_declaration(code, answer):
    """Return completeness; raise ValueError for a provided invalid field."""
    if code not in CODES[5:]: raise ValueError('Unsupported declaration code.')
    if not isinstance(answer, dict): raise ValueError('Answer must be an object.')
    fields = {'S1.1':('count',),'S4.1':('injuries','fatalities'),'G1.1':('directors',),'G3.1':('year',),'G4.1':('count',)}
    if code == 'G2.1':
        policies = answer.get('policies')
        if policies in (None, ''): return False
        if not isinstance(policies, list): raise ValueError('Policies must be a list.')
        seen = {}
        for p in policies:
            if not isinstance(p, dict): raise ValueError('Each policy must be an object.')
            name, status = p.get('name'), p.get('status')
            if name not in POLICIES or name in seen: raise ValueError('Unknown or duplicate policy.')
            if status not in (None, '', 'in place', 'not in place', 'unknown'): raise ValueError('Invalid policy status.')
            seen[name] = status
        return len(seen)==4 and all(v in ('in place','not in place') for v in seen.values())
    complete = True
    for field in fields[code]:
        value = answer.get(field)
        if value is None or value == '': complete = False; continue
        if type(value) is not int or value < 0: raise ValueError(f'{field} must be a non-negative integer.')
        if field == 'year' and not 1900 <= value <= datetime.now(timezone.utc).year: raise ValueError('Financial year is outside the valid range.')
    if code in ('S1.1','S4.1','G4.1'):
        description = _text(answer.get('description'))
        if any(type(answer.get(f)) is int and answer[f]>0 for f in fields[code]) and not description: complete=False
    return complete

def _unique(values): return list(dict.fromkeys(v for v in values if v))

def calculate_profile(company, documents, declarations, factors, period):
    """Calculate only confirmed quantities for the exact requested month."""
    factor_map = {f.get('key', str(f.get('id','')).removesuffix('-v1')):f for f in factors}
    categories = ('electricity','diesel','petrol','water','waste_generated','waste_diverted','waste_disposed')
    groups = {c:dict(rows=[], evidence=[], pending=False, encountered=False, estimated=False) for c in categories}
    for document in documents:
        activities = document.get('activities', [])
        if not activities and not document.get('confirmed') and document.get('period') == period:
            types = ['waste_generated','waste_diverted','waste_disposed'] if document.get('type')=='waste' else [document.get('type')]
            for category in types:
                if category in groups:
                    groups[category]['pending']=True; groups[category]['encountered']=True
                    groups[category]['evidence'].append(document.get('id'))
        for a in activities:
            category=a.get('category')
            if category not in groups: continue
            start,end=a.get('period_start',''),a.get('period_end','')
            allocated=a.get('allocated_period')
            crosses=start[:7]!=end[:7]
            relevant=allocated==period if allocated else start[:7]==period and end[:7]==period
            # An unallocated cross-month input overlapping the month blocks completeness.
            overlap=bool(start and end and start[:7]<=period<=end[:7])
            if not relevant and not (crosses and not allocated and overlap): continue
            group=groups[category]; group['encountered']=True; group['evidence'].append(document.get('id'))
            valid_allocation=not crosses or bool(allocated==period and a.get('estimated') and str(a.get('assumptions','')).strip())
            if not document.get('confirmed') or not relevant or not valid_allocation:
                group['pending']=True; continue
            quantity=_number(a.get('quantity'))
            allowed={'electricity':('kWh',),'diesel':('L',),'petrol':('L',),'water':('L','m3','m³'),'waste_generated':('kg','t'),'waste_diverted':('kg','t'),'waste_disposed':('kg','t')}
            if a.get('unit') not in allowed[category]: raise ValueError('Unsupported activity unit.')
            if category == 'water' or category.startswith('waste_'):
                quantity = normalize_existing_quantity(category, quantity, a['unit'])
            group['rows'].append((quantity,a,document))
            group['estimated'] |= bool(a.get('estimated') or crosses or allocated)
    for group in groups.values():
        group['value']=sum((r[0] for r in group['rows']),Decimal(0)) if group['rows'] else None
        group['missing']=group['pending'] or group['value'] is None
    metrics=[]

    def build(code, used, components, unit, method, required=None, factor_keys=(), proxy=False):
        used_groups=[groups[c] for c in used]
        required=used if required is None else required
        missing=any(groups[c]['missing'] for c in required) or any(c.get('value') is None for c in components)
        selected=[factor_map[k] for k in factor_keys if k in factor_map]
        missing |= len(selected)!=len(factor_keys) or any(
            not factor_unit_compatible(key, factor_map.get(key)) for key in factor_keys)
        value=None if missing else sum((c['value'] for c in components),Decimal(0))
        if code=='E4.1': value=None if missing else components[0]['value']
        estimated=proxy or any(g['estimated'] for g in used_groups) or any(f.get('estimated') for f in selected)
        badge='missing' if missing else 'estimated' if estimated else 'auto'
        rows=[r for g in used_groups for r in g['rows']]
        result=dict(code=code,title=TITLES[code],value=value,unit=unit,badge=badge,evidence_ids=_unique(i for g in used_groups for i in g['evidence']),method=method,factors=deepcopy(selected),components=components,complete=badge=='auto',confirmed_by=_unique(r[1].get('confirmed_by') for r in rows),confirmation_history=[dict(evidence_id=r[2].get('id'),category=r[1]['category'],confirmed_by=r[1].get('confirmed_by'),confirmed_at=r[1].get('confirmed_at'),assumptions=r[1].get('assumptions','')) for r in rows],calculation_version='rules-v1')
        metrics.append(_strings(result))

    def component(category, name, unit, factor=None):
        group=groups[category]; value=group['value']
        if factor:
            value=value*_number(factor_map[factor]['value']) if (
                value is not None and factor_unit_compatible(factor, factor_map.get(factor))) else None
        return dict(name=name,category=category,value=value,unit=unit,evidence_ids=_unique(group['evidence']),pending=group['pending'])

    fuels=[c for c in ('diesel','petrol') if groups[c]['encountered']]
    build('E1.1',fuels,[component(c,c.title(),'kg CO₂e',c) for c in fuels] or [dict(name='Fuel',value=None,unit='kg CO₂e')],'kg CO₂e','Confirmed litres × versioned mineral-fuel proxy. Monthly only; no annual extrapolation.',factor_keys=fuels,proxy=True)
    build('E1.2',['electricity'],[component('electricity','Electricity','kg CO₂e','grid')],'kg CO₂e','Confirmed kWh × versioned grid factor. Monthly only; no annual extrapolation.',factor_keys=['grid'])
    build('E2.1',['electricity']+fuels,[component('electricity','Electricity','kWh')]+[component(c,c.title(),'kWh',c+'-energy') for c in fuels],'kWh','Electricity plus encountered fuel energy. Fuel energy uses a versioned proxy; unavailable factors remain missing.',factor_keys=[c+'-energy' for c in fuels],proxy=bool(fuels))
    build('E3.1',['water'],[component('water','Water','L')],'L','Purchased water: m³ × 1,000 = litres; litres unchanged.')
    waste=['waste_generated','waste_diverted','waste_disposed']
    build('E4.1',waste,[component(c,c.replace('waste_',''),'t') for c in waste],'t','kg ÷ 1,000 = tonnes. Generated waste is not added to diverted or disposed waste.')
    for code in CODES[5:]:
        candidates=[(i,d) for i,d in enumerate(declarations) if d.get('code')==code and d.get('period')==period]
        declaration=max(candidates,key=lambda pair:(int(pair[1].get('version',0)),pair[1].get('declared_at',''),pair[0]))[1] if candidates else None
        complete=False
        if declaration and declaration.get('complete'):
            try: complete=validate_declaration(code,declaration.get('answer'))
            except ValueError: complete=False
        answer=declaration.get('answer') if complete else None
        value=answer.get('directors') if answer is not None and code=='G1.1' else answer.get('year') if answer is not None and code=='G3.1' else answer
        metrics.append(_strings(dict(code=code,title=TITLES[code],value=value,unit='directors' if code=='G1.1' else '',badge='declared' if complete else 'missing',evidence_ids=declaration.get('evidence_ids',[]) if declaration else [],method='Owner declaration for the reporting month; not independently verified.',factors=[],components=[],complete=complete,confirmed_by=[declaration['declared_by']] if declaration and declaration.get('declared_by') else [],confirmation_history=[dict(declared_by=declaration.get('declared_by'),declared_at=declaration.get('declared_at'))] if declaration else [],calculation_version='rules-v1')))
    breakdown=dict(complete=0,partial=0,estimated=0,missing=0)
    for m in metrics:
        key='complete' if m['complete'] else 'estimated' if m['badge']=='estimated' else 'partial' if any(c['value'] is not None for c in m['components']) else 'missing'
        breakdown[key]+=1
    gaps=[dict(code=m['code'],title=m['title'],badge=m['badge'],reason='Estimated proxy or allocation; review cannot make a proxy complete.' if m['badge']=='estimated' else 'Partial data available; required evidence, factor or review is missing.' if any(c['value'] is not None for c in m['components']) else 'Evidence or review is missing.') for m in metrics if not m['complete']]
    return dict(company=deepcopy(company),period=period,metrics=metrics,factors=_strings(deepcopy(factors)),readiness=dict(complete=breakdown['complete'],total=11,percent=str(Decimal(breakdown['complete'])*100/11),breakdown=breakdown),gaps=gaps)

def suggest_codes(text):
    """Advisory wording matching only, explicitly not AI."""
    text=text.lower()
    patterns=[('E1.2',r'electricity|scope\s*2|purchased.*emission'),('E1.1',r'diesel|petrol|scope\s*1|direct.*emission'),('E2.1',r'energy|kwh'),('E3.1',r'water'),('E4.1',r'waste'),('S1.1',r'child|forced|labour|labor'),('S4.1',r'injur|fatal|safety'),('G1.1',r'director|board'),('G2.1',r'polic'),('G3.1',r'audit|financial'),('G4.1',r'corrupt|brib')]
    return [code for code,pattern in patterns if re.search(pattern,text)]

def answer_question(question, profile):
    result=deepcopy(question)
    unsupported_parts=['Scope 3 emissions'] if re.search(r'scope\s*3\b',question.get('text',''),re.IGNORECASE) else []
    result.update(answer='Not available — confirm this mapping first.',badge='missing',metrics=[],evidence_ids=[],manual_declaration=None,unsupported_parts=unsupported_parts)
    if not question.get('reviewed'): return result
    if question.get('manual_answer'):
        attribution=question.get('manual_declaration') or dict(declared_by=profile['company'].get('owner_name') or profile['company'].get('owner') or 'Owner',method='Owner declaration; not independently verified.')
        result.update(answer=question['manual_answer'],badge='declared',manual_declaration=attribution)
        return result
    lookup={m['code']:m for m in profile['metrics']}
    selected=[deepcopy(lookup[c]) for c in _unique(question.get('codes',[])) if c in lookup]
    result.update(metrics=selected,evidence_ids=_unique(e for m in selected for e in m['evidence_ids']))
    if not selected:
        result['answer']='\n'.join(f'{part}: Not available — outside supported disclosures.' for part in unsupported_parts) if unsupported_parts else 'Not available — outside supported disclosures.'
        return result
    lines=[]
    for m in selected:
        value=m['value']
        if value is None: display='Not available'
        elif m['code'] in ('E1.1','E1.2'): display=f"{Decimal(value)/1000:.3f} t CO₂e"
        elif isinstance(value,dict): display=json.dumps(value,ensure_ascii=False)
        else: display=f"{value} {m['unit']}".strip()
        attribution=f" Owner declaration by {', '.join(m.get('confirmed_by', [])) or 'Owner'}." if m['badge']=='declared' else ''
        lines.append(f"{profile['period']} · Partial-year · {m['code']} {m['title']}: {display}.{attribution}")
    lines.extend(f'{part}: Not available — outside supported disclosures.' for part in unsupported_parts)
    badge='missing' if unsupported_parts or any(m['badge']=='missing' for m in selected) else 'estimated' if any(m['badge']=='estimated' for m in selected) else 'declared' if all(m['badge']=='declared' for m in selected) else 'auto'
    result.update(answer='\n'.join(lines),badge=badge)
    return result

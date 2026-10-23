"""Conservative bilingual requirement mapping. Offline: no provider SDK or API calls."""
from pathlib import Path
from datetime import date
import argparse
import copy
import json
import re
import jsonschema

WORK=Path(__file__).resolve().parent/'catalogue'


def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def has(pattern,text): return bool(re.search(pattern,text,re.I))
def has_terms(key,text):
    terms=read(WORK/'terminology.json')['pairs'][key]
    return has(r'\b(?:'+'|'.join(re.escape(term) for term in terms)+r')\b',text)


def target_period(text):
    if has(r'\b(?:FY\s*20\d{2}|financial year|fiscal year|tahun kewangan)\b',text):
        return {'start':None,'end':None},['fiscal_dates_required']
    dates=re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',text)
    if dates:
        try:
            if len(dates)!=2 or date.fromisoformat(dates[0])>date.fromisoformat(dates[1]):
                raise ValueError()
            return {'start':dates[0],'end':dates[1]},[]
        except ValueError:
            return {'start':None,'end':None},['date_range_review_required']
    years=list(dict.fromkeys(re.findall(r'\b20\d{2}\b',text)))
    if len(years)==1:
        return {'start':years[0]+'-01-01','end':years[0]+'-12-31'},[]
    return {'start':None,'end':None},['reporting_period_required' if not years else 'multiple_periods_require_decomposition']


def requested_units(text):
    units=[]
    for match in re.finditer(r'\b(?:tCO2e|tCO₂e|kgCO2e|kgCO₂e|kWh|MWh|GJ|Wh|MJ|m3|m³|litres?|liters?|liter|L|tonnes?|tan metrik|kg|MYR|RM)\b',text,re.I):
        token=match.group().lower()
        canonical={'tco2e':'tCO2e','tco₂e':'tCO2e','kgco2e':'kgCO2e','kgco₂e':'kgCO2e',
            'kwh':'kWh','mwh':'MWh','wh':'Wh','gj':'GJ','mj':'MJ','m3':'m3','m³':'m3',
            'litre':'L','litres':'L','liter':'L','liters':'L','l':'L','kg':'kg',
            'tonne':'t','tonnes':'t','tan metrik':'t','myr':'MYR','rm':'MYR'}[token]
        if canonical not in units:units.append(canonical)
    return units


def catalogue(): return read(WORK/'catalogue.json')


def map_question(question_id,text,context=None):
    if not isinstance(text,str) or not text.strip():raise ValueError('A nonempty question is required')
    cat=catalogue();entries={entry['code']:entry for entry in cat['entries']}
    context=context or {}
    codes=set(); candidates=set(); issues=[]; rules=[]
    explicit=re.findall(r'\b(?:SEDG[- ]?)?([ESG]\d+\.\d+)\b',text,re.I)
    explicit={c.upper() for c in explicit}
    unknown=explicit-entries.keys()
    if unknown:issues.append('unknown_code_requires_review')
    codes.update(explicit & entries.keys())
    if explicit:rules.append('explicit_catalogue_code')
    emissions=has_terms('emissions',text) or has(r'\b(?:emission|CO2e|CO₂e)\b',text)
    energy=has(r'\b(?:electricity|energy|fuel|diesel|petrol|tenaga|elektrik|bahan api)\b',text)
    water=has(r'\b(?:water|air)\b',text)
    waste=has(r'\b(?:waste|sisa|buangan)\b',text)
    reduction=has(r'\b(?:reduc\w*|pengurangan|kurang\w*)\b',text)
    for n in (1,2,3):
        if has(r'\b(?:scope|skop)\s*'+str(n)+r'\b',text):
            codes.add({1:'E1.1',2:'E1.2',3:'E1.5'}[n]);rules.append('explicit_scope_'+str(n))
    if has(r'\b(?:scopes?|skop)\s*1\s*(?:and|dan|&|/)\s*2\b',text):
        codes.update(['E1.1','E1.2']);rules.append('combined_scopes_1_2')
    if emissions and has(r'\b(?:direct|langsung)\b',text) and not has(r'\b(?:indirect|tidak langsung)\b',text):
        codes.add('E1.1');rules.append('direct_emissions')
    if emissions and has(r'\b(?:electricity|elektrik|grid)\b',text) and has(r'\b(?:purchased|grid|dibeli|bekalan grid)\b',text):
        codes.add('E1.2');rules.append('purchased_electricity_emissions')
    consumption=has(r'\b(?:consum\w*|usage|use|used|penggunaan|digunakan|menggunakan)\b',text)
    if energy and consumption and not emissions:
        codes.add('E2.1');rules.append('energy_consumption')
    # A combined emissions + energy question needs an explicit energy-consumption phrase.
    if energy and has(r'\b(?:energy consumption|electricity consumption|fuel consumption|penggunaan tenaga|penggunaan elektrik|penggunaan diesel)\b',text):
        codes.add('E2.1');rules.append('explicit_energy_consumption_phrase')
    if water and (has_terms('water',text) or has(r'\b(?:withdraw\w*|abstraction|drawn|pengambilan|diambil|dibeli)\b',text)):
        codes.add('E3.1');rules.append('water_withdrawal')
    if water and consumption and 'E3.1' not in codes:
        candidates.add('E3.1');issues.append('water_consumption_vs_withdrawal_review')
    if waste and has(r'\b(?:generat\w*|divert\w*|dispos\w*|dijana|dialih\w*|dilupus\w*|jumlah sisa|total waste)\b',text):
        codes.add('E4.1');rules.append('waste_flow_totals')
    if waste and has(r'\b(?:collect\w*|pickup|dikutip|kutipan)\b',text) and 'E4.1' not in codes:
        candidates.add('E4.1');issues.append('waste_collection_not_final_flow')
    if waste and has(r'\b(?:hazardous|non-hazardous|berbahaya|tidak berbahaya|composition|komposisi)\b',text):
        codes.discard('E4.1');codes.add('E4.2');rules.append('waste_breakdown_outside_basic_scope')
    if reduction:
        replacements={'E1.1':'E1.3','E1.2':'E1.4','E2.1':'E2.2','E3.1':'E3.2'}
        codes={replacements.get(code,code) for code in codes};rules.append('reduction_not_current_total')
    if emissions and has(r'\b(?:intensity|intensiti)\b',text):
        codes.difference_update(['E1.1','E1.2']);codes.add('E1.7');rules.append('emissions_intensity')
    if emissions and not any(c.startswith('E1.') for c in codes):
        candidates.update(['E1.1','E1.2','E1.5']);issues.append('emissions_scope_unspecified')
    # Never use a negated code as a positive label.
    if has(r'\b(?:not|exclude\w*|bukan|kecuali|jangan|tidak termasuk)\b',text):
        candidates.update(codes);codes.clear();issues.append('negation_requires_review')
    if has(r'\b(?:cost|charges|price|kos|caj|harga)\b',text) and not has(r'\b(?:consum\w*|penggunaan|withdraw\w*|pengambilan|emissions?|pelepasan|emisi)\b',text):
        codes.clear();candidates.clear();issues.append('financial_amount_not_activity_quantity')
    if unknown:
        candidates.update(codes);codes.clear()
    if codes and explicit and not codes.issubset(explicit):
        candidates.update(codes);codes.clear();issues.append('explicit_code_semantics_conflict')
    if codes:
        status='mapped' if all(entries[c]['supported'] for c in codes) else (
            'partially_mapped' if any(entries[c]['supported'] for c in codes) else 'outside_scope')
    elif candidates:status='needs_review' if unknown or 'negation_requires_review' in issues else 'ambiguous'
    else:status='needs_review' if unknown else 'outside_scope'
    period,period_issues=target_period(text)
    units=requested_units(text)
    requirements=[]
    for code in sorted(codes):
        entry=entries[code]
        if not entry['supported']:continue
        metrics=list(entry['metric_ids'])
        if code=='E2.1':
            metrics=['electricity_consumption'] if has(r'\b(?:electricity|elektrik)\b',text) else (
                ['fuel_consumption_energy'] if has(r'\b(?:fuel|diesel|petrol|bahan api)\b',text) else ['energy_consumption'])
        if code=='E4.1':
            selected=[]
            for metric,pattern in [('waste_generated',r'\b(?:generat\w*|dijana)\b'),
                ('waste_diverted',r'\b(?:divert\w*|dialih\w*)\b'),('waste_disposed',r'\b(?:disposed|directed to disposal|dilupus\w*)\b')]:
                if has(pattern,text):selected.append(metric)
            metrics=selected or metrics
        compatible=[u for u in units if u in entry['accepted_question_units']]
        requested=compatible[0] if len(compatible)==1 else None
        splits=[]
        if code=='E3.1':splits=['water_source']
        if code=='E2.1' and has(r'\b(?:by source|mengikut sumber|setiap sumber)\b',text):splits=['energy_source']
        boundary=copy.deepcopy(context.get('boundary',{'organisation_id':None,'site_id':None,'consolidation_method':None}))
        site_required=has(r'\b(?:site[- ]level|each site|per site|setiap tapak|mengikut tapak)\b',text)
        boundary['site_required']=site_required
        if has(r'\b(?:subsidiar\w*|anak syarikat)\b',text):boundary['subsidiary_required']=True
        boundary['question_boundary_text']=text
        for metric in metrics:
            gaps=list(period_issues)
            if not boundary.get('organisation_id'):gaps.append('organisation_boundary_required')
            if site_required and not boundary.get('site_id'):gaps.append('site_breakdown_required')
            if code in ('E1.1','E1.2'):
                gaps.append('reviewed_emissions_or_calculation_inputs_required')
                if not boundary.get('consolidation_method'):gaps.append('consolidation_method_required')
            if code=='E1.2':gaps.extend(['site_grid_region_required','gef_vintage_and_method_confirmation_required'])
            if requested is None:gaps.append('requested_unit_unspecified_or_ambiguous')
            if code=='E2.1' and requested=='L':gaps.append('fuel_specific_energy_conversion_required')
            requirements.append({'requirement_id':f'{question_id}-r{len(requirements)+1}',
                'sedg_code':code,'level':entry['level'],'metric_id':metric,'requested_unit':requested,
                'catalogue_units':entry['catalogue_units'],'target_period':period,'boundary':boundary,
                'required_breakdowns':splits,'calculation_inputs_required':entry['calculation_inputs_required'],
                'requires_calculation_if_activity_only':code in ('E1.1','E1.2'),
                'status':'mapped_requirement','missing_inputs':list(dict.fromkeys(gaps)),
                'question_span':{'start':0,'end':len(text),'text':text},'rule_ids':list(dict.fromkeys(rules))})
    result={'schema_version':'0.2.0','catalogue_version':cat['catalogue_version'],
        'question_id':question_id,'original_text':text,'method':'rules','mapping_status':status,
        'codes':sorted(codes),'candidate_codes':sorted(candidates-codes),'requirements':requirements,
        'issues':list(dict.fromkeys(issues)),'requires_human_review':True}
    validate_result(result)
    return result


def validate_result(result):
    """Validate model/rule output semantically; caller downgrades invalid fallback output."""
    jsonschema.validate(result,read(WORK/'mapping.schema.json'))
    cat=catalogue();entries={e['code']:e for e in cat['entries']}
    if result['catalogue_version']!=cat['catalogue_version']:raise ValueError('Catalogue version mismatch')
    if any(code not in entries for code in result['codes']+result['candidate_codes']):raise ValueError('Unknown SEDG code')
    supported={code for code in result['codes'] if entries[code]['supported']}
    if result['mapping_status']=='mapped' and (not supported or len(supported)!=len(result['codes'])):
        raise ValueError('Mapped state requires supported catalogue codes')
    if result['mapping_status'] in ('ambiguous','needs_review') and result['codes']:
        raise ValueError('Unresolved question must not assert accepted codes')
    seen=set()
    for req in result['requirements']:
        code=req['sedg_code']
        if code not in supported:raise ValueError('Requirement uses unaccepted or unsupported code')
        entry=entries[code]
        if req['level']!=entry['level']:raise ValueError('Code/tier mismatch')
        if req['metric_id'] not in entry['metric_ids']:raise ValueError('Metric/code mismatch')
        if req['requested_unit'] is not None and req['requested_unit'] not in entry['accepted_question_units']:
            raise ValueError('Unit/code mismatch')
        if req['catalogue_units']!=entry['catalogue_units']:raise ValueError('Canonical units changed')
        if req['calculation_inputs_required']!=entry['calculation_inputs_required']:raise ValueError('Calculation dependencies changed')
        if code in ('E1.1','E1.2') and not req['requires_calculation_if_activity_only']:
            raise ValueError('Activity quantities cannot be disclosure emissions values')
        key=(code,req['metric_id'])
        if key in seen:raise ValueError('Duplicate requirement')
        seen.add(key)
        span=req['question_span']
        if not 0<=span['start']<span['end']<=len(result['original_text']):raise ValueError('Invalid question span')
        if result['original_text'][span['start']:span['end']]!=span['text']:raise ValueError('Question provenance mismatch')
        if req['boundary']['question_boundary_text']!=result['original_text']:raise ValueError('Boundary provenance mismatch')
        start,end=req['target_period']['start'],req['target_period']['end']
        if (start is None)!=(end is None):raise ValueError('Partial period definition')
        if start and date.fromisoformat(start)>date.fromisoformat(end):raise ValueError('Reversed period')
    if supported!={r['sedg_code'] for r in result['requirements']}:raise ValueError('Missing supported requirements')
    return result


def validate_fallback(result,question_id,text):
    """Untrusted LLM result cannot be accepted through schema compliance alone."""
    try:
        if result['question_id']!=question_id or result['original_text']!=text:raise ValueError('Question mismatch')
        validate_result(result)
        return {'status':'structurally_valid_needs_semantic_review','result':result}
    except (ValueError,KeyError,TypeError,jsonschema.ValidationError):
        return {'status':'manual_review','result':None,'reason':'Invalid catalogue, schema, provenance or semantic constraints'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--text',required=True);parser.add_argument('--question-id',default='q-example')
    args=parser.parse_args();print(json.dumps(map_question(args.question_id,args.text),ensure_ascii=False,indent=2))


if __name__=='__main__':main()

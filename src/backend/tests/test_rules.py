import unittest
from decimal import Decimal
from esg_backend.rules import calculate_profile, validate_declaration, suggest_codes, answer_question

PERIOD='2026-09'
FACTORS=[dict(key=k,id=k+'-v1',value=v,unit=u,estimated=k!='grid') for k,v,u in [('grid','0.740','kg CO₂e/kWh'),('diesel','2.66155','kg CO₂e/L'),('petrol','2.33984','kg CO₂e/L'),('diesel-energy',str(Decimal('2.66155')/Decimal('.26808')),'kWh/L')]]
def doc(cat,q,unit,confirmed=True,**kw):
    a=dict(category=cat,quantity=q,unit=unit,period_start='2026-09-01',period_end='2026-09-30',estimated=False,confirmed_by='Clerk',confirmed_at='2026-10-01')
    a.update(kw)
    return dict(id=cat,name=cat,confirmed=confirmed,activities=[a])
def profile(docs,ds=()): return calculate_profile({'name':'Test','owner_name':'Owner'},docs,list(ds),FACTORS,PERIOD)
def metrics(docs,ds=()): return {m['code']:m for m in profile(docs,ds)['metrics']}
class RulesTests(unittest.TestCase):
    def test_environmental_arithmetic(self):
        m=metrics([doc('electricity','1000','kWh'),doc('diesel','100','L'),doc('water','10','m3'),doc('waste_generated','100','kg'),doc('waste_diverted','80','kg'),doc('waste_disposed','.020','t')])
        self.assertEqual(Decimal(m['E1.2']['value']),Decimal('740'))
        self.assertEqual(Decimal(m['E1.1']['value']),Decimal('266.155'))
        self.assertEqual(m['E1.1']['badge'],'estimated')
        self.assertEqual(m['E3.1']['value'],'10000')
        self.assertEqual([Decimal(c['value']) for c in m['E4.1']['components']],[Decimal('.1'),Decimal('.08'),Decimal('.02')])
        self.assertEqual(m['E1.2']['confirmed_by'],['Clerk'])
        self.assertEqual(m['E1.2']['factors'][0]['id'],'grid-v1')
    def test_pending_partial_zero(self):
        docs=[doc('electricity','0','kWh'),doc('electricity','5','kWh',False)]
        docs[1]['id']='pending'
        m=metrics(docs)['E1.2']
        self.assertIsNone(m['value'])
        self.assertEqual(m['components'][0]['value'],'0')
        self.assertEqual(set(m['evidence_ids']),{'electricity','pending'})
        self.assertEqual(metrics(docs[:1])['E1.2']['badge'],'auto')
    def test_missing_energy_waste(self):
        m=metrics([doc('electricity','1000','kWh'),doc('petrol','100','L'),doc('waste_generated','100','kg')])
        self.assertIsNone(m['E2.1']['value'])
        self.assertEqual(m['E2.1']['components'][0]['value'],'1000')
        self.assertIn('petrol',m['E2.1']['evidence_ids'])
        self.assertIsNone(m['E4.1']['value'])
        self.assertEqual(Decimal(m['E4.1']['components'][0]['value']),Decimal('.1'))
    def test_allocation(self):
        d=doc('water','5','m3',period_start='2026-08-20',period_end='2026-09-20')
        self.assertIsNone(metrics([d])['E3.1']['value'])
        d['activities'][0].update(allocated_period=PERIOD,assumptions='Allocation',estimated=True)
        self.assertEqual(metrics([d])['E3.1']['value'],'5000')
        self.assertEqual(metrics([d])['E3.1']['badge'],'estimated')
        d['activities'][0]['allocated_period']='2026-08'
        self.assertIsNone(metrics([d])['E3.1']['value'])
    def test_energy_without_fuel(self):
        self.assertEqual(metrics([doc('electricity','1000','kWh')])['E2.1']['value'],'1000')
    def test_declaration_validation(self):
        for v in [-1,True,1.2,'1']:
            with self.subTest(v=v),self.assertRaises(ValueError): validate_declaration('S1.1',{'count':v})
        self.assertFalse(validate_declaration('S1.1',{}))
        self.assertFalse(validate_declaration('S1.1',{'count':2,'description':''}))
        self.assertTrue(validate_declaration('S1.1',{'count':0}))
        self.assertFalse(validate_declaration('G2.1',{'policies':[{'name':'Code of Conduct','status':'in place'}]}))
        with self.assertRaises(ValueError): validate_declaration('G3.1',{'year':1800})
    def test_readiness_latest(self):
        answers={'S1.1':{'count':0},'S4.1':{'injuries':0,'fatalities':0},'G1.1':{'directors':2},'G2.1':{'policies':[{'name':n,'status':'not in place'} for n in ['Code of Conduct','Anti-Corruption Policy','Whistleblowing Policy','Health and Safety Policy']]},'G3.1':{'year':2025},'G4.1':{'count':0}}
        ds=[dict(code=k,answer=v,period=PERIOD,complete=True,declared_by='Owner',version=1) for k,v in answers.items()]
        docs=[doc('electricity','1000','kWh',False),doc('diesel','100','L'),doc('water','10','m3'),doc('waste_generated','100','kg'),doc('waste_diverted','80','kg'),doc('waste_disposed','20','kg')]
        self.assertEqual(profile(docs,ds)['readiness']['complete'],8)
        ds.append(dict(code='G1.1',answer={},period=PERIOD,complete=False,version=2))
        self.assertIsNone(metrics(docs,ds)['G1.1']['value'])
    def test_question_review_and_mapping(self):
        self.assertEqual(suggest_codes('Scope 3 and purchased electricity emissions'),['E1.2'])
        p=profile([doc('electricity','1000','kWh')]); q={'text':'Electricity','codes':['E1.2'],'reviewed':False}
        self.assertEqual(answer_question(q,p)['metrics'],[])
        q['reviewed']=True
        self.assertIn('0.740 t CO₂e',answer_question(q,p)['answer'])
        q.update(codes=[],manual_answer='Owner supplied answer')
        a=answer_question(q,p)
        self.assertEqual(a['badge'],'declared'); self.assertEqual(a['metrics'],[])
        self.assertIn('Owner',str(a['manual_declaration']))
    def test_negative_quantity_and_non_finite_are_rejected(self):
        for quantity in ('-1','NaN','Infinity',True):
            with self.subTest(quantity=quantity),self.assertRaises(ValueError):
                metrics([doc('water',quantity,'L')])
    def test_out_of_period_records_do_not_block_or_supply_evidence(self):
        old=doc('electricity','900','kWh',False,period_start='2026-08-01',period_end='2026-08-31')
        old['id']='old'
        m=metrics([old,doc('electricity','0','kWh')])['E1.2']
        self.assertEqual(m['value'],'0')
        self.assertEqual(m['evidence_ids'],['electricity'])
        self.assertTrue(m['complete'])
    def test_declaration_unknown_and_description_validation(self):
        policies=[{'name':n,'status':'in place'} for n in ['Code of Conduct','Anti-Corruption Policy','Whistleblowing Policy','Health and Safety Policy']]
        policies[-1]['status']='unknown'
        self.assertFalse(validate_declaration('G2.1',{'policies':policies}))
        self.assertFalse(validate_declaration('S4.1',{'injuries':0,'fatalities':1}))
        self.assertTrue(validate_declaration('S4.1',{'injuries':0,'fatalities':1,'description':'One incident investigated.'}))
        with self.assertRaises(ValueError): validate_declaration('G4.1',{'count':0,'description':False})
    def test_compound_scope3_question_preserves_supported_answer_and_explicit_gap(self):
        p=profile([doc('electricity','1000','kWh')])
        q={'text':'Disclose Scope 2 electricity emissions and Scope 3 emissions','codes':['E1.2'],'reviewed':False,'uncertainty':'Wording-based suggestion; not AI.'}
        pending=answer_question(q,p)
        self.assertEqual(pending['unsupported_parts'],['Scope 3 emissions'])
        self.assertEqual(pending['uncertainty'],q['uncertainty'])
        self.assertEqual(pending['metrics'],[])
        q['reviewed']=True
        result=answer_question(q,p)
        self.assertIn('0.740 t CO₂e',result['answer'])
        self.assertIn('Scope 3 emissions: Not available — outside supported disclosures.',result['answer'])
        self.assertEqual(result['badge'],'missing')
        self.assertEqual([m['code'] for m in result['metrics']],['E1.2'])
        q['manual_answer']='Owner declaration covering both requested scopes'
        manual=answer_question(q,p)
        self.assertEqual(manual['badge'],'declared')
        self.assertEqual(manual['answer'],q['manual_answer'])
        self.assertEqual(manual['metrics'],[])
        self.assertEqual(manual['unsupported_parts'],['Scope 3 emissions'])

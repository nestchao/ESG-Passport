"""Boundary and validator regression tests; no live inference or external data."""
import copy
import hashlib
import unittest
from ai.workflow.mapping import map_question,validate_result,validate_fallback
from ai.workflow.coverage import assess_coverage

CONTEXT={'boundary':{'organisation_id':'demo-org','site_id':'demo-site','consolidation_method':'operational_control'}}


def req(text,context=None):
    return map_question('q-test',text,CONTEXT if context is None else context)['requirements'][0]


def evidence(metric='electricity_consumption',unit='kWh',value='100',left='2026-01-01',right='2026-12-31',identity='demo-1',**extra):
    return {'evidence_id':identity,'document_sha256':hashlib.sha256(identity.encode()).hexdigest(),
        'organisation_id':'demo-org','site_id':'demo-site','consolidation_method':'operational_control',
        'metric_id':metric,'value':value,'unit':unit,'period':{'start':left,'end':right},'reviewed':True,**extra}


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.energy=req('Report electricity consumption for 2026 in kWh.')
        self.water=req('Report water withdrawn for 2026 in litres.')
        self.scope2=req('Report Scope 2 emissions for 2026 in tCO2e.')
        self.water_declarations={'reviewed':True,'water_source_applicability':{
            'purchased':True,'surface':False,'groundwater':False,'seawater':False,'produced':False}}

    def test_electricity_quantity_direct_evidence_is_still_unverified(self):
        result=assess_coverage(self.energy,[evidence()])
        self.assertEqual(result['state'],'direct_evidence')
        self.assertEqual(result['normalized_candidate_total'],'100000')
        self.assertFalse(result['is_verified_disclosure'])

    def test_scope2_activity_is_not_an_emissions_value_or_default_factor(self):
        result=assess_coverage(self.scope2,[evidence()])
        self.assertEqual(result['state'],'calculation_required')
        self.assertIsNone(result['calculated_value'])
        self.assertIn('factor_vintage_confirmation_required',result['issues'])

    def test_all_reviewed_scope2_inputs_can_be_ready_without_calculation(self):
        result=assess_coverage(self.scope2,[evidence()],{'reviewed':True,'factor_reviewed':True,
            'grid_region':'peninsular','factor_vintage':'2024','factor_source':'explicit-demo-source',
            'accounting_method':'location_based','factor_value':'0.7','factor_unit':'kgCO2e/kWh',
            'factor_selection_justification':'Synthetic owner-approved example, not automatically selected'})
        self.assertEqual(result['readiness'],'inputs_ready')
        self.assertIsNone(result['calculated_value'])

    def test_power_is_not_scope2_energy(self):
        result=assess_coverage(self.scope2,[evidence(unit='kW')])
        self.assertEqual(result['state'],'manual_review')
        self.assertIn('scope2_activity_must_be_energy_not_power',result['issues'])

    def test_scope2_metadata_without_factor_value_is_not_input_ready(self):
        result=assess_coverage(self.scope2,[evidence()],{'reviewed':True,'factor_reviewed':True,
            'grid_region':'peninsular','factor_vintage':'2024','factor_source':'demo','accounting_method':'location_based'})
        self.assertEqual(result['readiness'],'activity_only')

    def test_reviewed_reported_emissions_can_be_matched(self):
        observation=evidence('scope2_emissions','tCO2e','1.25',calculation_provenance={
            'reviewed':True,'method':'documented location-based calculation','factor_source':'demo-source',
            'factor_vintage':'2024','grid_region':'peninsular','accounting_method':'location_based'})
        result=assess_coverage(self.scope2,[observation])
        self.assertEqual(result['state'],'direct_evidence')
        self.assertEqual(result['normalized_candidate_total'],'1.25')

    def test_unreviewed_calculation_is_not_accepted(self):
        observation=evidence('scope2_emissions','tCO2e','1.25')
        self.assertEqual(assess_coverage(self.scope2,[observation])['state'],'manual_review')

    def test_unconfirmed_water_sources_are_partial_not_assumed_missing(self):
        observation=evidence('water_withdrawal','m3','10',source='purchased')
        result=assess_coverage(self.water,[observation])
        self.assertEqual(result['state'],'partial')
        self.assertIn('water_source_applicability_unconfirmed',result['issues'])
        self.assertEqual(result['normalized_candidate_total'],'10000')

    def test_confirmed_only_purchased_water_can_fully_cover_requirement(self):
        observation=evidence('water_withdrawal','m3','10',source='purchased')
        self.assertEqual(assess_coverage(self.water,[observation],self.water_declarations)['state'],'direct_evidence')

    def test_applicable_groundwater_without_records_is_partial(self):
        declarations=copy.deepcopy(self.water_declarations)
        declarations['water_source_applicability']['groundwater']=True
        result=assess_coverage(self.water,[evidence('water_withdrawal','m3','10',source='purchased')],declarations)
        self.assertIn('partial_water_source_coverage',result['issues'])
        self.assertEqual(result['state'],'partial')

    def test_unreviewed_owner_declaration_does_not_close_gap(self):
        declarations=copy.deepcopy(self.water_declarations);declarations['reviewed']=False
        result=assess_coverage(self.water,[evidence('water_withdrawal','L','10',source='purchased')],declarations)
        self.assertEqual(result['state'],'partial')

    def test_partial_billing_period_does_not_cover_annual_request(self):
        result=assess_coverage(self.energy,[evidence(right='2026-06-30')])
        self.assertEqual(result['state'],'partial')
        self.assertIn('partial_period_coverage',result['issues'])

    def test_full_interval_bills_can_cover_year(self):
        first=evidence(right='2026-06-30')
        second=evidence(left='2026-07-01',identity='demo-2')
        self.assertEqual(assess_coverage(self.energy,[first,second])['state'],'direct_evidence')

    def test_crossing_period_needs_allocation_even_if_it_contains_target(self):
        result=assess_coverage(self.energy,[evidence(left='2025-12-01',right='2027-01-01')])
        self.assertEqual(result['state'],'partial')
        self.assertIn('allocation_required_for_crossing_period',result['issues'])

    def test_duplicate_document_does_not_double_count(self):
        observation=evidence()
        result=assess_coverage(self.energy,[observation,copy.deepcopy(observation)])
        self.assertEqual(result['duplicate_records_removed'],1)
        self.assertEqual(result['normalized_candidate_total'],'100000')

    def test_overlapping_distinct_bills_are_not_summed(self):
        self.assertEqual(assess_coverage(self.energy,[evidence(),evidence(identity='another-invoice')])['state'],'manual_review')

    def test_wrong_site_is_not_used(self):
        observation=evidence(site_id='other-site')
        self.assertEqual(assess_coverage(self.energy,[observation])['state'],'missing')

    def test_one_site_does_not_imply_company_coverage(self):
        energy=req('Report electricity consumption for 2026 in kWh.',{'boundary':{
            'organisation_id':'demo-org','site_id':None,'consolidation_method':'operational_control'}})
        self.assertIn('company_site_coverage_unconfirmed',assess_coverage(energy,[evidence()])['issues'])
        self.assertEqual(assess_coverage(energy,[evidence(covers_organisation_boundary=True)])['state'],'direct_evidence')

    def test_diesel_volume_requires_energy_conversion(self):
        fuel=req('Report diesel fuel consumption for 2026 in kWh.')
        result=assess_coverage(fuel,[evidence('fuel_consumed','L','40')])
        self.assertEqual(result['state'],'calculation_required')
        self.assertIn('fuel_specific_energy_conversion_required',result['issues'])

    def test_fuel_purchase_is_not_automatically_fuel_consumed(self):
        scope1=req('Report Scope 1 emissions for 2026 in tCO2e.')
        self.assertEqual(assess_coverage(scope1,[evidence('fuel_purchased','L','40')])['state'],'missing')

    def test_waste_pickup_is_not_waste_generated_or_confirmed_disposal(self):
        waste=req('Report waste generated for 2026 in tonnes.')
        result=assess_coverage(waste,[evidence('waste_transferred','kg','500')])
        self.assertEqual(result['state'],'partial')
        self.assertIn('waste_transfer_does_not_establish_requested_flow',result['issues'])

    def test_declared_waste_destination_is_not_confirmed_treatment(self):
        waste=req('Report waste diverted from disposal for 2026 in tonnes.')
        result=assess_coverage(waste,[evidence('waste_diverted','kg','500',treatment_confirmed=False)],
            {'reviewed':True,'waste_flow_completeness_confirmed':True})
        self.assertEqual(result['state'],'partial')
        self.assertIn('declared_destination_not_confirmed_treatment',result['issues'])


if __name__=='__main__':unittest.main()

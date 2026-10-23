"""PR #9 unit checks inside the original ESG calculation functions."""
from copy import deepcopy
from decimal import Decimal
from esg_backend.ai_calculation import factor_unit_compatible, normalize_existing_quantity, existing_calculation_provenance
from esg_backend.rules import calculate_profile
from test_rules import FACTORS, doc, profile


def metrics(result):
    return {m['code']: m for m in result['metrics']}


def test_pr9_unit_conversion_same_as_existing_arithmetic():
    assert normalize_existing_quantity('water', 10, 'm3') == Decimal('10000')
    assert normalize_existing_quantity('water', 10, 'L') == Decimal('10')
    assert normalize_existing_quantity('waste_generated', 250, 'kg') == Decimal('.250')
    assert normalize_existing_quantity('waste_generated', Decimal('0.25'), 't') == Decimal('.25')
    assert normalize_existing_quantity('water', 1, 'm³') == Decimal('1000')


def test_wrong_factor_unit_must_not_calculate_scope_2():
    factors = deepcopy(FACTORS)
    grid = next(f for f in factors if f['key'] == 'grid')
    assert factor_unit_compatible('grid', grid)
    grid['unit'] = 'kg CO₂e/L'
    assert not factor_unit_compatible('grid', grid)
    output = calculate_profile({'name': 'Test', 'owner_name': 'Owner'},
                               [doc('electricity', '1000', 'kWh')], [], factors, '2026-09')
    scope2 = metrics(output)['E1.2']
    assert scope2['value'] is None
    assert scope2['badge'] == 'missing'
    assert scope2['components'][0]['value'] is None


def test_wrong_fuel_energy_factor_unit_must_not_calculate_energy():
    factors = deepcopy(FACTORS)
    next(f for f in factors if f['key'] == 'diesel-energy')['unit'] = 'kg CO₂e/L'
    output = calculate_profile({'name':'Test','owner_name':'Owner'},
                               [doc('diesel','100','L')], [], factors, '2026-09')
    energy = metrics(output)['E2.1']
    assert energy['value'] is None
    assert energy['badge'] == 'missing'


def test_valid_factors_preserve_existing_values():
    results = metrics(profile([doc('electricity','1000','kWh'), doc('water','10','m3'),
                               doc('waste_generated','100','kg'),
                               doc('waste_diverted','80','kg'),
                               doc('waste_disposed','20','kg')]))
    assert Decimal(results['E1.2']['value']) == Decimal('740')
    assert Decimal(results['E3.1']['value']) == Decimal('10000')
    assert Decimal(results['E4.1']['value']) == Decimal('.1')


def test_scope2_missing_review_metadata_clearly_flagged():
    result = profile([doc('electricity','1000','kWh')])
    warning = existing_calculation_provenance(result, ['E1.2'])
    assert 'factor_review_decision_not_recorded' in warning
    assert 'grid_region_not_recorded' in warning
    assert 'accounting_method_not_recorded' in warning
    assert 'factor_site_scope_not_recorded' in warning
    assert existing_calculation_provenance(result, ['E3.1']) == ''

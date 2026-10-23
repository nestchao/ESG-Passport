"""Backend-only calculation guards using PR #9's reviewed unit catalogue.

This is NOT the standalone Stage 4 preparation/approval engine. Its source
provenance and boundary checks still require separately reviewed metadata.
"""
from decimal import Decimal
from pathlib import Path
import sys

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
from ai.workflow.coverage import UNIT

_CONVERT = {'water': ('water', 'L'),
            'waste_generated': ('waste', 't'),
            'waste_diverted': ('waste', 't'),
            'waste_disposed': ('waste', 't')}
_FACTOR_UNIT = {
    'grid': 'kgco2e/kwh',
    'diesel': 'kgco2e/l',
    'petrol': 'kgco2e/l',
    'diesel-energy': 'kwh/l',
    'petrol-energy': 'kwh/l',
}


def normalize_existing_quantity(category, quantity, unit):
    """Use PR #9's dimensions/conversion factors for existing water/waste sums."""
    expected_dimension, target_unit = _CONVERT[category]
    normalized_unit = {'m³': 'm3', 'm³': 'm3'}.get(unit, unit)
    source = UNIT.get(normalized_unit)
    target = UNIT[target_unit]
    if source is None or source[0] != expected_dimension:
        raise ValueError('Activity quantity has an incompatible unit.')
    return Decimal(str(quantity)) * source[1] / target[1]


def factor_unit_compatible(key, factor):
    """Do not apply emissions/energy factors to a mismatched activity unit."""
    if factor is None:
        return False
    expected = _FACTOR_UNIT.get(key)
    if expected is None:
        return False
    unit = factor.get('unit')
    if not isinstance(unit, str):
        return False
    canonical = unit.lower().replace(' ', '').replace('₂', '2')
    return canonical == expected


def existing_calculation_provenance(profile, codes):
    """PR #9 Stage-4 provenance requirements as advisory review gaps.

    The existing factor table has source, year and unit, but no explicit site/
    region/accounting-method/factor-review decision. Never invent those facts.
    """
    selected = set(codes or ()) & {'E1.1', 'E1.2', 'E2.1'}
    if not selected:
        return ''
    factors = {f.get('key'): f for f in profile.get('factors', [])}
    year = int(profile['period'][:4])
    warnings = []
    if 'E1.2' in selected:
        grid = factors.get('grid')
        gaps = []
        if not grid or not grid.get('source'):
            gaps.append('factor_source_not_recorded')
        if not grid or not grid.get('year'):
            gaps.append('factor_vintage_not_recorded')
        elif int(grid['year']) > year:
            gaps.append('factor_vintage_after_reporting_period')
        if not grid or grid.get('reviewed') is not True:
            gaps.append('factor_review_decision_not_recorded')
        if not grid or not grid.get('grid_region'):
            gaps.append('grid_region_not_recorded')
        if not grid or not grid.get('accounting_method'):
            gaps.append('accounting_method_not_recorded')
        if not grid or not grid.get('factor_site_ids'):
            gaps.append('factor_site_scope_not_recorded')
        if gaps:
            warnings.append('E1.2: ' + ', '.join(gaps))
    if 'E1.1' in selected:
        metric = next((m for m in profile.get('metrics', []) if m['code'] == 'E1.1'), {})
        if metric.get('badge') == 'estimated':
            warnings.append('E1.1: estimated_fuel_proxy_requires_explicit_review')
        if any(f.get('reviewed') is not True for f in metric.get('factors', [])):
            warnings.append('E1.1: fuel_factor_review_decision_not_recorded')
    if 'E2.1' in selected:
        metric = next((m for m in profile.get('metrics', []) if m['code'] == 'E2.1'), {})
        if metric.get('badge') == 'estimated':
            warnings.append('E2.1: fuel_energy_proxy_requires_review')
    return ('AI calculation provenance (requires owner verification): '
            + '; '.join(warnings) + '.') if warnings else ''

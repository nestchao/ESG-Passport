"""Explicit synthetic workspace creation; no startup seeding or overwriting."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import logging
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from .models import Activity, ActivityEvent, Company, Declaration, Document, FactorVersion, Question, Questionnaire, utcnow
from .rules import validate_declaration

PERIOD = '2026-09'
SAMPLES = (
    ('electricity', 'electricity', 'Electricity bill - September', '1000', 'kWh', False),
    ('diesel', 'diesel', 'Diesel receipt - September', '100', 'L', True),
    ('water', 'water', 'Purchased water bill - September', '10', 'm3', True),
    ('waste-generated', 'waste_generated', 'Waste generated record', '100', 'kg', True),
    ('waste-diverted', 'waste_diverted', 'Recycler collection slip', '80', 'kg', True),
    ('waste-disposed', 'waste_disposed', 'Waste disposal slip', '20', 'kg', True),
)


def sample_png(name, category, quantity, unit):
    """Each record has distinct source bytes and legible, matching quantities."""
    image = Image.new('RGB', (900, 1000), '#f5f8f7')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 900, 150), fill='#123c35')
    font = ImageFont.load_default(size=26)
    draw.text((40, 55), 'SAMPLE SOURCE RECORD', fill='white', font=font)
    lines = [name, 'Lim Carton Industries (fictional)', 'Shah Alam, Selangor',
             'Period: 01-30 September 2026', f'{category}: {quantity} {unit}',
             'Sample evidence for the starting workspace.', 'Not a real bill.']
    for index, line in enumerate(lines):
        draw.text((40, 210 + index * 75), line, fill='#172d28', font=font)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def seed_workspace(session, storage, settings) -> None:
    """Seed once; caller commits. Failures roll back and remove new originals."""
    if session.get(Company, settings.company_id) is not None:
        return
    uploaded = []
    try:
        storage.ensure_bucket()
        now = utcnow()
        company_id = settings.company_id
        session.add(Company(id=company_id, name='Lim Carton Industries', location='Shah Alam',
                            sector='Manufacturing', period=PERIOD, synthetic=True))
        session.flush()
        grid_source = 'https://myenergystats.st.gov.my/documents/d/guest/grid-emission-factor-gef-in-malaysia-2022-2024-provisional-'
        fuel_source = 'https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2025'
        factors = [
            ('grid', 'Peninsular grid', Decimal('0.740'), 'kg CO₂e/kWh', 2024, grid_source, '2024 provisional factor; Peninsular Malaysia grid basis.', False),
            ('diesel', 'Mineral diesel proxy', Decimal('2.66155'), 'kg CO₂e/L', 2025, fuel_source, 'Mineral-fuel proxy; no biodiesel adjustment.', True),
            ('diesel-energy', 'Diesel energy proxy', (Decimal('2.66155') / Decimal('0.26808')).quantize(Decimal('0.000000000000001')), 'kWh/L', 2025, fuel_source, 'Derived mineral-fuel proxy; illustrative monthly energy arithmetic.', True),
            ('petrol', 'Mineral petrol proxy', Decimal('2.33984'), 'kg CO₂e/L', 2025, fuel_source, 'Petrol energy factor unavailable.', True),
        ]
        for key, name, value, unit, year, source, assumptions, estimated in factors:
            if session.get(FactorVersion, key + '-v1') is None:
                session.add(FactorVersion(id=key + '-v1', key=key, name=name, value=value, unit=unit,
                                         year=year, version=key + '-v1', source=source,
                                         assumptions=assumptions, estimated=estimated))
        for slug, category, name, quantity, unit, confirmed in SAMPLES:
            document_id = 'doc-' + slug
            content = sample_png(name, category, quantity, unit)
            path = f'{company_id}/seed/{uuid4()}/{document_id}.png'
            # Register the attempted path before upload in case transport failure follows a successful write.
            uploaded.append(path)
            storage.upload(path, content, 'image/png')
            activity = dict(category=category, quantity=quantity, unit=unit, period_start='2026-09-01',
                            period_end='2026-09-30', estimated=False, source_reference='Synthetic quantity line',
                            confirmed_by='Admin clerk' if confirmed else '',
                            confirmed_at=now.isoformat() if confirmed else None)
            extraction = dict(supplier_name='Sample Utilities / Services', document_date='2026-09-30',
                              period_start='2026-09-01', period_end='2026-09-30', activities=[activity],
                              uncertainty_notes=['Sample source record. Check all quantities before confirmation.'])
            session.add(Document(id=document_id, company_id=company_id, name=name + '.png',
                                 type='waste' if category.startswith('waste') else category, period=PERIOD,
                                 mime_type='image/png', file_hash=sha256(content).hexdigest(), object_path=path,
                                 confirmed=confirmed, activity_revision=1, extraction=deepcopy(extraction),
                                 original_extraction=deepcopy(extraction), uploaded_by='Admin clerk', uploaded_at=now))
            session.flush()
            session.add(Activity(company_id=company_id, document_id=document_id, revision=1, category=category,
                                 quantity=Decimal(quantity), unit=unit, period_start=date(2026, 9, 1),
                                 period_end=date(2026, 9, 30), estimated=False, source_reference='Synthetic quantity line',
                                 confirmed_by='Admin clerk' if confirmed else '', confirmed_at=now if confirmed else None))
        answers = {
            'S1.1': {'count': 0, 'description': 'No incidents reported in the synthetic month.'},
            'S4.1': {'injuries': 0, 'fatalities': 0, 'description': 'No injuries or fatalities reported.'},
            'G1.1': {'directors': 2},
            'G2.1': {'policies': [{'name': 'Code of Conduct', 'status': 'in place'},
                                {'name': 'Anti-Corruption Policy', 'status': 'not in place'},
                                {'name': 'Whistleblowing Policy', 'status': 'not in place'},
                                {'name': 'Health and Safety Policy', 'status': 'in place'}]},
            'G3.1': {'year': 2025},
            'G4.1': {'count': 0, 'description': 'No confirmed corruption incidents reported.'},
        }
        for code, answer in answers.items():
            session.add(Declaration(company_id=company_id, code=code, period=PERIOD, answer=answer,
                                    evidence_ids=[], complete=validate_declaration(code, answer),
                                    declared_by='Mr Lim', declared_at=now, version=1))
        requests = [
            ('Meridian Foods', ['What are your Scope 2 electricity emissions?', 'How much water did you use?',
                                'How many directors does your company have?', 'What are your Scope 3 emissions?']),
            ('Northstar Packaging', ['Please disclose carbon emissions from purchased electricity.',
                                     'State your purchased water volume.', 'List the number of company directors.']),
        ]
        for index, (customer, texts) in enumerate(requests, 1):
            request_id = f'request-{index}'
            session.add(Questionnaire(id=request_id, company_id=company_id, customer=customer,
                                      period=PERIOD, due_date=date(2026, 10, 23), status='draft', version=1))
            session.flush()
            for position, text in enumerate(texts):
                session.add(Question(id=f'{request_id}-q{position}', questionnaire_id=request_id,
                                     text=text, codes=[], proposed_codes=[], reviewed=False, position=position,
                                     confidence='Not assessed', rationale='Awaiting matching; no AI is connected.'))
        session.add(ActivityEvent(company_id=company_id, actor='System', role='owner', action='workspace_seeded',
                                  target=company_id, time=now, summary='Synthetic sample workspace explicitly seeded.'))
        session.flush()
        # Enables the explicit CLI caller to compensate if its subsequent commit fails.
        session.info.setdefault('seed_uploaded_paths', []).extend(uploaded)
    except Exception:
        session.rollback()
        if uploaded:
            try:
                storage.delete(uploaded)
            except Exception:
                logging.getLogger(__name__).error('Seed rollback could not remove newly uploaded sample objects; review private storage.')
        raise

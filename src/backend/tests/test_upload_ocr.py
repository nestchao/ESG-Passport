"""OCR fills the existing document editor but never confirms source data."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from esg_backend.bill_ocr import parse_bill_text, extract_upload
from test_api import workspace, CLERK, get


def bill(fmt='PNG'):
    image = Image.new('RGB', (1200, 410), 'white')
    draw = ImageDraw.Draw(image)
    # CI runs on Ubuntu; local development often runs on Windows.
    font_paths = [Path('C:/Windows/Fonts/arial.ttf'),
                  Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font_file = next((path for path in font_paths if path.exists()), None)
    font = ImageFont.truetype(str(font_file), 44) if font_file else ImageFont.load_default(size=44)
    draw.text((28, 25), 'Sample Electricity Supplier', font=font, fill='black')
    draw.text((28, 105), 'Electricity Usage: 1,234 kWh', font=font, fill='black')
    draw.text((28, 195), 'Billing Period: 01/09/2026 - 30/09/2026', font=font, fill='black')
    output=BytesIO();image.save(output, format=fmt);image.close()
    return output.getvalue()


def test_parser_requires_unit_and_avoids_guessing():
    result = parse_bill_text(['Bill total: RM 12,300.00', 'Account 10298'], 'electricity', '2026-09')
    assert result['activities'] == []
    assert result['ocr_status'] == 'manual_entry_required'
    result = parse_bill_text(['Electricity Usage: 120 kWh','Electricity Usage: 140 kWh'], 'electricity', '2026-09')
    assert result['activities'] == []
    assert any('multiple' in note for note in result['uncertainty_notes'])


def test_image_ocr_extracts_candidate_without_confirmation(workspace):
    client, *_ = workspace
    response = client.post('/documents', headers=CLERK,
        data={'type':'electricity','period':'2026-09'},
        files={'file':('electricity-bill.png',bill('PNG'),'image/png')})
    assert response.status_code == 201, response.text
    document = response.json()
    assert document['confirmed'] is False
    assert document['activities'] == []
    extraction = document['extraction']
    assert extraction['ocr_engine'] == 'RapidOCR (offline)'
    assert extraction['ocr_status'] == 'candidate_found', extraction
    assert extraction['activities'][0]['quantity'] == '1234'
    assert extraction['activities'][0]['unit'] == 'kWh'
    assert extraction['activities'][0]['period_start'] == '2026-09-01'
    assert extraction['activities'][0]['period_end'] == '2026-09-30'
    assert document['original_extraction'] == extraction
    assert get(client, f"/documents/{document['id']}")['extraction'] == extraction
    before=get(client, '/profile')
    saved=client.put(f"/documents/{document['id']}/activities", headers=CLERK,
                     json={'activities':extraction['activities'], 'confirmed':True,
                           'expected_version':document['version']})
    assert saved.status_code == 200, saved.text
    after=get(client,'/profile')
    scope2=next(m for m in after['metrics'] if m['code']=='E1.2')
    assert document['id'] in scope2['evidence_ids']
    assert scope2['components'][0]['value'] == '913.16'  # 1234 kWh x existing 0.740 factor
    assert next(m for m in before['metrics'] if m['code']=='E1.2')['components'][0]['value'] is None


def test_scanned_pdf_ocr_uses_existing_upload_format():
    result = extract_upload(bill('PDF'), 'application/pdf', 'electricity', '2026-09')
    assert result['ocr_status'] == 'candidate_found', result
    assert result['activities'][0]['quantity'] == '1234'


def test_mismatched_billing_month_stays_unconfirmed():
    result = parse_bill_text(['Electricity Usage: 50 kWh',
                              'Billing Period: 01/08/2026 - 31/08/2026'],
                             'electricity','2026-09')
    assert result['activities'][0]['period_start'] == '2026-08-01'
    assert any('differ' in note for note in result['uncertainty_notes'])


def test_scanned_pdf_created_through_existing_api(workspace):
    client, *_ = workspace
    response=client.post('/documents',headers=CLERK,
        data={'type':'electricity','period':'2026-09'},
        files={'file':('scanned-bill.pdf',bill('PDF'),'application/pdf')})
    assert response.status_code == 201, response.text
    document=response.json()
    assert document['confirmed'] is False
    assert document['extraction']['activities'][0]['quantity'] == '1234'
    assert document['activities'] == []


# The repository sample that exposed the OCR parser bug: Malay headings are
# split from the consumption value, and date-label spaces disappear in OCR.
def test_malay_itemised_sample_exact_file():
    from pathlib import Path
    sample = (Path(__file__).resolve().parents[2] / 'ai' / 'synthetic_dataset'
              / 'electricity' / 'electricity-itemised-001-photo.png')
    assert sample.is_file()
    result = extract_upload(sample.read_bytes(), 'image/png', 'electricity', '2026-09')
    assert result['ocr_status'] == 'candidate_found', result
    assert len(result['activities']) == 1
    assert result['activities'][0]['quantity'] == '2577'
    assert result['activities'][0]['unit'] == 'kWh'
    assert result['activities'][0]['period_start'] == '2026-05-01'
    assert result['activities'][0]['period_end'] == '2026-05-31'
    assert result['document_date'] == '2026-06-02'
    assert any('differ from the selected reporting month' in note
               for note in result['uncertainty_notes'])


def test_existing_failed_extraction_retried_without_modifying_original(workspace):
    from pathlib import Path
    from sqlalchemy import select
    from esg_backend.models import Document
    client, sessions, *_ = workspace
    sample = (Path(__file__).resolve().parents[2] / 'ai' / 'synthetic_dataset'
              / 'electricity' / 'electricity-itemised-001-photo.png')
    uploaded = client.post('/documents', headers=CLERK,
         data={'type': 'electricity', 'period':'2026-09'},
         files={'file': ('itemised.png',sample.read_bytes(),'image/png')})
    assert uploaded.status_code == 201, uploaded.text
    identifier=uploaded.json()['id']
    old = {'ocr_engine':'RapidOCR (offline)', 'ocr_status':'manual_entry_required',
           'activities': [], 'uncertainty_notes':['Old OCR parser could not find quantity']}
    with sessions() as session:
        row = session.get(Document, identifier)
        row.extraction = old
        row.original_extraction = old
        session.commit()
    result = get(client, f'/documents/{identifier}')
    assert result['confirmed'] is False
    assert result['activities'] == []
    assert result['extraction']['activities'][0]['quantity'] == '2577'
    assert result['extraction']['period_start'] == '2026-05-01'
    assert result['original_extraction'] == old
    with sessions() as session:
        assert session.get(Document, identifier).extraction == old


def test_month_mismatch_must_be_corrected_before_confirmation(workspace):
    from pathlib import Path
    client, *_ = workspace
    sample = (Path(__file__).resolve().parents[2] / 'ai' / 'synthetic_dataset'
              / 'electricity' / 'electricity-itemised-001-photo.png')
    response = client.post('/documents', headers=CLERK,
        data={'type':'electricity','period':'2026-09'},
        files={'file':('itemised.png',sample.read_bytes(),'image/png')})
    assert response.status_code == 201, response.text
    saved = response.json()
    activities = saved['extraction']['activities']
    fail = client.put(f"/documents/{saved['id']}/activities",headers=CLERK,
                      json={'confirmed':True,'expected_version':saved['version'],'activities':activities})
    assert fail.status_code == 422, fail.text
    assert get(client, f"/documents/{saved['id']}")['confirmed'] is False
    corrected = client.put(f"/documents/{saved['id']}",headers=CLERK,
        json={'name':saved['name'],'type':'electricity','period':'2026-05',
              'expected_version':saved['version'],'activities':activities})
    assert corrected.status_code == 200, corrected.text
    draft=corrected.json()
    approved = client.put(f"/documents/{saved['id']}/activities",headers=CLERK,
        json={'confirmed':True,'expected_version':draft['version'],'activities':activities})
    assert approved.status_code == 200, approved.text
    assert approved.json()['confirmed'] is True
    metric = next(m for m in get(client,'/profile?period=2026-05')['metrics'] if m['code']=='E1.2')
    assert saved['id'] in metric['evidence_ids']
    assert metric['value']=='1906.98'

"""Synthetic weighbridge receipts: extract transfer weight, NEVER infer waste outcome."""
from pathlib import Path
from sqlalchemy import select
from test_api import workspace, CLERK, get
from esg_backend.bill_ocr import extract_upload, parse_bill_text
from esg_backend.models import Document


SOURCE = (Path(__file__).resolve().parents[2] / 'ai' / 'synthetic_dataset'
          / 'waste' / 'waste-landscape-001-clean.png')


def test_exact_waste_weighbridge_ocr_detects_net_not_gross_or_tare():
    result=extract_upload(SOURCE.read_bytes(),'image/png','waste','2026-05')
    assert result['waste_transfer_candidate']['quantity']=='4850'
    assert result['waste_transfer_candidate']['unit']=='kg'
    assert result['document_date']=='2026-03-29'
    assert result['period_start']=='2026-03-29'
    assert result['period_end']=='2026-03-29'
    assert result['activities']==[]
    assert result['ocr_status']=='candidate_found'
    assert any('Transfer ticket date differs' in note for note in result['uncertainty_notes'])
    assert not any('waste_generated: no clearly labelled' in note for note in result['uncertainty_notes'])


def test_waste_net_weight_is_not_auto_classified_even_with_recycling_destination():
    result=parse_bill_text([
        'Tarikh: 29/03/2026','Tujuan: RECYCLING',
        'GROSS / BERAT KASAR','13,680 kg',
        'TARE / BERAT KENDERAAN','8,830 kg',
        'NET / BERAT BERSIH','4,850 kg'], 'waste','2026-03')
    assert result['waste_transfer_candidate']['quantity']=='4850'
    assert result['activities']==[]
    even_same_line=parse_bill_text([
        'Tujuan: RECYCLING 4,850 kg', 'Gross 13,680 kg', 'Tare 8,830 kg',
        'Net weight 4,850 kg'], 'waste','2026-03')
    assert even_same_line['activities']==[]
    assert even_same_line['waste_transfer_candidate']['quantity']=='4850'
    assert 'choose a supported esg waste category' in ' '.join(result['uncertainty_notes']).lower()


def test_conflicting_or_ambiguous_net_weights_are_not_suggested():
    conflict=parse_bill_text(['Gross 100 kg','Tare 90 kg','Net weight 20 kg'], 'waste','2026-03')
    assert conflict['waste_transfer_candidate'] is None
    assert any('conflicts with gross minus tare' in note for note in conflict['uncertainty_notes'])
    ambiguous=parse_bill_text(['Net weight 20 kg','Net weight 30 kg'], 'waste','2026-03')
    assert ambiguous['waste_transfer_candidate'] is None
    assert ambiguous['activities']==[]
    assert any('Multiple different net' in note for note in ambiguous['uncertainty_notes'])


def test_existing_waste_document_can_recover_old_failed_ocr_without_modifying_original(workspace):
    client,sessions,_,_=workspace
    response=client.post('/documents',headers=CLERK,
        data={'type':'waste','period':'2026-05'},
        files={'file':('synthetic-waste.png',SOURCE.read_bytes(),'image/png')})
    assert response.status_code==201,response.text
    initial=response.json()
    assert initial['confirmed'] is False and initial['activities']==[]
    assert initial['extraction']['waste_transfer_candidate']['quantity']=='4850'
    old={'ocr_engine':'RapidOCR (offline)','ocr_status':'manual_entry_required',
         'activities':[],'uncertainty_notes':['Previous OCR did not identify net weight']}
    with sessions() as db:
        row=db.get(Document,initial['id']);row.extraction=old;row.original_extraction=old;db.commit()
    reopened=get(client,f'/documents/{initial["id"]}')
    assert reopened['extraction']['waste_transfer_candidate']['quantity']=='4850'
    assert reopened['extraction']['period_start']=='2026-03-29'
    assert reopened['original_extraction']==old
    with sessions() as db:
        assert db.get(Document,initial['id']).extraction==old
    assert reopened['confirmed'] is False
    assert reopened['activities']==[]
    # No classification can be confirmed silently, even in the correct month.
    blank={'category':'','quantity':'4850','unit':'kg',
           'period_start':'2026-03-29','period_end':'2026-03-29','estimated':False}
    rejected=client.put(f'/documents/{initial["id"]}/activities',headers=CLERK,
        json={'activities':[blank],'confirmed':True,'expected_version':initial['version']})
    assert rejected.status_code==422
    # Selecting a category still cannot confirm under the wrong reporting month.
    blank['category']='waste_generated'
    mismatch=client.put(f'/documents/{initial["id"]}/activities',headers=CLERK,
        json={'activities':[blank],'confirmed':True,'expected_version':initial['version']})
    assert mismatch.status_code==422
    assert get(client,f'/documents/{initial["id"]}')['confirmed'] is False

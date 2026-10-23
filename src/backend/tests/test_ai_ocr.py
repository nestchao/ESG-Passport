"""External AI OCR adapter tests: mocked providers, no network calls or credentials."""
import json
from types import SimpleNamespace

from esg_backend import ai_ocr
from esg_backend.config import Settings


def settings(mode='offline'):
    return Settings(esg_ocr_mode=mode, gemini_api_key='example-only',
                    grafilab_api_key='example-only')


def test_offline_never_calls_remote(monkeypatch):
    monkeypatch.setattr(ai_ocr, '_gemini', lambda *a: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(ai_ocr, '_grafilab', lambda *a: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(ai_ocr, 'extract_upload', lambda *a: {'ocr_engine': 'offline'})
    assert ai_ocr.extract_with_ai(b'img', 'image/png', 'electricity', '2026-09',
                                  settings())['ocr_engine'] == 'offline'


def test_gemini_prefills_existing_review_schema(monkeypatch):
    monkeypatch.setattr(ai_ocr, '_image_bytes', lambda a,b: (a,b))
    monkeypatch.setattr(ai_ocr, '_gemini', lambda *a: [
        'Electricity Usage: 1234 kWh',
        'Billing Period: 01/09/2026 - 30/09/2026',
    ])
    got = ai_ocr.extract_with_ai(b'img', 'image/png', 'electricity', '2026-09',
                                  settings('gemini'))
    assert got['ocr_engine'] == 'Gemini (remote AI)'
    assert got['activities'][0]['quantity'] == '1234'
    assert got['activities'][0]['unit'] == 'kWh'
    assert 'confirmed_by' not in got['activities'][0]


def test_gemini_failure_falls_back_to_grafilab(monkeypatch):
    monkeypatch.setattr(ai_ocr, '_image_bytes', lambda a,b: (a,b))
    def unavailable(*args):
        raise ai_ocr.RemoteOcrError('upstream issue')
    monkeypatch.setattr(ai_ocr, '_gemini', unavailable)
    monkeypatch.setattr(ai_ocr, '_grafilab', lambda *args: ['Electricity Usage: 12 kWh'])
    got = ai_ocr.extract_with_ai(b'x', 'image/png', 'electricity', '2026-09',
                                  settings('gemini_grafilab_fallback'))
    assert got['ocr_engine'] == 'Grafilab (remote AI)'
    assert got['activities'][0]['quantity'] == '12'


def test_both_fail_offline_preserves_upload(monkeypatch):
    monkeypatch.setattr(ai_ocr, '_image_bytes', lambda a,b: (a,b))
    def fail(*args):
        raise ai_ocr.RemoteOcrError('failure')
    monkeypatch.setattr(ai_ocr, '_gemini', fail)
    monkeypatch.setattr(ai_ocr, '_grafilab', fail)
    monkeypatch.setattr(ai_ocr, 'extract_upload', lambda *a: {
        'ocr_engine': 'RapidOCR (offline)', 'uncertainty_notes': []})
    got = ai_ocr.extract_with_ai(b'x', 'image/png', 'electricity', '2026-09',
                                  settings('gemini_grafilab_fallback'))
    assert got['ocr_engine'] == 'RapidOCR (offline)'
    assert got['uncertainty_notes']


def test_compare_flags_conflicting_candidates(monkeypatch):
    monkeypatch.setattr(ai_ocr, '_image_bytes', lambda a,b: (a,b))
    monkeypatch.setattr(ai_ocr, '_gemini', lambda *a: ['Electricity Usage: 10 kWh'])
    monkeypatch.setattr(ai_ocr, '_grafilab', lambda *a: ['Electricity Usage: 20 kWh'])
    got = ai_ocr.extract_with_ai(b'x', 'image/png', 'electricity', '2026-09',
                                  settings('compare'))
    assert got['ocr_comparison']['agrees_on_candidates'] is False


def test_sandbox_never_calls_external_providers(monkeypatch):
    monkeypatch.setattr(ai_ocr, '_gemini', lambda *a: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(ai_ocr, 'extract_upload', lambda *a: {'ocr_engine': 'offline'})
    opts = SimpleNamespace(esg_ocr_mode='gemini', sandbox_instance=True)
    assert ai_ocr.extract_with_ai(b'x', 'image/png', 'water', '2026-09', opts)['ocr_engine']=='offline'


def test_valid_json_lines_rejected_if_extra_fields_or_invalid():
    assert ai_ocr._parse_lines(json.dumps({'lines': ['Water usage: 30 m3']})) == [
        'Water usage: 30 m3']
    for value in ('{}','{"lines": "injected"}', '{"lines": [], "status":"confirmed"}'):
        try:
            ai_ocr._parse_lines(value)
        except ai_ocr.RemoteOcrError:
            pass
        else:
            raise AssertionError('Invalid OCR JSON should be rejected')

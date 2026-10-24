"""Failure-injection checks; no network requests or new package installs."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from ai.workflow.ocr import OCRRouter, RoutingPolicy, OCRState
from ai.workflow.ocr.contract import OCRFailure, classify
from ai.workflow.ocr.providers import GrafilabOCR

PNG = b'\x89PNG\r\n\x1a\nfixture-only-mocked-provider'
PAYLOAD = {'text': 'SYNTHETIC: Electricity 120 kWh', 'fields': [], 'uncertainties': [], 'requires_human_review': True}


class FakeProvider:
    def __init__(self, name, *, error=None, remote=True, paid=False, structured=True, payload=None, cost='0.02', reservation='0.30'):
        self.identity, self.remote, self.paid = name, remote, paid
        self.error, self.structured = error, structured
        self.payload = PAYLOAD if payload is None else payload
        self.calls, self.metadata_calls, self.cost, self.reservation = 0, 0, cost, reservation

    def reservation_myr(self):
        self.metadata_calls += 1
        return self.reservation

    def extract(self, image, mime_type):
        self.calls += 1
        if self.error:
            raise self.error
        return {'payload': deepcopy(self.payload), 'structured': self.structured, 'cost_myr': self.cost,
                'returned_model': self.identity, 'lines': []}


class RoutingTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'src/ai/.local'
        root.mkdir(exist_ok=True)
        self.folder = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.folder.name) / 'routing.sqlite3'
        self.state = OCRState(self.path)
        self.google = FakeProvider('gemini:test')
        self.qwen = FakeProvider('grafilab:test', paid=True)
        self.local = FakeProvider('rapidocr:test', remote=False, structured=False)

    def tearDown(self):
        self.state.close()
        self.folder.cleanup()

    def router(self, paid=False, cap='0', clock=lambda: 100):
        return OCRRouter(gemini=self.google, grafilab=self.qwen, local=self.local, state=self.state,
                         policy=RoutingPolicy(paid_fallback=paid, paid_allowance_myr=cap), clock=clock)

    def test_primary_success_never_calls_fallbacks(self):
        result = self.router().extract('a', PNG, synthetic=True)
        self.assertEqual(result['engine'], self.google.identity)
        self.assertEqual((self.google.calls, self.qwen.calls, self.local.calls), (1, 0, 0))
        self.assertTrue(result['requires_human_review'])

    def test_missing_origin_flag_cannot_silently_upload_a_document(self):
        with self.assertRaises(ValueError):
            self.router().extract('a', PNG)
        self.assertEqual(self.google.calls, 0)

    def test_503_defaults_to_local_without_paid_request_or_metadata(self):
        self.google.error = OCRFailure('transient', 503)
        result = self.router().extract('a', PNG, synthetic=True)
        self.assertEqual(result['engine'], self.local.identity)
        self.assertEqual(result['status'], 'manual_review')
        self.assertEqual(result['field_status'], 'transcription_only')
        self.assertEqual((self.qwen.calls, self.qwen.metadata_calls), (0, 0))
        self.assertEqual(result['attempts'][0]['status_code'], 503)

    def test_approved_paid_fallback_reserves_and_reconciles_charge(self):
        self.google.error = OCRFailure('transient', 503)
        result = self.router(True, '0.50').extract('a', PNG, synthetic=True)
        self.assertEqual(result['engine'], self.qwen.identity)
        self.assertEqual(self.state.exposure_myr(), '0.02')
        self.assertEqual(self.local.calls, 0)

    def test_grafilab_failure_keeps_reservation_then_uses_local(self):
        self.google.error = OCRFailure('transient', 503)
        self.qwen.error = TimeoutError()
        result = self.router(True, '0.50').extract('a', PNG, synthetic=True)
        self.assertEqual(result['engine'], self.local.identity)
        self.assertEqual(self.state.exposure_myr(), '0.3')
        self.assertEqual((self.google.calls, self.qwen.calls, self.local.calls), (1, 1, 1))

    def test_exhausted_allowance_skips_paid_inference(self):
        self.google.error = OCRFailure('transient', 503)
        result = self.router(True, '0.10').extract('a', PNG, synthetic=True)
        self.assertEqual(self.qwen.calls, 0)
        self.assertIn('paid_budget_exhausted', [a.get('reason') for a in result['attempts']])

    def test_unknown_cost_holds_full_reservation_and_limits_next_job(self):
        self.google.error = OCRFailure('transient', 503)
        self.qwen.cost = None
        router = self.router(True, '0.50')
        router.extract('a', PNG, synthetic=True)
        result = router.extract('b', PNG, synthetic=True)
        self.assertEqual(self.qwen.calls, 1)
        self.assertEqual(result['engine'], self.local.identity)

    def test_unexpected_reported_charge_is_not_hidden_or_clamped(self):
        self.google.error = OCRFailure('transient', 503)
        self.qwen.cost = '0.80'
        result = self.router(True, '0.50').extract('a', PNG, synthetic=True)
        self.assertEqual(result['paid_exposure_myr'], '0.8')
        self.assertIn('reported_exposure_exceeded_local_allowance_paid_calls_blocked', result['warnings'])

    def test_circuit_skips_503_provider_then_recovers_for_a_new_job(self):
        self.google.error = OCRFailure('transient', 503)
        self.router().extract('a', PNG, synthetic=True)
        self.google.error = None
        result = self.router().extract('b', PNG, synthetic=True)
        self.assertEqual(result['attempts'][0]['reason'], 'circuit_open')
        self.assertEqual(self.google.calls, 1)
        result = self.router(clock=lambda: 221).extract('c', PNG, synthetic=True)
        self.assertEqual(result['engine'], self.google.identity)

    def test_same_completed_job_uses_cache_after_restart(self):
        self.router().extract('a', PNG, synthetic=True)
        self.state.close()
        self.state = OCRState(self.path)
        result = self.router().extract('a', PNG, synthetic=True)
        self.assertTrue(result['cache_hit'])
        self.assertEqual(self.google.calls, 1)
        with self.assertRaises(ValueError):
            self.router().extract('a', PNG+b'different', synthetic=True)

    def test_interrupted_job_cannot_resend_unknown_inference(self):
        self.state.claim('a', 'unknown-request-signature')
        with self.assertRaises(RuntimeError):
            self.state.claim('a', 'unknown-request-signature')

    def test_real_data_is_local_only(self):
        result = self.router(True, '1').extract('a', PNG, synthetic=False)
        self.assertEqual(result['engine'], self.local.identity)
        self.assertEqual((self.google.calls, self.qwen.calls, self.qwen.metadata_calls), (0, 0, 0))

    def test_auth_failure_does_not_trigger_paid_escalation(self):
        self.google.error = OCRFailure('authentication', 401)
        self.assertEqual(self.router(True, '1').extract('a', PNG, synthetic=True)['engine'], self.local.identity)
        self.assertEqual(self.qwen.calls, 0)

    def test_invalid_structured_output_is_not_reported_as_success(self):
        self.google.payload = {'text': 'looks valid but missing fields'}
        result = self.router(True, '1').extract('a', PNG, synthetic=True)
        self.assertEqual(result['engine'], self.local.identity)
        self.assertEqual(result['attempts'][0]['error_kind'], 'invalid_output')
        self.assertEqual(self.qwen.calls, 0)

    def test_all_engines_fail_preserves_audited_manual_entry_state(self):
        self.google.error = OCRFailure('transient', 503)
        self.local.error = OCRFailure('dependency_missing')
        result = self.router().extract('a', PNG, synthetic=True)
        self.assertIsNone(result['engine'])
        self.assertEqual(result['fields'], [])
        self.assertIn('all_eligible_engines_unavailable_manual_entry_required', result['warnings'])

    def test_invalid_image_and_negative_or_nonfinite_allowance_rejected(self):
        with self.assertRaises(ValueError):
            self.router().extract('a', b'not an image', synthetic=True)
        for allowance in ('NaN', '-1', 'Infinity'):
            with self.assertRaises(ValueError):
                RoutingPolicy(paid_allowance_myr=allowance)

    def test_failure_details_do_not_leak_exception_message(self):
        self.google.error = RuntimeError('SECRET_API_KEY=fake-secret-do-not-log')
        result = self.router().extract('a', PNG, synthetic=True)
        self.assertNotIn('fake-secret', str(result))

    def test_sdk_503_and_timeout_classified_without_error_text(self):
        error = RuntimeError('untrusted service message')
        error.code = 503
        self.assertEqual(classify(error).status_code, 503)
        self.assertEqual(classify(TimeoutError()).kind, 'timeout')

    def test_reservations_are_shared_between_database_connections(self):
        other = OCRState(self.path)
        try:
            self.assertTrue(self.state.reserve('a', 'p', '0.30', '0.50'))
            self.assertFalse(other.reserve('b', 'p', '0.30', '0.50'))
        finally:
            other.close()


class GrafilabAdapterTests(unittest.TestCase):
    def test_complete_fenced_json_is_parsed_but_incomplete_output_is_rejected(self):
        import json
        raw = {'model': 'grafilab/qwen3.5-397b-a17b', 'choices': [{'finish_reason': 'stop',
               'message': {'content': '```json\n' + json.dumps(PAYLOAD) + '\n```'}}],
               'usage': {'grafilab_cost_currency': 'MYR', 'grafilab_cost': 0.02}}
        http = SimpleNamespace(post=lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: raw))
        provider = GrafilabOCR('test-only', prices_confirmed=True, http=http)
        self.assertEqual(provider.extract(PNG, 'image/png')['payload'], PAYLOAD)
        raw['choices'][0]['finish_reason'] = 'length'
        with self.assertRaises(OCRFailure):
            provider.extract(PNG, 'image/png')

    def test_paid_adapter_preserves_503_for_router(self):
        http = SimpleNamespace(post=lambda *a, **kw: SimpleNamespace(status_code=503))
        with self.assertRaises(OCRFailure) as caught:
            GrafilabOCR('test-only', prices_confirmed=True, http=http).extract(PNG, 'image/png')
        self.assertEqual(caught.exception.status_code, 503)

    def test_catalogue_vision_and_context_are_checked_before_paid_inference(self):
        http = SimpleNamespace(get=lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: {
            'data': [{'id': 'grafilab/qwen3.5-397b-a17b', 'context_length': 128000, 'capabilities': {'vision': True}}]}))
        provider = GrafilabOCR('test-only', prices_confirmed=True, http=http)
        self.assertEqual(provider.reservation_myr(), '0.294912')
        http.get = lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: {'data': []})
        with self.assertRaises(OCRFailure):
            provider.reservation_myr()

    def test_paid_adapter_requires_explicit_price_confirmation(self):
        with self.assertRaises(OCRFailure):
            GrafilabOCR('test-only').reservation_myr()

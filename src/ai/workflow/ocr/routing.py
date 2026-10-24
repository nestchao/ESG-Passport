"""Bounded Gemini -> optional Grafilab -> local OCR, without hidden retries."""
from dataclasses import dataclass
from hashlib import sha256
import json
import time
from .contract import ROOT, OCRFailure, classify, validate_payload
from .state import micros


@dataclass(frozen=True)
class RoutingPolicy:
    paid_fallback: bool = False
    paid_allowance_myr: str = '0'
    circuit_cooldown_seconds: int = 120
    max_image_bytes: int = 10 * 1024 * 1024

    def __post_init__(self):
        micros(self.paid_allowance_myr)
        if self.circuit_cooldown_seconds < 0 or self.max_image_bytes <= 0:
            raise ValueError('Invalid routing limits')


class OCRRouter:
    def __init__(self, *, gemini, local, state, grafilab=None, policy=None, clock=time.time):
        self.gemini, self.local, self.grafilab = gemini, local, grafilab
        self.state, self.policy, self.clock = state, policy or RoutingPolicy(), clock

    def extract(self, job_id, image, *, mime_type='image/png', synthetic=None):
        if not isinstance(job_id, str) or not job_id or type(synthetic) is not bool or not isinstance(image, bytes) or not image:
            raise ValueError('Job ID, image bytes and explicit boolean data origin required')
        if len(image) > self.policy.max_image_bytes:
            raise ValueError('Image exceeds configured upload limit')
        magic = {'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff'}
        if mime_type not in magic or not image.startswith(magic[mime_type]):
            raise ValueError('Only PNG/JPEG pages with matching file signatures are accepted')
        digest = sha256(image).hexdigest()
        configuration = {'version': 'ocr-failover-v1', 'sha256': digest, 'mime': mime_type,
                         'contract_sha256': sha256((ROOT/'schema.json').read_bytes() + (ROOT/'prompt.txt').read_bytes()).hexdigest(),
                         'implementation_sha256': sha256(b''.join((ROOT/name).read_bytes() for name in
                             ('routing.py', 'providers.py', 'state.py', 'contract.py'))).hexdigest(),
                         'synthetic': synthetic, 'policy': self.policy.__dict__,
                         'providers': [getattr(p, 'configuration', {'identity': p.identity}) if p else None
                                       for p in (self.gemini, self.grafilab, self.local)]}
        signature = sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
        cached = self.state.claim(job_id, signature)
        if cached is not None:
            return {**cached, 'cache_hit': True}
        attempts = []
        result = {'job_id': job_id, 'image_sha256': digest, 'synthetic': synthetic, 'cache_hit': False,
                  'status': 'manual_review', 'engine': None, 'fields': [], 'text': '', 'attempts': attempts,
                  'requires_human_review': True, 'source_status': 'unverified_upload',
                  'warnings': [], 'field_status': 'unavailable', 'routing_version': 'ocr-failover-v1'}
        # One inference attempt per eligible provider. Only transient Gemini failures
        # allow paid escalation; authentication/configuration errors go to local OCR.
        allow_paid = False
        try:
            for provider in (self.gemini, self.grafilab, self.local):
                if provider is None:
                    continue
                entry = {'provider': provider.identity, 'started_at_unix': self.clock()}
                attempts.append(entry)
                if provider.remote and not synthetic:
                    entry.update(status='skipped', reason='real_data_cloud_policy_not_enabled')
                    continue
                if provider.paid and (not allow_paid or not self.policy.paid_fallback or micros(self.policy.paid_allowance_myr) == 0):
                    entry.update(status='skipped', reason='paid_fallback_not_authorised_or_no_allowance')
                    continue
                if provider.remote and self.state.circuit_open(provider.identity, self.clock()):
                    entry.update(status='skipped', reason='circuit_open')
                    if provider is self.gemini:
                        allow_paid = True
                    continue
                reserved = False
                began = time.monotonic()
                try:
                    reservation = provider.reservation_myr() if provider.paid else '0'
                    if provider.paid and micros(reservation) <= 0:
                        raise OCRFailure('positive_cost_reservation_required')
                    entry['reserved_myr'] = str(reservation)
                    if not self.state.reserve(job_id, provider.identity, reservation, self.policy.paid_allowance_myr):
                        entry.update(status='skipped', reason='paid_budget_exhausted')
                        continue
                    reserved = True
                    output = provider.extract(image, mime_type)
                    payload = validate_payload(output['payload'])
                    self.state.settle(job_id, provider.identity, success=True, actual_myr=output.get('cost_myr') if provider.paid else '0')
                    result.update(engine=provider.identity, text=payload['text'], fields=payload['fields'],
                                  field_status='candidate' if output['structured'] else 'transcription_only',
                                  status='success' if output['structured'] else 'manual_review',
                                  uncertainties=payload['uncertainties'], raw=output.get('raw'),
                                  lines=output.get('lines', []))
                    self.state.reset(provider.identity)
                    entry.update(status='success', elapsed_seconds=time.monotonic()-began,
                                 returned_model=output.get('returned_model'), actual_myr=output.get('cost_myr'))
                    if provider.paid and output.get('cost_myr') is not None and micros(output['cost_myr']) > micros(reservation):
                        result['warnings'].append('reported_charge_exceeded_reservation_check_provider_pricing')
                    if provider is not self.gemini:
                        result['warnings'].append('fallback_used')
                    if not output['structured']:
                        result['warnings'].append('local_transcription_requires_field_extraction_and_review')
                    break
                except Exception as error:
                    failure = classify(error)
                    entry.update(status='error', error_kind=failure.kind, status_code=failure.status_code,
                                 elapsed_seconds=time.monotonic()-began)
                    if reserved:
                        self.state.settle(job_id, provider.identity, success=False)
                    if failure.kind in ('transient', 'timeout'):
                        self.state.trip(provider.identity, self.clock()+self.policy.circuit_cooldown_seconds)
                        if provider is self.gemini:
                            allow_paid = True
            if result['engine'] is None:
                result['warnings'].append('all_eligible_engines_unavailable_manual_entry_required')
            result['paid_exposure_myr'] = self.state.exposure_myr()
            if self.policy.paid_fallback and micros(result['paid_exposure_myr']) > micros(self.policy.paid_allowance_myr):
                result['warnings'].append('reported_exposure_exceeded_local_allowance_paid_calls_blocked')
            self.state.finish(job_id, result)
            return result
        except BaseException:
            # Interrupted jobs remain claimed. A new upload/refresh cannot silently
            # repeat a request with an unknown outcome or duplicate its charge.
            raise

    def close(self):
        for provider in (self.gemini, self.grafilab, self.local):
            if provider is not None and hasattr(provider, 'close'):
                provider.close()
        self.state.close()

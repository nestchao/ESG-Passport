"""Lazy Gemini, Grafilab vision and CPU RapidOCR adapters; no implicit retries."""
from decimal import Decimal
from pathlib import Path
import base64
import json
import re
from .contract import OCRFailure, prompt


class GeminiOCR:
    remote, paid = True, False

    def __init__(self, api_key, *, billing_tier='unconfirmed', model='gemini-3.5-flash-lite', client=None):
        self.api_key, self.billing_tier, self.model = api_key, billing_tier, model
        self._client = client
        self.identity = 'gemini:' + model
        self.configuration = {'identity': self.identity, 'billing_tier': billing_tier}

    def extract(self, image, mime_type):
        if not self.api_key or self.billing_tier != 'free':
            raise OCRFailure('configuration')
        from google.genai import types
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(
                timeout=90000, retry_options=types.HttpRetryOptions(attempts=1)))
        result = self._client.models.generate_content(model=self.model, contents=[
            types.Part.from_bytes(data=image, mime_type=mime_type), prompt()],
            config=types.GenerateContentConfig(response_mime_type='application/json', temperature=0,
                                               max_output_tokens=8192, candidate_count=1))
        if not result.candidates or str(result.candidates[0].finish_reason).split('.')[-1] != 'STOP':
            raise OCRFailure('incomplete_output')
        try:
            payload = json.loads(result.text)
        except (ValueError, TypeError) as error:
            raise OCRFailure('invalid_output') from error
        return {'payload': payload, 'structured': True, 'returned_model': result.model_version,
                'raw': result.model_dump(mode='json', exclude_none=True)}

    def close(self):
        if self._client is not None:
            self._client.close()


class GrafilabOCR:
    remote, paid = True, True
    INPUT_RATE, OUTPUT_RATE = Decimal('1.60'), Decimal('11.00')
    MAX_CONTEXT, MAX_OUTPUT = 128000, 8192
    URL = 'https://llm.grafilab.ai/v1'

    def __init__(self, api_key, *, prices_confirmed=False, model='grafilab/qwen3.5-397b-a17b', http=None):
        if model != 'grafilab/qwen3.5-397b-a17b':
            raise ValueError('Only the reviewed vision model and MYR price policy are supported')
        self.api_key, self.prices_confirmed, self.model = api_key, prices_confirmed, model
        self._http = http
        self.identity = 'grafilab:' + model
        self.configuration = {'identity': self.identity, 'prices_confirmed': prices_confirmed,
                              'input_rate': str(self.INPUT_RATE), 'output_rate': str(self.OUTPUT_RATE)}

    def _transport(self):
        if not self.api_key or not self.prices_confirmed:
            raise OCRFailure('price_or_key_confirmation_required')
        if self._http is None:
            import httpx
            self._http = httpx.Client(timeout=httpx.Timeout(90, connect=15), follow_redirects=False,
                                      transport=httpx.HTTPTransport(retries=0))
        return self._http

    def reservation_myr(self):
        # Account-scoped catalogue check before sending any image or reserving inference.
        response = self._transport().get(self.URL + '/models', headers={'Authorization': 'Bearer ' + self.api_key})
        if response.status_code != 200:
            raise OCRFailure('catalogue_unavailable', response.status_code)
        model = next((m for m in response.json().get('data', []) if m['id'].lower() == self.model.lower()), None)
        if (not model or model.get('capabilities', {}).get('vision') is not True or
                type(model.get('context_length')) is not int or not 0 < model['context_length'] <= self.MAX_CONTEXT):
            raise OCRFailure('vision_or_context_not_verified')
        # Conservative input bound plus output bound. Rates are user-confirmed console
        # prices, not automatically assumed current or a provider-enforced billing cap.
        return str((self.MAX_CONTEXT*self.INPUT_RATE + self.MAX_OUTPUT*self.OUTPUT_RATE) / 1000000)

    def extract(self, image, mime_type):
        response = self._transport().post(self.URL + '/chat/completions',
            headers={'Authorization': 'Bearer ' + self.api_key},
            json={'model': self.model, 'messages': [{'role': 'user', 'content': [
                {'type': 'image_url', 'image_url': {'url': 'data:' + mime_type + ';base64,' + base64.b64encode(image).decode()}},
                {'type': 'text', 'text': prompt()}]}], 'temperature': 0, 'max_tokens': self.MAX_OUTPUT, 'stream': False})
        if response.status_code != 200:
            raise OCRFailure('transient' if response.status_code in (429, 500, 502, 503, 504) else 'provider_error', response.status_code)
        raw = response.json()
        try:
            choice = raw['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise OCRFailure('incomplete_output')
            text = choice['message']['content']
            fence = re.fullmatch(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text.strip())
            payload = json.loads(fence.group(1) if fence else text)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise OCRFailure('invalid_output') from error
        usage = raw.get('usage', {})
        cost = None
        if usage.get('grafilab_cost_currency') == 'MYR':
            try:
                amount = Decimal(str(usage['grafilab_cost']))
                if amount.is_finite() and amount >= 0:
                    cost = str(amount)
            except (KeyError, ArithmeticError):
                pass
        return {'payload': payload, 'structured': True, 'returned_model': raw.get('model'),
                'raw': raw, 'cost_myr': cost}

    def close(self):
        if self._http is not None:
            self._http.close()


class RapidOCREngine:
    remote, paid = False, False
    identity = 'rapidocr:cpu:ppocr-v6'

    def __init__(self, engine=None):
        self._engine = engine

    def _load(self):
        if self._engine is not None:
            return
        from importlib.util import find_spec
        from rapidocr import RapidOCR
        import onnxruntime
        folder = Path(find_spec('rapidocr').origin).parent / 'models'
        names = {'Det': 'PP-OCRv6_det_small.onnx', 'Rec': 'PP-OCRv6_rec_small.onnx',
                 'Cls': 'ch_ppocr_mobile_v2.0_cls_mobile.onnx'}
        if any(not (folder / name).is_file() for name in names.values()):
            raise OCRFailure('local_weights_missing_no_download')
        if 'CPUExecutionProvider' not in onnxruntime.get_available_providers():
            raise OCRFailure('cpu_provider_missing')
        params = {key + '.model_path': str(folder / name) for key, name in names.items()}
        params.update({'Global.log_level': 'warning', 'EngineConfig.onnxruntime.use_cuda': False,
                       'EngineConfig.onnxruntime.use_dml': False, 'EngineConfig.onnxruntime.use_cann': False,
                       'EngineConfig.onnxruntime.use_coreml': False,
                       'EngineConfig.onnxruntime.intra_op_num_threads': 2,
                       'EngineConfig.onnxruntime.inter_op_num_threads': 1})
        self._engine = RapidOCR(params=params)

    def extract(self, image, mime_type):
        import cv2
        import numpy as np
        self._load()
        decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            raise OCRFailure('invalid_image')
        output = self._engine(decoded)
        texts = list(output.txts) if output.txts is not None else []
        scores = list(output.scores) if output.scores is not None else []
        boxes = output.boxes.tolist() if output.boxes is not None else []
        lines = [{'text': text, 'engine_score': float(score), 'box': box}
                 for text, score, box in zip(texts, scores, boxes, strict=True)]
        # Preserve engine order and coordinates; do not claim generic layout reconstruction.
        return {'payload': {'text': '\n'.join(texts), 'fields': [], 'requires_human_review': True,
                            'uncertainties': ['Local OCR provides text/boxes only; field mapping and layout order need review.',
                                              'Engine scores are not calibrated probabilities of correctness.']},
                'structured': False, 'lines': lines, 'returned_model': self.identity}

    def close(self):
        self._engine = None

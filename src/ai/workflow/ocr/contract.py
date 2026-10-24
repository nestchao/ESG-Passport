"""Common untrusted OCR output contract and sanitised provider errors."""
from pathlib import Path
import json
import jsonschema

ROOT = Path(__file__).resolve().parent


class OCRFailure(Exception):
    def __init__(self, kind, status_code=None):
        super().__init__(kind)
        self.kind = kind
        self.status_code = status_code


def validate_payload(payload):
    schema = json.loads((ROOT / 'schema.json').read_text(encoding='utf-8'))
    try:
        jsonschema.validate(payload, schema)
        if not payload['text'].strip():
            raise ValueError('Empty transcription')
    except (jsonschema.ValidationError, ValueError, TypeError) as error:
        raise OCRFailure('invalid_output') from error
    return payload


def prompt():
    return (ROOT / 'prompt.txt').read_text(encoding='utf-8')


def classify(error):
    if isinstance(error, OCRFailure):
        if error.status_code in (429, 500, 502, 503, 504):
            return OCRFailure('transient', error.status_code)
        return error
    code = getattr(error, 'code', None) or getattr(getattr(error, 'response', None), 'status_code', None)
    code = code if isinstance(code, int) else None
    if code in (429, 500, 502, 503, 504):
        return OCRFailure('transient', code)
    if code in (401, 403):
        return OCRFailure('authentication', code)
    if isinstance(error, TimeoutError) or 'timeout' in type(error).__name__.lower():
        return OCRFailure('timeout')
    if isinstance(error, ImportError):
        return OCRFailure('dependency_missing')
    return OCRFailure('provider_error', code)

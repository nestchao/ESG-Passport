"""Project-local configuration; cloud clients stay lazy until an eligible attempt."""
from pathlib import Path
from .providers import GeminiOCR, GrafilabOCR, RapidOCREngine
from .routing import OCRRouter, RoutingPolicy
from .state import OCRState


def create_router(*, state_path, project_root=None):
    from dotenv import dotenv_values
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[4]
    settings = dotenv_values(root / '.env', interpolate=False)
    mode = settings.get('OCR_FALLBACK_MODE', 'local')
    if mode not in ('local', 'grafilab_then_local'):
        raise ValueError('OCR_FALLBACK_MODE must be local or grafilab_then_local')
    paid = mode == 'grafilab_then_local'
    if paid and settings.get('GRAFILAB_BASE_URL', GrafilabOCR.URL).rstrip('/') != GrafilabOCR.URL:
        raise ValueError('Only the reviewed Grafilab host is supported')
    grafilab = GrafilabOCR(settings.get('GRAFILAB_API_KEY'),
                          prices_confirmed=settings.get('OCR_GRAFILAB_PRICES_CONFIRMED') == 'true') if paid else None
    return OCRRouter(gemini=GeminiOCR(settings.get('GEMINI_API_KEY'),
                                     billing_tier=settings.get('GOOGLE_API_BILLING_TIER')),
                     grafilab=grafilab, local=RapidOCREngine(), state=OCRState(state_path),
                     policy=RoutingPolicy(paid_fallback=paid,
                                          paid_allowance_myr=settings.get('OCR_GRAFILAB_ALLOWANCE_MYR', '0')))

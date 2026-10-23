"""Verify Gemini -> Grafilab failover at mocked HTTP transport level.

No real API calls, model credits or live credentials are used in these tests.
"""
import json
from io import BytesIO

import httpx
from PIL import Image

from esg_backend import ai_ocr
from esg_backend.config import Settings


def fake_png():
    output = BytesIO()
    Image.new("RGB", (120, 70), "white").save(output, format="PNG")
    return output.getvalue()


def config(mode="gemini_grafilab_fallback"):
    return Settings(
        esg_ocr_mode=mode,
        esg_compare_models=("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"),
        gemini_api_key="TEST_GEMINI_KEY_DO_NOT_USE",
        grafilab_api_key="TEST_GRAFILAB_KEY_DO_NOT_USE",
    )


def test_gemini_http_429_calls_real_grafilab_adapter_via_mocked_transport(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        request = httpx.Request("POST", url)
        if "generativelanguage.googleapis.com" in url:
            calls.append("gemini")
            assert url.endswith("/gemini-3.5-flash-lite:generateContent")
            assert kwargs["headers"]["x-goog-api-key"] == "TEST_GEMINI_KEY_DO_NOT_USE"
            return httpx.Response(
                429, request=request,
                json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}},
            )
        assert url == "https://llm.grafilab.ai/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer TEST_GRAFILAB_KEY_DO_NOT_USE"
        assert kwargs["follow_redirects"] is False
        calls.append("grafilab")
        return httpx.Response(
            200, request=request, json={"choices": [{
                "finish_reason": "stop",
                "message": {"content": json.dumps({"lines": [
                    "Electricity usage: 2577 kWh",
                    "Billing Period: 01/05/2026 - 31/05/2026",
                ]})},
            }]},
        )

    monkeypatch.setattr(ai_ocr.httpx, "post", fake_post)
    result = ai_ocr.extract_with_ai(fake_png(), "image/png",
                                    "electricity", "2026-05", config())
    assert calls == ["gemini", "grafilab"]
    assert result["ocr_engine"] == "Grafilab (remote AI)"
    assert result["ocr_model"] == "grafilab/qwen3.5-397b-a17b"
    assert result["activities"][0]["quantity"] == "2577"
    assert result["activities"][0]["unit"] == "kWh"
    assert result["activities"][0]["period_start"] == "2026-05-01"
    assert "confirmed_at" not in result["activities"][0]
    assert any("Gemini HTTP 429" in text for text in result["uncertainty_notes"])
    assert "TEST_GEMINI_KEY_DO_NOT_USE" not in str(result)
    assert "TEST_GRAFILAB_KEY_DO_NOT_USE" not in str(result)


def test_successful_gemini_does_not_call_grafilab(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        assert "generativelanguage.googleapis.com" in url
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "candidates": [{"finishReason": "STOP", "content": {
                "parts": [{"text": json.dumps({"lines": ["Electricity usage: 42 kWh"]})}]
            }}],
        })

    monkeypatch.setattr(ai_ocr.httpx, "post", fake_post)
    result = ai_ocr.extract_with_ai(fake_png(), "image/png",
                                    "electricity", "2026-05", config())
    assert len(calls) == 1
    assert result["ocr_engine"] == "Gemini (remote AI)"
    assert result["ocr_model"] == "gemini-3.5-flash-lite"


def test_both_providers_http_errors_fall_back_to_offline(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        code = 503 if "grafilab" in url else 429
        return httpx.Response(code, request=httpx.Request("POST", url),
                              json={"error": {"code": code}})

    def fake_offline(*args):
        return {"ocr_engine": "RapidOCR (offline)", "uncertainty_notes": [],
                "activities": []}

    monkeypatch.setattr(ai_ocr.httpx, "post", fake_post)
    monkeypatch.setattr(ai_ocr, "extract_upload", fake_offline)
    result = ai_ocr.extract_with_ai(fake_png(), "image/png",
                                    "electricity", "2026-05", config())
    assert len(calls) == 2
    assert result["ocr_engine"] == "RapidOCR (offline)"
    assert "Gemini HTTP 429" in result["uncertainty_notes"][-1]
    assert "Grafilab HTTP 503" in result["uncertainty_notes"][-1]


def test_gemini_timeout_or_invalid_json_uses_grafilab(monkeypatch):
    for scenario in ("timeout", "invalid_json"):
        calls = []

        def fake_post(url, **kwargs):
            request = httpx.Request("POST", url)
            if "generativelanguage.googleapis.com" in url:
                calls.append("gemini")
                if scenario == "timeout":
                    raise httpx.ReadTimeout("simulated timeout", request=request)
                return httpx.Response(200, request=request, json={
                    "candidates": [{"finishReason": "STOP", "content": {
                        "parts": [{"text": "not JSON"}]}}]
                })
            calls.append("grafilab")
            return httpx.Response(200, request=request, json={
                "choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps({"lines": ["Electricity usage: 101 kWh"]})
                }}]
            })

        monkeypatch.setattr(ai_ocr.httpx, "post", fake_post)
        result = ai_ocr.extract_with_ai(fake_png(), "image/png",
                                        "electricity", "2026-05", config())
        assert calls == ["gemini", "grafilab"]
        assert result["ocr_engine"] == "Grafilab (remote AI)"
        assert result["activities"][0]["quantity"] == "101"


def test_compare_mode_uses_two_gemini_models_without_grafilab(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        assert "generativelanguage.googleapis.com" in url
        calls.append(url)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "candidates": [{"finishReason": "STOP", "content": {
                "parts": [{"text": json.dumps({"lines": ["Electricity usage: 42 kWh"]})}]
            }}],
        })

    monkeypatch.setattr(ai_ocr.httpx, "post", fake_post)
    result = ai_ocr.extract_with_ai(fake_png(), "image/png",
                                    "electricity", "2026-05", config("compare"))
    assert len(calls) == 2
    assert "/gemini-3.5-flash-lite:generateContent" in calls[0]
    assert "/gemini-3.1-flash-lite:generateContent" in calls[1]
    assert result["ocr_comparison"]["status"] == "completed"

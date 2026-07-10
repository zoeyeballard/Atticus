"""Provider selection for the unified LLM client (no network)."""

from src.generation.llm_client import LLMClient, Usage, _extract_json


def test_extract_json_top_level_array():
    # Decomposition prompts return arrays; must not be corrupted into "Extra data" errors.
    text = '[\n  {"claim_text": "a", "claim_type": "citation"},\n  {"claim_text": "b", "claim_type": "factual_assertion"}\n]'
    data = _extract_json(text)
    assert isinstance(data, list) and len(data) == 2


def test_extract_json_array_with_prose_and_fences():
    text = 'Here you go:\n```json\n[{"claim_text": "x", "claim_type": "citation"}]\n```\nLet me know!'
    data = _extract_json(text)
    assert isinstance(data, list) and data[0]["claim_type"] == "citation"


def test_extract_json_object_with_trailing_prose():
    text = '{"rejections": []}\n\nI hope this helps.'
    data = _extract_json(text)
    assert data == {"rejections": []}


def test_extract_json_salvages_truncated_array():
    # A max_tokens truncation mid-element must yield the complete elements, not nothing.
    text = '[{"claim_text": "a", "claim_type": "citation"}, {"claim_text": "b", "claim_type": "factual_assertion"}, {"claim_text": "unterminated'
    data = _extract_json(text)
    assert isinstance(data, list) and len(data) == 2
    assert data[1]["claim_text"] == "b"


def test_gemini_pricing_tracked():
    u = Usage()
    u.add("gemini-2.5-flash", 1_000_000, 1_000_000)  # $0.30 in + $2.50 out
    assert round(u.cost_usd, 2) == 2.80


def test_provider_selects_models(monkeypatch):
    from src.config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    client = LLMClient()
    assert client.provider == "gemini"
    assert client.generation_model.startswith("gemini")
    assert client.verification_model.startswith("gemini")
    settings_mod.get_settings.cache_clear()


def test_missing_key_raises_clear_error(monkeypatch):
    from src.config import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    client = LLMClient()
    try:
        _ = client.client  # accessing the provider client with no key
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "gemini" in str(exc).lower()
    finally:
        settings_mod.get_settings.cache_clear()

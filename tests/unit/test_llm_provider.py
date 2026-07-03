"""Provider selection for the unified LLM client (no network)."""

from src.generation.llm_client import LLMClient, Usage


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

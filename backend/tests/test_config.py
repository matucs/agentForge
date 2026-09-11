from app.config import Settings


def test_blank_api_key_env_var_is_not_treated_as_configured(monkeypatch) -> None:
    """A real deployment mistake: DEFAULT env files often set KEY= (blank)
    rather than omitting the line. That must still read as "not configured",
    matching the falsy check the LLM providers themselves use — otherwise
    /api/health would claim a provider is ready when it cannot make calls."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    settings = Settings()
    assert not settings.anthropic_api_key

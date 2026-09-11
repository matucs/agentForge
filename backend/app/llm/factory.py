from functools import lru_cache

from app.config import Settings, get_settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.openai_provider import OpenAIProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


def build_provider(name: str, settings: Settings) -> LLMProvider:
    try:
        provider_cls = _PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown LLM provider '{name}'. Available: {sorted(_PROVIDERS)}"
        ) from exc
    return provider_cls(settings)


@lru_cache
def get_default_provider() -> LLMProvider:
    settings = get_settings()
    return build_provider(settings.default_llm_provider, settings)

from app.config import Settings
from app.llm.base import LLMProvider, LLMProviderUnavailable, LLMResponse, LLMUsage

_PRICING_PER_MTOK = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}
_DEFAULT_PRICING = {"input": 2.50, "output": 10.00}


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None
        if settings.openai_api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    def is_configured(self) -> bool:
        return self._client is not None

    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        if self._client is None:
            raise LLMProviderUnavailable(
                "OpenAI provider selected but OPENAI_API_KEY is not set. "
                "Configure OPENAI_API_KEY to enable this feature."
            )

        model = self._settings.openai_model
        response = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )

        text = response.choices[0].message.content or ""
        pricing = _PRICING_PER_MTOK.get(model, _DEFAULT_PRICING)
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0
        cost = (input_tokens / 1_000_000) * pricing["input"] + (
            output_tokens / 1_000_000
        ) * pricing["output"]

        return LLMResponse(
            text=text,
            model=model,
            provider=self.name,
            usage=LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=round(cost, 6),
            ),
        )

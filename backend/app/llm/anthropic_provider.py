from app.config import Settings
from app.llm.base import LLMProvider, LLMProviderUnavailable, LLMResponse, LLMUsage

# USD per token, as of model release pricing. Kept explicit (not hidden in a
# third-party pricing table) so evaluation cost numbers are auditable.
_PRICING_PER_MTOK = {
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
}
_DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None
        if settings.anthropic_api_key:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

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
                "Anthropic provider selected but ANTHROPIC_API_KEY is not set. "
                "Configure ANTHROPIC_API_KEY to enable this feature."
            )

        model = self._settings.anthropic_model
        response = await self._client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            extra_body={"temperature": temperature},
        )

        text = "".join(block.text for block in response.content if block.type == "text")
        pricing = _PRICING_PER_MTOK.get(model, _DEFAULT_PRICING)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
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

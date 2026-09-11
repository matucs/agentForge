from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    provider: str
    usage: LLMUsage


class LLMProviderUnavailable(RuntimeError):
    """Raised when a provider is selected but its credentials are absent.

    Callers must surface this as an explicit "integration unavailable"
    state (per project rule: no fake AI, no simulated responses) rather
    than falling back to canned text.
    """


class LLMProvider(ABC):
    """Common interface every model provider implements.

    Keeping this abstraction thin (single `complete` method) is deliberate:
    agents depend on this interface, never on a concrete SDK, so swapping
    or adding providers never touches agent code.
    """

    name: str

    @abstractmethod
    def __init__(self, settings: Settings) -> None: ...

    @abstractmethod
    def is_configured(self) -> bool:
        """True if credentials required to make real calls are present."""

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Issue a real completion call. Must raise LLMProviderUnavailable
        if not configured — never return synthetic text."""

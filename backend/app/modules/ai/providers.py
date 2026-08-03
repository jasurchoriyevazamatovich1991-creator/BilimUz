"""
AIProvider interface + AIRequest/AIResponse — infrastructure used by
AIService, same relationship StorageBackend/EmailProvider have to their
respective services (Sprint 8). NOT a new architectural layer.

Per the approved Sprint 9 scope: NO vendor SDK (OpenAI, Anthropic,
Gemini, or any other) is imported anywhere in this module.
UnconfiguredAIProvider is the only implementation — it honestly raises
rather than pretending to generate a response. A future sprint adds a
real implementation (e.g. OpenAIProvider) and wires it in via
get_ai_provider() — zero change to AIService.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.modules.ai.exceptions import AIProviderNotConfiguredException


@dataclass
class AIMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class AIRequest:
    prompt: str
    history: list[AIMessage] = field(default_factory=list)


@dataclass
class AIResponse:
    content: str
    provider: str
    model: str | None = None
    tokens_used: int | None = None


class AIProvider(ABC):
    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Raises on any failure (including 'not configured'). Returns
        normally only on a confirmed, real generated response."""
        ...


class UnconfiguredAIProvider(AIProvider):
    """The only AIProvider implementation this sprint. Honest, not fake:
    real vendor integration is explicitly deferred (see module docstring)."""

    def generate(self, request: AIRequest) -> AIResponse:
        raise AIProviderNotConfiguredException(
            "AI provayder ulanmagan — haqiqiy vendor integratsiyasi keyingi sprintga qoldirilgan"
        )

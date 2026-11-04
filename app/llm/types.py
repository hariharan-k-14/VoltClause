from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    estimated: bool = False


@dataclass(frozen=True)
class TextChunk:
    text: str
    usage: Usage | None = None


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[Message, ...]
    model: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: Usage


class ProviderError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.retry_after = retry_after

    def __str__(self) -> str:
        return self.message


class LLMProvider:
    def stream(self, request: LLMRequest):
        raise NotImplementedError

    async def stream_async(self, request: LLMRequest) -> AsyncIterator[TextChunk]:
        raise NotImplementedError
